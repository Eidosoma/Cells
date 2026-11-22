"""Operator neutral_arrival_labels@1: neutral arrival-time labels as shares of a physical row.

FR-42 (docs/FEATURE_REQUESTS.md), option A of docs/NEUTRAL_LABELS_DESIGN.md (D289), stage 1: pools.
A neutral label records when otherwise identical units entered a pool, so the cohort that arrived
during a window can be followed. Each labelled species stays one physical row of @3's species axis,
which every law, energy term and heat booking reads as today; the labels are shares of it, which no
law reads. So labelling never changes the dynamics, the energy or a record of the physical state,
and a cohort can start at exactly zero (a share, not a stored amount).

Declaration: `species`, each {id, labels, initial}: a species of the model; its labels, one or
more distinct IDs (at most MAX_LABELS), the first its **base**, which holds unlabelled material (all
initial material unless declared otherwise, and every arrival outside a window); and `initial`, a
list, possibly empty, of {node, shares: {label: fraction}}: a cell's or finite outside node's
starting shares, each fraction in [0, 1] and their sum 1 within SUM_ULPS ulps (every node not
listed starts at the base). A species is labelled once. A world that declares D1's label families
(registry/species_registry.py) is refused by the registry's family check, which admits only
turnover and declarations beside them: a family's rows are separate rows, and shares replace them.

Schedule `label_arrivals`: [{species, schedule: [{time, label}, ...]}], at most one per species: the
label that each step's arrivals join, piecewise constant from its first change (the base before it
and for a species with no schedule). A change is an exact multiple of dt inside the horizon, and
changes increase strictly. A window [start, end) for label L is a change to L at start and one
back at end. Each step's label is the one in force at the step's start, resolved by step index
with execution/grid.py's same_instant (the predicate D283 names for label switches), so arrivals
during the step that starts at a window's start join it and during the step that starts at its
end do not. A label reused later keeps its older material, which survives with the rest.

State, present only in a composition that declares this operator: `label_share` [labelled species,
label, cell] and `label_outside_share` [..., outside node], each row's shares at each node (padded
labels 0, the presence mask bound in `label_present`); `label_closure_relative` [labelled species],
a diagnostic: the largest closure residual of any reporter's half-step so far
(label_shares.closure_residual), relative to the amounts involved. It measures each reporter's own
consistency, its booked move against its reported one-way parts, at rounding; that no other mover
touched the row is the definition's refusals' to hold, not this record's.

The update (the composite, models/pump_composite.py `_half_step`): after each applied half-step of a
reporter (contract.reports_labels: turnover, the reactions' driven routes, and templated
polymerisation with the gene regulation lane's side), the shares are advanced from the half-step's
start and end amounts and its moves (numerics/label_shares.advance: exact for a constant
per-molecule rate within the half-step, second-order otherwise; without arrivals the shares are
kept bit for bit). The physical state and validity are the reporter's, bit for bit, so a labelled
run's physical fields and records equal the unlabelled run's.

Refused in stage 1 (fail closed), each refusal naming the FR-42 stage that lifts it:
- a labelled species moved inside the inner step (registry moved_in_step: faces, routes, channels,
  pumps, kinds and in-step processes), which report from stage 2;
- an operator whose split part writes species amounts without reporting, except exchange whose
  routes name no labelled species (exchange reports from stage 3);
- an event that writes species amounts, a closer or retirer of slots, and a provider of the amount
  references (no FR-42 stage plans them yet).
A second label owner is refused by the composite's parser, as a second declaration of its schedule
key. Reporters refuse their own unreported cases (reactions: a passive route on a labelled row,
which reports from stage 3). RK4 on the coupled path needs no refusal: a coupled RK4 composition
refuses every split-only part, so no reporter runs there.
"""

from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.execution.grid import same_instant
from cells.numerics import label_shares
from cells.numerics.species_sums import entity_sum
from cells.operators.contract import Operator, reports_labels
from cells.registry import species_registry

LAW_ID = "neutral_arrival_labels@1"
SCHEDULE_KEY = "label_arrivals"
MAX_LABELS = 16
SUM_ULPS = 8  # A declared node's shares sum to 1 within this many ulps.
AMOUNT_FIELDS = ("amount_increment", "extracellular_amount_increment")
AMOUNT_VIEWS = ("amount_reference", "extracellular_amount_reference")
EXCHANGE = "scheduled_species_exchange@1"
# The FR-42 stage that adds a non-reporting writer's one-way reports, where one plans it.
PLANNED = {
    EXCHANGE: "FR-42's stage 3",
    "templated_polymerisation@1": "FR-42's stage 1, the gene regulation lane's side",
}
NOT_PLANNED = "no FR-42 stage plans it yet"

STATE_AXES = {
    "label_share": ["label_species", "label_slot", "cell_slot"],
    "label_outside_share": ["label_species", "label_slot", "extracellular_slot"],
    "label_closure_relative": ["label_species"],
}
LAYOUT_FIELDS = (
    "label_rows",  # [labelled species] int64: their rows of the model's species axis.
    "label_present",  # [labelled species, label] bool: the declared labels (padding False).
)


@dataclass(frozen=True)
class Labelled:
    id: str
    labels: tuple  # Label IDs, the base first.
    initial: tuple  # ((node id, ((label, fraction), ...)), ...), in declared order.


@dataclass(frozen=True)
class Labels:
    law: str
    species: tuple  # Labelled, ...


# ------------------------------------------------------------------ definition


def _fraction(value, what):
    if type(value) not in (int, float) or not np.isfinite(value) or not 0 <= value <= 1:
        raise ConfigError(f"{LAW_ID}: {what} is a share in [0, 1]")
    return float(value)


def parse_labels(raw, base):
    _fields(raw, {"law", "species"}, "neutral arrival labels")
    if raw["law"] != LAW_ID:
        raise ConfigError("Neutral arrival labels require law " + LAW_ID)
    if type(raw["species"]) is not list or not raw["species"]:
        raise ConfigError(f"{LAW_ID} lists its labelled species in a non-empty list")
    m = base.model
    cells = {c.id for c in m.cells}
    outside = {c.id: c for c in m.extracellular}
    out = []
    for entry in raw["species"]:
        _fields(entry, {"id", "labels", "initial"}, f"{LAW_ID} species")
        name = identifier(entry["id"])
        if name not in m.species_ids:
            raise ConfigError(f"{LAW_ID} labels a species the model does not declare: {name!r}")
        labels = entry["labels"]
        if (
            type(labels) is not list
            or not 1 <= len(labels) <= MAX_LABELS
            or len(set(labels)) != len(labels)
        ):
            raise ConfigError(
                f"{LAW_ID}: species {name} lists 1 to {MAX_LABELS} distinct labels, its base first"
            )
        labels = tuple(identifier(label) for label in labels)
        if type(entry["initial"]) is not list:
            raise ConfigError(f"{LAW_ID}: species {name}'s initial shares are a list")
        initial, seen = [], set()
        for item in entry["initial"]:
            _fields(item, {"node", "shares"}, f"{LAW_ID} initial shares")
            node = item["node"]
            if node in outside and outside[node].reservoir:
                raise ConfigError(
                    f"{LAW_ID}: {name}'s shares at {node}, a held bath, whose composition is held"
                )
            if node not in cells and node not in outside:
                raise ConfigError(f"{LAW_ID}: {name}'s shares at an undeclared node {node!r}")
            if node in seen:
                raise ConfigError(f"{LAW_ID}: {name}'s shares at {node} are declared twice")
            seen.add(node)
            shares = item["shares"]
            if not isinstance(shares, dict) or not shares or set(shares) - set(labels):
                raise ConfigError(f"{LAW_ID}: {name}'s shares at {node} name its own labels")
            values = tuple(
                (label, _fraction(v, f"{name}'s share {label} at {node}"))
                for label, v in shares.items()
            )
            if abs(sum(v for _, v in values) - 1.0) > SUM_ULPS * label_shares.EPS:
                raise ConfigError(f"{LAW_ID}: {name}'s shares at {node} sum to 1")
            initial.append((node, values))
        out.append(Labelled(name, labels, tuple(initial)))
    if len({s.id for s in out}) != len(out):
        raise ConfigError(f"{LAW_ID} labels a species twice")
    return Labels(LAW_ID, tuple(out))


def labels_to_dict(declaration):
    if type(declaration) is not Labels or any(type(s) is not Labelled for s in declaration.species):
        raise ConfigError("Require explicit immutable neutral arrival label declaration types")
    return dict(
        law=declaration.law,
        species=[
            dict(
                id=s.id,
                labels=list(s.labels),
                initial=[dict(node=node, shares=dict(values)) for node, values in s.initial],
            )
            for s in declaration.species
        ],
    )


def parse_arrivals(raw, base, declaration):
    """((species, ((time, label), ...)), ...), by species ID, from the label_arrivals list
    (module docstring): nested tuples, so the definition stays hashable."""
    if type(raw) is not list:
        raise ConfigError(f"{SCHEDULE_KEY} requires an explicit list")
    by_id = {s.id: s for s in declaration.species}
    dt, end = base.execution.dt, base.experiment.end_time
    schedules = {}
    for entry in raw:
        _fields(entry, {"species", "schedule"}, f"{SCHEDULE_KEY} entry")
        species = by_id.get(entry["species"])
        if species is None:
            raise ConfigError(f"{SCHEDULE_KEY} names a species not labelled: {entry['species']!r}")
        if species.id in schedules:
            raise ConfigError(f"{LAW_ID}: one arrival schedule per species ({species.id})")
        if type(entry["schedule"]) is not list or not entry["schedule"]:
            raise ConfigError(f"{LAW_ID}: {species.id}'s arrival schedule lists its changes")
        changes = []
        for change in entry["schedule"]:
            _fields(change, {"time", "label"}, f"{SCHEDULE_KEY} change")
            time, label = change["time"], change["label"]
            if type(time) not in (int, float) or not np.isfinite(time):
                raise ConfigError(f"{SCHEDULE_KEY} requires a finite time")
            time = float(time)
            if time != round(time / dt) * dt or not 0.0 <= time <= end:
                raise ConfigError(
                    f"{LAW_ID}: a label switch is an exact multiple of dt (k * dt) inside the "
                    f"horizon ({species.id} at {time!r})"
                )
            if label not in species.labels:
                raise ConfigError(f"{LAW_ID}: {species.id} has no label {label!r}")
            changes.append((time, label))
        times = [t for t, _ in changes]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ConfigError(f"{LAW_ID}: {species.id}'s switch times increase strictly")
        schedules[species.id] = tuple(changes)
    return tuple(sorted(schedules.items()))


def arrival_index(changes, times):
    """[time] the position, among a species' labels, of the label in force at each step start of
    `times` (increasing), given its changes ((time, position), ...) in increasing time and the
    base (0) before the first. A change applies from the first step that starts at it or after it,
    a start at the same instant (grid.same_instant) included: a window's start is its first step,
    and its end the first step it does not hold."""
    times = np.asarray(times, dtype=np.float64)
    index = np.zeros(times.shape, dtype=np.int64)
    for at, position in changes:
        first = int(np.searchsorted(times, at, side="left"))
        if first > 0 and same_instant(float(times[first - 1]), at):
            first -= 1
        index[first:] = position
    return index


def arrival_controls(declaration, schedule, times):
    """[time, labelled species, label] one-hot: the label each step's arrivals join."""
    width = max(len(s.labels) for s in declaration.species)
    out = np.zeros((len(times), len(declaration.species), width))
    for j, s in enumerate(declaration.species):
        changes = tuple((t, s.labels.index(label)) for t, label in dict(schedule).get(s.id, ()))
        out[np.arange(len(times)), j, arrival_index(changes, times)] = 1.0
    return out


def operator_errors(spec, declaration):
    """Stage 1's fail-closed refusals of the composition (module docstring), as messages."""
    labelled = {s.id for s in declaration.species}
    errors = []
    for op, other, _ in composite_spec.entries(spec):
        if op.LABEL_OWNER:
            continue
        writes = set(AMOUNT_FIELDS) & {*op.ENTITY_WRITES, *op.EVENT_REPLACES, *op.STATE_RESETS}
        where = f"{op.LAW_ID} beside {LAW_ID}"
        if op.RETIRES or op.CLOSES:
            errors.append(f"{where}: it closes or retires slots ({NOT_PLANNED})")
        elif set(AMOUNT_VIEWS) & set(op.VIEW_FIELDS):
            errors.append(f"{where}: its view changes species amounts ({NOT_PLANNED})")
        elif writes and op.EVENT:
            errors.append(f"{where}: its events write species amounts ({NOT_PLANNED})")
        elif writes and op.SPLIT and not reports_labels(op):
            routed = {r.species for r in getattr(other, "routes", ())}
            if op.LAW_ID == EXCHANGE and not routed & labelled:
                continue
            later = f"{PLANNED[op.LAW_ID]} adds them" if op.LAW_ID in PLANNED else NOT_PLANNED
            errors.append(
                f"{where}: it writes species amounts without reporting its one-way moves ({later})"
            )
    return errors


def check_labels(spec, declaration):
    """The definition's refusals (module docstring)."""
    moved = species_registry.moved_in_step(spec)
    for s in declaration.species:
        movers = [*moved[s.id]["cell"], *moved[s.id]["outside"]]
        if movers:
            raise ConfigError(
                f"{LAW_ID}: {s.id} is moved inside the inner step by {', '.join(movers)}, which "
                "do not report one-way moves yet (faces, routes and kinds report from FR-42's "
                "stage 2)"
            )
    errors = operator_errors(spec, declaration)
    if errors:
        raise ConfigError("; ".join(errors))


def labelled_species(spec):
    """The species a composition's label owner labels (a frozenset; empty without one): for a
    reporter's own refusals of the cases it does not report."""
    return frozenset(
        s.id
        for op, declaration, _ in composite_spec.entries(spec)
        if op.LABEL_OWNER
        for s in declaration.species
    )


def bind(spec, declaration):
    m, x = spec.model, spec.execution
    species = list(m.species_ids)
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    count = len(declaration.species)
    width = max(len(s.labels) for s in declaration.species)
    present = np.zeros((count, width), dtype=bool)
    share = np.zeros((count, width, x.capacity))
    outside_share = np.zeros((count, width, x.extracellular_capacity))
    share[:, 0, :] = 1.0
    outside_share[:, 0, :] = 1.0
    for j, s in enumerate(declaration.species):
        present[j, : len(s.labels)] = True
        for node, values in s.initial:
            target, k = (share, cells.index(node)) if node in cells else (outside_share, None)
            k = outside.index(node) if k is None else k
            target[j, :, k] = 0.0
            for label, value in values:
                target[j, s.labels.index(label), k] = value
    layout = dict(
        label_rows=np.asarray([species.index(s.id) for s in declaration.species], dtype=np.int64),
        label_present=present,
    )
    state = dict(
        label_share=share,
        label_outside_share=outside_share,
        label_closure_relative=np.zeros(count),
    )
    return state, layout


# ------------------------------------------------------------------ the update


def amounts(state, p, *, xp):
    """([labelled, cell], [labelled, outside node]) amounts, and the increments' magnitudes."""
    rows = p.label_rows
    cell_increment = state.amount_increment[rows]
    node_increment = state.extracellular_amount_increment[rows]
    return (
        p.amount_reference[rows] + cell_increment,
        p.extracellular_amount_reference[rows] + node_increment,
        xp.abs(cell_increment),
        xp.abs(node_increment),
    )


def advance(start, end, moves, p, *, xp=jnp):
    """end with the label shares advanced by one reporter's applied half-step from start, given
    its moves (out [m, node], into [m, label, node], transfers): label_shares.advance at the cells
    and the outside nodes, and the closure diagnostic's running maximum. The node axis is the cells
    then the outside nodes, or the cells alone (contract)."""
    out, into, transfers = moves
    if transfers:
        raise ConfigError(f"{LAW_ID}: transfers are reported from FR-42's stage 2")
    cells, nodes = p.active.shape[0], p.outside_active.shape[0]
    if out.shape[-1] == cells and nodes:  # A reporter at cells only: nothing at outside nodes.
        out = xp.concatenate((out, xp.zeros(out.shape[:-1] + (nodes,))), axis=-1)
        into = xp.concatenate((into, xp.zeros(into.shape[:-1] + (nodes,))), axis=-1)
    present = p.label_present
    c0, o0, ci0, oi0 = amounts(start, p, xp=xp)
    c1, o1, ci1, oi1 = amounts(end, p, xp=xp)
    shares = (start.label_share, start.label_outside_share)
    parts = ((c0, c1, ci0, ci1, p.active), (o0, o1, oi0, oi1, p.outside_active & ~p.reservoir))
    ends = (slice(None, cells), slice(cells, None))
    new, worst = [], start.label_closure_relative
    for share, (n0, n1, i0, i1, mask), part in zip(shares, parts, ends, strict=True):
        o, i = out[..., part], into[..., part]
        new.append(label_shares.advance(share, n0, n1, i, present, xp=xp))
        residual = label_shares.closure_residual(n0, n1, i, o, xp=xp)
        scale = n0 + n1 + entity_sum(i, axis=1, xp=xp) + o + i0 + i1
        relative = xp.where(mask[None, :], residual / xp.where(scale > 0, scale, 1.0), 0.0)
        worst = xp.maximum(worst, xp.max(relative, axis=1, initial=0.0))
    return end._replace(
        label_share=new[0], label_outside_share=new[1], label_closure_relative=worst
    )


def labels_domain_valid(state, p, *, xp):
    """The shares' domain (label_shares.domain_valid) at every node, and the diagnostic finite
    and non-negative."""
    present = p.label_present
    closure = state.label_closure_relative
    return (
        label_shares.domain_valid(state.label_share, present, xp=xp)
        & label_shares.domain_valid(state.label_outside_share, present, xp=xp)
        & xp.all(xp.isfinite(closure) & (closure >= 0))
    )


# ------------------------------------------------------------------ the operator


class NeutralArrivalLabels(Operator):
    LAW_ID = LAW_ID
    LABEL_OWNER = True
    IDENTITY_ROLE = "user"  # It labels species others declare.
    STATE_AXES = STATE_AXES
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("label_arrival",)
    EXPERIMENT_KEYS = (SCHEDULE_KEY,)
    VIEW_LAYERS = (
        {"id": "labels", "label": "Neutral arrival labels", "representation": "simulated"},
    )
    UNITS = {"label_share": "1", "label_outside_share": "1", "label_closure_relative": "1"}
    RECORD_KINDS = {
        "label_share": "level",
        "label_outside_share": "level",
        "label_closure_relative": "level",
    }
    RECORD_DIAGNOSTICS = ("label_closure_relative",)

    def view_sets(self, spec, declaration):
        """The run view's sets of its two axes: the labelled species, and the label positions
        (each species' labels in declared order, the base first; padding past its own)."""
        width = max(len(s.labels) for s in declaration.species)
        return {
            "label_species": {
                "id": "label_species",
                "ids": tuple(s.id for s in declaration.species),
                "holds": "labelled species",
                "carries": tuple(s.id for s in declaration.species),
            },
            "label_slot": {
                "id": "label_slot",
                "ids": tuple(f"label_{k}" for k in range(width)),
                "holds": "label position, each labelled species' labels in declared order",
                "labels": {s.id: list(s.labels) for s in declaration.species},
            },
        }

    def view_events(self, spec, declaration, schedule):
        """Each label switch, at its labelled species (the entry at time 0 sets the start). It
        decides no cell's life, so there are no births or retirements."""
        layer = self.VIEW_LAYERS[0]["id"]
        events = [
            dict(
                time=float(t),
                kind="label switch",
                layer=layer,
                at={"label_species": name},
                label=f"{name}: arrivals join {label}",
            )
            for name, changes in schedule
            for t, label in changes
        ]
        return tuple(sorted(events, key=lambda e: (e["time"], e["label"])))

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_labels(raw, base)

    def to_dict(self, declaration, base):
        return labels_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_arrivals(raw[SCHEDULE_KEY], base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return {
            SCHEDULE_KEY: [
                dict(species=name, schedule=[dict(time=t, label=label) for t, label in changes])
                for name, changes in schedule
            ]
        }

    def schedule_times(self, schedule):
        return tuple(t for _, changes in schedule for t, _ in changes)

    def value_at(self, schedule, time):
        """Each scheduled species' label in force at `time` (None before its first change)."""
        out = []
        for name, changes in schedule:
            before = [label for t, label in changes if t <= time]
            out.append((name, before[-1] if before else None))
        return tuple(out)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        return (arrival_controls(declaration, schedule, times),)

    def check_definition(self, spec, declaration, schedule, model):
        check_labels(spec, declaration)

    def batch_signature(self, declaration):
        """The labelled species and their label counts; IDs, shares and schedules are data."""
        return (LAW_ID, tuple((s.id, len(s.labels)) for s in declaration.species))

    def working_size(self, spec):
        (declaration,) = (d for op, d, _ in composite_spec.entries(spec) if op.LAW_ID == LAW_ID)
        x = spec.execution
        width = max(len(s.labels) for s in declaration.species)
        size = len(declaration.species) * width * (x.capacity + x.extracellular_capacity)
        return 8 * 6 * size

    def summary(self, spec, declaration, schedule, history):
        return {
            "label_law": LAW_ID,
            "labelled_species": {
                s.id: dict(
                    labels=list(s.labels),
                    base=s.labels[0],
                    initial={node: dict(values) for node, values in s.initial},
                    arrivals=[
                        dict(time=t, label=label) for t, label in dict(schedule).get(s.id, ())
                    ],
                )
                for s in declaration.species
            },
            "label_update": "shares of each physical row, advanced after each reporter's "
            "half-step from its one-way moves (numerics/label_shares.advance)",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ the composite's calls

    def labels(self, control, p):
        """A reporter's labels argument (contract): (the labelled rows, this step's arrival)."""
        return p.label_rows, control.label_arrival

    def advance(self, start, end, moves, p, *, xp):
        return advance(start, end, moves, p, xp=xp)

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & labels_domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = labels_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own
