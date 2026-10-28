"""One chemical cytosol/water owner and a fixed-volume ER per resolved cell."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_calcium_spec as prior
from cells.core import surface_kinetic_spec as kinetic
from cells.core import surface_water_spec as water
from cells.core.spatial_calcium_spec import project
from cells.core.specs import ConfigError, _fields

MODEL_ID = "resolved_calcium_water@1"
OSMOTIC_COUPLING_ID = "ideal_all_cytosol_species_fixed_er@1"


@dataclass(frozen=True)
class SurfaceCalciumWaterModel(prior.SurfaceCalciumMorrisLecarModel):
    chemical_osmotic_coupling: str
    water_compartments: tuple[water.WaterCompartment, ...]
    water_membranes: tuple[water.WaterMembrane, ...]


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    er_reactions: object
    er_passive: object
    er_pump: object
    er_release: object
    plasma_pump: object
    plasma_exchange: object
    calcium_channel: object
    water: object


@dataclass(frozen=True)
class Change(prior.Change):
    water: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    water: tuple

    @property
    def changes(self):
        original = super().changes
        groups = (original, *self.water)
        clocks = [[p.time for p in group] for group in groups]
        result = []
        for time in sorted({t for clock in clocks for t in clock}):
            held = [g[bisect_right(c, time) - 1] for g, c in zip(groups, clocks, strict=True)]
            result.append(
                Change(
                    **(vars(held[0]) | {"time": time}),
                    water=tuple(p.availability for p in held[1:]),
                )
            )
        return tuple(result)


def prior_spec(spec):
    return replace(
        spec,
        model=project(spec.model, prior.SurfaceCalciumMorrisLecarModel),
        experiment=project(spec.experiment, prior.Experiment),
    )


def water_spec(spec):
    passive = kinetic.passive_spec(prior.ionic_spec(prior_spec(spec)))
    return replace(
        passive,
        model=water.SurfaceWaterModel(
            **vars(passive.model),
            water_compartments=spec.model.water_compartments,
            water_membranes=spec.model.water_membranes,
        ),
        experiment=water.Experiment(**vars(passive.experiment), water=spec.experiment.water),
    )


def minimum_volume_spec(spec):
    """Conservative loss-bound inputs; this is never a physical trial state."""
    parent = prior_spec(spec)
    volumes = {row.compartment_id: row.minimum_volume_pL for row in spec.model.water_compartments}
    return replace(
        parent,
        model=replace(
            parent.model,
            cells=tuple(replace(row, volume_pL=volumes[row.id]) for row in parent.model.cells),
            extracellular=tuple(
                replace(row, volume_pL=volumes[row.id]) for row in parent.model.extracellular
            ),
            stores=tuple(
                replace(
                    store,
                    compartments=tuple(
                        replace(row, volume_pL=volumes[cell.id])
                        if row.id == store.membrane.cytosol
                        else row
                        for row in store.compartments
                    ),
                )
                for cell, store in zip(parent.model.cells, parent.model.stores, strict=True)
            ),
        ),
    )


def to_dict(spec):
    if type(spec.model) is not SurfaceCalciumWaterModel or type(spec.experiment) is not Experiment:
        raise ConfigError("Calcium water requires its explicit model and experiment")
    raw = prior.to_dict(prior_spec(spec))
    raw["model"].update(
        id=MODEL_ID,
        chemical_osmotic_coupling=spec.model.chemical_osmotic_coupling,
        water_compartments=[asdict(row) for row in spec.model.water_compartments],
        water_membranes=[asdict(row) for row in spec.model.water_membranes],
    )
    raw["experiment"]["water_controls"] = [
        dict(membrane_id=patch.id, schedule=[asdict(c) for c in group])
        for patch, group in zip(spec.model.membranes, spec.experiment.water, strict=True)
    ]
    return raw


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    raw = deepcopy(data)
    if not isinstance(raw["model"], dict) or raw["model"].get("id") != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    try:
        coupling = raw["model"].pop("chemical_osmotic_coupling")
        compartments = raw["model"].pop("water_compartments")
        membranes = raw["model"].pop("water_membranes")
        controls = raw["experiment"].pop("water_controls")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError(
            "Calcium water requires explicit chemical particles, owners and controls"
        ) from error
    if coupling != OSMOTIC_COUPLING_ID:
        raise ConfigError("Require explicit all-species cytosol osmosis with fixed ER")
    raw["model"]["id"] = prior.MORRIS_LECAR_MODEL_ID
    original = prior.parse(raw)
    passive = kinetic.passive_spec(prior.ionic_spec(original)).to_dict()
    passive["model"].update(
        id=water.MODEL_ID, water_compartments=compartments, water_membranes=membranes
    )
    passive["experiment"]["water_controls"] = controls
    validated = water.parse(passive)
    spec = replace(
        original,
        model=SurfaceCalciumWaterModel(
            **vars(original.model),
            chemical_osmotic_coupling=coupling,
            water_compartments=validated.model.water_compartments,
            water_membranes=validated.model.water_membranes,
        ),
        experiment=Experiment(**vars(original.experiment), water=validated.experiment.water),
    )
    from cells.models import surface_calcium_water

    try:
        surface_calcium_water.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid calcium water definition: " + str(error)) from error
    return spec
