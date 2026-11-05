"""Blocked natural-loop protocol controls; no issued parent or native body."""

import ast
import dis
import gc
import os
import struct
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_init_short_history as prefix
from cells.processes import betse_native_init_terminal as stage
from tests.unit import test_betse_native_init_first_step as interpreter_model
from tests.unit import test_betse_native_init_retained_world as guard_model
from validation.betse import betse_native_init_terminal_software as software


@pytest.mark.parametrize(
    "mode",
    (
        "valid",
        "parent_error",
        "falsey_error",
        "wrong_return",
        "before_guard",
        "after_guard",
        "setup",
        "loop",
        "work",
        "bindings",
        "before",
        "stable",
        "stable_graph",
        "unclaimed",
    ),
)
def test_pre_source_parent_check_authenticates_exact_return_and_preserves_failures(
    monkeypatch, mode
):
    from tests.unit import test_betse_native_init_short_history as controls

    original = (
        controls.test_pre_source_parent_check_authenticates_exact_return_and_preserves_failures
    )
    clone(original, stage=stage)(monkeypatch, mode)


def test_pre_source_parent_check_is_after_full_alias_proof_before_source_accounting():
    from tests.unit import test_betse_native_init_short_history as controls

    original = (
        controls.test_pre_source_parent_check_is_after_full_alias_proof_before_source_accounting
    )
    clone(original, stage=stage)()


def clone(function, **values):
    result = FunctionType(
        function.__code__,
        dict(function.__globals__, **values),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    result.__kwdefaults__ = function.__kwdefaults__
    return result


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit immutable native-blocked software release required")
    namespace = dict(vars(guard_model), software=software, _RAW_GUARDS=[])
    function = FunctionType(guard_model.blocked.__wrapped__.__code__, namespace)
    with contextmanager(function)(request, tmp_path, monkeypatch):
        yield


@pytest.mark.parametrize("maximum", (True, False, 0, -1, 513, 1.0, "2", None))
def test_init_terminal_maximum_is_exact_bounded_int(maximum, monkeypatch):
    monkeypatch.setattr(stage, "_ready", lambda: pytest.fail("Readiness must not run"))
    with pytest.raises(ValueError):
        stage.from_electrical(object(), maximum=maximum, law_id=stage.LAW_ID)


@pytest.mark.parametrize("actual,maximum", ((1, 1), (1, 64), (3, 4), (64, 64)))
def test_init_terminal_uses_complete_configured_count_without_shortening(actual, maximum):
    assert stage._configured_count(actual, maximum) is actual
    assert stage._count(maximum) is maximum


@pytest.mark.parametrize("actual", (True, False, 0, -1, 4, 65, 1.0, "2", None))
def test_init_terminal_configured_count_must_fit_without_truncation(actual):
    with pytest.raises(ValueError):
        stage._configured_count(actual, 3)


@pytest.mark.parametrize("entry", ("declaration", "prepare"))
def test_init_terminal_unadopted_gates_precede_foreign_parent_inspection(entry, monkeypatch):
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No supplied owner inspection before genuine provider adoption")

    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.InitTerminalRejected) as caught:
        if entry == "declaration":
            stage.from_electrical(Foreign(), maximum=64, law_id=stage.LAW_ID)
        else:
            stage.prepare(Foreign(), enabled=True)
    assert caught.value.stage == "integration_held"
    assert stage.PARENT_SOURCE_SHA256 is stage.PARENT_REVIEW_SHA256 is None
    assert stage.PARENT_CLAIM is stage.PARENT_CHECK is None
    assert stage.RUNTIME_SOURCE_SHA256 is stage.RUNTIME_REVIEW_SHA256 is None
    assert stage.RUNTIME_BEGIN is stage.RUNTIME_END is stage.RUNTIME_CONTRACT is None
    assert not stage._CONSUMED and not stage._ISSUED


@pytest.mark.parametrize("operation", ("construct", "hydrate", "phase", "trial"))
def test_init_terminal_owner_has_no_supplied_or_hydrated_authority(operation):
    owner = object.__new__(stage.InitTerminalOwner)
    with pytest.raises((TypeError, stage.InitTerminalRejected)):
        if operation == "construct":
            stage.InitTerminalOwner()
        elif operation == "hydrate":
            owner.__reduce_ex__(4)
        else:
            getattr(owner, operation)


@pytest.mark.parametrize("owner_type", (stage.base.FirstStepOwner, prefix.ShortHistoryOwner))
def test_init_terminal_prefix_owner_is_not_a_fresh_electrical_parent(owner_type, monkeypatch):
    calls = []
    binding = NS(module=NS(_authority=lambda owner: calls.append(owner)))
    function = clone(stage.from_electrical, _ready=lambda: binding)
    with pytest.raises(stage.InitTerminalRejected) as caught:
        function(object.__new__(owner_type), maximum=64, law_id=stage.LAW_ID)
    assert caught.value.stage == "owner" and calls == []
    assert not stage._REQUESTS and not stage._CONSUMED


def test_init_terminal_explicit_release_and_law_precede_real_source(monkeypatch):
    monkeypatch.setattr(stage, "_ready", lambda: pytest.fail("No provider admission"))
    with pytest.raises(stage.InitTerminalRejected) as caught:
        stage.prepare(object())
    assert caught.value.stage == "release"
    with pytest.raises(stage.InitTerminalRejected) as caught:
        stage.from_electrical(object(), maximum=2, law_id=prefix.LAW_ID)
    assert caught.value.stage == "law"


def test_init_terminal_request_binds_both_complete_count_and_maximum():
    request = stage.Request(object(), "parent", "source", stage.SELECTION, "mode", 2, 4, "id")
    original = stage.request_record(request)
    assert original["iterations"] == 2 and original["maximum"] == 4
    assert stage.request_record(replace(request, maximum=5)) != original
    assert stage.request_record(replace(request, iterations=3)) != original
    with pytest.raises(TypeError):
        request.__reduce_ex__(4)


def test_init_terminal_plan_keeps_full_calendar_and_independent_held_endpoint(tmp_path):
    plan = stage.source_plan()
    assert stage.SELECTION not in (prefix.SELECTION, stage.base.SELECTION)
    assert plan["one_fresh_parent_one_original_loop"]
    assert plan["original_calendar_dt_sampled_set_and_objects_unchanged"]
    assert plan["completed_first_step_or_short_history_owner_is_not_a_parent"]
    assert plan["natural_calendar_return_and_context_exit_required"]
    assert plan["before_native_pickle"]
    assert not plan["physical_checkpoint_SIM_or_scientific_admission"]
    assert plan["runtime_entry_names_unadopted"] == (None, None)
    software.snapshot.write_json(tmp_path / "terminal-plan.json", plan)


@pytest.mark.parametrize("count", (1, 3, 64))
def test_init_terminal_timeline_preserves_nonuniform_labels_and_refuses_extra_epoch(count):
    ledger = stage._Timeline(count)
    labels = tuple(float(i * i) / 7 for i in range(count))
    for ordinal, label in enumerate(labels):
        ledger.begin(label, ordinal % 2 == 0)
        row = stage.Iteration(
            ordinal, label, ordinal % 2 == 0, NS(identity=str(ordinal)), 0, 0, None
        )
        ledger.end(row)
        assert ledger.records[-1] is row
    assert ledger.completed == count and ledger.current is None
    assert all(row.source_time is label for row, label in zip(ledger.records, labels, strict=True))
    with pytest.raises(ValueError):
        ledger.begin(100.0, False)
    assert ledger.invalid and ledger.completed == count


def test_init_terminal_engine_keeps_original_run_and_namespace_without_selected_stop_rewrite():
    before = tuple(len(value) for value in (stage._REQUESTS, stage._CONSUMED, stage._ISSUED))
    engine = stage._engine(NS())
    assert engine["_run"].__code__ is stage.base._run.__code__
    assert engine["_base_namespace"].__code__ is stage.base._namespace.__code__
    assert engine["_namespace"] is stage._namespace
    assert engine["_loop_boundary"] is stage._loop_boundary
    assert engine["_dispatch"] is stage._dispatch
    assert "_dispatch_impl" not in engine
    assert (
        tuple(len(value) for value in (stage._REQUESTS, stage._CONSUMED, stage._ISSUED)) == before
    )
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    boundary = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_loop_boundary"
    )
    assert not any(
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Attribute)
        and node.exc.attr == "selected_stop"
        for node in ast.walk(boundary)
    )


@pytest.mark.parametrize("drift", ("guard_code", "snapshot_defaults", "account_body"))
def test_init_terminal_engine_refuses_changed_inherited_metadata_before_source(drift, monkeypatch):
    def foreign(context):
        raise AssertionError("Changed inherited code must not execute")

    if drift == "guard_code":
        monkeypatch.setattr(stage.base._guard, "__code__", foreign.__code__)
    elif drift == "snapshot_defaults":
        monkeypatch.setattr(stage.base._snapshot, "__kwdefaults__", {"stable": True})
    else:
        monkeypatch.setattr(stage.base._account.__wrapped__, "__code__", foreign.__code__)
    with pytest.raises(ValueError):
        stage._engine(NS())
    assert not stage._CONSUMED and not stage._ISSUED


def _loop_model(tmp_path, *, count, extra=False):
    """Installed CPython hooks and toy frames only; no live owner/claim registry."""
    h = interpreter_model.installed_iteration_model.__wrapped__(tmp_path)

    def source_loop(self, phase, time_steps, time_steps_sampled, anim_cells):
        for t in time_steps:
            phase.bodies.append(t)
            phase.body_count = len(phase.bodies)
            if phase.source_error is not None:
                raise phase.source_error from phase.source_cause
        phase.post_loop = True

    old_code = h.loop.__code__
    h.loop.__code__ = source_loop.__code__
    h.context.loop_code = h.loop.__code__
    h.context.allowed_codes = frozenset(
        h.loop.__code__ if code is old_code else code for code in h.context.allowed_codes
    )
    h.context.body_names[h.loop.__code__] = h.context.body_names.pop(old_code)
    branch = next(item for item in dis.get_instructions(h.loop) if item.opname == "FOR_ITER")
    h.context.loop_offset = branch.offset
    stage._bind_loop_span(h.context)

    class Calendar:
        def __init__(self):
            self.labels = tuple(float(i * i) / 7 for i in range(count + int(extra)))
            self.next_calls = 0

        def __iter__(self):
            return self

        def __next__(self):
            ordinal = self.next_calls
            self.next_calls += 1
            if ordinal == len(self.labels):
                raise StopIteration
            return self.labels[ordinal]

        def __len__(self):
            return len(self.labels)

        def __getitem__(self, index):
            if type(index) is not int:
                raise AssertionError("Complete original calendar must not be sliced")
            return self.labels[index]

    h.phase.steps = h.calendar = Calendar()
    h.phase.sampled = {h.calendar.labels[0]}
    context = h.context
    context.calendar_raw = (h.calendar, h.phase.sampled, None)
    context.request = NS(iterations=count, maximum=64)
    context.timeline = stage._Timeline(count)
    context.runtime = h.namespace
    metadata_base = NS(**dict(vars(stage.base), previous=h.namespace["previous"]))
    scope = dict(vars(stage), base=metadata_base, _guard=h.namespace["_guard"])
    calls = []

    def begin(claim, *, child, ordinal, source_time, source_frame):
        calls.append(("begin", ordinal, source_time, source_frame))
        return object()

    def end(claim, *, child, ordinal, source_time, source_frame):
        calls.append(("end", ordinal, source_time, source_frame))
        return object()

    scope.update(
        _runtime=lambda ignored: (NS(begin_iteration=begin, finish_iteration=end), object()),
        _diagnostics=lambda ignored: None,
        RUNTIME_BEGIN="begin_iteration",
        RUNTIME_END="finish_iteration",
        # This existing calendar-only model returns scalar identity records,
        # not typed array caches. Real cache retention is exercised below.
        _retain_snapshot=lambda actual, value: value,
    )
    for name in ("_begin", "_end", "_loop_boundary", "_observe", "_dispatch"):
        scope[name] = FunctionType(getattr(stage, name).__code__, scope)
        h.namespace[name] = scope[name]
    h.namespace["_snapshot"] = lambda ignored: NS(identity=str(len(h.phase.bodies)))
    api = h.namespace["previous"].storage.previous.previous.previous
    api.child_dispatch = h.namespace["_dispatch"]
    h.provider_calls = calls
    return h


@pytest.mark.parametrize("count", (1, 3, 5))
def test_init_terminal_installed_hooks_exhaust_whole_calendar_without_selected_stop(
    count, tmp_path
):
    h = _loop_model(tmp_path, count=count)
    required = sys.getprofile(), sys.gettrace()
    h.drive()
    assert h.phase.bodies == list(h.calendar.labels)
    assert h.calendar.next_calls == count + 1
    assert h.context.loop_visits == count + 1 and h.context.timeline.completed == count
    assert h.context.timeline.current is None
    assert h.context.loop_returned and not h.context.selected_stopped and not h.context.stopping
    assert h.phase.post_loop is True
    assert h.context.time_steps is h.calendar and h.context.calendar_raw[0] is h.calendar
    assert h.context.loop_span is h.context.loop_span_record
    assert [(kind, ordinal) for kind, ordinal, _, _ in h.provider_calls] == [
        (kind, ordinal) for ordinal in range(count) for kind in ("begin", "end")
    ]
    assert all(frame is h.context.loop_frame for _, _, _, frame in h.provider_calls)
    assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
    assert not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "natural-loop.json",
        dict(
            labels=h.phase.bodies,
            complete_calendar_retained=True,
            iterator_advances=h.calendar.next_calls,
            completed=h.context.timeline.completed,
            selected_stop=h.context.selected_stopped,
            loop_returned=h.context.loop_returned,
            hooks_restored=True,
            actual_native_owner_or_source_execution=False,
        ),
    )


def test_init_terminal_extra_iteration_refuses_before_extra_body_or_molecular_claim(tmp_path):
    h = _loop_model(tmp_path, count=2, extra=True)
    with pytest.raises(stage.base.FirstStepRejected):
        h.drive()
    assert h.phase.bodies == list(h.calendar.labels[:2])
    assert h.context.timeline.completed == 2 and len(h.context.timeline.records) == 2
    assert not h.context.loop_returned and not h.context.selected_stopped
    assert [ordinal for _, ordinal, _, _ in h.provider_calls] == [0, 0, 1, 1]
    assert h.context.invalid and not stage._ISSUED
    assert not hasattr(h.phase, "post_loop")


@pytest.mark.parametrize("offset", ("actual", "wrong", "bool"))
def test_init_terminal_loop_span_comes_from_actual_unmodified_bytecode(offset):
    def body(calendar):
        for _value in calendar:
            pass
        return None

    branch = next(item for item in dis.get_instructions(body) if item.opname == "FOR_ITER")
    events = []
    context = NS(
        loop_code=body.__code__,
        loop_offset=branch.offset if offset == "actual" else (True if offset == "bool" else -1),
        runtime={"_base_namespace": lambda actual: events.append(actual)},
    )
    namespace = clone(stage._namespace, __name__=__name__)
    if offset == "actual":
        namespace(context)
        assert context.loop_span is context.loop_span_record
        assert context.loop_span == (body.__code__, branch.offset, branch.argval)
    else:
        with pytest.raises(ValueError):
            namespace(context)
    assert events == [context]


@pytest.mark.parametrize("drift", ("missing", "record_missing", "copied", "bool_offset", "exit"))
def test_init_terminal_installed_hooks_refuse_missing_or_changed_span_before_loop_work(
    tmp_path, drift
):
    h = _loop_model(tmp_path, count=2)
    original = h.context.loop_span
    if drift == "missing":
        h.context.loop_span = h.context.loop_span_record = None
    elif drift == "record_missing":
        h.context.loop_span_record = None
    elif drift == "copied":
        h.context.loop_span = tuple(list(original))
    elif drift == "bool_offset":
        h.context.loop_span = h.context.loop_span_record = (original[0], True, original[2])
    else:
        h.context.loop_span = h.context.loop_span_record = (original[0], original[1], original[1])
    required = sys.getprofile(), sys.gettrace()
    with pytest.raises(stage.base.FirstStepRejected, match="sealed outer FOR_ITER") as caught:
        h.drive()
    assert h.phase.bodies == [] and h.calendar.next_calls == 0 and h.provider_calls == []
    assert h.context.timeline.completed == 0 and h.context.timeline.current is None
    assert h.context.invalid and h.context.entry_error is caught.value and not stage._ISSUED
    assert sys.getprofile() is required[0] and sys.gettrace() is required[1]


def test_init_terminal_span_does_not_disappear_on_legitimate_iterator_exhaustion(tmp_path):
    h = _loop_model(tmp_path, count=2)
    span = h.context.loop_span
    seen = []

    def after_exhaustion(frame, event, arg):
        if h.context.timeline.completed == 2 and frame.f_lasti >= span[2]:
            seen.append(frame.f_lasti)
            h.context.loop_span = None

    required = sys.getprofile(), sys.gettrace()
    with h.inherited("trace", "line", after_exhaustion):
        with pytest.raises(stage.base.FirstStepRejected, match="sealed outer FOR_ITER"):
            h.drive()
    assert seen and h.phase.bodies == list(h.calendar.labels)
    assert h.context.timeline.completed == 2 and h.context.timeline.current is None
    assert not getattr(h.phase, "post_loop", False) and not stage._ISSUED
    assert h.context.invalid and not h.context.loop_returned
    assert sys.getprofile() is required[0] and sys.gettrace() is required[1]


def test_init_terminal_canonical_loop_span_binding_is_one_shot_metadata():
    def loop(calendar):
        for _label in calendar:
            pass

    branch = next(row for row in dis.get_instructions(loop) if row.opname == "FOR_ITER")
    context = NS(
        loop_code=loop.__code__, loop_offset=branch.offset, loop_span=None, loop_span_record=None
    )
    stage._bind_loop_span(context)
    span = context.loop_span
    assert span is context.loop_span_record and span == (
        loop.__code__,
        branch.offset,
        branch.argval,
    )
    with pytest.raises(ValueError, match="already bound"):
        stage._bind_loop_span(context)
    assert context.loop_span is span and context.loop_span_record is span


@pytest.mark.parametrize("entry", ("declaration", "preparation"))
@pytest.mark.parametrize("layer", ("profile", "trace"))
def test_init_terminal_caught_public_reentry_is_sticky_before_any_body(entry, layer, tmp_path):
    h = _loop_model(tmp_path, count=2)
    caught = []

    def callback(frame, event, arg):
        stage._ACTIVE.append(h.context)
        try:
            with pytest.raises(stage.base.FirstStepRejected) as error:
                if entry == "declaration":
                    stage.from_electrical(object(), maximum=2, law_id=stage.LAW_ID)
                else:
                    stage.prepare(object())
            caught.append(error.value)
        finally:
            assert stage._ACTIVE.pop() is h.context

    with h.inherited(layer, "call", callback):
        with pytest.raises(stage.base.FirstStepRejected) as error:
            h.drive()
    assert error.value is caught[0] is h.context.entry_error
    assert h.phase.bodies == [] and h.calendar.next_calls == 0 and not h.provider_calls
    assert h.context.invalid and not stage._ISSUED


@pytest.mark.parametrize("failure", ("none", "snapshot", "diagnostics", "provider"))
def test_init_terminal_iteration_retains_real_raw_return_before_fallible_capture(failure):
    raw, after, frame = object(), NS(identity="after"), sys._getframe()
    source = ValueError("provider primary")
    capture = OSError("observation failed")
    calls = []
    context = NS(
        timeline=stage._Timeline(1),
        molecule_claim=object(),
        work=[],
        callback_calls=[],
        runtime={},
    )
    label = float("0.125")
    context.timeline.begin(label, True)

    def end(claim, **kwargs):
        calls.append((claim, kwargs))
        if failure == "provider":
            raise source
        return raw

    def snapshot(actual):
        assert actual is context and context.last_iteration_raw is raw
        if failure == "snapshot":
            raise capture
        return after

    def diagnostics(actual):
        assert actual is context and context.last_iteration_raw is raw
        if failure == "diagnostics":
            raise capture
        return None

    observed = []
    context.runtime.update(
        _snapshot=snapshot,
        _capture=lambda *args: observed.append(args),
    )
    function = clone(
        stage._end,
        _runtime=lambda actual: (NS(finish_iteration=end), context.molecule_claim),
        _diagnostics=diagnostics,
        RUNTIME_END="finish_iteration",
        _retain_snapshot=lambda actual, value: value,
    )
    if failure == "none":
        function(context, frame)
        assert context.timeline.records[0].molecular_record is raw
        assert context.timeline.records[0].after is after
        assert context.timeline.completed == 1
    else:
        with pytest.raises(BaseException) as caught:
            function(context, frame)
        if failure == "provider":
            assert caught.value is source and not hasattr(context, "last_iteration_raw")
        elif failure == "snapshot":
            assert caught.value is capture and context.last_iteration_raw is raw
        else:
            assert caught.value.__cause__ is capture
            assert observed[0][2] is capture and observed[0][3] == (frame, after, raw)
        assert context.timeline.completed == 0 and context.timeline.current[1] is label
        assert context.timeline.records == []
    assert context.last_iteration_end == (frame, (0, label, True))
    assert calls[0][1]["source_frame"] is frame and calls[0][1]["source_time"] is label


def _natural_model(*, exit_arguments=(None, None, None), exit_result=False):
    """Real returned toy frames only; these rows never become native owner authority."""
    returned, rows, work = [], {}, []
    labels, sampled = (0.0, 0.125), {0.0}
    sim, phase = object(), NS(bodies=[])

    class Solver:
        def __enter__(self):
            return None

        def __exit__(self, typ, value, traceback):
            return exit_result

    def loop(self, phase, time_steps, time_steps_sampled):
        for label in time_steps:
            phase.bodies.append(label)
        return None

    def setup(self, phase, time_steps, time_steps_sampled, solver_context):
        exception_instability = None
        solver_context.__enter__()
        loop(self, phase, time_steps, time_steps_sampled)
        solver_context.__exit__(*exit_arguments)
        assert exception_instability is None
        return None

    functions = {
        setup.__code__: ("setup", setup),
        loop.__code__: ("_run_sim_core_loop", loop),
        Solver.__enter__.__code__: ("solver_context_enter", Solver.__enter__),
        Solver.__exit__.__code__: ("solver_context_exit", Solver.__exit__),
    }
    hooks = sys.getprofile(), sys.gettrace()

    def profile(frame, event, arg):
        if hooks[0] is not None:
            hooks[0](frame, event, arg)
        if event == "return" and frame.f_code in functions:
            role, _ = functions[frame.f_code]
            returned.append((frame, arg))
            row = dict(
                frame=frame,
                code=frame.f_code,
                globals=frame.f_globals,
                name=role,
                body_started=True,
                returned=True,
                suspended=False,
                unwound_error=None,
            )
            rows[id(frame)] = row
            work.append(row)

    solver = Solver()
    try:
        sys.setprofile(profile)
        setup(sim, phase, labels, sampled, solver)
    finally:
        try:
            sys.settrace(hooks[1])
        finally:
            sys.setprofile(hooks[0])
    assert sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]
    frames = {row["name"]: row["frame"] for row in work}
    timeline = stage._Timeline(2)
    for ordinal, label in enumerate(labels):
        timeline.begin(label, label in sampled)
        timeline.end(
            stage.Iteration(ordinal, label, label in sampled, NS(identity=str(ordinal)), 0, 0, None)
        )
    context = NS(
        primary=None,
        capture_error=None,
        entry_error=None,
        invalid=False,
        observing=False,
        selected_stopped=False,
        stopping=False,
        loop_returned=True,
        cleanup_errors=(),
        hooks_safe=True,
        timeline=timeline,
        request=NS(iterations=2, maximum=64),
        p=NS(init_tsteps=2),
        loop_visits=3,
        calendar_raw=(labels, sampled, solver),
        time_steps=labels,
        sampled=sampled,
        solver_context=solver,
        noop_entries=sum(row["name"].startswith("solver_context_") for row in work),
        setup_frame=frames["setup"],
        loop_frame=frames["_run_sim_core_loop"],
        loop_code=loop.__code__,
        sim=sim,
        phase=phase,
        methods={"setup": setup, "_run_sim_core_loop": loop},
        noop_methods=(Solver.__enter__, Solver.__exit__),
        initial=NS(),
        frames=rows,
        work=work,
        raw_returns=returned,
        terminal_status=None,
        terminal_status_record=None,
        context_returned=False,
    )
    return context


def test_init_terminal_natural_status_retains_actual_return_frames_and_same_raw_tuples(tmp_path):
    context = _natural_model()
    status = stage._natural_terminal(context)
    assert type(status) is stage.NaturalTerminalStatus and status.child is context
    assert status.calendar_raw is context.calendar_raw
    assert status.loop_frame is context.loop_frame
    assert status.loop_raw is context.raw_returns[1]
    assert status.context_raw is context.raw_returns[2]
    assert status.context_frame is status.context_raw[0]
    assert status.context_frame.f_back is context.setup_frame
    assert status.exception_arguments == (None, None, None)
    assert status.selected_stop is False and status.before_native_pickle is True
    context.terminal_status = context.terminal_status_record = status
    context.context_returned = True
    assert stage._terminal_runtime_status(context) is status
    with pytest.raises(ValueError, match="already attempted"):
        stage._natural_terminal(context)
    assert not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "natural-status.json",
        dict(
            returned_roles=[row["name"] for row in context.work],
            loop_return_is_None=status.loop_raw[1] is None,
            context_return_is_False=status.context_raw[1] is False,
            exact_retained_raw_tuples=True,
            same_status_returned=True,
            private_toy_frames_not_native_authority=True,
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "no_loop_return",
        "selected_stop",
        "active_iteration",
        "incomplete_count",
        "wrong_configured_count",
        "wrong_visit_count",
        "bool_visit_count",
        "calendar_retarget",
        "frame_retarget",
        "foreign_namespace",
        "unreturned_row",
        "suspended_row",
        "unstarted_row",
        "unwound_row",
        "missing_work",
        "duplicate_raw",
        "raw_order",
        "pending_falsey_primary",
        "capture_error",
        "unsafe_hooks",
    ),
)
def test_init_terminal_normal_witness_refuses_incomplete_foreign_or_failed_evidence(mutation):
    context = _natural_model()
    stage._natural_terminal(context)
    row = context.frames[id(context.loop_frame)]
    if mutation == "no_loop_return":
        context.loop_returned = False
    elif mutation == "selected_stop":
        context.selected_stopped = True
    elif mutation == "active_iteration":
        context.timeline.current = (2, 0.5, False)
    elif mutation == "incomplete_count":
        context.timeline.completed = 1
    elif mutation == "wrong_configured_count":
        context.p.init_tsteps = 3
    elif mutation == "wrong_visit_count":
        context.loop_visits = 2
    elif mutation == "bool_visit_count":
        context.loop_visits = True
    elif mutation == "calendar_retarget":
        context.time_steps = tuple(list(context.time_steps))
    elif mutation == "frame_retarget":
        context.loop_frame = context.setup_frame
    elif mutation == "foreign_namespace":
        original = context.methods["_run_sim_core_loop"]
        context.methods["_run_sim_core_loop"] = clone(original)
    elif mutation == "unreturned_row":
        row["returned"] = False
    elif mutation == "suspended_row":
        row["suspended"] = True
    elif mutation == "unstarted_row":
        row["body_started"] = False
    elif mutation == "unwound_row":
        row["unwound_error"] = FalseSourceError("unwound")
    elif mutation == "missing_work":
        context.work.remove(row)
    elif mutation == "duplicate_raw":
        context.raw_returns.append(context.raw_returns[1])
    elif mutation == "raw_order":
        context.raw_returns[1:3] = reversed(context.raw_returns[1:3])
    elif mutation == "pending_falsey_primary":
        context.primary = FalseSourceError("original failed source")
    elif mutation == "capture_error":
        context.capture_error = OSError("capture unavailable")
    elif mutation == "unsafe_hooks":
        context.hooks_safe = False
    with pytest.raises(ValueError):
        stage._natural_terminal(context)
    assert not stage._ISSUED


@pytest.mark.parametrize(
    "arguments,result",
    (
        ((False, None, None), False),
        ((None, False, None), False),
        ((None, None, False), False),
        ((None, None, None), None),
        ((None, None, None), 0),
        ((None, None, None), True),
    ),
)
def test_init_terminal_normal_context_requires_exact_None_arguments_and_False_return(
    arguments, result
):
    context = _natural_model(exit_arguments=arguments, exit_result=result)
    with pytest.raises(ValueError, match="normal loop/context/caller"):
        stage._natural_terminal(context)


@pytest.mark.parametrize(
    "mutation",
    ("copied", "raw_tuple", "calendar_tuple", "foreign_child", "falsey_arg", "not_returned"),
)
def test_init_terminal_runtime_inspection_never_reconstructs_or_promotes_retargeted_status(
    mutation,
):
    context = _natural_model()
    status = stage._natural_terminal(context)
    context.terminal_status = context.terminal_status_record = status
    context.context_returned = True
    assert stage._terminal_runtime_status(context) is status
    if mutation == "copied":
        context.terminal_status = replace(status)
    elif mutation == "raw_tuple":
        object.__setattr__(status, "loop_raw", tuple(list(status.loop_raw)))
    elif mutation == "calendar_tuple":
        object.__setattr__(status, "calendar_raw", tuple(list(status.calendar_raw)))
    elif mutation == "foreign_child":
        object.__setattr__(status, "child", object())
    elif mutation == "falsey_arg":
        object.__setattr__(status, "exception_arguments", (None, False, None))
    else:
        context.context_returned = False
    with pytest.raises(ValueError):
        stage._terminal_runtime_status(context)
    assert context.terminal_status_record is status and not stage._ISSUED


@dataclass(frozen=True)
class _DiagnosticMetadata:
    value: str = "metadata only"


def _closed_model():
    labels, sampled = (0.0, 0.125), {0.0}
    ledger = stage._Timeline(2)
    for ordinal, label in enumerate(labels):
        ledger.begin(label, label in sampled)
        ledger.end(
            stage.Iteration(
                ordinal, label, label in sampled, NS(identity=str(ordinal)), 3, 1, object()
            )
        )

    def snapshot(value):
        return NS(identity=repr(value))

    trial = stage.Trial(
        request_identity="request",
        parent_identity="parent",
        before=NS(identity="before"),
        after=NS(identity="after"),
        calendar=snapshot(labels),
        sampled=snapshot(tuple(sampled)),
        dt=snapshot(0.1),
        iterations=tuple(ledger.records),
        work=(),
        helpers=(),
        callbacks=(),
        raw_returns=(),
        rng_before=("original-before",),
        rng_after=("actual-after",),
        source_completed=True,
        loop_returned=True,
        context_returned=True,
        selected_stop=False,
        initial_diagnostics=_DiagnosticMetadata(),
        identity="trial",
    )
    context = NS(
        timeline=ledger,
        request=NS(iterations=2, maximum=64),
        stream_ids=("original-before",),
        parent=object(),
        sampled=sampled,
        time_steps=labels,
        calendar_raw=(labels, sampled, None),
        p=NS(dt=0.1),
    )
    metadata_base = NS(
        previous=NS(
            storage=NS(
                previous=NS(
                    _streams=lambda parent: (NS(identity="actual-after"),),
                    _scope=lambda parent: NS(snapshot=snapshot),
                )
            )
        )
    )

    def validate(claim, record, *, child, ordinal, source_time):
        row = context.timeline.records[ordinal]
        assert child is context
        assert record is row.molecular_record and source_time is row.source_time
        return record

    check = clone(
        stage._closed_protocol,
        base=metadata_base,
        _terminal_runtime_status=lambda actual: None,
        _runtime=lambda actual: (NS(validate_iteration=validate), object()),
    )
    return NS(context=context, trial=trial, check=check)


@pytest.mark.parametrize(
    "mutation",
    (
        "unchanged",
        "selected_stop",
        "loop_returned",
        "context_returned",
        "source_completed",
        "rng_before",
        "rng_after",
        "calendar_retarget",
        "sampled_retarget",
        "dt",
        "ordinal_bool",
        "sample_int",
        "signed_zero",
        "completed_bool",
        "active_iteration",
    ),
)
def test_init_terminal_closed_protocol_binds_normal_terminal_calendar_bits_and_streams(mutation):
    h = _closed_model()
    original = stage.trial_record(h.trial)
    if mutation in ("loop_returned", "context_returned", "source_completed"):
        h.trial = replace(h.trial, **{mutation: False})
    elif mutation == "selected_stop":
        h.trial = replace(h.trial, selected_stop=True)
    elif mutation in ("rng_before", "rng_after"):
        h.trial = replace(h.trial, **{mutation: ("different",)})
    elif mutation == "calendar_retarget":
        h.context.time_steps = tuple(list(h.context.time_steps))
    elif mutation == "sampled_retarget":
        h.context.sampled = set(h.context.sampled)
    elif mutation == "dt":
        h.context.p.dt = 0.2
    elif mutation == "ordinal_bool":
        object.__setattr__(h.trial.iterations[0], "ordinal", False)
    elif mutation == "sample_int":
        object.__setattr__(h.trial.iterations[0], "sampled", 1)
    elif mutation == "signed_zero":
        object.__setattr__(h.trial.iterations[0], "source_time", -0.0)
    elif mutation == "completed_bool":
        h.context.timeline.completed = True
    elif mutation == "active_iteration":
        h.context.timeline.current = (2, 0.5, False)
    if mutation == "unchanged":
        h.check(h.context, h.trial)
        assert original["iterations"][0][1] == struct.pack("!d", 0.0).hex()
        assert original["rng_before"] == h.trial.rng_before
        assert original["rng_after"] == h.trial.rng_after
        assert original["loop_returned"] and original["context_returned"]
        assert not original["selected_stop"]
    else:
        with pytest.raises(ValueError):
            h.check(h.context, h.trial)
    assert not stage._ISSUED


class FalseSourceError(ValueError):
    def __bool__(self):
        return False


@pytest.mark.parametrize("broken_journal", (False, True))
def test_init_terminal_outer_failure_keeps_falsey_primary_and_independent_hook_cleanup(
    monkeypatch, tmp_path, broken_journal
):
    source, cause = FalseSourceError("original source"), OSError("source cause")
    source.__cause__ = cause
    admission, capture = ValueError("later admission"), RuntimeError("later capture")
    required, hooks, actions = (object(), object()), [None, None], []

    class BrokenJournal:
        def __add__(self, value):
            raise LookupError("secondary cleanup journal")

    def set_hook(index, value):
        actions.append(index)
        hooks[index] = value
        if broken_journal:
            raise OSError("setter raised after restoration")

    context = NS(
        initial=NS(atoms=lambda fn: (fn,), checker=object()),
        p=NS(init_tsteps=2),
        entry_error=None,
        primary=None,
        first_failure=None,
        capture_error=None,
        active=True,
        invalid=False,
        stage="synthetic_source_unwind",
        setters=tuple(lambda value, i=i: set_hook(i, value) for i in range(2)),
        getters=tuple(lambda i=i: hooks[i] for i in range(2)),
        required_hooks=required,
        cleanup_errors=BrokenJournal() if broken_journal else (),
        trial=None,
    )
    parent = NS(trial=NS(identity="sealed"))
    binding = NS(
        module=NS(
            _authority=lambda owner: parent,
            _snapshot=lambda value: NS(identity="sealed"),
            _graph=lambda value: ((), ()),
        ),
        claim=lambda *args, **kwargs: parent,
    )
    request = stage.Request(object(), "parent", "mode", stage.SELECTION, "value", 2, 4, "id")
    refs = (parent, parent.trial, NS(identity="sealed"), ((), ()))

    def fail(current):
        try:
            raise source from cause
        except FalseSourceError as original:
            current.first_failure = ("source", original)
            current.primary = original
            current.entry_error, current.capture_error = admission, capture
            raise capture from original

    metadata_base = NS(**dict(vars(stage.base)))
    metadata_base._digest, metadata_base._context = lambda value: "mode", lambda *args: context
    metadata_base.previous = NS(_callable_atoms=lambda current, fn: (fn,))
    namespace = dict(
        vars(stage),
        base=metadata_base,
        _ready=lambda: binding,
        _parent=lambda value: None,
        _engine=lambda current: {"_namespace": fail, "_claim_wrapper": object()},
        source_plan=lambda: {},
        _REQUESTS={request: refs},
        _CONSUMED={},
        _RETIRED={},
        _ISSUED={},
        _ACTIVE=[],
        _FAILED=[],
    )
    prepare = FunctionType(stage.prepare.__code__, namespace)
    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.InitTerminalRejected) as caught:
        prepare(request, enabled=True)
    assert caught.value.__cause__ is source and source.__cause__ is cause
    assert context.failure_error is source and context.secondary_error == (capture, source)
    assert actions == [1, 0] and tuple(hooks) == required and context.hooks_safe
    assert namespace["_FAILED"] == [context] and not namespace["_ISSUED"]
    assert context.trial is None
    if broken_journal:
        assert isinstance(context.cleanup_journal_error[0], LookupError)
    software.snapshot.write_json(
        tmp_path / "outer-failure.json",
        dict(
            primary=str(source),
            falsey_primary=not bool(source),
            cause=str(cause),
            capture=str(capture),
            independent_hook_restoration=actions,
            original_primary_and_cause_retained=True,
            no_trial_or_owner=True,
        ),
    )


def _software_inputs():
    return dict(
        selection="init_terminal",
        cpu=4,
        threads=1,
        metadata_bytes=512 * 2**20,
        software_bytes=2**30,
        wall_seconds=480,
        reserve_bytes=8 * 2**30,
        software_release_requested=True,
        terminal_metadata_only=True,
        actual_parent_native_operator_RNG_reference_or_scientific_release=False,
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("selection", "other"),
        ("cpu", True),
        ("threads", True),
        ("wall_seconds", 1800),
        ("software_bytes", 512 * 2**20),
        ("reserve_bytes", 0),
        ("software_release_requested", 1),
        ("terminal_metadata_only", False),
        ("actual_parent_native_operator_RNG_reference_or_scientific_release", True),
    ),
)
def test_init_terminal_runner_rejects_resource_release_and_selector_drift(field, value):
    inputs = _software_inputs()
    software._prepared_policy(inputs, "init_terminal", cpu=4)
    inputs[field] = value
    with pytest.raises(ValueError):
        software._prepared_policy(inputs, "init_terminal", cpu=4)


def test_init_terminal_runner_preserves_real_nested_reporter_and_all_native_blocks():
    scope = software._scope()
    assert scope["base"].reuse.Reports is software.Reports
    assert scope["is_forbidden_frame"] is software.is_forbidden_frame
    assert software.reused.FORBIDDEN_MODULES <= software.FORBIDDEN_MODULES
    assert "cells.processes.betse_native_init_terminal_molecules" in software.FORBIDDEN_MODULES
    assert software._cpu(4) == 4 and software._cpu(6) == 6
    for invalid in (True, False, 0, 3, 4.0, "4", None):
        with pytest.raises(ValueError):
            software._cpu(invalid)


@pytest.mark.parametrize("name", ("_namespace", "_run"))
def test_init_terminal_runner_blocks_literal_engine_dispatch_names(name):
    frame = NS(
        f_globals={"__name__": "cells.processes.betse_native_init_terminal"},
        f_code=NS(co_name=name),
    )
    assert software.is_forbidden_frame(frame)


def _overlay_model(tmp_path):
    root = tmp_path / "overlay"
    package = root / "PIL"
    package.mkdir(parents=True)
    path = package / "__init__.py"
    path.write_text("# Synthetic overlay metadata; never imported.\n")
    (package / "unused.py").write_text("# Unimported, no loaded credit.\n")
    declared = software._overlay_inventory((("pillow", "PIL", root),))
    module = ModuleType("PIL")
    module.__file__ = str(path)
    module.__spec__ = NS(origin=str(path))
    return NS(path=path, module=module, declared=declared)


@pytest.mark.parametrize("loaded", (False, True))
def test_init_terminal_overlay_manifest_keeps_unused_files_without_false_import_credit(
    tmp_path, loaded
):
    h = _overlay_model(tmp_path)
    result = software._loaded_overlays(h.declared, modules={"PIL": h.module} if loaded else {})
    row = result["pillow"]
    assert row["used"] is loaded
    assert len(row["loaded"]) == int(loaded)
    assert "PIL/unused.py" in row["unused_files"]
    assert ("PIL/__init__.py" in row["unused_files"]) is not loaded
    assert row["unused_files_have_no_loaded_producer_credit"]
    software.snapshot.write_json(tmp_path / "overlay-metadata.json", result)


@pytest.mark.parametrize("mutation", ("origin", "hash", "spec", "unlisted"))
def test_init_terminal_loaded_overlay_origin_and_bytes_must_match_predeclared_manifest(
    tmp_path, mutation
):
    h = _overlay_model(tmp_path)
    software._loaded_overlays(h.declared, modules={"PIL": h.module})
    if mutation == "origin":
        foreign = tmp_path / "foreign.py"
        foreign.write_bytes(h.path.read_bytes())
        h.module.__file__ = str(foreign)
        h.module.__spec__.origin = str(foreign)
    elif mutation == "hash":
        original = h.path.read_bytes()
        h.path.write_bytes(original.replace(b"Synthetic", b"synthetic"))
        assert h.path.stat().st_size == len(original)
    elif mutation == "spec":
        h.module.__spec__.origin = str(tmp_path / "different.py")
    else:
        foreign = h.path.with_name("late.py")
        foreign.write_bytes(h.path.read_bytes())
        h.module.__file__ = str(foreign)
        h.module.__spec__.origin = str(foreign)
    with pytest.raises(ValueError):
        software._loaded_overlays(h.declared, modules={"PIL": h.module})


def _terminal_permission_model(*, molecular=False, gap=False):
    """Unissued holders and real source-effect derivation; no runtime issuer."""
    context = NS(
        sim=NS(),
        phase=NS(callbacks=NS()),
        gap=NS() if gap else None,
        callback_nodes={
            "progressed_next": ast.parse(
                "def progressed_next(self):\n    self.progress += 1\n"
            ).body[0]
        },
        molecule_permissions=(),
    )
    context.runtime = stage._engine(context)
    original = context.runtime["_base_mutation_contract"](context)
    network = NS()
    if molecular:
        # Synthetic permission metadata, never a genuine molecular claimant.
        context.molecule_permissions = (
            (context.sim, frozenset(("molecular_probe",))),
            (network, frozenset(("runtime_probe",))),
        )
    return NS(context=context, original=original, network=network)


@pytest.mark.parametrize("mode", ("source_only", "molecular", "molecular_gap"))
def test_init_terminal_permission_union_matches_real_source_and_runtime_holders(tmp_path, mode):
    h = _terminal_permission_model(molecular=mode != "source_only", gap=mode == "molecular_gap")
    context = h.context
    before = tuple((owner, vars(owner).copy()) for owner, _ in h.original)
    runtime_rows = context.molecule_permissions
    actual = stage._mutation_contract(context)
    expected = h.original
    if mode != "source_only":
        expected = (
            (context.sim, h.original[0][1] | runtime_rows[0][1]),
            *h.original[1:],
            runtime_rows[1],
        )
    assert context.runtime["_mutation_contract"] is stage._mutation_contract
    assert context.molecule_permissions is runtime_rows
    assert len(actual) == len(expected) and len({id(owner) for owner, _ in actual}) == len(actual)
    assert all(
        owner is original and fields == allowed and type(fields) is frozenset
        for (owner, fields), (original, allowed) in zip(actual, expected, strict=True)
    )
    assert all(vars(owner) == fields for owner, fields in before)
    assert any(owner is context.phase.callbacks for owner, _ in actual)
    assert any(owner is h.network for owner, _ in actual) is (mode != "source_only")
    software.snapshot.write_json(
        tmp_path / "permissions.json",
        dict(
            mode=mode,
            source_rows=len(h.original),
            merged_rows=len(actual),
            fields=[sorted(fields) for _, fields in actual],
            real_source_effects_and_merge=True,
            runtime_rows_are_synthetic_metadata=True,
            actual_owner_or_claim=False,
        ),
    )


@pytest.mark.parametrize("fields", ({"probe"}, ["probe"], frozenset((1,))))
def test_init_terminal_permission_union_refuses_mutable_or_nontext_fields(fields):
    h = _terminal_permission_model()
    assert stage._mutation_contract(h.context) == h.original
    h.context.molecule_permissions = ((h.network, fields),)
    with pytest.raises(ValueError, match="Exact original runtime field permissions"):
        stage._mutation_contract(h.context)
    assert h.context.molecule_permissions[0][1] is fields


@pytest.mark.parametrize("missing", ("base_contract", "runtime_rows"))
def test_init_terminal_permission_union_has_no_missing_contract_fallback(missing):
    h = _terminal_permission_model(molecular=True)
    assert len(stage._mutation_contract(h.context)) == len(h.original) + 1
    if missing == "base_contract":
        del h.context.runtime["_base_mutation_contract"]
        error = KeyError
    else:
        del h.context.molecule_permissions
        error = AttributeError
    with pytest.raises(error):
        stage._mutation_contract(h.context)


@pytest.mark.parametrize(
    "mutation",
    (
        "unchanged",
        "missing_field",
        "extra_field",
        "equal_holder",
        "foreign_holder",
        "duplicate_holder",
        "missing_sim",
        "permissions_not_tuple",
        "fields_not_frozen",
        "runtime_without_enabled_parent",
    ),
)
def test_init_terminal_permission_union_remains_subject_to_actual_roster_checker(mutation):
    """Generic real checker only; terminal ancestor issuance remains unimplemented."""
    h = _terminal_permission_model(gap=True)
    context = h.context
    context.permissions = stage._mutation_contract(context)
    lease = NS(
        child=context,
        module=stage,
        parent=NS(sim=context.sim, request=NS(native_molecules=False), molecule_session=None),
        objects=tuple((str(index), owner) for index, (owner, _) in enumerate(context.permissions)),
    )
    checker = stage.base.previous.storage.previous._first_step_permissions
    assert checker(lease) is context.permissions
    rows = list(context.permissions)
    if mutation == "missing_field":
        assert rows[0][1]
        rows[0] = (rows[0][0], rows[0][1] - {next(iter(rows[0][1]))})
    elif mutation == "extra_field":
        rows[0] = (rows[0][0], rows[0][1] | {"unowned_permission_probe"})
    elif mutation == "equal_holder":
        equal = NS(**vars(context.sim))
        assert equal == context.sim and equal is not context.sim
        rows[0] = (equal, rows[0][1])
    elif mutation == "foreign_holder":
        rows[0] = (object(), rows[0][1])
    elif mutation == "duplicate_holder":
        rows[1] = rows[0]
    elif mutation == "missing_sim":
        rows.pop(0)
    elif mutation == "fields_not_frozen":
        rows[0] = (rows[0][0], set(rows[0][1]))
    elif mutation == "runtime_without_enabled_parent":
        context.molecule_permissions = ((context.sim, frozenset(("molecular_probe",))),)
        rows = list(stage._mutation_contract(context))
    context.permissions = rows if mutation == "permissions_not_tuple" else tuple(rows)
    if mutation == "unchanged":
        assert checker(lease) is context.permissions
    else:
        with pytest.raises(ValueError):
            checker(lease)


@pytest.mark.parametrize(
    "change", ("unchanged", "copied", "foreign_holder", "extra_field", "mutable_field", "missing")
)
def test_init_terminal_permission_union_retains_exact_runtime_tuple_gate(change):
    """Actual binding code with an isolated metadata provider, never an issued runtime."""
    h = _terminal_permission_model(molecular=True)
    context, claim, session, source = h.context, object(), object(), object()
    rows = context.molecule_permissions
    calls = []

    def runtime_permissions(actual):
        assert actual is claim
        calls.append("permissions")
        return rows

    def active(actual, *, child):
        assert actual is claim and child is context
        calls.append("active")
        return claim

    api = NS(
        session_of=lambda actual, *, child: session,
        session_provider=lambda actual, *, child: source,
        runtime_members=lambda actual: (),
        runtime_codes=lambda actual: (),
        runtime_permissions=runtime_permissions,
        validate_runtime_active=active,
    )
    context.parent, context.molecule = NS(molecule_session=session), source
    context.molecule_claim, context.molecule_record = claim, None
    context.molecule_members = context.molecule_expressions = ()
    context.molecule_codes = frozenset()
    context.terminal_runtime_functions = context.terminal_runtime_function_atoms = ()
    check = clone(stage._terminal_bindings, _runtime=lambda actual: (api, claim))
    assert check(context)[3] is rows
    assert calls == ["permissions", "active"]
    calls.clear()
    if change == "copied":
        context.molecule_permissions = tuple(list(rows))
        assert context.molecule_permissions == rows and context.molecule_permissions is not rows
    elif change == "foreign_holder":
        context.molecule_permissions = ((NS(), rows[0][1]), *rows[1:])
    elif change == "extra_field":
        context.molecule_permissions = ((rows[0][0], rows[0][1] | {"unowned"}), *rows[1:])
    elif change == "mutable_field":
        context.molecule_permissions = ((rows[0][0], set(rows[0][1])), *rows[1:])
    elif change == "missing":
        context.molecule_permissions = rows[:-1]
    if change == "unchanged":
        assert check(context)[3] is rows
        assert calls == ["permissions", "active"]
    else:
        with pytest.raises(ValueError, match="permission association"):
            check(context)
        assert calls == ["permissions"]


@pytest.mark.parametrize("count", (65, 500, 512))
def test_init_terminal_full_capacity_preserves_configured_count_and_short_history_bound(count):
    assert stage.MAX_ITERATIONS == 512 and prefix.MAX_ITERATIONS == 64
    assert stage._configured_count(count, 512) is count
    assert stage.source_plan()["max_iterations"] == 512
    with pytest.raises(ValueError):
        prefix._count(count)
    request = stage.Request(object(), "parent", "source", stage.SELECTION, "mode", count, 512, "id")
    record = stage.request_record(request)
    assert record["iterations"] == count and record["maximum"] == 512
    assert not stage._REQUESTS and not stage._ISSUED


@pytest.mark.parametrize("count,maximum", ((500, 64), (500, 499), (513, 512), (512, 513)))
def test_init_terminal_full_capacity_refuses_oversize_without_truncating(count, maximum):
    with pytest.raises(ValueError):
        stage._configured_count(count, maximum)
    assert not stage._REQUESTS and not stage._CONSUMED and not stage._ISSUED


@pytest.mark.parametrize("count", (500, 512))
def test_init_terminal_full_capacity_timeline_retains_every_label_and_record(count):
    ledger = stage._Timeline(count)
    labels = tuple(float(i * i) / 7 for i in range(count))
    rows = []
    for ordinal, label in enumerate(labels):
        sampled = ordinal % 19 == 0
        ledger.begin(label, sampled)
        row = stage.Iteration(ordinal, label, sampled, NS(identity=str(ordinal)), ordinal, 0, None)
        rows.append(row)
        ledger.end(row)
    assert ledger.completed == count and ledger.current is None
    assert all(actual is expected for actual, expected in zip(ledger.records, rows, strict=True))
    assert all(row.source_time is label for row, label in zip(rows, labels, strict=True))
    assert ledger.token()[0] == count
    with pytest.raises(ValueError):
        ledger.begin(labels[-1], False)
    assert ledger.invalid and ledger.completed == count


def test_init_terminal_full_capacity_installed_hooks_exhaust_all_500_original_labels(tmp_path):
    # The synthetic source retains its whole nonsliceable calendar. No native
    # equation, claimant, original RNG, owner or configured-time mutation runs.
    h = _loop_model(tmp_path, count=500)
    h.context.request.maximum = 512
    required = sys.getprofile(), sys.gettrace()
    h.drive()
    assert len(h.phase.bodies) == 500 and h.phase.bodies == list(h.calendar.labels)
    assert h.calendar.next_calls == h.context.loop_visits == 501
    assert h.context.timeline.completed == 500 and h.context.timeline.current is None
    assert h.context.loop_returned and h.phase.post_loop is True
    assert not h.context.selected_stopped and not h.context.stopping
    assert h.context.time_steps is h.calendar and h.context.calendar_raw[0] is h.calendar
    assert [(kind, ordinal) for kind, ordinal, _, _ in h.provider_calls] == [
        (kind, ordinal) for ordinal in range(500) for kind in ("begin", "end")
    ]
    assert all(frame is h.context.loop_frame for _, _, _, frame in h.provider_calls)
    assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
    assert not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "full-calendar-capacity.json",
        dict(
            configured_iterations=500,
            maximum=512,
            completed=500,
            iterator_advances=501,
            all_original_synthetic_labels=True,
            source_calendar_shortened=False,
            original_time_input_mutation=False,
            native_or_owner_execution=False,
        ),
    )


def _retention_context():
    columns = stage.WeakValueDictionary()
    return NS(
        retained_columns=columns,
        retained_columns_record=columns,
        retention_work=[],
        last_retention_raw=None,
    )


def test_init_terminal_retention_500_real_625_caches_share_immutable_storage_only(tmp_path):
    from cells.processes import betse_native_single_cell_poisson_observation as observation

    # Declared synthetic observation data: no operator/native INIT derivation.
    live = np.zeros((625, 625), dtype=np.float64)
    scope, context, snapshots = observation.Scope((live,)), _retention_context(), []
    for ordinal in range(500):
        fresh = scope.snapshot(dict(ordinal=ordinal, inverse=live))
        saved = stage._retain_snapshot(context, fresh)
        assert saved.identity == fresh.identity and saved.descriptor_json == fresh.descriptor_json
        assert saved is not fresh and saved.columns is not fresh.columns
        snapshots.append(saved)
    columns = [s.columns[0].values for s in snapshots]
    assert len({id(column) for column in columns}) == 500
    assert all(stage._column_bytes(column) is stage._column_bytes(columns[0]) for column in columns)
    assert len({s.identity for s in snapshots}) == 500
    assert len(context.retention_work) == 500
    assert sum(row[2] for row in context.retention_work) == live.nbytes == 3125000
    assert sum(row[3] for row in context.retention_work) == live.nbytes * 499
    assert len(context.retained_columns) == 1
    assert context.last_retention_raw.columns[0].values is not columns[0]
    assert len(stage._column_bytes(columns[0])) == 3125000
    assert len(stage._column_bytes(context.last_retention_raw.columns[0].values)) == 3125000
    stage.retained_cache.validate(snapshots[0])
    stage.retained_cache.validate(snapshots[-1])
    assert not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "retained-cache-capacity.json",
        dict(
            fresh_complete_snapshots=500,
            full_shaped_columns_retained=500,
            unique_retained_column_bytes=3125000,
            last_raw_fresh_column_bytes=3125000,
            without_sharing_column_bytes=1562500000,
            descriptor_bytes=sum(len(s.descriptor_json.encode()) for s in snapshots),
            storage_shared_not_native_alias_or_operator_authority=True,
            native_or_RNG_or_scientific_entries=0,
        ),
    )


@pytest.mark.parametrize(
    "mutation", ("value", "signed_zero", "nan_payload", "dtype", "shape", "stride")
)
def test_init_terminal_retention_changed_live_bits_or_layout_stay_separate(mutation):
    context = _retention_context()
    live = np.asarray([[0.0, 1.0], [2.0, 3.0]], dtype=np.float64)
    if mutation == "nan_payload":
        live.view(np.uint64)[0, 0] = 0x7FF8000000000001
    first = stage._retain_snapshot(context, stage.retained_cache.snapshot(live))
    original_bytes = stage._column_bytes(first.columns[0].values)
    if mutation == "value":
        live[0, 0] = 11.0
    elif mutation == "signed_zero":
        live[0, 0] = -0.0
    elif mutation == "nan_payload":
        live.view(np.uint64)[0, 0] = 0xFFF8000000000002
    elif mutation == "dtype":
        live = live.astype(np.float32)
    elif mutation == "shape":
        live = live.reshape(4)
    else:
        live = live.T
    fresh = stage.retained_cache.snapshot(live)
    second = stage._retain_snapshot(context, fresh)
    assert second.columns[0].values is not first.columns[0].values
    assert second.identity == fresh.identity and second.descriptor_json == fresh.descriptor_json
    assert stage._column_bytes(first.columns[0].values) == original_bytes
    stage.retained_cache.validate(first)
    stage.retained_cache.validate(second)


def test_init_terminal_retention_source_layout_and_distinct_live_roots_remain_separate_evidence():
    context = _retention_context()
    live = np.asarray([[1.0, 2.0], [3.0, 4.0]])
    other = np.asfortranarray(live)
    assert other is not live and other.base is not live
    a = stage.retained_cache.snapshot(dict(first=live, second=other))
    b = stage._retain_snapshot(context, a)
    assert b.descriptor_json == a.descriptor_json and b.identity == a.identity
    assert b.columns[0].values is not b.columns[1].values
    assert stage._column_bytes(b.columns[0].values) is stage._column_bytes(b.columns[1].values)
    assert a.columns[0].values is not a.columns[1].values
    assert (
        b.descriptor["items"][0][1]["source_layout"] != b.descriptor["items"][1][1]["source_layout"]
    )
    assert live.flags.writeable and other.flags.writeable
    assert not b.columns[0].values.flags.writeable
    with pytest.raises(ValueError):
        b.columns[0].values.flags.writeable = True


def test_init_terminal_retention_equal_raw_bits_with_distinct_dtype_or_shape_do_not_conflate():
    context = _retention_context()
    arrays = (
        np.zeros((2, 2), dtype=np.float64),
        np.zeros((2, 2), dtype=np.int64),
        np.zeros(4, dtype=np.float64),
    )
    caches = [stage._retain_snapshot(context, stage.retained_cache.snapshot(a)) for a in arrays]
    assert all(stage._column_bytes(c.columns[0].values) == bytes(32) for c in caches)
    assert len({id(c.columns[0].values) for c in caches}) == 3


def test_init_terminal_retention_weak_pool_does_not_keep_unretained_history_alive():
    context = _retention_context()
    saved = stage._retain_snapshot(context, stage.retained_cache.snapshot(np.zeros(4)))
    assert len(context.retained_columns) == 1
    context.last_retention_raw = None
    del saved
    gc.collect()
    assert len(context.retained_columns) == 0
    assert len(context.retention_work) == 1 and type(context.retention_work[0][0]) is str


def test_init_terminal_retention_shared_bytes_do_not_share_mutable_ndarray_headers():
    context = _retention_context()
    a = stage._retain_snapshot(context, stage.retained_cache.snapshot(np.zeros((2, 2))))
    b = stage._retain_snapshot(context, stage.retained_cache.snapshot(np.zeros((2, 2))))
    assert stage._column_bytes(a.columns[0].values) is stage._column_bytes(b.columns[0].values)
    b.columns[0].values.shape = (4,)
    assert a.columns[0].values.shape == (2, 2)
    stage.retained_cache.validate(a)
    with pytest.raises(ValueError):
        stage.retained_cache.validate(b)


@pytest.mark.parametrize(
    "kind", ("own_array", "bytearray_view", "shifted_bytes", "foreign_column", "foreign_cache")
)
def test_init_terminal_retention_refuses_mutable_or_unsupported_storage_before_sharing(kind):
    context = _retention_context()
    fresh = stage.retained_cache.snapshot(np.zeros(3))
    entered = []

    class Foreign:
        def __getattribute__(self, name):
            entered.append(name)
            raise AssertionError("No foreign evidence callback")

    if kind == "foreign_cache":
        fresh = Foreign()
    elif kind == "foreign_column":
        fresh = replace(fresh, columns=(Foreign(),))
    else:
        if kind == "own_array":
            value = np.zeros(3)
        elif kind == "bytearray_view":
            value = np.frombuffer(bytearray(24), dtype=np.float64)
        else:
            value = np.frombuffer(bytes(32), dtype=np.float64, offset=8)
        value.flags.writeable = False
        fresh = replace(fresh, columns=(stage.retained_cache.CacheColumn("column_00000", value),))
    with pytest.raises(ValueError):
        stage._retain_snapshot(context, fresh)
    assert context.last_retention_raw is fresh
    assert len(context.retained_columns) == 0 and context.retention_work == [] and entered == []


@pytest.mark.parametrize("kind", ("pool_identity", "stored_shape", "mutable_backing"))
def test_init_terminal_retention_pool_or_previous_column_drift_refuses(kind):
    context = _retention_context()
    first = stage._retain_snapshot(context, stage.retained_cache.snapshot(np.zeros((2, 2))))
    key = next(iter(context.retained_columns))
    if kind == "pool_identity":
        context.retained_columns = stage.WeakValueDictionary()
    elif kind == "stored_shape":
        first.columns[0].values.shape = (4,)
    else:
        foreign = np.zeros((2, 2))
        foreign.flags.writeable = False
        context.retained_columns[key] = foreign
    fresh = stage.retained_cache.snapshot(np.zeros((2, 2)))
    with pytest.raises(ValueError):
        stage._retain_snapshot(context, fresh)
    assert context.last_retention_raw is fresh and len(context.retention_work) == 1


def test_init_terminal_retention_only_wraps_retained_snapshots_never_live_validation():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "_retain_snapshot" not in ast.unparse(functions["_snapshot"])
    assert "snapshot(tuple(values))" in ast.unparse(functions["_snapshot"])
    assert ast.unparse(functions["_end"]).index(
        "context.runtime['_snapshot'](context)"
    ) < ast.unparse(functions["_end"]).index("_diagnostics(context)")
    calls = [
        n
        for n in ast.walk(functions["prepare"])
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "_retain_snapshot"
    ]
    assert len(calls) == 3
    assert "frames" not in ast.unparse(functions["_retain_snapshot"])
    assert "raw_returns" not in ast.unparse(functions["_retain_snapshot"])
