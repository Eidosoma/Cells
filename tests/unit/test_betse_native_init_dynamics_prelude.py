"""Source/conditional metadata controls; no original dynamics or helper work."""

import ast
import builtins
import importlib.abc
import os
import struct
import sys
from dataclasses import replace
from enum import Enum
from pathlib import Path
from types import CodeType, FunctionType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_init_dynamics_prelude as stage
from cells.processes import betse_native_single_cell_poisson_observation as observation
from tests.unit import test_betse_native_parameter_seed_init_transition as cleanup
from validation.betse import betse_native_init_dynamics_prelude_software as runner


def _diagnostics(directory, contexts):
    def error(value):
        return (
            None
            if value is None
            else dict(
                type=type(value).__name__,
                message=str(value),
                cause=None if value.__cause__ is None else type(value.__cause__).__name__,
            )
        )

    for index, context in enumerate(contexts):
        runner.snapshot.write_json(
            directory / ("prelude-failure-" + str(index) + ".json"),
            dict(
                stage=context.stage,
                primary=error(context.primary),
                capture_error=error(context.capture_error),
                capture_errors=[
                    dict(origin=row[0], error=error(row[1])) for row in context.capture_errors
                ],
                cleanup_errors=[
                    dict(origin=row[0], error=error(row[1])) for row in context.cleanup_errors
                ],
                raw_return_available=context.last_raw is not None,
                last_raw_frame=None if context.last_raw is None else id(context.last_raw[0]),
                work_entries=len(context.work),
                c_entries=len(context.c_calls),
                trial_available=context.trial is not None,
                actual_native_or_completed_INIT_credit=False,
            ),
        )


def _blocked_generator(request, tmp_path, monkeypatch):
    if os.environ.get(runner.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit frozen CPU5 software release required")
    before, attempts = (sys.getprofile(), sys.gettrace()), []
    active, failed = tuple(stage._ACTIVE), len(stage._FAILED)

    def forbidden(*args, **kwargs):
        attempts.append("native_solver_or_RNG")
        raise AssertionError("Native/model/RNG entry forbidden")

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "betse" or fullname.startswith("betse."):
                attempts.append(fullname)
                raise AssertionError("Native import forbidden")

    def trace(frame, event, arg):
        if event == "call" and runner.is_forbidden_frame(frame):
            attempts.append((frame.f_code.co_filename, frame.f_code.co_name))
            raise AssertionError("Native/source/parser/time-law entry forbidden")
        # The blockade is a CALL guard. Returning None avoids subscribing an
        # observer to every line of metadata-copy/checker machinery. An already
        # installed caller tracer retains its own exact local callback.
        return None if before[1] is None else before[1](frame, event, arg)

    finder = Block()
    inserted = False
    try:
        sys.meta_path.insert(0, finder)
        inserted = True
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
        yield
    finally:
        intact = sys.getprofile() is before[0] and sys.gettrace() is trace
        active_ok = tuple(stage._ACTIVE) == active
        stage._ACTIVE[:] = active
        del stage._FAILED[failed:]
        try:
            sys.settrace(before[1])
        finally:
            sys.setprofile(before[0])
        if inserted:
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
                actual_native_source_parser_RNG_or_factory_entries=0,
                conditional_metadata_is_not_genuine_INIT_authority=True,
            ),
        )
        assert intact and active_ok and not attempts


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    generator = _blocked_generator(request, tmp_path, monkeypatch)
    hooks, started, primary = (sys.getprofile(), sys.gettrace()), False, None
    failed = len(stage._FAILED)
    try:
        next(generator)
        started = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        drain = FunctionType(
            cleanup._drain_guard.__code__,
            dict(cleanup._drain_guard.__globals__, _write_failure_diagnostics=_diagnostics),
        )
        drain(
            generator,
            started,
            tuple(stage._FAILED[failed:]),
            tmp_path,
            required_hooks=hooks,
            primary=primary,
        )


def test_exact_source_extent_complete_helpers_headers_and_declared_stop(tmp_path):
    plan = stage.source_plan()
    assert plan["prefix"] == (758, 806)
    assert plan["helpers"]["initDenv"] == (2347, 2400)
    assert plan["helpers"]["get_ion"] == (2313, 2344)
    assert plan["actual_execution_held"] and plan["normal_ECM_only"]
    assert plan["parent_source"] is None and plan["parent_review"] is None
    nodes, codes = stage._nodes(), stage._codes()
    assert tuple(nodes) == tuple(codes)
    assert all(type(code) is CodeType for code in codes.values())
    text = ast.unparse(nodes["init_dynamics"])
    assert (
        text.index("smooth_weight_mem") < text.index("smooth_weight_o") < text.index("Gap_Junction")
    )
    assert (
        text.index("self.initDenv")
        < text.index("p.ions_dict.items()")
        < text.index("self.c_env_bound")
    )
    assert "init_profiles" not in text and "random" not in text
    assert "gaussian_filter" in ast.unparse(nodes["initDenv"])
    assert "np.exp" in ast.unparse(nodes["Gap_Junction.init"])
    runner.snapshot.write_json(
        tmp_path / "source-only.json",
        dict(plan=plan, original_AST_compiled_not_invoked=list(codes), actual_science_entries=0),
    )


@pytest.mark.parametrize("change", ["default", "keyword_only", "decorator", "body"])
def test_complete_declaration_and_literal_body_drift_refuse_without_execution(
    tmp_path, monkeypatch, change
):
    tree = ast.parse(Path(stage.source.__file__).read_bytes())
    method = stage._method(tree, "InitDynamicsPrelude", "initDenv")
    if change == "default":
        method.args.defaults.append(ast.Constant(None))
    elif change == "keyword_only":
        method.args.kwonlyargs.append(ast.arg(arg="foreign"))
        method.args.kw_defaults.append(ast.Constant(None))
    elif change == "decorator":
        method.decorator_list.append(ast.Name(id="foreign"))
    else:
        method.body[-1] = ast.Pass()
    path = tmp_path / "declaration.py"
    path.write_text(ast.unparse(ast.fix_missing_locations(tree)))
    monkeypatch.setattr(stage.source, "__file__", str(path))
    with pytest.raises(ValueError, match="(declaration|body/order)"):
        stage._nodes()


@pytest.mark.parametrize(
    "values",
    [
        (3, 3 + 0j),
        (1, True),
        (0.0, -0.0),
        ((1, (3.0,)), (1, (3 + 0j,))),
        (
            struct.unpack(">d", bytes.fromhex("7ff8000000000001"))[0],
            struct.unpack(">d", bytes.fromhex("fff8000000000002"))[0],
        ),
    ],
)
def test_typed_executable_constants_keep_category_float_bits_and_nesting(values):
    left, right = values
    assert stage._constant(left) != stage._constant(right)


@pytest.mark.parametrize("present", [False, True])
def test_native_logs_warning_is_only_captured_if_the_actual_export_exists(present):
    def forbidden(*args, **kwargs):
        pytest.fail("No logging, Gaussian, NumPy or native body execution")

    logs = ModuleType("conditional_logs")
    logs.log_info = forbidden
    logs.log_warning = object()
    if present:
        logs.warning = forbidden
    numpy = NS(**dict.fromkeys(("ones", "copy", "hstack", "abs", "exp"), forbidden))
    helpers = stage._source_helpers(dict(logs=logs, gaussian_filter=forbidden), numpy)
    assert ("log_warning" in helpers) is present
    if present:
        assert helpers["log_warning"] is logs.warning
    else:
        assert not hasattr(logs, "warning")
    original = ast.unparse(stage._nodes()["get_ion"])
    assert "logs.warning(" in original and "logs.log_warning(" not in original


@pytest.mark.parametrize(
    "relative,cls,name",
    [
        (stage.SIM_FILE, "Simulator", "init_dynamics"),
        (stage.SIM_FILE, "Simulator", "initDenv"),
        (stage.SIM_FILE, "Simulator", "get_ion"),
        (stage.GAP_FILE, "Gap_Junction", "__init__"),
        (stage.GAP_FILE, "Gap_Junction", "init"),
    ],
)
def test_genuine_executable_comparison_uses_original_whole_module_class_context(
    relative, cls, name
):
    path = stage.NATIVE / relative
    full = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    expected_class = next(
        item for item in full.co_consts if type(item) is CodeType and item.co_name == cls
    )
    expected = next(
        item for item in expected_class.co_consts if type(item) is CodeType and item.co_name == name
    )
    actual = stage._native_code(relative, cls, name)
    assert stage._constant(actual) == stage._constant(expected)
    assert actual.co_qualname == cls + "." + name
    # No FunctionType or original module body has been invoked. This compares
    # the actual native executable context, independently of prefix projection.


def test_actual_parent_producer_and_hooks_remain_explicitly_unbound(monkeypatch):
    monkeypatch.setattr(
        stage.previous, "_authority", lambda value: pytest.fail("No supplied owner inspection")
    )
    with pytest.raises(stage.DynamicsRejected) as caught:
        stage.from_init(object(), law_id=stage.LAW_ID)
    assert caught.value.stage == "unbound"
    with pytest.raises(stage.DynamicsRejected) as caught:
        stage.from_init(object(), law_id="foreign")
    assert caught.value.stage == "law"


@pytest.mark.parametrize("value", [None, {}, NS(), object.__new__(stage.PreludeOwner)])
def test_records_or_unissued_owners_grant_no_live_authority(value):
    with pytest.raises(stage.DynamicsRejected):
        stage._authority(value)
    with pytest.raises(stage.DynamicsRejected):
        stage.failed_context(value)


@pytest.fixture
def conditional(monkeypatch):
    """Explicit small metadata model; never an actual native/INIT prerequisite."""
    h = NS(source_error=None, cause=None, stream="conditional-MT-no-RNG-work")
    h.p = NS(
        _run_sim=False,
        is_ecm=True,
        v_sensitive_gj=False,
        ions_dict={"Na": 1, "K": 1, "Ca": 0},
        cbnd=None,
        _conf={"same": [1, 2]},
    )
    h.cells, h.callback = NS(retained=np.array([7, 9])), NS(label="original-conditional-callback")
    h.weights = np.array([0.25, 0.5])
    h.environment = np.array([[3.0, 4.0], [5.0, 6.0]])
    h.indices = {"Na": 0, "K": 1}

    class Gap:
        pass

    def initDenv(self, cells, p):
        assert cells is h.cells and p is h.p
        self.D_env_weight = h.environment

    def get_ion(self, ion_name):
        return h.indices[ion_name]

    def init_dynamics(self, phase):
        if h.source_error is not None:
            raise h.source_error from h.cause
        self.smooth_weight_mem = h.weights
        self.smooth_weight_o = h.weights
        self.initDenv(phase.cells, phase.p)
        for key, val in phase.p.ions_dict.items():
            if val == 1:
                ion_i = self.get_ion(key)
                if phase.p.cbnd is not None:
                    self.c_env_bound[ion_i] = phase.p.cbnd[key]

    def invoke(parent, label, delegate, actual, *args, **kwargs):
        return stage._dispatch(
            parent.transition, parent, label, delegate, actual, args, kwargs, sys._getframe()
        )

    namespace = {"__name__": __name__, "__builtins__": vars(builtins), "Gap_Junction": Gap}
    functions = {
        function.__name__: FunctionType(
            function.__code__,
            namespace,
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
        for function in (init_dynamics, initDenv, get_ion)
    }

    def guarded(method, delegate):
        context, name = h.parent, "Simulator"

        def invoke_wrapper(actual, *args, **kwargs):
            stage._wrapper_guard(context.transition, context, sys._getframe())
            return invoke(context, name + "." + method, delegate, actual, *args, **kwargs)

        return invoke_wrapper

    class Simulator:
        pass

    h.sim = Simulator()
    h.sim.D_env = np.array([[2.0, 4.0], [6.0, 8.0]])
    h.sim.c_env_bound = np.array([10.0, 20.0])
    h.sim.unowned_gate = np.array([0.125, 0.75])
    h.sim.gj_funk = None

    class Kind(Enum):
        INIT = 1

    h.phase = NS(
        p=h.p,
        cells=h.cells,
        sim=h.sim,
        callbacks=h.callback,
        dyna=NS(profile="retained"),
        kind=Kind.INIT,
    )
    h.owner = object.__new__(stage.previous.InitOwner)
    h.parent = NS(
        phase=h.phase,
        p=h.p,
        cells=h.cells,
        callback=h.callback,
        trial=NS(identity="conditional-completed-core-no-native-authority"),
        parameter_record=object(),
        parent=NS(world=object()),
        objects=[
            ("phase", h.phase),
            ("sim", h.sim),
            ("handler", h.phase.dyna),
            ("callback", h.callback),
        ],
        graph_tape=NS(rng=object(), events=(), draws=(), locals={}),
    )
    for name in stage.METHODS[1:]:
        setattr(Simulator, name, guarded(name, functions[name]))
    # This metadata model has only 2x2 arrays. Use the existing ordinary closed
    # snapshot/graph functions; the genuine path retains the parent's explicit
    # larger Poisson-array scope. No capacity or source admission is borrowed.
    scope = NS(snapshot=observation.caches.snapshot, graph=observation.callers._graph)
    projector = NS(objects=[*h.parent.objects, ("parameters", h.p), ("cells", h.cells)])
    monkeypatch.setattr(stage, "_ready", lambda: None)
    monkeypatch.setattr(
        stage,
        "source_plan",
        lambda: dict(law=stage.LAW_ID, conditional_metadata_not_native_or_InitOwner_authority=True),
    )
    monkeypatch.setattr(stage, "_scope", lambda context: scope)
    monkeypatch.setattr(stage.previous, "_projector", lambda parent: projector)
    monkeypatch.setattr(
        stage.previous,
        "_authority",
        lambda value: h.parent if value is h.owner else pytest.fail("Foreign model owner"),
    )
    monkeypatch.setattr(stage.previous, "_snapshot", lambda parent: scope.snapshot(vars(h.p)))
    monkeypatch.setattr(
        stage.previous, "_graph", lambda parent: scope.graph(h.phase, h.p, h.parent.graph_tape)
    )
    monkeypatch.setattr(stage.previous, "_rng", lambda parent: NS(identity=h.stream))
    monkeypatch.setattr(stage.previous, "_invoke", invoke)

    def claim(owner, *, expected, transition, entries):
        assert owner is h.owner and expected is h.parent.trial
        assert entries["dispatch"] is stage._dispatch
        assert entries["wrapper_guard"] is stage._wrapper_guard
        h.parent.transition = transition

    def check(transition):
        assert transition is h.parent.transition
        return h.parent

    monkeypatch.setattr(stage.previous, stage.PARENT_CLAIM, claim, raising=False)
    monkeypatch.setattr(stage.previous, stage.PARENT_CHECK, check, raising=False)

    def namespace_model(context):
        def no_factory(*args):
            pytest.fail("No actual or model factory work in this conditional route")

        context.original_globals = namespace
        context.private = dict(namespace, Gap_Junction=no_factory)
        context.gap_factory, context.gap_constructor, context.numpy = Gap, no_factory, np
        context.methods = dict(
            functions,
            init_dynamics=FunctionType(
                functions["init_dynamics"].__code__,
                context.private,
                "init_dynamics",
                closure=functions["init_dynamics"].__closure__,
            ),
        )
        context.native_functions, context.helper_functions = tuple(functions.values()), ()
        context.native_delegates = {name: functions[name] for name in stage.METHODS[1:]}
        context.sim_wrappers = {name: vars(Simulator)[name] for name in stage.METHODS[1:]}
        context.helpers = {}
        context.gap_bodies = {}
        context.allowed_codes = frozenset(fn.__code__ for fn in context.methods.values())
        context.expected_body = context.methods["init_dynamics"].__code__
        context.body_functions = {fn.__code__: fn for fn in context.methods.values()}

    monkeypatch.setattr(stage, "_namespace", namespace_model)
    monkeypatch.setenv(stage.RELEASE, "1")
    h.request = stage.from_init(h.owner, law_id=stage.LAW_ID)
    h.prefix_code = functions["init_dynamics"].__code__
    return h


def test_conditional_same_owner_graph_helper_and_ion_order_without_native_work(conditional):
    h = conditional
    result = stage.prepare(h.request, enabled=True)
    context = stage._authority(result)
    assert result.phase is h.phase and result.trial is context.trial
    assert context.parent is h.parent and context.p is h.p and context.cells is h.cells
    assert context.original_D_env is h.sim.D_env
    assert context.ion_order == ("Na", "K")
    assert [row[0] for row in context.helper_returns] == ["initDenv", "get_ion", "get_ion"]
    assert context.before is not context.after and context.after_graph
    assert context.trial.source_completed and context.body_return is None
    assert len(context.trial.c_calls) == len(context.c_calls)
    assert all(a is b for a, b in zip(context.trial.c_calls, context.c_calls, strict=True))
    assert not stage.trial_record(context.trial)["completed_INIT_or_independent_case"]


@pytest.mark.parametrize("mode", ["default", "integer", "gate"])
def test_both_release_gates_precede_retirement(conditional, monkeypatch, mode):
    h = conditional
    if mode == "gate":
        monkeypatch.setenv(stage.RELEASE, "0")
    with pytest.raises(stage.DynamicsRejected) as caught:
        stage.prepare(h.request, enabled=1 if mode == "integer" else mode != "default")
    assert caught.value.stage == "release" and h.request not in stage._CONSUMED


def test_once_only_request_and_owner_epoch_never_rebase_or_retry(conditional):
    h = conditional
    stage.prepare(h.request, enabled=True)
    context = stage._CONSUMED[h.request]
    count = len(context.work)
    with pytest.raises(stage.DynamicsRejected, match="already attempted"):
        stage.prepare(h.request, enabled=True)
    with pytest.raises(stage.DynamicsRejected, match="unconsumed"):
        stage.from_init(h.owner, law_id=stage.LAW_ID)
    assert stage._RETIRED[h.owner] is context and len(context.work) == count


def test_two_issued_requests_share_one_irreversible_actual_owner_epoch(conditional):
    h = conditional
    second = stage.from_init(h.owner, law_id=stage.LAW_ID)
    stage.prepare(h.request, enabled=True)
    with pytest.raises(stage.DynamicsRejected, match="already attempted"):
        stage.prepare(second, enabled=True)
    assert second not in stage._CONSUMED


def test_native_shape_wrapper_functions_share_code_but_retain_distinct_closures(conditional):
    h = conditional
    methods = vars(type(h.sim))
    assert methods["initDenv"].__code__ is methods["get_ion"].__code__
    assert methods["initDenv"] is not methods["get_ion"]
    owner = stage.prepare(h.request, enabled=True)
    context = stage._authority(owner)
    assert [row["name"] for row in context.helper_invocations] == ["initDenv", "get_ion", "get_ion"]


def test_issued_plan_drift_refuses_before_irreversible_claim(conditional, monkeypatch):
    h = conditional
    monkeypatch.setattr(stage, "source_plan", lambda: dict(foreign=True))
    with pytest.raises(stage.DynamicsRejected, match="parent changed"):
        stage.prepare(h.request, enabled=True)
    assert h.request not in stage._CONSUMED and not hasattr(h.parent, "transition")


def test_equal_parent_array_replacement_refuses_before_source(conditional):
    h = conditional
    h.p._conf["same"] = list(h.p._conf["same"])
    with pytest.raises(ValueError):
        stage.prepare(h.request, enabled=True)
    assert h.request not in stage._CONSUMED


class FalseyError(RuntimeError):
    def __bool__(self):
        return False


def _observer_focus(monkeypatch):
    """Keep these observer tests bounded with an explicit metadata-check seam.

    Full-chain/source-lookup/closed-owner tests use the actual complete _check.
    Here upstream authority/delegates are already conditional, and this seam
    selects the actual active guard. The production _account, _inherited,
    _epoch, _same_epoch and _guard still run, including real profiled frames.
    This grants no genuine owner and skips no native/runtime release gate.
    """
    monkeypatch.setattr(stage, "_check", lambda context, **kwargs: stage._guard(context))


@pytest.mark.parametrize("error_type", [RuntimeError, FalseyError])
def test_original_source_primary_cause_and_irreversible_failed_prefix_retained(
    conditional, error_type
):
    h = conditional
    h.source_error, h.cause = error_type("conditional-source-primary"), KeyError("original-cause")
    with pytest.raises(error_type) as caught:
        stage.prepare(h.request, enabled=True)
    context = stage.failed_context(h.request)
    assert caught.value is h.source_error and caught.value.__cause__ is h.cause
    assert context.primary is h.source_error and context.trial is None
    assert caught.value.init_dynamics_prelude_partial is context
    assert context.last_raw is not None and context.last_raw[1] is None
    assert not context.active and context.invalid and stage._RETIRED[h.owner] is context
    with pytest.raises(stage.DynamicsRejected, match="already attempted"):
        stage.prepare(h.request, enabled=True)


@pytest.mark.parametrize("source_failure", [False, True])
def test_actual_profile_return_or_unwind_failure_preserves_primary_and_hooks(
    conditional, monkeypatch, source_failure
):
    _observer_focus(monkeypatch)
    h = conditional
    capture = LookupError("inherited-return-observer")
    if source_failure:
        h.source_error, h.cause = RuntimeError("native-model-primary"), KeyError("cause")
    original = sys.getprofile()

    def profile(frame, event, arg):
        if frame.f_code is h.prefix_code and event == "return":
            raise capture

    sys.setprofile(profile)
    try:
        with pytest.raises((RuntimeError, LookupError)) as caught:
            stage.prepare(h.request, enabled=True)
        context = stage.failed_context(h.request)
        assert caught.value is (h.source_error if source_failure else capture)
        assert context.capture_error is capture and context.last_raw[1] is None
        if source_failure:
            assert caught.value.__cause__ is h.cause
        assert sys.getprofile() is profile and context.hooks_safe
    finally:
        sys.setprofile(original)


def test_reentrant_profile_refusal_is_sticky_even_if_observer_catches_it(conditional, monkeypatch):
    _observer_focus(monkeypatch)
    h = conditional
    original, nested = sys.getprofile(), []

    def profile(frame, event, arg):
        if frame.f_code is h.prefix_code and event == "call":
            try:
                stage.prepare(h.request, enabled=True)
            except stage.DynamicsRejected as error:
                nested.append(error)

    sys.setprofile(profile)
    try:
        with pytest.raises(stage.DynamicsRejected) as caught:
            stage.prepare(h.request, enabled=True)
        context = stage.failed_context(h.request)
        assert nested and context.entry_error is nested[0] and caught.value is nested[0]
        assert "smooth_weight_mem" not in vars(h.sim)
    finally:
        sys.setprofile(original)


def test_inherited_hook_loss_refuses_before_first_source_store(conditional, monkeypatch):
    _observer_focus(monkeypatch)
    h = conditional
    original = sys.getprofile()

    def profile(frame, event, arg):
        if frame.f_code is h.prefix_code and event == "call":
            sys.settrace(None)

    sys.setprofile(profile)
    try:
        with pytest.raises(stage.DynamicsRejected):
            stage.prepare(h.request, enabled=True)
        context = stage.failed_context(h.request)
        assert context.entry_error is not None
        assert "smooth_weight_mem" not in vars(h.sim)
        assert context.hooks_safe
    finally:
        sys.setprofile(original)


@pytest.mark.parametrize("field", ["method", "delegate", "context", "actual"])
def test_native_shape_wrapper_closure_and_receiver_drift_refuse_before_helper(
    conditional, monkeypatch, field
):
    _observer_focus(monkeypatch)
    h = conditional
    original = sys.getprofile()
    observed = []

    def profile(frame, event, arg):
        if frame.f_code is stage._wrapper_guard.__code__ and event == "call" and not observed:
            wrapper_frame = frame.f_locals["frame"]
            observed.append(wrapper_frame)
            wrapper_frame.f_locals[field] = "get_ion" if field == "method" else object()

    sys.setprofile(profile)
    try:
        with pytest.raises(ValueError):
            stage.prepare(h.request, enabled=True)
        context = stage.failed_context(h.request)
        assert observed and context.trial is None
        assert not context.helper_invocations
    finally:
        sys.setprofile(original)


@pytest.mark.parametrize("target", ["parameter", "material", "geometry"])
def test_inherited_observer_is_read_only_even_for_source_owned_arrays(
    conditional, monkeypatch, target
):
    _observer_focus(monkeypatch)
    h = conditional
    original = sys.getprofile()

    def profile(frame, event, arg):
        if frame.f_code is h.prefix_code and event == "call":
            if target == "parameter":
                h.p._run_sim = True
            elif target == "material":
                h.sim.D_env[0, 0] = 99
            else:
                h.cells.retained = h.cells.retained.copy()

    sys.setprofile(profile)
    try:
        with pytest.raises(ValueError) as caught:
            stage.prepare(h.request, enabled=True)
        context = stage.failed_context(h.request)
        if target == "geometry":
            # The common graph checker retains its original identity refusal;
            # source-specific value drift takes the sticky entry-guard path.
            assert "identity changed" in str(caught.value)
            assert context.capture_error is caught.value
        else:
            assert caught.value is context.entry_error
        assert context.trial is None
        assert "smooth_weight_mem" not in vars(h.sim)
    finally:
        sys.setprofile(original)


@pytest.mark.parametrize("kind", ["value", "alias", "unowned", "MT", "parent_record"])
def test_closed_owner_refuses_real_state_alias_or_authority_drift(conditional, kind):
    h = conditional
    owner = stage.prepare(h.request, enabled=True)
    context = stage._ISSUED[owner][0]
    if kind == "value":
        h.sim.D_env_weight[0, 0] = 99
    elif kind == "alias":
        h.sim.D_env_weight = h.sim.D_env_weight.copy()
    elif kind == "unowned":
        h.sim.unowned_gate = h.sim.unowned_gate.copy()
    elif kind == "MT":
        h.stream = "foreign-stream"
    else:
        h.parent.parameter_record = object()
    with pytest.raises(ValueError):
        stage._authority(owner)
    assert context.invalid


def test_missing_original_conditional_gap_application_cannot_publish(conditional):
    h = conditional
    h.p.v_sensitive_gj = True
    h.request = stage.from_init(h.owner, law_id=stage.LAW_ID)
    with pytest.raises(ValueError, match="conditional gap"):
        stage.prepare(h.request, enabled=True)
    assert stage.failed_context(h.request).trial is None


def test_recovery_attempts_both_hooks_and_independent_samples_after_one_getter_error():
    calls, original = [], (object(), object())
    context = NS(required_hooks=original, cleanup_errors=(), hooks_safe=True)
    context.setters = tuple(
        lambda value, index=index: calls.append(("set", index, value)) for index in range(2)
    )

    def get(index):
        calls.append(("get", index))
        if index == 0:
            raise OSError("profile-sample")
        return original[index]

    context.getters = tuple(lambda index=index: get(index) for index in range(2))
    stage._recover_hooks(context, "conditional")
    assert [row[:2] for row in calls] == [
        ("set", 1),
        ("set", 0),
        ("get", 0),
        ("get", 1),
        ("get", 1),
        ("get", 0),
    ]
    assert not context.hooks_safe and len(context.cleanup_errors) == 2


@pytest.mark.parametrize("source_error", [None, RuntimeError("retained-unwind")])
def test_raw_none_return_precedes_fallible_return_list_capture(
    conditional, monkeypatch, source_error
):
    h = conditional
    h.source_error = source_error
    capture = OSError("return-history-capture")
    raw_context = stage._raw_context

    class RefuseAppend(list):
        def append(self, value):
            raise capture

    def context(*args):
        value = raw_context(*args)
        value.raw_returns = RefuseAppend()
        value.graph_tape.events = value.raw_returns
        return value

    monkeypatch.setattr(stage, "_raw_context", context)
    with pytest.raises((RuntimeError, stage.DynamicsRejected)) as caught:
        stage.prepare(h.request, enabled=True)
    failed = stage.failed_context(h.request)
    assert failed.last_raw is not None and failed.last_raw[1] is None
    assert failed.capture_error is capture and failed.capture_errors
    if source_error is not None:
        assert caught.value is source_error
    assert failed.trial is None


def test_cleanup_helper_entry_refusal_cannot_mask_source_primary(conditional, monkeypatch):
    _observer_focus(monkeypatch)
    h = conditional
    h.source_error, h.cause = RuntimeError("source-before-cleanup"), KeyError("source-cause")
    secondary = LookupError("recovery-entry")
    original = sys.getprofile()

    def profile(frame, event, arg):
        if frame.f_code is stage._recover_hooks.__code__ and event == "call":
            raise secondary

    sys.setprofile(profile)
    try:
        with pytest.raises(RuntimeError) as caught:
            stage.prepare(h.request, enabled=True)
        failed = stage.failed_context(h.request)
        assert caught.value is h.source_error and caught.value.__cause__ is h.cause
        assert any(row[1] is secondary for row in failed.cleanup_errors)
        assert failed.hooks_safe and sys.getprofile() is profile
    finally:
        sys.setprofile(original)


@pytest.mark.parametrize("mode", ["cached_builtins", "reached_numpy", "prefix_namespace"])
def test_bound_source_lookup_caches_and_reached_module_exports_reject_no_call_drift(
    conditional, monkeypatch, mode
):
    h = conditional
    owner = stage.prepare(h.request, enabled=True)
    context = stage._ISSUED[owner][0]
    if mode == "cached_builtins":
        function = context.methods["get_ion"]
        namespace = function.__globals__
        original = namespace["__builtins__"]
        namespace["__builtins__"] = dict(original)
        copied = FunctionType(
            function.__code__, namespace, function.__name__, closure=function.__closure__
        )
        namespace["__builtins__"] = original
        context.methods["get_ion"] = copied
    elif mode == "prefix_namespace":
        context.private["foreign"] = object()
    else:

        def unexecuted():
            return np.ones(2)

        context.helper_functions = (unexecuted,)
        context.bindings = stage._binding(context)
        monkeypatch.setattr(np, "ones", lambda *args: pytest.fail("No actual helper evaluation"))
    with pytest.raises(ValueError):
        stage._authority(owner)
    assert context.invalid


def test_restamped_trial_cannot_replace_original_issue_record_or_work(conditional):
    h = conditional
    owner = stage.prepare(h.request, enabled=True)
    context, original = stage._ISSUED[owner]
    changed = replace(original, c_calls=())
    changed = replace(changed, identity=stage._digest(stage.trial_record(changed)))
    context.trial = changed
    with pytest.raises(ValueError, match="state changed"):
        stage._authority(owner)
    assert context.invalid and stage._ISSUED[owner][1] is original
