"""Logging regression, saved-byte reuse and Cells-only detached orchestration."""

import copy
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resume_context as res  # noqa: E402
import resume_job as job  # noqa: E402
from resume_context import ctx  # noqa: E402


def test_actual_script_logging_prefix(tmp_path):
    probe = res.HERE / "notice_probe.py"
    with (tmp_path / "stdout.log").open("x") as out, (tmp_path / "stderr.log").open("x") as err:
        completed = subprocess.run(
            [str(ctx.NATIVE_PYTHON), "-B", str(probe)],
            env=ctx.environment(),
            cwd=ctx.ROOT,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            timeout=15,
            check=True,
        )
    assert completed.returncode == 0
    assert (tmp_path / "stdout.log").read_bytes() == b""
    assert res.native_notices(
        (tmp_path / "stderr.log").read_text(), program=probe, count=1
    ) == dict(program="notice_probe.py", message=res.NOTICE, count=1)


def test_saved_notices_reject_old_classifier():
    text = (res.FAILED / "native.stderr.log").read_text()
    assert text.splitlines() != ["[betse] " + res.NOTICE] * 72
    assert res.native_notices(text, program=ctx.HERE / "live_job.py", count=72)["count"] == 72
    with pytest.raises(ValueError, match="Unexpected worker stderr"):
        res.native_notices(text, program="betse", count=72)


@pytest.mark.parametrize(
    "change", ["short", "extra", "other-prefix", "other-message", "blank", "traceback", "mixed"]
)
def test_notice_classifier_fails_closed(change):
    text = ("[live_job.py] " + res.NOTICE + "\n") * 72
    if change == "short":
        text = "\n".join(text.splitlines()[:-1])
    elif change == "extra":
        text += text.splitlines()[0] + "\n"
    elif change == "other-prefix":
        text = text.replace("live_job.py", "betse")
    elif change == "other-message":
        text = text.replace("disabled.", "enabled.")
    elif change == "blank":
        text += "\n"
    elif change == "traceback":
        text += "Traceback: genuine failure\n"
    else:
        text = text.replace("live_job.py", "unknown.py", 1)
    with pytest.raises(ValueError, match="Unexpected worker stderr"):
        res.native_notices(text, program="live_job.py", count=72)


@pytest.mark.parametrize(
    "program,count", [("-c", 72), ("-m", 72), ("", 72), ("live_job.py", 0), ("live_job.py", True)]
)
def test_ambiguous_notice_context_refused(program, count):
    with pytest.raises(ValueError):
        res.native_notices("", program=program, count=count)


def test_saved_packet_native_hash_links():
    result = res.failed_packet()
    assert len(result["files_sha256"]) == 964
    assert (result["native_runs"], result["observer_pairs"], result["stream_records"]) == (
        36,
        18,
        20196,
    )
    assert result["artifact_bytes"] == 58017037
    assert result["new_native_runs"] == 0 and result["original_stays_failed"] is True
    assert result["independent_live_review_complete"] is False


@pytest.mark.parametrize("name", sorted(res.IDENTITIES))
def test_changed_original_identity_refused(tmp_path, monkeypatch, name):
    for key in res.IDENTITIES:
        shutil.copyfile(res.FAILED / key, tmp_path / key)
    with (tmp_path / name).open("ab") as file:
        file.write(b" ")
    monkeypatch.setattr(res, "FAILED", tmp_path)
    with pytest.raises(ValueError, match="Changed input"):
        res.failed_packet()


@pytest.fixture
def saved_stream(tmp_path):
    directory = tmp_path / "stream"
    shutil.copytree(res.FAILED / "native/04/stream", directory)
    return directory, ctx.read(directory / "manifest.json")


def test_changed_chunk_refused(saved_stream):
    directory, manifest = saved_stream
    path = directory / "chunk-00000000.bin.z"
    with path.open("r+b") as file:
        first = file.read(1)
        file.seek(0)
        file.write(bytes([first[0] ^ 1]))
    with pytest.raises(ValueError, match="Changed compressed chunk"):
        res.stream_links(directory, manifest)


@pytest.mark.parametrize("change", ["index", "manifest", "extra", "missing", "symlink"])
def test_incomplete_stream_refused(saved_stream, change):
    directory, manifest = saved_stream
    if change == "index":
        with (directory / "index.jsonl").open("ab") as file:
            file.write(b"\n")
    elif change == "manifest":
        manifest["peak_encoded_record_bytes"] += 1
    elif change == "extra":
        ctx.write(directory / "unregistered.json", {})
    elif change == "missing":
        (directory / "chunk-00000000.bin.z").rename(directory.parent / "held-chunk")
    else:
        (directory / "alias").symlink_to(directory / "manifest.json")
    try:
        with pytest.raises(ValueError):
            res.stream_links(directory, manifest)
    finally:
        if change == "symlink":
            (directory / "alias").unlink()


@pytest.mark.parametrize(
    "change",
    ["missing-row", "wrong-directory", "updates", "pair-order", "pair-records", "pair-mode"],
)
def test_native_reuse_coverage_refused(change):
    r = ctx.read(res.FAILED / "registration.json")
    result = ctx.read(res.FAILED / "native.json")
    first = result["records"][r["native_labels"][0]]
    if change == "missing-row":
        result["records"].pop(r["native_labels"][0])
    elif change == "wrong-directory":
        first["directory"] = "native/01"
    elif change == "updates":
        first["observed_updates"] -= 1
    elif change == "pair-order":
        result["observer_pairs"].reverse()
    elif change == "pair-records":
        result["observer_pairs"][0]["records"] -= 1
    else:
        result["observer_pairs"][0]["common_fields_only"] = False
    with pytest.raises(ValueError):
        res.native_rows(res.FAILED, r, result)


def test_detached_launch_binds_registration(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        job, "register", lambda output, checked: ctx.write(output / "registration.json", {})
    )
    monkeypatch.setattr(
        job.subprocess, "Popen", lambda command, **kw: calls.append((command, kw)) or NS(pid=123)
    )
    ack = job.launch(tmp_path, "software")
    command, options = calls[0]
    assert len(calls) == 1 and "execute" in command and "worker" not in command
    assert command[-2:] == ["--registration-sha", ctx.sha(tmp_path / "registration.json")]
    assert options["start_new_session"] is True and options["stdin"] == subprocess.DEVNULL
    assert ack["automatic_polling"] is False and ack["new_native_runs"] == 0
    assert ctx.read(tmp_path / "launch.json") == ack


def cells_result():
    return dict(
        status="matched_windows_pass_pending_independent_review",
        full_trajectories=24,
        window_runs=72,
        disk_recordings=18,
        restart_suffixes=6,
        restart_window_runs=6,
        zero_length_runs=6,
        sparse_schedule_controls=2,
        records={
            f"case-{i:02d}": dict(
                windows=3, recordings=3 if i < 6 else 0, restarts=1 if i < 6 else 0
            )
            for i in range(24)
        },
    )


def controller_setup(monkeypatch):
    r = dict(prior={}, reused_native={}, cells_keys=sorted(cells_result()["records"]))
    monkeypatch.setattr(job, "authenticate", lambda *_: r)
    monkeypatch.setattr(ctx, "prerequisite", lambda: {})
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda _: {0, 1, 2, 3})
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    return r


def test_controller_runs_only_cells(tmp_path, monkeypatch):
    controller_setup(monkeypatch)
    calls = []

    def run(command, out, err, timeout):
        calls.append(command)
        assert timeout == 750
        ctx.write(tmp_path / "cells.json", cells_result())

    monkeypatch.setattr(job, "run_child", run)
    job.execute(tmp_path, "registered")
    assert len(calls) == 1 and calls[0][0] == str(ctx.CELLS_PYTHON)
    assert calls[0][2] == str(Path(job.__file__).resolve()) and calls[0][3] == "worker"
    done = ctx.read(tmp_path / "completion.json")
    assert done["native_runs_reused"] == 36 and done["new_native_runs"] == 0
    assert done["original_attempt_stays_failed"] is True
    assert done["independent_live_review_complete"] is False
    assert done["automatic_followup"] is False
    ctx.hashes(tmp_path, done["files_sha256"])
    assert not any(p.name.startswith("native.") for p in tmp_path.iterdir())


@pytest.mark.parametrize("text", ["unexpected warning\n", "\n"])
def test_cells_stderr_not_ignored(tmp_path, monkeypatch, text):
    controller_setup(monkeypatch)

    def run(command, out, err, timeout):
        ctx.write(tmp_path / "cells.json", cells_result())
        err.write(text)

    monkeypatch.setattr(job, "run_child", run)
    with pytest.raises(ValueError, match="Unexpected Cells stderr"):
        job.execute(tmp_path, "registered")
    assert (tmp_path / "failure.json").is_file() and not (tmp_path / "completion.json").exists()


def test_failure_is_terminal(tmp_path, monkeypatch):
    calls = []

    def fail(*_):
        raise ValueError("changed evidence")

    monkeypatch.setattr(job, "authenticate", fail)
    monkeypatch.setattr(job, "run_child", lambda *_: calls.append("unexpected worker"))
    with pytest.raises(ValueError, match="changed evidence"):
        job.execute(tmp_path, "registered")
    first = ctx.sha(tmp_path / "failure.json")
    with pytest.raises(ValueError, match="already attempted"):
        job.execute(tmp_path, "registered")
    assert ctx.sha(tmp_path / "failure.json") == first and calls == []


@pytest.mark.parametrize("failure", ["timeout", "nonzero", "interrupt"])
def test_worker_group_timeout_cleanup(monkeypatch, failure):
    waited, killed = [], []

    def wait(timeout=None):
        waited.append(timeout)
        if timeout is not None:
            if failure == "timeout":
                raise subprocess.TimeoutExpired("worker", timeout)
            if failure == "interrupt":
                raise KeyboardInterrupt
            return 1
        return -9

    monkeypatch.setattr(job.subprocess, "Popen", lambda *a, **kw: NS(pid=77, wait=wait))
    monkeypatch.setattr(job.os, "killpg", lambda *args: killed.append(args))
    expected = {
        "timeout": subprocess.TimeoutExpired,
        "nonzero": subprocess.CalledProcessError,
        "interrupt": KeyboardInterrupt,
    }[failure]
    with pytest.raises(expected):
        job.run_child(["worker"], None, None, 3)
    assert waited == [3, None] and killed == [(77, job.signal.SIGKILL)]


@pytest.fixture
def authentication(tmp_path, monkeypatch):
    old = ctx.read(res.FAILED / "registration.json")
    r = dict(
        schema="cells.live_recording_continuation@1",
        decision="D127",
        duration_s=0.001,
        bounds=copy.deepcopy(ctx.BOUNDS),
        phases=["cells"],
        new_native_runs=0,
        production_changed=False,
        scientific_tolerances_changed=False,
        automatic_retry=False,
        automatic_followup=False,
        sources_sha256={"source": "digest"},
        software={"path": "checked"},
        reused_native={"sealed": True},
        **{k: old[k] for k in ("prior", "native_labels", "cells_keys")},
    )
    monkeypatch.setattr(res, "sources", lambda: {"source": "digest"})
    monkeypatch.setattr(ctx, "capsule", lambda *_: None)
    monkeypatch.setattr(job, "software", lambda _: {"path": "checked"})
    monkeypatch.setattr(res, "failed_packet", lambda: {"sealed": True})
    return r


@pytest.mark.parametrize(
    "change",
    [
        "registration",
        "sources",
        "native",
        "software",
        "phase",
        "duration",
        "bounds",
        "keys",
        "followup",
    ],
)
def test_continuation_authentication_refuses_changes(tmp_path, monkeypatch, authentication, change):
    r = authentication
    if change == "sources":
        r["sources_sha256"]["source"] = "changed"
    elif change == "native":
        r["reused_native"]["sealed"] = False
    elif change == "software":
        r["software"]["path"] = "wrong"
    elif change == "phase":
        r["phases"] = ["native", "cells"]
    elif change == "duration":
        r["duration_s"] = 0.01
    elif change == "bounds":
        r["bounds"]["cells_timeout_seconds"] += 1
    elif change == "keys":
        r["cells_keys"].pop()
    elif change == "followup":
        r["automatic_followup"] = True
    ctx.write(tmp_path / "registration.json", r)
    digest = "wrong" if change == "registration" else ctx.sha(tmp_path / "registration.json")
    with pytest.raises(ValueError):
        job.authenticate(tmp_path, digest)


def test_continuation_authentication_success(tmp_path, authentication):
    ctx.write(tmp_path / "registration.json", authentication)
    assert job.authenticate(tmp_path, ctx.sha(tmp_path / "registration.json")) == authentication


def test_no_science_import_in_controller():
    assert not any(
        name == root or name.startswith(root + ".")
        for root in ("cells", "betse", "jax")
        for name in sys.modules
    )


def test_software_evidence_roundtrip(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    output = root / "runs/checks"
    output.mkdir(parents=True)
    monkeypatch.setattr(ctx, "ROOT", root)
    monkeypatch.setattr(res, "sources", lambda: {"a": "b"})
    expected = dict(path="reports/test.xml", sha256="xml", tests=50)
    monkeypatch.setattr(job, "receipt", lambda _: expected)
    ctx.write(output / "registration.json", {})
    ctx.write(
        output / "completion.json",
        dict(
            status="continuation_software_pass",
            software=expected,
            sources_sha256={"a": "b"},
            files_sha256={"registration.json": ctx.sha(output / "registration.json")},
            pytest_internal_links={},
            full_campaign_launched=False,
            automatic_followup=False,
        ),
    )
    evidence = "runs/checks/completion.json"
    assert job.software(evidence) == dict(
        path=evidence, sha256=ctx.sha(output / "completion.json"), xml=expected
    )
    ctx.write(output / "extra.json", {})
    with pytest.raises(ValueError, match="Software artifacts changed"):
        job.software(evidence)


def test_existing_or_escaping_output_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx, "ROOT", tmp_path)
    directory = tmp_path / "runs/existing"
    directory.mkdir(parents=True)
    for path in (directory, tmp_path / "runs", tmp_path / "unscoped"):
        with pytest.raises(ValueError, match="Fresh continuation"):
            job.fresh(path)


def test_failed_launch_retains_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(
        job, "register", lambda output, checked: ctx.write(output / "registration.json", {})
    )

    def fail(*args, **kwargs):
        raise OSError("launch failed")

    monkeypatch.setattr(job.subprocess, "Popen", fail)
    with pytest.raises(OSError, match="launch failed"):
        job.launch(tmp_path, "checked")
    assert ctx.read(tmp_path / "launch-failure.json")["status"] == "not_launched"
    assert not (tmp_path / "launch.json").exists()
