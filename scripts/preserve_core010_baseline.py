"""Authenticate accepted 0.14.0 and NUM-010 before any CORE-010 production edit."""

import hashlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.io import _write_json, runtime_identity, source_hashes  # noqa: E402
from scripts.audit_finite_extracellular_build import audit as audit_build  # noqa: E402
from scripts.audit_spatial_extracellular_reference import audit as audit_reference  # noqa: E402
from scripts.spatial_extracellular_artifacts import SOURCE_FILES  # noqa: E402

RELEASE = ROOT / "runs/core-009-2026-09-10/release-audit.json"
RELEASE_SHA = "940c2289d15f2df6e04ca4a1abaece05e5a0ef7c0e4fedccc73af073d0b9133a"
REFERENCE = ROOT / "runs/num-010-2026-09-11/reference-01"
REFERENCE_SHA = "abf25d88ebd64bf2c922f189bdf0669ae100c46eef3101d0d8eda98f15a66046"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preserve():
    destination = ROOT / "reports/cells-0.14.0-source.tar.gz"
    receipt_path = ROOT / "reports/core-010-preservation.json"
    if destination.exists() or receipt_path.exists():
        raise ValueError("Preservation output exists; it must not be overwritten")
    if sha(RELEASE) != RELEASE_SHA or sha(REFERENCE / "verification.json") != REFERENCE_SHA:
        raise ValueError("Accepted release or spatial reference identity differs")
    release = json.loads(RELEASE.read_text())
    sources, runtime = source_hashes(), runtime_identity()
    if sources != release["source_hashes"] or runtime != release["runtime"]:
        raise ValueError("Current production is not accepted 0.14.0")
    print("Authenticate accepted production", flush=True)
    build_audit = audit_build(ROOT / "runs/core-009-2026-09-10/acceptance-02")
    print("Authenticate and replay NUM-010 without ODE integration", flush=True)
    reference_audit = audit_reference(REFERENCE)
    names = sorted(
        {
            str(p.relative_to(ROOT))
            for folder in ("src", "tests", "scripts", "configs", "docs")
            for p in (ROOT / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".json", ".md")
        }
        | set(SOURCE_FILES)
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
        "scope": "Pre-edit accepted 0.14.0 and NUM-010 source/evidence preservation",
        "accepted_release_sha256": RELEASE_SHA,
        "accepted_reference_sha256": REFERENCE_SHA,
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
        ),
        flush=True,
    )


if __name__ == "__main__":
    preserve()
