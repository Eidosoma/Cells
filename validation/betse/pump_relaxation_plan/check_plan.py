"""Source-bound pilot closeout facts and planning estimates; never integrate."""

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pump_pilot_audit"))
import audit_evidence as evidence  # noqa: E402

e, ROOT = evidence.e, evidence.ROOT
AUDIT = ROOT / "runs/ref-005c-refined-pump-audit-2026-09-16/audit-01"
AUDIT_SHA = "e2e67df2b6118cdacfcbf4f23357a972bcb6ecae7d4eacad3f02956ab4369bc1"
PROPOSAL = HERE / "proposal.json"


def whole_steps(duration, step):
    e.require(
        type(duration) in (int, float)
        and type(step) in (int, float)
        and math.isfinite(duration)
        and math.isfinite(step)
        and duration > 0
        and step > 0,
        "Invalid clock",
    )
    count = round(duration / step)
    e.require(
        count > 0 and math.isclose(duration / step, count, rel_tol=0, abs_tol=1e-9),
        "Off-grid clock",
    )
    return count


def validate(proposal, prior):
    e.require(
        proposal["schema"] == "cells.pump_relaxation_proposal@1"
        and proposal["status"] == "design_only_not_an_execution_registration"
        and proposal["prior_audit_completion_sha256"] == AUDIT_SHA,
        "Proposal identity",
    )
    for flag in (
        "runnable",
        "physics_changed",
        "scientific_tolerances_changed",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ):
        e.require(proposal[flag] is False, "Unregistered execution or scientific change")
    e.require(
        proposal["model"] == "finite_extracellular@2"
        and proposal["backend"] == "cpu"
        and proposal["precision"] == "float64",
        "Model/device scope",
    )
    stages = proposal["stages"]
    e.require([s["id"] for s in stages] == ["R0", "R1", "R2", "R3", "B0"], "Stage order")
    for stage in stages[:2]:
        e.require(
            stage["variants"] == prior["variants"]
            and stage["native_steps_s"] == prior["native_steps_s"]
            and stage["modes"] == ["observed", "unobserved"]
            and stage["planned_native_runs"] == 36,
            "Native scope",
        )
        e.require(stage["runtime_and_total_artifact_caps"] is None, "Unmeasured launch budget")
        for step in stage["native_steps_s"]:
            whole_steps(stage["duration_s"], step)
    codec, numerical, relaxation, perturbation, biology = stages
    e.require(
        codec["duration_s"] == prior["duration_s"] == 0.001
        and codec["offline_codec_before_live_capture"] is True
        and codec["require_every_record_exact_including_signed_zero"] is True
        and codec["require_real_buffer_and_rss_measurements"] is True,
        "Recorder guard",
    )
    e.require(
        numerical["duration_s"] == 0.01
        and numerical["cells_steps_s"] == prior["cells_steps_s"]
        and numerical["cells_eager_step_s"] == prior["cells_eager_step_s"]
        and numerical["planned_cells_trajectories"] == 24
        and numerical["planned_reference_solves"] == 18
        and numerical["reference_settings"] == [v["id"] for v in prior["reference"]["solves"]],
        "Numerical scope",
    )
    e.require(
        numerical["restart_step_s"] == prior["restart_step_s"]
        and numerical["restart_time_s"] == numerical["duration_s"] / 2
        and numerical["planned_restart_suffixes"] == 6
        and numerical["native_restart_qualification"] is False
        and numerical["equate_changed_horizon_raw_native_labels"] is False
        and numerical["launch_requires_new_registration"] is True,
        "Restart/clock distinction",
    )
    obs = whole_steps(numerical["duration_s"], numerical["observation_interval_s"])
    for step in numerical["native_steps_s"] + numerical["cells_steps_s"]:
        whole_steps(numerical["observation_interval_s"], step)
        whole_steps(numerical["restart_time_s"], step)
    e.require(
        relaxation["automatic_horizon_extension"] is False
        and relaxation["steady_state_thresholds_and_window"] is None
        and perturbation["amplitude_and_schedule"] is None
        and biology["biological_parameters_or_tolerances_selected"] is False,
        "Unregistered physiology/perturbation claim",
    )
    count = len(numerical["variants"])
    native_updates = count * sum(
        whole_steps(numerical["duration_s"], h) for h in numerical["native_steps_s"]
    )
    cells_updates = count * (
        sum(whole_steps(numerical["duration_s"], h) for h in numerical["cells_steps_s"])
        + whole_steps(numerical["duration_s"], numerical["cells_eager_step_s"])
    )
    return dict(
        candidate_observation_times_s=[
            i * numerical["observation_interval_s"] for i in range(obs + 1)
        ],
        native_observed_updates=native_updates,
        native_total_updates=2 * native_updates,
        cells_primary_updates=cells_updates,
        cells_restart_suffix_updates=count
        * whole_steps(
            numerical["duration_s"] - numerical["restart_time_s"], numerical["restart_step_s"]
        ),
        ten_ms_reference_samples_at_unchanged_cadence=whole_steps(
            numerical["duration_s"], prior["reference"]["sample_dt_s"]
        )
        + 1,
    )


def authenticate():
    e.require(e.sha(AUDIT / "completion.json") == AUDIT_SHA, "Audit identity changed")
    done, registration = e.read(AUDIT / "completion.json"), e.read(AUDIT / "registration.json")
    e.require(
        done["status"] == "bounded_refined_pump_pilot_independently_closed"
        and done["failed_comparisons"] == 0
        and done["bounded_1ms_pilot_qualified"] is True,
        "Pilot not closed",
    )
    files = evidence.diagnostic.inventory(AUDIT)
    e.require(
        set(files)
        == set(done["files_sha256"])
        | {"completion.json", "launch.json", "runner.stdout.log", "runner.stderr.log"},
        "Audit membership",
    )
    evidence.hashes(AUDIT, done["files_sha256"])
    evidence.capsule(AUDIT, registration["sources_sha256"])
    e.require(
        e.sha(AUDIT / "registration.json") == e.read(AUDIT / "launch.json")["registration_sha256"],
        "Audit registration link",
    )
    e.require(
        e.software(ROOT / registration["software"]["path"], 47) == registration["software"],
        "Audit software receipt",
    )
    r, sources, captured_files = evidence.authenticate()
    e.require(captured_files == registration["capture_files_sha256"], "Reviewed capture changed")
    return r, sources, done


def resource_estimates(prior, capture, completed, horizons):
    paths = [p for p in capture.rglob("*") if p.is_file()]
    largest = max(paths, key=lambda p: p.stat().st_size)
    used = sum(p.stat().st_size for p in paths)
    begin = e.read(capture / "reuse-complete.json")["elapsed_seconds"]
    end = e.read(capture / "betse-complete.json")["elapsed_seconds"]
    baseline = dict(
        duration_s=prior["duration_s"],
        all_capture_bytes=used,
        largest_file_bytes=largest.stat().st_size,
        largest_file=str(largest.relative_to(capture)),
        native_phase_seconds=end - begin,
        independent_review_seconds=completed["elapsed_seconds"],
    )
    projections = []
    for duration in horizons:
        e.require(math.isfinite(duration) and duration > 0, "Projection horizon")
        factor = duration / prior["duration_s"]
        projections.append(
            dict(
                duration_s=duration,
                scale=factor,
                naive_capture_bytes=math.ceil(used * factor),
                naive_largest_file_bytes=math.ceil(largest.stat().st_size * factor),
                naive_native_phase_seconds=(end - begin) * factor,
                naive_independent_review_seconds=completed["elapsed_seconds"] * factor,
                violates_old_per_file_cap=largest.stat().st_size * factor
                > prior["resources"]["per_file_bytes"],
                violates_old_aggregate_cap=used * factor > prior["resources"]["artifact_bytes"],
            )
        )
    return dict(
        measured_baseline=baseline,
        linear_legacy_recording_projections=projections,
        measured_future_performance=False,
        approved_resource_caps=False,
    )


def summarize_review(review):
    result = {}
    for label, energy in review["native_energy"].items():
        if label.endswith("dt_1.5625e-06"):
            errors = review["reference_error_ladders"]["native/" + label]
            result[label.split("/")[0]] = dict(
                max_reference_errors={name: v["max_error"] for name, v in errors.items()},
                energy_budget_ratio=errors["energy"]["worst"]["ratio"],
                max_energy_balance_defect_pJ=energy["max_defect_pJ"],
                max_unexplained_pJ=energy["max_unexplained_pJ"],
            )
    return dict(
        finest_native=result,
        floor_limited_groups=sum(
            all(x <= v["floor"] for x in v["errors"]) for v in review["refinements"].values()
        ),
        pump_leak_energy_refinement=review["refinements"]["pump_leak/native/energy"],
        max_unexplained_energy_pJ=max(
            v["max_unexplained_pJ"] for v in review["native_energy"].values()
        ),
    )


def prepare(output, tests):
    e.require(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs" and not output.exists(),
        "Fresh planning output required",
    )
    receipt = e.software(tests, 20)
    with e.model_fence():
        r, sources, done = authenticate()
        proposal = e.read(PROPOSAL)
        counts = validate(proposal, r["protocol"])
        review = e.read(AUDIT / "review.json")
        facts = summarize_review(review)
        estimates = resource_estimates(
            r["protocol"], evidence.CAPTURE, done, proposal["resource_estimate_horizons_s"]
        )
        code = {
            str(p.relative_to(ROOT)): e.sha(p)
            for p in sorted(HERE.iterdir())
            if p.suffix in (".py", ".json")
        }
        result = dict(
            schema="cells.pump_relaxation_planning_receipt@1",
            status="pilot_closeout_verified_longer_scope_design_only",
            created_utc=datetime.now(UTC).isoformat(),
            prior_audit_completion_sha256=AUDIT_SHA,
            audit_payloads=len(done["files_sha256"]),
            captured_inputs=len(r["sources_sha256"]),
            production_modules=len(sources),
            closeout_facts=facts,
            candidate_counts=counts,
            resource_estimates=estimates,
            proposal=proposal,
            software=receipt,
            sources_sha256=code,
            inherited_scientific_limits={
                k: r["protocol"][k]
                for k in ("reference", "mapping", "trajectory", "refinement", "accounting")
            },
            simulator_or_reference_reruns=0,
            production_changed=False,
            longer_scope_executed=False,
            biology_validated=False,
            gpu_tested=False,
        )
        output.mkdir(parents=True)
        e.write(output / "plan.json", result)
        e.require(all(e.sha(ROOT / n) == h for n, h in code.items()), "Planning source changed")
        e.write(
            output / "completion.json",
            dict(
                status=result["status"],
                files_sha256={"plan.json": e.sha(output / "plan.json")},
                automatic_followup=False,
                longer_scope_executed=False,
            ),
        )
    return dict(
        status=result["status"],
        candidate_counts=counts,
        completion_sha256=e.sha(output / "completion.json"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output.resolve(), args.tests.resolve()), sort_keys=True))
