"""Host schedule + pure JAX rollout, with observations outside the dynamics."""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import blas_threads, phases
from cells.core.devices import execution_device
from cells.core.errors import NumericalError as NumericalError
from cells.core.grid import EventGrid, checked_grid, require_refinement_model
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


def _refuse_projective(spec: SimulationSpec) -> None:
    # Fine-only execution paths must not silently ignore a projective block.
    if getattr(spec, "projective", None) is not None:
        raise ConfigError("execution.projective runs only through cells.core.runner.run")


def timeline(spec: SimulationSpec) -> np.ndarray:
    """The shared exact grid, with storage admission before allocating a trace."""
    _refuse_projective(spec)
    require_refinement_model(spec)
    grid = EventGrid(spec)
    _trace_budget(spec, len(grid) - 1)
    times = np.fromiter(grid, dtype=np.float64, count=len(grid))
    get_model(spec.model).check_steps(spec, np.diff(times), control_values(spec, times[:-1]))
    return times


def validate_checkpoint(
    spec: SimulationSpec, checkpoint: Checkpoint, times=None, *, initial=None
) -> None:
    """Refuse a checkpoint that is not an accepted, valid state of this definition.

    ``initial`` may pass initialise(spec) when several checkpoints of one
    definition are validated, so the initial state is built once.
    """
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
    initial = initialise(spec) if initial is None else initial
    # The layout type the definition binds (a declared field solver can select
    # its own, e.g. surface_field.FLOOR_SOLVER_ID), or the model's.
    if (
        type(checkpoint.state) is not model.STATE_TYPE
        or type(checkpoint.layout) not in (model.LAYOUT_TYPE, type(initial.layout))
        or len(checkpoint.layout) != len(initial.layout)
    ):
        raise ConfigError("Checkpoint state/layout types do not match the declared model")
    if checkpoint.time < initial.time:
        raise ConfigError("Checkpoint precedes this model's initial epoch")
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
    model.check_values(
        model.STATE_TYPE(*(np.asarray(v) for v in checkpoint.state)),
        spec,
        **check_steps(model, checkpoint.step_index, 1),
    )
    if hasattr(model, "check_checkpoint"):
        model.check_checkpoint(spec, checkpoint)
    if checkpoint.step_index == initial.step_index and any(
        not np.array_equal(a, b) for a, b in zip(checkpoint.state, initial.state, strict=True)
    ):
        raise ConfigError("Initial checkpoint does not match the declared initial state")


def branch_checkpoint(
    original: SimulationSpec, checkpoint: Checkpoint, changed: SimulationSpec
) -> Checkpoint:
    """Only supported future inputs, the horizon, and observations may change."""
    validate_checkpoint(original, checkpoint)
    changed = parse_spec(changed.to_dict())
    if (
        original.model != changed.model
        or original.execution != changed.execution
        or getattr(original, "projective", None) != getattr(changed, "projective", None)
    ):
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


def _window_rollout(state, steps, controls, parameters, active, enabled, rhs, domain, checked_step):
    """Fixed execution shape; disabled slots never call a model or advance state."""

    def advance(carry, inputs):
        current, previous_ok = carry
        dt, control, real_step = inputs

        def evaluate(value):
            if checked_step is not None:
                return checked_step(value, dt, control, parameters, active)
            if domain is not None:
                return rk4_checked_step(rhs, domain, value, dt, control, parameters, active)
            return rk4_step(rhs, value, dt, control, parameters, active), jnp.array(True)

        updated, ok = jax.lax.cond(
            real_step & previous_ok,
            evaluate,
            lambda value: (value, previous_ok),
            current,
        )
        return (updated, ok), (updated, ok)

    (final, _), (history, valid) = jax.lax.scan(
        advance, (state, jnp.array(True)), (steps, controls, enabled)
    )
    return final, history, valid


_compiled_window_rollout = jax.jit(_window_rollout, static_argnums=(6, 7, 8))


@dataclass
class _WindowExecution:
    """One iterator owns one compiled shape and its complete fixed definition.

    row_checks: the run's compiled device row checks (core.row_checks.DeviceRowChecks) under
    WindowPolicy row_checks="device", else None (every row checked by check_values).
    """

    spec: SimulationSpec
    width: int
    compiled: Any = None
    row_checks: Any = None


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


@dataclass(frozen=True)
class CheckedRunResult(RunResult):
    """A window whose rows the device checked (WindowPolicy row_checks="device").

    row_checks is the window's core.row_checks.Outcome: whether the device or the host's
    check_values decided it, why it was handed back, and the device's ratios to the bounds.
    Its diagnostics are the device's maxima when the device decided (reported, not judged).
    """

    row_checks: Any


def run(spec: SimulationSpec, checkpoint: Checkpoint | None = None) -> RunResult:
    blas_threads.require_pinned("run")  # D190: refused unless every BLAS is at 1 thread.
    started = perf_counter()
    spec = parse_spec(spec.to_dict())  # Also validates specs constructed through the Python API.
    if spec.projective is not None:  # Opt-in coarse mode; absent, nothing below changes.
        from cells.core.projective import run_projective

        return run_projective(spec, checkpoint, started=started)
    grid = timeline(spec)
    checkpoint = initialise(spec) if checkpoint is None else checkpoint
    validate_checkpoint(spec, checkpoint, grid)
    times = grid[checkpoint.step_index :]
    requested = [t for t in spec.experiment.observation_times if t >= checkpoint.time]
    return _run_segment(spec, checkpoint, times, requested, started=started)


def _compiled(record, seconds):
    record.end("compile", seconds=seconds)
    return seconds


def _run_segment(spec, checkpoint, times, requested, *, started=None, window_execution=None):
    """Shared numerical/observer path; callers validate the grid and checkpoint.

    A segment only partitions accepted storage. It must never insert solver steps. Its
    phases write start, completion and failure records (core.phases.Recorder).
    """
    with phases.Recorder() as record:
        return _segment(
            spec,
            checkpoint,
            times,
            requested,
            record,
            started=started,
            window_execution=window_execution,
        )


def _segment(spec, checkpoint, times, requested, record, *, started=None, window_execution=None):
    # A windowed run's later windows (its executable already compiled) report at DEBUG.
    later = window_execution is not None and window_execution.compiled is not None
    record.start("preparation", debug=later, steps=len(times) - 1)
    _refuse_projective(spec)
    started = perf_counter() if started is None else started
    model = get_model(spec.model)
    controls = control_values(spec, times[:-1])
    device = execution_device(spec.execution.backend)
    state = jax.device_put(checkpoint.state, device)
    layout = jax.device_put(checkpoint.layout, device)
    step_values = integration_steps(spec, times)
    enabled = None
    if window_execution is not None and len(times) > 1:
        if (
            window_execution.spec is not spec
            or not spec.execution.jit
            or type(window_execution.width) is not int
            or window_execution.width < len(step_values)
        ):
            raise ConfigError("Prepared window execution differs from its definition or width")
        padding = window_execution.width - len(step_values)
        enabled = jax.device_put(np.arange(window_execution.width) < len(step_values), device)
        step_values = np.pad(step_values, (0, padding))
        controls = jax.tree.map(
            lambda value: np.pad(value, ((0, padding), *((0, 0) for _ in value.shape[1:]))),
            controls,
        )
    steps, controls, parameters = jax.device_put(
        (step_values, controls, model.parameters(spec, layout)), device
    )
    jax.block_until_ready((state, steps, controls, parameters))
    prepared = perf_counter()
    record.end("preparation", debug=later, steps=len(times) - 1, seconds=prepared - started)
    compile_seconds = 0.0
    window_history = None  # The window rollout's full-width device history (row checks).
    if len(times) > 1:
        if window_execution is not None:
            args = (state, steps, controls, parameters, layout.active, enabled)
            if window_execution.compiled is None:
                record.start("compile")
                window_execution.compiled = _compiled_window_rollout.lower(
                    *args,
                    getattr(model, "rhs", None),
                    getattr(model, "domain_valid", None),
                    getattr(model, "checked_step", None),
                ).compile()
                compile_seconds = _compiled(record, perf_counter() - prepared)
            record.start("execute", debug=later, steps=len(times) - 1)
            execute_started = perf_counter()
            final_state, history, valid = window_execution.compiled(*args)
            window_history = history
            real_steps = len(times) - 1
            history = jax.tree.map(lambda values: values[:real_steps], history)
            failed = np.flatnonzero(~np.asarray(valid[:real_steps]))
            if len(failed):
                index = int(failed[0])
                label = spec.execution.solver if hasattr(model, "checked_step") else "RK4"
                raise NumericalError(
                    f"{label} trial/endpoint domain failure on "
                    f"[{times[index]}, {times[index + 1]}]; no invalid step accepted or repaired"
                )
        elif hasattr(model, "checked_step"):
            args = (state, steps, controls, parameters, layout.active)
            if spec.execution.jit:
                record.start("compile")
                compiled = _compiled_discrete_rollout.lower(*args, model.checked_step).compile()
                compile_seconds = _compiled(record, perf_counter() - prepared)
                record.start("execute", debug=later, steps=len(times) - 1)
                execute_started = perf_counter()
                final_state, history, valid = compiled(*args)
            else:
                record.start("execute", debug=later, steps=len(times) - 1)
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
                record.start("compile")
                compiled = _compiled_checked_rollout.lower(
                    *args, model.rhs, model.domain_valid
                ).compile()
                compile_seconds = _compiled(record, perf_counter() - prepared)
                record.start("execute", debug=later, steps=len(times) - 1)
                execute_started = perf_counter()
                final_state, history, valid = compiled(*args)
            else:
                record.start("execute", debug=later, steps=len(times) - 1)
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
            record.start("compile")
            compiled = _compiled_rollout.lower(
                state, steps, controls, parameters, layout.active, model.rhs
            ).compile()
            compile_seconds = _compiled(record, perf_counter() - prepared)
            record.start("execute", debug=later, steps=len(times) - 1)
            execute_started = perf_counter()
            final_state, history = compiled(state, steps, controls, parameters, layout.active)
        else:
            record.start("execute", debug=later, steps=len(times) - 1)
            execute_started = perf_counter()
            final_state, history = _eager_rollout(
                state, steps, controls, parameters, layout.active, model.rhs
            )
        jax.block_until_ready((final_state, history))
        execute_seconds = perf_counter() - execute_started
        record.end("execute", debug=later, steps=len(times) - 1, seconds=execute_seconds)
        launched = None
        if window_history is not None and window_execution.row_checks is not None:
            checks = window_execution.row_checks
            if checks.executable is None:
                record.start("compile", program="row_checks")
                seconds = checks.compile(state, window_history, parameters)
                record.end("compile", seconds=seconds, program="row_checks")
                compile_seconds += seconds
            launch_started = perf_counter()
            pending = checks.launch(
                state, window_history, len(times) - 1, checkpoint.step_index, parameters
            )
            launched = (checks, pending, launch_started)
        transfer_started = perf_counter()
        arrays = tuple(
            np.concatenate((np.asarray(start)[None, :], np.asarray(values)), axis=0)
            for start, values in zip(state, history, strict=True)
        )
    else:
        launched = None
        transfer_started = perf_counter()
        final_state = state
        arrays = tuple(np.array(v, copy=True)[None, :] for v in state)
        execute_seconds = 0.0
    analysis_started = perf_counter()
    if launched is None:
        accepted_history, observations, final, diagnostics = _analyse_segment(
            spec, checkpoint, times, arrays, final_state, layout, requested
        )
    else:
        (accepted_history, observations, final, diagnostics), checked = _analyse_checked_segment(
            spec, checkpoint, times, arrays, final_state, layout, requested, launched
        )
    timings = {
        "preparation_seconds": prepared - started,
        "compile_or_cache_seconds": compile_seconds,
        "execute_seconds": execute_seconds,
        "host_transfer_and_assembly_seconds": analysis_started - transfer_started,
        "analysis_seconds": perf_counter() - analysis_started,
        "total_run_seconds": perf_counter() - started,
    }
    values = (
        spec,
        final,
        checkpoint.step_index,
        times,
        accepted_history,
        observations,
        timings,
        diagnostics,
    )
    if launched is None:
        return RunResult(*values)
    outcome, device_seconds, host_seconds = checked
    # From launch to the summary (overlapping the transfer), and a handed-back window's host
    # check (within analysis); phase_totals lists both under "other", counted once.
    timings["device_row_check_seconds"] = device_seconds
    timings["host_row_check_seconds"] = host_seconds
    return CheckedRunResult(*values, outcome)


def takes_steps(model):
    """Whether check_values takes each row's accepted-step index (steps=...).

    Such checks scale their rounding allowances with the steps accepted so far.
    """
    try:
        return "steps" in inspect.signature(model.check_values).parameters
    except (TypeError, ValueError):
        return False


def check_steps(model, first, rows):
    """check_values keywords for rows at consecutive global step indices from first."""
    return {"steps": first + np.arange(rows)} if takes_steps(model) else {}


def _analyse_segment(spec, checkpoint, times, arrays, final_state, layout, requested):
    """Shared ordinary model checks/observers on already computed accepted states."""
    model = get_model(spec.model)
    accepted_history = model.STATE_TYPE(*arrays)
    diagnostics = model.check_values(
        accepted_history, spec, **check_steps(model, checkpoint.step_index, len(times))
    )
    return _accept_segment(
        model, spec, checkpoint, times, arrays, accepted_history, final_state, layout, requested
    ) + (diagnostics,)


def _analyse_checked_segment(
    spec, checkpoint, times, arrays, final_state, layout, requested, launched
):
    """_analyse_segment for a window whose rows the device checked (core/row_checks.py).

    launched: (DeviceRowChecks, the launched summary, its launch time). A window the device
    hands back is decided by today's check_values, which raises today's exception class and
    message; a clean one takes the device's maxima as its diagnostics. Returns
    _analyse_segment's values and (outcome, device seconds from launch, host check seconds).
    """
    checks, pending, launched_at = launched
    summary, outcome = checks.outcome(pending)
    device_seconds = perf_counter() - launched_at
    model = get_model(spec.model)
    accepted_history = model.STATE_TYPE(*arrays)
    host_seconds = 0.0
    if outcome.decided_by == "host":
        began = perf_counter()
        diagnostics = model.check_values(
            accepted_history, spec, **check_steps(model, checkpoint.step_index, len(times))
        )
        host_seconds = perf_counter() - began
    else:
        diagnostics = checks.diagnostics(summary)
    accepted = _accept_segment(
        model, spec, checkpoint, times, arrays, accepted_history, final_state, layout, requested
    )
    return accepted + (diagnostics,), (outcome, device_seconds, host_seconds)


def _accept_segment(
    model, spec, checkpoint, times, arrays, accepted_history, final_state, layout, requested
):
    """(history, observations, final checkpoint) of a segment whose rows passed their checks."""
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
    return accepted_history, observations, final
