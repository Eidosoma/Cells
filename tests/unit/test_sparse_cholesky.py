"""cells.numerics.sparse_cholesky (FR-17 stage 1): bind, factor, solve and product on SPD patterns,
NumPy and JAX, against dense references. No world is compiled: small synthetic systems only."""

import heapq

import jax
import jax.numpy as jnp
import jax.scipy.linalg
import numpy as np
import pytest

from cells.numerics import sparse_cholesky as sc
from cells.numerics import surface_field as field

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


def coordinates(pattern):
    rows, columns = np.nonzero(np.tril(pattern, -1))
    return pattern.shape[0], rows, columns


def plans(pattern, order=None):
    s = sc.bind(*coordinates(pattern), order=order)
    return s, sc.factor_plan(s), sc.solve_plan(s)


def assembled(a, s):
    return a[s.row, s.column]  # The factor's positions hold the system's entries (zero at fill).


def dense_factor(values, s):
    lower = np.zeros((s.size, s.size))
    lower[s.rank[s.row], s.rank[s.column]] = np.asarray(values)
    return lower


def run(xp, a, b, s, fp, sp, *, jit=False):
    def go(a, b):
        f = sc.factor(assembled(a, s), fp, xp=xp)
        return f, sc.solve(f, b, sp, xp=xp)

    if xp is np:
        return go(a, b)
    return (jax.jit(go) if jit else go)(jnp.asarray(a), jnp.asarray(b))


@pytest.mark.parametrize("name", sorted(PATTERNS))
@pytest.mark.parametrize("xp", [np, jnp], ids=["numpy", "jax"])
def test_factor_and_solve_against_dense(name, xp):
    pattern = PATTERNS[name]
    a = spd(pattern, seed=len(name))
    b = np.random.default_rng(7).uniform(-1.0, 1.0, a.shape[0])
    s, fp, sp = plans(pattern)
    values, x = (np.asarray(v) for v in run(xp, a, b, s, fp, sp))
    lower = dense_factor(values, s)
    permuted = a[np.ix_(s.order, s.order)]
    assert np.allclose(lower @ lower.T, permuted, rtol=1e-13, atol=1e-13)
    assert np.allclose(x, np.linalg.solve(a, b), rtol=1e-12, atol=1e-13)
    assert np.allclose(a @ x, b, rtol=1e-12, atol=1e-13)


@pytest.mark.parametrize("name", sorted(PATTERNS))
def test_the_defined_order_across_programs_and_backends(name, monkeypatch):
    """Eager JAX, jitted JAX and the fori_loop over levels (forced here) give the same bits on every
    pattern; the host's factor is the device's too, and its solve differs only in applying each
    pivot by division (the dense host solve's) rather than by the reciprocal (the device's)."""
    pattern = PATTERNS[name]
    a, b = spd(pattern, 4), np.random.default_rng(5).uniform(-1.0, 1.0, (pattern.shape[0], 3))
    s, fp, sp = plans(pattern)
    reference = [np.asarray(v).tobytes() for v in run(jnp, a, b, s, fp, sp)]
    assert [np.asarray(v).tobytes() for v in run(jnp, a, b, s, fp, sp, jit=True)] == reference
    monkeypatch.setattr(sc, "UNROLLED_LEVELS", 0)
    assert [np.asarray(v).tobytes() for v in run(jnp, a, b, s, fp, sp, jit=True)] == reference
    factor, x = run(np, a, b, s, fp, sp)
    assert factor.tobytes() == reference[0]
    device = np.frombuffer(reference[1]).reshape(x.shape)
    assert np.max(np.abs(x - device)) <= 1e-14 * np.max(np.abs(device))


@pytest.mark.parametrize("n", [1, 2, 7, 64, 65, 300])
def test_a_diagonal_system_is_the_dense_path_bit_for_bit(n):
    """One level, no terms: the factor is the dense Cholesky's, by bytes, and the solve the dense
    solve's on the same backend: on the device jax's cho_solve (dtrsm multiplies by each pivot's
    reciprocal), on the host surface_field.cholesky_solve (it divides). A zero right-hand side entry
    solves to a zero of either sign on the device: from 64 rows the dense blocked dtrsm turns some
    -0.0 into +0.0 (measured), while this solve keeps each zero's sign."""
    rng = np.random.default_rng(n)
    d = rng.uniform(0.3, 3.0, n) * 10.0 ** rng.uniform(-3, 3, n)
    b = rng.uniform(-1.0, 1.0, n) * 10.0 ** rng.uniform(-20, 0, n)
    b[: n // 3] = 0.0
    b[n // 3 : n // 2] = -0.0
    s, fp, sp = plans(np.eye(n, dtype=bool))
    assert len(fp.entry) == 1 and fp.terms.shape[-1] == 0

    @jax.jit
    def dense(a, b):
        factor = jnp.linalg.cholesky(a)
        return jnp.diagonal(factor), jax.scipy.linalg.cho_solve((factor, True), b)

    root, expected = (np.asarray(v) for v in dense(jnp.asarray(np.diag(d)), jnp.asarray(b)))
    host = field.cholesky_solve(np.diag(np.sqrt(d)), b, xp=np)
    nonzero = b != 0
    for xp, reference in ((np, host), (jnp, expected)):
        values, x = (np.asarray(v) for v in run(xp, np.diag(d), b, s, fp, sp, jit=xp is jnp))
        assert values[s.rank].tobytes() == root.tobytes()
        assert x[nonzero].tobytes() == reference[nonzero].tobytes()
        assert np.all(x[~nonzero] == 0) and np.array_equal(np.signbit(x), np.signbit(b))
    assert host.tobytes() == x.tobytes() or not np.array_equal(host[nonzero], expected[nonzero])


@pytest.mark.parametrize("name", sorted(PATTERNS))
def test_products_against_dense_and_host_equals_device(name):
    pattern = PATTERNS[name]
    n, rows, columns = coordinates(pattern)
    plan = sc.product_plan(n, rows, columns)
    a = spd(pattern, 9)
    a[0, 0] = 0.0  # A zero entry on the pattern stays an entry.
    x = np.random.default_rng(3).uniform(-1.0, 1.0, (n, 2))
    values = a[plan.row, plan.column]
    host = sc.product(values, x, plan, xp=np)
    assert np.allclose(host, a @ x, rtol=1e-13, atol=1e-14)
    device = jax.jit(lambda v, x: sc.product(v, x, plan, xp=jnp))(values, x)
    assert np.asarray(device).tobytes() == host.tobytes()


def test_the_pairwise_fold_is_its_tree_with_signed_zeros():
    """fold sums each segment in adjacent pairs, step by step; padding adds -0.0, and an empty
    segment gives +0.0, so a sum of -0.0 terms stays -0.0."""
    rng = np.random.default_rng(11)
    lengths = [0, 1, 2, 3, 4, 5, 8, 9, 17]
    terms = rng.uniform(-1.0, 1.0, sum(lengths)) * 10.0 ** rng.uniform(-8, 8, sum(lengths))
    segments, start = [], 0
    for k in lengths:
        segments.append(list(range(start, start + k)))
        start += k
    pairs, out = sc.pairwise_plan(segments, terms.size)

    def tree(values):
        values = list(values)
        while len(values) > 1:
            values = [values[i] + values[i + 1] if i + 1 < len(values) else values[i]
                      for i in range(0, len(values), 2)]  # fmt: skip
        return values[0] if values else 0.0

    expected = np.asarray([tree(terms[s]) for s in segments])
    for xp in (np, jnp):
        assert np.asarray(sc.fold(xp.asarray(terms), pairs, out, xp=xp)).tobytes() == (
            expected.tobytes()
        )
    zeros = np.full(terms.size, -0.0)
    summed = sc.fold(zeros, pairs, out, xp=np)
    assert np.signbit(summed).tolist() == [k > 0 for k in lengths]


def reference_minimum_degree(pattern):
    """The definition, by scanning every live node at each step (O(n^2))."""
    n = pattern.shape[0]
    adjacency = [set(np.flatnonzero(pattern[i]).tolist()) - {i} for i in range(n)]
    original = [len(a) for a in adjacency]
    alive, order = set(range(n)), []
    for _ in range(n):
        node = min(alive, key=lambda i: (len(adjacency[i]), original[i], i))
        for a in adjacency[node]:
            adjacency[a].discard(node)
            adjacency[a] |= adjacency[node] - {a}
        alive.discard(node)
        order.append(node)
    return order


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_heap_minimum_degree_is_the_definition(seed):
    pattern = random_pattern(60, 0.06, seed)
    assert sc.minimum_degree(*coordinates(pattern)).tolist() == reference_minimum_degree(pattern)
    assert heapq  # The module under test uses the standard library's heap.


def test_minimum_degree_puts_the_hub_last_with_no_fill():
    pattern = arrowhead(30, hub=0)
    s = sc.bind(*coordinates(pattern))
    assert int(s.order[-1]) == 0
    assert s.row.size == np.tril(pattern).sum()  # No fill.
    assert int(s.level.max()) + 1 == 2  # The leaves, then the hub.
    natural = sc.bind(*coordinates(pattern), order=np.arange(30))
    assert natural.row.size == 30 * 31 // 2  # The hub first fills the whole factor.


def test_the_level_schedule_orders_every_column_after_its_children():
    s = sc.bind(*coordinates(PATTERNS["random_40"]))
    for k, p in enumerate(s.parent.tolist()):
        if p >= 0:
            assert s.level[p] > s.level[k]
    sp = sc.solve_plan(s)
    nodes = sp.node[sp.node < s.size]
    assert sorted(nodes.tolist()) == list(range(40))


def test_a_matrix_that_is_not_positive_definite_gives_a_non_finite_factor():
    pattern = arrowhead(6, hub=2)
    a = spd(pattern, 5)
    a[2, 2] = -1.0
    s, fp, _ = plans(pattern)
    with np.errstate(invalid="ignore", divide="ignore"):  # The square root of a negative pivot.
        values = sc.factor(assembled(a, s), fp, xp=np)
    assert not bool(sc.finite(values, xp=np))
    assert not bool(sc.finite(sc.factor(jnp.asarray(assembled(a, s)), fp, xp=jnp), xp=jnp))


@pytest.mark.parametrize(
    "args",
    [(0, [], []), (3, [0, 1], [1]), (3, [0], [3]), (3, [-1], [0])],
    ids=["empty", "unequal coordinates", "outside", "negative"],
)
def test_bind_refuses_a_malformed_pattern(args):
    with pytest.raises(ValueError):
        sc.bind(*args)


def test_bind_refuses_an_order_that_is_not_a_permutation():
    with pytest.raises(ValueError):
        sc.bind(3, [0], [1], order=[0, 0, 1])
