"""Blocked source/owner contracts and actual CPython observation plumbing.

Private stand-ins exercise the driver, never a genuine owner or native body.
Small arrays test raw retention, not junction physics or graph correctness.
"""

import ast
import sys
from contextlib import contextmanager
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_seed_junctions as stage
from tests.unit import test_betse_native_seed_init_core as old
from validation.betse import betse_native_seed_junctions_software as software

_RAW_GUARD_SCOPES = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    function = old.clone(
        old.blocked.__wrapped__, stage=stage, software=software, _RAW_GUARD_SCOPES=_RAW_GUARD_SCOPES
    )
    with contextmanager(function)(request, tmp_path, monkeypatch):
        yield


def clone(function, **overrides):
    return old.clone(function, **overrides)


def context():
    value = old.context()
    value.stage = "synthetic_junction_contract"
    value.entered, value.method_returns = [], []
    value.callback_frames, value.callback_returned, value.callback_statuses = [], [], []
    value.callbacks_completed, value.callback_exception = [], None
    value.wrapper_claims, value.dispatch_frames = {}, {}
    value.original_wrappers, value.native_delegates = {}, {}
    value.allowed_codes, value.callback_codes, value.wrapper_codes = frozenset(), frozenset(), set()
    value.callback_helpers, value.helper_functions = (), ()
    value.caller_frame, value.last_method_return = None, None
    return value


@contextmanager
def active(value):
    stage._ACTIVE.append(value)
    try:
        yield value
    finally:
        assert stage._ACTIVE.pop() is value


def save(tmp_path, label, value):
    cache = stage._CORE.caches.snapshot(value)
    software.snapshot.write_json(
        tmp_path / (label + ".json"),
        dict(
            descriptor=cache.descriptor,
            identity=cache.identity,
            all_finite=cache.all_finite,
            synthetic_contract_only=True,
            native_or_scientific_credit=0,
        ),
    )
    np.savez(tmp_path / (label + ".npz"), **cache.numeric_columns())
    return cache


def definitions():
    return {
        n.name: n
        for n in ast.parse((software.ROOT / software.SOURCE).read_bytes()).body
        if isinstance(n, ast.FunctionDef)
    }


def test_junction_exact_whole_methods_and_four_caller_statements(tmp_path):
    plan = stage.source_plan()
    software.snapshot.write_json(tmp_path / "source-plan.json", plan)
    assert plan["methods"] == ("redo_gj", "calc_gj_vects", "graphLaplacian")
    assert [
        (plan["bodies"][n]["first_line"], plan["bodies"][n]["last_line"]) for n in stage.METHODS
    ] == [(1941, 2015), (2018, 2118), (1845, 1894)]
    assert plan["caller_statements"] == (148, 150, 154, 156)
    assert plan["callbacks"] == stage.CALLBACK_STATUSES
    assert len(plan["reused_source_pins"]) == 2
    assert plan["inherited_flux_modes"] == ("original", "disabled")
    assert all(
        plan[n] is None
        for n in (
            "parent_source_pin",
            "parent_review_pin",
            "coordinator_source_pin",
            "coordinator_review_pin",
        )
    )
    assert not plan["source_native_or_scientific_release"] and not plan["physical_admission"]


@pytest.mark.parametrize("name", ["redo_gj", "calc_gj_vects", "graphLaplacian", "continue_seed"])
def test_junction_original_codes_compiled_never_entered(name):
    code = stage._codes()[name]
    assert type(code) is CodeType and code.co_name == name
    assert code.co_filename.startswith(str(stage._PREFIX.aliases.NATIVE))


def test_junction_original_quirks_inverse_and_stop_are_exact():
    nodes = stage._source_nodes()
    redo, vectors, graph = (ast.unparse(nodes[n]) for n in stage.METHODS)
    assert "for indices in self.cell_nn:" in redo
    assert "sum(self.num_nn) / len(self.num_nn)" in redo
    assert "self.calc_gj_vects(p)" in redo
    assert "self.nn_len.append(-1)" in vectors
    assert "self.mesh.delta_tri_0_inv" in graph
    assert not any(x in graph for x in ("pinv", "svd", "lstsq", "np.linalg"))
    caller = ast.unparse(nodes["continue_seed"])
    assert "phase.cells.redo_gj(phase)" in caller
    assert "phase.cells.graphLaplacian(self._p)" in caller
    assert not any(
        x in caller for x in ("deform_tools", "save_cluster", "sim_info_report", "progressed_last")
    )


@pytest.mark.parametrize("entry", ["request", "prepare"])
def test_junction_unbound_pins_refuse_before_parent_lookup(monkeypatch, entry):
    def forbidden(*args, **kwargs):
        raise AssertionError("No parent lookup while closed")

    monkeypatch.setattr(stage.previous, "_authority", forbidden)
    with pytest.raises(stage.JunctionsRejected, match="remains held") as caught:
        if entry == "request":
            stage.from_profiles(object(), law_id=stage.LAW_ID)
        else:
            stage.prepare(object(), enabled=True)
    assert caught.value.stage == "unbound_contract"


@pytest.mark.parametrize("law", [None, True, "", "redo_gj"])
def test_junction_explicit_law_precedes_parent_or_route(law, monkeypatch):
    monkeypatch.setattr(stage, "_ready", lambda: pytest.fail("No route for wrong law"))
    with pytest.raises(stage.JunctionsRejected) as caught:
        stage.from_profiles(object(), law_id=law)
    assert caught.value.stage == "law"


@pytest.mark.parametrize("kind", ["constructor", "foreign", "restore"])
def test_junction_no_supplied_or_hydrated_owner(kind):
    with pytest.raises((TypeError, stage.JunctionsRejected)):
        if kind == "constructor":
            stage.JunctionsOwner()
        elif kind == "foreign":
            stage._authority(object())
        else:
            object.__new__(stage.JunctionsOwner).__reduce_ex__(4)
    assert not stage._ISSUED


def test_junction_single_claim_and_exact_parent_trial_contract():
    body = ast.unparse(definitions()["prepare"])
    assert (
        body.index("_CONSUMED[request]")
        < body.index("context.parent_claim(")
        < body.index("_namespace(context)")
    )
    assert "expected=refs[1]" in body
    assert (
        "exact retained previous.Trial" in stage.source_plan()["parent_hooks"][stage.PROPOSED_CLAIM]
    )
    assert "_restore" in ast.unparse(definitions()["_caller_restore"])
    assert stage.source_plan()["router"] == "_seed_junctions_api"


class FalseySource(RuntimeError):
    def __bool__(self):
        return False


class BadAppend:
    def __init__(self, error):
        self.error = error

    def append(self, value):
        raise self.error


def observation_case(monkeypatch):
    """Run actual private hook/dispatch machinery with no issued authority."""
    ctx, delivered = context(), []
    p = NS(marker=1)
    assembly = object()

    def callback_body(self, *, status):
        delivered.append((self, status))

    def callback_wrapper(self, *args, **kwargs):
        return callback_body(self, *args, **kwargs)

    class Callback:
        progressed_next = callback_wrapper

    class Cells:
        pass

    cells, callback = Cells(), Callback()
    phase = NS(p=p, cells=cells, callbacks=callback, dyna=object(), sim=object())
    ctx.phase, ctx.p, ctx.cells, ctx.callback, ctx.assembly = phase, p, cells, callback, assembly
    ctx.callback_target, ctx.status_targets = callback, list(stage.CALLBACK_STATUSES)
    ctx.core_action, ctx.helper_action, ctx.graph_action = None, None, None
    ctx.original_names = ()
    ctx.callback_chain = (callback_wrapper, callback_body)
    ctx.callback_codes = frozenset(f.__code__ for f in ctx.callback_chain)
    ctx.caller = NS(_callbacks=callback, _p=p)

    def calc_gj_vects(self, p):
        delivered.append("vectors")
        for field in stage.OUTPUTS["calc_gj_vects"]:
            setattr(self, field, [])
        if ctx.helper_action is not None:
            return ctx.helper_action()

    def redo_gj(self, phase):
        delivered.append("redo")
        for field in stage.OUTPUTS["redo_gj"]:
            setattr(self, field, [])
        if ctx.core_action is not None:
            ctx.core_action()
        self.calc_gj_vects(phase.p)

    def graphLaplacian(self, p):
        delivered.append("graph")
        for field in stage.OUTPUTS["graphLaplacian"]:
            setattr(self, field, [])
        if ctx.graph_action is not None:
            ctx.graph_action()

    def continue_seed(self, phase):
        ctx.callback_target.progressed_next(status=ctx.status_targets[0])
        phase.cells.redo_gj(phase)
        ctx.callback_target.progressed_next(status=ctx.status_targets[1])
        phase.cells.graphLaplacian(self._p)

    ctx.methods = dict(
        redo_gj=redo_gj,
        calc_gj_vects=calc_gj_vects,
        graphLaplacian=graphLaplacian,
        continue_seed=continue_seed,
    )
    ctx.body_codes = {ctx.methods[n].__code__: n for n in stage.METHODS}

    def route(context, label, delegate, actual, args, kwargs):
        return stage._dispatch(ctx, context, label, delegate, actual, args, kwargs, sys._getframe())

    def native_call(context, label, delegate, actual, *args, **kwargs):
        return route(context, label, delegate, actual, args, kwargs)

    def factory(method, delegate):
        context, name = assembly, "Cells"

        def invoke(actual, *args, **kwargs):
            stage._wrapper_guard(ctx, context, sys._getframe())
            return native_call(context, name + "." + method, delegate, actual, *args, **kwargs)

        return invoke

    ctx.native_call_code = native_call.__code__
    for name in stage.METHODS:
        fn = ctx.methods[name]
        wrapper = factory(name, fn)
        setattr(Cells, name, wrapper)
        ctx.original_wrappers[name], ctx.native_delegates[name] = wrapper, fn
    ctx.wrapper_codes = {f.__code__ for f in ctx.original_wrappers.values()}

    def check(value):
        assert value is ctx
        stage._guard(value)
        if phase.p is not p or phase.cells is not cells or p.marker != 1:
            raise ValueError("Private stand-in association changed")
        stage._check_fields(value)

    monkeypatch.setattr(stage, "_check", check)
    monkeypatch.setattr(stage, "_cache", lambda context, raw: stage._CORE.caches.snapshot(raw))

    def run(*, profile=None, trace=None):
        old_profile, old_trace = sys.getprofile(), sys.gettrace()

        def prior_profile(frame, event, arg):
            if old_profile is not None:
                old_profile(frame, event, arg)
            if profile is not None:
                profile(frame, event, arg)

        local_traces = {}

        def prior_trace(frame, event, arg):
            old = old_trace if event == "call" else local_traces.get(id(frame))
            if old is not None:
                value = old(frame, event, arg)
                if event == "call" or value is not None:
                    local_traces[id(frame)] = value
            if trace is not None:
                trace(frame, event, arg)
            if event == "return":
                local_traces.pop(id(frame), None)
            return prior_trace

        sys.setprofile(prior_profile)
        sys.settrace(prior_trace)
        ctx.required_hooks = (prior_profile, prior_trace)
        ctx.driver_frame = sys._getframe()
        try:
            with active(ctx), stage._account(ctx):
                ctx.methods["continue_seed"](ctx.caller, phase)
        finally:
            try:
                sys.settrace(old_trace)
            finally:
                sys.setprofile(old_profile)
        return ctx

    return NS(
        ctx=ctx,
        delivered=delivered,
        run=run,
        Callback=Callback,
        callback_body=callback_body,
        callback_wrapper=callback_wrapper,
    )


def test_junction_real_observer_and_dispatch_orders_two_callbacks_and_three_methods(
    monkeypatch, tmp_path
):
    case = observation_case(monkeypatch)
    before_prior = []

    def prior(frame, event, arg):
        if event == "call" and frame.f_code in case.ctx.body_codes:
            before_prior.append(case.ctx.admitted[id(frame)]["name"])

    case.run(profile=prior, trace=prior)
    assert case.delivered == [
        (case.ctx.callback, stage.CALLBACK_STATUSES[0]),
        "redo",
        "vectors",
        (case.ctx.callback, stage.CALLBACK_STATUSES[1]),
        "graph",
    ]
    assert before_prior == ["redo_gj"] * 2 + ["calc_gj_vects"] * 2 + ["graphLaplacian"] * 2
    assert tuple(case.ctx.entered) == stage.METHODS
    assert tuple(n for n, _ in case.ctx.method_returns) == stage.RETURN_ORDER
    assert case.ctx.callbacks_completed == [0, 1]
    assert case.ctx.callback_returned == [[1, 0], [1, 0]]
    stage._complete(case.ctx)
    assert case.ctx.hooks_safe and not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "actual-hook-order.json",
        dict(
            methods=case.ctx.entered,
            returns=[n for n, _ in case.ctx.method_returns],
            callbacks=case.ctx.callbacks_completed,
            real_observe_and_dispatch=True,
            genuine_owner_or_native_entry=False,
        ),
    )


@pytest.mark.parametrize("which", ["receiver", "first_status", "second_status"])
def test_junction_callback_same_code_receiver_and_each_status_refuse(monkeypatch, which):
    case = observation_case(monkeypatch)
    if which == "receiver":
        case.ctx.callback_target = case.Callback()
    else:
        case.ctx.status_targets[0 if which == "first_status" else 1] = "foreign"
    with pytest.raises(stage.JunctionsRejected):
        case.run()
    assert "graph" not in case.delivered and not stage._ISSUED
    if which != "second_status":
        assert "redo" not in case.delivered


@pytest.mark.parametrize("which", ["receiver", "parameter", "phase"])
def test_junction_same_code_method_wrong_actual_argument_refuses_before_delegate(
    monkeypatch, which
):
    case = observation_case(monkeypatch)

    def prior(frame, event, arg):
        if event == "call" and frame.f_code is case.ctx.methods["redo_gj"].__code__:
            frame.f_locals["self" if which == "receiver" else "phase"] = (
                object() if which != "parameter" else NS(p=object())
            )

    with pytest.raises(stage.JunctionsRejected):
        case.run(profile=prior)
    assert "redo" not in case.delivered


@pytest.mark.parametrize("kind", ["reentry", "mutation", "entry_error"])
def test_junction_inherited_entry_guard_and_caught_reentry_stay_sticky(monkeypatch, kind):
    case, failures = observation_case(monkeypatch), []
    error = ValueError("prior entry")

    def prior(frame, event, arg):
        if event == "call" and frame.f_code is case.ctx.methods["redo_gj"].__code__:
            if kind == "entry_error":
                raise error
            if kind == "mutation":
                case.ctx.p.marker = 2
            else:
                try:
                    case.ctx.callback.progressed_next(status=stage.CALLBACK_STATUSES[0])
                except stage.JunctionsRejected as caught:
                    failures.append(caught)

    with pytest.raises((stage.JunctionsRejected, ValueError)):
        case.run(profile=prior)
    assert "redo" not in case.delivered and case.ctx.hooks_safe
    if kind == "reentry":
        assert len(failures) == 1 and failures[0] is case.ctx.entry_error


@pytest.mark.parametrize("where", ["prior_exception", "locals", "history"])
def test_junction_falsey_native_style_failure_keeps_raw_cause_before_observers(monkeypatch, where):
    case = observation_case(monkeypatch)
    primary, cause, secondary = (
        FalseySource("original stand-in"),
        ZeroDivisionError("original zero division"),
        RuntimeError("observer"),
    )
    primary.__cause__ = cause

    def action():
        raise primary

    case.ctx.core_action = action
    if where == "history":
        case.ctx.source_exceptions = BadAppend(secondary)
    if where == "locals":

        class Locals(dict):
            def __setitem__(self, name, value):
                if name == "redo_gj":
                    raise secondary
                super().__setitem__(name, value)

        case.ctx.locals = Locals()

    def prior(frame, event, arg):
        if (
            where == "prior_exception"
            and event == "exception"
            and frame.f_code is case.ctx.methods["redo_gj"].__code__
        ):
            assert case.ctx.primary is primary
            raise secondary

    with pytest.raises(FalseySource) as caught:
        case.run(trace=prior)
    assert caught.value is primary and primary.__cause__ is cause
    assert case.ctx.last_source_exception[1][1] is primary
    assert case.ctx.observation_error is secondary
    assert case.ctx.hooks_safe and "vectors" not in case.delivered and "graph" not in case.delivered


@pytest.mark.parametrize("where", ["input", "return", "prior_return"])
def test_junction_helper_raw_return_or_inputs_retained_before_failed_observer(
    monkeypatch, tmp_path, where
):
    case = observation_case(monkeypatch)
    raw, error, calls = np.asarray([1.0, -0.0, float("inf")]), ValueError("capture"), []

    def delegate(n):
        calls.append(n)
        return raw

    def observed():
        return stage._helper(case.ctx, "ones", delegate, (3,), {}, sys._getframe())

    def redo(self, phase):
        observed()
        case.delivered.append("after helper")

    # Replace only the private stand-in method/body together, never native code.
    original = case.ctx.original_wrappers["redo_gj"]
    closure = dict(zip(original.__code__.co_freevars, original.__closure__, strict=True))
    cell = (lambda value: lambda: value)(redo).__closure__[0]
    new = FunctionType(
        original.__code__,
        original.__globals__,
        original.__name__,
        original.__defaults__,
        tuple(
            cell if name == "delegate" else closure[name] for name in original.__code__.co_freevars
        ),
    )
    case.ctx.methods["redo_gj"], case.ctx.native_delegates["redo_gj"] = redo, redo
    case.ctx.original_wrappers["redo_gj"] = new
    type(case.ctx.cells).redo_gj = new
    case.ctx.body_codes = {case.ctx.methods[n].__code__: n for n in stage.METHODS}
    case.ctx.helpers = {"ones": delegate}
    if where == "input":
        case.ctx.helper_inputs = BadAppend(error)
    elif where == "return":
        case.ctx.helper_returns = BadAppend(error)

    def prior(frame, event, arg):
        if where == "prior_return" and event == "return" and frame.f_code is delegate.__code__:
            assert case.ctx.last_helper_return[1] is raw
            raise error

    with pytest.raises(stage._LITERAL._CaptureStop):
        case.run(profile=prior)
    assert case.ctx.observation_error is error and case.ctx.primary is None
    assert (
        not case.ctx.helper_busy
        and "after helper" not in case.delivered
        and "graph" not in case.delivered
    )
    if where == "input":
        assert calls == [] and case.ctx.last_helper[:3] == ("ones", (3,), {})
    else:
        assert (
            calls == [3]
            and case.ctx.last_helper_return[1] is raw
            and case.ctx.last_helper[3] is raw
        )
        saved = save(tmp_path, "raw-return", raw)
        assert saved.all_finite is False


def test_junction_restore_call_rejection_cannot_replace_primary(monkeypatch):
    case = observation_case(monkeypatch)
    primary, cause, secondary = (
        FalseySource("source"),
        KeyError("cause"),
        ValueError("restore entry"),
    )
    primary.__cause__ = cause

    def action():
        raise primary

    case.ctx.core_action = action

    def prior(frame, event, arg):
        if event == "call" and frame.f_code is stage._restore.__code__:
            raise secondary

    with pytest.raises(FalseySource) as caught:
        case.run(profile=prior)
    assert caught.value is primary and primary.__cause__ is cause and case.ctx.hooks_safe
    assert any(row[1] is secondary for row in case.ctx.cleanup_errors)


def test_junction_helper_inherited_entry_rejection_is_observation_not_source(monkeypatch, tmp_path):
    case = observation_case(monkeypatch)
    raw = np.asarray([1.0, -0.0])
    args, kwargs, calls = (raw,), {"order": "C"}, []
    error, cause = ValueError("inherited helper entry guard"), KeyError("guard cause")
    error.__cause__ = cause

    def delegate(shape, *, order):
        calls.append((shape, order))
        raise AssertionError("The helper body must not execute")

    def observed():
        return stage._helper(case.ctx, "ones", delegate, args, kwargs, sys._getframe())

    def redo(self, phase):
        observed()
        case.delivered.append("after helper")

    original = case.ctx.original_wrappers["redo_gj"]
    closure = dict(zip(original.__code__.co_freevars, original.__closure__, strict=True))
    cell = (lambda value: lambda: value)(redo).__closure__[0]
    wrapper = FunctionType(
        original.__code__,
        original.__globals__,
        original.__name__,
        original.__defaults__,
        tuple(
            cell if name == "delegate" else closure[name] for name in original.__code__.co_freevars
        ),
    )
    case.ctx.methods["redo_gj"], case.ctx.native_delegates["redo_gj"] = redo, redo
    case.ctx.original_wrappers["redo_gj"] = wrapper
    type(case.ctx.cells).redo_gj = wrapper
    case.ctx.body_codes = {case.ctx.methods[n].__code__: n for n in stage.METHODS}
    case.ctx.helpers = {"ones": delegate}
    entries = []

    def prior(frame, event, arg):
        if event == "call" and frame.f_code is delegate.__code__:
            entries.append((frame, case.ctx.admitted[id(frame)]["role"]))
            assert case.ctx.helper_inputs[0][1] is args
            assert case.ctx.helper_inputs[0][2] is kwargs
            raise error

    with pytest.raises(ValueError) as caught:
        case.run(profile=prior)
    assert caught.value is error and error.__cause__ is cause
    assert len(entries) == 1 and entries[0][1] == "helper"
    assert calls == [] and case.ctx.primary is None and case.ctx.entry_error is None
    assert case.ctx.observation_error is error
    assert case.ctx.helper_inputs[0][1] is args and case.ctx.helper_inputs[0][2] is kwargs
    assert case.ctx.last_helper[1] is args and case.ctx.last_helper[2] is kwargs
    assert case.ctx.last_helper[3] is None
    assert case.ctx.last_helper_return[:2] == ("ones", None)
    assert case.ctx.last_helper_return[2] is error  # Raw unwind, not a successful helper return.
    assert case.ctx.helper_returns == [] and not case.ctx.helper_busy
    assert case.ctx.entered == ["redo_gj"] and case.ctx.method_returns == []
    assert "after helper" not in case.delivered and "vectors" not in case.delivered
    assert "graph" not in case.delivered and not stage._ISSUED and case.ctx.hooks_safe
    assert any(
        origin == "inherited_profile_call" and captured is error
        for origin, captured, retained in case.ctx.capture_errors
    )
    save(tmp_path, "rejected-helper-raw-inputs", dict(args=args, kwargs=kwargs))
    software.snapshot.write_json(
        tmp_path / "helper-entry-classification.json",
        dict(
            installed_profile=True,
            real_observe_and_dispatch=True,
            helper_body_calls=len(calls),
            source_primary_present=case.ctx.primary is not None,
            exact_observer_error=True,
            raw_input_identity_preserved=True,
            following_methods=[],
            native_or_scientific_credit=0,
        ),
    )


@pytest.mark.parametrize("kind", ["unrecoverable", "partial_clears"])
def test_junction_failure_capture_stops_after_hook_loss(kind):
    ctx, primary = context(), FalseySource("source")
    ctx.primary = primary
    expected, actual, calls = (object(), object()), [], []
    actual[:] = expected
    ctx.required_hooks, ctx.restore_getters = expected, (lambda: actual[0], lambda: actual[1])

    def profile(value):
        actual[0] = value
        if kind == "unrecoverable":
            actual[1] = None

    def trace(value):
        actual[1] = value

    def partial(value):
        calls.append(value)
        actual[0] = None
        raise ValueError("partial clears hook")

    ctx.restore_setters = (profile, trace)
    if kind == "unrecoverable":
        actual[1] = None
    fn = clone(stage._failure, _raw_partial=partial, _FAILED=())
    with pytest.raises(FalseySource) as caught:
        fn(ctx, primary)
    assert caught.value is primary and fn.__globals__["_LAST_FAILED"] is ctx
    assert ctx.metadata_stopped and not hasattr(primary, "seed_junctions_partial")
    assert len(calls) == (0 if kind == "unrecoverable" else 1)


@pytest.mark.parametrize("which", ["extra", "deleted", "order"])
def test_junction_output_field_scope_refuses_unrelated_or_reordered_store(which):
    ctx = context()
    ctx.cells = NS(original=object())
    ctx.original_names = ("original",)
    ctx.entered = ["redo_gj"]
    for name in stage.OUTPUTS["redo_gj"]:
        setattr(ctx.cells, name, [])
    stage._check_fields(ctx)
    if which == "extra":
        ctx.cells.foreign = 1
    elif which == "deleted":
        del ctx.cells.original
    else:
        value = vars(ctx.cells).pop("cell_nn_connected")
        ctx.cells.cell_nn_connected = value
    with pytest.raises(ValueError):
        stage._check_fields(ctx)


def test_junction_original_nonoutput_aliases_and_map_order_are_observed(monkeypatch):
    # The existing graph walker sees real stand-in object references, not IDs
    # substituted into a reconstructed numerical owner.
    first, second = [1, 1], [1, 1]
    ctx = context()
    ctx.cells = NS(cell_target_inds={"first": first, "second": second}, untouched=np.asarray([2.0]))
    ctx.p, ctx.sim, ctx.dyna, ctx.mesh, ctx.grid = (NS() for _ in range(5))
    ctx.world = object()
    ctx.stable_caller, ctx.profile_views = {}, ()
    ctx.graph_view, ctx.stable_view = NS(), NS()
    ctx.graph_tape = NS(rng=object(), events=(), draws=(), locals={})
    callers = stage._WORLD.observation.callers
    monkeypatch.setattr(stage._WORLD, "_scope", lambda value: NS(graph=callers._graph))
    before = stage._graph(ctx, stable=True)
    ctx.cells.gj_default_weights = np.asarray([0.0])
    after = stage._graph(ctx, stable=True)
    stage._WORLD._same(before[0], after[0])
    assert before[1] == after[1]
    ctx.cells.cell_target_inds["first"], ctx.cells.cell_target_inds["second"] = second, first
    changed = stage._graph(ctx, stable=True)
    assert before[1] != changed[1] or any(
        a is not b for a, b in zip(before[0], changed[0], strict=True)
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("callbacks_completed", [0]),
        ("callback_exception", ValueError("callback")),
        ("primary", FalseySource("source")),
        ("observation_error", ValueError("capture")),
        ("cleanup_errors", (("failed",),)),
        ("hooks_safe", False),
    ],
)
def test_junction_incomplete_or_failed_epoch_cannot_complete(monkeypatch, field, value):
    case = observation_case(monkeypatch)
    case.run()
    stage._complete(case.ctx)
    setattr(case.ctx, field, value)
    with pytest.raises(ValueError, match="completion required"):
        stage._complete(case.ctx)


def test_junction_runner_closed_scope_and_exact_cpu_policy():
    assert software.SOFTWARE_RELEASE == "BETSE_NATIVE_SEED_JUNCTIONS_SOFTWARE_RELEASED"
    assert len(software.OWNED) == 4
    assert "cells.processes.betse_native_seed_junctions_source" in software.FORBIDDEN_MODULES
    assert "cells.processes.betse_post_cut_mesh_contact_source" in software.FORBIDDEN_MODULES
    text = (software.ROOT / software.FILE).read_text()
    assert "os.sched_getaffinity(0) != {4}" in text
    assert "timeout=480" in text and "min_available_bytes=8 * 2**30" in text
    assert "software_bytes=2**30" in text
