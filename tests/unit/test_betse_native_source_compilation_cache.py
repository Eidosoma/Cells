"""Actual extracted metadata helpers only; no production import or source body."""

import ast
import builtins
import copy
import dis
import functools
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import CodeType, FunctionType, ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
PARAMETERS = "src/cells/processes/betse_native_phase_parameters.py"
COLORMAPS = "src/cells/processes/betse_native_parameter_colormaps.py"
PARAMETER_FUNCTIONS = (
    "_compilation_function_record",
    "_compilation_validate",
    "_compilation_key",
    "_compilation_metadata",
    "_compilation_contract",
    "_compiled_source",
    "_method_code",
    "_compilation_record_anchor",
)
COLORMAP_FUNCTIONS = ("_context_code", "_compiler_contract", "_context_record_anchor")
SAMPLE = (
    b"from __future__ import annotations\n"
    b"import unavailable_module\n"
    b"@unavailable_decorator\n"
    b"class Example:\n"
    b"    def first(self, value: Missing = unavailable_default()):\n"
    b"        assert value\n"
    b"        return super().first(value), __class__\n"
    b"    def second(self):\n"
    b"        def nested():\n"
    b"            return __class__\n"
    b"        return nested\n"
)


def _load(path, functions, prefix, *, parameters=None):
    raw = path.read_bytes()
    tree = ast.parse(raw)
    selected = []
    for node in tree.body:
        if type(node) is ast.FunctionDef and node.name in functions:
            selected.append(node)
        elif type(node) is ast.Assign and all(
            type(target) is ast.Name and target.id.startswith(prefix) for target in node.targets
        ):
            selected.append(node)
        elif type(node) is ast.Assign and prefix == "_CONTEXT_":
            # The three preexisting bounds share one tuple assignment.
            if any(
                type(target) is ast.Tuple
                and all(
                    type(name) is ast.Name and name.id.startswith(prefix) for name in target.elts
                )
                for target in node.targets
            ):
                selected.append(node)
    assert {node.name for node in selected if type(node) is ast.FunctionDef} == set(functions)
    module = ModuleType("source_compilation_metadata_" + prefix.strip("_").lower())
    module.__file__ = str(path)
    module.__dict__.update(
        __builtins__=vars(builtins),
        ast=ast,
        builtins=builtins,
        copy=copy,
        dis=dis,
        lru_cache=functools.lru_cache,
        Path=Path,
        CodeType=CodeType,
        FunctionType=FunctionType,
        ModuleType=ModuleType,
    )
    if parameters is not None:
        module.prefix = SimpleNamespace(parameters=parameters)
    exec(
        compile(
            ast.Module(body=selected, type_ignores=[]),
            "<extracted-source-compilation-metadata>",
            "exec",
            dont_inherit=True,
        ),
        vars(module),
    )
    return module, hashlib.sha256(raw).hexdigest()


def _same(actual, expected):
    assert actual[0] == expected[0]
    if len(actual[1]) != len(expected[1]) or any(
        value is not old for value, old in zip(actual[1], expected[1], strict=True)
    ):
        raise ValueError("Retained compiler binding changed")


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    old, trace, original_import = sys.getprofile(), sys.gettrace(), builtins.__import__
    attempts, protected, primary = [], set(), None

    def profile(frame, event, arg):
        name = frame.f_globals.get("__name__", "")
        filename = frame.f_code.co_filename
        if event == "call" and (
            name == "cells"
            or name.startswith(("cells.", "betse.", "numpy.", "scipy."))
            or filename in protected
            or "/src/cells/" in filename
        ):
            attempts.append((name, frame.f_code.co_qualname, filename))
            raise AssertionError("Native, owner, or compiled source execution forbidden")
        if old is not None:
            old(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name.split(".")[0] in ("cells", "betse", "numpy", "scipy", "matplotlib"):
            attempts.append((name, "import", ""))
            raise AssertionError("Scientific or production import forbidden")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", imports)
    sys.setprofile(profile)
    try:
        yield protected
        assert attempts == []
        assert sys.getprofile() is profile and sys.gettrace() is trace
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup = []
        try:
            sys.setprofile(old)
        except BaseException as error:
            cleanup.append(error)
        try:
            sys.settrace(trace)
        except BaseException as error:
            cleanup.append(error)
        if sys.getprofile() is old and sys.gettrace() is trace:
            try:
                (tmp_path / "native-blocked.json").write_text(
                    json.dumps(
                        dict(
                            nodeid=request.node.nodeid,
                            attempts=attempts,
                            compiled_source_entries=0,
                            hooks_restored=True,
                        )
                    )
                )
            except BaseException as error:
                cleanup.append(error)
        if primary is None and cleanup:
            raise cleanup[0]


@pytest.fixture
def metadata(tmp_path, blocked):
    parameters, parameter_sha = _load(ROOT / PARAMETERS, PARAMETER_FUNCTIONS, "_COMPILATION_")
    parameters.inherited = SimpleNamespace(_same=_same)
    colormaps, colormap_sha = _load(
        ROOT / COLORMAPS, COLORMAP_FUNCTIONS, "_CONTEXT_", parameters=parameters
    )
    (tmp_path / "metadata-producers.json").write_text(
        json.dumps(
            dict(
                files={PARAMETERS: parameter_sha, COLORMAPS: colormap_sha},
                selected_functions={PARAMETERS: PARAMETER_FUNCTIONS, COLORMAPS: COLORMAP_FUNCTIONS},
                source_bodies_executed=0,
                production_modules_imported=0,
            )
        )
    )
    return SimpleNamespace(parameters=parameters, colormaps=colormaps, paths=blocked)


def _source(metadata, tmp_path, raw=SAMPLE, name="compiler_input.py"):
    path = tmp_path / name
    path.write_bytes(raw)
    metadata.paths.add(str(path))
    return path, ast.parse(raw, filename=str(path))


def _body(code, qualified):
    pending, found = [code], []
    while pending:
        current = pending.pop()
        if current.co_qualname == qualified:
            found.append(current)
        pending.extend(value for value in current.co_consts if type(value) is CodeType)
    assert len(found) == 1
    return found[0]


@contextmanager
def _compiler_calls(parameters):
    old, calls = sys.getprofile(), []
    code, compiler = parameters._COMPILATION_BODY.__code__, builtins.compile

    def observe(frame, event, arg):
        if event == "c_call" and arg is compiler and frame.f_code is code:
            calls.append((frame.f_locals["filename"], frame.f_locals["optimize"]))
        if old is not None:
            old(frame, event, arg)

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(old)


def test_compilation_cache_reuses_full_context_without_executing_source(metadata, tmp_path):
    p, c = metadata.parameters, metadata.colormaps
    path, tree = _source(metadata, tmp_path)
    cls = tree.body[-1]
    expected = compile(SAMPLE, str(path), "exec", dont_inherit=True)
    with _compiler_calls(p) as calls:
        first = p._method_code(cls, "first", str(path), native_context=True)
        second = p._method_code(copy.deepcopy(cls), "second", str(path), native_context=True)
        assert p._method_code(cls, "first", str(path), native_context=True) is first
        contextual = c._context_code(cls.body[0], str(path))
        assert c._context_code(copy.deepcopy(cls.body[0]), str(path)) is contextual
    assert calls == [(str(path), -1), (str(path), 0)]
    assert first == _body(expected, "Example.first")
    assert second == _body(expected, "Example.second")
    assert first.co_freevars == ("__class__",) and first.co_firstlineno == 5
    assert first.co_flags & __import__("__future__").annotations.compiler_flag
    assert contextual == first
    assert p._compilation_metadata.cache_info().hits == 3


@pytest.mark.parametrize("change", ("bytes", "filename", "optimization"))
def test_compilation_cache_keys_every_compiler_input(metadata, change):
    p = metadata.parameters
    raw, filename, optimize = SAMPLE, "<compiler-input>", 0
    before = p._compiled_source(raw, filename, optimize=optimize)
    if change == "bytes":
        raw += b"# distinct immutable bytes\n"
    elif change == "filename":
        filename = "<other-compiler-input>"
    else:
        optimize = 1
    after = p._compiled_source(raw, filename, optimize=optimize)
    assert before is not after
    assert p._compilation_metadata.cache_info().misses == 2
    assert after[0] == compile(raw, filename, "exec", dont_inherit=True, optimize=optimize)


def test_compilation_cache_preserves_method_filename_spelling(metadata, tmp_path):
    p = metadata.parameters
    path, tree = _source(metadata, tmp_path)
    spelling = str(tmp_path) + "/./" + path.name
    metadata.paths.add(spelling)
    first = p._method_code(tree.body[-1], "first", str(path), native_context=True)
    second = p._method_code(tree.body[-1], "first", spelling, native_context=True)
    assert first.co_filename == str(path) and second.co_filename == spelling
    assert first is not second and p._compilation_metadata.cache_info().misses == 2
    # The existing colormap function deliberately canonicalizes through Path.
    c = metadata.colormaps
    assert c._context_code(tree.body[-1].body[0], spelling).co_filename == str(path)


def test_compilation_cache_rereads_same_size_mtime_and_does_not_retain_ast(metadata, tmp_path):
    p = metadata.parameters
    raw = b"class Example:\n    def first(self):\n        return 1\n"
    path, tree = _source(metadata, tmp_path, raw)
    stamp = path.stat().st_mtime_ns
    before = p._method_code(tree.body[0], "first", str(path), native_context=True)
    path.write_bytes(raw.replace(b"return 1", b"return 2"))
    os.utime(path, ns=(stamp, stamp))
    with pytest.raises(ValueError, match="Exact original class AST"):
        p._method_code(tree.body[0], "first", str(path), native_context=True)
    node = ast.parse(path.read_bytes()).body[0]
    after = p._method_code(node, "first", str(path), native_context=True)
    assert before.co_consts != after.co_consts and path.stat().st_mtime_ns == stamp
    assert p._compilation_metadata.cache_info().currsize == 2


@pytest.mark.parametrize("route", ("method", "context"))
@pytest.mark.parametrize("change", ("body", "line", "column", "decorator"))
def test_compilation_cache_hit_still_checks_mutable_caller_ast(metadata, tmp_path, route, change):
    path, tree = _source(metadata, tmp_path)
    cls = tree.body[-1]
    node = cls if route == "method" else cls.body[0]

    def call():
        if route == "method":
            return metadata.parameters._method_code(node, "first", str(path), native_context=True)
        return metadata.colormaps._context_code(node, str(path))

    call()
    if change == "body":
        node.body.pop()
    elif change == "line":
        node.lineno += 1
    elif change == "column":
        node.col_offset += 1
    else:
        node.decorator_list.append(ast.Name(id="foreign", ctx=ast.Load(), lineno=1, col_offset=0))
    with pytest.raises(ValueError, match="original class AST|declared function/source span"):
        call()


@pytest.mark.parametrize("warm", (False, True))
@pytest.mark.parametrize(
    "change",
    (
        "compiler",
        "same_compiler_shadow",
        "cached_builtins",
        "cache_wrapper",
        "cache_delegate",
        "equal_body_code",
        "body_defaults",
        "helper_function",
        "equal_helper_code",
        "helper_globals",
        "keywords",
        "keyword_key",
        "ast_parser",
        "guard",
        "guard_code",
        "validator",
    ),
)
def test_compilation_cache_rejects_live_dispatch_drift(metadata, monkeypatch, warm, change):
    p, entries = metadata.parameters, []
    if warm:
        p._compiled_source(SAMPLE, "<compiler-input>", optimize=0)
    before = p._compilation_metadata.cache_info()

    def foreign(*args, **kwargs):
        entries.append(change)
        raise AssertionError("Unowned compiler or metadata helper entered")

    caught = None
    with monkeypatch.context() as patch:
        if change == "compiler":
            patch.setattr(builtins, "compile", foreign)
        elif change == "same_compiler_shadow":
            patch.setattr(p, "compile", builtins.compile, raising=False)
        elif change == "cached_builtins":
            patch.setitem(vars(p), "__builtins__", dict(vars(builtins)))
        elif change == "cache_wrapper":
            patch.setattr(p, "_compilation_metadata", foreign)
        elif change == "cache_delegate":
            patch.setattr(p._compilation_metadata, "__wrapped__", foreign)
        elif change == "equal_body_code":
            patch.setattr(p._COMPILATION_BODY, "__code__", p._COMPILATION_BODY.__code__.replace())
        elif change == "body_defaults":
            patch.setattr(p._COMPILATION_BODY, "__defaults__", (0,))
        elif change == "helper_function":
            patch.setattr(p, "_compilation_key", foreign)
        elif change == "equal_helper_code":
            patch.setattr(p._compilation_key, "__code__", p._compilation_key.__code__.replace())
        elif change == "helper_globals":
            original = p._compilation_key
            patch.setattr(p, "_compilation_key", FunctionType(original.__code__, dict(vars(p))))
        elif change == "keywords":
            patch.setattr(
                p._compiled_source, "__kwdefaults__", dict(p._compiled_source.__kwdefaults__)
            )
        elif change == "keyword_key":
            keywords = p._compiled_source.__kwdefaults__
            key = next(iter(keywords))
            other = "".join(("opti", "mize"))
            assert key == other and key is not other
            patch.delitem(keywords, key)
            patch.setitem(keywords, other, -1)
        elif change == "ast_parser":
            patch.setattr(ast, "parse", foreign)
        elif change == "guard":
            patch.setattr(p, "_compilation_contract", foreign)
        elif change == "guard_code":
            original = p._compilation_contract
            patch.setattr(original, "__code__", original.__code__.replace())
        else:
            patch.setattr(p, "_compilation_validate", foreign)
        try:
            p._compiled_source(SAMPLE, "<compiler-input>", optimize=0)
        except BaseException as error:
            caught = error
    assert type(caught) is ValueError and entries == []
    assert p._compilation_metadata.cache_info() == before
    p._compilation_contract()


@pytest.mark.parametrize("boundary", ("read", "compile_return", "cache_return"))
@pytest.mark.parametrize("change", ("compiler", "guard_code"))
def test_compilation_cache_rechecks_after_miss_and_use(
    metadata, tmp_path, monkeypatch, boundary, change
):
    p = metadata.parameters
    path, tree = _source(metadata, tmp_path)
    if boundary == "cache_return":
        p._method_code(tree.body[-1], "first", str(path), native_context=True)
    previous, seen, caught = sys.getprofile(), [], None

    def foreign(*args, **kwargs):
        raise AssertionError("Changed compiler must not execute")

    with monkeypatch.context() as patch:

        def observe(frame, event, arg):
            selected = (
                (
                    boundary == "read"
                    and event == "return"
                    and frame.f_code is Path.read_bytes.__code__
                )
                or (
                    boundary == "compile_return"
                    and event == "c_return"
                    and frame.f_code is p._COMPILATION_BODY.__code__
                    and arg is builtins.compile
                )
                or (
                    boundary == "cache_return"
                    and event == "return"
                    and frame.f_code is p._compiled_source.__code__
                )
            )
            if selected and not seen:
                seen.append(boundary)
                if change == "compiler":
                    patch.setattr(p, "compile", foreign, raising=False)
                else:
                    patch.setattr(p._compilation_contract, "__code__", foreign.__code__)
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(observe)
        try:
            p._method_code(tree.body[-1], "first", str(path), native_context=True)
        except BaseException as error:
            caught = error
        finally:
            sys.setprofile(previous)
    assert seen == [boundary] and type(caught) is ValueError
    p._compilation_contract()


def test_compilation_cache_ast_limit_refuses_before_module_compile(metadata):
    p = metadata.parameters
    with _compiler_calls(p) as calls:
        with pytest.raises(ValueError, match="Bounded compiler AST"):
            p._compiled_source(b"value = 0\n" * 25001, "<bounded-ast>", optimize=0)
    assert calls == [] and p._compilation_metadata.cache_info().currsize == 0


def test_compilation_cache_retains_inherited_guard_primary(metadata, tmp_path):
    p = metadata.parameters
    path, tree = _source(metadata, tmp_path)

    class Primary(BaseException):
        def __bool__(self):
            return False

    cause, primary = RuntimeError("original cause"), Primary("original guard")
    previous, caught = sys.getprofile(), None

    def observe(frame, event, arg):
        if event == "call" and frame.f_code is p._COMPILATION_BODY.__code__:
            raise primary from cause
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(observe)
    try:
        p._method_code(tree.body[-1], "first", str(path), native_context=True)
    except BaseException as error:
        caught = error
    finally:
        sys.setprofile(previous)
    assert caught is primary and caught.__cause__ is cause
    assert p._compilation_metadata.cache_info().currsize == 0


def test_compilation_cache_keeps_replacement_and_fragment_modes_exact(metadata, tmp_path):
    p, c = metadata.parameters, metadata.colormaps
    path, tree = _source(metadata, tmp_path)
    cls, method = tree.body[-1], tree.body[-1].body[0]
    c._context_code(method, str(path))
    before = p._compilation_metadata.cache_info()
    replacement = copy.deepcopy(method)
    replacement.body = [ast.copy_location(ast.Return(value=ast.Constant(value=17)), method.body[0])]
    ast.fix_missing_locations(replacement)
    expected_tree = copy.deepcopy(tree)
    expected_tree.body[-1].body[0] = replacement
    expected = compile(expected_tree, str(path), "exec", dont_inherit=True, optimize=0)
    assert c._context_code(method, str(path), replacement=replacement) == _body(
        expected, "Example.first"
    )
    fragment = compile(
        ast.Module(body=[cls], type_ignores=[]), str(path), "exec", dont_inherit=True
    )
    assert p._method_code(cls, "first", str(path)) == _body(fragment, "Example.first")
    assert p._compilation_metadata.cache_info() == before
    replacement.args.args[0].arg = "foreign"
    with pytest.raises(ValueError, match="header or scope"):
        c._context_code(method, str(path), replacement=replacement)


def test_compilation_cache_preserves_duplicate_and_nested_selection(metadata, tmp_path):
    raw = (
        b"class Example:\n    def first(self): return 1\n"
        b"class Example:\n    def first(self): return 2\n"
        b"def outer():\n    class Nested:\n        def method(self): return __class__\n"
    )
    path, tree = _source(metadata, tmp_path, raw)
    expected = compile(raw, str(path), "exec", dont_inherit=True)
    first_class = next(value for value in expected.co_consts if type(value) is CodeType)
    first = metadata.parameters._method_code(tree.body[0], "first", str(path), native_context=True)
    assert first == _body(first_class, "Example.first")
    with pytest.raises(ValueError, match="original class AST"):
        metadata.parameters._method_code(tree.body[1], "first", str(path), native_context=True)
    nested = tree.body[2].body[0].body[0]
    assert metadata.colormaps._context_code(nested, str(path)) == _body(
        expected, "outer.<locals>.Nested.method"
    )


def test_compilation_cache_bounded_eviction_returns_only_immutable_metadata(metadata):
    p = metadata.parameters
    first = p._compiled_source(SAMPLE, "<compiler-input>", optimize=0)
    for index in range(17):
        p._compiled_source(
            SAMPLE + f"# cache entry {index}\n".encode(), "<compiler-input>", optimize=0
        )
    assert p._compilation_metadata.cache_info().currsize == 16
    after = p._compiled_source(SAMPLE, "<compiler-input>", optimize=0)
    assert after == first and after is not first

    def immutable(value):
        return type(value) in (str, int, CodeType) or (
            type(value) is tuple and all(immutable(child) for child in value)
        )

    assert immutable(after)


@pytest.mark.parametrize(
    "change", ("bytes_subclass", "filename_subclass", "bool", "too_large", "syntax")
)
def test_compilation_cache_invalid_inputs_never_prime_cache(metadata, change):
    p = metadata.parameters

    class Bytes(bytes):
        pass

    class Text(str):
        pass

    raw, filename, optimize = SAMPLE, "<compiler-input>", 0
    if change == "bytes_subclass":
        raw = Bytes(raw)
    elif change == "filename_subclass":
        filename = Text(filename)
    elif change == "bool":
        optimize = False
    elif change == "too_large":
        raw = b" " * (p._COMPILATION_MAX_BYTES + 1)
    else:
        raw = b"def ("
    for _ in range(2):
        with pytest.raises((ValueError, SyntaxError)):
            p._compiled_source(raw, filename, optimize=optimize)
    assert p._compilation_metadata.cache_info().currsize == 0


@pytest.mark.parametrize("change", ("code", "keywords", "guard", "shared", "compiler"))
def test_compilation_cache_context_guard_retains_live_contract(
    metadata, tmp_path, monkeypatch, change
):
    p, c = metadata.parameters, metadata.colormaps
    path, tree = _source(metadata, tmp_path)
    method = tree.body[-1].body[0]
    c._context_code(method, str(path))
    entries, caught = [], None

    def foreign(*args, **kwargs):
        entries.append(change)
        raise AssertionError("Unowned contextual helper entered")

    with monkeypatch.context() as patch:
        if change == "code":
            patch.setattr(c._context_code, "__code__", c._context_code.__code__.replace())
        elif change == "keywords":
            patch.setattr(c._context_code, "__kwdefaults__", dict(c._context_code.__kwdefaults__))
        elif change == "guard":
            patch.setattr(c, "_compiler_contract", foreign)
        elif change == "shared":
            patch.setattr(p, "_compiled_source", foreign)
        else:
            patch.setattr(c, "compile", builtins.compile, raising=False)
        try:
            c._context_code(method, str(path))
        except BaseException as error:
            caught = error
    assert type(caught) is ValueError and entries == []
    c._compiler_contract()


@pytest.mark.parametrize("route", ("parameters", "colormaps"))
@pytest.mark.parametrize("change", ("empty", "equal_tuple", "anchor_defaults"))
def test_compilation_cache_record_anchors_refuse_retargeting(
    metadata, tmp_path, monkeypatch, route, change
):
    path, tree = _source(metadata, tmp_path)
    p, c = metadata.parameters, metadata.colormaps
    c._context_code(tree.body[-1].body[0], str(path))
    module = p if route == "parameters" else c
    prefix = "_COMPILATION_" if route == "parameters" else "_CONTEXT_"
    records = getattr(module, prefix + "RECORDS")
    changed = () if change == "empty" else tuple(list(records))
    assert changed is not records
    with monkeypatch.context() as patch:
        if change == "anchor_defaults":
            patch.setattr(getattr(module, prefix + "ANCHOR"), "__defaults__", (changed,))
        else:
            patch.setattr(module, prefix + "RECORDS", changed)
        with pytest.raises(ValueError, match="anchor|cache/guard/delegate"):
            c._context_code(tree.body[-1].body[0], str(path))
    p._compilation_contract()
    c._compiler_contract()
