"""Design and evidence checks only; these are not longer-duration simulations."""

import copy
import importlib

import check_plan as plan
import pytest


@pytest.fixture(scope="module")
def inputs():
    proposal = plan.e.read(plan.PROPOSAL)
    prior = plan.e.read(plan.evidence.CAPTURE / "registration.json")["protocol"]
    return proposal, prior


def test_actual_closed_capture_authenticates():
    with plan.e.model_fence():
        r, sources, done = plan.authenticate()
    assert len(r["sources_sha256"]) == 641 and len(sources) == 55
    assert done["failed_comparisons"] == 0
    assert done["native_law_transfer_conservation_link_comparisons"] == 10610676


def test_ten_ms_matrix_and_common_grid(inputs):
    result = plan.validate(*inputs)
    assert result["native_observed_updates"] == 67200
    assert result["native_total_updates"] == 134400
    assert result["cells_primary_updates"] == 9600
    assert result["cells_restart_suffix_updates"] == 1200
    assert result["ten_ms_reference_samples_at_unchanged_cadence"] == 1601
    assert len(result["candidate_observation_times_s"]) == 41
    assert result["candidate_observation_times_s"][-1] == 0.01
    assert set(inputs[1]["common_times_s"]) <= set(result["candidate_observation_times_s"])


@pytest.mark.parametrize(
    "flag",
    [
        "runnable",
        "physics_changed",
        "scientific_tolerances_changed",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ],
)
def test_unregistered_execution_or_scientific_change_refused(inputs, flag):
    proposal, prior = copy.deepcopy(inputs)
    proposal[flag] = True
    with pytest.raises(ValueError, match="Unregistered"):
        plan.validate(proposal, prior)


@pytest.mark.parametrize(
    "stage,field,value",
    [
        (0, "duration_s", 0.01),
        (0, "require_every_record_exact_including_signed_zero", False),
        (0, "offline_codec_before_live_capture", False),
        (0, "runtime_and_total_artifact_caps", {"seconds": 10}),
        (1, "native_steps_s", [1e-3, 5e-4, 2.5e-4]),
        (1, "observation_interval_s", 0.00027),
        (1, "planned_reference_solves", 6),
        (1, "restart_time_s", 0.006),
        (1, "native_restart_qualification", True),
        (1, "equate_changed_horizon_raw_native_labels", True),
        (2, "automatic_horizon_extension", True),
        (4, "biological_parameters_or_tolerances_selected", True),
    ],
)
def test_changed_stage_scope_refused(inputs, stage, field, value):
    proposal, prior = copy.deepcopy(inputs)
    proposal["stages"][stage][field] = value
    with pytest.raises(ValueError):
        plan.validate(proposal, prior)


@pytest.mark.parametrize(
    "duration,step",
    [(0, 1), (1, 0), (-1, 0.01), (1, float("nan")), (float("inf"), 1), (1, 0.3), (True, 0.1)],
)
def test_invalid_or_offgrid_clock_refused(duration, step):
    with pytest.raises(ValueError):
        plan.whole_steps(duration, step)


@pytest.mark.parametrize("name", ["cells", "betse", "jax", "coupled_reference", "refinement_check"])
def test_planning_cannot_import_a_solver(name):
    with plan.e.model_fence(), pytest.raises(ImportError):
        importlib.import_module(name)


def test_review_summary_does_not_promote_roundoff_to_convergence():
    result = plan.summarize_review(plan.e.read(plan.AUDIT / "review.json"))
    assert len(result["finest_native"]) == 6
    assert result["floor_limited_groups"] == 23
    main = result["finest_native"]["pump_leak"]
    assert main["max_energy_balance_defect_pJ"] < 1e-7
    assert main["energy_budget_ratio"] < 1
    assert all(0.99 < x < 1.01 for x in result["pump_leak_energy_refinement"]["observed_orders"])


def test_resource_scaling_uses_measured_bytes_not_desired_compression(tmp_path, inputs):
    plan.e.write(tmp_path / "reuse-complete.json", {"elapsed_seconds": 8})
    plan.e.write(tmp_path / "betse-complete.json", {"elapsed_seconds": 434})
    done = {"elapsed_seconds": 337}
    estimate = plan.resource_estimates(inputs[1], tmp_path, done, [0.01, 1.0])
    a, b = estimate["linear_legacy_recording_projections"]
    assert a["scale"] == 10 and b["scale"] == 1000
    assert a["naive_native_phase_seconds"] == 4260
    assert b["naive_capture_bytes"] == a["naive_capture_bytes"] * 100
    assert estimate["measured_future_performance"] is False
    assert estimate["approved_resource_caps"] is False


def test_plan_cannot_overwrite_old_evidence(inputs):
    with pytest.raises(ValueError, match="Fresh"):
        plan.prepare(plan.AUDIT, plan.ROOT / "reports/ref-005c-audit-checks-01.xml")
