"""Saved-output corruption cannot pass by simply refreshing a payload checksum."""

import json
from dataclasses import replace

import numpy as np
import pytest

from cells.core.runner import run
from cells.io import _sha256 as sha
from cells.io import write_run
from scripts.audit_voltage_gated_build import REFERENCE, audit_run
from tests.reference_voltage_gated_dynamics import load_panel
from tests.voltage_gated_fixtures import spec_for

PLAN, CASES = load_panel()


@pytest.fixture
def saved(tmp_path):
    original = next(c for c in CASES if c.id == "divalent_depolarized")
    case = replace(original, horizon_s=0.005)
    result = run(spec_for(case, samples=[0, 0.00013, 0.00137, 0.005]))
    write_run(tmp_path / "run", result)
    definition = json.loads(json.dumps(case.definition()))
    return tmp_path / "run", definition


def test_saved_gate_state_readouts_dense_and_snapshots_pass(saved):
    path, case = saved
    _, report = audit_run(path, case, PLAN, REFERENCE / case["id"])
    assert report["independent_readout_fields"] == 26
    assert report["dense_domain"]["pass"]


@pytest.mark.parametrize(
    "field",
    [
        "gate",
        "channel_transferred",
        "observed_gate",
        "observed_channel_transferred",
        "observed_gate_inf",
        "observed_gate_tau_s",
        "observed_gate_rate_per_s",
        "observed_channel_availability",
        "observed_channel_open_probability",
        "observed_channel_effective_permeability_m_per_s",
        "observed_channel_flux_fmol_per_s",
        "observed_inward_current_A",
        "observed_bath_exchange_fmol",
        "observed_resolved_energy_balance_pJ",
    ],
)
def test_rehashed_wrong_physical_data_is_refused(saved, field):
    path, case = saved
    with np.load(path / "trajectory.npz", allow_pickle=False) as values:
        data = dict(values)
    data[field].flat[-1] += 1
    np.savez(path / "trajectory.npz", **data)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files_sha256"]["trajectory.npz"] = sha(path / "trajectory.npz")
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((AssertionError, ValueError)):
        audit_run(path, case, PLAN, REFERENCE / case["id"])
