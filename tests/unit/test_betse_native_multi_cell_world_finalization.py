"""Synthetic data-tail contracts; every literal/native/operator entry is blocked."""

import ast
import hashlib
import os
import pickle
import runpy
import sys
from dataclasses import replace
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_multi_cell_world_finalization as tail
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

poisson, core, env = tail.poisson, tail.core, tail.environment


class SyntheticNamespace:
    """Weak-referenceable fixture storage, never a public source authority."""

    def __init__(self, **values):
        vars(self).update(values)


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_WORLD_DATA_EVIDENCE", str(tmp_path)))
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(parents=True, exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def fixture(monkeypatch, *, failure=None, full=False, equal_grid=False, existing_array=False):
    helper = runpy.run_path(
        str(Path(__file__).with_name("test_betse_native_multi_cell_poisson.py"))
    )
    constructor = helper["harness"]
    h = FunctionType(
        constructor.__code__,
        dict(constructor.__globals__, SimpleNamespace=SyntheticNamespace),
        constructor.__name__,
        constructor.__defaults__,
        constructor.__closure__,
    )(monkeypatch, failure=None)
    h.mesh._cells_rng.rng = h.rng
    monkeypatch.setitem(tail.multi._ACTIVE, h.mesh, h.prefix)
    caller_owner = object.__new__(tail.multi.MultiCellOwner)
    h.parent.request = env.ContinuationRequest(caller_owner, "synthetic-environment-request")
    h.parent.retirement = object()
    monkeypatch.setitem(tail.multi._ISSUED, caller_owner, h.prefix)
    monkeypatch.setitem(tail.multi._FORWARDED, caller_owner, h.parent.retirement)
    monkeypatch.setattr(
        core.initial,
        "_rng_stream",
        lambda actual: core.caches.snapshot(dict(synthetic_MT_epoch=actual.epoch)),
    )
    h.caller.cell_i = np.asarray([0, 1]) if existing_array else [0, 1]
    h.caller.mem_i = [0, 1, 2]
    h.caller.all_points_cell_i = h.caller.cell_i
    old_cell_i = h.caller.cell_i
    if equal_grid:
        h.grid.original_map = h.grid.map_ij2k_cents
        h.grid.equal_map = h.grid.map_ij2k_cents.copy()
    if full:
        calls = {"zeros": 0, "pinv": 0}

        def zeros(shape):
            calls["zeros"] += 1
            return helper["_matrix"](10 * calls["zeros"])

        def pinv(array):
            calls["pinv"] += 1
            return helper["_matrix"](10 * calls["pinv"] + 2)

        monkeypatch.setattr(poisson, "_ZEROS", zeros)
        monkeypatch.setattr(poisson, "_PINV", pinv)
    cache = env._snapshot(h.parent)
    h.parent.trial = replace(h.parent.trial, before=cache, cache=cache, identity="")
    h.parent.trial = replace(
        h.parent.trial, identity=core.records._digest(env.trial_record(h.parent.trial))
    )
    h.parent.graphs = env._graphs(h.parent)
    parent_owner = poisson.prepare_continuation(helper["continuation"](h))
    parent = poisson._authority(parent_owner)
    events, hooks, errors = [], {}, {}

    def fail(where):
        if failure == where:
            try:
                raise SyntheticSourceCause("original synthetic data-tail cause")
            except SyntheticSourceCause as cause:
                error = SyntheticSourceFailure("synthetic source failure at " + where)
                errors.update(source=error, cause=cause)
                raise error from cause

    def asarray(value):
        assert value is old_cell_i
        events.append("asarray_delegate")
        fail("asarray")
        return np.asarray(value)

    def ones(size):
        assert size == 3
        events.append("ones_delegate")
        fail("ones")
        return np.asarray([1.0] * size)

    monkeypatch.setattr(tail, "_ASARRAY", asarray)
    monkeypatch.setattr(tail, "_ONES", ones)
    namespace = dict(tail.source.__dict__)
    statements = (
        "self.lapGJinv = None",
        "self.lapGJ = None",
        "self.M_sum_mem_to_ecm = None",
        "self.gradMem = None",
        "self.cell_i = np.asarray(self.cell_i)",
        "self.gj_default_weights = np.ones(len(self.mem_i))",
    )
    text = "\n".join(
        f"def {name}(self):\n    step('{name}_before',self)\n    {statement}\n"
        f"    step('{name}_after',self)\n"
        for name, statement in zip(tail.METHODS, statements, strict=True)
    )
    exec(compile(text, "<synthetic-world-tail>", "exec"), namespace)
    monkeypatch.setattr(tail, "_NATIVE", {name: namespace[name] for name in tail.METHODS})
    original = tail._namespace

    def methods(context):
        result = original(context)

        def step(where, actual):
            assert actual is h.caller
            events.append(where)
            if where in hooks:
                hooks[where](context)
            fail(where)

        for function in result.values():
            function.__globals__["step"] = step
        return result

    monkeypatch.setattr(tail, "_namespace", methods)
    return SimpleNamespace(
        h=h,
        owner=parent_owner,
        parent=parent,
        caller=h.caller,
        old_cell_i=old_cell_i,
        events=events,
        hooks=hooks,
        errors=errors,
        archive=helper["_archive"],
    )


def continuation(h):
    return tail.from_poisson(h.owner, law_id=tail.LAW_ID)


def test_software_literal_six_store_AST_order_exact_roster_and_no_solver_claim(evidence):
    save(evidence, "pins", tail._verify_sources())
    assert tail.STORES == (
        "lapGJinv",
        "lapGJ",
        "M_sum_mem_to_ecm",
        "gradMem",
        "cell_i",
        "gj_default_weights",
    )
    assert tail.source.STORE_LINES == (517, 518, 521, 522, 525, 526)
    tree = ast.parse(Path(tail.source.__file__).read_text())
    calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert calls == {"np.asarray", "np.ones", "len"}
    methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert tuple(node.name for node in methods) == tail.METHODS
    assert all(len(node.body) == 1 and isinstance(node.body[0], ast.Assign) for node in methods)
    assert len(tail.INVALIDATED_OWNERS) == 11


@pytest.mark.parametrize("existing_array", [False, True])
def test_software_same_actual_caller_operators_and_original_aliases_six_stores_only(
    existing_array, monkeypatch, evidence
):
    h = fixture(monkeypatch, existing_array=existing_array)
    original = dict(vars(h.caller))
    operator_pairs = [(name, pair) for name, pair in h.parent.results]
    owner = tail.prepare_continuation(continuation(h))
    context = tail._authority(owner)
    caller = owner.cells
    assert caller is h.caller and context.prior_trial is h.parent.trial
    for name, value in original.items():
        if name not in tail.STORES:
            assert getattr(caller, name) is value
    assert all(getattr(caller, name) is None for name in tail.STORES[:4])
    assert caller.all_points_cell_i is h.old_cell_i
    assert (caller.cell_i is h.old_cell_i) is existing_array
    assert [int(value) for value in caller.cell_i] == [0, 1]
    assert caller.gj_default_weights.tolist() == [1.0, 1.0, 1.0]
    assert all(caller.gj_default_weights is not value for value in original.values())
    assert h.parent.results == operator_pairs
    assert context.applied == list(tail.STORES) and len(context.stages) == 6
    assert [name for name, _ in context.helpers] == ["asarray", "ones"]
    assert owner.trial.stream_before.identity == owner.trial.stream_after.identity
    assert [row["sequence"] for row in owner.trial.work] == list(range(len(owner.trial.work)))
    for method in tail.METHODS:
        assert sum(row["entry_method"] == method for row in owner.trial.work) == 1
    assert len(poisson._observation(h.parent).roots) == 6
    with pytest.raises(poisson.PoissonRejected, match="consumed"):
        _ = h.owner.cells
    with pytest.raises(TypeError):
        pickle.dumps(owner)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.require_full_make_world(owner, phase=SimpleNamespace())
    assert caught.value.stage == "full_make_world_held"
    save(evidence, "trial", owner.trial)
    save(
        evidence,
        "identity-aliases",
        dict(
            original_cell_i=context.original_fields["cell_i"],
            cell_i=caller.cell_i,
            all_points_cell_i=caller.all_points_cell_i,
            helper_results=context.helpers,
            applied=context.applied,
            full_world_refusal=caught.value,
        ),
    )


@pytest.mark.parametrize("kind", ["mapping", "fake_owner", "unissued", "law", "identity"])
def test_software_unavailable_or_changed_owner_refuses_without_consumption(
    kind, monkeypatch, evidence
):
    h = fixture(monkeypatch)
    request = continuation(h)
    with pytest.raises((tail.FinalizationRejected, poisson.PoissonRejected)) as caught:
        if kind == "mapping":
            tail.prepare_continuation(dict(poisson=h.parent))
        elif kind == "fake_owner":
            tail.from_poisson(SimpleNamespace(cells=h.caller), law_id=tail.LAW_ID)
        elif kind == "unissued":
            tail.from_poisson(object.__new__(poisson.PoissonOwner), law_id=tail.LAW_ID)
        elif kind == "law":
            tail.from_poisson(h.owner, law_id="full-world")
        else:
            tail.prepare_continuation(replace(request, identity="changed"))
    assert h.events == [] and h.owner not in poisson._FORWARDED
    save(evidence, "refusal", caught.value)


def test_software_early_failure_has_primary_raw_parent_and_no_fabricated_baseline(
    monkeypatch, evidence
):
    h = fixture(monkeypatch)
    request = continuation(h)
    primary = SyntheticSourceFailure("retained primary preflight")
    primary.__cause__ = SyntheticSourceCause("original cause")

    def fail(owner):
        assert owner is h.owner
        raise primary

    def forbidden(*args):
        raise AssertionError("preflight refusal must not recapture baseline or RNG")

    monkeypatch.setattr(poisson, "_validate", fail)
    monkeypatch.setattr(tail, "_snapshot", forbidden)
    monkeypatch.setattr(core.initial, "_rng_stream", forbidden)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(request)
    error = caught.value
    assert error.source_error is primary and error.trial is None and error.capture_error is None
    assert error.__cause__ is primary and error.partial["parent"] is h.parent
    assert error.partial["parent_trial"] is h.parent.trial
    assert not error.partial["poisson_consumed"]
    assert not hasattr(error.partial["context"], "before")
    save(evidence, "failure", error)


@pytest.mark.parametrize("method", tail.METHODS)
@pytest.mark.parametrize("boundary", ["before", "after"])
def test_software_each_native_store_failure_retains_partial_original_parent_and_cause(
    method, boundary, monkeypatch, evidence
):
    h = fixture(monkeypatch, failure=method + "_" + boundary)
    request = continuation(h)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(request)
    error = caught.value
    assert error.source_error is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert error.partial["parent_trial"] is h.parent.trial
    assert error.partial["poisson_consumed"] and not error.trial.source_completed
    index = tail.METHODS.index(method)
    assert error.partial["applied"] == list(tail.STORES[:index])
    if boundary == "after":
        assert tail.STORES[index] in error.partial["actual_tail_fields"]
    assert h.caller.lapENVinv is h.parent.results[0][1][1]
    assert h.caller.lapENV_P_inv is h.parent.results[1][1][1]
    assert not any(context.request is request for context in tail._ISSUED.values())
    with pytest.raises(poisson.PoissonRejected, match="consumed"):
        _ = h.owner.cells
    save(evidence, "failure", error)


@pytest.mark.parametrize("name", ["asarray", "ones"])
def test_software_helper_source_failure_keeps_partial_cell_coercion_and_operators(
    name, monkeypatch, evidence
):
    h = fixture(monkeypatch, failure=name)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(continuation(h))
    error = caught.value
    assert error.source_error is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert h.caller.all_points_cell_i is h.old_cell_i
    assert (h.caller.cell_i is h.old_cell_i) is (name == "asarray")
    assert not hasattr(h.caller, "gj_default_weights")
    assert error.partial["parent_trial"] is h.parent.trial and not error.trial.source_completed
    save(evidence, "failure", error)


@pytest.mark.parametrize(
    "kind",
    [
        "bits",
        "equal_cell_i",
        "old_cell_i",
        "operator_bits",
        "operator_alias",
        "grid_equal_map",
        "grid",
        "parameter",
        "RNG",
        "observer",
        "parent_trial",
        "parent_context",
        "class_code",
        "source_code",
        "np_helper",
        "namespace_helper",
        "cleared_default",
    ],
)
def test_software_completed_child_refuses_value_alias_callable_observer_and_epoch_drift(
    kind, monkeypatch, evidence
):
    h = fixture(monkeypatch, equal_grid=True)
    owner = tail.prepare_continuation(continuation(h))
    context = tail._authority(owner)
    if kind == "bits":
        h.caller.gj_default_weights[0] = -0.0
    elif kind == "equal_cell_i":
        h.caller.cell_i = h.caller.cell_i.copy()
    elif kind == "old_cell_i":
        h.old_cell_i[0] = 99
    elif kind == "operator_bits":
        h.caller.lapENVinv[0, 0] += 1
    elif kind == "operator_alias":
        h.caller.lapENVinv = h.caller.lapENVinv.copy()
    elif kind == "grid_equal_map":
        h.h.grid.map_ij2k_cents = h.h.grid.equal_map
    elif kind == "grid":
        h.caller.grid_obj = object.__new__(env._GridRuntime)
    elif kind == "parameter":
        h.h.p.cell_height += 1
    elif kind == "RNG":
        h.h.rng.epoch += 1
    elif kind == "observer":
        h.h.mesh._cells_rng.observer = object()
    elif kind == "parent_trial":
        h.parent.trial = replace(h.parent.trial)
    elif kind == "parent_context":
        h.parent.finished = False
    elif kind == "class_code":
        monkeypatch.setattr(env._GridRuntime.cell_grid, "__code__", (lambda *args: None).__code__)
    elif kind == "source_code":
        monkeypatch.setattr(
            tail._NATIVE[tail.METHODS[0]], "__code__", (lambda *args: None).__code__
        )
    elif kind == "np_helper":
        monkeypatch.setattr(tail, "_ONES", lambda *args: None)
    elif kind == "namespace_helper":
        context.methods[tail.METHODS[0]].__globals__["np"].ones = lambda *args: None
    else:
        h.caller.lapGJ = np.asarray([[1.0]])
    with pytest.raises(tail.FinalizationRejected) as caught:
        _ = owner.cells
    assert context.invalid and caught.value.stage == "world_data_drift"
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize("kind", ["outside_store", "already_retained_edge", "earlier_output"])
def test_software_mid_tail_drift_refuses_before_next_helper(kind, monkeypatch, evidence):
    h = fixture(monkeypatch, equal_grid=True)

    def change(context):
        if kind == "outside_store":
            h.caller.maskM[0, 0] += 1
        elif kind == "already_retained_edge":
            before = tail._immutable_state(context).identity
            h.h.grid.map_ij2k_cents = h.h.grid.equal_map
            assert tail._immutable_state(context).identity == before
        else:
            h.caller.cell_i[0] = 90

    h.hooks[tail.METHODS[5] + "_before"] = change
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(continuation(h))
    assert "ones_delegate" not in h.events
    assert caught.value.partial["poisson_consumed"]
    save(evidence, "failure", caught.value)


@pytest.mark.parametrize("phase", [tail.METHODS[0], "ones"])
@pytest.mark.parametrize("boundary", ["enter", "return", "unwind"])
def test_software_observer_boundaries_no_later_delegate_and_primary_capture_separation(
    phase, boundary, monkeypatch, evidence
):
    failure = phase + "_before" if phase in tail.METHODS else phase
    h = fixture(monkeypatch, failure=failure if boundary == "unwind" else None)
    request = continuation(h)
    capture = SyntheticCaptureFailure("synthetic observation capture")
    original = env._observe

    def observe(context, kind, raw):
        if kind == phase + "_" + boundary:
            tail.geometry._remember_observation_error(context, capture, origin=kind, raw=raw)
        else:
            original(context, kind, raw)

    monkeypatch.setattr(env, "_observe", observe)
    previous = sys.getprofile()
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(request)
    error = caught.value
    assert error.capture_error is capture and sys.getprofile() is previous
    assert error.source_error is (h.errors["source"] if boundary == "unwind" else None)
    if boundary == "unwind":
        assert error.source_error.__cause__ is h.errors["cause"]
    if boundary == "enter":
        assert (phase + "_before" if phase in tail.METHODS else "ones_delegate") not in h.events
    if boundary == "return":
        assert (
            error.partial["last_completed_method"] is not None
            if phase in tail.METHODS
            else error.partial["last_completed_helper"][0] == "ones"
        )
    assert error.partial["parent_trial"] is h.parent.trial
    assert error.partial["poisson_consumed"]
    save(evidence, "failure", error)


@pytest.mark.parametrize("unwind", [False, True])
def test_software_raw_local_capture_retains_source_cause_raw_state_and_prior_profiler(
    unwind, monkeypatch, evidence
):
    name = tail.METHODS[1]
    h = fixture(monkeypatch, failure=name + "_after" if unwind else None)
    request = continuation(h)
    original = tail.geometry._capture_locals
    capture = SyntheticCaptureFailure("raw-local capture")

    def locals(context, method, frame):
        if method == name:
            raise capture
        return original(context, method, frame)

    monkeypatch.setattr(tail.geometry, "_capture_locals", locals)
    previous = sys.getprofile()
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(request)
    error = caught.value
    assert error.capture_error is capture and sys.getprofile() is previous
    assert error.source_error is (h.errors["source"] if unwind else None)
    assert "clear_M_sum_mem_to_ecm_before" not in h.events
    assert h.caller.lapGJ is None
    save(evidence, "failure", error)


@pytest.mark.parametrize("part", ["namespace", "snapshot", "trial", "identity", "graphs"])
@pytest.mark.parametrize("native_error", [False, True])
def test_software_sealing_failure_keeps_original_parent_and_never_rearms(
    part, native_error, monkeypatch, evidence
):
    h = fixture(monkeypatch, failure="ones" if native_error else None)
    request = continuation(h)
    capture = SyntheticCaptureFailure("synthetic " + part + " capture")
    original = tail._namespace

    def namespace(context):
        if part == "namespace":
            raise capture
        if part == "snapshot":
            snapshot = tail._snapshot

            def fail(c):
                if c.stage in {tail.METHODS[-1], "source_checks"}:
                    raise capture
                return snapshot(c)

            monkeypatch.setattr(tail, "_snapshot", fail)
        elif part == "trial":
            monkeypatch.setattr(tail, "Trial", lambda *args: (_ for _ in ()).throw(capture))
        elif part == "identity":
            monkeypatch.setattr(tail, "trial_record", lambda *args: (_ for _ in ()).throw(capture))
        elif part == "graphs":
            monkeypatch.setattr(tail, "_graphs", lambda *args: (_ for _ in ()).throw(capture))
        return original(context)

    monkeypatch.setattr(tail, "_namespace", namespace)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(request)
    error = caught.value
    assert error.partial["parent_trial"] is h.parent.trial and error.partial["poisson_consumed"]
    assert not any(context.request is request for context in tail._ISSUED.values())
    if part == "namespace":
        assert error.source_error is capture
    elif native_error and part == "graphs":
        assert error.source_error is h.errors["source"] and error.capture_error is None
    else:
        assert error.capture_error is capture
        assert error.source_error is (h.errors["source"] if native_error else None)
    with pytest.raises(poisson.PoissonRejected, match="consumed"):
        _ = h.owner.cells
    save(evidence, "failure", error)


def test_software_reentrant_repeat_and_raw_helper_entry_cannot_rearm(monkeypatch, evidence):
    h = fixture(monkeypatch)
    request = continuation(h)
    refusals = []

    def reenter(context):
        with pytest.raises(tail.FinalizationRejected) as caught:
            tail.prepare_continuation(request)
        refusals.append(caught.value)
        with pytest.raises(tail.FinalizationRejected):
            tail._helper(context, "ones", lambda size: None, 3)

    h.hooks[tail.METHODS[0] + "_before"] = reenter
    owner = tail.prepare_continuation(request)
    assert owner.cells is h.caller and len(refusals) == 1
    assert refusals[0].trial is None
    with pytest.raises(tail.FinalizationRejected):
        tail.prepare_continuation(request)
    assert tail._authority(owner).applied == list(tail.STORES)
    save(evidence, "reentrant-refusal", refusals)


@pytest.mark.parametrize("part", ["helper", "store"])
def test_software_completed_output_bookkeeping_failure_retains_raw_assignment(
    part, monkeypatch, evidence
):
    h = fixture(monkeypatch)
    original = tail._namespace
    capture = SyntheticCaptureFailure("completed output bookkeeping")

    class NoAppend(list):
        def append(self, value):
            raise capture

    def namespace(context):
        attr = "helpers" if part == "helper" else "applied"
        value = NoAppend()
        setattr(context, attr, value)
        setattr(context.raw_state, attr, value)
        return original(context)

    monkeypatch.setattr(tail, "_namespace", namespace)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(continuation(h))
    error = caught.value
    assert error.capture_error is capture and error.source_error is None
    key = "last_completed_helper" if part == "helper" else "last_completed_method"
    assert error.partial[key] is not None
    assert h.caller.lapGJinv is None
    save(evidence, "failure", error)


def test_software_weight_helper_cannot_return_preexisting_array(monkeypatch, evidence):
    h = fixture(monkeypatch)
    monkeypatch.setattr(tail, "_ONES", lambda size: h.caller.maskM)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(continuation(h))
    assert "aliases a preexisting" in str(caught.value.source_error)
    assert not hasattr(h.caller, "gj_default_weights")
    assert caught.value.partial["last_completed_helper"][1] is h.caller.maskM
    save(evidence, "failure", caught.value)


def test_software_request_factory_and_full_prefix_work_composition_are_nonadditive(
    monkeypatch, evidence
):
    h = fixture(monkeypatch)
    prefix_request = poisson.Request(None, "synthetic-fresh-Poisson-request")
    marker = object()

    def factory(parent, state, configuration, *, law_id):
        assert (
            parent is marker
            and state is marker
            and configuration is marker
            and law_id == poisson.LAW_ID
        )
        return prefix_request

    monkeypatch.setattr(poisson, "from_lifecycle", factory)
    request = tail.from_lifecycle(marker, marker, marker, law_id=tail.LAW_ID)
    monkeypatch.setattr(
        poisson, "prepare", lambda supplied: h.owner if supplied is prefix_request else None
    )
    owner = tail.prepare(request)
    retained = [row for row in owner.trial.work if row.get("component") == "multi_Poisson_prefix"]
    assert len(retained) == len(h.parent.trial.work)
    assert [row["sequence"] for row in owner.trial.work] == list(range(len(owner.trial.work)))
    error = poisson.PoissonRejected(
        "synthetic failed prefix", stage="prefix", partial=dict(work=list(h.parent.trial.work))
    )

    def failed(supplied):
        raise error

    monkeypatch.setattr(poisson, "prepare", failed)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare(request)
    assert caught.value.source_error is error
    assert caught.value.partial["work"] == list(h.parent.trial.work)
    save(evidence, "work", dict(success=owner.trial.work, failure=caught.value.partial["work"]))


def issued_multi_chain(monkeypatch):
    helper = runpy.run_path(
        str(Path(__file__).with_name("test_betse_native_multi_cell_environment.py"))
    )
    h = helper["fixture"](monkeypatch, native_mask_layout=True)
    geometry_fixture = {}
    exec(
        compile(
            "def cellMatrices(self,p):\n"
            "    logs.log_info('synthetic log')\n"
            "    probe('cellMatrices',self,p)\n"
            "    self.mem_i=[0,1]\n",
            "<synthetic-world-geometry>",
            "exec",
        ),
        geometry_fixture,
    )
    monkeypatch.setitem(env._METHODS, "cellMatrices", geometry_fixture["cellMatrices"])
    env_owner = env.prepare_continuation(h.continuation)
    actual_env = env._authority(env_owner)
    old_cell_i = h.parent.caller.cell_i
    with monkeypatch.context() as templates:
        fixture(templates)
        operator_methods, operator = dict(poisson._CALLER), poisson._LAPLACIAN
        tail_methods = dict(tail._NATIVE)
    monkeypatch.setattr(poisson, "_CALLER", operator_methods)
    monkeypatch.setattr(poisson, "_LAPLACIAN", operator)
    monkeypatch.setattr(poisson, "_ZEROS", lambda shape: np.asarray([[1.0, 0.0], [0.0, 1.0]]))
    monkeypatch.setattr(poisson, "_PINV", lambda matrix: np.asarray([[2.0, 0.0], [0.0, 2.0]]))
    operator_namespace = poisson._namespace

    def operators(context):
        methods, laplacian = operator_namespace(context)

        def step(name, actual):
            assert actual is (actual_env.grid if name.startswith("operator_") else h.parent.caller)

        for function in (*methods.values(), laplacian):
            function.__globals__["step"] = step
        return methods, laplacian

    monkeypatch.setattr(poisson, "_namespace", operators)
    poisson_owner = poisson.prepare_continuation(
        poisson.from_environment(env_owner, law_id=poisson.LAW_ID)
    )
    monkeypatch.setattr(tail, "_NATIVE", tail_methods)
    monkeypatch.setattr(tail, "_ASARRAY", lambda value: np.asarray(value))
    monkeypatch.setattr(tail, "_ONES", lambda size: np.asarray([1.0] * size))
    tail_namespace = tail._namespace
    steps, delegates, hooks = [], [], {}

    def asarray(value):
        delegates.append("asarray")
        return np.asarray(value)

    def ones(size):
        delegates.append("ones")
        return np.asarray([1.0] * size)

    monkeypatch.setattr(tail, "_ASARRAY", asarray)
    monkeypatch.setattr(tail, "_ONES", ones)

    def methods(context):
        result = tail_namespace(context)

        def step(name, actual):
            assert actual is h.parent.caller
            steps.append(name)
            if name in hooks:
                hooks[name](context)

        for function in result.values():
            function.__globals__["step"] = step
        return result

    monkeypatch.setattr(tail, "_namespace", methods)
    return SimpleNamespace(
        h=h,
        env=actual_env,
        old_cell_i=old_cell_i,
        owner=poisson_owner,
        steps=steps,
        delegates=delegates,
        hooks=hooks,
    )


@pytest.mark.parametrize("drift", [None, "descriptor_dispatch", "descriptor_state", "geometry_pi"])
def test_software_issued_multi_API_chain_keeps_real_caller_and_coerces_old_ECM_alias(
    drift, monkeypatch, evidence
):
    chain = issued_multi_chain(monkeypatch)
    h, actual_env, old_cell_i, poisson_owner = chain.h, chain.env, chain.old_cell_i, chain.owner
    child = tail.prepare_continuation(tail.from_poisson(poisson_owner, law_id=tail.LAW_ID))
    context = tail._authority(child)
    assert child.cells is h.parent.caller
    assert context.parent is poisson._authority(poisson_owner)
    assert context.parent.parent is actual_env and actual_env.parent is h.parent
    assert child.cells.all_points_cell_i is old_cell_i and child.cells.cell_i is not old_cell_i
    assert child.cells.mesh is h.parent.kernel and child.cells.grid_obj is actual_env.grid
    assert child.cells.cluster_mask is h.live_view and h.mask.clipping_matrix is h.live_view
    assert tail._prefix(context).p is h.parent.p and tail._prefix(context).rng is h.rng
    assert len(tail._scope(context).roots) == 6
    if drift == "descriptor_dispatch":

        def dispatch(self, name):
            if name == "grid_size":
                return 2
            return object.__getattribute__(self, name)

        monkeypatch.setattr(type(h.parent.p), "__getattribute__", dispatch)
    elif drift == "descriptor_state":
        h.parent.parameter_info.native.changed = True
    elif drift == "geometry_pi":
        namespace = actual_env.methods[tail.geometry.METHODS[0]].__globals__
        monkeypatch.setattr(namespace["math"], "pi", float.fromhex("0x1.921fb54442d17p+1"))
    if drift is not None:
        with pytest.raises(tail.FinalizationRejected) as caught:
            _ = child.cells
        save(evidence, "inherited-refusal", caught.value)
    save(
        evidence,
        "same-issued-chain",
        dict(
            trial=child.trial,
            original_cell_i=old_cell_i,
            coerced_cell_i=h.parent.caller.cell_i,
            original_alias=h.parent.caller.all_points_cell_i,
            mask_layout=core.caches.layout(h.live_view),
            descriptor_proof=h.parent.trial.descriptor_proof,
        ),
    )


@pytest.mark.parametrize("position", ["preflight", "before_helper", "completed"])
@pytest.mark.parametrize(
    "registry,mutation",
    [
        ("issuance", "remove"),
        ("issuance", "replace"),
        ("retirement", "remove"),
        ("retirement", "replace"),
    ],
)
def test_software_issued_multi_API_chain_caller_registry_links_repair(
    position, registry, mutation, monkeypatch, evidence, request
):
    chain = issued_multi_chain(monkeypatch)
    h, env_context = chain.h, chain.env
    supplied = tail.from_poisson(chain.owner, law_id=tail.LAW_ID)
    caller_owner = env_context.request.caller_owner
    assert tail.multi._authority(caller_owner) is h.parent
    assert tail.multi._FORWARDED.get(caller_owner) is env_context.retirement
    parent = poisson._authority(chain.owner)
    original_trial = parent.trial
    proof = {}
    save(
        evidence,
        "selection",
        dict(
            keyword=request.config.getoption("keyword"),
            deselect=request.config.getoption("deselect"),
            PYTEST_ADDOPTS=os.environ.get("PYTEST_ADDOPTS"),
        ),
    )

    def change(context):
        before = tail._snapshot(context)
        immutable = tail._immutable_state(context)
        graphs = tail._immutable_graphs(context)
        fields = tail._parent_fields(context)
        bindings = tail._inherited_bindings(context)
        mapping = tail.multi._ISSUED if registry == "issuance" else tail.multi._FORWARDED
        if mutation == "remove":
            monkeypatch.delitem(mapping, caller_owner)
        else:
            monkeypatch.setitem(
                mapping, caller_owner, SimpleNamespace() if registry == "issuance" else object()
            )
        # The only changed state is the one inherited registry edge. Numeric
        # caches, actual references, RNG, classes/code and all source contexts
        # remain identical, so the registry refusal is non-vacuous.
        assert tail._snapshot(context).identity == before.identity
        assert tail._immutable_state(context).identity == immutable.identity
        tail.geometry.meshes._same_graphs(tail._immutable_graphs(context), graphs)
        tail.multi.accounting._check_binding_identity(tail._parent_fields(context), fields)
        tail.multi.accounting._check_binding_identity(tail._inherited_bindings(context), bindings)
        proof.update(
            cache_before=before.identity,
            cache_after=tail._snapshot(context).identity,
            immutable_before=immutable.identity,
            immutable_after=tail._immutable_state(context).identity,
            graphs_unchanged=True,
            context_fields_unchanged=True,
            callable_bindings_unchanged=True,
        )

    if position == "preflight":
        original_links = tail._registry_links

        def links(context):
            if context.stage == "preflight":
                change(context)
            return original_links(context)

        monkeypatch.setattr(tail, "_registry_links", links)
    elif position == "before_helper":
        chain.hooks[tail.METHODS[4] + "_before"] = change
    else:
        child = tail.prepare_continuation(supplied)
        assert child.cells is h.parent.caller
        assert chain.delegates == ["asarray", "ones"]
        context = tail._authority(child)
        change(context)
        previous_delegates = list(chain.delegates)
        previous_steps = list(chain.steps)

    with pytest.raises(tail.FinalizationRejected) as caught:
        if position == "completed":
            _ = child.cells
        else:
            tail.prepare_continuation(supplied)
    error = caught.value
    assert proof and proof["cache_before"] == proof["cache_after"]
    if position == "completed":
        assert error.stage == "world_data_drift" and context.invalid
        assert error.trial is context.trial
        assert chain.delegates == previous_delegates and chain.steps == previous_steps
    else:
        assert error.partial["parent"] is parent and error.partial["parent_trial"] is original_trial
        assert error.partial["poisson_consumed"] is (position == "before_helper")
        assert chain.delegates == []
        assert "default_gj_weights_before" not in chain.steps
        if position == "preflight":
            assert error.trial is None and chain.steps == []
        else:
            assert error.partial["applied"] == list(tail.STORES[:4])
            assert h.parent.caller.cell_i is chain.old_cell_i
            assert error.partial["actual_tail_fields"]["gradMem"] is None
            assert not hasattr(h.parent.caller, "gj_default_weights")
        assert not any(value.request is supplied for value in tail._ISSUED.values())
    assert parent.trial is original_trial
    assert (chain.owner in poisson._FORWARDED) is (position != "preflight")
    save(evidence, "registry-proof", proof)
    save(evidence, "refusal", error)


def test_software_issued_multi_API_chain_caller_registry_links_unchanged_success(
    monkeypatch, evidence
):
    chain = issued_multi_chain(monkeypatch)
    owner = tail.prepare_continuation(tail.from_poisson(chain.owner, law_id=tail.LAW_ID))
    assert owner.cells is chain.h.parent.caller
    caller_owner = chain.env.request.caller_owner
    assert tail.multi._authority(caller_owner) is chain.h.parent
    assert tail.multi._FORWARDED.get(caller_owner) is chain.env.retirement
    assert chain.delegates == ["asarray", "ones"]
    assert chain.h.parent.caller.all_points_cell_i is chain.old_cell_i
    assert chain.h.parent.caller.cell_i is not chain.old_cell_i
    assert tail._authority(owner).applied == list(tail.STORES)
    save(
        evidence,
        "same-links",
        dict(
            trial=owner.trial,
            original_parent=poisson._authority(chain.owner).trial.identity,
            original_caller_trial=chain.h.parent.trial.identity,
        ),
    )


@pytest.mark.parametrize("second_helper_failure", [False, True])
def test_software_full_default_625_operators_unchanged_through_tail_and_failed_weights(
    second_helper_failure, monkeypatch, evidence
):
    h = fixture(monkeypatch, full=True, failure="ones" if second_helper_failure else None)
    before_pairs = tuple((name, pair) for name, pair in h.parent.results)
    if second_helper_failure:
        with pytest.raises(tail.FinalizationRejected) as caught:
            tail.prepare_continuation(continuation(h))
        error = caught.value
        context, trial = error.partial["context"], error.trial
        assert (
            error.source_error is h.errors["source"]
            and error.source_error.__cause__ is h.errors["cause"]
        )
        assert context.applied == list(tail.STORES[:5])
        assert not hasattr(h.caller, "gj_default_weights")
    else:
        owner = tail.prepare_continuation(continuation(h))
        context, trial = tail._authority(owner), owner.trial
        assert owner.cells is h.caller
    assert h.parent.results == list(before_pairs)
    assert h.caller.all_points_cell_i is h.old_cell_i and h.caller.cell_i is not h.old_cell_i
    scope = tail._scope(context)
    assert len(scope.roots) == 6
    for name, array in scope.roles.items():
        assert array.shape == (625, 625)
        h.archive(evidence, name, array)
    for index, column in enumerate(trial.cache.columns):
        if column.values.shape == (625, 625):
            h.archive(evidence, "cache-column-" + str(index), column.values)
    assert (
        core.caches.MAX_ARRAY_ELEMENTS,
        core.caches.MAX_TREE_NODES,
        core.caches.MAX_TREE_DEPTH,
    ) == (262144, 262144, 32)
    save(
        evidence,
        "full-cache",
        dict(
            descriptor=trial.cache.descriptor,
            identity=trial.cache.identity,
            roles=list(scope.roles),
            applied=context.applied,
            source_completed=trial.source_completed,
        ),
    )
