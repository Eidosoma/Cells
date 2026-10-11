"""D041: immutable scalar RHS caching, matched checked profiles and stage audit."""

import argparse
import cProfile
import hashlib
import json
import os
import pstats
import resource
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_comparison_evidence as parent_audit  # noqa: E402
from scripts import profile_comparison_evidence as parent  # noqa: E402

campaign, previous, ref, prep = parent.campaign, parent.previous, parent.ref, parent.prep
from tests import reference_comparison_evidence as comparison_codec  # noqa: E402
from tests import reference_graph_evaluation as recorded  # noqa: E402
from tests import reference_graph_evidence as evidence_codec  # noqa: E402
from tests import source_graph_fixtures as fixtures  # noqa: E402

candidate = parent.candidate
PRIOR = ROOT / "runs/num-005c2d-2026-09-09/comparison-01"
PRIOR_ROOTS = [*parent.PRIOR_ROOTS, PRIOR.parent]
OUTPUT_PARENT = ROOT / "runs/num-005c2e-2026-09-09"
PLAN = "configs/reference/e02_evaluation_profiles_v1.json"
PLAN_SHA = "73e24fcde771fdcb3fe43f155fe1ec7b4c2323f35af5f28de33fd6016acc308e"
CLOSEOUT = "reports/num-005c2d-closeout.json"
CLOSEOUT_SHA = "d4bd48e5d907c2223df18bb0eca047b209c858f860ff134852e7edd1332336c0"
AUDIT = "reports/num-005c2d-audit.json"
AUDIT_SHA = "53ead23b422d1bc5e9f1ec0054aca4f23ffa0e1da741f90804fa78397e4f98de"
SOURCES = parent.SOURCES + [
    PLAN,
    "docs/E02_INTEGRATION_EVALUATION.md",
    "tests/reference_graph_evaluation.py",
    "scripts/profile_graph_evaluation.py",
    "scripts/audit_graph_evaluation.py",
    "tests/unit/test_graph_evaluation.py",
]


def evidence():
    closeout = campaign.frozen.pinned_json(ROOT / CLOSEOUT, CLOSEOUT_SHA)
    audited = campaign.frozen.pinned_json(ROOT / AUDIT, AUDIT_SHA)
    for name, digest in closeout["payload_hashes"].items():
        if not (ROOT / name).resolve().is_relative_to(ROOT) or ref.sha(ROOT / name) != digest:
            raise ValueError("D040 closeout payload changed")
    registered, receipt, name = parent_audit.check_integrity(PRIOR)
    if (
        closeout["status"] != "pass"
        or not closeout["NUM005c2d_complete"]
        or closeout["long_study_run"]
        or audited["status"] != "pass"
        or name != "verification.json"
        or receipt["status"] != "pass"
        or audited["receipt_sha256"] != ref.sha(PRIOR / name)
        or audited["registration_sha256"] != ref.sha(PRIOR / "registration.json")
        or audited["integration_and_sample_identity"] != "exact_D039_ordered_arrays"
        or any(
            result["readouts"]["maximum_scalar_difference_score"] != 0
            for result in audited["results"].values()
        )
    ):
        raise ValueError("D040 is not eligible for integration evaluation")
    prior_bytes = sum(previous.tree_bytes(path) for path in PRIOR_ROOTS)
    if prior_bytes != 831126114 or prior_bytes != audited["aggregate_artifact_bytes"]:
        raise ValueError("Prior aggregate artifact size changed")
    return registered, audited, prior_bytes


def storage(output, prior_bytes, cap):
    if output.absolute() != output or output.resolve() != output or output.parent != OUTPUT_PARENT:
        raise ValueError("Engineering output must be an unlinked child of its registered parent")
    if OUTPUT_PARENT.exists() and (
        OUTPUT_PARENT.is_symlink() or set(OUTPUT_PARENT.iterdir()) - {output}
    ):
        raise ValueError("Unexpected engineering session/artifact")
    used = previous.tree_bytes(output) if output.exists() else 0
    if used + prior_bytes > cap or prior_bytes + candidate.paths.TAIL_RESERVE > cap:
        raise ref.BudgetExceeded("Aggregate candidate artifact budget exhausted")
    return {
        "prior_roots": [str(p.relative_to(ROOT)) for p in PRIOR_ROOTS],
        "prior_bytes": prior_bytes,
        "aggregate_cap_bytes": cap,
        "new_root_limit_bytes": cap - prior_bytes,
        "policy": "preparation_all_old_partial_failed_qualified_roots_and_one_new_root_no_reset",
    }


def specification(output):
    base, audited, prior_bytes = evidence()
    plan = campaign.frozen.pinned_json(ROOT / PLAN, PLAN_SHA)
    if (
        plan["cases"] != base["plan"]["cases"]
        or plan["policies"] != list(recorded.POLICIES)
        or plan["duration"] != base["plan"]["duration"]
        or plan["step"] != base["plan"]["step"]
        or plan["window_steps"] != 256
        or plan["readout_policy"] != "batched_cached"
        or plan["trajectory_policy"] != "rk4_basis"
        or plan["comparison_policy"] != "trajectory_backed"
        or plan["probe_states_per_case"] != 8
        or plan["microprofile_calls"] != 256
        or plan["probe_coordinate_modes"] != ["absolute", "increments"]
        or plan["steps_per_profile"] != base["plan"]["steps_per_profile"]
        or plan["planned_profiles"] != len(plan["cases"]) * len(plan["policies"])
        or any(
            plan[k]
            for k in (
                "automatic_retry_or_refinement",
                "equations_changed",
                "integration_kernel_changed",
                "stage_checks_changed",
                "whole_curve_checks_changed",
                "production_changed",
                "long_study_run",
                "timestep_selected",
                "compact_long_policy_adopted",
            )
        )
    ):
        raise ValueError("Comparison profile plan changed")
    return {
        "revision": plan["revision"],
        "plan": plan,
        "plan_sha256": PLAN_SHA,
        "output_directory": str(output.relative_to(ROOT)),
        "cases": base["cases"],
        "numerics": base["numerics"],
        "resources": base["resources"],
        "observation_times": base["observation_times"],
        "readout_tolerances": ref.read_json(
            ROOT / "configs/reference/source_emt_graph_probes_v1.json"
        )["instantaneous_tolerances"],
        "parent_directory": str(PRIOR.relative_to(ROOT)),
        "parent_closeout_sha256": CLOSEOUT_SHA,
        "parent_audit_sha256": AUDIT_SHA,
        "parent_results": audited["results"],
        "runtime": prep.runtime(),
        "thread_environment": campaign.THREADS,
        "production_source_hashes": prep.production_identity(campaign.frozen.load_protocol()),
        "storage_budget": storage(output, prior_bytes, base["resources"]["artifact_budget_bytes"]),
        "planned_attempts": [
            f"{case}/{policy}" for case in plan["cases"] for policy in plan["policies"]
        ],
    }


def register(output):
    previous.check_threads()
    spec = specification(output)
    if spec["runtime"]["cpu_affinity"] != spec["resources"]["cpu_affinity"]:
        raise ValueError("Candidate CPU affinity differs")
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(
        output / "reference_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name in SOURCES:
            archive.write(ROOT / name, name)
    receipt = spec | {
        "source_hashes": {name: ref.sha(ROOT / name) for name in SOURCES},
        "source_capsule_sha256": ref.sha(output / "reference_sources.zip"),
    }
    ref.write_json(output / "registration.json", receipt)
    return receipt


def check_registration(output):
    receipt = ref.read_json(output / "registration.json")
    spec = specification(output)
    if set(receipt) != set(spec) | {"source_hashes", "source_capsule_sha256"} or any(
        receipt[k] != v for k, v in spec.items()
    ):
        raise ValueError("Candidate registration inputs/runtime/budgets changed")
    if receipt["source_hashes"] != {name: ref.sha(ROOT / name) for name in SOURCES} or receipt[
        "source_capsule_sha256"
    ] != ref.sha(output / "reference_sources.zip"):
        raise ValueError("Candidate source identity changed")
    with zipfile.ZipFile(output / "reference_sources.zip") as archive:
        if sorted(archive.namelist()) != sorted(SOURCES) or any(
            hashlib.sha256(archive.read(name)).hexdigest() != digest
            for name, digest in receipt["source_hashes"].items()
        ):
            raise ValueError("Candidate source capsule differs")
    return receipt


def execution(registration, key):
    if key not in registration["planned_attempts"]:
        raise ValueError("Unregistered diagnostic profile")
    case, policy = key.rsplit("/", 1)
    resources = registration["resources"] | {
        "window_steps": registration["plan"]["window_steps"],
        "artifact_budget_bytes": registration["storage_budget"]["new_root_limit_bytes"],
    }
    return case, policy, resources


def identity(registration, case, policy):
    # A different evaluator is a different numerical identity, even if probes match.
    model = recorded.PreparedModel(
        prep.graph.Model(registration["cases"][case]["selected"]["case"]), policy=policy
    )
    return parent.identity(registration, case) | {"integration_evaluation": model.identity}


def probe_values(model, index):
    values = np.zeros(model.coordinates.size, dtype=np.float64)
    shaped = values[: 6 * model.n].reshape(6, model.n)
    offset = index * 0.0001 * (1 + np.arange(model.n))
    shaped[0] = shaped[2] = offset
    shaped[3:] = offset
    # History inputs are explicit but do not feed the instantaneous constitutive RHS.
    values[6 * model.n :] = index * 0.125
    return values


def exact_probes(cases=None):
    records = []
    for case in fixtures.cases() if cases is None else cases:
        model = prep.graph.Model(case)
        prepared = {
            policy: recorded.PreparedModel(model, policy=policy) for policy in recorded.POLICIES
        }
        inputs, derivatives, fields = (hashlib.sha256() for _ in range(3))
        for index in range(8):
            value = probe_values(model, index)
            primary = value[: 6 * model.n].reshape(6, model.n) + model.anchor
            expected_fields = model.evaluate(primary)
            for cached in prepared.values():
                actual = cached.evaluate(primary)
                if comparison_codec.fingerprint(actual) != comparison_codec.fingerprint(
                    expected_fields
                ):
                    raise ValueError("Instantaneous decomposed evaluation is not bitwise exact")
            fields.update(comparison_codec.fingerprint(expected_fields).encode())
            for increments in (False, True):
                chosen = value.copy()
                if not increments:
                    chosen[: 6 * model.n] += model.anchor.ravel()
                expected = model.derivative(chosen, increments=increments)
                before = chosen.tobytes()
                for cached in prepared.values():
                    actual = cached.derivative(chosen, increments=increments)
                    if actual.tobytes() != expected.tobytes() or chosen.tobytes() != before:
                        raise ValueError("Complete derivative/input identity changed")
                inputs.update(chosen.tobytes())
                derivatives.update(expected.tobytes())
        records.append(
            {
                "case": case["id"],
                "size": model.coordinates.size,
                "input_sha256": inputs.hexdigest(),
                "complete_RHS_sha256": derivatives.hexdigest(),
                "all_evaluation_fields_sha256": fields.hexdigest(),
                "coordinate_modes": ["absolute", "increments"],
                "states": 8,
            }
        )
    return {
        "revision": recorded.REVISION,
        "status": "pass",
        "cases": records,
        "prepared_RHS_evaluations": 32 * len(records),
        "decomposed_evaluations": 16 * len(records),
        "bitwise_exact": True,
        "scope": "bounded_instantaneous_inputs_not_trajectories_or_all_possible_states",
    }


def microprofile(case, policy, calls):
    if type(calls) is not int or not 1 <= calls <= 256:
        raise ValueError("Invalid microprofile call cap")
    model = recorded.PreparedModel(prep.graph.Model(case), policy=policy)
    value = np.zeros(model.coordinates.size, dtype=np.float64)
    profiler = cProfile.Profile()
    begun = perf_counter()
    profiler.enable()
    for _ in range(calls):
        model.derivative(value, increments=True)
    profiler.disable()
    seconds = perf_counter() - begun
    stats = pstats.Stats(profiler).stats
    rows = []
    for (file, line, function), (primitive, count, self_time, cumulative, _) in sorted(
        stats.items(), key=lambda item: item[1][3], reverse=True
    )[:20]:
        rows.append(
            {
                "file": Path(file).name,
                "line": line,
                "function": function,
                "primitive_calls": primitive,
                "calls": count,
                "self_seconds": self_time,
                "cumulative_seconds": cumulative,
            }
        )
    return {
        "policy": policy,
        "calls": calls,
        "seconds": seconds,
        "top_cumulative": rows,
        "scope": "instrumented_initial_state_RHS_only_not_checked_trajectory_timing",
    }


def worker(output, key):
    begun = perf_counter()
    previous.check_threads()
    if (output / "verification.json").exists() or (output / "failure.json").exists():
        raise ValueError("Closed evaluation session cannot launch a worker")
    r = check_registration(output)
    case, policy, resources = execution(r, key)
    session = ref.read_json(output / "session.json")
    starts = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
    if (
        session["registration_sha256"] != ref.sha(output / "registration.json")
        or session["automatic_retry"]
        or [a["key"] for a in starts] != r["planned_attempts"][: len(starts)]
        or not starts
        or starts[-1]["key"] != key
        or any(not (output / a["key"] / "profile.json").exists() for a in starts[:-1])
        or (
            datetime.now(timezone.utc) - datetime.fromisoformat(session["started_utc"])
        ).total_seconds()
        >= r["resources"]["session_wall_budget_seconds"]
    ):
        raise ValueError("Comparison worker order/session differs")
    selected = r["cases"][case]["selected"]
    checked_begun = perf_counter()
    model = recorded.PreparedModel(
        prep.graph.Model(selected["case"]),
        policy=policy,
        array_budget_bytes=resources["estimated_array_budget_bytes"],
    )
    consumer = comparison_codec.Comparison(
        {v: ROOT / d for v, d in r["cases"][case]["trajectories"].items()},
        selected,
        output / key,
        output,
        resources,
        r["observation_times"],
        policy=r["plan"]["readout_policy"],
        storage_policy=r["plan"]["comparison_policy"],
    )
    result = recorded.integrate(
        model,
        output / key,
        step=r["plan"]["step"],
        end=r["plan"]["duration"],
        numerics=r["numerics"],
        resources=resources,
        identity=identity(r, case, policy),
        policy=r["plan"]["trajectory_policy"],
        artifact_root=output,
        comparison=consumer,
    )
    checked_seconds = perf_counter() - checked_begun
    micro = microprofile(selected["case"], policy, r["plan"]["microprofile_calls"])
    evidence_codec.save_json(
        output / key / "rhs-profile.json", micro, output, resources["artifact_budget_bytes"]
    )
    measured = {
        "key": key,
        "policy": policy,
        "evaluation": model.receipt(),
        "rhs_profile_sha256": ref.sha(output / key / "rhs-profile.json"),
        "aggregate_array_estimate_bytes": comparison_codec.estimate_array_bytes(
            resources["window_steps"], model.coordinates.size, model.n
        )
        + model.estimated_array_bytes,
        "status": result["status"],
        "checked_candidate_seconds": checked_seconds,
        "process_wall_seconds_including_input_checks": perf_counter() - begun,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "rss_scope": "Linux_process_high_water_with_imports_checks_comparison_not_array_estimate",
        "artifact_bytes_before_profile_receipt": previous.tree_bytes(output / key),
        "trajectory_sha256": ref.sha(output / key / "trajectory.json"),
        "evidence": result["evidence"],
        "recording_revision": evidence_codec.REVISION,
        "encoded_trajectory_payload_bytes": sum(
            path.stat().st_size for path in (output / key).glob("chunk-*.npz")
        ),
        "comparison_artifact_bytes": previous.tree_bytes(output / key / "comparison"),
        "complete_checkpoint_bytes": sum(
            (output / key / name).stat().st_size for name in ("initial.npz", "final.npz")
        ),
        "comparison_storage": ref.read_json(output / key / "comparison/storage.json"),
        "comparison_storage_sha256": ref.sha(output / key / "comparison/storage.json"),
        "diagnostics": ref.read_json(output / key / "comparison/diagnostics.json"),
        "diagnostics_sha256": ref.sha(output / key / "comparison/diagnostics.json"),
        "long_time_step_selected": False,
        "production_changed": False,
    }
    ref.write_json(output / key / "profile.json", measured)
    print(json.dumps(measured, sort_keys=True), flush=True)


def run(output):
    r = register(output)
    begun = perf_counter()
    ref.write_json(
        output / "session.json",
        {
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "registration_sha256": ref.sha(output / "registration.json"),
            "wall_budget_seconds": r["resources"]["session_wall_budget_seconds"],
            "automatic_retry": False,
        },
    )
    attempts = []
    try:
        probe_begun = perf_counter()
        probes = exact_probes()
        evidence_codec.save_json(
            output / "instantaneous-probes.json",
            probes,
            output,
            r["storage_budget"]["new_root_limit_bytes"],
        )
        evidence_codec.save_json(
            output / "probe-timing.json",
            {"seconds": perf_counter() - probe_begun, "scope": "exactness_suite_not_RHS_benchmark"},
            output,
            r["storage_budget"]["new_root_limit_bytes"],
        )
        for key in r["planned_attempts"]:
            remaining = r["resources"]["session_wall_budget_seconds"] - (perf_counter() - begun)
            if remaining <= 0:
                raise ref.BudgetExceeded("Candidate engineering session exhausted")
            started = {"key": key, "status": "started", "initial_time": 0}
            with (output / "attempts.jsonl").open("a") as handle:
                handle.write(json.dumps(started, sort_keys=True) + "\n")
            attempts.append(started)
            log = output / f"{key.replace('/', '-')}.log"
            print(f"Starting short profile {key}", flush=True)
            worker_begun = perf_counter()
            with log.open("x") as handle:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/profile_graph_evaluation.py"),
                        "--output",
                        str(output),
                        "--worker",
                        key,
                    ],
                    cwd=ROOT,
                    env=os.environ | campaign.THREADS,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    timeout=min(remaining, r["resources"]["worker_timeout_seconds"]),
                    check=False,
                )
            attempts[-1] = started | {
                "status": "complete" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "log_sha256": ref.sha(log),
                "wall_seconds_including_startup_and_all_receipts": perf_counter() - worker_begun,
            }
            if completed.returncode != 0:
                raise ValueError("Short candidate profile failed; no automatic retry/refinement")
            measured = ref.read_json(output / key / "profile.json")
            print(
                f"Completed {key}: {measured['checked_candidate_seconds']:.3f} s checked",
                flush=True,
            )
        check_registration(output)
        seconds = perf_counter() - begun
        if seconds > r["resources"]["session_wall_budget_seconds"]:
            raise ref.BudgetExceeded("Candidate engineering session exhausted")
        receipt = {
            "status": "pass",
            "scope": "short_exact_scalar_evaluation_pending_independent_stage_audit",
            "seconds": seconds,
            "attempts": attempts,
            "profiles": {
                key: ref.read_json(output / key / "profile.json") for key in r["planned_attempts"]
            },
            "registration_sha256": ref.sha(output / "registration.json"),
            "payload_hashes": previous.payload_hashes(output),
            "long_study_run": False,
            "long_time_step_selected": False,
            "production_changed": False,
        }
        ref.write_json(output / "verification.json", receipt)
        storage(output, r["storage_budget"]["prior_bytes"], r["resources"]["artifact_budget_bytes"])
        return receipt
    except Exception as error:
        ref.write_json(
            output / "failure.json",
            {
                "status": "incomplete",
                "exception": type(error).__name__,
                "message": str(error),
                "seconds": perf_counter() - begun,
                "attempts": attempts,
                "not_started": r["planned_attempts"][len(attempts) :],
                "no_automatic_retry": True,
                "registration_sha256": ref.sha(output / "registration.json"),
                "payload_hashes": previous.payload_hashes(output),
                "long_study_run": False,
                "long_time_step_selected": False,
                "production_changed": False,
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    output = args.output.absolute()
    if args.worker and not args.run:
        worker(output, args.worker)
    elif args.run and not args.worker:
        run(output)
    else:
        parser.error("Choose --run for one new session or an already registered --worker")


if __name__ == "__main__":
    main()
