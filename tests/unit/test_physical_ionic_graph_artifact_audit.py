"""NUM-008 immutable saved-evidence corruption tests; mutate temporary copies."""

import json
import shutil
from pathlib import Path

import pytest

from scripts import audit_physical_ionic_graph_reference as audit

SESSION = Path(__file__).resolve().parents[2] / "runs/num-008-2026-09-10/reference-01"


@pytest.fixture
def saved(tmp_path):
    if not (SESSION / "verification.json").is_file():
        pytest.skip("Optional immutable NUM-008 reference session is unavailable")
    destination = tmp_path / "session"
    shutil.copytree(SESSION, destination)
    return destination


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def rehash(root, receipt, *names):
    for name in names:
        receipt["files_sha256"][name] = audit.sha(root / name)
    receipt["artifact_bytes_before_receipt"] = sum(
        (root / n).stat().st_size for n in receipt["files_sha256"]
    )
    write(root / "verification.json", receipt)


def test_safe_member_refuses_escape_and_symlink(tmp_path):
    payload = tmp_path / "payload"
    payload.write_text("data")
    alias = tmp_path / "alias"
    alias.symlink_to(payload)
    for path in ("../payload", str(payload), "alias"):
        with pytest.raises(ValueError):
            audit.safe_member(tmp_path, path)
