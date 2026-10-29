"""Complete calcium @6 with native background plasma D pulses.

Physical chemistry, stage fuel and every parent equation stay owner-specific.
Only the closed background transfer diagnostic receives the qualified
readout-only view; all actual full histories drive accounting and output.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import owned_calcium_profile_binding as binding
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_profile_interventions_spec import MODEL_ID, artifact, owner_spec
from cells.models import surface_calcium_cav as base
from cells.models import surface_profile_interventions as scheduled

STATE_AXES = base.STATE_AXES | {"phase_clock_s": ["phase_clock"]}
STATE_TYPE = NamedTuple("SurfaceCalciumProfileState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumProfileLayout",
    [(k, object) for k in (*base.LAYOUT_TYPE._fields, *scheduled.EXTRA_LAYOUT)],
)
OBSERVER_ID = "resolved_surface_calcium_profile_interventions_readouts@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_clock_background_D_complete_calciumprofile_owner@1"
BATCH_CAPACITIES = (*base.BATCH_CAPACITIES, "intervention_capacity", "intervention_target_capacity")
OBSERVATION_FIELDS = (
    *base.OBSERVATION_FIELDS,
    "phase_clock_s",
    "membrane_permeability_m_per_s",
    "scheduled_native_Dm_m2_s",
    "native_pulse",
)
Observations = make_dataclass(
    "SurfaceCalciumProfileObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = base.parameters
signal_values = scheduled.signal_values


def parent_state(state):
    return base.STATE_TYPE(*(getattr(state, k) for k in base.STATE_TYPE._fields))


def parent_layout(layout):
    # Exact parent type is part of channel-catalog dispatch, including its
    # zero/one/two-state and calcium-dependent instantaneous channel contracts.
    return base.LAYOUT_TYPE(*(getattr(layout, k) for k in base.LAYOUT_TYPE._fields))


def initial_values(spec):
    state, p = base.initial_values(owner_spec(spec))
    layout = LAYOUT_TYPE(**(p._asdict() | binding.native_parameters(spec)))
    return STATE_TYPE(*state, np.zeros(1)), layout


def accounting_layout(p, *, xp=jnp):
    union = scheduled.accounting_layout(p, xp=xp).membrane_permeability
    return parent_layout(p)._replace(membrane_permeability=union)


def accounting_spec(spec):
    _, p = initial_values(spec)
    original = owner_spec(spec)
    union = accounting_layout(p, xp=np).membrane_permeability
    membranes = tuple(
        replace(row, permeability_m_per_s=tuple(union[:, j]))
        for j, row in enumerate(original.model.membranes)
    )
    return replace(original, model=replace(original.model, membranes=membranes))


def readout_state(state, permeability, *, xp):
    # These diagnostic integrals never enter gates, fluxes, pump kinetics,
    # inventories, charge or fields. Only the fixed-parent route validity reads
    # them here. Actual histories remain in state and are checked separately.
    value = parent_state(state)
    return value._replace(
        membrane_transferred=xp.where(permeability > 0, value.membrane_transferred, 0.0)
    )


def domain_valid(state, p, active, *, xp=jnp):
    clock = state.phase_clock_s
    if clock.shape != (1,):
        return xp.asarray(False)
    return base.domain_valid(
        parent_state(state), accounting_layout(p, xp=xp), active, xp=xp
    ) & xp.all(xp.isfinite(clock) & (clock >= 0) & (clock <= p.phase_end_s + p.phase_clock_atol_s))


class Values(NamedTuple):
    field: object
    derivative: object
    signal: object
    parent: object
    valid: object


def readouts(state, control, p, *, xp=jnp):
    signal = signal_values(state, p, xp=xp)
    current = parent_layout(p)._replace(membrane_permeability=signal.permeability)
    value = base.readouts(readout_state(state, signal.permeability, xp=xp), control, current, xp=xp)
    valid = value.valid & signal.valid & domain_valid(state, p, p.active, xp=xp)
    field = value.field._replace(converged=valid, rates=value.field.rates._replace(valid=valid))
    value = value._replace(field=field, valid=valid)
    return Values(
        field,
        STATE_TYPE(*value.derivative, xp.ones_like(state.phase_clock_s)),
        signal,
        value,
        valid,
    )


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    value = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(value.valid, v, xp.nan) for v in value.derivative))


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp) & signal_values(state, p, xp=xp).valid
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return readouts(state, control, p, xp=np).valid
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid, lambda: readouts(state, control, p).valid, lambda: jnp.asarray(False)
    )


domain_valid.with_control = control_domain_valid


def check_definition(spec):
    from cells.core.schedule import control_values

    state, p = initial_values(spec)
    clocks = sorted(
        {
            0.0,
            spec.experiment.end_time,
            *(c.time for c in spec.experiment.changes),
            *(
                t
                for e in spec.model.interventions
                for t in (e.on_s, (e.on_s + e.off_s) / 2, e.off_s)
            ),
        }
    )
    controls = control_values(owner_spec(spec), clocks)
    for i, time in enumerate(clocks):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        u = type(controls)(*(v[i] for v in controls))
        if not control_domain_valid(trial, u, p, p.active, xp=np):
            raise ConfigError("Owned calcium pulse/control stage violates the full physical domain")


def check_steps(spec, steps, controls):
    from cells.models import surface_calcium as calcium
    from cells.processes import calcium_gates

    complete = accounting_spec(spec)
    base.check_steps(complete, steps, controls)
    _, p = initial_values(spec)
    bound = binding.background_loss_bound(
        accounting_layout(p, xp=np), max(map(abs, calcium_gates.VOLTAGE_DOMAIN_V))
    ) + calcium.loss_bound(complete)
    if not np.isfinite(bound) or np.max(steps, initial=0) * bound > 0.25:
        raise ConfigError("Scheduled calcium step * complete background/chemical loss exceeds 0.25")
    scheduled.check_steps(spec, steps, controls)


def check_values(state, spec):
    clock = np.asarray(state.phase_clock_s)
    if clock.ndim not in (1, 2) or clock.shape[-1:] != (1,):
        raise NumericalError("Owned calcium scheduled phase clock has incompatible shape")
    diagnostics = base.check_values(parent_state(state), accounting_spec(spec))
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.phase_clock_s.ndim == 1
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.phase_clock_s))]
    )
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np) or not signal_values(row, p, xp=np).valid:
            raise NumericalError(
                "Invalid owned calcium profile physical state/history/clock/permeability; no repair"
            )
    if (
        state.phase_clock_s.ndim == 2
        and np.min(np.diff(np.asarray(state.phase_clock_s)[:, 0]), initial=0)
        < -p.phase_clock_atol_s
    ):
        raise NumericalError("Owned calcium scheduled phase clock cannot decrease")
    diagnostics["phase_clock_final_s"] = float(np.asarray(rows[-1].phase_clock_s)[0])
    return diagnostics


def check_checkpoint(spec, checkpoint):
    return binding.check_checkpoint(spec, checkpoint)


def batch_signature(model):
    return (
        base.batch_signature(model),
        tuple((c.id, c.membrane_id, c.kinetic_law) for c in model.channels),
        tuple(
            (e.name, e.kind, e.profiles, None if e.spatial is None else e.spatial["axis"])
            for e in model.interventions
        ),
    )


def working_size(spec):
    x = spec.execution
    return (
        base.working_size(owner_spec(spec))
        + 256 * x.intervention_capacity * max(1, x.intervention_target_capacity)
        + 256 * x.membrane_capacity
    )


def observe_history(times, history, layout, requested, spec):
    # Conservation diagnostics always inspect the untouched, complete history.
    check_values(history, spec)
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    records = []
    for time in requested:
        matches = np.flatnonzero(times == time)
        if len(matches) != 1:
            raise ConfigError("Owned calcium profile observations need accepted boundaries")
        i = int(matches[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        signal = signal_values(state, p, xp=np)
        if abs(state.phase_clock_s[0] - time) > p.phase_clock_atol_s:
            raise ConfigError("Observed active phase clock differs from accepted time")
        current = parent_layout(p)._replace(membrane_permeability=signal.permeability)
        view = readout_state(state, signal.permeability, xp=np)
        observed = base.observe_history(
            np.asarray([time]),
            base.STATE_TYPE(*(v[None] for v in view)),
            current,
            [time],
            owner_spec(spec),
        )
        # The readout-only validity projection must never alter reported history.
        observed = replace(observed, membrane_transferred=state.membrane_transferred[None])
        records.append(
            (
                *[v[0] for v in vars(observed).values()],
                state.phase_clock_s,
                signal.permeability,
                signal.scheduled,
                signal.pulse,
            )
        )
    if records:
        return Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    y = STATE_TYPE(*(np.asarray(v) for v in state))
    if abs(y.phase_clock_s[0] - time) > p.phase_clock_atol_s:
        raise ConfigError("Owned calcium endpoint phase clock differs from accepted time")
    table = control_values(owner_spec(spec), [time])
    u = type(table)(*(v[0] for v in table))
    value = readouts(y, u, p, xp=np)
    if not value.valid:
        raise NumericalError("Owned calcium scheduled endpoint field/domain invalid")
    return value.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return base.summarize(parent_state(history), diagnostics, owner_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        phase=spec.model.phase,
        timing_policy=spec.model.timing_policy,
        reset_policy=spec.model.reset_policy,
        intervention_identity=artifact(spec)["interventions"]["identity"],
        intervention_scope=(
            "background membrane D; actual complete chemical/fuel owner equations retained"
        ),
        native_solver_loop_parity=False,
    )
