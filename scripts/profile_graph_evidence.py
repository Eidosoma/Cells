"""D039: lossless recording policies and matched short checked/audited profiles."""

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_graph_diagnostics as parent_audit  # noqa: E402
from scripts import profile_graph_diagnostics as parent  # noqa: E402
from tests import reference_graph_diagnostics as diagnostics  # noqa: E402

campaign, previous, ref, prep = parent.campaign, parent.previous, parent.ref, parent.prep
from tests import reference_graph_evidence as evidence_codec  # noqa: E402
from tests import reference_recorded_candidate as recorded  # noqa: E402

candidate = parent.candidate
PRIOR = ROOT / "runs/num-005c2b-2026-09-09/diagnostics-01"
PRIOR_ROOTS = [*parent.PRIOR_ROOTS, PRIOR.parent]
OUTPUT_PARENT = ROOT / "runs/num-005c2c-2026-09-09"
PLAN = "configs/reference/e02_evidence_profiles_v1.json"
PLAN_SHA = "b70b57543fece34481afcea811a788b2a8791596435223ec890344013c8fb99a"
CLOSEOUT = "reports/num-005c2b-closeout.json"
CLOSEOUT_SHA = "4d9121f8e48066e60d988e1ee11ae9c05f68667fb9865e94fad4734734af3f99"
AUDIT = "reports/num-005c2b-audit.json"
AUDIT_SHA = "901277e0357555b4ff4d669af9f2af8c8267ad8a8b6dd9fb8f8ea7885e52a6b1"
SOURCES = parent.SOURCES + [
    PLAN,
    "docs/E02_LOSSLESS_EVIDENCE.md",
    "tests/reference_graph_evidence.py",
    "tests/reference_recorded_candidate.py",
    "scripts/profile_graph_evidence.py",
    "scripts/audit_graph_evidence.py",
    "tests/unit/test_graph_evidence.py",
]


def evidence():
    closeout = campaign.frozen.pinned_json(ROOT / CLOSEOUT, CLOSEOUT_SHA)
    audited = campaign.frozen.pinned_json(ROOT / AUDIT, AUDIT_SHA)
    for name, digest in closeout["payload_hashes"].items():
        if not (ROOT / name).resolve().is_relative_to(ROOT) or ref.sha(ROOT / name) != digest:
            raise ValueError("D038 closeout payload changed")
    registered, receipt, name = parent_audit.check_integrity(PRIOR)
    if (
        closeout["status"] != "pass"
        or not closeout["NUM005c2b_complete"]
        or closeout["long_study_run"]
        or audited["status"] != "pass"
        or name != "verification.json"
        or receipt["status"] != "pass"
        or audited["receipt_sha256"] != ref.sha(PRIOR / name)
        or audited["registration_sha256"] != ref.sha(PRIOR / "registration.json")
        or audited["integration_and_sample_identity"] != "exact_D037_ordered_arrays"
        or any(
            result["readouts"]["maximum_scalar_difference_score"] != 0
            for result in audited["results"].values()
        )
    ):
        raise ValueError("D038 is not eligible for diagnostic optimization")
    prior_bytes = sum(previous.tree_bytes(path) for path in PRIOR_ROOTS)
    if prior_bytes != 803085279 or prior_bytes != audited["aggregate_artifact_bytes"]:
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
        or plan["policies"] != list(evidence_codec.POLICIES)
        or plan["duration"] != base["plan"]["duration"]
        or plan["step"] != base["plan"]["step"]
        or plan["window_steps"] != 256
        or plan["readout_policy"] != "batched_cached"
        or plan["steps_per_profile"] != base["plan"]["steps_per_profile"]
        or plan["planned_profiles"] != len(plan["cases"]) * len(plan["policies"])
        or any(
            plan[k]
            for k in (
                "automatic_retry_or_refinement",
                "equations_changed",
                "integration_kernel_changed",
                "production_changed",
                "long_study_run",
                "timestep_selected",
                "compact_long_policy_adopted",
            )
        )
    ):
        raise ValueError("Diagnostic profile plan changed")
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


def identity(registration, case):
    # Evidence policy is not a numerical identity: exact cross-policy restart is allowed.
    return parent.identity(registration, case, "batched_cached")


def worker(output, key):
    begun = perf_counter()
    previous.check_threads()
    if (output / "verification.json").exists() or (output / "failure.json").exists():
        raise ValueError("Closed diagnostic session cannot launch a worker")
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
        raise ValueError("Diagnostic worker order/session differs")
    selected = r["cases"][case]["selected"]
    model = prep.graph.Model(selected["case"])
    checked_begun = perf_counter()
    consumer = diagnostics.Comparison(
        {v: ROOT / d for v, d in r["cases"][case]["trajectories"].items()},
        selected,
        output / key,
        output,
        resources,
        r["observation_times"],
        policy=r["plan"]["readout_policy"],
    )
    result = recorded.integrate(
        model,
        output / key,
        step=r["plan"]["step"],
        end=r["plan"]["duration"],
        numerics=r["numerics"],
        resources=resources,
        identity=identity(r, case),
        policy=policy,
        artifact_root=output,
        comparison=consumer,
    )
    checked_seconds = perf_counter() - checked_begun
    measured = {
        "key": key,
        "policy": policy,
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
                        str(ROOT / "scripts/profile_graph_evidence.py"),
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
            "scope": "short_lossless_recording_pending_independent_reconstructed_evidence_audit",
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
