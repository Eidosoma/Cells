"""Boundary replay, exact bytes, failure safety and detached orchestration checks."""

import copy
import dis
import gc
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_context as ctx  # noqa: E402
import live_job as job  # noqa: E402
import live_observer as observer  # noqa: E402
import record_codec as codec  # noqa: E402
from stream_compare import compare  # noqa: E402

SHORT = ctx.ROOT / "runs/ref-005b-pump-loop-2026-09-16/capture-01/betse.json"
VARIANTS = ("pump_leak", "pump_only", "leak_only", "all_blocked", "half_density", "closed_boundary")


@pytest.fixture(scope="module")
def rows():
    return ctx.read(SHORT)["rows"]


def frame(name, source, obj=None, parent=None, **locals_):
    return NS(
        f_code=NS(
            co_name=name, co_filename=str(source), co_code=bytes([dis.opmap["RETURN_VALUE"]])
        ),
        f_lasti=0,
        f_back=parent,
        f_locals=dict(self=obj, **locals_),
    )


def make(row, trace, sink):
    snapshots = []
    if row["mode"] == "observed":
        snapshots.append(trace["initial"])
        for step, raw in zip(trace["steps"], trace["raw_steps"], strict=True):
            snapshots.extend(
                [
                    raw["before"],
                    step["before"],
                    step["before_ordinary"],
                    step["after_ordinary"],
                    step["after_voltage"],
                ]
            )
    snapshots = iter(snapshots)
    sim = NS(
        molecules=None,
        movingIons=row["moving_ions"],
        mdl=row["geometry"]["membrane_count"],
        **{name: [] for name in observer.HISTORY_SOURCE},
    )
    phase = NS(sim=sim, p=NS(dt=row["dt_s"], init_tsteps=row["steps"], grn_enabled=False))
    header = next(observer.layout.records(row))

    def entry(initial):
        if row["mode"] == "observed":
            assert codec.canonical(initial) == codec.canonical(header["trace"]["initial"])
        return header

    o = observer.StreamObserver(
        phase,
        "/science",
        lambda sim: next(snapshots),
        entry,
        sink,
        observed=row["mode"] == "observed",
    )
    for name in ("run_sim_core", "init_dynamics", "clear_storage", "update_V"):
        o.observe(frame(name, o.sim_file, sim), "call", None)
    loop = frame(
        "_run_sim_core_loop",
        o.sim_file,
        sim,
        time_steps=trace["labels_s"],
        time_steps_sampled=set(trace["labels_s"][1:]),
    )
    o.observe(loop, "call", None)
    return o, sim, loop


def replay(row, trace, directory, *, mutate=None, wrapped=False):
    with codec.RecordSink(directory, max_output_bytes=32 * 1024**2) as sink:
        o, sim, loop = make(row, trace, sink)
        for i, step in enumerate(trace["steps"]):
            loop.f_locals["t"] = step["raw_label_s"]
            if o.observed:
                for call in trace["raw_steps"][i]["calls"]:
                    loop.f_locals["i"] = call.get("species_index")
                    f = frame(call["function"], o.toolbox, parent=loop, **call["inputs"])
                    o.observe(f, "call", None)
                    o.observe(f, "return", call["returned"])
            parent = (
                frame("update_all_concs", "<pinned type-check wrapper>", parent=loop)
                if wrapped
                else loop
            )
            update = frame("update_all_concs", o.sim_file, sim, parent)
            o.observe(update, "call", None)
            o.observe(update, "return", None)
            o.observe(frame("update_V", o.sim_file, sim, loop), "return", None)
            if i:
                for name in observer.HISTORY_SOURCE:
                    getattr(sim, name).append(
                        copy.deepcopy(row["histories"][name]["values"][i - 1])
                    )
                o.observe(
                    frame("write2storage", o.sim_file, sim, loop, t=step["raw_label_s"]),
                    "return",
                    None,
                )
            assert o.pending is o.raw is o.inflight is None
            assert not any(
                hasattr(o, name)
                for name in ("steps", "raw_steps", "labels", "storage", "sampled_indices")
            )
        o.observe(loop, "return", None)
        o.observe(frame("run_sim_core", o.sim_file, sim), "return", None)
        if mutate:
            mutate(o, sim)
        footer = {name: row[name] for name in observer.layout.ROW_LATE}
        o.finish(footer)
        assert o.peak_pending_updates == 1
        assert o.updates == row["steps"] and o.samples == row["steps"] - 1
    return o


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("mode", ("observed", "unobserved"))
def test_saved_real_boundary_replay_exact(rows, tmp_path, variant, mode):
    from codec_review import inspect

    row = rows[variant + "/" + mode]
    replay(row, rows[variant + "/observed"]["trace"], tmp_path / "stream")
    report = inspect(row, tmp_path / "stream")
    assert report["exact_scalar_comparisons"] == report["original_scalar_values"] > 0


@pytest.mark.parametrize("variant", VARIANTS)
def test_storage_only_and_full_observer_pairs(rows, tmp_path, variant):
    for mode in ("observed", "unobserved"):
        replay(rows[variant + "/" + mode], rows[variant + "/observed"]["trace"], tmp_path / mode)
    assert (
        compare(tmp_path / "observed", tmp_path / "unobserved", common=True)["failed_comparisons"]
        == 0
    )


@pytest.mark.parametrize("field", ("pending", "raw", "inflight"))
def test_incomplete_groups_never_publish(rows, tmp_path, field):
    row = rows["pump_leak/observed"]
    with pytest.raises(ValueError, match="Incomplete live"):
        replay(row, row["trace"], tmp_path / "stream", mutate=lambda o, sim: setattr(o, field, {}))
    assert not (tmp_path / "stream/manifest.json").exists()


@pytest.mark.parametrize("history", sorted(observer.HISTORY_SOURCE))
def test_native_histories_not_silently_mutated(rows, tmp_path, history):
    row = rows["pump_leak/observed"]

    def mutate(o, sim):
        values = getattr(sim, history)
        values.pop()

    with pytest.raises(ValueError, match="Terminal history extent"):
        replay(row, row["trace"], tmp_path / "stream", mutate=mutate)
    assert not (tmp_path / "stream/manifest.json").exists()


def test_reused_footer_refused(rows, tmp_path):
    row = rows["pump_leak/observed"]
    o = replay(row, row["trace"], tmp_path / "stream")
    with pytest.raises(ValueError, match="reused footer"):
        o.finish({})


def test_exception_unwind_not_a_success():
    f = frame("example", "/science/sim.py")
    assert observer.successful_return(f)
    f.f_code.co_code = bytes([dis.opmap["RAISE_VARARGS"]])
    assert not observer.successful_return(f)


@pytest.mark.parametrize("value", (0.0, -0.0, 6.25e-6, 1.0000000000000002, 1e-300))
def test_native_float_subclasses_keep_json_bits(value):
    import numpy as np

    class Scalar(float):
        pass

    original = dict(value=(Scalar(value), np.float64(value)), flag=True, integer=2)
    assert codec.canonical(observer.json_tree(original)) == codec.canonical(
        json.loads(json.dumps(original, allow_nan=False))
    )


@pytest.mark.parametrize("value", (object(), {1: 2}, float("nan"), float("inf")))
def test_unsupported_native_metadata_refused(value):
    with pytest.raises(ValueError):
        observer.json_tree(value)


def test_source_instance_and_direct_parent_scoping(rows, tmp_path):
    row = rows["pump_leak/observed"]
    with codec.RecordSink(tmp_path / "stream") as sink:
        o, sim, loop = make(row, row["trace"], sink)
        for f in (
            frame("electroflux", "/different/sim_toolbox.py", parent=loop),
            frame("electroflux", o.toolbox, parent=NS()),
            frame("update_all_concs", o.sim_file, NS(), loop),
        ):
            o.observe(f, "call", None)
        assert o.raw is None and o.pending is None


def test_source_owned_boundary_inside_type_check_wrapper(rows, tmp_path):
    from codec_review import inspect

    row = rows["pump_leak/observed"]
    replay(row, row["trace"], tmp_path / "stream", wrapped=True)
    assert inspect(row, tmp_path / "stream")["status"] == "exact_every_original_value"


@pytest.mark.parametrize(
    "kind", ("duplicate_setup", "early_storage", "missing_voltage", "repeat_loop", "unpaired_call")
)
def test_bad_lifecycle_refused(rows, tmp_path, kind):
    row = rows["pump_leak/observed"]
    with codec.RecordSink(tmp_path / "stream") as sink:
        o, sim, loop = make(row, row["trace"], sink)
        with pytest.raises(ValueError):
            if kind == "duplicate_setup":
                o.observe(frame("clear_storage", o.sim_file, sim), "call", None)
            elif kind == "early_storage":
                o.stored(0.0)
            elif kind == "missing_voltage":
                o.flush_step(None)
            elif kind == "repeat_loop":
                o.enter_loop(loop)
            else:
                o.raw_call(frame("electroflux", o.toolbox, parent=loop), "return", [])


def test_pending_buffers_release_with_gc_disabled(rows, tmp_path):
    import weakref

    row = rows["pump_leak/observed"]
    gc.collect()
    enabled = gc.isenabled()
    gc.disable()
    try:
        refs = []
        for i in range(8):
            o = replay(row, row["trace"], tmp_path / str(i))
            refs.append(weakref.ref(o))
            del o
        assert all(ref() is None for ref in refs)
    finally:
        if enabled:
            gc.enable()


@pytest.mark.parametrize("change", ("sign", "dtype", "shape", "nan"))
def test_cells_exact_array_guard(change):
    import numpy as np
    from matched_windows import Arrays

    base = np.array([0.0, 1.0], dtype=np.float64)
    other = dict(
        sign=np.array([-0.0, 1.0]),
        dtype=base.astype(np.float32),
        shape=base.reshape(1, 2),
        nan=np.array([float("nan"), 1.0]),
    )[change]
    with pytest.raises(ValueError):
        Arrays().match(other, base, "fixture")


def test_detached_launch_binding_no_wait(monkeypatch, tmp_path):
    monkeypatch.setattr(job, "register", lambda *a: None)
    ctx.write(tmp_path / "registration.json", {})
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return NS(pid=123)

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    ack = job.launch(tmp_path, tmp_path / "tests.xml")
    assert ack["pid"] == 123 and not ack["automatic_polling"]
    command, kwargs = calls[0]
    assert command[-2:] == ["--registration-sha", ctx.sha(tmp_path / "registration.json")]
    assert kwargs["start_new_session"] and kwargs["stdin"] == subprocess.DEVNULL


def test_failure_is_terminal_no_worker_or_retry(monkeypatch, tmp_path):
    monkeypatch.setattr(job, "authenticate", lambda *a: (_ for _ in ()).throw(ValueError("guard")))
    with pytest.raises(ValueError, match="guard"):
        job.execute(tmp_path, "invalid")
    assert not ctx.read(tmp_path / "failure.json")["automatic_retry"]
    with pytest.raises(ValueError, match="already attempted"):
        job.execute(tmp_path, "invalid")
    assert not (tmp_path / "completion.json").exists()


def test_changed_registration_refused(tmp_path):
    ctx.write(tmp_path / "registration.json", {})
    with pytest.raises(ValueError, match="Launch-bound"):
        job.authenticate(tmp_path, "0" * 64)


@pytest.mark.parametrize(
    "changed", ("native_runs", "observed_updates", "history_samples", "records", "observer_pairs")
)
def test_native_matrix_coverage_refused(changed):
    result = dict(
        status="live_overlap_pass_pending_independent_review",
        native_runs=36,
        observed_updates=6720,
        history_samples=13404,
        native_memory_bounded=False,
        records={"row": dict(overlap=dict(failed_comparisons=0, exact_scalars=1))},
        observer_pairs=[dict(failed_comparisons=0)] * 18,
    )
    if changed == "records":
        result[changed] = {}
    elif changed == "observer_pairs":
        result[changed].pop()
    else:
        result[changed] -= 1
    with pytest.raises(ValueError, match="Native matrix"):
        job.gate("native", result, dict(native_labels=["row"]))


@pytest.mark.parametrize(
    "changed",
    (
        "full_trajectories",
        "window_runs",
        "disk_recordings",
        "restart_suffixes",
        "restart_window_runs",
        "zero_length_runs",
        "sparse_schedule_controls",
    ),
)
def test_cells_matrix_coverage_refused(changed):
    result = dict(
        status="matched_windows_pass_pending_independent_review",
        full_trajectories=24,
        window_runs=72,
        disk_recordings=18,
        restart_suffixes=6,
        restart_window_runs=6,
        zero_length_runs=6,
        sparse_schedule_controls=2,
        records={"row": dict(windows=72, recordings=18, restarts=6)},
    )
    result[changed] -= 1
    with pytest.raises(ValueError, match="Cells coverage"):
        job.gate("cells", result, dict(cells_keys=["row"]))


def test_comparator_checks_terminal_and_exact_mismatch(tmp_path):
    for name, value in (("a", 0.0), ("b", -0.0)):
        with codec.RecordSink(tmp_path / name, max_output_bytes=32 * 1024**2) as sink:
            sink.append(dict(kind="fixture", value=value))
            sink.finish()
    with pytest.raises(ValueError, match="float64 bits"):
        compare(tmp_path / "a", tmp_path / "b")
    with codec.RecordSink(tmp_path / "unfinished") as sink:
        sink.append(dict(kind="fixture", value=0.0))
    with pytest.raises((ValueError, FileNotFoundError)):
        compare(tmp_path / "a", tmp_path / "unfinished")


def test_output_quotas_are_not_just_per_file(monkeypatch, tmp_path):
    monkeypatch.setitem(ctx.BOUNDS, "artifact_bytes", 100)
    monkeypatch.setitem(ctx.BOUNDS, "per_file_bytes", 100)
    ctx.write(tmp_path / "one.json", {"data": "a" * 30})
    ctx.write(tmp_path / "two.json", {"data": "b" * 30})
    with pytest.raises(ValueError, match="Aggregate"):
        ctx.budget(tmp_path, reserve=10)


def test_launch_failure_retains_receipt(monkeypatch, tmp_path):
    monkeypatch.setattr(job, "register", lambda *args: None)
    ctx.write(tmp_path / "registration.json", {})

    def fail(*args, **kwargs):
        raise OSError("spawn failed")

    monkeypatch.setattr(job.subprocess, "Popen", fail)
    with pytest.raises(OSError, match="spawn failed"):
        job.launch(tmp_path, tmp_path / "tests.xml")
    assert ctx.read(tmp_path / "launch-failure.json")["status"] == "not_launched"


def test_preflight_launch_detaches_without_campaign(monkeypatch, tmp_path):
    import preflight_job as preflight

    monkeypatch.setattr(preflight, "register", lambda *args: None)
    ctx.write(tmp_path / "registration.json", {})
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return NS(pid=456)

    monkeypatch.setattr(preflight.subprocess, "Popen", popen)
    ack = preflight.launch(tmp_path, tmp_path / "receipt.xml")
    assert not ack["full_campaign_launched"] and not ack["automatic_polling"]
    assert calls[0][1]["start_new_session"]
    assert "preflight_job.py" in " ".join(calls[0][0])
    assert not (tmp_path / "started.json").exists()


def test_preflight_timeout_owns_entire_worker_group(monkeypatch):
    import preflight_job as preflight

    waits, killed = [], []

    def wait(**kwargs):
        waits.append(kwargs)
        if kwargs:
            raise subprocess.TimeoutExpired(["fixture"], 1)
        return -9

    child = NS(pid=987654321, wait=wait)
    monkeypatch.setattr(preflight.subprocess, "Popen", lambda *args, **kwargs: child)
    monkeypatch.setattr(preflight.os, "killpg", lambda *args: killed.append(args))
    with pytest.raises(subprocess.TimeoutExpired):
        preflight.run_tests(["fixture"], None, None)
    assert len(killed) == 1 and killed[0][0] == child.pid
    assert waits == [dict(timeout=preflight.TEST_TIMEOUT), {}]


def test_preflight_keeps_pytest_aliases_but_refuses_escape(tmp_path):
    import preflight_job as preflight

    ctx.write(tmp_path / "data.json", {})
    (tmp_path / "current").symlink_to(tmp_path / "data.json")
    report = preflight.artifacts(tmp_path)
    assert "current" in report["pytest_internal_links"]
    assert set(report["files_sha256"]) == {"data.json"}
    (tmp_path / "escape").symlink_to(tmp_path.parent)
    try:
        with pytest.raises(ValueError, match="Escaping"):
            preflight.artifacts(tmp_path)
    finally:
        (tmp_path / "escape").unlink()  # Only this test-created alias, never its target.


@pytest.mark.parametrize("name", ("../escape", "/absolute"))
def test_unsafe_evidence_path_refused(tmp_path, name):
    with pytest.raises(ValueError, match="Unsafe"):
        ctx.path_for(tmp_path, name)


@pytest.mark.parametrize("mode,index", (("observed", 28), ("unobserved", 29)))
def test_actual_native_smoke(tmp_path, mode, index):
    program = """
import copy, resource, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'validation/betse/live_recording'))
import live_context as ctx
resource.setrlimit(resource.RLIMIT_AS, (ctx.BOUNDS['native_address_space_bytes'],) * 2)
import live_native as live
import betse
import numpy as np
from ruamel.yaml import YAML
from stream_compare import compare
r = copy.deepcopy(ctx.read(ctx.LEGACY / 'registration.json')['native_preparation'])
r['protocol'].update(dt_s=6.25e-6, duration_s=0.001, steps=160)
variant = next(v for v in r['protocol']['variants'] if v['id'] == 'pump_leak')
with (live.prior.c.SOURCE / 'betse/data/yaml/sim_config.yaml').open() as stream:
    template = YAML(typ='safe').load(stream)
target = Path(sys.argv[1])
with np.errstate(over='raise', invalid='raise', divide='raise'):
    live.run_row(r, variant, sys.argv[2], target, Path(betse.__file__).resolve().parent, template)
comparison = compare(target / 'stream', ctx.CODEC / 'rows' / sys.argv[3])
ctx.write(target / 'smoke-comparison.json', comparison)
"""
    with (
        (tmp_path / "stdout.log").open("x") as stdout,
        (tmp_path / "stderr.log").open("x") as stderr,
    ):
        result = subprocess.run(
            [
                str(ctx.NATIVE_PYTHON),
                "-B",
                "-c",
                program,
                str(tmp_path / "native"),
                mode,
                f"{index:02d}",
            ],
            env=ctx.environment(),
            cwd=ctx.ROOT,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            timeout=35,
        )
    assert result.returncode == 0, (tmp_path / "stderr.log").read_text()
    assert ctx.read(tmp_path / "native/smoke-comparison.json")["failed_comparisons"] == 0


def test_actual_cells_smoke(tmp_path):
    program = """
import resource, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'validation/betse/live_recording'))
import live_context as ctx
resource.setrlimit(resource.RLIMIT_AS, (ctx.BOUNDS['cells_address_space_bytes'],) * 2)
import matched_windows as matched
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy, run_windowed
from cells.window_io import write_windowed_run
from cells.io import load_snapshot
original = ctx.read(ctx.LEGACY / 'registration.json')
spec = parse_spec(matched.prior.definition(original['cases']['pump_leak'], 25e-6))
full = run(spec)
previous = ctx.read(ctx.LEGACY / 'cells.json')['records']['pump_leak/dt_2.5e-05/jax_jit']
matched.baseline(full, ctx.LEGACY / previous['directory'])
ctx.write(Path(sys.argv[1]).parent / 'cells-baseline-pass.json', dict(status='exact_prior_overlap'))
check = matched.WindowCheck(full, 7)
result = run_windowed(spec, WindowPolicy(7), sink=check)
check.finish(result)
target = Path(sys.argv[1])
for mode in ('full', 'observations', 'checkpoints'):
    policy = WindowPolicy(7, mode)
    write_windowed_run(target / mode, spec, policy, checkpoint_times=(0.0005,))
    matched.disk_check(target / mode, full, policy)
ctx.write(target.parent / 'cells-disk-policies-pass.json', dict(status='all_three_policies_exact'))
saved = load_snapshot(target / 'checkpoints/snapshots/step-0000000020')
check = matched.WindowCheck(full, 3, saved.checkpoint)
check.finish(run_windowed(spec, WindowPolicy(3), saved.checkpoint, sink=check), suffix=True)
ctx.write(target.parent / 'cells-restart-pass.json', dict(status='loaded_window_suffix_exact'))
zero = matched.WindowCheck(full, 3, full.final)
zero.finish(run_windowed(spec, WindowPolicy(3), full.final, sink=zero), suffix=True)
ctx.write(target.parent / 'cells-zero-length-pass.json', dict(status='zero_length_exact'))
sparse = parse_spec(matched.prior.definition(original['cases']['pump_leak'], 25e-6,
                                           times=[0.0, 0.001]))
sfull = run(sparse)
assert sfull.diagnostics == full.diagnostics
check = matched.WindowCheck(sfull, 7)
check.finish(run_windowed(sparse, WindowPolicy(7, 'checkpoints'), sink=check))
ctx.write(target.parent / 'cells-sparse-pass.json', dict(status='sparse_schedule_exact'))
"""
    with (
        (tmp_path / "stdout.log").open("x") as stdout,
        (tmp_path / "stderr.log").open("x") as stderr,
    ):
        result = subprocess.run(
            [str(ctx.CELLS_PYTHON), "-B", "-c", program, str(tmp_path / "cells")],
            env=ctx.environment(),
            cwd=ctx.ROOT,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            timeout=120,
        )
    assert result.returncode == 0, (tmp_path / "stderr.log").read_text()
