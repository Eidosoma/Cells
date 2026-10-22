"""Independent high-precision bounds and faults that an allowance must not hide."""

import copy
import json
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest

from tests.unit import test_betse_spatial_trajectory as common
from validation.betse.spatial_active import gate_roundoff as check
from validation.betse.spatial_active import junction_runtime, mixed_interventions, refinement


def decimal_replay(voltage, initial, dt):
    """80-digit continuous-V/s law, using increment form rather than weighted sums."""
    with localcontext() as context:
        context.prec = 80

        def d(value):
            return Decimal.from_float(float(value))

        gate = [[d(v) for v in row] for row in initial]
        history = []
        for row in voltage:
            for i, (offset, width, intercept, slope, sign) in enumerate(
                (
                    ("0.006", "0.0064", "0.008330", "0.1163", -1),
                    ("0.0253", "0.0035", "1.620000", "15.500", 1),
                )
            ):
                for j, value in enumerate(row):
                    v = d(value)
                    target = 1 / (1 + (sign * (v + Decimal(offset)) / Decimal(width)).exp())
                    tau = Decimal(intercept) - Decimal(slope) * v
                    gate[i][j] += (target - gate[i][j]) * d(dt) / (tau + d(dt))
            history.append([row.copy() for row in gate])
        return np.asarray(history, dtype=object)


def test_host_gate_bound_known_answers():
    initial = np.array([[0.0, 1.0], [0.6, 0.2]])
    ramp = np.column_stack((np.linspace(-0.110, 0.050, 24), np.linspace(0.050, -0.110, 24)))
    histories = (
        (np.full_like(ramp, -0.030), np.full_like(ramp, -0.030)),
        (ramp, ramp + np.array([2e-12, -3e-12])),
        (ramp, ramp + 0.008 * np.sin(np.arange(24))[:, None]),
    )
    cases = scalars = 0
    largest_ratio = 0.0
    for dt in (0.25e-6, 1e-6, 1e-3):
        for left, right in histories:
            a, b = (decimal_replay(v, initial, dt) for v in (left, right))
            # Subtract before rounding to float, so tiny true differences are
            # not manufactured by subtracting two already-rounded gate values.
            with localcontext() as context:
                context.prec = 80
                delta = np.asarray(abs(a - b), dtype=float)
            bound = check.voltage_allowance(left, right, dt)
            assert np.all(delta <= bound)
            if np.array_equal(left, right):
                np.testing.assert_array_equal(bound, np.zeros_like(bound))
            else:
                ratio = np.divide(delta, bound, out=np.zeros_like(delta), where=bound > 0)
                largest_ratio = max(largest_ratio, float(np.max(ratio)))
            for voltage, target in ((left, a), (right, b)):
                np.testing.assert_allclose(
                    check.replay(voltage, initial, dt),
                    np.asarray(target, dtype=float),
                    atol=2e-13,
                    rtol=2e-12,
                )
            cases += 1
            scalars += delta.size
    common.evidence(
        "mixed-gate-known-answers",
        dict(
            status="passed",
            decimal_digits=80,
            paired_histories=cases,
            bound_scalars=scalars,
            max_exact_difference_over_bound=largest_ratio,
            zero_input_difference_zero_allowance=True,
            includes_large_voltage_and_timestep_changes=True,
        ),
    )


def test_host_gate_bound_negative_inputs():
    voltage = np.full((8, 2), -0.030)
    invalid = (
        np.full_like(voltage, np.nan),
        np.full_like(voltage, 0.061),
        np.full_like(voltage, -0.121),
        voltage.astype(np.float32),
        voltage[:0],
    )
    rejected = 0
    for bad in invalid:
        with pytest.raises(ValueError):
            check.voltage_allowance(bad, voltage, 1e-6)
        rejected += 1
    for dt in (0, -1e-6, float("nan")):
        with pytest.raises(ValueError):
            check.voltage_allowance(voltage, voltage, dt)
        rejected += 1
    with pytest.raises(ValueError, match="shapes"):
        check.voltage_allowance(voltage, voltage[:-1], 1e-6)
    rejected += 1
    for bad in (np.ones((1, 2)), -np.ones_like(voltage), np.full_like(voltage, np.inf)):
        with pytest.raises(AssertionError):
            check.addition(dict(m_gate=bad, h_gate=voltage), "m_gate", voltage)
        rejected += 1
    with pytest.raises(AssertionError, match="fields"):
        check.addition(dict(junction_open=voltage), "m_gate", voltage)
    with pytest.raises(ValueError, match="initial"):
        check.replay(voltage, np.full((2, 2), 1.01), 1e-6)
    common.evidence(
        "mixed-gate-negative-inputs",
        dict(
            status="passed",
            rejected=rejected + 2,
            invalid_domain_clock_precision_shape_and_allowance_rejected=True,
        ),
    )


@pytest.fixture(scope="module")
def archived():
    rule = mixed_interventions.protocol()
    binding = rule["gate_comparison"]["regression_binding"]
    path = Path(binding["root"])
    assert refinement.digest(path / "closeout.json") == binding["closeout_sha256"]
    receipt = json.loads((path / "closeout.json").read_text())
    assert (
        receipt["status"] == "diagnostic_completed" and not receipt["native_qualification_passed"]
    )
    native, rows = mixed_interventions.native_capture()
    key = "regional/step-0/observed"
    with np.load(native / key / "trace.npz", allow_pickle=False) as archive:
        trace = dict(archive)
    actual = {}
    for backend, filename in binding["arrays"].items():
        target = Path(filename)
        assert refinement.digest(target) == receipt["evidence_sha256"][filename]
        with np.load(target, allow_pickle=False) as archive:
            actual[backend] = dict(archive)
    return rows[key], trace, actual, rule["tolerances"]


def test_host_gate_saved_regression(archived):
    row, trace, saved, tol = archived
    reports = {}
    for backend, actual in saved.items():
        allowance, report, _ = check.check(row, trace, actual, tol)
        assert report["gates"]["m_gate"]["original_violations"] == 604
        assert report["gates"]["m_gate"]["original_max_error_over_budget"] > 1
        states = {k: v[1:] for k, v in actual.items() if not k.startswith("rate__")}
        with pytest.raises(AssertionError, match="active__m_gate"):
            junction_runtime.compare_native(states, row, trace)
        compared = junction_runtime.compare_native(states, row, trace, gate_allowance=allowance)
        assert compared["fields"]["active__m_gate"]["original_violations"] == 604
        reports[backend] = report
    common.evidence(
        "mixed-gate-saved-regression",
        dict(
            status="passed",
            reports=reports,
            scope="Archived failed case, not independent biology or a fresh qualification",
            default_strict_comparison_still_rejects=True,
        ),
    )


def test_host_gate_faults_cannot_hide_in_allowance(archived):
    row, trace, saved, tol = archived
    actual = saved["cpu"]
    _, _, values = check.check(row, trace, actual, tol)
    native_after = np.flatnonzero((trace["method"] == 4) & trace["after"])
    where = np.unravel_index(
        np.argmax(values["voltage_allowance"]), values["voltage_allowance"].shape
    )
    step, gate, patch = where
    name = check.NAMES[gate]
    original = trace[name][native_after[step], patch]
    replay = values["cells_replay"][where]
    budget = values["original_budget"][where] + values["voltage_allowance"][where]
    choices = [original + sign * 0.9 * budget for sign in (-1, 1)]
    corrupted = max(choices, key=lambda v: abs(v - replay))
    assert abs(corrupted - original) <= budget
    assert abs(corrupted - replay) > tol["gate_atol"] + tol["gate_rtol"] * abs(replay)
    bad = copy.deepcopy(actual)
    bad["active__" + name][step + 1, patch] = corrupted
    with pytest.raises(AssertionError, match="cells kinetic replay"):
        check.check(row, trace, bad, tol)
    bad = copy.deepcopy(actual)
    bad["observed__vm"][0, 0] += 1e-8
    with pytest.raises(AssertionError, match="gate input voltage"):
        check.check(row, trace, bad, tol)
    bad = copy.deepcopy(actual)
    initial = np.stack([trace["initial_" + name] for name in check.NAMES])
    wrong_clock = check.replay(values["cells_voltage_V"], initial, row["dt_s"] / 2)
    for i, name in enumerate(check.NAMES):
        bad["active__" + name][1:] = wrong_clock[:, i]
    with pytest.raises(AssertionError, match="cells kinetic replay"):
        check.check(row, trace, bad, tol)
    common.evidence(
        "mixed-gate-fault-rejection",
        dict(
            status="passed",
            rejected=3,
            gate_fault_inside_expanded_budget_rejected_by_kinetic_replay=True,
            wrong_voltage_rejected=True,
            wrong_clock_rejected=True,
        ),
    )
