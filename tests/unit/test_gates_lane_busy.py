"""scripts/gates/lane_busy.py: the gate holders' lane check (D222's first fault, fixed).

The check it supersedes, in FR's landing-set holder, refused while any other unit pinned to the
lane was active. On 18 November 2026 at 19:32 it refused 8c2cb523's set for
cells-ops-b1-laneB-42ca1c94, a gate that was only waiting for lane B's lock. The new check:
- still refuses a unit computing on the lane without the lock (the plant);
- ignores a unit blocked in flock on the lane's lock, in both flock forms (argument and
  descriptor), with real processes;
- ignores a unit idle over the sampling window;
- leaves out units off the lane, and the holder's own;
- lists unpinned units without counting them, as the old check did.
The gathering is checked on a fake cgroup tree and with systemd faked: no unit is started here.
"""

import fcntl
import importlib.util
import os
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gates" / "lane_busy.py"
LANE = set(range(8, 12)) | set(range(24, 28))


@pytest.fixture(scope="module")
def lb():
    spec = importlib.util.spec_from_file_location("lane_busy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cpu_sets(lb):
    assert lb.cpu_set("8-11,24-27") == LANE == lb.cpu_set("8-11 24-27")
    assert lb.cpu_set("") == set() and lb.cpu_set("5") == {5}


def decide(lb, units, waiters=(), usage=None, own=(), prefixes=()):
    usage = usage if usage is not None else {n: 0.0 for n in units}
    return lb.classify(units, LANE, set(waiters), usage, window=10.0, threshold=0.05,
                       own=set(own), ignore_prefixes=prefixes)


def test_a_unit_computing_on_the_lane_without_the_lock_is_busy(lb):
    out = decide(lb, {"cells-stray.service": {8}}, usage={"cells-stray.service": 9.8})
    assert [r["unit"] for r in out["busy"]] == ["cells-stray.service"]  # The refusal is kept.
    assert out["busy"][0]["cpus_used"] == pytest.approx(0.98)


def test_the_19_32_refusal_is_a_waiter_now(lb):
    """cells-ops-b1-laneB-42ca1c94 (8-11 24-27), queued on lane B's lock: the old check refused the
    set for it; the new one counts it a lock waiter."""
    unit = "cells-ops-b1-laneB-42ca1c94.service"
    out = decide(lb, {unit: set(LANE)}, waiters={unit})
    assert out["busy"] == [] and [r["unit"] for r in out["waiters"]] == [unit]


def test_idle_off_lane_own_and_unpinned_units(lb):
    units = {"cells-idle.service": {9}, "cells-laneA.service": {0, 1, 2, 3},
             "cells-me.service": {8}, "cells-fr45-landingB-q8.service": {8},
             "cells-anywhere.service": set(), "cells-gone.service": {10}}
    usage = {"cells-idle.service": 0.2, "cells-laneA.service": 40.0, "cells-me.service": 9.0,
             "cells-fr45-landingB-q8.service": 9.0, "cells-anywhere.service": 50.0,
             "cells-gone.service": None}
    out = decide(lb, units, usage=usage, own={"cells-me.service"},
                 prefixes=("cells-fr45-landingB-",))
    assert out["busy"] == []
    assert [r["unit"] for r in out["idle"]] == ["cells-gone.service", "cells-idle.service"]
    assert out["own"] == ["cells-fr45-landingB-q8.service", "cells-me.service"]
    assert out["unpinned"] == ["cells-anywhere.service"]
    listed = {r["unit"] for k in ("busy", "waiters", "idle") for r in out[k]}
    assert "cells-laneA.service" not in listed  # Off the lane: not counted.


def test_the_threshold_is_a_fraction_of_one_cpu(lb):
    units = {"cells-a.service": {8}}
    assert decide(lb, units, usage={"cells-a.service": 0.49})["busy"] == []  # 0.049 CPU.
    assert decide(lb, units, usage={"cells-a.service": 0.51})["busy"]  # 0.051 CPU.


# --------------------------------------------------------------- flock waiters, real processes


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


# -------------------------------------------------------------- the gathering, faked systemd


def test_cgroup_readers_on_a_fake_tree(lb, tmp_path):
    unit = tmp_path / "cells.slice" / "cells-a.service"
    (unit / "sub").mkdir(parents=True)
    (unit / "cpu.stat").write_text("usage_usec 1234567\nuser_usec 1\n")
    (unit / "cgroup.procs").write_text("11\n12\n")
    (unit / "sub" / "cgroup.procs").write_text("13\n")
    group = "/cells.slice/cells-a.service"
    assert lb.cgroup_usage_usec(group, root=tmp_path) == 1234567
    assert sorted(lb.cgroup_pids(group, root=tmp_path)) == [11, 12, 13]
    assert lb.cgroup_usage_usec("/cells.slice/gone.service", root=tmp_path) is None
    assert lb.cgroup_pids("/cells.slice/gone.service", root=tmp_path) == []


def test_own_unit_from_the_cgroup_path(lb, tmp_path):
    path = tmp_path / "cgroup"
    path.write_text("0::/user.slice/user-1000.slice/user@1000.service/cells.slice/"
                    "cells-gate.service\n")
    assert lb.own_unit(path) == "cells-gate.service"
    path.write_text("0::/user.slice/user-1000.slice/session-3.scope\n")
    assert lb.own_unit(path) == "session-3.scope"
    assert lb.own_unit(tmp_path / "missing") is None


def test_check_samples_usage_over_the_window(lb, monkeypatch, tmp_path):
    units = {"cells-busy.service": "8-11 24-27", "cells-waiting.service": "8-11 24-27",
             "cells-idle.service": "10", "cells-laneA.service": "0-3 16-19"}
    usage = {u: [0, 0] for u in units}
    usage["cells-busy.service"] = [1_000_000, 11_000_000]  # 10 s in 10 s: one CPU.
    usage["cells-waiting.service"] = [5, 5]
    usage["cells-idle.service"] = [0, 100_000]  # 0.1 s in 10 s: 0.01 CPU.
    calls = {u: 0 for u in units}

    def read(group):
        unit = group.rsplit("/", 1)[-1]
        value = usage[unit][min(calls[unit], 1)]
        calls[unit] += 1
        return value

    monkeypatch.setattr(lb, "active_units", lambda pattern="cells-*": list(units))
    monkeypatch.setattr(lb, "unit_properties", lambda u: dict(
        CPUAffinity=units[u], ControlGroup=f"/cells.slice/{u}"))
    monkeypatch.setattr(lb, "cgroup_usage_usec", read)
    monkeypatch.setattr(lb, "cgroup_pids", lambda group: [group])
    monkeypatch.setattr(lb, "waits_on_lock", lambda pids, lock: "waiting" in pids[0])
    monkeypatch.setattr(lb, "own_unit", lambda: None)
    slept = []
    out = lb.check(LANE, tmp_path / "lane.lock", window=10.0, sleep=slept.append)
    assert slept == [10.0]
    assert [r["unit"] for r in out["busy"]] == ["cells-busy.service"]
    assert [r["unit"] for r in out["waiters"]] == ["cells-waiting.service"]
    assert [r["unit"] for r in out["idle"]] == ["cells-idle.service"]
    assert out["busy"][0]["cpus_used"] == pytest.approx(1.0)
