"""Operator species_regulated_availability@1: coupling out of the inventory (D155 item 1, D156).

docs/INVENTORY_COUPLING_DESIGN.md (accepted 14 November 2026; rulings in §6.3, milestone-1 notes in
§7). A species amount on @3's cell rows sets @3's availability of a declared target through the
contract's CONTROL_FACTORS, either at once (an instantaneous Hill factor) or through a regulatory
state, a two-state fraction per cell with declared on- and off-rates. Version 1 targets @3's
junction and channel-population availabilities; the channel target was admitted when milestone 1's
probe P1 matched its path through control_view and held_schedules to the scheduled availability,
bit for bit (ruling 12; its acceptance into scope is the lead's).

Declaration (§1.6): `species`, the rows the operator reads (a read-only list: any species of the
world, ions included, with D150's identity form, never written; ruling 1); `states`, each with its
law hill_regulated_two_state@1, its cells, its inputs (Hill factors of species read in the same
cell, which multiply), on_rate_per_s, off_rate_per_s, initial (s0: one value for every cell of the
state, or an object naming each of its cells once, a cell's prior condition) and crossing_level
(null or a level in [0, 1]); `couplings`, each with a target ({operator: "inner", control, ids,
side}), a source ({"species": id} or {"state": id}), a law and basal. Every key is explicit. The
experiment's `regulatory_writes` set a (state, cell) at the start of the step leaving their time,
0 <= t < end: a write at 0 is applied at the first step start, before any later event.

Laws (§1.3, §1.5):
* instantaneous: hill_activation x^n/(K^n + x^n) or hill_inhibition K^n/(K^n + x^n) of the
  concentration c = n/V in the target's own cell, at the declared volume (processes/hill_factors,
  the expression of local_species_reactions@1); its source must be a neutral species with no
  membrane, junction or channel route, a row @3's step does not move, so the factor held through
  @3's step is exact there (§1.4);
* through a state: state_fraction s or state_complement 1 - s, with
  ds/dt = k_on u (1 - s) - k_off s, u the product of the state's input factors; each half-step is
  the exact solution with u frozen at the half-step's start (s' = s + (k_on u (1 - s) - k_off s) h
  phi(lambda h), lambda = k_on u + k_off, phi(x) = (1 - e^-x)/x), so s stays in [0, 1] in exact
  arithmetic and a value outside it is refused, never clipped. A source @3's step moves (an ion)
  enters only this way: the two halves read it before and after @3's step (Strang, §1.4);
* every coupling: F = b + (1 - b) f with 0 <= b < 1; a switched-off coupling gives exactly 1. A
  junction's side is first, second or both (the product of its two cells' factors; ruling 4). Each
  element takes the product of its routes in declared order; an untargeted element exactly 1.

Parts: an event map at each step start (a crossing record from the state at the step start with the
step counter, then due writes, then the switches copied from their schedule, then the counter), and
a split part (the states' exact half-steps), kept "split" under an RK4 inner step. The factors enter
through the composite's control view, evaluated once per step after the first half-steps and held
through @3's step (§1.1). Statically idle with no state and no coupling (the declaration alone).

Energy (§1.8): nothing is booked. Within a step a factor is a constant in [0, 1] times a scheduled
availability, the same object as a schedule; @3 books every gated flux at the effective value. The
states are kinetic, the integrals and crossings diagnostic: no ledger.

Refused at the definition (§1.11): an undeclared species; an instantaneous source that is charged
or has a route; an identity that differs from a D150 or D152 declaration; more than D150's species
cap; a target operator other than "inner"; a control outside the admitted targets; an unknown or
repeated element; a side on a channel or a junction side other than first, second or both; a law
that does not match its source kind; K <= 0, n <= 0, b outside [0, 1), negative rates, an initial
value or crossing level outside [0, 1], an initial object that does not name each of the state's
cells once; a state with no input; a state source not declared in a cell the coupling reads; a
target, state cell or junction endpoint on a slot replacement@1 replaces; dt (k_on + k_off) > 1
(ruling 5); a switch schedule that does not start at 0 or holds a value other than 0 and 1; a
later switch change off the dt grid or outside 0 < t < end; a write off the dt grid or outside
0 <= t < end, to an undeclared (state, cell), outside [0, 1], or twice at one time; and
(CONFLICTS_VIEW, D150's static-tissue list) every provider of volumes and closer of masks. At run
time a non-finite or out-of-range state or factor refuses the step (domain_valid, on every step's
end state; also rate_checks, wherever the composite evaluates readouts), as does a stale write
count (in the event map, as replacement's stale generation does).
"""

from dataclasses import dataclass

import numpy as np

from cells.core import species_registry
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _number
from cells.models.operators import species_common as common
from cells.models.operators.contract import Operator
from cells.numerics.species_sums import entity_sum
from cells.processes import hill_factors

LAW_ID = "species_regulated_availability@1"
STEP_ID = "exact_two_state_half_steps@1"
STATE_LAW = "hill_regulated_two_state@1"
# Admitted targets: @3's junction and channel-population availabilities (the channel after
# milestone 1's probe P1). The leak (membrane) and pump availabilities are later targets.
TARGET_CONTROLS = ("junction", "channel")
SIDES = ("first", "second", "both")
SPECIES_LAWS = hill_factors.KINDS  # hill_activation 1, hill_inhibition 2.
STATE_FRACTION, STATE_COMPLEMENT = 3, 4
STATE_FACTOR_LAWS = {"state_fraction": STATE_FRACTION, "state_complement": STATE_COMPLEMENT}
FROM_SPECIES, FROM_STATE = 1, 2
CONTROLS_KEY, WRITES_KEY = "coupling_controls", "regulatory_writes"

STATE_AXES = {
    "regulatory_state": ["regulatory_slot"],  # s in [0, 1], kinetic.
    "regulatory_input_integral": ["regulatory_slot"],  # U = integral of u dt, diagnostic.
    "regulatory_crossing_step": ["regulatory_slot"],  # int64: first step end with s >= level; -1.
    "regulatory_writes_applied": ["regulatory_slot"],  # int64: writes applied so far.
    "coupling_enabled": ["coupling"],  # 0 or 1, copied from the schedule at each step start.
    "coupling_step_count": ["one"],  # int64: steps started; time of a step start = count * dt.
}
INTEGER_FIELDS = ("regulatory_crossing_step", "regulatory_writes_applied", "coupling_step_count")
LAYOUT_FIELDS = (
    "regulatory_slot_cell",  # [slot] int64: the cell of each declared (state, cell) slot.
    "regulatory_on_rate",  # [slot] 1/s
    "regulatory_off_rate",  # [slot] 1/s
    "regulatory_has_level",  # [slot] bool
    "regulatory_level",  # [slot] (0 where none)
    "regulatory_input_row",  # [slot, input] int64 species row (0 on padding)
    "regulatory_input_kind",  # [slot, input] int64: 1 activation, 2 inhibition, 0 padding
    "regulatory_input_half_saturation_mM",  # [slot, input] (1 on padding)
    "regulatory_input_coefficient",  # [slot, input] (1 on padding)
    "coupling_route_law",  # [route] int64: 1, 2 (species), 3, 4 (state)
    "coupling_route_row",  # [route] int64 species row (0 for a state route)
    "coupling_route_cell",  # [route] int64 the cell the route reads
    "coupling_route_slot",  # [route] int64 state slot (0 for a species route)
    "coupling_route_half_saturation_mM",  # [route] (1 for a state route)
    "coupling_route_coefficient",  # [route] (1 for a state route)
    "coupling_route_basal",  # [route]
    "coupling_route_coupling",  # [route] int64 its coupling (for the switch)
    "coupling_junction_routes",  # [edge capacity, width] int64 route per element (-1 pads)
    "coupling_channel_routes",  # [channel capacity, width] int64 route per element (-1 pads)
)
TARGET_TABLES = {"junction": "coupling_junction_routes", "channel": "coupling_channel_routes"}


# ------------------------------------------------------------------ declaration


@dataclass(frozen=True)
class Input:
    law: str
    species: str
    half_saturation_mM: float
    hill_coefficient: float


@dataclass(frozen=True)
class RegulatoryState:
    id: str
    law: str
    cells: tuple
    inputs: tuple
    on_rate_per_s: float
    off_rate_per_s: float
    initial: tuple  # s0 per cell, aligned with cells.
    crossing_level: float | None


@dataclass(frozen=True)
class Target:
    operator: str
    control: str
    ids: tuple
    side: str | None


@dataclass(frozen=True)
class Coupling:
    id: str
    target: Target
    source_kind: str  # "species" or "state"
    source: str
    law: str
    half_saturation_mM: float | None
    hill_coefficient: float | None
    basal: float


@dataclass(frozen=True)
class Declaration:
    law: str
    species: tuple
    states: tuple
    couplings: tuple


@dataclass(frozen=True)
class Schedule:
    switches: tuple  # ((coupling id, ((time, enabled), ...)), ...) in declared coupling order
    writes: tuple  # (((state id, cell id), ((time, value), ...)), ...) in slot order


def _fraction(value, what, *, upper_open=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{LAW_ID}: {what} must be a finite number")
    result = float(value)
    if not np.isfinite(result) or result < 0 or result > 1 or (upper_open and result == 1):
        raise ConfigError(f"{LAW_ID}: {what} lies in [0, {'1)' if upper_open else '1]'}")
    return result


def _positive(value, what):
    return _number(value, f"{LAW_ID}: {what}", positive=True)


def _id_list(raw, what):
    if type(raw) is not list or not raw:
        raise ConfigError(f"{LAW_ID}: {what} is a non-empty explicit list")
    ids = tuple(identifier(v) for v in raw)
    if len(set(ids)) != len(ids):
        raise ConfigError(f"{LAW_ID}: {what} names an element twice")
    return ids


def _parse_initial(raw, name, where):
    """s0: one number for every cell of the state, or an object naming each of its cells once."""
    if isinstance(raw, dict):
        if set(raw) != set(where) or len(raw) != len(where):
            raise ConfigError(
                f"{LAW_ID}: state {name}'s initial object names each of its cells once"
            )
        return tuple(_fraction(raw[c], f"state {name}'s initial value in {c}") for c in where)
    value = _fraction(raw, f"state {name}'s initial value")
    return tuple(value for _ in where)


def _parse_states(raw, base, listed):
    if type(raw) is not list:
        raise ConfigError(f"{LAW_ID} declares its states in an explicit list")
    cells = [c.id for c in base.model.cells]
    states = []
    for entry in raw:
        _fields(
            entry,
            {
                "id",
                "law",
                "cells",
                "inputs",
                "on_rate_per_s",
                "off_rate_per_s",
                "initial",
                "crossing_level",
            },
            f"{LAW_ID} state",
        )
        name = identifier(entry["id"])
        if entry["law"] != STATE_LAW:
            raise ConfigError(f"{LAW_ID}: state {name} follows law {STATE_LAW}")
        where = (
            tuple(cells)
            if entry["cells"] == "all"
            else _id_list(entry["cells"], f"state {name}'s cells")
        )
        unknown = [c for c in where if c not in cells]
        if unknown:
            raise ConfigError(
                f"{LAW_ID}: state {name} is declared in an undeclared cell {unknown[0]!r}"
            )
        if type(entry["inputs"]) is not list or not entry["inputs"]:
            raise ConfigError(f"{LAW_ID}: state {name} reads at least one input")
        inputs = []
        for item in entry["inputs"]:
            _fields(
                item,
                {"law", "species", "half_saturation_mM", "hill_coefficient"},
                f"{LAW_ID} input",
            )
            if item["law"] not in SPECIES_LAWS:
                raise ConfigError(f"{LAW_ID}: an input's law is one of " + ", ".join(SPECIES_LAWS))
            if item["species"] not in listed:
                raise ConfigError(
                    f"{LAW_ID}: state {name} reads {item['species']!r}, not a listed species"
                )
            inputs.append(
                Input(
                    item["law"],
                    item["species"],
                    _positive(item["half_saturation_mM"], f"state {name}'s half_saturation_mM"),
                    _positive(item["hill_coefficient"], f"state {name}'s hill_coefficient"),
                )
            )
        level = entry["crossing_level"]
        states.append(
            RegulatoryState(
                name,
                STATE_LAW,
                where,
                tuple(inputs),
                _number(entry["on_rate_per_s"], f"{LAW_ID}: state {name}'s on_rate_per_s"),
                _number(entry["off_rate_per_s"], f"{LAW_ID}: state {name}'s off_rate_per_s"),
                _parse_initial(entry["initial"], name, where),
                None if level is None else _fraction(level, f"state {name}'s crossing level"),
            )
        )
    if len({s.id for s in states}) != len(states):
        raise ConfigError(f"{LAW_ID}: state IDs are unique")
    return tuple(states)


def _target_cells(model, target, element):
    """The cells a route of `target` on `element` reads, in order (a junction's side picks)."""
    if target.control == "channel":
        membranes = {p.id: p for p in model.membranes}
        channel = next(c for c in model.channels if c.id == element)
        return (membranes[channel.membrane_id].inside,)
    junction = next(j for j in model.junctions if j.id == element)
    return {
        "first": (junction.sender,),
        "second": (junction.receiver,),
        "both": (junction.sender, junction.receiver),
    }[target.side]


def _parse_couplings(raw, base, listed, states):
    if type(raw) is not list:
        raise ConfigError(f"{LAW_ID} declares its couplings in an explicit list")
    m = base.model
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    elements = dict(junction={j.id for j in m.junctions}, channel={c.id for c in m.channels})
    by_state = {s.id: s for s in states}
    couplings = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ConfigError(f"{LAW_ID}: a coupling is an object")
        law = entry.get("law")
        keys = {"id", "target", "source", "law", "basal"}
        if law in SPECIES_LAWS:
            keys |= {"half_saturation_mM", "hill_coefficient"}
        elif law not in STATE_FACTOR_LAWS:
            raise ConfigError(
                f"{LAW_ID}: a coupling's law is one of "
                + ", ".join((*SPECIES_LAWS, *STATE_FACTOR_LAWS))
            )
        _fields(entry, keys, f"{LAW_ID} coupling")
        name = identifier(entry["id"])
        t = _fields(entry["target"], {"operator", "control", "ids", "side"}, f"{LAW_ID} target")
        if t["operator"] != "inner":
            raise ConfigError(
                f"{LAW_ID}: coupling {name} targets {t['operator']!r}; version 1 targets the inner "
                "model's controls only (routes to other operators' controls are a later door, §2)"
            )
        if t["control"] not in TARGET_CONTROLS:
            raise ConfigError(
                f"{LAW_ID}: coupling {name} targets {t['control']!r}; admitted targets: "
                + ", ".join(TARGET_CONTROLS)
            )
        ids = _id_list(t["ids"], f"coupling {name}'s target ids")
        unknown = [i for i in ids if i not in elements[t["control"]]]
        if unknown:
            raise ConfigError(
                f"{LAW_ID}: coupling {name} names an unknown {t['control']} {unknown[0]!r}"
            )
        if t["control"] == "junction":
            if t["side"] not in SIDES:
                raise ConfigError(f"{LAW_ID}: a junction's side is one of " + ", ".join(SIDES))
        elif t["side"] is not None:
            raise ConfigError(f"{LAW_ID}: a {t['control']} target takes no side")
        target = Target("inner", t["control"], ids, t["side"])
        source = entry["source"]
        if (
            not isinstance(source, dict)
            or len(source) != 1
            or next(iter(source)) not in ("species", "state")
        ):
            raise ConfigError(
                f"{LAW_ID}: coupling {name}'s source is {{'species': id}} or {{'state': id}}"
            )
        kind, origin = next(iter(source.items()))
        if kind == "species":
            if law not in SPECIES_LAWS:
                raise ConfigError(f"{LAW_ID}: coupling {name} reads a species through a Hill law")
            if origin not in listed:
                raise ConfigError(
                    f"{LAW_ID}: coupling {name} reads {origin!r}, not a listed species"
                )
            if valence[origin] != 0:
                raise ConfigError(
                    f"{LAW_ID}: coupling {name} reads the charged species {origin!r} "
                    "instantaneously; "
                    "@3's step moves it, so a factor held through the step would lag (first order) "
                    "and could close a loop @3's bound does not see: read it through a state (§1.4)"
                )
            common.check_impermeant(m, origin, LAW_ID)
            k = _positive(entry["half_saturation_mM"], f"coupling {name}'s half_saturation_mM")
            n = _positive(entry["hill_coefficient"], f"coupling {name}'s hill_coefficient")
        else:
            if law not in STATE_FACTOR_LAWS:
                raise ConfigError(f"{LAW_ID}: coupling {name} reads a state through a state law")
            if origin not in by_state:
                raise ConfigError(f"{LAW_ID}: coupling {name} reads an undeclared state {origin!r}")
            k = n = None
            for element in ids:
                for cell in _target_cells(m, target, element):
                    if cell not in by_state[origin].cells:
                        raise ConfigError(
                            f"{LAW_ID}: coupling {name} reads state {origin} in {cell}, where it "
                            "is not declared"
                        )
        basal = _fraction(entry["basal"], f"coupling {name}'s basal level", upper_open=True)
        couplings.append(Coupling(name, target, kind, origin, law, k, n, basal))
    if len({c.id for c in couplings}) != len(couplings):
        raise ConfigError(f"{LAW_ID}: coupling IDs are unique")
    return tuple(couplings)


def parse_declaration(raw, base):
    _fields(raw, {"law", "species", "states", "couplings"}, "species-regulated availability")
    if raw["law"] != LAW_ID:
        raise ConfigError("Species-regulated availability requires law " + LAW_ID)
    species = common.parse_read_species(raw["species"], base, LAW_ID)
    listed = {s.id for s in species}
    states = _parse_states(raw["states"], base, listed)
    couplings = _parse_couplings(raw["couplings"], base, listed, states)
    return Declaration(LAW_ID, species, states, couplings)


def _initial_to_dict(state):
    if len(set(state.initial)) == 1:
        return state.initial[0]
    return dict(zip(state.cells, state.initial, strict=True))


def declaration_to_dict(declaration):
    if type(declaration) is not Declaration:
        raise ConfigError("Require explicit immutable species-regulated availability types")
    return dict(
        law=declaration.law,
        species=[
            dict(
                id=s.id,
                catalogue=None
                if s.catalogue is None
                else dict(catalogue=s.catalogue[0], entry=s.catalogue[1]),
                evidence=s.evidence,
            )
            for s in declaration.species
        ],
        states=[
            dict(
                id=s.id,
                law=s.law,
                cells=list(s.cells),
                inputs=[
                    dict(
                        law=i.law,
                        species=i.species,
                        half_saturation_mM=i.half_saturation_mM,
                        hill_coefficient=i.hill_coefficient,
                    )
                    for i in s.inputs
                ],
                on_rate_per_s=s.on_rate_per_s,
                off_rate_per_s=s.off_rate_per_s,
                initial=_initial_to_dict(s),
                crossing_level=s.crossing_level,
            )
            for s in declaration.states
        ],
        couplings=[
            dict(
                id=c.id,
                target=dict(
                    operator=c.target.operator,
                    control=c.target.control,
                    ids=list(c.target.ids),
                    side=c.target.side,
                ),
                source={c.source_kind: c.source},
                law=c.law,
                basal=c.basal,
                **(
                    dict(
                        half_saturation_mM=c.half_saturation_mM, hill_coefficient=c.hill_coefficient
                    )
                    if c.source_kind == "species"
                    else {}
                ),
            )
            for c in declaration.couplings
        ],
    )


def slots(declaration):
    """The (state id, cell id) slots, in declared order: states, then each state's cells."""
    return tuple((s.id, c) for s in declaration.states for c in s.cells)


def _event_time(value, what, base, *, at_zero=False):
    """A switch change after time 0 (0 < t < end, the composite's rule for event times, §1.11), or
    a write (0 <= t < end: a write at 0 is applied at the first step start and is not a schedule
    change time). An exact multiple of dt, refused here with its own message."""
    dt, end = base.execution.dt, base.experiment.end_time
    time = _number(value, f"{LAW_ID}: {what}")
    if time != round(time / dt) * dt:
        raise ConfigError(f"{LAW_ID}: {what} must be an exact multiple of dt (k * dt)")
    if not (0.0 <= time if at_zero else 0.0 < time) or not time < end:
        bound = "0 <= t < end" if at_zero else "0 < t < end"
        raise ConfigError(f"{LAW_ID}: {what} lies inside the horizon, {bound}")
    return time


def parse_schedule(raw, base, declaration):
    rows = raw[CONTROLS_KEY]
    if type(rows) is not list:
        raise ConfigError(f"{LAW_ID}: {CONTROLS_KEY} is an explicit list")
    switches = {}
    for row in rows:
        _fields(row, {"coupling_id", "schedule"}, f"{LAW_ID} coupling control")
        name = row["coupling_id"]
        if name not in {c.id for c in declaration.couplings} or name in switches:
            raise ConfigError(f"{LAW_ID}: one schedule per declared coupling ({name!r})")
        changes = row["schedule"]
        if type(changes) is not list or not changes:
            raise ConfigError(f"{LAW_ID}: coupling {name}'s schedule is a non-empty list")
        parsed = []
        for index, change in enumerate(changes):
            _fields(change, {"time", "enabled"}, f"{LAW_ID} switch change")
            if index == 0:
                time = _number(change["time"], f"{LAW_ID}: a switch time")
                if time != 0.0:
                    raise ConfigError(f"{LAW_ID}: coupling {name}'s schedule starts at 0")
            else:
                time = _event_time(change["time"], "a switch change", base)
            value = change["enabled"]
            if isinstance(value, bool) or value not in (0, 1):
                raise ConfigError(f"{LAW_ID}: a coupling is enabled (1) or not (0)")
            parsed.append((time, float(value)))
        times = [t for t, _ in parsed]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ConfigError(f"{LAW_ID}: coupling {name}'s schedule times increase strictly")
        switches[name] = tuple(parsed)
    if set(switches) != {c.id for c in declaration.couplings}:
        raise ConfigError(f"{LAW_ID}: every coupling has its schedule in {CONTROLS_KEY}")
    writes_raw = raw[WRITES_KEY]
    if type(writes_raw) is not list:
        raise ConfigError(f"{LAW_ID}: {WRITES_KEY} is an explicit list")
    known = slots(declaration)
    writes = {key: [] for key in known}
    for row in writes_raw:
        _fields(row, {"state_id", "cell_id", "time", "value"}, f"{LAW_ID} regulatory write")
        key = (row["state_id"], row["cell_id"])
        if key not in writes:
            raise ConfigError(f"{LAW_ID}: a write names an undeclared state and cell {key!r}")
        time = _event_time(row["time"], "a write", base, at_zero=True)
        writes[key].append((time, _fraction(row["value"], "a written value")))
    for key, entries in writes.items():
        times = [t for t, _ in entries]
        if len(set(times)) != len(times):
            raise ConfigError(f"{LAW_ID}: two writes to {key!r} at one time")
        writes[key] = tuple(sorted(entries))
    return Schedule(
        tuple((c.id, switches[c.id]) for c in declaration.couplings),
        tuple((key, writes[key]) for key in known),
    )


def schedule_to_dict(schedule):
    if type(schedule) is not Schedule:
        raise ConfigError("Require explicit immutable species-regulated availability schedules")
    return {
        CONTROLS_KEY: [
            dict(coupling_id=name, schedule=[dict(time=t, enabled=int(v)) for t, v in changes])
            for name, changes in schedule.switches
        ],
        WRITES_KEY: [
            dict(state_id=key[0], cell_id=key[1], time=t, value=v)
            for key, entries in schedule.writes
            for t, v in entries
        ],
    }


def _switch_at(changes, time):
    value = changes[0][1]
    for t, v in changes:
        if t <= time:
            value = v
    return value


def _writes_at(entries, time):
    """(count of writes at or before time, the latest written value or 0)."""
    done = [v for t, v in entries if t <= time]
    return len(done), (done[-1] if done else 0.0)


# ------------------------------------------------------------------ binding


def bind(spec, declaration, schedule):
    m, x = spec.model, spec.execution
    species = list(m.species_ids)
    cells = [c.id for c in m.cells]
    junctions = [j.id for j in m.junctions]
    channels = [c.id for c in m.channels]
    slot_keys = slots(declaration)
    by_state = {s.id: s for s in declaration.states}
    width = max((len(s.inputs) for s in declaration.states), default=0)
    k = len(slot_keys)
    layout = dict(
        regulatory_slot_cell=np.asarray([cells.index(c) for _, c in slot_keys], dtype=np.int64),
        regulatory_on_rate=np.asarray(
            [by_state[s].on_rate_per_s for s, _ in slot_keys], dtype=float
        ),
        regulatory_off_rate=np.asarray(
            [by_state[s].off_rate_per_s for s, _ in slot_keys], dtype=float
        ),
        regulatory_has_level=np.asarray(
            [by_state[s].crossing_level is not None for s, _ in slot_keys], dtype=bool
        ),
        regulatory_level=np.asarray(
            [by_state[s].crossing_level or 0.0 for s, _ in slot_keys], dtype=float
        ),
        regulatory_input_row=np.zeros((k, width), dtype=np.int64),
        regulatory_input_kind=np.zeros((k, width), dtype=np.int64),
        regulatory_input_half_saturation_mM=np.ones((k, width)),
        regulatory_input_coefficient=np.ones((k, width)),
    )
    for i, (state_id, _) in enumerate(slot_keys):
        for j, item in enumerate(by_state[state_id].inputs):
            layout["regulatory_input_row"][i, j] = species.index(item.species)
            layout["regulatory_input_kind"][i, j] = SPECIES_LAWS[item.law]
            layout["regulatory_input_half_saturation_mM"][i, j] = item.half_saturation_mM
            layout["regulatory_input_coefficient"][i, j] = item.hill_coefficient
    routes, on_element = [], {name: {} for name in TARGET_TABLES}
    for c_index, coupling in enumerate(declaration.couplings):
        law = (SPECIES_LAWS | STATE_FACTOR_LAWS)[coupling.law]
        for element in coupling.target.ids:
            for cell in _target_cells(m, coupling.target, element):
                from_state = coupling.source_kind == "state"
                route = dict(
                    law=law,
                    row=0 if from_state else species.index(coupling.source),
                    cell=cells.index(cell),
                    slot=slot_keys.index((coupling.source, cell)) if from_state else 0,
                    half=1.0 if from_state else coupling.half_saturation_mM,
                    coefficient=1.0 if from_state else coupling.hill_coefficient,
                    basal=coupling.basal,
                    coupling=c_index,
                )
                index = (junctions if coupling.target.control == "junction" else channels).index(
                    element
                )
                on_element[coupling.target.control].setdefault(index, []).append(len(routes))
                routes.append(route)
    layout.update(
        coupling_route_law=np.asarray([r["law"] for r in routes], dtype=np.int64),
        coupling_route_row=np.asarray([r["row"] for r in routes], dtype=np.int64),
        coupling_route_cell=np.asarray([r["cell"] for r in routes], dtype=np.int64),
        coupling_route_slot=np.asarray([r["slot"] for r in routes], dtype=np.int64),
        coupling_route_half_saturation_mM=np.asarray([r["half"] for r in routes], dtype=float),
        coupling_route_coefficient=np.asarray([r["coefficient"] for r in routes], dtype=float),
        coupling_route_basal=np.asarray([r["basal"] for r in routes], dtype=float),
        coupling_route_coupling=np.asarray([r["coupling"] for r in routes], dtype=np.int64),
    )
    for name, field in TARGET_TABLES.items():
        size = x.edge_capacity if name == "junction" else x.channel_capacity
        depth = max((len(v) for v in on_element[name].values()), default=0)
        table = -np.ones((size, depth), dtype=np.int64)
        for index, members in on_element[name].items():
            table[index, : len(members)] = members
        layout[field] = table
    switches = np.asarray([changes[0][1] for _, changes in schedule.switches], dtype=float)
    state = dict(
        regulatory_state=np.asarray(
            [by_state[s].initial[by_state[s].cells.index(c)] for s, c in slot_keys], dtype=float
        ),
        regulatory_input_integral=np.zeros(k),
        regulatory_crossing_step=-np.ones(k, dtype=np.int64),
        regulatory_writes_applied=np.zeros(k, dtype=np.int64),
        coupling_enabled=switches,
        coupling_step_count=np.zeros(1, dtype=np.int64),
    )
    return state, layout


# ------------------------------------------------------------------ the laws


def route_factors(state, p, *, xp):
    """[route] F = b + (1 - b) f, exactly 1 for a switched-off coupling (module docstring)."""
    law = p.coupling_route_law
    rows, cells = p.coupling_route_row, p.coupling_route_cell
    amount = p.amount_reference[rows, cells] + state.amount_increment[rows, cells]
    log_x = xp.log(amount) - xp.log(p.volume[cells])
    hill = hill_factors.factor(
        log_x, p.coupling_route_half_saturation_mM, p.coupling_route_coefficient, law, xp=xp
    )
    if p.regulatory_slot_cell.shape[0] > 0:  # Static: states declared.
        s = state.regulatory_state[p.coupling_route_slot]
        f = xp.where(law == STATE_FRACTION, s, xp.where(law == STATE_COMPLEMENT, 1.0 - s, hill))
    else:
        f = hill
    basal = p.coupling_route_basal
    value = basal + (1.0 - basal) * f
    on = state.coupling_enabled[p.coupling_route_coupling] > 0
    return xp.where(on, value, 1.0)


def element_product(values, table, *, xp):
    """[element] the product of each element's routes in declared order; exactly 1 elsewhere."""
    total = None
    for j in range(table.shape[1]):
        index = table[:, j]
        term = xp.where(index >= 0, values[xp.maximum(index, 0)], 1.0)
        total = term if total is None else total * term
    return total


def state_inputs(state, p, *, xp):
    """[slot] u, the product of each state's input factors at the current amounts."""
    rows = p.regulatory_input_row
    cells = p.regulatory_slot_cell[:, None]
    amount = p.amount_reference[rows, cells] + state.amount_increment[rows, cells]
    log_x = xp.log(amount) - xp.log(p.volume[p.regulatory_slot_cell])[:, None]
    log_f = hill_factors.log_factor(
        log_x,
        p.regulatory_input_half_saturation_mM,
        p.regulatory_input_coefficient,
        p.regulatory_input_kind,
        xp=xp,
    )
    return xp.exp(entity_sum(log_f, axis=1, xp=xp))


def state_half_step(state, h, p, *, xp):
    """(state after h of every regulatory state, valid); u frozen over h (module docstring)."""
    if p.regulatory_slot_cell.shape[0] == 0:  # Static: no state.
        return state, None
    u = state_inputs(state, p, xp=xp)
    k_on, k_off = p.regulatory_on_rate, p.regulatory_off_rate
    lam = k_on * u + k_off
    x = lam * h
    positive = x > 0
    phi = xp.where(positive, -xp.expm1(-x) / xp.where(positive, x, 1.0), 1.0)
    s = state.regulatory_state
    moved = s + (k_on * u * (1.0 - s) - k_off * s) * h * phi
    new_s = xp.where(lam > 0, moved, s)
    du = u * h
    total = state.regulatory_input_integral
    new_total = xp.where(du > 0, total + du, total)
    valid = xp.all(xp.isfinite(new_s) & (new_s >= 0) & (new_s <= 1))
    valid &= xp.all(xp.isfinite(new_total))
    return state._replace(regulatory_state=new_s, regulatory_input_integral=new_total), valid


def event_map(state, control, p, *, xp):
    """(state at the step start after crossings, writes, switches and the counter, consistent)."""
    count = state.coupling_step_count
    ok = None
    if p.regulatory_slot_cell.shape[0] > 0:  # Static: states declared.
        s = state.regulatory_state
        crossed = (
            p.regulatory_has_level
            & (state.regulatory_crossing_step < 0)
            & (s >= p.regulatory_level)
        )
        applied = state.regulatory_writes_applied
        target = control.regulatory_write_count
        due = target == applied + 1
        ok = xp.all((target == applied) | due)  # A stale schedule refuses the step.
        state = state._replace(
            regulatory_crossing_step=xp.where(crossed, count[0], state.regulatory_crossing_step),
            regulatory_state=xp.where(due, control.regulatory_write_value, s),
            regulatory_writes_applied=xp.where(due, applied + 1, applied),
        )
    state = state._replace(coupling_enabled=control.coupling_switch, coupling_step_count=count + 1)
    return state, ok


def factors_valid(state, p, *, xp):
    """Every route's factor finite and in [0, 1] (none declared: valid)."""
    if p.coupling_route_law.shape[0] == 0:  # Static: no route.
        return True
    f = route_factors(state, p, xp=xp)
    return xp.all(xp.isfinite(f) & (f >= 0) & (f <= 1))


def own_valid(state, *, xp):
    s, total = state.regulatory_state, state.regulatory_input_integral
    valid = xp.all(xp.isfinite(s) & (s >= 0) & (s <= 1))
    valid &= xp.all(xp.isfinite(total) & (total >= 0))
    valid &= xp.all(state.regulatory_crossing_step >= -1)
    valid &= xp.all(state.regulatory_writes_applied >= 0)
    enabled = state.coupling_enabled
    valid &= xp.all((enabled == 0) | (enabled == 1))
    valid &= xp.all(state.coupling_step_count >= 0)
    return valid


# ------------------------------------------------------------------ definition checks


def check_identities(spec, declaration):
    """Refuse a species declared with another identity than its one authority (the species
    registry: D150's and D152's operators come first, as authors; D176)."""
    common.check_identities(spec, LAW_ID, declaration.species)


def check_unmoved_sources(declaration, moved):
    """Refuse an instantaneous coupling whose source row something moves inside the inner step
    (moved: species_registry.moved_in_step). The parse-time refusals (a charged source; a route
    through a membrane, junction or channel) stay; this one adds every other in-step mover, such
    as a pump's fuel rows under F2 or an in-step process (D176, "moved by the step")."""
    for coupling in declaration.couplings:
        if coupling.source_kind != "species":
            continue
        movers = moved.get(coupling.source, {}).get("cell", ())
        if movers:
            raise ConfigError(
                f"{LAW_ID}: coupling {coupling.id} reads {coupling.source!r} instantaneously, but "
                f"{movers[0]} moves it inside the inner step, so a factor held through the step "
                "would lag (first order): read it through a state (§1.4)"
            )


def check_replaced_slots(spec, declaration):
    """Refuse a target, state cell or junction endpoint on a slot replacement@1 replaces."""
    _, events = common.replacement_of(spec)
    replaced = {v.slot for v in events}
    if not replaced:
        return
    m = spec.model
    for state in declaration.states:
        hit = replaced & set(state.cells)
        if hit:
            raise ConfigError(
                f"{LAW_ID}: state {state.id} is declared in {sorted(hit)[0]}, a slot "
                f"{common.REPLACEMENT_LAW} replaces (version 1.1's reset rule; refused in "
                "version 1)"
            )
    for coupling in declaration.couplings:
        for element in coupling.target.ids:
            if coupling.target.control == "junction":
                junction = next(j for j in m.junctions if j.id == element)
                cells = {junction.sender, junction.receiver}
            else:
                cells = set(_target_cells(m, coupling.target, element))
            hit = replaced & cells
            if hit:
                raise ConfigError(
                    f"{LAW_ID}: coupling {coupling.id} targets {element}, on "
                    f"{sorted(hit)[0]}, a slot "
                    f"{common.REPLACEMENT_LAW} replaces (refused in version 1)"
                )


def check_rate_limit(spec, declaration):
    dt = spec.execution.dt
    for state in declaration.states:
        if dt * (state.on_rate_per_s + state.off_rate_per_s) > 1:
            raise ConfigError(
                f"{LAW_ID}: state {state.id} has dt (k_on + k_off) = "
                f"{dt * (state.on_rate_per_s + state.off_rate_per_s):.3g} > 1: a state that "
                "relaxes "
                "within one step makes @3's held value an endpoint value (ruling 5)"
            )


# ------------------------------------------------------------------ the operator


class SpeciesRegulatedAvailability(Operator):
    LAW_ID = LAW_ID
    IDENTITY_ROLE = "user"  # Species registry (D176): it reads species others declare.
    STEP_ID = STEP_ID
    EVENT = True
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    STATE_DTYPES = {k: np.int64 for k in INTEGER_FIELDS}
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("coupling_switch", "regulatory_write_count", "regulatory_write_value")
    EXPERIMENT_KEYS = (CONTROLS_KEY, WRITES_KEY)
    CONTROL_FACTORS = TARGET_CONTROLS
    CONFLICTS_VIEW = common.CONFLICTS_VIEW
    READOUT_COLUMNS = ("coupling_factor",)

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_declaration(raw, base)

    def to_dict(self, declaration, base):
        return declaration_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_schedule(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return schedule_to_dict(schedule)

    def schedule_times(self, schedule):
        times = {t for _, changes in schedule.switches for t, _ in changes if t > 0}
        times |= {t for _, entries in schedule.writes for t, _ in entries if t > 0}
        return tuple(sorted(times))

    def value_at(self, schedule, time):
        return (
            tuple(_switch_at(changes, time) for _, changes in schedule.switches),
            tuple(_writes_at(entries, time) for _, entries in schedule.writes),
        )

    def control_values(self, spec, declaration, schedule, records, indices, times):
        count = len(records)
        switch = np.zeros((count, len(schedule.switches)))
        written = np.zeros((count, len(schedule.writes)), dtype=np.int64)
        value = np.zeros((count, len(schedule.writes)))
        for i, (switches, writes) in enumerate(records):
            switch[i] = switches
            for j, (number, last) in enumerate(writes):
                written[i, j], value[i, j] = number, last
        return switch[indices], written[indices], value[indices]

    def species_identities(self, declaration):
        return declaration.species

    def check_definition(self, spec, declaration, schedule, model):
        common.check_species_cap(spec, LAW_ID)
        check_identities(spec, declaration)
        check_unmoved_sources(declaration, species_registry.moved_in_step(spec))
        check_replaced_slots(spec, declaration)
        check_rate_limit(spec, declaration)

    def batch_signature(self, declaration):
        """The static structure; identities and every parameter are not part of it."""
        return (
            LAW_ID,
            tuple(s.id for s in declaration.species),
            tuple(
                (s.id, s.cells, tuple((i.law, i.species) for i in s.inputs))
                for s in declaration.states
            ),
            tuple(
                (
                    c.target.operator,
                    c.target.control,
                    c.target.ids,
                    c.target.side,
                    c.source_kind,
                    c.source,
                    c.law,
                )
                for c in declaration.couplings
            ),
        )

    def working_size(self, spec):
        x = spec.execution
        return 8 * 16 * (x.capacity + x.edge_capacity + x.channel_capacity)

    def summary(self, spec, declaration, schedule, history):
        unrecorded = []
        if hasattr(history, "regulatory_state") and len(np.asarray(history.regulatory_state)):
            final = np.asarray(history.regulatory_state)[-1]
            record = np.asarray(history.regulatory_crossing_step)[-1]
            levels = {s.id: s.crossing_level for s in declaration.states}
            for k, (state_id, cell) in enumerate(slots(declaration)):
                level = levels[state_id]
                if level is not None and record[k] < 0 and final[k] >= level:
                    unrecorded.append([state_id, cell])
        return {
            "coupling_law": LAW_ID,
            "coupling_step": STEP_ID,
            "coupling_mechanism": "regulation of availability (a factor in [b, 1] on the schedule)",
            "coupling_species": {
                s.id: dict(
                    catalogue=None if s.catalogue is None else list(s.catalogue),
                    evidence=s.evidence,
                )
                for s in declaration.species
            },
            "coupling_states": {
                s.id: dict(
                    law=s.law,
                    cells=list(s.cells),
                    inputs=[
                        (i.law, i.species, i.half_saturation_mM, i.hill_coefficient)
                        for i in s.inputs
                    ],
                    on_rate_per_s=s.on_rate_per_s,
                    off_rate_per_s=s.off_rate_per_s,
                    initial=dict(zip(s.cells, s.initial, strict=True)),
                    crossing_level=s.crossing_level,
                )
                for s in declaration.states
            },
            "coupling_targets": {
                c.id: dict(
                    control=c.target.control,
                    ids=list(c.target.ids),
                    side=c.target.side,
                    source={c.source_kind: c.source},
                    law=c.law,
                    half_saturation_mM=c.half_saturation_mM,
                    hill_coefficient=c.hill_coefficient,
                    basal=c.basal,
                )
                for c in declaration.couplings
            },
            # A crossing in the final step has no later step start to record it (§1.5).
            "coupling_unrecorded_final_crossings": unrecorded,
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration, schedule)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.regulatory_slot_cell.shape[0] == 0 and p.coupling_route_law.shape[0] == 0

    def control_factors(self, state, p, *, xp):
        factors, values = {}, None
        for name in self.CONTROL_FACTORS:
            table = getattr(p, TARGET_TABLES[name])
            if table.shape[1] == 0:  # Static: no route on this control.
                continue
            values = route_factors(state, p, xp=xp) if values is None else values
            factors[name] = element_product(values, table, xp=xp)
        return factors

    def event(self, state, control, p, *, xp):
        return event_map(state, control, p, xp=xp)

    def half_step(self, state, h, control, p, *, xp):
        return state_half_step(state, h, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        switch = control.coupling_switch
        valid = xp.all((switch == 0) | (switch == 1))
        value = control.regulatory_write_value
        valid &= xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))
        valid &= xp.all(control.regulatory_write_count >= 0)
        return valid

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, xp=xp) & factors_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, xp=xp) & factors_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        if p.coupling_route_law.shape[0]:
            columns["coupling_factor"] = np.asarray(route_factors(state, p, xp=np))
        else:
            columns["coupling_factor"] = np.zeros(0)
        return columns
