"""Private protocol/metadata controls only; no issued parent/native body."""

import ast
import dis
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_molecule_short_runtime as runtime_provider
from cells.processes import betse_native_init_short_history as stage
from tests.unit import test_betse_native_init_first_step as interpreter_model
from tests.unit import test_betse_native_init_retained_world as guard_model
from tests.unit import test_betse_native_init_short_history_diagnostics as diagnostic_controls
from validation.betse import betse_native_init_short_history_software as software


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
    class FalseyError(ValueError):
        def __bool__(self):
            return False

    primary = FalseyError("primary") if mode == "falsey_error" else ValueError("primary")
    cause = KeyError("original cause")
    primary.__cause__ = cause
    parent, foreign, calls = object(), object(), []
    context = NS(
        claimed=True,
        setup_frame=None,
        loop_frame=None,
        work=[],
        bindings=object(),
        before=object(),
        stable=object(),
        stable_graph=object(),
        electrical_parent=parent,
    )

    def check(actual):
        calls.append(("check", actual))
        if mode in ("parent_error", "falsey_error"):
            raise primary
        return foreign if mode == "wrong_return" else parent

    binding = NS(check=check)

    def guard(actual):
        calls.append(("guard", actual))
        if mode == "before_guard" or mode == "after_guard" and len(calls) == 3:
            raise primary

    monkeypatch.setattr(stage, "_parent", guard)
    if mode in ("setup", "loop"):
        setattr(context, mode + "_frame", object())
    elif mode == "work":
        context.work.append(dict(body_started=False))
    elif mode in ("bindings", "before", "stable", "stable_graph"):
        setattr(context, mode, None)
    elif mode == "unclaimed":
        context.claimed = False
    if mode == "valid":
        assert stage._pre_source_parent_check(context, binding) is parent
        assert [row[0] for row in calls] == ["guard", "check", "guard"]
        assert context.pre_source_parent_check_attempt is check
        assert context.pre_source_parent_check_raw is parent
    else:
        with pytest.raises(ValueError) as caught:
            stage._pre_source_parent_check(context, binding)
        if mode in ("parent_error", "falsey_error", "before_guard", "after_guard"):
            assert caught.value is primary and primary.__cause__ is cause
        if mode in (
            "setup",
            "loop",
            "work",
            "bindings",
            "before",
            "stable",
            "stable_graph",
            "unclaimed",
        ):
            assert not calls
        elif mode in ("parent_error", "falsey_error"):
            assert [row[0] for row in calls] == ["guard", "check"]
            assert context.pre_source_parent_check_attempt is check
        elif mode in ("wrong_return", "after_guard"):
            assert context.pre_source_parent_check_raw is (
                foreign if mode == "wrong_return" else parent
            )
    assert not context.work or mode == "work"


def test_pre_source_parent_check_is_after_full_alias_proof_before_source_accounting():
    from pathlib import Path

    tree = ast.parse(Path(stage.__file__).read_bytes())
    prepare = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "prepare"
    )
    calls = [node for node in ast.walk(prepare) if isinstance(node, ast.Call)]
    seals = [
        node
        for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "_pre_source_parent_check"
    ]
    assert len(seals) == 1
    account = [node for node in calls if ast.unparse(node.func) == "scope['_account']"]
    snapshots = [
        node
        for node in calls
        if ast.unparse(node.func) in ("binding.module._graph", "binding.module._snapshot")
    ]
    assert len(account) == 1 and len(snapshots) >= 2
    assert max(node.lineno for node in snapshots) < seals[0].lineno < account[0].lineno


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit immutable native-blocked software release required")
    if (
        request.node.name in software.ISSUED_CASES
        and os.environ.get(software.ISSUED_RELEASE) != "1"
    ):
        pytest.skip("Exact immutable issued-chain software envelope required before setup")
    namespace = dict(vars(guard_model), software=software, _RAW_GUARDS=[])
    fn = FunctionType(guard_model.blocked.__wrapped__.__code__, namespace)
    with contextmanager(fn)(request, tmp_path, monkeypatch):
        yield


@pytest.mark.parametrize("count", (True, False, 0, -1, 65, 1.0, "2", None))
def test_short_history_count_is_explicit_bounded_and_not_bool(count):
    with pytest.raises(ValueError):
        stage._count(count)


@pytest.mark.parametrize("count", (1, 2, 5, 64))
def test_short_history_private_timeline_is_contiguous_and_retains_each_actual_label(count):
    ledger = stage._Timeline(count)
    labels = [float(index) / 3 for index in range(count)]
    for ordinal, label in enumerate(labels):
        assert ledger.begin(label, ordinal % 2 == 0) == (ordinal, label, ordinal % 2 == 0)
        record = stage.Iteration(
            ordinal,
            label,
            ordinal % 2 == 0,
            NS(identity=str(ordinal)),
            ordinal + 1,
            ordinal + 1,
            object(),
        )
        ledger.end(record)
        assert ledger.records[-1] is record and ledger.current is None
    assert ledger.completed == count
    assert all(row.source_time is label for row, label in zip(ledger.records, labels, strict=True))
    with pytest.raises(ValueError):
        ledger.begin(99.0, False)
    assert ledger.invalid and ledger.completed == count


@pytest.mark.parametrize(
    "fault", ("reentry", "wrong_ordinal", "equal_time", "wrong_sample", "end_first")
)
def test_short_history_private_timeline_refusal_is_sticky_and_keeps_partial(fault):
    ledger = stage._Timeline(2)
    label = float("0.3141592653589793")
    if fault != "end_first":
        ledger.begin(label, True)
    if fault == "reentry":
        with pytest.raises(ValueError):
            ledger.begin(label, True)
    else:
        actual = float(str(label)) if fault == "equal_time" else label
        assert fault != "equal_time" or actual is not label
        row = stage.Iteration(
            1 if fault == "wrong_ordinal" else 0,
            actual,
            fault != "wrong_sample",
            NS(identity="partial"),
            0,
            0,
            object(),
        )
        with pytest.raises(ValueError):
            ledger.end(row)
    assert ledger.invalid and ledger.completed == 0 and ledger.records == []
    with pytest.raises(ValueError):
        ledger.begin(label, True)


def test_short_history_protocol_token_records_value_changes_not_only_same_object_refs():
    ledger = stage._Timeline(2)
    label = float("0.00125")
    ledger.begin(label, True)
    row = stage.Iteration(0, label, True, NS(identity="before"), 3, 1, object())
    ledger.end(row)
    token = ledger.token()
    row.after.identity = "after"
    assert ledger.token() != token
    assert ledger.records[0] is row


@pytest.mark.parametrize("roots", (False, True))
def test_short_history_callback_claims_are_per_iteration_and_never_clear_prior_claims(roots):
    ledger = stage._Timeline(2)
    claims = stage._CallbackClaims(ledger, roots=roots)
    item = "progressed_next" if roots else (123, "progressed_next", (17, 17, 2, 24))
    ranged = "progress_ranged" if roots else (456, "progress_ranged", (3, 3, 2, 20))
    claims.add(ranged)
    for ordinal in range(2):
        label = float(ordinal)
        ledger.begin(label, True)
        assert item not in claims
        claims.add(item)
        assert item in claims
        with pytest.raises(ValueError):
            claims.add(item)
        ledger.end(stage.Iteration(ordinal, label, True, NS(identity=str(ordinal)), 0, 0, object()))
    assert len(claims.data) == 3 and ranged in claims
    with pytest.raises(ValueError):
        claims.add(item)


@pytest.mark.parametrize("operation", ("construct", "hydrate", "phase", "trial"))
def test_short_history_owner_cannot_be_supplied_decoded_or_recycled(operation):
    owner = object.__new__(stage.ShortHistoryOwner)
    with pytest.raises((TypeError, stage.ShortHistoryRejected)):
        if operation == "construct":
            stage.ShortHistoryOwner()
        elif operation == "hydrate":
            owner.__reduce_ex__(4)
        else:
            getattr(owner, operation)


def test_short_history_missing_real_contracts_refuse_before_foreign_parent_inspection(monkeypatch):
    monkeypatch.setattr(
        stage.base.previous, "_authority", lambda value: pytest.fail("No parent entry")
    )
    with pytest.raises(stage.ShortHistoryRejected) as caught:
        stage.from_electrical(object(), iterations=2, law_id=stage.LAW_ID)
    assert caught.value.stage == "integration_held"
    assert (
        stage.PARENT_CLAIM is stage.PARENT_CHECK is stage.RUNTIME_BEGIN is stage.RUNTIME_END is None
    )
    assert not stage._CONSUMED and not stage._RETIRED


def test_short_history_release_and_bad_count_refuse_before_any_engine_or_provider(monkeypatch):
    monkeypatch.setattr(stage, "_ready", lambda: pytest.fail("No readiness entry"))
    with pytest.raises(stage.ShortHistoryRejected, match="held"):
        stage.prepare(object())
    with pytest.raises(ValueError):
        stage.from_electrical(object(), iterations=True, law_id=stage.LAW_ID)


def test_short_history_source_mode_preserves_literal_body_calendar_and_default_first_step():
    assert stage.base.SELECTION != stage.SELECTION
    plan = stage.source_plan()
    assert plan["one_fresh_parent_one_original_loop"]
    assert plan["original_calendar_dt_sampled_set_and_objects_unchanged"]
    assert plan["completed_first_step_owner_is_not_a_parent"]
    assert not plan["physical_checkpoint_full_INIT_or_scientific_admission"]
    assert plan["runtime_entry_names_unadopted"] == (None, None)
    assert software._cpu(4) == 4 and software._cpu(6) == 6
    for unavailable in (True, False, 0, 2, 4.0, "4", None):
        with pytest.raises(ValueError):
            software._cpu(unavailable)


@pytest.mark.parametrize("visits", (0, 1))
def test_short_history_observer_waits_for_real_outer_iteration_before_begin(visits, monkeypatch):
    frame = sys._getframe()
    calls = []
    context = NS(
        runtime={},
        molecule_codes=frozenset(),
        frames={id(frame): {"returned": False}},
        timeline=stage._Timeline(2),
        loop_frame=frame,
        loop_visits=visits,
        setup_frame=None,
    )
    monkeypatch.setattr(stage, "_guard", lambda value: None)
    monkeypatch.setattr(
        stage, "_begin", lambda actual, actual_frame: calls.append((actual, actual_frame))
    )
    stage._observe(context, frame, "line", None)
    assert calls == ([(context, frame)] if visits else [])


def test_short_history_private_engine_only_specializes_metadata_stop_and_owns_no_parent(tmp_path):
    registries = tuple(
        len(value) for value in (stage._REQUESTS, stage._CONSUMED, stage._RETIRED, stage._ISSUED)
    )
    scope = stage._engine(NS())
    assert scope["__name__"] == stage.__name__
    assert scope["Request"] is stage.Request and scope["prepare"] is stage.prepare
    assert scope["_dispatch"] is stage._dispatch and scope["_loop_boundary"] is stage._loop_boundary
    assert scope["_namespace"].__code__ is stage.base._namespace.__code__
    assert scope["_run"].__code__ is stage.base._run.__code__
    instructions = tuple(dis.get_instructions(scope["_dispatch_impl"]))
    assert any(item.opname == "LOAD_ATTR" and item.argval == "iterations" for item in instructions)
    assert (
        tuple(
            len(value)
            for value in (stage._REQUESTS, stage._CONSUMED, stage._RETIRED, stage._ISSUED)
        )
        == registries
    )
    software.snapshot.write_json(
        tmp_path / "engine-metadata.json",
        dict(
            source_mode=stage.SELECTION,
            dispatch_reads_declared_iterations=True,
            original_namespace_and_run_code=True,
            registry_sizes=registries,
            actual_parent_or_source_execution=False,
        ),
    )


@pytest.mark.parametrize("drift", ("guard_code", "snapshot_defaults", "account_body"))
def test_short_history_engine_refuses_reused_live_metadata_drift_before_any_delegate(
    drift, monkeypatch, tmp_path
):
    def foreign(context):
        raise AssertionError("Foreign source engine must never run")

    if drift == "guard_code":
        monkeypatch.setattr(stage.base._guard, "__code__", foreign.__code__)
    elif drift == "snapshot_defaults":
        monkeypatch.setattr(stage.base._snapshot, "__kwdefaults__", {"stable": True})
    else:
        monkeypatch.setattr(stage.base._account.__wrapped__, "__code__", foreign.__code__)
    with pytest.raises(ValueError) as caught:
        stage._engine(NS())
    assert not stage._CONSUMED and not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "engine-refusal.json",
        dict(
            mutation=drift,
            error=type(caught.value).__name__,
            message=str(caught.value),
            delegate_calls=0,
            original_registries_empty=True,
        ),
    )


@pytest.fixture
def history_loop_model(tmp_path):
    """Installed CPython observer mechanism only, no public parent/claim."""
    h = interpreter_model.installed_iteration_model.__wrapped__(tmp_path)

    class Calendar:
        def __init__(self):
            self.labels = tuple(float(i) for i in range(6))
            self.next_calls = 0

        def __iter__(self):
            return self

        def __next__(self):
            value = self.labels[self.next_calls]
            self.next_calls += 1
            return value

        def __getitem__(self, index):
            return self.labels[index]

    context = h.context
    h.phase.steps = h.calendar = Calendar()
    context.calendar_raw = (h.calendar, h.phase.sampled, None)
    context.request = NS(iterations=3)
    context.timeline = stage._Timeline(3)
    context.runtime = h.namespace
    scope = dict(vars(stage), _guard=h.namespace["_guard"])
    provider_calls = []

    def begin(claim, *, child, ordinal, source_time, source_frame):
        provider_calls.append(("begin", ordinal, source_time, source_frame))
        return object()

    def end(claim, *, child, ordinal, source_time, source_frame):
        provider_calls.append(("end", ordinal, source_time, source_frame))
        return object()

    provider = NS(begin_iteration=begin, finish_iteration=end)
    scope.update(
        _runtime=lambda ignored: (provider, object()),
        _diagnostics=lambda ignored: None,
        RUNTIME_BEGIN="begin_iteration",
        RUNTIME_END="finish_iteration",
    )
    for name in ("_begin", "_end", "_loop_boundary", "_observe"):
        scope[name] = FunctionType(getattr(stage, name).__code__, scope)
        h.namespace[name] = scope[name]
    h.namespace["_snapshot"] = lambda ignored: NS(identity=str(len(h.phase.bodies)))
    dispatch = stage._engine(NS())["_dispatch_impl"]
    h.namespace["_dispatch"] = FunctionType(dispatch.__code__, h.namespace)
    # The reused fixture's actual invoke globals retain the dispatch callback.
    # Update that private model slot as well as its observer namespace.
    api = h.namespace["previous"].storage.previous.previous.previous
    api.child_dispatch = h.namespace["_dispatch"]
    h.provider_calls = provider_calls
    return h


def test_short_history_installed_dual_hooks_stop_after_N_before_next_calendar_advance(
    history_loop_model,
):
    h = history_loop_model
    required = sys.getprofile(), sys.gettrace()
    h.drive()
    assert h.phase.bodies == [0.0, 1.0, 2.0]
    assert h.calendar.next_calls == 3 and h.context.loop_visits == 4
    assert h.context.timeline.completed == 3 and h.context.timeline.current is None
    assert len(h.context.timeline.records) == 3
    assert [(kind, ordinal) for kind, ordinal, _, _ in h.provider_calls] == [
        (kind, ordinal) for ordinal in range(3) for kind in ("begin", "end")
    ]
    assert all(frame is h.context.loop_frame for _, _, _, frame in h.provider_calls)
    assert h.context.time_steps is h.calendar
    assert h.context.calendar_raw == (h.calendar, h.phase.sampled, None)
    assert h.context.selected_stopped and not h.context.loop_returned
    assert h.context.hooks_safe and h.context.cleanup_errors == ()
    assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
    assert not stage._CONSUMED and not stage._ISSUED
    software.snapshot.write_json(
        h.directory / "installed-history.json",
        dict(
            requested=3,
            bodies=h.phase.bodies,
            iterator_advances=h.calendar.next_calls,
            loop_boundaries=h.context.loop_visits,
            provider_boundaries=[(kind, ordinal) for kind, ordinal, _, _ in h.provider_calls],
            completed=h.context.timeline.completed,
            actual_loop_frame_preserved=True,
            both_hooks_restored=True,
            actual_parent_or_native_execution=False,
        ),
    )


@pytest.mark.parametrize("entry", ("declaration", "preparation"))
@pytest.mark.parametrize("layer", ("profile", "trace"))
def test_short_history_caught_public_reentry_poison_precedes_any_loop_delegate(
    history_loop_model,
    entry,
    layer,
):
    h = history_loop_model
    rejected = []

    def callback(frame, event, arg):
        stage._ACTIVE.append(h.context)
        try:
            with pytest.raises(stage.base.FirstStepRejected) as caught:
                if entry == "declaration":
                    stage.from_electrical(object(), iterations=2, law_id=stage.LAW_ID)
                else:
                    stage.prepare(object())
            rejected.append(caught.value)
        finally:
            assert stage._ACTIVE.pop() is h.context

    with h.inherited(layer, "call", callback):
        with pytest.raises(stage.base.FirstStepRejected) as caught:
            h.drive()
    assert rejected and caught.value is rejected[0] is h.context.entry_error
    assert h.context.invalid and h.phase.bodies == [] and h.calendar.next_calls == 0
    assert h.context.timeline.records == [] and not stage._ISSUED
    software.snapshot.write_json(
        h.directory / "caught-entry-refusal.json",
        dict(
            method=entry,
            hook=layer,
            identical_sticky_primary=True,
            error=type(caught.value).__name__,
            message=str(caught.value),
            delegate_calls=len(h.phase.bodies),
            iterator_advances=h.calendar.next_calls,
            poisoned=h.context.invalid,
            issued_owner=False,
        ),
    )


class FalseSourceError(ValueError):
    def __bool__(self):
        return False


def _outer_failure_model(monkeypatch, *, broken_journal=False):
    """Exercise actual prepare failure/finally code in an isolated namespace.

    No real request/owner registry, readiness checker or source entry is used.
    This is not a substitute chain for the held public API.
    """
    source, cause = FalseSourceError("first actual source"), OSError("source cause")
    source.__cause__ = cause
    admission, capture = ValueError("later admission"), RuntimeError("later capture")
    required, hooks, actions = (object(), object()), [None, None], []

    class BrokenJournal:
        def __add__(self, item):
            raise LookupError("secondary journal failure")

    def set_hook(index, value):
        actions.append(("set", index, value))
        hooks[index] = value
        if broken_journal:
            raise OSError("setter error after restoring actual identity")

    context = NS(
        initial=NS(atoms=lambda fn: (fn,), checker=object()),
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
    parent_api = NS(
        _authority=lambda owner: parent,
        _snapshot=lambda value: NS(identity="sealed"),
        _graph=lambda value: ((), ()),
    )
    binding = NS(module=parent_api, claim=lambda *a, **k: parent)
    request = stage.Request(object(), "parent", "mode", stage.SELECTION, "value", 2, "id")
    refs = (parent, parent.trial, NS(identity="sealed"), ((), ()))

    def fail(current):
        try:
            raise source from cause
        except FalseSourceError as original:
            current.first_failure = ("source", original)
            current.primary = original
            current.entry_error, current.capture_error = admission, capture
            raise capture from original

    engine = {"_namespace": fail, "_claim_wrapper": object()}
    base = NS(**dict(vars(stage.base)))
    base._digest, base._context = lambda value: "mode", lambda actual, values: context
    base.previous = NS(_callable_atoms=lambda current, fn: (fn,))
    namespace = dict(
        vars(stage),
        base=base,
        _ready=lambda: binding,
        _parent=lambda value: None,
        _engine=lambda current: engine,
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
    with pytest.raises(stage.ShortHistoryRejected) as caught:
        prepare(request, enabled=True)
    return NS(
        caught=caught.value,
        context=context,
        source=source,
        cause=cause,
        capture=capture,
        actions=actions,
        required=required,
        hooks=hooks,
        namespace=namespace,
    )


@pytest.mark.parametrize("broken_journal", (False, True))
def test_short_history_outer_failure_keeps_first_falsey_source_and_recovers_both_hooks(
    monkeypatch,
    broken_journal,
    tmp_path,
):
    h = _outer_failure_model(monkeypatch, broken_journal=broken_journal)
    assert h.caught.__cause__ is h.source and h.source.__cause__ is h.cause
    assert h.context.failure_error is h.source
    assert h.context.secondary_error == (h.capture, h.source)
    assert [index for _, index, _ in h.actions] == [1, 0]
    assert tuple(h.hooks) == h.required and h.context.hooks_safe
    assert h.context.final_hooks == (h.required, h.required)
    assert h.namespace["_FAILED"] == [h.context] and not h.namespace["_ISSUED"]
    if broken_journal:
        assert isinstance(h.context.cleanup_journal_error[0], LookupError)
        assert isinstance(h.context.cleanup_journal_error[1], OSError)
    software.snapshot.write_json(
        tmp_path / "outer-failure-retention.json",
        dict(
            primary_type=type(h.caught.__cause__).__name__,
            primary=str(h.caught.__cause__),
            primary_truth=bool(h.source),
            source_cause=str(h.source.__cause__),
            secondary_type=type(h.capture).__name__,
            secondary=str(h.capture),
            journal_failed=broken_journal,
            restore_order=[i for _, i, _ in h.actions],
            identical_source_primary_and_cause=True,
            both_hooks_restored=h.context.hooks_safe,
            retained_failed_context=True,
            issued_owner=False,
            complete_raw_owner_archive=False,
        ),
    )


@dataclass(frozen=True)
class _DiagnosticMetadata:
    value: str = "metadata only"


def _closed_metadata_model(count=2):
    labels, sampled = (0.0, 0.5), {0.0}
    ledger = stage._Timeline(count)
    for i, value in enumerate(labels[:count]):
        ledger.begin(value, value in sampled)
        ledger.end(stage.Iteration(i, value, value in sampled, NS(identity=str(i)), i, 0, object()))

    def snapshot(value):
        return NS(identity=repr(value))

    trial = stage.Trial(
        "request",
        "parent",
        NS(identity="before"),
        NS(identity="after"),
        snapshot(labels),
        snapshot(tuple(sampled)),
        snapshot(0.1),
        tuple(ledger.records),
        (),
        (),
        (),
        (),
        ("original-before",),
        ("actual-after",),
        True,
        False,
        True,
        _DiagnosticMetadata(),
        "",
    )
    context = NS(
        timeline=ledger,
        request=NS(iterations=count),
        stream_ids=("original-before",),
        parent=object(),
        sampled=sampled,
        time_steps=labels,
        calendar_raw=(labels, sampled, None),
        p=NS(dt=0.1),
    )
    base = NS(
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
        assert child is context and record is row.molecular_record
        assert source_time is row.source_time
        return record

    check = FunctionType(
        stage._closed_protocol.__code__,
        dict(
            vars(stage),
            base=base,
            _runtime=lambda current: (NS(validate_iteration=validate), object()),
        ),
    )
    return NS(context=context, trial=trial, check=check)


@pytest.mark.parametrize(
    "change",
    (
        "unchanged",
        "sampled",
        "rng_before",
        "rng_after",
        "completed",
        "current",
        "invalid",
        "source_completed",
        "loop_returned",
        "selected_stop",
        "calendar",
        "dt",
        "target_bool",
        "completed_bool",
        "ordinal_bool",
        "sample_int",
    ),
)
def test_short_history_closed_protocol_refuses_sample_stream_and_epoch_drift_without_owner(
    change,
    tmp_path,
):
    h = _closed_metadata_model(count=1 if change.endswith("bool") or change == "sample_int" else 2)
    before = stage.trial_record(h.trial)
    if change == "sampled":
        object.__setattr__(h.trial.iterations[0], "sampled", False)
    elif change in ("rng_before", "rng_after"):
        h.trial = replace(h.trial, **{change: ("retargeted",)})
    elif change == "completed":
        h.context.timeline.completed = 1
    elif change == "current":
        h.context.timeline.current = (2, 1.0, False)
    elif change == "invalid":
        h.context.timeline.invalid = True
    elif change in ("source_completed", "loop_returned", "selected_stop"):
        h.trial = replace(h.trial, **{change: change == "loop_returned"})
    elif change == "calendar":
        h.context.time_steps = tuple([0.0, 0.5])
    elif change == "dt":
        h.context.p.dt = 0.2
    elif change == "target_bool":
        h.context.timeline.target = True
    elif change == "completed_bool":
        h.context.timeline.completed = True
    elif change == "ordinal_bool":
        object.__setattr__(h.trial.iterations[0], "ordinal", False)
    elif change == "sample_int":
        object.__setattr__(h.trial.iterations[0], "sampled", 1)
    if change == "unchanged":
        h.check(h.context, h.trial)
    else:
        with pytest.raises(ValueError):
            h.check(h.context, h.trial)
    if change in ("sampled", "rng_before", "rng_after"):
        assert stage.trial_record(h.trial) != before
    assert not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "closed-protocol-control.json",
        dict(
            mutation=change,
            accepted=change == "unchanged",
            ordinal_type=type(h.trial.iterations[0].ordinal).__name__,
            sampled_type=type(h.trial.iterations[0].sampled).__name__,
            target_type=type(h.context.timeline.target).__name__,
            completed_type=type(h.context.timeline.completed).__name__,
            rng_before=h.trial.rng_before,
            rng_after=h.trial.rng_after,
            metadata_only=True,
            actual_owner_issued=False,
        ),
    )


@pytest.mark.parametrize("layer", ("electrical", "Completion"))
def test_short_history_parent_and_key_contracts_stay_held_before_foreign_entry(layer, tmp_path):
    electrical = stage.base.previous
    if layer == "electrical":
        with pytest.raises(electrical.ElectricalRejected) as caught:
            electrical._short_init_api()
        assert caught.value.stage == "short_init_held"
    else:
        with pytest.raises(electrical.storage.StorageRejected) as caught:
            electrical.storage._short_init_key_api()
        assert caught.value.stage == "short_init_ancestor_held"
    software.snapshot.write_json(
        tmp_path / "unavailable-parent-refusal.json",
        dict(
            layer=layer,
            stage=caught.value.stage,
            error=type(caught.value).__name__,
            message=str(caught.value),
            claimed_or_published=False,
        ),
    )


def test_short_history_request_hydration_and_iteration_record_schema_remain_explicit(tmp_path):
    request = stage.Request(object(), "parent", "source", stage.SELECTION, "value", 2, "id")
    with pytest.raises(TypeError):
        request.__reduce_ex__(4)
    h = _closed_metadata_model()
    row = stage.trial_record(h.trial)["iterations"][0]
    assert len(row) == 8
    assert row[0] == 0 and row[2] is True and row[3] == "0"
    assert stage.trial_record(h.trial)["rng_before"] == ("original-before",)
    assert stage.trial_record(h.trial)["rng_after"] == ("actual-after",)
    assert software.ELECTRICAL in software.OWNED and software.STORAGE in software.OWNED
    software.snapshot.write_json(
        tmp_path / "record-schema.json",
        dict(
            iteration_fields=(
                "ordinal",
                "time_bits",
                "sampled",
                "after",
                "work_end",
                "callbacks_end",
                "molecular_record_id",
                "diagnostics",
            ),
            trial_record_keys=tuple(stage.trial_record(h.trial)),
            explicit_rng_rosters=True,
            request_hydration_refused=True,
            metadata_only=True,
        ),
    )


@pytest.mark.parametrize(
    "slot",
    (
        "PARENT_SOURCE_SHA256",
        "PARENT_REVIEW_SHA256",
        "RUNTIME_SOURCE_SHA256",
        "RUNTIME_REVIEW_SHA256",
    ),
)
def test_short_history_runtime_consumer_binding_excludes_only_declared_literal_backrefs(
    slot,
    tmp_path,
):
    raw = stage.Path(stage.__file__).read_bytes()
    identity, original = runtime_provider.consumer_binding(raw)
    assert tuple(name for name, _ in original) == runtime_provider.CONSUMER_BACK_REFERENCE_SLOTS
    assert all(value is None for _, value in original)
    before = (slot + " = None").encode()
    assert raw.count(before) == 1
    changed = raw.replace(before, (slot + " = " + repr("a" * 64)).encode())
    after_identity, after = runtime_provider.consumer_binding(changed)
    assert after_identity == identity and dict(after)[slot] == "a" * 64
    assert all(value is None for name, value in after if name != slot)
    assert runtime_provider.consumer_binding(raw + b"\n# distinct metadata bytes\n")[0] != identity
    assert stage.PARENT_SOURCE_SHA256 is stage.RUNTIME_SOURCE_SHA256 is None
    assert not stage._ISSUED and not stage._CONSUMED
    software.snapshot.write_json(
        tmp_path / "four-backref-control.json",
        dict(
            mutated_slot=slot,
            original_identity=identity,
            normalized_identity=after_identity,
            actual_backrefs=after,
            unrelated_bytes_refused=True,
            producer_or_owner_adoption=False,
        ),
    )


def _toy_functions(text, namespace):
    """Fixed test definitions only, without executing a labelled module."""
    compiled = compile(ast.parse(text), __file__, "exec", dont_inherit=True)
    return {
        value.co_name: FunctionType(value, namespace)
        for value in compiled.co_consts
        if type(value) is CodeType
    }


def _issued_history_inputs(monkeypatch, tmp_path, *, retained_flux, failed):
    """Declared pre-birth acquisition; actual public claims stay installed."""
    from tests.unit import test_betse_native_init_dynamics_completion as completion_model

    base = stage.base
    previous = {name: getattr(base, name) for name in ("_ready", "_namespace", "source_plan")}
    h = interpreter_model._enabled_public_chain_inputs(monkeypatch, tmp_path)
    namespace_builder = base._namespace
    for name, fn in previous.items():
        monkeypatch.setattr(base, name, fn)
    numpy = interpreter_model.np
    h.p.init_tsteps, h.p.F = 5, 96485.33212
    h.cells.cell_vol, h.cells.ecm_vol = numpy.array([1.0, 2.0]), 1.0
    # Explicit synthetic predecessor data, set before any public issuer. This
    # describes both retained modes and confers no native operator authority.
    h.cells.lapENVinv = h.cells.environment
    h.cells.lapENV_P_inv = h.cells.environment if retained_flux else None
    h.calendar = numpy.linspace(0.0, 5 * h.p.dt, 5)
    h.sampled = {h.calendar[1], h.calendar[2]}
    h.first_step_namespace.update(calendar=h.calendar, sampled=h.sampled)
    factory = h.factories["Simulator"]
    scope = dict(
        __name__=__name__,
        __builtins__=__builtins__,
        np=numpy,
        milestone=factory.__init__.__globals__["milestone"],
    )
    factory.__init__ = _toy_functions(
        """
def __init__(self):
    milestone("Simulator.__init__")
    self.cc_cells = np.array([[1.0, 2.0], [2.0, 3.0]])
    self.cc_env = np.array([[3.0, 4.0], [4.0, 5.0]])
    self.zs = np.array([1.0, -1.0])
""",
        scope,
    )["__init__"]
    actual_engine = stage._engine
    original_network = completion_model._synthetic_enabled_network
    h.synthetic_error = FalseSourceError("declared second-iteration molecular failure")
    h.synthetic_cause = OSError("declared retained source cause")

    def enabled_network(inputs, patch):
        original_network(inputs, patch)
        cls = completion_model.Molecule
        namespace = dict(
            cls.update_intra.__globals__,
            failure_enabled=failed,
            failure=h.synthetic_error,
            cause=h.synthetic_cause,
        )
        # Original toy transport increments c_cells once. Inject failure on its
        # second reached update using that actual retained array, no reset.
        cls.update_intra = _toy_functions(
            """
def update_intra(self, sim, cells, p):
    self.cc_at_mem = self.c_cells
    if failure_enabled and self.c_cells[0] == 2.0:
        raise failure from cause
""",
            namespace,
        )["update_intra"]

    def engine(context):
        namespace = actual_engine(context)
        namespace["_namespace"] = namespace_builder
        namespace["_domain"] = lambda c: None  # Toy bodies, no native FULL-branch credit.
        return namespace

    electrical, storage = base.previous, base.previous.storage

    # These are source-interface NAME declarations, not producer/review
    # admission. Bind the actual functions before any public issuer runs;
    # production guards must resolve the same names at every later check.
    for module, values in (
        (
            electrical,
            dict(PARENT_CLAIM="_claim_for_electrical", PARENT_CHECK="_check_electrical_authority"),
        ),
        (
            storage,
            dict(
                ELECTRICAL_ANCESTOR_CLAIM="_claim_electrical_ancestor",
                ELECTRICAL_ANCESTOR_CHECK="_check_electrical_ancestor",
                SHORT_INIT_ANCESTOR_CLAIM="_claim_short_init_ancestor",
                SHORT_INIT_ANCESTOR_CHECK="_check_short_init_ancestor",
            ),
        ),
    ):
        for name, value in values.items():
            monkeypatch.setattr(module, name, value)

    electrical_functions = storage._claim_for_electrical, storage._check_electrical_authority
    electrical_parent = electrical._ParentBinding(
        storage,
        *electrical_functions,
        tuple(electrical._parent_atoms(fn) for fn in electrical_functions),
    )

    def electrical_ready():
        electrical._check_parent_binding(electrical_parent)
        return electrical_parent

    monkeypatch.setattr(electrical, "_ready", electrical_ready)
    parent_functions = electrical._claim_for_short_init, electrical._check_short_init_authority
    history_parent = base._ParentBinding(
        electrical,
        *parent_functions,
        tuple(electrical._parent_atoms(fn) for fn in parent_functions),
    )

    def ready():
        stage._parent(history_parent)
        return history_parent

    def binding():
        names = (
            "prepare",
            "_ready",
            "_claim_wrapper",
            "_dispatch",
            "_check_ancestor_metadata",
            "_mutation_contract",
        )
        return electrical._StepBinding(
            stage,
            tuple(
                (name, vars(stage)[name], storage._electrical_atoms(vars(stage)[name]))
                for name in names
            ),
        )

    monkeypatch.setattr(completion_model, "_synthetic_enabled_network", enabled_network)
    monkeypatch.setattr(stage, "_ready", ready)
    monkeypatch.setattr(stage, "_engine", engine)
    monkeypatch.setattr(stage, "source_plan", lambda: dict(synthetic_history_ownership_only=True))
    for name, value in dict(
        PARENT_CLAIM="_claim_for_short_init",
        PARENT_CHECK="_check_short_init_authority",
        RUNTIME_BEGIN="begin_iteration",
        RUNTIME_END="finish_iteration",
        RUNTIME_CONTRACT=runtime_provider.LAW_ID,
        RUNTIME_SOURCE_SHA256=software.snapshot.digest(stage.Path(runtime_provider.__file__)),
    ).items():
        monkeypatch.setattr(stage, name, value)
    monkeypatch.setattr(electrical, "_short_init_api", binding)
    monkeypatch.setattr(completion_model.stage, "_molecule_short_api", lambda: runtime_provider)
    monkeypatch.setattr(runtime_provider, "_ready", lambda: stage)
    monkeypatch.setenv(stage.RELEASE, "1")
    # Exercise the real non-mutating binding checkers while still pre-birth.
    # An absent name or a foreign/currently retargeted function must fail here,
    # not consume an expensive source-chain epoch before discovering it.
    electrical._check_parent_binding(electrical._ready())
    storage._check_electrical_binding(storage._electrical_api())
    stage._parent(stage._ready())
    electrical._check_step_binding(electrical._short_init_api())
    h.synthetic_contract = (electrical_parent, history_parent)
    h.seams += (
        "fresh actual public issuer/claim chain; only declared pre-birth toy acquisition/readiness",
        "five-label unsliced calendar; three actual contiguous toy iterations; no FirstStepOwner",
        "retained toy operator presence only; no native equation/operator/physical admission",
    )
    return h


def _run_issued_history(monkeypatch, tmp_path, *, retained_flux, failed):
    from tests.unit import test_betse_native_init_dynamics_completion as completion_model

    software.diagnostic_stage("fixture:prebirth_inputs_enter")
    h = _issued_history_inputs(monkeypatch, tmp_path, retained_flux=retained_flux, failed=failed)
    software.diagnostic_stage("fixture:prebirth_inputs_return")
    generator = completion_model.issued_synthetic_completion.__wrapped__(
        h, monkeypatch, tmp_path, native_molecules=True
    )
    started, primary, current, expected_source = time.monotonic(), None, None, None
    outcomes = []
    try:
        software.diagnostic_stage("fixture:fresh_parent_generation_enter")
        h = next(generator)
        software.diagnostic_stage("fixture:Completion_owner_yielded")
        original, prior = h.completion_context, h.completion_owner
        for label, api, declaration in (
            ("storage", stage.base.previous.storage, "from_dynamics"),
            ("electrical", stage.base.previous, "from_storage"),
            ("history", stage, "from_electrical"),
        ):
            kwargs = dict(law_id=api.LAW_ID)
            if api is stage:
                kwargs["iterations"] = 3
            software.diagnostic_stage(label + ":declaration_enter")
            request = getattr(api, declaration)(prior, **kwargs)
            software.diagnostic_stage(label + ":declaration_return")
            try:
                software.diagnostic_stage(label + ":prepare_enter")
                prior = api.prepare(request, enabled=True)
                software.diagnostic_stage(label + ":prepare_return")
            except BaseException as error:
                software.diagnostic_stage(label + ":prepare_unwind", error)
                current = api._CONSUMED.get(request)
                if api is not stage or not failed:
                    raise
                assert isinstance(error, stage.ShortHistoryRejected)
                assert error.__cause__ is h.synthetic_error
                assert h.synthetic_error.__cause__ is h.synthetic_cause
                expected_source = h.synthetic_error
                assert current.invalid and current.timeline.completed == 1
                assert current.timeline.current[0] == 1 and current.trial is None
                assert not hasattr(current, "owner")
                with pytest.raises(stage.ShortHistoryRejected, match="attempted"):
                    stage.prepare(request, enabled=True)
                interpreter_model._chain_checkpoint(
                    tmp_path, "retained-mid-history-failure", current, error=error
                )
                outcomes.append(dict(stage=label, status="expected_failed", completed=1))
                break
            software.diagnostic_stage(label + ":closed_owner_validation_enter")
            current = api._authority(prior)
            software.diagnostic_stage(label + ":closed_owner_validation_return")
            assert all(
                getattr(current, field) is getattr(original, field)
                for field in ("phase", "sim", "cells", "p", "handler")
            )
            interpreter_model._chain_checkpoint(tmp_path, label, current)
            outcomes.append(dict(stage=label, status="completed", trial=current.trial.identity))
        if not failed:
            assert type(prior) is stage.ShortHistoryOwner
            assert current.timeline.completed == 3 and current.timeline.current is None
            assert len(current.trial.iterations) == 3 and len(current.sim.vm_time) == 2
            assert current.time_steps is h.calendar and current.sampled is h.sampled
            assert current.selected_stopped and not current.loop_returned
            assert (
                runtime_provider.validate_runtime(current.molecule_claim, child=current)
                is current.molecule_record
            )
            assert current.request.operator_mode == (
                "original_value_and_flux" if retained_flux else "original_value_only_flux_omitted"
            )
        software.snapshot.write_json(
            tmp_path / "issued-history-outcome.json",
            dict(
                status="completed_control",
                expected_mid_failure=failed,
                retained_flux=retained_flux,
                elapsed_seconds=time.monotonic() - started,
                outcomes=outcomes,
                seams=h.seams,
                requested_iterations=3,
                distinct_inputs=1,
                prefix_work_is_not_independent_cases=True,
                actual_native_operator_RNG_reference_or_physical_credit=0,
            ),
        )
    except BaseException as error:
        software.diagnostic_stage("fixture:control_unwind", error)
        primary = error
        if current is None:
            # Retain only a real public issuer's request/consumption edge,
            # never arbitrary exception.partial or a fabricated failed owner.
            for api, field in (
                (completion_model.stage, "completion_request"),
                (completion_model.stage.previous, "dynamics_request"),
                (guard_model.stage, "request"),
            ):
                attempted = vars(h).get(field)
                if type(attempted) is api.Request and attempted in api._REQUESTS:
                    partial = api._CONSUMED.get(attempted)
                    if partial is not None and partial.request is attempted:
                        current = partial
                        break
        if current is not None:
            try:
                interpreter_model._chain_checkpoint(
                    tmp_path, "failed-control", current, error=error
                )
            except BaseException as capture:
                software.snapshot.write_json(
                    tmp_path / "failed-control-capture.json",
                    dict(
                        primary=str(error), capture=str(capture), complete_raw_serialization=False
                    ),
                )
        raise
    finally:
        software.diagnostic_stage("fixture:cleanup_enter", primary)
        try:
            generator.close()
            software.diagnostic_stage("fixture:cleanup_return")
        except BaseException as cleanup:
            software.diagnostic_stage("fixture:cleanup_error", cleanup)
            retained = primary if primary is not None else expected_source
            software.snapshot.write_json(
                tmp_path / "fixture-cleanup-secondary.json",
                dict(primary=None if retained is None else str(retained), cleanup=str(cleanup)),
            )
            if primary is None:
                raise cleanup from retained


def test_short_history_issued_value_only(monkeypatch, tmp_path):
    _run_issued_history(monkeypatch, tmp_path, retained_flux=False, failed=False)


def test_short_history_issued_retained_flux(monkeypatch, tmp_path):
    _run_issued_history(monkeypatch, tmp_path, retained_flux=True, failed=False)


def test_short_history_failed_mid_history_value_only(monkeypatch, tmp_path):
    _run_issued_history(monkeypatch, tmp_path, retained_flux=False, failed=True)


def test_short_history_failed_mid_history_retained_flux(monkeypatch, tmp_path):
    _run_issued_history(monkeypatch, tmp_path, retained_flux=True, failed=True)


@pytest.mark.parametrize(
    "selection",
    (
        "test_short_history_issued_value_only,metadata",
        "test_short_history_issued_value_only,test_short_history_issued_retained_flux",
        "prefix_test_short_history_failed_mid_history_value_only",
    ),
)
def test_issued_history_software_mode_refuses_ambiguous_owner_selection(selection):
    with pytest.raises(ValueError, match="One exact"):
        software._policy(selection, 480)


def test_issued_history_driver_gate_refuses_fake_and_foreign_frames_before_lookup(monkeypatch):
    monkeypatch.setenv(software.ISSUED_RELEASE, "1")
    assert software._issued_driver(object()) is False
    assert software._issued_driver(sys._getframe()) is False
    assert len(software.ISSUED_CASES) == len(set(software.ISSUED_CASES)) == 4
    assert all(software._policy(name, 480) == 480 for name in software.ISSUED_CASES)


def test_issued_history_wrong_lane_refuses_before_snapshot(tmp_path):
    with pytest.raises(ValueError, match="CPU6"):
        software.prepare(tmp_path / "never-created", software.ISSUED_CASES[0], cpu=4)
    assert not (tmp_path / "never-created").exists()


@pytest.mark.parametrize(
    "selection,seconds",
    (
        ("metadata", 1800),
        (software.ISSUED_CASES[1], 1800),
        (software.ISSUED_CASES[2], 1800),
        (software.ISSUED_CASES[3], 1800),
        (software.ISSUED_CASES[0], True),
        (software.ISSUED_CASES[0], 1800.0),
        (software.ISSUED_CASES[0], 7200),
    ),
)
def test_issued_history_extended_policy_refuses_other_cases_and_implicit_limits(selection, seconds):
    with pytest.raises(ValueError):
        software._policy(selection, seconds)


def _extended_inputs():
    selection = software.ISSUED_CASES[0]
    return dict(
        selection=selection,
        wall_seconds=1800,
        software_release_requested=True,
        software_integration_envelope=software._integration_envelope(selection, 1800),
        cpu=6,
        threads=1,
        software_bytes=2**30,
        reserve_bytes=8 * 2**30,
        snapshot_sha256="synthetic-metadata-only",
        owned_files={},
        short_history_dependencies={},
        setup_diagnostic=None,
    )


def test_issued_history_extended_policy_preserves_default_and_exact_named_envelope():
    for name in (*software.ISSUED_CASES, "metadata"):
        assert software._policy(name, 480) == 480
        assert software._integration_envelope(name, 480) is None
    inputs = _extended_inputs()
    assert software._prepared_policy(inputs, software.ISSUED_CASES[0], cpu=6, seconds=1800) == 1800
    with pytest.raises(ValueError):
        software._prepared_policy(inputs, software.ISSUED_CASES[0], cpu=6, seconds=480)


@pytest.mark.parametrize(
    "field,value",
    (
        ("cpu", 4),
        ("threads", True),
        ("software_bytes", 2**31),
        ("reserve_bytes", 0),
        ("software_release_requested", 1),
        ("software_integration_envelope", {"seconds": 1800}),
    ),
)
def test_issued_history_extended_prepared_resource_drift_refuses(field, value):
    inputs = _extended_inputs()
    inputs[field] = value
    with pytest.raises(ValueError, match="Exact prepared"):
        software._prepared_policy(inputs, software.ISSUED_CASES[0], cpu=6, seconds=1800)


def test_issued_history_extended_controller_input_drift_stops_before_snapshot(
    monkeypatch, tmp_path
):
    software.snapshot.write_json(tmp_path / "inputs.json", _extended_inputs())
    monkeypatch.setattr(software.snapshot, "verify", lambda *a, **k: pytest.fail("No verification"))
    with pytest.raises(ValueError, match="input digest"):
        software._controller_inputs(
            tmp_path, software.ISSUED_CASES[0], cpu=6, seconds=1800, inputs_sha256="wrong"
        )
    assert not (tmp_path / "process").exists()


def _metadata_controller(monkeypatch):
    monkeypatch.setenv(software.SOFTWARE_RELEASE, "1")
    monkeypatch.setattr(software.os, "sched_getaffinity", lambda pid: {6})
    monkeypatch.setattr(software, "_controller_inputs", lambda *a, **k: _extended_inputs())


def test_issued_history_extended_controller_retains_failed_guard_primary(monkeypatch, tmp_path):
    _metadata_controller(monkeypatch)
    primary, cause = FalseSourceError("synthetic resource stop"), OSError("saved cause")
    primary.__cause__ = cause
    calls = []

    def stop(command, **kwargs):
        calls.append((command, kwargs))
        raise primary

    monkeypatch.setattr(software.guard, "run_bounded", stop)
    with pytest.raises(FalseSourceError) as caught:
        software.run_prepared(
            tmp_path, software.ISSUED_CASES[0], cpu=6, seconds=1800, inputs_sha256="metadata"
        )
    assert caught.value is primary and caught.value.__cause__ is cause
    assert len(calls) == 1 and calls[0][1]["timeout"] == 1800
    assert calls[0][1]["max_rss_bytes"] == 2**30
    assert calls[0][1]["min_available_bytes"] == 8 * 2**30
    saved = software.json.loads((tmp_path / "controller-failure.json").read_text())
    assert saved["status"] == "failed" and saved["stage"] == "guarded_software_worker"
    assert saved["primary"][1]["args"] == ["saved cause"]
    assert not (tmp_path / "controller-result.json").exists()


def test_issued_history_extended_completed_image_keeps_checkout_drift_separate(
    monkeypatch, tmp_path
):
    _metadata_controller(monkeypatch)
    inputs_path = tmp_path / "inputs.json"
    software.snapshot.write_json(inputs_path, _extended_inputs())
    inputs_sha = software.snapshot.digest(inputs_path)
    calls = []

    def complete(command, **kwargs):
        calls.append((command, kwargs))
        software.snapshot.write_json(tmp_path / "child-cleanup.json", {"status": "completed"})
        software.snapshot.write_json(tmp_path / "native-entry-guard.json", {"attempted": []})
        (tmp_path / "reports").mkdir()
        for when in ("setup", "call", "teardown"):
            software.snapshot.write_json(
                tmp_path / "reports" / (when + ".json"), dict(when=when, outcome="passed")
            )

    def integration_drift(*args):
        raise ValueError("Unrelated current-checkout change")

    monkeypatch.setattr(software.guard, "run_bounded", complete)
    monkeypatch.setattr(software.snapshot, "verify", lambda *a, **k: None)
    monkeypatch.setattr(software.snapshot, "assert_checkout_unchanged", integration_drift)
    assert (
        software.run_prepared(
            tmp_path, software.ISSUED_CASES[0], cpu=6, seconds=1800, inputs_sha256=inputs_sha
        )
        == 0
    )
    saved = software.json.loads((tmp_path / "controller-result.json").read_text())
    assert saved["status"] == "completed" and saved["calls"] == 1 and len(calls) == 1
    assert saved["checkout_integration"]["integration_pending"] is True
    assert saved["scientific_credit"] == 0 and not (tmp_path / "controller-failure.json").exists()


def test_issued_history_extended_controller_exclusive_start_prevents_reexecution(
    monkeypatch, tmp_path
):
    _metadata_controller(monkeypatch)
    software.snapshot.write_json(tmp_path / "controller-start.json", {"original": True})
    before = software.snapshot.digest(tmp_path / "controller-start.json")
    monkeypatch.setattr(software.guard, "run_bounded", lambda *a, **k: pytest.fail("No second run"))
    with pytest.raises(FileExistsError):
        software.run_prepared(
            tmp_path, software.ISSUED_CASES[0], cpu=6, seconds=1800, inputs_sha256="metadata"
        )
    assert software.snapshot.digest(tmp_path / "controller-start.json") == before
    assert not (tmp_path / "process").exists()


def test_issued_history_extended_terminal_capture_cannot_replace_guard_primary(
    monkeypatch, tmp_path
):
    _metadata_controller(monkeypatch)
    primary, cause = FalseSourceError("guard stopped"), OSError("primary cause")
    primary.__cause__ = cause
    capture = OSError("terminal write failed")
    original_write = software.snapshot.write_json

    def stop(*args, **kwargs):
        raise primary

    def write(path, value):
        if path.name == "controller-failure.json":
            raise capture
        return original_write(path, value)

    monkeypatch.setattr(software.guard, "run_bounded", stop)
    monkeypatch.setattr(software.snapshot, "write_json", write)
    monkeypatch.setattr(software, "_RAW_FAILURES", ())
    with pytest.raises(FalseSourceError) as caught:
        software.run_prepared(
            tmp_path, software.ISSUED_CASES[0], cpu=6, seconds=1800, inputs_sha256="metadata"
        )
    assert caught.value is primary and caught.value.__cause__ is cause
    saved_primary, saved_capture, path = software._RAW_FAILURES[-1]
    assert saved_primary is primary and saved_capture is capture
    assert path == tmp_path / "controller-failure.json"


def _history_permission_model(*, molecular, gap):
    """Unissued holders; real pinned source effect derivation, no body/claim."""
    sim, callback, network = NS(), NS(), NS()
    context = NS(
        sim=sim,
        phase=NS(callbacks=callback),
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
    table = runtime_provider.base._runtime_field_table("first_step")
    if molecular:
        context.molecule_permissions = (
            (sim, table["Simulator"]),
            (network, table["MasterOfNetworks"]),
        )
    return NS(context=context, original=original, table=table, network=network)


@pytest.mark.parametrize("mode", ("source_only", "molecular", "molecular_gap"))
def test_short_history_complete_permission_contract_preserves_source_and_runtime_holders(
    tmp_path, mode
):
    h = _history_permission_model(molecular=mode != "source_only", gap=mode == "molecular_gap")
    context = h.context
    before = tuple((actual, vars(actual).copy()) for actual, _ in h.original)
    actual = stage._mutation_contract(context)
    expected = h.original
    if mode != "source_only":
        expected = (
            (context.sim, h.original[0][1] | h.table["Simulator"]),
            *h.original[1:],
            (h.network, h.table["MasterOfNetworks"]),
        )
    assert len(actual) == len(expected) and len({id(owner) for owner, _ in actual}) == len(actual)
    assert all(
        owner is original and fields == allowed and type(fields) is frozenset
        for (owner, fields), (original, allowed) in zip(actual, expected, strict=True)
    )
    assert context.runtime["_mutation_contract"] is stage._mutation_contract
    assert all(vars(owner) == retained for owner, retained in before)
    assert actual[0][0] is context.sim
    assert any(owner is context.phase.callbacks for owner, _ in actual)
    assert (len(actual) > len(h.original)) is (mode != "source_only")
    software.snapshot.write_json(
        tmp_path / "complete-permission-contract.json",
        dict(
            mode=mode,
            source_rows=len(h.original),
            complete_rows=len(actual),
            source_and_runtime_fields=[sorted(fields) for _, fields in actual],
            unique_actual_holders=True,
            simulator_union_preserves_both_source_rosters=True,
            no_claim_owner_or_native_body=True,
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "unchanged",
        "missing_source_field",
        "extra_source_field",
        "equal_holder",
        "duplicate_holder",
        "missing_sim",
        "foreign_holder",
        "permissions_not_tuple",
        "fields_not_frozen",
        "runtime_without_enabled_parent",
    ),
)
def test_short_history_complete_permission_contract_actual_ancestor_checker(tmp_path, mutation):
    """Exercise the real checker with unissued source-only metadata, no owner."""
    h = _history_permission_model(molecular=False, gap=True)
    context = h.context
    context.permissions = stage._mutation_contract(context)
    lease = NS(
        child=context,
        module=stage,
        parent=NS(sim=context.sim, request=NS(native_molecules=False), molecule_session=None),
        objects=tuple((str(index), owner) for index, (owner, _) in enumerate(context.permissions)),
    )
    checker = stage.base.previous.storage.previous._first_step_permissions
    original = context.permissions
    assert checker(lease) is original
    rows = list(original)
    if mutation == "missing_source_field":
        assert rows[0][1]
        rows[0] = (rows[0][0], rows[0][1] - {next(iter(rows[0][1]))})
    elif mutation == "extra_source_field":
        rows[0] = (rows[0][0], rows[0][1] | {"unowned_permission_probe"})
    elif mutation == "equal_holder":
        equal = NS(**vars(context.sim))
        assert equal == context.sim and equal is not context.sim
        rows[0] = (equal, rows[0][1])
    elif mutation == "duplicate_holder":
        rows[1] = rows[0]
    elif mutation == "missing_sim":
        rows.pop(0)
    elif mutation == "foreign_holder":
        rows[0] = (object(), rows[0][1])
    elif mutation == "fields_not_frozen":
        rows[0] = (rows[0][0], set(rows[0][1]))
    elif mutation == "runtime_without_enabled_parent":
        context.molecule_permissions = ((context.sim, frozenset(("cc_cells",))),)
        rows = list(stage._mutation_contract(context))
    context.permissions = rows if mutation == "permissions_not_tuple" else tuple(rows)
    caught = None
    if mutation == "unchanged":
        assert checker(lease) is context.permissions
    else:
        with pytest.raises(ValueError) as rejected:
            checker(lease)
        caught = rejected.value
    software.snapshot.write_json(
        tmp_path / "permission-ancestor-check.json",
        dict(
            mutation=mutation,
            actual_production_checker=True,
            refused=mutation != "unchanged",
            error_type=None if caught is None else type(caught).__name__,
            reason=None if caught is None else str(caught),
            original_source_permission_rows=len(original),
            no_issued_owner_or_runtime_claim_or_native_body=True,
        ),
    )


def _parameter_projection_model(monkeypatch):
    """Unissued metadata objects; real canonical projector and typed codec."""
    from cells.processes import betse_native_single_cell_poisson_observation as observation

    storage = stage.base.previous.storage
    completion, initial = storage.previous, storage.previous.previous.previous
    anim, equal_anim = NS(is_while_sim=False, retained=-0.0), NS(is_while_sim=False, retained=-0.0)
    p, sim, cells, callback = NS(anim=anim, dt=0.01), NS(vm=1.0, vm_time=[1]), NS(cell_i=[0]), NS()
    roots = [("animation_configuration", anim), ("already_retained_equal_animation", equal_anim)]
    objects = [("Simulator", sim), ("parameters", p), ("Cells", cells)]
    prefix = NS(
        parent=NS(world=NS(parent=NS(projector=NS(objects=roots)))),
        objects=objects,
        proxies=(),
        cells=cells,
        p=p,
        callback=callback,
    )
    parent = NS(init_parent=prefix, parent=NS(gap=None), tissue_session=None, molecule_session=None)
    context = NS(
        parent=parent,
        sim=sim,
        p=p,
        cells=cells,
        store_fields=frozenset(("vm_time",)),
        molecule_permissions=(),
        molecule_claim=None,
        objects=objects,
        permissions=((sim, frozenset(("vm_time",))),),
    )
    codec = observation.Scope()
    monkeypatch.setattr(completion, "_scope", lambda actual: codec)
    return NS(
        storage=storage,
        completion=completion,
        initial=initial,
        context=context,
        roots=roots,
        anim=anim,
        equal_anim=equal_anim,
        codec=codec,
    )


@pytest.mark.parametrize("consumer", ("storage", "history"))
def test_short_history_parameter_projection_keeps_actual_original_registered_roots(
    monkeypatch, consumer, tmp_path
):
    h = _parameter_projection_model(monkeypatch)
    root_refs = tuple(actual for _, actual in h.roots)
    snapshot = h.storage._snapshot if consumer == "storage" else stage._engine(NS())["_snapshot"]
    if consumer == "history":
        assert snapshot is stage._snapshot
    before = snapshot(h.context)
    after = snapshot(h.context)
    assert before.identity == after.identity and h.context.p.anim is h.anim
    projector = h.initial._projector(h.context.parent.init_parent)
    assert projector.objects[0][1] is h.anim and projector.objects[1][1] is h.equal_anim
    expected = h.initial.core._LITERAL._project(projector, h.anim)
    # Decode only the declared cache, never a phase or executable owner.
    from cells.processes import betse_initial_mesh_preparation_cache as codec

    value = codec.plain(before)
    fields = (
        value["parameters"]
        if consumer == "storage"
        else next(data for role, data in value if role == "parameters")
    )
    assert fields["anim"] == expected and fields["anim"] is not h.anim
    assert all(actual is retained for (_, actual), retained in zip(h.roots, root_refs, strict=True))
    software.snapshot.write_json(
        tmp_path / "projection.json",
        dict(
            consumer=consumer,
            before=before.identity,
            after=after.identity,
            exact_original_wrapper=True,
            predecessor_root_refs_unchanged=True,
            no_issued_owner_or_native_entry=True,
        ),
    )


@pytest.mark.parametrize("consumer", ("storage", "history"))
@pytest.mark.parametrize(
    "mutation", ("parameter_scalar", "wrapper_field", "unowned_wrapper", "equal_retained_root")
)
def test_short_history_parameter_projection_preserves_fields_and_distinguishes_retargets(
    monkeypatch, consumer, mutation, tmp_path
):
    h = _parameter_projection_model(monkeypatch)
    snapshot = h.storage._snapshot if consumer == "storage" else stage._engine(NS())["_snapshot"]
    before = snapshot(h.context)
    # The historical ancestor retains COMPLETE fields of the actual roots,
    # not only the reference tokens used by the child cache. Exercise that
    # original projector on the root fields rather than flattening vars(p).
    projector = h.initial._projector(h.context.parent.init_parent)
    project = h.initial.core._LITERAL._project

    def inherited_fields():
        return h.codec.snapshot(
            tuple((role, project(projector, vars(actual))) for role, actual in h.roots)
        )

    original_fields = inherited_fields()
    if mutation == "parameter_scalar":
        h.context.p.dt = 0.02
    elif mutation == "wrapper_field":
        h.anim.is_while_sim = True
    elif mutation == "unowned_wrapper":
        h.context.p.anim = NS(is_while_sim=False, retained=-0.0)
    else:
        assert h.anim is not h.equal_anim and vars(h.anim) == vars(h.equal_anim)
        h.context.p.anim = h.equal_anim
    if mutation == "unowned_wrapper":
        with pytest.raises(ValueError):
            snapshot(h.context)
        changed = "unregistered_actual_object_refused"
    elif mutation == "wrapper_field":
        assert h.context.p.anim is h.anim
        assert inherited_fields().identity != original_fields.identity
        # Reference identity intentionally stays the original object; the
        # inherited field witness changes instead of replacing the wrapper.
        assert snapshot(h.context).identity == before.identity
        changed = "original_inherited_wrapper_fields_changed"
    else:
        assert snapshot(h.context).identity != before.identity
        changed = "child_projection_changed"
    software.snapshot.write_json(
        tmp_path / "projection-mutation.json",
        dict(
            consumer=consumer,
            mutation=mutation,
            disposition=changed,
            real_parent_validation_not_replaced=True,
            private_codec_model_only=True,
        ),
    )


@pytest.mark.parametrize("consumer", ("storage", "history"))
def test_short_history_parameter_projection_keeps_only_existing_stable_permissions(
    monkeypatch, consumer
):
    h = _parameter_projection_model(monkeypatch)
    snapshot = h.storage._snapshot if consumer == "storage" else stage._engine(NS())["_snapshot"]
    full, stable = snapshot(h.context), snapshot(h.context, stable=True)
    h.context.sim.vm_time.append(2)
    assert snapshot(h.context).identity != full.identity
    assert snapshot(h.context, stable=True).identity == stable.identity
    h.context.p.dt = -0.0
    negative = snapshot(h.context, stable=True)
    h.context.p.dt = 0.0
    assert snapshot(h.context, stable=True).identity != negative.identity


def test_short_history_parameter_projection_software_cpu5_cannot_launch_issued_owner(tmp_path):
    assert software._cpu(5) == 5
    with pytest.raises(ValueError, match="CPU6"):
        software.prepare(tmp_path / "uncreated", software.ISSUED_CASES[0], cpu=5)
    assert not (tmp_path / "uncreated").exists()
    assert software.snapshot.digest(stage.Path(stage.base.__file__)) == stage.BASE_SOURCE_SHA256


@pytest.mark.parametrize("selection", software.ISSUED_CASES)
@pytest.mark.parametrize("count", (0, 1, 2))
def test_short_history_exact_issued_selector_ignores_parameter_and_output_labels(selection, count):
    exact = [NS(name=selection, originalname=selection) for _ in range(count)]
    misleading = [
        NS(name="test_metadata[" + selection + "]", originalname="test_metadata"),
        NS(name=selection + "[parameter]", originalname=selection),
        NS(name="prefix_" + selection, originalname="prefix_" + selection),
        NS(name=selection, originalname="other_function"),
        NS(name="test_other", originalname="test_other", nodeid=selection + "/output/test_other"),
    ]
    items = [misleading[0], *exact, *misleading[1:]]
    if count != 1:
        with pytest.raises(ValueError, match="Exactly one"):
            software._select_items(items, selection)
    else:
        chosen, removed = software._select_items(items, selection)
        assert len(chosen) == 1 and chosen[0] is exact[0]
        assert len(removed) == len(misleading)
        assert all(actual is expected for actual, expected in zip(removed, misleading, strict=True))


def test_short_history_exact_issued_reporter_reaches_actual_core_namespace(tmp_path):
    scope = software._scope()
    assert scope["Reports"] is software.Reports
    assert scope["base"].reuse.Reports is software.Reports
    reporter = software.Reports(tmp_path, NS(), software.ISSUED_CASES[0], [])
    wanted = NS(name=software.ISSUED_CASES[0], originalname=software.ISSUED_CASES[0])
    unwanted = NS(
        name="test_metadata[" + software.ISSUED_CASES[0] + "]", originalname="test_metadata"
    )
    removed = []
    config = NS(hook=NS(pytest_deselected=lambda *, items: removed.extend(items)))
    items = [unwanted, wanted]
    reporter.pytest_collection_modifyitems(config, items)
    assert items == [wanted] and removed == [unwanted]
    saved = software.json.loads((tmp_path / "selection.json").read_text())
    assert saved["selected"] == [software.ISSUED_CASES[0]]
    assert saved["deselected"] == [unwanted.name] and saved["matching"].startswith("exact")


@pytest.mark.parametrize(
    "retained_flux,failed", ((False, False), (True, False), (False, True), (True, True))
)
def test_short_history_prebirth_contract_binds_all_actual_hooks_without_issuing_owners(
    monkeypatch, tmp_path, retained_flux, failed
):
    completion = stage.base.previous.storage.previous
    initial = completion.previous.previous
    modules = (
        initial,
        completion.previous,
        completion,
        stage.base.previous.storage,
        stage.base.previous,
        stage,
    )
    prepares = tuple(module.prepare for module in modules)
    registries = tuple((module._REQUESTS, module._CONSUMED, module._ISSUED) for module in modules)
    counts = tuple(tuple(len(value) for value in row) for row in registries)
    h = _issued_history_inputs(monkeypatch, tmp_path, retained_flux=retained_flux, failed=failed)
    assert not hasattr(h, "owner") and not hasattr(h, "completion_owner")
    assert all(module.prepare is fn for module, fn in zip(modules, prepares, strict=True))
    assert tuple(tuple(len(value) for value in row) for row in registries) == counts
    electrical, storage = stage.base.previous, stage.base.previous.storage
    binding = electrical._ready()
    assert binding is h.synthetic_contract[0] and binding.module is storage
    assert electrical.PARENT_CLAIM == "_claim_for_electrical"
    assert electrical.PARENT_CHECK == "_check_electrical_authority"
    assert binding.claim is storage._claim_for_electrical
    assert binding.check is storage._check_electrical_authority
    assert stage._ready() is h.synthetic_contract[1]
    electrical._check_parent_binding(binding)
    storage._check_electrical_binding(storage._electrical_api())
    stage._parent(stage._ready())
    electrical._check_step_binding(electrical._short_init_api())
    assert (h.cells.lapENV_P_inv is not None) is retained_flux
    software.snapshot.write_json(
        tmp_path / "prebirth-contract.json",
        dict(
            retained_flux=retained_flux,
            declared_mid_failure=failed,
            actual_hook_names_and_identities=True,
            public_prepare_functions_unchanged=True,
            zero_owner_issuance=True,
            genuine_binding_checkers_executed=True,
            actual_native_source_RNG_operator_or_physical_credit=0,
        ),
    )


@pytest.mark.parametrize(
    "mutation", ("none_name", "wrong_name", "foreign_function", "same_code_copy", "code", "keyword")
)
def test_short_history_prebirth_contract_rejects_parent_name_or_function_drift_before_delegation(
    monkeypatch, tmp_path, mutation
):
    h = _issued_history_inputs(monkeypatch, tmp_path, retained_flux=False, failed=False)
    electrical, storage = stage.base.previous, stage.base.previous.storage
    original, called = storage._claim_for_electrical, []

    def foreign(*args, **kwargs):
        called.append(True)
        pytest.fail("A retargeted claim must never execute")

    if mutation == "none_name":
        monkeypatch.setattr(electrical, "PARENT_CLAIM", None)
    elif mutation == "wrong_name":
        monkeypatch.setattr(electrical, "PARENT_CLAIM", "_check_electrical_authority")
    elif mutation == "foreign_function":
        monkeypatch.setattr(storage, "_claim_for_electrical", foreign)
    elif mutation == "same_code_copy":
        copied = FunctionType(
            original.__code__,
            original.__globals__,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        copied.__kwdefaults__ = original.__kwdefaults__
        monkeypatch.setattr(storage, "_claim_for_electrical", copied)
    elif mutation == "code":

        def foreign_code(*args, **kwargs):
            pytest.fail("Changed claim code must not execute")

        monkeypatch.setattr(original, "__code__", foreign_code.__code__)
    else:
        monkeypatch.setattr(
            original, "__kwdefaults__", dict(original.__kwdefaults__ or {}, synthetic=True)
        )
    with pytest.raises((TypeError, ValueError)) as caught:
        electrical._ready()
    assert not called and not hasattr(h, "completion_owner")
    software.snapshot.write_json(
        tmp_path / "prebirth-contract-refusal.json",
        dict(
            mutation=mutation,
            type=type(caught.value).__name__,
            reason=str(caught.value),
            retained_binding_is_original=True,
            no_claim_or_native_body_called=True,
        ),
    )


def test_setup_cost_diagnostic_exception_summary_never_renders_owner_arguments():
    class Opaque:
        def __repr__(self):
            pytest.fail("No live owner graph rendering")

        __str__ = __repr__

    error = FalseSourceError(Opaque(), "kept primitive")
    error.__cause__ = OSError("original cause")
    summary = software.compact_error(error)
    assert len(summary) == 2 and summary[0]["args"][1] == "kept primitive"
    assert summary[0]["args"][0]["opaque_type"].endswith("Opaque")
    assert summary[1]["args"] == ["original cause"]


def test_setup_cost_diagnostic_stack_and_stage_caps_keep_outer_hooks(tmp_path):
    directory = tmp_path / "bounded-diagnostic"
    directory.mkdir()
    state = software.SetupDiagnostic(directory, {})
    hooks = sys.getprofile(), sys.gettrace()
    for _ in range(130):
        state.record("plain_metadata_stage")
    for _ in range(18):
        state._sample(0, sys._getframe())
    assert state.events == 128 and state.samples == 16 and state.skipped == 4
    assert len(list(directory.glob("stage-*.json"))) == 128
    assert len(list(directory.glob("stack-*.json"))) == 16
    assert sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]
    assert not state.errors


def test_setup_cost_diagnostic_local_method_events_restore_signal_monitor_and_hooks(tmp_path):
    signal = software.signal
    old_handler, old_timer = signal.getsignal(signal.SIGALRM), signal.getitimer(signal.ITIMER_REAL)
    hooks = sys.getprofile(), sys.gettrace()
    monitor = sys.monitoring
    tools = tuple(monitor.get_tool(i) for i in range(6))

    def target():
        return 17

    state = software.SetupDiagnostic(tmp_path / "local-diagnostic", {target.__code__: "target"})
    with state:
        assert target() == 17
        state._sample(0, sys._getframe())
    assert state.events == 4 and state.samples == 1 and not state.errors
    assert tuple(monitor.get_tool(i) for i in range(6)) == tools
    assert signal.getsignal(signal.SIGALRM) is old_handler
    assert signal.getitimer(signal.ITIMER_REAL) == old_timer
    assert sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]


# One collection module gives every plain diagnostic the same per-case native
# and operator/RNG blockade. Their real producer remains the paired test file.
for _name, _function in vars(diagnostic_controls).items():
    if _name.startswith("test_") and type(_function) is FunctionType:
        globals()[_name] = _function
