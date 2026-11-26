"""The step's control reaches a kind's book (docs/INNER_MODEL_V4_DESIGN.md §7.4 (l) 5).

tests/kind_fixtures.py's `tests.kind.relaxation@1` is FR-5's damage law in miniature
(laws/transport/patch_damage.py): per cell, dd/dt = k_inj u_inj(t) (1 - d) - k_res u_res(t) d, with u_inj
and u_res piecewise-constant schedules. Its book replaces d with the law's exact step at the step's
held control. With the schedules' breakpoints on the step grid (an off-nominal one inserted), d
matches its closed form at every step boundary to rounding: injury on from 1 ms, then off and
resealing on from 2.5 ms. Left to the tableau alone (no book), the same run does not.
"""  # noqa: E501

import math

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry import kind_registry
from tests import kind_fixtures as kf
from validation.tissue import pump_water_fixtures as water_fixtures

INJURY, RESEALING = 500.0, 300.0  # 1/s: (a + b) dt up to 0.5 at 1 ms, so the tableau's error shows.
SCHEDULE = {
    "injury": ((0.0, 0.0), (0.001, 1.0), (0.0025, 0.0)),
    "resealing": ((0.0, 0.0), (0.0025, 1.0)),
}
GRID = (0.0, 0.001, 0.002, 0.0025, 0.003, 0.004)


def closed_form(t):
    """d(t) from d(0) = 0: 0 to 1 ms; toward 1 at INJURY to 2.5 ms; then toward 0 at RESEALING."""
    if t <= 0.001:
        return 0.0
    if t <= 0.0025:
        return -math.expm1(-INJURY * (t - 0.001))
    return -math.expm1(-INJURY * 0.0015) * math.exp(-RESEALING * (t - 0.0025))


def relaxation_run(*, booked):
    raw = water_fixtures.heredity_cell("D", end_time=0.004, observation_times=list(GRID))
    raw = kf.declare_relaxation(raw, injury=INJURY, resealing=RESEALING, schedule=SCHEDULE)
    with kind_registry.scope(kf.registry(kf.relaxation(booked=booked))):
        spec = parse_spec(raw)
        return run(spec)


def test_a_relaxation_booked_at_the_steps_control_is_exact_across_breakpoints():
    result = relaxation_run(booked=True)
    assert tuple(result.times) == GRID  # 0.0025 inserted exactly.
    d = np.asarray(result.observations.relaxation_damage)[:, 0]
    expected = [closed_form(t) for t in GRID]
    assert d[0] == d[1] == 0.0
    for got, want in zip(d[2:], expected[2:], strict=True):
        assert got == pytest.approx(want, rel=1e-13)
    per_cell = np.asarray(result.observations.relaxation_damage)  # Every cell alike.
    assert np.all(per_cell == per_cell[:, :1])


def test_left_to_the_tableau_the_same_relaxation_is_not_exact():
    d = np.asarray(relaxation_run(booked=False).observations.relaxation_damage)[:, 0]
    errors = [
        abs(got - closed_form(t)) / closed_form(t) for got, t in zip(d[2:], GRID[2:], strict=True)
    ]
    assert max(errors) > 1e-4  # ARS(2,2,2) on (a + b) dt = 0.5: the book is what makes it exact.
