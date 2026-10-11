"""NUM-010 preflights: full panel only at t=0, short independent fixtures in time."""

import copy
from time import monotonic

import numpy as np
import pytest

from tests import reference_spatial_extracellular_dynamics as ref
from tests import spatial_extracellular_fields as fields
from tests import spatial_extracellular_numerical_checks as checks
from tests import spatial_extracellular_numerical_data as data

PLAN, CASES = data.load_panel()


def short_case(source="binary_unequal", *, controls=True):
    raw = copy.deepcopy(next(c.raw for c in CASES if c.id == source))
    raw["id"], raw["horizon_s"], raw["analytic_kind"] = "short_preflight", 0.002, None
    ids = [m["id"] for m in raw["world"]["membranes"]]
    raw["controls"] = [
        {"time_s": t, "membrane_availability": {i: v for i in ids}}
        for t, v in ([(0, 1), (0.0007, 0), (0.0013, 1)] if controls else [(0, 1)])
    ]
    return data.resolve(raw)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_initial_independent_complete_derivative(case):
    y = data.initial_state(case)
    actual, a = fields.candidate(case, case.controls[0], y)
    expected, b = fields.independent(case, case.controls[0], y)
    np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=1e-10)
    np.testing.assert_allclose(a["potential_V"], b["potential_V"], rtol=2e-12, atol=1e-10)
    assert max(a["current_normalized"], b["current_normalized"]) <= 1
    p = case.layout.split(expected)
    np.testing.assert_allclose(np.sum(p["amount"], axis=0), 0, atol=1e-12)
    assert not case.g.initial.flags.writeable
    assert np.array_equal(case.layout.pack(p), expected)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_projector_preserves_both_material_and_component_charge(case):
    p, g = ref.amount_projector(case), case.g
    np.testing.assert_allclose(p, p.T, atol=1e-14)
    np.testing.assert_allclose(p @ p, p, atol=1e-14)
    material = np.kron(np.ones((1, len(g.ids))), np.eye(len(g.z)))
    charge = np.kron(g.p.T, g.z[None, :])
    constraint = np.r_[material, charge]
    np.testing.assert_allclose(constraint @ p, 0, atol=1e-14)
    # Independently characterize the nullspace using an SVD, not the constructor.
    _, singular, right = np.linalg.svd(constraint, full_matrices=True)
    rank = np.count_nonzero(singular > 1e-12)
    basis = right[rank:].T
    np.testing.assert_allclose(p, basis @ basis.T, atol=2e-14)


@pytest.mark.parametrize("method", ["Radau", "BDF", "RK4"])
def test_short_native_dense_accounting_and_nonzero_block(method):
    case = short_case()
    if method == "RK4":
        arrays, stats = ref.integrate_candidate(case, 0.0004)
        assert checks.cubic_domain(case, arrays)["pass"]
    else:
        setting = next(s for s in PLAN["references"] if s["method"] == method)
        arrays, stats = ref.integrate_reference(case, setting)
    checks.validate_record(case, arrays, stats)
    for prefix in ("native", "sample"):
        times, state = arrays[prefix + "_times_s"], arrays[prefix + "_state"]
        assert checks.inspect(case, times, state, PLAN["accounting_limits"])[0]["pass"]
        assert checks.blocked_checks(case, times, state)["pass"]
    at = np.flatnonzero(arrays["native_times_s"] == 0.0007)[0]
    p = case.layout.split(arrays["native_state"][at])
    assert np.any(p["membrane_transfer"] != 0)
    assert np.any(p["amount"][0] != 0)
    assert np.all(p["membrane_dissipation"] > 0)


def test_reference_jacobian_is_tangent_not_state_projection():
    case = short_case()
    y, budget = data.initial_state(case), ref.Budget()
    matrix = ref.jacobian(case, case.controls[0], y, 0.0, budget)
    rng = np.random.default_rng(10)
    direction = np.zeros(case.size)
    direction[: case.layout.amount_count] = ref.amount_projector(case) @ rng.normal(
        size=case.layout.amount_count
    )
    epsilon = 1e-7
    plus = fields.independent(case, case.controls[0], y + epsilon * direction)[0]
    minus = fields.independent(case, case.controls[0], y - epsilon * direction)[0]
    np.testing.assert_allclose(
        matrix @ direction, (plus - minus) / (2 * epsilon), rtol=1e-5, atol=1e-5
    )
    assert budget.jacobian_rhs_calls == 1 + 2 * case.layout.amount_count
    np.testing.assert_array_equal(matrix[:, case.layout.amount_count :], 0)
    blocked = ref.jacobian(case, case.controls[1], y, 0.0007, ref.Budget())
    np.testing.assert_array_equal(blocked[: len(case.g.z)], 0)
    np.testing.assert_array_equal(y, 0)


def test_general_one_sided_probe_rule_and_zero_tangent_columns():
    step, central = ref.difference_rule(1e-6, -1e-15, 1.0)
    assert step == 1e-6 and not central
    step, central = ref.difference_rule(1e-6, -1.0, 1e-15)
    assert step == -1e-6 and not central
    raw = copy.deepcopy(next(c.raw for c in CASES if c.id == "pure_bulk"))
    raw["world"]["compartments"] = raw["world"]["compartments"][:1]
    raw["world"]["faces"] = []
    case = data.resolve(raw)
    budget = ref.Budget()
    j = ref.jacobian(case, case.controls[0], data.initial_state(case), 0.0, budget)
    np.testing.assert_array_equal(j, 0)
    assert budget.zero_tangent_columns == 2 and budget.jacobian_rhs_calls == 1


@pytest.mark.parametrize("function", [fields.candidate, fields.independent])
def test_invalid_component_charge_cannot_be_repaired(function):
    case = short_case()
    value = data.initial_state(case)
    delta = case.layout.split(value)["amount"]
    delta[1, 0], delta[2, 0] = -0.01, 0.01
    assert np.sum(delta) == 0
    with pytest.raises(fields.DomainViolation, match="component"):
        function(case, case.controls[0], value)
    assert delta[2, 0] == 0.01


@pytest.mark.parametrize(
    "name",
    ["amount", "membrane_transfer", "face_transfer", "membrane_dissipation", "face_dissipation"],
)
def test_no_coordinate_field_can_be_omitted(name):
    case = short_case()
    parts = case.layout.split(data.initial_state(case))
    del parts[name]
    with pytest.raises(ValueError, match="five"):
        case.layout.pack(parts)


def test_complete_absolute_clock_restart_is_bitwise_equal(tmp_path):
    case, dt = short_case(), 0.0004
    original, _ = ref.integrate_candidate(case, dt)
    midpoint = len(original["native_times_s"]) // 2
    checkpoint = tmp_path / "complete.npz"
    np.savez(
        checkpoint,
        state=original["native_state"][midpoint],
        time=original["native_times_s"][midpoint],
    )
    with np.load(checkpoint, allow_pickle=False) as saved:
        resumed, stats = ref.integrate_candidate(
            case, dt, start=float(saved["time"]), initial=saved["state"]
        )
    for key, value in original.items():
        if key.startswith("sample_"):
            at = np.searchsorted(original["sample_times_s"], original["native_times_s"][midpoint])
            expected = value[at:]
        else:
            expected = value[midpoint:]
        assert expected.tobytes() == resumed[key].tobytes(), key
    checks.validate_record(case, resumed, stats, start=float(original["native_times_s"][midpoint]))
    with pytest.raises(ValueError, match="complete state"):
        ref.integrate_candidate(case, dt, start=0.0004)


@pytest.mark.parametrize("failure", ["amount", "charge", "voltage"])
def test_cubic_interior_failure_is_visible_with_healthy_endpoints(failure):
    case = short_case(controls=False)
    c = np.zeros((1, case.size, 6))
    s = len(case.g.z)
    if failure == "amount":
        for j in range(2 * s, 3 * s):
            c[0, j, 1], c[0, j, 2] = -5 * case.g.initial.ravel()[j], 5 * case.g.initial.ravel()[j]
    elif failure == "charge":
        c[0, 2 * s, 1], c[0, 2 * s, 2] = 4e-9, -4e-9
    else:
        c[0, 0, 1:3] = [-1, 1]
        c[0, s, 1:3] = [1, -1]
    result = checks.cubic_domain(case, {"coefficients": c, "native_times_s": np.array([0, 0.002])})
    assert not result["pass"]


@pytest.mark.parametrize(
    "case",
    [c for c in CASES if c.raw["analytic_kind"] == "cosine_line"],
    ids=["8_volumes", "16_volumes", "32_volumes"],
)
def test_line_initial_derivative_matches_discrete_analytic_eigenmode(case):
    exact, _ = checks.analytic_values(case, np.array([0.0]), discrete=True)
    np.testing.assert_allclose(exact[0], case.g.initial / case.g.volume[:, None], atol=3e-14)
    mesh = case.raw["mesh_parameters"]
    dp, dm = mesh["diffusivities_m2_per_s"]
    dx, n = mesh["length_m"] / mesh["volumes"], mesh["volumes"]
    eigenvalue = 4 * (2 * dp * dm / (dp + dm)) / dx**2 * np.sin(np.pi / (2 * n)) ** 2
    rate = fields.independent(case, case.controls[0], data.initial_state(case))[0]
    expected = -eigenvalue * (exact[0] - mesh["mean_mM"]) * case.g.volume[:, None]
    np.testing.assert_allclose(case.layout.split(rate)["amount"], expected, rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("case", CASES[:8], ids=[c.id for c in CASES[:8]])
def test_instantaneous_energy_direction_is_independent_of_histories(case):
    y = data.initial_state(case)
    rate = fields.independent(case, case.controls[0], y)[0]
    step = 1e-7
    derivative = (
        checks.energy_change(case, y + step * rate) - checks.energy_change(case, y - step * rate)
    ) / (2 * step)
    p = case.layout.split(rate)
    expected = -np.sum(p["membrane_dissipation"]) - np.sum(p["face_dissipation"])
    np.testing.assert_allclose(derivative, expected, rtol=1e-7, atol=1e-6)


def test_resource_limits_are_counted_and_reference_prefix_can_be_retained():
    case, settings = short_case(), PLAN["references"][0]
    budget = ref.Budget(max_calls=2)
    with pytest.raises(ref.ResourceLimit):
        ref.integrate_reference(case, settings, budget=budget)
    arrays, stats = ref.stopped_reference(case, settings, budget, ref.ResourceLimit("retained"))
    assert stats["status"] == "stopped" and stats["rhs_calls"] == 2
    assert arrays["native_state"].shape[1] == case.size
    assert arrays["sample_state"].shape == (0, case.size)
    with pytest.raises(ref.ResourceLimit, match="wall-time"):
        ref.integrate_candidate(case, 0.0004, budget=ref.Budget(deadline=monotonic() - 1))


def test_candidate_retains_actual_bad_trial_and_completed_prefix():
    raw = short_case(controls=False).definition()
    raw["horizon_s"] = 0.02
    raw["world"]["faces"][0]["area_m2"] *= 1000
    case = data.resolve(raw)
    arrays, stats = ref.integrate_candidate(case, 0.01)
    assert stats["status"] == "rejected" and stats["rejected_trial"]["stage"] in {
        "k2",
        "k3",
        "k4",
        "endpoint",
    }
    assert len(stats["rejected_trial"]["state"]) == case.size
    assert arrays["native_times_s"][-1] < case.horizon_s
    checks.validate_record(case, arrays, stats)


@pytest.mark.parametrize(
    "change", ["missing_control", "late_start", "extra_control", "bad_availability"]
)
def test_control_bindings_are_strict(change):
    raw = short_case().definition()
    if change == "missing_control":
        raw["controls"][0]["membrane_availability"] = {}
    elif change == "late_start":
        raw["controls"][0]["time_s"] = 0.0001
    elif change == "extra_control":
        raw["controls"][0]["membrane_availability"]["unknown"] = 1
    else:
        raw["controls"][0]["membrane_availability"]["membrane_0"] = 2
    with pytest.raises(ValueError):
        data.resolve(raw)
