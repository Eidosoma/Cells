"""Stdlib runner controls. No Cells, native, NumPy, Pillow or scientific entry."""

import importlib.abc
import json
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest

from validation.betse import native_single_cell_prefix_qualification as runner


@pytest.fixture(autouse=True)
def no_science():
    attempted = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {
                "cells",
                "betse",
                "numpy",
                "scipy",
                "PIL",
                "jax",
                "jaxlib",
            }:
                attempted.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    blocker = Block()
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
    assert not attempted


@pytest.fixture
def packet(tmp_path, monkeypatch):
    repository, base = tmp_path / "repo", tmp_path / "outputs"
    repository.mkdir()
    base.mkdir()
    native = base / "native"
    native.mkdir()
    defaults = native / "defaults.yaml"
    defaults.write_text("cell height: 1e-5\ncell spacing: 2.6e-8\n")
    original = native / "original.py"
    original.write_text("# retained synthetic source authority\n")
    files = {runner.OWN: "# synthetic runner bytes\n", runner.TEST: "# controls\n"}
    for suffix in ("caller_lattice", "image_mask"):
        name = f"src/cells/processes/betse_native_single_cell_{suffix}_source.py"
        files[name] = "NATIVE_PINS = " + repr({"original.py": runner.pin(original)["sha256"]})
    names = [*files, runner.CLOSURE]
    files[runner.CLOSURE] = (
        "def closure(root, starts):\n    return {name: '' for name in " + repr(names) + "}\n"
    )
    for name, text in files.items():
        path = repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Control",
            "-c",
            "user.email=control@invalid",
            "commit",
            "-qm",
            "synthetic source",
        ],
        check=True,
    )
    monkeypatch.setattr(runner, "BASE", base)
    monkeypatch.setattr(runner, "NATIVE", native)
    monkeypatch.setattr(runner, "DEFAULTS", defaults)
    monkeypatch.setattr(runner, "DEFAULTS_SHA256", runner.pin(defaults)["sha256"])
    cpu = next(iter(runner.os.sched_getaffinity(0)))
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {cpu})
    prepared = base / "prepared"
    plan = runner.prepare(prepared, repository=repository, cpu=cpu)
    sha = runner.pin(prepared / "plan.json")["sha256"]
    review = base / "review.json"
    runner.write(review, dict(scope="synthetic orchestration control, not source admission"))
    release = base / "release.json"
    runner.write(
        release,
        dict(
            kind=runner.KINDS[1],
            plan_sha256=sha,
            snapshot_sha256=plan["snapshot_sha256"],
            case=runner.CASES[0],
            allow_actual_source_diagnostic=True,
            scientific_qualification=False,
            source_review=runner.pin(review),
        ),
    )
    return SimpleNamespace(
        root=base,
        repository=repository,
        prepared=prepared,
        plan=plan,
        sha=sha,
        release=release,
        review=review,
        native=original,
        cpu=cpu,
    )


def test_prepare_freezes_git_and_native_inputs_without_model_imports(packet):
    plan = runner.verify_plan(packet.prepared, packet.sha)
    assert plan["cases"] == list(runner.CASES)
    assert plan["configuration"] == runner.CONFIGURATION
    assert plan["git_revision"]
    assert len(plan["external_inputs"]) == 2
    assert not plan["scientific_qualification"]
    assert not (packet.prepared / "release.json").exists()
    assert not (packet.prepared / "source" / runner.OWN).stat().st_mode & 0o222


def test_execution_verification_uses_frozen_source_after_checkout_moves(packet):
    (packet.repository / runner.OWN).write_text("# subsequent checkout development\n")
    assert (
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])
        == packet.plan
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan_sha256", "0" * 64),
        ("snapshot_sha256", "0" * 64),
        ("allow_actual_source_diagnostic", False),
        ("allow_actual_source_diagnostic", 1),
        ("scientific_qualification", True),
        ("case", runner.CASES[1]),
        ("source_review", None),
    ],
)
def test_release_mismatches_refuse_before_any_launch(packet, field, value):
    release = runner.read(packet.release)
    release[field] = value
    packet.release.write_text(json.dumps(release))
    with pytest.raises(ValueError, match="release"):
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])


def test_release_review_and_native_source_drift_refuse(packet):
    packet.review.write_text("changed review")
    with pytest.raises(ValueError, match="external"):
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])
    packet.native.write_text("changed native source")
    with pytest.raises(ValueError, match="external"):
        runner.verify_plan(packet.prepared, packet.sha)


def test_missing_release_never_starts_child(packet, monkeypatch):
    monkeypatch.setattr(
        runner.guard, "run_bounded", lambda *a, **k: pytest.fail("unexpected launch")
    )
    output = packet.root / "not-started"
    with pytest.raises(FileNotFoundError):
        runner.launch(packet.prepared, packet.sha, packet.root / "absent", runner.CASES[0], output)
    assert not output.exists()


def test_snapshot_change_and_incomplete_preparation_refuse(packet):
    file = packet.prepared / "source" / runner.OWN
    file.chmod(0o644)
    file.write_text("changed frozen source")
    with pytest.raises(ValueError, match="Changed snapshot"):
        runner.verify_plan(packet.prepared, packet.sha)
    runner.write(packet.prepared / "preparation-failure.json", {"failed": True})
    with pytest.raises(ValueError, match="Incomplete"):
        runner.verify_plan(packet.prepared, packet.sha)


def test_failed_preparation_retains_error_and_never_publishes_plan(packet):
    packet.native.write_text("drift before preparation")
    target = packet.root / "failed-preparation"
    with pytest.raises(ValueError, match="external"):
        runner.prepare(target, repository=packet.repository, cpu=packet.cpu)
    assert (target / "preparation-failure.json").is_file()
    assert not (target / "plan.json").exists()


def test_overlay_pins_include_versioned_shared_libraries(packet):
    overlay = packet.root / "overlay"
    overlay.mkdir()
    library = overlay / "libnative.so.6.0.0"
    library.write_bytes(b"synthetic library bytes, never loaded")
    prepared = packet.root / "with-overlay"
    plan = runner.prepare(
        prepared, repository=packet.repository, cpu=packet.cpu, runtime_paths=[overlay]
    )
    assert runner.pin(library) in plan["external_inputs"]
    library.write_bytes(b"changed library")
    with pytest.raises(ValueError, match="external"):
        runner.verify_plan(prepared, runner.pin(prepared / "plan.json")["sha256"])


def test_output_escape_link_and_reuse_refused(packet):
    with pytest.raises(ValueError):
        runner.output_path(packet.root.parent / "outside")
    link = packet.root / "linked"
    link.symlink_to(packet.root / "prepared", target_is_directory=True)
    with pytest.raises(ValueError, match="Linked"):
        runner.output_path(link / "child")
    with pytest.raises(FileExistsError):
        runner.prepare(packet.prepared, repository=packet.repository, cpu=packet.cpu)


def test_wrong_cpu_refuses(packet, monkeypatch):
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {packet.cpu, packet.cpu + 1})
    with pytest.raises(ValueError, match="single CPU"):
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])


@pytest.mark.parametrize("target", ["prepared", "source", "native"])
def test_output_cannot_modify_prepared_or_native_inputs(packet, target):
    roots = {
        "prepared": packet.prepared,
        "source": packet.prepared / "source",
        "native": runner.NATIVE,
    }
    output = roots[target] / "new-run"
    with pytest.raises(ValueError, match="overlaps"):
        runner.launch(packet.prepared, packet.sha, packet.release, runner.CASES[0], output)
    assert not output.exists()


def test_environment_discards_inherited_source_and_gpu_settings(packet, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(packet.repository) + ":/unknown")
    monkeypatch.setenv("CELLS_BETSE_SOURCE", "/unknown/native")
    monkeypatch.setenv("PYTHONHOME", "/unknown/python")
    env = runner.environment(packet.prepared / "source", packet.plan)
    assert env["PYTHONPATH"].split(":") == [
        str(packet.prepared / "source"),
        str(packet.prepared / "source/src"),
    ]
    assert env["CUDA_VISIBLE_DEVICES"] == ""
    assert env["OPENBLAS_NUM_THREADS"] == "1"
    assert "PYTHONHOME" not in env and "CELLS_BETSE_SOURCE" not in env


def test_source_failure_retains_parent_trial_cause_and_unrun_stages(tmp_path):
    evidence = runner.Evidence(tmp_path)
    work = SimpleNamespace(phase="", count=7)
    later = []
    parent = {"cache": [1, 2], "rng": {"position": 624, "cached": -0.25}}

    def fail():
        try:
            raise ZeroDivisionError("original native defect")
        except ZeroDivisionError as original:
            error = ValueError("owned trial refused")
            error.trial, error.parent_state = {"partial": [3]}, parent
            raise error from original

    result = runner.run_stages(
        [("parent", lambda: parent), ("pre_mesh", fail), ("later", lambda: later.append(1))],
        evidence,
        work,
    )
    assert result["status"] == "diagnostic_failed" and result["failed_stage"] == "pre_mesh"
    assert result["completed_stages"] == ["parent"] and not later
    assert result["source_error"]["nodes"][1]["type"].endswith("ZeroDivisionError")
    assert all(row["status"] == "saved" for row in result["captures"])
    assert len(result["captures"]) == 3
    assert runner.read(tmp_path / result["captures"][2]["path"]) == {
        "cache": [1, 2],
        "rng": {"position": 624, "cached": {"float64_bits": "000000000000d0bf"}},
    }
    assert result["accepted_cases"] == 0


def test_capture_failure_is_separate_and_stops_continuation(tmp_path):
    evidence = runner.Evidence(tmp_path)
    later = []
    result = runner.run_stages(
        [("parent", lambda: object()), ("later", lambda: later.append(1))],
        evidence,
        SimpleNamespace(phase="", count=0),
    )
    assert result["failed_stage"] == "parent:capture"
    assert result["source_error"] is None and not later
    assert result["captures"][0]["status"] == "capture_failed"


def test_failed_live_partial_capture_does_not_hide_primary_error(tmp_path):
    error = RuntimeError("primary source failure")
    error.partial = {"live_owner": object(), "saved_cache": {"value": 3}}
    evidence = runner.Evidence(tmp_path)
    evidence.failure(error)
    assert [r["status"] for r in evidence.rows] == ["capture_failed", "saved"]
    assert runner.read(tmp_path / evidence.rows[1]["path"]) == {"value": 3}
    assert runner.exception_record(error)["nodes"][0]["message"] == "primary source failure"


def test_exception_graph_retains_separate_capture_error_and_cycles():
    primary, capture = ValueError("source"), RuntimeError("capture")
    wrapper = RuntimeError("sealing")
    wrapper.source_error, wrapper.capture_error = primary, capture
    wrapper.__cause__ = primary
    primary.__cause__ = wrapper
    record = runner.exception_record(wrapper)
    assert len(record["nodes"]) == 3
    assert record["nodes"][0]["cause"] == record["nodes"][0]["source_error"]
    assert record["nodes"][1]["cause"] == record["root"]


def test_capture_preserves_noncanonical_nan_bits(tmp_path):
    bits = "030000000000f87f"
    value = struct.unpack("<d", bytes.fromhex(bits))[0]
    evidence = runner.Evidence(tmp_path)
    assert evidence.save("failed-cache", {"nan": value})
    saved = runner.read(tmp_path / evidence.rows[0]["path"])
    assert saved["nan"] == {"float64_bits": bits}


def test_completed_diagnostic_never_implies_parity(tmp_path):
    work = SimpleNamespace(phase="", count=19)
    result = runner.run_stages(
        [(name, lambda: {"synthetic": True}) for name in runner.STAGES],
        runner.Evidence(tmp_path),
        work,
    )
    assert result["status"] == "source_completed_unqualified"
    assert result["completed_stages"] == list(runner.STAGES)
    assert result["observed_source_entry_attempts"] == 19
    assert result["independent_cases"] == 1 and result["accepted_cases"] == 0
    assert all(result[key] == value for key, value in runner.NO_CREDIT.items())


def test_worklog_chains_restores_and_records_failed_attempt(tmp_path):
    source = tmp_path / "frozen"
    namespace = {}
    exec(
        compile(
            "def action():\n    raise ValueError('synthetic')\n",
            str(source / "src/cells/probe.py"),
            "exec",
        ),
        namespace,
    )
    previous = sys.getprofile()
    called = []

    def outer(frame, event, arg):
        if frame.f_code is namespace["action"].__code__ and event == "call":
            called.append(True)

    work = runner.WorkLog(tmp_path, source)
    sys.setprofile(outer)
    try:
        with pytest.raises(ValueError, match="synthetic"), work.active():
            work.phase = "authentication"
            namespace["action"]()
        assert sys.getprofile() is outer
    finally:
        sys.setprofile(previous)
    rows = [json.loads(line) for line in work.path.read_text().splitlines()]
    assert called == [True] and len(rows) == 1
    assert rows[0]["phase"] == "authentication" and rows[0]["event"] == "call"
    assert rows[0]["entry_is_success_or_independent_case"] is False


def test_observer_budget_failure_is_not_a_native_failure(tmp_path):
    source = tmp_path / "source"
    namespace = {}
    exec(
        compile("def action():\n    return 1\n", str(source / "src/cells/probe.py"), "exec"),
        namespace,
    )
    work = runner.WorkLog(tmp_path, source)
    work.count = 100000
    with work.active():
        result = runner.run_stages(
            [("native", namespace["action"])], runner.Evidence(tmp_path), work
        )
    assert result["status"] == "diagnostic_failed"
    assert result["observer_error"] and result["interrupted_exception_graph"]
    assert result["source_error"] is None
    assert not result["completed_stages"] and result["accepted_cases"] == 0


def test_swallowed_profiler_error_still_stops_diagnostic(tmp_path):
    source = tmp_path / "source"
    namespace = {}
    exec(
        compile("def inner():\n    return 1\n", str(source / "src/cells/probe.py"), "exec"),
        namespace,
    )
    work = runner.WorkLog(tmp_path, source)
    work.count = 100000
    later = []

    def catching_action():
        try:
            namespace["inner"]()
        except RuntimeError:
            return {"partial": "returned after profile failure"}

    with work.active():
        result = runner.run_stages(
            [("native", catching_action), ("later", lambda: later.append(True))],
            runner.Evidence(tmp_path),
            work,
        )
    assert result["status"] == "diagnostic_failed" and result["failed_stage"] == "native:observer"
    assert result["observer_error"] and result["source_error"] is None
    assert not later and not result["completed_stages"]
    assert result["captures"][0]["label"] == "native:interrupted-return"


@pytest.mark.parametrize("mode", ["source_failure", "guard_stop", "success"])
def test_launch_retains_terminal_artifacts_without_retry(packet, monkeypatch, mode):
    monkeypatch.setattr(runner.guard, "memory_available", lambda: 13 * 2**30)
    attempts = []

    def bounded(command, *, directory, cwd, env, **limits):
        attempts.append(command)
        assert limits == runner.LIMITS
        assert cwd == packet.prepared / "source"
        assert env["PYTHONPATH"].startswith(str(cwd))
        if mode == "success":
            runner.write(
                directory.parent / "diagnostic.json", dict(status="source_completed_unqualified")
            )
            result = dict(status="completed", returncode=0)
            runner.write(directory / "result.json", result)
            return result
        if mode == "source_failure":
            runner.write(
                directory.parent / "diagnostic.json",
                dict(status="diagnostic_failed", source_error="retained"),
            )
        else:
            runner.write(directory / "resource-stop.json", dict(reason="synthetic wall guard"))
        runner.write(directory / "failure.json", dict(status="failed", returncode=1))
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(runner.guard, "run_bounded", bounded)
    output = packet.root / mode
    result = runner.launch(packet.prepared, packet.sha, packet.release, runner.CASES[0], output)
    assert len(attempts) == 1 and result["automatic_retry"] is False
    assert result["status"] == ("completed_unqualified" if mode == "success" else "failed")
    assert result["process_receipts"] and result["accepted_cases"] == 0
    assert (output / ("result.json" if mode == "success" else "failure.json")).is_file()


def test_low_memory_leaves_terminal_failure_without_launch(packet, monkeypatch):
    monkeypatch.setattr(runner.guard, "memory_available", lambda: 11 * 2**30)
    monkeypatch.setattr(
        runner.guard, "run_bounded", lambda *a, **k: pytest.fail("unexpected launch")
    )
    output = packet.root / "low-memory"
    result = runner.launch(packet.prepared, packet.sha, packet.release, runner.CASES[0], output)
    assert result["status"] == "failed" and result["diagnostic"] is None
    assert not result["process_receipts"]
    assert (output / "failure.json").is_file()


@pytest.mark.parametrize("operation", ["mkdir", "inputs_write"])
def test_owned_startup_failure_has_terminal_receipt(packet, monkeypatch, operation):
    output = packet.root / "startup-failure"
    if operation == "mkdir":
        original = type(output).mkdir

        def mkdir(path, *args, **kwargs):
            if path == output / "process":
                raise OSError("synthetic process-directory failure")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(type(output), "mkdir", mkdir)
    else:
        original = runner.write

        def write(path, value):
            if path == output / "inputs.json":
                raise OSError("synthetic inputs-write failure")
            return original(path, value)

        monkeypatch.setattr(runner, "write", write)
    monkeypatch.setattr(
        runner.guard, "run_bounded", lambda *a, **k: pytest.fail("unexpected launch")
    )
    result = runner.launch(packet.prepared, packet.sha, packet.release, runner.CASES[0], output)
    assert result["status"] == "failed" and result["process"] is None
    assert (output / "failure.json").is_file()
