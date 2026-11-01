"""Blocked-native multi-cell continuation contracts; no numerical qualification."""

import ast
import hashlib
import json
import os
import pickle
import runpy
import subprocess
import sys
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_multi_cell_environment as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

multi = stage.multi
HELPER_PATH = Path(__file__).resolve().with_name("test_betse_native_multi_cell_caller.py")
helpers = SimpleNamespace(**runpy.run_path(str(HELPER_PATH)))


@pytest.fixture
def evidence(request, tmp_path):
    path = Path(os.environ.get("CELLS_MULTI_ENV_EVIDENCE", str(tmp_path)))
    path /= hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(parents=True, exist_ok=False)
    save(
        path,
        "case",
        dict(
            nodeid=request.node.nodeid,
            synthetic_only=True,
            native_entries=0,
            helper_sha256=hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest(),
        ),
    )
    return path


def descriptor_factory(monkeypatch, h):
    class SyntheticDescriptor:
        expr_alias_cls = int

        def __get__(self, instance, owner):
            h.steps.append("descriptor_read")
            if h.failure == "descriptor_read":
                fail(h, "descriptor_read")
            return instance._conf["general options"]["comp grid size"]

        def __set__(self, instance, value):
            raise AssertionError("No descriptor write is authorized")

    def factory(base):
        h.steps.append("descriptor_factory_before_birth")
        if h.failure == "descriptor_factory":
            fail(h, "descriptor_factory")
        info = SimpleNamespace(
            native=SyntheticDescriptor(),
            factories=(factory,),
            occurrence=("synthetic", stage.aliases.SELECTOR, "SyntheticDescriptor"),
            pins=stage.aliases.source_pins(),
            modules={},
        )
        info.wrapper = stage.aliases._GridAlias()
        info.runtime = type("SyntheticFreshParameters", (base,), {"grid_size": info.wrapper})
        info.bindings = stage.aliases._bindings(info)
        info.native_state = dict(vars(info.native))
        monkeypatch.setitem(stage.aliases._ALIASES, info.wrapper, info)
        stage.aliases.validate(info)
        h.info = info
        return info

    monkeypatch.setattr(stage.aliases, "prepare_runtime", factory)
    return factory


def fail(h, name):
    try:
        raise SyntheticSourceCause("synthetic primary cause at " + name)
    except SyntheticSourceCause as cause:
        error = SyntheticSourceFailure("synthetic native failure at " + name)
        h.errors.update(source=error, cause=cause)
        raise error from cause


def fixture(monkeypatch, *, failure=None, legacy=False, native_mask_layout=False):
    h = helpers.harness(monkeypatch)
    if native_mask_layout:
        h = helpers.mask_token_fixture(h, side=2)
    h.failure, h.steps, h.continuation_controls = failure, [], {}
    h.conf["general options"] = {"comp grid size": 2}
    descriptor_factory(monkeypatch, h)
    factory = multi.from_lifecycle if legacy else multi.from_lifecycle_ordinary
    h.request = factory(
        h.lr, h.ls, h.conf, law_id=multi.LAW_ID if legacy else multi.ORDINARY_LAW_ID
    )

    def prefix(context):
        context.initial_request, context.initial_state = h.ir, h.state
        context.clip_state, context.prelude = h.cs, h.ir.upstream[2]
        context.stage = context.work_context.stage = "isolated_authentication"
        h.steps.append("isolated_authentication")
        multi._new_parameters(context, h.recipe)
        h.steps.append("parameter_stores_complete")
        multi._controls(context)
        context.parameter_cache = multi.core.caches.snapshot(multi.callers._parameters(context.p))
        context.rng = h.rng
        context.tape = multi.callers._Tape(h.rng)
        context.image_tape = multi.images._Tape(h.ir.upstream[2].image)
        context.image_tape.picker = SimpleNamespace(filename="synthetic-owned-image")
        context.mask = context.image_tape.mask = h.mask
        context.image_tape.locals["TissuePickerImageMask.__init__"] = dict(
            xpts=h.mask_record["xpts_m"],
            ypts=h.mask_record["ypts_m"],
            **getattr(h, "synthetic_constructor_locals", {}),
        )
        context.lattice_audit = stage.core.caches.snapshot(dict(synthetic=True))
        context.image_audit = multi._image_state(context)
        context.lattice_method = lambda *a: None
        context.caller_method, context.pipeline = multi._namespaces(context)
        context.namespace_bindings = multi._namespace_bindings(context)
        context.native_entry_codes = multi._entry_codes(context)
        context.caller = object.__new__(multi._Caller)
        monkeypatch.setitem(multi._ACTIVE, context.caller, context)
        context.caller.__init__(context.p)
        h.steps.append("caller_birth")
        context.executing = True
        context.caller_method(context.caller, context.p, context.mask)
        multi._compare_mesh(context, h.ls)
        context.caller.cell_index(context.p)
        context.finished = True
        multi._check(context)

    monkeypatch.setattr(multi, "_execute", prefix)
    if failure == "descriptor_factory":
        return h
    h.owner = multi.prepare(h.request)
    h.parent = multi._authority(h.owner)
    if legacy:
        return h
    monkeypatch.setattr(
        stage, "_verify_sources", lambda: {"synthetic-continuation": "blocked-native"}
    )
    native_class = stage._TreeRuntime

    class SyntheticTree:
        __init__ = native_class.__init__
        query = native_class.query
        query_ball_point = native_class.query_ball_point
        __reduce_ex__ = native_class.__reduce_ex__
        __getstate__ = native_class.__getstate__
        __setstate__ = native_class.__setstate__
        tree = native_class.tree

    monkeypatch.setattr(stage, "_TreeRuntime", SyntheticTree)
    monkeypatch.setattr(stage, "_allocate_native_tree", lambda: object.__new__(SyntheticTree))

    def probe(name, caller, p=None):
        h.steps.append(name)
        assert caller is h.parent.caller
        assert p is None or p is h.parent.p
        assert caller.mesh is h.parent.kernel
        assert caller.mesh.image_mask is h.mask
        if name in h.continuation_controls:
            h.continuation_controls[name](stage_context())
        if h.failure == name:
            fail(h, name)
        if name == "cellVerts":
            caller.cell_i = [0]
            caller.synthetic_before = np.asarray([1.0, -0.0])
            caller.equal_reference = np.asarray([1.0, -0.0])
            caller.references = [caller.synthetic_before, caller.equal_reference]
        return h

    def stage_context():
        return next(ctx for ctx in stage._GRIDS.values() if ctx.parent is h.parent)

    def grid_init(grid):
        h.steps.append("grid_constructor")
        assert "grid_obj" not in vars(h.parent.caller)
        if h.failure == "grid_constructor":
            fail(h, "grid_constructor")
        grid.synthetic_ctor_completed = True

    def grid_method(grid, *args):
        h.steps.append("cell_grid_after_assignment")
        assert h.parent.caller.grid_obj is grid
        assert grid.synthetic_ctor_completed
        grid.cents_X = np.asarray([[0.25, 0.75], [0.25, 0.75]])
        grid.cents_Y = np.asarray([[0.25, 0.25], [0.75, 0.75]])
        grid.xy_cents = np.asarray([[0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]])
        grid.map_ij2k_cents = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]])
        if h.failure == "cell_grid":
            fail(h, "cell_grid")

    def tree_init(tree, data):
        h.steps.append("tree_constructor")
        tree.data = data
        tree.indices = np.asarray([0, 1])
        tree.mins, tree.maxes = np.asarray([0.0, 0.0]), np.asarray([1.0, 1.0])
        tree.n, tree.m, tree.leafsize, tree.boxsize = len(data), 2, 16, None
        if h.failure == "tree_constructor":
            fail(h, "tree_constructor")

    def query(tree, data, *a, **kw):
        h.steps.append("tree_query")
        if h.failure == "tree_query":
            fail(h, "tree_query")
        return np.asarray([0.0]), np.asarray([0])

    def ball(tree, data, *a, **kw):
        h.steps.append("tree_query_ball_point")
        if h.failure == "tree_query_ball_point":
            fail(h, "tree_query_ball_point")
        return [[0]]

    def interpolation(*a, **kw):
        h.steps.append("griddata")
        if h.failure == "griddata":
            fail(h, "griddata")
        return np.asarray([[0.0, 1.0], [1.0, 0.0]])

    def smoothing(value, *a, **kw):
        h.steps.append("gaussian_filter")
        if h.failure == "gaussian_filter":
            fail(h, "gaussian_filter")
        return value

    for name, fn in {
        "_INIT": grid_init,
        "_GRID": grid_method,
        "_TREE_INIT": tree_init,
        "_TREE_QUERY": query,
        "_TREE_BALL": ball,
        "_GRIDDATA": interpolation,
        "_GAUSSIAN": smoothing,
    }.items():
        monkeypatch.setattr(stage, name, fn)
    namespace = {}
    exec(
        compile(
            "def cellVerts(self,p):\n    probe('cellVerts',self,p)\n"
            "def cellMatrices(self,p):\n    logs.log_info('synthetic log')\n"
            "    probe('cellMatrices',self,p)\n"
            "def cell_vols(self,p):\n    probe('cell_vols',self,p)\n"
            "def mem_processing(self,p):\n    probe('mem_processing',self,p)\n"
            "def near_neigh(self,p):\n    probe('near_neigh',self,p)\n"
            "def makeECM(self,p):\n"
            "    probe('makeECM',self,p)\n"
            "    self.delta=1/p.grid_size\n"
            "    self.grid_obj=fd.FiniteDiffSolver()\n"
            "    self.grid_obj.cell_grid(self.delta,0,1,0,1)\n"
            "    probe('after_cell_grid',self,p)\n"
            "    self.X=self.grid_obj.cents_X\n    self.Y=self.grid_obj.cents_Y\n"
            "    self.xypts=self.grid_obj.xy_cents\n"
            "    self.map_ij2k=self.grid_obj.map_ij2k_cents\n"
            "    self.all_points_cell_i=self.cell_i\n"
            "    tree=cKDTree(self.xypts)\n    tree.query(self.xypts)\n"
            "    tree.query_ball_point(self.xypts,r=p.cell_space)\n"
            "def environment(self,p):\n"
            "    probe('environment',self,p)\n"
            "    self.points_tree=cKDTree(self.xypts)\n"
            "    self.points_tree.query(self.cell_centres)\n"
            "    self.ecm_sa=2.5\n    self.ecm_vol=1.25\n"
            "def assign_grid_len(self):\n    probe('assign_grid_len',self)\n"
            "    self.grid_len=len(self.xypts)\n"
            "def make_maskM(self,p):\n"
            "    probe('make_maskM',self,p)\n    tree=cKDTree(self.xypts)\n"
            "    tree.query(self.cell_centres)\n"
            "    self.maskM=interp.griddata(self.xypts,None,None)\n"
            "    self.maskM=gaussian_filter(self.maskM,1)\n"
            "    self.voronoi_centres=self.xypts\n",
            "<synthetic-multi-environment>",
            "exec",
        ),
        namespace,
    )
    monkeypatch.setattr(stage, "_METHODS", {name: namespace[name] for name in stage.METHODS})
    real_namespace = stage._namespace

    def namespaces(context):
        methods = real_namespace(context)
        for fn in methods.values():
            fn.__globals__["probe"] = probe
        return methods

    monkeypatch.setattr(stage, "_namespace", namespaces)
    h.continuation = stage.from_caller(h.owner, law_id=stage.LAW_ID)
    return h


def save_state(evidence, h, *, child=None, error=None):
    context = stage._authority(child) if child is not None else error.partial["context"]
    save(
        evidence,
        "state",
        dict(
            steps=h.steps,
            parent_trial=context.prior_trial.identity,
            trial=None if child is None else stage.trial_record(child.trial),
            raw_caller={
                k: v
                for k, v in vars(h.parent.caller).items()
                if k not in {"mesh", "grid_obj", "points_tree"}
            },
            raw_grid=None if context.grid is None else dict(vars(context.grid)),
            stage=context.stage,
            events=[name for name, _ in context.events],
            helper_names=[name for name, _ in context.helper_results],
            source_error=None if error is None else repr(error.source_error),
            capture_error=None if error is None else repr(error.capture_error),
            consumed=h.owner in multi._FORWARDED,
            usable_child=child is not None,
        ),
    )


def test_software_literal_sources_native_order_and_readonly_body_reuse(evidence):
    save(evidence, "source-pins", stage._verify_sources())
    assert stage.METHODS == (
        "cellVerts",
        "cellMatrices",
        "cell_vols",
        "mem_processing",
        "near_neigh",
        "makeECM",
        "environment",
        "assign_grid_len",
        "make_maskM",
    )
    assert len(multi.source.STORE_LINES) == 20
    assert multi.source.STORE_LINES[0] == 521
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "grid_size"
        for node in ast.walk(ast.parse(Path(multi.source.__file__).read_text()))
    )
    assert len(stage.INVALIDATED_OWNERS) == 11


def test_software_legacy_request_and_trial_remain_separate_and_factory_is_metadata_only(
    monkeypatch, evidence
):
    h = helpers.inputs()
    old = multi.request_record(h.request)
    fields_before = tuple(field.name for field in fields(multi.Request))
    monkeypatch.setattr(multi.atoms, "prepare_runtime", lambda *a: pytest.fail("native factory"))
    fresh = stage.from_lifecycle(h.lr, h.ls, h.conf, law_id=stage.LAW_ID)
    assert type(h.request) is multi.Request and fields_before == (
        "lifecycle_request",
        "lifecycle_state",
        "configuration_json",
        "identity",
    )
    assert type(fresh.caller_request) is multi.OrdinaryRequest
    assert fresh.caller_request.identity != h.request.identity
    assert multi.request_record(h.request) == old
    assert "selected_descriptor" not in old
    assert "descriptor_proof" not in {field.name for field in fields(multi.Trial)}
    save(evidence, "identities", dict(legacy=old, fresh=multi.request_record(fresh.caller_request)))


def test_software_descriptor_factory_precedes_parameter_and_caller_birth(monkeypatch, evidence):
    h = fixture(monkeypatch)
    assert h.steps[:4] == [
        "isolated_authentication",
        "descriptor_factory_before_birth",
        "parameter_stores_complete",
        "caller_birth",
    ]
    assert h.parent.p is not None and type(h.parent.p) is h.info.runtime
    assert h.parent.trial.descriptor_proof == h.parent.descriptor_proof
    assert "grid_size" not in vars(h.parent.p)
    with pytest.raises(ValueError, match="active owned"):
        _ = h.parent.p.grid_size
    save(
        evidence,
        "birth",
        dict(order=h.steps, proof=h.parent.descriptor_proof, parameter_stores=vars(h.parent.p)),
    )


def test_software_legacy_default_never_constructs_descriptor_or_gains_continuation(
    monkeypatch, evidence
):
    h = fixture(monkeypatch, legacy=True)
    assert "descriptor_factory_before_birth" not in h.steps
    assert type(h.parent.trial) is multi.Trial
    assert h.owner.cells is h.parent.caller
    with pytest.raises(stage.EnvironmentRejected) as wrong_mode:
        stage.from_caller(h.owner, law_id=stage.LAW_ID)
    assert wrong_mode.value.stage == "parameter_prerequisite"
    assert h.owner.cells is h.parent.caller
    h.parent.p.grid_size = 2  # Equal late scalar cannot supply descriptor provenance.
    with pytest.raises((stage.EnvironmentRejected, multi.MultiCellRejected)):
        stage.from_caller(h.owner, law_id=stage.LAW_ID)
    save(evidence, "legacy", multi.trial_record(h.parent.trial))


def test_software_descriptor_factory_failure_retains_original_typed_parents(monkeypatch, evidence):
    h = fixture(monkeypatch, failure="descriptor_factory")
    with pytest.raises(multi.MultiCellRejected) as caught:
        multi.prepare(h.request)
    error = caught.value
    assert error.source_error is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert error.partial["parameters"] is None and error.partial["caller"] is None
    assert error.partial["parent_trials"][0] is h.state
    save(
        evidence,
        "failure",
        dict(steps=h.steps, stage=error.stage, primary=repr(error.source_error)),
    )


def test_software_success_same_multi_caller_aliases_and_one_shot_retirement(monkeypatch, evidence):
    h = fixture(monkeypatch)
    parent_trial = h.owner.trial
    child = stage.prepare_continuation(h.continuation)
    context = stage._authority(child)
    assert child.cells is h.parent.caller and context.parent is h.parent
    assert h.parent.caller.mesh is h.parent.kernel
    assert context.parent.trial is parent_trial
    assert [name for name, _ in child.trial.stages] == list(stage.METHODS)
    assert h.steps.index("descriptor_read") < h.steps.index("grid_constructor")
    assert h.steps.index("grid_constructor") < h.steps.index("cell_grid_after_assignment")
    assert h.steps.index("cell_grid_after_assignment") < h.steps.index("after_cell_grid")
    assert h.steps.index("assign_grid_len") < h.steps.index("make_maskM")
    assert h.parent.caller.X is context.grid.cents_X
    assert h.parent.caller.xypts is context.grid.xy_cents
    assert h.parent.caller.voronoi_centres is context.grid.xy_cents
    assert "tree_query_ball_point" in h.steps
    assert child.trial.stream_after.identity == h.stream.identity
    with pytest.raises(multi.MultiCellRejected, match="consumed"):
        _ = h.owner.cells
    with pytest.raises(stage.EnvironmentRejected):
        stage.prepare_continuation(h.continuation)
    assert context.prior_trial is parent_trial
    save_state(evidence, h, child=child)


@pytest.mark.parametrize(
    "failure",
    [
        *stage.METHODS,
        "descriptor_read",
        "grid_constructor",
        "cell_grid",
        "tree_constructor",
        "tree_query",
        "tree_query_ball_point",
        "griddata",
        "gaussian_filter",
    ],
)
def test_software_source_failures_preserve_original_cause_partial_state_and_consumption(
    failure, monkeypatch, evidence
):
    h = fixture(monkeypatch, failure=failure)
    prior = h.owner.trial
    with pytest.raises(stage.EnvironmentRejected) as caught:
        stage.prepare_continuation(h.continuation)
    error = caught.value
    assert error.source_error is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert error.partial["parent_trial"] is prior
    assert error.partial["mesh"] is h.parent.kernel and error.partial["rng"] is h.rng
    assert error.partial["caller_consumed"] is True
    assert error.partial["usable_environment_child_available"] is False
    assert error.trial is not None and not error.trial.source_completed
    with pytest.raises(multi.MultiCellRejected, match="consumed"):
        _ = h.owner.cells
    if failure == "cell_grid":
        assert error.partial["caller"].grid_obj is error.partial["grid"]
        assert error.partial["grid"].xy_cents.shape == (4, 2)
    save_state(evidence, h, error=error)


@pytest.mark.parametrize("kind", ["enter", "return", "unwind"])
@pytest.mark.parametrize(
    "operation",
    [
        "grid_constructor",
        "cell_grid",
        "tree_constructor",
        "tree_query",
        "tree_query_ball_point",
        "griddata",
        "gaussian_filter",
    ],
)
def test_software_helper_observation_boundaries_do_not_execute_after_failed_enter_or_hide_primary(
    kind, operation, monkeypatch, evidence
):
    failure = operation if kind == "unwind" else None
    h = fixture(monkeypatch, failure=failure)
    capture = SyntheticCaptureFailure("synthetic observation " + operation + kind)
    actual = stage._observe

    def observe(context, name, raw):
        if name == operation + "_" + kind:
            stage.geometry._remember_observation_error(context, capture, origin=name, raw=raw)
        else:
            actual(context, name, raw)

    monkeypatch.setattr(stage, "_observe", observe)
    with pytest.raises(stage.EnvironmentRejected) as caught:
        stage.prepare_continuation(h.continuation)
    error = caught.value
    assert error.capture_error is capture
    if kind == "enter":
        assert operation not in h.steps
        if operation == "cell_grid":
            assert "cell_grid_after_assignment" not in h.steps
    elif kind == "unwind":
        assert error.source_error is h.errors["source"]
        assert error.source_error.__cause__ is h.errors["cause"]
    else:
        assert error.source_error is None
        assert error.partial["last_completed_helper"][0] == operation
        if operation == "cell_grid":
            assert "after_cell_grid" not in h.steps
    assert error.partial["caller_consumed"] and error.partial["parent_trial"] is h.parent.trial
    save_state(evidence, h, error=error)


@pytest.mark.parametrize("native_error", [False, True])
def test_software_local_observer_return_unwind_retains_profiler_and_primary(
    native_error, monkeypatch, evidence
):
    h = fixture(monkeypatch, failure="cell_grid" if native_error else None)
    capture = SyntheticCaptureFailure("synthetic locals capture")
    actual = stage.geometry._capture_locals

    def capture_locals(context, name, frame):
        if name == "cell_grid":
            raise capture
        actual(context, name, frame)

    monkeypatch.setattr(stage.geometry, "_capture_locals", capture_locals)
    previous = sys.getprofile()
    with pytest.raises(stage.EnvironmentRejected) as caught:
        stage.prepare_continuation(h.continuation)
    assert sys.getprofile() is previous
    error = caught.value
    assert error.capture_error is capture
    assert error.source_error is (h.errors["source"] if native_error else None)
    assert error.partial["observation_raw"] is not None
    assert "after_cell_grid" not in h.steps
    save_state(evidence, h, error=error)


@pytest.mark.parametrize("point", ["namespace", "sealing", "issuance", "log"])
def test_software_capture_failures_never_issue_or_rearm_parent(point, monkeypatch, evidence):
    h = fixture(monkeypatch)
    error = SyntheticCaptureFailure("synthetic " + point)
    if point == "namespace":
        monkeypatch.setattr(stage, "_namespace", lambda context: (_ for _ in ()).throw(error))
    elif point == "sealing":
        monkeypatch.setattr(stage, "trial_record", lambda *a: (_ for _ in ()).throw(error))
    elif point == "issuance":
        monkeypatch.setattr(stage, "_graphs", lambda *a: (_ for _ in ()).throw(error))
    else:
        actual = stage.geometry._Logs.log_info

        def logging(self, *args):
            stage.geometry._remember_observation_error(
                self.context, error, origin="log_info", raw=args
            )
            return None

        assert actual is not logging
        monkeypatch.setattr(stage.geometry._Logs, "log_info", logging)
    with pytest.raises(stage.EnvironmentRejected) as caught:
        stage.prepare_continuation(h.continuation)
    rejected = caught.value
    assert rejected.partial["parent_trial"] is h.parent.trial
    assert h.owner in multi._FORWARDED
    assert rejected.partial["usable_environment_child_available"] is False
    assert rejected.capture_error is error or rejected.source_error is error
    save_state(evidence, h, error=rejected)


@pytest.mark.parametrize(
    "kind",
    [
        "mesh_binding",
        "caller_binding",
        "observer",
        "RNG_observer",
        "RNG",
        "grid_alias",
        "array_alias",
        "tree_alias",
        "math",
        "helper",
        "log_context",
        "descriptor_dispatch",
        "read_callback",
    ],
)
def test_software_completed_owner_refuses_alias_callable_helper_and_epoch_drift(
    kind, monkeypatch, evidence
):
    h = fixture(monkeypatch)
    child = stage.prepare_continuation(h.continuation)
    context = stage._authority(child)
    before = stage._snapshot(context).identity
    if kind == "mesh_binding":
        monkeypatch.setattr(multi._Runtime, "create_core_operators", lambda self: None)
    elif kind == "caller_binding":
        monkeypatch.setattr(multi._Caller, "cell_index", lambda self, p: None)
    elif kind == "observer":
        h.parent.kernel._cells_observer = SimpleNamespace()
    elif kind == "RNG_observer":
        h.parent.kernel._cells_rng.observer = SimpleNamespace()
    elif kind == "RNG":
        h.rng.epoch += 1
    elif kind == "grid_alias":
        h.parent.caller.X = h.parent.caller.X.copy()
    elif kind == "array_alias":
        caller = h.parent.caller
        caller.references[0] = caller.equal_reference
        assert stage._snapshot(context).identity == before
    elif kind == "tree_alias":
        h.parent.caller.points_tree = context.trees[0]
    elif kind == "math":
        monkeypatch.setattr(
            stage.geometry.source.math, "pi", np.float64(stage.geometry.source.math.pi)
        )
    elif kind == "helper":
        monkeypatch.setattr(
            context.methods["make_maskM"].__globals__["interp"], "griddata", lambda *a: None
        )
    elif kind == "log_context":
        context.methods["cellMatrices"].__globals__["logs"].context = SimpleNamespace(logs=[])
    elif kind == "descriptor_dispatch":
        runtime = type(h.parent.p)
        monkeypatch.setattr(
            runtime,
            "__getattribute__",
            lambda self, name: 2 if name == "grid_size" else object.__getattribute__(self, name),
        )
    else:
        context.observe = lambda *args: None
    with pytest.raises(stage.EnvironmentRejected) as caught:
        _ = child.cells
    assert context.invalid and caught.value.trial is child.trial
    save(
        evidence,
        "drift",
        dict(
            kind=kind,
            error=repr(caught.value.source_error),
            scalar_cache_equal=stage._snapshot(context).identity == before
            if kind != "math"
            else None,
        ),
    )


def test_software_actual_descriptor_read_is_required_before_constructor(monkeypatch, evidence):
    h = fixture(monkeypatch)
    real_namespace = stage._namespace

    def namespace(context):
        methods = real_namespace(context)
        native = methods["makeECM"]
        values = dict(native.__globals__)
        exec(
            compile(
                "def bypass(self,p):\n    self.grid_obj=fd.FiniteDiffSolver()\n",
                "<synthetic-no-descriptor>",
                "exec",
            ),
            values,
        )
        methods["makeECM"] = values["bypass"]
        return methods

    monkeypatch.setattr(stage, "_namespace", namespace)
    with pytest.raises(stage.EnvironmentRejected) as caught:
        stage.prepare_continuation(h.continuation)
    assert "read did not enter" in str(caught.value.source_error)
    assert "grid_constructor" not in h.steps and "grid_obj" not in vars(h.parent.caller)
    save_state(evidence, h, error=caught.value)


def test_software_reentrant_attempt_refuses_without_reopening_consumed_parent(
    monkeypatch, evidence
):
    h = fixture(monkeypatch)
    failures = []

    def reenter(_context):
        with pytest.raises(stage.EnvironmentRejected) as caught:
            stage.prepare_continuation(h.continuation)
        failures.append(caught.value)

    h.continuation_controls["environment"] = reenter
    child = stage.prepare_continuation(h.continuation)
    assert len(failures) == 1 and child.cells is h.parent.caller
    save_state(evidence, h, child=child)


def test_software_raw_success_and_failure_grid_tree_native_methods_and_checkpoint_refuse(
    monkeypatch, evidence
):
    h = fixture(monkeypatch)
    child = stage.prepare_continuation(h.continuation)
    context = stage._authority(child)
    for operation in (
        lambda: context.grid.__init__(),
        lambda: context.grid.cell_grid(1, 0, 1, 0, 1),
        lambda: context.grid.makeLaplacian(),
        lambda: context.trees[0].query([]),
        lambda: context.trees[0].query_ball_point([], 1),
        lambda: context.trees[0].__init__([]),
        lambda: context.trees[0].tree,
        lambda: pickle.dumps(child),
        lambda: pickle.dumps(context.grid),
        lambda: pickle.dumps(context.trees[0]),
        lambda: stage.require_Poisson(child),
    ):
        with pytest.raises((stage.EnvironmentRejected, TypeError)):
            operation()
    save_state(evidence, h, child=child)


def test_software_full_prefix_work_composition_is_complete_once_and_refusal_keeps_failed_work(
    monkeypatch, evidence
):
    h = fixture(monkeypatch)
    request = stage.Request(
        h.request, stage.core.records._digest(dict(law=stage.LAW_ID, caller=h.request.identity))
    )
    parent_work = (
        dict(
            sequence=0,
            phase="isolated_authentication",
            entry_method="pre_mesh",
            status="entered_not_success_credit",
        ),
        dict(
            sequence=1,
            phase="actual_mesh",
            entry_method="create_core_operators",
            status="entered_not_success_credit",
        ),
    )
    trial = replace(h.parent.trial, work=parent_work, identity="")
    h.parent.trial = replace(trial, identity=core_digest(multi.trial_record(trial)))
    monkeypatch.setattr(multi, "prepare", lambda candidate: h.owner)
    child = stage.prepare(request)
    rows = child.trial.work
    assert [row["entry_method"] for row in rows[:2]] == ["pre_mesh", "create_core_operators"]
    assert [row["sequence"] for row in rows] == list(range(len(rows)))
    assert all(row["component"] == "multi_caller_prefix" for row in rows[:2])
    assert sum(row.get("component") == "multi_caller_prefix" for row in rows) == 2
    assert any(row["entry_method"] == "_invoke_method" for row in rows[2:])
    save_state(evidence, h, child=child)


def core_digest(value):
    return stage.core.records._digest(value)


@pytest.mark.parametrize(
    "kind",
    [
        "parameter",
        "parameter_equal_graph",
        "mesh",
        "RNG",
        "original_caller",
        "original_caller_equal_alias",
    ],
)
def test_software_parent_immutable_authority_cannot_change_inside_continuation(
    kind, monkeypatch, evidence
):
    h = fixture(monkeypatch)

    def mutate(_context):
        parent = h.parent
        if kind == "parameter":
            parent.p.cell_space += 1.0
        elif kind == "parameter_equal_graph":
            old = parent.p._conf["world options"]
            parent.p._conf["world options"] = dict(old)
        elif kind == "mesh":
            parent.kernel.vor_verts[0, 0] += 1.0
        elif kind == "RNG":
            h.rng.epoch += 1
        elif kind == "original_caller":
            parent.caller.bbox[0, 0] += 1.0
        else:
            parent.caller.bbox = parent.caller.bbox.copy()

    h.continuation_controls["environment"] = mutate
    with pytest.raises(stage.EnvironmentRejected) as caught:
        stage.prepare_continuation(h.continuation)
    error = caught.value
    assert error.source_error is not None
    assert error.partial["parent_trial"] is h.parent.trial
    assert h.owner in multi._FORWARDED
    assert "make_maskM" not in h.steps
    save_state(evidence, h, error=error)


def test_software_failed_prefix_work_is_not_lost_by_outer_retention(monkeypatch, evidence):
    h = helpers.inputs()
    request = stage.from_lifecycle(h.lr, h.ls, h.conf, law_id=stage.LAW_ID)
    work = [
        dict(
            sequence=0,
            phase="isolated_authentication",
            entry_method="pre_mesh",
            status="entered_not_success_credit",
        )
    ]
    source = multi.MultiCellRejected(
        "synthetic prefix refusal",
        stage="initial",
        request=request,
        partial=dict(work=work, initial_state=h.state),
    )

    def refusal(candidate):
        raise source

    monkeypatch.setattr(multi, "prepare", refusal)
    with pytest.raises(stage.EnvironmentRejected) as caught:
        stage.prepare(request)
    assert caught.value.source_error is source
    assert caught.value.partial["work"] == work
    assert caught.value.partial["source_partial"] is source.partial
    assert source.partial["initial_state"] is h.state
    save(evidence, "failed-work", dict(work=caught.value.partial["work"], stage=source.stage))


def test_software_mask_bridge_integration_same_fresh_descriptor_caller_through_environment(
    monkeypatch, evidence
):
    h = fixture(monkeypatch, native_mask_layout=True)
    caller, mesh, p, mask, rng = h.parent.caller, h.parent.kernel, h.parent.p, h.mask, h.rng
    prior = h.owner.trial
    assert type(h.request) is multi.OrdinaryRequest and type(prior) is multi.OrdinaryTrial
    assert type(p) is h.info.runtime and "grid_size" not in vars(p)
    assert h.steps.index("descriptor_factory_before_birth") < h.steps.index("caller_birth")
    assert mask.clipping_matrix is h.live_view and h.live_view.base is h.live_base
    assert h.parent.mask_token_comparisons
    assert all(
        proof["actual_matrix_layout"]["strides_bytes"] == [-16, 8]
        for proof in h.parent.mask_token_comparisons
    )
    child = stage.prepare_continuation(h.continuation)
    context = stage._authority(child)
    assert child.cells is caller and context.parent is h.parent
    assert context.prior_trial is prior
    assert context.parent.p is p and context.parent.rng is rng
    assert caller.mesh is mesh and mesh.image_mask is mask
    assert caller.cluster_mask is mask.clipping_matrix is h.live_view
    assert h.live_view.base is h.live_base and h.live_view.strides == (-16, 8)
    assert context.parameter_info is h.info
    assert context.descriptor_read_instance is context.descriptor_read_return_instance is p
    assert caller.grid_obj is context.grid and caller.xypts is context.grid.xy_cents
    assert caller.voronoi_centres is caller.xypts
    assert [name for name, _ in child.trial.stages] == list(stage.METHODS)
    assert h.owner in multi._FORWARDED
    save_state(evidence, h, child=child)
    save(
        evidence,
        "mask-bridge-lineage",
        dict(
            parent_trial=multi.trial_record(prior),
            comparisons=h.parent.mask_token_comparisons,
            live_matrix=h.live_view,
            live_layout=stage.core.caches.layout(h.live_view),
            retained_token_layout=stage.core.caches.layout(h.stored),
            descriptor_proof=prior.descriptor_proof,
        ),
    )


@pytest.mark.parametrize("failure", ["descriptor_read", "cell_grid"])
def test_software_mask_bridge_integration_failure_retains_flipped_mask_and_consumed_parent(
    failure, monkeypatch, evidence
):
    h = fixture(monkeypatch, native_mask_layout=True, failure=failure)
    prior = h.owner.trial
    with pytest.raises(stage.EnvironmentRejected) as caught:
        stage.prepare_continuation(h.continuation)
    error = caught.value
    assert error.source_error is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert error.partial["parent_trial"] is prior
    assert error.partial["parameters"] is h.parent.p
    assert error.partial["mask"] is h.mask and error.partial["mesh"] is h.parent.kernel
    assert h.parent.kernel.image_mask is h.mask
    assert h.parent.caller.cluster_mask is h.mask.clipping_matrix is h.live_view
    assert h.live_view.base is h.live_base and h.live_view.strides == (-16, 8)
    assert h.parent.mask_token_comparisons
    assert error.partial["caller_consumed"] is True
    assert error.partial["usable_environment_child_available"] is False
    assert not error.trial.source_completed
    with pytest.raises(multi.MultiCellRejected, match="consumed"):
        _ = h.owner.cells
    save_state(evidence, h, error=error)
    save(evidence, "retained-primary", error.source_error)
    save(evidence, "retained-mask-bridge", h.parent.mask_token_comparisons)


def test_software_mask_bridge_integration_equal_flipped_view_retarget_refuses_without_value_change(
    monkeypatch, evidence
):
    h = fixture(monkeypatch, native_mask_layout=True)
    child = stage.prepare_continuation(h.continuation)
    context = stage._authority(child)
    before = stage._snapshot(context).identity
    original = h.mask.clipping_matrix
    equal_view = h.live_base[::-1]
    assert equal_view is not original and equal_view.base is original.base
    assert stage.core.caches.layout(equal_view) == stage.core.caches.layout(original)
    assert equal_view.tobytes() == original.tobytes()
    h.mask.clipping_matrix = h.parent.caller.cluster_mask = equal_view
    assert stage._snapshot(context).identity == before
    with pytest.raises(stage.EnvironmentRejected) as caught:
        _ = child.cells
    assert context.invalid and caught.value.trial is child.trial
    save(
        evidence,
        "equal-view-retarget",
        dict(
            error=caught.value.source_error,
            cache_unchanged=True,
            original_layout=stage.core.caches.layout(original),
            equal_layout=stage.core.caches.layout(equal_view),
        ),
    )


def frozen_execution_fixture(tmp_path):
    from validation.betse import betse_native_multi_cell_environment_software as software

    repository = tmp_path / "synthetic-repository"
    repository.mkdir()

    def git(*args):
        return subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgSign=false",
                "-c",
                "user.name=Snapshot Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                *args,
            ],
            cwd=repository,
            check=True,
            capture_output=True,
            env=dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null"),
        )

    git("init", "--quiet")
    name = "src/cells/fixture.py"
    source = repository / name
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n")
    git("add", "--", name)
    git("commit", "--quiet", "-m", "synthetic source")
    output = tmp_path / "execution-output"
    output.mkdir()
    frozen = output / "tested-source"
    snapshot = software.runner.source_snapshot.freeze(repository, frozen, {name: name})
    manifest_sha = software.runner.source_snapshot.digest(frozen / "SNAPSHOT.json")
    runtime = output / "runtime-producers.json"
    producers = {
        key: dict(path=str(frozen / name), sha256=snapshot["files"][name]["sha256"])
        for key in ("cells", software.runner.__name__, Path(software.TEST).stem)
    }
    runtime.write_text(json.dumps(producers))
    return SimpleNamespace(
        software=software,
        git=git,
        repository=repository,
        source=source,
        name=name,
        output=output,
        frozen=frozen,
        runtime=runtime,
        snapshot=snapshot,
        manifest_sha=manifest_sha,
        producers=producers,
    )


def test_software_frozen_execution_unchanged_source_and_integration_are_distinct(
    tmp_path, evidence
):
    h = frozen_execution_fixture(tmp_path)
    authority = h.software.verify_frozen_execution(h.frozen, h.manifest_sha, h.runtime)
    integration = h.software.checkout_integration_status(h.frozen, h.output)
    assert authority["current_checkout_used_as_execution_authority"] is False
    assert authority["verified_loaded_producers"] == 3
    assert integration["integration_pending"] is False
    assert integration["explicit_later_integration_check_required"] is False
    save(evidence, "frozen-execution", dict(authority=authority, integration=integration))


def test_software_frozen_execution_unrelated_head_change_does_not_fail_frozen_result(
    tmp_path, evidence
):
    h = frozen_execution_fixture(tmp_path)
    (h.repository / "unrelated.txt").write_text("unrelated committed metadata\n")
    h.git("add", "--", "unrelated.txt")
    h.git("commit", "--quiet", "-m", "unrelated change")
    with pytest.raises(ValueError, match="Git revision"):
        h.software.runner.source_snapshot.assert_checkout_unchanged(h.frozen)
    authority = h.software.verify_frozen_execution(h.frozen, h.manifest_sha, h.runtime)
    integration = h.software.checkout_integration_status(h.frozen, h.output)
    assert authority["frozen_git_revision"] == h.snapshot["git_revision"]
    assert integration["current_git_revision"] != authority["frozen_git_revision"]
    assert integration["integration_pending"] and integration["checkout_bookkeeping_drift"]
    assert integration["selected_source_drift"] == []
    assert integration["explicit_later_integration_check_required"] is False
    assert integration["selected_current_snapshot"] is None
    assert integration["frozen_execution_result_changed"] is False
    save(evidence, "unrelated-head", dict(authority=authority, integration=integration))


def test_software_frozen_execution_selected_drift_keeps_both_unexecuted_and_executed_bytes(
    tmp_path, evidence
):
    h = frozen_execution_fixture(tmp_path)
    h.source.write_text("VALUE = 2\n")
    authority = h.software.verify_frozen_execution(h.frozen, h.manifest_sha, h.runtime)
    integration = h.software.checkout_integration_status(h.frozen, h.output)
    assert integration["integration_pending"]
    assert integration["explicit_later_integration_check_required"]
    assert len(integration["selected_source_drift"]) == 1
    assert (
        integration["selected_source_drift"][0]["frozen_sha256"]
        != integration["selected_source_drift"][0]["current_sha256"]
    )
    assert (h.frozen / h.name).read_text() == "VALUE = 1\n"
    current = integration["selected_current_snapshot"]
    assert current["executed"] is False
    new_root = Path(current["path"]).parent
    h.software.runner.source_snapshot.verify(new_root, manifest_sha256=current["sha256"])
    assert (new_root / h.name).read_text() == "VALUE = 2\n"
    assert authority["snapshot_manifest_sha256"] == h.manifest_sha
    assert integration["frozen_execution_result_changed"] is False
    save(evidence, "selected-drift", dict(authority=authority, integration=integration))


@pytest.mark.parametrize("kind", ["missing", "linked", "ignored"])
def test_software_frozen_execution_invalid_current_source_cannot_gain_integration_credit(
    kind, tmp_path, evidence
):
    h = frozen_execution_fixture(tmp_path)
    if kind == "missing":
        h.source.unlink()
    elif kind == "linked":
        other = h.repository / "other.txt"
        other.write_text("VALUE = 3\n")
        h.source.unlink()
        h.source.symlink_to(other)
    else:
        (h.repository / ".gitignore").write_text("src/\n")
    authority = h.software.verify_frozen_execution(h.frozen, h.manifest_sha, h.runtime)
    integration = h.software.checkout_integration_status(h.frozen, h.output)
    assert authority["snapshot_manifest_sha256"] == h.manifest_sha
    assert integration["integration_pending"]
    assert integration["explicit_later_integration_check_required"]
    assert integration["selected_source_drift"] or integration["checkout_source_policy_error"]
    assert integration["selected_current_snapshot"] is None
    assert integration["selected_current_snapshot_error"] is not None
    assert (h.frozen / h.name).read_text() == "VALUE = 1\n"
    save(
        evidence,
        "invalid-current-source",
        dict(kind=kind, authority=authority, integration=integration),
    )


@pytest.mark.parametrize(
    "kind", ["payload", "manifest", "producer_hash", "producer_escape", "producer_missing"]
)
def test_software_frozen_execution_corrupt_payload_manifest_or_loaded_producer_refuses(
    kind, tmp_path, evidence
):
    h = frozen_execution_fixture(tmp_path)
    if kind in {"payload", "manifest"}:
        path = h.frozen / (h.name if kind == "payload" else "SNAPSHOT.json")
        path.chmod(0o644)
        path.write_text("VALUE = 9\n" if kind == "payload" else "{}\n")
        path.chmod(0o444)
    else:
        producers = h.producers
        if kind == "producer_hash":
            producers["cells"]["sha256"] = "0" * 64
        elif kind == "producer_escape":
            producers["cells"]["path"] = str(h.source)
        else:
            del producers[Path(h.software.TEST).stem]
        h.runtime.write_text(json.dumps(producers))
    with pytest.raises(ValueError) as caught:
        h.software.verify_frozen_execution(h.frozen, h.manifest_sha, h.runtime)
    save(evidence, "invalid-execution-evidence", dict(kind=kind, error=caught.value))


@pytest.mark.parametrize("phase", ["before_grid", "completed_owner"])
@pytest.mark.parametrize("helper", ["linspace", "meshgrid", "column_stack", "asarray"])
def test_software_grid_original_numpy_replacement_refuses_with_copied_namespaces_unchanged(
    phase, helper, monkeypatch, evidence
):
    h = fixture(monkeypatch, native_mask_layout=True)
    original_numpy, called = stage.ecm_source.np, []
    retained = {}

    def forbidden(*args, **kwargs):
        called.append(helper)
        raise AssertionError("Replaced original-grid helper must never execute")

    def replace_original_namespace(context):
        copied = stage._namespace_bindings(context)
        make_numpy = context.methods["makeECM"].__globals__["np"]
        geometry_numpy = context.methods["cellVerts"].__globals__["np"]
        proxy = SimpleNamespace(
            **{name: getattr(original_numpy, name) for name in stage._GRID_HELPERS}
        )
        setattr(proxy, helper, forbidden)
        monkeypatch.setattr(stage.ecm_source, "np", proxy)
        assert context.methods["makeECM"].__globals__["np"] is make_numpy
        assert context.methods["cellVerts"].__globals__["np"] is geometry_numpy
        assert stage.geometry.source.np is original_numpy
        multi.accounting._check_binding_identity(stage._namespace_bindings(context), copied)
        retained.update(context=context, copied_namespaces_unchanged=True)

    if phase == "before_grid":
        original_cell_grid = stage._GridRuntime.cell_grid

        def enter_grid(grid, *args):
            context = stage._GRIDS[grid]
            assert h.parent.caller.grid_obj is grid
            replace_original_namespace(context)
            return original_cell_grid(grid, *args)

        monkeypatch.setattr(stage._GridRuntime, "cell_grid", enter_grid)
        with pytest.raises(stage.EnvironmentRejected) as caught:
            stage.prepare_continuation(h.continuation)
        error = caught.value
        assert "cell_grid_after_assignment" not in h.steps
        assert "after_cell_grid" not in h.steps
        assert error.partial["grid"] is h.parent.caller.grid_obj
        assert error.partial["parent_trial"] is h.parent.trial
        assert error.partial["caller_consumed"]
        save_state(evidence, h, error=error)
    else:
        child = stage.prepare_continuation(h.continuation)
        context = stage._authority(child)
        before = stage._snapshot(context).identity
        replace_original_namespace(context)
        assert stage._snapshot(context).identity == before
        with pytest.raises(stage.EnvironmentRejected) as caught:
            _ = child.cells
        assert context.invalid and caught.value.trial is child.trial
        save(evidence, "completed-owner-refusal", caught.value.source_error)
    assert called == [] and retained["copied_namespaces_unchanged"]
    assert h.mask.clipping_matrix is h.live_view
    save(
        evidence,
        "original-grid-namespace",
        dict(
            phase=phase,
            helper=helper,
            delegates_called=called,
            copied_namespaces_unchanged=True,
            live_layout=stage.core.caches.layout(h.live_view),
        ),
    )


@pytest.mark.parametrize("helper", ["linspace", "meshgrid", "column_stack"])
def test_software_grid_original_numpy_wrapped_implementation_code_drift_refuses(
    helper, monkeypatch, evidence
):
    h = fixture(monkeypatch, native_mask_layout=True)
    child = stage.prepare_continuation(h.continuation)
    context = stage._authority(child)
    copied = stage._namespace_bindings(context)
    numpy = stage.ecm_source.np
    function = getattr(numpy, helper)
    implementation = function.__wrapped__

    def forbidden(*args, **kwargs):
        raise AssertionError("Changed grid implementation code must never execute")

    replacement = forbidden.__code__.replace(co_freevars=implementation.__code__.co_freevars)
    monkeypatch.setattr(implementation, "__code__", replacement)
    assert stage.ecm_source.np is numpy and getattr(numpy, helper) is function
    multi.accounting._check_binding_identity(stage._namespace_bindings(context), copied)
    with pytest.raises(stage.EnvironmentRejected) as caught:
        _ = child.cells
    assert context.invalid and caught.value.trial is child.trial
    save(
        evidence,
        "grid-implementation-code-refusal",
        dict(
            helper=helper,
            callable_object_unchanged=True,
            copied_namespace_atoms_unchanged=True,
            error=caught.value.source_error,
        ),
    )
