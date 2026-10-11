"""Explicit CPU/GPU execution and finite-material, graph and clock checks."""

import time
from functools import lru_cache

import jax
import numpy as np

from cells.assembly.engine import device_for
from cells.assembly.graph import FULL
from cells.assembly.spec import AssemblyError
from cells.assembly_pool.kernel import PoolState, advance
from cells.assembly_pool.reference import bonds_within, connected, rates
from cells.assembly_pool.spec import AVOGADRO, FULL_BONDS, parse_spec


def initial_state(spec):
    n, size = spec.worlds, len(spec.initial_nodes)
    first = np.full((n, 21), -1.0)
    first[:, size] = 0.0
    full = spec.initial_mask == FULL and spec.initial_bonds == FULL_BONDS
    return PoolState(
        np.full(n, spec.initial_mask, np.uint32),
        np.full(n, spec.initial_bonds, np.uint32),
        np.full(n, spec.initial_free_trimers, np.int64),
        np.zeros((n, 21), np.int64),
        np.zeros(n),
        np.zeros(n),
        np.zeros(n, np.uint32),
        np.zeros(n),
        np.full(n, -1, np.int32),
        np.zeros(n, bool),
        np.zeros((n, 4), np.int64),
        np.zeros(n, np.int64),
        np.zeros(n, np.int64),
        np.zeros(n, np.int64),
        np.zeros((n, 21)),
        first,
        np.full(n, 0.0 if full else -1.0),
        np.zeros(n),
        np.zeros(n, np.int32),
    )


@lru_cache(maxsize=4096)
def _graph_valid(mask, bonds, root):
    return (
        0 < mask <= FULL
        and 0 <= bonds <= FULL_BONDS
        and bonds_within(mask, bonds) == bonds
        and connected(mask, bonds, root) == mask
    )


def validate_state(spec, state, *, allow_fault=False):
    if not isinstance(state, PoolState):
        raise AssemblyError("Expected complete finite-bond event state")
    values = PoolState(*(np.asarray(x) for x in state))
    for name, value, expected in zip(state._fields, values, initial_state(spec), strict=True):
        if value.shape != expected.shape or value.dtype != expected.dtype:
            raise AssemblyError(f"Invalid finite-pool shape/dtype: {name}")
        if name != "pending_time_s" and not np.isfinite(value).all():
            raise AssemblyError(f"Nonfinite finite-pool state: {name}")
    if np.any((values.fault < 0) | (values.fault > 2)) or (
        np.any(values.fault) and not allow_fault
    ):
        raise AssemblyError("Finite-pool event/clock fault")
    for mask, bonds in np.unique(np.column_stack((values.occupied, values.bonds)), axis=0):
        if not _graph_valid(int(mask), int(bonds), spec.root_node):
            raise AssemblyError(
                "Invalid bond endpoints or assembly disconnected from retained root"
            )
    sizes = np.bitwise_count(values.occupied).astype(np.int64)
    if np.any(values.free < 0) or np.any(values.fragments < 0) or np.any(values.fragments[:, :2]):
        raise AssemblyError("Invalid finite material inventory")
    # Check element bounds before int64 reductions, including untrusted checkpoints.
    if np.any(values.free > spec.total_trimers) or np.any(values.fragments > spec.total_trimers):
        raise AssemblyError("Material inventory exceeds initial total")
    fragment_mass = values.fragments @ np.arange(21, dtype=np.int64)
    if np.any(values.free + sizes + fragment_mass != spec.total_trimers):
        raise AssemblyError("Finite material conservation failed")
    limit = spec.max_events_per_world
    if (
        np.any(values.reaction_counts < 0)
        or np.any(values.reaction_counts > limit)
        or np.any(values.event_count > limit)
        or np.any(values.reaction_counts.sum(axis=1) != values.event_count)
    ):
        raise AssemblyError("Reaction counts disagree with event ledger")
    for name in ("removed", "single_returns", "dissolved"):
        if np.any(getattr(values, name) < 0) or np.any(getattr(values, name) > 20 * limit):
            raise AssemblyError("Invalid material transfer ledger")
    associated, _, broken, dissolved_events = values.reaction_counts.T
    if (
        np.any(sizes != len(spec.initial_nodes) + associated - values.removed)
        or np.any(values.single_returns > broken)
        or np.any(values.removed > 19 * broken)
        or np.any(values.dissolved < 2 * dissolved_events)
        or np.any(values.dissolved > 20 * dissolved_events)
        or np.any(fragment_mass != values.removed - values.single_returns - values.dissolved)
        or np.any(
            values.free
            != spec.initial_free_trimers - associated + values.single_returns + values.dissolved
        )
    ):
        raise AssemblyError("Material transfer counters disagree with inventories")
    if (
        np.any(values.time_s < 0)
        or np.any(values.time_s > 86400)
        or np.any(values.last_event_time_s < 0)
        or np.any(values.last_event_time_s > values.time_s)
    ):
        raise AssemblyError("Invalid event clock")
    pending = values.pending_valid
    if (
        np.any(np.isnan(values.pending_time_s))
        or np.any(values.pending_time_s < 0)
        or np.any(pending & (values.pending_time_s < values.time_s))
        or np.any((values.pending_event < -1) | (values.pending_event >= 79))
        or np.any(pending & (np.isinf(values.pending_time_s) != (values.pending_event == -1)))
        or np.any(~pending & ((values.pending_time_s != 0) | (values.pending_event != -1)))
    ):
        raise AssemblyError("Invalid pending event/clock")
    for i in np.flatnonzero(pending):
        propensities = rates(
            int(values.occupied[i]),
            int(values.bonds[i]),
            int(values.free[i]),
            values.fragments[i].tolist(),
            spec,
        )
        event = int(values.pending_event[i])
        if (event == -1 and any(propensities)) or (event >= 0 and propensities[event] <= 0):
            raise AssemblyError("Pending event is not a permitted finite-pool reaction")
    tolerance = (
        128
        * np.finfo(float).eps
        * np.maximum(1, values.event_count)
        * np.maximum(1, values.last_event_time_s)
    )
    if (
        np.any(values.dwell_completed_s < 0)
        or np.any(
            np.abs(values.dwell_completed_s.sum(axis=1) - values.last_event_time_s) > tolerance
        )
        or np.any(values.full_dwell_completed_s < 0)
        or np.any(values.full_dwell_completed_s > values.dwell_completed_s[:, 20] + tolerance)
    ):
        raise AssemblyError("Dwell exposure does not account for elapsed event time")
    for first in (values.first_passage_s, values.full_first_s[:, None]):
        if np.any((first < 0) & (first != -1)) or np.any(first > values.last_event_time_s[:, None]):
            raise AssemblyError("Invalid first-passage observations")
    if np.any(values.first_passage_s[:, len(spec.initial_nodes)] != 0):
        raise AssemblyError("Initial size first passage changed")
    is_full = (values.occupied == FULL) & (values.bonds == FULL_BONDS)
    if np.any(is_full & (values.full_first_s < 0)):
        raise AssemblyError("Full cage lacks its first-passage record")
    if spec.initial_mask == FULL and spec.initial_bonds == FULL_BONDS:
        if np.any(values.full_first_s != 0):
            raise AssemblyError("Initial full-cage first passage changed")
    return values


def summary(spec, state):
    values = validate_state(spec, state)
    sizes = np.bitwise_count(values.occupied)
    dwell = values.dwell_completed_s.copy()
    dwell[np.arange(spec.worlds), sizes] += values.time_s - values.last_event_time_s
    full = (values.occupied == FULL) & (values.bonds == FULL_BONDS)
    full_dwell = values.full_dwell_completed_s + np.where(
        full, values.time_s - values.last_event_time_s, 0.0
    )
    return {
        "model": spec.model,
        "worlds": spec.worlds,
        "committed_events": int(values.event_count.astype(np.int64).sum()),
        "reaction_counts": dict(
            zip(
                ("association", "closure", "bond_break", "fragment_dissolution"),
                values.reaction_counts.sum(axis=0).tolist(),
                strict=True,
            )
        ),
        "final_size_histogram": np.bincount(sizes, minlength=21).tolist(),
        "final_bond_histogram": np.bincount(np.bitwise_count(values.bonds), minlength=31).tolist(),
        "final_free_trimers": int(values.free.sum()),
        "final_attached_trimers": int(sizes.sum()),
        "final_fragment_trimers": int((values.fragments @ np.arange(21)).sum()),
        "initial_total_trimers": spec.total_trimers * spec.worlds,
        "material_residual_trimers": 0,
        "ever_full_cages": int((values.full_first_s >= 0).sum()),
        "currently_full_cages": int(full.sum()),
        "full_cage_dwell_total_s": float(full_dwell.sum()),
        "dwell_by_size_total_s": dwell.sum(axis=0).tolist(),
        "experimental_validation": False,
        "scope": "Prescribed graph, finite neutral material, coarse-grained fragment recycling",
    }


def run(spec, *, backend="cpu", device_index=0, state=None, until=None, callback=None):
    spec = parse_spec(spec.to_dict())
    until = spec.end_time_s if until is None else until
    if type(until) not in (int, float) or not np.isfinite(until) or not 0 < until <= 86400:
        raise AssemblyError("Invalid finite-pool run horizon")
    state = initial_state(spec) if state is None else validate_state(spec, state)
    if np.any(state.time_s > until):
        raise AssemblyError("Cannot run backward from a saved observation boundary")
    began = time.monotonic()
    device = device_for(backend, device_index)
    constants = np.array(
        [
            spec.k_on_M_inv_s / (AVOGADRO * spec.pool_volume_L),
            spec.k_close_s_inv,
            spec.k_off_s_inv,
            spec.k_fragment_dissolve_s_inv,
        ],
        dtype=np.float64,
    )
    args = jax.device_put(
        (
            state,
            np.arange(spec.world_id_start, spec.world_id_start + spec.worlds, dtype=np.uint32),
            np.uint32(spec.seed),
            np.uint32(spec.root_node),
            constants,
            np.float64(until),
            np.uint32(spec.max_events_per_world),
        ),
        device,
    )
    start = time.monotonic()
    compiled = advance.lower(
        *args, steps=spec.event_chunk_size, record=spec.recording == "events"
    ).compile()
    compile_s = time.monotonic() - start
    current, rest = args[0], args[1:]
    execute_s, chunks = 0.0, 0
    while True:
        start = time.monotonic()
        current, trace = compiled(current, *rest)
        jax.block_until_ready((current, trace))
        if any(value.device != device for value in current):
            raise AssemblyError("Finite-pool kernel returned arrays on the wrong device")
        execute_s += time.monotonic() - start
        chunks += 1
        host = PoolState(*(np.asarray(x) for x in current))
        if callback:
            callback(chunks, host, trace)
        if np.any(host.fault):
            validate_state(spec, host)
        if time.monotonic() - began > spec.max_wall_seconds:
            raise AssemblyError("Finite-pool wall-time budget exceeded")
        if np.all(host.time_s >= until):
            break
    result = summary(spec, host)
    return host, result | {
        "backend": backend,
        "device": str(device),
        "device_kind": device.device_kind,
        "precision": "float64",
        "chunks": chunks,
        "through_time_s": float(until),
        "compile_seconds": compile_s,
        "execute_seconds": execute_s,
        "total_seconds": time.monotonic() - began,
        "rng": "threefry2x32_fold_in_seed_world_event_open52@1",
    }
