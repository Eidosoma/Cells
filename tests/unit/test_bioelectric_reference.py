"""Tests of the independent NUM-002 oracle, not a production bioelectric model."""

from dataclasses import replace

import numpy as np
import pytest

from tests import reference_bioelectric as ref


def assert_physical_accuracy(parameters, actual, expected, factor=1.0):
    limits = {
        "amount_fmol": 1e-7,
        "leak_fmol": 1e-7,
        "pump_cycles_fmol": 1e-7,
        "voltage_V": 1e-6,
        "dissipation_pJ": 1e-6,
    }
    for name, error in ref.trajectory_errors(parameters, actual, expected).items():
        assert error <= limits[name] * factor, (name, error)


def test_initial_fixture_matches_prior_independent_design_values():
    p = ref.Parameters()
    leak, cycles, _, energy = ref.fluxes(p, p.initial_amount, p.initial_voltage_V, ref.Control())
    np.testing.assert_allclose(
        leak,
        [0.03959636779095933, -0.016914657583149164, 0.0005360061901298455],
        rtol=2e-14,
        atol=1e-16,
    )
    assert cycles == pytest.approx(0.01882747558106557, rel=2e-14)
    assert energy == pytest.approx(-8676.272959336035, rel=2e-14)
    assert p.fixed_anion_equivalent == pytest.approx(142.00673677527658, abs=1e-12)


@pytest.mark.parametrize("voltage", [-0.2, -0.065, -1e-10, 0.0, 1e-10, 0.02, 0.2])
def test_hyperbolic_flux_against_direct_expm1_expression(voltage):
    p = ref.Parameters()
    x = ref.Z * ref.F * voltage / (ref.R * p.temperature_K)
    b = np.array([v / np.expm1(v) if v != 0 else 1.0 for v in x])
    inverse = np.array([-v / np.expm1(-v) if v != 0 else 1.0 for v in x])
    expected = (
        p.area_m2
        * np.asarray(p.permeability_m_per_s)
        / 1e-15
        * (np.asarray(p.bath_mM) * b - np.asarray(p.initial_mM) * inverse)
    )
    actual = ref.fluxes(p, p.initial_amount, voltage, ref.Control())[0]
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-16)


@pytest.mark.parametrize("species", range(3))
def test_nernst_limit(species):
    p = ref.Parameters()
    voltage = (
        ref.R
        * p.temperature_K
        / (ref.Z[species] * ref.F)
        * np.log(p.bath_mM[species] / p.initial_mM[species])
    )
    assert abs(ref.fluxes(p, p.initial_amount, voltage, ref.Control())[0][species]) < 1e-12


def test_diffusion_orientation_area_and_off_limits():
    p = ref.Parameters(initial_mM=(10, 100, 110))
    leak = ref.fluxes(p, p.initial_amount, 0.0, ref.Control())[0]
    expected = (
        p.area_m2
        * np.asarray(p.permeability_m_per_s)
        / 1e-15
        * (np.asarray(p.bath_mM) - p.initial_mM)
    )
    np.testing.assert_allclose(leak, expected, rtol=2e-15, atol=1e-16)
    incoming = ref.fluxes(p, p.initial_amount, -0.065, ref.Control())[0]
    swapped = replace(p, initial_mM=p.bath_mM, bath_mM=p.initial_mM)
    outgoing = ref.fluxes(swapped, swapped.initial_amount, 0.065, ref.Control())[0]
    np.testing.assert_allclose(incoming, -outgoing, rtol=2e-15, atol=1e-16)
    larger = replace(p, area_m2=p.area_m2 * 2)
    np.testing.assert_array_equal(
        ref.fluxes(larger, p.initial_amount, -0.065, ref.Control())[0], 2 * incoming
    )
    np.testing.assert_array_equal(
        ref.fluxes(p, p.initial_amount, -0.065, ref.Control(leak=(0, 0, 0)))[0], np.zeros(3)
    )


def test_pump_stall_reverse_and_signed_chemical_work():
    p = ref.Parameters()
    _, forward, mu, energy = ref.fluxes(p, p.initial_amount, -0.065, ref.Control())
    assert forward > 0 and energy < 0 and ref.NU @ ref.Z == -1
    stalled = replace(p, atp_free_energy_J_per_mol=float(-ref.NU @ mu))
    assert ref.fluxes(stalled, stalled.initial_amount, -0.065, ref.Control())[1] == 0
    assert ref.fluxes(p, p.initial_amount, -0.065, ref.Control(pump=0))[1] == 0
    # Mechanism probe only: a strong opposing electrical gradient drives reversal.
    _, backward, _, energy = ref.fluxes(p, p.initial_amount, -0.8, ref.Control())
    assert backward < 0 and energy > 0 and backward * energy < 0
    assert -p.atp_free_energy_J_per_mol * backward * 1e-15 < 0


@pytest.mark.parametrize(
    "changes",
    [
        {"volume_pL": 0},
        {"area_m2": -1},
        {"temperature_K": 0},
        {"specific_capacitance_F_per_m2": np.nan},
        {"initial_mM": (1, 2)},
        {"initial_mM": (0, 2, 1)},
        {"initial_mM": (1, 1, 10)},
        {"bath_mM": (145, 5, 149)},
        {"bath_mM": (np.inf, 5, 150)},
        {"permeability_m_per_s": (-1, 0, 0)},
        {"pump_capacity_fmol_per_s": -1},
        {"atp_free_energy_J_per_mol": np.inf},
        {"initial_voltage_V": 2},
    ],
)
def test_parameter_domain_refused(changes):
    with pytest.raises(ValueError):
        ref.Parameters(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"time": -1},
        {"time": np.nan},
        {"leak": (0, 1)},
        {"leak": (0, 2, 1)},
        {"leak": (np.nan, 1, 1)},
        {"pump": -1},
        {"pump": np.inf},
    ],
)
def test_control_domain_refused(changes):
    with pytest.raises(ValueError):
        ref.Control(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"horizon": 0},
        {"horizon": np.nan},
        {"controls": ()},
        {"controls": (ref.Control(1),)},
        {"controls": (ref.Control(), ref.Control())},
        {"controls": (ref.Control(), ref.Control(2), ref.Control(1))},
        {"controls": (ref.Control(), ref.Control(11))},
    ],
)
def test_schedule_domain_refused(changes):
    with pytest.raises(ValueError):
        ref.Case("invalid", **changes)


def test_resolved_tuple_parameters_and_controls_are_immutable():
    original = [12, 140, 10]
    p = ref.Parameters(initial_mM=original)
    controls = [ref.Control()]
    c = ref.Case("immutable", p, controls=controls)
    original[0] = 100
    controls.clear()
    assert p.initial_mM == (12, 140, 10) and len(c.controls) == 1


@pytest.mark.parametrize("case", ref.panel(), ids=lambda c: c.name)
def test_independent_reference_solvers_agree(case):
    a = ref.integrate_reference(case)
    b = ref.integrate_reference(case, method="BDF")
    times = np.unique(np.r_[np.linspace(0, case.horizon, 151), [c.time for c in case.controls]])
    values = a.sample(times)
    assert_physical_accuracy(case.parameters, values, b.sample(times), factor=0.1)
    for candidate in (values, b.sample(times)):
        residuals = ref.balances(case.parameters, candidate)
        assert residuals["amount_fmol"] <= 1e-10
        assert residuals["charge_as_voltage_V"] <= 1e-8
        assert residuals["energy_pJ"] <= 1e-6
        assert np.all(candidate[:, :3] > 0)
    assert a.stats["trial_domain"]["minimum_amount_fmol"] > 0
    assert b.stats["trial_domain"]["max_abs_x"] <= 50


@pytest.fixture(scope="module")
def controlled_probe():
    case = next(case for case in ref.panel() if case.name == "independent_controls")
    oracle = ref.integrate_reference(case, rtol=1e-12, atol=1e-14)
    times, values, _ = ref.integrate_rk4_probe(case, 0.005)
    return case, oracle, times, values


def test_rk4_and_hermite_accuracy_with_controlled_transients(controlled_probe):
    case, oracle, times, values = controlled_probe
    assert_physical_accuracy(case.parameters, values, oracle.sample(times))
    midpoints = (times[:-1] + times[1:]) / 2
    observed = ref.sample_probe(case, times, values, midpoints, method="hermite")
    expected = oracle.sample(midpoints)
    assert_physical_accuracy(case.parameters, observed, expected)
    linear = ref.sample_probe(case, times, values, midpoints, method="linear")
    assert ref.trajectory_errors(case.parameters, linear, expected)["voltage_V"] > 1e-6


def test_independent_controls_hold_only_the_declared_routes(controlled_probe):
    _, _, times, values = controlled_probe
    pump = values[(times >= 2.03) & (times <= 5.07), 6]
    sodium = values[(times >= 3.11) & (times <= 4.13), 3]
    np.testing.assert_array_equal(pump, np.full_like(pump, pump[0]))
    np.testing.assert_array_equal(sodium, np.full_like(sodium, sodium[0]))
    assert np.ptp(values[(times >= 3.11) & (times <= 4.13), 4]) > 1e-6


def test_sampling_is_read_only_and_preserves_exact_endpoints(controlled_probe):
    case, oracle, times, values = controlled_probe
    before, stats = values.copy(), dict(oracle.stats)
    np.testing.assert_array_equal(
        ref.sample_probe(case, times, values, times, method="hermite"), values
    )
    assert ref.sample_probe(case, times, values, [], method="hermite").shape == (0, 8)
    assert oracle.sample([]).shape == (0, 8)
    sample = oracle.sample([0.201, 2.033, 9.917])
    np.testing.assert_array_equal(sample, oracle.sample([0.201, 2.033, 9.917]))
    np.testing.assert_array_equal(before, values)
    assert oracle.stats == stats


@pytest.mark.parametrize("times", [[-1], [11], [2, 1], [np.nan], [[1]]])
def test_invalid_sample_times_refused(controlled_probe, times):
    case, oracle, accepted, values = controlled_probe
    with pytest.raises(ValueError):
        oracle.sample(times)
    with pytest.raises(ValueError):
        ref.sample_probe(case, accepted, values, times, method="hermite")


def test_hermite_uses_left_interval_control_at_an_event():
    case = ref.Case("event_slope", horizon=0.3, controls=(ref.Control(pump=0), ref.Control(0.203)))
    times, values, _ = ref.integrate_rk4_probe(case, 0.01)
    sample = np.array([0.202])
    oracle = ref.integrate_reference(case)
    actual = ref.sample_probe(case, times, values, sample, method="hermite")
    assert_physical_accuracy(case.parameters, actual, oracle.sample(sample))
    left = np.searchsorted(times, sample[0], side="right") - 1
    h = times[left + 1] - times[left]
    theta = (sample[0] - times[left]) / h
    old = ref.derivative(
        case.parameters, case.control_at(times[left]), values[left + 1], increments=False
    )
    wrong = ref.derivative(
        case.parameters, case.control_at(times[left + 1]), values[left + 1], increments=False
    )
    incorrect = actual + h * (theta**3 - theta**2) * (wrong - old)
    assert (
        ref.trajectory_errors(case.parameters, incorrect, oracle.sample(sample))["voltage_V"] > 1e-6
    )


def test_substep_pulse_and_final_time_event():
    case = next(c for c in ref.panel() if c.name == "short_pulse")
    times, values, _ = ref.integrate_rk4_probe(case, 0.01)
    assert 0.203 in times and 0.207 in times
    assert values[-1, 6] > 1e-6
    end_event = replace(case, controls=(*case.controls, ref.Control(case.horizon, pump=1)))
    t2, y2, _ = ref.integrate_rk4_probe(end_event, 0.01)
    np.testing.assert_array_equal(t2, times)
    np.testing.assert_array_equal(y2, values)
    assert end_event.control_at(case.horizon).pump == 1


def test_all_off_is_exact_with_interpolation():
    case = ref.Case("zero", horizon=0.1, controls=(ref.Control(leak=(0, 0, 0), pump=0),))
    times, values, _ = ref.integrate_rk4_probe(case, 0.01)
    for method in ("linear", "hermite"):
        actual = ref.sample_probe(case, times, values, np.linspace(0, 0.1, 137), method=method)
        np.testing.assert_array_equal(actual, np.broadcast_to(values[0], actual.shape))


def test_rk4_transient_refinement_and_coarse_step_failure():
    case = ref.Case("refinement", horizon=1)
    oracle = ref.integrate_reference(case, rtol=1e-12, atol=1e-14)
    errors = []
    for step in (0.04, 0.02, 0.01, 0.005):
        times, values, _ = ref.integrate_rk4_probe(case, step)
        errors.append(
            ref.trajectory_errors(case.parameters, values, oracle.sample(times))["voltage_V"]
        )
    assert errors[0] > 1e-6
    assert all(14 <= a / b <= 22 for a, b in zip(errors[1:-1], errors[2:], strict=True))


def test_trial_domain_and_resource_budgets_are_enforced(monkeypatch):
    case = ref.Case("budget", horizon=1)
    with pytest.raises(ValueError, match="budget"):
        ref.probe_grid(case, 1e-6)
    fast = replace(case, parameters=ref.Parameters(permeability_m_per_s=(2e-9, 2e-8, 2e-9)))
    with pytest.raises(ValueError, match="trial"):
        ref.integrate_rk4_probe(fast, 0.2)
    monkeypatch.setattr(ref, "MAX_REFERENCE_EVALUATIONS", 2)
    with pytest.raises(ValueError, match="budget"):
        ref.integrate_reference(case)


@pytest.mark.parametrize("state", [np.zeros(7), np.full(8, np.nan), np.r_[np.zeros(7), np.inf]])
def test_nonfinite_or_wrong_shape_reference_state_refused(state):
    with pytest.raises(ValueError, match="eight finite"):
        ref.derivative(ref.Parameters(), ref.Control(), state, increments=True)


def test_passive_equilibrium_and_local_timescale_separation():
    p = ref.Parameters()
    voltage, amounts = ref.passive_equilibrium(p)
    leak = ref.fluxes(p, amounts, voltage, ref.Control(pump=0))[0]
    assert np.max(np.abs(leak)) < 1e-12
    assert abs(p.voltage(amounts) - voltage) < 1e-10
    spectrum = ref.local_spectrum(p, p.initial_amount, ref.Control())
    assert max(abs(v) for v in spectrum["eigenvalues_imag_per_s"]) < 1e-9
    rates = -np.asarray(spectrum["eigenvalues_real_per_s"])
    assert rates.min() > 0
    assert rates.max() / rates.min() > 10000
