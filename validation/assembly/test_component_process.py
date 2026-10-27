"""Small real subprocesses exercise limits without approaching host exhaustion."""

import errno
import json
import os
import shutil
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


@pytest.mark.parametrize("private_copy", [False, True])
def test_pss_distinguishes_shared_fork_pages_from_private_growth(tmp_path, private_copy):
    # Both processes stay below the individual limit; copying inherited pages
    # crosses the tree limit, whereas sharing the exact same allocation does not.
    code = f"""
import os, time
from pathlib import Path
buffer = bytearray(48 * 1024**2)
pid = os.fork()
if pid == 0:
    Path('child.pid').write_text(str(os.getpid()))
    if {private_copy!r}:
        for i in range(0, len(buffer), 4096):
            buffer[i] = 1
    time.sleep(2)
    os._exit(0)
os.waitpid(pid, 0)
"""
    limit = 80 * 1024**2
    if private_copy:
        with pytest.raises(guard.ProcessBudgetExceeded, match="process_tree_pss_allowance"):
            execute(tmp_path, code, max_rss_bytes=limit, process_tree_memory_metric="pss")
        stop = json.loads((tmp_path / "resource-stop.json").read_text())
        assert stop["reasons"] == ["process_tree_pss_allowance"]
        assert stop["sample"]["tree_charged_memory_bytes"] > limit
        assert stopped(int((tmp_path / "child.pid").read_text()))
        result = json.loads((tmp_path / "failure.json").read_text())
    else:
        result = execute(tmp_path, code, max_rss_bytes=limit, process_tree_memory_metric="pss")
        assert result["sampled_peak_process_tree_rss_bytes"] > limit
        assert 48 * 1024**2 <= result["sampled_peak_charged_memory_bytes"] < limit
    assert result["process_tree_memory_metric"] == "pss"
    assert result["observed_process_high_water_bytes"] < limit
    assert result["rss_fallback_samples"] == 0
    assert result["limits"]["max_individual_process_rss_bytes"] == limit
    assert "max_process_tree_rss_bytes" not in result["limits"]


def test_pss_keeps_individual_rss_high_water_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        guard,
        "proportional_memory",
        lambda row: {"memory_accounting": "pss", "charged_memory_bytes": 1},
    )
    with pytest.raises(guard.ProcessBudgetExceeded, match="individual_process_rss_allowance"):
        execute(
            tmp_path,
            "import time; buffer=bytearray(48*1024**2); time.sleep(30)",
            max_rss_bytes=32 * 1024**2,
            process_tree_memory_metric="pss",
        )
    stop = json.loads((tmp_path / "resource-stop.json").read_text())
    assert stop["reasons"] == ["individual_process_rss_allowance"]
    assert stop["sample"]["tree_charged_memory_bytes"] == 1


@pytest.mark.parametrize("unavailable", ["permission", "missing_pss"])
def test_pss_unavailable_live_process_falls_back_to_rss(tmp_path, monkeypatch, unavailable):
    read = Path.read_text

    def restricted(path, *args, **kwargs):
        if path.name == "smaps_rollup":
            if unavailable == "permission":
                raise PermissionError("injected restriction")
            return "Rss: 64 kB\n"
        return read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", restricted)
    code = """
import os, time
buffer = bytearray(48*1024**2)
os.fork()
time.sleep(30)
"""
    with pytest.raises(guard.ProcessBudgetExceeded, match="process_tree_pss_allowance"):
        execute(tmp_path, code, max_rss_bytes=80 * 1024**2, process_tree_memory_metric="pss")
    stop = json.loads((tmp_path / "resource-stop.json").read_text())
    assert stop["sample"]["rss_fallback"]
    assert stop["sample"]["tree_charged_memory_bytes"] == stop["sample"]["tree_rss_bytes"]
    assert all(row["hwm_bytes"] < 80 * 1024**2 for row in stop["sample"]["processes"])


@pytest.mark.parametrize("content", ["Pss: -1 kB", "Pss: 10 MB", "Pss: 1 kB\nPss: 2 kB"])
def test_malformed_pss_stops_and_cleans_up(tmp_path, monkeypatch, content):
    read = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path, *args, **kwargs: (
            content if path.name == "smaps_rollup" else read(path, *args, **kwargs)
        ),
    )
    with pytest.raises(ValueError, match="Malformed"):
        execute(tmp_path, "import time; time.sleep(30)", process_tree_memory_metric="pss")
    result = json.loads((tmp_path / "failure.json").read_text())
    assert result["returncode"] == -9 and result["cleanup_traceback"] is None


def test_pss_accounts_for_hugetlb_and_exited_identity(monkeypatch):
    row = {"pid": 1, "start_ticks": 2, "rss_bytes": 4096}
    monkeypatch.setattr(guard, "same_live_process", lambda *args: True)
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path: "Pss: 10 kB\nPrivate_Hugetlb: 20 kB\nShared_Hugetlb: 30 kB\n",
    )
    result = guard.proportional_memory(row)
    assert result["pss_bytes"] == 10 * 1024
    assert result["hugetlb_bytes"] == 50 * 1024
    assert result["charged_memory_bytes"] == 60 * 1024
    identity = iter([True, False])  # Exited, or PID reused, while reading rollup.
    monkeypatch.setattr(guard, "same_live_process", lambda *args: next(identity))
    assert guard.proportional_memory(row) == {
        "memory_accounting": "exited",
        "charged_memory_bytes": 0,
    }


@pytest.mark.parametrize("value", [None, True, "", "uss", []])
def test_unknown_memory_metric_rejected_before_launch(tmp_path, value):
    with pytest.raises(ValueError, match="memory metric"):
        execute(
            tmp_path, "raise AssertionError('must not start')", process_tree_memory_metric=value
        )
    assert not (tmp_path / "process-started.json").exists()


@pytest.fixture
def shared_vm_program(tmp_path):
    """A small Linux CLONE_VM process, with an optional independent allocation."""
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("Native shared-address-space check requires a C compiler")
    try:
        assert guard.kcmp_vm(os.getpid(), os.getpid())
    except OSError as exc:
        pytest.skip(f"Native shared-address-space check requires kcmp: {exc}")
    source = tmp_path / "shared_vm.c"
    source.write_text(r"""
#define _GNU_SOURCE
#include <linux/kcmp.h>
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>
static int child(void *arg) {
    char **argv = arg;
    if (strcmp(argv[1], "exec") == 0) {
        usleep(250000);
        execl(argv[2], argv[2], "-B", "-c",
              "import time; data=bytearray(48*1024**2); time.sleep(2)", NULL);
        return 127;
    }
    sleep(2);
    return 0;
}
int main(int argc, char **argv) {
    volatile char *data = calloc(48 * 1024 * 1024, 1);
    char *stack = malloc(1024 * 1024);
    if (argc != 3 || !data || !stack) return 2;
    for (int i = 0; i < 48 * 1024 * 1024; i += 4096) data[i] = 1;
    pid_t shared = clone(child, stack + 1024 * 1024, CLONE_VM | SIGCHLD, argv);
    if (shared < 0) return 3;
    printf("kcmp_vm=%ld\n", syscall(SYS_kcmp, getpid(), shared, KCMP_VM, 0UL, 0UL));
    fflush(stdout);
    pid_t separate = 0;
    if (strcmp(argv[1], "distinct") == 0) {
        separate = fork();
        if (separate < 0) return 4;
        if (separate == 0) {
            for (int i = 0; i < 48 * 1024 * 1024; i += 4096) data[i] = 2;
            sleep(2);
            _exit(0);
        }
    }
    int status = 0;
    if (waitpid(shared, &status, 0) < 0 || status != 0) return 5;
    if (separate && (waitpid(separate, &status, 0) < 0 || status != 0)) return 6;
    return 0;
}
""")
    binary = tmp_path / "shared_vm"
    subprocess.run(
        [compiler, "-O2", "-Wall", "-Werror", "-o", str(binary), str(source)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    return binary


@pytest.mark.parametrize("mode", ["shared", "distinct", "exec", "denied", "rss"])
def test_real_shared_vm_is_counted_once_but_private_memory_still_stops(
    tmp_path, monkeypatch, shared_vm_program, mode
):
    if mode == "denied":

        def denied(*args):
            raise PermissionError(errno.EPERM, "injected kcmp restriction")

        monkeypatch.setattr(guard, "kcmp_vm", denied)
    limit = 80 * 1024**2
    options = dict(
        directory=tmp_path,
        cwd=tmp_path,
        env=dict(os.environ),
        timeout=5,
        max_rss_bytes=limit,
        min_available_bytes=0,
        sample_interval=0.01,
        process_tree_memory_metric="rss" if mode == "rss" else "pss",
    )
    command = [str(shared_vm_program), mode, sys.executable]
    if mode == "shared":
        result = guard.run_bounded(command, **options)
        assert result["shared_address_space_samples"] > 0
        assert result["sampled_peak_summed_process_memory_bytes"] > limit
        assert 48 * 1024**2 <= result["sampled_peak_charged_memory_bytes"] < limit
        assert result["observed_process_high_water_bytes"] < limit
    else:
        reason = "process_tree_rss_allowance" if mode == "rss" else "process_tree_pss_allowance"
        with pytest.raises(guard.ProcessBudgetExceeded, match=reason):
            guard.run_bounded(command, **options)
        stop = json.loads((tmp_path / "resource-stop.json").read_text())
        assert stop["reasons"] == [reason]
        sample = stop["sample"]
        assert sample["tree_charged_memory_bytes"] > limit
        assert all(row["hwm_bytes"] < limit for row in sample["processes"])
        assert all(stopped(row["pid"]) for row in sample["processes"])
        if mode == "distinct":
            assert len(sample["processes"]) == 3
            assert sample["shared_address_space_deduplicated"]
        if mode == "denied":
            assert not sample["shared_address_space_deduplicated"]
            assert all(
                c["before"]["status"] == "unavailable" for c in sample["address_space_comparisons"]
            )
    assert (tmp_path / "stdout.log").read_text() == "kcmp_vm=0\n"


@pytest.mark.parametrize("after", ["shared", "distinct", "unavailable", "identity_changed"])
@pytest.mark.parametrize("accounting", ["pss", "rss_fallback"])
def test_shared_vm_needs_stable_proof_and_valid_pss(monkeypatch, after, accounting):
    rows = [{"pid": 10, "start_ticks": 1}, {"pid": 11, "start_ticks": 2}]
    comparisons = iter([{"status": "shared"}, {"status": after}])
    monkeypatch.setattr(guard, "address_space_comparison", lambda *args: next(comparisons))
    monkeypatch.setattr(
        guard,
        "proportional_memory",
        lambda row: {
            "memory_accounting": accounting,
            "charged_memory_bytes": 100 if row["pid"] == 10 else 120,
        },
    )
    sample = guard.proportional_tree_memory(rows)
    assert sample["tree_summed_process_memory_bytes"] == 220
    merged = after == "shared" and accounting == "pss"
    assert sample["tree_charged_memory_bytes"] == (120 if merged else 220)
    assert sample["shared_address_space_deduplicated"] is merged
    assert [row["charged_memory_bytes"] for row in rows] == [100, 120]


def test_kcmp_confirmation_rejects_exited_or_reused_identity(monkeypatch):
    rows = [{"pid": 10, "start_ticks": 1}, {"pid": 11, "start_ticks": 2}]
    live = iter([True, True, True, False])
    monkeypatch.setattr(guard, "same_live_process", lambda *args: next(live))
    monkeypatch.setattr(guard, "kcmp_vm", lambda *args: True)
    assert guard.address_space_comparison(*rows) == {"status": "identity_changed"}
