"""FR-8 stage 0's M2, M4 and M5 judges (validation/long_duration/m2_spectrum.py, m4_settling.py,
m5_energy.py; REGISTRATION_20261118.md §4, §6, §7 and §8). Each claim with its plant, on synthetic
values (no engine run):

- M2: the declared split separates a spectrum with a gap, and reports a spectrum without one,
  or whose fast part does not match the fast mode's spectrum, as not separated;
- M4: the settling time is the first row from which the trace stays inside for the hold, and a
  re-crossing inside the hold moves it; a trace that never settles, or that ends inside the hold,
  gives None;
- M5: a residual at 1.01 times its bound gives rho above 1, and the order and extrapolated
  binding step of a second-order sequence are recovered.
"""

import math

import numpy as np
import pytest

from validation.long_duration import m2_spectrum as m2
from validation.long_duration import m4_settling as m4
from validation.long_duration import m5_energy as m5


def test_the_split_separates_a_spectrum_with_a_gap_and_not_one_without():
    full = [-6804.0, -1159.0, -140.0, -3.87 + 0.78j, -3.87 - 0.78j, -1 / 219, -1 / 5500]
    fast = [-6800.0, -1160.0, -140.5, -3.9 + 0.8j, -3.9 - 0.8j]
    verdict = m2.split(full, fast, 0.1, 0.1)
    assert verdict["separated"] and verdict["n_fast"] == 5
    assert verdict["h_r1_s"] == pytest.approx(219.0)
    assert verdict["epsilon"] == pytest.approx((1 / 219) / abs(-3.87 + 0.78j))
    no_gap = [-10.0, -5.0, -2.0, -1.0]
    assert not m2.split(no_gap, [-10.0, -5.0], 0.1, 0.1)["separated"]  # eps = 0.4.
    mismatched = [-6804.0, -1159.0, -1 / 219]
    assert not m2.split(mismatched, [-6804.0, -500.0], 0.1, 0.1)["separated"]


def test_the_settling_time_and_a_re_crossing_inside_the_hold():
    t = np.round(np.arange(0.0, 30.001, 0.5), 6)
    rate = np.where(t < 8.0, 1.0, 1e-6)
    gate = np.zeros_like(t)
    assert m4.settling_time(t, rate, gate, 1e-3, 1e-3, 5.0, 10.0, 20.0) == 8.0
    short = t <= 8.5  # Planted: the trace ends one row after 8 s, inside its hold.
    assert m4.settling_time(t[short], rate[short], gate[short], 1e-3, 1e-3, 5.0, 10.0, 20.0) is None
    rate[t == 12.0] = 1.0  # A re-crossing inside the hold: settling moves past it.
    assert m4.settling_time(t, rate, gate, 1e-3, 1e-3, 5.0, 10.0, 20.0) == 12.5
    gate[:] = 1.0  # The gate never settles.
    assert m4.settling_time(t, rate, gate, 1e-3, 1e-3, 5.0, 10.0, 20.0) is None


def test_rho_over_one_and_the_order_and_binding_step():
    assert m5.ratio(1.01e-6, 1e-6) > 1.0 and m5.ratio(-1.01e-6, 1e-6) > 1.0
    assert m5.ratio(0.99e-6, 1e-6) < 1.0
    p = m5.order(2e-3, 0.4, 1e-3, 0.1)
    assert p == pytest.approx(2.0)
    binding = 2e-3 * (1 / 0.4) ** (1 / p)
    assert binding == pytest.approx(2e-3 * math.sqrt(2.5))
