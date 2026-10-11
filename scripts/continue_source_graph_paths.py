"""NUM-005c1: one registered continuation of the capped long-reference panel.

Import audited complete trios; restart the interrupted path from zero under a
new attempt identity. No changes to the archived solver, equations or observers.
"""

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_source_graph_paths as previous_audit  # noqa: E402
from scripts import qualify_source_graph_paths as campaign  # noqa: E402

ref, paths = campaign.ref, campaign.paths
PRIOR = ROOT / "runs/num-005c1-2026-09-08/reference-01"
PRIOR_HASHES = {
    "registration.json": "0d203e30191c4f879e7dc029979d354b1a2194aec5f8f2c8a3fb6e4f62cfcab4",
    "failure.json": "fdebf3a244e185ad3bc45d32fa9f4e7f322c6a2373fcf358e2b210147cb9bac4",
    "reference_sources.zip": "bc535e18dfc1681717a671263f8391db908d4b071845c7ab56fff18e206cd131",
}
PRIOR_AUDIT = ROOT / "reports/num-005c1-audit.json"
PRIOR_AUDIT_SHA = "c1e0ec7be902316d50cfc605cf7ebe7f4a031c9ad42f1c0813f44f93c016cfbd"
SOURCES = campaign.SOURCES + [
    "scripts/continue_source_graph_paths.py",
    "scripts/audit_source_graph_continuation.py",
    "tests/unit/test_source_graph_continuation.py",
    "docs/SOURCE_GRAPH_CONTINUATION.md",
]


def tree_bytes(directory):
    """Count retained files; refuse links and special files, including linked roots."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Artifact root must be a real directory")
    total = 0
    for path in directory.rglob("*"):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Linked or special artifacts are not supported")
        total += info.st_size
    return total


def prior_evidence():
    """Recheck every old payload; only the pinned full-subset audit permits reuse."""
    for name, digest in PRIOR_HASHES.items():
        if ref.sha(PRIOR / name) != digest:
            raise ValueError(f"Prior evidence changed: {name}")
    audited = campaign.frozen.pinned_json(PRIOR_AUDIT, PRIOR_AUDIT_SHA)
    registration = campaign.check_registration(PRIOR)
    integrity = previous_audit.audit(PRIOR)
    stopped = ref.read_json(PRIOR / "failure.json")
    imported = stopped["cross_qualified_cases"]
    planned = registration["planned_attempts"]
    ordered_cases = list(dict.fromkeys(key.rsplit("/", 1)[0] for key in planned))
    complete = [
        a["key"] for a in stopped["attempts"] if a["status"] == "complete_not_yet_cross_qualified"
    ]
    if (
        audited["status"] != "pass"
        or audited["integrity"] != integrity
        or stopped["status"] != "incomplete"
        or not audited["incomplete_attempts_not_numerically_promoted"]
        or imported != ordered_cases[: len(imported)]
        or set(audited["case_audits"]) != set(imported)
        or set(audited["complete_trajectory_audits"]) != set(complete)
        or complete != [key for key in planned if key.rsplit("/", 1)[0] in imported]
        or tree_bytes(PRIOR) != integrity["artifact_bytes"]
    ):
        raise ValueError("Prior complete-subset audit/inventory does not permit reuse")
    imports = {}
    for case in imported:
        comparison = ref.read_json(PRIOR / case / "comparison/comparison.json")
        observations = ref.read_json(PRIOR / case / "observations/summary.json")
        if (
            comparison["status"] != "pass"
            or comparison["maximum_score"]
            > registration["numerics"]["reference_agreement_fraction"]
            or comparison["maximum_accounting_residual"]
            > registration["numerics"]["accounting_atol"]
            or audited["case_audits"][case]["comparison_grid"]["samples"] != comparison["samples"]
            or observations["samples"] != len(registration["observation_times"])
        ):
            raise ValueError(f"Prior trio is not cross-qualified: {case}")
        files = [f"{variant}/trajectory.json" for variant in campaign.METHODS]
        files += ["comparison/comparison.json", "observations/summary.json"]
        imports[case] = {
            "directory": str((PRIOR / case).relative_to(ROOT)),
            "receipt_hashes": {name: ref.sha(PRIOR / case / name) for name in files},
        }
    return registration, stopped, integrity, imports


def budget(output, prior_bytes, cap):
    """Immutable old root + one new sibling, without resetting the campaign quota."""
    output = Path(output).absolute()
    if output.is_symlink() or output.resolve() != output:
        raise ValueError("Continuation path must not contain links or traversal")
    if output.parent != PRIOR.parent or output == PRIOR:
        raise ValueError("Continuation must be a new direct sibling of the prior session")
    if set(PRIOR.parent.iterdir()) - {PRIOR, output}:
        raise ValueError("Unexpected session/artifact in aggregate budget root")
    if tree_bytes(PRIOR) != prior_bytes:
        raise ValueError("Prior artifact size changed")
    used = tree_bytes(output) if output.exists() else 0
    if prior_bytes + used > cap or prior_bytes + paths.TAIL_RESERVE > cap:
        raise ref.BudgetExceeded("Aggregate artifact budget exhausted")
    return {
        "root": str(PRIOR.parent.relative_to(ROOT)),
        "prior_artifact_bytes_including_stopped_attempt": prior_bytes,
        "aggregate_artifact_budget_bytes": cap,
        "new_session_artifact_limit_bytes": cap - prior_bytes,
        "policy": "immutable_prior_bytes_plus_new_root_bytes_lossless_conservative_batch_preflight",
    }


def specification(output):
    previous, stopped, integrity, imports = prior_evidence()
    pending = [key for key in previous["planned_attempts"] if key.rsplit("/", 1)[0] not in imports]
    new_cases = list(dict.fromkeys(key.rsplit("/", 1)[0] for key in pending))
    # Preserve the numerical specification; only the named execution slice changes.
    spec = {
        key: value
        for key, value in previous.items()
        if key not in ("source_hashes", "source_capsule_sha256")
    }
    spec.update(
        revision="num005c1_registered_continuation@1",
        scope="remaining_long_implicit_references_with_audited_prior_trio_imports",
        output_directory=str(output.relative_to(ROOT)),
        prior_directory=str(PRIOR.relative_to(ROOT)),
        prior_hashes=PRIOR_HASHES,
        prior_audit_path=str(PRIOR_AUDIT.relative_to(ROOT)),
        prior_audit_sha256=PRIOR_AUDIT_SHA,
        prior_incomplete_attempts=[
            a
            for a in stopped["attempts"]
            if a["key"]
            not in {key for key in previous["planned_attempts"] if key.rsplit("/", 1)[0] in imports}
        ],
        imported_cases=imports,
        new_cases=new_cases,
        full_panel_planned_attempts=previous["planned_attempts"],
        planned_attempts=pending,
        restart_policy="new_root_attempt_identity_initial_clock_zero_no_adaptive_checkpoint_resume",
        storage_budget=budget(
            output, integrity["artifact_bytes"], previous["resources"]["artifact_budget_bytes"]
        ),
    )
    if not pending:
        raise ValueError("No remaining registered conditions")
    return spec


def execution_registration(registration):
    """Give unchanged writers the remaining quota, not a fresh whole-campaign cap.

    All other execution resources and numerical settings remain exactly frozen.
    This derived lower local quota is explicit in the registration and is also
    used for comparison/observer writers whose budget root is the new session.
    """
    resources = registration["resources"] | {
        "artifact_budget_bytes": registration["storage_budget"]["new_session_artifact_limit_bytes"]
    }
    return registration | {"resources": resources}


def check_threads():
    if any(os.environ.get(k) != v for k, v in campaign.THREADS.items()):
        raise ValueError("Continuation requires the registered single-thread environment")


def register(output):
    check_threads()
    campaign.prepared(audit_payloads=True)
    spec = specification(output)
    output.mkdir(exist_ok=False)
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
        receipt[key] != value for key, value in spec.items()
    ):
        raise ValueError("Continuation registration inputs/order/imports/budgets changed")
    if receipt["source_hashes"] != {name: ref.sha(ROOT / name) for name in SOURCES}:
        raise ValueError("Continuation source identity changed")
    if ref.sha(output / "reference_sources.zip") != receipt["source_capsule_sha256"]:
        raise ValueError("Continuation source capsule changed")
    with zipfile.ZipFile(output / "reference_sources.zip") as archive:
        if sorted(archive.namelist()) != sorted(SOURCES) or any(
            hashlib.sha256(archive.read(name)).hexdigest() != digest
            for name, digest in receipt["source_hashes"].items()
        ):
            raise ValueError("Continuation archived source inventory changed")
    return receipt


def worker(output, key):
    check_threads()
    if (output / "failure.json").exists() or (output / "verification.json").exists():
        raise ValueError("A closed continuation cannot launch another worker")
    registration = check_registration(output)
    if key not in registration["planned_attempts"]:
        raise ValueError("Unregistered continuation attempt (imported cases cannot be rerun)")
    session = ref.read_json(output / "session.json")
    if (
        session["registration_sha256"] != ref.sha(output / "registration.json")
        or session["wall_budget_seconds"]
        != registration["resources"]["session_wall_budget_seconds"]
        or session["automatic_retry"]
    ):
        raise ValueError("Continuation session identity changed")
    elapsed = (
        datetime.now(timezone.utc) - datetime.fromisoformat(session["started_utc"])
    ).total_seconds()
    if not 0 <= elapsed < session["wall_budget_seconds"]:
        raise ref.BudgetExceeded("Continuation session is no longer live")
    starts = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
    if not starts or starts[-1] != {
        "key": key,
        "attempt_id": f"{registration['output_directory']}/{key}",
        "initial_time": 0.0,
        "status": "started",
    }:
        raise ValueError("Worker has no matching registered start entry")
    case, variant = key.rsplit("/", 1)
    method, refinement = campaign.METHODS[variant]
    return paths.integrate(
        campaign.graph.Model(registration["cases"][case]),
        output / key,
        method=method,
        refinement=refinement,
        duration=registration["duration"],
        numerics=registration["numerics"],
        resources=execution_registration(registration)["resources"],
        artifact_root=output,
    )


def case_result(folder):
    return {
        "comparison": ref.read_json(folder / "comparison/comparison.json"),
        "observations": ref.read_json(folder / "observations/summary.json"),
    }


def payload_hashes(output):
    return {
        str(path.relative_to(output)): ref.sha(path) for path in output.rglob("*") if path.is_file()
    }


def run(output):
    registration = register(output)
    begun = perf_counter()
    deadline = begun + registration["resources"]["session_wall_budget_seconds"]
    ref.write_json(
        output / "session.json",
        {
            "registration_sha256": ref.sha(output / "registration.json"),
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "wall_budget_seconds": registration["resources"]["session_wall_budget_seconds"],
            "automatic_retry": False,
        },
    )
    attempts, completed = [], {}
    try:
        execution = execution_registration(registration)
        for case in registration["new_cases"]:
            for variant in campaign.METHODS:
                campaign.guard(deadline)
                key = f"{case}/{variant}"
                attempt = {
                    "key": key,
                    "attempt_id": f"{registration['output_directory']}/{key}",
                    "status": "started",
                    "initial_time": 0.0,
                }
                attempts.append(attempt)
                log = output / f"{key.replace('/', '-')}.log"
                print(f"Starting new registered attempt {attempt['attempt_id']}", flush=True)
                with (output / "attempts.jsonl").open("a") as history:
                    history.write(json.dumps(attempt, sort_keys=True) + "\n")
                with log.open("x") as handle:
                    try:
                        result = subprocess.run(
                            [
                                sys.executable,
                                str(Path(__file__).resolve()),
                                "--output",
                                str(output),
                                "--worker",
                                key,
                            ],
                            env=os.environ | campaign.THREADS | {"PYTHONDONTWRITEBYTECODE": "1"},
                            stdout=handle,
                            stderr=subprocess.STDOUT,
                            check=False,
                            timeout=max(
                                0,
                                min(
                                    deadline - perf_counter(),
                                    registration["resources"]["worker_timeout_seconds"],
                                ),
                            ),
                        )
                    except subprocess.TimeoutExpired:
                        handle.flush()
                        attempt.update(status="incomplete_timeout", log_sha256=ref.sha(log))
                        raise
                attempt.update(returncode=result.returncode, log_sha256=ref.sha(log))
                if result.returncode:
                    failure = output / key / "failure.json"
                    incomplete = (
                        failure.exists() and ref.read_json(failure)["status"] == "incomplete"
                    )
                    attempt["status"] = "incomplete" if incomplete else "refused"
                    error = ref.BudgetExceeded if incomplete else ValueError
                    raise error(
                        f"Continuation worker {attempt['status']}: {key}; no automatic retry"
                    )
                attempt["status"] = "complete_not_yet_cross_qualified"
                print(f"Completed {key}", flush=True)
            agreement = campaign.compare(output, case, execution, deadline)
            if agreement["status"] != "pass":
                raise ValueError(f"Reference disagreement in {case}; no automatic amendment")
            observations = campaign.observe(output, case, execution, deadline)
            completed[case] = {"comparison": agreement, "observations": observations}
            print(f"Cross-qualified {case}: score={agreement['maximum_score']:.9g}", flush=True)
        check_registration(output)
        campaign.prepared(audit_payloads=True)
        campaign.guard(deadline)
        combined = {
            case: case_result(PRIOR / case) for case in registration["imported_cases"]
        } | completed
        payloads = payload_hashes(output)
        campaign.guard(deadline)
        receipt = {
            "status": "pass",
            "scope": registration["scope"],
            "attempts": attempts,
            "new_cross_qualified_cases": list(completed),
            "cases": combined,
            "case_directories": {
                case: data["directory"] for case, data in registration["imported_cases"].items()
            }
            | {case: f"{registration['output_directory']}/{case}" for case in completed},
            "seconds": perf_counter() - begun,
            "payload_hashes": payloads,
            "registration_sha256": ref.sha(output / "registration.json"),
            "full_panel_cross_qualified": True,
            "independent_continuation_audit": "pending",
            "NUM005c_complete": False,
            "production_changed": False,
            "long_time_rk4_step": "not_selected",
            "candidate_owned_continuations": "not_run",
        }
        ref.write_json(output / "verification.json", receipt)
        print(
            json.dumps(
                receipt | {"payload_hashes": len(payloads), "cases": list(combined)}, indent=2
            ),
            flush=True,
        )
        return receipt
    except Exception as error:
        receipt = {
            "status": "incomplete"
            if isinstance(error, (ref.BudgetExceeded, subprocess.TimeoutExpired))
            else "unqualified",
            "exception": type(error).__name__,
            "message": str(error),
            "attempts": attempts,
            "new_cross_qualified_cases": list(completed),
            "imported_cases": list(registration["imported_cases"]),
            "not_started": [
                key
                for key in registration["planned_attempts"]
                if key not in {a["key"] for a in attempts}
            ],
            "seconds": perf_counter() - begun,
            "no_automatic_retry": True,
            "registration_sha256": ref.sha(output / "registration.json"),
            "payload_hashes": payload_hashes(output),
        }
        ref.write_json(output / "failure.json", receipt)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    if args.worker:
        worker(output, args.worker)
    else:
        run(output)


if __name__ == "__main__":
    main()
