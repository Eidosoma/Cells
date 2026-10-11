"""NUM-009 engineering preflights; no undeclared full-panel trajectories."""

import ast
import copy
import json
import subprocess
from dataclasses import replace
from time import monotonic

import numpy as np
import pytest

from scripts import audit_finite_extracellular_reference as audit
from scripts import qualify_finite_extracellular_reference as qualify
from tests import finite_extracellular_numerical_checks as check
from tests import finite_extracellular_numerical_data as data
from tests import reference_finite_extracellular_dynamics as ref


@pytest.fixture(scope="module")
def panel():
    return data.load_panel()


@pytest.fixture(scope="module")
def small(panel):
    base = next(c for c in panel[1] if c.id == "star_mono")
    channels = list(base.world.channels)
    channels[0] = replace(channels[0], initial_gate=data.spec.channel.Gate(0.3, 0.7))
    world = replace(base.world, channels=tuple(channels))
    enabled = data.spec.graph.enabled(world)
    off = replace(
        enabled,
        leak=((0.0,) * base.layout.s,) * base.layout.n,
        pump=(0.0,) * base.layout.n,
        channel=(0.0,) * base.layout.k,
        junction=(0.0,) * base.layout.e,
    )
    return data.Case(
        "short_synthetic_preflight",
        world,
        0.012,
        (
            data.Control(0, enabled),
            data.Control(0.0023, replace(enabled, junction=(0.0, 1.0))),
            data.Control(0.0024, replace(enabled, channel=(1.0, 0.0), pump=(0.0, 1.0, 1.0))),
            data.Control(0.0051, off),
            data.Control(0.0089, enabled),
            data.Control(0.012, off),
        ),
    )


@pytest.fixture(scope="module")
def small_records(panel, small):
    plan = panel[0]
    samples = ref.comparison_grid(small, plan["candidate"])
    records, stats = {}, {}
    attempts = [(s["id"], s) for s in plan["references"]] + [
        (f"rk4_{dt:g}", dt) for dt in plan["candidate"]["steps_s"]
    ]
    for name, setting in attempts:
        if isinstance(setting, dict):
            arrays, stats[name] = ref.integrate_reference(small, setting)
            kind = setting["method"]
        else:
            arrays, stats[name] = ref.integrate_candidate(small, setting)
            kind = "RK4"
        complete = stats[name]["status"] == "complete"
        records[name] = arrays | {
            "sample_times_s": samples if complete else np.empty(0),
            "sample_state": ref.sample_record(small, arrays, kind, samples)
            if complete
            else np.empty((0, small.size)),
        }
    return records, stats


def test_frozen_scope_and_complete_sources(panel):
    plan, cases = panel
    assert len(cases) == 14 and plan["resources"]["max_attempts"] == 112
    assert len(data.FIELD_NAMES) == 10
    assert data.FIELD_NAMES[-1] == "extracellular_amount"
    assert data.sha(data.PANEL) == data.PANEL_SHA256
    _, hashes = qualify.capture_sources()
    assert set(hashes) == set(qualify.SOURCE_FILES)
    assert plan["candidate"]["steps_s"] == [0.004, 0.002, 0.001, 0.0005, 0.00025]
    assert not any("independent_cell_reduction" in c.definition() for c in cases)


@pytest.mark.parametrize("index", range(14))
def test_initial_independent_equations_and_full_coordinates(panel, index):
    case = panel[1][index]
    y = data.initial_state(case)
    state = data.physical_state(case, y)
    assert state == data.spec.initial_state(case.world)
    assert np.array_equal(data.expand(case, y[: case.layout.reduced_size]), y)
    for control in case.controls:
        a = ref.hyperbolic_rhs(case, control, y)
        b = ref.bernoulli_rhs(case, control, y)
        np.testing.assert_allclose(a, b, rtol=2e-12, atol=1e-11)
        p = case.layout.split(a)
        np.testing.assert_allclose(
            p["extracellular_amount"] + np.sum(p["amount"], axis=0), 0, atol=1e-16
        )


@pytest.mark.parametrize("index", range(14))
def test_inside_jacobian_perturbations_expand_conservatively(panel, index):
    case = panel[1][index]
    y = data.initial_state(case)[: case.layout.reduced_size]
    for coordinate in range(case.layout.amount_count):
        trial = y.copy()
        trial[coordinate] = 1e-9
        full = data.expand(case, trial)
        ref.domain(case, full)
        p = case.layout.split(full)
        assert np.array_equal(p["extracellular_amount"], -np.sum(p["amount"], axis=0))


@pytest.mark.parametrize(
    "field,bad", [("n", 0), ("n", True), ("s", 0), ("s", 2.5), ("k", -1), ("e", -1), ("e", False)]
)
def test_layout_rejects_bad_extents(field, bad):
    values = {"n": 1, "s": 3, "k": 0, "e": 0}
    values[field] = bad
    with pytest.raises(ValueError):
        data.Layout(**values)


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_outside_trial_domain_is_strict(panel, bad):
    case = panel[1][1]
    y = data.initial_state(case)
    data.layout(case.definition()).split(y)["extracellular_amount"][0] = (
        bad - case.outside_initial[0]
    )
    with pytest.raises(ref.DomainViolation):
        ref.domain(case, y)


def test_full_invalid_outside_is_not_repaired(panel):
    case = panel[1][1]
    y = data.initial_state(case)
    y[case.layout.slices["extracellular_amount"].start] += 1e-4
    with pytest.raises(ref.DomainViolation, match="countercharge"):
        ref.bernoulli_rhs(case, case.controls[0], y)


@pytest.mark.parametrize("field", data.FIELD_NAMES)
def test_every_hidden_state_field_must_be_finite(small, field):
    y = data.initial_state(small)
    y[small.layout.slices[field].start] = np.nan
    with pytest.raises(ref.DomainViolation):
        ref.domain(small, y)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_nonzero_conservative_rates(small, index):
    y = data.initial_state(small)
    slope = ref.hyperbolic_rhs(small, small.controls[0], y)
    y += (index + 1) * 1e-6 * slope
    a = ref.hyperbolic_rhs(small, small.controls[0], y)
    b = ref.bernoulli_rhs(small, small.controls[0], y)
    np.testing.assert_allclose(a, b, rtol=1e-8, atol=1e-9)


def test_short_reference_qualification(panel, small, small_records):
    records, stats = small_records
    verdict = check.analyze_case(small.definition(), records, stats, panel[0])
    assert verdict["references_pass"], verdict
    assert any(
        verdict["attempts"][f"rk4_{dt:g}"]["pass"] for dt in panel[0]["candidate"]["steps_s"]
    )
    for name in ("radau", "bdf", "refined"):
        p = small.layout.split(records[name]["native_state"])
        assert np.array_equal(p["extracellular_amount"], -np.sum(p["amount"], axis=1))
        assert stats[name]["max_trial_countercharge_C"] <= 1e-20


@pytest.mark.parametrize(
    "name",
    ["radau", "bdf", "refined", "rk4_0.004", "rk4_0.002", "rk4_0.001", "rk4_0.0005", "rk4_0.00025"],
)
def test_full_dense_replay_and_native_queries(small, small_records, name):
    records, stats = small_records
    arrays = records[name]
    kind = stats[name]["method"]
    if stats[name]["status"] != "complete":
        check.rejection_check(small.definition(), arrays, stats[name])
        return
    assert np.array_equal(audit.replay(small.definition(), arrays, kind), arrays["sample_state"])
    native = ref.sample_record(small, arrays, kind, arrays["native_times_s"])
    assert np.array_equal(native, arrays["native_state"])
    assert native.shape[1] == small.size


def test_controls_preserve_nonzero_histories_and_relax_gates(panel, small, small_records):
    arrays = small_records[0]["refined"]
    verdict = check.control_checks(
        small.definition(),
        arrays["sample_times_s"],
        arrays["sample_state"],
        panel[0]["trajectory_limits"],
        factor=0.1,
    )
    assert verdict["pass"], verdict
    p = small.layout.split(arrays["sample_state"])
    times = arrays["sample_times_s"]
    chosen = (times >= 0.0051) & (times <= 0.0089)
    assert np.any(p["channel_transferred"][chosen][0] != 0)
    assert np.any(p["membrane_gate"][chosen][-1] != p["membrane_gate"][chosen][0])
    assert np.array_equal(
        p["extracellular_amount"][chosen],
        np.broadcast_to(
            p["extracellular_amount"][chosen][0], p["extracellular_amount"][chosen].shape
        ),
    )


def test_candidate_endpoint_slope_uses_incoming_control(small, small_records):
    arrays = small_records[0]["rk4_0.00025"]
    times = arrays["native_times_s"]
    for i, t in enumerate(times[1:]):
        if t not in [c.time_s for c in small.controls[1:]]:
            continue
        held = small.control_at(float(times[i]))
        c = arrays["coefficients"][i]
        slope = (c[:, 1] + 2 * c[:, 2] + 3 * c[:, 3]) / (t - times[i])
        expected = ref.bernoulli_rhs(small, held, arrays["native_state"][i + 1])
        np.testing.assert_allclose(slope, expected, atol=1e-10, rtol=1e-10)
    assert all(u == 0 for u in small.control_at(small.horizon_s).value.pump)


@pytest.mark.parametrize(
    "field",
    [
        "leak_transferred",
        "pump_cycles",
        "channel_transferred",
        "junction_transferred",
        "membrane_dissipated_energy_pJ",
        "junction_dissipated_energy_pJ",
    ],
)
def test_hidden_history_corruption_breaks_accounting(panel, small, small_records, field):
    arrays = small_records[0]["refined"]
    values = arrays["sample_state"].copy()
    values[-1, small.layout.slices[field].start] += 0.01
    verdict = check.inspect_samples(
        small.definition(), arrays["sample_times_s"], values, panel[0]["accounting_limits"]
    )
    assert not verdict["pass"]


def test_neutral_outside_corruption_is_material_not_charge(panel, small, small_records):
    arrays = small_records[0]["refined"]
    values = arrays["sample_state"].copy()
    p = small.layout.split(values)
    for species in ("Na", "Cl"):
        p["extracellular_amount"][-1, small.world.species_ids.index(species)] += 0.01
    assert check.domain_summary(small.definition(), values)["pass"]
    verdict = check.inspect_samples(
        small.definition(), arrays["sample_times_s"], values, panel[0]["accounting_limits"]
    )
    assert not verdict["pass"]
    assert verdict["outside_material_residual_fmol"]["Na"] > 0.009


def test_whole_cubic_detects_outside_depletion(small, small_records):
    arrays = {k: v.copy() for k, v in small_records[0]["rk4_0.00025"].items()}
    start = small.layout.slices["extracellular_amount"].start
    # Equal K/Cl changes preserve charge; endpoints unchanged, K interior negative.
    for species in ("K", "Cl"):
        j = start + small.world.species_ids.index(species)
        arrays["coefficients"][0, j, :4] = [0, -40, 40, 0]
    verdict = check.candidate_polynomial_domain(small.definition(), arrays)
    assert not verdict["pass"]
    assert verdict["minimum_outside_amount_fmol"] < 0


@pytest.mark.parametrize("small_cubic", [0, 1e-17, -1e-17, 1e-25, -1e-25])
@pytest.mark.parametrize("scale", [1.0, 1e-13, 1e-100])
def test_nearly_quadratic_extrema_keep_finite_stationary_root(small_cubic, scale):
    lo, hi, count = check.polynomial_range(np.array([0, 1, -1, small_cubic]) * scale)
    assert lo == pytest.approx(0, abs=1e-15 * scale)
    assert hi == pytest.approx(0.25 * scale, rel=1e-14, abs=0)
    assert count >= 3


def test_whole_cubic_detects_countercharge_between_endpoints(small, small_records):
    arrays = {k: v.copy() for k, v in small_records[0]["rk4_0.00025"].items()}
    j = small.layout.slices["extracellular_amount"].start
    arrays["coefficients"][0, j, 1] += 0.001
    arrays["coefficients"][0, j, 2] -= 0.001
    verdict = check.candidate_polynomial_domain(small.definition(), arrays)
    assert not verdict["pass"]
    assert verdict["countercharge_C"] > 1e-20


@pytest.mark.parametrize("method", ["candidate", "reference"])
def test_work_budget_counts_actual_calls(panel, small, method):
    budget = ref.Budget(max_calls=1)
    with pytest.raises(ref.ResourceLimit, match="RHS budget"):
        if method == "candidate":
            ref.integrate_candidate(small, 0.001, budget=budget)
        else:
            ref.integrate_reference(small, panel[0]["references"][0], budget=budget)


def test_expired_deadline_stops_before_work(small):
    budget = ref.Budget(deadline=monotonic() - 1)
    with pytest.raises(ref.ResourceLimit):
        ref.integrate_candidate(small, 0.001, budget=budget)
    assert budget.calls == 0


@pytest.mark.parametrize("query", [-1, float("nan"), 0.013])
def test_controls_refuse_out_of_range_queries(small, query):
    with pytest.raises(ValueError):
        small.control_at(query)


def test_control_unknown_id_and_fraction_are_refused(panel):
    case = panel[1][1]
    row = copy.deepcopy(panel[0]["profiles"]["single"]["controls"][0])
    row["overrides"]["pump"]["missing"] = 0
    with pytest.raises(ValueError):
        data.resolve_control(case.world, row)
    del row["overrides"]["pump"]["missing"]
    row["pump"] = 1.1
    with pytest.raises(ValueError):
        data.resolve_control(case.world, row)


def test_json_duplicate_keys_are_refused(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError):
        data.spec.ion.load_json(path)


def test_artifacts_refuse_overwrite(tmp_path):
    with pytest.raises(FileExistsError):
        qualify.Artifacts(tmp_path, 100000)


def test_auditor_imports_no_solver():
    result = subprocess.run(
        [
            str(data.ROOT / ".venv/bin/python"),
            "-c",
            "import sys; from scripts import audit_finite_extracellular_reference; "
            "assert 'scipy.integrate' not in sys.modules; assert 'cells' not in sys.modules",
        ],
        cwd=data.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for name in (
        "tests/finite_extracellular_numerical_checks.py",
        "tests/finite_extracellular_numerical_data.py",
        "scripts/audit_finite_extracellular_reference.py",
    ):
        tree = ast.parse((data.ROOT / name).read_text())
        imported = [
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ]
        assert not any(n.startswith(("cells", "jax", "scipy.integrate")) for n in imported)


def test_depletion_witness_is_not_automatically_passed(panel):
    case = next(c for c in panel[1] if c.id == "single_mono_depletion")
    summary = {case.id: {"minimum_outside_fraction": [1.0] * case.layout.s}}
    assert not check.depletion_witness([case.definition()], summary, panel[0])["pass"]
    summary[case.id]["minimum_outside_fraction"][case.world.species_ids.index("K")] = 0.8
    assert check.depletion_witness([case.definition()], summary, panel[0])["pass"]


def test_frozen_plan_changes_are_refused(monkeypatch, tmp_path):
    plan = json.loads(data.PANEL.read_text())
    plan["accounting_limits"]["countercharge_C"] = 1e-10
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    monkeypatch.setattr(data, "PANEL", path)
    with pytest.raises(ValueError, match="Frozen NUM-009"):
        data.load_panel()
