"""Conditional same-p dataflow; original constants/getters/float remain held."""

import ast
import builtins
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_initializer_constants as stage
from cells.processes import betse_native_parameter_load_remainder as remainder
from tests.unit import test_betse_native_parameter_colormap_load as earlier
from tests.unit import test_betse_native_parameter_subconfigurations as roots
from validation.betse import betse_native_parameter_initializer_constants_software as runner
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

blocked = earlier.blocked
prevent_reference_execution = earlier.prevent_reference_execution
ORIGINAL_PLOT, ORIGINAL_COMPILE = stage._plot, stage._compile


@pytest.fixture
def conditional_grant_contract(monkeypatch, tmp_path):
    """Private contract data only; never native birth, parsed YAML or an admitted parent.

    The initial native validator is replaced explicitly. Its real typed/raw
    authority is still mandatory in production and remains unreleased.
    """

    class DataOwner:
        pass

    class ConditionalYaml:
        pass

    cfg = {"internal parameters": {"declared": "unexecuted"}}
    p = SimpleNamespace(_conf=cfg, vol_env=float("1.0"), wsx=2.0, wsy=3.0, cell_radius=0.25)
    owner = object.__new__(stage.ConstantsOwner)
    cm_owner, mod_owner, grn_owner, seven_owner, source_owner = (DataOwner() for _ in range(5))
    loaded = SimpleNamespace(owner=seven_owner, p=p)
    grn = SimpleNamespace(owner=grn_owner, p=p, authority=SimpleNamespace(loaded=loaded))
    mod = SimpleNamespace(
        owner=mod_owner,
        p=p,
        parent=grn,
        birth=SimpleNamespace(source=SimpleNamespace(yaml=ConditionalYaml)),
        runtime=SimpleNamespace(runtime_types=()),
    )
    cm = SimpleNamespace(owner=cm_owner, p=p, parent=mod, source_owner=source_owner)
    source_plan = dict(conditional_contract=True, original_source_entries=0)
    graph = stage.prefix.graphs.capture(vars(p), yaml_base=ConditionalYaml, runtime_types=())
    # Typed conditional observations only, never an actual colormap result or
    # a replacement for the deliberately stubbed initial authority validator.
    cm_trial = stage.previous.Trial(
        "conditional-registry",
        "conditional-boundary",
        "conditional-modulator",
        stage._digest(graph[1]),
        stage._digest(graph[1]),
        (),
        (),
        (),
        True,
        "",
    )
    cm_trial = replace(
        cm_trial, identity=stage._digest(stage.previous.trial_record(cm_trial))
    )
    cm.trial = cm.original_trial = cm_trial
    trial = stage.Trial(
        cm.trial.identity,
        stage._digest(graph[1]),
        stage._digest(graph[1]),
        stage._digest(source_plan),
        (),
        (),
        (),
        True,
        "",
    )
    trial = replace(trial, identity=stage._digest(stage.trial_record(trial)))
    source_guard = SimpleNamespace(
        thread=stage.get_ident(), active=False, invalid=False, audit_ready=True
    )

    def source(self):
        raise AssertionError("No native source/function may run")

    base = SimpleNamespace(
        owner=owner,
        parent_owner=cm_owner,
        parent=cm,
        parent_trial=cm.trial,
        p=p,
        guard=source_guard,
        thread=stage.get_ident(),
        active=False,
        validating=False,
        invalid=False,
        retired=True,
        source_completed=True,
        source_error=None,
        capture_errors=(),
        observation_errors=(),
        trial=trial,
        original_trial=trial,
        work=[],
        metadata_work=[],
        validations=[],
        before_graph=graph,
        after_graph=graph,
        plot=object(),
        function=source,
        historical={},
        historical_bindings={},
        parent_refs=(),
        plan=source_plan,
        source_identity=trial.source_identity,
        source_return_graph=graph,
        locals=dict(iu=cfg["internal parameters"]),
    )
    cm_marker, flags, calls = object(), {}, []

    def validate(actual):
        calls.append(actual)
        if flags.get("forbid_parent"):
            raise AssertionError("Closed history replayed stale initial validator")
        if flags.get("primary") is not None:
            raise flags["primary"]
        assert actual is owner and stage._ISSUED.get(actual) is base
        return base

    def same_cm(actual, expected):
        assert actual is cm_marker and expected is cm_marker

    monkeypatch.setattr(stage, "_validate_state", validate)
    monkeypatch.setattr(stage, "source_plan", lambda: source_plan)
    monkeypatch.setattr(stage, "_cm_graph", lambda parent: cm_marker)
    monkeypatch.setattr(stage, "_same_cm", same_cm)
    for mapping, key, value in (
        (stage._ISSUED, owner, base),
        (stage._CONSUMED, cm_owner, base),
        (stage._CLAIMED, source_owner, base),
        (stage.previous._ISSUED, cm_owner, cm),
        (stage.previous.mod._ISSUED, mod_owner, mod),
        (stage.previous.mod.previous._ISSUED, grn_owner, grn),
        (stage.previous.mod.subconfigs._ISSUED, seven_owner, loaded),
    ):
        monkeypatch.setitem(mapping, key, value)
    for gate in (stage.RELEASE, stage.previous.RELEASE, stage.previous.mod.RELEASE):
        monkeypatch.setenv(gate, "1")
    base.function_bindings = stage.prefix._function_bindings(source)
    base.bindings = stage._bindings()
    scope = stage._remainder_scope()

    def finish():
        p.wsx, p.wsy = 4.0, 5.0  # Declared control values, never a native geometry calculation.
        for name in scope["append_orders"][0]:
            setattr(p, name, 1.0)

    evidence_errors = []

    def retain(label, *, grant=None, primary=None):
        # Bounded forensic data, not a validator or a serialized live owner.
        # Never inspect grant.record: a failed entry may have no public record.
        try:
            entry = stage._REMAINDER_ISSUED.get(grant) if grant is not None else None
            context = entry[0] if entry is not None else None
            fields = vars(context) if context is not None else {}
            record = fields.get("record")
            save(
                tmp_path,
                label,
                dict(
                    conditional_contract_only=True,
                    native_parent_or_successful_grant_inferred=False,
                    parent_trial=cm.trial,
                    constants_trial=trial,
                    parent_trial_is_retained=base.parent_trial is cm.trial,
                    parent_identity_matches=trial.parent_identity == cm.trial.identity,
                    parameter_names=tuple(vars(p)),
                    source_context_fields=tuple(vars(base)),
                    primary=primary,
                    partial=dict(
                        grant_present=grant is not None,
                        actual_issued_entry=entry is not None,
                        stage=fields.get("stage"),
                        active=fields.get("active"),
                        entered=fields.get("entered"),
                        invalid=fields.get("invalid"),
                        parent_verified=fields.get("parent_verified"),
                        source_error=fields.get("source_error"),
                        effective_primary=fields.get("effective_primary"),
                        first_refusal=fields.get("first_refusal"),
                        capture_errors=fields.get("capture_errors", ())[:16],
                        work=tuple(fields.get("work", ())[:16]),
                        work_count=len(fields.get("work", ())),
                        validation_work=tuple(fields.get("validation_work", ())[:16]),
                        validation_work_count=len(fields.get("validation_work", ())),
                        evidence_prefix_limit=16,
                        complete_live_context_transport=False,
                        record_identity=record.identity if record is not None else None,
                        record_succeeded=record.succeeded if record is not None else None,
                        record_failure_type=record.failure_type if record is not None else None,
                    ),
                ),
            )
        except BaseException as secondary:
            if primary is None:
                raise
            # Preserve the original failing operation even if evidence I/O
            # also fails; leave partial files and retain the secondary error.
            evidence_errors.append((label, secondary))
            try:
                primary.conditional_grant_evidence_errors = tuple(evidence_errors)
            except BaseException as attachment:
                evidence_errors.append(("evidence_error_attachment", attachment))

    retain("conditional-grant-input")
    return SimpleNamespace(
        p=p,
        owner=owner,
        base=base,
        loaded=loaded,
        scope=scope,
        flags=flags,
        calls=calls,
        finish=finish,
        retain=retain,
        evidence_errors=evidence_errors,
        factory=lambda: stage.remainder_handoff(
            owner, law_id=stage.REMAINDER_HANDOFF_LAW, enabled=True
        ),
    )


def test_remainder_handoff_scope_matches_original_tail_profile_and_balance_ast_without_calls(
    monkeypatch,
):
    # Exact fresh-source connections do not issue an actual native parent.
    edges = (
        (stage.previous.state, "PREVIOUS_SHA256", stage.previous.boundary),
        (stage.previous, "STATE_SHA256", stage.previous.state),
        (stage, "PREVIOUS_SHA256", stage.previous),
        (remainder, "HANDOFF_PRODUCER_SHA256", stage),
    )
    for consumer, field, provider in edges:
        digest = hashlib.sha256(Path(provider.__file__).read_bytes()).hexdigest()
        assert getattr(consumer, field) == digest
    assert remainder._hook() is stage
    assert stage.source_plan()["previous_producer"] == stage.PREVIOUS_SHA256
    assert remainder.source_plan()["runtime_hook_available"] is True
    checks = (
        (stage.previous.state, "PREVIOUS_SHA256", stage.previous.state.source_plan,
         ValueError, "Exact explicitly bound colormap input producer required"),
        (stage.previous, "STATE_SHA256", stage.previous.source_plan,
         ValueError, "Exact selected-registry source producer required"),
        (stage, "PREVIOUS_SHA256", stage.source_plan,
         ValueError, "Explicit original four-colormap producer required"),
        (remainder, "HANDOFF_PRODUCER_SHA256", remainder._hook,
         remainder.LoadRejected, "Explicit hook producer mismatch"),
    )
    issued_before = (len(stage._ISSUED), len(remainder._ISSUED), len(remainder._CONSUMED))
    for consumer, field, check, error_type, reason in checks:
        with monkeypatch.context() as changed:
            changed.setattr(consumer, field, "0" * 64)
            with pytest.raises(error_type, match=reason):
                check()
    for gate in (stage.RELEASE, remainder.RELEASE):
        monkeypatch.delenv(gate, raising=False)
    with pytest.raises(stage.ConstantsRejected) as constants_refusal:
        stage.prepare(None, law_id=stage.LAW_ID, enabled=True)
    with pytest.raises(remainder.LoadRejected) as remainder_refusal:
        remainder.complete_load(None, law_id=remainder.LAW_ID, enabled=True)
    assert constants_refusal.value.stage == remainder_refusal.value.stage == "release"
    assert issued_before == (len(stage._ISSUED), len(remainder._ISSUED), len(remainder._CONSUMED))
    scope = stage._remainder_scope()
    _, _, _, tail, ion, balance = remainder._source()
    assert scope["statement_slice"] == (203, 218)
    assert scope["profiles"] == tuple(
        (name, fields) for name, fields, _ in remainder._branches(ion)
    )
    assert scope["tail_ast"] == stage._digest(ast.dump(ast.Module(body=tail, type_ignores=[])))
    assert scope["balance_ast"] == stage._digest(ast.dump(balance))
    assert scope["replaced"] == ("wsx", "wsy")
    assert not scope["permits_source_execution"] and not scope["permits_phase_or_INIT"]
    assert all(
        "vol_env" not in order and "_run_sim" not in order for order in scope["append_orders"]
    )


def test_remainder_handoff_reserves_before_fallible_validation_and_never_rearms(
    conditional_grant_contract,
):
    h = conditional_grant_contract
    primary = SyntheticSourceFailure("conditional initial authority refusal")
    cause = SyntheticSourceCause("conditional cause")
    primary.__cause__ = cause
    h.flags["primary"] = primary
    grant = h.factory()
    assert stage._REMAINDER_CONSUMED[h.owner] is stage._remainder_context(grant)
    with pytest.raises(SyntheticSourceFailure) as caught:
        grant.__enter__()
    assert caught.value is primary and caught.value.__cause__ is cause
    assert primary.remainder_grant is grant and grant.record.succeeded is False
    assert grant.record.parent_identity == h.base.original_trial.identity
    assert grant.record.parent_verified is False
    assert not stage._REMAINDER_ACTIVE and not stage._remainder_context(grant).active
    with pytest.raises(stage.ConstantsRejected, match="consumed"):
        h.factory()
    with pytest.raises(stage.ConstantsRejected) as retired:
        stage._validate(h.owner)
    assert retired.value.stage == "remainder_retired" and h.calls == [h.owner]


def test_remainder_handoff_conditional_active_closed_identity_and_history_without_replay(
    conditional_grant_contract,
):
    h = conditional_grant_contract
    grant = None
    try:
        original_trial = h.base.trial
        assert type(h.base.parent.trial) is stage.previous.Trial
        assert h.base.parent_trial is h.base.parent.trial
        assert original_trial.parent_identity == h.base.parent_trial.identity
        grant = h.factory()
        with grant as active:
            assert active is grant and grant.parameters is h.p and grant.check() is h.p
            with pytest.raises(stage.ConstantsRejected):
                _ = grant.record
            h.finish()
            grant.check()
        # Save closure before assertions so a refused or incomplete entry is
        # never lost merely because an intended success assertion failed.
        h.retain("conditional-grant-closed", grant=grant)
        record = grant.record
        assert record.parent_verified is True
        assert record.succeeded and record is stage.validate_remainder_history(
            grant, original_owner=h.owner
        )
        assert record.work and h.base.trial is original_trial and h.base.retired is True
        h.flags["forbid_parent"] = True
        h.p._run_sim = False  # History grants no authority for this later SEED mutation.
        assert stage.validate_remainder_history(grant, original_owner=h.owner) is record
        assert h.calls == [h.owner]
        with pytest.raises(stage.ConstantsRejected):
            _ = grant.parameters
        assert (
            grant.record is record
            and stage.validate_remainder_history(grant, original_owner=h.owner) is record
        )
        assert not stage._REMAINDER_ACTIVE
    except BaseException as primary:
        h.retain("conditional-grant-first-failure", grant=grant, primary=primary)
        raise


@pytest.mark.parametrize(
    "drift", ["guard", "before", "work", "bindings", "trial", "thread", "audit", "consumption"]
)
def test_remainder_handoff_closed_history_refuses_original_edge_drift(
    conditional_grant_contract, drift
):
    h = conditional_grant_contract
    grant = h.factory()
    with grant:
        h.finish()
    record = grant.record
    if drift == "guard":
        h.base.guard = SimpleNamespace(**vars(h.base.guard))
    elif drift == "before":
        h.base.before_graph = tuple(list(h.base.before_graph))
    elif drift == "work":
        h.base.work = list(h.base.work)
    elif drift == "bindings":
        h.base.bindings = tuple(list(h.base.bindings))
    elif drift == "trial":
        h.base.trial = replace(h.base.trial)
    elif drift == "thread":
        h.base.thread += 1
    elif drift == "audit":
        h.base.guard.audit_ready = False
    elif drift == "consumption":
        stage._REMAINDER_CONSUMED.pop(h.owner)
    with pytest.raises((ValueError, stage.ConstantsRejected)):
        stage.validate_remainder_history(grant, original_owner=h.owner)
    assert record.succeeded  # Original immutable historical record is never rewritten as a retry.


@pytest.mark.parametrize(
    "drift", ["old-field", "config", "volume", "foreign-store", "order", "phase"]
)
def test_remainder_handoff_rejects_undeclared_changes_and_keeps_failed_prefix(
    conditional_grant_contract, drift
):
    h = conditional_grant_contract
    grant = h.factory()
    with pytest.raises((ValueError, stage.ConstantsRejected)):
        with grant:
            if drift == "old-field":
                h.p.cell_radius = float("0.25")
            elif drift == "config":
                h.p._conf = dict(h.p._conf)
            elif drift == "volume":
                h.p.vol_env = float("1.0")
            elif drift == "foreign-store":
                h.p.supplied_store = 1.0
            elif drift == "order":
                setattr(h.p, h.scope["append_orders"][0][1], 1.0)
            elif drift == "phase":
                h.p._run_sim = False
            grant.check()
    assert grant.record.succeeded is False and not stage._REMAINDER_ACTIVE


def test_remainder_handoff_ancestral_constructor_marker_is_not_reset(
    conditional_grant_contract, monkeypatch
):
    h = conditional_grant_contract
    marker = object()
    monkeypatch.setitem(stage.claims._CONSTRUCTED, h.loaded.owner, marker)
    grant = h.factory()
    with pytest.raises(ValueError, match="unconstructed"):
        grant.__enter__()
    assert stage.claims._CONSTRUCTED[h.loaded.owner] is marker and grant.record.succeeded is False


def test_remainder_handoff_reentry_poison_is_irreversible(conditional_grant_contract):
    h = conditional_grant_contract
    grant = h.factory()
    with pytest.raises(stage.ConstantsRejected):
        with grant:
            with pytest.raises(stage.ConstantsRejected):
                h.factory()
            h.finish()
    assert grant.record.succeeded is False and not stage._REMAINDER_ACTIVE


def test_remainder_handoff_entry_lock_refuses_without_wait_or_verification(
    conditional_grant_contract,
):
    h = conditional_grant_contract
    grant = h.factory()
    assert stage._REMAINDER_LOCK.acquire(blocking=False)
    try:
        with pytest.raises(stage.ConstantsRejected, match="reservation busy"):
            grant.__enter__()
    finally:
        stage._REMAINDER_LOCK.release()
    context = stage._remainder_context(grant)
    assert context.entered and context.invalid and context.active is False
    assert context.work == [] and h.calls == [] and not stage._REMAINDER_ACTIVE
    with pytest.raises(stage.ConstantsRejected, match="already attempted"):
        grant.__enter__()
    assert h.calls == []


def test_remainder_handoff_record_capture_error_preserves_primary_and_cause(
    conditional_grant_contract, monkeypatch
):
    h = conditional_grant_contract
    primary, secondary = SyntheticSourceFailure("primary"), SyntheticCaptureFailure("capture")
    cause = SyntheticSourceCause("cause")
    primary.__cause__ = cause
    original = stage.remainder_record_document
    fail = []

    def document(record):
        if fail:
            raise secondary
        return original(record)

    monkeypatch.setattr(stage, "remainder_record_document", document)
    h.base.bindings = stage._bindings()
    grant = h.factory()
    with pytest.raises(SyntheticSourceFailure) as caught:
        with grant:
            fail.append(True)
            raise primary
    context = stage._remainder_context(grant)
    assert caught.value is primary and primary.__cause__ is cause
    assert ("record_capture", secondary) in context.capture_errors and context.record is None
    assert not context.active and not stage._REMAINDER_ACTIVE


def test_remainder_handoff_caught_restore_cannot_erase_first_active_refusal(
    conditional_grant_contract,
):
    h = conditional_grant_contract
    grant = h.factory()
    original = h.p.cell_radius
    first = []
    with pytest.raises(stage.ConstantsRejected) as closure:
        with grant:
            h.p.cell_radius = float("0.25")
            with pytest.raises(ValueError, match="field replacement") as caught:
                grant.check()
            first.append(caught.value)
            h.p.cell_radius = original
            h.finish()
    context = stage._remainder_context(grant)
    assert context.first_refusal is first[0] and context.invalid and context.guard.invalid
    assert closure.value.__cause__ is first[0] and grant.record.succeeded is False


def test_remainder_handoff_closed_restore_cannot_erase_first_history_refusal(
    conditional_grant_contract,
):
    h = conditional_grant_contract
    grant = h.factory()
    with grant:
        h.finish()
    record, original = grant.record, h.base.guard
    assert stage.validate_remainder_history(grant, original_owner=h.owner) is record
    h.base.guard = SimpleNamespace(**vars(original))
    with pytest.raises(ValueError) as first:
        stage.validate_remainder_history(grant, original_owner=h.owner)
    h.base.guard = original
    with pytest.raises(stage.ConstantsRejected):
        stage.validate_remainder_history(grant, original_owner=h.owner)
    assert stage._remainder_context(grant).first_refusal is first.value
    assert grant.record is record and record.succeeded


def test_remainder_handoff_swallowed_recursive_history_poisons_outer_validation(
    conditional_grant_contract,
    monkeypatch,
):
    h = conditional_grant_contract
    actual = stage._remainder_history
    switches, nested = dict(recurse=False, claim=None), []

    def history(context):
        actual(context)
        if switches["recurse"]:
            with pytest.raises(stage.ConstantsRejected) as caught:
                stage.validate_remainder_history(switches["claim"], original_owner=h.owner)
            nested.append(caught.value)

    monkeypatch.setattr(stage, "_remainder_history", history)
    h.base.bindings = stage._bindings()  # Callback is installed before the grant captures bindings.
    grant = h.factory()
    switches["claim"] = grant
    with grant:
        h.finish()
    record = grant.record
    assert stage.validate_remainder_history(grant, original_owner=h.owner) is record
    assert nested == []
    switches["recurse"] = True
    with pytest.raises(ValueError, match="poisoned"):
        stage.validate_remainder_history(grant, original_owner=h.owner)
    context = stage._remainder_context(grant)
    assert len(nested) == 1 and context.first_refusal is nested[0]
    assert context.invalid and context.guard.invalid and grant.record is record


@pytest.mark.parametrize("mode", ["closure", "falsey-closure", "record-only"])
def test_remainder_handoff_closure_primary_survives_later_record_capture_failure(
    conditional_grant_contract,
    monkeypatch,
    mode,
):
    h = conditional_grant_contract

    class FalseyFailure(SyntheticCaptureFailure):
        def __bool__(self):
            return False

    first = (
        FalseyFailure("first closure")
        if mode == "falsey-closure"
        else SyntheticCaptureFailure("first closure")
    )
    secondary = SyntheticCaptureFailure("record capture")
    capture, document = stage._remainder_capture, stage.remainder_record_document
    enabled = []

    def capture_fault(context, values, phase):
        if enabled and phase == "closed_new_values" and mode != "record-only":
            raise first
        return capture(context, values, phase)

    def document_fault(record):
        if enabled:
            raise secondary
        return document(record)

    monkeypatch.setattr(stage, "_remainder_capture", capture_fault)
    monkeypatch.setattr(stage, "remainder_record_document", document_fault)
    h.base.bindings = stage._bindings()  # Both callbacks predate validation/binding.
    grant = h.factory()
    with pytest.raises(stage.ConstantsRejected) as caught:
        with grant:
            h.finish()
            enabled.append(True)
    context = stage._remainder_context(grant)
    expected = secondary if mode == "record-only" else first
    assert caught.value.__cause__ is expected and caught.value.source_error is expected
    assert context.effective_primary is expected and context.record is None
    assert ("record_capture", secondary) in context.capture_errors
    if mode != "record-only":
        assert context.closure_error is first and ("scope_closure", first) in context.capture_errors
    assert not context.active and not stage._REMAINDER_ACTIVE


@pytest.mark.parametrize("slots", [0, 1, 2, 3])
def test_remainder_handoff_every_history_row_respects_exact_declared_budget(
    conditional_grant_contract,
    monkeypatch,
    slots,
):
    h = conditional_grant_contract
    monkeypatch.setattr(stage, "MAX_WORK", 32)
    h.base.bindings = stage._bindings()  # Small declared budget, not post-issue constant drift.
    grant = h.factory()
    with grant:
        h.finish()
    context, record = stage._remainder_context(grant), grant.record
    while len(context.work) + len(context.validation_work) < 32 - slots:
        stage._remainder_work(context, True, "declared_padding", "software_metadata_only")
    before = len(context.validation_work)
    if slots == 3:
        assert stage.validate_remainder_history(grant, original_owner=h.owner) is record
        assert context.invalid is False
    else:
        with pytest.raises(stage.ConstantsRejected) as refusal:
            stage.validate_remainder_history(grant, original_owner=h.owner)
        assert refusal.value.stage == "grant_work" and context.first_refusal is refusal.value
        assert context.invalid and context.refusals
    assert len(context.work) + len(context.validation_work) == 32
    assert len(context.validation_work) - before == slots
    assert record is grant.record and record.succeeded


def test_remainder_handoff_runner_routes_each_consumer_control_to_its_actual_file():
    assert len(runner.HANDOFF_CONSUMER_TARGETS) == 3
    for target in runner.HANDOFF_CONSUMER_TARGETS:
        assert target in runner.TARGETS
        assert runner._target(target) == runner.HANDOFF_CONSUMER_TEST + "::" + target
    for target in runner.HANDOFF_TARGETS:
        assert runner._target(target) == runner.TEST + "::" + target
    for target in runner.HANDOFF_READER_TARGETS:
        assert runner._target(target) == runner.HANDOFF_CONSUMER_TEST + "::" + target
    assert not any(target in runner.HANDOFF_CONSUMER_TARGETS for _, target in runner.BATCH)


class ConditionalAlias:
    def __init__(self, key):
        self.key = key

    def __get__(self_descriptor, self, cls):
        if self is None:
            return self_descriptor
        return self._conf["results options"]["after solving"]["plots"][self_descriptor.key]


def plot_model(context):
    value = vars(context.p)["plot"]
    cls = type(value)
    rows, refs = [], [value, cls]
    for name in ("is_after_sim_show", "is_after_sim_save"):
        descriptor = vars(cls)[name]
        function = vars(type(descriptor))["__get__"]
        rows.append((name, descriptor, function))
        refs.extend(
            (descriptor, *stage.prefix.parameters.inherited.tissue._surface(type(descriptor)))
        )
        refs.extend(stage.prefix._function_bindings(function)[1])
    return SimpleNamespace(plot=value, cls=cls, rows=tuple(rows), bindings=((), tuple(refs)))


@pytest.fixture
def controlled(monkeypatch, tmp_path):
    initial = roots.controlled.__wrapped__

    def configured(*args, **kwargs):
        h = initial(*args, **kwargs)
        h.cfg["results options"].update(
            {
                "plot cutlines": False,
                "plot networks": False,
                "vector and stream color": "black",
                "plot networks single cell": False,
                "show cells": True,
                "streamline density": 1.0,
                "plot total current": False,
                "plot masked geometry": False,
            }
        )
        h.cfg["results options"]["after solving"]["plots"].update(show=False, save=True)
        h.cfg["internal parameters"] = {"declared-only": "not numerically evaluated"}
        cls = type(h.p.plot)
        cls.is_after_sim_show = ConditionalAlias("show")
        cls.is_after_sim_save = ConditionalAlias("save")
        return h

    monkeypatch.setattr(roots.controlled, "__wrapped__", configured)
    prior = earlier.controlled.__wrapped__(monkeypatch, tmp_path, SimpleNamespace())
    parent = prior.run()
    owner_context = stage.previous._ISSUED[parent]
    plan = stage.source_plan()
    hooks, flags = {}, {}
    primary, cause = (
        SyntheticSourceFailure("conditional constants source"),
        SyntheticSourceCause("cause"),
    )
    values = {name: 1.0 for name in plan["stores"]}
    values.update(turn_all_plots_off=True, autosave=True)

    def driver(self):
        if "before" in hooks:
            hooks["before"]()
        ro = self._conf["results options"]
        iu = self._conf["internal parameters"]
        self.turn_all_plots_off = not self.plot.is_after_sim_show
        self.autosave = self.plot.is_after_sim_save
        for name in plan["stores"][2:]:
            if name == flags.get("fail_at"):
                raise primary from cause
            if name == flags.get("skip"):
                continue
            setattr(self, name, values[name])
        if flags.get("wrong_ro"):
            ro = dict(ro)
        if flags.get("wrong_iu"):
            iu = dict(iu)
        if "after" in hooks:
            hooks["after"]()
        assert ro is not None and iu is not None

    monkeypatch.setattr(stage, "_compile", lambda context: driver)
    monkeypatch.setattr(stage, "_plot", plot_model)
    monkeypatch.setenv(stage.RELEASE, "1")
    return SimpleNamespace(
        prior=prior,
        parent=parent,
        parent_context=owner_context,
        p=prior.p,
        plan=plan,
        hooks=hooks,
        flags=flags,
        primary=primary,
        cause=cause,
        driver=driver,
        run=lambda: stage.prepare(parent, law_id=stage.LAW_ID, enabled=True),
    )


def empty():
    assert not stage._ACTIVE
    assert stage._LOCK.acquire(blocking=False)
    stage._LOCK.release()
    earlier.empty()


def test_source_scope_stops_before_geometry_and_ions():
    plan = stage.source_plan()
    assert plan["statement_slice"] == (139, 203) and plan["source_lines"] == (1017, 1125)
    assert plan["next_source_line"] == 1127 and len(plan["stores"]) == 62
    assert plan["native_float_site_count"] == 10 and not plan["supplied_configuration"]
    assert not plan["geometry_ion_profile_phase_Simulator_INIT_admitted"]
    assert not plan["predecessor_source_acceptance_inferred"]
    fns, descriptions = stage._historical()
    assert set(fns) == {"_history", "_outputs"} and len(descriptions) == 2
    for name, fn in fns.items():
        original = vars(stage.previous)[name]
        assert fn.__globals__ is original.__globals__ and fn.__builtins__ is original.__builtins__


@pytest.mark.parametrize("mode", ["default", "integer", "local", "colormap", "modulator", "law"])
def test_all_release_gates_precede_authority_or_work(monkeypatch, mode):
    for gate in (stage.RELEASE, stage.previous.RELEASE, stage.previous.mod.RELEASE):
        monkeypatch.setenv(gate, "1")
    if mode in ("local", "colormap", "modulator"):
        gate = {
            "local": stage.RELEASE,
            "colormap": stage.previous.RELEASE,
            "modulator": stage.previous.mod.RELEASE,
        }[mode]
        monkeypatch.setenv(gate, "0")
    enabled = False if mode == "default" else 1 if mode == "integer" else True
    with pytest.raises(stage.ConstantsRejected) as caught:
        stage.prepare(None, law_id="foreign" if mode == "law" else stage.LAW_ID, enabled=enabled)
    assert caught.value.stage == ("law" if mode == "law" else "release")
    empty()


def test_actual_source_compilation_is_metadata_only():
    module = ModuleType("conditional-original-constants-namespace")
    module.__dict__["__builtins__"] = vars(builtins)

    def forbidden(self):
        raise AssertionError("Original body cannot execute in metadata control")

    original = FunctionType(forbidden.__code__, vars(module), "load")
    context = SimpleNamespace(parent=SimpleNamespace(bound=SimpleNamespace(original=original)))
    fn = ORIGINAL_COMPILE(context)
    path, _, _, selected = stage._ast()
    # Compare extracted code with the pinned exact AST at its original locations.
    _, original_cls, _, _ = stage._ast()
    stage.prefix.parameters.inherited._method(original_cls, "load").body = selected
    expected = stage.prefix.parameters._method_code(original_cls, "load", str(path))
    assert stage.prefix.parameters.inherited._code(
        fn.__code__
    ) == stage.prefix.parameters.inherited._code(expected)
    assert fn.__globals__ is vars(module) and fn.__builtins__ is original.__builtins__
    assert "d_cell" not in fn.__code__.co_names and "_load_ion_profile" not in fn.__code__.co_names


@pytest.mark.parametrize(
    "mode", ["valid", "foreign-plot", "equal-config", "descriptor", "shadow", "birth-class"]
)
def test_plot_metadata_requires_original_birth_wrapper_config_and_dispatch(monkeypatch, mode):
    class Plot:
        is_after_sim_show = ConditionalAlias("show")
        is_after_sim_save = ConditionalAlias("save")

    plot = object.__new__(Plot)
    conf = {"results options": {"after solving": {"plots": dict(show=False, save=True)}}}
    plot._conf = conf
    p = SimpleNamespace(_conf=conf, plot=plot)
    native = stage.prefix.parameters.inherited.tissue.aliases.NATIVE
    frame = dict(self=p, SimConfExportPlots=Plot, __class__=type(p))
    birth = SimpleNamespace(
        source=SimpleNamespace(cls=type(p)),
        source_completed=True,
        trial=SimpleNamespace(source_completed=True),
        graph=((p, plot), {}),
        locals={(str(native / stage.prefix.parameters.PARAMETERS), "Parameters.__init__"): frame},
    )
    owner = object.__new__(stage.previous.mod.subconfigs.SubconfigurationsOwner)
    loaded = SimpleNamespace(
        owner=owner,
        p=p,
        parent=SimpleNamespace(parent=birth),
        authority=SimpleNamespace(classes={"SimConfExportPlots": Plot}, objects={"plot": plot}),
        before_objects=(p, plot),
    )
    subconfigs = stage.previous.mod.subconfigs
    monkeypatch.setitem(subconfigs._ISSUED, owner, loaded)

    def bindings(context):
        return (), stage.prefix.parameters.inherited.tissue._surface(Plot)

    monkeypatch.setattr(subconfigs, "_native_bindings", bindings)
    loaded.native_bindings = bindings(loaded)
    module = ModuleType(subconfigs.MODULES["SimConfExportPlots"])
    module.__file__ = str(native / "betse/science/config/export/visual/confexpvisplot.py")
    module.SimConfExportPlots = Plot
    monkeypatch.setitem(sys.modules, module.__name__, module)
    context = SimpleNamespace(
        p=p,
        parent=SimpleNamespace(
            parent=SimpleNamespace(parent=SimpleNamespace(authority=SimpleNamespace(loaded=loaded)))
        ),
    )
    if mode == "foreign-plot":
        foreign = object.__new__(Plot)
        foreign._conf = conf
        p.plot = loaded.authority.objects["plot"] = foreign
    elif mode == "equal-config":
        plot._conf = dict(conf)
    elif mode == "descriptor":
        Plot.is_after_sim_show = ConditionalAlias("show")
    elif mode == "shadow":
        plot.is_after_sim_show = False
    elif mode == "birth-class":
        frame["SimConfExportPlots"] = type(Plot.__name__, (), {})
    if mode == "valid":
        actual = ORIGINAL_PLOT(context)
        assert actual.plot is plot and actual.cls is Plot and len(actual.rows) == 2
    else:
        with pytest.raises(ValueError):
            ORIGINAL_PLOT(context)


def test_full_conditional_continuation_and_retirement(controlled, tmp_path):
    h = controlled
    before = tuple(vars(h.p))
    result = h.run()
    context = stage._ISSUED[result]
    assert result.parameters is h.p and result.trial.source_completed
    assert context.parent.invalid and context.retired and context.entries == context.returns == 1
    assert context.plot_entries == 2 and context.plot_returns == [False, True]
    assert tuple(vars(h.p))[len(before) :] == h.plan["stores"]
    assert context.locals["ro"] is h.p._conf["results options"]
    assert context.locals["iu"] is h.p._conf["internal parameters"]
    assert not any(name in vars(h.p) for name in ("d_cell", "nx", "ny"))
    with pytest.raises(stage.ConstantsRejected) as repeated:
        h.run()
    assert repeated.value.stage == "consumed"
    with pytest.raises(stage.ConstantsRejected) as following:
        stage.require_continuation(result)
    assert following.value.partial["next_line"] == 1127
    empty()
    save(
        tmp_path,
        "conditional-constants-complete",
        dict(
            trial=stage.trial_record(context.trial),
            data=context.after_graph[1],
            metadata_work=context.metadata_work,
            validation_work=context.validations,
            p_identity_preserved=True,
            returned_colormap_graph_preserved=True,
            conditional_source_only=True,
            actual_native_float_alias_ion_entries=0,
            independent_biological_cases=0,
        ),
    )


@pytest.mark.parametrize(
    "mode", ["primary", "capture", "combined", "skipped-store", "foreign-locals"]
)
def test_conditional_primary_and_capture_failures_keep_prefix(
    controlled, monkeypatch, tmp_path, mode
):
    h = controlled
    if mode in ("primary", "combined"):
        h.flags["fail_at"] = "Do_Cl"
    if mode == "skipped-store":
        h.flags["skip"] = "Do_Cl"
    if mode == "foreign-locals":
        h.flags["wrong_ro"] = True
    if mode in ("capture", "combined"):

        def bad(frame):
            if frame.f_code is h.driver.__code__:
                raise SyntheticCaptureFailure("conditional locals capture")
            return dict(frame.f_locals)

        monkeypatch.setattr(stage, "_copy_locals", bad)
    refusal = None
    try:
        h.run()
    except BaseException as error:
        refusal = error
    context = getattr(refusal, "partial", None)
    if context is None:
        context = stage._CONSUMED.get(h.parent)
    before_names = getattr(context, "before_names", tuple(vars(h.p)))
    stores = tuple(vars(h.p))[len(before_names) :]
    # Persist before pytest can format a failed assertion. The partial graph is
    # the existing closed, bounded YAML capture, never the live owner/namespace.
    # An unexpected refusal is retained too; this is not evidence of admission.
    try:
        save(
            tmp_path,
            "conditional-constants-refusal",
            dict(
                mode=mode,
                refusal=refusal,
                refusal_stage=getattr(refusal, "stage", None),
                partial_context_present=context is not None,
                source_error=getattr(context, "source_error", None),
                operation_error=getattr(context, "operation_error", None),
                observation_errors=getattr(context, "observation_errors", ()),
                capture_errors=getattr(context, "capture_errors", ()),
                partial_graph=(
                    None
                    if getattr(context, "failure_capture", None) is None
                    else context.failure_capture[1]
                ),
                stores=stores,
                graph_capture_bounds=dict(
                    nodes=stage.prefix.graphs.MAX_NODES,
                    bytes=stage.prefix.graphs.MAX_BYTES,
                    depth=stage.prefix.graphs.MAX_DEPTH,
                ),
                raw_source_return=getattr(context, "raw_return", None) is not None,
                raw_source_return_is_none=(
                    getattr(context, "raw_return", None) is not None
                    and context.raw_return[2] is None
                ),
                no_success_record=context is None or not hasattr(context, "trial"),
                conditional_evidence_only=True,
                actual_native_entries_require_final_guard_receipts=True,
            ),
        )
    except BaseException as capture_error:
        if refusal is not None:
            _refusal_save_failures = [capture_error]  # Retained by this traceback frame.
            try:
                refusal.constants_refusal_save_error = capture_error
            except BaseException as attachment_error:
                _refusal_save_failures.append(attachment_error)
            # Keep the original refusal/cause primary if its evidence I/O fails.
            raise refusal  # noqa: B904
        raise
    assert type(refusal) is stage.ConstantsRejected
    assert context is stage._CONSUMED[h.parent] and context.invalid and not context.active
    assert context.raw_return is not None and context.raw_return[0] == "source"
    assert context.raw_return[2] is None and not hasattr(context, "trial")
    if mode in ("primary", "combined"):
        assert refusal.source_error is h.primary and h.primary.__cause__ is h.cause
        assert "Do_Na" in vars(h.p) and "Do_Cl" not in vars(h.p)
    else:
        assert context.source_completed and context.source_error is None
        if mode == "capture":
            assert context.observation_errors
        elif mode == "skipped-store":
            assert type(context.operation_error) is ValueError
            assert context.operation_error.args == (
                "Original field layout/new constants prefix changed",
            )
            assert refusal.__cause__ is context.operation_error
            assert stores == tuple(name for name in context.plan["stores"] if name != "Do_Cl")
            assert "Do_Cl" not in stores and stores != context.plan["stores"][: len(stores)]
        else:
            assert "config associations" in str(context.operation_error)
    empty()


@pytest.mark.parametrize("mode", ["old-data", "new-data", "record", "plot-descriptor"])
def test_retained_successor_refuses_drift(controlled, mode):
    h = controlled
    owner = h.run()
    context = stage._ISSUED[owner]
    assert owner.parameters is h.p
    if mode == "old-data":
        h.p.periodic_properties["frequency"] = 99.0
    elif mode == "new-data":
        h.p.Do_Na = 99.0
    elif mode == "record":
        context.trial = replace(context.trial)
    else:
        type(h.p.plot).is_after_sim_show = ConditionalAlias("show")
    with pytest.raises(stage.ConstantsRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "drift" and context.invalid
    empty()


def test_reentrant_attempt_cannot_issue_success(controlled):
    h = controlled
    observed = []

    def nested():
        try:
            h.run()
        except stage.ConstantsRejected as error:
            observed.append(error)

    h.hooks["before"] = nested
    with pytest.raises(stage.ConstantsRejected):
        h.run()
    context = stage._CONSUMED[h.parent]
    assert len(observed) == 1 and observed[0].stage == "reentrant"
    assert context.invalid and context.plot_entries == 0 and not hasattr(context, "trial")
    empty()


@pytest.mark.parametrize("target", [None, "", "foreign", 1])
def test_runner_target_validation_precedes_worker(monkeypatch, tmp_path, target):
    def forbidden(*args, **kwargs):
        raise AssertionError("No worker should be launched")

    monkeypatch.setattr(runner.callbacks, "delegate", forbidden)
    with pytest.raises(ValueError, match="declared bounded"):
        runner.software(tmp_path / "packet", tmp_path / "output", target=target)
    assert not (tmp_path / "output").exists()


def test_detached_batch_plan_is_finite_unique_single_case_only():
    assert len(runner.BATCH) == 10
    assert (
        len({label for label, _ in runner.BATCH}) == len({node for _, node in runner.BATCH}) == 10
    )
    for _, node in runner.BATCH:
        assert runner._target(node) == runner.TEST + "::" + node
        name, _, _ = node.partition("[")
        assert name in globals() and callable(globals()[name])
    assert sum(node.startswith("test_conditional_primary") for _, node in runner.BATCH) == 5
    assert sum(node.startswith("test_retained_successor") for _, node in runner.BATCH) == 4


@pytest.mark.parametrize("failed_first", [False, True])
def test_detached_batch_retains_each_terminal_without_retry(monkeypatch, tmp_path, failed_first):
    packet, output = tmp_path / "packet", tmp_path / "controller-model"
    packet.mkdir()
    (packet / "source").mkdir()
    (packet / "inputs.json").write_text(json.dumps(dict(snapshot=dict(sha256="conditional"))))
    monkeypatch.setattr(
        runner.snapshot, "verify", lambda *a, **k: dict(repository=str(tmp_path / "repo"))
    )
    selected = runner.BATCH[:2]
    monkeypatch.setattr(runner, "BATCH", selected)
    calls = []

    def model(packet_arg, directory, *, target):
        assert packet_arg == packet.resolve() and target == selected[len(calls)][1]
        calls.append(target)
        process = directory / "process"
        process.mkdir(parents=True)
        fail = failed_first and len(calls) == 1
        result = dict(
            status="failed" if fail else "completed",
            returncode=1 if fail else 0,
            conditional_controller_observation_only=True,
        )
        runner.snapshot.write_json(process / ("failure.json" if fail else "result.json"), result)
        return result

    monkeypatch.setattr(runner, "software", model)
    result = runner.batch(packet, output)
    assert calls == [node for _, node in selected] and len(result["rows"]) == 2
    assert result["status"] == ("failed" if failed_first else "completed")
    assert result["unrun"] == [] and result["saved_results_still_require_review"]
    assert result["native_or_science_release"] is False
    for label, _ in selected:
        assert (output / (label + "-terminal.json")).is_file()
    assert (output / ("failure.json" if failed_first else "result.json")).is_file()
