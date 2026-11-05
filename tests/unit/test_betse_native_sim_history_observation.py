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
