"""Batched finite-pool Gillespie dynamics with explicit, breakable bonds."""

from functools import partial
from typing import NamedTuple

import jax
import jax.numpy as jnp

from cells.assembly.graph import EDGES, FULL
from cells.assembly.kernel import random_pair
from cells.assembly_pool.spec import FULL_BONDS


class PoolState(NamedTuple):
    occupied: jax.Array
    bonds: jax.Array
    free: jax.Array
    fragments: jax.Array  # Counts by size; bins zero and one are always empty.
    time_s: jax.Array
    last_event_time_s: jax.Array
    event_count: jax.Array
    pending_time_s: jax.Array
    pending_event: jax.Array
    pending_valid: jax.Array
    reaction_counts: jax.Array  # Association, closure, break, fragment dissolution.
    removed: jax.Array
    single_returns: jax.Array
    dissolved: jax.Array  # Trimer units, not fragment count.
    dwell_completed_s: jax.Array
    first_passage_s: jax.Array
    full_first_s: jax.Array
    full_dwell_completed_s: jax.Array
    fault: jax.Array


def edge_bits():
    ends = jnp.asarray(EDGES, dtype=jnp.uint32)
    return (
        jnp.uint32(1) << ends[:, 0],
        jnp.uint32(1) << ends[:, 1],
        jnp.uint32(1) << jnp.arange(30, dtype=jnp.uint32),
    )


def event_options(mask, bonds, free, fragments, constants):
    a, b, edge = edge_bits()
    has_a, has_b = (mask & a) != 0, (mask & b) != 0
    association = has_a ^ has_b
    closure = has_a & has_b & ((bonds & edge) == 0)
    present = (bonds & edge) != 0
    on, close, off, dissolve = constants
    on = on * free
    first = (
        jnp.cumsum(association, dtype=jnp.int64) * on + jnp.cumsum(closure, dtype=jnp.int64) * close
    )
    second = first[-1] + jnp.cumsum(present, dtype=jnp.int64) * off
    third = second[-1] + jnp.cumsum(fragments[2:], dtype=jnp.int64) * dissolve
    return jnp.concatenate((first, second, third))


def transition(mask, bonds, free, fragments, event, root):
    """Apply one permitted channel; connectivity is needed only for the chosen cut."""
    a, b, edges = edge_bits()
    index = jnp.clip(event % 30, 0, 29)
    association = (event < 30) & (((mask & a[index]) != 0) ^ ((mask & b[index]) != 0))
    closure = (event < 30) & ~association
    breaking = (event >= 30) & (event < 60)
    dissolving = event >= 60
    added_mask = mask | a[index] | b[index]
    cut = bonds & ~edges[index]

    def flood(_, reached):
        connected_a = ((cut & edges) != 0) & ((reached & a) != 0)
        connected_b = ((cut & edges) != 0) & ((reached & b) != 0)
        extra = jnp.where(connected_a, b, jnp.uint32(0)) | jnp.where(connected_b, a, jnp.uint32(0))
        return reached | (jnp.bitwise_or.reduce(extra) & mask)

    kept = jax.lax.fori_loop(0, 19, flood, jnp.uint32(1) << root)
    kept_bonds = jnp.bitwise_or.reduce(
        jnp.where(((kept & a) != 0) & ((kept & b) != 0), cut & edges, jnp.uint32(0))
    )
    removed = jnp.where(breaking, jax.lax.population_count(mask ^ kept), 0).astype(jnp.int64)
    single_return = (removed == 1).astype(jnp.int64)
    size = jnp.clip(event - 58, 2, 20)
    dissolved = jnp.where(dissolving, size, 0).astype(jnp.int64)
    fragments = fragments.at[removed.astype(jnp.int32)].add((removed > 1).astype(jnp.int64))
    fragments = fragments.at[size].add(-dissolving.astype(jnp.int64))
    result_mask = jnp.where(association, added_mask, jnp.where(breaking, kept, mask))
    result_bonds = jnp.where(
        association | closure, bonds | edges[index], jnp.where(breaking, kept_bonds, bonds)
    )
    result_free = free - association.astype(jnp.int64) + single_return + dissolved
    kind = jnp.where(association, 0, jnp.where(closure, 1, jnp.where(breaking, 2, 3)))
    return (
        result_mask,
        result_bonds,
        result_free,
        fragments,
        kind,
        removed,
        single_return,
        dissolved,
    )


def scheduled_event(state, world_id, seed, constants):
    """Read the pending event without committing it or advancing an observation clock."""
    cumulative = event_options(state.occupied, state.bonds, state.free, state.fragments, constants)
    total = cumulative[-1]
    uniforms = random_pair(seed, world_id, state.event_count)
    wait = -jnp.log(uniforms[0]) / jnp.where(total > 0, total, 1.0)
    proposed_time = jnp.where(total > 0, state.last_event_time_s + wait, jnp.inf)
    threshold = jnp.minimum(uniforms[1] * total, jnp.nextafter(total, 0.0))
    proposed_event = jnp.where(total > 0, jnp.argmax(cumulative > threshold), -1).astype(jnp.int32)
    when = jnp.where(state.pending_valid, state.pending_time_s, proposed_time)
    event = jnp.where(state.pending_valid, state.pending_event, proposed_event)
    return when, event, total


def step(state, world_id, seed, root, constants, until, event_limit):
    active = (state.time_s < until) & (state.fault == 0)
    when, event, total = scheduled_event(state, world_id, seed, constants)
    bad_clock = (
        active
        & ~state.pending_valid
        & (total > 0)
        & (~jnp.isfinite(when) | (when <= state.last_event_time_s))
    )
    due = active & (when <= until) & (event >= 0)
    over_budget = due & (state.event_count >= event_limit)
    fault = jnp.where(bad_clock, 1, jnp.where(over_budget, 2, state.fault)).astype(jnp.int32)
    commit = due & (fault == 0)
    proposed = transition(
        state.occupied, state.bonds, state.free, state.fragments, jnp.maximum(event, 0), root
    )
    mask, bonds, free, fragments = (
        jnp.where(commit, new, old) for new, old in zip(proposed[:4], state[:4], strict=True)
    )
    kind, removed, single_return, dissolved = proposed[4:]
    old_size = jax.lax.population_count(state.occupied).astype(jnp.int32)
    size = jax.lax.population_count(mask).astype(jnp.int32)
    duration = jnp.where(commit, when - state.last_event_time_s, 0.0)
    dwell = state.dwell_completed_s.at[old_size].add(duration)
    first = state.first_passage_s.at[size].set(
        jnp.where(commit & (state.first_passage_s[size] < 0), when, state.first_passage_s[size])
    )
    was_full = (state.occupied == FULL) & (state.bonds == FULL_BONDS)
    is_full = (mask == FULL) & (bonds == FULL_BONDS)
    pending = (state.pending_valid | active) & ~commit
    result = PoolState(
        mask,
        bonds,
        free,
        fragments,
        jnp.where(active & (fault == 0), jnp.where(commit, when, until), state.time_s),
        jnp.where(commit, when, state.last_event_time_s),
        state.event_count + commit.astype(jnp.uint32),
        jnp.where(pending, when, 0.0),
        jnp.where(pending, event, jnp.int32(-1)),
        pending,
        state.reaction_counts.at[kind].add(commit.astype(jnp.int64)),
        state.removed + jnp.where(commit, removed, 0),
        state.single_returns + jnp.where(commit, single_return, 0),
        state.dissolved + jnp.where(commit, dissolved, 0),
        dwell,
        first,
        jnp.where(commit & is_full & (state.full_first_s < 0), when, state.full_first_s),
        state.full_dwell_completed_s + jnp.where(was_full, duration, 0.0),
        fault,
    )
    trace = (jnp.where(commit, when, 0.0), mask, bonds, free, jnp.where(commit, event, -1))
    return result, trace


@partial(jax.jit, static_argnames=("steps", "record"))
def advance(
    state, world_ids, seed, root, constants, until, event_limit, *, steps=128, record=False
):
    def body(current, _):
        updated, trace = jax.vmap(step, in_axes=(0, 0, None, None, None, None, None))(
            current, world_ids, seed, root, constants, until, event_limit
        )
        return updated, trace if record else None

    return jax.lax.scan(body, state, None, length=steps)
