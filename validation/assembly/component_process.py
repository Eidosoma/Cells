"""Run a qualification subprocess with sampled, live host-resource limits."""

import json
import math
import os
import signal
import subprocess
import time
import traceback
from pathlib import Path

from cells.assembly.cli import utc
from cells.assembly.io import write_json
from validation.ensemble.profile_cluster import memory_available, process_tree


class ProcessBudgetExceeded(RuntimeError):
    """A sampled memory/reserve or wall-time limit stopped the process group."""


def same_live_process(pid, start_ticks):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[19]) == start_ticks and fields[0] not in ("Z", "X")
    except (FileNotFoundError, ProcessLookupError):
        return False


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
):
    """Preserve a stop receipt before killing only this child's new process group.

    RSS is sampled, not a kernel allocation cap; allocations between samples can
    overshoot. The host reserve provides headroom. Reuse the ensemble sampler,
    including descendants and children spawned by non-main threads.
    """
    if (
        not math.isfinite(timeout)
        or timeout <= 0
        or not math.isfinite(sample_interval)
        or not 0 < sample_interval <= 1
        or type(max_rss_bytes) is not int
        or max_rss_bytes <= 0
        or type(min_available_bytes) is not int
        or min_available_bytes < 0
    ):
        raise ValueError("Invalid qualification process limits")
    began = time.monotonic()
    child = None
    peak, hwm, samples = 0, 0, 0
    minimum_available = None
    failure = None
    identities = {}
    limits = {
        "max_process_tree_rss_bytes": max_rss_bytes,
        "min_available_host_memory_bytes": min_available_bytes,
        "max_wall_seconds": timeout,
        "sample_interval_seconds": sample_interval,
    }
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
            # Do not start expensive work when the host reserve is already gone.
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
                available = memory_available()
                elapsed = time.monotonic() - began
                rss = sum(row["rss_bytes"] for row in rows)
                peak = max(peak, rss)
                hwm = max([hwm, *(row["hwm_bytes"] for row in rows)])
                minimum_available = (
                    available if minimum_available is None else min(minimum_available, available)
                )
                sample = {
                    "elapsed_seconds": elapsed,
                    "processes": rows,
                    "tree_rss_bytes": rss,
                    "available_memory_bytes": available,
                }
                stream.write(json.dumps(sample) + "\n")
                stream.flush()
                samples += 1
                reasons = []
                if rss > max_rss_bytes or hwm > max_rss_bytes:
                    reasons.append("process_tree_rss_allowance")
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
        # Also remove descendants if a failed pytest or compiler left them alive.
        # The session was created above; this cannot signal the supervisor.
        cleanup_failure = None
        if child is not None:
            try:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                # A descendant may have started its own session. Only signal
                # recorded descendants whose process identity still matches.
                for pid, identity in identities.items():
                    if same_live_process(pid, identity):
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                child.wait(timeout=10)
                deadline = time.monotonic() + 10
                while any(same_live_process(pid, value) for pid, value in identities.items()):
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
            directory / ("failure.json" if result["status"] == "failed" else "result.json"),
            result,
        )
        if cleanup_failure and not failure:
            raise RuntimeError("Qualification process-group cleanup failed: " + cleanup_failure)
    return result
