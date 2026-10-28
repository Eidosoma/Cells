"""Strict named electroneutral cotransport on fixed-volume finite-energy tissue."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core import surface_energy_spec as prior
from cells.core.multispecies_spec import identifier
from cells.core.specs import ChannelChange, ConfigError, _fields, _integer, _number
from cells.core.voltage_gated_spec import fraction
from cells.processes import cotransport

MODEL_ID = "resolved_cotransport@1"


@dataclass(frozen=True)
class CotransportRoles:
    potassium: str
    chloride: str
    sodium: str | None = None


@dataclass(frozen=True)
class Cotransporter:
    id: str
    membrane_id: str
    law: str
    roles: CotransportRoles
    capacity_fmol_per_s: float


@dataclass(frozen=True)
class SurfaceCotransportModel(prior.SurfaceEnergyModel):
    cotransporters: tuple[Cotransporter, ...]


@dataclass(frozen=True)
class Execution(prior.Execution):
    cotransport_capacity: int = 0


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    regeneration: object
    cotransport: object


@dataclass(frozen=True)
class Change(prior.Change):
    cotransport: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    cotransports: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        families = (
            self.membranes,
            self.junctions,
            self.channels,
            self.pumps,
            self.regenerations,
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


def energy_spec(spec):
    return replace(
        spec,
        model=prior._project(spec.model, prior.SurfaceEnergyModel),
        experiment=prior._project(spec.experiment, prior.Experiment),
        execution=prior._project(spec.execution, prior.Execution),
    )


def initial_ionic_spec(spec):
    return prior.initial_ionic_spec(energy_spec(spec))


def route_stoichiometry(route, model):
    roles = {route.roles.potassium: "K", route.roles.chloride: "Cl"}
    if route.roles.sodium is not None:
        roles[route.roles.sodium] = "Na"
    ids = tuple(roles.get(s, "unused_" + str(i)) for i, s in enumerate(model.species_ids))
    return cotransport.named_stoichiometry(ids, np.array(model.valence), route.law)


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCotransportModel
        or type(spec.experiment) is not Experiment
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Resolved cotransport requires its own model/experiment/execution types")
    raw = prior.to_dict(energy_spec(spec))
    rows = []
    for route in spec.model.cotransporters:
        row = asdict(route)
        row["roles"] = {k: v for k, v in row["roles"].items() if v is not None}
        rows.append(row)
    raw["model"].update(id=MODEL_ID, cotransporters=rows)
    raw["experiment"]["cotransport_controls"] = [
        dict(cotransport_id=route.id, schedule=[asdict(v) for v in group])
        for route, group in zip(
            spec.model.cotransporters, spec.experiment.cotransports, strict=True
        )
    ]
    raw["execution"]["cotransport_capacity"] = spec.execution.cotransport_capacity
    return raw


def _routes(rows, model):
    if type(rows) is not list:
        raise ConfigError("Require an explicit ordered cotransporter list")
    names = {
        v.id
        for family in (
            model.cells,
            model.extracellular,
            model.membranes,
            model.junctions,
            model.faces,
            model.channels,
            model.energy_pools,
            model.regeneration_ports,
        )
        for v in family
    }
    names.update(p.pump.id for p in model.membranes if p.pump is not None)
    patches = {p.id for p in model.membranes}
    result = []
    for row in rows:
        _fields(row, set(Cotransporter.__dataclass_fields__), "cotransporter")
        name, patch = identifier(row["id"]), identifier(row["membrane_id"])
        law = row["law"]
        keys = {"potassium", "chloride"}
        if law == cotransport.NKCC_LAW_ID:
            keys.add("sodium")
        elif law != cotransport.KCC_LAW_ID:
            raise ConfigError("Cotransport requires a named manufactured reversible law")
        roles = _fields(row["roles"], keys, "cotransport roles")
        refs = {k: identifier(v) for k, v in roles.items()}
        if name in names or patch not in patches or len(set(refs.values())) != len(refs):
            raise ConfigError("Cotransport requires unique route/role IDs and a declared membrane")
        route = Cotransporter(
            name,
            patch,
            law,
            CotransportRoles(**refs),
            _number(row["capacity_fmol_per_s"], "cotransport cycle capacity"),
        )
        if any(v not in model.species_ids for v in refs.values()):
            raise ConfigError("Cotransport roles must name declared species")
        try:
            route_stoichiometry(route, model)
        except ValueError as error:
            raise ConfigError("Invalid actual cotransport role valence: " + str(error)) from error
        result.append(route)
        names.add(name)
    return tuple(result)


def _controls(rows, routes, end):
    if type(rows) is not list:
        raise ConfigError("Require explicit cotransport controls")
    result = {}
    for row in rows:
        _fields(row, {"cotransport_id", "schedule"}, "cotransport control")
        name, group = identifier(row["cotransport_id"]), row["schedule"]
        if name in result or type(group) is not list or not group:
            raise ConfigError("Each cotransporter needs one nonempty schedule")
        for change in group:
            _fields(change, {"time", "availability"}, "cotransport change")
        changes = tuple(
            ChannelChange(
                _number(v["time"], "cotransport time"),
                fraction(v["availability"], "cotransport availability"),
            )
            for v in group
        )
        if (
            changes[0].time != 0
            or any(v.time > end for v in changes)
            or any(b.time <= a.time for a, b in zip(changes, changes[1:], strict=False))
        ):
            raise ConfigError("Cotransport controls start at zero and increase within horizon")
        result[name] = changes
    if set(result) != {r.id for r in routes}:
        raise ConfigError("Cotransport control IDs must exactly match routes")
    return tuple(result[r.id] for r in routes)


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    raw = deepcopy(data)
    if type(raw["model"]) is not dict or raw["model"].get("id") != MODEL_ID:
        raise ConfigError("Require resolved_cotransport@1")
    try:
        rows = raw["model"].pop("cotransporters")
        schedules = raw["experiment"].pop("cotransport_controls")
        capacity = raw["execution"].pop("cotransport_capacity")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError("Require explicit cotransport routes, controls and capacity") from error
    raw["model"]["id"] = prior.MODEL_ID
    original = prior.parse(raw)
    routes = _routes(rows, original.model)
    spec = replace(
        original,
        model=SurfaceCotransportModel(**vars(original.model), cotransporters=routes),
        experiment=Experiment(
            **vars(original.experiment),
            cotransports=_controls(schedules, routes, original.experiment.end_time),
        ),
        execution=Execution(
            **vars(original.execution),
            cotransport_capacity=_integer(capacity, "cotransport capacity", minimum=len(routes)),
        ),
    )
    from cells.models import surface_cotransport

    try:
        surface_cotransport.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid resolved cotransport definition: " + str(error)) from error
    return spec
