"""D041 independent complete stage-RHS checks plus unchanged D040 evidence auditing."""

import argparse
import hashlib
import json
import sys
import zipfile
from contextlib import closing
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_comparison_evidence as frozen  # noqa: E402
from scripts import profile_graph_evaluation as profile  # noqa: E402
from tests import reference_comparison_evidence as codec  # noqa: E402
from tests import reference_graph_evaluation as evaluation  # noqa: E402
from tests import reference_graph_evidence as evidence  # noqa: E402

ref, guard = profile.ref, frozen.guard
audit_trajectory, audit_samples, audit_readouts = (
    frozen.audit_trajectory,
    frozen.audit_samples,
    frozen.audit_readouts,
)


def audit_stage_rhs(folder, case, panel, deadline):
    """Recompute complete slopes with frozen constitutive equations, not the cache."""
    model = profile.prep.graph.Model(case, panel)
    fingerprint = hashlib.sha256()
    count = steps = 0
    with closing(evidence.chunks(folder, decoder=frozen.frozen.independent_decode)) as stream:
        for _, data in stream:
            for i, slopes in enumerate(data["slopes"]):
                guard(deadline)
                left, right = data["increments"][i : i + 2]
                h = data["times"][i + 1] - data["times"][i]
                stages = (
                    left,
                    left + h * slopes[0] / 2,
                    left + h * slopes[1] / 2,
                    left + h * slopes[2],
                    right,
                )
                for state, recorded in zip(stages, slopes, strict=True):
                    expected = model.derivative(state, increments=True)
                    if expected.tobytes() != recorded.tobytes():
                        raise ValueError("Independent complete stage RHS is not bitwise exact")
                    fingerprint.update(state.tobytes())
                    fingerprint.update(expected.tobytes())
                    count += 1
                steps += 1
    report = ref.read_json(folder / "trajectory.json")
    if count != report["rhs_calls"] or steps != report["steps"]:
        raise ValueError("Independent stage RHS inventory differs")
    return {
        "steps": steps,
        "complete_RHS_evaluations": count,
        "ordered_stage_inputs_and_RHS_sha256": fingerprint.hexdigest(),
        "bitwise_exact": True,
        "evaluator": "frozen_NUM005a_graph_Model",
        "scope": "every_recorded_RK4_stage_and_endpoint_slope_not_interval_ODE_certification",
        "RHS_used_to_reconstruct_stored_evidence": False,
    }


def check_evaluation(folder, measured, trajectory, case, policy, resources, plan):
    model = evaluation.PreparedModel(profile.prep.graph.Model(case), policy=policy)
    receipt = measured["evaluation"]
    fixed = model.identity | {
        "rhs_calls": trajectory["rhs_calls"],
        "estimated_array_bytes": model.estimated_array_bytes,
        "stage_and_curve_checks_changed": False,
        "state_dependent_values_cached": False,
    }
    estimate = (
        codec.estimate_array_bytes(resources["window_steps"], model.coordinates.size, model.n)
        + model.estimated_array_bytes
    )
    micro = ref.read_json(folder / "rhs-profile.json")
    if (
        set(receipt) != set(fixed) | {"rhs_seconds", "preparation_seconds"}
        or any(receipt[k] != value for k, value in fixed.items())
        or any(
            not np.isfinite(receipt[k]) or receipt[k] < 0
            for k in ("rhs_seconds", "preparation_seconds")
        )
        or receipt["rhs_seconds"] > trajectory["timings"]["integration_and_stage_checks"]
        or receipt["preparation_seconds"] > measured["checked_candidate_seconds"]
        or measured["aggregate_array_estimate_bytes"] != estimate
        or estimate > resources["estimated_array_budget_bytes"]
        or measured["rhs_profile_sha256"] != ref.sha(folder / "rhs-profile.json")
        or micro["policy"] != policy
        or micro["calls"] != plan["microprofile_calls"]
        or not np.isfinite(micro["seconds"])
        or micro["seconds"] <= 0
        or not 1 <= len(micro["top_cumulative"]) <= 20
        or any(
            not np.isfinite(row[k]) or row[k] < 0
            for row in micro["top_cumulative"]
            for k in ("self_seconds", "cumulative_seconds")
        )
    ):
        raise ValueError("Integration evaluator/profile identity, timing or estimate differs")


def check_integrity(output):
    registration = profile.check_registration(output)
    name = "verification.json" if (output / "verification.json").exists() else "failure.json"
    if name == "verification.json" and (output / "failure.json").exists():
        raise ValueError("Both candidate pass and failure receipts exist")
    receipt = ref.read_json(output / name)
    inventory = profile.previous.payload_hashes(output)
    inventory.pop(name)
    if receipt["payload_hashes"] != inventory or receipt["registration_sha256"] != ref.sha(
        output / "registration.json"
    ):
        raise ValueError("Candidate session payload inventory/hash differs")
    starts = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
    attempts = receipt["attempts"]
    if (
        starts != [{"key": a["key"], "status": "started", "initial_time": 0} for a in attempts]
        or [a["key"] for a in attempts] != registration["planned_attempts"][: len(attempts)]
    ):
        raise ValueError("Candidate session attempt order differs")
    session = ref.read_json(output / "session.json")
    if (
        session["registration_sha256"] != receipt["registration_sha256"]
        or session["wall_budget_seconds"]
        != registration["resources"]["session_wall_budget_seconds"]
        or session["automatic_retry"]
    ):
        raise ValueError("Candidate session settings differ")
    for attempt in attempts:
        if (
            "log_sha256" in attempt
            and ref.sha(output / f"{attempt['key'].replace('/', '-')}.log") != attempt["log_sha256"]
        ):
            raise ValueError("Candidate worker log differs")
    if (
        receipt["production_changed"]
        or receipt["long_study_run"]
        or receipt["long_time_step_selected"]
    ):
        raise ValueError("Engineering scope was expanded")
    if name == "verification.json":
        if (
            receipt["status"] != "pass"
            or len(attempts) != len(registration["planned_attempts"])
            or any(
                a["status"] != "complete"
                or a["returncode"] != 0
                or not 0
                < a["wall_seconds_including_startup_and_all_receipts"]
                <= registration["resources"]["worker_timeout_seconds"]
                for a in attempts
            )
            or receipt["seconds"] > registration["resources"]["session_wall_budget_seconds"]
        ):
            raise ValueError("Incomplete candidate session cannot pass")
        if receipt["profiles"] != {
            key: ref.read_json(output / key / "profile.json")
            for key in registration["planned_attempts"]
        }:
            raise ValueError("Candidate profile inventory differs")
    elif (
        receipt["status"] != "incomplete"
        or not receipt["no_automatic_retry"]
        or receipt["not_started"] != registration["planned_attempts"][len(attempts) :]
    ):
        raise ValueError("Invalid candidate stop receipt")
    return registration, receipt, name


def estimates(registration, receipt, results):
    policies = {}
    for policy in registration["plan"]["policies"]:
        rows = []
        for case in registration["plan"]["cases"]:
            measured = receipt["profiles"][f"{case}/{policy}"]
            selected = registration["cases"][case]["selected"]
            n, e = len(selected["case"]["cell_ids"]), len(selected["case"]["edges"])
            for step in registration["numerics"]["rk4_study_steps"]:
                steps = profile.candidate.Grid(step, selected["duration"]).count
                rows.append(
                    {
                        "case": case,
                        "step": step,
                        "steps": steps,
                        "estimated_checked_seconds": steps
                        * measured["checked_candidate_seconds"]
                        / registration["plan"]["steps_per_profile"],
                        "estimated_audit_seconds": steps
                        * results[f"{case}/{policy}"]["audit_seconds"]
                        / registration["plan"]["steps_per_profile"],
                        "uncompressed_trajectory_array_floor_bytes": steps
                        * (40 * (13 * n + 4 * e) + 16),
                        "short_rate_compressed_evidence_estimate_bytes": steps
                        * measured["artifact_bytes_before_profile_receipt"]
                        / registration["plan"]["steps_per_profile"],
                    }
                )
        policies[policy] = {
            "trials": rows,
            "estimated_study_seconds": sum(row["estimated_checked_seconds"] for row in rows),
            "estimated_study_audit_seconds": sum(row["estimated_audit_seconds"] for row in rows),
            "estimated_study_checked_and_audited_seconds": sum(
                row["estimated_audit_seconds"] + row["estimated_checked_seconds"] for row in rows
            ),
            "maximum_estimated_trial_seconds": max(
                row["estimated_checked_seconds"] for row in rows
            ),
            "uncompressed_trajectory_array_floor_bytes": sum(
                row["uncompressed_trajectory_array_floor_bytes"] for row in rows
            ),
            "short_rate_compressed_evidence_estimate_bytes": sum(
                row["short_rate_compressed_evidence_estimate_bytes"] for row in rows
            ),
        }
    return {
        "scope": "short_rate_planning_estimates_not_long_measurements_or_feasibility_certification",
        "policies": policies,
        "long_study_run": False,
    }


def verify(output, deadline=None):
    begun = perf_counter()
    deadline = begun + 3600 if deadline is None else deadline
    r, receipt, name = check_integrity(output)
    results, speedups = {}, {}
    probes = None
    if name == "verification.json":
        probes = profile.exact_probes()
        if probes != ref.read_json(output / "instantaneous-probes.json"):
            raise ValueError("Registered instantaneous probe evidence differs")
        with zipfile.ZipFile(output / "reference_sources.zip") as archive:
            panel = json.loads(archive.read("configs/reference/source_emt_pair_panel_v1.json"))
        for key in r["planned_attempts"]:
            guard(deadline)
            audit_begun = perf_counter()
            case, policy, resources = profile.execution(r, key)
            selected = r["cases"][case]["selected"]
            expected = {
                "revision": profile.candidate.REVISION,
                "case": selected["case"],
                "step": r["plan"]["step"],
                "end": r["plan"]["duration"],
                "numerics": r["numerics"],
                "numerical_source_runtime_identity": profile.identity(r, case, policy),
            }
            folder = output / key
            trajectory = audit_trajectory(folder, expected, resources, panel, deadline)
            sampled = audit_samples(
                folder,
                {v: ROOT / d for v, d in r["cases"][case]["trajectories"].items()},
                selected,
                r["observation_times"],
                resources,
                deadline,
            )
            baseline = r["parent_results"][f"{case}/trajectory_backed"]
            if (
                trajectory["ordered_step_arrays_sha256"]
                != baseline["trajectory"]["ordered_step_arrays_sha256"]
                or sampled["ordered_sample_arrays_sha256"]
                != baseline["comparison"]["ordered_sample_arrays_sha256"]
            ):
                raise ValueError(
                    "Prepared evaluation changed integration or sampled state evidence"
                )
            readouts = audit_readouts(
                folder, selected, "batched_cached", r["readout_tolerances"], resources, deadline
            )
            stages = audit_stage_rhs(folder, selected["case"], panel, deadline)
            measured = receipt["profiles"][key]
            path_report = ref.read_json(folder / "trajectory.json")
            if (
                measured["evidence"] != path_report["evidence"]
                or measured["recording_revision"] != evidence.REVISION
                or path_report["evidence"]["policy"] != r["plan"]["trajectory_policy"]
                or measured["comparison_storage"]
                != ref.read_json(folder / "comparison/storage.json")
                or measured["comparison_storage_sha256"]
                != ref.sha(folder / "comparison/storage.json")
                or measured["comparison_storage"]["policy"] != r["plan"]["comparison_policy"]
                or measured["encoded_trajectory_payload_bytes"]
                != sum(p.stat().st_size for p in folder.glob("chunk-*.npz"))
                or measured["comparison_artifact_bytes"]
                != profile.previous.tree_bytes(folder / "comparison")
                or measured["complete_checkpoint_bytes"]
                != sum((folder / name).stat().st_size for name in ("initial.npz", "final.npz"))
                or measured["trajectory_sha256"] != ref.sha(folder / "trajectory.json")
                or measured["diagnostics_sha256"] != ref.sha(folder / "comparison/diagnostics.json")
                or measured["diagnostics"] != ref.read_json(folder / "comparison/diagnostics.json")
                or measured["policy"] != policy
                or not path_report["seconds"]
                <= measured["checked_candidate_seconds"]
                <= measured["process_wall_seconds_including_input_checks"]
                or measured["artifact_bytes_before_profile_receipt"]
                != profile.previous.tree_bytes(folder) - (folder / "profile.json").stat().st_size
                or measured["process_wall_seconds_including_input_checks"]
                > resources["worker_timeout_seconds"]
                or measured["diagnostics"]["readout_seconds"]
                > measured["checked_candidate_seconds"]
                or path_report["steps"] != r["plan"]["steps_per_profile"]
                or path_report["start_tick"] != 0
            ):
                raise ValueError("Measured diagnostic profile differs")
            check_evaluation(
                folder, measured, path_report, selected["case"], policy, resources, r["plan"]
            )
            results[key] = {
                "stage_RHS": stages,
                "trajectory": trajectory,
                "comparison": sampled,
                "readouts": readouts,
                "audit_seconds": perf_counter() - audit_begun,
                "audit_timing_scope": "curve_sample_readout_stage_RHS_excluding_session_integrity",
            }
        for case in r["plan"]["cases"]:
            a, b = [receipt["profiles"][f"{case}/{policy}"] for policy in r["plan"]["policies"]]
            ta, tb = [
                results[f"{case}/{policy}"]["audit_seconds"] for policy in r["plan"]["policies"]
            ]
            speedups[case] = {
                "checked_time_ratio_frozen_over_cached": a["checked_candidate_seconds"]
                / b["checked_candidate_seconds"],
                "artifact_bytes_ratio_frozen_over_cached": a[
                    "artifact_bytes_before_profile_receipt"
                ]
                / b["artifact_bytes_before_profile_receipt"],
                "comparison_artifact_bytes_ratio_frozen_over_cached": a["comparison_artifact_bytes"]
                / b["comparison_artifact_bytes"],
                "frozen_checked_plus_audited_seconds": a["checked_candidate_seconds"] + ta,
                "cached_checked_plus_audited_seconds": b["checked_candidate_seconds"] + tb,
                "scope": "one_matched_short_measurement_not_statistical_benchmark",
            }
    check_integrity(output)
    guard(deadline)
    return {
        "status": "pass" if name == "verification.json" else "integrity_only_incomplete",
        "scope": "D040_exact_arrays_dependencies_readouts_and_every_frozen_complete_stage_RHS",
        "instantaneous_probes": probes,
        "results": results,
        "policy_comparisons": speedups,
        "planning_preflight": estimates(r, receipt, results) if results else None,
        "seconds": perf_counter() - begun,
        "payloads_audited": len(receipt["payload_hashes"]),
        "source_files": len(r["source_hashes"]),
        "registration_sha256": ref.sha(output / "registration.json"),
        "receipt_sha256": ref.sha(output / name),
        "new_artifact_bytes": profile.previous.tree_bytes(output),
        "aggregate_artifact_bytes": r["storage_budget"]["prior_bytes"]
        + profile.previous.tree_bytes(output),
        "integration_and_sample_identity": "exact_D040_ordered_arrays"
        if results
        else "not_qualified",
        "long_study_run": False,
        "long_time_step_selected": False,
        "compact_evidence_used_in_short_profiles": bool(results),
        "compact_long_policy_adopted": False,
        "reconstruction_decoder": "independent_of_writer_and_no_RHS_replay",
        "reference_dependencies_checked": bool(results),
        "comparison_representations": [r["plan"]["comparison_policy"]],
        "integration_evaluation_policies": list(evaluation.POLICIES),
        "every_recorded_stage_RHS_recomputed": bool(results),
        "production_changed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.directory.absolute())
    ref.write_json(args.output, result)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
