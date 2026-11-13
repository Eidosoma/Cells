"""Operator cytoplasmic_bridge_closure@1: the cytoplasmic bridge between two daughters closes (S5).

docs/CELL_DIVISION_S5_DESIGN.md §4; the law is docs/CELL_DIVISION_DESIGN.md §4.2. The name is
general: a cleaving egg's bridge is one use (D144).

The bridge is an @3 junction between the two daughters of one division of
isopotential_partition@1. Its constant-field junction law has P_s A_j = 2 a_0 D_s^cyt, with
D_s^cyt the cytoplasmic diffusivities: area 2 a_0 x 1 m and permeability D_s^cyt / (1 m). For equal
concentrations its conductance is 2 a sigma_cyt, the access conductance of an aperture in a thin
wall. Its gate is fixed open (minimum open fraction 1, initial gate 1). It opens with both
daughters at their birth, by closure propagation (§2), and retires with either of them; while
closed its slot is @3 padding (gate 0), and the partition writes its declared gate at birth.

This operator owns the aperture a (state, a_0 until the closure starts). Its view is a factor
a / a_0 on the junction's availability (CONTROL_FACTORS: a product with any other factor), so the
junction carries 2 a(t) D_s^cyt and @3 books its transport and heat. The split part advances a by
exact half-steps from the closure's start, under a declared law:
* linear: a decreases at a_0 / tau until 0;
* exponential: a falls by exp(-h / tau) per half-step.
The start is a schedule (`bridge_controls`), checked equal to the daughters' division time.
A half-step with no closing bridge selects its start state, and a statically absent bridge set is
idle, so neither adds a computed value.

Refused: a bridge junction that is not a contact between one division's two daughters; a gate that
is not fixed open; P_s A_j != 2 a_0 D_s^cyt (relative 1e-12); a start other than its division's
time; a daughter that divides again before its bridge has closed (a linear closure ends at
start + tau; an exponential one never ends, so its daughters may not divide again). The domain:
0 <= a <= a_0, and a = a_0 until the start. a_0 is bounded by the step through @3's
explicit-rate step check, which counts the bridge's declared conductance (§4.2).

The aperture is not a conserved quantity, so the operator has no ledger of its own: the junction's
transport and heat are @3's. sigma_cyt enters only through the declared P_s A_j, that is through
G_b0 = 2 a_0 sigma_cyt (§4.2).
"""

from dataclasses import dataclass

import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _number
from cells.models.operators import partition
from cells.models.operators.contract import Operator

LAW_ID = "cytoplasmic_bridge_closure@1"
STEP_ID = "exact_aperture_half_steps@1"
LAWS = ("linear", "exponential")
PERMEABILITY_RTOL = 1e-12

STATE_AXES = {"bridge_aperture_m": ["edge_slot"]}
LAYOUT_FIELDS = (
    "bridge_junction",  # [bridge] int64: the static set (shape 0: statically idle).
    "bridge_present",  # [edge] bool
    "bridge_initial_aperture_m",  # [edge] (0 elsewhere)
    "bridge_closure_time_s",  # [edge] (1 elsewhere)
    "bridge_linear",  # [edge] bool
)


@dataclass(frozen=True)
class Bridge:
    junction_id: str
    initial_aperture_m: float
    closure: str
    closure_time_s: float
    cytoplasmic_diffusivity: tuple  # ((species, m^2/s), ...)


@dataclass(frozen=True)
class Bridges:
    law: str
    bridges: tuple


@dataclass(frozen=True)
class BridgeStart:
    junction_id: str
    time: float


# ------------------------------------------------------------------ definition


def parse_bridges(raw, base):
    _fields(raw, {"law", "bridges"}, "bridge closure")
    if raw["law"] != LAW_ID:
        raise ConfigError("A bridge closure requires law " + LAW_ID)
    if type(raw["bridges"]) is not list:
        raise ConfigError("A bridge closure lists its bridges")
    m = base.model
    junctions = {j.id: j for j in m.junctions}
    species = list(m.species_ids)
    bridges = []
    for entry in raw["bridges"]:
        _fields(
            entry,
            {
                "junction_id",
                "initial_aperture_m",
                "closure",
                "closure_time_s",
                "cytoplasmic_diffusivity_m2_per_s",
            },
            "bridge",
        )
        junction = junctions.get(identifier(entry["junction_id"]))
        if junction is None:
            raise ConfigError(f"A bridge names an unknown junction {entry['junction_id']!r}")
        a0 = _number(entry["initial_aperture_m"], "initial aperture", positive=True)
        tau = _number(entry["closure_time_s"], "closure time", positive=True)
        if entry["closure"] not in LAWS:
            raise ConfigError("A bridge closes by one of " + ", ".join(LAWS))
        diffusivity = entry["cytoplasmic_diffusivity_m2_per_s"]
        if type(diffusivity) is not dict or set(diffusivity) - set(species):
            raise ConfigError("Cytoplasmic diffusivities are an object over the model's species")
        d = {s: _number(diffusivity.get(s, 0.0), "cytoplasmic diffusivity") for s in species}
        if any(v < 0 for v in d.values()):
            raise ConfigError("Cytoplasmic diffusivities are nonnegative")
        if junction.minimum_open_fraction != 1.0 or junction.initial_gate != 1.0:
            raise ConfigError(f"A bridge's gate is fixed open, not {junction.id}'s")
        for s, p in zip(species, junction.permeability_m_per_s, strict=True):
            expected = 2.0 * a0 * d[s]
            if abs(p * junction.area_m2 - expected) > PERMEABILITY_RTOL * max(
                abs(expected), 1e-300
            ):
                raise ConfigError(
                    f"Bridge {junction.id}: P A for {s} must be 2 a_0 D^cyt ({expected!r} m^3/s)"
                )
        bridges.append(Bridge(junction.id, a0, entry["closure"], tau, tuple(d.items())))
    if len({b.junction_id for b in bridges}) != len(bridges):
        raise ConfigError("One entry per bridge")
    return Bridges(LAW_ID, tuple(bridges))


def bridges_to_dict(declaration):
    if type(declaration) is not Bridges or any(type(b) is not Bridge for b in declaration.bridges):
        raise ConfigError("Require explicit immutable bridge declaration types")
    return dict(
        law=declaration.law,
        bridges=[
            dict(
                junction_id=b.junction_id,
                initial_aperture_m=b.initial_aperture_m,
                closure=b.closure,
                closure_time_s=b.closure_time_s,
                cytoplasmic_diffusivity_m2_per_s=dict(b.cytoplasmic_diffusivity),
            )
            for b in declaration.bridges
        ],
    )


def parse_starts(raw, base, declaration):
    rows = raw["bridge_controls"]
    if type(rows) is not list:
        raise ConfigError("Bridge controls are an explicit list")
    known = {b.junction_id for b in declaration.bridges}
    starts = []
    for row in rows:
        _fields(row, {"junction_id", "start_time"}, "bridge control")
        if row["junction_id"] not in known:
            raise ConfigError(f"A bridge control names an undeclared bridge {row['junction_id']!r}")
        starts.append(BridgeStart(row["junction_id"], _number(row["start_time"], "start time")))
    if len({s.junction_id for s in starts}) != len(starts):
        raise ConfigError("A bridge starts closing at most once")
    return tuple(sorted(starts, key=lambda s: (s.time, s.junction_id)))


def starts_to_dict(schedule):
    if any(type(s) is not BridgeStart for s in schedule):
        raise ConfigError("Require explicit immutable bridge control types")
    return dict(
        bridge_controls=[dict(junction_id=s.junction_id, start_time=s.time) for s in schedule]
    )


def check_definition(spec, declaration, schedule, model):
    """Each bridge joins one division's two daughters, starts closing at that division's time and
    has closed before either daughter divides again (module docstring)."""
    found = [(d, s) for op, d, s in composite_spec.entries(spec) if op.LAW_ID == partition.LAW_ID]
    if not found:
        raise ConfigError("A bridge closure requires " + partition.LAW_ID)
    divisions, events = found[0]
    when = {e.division: e.time for e in events}
    junctions = {j.id: j for j in spec.model.junctions}
    start = {s.junction_id: s.time for s in schedule}
    dt = spec.execution.dt
    for b in declaration.bridges:
        ends = {junctions[b.junction_id].sender, junctions[b.junction_id].receiver}
        division = next((d for d in divisions.divisions if set(d.daughters) == ends), None)
        if division is None:
            raise ConfigError(f"Bridge {b.junction_id} does not join one division's daughters")
        if start.get(b.junction_id) != when.get(division.id):
            raise ConfigError(
                f"Bridge {b.junction_id} starts closing at its division's time "
                f"({when.get(division.id)!r}), not {start.get(b.junction_id)!r}"
            )
        if b.junction_id in start and start[b.junction_id] != round(start[b.junction_id] / dt) * dt:
            raise ConfigError("A bridge's start is an exact multiple of dt")
        for later in divisions.divisions:
            if later.parent in ends and later.id in when:
                closed = (
                    b.closure == "linear"
                    and b.junction_id in start
                    and start[b.junction_id] + b.closure_time_s <= when[later.id]
                )
                if not closed:
                    raise ConfigError(
                        f"Bridge {b.junction_id} must have closed before {later.parent} divides "
                        "(an exponential closure never ends)"
                    )


def bind(spec, declaration):
    junctions = [j.id for j in spec.model.junctions]
    ne = spec.execution.edge_capacity
    layout = dict(
        bridge_junction=np.asarray(
            [junctions.index(b.junction_id) for b in declaration.bridges], dtype=np.int64
        ),
        bridge_present=np.zeros(ne, dtype=bool),
        bridge_initial_aperture_m=np.zeros(ne),
        bridge_closure_time_s=np.ones(ne),
        bridge_linear=np.zeros(ne, dtype=bool),
    )
    for b in declaration.bridges:
        e = junctions.index(b.junction_id)
        layout["bridge_present"][e] = True
        layout["bridge_initial_aperture_m"][e] = b.initial_aperture_m
        layout["bridge_closure_time_s"][e] = b.closure_time_s
        layout["bridge_linear"][e] = b.closure == "linear"
    state = {"bridge_aperture_m": np.array(layout["bridge_initial_aperture_m"], copy=True)}
    return state, layout


# ------------------------------------------------------------------ the law


def closed(state, h, control, p, *, xp):
    """(state after h of closure, valid) (module docstring)."""
    a = state.bridge_aperture_m
    present = p.bridge_present
    closing = present & (control.bridge_closing > 0)
    tau = xp.where(present, p.bridge_closure_time_s, 1.0)
    linear = xp.maximum(a - (p.bridge_initial_aperture_m / tau) * h, 0.0)
    exponential = a * xp.exp(-h / tau)
    new = xp.where(closing, xp.where(p.bridge_linear, linear, exponential), a)
    flowing = xp.any(closing)  # No closing bridge: select the start state (bitwise idle).
    return state._replace(bridge_aperture_m=xp.where(flowing, new, a)), None


def availability(state, p, *, xp):
    """[edge] a / a_0 on bridges, exactly 1 elsewhere."""
    a0 = xp.where(p.bridge_present, p.bridge_initial_aperture_m, 1.0)
    return xp.where(p.bridge_present, state.bridge_aperture_m / a0, 1.0)


def own_valid(state, p, *, xp):
    a, a0 = state.bridge_aperture_m, p.bridge_initial_aperture_m
    valid = xp.all(xp.isfinite(a))
    valid &= xp.all(xp.where(p.bridge_present, (a >= 0) & (a <= a0), a == 0))
    return valid


class CytoplasmicBridgeClosure(Operator):
    LAW_ID = LAW_ID
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("bridge_closing",)
    EXPERIMENT_KEYS = ("bridge_controls",)
    CONTROL_FACTORS = ("junction",)
    REQUIRES = (partition.LAW_ID,)

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_bridges(raw, base)

    def to_dict(self, declaration, base):
        return bridges_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_starts(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return starts_to_dict(schedule)

    def schedule_times(self, schedule):
        return tuple(s.time for s in schedule)

    def value_at(self, schedule, time):
        return tuple(sorted((s.junction_id, float(s.time <= time)) for s in schedule))

    def control_values(self, spec, declaration, schedule, records, indices, times):
        junctions = [j.id for j in spec.model.junctions]
        closing = np.zeros((len(records), spec.execution.edge_capacity))
        for i, record in enumerate(records):
            for junction, value in record:
                closing[i, junctions.index(junction)] = value
        return (closing[indices],)

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration, schedule, model)

    def batch_signature(self, declaration):
        return (LAW_ID, tuple((b.junction_id, b.closure) for b in declaration.bridges))

    def working_size(self, spec):
        return 8 * 4 * spec.execution.edge_capacity

    def summary(self, spec, declaration, schedule, history):
        return {
            "bridge_law": LAW_ID,
            "bridge_step": STEP_ID,
            "bridges": {
                b.junction_id: dict(
                    initial_aperture_m=b.initial_aperture_m,
                    closure=b.closure,
                    closure_time_s=b.closure_time_s,
                    initial_conductance_scale_m3_per_s=dict(
                        (s, 2.0 * b.initial_aperture_m * v) for s, v in b.cytoplasmic_diffusivity
                    ),
                )
                for b in declaration.bridges
            },
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.bridge_junction.shape[0] == 0

    def control_factors(self, state, p, *, xp):
        return dict(junction=availability(state, p, xp=xp))

    def half_step(self, state, h, control, p, *, xp):
        return closed(state, h, control, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        closing = control.bridge_closing
        return xp.all((closing == 0) | (closing == 1))

    def rate_checks(self, state, control, p, valid, *, xp):
        waiting = p.bridge_present & (control.bridge_closing == 0)  # a_0 until its start.
        unchanged = xp.all(
            xp.where(waiting, state.bridge_aperture_m == p.bridge_initial_aperture_m, True)
        )
        return valid & own_valid(state, p, xp=xp) & unchanged

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own
