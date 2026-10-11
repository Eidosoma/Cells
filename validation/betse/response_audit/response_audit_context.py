"""D082: preserve the rejected response and separately register an offline audit."""

import argparse
import hashlib
import importlib
import json
import math
import stat
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
# This nested audit package deliberately does not enlarge the frozen adapter's
# flat 88-file source inventory. Existing regression tests can run unchanged.
sys.path.insert(0, str(HERE.parent))
c = importlib.import_module("contact")
prior = importlib.import_module("held_response_context")
files = importlib.import_module("cluster_closeout")
receipts = importlib.import_module("full_loop_audit_context")
SESSION = c.ROOT / "runs/ref-003e1-response-2026-09-13/capture-01"
PRESERVATION = c.ROOT / "reports/ref-003e1-response-audit-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e1-response-audit-prelaunch.json"
CAPTURE_PREFLIGHT_SHA = "2e6b2186686c16b372ae279bf47db2e492e88f481ecf85ec6af55f3cc6d915af"
ANCHORS = {
    "failure.json": "557eb5bdf908451c67e96e04f09fbce303f15f8389eaaeb7c53edca2e7486703",
    "registration.json": "8c7b1e5fe7ff8f963ed14896fc57cf8e174c8f7e5812d33a0339c87b7f17349b",
    "sources.zip": "e287cb9dbb102859446a7c8d8940b8fbc3cf818a013f791e197b87b89a05ed8e",
    "launch.json": "1d485eed1ea858bf1388557d0e0edb97754e747083d2487cf8a7b74bc2ae88a8",
    "comparison.json": "8f5354995beb44324b3bc92fa15527ff26de5a6fb44bff364558b758706ed939",
    "native.json": "7c988fa9346a7e713cb1235e99adff2db8dd7af3917b17678f43e303606f67f0",
    "cells.json": "1ecd08895df82580be10bf9c210096c371ccb24ac969d1f19870ae2f62b28d4f",
}
NEW_FILES = {
    "response_audit_context.py",
    "response_audit.py",
    "response_audit_job.py",
    "test_saved_response.py",
}
OPERATIONAL = {"launch.json", "runner.stdout.log", "runner.stderr.log"}
PLAN = {
    "schema": "cells.betse_held_response_audit_plan@1",
    "cpu_affinity": "0-3",
    "stage_timeout_seconds": {"audit": 90, "legacy_regression": 90, "regression": 120},
    "total_timeout_seconds": 360,
    "max_artifact_bytes": 16777216,
    "max_worker_file_bytes": 8388608,
    "test_modules": [
        "test_held_response.py",
        "test_held_response_check.py",
        "response_audit/test_saved_response.py",
    ],
    "frozen_comparisons": 345576,
    "frozen_failures": 150,
    "independent_surface_comparisons": 147312,
    "internal_comparisons": 198264,
    "capture_rerun": False,
    "original_packet_rewritten": False,
    "automatic_polling": False,
    "automatic_retry": False,
    "automatic_expansion": False,
    "response_qualified": False,
}
EXTERNAL_METADATA = {
    "path": ".gitignore",
    "before_sha256": "4f9e07619d8b890d1a6144a8270fef4325058fb248b278c841f17cc25bbeb365",
    "after_sha256": "333c9eb6f13478d273688c4bb4c7509cc43ca195885fa8a0a9dec63d9646c4e5",
    "user_commit": "fa5ec7127cfb0062e1151904b90f25a38b3e9bd5",
    "added_line": "reports/ref-*.xml",
    "old_preservation_guard_expected_to_reject": True,
    "changed_by_audit": False,
}


def sources():
    return {"response_audit/" + n: c.sha(HERE / n) for n in sorted(NEW_FILES)}


def packet_hashes(output=SESSION):
    c.require(output.is_dir() and not output.is_symlink(), "Not a regular response packet")
    result = {}
    for p in sorted(output.rglob("*")):
        c.require(
            not p.is_symlink() and (p.is_dir() or stat.S_ISREG(p.stat().st_mode)),
            "Packet contains a link or special file",
        )
        if p.is_file():
            result[str(p.relative_to(output))] = c.sha(p)
    return result


def expected_paths(registered):
    prior.validate_plan(registered["plan"])
    c.require(
        registered["native_rows"] == prior.native_rows(registered["plan"])
        and registered["cells_rows"] == prior.cells_rows(registered["plan"]),
        "Audit row coverage differs",
    )
    result = {
        "registration.json",
        "sources.zip",
        "started.json",
        "native.json",
        "cells.json",
        "comparison.json",
        "native.log",
        "cells.log",
        "comparison.log",
        "matplotlib-cache/fontlist-v3.11.0.json",
    }
    common = {
        "started.json",
        "core.json",
        "final-state.json",
        "final-metadata.json",
        "result.json",
        "checks.json",
        "native.yaml",
        "INITS/world_1.betse.gz",
        "SIMS/sim_1.betse.gz",
    }
    observed = {"dynamics.json", "loop-entry.json", "loop-metadata.json", "events.json"}
    for row in registered["native_rows"]:
        for mode in registered["plan"]["native_modes"]:
            result |= {
                f"native/{row['condition']}/{mode}/{n}"
                for n in common | (observed if mode == "observed" else set())
            }
    for k, row in enumerate(registered["cells_rows"]):
        result |= {f"cells/{row['id']}/result.json", f"cells-started/{k:02d}.json"}
    return result


def verify_manifest(output, registered):
    """Structural and hash checks also accept pytest-owned, rehashed corruptions."""
    actual, expected = packet_hashes(output), expected_paths(registered)
    failure = c.read(output / "failure.json")
    c.require(
        set(actual) == expected | OPERATIONAL | {"failure.json"}
        and set(failure["files_sha256"]) == expected,
        "Response payload coverage differs",
    )
    c.require(
        all(actual[n] == h for n, h in failure["files_sha256"].items()),
        "Response payload digest differs",
    )
    c.require(
        all((output / n).stat().st_size > 0 for n in expected if not n.endswith(".log")),
        "Empty response payload",
    )
    return failure


def authenticate():
    c.require(c.sha(prior.PRELAUNCH) == CAPTURE_PREFLIGHT_SHA, "D081 prelaunch changed")
    c.require(
        all(c.sha(SESSION / n) == h for n, h in ANCHORS.items()), "D081 response anchor changed"
    )
    registered = c.read(SESSION / "registration.json")
    prior.validate_registration(registered)
    verify_manifest(SESSION, registered)
    with zipfile.ZipFile(SESSION / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) == len(registered["sources"]) == 88
            and set(names) == set(registered["sources"]),
            "D081 capsule coverage differs",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest()
                == c.sha(c.HERE / n)
                == registered["sources"][n]
                for n in names
            ),
            "D081 capsule content differs",
        )
    prior.authenticate()
    # The user committed this metadata change while D082 was being prepared.
    # Do not rewrite the historical guard, silently allow arbitrary changes,
    # or drop ignored XML evidence from the new preservation inventory.
    baseline = c.read(prior.PRESERVATION)["baseline_sha256"]
    path = EXTERNAL_METADATA["path"]
    contents = (c.ROOT / path).read_bytes()
    added = (EXTERNAL_METADATA["added_line"] + "\n").encode()
    c.require(
        contents.endswith(added)
        and hashlib.sha256(contents[: -len(added)]).hexdigest()
        == baseline[path]
        == EXTERNAL_METADATA["before_sha256"]
        and c.sha(c.ROOT / path) == EXTERNAL_METADATA["after_sha256"],
        "External ignore-rule amendment differs",
    )
    changed = {n for n, h in baseline.items() if c.sha(c.ROOT / n) != h}
    c.require(
        changed <= prior.edits.ALLOWED_EDITS | {path},
        "Unexpected change beyond recorded metadata amendment",
    )
    return c.authenticate_cells()


def preserve():
    accepted = authenticate()
    owned = {str((HERE / n).relative_to(c.ROOT)) for n in NEW_FILES}
    old_names = (
        set(c.read(prior.PRESERVATION)["baseline_sha256"])
        | set(c.read(prior.PRELAUNCH)["new_files_sha256_before_prelaunch"])
        | {str(prior.PRELAUNCH.relative_to(c.ROOT))}
    )
    baseline = {n: c.sha(c.ROOT / n) for n in sorted((set(files.worktree()) | old_names) - owned)}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_held_response_audit_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "anchors": ANCHORS,
            "external_metadata_change": EXTERNAL_METADATA,
            "baseline_sha256": baseline,
            "capture_files_sha256": packet_hashes(),
            "accepted_sources": accepted["implementation_files_sha256"],
            "runtime": accepted["runtime"],
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
    accepted, saved = authenticate(), c.read(PRESERVATION)
    c.require(
        saved["anchors"] == ANCHORS
        and saved["external_metadata_change"] == EXTERNAL_METADATA
        and saved["capture_files_sha256"] == packet_hashes(),
        "Rejected response packet changed",
    )
    c.require(
        saved["accepted_sources"] == accepted["implementation_files_sha256"]
        and saved["runtime"] == accepted["runtime"],
        "Accepted production/runtime changed",
    )
    changed = {
        n: {"before": h, "after": c.sha(c.ROOT / n)}
        for n, h in saved["baseline_sha256"].items()
        if c.sha(c.ROOT / n) != h
    }
    c.require(set(changed) <= prior.edits.ALLOWED_EDITS, "Unexpected pre-existing edit")
    return {
        "baseline_files": len(saved["baseline_sha256"]),
        "unchanged_baseline_files": len(saved["baseline_sha256"]) - len(changed),
        "changed_documents": changed,
        "capture_files_unchanged": len(saved["capture_files_sha256"]),
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": 51,
    }


def resource_estimate(tests):
    test_seconds = sum(float(s.get("time", 0)) for s in ET.parse(tests).getroot().iter("testsuite"))
    comparison_seconds = c.read(SESSION / "comparison.json")["elapsed_seconds"]
    old_test_seconds = sum(
        float(s.get("time", 0))
        for s in ET.parse(c.ROOT / "reports/ref-003e1-response-checks-03.xml")
        .getroot()
        .iter("testsuite")
    )
    estimates = {
        "audit": math.ceil(2 * comparison_seconds + 30),
        "legacy_regression": math.ceil(1.5 * old_test_seconds + 15),
        "regression": math.ceil(1.5 * test_seconds + 15),
    }
    c.require(
        all(estimates[k] < PLAN["stage_timeout_seconds"][k] for k in estimates)
        and sum(estimates.values()) + 30 < PLAN["total_timeout_seconds"],
        "Audit resource estimate exceeds wall cap",
    )
    size = 4 * (SESSION / "comparison.json").stat().st_size + 4 * 1024 * 1024
    c.require(size < PLAN["max_artifact_bytes"], "Audit output estimate exceeds cap")
    return {
        "basis": (
            "D081 comparison/focused-test measurements plus current preflight "
            "and explicit allowances"
        ),
        "stage_seconds_with_allowances": estimates,
        "estimated_artifact_bytes_with_allowances": size,
        "new_preflight_seconds": test_seconds,
        "original_capture_copied": False,
        "peak_RAM_measured": False,
    }


def prelaunch(tests, expected):
    preserved = preservation_check()
    counts, modules = receipts.test_counts(tests)
    c.require(
        counts["tests"] == expected
        and modules == {"validation.betse.response_audit.test_saved_response"},
        "Wrong response audit preflight coverage",
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
    # Explicitly include the JUnit receipt even though the user's rule ignores it.
    new_files = {n: h for n, h in files.worktree().items() if n not in baseline} | {
        str(tests.relative_to(c.ROOT)): c.sha(tests)
    }
    result = {
        "schema": "cells.betse_held_response_audit_prelaunch@1",
        "status": "pass",
        "created_utc": datetime.now(UTC).isoformat(),
        "plan": PLAN,
        "sources": sources(),
        "anchors": ANCHORS,
        "external_metadata_change": EXTERNAL_METADATA,
        "preservation_sha256": c.sha(PRESERVATION),
        "tests": counts,
        "test_receipt": str(tests.relative_to(c.ROOT)),
        "test_receipt_sha256": c.sha(tests),
        "quality": quality,
        "resources": resource_estimate(tests),
        "new_files_sha256_before_prelaunch": new_files,
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
