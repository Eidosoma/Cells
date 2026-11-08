"""Sparse, flushed stage messages for the existing captured stdout log.

Call only at orchestration boundaries, never inside timestep or array loops.
These messages are diagnostic; the saved results remain the completion record.
"""

import sys
import time

_disabled = False


def start(label):
    return _write(label, "start", None)


def end(label, started, *, failed=False):
    if started is not None:
        _write(label, "failed" if failed else "returned", started)


def _write(label, event, started):
    global _disabled
    if _disabled:
        return None
    profile, trace = sys.getprofile(), sys.gettrace()
    try:
        now = time.monotonic()
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        elapsed = "" if started is None else f" elapsed={now - started:.3f}s"
        sys.stdout.write(f"[stage] {timestamp} {label} {event}{elapsed}\n")
        sys.stdout.flush()
    except Exception:
        # An unavailable log must not repeatedly interrupt a scientific run.
        # Observer rejection can clear a hook: it must propagate, never allow
        # subsequent work to proceed without the inherited observer.
        if sys.getprofile() is not profile or sys.gettrace() is not trace:
            raise
        _disabled = True
        return None
    if sys.getprofile() is not profile or sys.gettrace() is not trace:
        raise RuntimeError("Stage logging changed an inherited observer")
    return now
