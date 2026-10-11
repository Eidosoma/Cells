"""Read-only D038 audit: frozen numerical evidence and scalar-checked readouts."""

import argparse
import json
import sys
import zipfile
from contextlib import closing
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_graph_candidate as old  # noqa: E402
from scripts import profile_graph_diagnostics as profile  # noqa: E402
from tests import reference_graph_diagnostics as diagnostics  # noqa: E402

ref = profile.ref
guard = old.guard


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


def audit_readouts(folder, selected, policy, tolerances, resources, deadline):
    model = profile.prep.graph.Model(selected["case"])
    cached = (
        diagnostics.BatchedReadouts(
            model,
            max_samples=resources["window_steps"],
            array_budget_bytes=resources["estimated_array_budget_bytes"],
        )
        if policy == "batched_cached"
        else None
    )
    result = ref.read_json(folder / "comparison/diagnostics.json")
    summary = ref.read_json(folder / "comparison/comparison.json")
    variants = list(selected["methods"])
    maxima = {key: {} for key in variants}
    differences, exact = {}, {}
    samples = chunks = 0
    with closing(diagnostics.original.chunks(folder, comparison=True)) as stream:
        for entry, data in stream:
            guard(deadline)
            states = {key: data[key] for key in ["candidate", *variants]}
            if set(entry["readout_hashes"]) != set(states):
                raise ValueError("Readout fingerprint inventory differs")
            scalar = {key: profile.prep.observed(model, value) for key, value in states.items()}
            actual = (
                scalar
                if cached is None
                else {key: cached.observed(value) for key, value in states.items()}
            )
            for key in states:
                if diagnostics.fingerprint(actual[key]) != entry["readout_hashes"][key]:
                    raise ValueError("Recorded readout fingerprint differs")
                for name, score in diagnostics.readout_scores(
                    actual[key], scalar[key], tolerances
                ).items():
                    differences[name] = max(differences.get(name, 0), score)
                    exact[name] = (
                        exact.get(name, True)
                        and actual[key][name].tobytes() == scalar[key][name].tobytes()
                    )
            for key in variants:
                scores = profile.prep.comparison_scores(
                    model,
                    states["candidate"],
                    states[key],
                    actual["candidate"],
                    actual[key],
                    selected["numerics"]["targets"],
                )
                for quantity, score in scores.items():
                    maxima[key][quantity] = max(maxima[key].get(quantity, 0), score)
            samples += len(data["times"])
            chunks += 1
    if maxima != summary["scores"] or max(differences.values()) > 1:
        raise ValueError("Scalar differential or recomputed candidate scores differ")
    if (
        result["revision"] != diagnostics.REVISION
        or result["policy"] != policy
        or result["readout_batches"] != 4 * chunks
        or result["readout_evaluations"] != 4 * samples
        or result["cache_identity"] != (None if cached is None else cached.cache_identity)
        or result["readout_array_estimate_bytes"]
        != (0 if cached is None else cached.estimated_array_bytes)
        or not result["evaluation_hashes_retained_per_batch"]
        or result["integration_policy_changed"]
        or any(
            not np.isfinite(result[k]) or result[k] < 0
            for k in ("readout_seconds", "cache_seconds", "fingerprint_seconds")
        )
    ):
        raise ValueError("Readout policy/count/estimate receipt differs")
    return {
        "samples": samples,
        "state_evaluations": 4 * samples,
        "chunks": chunks,
        "maximum_scalar_difference_score": max(differences.values()),
        "difference_scores": differences,
        "bitwise_exact_fields": exact,
        "all_eight_candidate_scores_recomputed": True,
        "every_recorded_readout_fingerprint_recomputed": True,
    }


def estimates(registration, receipt):
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
                        "uncompressed_trajectory_array_floor_bytes": steps
                        * (80 * (13 * n + 4 * e) + 16),
                        "short_rate_compressed_evidence_estimate_bytes": steps
                        * measured["artifact_bytes_before_profile_receipt"]
                        / registration["plan"]["steps_per_profile"],
                    }
                )
        policies[policy] = {
            "trials": rows,
            "estimated_study_seconds": sum(row["estimated_checked_seconds"] for row in rows),
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
    if name == "verification.json":
        with zipfile.ZipFile(output / "reference_sources.zip") as archive:
            panel = json.loads(archive.read("configs/reference/source_emt_pair_panel_v1.json"))
        for key in r["planned_attempts"]:
            guard(deadline)
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
            trajectory = old.audit_trajectory(folder, expected, resources, panel, deadline)
            sampled = old.audit_samples(
                folder,
                {v: ROOT / d for v, d in r["cases"][case]["trajectories"].items()},
                selected,
                r["observation_times"],
                resources,
                deadline,
            )
            baseline = r["parent_results"][f"{case}/window-256"]
            if (
                trajectory["ordered_step_arrays_sha256"]
                != baseline["trajectory"]["ordered_step_arrays_sha256"]
                or sampled["ordered_sample_arrays_sha256"]
                != baseline["comparison"]["ordered_sample_arrays_sha256"]
            ):
                raise ValueError(
                    "Readout optimization changed integration or sampled state evidence"
                )
            readouts = audit_readouts(
                folder, selected, policy, r["readout_tolerances"], resources, deadline
            )
            measured = receipt["profiles"][key]
            path_report = ref.read_json(folder / "trajectory.json")
            if (
                measured["trajectory_sha256"] != ref.sha(folder / "trajectory.json")
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
            results[key] = {"trajectory": trajectory, "comparison": sampled, "readouts": readouts}
        for case in r["plan"]["cases"]:
            a, b = [receipt["profiles"][f"{case}/{policy}"] for policy in r["plan"]["policies"]]
            speedups[case] = {
                "checked_path_ratio_scalar_over_batched": a["checked_candidate_seconds"]
                / b["checked_candidate_seconds"],
                "readout_ratio_scalar_over_batched": a["diagnostics"]["readout_seconds"]
                / b["diagnostics"]["readout_seconds"],
                "scope": "single_matched_short_observation_not_statistical_speedup",
            }
    check_integrity(output)
    guard(deadline)
    return {
        "status": "pass" if name == "verification.json" else "integrity_only_incomplete",
        "scope": "D037_exact_numerical_evidence_and_all_saved_readouts_scalar_checked",
        "results": results,
        "speed_ratios": speedups,
        "planning_preflight": estimates(r, receipt) if results else None,
        "seconds": perf_counter() - begun,
        "payloads_audited": len(receipt["payload_hashes"]),
        "source_files": len(r["source_hashes"]),
        "registration_sha256": ref.sha(output / "registration.json"),
        "receipt_sha256": ref.sha(output / name),
        "new_artifact_bytes": profile.previous.tree_bytes(output),
        "aggregate_artifact_bytes": r["storage_budget"]["prior_bytes"]
        + profile.previous.tree_bytes(output),
        "integration_and_sample_identity": "exact_D037_ordered_arrays"
        if results
        else "not_qualified",
        "long_study_run": False,
        "long_time_step_selected": False,
        "compact_evidence_used": False,
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
