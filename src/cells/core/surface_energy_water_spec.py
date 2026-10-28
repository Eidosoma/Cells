"""Finite cellular energy with explicit neutral pool osmolytes and compliant water."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_energy_spec as energy
from cells.core import surface_kinetic_spec as kinetic
from cells.core import surface_water_spec as water
from cells.core.specs import ConfigError, _fields

MODEL_ID = "resolved_energy_water@1"
MORRIS_LECAR_MODEL_ID = "resolved_energy_water@2"
OSMOTIC_COUPLING_ID = "neutral_ideal_atp_adp_pi@1"


@dataclass(frozen=True)
class SurfaceEnergyWaterModel(energy.SurfaceEnergyModel):
    energy_osmotic_coupling: str
    water_compartments: tuple[water.WaterCompartment, ...]
    water_membranes: tuple[water.WaterMembrane, ...]


@dataclass(frozen=True)
class SurfaceEnergyWaterMorrisLecarModel(SurfaceEnergyWaterModel):
    """53-law finite fuel and water with current owner-local concentrations."""


def model_id(model):
    return (
        MORRIS_LECAR_MODEL_ID if isinstance(model, SurfaceEnergyWaterMorrisLecarModel) else MODEL_ID
    )


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    regeneration: object
    water: object


@dataclass(frozen=True)
class Change(energy.Change):
    water: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(energy.Experiment):
    water: tuple

    @property
    def changes(self):
        families = (
            self.membranes,
            self.junctions,
            self.channels,
            self.pumps,
            self.regenerations,
            self.water,
        )
        times = sorted({0.0, *(c.time for family in families for group in family for c in group)})
        return tuple(
            Change(
                time,
                *(
                    tuple(
                        group[bisect_right([c.time for c in group], time) - 1].availability
                        for group in family
                    )
                    for family in families
                ),
            )
            for time in times
        )


def energy_spec(spec):
    """Retain every finite-energy declaration, removing only water composition."""
    kind = (
        energy.SurfaceEnergyMorrisLecarModel
        if isinstance(spec.model, SurfaceEnergyWaterMorrisLecarModel)
        else energy.SurfaceEnergyModel
    )
    return replace(
        spec,
        model=kind(**{k: getattr(spec.model, k) for k in kind.__dataclass_fields__}),
        experiment=energy.Experiment(
            **{k: getattr(spec.experiment, k) for k in energy.Experiment.__dataclass_fields__}
        ),
    )


def water_spec(spec):
    """Water geometry/schema projection; live pool osmolytes are added at stages."""
    passive = kinetic.passive_spec(energy.initial_ionic_spec(energy_spec(spec)))
    return replace(
        passive,
        model=water.SurfaceWaterModel(
            **vars(passive.model),
            water_compartments=spec.model.water_compartments,
            water_membranes=spec.model.water_membranes,
        ),
        experiment=water.Experiment(**vars(passive.experiment), water=spec.experiment.water),
    )


def to_dict(spec):
    if (
        type(spec.model) not in (SurfaceEnergyWaterModel, SurfaceEnergyWaterMorrisLecarModel)
        or type(spec.experiment) is not Experiment
    ):
        raise ConfigError("Energy/water requires its own model and experiment")
    raw = energy.to_dict(energy_spec(spec))
    raw["model"].update(
        id=model_id(spec.model),
        energy_osmotic_coupling=spec.model.energy_osmotic_coupling,
        water_compartments=[asdict(v) for v in spec.model.water_compartments],
        water_membranes=[asdict(v) for v in spec.model.water_membranes],
    )
    raw["experiment"]["water_controls"] = [
        dict(membrane_id=patch.id, schedule=[asdict(c) for c in group])
        for patch, group in zip(spec.model.membranes, spec.experiment.water, strict=True)
    ]
    return raw


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    raw = deepcopy(data)
    if not isinstance(raw["model"], dict) or raw["model"].get("id") not in (
        MODEL_ID,
        MORRIS_LECAR_MODEL_ID,
    ):
        raise ConfigError("Require resolved_energy_water@1/@2")
    added = raw["model"]["id"] == MORRIS_LECAR_MODEL_ID
    try:
        coupling = raw["model"].pop("energy_osmotic_coupling")
        compartments = raw["model"].pop("water_compartments")
        membranes = raw["model"].pop("water_membranes")
        controls = raw["experiment"].pop("water_controls")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError(
            "Energy/water requires explicit osmotic coupling and water declarations"
        ) from error
    if coupling != OSMOTIC_COUPLING_ID:
        raise ConfigError("Require explicit neutral ideal ATP/ADP/Pi osmolyte coupling")
    raw["model"]["id"] = energy.MORRIS_LECAR_MODEL_ID if added else energy.MODEL_ID
    original = energy.parse(raw)
    passive = kinetic.passive_spec(energy.initial_ionic_spec(original)).to_dict()
    passive["model"].update(
        id=water.MODEL_ID,
        water_compartments=compartments,
        water_membranes=membranes,
    )
    passive["experiment"]["water_controls"] = controls
    validated = water.parse(passive)
    spec = replace(
        original,
        model=(SurfaceEnergyWaterMorrisLecarModel if added else SurfaceEnergyWaterModel)(
            **vars(original.model),
            energy_osmotic_coupling=coupling,
            water_compartments=validated.model.water_compartments,
            water_membranes=validated.model.water_membranes,
        ),
        experiment=Experiment(**vars(original.experiment), water=validated.experiment.water),
    )
    from cells.models import surface_energy_water

    try:
        surface_energy_water.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid finite-energy/water definition: " + str(error)) from error
    return spec
