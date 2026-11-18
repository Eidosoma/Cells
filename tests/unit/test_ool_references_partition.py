"""OL5 references for OL3 (§0.2c rules 9 and 10): C3x and the lumen split, replayable from the
uniforms, with their exact laws.

Planted controls: G1's floor-to-first sizes, ties broken by the later list position, blocks given
to daughters without pi, the largest minimising cut, and lumen weights by area instead of by
sphere volume.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest

from validation.ool.references import partition as PT

EQUAL_CASES = [((2, 1, 2), 3), ((3, 2), 2), ((2, 2, 2), 3), ((1, 1, 1, 1), 2), ((4, 1), 3), ((3, 3), 3)]


@pytest.mark.parametrize("counts,k", EQUAL_CASES)
def test_c3x_at_equal_areas_is_the_balanced_hypergeometric_in_random_order(counts, k):
    law = PT.exact_law(counts, (1,) * len(counts), k)
    assert PT.total_variation(law, PT.balanced_hypergeometric_law(list(counts), k)) == 0
    assert sum(law.values()) == 1


@pytest.mark.parametrize("counts,k", [((2, 1, 2), 3), ((3, 2), 2), ((4, 1), 3)])
def test_planted_sizes_and_orders_depart_where_N_mod_k_is_not_zero(counts, k):
    ref = PT.balanced_hypergeometric_law(list(counts), k)
    for planted in ("g1_sizes", "no_pi"):
        assert PT.total_variation(PT.exact_law(counts, (1,) * len(counts), k, planted), ref) >= Fraction(1, 2)


def test_unequal_areas_conserve_the_parent_and_keep_the_daughters_exchangeable():
    for counts, areas, k in (((2, 2), (1, 2), 2), ((2, 1, 2), (1, 3, 2), 3)):
        law = PT.exact_law(counts, areas, k)
        W = sum(n * a for n, a in zip(counts, areas))
        for key in law:
            assert [sum(r[i] for r in key) for i in range(len(counts))] == list(counts)
        marg = PT.daughter_marginals(law, k)
        assert all(marg[j] == marg[0] for j in range(k))
        # the cuts minimise |k S_c - t W|, so every block's area is within one molecule of W/k
        for key in law:
            for r in key:
                assert abs(k * sum(r[i] * areas[i] for i in range(len(counts))) - W) <= k * max(areas)
    # planted: the largest minimiser c. pi randomises the blocks' order, so it leaves the law
    # unchanged (zero power distributionally); the replay catches it, outcome by outcome
    law_small = PT.exact_law((2, 1), (1, 1), 2)
    assert PT.total_variation(law_small, PT.exact_law((2, 1), (1, 1), 2, "largest_c")) == 0
    u = [0.1, 0.5, 0.9, 0.3, 0.7]
    assert PT.c3x((2, 1), (1, 1), 2, u)[0] != PT.c3x((2, 1), (1, 1), 2, u, "largest_c")[0]


def test_replay_from_uniforms_is_deterministic_and_rule_ordered():
    rng = np.random.default_rng(20261118)
    counts, areas, lumen, k = (3, 2, 1), (1, 2, 3), (4, 2), 3
    N = sum(counts)
    u = list(rng.random(N + k + sum(lumen)))
    a = PT.split_from_uniforms(counts, areas, lumen, k, u)
    b = PT.split_from_uniforms(counts, areas, lumen, k, u)
    assert a == b and a["uniforms_used"] == len(u)
    assert [sum(r[i] for r in a["membrane"]) for i in range(3)] == list(counts)
    assert [sum(r[i] for r in a["lumen"]) for i in range(2)] == list(lumen)
    assert sorted(a["pi"]) == list(range(k)) and abs(sum(a["weights"]) - 1) < 1e-15
    # ties: two molecules with the same uniform are ranked by list position (planted: the reverse)
    u_tied = list(u)
    u_tied[1] = u_tied[0]
    assert PT.rank(u_tied[:N]) != PT.rank(u_tied[:N], "ties_last")
    assert PT.rank(u_tied[:N]).index(0) < PT.rank(u_tied[:N]).index(1)


def test_lumen_weights_are_sphere_volumes_and_the_split_is_multinomial():
    mem = [[2, 0], [1, 1]]                   # W = 2 and 3 at k = (1, 2)
    p = PT.lumen_weights(mem, (1, 2))
    assert p[0] == pytest.approx(2 ** 1.5 / (2 ** 1.5 + 3 ** 1.5), rel=1e-15)
    # planted: weights by area (W_j / Sum W) instead of V_sph
    assert abs(p[0] - 2 / 5) > 0.04
    # the split's law at one species: binomial(L, p_pi) by enumeration of u over a fine grid of bins
    pi = [1, 0]
    cum = [p[pi[0]], 1.0]
    L, M = 3, 2 ** 12
    counts = {}
    grid = (np.arange(M) + 0.5) / M
    for u0 in grid[::64]:
        for u1 in grid[::64]:
            for u2 in grid[::64]:
                out = PT.lumen_split([L], p, pi, [u0, u1, u2])
                key = out[0][0]
                counts[key] = counts.get(key, 0) + 1
    n = sum(counts.values())
    from math import comb
    for x in range(L + 1):
        exp = comb(L, x) * p[0] ** x * p[1] ** (L - x)
        assert abs(counts.get(x, 0) / n - exp) < 0.03
    del cum
