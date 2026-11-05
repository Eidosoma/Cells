"""Blocked source/input/observer controls; no native INIT/SIM owner is supplied."""

import ast
import contextlib
import os
import sys
from types import CodeType, FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_init_sim_preparation as stage
from tests.unit import test_betse_native_init_retained_world as guards
from validation.betse import betse_native_init_sim_preparation_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    from types import FunctionType

    namespace = dict(vars(guards), software=software, _RAW_GUARDS=[])
    function = FunctionType(guards.blocked.__wrapped__.__code__, namespace)
    with contextlib.contextmanager(function)(request, tmp_path, monkeypatch):
        yield


def test_preparation_original_SIM_caller_retains_sim_cells_and_current_configuration(tmp_path):
    plan = stage.source_plan()
    original = plan["original"]
    assert original["caller_keyword_order"] == ("kind", "cells", "p", "sim", "callbacks")
    assert original["retained_from_INIT"] == ("sim", "cells")
    assert original["setup_order"] == (
        "phase.die_unless_kind_init_or_sim",
        "self.init_dynamics",
        "self.clear_storage",
        "self.update_V",
        "self._plot_loop",
    )
    assert "fresh SimPhaseCaches" in original["phase_order"]
    assert "fresh TissueHandler" in original["phase_order"]
    assert original["phase_order"].index("sim.dyna = phase.dyna") < original["phase_order"].index(
        "p._run_sim = True"
    )
    assert original["stopped_before"].startswith("SimPhase allocation")
    assert plan["same_p_SIM_mutation_not_implemented"] is True
    assert plan["native_pickle_full_caller_or_scientific_admission"] is False
    software.snapshot.write_json(tmp_path / "original-boundary.json", plan)


@pytest.mark.parametrize("role", ("runner_constructor", "compatibility"))
def test_preparation_compiles_original_body_without_evaluating_it(role):
    node = stage.source.nodes()[role]
    code = stage.source.code(role)
    assert code.co_filename == str(stage.source.NATIVE / stage.source.RUNNER)
    assert code.co_name == node.name
    assert code.co_varnames[: code.co_argcount] == tuple(arg.arg for arg in node.args.args)
    compiled = compile(
        (stage.source.NATIVE / stage.source.RUNNER).read_bytes(),
        str(stage.source.NATIVE / stage.source.RUNNER),
        "exec",
        dont_inherit=True,
    )
    cls = next(
        value
        for value in compiled.co_consts
        if type(value) is CodeType and value.co_name == "SimRunner"
    )
    original = next(
        value for value in cls.co_consts if type(value) is CodeType and value.co_name == node.name
    )
    assert stage.observation._code(code) == stage.observation._code(original)
    if role == "compatibility":
        assert {"general options", "world options"}.issubset(code.co_consts)
        assert code.co_varnames[:3] == ("self", "p_old", "p_new")


@pytest.mark.parametrize("role", ("phase", "setup", "caller", "invented"))
def test_preparation_no_compiled_phase_or_timestep_admission(role):
    with pytest.raises(ValueError, match="non-mutating runner prefix"):
        stage.source.code(role)


class Foreign:
    def __getattribute__(self, name):
        raise AssertionError("No foreign owner/configuration/phase read")


def test_preparation_missing_reviews_refuse_before_foreign_owner_or_source_use():
    assert stage.PARENT_REVIEW_SHA256 is stage.PARAMETERS_REVIEW_SHA256 is None
    with pytest.raises(stage.PreparationRejected) as caught:
        stage.from_init(Foreign(), current_parameters_owner=Foreign(), law_id=stage.LAW_ID)
    assert caught.value.stage == "producer_review_held"


@pytest.mark.parametrize("law", (None, "other", 1))
def test_preparation_wrong_law_refuses_before_any_foreign_authority_read(law):
    with pytest.raises(stage.PreparationRejected) as caught:
        stage.from_init(Foreign(), current_parameters_owner=Foreign(), law_id=law)
    assert caught.value.stage == "law"


@pytest.mark.parametrize("kind", ("none", "empty", "receipt", "foreign"))
def test_preparation_caches_receipts_and_foreign_objects_cannot_supply_INIT(kind):
    supplied = {
        "none": None,
        "empty": {},
        "receipt": {"complete": True, "phase": "INIT"},
        "foreign": Foreign(),
    }[kind]
    with pytest.raises(stage.PreparationRejected) as caught:
        stage._types(supplied, Foreign())
    assert caught.value.stage == "init_owner"


@pytest.mark.parametrize(
    "enabled,flag,expected",
    (
        (False, None, "release"),
        (True, None, "release"),
        (1, "1", "release"),
        (True, "1", "producer_review_held"),
    ),
)
def test_preparation_actual_prepare_is_held_before_foreign_request(
    monkeypatch, enabled, flag, expected
):
    if flag is None:
        monkeypatch.delenv(stage.RELEASE, raising=False)
    else:
        monkeypatch.setenv(stage.RELEASE, flag)
    with pytest.raises(stage.PreparationRejected) as caught:
        stage.prepare(Foreign(), enabled=enabled)
    assert caught.value.stage == expected


def test_preparation_owner_and_record_cannot_hydrate_native_SIM_authority(monkeypatch):
    with pytest.raises(TypeError):
        stage.SimPreparationOwner()
    with pytest.raises(stage.PreparationRejected) as caught:
        stage._authority({"source_completed": True})
    assert caught.value.stage == "owner"
    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.PreparationRejected) as caught:
        stage.construct_sim(Foreign(), enabled=True)
    assert caught.value.stage == "owner"


def test_preparation_phase_constructor_stays_behind_the_missing_genuine_forwarding_contract():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    node = functions["construct_sim"]
    assert isinstance(node.body[-1], ast.Raise)
    assert "SIM_parent_forwarding_prerequisite" in ast.unparse(node.body[-1])
    assert "SimPhase(" not in ast.unparse(node)
    assert "_authority(owner)" in ast.unparse(node)
    assert "_ready()" in ast.unparse(functions["from_init"])
    assert "_run_prefix(context)" in ast.unparse(functions["prepare"])
    assert stage.MAX_WORK == stage.observation.MAX_WORK == 10000


@pytest.mark.parametrize(
    "failing,hook_event",
    ((False, None), (True, None), (False, "return"), (True, "return"), (False, "call")),
)
def test_preparation_reused_observer_keeps_actual_toy_primary_and_return_hook_separate(
    tmp_path, failing, hook_event
):
    class FalseSourceError(ValueError):
        def __bool__(self):
            return False

    primary, cause = FalseSourceError("toy original prefix failure"), OSError("retained cause")
    secondary = RuntimeError("toy observer refusal")
    entered = []

    def toy(self):
        entered.append(self)
        if failing:
            raise primary from cause
        return None

    context = SimpleNamespace(
        stage="synthetic_metadata_only",
        constructor_codes={toy.__code__},
        work=[],
        raw_locals=[],
        observations=[],
        capture_errors=[],
        partial_instance=None,
    )
    previous_profile, previous_trace = sys.getprofile(), sys.gettrace()

    def inherited(frame, event, arg):
        if previous_profile is not None:
            previous_profile(frame, event, arg)
        if frame.f_code is toy.__code__ and event == hook_event:
            raise secondary

    actual = SimpleNamespace()
    try:
        sys.setprofile(inherited)
        if hook_event == "call":
            with pytest.raises(RuntimeError) as caught, stage.observation._observe(context):
                toy(actual)
            assert caught.value is secondary and entered == []
        elif failing:
            with pytest.raises(FalseSourceError) as caught, stage.observation._observe(context):
                toy(actual)
            assert caught.value is primary and caught.value.__cause__ is cause
            assert entered == [actual]
        else:
            with stage.observation._observe(context):
                assert toy(actual) is None
            assert entered == [actual]
    finally:
        sys.setprofile(previous_profile)
        sys.settrace(previous_trace)
    assert sys.getprofile() is previous_profile and sys.gettrace() is previous_trace
    if hook_event == "return":
        assert any(error is secondary for _, error in context.capture_errors)
    else:
        assert context.capture_errors == []
    software.snapshot.write_json(
        tmp_path / "observer-control.json",
        dict(
            synthetic_metadata_only=True,
            failing=failing,
            inherited_hook_event=hook_event,
            actual_native_or_owner_entries=0,
            primary_cause_identity_retained=True,
            deferred_capture_errors=len(context.capture_errors),
            real_original_observer_reused=True,
        ),
    )


@pytest.mark.parametrize("seconds", (0, 1800, True))
def test_preparation_software_never_admits_an_issued_or_extended_run(seconds):
    with pytest.raises(ValueError):
        software._policy("preparation", seconds)
    assert software._policy("preparation", 480) == 480


def test_preparation_software_blocks_real_native_and_actual_prefix_entry():
    supplied = SimpleNamespace(
        f_globals={"__name__": stage.__name__}, f_code=SimpleNamespace(co_name="_native")
    )
    assert software.is_forbidden_frame(supplied)
    supplied.f_code.co_name = "_run_prefix"
    assert software.is_forbidden_frame(supplied)
    assert os.environ.get(software.SOFTWARE_RELEASE) == "1"


@pytest.mark.parametrize("failing", (False, True))
def test_preparation_metadata_verification_attempts_are_retained_without_owner_or_case_credit(
    failing,
):
    work, actual = [], object()
    primary, cause = ValueError("metadata refusal"), OSError("metadata cause")

    def metadata():
        if failing:
            raise primary from cause
        return actual

    if failing:
        with pytest.raises(ValueError) as caught:
            stage._metadata_call(work, "declared metadata observation", metadata)
        assert caught.value is primary and caught.value.__cause__ is cause
    else:
        assert stage._metadata_call(work, "declared metadata observation", metadata) is actual
    assert work == [
        dict(
            sequence=0,
            call="declared metadata observation",
            status="failed" if failing else "returned",
        )
    ]


def test_preparation_entry_guard_rejects_reentry_before_nested_metadata_and_poison_outer():
    calls = []

    @stage._entry_guard
    def outer():
        calls.append("outer entered")
        with pytest.raises(stage.PreparationRejected) as caught:
            outer()
        assert caught.value.stage == "reentrant"
        return object()

    with pytest.raises(stage.PreparationRejected) as caught:
        outer()
    assert caught.value.stage == "reentrant" and calls == ["outer entered"]
    assert stage._ENTRY == []


@pytest.mark.parametrize("source_failure", (False, True))
def test_preparation_read_guard_deactivates_on_closure_failure_without_replacing_primary(
    source_failure,
):
    """Isolated metadata guard only; no owner type or public API is supplied."""
    from types import FunctionType

    stack, observed = [], []

    @contextlib.contextmanager
    def registry(metadata_token):
        yield

    paths = SimpleNamespace(_install_audit=lambda guard: observed.append(guard))
    metadata_parameters = SimpleNamespace(
        _stacks=lambda audit: ((stack, audit),),
        previous=SimpleNamespace(
            previous=SimpleNamespace(mod=SimpleNamespace(subconfigs=SimpleNamespace(paths=paths)))
        ),
    )
    fn = FunctionType(
        stage._reading_current.__wrapped__.__code__,
        dict(
            vars(stage),
            parameters=metadata_parameters,
            claims=SimpleNamespace(_registry=registry, _busy=lambda *args: None),
        ),
    )
    context = SimpleNamespace(
        current=SimpleNamespace(loaded=SimpleNamespace(owner=object())),
        capture_errors=[],
        invalid=False,
    )
    primary, cause = ValueError("synthetic body failure"), OSError("retained source cause")
    with pytest.raises(ValueError) as caught, contextlib.contextmanager(fn)(context):
        stack[-1] = object()  # Deliberately break only this isolated test stack.
        if source_failure:
            raise primary from cause
    assert len(observed) == 1 and observed[0].active is False
    assert context.invalid and len(context.capture_errors) == 1
    assert context.capture_errors[0][0] == "current_read_lease_closure"
    if source_failure:
        assert caught.value is primary and caught.value.__cause__ is cause
        assert context.capture_errors[0][1] is not primary
    else:
        assert caught.value is context.capture_errors[0][1]


def _clone(function, **values):
    copied = FunctionType(
        function.__code__,
        dict(function.__globals__, **values),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    copied.__kwdefaults__ = function.__kwdefaults__
    return copied


@pytest.fixture
def wrapper_model(monkeypatch):
    """Actual monitoring, with explicitly synthetic factory/loader bodies.

    Only this private fixture namespace has a toy backend/loader seam. The
    production observer and scoped SimRunner registry stay untouched. No
    native body, library factory, constructor or import executes.
    """
    from tests.unit import test_betse_native_init_molecule_wrapper_authority as fixtures

    api = stage._wrapper_api()
    observer = ModuleType("synthetic_runner_import_observer")
    namespace = vars(observer)
    namespace.update(api)
    for name, function in tuple(api.items()):
        if type(function) is FunctionType and function.__globals__ is api:
            copied = FunctionType(
                function.__code__,
                namespace,
                function.__name__,
                function.__defaults__,
                function.__closure__,
            )
            copied.__kwdefaults__ = function.__kwdefaults__
            namespace[name] = copied
    watched = api["observing_native_imports"].__wrapped__
    copied = FunctionType(watched.__code__, namespace, watched.__name__, watched.__defaults__)
    copied.__kwdefaults__ = watched.__kwdefaults__
    namespace["observing_native_imports"] = contextlib.contextmanager(copied)
    factory = _clone(fixtures.factory_model.__wrapped__, stage=observer)
    return SimpleNamespace(model=factory(monkeypatch), authority=namespace)


def _probe_dispatch(wrapper_model, *, original_code=None):
    """Bind production admission/dispatch helpers to observed TOY sites."""
    model, api = wrapper_model.model, wrapper_model.authority

    def plain_probe(self, p_old, p_new):
        self._callbacks = p_old
        self._p = p_new
        return None

    # Change the uncalled fixture function before actual factory observation.
    model.original.__code__ = original_code or plain_probe.__code__
    imported, wrapper = model.run()
    selected = (("compatibility", "method"),)
    class_check = _clone(stage._class_dispatch, _SELECTED=selected)
    select = _clone(
        stage._selected_dispatch,
        _SELECTED=selected,
        _class_dispatch=class_check,
        _wrapper_api=lambda: api,
    )
    invoke = _clone(stage._invoke_selected, _selected_dispatch=select, _SELECTED=selected)
    native = SimpleNamespace(
        cls=model.owner,
        methods={"compatibility": model.original},
        outer={"compatibility": wrapper},
        selected_slots=class_check(model.owner),
    )
    instance = object.__new__(model.owner)
    p_old, p_new, callbacks = object(), object(), object()
    context = SimpleNamespace(
        native=native,
        parent=SimpleNamespace(p=p_old, phase=SimpleNamespace(callbacks=callbacks)),
        current=SimpleNamespace(p=p_new),
        capture_errors=[],
        raw_locals=[],
        instance=instance,
        source_error=None,
    )
    return SimpleNamespace(
        model=model,
        imported=imported,
        wrapper=wrapper,
        native=native,
        select=select,
        invoke=invoke,
        receiver=instance,
        context=context,
    )


def test_preparation_scoped_import_observer_has_original_code_and_private_registry():
    api = stage._wrapper_api()
    assert api["_ISSUED"] is stage._WRAPPER_ISSUED
    assert api["_ISSUED"] is not stage.imported_wrappers._ISSUED
    assert api["_ACTIVE"] is stage.imported_wrappers._ACTIVE
    assert api["network"].SITES == {
        ("SimRunner", "__init__"): stage.source.RUNNER,
        ("SimRunner", "_die_if_seed_differs"): stage.source.RUNNER,
    }
    for _name, copied, original in stage._WRAPPER_API.functions:
        assert copied.__code__ is original.__code__
        assert copied.__globals__ is api
        assert original.__globals__ is vars(stage.imported_wrappers)
    assert stage._runner_import_code("SimRunner", "__init__").co_name == "__init__"
    with pytest.raises(ValueError, match="Unknown original"):
        stage._runner_import_code("Simulator", "__init__")


@pytest.mark.parametrize("kind", ("constant", "equal_function", "target", "compiler"))
def test_preparation_private_observer_namespace_drift_refuses_without_calls(monkeypatch, kind):
    api = stage._wrapper_api()
    if kind == "constant":
        monkeypatch.setitem(api, "MAX_FACTORIES", 3)
    elif kind == "equal_function":
        monkeypatch.setitem(api, "validate", _clone(api["validate"]))
    elif kind == "target":
        monkeypatch.setitem(api["network"].SITES, ("SimRunner", "foreign"), stage.source.RUNNER)
    else:
        monkeypatch.setattr(api["network"], "code", _clone(stage._runner_import_code))
    with pytest.raises(ValueError, match="(namespace|targets) changed"):
        stage._wrapper_api()


@pytest.mark.parametrize("enabled", (False, None, 1, "1"))
def test_preparation_native_import_gate_precedes_source_or_library_call(enabled):
    with pytest.raises(stage.PreparationRejected) as caught:
        with stage.observing_runner_import(enabled=enabled):
            pytest.fail("No unreleased import work")
    assert caught.value.stage == "release"


def test_preparation_compiled_original_observed_wrapper_contract_is_metadata_only(wrapper_model):
    probe = _probe_dispatch(wrapper_model, original_code=stage.source.code("compatibility"))
    assert stage.observation._code(probe.model.original.__code__) == stage.observation._code(
        stage.source.code("compatibility")
    )
    assert probe.select(probe.native, "compatibility") is probe.wrapper
    assert probe.imported.record.source_completed and probe.imported.record.factories == 1
    assert vars(probe.receiver) == {}
    assert not stage._ISSUED and not stage._WRAPPER_ISSUED


@pytest.mark.parametrize("kind", ("extra_outer", "equal_copy"))
def test_preparation_arbitrary_outer_or_equal_copy_is_not_observed_authority(wrapper_model, kind):
    probe = _probe_dispatch(wrapper_model)
    entered = []

    def foreign(*args, **kwargs):
        entered.append("foreign wrapper")
        return probe.wrapper(*args, **kwargs)

    foreign.__wrapped__ = probe.model.original
    changed = foreign if kind == "extra_outer" else _clone(probe.wrapper)
    # Synchronized local slot snapshots do not issue imported authority.
    probe.model.owner.method = changed
    probe.native.outer["compatibility"] = changed
    probe.native.selected_slots = (("method", changed),)
    with pytest.raises(stage.imported_wrappers.WrapperAuthorityRejected) as caught:
        probe.select(probe.native, "compatibility")
    assert caught.value.stage == "unissued"
    assert entered == [] and vars(probe.receiver) == {}


@pytest.mark.parametrize("name", ("__setattr__", "__getattribute__", "__new__", "_callbacks", "_p"))
def test_preparation_class_assignment_or_descriptor_refuses_before_body(wrapper_model, name):
    probe = _probe_dispatch(wrapper_model)
    entered = []

    def foreign(*args):
        entered.append(name)
        raise AssertionError("Foreign class dispatch must never run")

    replacement = property(foreign, foreign) if name in ("_p", "_callbacks") else foreign
    setattr(probe.model.owner, name, replacement)
    with pytest.raises(ValueError, match="dispatch changed"):
        probe.select(probe.native, "compatibility")
    assert entered == [] and object.__getattribute__(probe.receiver, "__dict__") == {}


def test_preparation_installed_dispatch_keeps_toy_wrapper_receiver_and_arguments(wrapper_model):
    probe = _probe_dispatch(wrapper_model)
    before = sys.getprofile(), sys.gettrace()
    assert probe.invoke(probe.context, "compatibility", probe.receiver) is None
    assert vars(probe.receiver) == {
        "_callbacks": probe.context.parent.p,
        "_p": probe.context.current.p,
    }
    assert probe.context.capture_errors == []
    assert (sys.getprofile(), sys.gettrace()) == before


@pytest.mark.parametrize("hook", ("profile", "trace"))
@pytest.mark.parametrize("mutation", ("slot", "setter", "descriptor", "code"))
def test_preparation_installed_hook_drift_refuses_before_foreign_body(
    wrapper_model, hook, mutation
):
    probe = _probe_dispatch(wrapper_model)
    entered, changed = [], []

    def foreign(*args, **kwargs):
        entered.append(mutation)
        raise AssertionError("Foreign changed callable must never execute")

    def foreign_code(*args, **kwargs):
        raise AssertionError("Changed executable must never run")

    before = sys.getprofile(), sys.gettrace()

    def inherited(frame, event, arg):
        prior = before[0] if hook == "profile" else before[1]
        if prior is not None:
            prior(frame, event, arg)
        selected_event = "call" if hook == "profile" else "line"
        if (
            frame.f_code is probe.model.original.__code__
            and event == selected_event
            and not changed
        ):
            changed.append(mutation)
            if mutation == "slot":
                probe.model.owner.method = foreign
            elif mutation == "setter":
                probe.model.owner.__setattr__ = foreign
            elif mutation == "descriptor":
                probe.model.owner._p = property(foreign, foreign)
            else:
                probe.wrapper.__code__ = foreign_code.__code__
        return inherited

    setter = sys.setprofile if hook == "profile" else sys.settrace
    setter(inherited)
    try:
        with pytest.raises(ValueError) as caught:
            probe.invoke(probe.context, "compatibility", probe.receiver)
        assert changed == [mutation]
        assert entered == [] and vars(probe.receiver) == {}
        assert probe.context.capture_errors
        assert probe.context.capture_errors[0] == ("runner_dispatch", caught.value)
        assert (sys.getprofile() if hook == "profile" else sys.gettrace()) is inherited
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])


@pytest.mark.parametrize("mismatch", ("receiver", "p_old", "p_new", "delegate"))
def test_preparation_installed_binding_mismatch_refuses_before_toy_store(wrapper_model, mismatch):
    probe = _probe_dispatch(wrapper_model)
    receiver, old, new = probe.receiver, probe.context.parent.p, probe.context.current.p
    if mismatch == "receiver":
        receiver = object.__new__(probe.model.owner)
    elif mismatch == "p_old":
        old = object()
    elif mismatch == "p_new":
        new = object()
    before, changed = (sys.getprofile(), sys.gettrace()), []

    def inherited(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if frame.f_code is probe.wrapper.__code__ and event == "call":
            changed.append(mismatch)
            if mismatch == "delegate":
                frame.f_locals["__beartype_func"] = lambda *args: pytest.fail(
                    "No foreign runtime delegate"
                )
            else:
                frame.f_locals["args"] = (receiver, old, new)

    sys.setprofile(inherited)
    try:
        with pytest.raises(ValueError):
            probe.invoke(probe.context, "compatibility", probe.receiver)
        assert changed == [mismatch]
        assert vars(receiver) == {} and vars(probe.receiver) == {}
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])


@pytest.mark.parametrize("source_failure", (False, True))
def test_preparation_dispatch_return_observer_keeps_primary_cause_and_restores_hooks(
    wrapper_model,
    source_failure,
):
    def failure_probe(self, p_old, p_new):
        raise p_old from p_new

    probe = _probe_dispatch(
        wrapper_model, original_code=failure_probe.__code__ if source_failure else None
    )
    primary, cause = ValueError("synthetic source error"), OSError("synthetic source cause")
    secondary = RuntimeError("synthetic return capture error")
    if source_failure:
        probe.context.parent.p, probe.context.current.p = primary, cause
    before = sys.getprofile(), sys.gettrace()

    def inherited(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if frame.f_code is probe.model.original.__code__ and event == "return":
            raise secondary

    sys.setprofile(inherited)
    try:
        if source_failure:
            with pytest.raises(ValueError) as caught:
                probe.invoke(probe.context, "compatibility", probe.receiver)
            assert caught.value is primary and primary.__cause__ is cause
        else:
            with pytest.raises(stage.PreparationRejected) as caught:
                probe.invoke(probe.context, "compatibility", probe.receiver)
            assert caught.value.stage == "capture" and probe.context.source_error is None
        assert sys.getprofile() is inherited and sys.gettrace() is before[1]
        assert any(
            label == "runner_inherited_return" and error is secondary
            for label, error in probe.context.capture_errors
        )
        assert any(row[0] == "runner_inherited_return" for row in probe.context.raw_locals)
        # No complete native preparation owner is created by a toy success.
        assert not stage._ISSUED
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])


class FalseBodyError(ValueError):
    def __bool__(self):
        return False


@pytest.mark.parametrize(
    "kind,event",
    (
        ("normal", "return"),
        ("ordinary", "exception"),
        ("ordinary", "return"),
        ("falsey", "exception"),
        ("falsey", "return"),
    ),
)
def test_preparation_trace_exception_or_return_retains_primary_before_inherited_failure(
    wrapper_model,
    kind,
    event,
):
    def failure(self, p_old, p_new):
        raise p_old from p_new

    probe = _probe_dispatch(
        wrapper_model, original_code=failure.__code__ if kind != "normal" else None
    )
    primary = FalseBodyError("false source") if kind == "falsey" else ValueError("ordinary source")
    cause, secondary = OSError("original cause"), RuntimeError("trace capture refusal")
    if kind != "normal":
        probe.context.parent.p, probe.context.current.p = primary, cause
    before, witnessed = (sys.getprofile(), sys.gettrace()), []

    def inherited(frame, actual_event, arg):
        if before[1] is not None:
            before[1](frame, actual_event, arg)
        if frame.f_code is probe.model.original.__code__ and actual_event == event:
            assert any(
                row[0] == "runner_inherited_trace_" + event and row[1] is frame and row[2] is arg
                for row in probe.context.raw_locals
            )
            witnessed.append((frame, arg))
            raise secondary
        return inherited

    sys.settrace(inherited)
    try:
        if kind == "normal":
            with pytest.raises(stage.PreparationRejected) as caught:
                probe.invoke(probe.context, "compatibility", probe.receiver)
            assert caught.value.stage == "capture" and probe.context.source_error is None
        else:
            with pytest.raises(ValueError) as caught:
                probe.invoke(probe.context, "compatibility", probe.receiver)
            assert caught.value is primary and primary.__cause__ is cause
            assert probe.context.source_error is primary
        assert len(witnessed) == 1
        assert any(
            label == "runner_inherited_trace_" + event and error is secondary
            for label, error in probe.context.capture_errors
        )
        assert sys.gettrace() is inherited and sys.getprofile() is before[0]
        assert not stage._ISSUED
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])


@pytest.mark.parametrize("falsey", (False, True))
def test_preparation_caller_exit_entry_rejection_preserves_body_and_reachable_outer_recovery(
    wrapper_model,
    falsey,
):
    def failure(self, p_old, p_new):
        raise p_old from p_new

    probe = _probe_dispatch(wrapper_model, original_code=failure.__code__)
    primary = FalseBodyError("original falsey") if falsey else ValueError("original")
    cause, secondary = OSError("cause"), RuntimeError("one-shot context exit refusal")
    probe.context.parent.p, probe.context.current.p = primary, cause
    probe.context.work = []
    probe.context.observations = []
    probe.context.partial_instance = None
    rejected, before = [], (sys.getprofile(), sys.gettrace())

    def inherited(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if (
            event == "call"
            and frame.f_code is contextlib._GeneratorContextManager.__exit__.__code__
            and getattr(frame.f_locals.get("self"), "gen", None) is not None
            and frame.f_locals["self"].gen.gi_code
            is stage.observation._observe.__wrapped__.__code__
            and probe.context.source_error is primary
            and not rejected
        ):
            rejected.append(frame)
            raise secondary

    def invoke(context, role, receiver=None):
        if role == "runner_constructor":
            return probe.receiver
        return probe.invoke(context, role, receiver)

    run = _clone(
        stage._run_prefix,
        __name__=__name__,
        _native=lambda: probe.native,
        _reading_current=lambda context: contextlib.nullcontext(),
        _proof=lambda *args, **kwargs: None,
        _invoke_selected=invoke,
        _runner_check=lambda context: pytest.fail("No failed source admission"),
    )
    sys.setprofile(inherited)
    try:
        with pytest.raises(ValueError) as caught:
            run(probe.context)
        assert caught.value is primary and primary.__cause__ is cause
        assert rejected and probe.context.source_error is primary
        assert rejected[0].f_locals["self"].gen.gi_frame is None
        assert any(error is secondary for _, error in probe.context.capture_errors)
        assert sys.getprofile() is inherited and sys.gettrace() is before[1]
        assert not stage._ISSUED
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
