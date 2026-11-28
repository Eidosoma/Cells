"""Operator cells.operator.neutral_arrival_labels@1: neutral arrival-time labels as shares of a physical row.

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
listed starts at the base). A species is labelled once. Shares replaced D1's label families, rows
of their own with their own potentials, which D300 retired.

Producers (amendment G, TEMPLATED_POLYMERISATION_LAWS §9.20, option (a); D307): a species' entry may
name chain sources, `producers: [{source, windows: [{label, from, to}, ...]}]`, whose labels and
schedules the owner derives at the definition, host side (`derived`), from replacement@1's occupants
keyed by cell ID: for each generation k of the chain's cell, `<cell>-g<k>-<chain>` and
`<cell>-g<k>-<chain>-<window>` for each window, after the species' own labels and within
MAX_LABELS; and the source's schedule, the generation's label from its birth, its window's inside
each window, the next generation's from the next event's step. These are the controls a correct
hand-written schedule gives, so the programs are unchanged; a hand-written schedule for a producer
source is refused (one authority). The definition keeps `producers`, not the labels, so a restart
and a reordering of the cells derive the same.

Schedule `label_arrivals`: [{species, schedule: [{time, label}, ...]}], at most one per species: the
label that each step's arrivals join, piecewise constant from its first change (the base before it
and for a species with no schedule). A change is a point of the clock's grid (D283's on_grid:
k * dt, or within its same-instant tolerance of it) inside the horizon, and changes increase
strictly. A window [start, end) for label L is a change to L at start and one back at end. Each
step's label is the one in force at the step's start, resolved by step index with D283's
same_instant (numerics/clock_instants.py, the predicate it names for label switches), so arrivals
during the step that starts at a window's start join it and during the step that starts at its end
do not. A label reused later keeps its older material, which survives with the rest.

State, present only in a composition that declares this operator: `label_share` [labelled species,
label, cell] and `label_outside_share` [..., outside node], each row's shares at each node (padded
labels 0, the presence mask bound in `label_present`); beside a replacing event (`replacing`;
zero-size elsewhere), `label_removed_fmol` [labelled species, label, cell] and
`label_pool_removed_fmol` [pool reporter, label, pool], what left at its events by label, cumulative
from t = 0 (erratum E); beside an exchanging event (`exchanging`, FR-44; zero-size elsewhere),
`label_outside_removed_fmol` [labelled species, label, outside node], what left at its liquid
exchanges by label, cumulative from t = 0 (fmol); `label_closure_relative` [labelled species],
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

Stage 2 and D296 (docs/NEUTRAL_LABELS_DESIGN.md section 8): where the inner step takes labels=,
its faces' and routes' one-way transfers carry their sources' shares (advance_inner), and so do
its declared kinds' through their hook (section 11; D303 item 6); a pool reporter's pools are
advanced with its rows as sites (advance_pools); a source reporter receives each source's arrival
label (source_controls); replacement@1's event reports the slots it replaced, which take the
newcomer label, and a pool reporter's event the pools it emptied, which take the base label, what
left recorded by label (advance_event; erratum E, TEMPLATED_POLYMERISATION_LAWS §9.18).

Liquid exchanges (FR-44, D327; docs/NEUTRAL_LABELS_DESIGN.md §13): an exchanging event (the
compartment wash) reports a LiquidExchange at the outside nodes. The owner reads each report by
its event's declared kind (contract.label_event), never by its shape.
- The sample is well mixed, so it leaves with the node's shares; what left is recorded by label at
  the shares just before the event.
- The buffer carries no label and joins the base, even while a window is open: a buffer is not an
  arrival.
- Each label's material is then (n - removed) s_k + supplied [k = 0], exactly
  (label_shares.exchange). A labelled ion's amount is kept while its shares dilute toward the
  base, since the exchanged liquid is replaced by unlabelled liquid of the same composition.
- Cells' shares are not touched: the report's axis is the outside nodes, so an exchange of a
  cell's own liquid cannot be expressed in version 1.

Admission by species (FR-44 step 3; D327, D424; docs/NEUTRAL_LABELS_DESIGN.md §14). A split writer
that reports no one-way moves is admitted beside the owner only where its law is on BY_SPECIES, it
declares its rows (the contract's ROW_MOVES and written_rows, FR-43 part 3's one authority), and no
species of its written rows is labelled. The test is by species, not by row: a labelled species has
shares at every cell and finite node, and an unreported change at one node would be carried onward
by every later transfer. Version 1 lists cells.operator.site_occupancy@1 alone, whose half-steps
write amounts only at its pools, which are its written rows, and keep every other entry bit for
bit. Beside such a writer and the owner, the other operator laws must all lie in one of the
writer's qualified sets (BY_SPECIES), any subset of one, each set qualified together by its own
check:
- FR-44 step 3's: the wash, D152's reactions, turnover and exchange, qualified by
  tests/unit/test_neutral_labels_sites.py's twin (D425);
- FR-49's C4 (fr49-compartment-compositions-v1, amendment 2): the compartments
  (cells.operator.cell_owned_compartments@1), expression
  (cells.operator.templated_polymerisation@1) with its routes in cells only, turnover and the wash,
  anchored on the compartments: it applies only where they are declared, since C4 qualifies its
  laws in a compartment world.
Each of these is refused by name (by_species_errors, fail closed) until a world qualifies it:
- an operator law in no set, all named in one message (NOT_A_PARTNER);
- laws each in some set but in no one set together, expression with no compartment declared among
  them (NOT_TOGETHER);
- a partner's variant that no set's check qualifies (PARTNER_VARIANT): in version 1, an export or an
  outside degradation of cells.operator.templated_polymerisation@1 (amendment T);
- a channel population where the set that admits the composition was qualified with none (CHANNEL):
  in version 1, beside C4's set, whose world declares no channel;
- an internalising population, which no registered world needs (D424), and a population that
  binds from a cell (an inward patch face or a contact): the twin qualifies binding at outside
  nodes only, so version 1 writes no cell row;
- the inner model's later options: cells.model.resolved_pump_tissue@3's own one-way records, a
  blocked channel population, a declared voltage shift, the sparse field solver, and X2, which is
  attached after the definition's checks and so is refused at binding (initial_values).
A labelled ligand stays refused: it waits for sites as label reporters (D327).

Refused (fail closed), each refusal naming the FR-42 stage that lifts it:
- a labelled species moved inside the inner step (registry moved_in_step) by anything the inner
  step does not report: every mover before @3's side lands (stage 2); afterwards a charged face,
  a channel, a pump, a kind without its hook (label_transfers) or an in-step process, and RK4
  beside a followed mover;
- what a declared kind says it cannot carry (its label_refusals), and, while any row is
  labelled, every kind with a rates hook and no label_refusals (kind_registry.label_refusal_errors);
- a labelled species a closure holds at some node (a kind's stage read: B4's proton row and
  buffers, cells.binding.rapid_binding@1's closure rows), whatever moves it (closure_errors);
- an operator whose split part writes species amounts without reporting (turnover, exchange,
  reactions and templated polymerisation report; FR-42's stage 3 added exchange and the reactions'
  passive routes), unless it is admitted by species (above);
- an event that writes species amounts and reports neither the slots it replaced nor a liquid
  exchange, a closer or retirer of slots, and a provider of the amount references (no FR-42 stage
  plans them yet);
- a labels-taking event whose report kind is missing or contradicts its declarations
  (contract.label_event_error, FR-44), so that no report is read as another kind's;
- beside a replacing event, a pool reporter whose event takes no labels (it could empty its pools
  unreported; erratum E).
A second label owner is refused by the composite's parser, as a second declaration of its schedule
key. RK4 on the coupled path needs no refusal: a coupled RK4 composition refuses every split-only
part, so no reporter runs there.
"""

from dataclasses import dataclass, replace
from types import MappingProxyType

import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.models import inner_laws
from cells.numerics import label_shares
from cells.numerics.clock_instants import ON_THE_GRID, on_grid, same_instant  # D283's predicate.
from cells.numerics.species_sums import entity_sum
from cells.operators.contract import (
    EMPTIED,
    EXCHANGED,
    LABEL_EVENT_KINDS,
    LiquidExchange,
    Operator,
    label_event,
    label_event_error,
    reports_labels,
    takes_labels,
)
from cells.registry import kind_registry, species_registry

LAW_ID = "cells.operator.neutral_arrival_labels@1"
SCHEDULE_KEY = "label_arrivals"
MAX_LABELS = 64  # Producer x window labels (D296) need more than one window's few.
SUM_ULPS = 8  # A declared node's shares sum to 1 within this many ulps.
AMOUNT_FIELDS = ("amount_increment", "extracellular_amount_increment")
AMOUNT_VIEWS = ("amount_reference", "extracellular_amount_reference")
# FR-42's stage 2: the inner step's movers whose one-way transfers it reports (@3's side), by mover
# kind: the uncharged face (cells.route.logmean_electrodiffusion@1, Fick's for an uncharged row) and the
# membrane and junction routes (cells.route.constant_field@1, GHK at the shared voltage), each linear in each
# end.
REPORTED_MOVERS = {
    "face": inner_laws.FACE_ROUTE_LAW_ID,
    "membrane": inner_laws.MEMBRANE_ROUTE_LAW_ID,
    "junction": inner_laws.MEMBRANE_ROUTE_LAW_ID,
}
NOT_PLANNED = "no FR-42 stage plans it yet"
# FR-44 step 3, admission by species (D327, D424; module docstring).
SITES_LAW = "cells.operator.site_occupancy@1"
COMPARTMENTS_LAW = "cells.operator.cell_owned_compartments@1"
# Its refusals by name (operator_errors, by_species_errors).
LABELLED_ROW = "a writer admitted by species writes a labelled row"
NOT_A_PARTNER = "an operator not admitted beside labels and a writer admitted by species"
NOT_TOGETHER = "operators not admitted together beside labels and a writer admitted by species"
PARTNER_VARIANT = "a partner's variant not admitted beside labels and a writer admitted by species"
CHANNEL = (
    "a channel population not admitted beside labels, its qualified set and a writer admitted by "
    "species"
)
UNQUALIFIED = "a variant not admitted beside labels"
OPTION = "an inner-model option not admitted beside labels and a writer admitted by species"


@dataclass(frozen=True)
class QualifiedSet:
    """Operator laws admitted together beside a writer admitted by species and the owner, any
    subset of them, qualified by one check; with an anchor, only where that law is declared."""

    name: str
    laws: tuple
    check: str
    anchor: str | None = None
    channels: bool = True  # Whether its check qualified channel populations beside the set.

    def admits(self, others, declared):
        """Whether these other laws lie in this set, where its anchor, if any, is declared."""
        return set(others) <= set(self.laws) and (self.anchor is None or self.anchor in declared)

    def described(self):
        where = f", where {self.anchor} is declared" if self.anchor else ""
        return f"{self.name}'s {{{', '.join(self.laws)}}}{where} ({self.check})"


@dataclass(frozen=True)
class BySpecies:
    """A split writer admitted by species: its qualified sets (QualifiedSet), its declaration's
    variants not yet qualified, each (what, function(declaration) -> the IDs that declare it), and
    its partners' variants not yet qualified, each (law, what, function(the partner's declaration)
    -> the IDs that declare it)."""

    sets: tuple
    unqualified: tuple
    partner_variants: tuple = ()

    @property
    def partners(self):
        """Every law of its sets, in order: the laws admitted beside it in some set."""
        return tuple(dict.fromkeys(law for qualified in self.sets for law in qualified.laws))

    def together(self, others, declared):
        """Whether one set admits all these other laws together."""
        return any(qualified.admits(others, declared) for qualified in self.sets)

    def described(self):
        return "; ".join(qualified.described() for qualified in self.sets)


def _internalising(declaration):
    """The site operator's populations that internalise (D424: refused by name beside labels)."""
    return tuple(p.id for p in declaration.populations if p.internalisation_rate is not None)


def _cell_facing(declaration):
    """The site operator's populations that bind from a cell, an inward patch face or a contact
    (site_occupancy.facing_node): refused by name beside labels until a world qualifies a cell
    pool, since the twin binds at outside nodes only."""
    return tuple(
        p.id
        for p in declaration.populations
        if p.owner_kind == "contact" or (p.owner_kind == "patch" and p.facing != "outside")
    )


def _reaches_outside(declaration):
    """Expression's exports and outside degradations (amendment T): C4 qualifies expression with
    its routes in cells only, World L's form."""
    return tuple(
        route.id
        for route in (
            *getattr(declaration, "exports", ()),
            *getattr(declaration, "outside_degradations", ()),
        )
    )


EXPRESSION_LAW = "cells.operator.templated_polymerisation@1"
BY_SPECIES = MappingProxyType(
    {
        SITES_LAW: BySpecies(
            sets=(
                QualifiedSet(
                    "FR-44 step 3",
                    (
                        "cells.operator.scheduled_compartment_wash@1",
                        "cells.operator.local_species_reactions@1",
                        "cells.operator.scheduled_species_turnover@1",
                        "cells.operator.scheduled_species_exchange@1",
                    ),
                    "tests/unit/test_neutral_labels_sites.py, D425",
                ),
                QualifiedSet(
                    "FR-49's C4",
                    (
                        COMPARTMENTS_LAW,
                        EXPRESSION_LAW,
                        "cells.operator.scheduled_species_turnover@1",
                        "cells.operator.scheduled_compartment_wash@1",
                    ),
                    "fr49-compartment-compositions-v1, amendment 2",
                    anchor=COMPARTMENTS_LAW,
                    channels=False,  # C4's world declares none (the lead's ruling, D327).
                ),
            ),
            unqualified=(
                ("an internalising population", _internalising),
                ("a population facing a cell (an inward patch face or a contact)", _cell_facing),
            ),
            partner_variants=(
                (EXPRESSION_LAW, "an export or an outside degradation", _reaches_outside),
            ),
        ),
    }
)

STATE_AXES = {
    "label_share": ["label_species", "label_slot", "cell_slot"],
    "label_outside_share": ["label_species", "label_slot", "extracellular_slot"],
    "label_closure_relative": ["label_species"],
    # D296: each pool reporter's (LABEL_POOLS, in declared order) pool entries' shares.
    "label_pool_share": ["label_pool_owner", "label_slot", "label_pool"],
    # Erratum E (TEMPLATED_POLYMERISATION_LAWS §9.18): what left at replacement events, by label,
    # cumulative from t = 0 (fmol); zero-size along the first axis without a replacing event.
    "label_removed_fmol": ["label_removed_species", "label_slot", "cell_slot"],
    "label_pool_removed_fmol": ["label_removed_pool_owner", "label_slot", "label_pool"],
    # FR-44: what left outside nodes at liquid exchanges, by label, cumulative from t = 0 (fmol);
    # zero-size along the first axis without an exchanging event.
    "label_outside_removed_fmol": [
        "label_outside_removed_species",
        "label_slot",
        "extracellular_slot",
    ],
}
LAYOUT_FIELDS = (
    "label_rows",  # [labelled species] int64: their rows of the model's species axis.
    "label_present",  # [labelled species, label] bool: the declared labels (padding False).
    "label_pool_rows",  # [pool owner, pool] int64: the entry's labelled species, -1 if none.
    "label_pool_present",  # [pool owner, label, pool] bool: its species' labels (else the base).
    "label_pool_cells",  # [pool owner, pool] int64: the entry's cell, -1 for none (D296).
)


@dataclass(frozen=True)
class Labelled:
    id: str
    labels: tuple  # Label IDs, the base first.
    initial: tuple  # ((node id, ((label, fraction), ...)), ...), in declared order.
    # Amendment G (TEMPLATED_POLYMERISATION_LAWS §9.20, option (a)): chain sources whose producer
    # labels and schedules the owner derives, ((source, ((window, from, to), ...)), ...).
    producers: tuple = ()


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
        keys = {"id", "labels", "initial"} | ({"producers"} if "producers" in entry else set())
        _fields(entry, keys, f"{LAW_ID} species")
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
        producers = _producers(entry.get("producers", []), name, base)
        out.append(Labelled(name, labels, tuple(initial), producers))
    if len({s.id for s in out}) != len(out):
        raise ConfigError(f"{LAW_ID} labels a species twice")
    return Labels(LAW_ID, tuple(out))


def _producers(raw, name, base):
    """A species' producers (amendment G): ((source, ((window, from, to), ...)), ...), each a chain
    source whose producer labels the owner derives, its windows [from, to) on the clock's grid
    inside the horizon, increasing and disjoint, crossed with each generation."""
    if type(raw) is not list:
        raise ConfigError(f"{LAW_ID}: species {name}'s producers are a list")
    dt, end = base.execution.dt, base.experiment.end_time
    out, seen = [], set()
    for item in raw:
        _fields(item, {"source", "windows"}, f"{LAW_ID} producer")
        source = identifier(item["source"])
        if source in seen:
            raise ConfigError(f"{LAW_ID}: species {name} names producer {source} twice")
        seen.add(source)
        if type(item["windows"]) is not list:
            raise ConfigError(f"{LAW_ID}: producer {source}'s windows are a list")
        windows, last = [], 0.0
        for window in item["windows"]:
            _fields(window, {"label", "from", "to"}, f"{LAW_ID} producer window")
            label = identifier(window["label"])
            times = [window[k] for k in ("from", "to")]
            if any(type(t) not in (int, float) or not np.isfinite(t) for t in times):
                raise ConfigError(f"{LAW_ID}: producer {source}'s window {label} has finite times")
            lo, hi = map(float, times)
            if any(on_grid(t, dt) is None for t in (lo, hi)):
                raise ConfigError(
                    f"{LAW_ID}: producer {source}'s window {label} is {ON_THE_GRID} at both ends"
                )
            if not last <= lo < hi <= end or label in {w for w, _, _ in windows}:
                raise ConfigError(
                    f"{LAW_ID}: producer {source}'s windows are distinct, inside the horizon, "
                    "increasing and disjoint"
                )
            windows.append((label, lo, hi))
            last = hi
        out.append((source, tuple(windows)))
    return tuple(out)


class Unbatched:
    """A batch signature's part equal to nothing, itself included (amendment G's batch limit);
    a fresh one per signature."""

    def __eq__(self, other):
        return False

    def __hash__(self):
        return 0

    def __repr__(self):
        return "Unbatched()"


def producer_label(cell, generation, source, window=None):
    """Amendment G's producer label: <cell>-g<k>-<chain>, and <cell>-g<k>-<chain>-<window> inside
    a declared window (a contract convention: the requester's triple, cell, generation, chain)."""
    name = f"{cell}-g{generation}-{source}"
    return name if window is None else f"{name}-{window}"


def _producer_changes(cell, source, births, windows, end):
    """One producer source's schedule: each generation's label from its birth (an event's step),
    its window label inside each window, and the next generation's from the next birth."""
    points = sorted({0.0, *births, *(t for _, lo, hi in windows for t in (lo, hi) if t <= end)})
    changes = []
    for time in points:
        generation = max(k for k, birth in enumerate(births) if birth <= time)
        window = next((w for w, lo, hi in windows if lo <= time < hi), None)
        label = producer_label(cell, generation, source, window)
        if not changes or changes[-1][1] != label:
            changes.append((time, label))
    return tuple(changes)


def derived(spec, declaration):
    """Amendment G (TEMPLATED_POLYMERISATION_LAWS §9.20, option (a); D307), host side, at the
    definition: (the declaration with each species' producer labels after its own labels, the
    producer sources' schedules (((species, source), changes), ...)); the declaration itself and ()
    where no species names a producer. For each producer source, its chain's cell (a source
    reporter's label_sources) and that cell's occupants (replacement@1's events through
    species_common.occupants, keyed by cell ID: the founder is generation 0, then each newcomer in
    event order). Its labels: each generation's, then its windows', in declared order, so they
    depend on neither the cells' order nor a restart. Its schedule, for the species the source's
    own new material joins: the generation's label from its birth, its window label inside each
    window, the next generation's from the next event's step."""
    if not any(s.producers for s in declaration.species):
        return declaration, ()
    from cells.operators.species_common import occupants

    sources = reporters(spec, "LABEL_SOURCES")
    declared = [entry for op, d in sources for entry in op.label_sources(d)]
    cells = {source: cell for source, _, cell in declared}
    own = {(name, source) for source, name, _ in declared}
    lives, end = occupants(spec), spec.experiment.end_time
    species, schedules = [], []
    for s in declaration.species:
        labels = list(s.labels)
        for source, windows in s.producers:
            cell = cells.get(source)
            if cell not in lives:
                raise ConfigError(
                    f"{LAW_ID}: {s.id}'s producer {source} is no source reporter's chain at a cell "
                    "(label_sources)"
                )
            births = [life.birth for life in lives[cell]]
            for generation in range(len(births)):
                labels.append(producer_label(cell, generation, source))
                labels += [producer_label(cell, generation, source, w) for w, _, _ in windows]
            if (s.id, source) in own:
                changes = _producer_changes(cell, source, births, windows, end)
                schedules.append(((s.id, source), changes))
        if len(labels) > MAX_LABELS or len(set(labels)) != len(labels):
            raise ConfigError(
                f"{LAW_ID}: {s.id}'s labels with its producers' are at most {MAX_LABELS} and "
                f"distinct ({len(labels)}): generations times (windows + 1), plus its own"
            )
        species.append(replace(s, labels=tuple(labels)))
    return replace(declaration, species=tuple(species)), tuple(sorted(schedules))


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
                **(
                    dict(
                        producers=[
                            dict(
                                source=source,
                                windows=[
                                    {"label": w, "from": lo, "to": hi} for w, lo, hi in windows
                                ],
                            )
                            for source, windows in s.producers
                        ]
                    )
                    if s.producers
                    else {}
                ),
            )
            for s in declaration.species
        ],
    )


def parse_arrivals(raw, base, declaration):
    """(((species, source), ((time, label), ...)), ...), sorted, from the label_arrivals list
    (module docstring): source "" for a species' own schedule, or a reporter's source ID (D296);
    nested tuples, so the definition stays hashable. A source's existence is checked with the
    composition (check_labels)."""
    if type(raw) is not list:
        raise ConfigError(f"{SCHEDULE_KEY} requires an explicit list")
    by_id = {s.id: s for s in declaration.species}
    dt, end = base.execution.dt, base.experiment.end_time
    producers = {source for s in declaration.species for source, _ in s.producers}
    schedules = {}
    for entry in raw:
        keys = {"species", "source", "schedule"} if "source" in entry else {"species", "schedule"}
        _fields(entry, keys, f"{SCHEDULE_KEY} entry")
        species = by_id.get(entry["species"])
        if species is None:
            raise ConfigError(f"{SCHEDULE_KEY} names a species not labelled: {entry['species']!r}")
        source = identifier(entry["source"]) if "source" in entry else ""
        if source in producers:  # Amendment G: one authority, the replacement events.
            raise ConfigError(
                f"{LAW_ID}: {SCHEDULE_KEY} gives source {source}'s schedule by hand, and {source} "
                "is a producer source, whose schedule the owner derives from replacement@1's "
                "occupants (amendment G)"
            )
        if (species.id, source) in schedules:
            raise ConfigError(
                f"{LAW_ID}: one arrival schedule per species and source ({species.id} {source})"
            )
        if type(entry["schedule"]) is not list or not entry["schedule"]:
            raise ConfigError(f"{LAW_ID}: {species.id}'s arrival schedule lists its changes")
        changes = []
        for change in entry["schedule"]:
            _fields(change, {"time", "label"}, f"{SCHEDULE_KEY} change")
            time, label = change["time"], change["label"]
            if type(time) not in (int, float) or not np.isfinite(time):
                raise ConfigError(f"{SCHEDULE_KEY} requires a finite time")
            time = float(time)
            if on_grid(time, dt) is None:
                raise ConfigError(
                    f"{LAW_ID}: a label switch must be {ON_THE_GRID} ({species.id} at {time!r})"
                )
            if not 0.0 <= time <= end:
                raise ConfigError(
                    f"{LAW_ID}: a label switch lies outside the horizon ({species.id} at {time!r})"
                )
            if label not in species.labels:
                raise ConfigError(f"{LAW_ID}: {species.id} has no label {label!r}")
            changes.append((time, label))
        times = [t for t, _ in changes]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ConfigError(f"{LAW_ID}: {species.id}'s switch times increase strictly")
        schedules[(species.id, source)] = tuple(changes)
    return tuple(sorted(schedules.items()))


def species_schedules(schedule):
    """{species: changes} of the species' own schedules."""
    return {name: changes for (name, source), changes in schedule if not source}


def arrival_index(changes, times):
    """[time] the position, among a species' labels, of the label in force at each step start of
    `times` (increasing), given its changes ((time, position), ...) in increasing time and the
    base (0) before the first. A change applies from the first step that starts at it or after it,
    a start at the same instant (clock_instants.same_instant) included: a window's start is its
    first step, and its end the first step it does not hold."""
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
        own = species_schedules(schedule).get(s.id, ())
        changes = tuple((t, s.labels.index(label)) for t, label in own)
        out[np.arange(len(times)), j, arrival_index(changes, times)] = 1.0
    return out


def reporters(spec, flag):
    """(operator, declaration) of the composition's reporters with `flag` (LABEL_SOURCES or
    LABEL_POOLS), in declared order: their positions are the owner's axes'."""
    return tuple(
        (op, declaration)
        for op, declaration, _ in composite_spec.entries(spec)
        if getattr(op, flag) and reports_labels(op)
    )


def source_controls(spec, declaration, schedule, times):
    """[time, source reporter, source, label] one-hot (D296): each declared source's label this
    step, its own schedule's where it has one, else its species' (and zeros for a source of an
    unlabelled species and for padding)."""
    labelled = {s.id: (j, s) for j, s in enumerate(declaration.species)}
    width = max(len(s.labels) for s in declaration.species)
    species = arrival_controls(declaration, schedule, times)
    owners = reporters(spec, "LABEL_SOURCES")
    sources = [op.label_sources(d) for op, d in owners]
    out = np.zeros((len(times), len(owners), max(map(len, sources), default=0), width))
    own = {key: changes for key, changes in schedule}
    for r, declared in enumerate(sources):
        for k, (source, name, _) in enumerate(declared):
            if name not in labelled:
                continue
            j, entry = labelled[name]
            if (name, source) not in own:
                out[:, r, k, :] = species[:, j, :]
                continue
            changes = tuple((t, entry.labels.index(label)) for t, label in own[(name, source)])
            out[np.arange(len(times)), r, k, arrival_index(changes, times)] = 1.0
    return out


def operator_errors(spec):
    """The fail-closed refusals of the composition's operators (module docstring), as messages:
    a split writer that reports nothing is refused in today's words unless it is admitted by
    species (BY_SPECIES, a declared ROW_MOVES, and no labelled species among its written rows),
    and beside one that is, by_species_errors' refusals by name."""
    errors, events = [], replacing(spec)
    labelled = labelled_species(spec)
    for op, declaration, _ in composite_spec.entries(spec):
        if op.LABEL_OWNER:
            continue
        if events and op.LABEL_POOLS and op.EVENT and not takes_labels(op.event):
            errors.append(
                f"{op.LAW_ID} beside {LAW_ID} and a replacing event: its event may empty its label "
                "pools without reporting what it removed (erratum E: an event that empties them "
                "takes labels= and reports their amounts)"
            )
        replaces = set(AMOUNT_FIELDS) & {*op.EVENT_REPLACES, *op.STATE_RESETS}
        writes = set(AMOUNT_FIELDS) & set(op.ENTITY_WRITES) - replaces
        where = f"{op.LAW_ID} beside {LAW_ID}"
        kind_error = label_event_error(op)  # FR-44: no report is read as another kind's.
        if op.RETIRES or op.CLOSES:
            errors.append(f"{where}: it closes or retires slots ({NOT_PLANNED})")
        elif set(AMOUNT_VIEWS) & set(op.VIEW_FIELDS):
            errors.append(f"{where}: its view changes species amounts ({NOT_PLANNED})")
        elif kind_error:
            errors.append(f"{where}: {kind_error} (fail closed)")
        elif replaces and not (op.EVENT and takes_labels(op.event)):
            errors.append(f"{where}: its events write species amounts ({NOT_PLANNED})")
        elif writes and op.EVENT and not op.SPLIT and label_event(op) != EXCHANGED:
            errors.append(
                f"{where}: its events write species amounts and report neither replaced slots "
                f"nor a liquid exchange ({NOT_PLANNED})"
            )
        elif writes and op.SPLIT and not reports_labels(op):
            if op.LAW_ID not in BY_SPECIES or op.ROW_MOVES is None:  # Today's words.
                errors.append(
                    f"{where}: it writes species amounts without reporting its one-way moves "
                    f"({NOT_PLANNED})"
                )
                continue
            written = sorted({name for name, _ in op.written_rows(spec, declaration)} & labelled)
            if written:
                errors.append(
                    f"{where}: it writes species amounts without reporting its one-way moves, and "
                    f"it writes the labelled {', '.join(written)}: {LABELLED_ROW} (admission by "
                    "species admits only a writer of unlabelled rows; a labelled ligand waits for "
                    "sites as label reporters, D327)"
                )
    return errors + by_species_errors(spec)


def by_species_writers(spec):
    """(operator, declaration) of the composition's split writers on BY_SPECIES that declare their
    rows (ROW_MOVES), in declared order. Beside the owner each is admitted by species unless it
    writes a labelled species, which operator_errors refuses."""
    return tuple(
        (op, declaration)
        for op, declaration, _ in composite_spec.entries(spec)
        if op.LAW_ID in BY_SPECIES and op.ROW_MOVES is not None
    )


def inner_options(spec):
    """((declared, what), ...): the inner model's later options that a writer admitted by species
    is refused beside. These are the same five as FR-45's list beside site sets
    (site_occupancy.check_set_composition)."""
    from cells.numerics.surface_field import SPARSE_SOLVER_ID

    m = spec.model
    channels = getattr(m, "channels", ())
    return (
        (
            bool(getattr(m, "one_way_records", ())),
            "cells.model.resolved_pump_tissue@3's own one_way records (FR-50 phase 2)",
        ),
        (
            any(getattr(c, "block", None) is not None for c in channels),
            "a blocked channel population (FR-51)",
        ),
        (
            any(getattr(c, "voltage_shift", None) is not None for c in channels),
            "a declared voltage shift (FR-64)",
        ),
        (spec.execution.field_solver == SPARSE_SOLVER_ID, f"the field solver {SPARSE_SOLVER_ID}"),
        (getattr(spec, "energy_check", None) is not None, "execution.energy_check (X2, D224)"),
    )


def option_errors(spec, writers):
    """The inner model's declared later options beside the writers admitted by species, named
    in one message, or none."""
    if not writers:
        return []
    options = [what for declared, what in inner_options(spec) if declared]
    if not options:
        return []
    names = ", ".join(op.LAW_ID for op, _ in writers)
    return [
        f"{', '.join(options)} beside {LAW_ID} and {names} admitted by species: {OPTION}; "
        "refused until a world qualifies each beside them (D327)"
    ]


def by_species_errors(spec):
    """FR-44 step 3's refusals by name beside a writer admitted by species (module docstring;
    D327, D424), as messages, none without such a writer:
    - every operator law in none of the writer's qualified sets, all named in one message
      (NOT_A_PARTNER, today's words);
    - laws each in some set, but in no one set together (NOT_TOGETHER), C4's set counting only
      where its anchor, the compartments, is declared;
    - each partner's variant not yet qualified (PARTNER_VARIANT: expression's exports and outside
      degradations);
    - a channel population where no set that admits the composition qualified one (CHANNEL: beside
      C4's set);
    - each of the writer's variants not yet qualified (an internalising population, and one
      facing a cell);
    - the inner model's later options (option_errors)."""
    writers = by_species_writers(spec)
    if not writers:
        return []
    entries = composite_spec.entries(spec)
    laws = tuple(dict.fromkeys(op.LAW_ID for op, _, _ in entries))
    errors = []
    for op, declaration in writers:
        entry = BY_SPECIES[op.LAW_ID]
        others = [law for law in laws if law not in (LAW_ID, op.LAW_ID)]
        outside = [law for law in others if law not in entry.partners]
        where = f"beside {LAW_ID} and {op.LAW_ID} admitted by species"
        if outside:
            errors.append(
                f"{', '.join(outside)} {where}: {NOT_A_PARTNER}; version 1 admits beside both only "
                f"a subset of one qualified set: {entry.described()}, each with its own check "
                "(D327)"
            )
        elif not entry.together(others, laws):
            errors.append(
                f"{', '.join(others)} {where}: {NOT_TOGETHER}; version 1 admits beside both only a "
                f"subset of one qualified set: {entry.described()} (D327)"
            )
        else:
            admitting = [q for q in entry.sets if q.admits(others, laws)]
            channels = tuple(c.id for c in getattr(spec.model, "channels", ()) or ())
            if channels and not any(q.channels for q in admitting):
                names = " and ".join(f"{q.name}'s" for q in admitting)
                errors.append(
                    f"{', '.join(channels)} {where}: {CHANNEL}; {names} check qualifies its set "
                    "with no channel population, so one is refused until a world qualifies it "
                    "(D327)"
                )
        for law, what, find in entry.partner_variants:
            for partner, partner_declaration, _ in entries:
                found = find(partner_declaration) if partner.LAW_ID == law else ()
                if found:
                    errors.append(
                        f"{law} {where}: {PARTNER_VARIANT}: {what} ({', '.join(found)}); refused "
                        "until a world qualifies it (D327)"
                    )
        for what, find in entry.unqualified:
            found = find(declaration)
            if found:
                errors.append(
                    f"{op.LAW_ID} beside {LAW_ID}: {UNQUALIFIED}: {what} ({', '.join(found)}); "
                    "refused until a world qualifies it (D424)"
                )
    return errors + option_errors(spec, writers)


def in_step_errors(spec, declaration, reports):
    """Stage 2's refusals of a labelled species moved inside the inner step, and the kinds hook's
    (D303 item 6), as messages. reports: the inner step reports its one-way transfers (it takes
    labels=; the composition's inner_reports_labels). Where it does, an uncharged face, the
    membrane and junction routes (REPORTED_MOVERS) and a declared kind's moves through its hook
    (label_transfers) are followed, except under RK4; every other in-step mover is refused: a
    charged face (no one-way form), a channel or a pump (no FR-42 stage plans them yet), a kind
    without the hook and an operator's in-step process. Without a reporting inner step (one that
    takes no labels), every in-step mover is refused. Besides: each declared kind's own refusals
    (kind_registry.label_refusal_errors: its label_refusals, and a kind with a rates hook and none
    refused while any row is labelled), and a labelled row a closure holds (closure_errors)."""
    m, inner = species_registry.inner_movers(spec)
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    moved = species_registry.moved_in_step(spec)
    rk4 = spec.execution.solver == "rk4"
    kinds = kind_registry.declared_kinds(getattr(m, "kinds", ()))
    hooked = {kind_id for kind_id, kind, _ in kinds if kind.label_transfers is not None}
    errors = []
    for s in declaration.species:
        followed, refused = [], []
        for mover, law, entities in inner.get(s.id, ()):
            ok = mover in hooked or (
                REPORTED_MOVERS.get(mover) == law and (mover != "face" or valence[s.id] == 0)
            )
            (followed if reports and ok else refused).append(f"{mover} {', '.join(entities)}")
        names = [*moved[s.id]["cell"], *moved[s.id]["outside"]]
        refused += list(dict.fromkeys(n for n in names if n.endswith("(its in-step process)")))
        if refused:
            later = (
                "a charged face has no one-way form, channels, pumps and in-step processes "
                "wait for a later stage, and a kind reports only through its hook "
                "(label_transfers)"
                if reports
                else "this composition's inner step reports none: its step takes no labels"
            )
            errors.append(
                f"{LAW_ID}: {s.id} is moved inside the inner step by {', '.join(refused)}, "
                f"which do not report one-way moves ({later})"
            )
        if followed and rk4:
            errors.append(
                f"{LAW_ID}: {s.id} is moved inside the inner step by {', '.join(followed)}, and "
                "version 1 follows labels through the IMEX step only, not RK4 (FR-42)"
            )
    species = tuple(s.id for s in declaration.species)
    errors += [
        f"{LAW_ID}: {reason}"
        for reason in kind_registry.label_refusal_errors(getattr(m, "kinds", ()), species)
    ]
    return errors + closure_errors(kinds, declaration)


def closure_errors(kinds, declaration):
    """D303 item 6, centrally: a labelled species that a closure holds at some node (a declared
    kind's stage read, its stage_rows: B4's proton row and buffers at their buffered nodes,
    cells.binding.rapid_binding@1's closure rows) is refused, whatever moves it. Its stored row is the closure's
    total, which the read splits between forms for the rates, so no mover's one-way terms are the
    stored row's. kinds: kind_registry.declared_kinds of the inner model."""
    held = {}
    for kind_id, kind, kind_declaration in kinds:
        if kind.stage_rows is not None:
            for row in kind.stage_rows(kind_declaration):
                held.setdefault(row[0], {}).setdefault(kind_id, []).append(row[1])
    return [
        f"{LAW_ID}: {s.id} is held by {kind_id}'s closure at {', '.join(dict.fromkeys(nodes))} "
        "(its stored row is the closure's total, which the stage read splits between forms), and "
        "labels do not follow a closure's rows"
        for s in declaration.species
        for kind_id, nodes in held.get(s.id, {}).items()
    ]


def check_labels(spec, declaration, model=None):
    """The definition's refusals (module docstring); model: the composition (its inner step's
    reporting decides stage 2's admission)."""
    reports = bool(getattr(model, "inner_reports_labels", False))
    derived(spec, declaration)  # Amendment G's refusals: an unknown producer, MAX_LABELS.
    errors = in_step_errors(spec, declaration, reports) + operator_errors(spec)
    errors += source_errors(spec, schedule_of(spec))
    if errors:
        raise ConfigError("; ".join(errors))


def schedule_of(spec):
    """The owner's parsed schedule in a composition."""
    return next(schedule for op, _, schedule in composite_spec.entries(spec) if op.LABEL_OWNER)


def source_errors(spec, schedule):
    """D296: each source a schedule names is a source reporter's, of the species it names."""
    declared = {
        (name, source)
        for op, d in reporters(spec, "LABEL_SOURCES")
        for source, name, _ in op.label_sources(d)
    }
    return [
        f"{LAW_ID}: label_arrivals names source {source!r} of {name}, which no reporter declares "
        "(label_sources)"
        for (name, source), _ in schedule
        if source and (name, source) not in declared
    ]


def labelled_species(spec):
    """The species a composition's label owner labels (a frozenset; empty without one): for a
    reporter's own refusals of the cases it does not report."""
    return frozenset(
        s.id
        for op, declaration, _ in composite_spec.entries(spec)
        if op.LABEL_OWNER
        for s in declaration.species
    )


def replacing(spec):
    """Whether the composition declares an event that replaces slots' amounts and reports the
    slots (D296: replacement@1), static: the records of what leaves at an event exist only then,
    zero-size elsewhere, so every other labelled world keeps its fields (D148 case 2)."""
    return any(
        op.EVENT
        and takes_labels(op.event)
        and set(AMOUNT_FIELDS) & {*op.EVENT_REPLACES, *op.STATE_RESETS}
        for op, _, _ in composite_spec.entries(spec)
    )


def exchanging(spec):
    """Whether the composition declares an event that exchanges liquid and reports it (FR-44: the
    compartment wash), static: the record of what left at an exchange exists only then, zero-size
    elsewhere, so every other labelled world keeps its fields (D148 case 2)."""
    return any(label_event(op) == EXCHANGED for op, _, _ in composite_spec.entries(spec))


def bind(spec, declaration):
    declaration = derived(spec, declaration)[0]  # Amendment G: the producers' labels too.
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
    pools = [op.label_pools(d) for op, d in reporters(spec, "LABEL_POOLS")]
    position = {s.id: j for j, s in enumerate(declaration.species)}
    size = max(map(len, pools), default=0)
    pool_rows = np.full((len(pools), size), -1, dtype=np.int64)
    pool_cells = np.full((len(pools), size), -1, dtype=np.int64)
    cell_ids = [c.id for c in m.cells]
    pool_present = np.zeros((len(pools), width, size), dtype=bool)
    pool_present[:, 0, :] = True  # An unlabelled species' entry, or padding: the base alone.
    for r, entries in enumerate(pools):
        for k, (_, name, cell) in enumerate(entries):
            if cell in cell_ids:
                pool_cells[r, k] = cell_ids.index(cell)
            if name in position:
                pool_rows[r, k] = position[name]
                pool_present[r, :, k] = present[position[name]]
    pool_share = np.zeros((len(pools), width, size))
    pool_share[:, 0, :] = 1.0  # A pool's material starts unlabelled.
    layout = dict(
        label_rows=np.asarray([species.index(s.id) for s in declaration.species], dtype=np.int64),
        label_present=present,
        label_pool_rows=pool_rows,
        label_pool_present=pool_present,
        label_pool_cells=pool_cells,
    )
    events = replacing(spec)  # Static: the records' first axes (erratum E).
    exchanges = exchanging(spec)  # FR-44, likewise.
    state = dict(
        label_share=share,
        label_outside_share=outside_share,
        label_closure_relative=np.zeros(count),
        label_pool_share=pool_share,
        label_removed_fmol=np.zeros((count if events else 0, width, x.capacity)),
        label_pool_removed_fmol=np.zeros((len(pools) if events else 0, width, size)),
        label_outside_removed_fmol=np.zeros(
            (count if exchanges else 0, width, x.extracellular_capacity)
        ),
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


def _all_nodes(values, p, *, xp):
    """values [..., node], padded with zeros at the outside nodes when a reporter at cells only
    gives its cells alone (the contract)."""
    cells, nodes = p.active.shape[0], p.outside_active.shape[0]
    if values.shape[-1] == cells and nodes:
        return xp.concatenate((values, xp.zeros(values.shape[:-1] + (nodes,))), axis=-1)
    return values


def advance(start, end, moves, p, *, xp=jnp, pool=None):
    """end with the label shares advanced by one reporter's applied half-step from start, given
    its moves (out [m, node], into [m, label, node], transfers): label_shares.advance at the cells
    and the outside nodes, and the closure diagnostic's running maximum. The node axis is the cells
    then the outside nodes, or the cells alone (contract). A pool reporter (LABEL_POOLS; pool: its
    position among them) gives a fourth part, its pools' (advance_pools)."""
    if pool is not None:
        return advance_pools(start, end, moves, p, pool, xp=xp)
    out, into, transfers = moves
    out, into = _all_nodes(out, p, xp=xp), _all_nodes(into, p, xp=xp)
    if transfers:  # Static: a reporter that moves material between nodes (exchange's routes).
        return advance_nodes(start, end, out, into, transfers, p, xp=xp)
    cells = p.active.shape[0]
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


def _sites(rows, pools, *, xp):
    """[label, site]: the rows' [m, label, node] as sites j N + k, then the pools' [label, P]."""
    m, width, nodes = rows.shape
    flat = xp.reshape(xp.transpose(rows, (1, 0, 2)), (width, m * nodes))
    return xp.concatenate((flat, pools), axis=1)


def advance_pools(start, end, moves, p, pool, *, xp=jnp):
    """advance() for a pool reporter (D296), at its position `pool` among them: its rows and its
    pools advanced together as sites (label_shares.advance_transfers: carried material arrives
    with its source's shares, predictor-corrector), and the closure diagnostic over both."""
    out, into, transfers, (n0p, n1p, intop, outp, (amount, source, destination)) = moves
    if transfers:
        raise ConfigError(f"{LAW_ID}: a reporter's transfers are its pools' carried part (D296)")
    cells, size = p.active.shape[0], n0p.shape[0]
    out, into = _all_nodes(out, p, xp=xp), _all_nodes(into, p, xp=xp)
    m, width = p.label_present.shape
    nodes = out.shape[-1]
    c0, o0, ci0, oi0 = amounts(start, p, xp=xp)
    c1, o1, ci1, oi1 = amounts(end, p, xp=xp)
    n0 = xp.concatenate((xp.reshape(xp.concatenate((c0, o0), axis=1), (-1,)), n0p))[None]
    n1 = xp.concatenate((xp.reshape(xp.concatenate((c1, o1), axis=1), (-1,)), n1p))[None]
    rows = xp.concatenate((start.label_share, start.label_outside_share), axis=2)
    shares = _sites(rows, start.label_pool_share[pool, :, :size], xp=xp)[None]
    present = xp.broadcast_to(p.label_present[:, :, None], (m, width, nodes))
    present = _sites(present, p.label_pool_present[pool, :, :size], xp=xp)[None]
    fixed = _sites(into, xp.transpose(intop), xp=xp)[None]
    held = xp.concatenate(
        (xp.tile(xp.concatenate((xp.zeros_like(p.active), p.reservoir)), m), xp.zeros(size, bool))
    )
    carried = ((amount[None, :], source, destination),) if amount.shape[0] else ()
    new = label_shares.advance_transfers(shares, n0, n1, carried, present, held, xp=xp, into=fixed)[
        0
    ]
    arriving, leaving = label_shares.carried(shares, carried, xp=xp)
    lost = xp.concatenate((xp.reshape(out, (-1,)), outp))[None] + leaving
    residual = label_shares.closure_residual(n0, n1, fixed + arriving, lost, xp=xp)[0]
    scale = (n0 + n1 + entity_sum(fixed + arriving, axis=1, xp=xp) + lost)[0]
    increments = xp.concatenate((ci0 + ci1, oi0 + oi1), axis=1)
    scale = scale + xp.concatenate((xp.reshape(increments, (-1,)), xp.zeros(size)))
    live = xp.concatenate(
        (xp.tile(xp.concatenate((p.active, p.outside_active & ~p.reservoir)), m), n0p >= 0)
    )
    relative = xp.where(live, residual / xp.where(scale > 0, scale, 1.0), 0.0)
    worst = xp.max(xp.reshape(relative[: m * nodes], (m, nodes)), axis=1, initial=0.0)
    owner = p.label_pool_rows[pool, :size][None, :] == xp.arange(m)[:, None]  # [m, P]
    worst = xp.maximum(
        worst, xp.max(xp.where(owner, relative[m * nodes :][None, :], 0.0), axis=1, initial=0.0)
    )
    rows_new = xp.transpose(xp.reshape(new[:, : m * nodes], (width, m, nodes)), (1, 0, 2))
    pools_new = new[:, m * nodes :]
    if xp is jnp:
        pool_share = start.label_pool_share.at[pool, :, :size].set(pools_new)
    else:
        pool_share = np.array(start.label_pool_share, copy=True)
        pool_share[pool, :, :size] = pools_new
    return end._replace(
        label_share=rows_new[:, :, :cells],
        label_outside_share=rows_new[:, :, cells:],
        label_closure_relative=xp.maximum(start.label_closure_relative, worst),
        label_pool_share=pool_share,
    )


def _set_pool(values, pool, size, new, *, xp):
    """values [pool owner, label, pool] with its pool reporter `pool`'s first `size` entries
    replaced by new [label, size] (a copy in NumPy)."""
    if xp is jnp:
        return values.at[pool, :, :size].set(new)
    out = np.array(values, copy=True)
    out[pool, :, :size] = new
    return out


def advance_event(before, end, report, control, p, *, kind, xp=jnp, pool=None):
    """end after an event that reports what it moved, its report read by the event's kind
    (contract.label_event; D296; erratum E, TEMPLATED_POLYMERISATION_LAWS §9.18; FR-44), never by
    its shape. Each event reports only its own material, so reporting events commute. What leaves
    is recorded by label: its amount before the event times its shares just before it, in the
    cumulative records (zero-size where no event of the kind is declared: `replacing`,
    `exchanging`).
    - "replaced" (pool None): report is replaced [cell], the slots whose rows the event swapped
      (replacement@1). Every labelled row there leaves whole, into label_removed_fmol [m, label,
      cell], and its shares become the label in force for its species this step, the newcomer's:
      the template's material is newcomer material, a donor copy's included.
    - "emptied" (pool k, the reporter's position among the pool reporters): report is removed [P]
      >= 0, the amounts its event emptied from its pool entries (its label_pools, in order), into
      label_pool_removed_fmol[k]. An entry it emptied (removed > 0) takes the base label: it holds
      no material, so no later share depends on it, and its next arrivals set its shares.
    - "exchanged" (pool None): report is a LiquidExchange [m, outside node] (advance_exchange)."""
    if kind not in LABEL_EVENT_KINDS:  # Fail closed: no report is read as another kind's.
        raise ValueError(f"{LAW_ID}: an event's report kind is one of {LABEL_EVENT_KINDS}")
    if (kind == EMPTIED) != (pool is not None):
        raise ValueError(f"{LAW_ID}: an emptied report names its pool reporter, and no other does")
    if kind == EXCHANGED:
        return advance_exchange(before, end, report, p, xp=xp)
    if pool is None:
        replaced = report
        newcomer = control.label_arrival[:, :, None]  # [m, label, 1] one-hot.
        out = end._replace(label_share=xp.where(replaced[None, None, :], newcomer, end.label_share))
        if not before.label_removed_fmol.shape[0]:  # Static: no replacing event declared.
            return out
        rows = xp.where(replaced[None, :], amounts(before, p, xp=xp)[0], 0.0)  # [m, cell]
        leaving = rows[:, None, :] * before.label_share
        return out._replace(label_removed_fmol=end.label_removed_fmol + leaving)
    removed = report  # [P]
    size = removed.shape[0]
    shares = before.label_pool_share[pool, :, :size]  # [label, P] just before the event.
    base = (xp.arange(shares.shape[0]) == 0).astype(shares.dtype)[:, None]  # The base label.
    emptied = xp.where((removed > 0)[None, :], base, end.label_pool_share[pool, :, :size])
    out = end._replace(label_pool_share=_set_pool(end.label_pool_share, pool, size, emptied, xp=xp))
    if not before.label_pool_removed_fmol.shape[0]:  # Static: no replacing event declared.
        return out
    record = end.label_pool_removed_fmol[pool, :, :size] + removed[None, :] * shares
    return out._replace(
        label_pool_removed_fmol=_set_pool(end.label_pool_removed_fmol, pool, size, record, xp=xp)
    )


def advance_exchange(before, end, report, p, *, xp=jnp):
    """end after a liquid exchange at the outside nodes (FR-44; module docstring), from its
    LiquidExchange report [m, outside node].
    - The sample (removed) leaves with each node's shares just before the event, recorded by label
      in label_outside_removed_fmol [m, label, outside node].
    - The buffer (supplied) joins the base, whatever window is open (label_shares.exchange).
    - Where nothing is exchanged the shares and the record keep their bits, and cells' shares are
      never touched."""
    if not isinstance(report, LiquidExchange):
        raise ValueError(f"{LAW_ID}: an exchanged report is a LiquidExchange (operators/contract)")
    removed, supplied = report
    shares = before.label_outside_share  # [m, label, outside node] just before the event.
    n0 = amounts(before, p, xp=xp)[1]  # [m, outside node], the rows the sample was taken from.
    new = label_shares.exchange(shares, n0, removed, supplied, p.label_present, xp=xp)
    record = end.label_outside_removed_fmol + removed[:, None, :] * shares
    return end._replace(label_outside_share=new, label_outside_removed_fmol=record)


def advance_inner(start, end, transfers, p, *, xp=jnp):
    """end with the label shares advanced over the inner step's transport (FR-42's stage 2), from
    its transfers ((amount [m, entity], source [entity], destination [entity]), ..., nodes on the
    combined axis, cells then outside nodes): advance_nodes with no other move."""
    return advance_nodes(start, end, 0.0, 0.0, transfers, p, xp=xp)


def advance_nodes(start, end, out, into, transfers, p, *, xp=jnp):
    """end with the label shares advanced over one application with transfers between nodes:
    label_shares.advance_transfers on the combined node axis (out [m, node] and into [m, label,
    node] its other one-way moves, 0 for none; held baths kept), and the closure diagnostic's
    running maximum."""
    cells = p.active.shape[0]
    c0, o0, ci0, oi0 = amounts(start, p, xp=xp)
    c1, o1, ci1, oi1 = amounts(end, p, xp=xp)
    n0, n1 = xp.concatenate((c0, o0), axis=1), xp.concatenate((c1, o1), axis=1)
    shares = xp.concatenate((start.label_share, start.label_outside_share), axis=2)
    held = xp.concatenate((xp.zeros_like(p.active), p.reservoir))
    fixed = into + xp.zeros_like(shares)
    new = label_shares.advance_transfers(
        shares, n0, n1, transfers, p.label_present, held, xp=xp, into=fixed
    )
    arriving, leaving = label_shares.carried(shares, transfers, xp=xp)
    into, out = fixed + arriving, out + leaving
    residual = label_shares.closure_residual(n0, n1, into, out, xp=xp)
    scale = n0 + n1 + entity_sum(into, axis=1, xp=xp) + out
    scale = scale + xp.concatenate((ci0 + ci1, oi0 + oi1), axis=1)
    live = xp.concatenate((p.active, p.outside_active & ~p.reservoir))
    relative = xp.where(live[None, :], residual / xp.where(scale > 0, scale, 1.0), 0.0)
    worst = xp.maximum(start.label_closure_relative, xp.max(relative, axis=1, initial=0.0))
    return end._replace(
        label_share=new[:, :, :cells],
        label_outside_share=new[:, :, cells:],
        label_closure_relative=worst,
    )


def labels_domain_valid(state, p, *, xp):
    """The shares' domain (label_shares.domain_valid) at every node, and the diagnostic and the
    records of what left at events (erratum E) finite and non-negative."""
    present = p.label_present
    closure = state.label_closure_relative
    valid = (
        label_shares.domain_valid(state.label_share, present, xp=xp)
        & label_shares.domain_valid(state.label_outside_share, present, xp=xp)
        & label_shares.domain_valid(state.label_pool_share, p.label_pool_present, xp=xp)
        & xp.all(xp.isfinite(closure) & (closure >= 0))
    )
    for record in (
        state.label_removed_fmol,
        state.label_pool_removed_fmol,
        state.label_outside_removed_fmol,
    ):
        if record.shape[0]:  # Static: present beside a replacing or an exchanging event alone.
            valid = valid & xp.all(xp.isfinite(record) & (record >= 0))
    return valid


# ------------------------------------------------------------------ the operator


class NeutralArrivalLabels(Operator):
    LAW_ID = LAW_ID
    LABEL_OWNER = True
    IDENTITY_ROLE = "user"  # It labels species others declare.
    STATE_AXES = STATE_AXES
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("label_arrival", "label_source_arrival")
    EXPERIMENT_KEYS = (SCHEDULE_KEY,)
    VIEW_LAYERS = (
        {"id": "labels", "label": "Neutral arrival labels", "representation": "simulated"},
    )
    UNITS = {
        "label_share": "1",
        "label_outside_share": "1",
        "label_closure_relative": "1",
        "label_pool_share": "1",
        "label_removed_fmol": "fmol",
        "label_pool_removed_fmol": "fmol",
        "label_outside_removed_fmol": "fmol",
    }
    RECORD_KINDS = {
        "label_share": "level",
        "label_outside_share": "level",
        "label_closure_relative": "level",
        "label_pool_share": "level",
        "label_removed_fmol": "cumulative",
        "label_pool_removed_fmol": "cumulative",
        "label_outside_removed_fmol": "cumulative",
    }
    RECORD_DIAGNOSTICS = ("label_closure_relative",)

    def view_sets(self, spec, declaration):
        """The run view's sets of its axes: the labelled species; the label positions (each
        species' labels in declared order, the base first; padding past its own); the pool
        reporters; their pool positions (each reporter's label_pools in order); and the records'
        first axes, the labelled species and the pool reporters again where a replacing event is
        declared (erratum E), and the labelled species where an exchanging one is (FR-44), empty
        elsewhere. A species' labels include its producers' (amendment G)."""
        declaration = derived(spec, declaration)[0]
        width = max(len(s.labels) for s in declaration.species)
        owners = reporters(spec, "LABEL_POOLS")
        pools = {op.LAW_ID: [entry[0] for entry in op.label_pools(d)] for op, d in owners}
        size = max(map(len, pools.values()), default=0)
        events = replacing(spec)
        removed = tuple(s.id for s in declaration.species) if events else ()
        exchanged = tuple(s.id for s in declaration.species) if exchanging(spec) else ()
        return {
            "label_removed_species": {
                "id": "label_removed_species",
                "ids": removed,
                "holds": "labelled species, its departing material at replacement events recorded",
                "carries": removed,
            },
            "label_outside_removed_species": {
                "id": "label_outside_removed_species",
                "ids": exchanged,
                "holds": "labelled species, its material leaving outside nodes at liquid "
                "exchanges recorded",
                "carries": exchanged,
            },
            "label_removed_pool_owner": {
                "id": "label_removed_pool_owner",
                "ids": tuple(op.LAW_ID for op, _ in owners) if events else (),
                "holds": "pool reporter, the holds its events emptied recorded",
            },
            "label_pool_owner": {
                "id": "label_pool_owner",
                "ids": tuple(op.LAW_ID for op, _ in owners),
                "holds": "pool reporter",
            },
            "label_pool": {
                "id": "label_pool",
                "ids": tuple(f"pool_{k}" for k in range(size)),
                "holds": "pool position, each reporter's pools in declared order",
                "pools": pools,
            },
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
        """Each label switch, at its labelled species (the entry at time 0 sets the start), with
        its source where it names one, a producer source's derived schedule included (amendment
        G). It decides no cell's life, so there are no births or retirements."""
        schedule = (*schedule, *derived(spec, declaration)[1])
        layer = self.VIEW_LAYERS[0]["id"]
        events = [
            dict(
                time=float(t),
                kind="label switch",
                layer=layer,
                at={"label_species": name},
                label=f"{name}: arrivals join {label}" + (f" from {source}" if source else ""),
            )
            for (name, source), changes in schedule
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
                dict(
                    species=name,
                    **({"source": source} if source else {}),
                    schedule=[dict(time=t, label=label) for t, label in changes],
                )
                for (name, source), changes in schedule
            ]
        }

    def schedule_times(self, schedule):
        return tuple(t for _, changes in schedule for t, _ in changes)

    def value_at(self, schedule, time):
        """Each schedule's label in force at `time` (None before its first change), by species
        and source."""
        out = []
        for key, changes in schedule:
            before = [label for t, label in changes if t <= time]
            out.append((key, before[-1] if before else None))
        return tuple(out)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        """The arrival controls, with amendment G's producer labels and their sources' derived
        schedules beside the declared ones (the same forms as a correct hand-written schedule)."""
        declaration, producers = derived(spec, declaration)
        return (
            arrival_controls(declaration, schedule, times),
            source_controls(spec, declaration, (*schedule, *producers), times),
        )

    def check_definition(self, spec, declaration, schedule, model):
        check_labels(spec, declaration, model)

    def batch_signature(self, declaration):
        """The labelled species and their label counts; IDs, shares and schedules are data. Where
        a species declares producers (amendment G) its label count follows its cells' replacement
        events, which a declaration does not hold, so version 1 batches such a definition with no
        other world: its signature holds a fresh part equal to nothing (Unbatched; a container's
        comparison checks identity first, so a shared one would match itself), which the batch's
        own check refuses ("matching model array axes"). Fail-closed: a batch of one runs."""
        parts = (LAW_ID, tuple((s.id, len(s.labels)) for s in declaration.species))
        return parts + ((Unbatched(),) if any(s.producers for s in declaration.species) else ())

    def working_size(self, spec):
        (declaration,) = (d for op, d, _ in composite_spec.entries(spec) if op.LAW_ID == LAW_ID)
        declaration = derived(spec, declaration)[0]  # Amendment G: the producers' labels too.
        x = spec.execution
        width = max(len(s.labels) for s in declaration.species)
        nodes = x.capacity + x.extracellular_capacity
        if replacing(spec):  # Erratum E's record of the rows' departing material, per cell.
            nodes += x.capacity
        if exchanging(spec):  # FR-44's record of what left at liquid exchanges, per node.
            nodes += x.extracellular_capacity
        return 8 * 6 * len(declaration.species) * width * nodes

    def summary(self, spec, declaration, schedule, history):
        declaration, producers = derived(spec, declaration)  # Amendment G's labels, schedules.
        schedule = (*schedule, *producers)
        out = {
            "label_law": LAW_ID,
            "labelled_species": {
                s.id: dict(
                    labels=list(s.labels),
                    base=s.labels[0],
                    initial={node: dict(values) for node, values in s.initial},
                    arrivals=[
                        dict(time=t, label=label)
                        for t, label in species_schedules(schedule).get(s.id, ())
                    ],
                    source_arrivals={
                        source: [dict(time=t, label=label) for t, label in changes]
                        for (name, source), changes in schedule
                        if source and name == s.id
                    },
                )
                for s in declaration.species
            },
            "label_update": "shares of each physical row, advanced after each reporter's "
            "half-step from its one-way moves (numerics/label_shares.advance)",
        }
        if exchanging(spec):  # FR-44: only a world with an exchanging event says it.
            out["label_exchange"] = (
                "at each liquid exchange, the sample leaves with the node's shares and the buffer "
                "joins the base, whatever window is open (numerics/label_shares.exchange)"
            )
        return out

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        # FR-44 step 3 (D424): execution.energy_check is attached after the definition's checks
        # have run (energy_check_spec.parse_definition), so they never see it. Every run binds
        # here first, so a world with a writer admitted by species refuses X2 here, by name,
        # before its first step, as the site operator's sets do (SiteOccupancy.initial_values).
        # Only X2 is read here: the definition's checks have already refused every other option.
        if getattr(spec, "energy_check", None) is not None:
            errors = option_errors(spec, by_species_writers(spec))
            if errors:
                raise ConfigError("; ".join(errors))
        return bind(spec, declaration)

    # ------------------------------------------------------------ the composite's calls

    def labels(self, control, p, source=None):
        """A reporter's labels argument (contract): (the labelled rows, this step's arrival), and
        a source reporter's sources' arrivals (D296; source: its position among them)."""
        if source is None:
            return p.label_rows, control.label_arrival
        return p.label_rows, control.label_arrival, control.label_source_arrival[source]

    def advance(self, start, end, moves, p, *, xp, pool=None):
        return advance(start, end, moves, p, xp=xp, pool=pool)

    def rows(self, p):
        """The inner step's labels argument (FR-42's stage 2): the labelled rows."""
        return p.label_rows

    def advance_inner(self, start, end, transfers, p, *, xp):
        return advance_inner(start, end, transfers, p, xp=xp)

    def advance_event(self, before, end, report, control, p, *, kind, xp, pool=None):
        return advance_event(before, end, report, control, p, kind=kind, xp=xp, pool=pool)

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & labels_domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = labels_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own
