"""Blocked contracts and small array retention; no native core or owner chain."""

import ast
import os
import sys
from contextlib import contextmanager
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_seed_init_core as stage
from tests.unit import test_betse_native_world_phase_construction as controls
from validation.betse import betse_native_seed_init_core_software as software

_RAW_GUARD_SCOPES = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit native-blocked software release required")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(software), reuse=software.reuse.reuse))
    namespace = dict(vars(controls), software=adapter, stage=stage, _BLOCKADE_FAILURES=())
    original = controls._blockade.__wrapped__
    fn = FunctionType(original.__code__, namespace, original.__name__)
    attempted = []

    def forbid(*args, **kwargs):
        attempted.append("numerical_or_RNG")
        raise AssertionError("No native, solver, RNG or model entry")

    try:
        with contextmanager(fn)(request, tmp_path):
            with monkeypatch.context() as patch:
                for name in ("pinv", "inv", "svd", "solve", "lstsq"):
                    patch.setattr(np.linalg, name, forbid)
                for name in (
                    "rand",
                    "randn",
                    "random",
                    "random_sample",
                    "uniform",
                    "normal",
                    "seed",
                    "set_state",
                    "RandomState",
                    "default_rng",
                ):
                    patch.setattr(np.random, name, forbid)
                try:
                    yield
                finally:
                    software.snapshot.write_json(
                        tmp_path / "solver-RNG-blocked.json",
                        dict(attempted=attempted, source_native_or_scientific_credit=0),
                    )
                assert attempted == []
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARD_SCOPES.append(namespace)


def clone(function, **overrides):
    result = FunctionType(
        function.__code__,
        dict(function.__globals__, **overrides),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def context():
    return NS(
        active=True,
        observing=False,
        inherited_hook_active=False,
        admitted={},
        active_helper=None,
        helper_frame=None,
        last_helper_return=None,
        last_source_exception=None,
        last_source_return=None,
        raw_returns=[],
        locals={},
        hooks_safe=True,
        metadata_stopped=False,
        call_tracing=sys.call_tracing,
        invalid=False,
        thread=stage.get_ident(),
        entry_error=None,
        observation_error=None,
        capture_errors=(),
        cleanup_errors=(),
        primary=None,
        stage="synthetic_contract",
        request=None,
        trial=None,
        events=[],
        stages=[],
        last_observation=None,
        helper_busy=False,
        helper_inputs=[],
        helper_returns=[],
        last_helper=None,
        body_codes={},
        frames={},
        helpers={},
        source_exceptions=[],
        required_hooks=(sys.getprofile(), sys.gettrace()),
        restore_setters=(sys.setprofile, sys.settrace),
        restore_getters=(sys.getprofile, sys.gettrace),
    )


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
            source_native_or_scientific_credit=0,
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


def test_core_complete_original_bodies_and_two_caller_statements(tmp_path):
    plan = stage.source_plan()
    software.snapshot.write_json(tmp_path / "source-plan.json", plan)
    assert plan["methods"] == ("init_core", "initDenv")
    assert plan["bodies"]["init_core"]["first_line"] == 452
    assert plan["bodies"]["init_core"]["last_line"] == 754
    assert plan["bodies"]["initDenv"]["first_line"] == 2347
    assert plan["bodies"]["initDenv"]["last_line"] == 2400
    assert plan["callback_source_lines"] == (138, 139, 140)
    assert plan["inherited_flux_modes"] == ("original", "disabled")
    assert plan["original_flux_numerics_unchanged"] is True
    assert plan["source_native_or_scientific_release"] is False
    assert plan["INIT_or_physical_admission"] is False
    assert all(
        plan[n] is None
        for n in (
            "parent_source_pin",
            "parent_review_pin",
            "coordinator_source_pin",
            "coordinator_review_pin",
        )
    )


@pytest.mark.parametrize("name", ["init_core", "initDenv", "continue_seed"])
def test_core_original_code_is_compiled_not_entered(name, tmp_path):
    code = stage._codes()[name]
    assert type(code) is CodeType
    assert code.co_filename.startswith(str(stage._PREFIX.aliases.NATIVE))
    assert "init_dynamics" not in code.co_names
    assert "makeLaplacian" not in code.co_names
    if name == "continue_seed":
        assert code.co_names == ("_callbacks", "progressed_next", "sim", "init_core")
        assert stage.CALLBACK_STATUS in code.co_consts
    software.snapshot.write_json(
        tmp_path / "unexecuted-code.json",
        dict(
            name=name,
            filename=code.co_filename,
            names=code.co_names,
            first_line=code.co_firstlineno,
            executed=False,
        ),
    )


def test_core_original_branch_and_ion_order_are_not_reimplemented():
    nodes = stage._source_nodes()
    body = ast.unparse(nodes["init_core"])
    assert "ion_names = list(p.ions_dict.keys())" in body
    assert "for name in ion_names:" in body
    assert "if name == 'M' and p.ions_dict['Ca'] == 1:" in body
    assert "self.cM_er[:] = p.cCa_er" in body
    assert body.count("self.initDenv(cells, p)") == 1
    calls = [
        n
        for n in ast.walk(nodes["init_core"])
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "p.is_ecm"
        and "self.initDenv(cells, p)" in ast.unparse(n)
    ]
    assert len(calls) == 1
    assert ast.unparse(nodes["initDenv"]).count("gaussian_filter(") == 2
    assert body.endswith("self.u_env_y = 0.0")


@pytest.mark.parametrize("kind", ["prepare", "request"])
def test_core_unbound_adoption_never_reads_foreign_parent(kind, monkeypatch):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("Foreign owner read before a closed gate")

    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.InitCoreRejected) as caught:
        if kind == "prepare":
            stage.prepare(Foreign(), enabled=True)
        else:
            stage.from_world(Foreign(), law_id=stage.LAW_ID)
    assert caught.value.stage == "unbound_contract"
    assert not stage._REQUESTS and not stage._CONSUMED and not stage._RETIRED and not stage._ISSUED


@pytest.mark.parametrize("law", [None, True, "", "init_core"])
def test_core_law_refuses_before_any_parent_access(law):
    with pytest.raises(stage.InitCoreRejected) as caught:
        stage.from_world(object(), law_id=law)
    assert caught.value.stage == "law"


@pytest.mark.parametrize("kind", ["constructor", "unissued", "checkpoint"])
def test_core_no_supplied_or_rehydrated_owner(kind):
    if kind == "constructor":
        with pytest.raises(TypeError):
            stage.InitCoreOwner()
    elif kind == "unissued":
        with pytest.raises(stage.InitCoreRejected) as caught:
            stage._authority(NS())
        assert caught.value.stage == "owner"
    else:
        with pytest.raises(TypeError):
            object.__new__(stage.InitCoreOwner).__reduce_ex__(4)


def test_core_single_irreversible_claim_and_actual_sim_dispatch_contract():
    funcs = definitions()
    prepare = ast.unparse(funcs["prepare"])
    assert prepare.count("previous._authority(") == 1
    assert prepare.index("_CONSUMED[request] = _RETIRED[") < prepare.index("context.parent_claim(")
    assert prepare.index("context.parent_claim(") < prepare.index("_namespace(context)")
    assert prepare.index("context.trial = replace(") < prepare.index(
        "object.__new__(InitCoreOwner)"
    )
    assert "context.methods['continue_seed'](context.caller, context.phase)" in prepare
    check = ast.unparse(funcs["_check"])
    assert "previous._authority(" not in check
    assert "context.phase.sim is not context.sim" in check
    assert "context.parent_check(context) is not context.parent" in check
    assert "context.parent.request.flux_operator != context.request.flux_operator" in check
    namespace = ast.unparse(funcs["_namespace"])
    assert "closure.get('delegate')" in namespace
    assert "closure.get('context') is not context.assembly" in namespace
    assert "_source_function(delegate, 'betse/science/sim.py', name, 'Simulator')" in namespace


@pytest.mark.parametrize(
    "array", [np.asarray([0.0, -0.0, 3.0]), np.asarray([np.nan, np.inf, -np.inf])]
)
def test_core_raw_record_precedes_cache_failure_without_changing_bits(array, tmp_path):
    ctx = context()
    before = array.tobytes()
    capture = RuntimeError("synthetic encoder failure")

    def fail(context, value):
        assert context.last_observation[1] is array
        assert context.events[-1][1] is array
        raise capture

    record = clone(stage._record, _cache=fail)
    with active(ctx), pytest.raises(stage._LITERAL._CaptureStop) as caught:
        record(ctx, "raw", array)
    assert caught.value.__cause__ is capture
    assert ctx.observation_error is capture
    assert ctx.capture_errors[0][2] is array
    assert array.tobytes() == before
    save(tmp_path, "raw-failed-capture", array)


def test_core_completed_cache_is_independent_of_later_mutation(tmp_path):
    ctx = context()
    raw = np.asarray([1.0, -0.0, 4.0])
    record = clone(stage._record, _cache=lambda c, value: stage._CORE.caches.snapshot(value))
    with active(ctx):
        record(ctx, "return", raw)
    saved = ctx.stages[0][1]
    initial = saved.identity
    raw[0] = 12.0
    assert ctx.events[0][1] is raw
    assert saved.identity == initial
    assert stage._CORE.caches.snapshot(raw).identity != initial
    save(tmp_path, "raw-mutated", raw)
    software.snapshot.write_json(
        tmp_path / "retained.json", dict(descriptor=saved.descriptor, identity=saved.identity)
    )
    np.savez(tmp_path / "retained.npz", **saved.numeric_columns())


def helper_case(delegate, *, cache=None, check=None):
    ctx = context()
    ctx.helpers = {"zeros": delegate}
    record = clone(stage._record, _cache=cache or (lambda c, raw: stage._CORE.caches.snapshot(raw)))
    helper = clone(stage._helper, _check=check or (lambda c: None), _record=record)

    def wrapper():
        return helper(ctx, "zeros", delegate, (2,), {}, sys._getframe())

    def body():
        ctx.frames["init_core"] = sys._getframe()
        return wrapper()

    ctx.body_codes = {body.__code__: "init_core"}
    return ctx, body


def test_core_actual_synthetic_helper_return_preserved_before_observer_failure(tmp_path):
    raw = np.asarray([3.0, -0.0])
    error = RuntimeError("return capture")
    count = []

    def cache(ctx, value):
        count.append(value)
        if len(count) == 2:
            assert ctx.helper_returns == [("zeros", raw)]
            assert ctx.last_helper[3] is raw
            raise error
        return stage._CORE.caches.snapshot(value)

    ctx, body = helper_case(lambda n: raw, cache=cache)
    with active(ctx), pytest.raises(stage._LITERAL._CaptureStop):
        body()
    assert ctx.primary is None
    assert ctx.observation_error is error
    assert not ctx.helper_busy
    save(tmp_path, "helper-raw", raw)


def test_core_helper_original_primary_and_cause_not_observer_error():
    cause, error = KeyError("cause"), RuntimeError("native stand-in failure")
    error.__cause__ = cause

    def fail(n):
        raise error

    ctx, body = helper_case(fail)
    with active(ctx), pytest.raises(RuntimeError) as caught:
        body()
    assert caught.value is ctx.primary is error
    assert caught.value.__cause__ is cause
    assert ctx.helper_returns == []
    assert ctx.helper_inputs == [("zeros", (2,), {})]
    assert not ctx.helper_busy


def test_core_failed_input_capture_prevents_delegate():
    entered = []
    error = ValueError("input capture")

    def cache(c, value):
        raise error

    ctx, body = helper_case(lambda n: entered.append(n), cache=cache)
    with active(ctx), pytest.raises(stage._LITERAL._CaptureStop):
        body()
    assert entered == [] and ctx.observation_error is error and ctx.primary is None


@pytest.mark.parametrize("foreign", ["caller", "delegate", "reentry"])
def test_core_helper_refuses_wrong_frame_delegate_or_reentry(foreign):
    ctx, body = helper_case(lambda n: np.asarray([1.0, 2.0]))
    if foreign == "caller":
        ctx.body_codes = {}
    elif foreign == "delegate":
        ctx.helpers["zeros"] = lambda n: None
    else:
        ctx.helper_busy = True
    with active(ctx), pytest.raises(stage.InitCoreRejected):
        body()
    assert ctx.helper_inputs == []


@pytest.mark.parametrize("ecm", [False, True])
def test_core_completion_requires_exact_conditional_return_order(ecm):
    ctx = context()
    ctx.ecm = ecm
    ctx.entered = ["init_core", "initDenv"] if ecm else ["init_core"]
    ctx.method_returns = [("initDenv", None), ("init_core", None)] if ecm else [("init_core", None)]
    ctx.callback_completed, ctx.callback_exception = True, None
    stage._complete(ctx)
    ctx.method_returns.reverse()
    if ecm:
        with pytest.raises(ValueError):
            stage._complete(ctx)
    else:
        ctx.method_returns.append(("initDenv", None))
        with pytest.raises(ValueError):
            stage._complete(ctx)


@pytest.mark.parametrize(
    "field,value",
    [
        ("callback_completed", False),
        ("callback_exception", ValueError()),
        ("primary", ValueError()),
        ("observation_error", ValueError()),
        ("entry_error", ValueError()),
        ("cleanup_errors", (("restore", ValueError(), None),)),
        ("frames", {"unfinished": object()}),
    ],
)
def test_core_failure_or_incomplete_boundary_cannot_complete(field, value):
    ctx = context()
    ctx.ecm, ctx.entered, ctx.method_returns = False, ["init_core"], [("init_core", None)]
    ctx.callback_completed, ctx.callback_exception = True, None
    setattr(ctx, field, value)
    with pytest.raises(ValueError):
        stage._complete(ctx)


@pytest.mark.parametrize("where", ["partial", "attachment"])
def test_core_raw_failure_survives_secondary_persistence_error(where):
    class Primary(RuntimeError):
        def __setattr__(self, name, value):
            if name == "seed_init_core_partial" and where == "attachment":
                raise ValueError("attachment refused")
            return super().__setattr__(name, value)

    cause, error, secondary = (
        KeyError("cause"),
        Primary("primary"),
        RuntimeError("partial observer"),
    )
    error.__cause__ = cause
    ctx = context()
    ctx.primary = error

    def partial(c):
        if where == "partial":
            raise secondary
        return {"raw": c}

    failure = clone(stage._failure, _raw_partial=partial, _FAILED=())
    with pytest.raises(Primary) as caught:
        failure(ctx, error)
    assert caught.value is error and error.__cause__ is cause
    assert ctx.invalid is True and len(ctx.capture_errors) == 1
    assert failure.__globals__["_FAILED"] == (ctx,)


def test_core_inherited_observer_failure_keeps_primary_and_hooks(monkeypatch):
    case = observation_case(monkeypatch)
    cause, primary, secondary = (
        KeyError("cause"),
        FalseySource("source"),
        ValueError("prior return"),
    )
    primary.__cause__ = cause
    case.ctx.action = lambda: (_ for _ in ()).throw(primary)

    def prior(frame, event, arg):
        if frame.f_code is case.body.__code__ and event == "return":
            raise secondary

    with pytest.raises(FalseySource) as caught:
        case.run(profile=prior)
    assert caught.value is primary and primary.__cause__ is cause
    assert case.ctx.last_source_exception[1][1] is primary
    assert any(row[1] is secondary for row in case.ctx.capture_errors)
    assert case.ctx.hooks_safe and not stage._ISSUED


def test_core_hook_recovery_is_independent_and_detects_cross_hook_clear():
    ctx = context()
    before = [object(), object()]
    actual = before.copy()
    calls = []

    def profile(value):
        calls.append("profile")
        actual[0] = value

    def trace(value):
        calls.append("trace")
        actual[1] = value
        actual[0] = None

    ctx.required_hooks = tuple(before)
    ctx.restore_setters = (profile, trace)
    ctx.restore_getters = (lambda: actual[0], lambda: actual[1])
    # Both passes end with profile restoration, so cross-clearing trace is
    # recovered; reverse cross-clearing below remains a detected failure.
    assert stage._restore(ctx) is True
    assert calls == ["trace", "profile", "trace", "profile"]

    def bad_profile(value):
        actual[0], actual[1] = value, None

    ctx.restore_setters = (bad_profile, trace)
    assert stage._restore(ctx) is False
    assert ctx.observation_error is not None


def test_core_bounded_work_retains_last_raw_before_refusal():
    ctx = context()
    raw = np.asarray([1.0])
    record = clone(stage._record, MAX_WORK=0)
    with active(ctx), pytest.raises(stage.InitCoreRejected):
        record(ctx, "full", raw)
    assert ctx.last_observation[1] is raw and ctx.events == []


def test_core_runner_scope_uses_literal_blockade_and_cpu4():
    tree = ast.parse((software.ROOT / software.FILE).read_bytes())
    text = ast.unparse(tree)
    assert '"cells.processes.betse_native_seed_init_core_source"' in repr(
        software.FORBIDDEN_MODULES
    ) or ("cells.processes.betse_native_seed_init_core_source" in software.FORBIDDEN_MODULES)
    assert "cpu=4" in text
    assert "os.sched_getaffinity(0) != {4}" in text
    assert software.OWNED == (software.SOURCE, software.LITERAL, software.TEST, software.FILE)
    assert "timeout=480" in text and "max_rss_bytes=2 ** 30" in text


def test_core_reached_helper_global_export_and_code_mutation_are_bound():
    from types import ModuleType

    module = ModuleType("synthetic_core_metadata")

    def actual():
        return 1

    def replacement():
        return 2

    module.helper = actual

    def reference():
        return module.helper()

    # Resolve a named global exactly as a real helper; neither body is called.
    namespace = dict(reference.__globals__, support=module)
    node = ast.parse("def reference():\n    return support.helper()\n")
    code = next(
        c for c in compile(node, "<synthetic-metadata>", "exec").co_consts if type(c) is CodeType
    )
    fn = FunctionType(code, namespace)
    before = stage._resolved_bindings((fn,))
    module.helper = replacement
    with pytest.raises(ValueError):
        stage.previous._same(stage._resolved_bindings((fn,)), before)
    module.helper = actual
    old = actual.__code__
    try:
        actual.__code__ = replacement.__code__
        with pytest.raises(ValueError):
            stage.previous._same(stage._resolved_bindings((fn,)), before)
    finally:
        actual.__code__ = old
    stage.previous._same(stage._resolved_bindings((fn,)), before)


def test_core_descriptor_binding_never_executes_a_getter():
    entries = []

    class Parent:
        @property
        def is_ecm(self):
            entries.append("getter")
            raise AssertionError("No property source execution")

    class Child(Parent):
        pass

    functions = stage._descriptor_helpers(((Child, ("is_ecm",)),))
    assert functions == (vars(Parent)["is_ecm"].fget,)
    assert entries == []


def test_core_final_snapshot_binds_raw_history_beyond_final_simulator(tmp_path):
    earlier = np.asarray([1.0, -0.0])
    ctx = NS(
        sim=NS(final=np.asarray([2.0])),
        cells=NS(),
        p=NS(),
        grid=NS(),
        request=NS(flux_operator="disabled"),
        events=[("earlier.return", earlier)],
    )
    snapshot = clone(stage._snapshot, _cache=lambda c, value: stage._CORE.caches.snapshot(value))
    before = snapshot(ctx)
    earlier[0] = 3.0
    after = snapshot(ctx)
    assert before.identity != after.identity
    assert ctx.sim.final.tolist() == [2.0]
    save(tmp_path, "history-retained", earlier)
    software.snapshot.write_json(
        tmp_path / "history-before.json",
        dict(descriptor=before.descriptor, identity=before.identity, synthetic_only=True),
    )
    np.savez(tmp_path / "history-before.npz", **before.numeric_columns())


class FalseySource(RuntimeError):
    def __bool__(self):
        return False


class BadAppend(list):
    def __init__(self, error):
        self.error = error

    def append(self, value):
        raise self.error


class BadLocals(dict):
    def __setitem__(self, key, value):
        if key == "init_core":
            raise ValueError("locals copy target refused")
        return super().__setitem__(key, value)


def observation_case(monkeypatch):
    """Real CPython hooks/real _observe over private metadata functions only.

    These objects are never registered as a phase, Simulator, callback owner,
    world or executable Request. No source pin/gate or registry is bypassed.
    Only the heavyweight ancestry/value checker is replaced by a small exact
    identity/value check so observation can be tested without source entry.
    """
    ctx = context()
    delivered = []
    ctx.assembly = NS()
    ctx.p, ctx.cells, ctx.grid, ctx.mesh, ctx.mask = NS(marker=7), NS(), NS(), object(), object()
    ctx.callback_frames, ctx.callback_returned, ctx.callback_status = [], [], None
    ctx.callback_frame, ctx.callback_exception, ctx.callback_return = None, None, None
    ctx.callback_completed, ctx.caller_frame = False, None
    ctx.original_wrappers, ctx.native_delegates, ctx.wrapper_claims = {}, {}, {}
    ctx.dispatch_frames, ctx.entered, ctx.method_returns = {}, [], []
    ctx.allowed_codes, ctx.ecm = frozenset(), False
    ctx.action = lambda: delivered.append("core")
    ctx.last_method_return = None

    def callback_body(self, status=None):
        delivered.append((self, status))

    def callback_wrapper(*args, **kwargs):
        return callback_body(*args, **kwargs)

    class Callback:
        progressed_next = callback_wrapper

    callback = Callback()
    ctx.callback = callback

    def body(self, phase):
        ctx.action()
        return None

    def make_wrapper():
        context, name, method, delegate = ctx.assembly, "Simulator", "init_core", body

        def invoke(actual, *args, **kwargs):
            # Keep exactly the original captured names alive in this metadata
            # wrapper. Real admission authenticates every one of these locals.
            assert name == "Simulator" and method == "init_core"
            stage._wrapper_guard(ctx, context, sys._getframe())
            ctx.entered.append(method)
            ctx.dispatch_frames[method] = sys._getframe()
            try:
                value = delegate(actual, *args, **kwargs)
                ctx.last_method_return = (method, value)
                ctx.method_returns.append((method, value))
                stage._guard(ctx)
                return value
            finally:
                ctx.dispatch_frames.pop(method, None)

        return invoke

    wrapper = make_wrapper()

    class Sim:
        init_core = wrapper

    ctx.sim = Sim()
    ctx.phase = NS(sim=ctx.sim, p=ctx.p, cells=ctx.cells, callbacks=callback)
    ctx.callback_target, ctx.status_target = callback, stage.CALLBACK_STATUS

    def caller(self, phase):
        ctx.callback_target.progressed_next(status=ctx.status_target)
        phase.sim.init_core(phase)

    ctx.caller = NS(_callbacks=callback)
    ctx.methods = {"continue_seed": caller, "init_core": body, "initDenv": body}
    ctx.original_wrappers["init_core"] = wrapper
    ctx.native_delegates["init_core"] = body
    ctx.body_codes = {body.__code__: "init_core"}
    ctx.wrapper_codes = {wrapper.__code__}
    ctx.callback_chain = (callback_wrapper, callback_body)
    ctx.callback_codes = {fn.__code__ for fn in ctx.callback_chain}
    original_refs = (ctx.phase, ctx.sim, ctx.p, ctx.cells, ctx.callback)

    def check(value):
        stage._guard(value)
        assert (ctx.phase, ctx.sim, ctx.p, ctx.cells, ctx.callback) == original_refs
        if ctx.p.marker != 7 or ctx.phase.sim is not ctx.sim or ctx.phase.callbacks is not callback:
            raise ValueError("synthetic actual lineage/value mutation")

    monkeypatch.setattr(stage, "_check", check)

    def run(*, profile=None, trace=None):
        before = (sys.getprofile(), sys.gettrace())

        def prior_profile(frame, event, arg):
            if profile is not None:
                profile(frame, event, arg)
            if before[0] is not None:
                before[0](frame, event, arg)

        def prior_trace(frame, event, arg):
            if trace is not None:
                trace(frame, event, arg)
            if before[1] is not None:
                before[1](frame, event, arg)
            return prior_trace

        ctx.required_hooks = (prior_profile, prior_trace)
        ctx.driver_frame = sys._getframe()
        try:
            sys.setprofile(prior_profile)
            sys.settrace(prior_trace)
            with active(ctx):
                with stage._account(ctx):
                    caller(ctx.caller, ctx.phase)
                stage._guard(ctx)
        finally:
            # Test fixture cleanup is independent of the subject's cleanup.
            try:
                sys.setprofile(before[0])
            finally:
                sys.settrace(before[1])

    return NS(
        ctx=ctx,
        run=run,
        delivered=delivered,
        body=body,
        wrapper=wrapper,
        caller=caller,
        callback_body=callback_body,
        callback_wrapper=callback_wrapper,
        Callback=Callback,
    )


def test_core_repair_real_trace_profile_legal_chain_before_inherited_callbacks(
    monkeypatch, tmp_path
):
    case = observation_case(monkeypatch)
    entered = []
    selected = {
        case.caller.__code__,
        case.body.__code__,
        case.wrapper.__code__,
        case.callback_wrapper.__code__,
        case.callback_body.__code__,
    }

    def prior(frame, event, arg):
        if event == "call" and frame.f_code in selected:
            row = case.ctx.admitted[id(frame)]
            assert row["frame"] is frame
            entered.append((row["role"], row["name"]))

    case.run(profile=prior, trace=prior)
    assert case.delivered == [(case.ctx.callback, stage.CALLBACK_STATUS), "core"]
    assert case.ctx.callback_returned == [1, 0]
    assert len(entered) == 10 and len(case.ctx.admitted) == 5
    assert all(
        row["call_layers"] == {"trace", "profile"} and row["return_layers"] == {"trace", "profile"}
        for row in case.ctx.admitted.values()
    )
    assert case.ctx.hooks_safe and not stage._ISSUED
    stage._complete(case.ctx)
    software.snapshot.write_json(
        tmp_path / "actual-observer-path.json",
        dict(
            actual_cpython_hooks=True,
            real_observe_used=True,
            source_bodies=False,
            entered=entered,
            callback_returned=case.ctx.callback_returned,
            complete=case.ctx.callback_completed,
        ),
    )


@pytest.mark.parametrize("wrong", ["receiver", "status"])
def test_core_repair_same_code_foreign_callback_refuses_before_body_or_prior(monkeypatch, wrong):
    case = observation_case(monkeypatch)
    called = []
    if wrong == "receiver":
        case.ctx.callback_target = case.Callback()
    else:
        case.ctx.status_target = "foreign status"

    def prior(frame, event, arg):
        if frame.f_code is case.callback_wrapper.__code__ and event == "call":
            called.append(frame)

    with pytest.raises(stage.InitCoreRejected):
        case.run(profile=prior, trace=prior)
    assert case.delivered == [] and called == [] and case.ctx.invalid


@pytest.mark.parametrize("layer", ["profile", "trace"])
def test_core_repair_inherited_entry_rejection_is_immediate(monkeypatch, layer):
    case = observation_case(monkeypatch)
    error = ValueError("outer guard refuses entry")

    def prior(frame, event, arg):
        if frame.f_code is case.body.__code__ and event == "call":
            assert case.ctx.admitted[id(frame)]["role"] == "body"
            raise error

    with pytest.raises(ValueError) as caught:
        case.run(**{layer: prior})
    assert caught.value is error
    assert "core" not in case.delivered
    assert case.ctx.observation_error is error and case.ctx.hooks_safe


@pytest.mark.parametrize(
    "kind", ["caught_reentry", "callback_reentry", "mutation", "same_frame_argument"]
)
def test_core_repair_prior_caught_reentry_or_mutation_cannot_continue(monkeypatch, kind):
    case = observation_case(monkeypatch)
    attempted = []

    def prior(frame, event, arg):
        if frame.f_code is case.body.__code__ and event == "call":
            if kind == "caught_reentry":
                try:
                    stage._wrapper_guard(case.ctx, case.ctx.assembly, frame)
                except stage.InitCoreRejected as error:
                    attempted.append(error)
            elif kind == "callback_reentry":
                try:
                    case.ctx.callback.progressed_next(status=stage.CALLBACK_STATUS)
                except stage.InitCoreRejected as error:
                    attempted.append(error)
            elif kind == "mutation":
                case.ctx.p.marker = 8
            else:
                frame.f_locals["self"] = object()

    with pytest.raises((stage.InitCoreRejected, ValueError)):
        case.run(profile=prior)
    assert "core" not in case.delivered and not stage._ISSUED
    assert case.ctx.hooks_safe
    if kind in ("caught_reentry", "callback_reentry"):
        assert len(attempted) == 1 and attempted[0] is case.ctx.entry_error
        assert case.delivered == [(case.ctx.callback, stage.CALLBACK_STATUS)]


@pytest.mark.parametrize("where", ["prior_exception", "locals", "exception_append"])
def test_core_repair_falsey_source_retained_before_exception_observers(monkeypatch, where):
    case = observation_case(monkeypatch)
    cause, primary, secondary = (
        KeyError("cause"),
        FalseySource("actual stand-in"),
        ValueError("capture"),
    )
    primary.__cause__ = cause

    def action():
        raise primary

    case.ctx.action = action
    if where == "locals":
        case.ctx.locals = BadLocals()
    elif where == "exception_append":
        case.ctx.source_exceptions = BadAppend(secondary)

    def prior(frame, event, arg):
        if (
            where == "prior_exception"
            and frame.f_code is case.body.__code__
            and event == "exception"
        ):
            assert case.ctx.primary is primary and case.ctx.last_source_exception[1][1] is primary
            raise secondary

    with pytest.raises(FalseySource) as caught:
        case.run(trace=prior)
    assert caught.value is primary and primary.__cause__ is cause and case.ctx.primary is primary
    assert case.ctx.last_source_exception[1][1] is primary
    assert case.ctx.capture_errors and case.ctx.hooks_safe and not stage._ISSUED


@pytest.mark.parametrize("where", ["prior_return", "return_append"])
def test_core_repair_successful_raw_helper_return_survives_observer(monkeypatch, tmp_path, where):
    case = observation_case(monkeypatch)
    raw, error = np.asarray([1.0, -0.0, 2.0]), ValueError("return observer")

    def delegate(n):
        return raw

    case.ctx.helpers = {"zeros": delegate}
    record = clone(stage._record, _cache=lambda c, value: stage._CORE.caches.snapshot(value))
    monkeypatch.setattr(stage, "_record", record)

    def observed():
        return stage._helper(case.ctx, "zeros", delegate, (3,), {}, sys._getframe())

    # The actual helper boundary must be a direct call from the selected body.
    def body(self, phase):
        observed()
        case.delivered.append("after helper")

    case.ctx.methods["init_core"] = body
    case.ctx.body_codes = {body.__code__: "init_core"}
    # Existing wrapper closes over its original body. Bind a new private
    # metadata wrapper with the exact original closure names for this control.
    context, name, method = case.ctx.assembly, "Simulator", "init_core"

    # _admit_wrapper reads the 'delegate' local: bind the body as in the real wrapper.
    delegate_body = body

    def factory(delegate):
        def invoke(actual, *args, **kwargs):
            assert name == "Simulator" and method == "init_core"
            stage._wrapper_guard(case.ctx, context, sys._getframe())
            case.ctx.entered.append(method)
            case.ctx.dispatch_frames[method] = sys._getframe()
            try:
                return delegate(actual, *args, **kwargs)
            finally:
                case.ctx.dispatch_frames.pop(method, None)

        return invoke

    wrapper = factory(delegate_body)
    type(case.ctx.sim).init_core = wrapper
    case.ctx.original_wrappers["init_core"] = wrapper
    case.ctx.native_delegates["init_core"] = body
    case.ctx.wrapper_codes = {wrapper.__code__}
    if where == "return_append":
        case.ctx.helper_returns = BadAppend(error)

    def prior(frame, event, arg):
        if where == "prior_return" and frame.f_code is delegate.__code__ and event == "return":
            assert case.ctx.last_helper_return[1] is raw
            raise error

    with pytest.raises(stage._LITERAL._CaptureStop):
        case.run(profile=prior)
    assert case.ctx.last_helper_return[1] is raw
    assert case.ctx.last_helper[3] is raw
    assert case.ctx.primary is None and case.ctx.observation_error is error
    assert "after helper" not in case.delivered and not case.ctx.helper_busy
    assert case.ctx.hooks_safe and not stage._ISSUED
    save(tmp_path, "successful-raw-before-observer-failure", raw)


def test_core_repair_helper_input_append_resets_busy_and_never_calls_delegate():
    called, error = [], ValueError("input history")
    ctx, body = helper_case(lambda n: called.append(n))
    ctx.helper_inputs = BadAppend(error)
    with active(ctx), pytest.raises(stage._LITERAL._CaptureStop):
        body()
    assert not ctx.helper_busy and ctx.active_helper is None
    assert called == [] and ctx.last_helper[:3] == ("zeros", (2,), {})
    assert ctx.observation_error is error


def test_core_repair_restore_entry_rejection_preserves_source_and_recovers_both(monkeypatch):
    case = observation_case(monkeypatch)
    primary, cause, secondary = (
        FalseySource("source"),
        KeyError("cause"),
        ValueError("restore call"),
    )
    primary.__cause__ = cause

    def action():
        raise primary

    case.ctx.action = action
    rejected = []

    def prior(frame, event, arg):
        if frame.f_code is stage._restore.__code__ and event == "call":
            rejected.append(event)
            raise secondary

    with pytest.raises(FalseySource) as caught:
        case.run(profile=prior)
    assert caught.value is primary and primary.__cause__ is cause
    assert rejected and any(row[1] is secondary for row in case.ctx.cleanup_errors)
    assert case.ctx.hooks_safe


@pytest.mark.parametrize("kind", ["unrecoverable", "partial_clears_hook"])
def test_core_repair_failure_never_runs_unsafe_metadata_callbacks(monkeypatch, kind):
    ctx = context()
    primary = FalseySource("source")
    ctx.primary = primary
    expected = (object(), object())
    actual = list(expected)
    calls = []
    ctx.required_hooks = expected
    ctx.restore_getters = (lambda: actual[0], lambda: actual[1])

    def profile(value):
        calls.append("profile")
        actual[0] = value
        if kind == "unrecoverable":
            actual[1] = None

    def trace(value):
        calls.append("trace")
        actual[1] = value

    ctx.restore_setters = (profile, trace)
    if kind == "unrecoverable":
        actual[1] = None

    def partial(value):
        calls.append("partial")
        actual[0] = None
        raise ValueError("partial clears prior profile")

    failure = clone(stage._failure, _raw_partial=partial, _FAILED=())
    with pytest.raises(FalseySource) as caught:
        failure(ctx, primary)
    assert caught.value is primary and ctx.metadata_stopped
    assert failure.__globals__["_LAST_FAILED"] is ctx
    assert not hasattr(primary, "seed_init_core_partial")
    if kind == "unrecoverable":
        assert "partial" not in calls and not ctx.hooks_safe
    else:
        assert calls.count("partial") == 1 and ctx.hooks_safe


def test_core_repair_expected_parent_is_exact_trial_not_an_epoch_tuple():
    plan = stage.source_plan()
    assert "exact retained previous.Trial" in plan["parent_hooks"][stage.PROPOSED_CLAIM]
    source = ast.unparse(definitions()["prepare"])
    assert "expected=refs[1]" in source
