"""Unchanged NUM-008 audit under authenticated 0.12.0 sources and dependencies."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "reports/cells-0.12.0-source.tar.gz"
ARCHIVE_SHA = "432fa9ec599c056f145f5e97ec6007a5b94e631e08ce3995df832367985ef5c6"
DEPENDENCIES = {
    "reports/spec-007-design-check.json": (
        "f649f5b18eddea1ced4d87bf61a936498dae14898f4e77abb67e990c1ac56ca9"
    ),
    "runs/core-007-2026-09-10/release-audit.json": (
        "2a08a2487aafd13cb1e604063e9ff3b68bd5a75cc7c09fe4dea480f952b05085"
    ),
}


def extract_sources(destination):
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Preserved 0.12.0 source capsule identity differs")
    with tarfile.open(ARCHIVE) as archive:
        archive.extractall(destination, filter="data")


def audit(path):
    with tempfile.TemporaryDirectory(prefix="cells-num008-audit-") as directory:
        extract_sources(directory)
        for name, digest in DEPENDENCIES.items():
            source, destination = ROOT / name, Path(directory) / name
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Preserved dependency identity differs: {name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        worker = subprocess.run(
            [
                sys.executable,
                str(Path(directory) / "scripts/audit_physical_ionic_graph_reference.py"),
                str(Path(path).resolve()),
            ],
            cwd=directory,
            env=os.environ | {"PYTHONPATH": str(Path(directory) / "src")},
            text=True,
            capture_output=True,
            timeout=300,
            check=True,
        )
    return json.loads(worker.stdout) | {"preserved_source_sha256": ARCHIVE_SHA}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.session), indent=2, sort_keys=True, allow_nan=False))
