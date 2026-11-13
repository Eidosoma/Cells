"""resolved_pump_tissue@2: resolved_pump_tissue@1 plus a plasma-membrane Ca-ATPase.

Every field of resolved_pump_tissue@1 keeps its meaning and is parsed by that
identity's parser. Each membrane additionally declares ``calcium_pump``: null,
or one ca_atp_mass_action_positive@1 pump (processes/calcium_atpase.py) with
its own maintained ATP/ADP/Pi pools (1 M standard state, as for the Na/K pump),
a +2 role species and exactly -1 of it per cycle. Each declared calcium pump
has its own availability schedule in ``calcium_pump_controls``. Species are
free as in @1 (for example Na, K, Cl, Ca and fixed anions). With no calcium
pump the identity reproduces resolved_pump_tissue@1.
"""

import copy
from bisect import bisect_right
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core import surface_kinetic_spec as kinetic
from cells.core import surface_pump_spec as first
from cells.core.bioelectric_spec import positive, signed_number
from cells.core.kinetic_finite_spec import METABOLISM_ID
from cells.core.multispecies_spec import identifier
from cells.core.specs import ChannelChange, ConfigError, MaintainedMetabolismSpec, _fields, _number
from cells.processes import calcium_atpase

MODEL_ID = "resolved_pump_tissue@2"
CALCIUM_PUMP_FIELDS = (
    "id",
    "law",
    "roles",
    "stoichiometry",
    "capacity_fmol_per_s",
    "km_ca_mM",
    "km_atp_mM",
    "metabolism",
)


@dataclass(frozen=True)
class CalciumPumpSpec:
    id: str
    law: str
    role: str
    capacity_fmol_per_s: float
    km_ca_mM: float
    km_atp_mM: float
    metabolism: MaintainedMetabolismSpec


@dataclass(frozen=True)
class Membrane(kinetic.Membrane):
    calcium_pump: CalciumPumpSpec | None


@dataclass(frozen=True)
class SurfacePumpModel:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    cells: tuple
    extracellular: tuple
    membranes: tuple[Membrane, ...]
    junctions: tuple[kinetic.Junction, ...]
    faces: tuple
    gauge_reference: str | None
    channels: tuple = ()  # Always empty; the shared kinetic rates read it.


@dataclass(frozen=True)
class Change(kinetic.Change):
    calcium_pump: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(kinetic.Experiment):
    calcium_pumps: tuple[tuple[ChannelChange, ...], ...]  # All membrane slots.

    @property
    def changes(self):
        """The held availabilities at every change time, built once per experiment.

        The schedules are immutable, so the rows are kept on the instance (outside
        the dataclass fields) after the first access. Rebuilding them from every
        schedule took about 10 ms per access at 825 nodes and 2802 channel
        populations, and execution reads them in every window (the held controls,
        each control table and each window's event index).
        """
        found = self.__dict__.get("_changes")
        if found is None:
            found = self._held_availabilities()
            self.__dict__["_changes"] = found  # As functools.cached_property stores.
        return found

    def _held_availabilities(self):
        groups = (self.membranes, self.junctions, self.channels, self.pumps, self.calcium_pumps)
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


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    calcium_pump: object  # [..., membrane_capacity]; absent pumps stay zero.


def parse_calcium_pump(raw, ids, z):
    if raw is None:
        return None
    _fields(raw, set(CALCIUM_PUMP_FIELDS), "calcium pump")
    role = identifier(_fields(raw["roles"], {"calcium"}, "calcium pump roles")["calcium"])
    if raw["law"] != calcium_atpase.LAW_ID or role not in ids or z[ids.index(role)] != 2:
        raise ConfigError("Calcium pump requires its named law and a +2 calcium role")
    nu = _fields(raw["stoichiometry"], {role}, "calcium pump stoichiometry")
    if type(nu[role]) is not int or nu[role] != calcium_atpase.CALCIUM_PER_CYCLE:
        raise ConfigError("Calcium pump requires exactly -1 calcium per cycle")
    pools = _fields(
        raw["metabolism"], set(MaintainedMetabolismSpec.__dataclass_fields__), "metabolism"
    )
    if pools["kind"] != METABOLISM_ID:
        raise ConfigError("Require explicit maintained chemical reservoirs")
    return CalciumPumpSpec(
        identifier(raw["id"]),
        calcium_atpase.LAW_ID,
        role,
        _number(raw["capacity_fmol_per_s"], "calcium pump capacity"),
        positive(raw["km_ca_mM"], "km_ca_mM"),
        positive(raw["km_atp_mM"], "km_atp_mM"),
        MaintainedMetabolismSpec(
            METABOLISM_ID,
            *(positive(pools[k], k) for k in ("atp_mM", "adp_mM", "pi_mM")),
            signed_number(pools["delta_g0_J_per_mol"], "standard hydrolysis free energy"),
        ),
    )


def calcium_pump_to_dict(p):
    if p is None:
        return None
    if type(p) is not CalciumPumpSpec or type(p.metabolism) is not MaintainedMetabolismSpec:
        raise ConfigError("Require explicit immutable calcium pump and metabolism types")
    return {
        "id": p.id,
        "law": p.law,
        "roles": {"calcium": p.role},
        "stoichiometry": {p.role: calcium_atpase.CALCIUM_PER_CYCLE},
        "capacity_fmol_per_s": p.capacity_fmol_per_s,
        "km_ca_mM": p.km_ca_mM,
        "km_atp_mM": p.km_atp_mM,
        "metabolism": asdict(p.metabolism),
    }


def projection(spec):
    """The resolved_pump_tissue@1 part of a definition (no calcium pumps)."""
    m, e = spec.model, spec.experiment
    membranes = tuple(
        kinetic.Membrane(**{k: getattr(p, k) for k in kinetic.Membrane.__dataclass_fields__})
        for p in m.membranes
    )
    model = first.SurfacePumpModel(
        **{
            k: getattr(m, k)
            for k in first.SurfacePumpModel.__dataclass_fields__
            if k != "membranes"
        },
        membranes=membranes,
    )
    experiment = kinetic.Experiment(
        **{k: getattr(e, k) for k in kinetic.Experiment.__dataclass_fields__}
    )
    return replace(spec, model=model, experiment=experiment)


def to_dict(spec):
    m, e = spec.model, spec.experiment
    if type(m) is not SurfacePumpModel or type(e) is not Experiment:
        raise ConfigError("Resolved pump tissue @2 requires its own model and experiment")
    if any(type(p) is not Membrane for p in m.membranes):
        raise ConfigError("Resolved pump tissue @2 requires its own membrane type")
    raw = first.to_dict(projection(spec))
    raw["model"]["id"] = MODEL_ID
    for target, p in zip(raw["model"]["membranes"], m.membranes, strict=True):
        target["calcium_pump"] = calcium_pump_to_dict(p.calcium_pump)
    raw["experiment"]["calcium_pump_controls"] = [
        dict(pump_id=p.calcium_pump.id, schedule=[asdict(c) for c in g])
        for p, g in zip(m.membranes, e.calcium_pumps, strict=True)
        if p.calcium_pump is not None
    ]
    return raw


def parse(data):
    raw = copy.deepcopy(data)
    m, e = raw.get("model"), raw.get("experiment")
    if not isinstance(m, dict) or not isinstance(e, dict) or m.get("id") != MODEL_ID:
        raise ConfigError("Require resolved_pump_tissue@2")
    if type(m.get("membranes")) is not list or any(type(p) is not dict for p in m["membranes"]):
        raise ConfigError("membranes requires an explicit list")
    if any("calcium_pump" not in p for p in m["membranes"]) or "calcium_pump_controls" not in e:
        raise ConfigError("Each membrane declares calcium_pump; the experiment its controls")
    declared = [p.pop("calcium_pump") for p in m["membranes"]]
    controls = e.pop("calcium_pump_controls")
    m["id"] = first.MODEL_ID
    base = first.parse(raw)
    ids, z = base.model.species_ids, base.model.valence
    pumps = [parse_calcium_pump(p, ids, z) for p in declared]
    membranes = tuple(
        Membrane(
            **{k: getattr(p, k) for k in kinetic.Membrane.__dataclass_fields__}, calcium_pump=c
        )
        for p, c in zip(base.model.membranes, pumps, strict=True)
    )
    model = base.model
    names = [
        p.id
        for p in (
            *model.cells,
            *model.extracellular,
            *model.membranes,
            *model.junctions,
            *model.faces,
            *(p.pump for p in model.membranes if p.pump is not None),
            *(c for c in pumps if c is not None),
        )
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Owner, route and pump IDs must be globally unique")
    schedules = first._schedules(
        controls, "pump", [c.id for c in pumps if c is not None], base.experiment.end_time
    )
    model = SurfacePumpModel(
        **{k: getattr(model, k) for k in SurfacePumpModel.__dataclass_fields__ if k != "membranes"},
        membranes=membranes,
    )
    experiment = Experiment(
        **{k: getattr(base.experiment, k) for k in kinetic.Experiment.__dataclass_fields__},
        calcium_pumps=tuple(
            (ChannelChange(0.0, 0.0),) if c is None else schedules[c.id] for c in pumps
        ),
    )
    spec = replace(base, model=model, experiment=experiment)
    from cells.models.surface_pump_v2 import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved pump @2 definition: " + str(error)) from error
    return spec


def control_values(spec, times):
    """resolved_pump_tissue@1 controls plus the calcium pump availabilities."""
    from cells.core.schedule import control_values as first_values

    base = first_values(projection(spec), times)
    changes = spec.experiment.changes
    indices = np.searchsorted([c.time for c in changes], times, side="right") - 1
    values = np.asarray([c.calcium_pump for c in changes], dtype=np.float64)
    padded = np.zeros((len(times), spec.execution.membrane_capacity))
    padded[:, : values.shape[-1]] = values[indices]
    return Control(*base, padded)
