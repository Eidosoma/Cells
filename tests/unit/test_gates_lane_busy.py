"""scripts/gates/lane_busy.py: the gate holders' lane check (D222's first fault, fixed).

The check it supersedes, in FR's landing-set holder, refused while any other unit pinned to the
lane was active. On 18 November 2026 at 19:32 it refused 8c2cb523's set for
cells-ops-b1-laneB-42ca1c94, a gate that was only waiting for lane B's lock. The new check charges
each process by its own affinity and its CPU time over the window (the lead's ruling):
- it refuses a unit computing on the lane without the lock, including the lead's plant: a unit with
  no pinning whose child is pinned to lane B and computing. It also refuses a child pinned onto lane
  B under a unit pinned elsewhere, and an unpinned process that computes (it may run on the lane);
- it ignores a unit that only waits: blocked in flock on the lane's lock (both flock forms, real
  processes), or idle;
- it leaves out the holder's own unit, and units with no process on the lane.
The readers run on real processes (an affinity and a spinning child's CPU time); the sampling runs
with systemd faked. No unit is started here.
"""

import fcntl
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gates" / "lane_busy.py"
LANE = set(range(8, 12)) | set(range(24, 28))
ALL = set(range(32))


@pytest.fixture(scope="module")
def lb():
    spec = importlib.util.spec_from_file_location("lane_busy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cpu_sets(lb):
    assert lb.cpu_set("8-11,24-27") == LANE == lb.cpu_set("8-11 24-27")
    assert lb.cpu_set("") == set() and lb.cpu_set("5") == {5}


def decide(lb, units, waiters=(), own=()):
    return lb.classify(units, set(waiters), window=10.0, threshold=0.05, own=set(own))


def test_a_unit_computing_on_the_lane_without_the_lock_is_busy(lb):
    out = decide(lb, {"cells-stray.service": [(5, {8}, 9.8)]})
    assert [r["unit"] for r in out["busy"]] == ["cells-stray.service"]  # The refusal is kept.
    assert out["busy"][0]["cpus_used"] == pytest.approx(0.98)


def test_the_19_32_refusal_is_a_waiter_now(lb):
    """cells-ops-b1-laneB-42ca1c94 (8-11 24-27), queued on lane B's lock: the old check refused the
    set for it; the new one counts it a lock waiter."""
    unit = "cells-ops-b1-laneB-42ca1c94.service"
    out = decide(lb, {unit: [(40, LANE, 0.0), (41, LANE, 0.01)]}, waiters={unit})
    assert out["busy"] == [] and [r["unit"] for r in out["waiters"]] == [unit]


def test_the_plant_an_unpinned_unit_whose_child_computes_pinned_to_the_lane(lb):
    """The unit's main process may run anywhere and idles; its child is pinned to CPU 8 and uses
    one CPU. The check that went by the unit's affinity left it out as unpinned."""
    out = decide(lb, {"cells-unpinned-parent.service": [(10, ALL, 0.0), (11, {8}, 9.9)]})
    assert [r["unit"] for r in out["busy"]] == ["cells-unpinned-parent.service"]
    assert out["busy"][0]["busiest"] == 11 and out["busy"][0]["cpus_used"] == pytest.approx(0.99)


def test_a_child_pinned_onto_the_lane_under_a_unit_pinned_elsewhere_is_busy(lb):
    out = decide(lb, {"cells-laneA-gate.service": [(20, {9, 25}, 8.0)]})
    assert [r["unit"] for r in out["busy"]] == ["cells-laneA-gate.service"]


def test_an_unpinned_computing_process_is_busy(lb):
    """Allowed on every CPU, it may run on the lane: charged (fail-closed)."""
    assert decide(lb, {"cells-anywhere.service": [(30, ALL, 4.0)]})["busy"]


def test_waiters_idle_units_and_the_holders_own(lb):
    units = {"cells-waiting.service": [(40, LANE, 0.0)],
             "cells-idle.service": [(50, {10}, 0.2)],
             "cells-holder.service": [(60, {8}, 9.0)],
             "cells-laneA.service": []}
    out = decide(lb, units, waiters={"cells-waiting.service"}, own={"cells-holder.service"})
    assert out["busy"] == []
    assert [r["unit"] for r in out["waiters"]] == ["cells-waiting.service"]
    assert [r["unit"] for r in out["idle"]] == ["cells-idle.service"]
    assert out["own"] == ["cells-holder.service"]
    listed = {r["unit"] for k in ("busy", "waiters", "idle") for r in out[k]}
    assert "cells-laneA.service" not in listed  # No process on the lane.


def test_the_threshold_is_a_fraction_of_one_cpu(lb):
    assert decide(lb, {"cells-a.service": [(1, {8}, 0.49)]})["busy"] == []  # 0.049 CPU.
    assert decide(lb, {"cells-a.service": [(1, {8}, 0.51)]})["busy"]  # 0.051 CPU.
    assert decide(lb, {"cells-a.service": [(1, {8}, 0.3), (2, {9}, 0.3)]})["busy"]  # Summed.


def test_a_waiter_that_computes_on_the_lane_is_busy(lb):
    """A flock waiter whose other process computes on the lane computes without the lock."""
    out = decide(lb, {"cells-w.service": [(1, LANE, 0.0), (2, {8}, 5.0)]},
                 waiters={"cells-w.service"})
    assert [r["unit"] for r in out["busy"]] == ["cells-w.service"] and out["waiters"] == []


# ----------------------------------------------------------------------- the readers, real


def test_a_processs_affinity_and_cpu_time(lb):
    cpu = min(os.sched_getaffinity(0))
    child = subprocess.Popen(
        [sys.executable, "-c", "while True: pass"],
        preexec_fn=lambda: os.sched_setaffinity(0, {cpu}))
    try:
        time.sleep(0.3)
        assert lb.proc_affinity(child.pid) == {cpu}
        first = lb.proc_cpu_seconds(child.pid)
        # It computes. Waiting for the CPU time, not a fixed wall time, keeps the claim true on a
        # shared CPU: a merged check on a loaded CPU gave the child 0.20 s in 0.8 s (19 November).
        deadline = time.time() + 30.0
        while lb.proc_cpu_seconds(child.pid) - first < 0.3 and time.time() < deadline:
            time.sleep(0.05)
        assert lb.proc_cpu_seconds(child.pid) - first >= 0.3
    finally:
        child.kill()
        child.wait()
    assert lb.proc_affinity(999999999) is None and lb.proc_cpu_seconds(999999999) is None


def started(proc, timeout=10.0):
    """Wait until the process's first argument is flock (it has exec'd)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        argv = Path(f"/proc/{proc.pid}/cmdline").read_bytes().split(b"\0")
        if os.path.basename(argv[0].decode()) == "flock":
            return
        time.sleep(0.05)
    raise AssertionError("flock did not start")


@pytest.mark.parametrize("form", ["argument", "descriptor"])
def test_a_process_blocked_in_flock_on_the_lock_is_a_waiter(lb, tmp_path, form):
    lock, other = tmp_path / "lane.lock", tmp_path / "other.lock"
    with open(lock, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)  # The holder: the waiter below blocks.
        if form == "argument":
            command = ["flock", str(lock), "sleep", "30"]
        else:  # exec 9> LOCK; flock 9 (the gates' form): the lock is a descriptor only.
            command = ["bash", "-c", 'exec 9> "$1"; exec flock 9', "_", str(lock)]
        waiter = subprocess.Popen(command)
        sleeper = subprocess.Popen(["sleep", "30"])
        try:
            started(waiter)
            assert lb.waits_on_lock([waiter.pid], lock)
            assert not lb.waits_on_lock([waiter.pid], other)  # Another lane's lock.
            assert not lb.waits_on_lock([sleeper.pid], lock)
            assert not lb.waits_on_lock([999999999], lock)  # A pid that has gone.
        finally:
            for p in (waiter, sleeper):
                p.kill()
                p.wait()


def test_cgroup_readers_on_a_fake_tree(lb, tmp_path):
    unit = tmp_path / "cells.slice" / "cells-a.service"
    (unit / "sub").mkdir(parents=True)
    (unit / "cgroup.procs").write_text("11\n12\n")
    (unit / "sub" / "cgroup.procs").write_text("13\n")
    assert sorted(lb.cgroup_pids("/cells.slice/cells-a.service", root=tmp_path)) == [11, 12, 13]
    assert lb.cgroup_pids("/cells.slice/gone.service", root=tmp_path) == []


def test_own_unit_from_the_cgroup_path(lb, tmp_path):
    path = tmp_path / "cgroup"
    path.write_text("0::/user.slice/user@1000.service/cells.slice/cells-gate.service\n")
    assert lb.own_unit(path) == "cells-gate.service"
    assert lb.own_unit(tmp_path / "missing") is None


# --------------------------------------------------------------- the sampling, faked systemd


def test_check_samples_usage_over_the_window(lb, monkeypatch, tmp_path):
    """cells-parent: unpinned, its child 2 pinned to CPU 8 and computing (the plant). cells-wait: a
    flock waiter. cells-born: a process born during the window, charged its whole time.
    cells-me: the caller, left out although it computes."""
    pids = {"cells-parent.service": {1: ALL, 2: {8}}, "cells-wait.service": {3: LANE},
            "cells-born.service": {4: {10}}, "cells-me.service": {5: {8}},
            "cells-laneA.service": {6: {0, 1}}}
    cpu = {1: [0.0, 0.01], 2: [3.0, 12.9], 3: [0.0, 0.0], 4: [None, 6.0], 5: [0.0, 9.0],
           6: [0.0, 40.0]}
    phase = {"n": 0}
    monkeypatch.setattr(lb, "active_units", lambda pattern="cells-*": list(pids))
    monkeypatch.setattr(lb, "unit_cgroup", lambda u: u)
    monkeypatch.setattr(lb, "cgroup_pids", lambda group: [
        p for p in pids[group] if not (p == 4 and phase["n"] == 0)])
    monkeypatch.setattr(lb, "proc_affinity", lambda pid: next(
        a for unit in pids.values() for p, a in unit.items() if p == pid))
    monkeypatch.setattr(lb, "proc_cpu_seconds", lambda pid: cpu[pid][phase["n"]])
    monkeypatch.setattr(lb, "waits_on_lock", lambda ps, lock: 3 in ps)
    monkeypatch.setattr(lb, "own_unit", lambda: "cells-me.service")

    def sleep(seconds):
        assert seconds == 10.0
        phase["n"] = 1

    out = lb.check(LANE, tmp_path / "lane.lock", window=10.0, sleep=sleep)
    assert [r["unit"] for r in out["busy"]] == ["cells-born.service", "cells-parent.service"]
    parent = next(r for r in out["busy"] if r["unit"] == "cells-parent.service")
    assert parent["cpus_used"] == pytest.approx(0.991) and parent["busiest"] == 2
    assert [r["unit"] for r in out["waiters"]] == ["cells-wait.service"]
    assert out["own"] == ["cells-me.service"]
    listed = {r["unit"] for k in ("busy", "waiters", "idle") for r in out[k]}
    assert "cells-laneA.service" not in listed and "cells-me.service" not in listed
