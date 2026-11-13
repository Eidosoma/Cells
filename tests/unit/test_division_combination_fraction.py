"""J1 combination round: the f calibration helper finds the registered crossing.

The main case runs the round's own search on a synthetic cell (tests/division_fixtures.py), not
the J1 egg. At every evaluation, P_old is recalibrated on a pulse Rm taken before insertion and
the access on a pulse Rm at a later 'J1' pair, as the round does on the J1 egg. The search's
other branches (widening to [0, f_end], no crossing, an f_end computed only when needed) are
checked on a cheap monotone function.
"""

from dataclasses import replace

import pytest

from tests.division_fixtures import growing
from validation.division import cleft_egg_reference as ref
from validation.division import j1_combination_runner as comb

RM1_PAIR = (0, 1)  # before insertion, which starts at 1.2 s
J1_PAIR = (7, 8)  # pulse 8's front edge at 4.0 s plays J1


def cell(**changes):
    """The synthetic growing cell with insertion after the Rm1 pair and P_Na = P_K in the old
    membrane (as the J1 egg's), so that a bath-facing fraction moves Em at 'J1'."""
    base = dict(onset_s=1.2, schedule=((1.2, 2e-10),), old_relative=(1.0, 1.0, 0.0))
    return growing(**(base | changes))


@pytest.fixture(scope="module")
def em_at():
    # Targets the null cell meets at its own P_old and A/L, so every recalibration is feasible.
    rm1 = ref.rm_at(cell(), RM1_PAIR, method="LSODA")[0]
    rm2 = ref.rm_at(cell(), J1_PAIR, method="LSODA")[0]

    def em(f):
        value, egg = comb.recalibrated_em(
            cell(bath_fraction=f),
            rm1_ohm=rm1,
            rm2_ohm=rm2,
            rm1_pair=RM1_PAIR,
            j1_pair=J1_PAIR,
            em_pulse=J1_PAIR[1],
            guess=1e-7,
        )
        assert ref.rm_at(egg, J1_PAIR, method="LSODA")[0] == pytest.approx(rm2, rel=1e-8)
        assert ref.rm_at(egg, RM1_PAIR, method="LSODA")[0] == pytest.approx(rm1, rel=1e-8)
        return value

    return em


def test_the_search_finds_the_crossing_on_a_synthetic_cell(em_at):
    f_true = 0.02
    target = em_at(f_true)
    lo, hi = em_at(0.01), em_at(0.03)
    assert (lo - target) * (hi - target) < 0.0  # the registered bracket holds the crossing
    assert abs(hi - lo) > 1e-4  # f moves Em at 'J1' on this cell: the search is not vacuous
    f, log = comb.calibrate_fraction(em_at, target)
    assert f == pytest.approx(f_true, abs=1e-6)
    assert em_at(f) == pytest.approx(target, abs=1e-9)
    assert len({entry["f"] for entry in log}) == len(log)  # each f evaluated once


def line(f):
    """A cheap monotone stand-in for Em at J1 (V) against f."""
    return -0.0099 - 0.37 * f


def test_the_search_widens_to_f_end_when_the_bracket_misses():
    calls = []

    def f_end():
        calls.append(1)
        return 0.0728

    f, log = comb.calibrate_fraction(line, line(0.05), f_end=f_end)
    assert f == pytest.approx(0.05, abs=1e-8)
    assert calls == [1]  # computed once, and only because the bracket missed
    assert {0.01, 0.03, 0.0, 0.0728} <= {entry["f"] for entry in log}


def test_f_end_is_not_computed_when_the_bracket_holds_the_crossing():
    f, _ = comb.calibrate_fraction(line, line(0.02), f_end=lambda: pytest.fail("computed"))
    assert f == pytest.approx(0.02, abs=1e-8)


def test_no_crossing_in_zero_to_f_end_gives_none():
    f, log = comb.calibrate_fraction(line, line(0.2), f_end=0.0728)
    assert f is None
    assert len(log) == 4


def test_a_sealed_egg_keeps_its_access():
    rm1 = ref.rm_at(cell(), RM1_PAIR, method="LSODA")[0]
    sealed = cell(bath_fraction=0.3, a_over_l_m=0.0)
    _, egg = comb.recalibrated_em(
        sealed,
        rm1_ohm=rm1,
        rm2_ohm=1.0,  # unreachable on purpose: a sealed egg must not be calibrated on it
        rm1_pair=RM1_PAIR,
        j1_pair=J1_PAIR,
        em_pulse=J1_PAIR[1],
        guess=1e-7,
    )
    assert egg.a_over_l_m == 0.0
    assert egg == replace(sealed, p_old=egg.p_old)
