"""Conditional claim/observer tests; no actual endpoint, constructor or division."""

import ast
import dis
import sys
from dataclasses import replace
from pathlib import Path
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_parameter_seed_init_transition as stage
from tests.unit import test_betse_native_parameter_phase_construction as inherited
from validation.betse import betse_native_parameter_seed_init_transition_software as runner

conditional_parent = inherited.conditional


_DIAGNOSTIC_ERRORS = ()


def _write_failure_diagnostics(tmp_path, contexts):
    def error_record(error):
        trace = []
        tb = error.__traceback__
        while tb is not None:
            trace.append((tb.tb_frame.f_code.co_filename, tb.tb_frame.f_code.co_name, tb.tb_lineno))
            tb = tb.tb_next
        return dict(type=type(error).__name__, message=str(error), traceback=trace)

    for index, context in enumerate(contexts):
        runner.snapshot.write_json(
            tmp_path / ("transition-failure-" + str(index) + ".json"),
            dict(
                source_error=error_record(context.source_error)
                if context.source_error is not None
                else None,
                observation_error=error_record(context.observation_error)
                if context.observation_error is not None
                else None,
                capture_errors=[
                    dict(stage=row[0], error=error_record(row[1])) for row in context.capture_errors
                ],
                assignments=[row[0] for row in getattr(context, "assignments", ())],
                flag_writes=len(getattr(context, "flag_write_events", ())),
                actual_work_entries=len(getattr(context, "actual_work", ())),
                record_available=context.record is not None,
            ),
        )


def _drain_guard(generator, started, contexts, tmp_path, *, required_hooks, primary=None):
    """Reporting failure never prevents the actual inherited guard unwind."""
    global _DIAGNOSTIC_ERRORS
    diagnostic = cleanup = None
    try:
        _write_failure_diagnostics(tmp_path, contexts)
    except BaseException as error:
        diagnostic = error
        _DIAGNOSTIC_ERRORS = (*_DIAGNOSTIC_ERRORS[-63:], ("diagnostic", error, contexts, primary))
    finally:
        try:
            if started:
                try:
                    next(generator)
                except StopIteration:
                    pass
                else:
                    raise RuntimeError("Inherited guard generator did not finish")
            else:
                generator.close()
        except BaseException as error:
            cleanup = error
            _DIAGNOSTIC_ERRORS = (
                *_DIAGNOSTIC_ERRORS[-63:],
                ("inherited_guard_cleanup", error, generator, primary),
            )
        finally:
            # Cleanup can itself be refused before its generator body runs.
            # Independent trusted setters follow all diagnostic callbacks.
            for index in (1, 0):
                try:
                    (sys.setprofile, sys.settrace)[index](required_hooks[index])
                except BaseException as error:
                    if cleanup is None:
                        cleanup = error
                    _DIAGNOSTIC_ERRORS = (
                        *_DIAGNOSTIC_ERRORS[-63:],
                        ("independent_guard_restore", error, index, primary),
                    )
            for index, getter in enumerate((sys.getprofile, sys.gettrace)):
                try:
                    if getter() is not required_hooks[index]:
                        raise ValueError("Original inherited guard hook was not restored")
                except BaseException as error:
                    if cleanup is None:
                        cleanup = error
                    _DIAGNOSTIC_ERRORS = (
                        *_DIAGNOSTIC_ERRORS[-63:],
                        ("independent_guard_sample", error, index, primary),
                    )
    if primary is not None:
        raise primary
    if diagnostic is not None:
        raise diagnostic
    if cleanup is not None:
        raise cleanup


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    function = inherited.native_blocked.__wrapped__
    scope = dict(function.__globals__, stage=stage, runner=runner)
    generator = FunctionType(function.__code__, scope)(request, tmp_path, monkeypatch)
    required_hooks = sys.getprofile(), sys.gettrace()
    started = False
    failed_before = len(stage._FAILED)
    primary = None
    try:
        next(generator)
        started = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        contexts = tuple(stage._FAILED[failed_before:])
        _drain_guard(
            generator, started, contexts, tmp_path, required_hooks=required_hooks, primary=primary
        )


def test_native_order_and_selected_boundary_preserve_loader_and_material_limits(tmp_path):
    plan = stage.source_plan()
    assert plan["original_caller"]["original_optional_inputs"] == (
        "kind",
        "cells",
        "p",
        "callbacks",
    )
    assert plan["original_caller"]["constructor_line"] == 225
    assert plan["store_order"] == ("_run_sim", "dt", "resample", "total_time", "t_resample")
    assert not plan["saved_loader_or_full_SimRunner_init_equivalence"]
    assert not plan["native_phase_material_completed_INIT_or_scientific_admission"]
    assert plan["held"] and not plan["existing_SEED_or_fresh_timing_API_changed"]
    runner.snapshot.write_json(tmp_path / "source-boundary.json", plan)


@pytest.mark.parametrize("mode", ["default", "integer", "local_gate", "parent_gate", "law"])
def test_release_and_law_refuse_before_accessing_a_seed_or_parent(monkeypatch, mode):
    for name in (
        stage.RELEASE,
        stage.timing.RELEASE,
        stage.parameters.RELEASE,
        stage.parameters.previous.RELEASE,
    ):
        monkeypatch.setenv(name, "1")
    if mode.endswith("gate"):
        monkeypatch.setenv(stage.RELEASE if mode == "local_gate" else stage.timing.RELEASE, "0")

    def forbidden(*args):
        raise AssertionError("No seed inspection/reservation before release/law")

    monkeypatch.setattr(stage, "_reserve", forbidden)
    with pytest.raises(stage.SeedInitRejected) as caught:
        with stage.seed_to_init(
            None,
            original_owner=None,
            law_id="foreign" if mode == "law" else stage.SEED_INIT_LAW,
            enabled=1 if mode == "integer" else mode != "default",
        ):
            raise AssertionError("No construction permission")
    assert caught.value.stage == ("law" if mode == "law" else "release")


@pytest.mark.parametrize("value", [None, {}, NS(), object.__new__(stage.SeedInitClaim)])
def test_data_or_unissued_claim_cannot_become_a_transition(value):
    with pytest.raises(stage.SeedInitRejected):
        stage.validate_closed_init(value, seed_claim=None, original_owner=None)
    with pytest.raises(stage.SeedInitRejected):
        stage.failed_context(value)


@pytest.fixture
def conditional(conditional_parent, monkeypatch):
    """Actual issued claim machinery, conditional complete-load/runtime model."""
    h = conditional_parent
    shared = stage.shared
    # These are explicit metadata-boundary models. Their source declarations
    # are labelled conditional, avoiding repeated full upstream source-plan
    # construction inside every local instruction callback. The separate
    # source-only control above checks the actual complete native plans.
    monkeypatch.setattr(
        shared,
        "source_plan",
        lambda: dict(law=shared.WORLD_CONSTRUCTION_LAW, conditional_complete_load_only=True),
    )
    monkeypatch.setattr(
        stage,
        "source_plan",
        lambda: dict(law=stage.SEED_INIT_LAW, conditional_complete_load_and_runtime_only=True),
    )
    monkeypatch.setenv(shared.RELEASE, "1")
    with shared.construction(h.owner, law_id=shared.WORLD_CONSTRUCTION_LAW, enabled=True) as seed:
        h.p._run_sim = False
    seed_record = shared.validate_closed_seed(seed, original_owner=h.owner)
    seed_context = shared._context(seed)
    fault = NS(error=None, omit_write=False, calls=[])
    Kind = h.kind
    ratio = 29.0
    cells, callback = object(), object()

    class LocalInit:
        def __init__(self, kind, p, cells=None, sim=None, callbacks=None):
            self.callbacks = callbacks
            self.cells = cells
            self.kind = kind
            self.p = p
            self.sim = NS() if sim is None else sim
            self.cache = object()
            self.dyna = object()
            self._init_kludge()
            self.export_dirname = p.init_export_dirname

        def _init_kludge(self):
            self.sim.dyna = self.dyna
            if not fault.omit_write:
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
            self.p.t_resample = ratio

    methods = {name: vars(LocalInit)[name] for name in stage.timing.METHODS}
    native = NS(
        cls=LocalInit,
        enum=Kind,
        methods=methods,
        chains={name: (fn,) for name, fn in methods.items()},
    )
    monkeypatch.setattr(stage.timing, "_native", lambda: native)
    monkeypatch.setattr(
        stage.timing, "_native_bindings", lambda actual: ((), (native, LocalInit, Kind))
    )
    tree = ast.parse(open(__file__).read())
    cls = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "LocalInit"
    )
    nodes = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    line_fn = FunctionType(
        stage.timing._store_lines.__code__,
        dict(stage.timing._store_lines.__globals__, _nodes=lambda: nodes),
    )
    monkeypatch.setattr(stage.timing, "_store_lines", line_fn)
    for name in (
        stage.RELEASE,
        stage.timing.RELEASE,
        stage.parameters.RELEASE,
        stage.parameters.previous.RELEASE,
    ):
        monkeypatch.setenv(name, "1")
    return NS(
        parent=h,
        seed=seed,
        seed_record=seed_record,
        seed_context=seed_context,
        p=h.p,
        owner=h.owner,
        fault=fault,
        cells=cells,
        callback=callback,
        native=native,
        ratio=ratio,
        enter=lambda: stage.seed_to_init(
            seed, original_owner=h.owner, law_id=stage.SEED_INIT_LAW, enabled=True
        ),
        run=lambda **kw: LocalInit(
            Kind.INIT, h.p, **dict(dict(cells=cells, sim=None, callbacks=callback), **kw)
        ),
    )


def test_same_actual_parameter_new_INIT_observes_existing_false_write_and_keeps_seed_history(
    conditional, tmp_path
):
    h = conditional
    original_fields = tuple(vars(h.p))
    old_graph = stage.parameters._capture(h.parent.source)
    with h.enter() as claim:
        assert claim.parameters is h.p and claim.check() is None
        with pytest.raises(stage.SeedInitRejected):
            _ = claim.record
        actual = h.run()
        assert actual.p is h.p and actual.cells is h.cells and actual.callbacks is h.callback
        assert claim.check() is None
    context = stage._context(claim)
    assert tuple(vars(h.p)) == (*original_fields, *stage.timing.STORES[1:])
    assert stage.parameters._CONSTRUCTED[h.owner] is h.seed
    assert stage._CONSUMED[h.seed] is context
    assert len(context.flag_write_events) == 1
    frame, offset, _ = context.flag_write_events[0]
    assert frame is context.frames["_init_kludge"]
    assert dis.opname[frame.f_code.co_code[offset]] == "STORE_ATTR"
    assert [row[0] for row in context.assignments] == list(stage.timing.STORES)
    assert h.p._run_sim is False and h.p.dt is h.p.init_time_step
    assert h.p.resample is h.p.init_time_sampling and h.p.total_time is h.p.init_time_total
    assert h.p.t_resample is h.ratio
    assert actual.sim is not None and actual.sim.dyna is actual.dyna
    assert context.optional_inputs == (("cells", h.cells), ("sim", None), ("callbacks", h.callback))
    assert context.seed_record is h.seed_record is h.seed.record
    assert stage._digest(old_graph[1]) == claim.record.seed_parameter_graph_identity

    runner.snapshot.write_json(
        tmp_path / "same-p-transition.json",
        dict(
            conditional_only=True,
            same_actual_p=True,
            original_map_edge_preserved=True,
            original_false_write_events=len(context.flag_write_events),
            native_time_divisions=0,
            original_seed_record_identity=h.seed_record.identity,
            actual_native_phase_or_completed_INIT_admitted=False,
        ),
    )


def test_successful_closed_validation_uses_metadata_history_without_stale_seed_bytes(conditional):
    h = conditional
    with h.enter() as claim:
        h.run()
    context = stage._context(claim)
    old_profile = sys.getprofile()
    stale_entries = []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code in (
            stage.shared._bytes.__code__,
            stage.shared.validate_closed_seed.__code__,
        ):
            stale_entries.append(frame)
            raise AssertionError("Stale pre-INIT parameter snapshot validator entered")
        if old_profile is not None:
            old_profile(frame, event, arg)

    sys.setprofile(profile)
    try:
        record = stage.validate_closed_init(claim, seed_claim=h.seed, original_owner=h.owner)
    finally:
        sys.setprofile(old_profile)
    assert stale_entries == []
    assert record is claim.record and record.succeeded
    assert record.original_seed_record_identity == h.seed_record.identity
    assert len(record.actual_source_calls) == 3
    assert all(row[0] == __file__ for row in record.actual_source_calls)
    with pytest.raises(stage.SeedInitRejected) as consumed:
        with h.enter():
            pass
    assert consumed.value.stage == "consumed"
    # Full SEED snapshots now differ; their immutable record is historical.
    assert (
        h.seed_context.record is h.seed_record and stage.shared._context(h.seed) is h.seed_context
    )
    assert context.constructor_completed and len(context.flag_write_events) == 1


@pytest.mark.parametrize(
    "mode", ["no_write", "manual_clock", "prior_clocks", "source_error", "caller_seal"]
)
def test_failed_prefix_or_equal_false_never_becomes_constructor_success(
    conditional, mode, tmp_path
):
    h = conditional
    primary, cause = ZeroDivisionError("local declared failure; no division"), LookupError("cause")
    primary.__cause__ = cause
    if mode == "no_write":
        h.fault.omit_write = True
    if mode == "source_error":
        h.fault.error = primary
    if mode == "prior_clocks":
        h.p.dt = h.p.init_time_step
    expected = ZeroDivisionError if mode in ("source_error", "caller_seal") else ValueError
    with pytest.raises(expected) as caught:
        with h.enter() as claim:
            if mode == "manual_clock":
                h.p.dt = h.p.init_time_step
                claim.check()
            else:
                h.run()
            if mode == "caller_seal":
                raise primary
    claim = caught.value.seed_init_claim
    context = stage.failed_context(claim)
    assert context.p is h.p and context.seed_claim is h.seed
    assert stage._CONSUMED[h.seed] is context
    assert stage.parameters._CONSTRUCTED[h.owner] is h.seed
    assert not context.active and not claim.record.succeeded
    if mode in ("source_error", "caller_seal"):
        assert caught.value is primary and primary.__cause__ is cause
    if mode == "no_write":
        assert context.flag_write_events == [] and h.p._run_sim is False
    if mode == "source_error":
        assert [row[0] for row in context.assignments] == list(stage.timing.STORES[:-1])
        assert "t_resample" not in vars(h.p)
    runner.snapshot.write_json(
        tmp_path / "failed-transition-prefix.json",
        dict(
            mode=mode,
            source_primary_identity=mode in ("source_error", "caller_seal"),
            retained_stores=[row[0] for row in context.assignments],
            completed_flag_writes=len(context.flag_write_events),
            native_time_divisions=0,
            same_p=True,
            historical_seed_edge_preserved=True,
        ),
    )


@pytest.mark.parametrize("mode", ["no_cells", "foreign_sim", "no_callback"])
def test_constructor_route_requires_existing_cells_and_fresh_simulator(conditional, mode):
    h = conditional
    kw = (
        {"cells": None}
        if mode == "no_cells"
        else {"sim": NS()}
        if mode == "foreign_sim"
        else {"callbacks": None}
    )
    with pytest.raises(stage.SeedInitRejected) as caught:
        with h.enter() as claim:
            h.run(**kw)
    assert caught.value is stage._context(claim).entry_error
    assert not claim.record.succeeded
    assert stage._context(claim).assignments == []


@pytest.mark.parametrize(
    "mode",
    ["record", "guard", "work", "binding", "consumed_edge", "parent_map", "clock", "flag", "phase"],
)
def test_closed_transition_rejects_ancestry_state_or_observation_drift(
    conditional, monkeypatch, mode
):
    h = conditional
    with h.enter() as claim:
        phase = h.run()
    assert (
        stage.validate_closed_init(claim, seed_claim=h.seed, original_owner=h.owner) is claim.record
    )
    if mode == "record":
        h.seed_context.record = replace(h.seed_record)
    elif mode == "guard":
        h.seed_context.guard = NS(**vars(h.seed_context.guard))
    elif mode == "work":
        h.seed_context.work = list(h.seed_context.work)
    elif mode == "binding":
        h.seed_context.bindings = tuple(list(h.seed_context.bindings))
    elif mode == "consumed_edge":
        monkeypatch.delitem(stage._CONSUMED, h.seed)
    elif mode == "parent_map":
        monkeypatch.setitem(stage.parameters._CONSTRUCTED, h.owner, claim)
    elif mode == "clock":
        h.p.t_resample = 300.0
    elif mode == "flag":
        h.p._run_sim = 0
    else:
        phase.kind = h.parent.kind.SEED
    with pytest.raises(stage.SeedInitRejected):
        stage.validate_closed_init(claim, seed_claim=h.seed, original_owner=h.owner)


@pytest.mark.parametrize("mode", ["source", "code", "builtins", "category"])
def test_shared_observer_private_namespace_and_executable_are_bound_without_calls(
    monkeypatch, mode
):
    stage._runtime_bindings()
    if mode == "source":
        monkeypatch.setitem(stage._RUNTIME, "_source_guard", lambda context: None)
    elif mode == "code":
        monkeypatch.setattr(stage._TIMING_OBSERVE, "__code__", (lambda *args: None).__code__)
    elif mode == "builtins":
        monkeypatch.setitem(stage._RUNTIME, "__builtins__", {})
    else:
        monkeypatch.setitem(stage._RUNTIME, "any", any)
    with pytest.raises(ValueError, match="Shared|shared"):
        stage._runtime_bindings()


def test_active_conflict_consumption_and_original_seed_map_are_irreversible(conditional):
    h = conditional
    with pytest.raises(stage.SeedInitRejected):
        with h.enter() as claim:
            with pytest.raises(stage.SeedInitRejected) as caught:
                with h.enter():
                    pass
            assert caught.value.stage == "reentrant"
            claim.check()
    assert not claim.record.succeeded
    assert stage.parameters._CONSTRUCTED[h.owner] is h.seed


@pytest.mark.parametrize("falsey", [False, True])
def test_failure_retains_primary_and_cleans_all_owned_exclusion_edges(conditional, falsey):
    h = conditional

    class Primary(RuntimeError):
        def __bool__(self):
            return not falsey

    primary, cause = Primary("original caller failure"), KeyError("cause")
    primary.__cause__ = cause
    with pytest.raises(Primary) as caught:
        with h.enter() as claim:
            h.run()
            raise primary
    assert caught.value is primary and primary.__cause__ is cause
    assert primary.seed_init_claim is claim
    context = stage.failed_context(claim)
    assert not context.active and not context.registered
    assert not stage._ACTIVE and all(not stack for stack, _ in context.exclusion[1:])
    assert context.final_hooks == (context.required_hooks, context.required_hooks)


@pytest.mark.parametrize("mode", ["valid", "keys", "builtin", "cached", "closure"])
def test_private_original_code_namespace_metadata_is_closed_without_evaluation(monkeypatch, mode):
    module = sys.modules[__name__]

    def declared_namespace(context):
        return lambda *args, **kwargs: context

    def code_tree(code):
        return (
            code,
            *(
                child
                for item in code.co_consts
                if type(item) is CodeType
                for child in code_tree(item)
            ),
        )

    monkeypatch.setattr(module, "_namespace", declared_namespace, raising=False)
    monkeypatch.setattr(module, "_code_tree", code_tree, raising=False)

    def original(self):
        raise AssertionError("No metadata function is to be evaluated")

    consumer = NS(factory_names=())
    private = dict(original.__globals__)
    private["__builtins__"] = dict(
        original.__builtins__,
        __import__=declared_namespace(object() if mode == "closure" else consumer),
    )
    function = FunctionType(original.__code__, private)
    consumer.methods = {("SimPhase", name): function for name in stage.timing.METHODS}
    consumer.runtime_types = {}
    context = NS(original_native=NS(methods={name: original for name in stage.timing.METHODS}))
    if mode == "keys":
        private["foreign_equal_shadow"] = 1
    elif mode == "builtin":
        private["__builtins__"]["str"] = lambda value: "foreign"
    elif mode == "cached":
        private["__builtins__"] = dict(private["__builtins__"])
    if mode == "valid":
        actual = stage._private_bindings(context, consumer, module)
        assert actual and any(value is function for value in actual)
    else:
        with pytest.raises(ValueError, match="Private|private|cached"):
            stage._private_bindings(context, consumer, module)


def test_unadopted_private_consumer_refuses_before_namespace_or_parent_access():
    assert stage.CONSUMER_INTERFACE_SHA256 is None
    with pytest.raises(stage.SeedInitRejected) as caught:
        stage._bind_consumer(NS(claim=None), first=True)
    assert caught.value.stage == "consumer_unbound"


def test_monitor_keeps_a_foreign_tool_and_independent_profile_trace_guards(conditional, tmp_path):
    h = conditional
    monitor = stage._MONITOR
    free = next(index for index in range(6) if monitor.get_tool(index) is None)
    monitor.use_tool_id(free, "declared external metadata observer")
    initial = (sys.getprofile(), sys.gettrace())
    observed = []

    def profile(frame, event, arg):
        if frame.f_code is h.native.methods["_init_kludge"].__code__:
            observed.append(event)
        if initial[0] is not None:
            initial[0](frame, event, arg)

    sys.setprofile(profile)
    try:
        with h.enter() as claim:
            phase = h.run()
            assert sys.getprofile() is profile and sys.gettrace() is initial[1]
        context = stage._context(claim)
        assert (
            stage.validate_closed_init(claim, seed_claim=h.seed, original_owner=h.owner)
            is claim.record
        )
        assert phase.p is h.p and len(context.flag_write_events) == 1
        assert observed == ["call", "return"]
        assert context.monitor_before == context.monitor_after
        assert monitor.get_tool(free) == "declared external metadata observer"
        assert monitor.get_tool(context.monitor_tool) is None
        runner.snapshot.write_json(
            tmp_path / "independent-monitor.json",
            dict(
                local_model_only=True,
                flag_write_events=1,
                external_tool_unchanged=True,
                external_profile_and_trace_preserved=True,
                owned_tool_released=True,
                native_time_divisions=0,
            ),
        )
    finally:
        sys.setprofile(initial[0])
        sys.settrace(initial[1])
        monitor.free_tool_id(free)


def test_unavailable_monitor_tool_refuses_without_stealing_other_observers(conditional):
    h = conditional
    monitor = stage._MONITOR
    free = [index for index in range(6) if monitor.get_tool(index) is None]
    for index in free:
        monitor.use_tool_id(index, "metadata-only occupied slot " + str(index))
    try:
        before = tuple(monitor.get_tool(index) for index in range(6))
        with pytest.raises(stage.SeedInitRejected) as caught:
            with h.enter():
                raise AssertionError("No source constructor with no observer slot")
        assert caught.value.stage == "monitoring"
        assert before == tuple(monitor.get_tool(index) for index in range(6))
        claim = caught.value.seed_init_claim
        assert not claim.record.succeeded and stage.failed_context(claim).assignments == []
    finally:
        for index in free:
            monitor.free_tool_id(index)


@pytest.mark.parametrize("edge", ["frame", "offset", "line"])
def test_closed_equal_value_flag_instruction_witness_cannot_be_relabelled(conditional, edge):
    h = conditional
    with h.enter() as claim:
        h.run()
    context = stage._context(claim)
    frame, offset, line = context.flag_write_events[0]
    context.flag_write_events[0] = (
        object() if edge == "frame" else frame,
        offset + 2 if edge == "offset" else offset,
        line + 1 if edge == "line" else line,
    )
    with pytest.raises(stage.SeedInitRejected):
        stage.validate_closed_init(claim, seed_claim=h.seed, original_owner=h.owner)


@pytest.mark.parametrize(
    "mode", ["valid", "backrefs", "other_bytes", "chained", "duplicate", "computed"]
)
def test_consumer_backreferences_use_exact_bytes_and_never_evaluate_source(mode):
    payload = (
        b'KEY_SOURCE_SHA256 = None\nKEY_REVIEW_SHA256 = None\nraise RuntimeError("not evaluated")\n'
    )
    identity, refs = stage.consumer_interface(payload)
    assert refs == (("KEY_SOURCE_SHA256", None), ("KEY_REVIEW_SHA256", None))
    changed = payload
    if mode == "backrefs":
        changed = changed.replace(b"None", repr("a" * 64).encode(), 1)
        changed = changed.replace(b"None", repr("b" * 64).encode(), 1)
    elif mode == "other_bytes":
        changed += b"# Even comments outside references are exact\n"
    elif mode == "chained":
        changed = b"KEY_SOURCE_SHA256 = KEY_REVIEW_SHA256 = None\n"
    elif mode == "duplicate":
        changed += b"KEY_SOURCE_SHA256 = None\n"
    elif mode == "computed":
        changed = changed.replace(b"= None", b'= "a" * 64', 1)
    if mode in ("chained", "duplicate", "computed"):
        with pytest.raises(ValueError):
            stage.consumer_interface(changed)
    else:
        actual, actual_refs = stage.consumer_interface(changed)
        assert (actual == identity) is (mode != "other_bytes")
        if mode == "backrefs":
            assert actual_refs == (("KEY_SOURCE_SHA256", "a" * 64), ("KEY_REVIEW_SHA256", "b" * 64))


@pytest.mark.parametrize("mode", ["owner", "active", "failed", "capture", "falsey_error", "thread"])
def test_foreign_or_unsuccessful_seed_cannot_reserve_a_new_successor(conditional, mode):
    h = conditional
    owner = h.owner
    if mode == "owner":
        owner = object()
    elif mode == "active":
        h.seed_context.active = True
    elif mode == "failed":
        h.seed_context.record = replace(h.seed_record, succeeded=False)
        h.seed_context.original_record = h.seed_context.record
    elif mode == "capture":
        h.seed_context.capture_errors = (("retained", OSError("capture failed")),)
    elif mode == "falsey_error":

        class FalseyError(RuntimeError):
            def __bool__(self):
                return False

        h.seed_context.source_error = FalseyError("original source failed")
    else:
        h.seed_context.thread = -1
    with pytest.raises(stage.SeedInitRejected) as caught:
        with stage.seed_to_init(
            h.seed, original_owner=owner, law_id=stage.SEED_INIT_LAW, enabled=True
        ):
            raise AssertionError("No successor from failed or foreign original authority")
    assert caught.value.stage == "seed_owner"
    assert h.seed not in stage._CONSUMED
    assert stage.parameters._CONSTRUCTED[h.owner] is h.seed
    assert not stage._ACTIVE


@pytest.mark.parametrize("kind", ["ordinary", "falsey", "none"])
@pytest.mark.parametrize("failure", ["inherited_profile", "getter"])
def test_final_tool_sampling_failure_keeps_caller_primary_and_samples_other_slots(
    conditional, monkeypatch, tmp_path, kind, failure
):
    h = conditional
    initial = (sys.getprofile(), sys.gettrace())
    actual_get = stage._MONITOR.get_tool
    secondary = OSError("final tool sampling rejected")
    sampled, box = [], {}

    class Primary(RuntimeError):
        def __bool__(self):
            return kind != "falsey"

    primary, cause = Primary("original caller/sealing error"), LookupError("original cause")
    primary.__cause__ = cause

    def prior(frame, event, arg):
        c = box.get("context")
        if (
            failure == "inherited_profile"
            and c is not None
            and not c.monitoring
            and event == "c_call"
            and arg is actual_get
            and frame.f_code is stage._monitor_flag.__wrapped__.__code__
        ):
            sampled.append(frame.f_locals["index"])
            raise secondary
        if initial[0] is not None:
            initial[0](frame, event, arg)

    def fail_getter(index):
        c = box["context"]
        if not c.monitoring:
            sampled.append(index)
            if len(sampled) == 1:
                raise secondary
        return actual_get(index)

    if failure == "inherited_profile":
        sys.setprofile(prior)
    try:
        with pytest.raises(stage.SeedInitRejected if kind == "none" else Primary) as caught:
            with h.enter() as claim:
                h.run()
                box["context"] = stage._context(claim)
                if failure == "getter":
                    monkeypatch.setattr(stage._MONITOR, "get_tool", fail_getter)
                if kind != "none":
                    raise primary
        c = stage.failed_context(claim)
        if kind != "none":
            assert caught.value is primary and primary.__cause__ is cause
            assert c.primary is primary and c.source_error is primary
        assert any(row[0] == "monitor_final_sample" and row[1] is secondary for row in c.raw_errors)
        assert c.monitor_after[0] is secondary and len(c.monitor_after) == 6
        assert all(c.monitor_after[i] == c.monitor_before[i] for i in range(1, 6))
        if failure == "getter":
            assert sampled == list(range(6))
        else:
            assert sampled == [0]
        assert tuple(actual_get(i) for i in range(6)) == c.monitor_before
        assert not claim.record.succeeded
        runner.snapshot.write_json(
            tmp_path / "final-sample-failure.json",
            dict(
                kind=kind,
                failure=failure,
                actual_first_sample_failed=True,
                remaining5_samples_taken=True,
                primary_and_cause_preserved=kind != "none",
                owned_tool_retired=True,
                successful_record=False,
                native_entries=0,
            ),
        )
    finally:
        monkeypatch.setattr(stage._MONITOR, "get_tool", actual_get)
        sys.setprofile(initial[0])
        sys.settrace(initial[1])


@pytest.mark.parametrize("falsey", [False, True])
@pytest.mark.parametrize("event", ["exception", "return", "both"])
def test_source_unwind_and_observer_failure_keep_raw_frame_event_and_original_cause(
    conditional, monkeypatch, tmp_path, falsey, event
):
    h = conditional

    class Primary(RuntimeError):
        def __bool__(self):
            return not falsey

    primary, cause = Primary("actual local helper unwind"), LookupError("original source cause")
    primary.__cause__ = cause
    secondary = OSError("secondary observation error")
    original = stage._observe
    events = []

    def fail_observe(context, frame, name, value):
        if frame.f_code is h.native.methods["_init_kludge_time"].__code__ and name in (
            ("exception", "return") if event == "both" else (event,)
        ):
            events.append((frame, name, value))
            raise secondary
        return original(context, frame, name, value)

    monkeypatch.setattr(stage, "_observe", fail_observe)
    h.fault.error = primary
    with pytest.raises(Primary) as caught:
        with h.enter() as claim:
            h.run()
    c = stage.failed_context(claim)
    assert caught.value is primary and primary.__cause__ is cause
    assert c.primary is primary and c.source_error is primary
    assert events
    expected = ("exception", "return") if event == "both" else (event,)
    for name in expected:
        rows = [
            row
            for row in c.capture_errors
            if row[0] == "unwind_" + name
            and row[1] is secondary
            and row[2][0].f_code is h.native.methods["_init_kludge_time"].__code__
        ]
        assert rows and rows[0][2][1] == name
        if name == "return":
            assert rows[0][2][2] is None
        else:
            assert rows[0][2][2][1] is primary
    assert [row[0] for row in c.assignments] == list(stage.timing.STORES[:-1])
    assert "t_resample" not in vars(h.p) and not claim.record.succeeded
    runner.snapshot.write_json(
        tmp_path / "combined-unwind-capture.json",
        dict(
            falsey_primary=falsey,
            failed_event=event,
            exact_primary_and_cause=True,
            separate_observation_error=True,
            exact_raw_frame_and_event=True,
            return_payload_retained=event in ("return", "both"),
            native_entries=0,
        ),
    )


@pytest.mark.parametrize("primary_kind", ["none", "ordinary", "falsey"])
@pytest.mark.parametrize("failure", ["formatter", "writer", "writer_entry"])
def test_diagnostic_failure_never_skips_real_guard_generator_cleanup(
    tmp_path, monkeypatch, primary_kind, failure
):
    initial = (sys.getprofile(), sys.gettrace())
    cleanup = []
    secondary = OSError("diagnostic failed")
    write = runner.snapshot.write_json

    class Primary(RuntimeError):
        def __bool__(self):
            return primary_kind != "falsey"

    class BadFormatter(RuntimeError):
        def __str__(self):
            raise secondary

    primary, cause = Primary("original inner test failure"), LookupError("cause")
    primary.__cause__ = cause
    context = NS(
        source_error=BadFormatter("unprintable") if failure == "formatter" else primary,
        observation_error=None,
        capture_errors=(),
        record=None,
    )

    def profile(frame, event, arg):
        if (
            failure == "writer_entry"
            and event == "call"
            and frame.f_code is _write_failure_diagnostics.__code__
        ):
            raise secondary
        if initial[0] is not None:
            initial[0](frame, event, arg)

    def trace(frame, event, arg):
        if initial[1] is not None:
            initial[1](frame, event, arg)
        return trace

    def guard():
        sys.setprofile(profile)
        sys.settrace(trace)
        try:
            yield
        finally:
            cleanup.append("entered")
            sys.setprofile(initial[0])
            sys.settrace(initial[1])
            cleanup.append("restored")

    def fail_write(path, value):
        if Path(path).name.startswith("transition-failure-"):
            raise secondary
        return write(path, value)

    if failure == "writer":
        monkeypatch.setattr(runner.snapshot, "write_json", fail_write)
    generator = guard()
    next(generator)
    chosen = None if primary_kind == "none" else primary
    try:
        with pytest.raises(OSError if chosen is None else Primary) as caught:
            _drain_guard(
                generator,
                True,
                (context,),
                tmp_path / "injected",
                required_hooks=initial,
                primary=chosen,
            )
        assert caught.value is (secondary if chosen is None else primary)
        if chosen is not None:
            assert caught.value.__cause__ is cause
        assert cleanup == ["entered", "restored"]
        assert sys.getprofile() is initial[0] and sys.gettrace() is initial[1]
        assert any(
            row[1] is secondary and row[2] == (context,) and row[3] is chosen
            for row in _DIAGNOSTIC_ERRORS
        )
        write(
            tmp_path / "guard-diagnostic-failure.json",
            dict(
                primary_kind=primary_kind,
                failure=failure,
                diagnostic_error_retained=True,
                original_primary_and_cause_preserved=chosen is not None,
                inherited_generator_cleanup_entered=True,
                both_hooks_restored=True,
                native_entries=0,
            ),
        )
    finally:
        sys.setprofile(initial[0])
        sys.settrace(initial[1])
        generator.close()


@pytest.mark.parametrize("primary_kind", ["none", "ordinary", "falsey"])
def test_diagnostic_and_generator_failure_both_retained_with_independent_hook_recovery(
    tmp_path, primary_kind
):
    initial = sys.getprofile(), sys.gettrace()
    diagnostic, cleanup = OSError("formatter rejected"), LookupError("generator cleanup rejected")

    class Primary(RuntimeError):
        def __bool__(self):
            return primary_kind != "falsey"

    class BadFormatter(RuntimeError):
        def __str__(self):
            raise diagnostic

    primary, cause = Primary("original caller failure"), KeyError("original cause")
    primary.__cause__ = cause
    context = NS(
        source_error=BadFormatter(), observation_error=None, capture_errors=(), record=None
    )

    def trace(frame, event, arg):
        if initial[1] is not None:
            initial[1](frame, event, arg)
        return trace

    def guard():
        sys.settrace(trace)
        try:
            yield
        finally:
            raise cleanup

    generator = guard()
    next(generator)
    selected = None if primary_kind == "none" else primary
    with pytest.raises(OSError if selected is None else Primary) as caught:
        _drain_guard(
            generator, True, (context,), tmp_path, required_hooks=initial, primary=selected
        )
    assert caught.value is (diagnostic if selected is None else primary)
    assert selected is None or caught.value.__cause__ is cause
    assert sys.getprofile() is initial[0] and sys.gettrace() is initial[1]
    assert any(row[0] == "diagnostic" and row[1] is diagnostic for row in _DIAGNOSTIC_ERRORS)
    assert any(
        row[0] == "inherited_guard_cleanup" and row[1] is cleanup for row in _DIAGNOSTIC_ERRORS
    )
    runner.snapshot.write_json(
        tmp_path / "combined-guard-cleanup.json",
        dict(
            primary_kind=primary_kind,
            diagnostic_and_cleanup_separate=True,
            original_primary_preserved=selected is not None,
            both_original_hooks_restored=True,
            native_entries=0,
        ),
    )
