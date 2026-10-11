"""Host schedule + pure JAX rollout, with observations outside the dynamics."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.devices import execution_device
from cells.core.errors import NumericalError as NumericalError
from cells.core.grid import checked_grid
from cells.core.resources import trace_bytes
from cells.core.schedule import control_values
from cells.core.schedule import event_index as event_index
from cells.core.specs import ConfigError, SimulationSpec, parse_spec
from cells.core.state import Checkpoint, initialise
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step, rk4_step


def _trace_budget(spec: SimulationSpec, steps: int) -> None:
    # Conservative allowance for device/host traces, temporaries, and observations.
    if trace_bytes(spec, steps) > spec.execution.max_trace_bytes:
        raise ConfigError("Estimated trace working storage exceeds max_trace_bytes")


def timeline(spec: SimulationSpec) -> np.ndarray:
    """Fixed mesh anchored at zero, split exactly at inputs and the final time."""
    end, dt = spec.experiment.end_time, spec.execution.dt
    count = end / dt
    if not math.isfinite(count) or count > spec.execution.max_steps:
        raise ConfigError("Nominal integration grid exceeds max_steps")
    nominal_count = math.ceil(count)
    _trace_budget(spec, nominal_count)
    points = {0.0, end, *(change.time for change in spec.experiment.changes)}
    points.update(i * dt for i in range(1, nominal_count) if i * dt < end)
    times = np.array(sorted(points), dtype=np.float64)
    if len(times) - 1 > spec.execution.max_steps:
        raise ConfigError("Event-split integration grid exceeds max_steps")
    _trace_budget(spec, len(times) - 1)
    get_model(spec.model).check_steps(spec, np.diff(times), control_values(spec, times[:-1]))
    return times


def validate_checkpoint(spec: SimulationSpec, checkpoint: Checkpoint, times=None) -> None:
    model = get_model(spec.model)
    if times is None:
        times = checked_grid(spec)
    if (
        isinstance(checkpoint.time, bool)
        or not isinstance(checkpoint.time, (int, float))
        or not math.isfinite(checkpoint.time)
    ):
        raise ConfigError("Checkpoint time must be a finite number")
    if type(checkpoint.step_index) is not int or not 0 <= checkpoint.step_index < len(times):
        raise ConfigError("Checkpoint step index is outside the declared integration grid")
    if checkpoint.time != times[checkpoint.step_index]:
        raise ConfigError("Checkpoint time does not match its accepted integration boundary")
    if type(checkpoint.event_index) is not int or checkpoint.event_index != event_index(
        spec, checkpoint.time
    ):
        raise ConfigError("Checkpoint event position is inconsistent with its schedule")
    if (
        type(checkpoint.state) is not model.STATE_TYPE
        or type(checkpoint.layout) is not model.LAYOUT_TYPE
    ):
        raise ConfigError("Checkpoint state/layout types do not match the declared model")
    initial = initialise(spec)
    for name, values, target in zip(
        model.STATE_TYPE._fields, checkpoint.state, initial.state, strict=True
    ):
        array = np.asarray(values)
        if array.shape != target.shape or array.dtype != target.dtype:
            raise ConfigError(f"Checkpoint {name} has incompatible shape or precision")
    expected = initial.layout
    for name, values, target in zip(expected._fields, checkpoint.layout, expected, strict=True):
        array = np.asarray(values)
        if array.dtype != target.dtype or not np.array_equal(array, np.asarray(target)):
            raise ConfigError(f"Checkpoint layout {name} does not match the model definition")
    model.check_values(model.STATE_TYPE(*(np.asarray(v) for v in checkpoint.state)), spec)
    if hasattr(model, "check_checkpoint"):
        model.check_checkpoint(spec, checkpoint)
    if checkpoint.step_index == 0 and any(
        not np.array_equal(a, b) for a, b in zip(checkpoint.state, initial.state, strict=True)
    ):
        raise ConfigError("Time-zero checkpoint does not match the declared initial state")


def branch_checkpoint(
    original: SimulationSpec, checkpoint: Checkpoint, changed: SimulationSpec
) -> Checkpoint:
    """Only supported future inputs, the horizon, and observations may change."""
    validate_checkpoint(original, checkpoint)
    changed = parse_spec(changed.to_dict())
    if original.model != changed.model or original.execution != changed.execution:
        raise ConfigError("A branch may not change model or execution settings")
    past_original = tuple(p for p in original.experiment.changes if p.time < checkpoint.time)
    past_changed = tuple(p for p in changed.experiment.changes if p.time < checkpoint.time)
    if past_original != past_changed:
        raise ConfigError("A branch cannot rewrite the input schedule before its checkpoint")
    result = replace(checkpoint, event_index=event_index(changed, checkpoint.time))
    try:
        validate_checkpoint(changed, result)
    except ConfigError as exc:
        raise ConfigError(
            "Branch must retain the checkpoint as an integration boundary and a valid horizon; "
            "retain/add a supported control entry at that exact time if necessary"
        ) from exc
    return result


def _rollout(state, steps, controls, parameters, active, rhs):
    def advance(current, inputs):
        dt, control = inputs
        updated = rk4_step(rhs, current, dt, control, parameters, active)
        return updated, updated

    return jax.lax.scan(advance, state, (steps, controls))


_compiled_rollout = jax.jit(_rollout, static_argnums=(5,))


def _eager_rollout(state, steps, controls, parameters, active, rhs):
    records = []
    for index, dt in enumerate(steps):
        control = jax.tree.map(lambda v, i=index: v[i], controls)
        state = rk4_step(rhs, state, dt, control, parameters, active)
        records.append(state)
    history = jax.tree.map(lambda *values: jnp.stack(values), *records)
    return state, history


def _checked_rollout(state, steps, controls, parameters, active, rhs, domain):
    def advance(carry, inputs):
        current, previous_ok = carry
        dt, control = inputs
        updated, ok = jax.lax.cond(
            previous_ok,
            lambda y: rk4_checked_step(rhs, domain, y, dt, control, parameters, active),
            lambda y: (y, jnp.array(False)),
            current,
        )
        return (updated, ok), (updated, ok)

    (final, _), (history, valid) = jax.lax.scan(
        advance, (state, jnp.array(True)), (steps, controls)
    )
    return final, history, valid


_compiled_checked_rollout = jax.jit(_checked_rollout, static_argnums=(5, 6))


def integration_steps(spec, times):
    """A discrete model may preserve its declared step instead of subtracting labels."""
    method = getattr(get_model(spec.model), "integration_steps", None)
    return np.diff(times) if method is None else method(spec, times)


def _discrete_rollout(state, steps, controls, parameters, active, checked_step):
    def advance(carry, inputs):
        current, previous_ok = carry
        dt, control = inputs
        updated, ok = jax.lax.cond(
            previous_ok,
            lambda y: checked_step(y, dt, control, parameters, active),
            lambda y: (y, jnp.array(False)),
            current,
        )
        return (updated, ok), (updated, ok)

    (final, _), (history, valid) = jax.lax.scan(
        advance, (state, jnp.array(True)), (steps, controls)
    )
    return final, history, valid


_compiled_discrete_rollout = jax.jit(_discrete_rollout, static_argnums=(5,))


def _checked_eager_rollout(state, steps, controls, parameters, active, rhs, domain):
    records = []
    # disable_jit avoids compiling a fresh lax.cond closure for each eager stage.
    with jax.disable_jit():
        for index, dt in enumerate(steps):
            control = jax.tree.map(lambda v, i=index: v[i], controls)
            state, valid = rk4_checked_step(rhs, domain, state, dt, control, parameters, active)
            if not bool(valid):
                raise NumericalError(
                    f"RK4 trial/endpoint domain failure at local step {index + 1}; no step accepted"
                )
            records.append(state)
    history = jax.tree.map(lambda *values: jnp.stack(values), *records)
    return state, history, np.ones(len(steps), dtype=bool)


@dataclass(frozen=True)
class RunResult:
    spec: SimulationSpec
    final: Checkpoint
    start_step: int
    times: np.ndarray
    history: Any  # [accepted_time, ...model-declared field axes], not fixed to one cell axis.
    observations: Any
    timings: dict[str, float]
    diagnostics: dict[str, float]

    # Compatibility accessors for the original synthetic fixture. EMT uses
    # explicitly named regulatory coordinates through result.history instead.
    @property
    def amount(self):
        return self.history.amount

    @property
    def supplied(self):
        return self.history.supplied

    @property
    def degraded(self):
        return self.history.degraded

    @property
    def max_balance_error(self):
        return self.diagnostics["max_balance_error_fmol"]

    def checkpoint_at(self, time: float) -> Checkpoint:
        matches = np.flatnonzero(self.times == time)
        if not len(matches):
            raise ConfigError("Checkpoints require an exact accepted time; see accepted_times")
        index = int(matches[0])
        state = type(self.history)(*(np.array(values[index], copy=True) for values in self.history))
        return Checkpoint(
            jax.device_put(state, execution_device(self.spec.execution.backend)),
            self.final.layout,
            float(time),
            self.start_step + index,
            event_index(self.spec, time),
        )


def run(spec: SimulationSpec, checkpoint: Checkpoint | None = None) -> RunResult:
    started = perf_counter()
    spec = parse_spec(spec.to_dict())  # Also validates specs constructed through the Python API.
    grid = timeline(spec)
    checkpoint = initialise(spec) if checkpoint is None else checkpoint
    validate_checkpoint(spec, checkpoint, grid)
    times = grid[checkpoint.step_index :]
    requested = [t for t in spec.experiment.observation_times if t >= checkpoint.time]
    return _run_segment(spec, checkpoint, times, requested, started=started)


def _run_segment(spec, checkpoint, times, requested, *, started=None):
    """Shared numerical/observer path; callers validate the grid and checkpoint.

    A segment only partitions accepted storage. It must never insert solver steps.
    """
    started = perf_counter() if started is None else started
    model = get_model(spec.model)
    controls = control_values(spec, times[:-1])
    device = execution_device(spec.execution.backend)
    state = jax.device_put(checkpoint.state, device)
    layout = jax.device_put(checkpoint.layout, device)
    steps, controls, parameters = jax.device_put(
        (integration_steps(spec, times), controls, model.parameters(spec, layout)), device
    )
    jax.block_until_ready((state, steps, controls, parameters))
    prepared = perf_counter()
    compile_seconds = 0.0
    if len(times) > 1:
        if hasattr(model, "checked_step"):
            args = (state, steps, controls, parameters, layout.active)
            if spec.execution.jit:
                compiled = _compiled_discrete_rollout.lower(*args, model.checked_step).compile()
                compile_seconds = perf_counter() - prepared
                execute_started = perf_counter()
                final_state, history, valid = compiled(*args)
            else:
                execute_started = perf_counter()
                with jax.disable_jit():
                    final_state, history, valid = _discrete_rollout(*args, model.checked_step)
            failed = np.flatnonzero(~np.asarray(valid))
            if len(failed):
                index = int(failed[0])
                raise NumericalError(
                    f"{spec.execution.solver} domain failure on "
                    f"[{times[index]}, {times[index + 1]}]; no invalid step accepted"
                )
        elif hasattr(model, "domain_valid"):
            args = (state, steps, controls, parameters, layout.active)
            if spec.execution.jit:
                compiled = _compiled_checked_rollout.lower(
                    *args, model.rhs, model.domain_valid
                ).compile()
                compile_seconds = perf_counter() - prepared
                execute_started = perf_counter()
                final_state, history, valid = compiled(*args)
            else:
                execute_started = perf_counter()
                final_state, history, valid = _checked_eager_rollout(
                    *args, model.rhs, model.domain_valid
                )
            failed = np.flatnonzero(~np.asarray(valid))
            if len(failed):
                index = int(failed[0])
                raise NumericalError(
                    f"RK4 trial/endpoint domain failure on [{times[index]}, {times[index + 1]}]; "
                    "no invalid state accepted or repaired"
                )
        elif spec.execution.jit:
            compiled = _compiled_rollout.lower(
                state, steps, controls, parameters, layout.active, model.rhs
            ).compile()
            compile_seconds = perf_counter() - prepared
            execute_started = perf_counter()
            final_state, history = compiled(state, steps, controls, parameters, layout.active)
        else:
            execute_started = perf_counter()
            final_state, history = _eager_rollout(
                state, steps, controls, parameters, layout.active, model.rhs
            )
        jax.block_until_ready((final_state, history))
        execute_seconds = perf_counter() - execute_started
        transfer_started = perf_counter()
        arrays = tuple(
            np.concatenate((np.asarray(start)[None, :], np.asarray(values)), axis=0)
            for start, values in zip(state, history, strict=True)
        )
    else:
        transfer_started = perf_counter()
        final_state = state
        arrays = tuple(np.array(v, copy=True)[None, :] for v in state)
        execute_seconds = 0.0
    analysis_started = perf_counter()
    accepted_history, observations, final, diagnostics = _analyse_segment(
        spec, checkpoint, times, arrays, final_state, layout, requested
    )
    timings = {
        "preparation_seconds": prepared - started,
        "compile_or_cache_seconds": compile_seconds,
        "execute_seconds": execute_seconds,
        "host_transfer_and_assembly_seconds": analysis_started - transfer_started,
        "analysis_seconds": perf_counter() - analysis_started,
        "total_run_seconds": perf_counter() - started,
    }
    return RunResult(
        spec,
        final,
        checkpoint.step_index,
        times,
        accepted_history,
        observations,
        timings,
        diagnostics,
    )


def _analyse_segment(spec, checkpoint, times, arrays, final_state, layout, requested):
    """Shared ordinary model checks/observers on already computed accepted states."""
    model = get_model(spec.model)
    accepted_history = model.STATE_TYPE(*arrays)
    diagnostics = model.check_values(accepted_history, spec)
    observations = model.observe_history(times, accepted_history, layout, requested, spec)
    for values in (times, *arrays):
        values.setflags(write=False)
    final = Checkpoint(
        final_state,
        layout,
        float(times[-1]),
        checkpoint.step_index + len(times) - 1,
        event_index(spec, float(times[-1])),
    )
    return accepted_history, observations, final, diagnostics
