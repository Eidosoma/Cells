"""Blocked current-source SIM protocol and reservation controls, zero native work.

Private registry-shaped models below are metadata controls, never inserted in
production issuance registries and never substitutes for actual INIT/SIM.
"""

import ast
import builtins
import contextlib
import dis
import gc
import json
import struct
import sys
from abc import ABCMeta, abstractmethod
from pathlib import Path
from threading import RLock
from types import CodeType, FunctionType, ModuleType
from types import SimpleNamespace as NS
from weakref import WeakKeyDictionary, WeakValueDictionary

import numpy as np
import pytest

from cells.processes import betse_native_sim_run as stage
from tests.unit import test_betse_native_init_retained_world as guards
from tests.unit import test_betse_native_init_sim_assembly as old_controls
from validation.betse import betse_native_sim_run_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    scope = dict(vars(guards), software=software, _RAW_GUARDS=[])
    function = FunctionType(guards.blocked.__wrapped__.__code__, scope)
    with contextlib.contextmanager(function)(request, tmp_path, monkeypatch):
        yield


def clone(function, **changes):
    result = FunctionType(
        function.__code__,
        dict(function.__globals__, **changes),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    result.__kwdefaults__ = function.__kwdefaults__
    return result


class Foreign:
    def __getattribute__(self, name):
        raise AssertionError("Foreign object read before real authority")


@pytest.mark.parametrize("role", tuple(stage.source.METHODS))
def test_sim_run_compiles_whole_original_method_without_import_or_body_execution(role):
    actual = stage.source.code(role)
    path, name = stage.source.METHODS[role]
    assert type(actual) is CodeType and actual.co_qualname == name
    unit = compile(
        (stage.source.NATIVE / path).read_bytes(),
        str(stage.source.NATIVE / path),
        "exec",
        dont_inherit=True,
    )
    pending = [unit]
    expected = None
    while pending:
        item = pending.pop()
        if item.co_qualname == name:
            expected = item
        pending.extend(v for v in item.co_consts if type(v) is CodeType)
    assert stage.previous.preparation.observation._code(actual) == (
        stage.previous.preparation.observation._code(expected)
    )


def test_sim_run_original_loop_and_pre_pickle_instruction_are_exact_and_separate():
    plan = stage.source_plan()
    spans = plan["original"]["boundaries"]
    instructions = {i.offset: i for i in dis.get_instructions(stage.source.code("run_core"))}
    assert instructions[spans["stop"]].argval == "_pickle_phase"
    assert instructions[spans["stop"]].opname in ("LOAD_ATTR", "LOAD_METHOD")
    loop = {i.offset: i for i in dis.get_instructions(stage.source.code("loop"))}
    assert loop[spans["for_iter"]].opname == "FOR_ITER"
    assert spans["iteration"] > spans["for_iter"]
    assert plan["original"]["endpoint"] == "after_original_loop_and_context_before_native_pickle"
    assert plan["fresh_runtime_import_observation_before_INIT_required"]
    assert not plan["numerical_reference_checkpoint_or_biological_admission"]
    assert not stage._ISSUED and not stage.previous._RUN_RESERVATIONS


@pytest.mark.parametrize("law", (None, "", "INIT", 1, True))
def test_sim_run_wrong_law_refuses_before_any_foreign_owner_read(law):
    with pytest.raises(stage.SimRunRejected) as caught:
        stage.from_assembly(Foreign(), maximum=3, law_id=law)
    assert caught.value.stage == "law"


@pytest.mark.parametrize("maximum", (0, -1, True, 3.0, 513, None))
def test_sim_run_exact_finite_bound_is_not_a_raised_coupled_cap(maximum):
    with pytest.raises(ValueError, match="integer bound"):
        stage.from_assembly(Foreign(), maximum=maximum, law_id=stage.LAW_ID)


def test_sim_run_genuine_constructor_and_review_prerequisite_remain_held():
    with pytest.raises(stage.SimRunRejected) as caught:
        stage.from_assembly(Foreign(), maximum=3, law_id=stage.LAW_ID)
    assert caught.value.stage == "producer_held"


@pytest.mark.parametrize("enabled,flag", ((False, None), (True, None), (1, "1"), (True, "1")))
def test_sim_run_release_and_import_gates_precede_native_or_owner_use(monkeypatch, enabled, flag):
    if flag is None:
        monkeypatch.delenv(stage.RELEASE, raising=False)
    else:
        monkeypatch.setenv(stage.RELEASE, flag)
    expected = "producer_held" if enabled is True and flag == "1" else "release"
    with pytest.raises(stage.SimRunRejected) as caught:
        stage.prepare(Foreign(), enabled=enabled)
    assert caught.value.stage == expected
    with pytest.raises(stage.SimRunRejected) as caught:
        with stage.observing_runtime_import(enabled=enabled):
            pytest.fail("Native import must remain blocked")
    assert caught.value.stage == expected


def test_sim_run_saved_trial_or_phase_is_not_a_live_parent():
    with pytest.raises(TypeError):
        stage.SimRunOwner()
    for value in (dict(completed=True), Foreign(), object.__new__(stage.SimRunOwner)):
        with pytest.raises(stage.SimRunRejected) as caught:
            stage.completed_sim(value)
        assert caught.value.stage == "owner"


def _terminal_model():
    model = old_controls._reservation_model()
    namespace = dict(model.reserve.__globals__, _SIM_PENDING={}, _SIM_FAILURES=[])
    model.reserve = FunctionType(stage.previous.terminal.reserve_for_sim.__code__, namespace)
    model.validate = FunctionType(stage.previous.terminal._sim_reservation.__code__, namespace)
    model.pending, model.failures = namespace["_SIM_PENDING"], namespace["_SIM_FAILURES"]
    return model


def _reserve(model):
    return model.reserve(
        model.owner,
        expected_trial=model.trial,
        law_id=stage.previous.terminal.SIM_RESERVATION_LAW,
        enabled=True,
    )


def test_sim_run_terminal_reservation_actual_profile_return_reentry_is_sticky(monkeypatch):
    model = _terminal_model()
    monkeypatch.setenv(stage.previous.terminal.SIM_RESERVATION_RELEASE, "1")
    prior, attempted = sys.getprofile(), []
    authority = model.reserve.__globals__["_authority"]

    def inherited(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if frame.f_code is authority.__code__ and event == "return" and not attempted:
            attempted.append("actual_return_hook_reentry")
            with pytest.raises(stage.previous.terminal.InitTerminalRejected) as nested:
                _reserve(model)
            assert nested.value.stage == "reentrant"

    try:
        sys.setprofile(inherited)
        with pytest.raises(stage.previous.terminal.InitTerminalRejected) as outer:
            _reserve(model)
    finally:
        sys.setprofile(prior)
    assert outer.value.stage == "association" and attempted == ["actual_return_hook_reentry"]
    assert not model.reservations and model.retired[model.owner] is False
    assert model.pending[model.owner].invalid and len(model.failures) == 1
    with pytest.raises(stage.previous.terminal.InitTerminalRejected) as refused:
        _reserve(model)
    assert refused.value.stage == "consumed"
    assert not stage.previous.terminal._SIM_RESERVATIONS


@pytest.mark.parametrize("failure", (False, True))
def test_sim_run_terminal_retirement_preserves_primary_and_never_rearms(monkeypatch, failure):
    model = _terminal_model()
    monkeypatch.setenv(stage.previous.terminal.SIM_RESERVATION_RELEASE, "1")
    primary, cause = ValueError("metadata source"), OSError("retained cause")

    def authority(actual):
        assert actual is model.owner
        if failure:
            raise primary from cause
        return model.parent

    model.reserve.__globals__["_authority"] = authority
    if failure:
        with pytest.raises(ValueError) as caught:
            _reserve(model)
        assert caught.value is primary and primary.__cause__ is cause
        assert model.failures[0].primary is primary and not model.reservations
    else:
        token = _reserve(model)
        assert model.validate(token) == (model.parent, model.trial)
        assert model.retired[model.owner] is True
    with pytest.raises(stage.previous.terminal.InitTerminalRejected):
        _reserve(model)


def _nested_model(meta=type):
    namespace = dict(__name__="metadata_nested", events=[], Meta=meta)
    exec(
        compile(
            "class Nested(metaclass=Meta):\n def __init__(self):\n  events.append('delegate')\n",
            "/tmp/cells-synthetic-native/child.py",
            "exec",
        ),
        namespace,
    )
    cls = namespace["Nested"]
    function = cls.__init__
    calls = []

    def validate(actual, original, *, owner, attribute):
        calls.append((actual, original, owner, attribute))
        if vars(owner).get(attribute) is not actual or original is not function:
            raise ValueError("Original actual nested dispatch changed")

    row = NS(original=function, module=object(), target=(("Nested", "__init__"),), stack=(cls,))
    helper = clone(
        stage.previous._nested_entry,
        _phase_import_api=lambda: dict(validate=validate),
        _IMPORTS={function: (object(), row)},
        source=NS(NATIVE=Path("/tmp/cells-synthetic-native"), PINS={"child.py": "metadata"}),
    )
    return NS(
        cls=cls,
        function=function,
        events=namespace["events"],
        calls=calls,
        helper=helper,
        context=NS(wrapper_codes=frozenset((function.__code__,))),
    )


@pytest.mark.parametrize("mutation", (None, "copied_method", "foreign_body"))
@pytest.mark.parametrize("meta", (type, ABCMeta))
def test_sim_run_nested_constructor_is_checked_at_profile_entry_before_delegate(mutation, meta):
    model = _nested_model(meta)
    if mutation == "copied_method":
        model.cls.__init__ = FunctionType(model.function.__code__, model.function.__globals__)
    elif mutation == "foreign_body":

        def foreign(self):
            model.events.append("foreign_delegate")

        # Same source-category filename, different unissued executable.
        code = foreign.__code__.replace(co_filename="/tmp/cells-synthetic-native/child.py")
        model.cls.__init__ = FunctionType(code, foreign.__globals__, closure=foreign.__closure__)
    prior = sys.getprofile()

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call" and frame.f_code.co_filename.startswith("/tmp/cells-synthetic-native/"):
            model.helper(model.context, frame)

    try:
        sys.setprofile(profile)
        if mutation is None:
            model.cls()
        else:
            with pytest.raises((ValueError, stage.previous.AssemblyRejected)):
                model.cls()
    finally:
        sys.setprofile(prior)
    assert model.events == (["delegate"] if mutation is None else [])


@pytest.mark.parametrize("source_fails", (False, True))
def test_sim_run_constructor_observer_failure_stops_next_delegate_and_keeps_primary(source_fails):
    events, primary, cause = [], ValueError("actual toy source"), OSError("actual toy cause")
    capture = LookupError("inherited return capture")
    context = NS(
        source_error=None,
        pending_source_error=None,
        capture_errors=[],
        raw_returns=[],
        parameter_manager=None,
        wrapper_codes=frozenset(),
    )

    def first():
        events.append("first")
        if source_fails:
            raise primary from cause

    def second():
        events.append("second")

    def construct(actual):
        try:
            first()
            second()
        except BaseException as error:
            if error is primary:
                actual.source_error = error
            raise

    context.wrapper_codes = frozenset((first.__code__, second.__code__))
    prior = sys.getprofile(), sys.gettrace()

    def profile(frame, event, arg):
        if prior[0] is not None:
            prior[0](frame, event, arg)
        if frame.f_code is first.__code__ and event == "return":
            raise capture

    run = clone(
        stage.previous._run_observed,
        __name__="metadata_constructor_observer",
        _construct=construct,
        _metadata_guard=lambda actual: None,
        _observe=lambda *args: None,
    )
    try:
        sys.setprofile(profile)
        with pytest.raises(BaseException) as caught:
            run(context)
        assert sys.getprofile() is profile and sys.gettrace() is prior[1]
    finally:
        sys.setprofile(prior[0])
        sys.settrace(prior[1])
    assert events == ["first"]
    assert caught.value is primary if source_fails else caught.value.__cause__ is capture
    if source_fails:
        assert primary.__cause__ is cause
    assert any(row[1] is capture for row in context.capture_errors)


@pytest.mark.parametrize("missing", ("events", "global_events", "tissue_events", "make_changes"))
def test_sim_run_omitted_event_cannot_seal_an_iteration(missing):
    label = 0.0
    events = tuple(
        (role, object(), label)
        for role in ("events", "global_events", "tissue_events", "make_changes")
        if role != missing
    )
    context = NS(
        current=(0, label, False, 0, 0),
        event_calls=list(events),
        callback_calls=[],
        sample_calls=[],
        invalid=False,
        entry_error=None,
    )
    with pytest.raises(stage.SimRunRejected) as caught:
        stage._finish_iteration(context)
    assert caught.value.stage == "events" and context.invalid


@pytest.mark.parametrize("role", ("global_events", "events", "make_changes"))
def test_sim_run_duplicate_or_out_of_order_event_refuses_before_state_effect(role):
    def actual():
        pass

    phase, handler, label = object(), object(), 0.0
    context = NS(
        core_roles={actual.__code__: role},
        current=(0, label, False, 0, 0),
        handler=handler,
        phase=phase,
        event_calls=[("events", object(), label)],
        callback_calls=[],
        callback_methods={},
        invalid=False,
        entry_error=None,
        loop_frame=None,
        added_objects=[],
    )
    frame = NS(
        f_code=actual.__code__,
        f_globals=actual.__globals__,
        f_locals=dict(self=handler, phase=phase, t=label),
        f_back=None,
    )
    if role == "global_events":
        context.event_calls.append(("global_events", object(), label))
    with pytest.raises(stage.SimRunRejected) as caught:
        stage._source_entry(context, frame, (actual, None, "not_callback", True))
    assert caught.value.stage == "events"


def test_sim_run_source_does_not_substitute_a_calendar_loop_or_numerical_body():
    tree = ast.parse(Path(stage.__file__).read_text())
    execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_execute")
    calls = [ast.unparse(n.func) for n in ast.walk(execute) if isinstance(n, ast.Call)]
    assert calls[:2] == ["context.sim.sim_info_report", "context.sim.run_sim_core"]
    assert all(not isinstance(n, ast.For) for n in ast.walk(execute))
    assert stage.PARENT_SHA256 is stage.PARENT_REVIEW_SHA256 is None
    assert not stage._ISSUED and not stage.previous._RUN_RESERVATIONS


@pytest.mark.parametrize("sampled", (False, True))
def test_sim_run_metadata_four_iteration_stream_retains_each_epoch_and_full_cache(sampled):
    cache = stage.previous.terminal.retained_cache
    stable = cache.snapshot(dict(geometry="retained", parameters="same actual lineage required"))
    context = NS(
        current=None,
        event_calls=[],
        callback_calls=[],
        sample_calls=[],
        invalid=False,
        entry_error=None,
        stable=stable,
        iterations=[],
        work=[],
        metadata_work=[],
    )
    roots, graph = (object(),), dict(actual_alias_edges="synthetic metadata only")

    def snapshot(actual):
        label = actual.current[1]
        return (
            cache.snapshot(dict(label=label, state="complete metadata payload")),
            (roots, graph),
            (cache.snapshot(dict(RNG="metadata state, no draw")),),
        )

    finish = clone(
        stage._finish_iteration,
        _bindings=lambda actual: None,
        _stable=lambda actual: stable,
        _snapshot=snapshot,
    )
    for ordinal, label in enumerate((0.0, 0.25, 0.5, 0.75)):
        context.current = (
            ordinal,
            label,
            sampled,
            len(context.event_calls),
            len(context.callback_calls),
        )
        context.event_calls.extend(
            (name, object(), label)
            for name in ("events", "global_events", "tissue_events", "make_changes")
        )
        if sampled:
            context.callback_calls.append(("progressed_next", object(), context.current))
            context.sample_calls.append((ordinal, label, object()))
        finish(context)
    assert [r.ordinal for r in context.iterations] == [0, 1, 2, 3]
    assert len({r.after.identity for r in context.iterations}) == 4
    assert all(r.sampled is sampled and r.graph[0] is roots for r in context.iterations)
    assert all(
        cache.validate(r.after) is r.after and len(r.event_calls) == 4 for r in context.iterations
    )
    assert context.current is None and len(context.metadata_work) == 4
    assert not stage._ISSUED


@pytest.mark.parametrize("count", (0, 2))
def test_sim_run_sampling_omission_or_duplicate_refuses_before_epoch_seal(count):
    context = NS(
        current=(0, 0.0, True, 0, 0),
        invalid=False,
        entry_error=None,
        event_calls=[
            (r, object(), 0.0) for r in ("events", "global_events", "tissue_events", "make_changes")
        ],
        callback_calls=[("progressed_next", object(), None)] * count,
    )
    with pytest.raises(stage.SimRunRejected) as caught:
        stage._finish_iteration(context)
    assert caught.value.stage == "sampling"


def test_sim_run_source_catalog_declares_actual_reload_and_does_not_alias_INIT_law():
    sites = stage.source.sites()
    assert sites[("MasterOfMolecules", "reinitialize")] == "betse/science/chemistry/molecules.py"
    assert sites[("TissueHandler", "fire_events")] == "betse/science/tissue/tishandler.py"
    assert stage.LAW_ID != stage.previous.terminal.LAW_ID
    assert stage.LAW_ID != stage.previous.LAW_ID


@pytest.mark.parametrize("failed_hook", ("trace", "profile"))
def test_sim_run_independent_hook_recovery_retries_and_checks_both_final_values(failed_hook):
    prior = object(), object()
    current, attempted = dict(profile=object(), trace=object()), []
    failed = []

    def setter(name, value):
        attempted.append(name)
        if name == failed_hook and not failed:
            failed.append(name)
            raise OSError("metadata hook restoration refusal")
        current[name] = value

    surface = NS(
        getprofile=lambda: current["profile"],
        gettrace=lambda: current["trace"],
        setprofile=lambda value: setter("profile", value),
        settrace=lambda value: setter("trace", value),
    )
    context = NS(cleanup_errors=[])
    recover = clone(stage._recover, sys=surface)
    assert recover(context, prior)
    assert current == dict(profile=prior[0], trace=prior[1])
    assert failed_hook in failed and set(attempted) == {"trace", "profile"}
    assert len(context.cleanup_errors) == 1


@pytest.mark.parametrize("count", (0, 2))
def test_sim_run_successful_callback_cannot_hide_omitted_or_duplicate_storage(count):
    label = 0.0
    context = NS(
        current=(0, label, True, 0, 0),
        invalid=False,
        entry_error=None,
        event_calls=[
            (r, object(), label)
            for r in ("events", "global_events", "tissue_events", "make_changes")
        ],
        callback_calls=[("progressed_next", object(), None)],
        sample_calls=[(0, label, object())] * count,
    )
    with pytest.raises(stage.SimRunRejected, match="time-storage") as caught:
        stage._finish_iteration(context)
    assert caught.value.stage == "sampling"


def test_sim_run_no_call_helper_attribute_binding_detects_foreign_replacement():
    calls, module = [], ModuleType("metadata_helper")

    def actual():
        calls.append("forbidden helper execution")

    module.operation = actual
    namespace = dict(__builtins__=builtins, helper=module)
    code = compile("def source():\n return helper.operation()\n", "metadata_probe", "exec")
    body = next(v for v in code.co_consts if type(v) is CodeType)
    function = FunctionType(body, namespace)
    attributes = stage._attributes(function)
    assert attributes == ((module, "operation", actual),)
    state = stage.previous.wrappers._function_state(function)
    context = NS(
        import_bindings=(),
        members=(),
        functions=((function, state, attributes),),
        library_bindings=(),
        callback_binding=(),
        expressions=None,
    )
    check = clone(stage._entry_bindings, base=NS(_callback_bindings=lambda c: ()))
    check(context)
    module.operation = lambda: calls.append("foreign helper execution")
    with pytest.raises(ValueError, match="helper changed"):
        check(context)
    assert calls == []


def test_sim_run_rng_event_uses_actual_completion_stream_owner_schema_without_draws():
    np_owner, std_owner = object(), object()
    cache = stage.previous.terminal.retained_cache.snapshot(dict(RNG="metadata only"))
    streams = NS(np_rng=np_owner, std_rng=std_owner)
    delegate = NS(__self__=np_owner)
    frame = NS(f_code=object())
    context = NS(
        assembly=NS(parent=NS(parent=streams)),
        codes={frame.f_code: object()},
        work=[],
        c_calls=[],
        rng_calls=[],
        pending_rng=[],
        metadata_work=[],
        invalid=False,
        entry_error=None,
    )
    helper = clone(
        stage._profile_event,
        _guard=lambda c: None,
        _entry_bindings=lambda c: None,
        _streams=lambda c: (cache,),
    )
    helper(context, frame, "c_call", delegate)
    helper(context, frame, "c_return", delegate)
    assert len(context.rng_calls) == 1 and not context.pending_rng
    row = context.rng_calls[0]
    assert row["before"] == row["after"] == (cache,) and row["delegate"] is delegate
    assert row["outcome"] == "c_return" and len(context.metadata_work) == 2
    assert not stage._ISSUED


@pytest.mark.parametrize("source_fails", (False, True))
def test_sim_run_real_profile_unwind_observation_retains_primary_cause_and_raw(source_fails):
    primary, cause, capture = (
        ValueError("toy original"),
        OSError("toy cause"),
        LookupError("capture"),
    )
    context = NS(
        observing=False,
        inherited=False,
        capture_errors=[],
        cleanup_errors=[],
        metadata_work=[],
        source_error=None,
        primary=None,
        pending={},
        exceptions=[],
        raw_returns=[],
        nested_codes={},
        expressions=None,
        boundary_seen=False,
        stop=stage._BeforeStorage(),
        last_raw=None,
        last_capture=None,
        last_cleanup_error=None,
        unwinds=[],
    )

    def target():
        if source_fails:
            raise primary from cause

    context.codes = {target.__code__: object()}

    def execute(actual):
        target()

    def profile_event(actual, frame, event, arg):
        if frame.f_code is target.__code__ and event == "return":
            raise capture

    cache = stage.previous.terminal.retained_cache.snapshot(dict(metadata="stable"))
    token, graph = (object(),), {}
    run = clone(
        stage._run_observed,
        __name__="metadata_sim_observer",
        _execute=execute,
        _profile_event=profile_event,
        _observe=lambda *args: None,
        _snapshot=lambda c: (cache, (token, graph), (cache,)),
    )
    prior = sys.getprofile(), sys.gettrace()
    with pytest.raises(BaseException) as caught:
        run(context)
    assert (sys.getprofile(), sys.gettrace()) == prior
    if source_fails:
        assert caught.value is primary and primary.__cause__ is cause
        assert any(
            event == "exception" and raw[1] is primary for _, event, raw in context.raw_returns
        )
    else:
        assert isinstance(caught.value, stage.SimRunRejected) and caught.value.stage == "capture"

    assert any(row[1] is capture for row in context.capture_errors)


def test_sim_run_core_complete_current_and_profile_helper_roster_is_original_and_closed():
    from cells.processes import betse_native_init_electrical_source as electrical

    sites = stage.source.sites()
    for path, pin in electrical.SOURCE_PINS.items():
        assert stage.source.PINS[path] == pin
    expected = {
        (None, "get_current"),
        (None, "HH_Decomp"),
        (None, "gradient"),
        (None, "divergence"),
        (None, "diff"),
        (None, "load_image"),
        (None, "interp2d_linear"),
        (None, "die_unless_file"),
        (None, "is_file"),
        (None, "is_dir"),
        (None, "is_path"),
        (None, "get_basename"),
        ("TissuePickerImage", "pick_cells"),
        ("TissuePickerImage", "get_image_mask"),
        ("TissuePickerImageMask", "__init__"),
        ("TissuePickerImageMask", "get_clipped_points_index"),
    }
    assert expected <= set(sites)
    for path, names in stage.source.IMAGE_HELPERS.items():
        assert {(owner, name) for (owner, name), file in sites.items() if file == path} == {
            (None, name) for name in names
        }
    assert sites[(None, "join")] == "betse/util/type/text/string/strjoin.py"
    assert (None, "copy_overwritable") not in sites
    # Direct and downstream edges are checked against independently read ASTs,
    # without invoking original methods, decorators, helpers or image readers.
    for role, reached in (
        ("voltage", {"get_current"}),
        ("current", {"HH_Decomp", "gradient"}),
        ("decompose", {"gradient", "divergence"}),
        ("divergence", {"diff"}),
        ("image_pick", {"get_image_mask", "get_clipped_points_index"}),
        ("mask_constructor", {"load_image", "interp2d_linear"}),
        ("image_load", {"get_basename", "die_unless_file", "to_signed"}),
    ):
        path, qualified = stage.source.METHODS[role]
        unit = ast.parse((stage.source.NATIVE / path).read_bytes())
        pieces = qualified.split(".")
        body = unit.body
        for name in pieces:
            node = next(
                n for n in body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name
            )
            body = node.body
        calls = {
            n.func.id if isinstance(n.func, ast.Name) else n.func.attr
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
        }
        assert reached <= calls
    assert stage.source.source_plan()["image_helpers"] == stage.source.IMAGE_HELPERS
    assert stage.MAX_ITERATIONS == 512 and stage.MAX_WORK == 100000
    assert not stage._ISSUED


def _core_binding_model():
    """Private loader-shaped metadata only; original code is never called."""
    code = stage.source.code("current")
    namespace = dict(__builtins__=vars(builtins), __name__="metadata_current")
    actual = FunctionType(code, namespace)
    path = stage.source.METHODS["current"][0]
    module = ModuleType(path[:-3].replace("/", "."))
    module.__file__ = str(stage.source.NATIVE / path)
    module.get_current = actual

    class MetadataRng:
        def shuffle(self):
            raise AssertionError("No RNG work in a binding control")

        def _randbelow(self):
            raise AssertionError("No RNG work in a binding control")

    rng = MetadataRng()

    def noop():
        raise AssertionError("No source work in a binding control")

    old = NS(
        log_support=[],
        logger_chains={},
        noop_generator=noop,
        noop_methods=(),
        parent=NS(shuffle=rng.shuffle, std_rng=rng, molecule_session=None),
    )
    context = NS(
        assembly=NS(parent=old),
        nested_codes={},
        callback_chains={},
        callback_owner=object(),
        callback_binding=(),
        expressions=None,
    )
    proof = NS(published=True, primary=None, active=False, loaded_codes={module.__name__: object()})
    checks = []
    catalog = NS(
        NATIVE=stage.source.NATIVE,
        sites=lambda: {(None, "get_current"): path},
        import_code=lambda owner, name: code,
        METHODS={"current": (path, "get_current")},
        code=lambda role: code,
    )
    context.import_api = {"validate": lambda *a, **k: checks.append((a, k))}
    bind = clone(
        stage._bind_runtime,
        __name__="metadata_SIM_core_binding",
        source=catalog,
        sys=NS(modules={module.__name__: module}),
        _IMPORT_EXPORTS=[(proof, ((module, module, "get_current", actual),))],
        _IMPORTS={actual: (proof,)},
        _runtime_import_api=lambda: context.import_api,
        base=NS(_callback_methods=lambda c: None, _callback_bindings=lambda c: ()),
    )
    return NS(context=context, actual=actual, module=module, code=code, bind=bind, checks=checks)


@pytest.mark.parametrize("drift", (None, "unobserved", "equal_copy", "code", "namespace"))
def test_sim_run_core_import_binding_requires_actual_fresh_electrical_export_without_call(drift):
    model = _core_binding_model()
    if drift == "unobserved":
        model.bind.__globals__["_IMPORT_EXPORTS"] = []
    elif drift == "equal_copy":
        model.module.get_current = FunctionType(model.code, model.actual.__globals__)
    elif drift == "code":
        model.actual.__code__ = (lambda: None).__code__
    elif drift == "namespace":
        model.module.__file__ = "/tmp/foreign_current.py"
    if drift is None:
        model.bind(model.context)
        assert model.context.codes[model.code][0] is model.actual
        assert model.context.members == [(model.module, "get_current", model.actual)]
        assert len(model.checks) == 1
        # An equal-code replacement after binding also refuses before a call.
        model.module.get_current = FunctionType(model.code, model.actual.__globals__)
        check = clone(stage._entry_bindings, base=NS(_callback_bindings=lambda c: ()))
        with pytest.raises(ValueError, match="dispatch changed"):
            check(model.context)
    else:
        with pytest.raises(ValueError, match="prerequisite|executable|module"):
            model.bind(model.context)
    assert not stage._ISSUED


@pytest.mark.parametrize("drift", (None, "sim", "cells", "p", "caller"))
def test_sim_run_core_actual_profile_dispatch_refuses_before_foreign_current_body(drift):
    entered, checked = [], []

    def current(sim, cells, p):
        entered.append((sim, cells, p))

    def voltage(self, cells, p):
        current(self, cells, p)

    simulator = type("Simulator", (), {})
    sim, cells, p = object.__new__(simulator), object(), object()
    context = NS(
        sim=sim,
        cells=cells,
        p=p,
        invalid=False,
        entry_error=None,
        core_roles={current.__code__: "current"},
        callback_methods={},
        image_codes=set(),
        codes={
            current.__code__: (current, None, "get_current", True),
            voltage.__code__: (voltage, simulator, "update_V", True),
        },
    )
    if drift == "caller":
        context.codes[voltage.__code__] = (voltage, simulator, "unrelated", True)
    args = [sim, cells, p]
    if drift in ("sim", "cells", "p"):
        args[("sim", "cells", "p").index(drift)] = object()
    prior = sys.getprofile()

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call" and frame.f_code is current.__code__:
            checked.append(frame)
            stage._source_entry(context, frame, context.codes[current.__code__])

    try:
        sys.setprofile(profile)
        if drift is None:
            voltage(*args)
        else:
            with pytest.raises(stage.SimRunRejected) as caught:
                voltage(*args)
            assert caught.value.stage == "dispatch" and caught.value.partial is context
    finally:
        sys.setprofile(prior)
    assert len(checked) == 1 and len(entered) == (1 if drift is None else 0)
    assert not stage._ISSUED


@pytest.mark.parametrize("role", ("decompose", "gradient", "divergence", "diff", "image_load"))
def test_sim_run_core_downstream_original_edges_cannot_skip_to_unrelated_callers(role):
    function = FunctionType(stage.source.code(role), dict(__builtins__=vars(builtins)))

    def unrelated():
        raise AssertionError("No downstream body may execute")

    code = function.__code__
    caller = NS(f_code=unrelated.__code__, f_globals=unrelated.__globals__, f_back=None)
    frame = NS(f_code=code, f_globals=function.__globals__, f_back=caller, f_locals={})
    context = NS(
        codes={
            code: (function, None, function.__name__, True),
            unrelated.__code__: (unrelated, None, "unrelated", True),
        },
        invalid=False,
        entry_error=None,
    )
    with pytest.raises(stage.SimRunRejected, match="caller/dispatch edge") as caught:
        stage._helper_entry(context, frame, role)
    assert caught.value.stage == "dispatch" and context.invalid


@pytest.mark.parametrize("role", ("decompose", "gradient", "divergence", "diff"))
@pytest.mark.parametrize("foreign", (False, True))
def test_sim_run_core_downstream_accepts_actual_owner_and_refuses_equal_foreign_spacing(
    role, foreign
):
    function = FunctionType(stage.source.code(role), dict(__builtins__=vars(builtins)))
    parents = {
        "decompose": "current",
        "gradient": "decompose",
        "divergence": "decompose",
        "diff": "divergence",
    }
    parent = FunctionType(stage.source.code(parents[role]), dict(__builtins__=vars(builtins)))
    delta, bounds = float("0.000008"), dict(L=0.0, R=0.0, T=0.0, B=0.0)
    sim, cells = NS(bound_V=bounds), NS(delta=delta)
    caller = NS(
        f_code=parent.__code__,
        f_globals=parent.__globals__,
        f_back=None,
        f_locals=dict(sim=sim),
    )
    values = dict(cells=cells, bounds=bounds, delx=delta, dely=None)
    if role == "divergence":
        values["dely"] = delta
    if foreign:
        if role == "decompose":
            values["bounds"] = dict(bounds)
        else:
            values["delx"] = float("0.000008")
            assert values["delx"] == delta and values["delx"] is not delta
    frame = NS(
        f_code=function.__code__, f_globals=function.__globals__, f_back=caller, f_locals=values
    )
    context = NS(
        sim=sim,
        cells=cells,
        invalid=False,
        entry_error=None,
        codes={
            function.__code__: (function, None, function.__name__, True),
            parent.__code__: (parent, None, parent.__name__, True),
        },
    )
    if foreign:
        with pytest.raises(stage.SimRunRejected, match="association|spacing") as caught:
            stage._helper_entry(context, frame, role)
        assert caught.value.stage == "dispatch" and context.invalid
    else:
        stage._helper_entry(context, frame, role)
        assert not context.invalid


def _image_callback_model():
    factory_code = stage.source.code("interpolator")
    code = next(v for v in factory_code.co_consts if type(v) is CodeType)

    class Spline:
        def __call__(self, *args):
            raise AssertionError("Original/SciPy interpolation stays blocked")

    spline = object.__new__(Spline)
    namespace = dict(__builtins__=vars(builtins), RectBivariateSpline=Spline)
    cell = (lambda: spline).__closure__[0]
    function = FunctionType(code, namespace, closure=(cell,))
    mask = NS(clipping_function=function)
    constructor = FunctionType(stage.source.code("mask_constructor"), namespace)
    constructor_owner = type("TissuePickerImageMask", (), {})
    constructor_frame = NS(
        f_code=constructor.__code__,
        f_globals=namespace,
        f_locals=dict(self=mask),
        f_back=None,
    )
    factory = FunctionType(factory_code, namespace)
    frame = NS(
        f_code=factory_code,
        f_globals=namespace,
        f_back=constructor_frame,
        f_locals=dict(bivariate_spline=spline, bivariate_spline_interpolator=function),
    )
    context = NS(
        invalid=False,
        entry_error=None,
        image_callbacks=[],
        functions=[],
        image_codes=set(),
        core_roles={constructor.__code__: "mask_constructor"},
        codes={
            factory_code: (factory, None, "interp2d_linear", True),
            constructor.__code__: (constructor, constructor_owner, "__init__", True),
        },
    )
    return NS(context=context, frame=frame, function=function, mask=mask, spline=spline)


@pytest.mark.parametrize(
    "drift", (None, "None", "equal_copy", "code", "closure", "namespace", "spline")
)
def test_sim_run_core_interpolator_requires_actual_original_return_and_closure_without_call(drift):
    model = _image_callback_model()
    result = model.function
    if drift == "None":
        result = None
    elif drift == "equal_copy":
        result = FunctionType(result.__code__, result.__globals__, closure=result.__closure__)
    elif drift == "code":
        result.__code__ = result.__code__.replace(co_firstlineno=result.__code__.co_firstlineno + 1)
    elif drift == "closure":
        result.__closure__[0].cell_contents = object()
    elif drift == "namespace":
        model.frame.f_globals = dict(model.frame.f_globals)
    elif drift == "spline":
        model.frame.f_globals["RectBivariateSpline"] = type("Spline", (), {})
    if drift is None:
        stage._interpolator_return(model.context, model.frame, result)
        assert model.context.image_callbacks[0][0] is result
        assert model.context.image_callbacks[0][2] is model.mask
        assert model.context.image_callbacks[0][3] is model.frame
        assert model.context.image_callbacks[0][4] is model.spline
        assert model.context.codes[result.__code__][0] is result
        assert len(model.context.functions) == 1
    else:
        with pytest.raises(stage.SimRunRejected) as caught:
            stage._interpolator_return(model.context, model.frame, result)
        assert caught.value.stage == "image_callback" and not model.context.image_callbacks
    assert model.context.last_image_return == (model.frame, result)
    assert not stage._ISSUED


@pytest.mark.parametrize("drift", (None, "equal_copy", "mask", "closure", "point", "caller"))
def test_sim_run_core_later_interpolator_dispatch_preserves_actual_factory_mask_and_point(drift):
    model = _image_callback_model()
    stage._interpolator_return(model.context, model.frame, model.function)
    clip_code = stage.source.code("mask_clip")
    x, y = object(), object()
    caller = NS(f_code=clip_code, f_locals=dict(self=model.mask, x=x, y=y))
    model.context.core_roles[clip_code] = "mask_clip"
    frame = NS(
        f_code=model.function.__code__,
        f_globals=model.function.__globals__,
        f_back=caller,
        f_locals=dict(bivariate_spline=model.spline, x_new=x, y_new=y),
    )
    if drift == "equal_copy":
        model.mask.clipping_function = FunctionType(
            model.function.__code__, model.function.__globals__, closure=model.function.__closure__
        )
    elif drift == "mask":
        caller.f_locals["self"] = NS(clipping_function=model.function)
    elif drift == "closure":
        model.function.__closure__[0].cell_contents = object()
    elif drift == "point":
        frame.f_locals["x_new"] = object()
    elif drift == "caller":
        caller.f_code = (lambda: None).__code__
    if drift is None:
        stage._image_callback_entry(model.context, frame)
        assert not model.context.invalid
    else:
        with pytest.raises((ValueError, stage.SimRunRejected)):
            stage._image_callback_entry(model.context, frame)
    assert not stage._ISSUED


@pytest.mark.parametrize("drift", (None, "callback", "fast_type"))
def test_sim_run_core_image_roots_keep_both_actual_splines_and_complete_fields(drift):
    model = _image_callback_model()
    stage._interpolator_return(model.context, model.frame, model.function)
    model.context.added_objects = [("TissuePickerImageMask.__init__", model.mask)]
    coefficients = np.asarray([[-0.0, 1.5], [2.5, 3.5]], dtype=np.float64)
    model.spline.tck = (coefficients, coefficients, coefficients)
    model.spline.degrees = (1, 1)
    fast = object.__new__(type(model.spline))
    fast.tck, fast.degrees = model.spline.tck, (3, 3)
    model.mask.clipping_function_fast = fast
    model.mask.clipping_matrix = coefficients
    if drift == "callback":
        model.mask.clipping_function = FunctionType(
            model.function.__code__, model.function.__globals__, closure=model.function.__closure__
        )
    elif drift == "fast_type":
        model.mask.clipping_function_fast = NS(tck=fast.tck, degrees=fast.degrees)
    if drift is not None:
        with pytest.raises(stage.SimRunRejected) as caught:
            stage._image_roots(model.context)
        assert caught.value.stage == "image_callback"
        return
    roots = (("mask", model.mask), *stage._image_roots(model.context))
    assert roots[1][1] is model.function and roots[2][1] is model.spline and roots[3][1] is fast
    literal = stage.base.previous.storage.previous.previous.previous.core._LITERAL
    projector = NS(objects=list(roots))
    fields = tuple(
        (role, literal._project(projector, vars(actual)))
        for role, actual in stage._field_objects(roots)
    )
    assert len(fields) == 3  # mask and both splines, no dropped numeric stores.
    assert fields[0][1]["clipping_function"] == dict(owned_reference=1)
    assert fields[0][1]["clipping_function_fast"] == dict(owned_reference=3)
    assert all(fields[i][1]["tck"][0] is coefficients for i in (1, 2))
    cache = stage.previous.terminal.retained_cache.snapshot(fields)
    assert stage.previous.terminal.retained_cache.validate(cache) is cache
    assert cache.columns and all(column.values.shape == (2, 2) for column in cache.columns)
    assert not stage._ISSUED


def test_sim_run_nested_original_super_ABC_constructor_remains_admitted():
    namespace = dict(__name__="metadata_nested_ABC", events=[], ABCMeta=ABCMeta)
    exec(
        compile(
            "class Base(metaclass=ABCMeta):\n"
            " def __init__(self): events.append('base')\n"
            "class Child(Base):\n"
            " def __init__(self):\n"
            "  super().__init__()\n"
            "  events.append('child')\n",
            "/tmp/cells-synthetic-native/abc.py",
            "exec",
        ),
        namespace,
    )
    classes = namespace["Base"], namespace["Child"]
    registry = {}
    for cls in classes:
        fn = vars(cls)["__init__"]
        row = NS(original=fn, module=object(), target=((cls.__name__, "__init__"),), stack=(cls,))
        registry[fn] = object(), row

    def validate(actual, original, *, owner, attribute):
        assert actual is original and vars(owner)[attribute] is actual

    helper = clone(
        stage.previous._nested_entry,
        _IMPORTS=registry,
        _phase_import_api=lambda: dict(validate=validate),
        source=NS(NATIVE=Path("/tmp/cells-synthetic-native"), PINS={"abc.py": "metadata"}),
    )
    context = NS(wrapper_codes=frozenset(fn.__code__ for fn in registry))
    prior = sys.getprofile()

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call" and frame.f_code.co_filename == "/tmp/cells-synthetic-native/abc.py":
            helper(context, frame)

    try:
        sys.setprofile(profile)
        namespace["Child"]()
    finally:
        sys.setprofile(prior)
    assert namespace["events"] == ["base", "child"]


def _observation_model():
    class AbstractType(metaclass=ABCMeta):
        @abstractmethod
        def required(self):
            raise NotImplementedError

    def callback():
        pytest.fail("Observation must never execute a callback")

    sim, cells = NS(data="retained sim"), NS(data="retained cells")
    roots = [
        ("sim", sim),
        ("module", ModuleType("metadata")),
        ("function", callback),
        ("type", AbstractType),
        ("slotted", object()),
        ("sim_alias", sim),
        ("cells", cells),
    ]
    fields = [("sim", sim), ("sim_alias", sim), ("cells", cells)]
    return NS(root_objects=roots, observation_field_objects=fields)


def test_sim_run_observation_roster_preserves_full_indices_filtered_order_and_aliases():
    model = _observation_model()
    objects, fields = stage._observation_roster(model)
    assert type(objects) is type(fields) is tuple
    assert len(objects) == 7 and len(fields) == 3
    assert objects[0][1] is objects[5][1] is fields[0][1] is fields[1][1]
    assert fields == (objects[0], objects[5], objects[6])
    assert stage._field_objects(objects) == fields
    assert not stage._ISSUED


@pytest.mark.parametrize("drift", ("swap", "drop", "equal_copy", "role", "extra"))
def test_sim_run_observation_roster_drift_refuses_without_reindexing(drift):
    model = _observation_model()
    rows = model.observation_field_objects
    if drift == "swap":
        rows[0], rows[1] = rows[1], rows[0]
    elif drift == "drop":
        rows.pop()
    elif drift == "equal_copy":
        role, original = rows[-1]
        replacement = NS(**vars(original))
        assert replacement == original and replacement is not original
        rows[-1] = role, replacement
    elif drift == "role":
        rows[-1] = "other label", rows[-1][1]
    else:
        rows.append(rows[-1])
    with pytest.raises(ValueError, match="roster association"):
        stage._observation_roster(model)


def test_sim_run_observation_snapshot_field_history_only_appends_and_rejects_prior_drift():
    original, appended = NS(value="old"), NS(value="new")
    model = NS(observation_field_objects=[])
    stage._retain_field_objects(model, (("old", original),))
    stage._retain_field_objects(model, (("old", original), ("new", appended)))
    assert model.observation_field_objects == [("old", original), ("new", appended)]
    same_value = NS(value="old")
    assert same_value == original and same_value is not original
    with pytest.raises(ValueError, match="order/identity"):
        stage._retain_field_objects(model, (("old", same_value), ("new", appended)))
    assert model.observation_field_objects[0][1] is original


def test_sim_run_observation_public_surface_authenticates_before_roster_access(monkeypatch):
    called = []
    monkeypatch.setattr(stage, "_observation_roster", lambda c: called.append(c))
    with pytest.raises(stage.SimRunRejected) as caught:
        stage.completed_sim(Foreign())
    assert caught.value.stage == "owner" and called == []


def test_sim_run_observation_public_projection_returns_exact_actual_references_in_model():
    context, checked = _observation_model(), []
    token = object()
    context.trial = NS(
        iterations=(),
        before=token,
        after=token,
        calendar=token,
        sampled=token,
        dt=0.01,
        operator_mode="original_value_and_flux",
    )
    context.phase = context.sim = context.cells = context.old_p = context.p = context.callback = (
        token
    )
    context.refs = token, token, token
    context.source_rng_observations = [dict(original="separate evidence only")]
    context.retained_validation_work = []
    context.retained_validation_attempts = context.retained_validation_returns = 0

    def authority(owner):
        checked.append(owner)
        return context

    # A private metadata namespace only; no live production issuance or owner.
    projection = clone(stage.completed_sim, _authority=authority)
    result = projection(token)
    assert checked == [token]
    assert result["observation_objects"] == tuple(context.root_objects)
    assert result["observation_field_objects"] == tuple(context.observation_field_objects)
    assert all(
        a is b
        for (_, a), (_, b) in zip(
            result["observation_field_objects"], context.observation_field_objects, strict=True
        )
    )
    assert (
        result["before_native_pickle"]
        and not result["native_pickle_or_checkpoint_or_physical_admission"]
    )
    assert result["retained_cache_validation_work"]["attempted"] == 0
    assert result["retained_cache_validation_work"]["sweeps"] == ()
    assert not stage._ISSUED


def _observation_stream_model(gaussian, *, legacy_error=None):
    raw = ("MT19937", np.asarray([1] * 624, dtype=np.uint32), 9, 1, gaussian)
    calls = []
    stdlib = stage.previous.terminal.retained_cache.snapshot(("stdlib", (1, 2), None))

    class MetadataRng:
        def get_state(self):
            calls.append("get_state")
            return raw

        def set_state(self, *args):
            pytest.fail("State observation must not reset an RNG")

    completion = NS(np_rng=MetadataRng(), numpy=np)
    source = stage.native_streams.NativeStream(
        json.dumps([raw[0], raw[1].tolist(), raw[2], raw[3], raw[4]], separators=(",", ":")),
        np.__version__,
        "metadata-source-record-only",
    )

    def legacy(actual):
        assert actual is completion
        calls.append("original_readers")
        if legacy_error is not None:
            raise legacy_error
        return source, stdlib

    context = NS(
        assembly=NS(parent=NS(parent=completion)),
        source_rng_observations=[],
        metadata_work=[],
        scope=stage.previous.terminal.retained_cache,
    )
    read = clone(stage._streams, base=NS(previous=NS(storage=NS(previous=NS(_streams=legacy)))))
    return NS(read=read, context=context, calls=calls, raw=raw, source=source, stdlib=stdlib)


@pytest.mark.parametrize("gaussian", (0.0, -0.0, 0.125))
def test_sim_run_observation_numpy_stream_is_typed_cache_and_original_record_is_retained(gaussian):
    model = _observation_stream_model(gaussian)
    first, second = model.read(model.context)
    assert type(first) is stage.previous.terminal.retained_cache.Cache
    assert stage.previous.terminal.retained_cache.validate(first) is first
    assert second is model.stdlib and model.calls == ["get_state", "original_readers"]
    row = model.context.source_rng_observations[0]
    assert (
        row["original"] is model.source and row["numpy"] is first and row["raw_state"] is model.raw
    )
    assert row["primary"] is None and len(model.context.metadata_work) == 3
    assert first.descriptor["items"][-1]["bits"] == struct.pack("<d", gaussian).hex()


@pytest.mark.parametrize("bits", ("7ff8000000000001", "fff8000000000042"))
def test_sim_run_observation_gaussian_nan_bits_survive_original_reader_refusal(bits):
    gaussian = struct.unpack("!d", bytes.fromhex(bits))[0]
    primary = ValueError("retained original NativeStream finite-domain refusal")
    model = _observation_stream_model(gaussian, legacy_error=primary)
    with pytest.raises(ValueError) as caught:
        model.read(model.context)
    assert caught.value is primary
    row = model.context.source_rng_observations[0]
    assert row["primary"] is primary and row["raw_state"] is model.raw
    assert row["original"] is None and row["stdlib"] is None
    assert row["numpy"].descriptor["items"][-1]["bits"] == struct.pack("<d", gaussian).hex()
    assert row["numpy"].all_finite is False
    assert stage.previous.terminal.retained_cache.validate(row["numpy"]) is row["numpy"]
    assert model.calls == ["get_state", "original_readers"] and not stage._ISSUED


class _MetadataMonitor:
    events = NS(PY_START=1, PY_RETURN=2, PY_UNWIND=4)

    def __init__(self, available=6):
        self.tools = {i: None if i < available else "existing metadata tool" for i in range(6)}
        self.masks = {i: 0 for i in range(6)}
        self.callbacks = {}
        self.allocations, self.freed = [], []

    def get_tool(self, tool):
        return self.tools[tool]

    def get_events(self, tool):
        return self.masks[tool]

    def use_tool_id(self, tool, name):
        assert self.tools[tool] is None
        self.tools[tool] = name
        self.allocations.append(tool)

    def register_callback(self, tool, event, callback):
        self.callbacks[tool, event] = callback

    def set_events(self, tool, mask):
        self.masks[tool] = mask

    def free_tool_id(self, tool):
        assert self.masks[tool] == 0
        assert all(value is None for (key, _), value in self.callbacks.items() if key == tool)
        self.tools[tool] = None
        self.freed.append(tool)


def _metadata_import_manager(api, monitor, *, active=None):
    """Actual manager code, real provider active lists, simulated I/O only.

    No native target/factory/import is called. Synthetic closure rows publish
    solely to model maps; the four actual issuance/failure maps are untouched.
    """
    backend = NS(
        functions={},
        states=(),
        metadata=type("Metadata", (), {}),
        configuration=type("Configuration", (), {}),
    )
    sys_view = NS(
        getprofile=sys.getprofile,
        gettrace=sys.gettrace,
        setprofile=sys.setprofile,
        settrace=sys.settrace,
        modules=sys.modules,
        monitoring=monitor,
    )
    body = api["observing_native_imports"].__wrapped__
    kwargs = dict(
        _backend=lambda: backend,
        sys=sys_view,
        os=NS(environ={api["RELEASE"]: "1"}),
        _ISSUED=WeakKeyDictionary(),
        _FAILED=[],
    )
    if active is not None:
        kwargs["_ACTIVE"] = active
    actual = clone(body, **kwargs)
    namespace = actual.__globals__
    manager = contextlib.contextmanager(actual)
    return dict(api, observing_native_imports=manager), namespace


def _metadata_import_row(api, context, label):
    def never_called():
        raise AssertionError("No simulated function is executable authority")

    original = FunctionType(never_called.__code__, {"__builtins__": builtins}, label)
    module = ModuleType("metadata_import_" + label)
    setattr(module, label, original)
    row = NS(
        original=original,
        output=original,
        returned=True,
        primary=None,
        generated="",
        make=None,
        module=module,
        target=((None, label),),
        stack=None,
        original_header=api["_original_header"](original),
        original_bindings=None,
    )
    row.bindings = api["_record_function"](row, context.backend)
    context.rows.append(row)


def test_sim_run_import_composition_provider_state_is_distinct_from_canonical():
    prep = stage.previous.preparation
    api = prep._wrapper_api()
    canonical = vars(prep.imported_wrappers)
    assert api["_ACTIVE"] is prep._WRAPPER_ACTIVE and api["_ACTIVE"] is not canonical["_ACTIVE"]
    assert api["_LOCK"] is prep._WRAPPER_LOCK and api["_LOCK"] is not canonical["_LOCK"]
    assert api["_ISSUED"] is not canonical["_ISSUED"] and api["_FAILED"] is not canonical["_FAILED"]
    all_apis = (api, stage.previous._phase_import_api(), stage._runtime_import_api(), canonical)
    assert len({id(value["_ACTIVE"]) for value in all_apis}) == 4
    assert len({id(value["_ISSUED"]) for value in all_apis}) == 4
    assert all(not value["_ACTIVE"] and not value["_ISSUED"] for value in all_apis)


@pytest.mark.parametrize(
    "mode", ("success", "predecessor_active_alias", "source_failure", "three_slots")
)
def test_sim_run_import_composition_nests_actual_four_provider_bodies_and_cleans_up(mode):
    prep = stage.previous.preparation
    canonical = vars(prep.imported_wrappers)
    apis = (
        prep._wrapper_api(),
        stage.previous._phase_import_api(),
        stage._runtime_import_api(),
        canonical,
    )
    monitor = _MetadataMonitor(available=3 if mode == "three_slots" else 6)
    original_tools = tuple(monitor.tools.items())
    prior = sys.getprofile(), sys.gettrace()
    originals = [dict(api["_ISSUED"].items()) for api in apis]
    model_apis, namespaces = [], []
    for i, api in enumerate(apis):
        active = canonical["_ACTIVE"] if i == 0 and mode == "predecessor_active_alias" else None
        model, namespace = _metadata_import_manager(api, monitor, active=active)
        model_apis.append(model)
        namespaces.append(namespace)
    wrappers = []
    for function, getter, model in (
        (prep.observing_runner_import.__wrapped__, "_wrapper_api", model_apis[0]),
        (stage.previous.observing_phase_import.__wrapped__, "_phase_import_api", model_apis[1]),
        (stage.observing_runtime_import.__wrapped__, "_runtime_import_api", model_apis[2]),
    ):
        body = clone(
            function,
            _ready=lambda: None,
            os=NS(environ={function.__globals__["RELEASE"]: "1"}),
            _IMPORT_EXPORTS=[],
            **{getter: lambda value=model: value},
        )
        wrappers.append(contextlib.contextmanager(body))
    wrappers.append(model_apis[3]["observing_native_imports"])
    contexts = []
    primary, cause = ValueError("metadata callback import failure"), OSError("metadata cause")

    def nested():
        with contextlib.ExitStack() as stack:
            for index, manager in enumerate(wrappers):
                context = stack.enter_context(manager(enabled=True))
                contexts.append(context)
                _metadata_import_row(model_apis[index], context, "scope_" + str(index))
            assert len({context.tool for context in contexts}) == 4
            assert all(context.active for context in contexts)
            assert all(len(api["_ACTIVE"]) == 1 for api in apis)
            if mode == "source_failure":
                raise primary from cause

    try:
        if mode == "success":
            nested()
        elif mode == "source_failure":
            with pytest.raises(ValueError) as caught:
                nested()
            assert caught.value is primary and primary.__cause__ is cause
        else:
            with pytest.raises(prep.imported_wrappers.WrapperAuthorityRejected) as caught:
                nested()
            assert caught.value.stage == (
                "reentry" if mode == "predecessor_active_alias" else "monitor"
            )
    finally:
        assert (sys.getprofile(), sys.gettrace()) == prior
        assert all(not api["_ACTIVE"] for api in apis)
        assert tuple(monitor.tools.items()) == original_tools
        assert monitor.freed == list(reversed(monitor.allocations))
    assert len(contexts) == (3 if mode in ("predecessor_active_alias", "three_slots") else 4)
    if mode == "success":
        assert all(
            context.published and context.monitor_restored and context.hooks_restored
            for context in contexts
        )
        assert all(len(namespace["_ISSUED"]) == 1 for namespace in namespaces)
    else:
        assert all(not namespace["_ISSUED"] for namespace in namespaces)
    assert all(
        dict(api["_ISSUED"].items()) == original
        for api, original in zip(apis, originals, strict=True)
    )
    assert not stage._ISSUED


def _storage_model():
    pool = WeakValueDictionary()
    return NS(
        retained_columns=pool,
        retained_columns_record=pool,
        retention_work=[],
        last_retention_raw=None,
        metadata_work=[],
        invalid=False,
        entry_error=None,
        retention_since_collection_bytes=0,
        metadata_collections=[],
    )


def test_sim_run_storage_350_complete_two_inverse_observations_preserve_every_column(tmp_path):
    from cells.processes import betse_native_single_cell_poisson_observation as observation

    # Synthetic shaped metadata only: neither matrix was produced by a solver.
    first = np.zeros((625, 625), dtype=np.float64)
    second = np.ones((625, 625), dtype=np.float64)
    scope, context, snapshots = observation.Scope((first, second)), _storage_model(), []
    ordinal = None
    try:
        for ordinal in range(350):
            fresh = scope.snapshot(dict(ordinal=ordinal, first=first, second=second, alias=first))
            retained = stage._retain_observation(context, fresh)
            assert retained is not fresh and retained.identity == fresh.identity
            assert retained.descriptor_json == fresh.descriptor_json and len(retained.columns) == 3
            snapshots.append(retained)
    except BaseException as primary:
        software.snapshot.write_json(
            tmp_path / "retained-capacity-failure.json",
            dict(
                failed_ordinal=ordinal,
                completed=len(snapshots),
                pool_columns=len(context.retained_columns),
                allocated_bytes=sum(row[2] for row in context.retention_work),
                collections=context.metadata_collections,
                primary_type=type(primary).__name__,
                primary_message=str(primary),
                native_or_scientific_credit=0,
            ),
        )
        raise
    columns = [row.columns for row in snapshots]
    raw = stage.previous.terminal._column_bytes
    assert len({id(c.values) for row in columns for c in row}) == 1050
    assert all(raw(row[0].values) is raw(columns[0][0].values) for row in columns)
    assert all(raw(row[2].values) is raw(columns[0][0].values) for row in columns)
    assert all(raw(row[1].values) is raw(columns[0][1].values) for row in columns)
    assert raw(columns[0][0].values) is not raw(columns[0][1].values)
    assert len(context.retained_columns) == 2
    assert sum(row[2] for row in context.retention_work) == first.nbytes + second.nbytes == 6250000
    assert len({row.identity for row in snapshots}) == 350
    assert len(context.retention_work) == 350
    assert (
        sum(
            row["call"] == "complete_fresh_observation_immutable_column_retention"
            for row in context.metadata_work
        )
        == 350
    )
    assert (
        context.metadata_collections
        and context.retention_since_collection_bytes < stage.METADATA_COLLECTION_BYTES
    )
    assert sum(c.values.nbytes for c in context.last_retention_raw.columns) == 9375000
    assert context.last_retention_raw.columns[0].values is not columns[-1][0].values
    software.snapshot.write_json(
        tmp_path / "retained-matrix-capacity.json",
        dict(
            synthetic_complete_snapshots=350,
            complete_columns=1050,
            distinct_retained_payload_bytes=6250000,
            last_raw_fresh_column_bytes=9375000,
            conditional_unshared_column_bytes=3281250000,
            live_input_bytes=first.nbytes + second.nbytes,
            independent_headers=1050,
            source_science_or_operator_runs=0,
            total_RSS_or_full_SIM_resource_admission=False,
            metadata_collections=context.metadata_collections,
        ),
    )
    assert not stage._ISSUED


def test_sim_run_storage_fresh_live_mutation_cannot_reuse_prior_scientific_state():
    cache, context = stage.previous.terminal.retained_cache, _storage_model()
    live = np.asarray([[0.0, -0.0], [2.0, 3.0]])
    a = stage._retain_observation(context, cache.snapshot(dict(data=live)))
    original = stage.previous.terminal._column_bytes(a.columns[0].values)
    live[0, 0] = 9.0
    b = stage._retain_observation(context, cache.snapshot(dict(data=live)))
    assert a.identity != b.identity and a.columns[0].values[0, 0] == 0.0
    assert b.columns[0].values[0, 0] == 9.0
    assert stage.previous.terminal._column_bytes(a.columns[0].values) == original
    assert len(context.retained_columns) == 2 and len(context.metadata_work) == 2


@pytest.mark.parametrize("kind", ("dtype", "shape", "nan_payload", "signed_zero"))
def test_sim_run_storage_equal_or_nonfinite_columns_keep_exact_bits_and_layout(kind):
    context, cache = _storage_model(), stage.previous.terminal.retained_cache
    a = np.asarray([0.0, 1.0], dtype=np.float64)
    b = a.copy()
    if kind == "dtype":
        b = b.astype(np.float32)
    elif kind == "shape":
        b = b.reshape((1, 2))
    elif kind == "nan_payload":
        a[0] = struct.unpack("!d", bytes.fromhex("7ff8000000000001"))[0]
        b[0] = struct.unpack("!d", bytes.fromhex("fff8000000000042"))[0]
    else:
        b[0] = -0.0
    first = stage._retain_observation(context, cache.snapshot(a))
    second = stage._retain_observation(context, cache.snapshot(b))
    assert first.identity != second.identity
    assert len(context.retained_columns) == 2
    assert stage.previous.terminal._column_bytes(first.columns[0].values) is not (
        stage.previous.terminal._column_bytes(second.columns[0].values)
    )
    assert cache.validate(first) is first and cache.validate(second) is second


def test_sim_run_storage_declared_source_body_always_captures_before_sharing():
    tree = ast.parse(Path(stage.__file__).read_text())
    for name in ("_snapshot", "_stable"):
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        calls = [(n.lineno, ast.unparse(n.func)) for n in ast.walk(node) if isinstance(n, ast.Call)]
        captured = [line for line, fn in calls if fn == "context.scope.snapshot"]
        shared = [line for line, fn in calls if fn == "_retain_observation"]
        assert len(captured) == len(shared) == 1 and captured[0] < shared[0]


def test_sim_run_storage_unreachable_recursive_metadata_closures_are_collectible():
    cache = stage.previous.terminal.retained_cache

    def closure_columns():
        payloads = {}
        for value in gc.get_objects():
            if (
                type(value) is not FunctionType
                or value.__globals__.get("__name__") != cache.__name__
                or value.__code__.co_qualname
                not in ("snapshot.<locals>.visit", "validate.<locals>.check")
            ):
                continue
            for name, cell in zip(value.__code__.co_freevars, value.__closure__ or (), strict=True):
                if name != "columns":
                    continue
                held = cell.cell_contents
                arrays = held.values() if type(held) is dict else (c.values for c in held)
                for array in arrays:
                    raw = stage.previous.terminal._column_bytes(array)
                    payloads[id(raw)] = len(raw)
        return sum(payloads.values())

    enabled = gc.isenabled()
    gc.collect()
    baseline = closure_columns()
    gc.disable()
    try:
        for _ in range(8):
            observed = cache.snapshot(np.asarray([1.0] * 128))
            cache.validate(observed)
        observed = None
        before = closure_columns()
        reclaimed = gc.collect()
        after = closure_columns()
        assert before > baseline and reclaimed > 0 and after <= baseline
    finally:
        if enabled:
            gc.enable()
        else:
            gc.disable()


def _validation_model(iterations, *, repeated=False):
    cache = stage.previous.terminal.retained_cache
    shared = cache.snapshot("synthetic immutable metadata")
    values = [shared if repeated else cache.snapshot(i) for i in range(9 + 3 * iterations)]
    rows = tuple(
        NS(after=values[9 + i], rng=tuple(values[9 + iterations + 2 * i : 11 + iterations + 2 * i]))
        for i in range(iterations)
    )
    return NS(
        trial=NS(
            before=values[0],
            ready=(values[1],),
            after=(values[2],),
            calendar=values[3],
            sampled=values[4],
            rng_before=tuple(values[5:7]),
            rng_after=tuple(values[7:9]),
            iterations=rows,
        ),
        expected=tuple(values),
        metadata_work=[],
        retained_validation_work=[],
        retained_validation_attempts=0,
        retained_validation_returns=0,
        retained_validation_active=False,
        last_retained_validation=None,
        invalid=False,
        entry_error=None,
    )


def _validation_helper(validate):
    # Closed metadata-only namespace; never production issuance or a native call.
    namespace = dict(vars(stage), previous=NS(terminal=NS(retained_cache=NS(validate=validate))))
    for name in ("_validate_retained", "_retained_validation_sweep"):
        namespace[name] = FunctionType(vars(stage)[name].__code__, namespace, name)
    return namespace["_validate_retained"]


def _validation_sweep(context, function=stage._validate_retained):
    return stage._metadata(
        context, "closed_SIM_complete_retained_cache_validation", function, context
    )


def test_sim_run_validation_every_actual_cache_occurrence_is_fresh_and_ordered():
    context, calls = _validation_model(3), []
    original = stage.previous.terminal.retained_cache.validate

    def checked(value):
        calls.append(value)
        return original(value)

    helper = _validation_helper(checked)
    for _ in range(2):
        _validation_sweep(context, helper)
    assert len(calls) == 36 and all(
        actual is expected for actual, expected in zip(calls, context.expected * 2, strict=True)
    )
    assert len(context.metadata_work) == len(context.retained_validation_work) == 2
    assert context.retained_validation_attempts == context.retained_validation_returns == 36
    first, second = context.retained_validation_work
    assert first["attempt_start"] == 0 and second["attempt_start"] == 18
    assert all(row["attempted"] == row["returned"] == 18 for row in (first, second))
    assert all(row["status"] == "returned" for row in (first, second))


@pytest.mark.parametrize("count", (350, 512))
def test_sim_run_validation_full_observer_call_count_has_bounded_exact_ledger(count, tmp_path):
    context, calls = _validation_model(count, repeated=True), 0
    shared = context.expected[0]

    def checked(value):
        nonlocal calls
        assert value is shared
        calls += 1
        return value

    helper = _validation_helper(checked)
    for _ in range(2 * count):
        _validation_sweep(context, helper)
    expected = 2 * count * (9 + 3 * count)
    assert calls == context.retained_validation_attempts == context.retained_validation_returns
    assert calls == expected > stage.MAX_WORK
    assert len(context.metadata_work) == len(context.retained_validation_work) == 2 * count
    assert len(context.metadata_work) < stage.MAX_WORK == 100000
    assert all(
        row["expected"] == row["attempted"] == row["returned"] == 9 + 3 * count
        for row in context.retained_validation_work
    )
    assert all(row["status"] == "returned" for row in context.metadata_work)
    software.snapshot.write_json(
        tmp_path / "cache-validation-capacity.json",
        dict(
            synthetic_calendar=count,
            modeled_public_validation_calls=2 * count,
            exact_nested_validator_attempts=expected,
            exact_nested_validator_returns=context.retained_validation_returns,
            metadata_operation_records=len(context.metadata_work),
            unchanged_source_C_and_metadata_record_cap=stage.MAX_WORK,
            model_uses_metadata_leaf_counter_not_native_or_scientific_work=True,
            actual_full_SIM_runtime_or_resource_admission=False,
        ),
    )


@pytest.mark.parametrize("index", (0, 4, 8, 9, 17))
def test_sim_run_validation_failed_leaf_keeps_exact_primary_cache_and_absolute_attempt(index):
    context, calls = _validation_model(3), []
    cause = LookupError("retained original cause")
    primary = TypeError("synthetic cache validation failure")
    primary.__cause__ = cause
    fail = False

    def checked(value):
        calls.append(value)
        if fail and len(calls) == 18 + index + 1:
            raise primary
        return value

    helper = _validation_helper(checked)
    _validation_sweep(context, helper)
    fail = True
    with pytest.raises(TypeError) as caught:
        _validation_sweep(context, helper)
    assert caught.value is primary and caught.value.__cause__ is cause
    row = context.retained_validation_work[-1]
    assert row["status"] == context.metadata_work[-1]["status"] == "failed"
    assert row["expected"] == 18 and row["attempt_start"] == 18
    assert row["attempted"] == index + 1 and row["returned"] == index
    assert row["failure_index"] == index and row["failure_cache"] is context.expected[index]
    assert row["primary"] is primary
    assert context.last_retained_validation == (
        row,
        18 + index,
        index,
        context.expected[index],
        primary,
    )
    assert context.retained_validation_attempts == 19 + index
    assert context.retained_validation_returns == 18 + index
    assert not context.retained_validation_active and len(calls) == 19 + index


def test_sim_run_validation_actual_corrupted_cache_rejects_after_prior_valid_sweep():
    context = _validation_model(1)
    original = stage.previous.terminal.retained_cache
    good = original.snapshot(np.asarray([1.0, 2.0]))
    context.trial.iterations[-1].rng = context.trial.iterations[-1].rng[:-1] + (good,)
    _validation_sweep(context)
    good.columns[0].values.shape = (1, 2)
    with pytest.raises(ValueError, match="Changed owned mesh cache column") as caught:
        _validation_sweep(context)
    row = context.retained_validation_work[-1]
    assert row["primary"] is caught.value and row["failure_cache"] is good
    assert row["failure_index"] == 11 and row["attempted"] == 12 and row["returned"] == 11
    assert context.retained_validation_attempts == 24 and context.retained_validation_returns == 23


def test_sim_run_validation_operation_record_cap_still_refuses_before_leaf_work():
    context, entered = _validation_model(1), []
    context.metadata_work = [None] * stage.MAX_WORK
    with pytest.raises(stage.SimRunRejected) as caught:
        _validation_sweep(context, lambda c: entered.append(c))
    assert caught.value.stage == "metadata_work" and caught.value.partial is context
    assert entered == [] and context.retained_validation_attempts == 0
    assert context.retained_validation_work == []


@pytest.mark.parametrize("drift", ("before", "after", "iteration"))
def test_sim_run_validation_missing_rng_occurrence_refuses_before_any_leaf(drift):
    context, entered = _validation_model(1), []
    if drift == "iteration":
        context.trial.iterations[0].rng = context.trial.iterations[0].rng[:-1]
    else:
        name = "rng_" + drift
        setattr(context.trial, name, getattr(context.trial, name)[:-1])
    with pytest.raises(ValueError, match="Both complete RNG caches"):
        _validation_sweep(context, _validation_helper(lambda v: entered.append(v)))
    assert entered == [] and context.retained_validation_attempts == 0
    assert (
        context.retained_validation_work == [] and context.metadata_work[-1]["status"] == "failed"
    )


def test_sim_run_validation_profile_reentry_is_sticky_and_does_not_dispatch_twice():
    context, calls, caught = _validation_model(1), [], []

    def leaf(value):
        calls.append(value)
        return value

    helper, prior = _validation_helper(leaf), sys.getprofile()

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if frame.f_code is leaf.__code__ and event == "return" and not caught:
            try:
                _validation_sweep(context, helper)
            except stage.SimRunRejected as error:
                caught.append(error)

    try:
        sys.setprofile(profile)
        with pytest.raises(stage.SimRunRejected) as raised:
            _validation_sweep(context, helper)
    finally:
        sys.setprofile(prior)
    assert raised.value is caught[0] is context.entry_error
    assert raised.value.stage == "retained_validation" and context.invalid
    assert len(calls) == 1 and not context.retained_validation_active
    assert context.retained_validation_attempts == context.retained_validation_returns == 1
    row = context.retained_validation_work[0]
    assert row["status"] == "failed" and row["primary"] is raised.value
    assert len(context.retained_validation_work) == 1


def test_sim_run_validation_public_work_document_is_detached_from_mutable_ledger():
    context = _validation_model(1)
    _validation_sweep(context)
    observed = stage._retained_validation_document(context)
    assert observed["attempted"] == observed["returned"] == 12
    assert observed["sweeps"] == ((0, 0, 0, 12, 12, 12, "returned", None),)
    observed["attempted"] = 0
    assert context.retained_validation_attempts == 12
    assert observed["sweeps"][0] is not context.retained_validation_work[0]
    assert observed["fresh_validation_of_every_occurrence"]
    assert not observed["capacity_or_scientific_admission"]


def _validation_authority_model():
    context, calls = _validation_model(2), []
    owner = object.__new__(stage.SimRunOwner)
    context.owner, context.active = owner, False
    context.trial.identity = context.sealed_identity = stage._digest("private metadata model")
    context.stable = NS(identity="unchanged stable metadata")
    context.after = (
        context.trial.after[0],
        (("actual modeled graph",), ("exact edge metadata",)),
        context.trial.rng_after,
    )
    context.observed_stable, context.observed_current = context.stable, context.after

    def stable(actual):
        assert actual is context
        calls.append("stable")
        return actual.observed_stable

    def current(actual):
        assert actual is context
        calls.append("fresh full state/graph/RNG")
        return actual.observed_current

    def validate(cache):
        calls.append(cache)
        return stage.previous.terminal.retained_cache.validate(cache)

    authority = clone(
        stage._authority,
        _ISSUED={owner: context},
        _links=lambda actual: calls.append("links"),
        _bindings=lambda actual: calls.append("bindings"),
        _stable=stable,
        _snapshot=current,
        record_document=lambda trial: "private metadata model",
        _validate_retained=_validation_helper(validate),
    )
    return NS(context=context, owner=owner, calls=calls, authority=authority)


def test_sim_run_validation_public_authority_keeps_all_fresh_live_and_history_checks():
    model = _validation_authority_model()
    for _ in range(2):
        assert model.authority(model.owner) is model.context
    calls = model.calls
    assert calls.count("links") == calls.count("bindings") == calls.count("stable") == 2
    assert calls.count("fresh full state/graph/RNG") == 2
    leaves = [value for value in calls if type(value) is not str]
    assert len(leaves) == 30 and all(
        a is b for a, b in zip(leaves, model.context.expected * 2, strict=True)
    )
    assert len(model.context.metadata_work) == 6
    assert model.context.retained_validation_attempts == 30
    assert not stage._ISSUED  # Neither actual live parent nor completed owner was issued.


@pytest.mark.parametrize("drift", ("stable", "values", "graph", "rng"))
def test_sim_run_validation_public_authority_refuses_fresh_live_drift(drift):
    model = _validation_authority_model()
    assert model.authority(model.owner) is model.context
    context, cache = model.context, stage.previous.terminal.retained_cache
    before = context.retained_validation_attempts
    if drift == "stable":
        context.observed_stable = NS(identity="foreign stable state")
    elif drift == "values":
        context.observed_current = (cache.snapshot("changed"), *context.after[1:])
    elif drift == "graph":
        context.observed_current = (
            context.after[0],
            (context.after[1][0], ("changed",)),
            context.after[2],
        )
    else:
        context.observed_current = (
            *context.after[:2],
            (cache.snapshot("changed"), context.after[2][1]),
        )
    with pytest.raises(ValueError, match="changed"):
        model.authority(model.owner)
    assert context.retained_validation_attempts == before + (0 if drift == "stable" else 15)
    assert not stage._ISSUED


def _admission_model():
    request = stage.Request(
        object(), "assembly", "init", "parameters", "source", 3, 3, "original", "request"
    )
    events, contexts = [], []
    stop = LookupError("software stops before constructor verification")

    def ready():
        events.append("ready")

    def context(value, refs):
        assert value is request
        events.append("context")
        result = NS(
            request=value,
            refs=refs,
            invalid=False,
            source_error=None,
            primary=None,
            phase_stage="metadata_boundary",
            active=True,
            owner=None,
            entry_error=None,
        )
        contexts.append(result)
        return result

    def metadata(actual, label, function, *args, **kwargs):
        events.append("blocked downstream verification")
        raise stop

    scope = dict(
        vars(stage),
        _LOCK=RLock(),
        _ACTIVE=[],
        _FAILED=[],
        _PREPARING=None,
        _PREPARATION_FAILURES=[],
        _REQUESTS={request: (object(), object(), object(), object())},
        _CONSUMED={},
        _ISSUED={},
        _ready=ready,
        _context=context,
        _metadata=metadata,
    )
    for name in ("prepare", "_prepare", "_preparation_guard"):
        original = vars(stage)[name]
        copied = FunctionType(original.__code__, scope, name, original.__defaults__)
        copied.__kwdefaults__ = original.__kwdefaults__
        scope[name] = copied
    return NS(
        request=request,
        events=events,
        contexts=contexts,
        stop=stop,
        scope=scope,
        ready=ready,
        context=context,
        prepare=scope["prepare"],
    )


@pytest.mark.parametrize("site", ("ready", "context"))
@pytest.mark.parametrize("event", ("call", "return"))
def test_sim_run_admission_real_profile_reentry_before_context_cannot_double_issue(
    site, event, monkeypatch
):
    model, reentries = _admission_model(), []
    monkeypatch.setenv(stage.RELEASE, "1")
    prior = sys.getprofile()
    target = getattr(model, site)

    def profile(frame, actual, arg):
        if prior is not None:
            prior(frame, actual, arg)
        if frame.f_code is target.__code__ and actual == event and not reentries:
            try:
                model.prepare(model.request, enabled=True)
            except stage.SimRunRejected as error:
                reentries.append(error)

    try:
        sys.setprofile(profile)
        with pytest.raises(stage.SimRunRejected) as caught:
            model.prepare(model.request, enabled=True)
    finally:
        sys.setprofile(prior)
    assert caught.value is reentries[0] and caught.value.stage == "reentrant"
    attempt = model.scope["_PREPARATION_FAILURES"][-1]
    assert attempt["invalid"] and attempt["consumed"] and not attempt["active"]
    assert attempt["request"] is model.request and attempt["entry_error"] is caught.value
    assert model.scope["_PREPARING"] is None and model.scope["_ACTIVE"] == []
    assert model.events == (["ready"] if site == "ready" else ["ready", "context"])
    assert len(model.contexts) == (site == "context")
    assert not model.scope["_ISSUED"] and not stage._ISSUED
    with pytest.raises(stage.SimRunRejected) as repeat:
        model.prepare(model.request, enabled=True)
    assert repeat.value.stage == "consumed"


def test_sim_run_admission_context_failure_is_once_only_and_keeps_original_cause(monkeypatch):
    model = _admission_model()
    monkeypatch.setenv(stage.RELEASE, "1")
    primary, cause = ValueError("context capture failed"), OSError("original cause")

    def fail(*args):
        raise primary from cause

    model.scope["_context"] = fail
    with pytest.raises(stage.SimRunRejected) as caught:
        model.prepare(model.request, enabled=True)
    assert caught.value.stage == "admission" and caught.value.__cause__ is primary
    assert primary.__cause__ is cause
    attempt = caught.value.partial
    assert attempt["primary"] is primary and attempt["consumed"] and attempt["context"] is None
    assert model.scope["_CONSUMED"][model.request] is attempt
    assert model.scope["_PREPARING"] is None and model.events == ["ready"]
    assert not model.scope["_ISSUED"]


def test_sim_run_admission_failure_ledger_refusal_retains_primary_and_attempt(monkeypatch):
    model = _admission_model()
    monkeypatch.setenv(stage.RELEASE, "1")
    primary, secondary = ValueError("original admission failure"), MemoryError("failure ledger")

    class Refusing(list):
        def append(self, value):
            raise secondary

    def ready():
        raise primary

    model.scope["_ready"] = ready
    model.scope["_PREPARATION_FAILURES"] = Refusing()
    with pytest.raises(stage.SimRunRejected) as caught:
        model.prepare(model.request, enabled=True)
    attempt = model.scope["_LAST_PREPARATION_FAILURE"]
    assert caught.value.__cause__ is primary and caught.value.partial is attempt
    assert attempt["primary"] is primary and attempt["recording_error"] == (
        "failure_ledger",
        secondary,
    )
    assert model.scope["_CONSUMED"][model.request] is attempt
    assert model.scope["_PREPARING"] is None and not attempt["active"]


def test_sim_run_validation_profile_reentry_at_count_refuses_before_first_cache():
    context, entered, caught = _validation_model(1), [], []
    helper = _validation_helper(lambda value: entered.append(value))
    prior = sys.getprofile()

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if frame.f_code is stage._count.__code__ and event == "call" and not caught:
            try:
                _validation_sweep(context, helper)
            except stage.SimRunRejected as error:
                caught.append(error)

    try:
        sys.setprofile(profile)
        with pytest.raises(stage.SimRunRejected) as raised:
            _validation_sweep(context, helper)
    finally:
        sys.setprofile(prior)
    assert raised.value is caught[0] is context.entry_error
    assert entered == [] and context.retained_validation_attempts == 0
    assert context.retained_validation_work == [] and not context.retained_validation_active


def test_sim_run_admission_valid_model_serializes_context_then_blocks_before_native(monkeypatch):
    model = _admission_model()
    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.SimRunRejected) as caught:
        model.prepare(model.request, enabled=True)
    assert caught.value.stage == "metadata_boundary" and caught.value.__cause__ is model.stop
    context = model.contexts[0]
    assert caught.value.partial is context and context.invalid and not context.active
    assert model.scope["_CONSUMED"][model.request] is context
    assert model.events == ["ready", "context", "blocked downstream verification"]
    assert model.scope["_PREPARING"] is None and not model.scope["_ACTIVE"]
    assert not model.scope["_ISSUED"]


def _run_observer_model(execute, codes=()):
    cache = stage.previous.terminal.retained_cache.snapshot("synthetic unchanged metadata")
    context = NS(
        observing=False,
        inherited=False,
        capture_errors=[],
        cleanup_errors=[],
        metadata_work=[],
        source_error=None,
        primary=None,
        pending={},
        exceptions=[],
        raw_returns=[],
        nested_codes={},
        expressions=None,
        boundary_seen=False,
        stop=stage._BeforeStorage(),
        last_raw=None,
        last_capture=None,
        last_capture_recording_error=None,
        last_cleanup_error=None,
        last_cleanup_recording_error=None,
        unwinds=[],
        codes={function.__code__: object() for function in codes},
    )
    run = clone(
        stage._run_observed,
        __name__="metadata_SIM_observer_model",
        _execute=execute,
        _profile_event=lambda *args: None,
        _observe=lambda *args: None,
        _guard=lambda actual: None,
        _entry_bindings=lambda actual: None,
        _snapshot=lambda actual: (cache, (("modeled graph",), {}), (cache,)),
    )
    return NS(context=context, run=run)


@pytest.mark.parametrize("kind", ("missing_file", "ESTALE"))
def test_sim_run_observer_handled_original_helper_unwind_is_forensic_not_fatal(kind):
    events, calls = [], 0
    primary = (
        FileNotFoundError("genuine missing helper file")
        if kind == "missing_file"
        else OSError(116, "stale helper retry")
    )

    def helper():
        nonlocal calls
        calls += 1
        events.append("helper")
        if calls == 1:
            raise primary
        return "retry returned"

    def target():
        try:
            helper()
        except OSError:
            events.append("original caller handled")
            assert helper() == "retry returned"

    model = _run_observer_model(lambda actual: target(), (helper, target))
    prior = sys.getprofile(), sys.gettrace()
    model.run(model.context)
    context = model.context
    assert events == ["helper", "original caller handled", "helper"]
    assert context.primary is context.source_error is None
    assert any(error is primary for _, error in context.unwinds)
    assert any(event == "exception" and raw[1] is primary for _, event, raw in context.raw_returns)
    assert context.capture_errors == context.cleanup_errors == []
    assert context.final_hooks == prior == (sys.getprofile(), sys.gettrace())


@pytest.mark.parametrize("recorder", ("raw", "capture", "both"))
def test_sim_run_observer_recorder_failure_keeps_actual_escaping_primary_and_cause(recorder):
    primary, cause = ValueError("source escapes"), OSError("source cause")
    recording = MemoryError("synthetic observer recording failure")

    class Refusing(list):
        def append(self, value):
            raise recording

    def target():
        raise primary from cause

    model = _run_observer_model(lambda actual: target(), (target,))
    context = model.context
    if recorder in ("raw", "both"):
        context.raw_returns = Refusing()
    if recorder in ("capture", "both"):
        context.capture_errors = Refusing()

        def observe(actual, frame, event, arg):
            if frame.f_code is target.__code__ and event in ("exception", "return"):
                raise recording

        model.run.__globals__["_observe"] = observe
    prior = sys.getprofile(), sys.gettrace()
    with pytest.raises(ValueError) as caught:
        model.run(context)
    assert caught.value is primary and primary.__cause__ is cause
    assert context.primary is context.source_error is primary
    assert context.last_capture[1] is recording
    if recorder in ("capture", "both"):
        assert context.last_capture_recording_error[1] is recording
    assert context.final_hooks == prior == (sys.getprofile(), sys.gettrace())


@pytest.mark.parametrize("source_fails", (False, True))
def test_sim_run_observer_inherited_recovery_entry_refusal_cannot_replace_primary(source_fails):
    primary, cause, hook_error = (
        ValueError("escaping source"),
        OSError("source cause"),
        LookupError("recover entry"),
    )
    prior = sys.getprofile(), sys.gettrace()
    entered = []
    custom = None

    def execute(actual):
        # Simulate loss of our profile hook immediately at the source boundary.
        # No native delegate is entered, and recovery must repair both hooks.
        sys.setprofile(custom)
        if source_fails:
            raise primary from cause

    model = _run_observer_model(execute, (execute,))
    original_recover = model.run.__globals__["_recover"]

    def profile(frame, event, arg):
        if prior[0] is not None:
            prior[0](frame, event, arg)
        if frame.f_code is original_recover.__code__ and event == "call":
            entered.append("recovery rejected before body")
            raise hook_error

    custom = profile
    try:
        sys.setprofile(profile)
        with pytest.raises(BaseException) as caught:
            model.run(model.context)
        assert sys.getprofile() is profile and sys.gettrace() is prior[1]
    finally:
        sys.setprofile(prior[0])
        sys.settrace(prior[1])
    assert entered == ["recovery rejected before body"]
    assert any(row[2] is hook_error for row in model.context.cleanup_errors)
    assert model.context.final_hooks == (profile, prior[1])
    if source_fails:
        assert caught.value is primary and primary.__cause__ is cause
    else:
        assert isinstance(caught.value, stage.SimRunRejected) and caught.value.stage == "capture"


@pytest.mark.parametrize("failed_hook", ("profile", "trace"))
def test_sim_run_observer_cleanup_writer_and_getter_failure_still_checks_peer_and_primary(
    failed_hook,
):
    prior, hooks, checked = (object(), object()), {}, []
    primary, cause = ValueError("escaping source"), OSError("source cause")
    capture, writer = LookupError("getter refusal"), MemoryError("cleanup writer refusal")
    armed = False

    class Refusing(list):
        def append(self, value):
            raise writer

    def getter(label):
        checked.append(label)
        if armed and label == failed_hook:
            raise capture
        return hooks[label]

    def setter(label, value):
        hooks[label] = value

    surface = NS(
        getprofile=lambda: getter("profile"),
        gettrace=lambda: getter("trace"),
        setprofile=lambda value: setter("profile", value),
        settrace=lambda value: setter("trace", value),
    )
    hooks.update(profile=prior[0], trace=prior[1])

    def execute(actual):
        nonlocal armed
        armed = True
        raise primary from cause

    model = _run_observer_model(execute)
    model.context.cleanup_errors = Refusing()
    model.run.__globals__["sys"] = surface
    model.run.__globals__["_recover"] = clone(stage._recover, sys=surface)
    with pytest.raises(ValueError) as caught:
        model.run(model.context)
    assert caught.value is primary and primary.__cause__ is cause
    assert "profile" in checked[2:] and "trace" in checked[2:]
    assert hooks == dict(profile=prior[0], trace=prior[1])
    assert model.context.last_cleanup_recording_error[0] is writer
    assert model.context.last_cleanup_error[2] is capture
    assert model.context.final_hooks == tuple(
        None if label == failed_hook else prior[i] for i, label in enumerate(("profile", "trace"))
    )


def test_sim_run_observer_final_hook_identity_refuses_equal_foreign_objects():
    prior = object(), object()

    class ForeignHook:
        def __eq__(self, other):
            return True

    foreign = ForeignHook(), ForeignHook()
    assert foreign == prior and all(a is not b for a, b in zip(foreign, prior, strict=True))
    surface = NS(
        getprofile=lambda: foreign[0],
        gettrace=lambda: foreign[1],
        setprofile=lambda value: None,
        settrace=lambda value: None,
    )
    context = NS(cleanup_errors=[])
    assert clone(stage._recover, sys=surface)(context, prior) is False
    assert context.final_hooks[0] is foreign[0] and context.final_hooks[1] is foreign[1]
    assert context.last_cleanup_error[0] == "final_hooks"


@pytest.mark.parametrize("kind", ("profile", "trace_global", "trace_local"))
@pytest.mark.parametrize("source_fails", (False, True))
def test_sim_run_observer_installed_wrappers_delegate_inherited_recovery_guards(kind, source_fails):
    primary, cause, denied = (
        ValueError("original source"),
        OSError("source cause"),
        LookupError("inherited recovery guard"),
    )
    witnessed, locals_ = [], {}

    def target():
        if source_fails:
            raise primary from cause

    model = _run_observer_model(lambda actual: target(), (target,))
    recover_code = model.run.__globals__["_recover"].__code__
    before = sys.getprofile(), sys.gettrace()

    def witness(frame, event):
        if frame.f_code is recover_code:
            witnessed.append(
                (
                    event,
                    sys.getprofile() is model.context.observers[0],
                    sys.gettrace() is model.context.observers[1],
                )
            )

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if kind == "profile" and frame.f_code is recover_code and event == "call":
            witness(frame, event)
            raise denied

    def local(frame, event, arg):
        if frame.f_code is recover_code and event == "line":
            witness(frame, event)
            raise denied
        return local

    def trace(frame, event, arg):
        fn = before[1] if event == "call" else locals_.get(id(frame))
        if fn is not None:
            result = fn(frame, event, arg)
            if result is not None:
                locals_[id(frame)] = result
        if frame.f_code is recover_code and event == "call":
            if kind == "trace_global":
                witness(frame, event)
                raise denied
            if kind == "trace_local":
                return local
        return trace

    try:
        sys.setprofile(profile)
        sys.settrace(trace)
        with pytest.raises(BaseException) as caught:
            model.run(model.context)
        assert sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    assert witnessed and witnessed[0][1:] == (True, True)
    assert any(row[1] is denied for row in model.context.capture_errors)
    assert any(row[2] is denied for row in model.context.cleanup_errors)
    assert model.context.final_hooks == (profile, trace)
    if source_fails:
        assert caught.value is primary and primary.__cause__ is cause
    else:
        assert isinstance(caught.value, stage.SimRunRejected) and caught.value.stage == "capture"
