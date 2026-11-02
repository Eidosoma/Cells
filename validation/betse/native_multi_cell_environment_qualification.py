"""Reviewed, guarded fresh multi-cell ordinary prefix through make_maskM.

Preparation and software controls do not run source. A separate exact release
is required for each actual diagnostic. Saved owners are evidence, never inputs
for object hydration. Nine ordinary methods share one actual issued caller.
"""

import argparse
import copy
import hashlib
import importlib.abc
import json
import marshal
import os
import resource
import runpy
import sys
import time
import traceback
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import CodeType, MappingProxyType

from validation import source_snapshot
from validation.betse import native_multi_cell_caller_qualification as prior
from validation.betse import native_multi_cell_environment_native as native
from validation.betse import native_single_cell_prefix_payload as payload

shared = prior.shared
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/native_multi_cell_environment_qualification.py"
FILES = tuple(
    "validation/betse/native_multi_cell_environment_" + name + ".py"
    for name in ("qualification", "native", "compare")
)
TESTS = tuple(
    "tests/unit/test_native_multi_cell_environment_" + name + ".py"
    for name in ("qualification", "native", "compare")
)
PAYLOAD_TEST = "tests/unit/test_native_single_cell_prefix_payload.py"
WORKLOG_TEST = "tests/unit/test_native_single_cell_prefix_qualification.py"
CASES, ENDPOINT = prior.CASES, native.ENDPOINT
STAGES = (*prior.STAGES[:6], "ordinary_request", "cell_index", "make_maskM")
KINDS = ("cells.multi_environment_diagnostic_plan@1", "cells.multi_environment_release@1")
PURPOSE = "fresh_multi_cell_ordinary_source_diagnostic_only"
CONTROLS = prior.CONTROLS
CAPTURE_POLICY = dict(
    ordinary_metadata_bytes=payload.MAX_METADATA,
    request_metadata_bytes=payload.REQUEST_METADATA,
    request_label="ordinary_request",
    request_filename="capture-0006.json",
    request_fields=["caller_request", "identity"],
    caller_request_fields=[
        "lifecycle_request",
        "lifecycle_state",
        "configuration_json",
        "identity",
        "grid_descriptor",
    ],
)
SOFTWARE_GROUPS = {
    "all": "",
    "runtime-integration": "runtime_namespace",
    "numpy-integration": "numpy_helper",
    "source-repairs": "repair_c or numpy_helper",
    "capture-metadata": "capture_metadata or failed_capture_stops or repair_c5 or prefix_payload",
    "stage-timing": "stage_timing or failed_capture_stops or repair_c5",
    "worklog": "",
    "authority-timing": "",
}
AUTHORITY_TIMING_POLICY = dict(
    kind="cells.exact_function_timing@1",
    max_targets=32,
    max_active=64,
    max_snapshots=512,
    max_events=2**63 - 1,
    max_snapshot_bytes=256 * 2**10,
    clock_stride=4096,
    periodic_ns=5 * 10**9,
    max_raw_errors=32,
)


def _authority_targets():
    """Read already-loaded bindings only; no imports, proxies or source calls."""
    prefix = "cells.processes.betse_native_multi_cell_"
    environment, multi = (sys.modules.get(prefix + name) for name in ("environment", "caller"))
    if environment is None or multi is None or vars(environment).get("multi") is not multi:
        raise ValueError("Actual loaded ordinary environment/caller modules required")
    selected = []
    for owner, names in (
        (
            environment,
            (
                "_check",
                "_verify_sources",
                "_immutable_graphs",
                "_immutable_state",
                "_active_tree",
                "_new_tree",
                "_tree_call",
                "_operation",
                "_TREE_INIT",
                "_TREE_QUERY",
                "_TREE_BALL",
            ),
        ),
        (multi, ("_check", "_verify_sources")),
    ):
        namespace = vars(owner)
        for name in names:
            selected.append((owner.__name__ + "." + name, namespace, name))
    tree = vars(environment).get("_TreeRuntime")
    if not isinstance(tree, type):
        raise ValueError("Actual loaded ordinary tree wrapper required")
    for name in ("__init__", "query", "query_ball_point"):
        selected.append((environment.__name__ + "._TreeRuntime." + name, vars(tree), name))
    return tuple(selected)


class AuthorityTimings:
    """Bounded metadata observation of exact loaded bindings, never authority.

    Python return events include exception unwinds. Inclusive durations overlap
    and include observer/guard costs. Event-driven periodic writes cannot run
    while a native call emits no profile events. No arguments/results are read.
    Own observation failures are deferred to protected outer boundaries; the
    prior profiler's rejections are always propagated immediately and unchanged.
    """

    def __init__(self, output, work, targets):
        self.work, self.folder = work, Path(output) / "authority-timings"
        self.policy = dict(AUTHORITY_TIMING_POLICY)
        self.targets, self.by_code, self.by_callable = [], {}, {}
        self.stack, self.rows, self.failure = [], [], None
        self.events = self.sequence = 0
        self.last_checkpoint = self.last_wall = self.last_cpu = None
        self.active_profile = None
        self.installed = False
        self.used = False
        self.ready = False
        self.bookkeeping_depth = self.suppressed_own_events = 0
        self.raw_errors, self.raw_records, self.pending_cleanup_errors = [], [], []
        self.lifecycle = dict(
            setup_error=None,
            cleanup_errors=[],
            cleanup_attempts=[],
            hooks_before_cleanup=None,
            hooks_after_cleanup=None,
            final_capture_attempted=False,
            final_capture_error=None,
            final_capture_blocked=None,
            raw_cleanup_error_count=0,
        )
        if type(targets) is not tuple or not 0 < len(targets) <= self.policy["max_targets"]:
            raise ValueError("Bounded nonempty exact-function timing targets required")
        labels = set()
        for label, namespace, name in targets:
            if (
                type(label) is not str
                or not 0 < len(label) <= 200
                or label in labels
                or type(name) is not str
                or not 0 < len(name) <= 100
                or type(namespace) not in (dict, MappingProxyType)
            ):
                raise ValueError("Invalid or duplicate timing target label")
            labels.add(label)
            value = namespace.get(name)
            if not callable(value):
                raise ValueError("Unavailable exact timing callable: " + label)
            code = getattr(value, "__code__", None)
            code = code if type(code) is CodeType else None
            globals_ = getattr(value, "__globals__", None)
            if code is not None and (id(code) in self.by_code or len(code.co_filename) > 1024):
                raise ValueError("Ambiguous or overlong timing code target")
            if id(value) in self.by_callable:
                raise ValueError("Duplicate timing callable identity")
            index = len(self.targets)
            self.targets.append((namespace, name, value, code, globals_))
            if code is not None and type(globals_) is dict:
                self.by_code[id(code)] = index
            self.by_callable[id(value)] = index
            self.rows.append(
                dict(
                    target=label,
                    callable_type=type(value).__module__ + "." + type(value).__qualname__,
                    code_file=None if code is None else code.co_filename,
                    code_line=None if code is None else code.co_firstlineno,
                    code_sha256=None
                    if code is None
                    else hashlib.sha256(marshal.dumps(code)).hexdigest(),
                    entries=0,
                    observed_returns=0,
                    observed_c_exceptions=0,
                    inclusive_wall_ns=0,
                    inclusive_process_cpu_ns=0,
                )
            )
        self.folder.mkdir()

    def _verify(self, index=None):
        targets = self.targets if index is None else (self.targets[index],)
        for namespace, name, value, code, globals_ in targets:
            if (
                namespace.get(name) is not value
                or (code is not None and getattr(value, "__code__", None) is not code)
                or getattr(value, "__globals__", None) is not globals_
            ):
                raise ValueError("Retained timing callable/code binding changed: " + name)

    def _clock(self):
        # An outer sample itself emits c_return events. Do not recursively
        # update last_wall between its wall and CPU reads. The profile hook
        # still invokes the inherited guard for every one of these events.
        self.bookkeeping_depth += 1
        try:
            wall, cpu = time.monotonic_ns(), time.process_time_ns()
            if (
                type(wall) is not int
                or type(cpu) is not int
                or wall < 0
                or cpu < 0
                or (self.last_wall is not None and (wall < self.last_wall or cpu < self.last_cpu))
            ):
                raise ValueError("Invalid authority timing clocks")
            self.last_wall, self.last_cpu = wall, cpu
            return wall, cpu
        finally:
            self.bookkeeping_depth -= 1

    def _error_record(self, error):
        # No formatting, type-name lookup, repr or user callback here. This
        # path also runs while CPython has cleared a rejecting profiler.
        if len(self.raw_errors) >= self.policy["max_raw_errors"]:
            return dict(raw_retention_limit_reached=True, exception_rendered=False)
        record = dict(raw_error_index=len(self.raw_errors), exception_rendered=False)
        self.raw_errors.append(error)
        self.raw_records.append(record)
        return record

    def _render_errors(self, previous, trace):
        # This is called only between independently protected restoration and
        # capture. Check again around every potentially user-defined __str__.
        for error, record in zip(self.raw_errors, self.raw_records, strict=True):
            if record["exception_rendered"]:
                continue
            if sys.getprofile() is not previous or sys.gettrace() is not trace:
                raise RuntimeError("Inherited hooks unavailable for exception formatting")
            rendered = shared.exception_record(error)
            if sys.getprofile() is not previous or sys.gettrace() is not trace:
                raise RuntimeError("Inherited hooks changed during exception formatting")
            record.update(error=rendered, exception_rendered=True)

    def _failed(self, error, origin):
        if self.failure is None:
            self.failure = error
            record = dict(origin=origin, error=self._error_record(error))
            self.failure_record = record
            if self.work.failure is None:
                self.work.failure = record

    def _snapshot(self, reason, now=None):
        self.bookkeeping_depth += 1
        try:
            return self._snapshot_record(reason, now)
        finally:
            self.bookkeeping_depth -= 1

    def _snapshot_record(self, reason, now):
        if self.sequence >= self.policy["max_snapshots"]:
            raise ValueError("Authority timing snapshot allowance exceeded")
        if type(reason) is not str or not 0 < len(reason) <= 200:
            raise ValueError("Invalid authority timing boundary")
        self._verify()
        wall, cpu = self._clock() if now is None else now
        inflight = [
            dict(
                target=self.rows[index]["target"],
                event=event,
                entered_monotonic_ns=started[0],
                entered_process_cpu_ns=started[1],
                elapsed_wall_ns=wall - started[0],
                elapsed_process_cpu_ns=cpu - started[1],
            )
            for frame, index, event, started in self.stack
        ]
        row = dict(
            **self.policy,
            sequence=self.sequence,
            reason=reason,
            phase=self.work.phase,
            monotonic_ns=wall,
            process_cpu_ns=cpu,
            observed_profile_events=self.events,
            targets=self.rows,
            active_frames=inflight,
            observation_failed=self.failure is not None,
            observation_failure=getattr(self, "failure_record", None),
            own_bookkeeping_profile_events_suppressed=self.suppressed_own_events,
            hook_lifecycle=self.lifecycle,
            return_event_is_success=False,
            inclusive_times_are_additive=False,
            includes_observer_and_chained_guard_cost=True,
            periodic_checkpoint_requires_profile_events=True,
            delegate_zero_events_is_execution_unknown=True,
            python_identity_scope=(
                "Retained callable binding plus observed code/global identity; identical "
                "code/global clones are not distinguishable by profiling."
            ),
            scientific_values_observed=False,
            independent_case_credit=0,
        )
        if len(json.dumps(row, allow_nan=False).encode()) > self.policy["max_snapshot_bytes"]:
            raise ValueError("Authority timing metadata byte allowance exceeded")
        path = self.folder / f"{self.sequence:04d}.json"
        self.sequence += 1
        shared.write(path, row)
        self.last_checkpoint = wall

    def checkpoint(self, reason):
        try:
            if self.failure is not None:
                raise self.failure
            if self.ready and (
                sys.getprofile() is not self.active_profile
                or sys.gettrace() is not self.entry_trace
            ):
                raise ValueError("Authority timing hooks changed at outer boundary")
            self._snapshot(reason)
        except BaseException as error:
            self._failed(error, "boundary:" + reason)
            raise TimingObservationFailed(
                error, label=self.work.phase or "imports", operation="authority_timing"
            ) from error

    def _event(self, frame, event, arg):
        if self.events >= self.policy["max_events"]:
            raise ValueError("Authority timing event allowance exceeded")
        self.events += 1
        index = None
        if event in ("call", "return"):
            index = self.by_code.get(id(frame.f_code))
            if index is not None and (
                frame.f_code is not self.targets[index][3]
                or frame.f_globals is not self.targets[index][4]
            ):
                raise ValueError("Timing code entered with foreign code/globals")
        elif event in ("c_call", "c_return", "c_exception"):
            index = self.by_callable.get(id(arg))
            if index is not None and self.targets[index][2] is not arg:
                raise ValueError("Timing callable identity changed")
        now, first = None, False
        if index is not None:
            self._verify(index)
            now = self._clock()
            row = self.rows[index]
            if event in ("call", "c_call"):
                if len(self.stack) >= self.policy["max_active"]:
                    raise ValueError("Authority timing active-frame allowance exceeded")
                first = row["entries"] == 0
                row["entries"] += 1
                self.stack.append((frame, index, event, now))
            else:
                if not self.stack or self.stack[-1][:2] != (frame, index):
                    raise ValueError("Unmatched authority timing return")
                _, _, entered, started = self.stack.pop()
                if (entered == "call") != (event == "return"):
                    raise ValueError("Changed authority timing return category")
                row["observed_returns"] += int(event != "c_exception")
                row["observed_c_exceptions"] += int(event == "c_exception")
                row["inclusive_wall_ns"] += now[0] - started[0]
                row["inclusive_process_cpu_ns"] += now[1] - started[1]
        if now is None and self.events % self.policy["clock_stride"] == 0:
            now = self._clock()
        if now is not None and (
            first
            or self.last_checkpoint is None
            or now[0] - self.last_checkpoint >= self.policy["periodic_ns"]
        ):
            self._snapshot("first-target-entry" if first else "periodic", now)

    @contextmanager
    def active(self):
        if self.installed or self.used:
            raise ValueError("Authority timing observer cannot be reentered or reused")
        self.used = True
        previous, trace = sys.getprofile(), sys.gettrace()
        self.entry_trace = trace

        def profile(frame, event, arg):
            if previous is not None:
                try:
                    previous(frame, event, arg)
                except BaseException as primary:
                    self._failed(primary, "previous_profile")
                    raise
            if self.bookkeeping_depth:
                self.suppressed_own_events += 1
            elif self.failure is None:
                try:
                    self._event(frame, event, arg)
                except BaseException as error:
                    # Do not turn a Python exception-unwind return into an
                    # observer exception. Protected outer checkpoints stop
                    # continuation and preserve any already returned object.
                    self._failed(error, "profile_observation")

        self.installed, self.active_profile = True, profile
        primary, phase = None, "setup"
        try:
            self.checkpoint("observer-enter")
            sys.setprofile(profile)
            self.ready = True
            phase = "source"
            yield
            phase = "returned"
        except BaseException as error:
            primary = error
            if phase == "setup":
                self.pending_cleanup_errors.append(("setup", error))
                try:
                    self.lifecycle["setup_error"] = self._error_record(error)
                    self._failed(error, "setup")
                except BaseException as recording:
                    self.pending_cleanup_errors.append(("setup_recording", recording))
                    self.lifecycle["setup_error"] = dict(recording_failed=True)
            raise
        finally:
            self.bookkeeping_depth += 1
            self.ready = False
            try:
                before = self._hook_state(previous, trace)
                self.lifecycle["hooks_before_cleanup"] = before
                if primary is None and (
                    before["profile"] != "observer" or before["trace"] != "entry"
                ):
                    self.pending_cleanup_errors.append(
                        ("profile_exit", ValueError("Authority timing profiler was not restored"))
                    )
            except BaseException as error:
                self.pending_cleanup_errors.append(("entry_state", error))
            # Each hook gets its own bounded restoration attempts, even if
            # the other setter fails before OR after changing the real hook.
            for name, expected in (("profile", previous), ("trace", trace)):
                try:
                    self._restore_hook(name, expected, "before_capture")
                except BaseException as error:
                    self.pending_cleanup_errors.append(("before_capture:" + name + ":entry", error))
            try:
                state = self._hook_state(previous, trace)
                if state["profile"] != "entry" or state["trace"] != "entry":
                    self.lifecycle["final_capture_blocked"] = "Inherited hooks not restored"
                else:
                    for origin, error in self.pending_cleanup_errors:
                        record = dict(origin=origin, error=self._error_record(error))
                        self.lifecycle["cleanup_errors"].append(record)
                        if self.failure is None:
                            self.failure, self.failure_record = error, record
                        if self.work.failure is None:
                            self.work.failure = record
                    self._render_errors(previous, trace)
                    self.lifecycle["final_capture_attempted"] = True
                    self._snapshot("observer-exit")
            except BaseException as error:
                self.pending_cleanup_errors.append(("final_capture", error))
                self.lifecycle["final_capture_error"] = dict(
                    raw_cleanup_error_index=len(self.pending_cleanup_errors) - 1,
                    exception_rendered=False,
                )
            # Capture itself can trigger a guard exception that clears a
            # CPython hook. Recover from its observed state, never rerun it.
            for name, expected in (("profile", previous), ("trace", trace)):
                try:
                    self._restore_hook(name, expected, "after_capture")
                except BaseException as error:
                    self.pending_cleanup_errors.append(("after_capture:" + name + ":entry", error))
            try:
                self.lifecycle["hooks_after_cleanup"] = self._hook_state(previous, trace)
            except BaseException as error:
                self.pending_cleanup_errors.append(("final_state", error))
            # No fallible helper call is needed to retain errors when a
            # helper was rejected before its body or hooks remain missing.
            self.lifecycle["raw_cleanup_error_count"] = len(self.pending_cleanup_errors)
            self.lifecycle["raw_cleanup_errors"] = []
            for index, (origin, _error) in enumerate(self.pending_cleanup_errors):
                self.lifecycle["raw_cleanup_errors"].append(
                    dict(
                        origin=origin,
                        raw_cleanup_error_index=index,
                        raw_exception_retained_in_process=True,
                    )
                )
            if self.pending_cleanup_errors:
                origin, error = self.pending_cleanup_errors[0]
                if self.failure is None:
                    self.failure = error
                if self.work.failure is None:
                    self.work.failure = dict(origin=origin, exception_rendered=False)
            self.installed = False
            self.bookkeeping_depth -= 1
            if primary is None and self.failure is not None:
                refusal = TimingObservationFailed(
                    self.failure,
                    label=self.work.phase or "imports",
                    operation="authority_timing",
                    message="Authority timing cleanup failed; raw exception retained",
                )
                refusal.raw_cleanup_errors = tuple(self.pending_cleanup_errors)
                raise refusal from self.failure

    def _hook_state(self, previous, trace):
        current, current_trace = sys.getprofile(), sys.gettrace()
        return dict(
            profile="entry"
            if current is previous
            else "observer"
            if current is self.active_profile
            else "absent"
            if current is None
            else "other",
            trace="entry"
            if current_trace is trace
            else "absent"
            if current_trace is None
            else "other",
        )

    def _restore_hook(self, name, expected, phase):
        getter, setter = (
            (sys.getprofile, sys.setprofile) if name == "profile" else (sys.gettrace, sys.settrace)
        )
        for attempt in range(2):
            try:
                if getter() is expected:
                    break
                self.lifecycle["cleanup_attempts"].append(
                    dict(phase=phase, hook=name, attempt=attempt + 1)
                )
                setter(expected)
            except BaseException as error:
                self.pending_cleanup_errors.append((phase + ":" + name, error))
        try:
            if getter() is not expected:
                self.pending_cleanup_errors.append(
                    (
                        phase + ":" + name + ":incomplete",
                        RuntimeError("Inherited " + name + " hook remains unrestored"),
                    )
                )
        except BaseException as error:
            self.pending_cleanup_errors.append((phase + ":" + name + ":state", error))


class TimingObservationFailed(RuntimeError):
    def __init__(self, primary, *, label, operation, returned=None, message=None):
        super().__init__(str(primary) if message is None else message)
        self.capture_error = primary
        self.label, self.operation = label, operation
        self.stage = label + ":" + operation + ":timing"
        self.partial = {"returned": returned} if returned is not None else {}


class StageTimings:
    """Durable wall/process-CPU checkpoints, with no source success inference.

    Each interval includes writing its start checkpoint. Forensic failure
    capture remains outside these ordinary action/capture intervals. An abrupt
    termination can leave a start without an end; no duration is then inferred.
    """

    def __init__(self, output, work):
        self.output, self.work, self.sequence = Path(output), work, 0
        self.folder = self.output / "stage-timings"
        self.folder.mkdir()
        self.failures = []
        self.authority = None

    def _checkpoint(self, label, operation, position, *, started=None, error=None, returned=None):
        try:
            if label not in STAGES or operation not in ("action", "capture"):
                raise ValueError("Undeclared timed diagnostic boundary")
            if self.authority is not None:
                self.authority.checkpoint(label + ":" + operation + ":" + position)
            wall, cpu = time.monotonic_ns(), time.process_time_ns()
            row = dict(
                kind="cells.diagnostic_stage_timing@1",
                sequence=self.sequence,
                label=label,
                operation=operation,
                position=position,
                monotonic_ns=wall,
                process_cpu_ns=cpu,
                elapsed_wall_ns=None if started is None else wall - started[0],
                elapsed_process_cpu_ns=None if started is None else cpu - started[1],
                interval_includes_start_checkpoint_write=True,
                independent_case_credit=0,
                entry_is_source_success=False,
                error=None if error is None else shared.exception_record(error),
            )
            if any(type(n) is not int or n < 0 for n in (wall, cpu)) or (
                started is not None and (wall < started[0] or cpu < started[1])
            ):
                raise ValueError("Invalid monotonic/process timing observation")
            path = self.folder / f"{self.sequence:04d}.json"
            self.sequence += 1
            shared.write(path, row)
            return wall, cpu
        except BaseException as failure:
            record = dict(
                label=label,
                operation=operation,
                position=position,
                error=shared.exception_record(failure),
            )
            self.failures.append(record)
            if self.work.failure is None:
                self.work.failure = record
            raise TimingObservationFailed(
                failure, label=label, operation=operation, returned=returned
            ) from failure

    def run(self, label, operation, action):
        # Protect the CALL event as well as the body: a chained profiler can
        # reject entry before _checkpoint's own exception handler runs.
        try:
            started = self._checkpoint(label, operation, "start")
        except TimingObservationFailed:
            raise
        except BaseException as failure:
            raise self._entry_failure(failure, label, operation, "start") from failure
        try:
            value = action()
        except BaseException as primary:
            try:
                self._checkpoint(label, operation, "raised", started=started, error=primary)
            except TimingObservationFailed:
                pass  # Keep the original source/capture exception and cause.
            except BaseException as failure:
                self._entry_failure(failure, label, operation, "raised")
            raise
        position = "capture_saved" if operation == "capture" and value is True else "returned"
        if operation == "capture" and value is False:
            position = "capture_failed"
        try:
            self._checkpoint(label, operation, position, started=started, returned=value)
        except TimingObservationFailed:
            raise
        except BaseException as failure:
            raise self._entry_failure(failure, label, operation, position, value) from failure
        return value

    def _entry_failure(self, failure, label, operation, position, returned=None):
        record = dict(
            label=label,
            operation=operation,
            position=position,
            error=shared.exception_record(failure),
        )
        self.failures.append(record)
        if self.work.failure is None:
            self.work.failure = record
        return TimingObservationFailed(failure, label=label, operation=operation, returned=returned)

    def steps(self, steps):
        return tuple(
            (label, lambda label=label, action=action: self.run(label, "action", action))
            for label, action in steps
        )


class TimedEvidence:
    """Preserve the existing typed writer and its separate failure handling."""

    def __init__(self, evidence, timings):
        self.evidence, self.timings = evidence, timings

    @property
    def rows(self):
        return self.evidence.rows

    def save(self, label, value):
        if label not in STAGES:
            return self.evidence.save(label, value)
        entered = False

        def save():
            nonlocal entered
            entered = True
            return self.evidence.save(label, value)

        try:
            return self.timings.run(label, "capture", save)
        except TimingObservationFailed:
            if not entered:
                # The source already returned. Make one forensic attempt with
                # the original label/occurrence, including its scoped cap.
                # Never retry an entered writer or resume source continuation.
                work = self.timings.work
                with work.retain_failure() if isinstance(work, shared.WorkLog) else nullcontext():
                    self.evidence.save(label, value)
            return False

    def failure(self, error):
        if (
            isinstance(error, TimingObservationFailed)
            and error.operation == "action"
            and error.label in STAGES
            and "returned" in error.partial
        ):
            # A completed action may need its declared capture budget. Keep
            # that exact occurrence before generic forensic traversal, whose
            # ordinary cap remains unchanged (and can still fail explicitly).
            work = self.timings.work
            with work.retain_failure() if isinstance(work, shared.WorkLog) else nullcontext():
                self.evidence.save(error.label, error.partial["returned"])
        return self.evidence.failure(error)


def _request_capture_schema(value):
    """Closed wire shape only; full lineage is checked by the comparison reader."""
    if type(value) is not dict or set(value) != set(CAPTURE_POLICY["request_fields"]):
        raise ValueError("Changed ordinary request capture schema")
    request = value["caller_request"]
    if (
        type(request) is not dict
        or set(request) != set(CAPTURE_POLICY["caller_request_fields"])
        or type(request["lifecycle_request"]) is not dict
        or type(request["lifecycle_state"]) is not dict
        or type(request["configuration_json"]) is not str
        or request["grid_descriptor"] != "native_grid_size_yaml_alias@1"
        or any(
            type(identity) is not str
            or len(identity) != 64
            or any(c not in "0123456789abcdef" for c in identity)
            for identity in (value["identity"], request["identity"])
        )
    ):
        raise ValueError("Changed descriptor-bearing request capture schema")


def _capture_limit(label, path):
    if label != CAPTURE_POLICY["request_label"]:
        return CAPTURE_POLICY["ordinary_metadata_bytes"]
    if Path(path).name != CAPTURE_POLICY["request_filename"]:
        raise ValueError("Nested request capture has the wrong occurrence")
    return CAPTURE_POLICY["request_metadata_bytes"]


def _write_capture(label, path, serialized):
    limit = _capture_limit(label, path)
    if label == CAPTURE_POLICY["request_label"]:
        _request_capture_schema(serialized)
    return payload.write(path, serialized, metadata_bytes=limit)


def _read_capture(path, row, *, expand, pins_only=False):
    """Authenticate role, occurrence and the same bytes decoded under its cap."""
    path = Path(path)
    if (
        type(row) is not dict
        or set(row) != {"label", "path", "status", "sha256"}
        or row["label"] not in STAGES
        or row["path"] != f"capture-{STAGES.index(row['label']):04d}.json"
        or path.name != row["path"]
        or row["status"] != "saved"
        or type(row["sha256"]) is not str
        or len(row["sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in row["sha256"])
    ):
        raise ValueError("Changed ordinary capture role or binding")
    kwargs = dict(metadata_bytes=_capture_limit(row["label"], path), expected_sha256=row["sha256"])
    value = payload.read(path, expand=expand, **kwargs)
    if row["label"] == CAPTURE_POLICY["request_label"]:
        _request_capture_schema(value)
    return payload.files(path, **kwargs) if pins_only else value


def read_capture(path, row, *, expand=True):
    return _read_capture(path, row, expand=expand)


def capture_files(path, row):
    return _read_capture(path, row, expand=False, pins_only=True)


def configuration():
    return dict(prior.configuration(), **{"general options": {"comp grid size": 25}})


def _native_inputs(repository):
    rows = prior._native_inputs(repository)
    for relative, digest in native.pins_for().items():
        name = str(shared.NATIVE / relative)
        if name in rows and rows[name] != digest:
            raise ValueError("Conflicting original source authority")
        rows[name] = digest
    return rows


def _diagnostic_limits(wall_seconds):
    if type(wall_seconds) is not int or wall_seconds not in (480, 1800):
        raise ValueError("Declare the 480-second or 1800-second diagnostic wall allowance")
    return dict(shared.LIMITS, timeout=wall_seconds)


def prepare(destination, *, repository=ROOT, cpu=6, runtime_paths=(), wall_seconds=480):
    """One-way current-checkout snapshot; original files are pinned, not copied."""
    repository = Path(repository).absolute()
    destination = shared.execution_output(destination, repository, {"runtime_paths": runtime_paths})
    if type(cpu) is not int or cpu not in os.sched_getaffinity(0):
        raise ValueError("Select an available single CPU")
    limits = _diagnostic_limits(wall_seconds)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        closure = runpy.run_path(str(repository / shared.CLOSURE))["closure"]
        files = closure(repository, [*FILES, *TESTS, PAYLOAD_TEST, WORKLOG_TEST])
        files[shared.CLOSURE] = source_snapshot.digest(repository / shared.CLOSURE)
        for parent in {Path(name).parent for name in files}:
            for path in (repository / parent).glob("*.json"):
                files[str(path.relative_to(repository))] = source_snapshot.digest(path)
        external, overlays = _native_inputs(repository), []
        for raw in runtime_paths:
            path = Path(raw).absolute()
            if not path.is_dir() or path.is_relative_to(repository) or path.is_symlink():
                raise ValueError("Require an explicit external runtime overlay")
            overlays.append(str(path))
            for file in path.rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts:
                    row = shared.pin(file)
                    if row["path"] in external and external[row["path"]] != row["sha256"]:
                        raise ValueError("Conflicting runtime/source pin")
                    external[row["path"]] = row["sha256"]
        pins = [dict(path=p, sha256=h) for p, h in sorted(external.items())]
        shared.verify_pins(pins)
        snapshot = source_snapshot.freeze(repository, destination / "source", {p: p for p in files})
        plan = dict(
            kind=KINDS[0],
            purpose=PURPOSE,
            cases=list(CASES),
            configuration=configuration(),
            fixture_controls=CONTROLS,
            snapshot_sha256=source_snapshot.digest(destination / "source/SNAPSHOT.json"),
            git_revision=snapshot["git_revision"],
            runner_sha256=files[OWN],
            external_inputs=pins,
            runtime_paths=overlays,
            interpreter=str(Path(sys.executable).absolute()),
            cpu=cpu,
            limits=limits,
            stop_after=ENDPOINT,
            execution_stages=list(STAGES),
            ordinary_methods=list(native.METHODS),
            capture_transport=payload.KIND,
            capture_policy=CAPTURE_POLICY,
            authority_timing_policy=AUTHORITY_TIMING_POLICY,
            source_review_required_before_release=True,
            automatic_retry=False,
            **shared.NO_CREDIT,
        )
        source_snapshot.assert_checkout_unchanged(destination / "source")
        shared.verify_pins(pins)
        shared.write(destination / "plan.json", plan)
        (destination / "plan.json").chmod(0o444)
        return plan
    except BaseException:
        shared.write(
            destination / "preparation-failure.json",
            dict(traceback=traceback.format_exc(), **shared.NO_CREDIT),
        )
        raise


def verify_plan(prepared, expected_sha256):
    prepared = shared.output_path(prepared)
    if source_snapshot.digest(prepared / "plan.json") != expected_sha256:
        raise ValueError("Changed ordinary diagnostic plan")
    plan = shared.read(prepared / "plan.json")
    if type(plan.get("limits")) is not dict:
        raise ValueError("Missing diagnostic resource limits")
    fixed = dict(
        kind=KINDS[0],
        purpose=PURPOSE,
        cases=list(CASES),
        configuration=configuration(),
        fixture_controls=CONTROLS,
        limits=_diagnostic_limits(plan["limits"].get("timeout")),
        stop_after=ENDPOINT,
        execution_stages=list(STAGES),
        ordinary_methods=list(native.METHODS),
        capture_transport=payload.KIND,
        capture_policy=CAPTURE_POLICY,
        authority_timing_policy=AUTHORITY_TIMING_POLICY,
        source_review_required_before_release=True,
        automatic_retry=False,
        **shared.NO_CREDIT,
    )
    if (
        (prepared / "preparation-failure.json").exists()
        or not prior._same({key: plan.get(key) for key in fixed}, fixed)
        or type(plan.get("cpu")) is not int
    ):
        raise ValueError("Incomplete or widened ordinary diagnostic plan")
    source_snapshot.verify(prepared / "source", manifest_sha256=plan["snapshot_sha256"])
    if source_snapshot.digest(prepared / "source" / OWN) != plan["runner_sha256"]:
        raise ValueError("Changed frozen worker")
    shared.verify_pins(plan["external_inputs"])
    if any(
        dict(path=p, sha256=h) not in plan["external_inputs"]
        for p, h in _native_inputs(prepared / "source").items()
    ):
        raise ValueError("Missing original source authority")
    return plan


def verify_release(prepared, digest, release, case):
    plan = verify_plan(prepared, digest)
    grant = shared.read(release)
    fixed = dict(
        kind=KINDS[1],
        plan_sha256=digest,
        snapshot_sha256=plan["snapshot_sha256"],
        case=case,
        stop_after=ENDPOINT,
        allow_actual_source_diagnostic=True,
        scientific_qualification=False,
    )
    review = grant.get("source_review")
    if (
        case not in CASES
        or not prior._same({key: grant.get(key) for key in fixed}, fixed)
        or type(review) is not dict
        or set(review) != {"path", "sha256"}
    ):
        raise ValueError("Exact ordinary endpoint and reviewed release required")
    shared.verify_pins([review])
    if os.sched_getaffinity(0) != {plan["cpu"]}:
        raise ValueError("Require the declared one CPU")
    return plan


def _pipeline(case, output, *, fixtures, initial, clipped, lifecycle, multi, environment):
    # Reuse only the first six prerequisite actions, with their original error
    # handling. The fresh ordinary request is constructed before caller birth.
    old = prior._pipeline(
        case,
        output,
        fixtures=fixtures,
        initial=initial,
        clipped=clipped,
        lifecycle=lifecycle,
        multi=multi,
    )
    retained, actions = {}, []
    for name, action in old[:6]:

        def step(name=name, action=action):
            value = action()
            retained[name] = value
            if name == STAGES[0]:
                value = dict(value, configuration=configuration())
            return value

        actions.append((name, step))

    def request():
        value = environment.from_lifecycle(
            retained["lifecycle_request"],
            retained["post_clip_lifecycle"],
            configuration(),
            law_id=environment.LAW_ID,
        )
        retained["request"] = value
        return value

    def caller():
        owner = multi.prepare(retained["request"].caller_request)
        retained["caller_owner"] = owner
        if owner.trial.source_completed is not True:
            raise prior.PrerequisiteRejected(retained["request"], owner.trial, "cell_index")
        return owner.trial

    def ordinary():
        req = environment.from_caller(retained["caller_owner"], law_id=environment.LAW_ID)
        retained["continuation_request"] = req
        owner = environment.prepare_continuation(req)
        retained["environment_owner"] = owner
        if owner.trial.source_completed is not True:
            raise prior.PrerequisiteRejected(req, owner.trial, ENDPOINT)
        return owner.trial

    return (*actions, (STAGES[6], request), (STAGES[7], caller), (STAGES[8], ordinary))


def _steps(case, output):
    from cells.processes import betse_initial_mesh_preparation as initial
    from cells.processes import betse_mesh_clip_preparation as clipped
    from cells.processes import betse_mesh_lifecycle_preparation as lifecycle
    from cells.processes import betse_native_multi_cell_caller as multi
    from cells.processes import betse_native_multi_cell_environment as environment
    from validation.betse import betse_mesh_lifecycle_preparation_fixtures as fixtures

    return _pipeline(
        case,
        output,
        fixtures=fixtures,
        initial=initial,
        clipped=clipped,
        lifecycle=lifecycle,
        multi=multi,
        environment=environment,
    )


def worker(prepared, digest, release, case, output):
    plan = verify_release(prepared, digest, release, case)
    source = Path(prepared) / "source"
    if ROOT != source or str(Path(sys.executable).absolute()) != plan["interpreter"]:
        raise ValueError("Use the frozen source and declared interpreter")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    output = shared.execution_output(output, prepared, plan)
    evidence, work = (
        shared.Evidence(output, sidecars=True, capture_writer=_write_capture),
        shared.WorkLog(output, source, phases=STAGES),
    )
    timings = StageTimings(output, work)
    evidence = TimedEvidence(evidence, timings)
    result = None
    authority = None
    stage = "source_execution"
    try:
        with work.active():
            steps = _steps(case, output)
            authority = AuthorityTimings(output, work, _authority_targets())
            timings.authority = authority
            with authority.active():
                result = shared.run_stages(timings.steps(steps), evidence, work)
                stage = "postprocessing.source_observer_finalization"
        stage = "postprocessing.saved_geometry_diagnostics"
        if result["status"] == "source_completed_unqualified":
            from validation.betse.native_multi_cell_environment_compare import (
                diagnostics_from_cache,
            )

            final = payload.read(output / evidence.rows[-1]["path"])
            # Observation of saved typed bits has no live-owner/source entry.
            domain = diagnostics_from_cache(final["cache"])
            shared.write(output / "domain-diagnostics.json", domain)
            result["domain_diagnostics"] = shared.pin(output / "domain-diagnostics.json")
        stage = "postprocessing.runtime_inventory"
        shared.write(output / "runtime-producers.json", shared.runtime_inventory(source))
        stage = "postprocessing.end_pin_verification"
        verify_plan(prepared, digest)
    except Exception as error:
        prior = copy.deepcopy(result)
        recording_error = None
        try:
            evidence.failure(error)
        except Exception as secondary:
            recording_error = shared.exception_record(secondary)
        if stage == "source_execution":
            result = dict(
                status="diagnostic_failed",
                failed_stage=work.phase,
                source_error=None if work.failure else shared.exception_record(error),
                observer_error=work.failure,
                interrupted_exception_graph=shared.exception_record(error)
                if work.failure
                else None,
                prior_result=prior,
                captures=evidence.rows,
                observed_source_entry_attempts=work.count,
                accepted_cases=0,
                **shared.NO_CREDIT,
            )
        else:
            # A metadata failure cannot rewrite a completed source call or
            # erase a primary source/observer failure already in its result.
            result = dict(
                prior or {},
                status="diagnostic_failed",
                accepted_cases=0,
                failed_stage=(prior or {}).get("failed_stage") or stage,
                source_error=(prior or {}).get("source_error"),
                observer_error=(prior or {}).get("observer_error") or work.failure,
                interrupted_exception_graph=(prior or {}).get("interrupted_exception_graph"),
                completed_stages=list((prior or {}).get("completed_stages", [])),
                prior_result=prior,
                captures=evidence.rows,
                observed_source_entry_attempts=work.count,
                postprocessing_stage=stage,
                postprocessing_error=shared.exception_record(error),
                **shared.NO_CREDIT,
            )
        if recording_error is not None:
            result["failure_capture_error"] = recording_error
    shared.write(
        output / "diagnostic.json",
        dict(
            case=case,
            plan_sha256=digest,
            stop_after=ENDPOINT,
            timing_observation_failures=timings.failures,
            authority_timing=dict(
                folder="authority-timings",
                snapshots_attempted=0 if authority is None else authority.sequence,
                observation_failure=None
                if authority is None
                else getattr(authority, "failure_record", None),
                hook_lifecycle=None if authority is None else authority.lifecycle,
                initialized=authority is not None,
                inclusive_times_are_additive=False,
                source_success_credit=False,
            ),
            **result,
        ),
    )
    return int(result["status"] != "source_completed_unqualified")


def launch(prepared, digest, release, case, output):
    plan = verify_release(prepared, digest, release, case)
    output = shared.execution_output(output, prepared, plan)
    output.mkdir(parents=True, exist_ok=False)
    process = failure = None
    try:
        (output / "process").mkdir()
        shared.write(
            output / "inputs.json",
            dict(
                case=case,
                stop_after=ENDPOINT,
                plan_sha256=digest,
                release=shared.pin(release),
                **shared.NO_CREDIT,
            ),
        )
        if shared.guard.memory_available() < 12 * 2**30:
            raise RuntimeError("Require 12 GiB available launch memory")
        command = [
            plan["interpreter"],
            "-B",
            "-m",
            "validation.betse.native_multi_cell_environment_qualification",
            "worker",
            "--prepared",
            str(prepared),
            "--plan-sha256",
            digest,
            "--release",
            str(release),
            "--case",
            case,
            "--output",
            str(output),
        ]
        process = shared.guard.run_bounded(
            command,
            directory=output / "process",
            cwd=Path(prepared) / "source",
            env=shared.environment(Path(prepared) / "source", plan),
            **plan["limits"],
        )
        recorded = shared.read(output / "diagnostic.json")
        if (
            process["returncode"] != 0
            or recorded.get("status") != "source_completed_unqualified"
            or recorded.get("completed_stages") != list(STAGES)
            or recorded.get("stop_after") != ENDPOINT
        ):
            raise RuntimeError("Ordinary diagnostic did not complete its exact boundary")
    except Exception as error:
        failure = shared.exception_record(error)
    result = dict(
        status="failed" if failure else "completed_unqualified",
        case=case,
        stop_after=ENDPOINT,
        process=process,
        failure=failure,
        diagnostic=shared.pin(output / "diagnostic.json")
        if (output / "diagnostic.json").is_file()
        else None,
        process_receipts=[
            shared.pin(output / "process" / p)
            for p in ("result.json", "failure.json", "resource-stop.json")
            if (output / "process" / p).is_file()
        ],
        automatic_retry=False,
        accepted_cases=0,
        **shared.NO_CREDIT,
    )
    shared.write(output / ("failure.json" if failure else "result.json"), result)
    return result


def supervised_launch(prepared, digest, release, case, output):
    """Retain startup failures after authenticating the failure-output domain.

    Invalid plans/output domains refuse before writing here; the detached
    launcher's existing stdout/stderr logs retain those preflight failures.
    """
    plan = verify_plan(prepared, digest)
    output = shared.execution_output(output, prepared, plan)
    if output.exists():
        raise ValueError("Use a fresh supervised diagnostic output")
    try:
        return launch(prepared, digest, release, case, output)
    except BaseException as error:
        try:
            output.mkdir(parents=True, exist_ok=True)
            failure = dict(
                status="failed",
                stage="controller",
                failure=shared.exception_record(error),
                traceback=traceback.format_exc(),
                plan_sha256=digest,
                automatic_retry=False,
                **shared.NO_CREDIT,
            )
            shared.write(output / "controller-failure.json", failure)
        except BaseException as capture_error:
            # A full disk or failed metadata encoder cannot replace the
            # controller's primary exception and its existing cause chain.
            try:
                error.controller_capture_error = capture_error
                error.add_note("Controller failure evidence could not be saved.")
            except BaseException:
                pass
        raise


def _software_selection(group, items):
    """Select by function name, excluding output-directory pytest keywords."""
    if group not in ("worklog", "authority-timing"):
        return list(items), []
    terms = (
        ("authority_timing", "stage_timing", "repair_c5")
        if group == "authority-timing"
        else (
            "worklog",
            "recorder",
            "profiler",
            "recursive_helper_work",
            "literal_kernel_entries",
            "stage_timing",
        )
    )
    selected, deselected = [], []
    for item in items:
        name = getattr(item, "originalname", None) or item.name.split("[", 1)[0]
        destination = selected if any(term in name for term in terms) else deselected
        destination.append(item)
    return selected, deselected


def software_child(output, group="all"):
    """All controls run behind import and native-file entry blockades."""
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    import pytest

    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {
                "cells",
                "betse",
                "numpy",
                "scipy",
                "PIL",
                "jax",
                "jaxlib",
            }:
                attempts.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    blocker = Block()
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code.co_filename.startswith(str(shared.NATIVE) + "/"):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual original source entry forbidden")

    (output / "case-reports").mkdir()

    class Reports:
        def pytest_collection_modifyitems(self, config, items):
            selected, deselected = _software_selection(group, items)
            if deselected:
                config.hook.pytest_deselected(items=deselected)
                items[:] = selected

        def pytest_runtest_logreport(self, report):
            if report.when == "call" or report.failed:
                key = hashlib.sha256((report.nodeid + report.when).encode()).hexdigest()
                shared.write(
                    output / "case-reports" / (key + ".json"),
                    dict(
                        nodeid=report.nodeid,
                        when=report.when,
                        outcome=report.outcome,
                        traceback=str(report.longrepr) if report.failed else None,
                        native_entry_attempts=list(attempts),
                    ),
                )

    try:
        sys.meta_path.insert(0, blocker)
        sys.setprofile(profile)
        arguments = [
            "-q",
            "--noconftest",
            "-c",
            "/dev/null",
            "-p",
            "no:cacheprovider",
            *(str(ROOT / p) for p in (TESTS[:1] if group == "authority-timing" else TESTS)),
            "--junitxml=" + str(output / "tests.xml"),
            "--basetemp=" + str(output / "tmp"),
        ]
        if SOFTWARE_GROUPS[group]:
            arguments += ["-k", SOFTWARE_GROUPS[group]]
        if group == "capture-metadata":
            arguments.append(str(ROOT / PAYLOAD_TEST))
        if group == "worklog":
            arguments.append(str(ROOT / WORKLOG_TEST))
        code = pytest.main(arguments, plugins=[Reports()])
    finally:
        sys.setprofile(previous)
        sys.meta_path.remove(blocker)
        shared.write(
            output / "native-entry-guard.json", dict(attempted=attempts, scientific_credit=False)
        )
        shared.write(output / "runtime-producers.json", shared.runtime_inventory(ROOT))
    shared.write(output / "pytest-exit.json", dict(returncode=int(code)))
    return int(code) if not attempts else 1


def software(output, group="all", *, cpu=6):
    if group not in SOFTWARE_GROUPS:
        raise ValueError("Unknown focused software group")
    output = shared.execution_output(output, ROOT, {"runtime_paths": []})
    output.mkdir(parents=True, exist_ok=False)
    plan = prepare(output / "prepared", cpu=cpu)
    source = output / "prepared/source"
    (output / "process").mkdir()
    env = shared.environment(source, plan)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    process = shared.guard.run_bounded(
        [
            plan["interpreter"],
            "-B",
            "-m",
            "validation.betse.native_multi_cell_environment_qualification",
            "software-child",
            "--output",
            str(output),
            "--group",
            group,
        ],
        directory=output / "process",
        cwd=source,
        env=env,
        **plan["limits"],
    )
    # The frozen bytes/loaded producers decide the execution, not a later HEAD.
    source_snapshot.verify(source, manifest_sha256=plan["snapshot_sha256"])
    producers = shared.read(output / "runtime-producers.json")
    for name, row in producers.items():
        if source_snapshot.digest(row["path"]) != row["sha256"]:
            raise ValueError("Changed loaded producer: " + name)
        if name.startswith("validation.") and not Path(row["path"]).is_relative_to(source):
            raise ValueError("Validation producer escaped immutable source")
    drift = None
    try:
        source_snapshot.assert_checkout_unchanged(source)
    except Exception as error:
        drift = shared.exception_record(error)
    result = dict(
        status="passed" if process["returncode"] == 0 else "failed",
        group=group,
        process=process,
        snapshot=shared.pin(source / "SNAPSHOT.json"),
        source_pins={p: shared.pin(source / p) for p in (*FILES, *TESTS)},
        checkout_drift=drift,
        integration_pending=drift is not None,
        native_entry_guard=shared.pin(output / "native-entry-guard.json"),
        **shared.NO_CREDIT,
    )
    shared.write(output / "software-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("prepare")
    item.add_argument("--output", type=Path, required=True)
    item.add_argument("--cpu", type=int, default=6)
    item.add_argument("--runtime-path", type=Path, action="append", default=[])
    item.add_argument("--wall-seconds", type=int, choices=(480, 1800), default=480)
    for name in ("software", "software-child"):
        item = sub.add_parser(name)
        item.add_argument("--output", type=Path, required=True)
        item.add_argument("--group", choices=SOFTWARE_GROUPS, default="all")
    for name in ("launch", "worker", "supervise"):
        item = sub.add_parser(name)
        item.add_argument("--prepared", type=Path, required=True)
        item.add_argument("--plan-sha256", required=True)
        item.add_argument("--release", type=Path, required=True)
        item.add_argument("--case", choices=CASES, required=True)
        item.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        prepare(
            args.output,
            cpu=args.cpu,
            runtime_paths=args.runtime_path,
            wall_seconds=args.wall_seconds,
        )
    elif args.command == "software":
        return int(software(args.output, args.group)["status"] != "passed")
    elif args.command == "software-child":
        return software_child(args.output, args.group)
    elif args.command == "worker":
        return worker(args.prepared, args.plan_sha256, args.release, args.case, args.output)
    else:
        launcher = supervised_launch if args.command == "supervise" else launch
        return int(
            launcher(args.prepared, args.plan_sha256, args.release, args.case, args.output)[
                "status"
            ]
            != "completed_unqualified"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
