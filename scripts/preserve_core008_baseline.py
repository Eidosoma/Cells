"""Authenticate and preserve accepted 0.12.0 before CORE-008 production edits."""

import hashlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.io import _write_json, runtime_identity, source_hashes  # noqa: E402
from scripts.audit_physical_ionic_graph_reference import audit as audit_reference  # noqa: E402
from scripts.audit_voltage_gated_build import audit as audit_build  # noqa: E402

RELEASE = ROOT / "runs/core-007-2026-09-10/release-audit.json"
RELEASE_SHA = "2a08a2487aafd13cb1e604063e9ff3b68bd5a75cc7c09fe4dea480f952b05085"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preserve():
    destination = ROOT / "reports/cells-0.12.0-source.tar.gz"
    receipt_path = ROOT / "reports/core-008-preservation.json"
    if destination.exists() or receipt_path.exists():
        raise ValueError("Preservation output exists; it must not be overwritten")
    if sha(RELEASE) != RELEASE_SHA:
        raise ValueError("Accepted release identity differs")
    release = json.loads(RELEASE.read_text())
    sources, runtime = source_hashes(), runtime_identity()
    if sources != release["source_hashes"] or runtime != release["runtime"]:
        raise ValueError("Current production is not the accepted 0.12.0 release")
    reference_audit = audit_reference(ROOT / "runs/num-008-2026-09-10/reference-01")
    build_audit = audit_build(ROOT / "runs/core-007-2026-09-10/acceptance-03")
    names = sorted(
        {
            str(p.relative_to(ROOT))
            for folder in ("src", "tests", "scripts", "configs", "docs")
            for p in (ROOT / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".json", ".md")
        }
        | {"pyproject.toml", "requirements-lock.txt", "requirements-reference.txt"}
    )
    hashes = {name: sha(ROOT / name) for name in names}
    with tarfile.open(destination, "x:gz") as archive:
        for name in names:
            archive.add(ROOT / name, arcname=name, recursive=False)
    with tarfile.open(destination) as archive:
        assert archive.getnames() == names
        for name, expected in hashes.items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected
    assert sources == source_hashes() and runtime == runtime_identity()
    assert hashes == {name: sha(ROOT / name) for name in names}
    receipt = {
        "status": "pass",
        "scope": "pre-edit accepted source and evidence preservation",
        "accepted_release_sha256": RELEASE_SHA,
        "runtime": runtime,
        "source_hashes": sources,
        "archive": str(destination.relative_to(ROOT)),
        "archive_sha256": sha(destination),
        "archive_files_sha256": hashes,
        "reference_audit": reference_audit,
        "build_audit": build_audit,
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
