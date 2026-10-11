"""NUM-003 independent-reference tests; no production pair is registered."""

import hashlib
from dataclasses import replace

import numpy as np
import pytest

from scripts import check_selective_contact_contract as design
from tests import reference_bioelectric_pair as ref


@pytest.fixture(scope="module")
def panel():
    return ref.load_panel()[1]


@pytest.fixture(scope="module")
def fast_case(panel):
    case = panel[9]
    fine = ref.integrate_reference(case, rtol=1e-12, atol=1e-14)
    times, values, _ = ref.integrate_rk4_probe(case, 0.001)
    return case, fine, times, values


def test_panel_frozen_before_integration():
    assert hashlib.sha256(ref.PANEL_PATH.read_bytes()).hexdigest() == (
        "642c92c6dba5f1f06c1639fbe37c0f69ef962e7018f2003d88c1c34d5ae14d46"
    )
    data, cases = ref.load_panel()
    assert len(cases) == 20
    assert data["targets"]["gate_fraction"] == 1e-7
    assert data["balance_targets"]["charge_as_voltage_V"] == 1e-8


@pytest.mark.parametrize("slot", range(20))
def test_every_frozen_case_has_valid_initial_state(panel, slot):
    case = panel[slot]
    absolute = ref.initial_state(case.parameters)
    incremental = ref.initial_state(case.parameters, increments=True)
    actual = ref.derivative(case.parameters, case.controls[0], absolute, increments=False)
    expected = ref.derivative(case.parameters, case.controls[0], incremental, increments=True)
    np.testing.assert_array_equal(actual, expected)
    assert actual.shape == (ref.SIZE,)


def test_initial_flux_matches_independent_design_expression(panel):
    p, control = panel[0].parameters, panel[0].controls[0]
    edge = p.junction
    actual = ref.junction_flux(p, p.initial_amount, p.initial_voltage, edge.initial_gate, control)
    expected = design.edge_flux(
        p.initial_amount[:, 0],
        p.initial_amount[:, 1],
        -0.02,
        ref.Z,
        edge.permeability_m_per_s,
        edge.area_m2,
        edge.initial_gate,
        edge.residual,
        1,
        p.temperature,
    )
    np.testing.assert_allclose(actual, expected, rtol=2e-14, atol=1e-18)


def test_closed_pair_rhs_conserves_species_and_weighted_voltage(panel):
    case = replace(panel[2], parameters=panel[5].parameters)
    d = ref.derivative(
        case.parameters, case.controls[0], ref.initial_state(case.parameters), increments=False
    )
    amount_rate = d[ref.AMOUNT].reshape(3, 2)
    np.testing.assert_array_equal(amount_rate.sum(axis=1), np.zeros(3))
    np.testing.assert_array_equal(d[ref.LEAK], np.zeros(6))
    np.testing.assert_array_equal(d[ref.PUMP], np.zeros(2))
    voltage_rate = ref.QF / case.parameters.capacitance * (ref.Z @ amount_rate)
    assert case.parameters.capacitance @ voltage_rate == pytest.approx(0, abs=1e-25)
    assert abs(voltage_rate.sum()) > 1e-6


def test_control_groups_are_not_linked(panel):
    case = panel[18]
    early, mid, blocked, released = (case.control_at(t) for t in (0.15, 0.25, 0.35, 0.5))
    assert np.array_equal(np.asarray(early.leak)[:, 0], np.zeros(3))
    assert early.pump == (1, 1)
    assert mid.pump == (1, 0) and mid.contact == 1
    assert blocked.pump == (1, 0) and blocked.contact == 0
    assert released.pump == (1, 0) and released.contact == 1


@pytest.mark.parametrize("gate", [0.0, 0.25, 1.0])
def test_jacobian_respects_gate_boundary_and_ledger_roles(panel, gate):
    p = panel[0].parameters
    value = ref.initial_state(p, increments=True)
    value[ref.GATE] = gate
    probes = []

    def rhs(y):
        assert 0 <= y[ref.GATE] <= 1
        probes.append(y[ref.GATE])
        return ref.derivative(p, panel[0].controls[0], y, increments=True)

    jac = ref.bounded_jacobian(p, value, rhs)
    assert jac[ref.GATE, ref.GATE] == pytest.approx(-1 / p.junction.tau_s, rel=1e-9)
    assert probes
    inactive_columns = sorted(set(range(ref.SIZE)) - set(ref.KINETIC))
    np.testing.assert_array_equal(
        jac[:, inactive_columns], np.zeros((ref.SIZE, len(inactive_columns)))
    )
    assert np.any(jac[ref.TRANSFER, ref.GATE] != 0)


@pytest.mark.parametrize("slot", [7, 8])
@pytest.mark.parametrize("method", ["Radau", "BDF"])
def test_implicit_oracle_starts_at_gate_boundaries(panel, slot, method):
    case = replace(panel[slot], horizon=0.1)
    result = ref.integrate_reference(case, method=method)
    values = result.sample(np.linspace(0, 0.1, 41))
    assert values[0, ref.GATE] == case.parameters.junction.initial_gate
    assert np.all((values[:, ref.GATE] >= 0) & (values[:, ref.GATE] <= 1))
    assert result.stats["trial_domain"]["gate_range"][0] >= 0
    assert result.stats["trial_domain"]["gate_range"][1] <= 1


def test_fast_gate_trial_is_refused_and_prefix_retained(panel):
    with pytest.raises(ref.ProbeFailure, match="gate outside") as caught:
        ref.integrate_rk4_probe(panel[9], 0.1)
    assert caught.value.trial["stage"] == "k2"
    np.testing.assert_array_equal(caught.value.times, [0])
    assert caught.value.values.shape == (1, ref.SIZE)
    assert caught.value.trial["state"][ref.GATE] > 1


def test_gate_only_matches_analytic_solution(panel):
    case = panel[3]
    times, values, _ = ref.integrate_rk4_probe(case, 0.001)
    p = case.parameters
    target = p.junction.target(p.initial_voltage[0] - p.initial_voltage[1])
    expected = target + (p.junction.initial_gate - target) * np.exp(-times / p.junction.tau_s)
    assert np.max(np.abs(values[:, ref.GATE] - expected)) < 1e-10
    other = [i for i in range(ref.SIZE) if i != ref.GATE]
    np.testing.assert_array_equal(
        values[:, other], np.broadcast_to(values[0, other], values[:, other].shape)
    )


def test_fast_case_candidate_accuracy_and_cubic_domain(fast_case):
    case, fine, times, values = fast_case
    samples = ref.observation_grid(times)
    coefficients = ref.hermite_coefficients(case, times, values)
    observed = ref.sample_probe(case, times, values, samples, coefficients=coefficients)
    error = ref.trajectory_errors(case.parameters, observed, fine.sample(samples))
    targets = ref.load_panel()[0]["targets"]
    assert all(error[name] <= limit for name, limit in targets.items()), error
    domain = ref.interpolant_domain(case.parameters, values, coefficients)
    assert 0 <= domain["gate_range"][0] <= domain["gate_range"][1] <= 1
    assert ref.balances(case.parameters, observed)["charge_as_voltage_V"] < 1e-8


def test_observation_schedule_cannot_change_state_or_samples(fast_case):
    case, _, times, values = fast_case
    before = values.copy()
    sparse = np.array([0, 0.0003, 0.1243, 0.7117, 1.0])
    dense = np.unique(np.r_[sparse, np.linspace(0, 1, 71)])
    one = ref.sample_probe(case, times, values, sparse)
    two = ref.sample_probe(case, times, values, dense)
    np.testing.assert_array_equal(one, two[np.searchsorted(dense, sparse)])
    np.testing.assert_array_equal(values, before)
    np.testing.assert_array_equal(ref.sample_probe(case, times, values, times), values)


def test_cubic_gate_overshoot_is_detected_between_valid_endpoints(panel):
    p = panel[0].parameters
    values = np.tile(ref.initial_state(p), (2, 1))
    values[:, ref.GATE] = 0.9
    ref.domain_summary(p, values)
    a, b, c = (np.zeros((1, ref.SIZE)) for _ in range(3))
    a[0, ref.GATE], b[0, ref.GATE] = 1, -1
    with pytest.raises(ValueError, match="Cubic interpolant"):
        ref.interpolant_domain(p, values, (a, b, c))


def test_substep_contact_block_retains_transfer_and_gate_state(panel):
    case = panel[17]
    times, values, _ = ref.integrate_rk4_probe(case, 0.001)
    start, end = np.searchsorted(times, [0.1234, 0.1241])
    assert times[start] == 0.1234 and times[end] == 0.1241
    np.testing.assert_array_equal(values[start, ref.TRANSFER], values[end, ref.TRANSFER])
    assert values[start, ref.GATE] != values[end, ref.GATE]
    samples = np.array([0.1234, 0.12355, 0.1238, 0.1241])
    observed = ref.sample_probe(case, times, values, samples)
    np.testing.assert_array_equal(
        observed[:, ref.TRANSFER], np.broadcast_to(values[start, ref.TRANSFER], (4, 3))
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"tau_s": 0},
        {"tau_s": -1},
        {"initial_gate": -0.1},
        {"initial_gate": 1.1},
        {"endpoints": (0, 0)},
        {"endpoints": (True, 0)},
        {"area_m2": 0},
        {"residual": (0, 1.1, 0)},
        {"permeability_m_per_s": (1, -1, 0)},
    ],
)
def test_invalid_junction_is_not_repaired(changes):
    with pytest.raises(ValueError):
        ref.Junction(**changes)


def test_different_baths_require_another_closure(panel):
    cells = panel[0].parameters.cells
    with pytest.raises(ValueError, match="common bath"):
        ref.Parameters((cells[0], replace(cells[1], temperature_K=310)))


@pytest.mark.parametrize("times", [[-0.1], [0.1, 0], [float("nan")], [11]])
def test_invalid_reference_sample_times(panel, times):
    with pytest.raises(ValueError):
        ref.checked_samples(times, 0, panel[0].horizon)


def test_reference_evaluation_budget(panel, monkeypatch):
    monkeypatch.setattr(ref, "MAX_CALLS", 1)
    with pytest.raises(ValueError, match="budget"):
        ref.integrate_reference(panel[0])
