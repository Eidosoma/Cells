"""Source/typed-reservation controls; no successful native parent is fabricated."""

import ast
import contextlib
import dis
import sys
import weakref
from abc import ABCMeta
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_init_sim_assembly as stage
from tests.unit import test_betse_native_init_retained_world as guards
from validation.betse import betse_native_init_sim_assembly_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    function = FunctionType(
        guards.blocked.__wrapped__.__code__, dict(vars(guards), software=software, _RAW_GUARDS=[])
    )
    with contextlib.contextmanager(function)(request, tmp_path, monkeypatch):
        yield


class Foreign:
    def __getattribute__(self, name):
        raise AssertionError("No foreign owner/native attribute read")


@pytest.mark.parametrize(
    "role", ("phase", "phase_kludge", "phase_time", "report", "run_core", "handler", "cache")
)
def test_assembly_compiles_complete_original_context_without_source_evaluation(role):
    code = stage.source.code(role)
    path, owner, method = stage.source.METHODS[role]
    assert type(code) is CodeType and code.co_qualname == owner + "." + method
    assert code.co_filename == str(stage.source.NATIVE / path)
    unit = compile(
        (stage.source.NATIVE / path).read_bytes(),
        str(stage.source.NATIVE / path),
        "exec",
        dont_inherit=True,
    )
    cls = next(c for c in unit.co_consts if type(c) is CodeType and c.co_name == owner)
    actual = next(c for c in cls.co_consts if type(c) is CodeType and c.co_name == method)
    assert stage.preparation.observation._code(actual) == stage.preparation.observation._code(code)


def test_assembly_source_boundary_keeps_original_order_and_no_SIM_completion_claim():
    plan = stage.source_plan()
    assert plan["original"]["order"] == (
        "runner compatibility",
        "SimPhase(SIM,cells,current_p,sim,callbacks)",
        "sim.sim_info_report(phase)",
        "sim.run_sim_core(phase)",
    )
    assert not plan["SIM_iterations_or_checkpoint_continuity"]
    assert plan["endpoint"] == "after_SIM_constructor_before_sim_info_report_and_run_sim_core"
    constructor = stage.source.original.nodes()["phase_kludge"]
    stores = [
        n
        for n in ast.walk(constructor)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "dyna" for t in n.targets)
    ]
    assert len(stores) == 1


def test_assembly_import_roster_and_compile_metadata_do_not_decorate_or_invoke():
    sites = stage.source.import_sites()
    assert sites[("SimPhase", "__init__")] == "betse/science/phase/phasecls.py"
    assert sites[("TissueHandler", "__init__")] == "betse/science/tissue/tishandler.py"
    assert stage.source.import_code("SimPhase", "__init__") is stage.source.code("phase")
    assert not stage._IMPORTS and not stage._ISSUED


@pytest.mark.parametrize("law", (None, "", "other", 1))
def test_assembly_wrong_law_refuses_before_any_owner_or_native_use(law):
    with pytest.raises(stage.AssemblyRejected) as caught:
        stage.from_preparation(Foreign(), law_id=law)
    assert caught.value.stage == "law"


def test_assembly_missing_reviews_refuse_instead_of_receipt_or_cache_hydration():
    with pytest.raises(stage.AssemblyRejected) as caught:
        stage.from_preparation(Foreign(), law_id=stage.LAW_ID)
    assert caught.value.stage == "producer_review_held"


@pytest.mark.parametrize("enabled,flag", ((False, None), (True, None), (1, "1"), (True, "1")))
def test_assembly_prepare_and_original_import_are_both_explicitly_held(monkeypatch, enabled, flag):
    if flag is not None:
        monkeypatch.setenv(stage.RELEASE, flag)
    else:
        monkeypatch.delenv(stage.RELEASE, raising=False)
    expected = "producer_review_held" if enabled is True and flag == "1" else "release"
    with pytest.raises(stage.AssemblyRejected) as caught:
        stage.prepare(Foreign(), enabled=enabled)
    assert caught.value.stage == expected
    with pytest.raises(stage.AssemblyRejected) as imported:
        with stage.observing_phase_import(enabled=enabled):
            pytest.fail("No native import/factory may run")
    assert imported.value.stage == expected


def test_assembly_owner_cannot_be_created_from_phase_dict_or_saved_metadata():
    with pytest.raises(TypeError):
        stage.SimAssemblyOwner()
    with pytest.raises(stage.AssemblyRejected) as caught:
        stage.run_core_boundary(dict(completed=True, phase="SIM"))
    assert caught.value.stage == "owner"
    with pytest.raises(TypeError):
        stage.terminal.SimReservation()
    with pytest.raises(stage.terminal.InitTerminalRejected):
        stage.terminal._sim_reservation(object.__new__(stage.terminal.SimReservation))


@pytest.mark.parametrize("failing", (False, True))
def test_assembly_metadata_invocations_retain_actual_attempt_and_primary_cause(failing):
    context, returned = SimpleNamespace(metadata_work=[]), object()
    primary, cause = ValueError("source metadata refusal"), OSError("source cause")

    def run():
        if failing:
            raise primary from cause
        return returned

    if failing:
        with pytest.raises(ValueError) as caught:
            stage._metadata(context, "metadata only", run)
        assert caught.value is primary and primary.__cause__ is cause
    else:
        assert stage._metadata(context, "metadata only", run) is returned
    assert context.metadata_work == [
        dict(sequence=0, call="metadata only", status="failed" if failing else "returned")
    ]


def test_assembly_retained_view_is_only_metadata_and_never_relabels_an_INIT_phase():
    old = SimpleNamespace(
        phase=object(), p=object(), sim=object(), cells=object(), objects=(("sim", object()),)
    )
    view = stage._retained_view(old)
    assert view is not old and view.phase is old.phase and view.p is old.p
    assert view.sim is old.sim and view.cells is old.cells and view.objects is old.objects
    assert view.permissions == ((old.sim, frozenset(("dyna",))),)
    assert view.graph_fields is not getattr(old, "graph_fields", None)
    assert not stage._ISSUED


def _reservation_model():
    # Private registry-shaped metadata model; never insert an owner into the
    # real terminal/assembly registries or execute any native phase source.
    class MetadataOwner:
        pass

    owner, trial = MetadataOwner(), object()
    parent = SimpleNamespace(trial=trial, active=False, invalid=False)
    issued = {owner: (parent, trial)}
    reservations, retired, checks = {}, {}, []

    def authority(actual):
        assert actual is owner
        checks.append(actual)
        return parent

    namespace = dict(
        vars(stage.terminal),
        InitTerminalOwner=MetadataOwner,
        _ISSUED=issued,
        _SIM_RESERVATIONS=reservations,
        _SIM_RETIRED=retired,
        _LOCK=RLock(),
        _ACTIVE=[],
        _authority=authority,
    )
    reserve = FunctionType(stage.terminal.reserve_for_sim.__code__, namespace)
    validate = FunctionType(stage.terminal._sim_reservation.__code__, namespace)
    return SimpleNamespace(
        owner=owner,
        trial=trial,
        parent=parent,
        issued=issued,
        retired=retired,
        reservations=reservations,
        reserve=reserve,
        validate=validate,
        checks=checks,
    )


def test_assembly_private_retirement_model_is_irreversible_without_state_mutation(monkeypatch):
    model = _reservation_model()
    monkeypatch.setenv(stage.terminal.SIM_RESERVATION_RELEASE, "1")
    token = model.reserve(
        model.owner,
        expected_trial=model.trial,
        law_id=stage.terminal.SIM_RESERVATION_LAW,
        enabled=True,
    )
    assert model.validate(token) == (model.parent, model.trial)
    with pytest.raises(stage.terminal.InitTerminalRejected) as caught:
        model.reserve(
            model.owner,
            expected_trial=model.trial,
            law_id=stage.terminal.SIM_RESERVATION_LAW,
            enabled=True,
        )
    assert caught.value.stage == "consumed" and model.checks == [model.owner]
    assert not model.parent.active and not model.parent.invalid
    assert not stage.terminal._SIM_RESERVATIONS and not stage._ISSUED


@pytest.mark.parametrize("drift", ("retired", "issued", "trial", "active", "invalid", "thread"))
def test_assembly_private_retirement_metadata_drift_cannot_validate_closed_parent(
    monkeypatch, drift
):
    model = _reservation_model()
    monkeypatch.setenv(stage.terminal.SIM_RESERVATION_RELEASE, "1")
    token = model.reserve(
        model.owner,
        expected_trial=model.trial,
        law_id=stage.terminal.SIM_RESERVATION_LAW,
        enabled=True,
    )
    if drift == "retired":
        model.retired.clear()
    elif drift == "issued":
        model.issued[model.owner] = (model.parent, model.trial)
    elif drift == "trial":
        model.parent.trial = object()
    elif drift == "active":
        model.parent.active = True
    elif drift == "invalid":
        model.parent.invalid = True
    else:
        row = model.reservations[token]
        model.reservations[token] = (row[0], row[1], get_ident() + 1)
    with pytest.raises(stage.terminal.InitTerminalRejected) as caught:
        model.validate(token)
    assert caught.value.stage == "reservation"


def test_assembly_default_retirement_gate_precedes_foreign_owner_or_source_read(monkeypatch):
    monkeypatch.delenv(stage.terminal.SIM_RESERVATION_RELEASE, raising=False)
    with pytest.raises(stage.terminal.InitTerminalRejected) as caught:
        stage.terminal.reserve_for_sim(
            Foreign(),
            expected_trial=Foreign(),
            law_id=stage.terminal.SIM_RESERVATION_LAW,
            enabled=True,
        )
    assert caught.value.stage == "release"


def _installed_nested_model(monkeypatch):
    """Private issued-import model, never a native object or public owner.

    Ordinary test-file functions run under the real assembly profile/trace
    closures. Neither their filenames nor a path-gated callback are relabelled
    as native; only private registry/API associations are modelled.
    """
    events, foreign, validations = [], [], []
    primary, cause = ValueError("original toy constructor"), OSError("original toy cause")
    settings = SimpleNamespace(fail=False)

    class SimPhaseCacheABC(metaclass=ABCMeta):  # noqa: B024 - same native cache boundary
        def __init__(self, phase):
            events.append("cache_abc")
            self._phase = weakref.proxy(phase)

    class SimPhaseCacheUpscaled(SimPhaseCacheABC):
        pass

    class SimPhaseCacheVectorCells(SimPhaseCacheABC):
        def __init__(self, phase):
            events.append("cache_vector")
            super().__init__(phase)

    class SimPhaseCacheVectorFieldCells(SimPhaseCacheABC):
        pass

    class SimPhaseCaches:
        def __init__(self, phase):
            from _cells_assembly_control_cache import (
                SimPhaseCacheUpscaled,
                SimPhaseCacheVectorCells,
                SimPhaseCacheVectorFieldCells,
            )

            events.append("cache")
            self.upscaled = SimPhaseCacheUpscaled(phase)
            self.vector = SimPhaseCacheVectorCells(phase)
            self.vector_field = SimPhaseCacheVectorFieldCells(phase)

    class TissueHandler:
        def __init__(self, p):
            events.append("handler")
            self.p = p
            if settings.fail:
                raise primary from cause

    class SimPhase:
        def __init__(self, kind, p, cells, sim, callbacks):
            from _cells_assembly_control_cache import SimPhaseCaches
            from _cells_assembly_control_tissue import TissueHandler

            events.append("phase")
            self.kind, self.p, self.cells = kind, p, cells
            self.sim, self.callbacks = sim, callbacks
            self.cache = SimPhaseCaches(phase=self)
            self.dyna = TissueHandler(p=p)
            self._init_kludge()

        def _init_kludge(self):
            self.sim.dyna = self.dyna
            self._init_kludge_time()

        def _init_kludge_time(self):
            events.append("time")

    class Simulator:
        pass

    modules = {}
    for suffix, classes in (
        (
            "cache",
            (
                SimPhaseCaches,
                SimPhaseCacheABC,
                SimPhaseCacheUpscaled,
                SimPhaseCacheVectorCells,
                SimPhaseCacheVectorFieldCells,
            ),
        ),
        ("tissue", (TissueHandler,)),
        ("phase", (SimPhase,)),
    ):
        module = ModuleType("_cells_assembly_control_" + suffix)
        for cls in classes:
            cls.__module__ = module.__name__
            vars(module)[cls.__name__] = cls
        modules[suffix] = module
        monkeypatch.setitem(sys.modules, module.__name__, module)

    imports, originals, wrapper_codes = {}, {}, set()

    def wrap(body):
        def checked(self, *args, __beartype_func=body, **kwargs):
            return __beartype_func(self, *args, **kwargs)

        # Distinct wrapper CodeTypes, with the ordinary unchanged test filename.
        checked.__code__ = checked.__code__.replace(co_qualname=body.__qualname__ + ".checked")
        checked.__wrapped__ = body
        return checked

    for suffix, cls, names in (
        ("phase", SimPhase, ("__init__", "_init_kludge", "_init_kludge_time")),
        ("cache", SimPhaseCaches, ("__init__",)),
        ("cache", SimPhaseCacheABC, ("__init__",)),
        ("cache", SimPhaseCacheVectorCells, ("__init__",)),
        ("tissue", TissueHandler, ("__init__",)),
    ):
        for name in names:
            original = vars(cls)[name]
            function = wrap(original)
            setattr(cls, name, function)
            row = SimpleNamespace(
                original=original,
                module=modules[suffix],
                target=((cls.__name__, name),),
                stack=(cls,),
            )
            imports[function] = (object(), row)
            originals[(cls.__name__, name)] = original
            wrapper_codes.update((function.__code__, original.__code__))

    def validate(actual, original, *, owner, attribute):
        validations.append((actual, original, owner, attribute))
        issued = imports.get(actual)
        if (
            issued is None
            or issued[1].original is not original
            or vars(owner).get(attribute) is not actual
            or actual.__wrapped__ is not original
            or actual.__kwdefaults__["__beartype_func"] is not original
        ):
            raise ValueError("Original model import issuance required")

    old_phase, old_cache = object.__new__(SimPhase), object.__new__(SimPhaseCaches)
    for name, cls in (
        ("upscaled", SimPhaseCacheUpscaled),
        ("vector", SimPhaseCacheVectorCells),
        ("vector_field", SimPhaseCacheVectorFieldCells),
    ):
        setattr(old_cache, name, object.__new__(cls))
    old_phase.cache, old_phase.dyna = old_cache, object.__new__(TissueHandler)
    old_phase.callbacks = object()
    sim = Simulator()
    sim.dyna = old_phase.dyna
    methods = {
        name: originals[("SimPhase", name)]
        for name in ("__init__", "_init_kludge", "_init_kludge_time")
    }
    context = SimpleNamespace(
        request=object(),
        thread=get_ident(),
        invalid=False,
        reservation=object(),
        parent=SimpleNamespace(phase=old_phase, sim=sim, cells=object()),
        current=SimpleNamespace(p=object()),
        native=SimpleNamespace(
            cls=SimPhase,
            module=modules["phase"],
            methods=methods,
            enum=SimpleNamespace(SIM=object()),
        ),
        roles={fn.__code__: name for name, fn in methods.items()},
        wrapper_codes=frozenset(wrapper_codes),
        admitted={},
        work=[],
        raw_calls=[],
        raw_returns=[],
        capture_errors=[],
        phase=None,
        raw_phase=None,
        original_handler=sim.dyna,
        handler_write=None,
        pending_handler_store=None,
        parameter_manager=None,
        source_error=None,
    )
    context.handler_store_offset = next(
        item.offset
        for item in dis.get_instructions(methods["_init_kludge"])
        if item.opname == "STORE_ATTR" and item.argval == "dyna"
    )

    def construct(actual):
        try:
            actual.raw_phase = actual.native.cls(
                kind=actual.native.enum.SIM,
                p=actual.current.p,
                cells=actual.parent.cells,
                sim=actual.parent.sim,
                callbacks=actual.parent.phase.callbacks,
            )
        except BaseException as error:
            actual.source_error = error
            raise

    def forbidden_simulator():
        raise AssertionError("No actual native constructor may execute")

    namespace = dict(
        vars(stage),
        __name__="metadata_assembly_installed_hooks",
        _IMPORTS=imports,
        _CONSUMED={context.request: context},
        _phase_import_api=lambda: dict(validate=validate),
        _construct=construct,
        terminal=SimpleNamespace(_sim_reservation=lambda token: None),
        source=SimpleNamespace(
            NATIVE=Path("/unavailable-assembly-native"),
            PINS={},
            code=lambda role: forbidden_simulator.__code__,
        ),
    )
    for name in (
        "_nested_header",
        "_bind_nested",
        "_check_nested_bindings",
        "_nested_caller",
        "_nested_entry",
        "_capture_boundary",
        "_metadata_guard",
        "_observe",
        "_run_observed",
    ):
        function = vars(stage)[name]
        namespace[name] = FunctionType(
            function.__code__, namespace, name, function.__defaults__, function.__closure__
        )
    namespace["_bind_nested"](context)
    return SimpleNamespace(
        context=context,
        namespace=namespace,
        run=namespace["_run_observed"],
        check=namespace["_metadata_guard"],
        events=events,
        foreign=foreign,
        modules=modules,
        classes=dict(SimPhase=SimPhase, TissueHandler=TissueHandler, SimPhaseCaches=SimPhaseCaches),
        imports=imports,
        originals=originals,
        primary=primary,
        cause=cause,
        settings=settings,
        validations=validations,
    )


def _run_nested_control(model, profile=None, trace=None):
    prior = sys.getprofile(), sys.gettrace()
    try:
        if profile is not None:
            sys.setprofile(profile)
        if trace is not None:
            sys.settrace(trace)
        expected = sys.getprofile(), sys.gettrace()
        try:
            model.run(model.context)
        finally:
            assert sys.getprofile() is expected[0] and sys.gettrace() is expected[1]
    finally:
        sys.setprofile(prior[0])
        sys.settrace(prior[1])
    assert sys.getprofile() is prior[0] and sys.gettrace() is prior[1]


def test_assembly_installed_hooks_preserve_actual_synthetic_cache_super_and_weak_links(
    monkeypatch, tmp_path
):
    model = _installed_nested_model(monkeypatch)
    _run_nested_control(model)
    context, phase = model.context, model.context.phase
    assert phase is context.raw_phase and phase.sim is context.parent.sim
    assert phase.cells is context.parent.cells and phase.p is context.current.p
    assert phase.sim.dyna is phase.dyna and context.handler_write is not None
    assert phase.cache.vector._phase.p is phase.p
    assert phase.cache.upscaled._phase.p is phase.p
    assert phase.cache.vector_field._phase.p is phase.p
    assert weakref.getweakrefcount(phase) > 0
    assert model.events == [
        "phase",
        "cache",
        "cache_abc",
        "cache_vector",
        "cache_abc",
        "cache_abc",
        "handler",
        "time",
    ]
    model.check(context)
    assert not context.capture_errors and not model.foreign
    assert context.nested_attempts
    phase_calls = context.nested_call_sites[id(model.originals[("SimPhase", "__init__")].__code__)]
    cache_calls = context.nested_call_sites[
        id(model.originals[("SimPhaseCaches", "__init__")].__code__)
    ]
    assert len(phase_calls) == 2 and len(cache_calls) == 3
    assert not stage._IMPORTS and not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "dispatch-control.json",
        dict(
            ordinary_test_file_bodies=True,
            actual_installed_assembly_profile_and_trace=True,
            actual_native_entries=0,
            real_super_and_weak_aliases_preserved=True,
            events=model.events,
            import_validations=len(model.validations),
            retained_raw_frames=len(context.work),
            actual_nested_attempts=len(context.nested_attempts),
            phase_factory_call_sites=len(phase_calls),
            cache_factory_call_sites=len(cache_calls),
        ),
    )


@pytest.mark.parametrize("role", ("TissueHandler", "SimPhaseCaches"))
@pytest.mark.parametrize("mutation", ("publication", "method", "code", "delegate"))
@pytest.mark.parametrize("observer", ("profile", "trace"))
def test_assembly_installed_hooks_refuse_foreign_nested_dispatch_before_body(
    monkeypatch, tmp_path, role, mutation, observer
):
    model = _installed_nested_model(monkeypatch)
    cls = model.classes[role]
    original = model.originals[(role, "__init__")]
    wrapper = vars(cls)["__init__"]
    changed = []

    def foreign(self, *args, **kwargs):
        model.foreign.append(self)

    def mutate():
        if mutation == "publication":
            suffix = "tissue" if role == "TissueHandler" else "cache"
            setattr(model.modules[suffix], role, foreign)
        elif mutation == "method":
            cls.__init__ = foreign
        elif mutation == "code":
            # Code replacement without changing the original function identity.
            def foreign_no_closure(self, *args, **kwargs):
                raise AssertionError("Foreign code must never enter")

            wrapper.__code__ = foreign_no_closure.__code__
        else:
            wrapper.__kwdefaults__["__beartype_func"] = foreign
        changed.append(True)

    before = sys.getprofile(), sys.gettrace()
    entry_code = wrapper.__code__

    def callback(frame, event, arg):
        previous = before[0] if observer == "profile" else before[1]
        result = previous(frame, event, arg) if previous is not None else None
        if frame.f_code is entry_code and event == "call" and not changed:
            mutate()
        return callback if observer == "trace" else result

    with pytest.raises(ValueError) as caught:
        _run_nested_control(model, **{observer: callback})
    expected = (
        ["phase"]
        if role == "SimPhaseCaches"
        else ["phase", "cache", "cache_abc", "cache_vector", "cache_abc", "cache_abc"]
    )
    assert changed == [True] and model.foreign == [] and model.events == expected
    assert model.context.invalid and model.context.nested_error is caught.value
    assert Path(foreign.__code__.co_filename) == Path(__file__)
    assert original in dict(model.context.nested_functions)
    software.snapshot.write_json(
        tmp_path / "dispatch-refusal.json",
        dict(
            role=role,
            mutation=mutation,
            inherited_observer=observer,
            original_foreign_filename=str(Path(foreign.__code__.co_filename)),
            actual_native_entries=0,
            foreign_body_entries=len(model.foreign),
            source_steps=model.events,
            primary_type=type(caught.value).__name__,
            original_issue_poisoned=model.context.invalid,
        ),
    )


@pytest.mark.parametrize("role", ("TissueHandler", "SimPhaseCaches"))
def test_assembly_source_local_factory_drift_refuses_with_unchanged_publication(
    monkeypatch, tmp_path, role
):
    model = _installed_nested_model(monkeypatch)
    body = model.originals[("SimPhase", "__init__")]
    original_cls = model.classes[role]
    changed = []
    prior = sys.gettrace()

    def foreign(*args, **kwargs):
        model.foreign.append(True)

    def trace(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if frame.f_code is body.__code__ and event == "opcode" and not changed:
            if frame.f_locals.get(role) is original_cls:
                frame.f_locals[role] = foreign
                assert frame.f_locals[role] is foreign
                changed.append(True)
        return trace

    with pytest.raises(ValueError, match="source-local nested factory") as caught:
        _run_nested_control(model, trace=trace)
    assert changed == [True] and not model.foreign
    assert model.context.invalid and model.context.nested_error is caught.value
    suffix = "tissue" if role == "TissueHandler" else "cache"
    assert getattr(model.modules[suffix], role) is original_cls
    assert model.classes[role].__init__ in model.imports
    software.snapshot.write_json(
        tmp_path / "local-factory-refusal.json",
        dict(
            role=role,
            publication_unchanged=True,
            code_and_defaults_unchanged=True,
            actual_native_entries=0,
            ordinary_foreign_body_entries=len(model.foreign),
            original_rejection_retained=model.context.nested_error is caught.value,
            partial_source_steps=model.events,
        ),
    )


@pytest.mark.parametrize("source_fails", (False, True))
@pytest.mark.parametrize("observer", ("profile", "trace"))
def test_assembly_real_hook_capture_stops_next_body_and_retains_source_primary(
    monkeypatch, tmp_path, source_fails, observer
):
    model = _installed_nested_model(monkeypatch)
    model.settings.fail = source_fails
    body = model.originals[("TissueHandler", "__init__")]
    secondary = LookupError("inherited constructor return capture")
    before = sys.getprofile(), sys.gettrace()

    def callback(frame, event, arg):
        prior = before[0] if observer == "profile" else before[1]
        result = prior(frame, event, arg) if prior is not None else None
        if frame.f_code is body.__code__ and event == "return":
            raise secondary
        return callback if observer == "trace" else result

    with pytest.raises(BaseException) as caught:
        _run_nested_control(model, **{observer: callback})
    if source_fails:
        assert caught.value is model.primary and model.primary.__cause__ is model.cause
    else:
        assert caught.value.__cause__ is secondary
    assert "handler" in model.events and "time" not in model.events
    assert model.context.parent.sim.dyna is model.context.original_handler
    assert model.context.handler_write is None
    assert any(error is secondary for _, error in model.context.capture_errors)
    assert model.context.raw_returns and not model.foreign
    software.snapshot.write_json(
        tmp_path / "capture-control.json",
        dict(
            source_fails=source_fails,
            inherited_observer=observer,
            actual_native_entries=0,
            raw_return_frames=len(model.context.raw_returns),
            source_primary_and_cause_retained=not source_fails or caught.value is model.primary,
            distinct_capture_retained=True,
            later_helper_entries=0,
            partial_source_steps=model.events,
        ),
    )


@pytest.mark.parametrize("role", ("TissueHandler", "SimPhaseCaches"))
@pytest.mark.parametrize("mutation", ("publication", "method", "code", "delegate"))
def test_assembly_completed_synthetic_dispatch_refuses_later_binding_drift(
    monkeypatch, tmp_path, role, mutation
):
    model = _installed_nested_model(monkeypatch)
    _run_nested_control(model)
    model.check(model.context)
    saved = tuple(model.events)
    actual = model.context.phase
    wrapper = vars(model.classes[role])["__init__"]

    def foreign(*args, **kwargs):
        model.foreign.append(True)

    if mutation == "publication":
        suffix = "cache" if role == "SimPhaseCaches" else "tissue"
        setattr(model.modules[suffix], role, foreign)
    elif mutation == "method":
        model.classes[role].__init__ = foreign
    elif mutation == "code":
        wrapper.__code__ = wrapper.__code__.replace()
    else:
        wrapper.__kwdefaults__["__beartype_func"] = foreign
    with pytest.raises(ValueError):
        model.check(model.context)
    assert model.context.phase is actual and tuple(model.events) == saved and not model.foreign
    assert model.context.invalid
    software.snapshot.write_json(
        tmp_path / "completed-binding-refusal.json",
        dict(
            role=role,
            mutation=mutation,
            actual_native_entries=0,
            original_raw_phase_retained=True,
            no_extra_source_steps=True,
        ),
    )


@pytest.mark.parametrize("role", ("TissueHandler", "SimPhaseCaches"))
@pytest.mark.parametrize("mutation", ("publication", "method"))
def test_assembly_foreign_frame_is_rejected_even_after_inherited_binding_restoration(
    monkeypatch, tmp_path, role, mutation
):
    model = _installed_nested_model(monkeypatch)
    cls = model.classes[role]
    wrapper = vars(cls)["__init__"]
    module = model.modules["cache" if role == "SimPhaseCaches" else "tissue"]
    restored = []

    def foreign(*args, **kwargs):
        model.foreign.append(True)

    # Deliberately exercise the reached-frame seam alone. Restore publications
    # at the actual foreign entry: pre/post header comparisons are equal, so
    # only the real caller/local/callee relationship can reject this attempt.
    if mutation == "publication":
        setattr(module, role, foreign)
    else:
        cls.__init__ = foreign
    phase = object.__new__(model.classes["SimPhase"])
    parent = model.context.parent
    before = sys.getprofile(), sys.gettrace()

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if event == "call" and frame.f_code is foreign.__code__:
            setattr(module, role, cls)
            cls.__init__ = wrapper
            model.namespace["_check_nested_bindings"](model.context)
            restored.append(True)
            model.namespace["_nested_caller"](model.context, frame, event)

    try:
        sys.setprofile(profile)
        with pytest.raises(ValueError) as caught:
            model.originals[("SimPhase", "__init__")](
                phase,
                model.context.native.enum.SIM,
                model.context.current.p,
                parent.cells,
                parent.sim,
                parent.phase.callbacks,
            )
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    assert restored == [True] and model.foreign == [] and model.context.invalid
    assert model.context.nested_error is caught.value
    assert getattr(module, role) is cls and cls.__init__ is wrapper
    if mutation == "method":
        assert model.context.nested_attempts[-1][0].f_code is foreign.__code__
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    software.snapshot.write_json(
        tmp_path / "restored-binding-frame-refusal.json",
        dict(
            role=role,
            mutation=mutation,
            actual_native_entries=0,
            foreign_body_entries=0,
            original_headers_exact_after_inherited_callback=True,
            actual_foreign_filename=foreign.__code__.co_filename,
            primary_rejection_retained=True,
            retained_nested_attempts=len(model.context.nested_attempts),
        ),
    )


def test_assembly_closed_owner_rechecks_nested_authority_before_retained_state():
    node = next(
        n
        for n in ast.parse(Path(stage.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "_check"
    )
    calls = [
        n.value.func.id
        for n in node.body
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name)
    ]
    assert calls.index("_check_nested_bindings") < calls.index("_check_retained")
