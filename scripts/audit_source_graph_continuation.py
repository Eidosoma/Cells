"""Read-only composite audit: pinned old subset plus every newly completed curve."""

import argparse
import json
import sys
import zipfile
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_source_graph_paths as audit  # noqa: E402
from scripts import continue_source_graph_paths as continuation  # noqa: E402


def check_integrity(output):
    registration = continuation.check_registration(output)
    passed = (output / "verification.json").exists()
    name = "verification.json" if passed else "failure.json"
    receipt = audit.read(output / name)
    if passed and (output / "failure.json").exists():
        raise ValueError("Both pass and failure receipts exist")
    names = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
    if names != set(receipt["payload_hashes"]) | {name}:
        raise ValueError("Continuation payload inventory differs")
    for path, digest in receipt["payload_hashes"].items():
        target = output / path
        if not target.resolve().is_relative_to(output) or audit.sha(target) != digest:
            raise ValueError(f"Continuation payload differs: {path}")
    if receipt["registration_sha256"] != audit.sha(output / "registration.json"):
        raise ValueError("Continuation registration hash differs")
    attempts = receipt["attempts"]
    attempted = [a["key"] for a in attempts]
    if attempted != registration["planned_attempts"][: len(attempted)] or any(
        a["initial_time"] != 0
        or a["attempt_id"] != f"{registration['output_directory']}/{a['key']}"
        for a in attempts
    ):
        raise ValueError("Continuation attempt order/identity differs")
    starts = (
        [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
        if attempts
        else []
    )
    if starts != [
        {k: a[k] for k in ("key", "attempt_id", "initial_time")} | {"status": "started"}
        for a in attempts
    ]:
        raise ValueError("Continuation start ledger differs")
    for attempt in attempts:
        if audit.sha(output / f"{attempt['key'].replace('/', '-')}.log") != attempt["log_sha256"]:
            raise ValueError("Attempt log differs")
    session = audit.read(output / "session.json")
    if (
        session["registration_sha256"] != receipt["registration_sha256"]
        or session["wall_budget_seconds"]
        != registration["resources"]["session_wall_budget_seconds"]
        or session["automatic_retry"]
    ):
        raise ValueError("Session registration/budget differs")
    if passed:
        if (
            receipt["status"] != "pass"
            or attempted != registration["planned_attempts"]
            or any(
                a["status"] != "complete_not_yet_cross_qualified" or a["returncode"] != 0
                for a in attempts
            )
            or receipt["seconds"] > registration["resources"]["session_wall_budget_seconds"]
            or receipt["new_cross_qualified_cases"] != registration["new_cases"]
            or set(receipt["cases"]) != set(registration["cases"])
            or not receipt["full_panel_cross_qualified"]
        ):
            raise ValueError("Incomplete continuation cannot pass")
        expected = {
            case: data["directory"] for case, data in registration["imported_cases"].items()
        } | {
            case: f"{registration['output_directory']}/{case}" for case in registration["new_cases"]
        }
        if receipt["case_directories"] != expected:
            raise ValueError("Composite case sources differ")
        for case, folder in expected.items():
            actual = continuation.case_result(ROOT / folder)
            if (
                receipt["cases"][case] != actual
                or actual["comparison"]["status"] != "pass"
                or actual["comparison"]["maximum_score"]
                > registration["numerics"]["reference_agreement_fraction"]
                or actual["comparison"]["maximum_accounting_residual"]
                > registration["numerics"]["accounting_atol"]
            ):
                raise ValueError("Composite comparison/readout differs")
    elif (
        receipt["status"] not in ("incomplete", "unqualified")
        or receipt["not_started"] != registration["planned_attempts"][len(attempted) :]
    ):
        raise ValueError("Invalid continuation stopping receipt")
    return registration, receipt, name


def verify(output):
    begun = perf_counter()
    registration, receipt, name = check_integrity(output)
    deadline = begun + registration["resources"]["session_wall_budget_seconds"]
    with zipfile.ZipFile(output / "reference_sources.zip") as archive:
        panel = json.loads(archive.read("configs/reference/source_emt_pair_panel_v1.json"))
    trajectories, cases = {}, {}
    # Audit complete attempts even in a stopped continuation; never promote partial paths.
    for attempt in receipt["attempts"]:
        if attempt["status"] != "complete_not_yet_cross_qualified":
            continue
        key = attempt["key"]
        case, _ = key.rsplit("/", 1)
        trajectories[key] = audit.audit_trajectory(
            output / key, registration["cases"][case], registration, panel, deadline
        )
    for case in receipt["new_cross_qualified_cases"]:
        cases[case] = {
            "comparison_grid": audit.audit_comparison_grid(output / case, registration, deadline),
            "observations": audit.audit_observations(
                output / case, registration["cases"][case], registration, deadline
            ),
        }
    # Recheck all identities after the bounded streaming audit; no solver or new trajectory.
    check_integrity(output)
    if perf_counter() > deadline:
        raise TimeoutError("Read-only continuation audit session exhausted")
    return {
        "status": "pass",
        "campaign_status": receipt["status"],
        "scope": "pinned_prior_subset_reuse_plus_new_dense_domain_accounting_grid_observer_audit",
        "NUM005c1_complete": receipt["status"] == "pass",
        "NUM005c_complete": False,
        "receipt_sha256": audit.sha(output / name),
        "registration_sha256": audit.sha(output / "registration.json"),
        "prior_audit_sha256": registration["prior_audit_sha256"],
        "prior_receipt_sha256": registration["prior_hashes"]["failure.json"],
        "prior_audited_conditions_reused": list(registration["imported_cases"]),
        "new_trajectory_audits": trajectories,
        "new_case_audits": cases,
        "aggregate_artifact_bytes": continuation.tree_bytes(continuation.PRIOR)
        + continuation.tree_bytes(output),
        "new_payloads": len(receipt["payload_hashes"]),
        "new_archived_source_files": len(registration["source_hashes"]),
        "seconds": perf_counter() - begun,
        "audit_wall_budget_seconds": registration["resources"]["session_wall_budget_seconds"],
        "incomplete_attempts_not_numerically_promoted": True,
        "comparison_flux_scores": "online_recorded_not_independently_recomputed_by_this_audit",
        "production_changed": False,
        "candidate_selected": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory.absolute()), indent=2))


if __name__ == "__main__":
    main()
