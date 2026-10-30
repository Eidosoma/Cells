"""Independent worlds on their own clocks, using guarded compiled mapping.

This is a homogeneous array-layout batch, not a shared biological world. No
model RHS knows about the world axis. Scalar RK4 and observer contracts apply.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.devices import execution_device
from cells.core.errors import NumericalError
from cells.core.grid import refinement_times
from cells.core.resources import trace_bytes
from cells.core.runner import (
    RunResult,
    branch_checkpoint,
    integration_steps,
    timeline,
    validate_checkpoint,
)
from cells.core.schedule import control_values, event_index
from cells.core.specs import (
    ConfigError,
    SimulationSpec,
    _fields,
    _integer,
    _number,
    digest,
    parse_spec,
    read_json,
)
from cells.core.state import Checkpoint, initialise
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step, rk4_step


@dataclass(frozen=True)
class WorldSpec:
    world_id: int
    simulation: SimulationSpec


@dataclass(frozen=True)
class BatchSpec:
    worlds: tuple[WorldSpec, ...]
    max_worlds: int
    max_padded_steps: int
    max_working_bytes: int
    mapping: str = "lax_map"

    def to_dict(self):
        return {
            "schema_version": 1,
            "kind": "independent_worlds",
            "worlds": [
                {"world_id": w.world_id, "simulation": w.simulation.to_dict()} for w in self.worlds
            ],
            "execution": {
                "mapping": self.mapping,
                "max_worlds": self.max_worlds,
                "max_padded_steps": self.max_padded_steps,
                "max_working_bytes": self.max_working_bytes,
            },
        }

    @property
    def fingerprint(self):
        return digest(self.to_dict())


def parse_batch(data):
    data = _fields(data, {"schema_version", "kind", "worlds", "execution"}, "batch")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Unsupported batch schema")
    if data["kind"] != "independent_worlds":
        raise ConfigError("Expected independent_worlds, not coupled organs")
    execution = _fields(
        data["execution"],
        {"mapping", "max_worlds", "max_padded_steps", "max_working_bytes"},
        "batch execution",
    )
    if execution["mapping"] != "lax_map":
        raise ConfigError("This version requires mapping='lax_map' to preserve scalar guards")
    maximum = _integer(execution["max_worlds"], "max_worlds", maximum=4096)
    steps = _integer(execution["max_padded_steps"], "max_padded_steps", maximum=2**53 - 1)
    storage = _integer(execution["max_working_bytes"], "max_working_bytes", maximum=2**53 - 1)
    if not isinstance(data["worlds"], list) or not 1 <= len(data["worlds"]) <= maximum:
        raise ConfigError("World list must be nonempty and fit max_worlds")
    worlds = []
    for entry in data["worlds"]:
        entry = _fields(entry, {"world_id", "simulation"}, "world")
        identity = _integer(entry["world_id"], "world ID")
        worlds.append(WorldSpec(identity, parse_spec(entry["simulation"])))
    if len({w.world_id for w in worlds}) != len(worlds):
        raise ConfigError("World IDs must be distinct")
    first = worlds[0].simulation
    for w in worlds[1:]:
        s = w.simulation
        if type(s.model) is not type(first.model):
            raise ConfigError("A batch requires one model family; use separate batches")
        for name in ("capacity", "edge_capacity", "membrane_capacity", "jit", "backend"):
            if getattr(s.execution, name) != getattr(first.execution, name):
                raise ConfigError(f"A batch requires equal {name}; no implicit resizing")
        model = get_model(first.model)
        for name in getattr(model, "BATCH_CAPACITIES", ()):
            if getattr(s.execution, name) != getattr(first.execution, name):
                raise ConfigError(f"A batch requires equal {name}; no implicit resizing")
        if hasattr(model, "batch_signature") and model.batch_signature(
            s.model
        ) != model.batch_signature(first.model):
            raise ConfigError("A batch requires matching model array axes; use separate batches")
    return BatchSpec(tuple(worlds), maximum, steps, storage)


def load_batch(path):
    return parse_batch(read_json(path))


@dataclass(frozen=True)
class BatchPlan:
    spec: BatchSpec
    grids: tuple[np.ndarray, ...]
    estimated_working_bytes: int
    padded_step_bound: int


def plan_batch(spec: BatchSpec) -> BatchPlan:
    spec = parse_batch(spec.to_dict())
    upper = []
    for world in spec.worlds:
        s = world.simulation
        nominal = s.experiment.end_time / s.execution.dt
        if not math.isfinite(nominal) or nominal > s.execution.max_steps:
            raise ConfigError(f"World {world.world_id}: nominal grid exceeds max_steps")
        # Before any timeline/control/capacity allocation. Events include zero,
        # so this intentionally overestimates instead of guessing overlap.
        upper.append(math.ceil(nominal) + len(s.experiment.changes) + len(refinement_times(s)))
    steps = max(upper)
    padded = steps * len(spec.worlds)
    if padded > spec.max_padded_steps:
        raise ConfigError("Conservative padded work exceeds batch max_padded_steps")
    working = 2 * sum(
        trace_bytes(w.simulation, steps) + trace_bytes(w.simulation, 0, 0) for w in spec.worlds
    )
    if working > spec.max_working_bytes:
        raise ConfigError("Estimated aggregate arrays exceed batch max_working_bytes")
    grids = []
    for world in spec.worlds:
        try:
            grids.append(timeline(world.simulation))
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}") from exc
    return BatchPlan(spec, tuple(grids), working, padded)


def _checkpoint_map(spec, checkpoints):
    if not isinstance(checkpoints, Mapping) or any(type(key) is not int for key in checkpoints):
        raise ConfigError("Batch checkpoints must be mapped by integer world ID")
    if set(checkpoints) != {w.world_id for w in spec.worlds}:
        raise ConfigError("Checkpoint worlds must exactly match the batch world IDs")
    if any(type(value) is not Checkpoint for value in checkpoints.values()):
        raise ConfigError("Every world requires a complete Checkpoint")


def checkpoint_batch_limits(spec):
    """Cohort identity/work/state bounds, independent of recording policy."""
    spec = parse_batch(spec.to_dict())
    upper = []
    for world in spec.worlds:
        s = world.simulation
        nominal = s.experiment.end_time / s.execution.dt
        if not math.isfinite(nominal) or nominal > s.execution.max_steps:
            raise ConfigError(f"World {world.world_id}: nominal grid exceeds max_steps")
        upper.append(
            max(1, math.ceil(nominal)) + len(s.experiment.changes) + len(refinement_times(s))
        )
    bound = len(spec.worlds) * max(upper)
    if bound > spec.max_padded_steps:
        raise ConfigError("Conservative padded work exceeds batch max_padded_steps")
    storage = 2 * sum(trace_bytes(w.simulation, 0, 0) for w in spec.worlds)
    if storage > spec.max_working_bytes:
        raise ConfigError("Checkpoint aggregate arrays exceed batch max_working_bytes")
    for world in spec.worlds:
        if trace_bytes(world.simulation, 0, 0) > world.simulation.execution.max_trace_bytes:
            raise ConfigError(f"World {world.world_id}: checkpoint exceeds max_trace_bytes")
    return spec, bound


def branch_batch_checkpoints(original, checkpoints, changed):
    original, _ = checkpoint_batch_limits(original)
    changed, _ = checkpoint_batch_limits(changed)
    _checkpoint_map(original, checkpoints)
    _checkpoint_map(changed, checkpoints)
    if original.to_dict()["execution"] != changed.to_dict()["execution"]:
        raise ConfigError("A batch branch may not change batch execution settings")
    prior = {w.world_id: w.simulation for w in original.worlds}
    result = {}
    for world in changed.worlds:
        try:
            result[world.world_id] = branch_checkpoint(
                prior[world.world_id], checkpoints[world.world_id], world.simulation
            )
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}") from exc
    return result


def _world_rollout(inputs, rhs, domain, checked_step=None):
    state, steps, controls, parameters, active, count = inputs

    def advance(carry, inputs):
        current, previous_ok = carry
        index, dt, control = inputs

        def step(y):
            if checked_step is not None:
                return checked_step(y, dt, control, parameters, active)
            if domain is not None:
                return rk4_checked_step(rhs, domain, y, dt, control, parameters, active)
            updated = rk4_step(rhs, y, dt, control, parameters, active)
            ok = jnp.all(jnp.stack([jnp.all(jnp.isfinite(v)) for v in updated]))
            return updated, ok

        updated, ok = jax.lax.cond(
            (index < count) & previous_ok,
            step,
            lambda y: (y, previous_ok),
            current,
        )
        return (updated, ok), (updated, ok)

    (final, _), (history, valid) = jax.lax.scan(
        advance, (state, jnp.array(True)), (jnp.arange(len(steps)), steps, controls)
    )
    return final, history, valid


def _batch_rollout(inputs, rhs, domain, checked_step=None):
    # Deliberately NOT vmap: batched cond would select both branches and could
    # evaluate invalid logs/divisions in a rejected trial or finished world.
    return jax.lax.map(lambda world: _world_rollout(world, rhs, domain, checked_step), inputs)


_compiled_batch = jax.jit(_batch_rollout, static_argnums=(1, 2, 3))


def _stack(values):
    leaves = [jax.tree.flatten(value) for value in values]
    first, structure = leaves[0]
    if any(
        tree != structure
        or any(np.shape(a) != np.shape(b) for a, b in zip(first, row, strict=True))
        for row, tree in leaves[1:]
    ):
        raise ConfigError("World parameter/state layouts are not homogeneous")
    return jax.tree.map(lambda *items: np.stack(items), *values)


def _array_bytes(tree):
    return sum(int(v.nbytes) for v in jax.tree.leaves(tree))


@dataclass(frozen=True)
class BatchResult:
    spec: BatchSpec
    worlds: Mapping[int, RunResult]
    timings: dict
    resources: dict

    def checkpoint_at(self, times):
        if isinstance(times, Mapping):
            if any(type(key) is not int for key in times) or set(times) != set(self.worlds):
                raise ConfigError("Checkpoint times must name every world exactly once")
            requested = times
        else:
            requested = {identity: times for identity in self.worlds}
        return {
            identity: result.checkpoint_at(_number(requested[identity], "checkpoint time"))
            for identity, result in self.worlds.items()
        }


def run_batch(spec, checkpoints=None, *, timing_repeats=1):
    """Execute independent worlds, refusing the whole batch on any failure.

    timing_repeats > 1 explicitly benchmarks the SAME initial numerical input,
    with one untimed warm-up. Only one biological trajectory is returned.
    """
    started = perf_counter()
    _integer(timing_repeats, "timing_repeats", maximum=10)
    plan = plan_batch(spec)
    spec = plan.spec
    if checkpoints is not None:
        _checkpoint_map(spec, checkpoints)
    model = get_model(spec.worlds[0].simulation.model)
    starts, times, controls, parameters = [], [], [], []
    for world, grid in zip(spec.worlds, plan.grids, strict=True):
        s = world.simulation
        try:
            checkpoint = initialise(s) if checkpoints is None else checkpoints[world.world_id]
            validate_checkpoint(s, checkpoint, grid)
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}") from exc
        starts.append(checkpoint)
        times.append(grid[checkpoint.step_index :])
        controls.append(control_values(s, times[-1][:-1]))
        parameters.append(model.parameters(s, checkpoint.layout))
    counts = np.array([len(t) - 1 for t in times], dtype=np.int64)
    longest = int(counts.max())
    steps = np.zeros((len(times), longest), dtype=np.float64)
    padded_controls = []
    for i, (t, control) in enumerate(zip(times, controls, strict=True)):
        steps[i, : counts[i]] = integration_steps(spec.worlds[i].simulation, t)
        padded_controls.append(
            jax.tree.map(
                lambda v: np.pad(v, [(0, longest - len(v)), *[(0, 0)] * (v.ndim - 1)]), control
            )
        )
    device = execution_device(spec.worlds[0].simulation.execution.backend)
    inputs = jax.device_put(
        (
            _stack([s.state for s in starts]),
            steps,
            _stack(padded_controls),
            _stack(parameters),
            _stack([s.layout.active for s in starts]),
            counts,
        ),
        device,
    )
    jax.block_until_ready(inputs)
    prepared = perf_counter()
    compile_seconds, warmup_seconds = 0.0, 0.0
    samples, compiler_memory = [], None
    domain = getattr(model, "domain_valid", None)
    rhs, stepper = getattr(model, "rhs", None), getattr(model, "checked_step", None)
    if longest:
        if spec.worlds[0].simulation.execution.jit:
            compiled = _compiled_batch.lower(inputs, rhs, domain, stepper).compile()
            compile_seconds = perf_counter() - prepared
            stats = compiled.memory_analysis()
            if stats is not None:
                compiler_memory = {
                    name: int(getattr(stats, name))
                    for name in (
                        "argument_size_in_bytes",
                        "output_size_in_bytes",
                        "temp_size_in_bytes",
                        "alias_size_in_bytes",
                        "generated_code_size_in_bytes",
                    )
                }

            def execute():
                return compiled(inputs)
        else:

            def execute():
                with jax.disable_jit():
                    return _batch_rollout(inputs, rhs, domain, stepper)

        if timing_repeats > 1:
            warm = perf_counter()
            jax.block_until_ready(execute())
            warmup_seconds = perf_counter() - warm
        for _ in range(timing_repeats):
            tick = perf_counter()
            outputs = execute()
            jax.block_until_ready(outputs)
            samples.append(perf_counter() - tick)
        final, history, valid = outputs
        failed = np.argwhere(~np.asarray(valid))
        if len(failed):
            world, step = map(int, failed[0])
            raise NumericalError(
                f"World {spec.worlds[world].world_id}: numerical failure on "
                f"[{times[world][step]}, {times[world][step + 1]}]; batch refused"
            )
    else:
        final = inputs[0]
        history = jax.tree.map(lambda v: v[:, None, ...][:, :0], final)
        valid = np.empty((len(times), 0), dtype=bool)
    transfer_started = perf_counter()
    host_history = jax.tree.map(np.asarray, history)
    assembled = []
    for i, checkpoint in enumerate(starts):
        assembled.append(
            model.STATE_TYPE(
                *(
                    np.concatenate((np.asarray(initial)[None], values[i, : counts[i]]), axis=0)
                    for initial, values in zip(checkpoint.state, host_history, strict=True)
                )
            )
        )
    analyzed = perf_counter()
    results = {}
    for i, (world, checkpoint) in enumerate(zip(spec.worlds, starts, strict=True)):
        s, path = world.simulation, assembled[i]
        try:
            diagnostics = model.check_values(path, s)
            requested = [t for t in s.experiment.observation_times if t >= checkpoint.time]
            observations = model.observe_history(times[i], path, checkpoint.layout, requested, s)
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}; batch refused") from exc
        for values in (times[i], *path):
            values.setflags(write=False)
        ending = Checkpoint(
            jax.tree.map(lambda v, index=i: v[index], final),
            checkpoint.layout,
            float(times[i][-1]),
            len(plan.grids[i]) - 1,
            event_index(s, float(times[i][-1])),
        )
        results[world.world_id] = RunResult(
            s, ending, checkpoint.step_index, times[i], path, observations, {}, diagnostics
        )
    finished = perf_counter()
    return BatchResult(
        spec,
        MappingProxyType(results),
        {
            "preparation_seconds": prepared - started,
            "compile_or_cache_seconds": compile_seconds,
            "untimed_warmup_seconds": warmup_seconds,
            "execute_samples_seconds": samples,
            "median_execute_seconds": float(np.median(samples)) if samples else 0.0,
            "host_transfer_and_assembly_seconds": analyzed - transfer_started,
            "analysis_seconds": finished - analyzed,
            "total_run_seconds": finished - started,
        },
        {
            "estimated_working_bytes": plan.estimated_working_bytes,
            "conservative_padded_step_bound": plan.padded_step_bound,
            "padded_step_slots": len(times) * longest,
            "executed_world_steps": int(counts.sum()),
            "device_input_array_bytes": _array_bytes(inputs),
            "device_output_array_bytes": _array_bytes((final, history, valid)),
            "host_history_array_bytes": _array_bytes(assembled),
            "host_observation_array_bytes": sum(
                _array_bytes(tuple(vars(result.observations).values()))
                for result in results.values()
            ),
            "compiler_memory_analysis": compiler_memory,
        },
    )
