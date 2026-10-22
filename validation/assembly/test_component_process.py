"""Small real subprocesses exercise limits without approaching host exhaustion."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from validation.assembly import component_process as guard


def execute(tmp_path, code, **limits):
    return guard.run_bounded(
        [sys.executable, "-B", "-c", code],
        directory=tmp_path,
        cwd=tmp_path,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        timeout=limits.pop("timeout", 5),
        max_rss_bytes=limits.pop("max_rss_bytes", 128 * 1024**2),
        min_available_bytes=limits.pop("min_available_bytes", 0),
        sample_interval=0.01,
        **limits,
    )


def test_success_records_real_resources_and_logs(tmp_path):
    result = execute(tmp_path, "import time; print('complete', flush=True); time.sleep(0.1)")
    assert result["status"] == "completed" and result["samples"] >= 2
    assert result["sampled_peak_process_tree_rss_bytes"] > 0
    assert (tmp_path / "stdout.log").read_text() == "complete\n"
    assert not (tmp_path / "failure.json").exists()


def stopped(pid):
    try:
        # A killed grandchild may remain a zombie briefly until init reaps it.
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z"
    except FileNotFoundError:
        return True


@pytest.mark.parametrize("reason", ["memory", "wall"])
def test_live_limits_stop_entire_process_group_with_durable_receipts(tmp_path, reason):
    child_code = (
        "import os,time; from pathlib import Path; "
        "Path(str(os.getpid())+'.pid').write_text(str(os.getpid())); "
        "buffer=bytearray(32*1024**2); time.sleep(30)"
    )
    code = (
        "import subprocess,sys,time; "
        f"children=[subprocess.Popen([sys.executable,'-B','-c',{child_code!r}], "
        f"start_new_session={reason == 'wall'!r}) "
        "for _ in range(2)]; "
        "time.sleep(30)"
    )
    with pytest.raises(guard.ProcessBudgetExceeded):
        execute(
            tmp_path,
            code,
            max_rss_bytes=(70 if reason == "memory" else 256) * 1024**2,
            timeout=5 if reason == "memory" else 0.7,
        )
    failure = json.loads((tmp_path / "failure.json").read_text())
    stop = json.loads((tmp_path / "resource-stop.json").read_text())
    assert failure["status"] == "failed" and failure["returncode"] == -9
    assert failure["elapsed_seconds"] < 5
    assert not (tmp_path / "result.json").exists()
    expected = "process_tree_rss_allowance" if reason == "memory" else "wall_time_allowance"
    assert expected in stop["reasons"]
    assert len(stop["sample"]["processes"]) == 3
    if reason == "memory":
        assert all(p["hwm_bytes"] < 70 * 1024**2 for p in stop["sample"]["processes"])
        assert stop["sample"]["tree_rss_bytes"] > 70 * 1024**2
    pids = [int(path.read_text()) for path in tmp_path.glob("*.pid")]
    assert len(pids) == 2 and all(stopped(pid) for pid in pids)
    parent = json.loads((tmp_path / "process-started.json").read_text())["pid"]
    assert stopped(parent)


def test_nonzero_exit_preserves_error_output_and_failure(tmp_path):
    with pytest.raises(subprocess.CalledProcessError) as caught:
        execute(tmp_path, "import sys; print('expected fault', file=sys.stderr); sys.exit(7)")
    assert caught.value.returncode == 7
    assert (tmp_path / "stderr.log").read_text() == "expected fault\n"
    assert json.loads((tmp_path / "failure.json").read_text())["returncode"] == 7


def test_unavailable_host_reserve_prevents_start(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "memory_available", lambda: 1)
    with pytest.raises(guard.ProcessBudgetExceeded, match="before launch"):
        execute(tmp_path, "raise AssertionError('must not start')", min_available_bytes=2)
    assert not (tmp_path / "process-started.json").exists()
    assert (tmp_path / "resource-stop.json").is_file()
    assert (tmp_path / "failure.json").is_file()


def test_sampler_failure_closes_worker_and_keeps_failure(tmp_path, monkeypatch):
    def unavailable(pid):
        raise OSError("injected proc read failure")

    monkeypatch.setattr(guard, "process_tree", unavailable)
    with pytest.raises(OSError, match="injected"):
        execute(tmp_path, "import time; time.sleep(30)")
    failure = json.loads((tmp_path / "failure.json").read_text())
    assert "injected proc read failure" in failure["traceback"]
    assert failure["returncode"] == -9
    assert not (tmp_path / "result.json").exists()
