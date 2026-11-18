"""Which systemd units are computing on a gate lane without its lock: the refusal check of a gate
holder (D222's first fault, fixed).

A holder takes its lane's lock (flock) and must not start while another unit computes on the
lane's CPUs without that lock: the other work would perturb the lane's timed or bitwise runs. The
check it supersedes (the holder of FR's landing set,
d172-restructure-20261115-01/fr45/judged-20261117/landing-laneB-holder.sh, kept byte for byte)
refused while any other unit pinned to the lane was active, even one that was only waiting for the
lock. On 18 November 2026 that refused core landings: 8c2cb523's set at 19:32, for a gate queued
on the lock. A unit that waits for the lock does not compute, and every unit that takes the lock is
serialised by it.

So among the active units (named `cells-*`) whose CPU affinity meets the lane's CPUs:
- the caller's own unit, and units whose names start with an --ignore-prefix, are the holder's own;
- a unit with a process named flock that holds a descriptor on the lane's lock file, or names it
  among its arguments, is blocked in flock on the lane's lock: a lock waiter, ignored;
- a unit whose cgroup used less than --threshold of one CPU over the sampling --window is idle,
  ignored;
- any other unit is computing on the lane without the lock: busy, and the caller refuses.
A unit without a CPU affinity can run anywhere. Like the check it supersedes, this one does not
count such a unit against the lane, but it does list it.

Usage:
  python3 lane_busy.py --cpus 8-11,24-27 --lock /path/lane.lock [--ignore-prefix PREFIX ...]
                       [--window 10] [--threshold 0.05] [--json OUT]
Exit 0 when no unit is busy, 1 when one is (the classification printed as JSON either way).
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CGROUP_ROOT = Path("/sys/fs/cgroup")


def cpu_set(text):
    """{cpu} of an affinity or a list: "8-11,24-27", "8-11 24-27" or "" (none)."""
    out = set()
    for part in str(text or "").replace(" ", ",").split(","):
        if part:
            lo, _, hi = part.partition("-")
            out.update(range(int(lo), int(hi or lo) + 1))
    return out


def active_units(pattern="cells-*"):
    listed = subprocess.run(
        ["systemctl", "--user", "list-units", pattern, "--no-legend", "--plain", "--state=active"],
        capture_output=True, text=True, check=True).stdout
    return [line.split()[0] for line in listed.splitlines() if line.strip()]


def unit_properties(unit):
    """{property: value} of CPUAffinity and ControlGroup."""
    shown = subprocess.run(
        ["systemctl", "--user", "show", unit, "-p", "CPUAffinity", "-p", "ControlGroup"],
        capture_output=True, text=True, check=True).stdout
    return dict(line.split("=", 1) for line in shown.splitlines() if "=" in line)


def cgroup_usage_usec(cgroup, root=CGROUP_ROOT):
    """The cgroup's CPU time so far (cpu.stat usage_usec), or None when it has gone."""
    try:
        for line in (root / cgroup.lstrip("/") / "cpu.stat").read_text().splitlines():
            key, _, value = line.partition(" ")
            if key == "usage_usec":
                return int(value)
    except OSError:
        return None
    return None


def cgroup_pids(cgroup, root=CGROUP_ROOT):
    """Every process in the cgroup and its descendants."""
    pids, base = [], root / cgroup.lstrip("/")
    for procs in sorted(base.rglob("cgroup.procs")) if base.is_dir() else []:
        try:
            pids += [int(p) for p in procs.read_text().split()]
        except OSError:
            continue
    return pids


def waits_on_lock(pids, lock, proc=Path("/proc")):
    """True when one of the processes is a flock on the lock file (by descriptor or argument)."""
    lock = os.path.realpath(lock)
    for pid in pids:
        try:
            argv = (proc / str(pid) / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if not argv or os.path.basename(os.fsdecode(argv[0])) != "flock":
            continue
        if any(os.path.realpath(os.fsdecode(a)) == lock for a in argv[1:] if a):
            return True
        try:
            fds = list((proc / str(pid) / "fd").iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                if os.path.realpath(os.readlink(fd)) == lock:
                    return True
            except OSError:
                continue
    return False


def own_unit(proc_self=Path("/proc/self/cgroup")):
    """The systemd unit this process runs in, from its cgroup path (None outside a unit)."""
    try:
        path = proc_self.read_text().strip().split(":", 2)[-1]
    except OSError:
        return None
    units = [p for p in path.split("/") if p.endswith((".service", ".scope"))]
    return units[-1] if units else None


def classify(units, lane, waiters, usage, window, threshold, own=(), ignore_prefixes=()):
    """The decision, from gathered facts.

    units: {name: affinity set}; waiters: names blocked in flock on the lane's lock; usage:
    {name: CPU seconds over the window, or None}. Returns {busy, waiters, idle, own, unpinned}.
    """
    out = dict(busy=[], waiters=[], idle=[], own=[], unpinned=[])
    for name in sorted(units):
        cpus = units[name]
        if name in own or any(name.startswith(p) for p in ignore_prefixes):
            out["own"].append(name)
            continue
        if not cpus:
            out["unpinned"].append(name)
            continue
        if not cpus & lane:
            continue
        seconds = usage.get(name)
        load = None if seconds is None else seconds / window
        row = dict(unit=name, affinity=sorted(cpus), cpus_used=load)
        if name in waiters:
            out["waiters"].append(row)
        elif load is not None and load < threshold:
            out["idle"].append(row)
        elif load is None:  # Gone during the window: no longer on the lane.
            out["idle"].append(dict(row, note="ended during the window"))
        else:
            out["busy"].append(row)
    return out


def check(lane, lock, window=10.0, threshold=0.05, ignore_prefixes=(), sleep=time.sleep):
    """Gather the facts from systemd, the cgroups and /proc, sample, and classify."""
    units, groups = {}, {}
    for name in active_units():
        try:
            props = unit_properties(name)
        except subprocess.CalledProcessError:
            continue
        units[name] = cpu_set(props.get("CPUAffinity", ""))
        groups[name] = props.get("ControlGroup", "")
    candidates = [n for n, c in units.items() if c & lane and groups.get(n)]
    before = {n: cgroup_usage_usec(groups[n]) for n in candidates}
    sleep(window)
    after = {n: cgroup_usage_usec(groups[n]) for n in candidates}
    usage = {n: None if before[n] is None or after[n] is None else (after[n] - before[n]) / 1e6
             for n in candidates}
    waiters = {n for n in candidates if waits_on_lock(cgroup_pids(groups[n]), lock)}
    me = own_unit()
    result = classify(units, lane, waiters, usage, window, threshold,
                      own={me} if me else set(), ignore_prefixes=ignore_prefixes)
    result.update(lane=sorted(lane), lock=str(lock), window_s=window, threshold_cpus=threshold)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cpus", required=True, help="the lane's CPUs, e.g. 8-11,24-27")
    p.add_argument("--lock", required=True, help="the lane's lock file")
    p.add_argument("--ignore-prefix", action="append", default=[])
    p.add_argument("--window", type=float, default=10.0, help="sampling window, seconds")
    p.add_argument("--threshold", type=float, default=0.05, help="idle below this many CPUs")
    p.add_argument("--json", help="write the classification here too")
    a = p.parse_args(argv)
    result = check(cpu_set(a.cpus), a.lock, a.window, a.threshold, tuple(a.ignore_prefix))
    text = json.dumps(result, indent=1)
    if a.json:
        Path(a.json).write_text(text + "\n")
    print(text)
    return 1 if result["busy"] else 0


if __name__ == "__main__":
    sys.exit(main())
