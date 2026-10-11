"""D078: preserve completed expanded capture and register a separate offline closeout."""

import argparse
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import cluster_closeout as files
import contact as c
import expanded_bridge_context as capture
import full_loop_audit_context as prior
import phase_bridge_context as edits

SESSION = c.ROOT / "runs/ref-003e0-expanded-2026-09-12/capture-01"
ANCHORS = {
    "capture.json": "0f71ad7752585fa2b82e00448664f55c5d265d7502089dac6a9c08c26ea4f63b",
    "registration.json": "1c25ce10d09cb5f564effcd70a06c0debe4904671430bb6a7cbfe1f6b13e0e71",
    "sources.zip": "f1a7ce40a3173f61034e74c8f2d913d4ce2979b6d6b061bdf55aa151566e3902",
    "launch.json": "c1dab165004935953cfa483c6d163a6c867a388fff2d63db31c1077786f0544c",
}
CAPTURE_PREFLIGHT_SHA = "f5443bdb366163cf74b6e60dd09b7c06e739ea4aa8eba6f55e0006b1521c15fc"
PRESERVATION = c.ROOT / "reports/ref-003e0-expanded-audit-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e0-expanded-audit-prelaunch.json"
NEW_FILES = {
    "expanded_audit_context.py",
    "expanded_audit.py",
    "expanded_audit_job.py",
    "test_saved_expanded.py",
}
COMPARISONS = 1_232_616
JOB_PLAN = {
    "schema": "cells.betse_expanded_audit_job_plan@1",
    "cpu_affinity": "0-3",
    "stage_timeout_seconds": 180,
    "total_timeout_seconds": 420,
    "max_artifact_bytes": 67108864,
    "stages": ["independent_saved_data_audit", "focused_regression"],
    "test_modules": [
        "test_full_loop_bridge.py",
        "test_full_loop_observer.py",
        "test_saved_full_loop.py",
        "test_expanded_bridge.py",
        "test_saved_expanded.py",
    ],
    "capture_rerun": False,
    "automatic_retry": False,
    "automatic_expansion": False,
}


def packet_hashes():
    return prior.packet_hashes(SESSION)


def authenticate():
    c.require(c.sha(capture.PRELAUNCH) == CAPTURE_PREFLIGHT_SHA, "D077 preflight changed")
    preflight = c.read(capture.PRELAUNCH)
    for n, h in preflight["new_files_sha256_before_prelaunch"].items():
        c.require(c.sha(c.ROOT / n) == h, "Frozen D077 source/evidence changed: " + n)
    for n, h in ANCHORS.items():
        c.require(c.sha(SESSION / n) == h, "Expanded capture anchor changed")
    registered = c.read(SESSION / "registration.json")
    capture.validate_plan(registered["plan"])
    c.require(registered["sources"] == preflight["sources"], "Expanded source coverage changed")
    for n, h in registered["sources"].items():
        c.require(c.sha(c.HERE / n) == h, "Captured expanded source changed: " + n)
    receipt = c.read(SESSION / "capture.json")
    actual = packet_hashes()
    c.require(
        all(actual.get(n) == h for n, h in receipt["files_sha256"].items())
        and set(actual)
        == set(receipt["files_sha256"])
        | {"capture.json", "launch.json", "runner.stdout.log", "runner.stderr.log"},
        "Expanded captured payloads changed",
    )
    return capture.authenticate()


def sources():
    return {n: c.sha(c.HERE / n) for n in sorted(NEW_FILES)}


def preserve():
    accepted = authenticate()
    owned = {"validation/betse/" + n for n in NEW_FILES}
    baseline = {n: h for n, h in files.worktree().items() if n not in owned}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_expanded_audit_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "anchors": ANCHORS,
            "baseline_sha256": baseline,
            "capture_files_sha256": packet_hashes(),
            "pilot_files_sha256": prior.packet_hashes(),
            "pilot_audit_files_sha256": prior.packet_hashes(capture.SESSION),
            "accepted_sources": accepted["implementation_files_sha256"],
        },
    )
    print(
        json.dumps(
            {
                "status": "preserved",
                "baseline_files": len(baseline),
                "capture_files": len(packet_hashes()),
            }
        )
    )


def preservation_check():
    accepted = authenticate()
    saved = c.read(PRESERVATION)
    c.require(saved["accepted_sources"] == accepted["implementation_files_sha256"], "Cells changed")
    c.require(saved["capture_files_sha256"] == packet_hashes(), "Saved expanded packet changed")
    c.require(saved["pilot_files_sha256"] == prior.packet_hashes(), "Original pilot packet changed")
    c.require(
        saved["pilot_audit_files_sha256"] == prior.packet_hashes(capture.SESSION),
        "Pilot closeout changed",
    )
    changed = {
        n: {"before": h, "after": c.sha(c.ROOT / n)}
        for n, h in saved["baseline_sha256"].items()
        if c.sha(c.ROOT / n) != h
    }
    c.require(set(changed) <= edits.ALLOWED_EDITS, "Unexpected pre-existing edit")
    return {
        "baseline_files": len(saved["baseline_sha256"]),
        "unchanged_baseline_files": len(saved["baseline_sha256"]) - len(changed),
        "changed_documents": changed,
        "capture_files_unchanged": len(saved["capture_files_sha256"]),
        "pilot_files_unchanged": len(saved["pilot_files_sha256"]),
        "pilot_audit_files_unchanged": len(saved["pilot_audit_files_sha256"]),
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": sum(
            n.startswith("src/") and n.endswith(".py")
            for n in accepted["implementation_files_sha256"]
        ),
    }


def resource_estimate(tests):
    from xml.etree import ElementTree as ET

    pilot = c.read(capture.SESSION / "completion.json")
    expanded = c.read(SESSION / "capture.json")
    test_seconds = sum(float(s.get("time", 0)) for s in ET.parse(tests).getroot().iter("testsuite"))
    step_ratio = expanded["observed_steps"] / 240
    audit_estimate = math.ceil(1.5 * step_ratio * pilot["stage_seconds"]["audit"] + 15)
    # 165 previous tests, the 125 D077 preflight tests, and the new measured tests.
    regression_estimate = math.ceil(
        1.5 * (pilot["stage_seconds"]["regression"] + 17.67 + test_seconds) + 10
    )
    estimated_bytes = math.ceil(
        step_ratio * pilot["artifact_bytes_before_receipt"] + 8 * 1024 * 1024
    )
    c.require(
        max(audit_estimate, regression_estimate) < JOB_PLAN["stage_timeout_seconds"],
        "Offline stage estimate exceeds cap",
    )
    c.require(
        audit_estimate + regression_estimate + 30 < JOB_PLAN["total_timeout_seconds"],
        "Offline total estimate exceeds cap",
    )
    c.require(
        estimated_bytes < JOB_PLAN["max_artifact_bytes"], "Offline output estimate exceeds cap"
    )
    return {
        "basis": (
            "D076 measured audit/regression, D077 focused tests, current preflight "
            "and explicit allowances; not expanded audit timing"
        ),
        "expected_comparisons": COMPARISONS,
        "step_multiplier": step_ratio,
        "new_preflight_seconds": test_seconds,
        "estimated_audit_seconds_with_allowances": audit_estimate,
        "estimated_regression_seconds_with_allowances": regression_estimate,
        "estimated_artifact_bytes_with_allowances": estimated_bytes,
        "existing_capture_bytes_not_duplicated": expanded["artifact_bytes_before_receipt"],
    }


def prelaunch(tests, expected):
    preserved = preservation_check()
    counts, modules = prior.test_counts(tests)
    c.require(
        counts["tests"] == expected and modules == {"validation.betse.test_saved_expanded"},
        "Wrong expanded audit preflight coverage",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
        ).strip()
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    result = {
        "schema": "cells.betse_expanded_audit_prelaunch@1",
        "status": "pass",
        "checked_utc": datetime.now(UTC).isoformat(),
        "sources": sources(),
        "anchors": ANCHORS,
        "preservation_sha256": c.sha(PRESERVATION),
        "tests": counts,
        "test_receipt": str(tests.relative_to(c.ROOT)),
        "test_receipt_sha256": c.sha(tests),
        "quality": quality,
        "job_plan": JOB_PLAN,
        "resources": resource_estimate(tests),
        "new_files_sha256_before_prelaunch": {
            n: h for n, h in files.worktree().items() if n not in baseline
        },
        "independent_numerical_audit_run": False,
        "capture_rerun": False,
        **preserved,
    }
    c.write(PRELAUNCH, result)
    print(
        json.dumps(
            {
                "status": "pass",
                "tests": counts,
                "resources": result["resources"],
                "quality": quality,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preserve", "prelaunch"))
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--expected-tests", type=int)
    args = parser.parse_args()
    if args.command == "preserve":
        preserve()
    else:
        prelaunch(args.tests.resolve(), args.expected_tests)
