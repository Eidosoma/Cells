"""Blocked ownership controls. Synthetic providers never issue actual INIT."""

import builtins
import json
import pickle
import sys
from dataclasses import replace
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_simulator_construction as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


@pytest.fixture(autouse=True)
def blocked_native(request, monkeypatch, tmp_path):
    attempted = []
    previous, trace, original_import = sys.getprofile(), sys.gettrace(), builtins.__import__
    blocked = {
        stage._acquire_native.__code__,
        stage.tissue.prepare.__code__,
        stage.tissue._native_setup.__code__,
        *(f.__code__ for f in stage.tissue._NATIVE.values()),
        *(f.__code__ for f in stage.tissue._STORES.values()),
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in blocked
            or frame.f_code.co_filename.startswith(str(stage.tissue.aliases.NATIVE) + "/")
        ):
            attempted.append((frame.f_code.co_filename, frame.f_code.co_name))
            raise AssertionError("Actual native/parameter/Simulator/phase work forbidden")
        if previous is not None:
            previous(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name == "betse" or name.startswith("betse."):
            attempted.append(("import", name))
            raise AssertionError("Actual native import forbidden")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", imports)

    def rng_forbidden(*args, **kwargs):
        attempted.append(("RNG", "numpy.random"))
        raise AssertionError("Actual RNG work forbidden")

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
        monkeypatch.setattr(stage.tissue.callers.np.random, name, rng_forbidden)
    sys.setprofile(profile)
    try:
        yield
        assert attempted == []
        assert sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempted,
                    native_constructor_entries=0,
                    numerical_or_RNG_entries=0,
                    synthetic_only=True,
                )
            )
        )


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, plan):
    """Stub only authority providers, preserving actual ownership/graph logic.

    The real provider refuses this unissued typed test parent. No synthetic
    object is passed off as an actual phase or finalized native owner.
    """
    calls, hooks, errors = [], {}, {}
    parent = object.__new__(stage.tissue.TissueConfigurationOwner)
    p = SimpleNamespace(_conf={"synthetic configuration": True})
    handler = SimpleNamespace(tissue="synthetic, not native-finalized")
    cache = stage.tissue.core.caches.snapshot(dict(synthetic_only=True))
    trial = SimpleNamespace(identity="synthetic-parent", source_completed=True, cache=cache)
    context = SimpleNamespace(p=p, handler=handler, trial=trial)

    def validate(value):
        calls.append("parent_validation")
        if value is not parent:
            raise stage.ConstructionRejected("Foreign synthetic parent", stage="owner")
        if "parent" in hooks:
            hooks["parent"]()
        return context

    class SyntheticSimulator:
        def __init__(self, *, marker=None):
            if marker is not None:
                raise AssertionError("Changed synthetic keyword default")
            calls.append("synthetic_constructor")
            if "constructor" in hooks:
                hooks["constructor"](self)
            if "source" in errors:
                raise errors["source"] from errors.get("cause")

    module = ModuleType("synthetic_constructor_control")
    module.Simulator = SyntheticSimulator

    def acquire():
        calls.append("synthetic_import")
        if "import" in errors:
            raise errors["import"] from errors.get("cause")
        return module

    def canonical(value):
        assert value is module
        return value.Simulator

    monkeypatch.setattr(stage.tissue, "_validate", validate)
    monkeypatch.setattr(stage, "_acquire_native", acquire)
    monkeypatch.setattr(stage, "_canonical", canonical)
    monkeypatch.setattr(stage, "source_plan", lambda: dict(plan, synthetic_only=True))
    monkeypatch.setenv(stage.RELEASE, "1")
    value = stage.from_tissue(parent, law_id=stage.LAW_ID)
    return SimpleNamespace(
        parent=parent,
        request=value,
        context=context,
        p=p,
        handler=handler,
        module=module,
        cls=SyntheticSimulator,
        calls=calls,
        hooks=hooks,
        errors=errors,
    )


def construct(controlled):
    return stage.prepare(controlled.request, enabled=True)


def test_pinned_original_empty_constructor_and_real_phase_gaps_are_metadata(plan):
    assert len(plan["native_pins"]) == 272
    assert plan["simulator_constructor_lines"] == (443, 448)
    assert plan["phase_constructor_lines"] == (107, 204)
    assert (
        plan["native_pins"][stage.SIM_FILE]
        == "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43"
    )
    assert len(plan["phase_prerequisites"]) == 5
    assert plan["phase_or_INIT_or_physical_or_checkpoint_admitted"] is False


@pytest.mark.parametrize("enabled,environment", [(False, "0"), (True, "0"), (False, "1"), (1, "1")])
def test_release_before_any_parent_or_native_work(monkeypatch, enabled, environment):
    monkeypatch.setenv(stage.RELEASE, environment)

    def forbidden(*a, **k):
        pytest.fail("Held route reached authority work")

    monkeypatch.setattr(stage.tissue, "_validate", forbidden)
    with pytest.raises(stage.ConstructionRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release" and caught.value.source_error is None


@pytest.mark.parametrize("value", [None, {}, SimpleNamespace(), "receipt-or-cache"])
def test_real_parent_provider_refuses_supplied_or_absent_authority(value):
    with pytest.raises(
        stage.tissue.ConfigurationRejected, match="Issued tissue configuration owner"
    ):
        stage.from_tissue(value, law_id=stage.LAW_ID)


def test_unissued_real_typed_parent_cannot_be_promoted():
    parent = object.__new__(stage.tissue.TissueConfigurationOwner)
    with pytest.raises(
        stage.tissue.ConfigurationRejected, match="Issued tissue configuration owner"
    ):
        stage.from_tissue(parent, law_id=stage.LAW_ID)


@pytest.mark.parametrize(
    "mutation",
    ["law", "incomplete", "copied-request", "foreign-p", "foreign-handler", "trial", "identity"],
)
def test_request_parent_associations_refuse_before_import(controlled, mutation):
    h = controlled
    if mutation in ("law", "incomplete"):
        if mutation == "incomplete":
            h.context.trial.source_completed = False
        with pytest.raises(stage.ConstructionRejected) as caught:
            stage.from_tissue(h.parent, law_id="foreign" if mutation == "law" else stage.LAW_ID)
        assert caught.value.stage == ("request_law" if mutation == "law" else "parent_completion")
        return
    request = h.request
    if mutation == "copied-request":
        request = replace(request)
    elif mutation == "foreign-p":
        h.context.p = SimpleNamespace(**vars(h.p))
    elif mutation == "foreign-handler":
        h.context.handler = SimpleNamespace(**vars(h.handler))
    elif mutation == "trial":
        h.context.trial = SimpleNamespace(**vars(h.context.trial))
    else:
        object.__setattr__(request, "identity", "foreign")
    with pytest.raises(stage.ConstructionRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.stage == ("request_owner" if mutation == "copied-request" else "parent")
    assert "synthetic_import" not in h.calls and "synthetic_constructor" not in h.calls
    if mutation != "copied-request":
        assert caught.value.source_error.stage == "parent_association"


def test_synthetic_transport_keeps_original_objects_and_one_occurrence(controlled, tmp_path):
    h = controlled
    owner = construct(h)
    assert owner.parameters is h.p and owner.tissue_handler is h.handler
    assert type(owner.simulator) is h.cls and vars(owner.simulator) == {}
    trial = owner.trial
    assert trial.constructor_completed and trial.failure_stage is None
    assert sum(row["constructor_body"] for row in trial.work) == 1
    assert [row["classification"] for row in trial.observations] == ["entry", "return_or_unwind"]
    assert h.calls.count("synthetic_import") == h.calls.count("synthetic_constructor") == 1
    with pytest.raises(stage.ConstructionRejected) as caught:
        construct(h)
    assert caught.value.stage == "consumed"
    another = stage.from_tissue(h.parent, law_id=stage.LAW_ID)
    with pytest.raises(stage.ConstructionRejected) as caught:
        stage.prepare(another, enabled=True)
    assert caught.value.stage == "consumed" and h.calls.count("synthetic_constructor") == 1
    save(
        tmp_path,
        "constructed",
        dict(trial=trial, live_graph=stage._ISSUED[owner].graph[1], synthetic_only=True),
    )


@pytest.mark.parametrize("point", ["import", "source"])
def test_primary_error_cause_partial_and_consumed_attempt_retained(controlled, tmp_path, point):
    h = controlled
    cause, error = SyntheticSourceCause("source cause"), SyntheticSourceFailure("source failure")
    h.errors.update({point: error, "cause": cause})
    with pytest.raises(stage.ConstructionRejected) as caught:
        construct(h)
    failure = caught.value
    assert failure.source_error is error and error.__cause__ is cause and failure.__cause__ is error
    assert failure.stage == ("native_import" if point == "import" else "simulator_constructor")
    assert failure.capture_errors == () and not failure.partial.completed
    if point == "source":
        assert type(failure.partial.partial_instance) is h.cls
        assert failure.partial.observations[-1]["classification"] == "return_or_unwind"
    assert h.request in stage._CONSUMED and h.parent in stage._CLAIMED
    assert not stage._ACTIVE and not failure.partial.active
    with pytest.raises(stage.ConstructionRejected) as repeated:
        construct(h)
    assert repeated.value.stage == "consumed"
    save(
        tmp_path,
        "failed",
        dict(
            primary=error,
            capture=failure.capture_errors,
            raw_locals=failure.partial.raw_locals,
            work=failure.partial.work,
            allocated=failure.partial.partial_instance,
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("source_failure", [False, True])
def test_observer_failure_never_masks_primary_or_issues_owner(
    controlled, monkeypatch, tmp_path, source_failure
):
    h = controlled
    capture = SyntheticCaptureFailure("locals copy failed")

    def broken(frame):
        raise capture

    monkeypatch.setattr(stage, "_copy_locals", broken)
    if source_failure:
        h.errors["source"] = SyntheticSourceFailure("original constructor failed")
    with pytest.raises(stage.ConstructionRejected) as caught:
        construct(h)
    failure = caught.value
    assert failure.source_error is h.errors.get("source")
    assert failure.capture_errors and all(e is capture for _, e in failure.capture_errors)
    assert failure.__cause__ is (h.errors["source"] if source_failure else capture)
    assert failure.partial.completed is (not source_failure)
    assert all(c is not failure.partial for c in stage._ISSUED.values())
    save(
        tmp_path,
        "capture-incomplete",
        dict(
            source=failure.source_error,
            capture=failure.capture_errors,
            work=failure.partial.work,
            completed=failure.partial.completed,
            synthetic_only=True,
        ),
    )


def test_snapshot_failure_retains_completed_constructor_and_actual_partial(controlled, monkeypatch):
    capture = SyntheticCaptureFailure("cache capture failed")
    monkeypatch.setattr(stage, "_snapshot", lambda c: (_ for _ in ()).throw(capture))
    with pytest.raises(stage.ConstructionRejected) as caught:
        construct(controlled)
    failure = caught.value
    assert failure.source_error is None and failure.capture_errors == (
        ("constructor_capture", capture),
    )
    assert failure.partial.completed and type(failure.partial.instance) is controlled.cls
    assert not stage._ACTIVE


@pytest.mark.parametrize("swallow", [False, True])
def test_reentrant_constructor_never_issues_or_dispatches_twice(controlled, swallow):
    h, nested = controlled, []

    def reenter(instance):
        try:
            construct(h)
        except stage.ConstructionRejected as error:
            nested.append(error)
            if not swallow:
                raise

    h.hooks["constructor"] = reenter
    with pytest.raises(stage.ConstructionRejected) as caught:
        construct(h)
    assert len(nested) == 1 and nested[0].stage == "reentrant"
    assert h.calls.count("synthetic_constructor") == 1
    if not swallow:
        assert caught.value.source_error is nested[0]
    else:
        assert isinstance(caught.value.source_error, ValueError)
    assert caught.value.partial.invalid and not stage._ACTIVE


def test_inherited_profiler_restored_with_primary_identity(controlled):
    h = controlled
    previous, trace = sys.getprofile(), sys.gettrace()
    error = SyntheticSourceFailure("inherited profiler failed")

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code is h.cls.__init__.__code__:
            raise error

    sys.setprofile(inherited)
    try:
        with pytest.raises(stage.ConstructionRejected) as caught:
            construct(h)
        assert caught.value.source_error is error and caught.value.__cause__ is error
        assert type(caught.value.partial.partial_instance) is h.cls
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)


@pytest.mark.parametrize(
    "mutation",
    [
        "p",
        "handler",
        "instance",
        "fields",
        "class",
        "method",
        "runtime",
        "graph",
        "keyword-default",
        "annotation",
    ],
)
def test_issued_identity_graph_and_native_runtime_drift_refuse(controlled, mutation):
    h, owner = controlled, construct(controlled)
    context = stage._ISSUED[owner]
    if mutation == "p":
        h.context.p = SimpleNamespace(**vars(h.p))
    elif mutation == "handler":
        h.context.handler = SimpleNamespace(**vars(h.handler))
    elif mutation == "instance":
        context.instance = object.__new__(h.cls)
    elif mutation == "fields":
        context.instance.illegal_material_cache = []
    elif mutation == "class":
        h.module.Simulator = type("ForeignEqualClass", (h.cls,), {})
    elif mutation == "method":
        fn = h.cls.__init__
        h.cls.__init__ = FunctionType(
            fn.__code__, fn.__globals__, fn.__name__, fn.__defaults__, fn.__closure__
        )
    elif mutation == "runtime":
        context.runtime = (context.runtime[0] + ("foreign declaration",), context.runtime[1])
    elif mutation == "keyword-default":
        h.cls.__init__.__kwdefaults__["marker"] = "foreign"
    elif mutation == "annotation":
        h.cls.__init__.__annotations__["return"] = int
    else:
        context.view.parameters = SimpleNamespace(**vars(h.p))
    with pytest.raises(stage.ConstructionRejected) as caught:
        _ = owner.simulator
    assert caught.value.stage == "owner_drift" and context.invalid
    assert h.calls.count("synthetic_constructor") == 1


def test_live_request_and_owner_never_pickle_or_restore_as_parent(controlled):
    owner = construct(controlled)
    for value in (controlled.request, owner):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)
    with pytest.raises(TypeError):
        stage.SimulatorOwner()
    with pytest.raises(stage.ConstructionRejected) as caught:
        stage._validate(object.__new__(stage.SimulatorOwner))
    assert caught.value.stage == "owner"


@pytest.mark.parametrize("supplied", [None, SimpleNamespace(kind="INIT"), {}, "cache-receipt"])
def test_no_supplied_phase_or_receipt_establishes_INIT(controlled, supplied):
    owner = construct(controlled)
    with pytest.raises(stage.ConstructionRejected) as caught:
        stage.require_phase(owner, supplied_phase=supplied)
    assert caught.value.stage == "phase_prerequisites"
    assert caught.value.partial["missing"] == stage._ISSUED[owner].plan["phase_prerequisites"]
    assert caught.value.partial["supplied_phase_refused"] is (supplied is not None)
    assert caught.value.partial["full_Parameters_or_INIT_or_checkpoint_admitted"] is False


def test_real_canonical_provider_refuses_foreign_module_without_call(monkeypatch):
    calls = []
    monkeypatch.setattr(stage.tissue.aliases, "_check_modules", lambda: calls.append("modules"))
    with pytest.raises(ValueError, match="Canonical original Simulator module/class"):
        stage._canonical(ModuleType("foreign_module"))
    assert calls == ["modules"]


def test_executable_constants_keep_binary64_type_sign_without_execution():
    assert stage._constant(0.0) != stage._constant(-0.0)
    assert stage._constant(3) != stage._constant(3.0)
    assert stage._constant((None, 3)) != stage._constant((None, 3.0))
    assert stage._constant(True) != stage._constant(1)
    assert Path(stage.__file__).is_file()


@pytest.mark.parametrize("point", ["import", "constructor"])
@pytest.mark.parametrize("source_failure", [False, True])
def test_inherited_return_hook_defers_success_and_unwind_errors(
    controlled, tmp_path, point, source_failure
):
    h = controlled
    previous, trace = sys.getprofile(), sys.gettrace()
    observer_error = SyntheticCaptureFailure("inherited return observer failed")
    observer_cause = SyntheticSourceCause("observer cause")
    source_error = SyntheticSourceFailure("original source failure")
    source_cause = SyntheticSourceCause("original source cause")
    if source_failure:
        h.errors.update(
            {"import" if point == "import" else "source": source_error, "cause": source_cause}
        )
    selected = stage._acquire_native.__code__ if point == "import" else h.cls.__init__.__code__
    invoked = []

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is selected and event == "return":
            invoked.append(arg)
            raise observer_error from observer_cause

    sys.setprofile(inherited)
    try:
        with pytest.raises(stage.ConstructionRejected) as caught:
            construct(h)
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
    label = (
        "inherited_profile_"
        + ("native_import" if point == "import" else "simulator_constructor")
        + "_return"
    )
    assert failure.capture_errors == ((label, observer_error),)
    context = failure.partial
    partials = [raw for event, raw in context.raw_locals if event == label]
    assert len(partials) == 1 and context.request is h.request
    assert context.parent is h.context and context.p is h.p and context.handler is h.handler
    assert context.import_completed is (not source_failure or point != "import")
    assert context.completed is (point == "constructor" and not source_failure)
    if point == "import":
        assert "module" in partials[0] and partials[0]["module"] is h.module
        assert h.calls.count("synthetic_constructor") == 0
        assert failure.stage == ("native_import" if source_failure else "import_capture")
    else:
        assert partials[0]["self"] is context.partial_instance
        assert type(context.partial_instance) is h.cls
        assert h.calls.count("synthetic_constructor") == 1
        assert failure.stage == (
            "simulator_constructor" if source_failure else "constructor_capture"
        )
    assert context.invalid and not context.active and not stage._ACTIVE
    assert all(c is not context for c in stage._ISSUED.values())
    save(
        tmp_path,
        "deferred-return-hook",
        dict(
            point=point,
            primary=failure.source_error,
            capture=failure.capture_errors,
            raw_locals=context.raw_locals,
            work=context.work,
            allocated=context.partial_instance,
            import_completed=context.import_completed,
            constructor_completed=context.completed,
            parent=h.p,
            handler=h.handler,
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("point", ["import", "constructor"])
def test_inherited_entry_guard_still_propagates_before_source_body(controlled, point):
    h = controlled
    previous, trace = sys.getprofile(), sys.gettrace()
    error = SyntheticSourceFailure("entry guard refusal")
    selected = stage._acquire_native.__code__ if point == "import" else h.cls.__init__.__code__
    invoked = []

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is selected and event == "call":
            invoked.append(event)
            raise error

    sys.setprofile(inherited)
    try:
        with pytest.raises(stage.ConstructionRejected) as caught:
            construct(h)
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
    assert invoked == ["call"]
    assert caught.value.source_error is error and caught.value.__cause__ is error
    assert caught.value.capture_errors == () and not caught.value.partial.completed
    assert h.calls.count("synthetic_constructor") == 0
    assert h.calls.count("synthetic_import") == (0 if point == "import" else 1)
