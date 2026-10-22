"""Conditional voltage-error propagation and independent Kv1p5 gate replay.

Validation only: no Cells/JAX/BETSE imports and no trajectory modification.
See gate_roundoff.md for the bound, changed acceptance rule and its limits.
"""

import numpy as np

POLICY = "kv1p5_voltage_propagation_with_independent_replay@1"
DOMAIN = (-0.120, 0.060)
NAMES = ("m_gate", "h_gate")


def _voltages(voltage, dt):
    value = np.asarray(voltage)
    if (
        value.dtype != np.float64
        or value.ndim != 2
        or min(value.shape) < 1
        or not np.isfinite(value).all()
        or np.any((value < DOMAIN[0]) | (value > DOMAIN[1]))
        or not np.isfinite(dt)
        or dt <= 0
    ):
        raise ValueError("Gate comparison requires float64 in-domain voltages and positive dt")
    return value


def replay(voltage, initial, dt):
    """Independent native mV/ms recurrence, starting only from initial gates."""
    voltage = _voltages(voltage, dt)
    gate = np.asarray(initial).copy()
    if gate.shape != (2, voltage.shape[1]) or not np.isfinite(gate).all():
        raise ValueError("Gate comparison initial shape/domain")
    if np.any((gate < 0) | (gate > 1)):
        raise ValueError("Gate comparison initial shape/domain")
    result = []
    for v in voltage:
        mv = v * 1000
        target = np.stack((1 / (1 + np.exp(-(mv + 6) / 6.4)), 1 / (1 + np.exp((mv + 25.3) / 3.5))))
        tau = np.stack((8.330 - 0.1163 * mv, 1620 - 15.5 * mv))
        gate = (tau * gate + dt * 1000 * target) / (tau + dt * 1000)
        result.append(gate.copy())
    return np.stack(result)


def voltage_allowance(left, right, dt):
    """Bound exact gate recurrences driven by two prescribed voltage histories.

    E_next = a_max E + L |delta_V|, with identical initial gates in [0,1].
    All positive bound arithmetic rounds outwards, including tau endpoints.
    No measured gate discrepancy, fitted factor or trajectory length multiplier
    enters the bound. This is conditional input-error propagation, not a proof
    that every voltage discrepancy in a coupled simulation is roundoff.
    """
    left, right = _voltages(left, dt), _voltages(right, dt)
    if left.shape != right.shape:
        raise ValueError("Gate comparison voltage shapes differ")

    def up(x):
        return np.nextafter(x, np.inf)

    def down(x):
        return np.nextafter(x, -np.inf)

    # tau = intercept - slope * V (seconds), |target'| <= 1 / (4 * width).
    intercept = np.array([0.008330, 1.620000])[:, None]
    slope = np.array([0.1163, 15.500])[:, None]
    width = np.array([0.0064, 0.0035])[:, None]
    target_slope = up(1 / down(4 * width))
    error = np.zeros((2, left.shape[1]))
    result = []
    for v, w in zip(left, right, strict=True):
        tau_lo = down(intercept - up(slope * np.maximum(v, w)))
        tau_hi = up(intercept - down(slope * np.minimum(v, w)))
        denominator = down(tau_lo + dt)
        assert np.all(denominator > 0)
        sensitivity = up(
            dt * up(up(target_slope / denominator) + up(slope / down(denominator * denominator)))
        )
        contraction = up(tau_hi / down(tau_hi + dt))
        dv = np.where(v == w, 0, up(abs(v - w)))
        # Preserve exact zero when both histories coincide and E is still zero.
        candidate = up(up(contraction * error) + up(sensitivity * dv))
        error = np.where((error == 0) & (dv == 0), 0, candidate)
        result.append(error.copy())
    return np.stack(result)


def addition(allowance, name, expected):
    """Only the two channel gates may receive an explicit comparison allowance."""
    if allowance is None:
        return 0
    assert set(allowance) == set(NAMES), "Unknown gate allowance fields"
    if name not in NAMES:
        return 0
    value = np.asarray(allowance[name])
    assert value.shape == expected.shape, "Gate allowance shape"
    assert value.dtype == np.float64 and np.isfinite(value).all() and np.all(value >= 0)
    return value


def check(row, trace, actual, tol):
    """Check inputs and both independent replays before permitting an allowance.

    ``actual`` contains the ordinary initial-inclusive saved arrays. Native
    evolving values are read only after the simulation, for comparison.
    """
    indices = np.flatnonzero((trace["method"] == 4) & ~trace["after"])
    assert len(indices) == row["steps"]
    np.testing.assert_array_equal(trace["step"][indices], np.arange(row["steps"]))
    assert np.all((trace["method"][indices + 1] == 4) & trace["after"][indices + 1])
    native_v = trace["vm"][indices]
    cells_v = np.asarray(actual["observed__vm"][:-1])
    assert actual["observed__vm"].shape == (row["steps"] + 1, native_v.shape[1])
    # Voltage itself keeps the old, independent acceptance criterion.
    np.testing.assert_allclose(
        cells_v,
        native_v,
        atol=tol["voltage_atol_V"],
        rtol=tol["voltage_rtol"],
        err_msg="gate input voltage",
    )
    initial = np.stack([trace["initial_" + name] for name in NAMES])
    np.testing.assert_array_equal(
        np.stack([actual["active__" + name][0] for name in NAMES]), initial
    )
    native = np.stack([trace[name][indices + 1] for name in NAMES], axis=1)
    cells = np.stack([actual["active__" + name][1:] for name in NAMES], axis=1)
    allowance = voltage_allowance(cells_v, native_v, row["dt_s"])
    replays, residuals = {}, {}
    for label, gates, voltage in (("native", native, native_v), ("cells", cells, cells_v)):
        expected = replay(voltage, initial, row["dt_s"])
        assert gates.shape == expected.shape and np.isfinite(gates).all()
        assert np.all((gates >= 0) & (gates <= 1))
        budget = tol["gate_atol"] + tol["gate_rtol"] * abs(expected)
        ratio = abs(gates - expected) / budget
        np.testing.assert_allclose(ratio, 0, atol=1, rtol=0, err_msg=label + " kinetic replay")
        replays[label] = expected
        residuals[label] = dict(
            max_absolute_error=float(abs(gates - expected).max()),
            max_error_over_budget=float(ratio.max()),
        )
    base = tol["gate_atol"] + tol["gate_rtol"] * abs(native)
    error = abs(cells - native)
    ratio = error / (base + allowance)
    np.testing.assert_allclose(ratio, 0, atol=1, rtol=0, err_msg="voltage-propagated gates")
    report = dict(
        status="passed",
        policy=POLICY,
        kinetic_replays=residuals,
        max_voltage_difference_V=float(abs(cells_v - native_v).max()),
        base_tolerances_unchanged=True,
        acceptance_criteria_changed=True,
        bound_scope=(
            "Conditional on separately checked voltage histories; not a global roundoff proof"
        ),
        gates={},
    )
    for i, name in enumerate(NAMES):
        report["gates"][name] = dict(
            max_absolute_error=float(error[:, i].max()),
            original_max_error_over_budget=float((error[:, i] / base[:, i]).max()),
            original_violations=int(np.count_nonzero(error[:, i] > base[:, i])),
            max_voltage_allowance=float(allowance[:, i].max()),
            max_error_over_accounted_budget=float(ratio[:, i].max()),
        )
    arrays = dict(
        native_voltage_V=native_v,
        cells_voltage_V=cells_v,
        native_replay=replays["native"],
        cells_replay=replays["cells"],
        voltage_allowance=allowance,
        original_budget=base,
        absolute_error=error,
    )
    return {name: allowance[:, i] for i, name in enumerate(NAMES)}, report, arrays
