"""Negative controls for the separate, non-RHS NUM-003 artifact auditor."""

import hashlib
import json

import numpy as np
import pytest

from scripts import audit_bioelectric_pair_reference as audit
from tests import reference_bioelectric_pair as ref


def initial_native():
    case = ref.load_panel()[1][0]
    values = np.tile(ref.initial_state(case.parameters, increments=True), (2, 1))
    return case.definition(), values


def test_native_initial_balances_and_gate_only_change():
    case, values = initial_native()
    values[1, ref.GATE] = 0.3
    assert audit.native_balances(case, values) == {
        "amount_fmol": 0,
        "charge_as_voltage_V": 0,
        "energy_pJ": 0,
    }


@pytest.mark.parametrize("gate", [-0.1, 1.1, np.nan])
def test_native_bad_gate_is_refused(gate):
    case, values = initial_native()
    values[1, ref.GATE] = gate
    with pytest.raises(ValueError):
        audit.native_balances(case, values)


def test_native_bad_amount_is_refused():
    case, values = initial_native()
    values[1, 0] = -1000
    with pytest.raises(ValueError, match="amounts/gates"):
        audit.native_balances(case, values)


def test_duplicate_transfer_inventory_is_detected():
    case, values = initial_native()
    values[1, 14] = 0.2
    residual = audit.native_balances(case, values)
    assert residual["amount_fmol"] == pytest.approx(0.2)
    assert residual["charge_as_voltage_V"] > 1


def test_changed_payload_is_rejected_before_array_loading(tmp_path):
    payload = tmp_path / "payload.npz"
    payload.write_bytes(b"original")
    metadata = {
        "status": "pass",
        "files_sha256": {"payload.npz": hashlib.sha256(payload.read_bytes()).hexdigest()},
    }
    (tmp_path / "verification.json").write_text(json.dumps(metadata))
    payload.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Payload hash mismatch"):
        audit.audit(tmp_path)
