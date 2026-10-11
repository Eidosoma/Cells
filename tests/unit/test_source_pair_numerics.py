"""Independent NUM-004 state/history/interpolation tests, not production acceptance."""

import numpy as np
import pytest

from tests import reference_source_pair_numerics as ref


def model(name="S13"):
    panel = ref.eq.load_panel()
    return ref.Model(panel, next(c for c in panel["cases"] if c["id"] == name))


@pytest.mark.parametrize("name", [f"S{i:02d}" for i in range(14)])
def test_bulk_readouts_match_frozen_pointwise_equations(name):
    m = model(name)
    times = np.array([0.0, *m.starts[1:], m.end])
    values = np.tile(m.initial(), (len(times), 1))
    bulk = ref.observations(m, times, values)
    for i, time in enumerate(times):
        one = ref.eq.evaluate(m.anchor, m.context, m.panel, m.held[m.slot(time)])
        for key, source in (
            ("voltage", "voltage"),
            ("gate_scale", "gate_scales"),
            ("packet", "packet"),
        ):
            np.testing.assert_allclose(bulk[key][i], one[source], atol=1e-12, rtol=1e-12)
        np.testing.assert_allclose(
            bulk["membrane_and_junction_flux"][i],
            np.r_[one["leak_flux"].ravel(), one["pump_flux"].ravel(), one["junction_flux"]],
            atol=1e-21,
            rtol=1e-12,
        )


def test_ledgers_are_diagnostics_and_close_each_primary():
    m = model()
    state = m.initial()
    slope = m.derivative(state, 0)
    changed = state.copy()
    changed[12:] = np.arange(18) - 9
    np.testing.assert_array_equal(m.derivative(changed, 0), slope)
    errors = ref.accounting(m, np.array([state, state + 1e-4 * slope]))
    assert max(errors.values()) < 1e-12


def test_checked_rk4_restart_and_interval_held_cubic():
    m = model()
    times, values, slopes, _ = ref.integrate_rk4(m, 0.01)
    coefficients = ref.cubic_coefficients(times, values, slopes)
    np.testing.assert_array_equal(ref.sample_cubic(times, values, coefficients, times), values)
    for time in (0.13, 0.137, 0.274):
        index = np.flatnonzero(times == time)[0]
        rt, ry, rs, _ = ref.integrate_rk4(m, 0.01, start_time=time, initial=values[index])
        np.testing.assert_array_equal(rt, times[index:])
        np.testing.assert_array_equal(ry, values[index:])
        np.testing.assert_array_equal(rs, slopes[index:])
    index = np.flatnonzero(times == 0.137)[0] - 1
    np.testing.assert_array_equal(slopes[index, 1], m.derivative(values[index + 1], 0))
    assert not np.array_equal(slopes[index, 1], m.derivative(values[index + 1], 1))


def test_cubic_checks_interior_not_only_endpoints():
    m = model()
    c = np.zeros((4, ref.SIZE))
    c[0] = m.initial()
    c[0, 6] = 0.01
    c[1, 6], c[2, 6] = -0.1, 0.1
    assert c[0, 6] > 0 and c[:, 6].sum() > 0
    with pytest.raises(ValueError, match="Whole interpolant"):
        ref.check_polynomial(m, c)


@pytest.mark.parametrize("dt", [0, -1, np.nan, np.inf, 1e-9])
def test_unbounded_steps_refused(dt):
    with pytest.raises(ValueError):
        ref.integrate_rk4(model(), dt)


@pytest.mark.parametrize("method", ["Radau", "BDF"])
def test_implicit_native_polynomial_adapter_and_accounting(method):
    m = model()
    m.case["end_time"] = 0.01
    m.case["events"] = []
    m = ref.Model(m.panel, m.case)
    solved = ref.integrate_reference(m, method=method)
    for a, b, coefficients in ref.native_polynomials(solved):
        theta = np.array([0.0, 0.137, 0.9, 1.0])
        np.testing.assert_allclose(
            np.polynomial.polynomial.polyval(theta, coefficients).T,
            solved.sample(a + (b - a) * theta),
            atol=1e-11,
            rtol=1e-12,
        )
        ref.check_polynomial(m, coefficients)
    assert max(ref.accounting(m, solved.sample(np.array([0.0, 0.0037, 0.01]))).values()) < 1e-10
