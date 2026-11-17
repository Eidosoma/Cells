"""GARD references, rows 3 and 4: local detailed balance and the closed world's
stationary law.

Planted controls: the single-event form must be refused as passive, and must depart
from the product form (P2).
"""

from __future__ import annotations

import itertools
import math
from fractions import Fraction

import numpy as np
import pytest

from validation.gard.references import closed_world as cw
from validation.gard.references import detailed_balance as db
from validation.gard.references.harness import probe_input_arrays
from validation.gard.references.kernels import (ExactLaw, ExchangeLaw, HeldReservoir, PAIR_CONSISTENT,
                                                SINGLE_EVENT, propensities)


@pytest.fixture(scope="module")
def kernel_inputs():
    return probe_input_arrays()["kernel_probe_inputs"]


def _law(inp, form):
    return ExchangeLaw(inp["beta"], inp["k_join"], inp["k_leave"], HeldReservoir(inp["rho"]), form)


def test_pair_consistent_kernel_identity_on_200_states(kernel_inputs):
    res = db.check_local_detailed_balance(_law(kernel_inputs, PAIR_CONSISTENT), kernel_inputs["states"])
    assert res.passed and res.detail["verdict"] == db.PASSIVE, res.detail
    assert res.detail["max_abs_residual"] < 1e-13
    assert kernel_inputs["states"].shape == (200, 100)


def test_single_event_form_is_refused_as_passive(kernel_inputs):
    law = _law(kernel_inputs, SINGLE_EVENT)
    res = db.check_local_detailed_balance(law, kernel_inputs["states"])
    assert res.passed and res.detail["verdict"] == db.REFUSED  # correct verdict for this form
    assert res.detail["max_abs_residual"] > 1e3 * db.LDB_ATOL
    # an engine declaring it passive is caught
    table = db.kernel_table(law, kernel_inputs["states"])
    bad = db.check_local_detailed_balance(law, kernel_inputs["states"], table, declared_verdict=db.PASSIVE)
    assert not bad.passed


def test_a_mislabelled_table_is_caught(kernel_inputs):
    # single-event propensities presented as the pair-consistent law
    se = db.kernel_table(_law(kernel_inputs, SINGLE_EVENT), kernel_inputs["states"])
    res = db.check_local_detailed_balance(_law(kernel_inputs, PAIR_CONSISTENT), kernel_inputs["states"], se,
                                          declared_verdict=db.PASSIVE)
    assert not res.passed and not res.detail["propensities_match_form"]


def test_exact_identity_in_rationals_on_small_states():
    rng = np.random.default_rng(3)
    beta = [[Fraction(int(v), 7) for v in row] for row in rng.integers(0, 30, size=(3, 3))]
    for form, expect in ((PAIR_CONSISTENT, True), (SINGLE_EVENT, False)):
        law = ExactLaw.make(beta, "1/100", "1/10000", form, rho="1/100")
        ok = True
        for x in itertools.product(range(4), repeat=3):
            N = sum(x)
            if N < 1:
                continue
            ap, _ = law.propensities(x)
            for i in range(3):
                y = list(x); y[i] += 1
                _, am = law.propensities(tuple(y))
                ok &= ap[i] / am[i] == Fraction(100) * Fraction(1, 100) * N / (x[i] + 1)
        assert ok == expect


def test_p1_square_reproduces_the_design_table():
    se = db.check_p1_square(SINGLE_EVENT)
    assert se.passed
    lnr = [row["ln_ratio"] for row in se.detail["rows"]]
    assert [round(v, 3) for v in lnr] == [0.012, 0.080, 0.113, 0.117]
    far = db.check_p1_square(SINGLE_EVENT, x=(40, 40))
    far_ln = [row["ln_ratio"] for row in far.detail["rows"]]
    assert far.passed and 1.6e-5 < min(far_ln) and max(far_ln) < 1.6e-4
    for x in ((1, 1), (40, 40)):
        pc = db.check_p1_square(PAIR_CONSISTENT, x=x)
        assert pc.passed and all(row["exact"] == "1" for row in pc.detail["rows"])


def test_the_independent_check_hand_square_44_over_63():
    law = ExactLaw.make([[1, 6], [2, 0]], "1/100", "1/10000", SINGLE_EVENT, rho="1/100")
    assert db.square_cycle_ratio(law, (1, 0)) == Fraction(44, 63)
    pc = ExactLaw.make([[1, 6], [2, 0]], "1/100", "1/10000", PAIR_CONSISTENT, rho="1/100")
    assert db.square_cycle_ratio(pc, (1, 1)) == 1


def test_p2_total_variation_with_the_design_parameters():
    se11 = cw.check_closed_world_float([[50, 0], [0, 0]], 0.05, (8, 8), SINGLE_EVENT)
    se12 = cw.check_closed_world_float([[0, 50], [0, 0]], 0.05, (8, 8), SINGLE_EVENT)
    pc11 = cw.check_closed_world_float([[50, 0], [0, 0]], 0.05, (8, 8), PAIR_CONSISTENT)
    assert se11.passed and abs(se11.detail["total_variation"] - cw.P2_TV_BETA11) < 1e-6
    assert se12.passed and abs(se12.detail["total_variation"] - cw.P2_TV_BETA12) < 1e-6
    assert pc11.passed and pc11.detail["total_variation"] < cw.TV_FLOAT_ATOL


@pytest.mark.parametrize("M", [(4, 4), (2, 2, 2)])
def test_closed_world_exact_master_equation(M):
    rng = np.random.default_rng(len(M))
    G = len(M)
    beta = [[Fraction(int(v), 3) for v in row] for row in rng.integers(0, 40, size=(G, G))]
    assert cw.check_closed_world_exact(beta, Fraction(1, 4), M, PAIR_CONSISTENT).detail["exact_zero"]
    se = cw.check_closed_world_exact(beta, Fraction(1, 4), M, SINGLE_EVENT)
    assert se.passed and not se.detail["exact_zero"]  # planted: the single-event form departs


def test_three_type_float_solve():
    beta = probe_input_arrays()["closed_world_three_types_inputs"]["beta"]
    assert cw.check_closed_world_float(beta, 0.1, (4, 4, 4), PAIR_CONSISTENT).passed
    assert cw.check_closed_world_float(beta, 0.1, (4, 4, 4), SINGLE_EVENT).passed


def test_rank_one_exception_of_section_2_5():
    assert cw.check_rank_one_exception((2, 3), (1, 2), Fraction(1, 5), (4, 4)).passed


def test_held_table_converts_to_the_closed_world():
    M, theta = (5, 4), 0.2
    states = np.asarray(cw.closed_states(M))
    beta = np.array([[2.0, 0.5], [1.5, 0.0]])
    held = ExchangeLaw(beta, 1.0, 1.0, HeldReservoir(np.ones(2)), PAIR_CONSISTENT)
    j = np.array([propensities(held, x)[0] for x in states])
    lv = np.array([propensities(held, x)[1] for x in states])
    cj, cl = cw.held_to_closed(states, j, lv, np.ones(2), np.ones(2), np.ones(2), theta, M)
    closed = cw.theta_law(beta, theta, M, PAIR_CONSISTENT)
    want = np.array([propensities(closed, x)[0] for x in states])
    assert np.allclose(cj, want, rtol=1e-14, atol=0)
    assert cw.check_closed_table(states, cj, cl, theta, M, PAIR_CONSISTENT).passed


def test_held_measure_is_normalisable_only_below_one():
    # mass marginal of (N-1)! prod (K rho)^x / x! is s^N / N (multinomial theorem)
    for s in (0.5, 0.9):
        assert math.isclose(sum(s ** N / N for N in range(1, 4000)), -math.log(1 - s), rel_tol=1e-12)
    partial = [sum(1.0 / N for N in range(1, n)) for n in (10, 1000, 100000)]
    assert partial[2] > partial[1] > partial[0] + 4  # s = 1 diverges (harmonic series)
