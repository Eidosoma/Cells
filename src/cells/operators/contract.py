"""The operator contract of the composite pump-tissue model (docs/CELL_DIVISION_DESIGN.md §3.3).

An operator is one law (with its version and parameters) that acts on an inner
model's state through declared parts and declared fields. The composite
(models/pump_composite.py) builds one implementation per ordered operator list
from these declarations at build time; each operator compiles to pure JAX
functions over arrays, so the hot loop stays array code (D142).

Declarations (class attributes):

* ``STATE_AXES``: owned state, written by this operator only; ``STATE_DTYPES``
  names non-float fields. ``HEAT_FIELDS`` and ``WORK_FIELDS`` declare which owned
  fields are booked as dissipation or work: the family's energy-flow sum reads
  every field ending in ``_dissipated_energy_pJ`` or ``_work_pJ`` by name, so no
  other owned field may carry those suffixes. ``ENERGY_ROLES`` ({owned state field:
  kind_registry.EnergyRole(role, monotone)}, the kinds' form; docs/CORE_SEAMS_DESIGN.md §6.1)
  declares a field's energy role, heat, work or stored, and whether it never decreases per
  element. An undeclared field of HEAT_FIELDS is heat and monotone, and one of WORK_FIELDS is
  work and not monotone (energy_roles), so today's programs stand. A declaration keeps both
  lists complete, since the run view and the declarations manifest read them: heat only on a
  field of HEAT_FIELDS, work only on one of WORK_FIELDS, and stored on a field of neither,
  without either suffix. The composite's dissipation check (non-negative and non-decreasing per
  element) takes monotone heat only, and its energy ledger's flows every heat and work field, so
  a non-monotone heat (GARD's event heat, closing against a state function) is booked but not
  held monotone. A stored field is a level, in neither.
* Entity writes, ``ENTITY_WRITES``: inner state fields it changes, each mapped to
  the owned accumulators that book the change, so the inner ledgers close with
  the operator's ledger terms (Δx = Σ over writers of their booked terms).
* View fields, ``VIEW_FIELDS``: inner layout fields it provides from state.
  Each field has exactly one provider; the composite refuses a second one.
  ``CONTROL_FACTORS``: inner control fields it multiplies; several factors on one
  field combine as a product in declared order. ``CONFLICTS_VIEW``: inner fields
  it reads as declared, so no other operator may provide them.
* Rate routes (B1′; docs/INVENTORY_COUPLING_DESIGN.md §2.1): ``ROUTABLE_CONTROLS`` ({own
  control field: "rate"}) names its rate controls that another operator's factor may multiply.
  They are read in its own exact half-steps only, so it has a split part kept split under RK4
  and no in-step process, and its scheduled rate is the maximum. ``RATE_ROUTES`` ((target law,
  target control field), ...) names the routable controls a source may route to. Its
  ``rate_factors`` gives each its factor and validity from the state the target's half-step
  receives, or None where the definition declares no route there (static, by layout shape);
  ``declared_rate_routes(declaration)`` names the routes a definition declares, and a target's
  ``routable_elements(declaration, field)`` names each element of a routable control with the
  cell its source is read in. The composite
  multiplies the target's field by its sources' factors in declared order, at the start of each
  of the target's two half-steps. A declared route's source precedes its target (refused at the
  definition otherwise), and a composition without a route source is unchanged. A factor
  operator's ``factor_valid`` holds its sources where the control view evaluates them, and a
  source's ``FACTOR_RECORD`` (an owned state field [route], with ``factor_record``) is filled by
  the composite with each route's factor where it is applied: at the control view, and at each
  routed half-step.
* The control view's reads (R2; docs/INVENTORY_COUPLING_DESIGN.md §2.1): a factor operator's
  current read at stage ``inner`` (``SCOPED_READS``) is a read at the control view, the state the
  inner step starts from, where its ``control_factors``, ``factor_valid`` and ``factor_record``
  are evaluated, so the contract admits that stage for a factor operator without an in-step
  process. The composite passes those three hooks ``view=``, a function of state giving its
  reader view of those fields (C4: the merged view's fields without the field refresh), only
  where such a read is declared (``factor_reads``; static), so every other call is unchanged; a
  factor operator that declares one takes ``view=None`` in each of those hooks it defines (a
  routed half-step's ``factor_record`` passes none).
* Readable quantities (R3, FR-24; docs/OPERATOR_FEATURES_FR23_24_26_DESIGN.md §3.3): an owner's
  ``QUANTITIES`` ({name: (entity axis, unit)}), each computed by its own ``quantities(state, p)``
  from its state, so its representation stays its own, with its entities' IDs and cells on each
  axis, host side (``quantity_entities``); a reader's ``QUANTITY_READS`` ({owner law:
  (names, ...)}), what it may read, and its ``declared_quantity_reads(declaration)``, what a
  definition reads: ((owner law, name, target law or None), ...), the target an operator target's
  route, whose half-steps evaluate the read, or None for a read at the control view. Where an
  owner it reads is in the composition, the composite passes a reader ``quantities=``, a function
  of state giving {owner law: {name: values}}, in its factor hooks at the control view
  (``control_factors``, ``factor_valid``, ``factor_record``) and in its routed ``rate_factors`` and
  ``factor_record``; elsewhere every call is unchanged, and nothing of the owner is traced unless
  the reader calls the function (static, by its own layout's shapes). The composite refuses a
  read of an undeclared quantity (structure), and at the definition a declared read whose owner
  the composition does not hold or whose owner follows the route's target (so both of the
  target's halves read the owner after its first half, symmetric about the target). It records
  the reads in the field map, only where a reader and its owner are both composed.
* Parts (kinds of §3.4), each optional: an event map at the start of the step
  leaving an event time (``EVENT``); a split process, half-steps around the inner
  step on its own variables (``SPLIT``); an in-step membrane process through the
  inner model's opt-in hook (``PROCESS``). One law may contribute several parts
  (scheduled replacement: its event map restarts its formation law's state). A
  state owner has no part: it holds entity state that later operators write
  (``ACCEPTS_WRITES``) and provides it through the view (membrane_entity_state);
  a part-less owner may instead own only fields that are accepted writes. A
  declaration (``DECLARATION_ONLY``, docs/CLOSED_COMPARTMENT_DESIGN.md §1.6) has
  no part and contributes nothing to the step: it declares entities and their
  refusals at the definition (``check_definition``, ``CONFLICTS_VIEW``,
  ``REQUIRES``) and its summary, and defines nothing else of the contract
  (``DECLARATION_MAY_DEFINE``, checked fail closed at registration): no field,
  schedule, view, factor, closure, ledger, readout, energy role, step method,
  schedule hook or definition-check hook of its own. Its ``SCOPED_READS`` may
  only be unscoped ``reference`` reads (the bound values as data, D217): it has
  no part to consume a view and no ``read_slots``, and a reference read
  constrains no changer of its field.
  ``RK4`` declares a split part's behaviour under an RK4 inner step: "coupled"
  (its rates join the coupled right-hand side, which RK4 integrates unsplit) or
  "split" (exact half-steps kept around the inner RK4 step).
* Ledgers: ``LEDGERS`` with ``LEDGER_DIAGNOSTICS`` and ``LEDGER_MESSAGE`` (its
  own ledgers and their rounding bounds), plus terms added to the inner ledgers
  and to their rounding magnitudes (methods below).
* Domain and refusal: ``domain_valid`` and ``control_valid``; any failure refuses
  the whole step, which returns the start state. ``REQUIRES``: laws that must
  precede it in the operator list. ``REQUIRES_KINDS``: the inner model's kinds
  (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)) whose fields it reads or writes, by
  kind ID; the composite refuses it where the definition does not declare one, and
  refuses a declared write or reset of a kind's field by an operator that does not
  require that kind (pump_composite.structure_errors). ``FIXED_INNER_FIELDS``: its
  parts build the inner model's state, layout or control with today's fixed fields
  (the inner module's own types), so the composite refuses it where the definition
  declares any kind. Beside a declared kind the composite also refuses an operator
  that opens, closes or retires slots (``CLOSES``, ``RETIRES`` or a provided activity
  mask): no closer resets a kind's per-slot fields, which would be left stale.
* Schedule: ``EXPERIMENT_KEYS`` (its schedule in the definition's experiment),
  parsed and checked at the definition (event times on the clock's grid, D283).
* Ownership (docs/PUMP_COMPOSITE_V2_DESIGN.md §1.2–§1.4), checked when a
  composition is built and recorded in its field map:
  - observation columns: its own are its state fields and ``READOUT_COLUMNS``;
    ``REPLACES`` ({column: reason}) names the inner or earlier operators' columns it
    computes instead. Replacement is a declared chain in operator order (water
    replaces the inner energy-balance rate, the symport then both energy columns),
    and the column's owner is the last in the chain. ``observe`` returns exactly its
    own and replaced columns;
  - ``VIEW_READS``: inner view fields it reads at their provided (current) value;
    an earlier operator must provide each;
  - ``ACCEPTS_WRITES`` ({owned field: its own ledgers}): fields a later operator may
    write (an ``ENTITY_WRITES`` target). The writer adds its booked terms to those
    ledgers and their rounding magnitudes (``external_ledger_terms``,
    ``external_magnitude_terms``); with no writer nothing changes;
  - ``EVENT_REPLACES`` ({field: (removed, supplied)}): fields its event map
    replaces, with the owned accumulators that book what was removed and supplied.
    Intensive fields set at events without a ledger are ``STATE_RESETS``;
  - ``ONSET_ANCHORED_VIEWS``: view fields it provides at their declared value at every
    node until an onset opens it, so the node opens with its declared content (its
    anchor, D057); insertion's onset rule admits their providers (a restricted lumen's
    volume grows only with its patch's area after the onset).
* Topology (docs/CELL_DIVISION_S5_DESIGN.md §2, §3.5):
  - ``CLOSES``: activity masks it may close (the adapter's MASK_FIELDS), through
    ``closures``. A slot is live only if every closer has it open: masks combine by
    conjunction with the declared ones, as availability factors multiply. The adapter then
    propagates closure down the entity hierarchy (cell to its patches, patch to its
    populations, cell to its contacts, node to its faces) and presents every closed slot to
    the inner model as padding. A closed contact's gate is state: the composite pads the bound
    state (gate 0), and a closer that opens or closes a contact writes its gate at that event.
    A mask has closers or a provider, never both, and a closer counts as the mask's provider
    for ``CONFLICTS_VIEW``. With a closer the composite owns the capacitor-energy correction
    at the view, referenced to the view of the initial state, and evaluates the inner domain
    at the view;
  - ``RETIRES``: its event moves retired slots' inner history (transfers and heat) into its
    own record and zeroes them, so the inner model sees padding; its ``adjust_inner`` adds the
    record back, and the composite runs its ledger and dissipation checks on that adjusted
    row, so every inner ledger and every heat element read as if nothing moved (the domain is
    read on the actual row, at the view);
  - ``TAKES_LIFECYCLE``: a retiring event map that takes ``lifecycle=``, the composite's
    callable for the kinds' state fields by role (pump_composite_adapter.lifecycle_split and
    lifecycle_retire), and calls it with its maps and retirement masks at every division.
    Beside a kind with fields on its slot axes, a retiring operator without it is refused
    (fails closed: the kinds' history would be lost);
  - ``DIVIDES_OWNED`` (FR-43 part 3, D315): an operator whose owned state divides at a retiring
    operator's division. Its ``divide_owned(state, maps, masks, p, *, xp)`` gives (state, valid)
    after the due divisions, from the same maps and retirement masks the kinds' lifecycle reads,
    and the composite calls it, in declared order after the kinds' fields, inside the lifecycle
    callable it passes the retiring event (TAKES_LIFECYCLE). Without such an operator nothing
    changes: the lifecycle is passed and called as before;
  - ``BOOKS_AT_VIEW`` on an event map: the composite passes ``view``, a function of state
    giving its view, when a field input is provided.
* Scoped composition, door S (docs/SCOPED_COMPOSITION_DESIGN.md), refining the view
  declarations per field:
  - ``VIEW_CHANGES`` ({field: Change}): what its contribution to a field it provides
    (``VIEW_FIELDS``) or closes (``CLOSES``) does: ``replace``, ``add`` or ``multiply`` (a
    closer's is ``and``), at stage ``event`` or ``split``. A scoped change is taken only on
    the slots ``changed_slots`` names (host) and ``view_slots`` masks (device); otherwise on
    every slot. Defaults (``view_change``): ``replace`` (``and`` for a closer) on every slot;
  - ``SCOPED_READS`` ({field: Read, or a tuple of Reads at distinct stages}): the mode of a
    read, ``current`` (the merged view at its stage: a ``VIEW_READS`` field), ``fixed`` (the
    declared value taken as the physical one: a ``CONFLICTS_VIEW`` field) or ``reference`` (the
    bound value as data, an anchor), and its stage. One field may be read in two modes at two
    stages (docs/OPERATOR_COMPOSITION_DESIGN.md §3, C3): ``current`` at the rates' stage beside
    ``reference`` at the existence checks'. A scoped read covers only the slots ``read_slots``
    names. Defaults (``scoped_read``): ``current`` for each ``VIEW_READS`` field, ``fixed`` for
    each ``CONFLICTS_VIEW`` field, on every slot. ``reads_of`` gives every Read of a field.
  - **A declared stage is one of its parts':** a change or read at ``event`` needs its event
    part, at ``split`` its split part (a change at ``split`` may also be a part-less state
    owner's, the default), and a read at ``inner`` its in-step process. The composite orders
    reads and changes by their stages, so a stage no part runs at is refused.
  Two changes or a change and a read of one field meet only on the slots both name; the
  composite admits a pair per slot (pump_composite.structure_errors and scope_errors) and
  merges each change onto the accumulated view on its slots (pump_composite_adapter.view).
  **The order of a current read** (docs/OPERATOR_COMPOSITION_DESIGN.md §4.1 and §5, C1 and C2),
  checked by pump_composite.structure_errors against every change of the field in the
  composition (pump_composite.view_changes: providers, closers, which change every mask and
  padded field, and writers of a provider's accepted state, at each stage they run at):
  - a field no operator changes is read at its declared value, and its reader receives no view
    (the fallback, C1);
  - a change at another stage of the step is seen whatever the declared order: the events run
    before the split parts' first halves, and an event reads the previous step's end;
  - a change at the reader's own stage must precede it in the declared order (door S's rule 3);
    a reader placed before it is refused rather than given a lagged value.
* Species identity and the step (registry/species_registry.py, D176): ``IDENTITY_ROLE``
  ("author" for an operator that declares the species it writes, "user" for one that refers to
  species others declare) and ``species_identities``; ``moves_in_step``, the rows an in-step
  process moves inside the inner step, which an operator with ``PROCESS`` declares;
  ``species_moieties``, the net row change of each move it makes, which the registry's
  check_moieties holds to the model's moieties (docs/GENE_REGULATION_DESIGN.md §7.6).
* Neutral arrival-time labels (FR-42, D289; operators/species_labels.py): a label owner
  (``LABEL_OWNER``, part-less, at most one per composition) holds each labelled species' shares,
  which the composite advances after every applied half-step of a reporter. A reporter is a split
  part whose ``half_step`` takes ``labels=None`` (reports_labels). Given ``labels=(rows,
  arrival)``, rows [m] the labelled species' rows and arrival [m, label] one-hot, the label the
  step's window names, it returns ``(state, valid, moves)``: its state and validity bit for bit
  the unlabelled call's, and moves = (out [m, node], into [m, label, node], transfers), from the
  same combination as its booked move. out is the one-way amount each labelled row lost at each
  node, into the one-way amount it gained by label (new material at the arrival label, material
  that keeps its labels at theirs), and transfers () until transport reports (FR-42's stage 2).
  The node axis is the cells, then the outside nodes; a reporter that acts at cells only may give
  its cells alone. Without labels nothing of it is traced.
  - **The inner step** (FR-42's stage 2): an inner implementation whose ``checked_step`` and
    ``imex_step`` take ``labels=rows`` returns its usual tuple with its transfers appended:
    ``((amount [m, entity], source [entity], destination [entity]), ...)``, one entry per
    direction per entity kind, each amount >= 0 over the step, nodes on the axis above. The label
    owner carries each transfer's source shares to its destination.
  - **Pools and sources** (D296): a reporter may declare ``label_pools(declaration)``, ((pool id,
    species, cell id or None), ...), each entry holding one labelled species' material outside
    the species axis (a release hold), whose shares the label owner holds; and
    ``label_sources(declaration)``, ((source id, species, cell id or None), ...), the entities that
    make new material (its chains), whose arrival label the owner's schedule may set per source.
    Whether it may is static, by class: ``LABEL_SOURCES`` and ``LABEL_POOLS``. A reporter with
    ``LABEL_SOURCES`` always takes a third element, ``labels=(rows, arrival, source_arrival)``,
    source_arrival [S, label] one-hot, S at least its sources (padding past them): source s's label
    this step. A reporter with ``LABEL_POOLS`` always returns a fourth part, possibly empty,
    ``moves = (out, into, transfers, pools)``, ``pools = (n0, n1,
    into, out, carried)``: its pool entries' amounts at the half-step's start and end [P], the
    new material entering them by label [P, label] and their losses [P], each >= 0; and carried,
    ``(amount [E] >= 0, source [E], destination [E])``, material that keeps its labels between
    sites: a row site j N + k (labelled row j at node k, N nodes) or one of its pool entries,
    M N + p (M labelled rows). Every move is counted once: a row's or pool's change is its into
    minus out plus carried in minus carried out, at rounding. Without pools and sources the
    argument and moves are as above, and nothing of them is traced.
  - **An event that replaces a slot's amounts** (D296: replacement@1) reports it: an ``event``
    that takes ``labels=rows`` returns ``(state, valid, replaced [cell])``, the slots whose
    amounts it replaced. The departing material leaves with its shares; the owner gives each
    replaced slot's labelled material the label in force for its species at that step (the
    newcomer label).
  - **A pool reporter's event that empties its pools** (erratum E,
    TEMPLATED_POLYMERISATION_LAWS §9.18) reports them too: its ``event`` with ``labels=rows``
    returns ``(state, valid, removed [P])``, the amounts it removed from its label_pools' entries,
    in order, taken from its state before the event (0 where it removed none). The owner gives
    each emptied entry the base label. Each event reports only its own material, rows or pools,
    so the two still commute. Beside a replacing event the owner records what leaves by label,
    the amount before the event times its shares just before it, cumulative from t = 0, rows
    (``label_removed_fmol``) and pools (``label_pool_removed_fmol``) apart; a pool reporter
    whose event takes no labels is refused there.
  - **An event that exchanges a node's liquid** (FR-44, D327: the compartment wash) reports the
    exchange: its ``event`` with ``labels=rows`` returns ``(state, valid, LiquidExchange)``,
    removed and supplied [m, outside node] >= 0, the amounts of each labelled row that this
    step's sample took away and its buffer brought, zero at every node not exchanged in the step.
    The axis is the outside nodes, as the owner's record of what left
    (``label_outside_removed_fmol``) is. An exchange of a cell's own liquid cannot be expressed in
    version 1. The sample leaves with the node's shares, since the liquid is well mixed. The
    buffer carries no label and joins the base, whatever window is open. The owner records what
    left by label, at the shares just before the event.
  - **Each labels-taking event has one report kind** (``LABEL_EVENT``, one of
    LABEL_EVENT_KINDS; label_event, static):
    - "replaced" is a replacing event's (``EVENT_REPLACES``) by default;
    - "emptied" is a pool reporter's (``LABEL_POOLS``);
    - "exchanged" is declared.
    The composite passes the kind to the owner, which reads the report by it. A labels-taking
    event with no kind, or one its declarations contradict, is refused (label_event_error), so no
    report is read as another kind's.
* The run view (docs/RUN_VIEW_DESIGN.md §3; cells/records/run_view.py reads them, host side only):
  - ``VIEW_LAYERS``: its layers, each {"id", "label", "representation"}; None: undeclared,
    which the run-view writer refuses;
  - ``view_events``: its events with their entities by id, each entity one {set: id}; the
    default gives the births and retirements of ``living_intervals`` at {"cell": id};
  - ``view_sets(spec, declaration)``: the view's set of each axis of its own (an axis of its
    STATE_AXES or OBSERVATION_AXES that the inner model does not have), and of any other kind
    of entity it declares (routes, sites), as {axis or key: {"id", "ids", optional "holds",
    "on": (set id, entity ids), "roles": {role: what it is}, and per-entity facts: "carries"
    (species ids), "direction" and "kinds" (words), "at" ({set id: entity id})}}; the default
    declares none;
  - ``OBSERVATION_AXES`` ({readout column: axes}): its READOUT_COLUMNS' axes, as STATE_AXES
    gives its state's;
  - ``UNITS`` ({field: unit}): the unit of an own field whose name carries no unit suffix;
  - ``RECORD_KINDS`` ({field: kind}), kind one of RECORD_KIND_VALUES: ``level``, ``amount``,
    ``cumulative`` (a total since the start) or ``rate``;
  - ``ORIENTATION`` ({field: {"from", "to", "says"}} for a flow, which way a positive value
    moves; {field: {"plus", "minus", "says"}} for a difference, plus less minus), by the roles
    of the record's entity set (the writer checks the roles; ``confirmed`` may name who
    confirmed it, ``source`` where it was read);
  - ``RECORD_LAYERS`` ({field: layer id}): the layer, one of its VIEW_LAYERS, of an own field
    or of a view field it provides or closes (door S's merged view, a record of the view);
    needed only with more than one layer;
  - ``RECORD_DIAGNOSTICS`` (own fields): the residuals of the step's own checks, held to their
    own absolute tolerances there, not quantities of the simulated world (a looping package's
    closure leaves them out; docs/LOOPING_REPLAY_DESIGN.md §2);
  - ``RECORD_REFERENCES`` ({own state field: own layout field}): a field stored as an increment
    over a fixed reference, whose quantity is reference + increment (a loop's closure measures
    that sum, the reference from the bound layout or from its merged view where door S changes
    it). The inner model declares both in the same forms, read by getattr.
  None of them changes a program, a binding or a checkpoint.

Methods take the composite's full state, control and layout NamedTuples, whose
fields are the inner model's followed by each operator's in declared order.
Defaults below are the idle answers: no parts, no terms, no columns.
"""

import inspect
from collections.abc import Mapping
from types import MappingProxyType
from typing import NamedTuple

from cells.registry import kind_registry

HEAT_SUFFIX = "_dissipated_energy_pJ"
WORK_SUFFIX = "_work_pJ"
RK4_MODES = ("coupled", "split")
ROUTE_KINDS = ("rate",)  # B1′'s routable controls (an event route is a later door, §2.2).
IDENTITY_ROLES = ("author", "user")
REPRESENTATIONS = ("simulated", "modelled", "prescribed")
LAYER_KEYS = frozenset({"id", "label", "representation"})
# The run view's record kinds and sign keys (docs/RUN_VIEW_DESIGN.md §3; cells/records/run_view.py).
RECORD_KIND_VALUES = ("level", "amount", "cumulative", "rate")
# An orientation is a flow's (from, to) or a difference's (plus, minus), each with says.
ORIENTATION_FORMS = (("from", "to"), ("plus", "minus"))
ORIENTATION_OPTIONAL = frozenset({"confirmed", "source"})
# Door S (docs/SCOPED_COMPOSITION_DESIGN.md §2).
CONTRIBUTIONS = ("replace", "add", "multiply")  # Of a provided field; a closer's is "and".
COMMUTING = ("add", "multiply", "and")  # Overlaps admitted, applied in declared order.
CHANGE_STAGES = ("event", "split")
READ_MODES = ("reference", "current", "fixed")
READ_STAGES = ("event", "split", "inner", "end", "observe")  # In step order.
# The reports a labels-taking event gives the label owner (FR-42's events, FR-44; label_event).
REPLACED, EMPTIED, EXCHANGED = "replaced", "emptied", "exchanged"
LABEL_EVENT_KINDS = (REPLACED, EMPTIED, EXCHANGED)


class Change(NamedTuple):
    """Door S: an operator's contribution to one view field (docs/SCOPED_COMPOSITION_DESIGN.md).

    scoped: taken only on the slots changed_slots names and view_slots masks; otherwise on
    every slot of the field's entity axis (its last axis)."""

    contribution: str = "replace"
    stage: str = "event"
    scoped: bool = False


class Read(NamedTuple):
    """Door S: an operator's read of one view field (docs/SCOPED_COMPOSITION_DESIGN.md).

    mode: "current", "fixed" or "reference"; stage: the point whose view it consumes; scoped:
    only the slots read_slots names, otherwise every slot."""

    mode: str
    stage: str
    scoped: bool = False


class LiquidExchange(NamedTuple):
    """An exchanging event's report to the label owner (FR-44; module docstring), in fmol, each
    [labelled species, outside node] and >= 0, zero at every node not exchanged in the step.

    removed: what this step's sample took away, which carries the node's shares. supplied: what
    its buffer brought, which carries no label."""

    removed: object
    supplied: object


def reads_of(operator, field):
    """Door S: every Read of `field` by `operator`, in declared order (C3: one per stage), from
    SCOPED_READS, else its default read (Operator.scoped_read's), or ()."""
    if field in operator.SCOPED_READS:
        declared = operator.SCOPED_READS[field]
        return (declared,) if isinstance(declared, Read) else tuple(declared)
    read = operator.scoped_read(field)
    return () if read is None else (read,)


def factor_reads(operator):
    """The fields a factor operator reads current at the control view (R2: stage inner, from
    SCOPED_READS), in declared order; () for any other operator."""
    if not operator.CONTROL_FACTORS:
        return ()
    return tuple(
        k
        for k in operator.SCOPED_READS
        if any(r.mode == "current" and r.stage == "inner" for r in reads_of(operator, k))
    )


def takes_labels(method):
    """Whether a step method takes the keyword labels= (FR-42, module docstring)."""
    return "labels" in inspect.signature(method).parameters


def reports_labels(operator):
    """Whether a split part reports its one-way moves to a label owner (FR-42, module
    docstring): its half_step takes labels=."""
    return operator.SPLIT and takes_labels(operator.half_step)


def label_event(operator):
    """The kind of report a labels-taking event gives the label owner (FR-42, FR-44; module
    docstring), static.
    - Its declared LABEL_EVENT where it declares one.
    - Otherwise "emptied" for a pool reporter's event and "replaced" for a replacing event's.
    - None for an event that takes no labels, and for one that declares no kind and is neither
      (label_event_error refuses that one)."""
    if not (operator.EVENT and takes_labels(operator.event)):
        return None
    if operator.LABEL_EVENT is not None:
        return operator.LABEL_EVENT
    if operator.LABEL_POOLS:
        return EMPTIED
    return REPLACED if operator.EVENT_REPLACES else None


def label_event_error(operator):
    """Why an operator's label event kind contradicts its declarations, or None (fail closed: no
    report is read as another kind's). check_declarations raises it for a class, and the label
    owner refuses it in a composition."""
    if not (operator.EVENT and takes_labels(operator.event)):
        if operator.LABEL_EVENT is None:
            return None
        return "it declares a report kind (LABEL_EVENT), which only an event taking labels= has"
    kind = label_event(operator)
    if kind is None:
        return (
            "its event takes labels= but has no report kind: it declares no LABEL_EVENT and is "
            "neither a pool reporter's nor a replacing event's, so no reader would read its report"
        )
    if kind not in LABEL_EVENT_KINDS:
        return f"its report kind {kind!r} is not one of {LABEL_EVENT_KINDS}"
    if kind == EMPTIED and not operator.LABEL_POOLS:
        return "an emptied report is a pool reporter's (LABEL_POOLS)"
    if kind == REPLACED and (operator.LABEL_POOLS or not operator.EVENT_REPLACES):
        return "a replaced report is a replacing event's (EVENT_REPLACES), not a pool reporter's"
    if kind == EXCHANGED and (
        operator.LABEL_POOLS or operator.EVENT_REPLACES or not operator.ENTITY_WRITES
    ):
        return (
            "an exchanged report is an event's that writes amounts (ENTITY_WRITES), replaces "
            "none and holds no label pools"
        )
    return None


def part_stages(operator):
    """The stages at which an operator's own parts run: event (its event map), split (its
    half-steps) and inner (its in-step process)."""
    parts = (("event", operator.EVENT), ("split", operator.SPLIT), ("inner", operator.PROCESS))
    return tuple(stage for stage, part in parts if part)


class Operator:
    """Base declarations and idle defaults; one subclass per operator law."""

    LAW_ID = None
    STEP_ID = None  # The numerical method of its split part, when it has one.
    # Parts.
    EVENT = False
    SPLIT = False
    PROCESS = False
    RK4 = None
    # Fields.
    STATE_AXES = MappingProxyType({})
    STATE_DTYPES = MappingProxyType({})
    HEAT_FIELDS = ()
    WORK_FIELDS = ()
    ENERGY_ROLES = MappingProxyType({})  # {owned state field: kind_registry.EnergyRole}
    LAYOUT_FIELDS = ()
    CONTROL_FIELDS = ()
    EXPERIMENT_KEYS = ()
    VIEW_FIELDS = ()
    CONTROL_FACTORS = ()
    # B1′ (module docstring): its routable rate controls, and the routable controls it routes to.
    ROUTABLE_CONTROLS = MappingProxyType({})
    RATE_ROUTES = ()
    # B1′'s exact record: an owned state field [route] the composite fills with each route's factor
    # where it is applied (factor_record); None: no record.
    FACTOR_RECORD = None
    # R3 (module docstring): its readable quantities, {name: (entity axis, unit)}, and the owners'
    # quantities it may read, {owner law: (names, ...)}.
    QUANTITIES = MappingProxyType({})
    QUANTITY_READS = MappingProxyType({})
    CONFLICTS_VIEW = ()
    ENTITY_WRITES = MappingProxyType({})
    # Inner kinetic state it sets at events (intensive, without a ledger: gates).
    STATE_RESETS = ()
    # Its view inputs evolve in its split part: the inner domain is then evaluated
    # at the view and re-checked at the step end.
    VIEW_FOLLOWS_SPLIT = False
    # Its split part books @3's capacitor terms (image charge, capacitor free energy) at
    # the composite's view: when a field input is provided, the composite passes the
    # current view to half_step (view=...); otherwise the declared layout applies.
    BOOKS_AT_VIEW = False
    # Ledgers and readouts.
    LEDGERS = ()
    LEDGER_DIAGNOSTICS = ()
    LEDGER_MESSAGE = ""
    READOUT = None
    READOUT_COLUMNS = ()
    FINITE_RATES = False
    REQUIRES = ()
    # The inner kinds whose fields it reads or writes, by kind ID (schema A; module docstring).
    REQUIRES_KINDS = ()
    # Its parts build the inner model's types with today's fixed fields: refused beside declared
    # kinds (schema A; module docstring).
    FIXED_INNER_FIELDS = False
    # Ownership (module docstring).
    REPLACES = MappingProxyType({})
    VIEW_READS = ()
    ACCEPTS_WRITES = MappingProxyType({})
    EVENT_REPLACES = MappingProxyType({})
    ONSET_ANCHORED_VIEWS = ()
    # Topology (module docstring).
    CLOSES = ()
    RETIRES = False
    TAKES_LIFECYCLE = False  # Its event map takes lifecycle= (module docstring).
    DIVIDES_OWNED = False  # Its owned state divides at a division (divide_owned; FR-43, D315).
    # Its parts call the inner model's structure-bound functions (an event map's kinetics, the
    # field solve): the composite passes the inner implementation object as `inner=` to its
    # event, half_step and rates calls and to initial_values (static), and host methods reach
    # it as model.inner (D176; docs/INNER_MODEL_V4_DESIGN.md §7.4). Every other call is unchanged.
    USES_INNER = False
    # Door S (module docstring): refinements of the view declarations, per field.
    VIEW_CHANGES = MappingProxyType({})
    SCOPED_READS = MappingProxyType({})
    # Species identity (registry/species_registry.py, D176): "author" for an operator that declares
    # the species it writes, "user" for one that refers to species others declare.
    IDENTITY_ROLE = "author"
    # Its layers in the run view (docs/RUN_VIEW_DESIGN.md §3): ({"id", "label",
    # "representation"}, ...), representation one of REPRESENTATIONS. None: undeclared, which the
    # run-view writer refuses.
    VIEW_LAYERS = None
    # Its records in the run view (module docstring), by its own field names.
    OBSERVATION_AXES = MappingProxyType({})
    UNITS = MappingProxyType({})
    RECORD_KINDS = MappingProxyType({})
    ORIENTATION = MappingProxyType({})
    RECORD_LAYERS = MappingProxyType({})
    RECORD_DIAGNOSTICS = ()
    RECORD_REFERENCES = MappingProxyType({})
    # A declaration with no part and no field (module docstring; check_declarations).
    DECLARATION_ONLY = False
    # FR-42 (module docstring): a part-less owner of label shares, advanced by the composite from
    # its reporters' moves; and, for a reporter, whether it may declare sources and pools (D296).
    LABEL_OWNER = False
    LABEL_SOURCES = False
    LABEL_POOLS = False
    # FR-44: a labels-taking event's report kind, one of LABEL_EVENT_KINDS, where its flags do
    # not give it (label_event): "exchanged" is declared.
    LABEL_EVENT = None

    @classmethod
    def observed_columns(cls):
        """Its own observation columns: its state fields, then READOUT_COLUMNS."""
        return (*cls.STATE_AXES, *cls.READOUT_COLUMNS)

    @classmethod
    def view_change(cls, field):
        """Door S: the Change of a field it provides or closes (VIEW_CHANGES, else the default:
        replace, or and for a closer, on every slot; stage split with a split part or none,
        else event)."""
        if field in cls.VIEW_CHANGES:
            return cls.VIEW_CHANGES[field]
        stage = "split" if cls.SPLIT or not (cls.EVENT or cls.PROCESS) else "event"
        return Change("and" if field in cls.CLOSES else "replace", stage)

    @classmethod
    def scoped_read(cls, field):
        """Door S: the Read of a field it reads (SCOPED_READS, else current for VIEW_READS and
        fixed for CONFLICTS_VIEW, on every slot), or None. A field read at several stages (C3)
        has no single Read: reads_of gives them all, and this refuses (fails closed)."""
        if field in cls.SCOPED_READS:
            declared = cls.SCOPED_READS[field]
            if isinstance(declared, Read):
                return declared
            if len(declared) == 1:
                return declared[0]
            raise ValueError(
                f"{cls.LAW_ID} reads {field} at {len(declared)} stages; contract.reads_of gives "
                "every Read of it"
            )
        stage = "split" if cls.SPLIT else "event"
        if field in cls.VIEW_READS:
            return Read("current", stage)
        if field in cls.CONFLICTS_VIEW:
            return Read("fixed", stage)
        return None

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        raise NotImplementedError

    def to_dict(self, declaration, base):
        raise NotImplementedError

    def parse_schedule(self, raw, base, declaration):
        """raw: {key: value} for EXPERIMENT_KEYS."""
        return ()

    def schedule_to_dict(self, schedule, base, declaration):
        return {}

    def schedule_times(self, schedule):
        return ()

    def value_at(self, schedule, time):
        """This operator's schedule record at `time` (hashable, for change records)."""
        return ()

    def control_values(self, spec, declaration, schedule, records, indices, times):
        """Arrays aligned with CONTROL_FIELDS at `times`; records[i] = value_at(change i)."""
        return ()

    def check_definition(self, spec, declaration, schedule, model):
        """Refusals beyond the composite's domain check of every scheduled control."""

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        """The definition the inner step checks read (by field name)."""
        return check_spec

    def check_steps(self, spec, declaration, schedule, steps, controls, model):
        """Step-size refusals of this operator (after the inner model's)."""

    def bind_check_steps(self, spec, declaration, schedule, model):
        """check_steps bound to one definition: a callable of each chunk's steps (the
        composite's bind_step_checks). The default calls check_steps per chunk; an
        operator whose checks read the definition (a layout, say) binds those parts once,
        evaluated at first use in check_steps' order (v2 design R5)."""
        return lambda steps: self.check_steps(spec, declaration, schedule, steps, None, model)

    def living_intervals(self, spec, declaration, schedule):
        """{cell id: (birth, retirement)} for the cells whose lives this operator decides (None:
        from the start, or never). Host side: other operators' definition checks read slot
        lifetimes through it, without importing the operator that decides them."""
        return {}

    def patch_maps(self, declaration):
        """{patch id: the patch ids this operator maps it onto} (host side, as above)."""
        return {}

    def onset_patches(self, spec, declaration, schedule):
        """{patch id: onset time} for the patches this operator opens at an onset (host side,
        as above)."""
        return {}

    def changed_volume_nodes(self, spec, declaration):
        """The outside nodes, by index into the definition's extracellular list, whose volume
        this operator changes where it provides extracellular_volume (host side, as above), or
        None: every node. The shared volume rule of the current-volume readers reads it
        (species_common.check_volume_changers; FR-65's route B,
        docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §3.5): a changer other than water is refused only
        at a node its reader reads. A provider that changes the volume at its own nodes alone
        names them, as a restricted lumen does; no program reads it."""
        return None

    def charged_compartments(self, spec, declaration):
        """The compartments, by their declared IDs (operators/compartments.py), into which its
        routes move charge (host side, as above). Refusal 5 version 1.2 admits a nonzero charge
        anchor on each, for the operators on the compartments declaration's admitted list: a world
        whose admitted routes charge a compartment must be able to resume from its own checkpoint
        (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.5). (): none."""
        return ()

    def changed_slots(self, spec, declaration):
        """Door S, host: {field: entity indices} for each field its scoped Change covers (the union
        over the run: later doses, onsets and closures included)."""
        return {}

    def read_slots(self, spec, declaration):
        """Door S, host: {field: entity indices} for each field its scoped Read covers."""
        return {}

    def moves_in_step(self, spec, declaration):
        """The rows its in-step process (PROCESS) moves inside the inner step, as
        ((species id, "cell" | "outside"), ...); read by core/species_registry.moved_in_step,
        which the coupling operator's instantaneous admission uses (D176, "moved by the step").
        An operator without an in-step process moves nothing in the step: ()."""
        return ()

    def label_pools(self, declaration):
        """FR-42's pools (D296; module docstring): ((pool id, species, cell id or None), ...), the
        entries of its own state that hold a labelled species' material, in a fixed order; ()."""
        return ()

    def label_sources(self, declaration):
        """FR-42's sources (D296; module docstring): ((source id, species, cell id or None), ...),
        the entities whose new material the owner may label per source, in a fixed order; ()."""
        return ()

    def species_identities(self, declaration):
        """The species identities it declares: items with id, catalogue and evidence; ()."""
        return ()

    def species_potentials(self, declaration):
        """The standard potentials it declares, ((species, mu°/RT, c0 in mM), ...); ().
        core/species_registry.check_potentials refuses one that the registry gives otherwise."""
        return ()

    def standard_free_energies(self, declaration):
        """The reaction-level standard free energies it declares (docs/CORE_SEAMS_DESIGN.md §7.1,
        seam E): ((stoichiometry, dG°/RT, c0 in mM), ...), the stoichiometry ((species, nu), ...)
        with nu signed (products positive); (). A law with constants of its own (a cycle's
        equilibrium constant, say) declares them here, and the species registry's check compares
        each with the registry's sum of nu mu°/RT, converted by (sum of nu) ln(c0_registry / c0).
        A species' potential is the case of one species at nu = 1; species_potentials keeps
        declaring those, as today's check reads them."""
        return ()

    def species_moieties(self, declaration):
        """The net moves of the species rows it converts (docs/GENE_REGULATION_DESIGN.md §7.6):
        ((move name, ((species, nu), ...)), ...), each move's net change of the model's rows per
        unit of its progress (a finished product, a molecule degraded, a turnover), nu nonzero
        integers, products positive; (). Material it holds in its own pools between the rows (a
        chain's residues in transit) is left out: its own ledgers close it. The species registry's
        check_moieties refuses a move that changes a declared moiety, naming the operator and the
        move, as it refuses a kind's mode or a free-energy entry; so a weight the operator assumes
        (the residues of a polymer row) that differs from the model's moiety shows as a change."""
        return ()

    def view_events(self, spec, declaration, schedule):
        """Its events in the run view: ({"time", "kind", "layer", "at", "from", "label"}, ...),
        each entity one {set id: entity id} ("from" optional). The default gives the births and
        retirements of living_intervals, each at {"cell": id}; an operator with an event map or a
        schedule overrides it, so that no event reaches the view without its entities, and keeps
        those births and retirements (the run-view writer refuses an override without them)."""
        layer = self.VIEW_LAYERS[0]["id"] if self.VIEW_LAYERS else None
        events = []
        lives = self.living_intervals(spec, declaration, schedule)
        for cell, (birth, retirement) in sorted(lives.items()):
            for time, kind in ((birth, "birth"), (retirement, "retirement")):
                if time is not None:
                    events.append(
                        dict(
                            time=float(time),
                            kind=kind,
                            layer=layer,
                            at={"cell": cell},
                            label=f"{cell} {'born' if kind == 'birth' else 'retired'}",
                        )
                    )
        return tuple(sorted(events, key=lambda e: (e["time"], e["kind"], e["label"])))

    def view_sets(self, spec, declaration):
        """The run view's set of each axis of its own (module docstring): {axis: {"id", "ids",
        optional "holds", optional "on": (set id, entity ids)}}, host side. The default declares
        none: an operator whose fields have an axis the inner model lacks declares its set, or the
        run-view writer refuses the composition."""
        return {}

    def batch_signature(self, declaration):
        return (self.LAW_ID,)

    def working_size(self, spec):
        return 0

    def summary(self, spec, declaration, schedule, history):
        return {}

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        """({owned state field: array}, {layout field: array})."""
        raise NotImplementedError

    # ------------------------------------------------------------ step parts

    def view(self, state, p, q, *, xp):
        """{inner layout field: value} for VIEW_FIELDS, from state (q: the running view)."""
        return {}

    def view_slots(self, p, *, xp):
        """Door S, device: {field: bool mask over the field's entity axis} for each field its
        scoped Change covers: the slots its contribution is taken on (changed_slots' slots, bound
        as layout data, checked when the composition binds)."""
        return {}

    def control_factors(self, state, p, *, xp):
        """{inner control field: multiplier} for CONTROL_FACTORS. An operator with factor_reads
        also takes view=, the function of state giving its reader view (R2)."""
        return {}

    def rate_factors(self, state, p, target, field, *, xp):
        """(factor, valid) for one of RATE_ROUTES, (target law, field): the factor shaped as the
        target's control field, from the state the target's half-step receives, and its validity
        (None: nothing to check); None where the definition declares no route on it (static)."""
        return None

    def declared_rate_routes(self, declaration):
        """((target law, field), ...) the declaration routes to: each one of RATE_ROUTES, checked
        at the definition with its target's place in the operator list (B1′)."""
        return ()

    def routable_elements(self, declaration, field):
        """((element id, cell id or None), ...) of a routable control field, aligned with its last
        axis: the ids a route names and the cell where its source is read (None: an outside node)
        (B1′, the target side; a routable operator defines it)."""
        raise NotImplementedError

    def half_step_rows(self, declaration):
        """((species id, cell id), ...) the rows its own half-steps move, in the cells its
        routable_elements name (B1′, the target side): a rate route whose species source is one of
        them is self-moved, and the composite evaluates its factor at the half-step's midpoint
        (pump_composite.self_moved_targets). (): it moves none."""
        return ()

    def rate_route_sources(self, declaration):
        """((target law, field, element ids, source species id), ...) of its declared rate routes
        with a species source read in each element's cell (B1′, the source side), for the
        composite's self-moved test; ()."""
        return ()

    def quantities(self, state, p, *, xp):
        """R3, the owner: {name: values} of its QUANTITIES at `state`, each on its entity axis."""
        return {}

    def quantity_entities(self, spec, declaration):
        """R3, the owner, host side: {entity axis: ((entity id, its cell id or None), ...)} in the
        axis' order, for each axis of its QUANTITIES: a reader binds its reads by entity ID and
        checks where they are read, without importing the owner."""
        return {}

    def declared_quantity_reads(self, declaration):
        """R3, the reader: ((owner law, name, target law or None), ...) the declaration reads,
        each one of QUANTITY_READS; the target is an operator target's route, whose half-steps
        evaluate it, or None, a read at the control view."""
        return ()

    def factor_valid(self, state, p, *, xp):
        """The validity of its CONTROL_FACTORS' sources at the control view, where the composite
        evaluates them (B1′: a declared operating range), or None: nothing to check. With
        factor_reads it also takes view= (R2)."""
        return None

    def factor_record(self, state, p, target, field, *, xp):
        """(values, mask) [route] for FACTOR_RECORD: each route's factor from `state` and the
        routes evaluated there, at the control view (target None) or at a target's half-step
        (target, field) (B1′'s exact record of the factor applied). With factor_reads it also
        takes view= at the control view (R2); a target's half-step passes none."""
        raise NotImplementedError

    def divide_owned(self, state, maps, masks, p, *, xp):
        """(state, valid) after a retiring operator's due divisions, for DIVIDES_OWNED: its owned
        fields from maps ({slot axis: (parent rows, daughter rows, daughter 1's fraction, due
        rows)}) and masks ({slot axis: retired}), the closer's own (module docstring)."""
        raise NotImplementedError

    def closures(self, state, p, q, *, xp):
        """{mask field: open (bool array)} for CLOSES, from state (q: the running view)."""
        return {}

    def event(self, state, control, p, *, xp):
        """(state, consistent) after the events due at the step start."""
        raise NotImplementedError

    def half_step(self, state, h, control, p, *, xp):
        """(state, valid or None) after h of the split part on its own variables. An operator
        that BOOKS_AT_VIEW also takes view=, @3's layout at the current state, when a field
        input is provided."""
        raise NotImplementedError

    def control_valid(self, control, p, *, xp):
        """Validity of this operator's controls (None: nothing to check)."""
        return None

    def idle_process(self, p):
        """True when the in-step process is statically absent (by layout shape)."""
        return True

    def statically_idle(self, p):
        """True when every part is statically absent (by layout shape): the step then
        skips the operator entirely and its owned fields pass through unchanged."""
        return False

    def process(self, control, p):
        """The inner model's membrane-process callable."""
        raise NotImplementedError

    def book_process(self, state, start, applied, heat, p):
        """state with the process's applied transfer and heat booked in owned fields."""
        raise NotImplementedError

    def rates(self, state, control, p, view, *, xp):
        """(derivatives {owned field: rate}, validity of the rates or None, readout).

        The readouts fold, in this order: every operator's rate validity, every
        operator's rate_checks, the finiteness of the FINITE_RATES operators' rates,
        then the energy_rate terms (the frozen models' order)."""
        zeros = {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}
        return zeros, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        """The readouts' running validity with this operator's state and control checks."""
        return valid

    def energy_rate(self, readout, p, *, xp):
        """Its term of the energy-balance rate (pJ/s), or None."""
        return None

    def domain_valid(self, state, p, valid, *, xp):
        """The running domain conjunction `valid` (None: nothing yet) with this operator's."""
        return valid

    # ------------------------------------------------------------ ledgers

    def adjust_inner(self, row, p, *, xp):
        """The row as the inner ledgers must see it (transfers it books in inner terms)."""
        return row

    def ledger_terms(self, result, row, p, *, xp):
        """(the inner ledgers' dict with this operator's terms, its own ledgers' dict)."""
        return result, {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The inner rounding magnitudes (a list in the inner LEDGERS order) with its terms."""
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        """Its own ledgers alone (the host check of its ledgers)."""
        return self.ledger_terms({"energy": 0.0}, row, p, xp=xp)[1]

    def own_magnitudes(self, row, p, *, xp):
        return ()

    def external_ledger_terms(self, ledgers, row, p, *, xp):
        """An earlier owner's accepted ledgers ({name: value}) with this writer's terms."""
        return ledgers

    def external_magnitude_terms(self, magnitudes, row, p, *, xp):
        """An earlier owner's accepted ledger magnitudes ({name: value}) with its terms."""
        return magnitudes

    def own_bounds(self, magnitudes, steps):
        return ()

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        """{column: value} for this operator's state fields and READOUT_COLUMNS."""
        return {k: getattr(state, k) for k in self.STATE_AXES}


# What a declaration (DECLARATION_ONLY) may define below Operator; everything else fails closed.
DECLARATION_MAY_DEFINE = frozenset(
    {
        "LAW_ID",
        "DECLARATION_ONLY",
        "CONFLICTS_VIEW",
        "REQUIRES",
        "parse",
        "to_dict",
        "check_definition",
        "initial_values",
        "summary",
        "VIEW_LAYERS",
        "view_events",
        "SCOPED_READS",  # Unscoped reference reads only (_declaration_read_errors).
    }
)


def _defined_below_operator(operator, name):
    """True when a class between `operator` and Operator in its MRO defines `name`."""
    for klass in operator.__mro__:
        if klass is Operator:
            return False
        if name in vars(klass):
            return True
    return True  # Not an Operator subclass: nothing of it is Operator's.


def declaration_errors(operator):
    """Why a DECLARATION_ONLY operator class is not a declaration (empty: it is one).

    Fails closed: no class below Operator may define a public attribute of Operator, data or
    method, outside DECLARATION_MAY_DEFINE, even at its default value. So a declaration has no
    part, field, schedule, view, factor, closure, view read, write, reset, ledger, readout,
    replaced column, energy role, step method, schedule hook or definition-check hook of its own.
    """
    errors = []
    for name in sorted(n for n in dir(Operator) if not n.startswith("_")):
        if name not in DECLARATION_MAY_DEFINE and _defined_below_operator(operator, name):
            kind = "overrides" if callable(getattr(Operator, name)) else "declares"
            errors.append(f"{kind} {name}")
    return errors + _declaration_read_errors(operator)


def _declaration_read_errors(operator):
    """A declaration's SCOPED_READS (D217): each Read is a reference read, the bound value as data,
    and unscoped, since a declaration has no part to consume a view (current) and holds no field
    as physical through them (fixed reads are its CONFLICTS_VIEW's), and defines no read_slots."""
    reads = operator.SCOPED_READS
    if not isinstance(reads, Mapping):
        return ["declares SCOPED_READS that is not a mapping of fields to Reads"]
    errors = []
    for field, declared in reads.items():
        if isinstance(declared, Read) or type(declared) is not tuple:
            declared = (declared,)  # A malformed entry is refused here, read by read.
        for read in declared:
            if not (isinstance(read, Read) and read.mode == "reference" and not read.scoped):
                errors.append(
                    f"declares a read of {field} that is not an unscoped reference read ({read!r})"
                )
    return errors


def check_declarations(operator):
    """Refuse an operator class whose declarations break the contract."""
    name = operator.LAW_ID
    if not isinstance(name, str) or "@" not in name:
        raise ValueError(f"Operator {operator!r} needs a versioned law ID")
    if operator.DECLARATION_ONLY:
        errors = declaration_errors(operator)
        if errors:
            raise ValueError(
                f"{name}: a declaration contributes nothing to the step, but it "
                + "; ".join(errors)
            )
    if operator.SPLIT and operator.RK4 not in RK4_MODES:
        raise ValueError(f"{name}: a split part declares its RK4 mode, one of {RK4_MODES}")
    if not operator.SPLIT and operator.RK4 is not None:
        raise ValueError(f"{name}: an RK4 mode needs a split part")
    if (
        not operator.DECLARATION_ONLY
        and not (operator.EVENT or operator.SPLIT or operator.PROCESS)
        and not (
            (operator.ACCEPTS_WRITES and operator.VIEW_FIELDS)
            or (operator.STATE_AXES and set(operator.STATE_AXES) <= set(operator.ACCEPTS_WRITES))
            or (operator.LABEL_OWNER and operator.STATE_AXES)
        )
    ):
        raise ValueError(
            f"{name}: an operator contributes at least one part, or is a state owner that "
            "provides views of fields later operators write (ACCEPTS_WRITES), or owns only "
            "fields later operators write, or owns label shares (LABEL_OWNER), or is a "
            "declaration (DECLARATION_ONLY)"
        )
    if operator.LABEL_OWNER and (operator.EVENT or operator.SPLIT or operator.PROCESS):
        raise ValueError(f"{name}: a label owner has no part; the composite advances its shares")
    if (operator.LABEL_SOURCES or operator.LABEL_POOLS) and not reports_labels(operator):
        raise ValueError(f"{name}: sources and pools are a label reporter's (FR-42, D296)")
    error = label_event_error(operator)
    if error:
        raise ValueError(f"{name}: {error} (FR-44)")
    for field in operator.STATE_AXES:
        booked = field in operator.HEAT_FIELDS or field in operator.WORK_FIELDS
        if field.endswith((HEAT_SUFFIX, WORK_SUFFIX)) != booked:
            raise ValueError(
                f"{name}: owned field {field} must be declared as heat or work exactly when "
                f"it ends in {HEAT_SUFFIX} or {WORK_SUFFIX}"
            )
    for field in (*operator.HEAT_FIELDS, *operator.WORK_FIELDS):
        if field not in operator.STATE_AXES:
            raise ValueError(f"{name}: heat and work fields must be owned state")
    _check_energy_roles(operator)
    if set(operator.STATE_RESETS) & set(operator.ENTITY_WRITES):
        raise ValueError(f"{name}: a field is either a ledgered write or a kinetic reset")
    if operator.STATE_RESETS and not operator.EVENT:
        raise ValueError(f"{name}: kinetic resets happen at events")
    for field, accumulators in operator.ENTITY_WRITES.items():
        if not accumulators or any(a not in operator.STATE_AXES for a in accumulators):
            raise ValueError(f"{name}: the entity write {field} needs owned accumulators")
    if len(operator.LEDGERS) != len(operator.LEDGER_DIAGNOSTICS):
        raise ValueError(f"{name}: one diagnostic per own ledger")
    if operator.VIEW_FOLLOWS_SPLIT and not (operator.SPLIT and operator.VIEW_FIELDS):
        raise ValueError(f"{name}: a view that follows the split needs both")
    own = operator.observed_columns()
    if len(set(own)) != len(own):
        raise ValueError(f"{name}: an observation column is declared twice")
    for column, reason in operator.REPLACES.items():
        if column in own or not (isinstance(reason, str) and reason):
            raise ValueError(f"{name}: a replaced column {column} is not its own and has a reason")
    if set(operator.VIEW_READS) & set((*operator.VIEW_FIELDS, *operator.CONFLICTS_VIEW)):
        raise ValueError(f"{name}: a view field is read, provided or held as declared, not two")
    if not set(operator.ONSET_ANCHORED_VIEWS) <= set(operator.VIEW_FIELDS):
        raise ValueError(f"{name}: an onset-anchored view field is one it provides")
    for field, ledgers in operator.ACCEPTS_WRITES.items():
        if field not in operator.STATE_AXES or not ledgers:
            raise ValueError(f"{name}: an accepted write {field} needs an owned field")
        if any(k not in operator.LEDGERS for k in ledgers):
            raise ValueError(f"{name}: an accepted write {field} is booked in its own ledgers")
    if set(operator.CLOSES) & set(operator.VIEW_FIELDS):
        raise ValueError(f"{name}: a mask is closed or provided, not both")
    if operator.RETIRES and not operator.EVENT:
        raise ValueError(f"{name}: retirement happens at events")
    if not isinstance(operator.TAKES_LIFECYCLE, bool) or (
        operator.TAKES_LIFECYCLE and not operator.RETIRES
    ):
        raise ValueError(f"{name}: TAKES_LIFECYCLE is a bool, true only for a retiring operator")
    if not isinstance(operator.DIVIDES_OWNED, bool) or (
        operator.DIVIDES_OWNED
        and not (operator.STATE_AXES and _defined_below_operator(operator, "divide_owned"))
    ):
        raise ValueError(
            f"{name}: DIVIDES_OWNED is a bool, true only for an operator with owned state that "
            "defines divide_owned"
        )
    if operator.EVENT_REPLACES and not operator.EVENT:
        raise ValueError(f"{name}: replaced fields need an event map")
    for field, accumulators in operator.EVENT_REPLACES.items():
        removed_supplied = len(accumulators) == 2 and set(accumulators) <= set(operator.STATE_AXES)
        if field not in operator.ENTITY_WRITES or not removed_supplied:
            raise ValueError(
                f"{name}: an event replaces {field} as an entity write, booked in owned "
                "removed and supplied accumulators"
            )
    _check_scopes(operator)
    _check_routes(operator)
    _check_quantities(operator)
    if operator.PROCESS and not _defined_below_operator(operator, "moves_in_step"):
        raise ValueError(f"{name}: an in-step process declares the rows it moves (moves_in_step)")
    if operator.IDENTITY_ROLE not in IDENTITY_ROLES:
        raise ValueError(f"{name}: IDENTITY_ROLE is one of {IDENTITY_ROLES}")
    _check_layers(operator)
    _check_records(operator)
    _check_kinds(operator)
    return operator


def energy_roles(operator):
    """{owned state field: kind_registry.EnergyRole} of every field the operator books as energy,
    in STATE_AXES order: its declaration (ENERGY_ROLES), else heat and monotone for a field of
    HEAT_FIELDS and work, not monotone, for one of WORK_FIELDS (today's rule)."""
    out = {}
    for field in operator.STATE_AXES:
        role = operator.ENERGY_ROLES.get(field)
        if role is None and field in operator.HEAT_FIELDS:
            role = kind_registry.EnergyRole("heat", True)
        elif role is None and field in operator.WORK_FIELDS:
            role = kind_registry.EnergyRole("work", False)
        if role is not None:
            out[field] = role
    return out


def monotone_heat(operator):
    """The operator's HEAT_FIELDS whose energy role is monotone, in HEAT_FIELDS' order: the fields
    the composite's dissipation check holds non-negative and non-decreasing per element."""
    roles = energy_roles(operator)
    return tuple(k for k in operator.HEAT_FIELDS if roles[k].monotone)


def _check_energy_roles(operator):
    """ENERGY_ROLES: kind_registry.EnergyRole values on owned state fields, consistent with
    HEAT_FIELDS and WORK_FIELDS (heat only on a listed heat field, work only on a listed work field,
    stored on neither and on no suffixed field)."""
    name, roles = operator.LAW_ID, operator.ENERGY_ROLES
    if not isinstance(roles, Mapping):
        raise ValueError(f"{name}: ENERGY_ROLES maps owned state fields to EnergyRole")
    lists = {"heat": operator.HEAT_FIELDS, "work": operator.WORK_FIELDS}
    for field, role in roles.items():
        if field not in operator.STATE_AXES:
            raise ValueError(f"{name}: the energy role of {field} names no owned state field")
        if not (
            isinstance(role, kind_registry.EnergyRole)
            and role.role in kind_registry.ENERGY_ROLES
            and isinstance(role.monotone, bool)
        ):
            raise ValueError(
                f"{name}: the energy role of {field} is an EnergyRole of "
                f"{', '.join(kind_registry.ENERGY_ROLES)} with a bool monotone"
            )
        listed = [r for r, fields in lists.items() if field in fields]
        if role.role == "stored":
            if listed or field.endswith((HEAT_SUFFIX, WORK_SUFFIX)):
                raise ValueError(
                    f"{name}: {field} is stored energy, a level: it is neither a heat nor a work "
                    f"field, and carries neither {HEAT_SUFFIX} nor {WORK_SUFFIX}"
                )
        elif listed != [role.role]:
            raise ValueError(
                f"{name}: {field} is declared {role.role}, so it is listed in "
                f"{role.role.upper()}_FIELDS alone (listed in: {', '.join(listed) or 'neither'})"
            )


def _check_records(operator):
    """The run view's record declarations (module docstring), each keyed by the operator's own
    fields: OBSERVATION_AXES by its readout columns only (its state's axes are STATE_AXES), and
    RECORD_LAYERS also by the view fields it provides or closes."""
    name, own = operator.LAW_ID, set(operator.observed_columns())
    changed = own | set(operator.VIEW_FIELDS) | set(operator.CLOSES)
    tables = {
        "OBSERVATION_AXES": (operator.OBSERVATION_AXES, set(operator.READOUT_COLUMNS)),
        "UNITS": (operator.UNITS, own),
        "RECORD_KINDS": (operator.RECORD_KINDS, own),
        "ORIENTATION": (operator.ORIENTATION, own),
        "RECORD_LAYERS": (operator.RECORD_LAYERS, changed),
    }
    for table, (values, fields) in tables.items():
        if not hasattr(values, "items"):
            raise ValueError(f"{name}: {table} maps its own fields")
        unknown = sorted(set(values) - fields)
        if unknown:
            raise ValueError(f"{name}: {table} names fields not its own: {unknown}")
    for column, axes in operator.OBSERVATION_AXES.items():
        if not (isinstance(axes, tuple) and all(isinstance(a, str) and a for a in axes)):
            raise ValueError(f"{name}: OBSERVATION_AXES gives {column} a tuple of axis names")
    for field, unit in operator.UNITS.items():
        if not (isinstance(unit, str) and unit):
            raise ValueError(f"{name}: UNITS gives {field} a non-empty unit")
    for field, kind in operator.RECORD_KINDS.items():
        if kind not in RECORD_KIND_VALUES:
            raise ValueError(f"{name}: the kind of {field} is one of {RECORD_KIND_VALUES}")
    for field, sign in operator.ORIENTATION.items():
        keys = set(sign) if hasattr(sign, "keys") else set()
        form = next((f for f in ORIENTATION_FORMS if {*f, "says"} <= keys), None)
        if (
            form is None
            or not keys <= {*form, "says", *ORIENTATION_OPTIONAL}
            or not all(isinstance(sign[k], str) and sign[k] for k in keys)
        ):
            raise ValueError(
                f"{name}: the orientation of {field} gives from, to and says (a flow) or plus, "
                "minus and says (a difference), and may name who confirmed it or its source, each "
                "a non-empty string"
            )
        if sign[form[0]] == sign[form[1]]:
            raise ValueError(f"{name}: the orientation of {field} names two different roles")
    layers = {layer["id"] for layer in operator.VIEW_LAYERS or ()}
    for field, layer in operator.RECORD_LAYERS.items():
        if layer not in layers:
            raise ValueError(f"{name}: RECORD_LAYERS gives {field} a layer not of its VIEW_LAYERS")
    diagnostics = operator.RECORD_DIAGNOSTICS
    if not (isinstance(diagnostics, tuple) and len(set(diagnostics)) == len(diagnostics)):
        raise ValueError(f"{name}: RECORD_DIAGNOSTICS is a tuple of distinct field names")
    unknown = sorted(set(diagnostics) - own)
    if unknown:
        raise ValueError(f"{name}: RECORD_DIAGNOSTICS names fields not its own: {unknown}")
    references = operator.RECORD_REFERENCES
    if not hasattr(references, "items"):
        raise ValueError(f"{name}: RECORD_REFERENCES maps its own fields")
    for field, reference in references.items():
        if field not in operator.STATE_AXES or reference not in operator.LAYOUT_FIELDS:
            raise ValueError(
                f"{name}: RECORD_REFERENCES maps an own state field to an own layout field, not "
                f"{field} to {reference!r}"
            )


def _check_kinds(operator):
    """REQUIRES_KINDS (schema A): a tuple of distinct kind IDs (registry/kind_registry.py);
    FIXED_INNER_FIELDS a bool, and never with REQUIRES_KINDS."""
    name, kinds = operator.LAW_ID, operator.REQUIRES_KINDS
    if not isinstance(operator.FIXED_INNER_FIELDS, bool):
        raise ValueError(f"{name}: FIXED_INNER_FIELDS is a bool")
    if operator.FIXED_INNER_FIELDS and kinds:
        raise ValueError(f"{name}: an operator with fixed inner fields cannot require kinds")
    if not isinstance(kinds, tuple):
        raise ValueError(f"{name}: REQUIRES_KINDS is a tuple of kind IDs")
    try:
        qualified = [kind_registry.qualified(k) for k in kinds]
    except ValueError as error:
        raise ValueError(f"{name}: {error}") from None
    if len(set(qualified)) != len(qualified):
        raise ValueError(f"{name}: REQUIRES_KINDS names a kind twice")


def _check_layers(operator):
    """VIEW_LAYERS, when declared (docs/RUN_VIEW_DESIGN.md §3)."""
    layers = operator.VIEW_LAYERS
    if layers is None:
        return
    name = operator.LAW_ID
    if not isinstance(layers, tuple) or not layers:
        raise ValueError(f"{name}: VIEW_LAYERS is a non-empty tuple of layers")
    for layer in layers:
        if not isinstance(layer, dict) or set(layer) != LAYER_KEYS:
            raise ValueError(f"{name}: a view layer is a dict of {sorted(LAYER_KEYS)}")
        if not all(isinstance(layer[k], str) and layer[k] for k in ("id", "label")):
            raise ValueError(f"{name}: a view layer's id and label are non-empty strings")
        if layer["representation"] not in REPRESENTATIONS:
            raise ValueError(f"{name}: a view layer's representation is one of {REPRESENTATIONS}")


def _named_string(value):
    return isinstance(value, str) and bool(value)


def _check_quantities(operator):
    """R3's declarations (module docstring): an owner's QUANTITIES map distinct names to (entity
    axis, unit), non-empty strings, with quantities defined; a reader's QUANTITY_READS map other
    laws to tuples of distinct names."""
    name = operator.LAW_ID
    own = operator.QUANTITIES
    if not isinstance(own, Mapping) or not all(
        _named_string(key)
        and isinstance(value, tuple)
        and len(value) == 2
        and all(map(_named_string, value))
        for key, value in own.items()
    ):
        raise ValueError(f"{name}: QUANTITIES maps names to (entity axis, unit) strings")
    if own and not _defined_below_operator(operator, "quantities"):
        raise ValueError(f"{name}: an owner of readable quantities defines quantities")
    reads = operator.QUANTITY_READS
    if not isinstance(reads, Mapping) or not all(
        _named_string(law)
        and isinstance(names, tuple)
        and names
        and all(map(_named_string, names))
        and len(set(names)) == len(names)
        for law, names in reads.items()
    ):
        raise ValueError(f"{name}: QUANTITY_READS maps owner laws to tuples of distinct names")
    if name in reads:
        raise ValueError(f"{name}: a reader reads no quantity of its own law")


def _check_routes(operator):
    """B1′'s declarations (module docstring): a target's routable controls are its own control
    fields, each "rate", read in exact half-steps (a split part kept split under RK4, no in-step
    process); a source's routes are distinct (target law, control field) pairs, never to its own
    law, with rate_factors defined."""
    name = operator.LAW_ID
    routable = operator.ROUTABLE_CONTROLS
    if not isinstance(routable, Mapping) or any(
        field not in operator.CONTROL_FIELDS or kind not in ROUTE_KINDS
        for field, kind in routable.items()
    ):
        raise ValueError(
            f"{name}: ROUTABLE_CONTROLS maps its own control fields to one of {ROUTE_KINDS}"
        )
    if routable and not (operator.SPLIT and operator.RK4 == "split" and not operator.PROCESS):
        raise ValueError(
            f"{name}: a routable control is read in exact half-steps only: a split part kept "
            "split under RK4, and no in-step process"
        )
    if routable and not _defined_below_operator(operator, "routable_elements"):
        raise ValueError(f"{name}: a routable operator defines routable_elements")
    routes = operator.RATE_ROUTES
    pairs = isinstance(routes, tuple) and all(
        isinstance(route, tuple) and len(route) == 2 and all(map(_named_string, route))
        for route in routes
    )
    if not pairs or len(set(routes)) != len(routes):
        raise ValueError(f"{name}: RATE_ROUTES is a tuple of distinct (target law, field) pairs")
    if any(law == name for law, _ in routes):
        raise ValueError(f"{name}: a route source routes no factor to its own controls")
    if routes and not _defined_below_operator(operator, "rate_factors"):
        raise ValueError(f"{name}: a route source defines rate_factors")
    record = operator.FACTOR_RECORD
    if record is not None and (
        record not in operator.STATE_AXES or not _defined_below_operator(operator, "factor_record")
    ):
        raise ValueError(f"{name}: FACTOR_RECORD is an owned state field, with factor_record")


def _check_scopes(operator):
    """Door S's declarations (docs/SCOPED_COMPOSITION_DESIGN.md §2), with per-stage read modes
    (docs/OPERATOR_COMPOSITION_DESIGN.md §3, C3) and each declared stage one of its parts'."""
    name = operator.LAW_ID
    stages = part_stages(operator)
    owner = not (operator.EVENT or operator.SPLIT or operator.PROCESS)  # A part-less state owner.
    for field, change in operator.VIEW_CHANGES.items():
        if not isinstance(change, Change):
            raise ValueError(f"{name}: VIEW_CHANGES maps {field} to a Change")
        if field in operator.CLOSES:
            if change.contribution != "and":
                raise ValueError(f"{name}: a closer's change of {field} is 'and'")
            if change.scoped:
                raise ValueError(
                    f"{name}: closers change whole masks in R (docs/SCOPED_COMPOSITION_DESIGN.md "
                    f"§3, rule 6), so {field} is not scoped"
                )
        elif field not in operator.VIEW_FIELDS:
            raise ValueError(
                f"{name}: VIEW_CHANGES refines a field it provides or closes, not {field}"
            )
        elif change.contribution not in CONTRIBUTIONS:
            raise ValueError(f"{name}: the change of {field} is one of {CONTRIBUTIONS}")
        if change.stage not in CHANGE_STAGES:
            raise ValueError(f"{name}: the change of {field} is at a stage of {CHANGE_STAGES}")
        if change.stage not in stages and not (change.stage == "split" and owner):
            raise ValueError(
                f"{name}: the change of {field} is at stage {change.stage}, which none of its "
                "parts runs at"
            )
    for field, declared in operator.SCOPED_READS.items():
        reads = (declared,) if isinstance(declared, Read) else declared
        if not (type(reads) is tuple and reads and all(isinstance(r, Read) for r in reads)):
            raise ValueError(
                f"{name}: SCOPED_READS maps {field} to a Read, or to a tuple of Reads at "
                "distinct stages"
            )
        if len({r.stage for r in reads}) != len(reads):
            raise ValueError(f"{name}: SCOPED_READS reads {field} once per stage")
        modes = {r.mode for r in reads}
        for read in reads:
            if read.mode not in READ_MODES or read.stage not in READ_STAGES:
                raise ValueError(
                    f"{name}: the read of {field} has a mode of {READ_MODES} and a stage of "
                    f"{READ_STAGES}"
                )
            listed = dict(current=operator.VIEW_READS, fixed=operator.CONFLICTS_VIEW).get(read.mode)
            if listed is not None and field not in listed:
                kind = "VIEW_READS" if read.mode == "current" else "CONFLICTS_VIEW"
                raise ValueError(f"{name}: a {read.mode} read of {field} needs it in {kind}")
            # A reference read beside a current one at another stage is the two-mode read (C3):
            # existence checks on the declared slots beside rates on the merged view.
            if read.mode == "reference" and (
                field in (*operator.CONFLICTS_VIEW, *operator.VIEW_FIELDS)
                or (field in operator.VIEW_READS and "current" not in modes)
            ):
                raise ValueError(
                    f"{name}: a reference read of {field} is not also read, held as declared or "
                    "provided, except beside a current read of it at another stage"
                )
            # A factor operator reads at stage inner through its control view (R2).
            points = (*stages, "inner") if operator.CONTROL_FACTORS else stages
            if read.stage in ("event", "split", "inner") and read.stage not in points:
                raise ValueError(
                    f"{name}: the read of {field} is at stage {read.stage}, which none of its "
                    "parts runs at"
                )
        if field in operator.VIEW_READS and "current" not in modes:
            raise ValueError(f"{name}: a VIEW_READS field, {field}, has a current read")
        if field in operator.CONFLICTS_VIEW and "fixed" not in modes:
            raise ValueError(f"{name}: a CONFLICTS_VIEW field, {field}, has a fixed read")
    if factor_reads(operator):  # R2: the composite passes view= to each control-view hook.
        for hook in ("control_factors", "factor_valid", "factor_record"):
            if _defined_below_operator(operator, hook) and not _takes_view(getattr(operator, hook)):
                raise ValueError(
                    f"{name}: it reads at the control view, so its {hook} takes view=None (R2: "
                    "a routed half-step's factor_record passes none)"
                )


def _takes_view(method):
    """Whether `method` takes the keyword view with a default, or any keyword."""
    parameters = inspect.signature(method).parameters.values()
    return any(
        (
            p.name == "view"
            and p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)
            and p.default is not p.empty
        )
        or p.kind is p.VAR_KEYWORD
        for p in parameters
    )
