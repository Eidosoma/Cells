"""Native-blocked factory observation; toy bodies issue no native authority."""

import ast
import builtins
import contextlib
import functools
import hashlib
import json
import os
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_molecule_wrapper_authority as stage
from cells.processes import betse_native_init_sim_assembly as assembly
from cells.processes import betse_native_init_sim_preparation as preparation
from cells.processes import betse_native_phase_callbacks as callbacks
from cells.processes import betse_native_sim_run as sim_run
from cells.processes import betse_native_simulator_construction as simulator
from cells.processes import betse_native_tissue_configuration as tissue
from tests.unit import test_betse_native_init_molecule_network as inherited
from validation.betse import betse_native_init_molecule_wrapper_authority_software as runner


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    original = inherited.inherited.inherited._blocked_generator
    guard = FunctionType(
        original.__code__,
        dict(original.__globals__, stage=NS(_ACTIVE=[], _FAILED=[]), runner=runner),
    )
    generator = guard(request, tmp_path, monkeypatch)
    before, entered, primary = (sys.getprofile(), sys.gettrace()), False, None
    failure_start = len(stage._FAILED)
    try:
        next(generator)
        entered = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup = inherited.inherited.inherited.cleanup._drain_guard
        FunctionType(
            cleanup.__code__,
            dict(cleanup.__globals__, _write_failure_diagnostics=lambda *args: None),
        )(generator, entered, (), tmp_path, required_hooks=before, primary=primary)
        for index, context in enumerate(stage._FAILED[failure_start:]):
            (tmp_path / ("import-capture-failure-" + str(index) + ".json")).write_text(
                json.dumps(
                    dict(
                        primary=None if context.primary is None else str(context.primary),
                        guard_failure=getattr(context, "guard_failure", None),
                        capture_errors=[(item[0], str(item[1])) for item in context.capture_errors],
                        raw_guard_events=len(context.guard_raw),
                        published=context.published,
                        hooks_restored=context.hooks_restored,
                        monitor_restored=context.monitor_restored,
                    )
                )
            )


def test_source_plan_has_no_decorator_or_native_execution_release():
    plan = stage.source_plan()
    assert not plan["original_factory_generator_or_wrapper_invoked_by_observer"]
    assert not plan["retrospective_or_decoded_or_supplied_wrapper_authority"]
    assert plan["no_Parameters_phase_material_or_scientific_admission"]


@pytest.mark.parametrize("copied", (False, True))
def test_context_wraps_dispatch_refuses_before_backend_snapshots(monkeypatch, copied):
    original = functools.wraps
    calls, snapshots = [], []

    def foreign(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    replacement = (
        FunctionType(
            original.__code__,
            original.__globals__,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        if copied
        else foreign
    )
    if copied:
        replacement.__kwdefaults__ = original.__kwdefaults__

    def snapshot_held(function):
        snapshots.append(function)
        pytest.fail("A foreign wraps dispatch may not become a backend baseline")

    monkeypatch.setattr(contextlib, "wraps", replacement)
    monkeypatch.setattr(stage, "_function_state", snapshot_held)
    with pytest.raises(ValueError, match="Original contextmanager wraps dispatch required"):
        stage._context_backend(NS())
    assert calls == [] and snapshots == []


def test_context_wraps_dispatch_baseline_then_use_drift_refuses_without_call(monkeypatch):
    functions = (
        (contextlib.contextmanager, contextlib, "contextmanager"),
        (functools.wraps, functools, "wraps"),
    )
    backend = NS(
        context_functions=functions,
        context_states=tuple(stage._function_state(function) for function, _, _ in functions),
    )
    stage._context_bindings(backend)
    calls = []

    def foreign(*args, **kwargs):
        calls.append(1)
        return functools.wraps(*args, **kwargs)

    monkeypatch.setattr(contextlib, "wraps", foreign)
    with pytest.raises(ValueError, match="Original contextmanager wraps dispatch changed"):
        stage._context_bindings(backend)
    assert calls == []


@pytest.fixture
def context_call_model(monkeypatch):
    """Actual CALL/PY_START on stdlib only; conditional targets issue no authority."""
    module = ModuleType("blocked_context_call_model")
    functions = (
        (contextlib.contextmanager, contextlib, "contextmanager"),
        (functools.wraps, functools, "wraps"),
    )
    backend = NS(
        context_factory=contextlib.contextmanager,
        context_functions=functions,
        context_states=tuple(stage._function_state(fn) for fn, _, _ in functions),
    )
    proof = NS(
        backend=backend,
        frames={},
        context_calls=[],
        context_call_raw=[],
        capture_error=None,
    )
    monkeypatch.setattr(stage, "validate_import_guards", lambda context: None)

    def target(function, frame):
        if type(function) is not FunctionType or function.__name__ != "noop_context":
            return None
        ancestor = frame.f_back
        while ancestor is not None and ancestor.f_globals is not vars(module):
            ancestor = ancestor.f_back
        return ((None, "noop_context"), module, ancestor)

    monkeypatch.setattr(stage, "_target", target)

    def run(edge, copied=False):
        events, entered, restorations = [], [], []
        owner = NS(target=((None, "noop_context"), module, None), row=None)

        def register(frame, generator):
            owner.row = NS(output=generator)
            proof.frames[id(frame)] = (frame, "context", owner)

        original = backend.context_factory
        copy = FunctionType(
            original.__code__,
            original.__globals__,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        copy.__kwdefaults__ = original.__kwdefaults__
        selected = copy if copied else original
        vars(module).update(contextmanager=selected, factory=selected, sys=sys, register=register)
        text = "def noop_context():\n    yield\n" + (
            "result = contextmanager(noop_context)\n"
            if edge == "original"
            else "def reconstruct(generator, func_contextmanager):\n"
            "    register(sys._getframe(), generator)\n"
            "    return func_contextmanager(generator)\n"
            "result = reconstruct(noop_context, factory)\n"
        )
        code = compile(text, "<blocked-stdlib-context-call-model>", "exec")
        monitor = sys.monitoring
        tool = next(i for i in range(6) if monitor.get_tool(i) is None)
        label = "blocked stdlib context CALL witness"
        witnesses = []

        def inherited_call(caller, function):
            if copied and function is copy:
                if edge == "original":
                    vars(module)["contextmanager"] = original
                    restored = vars(module)["contextmanager"] is original
                else:
                    caller.f_locals["func_contextmanager"] = original
                    restored = caller.f_locals["func_contextmanager"] is original
                restorations.append(restored)

        def called(caller_code, offset, function, arg0):
            if type(function) is not FunctionType or function.__code__ is not original.__code__:
                return
            caller = sys._getframe(1)
            if caller.f_globals is not vars(module):
                return
            assert caller.f_code is caller_code
            events.append((function is copy, arg0.__name__))
            # Real selected CALL arguments remain unchanged after this actual
            # inherited callback restores the live caller's lookup/local.
            inherited_call(caller, function)
            stage._context_call(proof, caller, function, arg0, offset)

        def start(entered_code, offset):
            if entered_code is not original.__code__:
                return
            frame = sys._getframe(1)
            if frame.f_back.f_globals is not vars(module):
                return
            witness = stage._context_call_entry(
                proof,
                frame,
                edge,
                frame.f_locals["func"],
                None if edge == "original" else owner,
            )
            if edge == "original":
                witness.owner = owner
            witnesses.append(witness)
            entered.append(frame)

        def returned(returned_code, offset, value):
            if returned_code is original.__code__:
                frame = sys._getframe(1)
                for witness in witnesses:
                    if witness.frame is frame:
                        witness.output, witness.returned = value, True

        callbacks = []
        prior_events = monitor.get_events(tool)
        monitor.use_tool_id(tool, label)
        error = None
        try:
            for event, callback in (
                (monitor.events.CALL, called),
                (monitor.events.PY_START, start),
                (monitor.events.PY_RETURN, returned),
            ):
                callbacks.append((event, monitor.register_callback(tool, event, callback)))
            monitor.set_events(
                tool, monitor.events.CALL | monitor.events.PY_START | monitor.events.PY_RETURN
            )
            exec(code, vars(module))
        except BaseException as failure:
            error = failure
        finally:
            monitor.set_events(tool, prior_events)
            for event, callback in callbacks:
                monitor.register_callback(tool, event, callback)
            monitor.free_tool_id(tool)
        return NS(
            error=error,
            events=events,
            entered=entered,
            restorations=restorations,
            witness=None if not witnesses else witnesses[0],
            owner=owner,
            proof=proof,
            result=vars(module).get("result"),
            original=original,
            selected=selected,
        )

    return run


@pytest.mark.parametrize("edge", ("original", "reconstructed"))
@pytest.mark.parametrize("copied", (False, True))
def test_context_call_selected_identity_survives_caller_self_restoration(
    context_call_model, edge, copied
):
    observed = context_call_model(edge, copied)
    assert observed.events == [(copied, "noop_context")]
    if copied:
        assert observed.restorations == [True]
        assert observed.entered == [] and observed.witness is None
        assert type(observed.error) is ValueError
        assert str(observed.error) == "Actual selected original contextmanager callable required"
        assert len(observed.proof.context_call_raw) == 1
        assert observed.proof.context_calls == []
    else:
        assert observed.error is None and observed.restorations == []
        witness = observed.witness
        assert witness is not None and len(observed.entered) == 1
        assert witness.callee is observed.original and witness.returned
        assert witness.output is observed.result
        stage._context_call_check(
            observed.proof,
            witness,
            witness.frame,
            edge,
            witness.arg0,
            observed.owner,
            observed.result,
        )


@pytest.mark.parametrize("drift", ("arg0", "caller", "callee", "record"))
def test_context_call_closed_witness_edges_refuse_drift(context_call_model, drift):
    observed = context_call_model("reconstructed")
    assert observed.error is None
    witness = observed.witness
    args = (
        observed.proof,
        witness,
        witness.frame,
        "reconstructed",
        witness.arg0,
        observed.owner,
        observed.result,
    )
    stage._context_call_check(*args)
    if drift == "record":
        observed.proof.context_calls.clear()
    else:
        setattr(witness, drift, object())
    with pytest.raises(ValueError, match="Retained actual contextmanager CALL witness changed"):
        stage._context_call_check(*args)


def test_pinned_native_type_check_is_identity_not_a_preclass_beartype_factory():
    path = stage.network.NATIVE / "betse/util/type/types.py"
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "9b8c83555b06a18bfb252d236c95c0d625699237e5c5cc671c085d282fc2c089"
    )
    method = next(
        node
        for node in ast.parse(raw).body
        if isinstance(node, ast.FunctionDef) and node.name == "type_check"
    )
    assert len(method.body) == 1 and isinstance(method.body[0], ast.Return)
    assert isinstance(method.body[0].value, ast.Name) and method.body[0].value.id == "func"


@pytest.mark.parametrize("enabled", (False, None, 1, "1"))
def test_release_precedes_library_import_or_observation(monkeypatch, enabled):
    monkeypatch.setattr(stage, "_backend", lambda: pytest.fail("No original library import"))
    with pytest.raises(stage.WrapperAuthorityRejected) as caught:
        with stage.observing_native_imports(enabled=enabled):
            pytest.fail("No operation before release")
    assert caught.value.stage == "release"


def test_existing_target_module_cannot_be_issued_retrospectively(monkeypatch):
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setitem(sys.modules, "betse.science.chemistry.networks", ModuleType("old"))
    monkeypatch.setattr(
        stage, "_backend", lambda: pytest.fail("No library import after fresh refusal")
    )
    with pytest.raises(stage.WrapperAuthorityRejected) as caught:
        with stage.observing_native_imports(enabled=True):
            pytest.fail("No old import promotion")
    assert caught.value.stage == "fresh"


@pytest.fixture
def factory_model(monkeypatch):
    """Actual monitoring events, explicit non-native factory/codegen bodies."""

    class Conf:
        __slots__ = ()

    class Meta:
        __slots__ = ("func", "conf", "cls_stack", "func_annotations")

    class Toy:
        def method(self, value):
            pytest.fail("The produced wrapper/delegate must NEVER execute")

    original, conf = Toy.method, Conf()
    state = NS(error=None, none=False, generate_none=False, made=None, load=None, after=None)

    def hidden_helper():
        pytest.fail("Neither hidden type-check helpers nor native delegates may execute")

    def generate(meta):
        if state.generate_none:
            return None
        return (
            "def method(*args, __beartype_func=__beartype_func, "
            "__beartype_check_meta=__beartype_check_meta, "
            "__beartype_helper=__beartype_helper, **kwargs):\n"
            " return __beartype_func(*args, **kwargs)\n"
        )

    def make(*, func_name, func_code, func_locals, func_wrapped, func_globals=None):
        if state.error is not None:
            raise state.error
        if state.none:
            return None
        func_globals = {} if func_globals is None else func_globals
        func_filename = "<explicit-toy-wrapper-not-native>"
        func_code_compiled = compile(func_code.strip(), func_filename, "exec", dont_inherit=True)
        exec(func_code_compiled, func_globals, func_locals)
        function = func_locals[func_name]
        function.__wrapped__ = func_wrapped
        function.__annotations__ = func_wrapped.__annotations__
        state.made = function
        return function

    def decorator(func, conf, wrapper=None, **kwargs):
        text = generate(None)
        if not text:
            return func
        meta = Meta()
        meta.func, meta.conf, meta.cls_stack = func, conf, kwargs.get("cls_stack")
        meta.func_annotations = func.__annotations__
        scope = {
            "__beartype_func": func,
            "__beartype_check_meta": meta,
            "__beartype_helper": hidden_helper,
        }
        function = make(func_name="method", func_code=text, func_locals=scope, func_wrapped=func)
        if function is not None:
            function.__beartype_wrapper = True
        return function

    functions = dict(decorator=decorator, generate=generate, make=make)
    backend = NS(
        functions=functions,
        states=tuple((fn, stage._function_state(fn)) for fn in functions.values()),
        metadata=Meta,
        configuration=Conf,
    )
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "Toy", Toy, raising=False)
    monkeypatch.setattr(stage, "_backend", lambda: backend)
    monkeypatch.setattr(
        stage,
        "_target",
        lambda fn, frame: (("Toy", "method"), module, frame.f_back) if fn is original else None,
    )
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setattr(stage, "_ISSUED", stage.WeakKeyDictionary())
    monkeypatch.setattr(stage, "_import_ancestry", lambda *args: None)
    before = sys.getprofile(), sys.gettrace()

    def source_body():
        Toy.method = decorator(original, conf, cls_stack=(Toy,))

    def run():
        with stage.observing_native_imports(enabled=True) as context:
            if state.load is not None:
                state.load()
            source_body()
            if state.after is not None:
                state.after()
        assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
        return context, Toy.method

    return NS(
        run=run,
        state=state,
        original=original,
        owner=Toy,
        conf=conf,
        backend=backend,
        source_body=source_body,
    )


def test_monitored_toy_factory_returns_actual_wrapper_without_invoking_it(factory_model):
    model = factory_model
    context, wrapper = model.run()
    assert context.record.source_completed and context.record.factories == 1
    assert context.record.generated == 1
    assert "__beartype_conf" not in wrapper.__kwdefaults__
    assert context.hooks_restored and context.monitor_restored
    assert (
        stage.validate(wrapper, model.original, owner=model.owner, attribute="method")
        is model.original
    )


def test_equal_copied_wrapper_and_spoofed_wrapped_are_unissued(factory_model):
    model = factory_model
    _, wrapper = model.run()
    copied = FunctionType(wrapper.__code__, wrapper.__globals__)
    copied.__kwdefaults__ = dict(wrapper.__kwdefaults__)
    copied.__wrapped__ = model.original
    copied.__beartype_wrapper = True
    with pytest.raises(stage.WrapperAuthorityRejected) as caught:
        stage.validate(copied, model.original, owner=model.owner, attribute="method")
    assert caught.value.stage == "unissued"


@pytest.mark.parametrize(
    "drift",
    (
        "delegate",
        "defaults",
        "class_slot",
        "cached_builtins",
        "meta_func",
        "meta_conf",
        "meta_stack",
        "meta_annotations",
        "original_code",
        "original_defaults",
        "hidden_helper_code",
        "module_export",
    ),
)
def test_valid_wrapper_baseline_then_exact_association_drift_refuses(factory_model, drift):
    model = factory_model
    _, wrapper = model.run()
    assert (
        stage.validate(wrapper, model.original, owner=model.owner, attribute="method")
        is model.original
    )
    if drift == "delegate":
        wrapper.__wrapped__ = lambda: None
    elif drift == "defaults":
        wrapper.__kwdefaults__["__beartype_func"] = lambda: None
    elif drift == "class_slot":
        model.owner.method = model.original
    elif drift == "cached_builtins":
        wrapper.__globals__["__builtins__"] = dict(vars(builtins))
    elif drift == "original_code":
        model.original.__code__ = (lambda: None).__code__
    elif drift == "original_defaults":
        model.original.__defaults__ = (None,)
    elif drift == "hidden_helper_code":
        wrapper.__kwdefaults__["__beartype_helper"].__code__ = (lambda: None).__code__
    elif drift == "module_export":
        sys.modules[__name__].Toy = type("Toy", (), {})
    else:
        field = dict(
            meta_func="func",
            meta_conf="conf",
            meta_stack="cls_stack",
            meta_annotations="func_annotations",
        )[drift]
        setattr(wrapper.__kwdefaults__["__beartype_check_meta"], field, object())
    with pytest.raises(ValueError):
        stage.validate(wrapper, model.original, owner=model.owner, attribute="method")


def test_original_factory_unwind_primary_and_cause_survive_monitoring(factory_model):
    model = factory_model
    primary = ValueError("original toy factory")
    primary.__cause__ = OSError("original cause")
    model.state.error = primary
    with pytest.raises(ValueError) as caught:
        model.run()
    assert caught.value is primary and primary.__cause__.args == ("original cause",)
    assert not stage._ACTIVE


def test_normal_none_factory_return_is_incomplete_not_native_failure(factory_model):
    factory_model.state.none = True
    with pytest.raises(stage.WrapperAuthorityRejected) as caught:
        factory_model.run()
    assert caught.value.stage == "capture"
    assert caught.value.partial.capture_error is not None
    assert not stage._ISSUED


def test_normal_none_codegen_return_does_not_acquire_identity_authority(factory_model):
    factory_model.state.generate_none = True
    with pytest.raises(stage.WrapperAuthorityRejected) as caught:
        factory_model.run()
    assert caught.value.stage == "capture" and not stage._ISSUED


@pytest.mark.parametrize("drift", ("none", "code", "loader", "missing_return"))
def test_profiled_toy_loader_return_is_required_before_factory_ancestry(
    factory_model, monkeypatch, drift
):
    model = factory_model
    imported = ModuleType("betse.science.chemistry.networks")

    class Loader:
        name = imported.__name__
        path = str(stage.network.NATIVE / "betse/science/chemistry/networks.py")

        def get_code(self, fullname):
            assert fullname == self.name
            return (lambda: None).__code__ if drift == "code" else model.source_body.__code__

    loader = Loader()
    imported.__spec__ = NS(loader=object() if drift == "loader" else loader)
    imported.Toy = model.owner
    model.backend.loader_type = Loader
    model.backend.functions["loader"] = Loader.get_code
    model.backend.states = tuple(
        (fn, stage._function_state(fn)) for fn in model.backend.functions.values()
    )
    monkeypatch.setattr(stage, "_import_ancestry", _REAL_IMPORT_ANCESTRY)
    monkeypatch.setattr(
        stage,
        "_target",
        lambda fn, frame: (
            (("Toy", "method"), imported, frame.f_back) if fn is model.original else None
        ),
    )
    if drift != "missing_return":
        model.state.load = lambda: loader.get_code(imported.__name__)
    # Even the unchanged function-code fixture is not an actual imported module.
    # Genuine positive loader/module publication is covered by pinned Beartype below.
    with pytest.raises(ValueError, match="module|loader/code/module ancestry"):
        model.run()
    assert model.state.made is None and not stage._ISSUED


_REAL_IMPORT_ANCESTRY = stage._import_ancestry


@pytest.mark.parametrize("hook", ("profile", "trace"))
def test_guard_loss_after_factory_refuses_publication_and_recovers_both_hooks(factory_model, hook):
    model = factory_model
    before = sys.getprofile(), sys.gettrace()

    def inherited_profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)

    def inherited_trace(frame, event, arg):
        if before[1] is not None:
            before[1](frame, event, arg)
        return inherited_trace

    model.state.after = lambda: sys.setprofile(None) if hook == "profile" else sys.settrace(None)
    try:
        sys.setprofile(inherited_profile)
        sys.settrace(inherited_trace)
        with pytest.raises(stage.WrapperAuthorityRejected) as caught:
            model.run()
        assert caught.value.stage == "cleanup"
        assert caught.value.partial.hook_losses
        assert sys.getprofile() is inherited_profile and sys.gettrace() is inherited_trace
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    assert not stage._ISSUED and not stage._ACTIVE


def test_return_capture_error_does_not_replace_original_toy_unwind(factory_model, monkeypatch):
    model = factory_model
    primary = ValueError("original toy maker error")
    primary.__cause__ = OSError("original cause")
    model.state.error = primary
    observed = stage._observe

    def capture(context, frame, event, value):
        observed(context, frame, event, value)
        if event == "unwind":
            raise KeyError("secondary capture")

    monkeypatch.setattr(stage, "_observe", capture)
    with pytest.raises(ValueError) as caught:
        model.run()
    assert caught.value is primary and primary.__cause__.args == ("original cause",)
    context = stage._FAILED[-1]
    assert context.primary is primary and context.capture_errors
    assert context.source_errors[-1][2] is primary
    assert not stage._ISSUED and context.hooks_restored and context.monitor_restored


@pytest.mark.parametrize("drift", ("none", "hidden_binding"))
def test_actual_profiled_wrapper_runtime_resolves_only_issued_delegate_and_scope(
    factory_model, drift
):
    model = factory_model
    _, wrapper = model.run()
    network = inherited.stage
    original = NS(
        source_functions=(wrapper, model.original),
        dynamic_callbacks=(),
        functions={("Toy", "method"): model.original},
        classes={"Toy": model.owner},
    )
    runtime = NS(original=original, primary=None, invalid=False)
    before, resolved = sys.getprofile(), []

    class StopBeforeBody(Exception):
        pass

    def profile(frame, event, arg):
        if before is not None:
            before(frame, event, arg)
        if event == "call" and frame.f_code is wrapper.__code__:
            resolved.append(network._runtime_resolution(runtime, frame))
            raise StopBeforeBody

    receiver, value = object(), object()
    try:
        sys.setprofile(profile)
        if drift == "none":
            with pytest.raises(StopBeforeBody):
                wrapper(receiver, value)
            fn, role, arguments, delegate = resolved[0]
            assert fn is wrapper and role == ("Toy", "method") and delegate is model.original
            assert arguments["self"] is receiver and arguments["value"] is value
        else:
            with pytest.raises(network.MoleculeNetworkRejected, match="hidden wrapper"):
                wrapper(receiver, value, __beartype_func=lambda: None)
            assert not resolved and runtime.invalid
    finally:
        sys.setprofile(before)


def test_source_acquisition_uses_actual_issued_wrapper_without_invoking_it(factory_model):
    model = factory_model
    _, wrapper = model.run()
    assert (
        inherited.stage._source_entry(wrapper, model.original, model.owner, "method")
        is model.original
    )
    copied = FunctionType(wrapper.__code__, wrapper.__globals__)
    copied.__kwdefaults__ = dict(wrapper.__kwdefaults__)
    copied.__wrapped__ = model.original
    with pytest.raises(inherited.stage.MoleculeNetworkRejected) as caught:
        inherited.stage._source_entry(copied, model.original, model.owner, "method")
    assert caught.value.stage == "wrapper_prerequisite"


@pytest.fixture
def issued_guard_models(monkeypatch):
    """Real guard bodies over conditional registries; no native owner is issued."""
    result = []

    class ConditionalRequest:
        pass

    for module, name in ((tissue, "_account"), (simulator, "_observe"), (callbacks, "_observe")):
        request = ConditionalRequest()
        child = NS(
            request=request,
            active=True,
            thread=stage.get_ident(),
            work=[],
            stage="conditional_software_not_native_authority",
            constructor_codes=set(),
            roles={},
            callback_types=(),
            raw_locals=[],
            observations=[],
            capture_errors=[],
            locals={},
            observation_error=None,
            observation_errors=(),
        )
        registry = stage.WeakKeyDictionary()
        registry[request] = child
        monkeypatch.setattr(module, "_ACTIVE", [child])
        monkeypatch.setattr(module, "_CONSUMED", registry)
        result.append(NS(module=module, name=name, child=child, manager=getattr(module, name)))
    return result


@pytest.mark.parametrize("mode", ("prefix", "nested"))
def test_guard_composition_actual_three_guard_bodies_keep_source_and_parent(
    factory_model, issued_guard_models, mode
):
    model = factory_model
    before = sys.getprofile(), sys.gettrace()
    with stage.observing_native_imports(enabled=True) as context:
        if mode == "prefix":
            rows = [issued_guard_models[i] for i in (0, 1, 1, 2)]
            for index, row in enumerate(rows):
                with row.manager(row.child):
                    stage.validate_import_guards(context)
                    if index == 3:
                        model.source_body()
        else:
            with ExitStack() as stack:
                for row in issued_guard_models:
                    stack.enter_context(row.manager(row.child))
                stage.validate_import_guards(context)
                model.source_body()
    assert len(context.guard_closed) == (4 if mode == "prefix" else 3)
    assert not context.guard_frames
    assert all(row.profile is not None for row in context.guard_closed)
    assert context.published and context.record.factories == 1
    assert context.hooks_restored and context.monitor_restored and not context.hook_losses
    assert (
        stage.validate(model.owner.method, model.original, owner=model.owner, attribute="method")
        is model.original
    )
    assert (sys.getprofile(), sys.gettrace()) == before


@pytest.mark.parametrize(
    "drift",
    (
        "equal_copy",
        "foreign_profile",
        "trace",
        "callback_code",
        "previous",
        "context",
        "registry",
        "thread",
        "body_code",
        "selection",
    ),
)
def test_guard_composition_issued_baseline_then_drift_refuses_before_factory_body(
    factory_model, issued_guard_models, drift
):
    model, child = factory_model, issued_guard_models[0]
    before = sys.getprofile(), sys.gettrace()

    def outer(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)

    sys.setprofile(outer)
    context = None
    try:
        with pytest.raises(ValueError) as caught:
            with stage.observing_native_imports(enabled=True) as context:
                with child.manager(child.child):
                    stage.validate_import_guards(context)  # Real valid baseline first.
                    row = context.guard_frames[-1]
                    cells = dict(
                        zip(row.profile.__code__.co_freevars, row.profile.__closure__, strict=True)
                    )
                    if drift == "equal_copy":
                        replacement = FunctionType(
                            row.profile.__code__,
                            row.profile.__globals__,
                            closure=row.profile.__closure__,
                        )
                        sys.setprofile(replacement)
                    elif drift == "foreign_profile":
                        sys.setprofile(lambda *args: None)
                    elif drift == "trace":
                        sys.settrace(None)
                    elif drift == "callback_code":
                        row.profile.__code__ = row.profile.__code__.replace()
                    elif drift == "previous":
                        cells["previous"].cell_contents = None
                    elif drift == "context":
                        cells["context"].cell_contents = NS(active=True)
                    elif drift == "registry":
                        del child.module._CONSUMED[child.child.request]
                    elif drift == "thread":
                        child.child.thread += 1
                    elif drift == "selection":
                        cells["selected"].cell_contents.clear()
                    else:
                        row.provider.body.__code__ = row.provider.body.__code__.replace()
                    model.source_body()
        assert context.primary is caught.value
        assert context.capture_errors and context.guard_raw
        assert model.state.made is None and not stage._ISSUED
        assert context.hooks_restored and context.monitor_restored and not stage._ACTIVE
    finally:
        # Code mutations are local fixture edits; restore the exact shared definition.
        if context is not None:
            for provider in context.guard_providers.values():
                provider.body.__code__ = provider.state[1]
        sys.setprofile(before[0])
        sys.settrace(before[1])


@pytest.mark.parametrize("kind", ("closed_callback", "reentry"))
def test_guard_composition_no_closed_callback_reuse_or_reentrant_child(
    factory_model, issued_guard_models, kind
):
    model, child = factory_model, issued_guard_models[0]
    with pytest.raises(ValueError) as caught:
        with stage.observing_native_imports(enabled=True) as context:
            with child.manager(child.child):
                stage.validate_import_guards(context)
                row = context.guard_frames[-1]
                if kind == "reentry":
                    with child.manager(child.child):
                        pytest.fail("Reentry must refuse before child setup")
            if kind == "closed_callback":
                sys.setprofile(row.profile)
                model.source_body()
    assert context.primary is caught.value and model.state.made is None
    assert not stage._ISSUED and context.hooks_restored and context.monitor_restored


def test_guard_composition_scope_budget_refuses_before_setup_and_is_not_factory_budget(
    factory_model, issued_guard_models, monkeypatch
):
    model, child = factory_model, issued_guard_models[0]
    monkeypatch.setattr(stage, "MAX_GUARD_SCOPES", 1)
    with pytest.raises(ValueError, match="Bounded exclusive child import guard") as caught:
        with stage.observing_native_imports(enabled=True) as context:
            with child.manager(child.child):
                stage.validate_import_guards(context)
            assert len(context.guard_closed) == 1 and not context.rows
            with child.manager(child.child):
                pytest.fail("Second guard setup must remain blocked")
    assert context.primary is caught.value and model.state.made is None
    assert not stage._ISSUED and context.hooks_restored and context.monitor_restored


@pytest.mark.parametrize("drift", ("selection", "callback_code"))
def test_guard_composition_late_callback_drift_refuses_publication(
    factory_model, issued_guard_models, drift
):
    model, child = factory_model, issued_guard_models[0]
    with pytest.raises(stage.WrapperAuthorityRejected) as caught:
        with stage.observing_native_imports(enabled=True) as context:
            with child.manager(child.child):
                model.source_body()
                row = context.guard_frames[-1]
                assert row.profile is not None and context.rows[0].returned
                if drift == "callback_code":
                    row.profile.__code__ = row.profile.__code__.replace()
                else:
                    cells = dict(
                        zip(row.profile.__code__.co_freevars, row.profile.__closure__, strict=True)
                    )
                    cells["selected"].cell_contents.clear()
    assert caught.value.stage == "capture"
    assert caught.value.__cause__ is context.capture_error
    assert context.record is None and not context.published and not stage._ISSUED
    assert context.hooks_restored and context.monitor_restored


class FalseyPrimary(RuntimeError):
    def __bool__(self):
        return False


@pytest.mark.parametrize("source_failure", (False, True))
def test_guard_composition_unwind_capture_keeps_primary_cause_and_raw(
    factory_model, issued_guard_models, monkeypatch, source_failure
):
    model, row = factory_model, issued_guard_models[0]
    original = FalseyPrimary("actual conditional source error")
    cause = OSError("actual conditional cause")
    original.__cause__ = cause
    secondary = KeyError("secondary guard closure observation")
    if source_failure:
        model.state.error = original
    actual = stage._guard_event

    def observe(context, provider, frame, event, value):
        actual(context, provider, frame, event, value)
        if event != "start":
            raise secondary

    monkeypatch.setattr(stage, "_guard_event", observe)
    with pytest.raises(
        FalseyPrimary if source_failure else stage.WrapperAuthorityRejected
    ) as caught:
        with stage.observing_native_imports(enabled=True) as context:
            with row.manager(row.child):
                model.source_body()
    assert context.primary is caught.value
    if source_failure:
        assert caught.value is original and original.__cause__ is cause
        assert any(raw[1] == "unwind" and raw[2] is original for raw in context.guard_raw)
        assert any(raw[2] is original for raw in context.source_errors)
    else:
        assert caught.value.stage == "capture" and context.record is None
    assert any(item[1] is secondary for item in context.capture_errors)
    assert not stage._ISSUED and context.hooks_restored and context.monitor_restored


def test_guard_composition_inherited_entry_rejection_remains_exact_before_body(
    factory_model, issued_guard_models
):
    model, row = factory_model, issued_guard_models[0]
    primary, cause = FalseyPrimary("inherited entry veto"), OSError("cause")
    before, calls = sys.getprofile(), []

    def inherited_profile(frame, event, arg):
        if before is not None:
            before(frame, event, arg)
        if event == "call" and frame.f_code is model.backend.functions["decorator"].__code__:
            calls.append(frame)
            raise primary from cause

    sys.setprofile(inherited_profile)
    try:
        with pytest.raises(FalseyPrimary) as caught:
            with stage.observing_native_imports(enabled=True) as context:
                with row.manager(row.child):
                    model.source_body()
        assert caught.value is primary and primary.__cause__ is cause and len(calls) == 1
        assert context.primary is primary and model.state.made is None
        assert not context.published and not stage._ISSUED
        assert context.hooks_restored and context.monitor_restored
    finally:
        sys.setprofile(before)


@pytest.fixture
def actual_scoped_import_apis(monkeypatch):
    """Read actual private clone APIs with explicit candidate pin, no producer adoption."""
    pin = hashlib.sha256(stage.Path(stage.__file__).read_bytes()).hexdigest()
    monkeypatch.setattr(preparation, "WRAPPER_OBSERVER_SHA256", pin)
    monkeypatch.setattr(assembly, "WRAPPER_SHA256", pin)
    monkeypatch.setattr(preparation, "_WRAPPER_API", None)
    monkeypatch.setattr(assembly, "_IMPORT_API", None)
    monkeypatch.setattr(sim_run, "_IMPORT_API", None)
    # This fixture runs before the toy factory fixture changes any definitions.
    return (
        vars(stage),
        preparation._wrapper_api(),
        assembly._phase_import_api(),
        sim_run._runtime_import_api(),
    )


@pytest.mark.parametrize("mode", ("prefix", "nested", "dropped_parent"))
def test_guard_composition_all_four_actual_clone_bodies_cover_the_complete_prefix(
    actual_scoped_import_apis, factory_model, issued_guard_models, mode
):
    """Four actual manager bodies with explicit TOY backend/registries, not native authority."""
    model, contexts, scopes = factory_model, [], []
    for api in actual_scoped_import_apis:
        namespace = dict(
            api,
            _backend=stage._backend,
            _target=stage._target,
            _import_ancestry=stage._import_ancestry,
            _ISSUED=stage.WeakKeyDictionary(),
            _ACTIVE=[],
            _FAILED=[],
        )
        for name, function in api.items():
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
        # Toy factories deliberately stay in their test namespace.
        namespace.update(
            _backend=stage._backend, _target=stage._target, _import_ancestry=stage._import_ancestry
        )
        body = api["observing_native_imports"].__wrapped__
        copied = FunctionType(
            body.__code__, namespace, body.__name__, body.__defaults__, body.__closure__
        )
        copied.__kwdefaults__ = body.__kwdefaults__
        for name in (
            "_guard_sources",
            "_guard_binding",
            "_guard_profile",
            "_guard_event",
            "validate_import_guards",
        ):
            assert namespace[name].__code__ is api[name].__code__
            assert namespace[name].__globals__ is namespace
        scopes.append((namespace, contextmanager(copied)))

    def run():
        with ExitStack() as imports:
            for namespace, manager in scopes:
                # Each original API retains its own release flag and private state.
                with pytest.MonkeyPatch.context() as patch:
                    patch.setenv(namespace["RELEASE"], "1")
                    context = imports.enter_context(manager(enabled=True))
                contexts.append(context)
            if mode == "prefix":
                rows = [issued_guard_models[i] for i in (0, 1, 1, 2)]
                for index, row in enumerate(rows):
                    with row.manager(row.child):
                        for (api, _), context in zip(scopes, contexts, strict=True):
                            api["validate_import_guards"](context)
                        if index == 3:
                            model.source_body()
            else:
                with ExitStack() as guards:
                    for row in issued_guard_models:
                        guards.enter_context(row.manager(row.child))
                    for (api, _), context in zip(scopes, contexts, strict=True):
                        api["validate_import_guards"](context)
                    if mode == "dropped_parent":
                        row = contexts[0].guard_frames[-1]
                        cells = dict(
                            zip(
                                row.profile.__code__.co_freevars,
                                row.profile.__closure__,
                                strict=True,
                            )
                        )
                        cells["previous"].cell_contents = None
                    model.source_body()

    if mode == "dropped_parent":
        with pytest.raises(ValueError):
            run()
        assert model.state.made is None
        assert all(not api["_ISSUED"] for api, _ in scopes)
    else:
        run()
        assert all(c.published and c.record.factories == 1 for c in contexts)
        expected = 4 if mode == "prefix" else 3
        assert all(len(c.guard_closed) == expected and not c.guard_frames for c in contexts)
    assert len(contexts) == 4 and len({c.tool for c in contexts}) == 4
    assert all(c.hooks_restored and c.monitor_restored for c in contexts)
    assert all(not api["_ACTIVE"] for api, _ in scopes)
    assert not stage._ISSUED


@pytest.mark.parametrize("variant", runner.LIBRARY_VARIANTS)
def test_publication_pinned_library_lifecycle_and_declared_drift_refusals(variant, tmp_path):
    """Real library factories on synthetic declarations; original methods stay held."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CELLS_", "PYTEST_CURRENT_TEST"))
    }
    environment[runner.LIBRARY_RELEASE] = "1"
    folder = tmp_path / "library"
    command = [
        sys.executable,
        "-B",
        "-m",
        runner.MODULE,
        "--library-probe",
        str(folder),
        "--library-variant",
        variant,
    ]
    result = subprocess.run(
        command, env=environment, text=True, capture_output=True, check=False, timeout=120
    )
    (tmp_path / "library-process.json").write_text(
        json.dumps(
            dict(
                command=command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
    )
    assert result.returncode == 0, result.stderr
    record = json.loads((folder / "library-probe.json").read_text())
    assert record["forbidden"] == [] and record["hooks_restored"]
    assert record["library_calls"] > 0 and record["scientific_credit"] == 0
    assert record["native_or_original_owner_issuance"] is False
    assert record["variant"] == variant and record["module_events"] >= 2
    if (
        variant.startswith("class_method_metaclass_")
        or variant == "class_method_foreign_key_before"
    ):
        assert record["equality_dispatch"] == []
        assert record["primary"]["cause"] == dict(
            type="ValueError", message="Complete original unwrapped source-method header required"
        )
    if variant in (
        "none",
        "self_reference",
        "unselected_class",
        "unselected_helper",
        "class_method_positive",
    ):
        assert record["status"] == "publication_observed"
        expected = 3 if variant.startswith(("unselected_", "class_method_")) else 4
        assert record["validated"] == expected and record["private_published"]
        first = record["rows"][0]
        assert first["no_code"] and first["current_count"] > first["before_count"]
        assert not record["capture_errors"]
    else:
        assert record["status"] == (
            "closed_validation_refused" if variant.endswith("_after") else "publication_refused"
        )
        assert record["validated"] == 0
        assert record["private_published"] is variant.endswith("_after")
        if variant.startswith("class_method_") and variant.endswith("_before"):
            assert len(record["observer_edits"]) == 1
            assert record["observer_edits"][0][0] == variant
        if variant.endswith("_after"):
            assert record["validation_attempts"] == 1
        if variant == "conf_cache":
            assert record["cached_repr_before"] is None
        if variant == "module_unwind":
            assert record["primary"] == dict(
                type="RuntimeError",
                message="synthetic module unwind",
                cause=dict(type="OSError", message="source cause"),
            )
            assert record["source_primary_identity"] and record["source_cause_identity"]


def test_counter_release_precedes_any_original_import_or_directory(tmp_path, monkeypatch):
    monkeypatch.delenv(runner.COUNTER_RELEASE, raising=False)
    with pytest.raises(ValueError, match="Explicit CPU5 pinned-counter metadata release"):
        runner.counter_probe(tmp_path / "held")
    assert not (tmp_path / "held").exists()


def test_bootstrap_release_precedes_runtime_import_or_directory(tmp_path, monkeypatch):
    monkeypatch.delenv(runner.BOOTSTRAP_RELEASE, raising=False)
    with pytest.raises(ValueError, match="Explicit CPU5 six-API metadata release"):
        runner.bootstrap_probe(tmp_path / "held")
    assert not (tmp_path / "held").exists()


def test_bootstrap_genuine_six_api_order_and_actual_context_export(tmp_path):
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_"))}
    environment[runner.BOOTSTRAP_RELEASE] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        (
            environment["PYTHONPATH"],
            "/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages",
            "/mnt/workspaces/Cells/venv-cpu/lib/python3.13/site-packages",
        )
    )
    folder = tmp_path / "bootstrap"
    command = [
        "/mnt/workspaces/Cells/venv-betse/bin/python",
        "-B",
        "-m",
        runner.MODULE,
        "--bootstrap-probe",
        str(folder),
        "--bootstrap-runner-import",
    ]
    result = subprocess.run(
        command, env=environment, text=True, capture_output=True, check=False, timeout=420
    )
    (tmp_path / "bootstrap-process.json").write_text(
        json.dumps(
            dict(
                command=command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
    )
    assert result.returncode == 0, result.stderr
    record = json.loads((folder / "bootstrap-probe.json").read_text())
    assert record["actual_api_order"] == list(runner.BOOTSTRAP_ORDER)
    assert len(record["operations"]) == 6
    assert all(row["status"] == "returned" for row in record["operations"])
    assert record["completed"] and record["primary"] is None and record["later_errors"] == []
    assert record["proposed_corrected_bootstrap_sequence"]
    assert not record["original_current_route_has_no_runner_import"]
    (added,) = record["additional_native_metadata_imports"]
    assert added["native_module_issuance_completed"] is True
    assert added["parameter_import_registry_ready"] is True
    assert added["module"] == "betse.science.simrunner" and added["status"] == "returned"
    assert added["after_real_six_APIs"] and not added["constructor_or_method_invocation"]
    assert (
        record["shared_writer_review"]["sha256"]
        == "2f6b64bb8cfb7a7eb70f203e51f1444849d7c0ed19adc580b02d044b1c799af0"
    )
    assert record["writer_lease"]["retained_to_process_exit"]
    assert type(record["writer_lease"]["descriptor"]) is int
    assert record["writer_lease"]["descriptor"] >= 0
    assert record["filesystem"]["failures"] == []
    assert record["filesystem"]["first_error"] is None
    assert record["filesystem"]["lifetime"] == "through_worker_process_exit"
    assert record["filesystem"]["temporary_directory"]["path"] == str(folder / "runtime-cache/tmp")
    assert record["metadata_environment"]["historical_Matplotlib_cache_is_not_a_write_root"]
    assert len(record["metadata_setup_operations"]) == 3
    assert all(row["status"] == "returned" for row in record["metadata_setup_operations"])
    assert record["forbidden"] == [] and record["hooks_restored"] and record["tools_restored"]
    assert len(record["actual_auxiliary_owners"]) == 3
    assert [row["label"] for row in record["contexts"]] == [
        "runner",
        "phase",
        "runtime",
        "molecule",
    ]
    assert all(
        row["published"]
        and row["hooks_restored"]
        and row["monitor_restored"]
        and not row["active"]
        and row["active_registry"] == 0
        and not row["capture_errors"]
        and row["guard_closed"] == 4
        and row["original_monitor"] == row["final_monitor"]
        for row in record["contexts"]
    )
    runtime = record["contexts"][2]
    assert len(runtime["exports"]) == 1
    export = runtime["exports"][0]
    assert export["target"] == [None, "noop_context"]
    assert export["exact_published_export"] and export["exact_wrapped_generator"]
    assert export["actual_export"]["identity"] != export["inner"]["identity"]
    assert export["transform_returned"]
    assert export["helper_frame"][1] == "_beartype_func_contextlib_contextmanager"
    assert export["factory_frame"] == ["/usr/lib/python3.13/contextlib.py", "contextmanager"]
    assert export["source_factory_frame"] == ["/usr/lib/python3.13/contextlib.py", "contextmanager"]
    assert export["exact_source_factory_return"]
    assert export["exact_factory_annotation_return"]
    assert record["native_work"] and record["library_work"] and record["owned_work"]
    assert record["auxiliary_parameters_or_simulator_are_not_world_or_INIT_or_SIM_authority"]
    assert record["numerical_RNG_solve_or_biological_credit"] == 0


@pytest.mark.parametrize("variant", runner.LIFECYCLE_VARIANTS)
def test_lifecycle_genuine_nested_import_and_complete_teardown(variant, tmp_path):
    environment = {
        k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_CURRENT_TEST"))
    }
    environment[runner.COUNTER_RELEASE] = "1"
    folder = tmp_path / "counter"
    command = [
        sys.executable,
        "-B",
        "-m",
        runner.MODULE,
        "--lifecycle-probe",
        str(folder),
        "--lifecycle-variant",
        variant,
    ]
    result = subprocess.run(
        command, env=environment, text=True, capture_output=True, check=False, timeout=120
    )
    (tmp_path / "counter-process.json").write_text(
        json.dumps(
            dict(
                command=command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
    )
    assert result.returncode == 0, result.stderr
    record = json.loads((folder / "counter-probe.json").read_text())
    assert record["forbidden"] == [] and record["hooks_restored"]
    assert record["foreign_wraps_calls"] == []
    assert [s["label"] for s in record["observer_scopes"]] == [
        "runner",
        "phase",
        "runtime",
        "molecule",
    ]
    assert record["all_tools_restored"]
    if variant in runner.CONTEXT_VARIANTS:
        positive = variant == "nested_export"
        assert all(
            s["hooks_restored"]
            and s["monitor_restored"]
            and not s["active"]
            and s["active_registry_entries"] == 0
            and not s["cleanup"]
            for s in record["observer_scopes"]
        )
        early = variant in (
            "nested_export_factory",
            "nested_export_input_equal",
            "nested_export_wraps",
        )
        if not early:
            assert len(record["export_observations"]) == 1
            export = record["export_observations"][0]
            assert export["scope"] == "runtime" and export["target"] == [None, "noop_context"]
            assert not export["actual_export_is_factory_output"]
            assert export["export_wrapped_is_factory_output"]
            assert export["export_code"] == [
                "/usr/lib/python3.13/contextlib.py",
                "contextmanager.<locals>.helper",
            ]
        assert record["export_edits"] == ([] if positive else [variant])
        assert record["actual_counter"] == (0 if early else 1)
        assert record["results"] == ([] if early else ["__DefaultDict1"])
        if positive:
            assert record["primary"] is None and record["published"]
            assert record["validations"] == 9
            assert all(s["published"] for s in record["observer_scopes"])
        else:
            expected_reason = {
                "nested_export_foreign": "Actual imported owner/export method changed",
                "nested_export_equal": "Actual imported owner/export method changed",
                "nested_export_closed": "Actual imported owner/export method changed",
                "nested_export_retarget": "Actual retained contextmanager reconstruction changed",
                "nested_export_record": "Actual retained contextmanager reconstruction changed",
                "nested_export_code": "Actual contextmanager export/closure/delegate required",
                "nested_export_input": "Actual retained contextmanager reconstruction changed",
                "nested_export_factory": "Original contextmanager runtime export changed",
                "nested_export_dispatch": "Actual source/closure/default/builtin binding changed",
                "nested_export_origin": "Actual retained contextmanager reconstruction changed",
                "nested_export_input_equal": (
                    "Actual original contextmanager factory return required"
                ),
                "nested_export_annotation_after": (
                    "Actual source/closure/default/builtin binding changed"
                ),
                "nested_export_wraps": "Actual source/closure/default/builtin binding changed",
            }[variant]
            if variant == "nested_export_input_equal":
                assert record["capture_errors"][0] == ["start", "ValueError", expected_reason]
                assert record["primary"] == dict(
                    type="WrapperAuthorityRejected",
                    message="Incomplete factory capture prevents more work",
                )
            else:
                assert record["primary"] == dict(type="ValueError", message=expected_reason)
            if variant == "nested_export_closed":
                assert all(s["published"] for s in record["observer_scopes"])
                assert record["validations"] == 6
            else:
                assert not record["observer_scopes"][2]["published"]
                assert record["validations"] == 0
        return
    positive = variant in (
        "nested_counter",
        "nested_all_counters",
        "nested_no_effect",
        "nested_prefix",
        "nested_guards",
    )
    if positive or variant in (
        "nested_exception",
        "primary_cleanup_failure",
        "teardown_binding_drift",
    ):
        assert all(
            s["monitor_restored"] and s["monitor_original"] == s["monitor_final"]
            for s in record["observer_scopes"]
        )
    if positive:
        assert len(record["cleanup_samples"]) == 4
        assert all(
            s["hooks_restored"]
            and s["monitor_restored"]
            and s["original"] == s["final"]
            and s["cleanup"] == []
            and s["hook_losses"] == 0
            for s in record["cleanup_samples"]
        )
    if variant in (
        "nested_exception",
        "primary_cleanup_failure",
        "bookkeeping_id_primary",
        "bookkeeping_values_falsey",
    ):
        assert record["source_primary_identity"] and record["source_cause_identity"]
        assert record["primary"] == dict(
            type="FalseyLifecycleError"
            if variant == "bookkeeping_values_falsey"
            else "RuntimeError",
            message="counter source unwind",
        )
        assert all(not s["published"] for s in record["observer_scopes"])
        if variant == "primary_cleanup_failure":
            assert any(
                label == "hook_restore" and error == "OSError"
                for s in record["observer_scopes"]
                for label, error in s["cleanup"]
            )
    elif positive:
        assert record["primary"] is None and record["published"]
        assert record["validations"] == 8
        assert all(s["published"] for s in record["observer_scopes"])
        assert record["fixture_recovery"] == []
    else:
        assert all(not s["published"] for s in record["observer_scopes"])
        if variant == "teardown_binding_drift":
            assert record["primary"] == dict(
                type="ValueError", message="Actual source/closure/default/builtin binding changed"
            )
        elif variant == "publication_mask":
            assert record["primary"] == dict(
                type="WrapperAuthorityRejected", message="Import observer final monitoring changed"
            )
            assert record["boundary_hits"][0]["hooks_unchanged"]
            assert record["boundary_hits"][0]["before"] != record["boundary_hits"][0]["after"]
            assert not record["observer_scopes"][-1]["monitor_restored"]
            assert (
                record["observer_scopes"][-1]["cleanup_monitor_final"]
                == record["observer_scopes"][-1]["monitor_original"]
            )
            assert (
                record["observer_scopes"][-1]["monitor_final"]
                == record["observer_scopes"][-1]["publication_monitor_final"]
            )
            assert (
                record["observer_scopes"][-1]["publication_monitor_final"]
                != record["observer_scopes"][-1]["monitor_original"]
            )
        elif variant.startswith("publication_"):
            assert record["primary"] == dict(
                type="WrapperAuthorityRejected", message="Import observer final hooks changed"
            )
        else:
            assert record["primary"] == dict(
                type="WrapperAuthorityRejected", message="Import observer cleanup incomplete"
            )
        inner = record["observer_scopes"][-1]
        if variant in ("own_events", "own_callback", "own_local", "own_tool"):
            assert inner["monitor_losses"] > 0
        elif variant == "foreign_tool":
            assert not inner["monitor_restored"]
        elif variant in ("profile_drop", "trace_change", "setter_failure"):
            assert inner["hook_losses"] > 0
        if variant in (
            "getter_failure",
            "setter_failure",
            "callback_restore_failure",
            "free_failure",
        ):
            assert inner["cleanup"]
        if variant in ("callback_restore_failure", "free_failure", "teardown_binding_drift"):
            assert len(record["fault_calls"]) == 1
    if variant.startswith("bookkeeping_"):
        assert len(record["boundary_hits"]) == 1 and record["boundary_error_retained"]
        assert all(
            not s["active"] and s["active_registry_entries"] == 0 for s in record["observer_scopes"]
        )
    if variant.startswith("publication_"):
        assert len(record["boundary_hits"]) == 1
        assert all(s["issued_entries"] == 0 for s in record["observer_scopes"])
    expected = 0 if variant == "nested_no_effect" else 1
    assert record["actual_counter"] == expected
    assert record["results"] == ([] if expected == 0 else ["__DefaultDict1"])
    assert [s["counter_effects"] for s in record["observer_scopes"]] == (
        [1, 1, 1, 1]
        if variant == "nested_all_counters"
        else [0, 0, 0, 0]
        if expected == 0
        else [0, 0, 1, 0]
    )
    if variant in ("nested_prefix", "nested_guards"):
        assert record["conditional_guard_code_only_no_native_owner"]
        assert all(
            s["guard_closed"] == (4 if variant == "nested_prefix" else 3)
            for s in record["observer_scopes"]
        )
        assert record["guard_model_work"][-1] > 0


@pytest.mark.parametrize(
    "observer,variant",
    (
        tuple(
            (observer, variant)
            for observer in runner.COUNTER_OBSERVERS
            for variant in ("none", "counter_after", "original_defaults", "foreign_body")
        )
        + tuple(
            ("molecule", variant)
            for variant in runner.COUNTER_VARIANTS
            if variant not in ("none", "counter_after", "original_defaults", "foreign_body")
        )
    ),
)
def test_counter_pinned_helper_effect_and_exact_drift_refusals(observer, variant, tmp_path):
    environment = {
        k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_CURRENT_TEST"))
    }
    environment[runner.COUNTER_RELEASE] = "1"
    folder = tmp_path / "counter"
    command = [
        sys.executable,
        "-B",
        "-m",
        runner.MODULE,
        "--counter-probe",
        str(folder),
        "--counter-observer",
        observer,
        "--counter-variant",
        variant,
    ]
    result = subprocess.run(
        command, env=environment, text=True, capture_output=True, check=False, timeout=120
    )
    (tmp_path / "counter-process.json").write_text(
        json.dumps(
            dict(
                command=command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
    )
    assert result.returncode == 0, result.stderr
    record = json.loads((folder / "counter-probe.json").read_text())
    assert record["forbidden"] == [] and record["hooks_restored"] and record["observer_restored"]
    assert record["variant"] == variant and record["observer"] == observer
    assert record["native_source_pins"] == runner.COUNTER_IMPORTS
    assert record["library_work"] and record["metadata_work"]
    assert record["genuine_INIT_phase_geometry_or_scientific_credit"] == 0
    attempts = record["counter_attempts"]
    if variant in ("none", "repeated"):
        count = 3 if variant == "repeated" else 1
        assert record["primary"] is None and record["published"] and record["validations"] == 2
        assert record["actual_counter"] == count
        assert record["counter_calls"] == dict(
            body=count, wrapper=count, starts=count, profiled_helper_entries=count
        )
        assert record["results"] == ["__DefaultDict" + str(i) for i in range(1, count + 1)]
        assert len(attempts) == count
        assert all(
            a["completed"]
            and a["primary"] is None
            and a["ordinal"] == a["before"] == i
            and a["after"] == i + 1
            and a["output"] == record["results"][i]
            for i, a in enumerate(attempts)
        )
        assert record["strict_difference"] == dict(
            before_count=13,
            current_count=13,
            indices=[7],
            reason="Actual source/closure/default/builtin binding changed",
        )
    else:
        assert record["primary"] is not None
        assert record["published"] is (variant == "closed_call")
        if variant in (
            "original_defaults",
            "original_code",
            "foreign_export",
            "foreign_body",
            "global_str",
        ):
            assert record["actual_counter"] == 0 and record["results"] == []
        elif variant == "reentry":
            # CPython suppresses recursive monitoring while the inherited
            # profiler runs. Preserve the actual extra effect and refuse its
            # unwitnessed state; never count it as an authenticated transition.
            assert record["actual_counter"] == 1 and attempts == [] and record["results"] == []
            assert record["primary"]["message"] == "Unwitnessed metadata counter change"
            assert record["callback_work"] == [
                dict(helper=stage.COUNTER_HELPER[2], completed=True, result="__DefaultDict1")
            ]
        elif variant == "counter_before":
            assert record["actual_counter"] == 1 and not attempts and record["results"] == []
            assert record["primary"]["message"] == "Unwitnessed metadata counter change"
        elif variant in ("counter_after", "closed_call"):
            assert record["actual_counter"] == 2 and len(attempts) == 1 and attempts[0]["completed"]
            assert record["primary"]["message"] == "Unwitnessed metadata counter change"
            if variant == "closed_call":
                assert record["counter_calls"] == dict(
                    body=1, wrapper=1, starts=1, profiled_helper_entries=2
                )
        elif variant in ("source_unwind", "source_capture_unwind"):
            assert record["source_primary_identity"] and record["source_cause_identity"]
            assert record["primary"] == dict(type="RuntimeError", message="counter source unwind")
            assert (
                record["actual_counter"] == 1
                and len(attempts) == 1
                and not attempts[0]["completed"]
            )
            if variant == "source_capture_unwind":
                assert any(
                    x[2] == "counter unwind capture failure" for x in record["capture_errors"]
                )
        elif variant == "capture_return":
            assert record["actual_counter"] == 1 and record["results"] == ["__DefaultDict1"]
            assert len(attempts) == 1 and not attempts[0]["completed"]
            assert any(x[2] == "counter return capture failure" for x in record["capture_errors"])
        elif variant == "budget":
            assert (
                record["actual_counter"]
                == len(attempts)
                == len(record["results"])
                == stage.MAX_COUNTER_CALLS
            )
            assert all(a["completed"] for a in attempts)
            assert record["primary"]["message"] == "Bounded metadata counter work exhausted"
            assert all(
                record["counter_calls"][key] == stage.MAX_COUNTER_CALLS + 1
                for key in ("body", "wrapper", "starts")
            )
        elif variant == "record_drop":
            assert record["actual_counter"] == 1 and attempts == []
            assert len(record["counter_history"]) == 1 and record["counter_history"][0]["completed"]
            assert (
                record["primary"]["message"]
                == "Complete ordered metadata counter witnesses required"
            )
