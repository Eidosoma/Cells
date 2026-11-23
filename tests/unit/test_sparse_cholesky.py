"""cells.numerics.sparse_cholesky (FR-17 stage 1): bind, factor and solve on SPD patterns, NumPy and
JAX, against dense references. No world is compiled: small synthetic systems only."""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.numerics import sparse_cholesky as sc

jax.config.update("jax_enable_x64", True)


def spd(pattern, seed):
    """An SPD matrix on a symmetric pattern: random off-diagonal entries, a dominant diagonal."""
    rng = np.random.default_rng(seed)
    a = np.where(np.tril(pattern, -1), rng.uniform(-1.0, 1.0, pattern.shape), 0.0)
    a = a + a.T
    a[np.diag_indices_from(a)] = np.abs(a).sum(axis=1) + rng.uniform(0.5, 2.0, a.shape[0])
    return a


def arrowhead(n, hub=0):
    p = np.eye(n, dtype=bool)
    p[hub, :] = p[:, hub] = True
    return p


def grid(m):
    n = m * m
    p = np.eye(n, dtype=bool)
    for r in range(m):
        for c in range(m):
            i = r * m + c
            for j in (i + 1 if c + 1 < m else None, i + m if r + 1 < m else None):
                if j is not None:
                    p[i, j] = p[j, i] = True
    return p


def random_pattern(n, density, seed):
    rng = np.random.default_rng(seed)
    p = np.tril(rng.uniform(size=(n, n)) < density, -1)
    return p | p.T | np.eye(n, dtype=bool)


PATTERNS = {
    "diagonal": np.eye(9, dtype=bool),
    "arrowhead_hub_first": arrowhead(12, hub=0),
    "arrowhead_hub_last": arrowhead(12, hub=11),
    "grid_5x5": grid(5),
    "random_40": random_pattern(40, 0.08, 3),
}


@pytest.mark.parametrize("name", sorted(PATTERNS))
@pytest.mark.parametrize("xp", [np, jnp], ids=["numpy", "jax"])
def test_factor_and_solve_against_dense(name, xp):
    pattern = PATTERNS[name]
    a = spd(pattern, seed=len(name))
    b = np.random.default_rng(7).uniform(-1.0, 1.0, a.shape[0])
    s = sc.bind(pattern)
    values = sc.factor(sc.assemble(xp.asarray(a), s, xp=xp), s, xp=xp)
    lower = np.zeros_like(a)
    lower[s.row, s.column] = np.asarray(values)
    permuted = a[np.ix_(s.order, s.order)]
    assert np.allclose(lower @ lower.T, permuted, rtol=1e-13, atol=1e-13)
    x = np.asarray(sc.solve(values, xp.asarray(b), s, xp=xp))
    assert np.allclose(x, np.linalg.solve(a, b), rtol=1e-12, atol=1e-13)
    assert np.allclose(a @ x, b, rtol=1e-12, atol=1e-13)


def test_minimum_degree_puts_the_hub_last_with_no_fill():
    pattern = arrowhead(30, hub=0)
    s = sc.bind(pattern)
    assert int(s.order[-1]) == 0
    assert s.row.size == np.tril(pattern).sum()  # No fill.
    assert len(s.levels) == 2  # The leaves, then the hub.
    natural = sc.bind(pattern, order=np.arange(30))
    assert natural.row.size == 30 * 31 // 2  # The hub first fills the whole factor.


def test_a_diagonal_system_is_one_level_in_the_dense_order_of_operations():
    d = np.random.default_rng(1).uniform(0.5, 3.0, 17)
    b = np.random.default_rng(2).uniform(-1.0, 1.0, 17)
    s = sc.bind(np.eye(17, dtype=bool))
    assert len(s.levels) == 1
    values = sc.factor(sc.assemble(np.diag(d), s, xp=np), s, xp=np)
    root = np.sqrt(d)
    assert np.asarray(values)[s.rank].tobytes() == root.tobytes()
    x = sc.solve(values, b, s, xp=np)
    assert np.asarray(x).tobytes() == ((b / root) / root).tobytes()
    xj = sc.solve(sc.factor(sc.assemble(jnp.asarray(np.diag(d)), s, xp=jnp), s, xp=jnp),
                  jnp.asarray(b), s, xp=jnp)
    assert np.asarray(xj).tobytes() == np.asarray(x).tobytes()


def test_the_level_schedule_orders_every_column_after_its_children():
    s = sc.bind(PATTERNS["random_40"])
    level_of = {}
    for k, lv in enumerate(s.levels):
        for j in np.asarray(s.column[lv.pivots]).tolist():
            level_of[j] = k
    assert sorted(level_of) == list(range(40))
    for j, p in enumerate(s.parent.tolist()):
        if p >= 0:
            assert level_of[p] > level_of[j]


def test_a_jitted_factor_and_solve_agree_with_the_eager_ones():
    pattern = PATTERNS["grid_5x5"]
    a, b = spd(pattern, 11), np.linspace(-1.0, 1.0, 25)
    s = sc.bind(pattern)

    def run(a, b):
        return sc.solve(sc.factor(sc.assemble(a, s, xp=jnp), s, xp=jnp), b, s, xp=jnp)

    jitted = jax.jit(run)(jnp.asarray(a), jnp.asarray(b))
    assert np.allclose(np.asarray(jitted), np.linalg.solve(a, b), rtol=1e-12, atol=1e-13)


def test_a_matrix_that_is_not_positive_definite_gives_a_non_finite_factor():
    pattern = arrowhead(6, hub=2)
    a = spd(pattern, 5)
    a[2, 2] = -1.0
    s = sc.bind(pattern)
    values = sc.factor(sc.assemble(a, s, xp=np), s, xp=np)
    assert not np.all(np.isfinite(np.asarray(values)))


@pytest.mark.parametrize(
    "bad", [np.ones((3, 4), dtype=bool), np.triu(np.ones((3, 3), dtype=bool)),
            ~np.eye(3, dtype=bool)],
    ids=["not square", "not symmetric", "no diagonal"],
)
def test_bind_refuses_a_pattern_that_is_not_a_symmetric_square_with_its_diagonal(bad):
    with pytest.raises(ValueError):
        sc.bind(bad)
