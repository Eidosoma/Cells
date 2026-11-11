"""resolved_pump_water@2: resolved_pump_water@1 plus KCC-type K+/anion symport routes.

Every field of resolved_pump_water@1 keeps its meaning and is parsed by that
identity's own parser. The model adds ``symport``:

* ``law``: processes/k_anion_symport.LAW_ID (mass action, electroneutral 1:1);
* ``volume_factor``: processes/k_anion_symport.VOLUME_FACTOR_ID;
* ``roles``: the ``potassium`` and ``anion`` species (valences +1 and -1);
* ``routes``: one row per membrane that carries a route, with its capacity
  (fmol/(s mM^2)), set volume (pL) and steepness.

The experiment adds ``symport_controls``: one availability schedule per route
(a block such as VU0463271 is availability 0). With no route the identity is
resolved_pump_water@1 (models/surface_pump_water_v2.py).
"""

import copy
from bisect import bisect_right
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core import surface_pump_spec as first
from cells.core import surface_pump_water_spec as water
from cells.core.bioelectric_spec import positive
from cells.core.multispecies_spec import identifier
from cells.core.specs import ChannelChange, ConfigError, _fields, _number
from cells.processes.k_anion_symport import LAW_ID, VOLUME_FACTOR_ID

MODEL_ID = "resolved_pump_water@2"
ROUTE_FIELDS = ("membrane_id", "capacity_fmol_s_mM2", "set_volume_pL", "steepness")


@dataclass(frozen=True)
class SymportRoute:
    membrane_id: str
    capacity_fmol_s_mM2: float
    set_volume_pL: float
    steepness: float


@dataclass(frozen=True)
class Symport:
    law: str
    volume_factor: str
    potassium: str
    anion: str
    routes: tuple[SymportRoute, ...]


@dataclass(frozen=True)
class SurfacePumpRegulatedWaterModel:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    cells: tuple
    extracellular: tuple
    membranes: tuple
    junctions: tuple
    faces: tuple
    gauge_reference: str | None
    channels: tuple
    water: water.Water
    symport: Symport
    junction_heat_booking: str = water.ionic.DEFAULT_JUNCTION_HEAT


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    calcium_pump: object
    water: object
    symport: object  # [..., membrane_capacity]; membranes without a route stay zero.


@dataclass(frozen=True)
class Change(water.Change):
    symport: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(water.Experiment):
    """resolved_pump_water@1's experiment plus one symport schedule per route."""

    symport: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        groups = (
            self.membranes,
            self.junctions,
            self.channels,
            self.pumps,
            self.calcium_pumps,
            self.water,
            self.symport,
        )
        times = sorted({0.0, *(c.time for family in groups for g in family for c in g)})
        return tuple(
            Change(
                time,
                *(
                    tuple(
                        g[bisect_right([p.time for p in g], time) - 1].availability for g in family
                    )
                    for family in groups
                ),
            )
            for time in times
        )


def projection(spec):
    """The resolved_pump_water@1 part of a definition (no symport routes)."""
    m, e = spec.model, spec.experiment
    model = water.SurfacePumpWaterModel(
        **{k: getattr(m, k) for k in water.SurfacePumpWaterModel.__dataclass_fields__}
    )
    experiment = water.Experiment(
        **{k: getattr(e, k) for k in water.Experiment.__dataclass_fields__}
    )
    return replace(spec, model=model, experiment=experiment)


def to_dict(spec):
    m, e = spec.model, spec.experiment
    if type(m) is not SurfacePumpRegulatedWaterModel or type(e) is not Experiment:
        raise ConfigError("Resolved pump water @2 requires its own model and experiment")
    y = m.symport
    if type(y) is not Symport or any(type(r) is not SymportRoute for r in y.routes):
        raise ConfigError("Require explicit immutable symport declaration types")
    raw = water.to_dict(projection(spec))
    raw["model"]["id"] = MODEL_ID
    raw["model"]["symport"] = dict(
        law=y.law,
        volume_factor=y.volume_factor,
        roles=dict(potassium=y.potassium, anion=y.anion),
        routes=[asdict(r) for r in y.routes],
    )
    raw["experiment"]["symport_controls"] = [
        dict(membrane_id=r.membrane_id, schedule=[asdict(c) for c in g])
        for r, g in zip(y.routes, e.symport, strict=True)
    ]
    return raw


def parse_symport(raw, base):
    _fields(raw, {"law", "volume_factor", "roles", "routes"}, "symport")
    if raw["law"] != LAW_ID or raw["volume_factor"] != VOLUME_FACTOR_ID:
        raise ConfigError(f"Symport requires law {LAW_ID} and volume factor {VOLUME_FACTOR_ID}")
    roles = _fields(raw["roles"], {"potassium", "anion"}, "symport roles")
    m = base.model
    for role, valence in (("potassium", 1), ("anion", -1)):
        sid = identifier(roles[role])
        if sid not in m.species_ids or m.valence[m.species_ids.index(sid)] != valence:
            raise ConfigError(
                f"Symport {role} role requires a declared species of valence {valence}"
            )
    if roles["potassium"] == roles["anion"]:
        raise ConfigError("Symport roles must name two species")
    if type(raw["routes"]) is not list:
        raise ConfigError("Symport routes require an explicit list")
    membranes = [p.id for p in m.membranes]
    routes, seen = [], set()
    for row in raw["routes"]:
        _fields(row, set(ROUTE_FIELDS), "symport route")
        mid = identifier(row["membrane_id"])
        if mid not in membranes or mid in seen:
            raise ConfigError("Each symport route names one distinct declared membrane")
        seen.add(mid)
        routes.append(
            SymportRoute(
                mid,
                _number(row["capacity_fmol_s_mM2"], "symport capacity"),
                positive(row["set_volume_pL"], "symport set volume"),
                positive(row["steepness"], "symport steepness"),
            )
        )
    routes.sort(key=lambda r: membranes.index(r.membrane_id))
    return Symport(LAW_ID, VOLUME_FACTOR_ID, roles["potassium"], roles["anion"], tuple(routes))


def parse(data):
    raw = copy.deepcopy(data)
    m, e = raw.get("model"), raw.get("experiment")
    if not isinstance(m, dict) or not isinstance(e, dict) or m.get("id") != MODEL_ID:
        raise ConfigError("Require resolved_pump_water@2")
    if "symport" not in m or "symport_controls" not in e:
        raise ConfigError("Declare symport and symport_controls")
    symport, controls = m.pop("symport"), e.pop("symport_controls")
    m["id"] = water.MODEL_ID
    base = water.parse(raw)
    declared = parse_symport(symport, base)
    ids = [r.membrane_id for r in declared.routes]
    schedules = first._schedules(controls, "membrane", ids, base.experiment.end_time)
    model = SurfacePumpRegulatedWaterModel(
        **{k: getattr(base.model, k) for k in water.SurfacePumpWaterModel.__dataclass_fields__},
        symport=declared,
    )
    experiment = Experiment(
        **{k: getattr(base.experiment, k) for k in water.Experiment.__dataclass_fields__},
        symport=tuple(schedules[i] for i in ids),
    )
    spec = replace(base, model=model, experiment=experiment)
    from cells.models.surface_pump_water_v2 import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved pump water @2 definition: " + str(error)) from error
    return spec


def control_values(spec, times):
    """resolved_pump_water@1 controls plus the symport availabilities (padded to membranes)."""
    base = water.control_values(projection(spec), times)
    changes = spec.experiment.changes
    indices = np.searchsorted([c.time for c in changes], times, side="right") - 1
    padded = np.zeros((len(times), spec.execution.membrane_capacity))
    if spec.model.symport.routes:
        values = np.asarray([c.symport for c in changes], dtype=np.float64)[indices]
        mids = [p.id for p in spec.model.membranes]
        for k, route in enumerate(spec.model.symport.routes):
            padded[:, mids.index(route.membrane_id)] = values[:, k]
    return Control(*base, padded)
