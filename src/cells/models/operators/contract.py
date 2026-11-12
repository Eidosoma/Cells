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
  (scheduled replacement: its event map restarts its formation law's state).
  ``RK4`` declares a split part's behaviour under an RK4 inner step: "coupled"
  (its rates join the coupled right-hand side, which RK4 integrates unsplit) or
  "split" (exact half-steps kept around the inner RK4 step).
* Ledgers: ``LEDGERS`` with ``LEDGER_DIAGNOSTICS`` and ``LEDGER_MESSAGE`` (its
  own ledgers and their rounding bounds), plus terms added to the inner ledgers
  and to their rounding magnitudes (methods below).
* Domain and refusal: ``domain_valid`` and ``control_valid``; any failure refuses
  the whole step, which returns the start state. ``REQUIRES``: laws that must
  precede it in the operator list.
* Schedule: ``EXPERIMENT_KEYS`` (its schedule in the definition's experiment),
  parsed and checked at the definition (event times are exact multiples of dt).

Methods take the composite's full state, control and layout NamedTuples, whose
fields are the inner model's followed by each operator's in declared order.
Defaults below are the idle answers: no parts, no terms, no columns.
"""

from types import MappingProxyType

HEAT_SUFFIX = "_dissipated_energy_pJ"
WORK_SUFFIX = "_work_pJ"
RK4_MODES = ("coupled", "split")


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
    # Ledgers and readouts.
    LEDGERS = ()
    LEDGER_DIAGNOSTICS = ()
    LEDGER_MESSAGE = ""
    READOUT = None
    READOUT_COLUMNS = ()
    FINITE_RATES = False
    REQUIRES = ()

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

    def control_factors(self, state, p, *, xp):
        """{inner control field: multiplier} for CONTROL_FACTORS."""
        return {}

    def event(self, state, control, p, *, xp):
        """(state, consistent) after the events due at the step start."""
        raise NotImplementedError

    def half_step(self, state, h, control, p, *, xp):
        """(state, valid or None) after h of the split part on its own variables."""
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

    def own_bounds(self, magnitudes, steps):
        return ()

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        """{column: value} for this operator's state fields and READOUT_COLUMNS."""
        return {k: getattr(state, k) for k in self.STATE_AXES}


def check_declarations(operator):
    """Refuse an operator class whose declarations break the contract."""
    name = operator.LAW_ID
    if not isinstance(name, str) or "@" not in name:
        raise ValueError(f"Operator {operator!r} needs a versioned law ID")
    if operator.SPLIT and operator.RK4 not in RK4_MODES:
        raise ValueError(f"{name}: a split part declares its RK4 mode, one of {RK4_MODES}")
    if not operator.SPLIT and operator.RK4 is not None:
        raise ValueError(f"{name}: an RK4 mode needs a split part")
    if not (operator.EVENT or operator.SPLIT or operator.PROCESS):
        raise ValueError(f"{name}: an operator contributes at least one part")
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
    return operator
