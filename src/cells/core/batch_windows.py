"""Bounded independent-clock rounds on the existing guarded batch kernel."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import jax
import numpy as np

from cells.core.batch import (
    BatchSpec,
    _array_bytes,
    _batch_rollout,
    _checkpoint_map,
    _compiled_batch,
    _stack,
    checkpoint_batch_limits,
)
from cells.core.devices import execution_device
from cells.core.errors import NumericalError
from cells.core.resources import trace_bytes
from cells.core.runner import RunResult, _analyse_segment, integration_steps, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.core.state import Checkpoint, initialise
from cells.core.windows import (
    DEFAULT_POLICY,
    WindowedResult,
    WindowPlan,
    WindowPolicy,
    _observation_tail,
    _plan_windows_metadata,
    _validate_window_plan,
    merge_diagnostics,
)
from cells.models.registry import get_model


@dataclass(frozen=True)
class BatchWindowPlan:
    spec: BatchSpec
    policy: WindowPolicy
    worlds: tuple[WindowPlan, ...]
    estimated_working_bytes: int
    padded_step_bound: int


def plan_batch_windows(spec, policy=DEFAULT_POLICY, checkpoints=None):
    spec, bound = checkpoint_batch_limits(spec)
    if checkpoints is not None:
        _checkpoint_map(spec, checkpoints)
    plans = []
    for world in spec.worlds:
        try:
            plans.append(
                _plan_windows_metadata(
                    world.simulation,
                    policy,
                    None if checkpoints is None else checkpoints[world.world_id],
                )
            )
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}") from exc
    width = min(plans[0].policy.window_steps, max(len(p.grid) - 1 - p.start_step for p in plans))
    # Reserve padding for EVERY world at the shared window width, including
    # worlds with less work. Two adjacent rounds may coexist in a consuming loop.
    estimate = 2 * sum(
        trace_bytes(p.spec, width, p.max_observations + 1) + trace_bytes(p.spec, 0, 0)
        for p in plans
    )
    if estimate > spec.max_working_bytes:
        raise ConfigError("Estimated window aggregate arrays exceed batch max_working_bytes")
    # No control arrays or model-capacity allocation before aggregate refusal.
    for world, plan in zip(spec.worlds, plans, strict=True):
        try:
            _validate_window_plan(
                plan, None if checkpoints is None else checkpoints[world.world_id]
            )
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}") from exc
    return BatchWindowPlan(spec, plans[0].policy, tuple(plans), estimate, bound)


def _initial_checkpoints(plan, checkpoints):
    result = {}
    for world, local in zip(plan.spec.worlds, plan.worlds, strict=True):
        try:
            cp = initialise(local.spec) if checkpoints is None else checkpoints[world.world_id]
            validate_checkpoint(local.spec, cp, local.grid)
            result[world.world_id] = cp
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}") from exc
    return result


@dataclass(frozen=True)
class BatchWindow:
    index: int  # Zero-based execution round, NOT a biological time.
    spec: BatchSpec
    worlds: Mapping[int, RunResult]  # Participating worlds only; all worlds in round zero.
    checkpoints: Mapping[int, Checkpoint]  # Complete cohort, including finished worlds.
    timings: dict
    resources: dict


def _iter_batch_windows(plan, checkpoints):
    started = perf_counter()
    spec = plan.spec
    starts = _initial_checkpoints(plan, checkpoints)
    model = get_model(spec.worlds[0].simulation.model)
    ids = [w.world_id for w in spec.worlds]
    state, parameters, active = jax.device_put(
        (
            _stack([starts[i].state for i in ids]),
            _stack(
                [model.parameters(w.simulation, starts[w.world_id].layout) for w in spec.worlds]
            ),
            _stack([starts[i].layout.active for i in ids]),
        ),
        execution_device(spec.worlds[0].simulation.execution.backend),
    )
    jax.block_until_ready((state, parameters, active))
    preparation_seconds = perf_counter() - started
    grids = [p.grid.windows(p.start_step, plan.policy.window_steps) for p in plan.worlds]
    observation_indices = [
        bisect_left(p.spec.experiment.observation_times, starts[i].time)
        for i, p in zip(ids, plan.worlds, strict=True)
    ]
    tails = [None] * len(ids)
    executables = {}
    domain = getattr(model, "domain_valid", None)
    rhs, stepper = getattr(model, "rhs", None), getattr(model, "checked_step", None)
    round_index = 0
    while True:
        tick = perf_counter()
        next_times = [next(grid, None) for grid in grids]
        if all(t is None for t in next_times):
            return
        times = [
            np.array([starts[i].time]) if t is None else t
            for i, t in zip(ids, next_times, strict=True)
        ]
        counts = np.array([len(t) - 1 for t in times], dtype=np.int64)
        width = int(counts.max())
        steps = np.zeros((len(ids), width), dtype=np.float64)
        controls = []
        for i, (local, t) in enumerate(zip(plan.worlds, times, strict=True)):
            steps[i, : counts[i]] = integration_steps(local.spec, t)
            held = control_values(local.spec, t[:-1])
            controls.append(
                jax.tree.map(
                    lambda v, size=width: np.pad(v, [(0, size - len(v)), *[(0, 0)] * (v.ndim - 1)]),
                    held,
                )
            )
        device_steps, device_controls, device_counts = jax.device_put(
            (steps, _stack(controls), counts),
            execution_device(spec.worlds[0].simulation.execution.backend),
        )
        inputs = (state, device_steps, device_controls, parameters, active, device_counts)
        jax.block_until_ready(inputs)
        prepared = perf_counter()
        compile_seconds = 0.0
        if width:
            if spec.worlds[0].simulation.execution.jit:
                if width not in executables:
                    executables[width] = _compiled_batch.lower(
                        inputs, rhs, domain, stepper
                    ).compile()
                    compile_seconds = perf_counter() - prepared
                execute_started = perf_counter()
                final, history, valid = executables[width](inputs)
            else:
                execute_started = perf_counter()
                with jax.disable_jit():
                    final, history, valid = _batch_rollout(inputs, rhs, domain, stepper)
            jax.block_until_ready((final, history, valid))
            execute_seconds = perf_counter() - execute_started
            failed = np.argwhere(~np.asarray(valid))
            if len(failed):
                world, step = map(int, failed[0])
                raise NumericalError(
                    f"World {ids[world]}: numerical failure on "
                    f"[{times[world][step]}, {times[world][step + 1]}]; windowed batch refused"
                )
        else:
            final = state
            history = jax.tree.map(lambda v: v[:, None, ...][:, :0], state)
            valid = np.empty((len(ids), 0), dtype=bool)
            execute_seconds = 0.0
        transfer_started = perf_counter()
        host = jax.tree.map(np.asarray, history)
        paths = {}
        for i, identity in enumerate(ids):
            if next_times[i] is not None:
                paths[identity] = model.STATE_TYPE(
                    *(
                        np.concatenate((np.asarray(initial)[None], values[i, : counts[i]]), axis=0)
                        for initial, values in zip(starts[identity].state, host, strict=True)
                    )
                )
        analysis_started = perf_counter()
        results, endings = {}, dict(starts)
        for i, (identity, local) in enumerate(zip(ids, plan.worlds, strict=True)):
            if identity not in paths:
                continue
            requested = local.spec.experiment.observation_times
            stop = bisect_right(requested, float(times[i][-1]))
            # Copy the endpoint: a complete host checkpoint must not retain a
            # view of the entire history buffer. Device carry stays on device.
            endpoint = model.STATE_TYPE(*(v[-1].copy() for v in paths[identity]))
            for v in endpoint:
                v.setflags(write=False)
            try:
                path, observations, ending, diagnostics = _analyse_segment(
                    local.spec,
                    starts[identity],
                    times[i],
                    paths[identity],
                    endpoint,
                    starts[identity].layout,
                    requested[observation_indices[i] : stop],
                )
                tails[i] = _observation_tail(model, local.spec, observations, tails[i])
            except (ConfigError, NumericalError) as exc:
                raise type(exc)(f"World {identity}: {exc}; windowed batch refused") from exc
            observation_indices[i] = stop
            endings[identity] = ending
            results[identity] = RunResult(
                local.spec,
                ending,
                starts[identity].step_index,
                times[i],
                path,
                observations,
                {},
                diagnostics,
            )
        finished = perf_counter()
        timings = {
            "static_preparation_seconds": preparation_seconds if round_index == 0 else 0.0,
            "window_preparation_seconds": prepared - tick,
            "compile_seconds": compile_seconds,
            "execute_seconds": execute_seconds,
            "host_transfer_and_assembly_seconds": analysis_started - transfer_started,
            "analysis_seconds": finished - analysis_started,
            "round_seconds": finished - tick,
        }
        resources = {
            "padded_step_slots": len(ids) * width,
            "executed_world_steps": int(counts.sum()),
            "device_input_array_bytes": _array_bytes(inputs),
            "device_output_array_bytes": _array_bytes((final, history, valid)),
            "host_history_array_bytes": sum(
                _array_bytes((r.times, r.history)) for r in results.values()
            ),
            "host_observation_array_bytes": sum(
                _array_bytes(tuple(vars(r.observations).values())) for r in results.values()
            ),
            "prepared_parameter_sets": len(ids) if round_index == 0 else 0,
            "compiled_executables": len(executables),
        }
        state, starts = final, endings
        yield BatchWindow(
            round_index,
            spec,
            MappingProxyType(results),
            MappingProxyType(endings),
            timings,
            resources,
        )
        round_index += 1


def iter_batch_windows(spec, policy=DEFAULT_POLICY, checkpoints=None):
    """Yield only wholly checked rounds. Retaining rounds is the caller's memory choice."""
    return _iter_batch_windows(plan_batch_windows(spec, policy, checkpoints), checkpoints)


@dataclass(frozen=True)
class WindowedBatchResult:
    spec: BatchSpec
    policy: WindowPolicy
    worlds: Mapping[int, WindowedResult]
    timings: dict
    resources: dict

    @property
    def checkpoints(self):
        return {identity: world.final for identity, world in self.worlds.items()}


def _consume_batch_windows(plan, checkpoints, sink, *, started, preflight_seconds):
    diagnostics = {w.world_id: {} for w in plan.spec.worlds}
    observations = {i: 0 for i in diagnostics}
    windows = {i: 0 for i in diagnostics}
    timings, peaks = {}, {}
    executed = padded = rounds = parameters = 0
    sink_seconds = 0.0
    for window in _iter_batch_windows(plan, checkpoints):
        for identity, world in window.worlds.items():
            merge_diagnostics(diagnostics[identity], world.diagnostics)
            observations[identity] += len(world.observations.times)
            windows[identity] += 1
        for name, value in window.timings.items():
            timings[name] = timings.get(name, 0.0) + value
        executed += window.resources["executed_world_steps"]
        padded += window.resources["padded_step_slots"]
        parameters += window.resources["prepared_parameter_sets"]
        for name in (
            "device_input_array_bytes",
            "device_output_array_bytes",
            "host_history_array_bytes",
            "host_observation_array_bytes",
            "compiled_executables",
        ):
            peaks[name] = max(peaks.get(name, 0), window.resources[name])
        if sink is not None:
            before = perf_counter()
            sink(window)
            sink_seconds += perf_counter() - before
        endings = window.checkpoints
        rounds += 1
    worlds = {}
    for world, local in zip(plan.spec.worlds, plan.worlds, strict=True):
        identity = world.world_id
        worlds[identity] = WindowedResult(
            local.spec,
            plan.policy,
            endings[identity],
            local.start_step,
            local.grid[local.start_step],
            diagnostics[identity],
            {},
            {
                "windows": windows[identity],
                "validated_observations": observations[identity],
                "executed_steps": endings[identity].step_index - local.start_step,
            },
        )
    return WindowedBatchResult(
        plan.spec,
        plan.policy,
        MappingProxyType(worlds),
        timings
        | {
            "preflight_seconds": preflight_seconds,
            "sink_seconds": sink_seconds,
            "total_run_seconds": perf_counter() - started,
        },
        {f"peak_{k}": v for k, v in peaks.items()}
        | {
            "estimated_working_bytes": plan.estimated_working_bytes,
            "conservative_padded_step_bound": plan.padded_step_bound,
            "padded_step_slots": padded,
            "executed_world_steps": executed,
            "rounds": rounds,
            "prepared_parameter_sets": parameters,
        },
    )


def run_batch_windowed(spec, policy=DEFAULT_POLICY, checkpoints=None, *, sink=None):
    if sink is not None and not callable(sink):
        raise ConfigError("Batch window sink must be callable")
    started = perf_counter()
    plan = plan_batch_windows(spec, policy, checkpoints)
    return _consume_batch_windows(
        plan, checkpoints, sink, started=started, preflight_seconds=perf_counter() - started
    )
