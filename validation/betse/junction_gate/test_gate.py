"""Physical-time rate checks and explicit rejection of native-semantics conflation."""

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from cells.processes import junction_gate as gate

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check as panel_check  # noqa: E402
import compatibility  # noqa: E402
import reference  # noqa: E402


@pytest.mark.parametrize("threshold", [0.0, 0.015, 0.06, 0.12])
@pytest.mark.parametrize("minimum", [0.0, 0.1, 0.4, 1.0])
def test_rates_and_clamped_steps_match_independent_reference(threshold, minimum):
    voltage = np.linspace(-0.12, 0.12, 25)
    params = gate.Parameters(threshold, minimum)
    initial = np.full(voltage.shape, minimum + 0.3 * (1 - minimum))
    rate = gate.kinetics(voltage, params, xp=np)
    alpha, beta = reference.rates(voltage, threshold)
    np.testing.assert_allclose(rate.alpha_per_s, alpha, rtol=4e-15, atol=2e-13)
    np.testing.assert_allclose(rate.beta_per_s, beta, rtol=4e-15, atol=2e-14)
    for duration in (0.0, 1e-6, 0.01, 0.25, 1.0):
        actual = gate.advance_clamped(initial, voltage, params, duration, xp=np)
        expected = reference.solution(initial, voltage, threshold, minimum, duration)
        np.testing.assert_allclose(actual, expected, rtol=0, atol=5e-15)
        assert np.all(gate.domain_valid(actual, voltage, params, 1.0, duration, xp=np))
    np.testing.assert_array_equal(gate.kinetics(-voltage, params, xp=np).target, rate.target)
    # Both ends of the intrinsic-conductance domain point inward.
    assert np.all(gate.rhs(np.full_like(voltage, minimum), voltage, params, xp=np) >= 0)
    assert np.all(gate.rhs(np.ones_like(voltage), voltage, params, xp=np) <= 0)


def test_physical_blocking_preserves_hidden_state_and_source_adapter_does_not():
    params = gate.Parameters(0.015, 0.1)
    initial = np.asarray([0.2, 0.9])
    voltage = np.asarray([0.0, 0.12])
    hidden = gate.advance_clamped(initial, voltage, params, 0.25, xp=np)
    np.testing.assert_array_equal(gate.open_fraction(hidden, 0.0), 0.0)
    np.testing.assert_array_equal(gate.open_fraction(hidden, 1.0), hidden)
    np.testing.assert_array_equal(compatibility.step(initial, voltage, 0.0, 0.001, params), 0.0)
    assert np.max(np.abs(hidden - initial)) > 0.05
    assert not np.all(gate.domain_valid(np.zeros(2), voltage, params, 0.0, xp=np))


def test_source_class_initialization_is_not_physical_preparation():
    params = gate.Parameters(0.015, 0.1)
    class_state = compatibility.class_initialization(np.asarray([0.0]), 1.0, params)
    assert class_state[0] > 1.0
    assert not gate.domain_valid(class_state, 0.0, params, 1.0, xp=np)[0]
    assert gate.kinetics(np.asarray([0.0]), params, xp=np).target[0] <= 1.0


@pytest.mark.parametrize(
    "field,value",
    [
        ("gate", np.nextafter(0.1, 0.0)),
        ("gate", np.nextafter(1.0, 2.0)),
        ("gate", np.nan),
        ("voltage", 0.121),
        ("voltage", np.inf),
        ("threshold", -0.001),
        ("threshold", 0.121),
        ("minimum", -0.1),
        ("minimum", 1.1),
        ("availability", -0.1),
        ("availability", 1.1),
        ("dt", -1e-6),
        ("dt", np.nan),
    ],
)
def test_domain_rejection_never_repairs_a_blocked_route(field, value):
    values = dict(gate=0.5, voltage=0.0, threshold=0.015, minimum=0.1, availability=0.0, dt=0.001)
    values[field] = value
    assert not gate.domain_valid(
        values["gate"],
        values["voltage"],
        gate.Parameters(values["threshold"], values["minimum"]),
        values["availability"],
        values["dt"],
        xp=np,
    )


def test_independent_ode_and_clamp_semigroup():
    voltage = np.asarray([-0.12, 0.0, 0.12])
    initial = np.asarray([0.1, 0.3, 1.0])
    params = gate.Parameters(0.015, 0.1)
    times = np.linspace(0, 0.25, 51)
    answer = reference.ode(initial, voltage, *params, 0.25)
    expected = reference.solution(initial, voltage, *params, times)
    np.testing.assert_allclose(answer.sol(times).T, expected, rtol=0, atol=5e-12)
    one = gate.advance_clamped(initial, voltage, params, 0.25, xp=np)
    halves = gate.advance_clamped(
        gate.advance_clamped(initial, voltage, params, 0.125, xp=np), voltage, params, 0.125, xp=np
    )
    np.testing.assert_allclose(one, halves, rtol=0, atol=3e-16)
    np.testing.assert_array_equal(initial, [0.1, 0.3, 1.0])
    np.testing.assert_array_equal(voltage, [-0.12, 0.0, 0.12])


def test_registered_heterogeneous_dense_reference_and_half_step_refinement(tmp_path):
    protocol = json.loads(Path(__file__).with_name("protocol.json").read_text())
    value, voltage, params = panel_check.device_inputs(protocol)
    reports = []
    for phase in protocol["phases"]:
        v, duration = voltage * phase["voltage_multiplier"], phase["duration_s"]
        answer = reference.ode(value, v, *params, duration)
        a, b = reference.rates(v, params.threshold_voltage_V)
        # Separate finer solve checks the adopted fastest-relaxation step cap.
        fine = solve_ivp(
            lambda t, y, a=a, b=b: a * (1 - y) - b * (y - params.minimum_open_fraction),
            (0, duration),
            value,
            method="DOP853",
            rtol=5e-14,
            atol=5e-16,
            max_step=min(duration / 40, 1 / (16 * np.max(a + b))),
            dense_output=True,
        )
        assert fine.success
        times = np.linspace(0, duration, 201)
        exact = reference.solution(value, v, *params, times)
        reports.append(
            {
                "default_error": float(np.max(np.abs(answer.sol(times).T - exact))),
                "refined_error": float(np.max(np.abs(fine.sol(times).T - exact))),
                "refinement_disagreement": float(
                    np.max(np.abs(answer.sol(times) - fine.sol(times)))
                ),
            }
        )
        value = exact[-1]
    (tmp_path / "heterogeneous-reference-refinement.json").write_text(json.dumps(reports, indent=2))
    assert all(
        error <= protocol["tolerances"]["physical_gate_atol"]
        for row in reports
        for error in row.values()
    )


def test_reference_failure_retains_numeric_evidence(tmp_path, monkeypatch):
    protocol = json.loads(Path(__file__).with_name("protocol.json").read_text())
    original = reference.ode

    def corrupted(*args, **kwargs):
        answer = original(*args, **kwargs)
        interpolate = answer.sol
        answer.sol = lambda times: interpolate(times) + 1e-6
        return answer

    monkeypatch.setattr(reference, "ode", corrupted)
    with pytest.raises(ValueError, match="Independent ODE disagreement"):
        panel_check.physical_reference(tmp_path, protocol)
    evidence = json.loads((tmp_path / "reference-checks.json").read_text())
    assert evidence["atol"] == protocol["tolerances"]["physical_gate_atol"]
    assert len(evidence["phases"]) == len(protocol["phases"])
    assert all(row["max_error"] > 9e-7 for row in evidence["phases"])
    assert (tmp_path / "reference.npz").is_file()


def test_registered_native_ladder_resolves_analytic_unblocked_clamp(tmp_path):
    protocol = json.loads(Path(__file__).with_name("protocol.json").read_text())
    voltage = np.repeat(protocol["voltages_V"], len(protocol["initial_gates"]))
    initial = np.tile(protocol["initial_gates"], len(protocol["voltages_V"]))
    a, b = reference.rates(voltage, protocol["threshold_voltage_V"])
    target = (a + b * protocol["minimum_open_fraction"]) / (a + b)
    reports = {}
    for calls in protocol["calls_per_outer_step"]:
        errors = []
        for dt in protocol["native_steps_s"]:
            steps = np.arange(round(protocol["phases"][0]["duration_s"] / dt) + 1)
            # Closed form for repeated backward-Euler steps, independent of
            # the implementation and the source adapter's update function.
            discrete = target + (initial - target) * (1 + dt * (a + b)) ** (-calls * steps[:, None])
            continuous = reference.solution(
                initial,
                voltage,
                protocol["threshold_voltage_V"],
                protocol["minimum_open_fraction"],
                steps * dt,
                clock=calls,
            )
            errors.append(float(np.max(np.abs(discrete - continuous))))
        assert errors[-1] <= protocol["tolerances"]["native_finest_gate_atol"]
        assert all(
            f <= protocol["tolerances"]["native_refinement_ratio_max"] * c
            for c, f in zip(errors[:-1], errors[1:], strict=True)
        )
        reports[calls] = errors
    (tmp_path / "predicted_native_clamp_errors.json").write_text(json.dumps(reports, indent=2))


def test_compatibility_adapter_matches_existing_unmodified_native_primitives():
    folder = os.environ.get("CELLS_JUNCTION_GATE_LIFECYCLE")
    if not folder:
        pytest.skip("Requires the completed native lifecycle panel")
    root = Path(folder)
    path = root / "native/panel.json"
    with path.open("rb") as handle:
        assert (
            hashlib.file_digest(handle, "sha256").hexdigest()
            == json.loads((root / "result.json").read_text())["native_panel_sha256"]
        )
    panel = json.loads(path.read_text())
    p = panel["protocol"]
    params = gate.Parameters(p["gj_vthresh_mV"] / 1000, p["gj_min"])
    voltage = np.asarray(p["probe_voltage_V"])
    compared = 0
    for row in panel["primitives"]:
        if row["class"] != "Gap_Junction":
            continue
        np.testing.assert_allclose(
            row["class_after_init"],
            compatibility.class_initialization(voltage, 1.0, params),
            rtol=2e-13,
            atol=5e-14,
        )
        np.testing.assert_array_equal(row["sim_after_init"], row["initial_gate"])
        for update in row["updates"]:
            actual = compatibility.step(
                np.asarray(update["before"]), voltage, update["block"], row["dt_s"], params
            )
            np.testing.assert_allclose(actual, update["after"], rtol=2e-13, atol=5e-14)
            compared += len(actual)
    assert compared == 378
