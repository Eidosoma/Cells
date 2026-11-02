"""Complete conditional four-store route; original imports/factories blocked."""

import ast
import builtins
import difflib
import importlib
import json
import sys
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_parameter_colormap_load as stage
from tests.unit import test_betse_native_parameter_colormap_state as earlier
from validation.betse import betse_native_parameter_colormap_load_software as software
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

blocked = earlier.blocked
ORIGINAL_REGISTRY_STATE = stage.boundary._registry_state
_GUARD_ATTACHMENT_FAILURES = []  # Forensic fallback, never admission authority.


def _guard_hooks(record, phase, prior, trace, *, set_profile, set_trace, get_profile, get_trace):
    current = dict(profile=object(), trace=object())
    for attempt in range(3):
        for name, setter, expected in (
            ("profile", set_profile, prior),
            ("trace", set_trace, trace),
        ):
            if attempt == 0 or current[name] is not expected:
                try:
                    setter(expected)
                except BaseException as error:
                    record["cleanup_errors"].append((phase + "_restore_" + name, error))
        for name, getter in (("profile", get_profile), ("trace", get_trace)):
            try:
                current[name] = getter()
            except BaseException as error:
                current[name] = object()
                record["cleanup_errors"].append((phase + "_sample_" + name, error))
        record["hook_samples"].append((phase, attempt, current["profile"], current["trace"]))
        if current["profile"] is prior and current["trace"] is trace:
            break
        record["cleanup_errors"].append(
            (phase + "_hook_identity", AssertionError("Both hooks must match"))
        )
    record["final_profile"], record["final_trace"] = current["profile"], current["trace"]


def _guard_attach(record, error):
    if error is not None and not any(error is item for item in record["attachment_attempts"]):
        record["attachment_attempts"].append(error)
        try:
            error.matplotlib_guard = record
        except BaseException as secondary:
            record["cleanup_errors"].append(("primary_attachment", secondary))
            if not any(record is item for item in _GUARD_ATTACHMENT_FAILURES):
                _GUARD_ATTACHMENT_FAILURES.append(record)


def _guard_cleanup(
    primary,
    attempts,
    prior,
    trace,
    write,
    *,
    set_profile=sys.setprofile,
    set_trace=sys.settrace,
    get_profile=sys.getprofile,
    get_trace=sys.gettrace,
):
    """Independently attempt both restores and evidence, retaining all errors."""
    record = dict(
        primary=primary,
        primary_cause=None if primary is None else primary.__cause__,
        attempts=tuple(attempts),
        cleanup_errors=[],
        final_profile=None,
        final_trace=None,
        evidence_persisted=False,
        clean_guard=False,
        attachment_attempts=[],
        hook_samples=[],
    )
    operations = dict(
        set_profile=set_profile, set_trace=set_trace, get_profile=get_profile, get_trace=get_trace
    )
    _guard_hooks(record, "initial", prior, trace, **operations)
    profile_restored = record["final_profile"] is prior
    trace_restored = record["final_trace"] is trace
    if not profile_restored or not trace_restored:
        record["cleanup_errors"].append(
            ("hook_identity", AssertionError("Matplotlib guard hook restoration incomplete"))
        )
    if attempts:
        record["cleanup_errors"].append(
            ("blocked_attempt", AssertionError("Matplotlib guard recorded forbidden attempts"))
        )
    error = (
        primary
        if primary is not None
        else (record["cleanup_errors"][0][1] if record["cleanup_errors"] else None)
    )
    _guard_attach(record, error)
    try:
        write(
            dict(
                attempts=list(record["attempts"]),
                profile_restored=profile_restored,
                trace_restored=trace_restored,
                final_profile_identity=id(record["final_profile"]),
                final_trace_identity=id(record["final_trace"]),
                expected_profile_identity=id(prior),
                expected_trace_identity=id(trace),
                primary_type=None if primary is None else type(primary).__qualname__,
                primary_identity=None if primary is None else id(primary),
                primary_cause_identity=None if primary is None else id(primary.__cause__),
                cleanup_errors=[
                    (name, type(error).__qualname__, str(error))
                    for name, error in record["cleanup_errors"]
                ],
                actual_import_factory_entries=(
                    0 if not attempts and not record["cleanup_errors"] else None
                ),
                # Written before persistence returns; never certify that an
                # errored/partial evidence write completed successfully.
                clean_guard=False,
                certification="Successful cleanup return is also required",
                hook_evidence_phase=(
                    "Before evidence callback; returned final samples also required"
                ),
            )
        )
        record["evidence_persisted"] = True
    except BaseException as error:
        record["cleanup_errors"].append(("guard_evidence", error))
    # Evidence serialization/writing and exception attachment are callbacks.
    # Inspect both hooks *after* them, retain late drift, and recover both.
    for name, getter, expected in (("profile", get_profile, prior), ("trace", get_trace, trace)):
        try:
            actual = getter()
            if actual is not expected:
                record["cleanup_errors"].append(
                    ("post_evidence_" + name, AssertionError("Evidence callback changed a hook"))
                )
        except BaseException as secondary:
            record["cleanup_errors"].append(("post_evidence_" + name, secondary))
    error = (
        primary
        if primary is not None
        else record["cleanup_errors"][0][1]
        if record["cleanup_errors"]
        else None
    )
    _guard_attach(record, error)
    _guard_hooks(record, "final", prior, trace, **operations)
    # A setter may itself supply the first secondary error. Attach it without
    # replacing a primary, then verify both hooks after that callback too.
    if primary is None and error is None and record["cleanup_errors"]:
        error = record["cleanup_errors"][0][1]
        _guard_attach(record, error)
        _guard_hooks(record, "after_attachment", prior, trace, **operations)
    record["clean_guard"] = (
        not attempts
        and not record["cleanup_errors"]
        and record["evidence_persisted"]
        and record["final_profile"] is prior
        and record["final_trace"] is trace
    )
    if primary is None and error is not None:
        raise error
    return record


@contextmanager
def _reference_guard(monkeypatch, tmp_path):
    prior, trace = sys.getprofile(), sys.gettrace()
    attempts = []
    primary = None
    original_import, original_module = builtins.__import__, importlib.import_module

    def no_import(name, *args, **kwargs):
        if name == "matplotlib" or name.startswith("matplotlib."):
            attempts.append(("import", name))
            raise AssertionError("Actual Matplotlib import forbidden")
        return original_import(name, *args, **kwargs)

    def no_module(name, *args, **kwargs):
        if name == "matplotlib" or name.startswith("matplotlib."):
            attempts.append(("import_module", name))
            raise AssertionError("Actual Matplotlib import forbidden")
        return original_module(name, *args, **kwargs)

    def profile(frame, event, arg):
        if event == "call" and frame.f_code.co_filename.startswith(
            str(stage.runtime.SITE / "matplotlib") + "/"
        ):
            attempts.append(("reference_body", frame.f_code.co_qualname))
            raise AssertionError("Actual Matplotlib body forbidden")
        if prior is not None:
            prior(frame, event, arg)

    try:
        monkeypatch.setattr(builtins, "__import__", no_import)
        monkeypatch.setattr(importlib, "import_module", no_module)
        sys.setprofile(profile)
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        # Retain forensic context in this exception traceback frame even if
        # both exception attachment and the evidence writer refused it.
        _guard_record = _guard_cleanup(
            primary,
            attempts,
            prior,
            trace,
            lambda record: (tmp_path / "matplotlib-blocked.json").write_text(json.dumps(record)),
        )


@pytest.fixture(autouse=True)
def prevent_reference_execution(monkeypatch, blocked, tmp_path):
    with _reference_guard(monkeypatch, tmp_path):
        yield


@pytest.fixture
def controlled(monkeypatch, tmp_path, request):
    # This is an explicit conditional metadata model, never library authority.
    original_bindings = stage.boundary._native_bindings

    def registry_state(registry, kind, cm):
        namespace = object.__getattribute__(registry, "__dict__")
        fields = type.__getattribute__(kind, "__dict__")
        surface = (tuple(fields), (kind, cm, *fields.values()))
        return namespace, namespace["_cmaps"], surface

    def native_bindings(api):
        vars(api.registry).setdefault("_cmaps", api.mapping)
        api.registry_namespace, _, api.registry_surface = registry_state(
            api.registry, api.kind, api.cm
        )
        return original_bindings(api)

    monkeypatch.setattr(stage.boundary, "_registry_state", registry_state)
    monkeypatch.setattr(stage.boundary, "_native_bindings", native_bindings)
    h = earlier.controlled.__wrapped__(monkeypatch, tmp_path)
    initialized = getattr(request, "param", False)
    control = dict(
        helper=0,
        checked=0,
        copies=0,
        np_copies=0,
        fail_at=None,
        before=None,
        wrong_return=False,
        duplicate=False,
    )
    primary, cause = (
        SyntheticSourceFailure("conditional source failure"),
        SyntheticSourceCause("cause"),
    )
    api = h.parent.api
    api.mapping[h.parent.names[2]] = h.blue
    if initialized:
        for value in (h.red, h.blue):
            value._isinit = True
            value._lut = np.array([[0.0, 0.25], [0.5, 1.0]], dtype=np.float64)

    def np_copy(a, order="K", subok=False):
        control["np_copies"] += 1
        return np.copy(a, order=order, subok=subok)

    def copy_body(self):
        control["copies"] += 1
        new = object.__new__(type(self))
        vars(new).update(vars(self))
        if self._isinit:
            new._lut = np_copy(self._lut)
        return new

    def copy_method(self):
        return self.__copy__()

    h.colors.Colormap.copy = copy_method
    h.colors.Colormap.__copy__ = copy_body

    def checked(mapping, /, _error_cls=ValueError, **kwargs):
        control["checked"] += 1
        return mapping[kwargs["colormap"]]

    def getter(self, item):
        value = checked(self._cmaps, _error_cls=KeyError, colormap=item)
        return value.copy()

    registry_type = type("ConditionalRegistry", (), {"__getitem__": getter})
    registry = object.__new__(registry_type)
    registry._cmaps = api.mapping
    api.registry, api.kind, api.getter = registry, registry_type, getter

    def helper(name):
        control["helper"] += 1
        if control["helper"] == control["fail_at"]:
            raise primary from cause
        result = registry[name]
        return api.mapping[name] if control["wrong_return"] else result

    def driver(self):
        if control["before"] is not None:
            control["before"]()
        for (field, _, _), name in zip(stage.boundary.ROLES, h.parent.names, strict=True):
            setattr(self, field, helper(name))
        if control["duplicate"]:
            helper(h.parent.names[0])

    api.helper = helper
    monkeypatch.setattr(stage.boundary, "_compile", lambda p: (driver, p.function))
    boundary = h.parent.prepare()
    source = stage.state.capture_registry(boundary, law_id=stage.state.LAW_ID)
    methods = []
    for cls in (h.colors.Colormap, h.colors.LinearSegmentedColormap, h.colors.ListedColormap):
        for name, fn in (("copy", copy_method), ("__copy__", copy_body)):
            methods.append((name, cls, fn, fn, (stage.prefix._function_bindings(fn),)))
    runtime = SimpleNamespace(
        report=dict(verified_files={}),
        methods=tuple(methods),
        checked=checked,
        checked_core=checked,
        checked_bindings=(stage.prefix._function_bindings(checked),),
        api_helpers=(),
        np_copy=np_copy,
        np_core=np_copy,
        np_bindings=(stage.prefix._function_bindings(np_copy),),
        np_dispatcher=np_copy,
        np_dispatcher_bindings=(stage.prefix._function_bindings(np_copy),),
        np_edges=(np_copy,),
        np_exports=(),
    )
    monkeypatch.setattr(stage.runtime, "bind", lambda bound, kinds: runtime)
    monkeypatch.setenv(stage.RELEASE, "1")
    return SimpleNamespace(
        h=h,
        source=source,
        p=h.parent.p,
        control=control,
        runtime=runtime,
        primary=primary,
        cause=cause,
        helper=helper,
        driver=driver,
        run=lambda: stage.prepare(source, law_id=stage.LAW_ID, enabled=True),
    )


def empty():
    earlier.empty()
    assert not stage._ACTIVE
    assert stage._LOCK.acquire(blocking=False)
    stage._LOCK.release()


def test_pinned_reference_is_present_without_import_or_factory():
    report = stage.runtime.inspect_reference()
    assert report["matplotlib"] == "3.11.2" and report["numpy"] == "2.5.3"
    assert len(report["verified_files"]) == len(stage.runtime.PINS) + 2
    assert "matplotlib" not in sys.modules
    plan = stage.source_plan()
    assert plan["source_lines"] == (1007, 1014) and plan["next_line"] == 1017
    assert plan["original_helper_registry_copy_invocation_implemented"]
    fn, _, removed = stage._metadata_code()
    assert fn.__globals__ is vars(stage.mod) and len(removed) == 3
    assert not plan["complete_Parameters_ions_profiles_Simulator_INIT_admitted"]


@pytest.mark.parametrize("gate", ["default", "integer", "local", "parent", "law"])
def test_gates_hold_before_any_parent_runtime_or_work(monkeypatch, gate):
    monkeypatch.setenv(stage.RELEASE, "0" if gate == "local" else "1")
    monkeypatch.setenv(stage.mod.RELEASE, "0" if gate == "parent" else "1")
    enabled = False if gate == "default" else 1 if gate == "integer" else True
    with pytest.raises(stage.ColormapLoadRejected) as caught:
        stage.prepare(None, law_id="foreign" if gate == "law" else stage.LAW_ID, enabled=enabled)
    assert caught.value.stage == ("law" if gate == "law" else "release")
    empty()


@pytest.mark.parametrize("controlled", [False, True], indirect=True)
def test_complete_guarded_conditional_four_stores_same_p_and_real_return_transport(
    controlled, tmp_path
):
    h = controlled
    before = tuple(vars(h.p))
    owner = h.run()
    assert owner.parameters is h.p
    ctx = stage._ISSUED[owner]
    assert ctx.source_completed and ctx.parent.invalid and ctx.source.invalid
    assert tuple(vars(h.p))[len(before) :] == tuple(r[0] for r in stage.boundary.ROLES)
    assert ctx.calls == dict(
        slice=1,
        helper=4,
        registry=4,
        checked=4,
        copy=4,
        copy_body=4,
        np_copy=4 if h.h.red._isinit else 0,
    )
    values = [vars(h.p)[r[0]] for r in stage.boundary.ROLES]
    assert len({id(value) for value in values}) == 4 and values[0] is not values[1]
    assert ctx.raw and len(ctx.returns["helper"]) == 4
    assert owner.trial.source_completed
    with pytest.raises(stage.ColormapLoadRejected) as next_stage:
        stage.require_continuation(owner)
    assert next_stage.value.partial["next_source_line"] == 1017
    with pytest.raises(stage.ColormapLoadRejected) as repeated:
        h.run()
    assert repeated.value.stage == "consumed"
    empty()
    save(
        tmp_path,
        "conditional-complete-four-store",
        dict(
            trial=stage.trial_record(ctx.trial),
            returned_graph=ctx.after.tree,
            arrays=ctx.after.arrays,
            calls=ctx.calls,
            raw_returns=len(ctx.raw),
            metadata_observations=ctx.observations,
            validations=ctx.validations,
            conditional_source_helpers_only=True,
            actual_reference_import_factory_evaluator_entries=0,
            independent_biological_cases=0,
        ),
    )


@pytest.mark.parametrize(
    "kind", ["primary", "capture", "combined", "missing-name", "wrong-return", "duplicate"]
)
def test_source_capture_failures_keep_actual_prefix_primary_and_returns(
    controlled, monkeypatch, tmp_path, kind
):
    h = controlled
    if kind in ("primary", "combined"):
        h.control["fail_at"] = 2
    if kind in ("capture", "combined"):

        def fail(frame):
            if frame.f_code is h.helper.__code__:
                raise SyntheticCaptureFailure("raw locals unavailable")
            return dict(frame.f_locals)

        monkeypatch.setattr(stage, "_copy_locals", fail)
    if kind == "missing-name":
        # Fresh declared missing-key input, not a mutated successful binding.
        del h.h.parent.api.mapping[h.h.parent.names[2]]
        new_boundary = h.h.parent.prepare()
        h.source = stage.state.capture_registry(new_boundary, law_id=stage.state.LAW_ID)
        h.run = lambda: stage.prepare(h.source, law_id=stage.LAW_ID, enabled=True)
    h.control["wrong_return"] = kind == "wrong-return"
    h.control["duplicate"] = kind == "duplicate"
    with pytest.raises((stage.ColormapLoadRejected, ValueError)) as caught:
        h.run()
    ctx = stage._CONSUMED[h.source]
    assert not ctx.active and h.source in stage._CONSUMED
    if kind in ("primary", "combined"):
        assert caught.value.source_error is h.primary and h.primary.__cause__ is h.cause
        assert ctx.source_error is h.primary and ctx.raw
        assert any(role == "helper" and value is None for role, _, value in ctx.raw)
    elif kind == "capture":
        assert ctx.source_completed and ctx.source_error is None and ctx.observation_errors
        assert len(ctx.returns["helper"]) == 4 and ctx.raw
    elif kind == "missing-name":
        assert isinstance(ctx.source_error, KeyError) and len(ctx.returns["helper"]) == 3
        assert [name for name, _, _ in stage.boundary.ROLES if name in vars(h.p)] == [
            "default_cm",
            "background_cm",
        ]
    elif kind != "missing-name":
        assert ctx.invalid and ctx.raw
    assert not hasattr(ctx, "trial")
    empty()
    save(
        tmp_path,
        "conditional-four-store-refusal",
        dict(
            kind=kind,
            source_error=ctx.source_error,
            operation_error=getattr(ctx, "operation_error", None),
            observation_errors=ctx.observation_errors,
            capture_errors=ctx.capture_errors,
            calls=ctx.calls,
            stores=[name for name, _, _ in stage.boundary.ROLES if name in vars(h.p)],
            raw_returns=[(role, value is None) for role, _, value in ctx.raw],
            available_graph=None if ctx.failure_capture is None else ctx.failure_capture.tree,
            actual_reference_entries=0,
            no_success=True,
        ),
    )


@pytest.mark.parametrize(
    "drift", ["old-field", "return-edge", "record", "saved-data", "completion", "accounting"]
)
def test_current_successor_rejects_parameter_return_and_evidence_drift(controlled, drift):
    h = controlled
    owner = h.run()
    assert owner.parameters is h.p
    ctx = stage._ISSUED[owner]
    if drift == "old-field":
        h.p.init_export_dirname = "foreign"
    elif drift == "return-edge":
        h.p.default_cm = h.p.background_cm
    elif drift == "record":
        ctx.trial = replace(ctx.trial)
    elif drift == "completion":
        ctx.source_completed = False
    elif drift == "accounting":
        ctx.work.append(("foreign", "unretained work"))
    else:
        ctx.after.tree["kind"] = "foreign"
    with pytest.raises(stage.ColormapLoadRejected):
        _ = owner.parameters
    assert ctx.invalid
    empty()


@pytest.mark.parametrize("swallow", [False, True])
def test_reentrant_attempt_cannot_double_enter_or_publish_success(controlled, swallow):
    h = controlled
    observed = []

    def nested():
        try:
            h.run()
        except stage.ColormapLoadRejected as error:
            observed.append(error)
            if not swallow:
                raise

    h.control["before"] = nested
    with pytest.raises(stage.ColormapLoadRejected):
        h.run()
    ctx = stage._CONSUMED[h.source]
    assert len(observed) == 1 and observed[0].stage == "reentrant"
    assert ctx.invalid and ctx.calls["helper"] == 0 and not hasattr(ctx, "trial")
    empty()


@pytest.mark.parametrize("location", ["selected-helper", "invoke-boundary"])
def test_inherited_return_unwind_failure_preserves_original_source_cause(controlled, location):
    h = controlled
    h.control["fail_at"] = 2
    prior = sys.getprofile()
    selected = h.helper.__code__ if location == "selected-helper" else stage._invoke.__code__

    def hook(frame, event, arg):
        if frame.f_code is selected and event == "return":
            raise SyntheticCaptureFailure("inherited return observer failed")
        if prior is not None:
            prior(frame, event, arg)

    sys.setprofile(hook)
    try:
        with pytest.raises(stage.ColormapLoadRejected) as caught:
            h.run()
    finally:
        sys.setprofile(prior)
    ctx = caught.value.partial
    assert caught.value.source_error is h.primary and h.primary.__cause__ is h.cause
    assert any(name == "inherited_return" for name, _ in ctx.observation_errors)
    assert ctx.raw and not hasattr(ctx, "trial")
    empty()


def test_lazy_missing_runtime_refuses_before_original_invocation(controlled, monkeypatch):
    h = controlled
    primary = ValueError("Pinned runtime not loaded for this declaration")

    def absent(bound, kinds):
        raise primary

    monkeypatch.setattr(stage.runtime, "bind", absent)
    with pytest.raises(ValueError) as caught:
        h.run()
    ctx = stage._CONSUMED[h.source]
    assert caught.value is primary and primary.colormap_load is ctx
    assert ctx.claim_error is primary and not ctx.retired and not ctx.active
    assert ctx.calls["slice"] == 0 and not any(r[0] in vars(h.p) for r in stage.boundary.ROLES)
    empty()


def _changed_metadata(parent):
    parent.changed_metadata_entered = True
    raise AssertionError("Changed metadata must be rejected before entry")


@pytest.mark.parametrize("when", ["active", "completed"])
@pytest.mark.parametrize("drift", ["code", "function"])
def test_metadata_binding_refuses_changed_body_before_active_or_completed_call(
    controlled, when, drift
):
    h = controlled

    def change(context):
        if drift == "code":
            context.metadata_function.__code__ = _changed_metadata.__code__
        else:
            context.metadata_function = _changed_metadata

    if when == "active":
        h.control["before"] = lambda: change(stage._CONSUMED[h.source])
        with pytest.raises((stage.ColormapLoadRejected, ValueError)):
            h.run()
        context = stage._CONSUMED[h.source]
        assert context.calls["slice"] == 1
    else:
        owner = h.run()
        assert owner.parameters is h.p
        context = stage._ISSUED[owner]
        change(context)
        with pytest.raises(stage.ColormapLoadRejected):
            _ = owner.parameters
    assert not hasattr(context.parent, "changed_metadata_entered")
    assert context.invalid
    empty()


def _api_metadata_model(tmp_path):
    """Define original code objects only; never import/call Matplotlib."""
    native = stage.runtime.SITE / "matplotlib/_api/__init__.py"
    path = tmp_path / "conditional_api.py"
    path.write_bytes(native.read_bytes())
    module = ModuleType("conditional.named_api")
    vars(module).update(__file__=str(path), __builtins__=vars(builtins), difflib=difflib)
    tree = ast.parse(path.read_bytes())
    for name in stage.runtime.REACHED_API_HELPERS:
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        function = FunctionType(stage.boundary._code(node, str(path), name), vars(module), name)
        if name == "getitem_checked":
            function.__kwdefaults__ = {"_error_cls": ValueError}
        vars(module)[name] = function
    return module


@pytest.mark.parametrize("drift", ["missing", "foreign-globals", "wrong-named-body"])
def test_named_missing_name_helper_authenticates_before_any_delegate(tmp_path, drift):
    module = _api_metadata_model(tmp_path)
    valid = stage.runtime._functions(module)
    assert {row[0] for row in valid} == set(stage.runtime.REACHED_API_HELPERS)
    entries = []
    if drift == "missing":
        del module.list_suggestion_error_msg
    elif drift == "foreign-globals":
        text = (
            "def list_suggestion_error_msg(*args):\n"
            "    entries.append('foreign-helper')\n"
            "    raise AssertionError('helper entry held')\n"
        )
        node = ast.parse(text).body[0]
        module.list_suggestion_error_msg = FunctionType(
            stage.boundary._code(node, "conditional_foreign_api.py", node.name),
            dict(__builtins__=vars(builtins), entries=entries),
            node.name,
        )
    else:
        module.list_suggestion_error_msg.__code__ = module.getitem_checked.__code__
    with pytest.raises(
        ValueError, match="(named retained API helper|helper outer executable/globals)"
    ):
        stage.runtime._functions(module)
    assert entries == []


@pytest.mark.parametrize("which", ["public", "implementation-module"])
def test_numpy_copy_export_substitution_refuses_without_any_delegate(which):
    public, module = ModuleType("conditional.numpy"), ModuleType("conditional.numpy.impl")
    entries = []

    def original(*args):
        entries.append("original")
        raise AssertionError("Original delegate call held")

    def foreign(*args):
        entries.append("foreign")
        raise AssertionError("Foreign delegate must not enter")

    public.copy = module.copy = original
    assert stage.runtime._copy_exports(public, module) is original
    if which == "public":
        public.copy = foreign
    else:
        module.copy = foreign
    with pytest.raises(ValueError, match="copy exports differ"):
        stage.runtime._copy_exports(public, module)
    assert entries == []


@pytest.mark.parametrize("drift", ["foreign", "equal-copy", "opaque", "dict-only", "duplicate"])
def test_numpy_argument_delegate_requires_actual_direct_owned_edge(monkeypatch, drift):
    # Synthetic traversal result models C metadata, not actual C construction or
    # copy work. Genuine traversal support remains a runtime prerequisite.
    module, argument, core = _numpy_metadata_model()
    edges = [argument, core, {"__wrapped__": core}]
    sentinel = SimpleNamespace(_implementation=core, __wrapped__=core)
    monkeypatch.setattr(
        stage.runtime, "get_referents", lambda value: edges if value is sentinel else ()
    )
    actual, _, direct = stage.runtime._copy_delegates(sentinel, core, module)
    assert actual is argument and direct == (argument, core)
    if drift == "foreign":
        edges[0] = test_numpy_copy_export_substitution_refuses_without_any_delegate
    elif drift == "equal-copy":
        edges[0] = FunctionType(argument.__code__, vars(module), argument.__name__)
    elif drift == "opaque":
        edges[:] = []
    elif drift == "dict-only":
        edges[:] = [core, {"argument": argument, "__wrapped__": core}]
    else:
        edges.append(argument)
    with pytest.raises(ValueError, match="argument-dispatch ownership is opaque or changed"):
        stage.runtime._copy_delegates(sentinel, core, module)


def _numpy_metadata_model():
    """Compile original declarations only; neither numerical body is called."""
    module = ModuleType("conditional.numpy.impl")
    vars(module).update(__builtins__=vars(builtins), array=np.array)
    path = stage.runtime.SITE / "numpy/lib/_function_base_impl.py"
    nodes = {n.name: n for n in ast.parse(path.read_bytes()).body if isinstance(n, ast.FunctionDef)}
    argument = FunctionType(
        stage.boundary._code(nodes["_copy_dispatcher"], str(path), "_copy_dispatcher"),
        vars(module),
        "_copy_dispatcher",
        (None, None),
    )
    core = FunctionType(
        stage.boundary._code(nodes["copy"], str(path), "copy"), vars(module), "copy", ("K", False)
    )
    module._copy_dispatcher = argument
    return module, argument, core


@pytest.mark.parametrize("helper", ["list_suggestion_error_msg", "_copy_dispatcher"])
def test_undecorated_outer_body_cannot_hide_behind_canonical_wrapped_helper(tmp_path, helper):
    if helper == "list_suggestion_error_msg":
        module = _api_metadata_model(tmp_path)
        original = vars(module)[helper]
        path = Path(vars(module)["__file__"])
    else:
        module, original, _ = _numpy_metadata_model()
        path = stage.runtime.SITE / "numpy/lib/_function_base_impl.py"
    node = next(
        n
        for n in ast.parse(path.read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == helper
    )
    assert stage.boundary._undecorated(original, module, path, node)
    entries = []
    vars(module)["changed_entries"] = entries
    outer_node = ast.parse(
        "def " + helper + "(*args, **kwargs):\n"
        "    changed_entries.append('outer')\n"
        "    raise AssertionError('changed helper entry forbidden')\n"
    ).body[0]
    outer = FunctionType(
        stage.boundary._code(outer_node, "conditional_spoofed_helper.py", helper),
        vars(module),
        helper,
    )
    outer.__wrapped__ = original
    vars(module)[helper] = outer
    with pytest.raises(ValueError, match="undecorated helper outer"):
        stage.boundary._undecorated(outer, module, path, node)
    if helper == "list_suggestion_error_msg":
        with pytest.raises(ValueError, match="undecorated helper outer"):
            stage.runtime._functions(module)
    assert entries == []


@pytest.mark.parametrize("drift", ["positional", "keyword", "wrapped"])
def test_undecorated_helper_defaults_and_delegates_are_exact(tmp_path, drift):
    if drift == "keyword":
        module = _api_metadata_model(tmp_path)
        function = module.getitem_checked
        path = Path(vars(module)["__file__"])
        name = "getitem_checked"
    else:
        module, function, _ = _numpy_metadata_model()
        path = stage.runtime.SITE / "numpy/lib/_function_base_impl.py"
        name = "_copy_dispatcher"
    node = next(
        n
        for n in ast.parse(path.read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    assert stage.boundary._undecorated(function, module, path, node)
    if drift == "positional":
        function.__defaults__ = (None,)
    elif drift == "keyword":
        function.__kwdefaults__ = {"_error_cls": KeyError}
    else:
        function.__wrapped__ = function
    with pytest.raises(ValueError, match="undecorated helper"):
        stage.boundary._undecorated(function, module, path, node)


@pytest.mark.parametrize("drift", ["valid", "swapped", "wrapped-only", "swapped-and-wrapped"])
def test_numpy_actual_implementation_role_is_distinct_from_unordered_gc_membership(
    monkeypatch, drift
):
    module, argument, core = _numpy_metadata_model()
    value = SimpleNamespace(_implementation=core, __wrapped__=core)
    monkeypatch.setattr(stage.runtime, "get_referents", lambda obj: (core, argument))
    if drift in ("swapped", "swapped-and-wrapped"):
        value._implementation = argument
    if drift in ("wrapped-only", "swapped-and-wrapped"):
        value.__wrapped__ = argument
    if drift == "valid":
        assert stage.runtime._copy_delegates(value, core, module)[0] is argument
    else:
        with pytest.raises(ValueError, match="C implementation role changed"):
            stage.runtime._copy_delegates(value, core, module)


def _registry_metadata_model():
    entries = []

    def forbidden(*args):
        entries.append("registry-dispatch")
        raise AssertionError("Registry source/descriptor must remain unentered")

    cm = ModuleType("conditional.registry_metadata")
    cm.Mapping = Mapping
    kind = type(
        "ColormapRegistry",
        (Mapping,),
        dict(__module__=cm.__name__, __getitem__=forbidden, __iter__=forbidden, __len__=forbidden),
    )
    cm.ColormapRegistry = kind
    registry = object.__new__(kind)
    namespace = object.__getattribute__(registry, "__dict__")
    namespace["_cmaps"] = {"declared": object()}
    namespace["_builtin_cmaps"] = ("declared",)
    return SimpleNamespace(
        cm=cm, kind=kind, registry=registry, namespace=namespace, entries=entries
    )


@pytest.mark.parametrize("where", ["metadata", "load-entry"])
@pytest.mark.parametrize("drift", ["getattribute", "descriptor", "getattr", "mro", "getter-code"])
def test_registry_dispatch_retarget_refuses_before_attribute_or_load_entry(
    monkeypatch, where, drift
):
    h = _registry_metadata_model()
    namespace, mapping, surface = ORIGINAL_REGISTRY_STATE(h.registry, h.kind, h.cm)
    assert namespace is h.namespace and mapping is namespace["_cmaps"]
    api = SimpleNamespace(
        registry=h.registry,
        kind=h.kind,
        cm=h.cm,
        mapping=mapping,
        registry_namespace=namespace,
        registry_surface=surface,
    )
    p, source = object(), object()
    context = SimpleNamespace(
        invalid=False,
        guard=SimpleNamespace(invalid=False),
        thread=stage.get_ident(),
        active=True,
        retired=True,
        source_owner=source,
        p=p,
        parent=SimpleNamespace(p=p, invalid=True),
        bound=SimpleNamespace(api=api),
        calls={"slice": 0},
    )
    monkeypatch.setattr(stage, "_CONSUMED", {source: context})
    monkeypatch.setattr(stage, "_stacks", lambda _: (([context], context),))
    if drift == "getattribute":
        h.kind.__getattribute__ = h.kind.__getitem__
    elif drift == "descriptor":
        h.kind._cmaps = property(h.kind.__getitem__)
    elif drift == "getattr":
        h.kind.__getattr__ = h.kind.__getitem__
    elif drift == "mro":

        class ForeignMapping(Mapping):
            __slots__ = ()

        h.kind.__bases__ = (ForeignMapping,)
    else:
        # Same callable, a new executable code identity; no changed body call.
        function = h.kind.__getitem__
        function.__code__ = function.__code__.replace(co_name="changed_registry")
    with pytest.raises(ValueError):
        if where == "metadata":
            _, _, now = ORIGINAL_REGISTRY_STATE(h.registry, h.kind, h.cm)
            stage.prefix.parameters.inherited._same(now, surface)
        else:
            stage._entry(context, "slice", SimpleNamespace(f_locals={"self": p}))
    assert h.entries == [] and context.calls == {"slice": 0}
    assert object.__getattribute__(h.registry, "__dict__") is namespace
    assert namespace["_cmaps"] is mapping


def test_registry_rechecks_surface_after_inherited_call_hook(controlled, monkeypatch):
    h = controlled
    api = h.h.parent.api
    selected, prior, entries = api.getter.__code__, sys.getprofile(), []

    def foreign(*args):
        entries.append("foreign_attribute_dispatch")
        raise AssertionError("Foreign registry attribute dispatch forbidden")

    def hook(frame, event, arg):
        if frame.f_code is selected and event == "call":
            monkeypatch.setattr(api.kind, "__getattribute__", foreign)
        if prior is not None:
            prior(frame, event, arg)

    sys.setprofile(hook)
    try:
        with pytest.raises(stage.ColormapLoadRejected) as caught:
            h.run()
    finally:
        sys.setprofile(prior)
    context = stage._CONSUMED[h.source]
    assert context.calls["registry"] == 1 and context.calls["checked"] == 0
    assert caught.value.source_error is context.source_error
    assert isinstance(context.source_error, ValueError) and context.invalid
    assert entries == [] and not hasattr(context, "trial")
    empty()


@pytest.mark.parametrize("drift", ["getattribute", "mapping-descriptor"])
def test_inherited_getter_line_mutation_refuses_before_foreign_attribute_body(
    controlled, monkeypatch, drift
):
    h = controlled
    api = h.h.parent.api
    before_namespace = object.__getattribute__(api.registry, "__dict__")
    before_mapping, getter_code = api.mapping, api.getter.__code__
    prior, foreign_entries, mutations = sys.gettrace(), [], []

    def foreign(*args):
        foreign_entries.append(args)
        return before_mapping  # Equal mapping/cache is not dispatch authority.

    def line_trace(frame, event, arg):
        if frame.f_code is getter_code and event == "line" and not mutations:
            mutations.append((frame, frame.f_lineno))
            if drift == "getattribute":
                monkeypatch.setattr(api.kind, "__getattribute__", foreign)
            else:
                monkeypatch.setattr(api.kind, "_cmaps", property(foreign), raising=False)
        return line_trace

    sys.settrace(line_trace)
    try:
        with pytest.raises(stage.ColormapLoadRejected) as caught:
            h.run()
    finally:
        sys.settrace(prior)
    context = stage._CONSUMED[h.source]
    assert mutations and foreign_entries == [] and context.invalid
    assert isinstance(caught.value.source_error, ValueError)
    assert context.calls["checked"] == 0 and context.trace_observations
    assert api.getter.__code__ is getter_code and api.mapping is before_mapping
    assert object.__getattribute__(api.registry, "__dict__") is before_namespace
    assert any(name.startswith("registry_trace_") for name, _ in context.observation_errors)
    empty()


def test_inherited_trace_unwind_error_retains_actual_primary_and_cause(controlled):
    h = controlled
    h.control["fail_at"] = 2
    prior = sys.gettrace()

    def line_trace(frame, event, arg):
        if frame.f_code is h.helper.__code__ and event == "return" and h.control["helper"] == 2:
            raise SyntheticCaptureFailure("trace unwind observation refused")
        return line_trace

    sys.settrace(line_trace)
    try:
        with pytest.raises(stage.ColormapLoadRejected) as caught:
            h.run()
    finally:
        sys.settrace(prior)
    context = caught.value.partial
    assert caught.value.source_error is h.primary and h.primary.__cause__ is h.cause
    assert any(name == "inherited_trace_return" for name, _ in context.observation_errors)
    assert context.raw and context.invalid


@pytest.mark.parametrize("failed", ["profile", "trace", "evidence", "all"])
@pytest.mark.parametrize("has_primary", [False, True])
def test_matplotlib_guard_cleanup_keeps_primary_and_all_independent_attempts(failed, has_primary):
    prior, trace, active_profile, active_trace = object(), object(), object(), object()
    hooks = dict(profile=active_profile, trace=active_trace)
    calls, written, attempts = [], [], [("reference_body", "deliberately_blocked")]
    cause = SyntheticSourceCause("original cause")
    primary = SyntheticSourceFailure("original blocked operation") if has_primary else None
    if primary is not None:
        primary.__cause__ = cause

    def restore(name, value):
        calls.append(name)
        if failed in (name, "all"):
            raise SyntheticCaptureFailure("secondary " + name)
        hooks[name] = value

    def write(value):
        calls.append("evidence")
        written.append(value)
        if failed in ("evidence", "all"):
            raise OSError("secondary evidence failure")

    def cleanup():
        return _guard_cleanup(
            primary,
            attempts,
            prior,
            trace,
            write,
            set_profile=lambda value: restore("profile", value),
            set_trace=lambda value: restore("trace", value),
            get_profile=lambda: hooks["profile"],
            get_trace=lambda: hooks["trace"],
        )

    if primary is None:
        with pytest.raises((SyntheticCaptureFailure, OSError)) as caught:
            cleanup()
        record = caught.value.matplotlib_guard
    else:
        record = cleanup()
        assert primary.matplotlib_guard is record
        assert record["primary"] is primary and primary.__cause__ is cause
    at = calls.index("evidence")
    assert "profile" in calls[:at] and "trace" in calls[:at]
    assert "profile" in calls[at + 1 :] and "trace" in calls[at + 1 :]
    assert record["attempts"] == tuple(attempts) and not record["clean_guard"]
    assert record["final_profile"] is hooks["profile"]
    assert record["final_trace"] is hooks["trace"]
    assert not written[0]["clean_guard"]
    assert written[0]["actual_import_factory_entries"] is None
    assert record["evidence_persisted"] is (failed not in ("evidence", "all"))
    expected = "restore_" + failed if failed in ("profile", "trace") else "guard_evidence"
    assert any(name.endswith(expected) for name, _ in record["cleanup_errors"])


def test_matplotlib_guard_unchanged_valid_cleanup_requires_evidence_return():
    prior, trace = object(), object()
    hooks, written = dict(profile=object(), trace=object()), []
    record = _guard_cleanup(
        None,
        [],
        prior,
        trace,
        written.append,
        set_profile=lambda value: hooks.update(profile=value),
        set_trace=lambda value: hooks.update(trace=value),
        get_profile=lambda: hooks["profile"],
        get_trace=lambda: hooks["trace"],
    )
    assert record["clean_guard"] and record["evidence_persisted"]
    assert record["cleanup_errors"] == [] and written[0]["attempts"] == []


def test_guard_attachment_rejection_preserves_exact_primary_and_secondary_failure():
    class AttachmentRefused(SyntheticSourceFailure):
        def __setattr__(self, name, value):
            if name == "matplotlib_guard":
                raise OSError("exception attachment refused")
            super().__setattr__(name, value)

    primary, cause = AttachmentRefused("original"), SyntheticSourceCause("cause")
    primary.__cause__ = cause
    prior, trace = object(), object()
    hooks, written = dict(profile=object(), trace=object()), []
    record = _guard_cleanup(
        primary,
        [("import", "blocked")],
        prior,
        trace,
        written.append,
        set_profile=lambda value: hooks.update(profile=value),
        set_trace=lambda value: hooks.update(trace=value),
        get_profile=lambda: hooks["profile"],
        get_trace=lambda: hooks["trace"],
    )
    assert record["primary"] is primary and primary.__cause__ is cause
    assert any(name == "primary_attachment" for name, _ in record["cleanup_errors"])
    assert any(record is item for item in _GUARD_ATTACHMENT_FAILURES)
    assert any(name == "primary_attachment" for name, _, _ in written[0]["cleanup_errors"])
    assert hooks["profile"] is prior and hooks["trace"] is trace and not record["clean_guard"]


@pytest.mark.parametrize("which", ["profile", "trace", "both"])
@pytest.mark.parametrize("primary_present", [False, True])
def test_guard_writer_hook_changes_are_recovered_after_callback_and_never_clean(
    which, primary_present
):
    primary = SyntheticSourceFailure("original") if primary_present else None
    cause = SyntheticSourceCause("cause")
    if primary is not None:
        primary.__cause__ = cause
    prior, trace = object(), object()
    hooks, actions = dict(profile=object(), trace=object()), []

    def restore(name, value):
        actions.append("restore_" + name)
        hooks[name] = value

    def write(value):
        actions.append("write")
        if which in ("profile", "both"):
            hooks["profile"] = None
        if which in ("trace", "both"):
            hooks["trace"] = None

    def cleanup():
        return _guard_cleanup(
            primary,
            [],
            prior,
            trace,
            write,
            set_profile=lambda value: restore("profile", value),
            set_trace=lambda value: restore("trace", value),
            get_profile=lambda: hooks["profile"],
            get_trace=lambda: hooks["trace"],
        )

    if primary is None:
        with pytest.raises(AssertionError) as caught:
            cleanup()
        record = caught.value.matplotlib_guard
    else:
        record = cleanup()
        assert primary.matplotlib_guard is record and primary.__cause__ is cause
    after = actions[actions.index("write") + 1 :]
    assert "restore_profile" in after and "restore_trace" in after
    assert record["final_profile"] is prior and record["final_trace"] is trace
    assert hooks["profile"] is prior and hooks["trace"] is trace
    assert not record["clean_guard"] and record["evidence_persisted"]
    assert any(name.startswith("post_evidence_") for name, _ in record["cleanup_errors"])


def test_nested_matplotlib_guard_blocks_real_import_attempt_and_retains_primary(
    monkeypatch, tmp_path
):
    prior, trace = sys.getprofile(), sys.gettrace()
    output = tmp_path / "nested-guard"
    output.mkdir()
    name = "matplotlib.__blocked_guard_control"
    with monkeypatch.context() as nested:
        with pytest.raises(AssertionError, match="Matplotlib import forbidden") as caught:
            with _reference_guard(nested, output):
                builtins.__import__(name)
    record = caught.value.matplotlib_guard
    assert record["primary"] is caught.value
    assert record["attempts"] == (("import", name),)
    assert not record["clean_guard"] and record["evidence_persisted"]
    assert sys.getprofile() is prior and sys.gettrace() is trace
    assert name not in sys.modules
    written = json.loads((output / "matplotlib-blocked.json").read_text())
    assert written["attempts"] == [["import", name]] and not written["clean_guard"]


@pytest.mark.parametrize("target", [None, "", "foreign", 1])
def test_runner_refuses_missing_or_foreign_target_before_worker(monkeypatch, tmp_path, target):
    def forbidden(*args, **kwargs):
        raise AssertionError("Worker/delegate must not be reached")

    monkeypatch.setattr(software.callbacks, "delegate", forbidden)
    with pytest.raises(ValueError, match="declared bounded software target"):
        software.software(tmp_path / "packet", tmp_path / "output", target=target)
    assert not (tmp_path / "output").exists()


def test_runner_forwards_one_declared_target_to_existing_guard_and_child(monkeypatch, tmp_path):
    target = software.TARGETS[0]
    observed = []

    def guarded(command, **kwargs):
        observed.append((command, kwargs))
        return 17

    def delegate(function, **changes):
        if function is software.inherited.child:
            assert changes == dict(TEST=software.TEST + "::" + target)
            return lambda output: 19
        assert function is software.inherited.software and changes["FILE"] == software.FILE
        return lambda packet, output: changes["guard"].run_bounded(
            ["python", "--child", str(output)], retained_marker=packet
        )

    monkeypatch.setattr(software.callbacks, "delegate", delegate)
    monkeypatch.setattr(software.inherited.guard, "run_bounded", guarded)
    assert software.child(tmp_path, target=target) == 19
    assert software.software("packet", tmp_path, target=target) == 17
    assert observed == [
        (["python", "--child", str(tmp_path), "--target", target], dict(retained_marker="packet"))
    ]
