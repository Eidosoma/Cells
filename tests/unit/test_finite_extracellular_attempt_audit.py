"""Corruption checks for the retained stopped NUM-009 attempt, not acceptance."""

import json
import shutil
from pathlib import Path

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
