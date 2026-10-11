"""Close the audited REF-003c slice without changing or rerunning either simulator."""

import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import cluster_alignment as cluster
import cluster_evidence as evidence
import contact as c
import geometry_probe as geometry

PRESERVATION = c.ROOT / "reports/ref-003c-preservation.json"
OUTPUT = c.ROOT / "reports/ref-003c-closeout.json"
AUDIT = c.ROOT / "reports/ref-003c-evidence-audit.json"
GEOMETRY_AUDIT = c.ROOT / "reports/ref-003c-geometry-audit.json"
TESTS = c.ROOT / "reports/ref-003c-checks-02.xml"
ALLOWED_EDITS = {
    "PROGRESS.md",
    "README.md",
    "docs/BETSE_CAPABILITY_ROADMAP.md",
    "docs/BETSE_INITIALIZATION_ALIGNMENT.md",
    "docs/BETSE_REFERENCE_PLAN.md",
    "docs/DECISIONS.md",
    "reports/REF003C_CLUSTER_ALIGNMENT.md",
    "validation/betse/README.md",
}


def worktree():
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=c.ROOT,
        )
        .decode()
        .split("\0")
    )
    return {name: c.sha(c.ROOT / name) for name in sorted(set(names) - {""})}


def changed_files(baseline):
    changed = {
        name: {"before": digest, "after": c.sha(c.ROOT / name)}
        for name, digest in baseline.items()
        if c.sha(c.ROOT / name) != digest
    }
    c.require(set(changed) <= ALLOWED_EDITS, "Unexpected existing source/evidence edit")
    return changed


def authenticate():
    c.require(
        c.sha(evidence.SESSION / "verification.json") == evidence.CAPTURE_SHA,
        "Original seven-cell capture changed",
    )
    c.require(
        c.sha(cluster.GEOMETRY_PROBE / "completion.json") == evidence.GEOMETRY_SHA,
        "Original geometry diagnostic changed",
    )
    previous = geometry.authenticate()
    development = c.authenticate_cells()
    return previous, development


def preserve():
    previous, development = authenticate()
    prior_baseline = c.read(cluster.GEOMETRY_PROBE / "registration.json")["baseline_sha256"]
    changed_files(prior_baseline)
    result = {
        "schema": "cells.betse_cluster_closeout_preservation@1",
        "status": "pass",
        "created_utc": datetime.now(UTC).isoformat(),
        "capture_verification_sha256": evidence.CAPTURE_SHA,
        "geometry_completion_sha256": evidence.GEOMETRY_SHA,
        "prior_handoff_sha256": c.sha(geometry.PRIOR_HANDOFF),
        "prior_retained_attempts": previous["retained_attempts"],
        "accepted_sources": development["implementation_files_sha256"],
        "pre_probe_baseline_sha256": prior_baseline,
        "closeout_baseline_sha256": worktree(),
    }
    c.write(PRESERVATION, result)
    print(json.dumps({"status": "preserved", "files": len(result["closeout_baseline_sha256"])}))


def finish():
    c.require(not OUTPUT.exists(), "Closeout exists; do not overwrite")
    previous, development = authenticate()
    preserved = c.read(PRESERVATION)
    c.require(
        preserved["prior_retained_attempts"] == previous["retained_attempts"], "Old attempts differ"
    )
    changes = changed_files(preserved["closeout_baseline_sha256"])
    pre_probe_changes = changed_files(preserved["pre_probe_baseline_sha256"])
    audit = evidence.audit(evidence.SESSION)
    c.require(audit == c.read(AUDIT), "Saved evidence audit differs")
    c.require(
        evidence.geometry_audit(cluster.GEOMETRY_PROBE) == c.read(GEOMETRY_AUDIT),
        "Saved geometry diagnostic differs",
    )
    c.require(
        cluster.audit(evidence.SESSION) == c.read(c.ROOT / "reports/ref-003c-audit-01.json"),
        "Frozen arithmetic replay differs",
    )
    suites = ET.parse(TESTS).getroot().findall("testsuite")
    counts = {
        key: sum(int(s.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    c.require(
        counts == {"tests": 171, "failures": 0, "errors": 0, "skipped": 0}, "Tests incomplete"
    )
    modules = {case.get("classname") for suite in suites for case in suite.findall("testcase")}
    c.require(
        modules
        == {
            "validation.betse." + name
            for name in (
                "test_contact",
                "test_saved_contact",
                "test_alignment",
                "test_preparation",
                "test_cluster",
                "test_saved_cluster",
            )
        },
        "Test source coverage differs",
    )
    quality = {}
    for name, arguments in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *arguments, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
        ).strip()
    current = worktree()
    result = {
        "schema": "cells.betse_cluster_closeout@1",
        "status": "pass",
        "scope": "Seven-cell initialization, instantaneous RHS and prescribed updates only",
        "finished_utc": datetime.now(UTC).isoformat(),
        "preservation_sha256": c.sha(PRESERVATION),
        "independent_audit": audit,
        "evidence_audit_sha256": c.sha(AUDIT),
        "geometry_audit_sha256": c.sha(GEOMETRY_AUDIT),
        "baseline_files": len(preserved["closeout_baseline_sha256"]),
        "unchanged_baseline_files": len(preserved["closeout_baseline_sha256"]) - len(changes),
        "changed_baseline_files": changes,
        "pre_probe_baseline_files": len(preserved["pre_probe_baseline_sha256"]),
        "pre_probe_unchanged_files": len(preserved["pre_probe_baseline_sha256"])
        - len(pre_probe_changes),
        "pre_probe_changed_files": pre_probe_changes,
        "accepted_implementation_files_unchanged": len(development["implementation_files_sha256"]),
        "production_modules_unchanged": sum(
            name.startswith("src/") and name.endswith(".py")
            for name in development["implementation_files_sha256"]
        ),
        "new_files_sha256_before_closeout": {
            name: digest
            for name, digest in current.items()
            if name not in preserved["closeout_baseline_sha256"]
        },
        "tests": counts | {"junit_sha256": c.sha(TESTS)},
        "quality": quality,
        "capture_rerun": False,
        "prior_production_matrix_tests": 4190,
        "production_matrix_rerun": False,
        "production_changed": False,
        "stable_version": "0.14.0",
        "development_version": "0.15.0.dev0",
        "stable_promotion": False,
        "one_cell_alignment_qualified": False,
        "trajectory_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
        "next_step": (
            "REF-003d short trajectory adapter/preflight and prospective registration; not launched"
        ),
        "driver_sha256": c.sha(Path(__file__)),
    }
    c.write(OUTPUT, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "tests": counts["tests"],
                "accepted_sources_unchanged": result["accepted_implementation_files_unchanged"],
                "unchanged_old_files": result["unchanged_baseline_files"],
                "document_edits": len(changes),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preserve", "finish"))
    args = parser.parse_args()
    (preserve if args.action == "preserve" else finish)()
