"""NUM-006 preflight, independent formulations, dense replay and failure semantics."""

import ast
import hashlib
import itertools
import json
from dataclasses import replace
from time import monotonic

import numpy as np
import pytest

from scripts import audit_multispecies_reference as audit
from scripts import qualify_multispecies_reference as qualify
from tests import multispecies_numerical_checks as check
from tests import reference_multispecies_dynamics as ref


@pytest.fixture(scope="module")
def panel():
    return ref.load_panel()


@pytest.fixture(scope="module")
def small_case(panel):
    p = panel[1][7].parameters
    return ref.Case(
        "small_controlled_check",
        p,
        0.03,
        (
            ref.Control(0, (1, 1, 1, 1), 1),
            ref.Control(0.007, (1, 1, 1, 1), 0),
            ref.Control(0.011, (1, 1, 1, 0), 0),
            ref.Control(0.018, (0, 0, 0, 0), 0),
            ref.Control(0.023, (1, 1, 1, 1), 1),
            ref.Control(0.03, (0, 0, 0, 0), 0),
        ),
    )


@pytest.fixture(scope="module")
def small_records(panel, small_case):
    plan = panel[0]
    times = ref.comparison_grid(small_case, plan["candidate"])
    records = {}
    for settings in plan["references"]:
        arrays, _ = ref.integrate_reference(small_case, settings)
        records[settings["id"]] = {
            **arrays,
            "sample_times_s": times,
            "sample_state": ref.sample_record(small_case, arrays, settings["method"], times),
        }
    for dt in plan["candidate"]["steps_s"]:
        arrays, _ = ref.integrate_candidate(small_case, dt)
        records[f"rk4_{dt:g}"] = {
            **arrays,
            "sample_times_s": times,
            "sample_state": ref.sample_record(small_case, arrays, "RK4", times),
        }
    return records


def test_frozen_plan_is_pinned_before_integration(panel):
    plan, cases = panel
    assert hashlib.sha256(ref.PANEL.read_bytes()).hexdigest() == ref.PANEL_SHA256
    assert len(cases) == 14
    assert {c.parameters.species_ids for c in cases} == {("Na", "K", "Cl"), ("Na", "K", "Cl", "Ca")}
    assert plan["trajectory_limits"]["species_overrides"]["Ca"]["amount_fmol"] == 1e-9
    assert plan["resources"]["workers"] == 1
    assert plan["candidate"]["steps_s"] == [0.01, 0.005, 0.0025]


@pytest.mark.parametrize("slot", range(14))
def test_independent_increment_and_absolute_rhs_agree(panel, slot):
    case = panel[1][slot]
    increments = ref.initial_state(case)
    increments[: case.species_count] = np.arange(case.species_count) * 1e-6
    absolute = increments.copy()
    absolute[: case.species_count] += case.parameters.initial_amount_fmol
    first = ref.hyperbolic_rhs(case, case.controls[0], increments)
    second = ref.bernoulli_rhs(case, case.controls[0], absolute)
    np.testing.assert_allclose(first[:-1], second[:-1], rtol=3e-12, atol=1e-14)
    assert first[-1] == pytest.approx(second[-1], rel=3e-12, abs=1e-11)


@pytest.mark.parametrize("bad", [0, -1, np.nan, np.inf, True, 11])
def test_horizon_domain_refused(small_case, bad):
    with pytest.raises(ValueError):
        replace(small_case, horizon_s=bad)


@pytest.mark.parametrize(
    "controls",
    [
        (),
        (ref.Control(0.01, (1, 1, 1, 1), 1),),
        (ref.Control(0, (1, 1, 1, 1), 1), ref.Control(0, (0, 0, 0, 0), 0)),
        (ref.Control(0, (1, 1), 1),),
        (ref.Control(0, (1, 1, 1, 1), 1), ref.Control(0.1, (1, 1, 1, 1), 1)),
    ],
)
def test_invalid_schedule_refused(small_case, controls):
    with pytest.raises(ValueError):
        replace(small_case, controls=controls)


@pytest.mark.parametrize(
    ("time", "leak", "pump"),
    [
        (-1, (1,), 1),
        (np.nan, (1,), 1),
        (0, (), 1),
        (0, (True,), 1),
        (0, (-1,), 1),
        (0, (2,), 1),
        (0, (1,), -1),
        (0, (1,), 2),
    ],
)
def test_invalid_controls_refused(time, leak, pump):
    with pytest.raises(ValueError):
        ref.Control(time, leak, pump)


@pytest.mark.parametrize("bad", [-1, np.nan, np.inf, 0.0300001])
def test_control_queries_outside_domain_refused(small_case, bad):
    with pytest.raises(ValueError):
        small_case.control_at(bad)


def test_grid_keeps_substep_pulse_and_every_offgrid_event(panel):
    case = panel[1][-1]
    for dt in panel[0]["candidate"]["steps_s"]:
        times = ref.candidate_grid(case, dt)
        assert 0.203 in times and 0.204 in times
        assert np.max(np.diff(times)) <= dt * (1 + 1e-12)
        assert times[0] == 0 and times[-1] == 1
    assert case.control_at(0.203).pump == 1
    assert case.control_at(0.204).pump == 0


@pytest.mark.parametrize("dt", [0, -1, np.nan, np.inf, True, 1e-100])
def test_invalid_or_unbounded_step_refused(small_case, dt):
    with pytest.raises(ValueError):
        ref.candidate_grid(small_case, dt)


@pytest.mark.parametrize("kind", ["radau", "bdf", "refined", "rk4_0.01", "rk4_0.005", "rk4_0.0025"])
def test_data_only_dense_replay_and_exact_native_nodes(small_case, small_records, kind):
    arrays = small_records[kind]
    method = "RK4" if kind.startswith("rk4_") else "BDF" if kind == "bdf" else "Radau"
    check.validate_record(small_case.definition(), arrays, method)
    np.testing.assert_array_equal(
        audit.replay(small_case.definition(), arrays, method), arrays["sample_state"]
    )
    at_nodes = ref.sample_record(small_case, arrays, method, arrays["native_times_s"])
    expected = ref.canonical(small_case, arrays["native_state"], absolute=method == "RK4")
    np.testing.assert_array_equal(at_nodes, expected)


@pytest.mark.parametrize("method", ["Radau", "BDF"])
def test_captured_reference_basis_agrees_with_scipy_dense_output(small_case, monkeypatch, method):
    solutions, original = [], ref.solve_ivp

    def capture(*args, **kwargs):
        solution = original(*args, **kwargs)
        solutions.append(solution)
        return solution

    monkeypatch.setattr(ref, "solve_ivp", capture)
    arrays, _ = ref.integrate_reference(
        small_case, {"method": method, "rtol": 1e-11, "atol": 1e-13, "max_step_s": 0.005}
    )
    for solution in solutions:
        probes = solution.t[:-1] + 0.37 * np.diff(solution.t)
        actual = ref.sample_record(small_case, arrays, method, probes)
        np.testing.assert_allclose(actual, solution.sol(probes).T, rtol=0, atol=1e-13)


def test_small_controlled_case_has_valid_accounting_and_independent_agreement(
    panel, small_case, small_records
):
    analysis = check.analyze_case(small_case.definition(), small_records, panel[0])
    assert analysis["references_pass"]
    assert analysis["attempts"]["rk4_0.0025"]["pass"], analysis


def test_disabled_ledgers_and_all_off_intervals_are_exact(small_case, small_records):
    for arrays in small_records.values():
        result = check.control_checks(
            small_case.definition(), arrays["sample_times_s"], arrays["sample_state"]
        )
        assert result["pass"], result


def test_right_endpoint_slope_uses_old_control_and_final_event_changes_only_readout(
    small_case, small_records
):
    arrays = small_records["rk4_0.0025"]
    for index, right in enumerate(arrays["native_times_s"][1:]):
        left = arrays["native_times_s"][index]
        old = small_case.control_at(float(left))
        expected = ref.bernoulli_rhs(small_case, old, arrays["native_state"][index + 1])
        c = arrays["coefficients"][index]
        observed_slope = (c[:, 1] + 2 * c[:, 2] + 3 * c[:, 3]) / (right - left)
        np.testing.assert_allclose(observed_slope, expected, rtol=2e-11, atol=1e-13)
    at_end = ref.bernoulli_rhs(
        small_case, small_case.control_at(small_case.horizon_s), arrays["native_state"][-1]
    )
    np.testing.assert_array_equal(at_end, np.zeros(small_case.size))
    assert np.any(expected != 0)


def test_observation_requests_are_read_only_and_do_not_change_grid(small_case, small_records):
    arrays = small_records["rk4_0.005"]
    copies = {key: value.copy() for key, value in arrays.items()}
    first = ref.sample_record(small_case, arrays, "RK4", [0.001, 0.009, 0.023])
    second = ref.sample_record(small_case, arrays, "RK4", [0.001, 0.002, 0.009, 0.023, 0.025])
    np.testing.assert_array_equal(first, second[[0, 2, 3]])
    for key in copies:
        np.testing.assert_array_equal(copies[key], arrays[key])


@pytest.mark.parametrize("queries", [[-1], [1], [np.nan], [0.02, 0.01], [[0.01]], [0] * 100001])
def test_bad_observation_queries_refused(small_case, small_records, queries):
    with pytest.raises(ValueError):
        ref.sample_record(small_case, small_records["rk4_0.005"], "RK4", queries)


def test_interior_cubic_domain_failure_is_not_hidden_by_valid_endpoints(small_case, small_records):
    original = small_records["rk4_0.005"]
    arrays = {key: value.copy() for key, value in original.items()}
    # Ca starts positive at both ends, but this synthetic cubic dips below zero.
    arrays["coefficients"][0, 3, :4] = [0.001, -0.01, 0.01, 0]
    result = check.candidate_polynomial_domain(small_case.definition(), arrays)
    assert not result["pass"] and result["minimum_amount_fmol"] < 0


@pytest.mark.parametrize("coordinates", ["increment", "absolute"])
def test_invalid_trial_is_rejected_even_when_routes_are_off(small_case, coordinates):
    absolute = coordinates == "absolute"
    state = ref.initial_state(small_case, absolute=absolute)
    state[3] = 0 if absolute else -small_case.parameters.initial_amount_fmol[3]
    control = ref.Control(0, (0, 0, 0, 0), 0)
    function = ref.bernoulli_rhs if absolute else ref.hyperbolic_rhs
    with pytest.raises(ValueError, match="positive"):
        function(small_case, control, state)


@pytest.mark.parametrize("setting", [0, True, 100001])
def test_invalid_work_allowance_refused(setting):
    with pytest.raises(ValueError):
        ref.Budget(max_calls=setting)


def test_deadline_and_jacobian_calls_share_explicit_work_budget(small_case):
    expired = ref.Budget(deadline=monotonic() - 1)
    with pytest.raises(ref.ResourceLimit, match="wall-time"):
        ref.integrate_candidate(small_case, 0.005, budget=expired)
    budget = ref.Budget(max_calls=1)
    with pytest.raises(ref.ResourceLimit, match="RHS budget"):
        ref.integrate_reference(
            small_case,
            {"method": "BDF", "rtol": 1e-11, "atol": 1e-13, "max_step_s": 0.05},
            budget=budget,
        )
    assert budget.calls == 2


def test_numerical_checker_detects_wrong_charge_energy_and_disabled_ledger(
    small_case, small_records, panel
):
    arrays = small_records["rk4_0.005"]
    values = arrays["sample_state"].copy()
    values[-1, 0] += 1e-6
    result = check.inspect_samples(
        small_case.definition(), arrays["sample_times_s"], values, panel[0]["accounting_limits"]
    )
    assert not result["pass"] and result["charge_residual_V"] > 1e-8
    values = arrays["sample_state"].copy()
    values[-1, -1] += 1e-3
    assert not check.inspect_samples(
        small_case.definition(), arrays["sample_times_s"], values, panel[0]["accounting_limits"]
    )["pass"]
    values = arrays["sample_state"].copy()
    values[(arrays["sample_times_s"] > 0.018) & (arrays["sample_times_s"] < 0.023), 7] += 1e-9
    assert not check.control_checks(small_case.definition(), arrays["sample_times_s"], values)[
        "pass"
    ]


@pytest.mark.parametrize(
    "mutation", ["missing", "dtype", "initial", "degree", "denominator", "event"]
)
def test_malformed_dense_record_refused(small_case, small_records, mutation):
    arrays = {key: value.copy() for key, value in small_records["rk4_0.005"].items()}
    if mutation == "missing":
        arrays.pop("shift")
    elif mutation == "dtype":
        arrays["native_state"] = arrays["native_state"].astype(np.float32)
    elif mutation == "initial":
        arrays["native_state"][0, -1] = 1
    elif mutation == "degree":
        arrays["degree"][0] = 5
    elif mutation == "denominator":
        arrays["denominator"][0, 0] = 0
    else:
        slot = np.flatnonzero(arrays["native_times_s"] == 0.007)[0]
        arrays["native_times_s"][slot] = 0.0071
    with pytest.raises(ValueError):
        check.validate_record(small_case.definition(), arrays, "RK4")


@pytest.mark.parametrize("order", list(itertools.permutations(range(4)))[:6])
def test_rhs_species_permutation_is_a_storage_change(small_case, order):
    p = small_case.parameters
    permuted = replace(
        p,
        **{
            key: tuple(getattr(p, key)[i] for i in order)
            for key in (
                "species_ids",
                "valence",
                "initial_amount_fmol",
                "bath_mM",
                "permeability_m_per_s",
                "stoichiometry",
            )
        },
    )
    case = replace(
        small_case,
        parameters=permuted,
        controls=tuple(
            replace(c, leak=tuple(c.leak[i] for i in order)) for c in small_case.controls
        ),
    )
    original = ref.hyperbolic_rhs(small_case, small_case.controls[0], ref.initial_state(small_case))
    result = ref.hyperbolic_rhs(case, case.controls[0], ref.initial_state(case))
    indices = [*order, *(i + 4 for i in order), 8, 9]
    np.testing.assert_allclose(result, original[indices], rtol=3e-12, atol=1e-14)


def synthetic_analyses(plan):
    return {
        case["id"]: {
            "references_pass": True,
            "attempts": {
                f"rk4_{dt:g}": {
                    "pass": True,
                    "observed_comparison": {"errors": {"voltage_V": error}},
                }
                for dt, error in zip(plan["candidate"]["steps_s"], (1e-8, 1e-9, 1e-10), strict=True)
            },
        }
        for case in plan["cases"]
    }


def test_selection_requires_all_cases_and_an_actual_passing_refinement(panel):
    plan = panel[0]
    analyses = synthetic_analyses(plan)
    assert check.select_candidate(analyses, plan)["selected_dt_s"] == 0.01
    first = next(iter(analyses.values()))
    first["attempts"]["rk4_0.01"]["pass"] = False
    assert check.select_candidate(analyses, plan)["selected_dt_s"] == 0.005
    first["attempts"]["rk4_0.005"]["pass"] = False
    assert check.select_candidate(analyses, plan)["selected_dt_s"] is None
    assert check.select_candidate({}, plan)["status"] == "not_qualified"


def test_reference_failure_cannot_be_hidden_by_candidate_agreement(panel):
    analyses = synthetic_analyses(panel[0])
    next(iter(analyses.values()))["references_pass"] = False
    assert check.select_candidate(analyses, panel[0])["selected_dt_s"] is None


def test_refinement_floor_prevents_roundoff_ratio_requirements(panel):
    analyses = synthetic_analyses(panel[0])
    for analysis in analyses.values():
        for entry in analysis["attempts"].values():
            entry["observed_comparison"]["errors"]["voltage_V"] = 1e-12
    assert check.select_candidate(analyses, panel[0])["selected_dt_s"] == 0.01


def test_new_artifacts_are_exclusive_and_quota_failure_keeps_evidence(tmp_path):
    sink = qualify.Artifacts(tmp_path / "out", 70000)
    sink.write("kept.bin", b"kept")
    with pytest.raises(FileExistsError):
        sink.write("kept.bin", b"overwrite")
    with pytest.raises(ref.ResourceLimit):
        sink.write("large.bin", b"x" * 5000)
    assert (sink.path / "kept.bin").read_bytes() == b"kept"
    assert not (sink.path / "large.bin").exists()
    with pytest.raises(FileExistsError):
        qualify.Artifacts(sink.path, 70000)


def test_failed_session_has_a_stopping_receipt_and_no_qualification(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise ref.ResourceLimit("test stop before integration")

    monkeypatch.setattr(ref, "integrate_reference", fail)
    output = tmp_path / "stopped"
    with pytest.raises(ref.ResourceLimit):
        qualify.run(output)
    failure = json.loads((output / "failure.json").read_text())
    assert failure["status"] == "stopped"
    assert failure["attempt"] == "radau" and not failure["completed_cases"]
    assert (output / "sources.zip").exists()
    assert not (output / "verification.json").exists()


def test_audit_and_analysis_do_not_import_solver_or_production_code():
    for relative in (
        "scripts/audit_multispecies_reference.py",
        "tests/multispecies_numerical_checks.py",
    ):
        tree = ast.parse((ref.ROOT / relative).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(a.name.startswith(("scipy", "cells", "jax")) for a in node.names)
            if isinstance(node, ast.ImportFrom):
                assert not node.module.startswith(("scipy", "cells", "jax"))
                assert not any(a.name == "reference_multispecies_dynamics" for a in node.names)


def test_altered_panel_identity_refused(tmp_path, monkeypatch):
    changed = tmp_path / "panel.json"
    changed.write_bytes(ref.PANEL.read_bytes() + b"\n")
    monkeypatch.setattr(ref, "PANEL", changed)
    with pytest.raises(ValueError, match="panel identity"):
        ref.load_panel()
