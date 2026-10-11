"""Bounded production contact smoke and detached controller guards."""

import copy
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
job = importlib.import_module("process_job")
check = importlib.import_module("process_check")


def fixtures():
    protocol = job.c.read(check.CAPTURE / "registration.json")["protocol"]
    cases = protocol["profiles"]["matched_constants"]["cases"]
    selected = [
        case
        for case in cases
        if case["id"]
        in {
            "baseline",
            "availability=0.0",
            "alpha_mol_m2_s=0.0",
            "mathematical_reverse",
            "mathematical_stall",
            "mathematical_forward",
        }
    ]
    assert len(selected) == 6
    return selected, job.c.read(check.CAPTURE / "comparison.json"), protocol


def test_six_state_numpy_eager_compiled_production_contact_smoke():
    result = check.evaluate(*fixtures())
    assert result["status"] == "pass" and result["comparisons"] == 180
    assert not result["native_rerun"] and not result["coupled_production_model_accepted"]


@pytest.mark.parametrize("change", ["duplicate", "invalid", "missing"])
def test_probe_coverage_and_domain_guards(change):
    cases, saved, protocol = copy.deepcopy(fixtures())
    if change == "duplicate":
        cases.append(cases[0])
    elif change == "invalid":
        cases[0]["na_in_mM"] = 0
    else:
        saved["rows"] = [
            r
            for r in saved["rows"]
            if not (
                r["engine"] == "native"
                and r["profile"] == "matched_constants"
                and r["case"] == "baseline"
            )
        ]
    with pytest.raises(ValueError):
        check.evaluate(cases, saved, protocol)


def test_prechange_context_preserves_all_old_files_and_registers_new_module():
    result = job.prior()
    assert result["old_production_modules"] == 51
    assert result["current_production_modules"] == 52


def test_launch_detaches_without_polling(tmp_path, monkeypatch):
    def register(output, *_):
        job.c.write(output / "registration.json", {"fixture": True})

    monkeypatch.setattr(job, "register", register)
    calls = []

    def popen(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    result = job.launch(tmp_path, None, None)
    assert result["automatic_polling"] is False and calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdin"] == job.subprocess.DEVNULL


def test_failure_is_durable_and_not_success(tmp_path, monkeypatch):
    def fail(_output):
        raise ValueError("Injected authentication failure")

    monkeypatch.setattr(job, "authenticate", fail)
    with pytest.raises(ValueError, match="Injected"):
        job.execute(tmp_path)
    assert job.c.read(tmp_path / "failure.json")["status"] == "failed_not_qualified"
    assert not (tmp_path / "completion.json").exists()


def test_attempted_execution_is_not_replaced(tmp_path):
    job.c.write(tmp_path / "started.json", {"fixture": True})
    before = job.c.sha(tmp_path / "started.json")
    with pytest.raises(ValueError, match="attempted"):
        job.execute(tmp_path)
    assert job.c.sha(tmp_path / "started.json") == before
    assert not (tmp_path / "failure.json").exists()


def test_fresh_output_required(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(tmp_path, None, None)


def test_worker_environment_is_explicit(monkeypatch):
    for name in ("PYTEST_ADDOPTS", "PYTHONPATH", "PYTEST_PLUGINS"):
        monkeypatch.setenv(name, "unexpected override")
    env = job.environment()
    assert all(name not in env for name in ("PYTEST_ADDOPTS", "PYTHONPATH", "PYTEST_PLUGINS"))
    assert env["JAX_ENABLE_X64"] == "true" and env["JAX_DISABLE_JIT"] == "false"
    assert env["JAX_PLATFORMS"] == "cpu"
    assert job.protocol()["regression_tests"] == 348
    assert job.protocol()["total_timeout_seconds"] == 900
