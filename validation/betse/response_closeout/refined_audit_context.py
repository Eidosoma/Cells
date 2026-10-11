"""D086: freeze the completed split-provenance response for a read-only audit."""

import argparse
import importlib
import json
import math
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "response_resume"))
prior = importlib.import_module("trace_resume_context")
c, files, receipts = prior.c, prior.audit.files, prior.audit.receipts
SESSION = c.ROOT / "runs/ref-003e1-trace-resume-2026-09-13/capture-01"
PRESERVATION = c.ROOT / "reports/ref-003e1-refined-audit-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e1-refined-audit-prelaunch.json"
PLAN = HERE / "refined_audit_plan.json"
CAPTURE_PRELAUNCH_SHA = "bff55be2f9d09e1ec0f8d11e8be42d27dfa145114c03b1783fd58a9ccba84b23"
FAILED_PREFLIGHT = c.ROOT / "reports/ref-003e1-refined-audit-checks-01.xml"
FAILED_PREFLIGHT_SHA = "59f4f2fcf68a292f66b373a25802466899943c4c17729befe379a2e272f3331c"
ANCHORS = {
    "capture.json": "e6e765413e6f8a160689e12f1fe38ed68ee5c651704f4055433cd5983797a53c",
    "registration.json": "4305faee24b080ca63ab67721ce4b86d0116b084f5c2082ed706ea4d9b366ffb",
    "comparison.json": "fa2f2cb7d841ee6804f2d637f648926f967e3aa76ccca8ec09a160b87157134f",
    "cells.json": "8f82cf9630429d2a76a218d171c81ccf7defa012f901c14239ec7b4e5c38a504",
    "sources.zip": "c85aa0a9b090bb45e4cee5dc5339d3ada1148686a7cbae7e370464a7521cedfd",
    "launch.json": "7aba009d06d3ccb790edc418e694126b9810daf626230d4d66cc0407824cabba",
}
NEW_FILES = {
    "refined_audit_plan.json",
    "refined_audit_context.py",
    "refined_audit_surfaces.py",
    "refined_audit.py",
    "refined_audit_job.py",
    "test_refined_audit.py",
}
EXPECTED = {
    "schema": "cells.betse_refined_response_audit_plan@1",
    "cpu_affinity": "0-3",
    "stage_timeout_seconds": {"audit": 300, "regression": 300},
    "total_timeout_seconds": 900,
    "max_artifact_bytes": 67108864,
    "max_worker_file_bytes": 16777216,
    "frozen_comparisons": 2494936,
    "required_comparisons": 2298936,
    "internal_comparisons": 1373032,
    "independent_surface_comparisons": 1121904,
    "surface_scopes": 132,
    "required_failed_comparisons": 0,
    "diagnostic_failed_comparisons": 4173,
    "previous_regression_tests": 231,
    "test_modules": [
        "response_audit/test_saved_response.py",
        "response_panel/test_refined_response.py",
        "response_panel/test_refined_response_check.py",
        "response_resume/test_trace_resume.py",
        "response_closeout/test_refined_audit.py",
    ],
    "capture_rerun": False,
    "original_packets_rewritten": False,
    "automatic_polling": False,
    "automatic_retry": False,
    "automatic_expansion": False,
    "native_convergence_qualified": False,
    "forcing_convergence_qualified": False,
    "biology_validated": False,
    "gpu_tested": False,
}
OLD_TESTS = {
    "runs/ref-003e1-response-audit-2026-09-13/audit-01/regression.xml": 70,
    "runs/ref-003e1-response-refined-preflight-2026-09-13/checks-01/regression.xml": 114,
    "reports/ref-003e1-trace-resume-checks-01.xml": 47,
}


def validate_plan(value):
    c.require(
        json.dumps(value, sort_keys=True, allow_nan=False) == json.dumps(EXPECTED, sort_keys=True),
        "Unregistered refined audit scope/resources",
    )


def expected_paths(r):
    names = {
        "registration.json",
        "sources.zip",
        "started.json",
        "runtime-resource-probe.json",
        "cells.json",
        "cells.log",
        "comparison.json",
        "comparison.log",
    }
    for index, row in enumerate(r["new_cells_rows"]):
        names |= {f"cells-started/{index:02d}.json", "cells/" + row["id"] + "/result.json"}
    return names


def verify_manifest(output, r):
    actual, expected = prior.audit.packet_hashes(output), expected_paths(r)
    capture = c.read(output / "capture.json")
    c.require(
        len(expected) == 52
        and set(actual) == expected | prior.audit.OPERATIONAL | {"capture.json"}
        and set(capture["files_sha256"]) == expected
        and all(actual[n] == h for n, h in capture["files_sha256"].items()),
        "Completed continuation manifest differs",
    )
    c.require(
        all((output / n).stat().st_size > 0 for n in expected if not n.endswith(".log")),
        "Empty completed continuation payload",
    )
    return capture


def authenticate():
    c.require(
        c.sha(prior.PRELAUNCH) == CAPTURE_PRELAUNCH_SHA
        and all(c.sha(SESSION / n) == h for n, h in ANCHORS.items()),
        "Completed response anchor changed",
    )
    r = c.read(SESSION / "registration.json")
    prior.validate_registration(r)
    prior.old_job.capsule(SESSION, r)
    verify_manifest(SESSION, r)
    return r


def sources():
    return c.read(SESSION / "registration.json")["sources"] | {
        "response_closeout/" + n: c.sha(HERE / n) for n in sorted(NEW_FILES)
    }


def preserve():
    authenticate()
    owned = {str((HERE / n).relative_to(c.ROOT)) for n in NEW_FILES}
    names = (
        set(files.worktree())
        | set(c.read(prior.PRESERVATION)["baseline_sha256"])
        | set(c.read(prior.PRELAUNCH)["files_sha256"])
        | {str(prior.PRELAUNCH.relative_to(c.ROOT))}
        | set(OLD_TESTS)
    )
    baseline = {n: c.sha(c.ROOT / n) for n in sorted(names - owned)}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_refined_response_audit_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "anchors": ANCHORS,
            "baseline_sha256": baseline,
            "capture_files_sha256": prior.audit.packet_hashes(SESSION),
            "resource_failure_files_sha256": prior.audit.packet_hashes(prior.FAILED),
        },
    )
    print(json.dumps({"status": "preserved", "baseline_files": len(baseline), "capture_files": 56}))


def preservation_check():
    authenticate()
    saved = c.read(PRESERVATION)
    c.require(
        saved["anchors"] == ANCHORS
        and saved["capture_files_sha256"] == prior.audit.packet_hashes(SESSION)
        and saved["resource_failure_files_sha256"] == prior.audit.packet_hashes(prior.FAILED),
        "Completed or resource-failed response changed",
    )
    changed = {
        n: {"before": h, "after": c.sha(c.ROOT / n)}
        for n, h in saved["baseline_sha256"].items()
        if c.sha(c.ROOT / n) != h
    }
    c.require(
        set(changed) <= prior.prior.legacy.edits.ALLOWED_EDITS, "Unexpected pre-existing edit"
    )
    return {
        "baseline_files": len(saved["baseline_sha256"]),
        "unchanged_baseline_files": len(saved["baseline_sha256"]) - len(changed),
        "changed_documents": changed,
        "capture_files_unchanged": 56,
        "resource_failure_files_unchanged": 241,
        "accepted_implementation_files_unchanged": 352,
        "production_modules_unchanged": 51,
    }


def test_evidence(path):
    counts, modules = receipts.test_counts(path)
    root = ET.parse(path).getroot()
    identities = [[v.get("classname"), v.get("name")] for v in root.iter("testcase")]
    c.require(
        len(identities) == len({tuple(v) for v in identities}) == counts["tests"],
        "Missing or duplicated regression identities",
    )
    return {
        "counts": counts,
        "modules": sorted(modules),
        "identities": sorted(identities),
        "seconds": sum(float(s.get("time", 0)) for s in root.iter("testsuite")),
    }


def resources(tests):
    old_seconds = sum(test_evidence(c.ROOT / n)["seconds"] for n in OLD_TESTS)
    new_seconds = test_evidence(tests)["seconds"]
    stages = {
        "audit": math.ceil(2 * c.read(SESSION / "comparison.json")["elapsed_seconds"] + 60),
        "regression": math.ceil(1.5 * (old_seconds + new_seconds) + 60),
    }
    size = 8 * (SESSION / "comparison.json").stat().st_size + 8 * 1024**2
    c.require(
        all(v < EXPECTED["stage_timeout_seconds"][k] for k, v in stages.items())
        and sum(stages.values()) + 90 < EXPECTED["total_timeout_seconds"]
        and size < EXPECTED["max_artifact_bytes"],
        "Refined audit resource estimate exceeds cap",
    )
    return {
        "basis": "saved comparison and 231 earlier tests plus new preflight, with allowances",
        "stage_seconds_with_allowances": stages,
        "estimated_artifact_bytes_with_allowances": size,
        "new_preflight_seconds": new_seconds,
        "peak_RAM_measured": False,
        "capture_copied": False,
    }


def prelaunch(tests, expected):
    validate_plan(c.read(PLAN))
    c.require(c.sha(FAILED_PREFLIGHT) == FAILED_PREFLIGHT_SHA, "Initial preflight failure changed")
    preserved = preservation_check()
    evidence = test_evidence(tests)
    c.require(
        evidence["counts"]["tests"] == expected
        and evidence["modules"] == ["validation.betse.response_closeout.test_refined_audit"],
        "Wrong refined audit preflight coverage",
    )
    identities = list(evidence["identities"])
    for n, count in OLD_TESTS.items():
        old = test_evidence(c.ROOT / n)
        c.require(old["counts"]["tests"] == count, "Prior regression count differs")
        identities += old["identities"]
    c.require(len({tuple(v) for v in identities}) == expected + 231, "Overlapping regression scope")
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
            timeout=20,
        ).strip()
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    frozen = {n: h for n, h in files.worktree().items() if n not in baseline}
    frozen[str(tests.relative_to(c.ROOT))] = c.sha(tests)
    frozen[str(FAILED_PREFLIGHT.relative_to(c.ROOT))] = FAILED_PREFLIGHT_SHA
    c.write(
        PRELAUNCH,
        {
            "schema": "cells.betse_refined_response_audit_prelaunch@1",
            "status": "pass",
            "created_utc": datetime.now(UTC).isoformat(),
            "plan": EXPECTED,
            "anchors": ANCHORS,
            "sources": sources(),
            "preservation_sha256": c.sha(PRESERVATION),
            "tests": evidence["counts"],
            "test_receipt": str(tests.relative_to(c.ROOT)),
            "test_receipt_sha256": c.sha(tests),
            "expected_regression_identities": sorted(identities),
            "files_sha256": frozen,
            "quality": quality,
            "resources": resources(tests),
            "full_numerical_audit_run": False,
            "capture_rerun": False,
            **preserved,
        },
    )
    print(
        json.dumps(
            {
                "status": "prelaunch_pass",
                "tests": evidence["counts"],
                "regression_tests": len(identities),
                "quality": quality,
                "resources": resources(tests),
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
