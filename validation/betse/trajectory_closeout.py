"""Preserve and close REF-003d v2 without another integration or production promotion."""

import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import cluster_closeout as previous
import contact as c
import trajectory_evidence as evidence
import trajectory_failure as prior
import trajectory_refinement_context as ctx

PRESERVATION = c.ROOT / "reports/ref-003d-closeout-preservation.json"
AUDIT = c.ROOT / "reports/ref-003d-v2-evidence-audit.json"
OUTPUT = c.ROOT / "reports/ref-003d-closeout.json"
TESTS = (
    c.ROOT / "reports/ref-003d-v2-closeout-existing-02.xml",
    c.ROOT / "reports/ref-003d-v2-closeout-new-02.xml",
)
NEW_TOOLS = {
    f"validation/betse/{name}.py"
    for name in ("trajectory_evidence", "trajectory_closeout", "test_saved_trajectory")
}


def authenticate():
    for name, digest in evidence.ANCHORS.items():
        c.require(c.sha(evidence.SESSION / name) == digest, "V2 evidence anchor changed")
    ctx.validate_registration(c.read(evidence.SESSION / "registration.json"))
    return c.authenticate_cells()


def preserve():
    accepted = authenticate()
    baseline = {n: h for n, h in previous.worktree().items() if n not in NEW_TOOLS}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_trajectory_closeout_preservation@1",
            "status": "pass",
            "created_utc": datetime.now(UTC).isoformat(),
            "baseline_sha256": baseline,
            "accepted_sources": accepted["implementation_files_sha256"],
            "v2_files_sha256": prior.files(evidence.SESSION),
            "v1_files_sha256": prior.files(prior.SESSION),
            "excluded_new_closeout_tools": sorted(NEW_TOOLS),
        },
    )
    print(json.dumps({"status": "preserved", "baseline_files": len(baseline)}))


def finish():
    c.require(not OUTPUT.exists(), "Closeout exists; do not overwrite")
    accepted = authenticate()
    saved = c.read(PRESERVATION)
    c.require(
        saved["accepted_sources"] == accepted["implementation_files_sha256"],
        "Accepted sources changed",
    )
    for version, path in (("v1", prior.SESSION), ("v2", evidence.SESSION)):
        c.require(prior.files(path) == saved[version + "_files_sha256"], "Retained packet changed")
    baseline = saved["baseline_sha256"]
    changes = {
        n: {"before": h, "after": c.sha(c.ROOT / n)}
        for n, h in baseline.items()
        if c.sha(c.ROOT / n) != h
    }
    c.require(set(changes) <= prior.ALLOWED_DOCUMENT_EDITS, "Unexpected existing file edit")
    audit = evidence.audit()
    c.require(audit == c.read(AUDIT), "Independent evidence audit receipt differs")
    suites = [suite for path in TESTS for suite in ET.parse(path).getroot().iter("testsuite")]
    counts = {
        k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")
    }
    cases = [case for suite in suites for case in suite.findall("testcase")]
    expected_modules = {
        "validation.betse." + Path(n).stem
        for n in c.read(evidence.SESSION / "registration.json")["sources"]
        if Path(n).name.startswith("test_")
    }
    expected_modules.add("validation.betse.test_saved_trajectory")
    c.require(
        counts["tests"] == len(cases) == 325
        and all(counts[k] == 0 for k in ("failures", "errors", "skipped"))
        and {case.get("classname") for case in cases} == expected_modules,
        "Incomplete adapter regression receipt",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
        ).strip()
    current = previous.worktree()
    result = {
        "schema": "cells.betse_trajectory_closeout@1",
        "status": "pass",
        "finished_utc": datetime.now(UTC).isoformat(),
        "scope": audit["scope"],
        "preservation_sha256": c.sha(PRESERVATION),
        "evidence_audit_sha256": c.sha(AUDIT),
        "independent_audit": audit,
        "baseline_files": len(baseline),
        "unchanged_baseline_files": len(baseline) - len(changes),
        "changed_documents": changes,
        "retained_v1_files": len(saved["v1_files_sha256"]),
        "retained_v2_files": len(saved["v2_files_sha256"]),
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": sum(
            n.startswith("src/") and n.endswith(".py")
            for n in accepted["implementation_files_sha256"]
        ),
        "new_files_sha256_before_closeout": {n: h for n, h in current.items() if n not in baseline},
        "tests": counts | {"junit_sha256": {str(p.relative_to(c.ROOT)): c.sha(p) for p in TESTS}},
        "quality": quality,
        "capture_rerun": False,
        "production_changed": False,
        "prior_production_matrix_tests": 4190,
        "production_matrix_rerun": False,
        "stable_version": "0.14.0",
        "development_version": "0.15.0.dev0",
        "stable_promotion": False,
        "trajectory_qualified": True,
        "original_v1_qualified": False,
        "one_cell_alignment_qualified": False,
        "biology_validated": False,
        "betse_family_parity": False,
        "gpu_tested": False,
        "next_step": (
            "Design a separately registered passive block/release event comparison; not launched"
        ),
        "driver_sha256": c.sha(Path(__file__)),
    }
    c.write(OUTPUT, result)
    print(
        json.dumps(
            {
                "status": "pass",
                "tests": counts["tests"],
                "accepted_sources_unchanged": result["accepted_implementation_files_unchanged"],
                "document_edits": len(changes),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preserve", "finish"))
    args = parser.parse_args()
    (preserve if args.action == "preserve" else finish)()
