"""Prepared blocked claim/data controls; no real phase/constructor execution.

Conditional issued-map models below exercise only the parameter claim. They
provide no original load, phase, world or physical authority. No test is run
by source-only development or source snapshot preparation.
"""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_world_construction as stage
from tests.unit import test_betse_native_parameter_initializer_constants as inherited
from validation.betse import betse_native_parameter_world_construction_software as runner
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticSourceCause,
    SyntheticSourceFailure,
)

blocked = inherited.blocked
prevent_reference_execution = inherited.prevent_reference_execution


@pytest.mark.parametrize("mode", ["default", "integer", "local", "parent", "law"])
def test_release_and_law_precede_world_owner_or_source_work(monkeypatch, mode):
    for name in (stage.RELEASE, stage.parameters.RELEASE, stage.parameters.previous.RELEASE):
        monkeypatch.setenv(name, "1")
    if mode in ("local", "parent"):
        monkeypatch.setenv(stage.RELEASE if mode == "local" else stage.parameters.RELEASE, "0")

    def forbidden(owner):
        raise AssertionError("Reservation must not be reached")

    monkeypatch.setattr(stage, "_reserve", forbidden)
    enabled = False if mode == "default" else 1 if mode == "integer" else True
    with pytest.raises(stage.WorldConstructionRejected) as caught:
        with stage.construction(
            None,
            law_id="foreign" if mode == "law" else stage.WORLD_CONSTRUCTION_LAW,
            enabled=enabled,
        ):
            raise AssertionError("No constructor permission")
    assert caught.value.stage == ("law" if mode == "law" else "release")


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.WorldConstructionClaim)]
)
def test_record_or_unissued_claim_cannot_become_closed_authority(value):
    with pytest.raises(stage.WorldConstructionRejected):
        stage.validate_closed_seed(value, original_owner=None)
    with pytest.raises(stage.WorldConstructionRejected):
        stage.failed_context(value)


@pytest.fixture
def conditional(monkeypatch):
    # Explicit synthetic input-boundary model; no native p/load/phase claim.
    r = stage.parameters
    p = SimpleNamespace(F=1.0, wsx=2.0, wsy=3.0)
    owner = object.__new__(r.WorldReadyParametersOwner)
    seven = object.__new__(r.previous.previous.mod.subconfigs.SubconfigurationsOwner)
    parent_owner = object.__new__(r.previous.ConstantsOwner)
    parent = SimpleNamespace()
    graph = ((), dict(vars(p)))
    cm = object()
    value = r.LoadRecord(
        "conditional-parent",
        "conditional-source",
        218,
        "BASIC",
        "before",
        "after",
        (),
        (),
        True,
        "",
    )
    value = replace(value, identity=r._digest(r.record_document(value)))
    source = SimpleNamespace(
        owner=owner,
        p=p,
        parent_owner=parent_owner,
        parent=parent,
        record=value,
        original_record=value,
        after_graph=graph,
        after_cm=cm,
        work=[],
        bindings=object(),
        loaded=SimpleNamespace(owner=seven),
        invalid=False,
    )
    monkeypatch.setitem(r._ISSUED, owner, source)
    monkeypatch.setitem(r._CONSUMED, parent_owner, source)

    def history(actual):
        if actual is not owner or source.invalid:
            raise ValueError("Synthetic history changed")
        return value

    def capture(actual, *, names=None):
        assert actual is source
        return (), {name: vars(p)[name] for name in (tuple(vars(p)) if names is None else names)}

    def same_graph(actual, saved):
        if actual[1] != saved[1]:
            raise ValueError("Conditional protected data changed")

    def same_cm(actual, saved):
        if actual is not cm or saved is not cm:
            raise ValueError("Conditional colormap edge changed")

    monkeypatch.setattr(r, "validate_completed_history", history)
    monkeypatch.setattr(r, "_capture", capture)
    monkeypatch.setattr(r, "_colormaps", lambda actual: cm)
    monkeypatch.setattr(r.previous, "_same_cm", same_cm)
    monkeypatch.setattr(stage.prefix.parameters.inherited, "_same_graph", same_graph)
    for name in (stage.RELEASE, r.RELEASE, r.previous.RELEASE):
        monkeypatch.setenv(name, "1")
    return SimpleNamespace(
        owner=owner,
        p=p,
        source=source,
        seven=seven,
        enter=lambda: stage.construction(owner, law_id=stage.WORLD_CONSTRUCTION_LAW, enabled=True),
    )


def test_conditional_claim_retains_same_p_and_exact_closed_record(conditional):
    h = conditional
    with h.enter() as claim:
        assert claim.parameters is h.p
        assert claim.check() is None
        with pytest.raises(stage.WorldConstructionRejected, match="No record before closure"):
            _ = claim.record
        with pytest.raises(stage.WorldConstructionRejected, match="Closed failed claim"):
            stage.failed_context(claim)
        h.p._run_sim = False
        claim.check()
    record = stage.validate_closed_seed(claim, original_owner=h.owner)
    assert record is claim.record and record.succeeded and record.seed_flag_created
    assert stage.record_document(record)["phase_admitted"] is False
    assert stage.parameters._CONSTRUCTED[h.owner] is claim
    with pytest.raises(stage.WorldConstructionRejected):
        _ = claim.parameters
    with pytest.raises(stage.WorldConstructionRejected):
        claim.check()
    with pytest.raises(stage.WorldConstructionRejected, match="Closed failed claim"):
        stage.failed_context(claim)
    with pytest.raises(stage.WorldConstructionRejected) as consumed:
        with h.enter():
            pass
    assert consumed.value.stage == "consumed"


@pytest.mark.parametrize("mode", ["missing", "true", "integer", "other-field", "exception"])
def test_conditional_failed_constructor_is_irreversible_and_retains_primary(conditional, mode):
    h = conditional
    primary, cause = (
        SyntheticSourceFailure("conditional constructor"),
        SyntheticSourceCause("cause"),
    )
    expected = SyntheticSourceFailure if mode == "exception" else stage.WorldConstructionRejected
    with pytest.raises(expected) as caught:
        with h.enter() as claim:
            if mode != "missing":
                h.p._run_sim = True if mode == "true" else 0 if mode == "integer" else False
            if mode == "other-field":
                h.p.F = 99.0
            if mode == "exception":
                raise primary from cause
    assert stage.parameters._CONSTRUCTED[h.owner] is claim
    assert claim.record.succeeded is False
    context = stage.failed_context(claim)
    assert context.claim is claim and context.owner is h.owner and context.p is h.p
    assert context.record is claim.record and not context.active
    if mode == "exception":
        assert caught.value is primary and primary.__cause__ is cause
        assert primary.world_construction_claim is claim
        assert context.source_error is primary
    with pytest.raises(stage.WorldConstructionRejected):
        stage.validate_closed_seed(claim, original_owner=h.owner)


def test_prior_ancestral_construction_is_not_fresh(conditional, monkeypatch):
    h = conditional
    monkeypatch.setitem(stage.claims._CONSTRUCTED, h.seven, True)
    with pytest.raises(ValueError, match="prior phase") as caught:
        with h.enter():
            pass
    claim = caught.value.world_construction_claim
    assert claim.record.succeeded is False and stage.parameters._CONSTRUCTED[h.owner] is claim
    assert stage.failed_context(claim).source_error is caught.value


def test_fallible_consumer_seal_stays_inside_claim_and_cannot_publish(conditional):
    h = conditional
    primary, cause = (
        SyntheticSourceFailure("conditional phase sealing"),
        SyntheticSourceCause("cause"),
    )
    sealed, published = [], []

    def seal_inside(claim):
        assert claim.parameters is h.p
        claim.check()
        sealed.append((claim, h.owner, h.p))
        raise primary from cause

    with pytest.raises(SyntheticSourceFailure) as caught:
        with h.enter() as claim:
            assert claim.parameters is h.p
            h.p._run_sim = False
            seal_inside(claim)
        # No publication until after successful closure and exact record check.
        record = stage.validate_closed_seed(claim, original_owner=h.owner)
        assert record is claim.record
        published.append(record)
    assert caught.value is primary and primary.__cause__ is cause
    assert sealed == [(claim, h.owner, h.p)] and published == []
    context = stage.failed_context(primary.world_construction_claim)
    assert context.source_error is primary and context.p is h.p
    assert context.record is claim.record and context.record.succeeded is False
    assert stage.parameters._CONSTRUCTED[h.owner] is claim
    with pytest.raises(stage.WorldConstructionRejected):
        stage.validate_closed_seed(claim, original_owner=h.owner)


def test_swallowed_reentry_cannot_issue_closed_success(conditional):
    h = conditional
    with pytest.raises(stage.WorldConstructionRejected):
        with h.enter() as claim:
            with pytest.raises(stage.WorldConstructionRejected):
                with h.enter():
                    pass
            h.p._run_sim = False
    assert claim.record.succeeded is False


def test_observed_seed_flag_cannot_disappear_and_recreate_after_caught_refusal(conditional):
    h = conditional
    with pytest.raises(stage.WorldConstructionRejected):
        with h.enter() as claim:
            h.p._run_sim = False
            claim.check()
            del h.p._run_sim
            with pytest.raises(ValueError, match="SEED flag disappeared"):
                claim.check()
            h.p._run_sim = False
            with pytest.raises(stage.WorldConstructionRejected, match="poisoned"):
                claim.check()
    context = stage.failed_context(claim)
    assert context.seed_flag_observed and context.invalid
    assert context.record is claim.record and claim.record.succeeded is False
    with pytest.raises(stage.WorldConstructionRejected):
        stage.validate_closed_seed(claim, original_owner=h.owner)


@pytest.mark.parametrize("mode", ["owner", "registry", "record", "protected-data", "seed-flag"])
def test_closed_lifetime_refuses_stale_edges_without_reopening(conditional, mode):
    h = conditional
    with h.enter() as claim:
        h.p._run_sim = False
    original = claim.record
    owner = h.owner
    if mode == "owner":
        owner = object.__new__(stage.parameters.WorldReadyParametersOwner)
    elif mode == "registry":
        del stage.parameters._CONSTRUCTED[h.owner]
    elif mode == "record":
        stage._ISSUED[claim].record = replace(original)
    elif mode == "protected-data":
        h.p.wsx = 99.0
    else:
        h.p._run_sim = True
    with pytest.raises(stage.WorldConstructionRejected):
        stage.validate_closed_seed(claim, original_owner=owner)


def test_software_launch_remains_explicitly_held(monkeypatch, tmp_path):
    monkeypatch.delenv(runner.SOFTWARE_RELEASE, raising=False)
    with pytest.raises(ValueError, match="remains held"):
        runner.software(tmp_path / "missing", tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_worker_routes_only_through_shared_owned_frozen_authorization(monkeypatch, tmp_path):
    observed = []

    def authenticated(output, authorization, pin, *, file, entry_path):
        observed.append((output, authorization, pin, file, entry_path))
        return "conditional-no-pytest-entry"

    monkeypatch.setattr(runner.reused, "_child", authenticated)
    output, authorization = tmp_path / "held", tmp_path / "authorization"
    assert (
        runner.child(output, authorization=authorization, authorization_sha256="conditional-pin")
        == "conditional-no-pytest-entry"
    )
    assert observed == [(output, authorization, "conditional-pin", runner.FILE, runner.__file__)]
