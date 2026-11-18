"""Which systemd units are computing on a gate lane without its lock: the refusal check of a gate
holder (D222's first fault, fixed; charged by process since the lead's ruling of 18 November 2026).

A holder takes its lane's lock (flock) and must not start while another unit computes on the
lane's CPUs without that lock: the other work would perturb the lane's timed or bitwise runs. The
check it supersedes (the holder of FR's landing set,
d172-restructure-20261115-01/fr45/judged-20261117/landing-laneB-holder.sh, kept byte for byte)
refused while any other unit pinned to the lane was active, even one that was only waiting for the
lock. On 18 November 2026 that refused core landings: 8c2cb523's set at 19:32, for a gate queued
on the lock. A unit that waits for the lock does not compute, and every unit that takes the lock is
serialised by it.

Each process is charged by its own affinity, not its unit's, so a child that is pinned onto the lane
under a unit pinned elsewhere (or not pinned at all) is seen. Over the sampling --window, every
process of every active unit (named `cells-*`) whose CPUs (/proc/PID/status Cpus_allowed_list)
meet the lane's is charged its CPU time (/proc/PID/stat utime and stime). A process born during the
window is charged all of its time, and one that ends during it cannot be charged. A process allowed
on every CPU meets the lane and is charged. A unit's charge is the sum, and then:
- the caller's own unit is the holder's, and is left out;
- a unit charged at least --threshold of one CPU over the window is computing on the lane without
  the lock: busy, and the caller refuses;
- any other unit with a process on the lane is listed: as a lock waiter when one of its processes
  is a flock that holds a descriptor on the lane's lock file or names it among its arguments, and
  as idle otherwise.

Usage:
  python3 lane_busy.py --cpus 8-11,24-27 --lock /path/lane.lock [--window 10] [--threshold 0.05]
                       [--json OUT]
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
PROC = Path("/proc")


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


def unit_cgroup(unit):
    shown = subprocess.run(["systemctl", "--user", "show", unit, "-p", "ControlGroup", "--value"],
                           capture_output=True, text=True, check=True).stdout
    return shown.strip()


def cgroup_pids(cgroup, root=CGROUP_ROOT):
    """Every process in the cgroup and its descendants."""
    pids, base = [], root / cgroup.lstrip("/")
    for procs in sorted(base.rglob("cgroup.procs")) if base.is_dir() else []:
        try:
            pids += [int(p) for p in procs.read_text().split()]
        except OSError:
            continue
    return pids


def proc_affinity(pid, proc=PROC):
    """The CPUs the process may run on (its Cpus_allowed_list), or None when it has gone."""
    try:
        for line in (proc / str(pid) / "status").read_text().splitlines():
            if line.startswith("Cpus_allowed_list:"):
                return cpu_set(line.split(":", 1)[1].strip())
    except OSError:
        return None
    return None


def proc_cpu_seconds(pid, proc=PROC):
    """The process's CPU time so far, all its threads (utime + stime), or None when it has gone."""
    try:
        text = (proc / str(pid) / "stat").read_text()
    except OSError:
        return None
    fields = text[text.rindex(")") + 2:].split()  # After "pid (comm) ": state is field 3.
    return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")  # Fields 14 and 15.


def waits_on_lock(pids, lock, proc=PROC):
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


def classify(units, waiters, window, threshold, own=()):
    """The decision, from gathered facts.

    units: {name: [(pid, affinity set, CPU seconds over the window)]}, each unit's processes on the
    lane; waiters: names with a flock on the lane's lock. Returns {busy, waiters, idle, own}, each
    unit's row giving its lane processes and the CPUs it used on them.
    """
    out = dict(busy=[], waiters=[], idle=[], own=[])
    for name in sorted(units):
        if name in own:
            out["own"].append(name)
            continue
        processes = units[name]
        if not processes:
            continue
        seconds = sum(s for _, _, s in processes)
        row = dict(unit=name, lane_processes=len(processes), cpus_used=seconds / window,
                   busiest=max(processes, key=lambda p: p[2])[0])
        if seconds / window >= threshold:
            out["busy"].append(row)
        elif name in waiters:
            out["waiters"].append(row)
        else:
            out["idle"].append(row)
    return out


def check(lane, lock, window=10.0, threshold=0.05, sleep=time.sleep):
    """Gather the facts from systemd, the cgroups and /proc, sample, and classify."""
    me = own_unit()
    groups = {}
    for name in active_units():
        if name == me:
            continue
        try:
            groups[name] = unit_cgroup(name)
        except subprocess.CalledProcessError:
            continue

    def on_lane(group):
        found = {}
        for pid in cgroup_pids(group):
            cpus = proc_affinity(pid)
            if cpus and cpus & lane:
                found[pid] = cpus
        return found

    before = {}
    for group in groups.values():
        for pid in on_lane(group):
            before[pid] = proc_cpu_seconds(pid)
    sleep(window)
    units, waiters = {}, set()
    for name, group in groups.items():
        processes = []
        for pid, cpus in on_lane(group).items():
            now = proc_cpu_seconds(pid)
            if now is None:
                continue  # Ended between the listing and the reading.
            was = before.get(pid)
            processes.append((pid, cpus, now - (was if was is not None else 0.0)))
        units[name] = processes
        if processes and waits_on_lock(cgroup_pids(group), lock):
            waiters.add(name)
    result = classify(units, waiters, window, threshold, own={me} if me else set())
    if me:
        result["own"] = [me]
    result.update(lane=sorted(lane), lock=str(lock), window_s=window, threshold_cpus=threshold)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cpus", required=True, help="the lane's CPUs, e.g. 8-11,24-27")
    p.add_argument("--lock", required=True, help="the lane's lock file")
    p.add_argument("--window", type=float, default=10.0, help="sampling window, seconds")
    p.add_argument("--threshold", type=float, default=0.05, help="idle below this many CPUs")
    p.add_argument("--json", help="write the classification here too")
    a = p.parse_args(argv)
    result = check(cpu_set(a.cpus), a.lock, a.window, a.threshold)
    text = json.dumps(result, indent=1)
    if a.json:
        Path(a.json).write_text(text + "\n")
    print(text)
    return 1 if result["busy"] else 0


if __name__ == "__main__":
    sys.exit(main())
