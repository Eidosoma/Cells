"""One live fuel/chemical cytosol with compliant water and fixed-volume ER."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_calcium_energy_spec as energy
from cells.core import surface_calcium_spec as calcium
from cells.core import surface_kinetic_spec as kinetic
from cells.core import surface_water_spec as water
from cells.core.spatial_calcium_spec import project
from cells.core.specs import ConfigError, _fields
from cells.core.surface_calcium_water_spec import OSMOTIC_COUPLING_ID as CHEMICAL_COUPLING_ID
from cells.core.surface_energy_water_spec import OSMOTIC_COUPLING_ID as ENERGY_COUPLING_ID

MODEL_ID = "resolved_calcium_energy_water@1"


@dataclass(frozen=True)
class SurfaceCalciumEnergyWaterModel(energy.SurfaceCalciumEnergyMorrisLecarModel):
    chemical_osmotic_coupling: str
    energy_osmotic_coupling: str
    water_compartments: tuple[water.WaterCompartment, ...]
    water_membranes: tuple[water.WaterMembrane, ...]


Control = NamedTuple(
    "SurfaceCalciumEnergyWaterControl",
    [(k, object) for k in (*energy.Control._fields, "water")],
)


@dataclass(frozen=True)
class Change(energy.Change):
    water: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(energy.Experiment):
    water: tuple

    @property
    def changes(self):
        groups = (super().changes, *self.water)
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


def energy_spec(spec):
    """Remove only water; retain the exact finite-pool owners and pump routes."""
    return replace(
        spec,
        model=project(spec.model, energy.SurfaceCalciumEnergyMorrisLecarModel),
        experiment=project(spec.experiment, energy.Experiment),
    )


def water_spec(spec):
    """Geometry/schema projection; never a source of stage fuel concentrations."""
    passive = kinetic.passive_spec(calcium.ionic_spec(energy.initial_prior_spec(energy_spec(spec))))
    return replace(
        passive,
        model=water.SurfaceWaterModel(
            **vars(passive.model),
            water_compartments=spec.model.water_compartments,
            water_membranes=spec.model.water_membranes,
        ),
        experiment=water.Experiment(**vars(passive.experiment), water=spec.experiment.water),
    )


def minimum_energy_spec(spec):
    """Minimum-volume inputs for conservative bounds, never a physical state."""
    parent = energy_spec(spec)
    volumes = {row.compartment_id: row.minimum_volume_pL for row in spec.model.water_compartments}
    return replace(
        parent,
        experiment=spec.experiment,
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
    if (
        type(spec.model) is not SurfaceCalciumEnergyWaterModel
        or type(spec.experiment) is not Experiment
    ):
        raise ConfigError("Calcium energy water requires its explicit model and experiment")
    raw = energy.to_dict(energy_spec(spec))
    raw["model"].update(
        id=MODEL_ID,
        chemical_osmotic_coupling=spec.model.chemical_osmotic_coupling,
        energy_osmotic_coupling=spec.model.energy_osmotic_coupling,
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
        chemical = raw["model"].pop("chemical_osmotic_coupling")
        fuel = raw["model"].pop("energy_osmotic_coupling")
        compartments = raw["model"].pop("water_compartments")
        membranes = raw["model"].pop("water_membranes")
        controls = raw["experiment"].pop("water_controls")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError(
            "Joint calcium/fuel/water requires explicit particles, owners and controls"
        ) from error
    if chemical != CHEMICAL_COUPLING_ID or fuel != ENERGY_COUPLING_ID:
        raise ConfigError("Require all-species cytosol and neutral ATP/ADP/Pi osmotic coupling")
    raw["model"]["id"] = energy.MORRIS_LECAR_MODEL_ID
    original = energy.parse(raw)
    passive = kinetic.passive_spec(
        calcium.ionic_spec(energy.initial_prior_spec(original))
    ).to_dict()
    passive["model"].update(
        id=water.MODEL_ID, water_compartments=compartments, water_membranes=membranes
    )
    passive["experiment"]["water_controls"] = controls
    validated = water.parse(passive)
    spec = replace(
        original,
        model=SurfaceCalciumEnergyWaterModel(
            **vars(original.model),
            chemical_osmotic_coupling=chemical,
            energy_osmotic_coupling=fuel,
            water_compartments=validated.model.water_compartments,
            water_membranes=validated.model.water_membranes,
        ),
        experiment=Experiment(**vars(original.experiment), water=validated.experiment.water),
    )
    from cells.models import surface_calcium_energy_water

    try:
        surface_calcium_energy_water.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid calcium energy water definition: " + str(error)) from error
    return spec
