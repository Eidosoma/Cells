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
  other owned field may carry those suffixes.
* Entity writes, ``ENTITY_WRITES``: inner state fields it changes, each mapped to
  the owned accumulators that book the change, so the inner ledgers close with
  the operator's ledger terms (Δx = Σ over writers of their booked terms).
* View fields, ``VIEW_FIELDS``: inner layout fields it provides from state.
  Each field has exactly one provider; the composite refuses a second one.
  ``CONTROL_FACTORS``: inner control fields it multiplies; several factors on one
  field combine as a product in declared order. ``CONFLICTS_VIEW``: inner fields
  it reads as declared, so no other operator may provide them.
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
  schedule hook or definition-check hook of its own.
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
  parsed and checked at the definition (event times are exact multiples of dt).
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
  - ``BOOKS_AT_VIEW`` on an event map: the composite passes ``view``, a function of state
    giving its view, when a field input is provided.
* Scoped composition, door S (docs/SCOPED_COMPOSITION_DESIGN.md), refining the view
  declarations per field:
  - ``VIEW_CHANGES`` ({field: Change}): what its contribution to a field it provides
    (``VIEW_FIELDS``) or closes (``CLOSES``) does: ``replace``, ``add`` or ``multiply`` (a
    closer's is ``and``), at stage ``event`` or ``split``. A scoped change is taken only on
    the slots ``changed_slots`` names (host) and ``view_slots`` masks (device); otherwise on
    every slot. Defaults (``view_change``): ``replace`` (``and`` for a closer) on every slot;
  - ``SCOPED_READS`` ({field: Read}): the mode of a read, ``current`` (the merged view at its
    stage: a ``VIEW_READS`` field), ``fixed`` (the declared value taken as the physical one:
    a ``CONFLICTS_VIEW`` field) or ``reference`` (the bound value as data, an anchor), and
    its stage. A scoped read covers only the slots ``read_slots`` names. Defaults
    (``scoped_read``): ``current`` for each ``VIEW_READS`` field, ``fixed`` for each
    ``CONFLICTS_VIEW`` field, on every slot.
  Two changes or a change and a read of one field meet only on the slots both name; the
  composite admits a pair per slot (pump_composite.structure_errors and scope_errors) and
  merges each change onto the accumulated view on its slots (pump_composite_adapter.view).
* Species identity and the step (core/species_registry.py, D176): ``IDENTITY_ROLE``
  ("author" for an operator that declares the species it writes, "user" for one that refers to
  species others declare) and ``species_identities``; ``moves_in_step``, the rows an in-step
  process moves inside the inner step, which an operator with ``PROCESS`` declares.
* The run view (docs/RUN_VIEW_DESIGN.md §3; cells/run_view.py reads them, host side only):
  - ``VIEW_LAYERS``: its layers, each {"id", "label", "representation"}; None: undeclared,
    which the run-view writer refuses;
  - ``view_events``: its events with their entities by id, each entity one {set: id}; the
    default gives the births and retirements of ``living_intervals`` at {"cell": id};
  - ``view_sets(spec, declaration)``: the view's set of each axis of its own (an axis of its
    STATE_AXES or OBSERVATION_AXES that the inner model does not have), as {axis: {"id",
    "ids", optional "holds", optional "on": (set id, entity ids)}}; the default declares none;
  - ``OBSERVATION_AXES`` ({readout column: axes}): its READOUT_COLUMNS' axes, as STATE_AXES
    gives its state's;
  - ``UNITS`` ({field: unit}): the unit of an own field whose name carries no unit suffix;
  - ``RECORD_KINDS`` ({field: kind}), kind one of RECORD_KIND_VALUES: ``level``, ``amount``,
    ``cumulative`` (a total since the start) or ``rate``;
  - ``ORIENTATION`` ({field: {"from", "to", "says"}}): which way a positive value moves, by
    the roles of the record's entity set (the writer checks the roles; ``confirmed`` may
    name who confirmed it);
  - ``RECORD_LAYERS`` ({field: layer id}): the layer, one of its VIEW_LAYERS, of an own field
    or of a view field it provides or closes (door S's merged view, a record of the view);
    needed only with more than one layer.
  None of them changes a program, a binding or a checkpoint.

Methods take the composite's full state, control and layout NamedTuples, whose
fields are the inner model's followed by each operator's in declared order.
Defaults below are the idle answers: no parts, no terms, no columns.
"""

from types import MappingProxyType
from typing import NamedTuple

from cells.core import kind_registry

HEAT_SUFFIX = "_dissipated_energy_pJ"
WORK_SUFFIX = "_work_pJ"
RK4_MODES = ("coupled", "split")
IDENTITY_ROLES = ("author", "user")
REPRESENTATIONS = ("simulated", "modelled", "prescribed")
LAYER_KEYS = frozenset({"id", "label", "representation"})
# The run view's record kinds and sign keys (docs/RUN_VIEW_DESIGN.md §3; cells/run_view.py).
RECORD_KIND_VALUES = ("level", "amount", "cumulative", "rate")
ORIENTATION_KEYS = frozenset({"from", "to", "says"})
ORIENTATION_OPTIONAL = frozenset({"confirmed"})
# Door S (docs/SCOPED_COMPOSITION_DESIGN.md §2).
CONTRIBUTIONS = ("replace", "add", "multiply")  # Of a provided field; a closer's is "and".
COMMUTING = ("add", "multiply", "and")  # Overlaps admitted, applied in declared order.
CHANGE_STAGES = ("event", "split")
READ_MODES = ("reference", "current", "fixed")
READ_STAGES = ("event", "split", "inner", "end", "observe")


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
    LAYOUT_FIELDS = ()
    CONTROL_FIELDS = ()
    EXPERIMENT_KEYS = ()
    VIEW_FIELDS = ()
    CONTROL_FACTORS = ()
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
    # Its parts call the inner model's structure-bound functions (an event map's kinetics, the
    # field solve): the composite passes the inner implementation object as `inner=` to its
    # event, half_step and rates calls and to initial_values (static), and host methods reach
    # it as model.inner (D176; docs/INNER_MODEL_V4_DESIGN.md §7.4). Every other call is unchanged.
    USES_INNER = False
    # Door S (module docstring): refinements of the view declarations, per field.
    VIEW_CHANGES = MappingProxyType({})
    SCOPED_READS = MappingProxyType({})
    # Species identity (core/species_registry.py, D176): "author" for an operator that declares
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
    # A declaration with no part and no field (module docstring; check_declarations).
    DECLARATION_ONLY = False

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
        fixed for CONFLICTS_VIEW, on every slot), or None."""
        if field in cls.SCOPED_READS:
            return cls.SCOPED_READS[field]
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

    def species_identities(self, declaration):
        """The species identities it declares: items with id, catalogue and evidence; ()."""
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
        """{inner control field: multiplier} for CONTROL_FACTORS."""
        return {}

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
        )
    ):
        raise ValueError(
            f"{name}: an operator contributes at least one part, or is a state owner that "
            "provides views of fields later operators write (ACCEPTS_WRITES), or owns only "
            "fields later operators write, or is a declaration (DECLARATION_ONLY)"
        )
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
    if operator.PROCESS and not _defined_below_operator(operator, "moves_in_step"):
        raise ValueError(f"{name}: an in-step process declares the rows it moves (moves_in_step)")
    if operator.IDENTITY_ROLE not in IDENTITY_ROLES:
        raise ValueError(f"{name}: IDENTITY_ROLE is one of {IDENTITY_ROLES}")
    _check_layers(operator)
    _check_records(operator)
    _check_kinds(operator)
    return operator


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
        if not (ORIENTATION_KEYS <= keys <= ORIENTATION_KEYS | ORIENTATION_OPTIONAL) or not all(
            isinstance(sign[k], str) and sign[k] for k in keys
        ):
            raise ValueError(
                f"{name}: the orientation of {field} gives from, to and says (and may name who "
                "confirmed it), each a non-empty string"
            )
        if sign["from"] == sign["to"]:
            raise ValueError(f"{name}: the orientation of {field} names two different roles")
    layers = {layer["id"] for layer in operator.VIEW_LAYERS or ()}
    for field, layer in operator.RECORD_LAYERS.items():
        if layer not in layers:
            raise ValueError(f"{name}: RECORD_LAYERS gives {field} a layer not of its VIEW_LAYERS")


def _check_kinds(operator):
    """REQUIRES_KINDS (schema A): a tuple of distinct kind IDs (a bare ID is in the cells
    namespace, core/kind_registry.py); FIXED_INNER_FIELDS a bool, and never with REQUIRES_KINDS."""
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


def _check_scopes(operator):
    """Door S's declarations (docs/SCOPED_COMPOSITION_DESIGN.md §2)."""
    name = operator.LAW_ID
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
    for field, read in operator.SCOPED_READS.items():
        if not isinstance(read, Read):
            raise ValueError(f"{name}: SCOPED_READS maps {field} to a Read")
        if read.mode not in READ_MODES or read.stage not in READ_STAGES:
            raise ValueError(
                f"{name}: the read of {field} has a mode of {READ_MODES} and a stage of "
                f"{READ_STAGES}"
            )
        listed = dict(current=operator.VIEW_READS, fixed=operator.CONFLICTS_VIEW).get(read.mode)
        if listed is not None and field not in listed:
            kind = "VIEW_READS" if read.mode == "current" else "CONFLICTS_VIEW"
            raise ValueError(f"{name}: a {read.mode} read of {field} needs it in {kind}")
        if read.mode == "reference" and field in (
            *operator.VIEW_READS,
            *operator.CONFLICTS_VIEW,
            *operator.VIEW_FIELDS,
        ):
            raise ValueError(
                f"{name}: a reference read of {field} is not also read, held as declared or "
                "provided"
            )
