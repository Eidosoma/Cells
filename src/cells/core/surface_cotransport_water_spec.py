"""Explicit cotransport, finite pools and compliant water on one shared clock."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_cotransport_spec as cotransport
from cells.core import surface_energy_spec as energy
from cells.core import surface_energy_water_spec as water
from cells.core.specs import ConfigError, _fields

MODEL_ID = "resolved_cotransport_water@1"


@dataclass(frozen=True)
class SurfaceCotransportWaterModel(water.SurfaceEnergyWaterModel):
    cotransporters: tuple[cotransport.Cotransporter, ...]


Control = NamedTuple(
    "CotransportWaterControl", [(k, object) for k in (*water.Control._fields, "cotransport")]
)


@dataclass(frozen=True)
class Change(water.Change):
    cotransport: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(water.Experiment):
    cotransports: tuple

    @property
    def changes(self):
        families = (
            self.membranes,
            self.junctions,
            self.channels,
            self.pumps,
            self.regenerations,
            self.water,
            self.cotransports,
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


def water_spec(spec):
    return replace(
        spec,
        model=energy._project(spec.model, water.SurfaceEnergyWaterModel),
        experiment=energy._project(spec.experiment, water.Experiment),
        execution=energy._project(spec.execution, energy.Execution),
    )


def cotransport_spec(spec):
    return replace(
        spec,
        model=energy._project(spec.model, cotransport.SurfaceCotransportModel),
        experiment=energy._project(spec.experiment, cotransport.Experiment),
        execution=energy._project(spec.execution, cotransport.Execution),
    )


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCotransportWaterModel
        or type(spec.experiment) is not Experiment
    ):
        raise ConfigError("Cotransport/water requires its own model and experiment")
    raw = cotransport.to_dict(cotransport_spec(spec))
    raw["model"].update(
        id=MODEL_ID,
        energy_osmotic_coupling=spec.model.energy_osmotic_coupling,
        water_compartments=[asdict(v) for v in spec.model.water_compartments],
        water_membranes=[asdict(v) for v in spec.model.water_membranes],
    )
    raw["experiment"]["water_controls"] = [
        dict(membrane_id=p.id, schedule=[asdict(c) for c in group])
        for p, group in zip(spec.model.membranes, spec.experiment.water, strict=True)
    ]
    return raw


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    raw = deepcopy(data)
    if type(raw["model"]) is not dict or raw["model"].get("id") != MODEL_ID:
        raise ConfigError("Require resolved_cotransport_water@1")
    try:
        coupling = raw["model"].pop("energy_osmotic_coupling")
        compartments = raw["model"].pop("water_compartments")
        membranes = raw["model"].pop("water_membranes")
        controls = raw["experiment"].pop("water_controls")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError("Require explicit neutral pool and water declarations") from error
    raw["model"]["id"] = cotransport.MODEL_ID
    original = cotransport.parse(raw)
    projected = cotransport.energy_spec(original).to_dict()
    projected["model"].update(
        id=water.MODEL_ID,
        energy_osmotic_coupling=coupling,
        water_compartments=compartments,
        water_membranes=membranes,
    )
    projected["experiment"]["water_controls"] = controls
    validated = water.parse(projected)
    spec = replace(
        original,
        model=SurfaceCotransportWaterModel(
            **vars(validated.model), cotransporters=original.model.cotransporters
        ),
        experiment=Experiment(
            **vars(validated.experiment), cotransports=original.experiment.cotransports
        ),
    )
    from cells.models import surface_cotransport_water

    try:
        surface_cotransport_water.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid cotransport/water composition: " + str(error)) from error
    return spec
