"""Event-split ionic RK4 on a fixed global grid, with all world state on device."""

from functools import partial
from typing import NamedTuple

import jax
import jax.numpy as jnp

from cells.assembly_pool.kernel import step as pool_step
from cells.models import kinetic_finite_extracellular as ionic
from cells.numerics.fixed_step import rk4_checked_step


class CoupledState(NamedTuple):
    pool: object
    ionic: object
    tick: object
    segments: object
    availability_exposure_s: object
    fault: object


def availability(pool, levels):
    # Root connectivity is a state invariant: E - V + 1 is the cycle rank.
    cyclic = jax.lax.population_count(pool.bonds) >= jax.lax.population_count(pool.occupied)
    return jnp.where(cyclic, levels[1], levels[0])


def one_tick(state, world_id, seed, root, constants, event_limit, dt, levels, layout, control):
    target = (state.tick + jnp.uint32(1)).astype(jnp.float64) * dt

    def active(current):
        return (current.pool.time_s < target) & (current.fault == 0) & (current.pool.fault == 0)

    def segment(current):
        updated, _ = pool_step(current.pool, world_id, seed, root, constants, target, event_limit)
        duration = updated.time_s - current.pool.time_s
        opening = availability(current.pool, levels)
        held = control._replace(channel=control.channel * opening)
        next_ionic, valid = rk4_checked_step(
            ionic.rhs, ionic.domain_valid, current.ionic, duration, held, layout, layout.active
        )
        valid &= (duration > 0) & (updated.fault == 0)
        return CoupledState(
            updated,
            next_ionic,
            current.tick,
            current.segments + (duration > 0).astype(jnp.uint32),
            current.availability_exposure_s + opening * duration,
            jnp.where(valid, current.fault, jnp.int32(1)),
        )

    result = jax.lax.while_loop(active, segment, state)
    success = (result.fault == 0) & (result.pool.fault == 0) & (result.pool.time_s == target)
    return result._replace(tick=result.tick + success.astype(jnp.uint32))


@partial(jax.jit, static_argnames=("ticks",))
def advance(state, ids, seed, root, constants, event_limit, dt, levels, layout, control, *, ticks):
    def body(_, current):
        return jax.vmap(one_tick, in_axes=(0, 0, None, None, None, None, None, None, None, None))(
            current, ids, seed, root, constants, event_limit, dt, levels, layout, control
        )

    return jax.lax.fori_loop(0, ticks, body, state)
