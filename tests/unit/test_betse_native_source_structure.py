"""Metadata-only structural-cache checks; native text is never executed."""

import ast
import hashlib
import importlib.abc
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from cells.processes import betse_native_source_structure as s

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = (
    b"class Example:\n    def first(self, value=2):\n        self.x = value\n"
    b"        return value\n    def second(self):\n        self.y = 3\n"
)
TAIL = (
    (517, "lapGJinv", "None"),
    (518, "lapGJ", "None"),
    (521, "M_sum_mem_to_ecm", "None"),
    (522, "gradMem", "None"),
    (525, "cell_i", "np.asarray(self.cell_i)"),
    (526, "gj_default_weights", "np.ones(len(self.mem_i))"),
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verifier(path, namespace):
    """Compile only the real metadata verifier, not its production module."""
    node = next(
        n
        for n in ast.parse(path.read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "_verify_sources"
    )
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_verify_sources"]


class StructureTests(unittest.TestCase):
    def setUp(self):
        s._method.cache_clear()
        s._definition.cache_clear()
        s._assignment.cache_clear()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.proof = {}

    def tearDown(self):
        self.proof["cache"] = s._method.cache_info()._asdict()
        self.proof["definition_cache"] = s._definition.cache_info()._asdict()
        self.proof["assignment_cache"] = s._assignment.cache_info()._asdict()
        s._method.cache_clear()
        s._definition.cache_clear()
        s._assignment.cache_clear()

    def test_structures_match_direct_parser_without_exposing_mutable_nodes(self):
        result = s.method(SAMPLE, "Example", "first")
        fn = ast.parse(SAMPLE).body[0].body[0]
        self.assertEqual(result[0], ast.dump(fn.args))
        self.assertEqual(result[1], ast.dump(ast.Module(body=fn.body, type_ignores=[])))
        self.assertEqual(result[2], ("self", "value"))
        self.assertEqual(tuple(r[1] for r in result[3]), tuple(ast.dump(n) for n in fn.body))

        def immutable(value):
            return type(value) in (str, int) or (
                type(value) is tuple and all(map(immutable, value))
            )

        self.assertTrue(immutable(result))
        self.proof["signature_sha256"] = digest(repr(result).encode())

    def test_first_method_and_line_selection_keep_source_order(self):
        first = s.method(SAMPLE, "Example", None)
        self.assertEqual(first, s.method(SAMPLE, "Example", "first"))
        selected = s.method(SAMPLE, "Example", "first", (4, 3, 4))
        self.assertEqual([r[0] for r in selected[3]], [3, 4])
        self.assertEqual(selected, first)
        self.assertEqual(s.method(SAMPLE, "Example", "second")[3][0][0], 6)
        self.assertEqual(s.method(SAMPLE, "Example", "first", (99,))[3], ())

    def test_hit_reuses_parsing_only(self):
        with patch.object(s.ast, "parse", wraps=ast.parse) as parse:
            a = s.method(SAMPLE, "Example", "first")
            b = s.method(bytes(bytearray(SAMPLE)), "Example", "first")
            self.assertIs(a, b)
            self.assertEqual(parse.call_count, 1)
        self.assertEqual(s._method.cache_info().hits, 1)

    def test_changed_bytes_with_identical_path_size_and_mtime_do_not_hit(self):
        path = self.folder / "source.py"
        path.write_bytes(SAMPLE)
        stamp = path.stat().st_mtime_ns
        before = s.method(path.read_bytes(), "Example", "first")
        changed = SAMPLE.replace(b"value=2", b"value=7")
        path.write_bytes(changed)
        os.utime(path, ns=(stamp, stamp))
        after = s.method(path.read_bytes(), "Example", "first")
        self.assertNotEqual(before, after)
        self.assertEqual(path.stat().st_mtime_ns, stamp)
        self.assertEqual(len(SAMPLE), len(changed))
        self.proof.update(before=digest(SAMPLE), after=digest(changed), mtime_ns=stamp)

    def test_eviction_and_clear_preserve_values(self):
        expected = s.method(SAMPLE, "Example", "first")
        for i in range(s.CACHE_SIZE + 1):
            s.method(SAMPLE + f"# distinct {i}\n".encode(), "Example", "first")
        self.assertEqual(s._method.cache_info().currsize, s.CACHE_SIZE)
        self.assertEqual(s.method(SAMPLE, "Example", "first"), expected)
        s._method.cache_clear()
        self.assertEqual(s.method(SAMPLE, "Example", "first"), expected)

    def test_parse_failure_is_not_cached_as_success(self):
        with patch.object(s.ast, "parse", wraps=ast.parse) as parse:
            for _ in range(2):
                with self.assertRaises(SyntaxError):
                    s.method(b"class (", "Example", None)
            self.assertEqual(parse.call_count, 2)
        self.assertEqual(s._method.cache_info().currsize, 0)

    def test_inputs_and_output_capacity_refuse_before_cache_admission(self):
        for raw in (bytearray(SAMPLE), b" " * (s.MAX_SOURCE_BYTES + 1)):
            with self.assertRaises(ValueError):
                s.method(raw, "Example", None)
        for lines in ([3], (True,), (3.0,)):
            with self.assertRaises(TypeError):
                s.method(SAMPLE, "Example", "first", lines)
        with patch.object(s, "MAX_SIGNATURE_CHARS", 1):
            with self.assertRaises(ValueError):
                s.method(SAMPLE, "Example", "first")
        self.assertEqual(s._method.cache_info().currsize, 0)

    def test_missing_selector_and_first_target_refusals_remain_explicit(self):
        with self.assertRaises(StopIteration):
            s.method(SAMPLE, "Missing", None)
        with self.assertRaises(StopIteration):
            s.method(SAMPLE, "Example", "missing")
        rows = s.method(SAMPLE, "Example", "first")[3]
        self.assertEqual(s.target_attribute(rows[0]), "x")
        with self.assertRaisesRegex(AttributeError, "Return.*targets"):
            s.target_attribute(rows[1])
        raw = b"class Example:\n    def first(self):\n        local = 1\n"
        with self.assertRaisesRegex(AttributeError, "Name.*attr"):
            s.target_attribute(s.method(raw, "Example", "first")[3][0])

    def test_bindings_detect_hidden_cached_body_code_drift(self):
        s.method(SAMPLE, "Example", "first")
        original = s._method.__wrapped__.__code__
        before = s.bindings()

        def replacement(raw, class_name, method_name, lines):
            raise AssertionError("Never executed")

        try:
            s._method.__wrapped__.__code__ = replacement.__code__
            self.assertNotEqual(before, s.bindings())
            # The already cached value is unchanged: live bindings, not a
            # changed result, must expose this otherwise hidden mutation.
            self.assertEqual(s.method(SAMPLE, "Example", "first")[2], ("self", "value"))
        finally:
            s._method.__wrapped__.__code__ = original
        self.assertEqual(s.bindings(), before)

    def test_bindings_expose_default_selector_change_even_when_code_is_equal(self):
        before, code, defaults = s.bindings(), s.method.__code__, s.method.__defaults__
        full = s.method(SAMPLE, "Example", "first")
        try:
            s.method.__defaults__ = ((),)
            empty = s.method(SAMPLE, "Example", "first")
            self.assertEqual(empty[3], ())
            self.assertNotEqual(empty, full)
            self.assertIs(s.method.__code__, code)
            self.assertNotEqual(s.bindings(), before)
        finally:
            s.method.__defaults__ = defaults
        self.assertEqual(s.bindings(), before)

    def test_callable_atoms_bind_defaults_keyword_defaults_and_closure(self):
        def factory():
            closed = 7

            def fn(arg=3, *, kw=4):
                return closed + arg + kw

            return fn

        fn = factory()
        before = s._atoms(fn)
        fn.__kwdefaults__["kw"] = 6
        self.assertNotEqual(before, s._atoms(fn))
        before = s._atoms(fn)
        fn.__closure__[0].cell_contents = 8
        self.assertNotEqual(before, s._atoms(fn))

    def test_selector_keys_are_bounded_before_parsing(self):
        with patch.object(s.ast, "parse", side_effect=AssertionError("Must not parse")):
            for name, lines in (
                ("X" * (s.MAX_SELECTOR_CHARS + 1), None),
                ("Example", tuple(range(1, s.MAX_SELECTED_LINES + 2))),
                ("Example", (0,)),
                ("Example", (s.MAX_SOURCE_BYTES + 1,)),
            ):
                with self.assertRaises(ValueError):
                    s.method(SAMPLE, name, "first", lines)
        self.assertEqual(s._method.cache_info().currsize, 0)

    def test_literal_owner_checker_detects_nested_default_shape_without_code_change(self):
        path = ROOT / "src/cells/processes/betse_native_single_cell_caller_completion.py"
        node = next(
            n
            for n in ast.parse(path.read_bytes()).body
            if isinstance(n, ast.FunctionDef) and n.name == "_check_binding_identity"
        )
        namespace = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        check = namespace["_check_binding_identity"]
        original, defaults = s.bindings(), s.method.__defaults__
        check(s.bindings(), original)
        try:
            for changed in (((),), ((None,),), (((None,),),)):
                s.method.__defaults__ = changed
                with self.assertRaisesRegex(ValueError, "identity changed"):
                    check(s.bindings(), original)
        finally:
            s.method.__defaults__ = defaults
        check(s.bindings(), original)
        self.proof["literal_owner_checker_sha256"] = digest(path.read_bytes())

    def test_repeated_callable_metadata_is_bounded_even_with_few_unique_values(self):
        def fn():
            return None

        fn.__defaults__ = (None,) * 65
        with self.assertRaisesRegex(ValueError, "capacity"):
            s._atoms(fn)
        fn.__defaults__ = None
        fn.__kwdefaults__ = {str(i): None for i in range(65)}
        with self.assertRaisesRegex(ValueError, "capacity"):
            s._atoms(fn)
        fn.__kwdefaults__ = None
        repeated = (None,) * 64
        fn.__defaults__ = (repeated,) * 64
        with self.assertRaisesRegex(ValueError, "capacity"):
            s._atoms(fn)

    def test_bindings_detect_parser_and_helper_replacement_after_cache_hit(self):
        s.method(SAMPLE, "Example", "first")
        for owner, name in ((s.ast, "parse"), (s, "_target"), (s, "target_attribute")):
            before = s.bindings()
            with patch.object(owner, name, lambda *args: None):
                self.assertNotEqual(before, s.bindings())
            self.assertEqual(before, s.bindings())

    def setup_verifiers(self):
        native = self.folder / "betse/science"
        (native / "math").mkdir(parents=True)
        lines = [""] * 526
        lines[0:2] = ["class Cells:", "    def make_world(self):"]
        for line, statement in (
            (503, "a = 1"),
            (504, "self.lapENVinv = a"),
            (511, "b = 2"),
            (512, "self.lapENV_P_inv = b"),
        ):
            lines[line - 1] = "        " + statement
        for line, name, expression in TAIL:
            lines[line - 1] = f"        self.{name} = {expression}"
        cells = native / "cells.py"
        cells.write_text("\n".join(lines) + "\n")
        grid = native / "math/finitediff.py"
        grid.write_text(
            "class FiniteDiffSolver:\n    def makeLaplacian(self, bound=None):\n"
            "        return bound\n"
        )
        copied = self.folder / "poisson_source.py"
        copied.write_text(
            "class FiniteDiffPoisson:\n    def makeLaplacian(self, bound=None):\n"
            "        return bound\n"
            "class CellsPoisson:\n    def value(self):\n        a = 1\n        self.lapENVinv = a\n"
            "    def flux(self):\n        b = 2\n        self.lapENV_P_inv = b\n"
        )
        tail = self.folder / "tail_source.py"
        tail.write_text(
            "class CellsWorldTail:\n"
            + "".join(
                f"    def store_{i}(self):\n        self.{name} = {expression}\n"
                for i, (_, name, expression) in enumerate(TAIL)
            )
        )
        calls = []

        def predecessor():
            calls.append(len(calls))
            return {"predecessor": str(len(calls))}

        p_source = SimpleNamespace(
            __file__=str(copied),
            CELLS_SHA256=digest(cells.read_bytes()),
            GRID_SHA256=digest(grid.read_bytes()),
            CALLER_LINES=((503, 504), (511, 512)),
        )
        t_source = SimpleNamespace(
            __file__=str(tail),
            CELLS_SHA256=p_source.CELLS_SHA256,
            STORE_LINES=tuple(row[0] for row in TAIL),
        )
        common = dict(
            hashlib=hashlib,
            Path=Path,
            structure=s,
            geometry=SimpleNamespace(callers=SimpleNamespace(NATIVE_ROOT=self.folder)),
        )
        p_path = ROOT / "src/cells/processes/betse_native_multi_cell_poisson.py"
        t_path = ROOT / "src/cells/processes/betse_native_multi_cell_world_finalization.py"
        p_ns = dict(
            common,
            __name__="p_verifier",
            source=p_source,
            METHODS=("value", "flux"),
            environment=SimpleNamespace(_verify_sources=predecessor),
            observation=SimpleNamespace(__file__=__file__),
            sys=SimpleNamespace(modules={"p_verifier": SimpleNamespace(__file__=str(p_path))}),
        )
        p_verify = verifier(p_path, p_ns)
        t_ns = dict(
            common,
            __name__="t_verifier",
            source=t_source,
            METHODS=tuple(f"store_{i}" for i in range(6)),
            STORES=tuple(row[1] for row in TAIL),
            poisson=SimpleNamespace(_verify_sources=p_verify),
            sys=SimpleNamespace(modules={"t_verifier": SimpleNamespace(__file__=str(t_path))}),
        )
        return SimpleNamespace(
            p=p_verify,
            t=verifier(t_path, t_ns),
            p_ns=p_ns,
            t_ns=t_ns,
            p_source=p_source,
            t_source=t_source,
            cells=cells,
            grid=grid,
            copied=copied,
            tail=tail,
            calls=calls,
        )

    def test_real_verifiers_keep_fresh_predecessor_and_producer_pins_on_hits(self):
        v = self.setup_verifiers()
        first = v.t()
        second = v.t()
        self.assertEqual(v.calls, [0, 1])
        self.assertEqual(first["predecessor"], "1")
        self.assertEqual(second["predecessor"], "2")
        for path in (v.copied, v.tail, Path(s.__file__)):
            self.assertEqual(second[str(path.resolve())], digest(path.read_bytes()))
        self.assertGreater(s._method.cache_info().hits, 0)
        self.proof["producer_pins"] = second

    def test_real_verifier_rejects_native_byte_drift_after_cached_success(self):
        v = self.setup_verifiers()
        v.t()
        raw, stat = v.grid.read_bytes(), v.grid.stat()
        v.grid.write_bytes(raw.replace(b"return bound", b"return False"))
        os.utime(v.grid, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "Original environmental Poisson source changed"):
            v.t()
        self.assertEqual(v.calls, [0, 1])

    def test_real_verifier_rejects_owned_body_and_signature_drift_after_hit(self):
        v = self.setup_verifiers()
        v.t()
        raw = v.copied.read_bytes()
        for changed in (raw.replace(b"a = 1", b"a = 7"), raw.replace(b"bound=None", b"bound=1")):
            v.copied.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "Literal"):
                v.t()
        v.copied.write_bytes(raw)
        v.t()

    def test_real_verifier_unchanged_ast_new_comment_has_new_producer_pin(self):
        v = self.setup_verifiers()
        original = v.t()[str(v.tail.resolve())]
        v.tail.write_bytes(v.tail.read_bytes() + b"# metadata only\n")
        current = v.t()[str(v.tail.resolve())]
        self.assertNotEqual(current, original)
        self.assertEqual(current, digest(v.tail.read_bytes()))

    def test_real_verifier_selectors_and_roster_remain_live(self):
        v = self.setup_verifiers()
        v.t()
        with patch.object(v.p_source, "CALLER_LINES", ((503,), (511, 512))):
            with self.assertRaisesRegex(ValueError, "caller statements"):
                v.t()
        with patch.object(v.t_source, "STORE_LINES", (517, 518, 521, 522, 525)):
            with self.assertRaisesRegex(ValueError, "six native"):
                v.t()
        v.t_ns["STORES"] = tuple(reversed(v.t_ns["STORES"]))
        with self.assertRaisesRegex(ValueError, "roster/order"):
            v.t()

    def test_real_tail_verifier_refuses_changed_target_and_extra_body(self):
        v = self.setup_verifiers()
        v.t()
        raw = v.tail.read_bytes()
        for changed in (
            raw.replace(b"self.lapGJ =", b"self.changed ="),
            raw.replace(b"self.lapGJ = None", b"self.lapGJ = None\n        pass"),
            raw.replace(b"store_1(self)", b"store_1(self, extra)"),
        ):
            v.tail.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "Literal make_world data store"):
                v.t()

    def test_predecessor_refusal_is_never_cached_or_bypassed(self):
        v = self.setup_verifiers()
        v.t()
        primary = LookupError("upstream authority changed")
        with patch.object(v.p_ns["environment"], "_verify_sources", side_effect=primary):
            with self.assertRaises(LookupError) as caught:
                v.t()
        self.assertIs(caught.exception, primary)

    def test_cached_success_does_not_hide_missing_files(self):
        v = self.setup_verifiers()
        v.t()
        v.grid.unlink()
        with self.assertRaises(FileNotFoundError):
            v.t()

    def test_full_definition_preserves_all_function_metadata(self):
        raw = (
            b"class Example:\n    @marker\n    def first(self, value: int=2) -> str:\n"
            b"        return value\n"
        )
        node = ast.parse(raw).body[0].body[0]
        self.assertEqual(s.definition(raw, "Example", "first"), ast.dump(node))
        self.assertEqual(s.definition(raw, "Example", None), ast.dump(node))
        for changed in (
            raw.replace(b"@marker", b"@other"),
            raw.replace(b"-> str", b"-> int"),
            raw.replace(b"first(", b"renamed("),
            raw.replace(b"int=2", b"int=3"),
        ):
            self.assertNotEqual(
                s.definition(raw, "Example", None), s.definition(changed, "Example", None)
            )
        self.assertEqual(
            s.method(raw, "Example", "first")[1], s.method(changed, "Example", None)[1]
        )

    def test_assignment_keeps_direct_order_and_any_target_position(self):
        raw = (
            b"class Example:\n    def world(self):\n"
            b"        if True:\n            self.grid_len = 9\n"
            b"        self.other = self.grid_len = 2\n"
            b"        self.grid_len = 3\n"
        )
        body = ast.parse(raw).body[0].body[0].body
        expected = ast.dump(ast.Module(body=[body[1]], type_ignores=[]))
        self.assertEqual(s.assignment(raw, "Example", "world", "grid_len"), expected)
        with self.assertRaises(StopIteration):
            s.assignment(raw, "Example", "world", "absent")
        annotated = b"class Example:\n    def world(self):\n        self.grid_len: int = 2\n"
        with self.assertRaises(StopIteration):
            s.assignment(annotated, "Example", "world", "grid_len")

    def test_class_occurrence_is_explicit_in_immutable_cache_keys(self):
        raw = SAMPLE + SAMPLE.replace(b"value=2", b"value=7")
        first, last = ast.parse(raw).body
        for last_class, node in ((False, first.body[0]), (True, last.body[0])):
            self.assertEqual(
                s.definition(raw, "Example", "first", last_class=last_class), ast.dump(node)
            )
            self.assertEqual(
                s.method(raw, "Example", "first", last_class=last_class)[0], ast.dump(node.args)
            )
        self.assertNotEqual(
            s.definition(raw, "Example", "first"),
            s.definition(raw, "Example", "first", last_class=True),
        )
        for call in (s.method, s.definition):
            with self.assertRaises(TypeError):
                call(raw, "Example", "first", last_class=1)

    def test_new_structural_caches_bind_hidden_bodies_and_refuse_bad_keys(self):
        s.definition(SAMPLE, "Example", "first")
        s.assignment(SAMPLE, "Example", "first", "x")
        for cached in (s._definition, s._assignment):
            original = cached.__wrapped__.__code__
            before = s.bindings()
            try:
                cached.__wrapped__.__code__ = original.replace(co_name="changed_metadata")
                self.assertNotEqual(s.bindings(), before)
            finally:
                cached.__wrapped__.__code__ = original
            self.assertEqual(s.bindings(), before)
        with patch.object(s.ast, "parse", side_effect=AssertionError("No parsing")):
            self.assertIsInstance(s.definition(SAMPLE, "Example", "first"), str)
            self.assertIsInstance(s.assignment(SAMPLE, "Example", "first", "x"), str)
            with self.assertRaises(ValueError):
                s.definition(bytearray(SAMPLE), "Example", None)
            with self.assertRaises(ValueError):
                s.assignment(SAMPLE, "Example", "first", "x" * (s.MAX_SELECTOR_CHARS + 1))
            with self.assertRaises(TypeError):
                s.assignment(SAMPLE, "Example", "first", None)
        for call in (
            lambda: s.definition(SAMPLE + b"# capacity\n", "Example", "first"),
            lambda: s.assignment(SAMPLE + b"# capacity\n", "Example", "first", "x"),
        ):
            with patch.object(s, "MAX_SIGNATURE_CHARS", 1):
                with self.assertRaisesRegex(ValueError, "capacity"):
                    call()

    def setup_multi_verifiers(self):
        native = self.folder / "betse/science"
        (native / "math").mkdir(parents=True)
        geometry_names = ("cellVerts", "cellMatrices", "cell_vols", "mem_processing", "near_neigh")

        def bodies(names):
            return "".join(
                f"    def {name}(self, p):\n        self.{name}_done = 1\n" for name in names
            )

        index = "    def cell_index(self, p) -> int:\n        return self.mesh\n"
        clip = "    def clip_and_refine(self, mask=None):\n        return mask\n"
        world = "    def make_world(self):\n        self.grid_len = len(self.cell_i)\n"
        grid_text = (
            "class FiniteDiffSolver:\n    def __init__(self):\n        self.ready = 1\n"
            "    def cell_grid(self, p):\n        self.shape = 2\n"
        )
        cells, mesh, grid = (
            native / "cells.py",
            native / "math/mesh.py",
            native / "math/finitediff.py",
        )
        cells.write_text(
            "class Cells:\n"
            + index
            + world
            + bodies((*geometry_names, "makeECM", "environment", "make_maskM"))
        )
        mesh.write_text("class DECMesh:\n" + clip)
        grid.write_text(grid_text)
        parameters = native / "parameters.py"
        parameters.write_text("# source pin only; never executed\n")

        def module(name, text):
            path = self.folder / (name + ".py")
            path.write_text(text)
            value = ModuleType(name)
            value.__file__ = str(path)
            return value

        source = module(
            "multi_source",
            "class ParameterStores:\n    def initialize_source_stores(self):\n"
            "        self.wsx = 1\n"
            "class CellsMulti:\n    def make_voronoi_non_svg(self):\n        self.mesh = 2\n"
            + index
            + "class MeshPipeline:\n"
            + clip,
        )
        source.NATIVE_PINS = {
            "cells.py": digest(cells.read_bytes()),
            "math/mesh.py": digest(mesh.read_bytes()),
            "parameters.py": digest(parameters.read_bytes()),
        }
        source.STORES_AST_SHA256 = digest(
            s.method(
                Path(source.__file__).read_bytes(), "ParameterStores", "initialize_source_stores"
            )[1].encode()
        )
        source.CALLER_AST_SHA256 = digest(
            s.method(Path(source.__file__).read_bytes(), "CellsMulti", "make_voronoi_non_svg")[
                1
            ].encode()
        )
        geom_source = module("geometry_source", "class CellKernel:\n" + bodies(geometry_names))
        ecm_source = module("ecm_source", "class CellsECM:\n" + bodies(("makeECM",)) + grid_text)
        ecm_source.CELLS_SHA256, ecm_source.GRID_SHA256 = (
            digest(cells.read_bytes()),
            digest(grid.read_bytes()),
        )
        env_source = module(
            "environment_source",
            "class CellsEnvironment:\n"
            + bodies(("environment", "make_maskM"))
            + "    def assign_grid_len(self):\n        self.grid_len = len(self.cell_i)\n",
        )
        env_source.NATIVE_CELLS_SHA256 = ecm_source.CELLS_SHA256
        geometry = module("geometry", "# metadata dependency\n")
        geometry.source, geometry.METHODS = geom_source, geometry_names
        dummy = module("dependency", "# metadata dependency\n")
        dummy.source = dummy
        calls, alias_calls = [], []

        def predecessor():
            calls.append(len(calls))
            return {"predecessor": str(len(calls))}

        def aliases():
            alias_calls.append(len(alias_calls))
            return {"descriptor_predecessor": str(len(alias_calls))}

        dummy.source_pins = aliases
        caller_path = ROOT / "src/cells/processes/betse_native_multi_cell_caller.py"
        env_path = ROOT / "src/cells/processes/betse_native_multi_cell_environment.py"
        caller_module, env_module = ModuleType("multi_verifier"), ModuleType("env_verifier")
        caller_module.__file__, env_module.__file__ = str(caller_path), str(env_path)
        common = dict(hashlib=hashlib, Path=Path, structure=s)
        caller_ns = dict(
            common,
            images=SimpleNamespace(_verify_sources=predecessor),
            callers=SimpleNamespace(NATIVE_ROOT=self.folder),
            initial=dummy,
            clipped=dummy,
            lifecycle=dummy,
            source=source,
            accounting=dummy,
            atoms=dummy,
            __name__="multi_verifier",
            sys=SimpleNamespace(modules={"multi_verifier": caller_module}),
        )
        caller = verifier(caller_path, caller_ns)
        env_ns = dict(
            common,
            multi=SimpleNamespace(_verify_sources=caller, callers=caller_ns["callers"]),
            geometry=geometry,
            ecm_source=ecm_source,
            environment_source=env_source,
            aliases=dummy,
            __name__="env_verifier",
            sys=SimpleNamespace(modules={"env_verifier": env_module}),
        )
        return SimpleNamespace(
            c=caller,
            e=verifier(env_path, env_ns),
            caller_ns=caller_ns,
            env_ns=env_ns,
            source=source,
            env_source=env_source,
            ecm_source=ecm_source,
            geometry=geometry,
            cells=cells,
            mesh=mesh,
            grid=grid,
            calls=calls,
            alias_calls=alias_calls,
        )

    def test_multi_verifiers_reuse_only_syntax_and_keep_both_predecessors_live(self):
        v = self.setup_multi_verifiers()
        first = v.e()
        with patch.object(s.ast, "parse", side_effect=AssertionError("Only cache hits expected")):
            second = v.e()
        self.assertEqual(v.calls, [0, 1])
        self.assertEqual(v.alias_calls, [0, 1])
        self.assertEqual((first["predecessor"], second["predecessor"]), ("1", "2"))
        self.assertEqual(second["descriptor_predecessor"], "2")
        self.assertEqual(
            second[str(Path(s.__file__).resolve())], digest(Path(s.__file__).read_bytes())
        )
        self.proof["producer_pins"] = second

    def test_multi_verifiers_reject_same_path_size_mtime_native_drift_after_hit(self):
        v = self.setup_multi_verifiers()
        v.e()
        raw, stat = v.cells.read_bytes(), v.cells.stat()
        v.cells.write_bytes(raw.replace(b"return self.mesh", b"return self.copy"))
        os.utime(v.cells, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(v.cells.stat().st_size, len(raw))
        with self.assertRaisesRegex(ValueError, "Original multi-cell source changed"):
            v.e()
        self.assertEqual(v.calls, [0, 1])

    def test_multi_verifiers_keep_full_definition_and_body_only_scopes_distinct(self):
        v = self.setup_multi_verifiers()
        v.e()
        path = Path(v.source.__file__)
        original = path.read_bytes()
        for changed in (
            original.replace(b"-> int", b"-> str"),
            original.replace(b"mask=None", b"mask=True"),
            original.replace(b"    def cell_index", b"    @marker\n    def cell_index"),
        ):
            path.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "signature/body"):
                v.c()
        path.write_bytes(original)
        env = Path(v.env_source.__file__)
        original = env.read_bytes()
        env.write_bytes(original.replace(b"environment(self, p)", b"environment(self, p=None)"))
        pins = v.e()  # The existing environment check compares bodies only.
        self.assertEqual(pins[str(env.resolve())], digest(env.read_bytes()))
        env.write_bytes(
            original.replace(b"self.environment_done = 1", b"self.environment_done = 2")
        )
        with self.assertRaisesRegex(ValueError, "Literal ordinary multi-cell body changed"):
            v.e()

    def test_multi_verifiers_keep_projection_and_grid_assignment_refusals(self):
        v = self.setup_multi_verifiers()
        v.e()
        path = Path(v.source.__file__)
        original = path.read_bytes()
        path.write_bytes(original.replace(b"self.wsx = 1", b"self.wsx = 2"))
        with self.assertRaisesRegex(ValueError, "source projection changed"):
            v.c()
        path.write_bytes(original)
        env = Path(v.env_source.__file__)
        original = env.read_bytes()
        for changed in (
            original.replace(b"self.grid_len =", b"self.wrong ="),
            original.replace(b"len(self.cell_i)", b"len(self.cell_i) + 1"),
        ):
            env.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "grid_len assignment"):
                v.e()

    def test_multi_owned_classes_keep_last_definition_and_missing_method_refusal(self):
        v = self.setup_multi_verifiers()
        path = Path(v.source.__file__)
        original = path.read_bytes()
        classes = {
            node.name: ast.get_source_segment(original.decode(), node).encode() + b"\n"
            for node in ast.parse(original).body
            if isinstance(node, ast.ClassDef)
        }
        changes = {
            "ParameterStores": (b"self.wsx = 1", b"self.wsx = 9"),
            "CellsMulti": (b"return self.mesh", b"return self.copy"),
            "MeshPipeline": (b"return mask", b"return None"),
        }
        for name, (before, after) in changes.items():
            bad = classes[name].replace(before, after)
            self.assertNotEqual(bad, classes[name])
            path.write_bytes(original + b"\n" + bad)
            with self.assertRaisesRegex(ValueError, "source projection|signature/body"):
                v.c()
            path.write_bytes(bad + b"\n" + original)
            pins = v.c()
            self.assertEqual(pins[str(path.resolve())], digest(path.read_bytes()))
            path.write_bytes(original + f"\nclass {name}:\n    pass\n".encode())
            with self.assertRaises(StopIteration):
                v.c()
        self.proof["last_owned_classes"] = list(changes)

    def test_multi_verifiers_hash_the_same_owned_bytes_used_for_parsing(self):
        v = self.setup_multi_verifiers()
        path = Path(v.ecm_source.__file__)
        original, read_bytes, reads = path.read_bytes(), Path.read_bytes, []

        def changing_read(p):
            if p == path:
                reads.append(p)
                return original if len(reads) == 1 else original + b"# changed on second read\n"
            return read_bytes(p)

        with patch.object(Path, "read_bytes", changing_read):
            pins = v.e()
        self.assertEqual(reads, [path])
        self.assertEqual(pins[str(path.resolve())], digest(original))

    def test_multi_predecessor_failure_and_missing_source_are_not_cached(self):
        v = self.setup_multi_verifiers()
        v.e()
        primary = LookupError("source predecessor refused")
        with patch.object(v.caller_ns["images"], "_verify_sources", side_effect=primary):
            with self.assertRaises(LookupError) as caught:
                v.e()
        self.assertIs(caught.exception, primary)
        Path(v.env_source.__file__).unlink()
        with self.assertRaises(FileNotFoundError):
            v.e()


def main():
    """Saved stdlib checks, under the existing external resource guard."""
    from validation.betse import betse_normal_channel_join_runtime as runtime

    output = Path(os.environ["CELLS_SOURCE_STRUCTURE_EVIDENCE"])
    attempts, rows = [], []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"betse", "numpy", "scipy", "PIL", "jax"}:
                attempts.append(fullname)
                raise AssertionError("Scientific import forbidden")

    class Result(unittest.TextTestResult):
        def record(self, test, outcome, err=None):
            row = dict(id=test.id(), outcome=outcome, proof=test.proof)
            if err is not None:
                row["traceback"] = self._exc_info_to_string(err, test)
            rows.append(row)

        def addSuccess(self, test):
            super().addSuccess(test)
            self.record(test, "passed")

        def addFailure(self, test, err):
            super().addFailure(test, err)
            self.record(test, "failed", err)

        def addError(self, test, err):
            super().addError(test, err)
            self.record(test, "error", err)

    blocker = Block()
    previous, trace = sys.getprofile(), sys.gettrace()

    def guard(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and "/betse/science/" in frame.f_code.co_filename:
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Native source execution forbidden")

    sys.meta_path.insert(0, blocker)
    sys.setprofile(guard)
    try:
        result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(StructureTests)
        )
    finally:
        sys.setprofile(previous)
        sys.meta_path.remove(blocker)
        (output / "case-results.json").write_text(json.dumps(rows, indent=2) + "\n")
        (output / "native-entry-guard.json").write_text(
            json.dumps(
                dict(
                    attempted=attempts,
                    trace_preserved=sys.gettrace() is trace,
                    profile_restored=sys.getprofile() is previous,
                )
            )
            + "\n"
        )
        (output / "runtime-producers.json").write_text(
            json.dumps(runtime.inventory(), indent=2) + "\n"
        )
    return int(not result.wasSuccessful() or bool(attempts) or sys.gettrace() is not trace)


if __name__ == "__main__":
    raise SystemExit(main())
