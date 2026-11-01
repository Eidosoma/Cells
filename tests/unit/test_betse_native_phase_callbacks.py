"""Blocked callback-authority controls, not actual native factory execution."""

import ast
import builtins
import json
import sys
from dataclasses import replace
from types import FunctionType, SimpleNamespace

import pytest

from cells.processes import betse_native_phase_callbacks as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


@pytest.fixture(autouse=True)
def native_blocked(monkeypatch, request, tmp_path):
    attempted, extra = [], set()
    previous, trace, original_import = sys.getprofile(), sys.gettrace(), builtins.__import__
    codes = {
        stage.simulator._acquire_native.__code__,
        stage.simulator.prepare.__code__,
        stage.simulator.tissue.prepare.__code__,
        stage.simulator.tissue._native_setup.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code in extra
            or frame.f_code.co_filename.startswith(str(stage.simulator.tissue.aliases.NATIVE) + "/")
        ):
            attempted.append((frame.f_code.co_filename, frame.f_code.co_name))
            raise AssertionError("Actual native factory/constructor/source work forbidden")
        if previous is not None:
            previous(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name == "betse" or name.startswith("betse."):
            attempted.append(("import", name))
            raise AssertionError("Actual native import forbidden")
        return original_import(name, *args, **kwargs)

    def rng(*args, **kwargs):
        attempted.append(("RNG", "numpy.random"))
        raise AssertionError("Actual RNG forbidden")

    monkeypatch.setattr(builtins, "__import__", imports)
    for name in (
        "RandomState",
        "default_rng",
        "seed",
        "random",
        "rand",
        "normal",
        "uniform",
        "choice",
    ):
        monkeypatch.setattr(stage.simulator.tissue.callers.np.random, name, rng)
    sys.setprofile(profile)
    try:
        yield extra
        assert attempted == [] and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempted,
                    actual_native_or_RNG_entries=0,
                    synthetic_only=True,
                )
            )
        )


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, plan):
    calls, hooks, errors = [], {}, {}
    parent = object.__new__(stage.simulator.SimulatorOwner)
    app = SimpleNamespace(_is_libs_initted=True)
    filename = str(stage.simulator.tissue.aliases.NATIVE / stage.APP)
    tissue = SimpleNamespace(
        trial=SimpleNamespace(source_completed=True),
        locals={(filename, "AppMetaABC.__init__"): dict(self=app)},
        work=[
            dict(
                source_file=filename,
                method="AppMetaABC.__init__",
                phase="native_factory_descriptor_setup",
            )
        ],
    )
    source_parent = SimpleNamespace(
        parent=tissue,
        p=SimpleNamespace(_conf={"synthetic": True}),
        handler=SimpleNamespace(),
        instance=SimpleNamespace(),
        trial=SimpleNamespace(identity="synthetic-simulator"),
    )

    def parent_owner(value):
        if value is not parent:
            raise stage.simulator.ConstructionRejected("Foreign synthetic parent", stage="owner")
        return source_parent

    monkeypatch.setattr(stage.simulator, "_validate", parent_owner)
    mode = [False]

    def target():
        calls.append("testing-body")
        return mode[0]

    def testing():
        calls.append("testing-wrapper")
        if stage.CACHE not in vars(target):
            setattr(target, stage.CACHE, target())
        return vars(target)[stage.CACHE]

    testing.__wrapped__ = target

    class Base:
        def __init__(self):
            calls.append("callback-init")
            self._clear_progress()
            if "callback" in errors:
                raise errors["callback"] from errors.get("cause")

        def _clear_progress(self):
            self._progress_min = None
            self._progress_max = None
            self._progress_next = None

    class BC(Base):
        pass

    class Noop(BC):
        pass

    def maker():
        calls.append("factory")
        if "factory" in hooks:
            hooks["factory"]()
        if "factory" in errors:
            raise errors["factory"] from errors.get("cause")
        value = BC() if testing() else Noop()
        return None if hooks.get("none_return") else value

    callbacks = SimpleNamespace(make_default=maker, SimCallbacksBC=BC, SimCallbacksNoop=Noop)
    base = SimpleNamespace(CallbacksBC=Base)
    one = SimpleNamespace(_app_meta=app)
    modules = {name: SimpleNamespace() for name in stage.MODULES}
    modules[stage.MODULES[0]] = callbacks
    modules[stage.MODULES[1]] = base
    modules[stage.MODULES[2]] = one
    modules[stage.MODULES[4]] = SimpleNamespace(is_testing=testing)

    def acquire(value):
        context, actual_app = stage._application(value)
        if one._app_meta is not actual_app or vars(actual_app).get("_is_libs_initted") is not True:
            raise stage.CallbackRejected(
                "Synthetic current singleton changed", stage="application_association"
            )
        return SimpleNamespace(
            parent=context,
            app=actual_app,
            modules=modules,
            callbacks=callbacks,
            base=base,
            testing=modules[stage.MODULES[4]],
            target=target,
            cache=stage._cache(target),
        )

    monkeypatch.setattr(stage, "_acquire", acquire)
    monkeypatch.setattr(stage, "source_plan", lambda: dict(plan, synthetic_only=True))
    monkeypatch.setenv(stage.simulator.RELEASE, "1")
    return SimpleNamespace(
        parent=parent,
        source_parent=source_parent,
        tissue=tissue,
        app=app,
        one=one,
        mode=mode,
        target=target,
        testing=testing,
        callbacks=callbacks,
        base=base,
        calls=calls,
        hooks=hooks,
        errors=errors,
        request=lambda: stage.from_simulator(parent, law_id=stage.LAW_ID),
    )


def prepare(h):
    return stage.prepare(h.request(), enabled=True)


def test_source_scope_retains_frozen_simulator_and_explicit_callback_route(plan):
    assert plan["simulator_sha256"] == stage.SIMULATOR_SHA256
    assert len(plan["native_pins"]) == 272 and len(plan["phase_prerequisites"]) == 4
    assert "explicit prepared" in plan["mode"]
    assert not plan["full_application_or_phase_or_INIT_or_checkpoint_authority"]


@pytest.mark.parametrize("enabled,environment", [(False, "0"), (True, "0"), (False, "1"), (1, "1")])
def test_release_precedes_any_source_authority(enabled, environment, monkeypatch):
    monkeypatch.setenv(stage.simulator.RELEASE, environment)
    with pytest.raises(stage.CallbackRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.simulator.SimulatorOwner)]
)
def test_actual_provider_never_promotes_receipts_or_unissued_parent(value):
    with pytest.raises(stage.simulator.ConstructionRejected, match="Issued actual Simulator owner"):
        stage.from_simulator(value, law_id=stage.LAW_ID)


@pytest.mark.parametrize(
    "mutation",
    ["missing", "self", "duplicate", "stage", "incomplete", "singleton", "uninitialized"],
)
def test_application_source_observation_and_current_singleton_required(controlled, mutation):
    h = controlled
    # These are explicit synthetic observation mutations, never native records.
    if mutation == "missing":
        h.tissue.locals.clear()
    elif mutation == "self":
        next(iter(h.tissue.locals.values())).clear()
    elif mutation == "duplicate":
        h.tissue.work.append(dict(h.tissue.work[0]))
    elif mutation == "stage":
        h.tissue.work[0]["phase"] = "foreign"
    elif mutation == "incomplete":
        h.tissue.trial.source_completed = False
    elif mutation == "singleton":
        h.one._app_meta = SimpleNamespace(**vars(h.app))
    else:
        h.app._is_libs_initted = False
    with pytest.raises(stage.CallbackRejected) as caught:
        h.request()
    assert caught.value.stage == (
        "application_association"
        if mutation in ("singleton", "uninitialized")
        else "application_observation"
    )
    assert h.calls == []


@pytest.mark.parametrize(
    "cached,mode", [(False, False), (False, True), (True, False), (True, True)]
)
def test_preserves_existing_cache_or_records_actual_new_cache_without_replay(
    controlled, tmp_path, cached, mode
):
    h = controlled
    h.mode[0] = mode
    if cached:
        setattr(h.target, stage.CACHE, mode)
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    assert type(owner.callback) is (
        h.callbacks.SimCallbacksBC if mode else h.callbacks.SimCallbacksNoop
    )
    assert vars(owner.callback) == dict(_progress_min=None, _progress_max=None, _progress_next=None)
    assert h.calls.count("factory") == h.calls.count("callback-init") == 1
    assert h.calls.count("testing-body") == (0 if cached else 1)
    assert request.cache_before == (cached, mode if cached else None)
    assert stage._cache(h.target) == (True, mode)
    assert owner.trial.factory_completed
    with pytest.raises(stage.CallbackRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.stage == "consumed"
    with pytest.raises(stage.CallbackRejected) as caught:
        stage.prepare(h.request(), enabled=True)
    assert caught.value.stage == "consumed" and h.calls.count("factory") == 1
    save(
        tmp_path,
        "constructed",
        dict(trial=owner.trial, graph=stage._ISSUED[owner].graph[1], synthetic_only=True),
    )


@pytest.mark.parametrize("bad", [None, 0, 1, 0.0, "False"])
def test_native_testing_cache_is_exact_bool_without_normalization(controlled, bad):
    setattr(controlled.target, stage.CACHE, bad)
    with pytest.raises(ValueError, match="actual bool"):
        controlled.request()
    assert controlled.calls == []


def test_cache_epoch_and_copied_request_refuse_before_factory(controlled):
    h = controlled
    request = h.request()
    with pytest.raises(stage.CallbackRejected) as caught:
        stage.prepare(replace(request), enabled=True)
    assert caught.value.stage == "request"
    setattr(h.target, stage.CACHE, False)
    with pytest.raises(stage.CallbackRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.source_error.stage == "cache_epoch" and h.calls == []


@pytest.mark.parametrize("point", ["factory", "callback"])
def test_actual_profile_unwind_retains_original_primary_cause_and_partial(
    controlled, tmp_path, point
):
    h = controlled
    request = h.request()
    error, cause = (
        SyntheticSourceFailure("synthetic source failure"),
        SyntheticSourceCause("source cause"),
    )
    h.errors.update({point: error, "cause": cause})
    with pytest.raises(stage.CallbackRejected) as caught:
        stage.prepare(request, enabled=True)
    e = caught.value
    assert e.source_error is error and e.__cause__ is error and error.__cause__ is cause
    assert e.capture_errors == () and not e.partial.factory_completed
    assert any(row["classification"] == "return_or_unwind" for row in e.partial.observations)
    if point == "callback":
        assert type(e.partial.partial_callback) is h.callbacks.SimCallbacksNoop
    assert not stage._ACTIVE
    save(
        tmp_path,
        "source-failed",
        dict(
            primary=error,
            locals=e.partial.raw_locals,
            work=e.partial.work,
            partial=e.partial.partial_callback,
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("source_failure", [False, True])
def test_source_vs_capture_errors_and_completed_partial_remain_separate(
    controlled, monkeypatch, tmp_path, source_failure
):
    h = controlled
    request = h.request()
    capture = SyntheticCaptureFailure("observation failed")

    def broken(frame):
        raise capture

    monkeypatch.setattr(stage, "_copy_locals", broken)
    if source_failure:
        h.errors["factory"] = SyntheticSourceFailure("original failed")
    with pytest.raises(stage.CallbackRejected) as caught:
        stage.prepare(request, enabled=True)
    e = caught.value
    assert e.source_error is h.errors.get("factory")
    assert e.capture_errors and all(err is capture for _, err in e.capture_errors)
    assert e.__cause__ is (h.errors["factory"] if source_failure else capture)
    assert e.partial.factory_completed is (not source_failure)
    save(
        tmp_path,
        "capture-incomplete",
        dict(
            source=e.source_error,
            capture=e.capture_errors,
            work=e.partial.work,
            completed=e.partial.factory_completed,
            synthetic_only=True,
        ),
    )


def test_normal_none_result_refuses_at_association_without_observer_valueerror(controlled):
    h = controlled
    h.hooks["none_return"] = True
    with pytest.raises(stage.CallbackRejected) as caught:
        prepare(h)
    e = caught.value
    assert e.stage == "post_factory_association" and isinstance(e.source_error, ValueError)
    assert e.capture_errors == () and e.partial.factory_completed and e.partial.callback is None
    assert e.partial.partial_callback is not None


@pytest.mark.parametrize("swallow", [False, True])
def test_reentry_is_one_factory_and_original_failure_or_unaccepted_callback(controlled, swallow):
    h = controlled
    request = h.request()
    nested = []

    def reenter():
        try:
            stage.prepare(request, enabled=True)
        except stage.CallbackRejected as e:
            nested.append(e)
            if not swallow:
                raise

    h.hooks["factory"] = reenter
    with pytest.raises(stage.CallbackRejected) as caught:
        stage.prepare(request, enabled=True)
    assert len(nested) == 1 and nested[0].stage == "reentrant"
    assert h.calls.count("factory") == 1 and caught.value.partial.invalid and not stage._ACTIVE
    if not swallow:
        assert caught.value.source_error is nested[0]
    else:
        assert caught.value.partial.factory_completed and caught.value.partial.callback is not None


@pytest.mark.parametrize(
    "mutation",
    ["singleton", "cache", "callback", "progress", "maker", "kwdefault", "global", "graph"],
)
def test_live_callback_owner_rejects_parent_runtime_cache_and_alias_drift(controlled, mutation):
    h = controlled
    owner = prepare(h)
    context = stage._ISSUED[owner]
    if mutation == "singleton":
        h.one._app_meta = SimpleNamespace(**vars(h.app))
    elif mutation == "cache":
        setattr(h.target, stage.CACHE, True)
    elif mutation == "callback":
        context.callback = object.__new__(h.callbacks.SimCallbacksNoop)
    elif mutation == "progress":
        context.callback._progress_next = 1
    elif mutation == "maker":
        f = h.callbacks.make_default
        h.callbacks.make_default = FunctionType(
            f.__code__, f.__globals__, f.__name__, f.__defaults__, f.__closure__
        )
    elif mutation == "kwdefault":
        h.callbacks.make_default.__kwdefaults__ = {"foreign": None}
    elif mutation == "global":
        context.runtime = (context.runtime[0] + ("foreign-global",), context.runtime[1])
    else:
        context.view.parameters = SimpleNamespace(**vars(context.view.parameters))
    with pytest.raises(stage.CallbackRejected) as caught:
        _ = owner.callback
    assert caught.value.stage == "owner_drift" and context.invalid and h.calls.count("factory") == 1


def test_inherited_profiler_primary_and_identity_restoration(controlled):
    h = controlled
    request = h.request()
    old, trace = sys.getprofile(), sys.gettrace()
    error = SyntheticSourceFailure("inherited profiler failure")

    def inherited(frame, event, arg):
        if old is not None:
            old(frame, event, arg)
        if event == "call" and frame.f_code is h.callbacks.make_default.__code__:
            raise error

    sys.setprofile(inherited)
    try:
        with pytest.raises(stage.CallbackRejected) as caught:
            stage.prepare(request, enabled=True)
        assert caught.value.source_error is error and caught.value.__cause__ is error
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        sys.setprofile(old)


def test_callback_owner_cannot_become_phase_or_pickle_input(controlled):
    import pickle

    h = controlled
    owner = prepare(h)
    with pytest.raises(stage.CallbackRejected) as caught:
        stage.require_phase(owner)
    assert caught.value.stage == "phase_prerequisites"
    assert not caught.value.partial["phase_or_INIT_or_checkpoint_admitted"]
    for value in (owner, h.request()):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)


def test_native_cache_template_reflection_is_no_call_and_target_identity_exact(native_blocked):
    tree = ast.parse((stage.simulator.tissue.aliases.NATIVE / stage.MEMO).read_bytes())
    factory = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "func_cached"
    )
    assign = next(
        n
        for n in factory.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "func_body" for t in n.targets)
    )
    node = next(
        n
        for n in ast.parse(assign.value.func.value.value.format(callable_var_name=stage.CACHE)).body
        if isinstance(n, ast.FunctionDef)
    )
    code = stage._code_from_node(node, "<string>")
    native_blocked.add(code)
    calls = []

    def target():
        calls.append("forbidden target")

    fn = FunctionType(code, dict(__builtins__=vars(builtins)), code.co_name)
    fn.__kwdefaults__ = {"__callable_cached": target}
    fn.__wrapped__ = target
    assert stage._cache_target(fn) is target and calls == []
    fn.__kwdefaults__["__callable_cached"] = lambda: None
    with pytest.raises(ValueError, match="Foreign cached-function target"):
        stage._cache_target(fn)
    assert calls == []


@pytest.mark.parametrize("mutation", ["shadow", "cached-builtins"])
def test_reached_builtin_resolution_and_cached_dictionary_are_no_call_controls(
    controlled, native_blocked, mutation
):
    h = controlled
    namespace = {"__builtins__": vars(builtins)}
    exec("def guarded_factory(): return str()", namespace)
    fn = namespace["guarded_factory"]
    native_blocked.add(fn.__code__)
    h.callbacks.make_default = fn
    source = stage._acquire(h.parent)
    if mutation == "shadow":
        before = stage._runtime(source)
        namespace["str"] = builtins.str
        with pytest.raises(ValueError, match="runtime reference changed"):
            stage.simulator._same(stage._runtime(source), before)
    else:
        foreign = dict(vars(builtins))
        foreign_namespace = {"__builtins__": foreign}
        fn = FunctionType(fn.__code__, foreign_namespace)
        foreign_namespace["__builtins__"] = vars(builtins)
        h.callbacks.make_default = fn
        with pytest.raises(ValueError, match="cached builtins association"):
            stage._runtime(source)
    assert h.calls == []


@pytest.mark.parametrize("point", ["factory", "callback_init"])
@pytest.mark.parametrize("source_failure", [False, True])
def test_inherited_return_hook_preserves_source_primary_and_raw_partials(
    controlled, tmp_path, point, source_failure
):
    h = controlled
    request = h.request()
    previous, trace = sys.getprofile(), sys.gettrace()
    observer_error = SyntheticCaptureFailure("inherited callback return failed")
    observer_cause = SyntheticSourceCause("observer cause")
    source_error = SyntheticSourceFailure("original callback source failure")
    source_cause = SyntheticSourceCause("original source cause")
    if source_failure:
        h.errors.update(
            {"factory" if point == "factory" else "callback": source_error, "cause": source_cause}
        )
    selected = (
        h.callbacks.make_default.__code__
        if point == "factory"
        else h.base.CallbacksBC.__init__.__code__
    )
    invoked = []

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is selected and event == "return":
            invoked.append(arg)
            raise observer_error from observer_cause

    sys.setprofile(inherited)
    try:
        with pytest.raises(stage.CallbackRejected) as caught:
            stage.prepare(request, enabled=True)
        failure = caught.value
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
    assert len(invoked) == 1
    assert failure.source_error is (source_error if source_failure else None)
    if source_failure:
        assert source_error.__cause__ is source_cause and failure.__cause__ is source_error
    else:
        assert failure.__cause__ is observer_error
    assert observer_error.__cause__ is observer_cause
    label = "inherited_profile_native_callback_factory_return"
    assert failure.capture_errors == ((label, observer_error),)
    context = failure.partial
    partials = [(name, raw) for event, name, raw in context.raw_locals if event == label]
    assert len(partials) == 1 and partials[0][1]
    assert context.source.parent is h.source_parent
    assert context.source.parent.p is h.source_parent.p and context.source.app is h.app
    assert context.factory_completed is (not source_failure)
    assert h.calls.count("factory") == 1
    assert context.invalid and not context.active and not stage._ACTIVE
    assert all(c is not context for c in stage._ISSUED.values())
    if point == "callback_init":
        assert partials[0][1]["self"] is context.partial_callback
        assert type(context.partial_callback) is h.callbacks.SimCallbacksNoop
        assert stage._cache(h.target) == (True, False)
    elif not source_failure:
        assert partials[0][1]["value"] is context.callback
    else:
        assert stage._cache(h.target) == request.cache_before
    if not source_failure:
        assert context.callback is context.partial_callback
        assert vars(context.callback) == dict(
            _progress_min=None, _progress_max=None, _progress_next=None
        )
    save(
        tmp_path,
        "deferred-return-hook",
        dict(
            point=point,
            primary=failure.source_error,
            capture=failure.capture_errors,
            raw_locals=context.raw_locals,
            work=context.work,
            callback=context.partial_callback,
            cache_before=request.cache_before,
            actual_cache_after=stage._cache(h.target),
            factory_completed=context.factory_completed,
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("point", ["factory", "callback_init"])
def test_inherited_entry_guard_rejects_before_callback_body(controlled, point):
    h = controlled
    request = h.request()
    previous, trace = sys.getprofile(), sys.gettrace()
    error = SyntheticSourceFailure("callback entry guard refusal")
    selected = (
        h.callbacks.make_default.__code__
        if point == "factory"
        else h.base.CallbacksBC.__init__.__code__
    )
    invoked = []

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is selected and event == "call":
            invoked.append(event)
            raise error

    sys.setprofile(inherited)
    try:
        with pytest.raises(stage.CallbackRejected) as caught:
            stage.prepare(request, enabled=True)
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
    assert invoked == ["call"]
    assert caught.value.source_error is error and caught.value.__cause__ is error
    assert caught.value.capture_errors == () and not caught.value.partial.factory_completed
    assert h.calls.count("callback-init") == 0
    assert h.calls.count("factory") == (0 if point == "factory" else 1)
