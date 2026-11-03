"""Native-blocked contract controls, never an issued SEED-owner integration.

Original code is parsed/compiled but never called. Small explicit arrays test
the private read-only observation/retention contracts; they are not operators.
"""

import ast
import dis
import os
import sys
from contextlib import contextmanager
from threading import get_ident
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_seed_world_poisson as stage
from tests.unit import test_betse_native_world_phase_construction as controls
from validation.betse import betse_native_seed_world_poisson_software as software

_RAW_GUARD_SCOPES = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Source preparation only; native-blocked software not released")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(software), reuse=software.reuse.reuse))
    namespace = dict(vars(controls), software=adapter, stage=stage, _BLOCKADE_FAILURES=())
    original = controls._blockade.__wrapped__
    fn = FunctionType(original.__code__, namespace, original.__name__)
    attempted = []

    def forbid(*args, **kwargs):
        attempted.append("numerical_solver_or_RNG")
        raise AssertionError("No actual solver or RNG work in source-contract controls")

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
    value = FunctionType(
        function.__code__,
        dict(function.__globals__, **overrides),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    value.__kwdefaults__ = function.__kwdefaults__
    return value


def save(tmp_path, value, *, scope=None, label="evidence"):
    cache = (stage._CORE.caches if scope is None else scope).snapshot(value)
    software.snapshot.write_json(
        tmp_path / (label + ".json"),
        dict(
            identity=cache.identity,
            descriptor=cache.descriptor,
            all_finite=cache.all_finite,
            synthetic_contract_only=True,
            real_owner_or_source_credit=0,
        ),
    )
    np.savez(tmp_path / (label + ".npz"), **cache.numeric_columns())
    return cache


def functions():
    tree = ast.parse((software.ROOT / software.SOURCE).read_bytes())
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_poisson_preparation_exact_source_boundary_and_closed_contract(mode, tmp_path):
    plan = stage.source_plan(flux_operator=mode)
    software.snapshot.write_json(tmp_path / "source-plan.json", plan)
    assert plan["stages"] == stage.STAGES
    assert plan["tail_stores"] == stage.TAIL_FIELDS
    assert plan["callback_statuses"] == stage.CALLBACK_STATUSES
    assert plan["parent_source_pin"] is plan["parent_review_pin"] is None
    assert plan["known_original_flux_issue_not_repaired"] is True
    assert plan["operator_numerical_or_physical_admission"] is False
    assert plan["source_native_reference_or_scientific_release"] is False
    assert plan["flux_solve"] == ("same original operator" if mode == "original" else "not called")
    assert plan["capacity"]["max_issued_operator_arrays"] == 6
    assert plan["capacity"]["ordinary_array_elements"] == 262144


@pytest.mark.parametrize("mode", [None, True, 0, "repaired", "disabled "])
def test_poisson_exact_mode_refuses_without_owner_access(mode):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("A foreign object is not a source parent")

    with pytest.raises(stage.PoissonRejected) as caught:
        stage.from_geometry(Foreign(), law_id=stage.LAW_ID, flux_operator=mode)
    assert caught.value.stage == "mode"


@pytest.mark.parametrize("entry", ["original", "disabled", "prepare"])
def test_poisson_adoption_refuses_before_parent_read_or_release(entry, monkeypatch):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("No missing-hook fallback may read an owner")

    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.PoissonRejected) as caught:
        if entry == "prepare":
            stage.prepare(Foreign(), enabled=True)
        else:
            stage.from_geometry(Foreign(), law_id=stage.LAW_ID, flux_operator=entry)
    assert caught.value.stage == "unbound_contract"
    assert not stage._ACTIVE and not stage._CONSUMED and not stage._RETIRED and not stage._ISSUED


@pytest.mark.parametrize("entry", ["constructor", "unissued", "checkpoint"])
def test_poisson_no_supplied_or_hydrated_authority(entry):
    if entry == "constructor":
        with pytest.raises(TypeError):
            stage.PoissonOwner()
    elif entry == "unissued":
        with pytest.raises(stage.PoissonRejected):
            stage._authority(NS())
    else:
        with pytest.raises(TypeError):
            object.__new__(stage.PoissonOwner).__reduce_ex__(4)


@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_poisson_compile_only_callbacks_and_exact_disabled_assignment(mode, tmp_path):
    result = {}
    for name in stage.STAGES:
        code = stage._caller_code(name, mode)
        assert type(code) is CodeType
        assert code.co_filename.endswith("betse/science/cells.py")
        result[name] = dict(
            names=code.co_names,
            first_line=code.co_firstlineno,
            disassembly=[(n.opname, n.argrepr) for n in dis.get_instructions(code)],
        )
        if name in stage.METHODS:
            assert stage.CALLBACK_STATUSES[stage.METHODS.index(name)] in code.co_consts
            assert "progressed_next" in code.co_names
    software.snapshot.write_json(tmp_path / "unexecuted-code.json", result)
    voltage = result[stage.METHODS[0]]["names"]
    current = result[stage.METHODS[1]]["names"]
    assert "makeLaplacian" in voltage
    assert ("makeLaplacian" in current) is (mode == "original")
    assert "lapENV_P_inv" in current
    assert "asarray" in result["coerce_cell_i"]["names"]
    assert "ones" in result["default_gj_weights"]["names"]


def test_poisson_one_claim_no_intermediate_owner_or_stale_authority():
    source = functions()
    prepared = ast.unparse(source["prepare"])
    assert prepared.index("previous._authority(") < prepared.index("context.parent_claim(")
    assert prepared.count("previous._authority(") == 1
    assert prepared.index("_CONSUMED[request] = _RETIRED[") < prepared.index(
        "context.parent_claim("
    )
    assert prepared.index("context.trial = replace") < prepared.index(
        "object.__new__(PoissonOwner)"
    )
    assert "for name in STAGES" in prepared
    checked = ast.unparse(source["_check"])
    assert "context.parent_check(context) is not context.parent" in checked
    assert "previous._authority(" not in checked
    assert "context.world.parameter_record is not context.closed_record" in checked
    assert "context.world.active" in checked
    assert "context.parent.projector.objects is not context.projector_objects" in checked


def test_poisson_scope_wraps_full_graph_and_numeric_results_without_new_projector_roots():
    source = functions()
    graph = ast.unparse(source["_graph"])
    snapshot = ast.unparse(source["_snapshot"])
    assert "context.parent.projector.objects" in graph
    assert "context.parent.helper_views" in graph
    assert "context.parent.objects" in graph and "context.parent.holders" in graph
    assert "_scope(context).graph(" in graph
    assert "_scope(context).snapshot(" in snapshot
    assert "results=context.results" in snapshot and "helpers=context.helper_results" in snapshot
    assert "tail_helpers=context.tail_results" in snapshot
    assert "projector.objects.append" not in (software.ROOT / software.SOURCE).read_text()


def role_context(mode="original", *, complete=True):
    context = NS(request=NS(flux_operator=mode), helper_results=[], helper_inputs=[], results=[])
    selected = stage.METHODS if mode == "original" else stage.METHODS[:1]
    for index, name in enumerate(selected):
        # Distinct, explicitly synthetic data, not a Laplacian or an inverse.
        z = np.arange(4, dtype=np.float64).reshape(2, 2).copy()
        a = np.full((2, 2), index + 2.0)
        p = np.full((2, 2), index + 3.0)
        context.helper_results.append((name, "zeros", z))
        context.helper_inputs.append((name, "pinv", a))
        if complete or index == 0:
            context.helper_results.append((name, "pinv", p))
            context.results.append((name, (a, p)))
    return context


@pytest.mark.parametrize(
    "mode,complete,count", [("original", True, 6), ("original", False, 5), ("disabled", True, 3)]
)
def test_poisson_exact_role_aliases_and_failed_second_input_retained(
    mode, complete, count, tmp_path
):
    context = role_context(mode, complete=complete)
    roles = stage._roles(context)
    scope = stage._scope(context)
    save(tmp_path, roles, scope=scope)
    assert len(scope.roots) == len(roles) == count
    for name, pair in context.results:
        assert roles[name + ".A"] is pair[0] and roles[name + ".P"] is pair[1]
    if not complete:
        assert "environment_current.A" in roles and "environment_current.P" not in roles


@pytest.mark.parametrize(
    "fault", ["input_alias", "inverse_alias", "unknown_helper", "disabled_extra"]
)
def test_poisson_role_mismatch_refuses_without_repair(fault, tmp_path):
    context = role_context()
    save(tmp_path, stage._roles(context), scope=stage._scope(context), label="before")
    if fault == "input_alias":
        name, pair = context.results[0]
        context.results[0] = (name, (pair[0].copy(), pair[1]))
    elif fault == "inverse_alias":
        name, pair = context.results[0]
        context.results[0] = (name, (pair[0], pair[1].copy()))
    elif fault == "unknown_helper":
        context.helper_results.append((stage.METHODS[0], "repair", np.array([1.0])))
    else:
        context.request.flux_operator = "disabled"
    with pytest.raises(ValueError):
        stage._roles(context)


def test_poisson_large_root_capacity_is_local_and_does_not_hide_foreign_array(tmp_path):
    root = np.full((625, 625), 2.0)
    scope = stage.observation.Scope(roles={"environment_voltage.A": root})
    cache = save(tmp_path, {"A": root}, scope=scope)
    assert len(cache.columns) == 1 and cache.columns[0].values.shape == (625, 625)
    with pytest.raises(ValueError, match="bounded array"):
        stage._CORE.caches.snapshot(root)
    with pytest.raises(ValueError, match="authority"):
        scope.snapshot(root.copy())
    assert stage._CORE.caches.MAX_ARRAY_ELEMENTS == 262144


class Identity:
    pass


def isolated_fields():
    original = [0, 1]
    request = Identity()
    request.geometry_owner, request.flux_operator = object(), "disabled"
    cells = NS(cell_i=original, all_points_cell_i=original, mem_i=[0, 1, 2])
    context = NS(
        request=request,
        refs=object(),
        invalid=False,
        cells=cells,
        original_names=tuple(vars(cells)),
        assignment_allowed=2,
        tail_allowed=0,
        original_cell_i=original,
        original_all_points_cell_i=original,
        results=[(stage.METHODS[0], (np.array([[1.0]]), np.array([[2.0]])))],
        tail_results=[],
        tail_stores=[],
    )
    check = clone(
        stage._check_fields,
        _bootstrap=lambda value: None,
        _REQUESTS={request: context.refs},
        _CONSUMED={request: context},
        _RETIRED={request.geometry_owner: context},
    )
    return context, check


def test_poisson_tail_exact_store_order_replacement_and_original_alias(tmp_path):
    context, check = isolated_fields()
    context.cells.lapENVinv = context.results[0][1][1]
    context.cells.lapENV_P_inv = None
    for index, name in enumerate(stage.TAIL_METHODS):
        context.tail_allowed = index + 1
        value = None
        if index >= 4:
            value = np.array([0, 1]) if index == 4 else np.array([1.0, 1.0, 1.0])
            context.tail_results.append(("asarray" if index == 4 else "ones", value))
        setattr(context.cells, stage.TAIL_FIELDS[index], value)
        stage._finish_store(context, name)
        check(context)
    save(tmp_path, dict(caller=vars(context.cells), original=context.original_cell_i))
    assert context.cells.all_points_cell_i is context.original_cell_i
    assert context.cells.cell_i is context.tail_results[0][1]
    assert tuple(name for name, _ in context.tail_stores) == stage.TAIL_FIELDS
    assert not stage._ISSUED


@pytest.mark.parametrize(
    "fault", ["extra_field", "early_store", "replacement", "lost_alias", "false_none"]
)
def test_poisson_tail_field_predicate_refuses_specific_drift(fault):
    context, check = isolated_fields()
    context.cells.lapENVinv = context.results[0][1][1]
    context.cells.lapENV_P_inv = None
    check(context)  # Non-vacuous isolated baseline.
    if fault == "extra_field":
        context.cells.unrelated = None
    elif fault == "early_store":
        context.cells.lapGJinv = None
    elif fault == "replacement":
        context.cells.cell_i = np.array([0, 1])
    elif fault == "lost_alias":
        context.cells.all_points_cell_i = [0, 1]
    else:
        context.cells.lapENV_P_inv = np.zeros((1, 1))
    with pytest.raises(ValueError):
        check(context)


@pytest.mark.parametrize("name", ["zeros", "pinv", "asarray", "ones"])
@pytest.mark.parametrize("failure", ["source", "capture"])
def test_poisson_helper_return_and_primary_retention(name, failure, tmp_path):
    class Original(BaseException):
        def __bool__(self):
            return False

    primary, cause, capture = Original("source"), LookupError("cause"), Original("capture")
    primary.__cause__ = cause
    returned = np.array([3.0])
    original = [0, 1]
    stage_name = (
        stage.METHODS[0]
        if name in ("zeros", "pinv")
        else stage.TAIL_METHODS[4 if name == "asarray" else 5]
    )
    context = NS(
        stage=stage_name,
        grid_busy=True,
        helper_busy=False,
        primary=None,
        grid=NS(cents_shape=(1, 1)),
        helper_attempts=[],
        helper_inputs=[],
        helper_results=[],
        last_helper_return=None,
        last_helper_input=None,
        tail_inputs=[],
        tail_results=[],
        tail_attempts=[],
        last_tail_return=None,
        last_tail_input=None,
        executing=True,
        cells=NS(cell_i=original, mem_i=[0, 1]),
        original_cell_i=original,
        admitted={},
        capture_errors=(),
        observation_error=None,
    )
    if name == "pinv":
        context.helper_attempts.append((stage_name, "zeros"))

    def delegate(*args, **kwargs):
        if failure == "source":
            raise primary
        return returned

    for key in ("zeros", "pinv", "asarray", "ones"):
        setattr(context, key, delegate)

    def record(value, label, raw):
        if label.endswith("_return"):
            stage._capture_failure(value, capture, label, raw)
            raise capture

    function = clone(
        stage._helper if name in ("zeros", "pinv") else stage._tail_helper,
        _guard=lambda value: None,
        _check=lambda value: None,
        _record=record,
    )

    def wrapper(args):
        frame = sys._getframe()
        context.admitted[id(frame)] = dict(frame=frame, state="admitted", body_started=True)
        return function(context, name, delegate, args, {}, frame)

    A = np.array([[4.0]])
    context.operator_frame = context.caller_frame = sys._getframe()
    arguments = {"zeros": ((1, 1),), "pinv": (A,), "asarray": (original,), "ones": (2,)}
    with pytest.raises(Original) as caught:
        wrapper(arguments[name])
    save(
        tmp_path,
        dict(
            returned=returned,
            original=original,
            A=A,
            helper_results=context.helper_results,
            tail_results=context.tail_results,
            attempted=context.helper_attempts,
            tail_attempted=context.tail_attempts,
        ),
    )
    assert not context.helper_busy
    if failure == "source":
        assert caught.value is primary and primary.__cause__ is cause
        assert context.primary is primary and context.helper_results == context.tail_results == []
        if name == "pinv":
            assert context.helper_inputs[0][2] is A
    else:
        assert caught.value is capture and context.primary is None
        assert context.observation_error is capture
        retained = (
            context.last_helper_return if name in ("zeros", "pinv") else context.last_tail_return
        )
        assert retained[-1] is returned


def test_poisson_failure_wrapper_keeps_falsey_primary_cause_and_secondary(tmp_path):
    class Falsey(BaseException):
        def __bool__(self):
            return False

        def __str__(self):
            raise AssertionError("Failure retention must not render source errors")

    primary, secondary, cause = Falsey(), Falsey(), LookupError("cause")
    primary.__cause__ = cause
    raw = {"partial": np.array([1.0, 2.0])}
    context = NS(
        invalid=False, capture_errors=(), stage="environment_current", request=None, trial=None
    )
    failure = clone(stage._failure, _partial=lambda value: raw)
    with pytest.raises(stage.PoissonRejected) as caught:
        failure(context, primary, secondary)
    save(tmp_path, raw)
    assert caught.value.__cause__ is primary and primary.__cause__ is cause
    assert caught.value.source_error is primary and caught.value.capture_error is secondary
    assert caught.value.partial is raw and context.invalid


def test_poisson_no_hidden_solver_or_native_route_in_software_scope():
    source = functions()
    for name in ("_namespace", "_helper", "_tail_helper", "prepare"):
        text = ast.unparse(source[name])
        assert "set_state(" not in text and "RandomState(" not in text
        assert "lstsq(" not in text and "svd(" not in text
    source_text = ast.unparse(source["_namespace"])
    assert "original.__code__" in source_text and "original.__defaults__" in source_text
    assert "context.numpy.linalg.pinv" in source_text
    account = ast.unparse(source["_account"])
    assert "_PREFIX._account.__wrapped__" in account
    assert 'namespace["sys"]' in account or "namespace['sys']" in account
    assert not stage._ISSUED and not stage._ACTIVE


def isolated_observer_context():
    """No owner/claim: only the real observer mechanics receive synthetic frames."""
    return NS(
        request=NS(flux_operator="original"),
        trial=None,
        stage=stage.METHODS[0],
        active=True,
        invalid=False,
        thread=get_ident(),
        entry_error=None,
        observation_error=None,
        pending_source_error=None,
        primary=None,
        capture_errors=(),
        capture_reporting_errors=(),
        cleanup_errors=(),
        work=[],
        events=[],
        locals={},
        admitted={},
        body_codes={},
        callback_codes=frozenset(),
        forbidden_callback_codes=frozenset(),
        callback=None,
        callback_occurrence=None,
        callbacks_completed=[],
        callback_chain=(),
        entered_stages=[],
        boundaries={},
        executing=True,
        driver_frame=None,
        caller_frame=None,
        operator_frame=None,
        rand=object(),
        draw_active=False,
        native_root="/unavailable-synthetic-native-root/",
        generator_sites={},
        last_observed_return=None,
        last_raw_operator_return=None,
        raw_operator_returns=[],
        assignment_allowed=0,
        cells=NS(),
        phase=NS(),
        methods={},
    )


def isolated_account(context):
    # The selected production admission/callback/capture/guard/observer code is
    # unchanged. Expensive authority/epoch checks are replaced only in this
    # private synthetic scope: this is not genuine parent integration.
    fn = clone(
        stage._account.__wrapped__,
        _check=lambda value: None,
        _epoch=lambda value: (),
        _same_epoch=lambda value, old: None,
        _observer_bindings=lambda context=None: (),
    )
    return contextmanager(fn)(context)


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("fault", ["none", "unrelated", "reentrant", "foreign"])
def test_poisson_selected_callback_chain_with_both_real_hooks(index, fault, tmp_path):
    context = isolated_observer_context()
    hits = []

    def body(self, *, status):
        hits.append(
            (
                sys.getprofile() is context.observer_system.profile,
                sys.gettrace() is context.observer_system.trace,
            )
        )
        if fault == "reentrant":
            self.progressed_next(status=status)

    class Callbacks:
        def progressed_next(self, *, status):
            return body(self, status=status)

        def unrelated(self, *, status):
            hits.append("unrelated_body_must_not_enter")

    receiver = Callbacks()
    context.callback, context.phase.callbacks = receiver, receiver
    chain = (Callbacks.progressed_next, body)
    forbidden = frozenset(fn.__code__ for fn in (*chain, Callbacks.unrelated))
    context.parent = NS(forbidden_callback_codes=forbidden)
    stage._select_callbacks(context, chain)
    assert context.forbidden_callback_codes == frozenset((Callbacks.unrelated.__code__,))
    assert context.parent.forbidden_callback_codes is forbidden
    context.stage = stage.METHODS[index]
    context.callbacks_completed = list(stage.CALLBACK_STATUSES[:index])

    def method(self, phase):
        if fault == "unrelated":
            phase.callbacks.unrelated(status=stage.CALLBACK_STATUSES[index])
        elif fault == "foreign":
            Callbacks().progressed_next(status=stage.CALLBACK_STATUSES[index])
        else:
            phase.callbacks.progressed_next(status=stage.CALLBACK_STATUSES[index])

    context.methods = {context.stage: method}
    context.body_codes = {method.__code__: context.stage}
    context.driver_frame = sys._getframe()
    hooks = (sys.getprofile(), sys.gettrace())
    stage._ACTIVE.append(context)
    try:
        if fault == "none":
            with isolated_account(context):
                method(context.cells, context.phase)
        else:
            with pytest.raises(stage.PoissonRejected):
                with isolated_account(context):
                    method(context.cells, context.phase)
    finally:
        assert stage._ACTIVE.pop() is context
    software.snapshot.write_json(
        tmp_path / "callback-hooks.json",
        dict(
            synthetic_frames=True,
            fault=fault,
            index=index,
            hooks_observed=hits,
            callbacks=context.callbacks_completed,
            work=[(r["name"], r["state"], r["body_started"]) for r in context.work],
            final_hook_identities_restored=(
                sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]
            ),
            actual_parent_authority=False,
        ),
    )
    assert sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]
    if fault == "none":
        assert hits == [(True, True)]
        assert context.callbacks_completed == list(stage.CALLBACK_STATUSES[: index + 1])
        assert context.observation_error is None and context.entry_error is None
    else:
        assert hits == ([(True, True)] if fault == "reentrant" else [])
        assert context.invalid and context.entry_error is not None
        assert context.callbacks_completed == list(stage.CALLBACK_STATUSES[:index])
    assert not stage._ISSUED


def test_poisson_callback_exclusion_is_after_original_source_authentication():
    text = ast.unparse(functions()["_namespace"])
    assert text.index("'progressed_next'") < text.index("_select_callbacks(context, chain)")
    assert "callbacks._source_function(" in text
    assert "path.is_relative_to(_PREFIX.aliases.NATIVE)" in text


def holder_context(mode):
    context, check = isolated_fields()

    class Holder:
        pass

    cells = Holder()
    vars(cells).update(vars(context.cells))
    context.cells = cells
    context.request.flux_operator = mode
    roles = role_context(mode)
    context.results, context.helper_inputs, context.helper_results = (
        roles.results,
        roles.helper_inputs,
        roles.helper_results,
    )
    context.cells.equal_data = np.array([7.0, 8.0])
    context.original_names = tuple(vars(context.cells))
    phase, parameters, callback = NS(cells=context.cells), NS(voltage=0.1), NS(status="unchanged")
    phase.p, phase.callbacks = parameters, callback
    context.grid = NS(cents_shape=(1, 1), delta=2.0)
    objects = (
        ("phase", phase),
        ("parameters", parameters),
        ("callback", callback),
        ("caller", context.cells),
        ("grid", context.grid),
    )
    context.parent = NS(
        objects=objects,
        holders=tuple(vars(obj) for _, obj in objects),
        projector=NS(objects=list(objects)),
        helper_views=[np.array([5.0])],
    )
    context.parent_objects, context.parent_holders = context.parent.objects, context.parent.holders
    context.stable_view = NS(caller={}, grid=None, operator_roots={})
    context.final_view = NS(caller={}, grid=None, operator_roots={})
    context.stable_tape = NS(rng=object(), events=(), draws=(), locals={})
    context.tail_inputs, context.tail_results, context.tail_stores = [], [], []
    stage._bind_holder_views(context)
    return context, check


@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_poisson_real_shaped_holder_roster_survives_only_eight_declared_stores(mode, tmp_path):
    context, check = holder_context(mode)
    before = stage._immutable(context)
    final_before = stage._graph(context)
    stores = [
        (stage.FIELDS[0], context.results[0][1][1]),
        (stage.FIELDS[1], None if mode == "disabled" else context.results[1][1][1]),
    ]
    stores += [(name, None) for name in stage.TAIL_FIELDS[:4]]
    stores += [("cell_i", np.array([0, 1])), ("gj_default_weights", np.array([1.0, 1.0, 1.0]))]
    observations = []
    for index, (name, value) in enumerate(stores):
        if index >= 2:
            context.tail_allowed = index - 1
        if index >= 6:
            context.tail_results.append(("asarray" if index == 6 else "ones", value))
        setattr(context.cells, name, value)
        if index >= 2:
            stage._finish_store(context, stage.TAIL_METHODS[index - 2])
        check(context)
        current = stage._immutable(context)
        stage._same(current[1][0], before[1][0])
        observations.append((name, current[0] == before[0], current[1][1] == before[1][1]))
        assert current[0] == before[0] and current[1][1] == before[1][1]
    final = stage._graph(context)
    save(
        tmp_path,
        {"caller": vars(context.cells), "original_cell_i": context.original_cell_i},
        scope=stage._scope(context),
    )
    software.snapshot.write_json(
        tmp_path / "holder-stores.json",
        dict(
            observations=observations,
            final_graph_changed=final[1] != final_before[1],
            actual_parent_authority=False,
        ),
    )
    assert len(observations) == 8 and final[1] != final_before[1]
    assert context.stable_view.holders[3] is context.stable_view.caller
    assert context.final_view.holders[3] is vars(context.cells)
    assert context.cells.all_points_cell_i is context.original_cell_i
    assert not stage._ISSUED


@pytest.mark.parametrize(
    "fault", ["unrelated", "equal_alias", "holder_roster", "holder_dictionary"]
)
def test_poisson_holder_projection_retains_unrelated_and_identity_guards(fault):
    context, _ = holder_context("disabled")
    before = stage._immutable(context)
    if fault == "unrelated":
        context.cells.extra = 1
    elif fault == "equal_alias":
        context.cells.equal_data = context.cells.equal_data.copy()
    elif fault == "holder_roster":
        context.parent.holders = tuple(dict(h) for h in context.parent.holders)
    else:
        context.cells.__dict__ = dict(vars(context.cells))
    if fault.startswith("holder_"):
        with pytest.raises(ValueError, match="holder|registry"):
            stage._immutable(context)
    else:
        current = stage._immutable(context)
        if fault == "equal_alias":
            assert current[0] == before[0]  # Equal bits must still fail alias identity.
            with pytest.raises(ValueError, match="identity"):
                stage._same(current[1][0], before[1][0])
        else:
            assert current[0] != before[0] and current[1][1] != before[1][1]


@pytest.mark.parametrize("source_fails", [False, True])
@pytest.mark.parametrize("append_fails", [False, True])
def test_poisson_real_return_observer_keeps_raw_and_falsey_primary(
    source_fails, append_fails, tmp_path
):
    class Failure(BaseException):
        def __bool__(self):
            return False

    original, secondary, cause = Failure("original"), Failure("capture"), LookupError("cause")
    original.__cause__ = cause

    class RejectAppend(list):
        def append(self, value):
            raise secondary

    context = isolated_observer_context()
    returned = (np.array([[2.0]]), np.array([[3.0]]))
    calls, following = [], []

    def operator(self, **kwargs):
        calls.append("operator")
        if source_fails:
            raise original
        return returned

    context.operator = operator
    context.original_operator = object()
    context.grid = NS()
    context.grid_busy = False
    context.results, context.attempted = [], []
    context.callbacks_completed = [stage.CALLBACK_STATUSES[0]]
    context.caller_frame = object()
    wrapper = NS(f_back=context.caller_frame)
    context.admitted[id(wrapper)] = dict(frame=wrapper, state="admitted", body_started=True)
    context.body_codes = {operator.__code__: "Grid.makeLaplacian"}
    context.raw_operator_returns = RejectAppend() if append_fails else []
    context.last_operator_return = None
    record = clone(stage._record, _epoch=lambda value: (), _same_epoch=lambda value, old: None)
    call = clone(stage._grid_call, _check=lambda value: None, _record=record)
    bound = dict.fromkeys(("N", "S", "E", "W"), "value")
    hooks = (sys.getprofile(), sys.gettrace())
    caught = None
    stage._ACTIVE.append(context)
    try:
        try:
            with isolated_account(context):
                actual = call(
                    context, context.original_operator, context.grid, (), {"bound": bound}, wrapper
                )
                following.append("synthetic_next_step")
        except BaseException as error:
            caught = error
    finally:
        assert stage._ACTIVE.pop() is context
    save(tmp_path, {"returned": returned, "available_results": context.results})
    software.snapshot.write_json(
        tmp_path / "return-observer.json",
        dict(
            source_fails=source_fails,
            append_fails=append_fails,
            calls=calls,
            following=following,
            source_primary_retained=context.primary is original,
            capture_retained=context.observation_error is secondary,
            raw_return_is_none=context.last_raw_operator_return[1] is None,
            no_child=not stage._ISSUED,
            actual_parent_authority=False,
        ),
    )
    assert sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]
    assert calls == ["operator"] and not stage._ISSUED
    if source_fails:
        assert caught is original and original.__cause__ is cause
        assert context.primary is original and context.pending_source_error is original
        assert context.last_raw_operator_return[1] is None and following == []
    elif append_fails:
        assert isinstance(caught, stage._LITERAL._CaptureStop)
        assert context.primary is None and context.last_operator_return[1] is returned
        assert context.last_raw_operator_return[1] is returned and following == []
    else:
        assert caught is None and actual is returned and following == ["synthetic_next_step"]
    if append_fails:
        assert context.observation_error is secondary
        assert context.capture_errors[0][1] is secondary
