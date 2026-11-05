"""Blocked natural-terminal metadata; no parent or source state manufactured."""

import ast
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_terminal_molecules as stage
from tests.unit import test_betse_native_init_molecule_short_runtime as inherited
from validation.betse import betse_native_init_terminal_molecules_software as runner


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    original = inherited.inherited.inherited.inherited.inherited._blocked_generator
    generator = FunctionType(
        original.__code__,
        dict(original.__globals__, stage=NS(_ACTIVE=[], _FAILED=[]), runner=runner),
    )(request, tmp_path, monkeypatch)
    before, entered, primary = (sys.getprofile(), sys.gettrace()), False, None
    try:
        next(generator)
        entered = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        drain = inherited.inherited.inherited.inherited.inherited.cleanup._drain_guard
        FunctionType(
            drain.__code__, dict(drain.__globals__, _write_failure_diagnostics=lambda *a: None)
        )(generator, entered, (), tmp_path, required_hooks=before, primary=primary)


@pytest.mark.parametrize(
    "count,maximum", ((0, 3), (-1, 3), (True, 3), (1.0, 3), (4, 3), (65, 64), (3, True), (1, 513))
)
def test_full_calendar_declared_bound_is_exact_and_cannot_shrink_or_promote_parent(count, maximum):
    with pytest.raises(ValueError):
        stage._FullCalendar(count, maximum)
    assert not stage._RUNTIME and not stage._BOUND


def test_unadopted_terminal_refuses_before_foreign_parent_access():
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No owner access before explicit source/ancestor adoption")

    value = Foreign()
    with pytest.raises(stage.TerminalRuntimeRejected) as caught:
        stage.bind_terminal(
            value, completion=value, storage=value, electrical=value, child=value, maximum=3
        )
    assert caught.value.stage == "held" and not stage._RUNTIME


@pytest.mark.parametrize(
    "name",
    (
        "session_of",
        "session_provider",
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "validate_runtime",
        "validate_runtime_active",
    ),
)
def test_old_claim_or_saved_dictionary_never_becomes_terminal_authority(name):
    function = vars(stage)[name]
    with pytest.raises(stage.TerminalRuntimeRejected) as caught:
        if name in ("runtime_members", "runtime_codes", "runtime_permissions"):
            function({})
        else:
            function({}, child={})
    assert caught.value.stage == "claim"


def _ledger(count=3):
    value = stage._FullCalendar(count, count)
    calendar = tuple(float(n) for n in range(count))
    sampled = {calendar[-1]}
    solver = object()
    raw = (calendar, sampled, solver)
    value.bind_calendar(raw, calendar=calendar, sampled=sampled, solver_context=solver)
    frame = object()
    for ordinal, label in enumerate(calendar):
        sampled = label in value.sampled
        value.iterations.begin(
            ordinal, label, (float, stage.struct.pack("!d", label)), frame, sampled, (0, 0, 0)
        )
        value.iterations.end(
            stage.IterationEvidence(ordinal, label, frame, sampled, (), (), (), (), "metadata-only")
        )
    return value


def test_natural_terminal_metadata_keeps_full_original_labels_and_distinct_context_end():
    value = _ledger()
    loop, context = object(), object()
    with pytest.raises(ValueError, match="Incomplete"):
        value.complete()
    value.natural_loop_end(loop, None, normal=True, selected_stop=False)
    with pytest.raises(ValueError, match="Incomplete"):
        value.complete()
    value.normal_context_end(context, None, normal=True, exception_arguments=(None, None, None))
    assert value.complete() is value
    assert value.loop_return == (loop, None) and value.context_return == (context, None)
    assert len(value.iterations.records) == value.configured_count == 3
    assert not stage._RUNTIME and not stage._BOUND


@pytest.mark.parametrize(
    "drift",
    (
        "selected",
        "abnormal",
        "missing_iteration",
        "active_iteration",
        "duplicate",
        "context_first",
        "context_error",
        "context_duplicate",
        "calendar_copy",
        "short_calendar",
    ),
)
def test_natural_terminal_refuses_prefix_incomplete_and_out_of_order_protocol(drift):
    value = _ledger()
    if drift in ("calendar_copy", "short_calendar"):
        value = stage._FullCalendar(3, 3)
        calendar = (0.0, 1.0, 2.0)
        actual = tuple(list(calendar)) if drift == "calendar_copy" else (0.0, 1.0)
        sampled, context = {2.0}, object()
        with pytest.raises(ValueError):
            value.bind_calendar(
                (actual, sampled, context),
                calendar=calendar,
                sampled=sampled,
                solver_context=context,
            )
    elif drift in ("context_first", "context_error", "context_duplicate"):
        if drift != "context_first":
            value.natural_loop_end(object(), None, normal=True, selected_stop=False)
        if drift == "context_duplicate":
            value.normal_context_end(
                object(), None, normal=True, exception_arguments=(None, None, None)
            )
        arguments = (ValueError, None, None) if drift == "context_error" else (None, None, None)
        with pytest.raises(ValueError):
            value.normal_context_end(object(), None, normal=True, exception_arguments=arguments)
    else:
        if drift == "missing_iteration":
            value.iterations.records.pop()
        elif drift == "active_iteration":
            value.iterations.current = (3, object())
        elif drift == "duplicate":
            value.natural_loop_end(object(), None, normal=True, selected_stop=False)
        with pytest.raises(ValueError):
            value.natural_loop_end(
                object(), None, normal=drift != "abnormal", selected_stop=drift == "selected"
            )
    assert value.invalid
    with pytest.raises(ValueError):
        value.complete()


def test_new_runtime_has_real_local_public_source_functions_and_no_numerical_copy():
    names = (
        "bind_terminal",
        "begin_iteration",
        "finish_iteration",
        "finish_runtime",
        "validate_iteration",
        "validate_runtime",
        "validate_runtime_active",
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "observes_runtime_frame",
        "runtime_wrapper_guard",
        "runtime_dispatch",
        "observe_runtime",
        "session_of",
        "session_provider",
        "runtime_failed_context",
    )
    path = Path(stage.__file__)
    stage.interfaces._source_interface(stage, path.read_bytes(), path, names)
    assert stage.TerminalMoleculeRuntimeClaim is not stage.previous.ShortMoleculeRuntimeClaim
    assert stage.MAX_WORK == stage.previous.MAX_WORK
    assert stage.MAX_ITERATIONS == 512 and stage.previous.MAX_ITERATIONS == 64
    for name, body in stage._BODIES.items():
        assert body.__code__ is vars(stage.base)[name].__code__
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name in ("run_loop", "update_intra", "update_V")
        for node in ast.parse(path.read_bytes()).body
    )


def test_metadata_provider_dependency_proof_does_not_enter_a_native_body():
    stage._dependency()
    assert stage.BASE_INTERFACE_SHA256 is stage.CONSUMER_INTERFACE_SHA256 is None


@pytest.mark.parametrize("mode", ("ordinary", "falsey", "cause", "handled_normal"))
def test_actual_installed_observer_preserves_unwind_and_refuses_handled_double_fault(
    monkeypatch, mode
):
    original = inherited.test_installed_trace_keeps_exact_unwind_before_return_delegate_audit
    FunctionType(original.__code__, dict(original.__globals__, stage=stage))(monkeypatch, mode)


@pytest.mark.parametrize("mode", ("normal", "selected", "source_error", "context_error"))
def test_actual_profile_separates_natural_loop_and_solver_context_with_primary_retention(mode):
    from cells.processes import betse_native_init_retained_world as normality

    class SelectedStop(BaseException):
        pass

    primary = SelectedStop("selected") if mode == "selected" else ValueError("actual toy source")
    cause = KeyError("original toy cause")
    primary.__cause__ = cause
    value = stage._FullCalendar(3, 3)
    calendar = (0.0, 1.0, 2.0)
    captures, events = [], []

    class Scope:
        def __enter__(self):
            return self

        def __exit__(self, typ, error, traceback):
            if mode == "context_error":
                raise primary
            return False

    solver = Scope()
    sampled_labels = {2.0}
    value.bind_calendar(
        (calendar, sampled_labels, solver),
        calendar=calendar,
        sampled=sampled_labels,
        solver_context=solver,
    )

    def loop():
        frame = sys._getframe()
        for ordinal, label in enumerate(calendar):
            sampled = label in value.sampled
            value.iterations.begin(
                ordinal, label, (float, stage.struct.pack("!d", label)), frame, sampled, (0, 0, 0)
            )
            if mode == "source_error" and ordinal == 1:
                raise primary
            value.iterations.end(
                stage.IterationEvidence(
                    ordinal, label, frame, sampled, (), (), (), (), "toy-metadata"
                )
            )
        if mode == "selected":
            raise primary

    before = sys.getprofile(), sys.gettrace()

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if event != "return":
            return
        if frame.f_code is loop.__code__:
            events.append(("loop", normality._normal_return(frame)))
            try:
                value.natural_loop_end(
                    frame,
                    arg,
                    normal=normality._normal_return(frame),
                    selected_stop=mode == "selected",
                )
            except BaseException as error:
                captures.append(error)
        elif frame.f_code is Scope.__exit__.__code__:
            events.append(("context", normality._normal_return(frame)))
            try:
                value.normal_context_end(
                    frame,
                    arg,
                    normal=normality._normal_return(frame),
                    exception_arguments=(
                        frame.f_locals["typ"],
                        frame.f_locals["error"],
                        frame.f_locals["traceback"],
                    ),
                )
            except BaseException as error:
                captures.append(error)

    try:
        sys.setprofile(profile)
        if mode == "normal":
            with solver:
                loop()
            assert value.complete() is value and not captures
        else:
            with pytest.raises(type(primary)) as caught:
                with solver:
                    loop()
            assert caught.value is primary and primary.__cause__ is cause
            assert captures and value.invalid
            with pytest.raises(ValueError):
                value.complete()
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    assert [name for name, _ in events] == ["loop", "context"]
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]


@pytest.mark.parametrize("recovery_fails", (False, True))
def test_public_terminal_closure_failure_is_irreversible_with_raw_primary(
    monkeypatch, recovery_fails
):
    class FalseyError(ValueError):
        def __bool__(self):
            return False

    primary, cause = FalseyError("closure primary"), KeyError("source cause")
    primary.__cause__ = cause
    claim = object.__new__(stage.TerminalMoleculeRuntimeClaim)
    runtime = NS(
        invalid=False,
        primary=None,
        primary_origin=None,
        capture_error=None,
        capture_errors=(),
        last_raw=(object(), None),
        record=None,
    )
    monkeypatch.setitem(stage._RUNTIME, claim, runtime)

    def failed(*args, **kwargs):
        raise primary

    monkeypatch.setattr(stage, "_finish_runtime", failed)
    if recovery_fails:

        class RefusedList(list):
            def append(self, value):
                raise OSError("recovery append")

        monkeypatch.setattr(stage, "_FAILED", RefusedList())
    else:
        monkeypatch.setattr(stage, "_FAILED", [])
    with pytest.raises(FalseyError) as caught:
        stage.finish_runtime(claim, child=object())
    assert caught.value is runtime.primary is primary and primary.__cause__ is cause
    assert runtime.invalid and runtime.record is None
    assert primary.molecule_terminal_partial is runtime
    before = tuple(stage._FAILED)
    with pytest.raises(FalseyError) as second:
        stage.finish_runtime(claim, child=object())
    assert second.value is primary and tuple(stage._FAILED) == before
    if recovery_fails:
        assert isinstance(runtime.capture_error, OSError)


@pytest.mark.parametrize("drift", ("lookup", "limit", "body", "class_method", "cached"))
def test_dependency_proof_binds_effective_metadata_lookups_and_local_class_bodies(
    monkeypatch, drift
):
    stage._dependency()
    if drift == "lookup":

        def foreign(*args):
            pytest.fail("Foreign builtin lookup must never execute")

        monkeypatch.setattr(stage, "type", foreign, raising=False)
    elif drift == "limit":
        monkeypatch.setattr(stage, "MAX_WORK", stage.MAX_WORK + 1)
    elif drift == "class_method":

        def foreign(self):
            pytest.fail("Changed ledger body must never execute")

        monkeypatch.setattr(stage._FullCalendar, "complete", foreign)
    elif drift == "cached":
        original = stage.source_plan
        copied = dict(vars(stage), __builtins__=dict(original.__builtins__))
        foreign = FunctionType(original.__code__, copied)
        # Restoring the globals' provider does not replace FunctionType's cache.
        copied["__builtins__"] = original.__builtins__
        monkeypatch.setattr(stage, "source_plan", foreign)
    else:

        def foreign():
            pytest.fail("Changed body must never execute")

        monkeypatch.setattr(stage, "source_plan", foreign)
    with pytest.raises((ValueError, stage.TerminalRuntimeRejected)):
        stage._dependency()


@dataclass(frozen=True)
class _ToyStatus:
    child: object
    calendar_raw: tuple
    loop_frame: object
    context_frame: object
    loop_raw: tuple
    context_raw: tuple
    selected_stop: bool = False
    before_native_pickle: bool = True
    exception_arguments: tuple = (None, None, None)


def _toy_closure(monkeypatch, *, context_error=False):
    """Exercise real closure checks with a patched metadata route, never a parent.

    No bind_terminal/ancestor/native work occurs. In particular these plain toy
    objects cannot pass _route or the held source gate in production.
    """
    import numpy

    from cells.processes import betse_native_init_dynamics_completion as metadata
    from cells.processes import betse_native_init_retained_world as normality

    full = stage._FullCalendar(3, 3)
    calendar, sampled, sim, phase = (0.0, 1.0, 2.0), {2.0}, object(), object()

    class Scope:
        def __enter__(self):
            return self

        def __exit__(self, typ, value, traceback):
            return sys._getframe()

    def loop(self, phase, time_steps, time_steps_sampled):
        return sys._getframe()

    solver = Scope()
    loop_frame = loop(sim, phase, calendar, sampled)
    context_frame = solver.__exit__(ValueError if context_error else None, None, None)
    raw = calendar, sampled, solver
    full.bind_calendar(raw, calendar=calendar, sampled=sampled, solver_context=solver)
    loop_raw, context_raw = (loop_frame, loop_frame), (context_frame, context_frame)
    child = NS(
        observing=False,
        primary=None,
        capture_error=None,
        calendar_raw=raw,
        time_steps=calendar,
        sampled=sampled,
        solver_context=solver,
        loop_frame=loop_frame,
        loop_code=loop.__code__,
        noop_methods=(Scope.__enter__, Scope.__exit__),
        raw_returns=[loop_raw, context_raw],
        frames={
            id(frame): dict(
                frame=frame,
                code=frame.f_code,
                globals=frame.f_globals,
                name=role,
                returned=True,
                suspended=False,
            )
            for role, frame in (
                ("_run_sim_core_loop", loop_frame),
                ("solver_context_exit", context_frame),
            )
        },
    )
    status = child.terminal_status = _ToyStatus(
        child, raw, loop_frame, context_frame, loop_raw, context_raw
    )
    for ordinal, label in enumerate(calendar):
        selected = label in sampled
        full.iterations.begin(
            ordinal,
            label,
            (float, stage.struct.pack("!d", label)),
            loop_frame,
            selected,
            (0, 0, 0),
        )
        row = stage.IterationEvidence(ordinal, label, loop_frame, selected, (), (), (), (), "")
        full.iterations.end(replace(row, identity=metadata._digest(stage._iteration_data(row))))
    claim = object.__new__(stage.TerminalMoleculeRuntimeClaim)
    runtime = NS(
        claim=claim,
        child=child,
        original=NS(session=object(), sim=sim, phase=phase, initial=normality, api=metadata),
        completion=NS(numpy=numpy),
        kind=stage.OBSERVER_MODE,
        full=full,
        ledger=full.iterations,
        active=True,
        invalid=False,
        primary=None,
        primary_origin=None,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        work=[],
        c_calls=[],
        raw_returns=[],
        source_exceptions=[],
        top_calls=[],
        last_raw=None,
        terminal_status=None,
        record=None,
    )
    consumer = ModuleType("toy_terminal_metadata_consumer")
    consumer.NaturalTerminalStatus = _ToyStatus
    consumer._terminal_runtime_status = lambda value: value.terminal_status
    consumer.runtime_api = stage

    def prepare(claim, context):
        return runtime_api.finish_runtime(claim, child=context)  # noqa: F821

    consumer.prepare = FunctionType(prepare.__code__, vars(consumer))
    monkeypatch.setattr(stage, "_ready", lambda: consumer)
    monkeypatch.setattr(
        stage, "_runtime_context", lambda supplied: runtime if supplied is claim else None
    )
    monkeypatch.setattr(stage, "_FAILED", [])
    monkeypatch.setitem(stage._RUNTIME, claim, runtime)
    return runtime, consumer, status


def test_actual_closure_body_and_reader_preserve_complete_metadata_records_without_parent(
    monkeypatch,
):
    runtime, consumer, status = _toy_closure(monkeypatch)
    record = consumer.prepare(runtime.claim, runtime.child)
    assert record is runtime.record and not runtime.active and not runtime.invalid
    assert stage.validate_runtime(runtime.claim, child=runtime.child) is record
    assert runtime.terminal_status is status
    assert record.records == tuple(runtime.ledger.records)
    assert record.calendar is runtime.full.calendar
    assert record.loop_return[0] is status.loop_frame
    assert record.context_return[0] is status.context_frame
    assert record.selected_stop is False and record.natural_loop_returned is True
    assert record.before_native_pickle is True
    assert not stage._BOUND  # The patched test route never issues native ancestry.


@pytest.mark.parametrize(
    "drift",
    (
        "calendar",
        "sampled",
        "context",
        "selected",
        "pickle",
        "raw_shape",
        "raw_copy",
        "role",
        "unfinished",
        "suspended",
        "source_code",
        "context_arguments",
        "actual_context_error",
        "missing_iteration",
    ),
)
def test_closure_refuses_actual_return_calendar_and_completion_drift_before_publishing(
    monkeypatch, drift
):
    runtime, consumer, status = _toy_closure(
        monkeypatch, context_error=drift == "actual_context_error"
    )
    child = runtime.child
    if drift == "calendar":
        child.time_steps = tuple(list(child.time_steps))
    elif drift == "sampled":
        child.sampled = set(child.sampled)
    elif drift == "context":
        child.solver_context = object()
    elif drift in ("selected", "pickle", "raw_shape", "context_arguments"):
        changes = {
            "selected": dict(selected_stop=True),
            "pickle": dict(before_native_pickle=False),
            "raw_shape": dict(loop_raw=[*status.loop_raw]),
            "context_arguments": dict(exception_arguments=(ValueError, None, None)),
        }
        child.terminal_status = replace(status, **changes[drift])
    elif drift == "raw_copy":
        child.raw_returns[0] = tuple(list(status.loop_raw))
    elif drift == "role":
        child.frames[id(status.context_frame)]["name"] = "unrelated_return"
    elif drift == "unfinished":
        child.frames[id(status.loop_frame)]["returned"] = False
    elif drift == "suspended":
        child.frames[id(status.context_frame)]["suspended"] = True
    elif drift == "source_code":
        child.loop_code = stage.source_plan.__code__
    elif drift == "missing_iteration":
        runtime.ledger.records.pop()
    with pytest.raises((ValueError, stage.MoleculeNetworkRejected)) as caught:
        consumer.prepare(runtime.claim, child)
    assert runtime.invalid and runtime.record is None and runtime.primary is caught.value
    assert caught.value.molecule_terminal_partial is runtime
    assert stage._FAILED == [runtime] and not stage._BOUND


@pytest.mark.parametrize("drift", ("status", "return", "record", "active"))
def test_closed_metadata_reader_rejects_replaced_evidence_and_epoch(monkeypatch, drift):
    runtime, consumer, status = _toy_closure(monkeypatch)
    record = consumer.prepare(runtime.claim, runtime.child)
    if drift == "status":
        runtime.child.terminal_status = replace(status)
    elif drift == "return":
        runtime.child.raw_returns.remove(status.context_raw)
    elif drift == "record":
        runtime.record = replace(record, loop_return=tuple(list(record.loop_return)))
    else:
        runtime.active = True
    with pytest.raises(stage.MoleculeNetworkRejected):
        stage.validate_runtime(runtime.claim, child=runtime.child)
    assert runtime.invalid and not stage._BOUND


def test_unclosed_metadata_reader_refuses_before_obtaining_a_terminal_status(monkeypatch):
    runtime, consumer, _ = _toy_closure(monkeypatch)

    def forbidden(value):
        pytest.fail("An active/unclosed runtime cannot request final source status")

    consumer._terminal_runtime_status = forbidden
    with pytest.raises(stage.MoleculeNetworkRejected):
        stage.validate_runtime(runtime.claim, child=runtime.child)
    assert runtime.invalid and runtime.record is None and runtime.active


@pytest.mark.parametrize("drift", ("count_body", "ledger_body", "ledger_class"))
def test_previous_bound_and_ledger_are_actual_reused_bodies_without_calling_foreign_code(
    monkeypatch, drift
):
    stage._dependency()

    def forbidden(*args):
        pytest.fail("Unreviewed metadata body must be refused before execution")

    if drift == "count_body":
        monkeypatch.setattr(stage.previous._count, "__code__", forbidden.__code__)
    elif drift == "ledger_body":
        monkeypatch.setattr(stage.previous._Iterations.end, "__code__", forbidden.__code__)
    else:

        class Foreign:
            __init__ = forbidden

        monkeypatch.setattr(stage.previous, "_Iterations", Foreign)
    with pytest.raises((ValueError, stage.TerminalRuntimeRejected)):
        stage._dependency()


@pytest.mark.parametrize("drift", ("records", "keys", "active", "bound", "invalid"))
def test_complete_metadata_rechecks_closed_iteration_ledger_after_natural_returns(drift):
    value = _ledger()
    value.natural_loop_end(object(), None, normal=True, selected_stop=False)
    value.normal_context_end(object(), None, normal=True, exception_arguments=(None, None, None))
    assert value.complete() is value
    if drift == "records":
        value.iterations.records.pop()
    elif drift == "keys":
        value.iterations.keys.pop()
    elif drift == "active":
        value.iterations.current = (3, object())
    elif drift == "bound":
        value.iterations.bound += 1
    else:
        value.iterations.invalid = True
    with pytest.raises(ValueError, match="Incomplete"):
        value.complete()


@pytest.mark.parametrize("count", (500, 512))
def test_separate_terminal_domain_keeps_every_configured_metadata_record(count):
    value = _ledger(count)
    assert type(value.iterations) is stage._TerminalIterations
    assert value.iterations is not stage.previous._Iterations
    assert value.configured_count == len(value.calendar) == len(value.iterations.records) == count
    assert [row.ordinal for row in value.iterations.records] == list(range(count))
    value.natural_loop_end(object(), None, normal=True, selected_stop=False)
    value.normal_context_end(object(), None, normal=True, exception_arguments=(None, None, None))
    assert value.complete() is value
    assert stage.previous.MAX_ITERATIONS == 64
    with pytest.raises(ValueError):
        stage.previous._count(65)
    assert not stage._RUNTIME and not stage._BOUND


def test_terminal_513_refuses_without_changing_short_bound_or_work_budget():
    assert stage.MAX_ITERATIONS == 512 and stage.previous.MAX_ITERATIONS == 64
    assert stage.MAX_WORK == stage.previous.MAX_WORK == 100000
    with pytest.raises(ValueError):
        stage._FullCalendar(513, 513)
    with pytest.raises(ValueError):
        stage._FullCalendar(513, 512)


def test_terminal_inherited_pairing_cannot_be_overridden_without_source_refusal(monkeypatch):
    def forbidden(*args):
        pytest.fail("Foreign pairing body must never execute")

    monkeypatch.setattr(stage._TerminalIterations, "begin", forbidden)
    with pytest.raises(stage.TerminalRuntimeRejected):
        stage._dependency()
