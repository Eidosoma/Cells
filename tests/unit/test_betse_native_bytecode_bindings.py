"""Stdlib-only extracted metadata tests; no production/native package import."""

import ast
import builtins
import dis
import hashlib
import importlib.abc
import json
import os
import statistics
import sys
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "src/cells/processes/betse_native_bytecode_bindings.py"
CALLER = ROOT / "src/cells/processes/betse_native_parameter_yaml_prefix.py"
ATOMS = ROOT / "src/cells/processes/betse_native_single_cell_grid_alias.py"


class NoScientificImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax"}:
            raise ImportError("Only extracted stdlib metadata permitted: " + fullname)
        return None


def helper_namespace(*, fallback=False):
    tree = ast.parse(HELPER.read_bytes(), str(HELPER))
    if fallback:
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "_FAST" for target in node.targets
            ):
                node.value = ast.Constant(False)
    namespace = {"__name__": "isolated_bytecode_metadata", "__file__": str(HELPER)}
    exec(compile(ast.fix_missing_locations(tree), str(HELPER), "exec"), namespace)
    return types.SimpleNamespace(**namespace)


def function(source, name="sample", namespace=None):
    namespace = {"__builtins__": dict(vars(builtins))} if namespace is None else namespace
    code = compile(source, "<isolated-bytecode-input>", "exec")
    selected = next(
        item for item in code.co_consts if type(item) is types.CodeType and item.co_name == name
    )
    return types.FunctionType(selected, namespace)


def oracle(code):
    return tuple(
        (instruction.opname, instruction.argval)
        for instruction in dis.get_instructions(code)
        if instruction.opname in ("LOAD_GLOBAL", "IMPORT_NAME")
    )


def callable_atoms():
    tree = ast.parse(ATOMS.read_bytes(), str(ATOMS))
    node = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_atoms"
    )
    namespace = {"FunctionType": types.FunctionType, "MethodType": types.MethodType}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ATOMS), "exec"), namespace)
    return namespace["_atoms"]


def caller_function(helper, *, bind_decoder=False):
    tree = ast.parse(CALLER.read_bytes(), str(CALLER))
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_function_bindings"
    )
    if bind_decoder:
        # Exercise the exact proposed one-default integration while Root owns
        # the real call-site edit. Once integrated this is already present.
        for item in ast.walk(node):
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and isinstance(item.func.value, ast.Name)
                and item.func.value.id == "bytecode_bindings"
                and item.func.attr == "lookup_names"
            ):
                item.func = ast.Name(id="_lookup_names", ctx=ast.Load())
        if "_lookup_names" not in [arg.arg for arg in node.args.args]:
            node.args.args.append(ast.arg(arg="_lookup_names"))
            node.args.defaults.append(
                ast.Attribute(
                    value=ast.Name(id="bytecode_bindings", ctx=ast.Load()),
                    attr="lookup_names",
                    ctx=ast.Load(),
                )
            )
    # Preserve the actual caller's live header/namespace resolution and use the
    # real callable-atom walker; neither production module is imported.
    namespace = {
        "FunctionType": types.FunctionType,
        "bytecode_bindings": helper,
        "parameters": types.SimpleNamespace(
            inherited=types.SimpleNamespace(
                tissue=types.SimpleNamespace(aliases=types.SimpleNamespace(_atoms=callable_atoms()))
            )
        ),
        "dis": types.SimpleNamespace(
            get_instructions=lambda value: (
                types.SimpleNamespace(opname=opname, argval=name)
                for opname, name in helper.lookup_names(value.__code__)
            )
        ),
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(CALLER), "exec"
        ),
        namespace,
    )
    return namespace["_function_bindings"]


class BytecodeBindingsTests(unittest.TestCase):
    def setUp(self):
        self.before_modules = set(sys.modules)
        self.blocker = NoScientificImports()
        sys.meta_path.insert(0, self.blocker)
        self.addCleanup(sys.meta_path.remove, self.blocker)
        self.addCleanup(self.check_modules)
        self.fast = helper_namespace()

    def check_modules(self):
        forbidden = {"cells", "betse", "numpy", "scipy", "jax"}
        self.assertFalse(
            [
                name
                for name in set(sys.modules) - self.before_modules
                if name.split(".")[0] in forbidden
            ]
        )

    def test_compact_and_fallback_equivalence(self):
        slow = helper_namespace(fallback=True)
        sources = (
            "def sample():\n return first + second + first\n",
            "def sample(value):\n return len(value) + helper(value) + len(value)\n",
            (
                "def sample():\n import math\n from collections import deque\n"
                " return math, deque, external\n"
            ),
            (
                "def sample(value):\n try:\n  return len(value.attr())\n"
                " except Exception:\n  return fallback\n"
            ),
            "def sample(value):\n yield from converter(value)\n return final\n",
            "async def sample(value):\n await consumer(value)\n return final\n",
            "def sample():\n return 3\n",
        )
        for source in sources:
            with self.subTest(source=source):
                code = function(source).__code__
                self.assertEqual(self.fast.lookup_names(code), oracle(code))
                self.assertEqual(slow.lookup_names(code), oracle(code))

    def test_extended_arguments_and_inline_caches(self):
        names = ["global_" + str(index) for index in range(600)]
        code = function("def sample():\n return (" + ",".join(names) + ")\n").__code__
        self.assertTrue(any(item.opname == "EXTENDED_ARG" for item in dis.get_instructions(code)))
        self.assertEqual(
            self.fast.lookup_names(code), tuple(("LOAD_GLOBAL", name) for name in names)
        )
        imports = "def sample():\n" + "".join(
            " import module_" + str(index) + "\n" for index in range(300)
        )
        code = function(imports).__code__
        self.assertEqual(self.fast.lookup_names(code), oracle(code))

    def test_nested_code_objects_are_decoded_independently(self):
        outer = function(
            "def sample():\n def inner():\n  return nested + nested\n return outside, inner\n"
        ).__code__
        inner = next(item for item in outer.co_consts if type(item) is types.CodeType)
        self.assertEqual(self.fast.lookup_names(outer), (("LOAD_GLOBAL", "outside"),))
        self.assertEqual(self.fast.lookup_names(inner), (("LOAD_GLOBAL", "nested"),) * 2)

    def test_repeated_calls_preserve_duplicate_order_and_no_plan_cache(self):
        selected = function("def sample():\n return left, right, left\n")
        before = self.fast.lookup_names(selected.__code__)
        changed = selected.__code__.replace(co_names=("new_left", "new_right"))
        self.assertEqual(
            self.fast.lookup_names(changed),
            (
                ("LOAD_GLOBAL", "new_left"),
                ("LOAD_GLOBAL", "new_right"),
                ("LOAD_GLOBAL", "new_left"),
            ),
        )
        self.assertEqual(self.fast.lookup_names(selected.__code__), before)

    def test_real_caller_resolves_current_globals_builtins_defaults_and_code(self):
        caller = caller_function(self.fast)
        selected = function("def sample(value=None):\n return len(value), live, len(value)\n")
        selected.__globals__["live"] = object()
        before = caller(selected)
        selected.__globals__["live"] = object()
        self.assertIsNot(caller(selected)[1][-2], before[1][-2])
        selected.__globals__["len"] = selected.__builtins__["len"]
        self.assertNotEqual(caller(selected)[0], before[0])
        del selected.__globals__["len"]
        selected.__defaults__ = (object(),)
        self.assertIs(caller(selected)[1][4], selected.__defaults__)
        selected.__code__ = selected.__code__.replace(co_filename="<equal-metadata-new-code>")
        self.assertIs(caller(selected)[1][1], selected.__code__)
        self.assertIsNot(caller(selected)[1][1], before[1][1])
        selected.__builtins__["len"] = object()
        self.assertIs(caller(selected)[1][-1], selected.__builtins__["len"])

    def test_real_caller_retains_missing_global_failure(self):
        selected = function("def sample():\n return missing\n")
        with self.assertRaisesRegex(KeyError, "missing"):
            caller_function(self.fast)(selected)

    def test_runtime_callable_equal_code_and_table_drift_refuse(self):
        selected = function("def sample():\n return original\n").__code__
        original = dis._unpack_opargs
        clone = types.FunctionType(original.__code__, original.__globals__)
        with patch.object(dis, "_unpack_opargs", clone), self.assertRaises(ValueError):
            self.fast.lookup_names(selected)
        saved_code = original.__code__
        try:
            original.__code__ = saved_code.replace(co_filename="<replacement-decoder>")
            with self.assertRaises(ValueError):
                self.fast.lookup_names(selected)
        finally:
            original.__code__ = saved_code
        for name in ("_all_opmap", "deoptmap", "_inline_cache_entries"):
            table = getattr(dis, name)
            key = next(iter(table))
            with patch.dict(table, {key: object()}), self.assertRaises(ValueError):
                self.fast.lookup_names(selected)
        with patch.object(dis, "hasarg", list(dis.hasarg)), self.assertRaises(ValueError):
            self.fast.lookup_names(selected)

    def test_same_function_resolved_helper_and_builtin_shadow_refuse(self):
        selected = function("def sample():\n return original\n").__code__
        with patch.object(dis, "_get_cache_size", lambda name: 0), self.assertRaises(ValueError):
            self.fast.lookup_names(selected)
        with patch.dict(vars(dis), {"len": len}), self.assertRaises(ValueError):
            self.fast.lookup_names(selected)

    def test_private_decoder_alias_retarget_refuses_before_delegate(self):
        selected = function("def sample():\n return original\n").__code__
        namespace = self.fast.lookup_names.__globals__
        calls = []

        def substitute(code):
            calls.append(code)
            return iter(())

        with patch.dict(namespace, {"_UNPACK": substitute}), self.assertRaises(ValueError):
            self.fast.lookup_names(selected)
        with (
            patch.dict(namespace, {"_FALLBACK": substitute}),
            patch.object(dis, "get_instructions", substitute),
            self.assertRaises(ValueError),
        ):
            self.fast.lookup_names(selected)
        self.assertFalse(calls)

    def test_observer_decoder_mutation_before_publication_refuses(self):
        selected = function("def sample():\n return original\n").__code__
        original = dis._deoptop
        before = sys.getprofile()
        fired = []

        def profile(frame, event, value):
            if before is not None:
                before(frame, event, value)
            if event == "return" and frame.f_code is dis._unpack_opargs.__code__ and not fired:
                fired.append(True)
                dis._deoptop = lambda op: op

        try:
            sys.setprofile(profile)
            with self.assertRaises(ValueError):
                self.fast.lookup_names(selected)
        finally:
            dis._deoptop = original
            sys.setprofile(before)
        self.assertEqual(fired, [True])
        self.assertIs(sys.getprofile(), before)

    def test_exact_code_input_and_runtime_binding_surface(self):
        with self.assertRaises(TypeError):
            self.fast.lookup_names(function("def sample():\n return 1\n"))
        labels, refs = self.fast.runtime_bindings()
        self.assertEqual(labels[0], (sys.implementation.name, tuple(sys.version_info[:2])))
        self.assertTrue(any(item is dis._unpack_opargs for item in refs))
        self.assertTrue(any(item is self.fast.lookup_names.__code__ for item in refs))

    def test_runtime_binding_atoms_stay_identical_without_mutation(self):
        before, first = self.fast.runtime_bindings()
        after, second = self.fast.runtime_bindings()
        self.assertEqual(before, after)
        self.assertEqual(len(first), len(second))
        self.assertTrue(all(left is right for left, right in zip(first, second, strict=True)))

    def test_retired_caller_atoms_reach_bound_decoder_authentication_and_checker(self):
        caller = caller_function(self.fast, bind_decoder=True)
        atoms = callable_atoms()(caller)
        for function in (
            self.fast.lookup_names,
            self.fast._authenticate,
            self.fast._check_function,
            dis._unpack_opargs,
            dis.get_instructions,
        ):
            with self.subTest(function=function.__name__):
                self.assertTrue(any(atom is function for atom in atoms))
                self.assertTrue(any(atom is function.__code__ for atom in atoms))
        self.assertTrue(any(atom is self.fast._AUTHORITY for atom in atoms))
        self.assertEqual(caller.__defaults__, (self.fast.lookup_names,))

    def test_retired_caller_keeps_bound_helpers_when_unused_module_aliases_change(self):
        caller = caller_function(self.fast, bind_decoder=True)
        selected = function(
            "def sample():\n return (" + ",".join("name_" + str(i) for i in range(100)) + ")\n"
        )
        selected.__globals__.update({name: object() for name in selected.__code__.co_names})
        atoms = callable_atoms()
        retained = atoms(caller)
        before = caller(selected)
        calls = []

        def replacement(*args):
            calls.append(args)
            raise AssertionError("An unretained module alias must never be called")

        with (
            patch.object(self.fast, "lookup_names", replacement),
            patch.dict(
                self.fast._authenticate.__globals__,
                {"_authenticate": replacement, "_check_function": replacement},
            ),
        ):
            current = atoms(caller)
            self.assertEqual(len(current), len(retained))
            self.assertTrue(all(a is b for a, b in zip(current, retained, strict=True)))
            after = caller(selected)
        self.assertEqual(before[0], after[0])
        self.assertTrue(all(a is b for a, b in zip(before[1], after[1], strict=True)))
        self.assertFalse(calls)

    def test_retired_caller_atoms_detect_bound_function_code_changes(self):
        caller = caller_function(self.fast, bind_decoder=True)
        atoms = callable_atoms()
        for function in (
            self.fast.lookup_names,
            self.fast._authenticate,
            self.fast._check_function,
            dis._unpack_opargs,
            dis.get_instructions,
        ):
            with self.subTest(function=function.__name__):
                retained, code = atoms(caller), function.__code__
                try:
                    function.__code__ = code.replace(co_filename="<retargeted-binding-code>")
                    current = atoms(caller)
                    self.assertEqual(len(current), len(retained))
                    self.assertTrue(any(a is not b for a, b in zip(current, retained, strict=True)))
                    self.assertTrue(any(atom is function.__code__ for atom in current))
                finally:
                    function.__code__ = code

    def test_retired_caller_atoms_detect_equal_code_default_retargets(self):
        caller = caller_function(self.fast, bind_decoder=True)
        atoms = callable_atoms()
        for owner in (caller, self.fast.lookup_names, self.fast._authenticate):
            with self.subTest(owner=owner.__name__):
                retained, defaults = atoms(caller), owner.__defaults__
                function = defaults[0]
                clone = types.FunctionType(
                    function.__code__,
                    function.__globals__,
                    function.__name__,
                    function.__defaults__,
                    function.__closure__,
                )
                try:
                    owner.__defaults__ = (clone, *defaults[1:])
                    current = atoms(caller)
                    self.assertTrue(any(atom is clone for atom in current))
                    self.assertFalse(
                        len(current) == len(retained)
                        and all(a is b for a, b in zip(current, retained, strict=True))
                    )
                finally:
                    owner.__defaults__ = defaults

    def test_bound_authentication_rejects_replaced_expected_roster_aliases(self):
        code = function("def sample():\n return original\n").__code__
        namespace = self.fast.lookup_names.__globals__
        for name in ("_FUNCTIONS", "_TABLES"):
            original = namespace[name]
            with patch.dict(namespace, {name: tuple(item for item in original)}):
                with self.assertRaises(ValueError):
                    self.fast.lookup_names(code)

    def test_bound_authentication_retains_inner_stdlib_helper_code_checks(self):
        caller = caller_function(self.fast, bind_decoder=True)
        atoms = callable_atoms()
        retained = atoms(caller)
        original = dis._deoptop.__code__
        try:
            dis._deoptop.__code__ = original.replace(co_filename="<inner-decoder-drift>")
            self.assertTrue(all(a is b for a, b in zip(atoms(caller), retained, strict=True)))
            with self.assertRaises(ValueError):
                self.fast.lookup_names(function("def sample():\n return original\n").__code__)
        finally:
            dis._deoptop.__code__ = original


def benchmark(iterations=400):
    """Synthetic decoding only; never invoke any selected caller/native body."""
    fast = helper_namespace()
    rows = []
    for size in (10, 100, 600):
        code = function(
            "def sample():\n return (" + ",".join("name_" + str(i) for i in range(size)) + ")\n"
        ).__code__
        expected = oracle(code)
        assert fast.lookup_names(code) == expected
        timings = {"oracle": [], "compact": []}
        for _ in range(5):
            for label, operation in (("oracle", oracle), ("compact", fast.lookup_names)):
                started = time.perf_counter()
                for _ in range(iterations):
                    operation(code)
                timings[label].append(time.perf_counter() - started)
        old, new = (statistics.median(timings[label]) for label in ("oracle", "compact"))
        rows.append(
            dict(
                global_lookups=size,
                iterations=iterations,
                seconds=timings,
                median_speed_ratio=old / new,
            )
        )
    return dict(synthetic_only=True, fast_runtime=fast._FAST, measurements=rows)


def source_metadata_benchmark(root, expected_pins, iterations=100):
    """Compile source for its code metadata; execute none of its definitions."""
    fast = helper_namespace()
    selected = (
        (root / "betse/science/phase/phasecallbacks.py", "make_default"),
        (root / "betse/util/type/call/callbacks.py", "CallbacksBC.__init__"),
        (root / "betse/util/type/call/callbacks.py", "CallbacksBC._clear_progress"),
        (root / "betse/util/test/tsttest.py", "is_testing"),
        (root / "betse/science/parameters.py", "Parameters.load"),
        (CALLER, "_function_bindings"),
        (CALLER, "_bindings"),
    )
    source_pins, rows = {}, []
    for path, qualname in selected:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        source_pins[str(path)] = digest
        if path != CALLER and expected_pins.get(str(path)) != digest:
            raise ValueError("Explicit compile-only source metadata pin required")
        pending, found = [compile(raw, str(path), "exec")], []
        while pending:
            code = pending.pop()
            if code.co_qualname == qualname:
                found.append(code)
            pending.extend(item for item in code.co_consts if type(item) is types.CodeType)
        if len(found) != 1:
            raise ValueError("One original code-metadata definition required: " + qualname)
        code = found[0]
        expected = oracle(code)
        if fast.lookup_names(code) != expected:
            raise AssertionError("Original source lookup metadata differs")
        timings = {"oracle": [], "compact": []}
        for _ in range(3):
            for label, operation in (("oracle", oracle), ("compact", fast.lookup_names)):
                started = time.perf_counter()
                for _ in range(iterations):
                    operation(code)
                timings[label].append(time.perf_counter() - started)
        old, new = (statistics.median(timings[label]) for label in ("oracle", "compact"))
        rows.append(
            dict(
                source=str(path),
                qualname=qualname,
                code_bytes=len(code.co_code),
                lookup_count=len(expected),
                iterations=iterations,
                seconds=timings,
                median_speed_ratio=old / new,
            )
        )
    return dict(
        source_metadata_only=True,
        original_body_calls=0,
        source_pins=source_pins,
        measurements=rows,
    )


if __name__ == "__main__":
    outer_import_blocker = NoScientificImports()
    sys.meta_path.insert(0, outer_import_blocker)
    initial_hooks = sys.getprofile(), sys.gettrace()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(BytecodeBindingsTests)
    )
    if folder := os.environ.get("CELLS_BYTECODE_BENCHMARK_OUTPUT"):
        target = Path(folder)
        with (target / "tests.json").open("x") as stream:
            json.dump(
                dict(
                    tests_run=result.testsRun,
                    passed=result.wasSuccessful(),
                    failures=[(test.id(), error) for test, error in result.failures],
                    errors=[(test.id(), error) for test, error in result.errors],
                    skipped=result.skipped,
                    exact_profile_restored=sys.getprofile() is initial_hooks[0],
                    exact_trace_restored=sys.gettrace() is initial_hooks[1],
                    forbidden_modules=[
                        name
                        for name in sys.modules
                        if name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax"}
                    ],
                    source_or_scientific_execution=0,
                ),
                stream,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
        with (target / "source-pins.json").open("x") as stream:
            json.dump(
                {
                    str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (HELPER, CALLER, ATOMS, Path(__file__).resolve())
                },
                stream,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
        if result.wasSuccessful():
            with (target / "benchmark.json").open("x") as stream:
                json.dump(benchmark(), stream, indent=2, sort_keys=True)
                stream.write("\n")
            if native := os.environ.get("CELLS_BYTECODE_NATIVE_METADATA_ROOT"):
                pins = json.loads(os.environ["CELLS_BYTECODE_EXTERNAL_PINS"])
                with (target / "source-metadata-benchmark.json").open("x") as stream:
                    json.dump(
                        source_metadata_benchmark(Path(native), pins),
                        stream,
                        indent=2,
                        sort_keys=True,
                    )
                    stream.write("\n")
    sys.meta_path.remove(outer_import_blocker)
    raise SystemExit(0 if result.wasSuccessful() else 1)
