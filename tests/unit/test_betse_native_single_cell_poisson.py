"""Poisson ownership controls with synthetic parents and forbidden native work."""

import ast
import hashlib
import inspect
import os
import pickle
import sys
from dataclasses import replace
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_poisson as poisson
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

env, ecm, core, geometry = poisson.environment, poisson.ecm, poisson.core, poisson.geometry


@pytest.fixture
def evidence(request, tmp_path):
    path = (
        Path(os.environ.get("CELLS_POISSON_EVIDENCE", str(tmp_path)))
        / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    )
    path.mkdir(parents=True, exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def harness(monkeypatch, *, failure=None):
    """Issue a test-only parent; no constructor, parameter store, RNG or source body.

    Only the already-qualified upstream *boundary* is substituted. The new
    Poisson registry, request proof, retirement, raw grid wrapper, binding,
    capture, cache/reference graph and sealing machinery execute normally.
    """
    pins, events, errors = {"synthetic-environment-source": "software-only"}, [], {}
    rng = SimpleNamespace(epoch=0)
    observer = object()
    mesh = SimpleNamespace(_cells_observer=observer, _cells_rng=SimpleNamespace(observer=observer))
    tape = SimpleNamespace(rng=rng, events=[], draws=[], locals={})
    p = SimpleNamespace(plot_grid_size=50, cell_height=2.5, cell_space=0.25)
    grid = object.__new__(ecm._GridRuntime)
    grid.cents_shape, grid.delta = (2, 2), 0.5
    grid.map_ij2k_cents = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]])
    caller = SimpleNamespace(grid_obj=grid, mesh=mesh, maskM=np.asarray([[0.0, 1.0]]))
    prefix = SimpleNamespace(
        caller=caller, p=p, rng=rng, mesh_context=SimpleNamespace(kernel=mesh, graph_tape=tape)
    )
    old = SimpleNamespace(parent=SimpleNamespace(parent=prefix), grid=grid)
    monkeypatch.setitem(ecm._GRIDS, grid, old)
    stream = core.caches.snapshot(dict(synthetic_MT_epoch=0))
    monkeypatch.setattr(
        core.initial, "_rng_stream", lambda actual: stream if actual is rng else None
    )

    def snapshot(context):
        return core.caches.snapshot(
            dict(
                caller={
                    name: value
                    for name, value in vars(caller).items()
                    if name not in {"grid_obj", "mesh"}
                },
                grid=dict(vars(grid)),
                parameters=vars(p),
                RNG_epoch=rng.epoch,
            )
        )

    def graphs(context):
        return (geometry.callers._graph(caller, p, tape), geometry.callers._graph(grid, p, tape))

    retained_env, retained_ecm = env._bindings(), ecm._bindings()

    def check(context):
        ecm.completion._check_binding_identity(env._bindings(), retained_env)
        ecm.completion._check_binding_identity(ecm._bindings(), retained_ecm)
        if (
            rng.epoch != 0
            or mesh._cells_observer is not observer
            or mesh._cells_rng.observer is not observer
            or prefix.p is not p
        ):
            raise ValueError("Synthetic retained upstream observer/RNG/parameter authority changed")

    monkeypatch.setattr(env, "_check", check)
    monkeypatch.setattr(env, "_snapshot", snapshot)
    monkeypatch.setattr(env, "_graphs", graphs)
    monkeypatch.setattr(poisson, "_verify_sources", lambda: dict(pins))
    parent = SimpleNamespace(
        parent=old,
        finished=True,
        invalid=False,
        active=False,
        thread=get_ident(),
        trees=[],
        request=object(),
    )
    cache = snapshot(parent)
    trial = env.Trial(
        "synthetic-env-request",
        "synthetic-prior",
        cache,
        cache,
        (),
        (),
        (),
        stream,
        stream,
        True,
        None,
        None,
        None,
        "",
    )
    parent.trial = replace(trial, identity=core.records._digest(env.trial_record(trial)))
    parent.graphs = graphs(parent)
    owner = object.__new__(env.EnvironmentOwner)
    monkeypatch.setitem(env._ISSUED, owner, parent)

    def fail(stage):
        if failure == stage:
            try:
                raise SyntheticSourceCause("original synthetic operator cause")
            except SyntheticSourceCause as cause:
                error = SyntheticSourceFailure("synthetic source failure at " + stage)
                errors.update(source=error, cause=cause)
                raise error from cause

    def zeros(shape):
        events.append(("zeros", shape))
        fail("zeros")
        return np.asarray([[1.0, -0.0], [0.0, 1.0]])

    def pinv(matrix):
        events.append(("pinv", matrix))
        fail("pinv")
        return np.asarray([[2.0, 0.0], [0.0, 2.0]])

    monkeypatch.setattr(poisson, "_ZEROS", zeros)
    monkeypatch.setattr(poisson, "_PINV", pinv)
    values = dict(poisson.source.__dict__)
    exec(
        compile(
            "def environment_voltage(self):\n"
            "    step('before_value',self)\n"
            "    discarded, self.lapENVinv = self.grid_obj.makeLaplacian("
            "bound={'N':'value','S':'value','E':'value','W':'value'})\n"
            "    step('after_value',self)\n"
            "def environment_current(self):\n"
            "    step('before_flux',self)\n"
            "    discarded, self.lapENV_P_inv = self.grid_obj.makeLaplacian("
            "bound={'N':'flux','S':'flux','E':'flux','W':'flux'})\n"
            "    step('after_flux',self)\n"
            "def synthetic_operator(self,"
            "bound={'N':'value','S':'value','E':'value','W':'value'}):\n"
            "    step('operator_'+bound['N'],self)\n"
            "    A = np.zeros((2,2))\n"
            "    Ainv = np.linalg.pinv(A)\n"
            "    return A,Ainv\n",
            "<synthetic-poisson>",
            "exec",
        ),
        values,
    )
    monkeypatch.setattr(poisson, "_CALLER", {name: values[name] for name in poisson.METHODS})
    monkeypatch.setattr(poisson, "_LAPLACIAN", values["synthetic_operator"])
    original_namespace = poisson._namespace
    hooks = {}

    def namespace(context):
        methods, operator = original_namespace(context)

        def step(stage, actual):
            assert actual is (grid if stage.startswith("operator_") else caller)
            events.append(stage)
            if stage in hooks:
                hooks[stage](context)
            fail(stage)

        for method in (*methods.values(), operator):
            method.__globals__["step"] = step
        return methods, operator

    monkeypatch.setattr(poisson, "_namespace", namespace)
    return SimpleNamespace(
        owner=owner,
        parent=parent,
        caller=caller,
        grid=grid,
        p=p,
        rng=rng,
        mesh=mesh,
        events=events,
        errors=errors,
        hooks=hooks,
        pins=pins,
    )


def continuation(h):
    return poisson.from_environment(h.owner, law_id=poisson.LAW_ID)


def test_software_literal_call_order_signature_helper_closure_and_stop(evidence):
    save(evidence, "pins", poisson._verify_sources())
    assert poisson.source.CALLER_LINES == ((503, 504), (511, 512))
    assert poisson.source.GRID_LINES == (252, 431)
    assert list(inspect.signature(poisson._LAPLACIAN).parameters) == ["self", "bound"]
    text = Path(poisson.source.__file__).read_text()
    tree = ast.parse(text)
    grids = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FiniteDiffPoisson"
    )
    attributes = {ast.unparse(n) for n in ast.walk(grids) if isinstance(n, ast.Attribute)}
    assert {s for s in attributes if s.startswith("self.")} == {
        "self.cents_shape",
        "self.map_ij2k_cents",
        "self.map_ij2k_cents.tolist",
        "self.map_ij2k_cents.tolist().index",
        "self.delta",
    }
    assert {s for s in attributes if s.startswith("np.")} == {
        "np.zeros",
        "np.linalg",
        "np.linalg.pinv",
    }
    callers = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CellsPoisson")
    assert not any(
        isinstance(n, ast.Attribute) and n.attr in {"lapGJ", "lapGJinv", "cell_i"}
        for n in ast.walk(callers)
    )
    assert len(poisson.INVALIDATED_OWNERS) == 11


def test_software_same_caller_grid_returns_aliases_retirement_and_work(monkeypatch, evidence):
    h = harness(monkeypatch)
    owner = poisson.prepare_continuation(continuation(h))
    context = poisson._authority(owner)
    save(evidence, "trial", owner.trial)
    save(evidence, "returns", context.results)
    assert owner.cells is h.caller and owner.cells.grid_obj is h.grid
    assert context.prior_trial is h.parent.trial
    assert [name for name, _ in context.results] == list(poisson.METHODS)
    assert h.caller.lapENVinv is context.results[0][1][1]
    assert h.caller.lapENV_P_inv is context.results[1][1][1]
    assert context.locals["environment_voltage"]["discarded"] is context.results[0][1][0]
    assert context.locals["environment_current"]["discarded"] is context.results[1][1][0]
    assert [s for s in h.events if isinstance(s, str)] == [
        "before_value",
        "operator_value",
        "after_value",
        "before_flux",
        "operator_flux",
        "after_flux",
    ]
    assert owner.trial.stream_before.identity == owner.trial.stream_after.identity
    assert all(
        any(e["entry_method"] == name for e in owner.trial.work)
        for name in (*poisson.METHODS, "synthetic_operator", "_grid_call", "_helper")
    )
    assert [e["sequence"] for e in owner.trial.work] == list(range(len(owner.trial.work)))
    assert all(e["status"] == "entered_not_success_credit" for e in owner.trial.work)
    with pytest.raises(env.EnvironmentRejected, match="consumed"):
        _ = h.owner.cells
    with pytest.raises(poisson.PoissonRejected):
        h.grid.makeLaplacian(bound=dict.fromkeys(("N", "S", "E", "W"), "value"))
    with pytest.raises(TypeError):
        pickle.dumps(owner)
    with pytest.raises(TypeError):
        pickle.dumps(h.grid)
    with pytest.raises(poisson.PoissonRejected) as caught:
        poisson.require_full_make_world(owner, phase=SimpleNamespace())
    assert caught.value.stage == "make_world_held"
    save(evidence, "next-boundary", caught.value)


@pytest.mark.parametrize("kind", ["mapping", "fake_owner", "unissued_owner", "law", "identity"])
def test_software_unavailable_or_changed_authority_refuses_without_native(
    kind, monkeypatch, evidence
):
    h = harness(monkeypatch)
    request = continuation(h)
    with pytest.raises((poisson.PoissonRejected, env.EnvironmentRejected)) as caught:
        if kind == "mapping":
            poisson.prepare_continuation(dict(environment=h.parent))
        elif kind == "fake_owner":
            poisson.from_environment(SimpleNamespace(cells=h.caller), law_id=poisson.LAW_ID)
        elif kind == "unissued_owner":
            poisson.from_environment(object.__new__(env.EnvironmentOwner), law_id=poisson.LAW_ID)
        elif kind == "law":
            poisson.from_environment(h.owner, law_id="supplied-state")
        else:
            poisson.prepare_continuation(replace(request, identity="changed"))
    save(evidence, "refusal", caught.value)
    assert h.events == [] and h.owner not in env._FORWARDED


@pytest.mark.parametrize("stage", ["operator_value", "operator_flux", "zeros", "pinv"])
def test_software_native_error_identity_partial_assignment_raw_locals_and_no_rearm(
    stage, monkeypatch, evidence
):
    h = harness(monkeypatch, failure=stage)
    request = continuation(h)
    with pytest.raises(poisson.PoissonRejected) as caught:
        poisson.prepare_continuation(request)
    error = caught.value
    save(evidence, "failure", error)
    assert error.source_error is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert error.partial["parent_trial"] is h.parent.trial and error.partial["environment_consumed"]
    assert not error.trial.source_completed
    if stage == "operator_flux":
        assert h.caller.lapENVinv is error.partial["results"][0][1][1]
        assert not hasattr(h.caller, "lapENV_P_inv")
    if stage == "pinv":
        assert "A" in error.partial["raw_locals"]["makeLaplacian"]
    assert not any(c.request is request for c in poisson._ISSUED.values())
    with pytest.raises(poisson.PoissonRejected):
        h.grid.makeLaplacian()
    with pytest.raises(poisson.PoissonRejected):
        poisson.prepare_continuation(request)
    assert error.partial["parent_trial"] is h.parent.trial


@pytest.mark.parametrize(
    "error",
    [
        np.linalg.LinAlgError("native SVD failure"),
        IndexError("native grid boundary"),
        ZeroDivisionError("native delta"),
        TypeError("native object array"),
    ],
)
def test_software_native_failure_types_are_not_repaired(error, monkeypatch, evidence):
    h = harness(monkeypatch)

    def fail(context):
        raise error

    h.hooks["operator_flux"] = fail
    with pytest.raises(poisson.PoissonRejected) as caught:
        poisson.prepare_continuation(continuation(h))
    save(evidence, "failure", caught.value)
    assert caught.value.source_error is error
    assert caught.value.partial["results"][0][1][1] is h.caller.lapENVinv
    assert not hasattr(h.caller, "lapENV_P_inv")


@pytest.mark.parametrize(
    "change",
    [
        "inverse_data",
        "equal_alias",
        "discarded_matrix",
        "grid_alias",
        "grid_method",
        "inherited_method_code",
        "caller_method_code",
        "source_class",
        "zeros",
        "pinv",
        "namespace_pinv",
        "observer",
        "RNG",
        "parent_trial",
        "grid_registry",
    ],
)
def test_software_child_refuses_changed_reference_binding_observer_and_epoch(
    change, monkeypatch, evidence
):
    h = harness(monkeypatch)
    owner = poisson.prepare_continuation(continuation(h))
    context = poisson._authority(owner)
    if change == "inverse_data":
        h.caller.lapENVinv[0, 0] += 1
    elif change == "equal_alias":
        assert np.array_equal(h.caller.lapENVinv, h.caller.lapENV_P_inv)
        h.caller.lapENVinv = h.caller.lapENV_P_inv
    elif change == "discarded_matrix":
        context.results[0][1][0][0, 0] += 1
    elif change == "grid_alias":
        h.caller.grid_obj = object.__new__(ecm._GridRuntime)
    elif change == "grid_method":
        monkeypatch.setattr(ecm._GridRuntime, "makeLaplacian", lambda *a, **k: None)
    elif change == "inherited_method_code":
        monkeypatch.setattr(ecm._GridRuntime.cell_grid, "__code__", (lambda *a: None).__code__)
    elif change == "caller_method_code":
        monkeypatch.setattr(
            poisson._CALLER[poisson.METHODS[0]], "__code__", (lambda *a: None).__code__
        )
    elif change == "source_class":
        monkeypatch.setattr(poisson.source.FiniteDiffPoisson, "makeLaplacian", lambda *a: None)
    elif change == "zeros":
        monkeypatch.setattr(poisson, "_ZEROS", lambda *a: None)
    elif change == "pinv":
        monkeypatch.setattr(poisson, "_PINV", lambda *a: None)
    elif change == "namespace_pinv":
        context.operator.__globals__["np"].linalg.pinv = lambda *a: None
    elif change == "observer":
        h.mesh._cells_rng.observer = object()
    elif change == "RNG":
        h.rng.epoch = 1
    elif change == "parent_trial":
        h.parent.trial = replace(h.parent.trial)
    else:
        monkeypatch.setitem(ecm._GRIDS, h.grid, SimpleNamespace())
    with pytest.raises(poisson.PoissonRejected) as caught:
        _ = owner.cells
    save(evidence, "refusal", caught.value)
    assert caught.value.stage == "poisson_drift" and context.invalid


@pytest.mark.parametrize("phase", ["makeLaplacian", "pinv"])
@pytest.mark.parametrize("boundary", ["enter", "return", "unwind"])
def test_software_observer_boundaries_stop_before_delegate_keep_output_or_primary(
    phase, boundary, monkeypatch, evidence
):
    h = harness(
        monkeypatch,
        failure="operator_value"
        if phase == "makeLaplacian" and boundary == "unwind"
        else "pinv"
        if boundary == "unwind"
        else None,
    )
    request = continuation(h)
    capture = SyntheticCaptureFailure("synthetic event capture failure")
    original = ecm._observe

    def observe(context, kind, raw):
        if kind == phase + "_" + boundary:
            geometry._remember_observation_error(context, capture, origin=kind, raw=raw)
        else:
            original(context, kind, raw)

    monkeypatch.setattr(ecm, "_observe", observe)
    previous = sys.getprofile()
    with pytest.raises(poisson.PoissonRejected) as caught:
        poisson.prepare_continuation(request)
    error = caught.value
    save(evidence, "failure", error)
    assert error.capture_error is capture and sys.getprofile() is previous
    assert error.source_error is (h.errors["source"] if boundary == "unwind" else None)
    if boundary == "unwind":
        assert error.source_error.__cause__ is h.errors["cause"]
    if boundary == "enter":
        assert (
            "operator_value" not in h.events
            if phase == "makeLaplacian"
            else not any(isinstance(e, tuple) and e[0] == "pinv" for e in h.events)
        )
    if boundary == "return":
        assert (
            len(error.partial["results"]) == 1
            if phase == "makeLaplacian"
            else any(name == "pinv" for _, name, _ in error.partial["helper_results"])
        )
    assert "after_value" not in h.events and "before_flux" not in h.events
    assert error.partial["parent_trial"] is h.parent.trial
    assert not any(c.request is request for c in poisson._ISSUED.values())


@pytest.mark.parametrize("where", ["makeLaplacian", "environment_voltage"])
@pytest.mark.parametrize("unwind", [False, True])
def test_software_raw_local_capture_keeps_primary_previous_profiler_and_partial(
    where, unwind, monkeypatch, evidence
):
    h = harness(monkeypatch, failure="operator_value" if unwind else None)
    request = continuation(h)
    original = geometry._capture_locals
    capture = SyntheticCaptureFailure("synthetic raw-local capture failure")

    def capture_locals(context, name, frame):
        if name == where:
            raise capture
        return original(context, name, frame)

    monkeypatch.setattr(geometry, "_capture_locals", capture_locals)
    previous = sys.getprofile()
    with pytest.raises(poisson.PoissonRejected) as caught:
        poisson.prepare_continuation(request)
    error = caught.value
    save(evidence, "failure", error)
    assert error.capture_error is capture and sys.getprofile() is previous
    assert error.source_error is (h.errors["source"] if unwind else None)
    assert "before_flux" not in h.events
    assert error.partial["parent_trial"] is h.parent.trial


@pytest.mark.parametrize("part", ["namespace", "snapshot", "trial", "identity", "graphs"])
@pytest.mark.parametrize("source_failure", [False, True])
def test_software_retirement_and_sealing_failure_preserve_prior_trial_never_issue(
    part, source_failure, monkeypatch, evidence
):
    h = harness(monkeypatch, failure="operator_flux" if source_failure else None)
    request = continuation(h)
    capture = SyntheticCaptureFailure("synthetic " + part + " failure")
    original_namespace = poisson._namespace

    def namespace(context):
        if part == "namespace":
            raise capture
        if part == "snapshot":
            original = poisson._snapshot

            def snapshot(c):
                if c.stage in {"source_checks", "environment_current"}:
                    raise capture
                return original(c)

            monkeypatch.setattr(poisson, "_snapshot", snapshot)
        elif part == "trial":
            monkeypatch.setattr(poisson, "Trial", lambda *a: (_ for _ in ()).throw(capture))
        elif part == "identity":
            original = poisson.trial_record

            def record(trial):
                original(trial)
                raise capture

            monkeypatch.setattr(poisson, "trial_record", record)
        elif part == "graphs":
            monkeypatch.setattr(poisson, "_graphs", lambda *a: (_ for _ in ()).throw(capture))
        return original_namespace(context)

    monkeypatch.setattr(poisson, "_namespace", namespace)
    with pytest.raises(poisson.PoissonRejected) as caught:
        poisson.prepare_continuation(request)
    error = caught.value
    save(evidence, "failure", error)
    assert error.partial["parent_trial"] is h.parent.trial and error.partial["environment_consumed"]
    assert not any(c.request is request for c in poisson._ISSUED.values())
    # An original source refusal precedes issuance-only graph capture.
    if source_failure and part == "graphs":
        assert error.source_error is h.errors["source"] and error.capture_error is None
    elif source_failure and part != "namespace":
        assert error.source_error is h.errors["source"] and error.capture_error is capture
    elif part == "namespace":
        assert error.source_error is capture
    else:
        assert error.capture_error is capture
    with pytest.raises(env.EnvironmentRejected, match="consumed"):
        _ = h.owner.cells


def test_software_reentrant_retirement_and_raw_entry_are_irreversible(monkeypatch, evidence):
    h = harness(monkeypatch)
    request, refusals = continuation(h), []

    def hook(context):
        for operation in (
            lambda: poisson.prepare_continuation(request),
            lambda: h.grid.makeLaplacian(bound=dict.fromkeys(("N", "S", "E", "W"), "value")),
        ):
            with pytest.raises(poisson.PoissonRejected) as caught:
                operation()
            refusals.append(caught.value)

    h.hooks["operator_value"] = hook
    owner = poisson.prepare_continuation(request)
    assert owner.cells is h.caller and len(refusals) == 2
    assert poisson._authority(owner).attempted == list(poisson.METHODS)
    save(evidence, "refusals", refusals)


@pytest.mark.parametrize("change", ["prior_mask", "equal_grid_alias"])
def test_software_mid_transition_parent_epoch_and_equal_grid_edges_refuse_before_helper(
    change, monkeypatch, evidence
):
    h = harness(monkeypatch)
    # Keep an equal, already-retained array available so alias retargeting does
    # not alter values, array counts or first-visit object order.
    if change == "equal_grid_alias":
        array = h.grid.map_ij2k_cents
        del h.grid.map_ij2k_cents
        h.grid.original_map, h.grid.equal_map = array, array.copy()
        h.grid.map_ij2k_cents = array
        h.parent.trial = replace(
            h.parent.trial, before=env._snapshot(h.parent), cache=env._snapshot(h.parent)
        )
        h.parent.trial = replace(
            h.parent.trial, identity=core.records._digest(env.trial_record(h.parent.trial))
        )
        h.parent.graphs = env._graphs(h.parent)

    def mutate(context):
        if change == "prior_mask":
            h.caller.maskM[0, 0] += 1
        else:
            before = poisson._parent_epoch(context)[0]
            h.grid.map_ij2k_cents = h.grid.equal_map
            assert poisson._parent_epoch(context)[0] == before

    h.hooks["before_value"] = mutate
    with pytest.raises(poisson.PoissonRejected) as caught:
        poisson.prepare_continuation(continuation(h))
    save(evidence, "failure", caught.value)
    assert "operator_value" not in h.events and caught.value.partial["environment_consumed"]
    assert not any(c.request is caught.value.request for c in poisson._ISSUED.values())
