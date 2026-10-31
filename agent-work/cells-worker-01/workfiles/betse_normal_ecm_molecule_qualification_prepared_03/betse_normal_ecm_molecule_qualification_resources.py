"""Literal existing subprocess resource guard with standalone stdlib adapters."""

import ctypes
import errno
import json
import math
import os
import signal
import subprocess
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def process_sample(pid, proc=Path("/proc")):
    """Read identity, CPU seconds and resident memory without counting threads twice."""
    directory = proc / str(pid)
    fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
    status = dict((line.split(":", 1) for line in (directory / "status").read_text().splitlines()))
    children = set()
    for task in (directory / "task").iterdir():
        try:
            children.update((int(p) for p in (task / "children").read_text().split()))
        except FileNotFoundError:
            pass
    return {
        "pid": pid,
        "start_ticks": int(fields[19]),
        "cpu_seconds": (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK"),
        "rss_bytes": int(status.get("VmRSS", "0").split()[0]) * 1024,
        "hwm_bytes": int(status.get("VmHWM", "0").split()[0]) * 1024,
        "children": sorted(children),
    }


def memory_available():
    return next(
        (
            int(line.split()[1]) * 1024
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith("MemAvailable:")
        )
    )


def process_tree(pid):
    pending, seen, rows = ([pid], set(), [])
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            row = process_sample(current)
        except (FileNotFoundError, ProcessLookupError):
            continue
        rows.append(row)
        pending.extend(row["children"])
    return rows


class ProcessBudgetExceeded(RuntimeError):
    """A sampled memory/reserve or wall-time limit stopped the process group."""


def same_live_process(pid, start_ticks):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[19]) == start_ticks and fields[0] not in ("Z", "X")
    except (FileNotFoundError, ProcessLookupError):
        return False


def memory_metric(value):
    if value not in ("rss", "pss"):
        raise ValueError("Process-tree memory metric must be rss or pss")
    return value


def proportional_memory(row):
    """Charge shared resident pages proportionally, with a conservative fallback.

    smaps_rollup excludes explicit hugetlb pages from PSS; charge those in full.
    Keep RSS/HWM untouched as separate observations. A vanished identity has no
    current resident charge; an unreadable live process falls back to its RSS.
    """
    pid, identity = (row["pid"], row["start_ticks"])
    if not same_live_process(pid, identity):
        return {"memory_accounting": "exited", "charged_memory_bytes": 0}
    try:
        content = Path(f"/proc/{pid}/smaps_rollup").read_text()
    except OSError as exc:
        if not same_live_process(pid, identity):
            return {"memory_accounting": "exited", "charged_memory_bytes": 0}
        return {
            "memory_accounting": "rss_fallback",
            "memory_accounting_error": type(exc).__name__,
            "charged_memory_bytes": row["rss_bytes"],
        }
    if not same_live_process(pid, identity):
        return {"memory_accounting": "exited", "charged_memory_bytes": 0}
    fields = {}
    for line in content.splitlines():
        name, _, value = line.partition(":")
        if name not in ("Pss", "Private_Hugetlb", "Shared_Hugetlb"):
            continue
        parts = value.split()
        if len(parts) != 2 or parts[1] != "kB" or (not parts[0].isdigit()) or (name in fields):
            raise ValueError("Malformed process proportional-memory sample")
        fields[name] = int(parts[0]) * 1024
    if "Pss" not in fields:
        return {
            "memory_accounting": "rss_fallback",
            "memory_accounting_error": "MissingPss",
            "charged_memory_bytes": row["rss_bytes"],
        }
    hugetlb = fields.get("Private_Hugetlb", 0) + fields.get("Shared_Hugetlb", 0)
    return {
        "memory_accounting": "pss",
        "pss_bytes": fields["Pss"],
        "hugetlb_bytes": hugetlb,
        "charged_memory_bytes": fields["Pss"] + hugetlb,
    }


def kcmp_vm(first, second):
    """Ask Linux whether two live processes currently share one mm_struct.

    glibc has no kcmp wrapper. These syscall numbers are the Linux x86-64 and
    arm64 ABIs; unsupported/denied calls retain the unmerged, conservative sum.
    """
    number = {"x86_64": 312, "aarch64": 272}.get(os.uname().machine)
    if number is None or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError(errno.ENOSYS, "Unsupported kcmp ABI")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    result = libc.syscall(
        ctypes.c_long(number),
        ctypes.c_int(first),
        ctypes.c_int(second),
        ctypes.c_int(1),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
    )
    if result < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))
    return result == 0


def address_space_comparison(first, second):
    """Bind each comparison to the sampled process identities, including exit."""

    def live():
        return all((same_live_process(row["pid"], row["start_ticks"]) for row in (first, second)))

    if not live():
        return {"status": "identity_changed"}
    try:
        shared = kcmp_vm(first["pid"], second["pid"])
    except OSError as exc:
        return {"status": "unavailable", "errno": exc.errno}
    if not live():
        return {"status": "identity_changed"}
    return {"status": "shared" if shared else "distinct"}


def proportional_tree_memory(rows):
    """Count a kernel-confirmed shared address space once, preserving raw samples.

    PSS apportions mappings, not task IDs: CLONE_VM/vfork children can expose the
    parent's entire PSS again. Merge only pairs confirmed shared both before and
    after all rollup reads, with unchanged live identities and usable PSS. Live
    sampling is not atomic; uncertain/changed/denied comparisons remain summed.
    Within each confirmed group charge the largest observation, never average.
    """
    comparisons = {}
    for i, row in enumerate(rows):
        for j in range(i):
            comparisons[j, i] = {
                "pids": [rows[j]["pid"], row["pid"]],
                "before": address_space_comparison(rows[j], row),
            }
    for row in reversed(rows):
        row.update(proportional_memory(row))
    for (i, j), comparison in comparisons.items():
        if comparison["before"]["status"] == "shared":
            comparison["after"] = address_space_comparison(rows[i], rows[j])
    groups = []
    for i, row in enumerate(rows):
        for group in groups:
            if all(
                (
                    row["memory_accounting"] == rows[j]["memory_accounting"] == "pss"
                    and comparisons[j, i]["before"]["status"] == "shared"
                    and (comparisons[j, i].get("after", {}).get("status") == "shared")
                    for j in group
                )
            ):
                group.append(i)
                break
        else:
            groups.append([i])
    charges = [
        {
            "pids": [rows[i]["pid"] for i in group],
            "charged_memory_bytes": max((rows[i]["charged_memory_bytes"] for i in group)),
        }
        for group in groups
    ]
    return {
        "tree_charged_memory_bytes": sum((group["charged_memory_bytes"] for group in charges)),
        "tree_summed_process_memory_bytes": sum((row["charged_memory_bytes"] for row in rows)),
        "shared_address_space_deduplicated": len(groups) < len(rows),
        "address_space_groups": charges,
        "address_space_comparisons": list(comparisons.values()),
    }


def run_bounded(
    command,
    *,
    directory,
    cwd,
    env,
    timeout,
    max_rss_bytes,
    min_available_bytes,
    sample_interval=0.25,
    process_tree_memory_metric="rss",
):
    """Preserve a stop receipt before killing only this child's new process group.

    Memory is sampled, not a kernel allocation cap; allocations between samples
    can overshoot. Default to summed RSS. Opt-in PSS avoids double charging shared
    fork pages and kernel-confirmed shared address spaces, while retaining the
    same individual RSS high-water limit and host reserve. Reuse the ensemble
    sampler, including children of non-main threads.
    """
    metric = memory_metric(process_tree_memory_metric)
    if (
        not math.isfinite(timeout)
        or timeout <= 0
        or (not math.isfinite(sample_interval))
        or (not 0 < sample_interval <= 1)
        or (type(max_rss_bytes) is not int)
        or (max_rss_bytes <= 0)
        or (type(min_available_bytes) is not int)
        or (min_available_bytes < 0)
    ):
        raise ValueError("Invalid qualification process limits")
    began = time.monotonic()
    child = None
    peak, charged_peak, hwm, samples, fallback_samples = (0, 0, 0, 0, 0)
    summed_peak, shared_samples = (0, 0)
    minimum_available = None
    failure = None
    identities = {}
    limits = {
        "process_tree_memory_metric": metric,
        "max_process_tree_memory_bytes": max_rss_bytes,
        "max_individual_process_rss_bytes": max_rss_bytes,
        "min_available_host_memory_bytes": min_available_bytes,
        "max_wall_seconds": timeout,
        "sample_interval_seconds": sample_interval,
    }
    if metric == "rss":
        limits["max_process_tree_rss_bytes"] = max_rss_bytes
    else:
        limits["pss_address_space_accounting"] = "kcmp_vm_bracketed_max"
    write_json(
        directory / "process-inputs.json",
        {"command": command, "cwd": str(cwd), "limits": limits, "utc": utc()},
    )
    try:
        with (
            (directory / "stdout.log").open("x") as out,
            (directory / "stderr.log").open("x") as err,
            (directory / "host-resources.jsonl").open("x") as stream,
        ):
            available = memory_available()
            if available < min_available_bytes:
                write_json(
                    directory / "resource-stop.json",
                    {
                        "reasons": ["available_host_memory_reserve"],
                        "available_memory_bytes": available,
                        "limits": limits,
                        "utc": utc(),
                    },
                )
                raise ProcessBudgetExceeded("Host memory reserve unavailable before launch")
            child = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=out,
                stderr=err,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
            write_json(
                directory / "process-started.json",
                {"pid": child.pid, "process_group": child.pid, "utc": utc()},
            )
            while True:
                rows = process_tree(child.pid)
                identities.update({row["pid"]: row["start_ticks"] for row in rows})
                accounting = proportional_tree_memory(rows) if metric == "pss" else {}
                available = memory_available()
                elapsed = time.monotonic() - began
                rss = sum((row["rss_bytes"] for row in rows))
                peak = max(peak, rss)
                charged = accounting.get("tree_charged_memory_bytes", rss)
                charged_peak = max(charged_peak, charged)
                summed_peak = max(
                    summed_peak, accounting.get("tree_summed_process_memory_bytes", rss)
                )
                shared_samples += int(accounting.get("shared_address_space_deduplicated", False))
                fallback = any((row.get("memory_accounting") == "rss_fallback" for row in rows))
                fallback_samples += int(fallback)
                hwm = max([hwm, *(row["hwm_bytes"] for row in rows)])
                minimum_available = (
                    available if minimum_available is None else min(minimum_available, available)
                )
                sample = {
                    "elapsed_seconds": elapsed,
                    "processes": rows,
                    "tree_rss_bytes": rss,
                    "tree_charged_memory_bytes": charged,
                    "process_tree_memory_metric": metric,
                    "rss_fallback": fallback,
                    "available_memory_bytes": available,
                    **accounting,
                }
                stream.write(json.dumps(sample) + "\n")
                stream.flush()
                samples += 1
                reasons = []
                if metric == "rss" and (rss > max_rss_bytes or hwm > max_rss_bytes):
                    reasons.append("process_tree_rss_allowance")
                if metric == "pss":
                    if charged > max_rss_bytes:
                        reasons.append("process_tree_pss_allowance")
                    if hwm > max_rss_bytes:
                        reasons.append("individual_process_rss_allowance")
                if available < min_available_bytes:
                    reasons.append("available_host_memory_reserve")
                if elapsed >= timeout:
                    reasons.append("wall_time_allowance")
                if reasons:
                    write_json(
                        directory / "resource-stop.json",
                        {"reasons": reasons, "sample": sample, "limits": limits, "utc": utc()},
                    )
                    raise ProcessBudgetExceeded(", ".join(reasons))
                code = child.poll()
                if code is not None:
                    if code:
                        raise subprocess.CalledProcessError(code, command)
                    break
                time.sleep(min(sample_interval, max(0, timeout - elapsed)))
            os.fsync(stream.fileno())
    except BaseException:
        failure = traceback.format_exc()
        raise
    finally:
        cleanup_failure = None
        if child is not None:
            try:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                for pid, identity in identities.items():
                    if same_live_process(pid, identity):
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                child.wait(timeout=10)
                deadline = time.monotonic() + 10
                while any((same_live_process(pid, value) for pid, value in identities.items())):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Recorded qualification descendants did not exit")
                    time.sleep(0.01)
            except BaseException:
                cleanup_failure = traceback.format_exc()
        result = {
            "status": "failed" if failure or cleanup_failure else "completed",
            "returncode": child.returncode if child is not None else None,
            "elapsed_seconds": time.monotonic() - began,
            "sampled_peak_process_tree_rss_bytes": peak,
            "sampled_peak_charged_memory_bytes": charged_peak,
            "sampled_peak_summed_process_memory_bytes": summed_peak,
            "shared_address_space_samples": shared_samples,
            "process_tree_memory_metric": metric,
            "rss_fallback_samples": fallback_samples,
            "observed_process_high_water_bytes": hwm,
            "minimum_available_host_memory_bytes": minimum_available,
            "samples": samples,
            "limits": limits,
            "utc": utc(),
            "automatic_retry": False,
        }
        if failure or cleanup_failure:
            result.update(traceback=failure, cleanup_traceback=cleanup_failure)
        write_json(
            directory / ("failure.json" if result["status"] == "failed" else "result.json"), result
        )
        if cleanup_failure and (not failure):
            raise RuntimeError("Qualification process-group cleanup failed: " + cleanup_failure)
    return result
