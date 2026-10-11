"""Resource/reuse/continuation contract tests; no new transport trajectories."""

import copy
import json
import subprocess
from types import SimpleNamespace

import pytest
import trace_resume_check as check
import trace_resume_context as ctx
import trace_resume_job as job
import trace_resume_probe as probe

c = ctx.c


@pytest.fixture(scope="module")
def inputs():
    return ctx.inputs()


def test_original_failure_sources_and_completed_payloads_preserved():
    result = ctx.preservation_check()
    assert result["baseline_files"] == 1013
    assert result["resource_failure_files_unchanged"] == 241
    assert result["production_modules_unchanged"] == 51
    assert result["accepted_implementation_files_unchanged"] == 352
    assert len(ctx.sources()) == 112 and len(ctx.prior.sources()) == 106
    assert len(ctx.prior.legacy.old.sources()) == 88


def test_only_eight_unexecuted_definitions_change_one_resource_field(inputs):
    original = ctx.previous()
    changed = set(ctx.changed_ids(original))
    assert len(changed) == 8 and not changed.intersection(inputs["reused_cells"])
    for identifier, old in original["cells_definitions"].items():
        new = copy.deepcopy(inputs["cells_definitions"][identifier])
        if identifier in changed:
            assert new["execution"]["max_trace_bytes"] == 64 * 1024**2
            new["execution"]["max_trace_bytes"] = old["execution"]["max_trace_bytes"]
        assert new == old
    assert inputs["plan"] == original["plan"]
    for key in ("criteria", "native_rows", "cells_rows", "common_times_s", "cells_runtime"):
        assert inputs[key] == original[key]


def test_reuse_and_new_execution_are_disjoint_complete_and_correctly_costed(inputs):
    old = {r["id"] for r in inputs["cells_rows"]}
    reused, fresh = set(inputs["reused_cells"]), {r["id"] for r in inputs["new_cells_rows"]}
    assert len(reused) == 26 and len(fresh) == 22 and not reused & fresh
    assert reused | fresh == old and len(old) == 48
    assert inputs["new_cells_rows"] == inputs["cells_rows"][26:]
    counts = {
        backend: sum(
            ctx.prior.count(r["hold_step_s"]) * r["subdivision"]
            for r in inputs["new_cells_rows"]
            if r["backend"] == backend
        )
        for backend in ("jax_eager", "jax_jit")
    }
    assert counts == {"jax_eager": 4000, "jax_jit": 4480}
    resources = ctx.resources()
    assert resources["estimated_cells_seconds_with_allowances"] == 5295
    assert resources["estimated_combined_artifact_bytes_with_allowances"] == 502363957
    assert resources["estimated_largest_worker_file_bytes_with_allowances"] == 16791168
    assert resources["peak_RAM_measured"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_trace_bytes", 32 * 1024**2),
        ("max_trace_bytes", True),
        ("new_native_runs", 16),
        ("new_cells_runs", 48),
        ("reused_cells_runs", 25),
        ("new_cells_steps", 8481),
        ("total_timeout_seconds", 20000),
        ("cpu_affinity", "0-31"),
        ("automatic_polling", True),
        ("automatic_retry", True),
        ("automatic_expansion", True),
        ("trajectory_qualified", True),
        ("forcing_convergence_qualified", True),
        ("native_convergence_qualified", True),
        ("biology_validated", True),
        ("gpu_tested", True),
    ],
)
def test_unregistered_scope_resource_or_claim_change_rejected(key, value):
    with pytest.raises(ValueError):
        ctx.validate_plan(c.read(ctx.PLAN) | {key: value})


def test_actual_production_timeline_probe_covers_original_and_amended_budgets(inputs):
    result = c.read(ctx.PROBE)
    probe.validate(result, inputs)
    assert len(result["rows"]) == 48
    assert result["original_guard_rejections"] == 8
    assert result["largest_trace_estimate_bytes"] == 25838496
    assert sum(r["max_trace_bytes"] == 67108864 for r in result["rows"]) == 8
    assert all(r["nominal_steps"] == r["event_split_steps"] for r in result["rows"])
    assert result["integration_calls"] == 0


@pytest.mark.parametrize(
    "corruption",
    [
        "count",
        "estimate",
        "grid",
        "cap",
        "original_guard",
        "runtime",
        "source",
        "integration",
    ],
)
def test_resource_receipt_corruptions_rejected(inputs, corruption):
    result = copy.deepcopy(c.read(ctx.PROBE))
    row = next(v for v in result["rows"] if v["original_guard_rejected"])
    if corruption == "count":
        result["rows"].pop()
    elif corruption == "estimate":
        row["event_split_trace_bytes"] -= 1
    elif corruption == "grid":
        row["event_split_steps"] -= 1
    elif corruption == "cap":
        row["max_trace_bytes"] = 16777216
    elif corruption == "original_guard":
        row["original_guard_rejected"] = False
    elif corruption == "runtime":
        result["runtime"] = {}
    elif corruption == "source":
        result["source_hashes"]["src/cells/core/runner.py"] = "0" * 64
    else:
        result["integration_calls"] = 1
    with pytest.raises(ValueError):
        probe.validate(result, inputs)


def test_saved_complete_rows_pass_unmodified_internal_arithmetic(inputs):
    result = c.read(ctx.REUSE)
    check.validate_reuse(result, inputs)
    assert result["internal_laws"]["comparisons"] == 666108
    assert result["internal_laws"]["failed_comparisons"] == 0
    assert result["internal_laws"]["first_failures"] == []
    assert result["retained_native_runs"] == 16 and result["retained_cells_runs"] == 26
    assert result["original_cells_worker_receipt_exists"] is False
    assert result["independent_audit_run"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("retained_cells_runs", 48),
        ("new_cells_runs", 22),
        ("retained_native_runs", 15),
        ("original_cells_worker_receipt_exists", True),
        ("integration_calls", 1),
        ("independent_audit_run", True),
        ("trajectory_qualified", True),
    ],
)
def test_reuse_receipt_cannot_overclaim_or_invent_worker_metadata(inputs, key, value):
    result = c.read(ctx.REUSE) | {key: value}
    with pytest.raises(ValueError):
        check.validate_reuse(result, inputs)


def test_reused_results_resolve_to_original_bytes_not_copies(inputs, tmp_path):
    for identifier, entry in inputs["reused_cells"].items():
        path = check.cells_path(inputs, tmp_path, identifier)
        assert path.is_relative_to(ctx.FAILED)
        assert c.sha(path) == entry["sha256"]
    for row in inputs["new_cells_rows"]:
        path = check.cells_path(inputs, tmp_path, row["id"])
        assert path == tmp_path / "cells" / row["id"] / "result.json"
        assert not path.exists()


@pytest.mark.parametrize("corruption", ["path", "digest", "unknown"])
def test_resolver_rejects_mismatched_provenance(inputs, tmp_path, corruption):
    r = copy.deepcopy(inputs)
    identifier = next(iter(r["reused_cells"]))
    if corruption == "path":
        r["reused_cells"][identifier]["path"] = "../registration.json"
    elif corruption == "digest":
        r["reused_cells"][identifier]["sha256"] = "0" * 64
    else:
        identifier = "unregistered"
    with pytest.raises(ValueError):
        check.cells_path(r, tmp_path, identifier)


def test_cells_worker_passes_only_missing_rows_after_full_timeline_probe(
    inputs, tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setattr(probe, "probe", lambda r: c.read(ctx.PROBE))

    def fake_export(subset, output):
        calls.append(copy.deepcopy(subset))
        assert (output / "runtime-resource-probe.json").exists()
        return {"engine": "fabricated_test_export", "results": {}}

    monkeypatch.setattr(job.old, "cells_worker", fake_export)
    result = job.cells_worker(inputs, tmp_path)
    assert len(calls) == 1 and calls[0]["cells_rows"] == inputs["new_cells_rows"]
    assert set(calls[0]["cells_definitions"]) == {r["id"] for r in inputs["new_cells_rows"]}
    assert calls[0]["plan"]["cells_runs"] == 22 and inputs["plan"]["cells_runs"] == 48
    assert calls[0]["plan"]["max_artifact_bytes"] == 1073741824 - 246326549
    assert result["new_cells_runs"] == 22 and result["reused_cells_runs"] == 26


def test_failed_resource_probe_prevents_any_rollout(inputs, tmp_path, monkeypatch):
    def rejected(r):
        raise ValueError("fabricated resource rejection")

    def forbidden(*args, **kwargs):
        pytest.fail("Rollout started despite resource preflight failure")

    monkeypatch.setattr(probe, "probe", rejected)
    monkeypatch.setattr(job.old, "cells_worker", forbidden)
    with pytest.raises(ValueError, match="resource rejection"):
        job.cells_worker(inputs, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_combined_loader_visits_every_original_and_new_row_once(inputs, tmp_path, monkeypatch):
    """Routing-only mock; actual retained physics is checked in the separate reuse receipt."""
    native_worker = c.read(ctx.FAILED / "native.json")
    actual_read = c.read
    visited = []
    cell_paths = {
        check.cells_path(inputs, tmp_path, row["id"]): row for row in inputs["cells_rows"]
    }

    def fake_read(path):
        if path not in cell_paths:
            return actual_read(path)
        row = cell_paths[path]
        return {
            "id": row["id"],
            "times": [],
            "history": [],
            "observations": [],
            "diagnostics": [],
            "final_step_index": 0,
        }

    def native_rows(view, checks):
        h = view["plan"]["hold_step_s"]
        rows = [r for r in native_worker["results"] if r["row"]["dt_s"] == h]
        pairs = [p for p in native_worker["pairs"] if p["row_id"].startswith(f"{h:.8f}/")]
        return {}, rows, pairs, native_worker["zero_control"][f"{h:.8f}"]

    def fake_decoder(view, record, row, checks):
        assert record["id"] == row["id"]
        visited.append(row["id"])
        return []

    monkeypatch.setattr(c, "read", fake_read)
    monkeypatch.setattr(check, "read_native", native_rows)
    monkeypatch.setattr(check.old.local, "cells_record", fake_decoder)
    _, _, coverage = check.load_fine(inputs, tmp_path)
    assert visited == [r["id"] for r in inputs["cells_rows"]] and len(set(visited)) == 48
    assert coverage == {
        "retained_native_runs": 16,
        "retained_cells_runs": 26,
        "new_cells_runs": 22,
        "Cells_zero_pairs": 12,
    }


def test_launch_is_detached_and_does_not_poll(inputs, tmp_path, monkeypatch, capsys):
    c.write(tmp_path / "registration.json", inputs)
    monkeypatch.setattr(job, "register", lambda output: inputs)
    calls = []

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=333333)  # no poll or wait method

    monkeypatch.setattr(job.subprocess, "Popen", spawn)
    job.launch(tmp_path)
    assert len(calls) == 1 and calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdin"] == subprocess.DEVNULL
    assert calls[0][0][-2:] == ["execute", str(tmp_path)]
    receipt = c.read(tmp_path / "launch.json")
    assert receipt["new_cells_runs"] == 22 and receipt["new_native_runs"] == 0
    assert receipt["automatic_polling"] is receipt["automatic_retry"] is False
    assert receipt["independent_audit"] == "await_user_instruction"
    assert "launched_detached" in capsys.readouterr().out


def test_timeout_preserves_partial_output_without_retry(inputs, tmp_path, monkeypatch):
    c.write(tmp_path / "registration.json", inputs)
    monkeypatch.setattr(ctx, "validate_registration", lambda r: None)
    monkeypatch.setattr(job.old, "capsule", lambda output, r: None)
    calls = []

    def expired(command, **kwargs):
        calls.append((command, kwargs))
        c.write(tmp_path / "partial.json", {"test_payload": True})
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(job.subprocess, "run", expired)
    with pytest.raises(subprocess.TimeoutExpired):
        job.execute(tmp_path)
    assert len(calls) == 1 and calls[0][1]["timeout"] == 6600
    assert calls[0][0][-2] == "cells" and job.STAGES == ("cells", "comparison")
    failure = c.read(tmp_path / "failure.json")
    assert failure["stage"] == "cells" and failure["automatic_retry"] is False
    assert failure["files_sha256"]["partial.json"] == c.sha(tmp_path / "partial.json")
    assert not (tmp_path / "capture.json").exists()


def test_comparison_imports_no_model_and_keeps_original_gate_surface():
    code = """
import sys
sys.path.insert(0, "validation/betse/response_resume")
import trace_resume_check as check
assert not any(n.split(".")[0] in check.old.fence.FORBIDDEN for n in sys.modules)
assert check.old.compare_panel.__module__ == "refined_response_check"
assert check.old.local.cells_record.__module__ == "refined_response_cells_check"
assert check.old.native_record.__module__ == "refined_response_check"
sys.meta_path.insert(0, check.old.fence.ImportFence())
for name in check.old.fence.FORBIDDEN:
    try:
        __import__(name)
    except RuntimeError as error:
        assert "Offline audit forbids" in str(error)
    else:
        raise AssertionError(name)
print("fence_and_frozen_arithmetic_pass")
"""
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code],
        cwd=c.ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    assert result.stdout.strip() == "fence_and_frozen_arithmetic_pass"


def test_registration_rejects_definition_mutation_before_reuse_check(inputs, tmp_path, monkeypatch):
    pre = {
        "sources": ctx.sources(),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "status": "resource_and_reuse_preflight_pass_not_continuation_execution",
    }
    path = tmp_path / "mock-prelaunch.json"
    c.write(path, pre)
    monkeypatch.setattr(ctx, "PRELAUNCH", path)
    r = copy.deepcopy(inputs) | {
        "schema": "cells.betse_trace_resume_registration@1",
        "sources": pre["sources"],
        "prelaunch_sha256": c.sha(path),
        "preservation_sha256": pre["preservation_sha256"],
    }
    identifier = r["new_cells_rows"][0]["id"]
    r["cells_definitions"][identifier]["execution"]["dt"] *= 2
    with pytest.raises(ValueError, match="registration/input/source"):
        ctx.validate_registration(r)
    assert json.dumps(inputs, allow_nan=False)
