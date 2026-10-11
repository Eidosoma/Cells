"""D076: preserve and authenticate the completed narrow SIM pilot for offline audit."""

import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import cluster_closeout as files
import contact as c
import full_loop_bridge_context as pilot
import phase_bridge_context as edits

SESSION = c.ROOT / "runs/ref-003e0-loop-2026-09-12/pilot-01"
ANCHORS = {
    "capture.json": "0bf8f5674a6b92af01171f95bab652d5c0cbfd8033d174d339fac9777a283b12",
    "registration.json": "1b6105df591e482697950feeac9b43f0228ae22038273c3f8c5284a6c6f90d82",
    "sources.zip": "0baa5e0a5e6b4482206dc4b96d07790c769e28815e66bcb5e1dc710e0976ac45",
    "launch.json": "381fdbc002d7703da669b0cf8929ab5d493089a241831aa2397dd02e871c908b",
}
PILOT_PRELAUNCH_SHA = "4bd938cd9e1fa7f14c6bc4bd19dc02c570940002e79e364831788d20b5effe03"
PRESERVATION = c.ROOT / "reports/ref-003e0-loop-audit-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e0-loop-audit-prelaunch.json"
NEW_FILES = {
    "full_loop_audit_context.py",
    "full_loop_audit.py",
    "full_loop_audit_job.py",
    "test_saved_full_loop.py",
}
JOB_PLAN = {
    "schema": "cells.betse_full_loop_audit_job_plan@1",
    "cpu_affinity": "0-3",
    "stage_timeout_seconds": 90,
    "total_timeout_seconds": 210,
    "max_artifact_bytes": 67108864,
    "stages": ["independent_saved_data_audit", "focused_regression"],
    "test_modules": [
        "test_full_loop_bridge.py",
        "test_full_loop_observer.py",
        "test_saved_full_loop.py",
    ],
    "capture_rerun": False,
    "automatic_retry": False,
    "automatic_expansion": False,
}


def packet_hashes(output=SESSION):
    return {str(p.relative_to(output)): c.sha(p) for p in sorted(output.rglob("*")) if p.is_file()}


def authenticate():
    c.require(c.sha(pilot.PRELAUNCH) == PILOT_PRELAUNCH_SHA, "D075 prelaunch changed")
    prelaunch = c.read(pilot.PRELAUNCH)
    for name, digest in prelaunch["new_files_sha256_before_prelaunch"].items():
        c.require(c.sha(c.ROOT / name) == digest, "Frozen D075 source/evidence changed: " + name)
    for name, digest in ANCHORS.items():
        c.require(c.sha(SESSION / name) == digest, "Completed pilot anchor changed")
    registered = c.read(SESSION / "registration.json")
    pilot.validate_plan(registered["plan"])
    c.require(registered["sources"] == prelaunch["sources"], "Pilot source coverage differs")
    for name, digest in registered["sources"].items():
        c.require(c.sha(c.HERE / name) == digest, "Captured pilot source changed")
    capture = c.read(SESSION / "capture.json")
    for name, digest in capture["files_sha256"].items():
        c.require(c.sha(SESSION / name) == digest, "Captured pilot payload changed")
    c.require(
        set(packet_hashes())
        == set(capture["files_sha256"])
        | {"capture.json", "launch.json", "runner.stdout.log", "runner.stderr.log"},
        "Pilot file coverage changed",
    )
    return pilot.authenticate()


def sources():
    # Older source capsules remain valid subsets of the growing adapter directory.
    return {name: c.sha(c.HERE / name) for name in sorted(NEW_FILES)}


def preserve():
    accepted = authenticate()
    owned = {"validation/betse/" + n for n in NEW_FILES}
    baseline = {n: h for n, h in files.worktree().items() if n not in owned}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_full_loop_audit_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "anchors": ANCHORS,
            "pilot_prelaunch_sha256": PILOT_PRELAUNCH_SHA,
            "baseline_sha256": baseline,
            "pilot_files_sha256": packet_hashes(),
            "accepted_sources": accepted["implementation_files_sha256"],
        },
    )
    print(
        json.dumps(
            {
                "status": "preserved",
                "baseline_files": len(baseline),
                "pilot_files": len(packet_hashes()),
            }
        )
    )


def preservation_check():
    accepted = authenticate()
    saved = c.read(PRESERVATION)
    c.require(saved["pilot_files_sha256"] == packet_hashes(), "Saved pilot packet changed")
    c.require(saved["accepted_sources"] == accepted["implementation_files_sha256"], "Cells changed")
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
        "pilot_files_unchanged": len(saved["pilot_files_sha256"]),
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": sum(
            n.startswith("src/") and n.endswith(".py")
            for n in accepted["implementation_files_sha256"]
        ),
    }


def test_counts(path):
    suites = list(ET.parse(path).getroot().iter("testsuite"))
    counts = {
        key: sum(int(s.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    c.require(
        counts["tests"] > 0 and all(counts[k] == 0 for k in ("failures", "errors", "skipped")),
        "Incomplete/failing audit preflight tests",
    )
    return counts, {case.get("classname") for s in suites for case in s.findall("testcase")}


def prelaunch(tests, expected):
    preserved = preservation_check()
    counts, modules = test_counts(tests)
    c.require(
        counts["tests"] == expected and modules == {"validation.betse.test_saved_full_loop"},
        "Wrong focused audit preflight coverage",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
        ).strip()
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    c.write(
        PRELAUNCH,
        {
            "schema": "cells.betse_full_loop_audit_prelaunch@1",
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
            "new_files_sha256_before_prelaunch": {
                n: h for n, h in files.worktree().items() if n not in baseline
            },
            "independent_numerical_audit_run": False,
            "capture_rerun": False,
            **preserved,
        },
    )
    print(json.dumps({"status": "pass", "tests": counts, **preserved}))


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
