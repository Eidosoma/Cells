"""Conditional SEED parameter boundary; actual native/phase/source stays blocked."""

import pickle
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_seed_tail as stage
from tests.unit import test_betse_native_parameter_dyna_construction as earlier
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

blocked = earlier.blocked


@pytest.fixture(scope="module")
def plan():
    return earlier.plan.__wrapped__()


@pytest.fixture
def controlled(monkeypatch, tmp_path, plan):
    h = earlier.controlled.__wrapped__(monkeypatch, tmp_path, plan)
    with earlier.acquire(h.original) as dyna:
        assert dyna.parameters is h.p
    assert dyna.record.succeeded and "_run_sim" not in vars(h.p)
    h.dyna, h.dyna_record = dyna, dyna.record
    h.dyna_context = stage.previous._ISSUED[dyna]
    monkeypatch.setenv(stage.RELEASE, "1")
    return h


def acquire(h):
    return stage.seed_tail(
        h.dyna, original_lease=h.original, law_id=stage.SEED_TAIL_LAW, enabled=True
    )


def empty():
    earlier.empty()
    assert not stage._ACTIVE
    assert stage._LOCK.acquire(blocking=False)
    stage._LOCK.release()


def test_exact_SEED_source_order_and_no_time_or_export_mutation():
    plan = stage.source_plan()
    assert plan["phase_source"]["sha256"] == stage.PHASE_SHA256
    assert plan["predecessor"] == stage.PREVIOUS_SHA256
    assert plan["no_native_execution"] and plan["no_temporal_stores_or_directories"]
    assert not plan["phase_handler_or_INIT_admitted"]


@pytest.mark.parametrize(
    "gate", ["default", "integer", "local", "dyna", "lease", "parameter", "law"]
)
def test_explicit_gates_before_any_source_claim(monkeypatch, gate):
    for name in (
        stage.RELEASE,
        stage.previous.RELEASE,
        stage.leases.RELEASE,
        stage.parameters.RELEASE,
    ):
        monkeypatch.setenv(name, "1")
    enabled = False if gate == "default" else 1 if gate == "integer" else True
    if gate in ("local", "dyna", "lease", "parameter"):
        name = {
            "local": stage.RELEASE,
            "dyna": stage.previous.RELEASE,
            "lease": stage.leases.RELEASE,
            "parameter": stage.parameters.RELEASE,
        }[gate]
        monkeypatch.setenv(name, "0")
    with pytest.raises(stage.SeedTailRejected) as caught:
        with stage.seed_tail(
            None,
            original_lease=None,
            law_id="foreign" if gate == "law" else stage.SEED_TAIL_LAW,
            enabled=enabled,
        ):
            raise AssertionError("Held input entered")
    assert caught.value.stage == ("law" if gate == "law" else "release")
    empty()


@pytest.mark.parametrize("kind", ["none", "dictionary", "record", "unissued", "lease"])
def test_actual_closed_dyna_only_no_receipt_or_owner_substitution(controlled, kind):
    h = controlled
    value = {
        "none": None,
        "dictionary": {},
        "record": h.dyna_record,
        "unissued": object.__new__(stage.previous.DynaConstructionClaim),
        "lease": h.original,
    }[kind]
    with pytest.raises(stage.SeedTailRejected) as caught:
        with stage.seed_tail(
            value, original_lease=h.original, law_id=stage.SEED_TAIL_LAW, enabled=True
        ):
            raise AssertionError("Unissued input entered")
    assert caught.value.stage == "dyna_claim" and h.dyna not in stage._CONSUMED
    assert not h.parent.invalid and h.calls == []
    empty()


def test_exact_same_owner_p_records_only_fresh_False_then_current_closed_validation(
    controlled, tmp_path
):
    h = controlled
    before = dict(vars(h.p))
    with acquire(h) as claim:
        assert claim.parameters is h.p and h.parent.invalid and h.dyna_context.retired
        assert h.dyna_context.invalid and h.dyna_context.guard.invalid
        assert stage.leases._CONSTRUCTED[h.parent_owner] is True
        claim.check()
        with pytest.raises(stage.SeedTailRejected, match="record"):
            _ = claim.record
        h.p._run_sim = False
        claim.check()
    record = claim.record
    assert (
        record.succeeded and record.parameter_value is False and not record.phase_handler_admitted
    )
    assert record.dyna_record is h.dyna_record and record.original_record is h.original_record
    assert h.dyna.record is h.dyna_record and h.original.record is h.original_record
    assert tuple(vars(h.p)) == (*before, "_run_sim") and vars(h.p)["_run_sim"] is False
    assert all(vars(h.p)[name] is value for name, value in before.items())
    assert stage.validate_closed(claim, dyna_claim=h.dyna, original_lease=h.original) is record
    with pytest.raises(stage.previous.ContinuationRejected):
        stage.previous.validate_closed(h.dyna, original_lease=h.original)
    with pytest.raises(stage.parameters.SubconfigurationsRejected):
        stage.parameters._validate(h.parent_owner)
    assert stage.validate_closed(claim, dyna_claim=h.dyna, original_lease=h.original) is record
    with pytest.raises(stage.SeedTailRejected) as repeat:
        with acquire(h):
            raise AssertionError("Duplicate SEED tail")
    assert repeat.value.stage == "consumed" and h.calls == []
    empty()
    ctx = stage._ISSUED[claim]
    save(
        tmp_path,
        "same-parameter-SEED-tail",
        dict(
            record=stage.record_document(record),
            before=ctx.before_graph[1],
            after=ctx.after_graph[1],
            work=ctx.work,
            actual_native_phase_constructor_source_entries=0,
            conditional_plain_assignment=True,
        ),
    )


@pytest.mark.parametrize("value", [True, 0, 0.0, None, "False"])
def test_exact_bool_False_not_truth_value_coercion(controlled, value):
    h = controlled
    with pytest.raises(stage.SeedTailRejected) as caught:
        with acquire(h) as claim:
            h.p._run_sim = value
    assert not claim.record.succeeded and caught.value.capture_errors
    assert h.dyna in stage._CONSUMED and h.parent.invalid
    empty()


@pytest.mark.parametrize(
    "mutation", ["none", "time-store", "config", "old-field", "alias", "order"]
)
def test_only_original_SEED_flag_assignment_is_allowed(controlled, mutation):
    h = controlled
    with pytest.raises(stage.SeedTailRejected):
        with acquire(h) as claim:
            if mutation != "none":
                h.p._run_sim = False
            if mutation == "time-store":
                h.p.dt = 1.0
            elif mutation == "config":
                h.cfg["foreign"] = True
            elif mutation == "old-field":
                h.p.init_export_dirname = "foreign"
            elif mutation == "alias":
                h.p.config = dict(h.cfg)
            elif mutation == "order":
                value = vars(h.p).pop("init_export_dirname")
                h.p.init_export_dirname = value
    assert not claim.record.succeeded and h.parent.invalid
    assert stage.leases._CONSTRUCTED[h.parent_owner] is True
    empty()


@pytest.mark.parametrize("when", ["before", "after"])
def test_primary_identity_cause_and_available_failed_prefix_preserved(controlled, tmp_path, when):
    h = controlled
    primary, cause = (
        SyntheticSourceFailure("native consumer tail failed"),
        SyntheticSourceCause("original cause"),
    )
    with pytest.raises(SyntheticSourceFailure) as caught:
        with acquire(h) as claim:
            if when == "after":
                h.p._run_sim = False
            raise primary from cause
    ctx = stage._ISSUED[claim]
    assert caught.value is primary and primary.__cause__ is cause and primary.seed_tail_claim is ctx
    assert ctx.source_error is primary and not claim.record.succeeded
    assert claim.record.source_error_present and ctx.partial_graph is not None
    assert ("_run_sim" in vars(h.p)) is (when == "after")
    assert h.dyna.record is h.dyna_record and stage.leases._CONSTRUCTED[h.parent_owner] is True
    empty()
    save(
        tmp_path,
        "SEED-tail-failed-prefix",
        dict(
            primary=primary,
            secondary=ctx.capture_errors,
            record=stage.record_document(claim.record),
            partial=ctx.partial_graph[1],
            actual_native_phase_source_entries=0,
        ),
    )


def test_secondary_record_failure_cannot_mask_primary_or_issue_success(
    controlled, monkeypatch, tmp_path
):
    h = controlled
    primary, cause = SyntheticSourceFailure("tail failed"), SyntheticSourceCause("cause")
    secondary = SyntheticCaptureFailure("record unavailable")

    def fail(*args, **kwargs):
        raise secondary

    with pytest.raises(SyntheticSourceFailure) as caught:
        with acquire(h) as claim:
            h.p._run_sim = False
            monkeypatch.setattr(stage, "SeedTailRecord", fail)
            raise primary from cause
    ctx = stage._ISSUED[claim]
    assert caught.value is primary and primary.__cause__ is cause and ctx.record is None
    assert any(
        name == "closure_record" and error is secondary for name, error in ctx.capture_errors
    )
    assert ctx.partial_graph is not None and h.parent.invalid
    empty()
    save(
        tmp_path,
        "SEED-tail-secondary-failure",
        dict(
            primary=primary,
            secondary=ctx.capture_errors,
            partial=ctx.partial_graph[1],
            success_record=False,
        ),
    )


@pytest.mark.parametrize("operation", ["tail", "construction", "numeric"])
@pytest.mark.parametrize("swallow", [False, True])
def test_shared_exclusion_and_irreversible_epoch_even_if_refusal_swallowed(
    controlled, operation, swallow
):
    h = controlled
    seen = []

    def nested():
        if operation == "tail":
            return acquire(h)
        if operation == "construction":
            return stage.leases.construction(
                h.parent_owner, law_id=stage.leases.LAW_ID, enabled=True
            )
        return stage.leases._advance(h.parent_owner)

    with pytest.raises((stage.SeedTailRejected, stage.leases.ConstructionRejected)):
        with acquire(h) as claim:
            h.p._run_sim = False
            try:
                with nested():
                    raise AssertionError("Conflicting delegate entered")
            except (stage.SeedTailRejected, stage.leases.ConstructionRejected) as error:
                seen.append(error)
                if not swallow:
                    raise
    assert len(seen) == 1 and not claim.record.succeeded and h.parent.invalid and h.calls == []
    assert h.dyna in stage._CONSUMED and stage.leases._CONSTRUCTED[h.parent_owner] is True
    empty()


def test_actual_profile_reentry_cannot_issue_two_tail_claims(controlled):
    h = controlled
    old = sys.getprofile()
    seen = []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code is stage.previous.validate_closed.__code__ and not seen:
            seen.append(frame)
            try:
                with acquire(h):
                    raise AssertionError("Second mutation epoch entered")
            except stage.SeedTailRejected as error:
                seen.append(error)
        if old is not None:
            old(frame, event, arg)

    sys.setprofile(profile)
    try:
        with pytest.raises(ValueError):
            with acquire(h):
                raise AssertionError("Poisoned first epoch entered")
    finally:
        sys.setprofile(old)
    assert len(seen) == 2 and seen[1].stage == "conflict" and h.parent.invalid
    assert not stage._CONSUMED[h.dyna].record.value.succeeded
    empty()


def test_closed_validation_uses_no_stale_pre_mutation_state_validators(controlled):
    h = controlled
    with acquire(h) as claim:
        h.p._run_sim = False
    old = sys.getprofile()
    forbidden = {
        stage.previous.validate_closed.__code__,
        stage.parameters._validate.__code__,
        stage.leases._parent.__code__,
    }
    reached = []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code in forbidden:
            reached.append(frame.f_code.co_qualname)
            raise AssertionError("Stale state validator invoked")
        if old is not None:
            old(frame, event, arg)

    sys.setprofile(profile)
    try:
        assert (
            stage.validate_closed(claim, dyna_claim=h.dyna, original_lease=h.original)
            is claim.record
        )
    finally:
        sys.setprofile(old)
    assert reached == []
    empty()


def _change_historical_lease(h, field):
    base = h.original_context
    if field == "guard":
        original = base.guard
        base.guard = SimpleNamespace(**vars(original))
        assert base.guard is not original
        assert all(getattr(base.guard, name) is value for name, value in vars(original).items())
        assert base.guard.active is False and base.guard.invalid is False
    elif field == "before":
        original = base.before
        base.before = tuple(list(original))
        assert base.before is not original
        assert all(a is b for a, b in zip(base.before, original, strict=True))
    elif field == "work":
        original = base.work
        base.work = list(original)
        assert base.work is not original and base.work == original
    elif field == "bindings":
        original = base.bindings
        base.bindings = tuple(list(original))
        assert base.bindings is not original
        assert all(a is b for a, b in zip(base.bindings, original, strict=True))
    elif field == "thread":
        base.thread += 1
    elif field == "guard-thread":
        base.guard.thread += 1
    elif field == "audit-ready":
        base.guard.audit_ready = False
    elif field == "retired":
        base.retired = True
    elif field == "purpose":
        base.purpose = "inspection"
    else:
        raise AssertionError(field)


@pytest.mark.parametrize("when", ["active", "closed"])
@pytest.mark.parametrize(
    "field",
    [
        "guard",
        "before",
        "work",
        "bindings",
        "thread",
        "guard-thread",
        "audit-ready",
        "retired",
        "purpose",
    ],
)
def test_historical_lease_metadata_drift_refuses_after_valid_issued_chain(
    controlled, tmp_path, when, field
):
    h = controlled
    assert stage.previous._source(h.dyna_context) is h.original_context
    assert h.original_context.guard is h.dyna_context.source_guard
    assert h.original.record is h.original_record and h.original_record.succeeded
    baseline = False
    if when == "active":
        with pytest.raises(ValueError, match="Actual closed Lease/") as caught:
            with acquire(h) as claim:
                h.p._run_sim = False
                claim.check()
                baseline = True
                _change_historical_lease(h, field)
                claim.check()
        ctx = stage._ISSUED[claim]
        assert ctx.source_error is caught.value and caught.value.seed_tail_claim is ctx
        assert not claim.record.succeeded and claim.record.source_error_present
    else:
        with acquire(h) as claim:
            h.p._run_sim = False
        record = claim.record
        assert stage.validate_closed(claim, dyna_claim=h.dyna, original_lease=h.original) is record
        baseline = True
        _change_historical_lease(h, field)
        with pytest.raises(ValueError, match="Actual closed Lease/") as caught:
            stage.validate_closed(claim, dyna_claim=h.dyna, original_lease=h.original)
        ctx = stage._ISSUED[claim]
        attempt = caught.value.seed_tail_validation
        assert attempt.source_error is caught.value and not attempt.succeeded
        assert ctx.validations[-1] is attempt and not attempt.active
        assert claim.record is record and record.succeeded
    assert baseline and ctx.invalid and h.parent.invalid and h.p._run_sim is False
    assert h.dyna.record is h.dyna_record and h.original.record is h.original_record
    assert stage.leases._CONSTRUCTED[h.parent_owner] is True and h.calls == []
    empty()
    save(
        tmp_path,
        "historical-Lease-refusal",
        dict(
            field=field,
            use=when,
            valid_issued_chain_baseline=baseline,
            primary=caught.value,
            secondary=ctx.capture_errors,
            record=stage.record_document(claim.record),
            actual_native_phase_constructor_source_entries=0,
        ),
    )


@pytest.mark.parametrize(
    "mutation", ["flag", "config", "dyna-edge", "tail-edge", "record", "rearm"]
)
def test_closed_successor_rejects_current_state_or_registry_drift(controlled, mutation):
    h = controlled
    with acquire(h) as claim:
        h.p._run_sim = False
    ctx = stage._ISSUED[claim]
    record = claim.record
    if mutation == "flag":
        h.p._run_sim = True
    elif mutation == "config":
        h.cfg["foreign"] = True
    elif mutation == "dyna-edge":
        del stage.previous._CONSUMED[h.original]
    elif mutation == "tail-edge":
        del stage._CONSUMED[h.dyna]
    elif mutation == "record":
        ctx.record.value = replace(record)
    else:
        h.parent.invalid = False
    with pytest.raises(ValueError):
        stage.validate_closed(claim, dyna_claim=h.dyna, original_lease=h.original)
    assert ctx.invalid and h.parent.invalid
    empty()


@pytest.mark.parametrize("operation", ["parameters", "pickle", "file", "directory"])
def test_closed_claim_and_filesystem_boundaries(controlled, tmp_path, operation):
    h = controlled
    target = tmp_path / "forbidden"
    if operation in ("file", "directory"):
        with pytest.raises(ValueError):
            with acquire(h) as claim:
                h.p._run_sim = False
                target.write_text("no") if operation == "file" else target.mkdir()
        assert not target.exists() and not claim.record.succeeded
    else:
        with acquire(h) as claim:
            h.p._run_sim = False
        if operation == "pickle":
            with pytest.raises(TypeError, match="cannot be serialized"):
                pickle.dumps(claim)
        else:
            with pytest.raises(stage.SeedTailRejected, match="closed"):
                _ = claim.parameters
        assert claim.record.succeeded
    empty()
