"""Analytic checks for external/assembly event ties, independent of tissue physics."""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.assembly_cluster import engine
from cells.assembly_cluster.controls import ScheduledControl
from cells.assembly_cluster.kernel import one_tick
from cells.assembly_cluster.spec import parse_spec
from tests.unit.test_assembly_cluster import raw_for


class Control(NamedTuple):
    channel: object
    injury: object
    resealing: object


class Integral(NamedTuple):
    channel: object
    injury: object
    resealing: object


class Layout(NamedTuple):
    active: object


class IntegralModel:
    @staticmethod
    def rhs(state, control, layout, active):
        return Integral(*control)

    @staticmethod
    def domain_valid(state, layout, active):
        return jnp.all(jnp.stack([jnp.all(jnp.isfinite(v)) for v in state]))


def prepared():
    jax.config.update("jax_enable_x64", True)
    raw = raw_for(worlds=1)
    for row in raw["pools"]:
        row["pool"].update(
            k_on_M_inv_s=0.0, k_close_s_inv=0.0, k_off_s_inv=0.0, k_fragment_dissolve_s_inv=0.0
        )
    spec = parse_spec(raw)
    state = jax.tree.map(lambda v: v[0].copy(), engine.initial_state(spec))
    state = state._replace(ionic=Integral(*(np.zeros(2) for _ in range(3))))
    args = (
        np.uint32(0),
        np.array([b.pool.seed for b in spec.pools], np.uint32),
        np.array([b.pool.root_node for b in spec.pools], np.uint32),
        np.zeros((2, 4)),
        np.full(2, 100, np.uint32),
        np.float64(2**-16),
        np.array([[0.0, 1.0], [0.0, 1.0]]),
        np.array([0, 1], np.int32),
        Layout(np.ones(2, bool)),
    )
    return spec, state, args


def exact(left, right):
    for a, b in zip(jax.tree.leaves(left), jax.tree.leaves(right), strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


def test_union_clock_ties_apply_preceding_inputs_then_commit_events():
    spec, state, args = prepared()
    dt = args[5]
    # A ring-breaking event coincides with an external control at 3/8 tick.
    state.pool.pending_valid[0] = True
    state.pool.pending_time_s[0] = 0.375 * dt
    state.pool.pending_event[0] = 30 + spec.pools[0].pool.initial_bond_indices[0]
    times = np.array([0.0, 0.25 * dt, 0.375 * dt, 0.75 * dt, dt, np.inf])
    channels = np.repeat(np.array([1.0, 0.5, 1.0, 0.25, 0.0])[:, None], 2, axis=1)
    injury = np.repeat(np.array([0.0, 1.0, 1.0, 0.0, 0.0])[:, None], 2, axis=1)
    control = ScheduledControl(times, Control(channels, injury, np.ones_like(channels)))
    advance = jax.jit(lambda current, c: one_tick(current, *args, c, model=IntegralModel))
    result = advance(state, control)
    np.testing.assert_array_equal(result.ionic.channel, np.array([0.3125, 0.75]) * dt)
    np.testing.assert_array_equal(result.ionic.injury, np.full(2, 0.5 * dt))
    np.testing.assert_array_equal(result.ionic.resealing, np.full(2, dt))
    np.testing.assert_array_equal(result.pool.event_count, [1, 0])
    assert result.segments == 4 and result.tick == 1 and result.fault == 0
    np.testing.assert_array_equal(result.availability_exposure_s, np.array([0.375, 1.0]) * dt)
    continued = advance(result, control)
    # The external change exactly at the tick acts only on the next tick.
    exact(continued.ionic.channel, result.ionic.channel)
    exact(continued.ionic.injury, result.ionic.injury)
    assert continued.segments == 5 and continued.tick == 2 and continued.fault == 0


def test_constant_input_retains_original_clock_and_arithmetic():
    _, state, args = prepared()
    control = Control(np.array([0.25, 0.5]), np.array([1.0, 0.0]), np.ones(2))
    table = ScheduledControl(np.array([0.0, np.inf]), jax.tree.map(lambda v: v[None], control))
    advance = jax.jit(lambda current, c: one_tick(current, *args, c, model=IntegralModel))
    exact(advance(state, control), advance(state, table))
