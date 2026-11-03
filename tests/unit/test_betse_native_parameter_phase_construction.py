"""Native-blocked parameter-contract models, with no actual phase admission.

The conditional fixture explicitly substitutes only the unavailable complete
load/runtime boundary. Local metadata functions assign declared witnesses;
they never invoke the literal/native constructor, time division or a parser.
"""

import ast
import builtins
import importlib.abc
import os
import struct
import sys
from dataclasses import replace
from enum import Enum
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_parameter_phase_construction as stage
from validation.betse import betse_native_parameter_phase_construction_software as runner


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    if os.environ.get(runner.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit CPU5 blocked-software release required")
    attempts = []
    before = (sys.getprofile(), sys.gettrace())
    saved_active, saved_failures = tuple(stage._ACTIVE), len(stage._FAILED)

    def forbidden(*args, **kwargs):
        attempts.append("native_solver_or_RNG")
        raise AssertionError("Actual native/parser/factory/solver/RNG entry forbidden")

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "betse" or fullname.startswith("betse."):
                attempts.append(fullname)
                raise AssertionError("Actual native import forbidden")

    def trace(frame, event, arg):
        if event == "call" and runner.is_forbidden_frame(frame):
            attempts.append((frame.f_code.co_filename, frame.f_code.co_name))
            raise AssertionError("Actual source/parser/native/time-law body forbidden")
        if before[1] is not None:
            before[1](frame, event, arg)
        return trace

    finder = Block()
    sys.meta_path.insert(0, finder)
    for name in (
        "random",
        "random_sample",
        "rand",
        "randn",
        "shuffle",
        "permutation",
        "seed",
        "default_rng",
        "RandomState",
        "normal",
        "uniform",
        "choice",
    ):
        monkeypatch.setattr(np.random, name, forbidden)
    for name in ("inv", "pinv", "solve", "lstsq", "svd"):
        monkeypatch.setattr(np.linalg, name, forbidden)
    sys.settrace(trace)
    try:
        yield
    finally:
        intact = sys.getprofile() is before[0] and sys.gettrace() is trace
        active_ok = tuple(stage._ACTIVE) == saved_active
        stage._ACTIVE[:] = saved_active
        del stage._FAILED[saved_failures:]
        sys.settrace(before[1])
        sys.setprofile(before[0])
        sys.meta_path.remove(finder)
        runner.snapshot.write_json(
            tmp_path / "native-blocked.json",
            dict(
                nodeid=request.node.nodeid,
                attempts=attempts,
                hooks_intact=intact,
                active_restored=active_ok,
                profile_restored=sys.getprofile() is before[0],
                trace_restored=sys.gettrace() is before[1],
                actual_native_parser_factory_RNG_or_time_division_entries=0,
                conditional_records_are_not_native_phase_or_INIT_authority=True,
            ),
        )
        assert intact and active_ok and attempts == []


def test_complete_original_timing_bodies_headers_and_source_order_are_unexecuted(tmp_path):
    plan = stage.source_plan()
    assert plan["stores"] == ("_run_sim", "dt", "resample", "total_time", "t_resample")
    assert plan["shared_reservation_code_unchanged"] and plan["shared_history_code_unchanged"]
    assert plan["native_execution_held"] and not plan["SEED_and_Seven_d9_47_interfaces_changed"]
    assert plan["native_phase_or_material_or_INIT_completion_admitted"] is False
    nodes = stage._nodes()
    code = {}
    for name, node in nodes.items():
        code[name] = stage.callbacks._code_from_node(node, str(stage.NATIVE / stage.PHASE))
        assert type(code[name]) is CodeType
        assert code[name].co_argcount == (6 if name == "__init__" else 1)
    text = ast.unparse(nodes["_init_kludge_time"])
    assert text.index("self.p.dt = self.p.init_time_step") < text.index("self.p.resample =")
    assert "self.p.t_resample = self.p.resample / self.p.dt" in text
    assert text.index("SimPhaseKind.SEED") < text.index("SimPhaseKind.INIT")
    lines = stage._store_lines()
    for kind in ("INIT", "SIM"):
        selected = [lines[(kind, name)] for name in stage.STORES]
        assert selected == sorted(selected)
    runner.snapshot.write_json(
        tmp_path / "source-only.json",
        dict(
            plan=plan,
            compiled=list(code),
            executed=False,
            ratio_evaluations=0,
        ),
    )


@pytest.mark.parametrize("mode", ["default", "integer", "local_gate", "parent_gate", "law"])
def test_release_law_refuses_before_owner_or_runtime_access(monkeypatch, mode):
    for name in (stage.RELEASE, stage.parameters.RELEASE, stage.parameters.previous.RELEASE):
        monkeypatch.setenv(name, "1")
    if mode.endswith("gate"):
        monkeypatch.setenv(stage.RELEASE if mode == "local_gate" else stage.parameters.RELEASE, "0")

    def forbidden(*args):
        raise AssertionError("No reservation/runtime work before release/law")

    monkeypatch.setattr(stage, "_RESERVE", forbidden)
    with pytest.raises(stage.PhaseConstructionRejected) as caught:
        with stage.construction(
            None,
            kind=None,
            law_id="foreign" if mode == "law" else stage.PHASE_CONSTRUCTION_LAW,
            enabled=1 if mode == "integer" else mode != "default",
        ):
            raise AssertionError("No constructor permission")
    assert caught.value.stage == ("law" if mode == "law" else "release")


@pytest.mark.parametrize("value", [None, {}, NS(), object.__new__(stage.PhaseConstructionClaim)])
def test_unissued_or_data_only_claim_cannot_supply_authority(value):
    with pytest.raises(stage.PhaseConstructionRejected):
        stage.validate_closed_phase(value, original_owner=None)
    with pytest.raises(stage.PhaseConstructionRejected):
        stage.failed_context(value)


def test_missing_genuine_native_runtime_is_explicit_without_import():
    with pytest.raises(stage.PhaseConstructionRejected) as caught:
        stage._native()
    assert caught.value.stage == "native_runtime"


@pytest.fixture
def conditional(monkeypatch):
    """Issued-map model, not an actual WorldReady/native phase prerequisite."""
    r = stage.parameters
    config = {"retained": ["unchanged", 1.0]}
    p = NS(
        _conf=config,
        config_alias=config,
        init_time_step=0.125,
        init_time_sampling=0.5,
        init_time_total=2.0,
        sim_time_step=0.25,
        sim_time_sampling=1.0,
        sim_time_total=4.0,
        init_export_dirname="/mnt/workspaces/Cells/declared/init",
        sim_export_dirname="/mnt/workspaces/Cells/declared/sim",
    )
    owner = object.__new__(r.WorldReadyParametersOwner)
    seven = object.__new__(r.previous.previous.mod.subconfigs.SubconfigurationsOwner)
    parent_owner = object.__new__(r.previous.ConstantsOwner)
    record = r.LoadRecord(
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
    record = replace(record, identity=r._digest(r.record_document(record)))

    def capture(actual, *, names=None):
        assert actual is source
        return stage.prefix.graphs.capture(
            {name: vars(p)[name] for name in (tuple(vars(p)) if names is None else names)},
            yaml_base=type(None),
            runtime_types=(),
        )

    cm = object()
    source = NS(
        owner=owner,
        p=p,
        parent_owner=parent_owner,
        parent=NS(),
        record=record,
        original_record=record,
        loaded=NS(owner=seven),
        work=[],
        bindings=object(),
        invalid=False,
    )
    source.after_graph = capture(source)
    source.after_cm = cm
    monkeypatch.setitem(r._ISSUED, owner, source)
    monkeypatch.setitem(r._CONSUMED, parent_owner, source)

    def history(actual):
        if actual is not owner or source.invalid:
            raise ValueError("Conditional immutable history changed")
        return record

    monkeypatch.setattr(r, "validate_completed_history", history)
    monkeypatch.setattr(r, "_capture", capture)
    monkeypatch.setattr(r, "_colormaps", lambda actual: cm)
    monkeypatch.setattr(
        r.previous,
        "_same_cm",
        lambda actual, saved: (
            None
            if actual is saved is cm
            else (_ for _ in ()).throw(ValueError("Colormap edge changed"))
        ),
    )

    class Kind(Enum):
        SEED = 1
        INIT = 2
        SIM = 3

    # A supplied metadata result of the local model; NO division, real phase,
    # cache, handler, constructor callback, parser or native body is evaluated.
    ratio_result = 17.0
    fault = NS(error=None)
    next_entries = []

    def next_delegate():
        next_entries.append("entered")

    class LocalPhase:
        def __init__(self, kind, p, cells=None, sim=None, callbacks=None):
            self.callbacks = callbacks
            self.cells = cells
            self.kind = kind
            self.p = p
            self.sim = sim
            self.cache = object()
            self.dyna = object()
            self._init_kludge()
            next_delegate()
            self.export_dirname = (
                p.init_export_dirname if kind is Kind.INIT else p.sim_export_dirname
            )

        def _init_kludge(self):
            self.sim.dyna = self.dyna
            self.p._run_sim = self.kind is Kind.SIM
            self._init_kludge_time()

        def _init_kludge_time(self):
            if self.kind is Kind.INIT:
                self.p.dt = self.p.init_time_step
                self.p.resample = self.p.init_time_sampling
                self.p.total_time = self.p.init_time_total
            else:
                self.p.dt = self.p.sim_time_step
                self.p.resample = self.p.sim_time_sampling
                self.p.total_time = self.p.sim_time_total
            if fault.error is not None:
                raise fault.error
            self.p.t_resample = ratio_result

    methods = {name: vars(LocalPhase)[name] for name in stage.METHODS}
    native = NS(
        cls=LocalPhase,
        enum=Kind,
        methods=methods,
        chains={name: (method,) for name, method in methods.items()},
    )
    monkeypatch.setattr(stage, "_native", lambda: native)
    monkeypatch.setattr(stage, "_native_bindings", lambda actual: ((), (native, LocalPhase, Kind)))
    tree = ast.parse(open(__file__).read())
    cls = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "LocalPhase"
    )
    nodes = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    namespace = dict(stage._store_lines.__globals__, _nodes=lambda: nodes)
    lines = FunctionType(stage._store_lines.__code__, namespace)
    # The metadata RHS is declared instead of evaluated, but its STORE_ATTR
    # line is still observed from an actual local frame under both real hooks.
    monkeypatch.setattr(stage, "_store_lines", lines)
    for name in (stage.RELEASE, r.RELEASE, r.previous.RELEASE):
        monkeypatch.setenv(name, "1")
    return NS(
        owner=owner,
        p=p,
        source=source,
        native=native,
        kind=Kind,
        ratio=ratio_result,
        fault=fault,
        next_entries=next_entries,
        seven=seven,
        enter=lambda kind=Kind.INIT: stage.construction(
            owner, kind=kind, law_id=stage.PHASE_CONSTRUCTION_LAW, enabled=True
        ),
        run=lambda kind: LocalPhase(kind, p, cells=object(), sim=NS(), callbacks=object()),
    )


@pytest.mark.parametrize("name", ["INIT", "SIM"])
def test_conditional_whole_claim_exact_order_aliases_and_closed_lifetime(
    conditional, name, tmp_path
):
    h = conditional
    kind = getattr(h.kind, name)
    with h.enter(kind) as claim:
        assert claim.parameters is h.p and claim.check() is None
        with pytest.raises(stage.PhaseConstructionRejected, match="No record before closure"):
            _ = claim.record
        actual = h.run(kind)
        assert claim.parameters is h.p and actual.p is h.p
    record = stage.validate_closed_phase(claim, original_owner=h.owner)
    assert record is claim.record and record.succeeded and record.kind == name
    assert [row[0] for row in record.stores] == list(stage.STORES)
    assert h.p._run_sim is (name == "SIM")
    assert h.p.dt is getattr(h.p, stage.TIMING_INPUTS[name][0])
    assert h.p.resample is getattr(h.p, stage.TIMING_INPUTS[name][1])
    assert h.p.total_time is getattr(h.p, stage.TIMING_INPUTS[name][2])
    assert h.p.t_resample is h.ratio and actual.sim.dyna is actual.dyna
    assert not record.actual_source_calls  # Local metadata functions only.
    assert stage.parameters._CONSTRUCTED[h.owner] is claim
    assert (
        stage.record_document(record)["phase_owner_or_material_or_completed_INIT_admitted"] is False
    )
    for operation in (lambda: claim.parameters, claim.check, lambda: stage.failed_context(claim)):
        with pytest.raises(stage.PhaseConstructionRejected):
            operation()
    with pytest.raises(stage.PhaseConstructionRejected) as caught:
        with h.enter(kind):
            pass
    assert caught.value.stage == "consumed"
    runner.snapshot.write_json(
        tmp_path / "conditional-only.json",
        dict(
            kind=name,
            observed_stores=[row[0] for row in record.stores],
            actual_time_divisions=0,
            actual_native_phase_or_INIT_owner_issued=False,
            exact_original_owner_claim_record_edges=True,
        ),
    )


@pytest.mark.parametrize("mode", ["SEED", "string", "integer", "none"])
def test_foreign_kind_cannot_relabel_or_reuse_seed(conditional, mode):
    h = conditional
    kind = {"SEED": h.kind.SEED, "string": "INIT", "integer": 2, "none": None}[mode]
    with pytest.raises(ValueError, match="original INIT/SIM") as caught:
        with h.enter(kind):
            raise AssertionError("No phase entry")
    claim = caught.value.phase_construction_claim
    assert not claim.record.succeeded and stage.failed_context(claim).p is h.p
    assert stage.parameters._CONSTRUCTED[h.owner] is claim
    assert not any(name in vars(h.p) for name in stage.STORES)


@pytest.mark.parametrize("mode", ["prior_flag", "prior_clock", "ancestral_construction"])
def test_prior_phase_or_ancestral_construction_never_becomes_fresh(conditional, monkeypatch, mode):
    h = conditional
    if mode == "ancestral_construction":
        monkeypatch.setitem(stage.claims._CONSTRUCTED, h.seven, object())
    else:
        setattr(h.p, "_run_sim" if mode == "prior_flag" else "dt", False)
    with pytest.raises(ValueError, match="genuinely fresh") as caught:
        with h.enter():
            pass
    assert not caught.value.phase_construction_claim.record.succeeded


@pytest.mark.parametrize(
    "mode", ["missing", "manual_stores", "source_error", "seal_error", "reentry"]
)
def test_failed_attempt_preserves_original_prefix_cause_and_one_shot(conditional, mode):
    h = conditional
    primary, cause = RuntimeError("original local failure"), LookupError("original cause")
    primary.__cause__ = cause
    expected = (
        RuntimeError if mode in ("source_error", "seal_error") else stage.PhaseConstructionRejected
    )
    with pytest.raises(expected) as caught:
        with h.enter() as claim:
            if mode == "manual_stores":
                h.p._run_sim = False
            if mode in ("seal_error", "reentry"):
                h.run(h.kind.INIT)
            if mode in ("source_error", "seal_error"):
                raise primary
            if mode == "reentry":
                with pytest.raises(stage.PhaseConstructionRejected):
                    with h.enter():
                        pass
    context = stage.failed_context(claim)
    assert not claim.record.succeeded and not context.active
    assert context.p is h.p and context.owner is h.owner and context.claim is claim
    assert stage.parameters._CONSTRUCTED[h.owner] is claim
    if mode in ("source_error", "seal_error"):
        assert caught.value is primary and primary.__cause__ is cause
        assert primary.phase_construction_claim is claim
    if mode == "manual_stores":
        assert vars(h.p)["_run_sim"] is False and context.assignments == []
    with pytest.raises(stage.PhaseConstructionRejected):
        stage.validate_closed_phase(claim, original_owner=h.owner)


@pytest.mark.parametrize("capture_failure", [False, True])
def test_local_helper_unwind_retains_original_four_store_prefix_and_raw_cause(
    conditional, capture_failure, tmp_path
):
    h = conditional
    primary = ZeroDivisionError("Declared local failure; no division was performed")
    cause = LookupError("retained original local cause")
    primary.__cause__ = cause
    secondary = OSError("secondary return history failure")
    h.fault.error = primary

    class FailedHistory(list):
        def append(self, value):
            raise secondary

    with pytest.raises(ZeroDivisionError) as caught:
        with h.enter() as claim:
            if capture_failure:
                stage._context(claim).raw_returns = FailedHistory()
            h.run(h.kind.INIT)
    assert caught.value is primary and caught.value.__cause__ is cause
    context = stage.failed_context(claim)
    assert context.primary is primary and context.source_error is primary
    assert [row[0] for row in context.assignments] == list(stage.STORES[:-1])
    assert tuple(vars(h.p))[-4:] == stage.STORES[:-1]
    assert "t_resample" not in vars(h.p)
    assert context.last_raw[1].f_locals["self"] is context.phase
    assert context.last_raw[2] is None
    if capture_failure:
        assert context.observation_error is secondary
        assert any(row[1] is secondary for row in context.capture_errors)
    assert not claim.record.succeeded
    runner.snapshot.write_json(
        tmp_path / "partial-source-prefix.json",
        dict(
            local_model_only=True,
            actual_divisions=0,
            retained_store_prefix=[row[0] for row in context.assignments],
            primary_identity=True,
            cause_identity=True,
            secondary_capture_failure=capture_failure,
            original_p_retained=context.p is h.p,
        ),
    )


@pytest.mark.parametrize("mode", ["flag_type", "alias", "config", "delete_recreate"])
def test_active_store_drift_is_sticky_and_refuses_continuation(conditional, mode):
    h = conditional
    with pytest.raises((ValueError, stage.PhaseConstructionRejected)):
        with h.enter() as claim:
            h.run(h.kind.INIT)
            if mode == "flag_type":
                h.p._run_sim = 0
            elif mode == "alias":
                h.p.dt = struct.unpack(">d", struct.pack(">d", h.p.dt))[0]
                assert h.p.dt == h.p.init_time_step and h.p.dt is not h.p.init_time_step
            elif mode == "config":
                h.p._conf["retained"].append("foreign")
            else:
                del h.p._run_sim
                with pytest.raises(ValueError):
                    claim.check()
                h.p._run_sim = False
            claim.check()
    assert not claim.record.succeeded
    assert stage.failed_context(claim).invalid


@pytest.mark.parametrize(
    "mode", ["owner", "claim_edge", "record", "clock", "phase", "source", "thread"]
)
def test_closed_validation_authenticates_live_ancestry_not_a_record(conditional, monkeypatch, mode):
    h = conditional
    with h.enter() as claim:
        actual = h.run(h.kind.INIT)
    assert stage.validate_closed_phase(claim, original_owner=h.owner) is claim.record
    context = stage._context(claim)
    owner = h.owner
    if mode == "owner":
        owner = object()
    elif mode == "claim_edge":
        monkeypatch.delitem(stage.parameters._CONSTRUCTED, h.owner)
    elif mode == "record":
        context.record = replace(claim.record)
    elif mode == "clock":
        h.p.t_resample = 99.0
    elif mode == "phase":
        actual.sim = NS(dyna=actual.dyna)
    elif mode == "source":
        context.source.work = []
    else:
        context.thread = -1
    with pytest.raises(stage.PhaseConstructionRejected):
        stage.validate_closed_phase(claim, original_owner=owner)


@pytest.mark.parametrize("mode", ["namespace", "reached_helper", "same_builtin_shadow", "code"])
def test_reused_private_algorithms_refuse_cached_or_reached_binding_drift(monkeypatch, mode):
    stage._reused()
    target = stage._CHECKED
    if mode == "namespace":
        monkeypatch.setitem(target.__globals__, "__builtins__", dict(vars(builtins)))
    elif mode == "reached_helper":
        monkeypatch.setitem(target.__globals__, "_source", lambda context: None)
    elif mode == "same_builtin_shadow":
        monkeypatch.setitem(target.__globals__, "any", any)
    else:
        monkeypatch.setattr(target, "__code__", (lambda claim: None).__code__)
    with pytest.raises(ValueError, match="Shared claim"):
        stage._reused()


@pytest.mark.parametrize("mode", ["valid", "shadow", "cached_builtins"])
def test_native_lookup_binding_control_never_executes_a_function(monkeypatch, mode):
    namespace = {"__builtins__": vars(builtins)}
    template = (lambda self: len(())).__code__
    if mode == "cached_builtins":
        namespace["__builtins__"] = dict(vars(builtins))
    function = FunctionType(template, namespace)
    if mode == "cached_builtins":
        namespace["__builtins__"] = vars(builtins)
    cls = type("LocalLookupMetadataOnly", (), {name: function for name in stage.METHODS})
    native = NS(
        module=object(),
        enum_module=object(),
        cls=cls,
        enum=Enum,
        methods={name: function for name in stage.METHODS},
    )
    monkeypatch.setattr(stage, "_native", lambda: native)
    if mode == "cached_builtins":
        with pytest.raises(ValueError, match="cached builtins"):
            stage._native_bindings(native)
        return
    saved = stage._native_bindings(native)
    if mode == "shadow":
        namespace["len"] = len
        with pytest.raises(ValueError):
            stage.prefix.parameters.inherited._same(stage._native_bindings(native), saved)
    else:
        stage.prefix.parameters.inherited._same(stage._native_bindings(native), saved)


def test_seed_and_new_domains_share_actual_irreversible_reservation(conditional, monkeypatch):
    h = conditional
    monkeypatch.setenv(stage.shared.RELEASE, "1")
    with h.enter() as claim:
        with pytest.raises(stage.shared.WorldConstructionRejected) as caught:
            with stage.shared.construction(
                h.owner, law_id=stage.shared.WORLD_CONSTRUCTION_LAW, enabled=True
            ):
                raise AssertionError("Old SEED claim must not reopen the same owner")
        assert caught.value.stage == "consumed"
        h.run(h.kind.INIT)
    assert stage.validate_closed_phase(claim, original_owner=h.owner) is claim.record
    assert stage.parameters._CONSTRUCTED[h.owner] is claim


def test_active_guard_replacement_cannot_become_constructor_permission(conditional):
    h = conditional
    with pytest.raises(ValueError, match="Original phase construction guard"):
        with h.enter() as claim:
            context = stage._context(claim)
            context.guard = NS(**vars(context.guard))
            claim.check()
    assert not claim.record.succeeded
    assert stage.failed_context(claim).original_guard is not stage.failed_context(claim).guard


@pytest.mark.parametrize("mode", ["guard", "active", "audit", "invalid"])
def test_closed_guard_is_the_original_successful_retired_audit_epoch(conditional, mode):
    h = conditional
    with h.enter() as claim:
        h.run(h.kind.INIT)
    record = claim.record
    context = stage._context(claim)
    if mode == "guard":
        context.guard = NS(**vars(context.guard))
    elif mode == "audit":
        context.guard.audit_ready = False
    else:
        setattr(context.guard, mode, True)
    try:
        with pytest.raises(stage.PhaseConstructionRejected) as caught:
            stage.validate_closed_phase(claim, original_owner=h.owner)
        assert caught.value.stage == "closed"
        assert context.original_record is record
    finally:
        context.original_guard.active = context.guard.active = False


def test_closed_source_binding_authenticates_public_claim_methods(conditional, monkeypatch):
    h = conditional
    with h.enter() as claim:
        h.run(h.kind.INIT)
    monkeypatch.setattr(stage.PhaseConstructionClaim, "check", lambda self: None)
    with pytest.raises(stage.PhaseConstructionRejected) as caught:
        stage.validate_closed_phase(claim, original_owner=h.owner)
    assert caught.value.stage == "closed_drift"


@pytest.mark.parametrize("layer", ["profile", "trace"])
@pytest.mark.parametrize("unwind", [False, True])
def test_inherited_helper_return_hook_loss_is_sticky_and_preserves_source_unwind(
    conditional, layer, unwind, tmp_path
):
    h = conditional
    initial = (sys.getprofile(), sys.gettrace())
    primary, cause = RuntimeError("local helper failure"), LookupError("local source cause")
    primary.__cause__ = cause
    if unwind:
        h.fault.error = primary
    losses = []

    def prior_profile(frame, event, arg):
        if frame.f_code is h.native.methods["_init_kludge_time"].__code__ and event == "return":
            losses.append((frame, event, arg))
            sys.setprofile(None)
            sys.settrace(None)
        if initial[0] is not None:
            initial[0](frame, event, arg)

    def prior_trace(frame, event, arg):
        if frame.f_code is h.native.methods["_init_kludge_time"].__code__ and event == "return":
            losses.append((frame, event, arg))
            sys.setprofile(None)
            sys.settrace(None)
        if initial[1] is not None:
            initial[1](frame, event, arg)
        return prior_trace

    if layer == "profile":
        sys.setprofile(prior_profile)
    else:
        sys.settrace(prior_trace)
    try:
        expected = RuntimeError if unwind else stage.PhaseConstructionRejected
        with pytest.raises(expected) as caught:
            with h.enter() as claim:
                h.run(h.kind.INIT)
        context = stage.failed_context(claim)
        assert len(losses) == 1 and not claim.record.succeeded
        assert h.next_entries == []  # No later source delegate after loss.
        assert any(row[0] == "hook_identity" for row in context.capture_errors)
        if unwind:
            assert caught.value is primary and primary.__cause__ is cause
            assert context.primary is primary
        assert sys.getprofile() is context.required_hooks[0]
        assert sys.gettrace() is context.required_hooks[1]
        assert context.final_hooks == (context.required_hooks, context.required_hooks)
        runner.snapshot.write_json(
            tmp_path / "inherited-hook-loss.json",
            dict(
                layer=layer,
                unwind=unwind,
                local_model_only=True,
                actual_source_or_time_division_entries=0,
                original_source_primary_preserved=unwind,
                both_final_samples_match=True,
                sticky_capture_failure=True,
                next_delegate_entries=len(h.next_entries),
                completed_phase_or_INIT_owner_issued=False,
            ),
        )
    finally:
        sys.setprofile(initial[0])
        sys.settrace(initial[1])


@pytest.mark.parametrize("layer", ["profile", "trace"])
def test_reservation_return_failure_retains_actual_consumed_claim_before_tuple_assignment(
    conditional, layer, tmp_path
):
    h = conditional
    initial = (sys.getprofile(), sys.gettrace())
    primary, cause = OSError("original reservation return refusal"), LookupError("original cause")
    primary.__cause__ = cause
    returns = []

    def prior_profile(frame, event, arg):
        if frame.f_code is stage._RESERVE.__code__ and event == "return":
            returns.append((frame, arg))
            raise primary
        if initial[0] is not None:
            initial[0](frame, event, arg)

    def prior_trace(frame, event, arg):
        if frame.f_code is stage._RESERVE.__code__ and event == "return":
            returns.append((frame, arg))
            raise primary
        if initial[1] is not None:
            initial[1](frame, event, arg)
        return prior_trace

    if layer == "profile":
        sys.setprofile(prior_profile)
    else:
        sys.settrace(prior_trace)
    try:
        with pytest.raises(OSError) as caught:
            with h.enter():
                raise AssertionError("No caller/native body after failed return")
        assert caught.value is primary and primary.__cause__ is cause
        assert len(returns) == 1
        claim = primary.phase_construction_claim
        context = stage.failed_context(claim)
        assert context is returns[0][1][0] and claim is returns[0][1][1]
        assert context.source_error is primary and context.p is h.p
        assert context.stage == "reservation_return" and not context.active
        assert stage.parameters._CONSTRUCTED[h.owner] is claim
        assert context.failed_capture is not None and context.record is None
        assert not any(name in vars(h.p) for name in stage.STORES)
        assert context.final_hooks == (context.required_hooks, context.required_hooks)
        assert sys.getprofile() is context.required_hooks[0]
        assert sys.gettrace() is context.required_hooks[1]
        with pytest.raises(stage.PhaseConstructionRejected) as missing:
            _ = claim.record
        assert missing.value.stage == "record_unavailable"
        with pytest.raises(stage.PhaseConstructionRejected):
            stage.validate_closed_phase(claim, original_owner=h.owner)
        runner.snapshot.write_json(
            tmp_path / "reservation-return-failure.json",
            dict(
                layer=layer,
                exact_original_claim_and_context_retained=True,
                primary_and_cause_preserved=True,
                record_available=False,
                actual_source_or_time_division_entries=0,
                both_hooks_restored=True,
                owner_irreversibly_consumed=True,
                caller_body_entered=False,
            ),
        )
    finally:
        sys.setprofile(initial[0])
        sys.settrace(initial[1])


@pytest.mark.parametrize("layer", ["profile", "trace"])
@pytest.mark.parametrize("falsey", [False, True])
@pytest.mark.parametrize("where", ["hook_restore", "release", "record"])
def test_recorder_entry_refusal_cannot_skip_retirement_or_replace_ordinary_or_falsey_primary(
    conditional, monkeypatch, tmp_path, layer, falsey, where
):
    h = conditional
    initial = (sys.getprofile(), sys.gettrace())

    class FalseyPrimary(RuntimeError):
        def __bool__(self):
            return False

    primary = (FalseyPrimary if falsey else RuntimeError)("original fallible caller seal")
    cause = LookupError("original caller cause")
    primary.__cause__ = cause
    cleanup = OSError("original cleanup failure")
    reporting = LookupError("inherited rejection of error-recorder entry")
    rejections, attempts = [], []

    def prior_profile(frame, event, arg):
        if frame.f_code is stage._capture_error.__code__ and event == "call":
            rejections.append(frame)
            raise reporting
        if initial[0] is not None:
            initial[0](frame, event, arg)

    def prior_trace(frame, event, arg):
        if frame.f_code is stage._capture_error.__code__ and event == "call":
            rejections.append(frame)
            raise reporting
        if initial[1] is not None:
            initial[1](frame, event, arg)
        return prior_trace

    def fail_cleanup(*args):
        raise cleanup

    if where in ("release", "record"):
        monkeypatch.setattr(stage, "_" + where, fail_cleanup)
    if layer == "profile":
        sys.setprofile(prior_profile)
    else:
        sys.settrace(prior_trace)
    try:
        with pytest.raises(RuntimeError) as caught:
            with h.enter() as claim:
                h.run(h.kind.INIT)
                context = stage._context(claim)
                original_setters = context.setters
                trace_failed = False

                def set_profile(hook):
                    attempts.append((0, hook))
                    original_setters[0](hook)

                def set_trace(hook):
                    nonlocal trace_failed
                    attempts.append((1, hook))
                    if (
                        where == "hook_restore"
                        and hook is context.required_hooks[1]
                        and not trace_failed
                    ):
                        trace_failed = True
                        raise cleanup
                    original_setters[1](hook)

                context.setters = (set_profile, set_trace)
                if where in ("release", "record"):
                    capture = stage.parameters._capture

                    def fail_full_capture(actual, *, names=None):
                        if names is None:
                            raise cleanup
                        return capture(actual, names=names)

                    monkeypatch.setattr(stage.parameters, "_capture", fail_full_capture)
                raise primary
        assert caught.value is primary and primary.__cause__ is cause
        context = stage.failed_context(claim)
        assert context.primary is primary and context.source_error is primary
        assert rejections and any(row[1] is cleanup for row in context.raw_errors)
        assert any(row[1] is reporting for row in context.reporting_errors)
        assert context.last_error is not None and context.last_reporting_error is not None
        assert len(context.raw_errors) <= stage.MAX_CAPTURE_ERRORS
        assert len(context.reporting_errors) <= stage.MAX_CAPTURE_ERRORS
        assert not context.active and not context.original_guard.active
        assert not context.registered
        assert not stage._ACTIVE
        assert all(not stack for stack, _ in context.exclusion[1:])
        assert stage.parameters._CONSTRUCTED[h.owner] is claim
        assert context.final_hooks == (context.required_hooks, context.required_hooks)
        assert sys.getprofile() is context.required_hooks[0]
        assert sys.gettrace() is context.required_hooks[1]
        assert any(i == 0 and value is context.required_hooks[0] for i, value in attempts)
        assert any(i == 1 and value is context.required_hooks[1] for i, value in attempts)
        if where == "record":
            with pytest.raises(stage.PhaseConstructionRejected) as unavailable:
                _ = claim.record
            assert unavailable.value.stage == "record_unavailable"
        else:
            assert not claim.record.succeeded
        runner.snapshot.write_json(
            tmp_path / "recorder-entry-refusal.json",
            dict(
                layer=layer,
                falsey_primary=falsey,
                failure_stage=where,
                original_primary_and_cause=True,
                raw_cleanup_error_retained=True,
                reporter_error_separate=True,
                both_hook_attempts=True,
                final_hook_samples_match=True,
                all_owned_stacks_retired=True,
                native_or_time_law_entries=0,
            ),
        )
    finally:
        sys.setprofile(initial[0])
        sys.settrace(initial[1])


@pytest.mark.parametrize("falsey", [False, True])
@pytest.mark.parametrize("layer", ["profile", "trace"])
@pytest.mark.parametrize("later_failure", ["none", "release", "record", "attachment"])
def test_each_later_helper_and_attachment_observes_both_required_hooks_inside_its_body(
    conditional, monkeypatch, tmp_path, falsey, layer, later_failure
):
    h = conditional
    initial = (sys.getprofile(), sys.gettrace())
    checks, rejected = [], []
    context = None
    cleanup, recorder = OSError("first full capture failed"), LookupError("recorder entry rejected")

    def inside(name):
        pair = (sys.getprofile(), sys.gettrace())
        checks.append((name, pair))
        assert pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
        if later_failure == name:
            sys.setprofile(None)
            sys.settrace(None)
            raise cleanup

    class Primary(RuntimeError):
        def __bool__(self):
            return not falsey

        def __setattr__(self, name, value):
            if name == "phase_construction_claim":
                inside("attachment")
            return super().__setattr__(name, value)

    primary, cause = Primary("original caller error"), KeyError("cause")
    primary.__cause__ = cause
    release, record = stage._release, stage._record

    def checked_release(actual):
        inside("release")
        return release(actual)

    def checked_record(actual, succeeded):
        inside("record")
        return record(actual, succeeded)

    monkeypatch.setattr(stage, "_release", checked_release)
    monkeypatch.setattr(stage, "_record", checked_record)

    def prior_profile(frame, event, arg):
        if frame.f_code is stage._capture_error.__code__ and event == "call":
            rejected.append(frame)
            raise recorder
        if initial[0] is not None:
            initial[0](frame, event, arg)

    def prior_trace(frame, event, arg):
        if frame.f_code is stage._capture_error.__code__ and event == "call":
            rejected.append(frame)
            raise recorder
        if initial[1] is not None:
            initial[1](frame, event, arg)
        return prior_trace

    if layer == "profile":
        sys.setprofile(prior_profile)
    else:
        sys.settrace(prior_trace)
    try:
        with pytest.raises(Primary) as caught:
            with h.enter() as claim:
                h.run(h.kind.INIT)
                context = stage._context(claim)
                capture = stage.parameters._capture

                def fail_capture(actual, *, names=None):
                    if names is None:
                        raise cleanup
                    return capture(actual, names=names)

                monkeypatch.setattr(stage.parameters, "_capture", fail_capture)
                raise primary
        assert caught.value is primary and primary.__cause__ is cause
        assert rejected and [name for name, _ in checks] == ["release", "record", "attachment"]
        assert not context.cleanup_blocked and not context.active and not context.registered
        assert all(not stack for stack, _ in context.exclusion[1:])
        assert any(row[1] is recorder for row in context.reporting_errors)
        assert sys.getprofile() is context.required_hooks[0]
        assert sys.gettrace() is context.required_hooks[1]
        runner.snapshot.write_json(
            tmp_path / "inside-cleanup-helper.json",
            dict(
                layer=layer,
                falsey_primary=falsey,
                later_failure=later_failure,
                checked_inside=[name for name, _ in checks],
                hooks_correct_inside_all=True,
                original_primary_and_cause=True,
                retired=True,
                native_entries=0,
            ),
        )
    finally:
        sys.setprofile(initial[0])
        sys.settrace(initial[1])


@pytest.mark.parametrize("falsey", [False, True])
def test_unrecoverable_hooks_skip_all_later_callbacks_and_retire_without_attachment(
    conditional, monkeypatch, tmp_path, falsey
):
    h = conditional
    initial = (sys.getprofile(), sys.gettrace())
    callbacks = []

    class Primary(RuntimeError):
        def __bool__(self):
            return not falsey

        def __setattr__(self, name, value):
            if name == "phase_construction_claim":
                callbacks.append("attachment")
            return super().__setattr__(name, value)

    primary, cause = Primary("original before unrecoverable cleanup"), LookupError("cause")
    primary.__cause__ = cause

    def forbidden(name):
        def invoke(*args):
            callbacks.append(name)
            raise AssertionError("Unsafe cleanup callback executed")

        return invoke

    for name in ("finish", "release", "record"):
        monkeypatch.setattr(stage, "_" + name, forbidden(name))
    try:
        with pytest.raises(Primary) as caught:
            with h.enter() as claim:
                h.run(h.kind.INIT)
                context = stage._context(claim)

                def cannot_restore(hook):
                    sys.setprofile(None)
                    sys.settrace(None)
                    raise OSError("declared unrecoverable setter failure")

                context.setters = (cannot_restore, cannot_restore)
                raise primary
        assert caught.value is primary and primary.__cause__ is cause
        assert context.cleanup_blocked and callbacks == []
        assert context.cleanup_skipped == ("finish", "release", "record", "attachment")
        assert not context.active and not context.registered and not context.original_guard.active
        assert not stage._ACTIVE and all(not stack for stack, _ in context.exclusion[1:])
        assert stage.parameters._CONSTRUCTED[h.owner] is claim
        assert context.record is None and context.source_error is primary
        assert context.raw_errors and not hasattr(primary, "phase_construction_claim")
        # The software fixture restores its own external blockade; this does
        # NOT relabel the failed production recovery as successful.
        assert context.final_hooks != (context.required_hooks, context.required_hooks)
        runner.snapshot.write_json(
            tmp_path / "unrecoverable-cleanup.json",
            dict(
                falsey_primary=falsey,
                callbacks_entered=callbacks,
                original_primary_and_cause=True,
                record_available=False,
                owned_edges_retired=True,
                production_recovery_succeeded=False,
                external_test_cleanup_separate=True,
                native_entries=0,
            ),
        )
    finally:
        sys.setprofile(initial[0])
        sys.settrace(initial[1])
