"""resolved_pump_replacement@1: scheduled cell replacement on resolved_pump_tissue@3.

Every field of the inner model (``replacement.inner_model``, here only
resolved_pump_tissue@3) keeps its meaning and is parsed by that identity's own
parser. The model adds ``replacement``:

* ``law``: the event operator, OPERATION_LAW_ID;
* ``inner_model``: the inner identity;
* ``junction_formation``: the law processes/junction_formation.LAW_ID with all
  four parameters declared: ``initial_abundance`` (A0 in [0, 1]), ``lag_s``,
  ``time_constant_s`` (at least MIN_TIME_CONSTANT_S) and ``gate_at_arrival``
  (GATE_RULES: the junction law's gate at Vj = 0, or its steady state at the
  post-event Vj);
* ``templates``: declared newcomer states, each the newcomer's isolated steady
  state computed by the experiment's driver. A template gives the amounts of every
  declared species (fmol) for one cell volume and fixed charge background, the
  gates of each gated channel law, and optional per-role route values (intensive:
  channel permeability (m/s) and abundance per channel law, membrane permeability
  per species (m/s), Na/K and Ca pump capacity per membrane area
  (fmol/(s m^2))). A newcomer's own parameter draw is its own template; the
  engine draws nothing;
* ``template_capacity``: template rows, so vectorized cohorts share shapes.

The experiment adds ``replacement_events``: each a time, a slot (cell ID), a
template ID and a new carrier ID. Event times are exact multiples of dt
(k * dt as a float product) inside the horizon, at most one per slot and time.
They join the schedule union (experiment.changes) as light records: the time,
the inner change record active then (shared, not copied) and the events at that
time. The per-slot replacement counters are derived from the event table by
control_values, never tabulated per record.

A template replaces only routes the slot already has, by a positive value:
the inner model's domain refuses transfers on a zero-coefficient route. Its
volume and fixed charge background must equal the slot's, so its declared
amounts fix the newcomer's charge and so its membrane voltage. Design and
sources: /mnt/workspaces/Cells/cell-replacement-g2-20261111-01/design-note-G2.md.
"""

import copy
import math
from bisect import bisect_right
from dataclasses import MISSING, dataclass, field, fields, make_dataclass, replace
from functools import cached_property
from typing import NamedTuple

import numpy as np

from cells.core import surface_pump_v3_spec as ionic
from cells.core.bioelectric_spec import positive, signed_number
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _integer, _number
from cells.core.voltage_gated_spec import fraction
from cells.processes.junction_formation import LAW_ID as FORMATION_LAW_ID

MODEL_ID = "resolved_pump_replacement@1"
OPERATION_LAW_ID = "scheduled_cell_replacement@1"
INNER_MODEL_IDS = (ionic.MODEL_ID,)
GATE_RULES = ("law_open", "law_steady")
# Newly formed channels take the junction's current gate state; that is exact
# only when formation is slow against gating. The junction law relaxes in at
# most about 0.4 s (rate >= 2.5/s), so formation must be 100 times slower.
MIN_TIME_CONSTANT_S = 40.0
ROUTE_KEYS = (
    "channel_permeability_m_per_s",
    "channel_abundance",
    "membrane_permeability_m_per_s",
    "pump_capacity_fmol_per_s_m2",
    "calcium_pump_capacity_fmol_per_s_m2",
)
TEMPLATE_FIELDS = (
    "id",
    "volume_pL",
    "fixed_charge_equivalent_fmol",
    "amounts_fmol",
    "channel_gates",
    "route_values",
)


@dataclass(frozen=True)
class JunctionFormation:
    law: str
    initial_abundance: float
    lag_s: float
    time_constant_s: float
    gate_at_arrival: str


@dataclass(frozen=True)
class Template:
    id: str
    volume_pL: float
    fixed_charge_equivalent_fmol: float
    amounts_fmol: tuple[float, ...]  # Species order.
    channel_gates: tuple[tuple[str, tuple[float, ...]], ...]  # (law, gates), law order.
    channel_permeability_m_per_s: tuple[tuple[str, float], ...]  # (law, value)
    channel_abundance: tuple[tuple[str, float], ...]  # (law, value)
    membrane_permeability_m_per_s: tuple[tuple[str, float], ...]  # (species, value)
    pump_capacity_fmol_per_s_m2: float | None
    calcium_pump_capacity_fmol_per_s_m2: float | None


@dataclass(frozen=True)
class Replacement:
    law: str
    inner_model: str
    junction_formation: JunctionFormation
    templates: tuple[Template, ...]
    template_capacity: int


@dataclass(frozen=True)
class ReplacementEvent:
    time: float
    slot: str
    template: str
    carrier_id: str


@dataclass(frozen=True)
class ReplacementChange:
    """One schedule time: the active inner record (shared) and the events at that time."""

    time: float
    inner: object
    events: tuple[ReplacementEvent, ...]


def _model_fields():
    inner = fields(ionic.SurfacePumpChannelModel)
    required = [
        (f.name, f.type) for f in inner if f.default is MISSING and f.default_factory is MISSING
    ]
    optional = [
        (f.name, f.type, field(default=f.default)) for f in inner if f.default is not MISSING
    ]
    return [*required, ("replacement", Replacement), *optional]


# The inner model's fields (whatever @3 declares) plus the replacement declaration.
CellReplacementModel = make_dataclass(
    "CellReplacementModel", _model_fields(), frozen=True, module=__name__
)


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    calcium_pump: object
    generation: object  # [..., capacity] int64: the slot's events at or before t.
    template: object  # [..., capacity] int64: 1 + template row of that latest event; 0 none.


@dataclass(frozen=True)
class Experiment(ionic.Experiment):
    """The inner experiment plus the replacement events, sorted by (time, slot order)."""

    replacement_events: tuple[ReplacementEvent, ...]

    @cached_property
    def changes(self):
        inner = ionic.Experiment.changes.fget(self)
        inner_times = [c.time for c in inner]
        at = {}
        for event in self.replacement_events:
            at.setdefault(event.time, []).append(event)
        times = sorted({*inner_times, *at})
        return tuple(
            ReplacementChange(t, inner[bisect_right(inner_times, t) - 1], tuple(at.get(t, ())))
            for t in times
        )


def projection(spec):
    """The inner (resolved_pump_tissue@3) definition: no replacement declarations."""
    m, e = spec.model, spec.experiment
    model = ionic.SurfacePumpChannelModel(
        **{k: getattr(m, k) for k in ionic.SurfacePumpChannelModel.__dataclass_fields__}
    )
    experiment = ionic.Experiment(
        **{k: getattr(e, k) for k in ionic.Experiment.__dataclass_fields__}
    )
    return replace(spec, model=model, experiment=experiment)


def template_to_dict(t, species):
    return dict(
        id=t.id,
        volume_pL=t.volume_pL,
        fixed_charge_equivalent_fmol=t.fixed_charge_equivalent_fmol,
        amounts_fmol=dict(zip(species, t.amounts_fmol, strict=True)),
        channel_gates={law: list(g) for law, g in t.channel_gates},
        route_values=dict(
            channel_permeability_m_per_s=dict(t.channel_permeability_m_per_s),
            channel_abundance=dict(t.channel_abundance),
            membrane_permeability_m_per_s=dict(t.membrane_permeability_m_per_s),
            pump_capacity_fmol_per_s_m2=t.pump_capacity_fmol_per_s_m2,
            calcium_pump_capacity_fmol_per_s_m2=t.calcium_pump_capacity_fmol_per_s_m2,
        ),
    )


def to_dict(spec):
    m, e = spec.model, spec.experiment
    if type(m) is not CellReplacementModel or type(e) is not Experiment:
        raise ConfigError("Cell replacement requires its own model and experiment")
    r = m.replacement
    if (
        type(r) is not Replacement
        or type(r.junction_formation) is not JunctionFormation
        or any(type(t) is not Template for t in r.templates)
        or any(type(v) is not ReplacementEvent for v in e.replacement_events)
    ):
        raise ConfigError("Require explicit immutable replacement declaration types")
    raw = ionic.to_dict(projection(spec))
    raw["model"]["id"] = MODEL_ID
    f = r.junction_formation
    raw["model"]["replacement"] = dict(
        law=r.law,
        inner_model=r.inner_model,
        junction_formation=dict(
            law=f.law,
            initial_abundance=f.initial_abundance,
            lag_s=f.lag_s,
            time_constant_s=f.time_constant_s,
            gate_at_arrival=f.gate_at_arrival,
        ),
        templates=[template_to_dict(t, m.species_ids) for t in r.templates],
        template_capacity=r.template_capacity,
    )
    raw["experiment"]["replacement_events"] = [
        dict(time=v.time, slot=v.slot, template=v.template, carrier_id=v.carrier_id)
        for v in e.replacement_events
    ]
    return raw


def _keyed(raw, keys, name, convert):
    if not isinstance(raw, dict) or any(k not in keys for k in raw):
        raise ConfigError(f"{name} keys must be among {sorted(keys)}")
    return tuple((k, convert(raw[k], f"{name} {k}")) for k in sorted(raw, key=list(keys).index))


def parse_formation(raw):
    _fields(
        raw,
        {"law", "initial_abundance", "lag_s", "time_constant_s", "gate_at_arrival"},
        "junction formation",
    )
    if raw["law"] != FORMATION_LAW_ID:
        raise ConfigError("Junction formation requires law " + FORMATION_LAW_ID)
    if raw["gate_at_arrival"] not in GATE_RULES:
        raise ConfigError("gate_at_arrival must be one of " + ", ".join(GATE_RULES))
    tau = positive(raw["time_constant_s"], "formation time constant")
    if tau < MIN_TIME_CONSTANT_S:
        raise ConfigError(
            f"Formation time constant must be at least {MIN_TIME_CONSTANT_S} s "
            "(100 x the junction gate's slowest relaxation)"
        )
    return JunctionFormation(
        FORMATION_LAW_ID,
        fraction(raw["initial_abundance"], "initial junction abundance"),
        _number(raw["lag_s"], "formation lag"),
        tau,
        raw["gate_at_arrival"],
    )


def parse_template(raw, base):
    _fields(raw, set(TEMPLATE_FIELDS), "template")
    m = base.model
    species = tuple(m.species_ids)
    amounts = raw["amounts_fmol"]
    if not isinstance(amounts, dict) or set(amounts) != set(species):
        raise ConfigError("Template amounts must name every declared species exactly once")
    gates = raw["channel_gates"]
    if not isinstance(gates, dict):
        raise ConfigError("Template channel_gates must be an object keyed by channel law")
    laws = tuple(ionic.LAW_CODES)
    parsed_gates = []
    for law in sorted(gates, key=lambda k: laws.index(k) if k in laws else -1):
        values = gates[law]
        if law not in laws or ionic.GATE_COUNTS[law] == 0:
            raise ConfigError("Template gates require a gated resolved_pump_tissue@3 channel law")
        if type(values) is not list or len(values) != ionic.GATE_COUNTS[law]:
            raise ConfigError("Template gates require exactly their law's gate count")
        parsed_gates.append((law, tuple(fraction(v, "template gate") for v in values)))
    routes = raw["route_values"]
    _fields(routes, set(ROUTE_KEYS), "template route_values")

    def density(value, name):
        return None if value is None else positive(value, name)

    return Template(
        identifier(raw["id"]),
        positive(raw["volume_pL"], "template volume"),
        signed_number(raw["fixed_charge_equivalent_fmol"], "template fixed charge"),
        tuple(positive(amounts[s], "template amount") for s in species),
        tuple(parsed_gates),
        _keyed(routes["channel_permeability_m_per_s"], laws, "channel permeability", positive),
        _keyed(routes["channel_abundance"], laws, "channel abundance", positive),
        _keyed(routes["membrane_permeability_m_per_s"], species, "membrane permeability", positive),
        density(routes["pump_capacity_fmol_per_s_m2"], "pump capacity density"),
        density(routes["calcium_pump_capacity_fmol_per_s_m2"], "calcium pump capacity density"),
    )


def slot_routes(model, slot):
    """The slot's membranes and channel populations (declaration objects)."""
    membranes = [p for p in model.membranes if p.inside == slot]
    ids = {p.id for p in membranes}
    return membranes, [c for c in model.channels if c.membrane_id in ids]


def check_template_on_slot(template, slot, model):
    """A template may only replace the slot's existing routes, on matching geometry."""
    cell = next(c for c in model.cells if c.id == slot)
    if template.volume_pL != cell.volume_pL:
        raise ConfigError(f"Template {template.id} volume differs from slot {slot}")
    if template.fixed_charge_equivalent_fmol != cell.fixed_charge_equivalent_fmol:
        raise ConfigError(f"Template {template.id} fixed charge background differs from {slot}")
    membranes, channels = slot_routes(model, slot)
    if not membranes:
        raise ConfigError(f"Replacement slot {slot} has no membrane")
    gated = {c.kinetic_law for c in channels if c.initial_gate}
    if not gated <= {law for law, _ in template.channel_gates}:
        raise ConfigError(f"Template {template.id} lacks gates for a channel law of {slot}")
    for law, _ in (*template.channel_permeability_m_per_s, *template.channel_abundance):
        present = [c for c in channels if c.kinetic_law == law]
        if not present or any(c.max_permeability_m_per_s <= 0 or c.abundance <= 0 for c in present):
            raise ConfigError(f"Template {template.id} would create a {law} route on {slot}")
    species = list(model.species_ids)
    for s, _ in template.membrane_permeability_m_per_s:
        if any(p.permeability_m_per_s[species.index(s)] <= 0 for p in membranes):
            raise ConfigError(f"Template {template.id} would create a {s} leak on {slot}")
    if template.pump_capacity_fmol_per_s_m2 is not None and any(
        p.pump is None or p.pump.capacity_fmol_per_s <= 0 for p in membranes
    ):
        raise ConfigError(f"Template {template.id} would create a Na/K pump on {slot}")
    if template.calcium_pump_capacity_fmol_per_s_m2 is not None and any(
        p.calcium_pump is None or p.calcium_pump.capacity_fmol_per_s <= 0 for p in membranes
    ):
        raise ConfigError(f"Template {template.id} would create a Ca pump on {slot}")


def on_grid(time, dt):
    """True when time is exactly k * dt for an integer k (the event grid's own test)."""
    k = round(time / dt)
    return k * dt == time


def exact_event_times(steps, dt):
    """Event times k * dt (float products) for integer step indices: no grid extras."""
    return [int(k) * dt for k in steps]


def parse_events(raw, base, templates):
    if type(raw) is not list:
        raise ConfigError("replacement_events requires an explicit list")
    m, dt, end = base.model, base.execution.dt, base.experiment.end_time
    order = {c.id: i for i, c in enumerate(m.cells)}
    names = {t.id: t for t in templates}
    events, carriers, seen = [], set(order), set()
    for row in raw:
        _fields(row, {"time", "slot", "template", "carrier_id"}, "replacement event")
        time = _number(row["time"], "replacement event time")
        slot, template, carrier = (
            identifier(row["slot"]),
            identifier(row["template"]),
            identifier(row["carrier_id"]),
        )
        if not 0 < time < end or not on_grid(time, dt):
            raise ConfigError("Replacement event times must be k * dt strictly inside the horizon")
        if slot not in order or template not in names:
            raise ConfigError("Replacement events require a declared cell and template")
        if carrier in carriers:
            raise ConfigError("Replacement carrier IDs must be new and unique")
        if (time, slot) in seen:
            raise ConfigError("At most one replacement per slot and time")
        carriers.add(carrier)
        seen.add((time, slot))
        events.append(ReplacementEvent(time, slot, template, carrier))
    events.sort(key=lambda v: (v.time, order[v.slot]))
    checked = set()
    for v in events:
        if (v.template, v.slot) not in checked:
            check_template_on_slot(names[v.template], v.slot, m)
            checked.add((v.template, v.slot))
    return tuple(events)


def parse(data):
    raw = copy.deepcopy(data)
    m, e = raw.get("model"), raw.get("experiment")
    if not isinstance(m, dict) or not isinstance(e, dict) or m.get("id") != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    if "replacement" not in m or "replacement_events" not in e:
        raise ConfigError("Declare replacement and replacement_events")
    declared, events = m.pop("replacement"), e.pop("replacement_events")
    _fields(
        declared,
        {"law", "inner_model", "junction_formation", "templates", "template_capacity"},
        "replacement",
    )
    if declared["law"] != OPERATION_LAW_ID:
        raise ConfigError("Replacement requires law " + OPERATION_LAW_ID)
    if declared["inner_model"] not in INNER_MODEL_IDS:
        raise ConfigError("Replacement inner model must be one of " + ", ".join(INNER_MODEL_IDS))
    m["id"] = declared["inner_model"]
    base = ionic.parse(raw)
    if type(declared["templates"]) is not list:
        raise ConfigError("Replacement templates require an explicit list")
    templates = tuple(parse_template(t, base) for t in declared["templates"])
    if len({t.id for t in templates}) != len(templates):
        raise ConfigError("Template IDs must be unique")
    capacity = _integer(
        declared["template_capacity"], "template_capacity", minimum=max(1, len(templates))
    )
    replacement = Replacement(
        OPERATION_LAW_ID,
        declared["inner_model"],
        parse_formation(declared["junction_formation"]),
        templates,
        capacity,
    )
    model = CellReplacementModel(
        **{k: getattr(base.model, k) for k in ionic.SurfacePumpChannelModel.__dataclass_fields__},
        replacement=replacement,
    )
    experiment = Experiment(
        **{k: getattr(base.experiment, k) for k in ionic.Experiment.__dataclass_fields__},
        replacement_events=parse_events(events, base, templates),
    )
    spec = replace(base, model=model, experiment=experiment)
    from cells.models.cell_replacement import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid cell replacement definition: " + str(error)) from error
    return spec


def event_table(spec):
    """Per slot index: (event times, 1-based template rows), in time order."""
    order = {c.id: i for i, c in enumerate(spec.model.cells)}
    rows = {t.id: k + 1 for k, t in enumerate(spec.model.replacement.templates)}
    table = {}
    for v in spec.experiment.replacement_events:
        times, templates = table.setdefault(order[v.slot], ([], []))
        times.append(v.time)
        templates.append(rows[v.template])
    return table


def control_values(spec, times):
    """Inner controls, then each slot's replacement count and latest template at each time.

    A count at t includes an event at exactly t (side "right", the inner schedules'
    rule), so the step leaving t_e sees the event; the model applies it at that
    step's start.
    """
    base = ionic.control_values(projection(spec), times)
    times = np.asarray(times, dtype=np.float64)
    shape = (len(times), spec.execution.capacity)
    generation, template = np.zeros(shape, dtype=np.int64), np.zeros(shape, dtype=np.int64)
    for slot, (event_times, rows) in event_table(spec).items():
        index = np.searchsorted(np.asarray(event_times), times, side="right")
        generation[:, slot] = index
        template[:, slot] = np.asarray([0, *rows], dtype=np.int64)[index]
    return Control(*base, generation, template)


def lineage(spec, generation=None):
    """One record per carrier: founders, then newcomers in event order.

    generation (per slot, the applied counts at the end of a run) limits the
    records to applied events; None lists every declared event.
    """
    order = {c.id: i for i, c in enumerate(spec.model.cells)}
    applied = {}
    for v in spec.experiment.replacement_events:
        k = applied.get(v.slot, 0)
        if generation is None or k < int(generation[order[v.slot]]):
            applied[v.slot] = k + 1
    current = {
        c.id: dict(carrier_id=c.id, slot=c.id, founder=True, birth_s=0.0) for c in spec.model.cells
    }
    records = list(current.values())
    count = {}
    for v in spec.experiment.replacement_events:
        if count.get(v.slot, 0) >= applied.get(v.slot, 0):
            continue
        count[v.slot] = count.get(v.slot, 0) + 1
        previous = current[v.slot]
        previous.update(death_s=v.time, successor=v.carrier_id)
        record = dict(
            carrier_id=v.carrier_id,
            slot=v.slot,
            founder=False,
            birth_s=v.time,
            template=v.template,
            predecessor=previous["carrier_id"],
        )
        records.append(record)
        current[v.slot] = record
    for r in records:
        r.setdefault("death_s", None)
        r.setdefault("successor", None)
    return records


def finite(value):
    return value is not None and math.isfinite(value)
