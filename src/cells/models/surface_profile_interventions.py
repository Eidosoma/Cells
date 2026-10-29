"""RK-stage membrane-profile pulses with the unchanged complete passive ledgers.

The explicit phase clock is checkpoint state. Zero scheduled buffers are an
algebraic representation of the supported fresh-phase membrane-only contract;
no native solver-loop, INIT-to-SIM state handoff or moving-geometry parity.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_profile_interventions_spec import MODEL_ID, artifact, base_spec, bindings
from cells.models import surface_tissue as base
from cells.processes import betse_tissue_profiles as native

OBSERVER_ID = "resolved_scheduled_membrane_profile_readouts@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_phase_clock_scheduled_Dm_resolved_charge_current@1"
BATCH_CAPACITIES = (*base.BATCH_CAPACITIES, "intervention_capacity", "intervention_target_capacity")
STATE_AXES = base.STATE_AXES | {"phase_clock_s": ["phase_clock"]}
STATE_TYPE = NamedTuple("SurfaceProfileInterventionState", [(k, object) for k in STATE_AXES])
EXTRA_LAYOUT = tuple("intervention_" + k for k in native.InterventionKernel._fields) + (
    "intervention_dynamic_factor",
    "native_baseline_m2_s",
    "native_event_coefficient_m2_s",
    "membrane_native_index",
    "membrane_thickness_m",
    "species_native_index",
    "species_native_supported",
    "profile_sim",
    "phase_end_s",
    "phase_clock_atol_s",
)
LAYOUT_TYPE = NamedTuple(
    "SurfaceProfileInterventionLayout",
    [(k, object) for k in (*base.LAYOUT_TYPE._fields, *EXTRA_LAYOUT)],
)
OBSERVATION_FIELDS = (
    *base.OBSERVATION_FIELDS,
    "phase_clock_s",
    "membrane_permeability_m_per_s",
    "scheduled_native_Dm_m2_s",
    "native_pulse",
)
Observations = make_dataclass(
    "SurfaceProfileInterventionObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)
parameters = base.parameters


def base_state(state):
    return base.STATE_TYPE(*(getattr(state, k) for k in base.STATE_TYPE._fields))


def base_layout(p):
    return base.LAYOUT_TYPE(*(getattr(p, k) for k in base.LAYOUT_TYPE._fields))


def kernel(p):
    return native.InterventionKernel(
        *(getattr(p, "intervention_" + k) for k in native.InterventionKernel._fields)
    )


def initial_values(spec):
    original = base_spec(spec)
    state, p = base.initial_values(original)
    view, bound, events, dynamic, baseline, coefficient = bindings(spec.model, spec.execution)
    mids = [m.id for m in spec.model.membranes]
    cap = spec.execution.membrane_capacity
    index = np.zeros(cap, dtype=np.int64)
    thickness = np.ones(cap)
    for i, name in enumerate(mids):
        index[i] = view.layout.membrane_ids.index(name)
        thickness[i] = view.thickness_m[name]
    species = spec.model.species_ids
    supported = np.asarray([s in native.IONS for s in species], bool)
    values = p._asdict() | {"intervention_" + k: v for k, v in events.kernel._asdict().items()}
    values.update(
        intervention_dynamic_factor=dynamic,
        native_baseline_m2_s=baseline,
        native_event_coefficient_m2_s=coefficient,
        membrane_native_index=index,
        membrane_thickness_m=thickness,
        species_native_index=np.asarray(
            [native.IONS.index(s) if s in native.IONS else 0 for s in species], dtype=np.int64
        ),
        species_native_supported=supported,
        profile_sim=np.asarray(spec.model.phase == "SIM"),
        phase_end_s=np.asarray(spec.experiment.end_time),
        phase_clock_atol_s=np.asarray(
            64 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
        ),
    )
    return STATE_TYPE(*state, np.zeros(1)), LAYOUT_TYPE(**values)


def native_state(p, *, xp):
    k = kernel(p)
    n, m, e = k.cell_slots.size, k.membrane_slots.size, k.environment_slots.size
    return native.InterventionState(
        xp.asarray(p.native_baseline_m2_s),
        xp.zeros((6, m)),
        xp.zeros(n),
        xp.zeros(n),
        xp.zeros((6, e)),
        xp.zeros((6, e)),
        xp.zeros(6),
        xp.ones(e),
        xp.ones(e),
    )


class Signal(NamedTuple):
    permeability: object
    scheduled: object
    pulse: object
    valid: object


def signal_values(state, p, *, xp=jnp):
    k = kernel(p)
    buffers = native_state(p, xp=xp)
    time = state.phase_clock_s[0]
    response = native.apply_interventions(time, buffers, k, p.intervention_dynamic_factor, xp=xp)
    total = response.membrane_total_m2_s[p.species_native_index][:, p.membrane_native_index]
    support = (
        p.native_event_coefficient_m2_s[p.species_native_index][:, p.membrane_native_index] != 0
    )
    selected = (
        p.profile_sim & p.membrane_active[None, :] & p.species_native_supported[:, None] & support
    )
    permeability = xp.where(selected, total / p.membrane_thickness_m, p.membrane_permeability)
    valid = native.intervention_domain_valid(time, buffers, k, p.intervention_dynamic_factor, xp=xp)
    valid &= xp.all(xp.isfinite(permeability) & (permeability >= 0))
    return Signal(
        permeability,
        xp.where(p.profile_sim, response.state.membrane_scheduled_m2_s, 0.0),
        xp.where(p.profile_sim, response.pulse, 0.0),
        valid,
    )


def effective_layout(state, p, *, xp=jnp):
    return base_layout(p)._replace(
        membrane_permeability=signal_values(state, p, xp=xp).permeability
    )


def accounting_layout(p, *, xp=jnp):
    upper = p.native_baseline_m2_s + xp.where(
        p.profile_sim, xp.maximum(p.native_event_coefficient_m2_s, 0), 0
    )
    coefficient = upper[p.species_native_index][:, p.membrane_native_index] / p.membrane_thickness_m
    union = xp.where(
        p.species_native_supported[:, None] & p.membrane_active[None, :],
        xp.maximum(coefficient, p.membrane_permeability),
        p.membrane_permeability,
    )
    return base_layout(p)._replace(membrane_permeability=union)


def accounting_spec(spec):
    _, p = initial_values(spec)
    parent = base_spec(spec)
    union = accounting_layout(p, xp=np).membrane_permeability
    membranes = tuple(
        replace(row, permeability_m_per_s=tuple(union[:, j]))
        for j, row in enumerate(parent.model.membranes)
    )
    return replace(parent, model=replace(parent.model, membranes=membranes))


def domain_valid(state, p, active, *, xp=jnp):
    clock = state.phase_clock_s
    if clock.shape != (1,):
        return xp.asarray(False)
    return base.domain_valid(
        base_state(state), accounting_layout(p, xp=xp), active, xp=xp
    ) & xp.all(xp.isfinite(clock) & (clock >= 0) & (clock <= p.phase_end_s + p.phase_clock_atol_s))


def field_values(state, control, p, *, xp=jnp):
    return base.field_values(base_state(state), control, effective_layout(state, p, xp=xp), xp=xp)


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp) & signal_values(state, p, xp=xp).valid
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return field_values(state, control, p, xp=np).converged
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid, lambda: field_values(state, control, p).converged, lambda: jnp.asarray(False)
    )


domain_valid.with_control = control_domain_valid


class Values(NamedTuple):
    field: object
    derivative: object
    signal: object
    valid: object


def readouts(state, control, p, *, xp=jnp):
    signal = signal_values(state, p, xp=xp)
    current = base_layout(p)._replace(membrane_permeability=signal.permeability)
    field = base.field_values(base_state(state), control, current, xp=xp)
    valid = field.converged & signal.valid & domain_valid(state, p, p.active, xp=xp)
    derivative = STATE_TYPE(
        *base.derivative_from_field(field, current, xp=xp), xp.ones_like(state.phase_clock_s)
    )
    return Values(field, derivative, signal, valid)


def rhs(state, control, p, active, *, xp=jnp):
    value = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(value.valid, v, xp.nan) for v in value.derivative))


def check_definition(spec):
    _, _, events, _, _, _ = bindings(spec.model, spec.execution)
    tc = int(np.max(events.kernel.selected.sum(axis=1), initial=0))
    m = spec.model
    compact = replace(
        spec,
        execution=replace(
            spec.execution,
            capacity=len(m.cells),
            extracellular_capacity=len(m.extracellular),
            membrane_capacity=len(m.membranes),
            edge_capacity=len(m.junctions),
            face_capacity=len(m.faces),
            intervention_capacity=len(m.interventions),
            intervention_target_capacity=tc,
        ),
    )
    state, p = initial_values(compact)
    from cells.core.schedule import control_values

    clocks = sorted(
        {
            0.0,
            spec.experiment.end_time,
            *(c.time for c in spec.experiment.changes),
            *(t for e in m.interventions for t in (e.on_s, (e.on_s + e.off_s) / 2, e.off_s)),
        }
    )
    table = control_values(base_spec(compact), clocks)
    for i, time in enumerate(clocks):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        u = type(table)(*(v[i] for v in table))
        if not control_domain_valid(trial, u, p, p.active, xp=np):
            raise ConfigError("Scheduled membrane stage violates physical/charge/current domain")


def check_steps(spec, steps, controls):
    ceiling = None
    if spec.model.phase == "SIM" and spec.model.interventions:
        ceiling = min(e.change_s / 8 for e in spec.model.interventions)
        # A large absolute clock must never relax the declared nominal step.
        # Check this before constructing the parent grid, independently of
        # endpoint subtraction errors in the supplied execution window.
        if spec.execution.dt > ceiling * (1 + 16 * np.finfo(float).eps):
            raise ConfigError(
                "Scheduled profile nominal execution.dt must be <= each transition time/8"
            )
    base.check_steps(base_spec(spec), steps, controls)
    if ceiling is not None:
        # Differences of rounded absolute clock labels have errors on the
        # clock scale, rather than only on the much shorter step scale. Two
        # horizon ulps cover the two endpoint roundings/subtraction; retain
        # the scalar step-expression allowance as well. No times are changed.
        allowance = max(
            2 * np.spacing(spec.experiment.end_time),
            16 * np.finfo(float).eps * ceiling,
        )
        if np.max(steps, initial=0) > ceiling + allowance:
            raise ConfigError("Scheduled profile RK4 steps must be <= each transition time/8")


def check_values(state, spec):
    diagnostics = base.check_values(base_state(state), accounting_spec(spec))
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.phase_clock_s.ndim == 1
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.phase_clock_s))]
    )
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np) or not signal_values(row, p, xp=np).valid:
            raise NumericalError("Invalid scheduled profile state/clock/permeability; no repair")
    if (
        state.phase_clock_s.ndim == 2
        and np.min(np.diff(np.asarray(state.phase_clock_s)[:, 0]), initial=0)
        < -p.phase_clock_atol_s
    ):
        raise NumericalError("Scheduled phase clock cannot decrease")
    diagnostics["phase_clock_final_s"] = float(np.asarray(rows[-1].phase_clock_s)[0])
    return diagnostics


def check_checkpoint(spec, checkpoint):
    _, p = initial_values(spec)
    clock = np.asarray(checkpoint.state.phase_clock_s)
    if (
        clock.shape != (1,)
        or not np.isfinite(clock).all()
        or abs(clock[0] - checkpoint.time) > p.phase_clock_atol_s
    ):
        raise ConfigError("Scheduled phase clock differs from accepted checkpoint metadata")


def batch_signature(model):
    return (
        *base.batch_signature(model),
        model.species_ids,
        tuple(m.id for m in model.membranes),
        tuple(
            (e.name, e.kind, e.profiles, None if e.spatial is None else e.spatial["axis"])
            for e in model.interventions
        ),
    )


def working_size(spec):
    x = spec.execution
    return (
        base.working_size(base_spec(spec))
        + 256 * x.intervention_capacity * max(1, x.intervention_target_capacity)
        + 256 * x.membrane_capacity
    )


def observe_history(times, history, layout, requested, spec):
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    records = []
    for time in requested:
        matches = np.flatnonzero(times == time)
        if len(matches) != 1:
            raise ConfigError("Scheduled profile observations need accepted boundaries")
        i = int(matches[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        signal = signal_values(state, p, xp=np)
        if abs(state.phase_clock_s[0] - time) > p.phase_clock_atol_s:
            raise ConfigError("Observed phase clock differs from accepted time")
        current = base_layout(p)._replace(membrane_permeability=signal.permeability)
        observed = base.observe_history(
            np.asarray([time]),
            base.STATE_TYPE(*(v[None] for v in base_state(state))),
            current,
            [time],
            base_spec(spec),
        )
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

    table = control_values(base_spec(spec), [time])
    u = type(table)(*(v[0] for v in table))
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    y = STATE_TYPE(*(np.asarray(v) for v in state))
    if abs(y.phase_clock_s[0] - time) > p.phase_clock_atol_s:
        raise ConfigError("Endpoint phase clock differs from accepted time")
    field = field_values(y, u, p, xp=np)
    if not field.converged:
        raise NumericalError("Scheduled profile endpoint field invalid")
    return field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return base.summarize(base_state(history), diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        phase=spec.model.phase,
        timing_policy=spec.model.timing_policy,
        reset_policy=spec.model.reset_policy,
        intervention_identity=artifact(spec)["interventions"]["identity"],
        native_solver_loop_parity=False,
    )
