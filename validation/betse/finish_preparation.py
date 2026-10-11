"""Record a rejected preparation and preserved sources, without claiming alignment."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import alignment as a
import contact as c
import preparation as p

OUTPUT = c.ROOT / "reports/ref-003b1-closeout.json"
SESSION = c.ROOT / "runs/ref-003b1-2026-09-12/alignment-05"
ALLOWED_EDITS = {
    "PROGRESS.md",
    "README.md",
    "docs/DECISIONS.md",
    "docs/BETSE_REFERENCE_PLAN.md",
    "docs/BETSE_CAPABILITY_ROADMAP.md",
    "validation/betse/README.md",
}


def finish():
    c.require(not OUTPUT.exists(), "Handoff already exists; do not overwrite")
    preserved = a.authenticate()
    baseline = preserved["baseline_sha256"]
    changed = {
        name: {"before": digest, "after": c.sha(c.ROOT / name)}
        for name, digest in baseline.items()
        if c.sha(c.ROOT / name) != digest
    }
    c.require(set(changed) <= ALLOWED_EDITS, "Unexpected pre-existing file edit")
    diagnostic = p.audit(SESSION)
    audit_path = c.ROOT / "reports/ref-003b1-preparation-audit.json"
    c.require(diagnostic == c.read(audit_path), "Saved diagnostic differs")
    tests_path = c.ROOT / "reports/ref-003b1-checks-02.xml"
    suites = ET.parse(tests_path).getroot().findall("testsuite")
    counts = {
        key: sum(int(s.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    c.require(
        counts == {"tests": 103, "failures": 0, "errors": 0, "skipped": 0},
        "Incomplete adapter tests",
    )
    attempts = {}
    for directory in sorted(SESSION.parent.glob("alignment-*")):
        c.require(not (directory / "verification.json").exists(), "Unexpected acceptance receipt")
        registration = c.read(directory / "registration.json")
        protocol = registration["protocol"]
        c.require(
            protocol["tolerances"] == c.read(a.PROTOCOL)["tolerances"],
            "Scientific tolerances changed",
        )
        if directory != SESSION:
            expected_protocol = dict(c.read(a.PROTOCOL))
            expected_protocol.pop("revision")
            expected_protocol.pop("amendment")
            expected_protocol["yaml_overrides"] = [
                entry
                for entry in expected_protocol["yaml_overrides"]
                if entry[0] != ["general network", "implement network"]
            ]
            c.require(protocol == expected_protocol, "Unexpected prior protocol amendment")
        with zipfile.ZipFile(directory / "adapter_sources.zip") as archive:
            c.require(
                set(archive.namelist()) == set(registration["source_sha256"]),
                "Old capsule coverage differs",
            )
            for name, digest in registration["source_sha256"].items():
                c.require(
                    hashlib.sha256(archive.read(name)).hexdigest() == digest,
                    "Old capsule bytes differ",
                )
        failure = c.read(directory / "failure.json")
        c.require(failure["status"] == "failed_not_qualified", "Wrong attempt status")
        attempts[directory.name] = {
            "status": failure["status"],
            "seconds": failure["seconds"],
            "files_sha256": {
                str(path.relative_to(directory)): c.sha(path)
                for path in directory.rglob("*")
                if path.is_file()
            },
        }
    c.require(
        set(attempts) == {f"alignment-{i:02d}" for i in range(1, 6)}, "Attempt coverage differs"
    )
    quality = {}
    for name, arguments in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *arguments, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
        ).strip()
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=c.ROOT,
        )
        .decode()
        .split("\0")
    )
    new_files = {name: c.sha(c.ROOT / name) for name in sorted(set(names) - set(baseline) - {""})}
    result = {
        "schema": "cells.betse_preparation_handoff@1",
        "status": "recorded_not_qualified",
        "finished_utc": datetime.now(UTC).isoformat(),
        "alignment_qualified": False,
        "scope": (
            "Native preparation rejected at one-cell guard; diagnostic and software tests only"
        ),
        "preservation_sha256": c.sha(a.PRESERVATION),
        "baseline_files": len(baseline),
        "unchanged_baseline_files": len(baseline) - len(changed),
        "changed_baseline_files": changed,
        "unchanged_accepted_implementation_files": len(preserved["accepted_sources"]),
        "prior_component_contact": c.audit(a.PRIOR),
        "diagnostic_audit_sha256": c.sha(audit_path),
        "retained_attempts": attempts,
        "new_files_sha256_before_handoff": new_files,
        "tests": counts | {"junit_sha256": c.sha(tests_path)},
        "quality": quality,
        "production_changed": False,
        "core_regression_tests_previously_passed": 4190,
        "core_matrix_rerun": False,
        "stable_version": "0.14.0",
        "development_version": "0.15.0.dev0",
        "stable_promotion": False,
        "trajectory_run": False,
        "gpu_tested": False,
        "next_step": (
            "Native one-cell geometry feasibility; "
            "explicitly specify seven-cell alternative if unavailable"
        ),
        "driver_sha256": c.sha(Path(__file__)),
    }
    c.write(OUTPUT, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "unchanged_old_files": result["unchanged_baseline_files"],
                "accepted_sources_unchanged": result["unchanged_accepted_implementation_files"],
                "tests": counts["tests"],
                "retained_attempts": len(attempts),
            }
        )
    )


if __name__ == "__main__":
    finish()
