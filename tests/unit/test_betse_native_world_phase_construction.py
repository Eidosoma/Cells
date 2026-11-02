"""Written, unrun coordinator controls; no stand-in grants source ownership."""

import json
import os
import sys
from contextlib import contextmanager
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_world_phase_construction as stage

SOFTWARE_RELEASE = "BETSE_NATIVE_WORLD_PHASE_CONSTRUCTION_SOFTWARE_RELEASED"


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        pytest.skip("Source preparation only; no software execution released")
    prior, trace = sys.getprofile(), sys.gettrace()
    attempted = []
    forbidden = {*stage.STAGE_MODULES, stage.KEY_MODULE, stage.PARAMETER_MODULE}

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_globals.get("__name__") in forbidden
            or "/betse/" in frame.f_code.co_filename
        ):
            attempted.append((frame.f_code.co_filename, frame.f_code.co_qualname))
            raise AssertionError("Actual phase/parameter/native source entry forbidden")
        if prior is not None:
            prior(frame, event, arg)

    before = tuple(stage._ISSUED.items())
    sys.setprofile(profile)
    try:
        yield
        assert not attempted and tuple(stage._ISSUED.items()) == before
        assert sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.settrace(trace)
        sys.setprofile(prior)
        (tmp_path / "native-blocked.json").write_text(json.dumps(dict(
            nodeid=request.node.nodeid, attempted=attempted,
            source_native_or_scientific_credit=0,
        )))


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
        request=NS(world_parameters=world_token), parents=(object(), parameter_token),
        api=NS(key=NS(construction=construction)), p=parameter_token,
        stage="construction_claim_before_phase_birth", invalid=False, entry_error=None,
        primary=None, capture_error=None, capture_errors=(), claim_errors=(),
        claim=None, parameter_record=None, failed_claim=None, failed_claim_partial=None,
        failed_stages=(), stage_partials=(), evidence=[], last_returned=None,
        raw_seal=None, seal=None, trial=None, work=[], executing=None,
        driver_frame=None, step_frame=None, dispatch_ticket=None,
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
    return NS(context=context, log=log, state=claim_state, claim=claim,
              record=record, active=active, step=step, seal=seal)


def test_ordering_claim_spans_all_stages_and_fallible_sealing_before_closed_validation(monkeypatch):
    metadata = _controller(monkeypatch)
    before = tuple(stage._ISSUED.items())
    stage._coordinate(metadata.context)
    assert metadata.log == [
        "claim enter before any phase", *stage.STAGES,
        "fallible phase seal inside claim", "claim exit", "closed record",
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
    assert metadata.context.capture_errors[-1] == ("closed_parameter_record", capture, metadata.claim)


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
    primary, cause, failed, partial = FalseFailure("claim entry"), KeyError("cause"), object(), object()
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


def test_failure_envelope_retains_actual_primary_capture_and_partial_without_truthiness(monkeypatch):
    metadata = _controller(monkeypatch)
    primary, cause, capture, partial = FalseFailure("source"), KeyError("cause"), OSError("capture"), object()
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
        work=[], evidence=[], executing=None, entry_error=None, invalid=False,
        stage="metadata", request=NS(world_parameters=object(), callbacks=object()),
        claim=object(), last_returned=None, p=NS(),
        dispatch_ticket=None, driver_frame=None, step_frame=None,
        capture_errors=(), capture_error=None,
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
        work=[], evidence=[], executing=None, entry_error=None, invalid=False,
        stage="metadata", request=NS(world_parameters=object(), callbacks=object()),
        claim=object(), last_returned=None, p=NS(),
        dispatch_ticket=None, driver_frame=None, step_frame=None,
        capture_errors=(), capture_error=None,
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
