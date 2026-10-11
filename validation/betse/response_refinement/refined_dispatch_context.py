"""D083: finer held-input dispatch registration; preserve the closed rejection."""

import argparse
import copy
import importlib
import json
import math
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "response_audit"))
audit_context = importlib.import_module("response_audit_context")
audit_job = importlib.import_module("response_audit_job")
c = audit_context.c
legacy = importlib.import_module("dispatch_preflight_context")
held = legacy.held
AUDIT = c.ROOT / "runs/ref-003e1-response-audit-2026-09-13/audit-01"
AUDIT_SHA = "fb95b54f0f29884cc09f0f5a001cad000e469857726fa3c6111a06f5fa35332f"
PLAN = HERE / "refined_dispatch_plan.json"
PRESERVATION = c.ROOT / "reports/ref-003e1-refined-dispatch-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e1-refined-dispatch-prelaunch.json"
NEW_FILES = {
    "refined_dispatch_plan.json",
    "refined_dispatch_context.py",
    "refined_dispatch_check.py",
    "refined_dispatch_native.py",
    "refined_dispatch_job.py",
    "test_refined_dispatch.py",
}
FALSE_FLAGS = (
    "trajectory_run",
    "trajectory_qualified",
    "native_convergence_qualified",
    "forcing_convergence_qualified",
    "biology_validated",
    "gpu_tested",
    "automatic_polling",
    "automatic_retry",
    "automatic_trajectory_launch",
)


def validate_plan(p):
    expected = {
        "schema": "cells.betse_refined_dispatch_plan@1",
        "hold_steps_s": [0.0000125, 0.00000625],
        "conditions": list(held.CONDITIONS),
        "constant_profile": "matched_constants",
        "duration_s": 0.001,
        "preparations": 8,
        "event_dispatch_calls": 960,
        "targeted_dispatches": 480,
        "nonzero_targeted_dispatches": 240,
        "control_values_checked": 345600,
        "control_atol": 2e-14,
        "raw_clock": "native_linspace_0_T_N",
        "terminal_control": "retain_last_interval_no_new_endpoint_event",
        "worker_timeout_seconds": 300,
        "total_timeout_seconds": 360,
        "max_artifact_bytes": 268435456,
        "max_worker_file_bytes": 33554432,
        "cpu_affinity": "0-3",
        "persist_each_completed_dispatch": True,
        "integration_calls": 0,
    } | dict.fromkeys(FALSE_FLAGS, False)
    c.require(
        json.dumps(p, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True),
        "Unregistered finer dispatch scope/resources",
    )


def coarse_row(condition):
    return next(r for r in legacy.rows(c.read(legacy.PLAN)) if r["condition"] == condition)


def rows(plan):
    validate_plan(plan)
    return [
        coarse_row(condition) | {"dt_s": h}
        for h in plan["hold_steps_s"]
        for condition in plan["conditions"]
    ]


def key(row):
    return f"{row['dt_s']:.8f}/{row['condition']}"


def mapping(row):
    """Versioned clock-only extension; 25 us remains an exact software overlap."""
    c.require(row["condition"] in held.CONDITIONS, "Unknown finer dispatch condition")
    coarse = coarse_row(row["condition"])
    c.require(
        row == coarse | {"dt_s": row["dt_s"]}
        and type(row["dt_s"]) is float
        and row["dt_s"] in c.read(held.PLAN)["control_probe_steps_s"],
        "Unknown finer dispatch row",
    )
    protocol, mapped = legacy.mapping(coarse)
    protocol = copy.deepcopy(protocol)
    count, scale, times = held.law.clock_parameters(c.read(held.law.PLAN), row["dt_s"])
    # Start from the frozen declared mapping, never from measured event history.
    for entry in protocol["yaml_overrides"]:
        path = entry[0]
        if path[0] in ("init time settings", "sim time settings") and path[1] in (
            "time step",
            "sampling rate",
        ):
            entry[1] = row["dt_s"]
        if path[0] in ("change Na mem", "change K mem", "change Cl mem"):
            if path[1] in ("change start", "change finish", "change rate"):
                entry[1] = times[("change start", "change finish", "change rate").index(path[1])]
    legacy.edits.require_dispatch_profiles(protocol)
    return protocol, mapped | {
        "steps": count,
        "dt_s": row["dt_s"],
        "raw_clock_scale": scale,
        "mapped_pulse_times_s": times,
        "raw_labels_s": [i * (mapped["duration_s"] / (count - 1)) for i in range(count - 1)]
        + [mapped["duration_s"]],
        "elapsed_times_s": [i * row["dt_s"] for i in range(count)],
    }


def sources():
    previous = c.read(AUDIT / "registration.json")["sources"]
    return previous | {"response_refinement/" + n: c.sha(HERE / n) for n in sorted(NEW_FILES)}


def authenticate():
    c.require(c.sha(AUDIT / "completion.json") == AUDIT_SHA, "D082 closeout changed")
    closed = c.read(AUDIT / "completion.json")
    c.require(
        closed["status"] == "failure_audit_closed_response_rejected"
        and closed["response_qualified"] is False
        and closed["failed_physical_comparisons"] == 150,
        "Not the reviewed failure closeout",
    )
    actual = audit_context.packet_hashes(AUDIT)
    c.require(
        set(actual) == set(closed["files_sha256"]) | audit_context.OPERATIONAL | {"completion.json"}
        and all(actual[n] == h for n, h in closed["files_sha256"].items()),
        "D082 audit artifacts changed",
    )
    registered = c.read(AUDIT / "registration.json")
    audit_job.validate_registration(registered)
    audit_job.capsule(AUDIT, registered)
    audit_job.validate_audit(c.read(AUDIT / "audit.json"), AUDIT, registered)
    c.require(
        audit_job.legacy_outcome(AUDIT / "legacy-regression.xml", 1) == closed["legacy_regression"],
        "D082 legacy outcome changed",
    )
    counts, modules = audit_context.receipts.test_counts(AUDIT / "regression.xml")
    c.require(
        counts == closed["new_tests"]
        and counts["tests"] == 70
        and modules == {"validation.betse.response_audit.test_saved_response"},
        "D082 new regression changed",
    )
    return audit_context.preservation_check()


def preserve():
    authenticate()
    previous = c.read(audit_context.PRESERVATION)["baseline_sha256"]
    pre = c.read(audit_context.PRELAUNCH)
    names = (
        set(audit_context.files.worktree())
        | set(previous)
        | set(pre["new_files_sha256_before_prelaunch"])
        | {str(audit_context.PRELAUNCH.relative_to(c.ROOT))}
    )
    owned = {str((HERE / n).relative_to(c.ROOT)) for n in NEW_FILES}
    baseline = {n: c.sha(c.ROOT / n) for n in sorted(names - owned)}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_refined_dispatch_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "audit_completion_sha256": AUDIT_SHA,
            "baseline_sha256": baseline,
            "audit_files_sha256": audit_context.packet_hashes(AUDIT),
            "capture_files_sha256": audit_context.packet_hashes(),
            "external_metadata_change": audit_context.EXTERNAL_METADATA,
        },
    )
    print(json.dumps({"status": "preserved", "baseline_files": len(baseline)}))


def preservation_check():
    preserved = authenticate()
    saved = c.read(PRESERVATION)
    c.require(
        saved["audit_completion_sha256"] == AUDIT_SHA
        and saved["audit_files_sha256"] == audit_context.packet_hashes(AUDIT)
        and saved["capture_files_sha256"] == audit_context.packet_hashes()
        and saved["external_metadata_change"] == audit_context.EXTERNAL_METADATA,
        "Reviewed audit/capture changed",
    )
    changed = {
        n: {"before": h, "after": c.sha(c.ROOT / n)}
        for n, h in saved["baseline_sha256"].items()
        if c.sha(c.ROOT / n) != h
    }
    c.require(set(changed) <= legacy.edits.ALLOWED_EDITS, "Unexpected pre-existing edit")
    return preserved | {
        "baseline_files": len(saved["baseline_sha256"]),
        "unchanged_baseline_files": len(saved["baseline_sha256"]) - len(changed),
        "changed_documents": changed,
        "audit_files_unchanged": len(saved["audit_files_sha256"]),
    }


def resources(plan):
    validate_plan(plan)
    root = audit_context.prior.DISPATCH
    measured = c.read(root / "completion.json")
    ratio = plan["event_dispatch_calls"] / measured["event_dispatch_calls"]
    seconds = math.ceil(1.5 * measured["elapsed_seconds"] * ratio + 30)
    size = math.ceil(1.25 * measured["artifact_bytes_before_receipt"] * ratio + 16 * 1024**2)
    largest = max(p.stat().st_size for p in root.glob("*/dispatch.json"))
    worker_file = math.ceil(1.25 * largest * 160 / 40)
    c.require(
        seconds < plan["worker_timeout_seconds"]
        and size < plan["max_artifact_bytes"]
        and worker_file < plan["max_worker_file_bytes"],
        "Prospective resources exceed cap",
    )
    return {
        "basis": "D080 measured preparation/dispatch scaled by calls plus explicit allowances",
        "prior_elapsed_seconds": measured["elapsed_seconds"],
        "estimated_worker_seconds_with_allowances": seconds,
        "estimated_artifact_bytes_with_allowances": size,
        "estimated_largest_worker_file_bytes_with_allowances": worker_file,
        "peak_RAM_measured": False,
    }


def prelaunch(tests, expected):
    preserved = preservation_check()
    plan = c.read(PLAN)
    counts, modules = audit_context.receipts.test_counts(tests)
    c.require(
        counts["tests"] == expected
        and modules == {"validation.betse.response_refinement.test_refined_dispatch"},
        "Wrong refined dispatch software coverage",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
            timeout=20,
        ).strip()
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    new = {n: h for n, h in audit_context.files.worktree().items() if n not in baseline}
    new[str(tests.relative_to(c.ROOT))] = c.sha(tests)
    c.write(
        PRELAUNCH,
        {
            "schema": "cells.betse_refined_dispatch_prelaunch@1",
            "status": "software_checks_pass_not_native_execution",
            "created_utc": datetime.now(UTC).isoformat(),
            "plan": plan,
            "sources": sources(),
            "audit_completion_sha256": AUDIT_SHA,
            "preservation_sha256": c.sha(PRESERVATION),
            "test_receipt": str(tests.relative_to(c.ROOT)),
            "test_receipt_sha256": c.sha(tests),
            "tests": counts,
            "quality": quality,
            "resources": resources(plan),
            "new_files_sha256_before_prelaunch": new,
            "native_execution": False,
            **preserved,
        },
    )
    print(
        json.dumps(
            {
                "status": "software_checks_pass_not_native_execution",
                "tests": counts,
                "resources": resources(plan),
                "quality": quality,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preserve", "prelaunch"))
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--expected-tests", type=int)
    args = parser.parse_args()
    if args.action == "preserve":
        preserve()
    else:
        prelaunch(args.tests.resolve(), args.expected_tests)
