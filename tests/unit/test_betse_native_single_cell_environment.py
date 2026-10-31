"""Synthetic environment/mask ownership; native stores/trees/interpolation blocked."""

import ast
import hashlib
import os
import pickle
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_environment as env
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def evidence(request, tmp_path):
    path = (
        Path(os.environ.get("CELLS_ENVIRONMENT_EVIDENCE", str(tmp_path)))
        / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    )
    path.mkdir(parents=True, exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def harness(monkeypatch, tmp_path, *, failure=None):
    helper = runpy.run_path(str(ROOT / "tests/unit/test_betse_native_single_cell_make_ecm.py"))
    h = helper["harness"](monkeypatch, tmp_path)
    upstream = h.h.upstream
    events, errors = [], {}

    def construct(p, recipe, configuration):
        upstream.events.append("parameters")
        mode = env.parameters._context(p).request.projection
        p._conf = configuration
        p.world_len, p.cell_radius, p.cell_lattice_disorder = 4.0, 0.5, 0.0
        p.cell_lattice_type = env.geometry.callers.source.CellLatticeType.HEX
        if mode == env.parameters.ENVIRONMENT:
            p.plot_grid_size = 50
        p.wsx, p.wsy, p.cell_height = 4.0, 4.0, 2.5
        if mode in (env.parameters.GEOMETRY, env.parameters.ENVIRONMENT):
            p.cell_space = 0.25
        p.ac = 1e-6
        if mode in (env.parameters.GEOMETRY, env.parameters.ENVIRONMENT):
            p.scale_cell, p.tm = 0.99, 7.5e-9
        p.d_cell, p.nx, p.ny, p.wsx, p.wsy = 1.0, 4, 4, 4.0, 4.0

    monkeypatch.setattr(env.parameters, "_construct", construct)
    monkeypatch.setattr(env, "_verify_sources", lambda: dict(upstream.pins))

    def fail(stage):
        if failure == stage:
            try:
                raise SyntheticSourceCause("original synthetic environment cause")
            except SyntheticSourceCause as cause:
                error = SyntheticSourceFailure("synthetic source failure at " + stage)
                errors.update(source=error, cause=cause)
                raise error from cause

    original_runtime = env._TreeRuntime

    class Tree:
        __new__ = original_runtime.__new__
        __init__ = original_runtime.__init__
        query = original_runtime.query
        tree = original_runtime.tree
        __reduce_ex__ = original_runtime.__reduce_ex__
        __getstate__ = original_runtime.__getstate__
        __setstate__ = original_runtime.__setstate__

    for name in env._REFUSED_TREE_METHODS:
        setattr(Tree, name, getattr(original_runtime, name))
    monkeypatch.setattr(env, "_TreeRuntime", Tree)
    monkeypatch.setattr(env, "_allocate_native_tree", lambda: object.__new__(Tree))

    def tree_init(tree, data):
        events.append("tree_constructor")
        tree.data = data
        tree.indices = np.asarray(list(range(len(data))))
        tree.mins, tree.maxes = np.asarray([0.0, 0.0]), np.asarray([1.0, 1.0])
        tree.n, tree.m, tree.leafsize, tree.boxsize = len(data), 2, 16, None
        fail("tree_constructor")

    def query(tree, data, **kwargs):
        events.append("tree_query")
        fail("tree_query")
        return np.zeros(len(data)), np.zeros(len(data), dtype=int)

    def griddata(points, values, xi, **kwargs):
        events.append("griddata")
        assert kwargs == dict(method="linear", fill_value=0)
        fail("griddata")
        return np.asarray([[0.0, 1.0], [1.0, 0.0]])

    def gaussian(value, sigma, **kwargs):
        events.append("gaussian_filter")
        assert sigma == 1 and kwargs == dict(mode="nearest")
        fail("gaussian_filter")
        return value

    monkeypatch.setattr(env, "_TREE_INIT", tree_init)
    monkeypatch.setattr(env, "_TREE_QUERY", query)
    monkeypatch.setattr(env, "_GRIDDATA", griddata)
    monkeypatch.setattr(env, "_GAUSSIAN", gaussian)

    values = dict(env.source.__dict__)
    exec(
        compile(
            "\n".join(
                "def " + name + "(self,p):\n    step(self,p," + repr(name) + ")"
                for name in env.METHODS
            ),
            "<synthetic-environment>",
            "exec",
        ),
        values,
    )
    monkeypatch.setattr(env, "_METHODS", {name: values[name] for name in env.METHODS})
    original_namespace = env._namespace

    def namespace(context):
        methods = original_namespace(context)

        def step(cells, p, name):
            events.append(name)
            assert p.plot_grid_size == 50
            if name == "environment":
                cells.ecm_sa = 4 * cells.delta * p.cell_height
                cells.ecm_vol = p.cell_height * cells.delta**2
                cells.ratio_cell2ecm = 1.0
                cells.points_tree = methods[name].__globals__["cKDTree"](cells.xypts)
                _, cells.map_cell2ecm = cells.points_tree.query(cells.cell_centres)
                cells.map_mem2ecm = np.asarray([0, 0])
                cells.ecm_bound_k = np.asarray([0])
                cells.ecm_allbound_k = np.asarray([0, 0])
                cells.bBot_k = cells.bTop_k = cells.bL_k = cells.bR_k = np.asarray([0])
                cells.map_ecm2mem = [[0, 1]]
                cells.envInds_inClust = np.asarray([0])
                cells.memSa_per_envSquare = np.asarray([1.0])
                cells.mems_per_envSquare = np.asarray([2.0])
                cells.true_ecm_vol = np.asarray([0.25])
                cells.cell2env_corrF = np.asarray([1.0, 1.0])
                cells.all_bound_mem_inds = cells.interior_bound_mem_inds = np.asarray([0])
                cells.inds_outmem = cells.ecm_inds_bound_cell = np.asarray([0])
                cells.M_divmap_mem2ecm = np.asarray([[1.0, 1.0]])
            elif name == "assign_grid_len":
                cells.grid_len = len(cells.xypts)
            else:
                assert cells.grid_len == len(cells.xypts)
                tree = methods[name].__globals__["cKDTree"](cells.xypts)
                _, cells.map_voronoi2ecm = tree.query(cells.ecm_verts_unique)
                cells.voronoi_mask = np.asarray([1.0])
                cells.Xgrid, cells.Ygrid = (
                    np.asarray([[0.0, 1.0], [0.0, 1.0]]),
                    np.asarray([[0.0, 0.0], [1.0, 1.0]]),
                )
                ns = methods[name].__globals__
                cells.maskM = ns["interp"].griddata(
                    (cells.xypts[:, 0], cells.xypts[:, 1]),
                    cells.voronoi_mask,
                    (cells.Xgrid, cells.Ygrid),
                    method="linear",
                    fill_value=0,
                )
                cells.maskM = ns["gaussian_filter"](cells.maskM, 1, mode="nearest")
                cells.maskECM = ns["interp"].griddata(
                    (cells.Xgrid.ravel(), cells.Ygrid.ravel()),
                    cells.maskM.ravel(),
                    (cells.X, cells.Y),
                    method="linear",
                    fill_value=0,
                )
                cells.maskECM = ns["gaussian_filter"](cells.maskECM, 1, mode="nearest")
                cells.inds_env, cells.inds_clust = [0, 3], [1, 2]
                cells.voronoi_centres = cells.xypts
                tree = ns["cKDTree"](cells.voronoi_centres)
                _, cells.cell_to_grid = tree.query(cells.cell_centres)
            fail(name)

        for method in methods.values():
            method.__globals__["step"] = step
        return methods

    monkeypatch.setattr(env, "_namespace", namespace)
    config = {
        "world options": {"cell height": "2.5", "cell spacing": "0.25"},
        "general options": {"comp grid size": 4},
    }
    request = env.from_core(upstream.parent, config, law_id=env.LAW_ID)
    return SimpleNamespace(h=h, upstream=upstream, request=request, events=events, errors=errors)


def parent(h):
    return env.ecm.prepare(h.request.ecm_request)


def test_software_literal_order_stores_and_preserved_yv_expression(evidence):
    save(evidence, "source-pins", env._verify_sources())
    assert env.source.STORE_LINES == [
        521,
        533,
        534,
        535,
        536,
        1118,
        1119,
        1122,
        1127,
        1128,
        1129,
        1130,
        1131,
    ]
    native = ast.parse(
        (env.geometry.callers.NATIVE_ROOT / "betse/science/parameters.py").read_text()
    )
    originals = {n.lineno: n for n in ast.walk(native) if isinstance(n, ast.Assign)}
    tree = ast.parse(Path(env.source.__file__).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ParameterStores")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef))
    assert ast.dump(ast.Module(body=method.body, type_ignores=[])) == ast.dump(
        ast.Module(body=[originals[n] for n in env.source.STORE_LINES], type_ignores=[])
    )
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CellsEnvironment")
    mask = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "make_maskM")
    yv = next(
        n
        for n in mask.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "yv" for t in n.targets)
    )
    assert [a.attr for a in yv.value.args[:2]] == ["xmin", "xmax"]


def test_software_fresh_projection_same_caller_grid_trees_masks_and_work(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = env.prepare(h.request)
    save(evidence, "trial", owner.trial)
    context = env._authority(owner)
    caller = owner.cells
    p = context.parent.parent.parent.p
    trial = env.parameters._authority(context.parent.parent.parent.parameter_owner).trial
    names = [name for name, _ in trial.stores]
    assert names[5] == "plot_grid_size" and names[6:8] == ["wsx", "wsy"]
    assert trial.projection == env.parameters.ENVIRONMENT and p.plot_grid_size == 50
    assert caller is env.geometry.callers._authority(h.upstream.state.caller)["caller"]
    assert [name for name, _ in owner.trial.stages] == list(env.METHODS)
    assert (
        h.events.count("tree_constructor") == 3
        and h.events.count("griddata") == h.events.count("gaussian_filter") == 2
    )
    assert caller.grid_obj is context.parent.grid and caller.voronoi_centres is caller.xypts
    assert type(caller.ecm_sa) is float and type(caller.ecm_vol) is float
    assert any(caller.points_tree is tree for tree in context.trees)
    assert owner.trial.stream_before.identity == owner.trial.stream_after.identity
    assert all(any(e["entry_method"] == name for e in owner.trial.work) for name in env.METHODS)
    assert owner.trial.source_completed


@pytest.mark.parametrize("retrofit", [False, True])
def test_software_legacy_ecm_cannot_gain_plot_store_authority(
    retrofit, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    old = env.ecm.prepare(h.h.request)
    if retrofit:
        env.ecm._authority(old).parent.parent.p.plot_grid_size = 50
    with pytest.raises((env.EnvironmentRejected, env.ecm.EcmRejected)) as caught:
        env.from_ecm(old, law_id=env.LAW_ID)
    assert old not in env.ecm._FORWARDED
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize(
    "stage", [*env.METHODS, "tree_constructor", "tree_query", "griddata", "gaussian_filter"]
)
def test_software_source_failures_keep_actual_parent_partial_trees_and_cause(
    stage, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure=stage)
    before = parent(h)
    request = env.from_ecm(before, law_id=env.LAW_ID)
    with pytest.raises(env.EnvironmentRejected) as caught:
        env.prepare_continuation(request)
    error = caught.value
    save(evidence, "failure", error)
    assert (
        error.source_error is h.errors["source"]
        and error.source_error.__cause__ is h.errors["cause"]
    )
    assert error.partial["parent_trial"] is before.trial and error.partial["ecm_consumed"]
    assert not error.trial.source_completed
    assert not any(c.request is request for c in env._ISSUED.values())
    with pytest.raises(env.ecm.EcmRejected):
        _ = before.cells
    for tree in error.partial["trees"]:
        with pytest.raises(env.EnvironmentRejected):
            tree.query(np.asarray([[0.0, 0.0]]))


@pytest.mark.parametrize("kind", ["empty", "index", "object_array", "interpolation"])
def test_software_native_style_failures_are_not_repaired(kind, monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    original = env._namespace
    failure = {
        "empty": IndexError("native empty boundary"),
        "index": IndexError("native grid index"),
        "object_array": TypeError("native object array"),
        "interpolation": ValueError("native interpolation triangulation"),
    }[kind]

    def namespace(context):
        methods = original(context)

        def broken(*a):
            raise failure

        fn = methods["environment"]
        from types import FunctionType

        methods["environment"] = FunctionType(
            broken.__code__, fn.__globals__, broken.__name__, closure=broken.__closure__
        )
        return methods

    monkeypatch.setattr(env, "_namespace", namespace)
    before = parent(h)
    with pytest.raises(env.EnvironmentRejected) as caught:
        env.prepare_continuation(env.from_ecm(before, law_id=env.LAW_ID))
    save(evidence, "failure", caught.value)
    assert caught.value.source_error is failure


@pytest.mark.parametrize(
    "change",
    [
        "caller_array",
        "equal_alias",
        "tree_data",
        "tree_edge",
        "tree_class",
        "parent_invalid",
        "parameter",
        "dispatch",
        "RNG",
        "observer",
        "method",
        "helper",
        "tree_method",
    ],
)
def test_software_source_child_rejects_authority_drift(change, monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    owner = env.prepare(h.request)
    context = env._authority(owner)
    caller = owner.cells
    if change == "caller_array":
        caller.maskM[0, 0] = 9.0
    elif change == "equal_alias":
        caller.voronoi_centres = caller.xypts.copy()
    elif change == "tree_data":
        caller.points_tree.data[0, 0] = 9.0
    elif change == "tree_edge":
        before = env._snapshot(context).identity
        other = next(tree for tree in context.trees if tree is not caller.points_tree)
        assert other.mins is not caller.points_tree.mins
        caller.points_tree.mins = other.mins
        assert env._snapshot(context).identity == before
    elif change == "tree_class":
        monkeypatch.setattr(env, "_TreeRuntime", type("OtherTree", (env._TreeRuntime,), {}))
    elif change == "parent_invalid":
        context.parent.invalid = True
    elif change == "parameter":
        context.parent.parent.parent.p.plot_grid_size = 51
    elif change == "dispatch":
        monkeypatch.setattr(
            type(context.parent.parent.parent.p),
            "__getattribute__",
            lambda p, n: 50 if n == "plot_grid_size" else object.__getattribute__(p, n),
        )
    elif change == "RNG":
        context.parent.parent.parent.rng.epoch = "changed"
    elif change == "observer":
        caller.mesh._cells_rng.observer = env.core.initial._Observer(())
    elif change == "method":
        monkeypatch.setitem(env._METHODS, "environment", lambda *a: None)
    elif change == "helper":
        context.methods["make_maskM"].__globals__["interp"].griddata = lambda *a, **k: None
    else:
        monkeypatch.setattr(env._TreeRuntime, "query", lambda *a, **k: None)
    with pytest.raises(env.EnvironmentRejected) as caught:
        _ = owner.cells
    save(evidence, "refusal", caught.value)
    assert caught.value.stage == "environment_drift"


@pytest.mark.parametrize("stage", env.METHODS)
@pytest.mark.parametrize("unwind", [False, True])
def test_software_local_capture_preserves_primary_and_stops_next_stage(
    stage, unwind, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure=stage if unwind else None)
    before = parent(h)
    request = env.from_ecm(before, law_id=env.LAW_ID)
    original, previous = env.geometry._capture_locals, sys.getprofile()
    capture = SyntheticCaptureFailure("synthetic environment observation failure")

    def broken(context, name, frame):
        if name == stage:
            raise capture
        return original(context, name, frame)

    monkeypatch.setattr(env.geometry, "_capture_locals", broken)
    with pytest.raises(env.EnvironmentRejected) as caught:
        env.prepare_continuation(request)
    error = caught.value
    save(evidence, "failure", error)
    assert error.capture_error is capture and sys.getprofile() is previous
    assert error.source_error is (h.errors["source"] if unwind else None)
    assert error.partial["parent_trial"] is before.trial and error.partial["ecm_consumed"]
    next_stage = env.METHODS.index(stage) + 1
    if next_stage < len(env.METHODS):
        assert env.METHODS[next_stage] not in h.events


@pytest.mark.parametrize("part", ["snapshot", "trial", "identity", "graphs"])
def test_software_sealing_failure_keeps_raw_completed_source_without_child(
    part, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    before = parent(h)
    request = env.from_ecm(before, law_id=env.LAW_ID)
    capture = SyntheticCaptureFailure("synthetic environment finalization failure")
    if part == "snapshot":
        original = env._snapshot

        def broken(context):
            if hasattr(context.parent.parent.parent.caller, "maskECM"):
                raise capture
            return original(context)
    else:

        def broken(*a, **k):
            raise capture

    monkeypatch.setattr(
        env,
        {
            "snapshot": "_snapshot",
            "trial": "Trial",
            "identity": "trial_record",
            "graphs": "_graphs",
        }[part],
        broken,
    )
    with pytest.raises(env.EnvironmentRejected) as caught:
        env.prepare_continuation(request)
    save(evidence, "failure", caught.value)
    assert (
        caught.value.capture_error is capture
        and caught.value.partial["parent_trial"] is before.trial
    )
    assert caught.value.partial["ecm_consumed"] and not any(
        c.request is request for c in env._ISSUED.values()
    )


def test_software_reentrancy_raw_tree_surface_checkpoint_and_Poisson_refuse(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    before = parent(h)
    request = env.from_ecm(before, law_id=env.LAW_ID)
    original = env._namespace
    refusals = []

    def namespace(context):
        with pytest.raises(env.EnvironmentRejected) as caught:
            env.prepare_continuation(request)
        refusals.append(caught.value)
        return original(context)

    monkeypatch.setattr(env, "_namespace", namespace)
    owner = env.prepare_continuation(request)
    context = env._authority(owner)
    assert owner.cells is context.parent.parent.parent.caller
    for tree in context.trees:
        for call in (
            lambda tree=tree: tree.query(np.asarray([[0.0, 0.0]])),
            lambda tree=tree: tree.__init__(np.asarray([[0.0, 0.0]])),
        ):
            with pytest.raises(env.EnvironmentRejected):
                call()
        for name in env._REFUSED_TREE_METHODS:
            with pytest.raises(env.EnvironmentRejected):
                getattr(tree, name)()
        with pytest.raises(TypeError):
            tree.__setstate__({})
        with pytest.raises(TypeError):
            pickle.dumps(tree)
        with pytest.raises(env.EnvironmentRejected):
            _ = tree.tree
    with pytest.raises(TypeError):
        pickle.dumps(owner)
    with pytest.raises(env.EnvironmentRejected) as caught:
        env.require_Poisson(owner, phase=SimpleNamespace())
    assert (
        caught.value.stage == "Poisson_held"
        and len(caught.value.partial["invalidated_owners"]) == 11
    )
    save(evidence, "reentrant", refusals)
    save(evidence, "Poisson-refusal", caught.value)
