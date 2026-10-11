"""Run unchanged NUM-006 revision-2 auditing with its preserved packaging source.

The old audit intentionally rejects a different current pyproject.toml. Extract
the authenticated pre-edit capsule and execute there; never relax that check to
accommodate a new production version. No solver or checkpoint migration occurs.
"""

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
ARCHIVE = ROOT / "reports/cells-0.10.0-source.tar.gz"
ARCHIVE_SHA = "24a65b3bd478b76e230670785091b255f51d1427450e15c7b5dabc8a154f6536"


def extract_sources(destination):
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Preserved 0.10.0 source capsule identity differs")
    with tarfile.open(ARCHIVE) as archive:
        archive.extractall(destination, filter="data")


def audit(path):
    with tempfile.TemporaryDirectory(prefix="cells-num006-audit-") as directory:
        extract_sources(directory)
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(directory) / "scripts/audit_multispecies_reference.py"),
                str(Path(path).resolve()),
            ],
            cwd=directory,
            env=os.environ | {"PYTHONPATH": directory},
            text=True,
            capture_output=True,
            timeout=120,
            check=True,
        )
    return json.loads(completed.stdout) | {"preserved_source_sha256": ARCHIVE_SHA}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.session), indent=2, sort_keys=True, allow_nan=False))
