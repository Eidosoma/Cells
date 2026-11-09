"""Independent worlds advanced as one vectorized batch, with checks on the device.

The guarded batch kernel (core/batch.py) maps worlds one after another with
lax.map and checks every accepted row on the host. Here one compiled window
advances every world together: the model's checked step is vmapped over a
world axis inside lax.scan, and the model's device checks (for example
surface_pump.device_checks) test each accepted row of each world in the same
window: the domain, every ledger against its bound, and nonnegative,
nondecreasing dissipation. Only per-window summaries leave the device: each
world's maxima of the check diagnostics and its first failing row with the
checks that failed there, plus the window endpoint (the complete restart
checkpoint) and, for windows that contain observation times, the rows at those
times. The host runs the model's ordinary observers and observation-continuity
checks (windows._observation_tail) on those rows only, while the device runs
the next window.

Worlds share array shapes and capacitor topology (the BatchSpec signature);
parameters, controls and clocks may differ per world, and each world keeps its
own clock, as in core/batch_windows.py: slots beyond a world's window, or after
its first failure, are masked. Under vmap a world evaluates every slot (a
batched lax.cond selects rather than branches), so a masked or refused step is
computed and discarded, never accepted. A failing world refuses the batch.

The BatchSpec is the cohort identity shared with core/batch_windows.py and its
snapshots; its mapping field names the guarded scalar mapping that format
requires. This runner is the separate, explicit vectorized execution of it.
"""

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.batch import (
    BatchSpec,
    WorldSpec,
    _array_bytes,
    _checkpoint_map,
    _stack,
    checkpoint_batch_limits,
)
from cells.core.batch_windows import WindowedBatchResult
from cells.core.devices import execution_device
from cells.core.errors import NumericalError
from cells.core.grid import refinement_times
from cells.core.resources import trace_bytes
from cells.core.runner import integration_steps, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, _integer
from cells.core.state import Checkpoint, initialise
from cells.core.windows import (
    DEFAULT_POLICY,
    WindowedResult,
    WindowPolicy,
    _observation_tail,
    _plan_windows_metadata,
    _validate_window_plan,
    merge_diagnostics,
)
from cells.models.registry import get_model

MAPPING_ID = "vmap_device_checks@1"
DEVICE_HOOKS = (
    "checked_step",
    "device_checks",
    "device_check_constants",
    "device_failure_message",
    "DEVICE_CHECKS",
    "DEVICE_DIAGNOSTICS",
)
STEP_REFUSED = "step"  # Failure bit 0: the model's checked step refused the step.
MIN_CONTROL_ROWS = 2  # One held control change per window keeps one executable.


class WorldCheckError(NumericalError):
    """A world failed in a vectorized window; nothing from that window is accepted.

    step_index is the global index of the first rejected row: the end of a
    refused step, or an accepted row that failed a check. checks names the
    failures there, in host order.
    """

    def __init__(self, message, *, world_id, step_index, time_interval, checks):
        super().__init__(message)
        self.world_id = world_id
        self.step_index = step_index
        self.time_interval = time_interval
        self.checks = checks


def require_device_checks(model):
    missing = [name for name in DEVICE_HOOKS if not hasattr(model, name)]
    if missing:
        raise ConfigError(
            "Vectorized worlds require the model's device checks; missing " + ", ".join(missing)
        )


@dataclass(frozen=True)
class VectorWindowPlan:
    spec: BatchSpec
    policy: WindowPolicy
    worlds: tuple  # One core.windows.WindowPlan per world.
    width: int  # Fixed slots per compiled window; shorter windows are masked.
    control_rows: int  # Held control rows per world and window.
    observation_rows: int  # Device rows stored per world and window.
    groups: tuple  # Worlds with identical definitions and starts share a clock.
    estimated_working_bytes: int
    padded_step_bound: int


def _control_rows(local, width):
    """Most held-control segments in any of the world's windows."""
    grid, start = local.grid, local.start_step
    inside = {
        grid.exact_index(c.time)
        for c in local.spec.experiment.changes
        if grid[start] < c.time < grid[len(grid) - 1]
    }
    counts = {}
    for offset in (index - start for index in inside):
        if offset % width:  # A change at a window start governs its first slot.
            counts[offset // width] = counts.get(offset // width, 0) + 1
    return 1 + max(counts.values(), default=0)


def cohort_limits(spec):
    """checkpoint_batch_limits, admitting each distinct world definition once.

    The core admission re-parses every world's definition, which costs seconds
    per world at tissue scale. Replicas (worlds holding one definition object,
    as ensemble tasks build them) are parsed and admitted once; the cohort-wide
    identity, padded-work and storage bounds of checkpoint_batch_limits are then
    checked with every world counted. Returns the parsed cohort (replicas share
    one parsed definition) and its padded-step bound.
    """
    if type(spec) is not BatchSpec:
        raise ConfigError("Expected a BatchSpec")
    position, distinct = {}, []
    for world in spec.worlds:
        if id(world.simulation) not in position:
            position[id(world.simulation)] = len(distinct)
            distinct.append(world)
    reduced, _ = checkpoint_batch_limits(replace(spec, worlds=tuple(distinct)))
    parsed = [w.simulation for w in reduced.worlds]
    worlds = tuple(WorldSpec(w.world_id, parsed[position[id(w.simulation)]]) for w in spec.worlds)
    ids = [_integer(w.world_id, "world ID") for w in worlds]
    if len(set(ids)) != len(ids):
        raise ConfigError("World IDs must be distinct")
    if not 1 <= len(worlds) <= reduced.max_worlds:
        raise ConfigError("World list must be nonempty and fit max_worlds")
    upper, storage = {}, {}
    for s in parsed:
        nominal = s.experiment.end_time / s.execution.dt
        upper[id(s)] = (
            max(1, math.ceil(nominal)) + len(s.experiment.changes) + len(refinement_times(s))
        )
        storage[id(s)] = trace_bytes(s, 0, 0)
    bound = len(worlds) * max(upper.values())
    if bound > reduced.max_padded_steps:
        raise ConfigError("Conservative padded work exceeds batch max_padded_steps")
    if 2 * sum(storage[id(w.simulation)] for w in worlds) > reduced.max_working_bytes:
        raise ConfigError("Checkpoint aggregate arrays exceed batch max_working_bytes")
    return replace(reduced, worlds=worlds), bound


def plan_vector_windows(spec, policy=DEFAULT_POLICY, checkpoints=None):
    """Admission before any device allocation; one executable shape per run.

    Window plans and grid validation run once per distinct definition and start
    time; every supplied checkpoint is validated against its own definition.
    """
    spec, bound = cohort_limits(spec)
    if checkpoints is not None:
        _checkpoint_map(spec, checkpoints)
    model = get_model(spec.worlds[0].simulation.model)
    require_device_checks(model)
    if not spec.worlds[0].simulation.execution.jit:
        raise ConfigError("Vectorized worlds require JIT execution")
    plans, shared, initial = [], {}, {}
    for world in spec.worlds:
        checkpoint = None if checkpoints is None else checkpoints[world.world_id]
        key = (id(world.simulation), None if checkpoint is None else checkpoint.time)
        try:
            if key not in shared:
                local = _plan_windows_metadata(world.simulation, policy, checkpoint)
                _validate_window_plan(local, None)
                shared[key] = local
            local = shared[key]
            if checkpoint is not None:
                if id(world.simulation) not in initial:
                    initial[id(world.simulation)] = initialise(local.spec)
                validate_checkpoint(
                    local.spec, checkpoint, local.grid, initial=initial[id(world.simulation)]
                )
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}") from exc
        plans.append(local)
    remaining = max(len(p.grid) - 1 - p.start_step for p in plans)
    width = max(1, min(plans[0].policy.window_steps, remaining))
    padded = len(plans) * width * max(1, -(-remaining // width))
    if padded > spec.max_padded_steps:
        raise ConfigError("Vectorized padded work exceeds batch max_padded_steps")
    distinct = {id(p): p for p in plans}.values()
    control_rows = max(MIN_CONTROL_ROWS, *(_control_rows(p, width) for p in distinct))
    observation_rows = max(1, *(p.max_observations for p in distinct))
    groups, position = [], {}
    for i, local in enumerate(plans):  # Shared plans are shared definitions and starts.
        if id(local) not in position:
            position[id(local)] = len(groups)
            groups.append([])
        groups[position[id(local)]].append(i)
    # Resident rows per world: start, carry, candidate and endpoint states, the
    # stored observation rows and held controls (trace_bytes rows include the
    # model's margin). Model temporaries such as dense field matrices are
    # measured from the compiled executable and admitted before it runs.
    rows = 4 + observation_rows + control_rows
    estimate = sum(
        rows * trace_bytes(p.spec, 0, 0) * len(g)
        for p, g in zip((plans[g[0]] for g in groups), groups, strict=True)
    )
    if estimate > spec.max_working_bytes:
        raise ConfigError("Estimated vectorized rows exceed batch max_working_bytes")
    return VectorWindowPlan(
        spec,
        plans[0].policy,
        tuple(plans),
        width,
        control_rows,
        observation_rows,
        tuple(tuple(g) for g in groups),
        estimate,
        max(bound, padded),
    )


def _pack(failed, shift):
    """Boolean [..., checks] flags as an int32 bit mask starting at bit ``shift``."""
    bits = jnp.left_shift(jnp.int32(1), jnp.arange(failed.shape[-1], dtype=jnp.int32) + shift)
    return jnp.sum(jnp.where(failed, bits, 0), axis=-1, dtype=jnp.int32)


def _expand(mask, value):
    return mask.reshape(mask.shape + (1,) * (value.ndim - 1))


def _vector_window(
    state, steps, counts, table, index, slots, params, active, constants, *, step, checks, rows
):
    """One window of every world: masked vmapped steps with per-row device checks.

    Local row 0 is the window start, re-checked as each host window checks its
    start row; row j is the state after slot j. ``rows`` is the number of stored
    observation rows per world. Returns the endpoint, the first failing row per
    world (-1 if none) and its failure bits, the diagnostic maxima over the
    accepted rows (row 0 included) and the stored rows.
    """
    stepped, checked = jax.vmap(step), jax.vmap(checks)
    worlds = counts.shape[0]
    failed, values = checked(state, state, params, constants)
    bits = _pack(failed, 1)
    ok = bits == 0
    first = jnp.where(ok, -1, 0).astype(jnp.int32)
    maxima = jnp.where(ok[:, None], values, 0.0)
    stored = jax.tree.map(lambda v: jnp.zeros((worlds, rows, *v.shape[1:]), v.dtype), state)

    def store(buffer, slot, value):
        return buffer.at[slot].set(value, mode="drop")

    def advance(carry, inputs):
        current, ok, first, bits, maxima, stored = carry
        row, dt, held, slot = inputs
        control = jax.tree.map(lambda t: jax.vmap(lambda u, i: u[i])(t, held), table)
        updated, accepted = stepped(current, dt, control, params, active)
        failed, values = checked(current, updated, params, constants)
        flags = jnp.where(accepted, _pack(failed, 1), 1)
        live = (row <= counts) & ok
        failing = live & (flags != 0)
        accept = live & (flags == 0)
        first = jnp.where(failing, row, first)
        bits = jnp.where(failing, flags, bits)
        current = jax.tree.map(
            lambda new, old: jnp.where(_expand(accept, new), new, old), updated, current
        )
        maxima = jnp.where(accept[:, None], jnp.maximum(maxima, values), maxima)
        target = jnp.where(accept, slot, rows)
        stored = jax.tree.map(lambda b, v: jax.vmap(store)(b, target, v), stored, current)
        return (current, ok & ~failing, first, bits, maxima, stored), None

    width = steps.shape[1]
    carry = (state, ok, first, bits, maxima, stored)
    inputs = (jnp.arange(1, width + 1, dtype=jnp.int32), steps.T, index.T, slots.T)
    (final, _, first, bits, maxima, stored), _ = jax.lax.scan(advance, carry, inputs)
    return final, first, bits, maxima, stored


_compiled_vector_window = jax.jit(_vector_window, static_argnames=("step", "checks", "rows"))
# In-process executables by model functions, window shape and placement: the
# tasks of one arm share shapes, so a worker compiles each shape once.
_EXECUTABLES = {}
_EXECUTABLE_LIMIT = 4


def compile_window(model, args, rows):
    """(executable, compile seconds or 0.0 if reused, XLA memory analysis)."""
    leaves, tree = jax.tree.flatten(args)
    key = (
        model.checked_step,
        model.device_checks,
        rows,
        tree,
        tuple((v.shape, v.dtype, v.sharding) for v in leaves),
    )
    if key in _EXECUTABLES:
        compiled, memory = _EXECUTABLES[key]
        return compiled, 0.0, memory
    started = perf_counter()
    compiled = _compiled_vector_window.lower(
        *args, step=model.checked_step, checks=model.device_checks, rows=rows
    ).compile()
    seconds = perf_counter() - started
    stats = compiled.memory_analysis()
    memory = None
    if stats is not None:
        memory = {
            name: int(getattr(stats, name))
            for name in (
                "argument_size_in_bytes",
                "output_size_in_bytes",
                "temp_size_in_bytes",
                "alias_size_in_bytes",
                "generated_code_size_in_bytes",
            )
        }
    while len(_EXECUTABLES) >= _EXECUTABLE_LIMIT:
        del _EXECUTABLES[next(iter(_EXECUTABLES))]
    _EXECUTABLES[key] = compiled, memory
    return compiled, seconds, memory


def device_stack(trees, groups, device):
    """[world, ...] device arrays from one host tree per group of identical worlds.

    Each group's tree is transferred once and gathered per world on the device,
    so replicas never stack host copies; every world still owns its arrays.
    """
    owner = np.empty(sum(len(g) for g in groups), dtype=np.int32)
    for k, group in enumerate(groups):
        owner[list(group)] = k
    stacked = jax.device_put(_stack(trees), device)
    gather = jax.jit(lambda tree, index: jax.tree.map(lambda v: v[index], tree))
    return gather(stacked, jax.device_put(owner, device))


@dataclass(frozen=True)
class VectorWindow:
    index: int  # Zero-based execution round, NOT a biological time.
    spec: BatchSpec
    observations: Mapping[int, object]  # Worlds with observation times in this round.
    diagnostics: Mapping[int, dict]  # Device-check maxima of participating worlds.
    checkpoints: Mapping[int, Checkpoint]  # Complete cohort, including finished worlds.
    timings: dict
    resources: dict


def _initial_checkpoints(plan, checkpoints):
    """Starts: the planned (already validated) checkpoints, or one validated fresh
    start per group of identical worlds, shared by its members."""
    if checkpoints is not None:
        return {w.world_id: checkpoints[w.world_id] for w in plan.spec.worlds}
    result = {}
    for group in plan.groups:
        world, local = plan.spec.worlds[group[0]], plan.worlds[group[0]]
        try:
            shared = initialise(local.spec)
            validate_checkpoint(local.spec, shared, local.grid)
        except (ConfigError, NumericalError) as exc:
            raise type(exc)(f"World {world.world_id}: {exc}") from exc
        for i in group:
            result[plan.spec.worlds[i].world_id] = shared
    return result


def held_controls(spec, times, rows):
    """A window's distinct held control rows (padded to ``rows``) and each slot's row.

    Controls are held between schedule changes (event_index), so evaluating a
    segment once equals evaluating each of its steps. The segment's last step is
    evaluated too and must agree, refusing a schedule that varies within one.
    """
    starts = times[:-1]
    segment = np.fromiter((event_index(spec, t) for t in starts), np.int64, len(starts))
    edges = np.flatnonzero(np.r_[True, segment[1:] != segment[:-1]])
    if len(edges) > rows:
        raise ConfigError("Window holds more control segments than planned")
    lengths = np.diff(np.r_[edges, len(starts)])
    first = control_values(spec, starts[edges])
    last = control_values(spec, starts[edges + lengths - 1])
    for a, b in zip(first, last, strict=True):
        if not np.array_equal(a, b):
            raise ConfigError("Controls vary within a held schedule segment")
    table = type(first)(
        *(np.concatenate((v, np.repeat(v[-1:], rows - len(v), axis=0))) for v in first)
    )
    return table, np.repeat(np.arange(len(edges), dtype=np.int32), lengths)


def _observation_rows(local, times, index, first_round):
    """Requested times in a window, their local rows (0 = start) and the next index."""
    requested = local.spec.experiment.observation_times
    stop = bisect_right(requested, float(times[-1]))
    chosen = tuple(requested[index:stop])
    rows = []
    for time in chosen:
        matches = np.flatnonzero(times == time)
        if not len(matches) or (matches[0] == 0 and not first_round):
            raise ConfigError("Observation time is not an accepted boundary of its window")
        rows.append(int(matches[0]))
    return chosen, rows, stop


def _failure(plan, model, ids, times, first, bits):
    failing = np.flatnonzero(first >= 0)
    i = int(failing[0])
    row, mask = int(first[i]), int(bits[i])
    names = tuple(
        name for bit, name in enumerate((STEP_REFUSED, *model.DEVICE_CHECKS)) if mask & (1 << bit)
    )
    interval = (float(times[i][max(row - 1, 0)]), float(times[i][row]))
    if names[0] == STEP_REFUSED:
        reason = f"numerical failure on [{interval[0]}, {interval[1]}]"
    else:
        messages = "; ".join(model.device_failure_message(n) for n in names)
        reason = f"{messages} at accepted time {interval[1]}"
    others = f" ({len(failing) - 1} more failing worlds)" if len(failing) > 1 else ""
    raise WorldCheckError(
        f"World {ids[i]}: {reason}; vectorized batch refused{others}",
        world_id=ids[i],
        step_index=plan.worlds[i].grid.exact_index(interval[1]),
        time_interval=interval,
        checks=names,
    )


class _Round:
    """Host inputs of one round, built for each group of identical worlds once."""

    def __init__(self, plan, grids, starts, ids, observation_index, first_round):
        tick = perf_counter()
        worlds, width = len(plan.worlds), plan.width
        self.times, self.chosen, self.rows = [None] * worlds, [()] * worlds, [[]] * worlds
        self.stops, self.live = list(observation_index), [False] * worlds
        steps = np.zeros((worlds, width))
        counts = np.zeros(worlds, dtype=np.int32)
        index = np.zeros((worlds, width), dtype=np.int32)
        slots = np.full((worlds, width), plan.observation_rows, dtype=np.int32)
        tables = [None] * worlds
        for group, grid in zip(plan.groups, grids, strict=True):
            lead, local = group[0], plan.worlds[group[0]]
            times = next(grid, None)
            live = times is not None
            if not live:
                times = np.array([starts[ids[lead]].time])
            count = len(times) - 1
            if count:
                table, held = held_controls(local.spec, times, plan.control_rows)
                step = integration_steps(local.spec, times)
            else:
                table, _ = held_controls(local.spec, np.r_[times, times], plan.control_rows)
                held, step = np.zeros(0, dtype=np.int32), np.zeros(0)
            chosen, rows, stop = ((), [], observation_index[lead])
            if live:
                chosen, rows, stop = _observation_rows(
                    local, times, observation_index[lead], first_round
                )
            stored = [r for r in rows if r > 0]
            if len(stored) > plan.observation_rows:
                raise ConfigError("Window stores more observation rows than planned")
            for i in group:
                self.times[i], self.chosen[i], self.rows[i] = times, chosen, rows
                self.stops[i], self.live[i] = stop, live
                counts[i], steps[i, :count], index[i, :count] = count, step, held
                tables[i] = table
                for slot, row in enumerate(stored):
                    slots[i, row - 1] = slot
        self.arrays = (steps, counts, _stack(tables), index, slots)
        self.observing = any(r > 0 for rows in self.rows for r in rows)
        self.seconds = perf_counter() - tick


def resident_inputs(plan, starts, model, device):
    """(state, params, active, constants, host layouts by id) for a cohort's starts.

    Device arrays are [world, ...]; identical host objects (shared fresh starts
    and their layouts) are transferred once. Observers read the host layouts.
    """
    ids = [w.world_id for w in plan.spec.worlds]
    host_layouts = {}
    for identity in ids:
        layout = starts[identity].layout
        if id(layout) not in host_layouts:
            host_layouts[id(layout)] = type(layout)(*(np.asarray(v) for v in layout))

    def resident(trees):
        position, unique, members = {}, [], []
        for i, tree in enumerate(trees):
            if id(tree) not in position:
                position[id(tree)] = len(unique)
                unique.append(tree)
                members.append([])
            members[position[id(tree)]].append(i)
        return device_stack(unique, members, device)

    layouts = [host_layouts[id(starts[i].layout)] for i in ids]
    constants = {g[0]: model.device_check_constants(plan.worlds[g[0]].spec) for g in plan.groups}
    lead = {i: g[0] for g in plan.groups for i in g}
    values = (
        resident([starts[i].state for i in ids]),
        resident(
            [
                model.parameters(local.spec, layout)
                for local, layout in zip(plan.worlds, layouts, strict=True)
            ]
        ),
        resident([layout.active for layout in layouts]),
        resident([constants[lead[i]] for i in range(len(ids))]),
    )
    jax.block_until_ready(values)
    return (*values, host_layouts)


def _iter_vector_windows(plan, checkpoints):
    started = perf_counter()
    spec = plan.spec
    starts = _initial_checkpoints(plan, checkpoints)
    model = get_model(spec.worlds[0].simulation.model)
    ids = [w.world_id for w in spec.worlds]
    device = execution_device(spec.worlds[0].simulation.execution.backend)
    state, params, active, constants, host_layouts = resident_inputs(plan, starts, model, device)
    static_seconds = perf_counter() - started
    grids = [
        plan.worlds[g[0]].grid.windows(plan.worlds[g[0]].start_step, plan.policy.window_steps)
        for g in plan.groups
    ]
    observation_index = [
        bisect_left(p.spec.experiment.observation_times, starts[i].time)
        for i, p in zip(ids, plan.worlds, strict=True)
    ]
    tails = [None] * len(ids)
    executable = None

    def launch(current):
        nonlocal executable
        args = (state, *jax.device_put(current.arrays, device), params, active, constants)
        compile_seconds, memory = 0.0, None
        if executable is None:
            executable, compile_seconds, memory = compile_window(model, args, plan.observation_rows)
            needed = memory and sum(
                memory[k]
                for k in ("argument_size_in_bytes", "output_size_in_bytes", "temp_size_in_bytes")
            )
            if needed and needed > spec.max_working_bytes:
                raise ConfigError(
                    f"Compiled vectorized window needs {needed} bytes, above batch "
                    f"max_working_bytes ({spec.max_working_bytes})"
                )
        return executable(*args), perf_counter(), compile_seconds, memory

    current = _Round(plan, grids, starts, ids, observation_index, True)
    if not any(current.live):
        return
    outputs, launched, compile_seconds, memory = launch(current)
    round_index = 0
    while current is not None:
        final, first, bits, maxima, stored = outputs
        first, bits, maxima = jax.device_get((first, bits, maxima))
        execute_seconds = perf_counter() - launched
        if np.any(first >= 0):
            _failure(plan, model, ids, current.times, first, bits)
        state = final
        following = _Round(plan, grids, starts, ids, current.stops, False)
        if not any(following.live):
            following = None
        else:  # The device runs the next window while the host finishes this one.
            next_outputs, next_launched, _, _ = launch(following)
        transfer_started = perf_counter()
        endpoint = jax.device_get(final)
        observed = jax.device_get(stored) if current.observing else None
        transfer_seconds = perf_counter() - transfer_started
        analysis_started = perf_counter()
        endings, observations, diagnostics = dict(starts), {}, {}
        for i, identity in enumerate(ids):
            if not current.live[i]:
                continue
            local, times, start = plan.worlds[i], current.times[i], starts[identity]
            endings[identity] = Checkpoint(
                model.STATE_TYPE(*(v[i] for v in endpoint)),
                start.layout,
                float(times[-1]),
                start.step_index + len(times) - 1,
                event_index(local.spec, float(times[-1])),
            )
            diagnostics[identity] = dict(
                zip(model.DEVICE_DIAGNOSTICS, map(float, maxima[i]), strict=True)
            )
            if current.chosen[i]:
                slot = {row: k for k, row in enumerate(r for r in current.rows[i] if r > 0)}
                samples = [
                    [np.asarray(v) for v in start.state]
                    if row == 0
                    else [v[i, slot[row]] for v in observed]
                    for row in current.rows[i]
                ]
                history = model.STATE_TYPE(*(np.stack(v) for v in zip(*samples, strict=True)))
                try:
                    found = model.observe_history(
                        np.asarray(current.chosen[i], dtype=np.float64),
                        history,
                        host_layouts[id(start.layout)],
                        list(current.chosen[i]),
                        local.spec,
                    )
                    tails[i] = _observation_tail(model, local.spec, found, tails[i])
                except (ConfigError, NumericalError) as exc:
                    raise type(exc)(f"World {identity}: {exc}; vectorized batch refused") from exc
                observations[identity] = found
        for value in endpoint:
            value.setflags(write=False)
        timings = {
            "static_preparation_seconds": static_seconds if round_index == 0 else 0.0,
            "window_preparation_seconds": current.seconds,
            "compile_seconds": compile_seconds,
            "execute_seconds": execute_seconds,
            "host_transfer_seconds": transfer_seconds,
            "analysis_seconds": perf_counter() - analysis_started,
        }
        resources = {
            "padded_step_slots": len(ids) * plan.width,
            "executed_world_steps": int(current.arrays[1].sum()),
            "summary_transfer_bytes": int(first.nbytes + bits.nbytes + maxima.nbytes),
            "endpoint_transfer_bytes": _array_bytes(endpoint),
            "observation_transfer_bytes": 0 if observed is None else _array_bytes(observed),
            "compiled_memory_analysis": memory,
        }
        starts = endings
        yield VectorWindow(
            round_index,
            spec,
            MappingProxyType(observations),
            MappingProxyType(diagnostics),
            MappingProxyType(endings),
            timings,
            resources,
        )
        round_index += 1
        current, compile_seconds, memory = following, 0.0, None
        if following is not None:
            outputs, launched = next_outputs, next_launched


def iter_vector_windows(spec, policy=DEFAULT_POLICY, checkpoints=None):
    """Yield only wholly checked rounds; preflight runs before the iterator returns."""
    return _iter_vector_windows(plan_vector_windows(spec, policy, checkpoints), checkpoints)


def run_vector_windowed(spec, policy=DEFAULT_POLICY, checkpoints=None, *, sink=None):
    """Vectorized counterpart of batch_windows.run_batch_windowed (same result type)."""
    if sink is not None and not callable(sink):
        raise ConfigError("Vector window sink must be callable")
    started = perf_counter()
    plan = plan_vector_windows(spec, policy, checkpoints)
    preflight = perf_counter() - started
    diagnostics = {w.world_id: {} for w in plan.spec.worlds}
    observations = {i: 0 for i in diagnostics}
    windows = {i: 0 for i in diagnostics}
    timings, peaks = {}, {}
    executed = padded = rounds = 0
    sink_seconds, memory, endings = 0.0, None, None
    for window in _iter_vector_windows(plan, checkpoints):
        for identity, values in window.diagnostics.items():
            merge_diagnostics(diagnostics[identity], values)
            windows[identity] += 1
        for identity, found in window.observations.items():
            observations[identity] += len(found.times)
        for name, value in window.timings.items():
            timings[name] = timings.get(name, 0.0) + value
        executed += window.resources["executed_world_steps"]
        padded += window.resources["padded_step_slots"]
        memory = window.resources["compiled_memory_analysis"] or memory
        for name in ("summary_transfer_bytes", "endpoint_transfer_bytes"):
            peaks[name] = max(peaks.get(name, 0), window.resources[name])
        peaks["observation_transfer_bytes"] = max(
            peaks.get("observation_transfer_bytes", 0),
            window.resources["observation_transfer_bytes"],
        )
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
    device = execution_device(plan.spec.worlds[0].simulation.execution.backend)
    stats = device.memory_stats() if device.platform == "gpu" else None
    return WindowedBatchResult(
        plan.spec,
        plan.policy,
        MappingProxyType(worlds),
        timings
        | {
            "preflight_seconds": preflight,
            "sink_seconds": sink_seconds,
            "total_run_seconds": perf_counter() - started,
        },
        {f"peak_{k}": v for k, v in peaks.items()}
        | {
            "mapping": MAPPING_ID,
            "estimated_working_bytes": plan.estimated_working_bytes,
            "conservative_padded_step_bound": plan.padded_step_bound,
            "window_width": plan.width,
            "control_rows": plan.control_rows,
            "observation_rows": plan.observation_rows,
            "padded_step_slots": padded,
            "executed_world_steps": executed,
            "rounds": rounds,
            "compiled_memory_analysis": memory,
            "device_peak_bytes_in_use": None if stats is None else stats.get("peak_bytes_in_use"),
        },
    )
