"""Saved-data and subprocess-mocked engineering tests; no new simulation evidence."""

import copy
import subprocess
from types import SimpleNamespace

import pytest
import refined_response_context as ctx
import refined_response_job as job
import refined_response_native as native

c = ctx.c


@pytest.fixture(scope="module")
def plan():
    return c.read(ctx.PLAN)


@pytest.fixture(scope="module")
def prior():
    return ctx.legacy.evidence.trusted_registration()


@pytest.fixture(scope="module")
def registered(plan, prior):
    """Unexecuted test input, not a registered scientific run."""
    return {
        "plan": plan,
        "native_rows": ctx.native_rows(plan),
        "cells_rows": ctx.cells_rows(plan),
        "cells_definitions": ctx.definitions(plan),
        "common_times_s": ctx.common_times(plan),
        "cells_export_shapes": ctx.export_shapes(),
        "criteria": prior["protocol"],
        **{k: prior[k] for k in ("base_protocol", "geometry", "settings", "cells_runtime")},
    }


@pytest.fixture(scope="module")
def saved(plan):
    """Real D077 fine no-op response, adapted only in the pytest envelope/metadata."""
    packets = {}
    for row in ctx.native_rows(plan):
        if row["condition"] == "suppression_recovery":
            continue
        pair = {}
        for mode in plan["native_modes"]:
            packet = native.links.read_packet(ctx.overlap_path(row, mode).parent, mode)
            metadata = ctx.prepared(row)["metadata"]
            packet["result"] |= {
                "schema": "cells.betse_refined_response_native_row@1",
                "row": row,
                "final_metadata": metadata
                | {"pickles_present": {"seed": True, "init": False, "sim": True}},
            }
            if mode == "observed":
                packet["metadata"] = metadata
            pair[mode] = packet
        packets[ctx.prior.key(row)] = pair
    return packets


def test_preserve_closed_failure_dispatch_and_production():
    preserved = ctx.preservation_check()
    assert preserved["baseline_files"] == 990
    assert preserved["capture_files_unchanged"] == 150
    assert preserved["audit_files_unchanged"] == 16
    assert preserved["refined_dispatch_files_unchanged"] == 1042
    assert preserved["accepted_implementation_files_unchanged"] == 352
    assert preserved["production_modules_unchanged"] == 51
    assert len(ctx.sources()) == 106
    assert len(ctx.legacy.old.sources()) == 88


def test_prospective_resource_allowance_and_exact_panel_size(registered):
    p = registered["plan"]
    result = ctx.resources(p)
    assert result["stage_seconds_with_allowances"] == {
        "native": 239,
        "cells": 10004,
        "comparison": 125,
    }
    assert result["estimated_artifact_bytes_with_allowances"] == 520964299
    assert result["estimated_largest_worker_file_bytes_with_allowances"] == 34058544
    assert result["peak_RAM_measured"] is False
    assert len(registered["native_rows"]) * 2 == p["native_runs"] == 16
    assert len(registered["cells_rows"]) == p["cells_runs"] == 48
    assert sum(ctx.count(r["dt_s"]) for r in registered["native_rows"]) == 960
    assert (
        sum(ctx.count(r["hold_step_s"]) * r["subdivision"] for r in registered["cells_rows"])
        == 13440
    )
    assert 0.000025 not in p["hold_steps_s"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("hold_steps_s", [0.00000625]),
        ("retained_hold_step_s", 0.00005),
        ("cells_subdivisions", [1, 4]),
        ("constant_profile", "source_constants"),
        ("control_atol", 1e-3),
        ("control_atol", float("nan")),
        ("cells_steps_total", True),
        ("native_runs", 8),
        ("cells_runs", 24),
        ("required_gates", "ignore_baseline"),
        ("across_hold_policy", "qualified"),
        ("cross_failure_policy", "relax"),
        ("max_artifact_bytes", 2**40),
        ("total_timeout_seconds", 20000),
        ("cpu_affinity", "0-31"),
        ("automatic_polling", True),
        ("automatic_retry", True),
        ("automatic_expansion", True),
        ("trajectory_qualified", True),
        ("native_convergence_qualified", True),
        ("forcing_convergence_qualified", True),
        ("biology_validated", True),
        ("gpu_tested", True),
    ],
)
def test_scope_resource_criteria_and_claim_changes_rejected(plan, key, value):
    with pytest.raises(ValueError):
        ctx.validate_plan(plan | {key: value})


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
@pytest.mark.parametrize("condition", ctx.held.CONDITIONS)
def test_fixed_input_separate_from_unchanged_solver_subdivision(registered, h, condition):
    view = ctx.panel_view(registered, h)
    assert len(view["common_times_s"]) == ctx.count(h) + 1
    assert len(view["native_rows"]) == 4 and len(view["cells_rows"]) == 24
    controls = None
    for row in view["cells_rows"]:
        if row["condition"] != condition:
            continue
        definition = view["cells_definitions"][row["id"]]
        assert definition == ctx.held.cells_definition(
            c.read(ctx.held.PLAN), condition, h, row["subdivision"], row["backend"]
        )
        assert definition["execution"]["dt"] == h / row["subdivision"]
        assert definition["execution"]["max_steps"] == ctx.count(h) * row["subdivision"]
        assert definition["experiment"]["observation_times"] == view["common_times_s"]
        inputs = definition["experiment"]["membrane_controls"]
        assert controls is None or inputs == controls
        controls = inputs
        assert len(inputs[0]["leak"]) == ctx.count(h)
        assert inputs[0]["leak"][-1]["time"] == (ctx.count(h) - 1) * h
    assert registered["plan"] == c.read(ctx.PLAN)


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
@pytest.mark.parametrize("condition", ["baseline", "zero_amplitude", "static_blocked"])
@pytest.mark.parametrize("mode", ["observed", "unobserved"])
def test_retained_fine_noop_links(plan, prior, saved, h, condition, mode):
    row = next(r for r in ctx.native_rows(plan) if (r["dt_s"], r["condition"]) == (h, condition))
    result = native.check_row(
        row,
        mode,
        saved[ctx.prior.key(row)][mode],
        prior,
        plan,
        ctx.prepared(row),
        c.read(ctx.overlap_path(row, mode)),
    )
    assert result["observed_steps"] == (ctx.count(h) if mode == "observed" else 0)


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
def test_retained_fine_pair_and_zero_identity(saved, h):
    panel = {
        condition: saved[f"{h:.8f}/{condition}"]["observed"]
        for condition in ("baseline", "zero_amplitude", "static_blocked")
    }
    assert native.check_zero(panel)["status"] == "baseline_zero_response_exact"
    for condition in panel:
        assert (
            native.links.check_pair(saved[f"{h:.8f}/{condition}"])["status"]
            == "observer_pair_exact"
        )


def test_launcher_detaches_once_without_polling(tmp_path, monkeypatch, capsys, plan):
    output = tmp_path / "mock-run"
    output.mkdir()
    c.write(output / "registration.json", {"plan": plan})
    monkeypatch.setattr(job, "register", lambda p: {"plan": plan})
    calls = []

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        # Deliberately no poll(), wait() or communicate().
        return SimpleNamespace(pid=123456)

    monkeypatch.setattr(job.subprocess, "Popen", spawn)
    job.launch(output)
    assert len(calls) == 1
    assert calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdin"] == subprocess.DEVNULL
    assert calls[0][0][-2:] == ["execute", str(output)]
    receipt = c.read(output / "launch.json")
    assert receipt["automatic_polling"] is receipt["automatic_retry"] is False
    assert receipt["independent_audit"] == "await_user_instruction"
    assert receipt["total_timeout_seconds"] == 11700
    assert "launched_detached" in capsys.readouterr().out


def test_stage_timeout_saves_failure_and_never_retries(tmp_path, monkeypatch, plan):
    output = tmp_path / "mock-timeout"
    output.mkdir()
    c.write(output / "registration.json", {"plan": plan})
    monkeypatch.setattr(ctx, "validate_registration", lambda r: None)
    monkeypatch.setattr(job, "capsule", lambda p, r: None)
    calls = []

    def timeout(command, **kwargs):
        calls.append(kwargs)
        c.write(output / "mock-partial.json", {"completed_step": 7})
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(job.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        job.execute(output)
    assert len(calls) == 1 and calls[0]["timeout"] == 300
    result = c.read(output / "failure.json")
    assert result["stage"] == "native" and result["automatic_retry"] is False
    assert result["files_sha256"]["mock-partial.json"] == c.sha(output / "mock-partial.json")
    assert not (output / "capture.json").exists()


def test_stage_commands_and_cpu_float64_environment(tmp_path, plan, monkeypatch):
    for stage in job.STAGES:
        command = job.stage_command(stage, tmp_path, plan)
        assert command[:3] == ["taskset", "-c", "0-3"]
        assert command[3] == str(c.REFERENCE_PYTHON if stage == "native" else c.CELLS_PYTHON)
        assert command[5].endswith("response_panel/refined_response_job.py")
    monkeypatch.setenv("PYTHONPATH", "/unregistered")
    monkeypatch.setenv("JAX_DISABLE_JIT", "1")
    env = job.environment(tmp_path)
    assert env["JAX_PLATFORMS"] == "cpu" and env["JAX_ENABLE_X64"] == "1"
    assert "PYTHONPATH" not in env and "JAX_DISABLE_JIT" not in env
    assert all(
        env[k] == "1"
        for k in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        )
    )


def test_launch_failure_has_durable_receipt_without_retry(tmp_path, monkeypatch, plan):
    output = tmp_path / "mock-launch-failure"
    output.mkdir()
    calls = []

    def fail(*args, **kwargs):
        calls.append(args)
        raise OSError("fabricated spawn failure")

    monkeypatch.setattr(job.subprocess, "Popen", fail)
    with pytest.raises(OSError, match="fabricated"):
        job.spawn_detached(output, plan, "execute")
    result = c.read(output / "failure.json")
    assert len(calls) == 1 and result["status"] == "launch_failed_not_started"
    assert result["automatic_retry"] is False and not (output / "launch.json").exists()


def test_software_launcher_never_chains_a_trajectory(tmp_path, monkeypatch, capsys):
    output = tmp_path / "mock-software-launch"
    output.mkdir()
    c.write(output / "registration.json", {"software_plan": job.SOFTWARE_PLAN})
    calls = []

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=222222)  # no poll or wait method

    monkeypatch.setattr(job.subprocess, "Popen", spawn)
    job.spawn_detached(output, job.SOFTWARE_PLAN, "checks")
    result = c.read(output / "launch.json")
    assert len(calls) == 1 and calls[0][0][-2] == "checks"
    assert calls[0][1]["start_new_session"] is True
    assert result["total_timeout_seconds"] == 300
    assert result["regression_timeout_seconds"] == 180
    assert result["automatic_trajectory_launch"] is result["automatic_polling"] is False
    assert result["automatic_retry"] is False
    assert "launched_detached" in capsys.readouterr().out


def test_registration_rejects_changed_source_before_authentication(
    tmp_path, monkeypatch, registered
):
    pre = {
        "plan": registered["plan"],
        "status": "software_checks_pass_not_response_execution",
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "test_receipt": str(ctx.PLAN.relative_to(c.ROOT)),
        "test_receipt_sha256": c.sha(ctx.PLAN),
        "sources": ctx.sources(),
    }
    path = tmp_path / "mock-prelaunch.json"
    c.write(path, pre)
    monkeypatch.setattr(ctx, "PRELAUNCH", path)
    r = copy.deepcopy(registered) | {
        "schema": "cells.betse_refined_response_registration@1",
        "dispatch_anchors": ctx.ANCHORS,
        "prelaunch_sha256": c.sha(path),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "sources": pre["sources"] | {"response_panel/refined_response_check.py": "0" * 64},
    }
    with pytest.raises(ValueError, match="identity/source/tests"):
        ctx.validate_registration(r)
