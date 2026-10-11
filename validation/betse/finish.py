"""Bind REF-003a results, tests and unchanged development sources after documentation."""

import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import contact as c

OUTPUT = c.ROOT / "reports/ref-003a-closeout.json"
SESSION = c.ROOT / "runs/ref-003a-2026-09-12/contact-01"
ALLOWED_DOCUMENT_EDITS = {
    "PROGRESS.md",
    "README.md",
    "docs/DECISIONS.md",
    "docs/SPATIAL_EXTRACELLULAR.md",
    "docs/BETSE_REFERENCE_PLAN.md",
    "docs/BETSE_CAPABILITY_ROADMAP.md",
    "reports/CORE010_ACCEPTANCE_V2.md",
    "reports/CORE010_CLOSEOUT_HANDOFF.md",
}


def finish():
    c.require(not OUTPUT.exists(), "Closeout already exists; do not overwrite")
    preserved = c.authenticate_cells()
    baseline = preserved["worktree_files_sha256"]
    c.require(all((c.ROOT / name).is_file() for name in baseline), "Pre-existing file missing")
    changed = {
        name: {"before": digest, "after": c.sha(c.ROOT / name)}
        for name, digest in baseline.items()
        if c.sha(c.ROOT / name) != digest
    }
    c.require(set(changed) <= ALLOWED_DOCUMENT_EDITS, "Unexpected pre-existing file edit")
    result = c.audit(SESSION)
    saved_audit = c.ROOT / "reports/ref-003a-audit-01.json"
    c.require(result == c.read(saved_audit), "Saved independent audit differs")
    tests = c.ROOT / "reports/ref-003a-checks-01.xml"
    suites = ET.parse(tests).getroot().findall("testsuite")
    counts = {
        key: sum(int(s.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    c.require(
        counts == {"tests": 52, "failures": 0, "errors": 0, "skipped": 0},
        "Adapter checks not complete",
    )
    quality = {}
    for name, arguments in (("lint", ["check"]), ("format", ["format", "--check"])):
        completed = subprocess.run(
            [str(c.ROOT / ".venv/bin/ruff"), *arguments, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        quality[name] = completed.stdout.strip()
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=c.ROOT,
        )
        .decode()
        .split("\0")
    )
    new = {name: c.sha(c.ROOT / name) for name in sorted(set(names) - set(baseline) - {""})}
    c.write(
        OUTPUT,
        {
            "schema": "cells.betse_passive_contact_closeout@1",
            "status": "pass",
            "finished_utc": datetime.now(UTC).isoformat(),
            "scope": (
                "Instantaneous passive-law source correspondence, "
                "not full-model or biological validation"
            ),
            "preservation_sha256": c.sha(c.PRESERVATION),
            "source_hashes": preserved["source_hashes"],
            "unchanged_accepted_implementation_files": len(
                preserved["implementation_files_sha256"]
            ),
            "baseline_files": len(baseline),
            "unchanged_baseline_files": len(baseline) - len(changed),
            "changed_baseline_files": changed,
            "new_files_sha256_before_closeout": new,
            "independent_audit": result,
            "independent_audit_sha256": c.sha(saved_audit),
            "tests": counts | {"junit_sha256": c.sha(tests)},
            "quality": quality,
            "core_regression_tests_previously_passed": 4190,
            "core_matrix_rerun": False,
            "stable_version": "0.14.0",
            "development_version": "0.15.0.dev0",
            "stable_promotion": False,
            "trajectory_run": False,
            "gpu_tested": False,
            "next_gate": (
                "REF-003b model, electrical-closure and initialization alignment before integration"
            ),
        },
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "unchanged_accepted_files": 352,
                "unchanged_baseline_files": len(baseline) - len(changed),
                "adapter_tests": 52,
            }
        )
    )


if __name__ == "__main__":
    finish()
