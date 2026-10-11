"""Union of cell-owned event clocks; one stage-consistent spatial solve per segment."""

from functools import partial

import jax
import jax.numpy as jnp

from cells.assembly_cell.kernel import CoupledState
from cells.assembly_pool.kernel import scheduled_event, step
from cells.models import spatial_junction as ionic
from cells.numerics.fixed_step import rk4_checked_step


def availability(pool, levels):
    cyclic = jax.lax.population_count(pool.bonds) >= jax.lax.population_count(pool.occupied)
    return jnp.where(cyclic, levels[:, 1], levels[:, 0])


def one_tick(
    state,
    world_id,
    seeds,
    roots,
    constants,
    limits,
    dt,
    levels,
    owners,
    layout,
    control,
    *,
    model=ionic,
):
    target = (state.tick + jnp.uint32(1)).astype(jnp.float64) * dt

    def active(current):
        return (
            (current.pool.time_s[0] < target)
            & (current.fault == 0)
            & jnp.all(current.pool.fault == 0)
        )

    def segment(current):
        when, _, _ = jax.vmap(scheduled_event, in_axes=(0, None, 0, 0))(
            current.pool, world_id, seeds, constants
        )
        end = jnp.minimum(target, jnp.min(when))
        duration = end - current.pool.time_s[0]
        valid_clock = jnp.isfinite(duration) & (duration > 0)
        duration = jnp.where(valid_clock, duration, 0.0)
        opening = availability(current.pool, levels)
        held = control._replace(channel=control.channel * opening[owners])
        next_ionic, valid = rk4_checked_step(
            model.rhs, model.domain_valid, current.ionic, duration, held, layout, layout.active
        )
        updated, _ = jax.vmap(step, in_axes=(0, None, 0, 0, 0, None, 0))(
            current.pool, world_id, seeds, roots, constants, end, limits
        )
        valid &= valid_clock & jnp.all(updated.fault == 0) & jnp.all(updated.time_s == end)
        return CoupledState(
            updated,
            next_ionic,
            current.tick,
            current.segments + (duration > 0).astype(jnp.uint32),
            current.availability_exposure_s + opening * duration,
            jnp.where(valid, current.fault, jnp.int32(1)),
        )

    result = jax.lax.while_loop(active, segment, state)
    success = (
        (result.fault == 0)
        & jnp.all(result.pool.fault == 0)
        & jnp.all(result.pool.time_s == target)
    )
    return result._replace(tick=result.tick + success.astype(jnp.uint32))


@partial(jax.jit, static_argnames=("model",))
def advance(
    state,
    ids,
    seeds,
    roots,
    constants,
    limits,
    dt,
    levels,
    owners,
    layout,
    control,
    *,
    ticks,
    model=ionic,
):
    # Keep spatial solves and energy reductions scalar in the independent-world
    # axis, matching the guarded ionic batch runner. vmap changes their shapes
    # with the batch width and can change the last bits of the energy ledger.
    # Cell-owned event operations inside one_tick remain vectorized. Mapping
    # complete windows avoids visiting the world axis at every ionic tick.
    def world_window(inputs):
        current, world_id = inputs

        def body(_, current):
            return one_tick(
                current,
                world_id,
                seeds,
                roots,
                constants,
                limits,
                dt,
                levels,
                owners,
                layout,
                control,
                model=model,
            )

        return jax.lax.fori_loop(0, ticks, body, current)

    return jax.lax.map(world_window, (state, ids))
