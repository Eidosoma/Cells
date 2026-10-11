"""Run the unchanged NUM-010 audit under the authenticated 0.14.0 source capsule."""

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
ARCHIVE = ROOT / "reports/cells-0.14.0-source.tar.gz"
ARCHIVE_SHA = "843f25671910f008a4c6c955c780e04dcbe66a1573abc96f66b85312e0708456"


def extract_sources(destination):
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Preserved 0.14.0 source capsule identity differs")
    with tarfile.open(ARCHIVE) as archive:
        archive.extractall(destination, filter="data")


def audit(path):
    with tempfile.TemporaryDirectory(prefix="cells-num010-audit-") as directory:
        extract_sources(directory)
        worker = subprocess.run(
            [
                sys.executable,
                str(Path(directory) / "scripts/audit_spatial_extracellular_reference.py"),
                str(Path(path).resolve()),
            ],
            cwd=directory,
            env=os.environ | {"PYTHONPATH": str(Path(directory) / "src")},
            text=True,
            capture_output=True,
            timeout=600,
            check=True,
        )
    return json.loads(worker.stdout) | {"preserved_source_sha256": ARCHIVE_SHA}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.session), indent=2, sort_keys=True, allow_nan=False))
