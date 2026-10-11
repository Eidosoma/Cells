"""D040 read-only dependency/reconstruction audit; no writer decoder or RHS replay."""

import argparse
import hashlib
import heapq
import itertools
import json
import sys
import zipfile
from contextlib import ExitStack, closing
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_graph_evidence as frozen  # noqa: E402
from scripts import profile_comparison_evidence as profile  # noqa: E402
from tests import reference_candidate_comparison as comparison  # noqa: E402
from tests import reference_comparison_evidence as codec  # noqa: E402
from tests import reference_graph_diagnostics as diagnostics  # noqa: E402
from tests import reference_graph_evidence as evidence  # noqa: E402

ref, guard = profile.ref, frozen.guard
source_audit = frozen.source_audit
audit_trajectory, Sampler, candidate_grid = (
    frozen.audit_trajectory,
    frozen.Sampler,
    frozen.candidate_grid,
)


def independent_reconstruct(window, times, readers):
    """Separate candidate interpolation arithmetic; immutable reference readers stay explicit."""
    points, accepted, cubic = window["times"], window["increments"], window["coefficients"]
    values = np.empty((len(times), accepted.shape[1]), dtype=np.float64)
    for row, time in enumerate(times):
        if not points[0] <= time <= points[-1]:
            raise ValueError("Independent sample is outside its bound candidate window")
        right = int(np.searchsorted(points, time))
        if time == points[right]:
            values[row] = accepted[right]
        else:
            left = right - 1
            position = (time - points[left]) / (points[right] - points[left])
            polynomial = cubic[left]
            values[row] = (
                (polynomial[3] * position + polynomial[2]) * position + polynomial[1]
            ) * position + polynomial[0]
    return {"candidate": values, **{name: reader.sample(times) for name, reader in readers.items()}}


def independent_decode_samples(policy, arrays, *, size, variants, reconstruct, budget):
    """Do not invoke codec.decode_samples or its writer's candidate sampler."""
    if (
        "times" not in arrays
        or not isinstance(arrays["times"], np.ndarray)
        or arrays["times"].ndim != 1
    ):
        raise ValueError("Independent comparison clocks missing")
    count = len(arrays["times"])
    evidence.validate_arrays(arrays, codec.layout(policy, count, size, variants))
    if type(budget) is not int or budget <= 0 or 8 * count * (16 * size + 32) > budget:
        raise ref.BudgetExceeded("Independent comparison decoded arrays exceed budget")
    if np.any(np.diff(arrays["times"]) <= 0):
        raise ValueError("Independent comparison clocks do not advance")
    if policy == "full_samples":
        decoded = {name: array.copy() for name, array in arrays.items()}
    else:
        decoded = {"times": arrays["times"].copy(), "observer": arrays["observer"].copy()}
        decoded.update(reconstruct(arrays["times"]))
    evidence.validate_arrays(decoded, codec.layout("full_samples", count, size, variants))
    return decoded


def logical_stream(folder, *, directories=None, selected=None):
    return codec.chunks(
        folder,
        directories=directories,
        selected=selected,
        decoder=independent_decode_samples,
        window_decoder=frozen.independent_decode,
        sampler=independent_reconstruct,
    )


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


def audit_samples(folder, directories, selected, observations, resources, deadline):
    summary = ref.read_json(folder / "comparison/comparison.json")
    report = ref.read_json(folder / "trajectory.json")
    if summary != report["comparison"] or summary["index_sha256"] != ref.sha(
        folder / "comparison/chunks.jsonl"
    ):
        raise ValueError("Candidate comparison summary/index differs")
    n, e = len(selected["case"]["cell_ids"]), len(selected["case"]["edges"])
    size = 13 * n + 4 * e
    anchor = np.asarray(selected["case"]["primary"]).ravel()
    slices = {
        "ionic_state": (slice(0, 3 * n), "ionic_state_and_ledger"),
        "regulatory_state": (slice(3 * n, 6 * n), "regulatory_state_and_ledger"),
        "ionic_history": (slice(6 * n, 10 * n + 3 * e), "ionic_state_and_ledger"),
        "regulatory_history": (slice(10 * n + 3 * e, size), "regulatory_state_and_ledger"),
    }
    scores = {key: dict.fromkeys(slices, 0.0) for key in directories}
    samples = chunks = observers = raw_bytes = 0
    fingerprint = hashlib.sha256()
    with comparison.open_readers(directories, selected) as readers, ExitStack() as stack:
        sampler = Sampler(folder)
        stack.callback(sampler.close)
        grids = [
            source_audit.profile.accepted.a1_audit.accepted_grid(d) for d in directories.values()
        ]
        for grid in grids:
            stack.callback(grid.close)
        merged = (
            key
            for key, _ in itertools.groupby(
                heapq.merge(*grids, candidate_grid(report), observations)
            )
        )
        expected = itertools.takewhile(
            lambda t: t <= report["end"], itertools.dropwhile(lambda t: t < report["start"], merged)
        )
        samples_stream = logical_stream(folder, directories=directories, selected=selected)
        stack.callback(samples_stream.close)
        for entry, data in samples_stream:
            guard(deadline)
            t, flags = data["times"], data["observer"]
            if (
                set(data) != {"times", "observer", "candidate", *directories}
                or t.shape != (entry["samples"],)
                or not 1 <= len(t) <= resources["window_steps"]
                or flags.shape != t.shape
                or flags.dtype != np.bool_
                or t.dtype != np.float64
                or (entry["start"], entry["end"]) != (t[0], t[-1])
            ):
                raise ValueError("Candidate comparison shape/window differs")
            np.testing.assert_array_equal(t, list(itertools.islice(expected, len(t))))
            np.testing.assert_array_equal(flags, np.isin(t, observations))
            states = {key: data[key].copy() for key in ["candidate", *directories]}
            for key, state in states.items():
                if (
                    state.shape != (len(t), size)
                    or state.dtype != np.float64
                    or not np.isfinite(state).all()
                ):
                    raise ValueError("Candidate comparison state shape/values differ")
                np.testing.assert_array_equal(
                    state, sampler.sample(t) if key == "candidate" else readers[key].sample(t)
                )
            for i in range(len(t)):
                for array in [
                    t[i : i + 1],
                    flags[i : i + 1],
                    *[states[k][i] for k in ["candidate", *sorted(directories)]],
                ]:
                    fingerprint.update(array.tobytes())
            for state in states.values():
                state[:, : 6 * n] += anchor
            for key in directories:
                for quantity, (chosen, target) in slices.items():
                    tol = selected["numerics"]["targets"][target]
                    score = float(
                        np.max(
                            abs(states["candidate"][:, chosen] - states[key][:, chosen])
                            / (tol["atol"] + tol["rtol"] * abs(states[key][:, chosen])),
                            initial=0,
                        )
                    )
                    scores[key][quantity] = max(scores[key][quantity], score)
            samples += len(t)
            chunks += 1
            observers += int(flags.sum())
            raw_bytes += sum(a.nbytes for a in data.values())
        if next(expected, None) is not None:
            raise ValueError("Candidate comparison grid was truncated")
    for key, quantities in scores.items():
        if set(summary["scores"][key]) != {
            *slices,
            "voltage",
            "gate_scale",
            "membrane_and_junction_flux",
            "binding_cache",
        } or any(v != summary["scores"][key][q] for q, v in quantities.items()):
            raise ValueError("Independent candidate state/history scores differ")
    maximum = max(v for quantities in summary["scores"].values() for v in quantities.values())
    if (
        summary["status"] != "pass"
        or maximum != summary["maximum_score"]
        or maximum > 1
        or summary["maximum_accounting_residual"] > selected["numerics"]["accounting_atol"]
        or (samples, chunks, observers, raw_bytes)
        != (
            summary["samples"],
            summary["chunks"],
            summary["observer_samples"],
            summary["raw_array_bytes"],
        )
        or summary["derived_readout_evaluations"] != samples * 4
    ):
        raise ValueError("Candidate comparison scores/totals differ")
    return {
        "samples": samples,
        "chunks": chunks,
        "observer_samples": observers,
        "maximum_score": maximum,
        "independent_scores": scores,
        "ordered_sample_arrays_sha256": fingerprint.hexdigest(),
    }


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
    with closing(logical_stream(folder, selected=selected)) as stream:
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
    if name == "verification.json":
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
                "numerical_source_runtime_identity": profile.identity(r, case),
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
            baseline = r["parent_results"][f"{case}/rk4_basis"]
            if (
                trajectory["ordered_step_arrays_sha256"]
                != baseline["trajectory"]["ordered_step_arrays_sha256"]
                or sampled["ordered_sample_arrays_sha256"]
                != baseline["comparison"]["ordered_sample_arrays_sha256"]
            ):
                raise ValueError(
                    "Comparison recording changed integration or sampled state evidence"
                )
            readouts = audit_readouts(
                folder, selected, "batched_cached", r["readout_tolerances"], resources, deadline
            )
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
                or measured["comparison_storage"]["policy"] != policy
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
            results[key] = {
                "trajectory": trajectory,
                "comparison": sampled,
                "readouts": readouts,
                "audit_seconds": perf_counter() - audit_begun,
                "audit_timing_scope": "curve_sample_readout_checks_excluding_session_integrity",
            }
        for case in r["plan"]["cases"]:
            a, b = [receipt["profiles"][f"{case}/{policy}"] for policy in r["plan"]["policies"]]
            ta, tb = [
                results[f"{case}/{policy}"]["audit_seconds"] for policy in r["plan"]["policies"]
            ]
            speedups[case] = {
                "checked_time_ratio_full_over_backed": a["checked_candidate_seconds"]
                / b["checked_candidate_seconds"],
                "artifact_bytes_ratio_full_over_backed": a["artifact_bytes_before_profile_receipt"]
                / b["artifact_bytes_before_profile_receipt"],
                "comparison_artifact_bytes_ratio_full_over_backed": a["comparison_artifact_bytes"]
                / b["comparison_artifact_bytes"],
                "full_checked_plus_audited_seconds": a["checked_candidate_seconds"] + ta,
                "backed_checked_plus_audited_seconds": b["checked_candidate_seconds"] + tb,
                "scope": "one_matched_short_measurement_not_statistical_benchmark",
            }
    check_integrity(output)
    guard(deadline)
    return {
        "status": "pass" if name == "verification.json" else "integrity_only_incomplete",
        "scope": "independent_dependency_decoding_D039_exact_arrays_and_scalar_checked_readouts",
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
        "integration_and_sample_identity": "exact_D039_ordered_arrays"
        if results
        else "not_qualified",
        "long_study_run": False,
        "long_time_step_selected": False,
        "compact_evidence_used_in_short_profiles": bool(results),
        "compact_long_policy_adopted": False,
        "reconstruction_decoder": "independent_of_writer_and_no_RHS_replay",
        "reference_dependencies_checked": bool(results),
        "comparison_representations": list(codec.POLICIES),
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
