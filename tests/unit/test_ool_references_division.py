"""OL5 references for OL3 (the equal-area case needs no ruling): the exact partition laws and the
registered chi-square design.

Planted controls: a split at 0.55, a binomial split presented as hypergeometric, and daughters
whose counts do not sum to the parent's.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np

from validation.ool.references import division as Dv


def test_hypergeometric_pmf_sums_to_one_and_matches_labelled_counting():
    for parent, sizes in (((3, 2, 1), (3, 3)), ((2, 2, 1), (2, 2, 1))):
        splits = list(Dv.enumerate_splits(parent, sizes))
        pmf = {d: Dv.hypergeometric_pmf(parent, sizes, d) for d in splits}
        assert sum(pmf.values()) == 1
        assert pmf == Dv.labelled_count_pmf(parent, sizes)


def test_multinomial_lumen_pmf():
    f = (Fraction(1, 3), Fraction(2, 3))
    total = sum(Dv.multinomial_pmf((4, 2), f, ((a, 4 - a), (b, 2 - b))) for a in range(5) for b in range(3))
    assert total == 1
    assert Dv.multinomial_pmf((1,), f, ((1, 0),)) == Fraction(1, 3)


def test_registered_chi_square_design_has_power():
    d = Dv.chi_square_design()
    assert d["parent"] == [40, 30, 10] and d["splits"] == 400
    assert not d["underpowered"] and min(d["power"].values()) > 0.999
    assert abs(sum(d["expected"]) - 1) < 1e-12


def test_reference_sampler_passes_and_planted_splits_fail():
    d = Dv.chi_square_design()
    rng = np.random.default_rng(20261117)
    parent = np.array(Dv.REGISTERED_PARENT)
    N = int(parent.sum())
    honest = np.array([rng.multivariate_hypergeometric(parent, N // 2)[0] for _ in range(d["splits"])])
    assert Dv.chi_square_test(honest, d).passed
    at055 = np.array([rng.multivariate_hypergeometric(parent, int(round(0.55 * N)))[0] for _ in range(d["splits"])])
    assert not Dv.chi_square_test(at055, d).passed
    binom = rng.binomial(parent[0], 0.5, size=d["splits"])
    assert not Dv.chi_square_test(binom, d).passed


def test_counts_must_sum_to_the_parent():
    parent = (40, 30, 10)
    good = np.array([[20, 20], [15, 15], [5, 5]])
    assert Dv.check_conservation(parent, good).passed
    bad = good.copy()
    bad[1, 1] -= 1
    assert not Dv.check_conservation(parent, bad).passed
