"""Native-blocked shared constructor/numeric claim ownership and failures."""

import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_construction_lease as leases
from cells.processes import betse_native_parameter_numeric_prefix as numeric
from tests.unit import test_betse_native_parameter_numeric_prefix as earlier
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

blocked = earlier.blocked


@pytest.fixture(scope="module")
def plan():
    return numeric.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, plan):
    h = earlier.controlled.__wrapped__(monkeypatch, tmp_path, plan)
    monkeypatch.setenv(leases.RELEASE, "1")
    return h


def construct(owner):
    return leases.construction(owner, law_id=leases.LAW_ID, enabled=True)


def empty():
    assert not leases._ACTIVE and not leases.previous._ACTIVE
    assert not leases.previous.paths._ACTIVE and not numeric._ACTIVE
    assert leases._MUTEX.acquire(blocking=False)
    leases._MUTEX.release()


def test_exact_repaired_predecessor_and_held_scope(plan):
    assert numeric.PREVIOUS_SHA256 == leases.PARENT_SHA256
    assert (
        leases.PARENT_SHA256 == "22e4a0db41a14d9fabd761b02583742004b162a1866d1769611b9e9ad8013b3b"
    )
    assert not plan["construction_lease"]["runtime_refresh"]
    assert not plan["construction_lease"]["native_release"]
    assert plan["statement_slice"] == (12, 29) and plan["source_lines"] == (520, 582)


@pytest.mark.parametrize(
    "enabled,local,parent", [(False, "1", "1"), (True, "0", "1"), (True, "1", "0"), (1, "1", "1")]
)
def test_public_construction_gates_before_claim_or_validation(monkeypatch, enabled, local, parent):
    monkeypatch.setenv(leases.RELEASE, local)
    monkeypatch.setenv(leases.previous.RELEASE, parent)
    with pytest.raises(leases.ConstructionRejected) as caught:
        with leases.construction(None, law_id=leases.LAW_ID, enabled=enabled):
            raise AssertionError("Must not enter")
    assert caught.value.stage == "release"
    empty()


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(leases.previous.SubconfigurationsOwner)]
)
def test_foreign_or_supplied_owner_is_not_hydrated(value):
    with pytest.raises(leases.previous.SubconfigurationsRejected, match="Issued same-parameter"):
        with leases.inspection(value):
            raise AssertionError("Must not enter")
    empty()


def test_clean_selected_leaf_keeps_same_parent_then_numeric_retires_it_once(controlled, tmp_path):
    h = controlled
    request = h.request()
    before = h.parent.graph, h.parent.trial, h.parent.authority, h.parent.capture_view
    with construct(h.parent_owner) as claim:
        p = claim.parameters
        handler = SimpleNamespace(p=p, synthetic_only=True)
        claim.check()
        assert p is h.p and handler.p is h.p
        assert leases._MUTEX.acquire(blocking=False)
        leases._MUTEX.release()
        with pytest.raises(leases.ConstructionRejected, match="before claim closure"):
            _ = claim.record
    assert claim.record.succeeded and not claim.record.retired and not h.parent.invalid
    assert all(
        a is b
        for a, b in zip(
            before,
            (h.parent.graph, h.parent.trial, h.parent.authority, h.parent.capture_view),
            strict=True,
        )
    )
    assert leases.previous._validate(h.parent_owner) is h.parent
    owner = numeric.prepare(request, enabled=True)
    ctx = numeric._ISSUED[owner]
    assert owner.parameters is h.p and handler.p is h.p and h.parent.invalid
    assert ctx.lease.record.retired and ctx.lease.record.succeeded
    assert h.calls == ["synthetic_numeric"] and len(h.setup_work) == 7
    with pytest.raises(leases.previous.SubconfigurationsRejected):
        leases.previous._validate(h.parent_owner)
    with pytest.raises(numeric.NumericPrefixRejected) as caught:
        numeric.prepare(request, enabled=True)
    assert caught.value.stage == "consumed"
    empty()
    save(
        tmp_path,
        "selected-leaf-then-numeric",
        dict(
            construction=claim.record,
            advance=ctx.lease.record,
            setup_work=h.setup_work,
            numeric_work=ctx.trial.work,
            synthetic_constructor_entries=1,
            actual_native_constructor_numeric_entries=0,
        ),
    )


@pytest.mark.parametrize("operation", ["parameters", "check", "pickle"])
def test_closed_claim_cannot_supply_parent_authority(controlled, operation):
    import pickle

    h = controlled
    with construct(h.parent_owner) as claim:
        assert claim.parameters is h.p
    if operation == "pickle":
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(claim)
    else:
        with pytest.raises(leases.ConstructionRejected, match="Closed"):
            if operation == "parameters":
                _ = claim.parameters
            else:
                claim.check()
    assert not h.parent.invalid and claim.record.succeeded
    empty()


def test_construction_attempt_does_not_repeat_or_issue_another_leaf(controlled):
    h = controlled
    with construct(h.parent_owner):
        pass
    with pytest.raises(leases.ConstructionRejected) as caught:
        with construct(h.parent_owner):
            raise AssertionError("Duplicate constructor")
    assert caught.value.stage == "consumed" and not h.parent.invalid
    empty()


@pytest.mark.parametrize("operation", ["request", "advance", "construction"])
@pytest.mark.parametrize("swallow", [False, True])
def test_active_constructor_refuses_overlap_before_parent_reads_and_numeric_work(
    controlled, monkeypatch, tmp_path, operation, swallow
):
    h = controlled
    request = h.request()
    forbidden = []
    inner = []

    def stop(*args, **kwargs):
        forbidden.append("numeric preparation")
        raise AssertionError("No numeric preparation during constructor")

    monkeypatch.setattr(numeric, "_prepare", stop)
    monkeypatch.setattr(numeric, "source_plan", stop)
    with pytest.raises(leases.ConstructionRejected) as caught:
        with construct(h.parent_owner) as claim:
            try:
                if operation == "request":
                    h.request()
                elif operation == "advance":
                    numeric.prepare(request, enabled=True)
                else:
                    with construct(h.parent_owner):
                        raise AssertionError("Nested constructor")
            except leases.ConstructionRejected as error:
                inner.append(error)
                if not swallow:
                    raise
    ctx = leases._ISSUED[claim]
    assert inner[0].stage == "claim_conflict" and ctx.invalid and h.parent.invalid
    assert forbidden == [] and h.calls == [] and request not in numeric._CONSUMED
    assert ctx.record.succeeded is False and ctx.record.source_error_present is (not swallow)
    if not swallow:
        assert caught.value is inner[0] and caught.value.construction_lease is ctx
    empty()
    save(
        tmp_path,
        "constructor-overlap",
        dict(
            operation=operation,
            swallow=swallow,
            record=claim.record,
            primary=ctx.source_error,
            secondary=ctx.capture_errors,
            numeric_entries=0,
            forbidden=forbidden,
        ),
    )


@pytest.mark.parametrize("swallow", [False, True])
def test_numeric_source_refuses_constructor_even_if_inner_error_is_swallowed(
    controlled, tmp_path, swallow
):
    h = controlled
    seen = []

    def nested():
        try:
            with construct(h.parent_owner):
                raise AssertionError("Must not construct")
        except leases.ConstructionRejected as error:
            seen.append(error)
            if not swallow:
                raise

    h.hooks["before"] = nested
    with pytest.raises(numeric.NumericPrefixRejected) as caught:
        numeric.prepare(h.request(), enabled=True)
    assert seen[0].stage == "claim_conflict" and h.parent.invalid
    assert h.calls == ["synthetic_numeric"] and caught.value.partial.invalid
    ctx = leases._ISSUED[caught.value.partial.lease]
    assert ctx.retired and not ctx.record.succeeded
    assert caught.value.construction_lease is ctx
    empty()
    save(
        tmp_path,
        "numeric-overlap",
        dict(
            record=ctx.record,
            primary=caught.value,
            synthetic_numeric_entries=1,
            actual_numeric_entries=0,
        ),
    )


def test_nonblocking_registry_refuses_without_waiting_or_poisoning_an_unclaimed_parent(controlled):
    h = controlled
    assert leases._MUTEX.acquire(blocking=False)
    try:
        with pytest.raises(leases.ConstructionRejected) as caught:
            with construct(h.parent_owner):
                raise AssertionError("Locked registry must refuse")
    finally:
        leases._MUTEX.release()
    assert caught.value.stage == "registry_busy" and not h.parent.invalid
    assert h.parent_owner not in leases._CONSTRUCTED
    empty()


@pytest.mark.parametrize("mutation", ["configuration", "store", "parent-trial", "wrapper"])
def test_constructor_cannot_mutate_or_reseal_parent_authorities(controlled, mutation):
    h = controlled
    with pytest.raises(leases.ConstructionRejected):
        with construct(h.parent_owner) as claim:
            if mutation == "configuration":
                h.cfg["foreign"] = True
            elif mutation == "store":
                h.p.autoInit = True
            elif mutation == "parent-trial":
                h.parent.trial = replace(h.parent.trial)
            else:
                h.p.visual.__class__ = h.base.classes["SimConfTissueDefault"]
    assert h.parent.invalid and not claim.record.succeeded
    empty()


@pytest.mark.parametrize("kind", ["source", "source-and-drift", "source-and-record", "record"])
def test_primary_identity_cause_and_secondary_capture_errors_remain_separate(
    controlled, monkeypatch, tmp_path, kind
):
    h = controlled
    primary = SyntheticSourceFailure("selected source failed")
    cause = SyntheticSourceCause("original source cause")
    secondary = SyntheticCaptureFailure("lease record failed")

    def fail_record(*args, **kwargs):
        raise secondary

    caught = None
    try:
        with construct(h.parent_owner) as claim:
            if "drift" in kind:
                h.cfg["changed"] = True
            if "record" in kind:
                monkeypatch.setattr(leases, "LeaseRecord", fail_record)
            if kind != "record":
                raise primary from cause
    except BaseException as error:
        caught = error
    ctx = leases._ISSUED[claim]
    if kind != "record":
        assert caught is primary and caught.__cause__ is cause and caught.construction_lease is ctx
        assert ctx.source_error is primary
    else:
        assert type(caught) is leases.ConstructionRejected and ctx.source_error is None
    if kind != "source":
        assert ctx.capture_errors
    if "record" in kind:
        assert any(error is secondary for _, error in ctx.capture_errors) and ctx.record is None
    assert h.parent.invalid
    empty()
    save(
        tmp_path,
        "source-secondary-separation",
        dict(
            kind=kind,
            primary=ctx.source_error,
            secondary=ctx.capture_errors,
            record=ctx.record,
            parent_invalid=h.parent.invalid,
        ),
    )


def test_real_runtime_growth_is_refused_without_refreshing_the_sealed_parent(monkeypatch, tmp_path):
    sub = earlier.earlier
    h = sub.controlled.__wrapped__(monkeypatch, tmp_path, leases.previous.source_plan())
    runtime = ModuleType("betse.synthetic_construction_runtime")
    runtime.__file__ = __file__
    vars(runtime).update(h.classes, Yaml=h.birth.source.yaml, Parameters=type(h.p))
    monkeypatch.setitem(sys.modules, runtime.__name__, runtime)
    monkeypatch.setattr(leases.previous.paths.prefix, "_runtime_types", sub.ORIGINAL_RUNTIME_TYPES)
    monkeypatch.setenv(leases.RELEASE, "1")
    owner = leases.previous.prepare(h.request(), enabled=True)
    parent = leases.previous._ISSUED[owner]
    files, namespaces, graph, trial = (
        parent.runtime_files,
        parent.runtime_namespaces,
        parent.graph,
        parent.trial,
    )
    with pytest.raises(leases.ConstructionRejected) as caught:
        with construct(owner) as claim:
            assert claim.parameters is h.p
            foreign = ModuleType("betse.synthetic_later_constructor_import")
            foreign.__file__ = str(Path(earlier.__file__).resolve())
            monkeypatch.setitem(sys.modules, foreign.__name__, foreign)
    assert parent.invalid and not claim.record.succeeded
    assert parent.runtime_files is files and parent.runtime_namespaces is namespaces
    assert parent.graph is graph and parent.trial is trial
    assert any(
        str(getattr(error, "source_error", None)) == "Subconfiguration runtime inventory changed"
        for _, error in caught.value.capture_errors
    )
    empty()
    save(
        tmp_path,
        "real-runtime-drift",
        dict(
            record=claim.record,
            original_runtime_files=files,
            original_inventory_not_refreshed=True,
            secondary=caught.value.capture_errors,
            actual_native_imports=0,
        ),
    )


def test_profiled_reentry_during_request_preparation_is_guarded(controlled):
    h = controlled
    prior = sys.getprofile()
    armed = []
    selected = numeric.source_plan.__code__

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if not armed and frame.f_code is selected and event == "call":
            armed.append(True)
            with construct(h.parent_owner):
                raise AssertionError("Must not construct at numeric request entry")

    sys.setprofile(profile)
    try:
        with pytest.raises(leases.ConstructionRejected) as caught:
            h.request()
        assert caught.value.stage == "claim_conflict"
    finally:
        sys.setprofile(prior)
    assert armed == [True] and h.parent.invalid and not h.calls
    empty()


def test_read_only_leaf_cannot_retire_parent_or_refresh_its_epoch(controlled):
    h = controlled
    with pytest.raises(leases.ConstructionRejected):
        with construct(h.parent_owner) as claim:
            leases.retire(claim, h.parent)
    assert h.parent.invalid and not claim.record.retired and not claim.record.succeeded
    empty()


@pytest.mark.parametrize("value", [None, {}, SimpleNamespace(), object.__new__(leases.Lease)])
def test_copied_record_or_foreign_claim_is_not_parent_admission(value):
    with pytest.raises(leases.ConstructionRejected, match="Issued opaque"):
        leases._parent(value)


def test_wrong_law_and_unknown_purpose_refuse_before_parent_work(controlled):
    h = controlled
    with pytest.raises(leases.ConstructionRejected) as caught:
        with leases.construction(h.parent_owner, law_id="foreign", enabled=True):
            raise AssertionError("Foreign law")
    assert caught.value.stage == "law"
    with pytest.raises(leases.ConstructionRejected) as caught:
        with leases._claim(h.parent_owner, "foreign"):
            raise AssertionError("Foreign purpose")
    assert caught.value.stage == "purpose" and not h.parent.invalid
    empty()
