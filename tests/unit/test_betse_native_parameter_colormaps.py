"""Read-only conditional colormap boundary; no native or Matplotlib calls."""

import ast
import builtins
import pickle
import sys
from dataclasses import replace
from types import FunctionType, ModuleType, SimpleNamespace

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


def _unavailable(*args, **kwargs):
    raise AssertionError("Prepared lookup/helper/getter must never execute")


@pytest.fixture
def controlled(monkeypatch, tmp_path):
    h = earlier.controlled.__wrapped__(monkeypatch, tmp_path, SimpleNamespace(param="none"))
    owner = earlier.run(h)
    parent = stage.previous._ISSUED[owner]
    names = ("conditional-red", "conditional-red", "missing", "conditional-blue")
    registry = SimpleNamespace()
    mapping = {names[0]: object(), names[3]: object()}
    module, cm, mpl = (
        ModuleType("conditional-colormap"),
        ModuleType("conditional-cm"),
        ModuleType("conditional-mpl"),
    )
    api = SimpleNamespace(
        module=module,
        helper=_unavailable,
        registry=registry,
        kind=type(registry),
        mapping=mapping,
        getter=_unavailable,
        cm=cm,
        mpl=mpl,
        files=(),
    )

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
        "class ColormapRegistry:\n"
        "    def __getitem__(self, name):\n"
        '        raise AssertionError("lookup forbidden")\n'
    )
    cm_path.write_text(text)
    cm.__dict__.update(__file__=str(cm_path), __builtins__=vars(builtins))
    cls_node = ast.parse(text).body[0]
    code = stage.prefix.parameters._method_code(cls_node, "__getitem__", str(cm_path))
    getter = FunctionType(code, vars(cm), "__getitem__")
    kind = type("ColormapRegistry", (), {"__getitem__": getter, "__module__": cm.__name__})
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
    helper_code = stage._code(node, str(native_path), "get_colormap")
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
        with pytest.raises(ValueError):
            ORIGINAL_NATIVE(h.parent)


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
