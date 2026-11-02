"""Read-only conditional colormap boundary; no native or Matplotlib calls."""

import ast
import builtins
import copy
import pickle
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import CodeType, FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_colormaps as stage
from tests.unit import test_betse_native_parameter_modulators as earlier
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

blocked = earlier.blocked
ORIGINAL_COMPILE, ORIGINAL_CONFIGURATION, ORIGINAL_NATIVE = (
    stage._compile,
    stage._configuration,
    stage._native,
)
ORIGINAL_CONTEXT = stage._context_code


def _unavailable(*args, **kwargs):
    raise AssertionError("Prepared lookup/helper/getter must never execute")


def _module_body(code, qualified):
    """Independent fixtures use whole-module CodeTypes, never module execution."""
    bodies = []
    pending = [code]
    while pending:
        current = pending.pop()
        for value in current.co_consts:
            if type(value) is CodeType:
                if value.co_qualname == qualified:
                    bodies.append(value)
                pending.append(value)
    assert len(bodies) == 1
    return bodies[0]


@pytest.fixture
def controlled(monkeypatch, tmp_path):
    h = earlier.controlled.__wrapped__(monkeypatch, tmp_path, SimpleNamespace(param="none"))
    owner = earlier.run(h)
    parent = stage.previous._ISSUED[owner]
    names = ("conditional-red", "conditional-red", "missing", "conditional-blue")
    # Reuse the complete conditional registry/source graph. This is metadata
    # inspection, never a helper/getter invocation or native-parent admission.
    model = _native_model(monkeypatch, tmp_path)
    model.registry._cmaps = {names[0]: object(), names[3]: object()}
    api = ORIGINAL_NATIVE(model.parent)
    assert api.registry_namespace is object.__getattribute__(model.registry, "__dict__")
    assert api.registry is model.registry and api.kind is model.kind
    assert api.mapping is model.registry._cmaps and model.entries == []

    def native(p):
        assert p is parent
        api.helper_bindings = (stage.prefix._function_bindings(api.helper),)
        api.getter_bindings = (stage.prefix._function_bindings(api.getter),)
        return api

    monkeypatch.setattr(stage, "_native", native)
    monkeypatch.setattr(stage, "_configuration", lambda p: (names, ((), (parent.p, names))))
    monkeypatch.setattr(stage, "_compile", lambda p: (_unavailable, _unavailable))
    return SimpleNamespace(
        before=h,
        parent=parent,
        owner=owner,
        p=parent.p,
        names=names,
        api=api,
        prepare=lambda: stage.prepare(owner, law_id=stage.LAW_ID),
    )


def empty():
    assert not stage._ACTIVE
    earlier.empty()


def test_literal_source_and_aliases_stop_before_exports_and_constants():
    plan = stage.source_plan()
    assert plan["statement_slice"] == (135, 139) and plan["source_lines"] == (1007, 1014)
    assert plan["next_source_line"] == 1017 and len(plan["roles"]) == 4
    assert plan["metadata_only"] and not plan["alias_getters_invoked"]
    assert plan["native_lookup_calls"] == 0 and not plan["parameter_advanced"]
    assert not plan["returned_colormap_objects_owned"]
    assert not plan["constants_ions_profiles_Simulator_INIT_admitted"]


def test_literal_four_statements_compile_without_running_source_or_getters():
    module = ModuleType("conditional-original-parameter-module")
    module.__dict__.update(__builtins__=vars(builtins))
    fn = FunctionType(_unavailable.__code__, vars(module), "load")
    parent = SimpleNamespace(
        function=fn,
        birth=SimpleNamespace(source=SimpleNamespace(modules={"betse.science.parameters": module})),
    )
    function, original = ORIGINAL_COMPILE(parent)
    _, _, _, selected = stage._ast()
    names = tuple(n.targets[0].attr for n in selected)
    assert names == tuple(row[0] for row in stage.ROLES)
    assert function.__globals__ is vars(module) and original is fn
    assert function.__builtins__ is fn.__builtins__ and function.__code__.co_freevars == ()
    assert function.__code__.co_filename == stage.source_plan()["parameter_source"]
    path = Path(function.__code__.co_filename)
    tree = ast.parse(path.read_bytes())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Parameters")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "load")
    method.body = copy.deepcopy(selected)
    expected = _module_body(
        compile(tree, str(path), "exec", dont_inherit=True, optimize=0), "Parameters.load"
    )
    assert function.__code__.co_qualname == expected.co_qualname
    assert stage.prefix.parameters.inherited._code(function.__code__) == (
        stage.prefix.parameters.inherited._code(expected)
    )


@pytest.mark.parametrize(
    "qualified", ["helper", "Envelope.method", "Envelope.factory.<locals>.nested"]
)
def test_context_compiler_preserves_import_future_decorator_and_nested_class_code(
    tmp_path, qualified
):
    # Every executable surface is deliberately unavailable. Compiling the
    # entire original context must not resolve/import/call any of them.
    text = (
        "from __future__ import annotations\n"
        "unavailable_module_entry()\n"
        "import unavailable_compiler_authority as authority\n"
        "@unavailable_decorator\n"
        "def helper(value: Missing = unavailable_default_entry()) -> Missing:\n"
        "    return authority.apply(value)\n"
        "class Envelope:\n"
        "    unavailable_class_entry()\n"
        "    @unavailable_decorator\n"
        "    def method(self, value: Missing = unavailable_default_entry()) -> Missing:\n"
        "        return authority.apply(__class__, value)\n"
        "    def factory(self):\n"
        "        def nested(value: Missing) -> Missing:\n"
        "            return authority.apply(self, value)\n"
        "        return nested\n"
    )
    path = tmp_path / "conditional_complete_context.py"
    path.write_text(text)
    tree = ast.parse(text)
    node = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == qualified.rsplit(".", 1)[-1]
    )
    expected = _module_body(
        compile(tree, str(path), "exec", dont_inherit=True, optimize=0), qualified
    )
    actual = stage._context_code(node, str(path))
    assert actual.co_qualname == qualified and actual.co_filename == str(path)
    assert actual.co_firstlineno == expected.co_firstlineno
    assert stage.prefix.parameters.inherited._code(actual) == (
        stage.prefix.parameters.inherited._code(expected)
    )
    if qualified == "Envelope.method":
        assert actual.co_freevars == ("__class__",)
    elif qualified.endswith(".<locals>.nested"):
        assert actual.co_freevars == ("self",)
    assert path.read_text() == text


def test_context_body_rewrite_preserves_whole_class_module_and_original_header(tmp_path):
    text = (
        "from __future__ import annotations\n"
        "unavailable_module_entry()\n"
        "import unavailable_compiler_authority as authority\n"
        "class Envelope:\n"
        "    @unavailable_decorator\n"
        "    def load(self, value: Missing = unavailable_default_entry()) -> Missing:\n"
        "        return authority.original(value)\n"
    )
    path = tmp_path / "conditional_context_rewrite.py"
    path.write_text(text)
    tree = ast.parse(text)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    selected = copy.deepcopy(node)
    selected.body[0].value.func.attr = "selected"
    actual = stage._context_code(node, str(path), replacement=selected)
    expected_tree = ast.parse(text)
    expected_node = next(n for n in ast.walk(expected_tree) if isinstance(n, ast.FunctionDef))
    expected_node.body[0].value.func.attr = "selected"
    expected = _module_body(
        compile(expected_tree, str(path), "exec", dont_inherit=True, optimize=0), "Envelope.load"
    )
    assert actual.co_qualname == expected.co_qualname == "Envelope.load"
    assert stage.prefix.parameters.inherited._code(actual) == (
        stage.prefix.parameters.inherited._code(expected)
    )
    assert "selected" in actual.co_names and "original" not in actual.co_names
    assert path.read_text() == text


@pytest.mark.parametrize("drift", ["name", "argument", "decorator", "return", "line"])
def test_context_body_rewrite_refuses_any_header_or_source_span_change(tmp_path, drift):
    text = "class Envelope:\n    def load(self, value: int) -> int:\n        return value\n"
    path = tmp_path / "conditional_context_header.py"
    path.write_text(text)
    node = ast.parse(text).body[0].body[0]
    selected = copy.deepcopy(node)
    if drift == "name":
        selected.name = "foreign"
    elif drift == "argument":
        selected.args.args[-1].arg = "foreign"
    elif drift == "decorator":
        selected.decorator_list.append(ast.Name(id="foreign", ctx=ast.Load()))
    elif drift == "return":
        selected.returns.id = "float"
    else:
        selected.lineno += 1
    with pytest.raises(ValueError, match="changed the original header or scope"):
        stage._context_code(node, str(path), replacement=selected)
    assert path.read_text() == text


@pytest.mark.parametrize("drift", ["body", "name", "line", "column"])
def test_context_compiler_requires_exact_declared_original_node(tmp_path, drift):
    text = "def helper(value):\n    return value\n"
    path = tmp_path / "conditional_context_span.py"
    path.write_text(text)
    node = ast.parse(text).body[0]
    if drift == "body":
        node.body[0].value.id = "foreign"
    elif drift == "name":
        node.name = "foreign"
    elif drift == "line":
        node.lineno += 1
    else:
        node.col_offset += 1
    with pytest.raises(ValueError, match="One exact declared function/source span"):
        stage._context_code(node, str(path))


@pytest.mark.parametrize("bound", ["bytes", "nodes", "codes"])
def test_context_compiler_refuses_bounded_source_or_traversal_exhaustion(
    monkeypatch, tmp_path, bound
):
    text = "def helper(value):\n    return value\n"
    path = tmp_path / "conditional_context_bounds.py"
    path.write_text(text)
    node = ast.parse(text).body[0]
    name, maximum = {
        "bytes": ("_CONTEXT_MAX_BYTES", len(text.encode()) - 1),
        "nodes": ("_CONTEXT_MAX_NODES", 1),
        "codes": ("_CONTEXT_MAX_CODES", 1),
    }[bound]
    monkeypatch.setattr(stage, name, maximum)
    with pytest.raises(ValueError, match="Bounded"):
        stage._context_code(node, str(path))


@pytest.mark.parametrize("drift", [False, True])
def test_undecorated_context_authentication_binds_exact_lexical_qualname(tmp_path, drift):
    text = "class Envelope:\n    def helper(self):\n        return None\n"
    path = tmp_path / "conditional_lexical_helper.py"
    path.write_text(text)
    tree = ast.parse(text)
    expected = _module_body(
        compile(tree, str(path), "exec", dont_inherit=True, optimize=0), "Envelope.helper"
    )
    module = ModuleType("conditional.lexical_helper")
    vars(module).update(__builtins__=vars(builtins))
    function = FunctionType(expected, vars(module), "helper")
    node = tree.body[0].body[0]
    assert stage._undecorated(function, module, path, node)
    if drift:
        function.__code__ = expected.replace(co_qualname="Foreign.helper")
        with pytest.raises(ValueError, match="undecorated helper outer executable"):
            stage._undecorated(function, module, path, node)


@pytest.mark.parametrize("drift", ["none", "isolated-context", "lexical-scope"])
def test_decorated_core_uses_same_complete_context_without_decorator_or_helper_calls(
    tmp_path, drift
):
    text = (
        "from __future__ import annotations\n"
        "unavailable_module_entry()\n"
        "import unavailable_compiler_authority as authority\n"
        "@unavailable_decorator\n"
        "def helper(value):\n"
        "    return authority.apply(value)\n"
    )
    path = tmp_path / "conditional_context_decorated.py"
    path.write_text(text)
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    expected = _module_body(
        compile(tree, str(path), "exec", dont_inherit=True, optimize=0), "helper"
    )
    module = ModuleType("conditional.decorated_core")
    vars(module).update(__builtins__=vars(builtins), authority=object())
    function = FunctionType(expected, vars(module), "helper")
    assert stage._canonical(function, module, path, node)
    if drift == "isolated-context":
        isolated = stage._code(node, str(path), "helper")
        assert stage.prefix.parameters.inherited._code(isolated) != (
            stage.prefix.parameters.inherited._code(expected)
        )
        function.__code__ = isolated
    elif drift == "lexical-scope":
        function.__code__ = expected.replace(co_qualname="Foreign.helper")
    if drift != "none":
        with pytest.raises(ValueError, match="helper executable/globals changed"):
            stage._canonical(function, module, path, node)


@pytest.mark.parametrize("when", ["before-use", "issued-boundary"])
@pytest.mark.parametrize(
    "drift",
    [
        "global-compiler",
        "builtin-compiler",
        "same-compiler-shadow",
        "builtins-namespace",
        "keyword-dictionary",
        "keyword-value",
        "keyword-key",
        "keyword-extra",
    ],
)
def test_context_compiler_and_keyword_defaults_refuse_entry_and_issued_lifetime_drift(
    monkeypatch, tmp_path, when, drift
):
    path = tmp_path / "conditional_compiler_binding.py"
    path.write_text("def helper(value):\n    return value\n")
    node = ast.parse(path.read_bytes()).body[0]
    assert ORIGINAL_CONTEXT(node, str(path)).co_qualname == "helper"
    h = controlled.__wrapped__(monkeypatch, tmp_path) if when == "issued-boundary" else None
    owner = None if h is None else h.prepare()
    record = None if owner is None else owner.binding
    retained = stage._bindings()
    binding = stage._compiler_contract()
    keywords = ORIGINAL_CONTEXT.__kwdefaults__
    key = next(iter(keywords))
    compiler = builtins.compile
    assert binding[1][0] is compiler and binding[1][5] is keywords
    assert binding[1][6] is key and binding[1][7] is None
    assert any(value is compiler for value in retained[1])
    assert any(value is keywords for value in retained[1])
    assert any(value is key for value in retained[1])
    entries = []

    def foreign_compiler(*args, **kwargs):
        entries.append("foreign-compiler")
        raise AssertionError("Foreign compiler must never enter")

    caught = None
    with monkeypatch.context() as patch:
        if drift == "global-compiler":
            patch.setattr(stage, "compile", foreign_compiler, raising=False)
        elif drift == "builtin-compiler":
            patch.setattr(builtins, "compile", foreign_compiler)
        elif drift == "same-compiler-shadow":
            patch.setattr(stage, "compile", compiler, raising=False)
        elif drift == "builtins-namespace":
            patch.setitem(vars(stage), "__builtins__", dict(vars(builtins)))
        elif drift == "keyword-dictionary":
            patch.setattr(ORIGINAL_CONTEXT, "__kwdefaults__", dict(keywords))
        elif drift == "keyword-value":
            patch.setitem(keywords, key, object())
        elif drift == "keyword-key":
            changed_key = "".join(("replace", "ment"))
            assert changed_key == key and changed_key is not key
            patch.delitem(keywords, key)
            patch.setitem(keywords, changed_key, None)
        else:
            patch.setitem(keywords, "foreign", None)
        # Restore a deliberately changed builtin before assertion/evidence
        # machinery. Only the actual compiler or issued-boundary check runs.
        try:
            if owner is None:
                ORIGINAL_CONTEXT(node, str(path))
            else:
                _ = owner.binding
        except BaseException as error:
            caught = error
    expected = (
        "Contextual compiler cached builtins association changed"
        if drift == "builtins-namespace"
        else "Original resolved contextual compiler required"
        if drift in ("global-compiler", "builtin-compiler", "same-compiler-shadow")
        else "Original contextual compiler keyword-default mapping required"
        if drift == "keyword-dictionary"
        else "Original contextual compiler replacement keyword/key/value required"
    )
    assert type(caught) is ValueError and caught.args == (expected,)
    assert entries == []
    stage.prefix.parameters.inherited._same(stage._compiler_contract(), binding)
    stage.prefix.parameters.inherited._same(stage._bindings(), retained)
    if owner is not None:
        assert owner.binding is record and stage._ISSUED[owner].binding is record
    empty()


@pytest.mark.parametrize("drift", ["resolved-compiler", "keyword-dictionary"])
def test_context_compiler_rechecks_contract_after_source_read_before_compilation(
    monkeypatch, tmp_path, drift
):
    path = tmp_path / "conditional_compiler_read_boundary.py"
    path.write_text("def helper(value):\n    return value\n")
    node = ast.parse(path.read_bytes()).body[0]
    assert ORIGINAL_CONTEXT(node, str(path)).co_qualname == "helper"
    retained = stage._compiler_contract()
    original_parse = ast.parse
    entries, reads, caught = [], [], None

    def foreign_compiler(*args, **kwargs):
        entries.append("foreign-compiler")
        raise AssertionError("Foreign compiler must never enter")

    with monkeypatch.context() as patch:

        def after_read(*args, **kwargs):
            tree = original_parse(*args, **kwargs)
            reads.append("source-parsed")
            if drift == "resolved-compiler":
                patch.setattr(stage, "compile", foreign_compiler, raising=False)
            else:
                patch.setattr(
                    ORIGINAL_CONTEXT, "__kwdefaults__", dict(ORIGINAL_CONTEXT.__kwdefaults__)
                )
            return tree

        patch.setattr(ast, "parse", after_read)
        try:
            ORIGINAL_CONTEXT(node, str(path))
        except BaseException as error:
            caught = error
    expected = (
        "Original resolved contextual compiler required"
        if drift == "resolved-compiler"
        else "Original contextual compiler keyword-default mapping required"
    )
    assert type(caught) is ValueError and caught.args == (expected,)
    assert reads == ["source-parsed"] and entries == []
    stage.prefix.parameters.inherited._same(stage._compiler_contract(), retained)


@pytest.mark.parametrize("case", ["valid", "missing-key", "wrong-type", "shadow", "descriptor"])
def test_configuration_binds_raw_names_and_descriptors_without_getters(case):
    calls = []

    def get(self):
        calls.append("getter")
        raise AssertionError("Actual alias getter forbidden")

    cls = type("ConditionalParameters", (), {alias: property(get) for _, alias, _ in stage.ROLES})
    p = cls()
    p._conf = {"results options": {key: "same-name" for _, _, key in stage.ROLES}}
    parent = SimpleNamespace(p=p, birth=SimpleNamespace(p=p, source=SimpleNamespace(cls=cls)))
    if case == "missing-key":
        del p._conf["results options"][stage.ROLES[0][2]]
    elif case == "wrong-type":
        p._conf["results options"][stage.ROLES[0][2]] = 123
    elif case == "shadow":
        vars(p)[stage.ROLES[0][1]] = "same-name"
    elif case == "descriptor":
        setattr(cls, stage.ROLES[0][1], "same-name")
    if case == "valid":
        names, bindings = ORIGINAL_CONFIGURATION(parent)
        assert names == ("same-name",) * 4 and bindings[1][0] is cls
        assert all(
            name is p._conf["results options"][key]
            for name, (_, _, key) in zip(names, stage.ROLES, strict=True)
        )
    else:
        with pytest.raises((ValueError, KeyError)):
            ORIGINAL_CONFIGURATION(parent)
    assert calls == []


def _native_model(monkeypatch, tmp_path):
    """Conditional already-imported shape, not genuine import/runtime authority."""
    native_path = (
        stage.prefix.parameters.inherited.tissue.aliases.NATIVE
        / "betse/lib/matplotlib/mplcolormap.py"
    )
    module = ModuleType("betse.lib.matplotlib.mplcolormap")
    module.__dict__.update(__file__=str(native_path), __builtins__=vars(builtins))
    cm = ModuleType("matplotlib.cm")
    cm_path = tmp_path / "conditional_cm.py"
    text = (
        "class ColormapRegistry(Mapping):\n"
        "    def __getitem__(self, name):\n"
        "        entries.append('__getitem__')\n"
        '        raise AssertionError("lookup forbidden")\n'
        "    def __iter__(self):\n"
        "        entries.append('__iter__')\n"
        '        raise AssertionError("iteration forbidden")\n'
        "    def __len__(self):\n"
        "        entries.append('__len__')\n"
        '        raise AssertionError("length forbidden")\n'
    )
    cm_path.write_text(text)
    entries = []
    cm.__dict__.update(
        __file__=str(cm_path), __builtins__=vars(builtins), Mapping=Mapping, entries=entries
    )
    compiled = compile(ast.parse(text), str(cm_path), "exec", dont_inherit=True, optimize=0)
    namespace = {"__module__": cm.__name__}
    for name in ("__getitem__", "__iter__", "__len__"):
        code = _module_body(compiled, "ColormapRegistry." + name)
        namespace[name] = FunctionType(code, vars(cm), name)
    kind = type(Mapping)("ColormapRegistry", (Mapping,), namespace)
    cm.ColormapRegistry = kind
    registry = object.__new__(kind)
    registry._cmaps = {"declared": object()}
    mpl = ModuleType("matplotlib")
    mpl.colormaps = registry
    module.colormaps = registry
    node = next(
        n
        for n in ast.parse(native_path.read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "get_colormap"
    )
    # Independent full-module compilation only; never execute its imports,
    # decorators, factories or helper body to create this conditional fixture.
    compiled = compile(
        ast.parse(native_path.read_bytes()), str(native_path), "exec", dont_inherit=True
    )
    helper_code = next(
        c for c in compiled.co_consts if type(c) is CodeType and c.co_name == node.name
    )
    module.get_colormap = FunctionType(helper_code, vars(module), "get_colormap")
    for name, obj in ((module.__name__, module), (cm.__name__, cm), (mpl.__name__, mpl)):
        monkeypatch.setitem(sys.modules, name, obj)
    pmod = ModuleType("conditional-parameter-module")
    pmod.mplcolormap = module
    parent = SimpleNamespace(
        birth=SimpleNamespace(source=SimpleNamespace(modules={"betse.science.parameters": pmod})),
        runtime=SimpleNamespace(runtime_files={str(native_path): stage.COLORMAP_SHA256}),
    )
    return SimpleNamespace(
        parent=parent,
        module=module,
        cm=cm,
        mpl=mpl,
        registry=registry,
        kind=kind,
        helper_code=helper_code,
        entries=entries,
    )


@pytest.mark.parametrize(
    "drift",
    [
        "none",
        "missing-module",
        "missing-born-pin",
        "missing-registry",
        "foreign-registry",
        "instance-shadow",
        "helper-code",
        "helper-globals",
        "cached-builtins",
        "getter-globals",
    ],
)
def test_native_runtime_and_reached_dispatch_binding_without_lookup(monkeypatch, tmp_path, drift):
    h = _native_model(monkeypatch, tmp_path)
    baseline = ORIGINAL_NATIVE(h.parent)
    assert baseline.registry is h.registry and baseline.mapping is h.registry._cmaps
    assert type(h.kind) is type(Mapping) and h.kind.__bases__ == (Mapping,)
    assert h.kind.__mro__ == (h.kind, *Mapping.__mro__)
    assert baseline.helper is h.module.get_colormap and baseline.getter is h.kind.__getitem__
    assert len(baseline.files) == 2 and baseline.files[0][1] == stage.COLORMAP_SHA256
    expected = {
        "missing-module": ("Actual born mplcolormap runtime required", "native_runtime"),
        "missing-born-pin": ("Actual born mplcolormap runtime required", "native_runtime"),
        "missing-registry": ("Actual imported Matplotlib registry authority absent", "registry"),
        "foreign-registry": ("Actual original Matplotlib registry/dispatch required", None),
        "instance-shadow": ("Original registry instance mapping/dispatch changed", None),
        "helper-code": ("Original colormap helper executable/globals changed", None),
        "helper-globals": ("Original colormap helper executable/globals changed", None),
        "cached-builtins": ("Prefix construction namespace/cached builtins differ", None),
        "getter-globals": ("Original undecorated helper outer executable/globals required", None),
    }
    if drift == "missing-module":
        monkeypatch.delitem(sys.modules, h.module.__name__)
    elif drift == "missing-born-pin":
        h.parent.runtime.runtime_files.clear()
    elif drift == "missing-registry":
        monkeypatch.delitem(sys.modules, "matplotlib")
    elif drift == "foreign-registry":
        h.mpl.colormaps = object()
    elif drift == "instance-shadow":
        h.registry.__getitem__ = _unavailable
    elif drift == "helper-code":
        h.module.get_colormap = _unavailable
    elif drift == "helper-globals":
        h.module.get_colormap = FunctionType(h.helper_code, dict(vars(h.module)))
    elif drift == "cached-builtins":
        ns = vars(h.module)
        ns["__builtins__"] = dict(vars(builtins))
        h.module.get_colormap = FunctionType(h.helper_code, ns)
        ns["__builtins__"] = vars(builtins)
    elif drift == "getter-globals":
        original = vars(h.kind)["__getitem__"]
        h.kind.__getitem__ = FunctionType(original.__code__, dict(vars(h.cm)))
    if drift == "none":
        api = ORIGINAL_NATIVE(h.parent)
        assert api.registry is h.registry and api.mapping is h.registry._cmaps
        assert api.helper is h.module.get_colormap and api.getter is h.kind.__getitem__
        assert len(api.files) == 2 and api.files[0][1] == stage.COLORMAP_SHA256
    else:
        message, expected_stage = expected[drift]
        with pytest.raises(ValueError) as caught:
            ORIGINAL_NATIVE(h.parent)
        assert caught.value.args == (message,)
        assert getattr(caught.value, "stage", None) == expected_stage
    assert h.entries == []


def test_missing_authentic_runtime_has_executable_refusal_without_import(monkeypatch):
    module = ModuleType("conditional-parameter-module")
    parent = SimpleNamespace(
        birth=SimpleNamespace(source=SimpleNamespace(modules={"betse.science.parameters": module})),
        runtime=SimpleNamespace(runtime_files={}),
    )
    with pytest.raises(stage.ColormapBoundaryRejected) as caught:
        ORIGINAL_NATIVE(parent)
    assert caught.value.stage == "native_runtime"


def test_conditional_issued_same_p_input_boundary_never_advances_or_looks_up(controlled, tmp_path):
    h = controlled
    before = tuple(vars(h.p)), tuple(vars(h.p).values())
    owner = h.prepare()
    assert owner.parameters is h.p and owner.binding.names == h.names
    assert owner.binding.registered == (True, True, False, True)
    assert not h.parent.invalid and h.before.calls == ["conditional_modulators"]
    stage.prefix.parameters.inherited._same((tuple(vars(h.p)), tuple(vars(h.p).values())), before)
    with pytest.raises(stage.ColormapBoundaryRejected) as caught:
        stage.require_lookup(owner)
    assert caught.value.stage == "lookup_result_prerequisite"
    assert not any(store in vars(h.p) for store, _, _ in stage.ROLES)
    assert h.parent.trial is stage.previous._validate(h.owner).trial
    empty()
    save(
        tmp_path,
        "conditional-colormap-boundary",
        dict(
            binding=stage.binding_record(owner.binding),
            work=stage._ISSUED[owner].work,
            genuine_native_import_or_lookup_entries=0,
            unchanged_parameter=True,
            conditional_upstream_and_api=True,
            result_objects_owned=False,
        ),
    )


@pytest.mark.parametrize(
    "drift", ["record", "mapping", "helper", "getter", "files", "parent", "source"]
)
def test_completed_boundary_refuses_live_binding_or_parent_drift(controlled, monkeypatch, drift):
    h = controlled
    owner = h.prepare()
    assert owner.parameters is h.p
    ctx = stage._ISSUED[owner]
    if drift == "record":
        ctx.binding = replace(ctx.binding, source_identity="foreign")
    elif drift == "mapping":
        h.api.mapping[h.names[0]] = object()
    elif drift in ("helper", "getter"):
        setattr(h.api, drift, FunctionType(_unavailable.__code__, _unavailable.__globals__))
    elif drift == "files":
        h.api.files = (("foreign", "0" * 64),)
    elif drift == "parent":
        h.parent.invalid = True
    else:
        monkeypatch.setattr(stage, "STOP", 140)
    with pytest.raises(ValueError):
        _ = owner.parameters
    empty()


def test_source_failure_identity_cause_and_readonly_claim_evidence(controlled, monkeypatch):
    h = controlled
    primary, cause = SyntheticSourceFailure("runtime absent"), SyntheticSourceCause("original")

    def fail(parent):
        raise primary from cause

    monkeypatch.setattr(stage, "_native", fail)
    with pytest.raises(SyntheticSourceFailure) as caught:
        h.prepare()
    assert caught.value is primary and primary.__cause__ is cause
    ctx = primary.colormap_boundary
    assert ctx.parent is h.parent and not ctx.active and ctx.primary is primary
    assert not h.parent.invalid and not any(store in vars(h.p) for store, _, _ in stage.ROLES)
    empty()


@pytest.mark.parametrize("case", ["law", "none", "dictionary", "record", "unissued", "pickle"])
def test_explicit_law_and_opaque_parent_boundary(controlled, case):
    h = controlled
    if case == "law":
        with pytest.raises(stage.ColormapBoundaryRejected) as caught:
            stage.prepare(h.owner, law_id="foreign")
        assert caught.value.stage == "law"
    elif case == "pickle":
        owner = h.prepare()
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(owner)
    else:
        value = {
            "none": None,
            "dictionary": {},
            "record": h.parent.trial,
            "unissued": object.__new__(stage.previous.ModulatorsOwner),
        }[case]
        with pytest.raises(stage.previous.ModulatorsRejected):
            stage.prepare(value, law_id=stage.LAW_ID)
    empty()
