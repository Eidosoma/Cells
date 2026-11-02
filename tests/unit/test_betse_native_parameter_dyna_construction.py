"""Conditional same-p claims only; no native constructor or numeric work."""

import pickle
import sys
from dataclasses import replace

import pytest

from cells.processes import betse_native_parameter_dyna_construction as stage
from tests.unit import test_betse_native_parameter_construction_lease as earlier
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

previous = stage.previous
blocked = earlier.blocked


@pytest.fixture(scope="module")
def plan():
    return earlier.numeric.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, plan):
    h = earlier.controlled.__wrapped__(monkeypatch, tmp_path, plan)
    monkeypatch.setenv(stage.RELEASE, "1")
    with earlier.construct(h.parent_owner) as original:
        assert original.parameters is h.p
        original.check()
    h.original = original
    h.original_context = previous._ISSUED[original]
    h.original_record = original.record
    assert original.record.succeeded and previous._CONSTRUCTED[h.parent_owner] is True
    return h


def acquire(lease, **changes):
    return stage.continuation(
        lease, **dict(law_id=stage.PHASE_DYNA_CONSTRUCTION_LAW, enabled=True, **changes)
    )


def empty():
    earlier.empty()
    assert not stage._ACTIVE
    assert stage._LOCK.acquire(blocking=False)
    stage._LOCK.release()


def test_exact_closed_source_producer_and_non_admission():
    p = stage.source_plan()
    assert (
        p["predecessor"]
        == stage.PREVIOUS_SHA256
        == ("5e942391adc112382e6bc38dcf252f5f615d22ef2f98dbdaa6c00484cdb89ff4")
    )
    assert p["parameter_producer"] == previous.PARENT_SHA256
    assert not p["source_constructor_or_numeric_execution"]
    assert not p["construction_marker_rearmed"]
    assert not p["successful_claim_is_TissueHandler_or_phase_or_INIT_admission"]


@pytest.mark.parametrize("gate", ["enabled", "integer-enabled", "local", "lease", "parameter"])
def test_gates_refuse_before_predecessor_lookup(monkeypatch, gate):
    for name in (stage.RELEASE, previous.RELEASE, stage.parameters.RELEASE):
        monkeypatch.setenv(name, "1")
    enabled = False if gate == "enabled" else 1 if gate == "integer-enabled" else True
    if gate not in ("enabled", "integer-enabled"):
        monkeypatch.setenv(
            {
                "local": stage.RELEASE,
                "lease": previous.RELEASE,
                "parameter": stage.parameters.RELEASE,
            }[gate],
            "0",
        )
    with pytest.raises(stage.ContinuationRejected) as caught:
        with stage.continuation(None, law_id=stage.PHASE_DYNA_CONSTRUCTION_LAW, enabled=enabled):
            raise AssertionError("Held gate entered")
    assert caught.value.stage == "release"
    empty()


@pytest.mark.parametrize("kind", ["law", "none", "dictionary", "record", "parameters", "unissued"])
def test_supplied_or_historical_data_cannot_issue_a_claim(controlled, kind):
    h = controlled
    value = dict(
        none=None,
        dictionary={},
        record=h.original_record,
        parameters=h.p,
        unissued=object.__new__(previous.Lease),
    ).get(kind, h.original)
    with pytest.raises(stage.ContinuationRejected) as caught:
        with stage.continuation(
            value,
            law_id="foreign" if kind == "law" else stage.PHASE_DYNA_CONSTRUCTION_LAW,
            enabled=True,
        ):
            raise AssertionError("Supplied authority entered")
    assert caught.value.stage == ("law" if kind == "law" else "lease")
    assert h.original not in stage._CONSUMED and not h.parent.invalid
    empty()


def test_same_live_parent_original_closed_lease_and_record_are_preserved(controlled, tmp_path):
    h = controlled
    before = tuple(h.original_context.before)
    with acquire(h.original) as claim:
        assert claim.parameters is h.p and h.p._conf is h.cfg
        claim.check()
        with pytest.raises(stage.ContinuationRejected, match="before closure"):
            _ = claim.record
        with pytest.raises(previous.ConstructionRejected, match="Closed"):
            _ = h.original.parameters
        assert not h.original_context.active and not h.original_context.guard.active
        assert previous._CONSTRUCTED[h.parent_owner] is True
        assert previous._MUTEX.acquire(blocking=False)
        previous._MUTEX.release()
    record = claim.record
    assert record is claim.record and record.original_record is h.original_record
    assert h.original.record is h.original_record and record.succeeded
    assert not record.parameter_advanced and not record.tissue_handler_admitted
    assert record.biological_cases == 0 and not h.parent.invalid
    assert all(a is b for a, b in zip(before, h.original_context.before, strict=True))
    assert stage.parameters._validate(h.parent_owner) is h.parent and h.calls == []
    assert previous._CONSTRUCTED[h.parent_owner] is True
    empty()
    save(
        tmp_path,
        "same-parameter-continuation",
        dict(
            record=stage.record_document(record),
            setup_work=h.setup_work,
            same_owner=True,
            same_p=True,
            same_original_record=True,
            original_lease_remains_closed=True,
            actual_constructor_numeric_entries=0,
        ),
    )


@pytest.mark.parametrize("operation", ["parameters", "check", "pickle"])
def test_closed_claim_is_not_live_or_serializable_authority(controlled, operation):
    h = controlled
    with acquire(h.original) as claim:
        pass
    if operation == "pickle":
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(claim)
    else:
        with pytest.raises(stage.ContinuationRejected, match="Closed"):
            getattr(claim, operation)() if operation == "check" else claim.parameters
    assert claim.record.succeeded and not h.parent.invalid
    empty()


@pytest.mark.parametrize("failure", [False, True])
def test_success_and_source_failure_each_consume_successor_irreversibly(
    controlled, tmp_path, failure
):
    h = controlled
    primary, cause = (
        SyntheticSourceFailure("new handler failed"),
        SyntheticSourceCause("original cause"),
    )
    try:
        with acquire(h.original) as claim:
            assert claim.parameters is h.p
            if failure:
                raise primary from cause
    except SyntheticSourceFailure as caught:
        assert failure and caught is primary and caught.__cause__ is cause
        assert caught.dyna_continuation is stage._ISSUED[claim]
    assert claim.record.succeeded is (not failure)
    assert claim.record.source_error_present is failure
    assert claim.record.original_record is h.original_record and h.original_record.succeeded
    with pytest.raises(stage.ContinuationRejected) as caught:
        with acquire(h.original):
            raise AssertionError("Repeated source constructor")
    assert caught.value.stage == "consumed"
    assert previous._CONSTRUCTED[h.parent_owner] is True and h.calls == []
    empty()
    save(
        tmp_path,
        "irreversible-attempt",
        dict(
            record=stage.record_document(claim.record),
            primary=primary if failure else None,
            cause=cause if failure else None,
            replay_refusal=caught.value.stage,
            actual_constructor_entries=0,
        ),
    )


@pytest.mark.parametrize("field", ["event_cut_profile_names", "event_cut_time"])
def test_missing_real_event_stores_remain_raw_source_failures(controlled, field, tmp_path):
    h = controlled
    assert field not in vars(h.p)
    with pytest.raises(AttributeError) as caught:
        with acquire(h.original) as claim:
            getattr(claim.parameters, field)
    assert field in str(caught.value) and stage._ISSUED[claim].source_error is caught.value
    assert not claim.record.succeeded and claim.record.source_error_present
    assert field not in vars(h.p) and previous._CONSTRUCTED[h.parent_owner] is True
    empty()
    save(
        tmp_path,
        "missing-native-store",
        dict(
            field=field,
            primary=caught.value,
            record=stage.record_document(claim.record),
            no_native_execution=True,
        ),
    )


@pytest.mark.parametrize(
    "mutation", ["parent", "closed-lease", "record", "marker", "before", "guard"]
)
def test_stale_or_reassociated_predecessor_refuses_before_delegate(controlled, mutation):
    h = controlled
    if mutation == "parent":
        h.parent.invalid = True
    elif mutation == "closed-lease":
        h.original_context.invalid = True
    elif mutation == "record":
        h.original_context.record = replace(h.original_record, succeeded=False)
    elif mutation == "marker":
        previous._CONSTRUCTED[h.parent_owner] = False
    elif mutation == "before":
        h.original_context.before = tuple(
            [
                *h.original_context.before[:2],
                replace(h.parent.trial),
                *h.original_context.before[3:],
            ]
        )
    else:
        h.original_context.guard.invalid = True
    delegated = []
    with pytest.raises((ValueError, stage.ContinuationRejected)):
        with acquire(h.original):
            delegated.append(True)
    assert delegated == [] and h.original in stage._CONSUMED and h.parent.invalid
    assert h.original.record is h.original_context.record and h.calls == []
    empty()


@pytest.mark.parametrize("kind", ["configuration", "store", "trial", "wrapper"])
def test_read_only_parent_graph_changes_refuse_at_exit(controlled, kind, tmp_path):
    h = controlled
    with pytest.raises(stage.ContinuationRejected) as caught:
        with acquire(h.original) as claim:
            if kind == "configuration":
                h.cfg["foreign"] = True
            elif kind == "store":
                h.p.autoInit = True
            elif kind == "trial":
                h.parent.trial = replace(h.parent.trial)
            else:
                h.p.visual.__class__ = h.base.classes["SimConfTissueDefault"]
    context = stage._ISSUED[claim]
    assert caught.value.partial is context and context.source_error is None
    assert context.capture_errors and not claim.record.succeeded and h.parent.invalid
    assert h.original_record.succeeded and previous._CONSTRUCTED[h.parent_owner] is True
    empty()
    save(
        tmp_path,
        "readonly-parent-drift",
        dict(
            kind=kind,
            record=stage.record_document(claim.record),
            partial_config=h.cfg,
            partial_stores=vars(h.p).keys(),
            secondary=context.capture_errors,
        ),
    )


@pytest.mark.parametrize("kind", ["continuation", "inspection", "construction", "numeric"])
@pytest.mark.parametrize("swallow", [False, True])
def test_shared_exclusion_poisoned_even_when_nested_refusal_is_swallowed(controlled, kind, swallow):
    h = controlled
    seen = []

    def nested():
        if kind == "continuation":
            return acquire(h.original)
        if kind == "inspection":
            return previous.inspection(h.parent_owner)
        if kind == "construction":
            return earlier.construct(h.parent_owner)
        return previous._advance(h.parent_owner)

    with pytest.raises((stage.ContinuationRejected, previous.ConstructionRejected)):
        with acquire(h.original) as claim:
            try:
                with nested():
                    raise AssertionError("Conflicting source body entered")
            except (stage.ContinuationRejected, previous.ConstructionRejected) as error:
                seen.append(error)
                if not swallow:
                    raise
    assert len(seen) == 1 and h.parent.invalid and not claim.record.succeeded
    assert claim.record.source_error_present is (not swallow)
    assert h.calls == [] and previous._CONSTRUCTED[h.parent_owner] is True
    empty()


def test_original_registry_busy_consumes_eligible_attempt_without_deadlock(controlled):
    h = controlled
    assert previous._MUTEX.acquire(blocking=False)
    try:
        with pytest.raises(previous.ConstructionRejected) as caught:
            with acquire(h.original):
                raise AssertionError("Busy registry entered")
    finally:
        previous._MUTEX.release()
    assert caught.value.stage == "registry_busy" and h.original in stage._CONSUMED
    context = stage._CONSUMED[h.original]
    assert context.source_error is caught.value and not context.record.value.succeeded
    assert h.parent.invalid and previous._CONSTRUCTED[h.parent_owner] is True
    empty()


def test_real_profile_reentry_during_validation_never_enters_second_body(controlled):
    h = controlled
    inherited = sys.getprofile()
    observed, nested = [], []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code is stage.parameters._validate.__code__ and not observed:
            observed.append(frame)
            try:
                with acquire(h.original):
                    nested.append(True)
            except stage.ContinuationRejected as error:
                observed.append(error)
        if inherited is not None:
            inherited(frame, event, arg)

    sys.setprofile(profile)
    try:
        with pytest.raises((stage.ContinuationRejected, ValueError)):
            with acquire(h.original):
                raise AssertionError("Poisoned first body entered")
    finally:
        sys.setprofile(inherited)
    assert len(observed) == 2 and observed[1].stage == "conflict" and nested == []
    assert h.parent.invalid and not stage._CONSUMED[h.original].record.value.succeeded
    empty()


@pytest.mark.parametrize("operation", ["write", "directory"])
def test_actual_readonly_audit_forbids_filesystem_effects(controlled, tmp_path, operation):
    h = controlled
    target = tmp_path / "forbidden-output"
    with pytest.raises(ValueError):
        with acquire(h.original) as claim:
            if operation == "write":
                target.write_text("no")
            else:
                target.mkdir()
    assert not target.exists() and h.parent.invalid and not claim.record.succeeded
    empty()


@pytest.mark.parametrize("kind", ["source-and-drift", "source-and-record", "record"])
def test_primary_cause_survives_secondary_capture_or_record_failure(
    controlled, monkeypatch, tmp_path, kind
):
    h = controlled
    primary, cause = SyntheticSourceFailure("dyna failed"), SyntheticSourceCause("source cause")
    secondary = SyntheticCaptureFailure("closure record failed")

    def refuse(*args, **kwargs):
        raise secondary

    caught = None
    try:
        with acquire(h.original) as claim:
            if "drift" in kind:
                h.cfg["changed"] = True
            if "record" in kind:
                monkeypatch.setattr(stage, "ContinuationRecord", refuse)
            if kind != "record":
                raise primary from cause
    except BaseException as error:
        caught = error
    context = stage._ISSUED[claim]
    if kind != "record":
        assert caught is primary and caught.__cause__ is cause
        assert caught.dyna_continuation is context and context.source_error is primary
    else:
        assert type(caught) is stage.ContinuationRejected and context.source_error is None
    assert context.capture_errors and h.parent.invalid
    if "record" in kind:
        assert any(
            stage_name == "closure_record" and error is secondary
            for stage_name, error in context.capture_errors
        )
        assert context.record is None
    else:
        assert not claim.record.succeeded
    assert h.original.record is h.original_record and h.original_record.succeeded
    empty()
    save(
        tmp_path,
        "primary-and-secondary",
        dict(
            primary=caught,
            secondary=context.capture_errors,
            record=None if context.record is None else stage.record_document(claim.record),
            original_record=h.original_record,
            no_native_execution=True,
        ),
    )


def test_historical_record_remains_available_after_later_real_retirement(controlled):
    h = controlled
    with acquire(h.original) as claim:
        pass
    record = claim.record
    with previous._advance(h.parent_owner) as advance:
        assert advance.parameters is h.p
        previous.retire(advance, h.parent)
    assert h.parent.invalid and advance.record.retired and advance.record.succeeded
    assert claim.record is record and record.succeeded
    assert previous._CONSTRUCTED[h.parent_owner] is True and h.calls == []
    empty()


@pytest.mark.parametrize("state", ["active", "failed", "inspection", "retired"])
def test_actual_predecessor_lifecycle_controls_without_native_construction(
    monkeypatch, tmp_path, plan, state
):
    h = earlier.controlled.__wrapped__(monkeypatch, tmp_path, plan)
    monkeypatch.setenv(stage.RELEASE, "1")
    delegate = []
    if state == "active":
        with earlier.construct(h.parent_owner) as original:
            with pytest.raises(stage.ContinuationRejected) as caught:
                with acquire(original):
                    delegate.append(True)
            assert caught.value.stage == "predecessor" and original not in stage._CONSUMED
        with acquire(original) as valid:
            assert valid.parameters is h.p
        assert valid.record.succeeded and not h.parent.invalid
    else:
        if state == "inspection":
            with previous.inspection(h.parent_owner) as original:
                assert original.parameters is h.p
        elif state == "failed":
            primary = SyntheticSourceFailure("first constructor failed")
            with pytest.raises(SyntheticSourceFailure) as first:
                with earlier.construct(h.parent_owner) as original:
                    raise primary
            assert first.value is primary and not original.record.succeeded
        else:
            with earlier.construct(h.parent_owner) as original:
                pass
            with previous._advance(h.parent_owner) as numeric:
                previous.retire(numeric, h.parent)
            assert numeric.record.retired and numeric.record.succeeded
        with pytest.raises(ValueError) as caught:
            with acquire(original):
                delegate.append(True)
        if state == "inspection":
            assert caught.value.stage == "predecessor" and original not in stage._CONSUMED
            assert not h.parent.invalid and h.parent_owner not in previous._CONSTRUCTED
        else:
            assert original in stage._CONSUMED and h.parent.invalid
            context = stage._CONSUMED[original]
            assert context.source_error is caught.value and not context.record.value.succeeded
            assert previous._CONSTRUCTED[h.parent_owner] is True
    assert delegate == [] and h.calls == []
    empty()
    save(
        tmp_path,
        "actual-predecessor-lifecycle",
        dict(
            state=state,
            original=original.record,
            constructor_numeric_entries=0,
            delegate_entered=False,
        ),
    )


def test_equal_copied_original_record_during_claim_cannot_replace_retained_identity(controlled):
    h = controlled
    with pytest.raises(stage.ContinuationRejected) as caught:
        with acquire(h.original) as claim:
            copied = replace(h.original_record)
            assert copied == h.original_record and copied is not h.original_record
            h.original_context.record = copied
    assert caught.value.partial is stage._ISSUED[claim]
    assert claim.record.original_record is h.original_record and not claim.record.succeeded
    assert h.original_context.record is copied and h.parent.invalid
    empty()


def test_existing_read_claim_conflict_cannot_release_or_replace_foreign_stacks(controlled):
    h = controlled
    with pytest.raises(previous.ConstructionRejected):
        with previous.inspection(h.parent_owner) as inspection:
            protected = previous._ISSUED[inspection]
            try:
                with acquire(h.original):
                    raise AssertionError("Overlapping continuation entered")
            finally:
                assert previous._ACTIVE[-1] is protected
                assert stage.parameters._ACTIVE[-1] is protected
                assert stage.parameters.paths._ACTIVE[-1] is protected.guard
                assert not stage._ACTIVE
    context = stage._CONSUMED[h.original]
    assert not context.shared_registered and not context.record.value.succeeded
    assert h.parent.invalid and not inspection.record.succeeded and h.calls == []
    assert previous._CONSTRUCTED[h.parent_owner] is True
    empty()


def test_closed_validation_keeps_exact_historical_claim_without_constructor_rearm(
    controlled, tmp_path
):
    h = controlled
    with acquire(h.original) as claim:
        assert claim.parameters is h.p
    record = claim.record
    for _ in range(2):
        assert stage.validate_closed(claim, original_lease=h.original) is record
    context = stage._ISSUED[claim]
    assert len(context.closed_checks) == 2 and not context.closed_check_active
    assert all(
        row.record.succeeded and row.record.purpose == "inspection" for row in context.closed_checks
    )
    assert all(not previous._ISSUED[row.lease].active for row in context.closed_checks)
    assert not context.active and not context.guard.active and not h.original_context.active
    assert h.original.record is h.original_record and record.original_record is h.original_record
    assert context.p is h.p and not h.parent.invalid
    assert previous._CONSTRUCTED[h.parent_owner] is True and h.calls == []
    with pytest.raises(stage.ContinuationRejected, match="consumed"):
        with acquire(h.original):
            raise AssertionError("Read validation cannot rearm construction")
    empty()
    save(
        tmp_path,
        "closed-child-validation",
        dict(
            historical_record=stage.record_document(record),
            metadata_checks=[row.record for row in context.closed_checks],
            same_original_record=True,
            constructor_numeric_entries=0,
        ),
    )


def test_closed_validation_requires_exact_cache_original_lease_association(controlled):
    h = controlled
    with acquire(h.original) as claim:
        pass
    with pytest.raises(stage.ContinuationRejected) as caught:
        stage.validate_closed(claim, original_lease=h.original.record)
    assert caught.value.stage == "closed_association" and not h.parent.invalid
    assert not stage._ISSUED[claim].closed_checks
    assert stage.validate_closed(claim, original_lease=h.original) is claim.record
    empty()


@pytest.mark.parametrize("state", ["failed", "retired", "changed-p", "copied-record", "claim"])
def test_closed_validation_rejects_failed_stale_or_replaced_current_authority(controlled, state):
    h = controlled
    primary = SyntheticSourceFailure("conditional constructor failure")
    try:
        with acquire(h.original) as claim:
            if state == "failed":
                raise primary
    except SyntheticSourceFailure as error:
        assert error is primary
    context = stage._ISSUED[claim]
    historical = claim.record
    if state == "retired":
        with previous._advance(h.parent_owner) as advance:
            previous.retire(advance, h.parent)
    elif state == "changed-p":
        h.p.autoInit = True
    elif state == "copied-record":
        copied = replace(historical)
        assert copied == historical and copied is not historical
        context.record.value = copied
    elif state == "claim":
        context.claim = object.__new__(stage.DynaConstructionClaim)
    with pytest.raises(ValueError):
        stage.validate_closed(claim, original_lease=h.original)
    assert h.parent.invalid and not context.closed_check_active
    assert context.closed_checks[-1].source_error is not None
    assert previous._CONSTRUCTED[h.parent_owner] is True and h.calls == []
    if state != "copied-record":
        assert claim.record is historical
    empty()


def test_closed_validation_real_profile_reentry_refuses_without_construction(controlled):
    h = controlled
    with acquire(h.original) as claim:
        pass
    inherited, observed = sys.getprofile(), []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code is stage.parameters._validate.__code__ and not observed:
            observed.append(frame)
            try:
                stage.validate_closed(claim, original_lease=h.original)
            except stage.ContinuationRejected as error:
                observed.append(error)
        if inherited is not None:
            inherited(frame, event, arg)

    sys.setprofile(profile)
    try:
        with pytest.raises(ValueError):
            stage.validate_closed(claim, original_lease=h.original)
    finally:
        sys.setprofile(inherited)
    context = stage._ISSUED[claim]
    assert len(observed) == 2 and observed[1].stage == "closed_busy"
    assert h.parent.invalid and not context.closed_check_active and h.calls == []
    assert claim.record.succeeded and not context.active
    empty()


@pytest.mark.parametrize("secondary", [False, True])
def test_closed_validation_profile_primary_and_partial_capture_error_are_separate(
    controlled, tmp_path, secondary
):
    h = controlled
    with acquire(h.original) as claim:
        pass
    capture = SyntheticCaptureFailure("partial observation failed")

    class SourceFailure(SyntheticSourceFailure):
        def __getattribute__(self, name):
            if secondary and name == "construction_lease":
                raise capture
            return super().__getattribute__(name)

    primary, cause = (
        SourceFailure("metadata source verification failed"),
        SyntheticSourceCause("original metadata cause"),
    )
    inherited, reached = sys.getprofile(), []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code is stage.parameters._validate.__code__ and not reached:
            reached.append(frame)
            raise primary from cause
        if inherited is not None:
            inherited(frame, event, arg)

    sys.setprofile(profile)
    try:
        with pytest.raises(SourceFailure) as caught:
            stage.validate_closed(claim, original_lease=h.original)
    finally:
        sys.setprofile(inherited)
    assert caught.value is primary and primary.__cause__ is cause and len(reached) == 1
    context = stage._ISSUED[claim]
    attempt = context.closed_checks[-1]
    assert primary.dyna_closed_validation is attempt and attempt.source_error is primary
    partial = vars(primary)["construction_lease"]
    assert not partial.record.succeeded and partial.record.source_error_present
    if secondary:
        assert attempt.partial is None and attempt.record is None
        assert attempt.capture_errors == (("inspection_partial", capture),)
    else:
        assert attempt.partial is partial and attempt.record is partial.record
        assert attempt.capture_errors == ()
    assert claim.record.succeeded and h.parent.invalid and not context.closed_check_active
    assert previous._CONSTRUCTED[h.parent_owner] is True and h.calls == []
    empty()
    save(
        tmp_path,
        "closed-validation-primary",
        dict(
            primary=primary,
            secondary=attempt.capture_errors,
            failed_inspection_record=partial.record,
            original_dyna_record=stage.record_document(claim.record),
            actual_native_constructor_entries=0,
        ),
    )
