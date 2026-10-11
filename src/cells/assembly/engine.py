"""Host orchestration, explicit device placement and domain checks."""

import time
from functools import lru_cache

import jax
import numpy as np

from cells.assembly.graph import FULL, component
from cells.assembly.kernel import AssemblyState, advance
from cells.assembly.spec import AssemblyError, parse_spec


def configure_runtime():
    jax.config.update("jax_enable_x64", True)
    jax.config.update("jax_threefry_partitionable", True)


def device_for(backend, index=0):
    if backend not in ("cpu", "gpu") or type(index) is not int or index < 0:
        raise AssemblyError("Choose cpu or gpu and a nonnegative device index")
    configure_runtime()
    try:
        devices = jax.devices(backend)
        device = devices[index]
    except (RuntimeError, IndexError) as exc:
        raise AssemblyError(f"Requested {backend}:{index} unavailable; no CPU fallback") from exc
    return device


def initial_state(spec):
    size = len(spec.initial_nodes)
    first = np.full((spec.worlds, 21), -1.0)
    first[:, size] = 0.0
    return AssemblyState(
        np.full(spec.worlds, spec.initial_mask, np.uint32),
        np.zeros(spec.worlds),
        np.zeros(spec.worlds),
        np.zeros(spec.worlds, np.uint32),
        np.zeros(spec.worlds),
        np.full(spec.worlds, spec.initial_mask, np.uint32),
        np.full(spec.worlds, -1, np.int32),
        np.zeros(spec.worlds, bool),
        np.zeros(spec.worlds, np.int64),
        np.zeros(spec.worlds, np.int64),
        np.zeros((spec.worlds, 21)),
        first,
        np.zeros(spec.worlds, np.int32),
    )


@lru_cache(maxsize=4096)
def _root_component(mask, root):
    return component(mask, root)


@lru_cache(maxsize=4096)
def _event_witness(mask, root, on_rate, off_rate):
    # Keep the independent traversal oracle. Only its immutable answers are
    # reused; each world's saved target, event, clock and inventories are checked.
    from cells.assembly.reference import events

    rates, targets = events(mask, root, on_rate, off_rate)
    rates.setflags(write=False)
    targets.setflags(write=False)
    return rates, targets, not np.any(rates)


def _validate_pending(spec, values):
    pending = values.pending_valid
    if not np.any(pending):
        return
    # Group identical (graph, event) questions without discarding any saved
    # per-world target. Six bits hold the 60 channels plus the no-event sentinel.
    keys = (values.occupied[pending].astype(np.uint64) << 6) | (
        values.pending_event[pending] + 1
    ).astype(np.uint64)
    unique, inverse = np.unique(keys, return_inverse=True)
    allowed = np.empty(unique.size, dtype=bool)
    expected = np.empty(unique.size, dtype=np.uint32)
    for index, key in enumerate(unique):
        mask, event = int(key) >> 6, (int(key) & 63) - 1
        rates, targets, no_event = _event_witness(
            mask, spec.root_node, spec.k_on_M_inv_s * spec.free_trimer_M, spec.k_off_s_inv
        )
        allowed[index] = no_event if event < 0 else rates[event] > 0
        expected[index] = mask if event < 0 else targets[event]
    invalid = ~allowed[inverse] | (values.pending_occupied[pending] != expected[inverse])
    if np.any(invalid & (values.pending_event[pending] < 0)):
        raise AssemblyError("Pending no-event state has a permitted reaction")
    if np.any(invalid):
        raise AssemblyError("Saved pending event is not a permitted graph transition")


def validate_state(spec, state, *, allow_fault=False):
    expected = initial_state(spec)
    values = AssemblyState(*(np.asarray(x) for x in state))
    for name, value, template in zip(state._fields, values, expected, strict=True):
        if value.shape != template.shape or value.dtype != template.dtype:
            raise AssemblyError(f"Invalid checkpoint shape/dtype: {name}")
        if name != "pending_time_s" and not np.isfinite(value).all():
            raise AssemblyError(f"Nonfinite assembly state: {name}")
    if np.any(values.fault) and not allow_fault:
        raise AssemblyError(f"Assembly event/clock fault: {sorted(set(values.fault.tolist()))}")
    sizes = np.bitwise_count(values.occupied)
    if any(_root_component(int(m), spec.root_node) != int(m) for m in np.unique(values.occupied)):
        raise AssemblyError("Assembly disconnected from its retained root")
    if np.any(values.occupied > FULL) or np.any(sizes == 0):
        raise AssemblyError("Occupied sites outside graph")
    if np.any(sizes != len(spec.initial_nodes) + values.added - values.removed):
        raise AssemblyError("Subunit inventory does not equal initial + added - removed")
    if np.any(values.added < 0) or np.any(values.removed < 0):
        raise AssemblyError("Negative material transfer counter")
    if (
        np.any(values.added > values.event_count)
        or np.any(values.removed > 19 * values.event_count.astype(np.int64))
        or np.any(values.event_count > values.added + values.removed)
    ):
        raise AssemblyError("Event and material transfer counters disagree")
    if (
        np.any(values.time_s < 0)
        or np.any(values.last_event_time_s < 0)
        or np.any(values.last_event_time_s > values.time_s)
        or np.any(values.event_count > spec.max_events_per_world)
    ):
        raise AssemblyError("Invalid event clock or event counter")
    pending = values.pending_valid
    if np.any(np.isnan(values.pending_time_s)) or np.any(values.pending_time_s < 0):
        raise AssemblyError("Invalid pending clock")
    if np.any(pending & (values.pending_time_s < values.time_s)):
        raise AssemblyError("Pending event precedes the observed clock")
    if np.any((values.pending_event < -1) | (values.pending_event >= 60)):
        raise AssemblyError("Invalid pending event index")
    if np.any(pending & (np.isinf(values.pending_time_s) != (values.pending_event == -1))):
        raise AssemblyError("Pending event/clock mismatch")
    if np.any(values.dwell_completed_s < 0):
        raise AssemblyError("Negative completed dwell exposure")
    tolerance = (
        128
        * np.finfo(float).eps
        * np.maximum(1, values.event_count)
        * np.maximum(1, values.last_event_time_s)
    )
    if np.any(np.abs(values.dwell_completed_s.sum(axis=1) - values.last_event_time_s) > tolerance):
        raise AssemblyError("Dwell exposure does not account for elapsed event time")
    first = values.first_passage_s
    if np.any((first < 0) & (first != -1)) or np.any(first > values.last_event_time_s[:, None]):
        raise AssemblyError("Invalid first-passage observations")
    if np.any(first[:, len(spec.initial_nodes)] != 0):
        raise AssemblyError("Initial state first passage changed")
    _validate_pending(spec, values)
    return values


def summary(spec, state):
    return _summary(spec, validate_state(spec, state, allow_fault=True))


def _summary(spec, state):
    """Read-only reductions of the state just validated by this module."""
    sizes = np.bitwise_count(state.occupied)
    dwell = state.dwell_completed_s.copy()
    dwell[np.arange(spec.worlds), sizes] += state.time_s - state.last_event_time_s
    passage = state.first_passage_s[:, 20]
    completed = passage >= 0
    return {
        "model": spec.model,
        "worlds": spec.worlds,
        "completed_shells": int(completed.sum()),
        "censored_worlds": int(((~completed) & (state.fault == 0)).sum()),
        "faulted_worlds": int((state.fault != 0).sum()),
        "committed_events": int(state.event_count.astype(np.int64).sum()),
        "final_size_histogram": np.bincount(sizes, minlength=21).tolist(),
        "dwell_by_size_total_s": dwell.sum(axis=0).tolist(),
        "completed_shell_time_mean_s": float(passage[completed].mean())
        if completed.any()
        else None,
        "completion_time_mean_conditions_on_success": True,
        "initial_subunits": spec.worlds * len(spec.initial_nodes),
        "final_subunits": int(sizes.sum()),
        "added_subunits": int(state.added.sum()),
        "removed_subunits": int(state.removed.sum()),
        "bath": "maintained_free_trimer_concentration_with_transfer_ledger",
        "experimental_validation": False,
    }


def run(spec, *, backend="cpu", device_index=0, state=None, until=None, callback=None):
    entry = time.monotonic()
    spec = parse_spec(spec.to_dict())
    until = spec.end_time_s if until is None else until
    if type(until) not in (float, int) or not np.isfinite(until) or not 0 < until <= 86400:
        raise AssemblyError("Invalid run horizon")
    state = initial_state(spec) if state is None else validate_state(spec, state)
    if np.any(state.time_s > until):
        raise AssemblyError("Cannot run backward from a saved observation boundary")
    device = device_for(backend, device_index)
    began = time.monotonic()
    initialization_s = began - entry
    ids = np.arange(spec.world_id_start, spec.world_id_start + spec.worlds, dtype=np.uint32)
    args = jax.device_put(
        (
            state,
            ids,
            np.uint32(spec.seed),
            np.uint32(spec.root_node),
            np.float64(spec.k_on_M_inv_s * spec.free_trimer_M),
            np.float64(spec.k_off_s_inv),
            np.float64(until),
            np.uint32(spec.max_events_per_world),
        ),
        device,
    )
    t0 = time.monotonic()
    device_put_s = t0 - began
    compiled = advance.lower(
        *args, steps=spec.event_chunk_size, record=spec.recording == "events"
    ).compile()
    compile_s = time.monotonic() - t0
    current, rest = args[0], args[1:]
    execute_s, transfer_s, callback_s, chunks = 0.0, 0.0, 0.0, 0
    while True:
        t0 = time.monotonic()
        current, trace = compiled(current, *rest)
        jax.block_until_ready((current, trace))
        if any(value.device != device for value in current):
            raise AssemblyError("Assembly kernel returned arrays on the wrong device")
        execute_s += time.monotonic() - t0
        chunks += 1
        t0 = time.monotonic()
        host = AssemblyState(*(np.asarray(value) for value in current))
        transfer_s += time.monotonic() - t0
        if callback:
            t0 = time.monotonic()
            callback(chunks, host, trace)
            callback_s += time.monotonic() - t0
        if np.any(host.fault):
            validate_state(spec, host)  # Failure evidence can be saved by callback.
        if np.all(host.time_s >= until):
            break
        if time.monotonic() - began > spec.max_wall_seconds:
            raise AssemblyError("Assembly wall-time budget exceeded")
    t0 = time.monotonic()
    host = validate_state(spec, host)
    validation_s = time.monotonic() - t0
    t0 = time.monotonic()
    result = _summary(spec, host)
    summary_s = time.monotonic() - t0
    return host, result | {
        "backend": backend,
        "device": str(device),
        "device_kind": device.device_kind,
        "precision": "float64",
        "compile_seconds": compile_s,
        "execute_seconds": execute_s,
        "initialization_seconds": initialization_s,
        "device_put_seconds": device_put_s,
        "host_transfer_seconds": transfer_s,
        "callback_seconds": callback_s,
        "validation_seconds": validation_s,
        "summary_seconds": summary_s,
        "total_seconds": time.monotonic() - began,
        "chunks": chunks,
        "through_time_s": float(until),
        "rng": "threefry2x32_fold_in_seed_world_event_open52@1",
    }
