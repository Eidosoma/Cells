"""Independent worlds on their own clocks, using guarded compiled mapping.

This is a homogeneous array-layout batch, not a shared biological world. No
model RHS knows about the world axis. Scalar RK4 and observer contracts apply.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import (
    ConfigError,
    SimulationSpec,
    _fields,
    _integer,
    _number,
    digest,
    parse_spec,
    read_json,
)
from cells.execution import blas_threads, phases
from cells.execution.devices import execution_device
from cells.execution.errors import NumericalError
from cells.execution.grid import applied_definition
from cells.execution.resources import fixed_bytes, row_bytes, trace_bytes
from cells.execution.runner import (
    RunResult,
    branch_checkpoint,
    check_steps,
    integration_steps,
    timeline,
    validate_checkpoint,
)
from cells.execution.schedule import control_values, event_index
from cells.execution.state import Checkpoint, initialise
from cells.numerics.fixed_step import rk4_checked_step, rk4_step
from cells.registry.models import get_model


@dataclass(frozen=True)
class WorldSpec:
    world_id: int
    simulation: SimulationSpec


class MemoryRefusal(ConfigError):
    """A cohort's working memory exceeds its declared max_working_bytes: the batch's size, never
    one world's refusal (docs/WINDOW_DEVICE_CHECKS_DESIGN.md §5.4).

    stage is "checkpoints" (the cohort's checkpoint storage), "estimate" (the planned working
    arrays) or "compiled" (a compiled window's argument, output and temporary bytes);
    required_bytes is what the stage needs and limit_bytes the declared limit. The messages are
    those of the plain ConfigError raised before, so callers that catch ConfigError or match
    "max_working_bytes" see no change; only the class name is new.
    """

    def __init__(self, message, *, required_bytes=None, limit_bytes=None, stage=None):
        super().__init__(message)  # The defaults keep type(exc)(message) re-raises working.
        self.required_bytes, self.limit_bytes, self.stage = required_bytes, limit_bytes, stage


@dataclass(frozen=True)
class WorldRefusal:
    """One world's refusal in a cohort, carried as `exc.refusal` by the exception that reports it
    (docs/WINDOW_DEVICE_CHECKS_DESIGN.md §5.3). The exception's class and message are unchanged.

    stage: "admission" (the cohort's planning of this world), "start" (its start checkpoint),
    "step" (a refused step), "check" (a failed device row check) or "observation" (its host
    observers or observation-continuity check). error: the class name of the exception raised
    for it when the batch is refused; message: its reason, "World N: ...", without any
    batch-outcome suffix. checkpoint: its last accepted checkpoint, at window granularity (its
    checkpoint at the start of the refusing window), where a run had started.
    """

    world_id: int
    stage: str
    error: str
    message: str
    step_index: int | None = None  # The first rejected row (step and check refusals).
    time_interval: tuple | None = None
    checks: tuple = ()
    checkpoint: Checkpoint | None = field(default=None, compare=False)  # Arrays: no ==.


def _refusing(exc, refusal):
    """exc, carrying its world's refusal record as exc.refusal."""
    exc.refusal = refusal
    return exc


def _world_error(error, world_id, stage, message):
    """error(message) for one world's refusal, with its record."""
    return _refusing(error(message), WorldRefusal(world_id, stage, error.__name__, message))


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
        if field_pattern_signature(s) != field_pattern_signature(first):
            raise ConfigError(
                f"A batch under {s.execution.field_solver} requires one face topology: its "
                "bound sparsity patterns hold the faces; use separate batches"
            )
    return BatchSpec(tuple(worlds), maximum, steps, storage)


def field_pattern_signature(spec):
    """The face topology ((sender, receiver), ...) of a world whose declared field solver binds
    static sparsity patterns (surface_field.SPARSE_SOLVER_ID, FR-17 stage 1, whose patterns hold
    the faces, so its arrays' shapes follow them); () for every other world, whose batches are
    admitted as before (the batch signature, BATCH_CAPACITIES and the field solver's equality)."""
    from cells.numerics.surface_field import SPARSE_SOLVER_ID

    if getattr(spec.execution, "field_solver", None) != SPARSE_SOLVER_ID:
        return ()
    return tuple((f.sender, f.receiver) for f in spec.model.faces)


def load_batch(path):
    return parse_batch(read_json(path))


@dataclass(frozen=True)
class BatchPlan:
    spec: BatchSpec
    grids: tuple[np.ndarray, ...]
    estimated_working_bytes: int
    padded_step_bound: int
    # D283: the batch as it runs, each world its applied copy (applied_definition; spec itself
    # where no clock snaps), and each world's snaps. The results keep the declared worlds.
    applied: BatchSpec | None = None
    snapped: object = field(default_factory=dict)


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
        upper.append(math.ceil(nominal) + len(s.experiment.changes))
    steps = max(upper)
    padded = steps * len(spec.worlds)
    if padded > spec.max_padded_steps:
        raise ConfigError("Conservative padded work exceeds batch max_padded_steps")
    # Each world's layout once (fixed_bytes, FR-43), its rows in both coexisting copies.
    working = sum(
        fixed_bytes(w.simulation)
        + 2 * (row_bytes(w.simulation, steps) + row_bytes(w.simulation, 0, 0))
        for w in spec.worlds
    )
    if working > spec.max_working_bytes:
        raise MemoryRefusal(
            "Estimated aggregate arrays exceed batch max_working_bytes",
            required_bytes=working,
            limit_bytes=spec.max_working_bytes,
            stage="estimate",
        )
    grids, applied, snapped = [], [], {}
    for world in spec.worlds:
        try:
            simulation, pairs = applied_definition(world.simulation)  # D283: as run does.
            grids.append(timeline(simulation))
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}") from exc
        applied.append(WorldSpec(world.world_id, simulation))
        snapped[world.world_id] = pairs
    runs = replace(spec, worlds=tuple(applied)) if any(snapped.values()) else spec
    return BatchPlan(spec, tuple(grids), working, padded, runs, MappingProxyType(snapped))


def _checkpoint_map(spec, checkpoints):
    if not isinstance(checkpoints, Mapping) or any(type(key) is not int for key in checkpoints):
        raise ConfigError("Batch checkpoints must be mapped by integer world ID")
    if set(checkpoints) != {w.world_id for w in spec.worlds}:
        raise ConfigError("Checkpoint worlds must exactly match the batch world IDs")
    if any(type(value) is not Checkpoint for value in checkpoints.values()):
        raise ConfigError("Every world requires a complete Checkpoint")


def checkpoint_batch_limits(spec):
    """Cohort identity/work/state bounds, independent of recording policy.

    A refusal of one world carries its WorldRefusal (stage "admission") as exc.refusal; the
    cohort's checkpoint storage above max_working_bytes is a MemoryRefusal.
    """
    spec = parse_batch(spec.to_dict())
    upper = []
    for world in spec.worlds:
        s = world.simulation
        nominal = s.experiment.end_time / s.execution.dt
        if not math.isfinite(nominal) or nominal > s.execution.max_steps:
            raise _world_error(
                ConfigError,
                world.world_id,
                "admission",
                f"World {world.world_id}: nominal grid exceeds max_steps",
            )
        upper.append(max(1, math.ceil(nominal)) + len(s.experiment.changes))
    bound = len(spec.worlds) * max(upper)
    if bound > spec.max_padded_steps:
        raise ConfigError("Conservative padded work exceeds batch max_padded_steps")
    storage = sum(
        fixed_bytes(w.simulation) + 2 * row_bytes(w.simulation, 0, 0) for w in spec.worlds
    )
    if storage > spec.max_working_bytes:
        raise MemoryRefusal(
            "Checkpoint aggregate arrays exceed batch max_working_bytes",
            required_bytes=storage,
            limit_bytes=spec.max_working_bytes,
            stage="checkpoints",
        )
    for world in spec.worlds:
        if trace_bytes(world.simulation, 0, 0) > world.simulation.execution.max_trace_bytes:
            raise _world_error(
                ConfigError,
                world.world_id,
                "admission",
                f"World {world.world_id}: checkpoint exceeds max_trace_bytes",
            )
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
    with one untimed warm-up. Only one biological trajectory is returned. Its phases
    write start, completion and failure records (core.phases.Recorder).
    """
    blas_threads.require_pinned("run_batch")  # D190.
    with phases.Recorder() as record:
        return _run_batch(spec, checkpoints, timing_repeats, record)


def _run_batch(spec, checkpoints, timing_repeats, record):
    started = perf_counter()
    record.start("preparation")
    _integer(timing_repeats, "timing_repeats", maximum=10)
    plan = plan_batch(spec)
    declared, spec = plan.spec, plan.applied or plan.spec  # D283: runs applied, records declared.
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
    record.end("preparation", worlds=len(spec.worlds), seconds=prepared - started)
    compile_seconds, warmup_seconds = 0.0, 0.0
    samples, compiler_memory = [], None
    domain = getattr(model, "domain_valid", None)
    rhs, stepper = getattr(model, "rhs", None), getattr(model, "checked_step", None)
    if longest:
        if spec.worlds[0].simulation.execution.jit:
            record.start("compile")
            compiled = _compiled_batch.lower(inputs, rhs, domain, stepper).compile()
            compile_seconds = perf_counter() - prepared
            record.end("compile", seconds=compile_seconds)
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

        record.start("execute", worlds=len(spec.worlds))
        if timing_repeats > 1:
            warm = perf_counter()
            jax.block_until_ready(execute())
            warmup_seconds = perf_counter() - warm
        for _ in range(timing_repeats):
            tick = perf_counter()
            outputs = execute()
            jax.block_until_ready(outputs)
            samples.append(perf_counter() - tick)
        record.end("execute", worlds=len(spec.worlds), seconds=samples[-1])
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
            rows = len(jax.tree.leaves(path)[0])
            diagnostics = model.check_values(
                path, s, **check_steps(model, checkpoint.step_index, rows)
            )
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
            declared.worlds[i].simulation,  # The declared world (D283); s is its applied copy.
            ending,
            checkpoint.step_index,
            times[i],
            path,
            observations,
            {},
            diagnostics,
            snapped_events=plan.snapped[world.world_id],
        )
    finished = perf_counter()
    return BatchResult(
        declared,
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
