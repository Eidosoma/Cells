"""Independent HCN source laws, unused state, and distinct physical/native clocks.

No production imports. Set CELLS_HCN_EXTRA_NATIVE to an unchanged-source capture
to include the pinned-source checks. The standalone supervisor supplies it.
"""

import ast
import hashlib
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


def test_capture_provenance_matches_frozen_protocol_and_installed_sources(native):
    assert native["source"]["version"] == PROTOCOL["source_version"]
    assert native["source"]["revision"] == PROTOCOL["source_revision"]
    assert native["source"]["unchanged_classes"]
    assert native["protocol_sha256"] == hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
    assert (
        native["capture_source_sha256"]
        == hashlib.sha256((ROOT / "validation/betse/hcn_extra_native.py").read_bytes()).hexdigest()
    )
    for name, expected in PROTOCOL["source_files"].items():
        assert native["source"]["files"][name]["installed_sha256"] == expected
        assert native["source"]["files"][name]["checkout_sha256"] == expected


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("case_index", range(12))
def test_unchanged_native_scalar_vector_targeted_and_empty_calls(native, name, case_index):
    case = native["classes"][name]["cases"][case_index]
    voltages = case["selected_voltage_V"]
    initial = np.array([reference.initial_gates(v, name) for v in voltages]).reshape(-1, 2).T
    values = [reference.kinetics(v, name) for v in voltages]
    target = np.array([row[0] for row in values]).reshape(-1, 2).T
    tau = np.array([row[1] for row in values]).reshape(-1, 2).T
    close(case["initial"], initial)
    close(case["target"], target)
    close(case["tau_s"], tau)
    assert tuple(case["powers"]) == reference.POWERS[name]
    assert (
        tuple(zip(case["ions"], case["relative_permeability"], strict=True))
        == reference.RELATIVE_PERMEABILITY[name]
    )
    assert case["time_unit"] == PROTOCOL["source_contracts"][name]["time_unit"]
    for step in case["native_steps"]:
        before = np.array(step["initial"])
        expected = (
            np.array(
                [
                    reference.backward_euler(before[:, i], v, name, step["dt_s"])
                    for i, v in enumerate(voltages)
                ]
            )
            .reshape(-1, 2)
            .T
        )
        close(step["gates"], expected)
        opened = np.array([reference.opening(expected[:, i], name) for i in range(len(voltages))])
        if case["targets"] is None:
            expected_opening = opened
        else:
            expected_opening = np.zeros(len(case["voltage_V"]))
            expected_opening[case["targets"]] = opened
        close(step["opening"], expected_opening)
    evidence(
        f"native-{name}-{case['label']}",
        dict(
            status="passed",
            case=case["label"],
            count=len(voltages),
            targets=case["targets"],
            native_steps=len(case["native_steps"]),
        ),
    )


@pytest.mark.parametrize("name", CLASSES)
def test_native_target_permutation_preserves_scattered_physical_opening(native, name):
    cases = native["classes"][name]["cases"]
    first, second = cases[9], cases[10]
    for a, b in zip(first["native_steps"], second["native_steps"], strict=True):
        np.testing.assert_array_equal(a["opening"], b["opening"])
        np.testing.assert_array_equal(
            np.array(a["gates"])[:, np.argsort(first["targets"])],
            np.array(b["gates"])[:, np.argsort(second["targets"])],
        )


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize(
    "refinement_index", range(len(PROTOCOL["native_capture"]["clamp_refinements"]))
)
def test_native_clamp_complete_states_follow_source_clock_through_recovery(
    native, name, refinement_index
):
    clamp = native["classes"][name]["clamps"][refinement_index]
    errors = []
    for phase in clamp["phases"]:
        voltage, times = phase["voltage_V"], np.array(phase["times_s"])
        states = np.array(phase["gates"])
        target, tau = reference.kinetics(voltage, name)
        target, tau = np.array(target), np.array(tau)
        assert times[0] == 0 and np.all(np.diff(times) > 0)
        assert times[-1] == 12 * max(tau)
        cumulative = states[0].copy()
        for i, dt in enumerate(np.diff(times)):
            cumulative = np.array(reference.backward_euler(cumulative, voltage, name, dt))
            close(states[i + 1], cumulative)
            close(phase["opening_after_step"][i], reference.opening(cumulative, name))
        continuous = np.array(reference.relaxation(states[0], voltage, name, times[-1]))
        errors.append(
            dict(
                voltage_V=voltage,
                duration_s=times[-1],
                steps=len(times) - 1,
                native_final=states[-1],
                continuous_final=continuous,
                absolute_difference=np.abs(states[-1] - continuous),
            )
        )
    evidence(
        f"native-clamp-{name}-{clamp['refinement']}",
        dict(
            status="passed",
            clock="native_backward_euler",
            phases=errors,
            continuous_equivalence=False,
        ),
    )


@pytest.mark.parametrize("name", CLASSES)
def test_native_clock_refinement_converges_toward_continuous_but_is_not_identical(native, name):
    errors = []
    for clamp in native["classes"][name]["clamps"]:
        phase = clamp["phases"][0]
        actual = np.array(phase["gates"][-1])
        exact = np.array(
            reference.relaxation(phase["gates"][0], phase["voltage_V"], name, phase["times_s"][-1])
        )
        errors.append(float(np.max(np.abs(actual - exact))))
    assert np.all(np.diff(errors) < 0) and errors[-1] > 0
    assert errors[-1] < 8e-6
    evidence(
        f"native-continuous-distinction-{name}",
        dict(
            status="passed",
            refinements=PROTOCOL["native_capture"]["clamp_refinements"],
            endpoint_errors=errors,
            clocks_equal=False,
        ),
    )
