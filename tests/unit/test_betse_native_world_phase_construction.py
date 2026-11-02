"""Written, unrun coordinator controls; no stand-in grants source ownership."""

import ast
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_world_phase_construction as stage
from validation.betse import betse_native_world_phase_construction_software as software

SOFTWARE_RELEASE = "BETSE_NATIVE_WORLD_PHASE_CONSTRUCTION_SOFTWARE_RELEASED"
_BLOCKADE_FAILURES = ()


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        pytest.skip("Source preparation only; no software execution released")
    with _blockade(request, tmp_path):
        yield


@contextmanager
def _blockade(request, tmp_path):
    global _BLOCKADE_FAILURES
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    prior, trace = getters[0](), getters[1]()
    attempted = []
    state = software.reuse._run_state()
    state.hook_before = (prior, trace)
    state.restore_setters, state.restore_getters = setters, getters

    def profile(frame, event, arg):
        if event == "call" and software.is_forbidden_frame(frame):
            attempted.append((frame.f_code.co_filename, frame.f_code.co_qualname))
            raise AssertionError("Actual phase/parameter/native source entry forbidden")
        if prior is not None:
            prior(frame, event, arg)

    before = tuple(stage._ISSUED.items())
    try:
        setters[0](profile)
        yield state
        assert not attempted and tuple(stage._ISSUED.items()) == before
        assert getters[0]() is profile and getters[1]() is trace
        state.status = 0
    except BaseException as error:
        state.primary, state.primary_stage = error, "fixture_body_or_guard"
        raise
    finally:
        try:
            software.reuse._restore_hooks(state, (prior, trace), (profile, trace), setters, getters)
        except BaseException as error:
            state.cleanup_errors = (*state.cleanup_errors, ("fixture_restore_entry", error, None))
            for index in (1, 0):
                try:
                    setters[index]((prior, trace)[index])
                except BaseException as capture:
                    state.cleanup_errors = (
                        *state.cleanup_errors,
                        ("fixture_emergency", capture, index),
                    )
        # Receipt is independent of either restoration's success. It logs
        # attempts/partial cleanup; final identity sampling follows the writer.
        try:
            software.snapshot.write_json(
                tmp_path / "native-blocked.json",
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempted,
                    source_native_or_scientific_credit=0,
                    primary=software.reuse._error_record(state.primary),
                    secondary_cleanup=[
                        software.reuse._error_record(row[1]) for row in state.cleanup_errors
                    ],
                    final_cleanup_pending=True,
                    final_hook_restoration_claimed=False,
                ),
            )
        except BaseException as error:
            state.evidence_errors = (*state.evidence_errors, ("fixture_receipt", error, tmp_path))
        if state.primary is not None:
            try:
                state.primary.world_phase_blockade = state
            except BaseException as error:
                state.secondary = (
                    *state.secondary,
                    ("fixture_primary_attachment", error, state.primary),
                )
        try:
            software.reuse._restore_hooks(
                state,
                (prior, trace),
                (prior, trace),
                setters,
                getters,
                record_active=False,
            )
        except BaseException as error:
            state.cleanup_errors = (
                *state.cleanup_errors,
                ("fixture_final_restore_entry", error, None),
            )
            for index in (1, 0):
                try:
                    setters[index]((prior, trace)[index])
                except BaseException as capture:
                    state.cleanup_errors = (
                        *state.cleanup_errors,
                        ("fixture_final_emergency", capture, index),
                    )
        first, second = [None, None], [None, None]
        for values, order in ((first, (0, 1)), (second, (1, 0))):
            for index in order:
                try:
                    values[index] = getters[index]()
                except BaseException as error:
                    values[index] = error
                    state.cleanup_errors = (
                        *state.cleanup_errors,
                        ("fixture_final_read", error, index),
                    )
        state.hook_samples = ((first[0], first[1]), (second[0], second[1]))
        state.hook_after = state.hook_samples[-1]
        state.hooks_restored = (
            first[0] is prior and first[1] is trace and second[0] is prior and second[1] is trace
        )
        if not state.hooks_restored:
            state.cleanup_errors = (
                *state.cleanup_errors,
                ("fixture_final_identity_mismatch", None, state.hook_samples),
            )
        failed = (
            state.primary is not None
            or state.cleanup_errors
            or state.evidence_errors
            or state.secondary
            or not state.guard_active_on_cleanup
            or not state.hooks_restored
        )
        if failed:
            _BLOCKADE_FAILURES = (*_BLOCKADE_FAILURES, state)
        if state.primary is None and failed:
            raise AssertionError("Native-blocked fixture cleanup/evidence incomplete")


def test_preparation_declares_one_claim_and_no_intermediate_closed_record():
    plan = stage.source_plan()
    assert plan["mode"] == stage.MODE
    assert plan["stages"] == ("phase_prefix", "caches", "dyna", "seed_tail")
    assert plan["construction_before_any_phase_allocation"] is True
    assert plan["one_active_claim_through_all_stages"] is True
    assert plan["phase_sealing_inside_claim"] is True
    assert plan["public_closed_records_between_stages"] is False
    assert plan["key_source"] is None and plan["key_review"] is None
    assert all(value is None for value in plan["stage_sources"])


def test_preparation_unbound_contract_refuses_before_any_import(monkeypatch):
    calls = []

    def forbidden(name):
        calls.append(name)
        raise AssertionError("No unsealed producer import may supply authority")

    monkeypatch.setattr(stage.importlib, "import_module", forbidden)
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage._dependencies()
    assert caught.value.stage == "unbound_contract" and calls == []


@pytest.mark.parametrize("mode", [None, "prepared_callback_seven_load_seed_prefix", "SEED"])
def test_preparation_legacy_mode_never_relabels_a_world_owner(mode):
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage.from_world_ready(object(), object(), law_id=stage.LAW_ID, mode=mode)
    assert caught.value.stage == "law"


def test_preparation_selected_mode_is_still_gated_by_missing_real_producers():
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage.from_world_ready(object(), object(), law_id=stage.LAW_ID, mode=stage.MODE)
    assert caught.value.stage == "unbound_contract"


@pytest.mark.parametrize("enabled", [False, None, 1])
def test_preparation_release_precedes_any_claim_or_stage_hook(monkeypatch, enabled):
    monkeypatch.setenv(stage.RELEASE, "1")

    def forbidden():
        raise AssertionError("No constructor authority at source preparation")

    monkeypatch.setattr(stage, "_dependencies", forbidden)
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


def test_preparation_plain_record_and_manually_created_request_are_not_authority():
    request = stage.Request(object(), object(), "parameter", "callback", "source", stage.MODE, "id")
    assert request not in stage._REQUESTS
    with pytest.raises(TypeError):
        request.__reduce_ex__(5)
    with pytest.raises(TypeError):
        stage.WorldPhaseOwner()
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage._validate(object())
    assert caught.value.stage == "owner"


class FalseFailure(ValueError):
    def __bool__(self):
        return False


def _controller(monkeypatch):
    """Abstract ordering tokens only: no phase, real p, owner or issuer mock.

    This exercises the private coordinator's lifetime/failure plumbing. It
    never calls public prepare/from_world_ready, opens real Key permission,
    or manufactures native stage evidence. Positive source tests stay held.
    """
    log, claim_state = [], NS(active=False, closed=False, error=None, record_error=None)
    record, parameter_token, world_token = object(), object(), object()

    class MetadataClaim:
        @property
        def record(self):
            if claim_state.active or not claim_state.closed:
                raise AssertionError("No intermediate public record")
            if claim_state.record_error is not None:
                raise claim_state.record_error
            log.append("closed record")
            return record

    claim = MetadataClaim()

    @contextmanager
    def construction(owner, *, law_id, enabled):
        assert owner is world_token and law_id == stage.KEY_LAW and enabled is True
        claim_state.active = True
        log.append("claim enter before any phase")
        try:
            yield claim
        except BaseException as error:
            claim_state.error = error
            raise
        finally:
            claim_state.active, claim_state.closed = False, True
            log.append("claim exit")

    context = NS(
        request=NS(world_parameters=world_token),
        parents=(object(), parameter_token),
        api=NS(key=NS(construction=construction)),
        p=parameter_token,
        stage="construction_claim_before_phase_birth",
        invalid=False,
        entry_error=None,
        primary=None,
        capture_error=None,
        capture_errors=(),
        claim_errors=(),
        claim=None,
        parameter_record=None,
        failed_claim=None,
        failed_claim_partial=None,
        failed_stages=(),
        stage_partials=(),
        evidence=[],
        last_returned=None,
        raw_seal=None,
        seal=None,
        trial=None,
        work=[],
        executing=None,
        driver_frame=None,
        step_frame=None,
        dispatch_ticket=None,
    )

    def active(actual):
        assert actual is context and claim_state.active and actual.claim is claim
        if actual.entry_error is not None:
            raise actual.entry_error

    def step(actual, index):
        active(actual)
        assert index == len(actual.evidence)
        assert actual.dispatch_ticket == (index, actual.driver_frame)
        actual.dispatch_ticket = None
        log.append(stage.STAGES[index])
        actual.evidence.append(object())

    def seal(actual):
        active(actual)
        assert len(actual.evidence) == 4
        log.append("fallible phase seal inside claim")
        actual.raw_seal = actual.seal = object()
        actual.trial = object()  # Ordering token, never a source trial or owner.

    def closed(actual):
        assert not claim_state.active and claim_state.closed
        assert actual.claim is claim and actual.parameter_record is record
        log.append("exact closed validation")
        return record

    monkeypatch.setattr(stage, "_active_claim", active)
    monkeypatch.setattr(stage, "_step", step)
    monkeypatch.setattr(stage, "_seal_active", seal)
    monkeypatch.setattr(stage, "_check_bindings", lambda actual: None)
    monkeypatch.setattr(stage, "_closed", closed)
    return NS(
        context=context,
        log=log,
        state=claim_state,
        claim=claim,
        record=record,
        active=active,
        step=step,
        seal=seal,
    )


def test_ordering_claim_spans_all_stages_and_fallible_sealing_before_closed_validation(monkeypatch):
    metadata = _controller(monkeypatch)
    before = tuple(stage._ISSUED.items())
    stage._coordinate(metadata.context)
    assert metadata.log == [
        "claim enter before any phase",
        *stage.STAGES,
        "fallible phase seal inside claim",
        "claim exit",
        "closed record",
        "exact closed validation",
    ]
    assert metadata.context.primary is None and metadata.context.capture_error is None
    assert tuple(stage._ISSUED.items()) == before  # Private ordering is never publication.


@pytest.mark.parametrize("index", range(4))
def test_ordering_stage_failure_keeps_primary_cause_and_never_continues(monkeypatch, index):
    metadata = _controller(monkeypatch)
    primary, cause, partial = FalseFailure("original stage"), KeyError("cause"), object()
    primary.partial = partial

    def step(context, reached):
        metadata.active(context)
        if reached == index:
            context.stage = stage.STAGES[index]
            raise primary from cause
        metadata.step(context, reached)

    monkeypatch.setattr(stage, "_step", step)
    stage._coordinate(metadata.context)
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.state.error is primary
    assert len(metadata.context.evidence) == index
    assert metadata.context.stage_partials[-1] == (stage.STAGES[index], partial)
    assert "fallible phase seal inside claim" not in metadata.log
    assert "exact closed validation" not in metadata.log


def test_ordering_fallible_phase_seal_fails_inside_claim_as_capture_not_new_source(monkeypatch):
    metadata = _controller(monkeypatch)
    capture, raw = OSError("phase capture"), object()

    def seal(context):
        metadata.active(context)
        context.raw_seal = raw
        raise capture

    monkeypatch.setattr(stage, "_seal_active", seal)
    stage._coordinate(metadata.context)
    assert metadata.state.error is capture and metadata.context.raw_seal is raw
    assert metadata.context.primary is None and metadata.context.capture_error is capture
    assert metadata.context.invalid and metadata.context.trial is None
    assert "exact closed validation" not in metadata.log


def test_ordering_closed_record_failure_keeps_original_source_and_secondary_capture(monkeypatch):
    metadata = _controller(monkeypatch)
    primary, cause, capture = FalseFailure("original"), KeyError("cause"), OSError("record")
    metadata.state.record_error = capture

    def step(context, index):
        raise primary from cause

    monkeypatch.setattr(stage, "_step", step)
    stage._coordinate(metadata.context)
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.context.capture_error is capture
    assert metadata.context.capture_errors[-1] == (
        "closed_parameter_record",
        capture,
        metadata.claim,
    )


def test_ordering_closed_authentication_refusal_cannot_publish_private_seal(monkeypatch):
    metadata = _controller(monkeypatch)
    refusal = ValueError("actual closed ancestry differs")

    def closed(context):
        assert context.parameter_record is metadata.record and not metadata.state.active
        raise refusal

    monkeypatch.setattr(stage, "_closed", closed)
    before = tuple(stage._ISSUED.items())
    stage._coordinate(metadata.context)
    assert metadata.context.primary is refusal and metadata.context.seal is not None
    assert tuple(stage._ISSUED.items()) == before


def test_ordering_claim_entry_failure_retains_failed_claim_parent_and_primary(monkeypatch):
    metadata = _controller(monkeypatch)
    primary, cause, failed, partial = (
        FalseFailure("claim entry"),
        KeyError("cause"),
        object(),
        object(),
    )
    primary.world_construction_claim, primary.partial = failed, partial

    @contextmanager
    def construction(*args, **kwargs):
        raise primary from cause
        yield  # No claim was entered; required only for the metadata generator shape.

    metadata.context.api.key.construction = construction
    stage._coordinate(metadata.context)
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.context.claim is None and metadata.context.trial is None
    assert metadata.context.failed_claim is failed
    assert metadata.context.failed_claim_partial is partial
    assert metadata.context.evidence == [] and metadata.log == []


def test_ordering_claim_exit_failure_retains_in_claim_seal_without_publication(monkeypatch):
    metadata = _controller(monkeypatch)
    original = metadata.context.api.key.construction
    failure = ValueError("parameter closure rejected")

    @contextmanager
    def construction(*args, **kwargs):
        with original(*args, **kwargs) as claim:
            yield claim
        raise failure

    metadata.context.api.key.construction = construction
    before = tuple(stage._ISSUED.items())
    stage._coordinate(metadata.context)
    assert metadata.context.primary is failure
    assert metadata.context.raw_seal is metadata.context.seal
    assert metadata.context.seal is not None and metadata.context.trial is not None
    assert "exact closed validation" not in metadata.log
    assert tuple(stage._ISSUED.items()) == before


def test_failure_envelope_retains_actual_primary_capture_and_partial_without_truthiness(
    monkeypatch,
):
    metadata = _controller(monkeypatch)
    primary, cause, capture, partial = (
        FalseFailure("source"),
        KeyError("cause"),
        OSError("capture"),
        object(),
    )
    primary.__cause__ = cause
    error = NS(source_error=primary, capture_error=capture, partial=partial)
    stage._retain_failure(metadata.context, error, "actual stage")
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.context.capture_error is capture and metadata.context.invalid
    assert metadata.context.stage_partials == (("actual stage", partial),)


def test_failure_recording_rejection_keeps_original_primary_and_claim_exit(monkeypatch):
    metadata = _controller(monkeypatch)
    primary, cause, capture = FalseFailure("source"), KeyError("cause"), OSError("recorder entry")

    def step(context, index):
        raise primary from cause

    def retain(*args):
        raise capture

    monkeypatch.setattr(stage, "_step", step)
    monkeypatch.setattr(stage, "_retain_failure", retain)
    stage._coordinate(metadata.context)
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.context.capture_error is capture and metadata.state.closed
    assert metadata.context.capture_errors[-1] == ("stage_failure_recording", capture, primary)


@pytest.mark.parametrize("next_index", [0, 1])
def test_step_claim_precedes_hook_and_caught_reentry_stays_poisoned(monkeypatch, next_index):
    # Only the private stage-call controller is exercised. No real phase,
    # parameter claim, stage evidence or public child is manufactured.
    context = NS(
        work=[],
        evidence=[],
        executing=None,
        entry_error=None,
        invalid=False,
        stage="metadata",
        request=NS(world_parameters=object(), callbacks=object()),
        claim=object(),
        last_returned=None,
        p=NS(),
        dispatch_ticket=None,
        driver_frame=None,
        step_frame=None,
        capture_errors=(),
        capture_error=None,
    )
    delegates = []
    raw = object()

    def active(actual):
        if actual.entry_error is not None:
            raise actual.entry_error

    def construct(actual, **kwargs):
        delegates.append("outer only")
        with pytest.raises(stage.WorldPhaseRejected):
            stage._step(actual, next_index)
        return raw

    context.api = NS(stages=(NS(**{stage.CONSTRUCT_HOOK: construct}),))
    monkeypatch.setattr(stage, "_active_claim", active)
    monkeypatch.setattr(stage, "_check_evidence", lambda *args: None)
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        _dispatch_metadata_step(context, 0)
    assert context.entry_error is caught.value and context.invalid
    assert delegates == ["outer only"] and context.evidence == []
    assert context.last_returned is raw and len(context.work) == 2


def test_step_raw_return_precedes_any_failed_result_observation(monkeypatch):
    raw, refusal = object(), ValueError("stage evidence refused")
    context = NS(
        work=[],
        evidence=[],
        executing=None,
        entry_error=None,
        invalid=False,
        stage="metadata",
        request=NS(world_parameters=object(), callbacks=object()),
        claim=object(),
        last_returned=None,
        p=NS(),
        dispatch_ticket=None,
        driver_frame=None,
        step_frame=None,
        capture_errors=(),
        capture_error=None,
        api=NS(stages=(NS(**{stage.CONSTRUCT_HOOK: lambda *args, **kwargs: raw}),)),
    )

    def check(*args):
        assert context.last_returned is raw
        raise refusal

    monkeypatch.setattr(stage, "_active_claim", lambda actual: None)
    monkeypatch.setattr(stage, "_check_evidence", check)
    with pytest.raises(ValueError) as caught:
        _dispatch_metadata_step(context, 0)
    assert caught.value is refusal and context.last_returned is raw
    assert context.evidence == [] and context.executing is None
    assert context.work[-1]["error"] is refusal


def _dispatch_metadata_step(context, index):
    # A private control-flow ticket, never an issued parameter/source epoch.
    context.driver_frame = sys._getframe()
    context.dispatch_ticket = (index, context.driver_frame)
    return stage._step(context, index)


def _checker_controller():
    """Helper references only; this cannot produce an issued source owner."""
    counts = []

    def function(tag):
        def delegate(*args, **kwargs):
            counts.append(tag + " delegate")

        def wrapper(*args, __delegate=delegate, **kwargs):
            counts.append(tag)
            return __delegate(*args, **kwargs)

        wrapper.__wrapped__ = delegate
        wrapper._implementation = delegate
        return wrapper

    helpers = NS(
        _atoms=function("atoms"),
        literal=NS(
            _surface=function("surface"),
            _same=function("same"),
        ),
    )
    context = NS(api=NS(helpers=helpers), invalid=False, bindings=())
    context.helper_authority = stage._helper_authority(context.api)
    return context, counts


@pytest.mark.parametrize("boundary", ["active", "closed"])
@pytest.mark.parametrize("name", ["atoms", "surface", "same"])
@pytest.mark.parametrize(
    "mutation", ["replace", "code", "wrapped_code", "implementation", "keyword"]
)
def test_helper_mutation_refuses_before_any_changed_helper_or_delegate(
    monkeypatch, boundary, name, mutation
):
    context, counts = _checker_controller()
    container, attribute = (
        (context.api.helpers, "_atoms")
        if name == "atoms"
        else (context.api.helpers.literal, "_" + name)
    )
    original = getattr(container, attribute)
    delegate = original.__wrapped__
    code, delegated_code = original.__code__, delegate.__code__

    def foreign(*args, **kwargs):
        counts.append("altered helper ran")

    monkeypatch.setattr(stage, "_guard", lambda actual: None)
    monkeypatch.setattr(stage, "_same_dependencies", lambda actual: None)
    try:
        if mutation == "replace":
            setattr(container, attribute, foreign)
        elif mutation == "code":
            original.__code__ = code.replace(co_name="accepting_changed_checker")
        elif mutation == "wrapped_code":
            delegate.__code__ = delegated_code.replace(co_name="changed_wrapped_checker")
        elif mutation == "implementation":
            original._implementation = foreign
        else:
            original.__kwdefaults__["__delegate"] = foreign
            assert original.__wrapped__ is delegate and original.__code__ is code
        with pytest.raises(ValueError, match="helper"):
            if boundary == "active":
                stage._check_bindings(context)
            else:
                with stage._validation_scope(object(), context):
                    stage._compare_bindings(context)
        assert counts == []
        assert stage._VALIDATION.current is None
    finally:
        original.__code__, delegate.__code__ = code, delegated_code


def test_unchanged_helper_bootstrap_does_not_invoke_any_comparator_or_atom_helper():
    context, counts = _checker_controller()
    stage._check_helpers(context)
    assert counts == []


def test_original_global_atom_delegate_is_authenticated_without_calling_it(monkeypatch):
    context, counts = _checker_controller()
    namespace = dict(aliases=NS(_atoms=lambda value: counts.append("old atoms")))
    exec("def helper(*args):\n    return aliases._atoms(args)\n", namespace)
    context.api.helpers._atoms = namespace["helper"]
    context.helper_authority = stage._helper_authority(context.api)

    def altered(value):
        counts.append("changed atoms")

    monkeypatch.setattr(namespace["aliases"], "_atoms", altered)
    with pytest.raises(ValueError, match="helper"):
        stage._compare_bindings(context)
    assert counts == []


@pytest.mark.parametrize("boundary", ["pre_key", "post_key"])
@pytest.mark.parametrize("entry", ["owner_read", "prepare", "declare"])
def test_validation_reservation_is_sticky_before_and_after_parameter_checker(
    monkeypatch, boundary, entry
):
    # A private reservation on metadata tokens, never a fabricated source owner.
    context = NS(invalid=False)
    owner, log = object(), []

    def recursive():
        with pytest.raises(stage.WorldPhaseRejected):
            if entry == "owner_read":
                with stage._validation_scope(owner, context):
                    log.append("forbidden recursive body")
            elif entry == "prepare":
                stage.prepare(None, enabled=False)
            else:
                stage.from_world_ready(None, None, law_id=stage.LAW_ID, mode=stage.MODE)

    def compare(actual):
        if boundary == "pre_key":
            recursive()

    def key_check(*args, **kwargs):
        log.append("Key metadata checker")
        if boundary == "post_key":
            recursive()
        return object()  # Refusal must precede any interpretation of this token.

    context.api = NS(key=NS(validate_closed_seed=key_check))
    context.request, context.claim = NS(world_parameters=object()), object()
    monkeypatch.setattr(stage, "_closed_lineage", lambda actual: None)
    monkeypatch.setattr(stage, "_same_dependencies", lambda actual: None)
    monkeypatch.setattr(stage, "_compare_bindings", compare)
    monkeypatch.setattr(stage, "_check_evidence", lambda *args, **kwargs: log.append("late stage"))
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        with stage._validation_scope(owner, context) as reservation:
            stage._validate_reserved(context, reservation)
    assert caught.value is reservation.rejection
    assert context.invalid and reservation.attempts
    assert log == ([] if boundary == "pre_key" else ["Key metadata checker"])
    assert stage._VALIDATION.current is None and reservation.active is False
    assert context.validation_failures[-1] is reservation


@pytest.mark.parametrize("has_primary", [False, True])
def test_validation_release_rejection_retains_primary_and_retires_exact_scope(
    monkeypatch, has_primary
):
    context, owner = NS(invalid=False), object()
    primary, cause, capture = (
        FalseFailure("original checker"),
        KeyError("cause"),
        OSError("release"),
    )

    def reject(reservation):
        raise capture

    monkeypatch.setattr(stage, "_release_validation", reject)
    expected = FalseFailure if has_primary else stage.WorldPhaseRejected
    with pytest.raises(expected) as caught:
        with stage._validation_scope(owner, context) as reservation:
            if has_primary:
                raise primary from cause
    if has_primary:
        assert caught.value is primary and primary.__cause__ is cause
    else:
        assert caught.value.capture_error is capture
    assert reservation.cleanup_errors == (capture,)
    assert context.validation_failures[-1] is reservation
    assert stage._VALIDATION.current is None and reservation.active is False


def test_reserved_source_failure_cleans_scope_without_reopening_any_claim():
    context, owner = NS(invalid=False), object()
    primary, cause = FalseFailure("post-Key failure"), LookupError("cause")
    with pytest.raises(FalseFailure) as caught:
        with stage._validation_scope(owner, context) as reservation:
            raise primary from cause
    assert caught.value is primary and primary.__cause__ is cause
    assert reservation.primary is primary and not reservation.cleanup_errors
    assert stage._VALIDATION.current is None


def test_actual_validation_reports_callback_is_allowed_by_exact_native_guard(tmp_path):
    directory = tmp_path / "allowed_callback"
    directory.mkdir()
    request = NS(node=NS(nodeid="metadata::actual_reports_callback"))
    state = software.reuse._run_state()
    plugin = software.Reports(directory, state, "", [])
    call = NS(excinfo=None, when="call")
    with _blockade(request, directory):
        plugin.pytest_runtest_makereport(None, call)
        plugin.pytest_runtest_logreport(
            NS(
                skipped=False,
                nodeid="metadata::report",
                when="call",
                outcome="passed",
                duration=0.0,
                longrepr="",
            )
        )
    assert not state.evidence_errors and state.primary is None
    assert len(list((directory / "reports").iterdir())) == 1
    receipt = directory / "native-blocked.json"
    saved = json.loads(receipt.read_text())
    assert saved["nodeid"] == "metadata::actual_reports_callback"
    assert saved["attempted"] == []
    receipt.rename(directory / "callback-control-guard.json")


@pytest.mark.parametrize("policy", ["native_path", "forbidden_module", "misleading_path"])
def test_exact_guard_distinguishes_native_root_from_metadata_labels(tmp_path, policy):
    directory = tmp_path / policy
    directory.mkdir()
    request = NS(node=NS(nodeid="metadata::exact_guard::" + policy))
    filename = {
        "native_path": software.NATIVE_ROOT + "/betse/controlled_guard_probe.py",
        "forbidden_module": "/tmp/metadata_only.py",
        "misleading_path": "/tmp/project/validation/betse/metadata_only.py",
    }[policy]
    calls = []
    namespace = dict(
        calls=calls,
        __name__=(
            "betse.science.cells"
            if policy == "forbidden_module"
            else "validation.betse.metadata_probe"
        ),
    )
    module_code = compile("def probe():\n    calls.append('body')\n", filename, "exec")
    function_code = next(value for value in module_code.co_consts if type(value) is CodeType)
    probe = FunctionType(function_code, namespace)
    if policy == "misleading_path":
        with _blockade(request, directory):
            probe()
        assert calls == ["body"]
    else:
        with pytest.raises(AssertionError, match="entry forbidden"):
            with _blockade(request, directory):
                probe()
        assert calls == []
    # These nested generated-code controls are not ordinary per-case source
    # guard receipts. Validate their exact known attempt before classifying;
    # an unknown attempt stays an ordinary receipt and fails this test.
    receipt = directory / "native-blocked.json"
    saved = json.loads(receipt.read_text())
    expected_attempts = [] if policy == "misleading_path" else [[filename, "probe"]]
    assert saved["attempted"] == expected_attempts
    assert saved["nodeid"] == "metadata::exact_guard::" + policy
    assert saved["source_native_or_scientific_credit"] == 0
    receipt = receipt.rename(
        directory
        / (
            "policy-control-guard.json"
            if policy == "misleading_path"
            else "synthetic-policy-attempt.json"
        )
    )
    (directory / "policy-classification.json").write_text(
        json.dumps(
            dict(
                generated_metadata_code=True,
                policy=policy,
                original_native_body_loaded_or_executed=False,
                delegate_calls=calls,
                guard_attempt_receipt=receipt.name,
                expected_attempts=0 if policy == "misleading_path" else 1,
            )
        )
    )


@pytest.mark.parametrize("primary_kind", ["none", "normal", "falsey"])
@pytest.mark.parametrize("failure", ["trace", "profile", "receipt", "all"])
def test_fixture_cleanup_receipt_failures_preserve_primary_and_attempt_both_hooks(
    monkeypatch, tmp_path, primary_kind, failure
):
    directory = tmp_path / "cleanup"
    directory.mkdir()
    request = NS(node=NS(nodeid="metadata::fixture_cleanup"))
    getters, setters = (sys.getprofile, sys.gettrace), (sys.setprofile, sys.settrace)
    before = (getters[0](), getters[1]())
    primary = (
        None
        if primary_kind == "none"
        else (
            FalseFailure("falsey original") if primary_kind == "falsey" else ValueError("original")
        )
    )
    cause, capture = KeyError("original cause"), OSError("cleanup observer")
    attempted, once = [], set()
    original_writer = software.snapshot.write_json

    def setter(index, value):
        if value is before[index]:
            attempted.append(index)
            name = ("profile", "trace")[index]
            if failure in (name, "all") and index not in once:
                once.add(index)
                raise capture
        setters[index](value)

    def writer(path, value):
        if failure in ("receipt", "all") and path.parent == directory:
            raise capture
        original_writer(path, value)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "setprofile", lambda value: setter(0, value))
            patch.setattr(sys, "settrace", lambda value: setter(1, value))
            patch.setattr(software.snapshot, "write_json", writer)
            expected = AssertionError if primary is None else type(primary)
            with pytest.raises(expected) as caught:
                with _blockade(request, directory) as state:
                    if primary is not None:
                        raise primary from cause
        if primary is not None:
            assert caught.value is primary and primary.__cause__ is cause
            assert primary.world_phase_blockade is state
        assert 0 in attempted and 1 in attempted
        assert state.hooks_restored is True
        assert state.cleanup_errors or state.evidence_errors
        assert getters[0]() is before[0] and getters[1]() is before[1]
        receipt = directory / "native-blocked.json"
        if failure not in ("receipt", "all"):
            saved = json.loads(receipt.read_text())
            assert saved["nodeid"] == "metadata::fixture_cleanup"
            assert saved["attempted"] == []
            receipt.rename(directory / "cleanup-control-guard.json")
        else:
            assert not receipt.exists()
        (directory / "cleanup-classification.json").write_text(
            json.dumps(
                dict(
                    metadata_cleanup_control=True,
                    primary_kind=primary_kind,
                    injected_failure=failure,
                    original_primary_preserved=(primary is None or caught.value is primary),
                    final_hooks_restored=state.hooks_restored,
                    cleanup_or_capture_errors_retained=True,
                    native_source_credit=0,
                )
            )
        )
    finally:
        setters[1](before[1])
        setters[0](before[0])


@pytest.mark.parametrize("boundary", ["active", "closed"])
@pytest.mark.parametrize("shadow", ["len", "any", "zip", "ValueError"])
def test_residual_resolved_comparator_shadow_refuses_equal_length_drift(
    monkeypatch, boundary, shadow
):
    context, calls = _checker_controller()
    namespace = {"__name__": "metadata_comparator"}
    exec(
        "def compare(actual, retained):\n"
        "    if len(actual) != len(retained) or any(\n"
        "        a is not b for a,b in zip(actual,retained,strict=True)):\n"
        "        raise ValueError('binding drift')\n",
        namespace,
    )
    comparator = namespace["compare"]
    context.api.helpers.literal._same = comparator
    context.helper_authority = stage._helper_authority(context.api)
    old_code, old_namespace = comparator.__code__, comparator.__globals__
    context.bindings = (object(), object())
    changed = (context.bindings[0], object())

    def accepting(*args, **kwargs):
        calls.append("changed resolved comparator dependency")
        return False

    namespace[shadow] = accepting
    monkeypatch.setattr(stage, "_bindings", lambda actual: changed)
    monkeypatch.setattr(stage, "_guard", lambda actual: None)
    monkeypatch.setattr(stage, "_same_dependencies", lambda actual: None)
    assert comparator.__code__ is old_code and comparator.__globals__ is old_namespace
    assert len(changed) == len(context.bindings)
    with pytest.raises(ValueError, match="helper"):
        if boundary == "active":
            stage._check_bindings(context)
        else:
            with stage._validation_scope(object(), context):
                stage._compare_bindings(context)
    assert calls == [] and stage._VALIDATION.current is None


def test_residual_independent_binding_comparison_precedes_accepting_checker(monkeypatch):
    calls = []

    def accepting(*args):
        calls.append("accepting comparator")

    retained = (object(), object())
    context = NS(bindings=retained, api=NS(helpers=NS(literal=NS(_same=accepting))))
    monkeypatch.setattr(stage, "_check_helpers", lambda actual: None)
    monkeypatch.setattr(stage, "_bindings", lambda actual: (retained[0], object()))
    with pytest.raises(ValueError, match="Independent coordinator"):
        stage._compare_bindings(context)
    assert calls == []


@pytest.mark.parametrize("entry", ["prepare", "owner_read"])
@pytest.mark.parametrize("has_primary", [False, True])
def test_residual_release_entry_reentry_cannot_return_poisoned_authority(entry, has_primary):
    context, owner, later = NS(invalid=False), object(), []
    primary, cause = FalseFailure("original validation"), KeyError("cause")
    prior, trace = sys.getprofile(), sys.gettrace()
    release_code = stage._release_validation.__code__
    attempted = []

    def observer(frame, event, arg):
        if event == "call" and frame.f_code is release_code and not attempted:
            attempted.append("release entry")
            with pytest.raises(stage.WorldPhaseRejected):
                if entry == "prepare":
                    stage.prepare(None, enabled=False)
                else:
                    with stage._validation_scope(owner, context):
                        later.append("recursive body must not run")
        if prior is not None:
            prior(frame, event, arg)

    try:
        sys.setprofile(observer)
        expected = FalseFailure if has_primary else stage.WorldPhaseRejected
        with pytest.raises(expected) as caught:
            with stage._validation_scope(owner, context) as reservation:
                if has_primary:
                    raise primary from cause
            later.append("poisoned read returned")
        if has_primary:
            assert caught.value is primary and primary.__cause__ is cause
        else:
            assert caught.value is reservation.rejection
        assert context.invalid and reservation.attempts and attempted == ["release entry"]
        assert later == [] and stage._VALIDATION.current is None and not reservation.active
        assert context.validation_failures[-1] is reservation
    finally:
        sys.settrace(trace)
        sys.setprofile(prior)


def test_residual_reservation_return_observer_failure_retires_its_published_token():
    context, owner, yielded = NS(invalid=False), object(), []
    original, cause = FalseFailure("reservation return observer"), KeyError("original cause")
    prior, trace = sys.getprofile(), sys.gettrace()
    reserve_code = stage._reserve_validation.__code__
    attempts = []

    def observer(frame, event, arg):
        if event == "return" and frame.f_code is reserve_code and not attempts:
            assert stage._VALIDATION.current is arg
            attempts.append(arg)
            raise original from cause
        if prior is not None:
            prior(frame, event, arg)

    try:
        sys.setprofile(observer)
        with pytest.raises(FalseFailure) as caught:
            with stage._validation_scope(owner, context):
                yielded.append("must never yield")
        assert caught.value is original and original.__cause__ is cause
        reservation = attempts[0]
        assert context.last_validation is reservation and reservation.primary is original
        assert not reservation.active and stage._VALIDATION.current is None and not yielded
        assert context.validation_failures[-1] is reservation
    finally:
        sys.settrace(trace)
        sys.setprofile(prior)


def test_residual_failed_reservation_does_not_retire_another_acquisition(monkeypatch):
    context, owner, foreign = NS(invalid=False), object(), NS(acquisition=object())
    original = FalseFailure("failed before own token returned")

    def reserve(actual_owner, actual_context, *, acquisition):
        stage._VALIDATION.current = foreign
        raise original

    monkeypatch.setattr(stage, "_reserve_validation", reserve)
    try:
        with pytest.raises(FalseFailure) as caught:
            with stage._validation_scope(owner, context):
                raise AssertionError("no body after failed acquisition")
        assert caught.value is original and stage._VALIDATION.current is foreign
    finally:
        stage._VALIDATION.current = None


def _world_integration_tree(module):
    path = software.ROOT / ("src/" + module.replace(".", "/") + ".py")
    return ast.parse(path.read_bytes())


def test_world_integration_declares_explicit_fresh_mode_without_provider_adoption():
    plan = stage.source_plan()
    assert plan["mode"] == "fresh_world_ready_prephase_single_claim_seed_constructor"
    assert plan["private_same_claim_stage_hooks_implemented"] is True
    assert plan["exact_same_instance_seed_and_world_dispatch_prepared"] is True
    assert plan["public_closed_records_between_stages"] is False
    assert plan["helper_source"] is None
    assert plan["key_source"] is None and plan["parameter_source"] is None
    assert plan["stage_sources"] == plan["stage_reviews"] == (None,) * 4
    assert plan["source_native_scientific_release"] is False


@pytest.mark.parametrize("index", range(4))
def test_world_integration_source_hooks_keep_one_actual_claim_and_exact_surface(index):
    tree = _world_integration_tree(stage.STAGE_MODULES[index])
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    construct = functions[stage.CONSTRUCT_HOOK]
    check = functions[stage.CHECK_HOOK]
    assert [v.arg for v in construct.args.args] == ["transition"]
    assert [v.arg for v in construct.args.kwonlyargs] == [
        "world_owner",
        "construction_claim",
        "callback_owner",
        "predecessor",
    ]
    assert [v.arg for v in check.args.kwonlyargs] == [
        "transition",
        "world_owner",
        "construction_claim",
        "predecessor",
        "closed_record",
    ]
    starts = [
        node
        for node in ast.walk(construct)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_world_stage_begin"
    ]
    assert len(starts) == 1 and ast.literal_eval(starts[0].args[1]) == index
    # Only the coordinator may enter construction. There is no new legacy
    # Lease/d9/47 claim and no closure/record synthesized between stages.
    forbidden = {"construction", "continuation", "seed_tail", "inspection", "_claim"}
    assert not any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in forbidden)
            or (isinstance(node.func, ast.Attribute) and node.func.attr in forbidden)
        )
        for node in ast.walk(construct)
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_world_stage_finish"
        for node in ast.walk(construct)
    )
    if index < 2:
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_world_body_scope"
            for node in ast.walk(construct)
        )
        assert any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute) and target.attr == "driver_frame"
                for target in node.targets
            )
            for node in ast.walk(construct)
        )


def test_world_integration_execution_closure_explicitly_selects_all_eight_paths():
    expected = {
        "src/cells/processes/betse_native_phase_assembly.py",
        "src/cells/processes/betse_native_phase_caches.py",
        "src/cells/processes/betse_native_phase_dyna.py",
        "src/cells/processes/betse_native_phase_tail.py",
        "src/cells/processes/betse_native_seed_world_prefix.py",
        software.SOURCE,
        software.TEST,
        software.FILE,
    }
    assert len(software.OWNED) == 8 and set(software.OWNED) == expected
    assert "cells.processes.betse_native_seed_world_prefix_source" in software.FORBIDDEN_MODULES


@pytest.mark.parametrize("entry", ["request", "prepare", "private_stage"])
def test_world_integration_unbound_gate_precedes_any_claim_or_foreign_object_inspection(
    monkeypatch, entry
):
    class Unavailable:
        def __getattribute__(self, name):
            raise AssertionError("An unadopted predecessor must not be inspected")

    unavailable = Unavailable()
    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        if entry == "request":
            stage.from_world_ready(unavailable, unavailable, law_id=stage.LAW_ID, mode=stage.MODE)
        elif entry == "prepare":
            stage.prepare(unavailable, enabled=True)
        else:
            stage._world_stage_begin(
                None, 0, unavailable, unavailable, unavailable, unavailable, unavailable, None
            )
    assert caught.value.stage == "unbound_contract"
    assert not stage._ACTIVE and not stage._ISSUED


@pytest.mark.parametrize("captured", [False, True])
def test_world_integration_failed_stage_retains_entry_primary_and_capture_separately(captured):
    # Private failure-flow metadata only: no owner, p, source class or claim
    # is fabricated, issued or accepted by these controls.
    original, cause = FalseFailure("original entry rejection"), KeyError("original cause")
    try:
        raise original from cause
    except FalseFailure:
        pass
    capture = OSError("observation") if captured else None
    transition = NS(invalid=False, entry_error=None)
    module = NS(_ACTIVE=[])
    context = NS(
        world_transition=transition,
        world_module=module,
        entry_error=original,
        observation_error=capture,
        primary=None,
        invalid=False,
        active=True,
        stage="metadata_only_failed_stage",
    )
    module._ACTIVE.append(context)
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage._world_stage_finish(context, primary=None)
    assert caught.value.source_error is original and original.__cause__ is cause
    assert caught.value.capture_error is capture and caught.value.partial is context
    assert transition.entry_error is original and context.primary is original
    assert not context.active and context.invalid and not module._ACTIVE
    assert not stage._ISSUED


def test_world_integration_prepares_only_exact_same_instance_phase_world_dispatch():
    assembly = _world_integration_tree(stage.STAGE_MODULES[0])
    tail = _world_integration_tree(stage.STAGE_MODULES[-1])
    helpers = _world_integration_tree(stage.HELPER_MODULE)
    tail_functions = {node.name for node in tail.body if isinstance(node, ast.FunctionDef)}
    assert {
        "_claim_for_seed_world",
        "_check_world_authority",
        "_dispatch_seed_world",
    } <= tail_functions
    assert {stage.SEAL_HOOK, stage.CHECK_SEAL_HOOK} <= tail_functions
    parent = next(
        node
        for node in helpers.body
        if isinstance(node, ast.FunctionDef) and node.name == "_world_parent"
    )
    assert "WorldPhaseOwner" in ast.unparse(parent)
    assert "PhaseTailOwner" not in ast.unparse(parent)
    # No phase class or per-instance method replacement is an integration tool.
    for tree in (assembly, tail, helpers):
        assert not any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute) and target.attr == "__class__"
                for target in node.targets
            )
            for node in ast.walk(tree)
        )


def _field_epoch_metadata():
    """Private code seams only: no Request, claim, issued parent or native body.

    The real seal/check code runs against field witnesses with authentication
    and capture replaced by explicit metadata seams. This proves the field
    transition, not that any genuine producer or phase has been admitted.
    """
    callback, cells, kind, cache, handler, export = (object() for _ in range(6))
    p, sim = NS(init_export_dirname=export, _run_sim=False), NS(dyna=handler)
    phase = NS(
        callbacks=callback,
        cells=cells,
        kind=kind,
        p=p,
        sim=sim,
        cache=cache,
        dyna=handler,
        export_dirname=export,
    )
    authority = NS()
    evidence = [
        stage.StageEvidence(
            name,
            authority,
            phase,
            p,
            cells,
            sim,
            callback,
            kind,
            None if index == 0 else cache,
            None if index < 2 else handler,
            "metadata trial " + name,
            (),
            str(index),
        )
        for index, name in enumerate(stage.STAGES)
    ]
    checks = []
    context = NS(
        request=NS(world_parameters=object(), identity="metadata request"),
        claim=object(),
        p=p,
        parents=(None, p, None, callback),
        evidence=evidence,
        executing=None,
        parameter_record=None,
        work=[],
        stage="before metadata seal",
        metadata_authenticated=True,
    )

    def authenticate(actual):
        assert actual is context and actual.parameter_record is None
        if not actual.metadata_authenticated:
            raise ValueError("Metadata authentication seam refused")
        checks.append("active metadata seam; no closed record")

    def issued_witness(actual, **kwargs):
        assert kwargs["closed_record"] is None
        assert kwargs["transition"] is context
        checks.append(actual.stage)
        return actual

    namespace = dict(vars(stage))
    namespace.update(
        __name__=__name__,
        _ready=lambda: None,
        _active_claim=authenticate,
        _guard=authenticate,
        _world_parameter_authority=authenticate,
        _world_state=lambda actual: (NS(identity="metadata cache"), ((), ())),
        _bindings=lambda actual: (),
    )
    for name in ("_seal_active", "_world_seal", "_check_evidence"):
        original = getattr(stage, name)
        fn = FunctionType(original.__code__, namespace, name, original.__defaults__)
        fn.__kwdefaults__ = dict(original.__kwdefaults__ or {})
        namespace[name] = fn

    def seal_hook(actual, *, transition, world_owner, construction_claim, stages):
        return namespace["_world_seal"](actual, transition, world_owner, construction_claim, stages)

    context.api = NS(stages=tuple(NS(_world_phase_check=issued_witness) for _ in stage.STAGES))
    context.api.stages[-1]._world_phase_seal = seal_hook
    context.api.stages[-1]._world_phase_check_seal = lambda actual, **kwargs: actual
    return context, namespace, checks


def test_interface_final_in_claim_seal_accepts_historical_witnesses_without_closed_record():
    context, code, checks = _field_epoch_metadata()
    before = tuple(stage._ISSUED.items())
    code["_seal_active"](context)
    assert type(context.seal) is stage.PhaseSeal and type(context.trial) is stage.Trial
    assert context.seal.stages == tuple(context.evidence)
    assert context.parameter_record is None and context.p._run_sim is False
    assert [name for name in checks if name in stage.STAGES] == list(stage.STAGES)
    assert tuple(stage._ISSUED.items()) == before


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("premature", ["later_fields", "seed_flag"])
def test_interface_immediate_epoch_still_refuses_premature_fields_and_seed_flag(index, premature):
    context, code, _ = _field_epoch_metadata()
    if premature == "seed_flag":
        allowed = stage._evidence_fields(index)
        for name in tuple(vars(context.evidence[index].phase)):
            if name not in allowed:
                delattr(context.evidence[index].phase, name)
    with pytest.raises(ValueError, match="field order|before its literal tail"):
        code["_check_evidence"](context, context.evidence[index], index)


@pytest.mark.parametrize("index", range(4))
def test_interface_unchanged_immediate_epoch_keeps_original_stage_semantics(index):
    context, code, _ = _field_epoch_metadata()
    for name in tuple(vars(context.evidence[index].phase)):
        if name not in stage._evidence_fields(index):
            delattr(context.evidence[index].phase, name)
    if index < 3:
        del context.p._run_sim
    assert (
        code["_check_evidence"](context, context.evidence[index], index) is context.evidence[index]
    )


@pytest.mark.parametrize("change", ["extra", "flag", "cache", "handler", "callback", "auth"])
def test_interface_final_in_claim_epoch_keeps_exact_fields_aliases_and_flag(change):
    context, code, _ = _field_epoch_metadata()
    if change == "extra":
        context.evidence[0].phase.extra = None
    elif change == "flag":
        context.p._run_sim = True
    elif change == "cache":
        context.evidence[0].phase.cache = object()
    elif change == "handler":
        context.evidence[0].sim.dyna = object()
    elif change == "callback":
        context.evidence[0].phase.callbacks = object()
    else:
        context.metadata_authenticated = False
    with pytest.raises(ValueError):
        code["_seal_active"](context)
    assert not hasattr(context, "seal") and context.parameter_record is None


def test_interface_completed_active_flag_cannot_authorize_an_outside_check():
    context, code, checks = _field_epoch_metadata()
    context.stage = "phase_sealing_inside_claim"
    with pytest.raises(ValueError, match="reserved for the actual full-phase seal"):
        code["_check_evidence"](context, context.evidence[0], 0, final_active=True)
    assert not checks and context.parameter_record is None


def _helper_image(source=None, review=None, *, extra=b""):
    return (
        ("CONSTRUCTION_SOURCE_SHA256 = " + repr(source) + "\n").encode()
        + ("CONSTRUCTION_REVIEW_SHA256 = " + repr(review) + "\n").encode()
        + b"OTHER = 3\ndef helper():\n    return OTHER\n"
        + extra
    )


def test_interface_binding_topology_adopts_two_unequal_images_without_a_hash_fixed_point():
    unbound = _helper_image()
    interface, _ = stage._helper_binding(unbound)
    constructors = [
        (
            "HELPER_INTERFACE_SHA256 = "
            + repr(interface)
            + "\nHELPER_CONSTRUCTION_REVIEW_SHA256 = "
            + repr("a" * 64)
            + "\nREVISION = "
            + repr(value)
        ).encode()
        for value in ("first independent image", "second independent image")
    ]
    assert constructors[0] != constructors[1]
    bound_helpers = []
    for constructor in constructors:
        image = _helper_image(hashlib.sha256(constructor).hexdigest(), "a" * 64)
        actual, backrefs = stage._helper_binding(image)
        assert image != unbound and actual == interface
        stage._check_helper_backrefs(backrefs, constructor, "a" * 64)
        bound_helpers.append(image)
        with pytest.raises(ValueError, match="full constructor"):
            stage._check_helper_backrefs(
                backrefs, constructor + b"\n# exact byte drift\n", "a" * 64
            )
        with pytest.raises(ValueError, match="source/review"):
            stage._check_helper_backrefs(backrefs, constructor, "b" * 64)
    assert bound_helpers[0] != bound_helpers[1]
    assert stage.source_plan()["helper_interface"] is None
    assert stage.source_plan()["helper_constructor_review"] is None
    assert stage.source_plan()["helper_non_back_reference_bytes_exact"] is True


@pytest.mark.parametrize(
    "change",
    [
        lambda image: image.replace(b"return OTHER", b"return OTHER + 1"),
        lambda image: image.replace(b"OTHER = 3", b"OTHER = 4"),
        lambda image: image + b"# comment byte drift\n",
        lambda image: image.replace(b"    return OTHER", b"  return OTHER"),
        lambda image: image.replace(b"\n", b"\r\n"),
    ],
    ids=["body", "constant", "comment", "whitespace", "line_endings"],
)
def test_interface_helper_binding_preserves_every_non_back_reference_source_byte(change):
    original = _helper_image()
    baseline, _ = stage._helper_binding(original)
    changed = change(original)
    assert changed != original and stage._helper_binding(changed)[0] != baseline


@pytest.mark.parametrize(
    "image",
    [
        b"CONSTRUCTION_SOURCE_SHA256 = None\n",
        _helper_image() + b"CONSTRUCTION_REVIEW_SHA256 = None\n",
        _helper_image().replace(b"CONSTRUCTION_SOURCE_SHA256 = None", b"X = None"),
        _helper_image().replace(b"= None", b"= str(None)", 1),
        _helper_image().replace(b"= None", b"= 'not a pin'", 1),
        _helper_image().replace(b"= None", b"= r'" + b"a" * 64 + b"'", 1),
    ],
    ids=["missing", "duplicate", "renamed", "expression", "invalid_pin", "prefixed_literal"],
)
def test_interface_helper_binding_refuses_ambiguous_or_nonliteral_back_reference_slots(image):
    with pytest.raises(ValueError):
        stage._helper_binding(image)


@pytest.mark.parametrize("review", [None, "wrong", "A" * 64])
def test_interface_valid_constructor_bytes_do_not_substitute_for_a_review_binding(review):
    constructor = b"independent full constructor bytes"
    _, slots = stage._helper_binding(_helper_image(hashlib.sha256(constructor).hexdigest(), None))
    invalid = (slots[0], (slots[1][0], review))
    with pytest.raises(ValueError, match="source/review"):
        stage._check_helper_backrefs(invalid, constructor, "a" * 64)
