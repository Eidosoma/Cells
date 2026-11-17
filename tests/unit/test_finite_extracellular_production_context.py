"""New production must not bypass the unchanged finite-reference source guards."""

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from scripts import test_finite_extracellular_production_build as driver


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
