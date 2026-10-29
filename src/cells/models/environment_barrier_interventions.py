"""Native ECM coefficient pulses coupled to Cells' conservative passive tissue.

The checkpointed phase clock drives the event at every RK stage. Coefficients
change, while all material, capacitor and dissipated-energy histories persist.
The native sodium weight remains a diagnostic, not a physical volume or charge.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.environment_barrier_interventions_spec import MODEL_ID, base_spec, bindings
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.models import surface_tissue as base
from cells.processes import betse_tissue_profiles as native

OBSERVER_ID = "resolved_scheduled_extracellular_barrier_readouts@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_phase_clock_ecm_barrier_resolved_charge_current@1"
BATCH_CAPACITIES = (*base.BATCH_CAPACITIES, "barrier_target_capacity")
STATE_AXES = base.STATE_AXES | {"phase_clock_s": ["phase_clock"]}
STATE_TYPE = NamedTuple("EnvironmentBarrierState", [(key, object) for key in STATE_AXES])
EXTRA_LAYOUT = tuple("barrier_" + key for key in native.InterventionKernel._fields) + (
    "barrier_base_m2_s",
    "barrier_modulator",
    "barrier_free_m2_s",
    "barrier_weight_base",
    "barrier_species_index",
    "barrier_face_sender",
    "barrier_face_receiver",
    "barrier_face_measure_m",
    "barrier_union_factor",
    "barrier_sim",
    "phase_end_s",
    "phase_clock_atol_s",
)
LAYOUT_TYPE = NamedTuple(
    "EnvironmentBarrierLayout", [(k, object) for k in (*base.LAYOUT_TYPE._fields, *EXTRA_LAYOUT)]
)
OBSERVATION_FIELDS = (
    *base.OBSERVATION_FIELDS,
    "phase_clock_s",
    "extracellular_site_diffusivity_m2_s",
    "extracellular_face_diffusivity_m2_s",
    "native_sodium_weight",
    "native_barrier_pulse",
)
Observations = make_dataclass(
    "EnvironmentBarrierObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = base.parameters


def base_state(state):
    return base.STATE_TYPE(*(getattr(state, k) for k in base.STATE_TYPE._fields))


def base_layout(p):
    return base.LAYOUT_TYPE(*(getattr(p, k) for k in base.LAYOUT_TYPE._fields))


def kernel(p):
    return native.InterventionKernel(
        *(getattr(p, "barrier_" + k) for k in native.InterventionKernel._fields)
    )


def harmonic_faces(site, p, *, xp):
    left, right = site[:, p.barrier_face_sender], site[:, p.barrier_face_receiver]
    low, high = xp.minimum(left, right), xp.maximum(left, right)
    result = low / (0.5 + 0.5 * low / xp.where(high > 0, high, 1.0))
    return xp.where(p.face_active, result, 0.0)


def initial_values(spec):
    state, parent = base.initial_values(base_spec(spec))
    events, site, modifiers, free, weight = bindings(spec.model, spec.execution)
    sites = spec.model.barrier_preparation["provenance"]["request"]["grid"]["site_ids"]
    capacity = spec.execution.face_capacity
    senders, receivers = np.zeros(capacity, dtype=np.int64), np.zeros(capacity, dtype=np.int64)
    measures = np.zeros(capacity)
    for i, row in enumerate(spec.model.faces):
        senders[i], receivers[i] = sites.index(row.sender), sites.index(row.receiver)
        measures[i] = row.area_m2 / row.length_m
    values = parent._asdict() | {"barrier_" + k: v for k, v in events._asdict().items()}
    values.update(
        barrier_base_m2_s=site,
        barrier_modulator=modifiers,
        barrier_free_m2_s=free,
        barrier_weight_base=weight,
        barrier_species_index=np.asarray([native.IONS.index(s) for s in spec.model.species_ids]),
        barrier_face_sender=senders,
        barrier_face_receiver=receivers,
        barrier_face_measure_m=measures,
        barrier_union_factor=parent.face_factor,
        barrier_sim=np.asarray(spec.model.phase == "SIM"),
        phase_end_s=np.asarray(spec.experiment.end_time),
        phase_clock_atol_s=np.asarray(
            64 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
        ),
    )
    p = LAYOUT_TYPE(**values)
    # Historical transfers remain legal when an opened route closes again.
    # This support union is used for accounting only, never for actual rates.
    upper = site.copy()
    if (
        spec.model.phase == "SIM"
        and spec.model.intervention is not None
        and spec.model.intervention.amplitude > 0
    ):
        for name in spec.model.intervention.site_ids:
            i = sites.index(name)
            upper[:, i] = np.maximum(upper[:, i], free)
    effective = (upper * modifiers)[p.barrier_species_index]
    union = harmonic_faces(effective, p, xp=np) * measures
    p = p._replace(barrier_union_factor=union)
    return STATE_TYPE(*state, np.zeros(1)), p


def native_state(p, *, xp):
    k = kernel(p)
    n, m = k.cell_slots.size, k.membrane_slots.size
    return native.InterventionState(
        xp.zeros((6, m)),
        xp.zeros((6, m)),
        xp.zeros(n),
        xp.zeros(n),
        xp.asarray(p.barrier_base_m2_s),
        xp.asarray(p.barrier_base_m2_s),
        xp.asarray(p.barrier_free_m2_s),
        xp.asarray(p.barrier_weight_base),
        xp.asarray(p.barrier_weight_base),
    )


class Signal(NamedTuple):
    site_diffusivity: object
    face_diffusivity: object
    face_factor: object
    sodium_weight: object
    pulse: object
    valid: object


def signal_values(state, p, *, xp=jnp):
    k, buffers = kernel(p), native_state(p, xp=xp)
    time = state.phase_clock_s[0]
    response = native.apply_interventions(time, buffers, k, 1.0, xp=xp)
    sites = xp.where(p.barrier_sim, response.state.environment_current_m2_s, p.barrier_base_m2_s)
    sites = (sites * p.barrier_modulator)[p.barrier_species_index]
    faces = harmonic_faces(sites, p, xp=xp)
    factors = faces * p.barrier_face_measure_m
    enabled = p.barrier_sim & xp.any(k.guard & (k.amplitude != 0))
    factors = xp.where(enabled, factors, p.face_factor)
    weight = xp.where(
        p.barrier_sim, response.state.environment_weight_current, p.barrier_weight_base
    )
    valid = native.intervention_domain_valid(time, buffers, k, 1.0, xp=xp)
    valid &= xp.all((k.amplitude >= 0) & (k.amplitude <= 1))
    valid &= xp.all(xp.isfinite(p.barrier_modulator) & (p.barrier_modulator >= 0))
    for values in (sites, faces, factors, weight):
        valid &= xp.all(xp.isfinite(values) & (values >= 0))
    return Signal(sites, faces, factors, weight, xp.where(p.barrier_sim, response.pulse, 0), valid)


def effective_layout(state, p, *, xp=jnp):
    return base_layout(p)._replace(face_factor=signal_values(state, p, xp=xp).face_factor)


def accounting_layout(p):
    return base_layout(p)._replace(face_factor=p.barrier_union_factor)


def accounting_spec(spec):
    _, p = initial_values(spec)
    parent = base_spec(spec)
    faces = tuple(
        replace(
            row,
            diffusivity_m2_per_s=tuple(p.barrier_union_factor[:, i] * row.length_m / row.area_m2),
        )
        for i, row in enumerate(parent.model.faces)
    )
    return replace(parent, model=replace(parent.model, faces=faces))


def domain_valid(state, p, active, *, xp=jnp):
    clock = state.phase_clock_s
    if clock.shape != (1,):
        return xp.asarray(False)
    return base.domain_valid(base_state(state), accounting_layout(p), active, xp=xp) & xp.all(
        xp.isfinite(clock) & (clock >= 0) & (clock <= p.phase_end_s + p.phase_clock_atol_s)
    )


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


def rhs(state, control, p, active, *, xp=jnp):
    signal = signal_values(state, p, xp=xp)
    current = base_layout(p)._replace(face_factor=signal.face_factor)
    field = base.field_values(base_state(state), control, current, xp=xp)
    derivative = STATE_TYPE(
        *base.derivative_from_field(field, current, xp=xp), xp.ones_like(state.phase_clock_s)
    )
    valid = signal.valid & field.converged & domain_valid(state, p, active, xp=xp)
    return STATE_TYPE(*(xp.where(valid, v, xp.nan) for v in derivative))


def check_definition(spec):
    m, event = spec.model, spec.model.intervention
    compact = replace(
        spec,
        execution=replace(
            spec.execution,
            capacity=len(m.cells),
            extracellular_capacity=len(m.extracellular),
            membrane_capacity=len(m.membranes),
            edge_capacity=len(m.junctions),
            face_capacity=len(m.faces),
            barrier_target_capacity=0 if event is None else len(event.site_ids),
        ),
    )
    state, p = initial_values(compact)
    if not np.isfinite(p.barrier_union_factor).all():
        raise ConfigError("ECM accounting support exceeds finite float64")
    from cells.core.schedule import control_values

    clocks = {0.0, spec.experiment.end_time, *(c.time for c in spec.experiment.changes)}
    if event is not None:
        clocks.update((event.on_s, (event.on_s + event.off_s) / 2, event.off_s))
    clocks = sorted(clocks)
    table = control_values(base_spec(compact), clocks)
    for i, time in enumerate(clocks):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        u = type(table)(*(v[i] for v in table))
        if not control_domain_valid(trial, u, p, p.active, xp=np):
            raise ConfigError("Scheduled ECM violates physical transport or charge/current domain")


def check_steps(spec, steps, controls):
    event = spec.model.intervention
    ceiling = None if event is None or spec.model.phase == "INIT" else event.change_s / 8
    if ceiling is not None and spec.execution.dt > ceiling * (1 + 16 * np.finfo(float).eps):
        raise ConfigError("ECM execution.dt must be <= transition time/8")
    base.check_steps(base_spec(spec), steps, controls)
    if ceiling is not None:
        allowance = max(
            2 * np.spacing(spec.experiment.end_time), 16 * np.finfo(float).eps * ceiling
        )
        if np.max(steps, initial=0) > ceiling + allowance:
            raise ConfigError("ECM RK4 steps must resolve transition time/8")


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
            raise NumericalError("Invalid ECM state/clock/coefficient; no repair")
    if (
        state.phase_clock_s.ndim == 2
        and np.min(np.diff(np.asarray(state.phase_clock_s)[:, 0]), initial=0)
        < -p.phase_clock_atol_s
    ):
        raise NumericalError("ECM phase clock cannot decrease")
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
        raise ConfigError("ECM phase clock differs from accepted checkpoint metadata")


def batch_signature(model):
    event = model.intervention
    return (
        *base.batch_signature(model),
        model.species_ids,
        tuple(f.id for f in model.faces),
        tuple(model.barrier_preparation["provenance"]["request"]["grid"]["site_ids"]),
        None if event is None else (event.name, event.site_ids),
    )


def working_size(spec):
    return base.working_size(base_spec(spec)) + 256 * (
        spec.execution.barrier_target_capacity
        + spec.execution.extracellular_capacity
        + spec.execution.face_capacity
    )


def observe_history(times, history, layout, requested, spec):
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    records = []
    for time in requested:
        indices = np.flatnonzero(times == time)
        if len(indices) != 1:
            raise ConfigError("ECM observations require accepted boundaries")
        state = STATE_TYPE(*(np.asarray(v[int(indices[0])]) for v in history))
        if abs(state.phase_clock_s[0] - time) > p.phase_clock_atol_s:
            raise ConfigError("Observed ECM phase clock differs from accepted time")
        signal = signal_values(state, p, xp=np)
        current = base_layout(p)._replace(face_factor=signal.face_factor)
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
                signal.site_diffusivity,
                signal.face_diffusivity,
                signal.sodium_weight,
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
        raise ConfigError("Endpoint ECM phase clock differs from accepted time")
    field = field_values(y, u, p, xp=np)
    if not field.converged:
        raise NumericalError("ECM endpoint field invalid")
    return field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return base.summarize(base_state(history), diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        phase=spec.model.phase,
        timing_policy=spec.model.timing_policy,
        native_solver_loop_parity=False,
        preparation_identity=spec.model.barrier_preparation["provenance"]["identity"],
    )
