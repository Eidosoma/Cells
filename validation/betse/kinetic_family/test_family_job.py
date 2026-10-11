"""Fast controller checks; never launch a real acceptance job from a test."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from validation.betse.kinetic_family import family_job as job


def test_preserved_prior_authenticates_without_waiving_current_source_identity():
    result = job.prior()
    assert result["preservation_sha256"] == job.PRESERVATION_SHA
    assert len(result["coupled_capture_sha256"]) == 14


def test_source_inventory_contains_every_model_and_test():
    sources = job.sources()
    assert len([n for n in sources if n.startswith("src/cells/")]) == 55
    assert set(job.NEW_TESTS + job.OLD_TESTS) <= sources.keys()
    assert "src/cells/processes/kinetic_pump.py" in sources
    assert "src/cells/models/kinetic_finite_bounds.py" in sources


def test_protocol_does_not_rerun_historical_source_guard_suites():
    p = job.protocol()
    assert p["new_test_count"] == 74 and p["regression_count"] == 348
    assert p["trajectory_runs"] == p["restart_suffixes"] == 12
    assert (
        p["total_timeout_seconds"] > p["family_timeout_seconds"] + p["regression_timeout_seconds"]
    )
    assert all("reference" not in n and "artifact_audit" not in n for n in job.OLD_TESTS)


def test_environment_removes_inherited_pytest_overrides(monkeypatch):
    for key in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        monkeypatch.setenv(key, "do_not_inherit")
    env = job.environment()
    assert not any(k in env for k in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"))
    assert env["JAX_PLATFORMS"] == "cpu" and env["JAX_ENABLE_X64"] == "true"
    assert env["JAX_DISABLE_JIT"] == "false"


def test_launch_is_detached_and_never_waits_or_polls(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "register", lambda p: job.write(p / "registration.json", {}))
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=1234)  # No wait(), poll() or communicate().

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    result = job.launch(tmp_path)
    assert result["status"] == "launched_detached" and result["pid"] == 1234
    assert calls[0][1]["start_new_session"] and calls[0][0][-2] == "execute"
    assert not result["automatic_polling"]


def test_existing_outputs_refused(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(tmp_path)
    job.write(tmp_path / "receipt.json", {})
    with pytest.raises(FileExistsError):
        job.write(tmp_path / "receipt.json", {})


def test_authentication_failure_retains_terminal_failure_without_worker(tmp_path, monkeypatch):
    def failed(_):
        raise ValueError("Frozen source changed")

    monkeypatch.setattr(job, "authenticate", failed)
    with pytest.raises(ValueError, match="Frozen source"):
        job.execute(tmp_path)
    failure = json.loads((tmp_path / "failure.json").read_text())
    assert failure["status"] == "failed_not_accepted" and not failure["automatic_retry"]
    assert not (tmp_path / "completion.json").exists()
    with pytest.raises(ValueError, match="already attempted"):
        job.execute(tmp_path)


def test_failed_or_skipped_junit_is_not_a_pass(tmp_path):
    # Test input is a generated artifact, never an edit to a saved receipt.
    path = Path(tmp_path) / "sample.xml"
    path.write_text(
        '<testsuites><testsuite tests="2" failures="0" skipped="1" errors="0"/></testsuites>'
    )
    with pytest.raises(ValueError, match="Nonpassing"):
        job.test_count(path)
