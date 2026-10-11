"""One read-only evidence review and pre-integration source preservation.

Run in the D111 source context, before editing production. Historical receipts
are never rewritten, and a new development tree must not bypass authentication.
"""

import hashlib
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import process_job as job


def main():
    c = job.c
    source = c.ROOT / "runs/spec-010-pump-process-2026-09-16/qualification-01"
    output = c.ROOT / "runs/spec-010-family-2026-09-16/pre-integration-01"
    c.require(not output.exists(), "Preservation already exists")
    registered = job.authenticate(source)
    completed = c.read(source / "completion.json")
    c.require(
        c.sha(source / "completion.json")
        == "6c4ec593d78f9572ffde7e9045d8f785009d11ff5dca68f394ba229410ef7402"
        and completed["status"] == "process_qualification_pass_pending_review",
        "Wrong process completion",
    )
    for name, expected in completed["files_sha256"].items():
        c.require(c.sha(source / name) == expected, "Changed payload: " + name)
    result = c.read(source / "process-contact.json")
    c.require(
        result["status"] == "pass"
        and result["comparisons"] == len(result["rows"]) == 930
        and not result["warnings"],
        "Process contact did not pass",
    )
    suites = ET.parse(source / "regression.xml").getroot().findall("testsuite")
    c.require(
        sum(int(s.attrib["tests"]) for s in suites) == 348
        and all(
            int(s.attrib.get(k, 0)) == 0 for s in suites for k in ("errors", "failures", "skipped")
        ),
        "Regression did not pass",
    )
    names = set(
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=c.ROOT,
        )
        .decode()
        .split("\0")
    ) - {""}
    # Include ignored production files too, but not environments, upstream clones
    # or run payloads. Those have their own explicitly bound source capsules.
    names |= {str(p.relative_to(c.ROOT)) for p in (c.ROOT / "src/cells").rglob("*.py")}
    baseline = {n: c.sha(c.ROOT / n) for n in sorted(names) if (c.ROOT / n).is_file()}
    c.require(set(registered["sources_sha256"]) <= baseline.keys(), "Incomplete baseline")
    output.mkdir(parents=True)
    archive_path = output / "worktree.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in baseline:
            archive.write(c.ROOT / name, arcname=name)
    with zipfile.ZipFile(archive_path) as archive:
        c.require(set(archive.namelist()) == baseline.keys(), "Preservation membership")
        c.require(
            all(hashlib.sha256(archive.read(n)).hexdigest() == h for n, h in baseline.items()),
            "Preservation bytes",
        )
    receipt = {
        "schema": "cells.kinetic_process_closeout_and_preservation@1",
        "status": "process_qualification_reviewed_pass",
        "created_utc": datetime.now(UTC).isoformat(),
        "scope": "Receipt/source review, not a new independent mathematical audit or simulation",
        "qualification": str(source.relative_to(c.ROOT)),
        "qualification_files_sha256": {p.name: c.sha(p) for p in source.iterdir() if p.is_file()},
        "registered_sources": len(registered["sources_sha256"]),
        "contact_comparisons": 930,
        "regression_tests": 348,
        "worktree_files_sha256": baseline,
        "worktree_zip_sha256": c.sha(archive_path),
        "driver_sha256": c.sha(Path(__file__)),
        "production_family_accepted": False,
        "biology_validated": False,
        "gpu_tested": False,
        "stable_release_promoted": False,
    }
    c.write(output / "completion.json", receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "preserved_files": len(baseline),
                "receipt_sha256": c.sha(output / "completion.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
