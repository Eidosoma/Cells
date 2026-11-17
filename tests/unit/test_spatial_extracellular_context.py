"""Version separation preserves old guards instead of weakening them for new code."""

import hashlib
from pathlib import Path

import pytest

from scripts import audit_preserved_spatial_extracellular_reference as preserved
from scripts import test_spatial_extracellular_build as matrix
from tests.spatial_extracellular_fixtures import REFERENCE, REFERENCE_SHA

ROOT = Path(__file__).resolve().parents[2]


def test_original_reference_no_production_change_guard_still_refuses_current_build():
    from tests.spatial_extracellular_numerical_data import load_panel

    with pytest.raises(ValueError, match="Accepted production changed"):
        load_panel()
    assert (
        hashlib.sha256((REFERENCE / "verification.json").read_bytes()).hexdigest() == REFERENCE_SHA
    )


def test_historical_test_routing_does_not_hide_current_model_tests():
    assert matrix.HISTORICAL == (
        "tests/unit/test_spatial_extracellular_dynamics.py",
        "tests/unit/test_spatial_extracellular_artifact_audit.py",
    )
    assert all("production" not in p and "execution" not in p for p in matrix.HISTORICAL)
    assert (
        matrix.sha(ROOT / "scripts/test_finite_extracellular_production_build.py")
        == matrix.DRIVER_SHA
    )


def test_changed_capsule_is_refused_before_extraction(tmp_path, monkeypatch):
    archive = tmp_path / "not-an-archive"
    archive.write_bytes(b"changed")
    monkeypatch.setattr(preserved, "ARCHIVE", archive)
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="identity"):
        preserved.extract_sources(destination)
    assert not destination.exists()
