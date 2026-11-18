"""Live phase markers of a run, and its timings grouped into phases.

Markers. The run paths (core.vector_windows, core.batch_windows, core.batch and
core.runner) report each phase as it ends: plan validation (per world for windowed
batches), binding (the worlds' states and layouts made resident), compile and the first
window, at INFO on the stdlib logger "cells.phases"; later windows at DEBUG. A marker is a
log record and nothing else: it is emitted on the host after values the run already
holds, adds no device synchronization and changes no result. With no handler attached
the records go nowhere (logging's last resort handler shows WARNING and above only);
enable() attaches one, for a driver's run log.

Start and failure records (D156; Recorder). Each run path also reports each of those
phases as it starts ("<phase>.start", at the level of its completion record), and writes
one failure record for any exception that leaves the path: "<phase>.failed" for the
innermost phase still open (with "within" its enclosing phase), or "failed after=<phase>"
when the exception is raised after the last phase's completion record (a refusal checked
after a phase ends, or a host check between phases). A failure record gives the seconds
since that phase started (or ended), the exception's type, and last its message on one
line; the exception propagates unchanged. Failure records are INFO, so they too go nowhere
without a handler. Like the completion records they read only host values and the host
clock. Their extra fields are phase, event ("start" or "failed"; completion records carry
none) and fields.

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

import contextlib
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


def _line(fields):
    return " ".join(f"{k}={_text(v)}" for k, v in fields.items())


def _message(error):
    """The exception's message on one line."""
    return " ".join(str(error).split())


class Recorder:
    """One run path's start, completion and failure records, host side only.

    start(phase) opens a phase and writes its start record; end(phase) closes it with the
    completion record mark or detail writes, unchanged. Used around a run path, ``with
    Recorder() as record:``, it writes one failure record for any Exception leaving the
    path (module docstring) and lets it propagate. GeneratorExit and the other
    BaseExceptions are not failures: an abandoned window iterator writes nothing.
    """

    def __init__(self):
        self._open = []  # (phase, started) of the open phases, innermost last.
        self._last = None  # (phase, ended) of the last phase closed.
        self._began = time.perf_counter()

    def start(self, phase, *, debug=False, **fields):
        self._open.append((phase, time.perf_counter()))
        level = logging.DEBUG if debug else logging.INFO
        if LOGGER.isEnabledFor(level):
            text = f"{phase}.start" + (f" {_line(fields)}" if fields else "")
            LOGGER.log(level, "%s", text, extra=dict(phase=phase, event="start", fields=fields))

    def end(self, phase, *, debug=False, **fields):
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == phase:
                del self._open[i:]  # Closing a phase closes any still open inside it.
                break
        self._last = (phase, time.perf_counter())
        (detail if debug else mark)(phase, **fields)

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        if isinstance(error, Exception):
            self.failed(error)
        return False

    def failed(self, error):
        """The failure record for error (__exit__ writes it; the caller re-raises)."""
        if not LOGGER.isEnabledFor(logging.INFO):
            return
        now = time.perf_counter()
        if self._open:
            phase, since = self._open[-1]
            name, fields = f"{phase}.failed", {}
            if len(self._open) > 1:
                fields["within"] = self._open[-2][0]
        elif self._last is not None:
            phase, since = self._last
            name, fields = "failed", {"after": phase}
        else:
            phase, since, name, fields = None, self._began, "failed", {}
        fields |= {"seconds": now - since, "error": type(error).__name__}
        message = _message(error)
        LOGGER.info(
            "%s %s message=%s",
            name,
            _line(fields),
            message,
            extra=dict(phase=phase, event="failed", fields=dict(fields, message=message)),
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


@contextlib.contextmanager
def enabled(stream=None, level=logging.INFO):
    """enable() for the duration of a block; the logger's handlers and level are restored."""
    handlers, previous = list(LOGGER.handlers), LOGGER.level
    handler = enable(stream, level)
    try:
        yield handler
    finally:
        if handler not in handlers:
            LOGGER.removeHandler(handler)
        LOGGER.setLevel(previous)


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
