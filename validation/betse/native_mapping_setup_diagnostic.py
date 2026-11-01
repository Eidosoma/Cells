"""Optional bounded metadata observer for an already guarded software worker.

No source callable is replaced. Python call durations include nested work and
observer overhead; they are not additive or an unprofiled speed measurement.
CPython may omit calls inside trace/profile callbacks, so periodic independent
faulthandler stacks supplement the counters. Missing observations are not zero
cost or proof that a source stage did not run.
"""

import faulthandler
import json
import os
import sys
import time
from pathlib import Path

API = frozenset({"prepare", "prepare_continuation", "bind", "advance"})
HOT = frozenset(
    {
        "_check",
        "_validate",
        "_bindings",
        "_capture",
        "_graph",
        "capture",
        "snapshot",
        "_runtime",
        "_runtime_types",
        "_same",
        "_same_graph",
        "_trace_spec",
        "_check_trace_metadata",
        "trace",
        "profile",
        "_verify_sources",
        "_verify_pin_bytes",
    }
)
FIXTURES = frozenset({"parent", "fixture", "issued_multi_chain", "_fixture_templates"})
MAX_CODES, MAX_ROWS, MAX_PENDING = 8192, 512, 512
ROOT = Path(__file__).resolve().parents[2]


class DiagnosticFailure(RuntimeError):
    pass


class Observer:
    def __init__(self, output, *, root=ROOT, stack_interval=15, flush_seconds=5):
        self.output, self.root = Path(output), str(root) + "/"
        self.stack_interval, self.flush_seconds = stack_interval, flush_seconds
        self.codes, self.rows, self.pending = {}, {}, {}
        self.errors, self.events, self.total, self.selected = [], 0, 0, 0
        self.last_notification = None
        self.duplicate_notifications = self.unmatched_returns = 0
        self.previous_profile = self.previous_trace = None
        self.started_wall = self.started_cpu = self.last_flush = None
        self.journal = self.stack_stream = None
        self.active = False
        self.timer_attempted = False
        self.first_error = None

    def _remember(self, error, stage):
        if self.first_error is None:
            self.first_error = error
        if len(self.errors) < 16:
            try:
                message = str(error)[:2048]
            except BaseException:
                message = "Exception message unavailable"
            self.errors.append(dict(stage=stage, type=type(error).__name__, message=message))

    def _site(self, code):
        if code in self.codes:
            return self.codes[code]
        filename, name = code.co_filename, code.co_name
        relative = filename[len(self.root) :] if filename.startswith(self.root) else None
        stage = False
        if relative and relative.startswith("src/cells/processes/"):
            stage = name in API or name.startswith("from_")
            selected = stage or name in HOT
        elif relative and relative.startswith("tests/"):
            stage = name in FIXTURES
            selected = stage
        else:
            selected = False
        if not selected:
            return None
        if len(self.codes) >= MAX_CODES:
            raise DiagnosticFailure("Metadata code-cache capacity exhausted")
        value = (relative, code.co_qualname, code.co_firstlineno, stage)
        self.codes[code] = value
        return value

    def _stamp(self, site, event, wall, cpu):
        row = dict(
            sequence=self.events,
            file=site[0],
            function=site[1],
            line=site[2],
            event=event,
            monotonic_seconds=wall,
            process_cpu_seconds=cpu,
            source_success_or_case_credit=False,
        )
        self.journal.write(json.dumps(row, sort_keys=True) + "\n")
        self.journal.flush()
        os.fsync(self.journal.fileno())
        self.events += 1

    def _observe(self, frame, event, arg):
        self.total += 1
        if event not in ("call", "return"):
            return
        site = self._site(frame.f_code)
        if site is None:
            return
        notification = (id(frame), frame.f_code, event)
        if notification == self.last_notification:
            self.duplicate_notifications += 1
            return
        self.last_notification = notification
        if event == "call" and id(frame) in self.pending:
            self.duplicate_notifications += 1
            return
        if event == "return" and id(frame) not in self.pending:
            self.unmatched_returns += 1
            return
        self.selected += 1
        wall, cpu = time.monotonic(), time.process_time()
        key = site[:3]
        if key not in self.rows:
            if len(self.rows) >= MAX_ROWS:
                raise DiagnosticFailure("Metadata row capacity exhausted")
            self.rows[key] = dict(
                file=site[0],
                function=site[1],
                line=site[2],
                calls=0,
                returns_or_unwinds=0,
                inclusive_wall_seconds=0.0,
                inclusive_cpu_seconds=0.0,
            )
        row = self.rows[key]
        if event == "call":
            if len(self.pending) >= MAX_PENDING:
                raise DiagnosticFailure("Metadata active-frame capacity exhausted")
            row["calls"] += 1
            self.pending[id(frame)] = (site, wall, cpu)
        else:
            row["returns_or_unwinds"] += 1
            started = self.pending.pop(id(frame), None)
            if started is not None:
                row["inclusive_wall_seconds"] += wall - started[1]
                row["inclusive_cpu_seconds"] += cpu - started[2]
        if site[3]:
            self._stamp(site, "call" if event == "call" else "return_or_unwind", wall, cpu)
        # Sparse flushes; never write one metadata row for every hot call.
        if self.selected % 512 == 0 and wall - self.last_flush >= self.flush_seconds:
            self.flush("in_progress")

    def profile(self, frame, event, arg):
        # An inherited entry refusal must still run before the target body.
        if self.previous_profile is not None:
            self.previous_profile(frame, event, arg)
        if not self.active or self.errors:
            return
        try:
            self._observe(frame, event, arg)
        except Exception as error:
            # Observation failures cannot replace an original source unwind.
            # They prohibit a successful diagnostic at the enclosing boundary.
            self._remember(error, "profile_metadata")

    def flush(self, status):
        wall, cpu = time.monotonic(), time.process_time()
        value = dict(
            status=status,
            started_monotonic=self.started_wall,
            elapsed_wall_seconds=wall - self.started_wall,
            elapsed_cpu_seconds=cpu - self.started_cpu,
            observed_profile_events=self.total,
            selected_python_events=self.selected,
            duplicate_selected_notifications=self.duplicate_notifications,
            unmatched_selected_returns=self.unmatched_returns,
            stage_events=self.events,
            code_cache_entries=len(self.codes),
            rows=list(self.rows.values()),
            open_calls=[
                dict(
                    file=s[0],
                    function=s[1],
                    line=s[2],
                    elapsed_wall_seconds=wall - w,
                    elapsed_cpu_seconds=cpu - c,
                )
                for s, w, c in self.pending.values()
            ],
            observation_errors=list(self.errors),
            stack_interval_seconds=self.stack_interval,
            inclusive_times_are_nonadditive=True,
            observer_overhead_included=True,
            profile_can_omit_trace_callback_work=True,
            source_success_native_entry_or_scientific_certificate=False,
        )
        temporary = self.output / "timing.tmp"
        with temporary.open("w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.output / "timing.json")
        self.last_flush = wall

    def __enter__(self):
        self.output.mkdir(parents=True, exist_ok=False)
        self.previous_profile, self.previous_trace = sys.getprofile(), sys.gettrace()
        self.started_wall, self.started_cpu = time.monotonic(), time.process_time()
        self.last_flush = self.started_wall
        try:
            self.journal = (self.output / "stages.jsonl").open("x")
            self.stack_stream = (self.output / "stacks.log").open("xb", buffering=0)
            self.flush("started")
            if self.stack_interval is not None:
                self.timer_attempted = True
                faulthandler.dump_traceback_later(
                    self.stack_interval, repeat=True, file=self.stack_stream, exit=False
                )
            self.active = True
            sys.setprofile(self.profile)
            return self
        except BaseException as primary:
            self._cleanup(primary, "setup_failed")
            raise

    def _cleanup(self, primary, status):
        self.active = False
        actions = [
            ("profile_restore", lambda: sys.setprofile(self.previous_profile)),
            ("trace_restore", lambda: sys.settrace(self.previous_trace)),
        ]
        if self.timer_attempted:
            actions.append(("stack_timer_close", faulthandler.cancel_dump_traceback_later))
        for name, stream in (("journal_close", self.journal), ("stack_close", self.stack_stream)):
            if stream is not None:
                actions.append((name, stream.close))
        for stage, action in actions:
            try:
                action()
            except BaseException as error:
                self._remember(error, stage)
        # This independent file remains writable after both observation streams
        # close, so late cleanup failures belong in the final metadata too.
        try:
            self.flush(status)
        except BaseException as error:
            self._remember(error, "final_metadata")
        if self.errors:
            if primary is not None:
                try:
                    primary.mapping_setup_diagnostic_errors = tuple(self.errors)
                except BaseException as error:
                    self._remember(error, "primary_evidence_attachment")
            # The enclosing resource runner already retains stderr. This is an
            # independent fallback when the diagnostic directory cannot be saved.
            try:
                record = dict(
                    kind="mapping_setup_observation_failure",
                    status=status,
                    primary_type=None if primary is None else type(primary).__name__,
                    secondary_errors=self.errors,
                )
                os.write(2, (json.dumps(record, sort_keys=True) + "\n").encode())
            except BaseException as error:
                self._remember(error, "stderr_fallback")

    def __exit__(self, kind, primary, traceback):
        self._cleanup(primary, "closed_with_source_error" if primary is not None else "closed")
        if primary is None and self.errors:
            error = DiagnosticFailure("Incomplete metadata observation: " + repr(self.errors))
            error.mapping_setup_diagnostic_errors = tuple(self.errors)
            raise error from self.first_error
        return False
