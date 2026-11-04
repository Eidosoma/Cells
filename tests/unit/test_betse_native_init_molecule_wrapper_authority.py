"""Native-blocked factory observation; toy bodies issue no native authority."""

import ast
import builtins
import hashlib
import sys
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_molecule_wrapper_authority as stage
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


def test_source_plan_has_no_decorator_or_native_execution_release():
    plan = stage.source_plan()
    assert not plan["original_factory_generator_or_wrapper_invoked_by_observer"]
    assert not plan["retrospective_or_decoded_or_supplied_wrapper_authority"]
    assert plan["no_Parameters_phase_material_or_scientific_admission"]


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
    if drift == "none":
        context, wrapper = model.run()
        assert context.loaded_codes[imported.__name__].output is model.source_body.__code__
        assert (
            stage.validate(wrapper, model.original, owner=model.owner, attribute="method")
            is model.original
        )
    else:
        with pytest.raises(ValueError, match="loader/code/module ancestry"):
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
