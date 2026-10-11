"""Authenticate existing CORE-010 evidence before the offline BETSE adapter work."""

import hashlib
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "runs/core-010-2026-09-11/acceptance-02"
CLOSEOUT = ROOT / "reports/core-010-v2-closeout.json"
CLOSEOUT_SHA = "7da291119b8386b6b14cb476513c8af035c4bcedeb27bb898b382df9fc371ad6"
OUTPUT = ROOT / "reports/ref-003a-preservation.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def preserve():
    if OUTPUT.exists():
        raise ValueError("Preservation output exists; do not overwrite")
    if sha(CLOSEOUT) != CLOSEOUT_SHA:
        raise ValueError("Development closeout identity differs")
    closed = read(CLOSEOUT)
    receipt = read(SESSION / "verification.json")
    audit = ROOT / "reports/core-010-v2-full-audit.json"
    matrix = ROOT / "reports/core-010-regression-03/verification.json"
    if not (
        closed["status"]
        == receipt["status"]
        == read(audit)["status"]
        == read(matrix)["status"]
        == "pass"
        and sha(audit) == closed["independent_audit_sha256"]
        and sha(matrix) == closed["regression"]["verification_sha256"]
        and sha(SESSION / "verification.json") == closed["acceptance"]["verification_sha256"]
        and not (SESSION / "failure.json").exists()
    ):
        raise ValueError("Passing capture/audit/matrix/closeout are not consistently bound")
    expected_files = receipt["files_sha256"]
    actual_files = {str(p.relative_to(SESSION)) for p in SESSION.rglob("*") if p.is_file()} - {
        "verification.json"
    }
    if actual_files != set(expected_files):
        raise ValueError("Accepted capture payload membership differs")
    for name, digest in expected_files.items():
        if sha(SESSION / name) != digest:
            raise ValueError(f"Accepted payload differs: {name}")
    sources = receipt["implementation_files_sha256"]
    for name, digest in sources.items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Accepted implementation differs: {name}")
    capsule = SESSION / "implementation_sources.zip"
    with zipfile.ZipFile(capsule) as archive:
        if len(archive.namelist()) != len(sources) or set(archive.namelist()) != set(sources):
            raise ValueError("Accepted capsule membership differs")
        for name, digest in sources.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError(f"Accepted capsule member differs: {name}")
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    baseline = {name: sha(ROOT / name) for name in sorted(set(names) - {""})}
    result = {
        "schema": "cells.betse_contact_preservation@1",
        "status": "pass",
        "created_utc": datetime.now(UTC).isoformat(),
        "scope": "Byte authentication of already audited development evidence; no new simulation",
        "closeout_sha256": CLOSEOUT_SHA,
        "capture_verification_sha256": sha(SESSION / "verification.json"),
        "independent_audit_sha256": sha(audit),
        "matrix_sha256": sha(matrix),
        "regression_tests": closed["regression"]["total_tests"],
        "payload_files_authenticated": len(expected_files),
        "implementation_files_sha256": sources,
        "source_hashes": closed["source_hashes"],
        "runtime": closed["runtime"],
        "preserved_capsule": str(capsule.relative_to(ROOT)),
        "preserved_capsule_sha256": sha(capsule),
        "worktree_files_sha256": baseline,
        "driver_sha256": sha(Path(__file__)),
        "stable_release": "0.14.0",
        "development_release": "0.15.0.dev0",
    }
    with OUTPUT.open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                "status": "pass",
                "accepted_payloads": len(expected_files),
                "captured_sources": len(sources),
                "baseline_files": len(baseline),
            }
        )
    )


if __name__ == "__main__":
    preserve()
