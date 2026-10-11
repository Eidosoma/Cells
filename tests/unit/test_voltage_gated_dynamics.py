"""NUM-007 preflight on smaller synthetic fixtures; never run the scientific panel."""

import ast
import copy
import hashlib
import json
import shutil
from dataclasses import replace
from time import monotonic

import numpy as np
import pytest

from scripts import audit_voltage_gated_reference as audit
from scripts import qualify_voltage_gated_reference as qualify
from tests import reference_multispecies_dynamics as old
from tests import reference_voltage_gated_dynamics as ref
from tests import voltage_gated_numerical_checks as check


@pytest.fixture(scope="module")
def panel():
    return ref.load_panel()


@pytest.fixture(scope="module")
def small(panel):
    base = panel[1][5]
    return ref.Case(
        "small_numerical_preflight",
        base.parameters,
        0.015,
        (
            ref.Control(0, (1, 1, 1, 1), 1, 1),
            ref.Control(0.0033, (1, 1, 1, 1), 0, 0),
            ref.Control(0.0034, (1, 1, 1, 0), 0, 1),
            ref.Control(0.0077, (0, 0, 0, 0), 0, 0),
            ref.Control(0.0111, (1, 1, 1, 1), 1, 1),
            ref.Control(0.015, (0, 0, 0, 0), 0, 0),
        ),
        replace(base.channel, initial_gate=ref.spec.Gate(0.3, 0.7)),
    )


@pytest.fixture(scope="module")
def small_records(panel, small):
    plan = panel[0]
    samples = ref.comparison_grid(small, plan["candidate"])
    records, stats = {}, {}
    for setting in plan["references"]:
        arrays, stats[setting["id"]] = ref.integrate_reference(small, setting)
        records[setting["id"]] = arrays | {
            "sample_times_s": samples,
            "sample_state": ref.sample_record(small, arrays, setting["method"], samples),
        }
    for dt in plan["candidate"]["steps_s"]:
        name = f"rk4_{dt:g}"
        arrays, stats[name] = ref.integrate_candidate(small, dt)
        assert stats[name]["status"] == "complete"
        records[name] = arrays | {
            "sample_times_s": samples,
            "sample_state": ref.sample_record(small, arrays, "RK4", samples),
        }
    return records, stats


def test_frozen_pre_evaluation_scope(panel):
    plan, cases = panel
    assert hashlib.sha256(ref.PANEL.read_bytes()).hexdigest() == ref.PANEL_SHA256
    assert len(cases) == 14
    assert plan["candidate"]["steps_s"] == [0.002, 0.001, 0.0005, 0.00025]
    assert plan["resources"]["workers"] == 1
    assert max(c.horizon_s for c in cases) == 2
    assert cases[0].channel.initial_gate == ref.spec.Gate(0, 1)
    assert cases[5].channel.initial_gate == ref.spec.Gate(0, 1)


@pytest.mark.parametrize("index", range(14))
def test_independent_native_unit_and_bernoulli_rhs_agree(panel, index):
    case = panel[1][index]
    delta = ref.initial_state(case)
    delta[: case.species_count] = -np.asarray(case.parameters.valence) * 1e-8
    absolute = delta.copy()
    absolute[: case.species_count] += case.parameters.initial_amount_fmol
    actual = ref.hyperbolic_rhs(case, case.controls[0], delta)
    expected = ref.bernoulli_rhs(case, case.controls[0], absolute)
    np.testing.assert_allclose(actual, expected, rtol=2e-9, atol=1e-10)


def test_reference_does_not_call_gate_or_flux_evaluator(small, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Independent reference called candidate evaluator")

    monkeypatch.setattr(ref.spec, "evaluate", forbidden)
    monkeypatch.setattr(ref.spec, "kinetics", forbidden)
    assert np.isfinite(ref.hyperbolic_rhs(small, small.controls[0], ref.initial_state(small))).all()


@pytest.mark.parametrize("bad", [-1e-15, 1.000000000000001, np.nan, np.inf])
@pytest.mark.parametrize("gate", [0, 1])
@pytest.mark.parametrize("enabled", [False, True])
def test_every_real_gate_is_checked_even_when_disabled(small, bad, gate, enabled):
    state = ref.initial_state(small)
    state[small.gate_start + gate] = bad
    control = replace(small.controls[0], availability=float(enabled))
    with pytest.raises(ref.DomainViolation):
        ref.hyperbolic_rhs(small, control, state)


@pytest.mark.parametrize("bad", [-0.121, 0.061])
def test_gate_voltage_domain_is_narrower_than_ionic_domain(small, bad):
    state = ref.initial_state(small)
    state[0] = (bad - small.parameters.initial_voltage_V) * small.parameters.capacitance_F / old.QF
    with pytest.raises(ref.DomainViolation, match="Voltage"):
        ref.domain(small, state)


@pytest.mark.parametrize("bad", [0, -1, True, np.nan, np.inf, 2.001])
def test_horizon_refused(small, bad):
    with pytest.raises(ValueError):
        replace(small, horizon_s=bad)


@pytest.mark.parametrize("bad", [-1, 1.01, True, np.nan, np.inf])
def test_availability_refused(bad):
    with pytest.raises(ValueError):
        ref.Control(0, (1,), 1, bad)


def test_mutable_or_nonchannel_controls_refused(small):
    for controls in (list(small.controls), (old.Control(0, (1, 1, 1, 1), 1),), ()):
        with pytest.raises(ValueError):
            replace(small, controls=controls)


@pytest.mark.parametrize("bad", [0, -1, True, np.nan, np.inf, 1e-100])
def test_invalid_or_unbounded_mesh_refused(small, bad):
    with pytest.raises(ValueError):
        ref.candidate_grid(small, bad)


@pytest.mark.parametrize("index", range(14))
def test_registered_grids_keep_events_and_fit_budget(panel, index):
    plan, cases = panel
    case = cases[index]
    samples = ref.comparison_grid(case, plan["candidate"])
    assert len(samples) <= plan["resources"]["max_samples_per_case"]
    for dt in plan["candidate"]["steps_s"]:
        mesh = ref.candidate_grid(case, dt)
        assert all(c.time_s in mesh and c.time_s in samples for c in case.controls)
        assert np.max(np.diff(mesh)) <= dt * (1 + 1e-12)


@pytest.mark.parametrize(
    "name", ["radau", "bdf", "refined", "rk4_0.002", "rk4_0.001", "rk4_0.0005", "rk4_0.00025"]
)
def test_data_only_replay_and_exact_nodes(small, small_records, name):
    records, _ = small_records
    arrays = records[name]
    kind = "RK4" if name.startswith("rk4_") else "BDF" if name == "bdf" else "Radau"
    check.validate_record(small.definition(), arrays, kind)
    np.testing.assert_array_equal(
        audit.replay(small.definition(), arrays, kind), arrays["sample_state"]
    )
    actual = ref.sample_record(small, arrays, kind, arrays["native_times_s"])
    np.testing.assert_array_equal(
        actual, ref.canonical(small, arrays["native_state"], absolute=kind == "RK4")
    )


@pytest.mark.parametrize("method", ["Radau", "BDF"])
def test_dense_capture_matches_pinned_scipy(small, panel, monkeypatch, method):
    original, results = ref.solve_ivp, []

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        results.append(result)
        return result

    monkeypatch.setattr(ref, "solve_ivp", capture)
    setting = next(s for s in panel[0]["references"] if s["method"] == method)
    arrays, _ = ref.integrate_reference(small, setting)
    for result in results:
        samples = result.t[:-1] + 0.37 * np.diff(result.t)
        np.testing.assert_allclose(
            ref.sample_record(small, arrays, method, samples),
            result.sol(samples).T,
            rtol=0,
            atol=1e-13,
        )


def test_small_fixture_accounting_and_fine_comparison(panel, small, small_records):
    records, stats = small_records
    analysis = check.analyze_case(small.definition(), records, stats, panel[0])
    assert analysis["references_pass"]
    assert analysis["attempts"]["rk4_0.00025"]["pass"], analysis


def test_transport_off_retains_gates_and_ledgers(small, small_records):
    arrays = small_records[0]["refined"]
    times, values = arrays["sample_times_s"], arrays["sample_state"]
    chosen = values[(times >= 0.0077) & (times <= 0.0111)]
    np.testing.assert_array_equal(
        chosen[:, : small.gate_start],
        np.broadcast_to(chosen[0, : small.gate_start], chosen[:, : small.gate_start].shape),
    )
    assert np.all(chosen[:, -1] == chosen[0, -1])
    assert not np.array_equal(
        chosen[0, small.gate_start : small.gate_start + 2],
        chosen[-1, small.gate_start : small.gate_start + 2],
    )


def test_separate_channel_history_is_required(small, small_records, panel):
    arrays = small_records[0]["refined"]
    wrong = arrays["sample_state"].copy()
    wrong[:, -1] = 0
    result = check.inspect_samples(
        small.definition(), arrays["sample_times_s"], wrong, panel[0]["accounting_limits"]
    )
    assert not result["pass"]


def test_unsampled_gate_polynomial_extremum_is_checked(small, small_records):
    arrays = {k: v.copy() for k, v in small_records[0]["rk4_0.00025"].items()}
    arrays["coefficients"][0, small.gate_start, :4] = (0.5, 2.4, -2.4, 0)
    result = check.candidate_polynomial_domain(small.definition(), arrays)
    assert result["m_range"][1] > 1
    assert not result["pass"]


def test_rejected_coarse_gate_keeps_exact_stage_and_prefix(panel):
    base = panel[1][-2]
    case = replace(base, id="tiny_gate_rejection", horizon_s=0.006)
    arrays, stats = ref.integrate_candidate(case, 0.002)
    assert stats["status"] == "rejected"
    assert stats["rejected_trial"]["stage"] == "k4"
    assert len(arrays["native_times_s"]) == 1
    record = arrays | {"sample_times_s": np.empty(0), "sample_state": np.empty((0, case.size))}
    check.validate_record(case.definition(), record, "RK4", complete=False)
    assert check.rejection_check(
        json.loads(json.dumps(case.definition())), record, json.loads(json.dumps(stats))
    )["rejection_domain_confirmed"]
    altered = copy.deepcopy(stats)
    altered["rejected_trial"]["absolute_state"][case.gate_start] = 0.5
    with pytest.raises(ValueError, match="does not violate"):
        check.rejection_check(case.definition(), record, altered)


def test_channel_off_reduces_to_unchanged_ionic_reference(small):
    control = ref.Control(0, (1, 1, 1, 1), 1, 0)
    case = replace(small, controls=(control,))
    delta = ref.initial_state(case)
    actual = ref.hyperbolic_rhs(case, control, delta)
    base = old.hyperbolic_rhs(case, control, delta)
    np.testing.assert_array_equal(actual[: case.gate_start], base)
    assert actual[-1] == 0
    assert np.any(actual[case.gate_start : case.gate_start + 2] != 0)


@pytest.mark.parametrize("mode", ["calls", "deadline"])
def test_resource_limits_stop_work(small, mode):
    budget = ref.Budget(max_calls=1) if mode == "calls" else ref.Budget(deadline=monotonic() - 1)
    with pytest.raises(ref.ResourceLimit):
        ref.integrate_candidate(small, 0.001, budget=budget)


def test_artifact_destination_refuses_overwrite(tmp_path):
    destination = tmp_path / "evidence"
    artifact = qualify.Artifacts(destination, 100000)
    artifact.json("kept.json", {"retained": True})
    with pytest.raises(FileExistsError):
        qualify.Artifacts(destination, 100000)
    with pytest.raises(FileExistsError):
        artifact.json("kept.json", {"retained": False})
    assert json.loads((destination / "kept.json").read_text())["retained"]


def test_no_production_or_solver_import_in_data_only_checks():
    for path in (
        ref.ROOT / "tests/voltage_gated_numerical_checks.py",
        ref.ROOT / "scripts/audit_voltage_gated_reference.py",
    ):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax", "scipy"))
                assert all("dynamics" not in name.name for name in node.names)


def test_no_eligible_refinement_pair_means_no_selection(panel, small, small_records):
    plan = copy.deepcopy(panel[0])
    plan["cases"] = [{"id": small.id}]
    analysis = check.analyze_case(small.definition(), *small_records, plan)
    for name, entry in analysis["attempts"].items():
        if name.startswith("rk4_"):
            entry["pass"] = name == "rk4_0.00025"
    assert check.select_candidate({small.id: analysis}, plan)["selected_dt_s"] is None


def test_missing_or_changed_frozen_panel_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "panel.json"
    path.write_text("{}\n")
    monkeypatch.setattr(ref, "PANEL", path)
    with pytest.raises(ValueError, match="Frozen NUM-007"):
        ref.load_panel()


def test_bad_observation_is_a_retained_verdict_not_a_session_exception(small, small_records, panel):
    arrays = small_records[0]["rk4_0.00025"]
    values = arrays["sample_state"].copy()
    values[1, small.gate_start] = 1.000001
    result = check.inspect_samples(
        small.definition(), arrays["sample_times_s"], values, panel[0]["accounting_limits"]
    )
    assert not result["pass"] and not result["domain_pass"]


def test_final_time_control_changes_readout_not_trajectory(small):
    changed = replace(
        small, controls=small.controls[:-1] + (ref.Control(small.horizon_s, (1, 1, 1, 1), 1, 1),)
    )
    first, _ = ref.integrate_candidate(small, 0.0005)
    second, _ = ref.integrate_candidate(changed, 0.0005)
    for key in first:
        np.testing.assert_array_equal(first[key], second[key])
    assert small.control_at(small.horizon_s).availability == 0
    assert changed.control_at(small.horizon_s).availability == 1


def test_observations_do_not_alter_retained_gates(small, small_records):
    arrays = small_records[0]["rk4_0.00025"]
    saved = arrays["native_state"].copy()
    ref.sample_record(small, arrays, "RK4", [0.000003, 0.01337, 0.015])
    np.testing.assert_array_equal(arrays["native_state"], saved)


def test_bath_material_accounting_includes_disabled_channel_past(small, small_records, panel):
    arrays = small_records[0]["refined"]
    values, times = arrays["sample_state"], arrays["sample_times_s"]
    selected = (times >= 0.0077) & (times <= 0.0111)
    assert np.any(values[selected, -1] != 0)
    assert check.inspect_samples(
        small.definition(), times[selected], values[selected], panel[0]["accounting_limits"]
    )["pass"]


def test_named_species_permutation_keeps_coupled_rhs(small):
    order = [3, 1, 0, 2]
    p = small.parameters
    fields = (
        "species_ids",
        "valence",
        "initial_amount_fmol",
        "bath_mM",
        "permeability_m_per_s",
        "stoichiometry",
    )
    permuted = replace(p, **{key: tuple(getattr(p, key)[i] for i in order) for key in fields})
    controls = tuple(replace(c, leak=tuple(c.leak[i] for i in order)) for c in small.controls)
    case = replace(small, parameters=permuted, controls=controls)
    expected = ref.hyperbolic_rhs(small, small.controls[0], ref.initial_state(small))
    actual = ref.hyperbolic_rhs(case, case.controls[0], ref.initial_state(case))
    positions = order + [4 + i for i in order] + list(range(8, case.size))
    np.testing.assert_allclose(actual, expected[positions], rtol=2e-13, atol=1e-13)


def test_shortened_synthetic_session_roundtrip_and_budget_receipt(panel, tmp_path, monkeypatch):
    original_root = ref.ROOT
    root = tmp_path / "source_fixture"
    for name in qualify.SOURCE_FILES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original_root / name, target)
    plan = copy.deepcopy(panel[0])
    plan["scope"] = "shortened synthetic unit-test fixture, not NUM-007 qualification"
    for profile in plan["profiles"].values():
        profile["horizon_s"] = 0.004
        profile["controls"] = profile["controls"][:1]
    protocol = root / audit.PROTOCOL_SOURCE
    protocol.write_bytes(qualify.json_bytes(plan))
    digest = hashlib.sha256(protocol.read_bytes()).hexdigest()
    for module in (ref, qualify, audit):
        monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(ref, "PANEL", protocol)
    monkeypatch.setattr(ref, "PANEL_SHA256", digest)
    monkeypatch.setattr(audit, "PANEL_SHA256", digest)
    destination = tmp_path / "shortened_session"
    result = qualify.run(destination)
    assert len(result["completed_cases"]) == 14
    report = audit.audit(destination)
    assert report["status"] == "pass" and not report["solver_rerun"]
    assert report["replayed_arrays"] + report["rejected_candidates"] == 98

    def exhausted(*args, **kwargs):
        raise ref.ResourceLimit("injected preflight budget stop")

    monkeypatch.setattr(ref, "integrate_reference", exhausted)
    failed = tmp_path / "budget_stop"
    with pytest.raises(ref.ResourceLimit, match="preflight budget"):
        qualify.run(failed)
    receipt = json.loads((failed / "failure.json").read_text())
    assert receipt["status"] == "stopped"
    assert receipt["completed_cases"] == []
    assert (failed / "sources.zip").exists()
    assert not (failed / "verification.json").exists()
