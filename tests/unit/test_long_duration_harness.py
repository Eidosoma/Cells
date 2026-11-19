"""FR-8 stage 0's harness judge (validation/long_duration/harness_judge.py;
validation/long_duration/REGISTRATION_20261118.md §5.3 and §8). Each claim with its plant, on
synthetic rows (no engine run):

- the budget judge passes rows at the budget and fails one entry at 1.01 x its budget, for each
  class and for the histories;
- the crossing locator finds a known linear crossing within 1e-9 s, with its direction;
- the timing verdict passes a 0.4 ms difference and fails a planted 1 ms shift, and fails when one
  run has a crossing the other has not, or a crossing located between rows sparser than 1 ms;
- the recovery time is the first row from which the trace stays inside, and a re-exit inside the
  window moves it;
- the observed order of a second-order sequence is 2;
- (amendment 3) the judge refuses a run compared with itself, arms out of order, a wrong step and
  mixed snapshots, and its error estimates on the 16:4:1 sequence are R2's 4 and R3's 1.
"""

import numpy as np
import pytest

from validation.long_duration import harness_judge as hj

TIMES = np.linspace(0.0, 10.0, 11)


@pytest.mark.parametrize(
    "kind,budget", [("voltage", 2e-6), ("concentration", 2e-5), ("gate", 1e-5)]
)
def test_each_class_fails_one_entry_just_over_its_budget(kind, budget):
    ref = np.full((11, 2, 3), 5.0)
    scale = 5.0 if kind == "concentration" else 1.0
    at_budget = ref + 0.999 * budget * scale
    assert hj.judge_class(at_budget, ref, kind, budget, TIMES)["passed"]
    planted = at_budget.copy()
    planted[7, 1, 2] = ref[7, 1, 2] + 1.01 * budget * scale
    verdict = hj.judge_class(planted, ref, kind, budget, TIMES)
    assert not verdict["passed"] and verdict["row_time_s"] == 7.0


def test_the_response_window_ignores_rows_before_the_cue():
    ref = np.zeros((11, 1))
    test = ref.copy()
    test[2, 0] = 1.0  # Before the cue at 5 s: outside the response window.
    assert hj.judge_class(test, ref, "voltage", 1e-6, TIMES, after=5.0)["passed"]
    test[6, 0] = 1.0
    assert not hj.judge_class(test, ref, "voltage", 1e-6, TIMES, after=5.0)["passed"]


def test_a_history_entry_just_over_its_relative_budget_fails():
    floors = dict(amount_fmol=1e-10, energy_pJ=2e-8, charge_C=3e-25)
    ref = {
        "membrane_transferred": np.full((11, 4), 3.0),
        "pump_dissipated_energy_pJ": np.ones((11, 2)),
    }
    test = {k: v * (1 + 0.999 * 2e-5) for k, v in ref.items()}
    assert hj.judge_histories(test, ref, 2e-5, floors)["passed"]
    test["pump_dissipated_energy_pJ"][4, 1] = 1 + 1.01 * 2e-5
    verdict = hj.judge_histories(test, ref, 2e-5, floors)
    assert not verdict["passed"]
    assert not verdict["fields"]["pump_dissipated_energy_pJ"]["passed"]
    assert hj.floor_of("electrode_charge_transferred_C", floors) == 3e-25


def test_the_crossing_locator_finds_a_known_crossing():
    t = np.linspace(1800.0, 1801.0, 1001)
    v = -0.07 + 0.04 * (t - 1800.0)  # Crosses -0.05 V at 1800.5 s, upward.
    found = hj.crossings(t, v, -0.05, 1800.0)
    assert len(found) == 1 and found[0]["direction"] == "up"
    assert abs(found[0]["time_s"] - 1800.5) < 1e-9


def test_the_timing_verdict_fails_a_planted_shift_and_a_missing_crossing():
    def at(*times, spacing=1.0000000002e-3):  # 1 ms rows, as float labels near 1800 s read them.
        directions = ("up", "down")[: len(times)]
        pairs = zip(times, directions, strict=True)
        return [dict(time_s=t, direction=d, spacing_s=spacing) for t, d in pairs]

    rows = hj.CROSSING_ROW_SPACING_S
    ref = at(1800.5, 1801.2)
    assert hj.timing_verdict(at(1800.5004, 1801.2), ref, 5e-4, rows)["passed"]
    assert not hj.timing_verdict(at(1800.501, 1801.2), ref, 5e-4, rows)["passed"]
    assert not hj.timing_verdict(ref[:1], ref, 5e-4, rows)["passed"]
    # Planted: the same times located between 10 ms rows take no 0.5 ms timing pass.
    assert not hj.timing_verdict(at(1800.5, 1801.2, spacing=1e-2), ref, 5e-4, rows)["passed"]


def test_the_recovery_time_and_a_re_exit():
    t = np.arange(0.0, 31.0)
    v = np.where(t < 10, 1.0, 0.0)
    assert hj.recovery_time(t, v, 0.0, 0.1, 0.5, 30.0) == 10.0
    v[20] = 1.0  # A re-exit inside the window moves the recovery to the row after it.
    assert hj.recovery_time(t, v, 0.0, 0.1, 0.5, 30.0) == 21.0
    v[30] = 1.0  # Outside at the window's last row: no recovery.
    assert hj.recovery_time(t, v, 0.0, 0.1, 0.5, 30.0) is None


def test_the_observed_order_of_a_second_order_sequence():
    assert hj.observed_order(4e-6, 1e-6) == pytest.approx(2.0)
    assert hj.observed_order(0.0, 1e-6) is None


REG = dict(arms_dt_s=dict(R1=1e-3, R2=5e-4, R3=2.5e-4))


def arm_record(arm, dt, revision="rev", registration="fr8-stage0-20261118"):
    return dict(arm=arm, dt_s=dt, snapshot_revision=revision, registration=registration)


def test_the_judge_refuses_a_run_compared_with_itself_or_out_of_order():
    dirs = ["/runs/R1", "/runs/R2", "/runs/R3"]
    good = [arm_record("R1", 1e-3), arm_record("R2", 5e-4), arm_record("R3", 2.5e-4)]
    hj.check_arms(dirs, good, REG)  # The registered order passes, and R1 with R2 alone.
    hj.check_arms(dirs[:2], good[:2], REG)
    refused = [
        ([dirs[0], dirs[0]], [good[0], good[0]]),  # [R1, R1]: a run compared with itself.
        ([dirs[0], dirs[1]], [good[0], good[0]]),  # R1's record twice, from two directories.
        ([dirs[1], dirs[0]], [good[1], good[0]]),  # [R2, R1]: out of order.
        (dirs, [good[0], arm_record("R2", 2.5e-4), good[2]]),  # A step not R2's.
        (dirs, [good[0], good[1], arm_record("R3", 2.5e-4, revision="other")]),  # Two snapshots.
        ([dirs[0], dirs[0], dirs[2]], good),  # Distinct names, one directory twice.
    ]
    for directories, records in refused:
        with pytest.raises(ValueError):
            hj.check_arms(directories, records, REG)


def test_the_error_estimates_on_a_16_4_1_sequence():
    t = np.arange(5, dtype=float)
    arms = []
    for error in (16.0, 4.0, 1.0):  # C h^2 at h = 4u, 2u, u, with z* = 1.
        z = np.full((5, 3), 1.0 + error * 1e-6)
        classes = dict(voltage=z, concentration=np.full((5, 3), 1.0), gate=z)
        arms.append(({}, t, classes, {}, np.zeros(5)))
    end = hj.orders(arms, (1.5, 2.5))["voltage"]["end_row"]
    assert end["p"] == pytest.approx(2.0) and end["inside_window"]
    assert end["r2_error_estimate"] == pytest.approx(4e-6)  # R2's own error.
    assert end["r3_error_estimate"] == pytest.approx(1e-6)  # The old expression: R3's.
    assert hj.error_estimates(3e-6, 2.0) == pytest.approx((4e-6, 1e-6))
