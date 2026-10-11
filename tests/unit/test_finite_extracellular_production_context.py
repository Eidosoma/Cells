"""New production must not bypass the unchanged finite-reference source guards."""

import json
import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from scripts import test_finite_extracellular_production_build as driver


@pytest.mark.parametrize("failed", [None, "current", "reference", "finite"])
def test_matrix_routes_failures_and_restores_overrides(tmp_path, monkeypatch, failed):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)
    seen = []

    def execute(path, *, only="finite"):
        seen.append((only, os.environ.get("PYTEST_ADDOPTS")))
        path.mkdir()
        result = {
            "status": "failed" if only == failed else "pass",
            "contexts": {only: {}},
            "total_tests": 2,
        }
        (path / "verification.json").write_text(json.dumps(result))
        return result

    monkeypatch.setattr(driver.previous, "run_tests", execute)
    monkeypatch.setattr(driver, "execute_preserved", execute)
    result = driver.run_tests(tmp_path / "matrix")
    assert result["status"] == ("pass" if failed is None else "failed")
    assert result["total_tests"] == 6
    assert seen[1:] == [("reference", None), ("finite", None)]
    assert all("--ignore=" + name in seen[0][1] for name in driver.FINITE_HISTORICAL)
    assert driver.V1_PROSPECTIVE in seen[0][1]
    assert result["unexecuted_prospective_suite"]["tests"] == 13
    assert "PYTEST_ADDOPTS" not in os.environ


@pytest.mark.parametrize("key", ["PYTEST_ADDOPTS", "PYTEST_PLUGINS"])
def test_hidden_overrides_refused(tmp_path, monkeypatch, key):
    monkeypatch.setenv(key, "unregistered")
    with pytest.raises(ValueError, match="inherited pytest"):
        driver.run_tests(tmp_path / "matrix")


def test_preserved_nested_subprocess_uses_pinned_environment(tmp_path, monkeypatch):
    def copy(destination, *, extract):
        assert extract is driver.extract_sources
        destination.mkdir()
        return destination

    monkeypatch.setattr(driver.previous, "reference_workspace", copy)
    workspace = driver.preserved_workspace(tmp_path / "historical")
    assert (workspace / ".venv").resolve() == Path(sys.prefix).resolve()
    child = subprocess.run(
        [
            str(workspace / ".venv/bin/python"),
            "-c",
            "import json, sys; from importlib.metadata import version; "
            "print(json.dumps([list(sys.version_info[:3]), "
            "{p: version(p) for p in ('numpy', 'jax', 'scipy')}]))",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(child.stdout) == [
        list(sys.version_info[:3]),
        {p: version(p) for p in ("numpy", "jax", "scipy")},
    ]


def test_preserved_environment_link_never_overwrites_existing_path(tmp_path, monkeypatch):
    def copy(destination, *, extract):
        destination.mkdir()
        (destination / ".venv").mkdir()
        return destination

    monkeypatch.setattr(driver.previous, "reference_workspace", copy)
    with pytest.raises(FileExistsError):
        driver.preserved_workspace(tmp_path / "historical")
    assert (tmp_path / "historical/.venv").is_dir()
    assert not (tmp_path / "historical/.venv").is_symlink()
