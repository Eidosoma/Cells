"""Archive accepted 0.10.0 and the NUM-006 audit environment before CORE-006 edits.

New, non-overwriting artifacts only. The source capsule contains no checkpoint
migration: old snapshots must still run with their own source/runtime identity.
"""

import hashlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.io import _write_json, runtime_identity, source_hashes  # noqa: E402
from scripts.audit_multispecies_reference import audit  # noqa: E402

RELEASE = ROOT / "runs/core-005b-2026-09-08/release-audit.json"
RELEASE_SHA = "94d8ee4500f91fb6fb5506085c515944ad235e7d42318430d11d85e41b74da4e"
REFERENCE = ROOT / "runs/num-006-2026-09-09/reference-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preserve():
    destination = ROOT / "reports/cells-0.10.0-source.tar.gz"
    receipt_path = ROOT / "reports/core-006-preservation.json"
    if destination.exists() or receipt_path.exists():
        raise ValueError("Preservation output exists; it must not be overwritten")
    if sha(RELEASE) != RELEASE_SHA:
        raise ValueError("Accepted release identity differs")
    release = json.loads(RELEASE.read_text())
    sources, runtime = source_hashes(), runtime_identity()
    if sources != release["source_hashes"] or runtime != release["runtime"]:
        raise ValueError("Current production is not the accepted 0.10.0 release")
    reference = json.loads((REFERENCE / "verification.json").read_text())
    reference_audit = audit(REFERENCE)
    names = sorted(
        {f"src/cells/{name}" for name in sources}
        | set(reference["source_sha256"])
        | {"tests/unit/test_multispecies_artifact_audit.py", "requirements-reference.txt"}
    )
    hashes = {name: sha(ROOT / name) for name in names}
    with tarfile.open(destination, "x:gz") as archive:
        for name in names:
            archive.add(ROOT / name, arcname=name, recursive=False)
    with tarfile.open(destination) as archive:
        if archive.getnames() != names:
            raise ValueError("Archive inventory differs")
        for name, expected in hashes.items():
            if hashlib.sha256(archive.extractfile(name).read()).hexdigest() != expected:
                raise ValueError(f"Archived bytes differ: {name}")
    if sources != source_hashes() or runtime != runtime_identity():
        raise ValueError("Production changed during preservation")
    receipt = {
        "status": "pass",
        "scope": "pre-edit source preservation and NUM-006 revision-2 audit",
        "accepted_release_sha256": RELEASE_SHA,
        "runtime": runtime,
        "source_hashes": sources,
        "archive": str(destination.relative_to(ROOT)),
        "archive_sha256": sha(destination),
        "archive_files_sha256": hashes,
        "reference_receipt_sha256": sha(REFERENCE / "verification.json"),
        "reference_audit": reference_audit,
        "driver_sha256": sha(Path(__file__)),
    }
    _write_json(receipt_path, receipt)
    print(
        json.dumps(
            {
                "status": "pass",
                "archive_files": len(names),
                "production_files": len(sources),
                "archive_sha256": sha(destination),
            }
        )
    )


if __name__ == "__main__":
    preserve()
