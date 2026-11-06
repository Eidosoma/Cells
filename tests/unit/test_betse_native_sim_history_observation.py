"""Closed metadata controls, never actual completed INIT/SIM authority.

Positive-shaped providers/registries live only in copied test module namespaces.
The actual completed owner and interval registries remain empty throughout.
"""

import contextlib
import hashlib
import sys
from dataclasses import replace
from pathlib import Path
from threading import RLock
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_sim_history_observation as stage
from tests.unit import test_betse_native_init_retained_world as guards
from validation.betse import betse_native_sim_history_observation_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    namespace = dict(vars(guards), software=software, _RAW_GUARDS=[])
    function = FunctionType(guards.blocked.__wrapped__.__code__, namespace)
    with contextlib.contextmanager(function)(request, tmp_path, monkeypatch):
        yield


class Foreign:
    def __getattribute__(self, name):
        raise AssertionError("No foreign authority read before release/producer gate")


def _model(monkeypatch, count=3, *, cache=None):
    # Actual codec/record shapes, but explicitly synthetic owner/provider state.
    original = stage.parent
    codec = original.previous.terminal.retained_cache
    cache = cache if cache is not None else codec.snapshot(np.asarray([-0.0, 2.0]))
    small = codec.snapshot("synthetic live state")
    rows = tuple(
        original.Iteration(i, np.float64(i), False, cache, ((), {}), (cache, cache), (), (), i)
        for i in range(count)
    )
    trial = original.Trial(
        "metadata_request",
        "metadata_assembly",
        "metadata_INIT",
        "metadata_parameters",
        "original",
        cache,
        (cache, ((), {}), (cache, cache)),
        (cache, ((), {}), (cache, cache)),
        cache,
        cache,
        0.1,
        rows,
        (cache, cache),
        (cache, cache),
        (),
        (),
        (),
        (),
        (),
        (),
        True,
        True,
        True,
        True,
        "",
    )
    trial = replace(trial, identity=original._digest(original.record_document(trial)))

    class MetadataOwner:
        pass

    owner = MetadataOwner()
    source = NS(
        owner=owner,
        trial=trial,
        active=False,
        invalid=False,
        metadata_work=[],
        retained_validation_attempts=0,
        retained_validation_returns=0,
        stable=NS(identity="stable"),
        after=(small, ((), {}), (small, small)),
    )
    source.current, source.stable_current = source.after, source.stable
    objects = (("metadata", source),)
    view = dict(
        owner=owner,
        trial=trial,
        iterations=rows,
        observation_objects=objects,
        observation_field_objects=objects,
        retained_cache_validation_work={},
    )
    provider, events = ModuleType("closed_metadata_completion_provider"), []
    provider._LOCK, provider._ACTIVE, provider._PREPARING = RLock(), [], None
    provider._ISSUED = {owner: source}
    provider.SimRunOwner, provider.Iteration, provider.MAX_ITERATIONS = (
        MetadataOwner,
        original.Iteration,
        512,
    )
    provider._count = original._count
    provider._metadata = original._metadata
    provider.previous = original.previous
    provider._links = lambda actual: events.append("source links")
    provider._bindings = lambda actual: events.append("source bindings")
    provider._same = original._same
    provider._digest, provider.record_document = original._digest, original.record_document
    provider._stable = lambda actual: actual.stable_current

    def snapshot(actual):
        events.append("fresh live metadata capture")
        return actual.current

    provider._snapshot = snapshot
    provider._observation_roster = lambda actual: (objects, objects)
    provider._recover = original._recover

    def full(actual):
        assert actual is owner
        events.append("full authority")
        if getattr(source, "fail_exit", None) is not None:
            raise source.fail_exit
        for value in module._caches(trial):
            source.retained_validation_attempts += 1
            codec.validate(value)
            source.retained_validation_returns += 1
        source.metadata_work.append(dict(call="modeled original complete sweep"))
        return trial

    def completed(actual):
        full(actual)
        return dict(view)

    provider.validate_sim, provider.completed_sim = full, completed
    name = "metadata_SIM_history_model_" + str(id(owner))
    module = ModuleType(name)
    module.__file__ = stage.__file__
    monkeypatch.setitem(sys.modules, name, module)
    exec(compile(Path(stage.__file__).read_bytes(), stage.__file__, "exec"), vars(module))
    module.parent = provider
    module._producer = lambda: provider
    module._EXIT_CHAIN = module._exit_chain(provider.validate_sim)
    module._SELF_API = module._self_bindings()
    monkeypatch.setenv(module.RELEASE, "1")
    return NS(
        api=module,
        provider=provider,
        owner=owner,
        source=source,
        trial=trial,
        rows=rows,
        cache=cache,
        codec=codec,
        view=view,
        events=events,
    )


def _finish(model, interval):
    for row in model.rows:
        assert interval.validate_sim(row=row) is model.trial


@pytest.mark.parametrize("enabled,flag", ((False, None), (True, None), (1, "1"), (True, "1")))
def test_history_default_release_and_producer_refuse_before_foreign_read(
    enabled, flag, monkeypatch
):
    if flag is None:
        monkeypatch.delenv(stage.RELEASE, raising=False)
    else:
        monkeypatch.setenv(stage.RELEASE, flag)
    with pytest.raises(stage.HistoryObservationRejected) as caught:
        with stage.observing_completed(Foreign(), enabled=enabled):
            pytest.fail("No actual owner or work available")
    assert caught.value.stage == ("producer_held" if enabled is True and flag == "1" else "release")
    assert not stage._ISSUED and not stage.parent._ISSUED and stage._PENDING is None


def test_history_contextmanager_and_method_actual_ABI_is_explicit():
    factory = stage.observing_completed
    assert type(factory) is FunctionType and type(factory.__wrapped__) is FunctionType
    assert factory.__globals__["__name__"] == "contextlib"
    assert factory.__wrapped__.__globals__ is vars(stage)
    assert factory.__wrapped__.__defaults__ is None
    assert factory.__wrapped__.__kwdefaults__ == dict(enabled=False)
    assert stage.CompletedHistoryObservation.validate_sim.__kwdefaults__ == dict(
        row=None, caches=()
    )
    assert stage.CompletedHistoryObservation.call.__kwdefaults__ == dict(row=None, caches=())
    with pytest.raises(TypeError):
        stage.CompletedHistoryObservation()


def test_history_complete_typed_model_brackets_with_original_authority_and_shared_exclusion(
    monkeypatch,
):
    model = _model(monkeypatch)
    with model.api.observing_completed(model.owner, enabled=True) as interval:
        assert model.provider._ACTIVE[-1].source is model.source
        view = interval.completed_sim()
        assert (
            view is not model.view and view["owner"] is model.owner and view["trial"] is model.trial
        )
        assert view["iterations"] is model.rows
        _finish(model, interval)
        assert interval.record is None
    record = interval.record
    assert record.status == "completed_observation" and record.checked_rows == (0, 1, 2)
    assert record.full_authority_attempts == record.full_authority_returns == 2
    assert record.retained_payload_attempts == record.retained_payload_returns == 9
    assert record.source_retained_cache_attempts == record.source_retained_cache_returns == 36
    assert record.native_or_scientific_credit == 0
    assert model.events.count("full authority") == 2
    assert model.events.count("fresh live metadata capture") == 5
    assert model.provider._ACTIVE == [] and model.api._PENDING is None
    with pytest.raises(model.api.HistoryObservationRejected):
        interval.validate_sim(row=model.rows[0])
    assert not stage._ISSUED and not stage.parent._ISSUED


@pytest.mark.parametrize("count", (350, 512))
def test_history_long_calendar_has_linear_fresh_payload_sweeps_and_exact_nested_counts(
    count, monkeypatch, tmp_path
):
    model = _model(monkeypatch, count, cache=stage._CACHE.snapshot("synthetic scalar payload"))
    with model.api.observing_completed(model.owner, enabled=True) as interval:
        _finish(model, interval)
    record = interval.record
    assert record.full_authority_attempts == record.full_authority_returns == 2
    assert (
        record.source_retained_cache_attempts
        == record.source_retained_cache_returns
        == 2 * (9 + 3 * count)
    )
    assert record.retained_payload_attempts == record.retained_payload_returns == 3 * count
    assert len(record.checked_rows) == count
    assert len(record.work) == count + 4
    assert record.source_metadata_operations == 2 + 2 * (count + 1)
    software.snapshot.write_json(
        tmp_path / "history-capacity.json",
        dict(
            rows=count,
            independent_cases=0,
            modeled_full_authority_calls=record.full_authority_attempts,
            actual_codec_full_sweep_occurrences=record.source_retained_cache_attempts,
            actual_codec_selected_payload_attempts=record.retained_payload_attempts,
            all_cache_immutable_proof_checks=sum(row[3] for row in record.work),
            operation_records=len(record.work),
            native_or_original_trajectory_work=0,
            actual_large_history_throughput_or_resource_admission=False,
        ),
    )


def test_history_large_shaped_columns_keep_all_bits_and_aliases(monkeypatch):
    from cells.processes import betse_native_single_cell_poisson_observation as observation

    first, second = np.zeros((625, 625)), np.ones((625, 625))
    cache = observation.Scope((first, second)).snapshot((first, second, first))
    model = _model(monkeypatch, cache=cache)
    with model.api.observing_completed(model.owner, enabled=True) as interval:
        for row in model.rows:
            assert interval.call(lambda actual: actual, row, row=row) is row
    assert interval.record.status == "completed_observation"
    assert interval.record.retained_payload_attempts == 18
    assert len(cache.columns) == 3 and cache.columns[0].values.shape == (625, 625)
    assert stage.parent.previous.terminal._column_bytes(
        cache.columns[0].values
    ) == stage.parent.previous.terminal._column_bytes(cache.columns[2].values)


@pytest.mark.parametrize("drift", ("cache", "row", "descriptor", "shape", "column", "dtype"))
def test_history_actual_retained_roots_and_headers_refuse_equal_copies_or_drift(drift, monkeypatch):
    model = _model(monkeypatch)
    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            _finish(model, interval)
            if drift == "cache":
                object.__setattr__(
                    model.rows[0], "after", model.codec.snapshot(np.asarray([-0.0, 2.0]))
                )
            elif drift == "row":
                replacement = stage.parent.Iteration(
                    *[getattr(model.rows[0], name) for name in model.rows[0].__dataclass_fields__]
                )
                assert replacement == model.rows[0] and replacement is not model.rows[0]
                object.__setattr__(model.trial, "iterations", (replacement, *model.rows[1:]))
            elif drift == "descriptor":
                object.__setattr__(
                    model.cache, "descriptor_json", (model.cache.descriptor_json + " ")[:-1]
                )
                assert model.cache.descriptor_json == model.api._ISSUED[interval].proofs[0][1]
            elif drift == "shape":
                model.cache.columns[0].values.shape = (1, 2)
            elif drift == "column":
                object.__setattr__(
                    model.cache.columns[0], "values", model.cache.columns[0].values.copy()
                )
            else:
                model.cache.columns[0].values.dtype = np.int64
            interval.validate_sim()
    assert caught.value.partial.invalid
    assert model.provider._ACTIVE == [] and model.api._PENDING is None
    assert model.api._FAILED[-1] is caught.value.partial


@pytest.mark.parametrize("drift", ("stable", "values", "graph", "rng", "owner_registry"))
def test_history_every_boundary_keeps_fresh_live_state_graph_RNG_and_issued_context(
    drift, monkeypatch
):
    model = _model(monkeypatch)
    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            _finish(model, interval)
            if drift == "stable":
                model.source.stable_current = NS(identity="changed")
            elif drift == "values":
                model.source.current = (model.codec.snapshot("changed"), *model.source.after[1:])
            elif drift == "graph":
                model.source.current = (
                    model.source.after[0],
                    ((), dict(changed=True)),
                    model.source.after[2],
                )
            elif drift == "rng":
                model.source.current = (
                    *model.source.after[:2],
                    (model.codec.snapshot("changed"), model.source.after[2][1]),
                )
            else:
                model.provider._ISSUED[model.owner] = NS()
            interval.validate_sim()
    assert caught.value.partial.primary is not None
    assert model.provider._ACTIVE == []


def test_history_missing_row_and_foreign_cache_are_not_successful_traversals(monkeypatch):
    model = _model(monkeypatch)
    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            interval.validate_sim(row=model.rows[0])
    assert caught.value.partial.record.status == "failed_observation"
    assert caught.value.partial.record.checked_rows == (0,)
    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            interval.validate_sim(caches=(model.codec.snapshot(np.asarray([-0.0, 2.0])),))
    assert isinstance(caught.value.partial.primary, ValueError)
    assert "actual retained" in str(caught.value.partial.primary).lower()


def test_history_capture_primary_cause_and_raw_inputs_survive_caught_callback_failure(monkeypatch):
    model = _model(monkeypatch)
    primary, cause = ValueError("capture failed"), OSError("capture cause")
    raw = dict(actual="caller metadata evidence")

    def capture(label, value):
        assert label == "row" and value is raw
        raise primary from cause

    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            with pytest.raises(ValueError) as direct:
                interval.call(capture, "row", raw, row=model.rows[0])
            assert direct.value is primary
            with pytest.raises(model.api.HistoryObservationRejected):
                interval.validate_sim(row=model.rows[1])
    context = caught.value.partial
    assert context.primary is primary and primary.__cause__ is cause
    assert context.raw_callback[1] == ("row", raw)
    assert context.callbacks[0]["error"] is primary
    assert context.full_attempts == context.full_returns == 2


def test_history_callback_reentry_is_sticky_even_when_inner_refusal_is_caught(monkeypatch):
    model = _model(monkeypatch)
    caught_inner = []
    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:

            def capture():
                try:
                    interval.validate_sim()
                except model.api.HistoryObservationRejected as error:
                    caught_inner.append(error)

            interval.call(capture, row=model.rows[0])
    assert caught.value.partial.entry_error is caught_inner[0]
    assert caught.value.__cause__ is caught_inner[0]
    assert model.events.count("full authority") == 2


def test_history_nested_factory_reentry_refuses_without_second_authority_call(monkeypatch):
    model = _model(monkeypatch)
    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            try:
                with model.api.observing_completed(model.owner, enabled=True):
                    pytest.fail("No nested interval")
            except model.api.HistoryObservationRejected:
                pass
            interval.validate_sim()
    assert caught.value.partial.invalid and model.events.count("full authority") == 2


def test_history_shared_pending_marker_blocks_actual_parent_admission_code(monkeypatch):
    model = _model(monkeypatch)
    model.provider.SimRunRejected = stage.parent.SimRunRejected
    attempts = []
    model.provider._prepare = lambda *args: attempts.append(args)
    actual_prepare = FunctionType(stage.parent.prepare.__code__, vars(model.provider))
    actual_prepare.__kwdefaults__ = dict(enabled=False)
    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            with pytest.raises(stage.parent.SimRunRejected):
                actual_prepare(object(), enabled=True)
            interval.validate_sim()
    assert attempts == [] and caught.value.partial.invalid
    assert model.provider._PREPARING is None and model.provider._ACTIVE == []


def test_history_no_token_or_record_hydration_or_foreign_row_admission(monkeypatch):
    model = _model(monkeypatch)
    token = object.__new__(model.api.CompletedHistoryObservation)
    with pytest.raises(model.api.HistoryObservationRejected):
        token.validate_sim()
    with model.api.observing_completed(model.owner, enabled=True) as interval:
        _finish(model, interval)
        with pytest.raises(TypeError):
            interval.__reduce_ex__(4)
    assert interval.record.native_or_scientific_credit == 0
    with pytest.raises(model.api.HistoryObservationRejected):
        with model.api.observing_completed(dict(record=interval.record), enabled=True):
            pytest.fail("No dictionary parent")


def test_history_sealed_SIM_source_and_public_parent_bytes_are_unchanged():
    pin = hashlib.sha256(Path(stage.parent.__file__).read_bytes()).hexdigest()
    assert pin == stage.PARENT_SHA256
    assert stage.parent.MAX_WORK == stage.MAX_OPERATIONS == 100000
    assert not stage._ISSUED and not stage.parent._ISSUED


@pytest.mark.parametrize("drift", ("method_copy", "method_code"))
def test_history_original_cache_class_dispatch_refuses_without_body_calls(drift, monkeypatch):
    entered = []
    monkeypatch.setattr(stage, "PARENT_REVIEW_SHA256", "1" * 64)
    monkeypatch.setattr(stage.parent, "_ready", lambda: entered.append("forbidden upstream"))
    function = stage._CACHE_TYPE.numeric_columns
    if drift == "method_copy":
        replacement = FunctionType(function.__code__, function.__globals__)
        monkeypatch.setattr(stage._CACHE_TYPE, "numeric_columns", replacement)
    else:

        def foreign(self):
            return {}

        monkeypatch.setattr(function, "__code__", foreign.__code__)
    with pytest.raises(stage.HistoryObservationRejected) as caught:
        stage._producer()
    assert caught.value.stage == "binding" and entered == []


@pytest.mark.parametrize("fails", (False, True))
def test_history_callback_hook_loss_restores_both_and_preserves_original_primary(
    fails, monkeypatch
):
    model = _model(monkeypatch)
    prior = sys.getprofile(), sys.gettrace()
    primary, cause = ValueError("capture source error"), OSError("capture source cause")

    def capture():
        sys.setprofile(None)
        sys.settrace(None)
        if fails:
            raise primary from cause

    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            interval.call(capture, row=model.rows[0])
    assert sys.getprofile() is prior[0] and sys.gettrace() is prior[1]
    assert caught.value.partial.final_hooks == prior
    if fails:
        assert caught.value.partial.primary is primary and primary.__cause__ is cause
    else:
        assert caught.value.partial.entry_error.stage == "hooks"


def test_history_capture_cannot_replace_equal_copied_observation_helper(monkeypatch):
    model = _model(monkeypatch)
    original = model.api._payload
    replacement = FunctionType(original.__code__, original.__globals__)

    def capture():
        model.api._payload = replacement

    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            interval.call(capture, row=model.rows[0])
    assert caught.value.partial.primary is not None
    assert "callable/code/globals" in str(caught.value.partial.primary)
    assert model.provider._ACTIVE == [] and model.provider._PREPARING is None


def test_history_body_primary_survives_independent_full_exit_failure(monkeypatch):
    model = _model(monkeypatch)
    primary, cause, secondary = (
        ValueError("original body"),
        OSError("body cause"),
        IOError("full exit failure"),
    )

    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True):
            model.source.fail_exit = secondary
            raise primary from cause
    context = caught.value.partial
    assert context.primary is primary and caught.value.__cause__ is primary
    assert primary.__cause__ is cause and any(row[1] is secondary for row in context.secondary)
    assert context.full_attempts == 2 and context.full_returns == 1


@pytest.mark.parametrize(
    "point", ("body", "restore_return", "validator_return", "authentication_return")
)
def test_history_full_exit_retarget_refuses_without_entering_foreign_validator(point, monkeypatch):
    model, foreign_calls = _model(monkeypatch), []
    original = model.provider.validate_sim
    restore_code = model.api._restore.__code__
    auth_code = model.api._exit_api.__code__
    before, changed = sys.getprofile(), []

    def foreign(owner):
        foreign_calls.append(owner)
        return model.trial

    def retarget():
        changed.append(point)
        model.provider.validate_sim = foreign
        model.source.current = (model.codec.snapshot("changed live state"), *model.source.after[1:])

    def profile(frame, event, arg):
        if before is not None:
            before(frame, event, arg)
        if event != "return" or changed:
            return
        if point == "restore_return" and frame.f_code is restore_code:
            retarget()
        elif (
            point == "validator_return"
            and frame.f_code is original.__code__
            and model.events.count("full authority") == 2
        ):
            retarget()
        elif point == "authentication_return" and frame.f_code is auth_code:
            retarget()

    try:
        sys.setprofile(profile)
        with pytest.raises(model.api.HistoryObservationRejected) as caught:
            with model.api.observing_completed(model.owner, enabled=True) as interval:
                _finish(model, interval)
                if point == "body":
                    retarget()
    finally:
        sys.setprofile(before)
    context = caught.value.partial
    assert changed == [point] and foreign_calls == []
    assert any("full-exit" in str(row[1]) for row in context.secondary)
    expected = 1 if point in ("body", "restore_return") else 2
    assert context.full_attempts == expected
    # A return observer refusal now stops delivery at that actual return,
    # before the caller counts an accepted full-exit result.
    assert context.full_returns == (
        1 if point in ("authentication_return", "validator_return") else expected
    )
    assert context.record.status == "failed_observation"
    assert model.provider._ACTIVE == [] and model.provider._PREPARING is None


@pytest.mark.parametrize("drift", ("code", "globals"))
def test_history_full_exit_authenticates_retained_executable_and_namespace(drift, monkeypatch):
    model = _model(monkeypatch)
    original = model.provider.validate_sim
    with pytest.raises(model.api.HistoryObservationRejected) as caught:
        with model.api.observing_completed(model.owner, enabled=True) as interval:
            _finish(model, interval)
            if drift == "code":
                original.__code__ = original.__code__.replace(
                    co_firstlineno=original.__code__.co_firstlineno + 1
                )
            else:
                model.provider.validate_sim = FunctionType(
                    original.__code__, dict(original.__globals__), closure=original.__closure__
                )
    assert caught.value.partial.full_attempts == 1
    assert caught.value.partial.record.status == "failed_observation"


@pytest.mark.parametrize(
    "point", ("authentication_return", "dispatch_line", "profile_entry", "trace_entry")
)
@pytest.mark.parametrize("self_restore", (False, True))
def test_history_full_exit_same_object_foreign_code_never_enters_even_if_restored(
    point, self_restore, monkeypatch, tmp_path
):
    model, foreign_calls, changed = _model(monkeypatch), [], []
    original = model.provider.validate_sim
    code, auth_code = original.__code__, model.api._exit_api.__code__
    generator_code = model.api.observing_completed.__wrapped__.__code__
    dispatch_lines = {
        index
        for index, line in enumerate(Path(stage.__file__).read_text().splitlines(), 1)
        if "result = exit_delegate(owner)" in line
    }
    before = sys.getprofile(), sys.gettrace()
    local_traces = {}
    # Match the real retained function's free-variable ABI without borrowing
    # any numerical body. A foreign frame must be refused before this append.
    free = code.co_freevars
    unit = compile(
        "def outer():\n"
        + "".join(" " + name + " = None\n" for name in free)
        + " def foreign(actual):\n"
        + "  witness.append(actual)\n"
        + "  return ("
        + ",".join(free)
        + ")\n"
        + " return foreign\n",
        "metadata_foreign_exit",
        "exec",
    )
    outer_code = next(v for v in unit.co_consts if type(v) is type(code))
    foreign_code = next(v for v in outer_code.co_consts if type(v) is type(code))
    assert foreign_code.co_freevars == free
    original.__globals__["witness"] = foreign_calls

    def substitute():
        if not changed:
            changed.append(point)
            original.__code__ = foreign_code

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if point == "authentication_return" and frame.f_code is auth_code and event == "return":
            substitute()
        elif (
            point == "profile_entry"
            and event == "call"
            and frame.f_code is code
            and frame.f_back is not None
            and frame.f_back.f_code is generator_code
        ):
            # The entry frame is already original, but mutation of the same
            # function must still refuse before its body begins.
            substitute()
        if self_restore and event == "call" and frame.f_code is foreign_code:
            original.__code__ = code

    def trace(frame, event, arg):
        fn = before[1] if event == "call" else local_traces.get(id(frame))
        if fn is not None:
            result = fn(frame, event, arg)
            if result is not None:
                local_traces[id(frame)] = result
        if event == "return":
            local_traces.pop(id(frame), None)
        if point == "dispatch_line" and frame.f_code is generator_code and event == "line":
            # Target the actual call instruction's source line, after all
            # authentication and hook installation have already completed.
            if frame.f_lineno in dispatch_lines:
                substitute()
        elif (
            point == "trace_entry"
            and frame.f_code is code
            and event == "call"
            and frame.f_back is not None
            and frame.f_back.f_code is generator_code
        ):
            substitute()
        if self_restore and frame.f_code is foreign_code and event == "call":
            original.__code__ = code
        return trace

    try:
        sys.setprofile(profile)
        sys.settrace(trace)
        with pytest.raises(model.api.HistoryObservationRejected) as caught:
            with model.api.observing_completed(model.owner, enabled=True) as interval:
                _finish(model, interval)
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
        original.__code__ = code
        original.__globals__.pop("witness", None)
    context = caught.value.partial
    assert changed == [point] and foreign_calls == []
    assert any("full-exit" in str(row[1]) for row in context.secondary)
    assert context.full_attempts == 2 and context.full_returns == 1
    assert context.record.status == "failed_observation"
    assert model.provider._ACTIVE == [] and model.provider._PREPARING is None
    assert not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "exit-call-gate.json",
        dict(
            scope="blocked metadata provider; no actual completed INIT/SIM authority",
            mutation=point,
            same_function_object=True,
            restore_requested=self_restore,
            foreign_body_entries=len(foreign_calls),
            full_attempts=context.full_attempts,
            accepted_full_returns=context.full_returns,
            status=context.record.status,
            closure_or_executable_refusal=True,
            observed_entries=[
                dict(
                    event=event,
                    actual_code=frame.f_code.co_qualname,
                    filename=frame.f_code.co_filename,
                    original_code=frame.f_code is code,
                )
                for frame, event in context.exit_entry_events
            ],
            source_native_RNG_entries=0,
            independent_biological_cases=0,
        ),
    )


def _exit_chain_model(monkeypatch):
    model = _model(monkeypatch)
    provider = model.provider
    provider._full, provider.source, provider.helper_entries = (
        provider.validate_sim,
        model.source,
        [],
    )
    # Original-shaped dispatch: validate_sim -> _authority -> _metadata ->
    # supplied helper. These are real profiled Python calls in a private
    # metadata provider, not native owner issuance or a substituted checker.
    exec(
        compile(
            "def validate_sim(actual):\n"
            " return _authority(actual).trial\n"
            "def _authority(actual):\n"
            " _leaf(actual)\n"
            " _metadata(source, 'modeled full validation', _delegated, actual)\n"
            " return source\n"
            "def _leaf(actual):\n"
            " helper_entries.append(('leaf', actual))\n"
            " return source\n"
            "def _delegated(actual):\n"
            " helper_entries.append(('delegated', actual))\n"
            " return _full(actual)\n",
            "metadata_original_exit_helper_chain",
            "exec",
        ),
        vars(provider),
    )
    model.api._EXIT_CHAIN = model.api._exit_chain(provider.validate_sim)
    return model


@pytest.mark.parametrize("observer", ("profile", "trace"))
@pytest.mark.parametrize("role", ("_authority", "_leaf", "_delegated"))
@pytest.mark.parametrize("mutation", ("slot", "code", "namespace", "cached_builtins"))
def test_history_exit_descendant_self_restoring_helper_refuses_before_foreign_body(
    observer, role, mutation, monkeypatch, tmp_path
):
    model = _exit_chain_model(monkeypatch)
    provider, foreign_calls, changed = model.provider, [], []
    original = vars(provider)[role]
    original_code, before = original.__code__, (sys.getprofile(), sys.gettrace())
    namespace = dict(vars(provider), foreign_entries=foreign_calls)
    exec(
        "def foreign(actual):\n foreign_entries.append(actual)\n return source\n",
        namespace,
    )
    foreign = namespace["foreign"]
    if mutation == "namespace":
        namespace["helper_entries"] = foreign_calls
        foreign = FunctionType(original_code, namespace)
    elif mutation == "cached_builtins":
        holder = vars(provider)
        builtins = holder["__builtins__"]
        try:
            holder["__builtins__"] = dict(original.__builtins__)
            foreign = FunctionType(original_code, holder)
        finally:
            holder["__builtins__"] = builtins
        assert foreign.__builtins__ is not original.__builtins__
    replacement_code = foreign.__code__
    trigger = (
        provider.validate_sim.__code__ if role == "_authority" else provider._authority.__code__
    )
    traces = {}
    foreign_entered = []

    def mutate(frame, event, kind):
        if event != "call":
            return
        if (
            not changed
            and kind == observer
            and frame.f_code is trigger
            and model.api._PENDING is not None
        ):
            changed.append(role)
            if mutation == "code":
                original.__code__ = replacement_code
            else:
                setattr(provider, role, foreign)
        elif changed and (
            frame.f_code is replacement_code
            and (mutation != "namespace" or frame.f_globals is namespace)
        ):
            # Actual foreign frame already exists, while every original live
            # slot/function is restored before the guard runs after this hook.
            original.__code__ = original_code
            setattr(provider, role, original)
            foreign_entered.append(frame)

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        mutate(frame, event, "profile")

    def trace(frame, event, arg):
        inherited = before[1] if event == "call" else traces.get(id(frame))
        result = None if inherited is None else inherited(frame, event, arg)
        if event == "return":
            traces.pop(id(frame), None)
        elif result is not None:
            traces[id(frame)] = result
        mutate(frame, event, "trace")
        return trace

    try:
        # The interpreter can deliver trace entry before profile entry.
        # Both hooks restore; only the selected hook makes the substitution.
        # This proves rejection of the actual foreign frame after restoration,
        # rather than an earlier still-mutated global slot.
        sys.setprofile(profile)
        sys.settrace(trace)
        inherited = sys.getprofile(), sys.gettrace()
        with pytest.raises(model.api.HistoryObservationRejected) as caught:
            with model.api.observing_completed(model.owner, enabled=True) as interval:
                _finish(model, interval)
        assert sys.getprofile() is inherited[0] and sys.gettrace() is inherited[1]
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
        original.__code__ = original_code
        setattr(provider, role, original)
    context = caught.value.partial
    software.snapshot.write_json(
        tmp_path / "exit-descendant-attempt.json",
        dict(
            observer=observer,
            role=role,
            mutation=mutation,
            changed=changed,
            foreign_frames=len(foreign_entered),
            foreign_body_entries=len(foreign_calls),
            primary=None if context.primary is None else str(context.primary),
            secondary=[(row[0], type(row[1]).__name__, str(row[1])) for row in context.secondary],
            last_helper=None
            if context.last_exit_helper is None
            else (
                context.last_exit_helper[0].f_code.co_qualname,
                context.last_exit_helper[1].f_code.co_qualname,
                context.last_exit_helper[1].f_lasti,
            ),
            full_attempts=context.full_attempts,
            accepted_full_returns=context.full_returns,
        ),
    )
    assert changed == [role] and foreign_calls == []
    assert foreign_entered
    assert model.provider.helper_entries == (
        [("leaf", model.owner)] if role == "_delegated" else []
    )
    assert context.record.status == "failed_observation"
    assert context.full_attempts == 2 and context.full_returns == 1
    assert any("full-exit" in str(row[1]) for row in context.secondary)
    assert context.last_exit_helper is not None
    assert model.events.count("full authority") == 1
    assert provider._ACTIVE == [] and provider._PREPARING is None
    assert not stage._ISSUED and not stage.parent._ISSUED
    software.snapshot.write_json(
        tmp_path / "exit-descendant-gate.json",
        dict(
            scope="synthetic issued-shape provider; actual native/RNG/INIT/SIM held",
            observer=observer,
            role=role,
            mutation=mutation,
            original_lookups_restored=vars(provider)[role] is original,
            original_code_restored=original.__code__ is original_code,
            foreign_body_entries=len(foreign_calls),
            last_actual_code=context.last_exit_helper[0].f_code.co_qualname,
            full_attempts=context.full_attempts,
            accepted_full_returns=context.full_returns,
            independent_biological_cases=0,
        ),
    )


def test_history_exit_descendant_original_chain_completes_and_counts_actual_helpers(monkeypatch):
    model = _exit_chain_model(monkeypatch)
    with model.api.observing_completed(model.owner, enabled=True) as interval:
        _finish(model, interval)
        context = model.api._ISSUED[interval]
    assert interval.record.status == "completed_observation"
    assert interval.record.full_authority_attempts == interval.record.full_authority_returns == 2
    assert model.events.count("full authority") == 2
    assert model.provider.helper_entries == [("leaf", model.owner), ("delegated", model.owner)]
    assert context.exit_helper_work[model.provider._authority] == 1
    assert context.exit_helper_work[model.provider._leaf] == 1
    assert context.exit_helper_work[model.provider._delegated] == 1


@pytest.mark.parametrize("observer", ("profile", "trace"))
def test_history_exit_descendant_refusal_keeps_body_primary_cause_and_hooks(observer, monkeypatch):
    model = _exit_chain_model(monkeypatch)
    original = model.provider._authority
    before, foreign_calls = (sys.getprofile(), sys.gettrace()), []
    primary, cause = ValueError("original history body"), OSError("original body cause")

    def foreign(actual):
        foreign_calls.append(actual)
        return model.source

    def observe(frame, event, arg):
        if event == "call" and frame.f_code is model.provider.validate_sim.__code__:
            model.provider._authority = foreign
        elif event == "call" and frame.f_code is foreign.__code__:
            model.provider._authority = original

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        observe(frame, event, arg)

    def trace(frame, event, arg):
        if before[1] is not None:
            before[1](frame, event, arg)
        observe(frame, event, arg)
        return trace

    try:
        if observer == "profile":
            sys.setprofile(profile)
        else:
            sys.settrace(trace)
        inherited = sys.getprofile(), sys.gettrace()
        with pytest.raises(model.api.HistoryObservationRejected) as caught:
            with model.api.observing_completed(model.owner, enabled=True):
                raise primary from cause
        assert sys.getprofile() is inherited[0] and sys.gettrace() is inherited[1]
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
        model.provider._authority = original
    assert caught.value.partial.primary is primary
    assert caught.value.__cause__ is primary and primary.__cause__ is cause
    assert foreign_calls == []
    assert any("full-exit" in str(row[1]) for row in caught.value.partial.secondary)


def test_history_exit_descendant_actual_source_closure_is_data_only_and_has_required_edges(
    tmp_path,
):
    bindings, _, functions, calls = stage._EXIT_CHAIN
    for function in (
        stage.parent.validate_sim,
        stage.parent._authority,
        stage.parent._validate_retained,
        stage.parent._retained_validation_sweep,
    ):
        assert functions[function][0] is function
        assert functions[function][1] is function.__code__
        assert function.__code__ in calls
    edges = (
        (stage.parent.validate_sim, stage.parent._authority),
        (stage.parent._authority, stage.parent._links),
        (stage.parent._authority, stage.parent._bindings),
        (stage.parent._validate_retained, stage.parent._retained_validation_sweep),
    )
    for caller, callee in edges:
        assert any(
            site[0] == "static" and site[1] is callee for site in calls[caller.__code__].values()
        )
    assert any(site[0] == "delegate" for sites in calls.values() for site in sites.values())
    assert not stage.parent._ISSUED and not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "actual-exit-closure-source-plan.json",
        dict(
            retained_function_bindings=len(bindings),
            caller_codes=len(calls),
            edges=[(a.__qualname__, b.__qualname__) for a, b in edges],
            actual_function_invocations=0,
            native_RNG_INIT_SIM_reference_entries=0,
            source_metadata_only=True,
        ),
    )


@pytest.mark.parametrize("observer", ("profile", "trace"))
def test_history_exit_descendant_unwind_observer_keeps_source_error_cause_and_both_hooks(
    observer, monkeypatch, tmp_path
):
    model = _exit_chain_model(monkeypatch)
    primary, cause, secondary = (
        ValueError("actual synthetic helper failure"),
        OSError("helper failure cause"),
        RuntimeError("inherited unwind observer failure"),
    )
    primary.__cause__ = cause
    model.source.fail_exit = primary
    before, traces, refused = (sys.getprofile(), sys.gettrace()), {}, []
    code = model.provider._full.__code__

    def observe(frame, event, arg):
        if event == "return" and frame.f_code is code and model.events.count("full authority") == 2:
            refused.append((frame, event, arg))
            raise secondary

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        observe(frame, event, arg)

    def trace(frame, event, arg):
        inherited = before[1] if event == "call" else traces.get(id(frame))
        result = None if inherited is None else inherited(frame, event, arg)
        if event == "return":
            traces.pop(id(frame), None)
        elif result is not None:
            traces[id(frame)] = result
        observe(frame, event, arg)
        return trace

    try:
        if observer == "profile":
            sys.setprofile(profile)
        else:
            sys.settrace(trace)
        inherited = sys.getprofile(), sys.gettrace()
        with pytest.raises(model.api.HistoryObservationRejected) as caught:
            # Set the failure only after the original entry authority returns.
            model.source.fail_exit = None
            with model.api.observing_completed(model.owner, enabled=True) as interval:
                _finish(model, interval)
                model.source.fail_exit = primary
        assert sys.getprofile() is inherited[0] and sys.gettrace() is inherited[1]
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
    context = caught.value.partial
    software.snapshot.write_json(
        tmp_path / "exit-unwind-primary.json",
        dict(
            observer=observer,
            refused_events=len(refused),
            actual_source_error_retained=any(
                row[0] == "full_exit" and row[1] is primary for row in context.secondary
            ),
            original_cause_retained=primary.__cause__ is cause,
            observer_error_retained=any(row[1] is secondary for row in context.secondary),
            secondary=[(row[0], type(row[1]).__name__, str(row[1])) for row in context.secondary],
            full_attempts=context.full_attempts,
            accepted_full_returns=context.full_returns,
            actual_native_RNG_entries=0,
        ),
    )
    assert len(refused) == 1 and refused[0][2] is None
    assert primary.__cause__ is cause
    assert any(row[0] == "full_exit" and row[1] is primary for row in context.secondary)
    assert any(row[1] is secondary for row in context.secondary)
    assert context.last_exit_source_exception[1][1] is primary
    assert context.full_attempts == 2 and context.full_returns == 1
