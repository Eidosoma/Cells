"""Observer isolation, process accounting and exact diagnostic replay guards."""

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from cells.ensemble import families
from validation.ensemble import profile_cluster as profile


def test_process_sample_handles_command_parentheses_and_thread_children(tmp_path):
    proc = tmp_path / "23"
    (proc / "task/23").mkdir(parents=True)
    (proc / "task/24").mkdir()
    fields = ["0"] * 40
    fields[0] = "R"
    fields[11], fields[12], fields[19] = "200", "300", "10000"
    (proc / "stat").write_text("23 (test ) process) " + " ".join(fields))
    (proc / "status").write_text("VmRSS:\t120 kB\nVmHWM:\t240 kB\n")
    (proc / "task/23/children").write_text("50 51")
    (proc / "task/24/children").write_text("51 52")
    row = profile.process_sample(23, tmp_path)
    assert row["start_ticks"] == 10000
    assert row["cpu_seconds"] == 500 / profile.os.sysconf("SC_CLK_TCK")
    assert row["rss_bytes"] == 120 * 1024 and row["hwm_bytes"] == 240 * 1024
    assert row["children"] == [50, 51, 52]


def test_process_tree_counts_processes_once_and_accepts_exited_children(monkeypatch):
    def sample(pid):
        if pid == 4:
            raise FileNotFoundError
        return {"pid": pid, "children": {1: [2, 3, 4], 2: [3], 3: []}[pid]}

    monkeypatch.setattr(profile, "process_sample", sample)
    assert sorted(row["pid"] for row in profile.process_tree(1)) == [1, 2, 3]


@pytest.mark.parametrize("interrupted", [False, True])
def test_trace_is_bounded_to_warm_windows(tmp_path, interrupted):
    profiler = Mock()
    trace = profile.WindowTrace(tmp_path / "trace", profiler)
    trace.observe(1)
    profiler.start_trace.assert_not_called()
    trace.observe(2)
    profiler.start_trace.assert_called_once()
    options = profiler.start_trace.call_args.kwargs["profiler_options"]
    assert options.python_tracer_level == 0 and options.host_tracer_level == 1
    assert options.enable_hlo_proto is False
    trace.observe(3)
    profiler.stop_trace.assert_not_called()
    if not interrupted:
        trace.observe(4)
    trace.close()
    profiler.stop_trace.assert_called_once()
    assert profile.cli.read(tmp_path / "trace/finished.json")["status"] == (
        "interrupted" if interrupted else "captured"
    )


@pytest.mark.parametrize("phase", ["start_trace", "stop_trace"])
def test_profiler_error_is_preserved_and_not_retried(tmp_path, phase):
    profiler = Mock()
    getattr(profiler, phase).side_effect = RuntimeError("profiler unavailable")
    trace = profile.WindowTrace(tmp_path / "trace", profiler)
    for window in range(1, 8):
        trace.observe(window)
    trace.close()
    assert trace.failed
    assert "profiler unavailable" in profile.cli.read(tmp_path / "trace/failure.json")["traceback"]
    getattr(profiler, phase).assert_called_once()


@pytest.mark.parametrize("change", ["none", "signed_zero", "dtype", "shape", "missing"])
def test_checkpoint_comparison_preserves_bits_and_every_field(tmp_path, change):
    left = {"ionic": np.array([0.0, 3.0]), "pending_event": np.array([3], np.uint32)}
    right = {key: value.copy() for key, value in left.items()}
    if change == "signed_zero":
        right["ionic"][0] = -0.0
    elif change == "dtype":
        right["pending_event"] = right["pending_event"].astype(np.int32)
    elif change == "shape":
        right["ionic"] = right["ionic"].reshape(1, 2)
    elif change == "missing":
        right.pop("pending_event")
    np.savez(tmp_path / "left.npz", **left)
    np.savez(tmp_path / "right.npz", **right)
    if change == "none":
        assert profile.compare_states(tmp_path / "left.npz", tmp_path / "right.npz") == 3
    else:
        with pytest.raises(ValueError, match="Checkpoint"):
            profile.compare_states(tmp_path / "left.npz", tmp_path / "right.npz")


@pytest.mark.parametrize("trace_enabled", [False, True])
def test_observer_forwards_state_callbacks_and_complete_worker(
    monkeypatch, tmp_path, trace_enabled
):
    import jax.profiler

    monkeypatch.setattr(jax.profiler, "start_trace", Mock())
    monkeypatch.setattr(jax.profiler, "stop_trace", Mock())
    calls, callbacks = [], []
    state, final, result, detail = object(), object(), object(), object()
    load, save = object(), object()

    def run(spec, *, backend, state, callback):
        calls.append((spec, backend, state))
        for window in range(1, 6):
            callback(window, final, detail)
        return final, result

    def runtime(spec):
        return run, load, save

    monkeypatch.setattr(families, "runtime_for", runtime)

    def worker(*args):
        for width, first in [(16, 0), (32, 64), (16, 16)]:
            spec = SimpleNamespace(pool=SimpleNamespace(worlds=width, world_id_start=first))
            wrapped, loader, saver = families.runtime_for(spec)
            assert loader is load and saver is save
            got = wrapped(
                spec, backend="gpu", state=state, callback=lambda *values: callbacks.append(values)
            )
            assert got == (final, result)

    monkeypatch.setattr(profile, "ordinary_worker", worker)
    profile.profile_worker(
        str(tmp_path), 0, {}, [4, 5], None, None, {}, trace_enabled=trace_enabled
    )
    assert families.runtime_for is runtime
    assert len(calls) == 3 and all(b == "gpu" and s is state for _, b, s in calls)
    assert callbacks == [(i, final, detail) for _ in range(3) for i in range(1, 6)]
    assert (
        jax.profiler.start_trace.call_count
        == jax.profiler.stop_trace.call_count
        == (2 if trace_enabled else 0)
    )
    assert len(list((tmp_path / "worker-0-profile").glob("windows-*.jsonl"))) == 3


@pytest.mark.parametrize(
    "mode,hardware", [("trace", False), ("throughput", False), ("throughput", True)]
)
def test_controller_installs_observer_and_preserves_campaign_failure(
    monkeypatch, tmp_path, mode, hardware
):
    from cells.ensemble import worker as worker_module

    parent = tmp_path / "parent"
    parent.mkdir()
    profile.cli.write(parent / "result.json", {})
    definition = {
        "execution": {"workers_per_gpu": 1, "worker_threads": 2, "max_wall_seconds": 3600}
    }
    profile.cli.write(tmp_path / "definition.json", definition)
    profile.cli.write(
        tmp_path / "profile-registration.json",
        {
            "driver_sha256": profile.cli.sha(profile.Path(profile.__file__)),
            "parent": str(parent),
            "parent_result_sha256": profile.cli.sha(parent / "result.json"),
            "definition_sha256": profile.cli.sha(tmp_path / "definition.json"),
            "sources_sha256": {},
            "mode": mode,
            "gpu_counters": {"configured": True} if hardware else None,
            "memory_limits": {
                "tree_rss_bytes": 16 * 1024**3,
                "available_memory_bytes": 4 * 1024**3,
            },
        },
    )
    monkeypatch.setattr(profile, "authenticate_parent", lambda _: ({}, {"definition": definition}))
    monkeypatch.setattr(profile.cli, "sources", lambda: {})
    counter_monitor = Mock()
    monkeypatch.setattr(profile.gpu_counters, "CounterMonitor", lambda *args: counter_monitor)

    def register(args):
        if mode == "trace":
            assert worker_module.worker is profile.profile_worker
        else:
            assert worker_module.worker.func is profile.profile_worker
            assert worker_module.worker.keywords == {"trace_enabled": False}
        assert args.detach is False and args.allocated_gpus == 1
        return {"status": "failed"}

    monkeypatch.setattr(profile.cli, "register", register)
    with pytest.raises(ValueError, match="campaign did not complete"):
        profile.execute(tmp_path)
    assert worker_module.worker is profile.ordinary_worker
    assert (tmp_path / "failure.json").exists() and not (tmp_path / "completion.json").exists()
    if hardware:
        counter_monitor.start.assert_called_once()
        counter_monitor.finish.assert_called()
    else:
        counter_monitor.start.assert_not_called()


@pytest.mark.parametrize("violation", ["rss", "reserve"])
def test_memory_guard_defers_until_handler_and_requests_pause_once(
    monkeypatch, tmp_path, violation
):
    limits = {"tree_rss_bytes": 100, "available_memory_bytes": 50}
    monitor = profile.ResourceMonitor(tmp_path, limits=limits)
    kill = Mock()
    monkeypatch.setattr(profile.os, "kill", kill)
    monkeypatch.setattr(profile.signal, "getsignal", lambda _: profile.signal.SIG_DFL)
    safe = {"time": 1, "tree_rss_bytes": 100, "available_memory_bytes": 50}
    monitor.inspect(safe)
    assert monitor.violation is None
    sample = safe | (
        {"tree_rss_bytes": 101} if violation == "rss" else {"available_memory_bytes": 49}
    )
    monitor.inspect(sample)
    assert monitor.violation and (tmp_path / "memory-stop.json").exists()
    kill.assert_not_called()
    monkeypatch.setattr(profile.signal, "getsignal", lambda _: lambda *args: None)
    # A previous breach stays recorded even after pressure subsides.
    monitor.inspect(safe)
    monitor.inspect(sample)
    kill.assert_called_once_with(profile.os.getpid(), profile.signal.SIGUSR1)
    assert (tmp_path / "memory-pause-requested.json").exists()


def test_failed_resource_sampling_requests_pause(monkeypatch, tmp_path):
    monitor = profile.ResourceMonitor(tmp_path, limits={"tree_rss_bytes": 100})
    monkeypatch.setattr(profile, "process_tree", Mock(side_effect=OSError("proc read failed")))
    monkeypatch.setattr(profile.signal, "getsignal", lambda _: lambda *args: None)
    kill = Mock()
    monkeypatch.setattr(profile.os, "kill", kill)
    monitor.record()
    assert "proc read failed" in monitor.error
    assert monitor.violation["reasons"] == ["resource_sampler_failed"]
    kill.assert_called_once()


@pytest.mark.parametrize("change", ["resources", "physics", "seed", "target", "output"])
def test_workload_comparison_allows_only_registered_resource_changes(change):
    import copy

    original = {
        "seed": 12,
        "arms": [{"rate": 1}],
        "execution": {
            "workers_per_gpu": 1,
            "worker_threads": 2,
            "max_wall_seconds": 3600,
            "target_gpu_utilization_pct": 70,
            "max_output_bytes": 1000,
        },
    }
    modified = copy.deepcopy(original)
    modified["execution"].update(workers_per_gpu=2, worker_threads=1, max_wall_seconds=1800)
    if change == "physics":
        modified["arms"][0]["rate"] = 2
    elif change == "seed":
        modified["seed"] += 1
    elif change == "target":
        modified["execution"]["target_gpu_utilization_pct"] = 50
    elif change == "output":
        modified["execution"]["max_output_bytes"] = 500
    if change == "resources":
        profile.same_workload(modified, original)
    else:
        with pytest.raises(ValueError, match="scientific workload"):
            profile.same_workload(modified, original)


@pytest.mark.parametrize("interrupted", [False, True])
def test_candidate_lifetime_preserves_callbacks_codecs_and_pause_provenance(
    monkeypatch, tmp_path, interrupted
):
    from contextlib import contextmanager

    from cells.ensemble.worker import PauseRequested

    binding = {
        "variant": "tested",
        "tile_width": 32,
        "result_sha256": "receipt",
        "helpers_sha256": {"kernel.py": "qualified"},
    }
    events, callbacks = [], []
    final, loaded = object(), object()
    parent = {"path": "previous-checkpoint", "sha256": "previous-manifest"}
    saved = []

    @contextmanager
    def context(selected):
        assert selected == binding
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    def run(spec, *, backend, state, callback):
        assert events == ["enter"] and backend == "gpu" and state is loaded
        callback(1, final, None)
        return final, {"status": "completed"}

    def save(path, spec, state, *, execution, provenance):
        assert state is final and provenance is parent
        assert execution == {"backend": "gpu", "experimental_candidate": binding}
        saved.append(path.name)
        return "saved-manifest"

    loader = object()
    runtime = lambda spec: (run, loader, save)  # noqa: E731
    monkeypatch.setattr(families, "runtime_for", runtime)
    monkeypatch.setattr(profile, "candidate_context", context)

    def worker(*args):
        for first in (0, 16):
            spec = SimpleNamespace(pool=SimpleNamespace(worlds=16, world_id_start=first))
            observed, got_loader, saver = families.runtime_for(spec)
            assert got_loader is loader

            def record(*values, first=first):
                callbacks.append(values)
                if interrupted and first == 16:
                    raise PauseRequested()

            try:
                state, report = observed(spec, backend="gpu", state=loaded, callback=record)
                assert state is final and report["experimental_candidate"] == binding
            except PauseRequested:
                saver(
                    tmp_path / "checkpoint-paused",
                    spec,
                    final,
                    execution={"backend": "gpu"},
                    provenance=parent,
                )
                raise
            assert (
                saver(
                    tmp_path / "checkpoint",
                    spec,
                    final,
                    execution={"backend": "gpu"},
                    provenance=parent,
                )
                == "saved-manifest"
            )

    monkeypatch.setattr(profile, "ordinary_worker", worker)
    call = lambda: profile.profile_worker(  # noqa: E731
        str(tmp_path),
        0,
        {},
        [4],
        None,
        None,
        {},
        trace_enabled=False,
        experimental_candidate=binding,
    )
    if interrupted:
        with pytest.raises(PauseRequested):
            call()
    else:
        call()
    assert events == ["enter", "exit"]  # Reused for both tasks, including on failure.
    assert families.runtime_for is runtime
    assert callbacks == [(1, final, None), (1, final, None)]
    assert saved == ["checkpoint", "checkpoint-paused" if interrupted else "checkpoint"]


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "mode",
        "eligibility",
        "numerical",
        "helper",
        "evidence",
        "physics",
        "width",
    ],
)
@pytest.mark.parametrize("width", [32, 64])
def test_candidate_requires_passing_unchanged_qualification(monkeypatch, tmp_path, change, width):
    from validation.ensemble.test_parallel_cluster import physical_spec

    parallel, helpers = profile.candidate_helpers()
    variant = parallel.ENERGY_SCREEN_VARIANT
    spec = parallel.rebound(physical_spec(), worlds=65, first=0)
    task = parallel.rebound(spec, worlds=16, first=80).to_dict()
    record = {
        "mode": "energy_gpu_screen",
        "variants": [variant],
        "tile_width_by_backend": {"gpu": width},
        "execution_policy_by_backend": {"gpu": variant},
        "drivers_sha256": {name: profile.cli.sha(path) for name, path in helpers.items()},
        "production_sources_sha256": {},
        "definition": spec.to_dict(),
    }
    (tmp_path / "evidence").write_text("checked states")
    result = {
        "status": "completed",
        "mode": "energy_gpu_screen",
        "variants": {
            variant: {
                "bounded_numerical_checks_pass": True,
                "eligible_for_performance_measurement": True,
                "candidate_backends": ["gpu"],
            }
        },
        "evidence_sha256": {"evidence": profile.cli.sha(tmp_path / "evidence")},
    }
    if change == "mode":
        record["mode"] = "energy_steps"
    elif change == "eligibility":
        result["variants"][variant]["eligible_for_performance_measurement"] = False
    elif change == "numerical":
        result["variants"][variant]["bounded_numerical_checks_pass"] = False
    elif change == "helper":
        record["drivers_sha256"]["step_cluster.py"] = "changed"
    elif change == "evidence":
        (tmp_path / "evidence").write_text("changed")
    elif change == "physics":
        task["window_ticks"] += 1
    elif change == "width":
        record["tile_width_by_backend"]["gpu"] = 128
    profile.cli.write(tmp_path / "registration.json", record)
    result["registration_sha256"] = profile.cli.sha(tmp_path / "registration.json")
    profile.cli.write(tmp_path / "result.json", result)
    profile.cli.write(
        tmp_path / "completion.json",
        {
            "status": "completed",
            "result_sha256": profile.cli.sha(tmp_path / "result.json"),
        },
    )
    monkeypatch.setattr(parallel, "authenticate", lambda path: record)
    registration = {"plan": {"tasks": [{"definition": task}]}}
    if change == "none":
        got = profile.authenticate_candidate(tmp_path, registration)
        assert got["variant"] == variant and got["qualified_trajectory_worlds"] == 65
        assert got["tile_width"] == width
    else:
        with pytest.raises(ValueError):
            profile.authenticate_candidate(tmp_path, registration)


@pytest.mark.parametrize("change", ["none", "device", "fields", "period", "coverage", "candidate"])
def test_counter_baseline_requires_matching_scalar_observations(tmp_path, change):
    counters = {
        "tool_sha256": {"library": "identity"},
        "driver_sha256": "sampler",
        "uuid": "L4",
        "field_ids": profile.gpu_counters.FIELDS,
        "period_seconds": 1.0,
        "minimum_coverage_fraction": 0.98,
    }
    record = {"mode": "throughput", "gpu_counters": counters}
    if change == "candidate":
        record["experimental_candidate"] = {"variant": "other"}
    parent = tmp_path / "campaign"
    parent.mkdir()
    profile.cli.write(parent / "result.json", {"status": "completed"})
    profile.cli.write(tmp_path / "profile-registration.json", record)
    profile.cli.write(
        tmp_path / "result.json",
        {
            "status": "completed",
            "profile_registration_sha256": profile.cli.sha(tmp_path / "profile-registration.json"),
            "campaign_result_sha256": profile.cli.sha(parent / "result.json"),
            "all_checkpoint_fields_bitwise_equal_to_parent": True,
            "evidence_sha256": {},
            "gpu_hardware_counters": {
                interval: {"coverage_pass": change != "coverage"}
                for interval in ("whole_job", "after_all_workers_warmed")
            },
        },
    )
    profile.cli.write(
        tmp_path / "completion.json",
        {
            "status": "completed",
            "result_sha256": profile.cli.sha(tmp_path / "result.json"),
        },
    )
    if change == "device":
        counters["uuid"] = "different-GPU"
    elif change == "fields":
        counters["field_ids"] = {1002: "sm_active"}
    elif change == "period":
        counters["period_seconds"] = 2.0
    if change == "none":
        assert profile.authenticate_counter_baseline(parent, counters)["path"] == str(tmp_path)
    else:
        with pytest.raises(ValueError):
            profile.authenticate_counter_baseline(parent, counters)
