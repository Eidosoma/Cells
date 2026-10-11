"""Version separation preserves old guards instead of weakening them for new code."""

import hashlib
import json
import tarfile
import tomllib
from pathlib import Path

import pytest

import cells
from scripts import audit_preserved_spatial_extracellular_reference as preserved
from scripts import test_spatial_extracellular_build as matrix
from tests.spatial_extracellular_fixtures import REFERENCE, REFERENCE_SHA

ROOT = Path(__file__).resolve().parents[2]


def test_archive_and_receipt_authenticate_every_preserved_member():
    receipt = json.loads((ROOT / "reports/core-010-preservation.json").read_text())
    assert receipt["status"] == "pass"
    assert receipt["archive_sha256"] == preserved.ARCHIVE_SHA
    assert hashlib.sha256(preserved.ARCHIVE.read_bytes()).hexdigest() == preserved.ARCHIVE_SHA
    with tarfile.open(preserved.ARCHIVE) as archive:
        assert set(archive.getnames()) == set(receipt["archive_files_sha256"])
        for name, expected in receipt["archive_files_sha256"].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected
        project = tomllib.loads(archive.extractfile("pyproject.toml").read().decode())
        assert project["project"]["version"] == "0.14.0"
    current = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert current["project"]["version"] == cells.__version__ != "0.14.0"


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
