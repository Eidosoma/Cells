"""Audit-revision-2 provenance checks; no solver or scientific session is rerun."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts import audit_multispecies_reference as audit
from scripts.audit_preserved_multispecies_reference import extract_sources

SESSION = Path(__file__).resolve().parents[2] / "runs/num-006-2026-09-09/reference-01"


@pytest.fixture
def saved_session(tmp_path, monkeypatch):
    if not (SESSION / "verification.json").exists():
        pytest.skip("Optional immutable NUM-006 artifact fixture is not available")
    destination = tmp_path / "session"
    shutil.copytree(SESSION, destination)
    # Production packaging may advance; the reference auditor still requires
    # every original source byte. Preserve that check using authenticated sources.
    original_sources = tmp_path / "original_sources"
    extract_sources(original_sources)
    monkeypatch.setattr(audit, "ROOT", original_sources)
    return destination


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def rehash(receipt, root, name):
    receipt["files_sha256"][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()


def test_rehashed_but_unfrozen_tolerance_change_is_refused(saved_session):
    root = saved_session
    plan = load(root / "protocol.json")
    plan["trajectory_limits"]["voltage_V"] *= 100
    save(root / "protocol.json", plan)
    receipt, session = load(root / "verification.json"), load(root / "session.json")
    new_hash = hashlib.sha256((root / "protocol.json").read_bytes()).hexdigest()
    receipt["protocol_sha256"] = session["protocol_sha256"] = new_hash
    save(root / "session.json", session)
    rehash(receipt, root, "protocol.json")
    rehash(receipt, root, "session.json")
    save(root / "verification.json", receipt)
    with pytest.raises(ValueError, match="frozen source capsule"):
        audit.audit(root)


def test_rehashed_inconsistent_solver_settings_are_refused(saved_session):
    root = saved_session
    receipt = load(root / "verification.json")
    name = receipt["completed_cases"][0]
    relative = f"{name}/radau.json"
    stats = load(root / relative)
    stats["rtol"] = 1e-5
    save(root / relative, stats)
    receipt["cases"][name]["attempts"]["radau"] = stats
    rehash(receipt, root, relative)
    save(root / "verification.json", receipt)
    with pytest.raises(ValueError, match="Reference settings differ"):
        audit.audit(root)


def test_rehashed_candidate_step_claim_is_refused(saved_session):
    root = saved_session
    receipt = load(root / "verification.json")
    name = receipt["completed_cases"][0]
    relative = f"{name}/rk4_0.01.json"
    stats = load(root / relative)
    stats["dt_s"] = 0.005
    save(root / relative, stats)
    receipt["cases"][name]["attempts"]["rk4_0.01"] = stats
    rehash(receipt, root, relative)
    save(root / "verification.json", receipt)
    with pytest.raises(ValueError, match="Candidate settings/grid/call count"):
        audit.audit(root)


def test_ordinary_payload_corruption_is_refused(saved_session):
    root = saved_session
    payload = root / "mono_baseline_1s/radau.npz"
    with payload.open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(ValueError, match="Payload hash mismatch"):
        audit.audit(root)
