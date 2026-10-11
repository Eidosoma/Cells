"""Ordinary Cells execution for the unchanged discrete BETSE active kernel."""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import numpy as np

from cells.core.betse_spatial_spec import MODEL_ID, SOLVER_ID, Control, definition_arrays
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.numerics import betse_active as active
from cells.numerics import betse_spatial as passive
from cells.processes import kinetic_pump

OBSERVER_ID = "betse_spatial_accepted_fields@1"
OBSERVATION_SAMPLING = "accepted_fixed_step_boundaries_only"
STAGE_DOMAIN_ID = "native_order_positive_concentrations_gates_retained_on_failure@1"
BATCH_CAPACITIES = ("extracellular_capacity",)
STATE_TYPE = NamedTuple(
    "BetseSpatialState", [(k, object) for k in (*passive.State._fields, *active.State._fields[1:])]
)
LAYOUT_TYPE = NamedTuple(
    "BetseSpatialLayout",
    [
        (k, object)
        for k in (
            "active",
            "ids",
            *("tissue_" + k for k in passive.Layout._fields),
            *("pump_" + k for k in kinetic_pump.Parameters._fields),
            "sodium_index",
            "potassium_index",
            "pump_available",
            "channel_permeability",
        )
    ],
)
STATE_AXES = {
    **{k: ["species", "cell_slot"] for k in ("cell_concentration",)},
    **{
        k: ["species", "membrane_slot"]
        for k in ("membrane_concentration", "membrane_inward_fmol", "junction_outward_fmol")
    },
    **{
        k: ["species", "outside_slot"]
        for k in ("outside_concentration", "reservoir_reset_fmol", "stencil_exchange_fmol")
    },
    **{k: ["clock"] for k in ("step_count", "elapsed_s")},
    **{k: ["membrane_slot"] for k in active.State._fields[1:]},
}
Observations = make_dataclass(
    "BetseSpatialObservations",
    [(k, np.ndarray) for k in ("times", *STATE_TYPE._fields, *passive.Field._fields)],
    frozen=True,
)


def flatten(state):
    # The public runner uses flat arrays, including a one-entry clock axis.
    return STATE_TYPE(
        *(
            getattr(state.tissue, k).reshape((1,))
            if k in ("step_count", "elapsed_s")
            else getattr(state.tissue, k)
            for k in passive.State._fields
        ),
        *state[1:],
    )


def unflatten(state):
    return active.State(
        passive.State(
            *(
                getattr(state, k)[0] if k in ("step_count", "elapsed_s") else getattr(state, k)
                for k in passive.State._fields
            )
        ),
        *(getattr(state, k) for k in active.State._fields[1:]),
    )


def initial_values(spec):
    state, p = definition_arrays(spec.model)
    n = p.tissue.cell_volume.size
    return flatten(state), LAYOUT_TYPE(
        np.ones(n, dtype=bool),
        np.arange(1, n + 1, dtype=np.int64),
        *p.tissue,
        *p.pump,
        *p[2:],
    )


def parameters(spec, layout):
    return active.Layout(
        passive.Layout(*(getattr(layout, "tissue_" + k) for k in passive.Layout._fields)),
        kinetic_pump.Parameters(
            *(getattr(layout, "pump_" + k) for k in kinetic_pump.Parameters._fields)
        ),
        *(getattr(layout, k) for k in active.Layout._fields[2:]),
    )


def controlled_parameters(parameters, control):
    if isinstance(control, Control):
        return parameters._replace(
            pump_available=parameters.pump_available * control.pump,
            channel_permeability=parameters.channel_permeability * control.channel,
        )
    return parameters


def checked_step(state, dt, control, parameters, active_mask):
    result, _, valid = active.step(unflatten(state), controlled_parameters(parameters, control), dt)
    return flatten(result), valid


def batch_signature(model):
    return model.species_ids, np.shape(
        model.tissue[passive.Layout._fields.index("boundary_values")]
    )


def working_size(spec):
    state, p = definition_arrays(spec.model)
    # Includes the dense boundary solve and complete state/field work buffers.
    return 4 * (sum(v.size for v in jax.tree.leaves((state, p))) + p.tissue.boundary_values.size**2)


def _check_fixed_steps(spec, steps):
    if spec.execution.solver != SOLVER_ID:
        raise ConfigError("BETSE update cannot be executed with another solver")
    tolerance = 8 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
    if not np.isfinite(steps).all() or np.any(abs(steps - spec.execution.dt) > tolerance):
        raise ConfigError("BETSE compatibility requires whole fixed steps")


def check_steps(spec, steps, controls):
    _check_fixed_steps(spec, steps)
    if not isinstance(controls, Control):
        raise ConfigError("BETSE controls must name pump and channel availability")
    for values in controls:
        if (
            values.shape != (len(steps), spec.execution.membrane_capacity)
            or not np.isfinite(values).all()
            or np.any((values < 0) | (values > 1))
        ):
            raise ConfigError("Invalid BETSE per-patch intervention fractions")


def integration_steps(spec, times):
    _check_fixed_steps(spec, np.diff(times))
    # Subtracting two clock labels would introduce tiny variable-step changes.
    return np.full(max(0, len(times) - 1), spec.execution.dt, dtype=np.float64)


def check_values(state, spec):
    initial, p = definition_arrays(spec.model)
    template = flatten(initial)
    scalar = np.asarray(state.step_count).ndim == 1
    history = STATE_TYPE(*(np.asarray(v)[None] if scalar else np.asarray(v) for v in state))
    length = len(history.step_count)
    for name, values, expected in zip(STATE_TYPE._fields, history, template, strict=True):
        if values.shape != (length, *expected.shape) or values.dtype != expected.dtype:
            raise ConfigError("BETSE state shape/precision differs: " + name)
        if not np.isfinite(values).all():
            raise NumericalError("Nonfinite BETSE state: " + name)
    for name in ("cell_concentration", "membrane_concentration", "outside_concentration"):
        if np.any(getattr(history, name) <= 0):
            raise NumericalError("BETSE concentration is not positive")
    for name in ("m_gate", "h_gate"):
        if np.any((getattr(history, name) < 0) | (getattr(history, name) > 1)):
            raise NumericalError("BETSE gate is outside [0,1]")
    count = history.step_count[:, 0]
    if np.any((count < 0) | (count > spec.execution.max_steps)) or np.any(np.diff(count) <= 0):
        raise ConfigError("BETSE step counts must increase within the declared bound")
    clock_error = abs(history.elapsed_s[:, 0] - count * spec.execution.dt)
    if np.any(clock_error > 6e-17):
        raise ConfigError("BETSE accumulated clock disagrees with completed steps")
    t = p.tissue
    cells, outside = passive.ownership(t, xp=np)
    membrane = history.membrane_inward_fmol.copy()
    membrane[:, p.potassium_index] += history.channel_inward_fmol
    cell_change = (
        (history.cell_concentration - initial.tissue.cell_concentration) * t.cell_volume * 1e15
    )
    outside_change = (
        (history.outside_concentration - initial.tissue.outside_concentration)
        * t.height
        * t.spacing**2
        * 1e15
    )
    cell_residual = cell_change - (membrane - history.junction_outward_fmol) @ cells.T
    outside_residual = (
        outside_change
        + membrane @ outside.T
        - history.reservoir_reset_fmol
        - history.stencil_exchange_fmol
    )
    epsn = 32 * count[:, None, None] * np.finfo(float).eps
    gamma = epsn / (1 - epsn)
    inside_scale = (
        abs(history.cell_concentration) + abs(initial.tissue.cell_concentration)
    ) * t.cell_volume * 1e15 + (abs(membrane) + abs(history.junction_outward_fmol)) @ cells.T
    outside_scale = (
        (abs(history.outside_concentration) + abs(initial.tissue.outside_concentration))
        * t.height
        * t.spacing**2
        * 1e15
        + abs(membrane) @ outside.T
        + abs(history.reservoir_reset_fmol)
        + abs(history.stencil_exchange_fmol)
    )
    inside_roundoff, outside_roundoff = gamma * inside_scale, gamma * outside_scale
    atol = np.asarray(spec.execution.material_balance_atol_fmol)[None, :, None]
    checks = (
        (cell_residual, atol + inside_roundoff),
        (outside_residual, atol + outside_roundoff),
        (
            cell_residual.sum(axis=-1) + outside_residual.sum(axis=-1),
            atol[..., 0] + inside_roundoff.sum(axis=-1) + outside_roundoff.sum(axis=-1),
        ),
    )
    for residual, budget in checks:
        if np.any(abs(residual) > budget):
            raise NumericalError("BETSE material balance exceeds its physical/roundoff budget")
    return dict(
        max_material_residual_fmol=max(float(np.max(abs(r), initial=0)) for r, _ in checks),
        max_material_error_over_budget=max(float(np.max(abs(r) / b, initial=0)) for r, b in checks),
        max_clock_error_s=float(np.max(clock_error, initial=0)),
    )


def check_checkpoint(spec, checkpoint):
    if int(np.asarray(checkpoint.state.step_count)[0]) != checkpoint.step_index:
        raise ConfigError("BETSE state clock differs from checkpoint metadata")


def observe_history(times, history, layout, requested, spec):
    p = jax.tree.map(np.asarray, parameters(spec, layout)).tissue
    requested = np.asarray(requested, dtype=float)
    records = []
    for time in requested:
        indices = np.flatnonzero(times == time)
        if len(indices) != 1:
            raise ConfigError("BETSE observations require an accepted fixed-step boundary")
        state = STATE_TYPE(*(v[int(indices[0])] for v in history))
        fields = passive.field(unflatten(state).tissue, p, xp=np)
        if not all(np.isfinite(v).all() for v in fields):
            raise NumericalError("Nonfinite BETSE observation field")
        records.append((np.asarray(time), *state, *fields))
    if records:
        return Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    sample = observe_history(
        times[:1], STATE_TYPE(*(v[:1] for v in history)), layout, times[:1], spec
    )
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def summarize(history, diagnostics, spec):
    return dict(
        model=MODEL_ID,
        solver=SOLVER_ID,
        species_ids=list(spec.model.species_ids),
        state_fields=list(STATE_TYPE._fields),
        observation_scope=OBSERVATION_SAMPLING,
        scheduled_changes=len(spec.experiment.changes),
        intervention_scope="held pump/channel availability fractions; intrinsic gates continue",
        material_convention=(
            "ordinary membrane plus channel transfer; separate reservoir/stencil exchange"
        ),
        metabolic_pools="maintained ATP/ADP/Pi",
        qualification_scope="synthetic native compatibility; no finite ATP or energy balance",
        **diagnostics,
    )
