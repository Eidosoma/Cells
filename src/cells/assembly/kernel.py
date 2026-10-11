"""Pure JAX Gillespie kernels on a fixed 20-site graph, batched over worlds."""

from functools import partial
from typing import NamedTuple

import jax
import jax.numpy as jnp

from cells.assembly.graph import EDGES, FULL, NEIGHBOR_MASKS


class AssemblyState(NamedTuple):
    occupied: jax.Array
    time_s: jax.Array
    last_event_time_s: jax.Array
    event_count: jax.Array
    pending_time_s: jax.Array
    pending_occupied: jax.Array
    pending_event: jax.Array
    pending_valid: jax.Array
    added: jax.Array
    removed: jax.Array
    dwell_completed_s: jax.Array  # Completed sojourns; current tail is derived.
    first_passage_s: jax.Array  # By occupied-site count; -1 means not reached.
    fault: jax.Array  # 0 valid, 1 non-advancing clock, 2 event budget.


def spread(reached):
    """Neighbor union on G(10,2) using two ten-bit circular shifts."""
    outer, inner = reached & jnp.uint32(1023), reached >> jnp.uint32(10)

    def rotate(word, n):
        return ((word << jnp.uint32(n)) | (word >> jnp.uint32(10 - n))) & jnp.uint32(1023)

    return (rotate(outer, 1) | rotate(outer, 9) | inner) | (
        (rotate(inner, 2) | rotate(inner, 8) | outer) << jnp.uint32(10)
    )


def event_options(occupied, root, on_rate, off_rate):
    """30 association channels, then 30 bridge-removal channels.

    One association opportunity per occupied–empty edge. An added node forms
    every permitted contact to present neighbors. Repeated targets represent
    distinct encounter channels. A bridge event loses the entire distal
    component. No contact in a cycle can be removed by this model's rule.
    """
    ends = jnp.asarray(EDGES, dtype=jnp.uint32)
    a_bit, b_bit = jnp.uint32(1) << ends[:, 0], jnp.uint32(1) << ends[:, 1]
    has_a, has_b = (occupied & a_bit) != 0, (occupied & b_bit) != 0
    addition = has_a ^ has_b
    add_targets = occupied | jnp.where(has_a, b_bit, a_bit)
    neighbor_masks = jnp.asarray(NEIGHBOR_MASKS, dtype=jnp.uint32)
    neighbors_a = neighbor_masks[ends[:, 0]] & ~b_bit
    neighbors_b = neighbor_masks[ends[:, 1]] & ~a_bit
    root_bit = jnp.uint32(1) << root.astype(jnp.uint32)
    initial = jnp.full((30,), root_bit, dtype=jnp.uint32)

    def flood(_, reached):
        # Remove the cut edge's contribution, retaining any alternate route.
        expanded = spread(reached) & ~(a_bit | b_bit)
        expanded |= jnp.where((reached & neighbors_a) != 0, a_bit, jnp.uint32(0))
        expanded |= jnp.where((reached & neighbors_b) != 0, b_bit, jnp.uint32(0))
        return reached | (expanded & occupied)

    retained = jax.lax.fori_loop(0, 19, flood, initial)
    removal = has_a & has_b & (retained != occupied)
    addition &= occupied != FULL
    removal &= occupied != FULL
    rates = jnp.concatenate((addition * on_rate, removal * off_rate))
    targets = jnp.concatenate((add_targets, retained))
    # Integer prefix counts avoid a device-dependent floating reduction tree.
    cumulative = jnp.concatenate(
        (
            jnp.cumsum(addition, dtype=jnp.int32) * on_rate,
            jnp.sum(addition, dtype=jnp.int32) * on_rate
            + jnp.cumsum(removal, dtype=jnp.int32) * off_rate,
        )
    )
    return rates, targets, cumulative


def random_pair(seed, world_id, event_count):
    """Threefry stream identified by (seed, uint32 world ID, event count).

    Midpoints of 2**52 equal bins give open-interval float64 uniforms, avoiding
    log(0) and zero waiting times without truncating a physical distribution.
    """
    key = jax.random.key(seed, impl="threefry2x32")
    key = jax.random.fold_in(key, world_id)
    key = jax.random.fold_in(key, event_count)
    bits = jax.random.bits(key, shape=(2,), dtype=jnp.uint64)
    mantissa = bits & jnp.uint64((1 << 52) - 1)
    return (mantissa.astype(jnp.float64) + 0.5) * (2.0**-52)


def step(state, world_id, seed, root, on_rate, off_rate, until, event_limit):
    active = (state.time_s < until) & (state.fault == 0)
    _, targets, cumulative = event_options(state.occupied, root, on_rate, off_rate)
    total = cumulative[-1]
    uniforms = random_pair(seed, world_id, state.event_count)
    wait = -jnp.log(uniforms[0]) / jnp.where(total > 0, total, 1.0)
    proposed_time = jnp.where(total > 0, state.last_event_time_s + wait, jnp.inf)
    threshold = jnp.minimum(uniforms[1] * total, jnp.nextafter(total, 0.0))
    proposed_event = jnp.argmax(cumulative > threshold).astype(jnp.int32)
    proposed_mask = targets[proposed_event]
    proposed_event = jnp.where(total > 0, proposed_event, jnp.int32(-1))
    proposed_mask = jnp.where(total > 0, proposed_mask, state.occupied)
    when = jnp.where(state.pending_valid, state.pending_time_s, proposed_time)
    target = jnp.where(state.pending_valid, state.pending_occupied, proposed_mask)
    event = jnp.where(state.pending_valid, state.pending_event, proposed_event)
    bad_clock = (
        active
        & ~state.pending_valid
        & (total > 0)
        & (~jnp.isfinite(when) | (when <= state.last_event_time_s))
    )
    event_due = active & (when <= until) & (event >= 0)
    over_budget = event_due & (state.event_count >= event_limit)
    fault = jnp.where(bad_clock, 1, jnp.where(over_budget, 2, state.fault)).astype(jnp.int32)
    commit = event_due & (fault == 0)
    valid_active = active & (fault == 0)
    new_time = jnp.where(valid_active, jnp.where(commit, when, until), state.time_s)
    old_size = jax.lax.population_count(state.occupied).astype(jnp.int32)
    new_mask = jnp.where(commit, target, state.occupied)
    new_size = jax.lax.population_count(new_mask).astype(jnp.int32)
    delta = new_size - old_size
    # Only completed sojourns enter the accumulator. Observation cuts do not
    # split its floating additions, so subsequent event ledgers replay exactly.
    duration = jnp.where(commit, when - state.last_event_time_s, 0.0)
    dwell = state.dwell_completed_s.at[old_size].add(duration)
    first = state.first_passage_s.at[new_size].set(
        jnp.where(
            commit & (state.first_passage_s[new_size] < 0), when, state.first_passage_s[new_size]
        )
    )
    pending = (state.pending_valid | active) & ~commit
    result = AssemblyState(
        new_mask,
        new_time,
        jnp.where(commit, when, state.last_event_time_s),
        state.event_count + commit.astype(jnp.uint32),
        jnp.where(pending, when, 0.0),
        jnp.where(pending, target, new_mask),
        jnp.where(pending, event, jnp.int32(-1)),
        pending,
        state.added + jnp.maximum(delta, 0).astype(jnp.int64),
        state.removed + jnp.maximum(-delta, 0).astype(jnp.int64),
        dwell,
        first,
        fault,
    )
    trace = (jnp.where(commit, when, 0.0), new_mask, jnp.where(commit, event, -1))
    return result, trace


@partial(jax.jit, static_argnames=("steps", "record"))
def advance(
    state, world_ids, seed, root, on_rate, off_rate, until, event_limit, *, steps=128, record=False
):
    def body(current, _):
        updated, trace = jax.vmap(step, in_axes=(0, 0, None, None, None, None, None, None))(
            current, world_ids, seed, root, on_rate, off_rate, until, event_limit
        )
        return updated, trace if record else None

    return jax.lax.scan(body, state, None, length=steps)
