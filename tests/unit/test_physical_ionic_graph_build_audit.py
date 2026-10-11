"""Independent graph saved-data checks reject rehashed corrupt state and readouts."""

import json
from dataclasses import replace

import numpy as np
import pytest

from cells.core.runner import run
from cells.io import _sha256 as sha
from cells.io import write_run
from scripts.audit_physical_ionic_graph_build import audit_run
from tests.physical_ionic_graph_fixtures import REFERENCE, load_cases, spec_for

PLAN, CASES = load_cases()


@pytest.fixture
def saved(tmp_path):
    original = next(c for c in CASES if c.id == "star_divalent")
    case = replace(original, horizon_s=0.006)
    result = run(spec_for(case, samples=[0, 0.00013, 0.00137, 0.006]))
    write_run(tmp_path / "run", result, checkpoint_times=(0.002,))
    return tmp_path / "run", case.definition()


def test_saved_complete_graph_has_independent_readouts_and_dense_domain(saved):
    path, case = saved
    _, report = audit_run(path, case, PLAN, REFERENCE / case["id"])
    assert report["independent_readout_fields"] == 38
    assert report["dense_domain"]["pass"]


@pytest.mark.parametrize(
    "field",
    [
        "amount",
        "gate",
        "junction_gate",
        "junction_transferred",
        "junction_dissipated_energy_pJ",
        "channel_transferred",
        "leak_transferred",
        "pump_cycles",
        "dissipated_energy_pJ",
        "observed_junction_gate",
        "observed_junction_transferred",
        "observed_junction_gate_inf",
        "observed_junction_gate_rate_per_s",
        "observed_junction_availability",
        "observed_junction_open_fraction",
        "observed_junction_effective_permeability_m_per_s",
        "observed_junction_flux_fmol_per_s",
        "observed_junction_delta_mu_J_per_mol",
        "observed_junction_current_A",
        "observed_junction_dissipation_rate_pJ_per_s",
        "observed_channel_availability",
        "observed_channel_flux_fmol_per_s",
        "observed_bath_exchange_fmol",
        "observed_species_balance_fmol",
        "observed_global_species_balance_fmol",
        "observed_global_charge_balance_C",
        "observed_resolved_energy_balance_pJ",
    ],
)
def test_rehashed_corrupt_real_values_cannot_pass(saved, field):
    path, case = saved
    with np.load(path / "trajectory.npz", allow_pickle=False) as source:
        arrays = dict(source)
    # Corrupt a REAL route/cell, not only padding. At time > 0 to evade t=0 identity alone.
    arrays[field].reshape(len(arrays[field]), -1)[1, 0] += 1
    np.savez(path / "trajectory.npz", **arrays)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files_sha256"]["trajectory.npz"] = sha(path / "trajectory.npz")
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, AssertionError)):
        audit_run(path, case, PLAN, REFERENCE / case["id"])
