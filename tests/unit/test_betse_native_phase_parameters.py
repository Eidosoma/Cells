"""Fresh native parameter ownership controls; all real constructors blocked."""

import ast
import builtins
import copy
import json
import sys
from dataclasses import replace
from types import CellType, CodeType, FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_paths as paths
from cells.processes import betse_native_phase_parameters as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    attempts = []
    old, trace, imp = sys.getprofile(), sys.gettrace(), builtins.__import__
    real = {
        stage._acquire.__code__,
        stage._invoke.__code__,
        stage.inherited.prepare.__code__,
        stage.inherited.tissue.prepare.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in real
            or frame.f_code.co_filename.startswith(str(stage.inherited.tissue.aliases.NATIVE) + "/")
        ):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native parameter/source entry forbidden")
        if old is not None:
            old(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name == "betse" or name.startswith("betse."):
            attempts.append(name)
            raise AssertionError("Actual native import forbidden")
        return imp(name, *args, **kwargs)

    def rng(*args, **kwargs):
        attempts.append("RNG")
        raise AssertionError("Actual RNG forbidden")

    monkeypatch.setattr(builtins, "__import__", imports)
    for name in ("RandomState", "default_rng", "seed", "random", "normal", "choice", "uniform"):
        monkeypatch.setattr(stage.inherited.tissue.callers.np.random, name, rng)
    sys.setprofile(profile)
    try:
        yield
        assert attempts == [] and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(old)
        sys.settrace(trace)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                dict(nodeid=request.node.nodeid, attempted=attempts, actual_native_or_RNG_entries=0)
            )
        )


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, plan):
    calls, hooks, errors, partial = [], {}, {}, []

    class Yaml:
        def __init__(self):
            self._conf = None

    class Child(Yaml):
        def __init__(self):
            super().__init__()
            self.item_type = Yaml

    class Parameters(Yaml):
        def __init__(self):
            partial.append(self)
            calls.append("constructor")
            super().__init__()
            for name in plan["path_fields"]:
                setattr(self, name, None)
            for name in stage._ROSTER:
                setattr(self, name, Child())
            self.anim.nested = Child()
            self.visual.same_nested = self.anim.nested
            if "constructor" in hooks:
                hooks["constructor"]()
            if "constructor" in errors:
                raise errors["constructor"] from errors.get("cause")

    module = SimpleNamespace(Parameters=Parameters)
    yamlfile = SimpleNamespace(YamlFileDefaultABC=Yaml)
    source = SimpleNamespace(
        cls=Parameters,
        yaml=Yaml,
        modules={"betse.science.parameters": module, "betse.lib.yaml.abc.yamlfileabc": yamlfile},
    )

    def acquire():
        calls.append("import")
        if "import" in errors:
            raise errors["import"] from errors.get("cause")
        return source

    def canonical(m, y):
        return m.Parameters

    def invoke(context):
        context.work.append(
            dict(
                layer="synthetic_constructor",
                source_file=__file__,
                method="SyntheticParameters.__init__",
            )
        )
        try:
            return context.source.cls()
        finally:
            context.locals[("synthetic", "constructor")] = dict(
                self=partial[-1] if partial else None
            )

    monkeypatch.setattr(stage, "_acquire", acquire)
    monkeypatch.setattr(stage, "_canonical", canonical)
    # This fixture supplies synthetic constructors only; genuine native method
    # admission is exercised separately by the compiled-metadata controls.
    monkeypatch.setattr(stage, "_acquired_parameter_methods", lambda source: None)
    monkeypatch.setattr(stage, "_live_parameter_method_bindings", lambda source: ())
    monkeypatch.setattr(stage, "_invoke", invoke)
    monkeypatch.setattr(stage, "source_plan", lambda: dict(plan, synthetic_only=True))
    monkeypatch.setenv(stage.inherited.RELEASE, "1")
    request = stage.declare(law_id=stage.LAW_ID, run_id="synthetic-unloaded")
    return SimpleNamespace(
        request=request,
        calls=calls,
        hooks=hooks,
        errors=errors,
        partial=partial,
        source=source,
        module=module,
        cls=Parameters,
    )


def birth(h):
    return stage.prepare(h.request, enabled=True)


def test_original_constructor_schema_and_no_selected_owner_adoption(plan):
    assert len(plan["native_pins"]) == 272
    assert plan["subconfigurations"] == stage._ROSTER and len(plan["path_fields"]) == 10
    assert plan["fresh_birth"] and not plan["existing_selected_parameter_or_tissue_owner_adopted"]
    assert not plan["loaded_Parameters_or_phase_or_INIT_authority"]


@pytest.mark.parametrize("enabled,env", [(False, "0"), (True, "0"), (False, "1"), (1, "1")])
def test_gates_precede_any_constructor_or_import(monkeypatch, enabled, env):
    monkeypatch.setenv(stage.inherited.RELEASE, env)
    with pytest.raises(stage.ParameterRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


@pytest.mark.parametrize(
    "law,run_id",
    [("foreign", "r"), (stage.LAW_ID, ""), (stage.LAW_ID, False), (stage.LAW_ID, "x" * 257)],
)
def test_request_requires_explicit_bounded_declaration(law, run_id):
    with pytest.raises(stage.ParameterRejected) as caught:
        stage.declare(law_id=law, run_id=run_id)
    assert caught.value.stage == "request"


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.ParameterOwner)]
)
def test_receipts_caches_or_existing_owners_are_never_constructor_inputs(controlled, value):
    with pytest.raises(stage.ParameterRejected) as caught:
        stage.prepare(value, enabled=True)
    assert caught.value.stage == "request" and controlled.calls == []


def test_copied_request_is_not_source_issuance(controlled):
    with pytest.raises(stage.ParameterRejected) as caught:
        stage.prepare(replace(controlled.request), enabled=True)
    assert caught.value.stage == "request" and controlled.calls == []


def test_bounded_complete_nested_graph_and_aliases_retained(controlled, tmp_path):
    h = controlled
    owner = birth(h)
    p = owner.parameters
    assert p is h.partial[0] and type(p) is h.cls and vars(p)["_conf"] is None
    assert p.visual.same_nested is p.anim.nested
    assert len(owner.trial.work) == 1 and owner.trial.source_completed
    with pytest.raises(stage.ParameterRejected) as caught:
        birth(h)
    assert caught.value.stage == "consumed" and h.calls == ["import", "constructor"]
    save(
        tmp_path,
        "constructed",
        dict(trial=owner.trial, graph=stage._ISSUED[owner].graph[1], synthetic_only=True),
    )


@pytest.mark.parametrize("point", ["import", "constructor"])
def test_primary_error_cause_and_failed_source_prefix_retained(controlled, tmp_path, point):
    h = controlled
    error, cause = (
        SyntheticSourceFailure("original source failed"),
        SyntheticSourceCause("original cause"),
    )
    h.errors.update({point: error, "cause": cause})
    with pytest.raises(stage.ParameterRejected) as caught:
        birth(h)
    e = caught.value
    assert e.source_error is error and e.__cause__ is error and error.__cause__ is cause
    assert not e.partial.source_completed and not stage._ACTIVE
    assert e.stage == ("native_import" if point == "import" else "native_parameter_constructor")
    if point == "constructor":
        assert e.partial.locals[("synthetic", "constructor")]["self"] is h.partial[0]
    save(
        tmp_path,
        "failed",
        dict(source=error, locals=e.partial.locals, work=e.partial.work, synthetic_only=True),
    )


@pytest.mark.parametrize("source_failure", [False, True])
def test_existing_observer_failure_retention_preserves_primary(
    controlled, monkeypatch, tmp_path, source_failure
):
    h = controlled
    capture = SyntheticCaptureFailure("capture failed")
    original = stage._invoke

    def invoke(ctx):
        try:
            return original(ctx)
        finally:
            stage.inherited.tissue.captures._remember_observation_error(
                ctx, capture, origin="synthetic_observer", raw=ctx.locals
            )

    monkeypatch.setattr(stage, "_invoke", invoke)
    if source_failure:
        h.errors["constructor"] = SyntheticSourceFailure("constructor failure")
    with pytest.raises(stage.ParameterRejected) as caught:
        birth(h)
    e = caught.value
    assert e.source_error is h.errors.get("constructor")
    assert any(err is capture for _, err in e.capture_errors)
    assert e.__cause__ is (h.errors["constructor"] if source_failure else capture)
    assert e.partial.source_completed is (not source_failure)
    save(
        tmp_path,
        "capture-incomplete",
        dict(
            primary=e.source_error,
            capture=e.capture_errors,
            partial=e.partial.locals,
            synthetic_only=True,
        ),
    )


def test_snapshot_failure_retains_returned_native_shaped_object(controlled, monkeypatch):
    capture = SyntheticCaptureFailure("snapshot failed")

    def fail(ctx):
        raise capture

    monkeypatch.setattr(stage, "_snapshot", fail)
    with pytest.raises(stage.ParameterRejected) as caught:
        birth(controlled)
    assert caught.value.source_error is None and caught.value.__cause__ is capture
    assert caught.value.partial.p is controlled.partial[0] and caught.value.partial.source_completed


@pytest.mark.parametrize(
    "mutation", ["load", "path", "subconfig", "alias", "same-dict", "class", "opaque"]
)
def test_unloaded_epoch_alias_layout_and_runtime_mutations_refuse(controlled, mutation):
    h = controlled
    owner = birth(h)
    ctx = stage._ISSUED[owner]
    p = ctx.p
    if mutation == "load":
        p._conf = {}
    elif mutation == "path":
        p.init_export_dirname = "/supplied/path"
    elif mutation == "subconfig":
        p.anim = h.source.yaml()
    elif mutation == "alias":
        p.visual.same_nested = p.csv
    elif mutation == "same-dict":
        p.anim.__dict__ = dict(vars(p.anim))
    elif mutation == "class":
        h.module.Parameters = type("Foreign", (h.cls,), {})
    else:
        p.opaque = object()
    with pytest.raises(stage.ParameterRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and ctx.invalid and h.calls.count("constructor") == 1


@pytest.mark.parametrize("swallow", [False, True])
def test_reentry_cannot_issue_or_construct_second_instance(controlled, swallow):
    h = controlled
    nested = []

    def reenter():
        try:
            birth(h)
        except stage.ParameterRejected as e:
            nested.append(e)
            if not swallow:
                raise

    h.hooks["constructor"] = reenter
    with pytest.raises(stage.ParameterRejected) as caught:
        birth(h)
    assert len(nested) == 1 and nested[0].stage == "reentrant"
    assert caught.value.partial.invalid and h.calls.count("constructor") == 1 and not stage._ACTIVE
    if not swallow:
        assert caught.value.source_error is nested[0]
    else:
        assert caught.value.partial.source_completed


def test_super_code_has_exact_class_cell_without_executing_constructor():
    tree = ast.parse("class Example(object):\n def __init__(self): super().__init__()")
    code = stage._method_code(tree.body[0], "__init__", "<metadata-only>")
    assert code.co_freevars == ("__class__",)


def _original_parameter_codes():
    path = stage.inherited.tissue.aliases.NATIVE / stage.PARAMETERS
    tree = ast.parse(path.read_bytes(), filename=str(path))
    node = stage.inherited._class(tree, "Parameters")
    module = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    cls = next(c for c in module.co_consts if type(c) is CodeType and c.co_name == "Parameters")
    return path, node, {c.co_name: c for c in cls.co_consts if type(c) is CodeType}


def _wrapped_parameter_metadata(name, monkeypatch):
    """Real decorator, compiled native metadata; no native class/body execution."""
    from beartype import beartype
    from beartype.claw._clawstate import claw_state

    path, _, codes = _original_parameter_codes()
    module = ModuleType("metadata_only_parameters")
    module.__file__ = str(path)
    module.__dict__["__builtins__"] = vars(builtins)
    cls = type("Parameters", (), {"__module__": module.__name__})
    originals = {}
    for method in ("__init__", "_unload_paths", "load", "reload_paths"):
        code = codes[method]
        original = FunctionType(
            code,
            vars(module),
            method,
            closure=tuple(CellType(cls) for _ in code.co_freevars) or None,
        )
        original.__annotations__ = {"return": None}
        setattr(cls, method, original)
        originals[method] = original
    assert beartype(cls) is cls
    wrapper = vars(cls)[name]
    # This isolated module exercises the genuine configuration association;
    # it never imports BETSE, installs a hook or issues a parameter owner.
    module.__dict__["__claw_state_beartype__"] = claw_state
    monkeypatch.setitem(
        claw_state.module_name_to_beartype_conf,
        module.__name__,
        wrapper.__kwdefaults__["__beartype_conf"],
    )
    return SimpleNamespace(
        source=SimpleNamespace(cls=cls, modules={"betse.science.parameters": module}),
        wrapper=wrapper,
        original=originals[name],
        module=module,
    )


@pytest.mark.parametrize("name", ["__init__", "_unload_paths", "load", "reload_paths"])
def test_wrapper_metadata_accepts_real_return_none_wrapper_without_body_execution(
    name, tmp_path, monkeypatch
):
    h = _wrapped_parameter_metadata(name, monkeypatch)
    assert h.wrapper is not h.original
    assert stage._method_original(h.source, name) is h.original
    before = stage._method_wrapper_bindings(h.wrapper, h.source.cls)
    after = stage._method_wrapper_bindings(h.wrapper, h.source.cls)
    assert len(before) == len(after) and all(a is b for a, b in zip(before, after, strict=True))
    save(tmp_path, "real-wrapper-metadata", dict(method=name, original_body_calls=0))


@pytest.mark.parametrize("removed", [None, "__init__", "_unload_paths", "load", "reload_paths"])
def test_wrapper_metadata_native_acquisition_requires_package_wrappers(removed, monkeypatch):
    h = _wrapped_parameter_metadata("load", monkeypatch)
    if removed is None:
        stage._acquired_parameter_methods(h.source)
    else:
        setattr(h.source.cls, removed, vars(h.source.cls)[removed].__wrapped__)
        with pytest.raises(ValueError, match="package-installed"):
            stage._acquired_parameter_methods(h.source)


@pytest.mark.parametrize("name", ["__init__", "_unload_paths", "load", "reload_paths"])
@pytest.mark.parametrize("change", ["unwrap", "remove"])
def test_wrapper_metadata_rechecks_acquisition_return_before_runtime_baseline(
    name, change, monkeypatch
):
    h = _wrapped_parameter_metadata("load", monkeypatch)
    h.module.Parameters = h.source.cls
    h.source.modules["betse.lib.yaml.abc.yamlfileabc"] = SimpleNamespace(YamlFileDefaultABC=object)
    h.source.yaml = object
    monkeypatch.setitem(sys.modules, "betse.science.parameters", h.module)
    monkeypatch.setattr(stage.inherited.tissue.aliases, "_check_modules", lambda: None)
    stage._acquired_parameter_methods(h.source)
    stage._runtime(h.source)
    original = vars(h.source.cls)[name].__wrapped__
    if change == "unwrap":
        setattr(h.source.cls, name, original)
    else:
        delattr(h.source.cls, name)
    with pytest.raises((ValueError, AttributeError)):
        stage._runtime(h.source)


@pytest.mark.parametrize("name", ["__init__", "_unload_paths", "load", "reload_paths"])
@pytest.mark.parametrize("change", ["unwrap", "remove"])
def test_wrapper_metadata_refuses_mutation_in_validation_return_observer(name, change, monkeypatch):
    h = _wrapped_parameter_metadata("load", monkeypatch)
    h.module.Parameters = h.source.cls
    h.source.modules["betse.lib.yaml.abc.yamlfileabc"] = SimpleNamespace(YamlFileDefaultABC=object)
    h.source.yaml = object
    monkeypatch.setitem(sys.modules, "betse.science.parameters", h.module)
    monkeypatch.setattr(stage.inherited.tissue.aliases, "_check_modules", lambda: None)
    stage._acquired_parameter_methods(h.source)
    before, trace, events = sys.getprofile(), sys.gettrace(), []

    def inherited_observer(frame, event, arg):
        if before is not None:
            before(frame, event, arg)
        if (
            event == "return"
            and frame.f_code is stage._acquired_parameter_methods.__code__
            and frame.f_locals.get("source") is h.source
            and not events
        ):
            events.append(name)
            method = vars(h.source.cls)[name]
            if change == "unwrap":
                setattr(h.source.cls, name, method.__wrapped__)
            else:
                delattr(h.source.cls, name)

    sys.setprofile(inherited_observer)
    try:
        with pytest.raises(ValueError):
            stage._runtime(h.source)
    finally:
        sys.setprofile(before)
        sys.settrace(trace)
    assert events == [name] and sys.getprofile() is before and sys.gettrace() is trace


@pytest.mark.parametrize(
    "change", ["delegate", "code", "globals", "defaults", "config", "state", "config_entry"]
)
def test_wrapper_metadata_rejects_preexisting_violation_and_hook_drift(change, monkeypatch):
    h = _wrapped_parameter_metadata("load", monkeypatch)
    error_module = sys.modules["beartype._check.error.errmain"]
    helper = error_module.get_hint_object_violation
    if change == "delegate":
        monkeypatch.setattr(
            error_module, "get_hint_object_violation", lambda **kwargs: ValueError()
        )
    elif change == "code":
        monkeypatch.setattr(
            helper,
            "__code__",
            helper.__code__.replace(co_consts=(*helper.__code__.co_consts, "drift")),
        )
    elif change == "globals":
        clone = FunctionType(
            helper.__code__, dict(helper.__globals__), helper.__name__, helper.__defaults__
        )
        monkeypatch.setattr(error_module, "get_hint_object_violation", clone)
    elif change == "defaults":
        monkeypatch.setattr(helper, "__defaults__", (1,) * 5)
    elif change == "state":
        h.original.__globals__["__claw_state_beartype__"] = object()
    elif change == "config_entry":
        state = h.original.__globals__["__claw_state_beartype__"]
        monkeypatch.setitem(state.module_name_to_beartype_conf, h.module.__name__, object())
    else:
        from beartype import BeartypeConf

        foreign = BeartypeConf(is_color=True)
        h.wrapper.__kwdefaults__["__beartype_conf"] = foreign
        h.wrapper.__kwdefaults__["__beartype_check_meta"].conf = foreign
    with pytest.raises(ValueError, match="violation executable|import-hook"):
        stage._method_wrapper_bindings(h.wrapper, h.source.cls)


@pytest.mark.parametrize(
    "change",
    [
        "code",
        "equal_code",
        "delegate",
        "wrapped",
        "kwdefaults",
        "extra_default",
        "metadata_function",
        "metadata_conf",
        "metadata_annotations",
        "class_stack",
        "annotation",
        "globals",
        "cached_builtins",
        "violation",
        "library_bytes",
    ],
)
def test_wrapper_metadata_rejects_changed_live_wrapper_edges(monkeypatch, tmp_path, change):
    h = _wrapped_parameter_metadata("load", monkeypatch)
    before = stage._method_wrapper_bindings(h.wrapper, h.source.cls)
    meta = h.wrapper.__kwdefaults__["__beartype_check_meta"]
    if change in ("code", "equal_code"):
        h.wrapper.__code__ = h.wrapper.__code__.replace(
            **({"co_consts": (*h.wrapper.__code__.co_consts, "drift")} if change == "code" else {})
        )
    elif change == "delegate":
        h.wrapper.__kwdefaults__["__beartype_func"] = lambda: None
    elif change == "wrapped":
        h.wrapper.__wrapped__ = lambda: None
    elif change == "kwdefaults":
        h.wrapper.__kwdefaults__ = dict(h.wrapper.__kwdefaults__)
    elif change == "extra_default":
        h.wrapper.__kwdefaults__["extra"] = None
    elif change == "metadata_function":
        meta.func = lambda: None
    elif change == "metadata_conf":
        meta.conf = object()
    elif change == "metadata_annotations":
        meta.func_annotations = dict(meta.func_annotations)
    elif change == "class_stack":
        meta.cls_stack = (type("Foreign", (), {}),)
    elif change == "annotation":
        h.original.__annotations__["return"] = int
    elif change == "globals":
        monkeypatch.setitem(h.wrapper.__globals__, "isinstance", lambda *args: True)
    elif change == "cached_builtins":
        monkeypatch.setitem(h.wrapper.__globals__, "__builtins__", dict(vars(builtins)))
    elif change == "violation":
        h.wrapper.__kwdefaults__["__beartype_get_violation"] = lambda **kwargs: ValueError()
    else:
        monkeypatch.setattr(
            stage, "RETURN_NONE_WRAPPER_PINS", (("beartype._check.error.errmain", "0" * 64),)
        )
    with pytest.raises(ValueError):
        after = stage._method_wrapper_bindings(h.wrapper, h.source.cls)
        stage.inherited._same(((), after), ((), before))
    save(tmp_path, "wrapper-drift", dict(change=change, original_body_calls=0))


@pytest.mark.parametrize("name", ["load", "reload_paths"])
def test_wrapper_metadata_ignores_no_wrapper_when_authenticating_original_body(name, monkeypatch):
    h = _wrapped_parameter_metadata(name, monkeypatch)
    setattr(h.source.cls, name, h.original)
    assert stage._method_original(h.source, name) is h.original
    h.original.__code__ = h.original.__code__.replace(
        co_consts=(*h.original.__code__.co_consts, 123)
    )
    with pytest.raises(ValueError, match="executable/header/globals"):
        stage._method_original(h.source, name)


@pytest.mark.parametrize(
    "name", ["__init__", "_unload_paths", "load", "reload_paths", "_load_ion_profile"]
)
def test_contextual_metadata_original_class_compilation_without_execution(name):
    path, node, original = _original_parameter_codes()
    actual = stage._method_code(node, name, str(path), native_context=True)
    assert actual == original[name]
    assert actual.co_qualname == "Parameters." + name
    assert actual.co_filename == str(path)
    isolated = compile(
        ast.Module(body=[node], type_ignores=[]), str(path), "exec", dont_inherit=True
    )
    cls = next(c for c in isolated.co_consts if type(c) is CodeType and c.co_name == "Parameters")
    expected_copy = next(c for c in cls.co_consts if type(c) is CodeType and c.co_name == name)
    assert stage._method_code(node, name, str(path)) == expected_copy
    if name in ("__init__", "load", "reload_paths"):
        assert expected_copy.co_code != actual.co_code


@pytest.mark.parametrize("change", ["body", "location", "mode"])
def test_contextual_metadata_original_class_rejects_changed_input(change):
    path, original, _ = _original_parameter_codes()
    node = copy.deepcopy(original)
    if change == "body":
        node.body.pop()
    elif change == "location":
        node.lineno += 1
    with pytest.raises(ValueError, match="compilation context|original class AST"):
        stage._method_code(
            node, "__init__", str(path), native_context=1 if change == "mode" else True
        )


@pytest.mark.parametrize(
    "change",
    [None, "isolated", "constants", "flags", "filename", "qualname", "globals", "class_cell"],
)
def test_contextual_metadata_real_constructor_authentication_without_call(monkeypatch, change):
    path, node, original = _original_parameter_codes()
    module = ModuleType("betse.science.parameters")
    module.__file__ = str(path)
    module.__dict__["__builtins__"] = vars(builtins)
    base = type("YamlFileDefaultABC", (), {})
    cls = type("Parameters", (base,), {"__module__": module.__name__})
    module.Parameters = cls
    for name in ("__init__", "_unload_paths"):
        code = original[name]
        globals_ = vars(module)
        cell_value = cls
        if name == "__init__":
            if change == "isolated":
                code = stage._method_code(node, name, str(path))
            elif change == "constants":
                code = code.replace(co_consts=(*code.co_consts, "foreign constant"))
            elif change == "flags":
                code = code.replace(co_flags=code.co_flags ^ 64)
            elif change == "filename":
                code = code.replace(co_filename="<foreign>")
            elif change == "qualname":
                code = code.replace(co_qualname="Other.__init__")
            elif change == "globals":
                globals_ = dict(vars(module))
            elif change == "class_cell":
                cell_value = base
        closure = tuple(CellType(cell_value) for _ in code.co_freevars) or None
        setattr(cls, name, FunctionType(code, globals_, name, closure=closure))
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(stage.inherited.tissue.aliases, "_check_modules", lambda: None)
    yaml = SimpleNamespace(YamlFileDefaultABC=base)
    if change is None:
        assert stage._canonical(module, yaml) is cls
    else:
        with pytest.raises(ValueError, match="executable changed|closure association"):
            stage._canonical(module, yaml)


@pytest.mark.parametrize("name", paths.VERSIONS)
def test_contextual_metadata_original_function_and_selected_copy_remain_distinct(name):
    path = stage.inherited.tissue.aliases.NATIVE / paths.COMPAT
    tree = ast.parse(path.read_bytes(), filename=str(path))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    expected = next(c for c in module.co_consts if type(c) is CodeType and c.co_name == name)
    assert paths._function(node, str(path), native_context=True) == expected
    isolated = compile(
        ast.Module(body=[node], type_ignores=[]), str(path), "exec", dont_inherit=True
    )
    assert paths._function(node, str(path)) == next(
        c for c in isolated.co_consts if type(c) is CodeType
    )
    changed = copy.deepcopy(node)
    changed.lineno += 1
    with pytest.raises(ValueError, match="original function AST"):
        paths._function(changed, str(path), native_context=True)


def test_native_parameter_owner_is_unloaded_not_phase_or_pickle_parent(controlled):
    import pickle

    owner = birth(controlled)
    with pytest.raises(stage.ParameterRejected) as caught:
        stage.require_loaded(owner)
    assert caught.value.stage == "loaded_parameters_prerequisites"
    assert not caught.value.partial["loaded_or_phase_or_INIT_admitted"]
    for value in (owner, controlled.request):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)


def test_capture_stop_from_source_without_observer_error_is_primary(controlled):
    error = stage.inherited.tissue._CaptureStop()
    controlled.errors["constructor"] = error
    with pytest.raises(stage.ParameterRejected) as caught:
        birth(controlled)
    assert caught.value.source_error is error and caught.value.__cause__ is error
    assert caught.value.capture_errors == () and not caught.value.partial.source_completed


@pytest.mark.parametrize("point", ["import", "constructor"])
@pytest.mark.parametrize("source_failure", [False, True])
def test_inherited_return_observer_preserves_unloaded_source_primary(
    controlled, tmp_path, point, source_failure
):
    h = controlled
    previous, trace = sys.getprofile(), sys.gettrace()
    secondary = SyntheticCaptureFailure("inherited return observer failed")
    secondary_cause = SyntheticSourceCause("observer cause")
    primary = SyntheticSourceFailure("original parameter source failure")
    primary_cause = SyntheticSourceCause("original source cause")
    if source_failure:
        h.errors.update({point: primary, "cause": primary_cause})
    selected = stage._acquire.__code__ if point == "import" else h.cls.__init__.__code__
    invoked = []

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is selected and event == "return":
            invoked.append(arg)
            raise secondary from secondary_cause

    sys.setprofile(inherited)
    try:
        with pytest.raises(stage.ParameterRejected) as caught:
            birth(h)
        failure = caught.value
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
    assert len(invoked) == 1
    assert failure.source_error is (primary if source_failure else None)
    if source_failure:
        assert failure.__cause__ is primary and primary.__cause__ is primary_cause
    else:
        assert failure.__cause__ is secondary
    assert secondary.__cause__ is secondary_cause
    assert failure.capture_errors == (
        ("inherited_profile_" + failure.stage + "_return", secondary),
    )
    context = failure.partial
    partials = [
        value
        for key, value in context.locals.items()
        if len(key) == 3 and key[0].startswith("inherited_profile_")
    ]
    assert len(partials) == 1 and partials[0]
    assert context.source_completed is (point == "constructor" and not source_failure)
    assert h.calls.count("constructor") == (1 if point == "constructor" else 0)
    if point == "constructor":
        assert partials[0]["self"] is h.partial[0]
    else:
        assert partials[0]["source"] is h.source
    assert context.invalid and not context.active and not stage._ACTIVE
    assert all(c is not context for c in stage._ISSUED.values())
    save(
        tmp_path,
        "deferred-return-observer",
        dict(
            point=point,
            source=failure.source_error,
            capture=failure.capture_errors,
            raw_locals=context.locals,
            work=context.work,
            constructor_completed=context.source_completed,
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("point", ["import", "constructor"])
def test_inherited_entry_guard_remains_immediate_for_unloaded_birth(controlled, point):
    h = controlled
    previous, trace = sys.getprofile(), sys.gettrace()
    error = SyntheticSourceFailure("entry guard rejected")
    selected = stage._acquire.__code__ if point == "import" else h.cls.__init__.__code__
    invoked = []

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is selected and event == "call":
            invoked.append(event)
            raise error

    sys.setprofile(inherited)
    try:
        with pytest.raises(stage.ParameterRejected) as caught:
            birth(h)
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
    assert invoked == ["call"]
    assert caught.value.source_error is error and caught.value.__cause__ is error
    assert caught.value.capture_errors == () and not caught.value.partial.source_completed
    assert h.calls.count("constructor") == 0
    assert h.calls.count("import") == (0 if point == "import" else 1)


@pytest.mark.parametrize("point", ["import-source", "constructor-source", "constructor-entry"])
def test_source_capture_stop_plus_return_capture_keeps_exact_primary_and_cause(
    controlled, tmp_path, point
):
    h = controlled
    primary = stage.inherited.tissue._CaptureStop("source or entry primary")
    cause = SyntheticSourceCause("original primary cause")
    secondary = SyntheticCaptureFailure("separate return observation failure")
    secondary_cause = SyntheticSourceCause("separate observation cause")
    previous, trace = sys.getprofile(), sys.gettrace()
    observed = []
    if point != "constructor-entry":
        h.errors.update({point.split("-")[0]: primary, "cause": cause})
        selected = stage._acquire.__code__ if point == "import-source" else h.cls.__init__.__code__
        entry = None
    else:
        # Capture fails on the completed base initialization; the next Child
        # call is refused immediately. Both observations genuinely occur.
        selected = h.source.yaml.__init__.__code__
        cells = dict(
            zip(h.cls.__init__.__code__.co_freevars, h.cls.__init__.__closure__, strict=True)
        )
        entry = cells["Child"].cell_contents.__init__.__code__

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "return" and frame.f_code is selected:
            observed.append("return-capture")
            raise secondary from secondary_cause
        if event == "call" and frame.f_code is entry:
            observed.append("call-entry")
            raise primary from cause

    sys.setprofile(inherited)
    try:
        with pytest.raises(stage.ParameterRejected) as caught:
            birth(h)
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
    failure = caught.value
    context = failure.partial
    assert observed == (
        ["return-capture", "call-entry"] if entry is not None else ["return-capture"]
    )
    assert failure.source_error is primary and failure.__cause__ is primary
    assert primary.__cause__ is cause and secondary.__cause__ is secondary_cause
    assert failure.capture_errors == (
        ("inherited_profile_" + failure.stage + "_return", secondary),
    )
    assert (
        not context.source_completed
        and context.invalid
        and not context.active
        and not stage._ACTIVE
    )
    assert all(issued is not context for issued in stage._ISSUED.values())
    assert h.calls.count("import") == 1
    assert h.calls.count("constructor") == (0 if point == "import-source" else 1)
    if point != "import-source":
        assert context.locals[("synthetic", "constructor")]["self"] is h.partial[0]
    save(
        tmp_path,
        "source-stop-and-return-capture",
        dict(
            primary=failure.source_error,
            capture=failure.capture_errors,
            raw_locals=context.locals,
            work=context.work,
            observation_order=observed,
            source_completed=context.source_completed,
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("field", ["anim", "nested-alias"])
def test_same_layout_same_qualified_name_type_change_refuses_live_owner(
    controlled, tmp_path, field
):
    h = controlled
    owner = birth(h)
    context = stage._ISSUED[owner]
    p = owner.parameters
    value = p.anim if field == "anim" else p.anim.nested
    original_type, original_fields = type(value), vars(value)
    foreign = type(
        original_type.__name__,
        original_type.__bases__,
        {"__module__": original_type.__module__, "__qualname__": original_type.__qualname__},
    )
    assert foreign is not original_type and foreign.__qualname__ == original_type.__qualname__
    assert foreign.__module__ == original_type.__module__
    value.__class__ = foreign
    assert vars(value) is original_fields and vars(value)["_conf"] is None
    if field == "nested-alias":
        assert p.anim.nested is p.visual.same_nested is value
    # The previous string-only graph and the constructor runtime both agree;
    # only the newly retained actual type association rejects this change.
    stage._check(context)
    after = stage._birth_graph(context)
    assert after[1] == context.graph[1]
    assert stage._snapshot(context).identity == context.trial.cache.identity
    assert any(item is foreign for item in after[0])
    assert any(item is original_type for item in context.graph[0])
    with pytest.raises(stage.ParameterRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and context.invalid
    assert h.calls == ["import", "constructor"]
    save(
        tmp_path,
        "actual-type-association",
        dict(
            field=field,
            same_graph_labels=after[1] == context.graph[1],
            class_identity_changed=foreign is not original_type,
            same_layout_dict_retained=vars(value) is original_fields,
            original_type_label=original_type.__module__ + "." + original_type.__qualname__,
            foreign_type_label=foreign.__module__ + "." + foreign.__qualname__,
            graph=after[1],
            trial=context.trial,
            refusal=caught.value,
            synthetic_only=True,
        ),
    )
