"""Isolated stdlib observer controls; selected AST only, never image/native code."""

import ast
import hashlib
import importlib.abc
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/cells/processes/betse_native_single_cell_image_mask.py"
CALLER = ROOT / "src/cells/processes/betse_native_multi_cell_caller.py"
MAPPING_TEST = ROOT / "tests/unit/test_betse_native_multi_cell_tissue_to_grid.py"
MAPPING = ROOT / "src/cells/processes/betse_native_multi_cell_tissue_to_grid.py"
BASELINE = Path(os.environ.get("CELLS_TAPE_BASELINE_SOURCE", "/unavailable"))


def selected_tape(path, source, path_type):
    tree = ast.parse(path.read_text())
    nodes = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in {"_trace_spec", "_trace_bindings"}
    ]
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_Tape")
    cls.body = [
        n
        for n in cls.body
        if isinstance(n, ast.FunctionDef)
        and n.name in {"__init__", "trace", "_check_trace_metadata"}
    ]
    nodes.append(cls)
    namespace = dict(source=source, Path=path_type)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def capture(namespace):
    tree = ast.parse(CALLER.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_capture")
    space = dict(
        namespace,
        sys=sys,
        contextmanager=contextmanager,
        FunctionType=FunctionType,
        _mask_record=lambda _: None,
        captures=SimpleNamespace(
            _remember_observation_error=lambda c, e, **k: c.errors.append((e, k))
        ),
    )
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(CALLER), "exec"), space)
    return space["_capture"]


class ImageTapeTraceTests(unittest.TestCase):
    def setUp(self):
        self.attempts = []
        attempts = self.attempts

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "PIL", "jax"}:
                    attempts.append(fullname)
                    raise ImportError("Scientific/native import forbidden: " + fullname)

        self.block = Block()
        sys.meta_path.insert(0, self.block)
        self.addCleanup(lambda: sys.meta_path.remove(self.block))
        self.source = SimpleNamespace(
            __file__="/owned/source.py",
            SITES={"type_check": {"kind": "full"}, "load_image": {"kind": "full"}},
        )
        calls, resolved = [], {}
        self.path_calls, self.resolved = calls, resolved

        class CountingPath:
            def __init__(self, value):
                self.value = value

            def resolve(self):
                calls.append(self.value)
                return resolved.get(self.value, self.value)

        self.Path = CountingPath
        self.namespace = selected_tape(SOURCE, self.source, self.Path)
        self.Tape = self.namespace["_Tape"]

    def tearDown(self):
        self.assertEqual(self.attempts, [])

    def frame(self, name="load_image", *, filename=None, qualname=None, obj=None):
        return SimpleNamespace(
            f_code=SimpleNamespace(
                co_filename=filename or self.source.__file__,
                co_name=name,
                co_qualname=qualname or name,
            ),
            f_locals={} if obj is None else {"self": obj, "marker": "retained"},
        )

    def retain(self, label, value):
        if root := os.environ.get("CELLS_TAPE_TRACE_EVIDENCE"):
            folder = Path(root) / hashlib.sha256(self.id().encode()).hexdigest()[:20]
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / (label + ".json")).open("x") as stream:
                json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
                stream.write("\n")

    def test_construction_caches_immutable_selectors_once(self):
        tape = self.Tape(None)
        self.assertEqual(self.path_calls, [self.source.__file__])
        self.assertIs(tape._trace_metadata[0], self.source)
        self.assertIs(tape._trace_metadata[2], self.source.SITES)
        self.assertIsInstance(tape._trace_metadata[6], frozenset)
        self.assertNotIn("type_check", tape._trace_metadata[6])
        self.assertIn("get_clipped_points_index", tape._trace_metadata[6])
        self.retain(
            "metadata", dict(path_calls=self.path_calls, methods=sorted(tape._trace_metadata[6]))
        )

    def test_irrelevant_line_and_opcode_do_not_inspect_frames_or_resolve(self):
        tape = self.Tape(None)
        for event in ("line", "opcode"):
            result = tape.trace(object(), event, object())
            self.assertIs(result.__self__, tape)
        self.assertEqual(len(self.path_calls), 1)
        self.assertEqual(tape.events, [])

    def test_ten_thousand_unrelated_calls_reuse_cached_path_and_methods(self):
        tape = self.Tape(None)
        frame = self.frame("__init__", filename="/unrelated.py")
        methods = tape._trace_metadata[6]
        for _ in range(10_000):
            for event in ("call", "return", "exception"):
                tape.trace(frame, event, None)
        self.assertEqual(len(self.path_calls), 1)
        self.assertIs(tape._trace_metadata[6], methods)
        self.assertEqual(tape.events, [])
        self.retain(
            "metadata_operations",
            dict(
                unrelated_events=30_000,
                path_resolutions=1,
                methods_object_retained=True,
                events_recorded=0,
            ),
        )

    def test_matched_call_return_unwind_keep_raw_values_and_identity(self):
        tape = self.Tape(None)
        obj = SimpleNamespace(value=1)
        frame = self.frame("__init__", qualname="TissuePickerImageMask.__init__", obj=obj)
        primary = RuntimeError("original observer payload")
        for event, arg in (
            ("call", None),
            ("exception", (RuntimeError, primary, None)),
            ("return", None),
        ):
            tape.trace(frame, event, arg)
        self.assertIs(tape.mask, obj)
        self.assertIs(tape.locals[frame.f_code.co_qualname]["self"], obj)
        self.assertEqual([e["kind"] for e in tape.events], ["call", "exception", "return"])
        self.assertIs(tape.events[1]["error"], primary)
        self.retain(
            "matched",
            dict(
                kinds=[e["kind"] for e in tape.events],
                locals=sorted(tape.locals),
                raw_error_identity_preserved=tape.events[1]["error"] is primary,
            ),
        )

    def test_unknown_source_method_keeps_metadata_validation_without_event(self):
        tape = self.Tape(None)
        tape.trace(self.frame("unselected_helper"), "return", None)
        self.assertEqual(len(self.path_calls), 2)
        self.assertEqual(tape.events, [])

    def test_source_module_and_filename_retarget_refuse(self):
        for kind in ("module", "filename"):
            with self.subTest(kind=kind):
                namespace = selected_tape(SOURCE, self.source, self.Path)
                tape = namespace["_Tape"](None)
                if kind == "module":
                    namespace["source"] = SimpleNamespace(**vars(self.source))
                else:
                    self.source.__file__ = "/retargeted.py"
                with self.assertRaises(ValueError):
                    tape.trace(self.frame(), "call", None)
                self.assertEqual(tape.events, [])
                self.source.__file__ = "/owned/source.py"

    def test_equal_site_mapping_replacement_refuses_before_recording(self):
        tape = self.Tape(None)
        self.source.SITES = dict(self.source.SITES)
        with self.assertRaises(ValueError):
            tape.trace(self.frame(), "call", None)
        self.assertEqual(tape.events, [])

    def test_site_key_and_value_mutation_refuse_at_matching_or_owner_check(self):
        for kind in ("key", "value"):
            with self.subTest(kind=kind):
                self.source.SITES = {"load_image": {"kind": "full"}}
                tape = self.Tape(None)
                if kind == "key":
                    self.source.SITES["added"] = {"kind": "full"}
                else:
                    self.source.SITES["load_image"]["kind"] = "changed"
                with self.assertRaises(ValueError):
                    tape.trace(self.frame(), "return", None)
                with self.assertRaises(ValueError):
                    tape._check_trace_metadata()
                self.assertEqual(tape.events, [])

    def test_cached_path_or_methods_tamper_refuses_owner_check(self):
        for index, value in ((5, "/wrong.py"), (6, frozenset(("wrong",)))):
            with self.subTest(index=index):
                tape = self.Tape(None)
                old = tape._trace_metadata
                tape._trace_metadata = (*old[:index], value, *old[index + 1 :])
                with self.assertRaises(ValueError):
                    tape._check_trace_metadata()

    def test_resolved_source_path_drift_is_not_hidden_by_cache(self):
        tape = self.Tape(None)
        self.resolved[self.source.__file__] = "/retargeted/source.py"
        with self.assertRaises(ValueError):
            tape._check_trace_metadata()

    def test_same_callable_code_mutation_refuses_owner_check(self):
        tape = self.Tape(None)
        original = self.Tape.trace.__code__
        self.Tape.trace.__code__ = original.replace()
        with self.assertRaises(ValueError):
            tape._check_trace_metadata()

    def test_path_resolver_callable_code_is_retained(self):
        tape = self.Tape(None)
        self.Path.resolve.__code__ = self.Path.resolve.__code__.replace()
        with self.assertRaises(ValueError):
            tape._check_trace_metadata()

    def test_audit_boundary_keeps_source_and_trace_checks(self):
        tree = ast.parse(SOURCE.read_text())
        audit = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_audit")
        first = audit.body[0]
        self.assertEqual(ast.unparse(first), "tape._check_trace_metadata()")
        graph = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_graph")
        self.assertIn("trace_callable_bindings", ast.unparse(graph))

    def test_caller_trace_preserves_inherited_events_profiler_and_primary(self):
        for unwind in (False, True):
            with self.subTest(unwind=unwind):
                tape = self.Tape(None)
                primary, cause = RuntimeError("source primary"), ValueError("source cause")
                namespace = dict(primary=primary, cause=cause, unwind=unwind)
                exec(
                    compile(
                        "def get_image_mask():\n"
                        "    marker='raw'\n"
                        "    if unwind:raise primary from cause\n"
                        "    return marker\n",
                        self.source.__file__,
                        "exec",
                    ),
                    namespace,
                )
                site = namespace["get_image_mask"]
                observed = []
                context = SimpleNamespace(
                    tape=SimpleNamespace(codes={site.__code__}, trace=lambda *a: None),
                    image_tape=tape,
                    local_codes={site.__code__},
                    locals={},
                    observer=None,
                    mask=None,
                    errors=[],
                )

                def previous(frame, event, arg, code=site.__code__, log=observed):
                    if frame.f_code is code:
                        log.append(event)
                    return previous

                outer, profile = sys.gettrace(), sys.getprofile()
                sys.settrace(previous)
                try:
                    with capture(self.namespace)(context):
                        if unwind:
                            with self.assertRaises(RuntimeError) as caught:
                                site()
                            self.assertIs(caught.exception, primary)
                            self.assertIs(primary.__cause__, cause)
                        else:
                            self.assertEqual(site(), "raw")
                    self.assertIs(sys.gettrace(), previous)
                    self.assertIs(sys.getprofile(), profile)
                finally:
                    sys.settrace(outer)
                    sys.setprofile(profile)
                self.assertIn("line", observed)
                self.assertEqual(
                    [e["kind"] for e in tape.events],
                    ["call", "exception", "return"] if unwind else ["call", "return"],
                )
                self.assertEqual(context.errors, [])
                self.retain(
                    "caller_unwind_" + str(unwind),
                    dict(
                        caller_events=observed,
                        image_events=[e["kind"] for e in tape.events],
                        primary_identity_retained=not unwind or primary.__cause__ is cause,
                    ),
                )

    def test_retained_original_trace_event_records_are_equal(self):
        if not BASELINE.is_file():
            self.skipTest("Pinned observer baseline is supplied by the software runner")
        expected = os.environ["CELLS_TAPE_BASELINE_SHA256"]
        self.assertEqual(hashlib.sha256(BASELINE.read_bytes()).hexdigest(), expected)
        old = selected_tape(BASELINE, self.source, self.Path)["_Tape"](None)
        new = self.Tape(None)
        obj = SimpleNamespace(value=13)
        primary = ValueError("raw original")
        for name, qual in (
            ("load_image", "load_image"),
            ("__init__", "TissuePickerImage.__init__"),
            ("__init__", "TissuePickerImageMask.__init__"),
            ("unselected", "unselected"),
        ):
            frame = self.frame(name, qualname=qual, obj=obj)
            for event, arg in (
                ("call", None),
                ("line", None),
                ("exception", (ValueError, primary, None)),
                ("return", None),
            ):
                old.trace(frame, event, arg)
                new.trace(frame, event, arg)
        self.assertEqual(old.events, new.events)
        self.assertEqual(old.locals, new.locals)
        self.assertIs(old.mask, new.mask)
        self.assertIs(old.picker, new.picker)
        self.retain(
            "baseline_comparison",
            dict(
                events_equal=True,
                locals_equal=True,
                original_event_count=len(old.events),
                baseline_sha256=expected,
            ),
        )

    def test_fixture_facade_keeps_replaced_method_dictionary_live(self):
        tree = ast.parse(MAPPING_TEST.read_text())
        node = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "_environment_facade"
        )
        namespace = {}
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), str(MAPPING_TEST), "exec"), namespace
        )
        original, replacement, template = {}, {}, object()
        continuation = object()
        environment = SimpleNamespace(_METHODS=original, prepare_continuation=object())
        facade = namespace["_environment_facade"](environment, continuation)
        self.assertIs(facade._METHODS, original)
        environment._METHODS = replacement
        facade._METHODS["cellMatrices"] = template
        self.assertIs(facade._METHODS, replacement)
        self.assertIs(replacement["cellMatrices"], template)
        self.assertNotIn("cellMatrices", original)
        self.assertIs(facade.prepare_continuation, continuation)
        self.retain(
            "fixture_facade",
            dict(replacement_dictionary_used=True, obsolete_dictionary_unchanged=True),
        )

    def test_compact_fixture_failure_keeps_primary_chain_without_live_repr(self):
        tree = ast.parse(MAPPING_TEST.read_text())
        node = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "_fixture_error_record"
        )
        namespace = {}
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), str(MAPPING_TEST), "exec"), namespace
        )

        class RawOwner:
            def __repr__(self):
                raise AssertionError("Failed owner repr must not execute")

        primary = AttributeError("missing synthetic mem_i")
        outer = RuntimeError("synthetic setup rejected")
        outer.source_error, outer.capture_error = primary, None
        outer.partial = dict(caller=RawOwner())
        outer.__cause__ = primary
        record = namespace["_fixture_error_record"](outer)
        self.assertEqual(record["source"]["arguments"], ["missing synthetic mem_i"])
        self.assertEqual(record["cause"], dict(ref=record["source"]["token"]))
        self.assertEqual(record["partial_keys"], ["caller"])
        self.assertFalse(record["complete_failed_live_owner_serialization"])
        self.retain("compact_fixture_failure", record)

    def test_fixture_retains_full_real_file_proof_and_refuses_changed_bytes(self):
        tree = ast.parse(MAPPING.read_text())
        node = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_verify_pin_bytes"
        )
        namespace = dict(hashlib=hashlib, Path=Path)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(MAPPING), "exec"), namespace)
        helper = next(
            n
            for n in ast.parse(MAPPING_TEST.read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name == "_fixture_verified_sources"
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "immutable.py"
            path.write_bytes(b"original source bytes\n")
            pins = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()}
            stage = SimpleNamespace(
                _verify_sources=lambda: dict(pins), _verify_pin_bytes=namespace["_verify_pin_bytes"]
            )
            space = dict(stage=stage)
            exec(
                compile(ast.Module(body=[helper], type_ignores=[]), str(MAPPING_TEST), "exec"),
                space,
            )
            verify = space["_fixture_verified_sources"]()
            stage._verify_sources = lambda: {"synthetic-continuation": "blocked-native"}
            self.assertEqual(verify(), pins)
            returned = verify()
            returned.clear()
            self.assertEqual(verify(), pins)
            path.write_bytes(b"changed source bytes\n")
            with self.assertRaises(ValueError):
                verify()
            self.retain(
                "retained_file_proof",
                dict(
                    complete_original_pins_retained=True,
                    synthetic_label_never_a_file_pin=True,
                    changed_bytes_refused=True,
                    result_map_cannot_change_retained_proof=True,
                ),
            )


if __name__ == "__main__":
    unittest.main()
