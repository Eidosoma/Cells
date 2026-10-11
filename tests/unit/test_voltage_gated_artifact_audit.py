"""Saved NUM-007 corruption/provenance tests; mutate temporary copies only."""

import json
import shutil
from pathlib import Path

import pytest

from scripts import audit_voltage_gated_reference as audit

SESSION = Path(__file__).resolve().parents[2] / "runs/num-007-2026-09-09/reference-01"


@pytest.fixture
def saved(tmp_path):
    if not (SESSION / "verification.json").exists():
        pytest.skip("Optional immutable NUM-007 session is unavailable")
    destination = tmp_path / "session"
    shutil.copytree(SESSION, destination)
    return destination


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def rehash(root, receipt, relative):
    receipt["files_sha256"][relative] = audit.sha((root / relative).read_bytes())
    receipt["artifact_bytes_before_receipt"] = sum(
        (root / name).stat().st_size for name in receipt["files_sha256"]
    )


def test_corrupted_payload_refused(saved):
    path = saved / "mono_baseline/radau.npz"
    with path.open("ab") as handle:
        handle.write(b"corrupted")
    with pytest.raises(ValueError, match="Payload hash mismatch"):
        audit.audit(saved)


def test_rehashed_tolerance_change_refused(saved):
    plan = audit.load(saved / "protocol.json")
    plan["trajectory_limits"]["gate"] = 1
    write(saved / "protocol.json", plan)
    receipt, session = audit.load(saved / "verification.json"), audit.load(saved / "session.json")
    receipt["protocol_sha256"] = session["protocol_sha256"] = audit.sha(
        (saved / "protocol.json").read_bytes()
    )
    write(saved / "session.json", session)
    for name in ("protocol.json", "session.json"):
        rehash(saved, receipt, name)
    write(saved / "verification.json", receipt)
    with pytest.raises(ValueError, match="Frozen protocol"):
        audit.audit(saved)


@pytest.mark.parametrize(
    ("attempt", "field", "value"), [("radau", "rtol", 1e-5), ("rk4_0.001", "dt_s", 0.01)]
)
def test_rehashed_solver_setting_refused(saved, attempt, field, value):
    receipt = audit.load(saved / "verification.json")
    relative = f"mono_baseline/{attempt}.json"
    stats = audit.load(saved / relative)
    stats[field] = value
    write(saved / relative, stats)
    receipt["cases"]["mono_baseline"]["attempts"][attempt] = stats
    rehash(saved, receipt, relative)
    write(saved / "verification.json", receipt)
    with pytest.raises(ValueError, match="settings differ"):
        audit.audit(saved)


def test_rehashed_preparation_change_refused(saved):
    cases, receipt = audit.load(saved / "cases.json"), audit.load(saved / "verification.json")
    cases[0]["channel"]["initial_gate"]["m"] = 0.1
    write(saved / "cases.json", cases)
    rehash(saved, receipt, "cases.json")
    write(saved / "verification.json", receipt)
    with pytest.raises(ValueError, match="frozen preparation"):
        audit.audit(saved)


def test_rehashed_hidden_gate_history_change_refused(saved):
    receipt = audit.load(saved / "verification.json")
    receipt["cases"]["mono_baseline"]["final_gate"][0] = 0.5
    write(saved / "verification.json", receipt)
    with pytest.raises(ValueError, match="Final summary"):
        audit.audit(saved)


def test_dropped_source_inventory_is_refused(saved):
    receipt, session = audit.load(saved / "verification.json"), audit.load(saved / "session.json")
    name = "tests/reference_voltage_gated_dynamics.py"
    del receipt["source_sha256"][name]
    del session["source_sha256"][name]
    write(saved / "session.json", session)
    rehash(saved, receipt, "session.json")
    write(saved / "verification.json", receipt)
    with pytest.raises(ValueError, match="Source inventory"):
        audit.audit(saved)
