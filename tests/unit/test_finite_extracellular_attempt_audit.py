"""Corruption checks for the retained stopped NUM-009 attempt, not acceptance."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from scripts import audit_finite_extracellular_attempt as audit

SESSION = Path(__file__).resolve().parents[2] / "runs/num-009-2026-09-10/reference-01"


@pytest.fixture
def saved(tmp_path):
    assert (SESSION / "failure.json").is_file(), "The retained failed attempt is required"
    root = tmp_path / "attempt"
    shutil.copytree(SESSION, root)
    return root


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def rehash(root, name):
    failure = audit.load(root / "failure.json")
    failure["files_sha256"][name] = audit.sha(root / name)
    write(root / "failure.json", failure)


def test_completed_acceptance_cannot_be_invented(saved):
    write(saved / "verification.json", {"status": "pass", "selected_dt_s": 0.002})
    with pytest.raises(ValueError, match="stopped, unqualified"):
        audit.audit(saved)


def test_failed_case_prefix_is_bound(saved):
    failure = audit.load(saved / "failure.json")
    failure["completed_cases"] = failure["completed_cases"][:-1]
    write(saved / "failure.json", failure)
    with pytest.raises(ValueError, match="prefix"):
        audit.audit(saved)


def test_rehashed_reference_false_pass_is_refused(saved):
    name = "star_mono_internal/analysis.json"
    record = audit.load(saved / name)
    record["references_pass"] = True
    write(saved / name, record)
    rehash(saved, name)
    with pytest.raises(ValueError, match="Recomputed analysis"):
        audit.audit(saved)


def test_rehashed_hidden_outside_change_is_refused(saved):
    name = "single_mono_small/radau.npz"
    arrays = audit.read_arrays(saved / name, 536870912)
    arrays["sample_state"][10, -1] += 0.01
    np.savez_compressed(saved / name, **arrays)
    rehash(saved, name)
    with pytest.raises(ValueError, match="Dense replay"):
        audit.audit(saved)


def test_rehashed_method_setting_is_refused(saved):
    name = "single_mono_small/radau.json"
    record = audit.load(saved / name)
    record["rtol"] = 1e-5
    write(saved / name, record)
    rehash(saved, name)
    with pytest.raises(ValueError, match="settings"):
        audit.audit(saved)


def test_unrun_case_cannot_be_added(saved):
    name = "single_mono_depletion/analysis.json"
    (saved / "single_mono_depletion").mkdir()
    write(saved / name, {"references_pass": True})
    with pytest.raises(ValueError, match="unexpected"):
        audit.audit(saved)


def test_missing_payload_is_refused(saved):
    (saved / "single_mono_small/radau.json").unlink()
    with pytest.raises(ValueError, match="Missing"):
        audit.audit(saved)


def test_failed_attempt_is_not_whole_panel_acceptance():
    report = audit.load(SESSION.parents[2] / "reports/num-009-stopped-attempt-audit.json")
    assert report["status"] == "pass"
    assert report["qualification_status"] == "stopped_not_qualified"
    assert report["selected_dt_s"] is None
    assert report["attempts"] == report["replayed_arrays"] == 80
    assert len(report["unrun_cases"]) == 4
    for record in report["diagnosis"]["star_mono_internal"].values():
        assert record["maximum_observed_outside_increment_fmol"] > 0
        assert record["native_accounting_pass"] and record["observed_accounting_pass"]
        assert record["reconstructed_observed_outside_amounts_constant"]
        assert not record["controls"]["pass"]
