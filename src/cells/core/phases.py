"""Live phase markers of a run, and its timings grouped into phases.

Markers. The run paths (core.vector_windows, core.batch_windows, core.batch and
core.runner) report each phase as it ends: plan validation (per world for windowed
batches), binding (the worlds' states and layouts made resident), compile and the first
window, at INFO on the stdlib logger "cells.phases"; later windows at DEBUG. A marker is a
log record and nothing else: it is emitted on the host after values the run already
holds, adds no device synchronization and changes no result. With no handler attached
the records go nowhere (logging's last resort handler shows WARNING and above only);
enable() attaches one, for a driver's run log.

Phases. phase_totals(timings) groups a result's (or a sum of windows') existing timing
keys into preparation (planning, binding, per-window host preparation and compile),
execution (the host blocked on the device), observation (transfers, host checks and
observations) and output (the caller's sink). The groups are measured from the host
loop, so that they sum to its wall time: a vectorized run launches window k + 1 before
it analyses window k, so its execution is the host's wait for each window's summary
(device_wait_seconds), not the device's time from launch (execute_seconds, kept as
device_from_launch). Paths without that key run synchronously: execution is their
execute time.
"""

import logging
import sys
import time

LOGGER = logging.getLogger("cells.phases")

PREPARATION = (
    "preflight_seconds",
    "preparation_seconds",
    "static_preparation_seconds",
    "window_preparation_seconds",
)
COMPILE = ("compile_seconds", "compile_or_cache_seconds")
EXECUTION = ("execute_seconds", "untimed_warmup_seconds", "execute_samples_seconds")
WAIT = "device_wait_seconds"  # Vectorized windows: the host's wait (execute overlaps it).
OBSERVATION = ("host_transfer_seconds", "host_transfer_and_assembly_seconds", "analysis_seconds")
OUTPUT = ("sink_seconds",)
DERIVED = ("total_run_seconds", "round_seconds", "median_execute_seconds")


def _text(value):
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def mark(phase, **fields):
    """An INFO marker that phase has ended, with its fields (seconds, counts, ...)."""
    if LOGGER.isEnabledFor(logging.INFO):
        LOGGER.info(
            "%s %s",
            phase,
            " ".join(f"{k}={_text(v)}" for k, v in fields.items()),
            extra={"phase": phase, "fields": fields},
        )


def detail(phase, **fields):
    """The same at DEBUG (every later window)."""
    if LOGGER.isEnabledFor(logging.DEBUG):
        LOGGER.debug(
            "%s %s",
            phase,
            " ".join(f"{k}={_text(v)}" for k, v in fields.items()),
            extra={"phase": phase, "fields": fields},
        )


def enable(stream=None, level=logging.INFO):
    """Print markers (UTC time, phase, fields) to stream (default stderr).

    Idempotent per stream: a second call for the same stream returns its handler.
    """
    stream = sys.stderr if stream is None else stream
    for handler in LOGGER.handlers:
        if getattr(handler, "stream", None) is stream:
            LOGGER.setLevel(level)
            return handler
    handler = logging.StreamHandler(stream)
    formatter = logging.Formatter("%(asctime)sZ cells.phases %(message)s", "%Y-%m-%dT%H:%M:%S")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
    LOGGER.setLevel(level)
    return handler


def _seconds(value):
    return float(sum(value)) if isinstance(value, (list, tuple)) else float(value)


def phase_totals(timings, *, output_seconds=0.0):
    """Preparation (compile included), execution, observation and output seconds.

    timings: a result's timings, or window timings summed by key. output_seconds: output
    time the caller measured itself (a sink it called, snapshots it wrote), added to the
    timings' own sink_seconds. Keys outside the groups are listed under other, so a new
    key is never dropped silently; total_run_seconds, when present, gives unaccounted.
    """
    execution = (WAIT,) if WAIT in timings else EXECUTION
    groups = dict(preparation=PREPARATION + COMPILE, execution=execution, observation=OBSERVATION)
    out = {
        name: sum(_seconds(timings[k]) for k in keys if k in timings)
        for name, keys in groups.items()
    }
    if WAIT in timings:
        out["device_from_launch"] = _seconds(timings.get("execute_seconds", 0.0))
    out["compile"] = sum(_seconds(timings[k]) for k in COMPILE if k in timings)
    out["output"] = sum(_seconds(timings[k]) for k in OUTPUT if k in timings) + output_seconds
    known = set(PREPARATION + COMPILE + EXECUTION + OBSERVATION + OUTPUT + DERIVED + (WAIT,))
    out["other"] = {k: v for k, v in timings.items() if k not in known}
    if "total_run_seconds" in timings:
        measured = out["preparation"] + out["execution"] + out["observation"] + out["output"]
        out["unaccounted"] = float(timings["total_run_seconds"]) - measured
    return out
