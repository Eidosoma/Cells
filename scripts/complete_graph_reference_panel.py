"""D036 / E02 A2: explicit amended acceptance and one bounded remaining panel."""

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
from scripts import audit_graph_refinement as a1_audit  # noqa: E402
from scripts import refine_graph_reference as a1  # noqa: E402
from tests import reference_graph_panel as panel  # noqa: E402

campaign, previous, ref, paths = a1.campaign, a1.previous, a1.ref, a1.paths
A1 = ROOT / "runs/num-005c1-a1-2026-09-09/bdf-tight-01"
PRIOR_PARENTS = [a1.PRIOR.parent, A1.parent]
OUTPUT_PARENT = ROOT / "runs/num-005c1-a2-2026-09-09"
PLAN = "configs/reference/e02_reference_policy_a2.json"
PLAN_SHA = "4562f67307b8d081bd26e7dd151e5a40ca8a8d966e70cc186de38f9d0e069598"
CLOSEOUT = "reports/num-005c1-a1-closeout.json"
CLOSEOUT_SHA = "3f7382cc1efc4d0afc3f5f5233cae9aa267b19a23f6581379f8cb9cf78b837f2"
AUDIT = "reports/num-005c1-a1-audit.json"
AUDIT_SHA = "ab652d6b39fe2ede6d76c2823a3011323c59dd66450de1053249e13272352310"
SOURCES = a1.SOURCES + [
    PLAN,
    "docs/E02_REFERENCE_POLICY_A2.md",
    "tests/reference_graph_panel.py",
    "scripts/complete_graph_reference_panel.py",
    "scripts/audit_graph_reference_panel.py",
    "tests/unit/test_graph_reference_panel.py",
]


def evidence():
    closeout = campaign.frozen.pinned_json(ROOT / CLOSEOUT, CLOSEOUT_SHA)
    audited = campaign.frozen.pinned_json(ROOT / AUDIT, AUDIT_SHA)
    for name, digest in closeout["payload_hashes"].items():
        if not (ROOT / name).resolve().is_relative_to(ROOT) or ref.sha(ROOT / name) != digest:
            raise ValueError(f"A1 closeout payload changed: {name}")
    registered, receipt, name = a1_audit.check_integrity(A1)
    if (
        closeout["status"] != "pass"
        or audited["status"] != "pass"
        or name != "verification.json"
        or audited["receipt_sha256"] != ref.sha(A1 / name)
        or audited["registration_sha256"] != ref.sha(A1 / "registration.json")
        or audited["case_qualification_changed"]
        or closeout["original_qualified_conditions"] != 10
        or receipt["comparison"]["status"] != "agreement_met"
        or receipt["comparison"]["maximum_required_score"]
        > registered["numerics"]["reference_agreement_fraction"]
    ):
        raise ValueError("A1 audited agreement is not eligible for explicit A2 adoption")
    parent = ref.read_json(a1.PRIOR / "registration.json")
    old_audit = campaign.frozen.pinned_json(ROOT / a1.AUDIT, a1.AUDIT_SHA)
    original = {case: item["directory"] for case, item in parent["imported_cases"].items()}
    original.update(
        {case: str((a1.PRIOR / case).relative_to(ROOT)) for case in old_audit["new_case_audits"]}
    )
    if len(original) != 10 or registered["case_key"] in original:
        raise ValueError("Original qualified-case inventory differs")
    return campaign.specification(), {
        "original": original,
        "adopted_paths": {
            key: str(a1.directories(registered)[key].relative_to(ROOT))
            for key in ("radau", "refined", "bdf_tight")
        },
        "adopted_comparison": str((A1 / "comparison/comparison.json").relative_to(ROOT)),
        "prior_bytes": audited["aggregate_artifact_bytes"],
    }


def storage(output, prior_bytes, cap):
    if output.absolute() != output or output.resolve() != output or output.parent != OUTPUT_PARENT:
        raise ValueError("Panel output must be an unlinked direct child of its registered parent")
    if OUTPUT_PARENT.exists() and (
        OUTPUT_PARENT.is_symlink() or set(OUTPUT_PARENT.iterdir()) - {output}
    ):
        raise ValueError("Unexpected panel session/artifact")
    if sum(previous.tree_bytes(p) for p in PRIOR_PARENTS) != prior_bytes:
        raise ValueError("Prior aggregate artifact size changed")
    used = previous.tree_bytes(output) if output.exists() else 0
    if prior_bytes + used > cap or prior_bytes + paths.TAIL_RESERVE > cap:
        raise ref.BudgetExceeded("Aggregate panel artifact budget exhausted")
    return {
        "prior_parents": [str(p.relative_to(ROOT)) for p in PRIOR_PARENTS],
        "prior_bytes": prior_bytes,
        "aggregate_cap_bytes": cap,
        "new_root_limit_bytes": cap - prior_bytes,
        "policy": "all_old_partial_failed_and_qualified_roots_plus_one_new_root_no_quota_reset",
    }


def specification(output):
    base, proof = evidence()
    plan = campaign.frozen.pinned_json(ROOT / PLAN, PLAN_SHA)
    adopted, remaining = plan["adopted_case"], plan["remaining_cases"]
    if (
        set(proof["original"]) | {adopted} | set(remaining) != set(base["cases"])
        or len(proof["original"]) + 1 + len(remaining) != len(base["cases"])
        or plan["reference_agreement_fraction"] != base["numerics"]["reference_agreement_fraction"]
        or plan["accounting_atol"] != base["numerics"]["accounting_atol"]
        or plan["automatic_retry_or_refinement"]
        or plan["old_BDF_failure_reclassified"]
        or plan["new_trajectory_count"] != len(remaining) * len(plan["reference_order"])
    ):
        raise ValueError("Amended panel inventory/limits differ")
    references = {}
    for case in base["cases"]:
        old = case in proof["original"]
        directory = proof["original"][case] if old else str((output / case).relative_to(ROOT))
        selected = list(campaign.METHODS) if old else plan["reference_order"]
        trajectories = (
            proof["adopted_paths"]
            if case == adopted
            else {key: f"{directory}/{key}" for key in selected}
        )
        comparison = (
            proof["adopted_comparison"]
            if case == adopted
            else f"{directory}/comparison/comparison.json"
        )
        references[case] = {
            "policy": "original_qualified"
            if old
            else "A1_adopted"
            if case == adopted
            else "A2_new",
            "trajectories": trajectories,
            "methods": base["methods"] if old else plan["methods"],
            "comparison": comparison,
            "observations": f"{directory}/observations/summary.json",
            "imported_receipt_hashes": {
                name: ref.sha(ROOT / name)
                for name in [comparison] + [f"{d}/trajectory.json" for d in trajectories.values()]
            }
            if old or case == adopted
            else {},
        }
        if old:
            observer = references[case]["observations"]
            references[case]["imported_receipt_hashes"][observer] = ref.sha(ROOT / observer)
    return base | {
        "revision": plan["revision"],
        "scope": plan["scope"],
        "amendment": plan,
        "amendment_sha256": ref.sha(ROOT / PLAN),
        "output_directory": str(output.relative_to(ROOT)),
        "prior_closeout_sha256": CLOSEOUT_SHA,
        "prior_audit_sha256": AUDIT_SHA,
        "references": references,
        "adopted_case": adopted,
        "original_qualified_cases": list(proof["original"]),
        "new_cases": remaining,
        "reference_order": plan["reference_order"],
        "methods": plan["methods"],
        "planned_attempts": [
            f"{case}/{key}" for case in remaining for key in plan["reference_order"]
        ],
        "storage_budget": storage(
            output, proof["prior_bytes"], base["resources"]["artifact_budget_bytes"]
        ),
        "original_campaign_reclassified": False,
        "biological_outcome_is_numerical_gate": False,
    }


def execution(registration):
    return registration | {
        "resources": registration["resources"]
        | {"artifact_budget_bytes": registration["storage_budget"]["new_root_limit_bytes"]}
    }


def directories(registration, case):
    return {
        key: ROOT / registration["references"][case]["trajectories"][key]
        for key in registration["reference_order"]
    }


def register(output):
    previous.check_threads()
    spec = specification(output)
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(
        output / "reference_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as z:
        for name in SOURCES:
            z.write(ROOT / name, name)
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
        raise ValueError("Panel registration inputs/order/imports/budgets changed")
    if receipt["source_hashes"] != {name: ref.sha(ROOT / name) for name in SOURCES} or receipt[
        "source_capsule_sha256"
    ] != ref.sha(output / "reference_sources.zip"):
        raise ValueError("Panel source identity changed")
    with zipfile.ZipFile(output / "reference_sources.zip") as archive:
        if sorted(archive.namelist()) != sorted(SOURCES) or any(
            hashlib.sha256(archive.read(name)).hexdigest() != digest
            for name, digest in receipt["source_hashes"].items()
        ):
            raise ValueError("Panel source archive differs")
    return receipt


def worker(output, key):
    previous.check_threads()
    if (output / "failure.json").exists() or (output / "verification.json").exists():
        raise ValueError("A closed panel cannot launch another worker")
    registration = check_registration(output)
    if key not in registration["planned_attempts"]:
        raise ValueError("Unregistered panel attempt; imports cannot be rerun")
    session = ref.read_json(output / "session.json")
    elapsed = (
        datetime.now(timezone.utc) - datetime.fromisoformat(session["started_utc"])
    ).total_seconds()
    if (
        session["registration_sha256"] != ref.sha(output / "registration.json")
        or session["wall_budget_seconds"]
        != registration["resources"]["session_wall_budget_seconds"]
        or session["automatic_retry"]
    ):
        raise ValueError("Panel session identity changed")
    if not 0 <= elapsed < session["wall_budget_seconds"]:
        raise ref.BudgetExceeded("Panel session is no longer live")
    starts = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
    expected = {
        "key": key,
        "attempt_id": f"{registration['output_directory']}/{key}",
        "initial_time": 0.0,
        "status": "started",
    }
    if (
        not starts
        or starts[-1] != expected
        or [s["key"] for s in starts] != registration["planned_attempts"][: len(starts)]
    ):
        raise ValueError("Worker has no matching ordered registered start entry")
    case, variant = key.rsplit("/", 1)
    method, refinement = registration["methods"][variant]
    return paths.integrate(
        campaign.graph.Model(registration["cases"][case]),
        output / key,
        method=method,
        refinement=refinement,
        duration=registration["duration"],
        numerics=registration["numerics"],
        resources=execution(registration)["resources"],
        artifact_root=output,
    )


def case_result(registration, case):
    selected = registration["references"][case]
    return {
        "policy": selected["policy"],
        "comparison": ref.read_json(ROOT / selected["comparison"]),
        "observations": ref.read_json(ROOT / selected["observations"]),
    }


def launch(output, registration, key, attempts, deadline):
    campaign.guard(deadline)
    attempt = {
        "key": key,
        "attempt_id": f"{registration['output_directory']}/{key}",
        "status": "started",
        "initial_time": 0.0,
    }
    attempts.append(attempt)
    with (output / "attempts.jsonl").open("a") as handle:
        handle.write(json.dumps(attempt, sort_keys=True) + "\n")
    log = output / f"{key.replace('/', '-')}.log"
    print(f"Starting registered {attempt['attempt_id']}", flush=True)
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
        incomplete = failure.exists() and ref.read_json(failure)["status"] == "incomplete"
        attempt["status"] = "incomplete" if incomplete else "refused"
        error = ref.BudgetExceeded if incomplete else ValueError
        raise error(f"Panel worker {attempt['status']}: {key}; no automatic retry")
    if (
        ref.read_json(output / key / "trajectory.json")["status"]
        != "complete_not_yet_cross_qualified"
    ):
        raise ValueError("Successful worker did not retain a complete trajectory")
    attempt["status"] = "complete_not_yet_cross_qualified"
    print(f"Completed {key}", flush=True)


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
    attempts, completed = [], []
    try:
        settings = execution(registration)
        case = registration["adopted_case"]
        (output / case).mkdir(parents=True, exist_ok=False)
        panel.observe(directories(registration, case), output, case, settings, deadline)
        completed.append(case)
        print(f"Recorded A2-adopted observers for {case}; original failure retained", flush=True)
        for case in registration["new_cases"]:
            for variant in registration["reference_order"]:
                launch(output, registration, f"{case}/{variant}", attempts, deadline)
            agreement = panel.compare(
                directories(registration, case), output, case, settings, deadline
            )
            if agreement["status"] != "pass":
                raise ValueError(f"Reference disagreement in {case}; no automatic amendment")
            panel.observe(directories(registration, case), output, case, settings, deadline)
            completed.append(case)
            print(f"Qualified {case}: score={agreement['maximum_score']:.9g}", flush=True)
        check_registration(output)
        combined = {case: case_result(registration, case) for case in registration["cases"]}
        payloads = previous.payload_hashes(output)
        campaign.guard(deadline)
        receipt = {
            "status": "pass",
            "scope": registration["scope"],
            "attempts": attempts,
            "new_observer_qualified_cases": completed,
            "cases": combined,
            "references": registration["references"],
            "seconds": perf_counter() - begun,
            "payload_hashes": payloads,
            "registration_sha256": ref.sha(output / "registration.json"),
            "amended_panel_cross_qualified": True,
            "qualified_conditions": len(combined),
            "original_campaign_reclassified": False,
            "original_qualified_conditions": 10,
            "independent_panel_audit": "pending",
            "NUM005c_complete": False,
            "production_changed": False,
            "candidate_selected": False,
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
            "new_observer_qualified_cases": completed,
            "original_qualified_cases": registration["original_qualified_cases"],
            "not_started": registration["planned_attempts"][len(attempts) :],
            "seconds": perf_counter() - begun,
            "no_automatic_retry": True,
            "original_campaign_reclassified": False,
            "registration_sha256": ref.sha(output / "registration.json"),
            "payload_hashes": previous.payload_hashes(output),
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
