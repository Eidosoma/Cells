"""Independent source, limit, branch and continuous-time checks for CaV gates."""

import hashlib
import json
import subprocess
from pathlib import Path

import jax
import numpy as np

from cells.processes import cav_channels as channels
from cells.processes import kv1_channels as prior
from tests.unit import test_surface_calcium as shared
from tests.unit.test_surface_kinetic import exact
from validation.tissue import cav_reference as reference

BACKEND = shared.BACKEND
PREFIX = "resolved-calcium-cav"
SOURCE_HASHES = {
    "vg_ca.py": "843d83f969ec53ba9322504f6ef0f699171c3c7c6e2caf03784de5bb17171dd6",
    "channelsabc.py": "ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4",
}


def evidence(name, value, arrays=None):
    shared.evidence(PREFIX + "-" + name, value, arrays)


def decimal_parameters(voltage, family):
    return tuple(
        np.asarray([[float(x) for x in reference.kinetics(v, family)[i]] for v in voltage]).T
        for i in (0, 1)
    )


def test_native_laws_and_discrete_clocks(tmp_path):
    output = tmp_path / "native.json"
    script = Path(__file__).resolve().parents[2] / "validation/betse/cav_native.py"
    child = subprocess.run(
        ["/mnt/workspaces/Cells/venv-betse/bin/python", "-B", str(script), str(output)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    (tmp_path / "native.stdout.log").write_text(child.stdout)
    (tmp_path / "native.stderr.log").write_text(child.stderr)
    child.check_returncode()
    native = json.loads(output.read_text())
    assert native["version"] == "1.5.0" and native["source_sha256"] == SOURCE_HASHES
    device = jax.devices(BACKEND)[0]
    maximum, count = 0.0, 0
    for law, family in reference.LAWS.items():
        row = native["families"][family]
        voltage = np.asarray(row["voltage_V"])
        codes = np.full(voltage.shape, channels.LAW_CODES[law], np.int64)
        target, tau = jax.jit(channels.kinetics)(*jax.device_put((voltage, codes), device))
        assert target.device.platform == BACKEND
        assert np.isfinite(target).all() and np.isfinite(tau).all() and np.all(np.asarray(tau) > 0)
        assert row["powers"] == list(reference.POWERS[family])
        assert row["ions"] == ["Ca"] and row["relative_permeability"] == [1.0]
        assert row["time_unit"] == 1000
        wanted = decimal_parameters(voltage, family)
        for actual, expected in (
            (target, row["initial"]),
            (target, row["target"]),
            (tau, row["tau_s"]),
            (target, wanted[0]),
            (tau, wanted[1]),
        ):
            np.testing.assert_allclose(actual, expected, rtol=5e-14, atol=5e-15)
            count += np.asarray(actual).size
        for trace in row["traces"]:
            gates = np.broadcast_to(np.asarray([[0.2], [0.7]]), (2, voltage.size)).copy()
            for v, expected, opened in zip(
                trace["voltage_V"], trace["gates"], trace["opening"], strict=True
            ):
                target, tau = channels.kinetics(np.asarray(v), codes, xp=np)
                dt = trace["dt_s"]
                gates = (gates * tau + dt * target) / (tau + dt)
                np.testing.assert_allclose(gates, expected, rtol=5e-14, atol=5e-15)
                np.testing.assert_allclose(
                    channels.opening(gates, codes, xp=np), opened, rtol=5e-14, atol=5e-15
                )
                maximum = max(maximum, float(np.max(np.abs(gates - expected))))
                count += gates.size + voltage.size
    probes = native["singular_probes"]
    assert probes["fields"] == [
        "initial_m",
        "initial_h",
        "m_target",
        "h_target",
        "m_tau_ms",
        "h_tau_ms",
    ]
    assert probes["finite"] == [[False], [True], [False], [True], [False], [True]]
    assert probes["warnings"] and probes["voltage_mV"] == [20.0]
    assert native["cav3p1_branch"]["threshold_V"] == -1e-5
    evidence(
        "native",
        dict(
            status="passed",
            native=native,
            compared_finite_scalars=count,
            max_native_clock_gate_error=maximum,
            capture_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
            scope=(
                "Finite source-law and native-clock correspondence; the retained "
                "nonfinite CaV2.2 probe is not a passing finite comparison"
            ),
        ),
    )


def test_removable_limit_and_literal_source_branch():
    device = jax.devices(BACKEND)[0]
    voltage = np.array([0.02 - 1e-12, 0.02, 0.02 + 1e-12])
    codes = np.full(voltage.shape, 14, np.int64)
    actual = jax.jit(channels.cav_kinetics)(*jax.device_put((voltage, codes), device))
    expected = decimal_parameters(voltage, "Cav2p2")
    for a, b in zip(actual, expected, strict=True):
        np.testing.assert_allclose(a, b, rtol=3e-14, atol=3e-15)
    gradients = jax.jit(jax.jacfwd(lambda v: channels.cav_kinetics(v, codes)))(
        jax.device_put(voltage, device)
    )
    assert all(np.isfinite(a).all() for a in (*actual, *gradients))
    voltage = np.array([-0.010, -1e-5 - 1e-12, -1e-5, -1e-5 + 1e-12])
    codes = np.full(voltage.shape, 16, np.int64)
    target, tau = jax.jit(channels.cav_kinetics)(*jax.device_put((voltage, codes), device))
    expected = decimal_parameters(voltage, "Cav3p1")
    for a, b in zip((target, tau), expected, strict=True):
        np.testing.assert_allclose(a, b, rtol=3e-14, atol=3e-15)
    assert tau[0, 0] != 0.001 and tau[0, 1] < 0.0007
    np.testing.assert_array_equal(tau[0, 2:], [0.001, 0.001])
    evidence(
        "edge-cases",
        dict(
            status="passed",
            regularized_voltage_V=0.02,
            finite_limit_and_autodiff=True,
            source_branch_voltage_V=-1e-5,
            branch_probe_voltage_V=voltage.tolist(),
            branch_tau_s=np.asarray(tau).tolist(),
            inferred_minus_10_mV_repair=False,
        ),
    )


def test_analytic_clamps_and_opening_powers():
    voltage = np.tile(np.linspace(-0.12, 0.06, 31), 7)
    codes = np.repeat(np.arange(11, 18), 31)
    target, tau = channels.kinetics(voltage, codes, xp=np)
    gates = np.broadcast_to(np.array([[0.2], [0.7]]), target.shape)
    # Resolve the fastest relaxation before it has equilibrated. A 2-ms
    # endpoint instead exposes accumulated rounding in the source's hours-long
    # low-voltage h gates; coupled 2-ms trajectories have their own checks.
    duration, steps = 0.0001, (0.625e-6, 0.3125e-6, 0.15625e-6)
    expected = target + (gates - target) * np.exp(-duration / tau)
    errors = []
    arrays = dict(
        voltage_V=voltage,
        codes=codes,
        initial=gates,
        target=target,
        tau_s=tau,
        analytic_reference=expected,
    )
    device = jax.devices(BACKEND)[0]
    for dt in steps:

        def solve(g, v, laws, step_size=dt):
            wanted, decay = channels.kinetics(v, laws)

            def step(old, _):
                k1 = (wanted - old) / decay
                k2 = (wanted - old - step_size * k1 / 2) / decay
                k3 = (wanted - old - step_size * k2 / 2) / decay
                k4 = (wanted - old - step_size * k3) / decay
                return old + step_size * (k1 + 2 * k2 + 2 * k3 + k4) / 6, None

            return jax.lax.scan(step, g, None, length=round(duration / step_size))[0]

        actual = jax.jit(solve)(*jax.device_put((gates, voltage, codes), device))
        assert actual.device.platform == BACKEND and np.isfinite(actual).all()
        errors.append(float(np.max(np.abs(actual - expected))))
        arrays[f"observed_{len(errors)}"] = np.asarray(actual)
        arrays[f"signed_error_{len(errors)}"] = np.asarray(actual - expected)
    passed = errors[0] < 1e-8 and errors[-1] <= max(errors[0] * 0.02, 2e-14)
    report = dict(
        status="running" if passed else "failed",
        duration_s=duration,
        dt_s=list(steps),
        max_gate_errors=errors,
        all_gate_powers_checked=False,
        absolute_gate_bound=1e-8,
        final_to_coarse_bound=0.02,
        roundoff_floor=2e-14,
        scope="Seven analytic clamp controls, not independent biological cases",
    )
    evidence("clamps", report, arrays)
    assert passed, errors
    for h in (0.0, 0.3, 1.0):
        g = np.stack((gates[0], np.full_like(voltage, h)))
        opened = jax.jit(channels.opening)(*jax.device_put((g, codes), device))
        wanted = [
            float(reference.opening(pair, family))
            for pair, family in zip(g.T, np.repeat(list(reference.LAWS.values()), 31), strict=True)
        ]
        np.testing.assert_allclose(opened, wanted, rtol=3e-15, atol=3e-16)
    evidence("clamps", report | dict(status="passed", all_gate_powers_checked=True), arrays)


def test_previous_catalog_and_code_domains():
    voltage = np.linspace(-0.12, 0.06, 61)
    gates = np.stack((np.linspace(0.0, 1.0, 61), np.linspace(1.0, 0.0, 61)))
    for code in range(11):
        codes = np.full(voltage.shape, code, np.int64)
        exact(channels.kinetics(voltage, codes, xp=np), prior.kinetics(voltage, codes, xp=np))
        exact(channels.opening(gates, codes, xp=np), prior.opening(gates, codes, xp=np))
    assert channels.valid_codes(np.arange(18), xp=np)
    for code in (-1, 18, 1.5, np.nan, np.inf):
        assert not channels.valid_codes(np.array([code]), xp=np)
    evidence(
        "retained-laws",
        dict(
            status="passed",
            previous_codes=list(range(11)),
            numpy_rates_and_opening="bitwise",
            unknown_fractional_nonfinite_codes_rejected=True,
        ),
    )
