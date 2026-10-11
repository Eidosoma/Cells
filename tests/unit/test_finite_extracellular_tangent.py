"""NUM-009 v2 general-engineering preflights, not extra full-panel attempts."""

import json
import subprocess
from dataclasses import replace
from time import monotonic

import numpy as np
import pytest

from scripts import audit_finite_extracellular_reference_v2 as audit
from scripts import qualify_finite_extracellular_reference_v2 as qualify
from tests import finite_extracellular_numerical_checks as checks
from tests import finite_extracellular_numerical_data as data
from tests import finite_extracellular_numerical_data_v2 as binding
from tests import finite_extracellular_tangent as tangent
from tests import reference_finite_extracellular_dynamics as v1
from tests import reference_finite_extracellular_dynamics_v2 as ref
from tests.unit.test_finite_extracellular_dynamics import small as small


@pytest.fixture(scope="module")
def panel():
    return binding.load_panel()


def observations(case, arrays, method, samples):
    return arrays | {
        "sample_times_s": samples,
        "sample_state": ref.sample_record(case, arrays, method, samples),
    }


@pytest.fixture(scope="module")
def small_records(panel, small):
    records, stats = {}, {}
    samples = ref.comparison_grid(small, panel[0]["candidate"])
    for setting in panel[0]["references"]:
        arrays, stats[setting["id"]] = ref.integrate_reference(small, setting)
        records[setting["id"]] = observations(small, arrays, setting["method"], samples)
    for dt in panel[0]["candidate"]["steps_s"]:
        name = f"rk4_{dt:g}"
        arrays, stats[name] = ref.integrate_candidate(small, dt, budget=tangent.Budget())
        assert stats[name]["status"] == "complete"
        records[name] = observations(small, arrays, "RK4", samples)
    return records, stats


def total_matrix(case):
    result = np.zeros((case.layout.s, case.size))
    for s, indices in enumerate(tangent.amount_indices(case).T):
        result[s, indices] = 1
    return result


def test_amendment_changes_no_physics_or_tolerance(panel):
    old, cases = data.load_panel()
    new, current = panel
    assert [c.definition() for c in cases] == [c.definition() for c in current]
    for key in old:
        if key not in ("schema", "coordinate_contract"):
            assert new[key] == old[key]
    assert not new["jacobian"]["state_projection"]
    assert new["jacobian"]["amount_scale_fmol"] == tangent.AMOUNT_SCALE_FMOL
    assert new["jacobian"]["gate_scale"] == tangent.GATE_SCALE
    assert new["jacobian"]["bound_fraction"] == tangent.BOUND_FRACTION
    assert new["jacobian"]["central_minimum_nominal_fraction"] == tangent.CENTRAL_FRACTION
    _, sources = qualify.capture_sources()
    assert set(sources) == set(qualify.SOURCE_FILES)


@pytest.mark.parametrize("index", range(14))
def test_projector_and_all_actual_probes_conserve_species(panel, index):
    case = panel[1][index]
    state = data.initial_state(case)
    before = state.copy()
    p, a = tangent.projector(case), total_matrix(case)
    np.testing.assert_allclose(p @ p, p, atol=5e-16, rtol=0)
    np.testing.assert_allclose(p.T, p, atol=0, rtol=0)
    np.testing.assert_allclose(a @ p, 0, atol=5e-16, rtol=0)

    class WatchingBudget(tangent.Budget):
        def jacobian_rhs(self, current, control, value):
            np.testing.assert_allclose(a @ value, 0, atol=1e-18, rtol=0)
            return super().jacobian_rhs(current, control, value)

    budget = WatchingBudget()
    j = tangent.jacobian(case, case.controls[0], state, budget=budget)
    columns = (case.layout.n + 1) * case.layout.s + 2 * case.layout.k + case.layout.e
    assert budget.calls == budget.jacobian_rhs_calls == 1 + 2 * columns
    assert budget.jacobian_evaluations == 1
    assert budget.central_columns + budget.one_sided_columns == columns
    assert budget.max_charge <= 1e-20
    np.testing.assert_array_equal(state, before)
    history = np.setdiff1d(
        np.arange(case.size),
        np.r_[tangent.amount_indices(case).ravel(), tangent.gate_indices(case)],
    )
    assert np.count_nonzero(j[:, history]) == 0


@pytest.mark.parametrize("index", [0, 5, 7, 8, 12, 13])
def test_tangent_derivative_matches_independent_bernoulli_path(panel, index):
    case = panel[1][index]
    y, a = data.initial_state(case), total_matrix(case)
    rng = np.random.default_rng(5291)
    direction = np.zeros(case.size)
    direction[tangent.amount_indices(case).ravel()] = rng.uniform(
        -1e-5, 1e-5, (case.layout.n + 1) * case.layout.s
    )
    direction[tangent.gate_indices(case)] = rng.uniform(
        -0.01, 0.01, len(tangent.gate_indices(case))
    )
    direction = tangent.projector(case) @ direction
    np.testing.assert_allclose(a @ direction, 0, atol=1e-19)
    control = case.controls[0]
    j = tangent.jacobian(case, control, y, budget=tangent.Budget())
    h = 1e-4
    expected = (
        v1.bernoulli_rhs(case, control, y + h * direction)
        - v1.bernoulli_rhs(case, control, y - h * direction)
    ) / (2 * h)
    np.testing.assert_allclose(j @ direction, expected, atol=1e-7, rtol=1e-5)


@pytest.mark.parametrize("gates", [(0.0, 1.0), (1.0, 0.0)])
def test_gate_boundaries_use_admissible_one_sided_probes(panel, gates):
    base = next(c for c in panel[1] if c.id == "star_mono")
    channels = tuple(
        replace(ch, initial_gate=data.spec.channel.Gate(*gates)) for ch in base.world.channels
    )
    case = replace(base, world=replace(base.world, channels=channels))
    y = data.initial_state(case)
    budget = tangent.Budget()
    tangent.jacobian(case, case.controls[0], y, budget=budget)
    assert budget.one_sided_columns >= 2 * case.layout.k
    assert budget.min_gate == 0 and budget.max_gate == 1


@pytest.mark.parametrize("target", ["outside", "all", 0, 1, 2])
@pytest.mark.parametrize("method", ["Radau", "BDF"])
def test_arbitrary_blocked_owner_stays_exact_after_nonzero_history(panel, target, method):
    base = next(c for c in panel[1] if c.id == "star_mono")
    enabled = data.spec.graph.enabled(base.world)
    off = enabled
    if target in ("outside", "all"):
        off = replace(
            off,
            leak=((0.0,) * base.layout.s,) * base.layout.n,
            pump=(0.0,) * base.layout.n,
            channel=(0.0,) * base.layout.k,
        )
        if target == "all":
            off = replace(off, junction=(0.0,) * base.layout.e)
    else:
        leak, pump, channel, junction = map(list, (off.leak, off.pump, off.channel, off.junction))
        leak[target], pump[target] = (0.0,) * base.layout.s, 0.0
        for k, cell in enumerate(base.channel_cells):
            if cell == target:
                channel[k] = 0.0
        for e, endpoints in enumerate(base.endpoints):
            if target in endpoints:
                junction[e] = 0.0
        off = replace(
            off,
            leak=tuple(leak),
            pump=tuple(pump),
            channel=tuple(channel),
            junction=tuple(junction),
        )
    case = data.Case(
        "blocked_owner_preflight",
        base.world,
        0.008,
        (data.Control(0, enabled), data.Control(0.0013, off)),
    )
    setting = next(s for s in panel[0]["references"] if s["method"] == method)
    arrays, stats = ref.integrate_reference(case, setting)
    samples = ref.comparison_grid(case, panel[0]["candidate"])
    arrays = observations(case, arrays, method, samples)
    for prefix in ("native", "sample"):
        chosen = arrays[prefix + "_times_s"] >= 0.0013
        values = case.layout.split(arrays[prefix + "_state"][chosen])
        field = (
            values["extracellular_amount"]
            if target in ("outside", "all")
            else values["amount"][:, target]
        )
        assert np.any(field[0] != 0)
        np.testing.assert_array_equal(field, np.broadcast_to(field[0], field.shape))
    control = checks.control_checks(
        case.definition(),
        samples,
        arrays["sample_state"],
        panel[0]["trajectory_limits"],
        factor=0.1,
    )
    assert control["pass"], control
    y = arrays["native_state"][np.flatnonzero(arrays["native_times_s"] == 0.0013)[0]]
    j = tangent.jacobian(case, case.controls[1], y, budget=tangent.Budget())
    indices = tangent.amount_indices(case)[-1 if target in ("outside", "all") else target]
    assert np.count_nonzero(j[indices]) == 0
    assert stats["rhs_calls"] == stats["nfev"] + stats["jacobian_rhs_calls"]


def test_complete_short_panel_agreement_and_all_fields(panel, small, small_records):
    records, stats = small_records
    verdict = checks.analyze_case(small.definition(), records, stats, panel[0])
    assert verdict["references_pass"], verdict
    assert any(
        verdict["attempts"][f"rk4_{dt:g}"]["pass"] for dt in panel[0]["candidate"]["steps_s"]
    )
    for name, arrays in records.items():
        assert arrays["native_state"].shape[1] == small.size
        np.testing.assert_array_equal(
            audit.replay(small.definition(), arrays, stats[name]["method"]), arrays["sample_state"]
        )
    assert all(stats[n]["jacobian_rhs_calls"] > 0 for n in ("radau", "bdf", "refined"))


def test_bad_supplied_outside_is_never_projected(panel):
    case = panel[1][1]
    y = data.initial_state(case)
    y[tangent.amount_indices(case)[-1, 0]] = 1e-4
    before = y.copy()
    with pytest.raises(v1.DomainViolation, match="countercharge"):
        tangent.jacobian(case, case.controls[0], y, budget=tangent.Budget())
    np.testing.assert_array_equal(y, before)


def test_probe_calls_and_deadline_are_bounded(panel):
    case = panel[1][0]
    with pytest.raises(ref.ResourceLimit, match="RHS budget"):
        ref.integrate_reference(case, panel[0]["references"][0], budget=tangent.Budget(max_calls=3))
    budget = tangent.Budget(deadline=monotonic() - 1)
    with pytest.raises(ref.ResourceLimit):
        tangent.jacobian(case, case.controls[0], data.initial_state(case), budget=budget)
    assert budget.calls == budget.jacobian_rhs_calls == 0


def test_unavailable_differentiation_interval_is_refused():
    with pytest.raises(v1.DomainViolation):
        tangent.difference_rule(1e-6, 0.0, 0.0)


def test_frozen_v2_binding_refuses_changed_limit(monkeypatch, tmp_path, panel):
    plan = json.loads(binding.PANEL.read_text())
    plan["accounting_limits"]["countercharge_C"] *= 10
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(plan))
    monkeypatch.setattr(binding, "PANEL", path)
    with pytest.raises(ValueError, match="Frozen NUM-009 v2"):
        binding.load_panel()


def test_read_only_v2_auditor_imports_no_rhs_or_ode():
    result = subprocess.run(
        [
            str(data.ROOT / ".venv/bin/python"),
            "-c",
            "import sys; from scripts import audit_finite_extracellular_reference_v2; "
            "assert 'scipy.integrate' not in sys.modules; assert 'cells' not in sys.modules; "
            "assert 'tests.finite_extracellular_tangent' not in sys.modules",
        ],
        cwd=data.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
