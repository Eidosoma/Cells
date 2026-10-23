"""Repeated route ownership must retain rounding and independent world identity."""

import os
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.models.surface_kinetic import channel_to_membrane
from cells.numerics.extracellular_field import ordered_scatter


def reference(values, target, indices):
    result = np.zeros_like(target)
    np.add.at(result, (Ellipsis, *indices), values)
    return result


def exact(actual, expected):
    actual, expected = np.asarray(actual), np.asarray(expected)
    assert actual.shape == expected.shape and actual.dtype == expected.dtype
    assert actual.tobytes() == expected.tobytes()


@pytest.fixture(scope="module")
def device():
    jax.config.update("jax_enable_x64", True)
    return jax.devices(os.environ.get("CELLS_COMPONENT_BACKEND", "cpu"))[0]


@pytest.mark.parametrize("leading", [(), (4,), (2, 4)])
@pytest.mark.parametrize("coordinates", [1, 2])
def test_repeated_destinations_preserve_declared_addition_order(device, leading, coordinates):
    # Cancellation deliberately distinguishes valid arithmetic orders. It is a
    # numerical regression input, not a physiological concentration or flux.
    values = np.broadcast_to(np.array([1e16, 1.0, -1e16, 1.0] * 6), (*leading, 24)).copy()
    indices = (np.zeros(24, np.int64),) * coordinates
    target = np.full((*leading, *((3,) * coordinates)), 17.0)
    expected = reference(values, target, indices)
    exact(ordered_scatter(values, target, indices, xp=np), expected)
    compiled = (
        jax.jit(ordered_scatter).lower(*jax.device_put((values, target, indices), device)).compile()
    )
    for _ in range(16):
        result = compiled(*jax.device_put((values, target, indices), device))
        assert result.device == device
        exact(result, expected)


@pytest.mark.parametrize("routes", [0, 1])
def test_empty_and_single_route_keep_unused_targets_zero(device, routes):
    values = np.full((2, routes), 3.0)
    target = np.full((2, 4), 17.0)
    indices = (np.ones(routes, np.int64),)
    args = jax.device_put((values, target, indices), device)
    exact(jax.jit(ordered_scatter)(*args), reference(values, target, indices))


def test_mixed_owners_and_padding_remain_independent_under_batching(device):
    values = np.array(
        [[1e16, 2.0, 1.0, 4.0, -1e16, 3.0, 0.0], [7.0, 1e16, 5.0, 1.0, -2.0, -1e16, 0.0]]
    )
    owners = np.array([[0, 1, 0, 1, 0, 0, 2], [2, 0, 2, 0, 2, 0, 1]])
    expected = np.stack(
        [reference(v, np.zeros(4), (o,)) for v, o in zip(values, owners, strict=True)]
    )

    def mapped(v, o):
        return jax.lax.map(lambda pair: ordered_scatter(pair[0], jnp.zeros(4), (pair[1],)), (v, o))

    compiled = jax.jit(mapped)
    for order in (np.array([0, 1]), np.array([1, 0])):
        result = compiled(*jax.device_put((values[order], owners[order]), device))
        exact(result, expected[order])
    vmapped = jax.jit(jax.vmap(lambda v, o: ordered_scatter(v, jnp.zeros(4), (o,))))
    exact(vmapped(*jax.device_put((values, owners), device)), expected)


@pytest.mark.parametrize("shared", [False, True])
def test_channel_population_routing_uses_ordered_accumulation(device, shared):
    values = np.array([1e16, 1.0, -1e16, 1.0] * 6)
    owners = np.zeros(24, np.int64)
    p = SimpleNamespace(membrane_permeability=np.zeros((2, 3)), channel_membranes=owners)
    if shared:
        values = np.stack((values, values))
        p.channel_relative_permeability = np.ones_like(values)
        indices = (owners,)
    else:
        p.channel_species = np.ones(24, np.int64)
        indices = (p.channel_species, owners)
    expected = reference(values, p.membrane_permeability, indices)
    exact(channel_to_membrane(values, p, xp=np), expected)
    p = SimpleNamespace(**{k: jax.device_put(v, device) for k, v in vars(p).items()})
    actual = jax.jit(lambda v: channel_to_membrane(v, p, xp=jnp))(jax.device_put(values, device))
    exact(actual, expected)
