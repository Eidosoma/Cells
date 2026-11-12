"""resolved_pump_composite@1: resolved_pump_tissue@3's own step plus declared operators.

Design: docs/CELL_DIVISION_DESIGN.md §3 (D142, D143). Definition:
core/pump_composite_spec.py. The inner model's names live only in the entity
adapter (models/pump_composite_adapter.py); operators implement the contract of
models/operators/contract.py. implementation(inner, laws) builds one object per
inner identity and ordered operator list (cached, so its state, layout and
control types and its step functions are stable jit inputs); registry.get_model
returns it for a composite definition. Object structure lives in that object and
the operators; every step function is pure JAX over arrays.

The step (§3.4), for an IMEX inner step:

    Phi_dt = P1(dt/2) o ... o Pm(dt/2) o I_dt[view] o Pm(dt/2) o ... o P1(dt/2) o E

* E: the operators' event maps at the step start, in declared order;
* P: their split parts on their own variables (the first half in declared order,
  the second in reverse);
* I: the inner model's own checked step at the view of its layout (the
  providers' fields) and control (availabilities times the declared factors),
  behind jax.lax.optimization_barrier on its inputs and outputs, so XLA compiles
  it as one unit; with an active in-step process, the inner IMEX step with that
  process through @3's hook, whose applied transfer and heat the operator books.
  Geometry and every view are frozen inside I.
* Any refused piece refuses the whole step: the start state is returned. Idle
  parts select the inner value and never add a computed zero; branches are static
  (by the operator list and layout shapes), never by value. The empty composition
  is the inner step itself.

RK4 inner steps (reference runs; a contract addition, §3.4 covers the split
form): when an operator's split part is declared "coupled" (water) or an
in-step process is present, RK4 integrates the coupled right-hand side (the inner
readouts at the view, with the process, plus the operators' rates) unsplit, as
resolved_pump_water@1 does; such compositions refuse event maps, split parts kept
"split" and integer state. Otherwise the events and exact half-steps stay around
the inner RK4 step, as resolved_pump_replacement@1 does.

Checks: host and device use the inner model's own row checks
(surface_pump.checked_rows, surface_pump_checks.row_checks, surface_pump.
ledger_limits) on the declared layout, with the inner balances plus the
operators' terms (in declared order), the operators' own ledgers after the inner
ones, the rounding magnitudes with the operators' terms, and the dissipation
fields with the operators' heat. Without operators every check is the inner
model's exactly.
"""

from dataclasses import make_dataclass, replace
from functools import cache
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core.errors import NumericalError
from cells.core.pump_composite_spec import MODEL_ID, entries, identity, projection
from cells.core.specs import ChannelChange, ConfigError
from cells.models import pump_composite_adapter as pump3
from cells.models.surface_pump_checks import row_checks
from cells.numerics.fixed_step import rk4_checked_step

OBSERVER_ID = "resolved_pump_composite_accepted_grid_readouts@1"
STAGE_DOMAIN_ID = "positive_resolved_inventory_gates_atp_operator_domains@1"
SPLITTING_ID = "events_then_symmetric_operator_halves@1"
INNERS = {pump3.MODEL_ID: pump3}
# Inner control fields and the experiment schedules that hold them for observation.
HELD_SCHEDULES = dict(
    membrane="membranes",
    junction="junctions",
    channel="channels",
    pump="pumps",
    calcium_pump="calcium_pumps",
)


def _and(a, b):
    """Conjunction of validity flags, where None means nothing to check."""
    if a is None:
        return b
    if b is None:
        return a
    return a & b


@cache
def implementation(inner_model, laws):
    """The composite for one inner identity and ordered operator law tuple."""
    from cells.models.operators import OPERATORS

    if inner_model not in INNERS:
        raise ConfigError("Composite inner model must be one of " + ", ".join(INNERS))
    unknown = [law for law in laws if law not in OPERATORS]
    if unknown:
        raise ConfigError("Unregistered operator laws: " + ", ".join(unknown))
    return Composition(INNERS[inner_model], tuple(OPERATORS[law] for law in laws))


def model_for(spec_model):
    return implementation(spec_model.inner_model, composite_spec.operator_laws(spec_model))


def check_definition(spec):
    model_for(spec.model).check_definition(spec)


def compact(spec):
    m = spec.model
    return replace(
        spec,
        execution=replace(
            spec.execution,
            capacity=len(m.cells),
            extracellular_capacity=len(m.extracellular),
            membrane_capacity=len(m.membranes),
            edge_capacity=len(m.junctions),
            face_capacity=len(m.faces),
            channel_capacity=len(m.channels),
        ),
    )


def held_schedules(base, control, names):
    """The inner definition with each named availability held at the given values.

    The inner observer reads its controls from its definition, so a row observed
    at an effective (factored) availability observes this definition.
    """
    e = base.experiment
    held = {}
    for name in names:
        attribute = HELD_SCHEDULES[name]
        count = len(getattr(e, attribute))
        values = np.asarray(getattr(control, name))[:count]
        held[attribute] = tuple((ChannelChange(0.0, float(v)),) for v in values)
    return replace(base, experiment=replace(e, **held))


def structure_errors(inner, operators):
    """Contract violations of an ordered operator list on an inner model (empty: none)."""
    errors = []
    laws = [op.LAW_ID for op in operators]
    if len(set(laws)) != len(laws):
        errors.append("an operator law appears twice")
    for kind, inner_names, attribute in (
        ("state", inner.STATE_FIELDS, "STATE_AXES"),
        ("layout", inner.LAYOUT_TYPE._fields, "LAYOUT_FIELDS"),
        ("control", inner.CONTROL_FIELDS, "CONTROL_FIELDS"),
    ):
        names = list(inner_names)
        for op in operators:
            names += list(getattr(op, attribute))
        if len(set(names)) != len(names):
            errors.append(f"two owners of one {kind} field")
    providers = {}
    for op in operators:
        for name in op.VIEW_FIELDS:
            if name not in inner.VIEW_FIELDS:
                errors.append(f"{op.LAW_ID} provides {name}, which is not an inner view field")
            if name in providers:
                errors.append(f"two providers of the view field {name}")
            providers[name] = op.LAW_ID
        for name in op.CONTROL_FACTORS:
            if name not in inner.CONTROL_FIELDS:
                errors.append(f"{op.LAW_ID} multiplies {name}, which is not an inner control")
        for name in op.STATE_RESETS:
            if name not in inner.STATE_FIELDS:
                errors.append(f"{op.LAW_ID} resets {name}, which is not inner state")
    accepted, provided, columns = {}, set(), {k: ["inner"] for k in inner.OBSERVATION_FIELDS}
    for op in operators:
        # Writers follow owners: an entity write targets inner state or a field an
        # earlier operator accepts.
        for name in op.ENTITY_WRITES:
            if name not in inner.STATE_FIELDS and name not in accepted:
                errors.append(
                    f"{op.LAW_ID} writes {name}, which is neither inner state nor accepted "
                    "by an earlier operator"
                )
        accepted.update(dict.fromkeys(op.ACCEPTS_WRITES, op.LAW_ID))
        for name in op.VIEW_READS:
            if name not in provided:
                errors.append(f"{op.LAW_ID} reads the view {name}; no earlier operator provides it")
        provided.update(op.VIEW_FIELDS)
        # One owner per observation column; replacement is a declared chain in order.
        for name in op.observed_columns():
            if name in columns:
                errors.append(f"{op.LAW_ID} adds the column {name}, which {columns[name][-1]} owns")
            else:
                columns[name] = [op.LAW_ID]
        for name in op.REPLACES:
            if name in columns:
                columns[name].append(op.LAW_ID)
            else:
                errors.append(f"{op.LAW_ID} replaces {name}, which no earlier owner observes")
    for op in operators:
        for name in op.CONFLICTS_VIEW:
            if providers.get(name, op.LAW_ID) != op.LAW_ID:
                errors.append(
                    f"{op.LAW_ID} reads {name} as declared, but {providers[name]} provides it"
                )
    for i, op in enumerate(operators):
        for law in op.REQUIRES:
            if law not in laws[:i]:
                errors.append(f"{op.LAW_ID} requires {law} before it")
    if sum(op.PROCESS for op in operators) > 1:
        errors.append(
            "at most one in-step membrane process (the inner hook books one combined transfer)"
        )
    return errors


def field_map(inner, operators):
    """The composition's field-to-owner map (written to the run manifest).

    State fields with their owner and writers (entity writes and resets), layout and
    control fields with their owner, view fields with their provider and readers, and
    each observation column's owner chain (its owner is the last).
    """
    state = {k: {"owner": "inner", "writers": []} for k in inner.STATE_FIELDS}
    layout = dict.fromkeys(inner.LAYOUT_TYPE._fields, "inner")
    control = dict.fromkeys(inner.CONTROL_FIELDS, "inner")
    columns = {k: ["inner"] for k in inner.OBSERVATION_FIELDS}
    for op in operators:
        state |= {k: {"owner": op.LAW_ID, "writers": []} for k in op.STATE_AXES}
        layout |= dict.fromkeys(op.LAYOUT_FIELDS, op.LAW_ID)
        control |= dict.fromkeys(op.CONTROL_FIELDS, op.LAW_ID)
        columns |= {k: [op.LAW_ID] for k in op.observed_columns()}
        for k in op.REPLACES:
            columns[k] = [*columns[k], op.LAW_ID]
    for op in operators:
        for k in dict.fromkeys((*op.ENTITY_WRITES, *op.STATE_RESETS)):
            state[k]["writers"].append(op.LAW_ID)
    views = {
        k: {"provider": op.LAW_ID, "readers": [r.LAW_ID for r in operators if k in r.VIEW_READS]}
        for op in operators
        for k in op.VIEW_FIELDS
    }
    return dict(state=state, layout=layout, control=control, views=views, observations=columns)


def accepted_writers(operators):
    """{owner law: ((writer, the owner's ledgers its writes reach), ...)} in declared order."""
    owners = {k: op for op in operators for k in op.ACCEPTS_WRITES}
    writers = {}
    for op in operators:
        for field in op.ENTITY_WRITES:
            if field in owners:
                owner = owners[field]
                reached = writers.setdefault(owner.LAW_ID, {}).setdefault(op.LAW_ID, [op, []])
                reached[1] += [k for k in owner.ACCEPTS_WRITES[field] if k not in reached[1]]
    return {law: tuple((w, tuple(k)) for w, k in byw.values()) for law, byw in writers.items()}


class Composition:
    """The model protocol of one composition (attributes as a model module's)."""

    def __init__(self, inner, operators):
        errors = structure_errors(inner, operators)
        if errors:
            raise ConfigError("Invalid operator composition: " + "; ".join(errors))
        self.inner, self.operators = inner, operators
        self.FIELD_MAP = field_map(inner, operators)
        self.writers_of = accepted_writers(operators)
        self.observed_keys = {op.LAW_ID: {*op.observed_columns(), *op.REPLACES} for op in operators}
        self.laws = tuple(op.LAW_ID for op in operators)
        self.MODEL_ID = MODEL_ID
        self.OBSERVER_ID = OBSERVER_ID
        self.OBSERVATION_SAMPLING = inner.OBSERVATION_SAMPLING
        self.STAGE_DOMAIN_ID = STAGE_DOMAIN_ID
        self.BATCH_CAPACITIES = inner.BATCH_CAPACITIES
        self.ENERGY_RTOL = inner.ENERGY_RTOL
        self.EXPLICIT_STEP_BOUND = inner.EXPLICIT_STEP_BOUND
        # Parts, in declared order.
        self.events = tuple(op for op in operators if op.EVENT)
        self.splits = tuple(op for op in operators if op.SPLIT)
        self.providers = tuple(op for op in operators if op.VIEW_FIELDS)
        self.factors = tuple(op for op in operators if op.CONTROL_FACTORS)
        self.factored = tuple(dict.fromkeys(k for op in self.factors for k in op.CONTROL_FACTORS))
        self.domain_views = tuple(op for op in operators if op.VIEW_FOLLOWS_SPLIT)
        self.process_operator = next((op for op in operators if op.PROCESS), None)
        self.coupled = any(op.SPLIT and op.RK4 == "coupled" for op in operators) or (
            self.process_operator is not None
        )
        self.field_inputs = any(set(op.VIEW_FIELDS) & set(inner.FIELD_INPUTS) for op in operators)
        # Types: the inner model's fields, then each operator's, in declared order.
        self.STATE_AXES = dict(inner.STATE_AXES)
        for op in operators:
            self.STATE_AXES.update(op.STATE_AXES)
        self.STATE_DTYPES = {k: v for op in operators for k, v in op.STATE_DTYPES.items()}
        self.STATE_TYPE = NamedTuple("CompositeState", [(k, object) for k in self.STATE_AXES])
        extra = tuple(k for op in operators for k in op.LAYOUT_FIELDS)
        self.LAYOUT_TYPE = NamedTuple(
            "CompositeLayout", [(k, object) for k in (*inner.LAYOUT_TYPE._fields, *extra)]
        )
        self.FLOOR_LAYOUT_TYPE = NamedTuple(
            "CompositeFloorLayout",
            [(k, object) for k in (*inner.FLOOR_LAYOUT_TYPE._fields, *extra)],
        )
        self.CONTROL_FIELDS = (
            *inner.CONTROL_FIELDS,
            *(k for op in operators for k in op.CONTROL_FIELDS),
        )
        self.CONTROL_TYPE = composite_spec.control_type(self.CONTROL_FIELDS)
        self.READOUTS = tuple(op.READOUT for op in operators if op.READOUT)
        self.VALUES_TYPE = NamedTuple(
            "CompositeValues",
            [(k, object) for k in ("field", "derivative", "ionic", *self.READOUTS, "valid")],
        )
        self.DISSIPATION_FIELDS = (
            *inner.DISSIPATION_FIELDS,
            *(k for op in operators for k in op.HEAT_FIELDS),
        )
        self.own_ledger_operators = tuple(op for op in operators if op.LEDGERS)
        self.LEDGERS = (*inner.LEDGERS, *(k for op in operators for k in op.LEDGERS))
        self.LEDGER_DIAGNOSTICS = (
            *inner.LEDGER_DIAGNOSTICS,
            *(k for op in operators for k in op.LEDGER_DIAGNOSTICS),
        )
        self.DEVICE_CHECKS = ("domain", *self.LEDGERS, "dissipation")
        self.DEVICE_DIAGNOSTICS = (
            *("max_" + k for k in self.LEDGER_DIAGNOSTICS),
            "max_energy_balance_relative",
            "max_global_charge_bound_ratio",
        )
        self.OBSERVATION_FIELDS = (
            *inner.OBSERVATION_FIELDS,
            *(k for op in operators for k in (*op.STATE_AXES, *op.READOUT_COLUMNS)),
        )
        self.Observations = make_dataclass(
            "CompositeObservations",
            [(k, np.ndarray) for k in self.OBSERVATION_FIELDS],
            frozen=True,
        )

        # Plain functions where callers read attributes off them.
        def domain_valid(state, p, active, *, xp=jnp):
            return self._domain(state, p, active, xp=xp)

        domain_valid.with_control = self.control_domain_valid
        self.domain_valid = domain_valid

    def __repr__(self):
        return f"<{MODEL_ID} {self.inner.MODEL_ID} [{', '.join(self.laws)}]>"

    # ------------------------------------------------------------ binding

    parameters = staticmethod(pump3.parameters)
    physical_amounts = staticmethod(pump3.physical_amounts)
    rebind = staticmethod(pump3.rebind)
    device_check_constants = staticmethod(pump3.device_check_constants)

    def composition_identity(self, spec):
        return identity(spec.model)

    def field_owners(self, spec):
        """The field-to-owner map (field_map), written to run manifests."""
        return self.FIELD_MAP

    def batch_signature(self, model):
        """The run identity and array axes of `model` (any composition: batches compare
        every world's signature with the first world's)."""
        from cells.models.operators import OPERATORS

        laws = composite_spec.operator_laws(model)
        parts = tuple(part for d in model.operators for part in OPERATORS[d.law].batch_signature(d))
        return (MODEL_ID, model.inner_model, laws, *self.inner.batch_signature(model), *parts)

    def working_size(self, spec):
        return self.inner.working_size(projection(spec)) + sum(
            op.working_size(spec) for op in self.operators
        )

    def initial_values(self, spec):
        state, p = self.inner.initial_values(projection(spec))
        values, layout = state._asdict(), p._asdict()
        for op, declaration, schedule in entries(spec):
            owned, bound = op.initial_values(spec, declaration, schedule, state, p)
            values.update(owned)
            layout.update(bound)
        kind = (
            self.FLOOR_LAYOUT_TYPE if type(p) is self.inner.FLOOR_LAYOUT_TYPE else self.LAYOUT_TYPE
        )
        return self.STATE_TYPE(**values), kind(**layout)

    def view(self, p, state, *, xp=jnp):
        return self.inner.view(p, state, self.providers, xp=xp)

    def control_view(self, control, state, p, *, xp=jnp):
        return self.inner.control_view(control, state, p, self.factors, xp=xp)

    def inner_state(self, state):
        return self.inner.inner_state(state)

    # ------------------------------------------------------------ the step

    def checked_step(self, state, dt, control, p, active):
        """The composite step (module docstring); RK4 for an empty tableau."""
        if not self.operators:  # The empty composition is the inner step.
            moved, ok = self.inner.checked_step(
                self.inner.inner_state(state),
                dt,
                self.inner.inner_control(control),
                self.inner.inner_layout(p),
                active,
            )
            return state._replace(**moved._asdict()), ok
        if p.imex_explicit.shape[0] == 0 and self.coupled:
            return rk4_checked_step(self.rhs, self.domain_valid, state, dt, control, p, active)
        return self.split_step(state, dt, control, p)

    def split_step(self, state, dt, control, p, *, xp=jnp):
        """E, the first halves, the inner step at the view, the second halves.

        The inner step is @3's checked step (IMEX, or RK4 for an empty tableau
        without coupled operators), or @3's IMEX step with the in-step process.
        A refused piece refuses the step, which returns the start state.
        """
        idle = tuple(op for op in self.operators if op.statically_idle(p))
        active = tuple(op for op in self.operators if op not in idle)
        valid, current = None, state
        for op in self.events:
            if op in active:
                current, ok = op.event(current, control, p, xp=xp)
                valid = _and(valid, ok)
        h = 0.5 * dt
        splits = tuple(op for op in self.splits if op in active)
        for op in splits:
            current, ok = op.half_step(current, h, control, p, xp=xp)
            valid = _and(valid, ok)
            valid = _and(valid, op.control_valid(control, p, xp=xp))
        process = self.process_operator
        if process is not None and process.idle_process(p):
            process = None  # Statically absent (no route declared): the inner step itself.
        inputs = (
            self.inner.inner_state(current),
            self.control_view(control, current, p, xp=xp),
            self.view(p, current, xp=xp),
        )
        inputs = self.inner.barrier(inputs, xp=xp)
        if process is None:
            moved, ok = self.inner.checked_step(inputs[0], dt, inputs[1], inputs[2], p.active)
            moved, ok = self.inner.barrier((moved, ok), xp=xp)
        else:
            moved, ok, (applied, heat) = self.inner.imex_step(
                inputs[0],
                dt,
                inputs[1],
                inputs[2],
                xp=xp,
                membrane_process=process.process(control, p),
            )
            moved, ok, applied, heat = self.inner.barrier((moved, ok, applied, heat), xp=xp)
        current = current._replace(**moved._asdict())
        last = None
        for op in reversed(splits):
            current, ok_half = op.half_step(current, h, control, p, xp=xp)
            last = _and(last, ok_half)
        if process is not None:
            current = process.book_process(current, state, applied, heat, p)
        valid = _and(_and(_and(valid, ok), last), self._end_domain(current, p, active, xp=xp))
        if not idle:
            return jax.tree.map(lambda old, new: xp.where(valid, new, old), state, current), valid
        # Statically idle operators' fields pass through; the rest is selected.
        passed = {k for op in idle for k in op.STATE_AXES}
        selected = {
            k: xp.where(valid, getattr(current, k), getattr(state, k))
            for k in self.STATE_TYPE._fields
            if k not in passed
        }
        return state._replace(**selected), valid

    imex_step = split_step

    def _end_domain(self, state, p, operators, *, xp):
        """Domain of the step's end state: the inner one at the view if a split moved it."""
        valid = None
        if self.domain_views:
            valid = self.inner.domain_valid(
                self.inner.inner_state(state),
                self.inner.view(p, state, self.domain_views, xp=xp),
                p.active,
                xp=xp,
            )
        for op in operators:
            valid = op.domain_valid(state, p, valid, xp=xp)
        return valid

    # ------------------------------------------------------------ readouts

    def readouts(self, state, control, p, *, xp=jnp):
        """The inner readouts at the view (with the in-step process) plus the operators' rates.

        Validity folds the operators' rate validity, then their state and control
        checks, then the finiteness of their rates; the energy-balance rate adds their
        terms last (the frozen models' order).
        """
        inner_control = self.control_view(control, state, p, xp=xp)
        view = self.view(p, state, xp=xp)
        hook = {}
        if self.process_operator is not None:
            hook = dict(membrane_process=self.process_operator.process(control, p))
        v = self.inner.readouts(self.inner.inner_state(state), inner_control, view, xp=xp, **hook)
        computed = [op.rates(state, control, p, view, xp=xp) for op in self.operators]
        derivative = list(v.derivative)
        for op, (rates, _, _) in zip(self.operators, computed, strict=True):
            derivative.extend(rates[k] for k in op.STATE_AXES)
        valid = v.valid
        for _, ok, _ in computed:
            valid = _and(valid, ok)
        for op in self.operators:
            valid = op.rate_checks(state, control, p, valid, xp=xp)
        for op, (rates, _, _) in zip(self.operators, computed, strict=True):
            if op.FINITE_RATES:
                for k in op.STATE_AXES:
                    valid &= xp.all(xp.isfinite(rates[k]))
        energy = v.field.energy_balance_pJ_s
        for op, (_, _, readout) in zip(self.operators, computed, strict=True):
            term = op.energy_rate(readout, p, xp=xp)
            if term is not None:
                energy = energy + term
        field = v.field._replace(energy_balance_pJ_s=energy, converged=valid)
        blocks = [r for op, (_, _, r) in zip(self.operators, computed, strict=True) if op.READOUT]
        return self.VALUES_TYPE(field, self.STATE_TYPE(*derivative), v, *blocks, valid)

    def field_values(self, state, control, p, *, xp=jnp):
        return self.readouts(state, control, p, xp=xp).field

    def rhs(self, state, control, p, active, *, xp=jnp):
        values = self.readouts(state, control, p, xp=xp)
        return self.STATE_TYPE(*(xp.where(values.valid, v, xp.nan) for v in values.derivative))

    def _domain(self, state, p, active, *, xp=jnp):
        layout = (
            self.inner.view(p, state, self.domain_views, xp=xp)
            if self.domain_views
            else self.inner.inner_layout(p)
        )
        valid = self.inner.domain_valid(self.inner.inner_state(state), layout, active, xp=xp)
        for op in self.operators:
            valid = op.domain_valid(state, p, valid, xp=xp)
        return valid

    def control_domain_valid(self, state, control, p, active, *, xp=jnp):
        valid = self.domain_valid(state, p, active, xp=xp)
        for op in self.operators:
            valid = _and(valid, op.control_valid(control, p, xp=xp))
        if xp is np:
            if not valid:
                return np.asarray(False)
            try:
                return np.asarray(self.readouts(state, control, p, xp=np).valid)
            except np.linalg.LinAlgError:
                return np.asarray(False)
        return jax.lax.cond(
            valid, lambda: self.readouts(state, control, p).valid, lambda: jnp.asarray(False)
        )

    # ------------------------------------------------------------ definition checks

    def check_definition(self, spec):
        """Contract refusals that need the definition, then every scheduled control.

        The inner definition was checked by its own parser. Each change of the
        schedule union is checked on the compact initial state (the domain and a
        valid field), then each operator's own checks run.
        """
        solver = spec.execution.solver
        if solver == "rk4" and self.coupled:
            if (
                self.events
                or self.STATE_DTYPES
                or any(op.SPLIT and op.RK4 == "split" for op in self.operators)
            ):
                raise ConfigError(
                    "An RK4 composition with a coupled operator cannot hold event maps, "
                    "split-only parts or integer state"
                )
        dt, end = spec.execution.dt, spec.experiment.end_time
        for op, _, schedule in entries(spec):
            if op.EVENT and any(
                not 0 < t < end or int(round(t / dt)) * dt != t for t in op.schedule_times(schedule)
            ):
                raise ConfigError(
                    f"{op.LAW_ID} event times must be exact multiples of dt inside the horizon"
                )
        small = compact(spec)
        state, p = self.initial_values(small)
        if self.field_inputs:
            self.inner.check_field_inputs(p)
        controls = composite_spec.control_values(small, [c.time for c in small.experiment.changes])
        with np.errstate(all="ignore"):
            for i in range(len(controls.membrane)):
                control = self.CONTROL_TYPE(*(v[i] for v in controls))
                if not self.control_domain_valid(state, control, p, p.active, xp=np):
                    raise ConfigError("Initial composite domain invalid")
        for op, declaration, schedule in entries(spec):
            op.check_definition(spec, declaration, schedule, self)

    def check_steps(self, spec, steps, controls):
        """The inner step checks on the definition the operators declare, then theirs
        (bind_step_checks for one chunk; the checks read no controls)."""
        self.bind_step_checks(spec)(steps)

    def bind_step_checks(self, spec):
        """check_steps bound to one definition, for every chunk of its clock (core/grid).

        The inner model's bound checks on the operator-adjusted check spec (each operator's
        inner_check_spec: water's minimum volumes, replacement's worst case; v2 design R5),
        then each operator's bound checks, in declared order. What they read from the
        definition is evaluated once, at first use; each chunk passes its steps.
        """
        check_spec = spec
        for op, declaration, schedule in entries(spec):
            check_spec = op.inner_check_spec(check_spec, spec, declaration, schedule)
        inner = self.inner.bind_step_checks(check_spec)
        own = tuple(
            op.bind_check_steps(spec, declaration, schedule, self)
            for op, declaration, schedule in entries(spec)
        )

        def bound(steps):
            inner(steps)
            for check in own:
                check(steps)

        return bound

    # ------------------------------------------------------------ ledgers

    def _adjusted(self, row, p, *, xp):
        for op in self.operators:
            row = op.adjust_inner(row, p, xp=xp)
        return row

    def _ledgers(self, state, p, *, xp, own):
        """The inner ledgers (declared layout) with the operators' terms, in declared
        order, then (own) the operators' own ledgers; one ledger call per operator."""
        row = self._adjusted(state, p, xp=xp)
        inner = self.inner.balances if xp is np else self.inner.device_balances
        result = inner(self.inner.inner_state(row), self.inner.inner_layout(p))
        extra = {}
        for op in self.operators:
            result, ledgers = op.ledger_terms(result, row, p, xp=xp)
            extra |= ledgers
        for op in self.operators:
            if op.LAW_ID in self.writers_of:
                extra |= self._with_writers(op, {k: extra[k] for k in op.LEDGERS}, row, p, xp=xp)
        return result | extra if own else result

    def _with_writers(self, owner, values, row, p, *, xp, magnitudes=False):
        """An owner's own ledgers (or their magnitudes), {name: value}, with the terms
        of the later operators that write its accepted fields (v2 design §1.4)."""
        for writer, ledgers in self.writers_of.get(owner.LAW_ID, ()):
            add = writer.external_magnitude_terms if magnitudes else writer.external_ledger_terms
            terms = add({k: values[k] for k in ledgers}, row, p, xp=xp)
            values = values | {k: terms[k] for k in ledgers}
        return values

    def _own_ledgers(self, op, row, p, *, xp):
        values = op.own_ledgers(row, p, xp=xp)
        return (
            self._with_writers(op, values, row, p, xp=xp)
            if op.LAW_ID in self.writers_of
            else values
        )

    def _own_magnitudes(self, op, row, p, *, xp):
        values = op.own_magnitudes(row, p, xp=xp)
        if op.LAW_ID not in self.writers_of:
            return values
        named = dict(zip(op.LEDGERS, values, strict=True))
        named = self._with_writers(op, named, row, p, xp=xp, magnitudes=True)
        return tuple(named[k] for k in op.LEDGERS)

    def inner_balances(self, state, p):
        """The inner ledgers with the operators' terms (host; the inner row checks)."""
        return self._ledgers(state, p, xp=np, own=False)

    def balances(self, state, p):
        return self._ledgers(state, p, xp=np, own=True)

    def device_balances(self, state, p):
        return self._ledgers(state, p, xp=jnp, own=True)

    def inner_magnitudes(self, row, p, *, xp=np):
        adjusted = self._adjusted(row, p, xp=xp)
        magnitudes = list(
            self.inner.magnitudes(
                self.inner.inner_state(adjusted), self.inner.inner_layout(p), xp=xp
            )
        )
        for op in self.operators:
            magnitudes = op.magnitude_terms(magnitudes, row, p, xp=xp)
        return tuple(magnitudes)

    def magnitudes(self, row, p, *, xp=np):
        inner = self.inner_magnitudes(row, p, xp=xp)
        own = tuple(
            m for op in self.own_ledger_operators for m in self._own_magnitudes(op, row, p, xp=xp)
        )
        return (*inner, *own)

    def ledger_limits(self, row, p, tol, rtol, *, steps, magnitudes, xp=np):
        count = len(self.inner.LEDGERS)
        flows, bounds = self.inner.ledger_limits(
            row, p, tol, rtol, steps=steps, magnitudes=magnitudes[:count], xp=xp
        )
        if not self.own_ledger_operators:
            return flows, bounds
        extra, offset = [], count
        for op in self.own_ledger_operators:
            k = len(op.LEDGERS)
            extra.extend(op.own_bounds(magnitudes[offset : offset + k], steps))
            offset += k
        return flows, (*bounds, *extra)

    def check_values(self, state, spec, steps=None):
        """Host checks of every accepted row (one row or a [time, ...] history).

        The inner model's row checks with the operators' terms, then each
        operator's own ledgers against their bounds (in declared order).
        """
        _, p = self.initial_values(spec)
        diagnostics = self.inner.checked_rows(
            state,
            spec,
            p,
            domain=self.domain_valid,
            balances=self.inner_balances,
            magnitudes=self.inner_magnitudes,
            dissipation=self.DISSIPATION_FIELDS,
            steps=steps,
        )
        if not self.own_ledger_operators:
            return diagnostics
        rows = (
            [state]
            if state.amount_increment.ndim == 2
            else [
                self.STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))
            ]
        )
        counts = [0] * len(rows) if steps is None else list(steps)
        extra = {"max_" + k: 0.0 for op in self.own_ledger_operators for k in op.LEDGER_DIAGNOSTICS}
        with np.errstate(all="ignore"):
            for row, count in zip(rows, counts, strict=True):
                for op in self.own_ledger_operators:
                    values = self._own_ledgers(op, row, p, xp=np)
                    bounds = op.own_bounds(self._own_magnitudes(op, row, p, xp=np), count)
                    for (name, value), key, bound in zip(
                        values.items(), op.LEDGER_DIAGNOSTICS, bounds, strict=True
                    ):
                        if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                            raise NumericalError(op.LEDGER_MESSAGE + name)
                        key = "max_" + key
                        extra[key] = max(extra[key], float(np.max(np.abs(value), initial=0)))
        return diagnostics | extra

    def device_failure_message(self, check):
        for op in self.own_ledger_operators:
            if check in op.LEDGERS:
                return op.LEDGER_MESSAGE + check
        return self.inner.device_failure_message(check)

    def device_checks(self, previous, row, p, constants, steps):
        """check_values' tests for one accepted row on the device: (failed, diagnostics)."""
        return row_checks(
            previous,
            row,
            p,
            constants,
            steps,
            domain_valid=self.domain_valid,
            balances=self.device_balances,
            limits=self.ledger_limits,
            magnitudes=self.magnitudes,
            dissipation=self.DISSIPATION_FIELDS,
        )

    # ------------------------------------------------------------ observations

    def observe_history(self, times, history, layout, requested, spec):
        """The inner observations of each row at its view, then each operator's columns."""
        p = type(layout)(*(np.asarray(v) for v in layout))
        requested = np.asarray(requested, dtype=float)
        if any(t not in times for t in requested):
            raise ConfigError("Composite observations require accepted times")
        controls = composite_spec.control_values(spec, requested)
        base, records = projection(spec), []
        for j, t in enumerate(requested):
            i = int(np.flatnonzero(times == t)[0])
            state = self.STATE_TYPE(*(np.asarray(v[i]) for v in history))
            control = self.CONTROL_TYPE(*(v[j] for v in controls))
            view = self.view(p, state, xp=np)
            inner_spec = base
            if self.factored:
                effective = self.control_view(control, state, p, xp=np)
                inner_spec = held_schedules(base, effective, self.factored)
            one = self.inner.STATE_TYPE(*(getattr(state, k)[None] for k in self.inner.STATE_FIELDS))
            observed = self.inner.observe_history(
                np.array([t]), one, view, np.array([t]), inner_spec
            )
            row = {k: v[0] for k, v in vars(observed).items()}
            for op in self.operators:
                columns = op.observe(row, state, control, p, view, self, spec)
                if set(columns) != self.observed_keys[op.LAW_ID]:
                    undeclared = sorted(set(columns) ^ self.observed_keys[op.LAW_ID])
                    raise ConfigError(f"{op.LAW_ID} observes {undeclared} against its declaration")
                row.update(columns)
            records.append(row)
        if records:
            return self.Observations(
                *(np.stack([r[k] for r in records]) for k in self.OBSERVATION_FIELDS)
            )
        sample = self.observe_history(
            times[:1], self.STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec
        )
        return self.Observations(
            *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
        )

    def ensemble_voltage(self, state, layout, spec, time):
        controls = composite_spec.control_values(spec, [time])
        control = self.CONTROL_TYPE(*(v[0] for v in controls))
        p = type(layout)(*(np.asarray(v) for v in layout))
        v = self.field_values(self.STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
        if not v.converged:
            raise NumericalError("Composite ensemble endpoint invalid")
        return v.rates.membrane_voltage_V[p.membrane_active]

    def summarize(self, history, diagnostics, spec):
        solver = spec.execution.solver
        coupled = solver == "rk4" and self.coupled
        result = self.inner.summarize(history, diagnostics, projection(spec)) | {
            "model": MODEL_ID,
            "inner_model": spec.model.inner_model,
            "operators": list(self.laws),
            "composition": identity(spec.model),
            "composition_status": composite_spec.DEVELOPMENT_STATUS,
            "state_fields": list(self.STATE_TYPE._fields),
            "time_integrator": solver,
            "splitting": "coupled rhs (rk4)" if coupled else SPLITTING_ID,
            "operator_steps": {op.LAW_ID: op.STEP_ID for op in self.operators},
        }
        for op, declaration, schedule in entries(spec):
            result |= op.summary(spec, declaration, schedule, history)
        return result
