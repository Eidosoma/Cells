"""Small serialized-output audit checks; frozen reference trajectories are read only."""

import json

import numpy as np
import pytest

from cells.core.runner import run
from cells.io import _sha256, write_run
from scripts.audit_multispecies_build import audit_run
from tests.multispecies_fixtures import spec_for
from tests.unit.test_multispecies_membrane import PLAN, REFERENCE, short_case


@pytest.fixture
def recorded(tmp_path):
    case = short_case()
    path = tmp_path / "run"
    result = run(spec_for(case, samples=[0.0, 0.003, 0.01, 0.027, 0.04]))
    write_run(path, result, checkpoint_times=(0.02,))
    return path, case


def test_serialized_readouts_and_reference_comparison(recorded):
    path, case = recorded
    _, report = audit_run(path, case.definition(), PLAN, REFERENCE / case.id)
    assert report["snapshots"] == 2
    assert report["accepted"]["errors"]["pass"]
    assert report["observed"]["accounting"]["pass"]


@pytest.mark.parametrize(
    "field",
    [
        "voltage_V",
        "leak_flux_fmol_per_s",
        "inward_current_A",
        "bath_exchange_fmol",
        "species_balance_fmol",
        "charge_balance_V",
        "resolved_energy_balance_pJ",
    ],
)
def test_rehashed_wrong_readout_is_independently_refused(recorded, field):
    path, case = recorded
    with np.load(path / "trajectory.npz", allow_pickle=False) as saved:
        data = dict(saved)
    data["observed_" + field].flat[1] += 1
    np.savez(path / "trajectory.npz", **data)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files_sha256"]["trajectory.npz"] = _sha256(path / "trajectory.npz")
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(AssertionError):
        audit_run(path, case.definition(), PLAN, REFERENCE / case.id)


def test_ordinary_payload_corruption_is_refused(recorded):
    path, case = recorded
    with (path / "trajectory.npz").open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(AssertionError):
        audit_run(path, case.definition(), PLAN, REFERENCE / case.id)
