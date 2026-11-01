"""Metadata-only observer controls; no simulator/native/numerical execution."""

import ast
import hashlib
import importlib.abc
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from validation.betse import native_mapping_setup_diagnostic as d


def synthetic(text, **namespace):
    filename = str(d.ROOT / "src/cells/processes/betse_native_synthetic_observer_fixture.py")
    exec(compile(text, filename, "exec"), namespace)
    return namespace


class ObserverTests(unittest.TestCase):
    def setUp(self):
        if folder := os.environ.get("CELLS_MAPPING_DIAGNOSTIC_EVIDENCE"):
            token = hashlib.sha256(self.id().encode()).hexdigest()[:20]
            self.output = Path(folder) / "per-case" / token / "diagnostic"
            self.output.parent.mkdir(parents=True, exist_ok=False)
        else:
            self.temporary = tempfile.TemporaryDirectory()
            self.addCleanup(self.temporary.cleanup)
            self.output = Path(self.temporary.name) / "diagnostic"
        self.profile, self.trace = sys.getprofile(), sys.gettrace()

    def tearDown(self):
        self.assertIs(sys.getprofile(), self.profile)
        self.assertIs(sys.gettrace(), self.trace)

    def observer(self, **kwargs):
        return d.Observer(self.output, stack_interval=None, **kwargs)

    def test_nested_calls_keep_durable_stages_and_nonadditive_timings(self):
        ns = synthetic("def _check(): return 3\ndef prepare(): return _check()\n")
        with self.observer() as obs:
            self.assertEqual(ns["prepare"](), 3)
            obs.flush("in_progress")
            saved = json.loads((self.output / "timing.json").read_text())
            self.assertEqual(saved["status"], "in_progress")
        saved = json.loads((self.output / "timing.json").read_text())
        rows = {r["function"]: r for r in saved["rows"]}
        self.assertEqual(set(rows), {"prepare", "_check"})
        self.assertTrue(all(r["calls"] == r["returns_or_unwinds"] == 1 for r in rows.values()))
        self.assertGreaterEqual(
            rows["prepare"]["inclusive_cpu_seconds"], rows["_check"]["inclusive_cpu_seconds"]
        )
        stages = [json.loads(s) for s in (self.output / "stages.jsonl").read_text().splitlines()]
        self.assertEqual([s["event"] for s in stages], ["call", "return_or_unwind"])
        self.assertTrue(saved["inclusive_times_are_nonadditive"])
        self.assertTrue(saved["profile_can_omit_trace_callback_work"])
        self.assertFalse(saved["source_success_native_entry_or_scientific_certificate"])

    def test_source_error_and_cause_survive_observation(self):
        primary, cause = ValueError("source"), LookupError("cause")
        fn = synthetic("def prepare(): raise primary from cause", primary=primary, cause=cause)[
            "prepare"
        ]
        with self.assertRaises(ValueError) as caught:
            with self.observer():
                fn()
        self.assertIs(caught.exception, primary)
        self.assertIs(primary.__cause__, cause)
        value = json.loads((self.output / "timing.json").read_text())
        self.assertEqual(value["status"], "closed_with_source_error")
        self.assertEqual(value["rows"][0]["returns_or_unwinds"], 1)

    def test_inherited_entry_guard_still_blocks_target_body(self):
        called = []
        fn = synthetic("def prepare(): called.append(1)", called=called)["prepare"]
        guard = ValueError("inherited guard")

        def previous(frame, event, arg):
            if self.profile is not None:
                self.profile(frame, event, arg)
            if frame.f_code is fn.__code__ and event == "call":
                raise guard

        sys.setprofile(previous)
        try:
            with self.assertRaises(ValueError) as caught:
                with self.observer():
                    fn()
            self.assertIs(caught.exception, guard)
            self.assertIs(sys.getprofile(), previous)
            self.assertEqual(called, [])
        finally:
            sys.setprofile(self.profile)

    def test_inherited_trace_and_successful_profiler_are_preserved(self):
        events = []
        fn = synthetic("def prepare(): return 4")["prepare"]

        def previous(frame, event, arg):
            if self.profile is not None:
                self.profile(frame, event, arg)
            if frame.f_code is fn.__code__:
                events.append(event)

        sys.setprofile(previous)
        try:
            with self.observer():
                self.assertIs(sys.gettrace(), self.trace)
                self.assertEqual(fn(), 4)
            self.assertIs(sys.getprofile(), previous)
        finally:
            sys.setprofile(self.profile)
        self.assertEqual(events, ["call", "return"])

    def test_three_nested_runner_facades_preserve_guards_without_triple_counting(self):
        fn = synthetic("def prepare(): return 9")["prepare"]
        guarded = []
        obs = self.observer()

        def facade(delegate, previous, label):
            def profile(frame, event, arg):
                if frame.f_code is fn.__code__:
                    guarded.append((label, event))
                delegate(frame, event, arg)
                previous(frame, event, arg)

            return profile

        with obs:
            # Each existing runner facade retains the same previous profiler
            # before the nested delegate is installed. Keep all three guards.
            def callback(frame, event, arg):
                pass

            for label in ("mapping", "post-world", "tail"):
                callback = facade(callback, obs.profile, label)
            sys.setprofile(callback)
            try:
                self.assertEqual(fn(), 9)
            finally:
                sys.setprofile(obs.profile)
        value = json.loads((self.output / "timing.json").read_text())
        self.assertEqual(len(value["rows"]), 1)
        self.assertEqual(value["rows"][0]["calls"], 1)
        self.assertEqual(value["rows"][0]["returns_or_unwinds"], 1)
        self.assertEqual(value["stage_events"], 2)
        self.assertEqual(value["duplicate_selected_notifications"], 4)
        self.assertEqual(value["unmatched_selected_returns"], 0)
        self.assertEqual(len(guarded), 6)
        self.assertEqual({label for label, event in guarded}, {"mapping", "post-world", "tail"})

    def _runner_facades(self, previous, codes):
        """Compile the real metadata-only closures, without importing Cells."""
        outer = sys
        facades, attempts = [], []
        for name in (
            "tissue_to_grid",
            "post_world_operators",
            "world_finalization",
        ):
            path = d.ROOT / ("validation/betse/betse_native_multi_cell_" + name + "_software.py")
            tree = ast.parse(path.read_text())
            child = next(
                n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "child"
            )
            closure = next(
                n for n in child.body if isinstance(n, ast.FunctionDef) and n.name == "setprofile"
            )
            attempted = []
            unused = SimpleNamespace(__name__="unused", METHODS=())
            namespace = dict(
                sys=outer,
                previous=previous,
                codes=codes,
                attempted=attempted,
                mapping=unused,
                stage=unused,
                finalization=unused,
                delegates=(),
                actual_helpers=(),
                source_path="<unused>",
            )
            exec(compile(ast.Module(body=[closure], type_ignores=[]), str(path), "exec"), namespace)
            outer = SimpleNamespace(setprofile=namespace["setprofile"])
            facades.append(outer)
            attempts.append(attempted)
        return facades, attempts

    def test_literal_nested_facades_restore_exact_previous_observer(self):
        fn = synthetic("def prepare(): return 7")["prepare"]
        seen = []
        with self.observer():
            previous = sys.getprofile()
            facades, attempts = self._runner_facades(previous, {})

            def delegate(frame, event, arg):
                if frame.f_code is fn.__code__:
                    seen.append(event)

            facades[-1].setprofile(delegate)
            try:
                self.assertEqual(fn(), 7)
            finally:
                facades[-1].setprofile(None)
            self.assertIs(sys.getprofile(), previous)
            # The enclosing runners explicitly restore their captured callback.
            # It must not be wrapped a second time during those finally blocks.
            for facade in reversed(facades):
                facade.setprofile(previous)
                self.assertIs(sys.getprofile(), previous)
            self.assertEqual(attempts, [[], [], []])
        self.assertEqual(seen, ["call", "return"])

    def test_literal_nested_facades_keep_source_rejection_and_restore(self):
        called = []
        fn = synthetic("def prepare(): called.append(1)", called=called)["prepare"]
        with self.observer():
            previous = sys.getprofile()
            facades, attempts = self._runner_facades(previous, {fn.__code__: "blocked"})
            facades[-1].setprofile(lambda frame, event, arg: None)
            try:
                with self.assertRaises(AssertionError):
                    fn()
            finally:
                facades[-1].setprofile(None)
            self.assertIs(sys.getprofile(), previous)
            self.assertEqual(called, [])
            self.assertEqual(attempts, [[fn.__qualname__], [], []])

    def test_literal_nested_facades_restore_after_primary_failure(self):
        primary = ValueError("synthetic source")
        cause = LookupError("original cause")
        fn = synthetic("def prepare(): raise primary from cause", primary=primary, cause=cause)[
            "prepare"
        ]
        with self.observer():
            previous = sys.getprofile()
            facades, attempts = self._runner_facades(previous, {})
            facades[-1].setprofile(lambda frame, event, arg: None)
            try:
                with self.assertRaises(ValueError) as caught:
                    fn()
            finally:
                facades[-1].setprofile(None)
            self.assertIs(caught.exception, primary)
            self.assertIs(primary.__cause__, cause)
            self.assertIs(sys.getprofile(), previous)
            self.assertEqual(attempts, [[], [], []])

    def test_capture_failure_is_deferred_and_keeps_source_primary(self):
        primary = ValueError("source")
        fn = synthetic("def prepare(): raise primary", primary=primary)["prepare"]
        obs = self.observer()
        with patch.object(obs, "_stamp", side_effect=OSError("disk")):
            with self.assertRaises(ValueError) as caught:
                with obs:
                    fn()
        self.assertIs(caught.exception, primary)
        self.assertEqual(obs.errors[0]["type"], "OSError")

    def test_capture_failure_cannot_report_success(self):
        fn = synthetic("def prepare(): return 4")["prepare"]
        obs = self.observer()
        with patch.object(obs, "_stamp", side_effect=OSError("disk")):
            with self.assertRaises(d.DiagnosticFailure):
                with obs:
                    self.assertEqual(fn(), 4)
        self.assertTrue(obs.errors)

    def test_starting_observer_does_not_overwrite_existing_evidence(self):
        self.output.mkdir()
        (self.output / "timing.json").write_text("retained")
        with self.assertRaises(FileExistsError):
            with self.observer():
                self.fail("body must not run")
        self.assertEqual((self.output / "timing.json").read_text(), "retained")

    def test_unselected_code_does_not_consume_bounded_code_cache(self):
        obs = self.observer()
        with obs:
            for i in range(100):
                code = compile("pass", "<unselected-" + str(i) + ">", "exec")
                exec(code, {})
        self.assertEqual(obs.codes, {})

    def test_code_capacity_is_explicit_failure_and_never_source_credit(self):
        fn = synthetic("def prepare(): return 1")["prepare"]
        with patch.object(d, "MAX_CODES", 0):
            with self.assertRaises(d.DiagnosticFailure):
                with self.observer() as obs:
                    fn()
        self.assertEqual(obs.errors[0]["type"], "DiagnosticFailure")

    def test_stack_timer_is_scoped_to_worker_and_cancelled(self):
        with (
            patch.object(d.faulthandler, "dump_traceback_later") as start,
            patch.object(d.faulthandler, "cancel_dump_traceback_later") as cancel,
        ):
            with d.Observer(self.output, stack_interval=15):
                pass
        self.assertEqual(start.call_args.args, (15,))
        self.assertTrue(start.call_args.kwargs["repeat"])
        self.assertFalse(start.call_args.kwargs["exit"])
        cancel.assert_called_once_with()

    def test_primary_survives_final_flush_and_close_failures(self):
        primary = ValueError("source primary")
        primary.__cause__ = cause = LookupError("source cause")
        saved = []
        obs = self.observer()

        class Closing:
            def __init__(self, stream):
                self.stream = stream

            def close(self):
                self.stream.close()
                raise OSError("close failed")

        def failed_flush(status):
            raise OSError("flush failed")

        with patch.object(d.os, "write", side_effect=lambda fd, data: saved.append(data)):
            with self.assertRaises(ValueError) as caught:
                with obs:
                    obs.journal = Closing(obs.journal)
                    obs.flush = failed_flush
                    raise primary
        self.assertIs(caught.exception, primary)
        self.assertIs(primary.__cause__, cause)
        self.assertEqual(
            [r["stage"] for r in primary.mapping_setup_diagnostic_errors],
            ["journal_close", "final_metadata"],
        )
        self.assertEqual(json.loads(saved[0])["primary_type"], "ValueError")
        self.assertEqual(len(json.loads(saved[0])["secondary_errors"]), 2)

    def test_setup_primary_is_not_replaced_by_timer_cleanup_failure(self):
        primary, cleanup = ValueError("timer setup"), OSError("timer cleanup")
        saved = []
        obs = d.Observer(self.output, stack_interval=15)
        with (
            patch.object(d.faulthandler, "dump_traceback_later", side_effect=primary),
            patch.object(d.faulthandler, "cancel_dump_traceback_later", side_effect=cleanup),
            patch.object(d.os, "write", side_effect=lambda fd, data: saved.append(data)),
        ):
            with self.assertRaises(ValueError) as caught:
                with obs:
                    self.fail("setup failed before body")
        self.assertIs(caught.exception, primary)
        self.assertTrue(obs.journal.closed and obs.stack_stream.closed)
        self.assertEqual(primary.mapping_setup_diagnostic_errors[0]["stage"], "stack_timer_close")
        self.assertEqual(json.loads(saved[0])["status"], "setup_failed")

    def test_live_snapshot_retains_open_stage_without_claiming_completion(self):
        obs = self.observer()
        fn = synthetic(
            "def prepare(): obs.flush('in_progress'); return read()",
            obs=obs,
            read=lambda: json.loads((self.output / "timing.json").read_text()),
        )["prepare"]
        with obs:
            live = fn()
        self.assertEqual([r["function"] for r in live["open_calls"]], ["prepare"])
        self.assertFalse(live["source_success_native_entry_or_scientific_certificate"])


def main():
    """Standard unittest entry with saved per-case results and runtime hashes."""
    from validation.betse import betse_normal_channel_join_runtime as runtime

    output = Path(os.environ["CELLS_MAPPING_DIAGNOSTIC_EVIDENCE"])
    attempts, rows = [], []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "PIL", "jax"}:
                attempts.append(fullname)
                raise AssertionError("Scientific import forbidden")

    class Result(unittest.TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test)
            rows.append(dict(id=test.id(), outcome="passed"))

        def addFailure(self, test, err):
            super().addFailure(test, err)
            rows.append(
                dict(id=test.id(), outcome="failed", traceback=self._exc_info_to_string(err, test))
            )

        def addError(self, test, err):
            super().addError(test, err)
            rows.append(
                dict(id=test.id(), outcome="error", traceback=self._exc_info_to_string(err, test))
            )

    blocker = Block()
    previous = sys.getprofile()

    def guard(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and "/betse/science/" in frame.f_code.co_filename:
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Original native source entry forbidden")

    sys.meta_path.insert(0, blocker)
    sys.setprofile(guard)
    try:
        result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(ObserverTests)
        )
    finally:
        sys.setprofile(previous)
        sys.meta_path.remove(blocker)
        (output / "case-results.json").write_text(json.dumps(rows, indent=2) + "\n")
        (output / "native-entry-guard.json").write_text(json.dumps(dict(attempted=attempts)) + "\n")
        (output / "runtime-producers.json").write_text(
            json.dumps(runtime.inventory(), indent=2) + "\n"
        )
    return int(not result.wasSuccessful() or bool(attempts))


if __name__ == "__main__":
    raise SystemExit(main())
