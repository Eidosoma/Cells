"""D039 independent reconstruction, numerical/sample audit and resource closeout."""

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
from scripts import audit_graph_diagnostics as prior_audit  # noqa: E402
from scripts import profile_graph_evidence as profile  # noqa: E402
from tests import reference_candidate_comparison as comparison  # noqa: E402
from tests import reference_graph_evidence as evidence  # noqa: E402

source_audit = prior_audit.old
ref, guard, old = profile.ref, source_audit.guard, source_audit.old


def independent_decode(policy, arrays, *, width, size, cells, budget):
    """Reconstruct independently; never call the recording codec or RK4 RHS."""
    evidence.preflight(width, size, cells, budget)
    evidence.validate_arrays(arrays, evidence.layout(policy, width, size, cells))
    if policy == "full_trace":
        return {k: a.copy() for k, a in arrays.items()}
    y = np.empty((width + 1, size), dtype=np.float64)
    polynomial = np.empty((width, 4, size), dtype=np.float64)
    y[0] = arrays["first_increments"]
    for index in range(width):
        dt = arrays["times"][index + 1] - arrays["times"][index]
        a, b, c, d, endpoint = arrays["slopes"][index]
        left = y[index]
        right = left + dt * (a + 2 * b + 2 * c + d) / 6
        y[index + 1] = right
        change, tangent_left, tangent_right = right - left, dt * a, dt * endpoint
        polynomial[index, 0] = left
        polynomial[index, 1] = tangent_left
        polynomial[index, 2] = 3 * change - 2 * tangent_left - tangent_right
        polynomial[index, 3] = -2 * change + tangent_left + tangent_right
    if y[-1].tobytes() != arrays["last_increments"].tobytes():
        raise ValueError("Independent reconstructed checkpoint differs")
    return {
        **{k: arrays[k] for k in ("times", "ticks", "slopes", "anchor", "context")},
        "increments": y,
        "coefficients": polynomial,
    }


def stream(directory):
    return evidence.chunks(directory, decoder=independent_decode)


def audit_checkpoint(directory, chunk, expected):
    return evidence.load_checkpoint(directory, chunk, expected, decoder=independent_decode)


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


def audit_trajectory(folder, expected, resources, panel, deadline):
    report = ref.read_json(folder / "trajectory.json")
    attempt = ref.read_json(folder / "attempt.json")
    if (
        attempt["contract"] != expected
        or attempt["contract_sha256"] != profile.candidate.digest(expected)
        or attempt["resources"] != resources
    ):
        raise ValueError("Candidate numerical/checkpoint contract differs")
    for file, key in [
        ("attempt.json", "attempt_sha256"),
        ("chunks.jsonl", "index_sha256"),
        ("initial.npz", "initial_sha256"),
        ("final.npz", "final_sha256"),
    ]:
        if ref.sha(folder / file) != report[key]:
            raise ValueError("Candidate trajectory identity differs")
    if (
        report["status"] != "complete_engineering_candidate_not_long_qualified"
        or report["revision"] != expected["revision"]
        or report["step"] != expected["step"]
        or report["end"] != expected["end"]
        or report["steps"] > resources["max_steps_per_trajectory"]
        or report["seconds"] > resources["worker_timeout_seconds"]
        or report["estimated_working_array_bytes"] > resources["estimated_array_budget_bytes"]
        or report["long_time_step_selected"]
        or report["production_changed"]
    ):
        raise ValueError("Candidate trajectory scope/resources differ")
    case = expected["case"]
    n, e = len(case["cell_ids"]), len(case["edges"])
    size = 13 * n + 4 * e
    initial = evidence.read_arrays(
        folder / "initial.npz",
        evidence.checkpoint_layout(size, n),
        budget=resources["estimated_array_budget_bytes"],
    )
    tick = int(initial["tick"])
    if (
        tick != attempt["start_tick"]
        or report["start_tick"] != tick
        or report["start"] != min(tick * expected["step"], expected["end"])
        or initial["time"] != report["start"]
    ):
        raise ValueError("Candidate initial global clock differs")
    value = initial["increments"]
    np.testing.assert_array_equal(initial["anchor"], case["primary"])
    np.testing.assert_array_equal(initial["context"], case["context"])
    if attempt["initial"] is None:
        if tick != 0 or np.any(value != 0):
            raise ValueError("Fresh candidate did not start with zero increments")
    else:
        carry = audit_checkpoint(
            attempt["initial"]["parent_directory"], attempt["initial"]["parent_chunk"], expected
        )
        if attempt["initial"] != carry or tick != carry["tick"]:
            raise ValueError("Candidate restart checkpoint differs")
        np.testing.assert_array_equal(value, carry["increments"])
    maximum = old.check_coefficients(value[None], case, panel)
    steps = chunks = raw_bytes = 0
    fingerprint = hashlib.sha256()
    with closing(stream(folder)) as windows:
        for entry, data in windows:
            guard(deadline)
            t, ticks, y, c, k = (
                data[name] for name in ("times", "ticks", "increments", "coefficients", "slopes")
            )
            width = len(t) - 1
            if (
                set(data)
                != {"times", "ticks", "increments", "coefficients", "slopes", "anchor", "context"}
                or not 1 <= width <= resources["window_steps"]
                or entry["steps"] != width
                or t.shape != (width + 1,)
                or ticks.dtype != np.int64
                or ticks.shape != t.shape
                or y.shape != (width + 1, size)
                or c.shape != (width, 4, size)
                or k.shape != (width, 5, size)
            ):
                raise ValueError("Candidate window inventory/shape differs")
            if any(
                a.dtype != np.float64 or not np.isfinite(a).all()
                for name, a in data.items()
                if name != "ticks"
            ):
                raise ValueError("Candidate window precision/values differ")
            np.testing.assert_array_equal(data["anchor"], case["primary"])
            np.testing.assert_array_equal(data["context"], case["context"])
            np.testing.assert_array_equal(ticks, np.arange(tick, tick + width + 1, dtype=np.int64))
            np.testing.assert_array_equal(
                t,
                [min(i * expected["step"], expected["end"]) for i in range(tick, tick + width + 1)],
            )
            np.testing.assert_array_equal(y[0], value)
            if np.any(np.diff(t) <= 0) or (
                entry["start"],
                entry["end"],
                entry["start_tick"],
                entry["end_tick"],
            ) != (t[0], t[-1], ticks[0], ticks[-1]):
                raise ValueError("Candidate window clock/index differs")
            for i in range(width):
                h, left, right = t[i + 1] - t[i], y[i], y[i + 1]
                k1, k2, k3, k4, kend = k[i]
                np.testing.assert_array_equal(right, left + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6)
                change, a, b = right - left, h * k1, h * kend
                np.testing.assert_array_equal(
                    c[i], np.stack((left, a, 3 * change - 2 * a - b, -2 * change + a + b))
                )
                for stage in (left, left + h * k1 / 2, left + h * k2 / 2, left + h * k3, right):
                    maximum = max(maximum, old.check_coefficients(stage[None], case, panel))
                maximum = max(maximum, old.check_coefficients(c[i], case, panel))
                for array in (t[i : i + 2], ticks[i : i + 2], y[i : i + 2], c[i], k[i]):
                    fingerprint.update(array.tobytes())
            raw_bytes += sum(a.nbytes for a in data.values())
            tick += width
            steps += width
            chunks += 1
            value = y[-1].copy()
    data = evidence.read_arrays(
        folder / "final.npz",
        evidence.checkpoint_layout(size, n),
        budget=resources["estimated_array_budget_bytes"],
    )
    np.testing.assert_array_equal(data["increments"], value)
    np.testing.assert_array_equal(data["anchor"], case["primary"])
    np.testing.assert_array_equal(data["context"], case["context"])
    if data["tick"] != tick or data["time"] != expected["end"]:
        raise ValueError("Candidate final checkpoint differs")
    if (
        steps != report["steps"]
        or chunks != report["chunks"]
        or raw_bytes != report["raw_trajectory_array_bytes"]
        or report["rhs_calls"] != 5 * steps
        or report["end_tick"] != tick
        or report["maximum_stage_accounting_residual"] > expected["numerics"]["accounting_atol"]
    ):
        raise ValueError("Candidate trajectory totals differ")
    if (
        any(not np.isfinite(v) or v < 0 for v in report["timings"].values())
        or sum(report["timings"].values()) > report["seconds"]
    ):
        raise ValueError("Candidate section timing inventory differs")
    return {
        "steps": steps,
        "chunks": chunks,
        "maximum_accounting_residual": maximum,
        "ordered_step_arrays_sha256": fingerprint.hexdigest(),
    }


class Sampler:
    """Audit-only candidate sampler; no call to the online cubic sampler."""

    def __init__(self, directory):
        self.stream = stream(directory)
        self.data = None

    def sample(self, times):
        rows = []
        for time in times:
            while self.data is None or time > self.data["times"][-1]:
                _, self.data = next(self.stream)
            t, values, c = (self.data[k] for k in ("times", "increments", "coefficients"))
            if time < t[0]:
                raise ValueError("Audit sample outside candidate window")
            right = int(np.searchsorted(t, time))
            if time == t[right]:
                rows.append(values[right].copy())
            else:
                i = right - 1
                theta = (time - t[i]) / (t[i + 1] - t[i])
                rows.append(((c[i, 3] * theta + c[i, 2]) * theta + c[i, 1]) * theta + c[i, 0])
        return np.asarray(rows)

    def close(self):
        self.stream.close()


def candidate_grid(report):
    step, end = report["step"], report["end"]
    yield report["start"]
    for tick in range(report["start_tick"], report["end_tick"]):
        a, b = min(tick * step, end), min((tick + 1) * step, end)
        yield a + (b - a) / 2
        yield b


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
        samples_stream = comparison.chunks(folder, comparison=True)
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
                        * ((80 if policy == "full_trace" else 40) * (13 * n + 4 * e) + 16),
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
            baseline = r["parent_results"][f"{case}/batched_cached"]
            if (
                trajectory["ordered_step_arrays_sha256"]
                != baseline["trajectory"]["ordered_step_arrays_sha256"]
                or sampled["ordered_sample_arrays_sha256"]
                != baseline["comparison"]["ordered_sample_arrays_sha256"]
            ):
                raise ValueError(
                    "Readout optimization changed integration or sampled state evidence"
                )
            readouts = prior_audit.audit_readouts(
                folder, selected, "batched_cached", r["readout_tolerances"], resources, deadline
            )
            measured = receipt["profiles"][key]
            path_report = ref.read_json(folder / "trajectory.json")
            if (
                measured["evidence"] != path_report["evidence"]
                or measured["recording_revision"] != evidence.REVISION
                or path_report["evidence"]["policy"] != policy
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
                "checked_time_ratio_full_over_basis": a["checked_candidate_seconds"]
                / b["checked_candidate_seconds"],
                "artifact_bytes_ratio_full_over_basis": a["artifact_bytes_before_profile_receipt"]
                / b["artifact_bytes_before_profile_receipt"],
                "trajectory_payload_bytes_ratio_full_over_basis": a[
                    "encoded_trajectory_payload_bytes"
                ]
                / b["encoded_trajectory_payload_bytes"],
                "full_checked_plus_audited_seconds": a["checked_candidate_seconds"] + ta,
                "basis_checked_plus_audited_seconds": b["checked_candidate_seconds"] + tb,
                "scope": "one_matched_short_measurement_not_statistical_benchmark",
            }
    check_integrity(output)
    guard(deadline)
    return {
        "status": "pass" if name == "verification.json" else "integrity_only_incomplete",
        "scope": "independent_decoding_D038_exact_arrays_and_scalar_checked_readouts",
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
        "integration_and_sample_identity": "exact_D038_ordered_arrays"
        if results
        else "not_qualified",
        "long_study_run": False,
        "long_time_step_selected": False,
        "compact_evidence_used_in_short_profiles": bool(results),
        "compact_long_policy_adopted": False,
        "reconstruction_decoder": "independent_of_writer_and_no_RHS_replay",
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
