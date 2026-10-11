"""Explicit routing is auditable and cannot silently turn failures into passes."""

import json
import os

import pytest

from scripts import test_finite_extracellular_build as driver


@pytest.mark.parametrize("failed", [False, True])
def test_driver_routes_only_unexecutable_v1_complete_suite(tmp_path, monkeypatch, failed):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)
    seen = []

    def execute(path, *, only):
        seen.append((only, os.environ.get("PYTEST_ADDOPTS")))
        path.mkdir()
        status = "failed" if only == "current" and failed else "pass"
        item = {"status": status, "contexts": {only: {"status": status}}, "total_tests": 2}
        (path / "verification.json").write_text(json.dumps(item))
        return item

    monkeypatch.setattr(driver.previous, "run_tests", execute)
    result = driver.run_tests(tmp_path / "matrix")
    assert result["status"] == ("failed" if failed else "pass")
    assert seen == [("current", "--ignore=" + driver.V1_PROSPECTIVE), ("reference", None)]
    assert "PYTEST_ADDOPTS" not in os.environ
    assert result["unexecuted_prospective_suite"]["tests"] == 13
    assert result["total_tests"] == 4


def test_driver_restores_environment_after_worker_exception(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)

    def execute(path, *, only):
        raise RuntimeError("worker failed")

    monkeypatch.setattr(driver.previous, "run_tests", execute)
    with pytest.raises(RuntimeError, match="worker failed"):
        driver.run_tests(tmp_path / "matrix")
    assert "PYTEST_ADDOPTS" not in os.environ


@pytest.mark.parametrize("key", ["PYTEST_ADDOPTS", "PYTEST_PLUGINS"])
def test_driver_rejects_inherited_hidden_routing(tmp_path, monkeypatch, key):
    monkeypatch.setenv(key, "unregistered")
    with pytest.raises(ValueError, match="inherited pytest overrides"):
        driver.run_tests(tmp_path / "matrix")
