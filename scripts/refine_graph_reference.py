"""D035 / E02 A1: one registered tenfold-tighter BDF diagnostic, no retry sweep."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_source_graph_continuation as prior_audit  # noqa: E402
from scripts import continue_source_graph_paths as previous  # noqa: E402
from scripts import qualify_source_graph_paths as campaign  # noqa: E402
from tests import reference_graph_comparison as comparison  # noqa: E402

ref, paths = campaign.ref, campaign.paths
PRIOR = ROOT / "runs/num-005c1-2026-09-08/continuation-01"
OUTPUT_PARENT = ROOT / "runs/num-005c1-a1-2026-09-09"
PLAN = "configs/reference/e02_bdf_refinement_a1.json"
PLAN_SHA = "4d7c15a60389b1e55dd098bbfa5dc794ce528354d3755e15ab9f1f6dfb69e75e"
CLOSEOUT = "reports/num-005c1-continuation-closeout.json"
CLOSEOUT_SHA = "91b0f766c63d45cbc9155b2aee48d1d9eae2a0d9f27a10c10589bf8164a88acd"
AUDIT = "reports/num-005c1-continuation-audit.json"
AUDIT_SHA = "a2608343963bf6c42aacfefdecd6c15d1dd63f1da3d2f338777cf674f5d8dee0"
SOURCES = previous.SOURCES + [
    PLAN,
    "tests/reference_graph_comparison.py",
    "scripts/refine_graph_reference.py",
    "scripts/audit_graph_refinement.py",
    "tests/unit/test_graph_refinement.py",
    "docs/E02_BDF_REFINEMENT_A1.md",
]


def evidence():
    closeout = campaign.frozen.pinned_json(ROOT / CLOSEOUT, CLOSEOUT_SHA)
    audited = campaign.frozen.pinned_json(ROOT / AUDIT, AUDIT_SHA)
    for name, digest in closeout["payload_hashes"].items():
        if not (ROOT / name).resolve().is_relative_to(ROOT) or ref.sha(ROOT / name) != digest:
            raise ValueError(f"Prior closeout payload changed: {name}")
    registration, stopped, _ = prior_audit.check_integrity(PRIOR)
    if (
        audited["status"] != "pass"
        or audited["receipt_sha256"] != ref.sha(PRIOR / "failure.json")
        or stopped["status"] != "unqualified"
        or closeout["qualified_reference_conditions_total"] != 10
    ):
        raise ValueError("Prior failed-reference evidence identity differs")
    return registration, audited


def storage(output, prior_bytes, cap):
    if output.absolute() != output or output.resolve() != output or output.parent != OUTPUT_PARENT:
        raise ValueError(
            "Refinement requires an unlinked direct output path in its registered parent"
        )
    if OUTPUT_PARENT.exists() and (
        OUTPUT_PARENT.is_symlink() or set(OUTPUT_PARENT.iterdir()) - {output}
    ):
        raise ValueError("Unexpected refinement session/artifact")
    if previous.tree_bytes(PRIOR.parent) != prior_bytes:
        raise ValueError("Prior aggregate artifact size changed")
    used = previous.tree_bytes(output) if output.exists() else 0
    if prior_bytes + used > cap or prior_bytes + paths.TAIL_RESERVE > cap:
        raise ref.BudgetExceeded("Aggregate refinement artifact budget exhausted")
    return {
        "prior_directory": str(PRIOR.parent.relative_to(ROOT)),
        "prior_bytes": prior_bytes,
        "aggregate_cap_bytes": cap,
        "new_root_limit_bytes": cap - prior_bytes,
        "new_output_parent": str(OUTPUT_PARENT.relative_to(ROOT)),
        "policy": "immutable_prior_campaign_plus_one_new_refinement_root_no_quota_reset",
    }


def specification(output):
    parent, audited = evidence()
    plan = campaign.frozen.pinned_json(ROOT / PLAN, PLAN_SHA)
    if (
        plan["case_key"] != "M_to_E/mirna_only"
        or plan["new_variant"] != "bdf_tight"
        or plan["new_method"] != ["BDF", 0.1]
        or plan["reference_order"] != ["radau", "bdf", "refined", "bdf_tight"]
        or plan["required_pairs"]
        != ["radau_vs_refined", "radau_vs_bdf_tight", "refined_vs_bdf_tight"]
        or plan["automatic_retry_or_sweep"]
        or plan["remaining_controls_run"]
    ):
        raise ValueError("Unsupported refinement amendment")
    case_key = plan["case_key"]
    imports = {}
    for variant in plan["reference_order"][:-1]:
        key = f"{case_key}/{variant}"
        if key not in audited["new_trajectory_audits"]:
            raise ValueError("Unaudited or incomplete trajectory cannot be imported")
        imports[variant] = {
            "directory": str((PRIOR / key).relative_to(ROOT)),
            "trajectory_sha256": ref.sha(PRIOR / key / "trajectory.json"),
        }
    return {
        "revision": plan["revision"],
        "scope": plan["scope"],
        "amendment": plan,
        "amendment_sha256": ref.sha(ROOT / PLAN),
        "output_directory": str(output.relative_to(ROOT)),
        "prior_closeout_sha256": CLOSEOUT_SHA,
        "prior_audit_sha256": AUDIT_SHA,
        "prior_registration_sha256": ref.sha(PRIOR / "registration.json"),
        "prior_failure_sha256": ref.sha(PRIOR / "failure.json"),
        "case": parent["cases"][case_key],
        "case_key": case_key,
        "imports": imports,
        "reference_order": plan["reference_order"],
        "methods": {variant: parent["methods"][variant] for variant in imports}
        | {"bdf_tight": plan["new_method"]},
        "required_pairs": plan["required_pairs"],
        "planned_attempts": ["bdf_tight"],
        "duration": parent["duration"],
        "numerics": parent["numerics"],
        "resources": parent["resources"],
        "observation_times": parent["observation_times"],
        "runtime": parent["runtime"],
        "thread_environment": parent["thread_environment"],
        "production_source_hashes": parent["production_source_hashes"],
        "storage_budget": storage(
            output,
            audited["aggregate_artifact_bytes"],
            parent["resources"]["artifact_budget_bytes"],
        ),
        "original_qualified_conditions": 10,
        "case_qualification_changed": False,
        "NUM005c1_complete": False,
        "candidate_selected": False,
    }


def execution(registration):
    return registration | {
        "resources": registration["resources"]
        | {"artifact_budget_bytes": registration["storage_budget"]["new_root_limit_bytes"]}
    }


def directories(registration):
    return {
        variant: ROOT
        / (
            registration["imports"][variant]["directory"]
            if variant in registration["imports"]
            else f"{registration['output_directory']}/{variant}"
        )
        for variant in registration["reference_order"]
    }


def register(output):
    previous.check_threads()
    spec = specification(output)
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
        raise ValueError("Refinement registration changed")
    if receipt["source_hashes"] != {name: ref.sha(ROOT / name) for name in SOURCES} or receipt[
        "source_capsule_sha256"
    ] != ref.sha(output / "reference_sources.zip"):
        raise ValueError("Refinement source identity changed")
    with zipfile.ZipFile(output / "reference_sources.zip") as archive:
        if sorted(archive.namelist()) != sorted(SOURCES) or any(
            hashlib.sha256(archive.read(name)).hexdigest() != digest
            for name, digest in receipt["source_hashes"].items()
        ):
            raise ValueError("Refinement source archive differs")
    return receipt


def worker(output):
    previous.check_threads()
    if (output / "failure.json").exists() or (output / "verification.json").exists():
        raise ValueError("Closed refinement cannot launch a worker")
    registration = check_registration(output)
    session = ref.read_json(output / "session.json")
    elapsed = (
        datetime.now(timezone.utc) - datetime.fromisoformat(session["started_utc"])
    ).total_seconds()
    if (
        session["registration_sha256"] != ref.sha(output / "registration.json")
        or session["attempt_id"] != f"{registration['output_directory']}/bdf_tight"
        or session["wall_budget_seconds"]
        != registration["resources"]["session_wall_budget_seconds"]
    ):
        raise ValueError("Refinement session identity changed")
    if not 0 <= elapsed < session["wall_budget_seconds"]:
        raise ref.BudgetExceeded("Refinement session is no longer live")
    return paths.integrate(
        campaign.graph.Model(registration["case"]),
        output / "bdf_tight",
        method="BDF",
        refinement=0.1,
        duration=registration["duration"],
        numerics=registration["numerics"],
        resources=execution(registration)["resources"],
        artifact_root=output,
    )


def run(output):
    registration = register(output)
    begun = perf_counter()
    deadline = begun + registration["resources"]["session_wall_budget_seconds"]
    attempt = {
        "key": "bdf_tight",
        "attempt_id": f"{registration['output_directory']}/bdf_tight",
        "initial_time": 0.0,
        "status": "started",
    }
    ref.write_json(
        output / "session.json",
        {
            "registration_sha256": ref.sha(output / "registration.json"),
            "attempt_id": attempt["attempt_id"],
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "wall_budget_seconds": registration["resources"]["session_wall_budget_seconds"],
        },
    )
    log = output / "bdf-tight.log"
    try:
        print(f"Starting the single registered {attempt['attempt_id']}", flush=True)
        with log.open("x") as handle:
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--output",
                        str(output),
                        "--worker",
                    ],
                    env=os.environ | campaign.THREADS | {"PYTHONDONTWRITEBYTECODE": "1"},
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    timeout=max(
                        0,
                        min(
                            deadline - perf_counter(),
                            registration["resources"]["worker_timeout_seconds"],
                        ),
                    ),
                    check=False,
                )
            except subprocess.TimeoutExpired:
                handle.flush()
                attempt.update(status="incomplete_timeout", log_sha256=ref.sha(log))
                raise
        attempt.update(returncode=result.returncode, log_sha256=ref.sha(log))
        if result.returncode:
            failure = output / "bdf_tight/failure.json"
            incomplete = failure.exists() and ref.read_json(failure)["status"] == "incomplete"
            attempt["status"] = "incomplete" if incomplete else "refused"
            raise (ref.BudgetExceeded if incomplete else ValueError)(
                "Refinement worker stopped; no retry"
            )
        attempt["status"] = "complete_not_yet_cross_qualified"
        print("Tighter BDF complete; comparing all four retained references", flush=True)
        summary = comparison.compare(
            directories(registration), execution(registration), output, deadline
        )
        if summary["status"] != "agreement_met":
            raise ValueError("Tighter BDF agreement target not met; no additional refinement")
        check_registration(output)
        campaign.guard(deadline)
        payloads = previous.payload_hashes(output)
        campaign.guard(deadline)
        receipt = {
            "status": "pass",
            "scope": registration["scope"],
            "attempts": [attempt],
            "comparison": summary,
            "seconds": perf_counter() - begun,
            "payload_hashes": payloads,
            "registration_sha256": ref.sha(output / "registration.json"),
            "case_qualification_changed": False,
            "NUM005c1_complete": False,
            "candidate_selected": False,
            "independent_audit": "pending",
        }
        ref.write_json(output / "verification.json", receipt)
        print(json.dumps(receipt | {"payload_hashes": len(payloads)}, indent=2), flush=True)
        return receipt
    except Exception as error:
        ref.write_json(
            output / "failure.json",
            {
                "status": "incomplete"
                if isinstance(error, (ref.BudgetExceeded, subprocess.TimeoutExpired))
                else "unqualified",
                "exception": type(error).__name__,
                "message": str(error),
                "attempts": [attempt],
                "seconds": perf_counter() - begun,
                "registration_sha256": ref.sha(output / "registration.json"),
                "payload_hashes": previous.payload_hashes(output),
                "automatic_retry": False,
                "case_qualification_changed": False,
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    worker(output) if args.worker else run(output)


if __name__ == "__main__":
    main()
