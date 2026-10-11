"""NUM-009 immutable saved-evidence corruption tests; mutate temporary copies."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from scripts import audit_finite_extracellular_reference as audit

SESSION = Path(__file__).resolve().parents[2] / "runs/num-009-2026-09-10/reference-01"


@pytest.fixture
def saved(tmp_path):
    if not (SESSION / "verification.json").is_file():
        pytest.skip("Optional immutable NUM-009 reference session is unavailable")
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


def test_corrupt_payload_is_refused(saved):
    with (saved / "single_mono/radau.npz").open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(ValueError, match="Payload hash"):
        audit.audit(saved)


def test_rehashed_protocol_is_refused(saved):
    plan = audit.load(saved / "protocol.json")
    plan["trajectory_limits"]["junction_gate"] = 1.0
    write(saved / "protocol.json", plan)
    receipt, session = audit.load(saved / "verification.json"), audit.load(saved / "session.json")
    receipt["protocol_sha256"] = session["protocol_sha256"] = audit.sha(saved / "protocol.json")
    write(saved / "session.json", session)
    rehash(saved, receipt, "protocol.json", "session.json")
    with pytest.raises(ValueError, match="Frozen protocol"):
        audit.audit(saved)


@pytest.mark.parametrize("field", ["volume_pL", "fixed_charge_equivalent_fmol"])
def test_rehashed_cell_preparation_is_refused(saved, field):
    cases, receipt = audit.load(saved / "cases.json"), audit.load(saved / "verification.json")
    cases[0]["world"]["cells"][0][field] *= 1.01
    write(saved / "cases.json", cases)
    rehash(saved, receipt, "cases.json")
    with pytest.raises(ValueError, match="frozen inputs"):
        audit.audit(saved)


@pytest.mark.parametrize(
    ("attempt", "field", "value"), [("radau", "rtol", 1e-5), ("rk4_0.001", "dt_s", 0.01)]
)
def test_rehashed_method_setting_is_refused(saved, attempt, field, value):
    receipt = audit.load(saved / "verification.json")
    relative = f"single_mono/{attempt}.json"
    stats = audit.load(saved / relative)
    stats[field] = value
    receipt["cases"]["single_mono"]["attempts"][attempt] = stats
    write(saved / relative, stats)
    rehash(saved, receipt, relative)
    with pytest.raises(ValueError, match="settings differ"):
        audit.audit(saved)


def test_rehashed_dense_observation_is_refused(saved):
    receipt = audit.load(saved / "verification.json")
    relative = "single_mono/radau.npz"
    arrays = audit.read_arrays(saved / relative, 536870912)
    arrays["sample_state"][10, -1] += 1e-6
    np.savez_compressed(saved / relative, **arrays)
    rehash(saved, receipt, relative)
    with pytest.raises(ValueError, match="Dense replay"):
        audit.audit(saved)


def test_dropped_source_is_refused(saved):
    receipt, session = audit.load(saved / "verification.json"), audit.load(saved / "session.json")
    name = "tests/reference_finite_extracellular_dynamics.py"
    del receipt["source_sha256"][name]
    del session["source_sha256"][name]
    write(saved / "session.json", session)
    rehash(saved, receipt, "session.json")
    with pytest.raises(ValueError, match="Source inventory"):
        audit.audit(saved)


def test_hidden_history_summary_is_refused(saved):
    receipt = audit.load(saved / "verification.json")
    receipt["cases"]["single_mono"]["final_state"]["channel_transferred"][0] += 0.01
    write(saved / "verification.json", receipt)
    with pytest.raises(ValueError, match="Final summary"):
        audit.audit(saved)


def test_outside_initial_inventory_is_bound(saved):
    cases, receipt = audit.load(saved / "cases.json"), audit.load(saved / "verification.json")
    cases[0]["world"]["extracellular"]["initial_amount_fmol"][0] *= 1.01
    write(saved / "cases.json", cases)
    rehash(saved, receipt, "cases.json")
    with pytest.raises(ValueError, match="frozen inputs"):
        audit.audit(saved)


def test_depletion_claim_is_recomputed(saved):
    receipt = audit.load(saved / "verification.json")
    receipt["depletion_witness"]["fractional_drop"] = 1.0
    write(saved / "verification.json", receipt)
    with pytest.raises(ValueError, match="Depletion witness"):
        audit.audit(saved)


def test_coordinate_contract_is_bound(saved):
    receipt, session = audit.load(saved / "verification.json"), audit.load(saved / "session.json")
    session["coordinate_contract"]["RK4"] = "project outside after every step"
    write(saved / "session.json", session)
    rehash(saved, receipt, "session.json")
    with pytest.raises(ValueError, match="scope/resource"):
        audit.audit(saved)


def test_safe_member_refuses_escape_and_symlink(tmp_path):
    payload = tmp_path / "payload"
    payload.write_text("data")
    alias = tmp_path / "alias"
    alias.symlink_to(payload)
    for path in ("../payload", str(payload), "alias"):
        with pytest.raises(ValueError):
            audit.safe_member(tmp_path, path)
