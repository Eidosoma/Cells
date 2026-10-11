"""Pilot scope, retained numerical limits and explicit larger evidence bounds."""

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("long_pump_pilot", HERE / "pilot.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_plan_preserves_physics_tolerances_and_declares_work():
    original = pilot.u.plan()
    plan = pilot.make_plan(original)
    for name in ("mapping", "accounting", "trajectory", "refinement", "cells_steps_s"):
        assert plan[name] == original[name]
    assert original["duration_s"] == 0.01 and plan["duration_s"] == 0.1
    assert len(plan["common_times_s"]) == 101
    assert round(pilot.DURATION / pilot.DT) == 64000
    assert plan["resources"]["max_cells_steps"] >= plan["duration_s"] / min(plan["cells_steps_s"])


def test_explicit_label_extent_and_original_bound():
    sys.path.insert(0, str(HERE.parent / "pump_relaxation_clock"))
    import clock_labels

    with pytest.raises(ValueError, match="extent"):
        clock_labels.labels(0.1, 64000)
    np.testing.assert_array_equal(
        clock_labels.labels(0.1, 64000, max_count=64000), np.linspace(0, 0.1, 64000)
    )
    with pytest.raises(ValueError, match="extent"):
        clock_labels.labels(0.1, 64001, max_count=64000)


def test_bound_refused_before_native_import(tmp_path):
    import prepare

    for value in (0, 1025 * 1024**2, True):
        with pytest.raises(ValueError, match="allowance"):
            prepare.capture(
                tmp_path, tmp_path, {}, "pump_leak", 0, "observed", 0.1, stream_bytes=value
            )
    assert not any(n == "betse" or n.startswith("betse.") for n in sys.modules)


def test_existing_preparation_and_three_reference_inputs_authenticate():
    root = Path("/mnt/workspaces/Cells")
    original, paths = pilot.inputs(
        root / "ref-005e-fresh-20260919-01", root / "betse-relaxation-20260920-01"
    )
    assert len(paths) == 3
    assert original["protocol"]["accounting"] == pilot.make_plan(original["protocol"])["accounting"]


def test_all_production_grids_and_restart_fit_registered_storage():
    preparation = pilot.u.read(
        Path("/mnt/workspaces/Cells/ref-005e-fresh-20260919-01/prepare/preparation.json")
    )
    result = pilot.cell_preflight(pilot.make_plan(pilot.u.plan()), preparation)
    assert [row["steps"] for row in result["rows"]] == [2000, 4000, 8000]
    assert sum(row["restart_grid_checked"] for row in result["rows"]) == 1
    assert all(row["estimated_trace_bytes"] <= row["max_trace_bytes"] for row in result["rows"])


def test_original_allowance_is_rejected_by_finest_grid_preflight():
    preparation = pilot.u.read(
        Path("/mnt/workspaces/Cells/ref-005e-fresh-20260919-01/prepare/preparation.json")
    )
    plan = pilot.make_plan(pilot.u.plan())
    plan["resources"]["max_cells_trace_bytes"] = 256 * 1024**2
    with pytest.raises(ValueError, match="trace working storage"):
        pilot.cell_preflight(plan, preparation)


def test_streamed_trace_has_exact_original_values_and_coverage():
    import fresh_review

    saved, native, _ = fresh_review.modules()
    path = Path("/mnt/workspaces/Cells/long-pump-pilot-development-20260921-01/native-smoke/stream")
    original, old_checks = pilot.reader(saved, native, streamed=False).read(path)
    streamed, checks = pilot.reader(saved, native).read(path)
    match = saved.c.exact.Exact()
    for key in ("steps", "raw_steps"):
        values = streamed["trace"][key]
        match.match(list(values), original["trace"][key], "Complete streamed values")
        for index in (3, 0, -1, 2):
            match.match(values[index], original["trace"][key][index], "Random trace access")
        match.match(values[1:5:2], original["trace"][key][1:5:2], "Trace slice")
        with pytest.raises(IndexError):
            _ = values[len(values)]
    for key, value in old_checks.items():
        assert checks[key] == value
    assert checks["step_storage"] == "reiterable_authenticated_stream"


def test_streamed_trace_rejects_changed_capture(tmp_path):
    import shutil

    import fresh_review

    saved, native, _ = fresh_review.modules()
    source = Path(
        "/mnt/workspaces/Cells/long-pump-pilot-development-20260921-01/native-smoke/stream"
    )
    target = tmp_path / "stream"
    shutil.copytree(source, target)
    path = next(p for p in target.iterdir() if p.name != "manifest.json")
    payload = bytearray(path.read_bytes())
    payload[-1] ^= 1
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        pilot.reader(saved, native).read(target)


def test_streamed_cache_crosses_chunks_and_rewinds():
    import fresh_review

    saved, native, _ = fresh_review.modules()
    decoder = pilot.reader(saved, native, streamed=False)
    module = pilot.u.private("_test_trace_cache", HERE / "streamed_review.py")
    source = Path(
        "/mnt/workspaces/Cells/ref-005e-fresh-20260919-01/native/pump_leak/prefix/capture/stream"
    )
    iterator = iter(decoder.ctx.reader()(source))
    expected = {}
    try:
        for record in iterator:
            if record["kind"] == "native_step":
                expected[record["index"]] = record
                if record["index"] == 64:
                    break
    finally:
        iterator.close()
    store = module.StepStore(source, decoder.ctx.reader(), 2560)
    try:
        for index in (0, 31, 32, 63, 64, 2, 32):
            saved.c.exact.Exact().match(store.get(index), expected[index], "Trace cache boundary")
    finally:
        store.close()


def smoke_physics():
    import fresh_review

    saved, native, clocks = fresh_review.modules()
    path = Path("/mnt/workspaces/Cells/long-pump-pilot-development-20260921-01")
    row, _ = pilot.reader(saved, native).read(path / "native-smoke/stream")
    preparation = pilot.u.read(
        Path("/mnt/workspaces/Cells/betse-long-pump-pilot-20260921-02/preparation.json")
    )
    variant = next(
        v
        for v in preparation["native_preparation"]["protocol"]["variants"]
        if v["id"] == "pump_leak"
    )
    plan = pilot.make_plan(pilot.u.plan())
    plan["duration_s"] = row["steps"] * row["dt_s"]
    baseline = preparation["rows"]["pump_leak/observed"]
    return saved, clocks, row, baseline, plan, variant, path


def test_history_checks_use_one_trace_pass_and_preserve_all_science():
    saved, clocks, row, baseline, plan, variant, path = smoke_physics()
    store = row["trace"]["steps"].store
    passes = store.passes
    ledger = saved.e.Ledger()
    events = []

    def progress(event, **values):
        events.append((event, values))

    physical = clocks.inspect(
        saved.native_records,
        saved.c.exact.Exact,
        row,
        baseline,
        plan,
        variant,
        ledger,
        progress=progress,
    )
    assert store.passes - passes == 1
    points = saved.native_energy.reconstruct(
        row,
        variant,
        [i * row["dt_s"] for i in range(row["steps"] + 1)],
        ledger,
        progress=progress,
    )
    previous = pilot.u.read(path / "streamed-review-smoke.json")
    assert physical == previous["physical"]
    assert points["energy"] == previous["energy"]
    assert ledger.count == previous["comparisons"]
    assert ledger.maxima == previous["maxima"]
    assert [name for name, _ in events] == ["physics_steps", "energy_steps"]
    assert all(v["completed"] == v["total"] == 8 for _, v in events)


@pytest.mark.parametrize(
    "field",
    ["cc_time", "cc_env_time", "vm_time", "I_mem_time", "rho_cells_time", "rate_NaKATP_time"],
)
@pytest.mark.parametrize("change", ["first", "last", "missing"])
def test_fused_history_check_rejects_every_changed_history(field, change):
    saved, clocks, row, baseline, plan, variant, _ = smoke_physics()
    values = row["histories"][field]["values"]
    if change == "missing":
        values.pop()
    else:
        index = 0 if change == "first" else -1
        leaf = values[index]
        while isinstance(leaf[0], list):
            leaf = leaf[0]
        leaf[0] += 1e-10
    with pytest.raises(ValueError, match="Native history"):
        clocks.inspect(
            saved.native_records,
            saved.c.exact.Exact,
            row,
            baseline,
            plan,
            variant,
            saved.e.Ledger(),
        )


@pytest.mark.parametrize("change", ["content", "extra", "missing", "symlink"])
def test_reuse_authentication_rejects_changed_completed_artifact(tmp_path, change):
    for name in pilot.SIMULATIONS:
        directory = tmp_path / name
        directory.mkdir()
        pilot.u.write(directory / "result.json", {"value": name})
        pilot.u.write(
            directory / "completion.json",
            {
                "status": "completed",
                "files_sha256": pilot.u.inventory(directory),
            },
        )
    assert pilot.authenticate_simulations(tmp_path)["artifacts_verified"] == 3
    target = tmp_path / "observed/result.json"
    if change == "content":
        target.write_text("{}")
    elif change == "extra":
        (target.parent / "extra.json").write_text("{}")
    elif change == "missing":
        target.unlink()
    else:
        target.unlink()
        target.symlink_to(tmp_path / "cells/result.json")
    with pytest.raises((ValueError, FileNotFoundError)):
        pilot.authenticate_simulations(tmp_path)


@pytest.mark.parametrize("timeout", [False, True])
def test_reuse_controller_launches_only_review_and_preserves_timeout_progress(
    tmp_path, monkeypatch, timeout
):
    root, previous = tmp_path / "review", tmp_path / "old"
    root.mkdir()
    receipt = {"path": str(previous)}
    pilot.u.write(
        root / "registration.json",
        {
            "workspace": str(tmp_path),
            "reused_simulations": receipt,
            "phase_limits_seconds": {"compare": 21600},
        },
    )
    for phase in pilot.SIMULATIONS:
        pilot.u.write(
            previous / phase / "completion.json",
            {
                "elapsed_seconds": 1,
                "peak_rss_bytes": 1024,
            },
        )
    calls = []

    def run(command, **options):
        calls.append(command[-1])
        assert options["timeout"] == 21600
        directory = root / "compare"
        directory.mkdir()
        progress = pilot.Progress(directory)
        progress.phase = "native_physics"
        progress("physics_steps", completed=1000, total=64000)
        if timeout:
            raise subprocess.TimeoutExpired(command, options["timeout"])
        pilot.u.write(directory / "result.json", {"status": "test_pass"})
        pilot.u.write(
            directory / "completion.json",
            {
                "elapsed_seconds": 1,
                "peak_rss_bytes": 1024,
            },
        )

    monkeypatch.setattr(pilot.subprocess, "run", run)
    if timeout:
        with pytest.raises(subprocess.TimeoutExpired):
            pilot.controller(root)
        failed = pilot.u.read(root / "failure.json")
        assert failed["last_review_progress"]["completed"] == 1000
        assert pilot.u.read(root / "compare/failure.json")["status"] == "timed_out"
        assert not (root / "completion.json").exists()
    else:
        pilot.controller(root)
        result = pilot.u.read(root / "result.json")
        assert result["new_native_runs"] == result["new_cells_trajectories"] == 0
        assert result["new_reference_solves"] == 0
        assert result["reused_simulations"] == receipt
    assert calls == ["compare"]
    assert not any((root / phase).exists() for phase in pilot.SIMULATIONS)


def test_failed_review_phase_keeps_progress_and_completed_artifacts(tmp_path):
    progress = pilot.Progress(tmp_path)
    progress.run("good", lambda: {"passed": True}, artifact="good.json")

    def fail():
        raise ValueError("test failure")

    with pytest.raises(ValueError, match="test failure"):
        progress.run("bad", fail, artifact="bad.json")
    events = [json.loads(line) for line in progress.path.read_text().splitlines()]
    assert events[-1]["event"] == "phase_failed" and events[-1]["phase"] == "bad"
    completed = next(e for e in events if e["event"] == "phase_completed")
    assert completed["sha256"] == pilot.u.sha(tmp_path / "good.json")
    assert not (tmp_path / "bad.json").exists()


@pytest.mark.parametrize("count", [128000, 256000, 512000])
def test_refined_clock_requires_explicit_extent_and_matches_native_arithmetic(count):
    import clock_labels

    with pytest.raises(ValueError, match="extent"):
        clock_labels.labels(0.1, count)
    with pytest.raises(ValueError, match="extent"):
        clock_labels.labels(0.1, count, max_count=64000)
    np.testing.assert_array_equal(
        clock_labels.labels(0.1, count, max_count=count), np.linspace(0, 0.1, count)
    )
    with pytest.raises(ValueError, match="extent"):
        clock_labels.labels(0.1, 512001, max_count=512001)


@pytest.mark.parametrize("change", [None, "index", "bool", "dt", "count"])
@pytest.mark.parametrize("index", [1, 2])
def test_refined_native_capture_and_review_clocks_cannot_diverge(change, index):
    dt, count = pilot.DT / 2**index, 64000 * 2**index
    registration = dict(native_index=index, native_dt_s=dt, max_native_labels=count)
    if change == "index":
        registration["native_index"] = 3
    elif change == "bool":
        registration["native_index"] = True
    elif change == "dt":
        registration["native_dt_s"] = pilot.DT
    elif change == "count":
        registration["max_native_labels"] = 64000
    if change is None:
        assert pilot.native_controls(registration) == (index, dt, count)
    else:
        with pytest.raises(ValueError, match="native"):
            pilot.native_controls(registration)


@pytest.fixture(scope="module")
def completed_coarse_review():
    parent = Path("/mnt/workspaces/Cells/betse-long-pump-review-20260921-01")
    original, result, receipt = pilot.refinement_inputs(parent)
    pilot.unchanged_production(original, pilot.u.sources())
    return original, result, receipt


@pytest.mark.parametrize("failure", [None, "memory", "disk", "stream", "process_memory"])
def test_finer_resource_preflight_uses_saved_costs_and_refuses_overruns(
    completed_coarse_review, failure, monkeypatch
):
    original, result, receipt = copy.deepcopy(completed_coarse_review)
    available, free = 32 * 1024**3, 8 * 1024**3
    if failure == "memory":
        available = 4 * 1024**3
    elif failure == "disk":
        free = 4 * 1024**3
    elif failure == "stream":
        monkeypatch.setattr(pilot, "STREAM_BYTES", 256 * 1024**2)
    elif failure == "process_memory":
        result["phase_resources"]["compare"]["peak_rss_bytes"] = 16 * 1024**3
    if failure:
        with pytest.raises(ValueError, match="Refinement"):
            pilot.refinement_preflight(
                original, result, receipt, available_memory=available, free_disk=free
            )
    else:
        check = pilot.refinement_preflight(
            original, result, receipt, available_memory=available, free_disk=free
        )
        assert check["steps"] == 128000 and check["step_count_factor"] == 2
        assert check["projected_artifact_bytes"] <= pilot.ARTIFACT_BYTES
        assert check["scientific_tolerances_changed"] is False
        assert check["native_histories_retained"] is True


@pytest.mark.parametrize("change", [None, "poor_contraction", "floor", "wrong_clock"])
def test_adjacent_convergence_keeps_failed_closure_and_requires_another_level(
    completed_coarse_review, change
):
    original, previous, _ = copy.deepcopy(completed_coarse_review)
    current = copy.deepcopy(previous)
    current["native_dt_s"] /= 2
    for field in ("amount", "energy", "voltage", "energy_closure"):
        current["constraints"]["native/" + field]["max_error"] /= 2
    if change == "poor_contraction":
        current["constraints"]["native/amount"]["max_error"] = previous["constraints"][
            "native/amount"
        ]["max_error"]
    elif change == "floor":
        previous["constraints"]["native/amount"]["max_error"] = original["protocol"]["refinement"][
            "floor_amount_fmol"
        ]
    elif change == "wrong_clock":
        current["native_dt_s"] = previous["native_dt_s"]
    before = copy.deepcopy((current, previous))
    if change == "wrong_clock":
        with pytest.raises(ValueError, match="clock"):
            pilot.adjacent_refinement(current, previous, original["protocol"])
        return
    result = pilot.adjacent_refinement(current, previous, original["protocol"])
    assert result["adjacent_trajectory_contraction_pass"] is (change != "poor_contraction")
    assert result["energy_closure"]["observed_order"] == 1
    assert result["energy_closure"]["fine_within_limit"] is False
    assert result["energy_closure"]["unchanged_limit_pJ"] == 1e-7
    assert result["timestep_ladder_qualified"] is False
    assert (current, previous) == before


@pytest.mark.parametrize("parallel", [True, False])
def test_refinement_controller_runs_two_native_captures_and_reuses_cells(
    tmp_path, monkeypatch, parallel
):
    root, previous = tmp_path / "refine", tmp_path / "old"
    root.mkdir()
    pilot.u.write(
        root / "registration.json",
        {
            "workspace": str(tmp_path),
            "native_parallel": parallel,
            "refinement": {"simulation_parent": str(previous)},
            "phase_limits_seconds": {"observed": 10800, "unobserved": 9000, "compare": 21600},
        },
    )
    pilot.u.write(
        previous / "cells/completion.json", {"elapsed_seconds": 10, "peak_rss_bytes": 1000}
    )
    prior_hash = pilot.u.sha(previous / "cells/completion.json")
    calls = []

    def run(command, **options):
        phase = command[-1]
        calls.append(phase)
        assert phase != "cells"
        assert (
            options["timeout"] == {"observed": 10800, "unobserved": 9000, "compare": 21600}[phase]
        )
        if phase == "compare":
            assert (root / "observed/completion.json").exists()
            assert (root / "unobserved/completion.json").exists()
        pilot.u.write(root / phase / "result.json", {"status": "test_pass"})
        pilot.u.write(
            root / phase / "completion.json", {"elapsed_seconds": 1, "peak_rss_bytes": 10}
        )

    monkeypatch.setattr(pilot.subprocess, "run", run)
    if not parallel:

        def no_pool(*args, **kwargs):
            raise AssertionError("Serial capture must not open a concurrent executor")

        monkeypatch.setattr(pilot, "ThreadPoolExecutor", no_pool)
    pilot.controller(root)
    result = pilot.u.read(root / "result.json")
    assert set(calls[:2]) == {"observed", "unobserved"} and calls[2:] == ["compare"]
    assert result["new_native_runs"] == 2
    assert result["new_cells_trajectories"] == result["new_reference_solves"] == 0
    assert result["phase_completions_sha256"]["cells"] == prior_hash
    assert pilot.u.sha(previous / "cells/completion.json") == prior_hash
    assert not (root / "cells").exists()
    if not parallel:
        assert calls == ["observed", "unobserved", "compare"]


def test_refinement_selects_matching_saved_prefix(completed_coarse_review):
    original, _, _ = completed_coarse_review
    directory = Path(original["parent"]) / "native/pump_leak/1"
    expected = pilot.u.authenticate_stage(directory)
    registration = dict(
        original, native_prefix={"path": str(directory), "completion_sha256": expected}
    )
    assert pilot.prefix_input(registration) == (directory, expected)
    assert pilot.prefix_input(original)[0].name == "0"


@pytest.fixture(scope="module")
def completed_half_step():
    parent = Path("/mnt/workspaces/Cells/betse-long-pump-half-step-20260921-01")
    original, result, receipt = pilot.refinement_inputs(parent)
    assert result["native_steps_per_run"] == 128000
    assert result["failed_numeric_limits"] == ["native/energy_closure"]
    assert receipt["simulation_parent"] != receipt["path"]
    return original, result, receipt


def test_refinement_authentication_rejects_a_non_decreasing_ancestor(completed_half_step):
    _, _, receipt = completed_half_step
    with pytest.raises(ValueError, match="parent clock index"):
        pilot.refinement_inputs(Path(receipt["path"]), expected_index=0)


def test_quarter_step_uses_latest_native_costs_and_serializes_to_fit(completed_half_step):
    original, result, receipt = completed_half_step
    check = pilot.refinement_preflight(
        original, result, receipt, available_memory=25 * 1024**3, free_disk=12 * 1024**3
    )
    assert check["steps"] == 256000 and check["dt_s"] == pilot.DT / 4
    assert check["native_cost_source"] == receipt["path"]
    assert check["native_parallel"] is False
    assert check["projected_parallel_native_peak_rss_bytes"] > 25 * 1024**3
    assert check["projected_concurrent_peak_rss_bytes"] + 4 * 1024**3 < 25 * 1024**3
    assert check["projected_seconds"] == 2 * sum(
        result["phase_resources"][p]["elapsed_seconds"]
        for p in ("observed", "unobserved", "compare")
    )
    assert check["native_stream_bytes"] == 1024**3 and check["artifact_bytes"] == 4 * 1024**3
    directory = Path(original["parent"]) / "native/pump_leak/2"
    assert pilot.u.authenticate_stage(directory)


@pytest.mark.parametrize("field", ["native_stream_bytes", "artifact_bytes"])
@pytest.mark.parametrize("value", [True, 0, 8 * 1024**3])
def test_recording_allowances_cannot_be_unbounded(field, value):
    with pytest.raises(ValueError, match="allowance"):
        pilot.recording_limits({field: value})


def test_large_pickle_requires_explicit_allowance_and_keeps_file_guard(tmp_path):
    artifact = tmp_path / "native-pickle"
    with artifact.open("wb") as handle:
        handle.truncate(512 * 1024**2 + 1)
    with pytest.raises(ValueError, match="per-file"):
        pilot.budget(tmp_path)
    pilot.u.write(
        tmp_path / "registration.json",
        {"native_stream_bytes": 1024**3, "artifact_bytes": 4 * 1024**3},
    )
    assert pilot.budget(tmp_path) > 512 * 1024**2
    with artifact.open("wb") as handle:
        handle.truncate(1024**3 + 1)
    with pytest.raises(ValueError, match="per-file"):
        pilot.budget(tmp_path)


@pytest.mark.parametrize("change", [None, "energy_miss", "earlier_contraction", "clock_gap"])
def test_three_levels_require_both_contractions_and_all_finest_limits(completed_half_step, change):
    original, previous, _ = copy.deepcopy(completed_half_step)
    current = copy.deepcopy(previous)
    current["native_dt_s"] /= 2
    current["failed_numeric_limits"] = []
    for field in ("amount", "energy", "voltage", "energy_closure"):
        current["constraints"]["native/" + field]["max_error"] /= 4
        current["constraints"]["native/" + field]["failures"] = 0
    if change == "energy_miss":
        current["failed_numeric_limits"] = ["native/energy_closure"]
        current["constraints"]["native/energy_closure"]["max_error"] = 1.1e-7
        current["constraints"]["native/energy_closure"]["failures"] = 1
    elif change == "earlier_contraction":
        previous["adjacent_refinement"]["adjacent_trajectory_contraction_pass"] = False
    elif change == "clock_gap":
        previous["adjacent_refinement"]["dt_s"][-1] /= 2
    if change == "clock_gap":
        with pytest.raises(ValueError, match="Nonconsecutive"):
            pilot.refinement_ladder(current, previous, original["protocol"])
        return
    result = pilot.refinement_ladder(current, previous, original["protocol"])
    assert result["levels"] == 3 and result["available_successive_contractions"] == 2
    assert result["timestep_ladder_qualified"] is (change is None)
    assert result["scientific_tolerances_changed"] is False
    assert result["pairs"][-1]["energy_closure"]["unchanged_limit_pJ"] == 1e-7


@pytest.mark.parametrize("failure", [None, "memory", "disk"])
def test_phase_resource_reserve_is_rechecked_and_durably_recorded(
    tmp_path, monkeypatch, completed_half_step, failure
):
    original, result, receipt = completed_half_step
    check = pilot.refinement_preflight(
        original, result, receipt, available_memory=25 * 1024**3, free_disk=12 * 1024**3
    )
    monkeypatch.setattr(
        pilot, "available_memory", lambda: (4 if failure == "memory" else 25) * 1024**3
    )
    monkeypatch.setattr(
        pilot.shutil,
        "disk_usage",
        lambda _: pilot.SimpleNamespace(free=(4 if failure == "disk" else 12) * 1024**3),
    )
    if failure:
        with pytest.raises(ValueError, match="phase memory/disk"):
            pilot.phase_resource_check(tmp_path, {"resource_preflight": check}, ("observed",))
    else:
        pilot.phase_resource_check(tmp_path, {"resource_preflight": check}, ("observed",))
    saved = pilot.u.read(tmp_path / "observed-resource-check.json")
    assert saved["passed"] is (failure is None)
    assert saved["phases"] == ["observed"]
