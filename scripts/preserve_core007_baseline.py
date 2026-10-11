"""Authenticate and preserve accepted 0.11.0 before CORE-007 production edits."""

import hashlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.io import _write_json, runtime_identity, source_hashes  # noqa: E402
from scripts.audit_multispecies_build import audit as audit_build  # noqa: E402
from scripts.audit_voltage_gated_reference import audit as audit_reference  # noqa: E402

RELEASE = ROOT / "runs/core-006-2026-09-09/release-audit.json"
RELEASE_SHA = "ec084d0f626fbb3793714bbb7ea346688d1f1244078869507396a57aec1f5005"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preserve():
    destination = ROOT / "reports/cells-0.11.0-source.tar.gz"
    receipt_path = ROOT / "reports/core-007-preservation.json"
    if destination.exists() or receipt_path.exists():
        raise ValueError("Preservation output exists; it must not be overwritten")
    if sha(RELEASE) != RELEASE_SHA:
        raise ValueError("Accepted release identity differs")
    release = json.loads(RELEASE.read_text())
    sources, runtime = source_hashes(), runtime_identity()
    if sources != release["source_hashes"] or runtime != release["runtime"]:
        raise ValueError("Current production is not the accepted 0.11.0 release")
    reference_audit = audit_reference(ROOT / "runs/num-007-2026-09-09/reference-01")
    build_audit = audit_build(ROOT / "runs/core-006-2026-09-09/acceptance-02")
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
