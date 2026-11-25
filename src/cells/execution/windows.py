"""Bounded single-world execution using the ordinary checked numerical path."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from cells.definitions.specs import ConfigError, SimulationSpec, _integer, _number, parse_spec
from cells.execution import blas_threads, row_checks
from cells.execution import energy_check as energy
from cells.execution.devices import execution_device
from cells.execution.grid import EventGrid, applied_definition, checked_grid, require_scalar_path
from cells.execution.resources import fixed_bytes, row_bytes
from cells.execution.runner import (
    CheckedRunResult,
    _run_segment,
    _WindowExecution,
    takes_steps,
    validate_checkpoint,
    with_energy_record,
)
from cells.execution.state import Checkpoint, initialise
from cells.registry.models import get_model


@dataclass(frozen=True)
class WindowPolicy:
    """How a windowed run is cut, recorded and checked.

    row_checks is the scalar windowed path's choice of where every accepted row is checked:
    "host" (the default: the model's check_values) or "device" (execution/row_checks.py: the
    model's compiled device checks, with windows near a bound decided by the host). It is an
    execution choice, so a restart may change it. Only "device" is written by to_dict(), so
    every earlier policy record keeps its bytes. The batch and vector paths refuse "device".
    """

    window_steps: int = 256
    recording: str = "observations"
    row_checks: str = "host"

    def __post_init__(self):
        _integer(self.window_steps, "window_steps")
        if type(self.recording) is not str or self.recording not in (
            "full",
            "observations",
            "checkpoints",
        ):
            raise ConfigError("recording must be full, observations or checkpoints")
        if type(self.row_checks) is not str or self.row_checks not in row_checks.MODES:
            raise ConfigError("row_checks must be host or device")

    def to_dict(self):
        out = {"window_steps": self.window_steps, "recording": self.recording}
        if self.row_checks != "host":
            out["row_checks"] = self.row_checks
        return out


DEFAULT_POLICY = WindowPolicy()


@dataclass(frozen=True)
class WindowPlan:
    spec: SimulationSpec
    policy: WindowPolicy
    grid: EventGrid
    start_step: int
    window_count: int
    max_observations: int
    estimated_working_bytes: int
    # D283: the declared definition where the clock snaps an event (spec is then its applied copy,
    # applied_definition), and the snaps; None and () otherwise.
    declared: SimulationSpec | None = None
    snapped: tuple = ()


def _plan_windows_metadata(spec, policy=DEFAULT_POLICY, checkpoint=None, *, energy_check=False):
    """energy_check: the caller is the scalar window path, which runs the step-doubled energy
    check; a definition selecting it is refused on every other path (the batch and vector
    windows share this planner), fail-closed."""
    spec = parse_spec(spec.to_dict())
    declared, (spec, snapped) = spec, applied_definition(spec)  # D283: () without a snap.
    if energy.selected(spec) and not energy_check:
        raise ConfigError(
            "execution.energy_check runs only through cells.execution.runner.run and the "
            "scalar windows (refused on this path)"
        )
    require_scalar_path(spec, energy_check)  # Declared fine windows take the same rule.
    if type(policy) is not WindowPolicy:
        raise ConfigError("Expected a WindowPolicy")
    policy = WindowPolicy(**policy.to_dict())
    if policy.row_checks == "device":
        row_checks.admit(spec)
    grid = EventGrid(spec)
    if checkpoint is not None and type(checkpoint) is not Checkpoint:
        raise ConfigError("Expected a complete Checkpoint")
    start_time = 0.0 if checkpoint is None else _number(checkpoint.time, "checkpoint time")
    start = grid.exact_index(start_time)
    remaining = len(grid) - 1 - start
    width = min(policy.window_steps, remaining)
    # Count only the largest resident observation group, without keeping one
    # counter per window. Boundary samples belong to the preceding window.
    peak, count, previous = 0, 0, None
    requested = spec.experiment.observation_times
    for i in range(bisect_left(requested, start_time), len(requested)):
        bucket = max(0, (bisect_left(grid, requested[i]) - start - 1) // policy.window_steps)
        count = count + 1 if bucket == previous else 1
        peak, previous = max(peak, count), bucket
    # Two adjacent results may overlap in a consuming for-loop. Reserve an
    # additional observation row for continuity and complete restart storage.
    # The world's layout once (fixed_bytes, FR-43), its two results' and two restarts' rows each.
    estimate = fixed_bytes(spec) + 2 * row_bytes(spec, width, peak + 1) + 2 * row_bytes(spec, 0, 0)
    estimate += 2 * energy.trace_bytes(spec, width)  # The energy check's own values (0 without it).
    if estimate > spec.execution.max_trace_bytes:
        raise ConfigError("Estimated window working storage exceeds max_trace_bytes")
    return WindowPlan(
        spec,
        policy,
        grid,
        start,
        max(1, (remaining + policy.window_steps - 1) // policy.window_steps),
        peak,
        estimate,
        declared if snapped else None,
        snapped,
    )


def _validate_window_plan(plan, checkpoint, *, energy_check=False):
    # Validate the complete declared clock, including before a restart. A short
    # or completed suffix must not turn that full-history check into one call
    # per historical step. checked_grid still caps its chunks to the storage
    # budget; this width changes neither the clock nor the execution window.
    checked_grid(plan.spec)
    if checkpoint is not None:
        validate_checkpoint(plan.spec, checkpoint, plan.grid, energy_check=energy_check)


def plan_windows(spec, policy=DEFAULT_POLICY, checkpoint=None):
    plan = _plan_windows_metadata(spec, policy, checkpoint, energy_check=True)
    if checkpoint is not None:  # A step-doubled run's first row takes its energy record here.
        checkpoint = with_energy_record(plan.spec, checkpoint)
    _validate_window_plan(plan, checkpoint, energy_check=True)
    return plan


def _observation_tail(model, spec, observations, previous, grid):
    """Read-only sampled-state continuity shared by scalar and cohort windows.

    previous is the last sampled row of the earlier windows and, for models whose
    checks take step counts, its accepted-step index on grid (those models observe
    accepted integration boundaries only).
    """
    if len(observations.times):
        sampled = model.STATE_TYPE(*(getattr(observations, k) for k in model.STATE_TYPE._fields))
        counting = takes_steps(model)
        steps = [grid.exact_index(float(t)) for t in observations.times] if counting else None
        if previous is not None:
            row, step = previous
            joined = model.STATE_TYPE(
                *(np.concatenate((a, b)) for a, b in zip(row, sampled, strict=True))
            )
            model.check_values(joined, spec, **({"steps": [step, *steps]} if counting else {}))
        previous = model.STATE_TYPE(*(v[-1:].copy() for v in sampled)), steps and steps[-1]
    for value in vars(observations).values():
        value.setflags(write=False)
    return previous


def _iter_windows(plan, checkpoint):
    spec = plan.spec
    checkpoint = initialise(spec) if checkpoint is None else checkpoint
    checkpoint = with_energy_record(spec, checkpoint)  # Unchanged without the energy check.
    validate_checkpoint(spec, checkpoint, plan.grid, energy_check=True)
    requested = spec.experiment.observation_times
    observation_index = bisect_left(requested, checkpoint.time)
    previous_observed = None
    model = get_model(spec.model)
    remaining = len(plan.grid) - 1 - plan.start_step
    execution = (
        _WindowExecution(spec, min(plan.policy.window_steps, remaining))
        if spec.execution.jit and remaining
        else None
    )
    if execution is not None and plan.policy.row_checks == "device":
        execution.row_checks = row_checks.DeviceRowChecks.build(
            spec, checkpoint, execution_device(spec.execution.backend)
        )
    for times in plan.grid.windows(plan.start_step, plan.policy.window_steps):
        stop = bisect_right(requested, float(times[-1]))
        result = _run_segment(
            spec,
            checkpoint,
            times,
            requested[observation_index:stop],
            window_execution=execution,
        )
        previous_observed = _observation_tail(
            model, spec, result.observations, previous_observed, plan.grid
        )
        observation_index = stop
        checkpoint = result.final
        yield result
        del result


def iter_windows(spec, policy=DEFAULT_POLICY, checkpoint=None):
    """Yield fully checked windows; retaining them is the caller's memory choice.

    Preflight runs before returning the iterator. Recording affects the disk
    writer only; an iterator/sink always sees every checked state and observation.
    """
    blas_threads.require_pinned("iter_windows")  # D190.
    return _iter_windows(plan_windows(spec, policy, checkpoint), checkpoint)


def merge_diagnostics(total, current):
    """The seven current models declare maximum-error diagnostics, not averages."""
    if total and total.keys() != current.keys():
        raise ConfigError("Window diagnostic fields changed during execution")
    for name, value in current.items():
        if not name.startswith("max_") or not np.isfinite(value) or value < 0:
            raise ConfigError("Window diagnostics require explicit nonnegative maximum reducers")
        total[name] = max(total.get(name, 0.0), float(value))


@dataclass(frozen=True)
class WindowedResult:
    spec: SimulationSpec
    policy: WindowPolicy
    final: Checkpoint
    start_step: int
    start_time: float
    diagnostics: dict
    timings: dict
    resources: dict

    def summary(self):
        model = get_model(self.spec.model)
        endpoint = model.STATE_TYPE(*(np.asarray(v)[None] for v in self.final.state))
        return {
            "status": "complete",
            "start_time": self.start_time,
            "end_time": self.final.time,
            "executed_steps": self.final.step_index - self.start_step,
            "global_step_index": self.final.step_index,
            "active_cells": int(np.count_nonzero(self.final.layout.active)),
            "capacity": self.spec.execution.capacity,
            **model.summarize(endpoint, self.diagnostics, self.spec),
        }


def _consume_windows(plan, checkpoint, sink, *, started, preparation_seconds):
    diagnostics, timings = {}, {}
    peak_history = peak_observations = observation_count = window_count = 0
    sink_seconds = 0.0
    device = plan.policy.row_checks == "device"
    report = row_checks.new_report() if device else None
    for window in _iter_windows(plan, checkpoint):
        merge_diagnostics(diagnostics, window.diagnostics)
        if device and isinstance(window, CheckedRunResult):
            row_checks.merge_outcomes(report, window.row_checks)
        for name, value in window.timings.items():
            timings[name] = timings.get(name, 0.0) + value
        peak_history = max(
            peak_history, sum(v.nbytes for v in window.history) + window.times.nbytes
        )
        peak_observations = max(
            peak_observations, sum(v.nbytes for v in vars(window.observations).values())
        )
        observation_count += len(window.observations.times)
        window_count += 1
        if sink is not None:
            before = perf_counter()
            sink(window)
            sink_seconds += perf_counter() - before
        final = window.final
    timings = {f"window_{k}": v for k, v in timings.items()} | {
        "preflight_seconds": preparation_seconds,
        "sink_seconds": sink_seconds,
        "total_run_seconds": perf_counter() - started,
    }
    checked = {} if report is None else {"row_checks": report}
    if final.energy_check is not None:  # The step-doubled energy check's run-level summary.
        checked = checked | {"energy_check": energy.summary(final.energy_check)}
    if plan.grid.spans:  # Declared fine windows, as the clock runs them (provenance).
        checked = checked | {"fine_windows": plan.grid.fine_window_record()}
    if plan.snapped:  # D283: each snapped event, declared and applied.
        checked = checked | {"snapped_events": [list(pair) for pair in plan.snapped]}
    return WindowedResult(
        plan.declared or plan.spec,  # The record keeps the declared definition (D283).
        plan.policy,
        final,
        plan.start_step,
        plan.grid[plan.start_step],
        diagnostics,
        timings,
        {
            "estimated_working_bytes": plan.estimated_working_bytes,
            "peak_host_history_bytes": peak_history,
            "peak_host_observation_bytes": peak_observations,
            "max_observations_per_window": plan.max_observations,
            "windows": window_count,
            "validated_observations": observation_count,
            "executed_steps": final.step_index - plan.start_step,
            "resident_off_nominal_events": len(plan.grid.extras),
        }
        | checked,
    )


def run_windowed(spec, policy=DEFAULT_POLICY, checkpoint=None, *, sink=None):
    """Execute without retaining a whole trace. A sink runs only after window checks."""
    if sink is not None and not callable(sink):
        raise ConfigError("Window sink must be callable")
    blas_threads.require_pinned("run_windowed")  # D190.
    started = perf_counter()
    plan = plan_windows(spec, policy, checkpoint)
    return _consume_windows(
        plan, checkpoint, sink, started=started, preparation_seconds=perf_counter() - started
    )
