"""The species-sum helper (cells/numerics/species_sums.py; operators/summation/SPEC.md §2).

Host equals device, bitwise, at the spec's 8-species inexact cases: products of fluxes with
valences z = ±3, and mu x dn, formed by the caller inside the compiled function. The fold's order
is declared; a reduce is not used; entity_sum is xp.sum.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.numerics.species_sums import entity_sum, species_sum

SPECIES = 8


def cases(shape):
    rng = np.random.default_rng(20261115)
    z = np.array([3.0, -3.0, 1.0, -1.0, 2.0, -2.0, 3.0, -3.0])[:SPECIES]
    flux = rng.normal(scale=1e-3, size=(SPECIES, *shape)) * np.exp(rng.normal(size=(SPECIES, *shape)))
    mu = 2.577 * np.log(rng.uniform(1e-6, 150.0, size=(SPECIES, *shape)))
    dn = rng.normal(scale=1e-9, size=(SPECIES, *shape))
    return z, flux, mu, dn


@pytest.mark.parametrize("shape", [(7,), (13, 5), (64,)])
def test_host_equals_device_bitwise_at_eight_species(shape):
    z, flux, mu, dn = cases(shape)
    zf = z.reshape((SPECIES,) + (1,) * len(shape))
    host_charge = species_sum(zf * flux, xp=np)
    host_energy = species_sum(mu * dn, xp=np)
    device_charge = jax.jit(lambda a, b: species_sum(a * b, xp=jnp))(zf, flux)
    device_energy = jax.jit(lambda a, b: species_sum(a * b, xp=jnp))(mu, dn)
    assert np.asarray(device_charge).tobytes() == host_charge.tobytes()
    assert np.asarray(device_energy).tobytes() == host_energy.tobytes()


def test_the_fold_is_serial_in_declared_order():
    values = np.array([1e16, 1.0, -1e16, 1.0])
    assert species_sum(values, xp=np) == ((1e16 + 1.0) + -1e16) + 1.0
    assert entity_sum(np.arange(6.0).reshape(2, 3), axis=1, xp=np).tolist() == [3.0, 12.0]
    with pytest.raises(ValueError):
        species_sum(np.zeros((0, 3)), xp=np)
