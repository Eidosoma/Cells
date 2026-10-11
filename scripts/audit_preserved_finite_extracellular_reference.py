"""Unchanged NUM-009 v2 audit under authenticated 0.13.0 sources and dependencies."""

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
ARCHIVE = ROOT / "reports/cells-0.13.0-source.tar.gz"
ARCHIVE_SHA = "73b152cfbeb016c9d842753fda21620f53fe8449a5fceb01f6cd6bac30dd9a15"
DEPENDENCIES = {
    "runs/num-009-2026-09-10/reference-01/failure.json": (
        "7dd501991ab3c61144d3f8862f91a8b76c146619e5c554b2b9fd46a5c87f3e67"
    ),
    "reports/spec-008-design-check-v2.json": (
        "ebb0e660dd5c1f980968d631f6539441fed94e4e9ec995aba26401510cf4e44b"
    ),
    "runs/core-008-2026-09-10/release-audit.json": (
        "e03a211726888d3962825db544bba6742aa09603031d68ebbbc4745542393f08"
    ),
}


def extract_sources(destination):
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Preserved 0.13.0 source capsule identity differs")
    with tarfile.open(ARCHIVE) as archive:
        archive.extractall(destination, filter="data")


def audit(path):
    with tempfile.TemporaryDirectory(prefix="cells-num009-audit-") as directory:
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
                str(Path(directory) / "scripts/audit_finite_extracellular_reference_v2.py"),
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
