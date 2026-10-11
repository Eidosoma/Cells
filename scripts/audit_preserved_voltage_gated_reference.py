"""Run unchanged NUM-007 auditing under its authenticated 0.11.0 sources."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "reports/cells-0.11.0-source.tar.gz"
ARCHIVE_SHA = "59d4c371f57b5a758a1c6f03c77d3385b97eb079c2fc05cfaeb708e155acdda4"


def extract_sources(destination):
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Preserved 0.11.0 source capsule identity differs")
    with tarfile.open(ARCHIVE) as archive:
        archive.extractall(destination, filter="data")


def audit(path):
    with tempfile.TemporaryDirectory(prefix="cells-num007-audit-") as directory:
        extract_sources(directory)
        worker = subprocess.run(
            [
                sys.executable,
                str(Path(directory) / "scripts/audit_voltage_gated_reference.py"),
                str(Path(path).resolve()),
            ],
            cwd=directory,
            env=os.environ | {"PYTHONPATH": directory},
            text=True,
            capture_output=True,
            timeout=120,
            check=True,
        )
    return json.loads(worker.stdout) | {"preserved_source_sha256": ARCHIVE_SHA}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.session), indent=2, sort_keys=True, allow_nan=False))
