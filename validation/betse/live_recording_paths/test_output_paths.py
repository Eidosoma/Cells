"""Fast filesystem/control tests, with explicitly stubbed physics; real probe is detached."""

import ast
import copy
import inspect
import subprocess
import sys
from collections import namedtuple
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import output_context as plan  # noqa: E402
import output_job as job  # noqa: E402
import output_worker as work  # noqa: E402
from output_context import ctx, previous  # noqa: E402


def registration():
    return dict(cells_keys=sorted(ctx.read(ctx.LEGACY / "cells.json")["records"]))


def result(phase):
    keys = plan.selected_keys(registration(), phase)
    rows = {}
    for key in keys:
        restart = int(key.endswith("/dt_2.5e-05/jax_jit"))
        rows[key] = dict(
            directory="cells/" + key,
            sha256="test-stub-not-numerical-evidence",
            windows=3,
            recordings=restart * 3,
            restarts=restart,
            restart_windows=restart,
            zero_length=restart,
            sparse=int(key.startswith("pump_leak/dt_5e-05/")),
            baseline_preserved=True,
        )
    return dict(
        status=plan.STATUS[phase],
        output_layout_version=plan.LAYOUT_VERSION,
        records=rows,
        production_changed=False,
        **plan.COUNTS[phase],
    )


@pytest.fixture
def stub_physics(monkeypatch):
    """Exercise real campaign control/writer dispatch, NOT numerical/biological correctness."""
    writes, loads = [], []
    History = namedtuple("History", "vm")
    cp = NS(time=0.0005, step_index=20)
    full = NS(
        history=History([0.0] * 81),
        times=[0.0] * 81,
        final=cp,
        diagnostics={},
        observations=NS(times=[0.0, 0.0005, 0.001]),
        checkpoint_at=lambda _: cp,
    )

    class Arrays:
        def match(self, *_):
            pass

        def checkpoint(self, *_):
            pass

        def report(self):
            return dict(exact_arrays=1, exact_values=1, comparison_sha256="stub")

    class WindowCheck:
        def __init__(self, *args):
            pass

        def finish(self, result, **kwargs):
            return dict(exact_arrays=1, exact_values=1, comparison_sha256="stub", diagnostics={})

    class Policy:
        def __init__(self, width, recording="full"):
            self.recording, self.width = recording, width

    def write(path, *args, **kwargs):
        path.mkdir(parents=True, exist_ok=False)
        ctx.write(path / "manifest.json", {"test_only": True})
        writes.append(path)

    def record(path, spec, policy, **kwargs):
        assert kwargs["checkpoint_times"] == (0.0005,)
        write(path)
        (path / "snapshots/step-0000000020").mkdir(parents=True)

    def load(path):
        assert path.is_dir()
        loads.append(path)
        return NS(spec={}, checkpoint=cp)

    modules = {
        "jax": dict(
            default_backend=lambda: "cpu", config=NS(x64_enabled=True, jax_disable_jit=False)
        ),
        "cells": {},
        "cells.core": {},
        "cells.core.runner": dict(run=lambda *a: full),
        "cells.core.specs": dict(parse_spec=lambda spec: spec),
        "cells.core.windows": dict(
            WindowPolicy=Policy, run_windowed=lambda *a, **kw: NS(diagnostics={})
        ),
        "cells.io": dict(write_run=write, load_snapshot=load),
        "cells.window_io": dict(write_windowed_run=record),
    }
    for name, attrs in modules.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(work, "Arrays", Arrays)
    monkeypatch.setattr(work, "WindowCheck", WindowCheck)
    monkeypatch.setattr(work, "baseline", lambda *a: Arrays().report())
    monkeypatch.setattr(work, "disk_check", lambda *a: Arrays().report())
    runtime = ctx.read(ctx.LEGACY / "registration.json")["cells_reference_runtime"]
    monkeypatch.setattr(work.prior, "runtime", lambda: runtime)
    monkeypatch.setattr(work.prior, "definition", lambda *a, **kw: {})
    return NS(writes=writes, loads=loads)


@pytest.mark.parametrize("phase", ["probe", "matrix"])
def test_same_worker_uses_disjoint_output_roles(tmp_path, stub_physics, phase):
    output = tmp_path / phase
    output.mkdir()
    r = registration()
    checked = work.worker(output, r, phase)
    plan.gate(phase, checked, r)
    assert len(stub_physics.writes) == len(set(stub_physics.writes))
    assert len(stub_physics.loads) == (1 if phase == "probe" else 6)
    for row in checked["records"].values():
        directory = output / row["directory"]
        report = ctx.read(directory / "comparison.json")
        assert report["output_paths"] == plan.LAYOUT
        ctx.hashes(directory / "baseline", report["baseline_files_sha256"])
        assert ctx.sha(directory / "comparison.json") == row["sha256"]
        if row["recordings"]:
            assert {p.name for p in (directory / "recordings").iterdir()} == {
                "full",
                "observations",
                "checkpoints",
            }
            assert (
                directory / "recordings/checkpoints/snapshots/step-0000000020" in stub_physics.loads
            )


def test_original_path_collision_regression(tmp_path, stub_physics, monkeypatch):
    """The campaign itself must refuse the original same-directory ownership before work."""
    monkeypatch.setitem(plan.LAYOUT, "recording_full", "baseline")
    with pytest.raises(ValueError, match="Output roles overlap"):
        work.worker(tmp_path, registration(), "probe")
    assert stub_physics.writes == []


@pytest.mark.parametrize(
    "relative", ["baseline/nested", "recordings", ".", "../escape", "/tmp/escape"]
)
def test_overlapping_or_unsafe_role_refused(tmp_path, monkeypatch, relative):
    monkeypatch.setitem(plan.LAYOUT, "resumed", relative)
    with pytest.raises(ValueError):
        plan.case_paths(tmp_path, plan.PROBE_KEY)


def test_existing_case_is_not_overwritten(tmp_path, stub_physics):
    directory = tmp_path / "cells" / plan.PROBE_KEY
    directory.mkdir(parents=True)
    ctx.write(directory / "existing.json", {"keep": True})
    before = ctx.inventory(tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        work.worker(tmp_path, registration(), "probe")
    assert ctx.inventory(tmp_path) == before and stub_physics.writes == []


def test_all_matrix_paths_checked_before_first_model(tmp_path, stub_physics):
    last = registration()["cells_keys"][-1]
    (tmp_path / "cells" / last).mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        work.worker(tmp_path, registration(), "matrix")
    assert stub_physics.writes == []


def test_baseline_mutation_during_recording_is_detected(tmp_path, stub_physics, monkeypatch):
    output = tmp_path / "probe"
    output.mkdir()

    def changed(directory, full, policy):
        baseline = directory.parent.parent / "baseline"
        ctx.write(baseline / "unexpected.json", {"changed": True})
        return {"exact_arrays": 1}

    original = work.disk_check

    def once(directory, full, policy):
        monkeypatch.setattr(work, "disk_check", original)
        return changed(directory, full, policy)

    monkeypatch.setattr(work, "disk_check", once)
    with pytest.raises(ValueError, match="Baseline output changed"):
        work.worker(output, registration(), "probe")


def test_all_numerical_checks_are_reused():
    import matched_windows as frozen

    for name in ("Arrays", "WindowCheck", "baseline", "disk_check", "prior"):
        assert getattr(work, name) is getattr(frozen, name)

    class OnlyPaths(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id in ("write_run", "load_snapshot"):
                node.args[0] = ast.Constant("<output-path>")
            return node

        def visit_Assign(self, node):
            node = self.generic_visit(node)
            if any(isinstance(t, ast.Name) and t.id == "target" for t in node.targets):
                node.value = ast.Constant("<recording-path>")
            return node

    def numerical_blocks(function):
        tree = ast.parse(inspect.getsource(function))
        blocks = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and (
                ast.unparse(node.test).startswith("jit and step")
                or ast.unparse(node.test).startswith("case == 'pump_leak'")
            ):
                blocks.append(node)
            if isinstance(node, ast.For) and ast.unparse(node.target) == "(width, recording)":
                blocks.append(node)
        assert len(blocks) == 3
        return [ast.dump(OnlyPaths().visit(block)) for block in blocks]

    assert numerical_blocks(work.worker) == numerical_blocks(frozen.worker)


@pytest.mark.parametrize("field", list(plan.COUNTS["matrix"]))
def test_every_matrix_count_is_checked(field):
    bad = result("matrix")
    bad[field] -= 1
    with pytest.raises(ValueError):
        plan.gate("matrix", bad, registration())


@pytest.mark.parametrize(
    "change", ["wrong-key", "baseline", "wrong-row", "missing-window", "layout", "status"]
)
def test_probe_scope_or_row_coverage_cannot_be_faked(change):
    bad = result("probe")
    row = bad["records"][plan.PROBE_KEY]
    if change == "wrong-key":
        bad["records"]["other"] = bad["records"].pop(plan.PROBE_KEY)
    elif change == "baseline":
        row["baseline_preserved"] = False
    elif change == "wrong-row":
        row["directory"] = "other"
    elif change == "missing-window":
        row["windows"] = 2
    else:
        bad["output_layout_version" if change == "layout" else "status"] = "wrong"
    with pytest.raises(ValueError):
        plan.gate("probe", bad, registration())


def controller(monkeypatch):
    r = registration() | dict(prior=dict(accepted={}, reused_native={}))
    monkeypatch.setattr(job, "authenticate", lambda *_: r)
    monkeypatch.setattr(ctx, "prerequisite", lambda: {})
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda _: {0, 1, 2, 3})
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    return r


def phase_files(output, phase):
    (output / phase).mkdir()
    ctx.write(output / phase / "test-stub.json", {"test_only": True})
    ctx.write(output / (phase + ".json"), result(phase))


def test_probe_gate_precedes_matrix(tmp_path, monkeypatch):
    r = controller(monkeypatch)
    phases = []

    def run(command, out, err, timeout):
        phase = command[-1]
        assert command[-2] == "--phase" and timeout == plan.PHASE_TIMEOUTS[phase]
        if phase == "matrix":
            job.probe_gate(tmp_path, r, "digest")
        else:
            assert not (tmp_path / "matrix").exists()
        phases.append(phase)
        phase_files(tmp_path, phase)

    monkeypatch.setattr(previous, "run_child", run)
    job.execute(tmp_path, "digest")
    assert phases == ["probe", "matrix"]
    done = ctx.read(tmp_path / "completion.json")
    assert done["actual_worker_probe_complete"] is True and done["automatic_followup"] is False
    assert done["new_native_runs"] == 0 and done["partial_cells_reused"] is False
    assert done["independent_live_review_complete"] is False
    ctx.hashes(tmp_path, done["files_sha256"])


@pytest.mark.parametrize("failure", ["exit", "bad-result", "stderr"])
def test_failed_probe_never_starts_matrix(tmp_path, monkeypatch, failure):
    controller(monkeypatch)
    phases = []

    def run(command, out, err, timeout):
        phases.append(command[-1])
        if failure == "exit":
            raise subprocess.CalledProcessError(1, command)
        if failure == "bad-result":
            bad = result("probe")
            bad["disk_recordings"] = 0
            (tmp_path / "probe").mkdir()
            ctx.write(tmp_path / "probe.json", bad)
        else:
            phase_files(tmp_path, "probe")
            err.write("unexpected warning\n")

    monkeypatch.setattr(previous, "run_child", run)
    with pytest.raises((subprocess.CalledProcessError, ValueError)):
        job.execute(tmp_path, "digest")
    assert phases == ["probe"] and not (tmp_path / "matrix.stdout.log").exists()
    assert (tmp_path / "failure.json").is_file() and not (tmp_path / "completion.json").exists()
    before = ctx.sha(tmp_path / "failure.json")
    with pytest.raises(ValueError, match="already attempted"):
        job.execute(tmp_path, "digest")
    assert before == ctx.sha(tmp_path / "failure.json")


@pytest.fixture
def probe(tmp_path):
    phase_files(tmp_path, "probe")
    (tmp_path / "probe.stderr.log").touch()
    ctx.write(
        tmp_path / "probe-complete.json",
        dict(
            status="phase_pass",
            phase="probe",
            registration_sha256="digest",
            result_sha256=ctx.sha(tmp_path / "probe.json"),
            files_sha256=ctx.inventory(tmp_path / "probe"),
        ),
    )
    return tmp_path


@pytest.mark.parametrize(
    "change", ["result", "payload", "extra", "failure", "stderr", "registration"]
)
def test_changed_probe_receipt_blocks_matrix(probe, change):
    if change in ("result", "payload"):
        target = probe / ("probe.json" if change == "result" else "probe/test-stub.json")
        with target.open("ab") as file:
            file.write(b" ")
    elif change == "extra":
        ctx.write(probe / "probe/extra.json", {})
    elif change == "failure":
        ctx.write(probe / "probe-failure.json", {})
    elif change == "stderr":
        with (probe / "probe.stderr.log").open("a") as file:
            file.write("warning\n")
    with pytest.raises(ValueError):
        job.probe_gate(probe, registration(), "wrong" if change == "registration" else "digest")


def test_matrix_worker_requires_completed_probe(tmp_path, monkeypatch):
    controller(monkeypatch)
    with pytest.raises(FileNotFoundError):
        job.worker(tmp_path, "digest", "matrix")
    assert not (tmp_path / "matrix").exists()
    assert (tmp_path / "matrix-failure.json").is_file()


@pytest.fixture
def auth(monkeypatch):
    r = registration() | dict(
        schema="cells.live_recording_output_layout@1",
        decision="D128",
        duration_s=0.001,
        bounds=copy.deepcopy(ctx.BOUNDS),
        phases=["probe", "matrix"],
        phase_timeouts=copy.deepcopy(plan.PHASE_TIMEOUTS),
        output_layout_version=plan.LAYOUT_VERSION,
        output_layout=copy.deepcopy(plan.LAYOUT),
        probe_keys=[plan.PROBE_KEY],
        phase_counts=copy.deepcopy(plan.COUNTS),
        new_native_runs=0,
        partial_cells_reused=False,
        production_changed=False,
        scientific_tolerances_changed=False,
        automatic_retry=False,
        automatic_followup=False,
        sources_sha256={"file": "sha"},
        software={"path": "checked"},
        prior={},
    )
    monkeypatch.setattr(plan, "sources", lambda: {"file": "sha"})
    monkeypatch.setattr(ctx, "capsule", lambda *_: None)
    monkeypatch.setattr(plan, "authenticate_prior", lambda *_: None)
    monkeypatch.setattr(job, "software", lambda _: {"path": "checked"})
    return r


@pytest.mark.parametrize(
    "change",
    [
        "digest",
        "sources",
        "layout",
        "phases",
        "probe",
        "duration",
        "keys",
        "bounds",
        "followup",
        "native",
        "partial",
    ],
)
def test_registration_binding_refuses_changes(tmp_path, auth, change):
    if change == "sources":
        auth["sources_sha256"] = {}
    elif change == "layout":
        auth["output_layout"]["recording_full"] = "baseline"
    elif change == "phases":
        auth["phases"].reverse()
    elif change == "probe":
        auth["probe_keys"] = []
    elif change == "duration":
        auth["duration_s"] = 0.01
    elif change == "keys":
        auth["cells_keys"].pop()
    elif change == "bounds":
        auth["phase_timeouts"]["probe"] = 999
    elif change == "followup":
        auth["automatic_followup"] = True
    elif change == "native":
        auth["new_native_runs"] = 1
    elif change == "partial":
        auth["partial_cells_reused"] = True
    ctx.write(tmp_path / "registration.json", auth)
    digest = "wrong" if change == "digest" else ctx.sha(tmp_path / "registration.json")
    with pytest.raises(ValueError):
        job.authenticate(tmp_path, digest)


def test_authentication_success(tmp_path, auth):
    ctx.write(tmp_path / "registration.json", auth)
    assert job.authenticate(tmp_path, ctx.sha(tmp_path / "registration.json")) == auth


def test_detached_launch_binding_no_wait(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        job, "register", lambda output, checked: ctx.write(output / "registration.json", {})
    )
    monkeypatch.setattr(
        job.subprocess, "Popen", lambda cmd, **kw: calls.append((cmd, kw)) or NS(pid=123)
    )
    ack = job.launch(tmp_path, "checked")
    command, options = calls[0]
    assert command[-2:] == ["--registration-sha", ctx.sha(tmp_path / "registration.json")]
    assert options["start_new_session"] is True and options["stdin"] == subprocess.DEVNULL
    assert ack["automatic_polling"] is False and ack["phases"] == ["probe", "matrix"]


def test_prior_failure_and_sources_remain_intact():
    ctx.hashes(plan.STOPPED, plan.STOPPED_IDENTITIES)
    r = previous.authenticate(plan.STOPPED, plan.STOPPED_IDENTITIES["registration.json"])
    assert len(r["sources_sha256"]) == 674
    assert len(ctx.inventory(plan.STOPPED)) == 24
    assert not (plan.STOPPED / "completion.json").exists()


def test_software_receipt_and_payload_binding(tmp_path, monkeypatch):
    output = tmp_path / "runs/checked"
    output.mkdir(parents=True)
    monkeypatch.setattr(ctx, "ROOT", tmp_path)
    monkeypatch.setattr(plan, "sources", lambda: {"a": "b"})
    xml = dict(path="reports/tests.xml", sha256="xml", tests=50)
    monkeypatch.setattr(job, "receipt", lambda *_: xml)
    ctx.write(
        output / "completion.json",
        dict(
            status="output_layout_software_pass",
            sources_sha256={"a": "b"},
            software=xml,
            files_sha256={},
            pytest_internal_links={},
            actual_model_probe_complete=False,
            qualification_launched=False,
            automatic_followup=False,
        ),
    )
    path = "runs/checked/completion.json"
    assert job.software(path) == dict(
        path=path, sha256=ctx.sha(output / "completion.json"), xml=xml
    )
    ctx.write(output / "extra.json", {})
    with pytest.raises(ValueError, match="Software artifacts changed"):
        job.software(path)
