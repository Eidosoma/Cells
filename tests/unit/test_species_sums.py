"""The species-sum helper (cells/numerics/species_sums.py; operators/summation/SPEC.md §2, §5).

SPEC §5's guard, with micro.py's M2 as the template: NumPy against the jit-compiled helper,
bitwise, at 8, 16, 17, 50, 150, 256 and 1,024 species and 1, 254 and 1151 columns. The cases are
materialized terms, z x n formed inside the compiled function (|z| in {1, 2}, and z = ±3), and
mu x dn formed inside. Above 16 terms the device fold is a lax.scan (the fold's gate, FR-43 /
D315), so 17, 50, 150, 256 and 1,024 check it against the host's loop; the gate itself is checked
on the program: no scan at 16 terms, one at 17.

The guard is not vacuous: without the barrier, at least one 8-species inexact case differs
between host and device, as test_species_cap asserts `differs > 0`.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.numerics.species_sums import UNROLLED_TERMS, entity_sum, species_sum

SEED = 20261115  # micro.py's.
COUNTS = (8, 16, 17, 50, 150, 256, 1024)
COLUMNS = (1, 254, 1151)


def terms(s, columns, rng):
    z_exact = np.array([(1, -1, 2, -2)[k % 4] for k in range(s)], dtype=np.float64)[:, None]
    z_three = np.array([(3, -1, -3, 1)[k % 4] for k in range(s)], dtype=np.float64)[:, None]
    n = rng.standard_normal((s, columns)) * 10.0 ** rng.uniform(-3, 0, size=(s, columns))
    mu = 1e3 * rng.uniform(-60, 60, size=(s, columns))
    return z_exact, z_three, n, mu


def same(host, device):
    device = np.asarray(device)
    return host.shape == device.shape and host.tobytes() == device.tobytes()


@pytest.mark.parametrize("s", COUNTS)
def test_host_equals_device_bitwise(s):
    rng = np.random.default_rng(SEED + s)
    fused = jax.jit(lambda a, b: species_sum(a * b, xp=jnp))
    for columns in COLUMNS:
        z_exact, z_three, n, mu = terms(s, columns, rng)
        materialized = mu * n
        assert same(species_sum(materialized, xp=np), jax.jit(lambda a: species_sum(a, xp=jnp))(materialized))
        assert same(species_sum(z_exact * n, xp=np), fused(z_exact, n)), (s, columns, "z exact")
        assert same(species_sum(z_three * n, xp=np), fused(z_three, n)), (s, columns, "z = ±3")
        assert same(species_sum(mu * n, xp=np), fused(mu, n)), (s, columns, "mu x dn")


def test_without_the_barrier_an_eight_species_inexact_case_differs():
    """Non-vacuous: the fold without its barrier differs on the device in at least one case."""
    rng = np.random.default_rng(SEED + 8)
    bare = jax.jit(lambda a, b: species_sum(a * b, xp=jnp, barrier=False))
    differs = 0
    for columns in COLUMNS:
        _, z_three, n, mu = terms(8, columns, rng)
        differs += int(not same(species_sum(z_three * n, xp=np), bare(z_three, n)))
        differs += int(not same(species_sum(mu * n, xp=np), bare(mu, n)))
    assert differs > 0, "the fold without the barrier never differed: the guard reaches nothing"


def test_the_fold_unrolls_through_16_terms_and_scans_above():
    """The gate is static on the fold's length: every world at 16 species or fewer keeps its
    program (its folds have at most 16 terms), and a longer fold's program holds one scan."""
    assert UNROLLED_TERMS == 16
    for s, scans in ((16, False), (17, True)):
        program = str(jax.make_jaxpr(lambda v: species_sum(v, xp=jnp))(np.zeros((s, 3))))
        assert ("scan" in program) == scans, (s, program)


def test_the_fold_is_serial_in_declared_order():
    values = np.array([1e16, 1.0, -1e16, 1.0])
    assert species_sum(values, xp=np) == ((1e16 + 1.0) + -1e16) + 1.0
    assert entity_sum(np.arange(6.0).reshape(2, 3), axis=1, xp=np).tolist() == [3.0, 12.0]
    with pytest.raises(ValueError):
        species_sum(np.zeros((0, 3)), xp=np)
