"""Independent HCN source laws, unused state, and distinct physical/native clocks.

No production imports. Set CELLS_HCN_EXTRA_NATIVE to an unchanged-source capture
to include the pinned-source checks. The standalone supervisor supplies it.
"""

import ast
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

from validation.channels import hcn_extra_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "validation/channels/hcn_extra_protocol.json"
PROTOCOL = json.loads(PROTOCOL_PATH.read_text())
CLASSES = reference.CLASSES
TOL = PROTOCOL["tolerances"]


def evidence(name, report):
    if directory := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        (target / (name + ".json")).write_text(
            json.dumps(report, indent=2, allow_nan=False, default=lambda value: value.tolist())
            + "\n"
        )


def close(actual, expected):
    np.testing.assert_allclose(
        actual, expected, rtol=TOL["native_gate_relative"], atol=TOL["native_gate_absolute"]
    )


@pytest.fixture(scope="module")
def native():
    filename = os.environ.get("CELLS_HCN_EXTRA_NATIVE")
    if filename is None:
        pytest.skip("Pinned native capture supplied by the independent source-check runner")
    return json.loads(Path(filename).read_text())


def test_scalar_oracle_is_independent_and_protocol_declares_scope():
    imports = [
        node
        for node in ast.walk(ast.parse(Path(reference.__file__).read_text()))
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert all(
        isinstance(node, ast.ImportFrom) and node.module in {"decimal", "numbers"}
        for node in imports
    )
    assert tuple(PROTOCOL["classes"]) == CLASSES
    assert "backward Euler" in PROTOCOL["native_clock"]
    assert any("whole-tissue" in value for value in PROTOCOL["scientific_limits"])


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("voltage", [-0.120, -0.080, -0.079, -0.076, 0.0, 0.060])
def test_domain_rates_opening_and_exact_initialization(name, voltage):
    target, tau = reference.kinetics(voltage, name)
    assert all(0 <= value <= 1 for value in target)
    assert all(value > 0 for value in tau)
    np.testing.assert_array_equal(tau, PROTOCOL["source_contracts"][name]["tau_s"])
    initial = reference.initial_gates(voltage, name)
    assert initial[1] == target[1] == 1
    if name != "HCN4_cAMP":
        np.testing.assert_array_equal(initial, target)
    else:
        assert initial[0] < target[0]
    np.testing.assert_array_equal(reference.relaxation(initial, voltage, name, 0), initial)
    np.testing.assert_array_equal(reference.backward_euler(initial, voltage, name, 0), initial)
    close(
        reference.rhs([0.2, 0.7], voltage, name), (np.asarray(target) - np.array([0.2, 0.7])) / tau
    )
    assert reference.opening([0.2, 0.7], name) == (1 if name == "HCNLeak" else 0.2)


@pytest.mark.parametrize("name,midpoint", [("HCN2_cAMP", -0.079), ("HCN4_cAMP", -0.076)])
def test_sigmoid_midpoint_symmetry_and_hyperpolarizing_sign(name, midpoint):
    assert reference.kinetics(midpoint, name)[0][0] == 0.5
    lower = reference.kinetics(midpoint - 0.010, name)[0][0]
    higher = reference.kinetics(midpoint + 0.010, name)[0][0]
    assert lower > 0.5 > higher
    close(lower + higher, 1)


def test_hcn4_source_initialization_is_not_the_update_equilibrium():
    assert reference.initial_gates(-0.080, "HCN4_cAMP")[0] == 0.5
    initial = reference.initial_gates(-0.080, "HCN4_cAMP")
    target, _ = reference.kinetics(-0.080, "HCN4_cAMP")
    assert target[0] > 0.60
    assert reference.rhs(initial, -0.080, "HCN4_cAMP")[0] > 0
    assert reference.backward_euler(initial, -0.080, "HCN4_cAMP", 0.001)[0] > initial[0]


@pytest.mark.parametrize("name", CLASSES)
def test_unused_h_and_leak_gate_clocks_are_explicit_but_do_not_change_opening(name):
    for m in (0.0, 0.2, 1.0):
        assert reference.opening([m, 0], name) == reference.opening([m, 1], name)
    if name == "HCNLeak":
        assert reference.opening([0, 0], name) == reference.opening([1, 1], name) == 1
        np.testing.assert_array_equal(reference.rhs([0, 0], -0.080, name), [1, 1])
    else:
        assert reference.rhs([0.2, 0], -0.080, name)[1] == 1000
    expected = (0.33, 1.0, 0.05) if name == "HCNLeak" else (0.2, 1.0, 0.05)
    assert tuple(ion for ion, _ in reference.RELATIVE_PERMEABILITY[name]) == ("Na", "K", "Ca")
    assert tuple(value for _, value in reference.RELATIVE_PERMEABILITY[name]) == expected


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("bad", [True, "-0.080", float("nan"), float("inf"), -0.120001, 0.060001])
def test_reject_invalid_voltage_without_clipping(name, bad):
    with pytest.raises(ValueError):
        reference.kinetics(bad, name)
    with pytest.raises(ValueError):
        reference.initial_gates(bad, name)


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize(
    "bad", [[0.2], [0.2, 0.7, 0], [-1e-10, 1], [0, 1.0000001], [0, float("nan")]]
)
def test_invalid_explicit_native_gates_rejected(name, bad):
    with pytest.raises(ValueError):
        reference.opening(bad, name)


def test_invalid_classes_and_negative_time_are_not_coerced():
    with pytest.raises(ValueError):
        reference.kinetics(-0.080, "HCN4")
    for method in (reference.relaxation, reference.backward_euler):
        for time in (-1e-10, True, float("nan")):
            with pytest.raises(ValueError):
                method([0.2, 0.7], -0.080, "HCN2_cAMP", time)


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("gate", [0, 1])
def test_continuous_each_native_gate_refinement_and_twelve_tau_recovery(name, gate):
    start = np.array([0.2, 0.7])
    target, tau = reference.kinetics(-0.080, name)
    target, tau = np.asarray(target), np.asarray(tau)
    initial, equilibrium, time_scale = start[gate], target[gate], tau[gate]
    endpoint = reference.relaxation(start, -0.080, name, 12 * time_scale)[gate]
    expected_residual = abs(initial - equilibrium) * math.exp(-12)
    close(abs(endpoint - equilibrium), expected_residual)
    errors = []
    finals = []
    for steps_per_tau in (8, 16, 32):
        dt, state = time_scale / steps_per_tau, initial
        at_tau = None
        for index in range(12 * steps_per_tau):

            def slope(value):
                return (equilibrium - value) / time_scale

            k1 = slope(state)
            k2 = slope(state + dt * k1 / 2)
            k3 = slope(state + dt * k2 / 2)
            k4 = slope(state + dt * k3)
            state += dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            if index + 1 == steps_per_tau:
                at_tau = state
        exact_one = reference.relaxation(start, -0.080, name, time_scale)[gate]
        errors.append(abs(at_tau - exact_one))
        finals.append(state)
    order = np.log2(np.asarray(errors[:-1]) / errors[1:])
    assert np.all(
        (order > TOL["continuous_rk4_order"][0]) & (order < TOL["continuous_rk4_order"][1])
    )
    assert abs(finals[-1] - endpoint) < 2e-12
    evidence(
        f"continuous-{name}-{gate}",
        dict(
            status="passed",
            clock="continuous",
            gate=gate,
            tau_s=time_scale,
            duration_s=12 * time_scale,
            initial=initial,
            exact_final=endpoint,
            rk4_final=finals,
            one_tau_errors=errors,
            observed_order=order,
            native_backward_euler=False,
        ),
    )
