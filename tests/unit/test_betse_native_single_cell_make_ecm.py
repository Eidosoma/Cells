"""Counterfactual live makeECM ownership; actual native work is forbidden."""

import ast
import hashlib
import os
import pickle
import runpy
import sys
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_make_ecm as ecm
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
        Path(os.environ.get("CELLS_MAKE_ECM_EVIDENCE", str(tmp_path)))
        / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    )
    path.mkdir(parents=True, exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def harness(monkeypatch, tmp_path, *, failure=None, grid_size=4):
    helper = runpy.run_path(
        str(ROOT / "tests/unit/test_betse_native_single_cell_initial_geometry.py")
    )
    h = helper["harness"](monkeypatch, tmp_path)
    events, errors = [], {}
    original_geometry_namespace = ecm.geometry._namespace

    def geometry_namespace(context):
        methods = original_geometry_namespace(context)
        first = methods["cellVerts"]

        def cell_verts(cells, p):
            first(cells, p)
            cells.cell_i = [0, 1]

        methods["cellVerts"] = FunctionType(
            cell_verts.__code__,
            first.__globals__,
            cell_verts.__name__,
            closure=cell_verts.__closure__,
        )
        return methods

    monkeypatch.setattr(ecm.geometry, "_namespace", geometry_namespace)

    def fail(stage):
        if failure == stage:
            try:
                raise SyntheticSourceCause("original synthetic makeECM cause")
            except SyntheticSourceCause as cause:
                error = SyntheticSourceFailure("synthetic source failure at " + stage)
                errors.update(source=error, cause=cause)
                raise error from cause

    class Descriptor:
        def __init__(self):
            self.expr_alias_cls = int

        def __get__(self, p, owner):
            if p is None:
                return self
            events.append("descriptor_read")
            fail("descriptor_read")
            value = p._conf["general options"]["comp grid size"]
            if not isinstance(value, int):
                raise SyntheticSourceFailure("native non-castable int rejection stand-in")
            return value

        def __set__(self, p, value):
            raise AssertionError("Selected getter control must not enter native setter")

    def descriptor():
        events.append("descriptor_factory_before_parameters")
        assert not h.upstream.events
        fail("descriptor_factory")
        return SimpleNamespace(
            native=Descriptor(),
            factories=(descriptor,),
            modules={},
            pins=ecm.aliases.source_pins(),
            occurrence=(-1, -1, Descriptor.__name__),
        )

    monkeypatch.setattr(ecm.aliases, "_descriptor_from_source", descriptor)
    monkeypatch.setattr(ecm, "_verify_sources", lambda: dict(h.upstream.pins))
    config = {
        "world options": {"cell height": "2.5", "cell spacing": "0.25"},
        "general options": {"comp grid size": grid_size},
    }
    request = ecm.from_core(h.upstream.parent, config, law_id=ecm.LAW_ID)

    def init(grid):
        events.append("constructor_body")
        grid.constructor_seen = "counterfactual"
        fail("constructor")

    def cell_grid(grid, *args):
        events.append("cell_grid_body")
        assert grid is ecm._GRIDS[grid].parent.parent.caller.grid_obj
        grid.arguments = args
        grid.cents_X = np.asarray([[0.5]])
        grid.cents_Y = np.asarray([[0.5]])
        grid.xy_cents = np.asarray([[0.5, 0.5]])
        grid.map_ij2k_cents = np.asarray([[0, 0]])
        grid.equal_reference = grid.cents_X
        fail("cell_grid")

    values = dict(ecm.source.__dict__, init=init, step=cell_grid)
    exec(
        compile(
            "def __init__(self):\n    init(self)\ndef cell_grid(self,*args):\n    step(self,*args)",
            "<synthetic-ECM-grid>",
            "exec",
        ),
        values,
    )
    monkeypatch.setattr(ecm, "_INIT", values["__init__"])
    monkeypatch.setattr(ecm, "_GRID", values["cell_grid"])
    values = dict(ecm.source.__dict__)
    exec(compile("def makeECM(self,p):\n    step(self,p)", "<synthetic-makeECM>", "exec"), values)
    monkeypatch.setattr(ecm, "_MAKE", values["makeECM"])
    original_namespace = ecm._namespace

    def namespace(context):
        method = original_namespace(context)

        def step(cells, p):
            value = p.grid_size
            events.append("delta_after_descriptor")
            cells.delta = (cells.xmax - cells.xmin) / value
            grid = method.__globals__["fd"].FiniteDiffSolver()
            events.append("constructor_return_before_assignment")
            fail("assignment")
            cells.grid_obj = grid
            events.append("assignment")
            grid.cell_grid(cells.delta, cells.xmin, cells.xmax, cells.ymin, cells.ymax)
            cells.X, cells.Y = grid.cents_X, grid.cents_Y
            cells.xypts, cells.map_ij2k = grid.xy_cents, grid.map_ij2k_cents
            cells.index_k = [0]
            fail("rounding")
            cells.ecm_points = np.asarray([[0.5, 0.5]])
            cells.bflags_ecm = np.asarray([0])
            cells.ecm_i = np.asarray([0])
            fail("tree")
            fail("object_array")
            cells.mem_to_ecm = np.asarray([0, 0])
            cells.cell_to_ecm = np.empty(2, dtype=object)
            cells.cell_to_ecm[0] = [0]
            cells.cell_to_ecm[1] = [0]
            cells.all_points = np.asarray([[0.5, 0.5], [1.5, 0.5], [0.5, 0.5]])
            cells.all_points_imap = np.asarray([0, 1, 0])
            cells.all_i = np.asarray([0, 1, 2])
            cells.all_points_ecm_i = np.asarray([2])
            cells.all_points_cell_i = cells.cell_i
            cells.adl = 3
            cells.ecm_to_mems = np.empty(1, dtype=object)
            cells.ecm_to_mems[0] = [0, 1]
            cells.ecm_to_cells = np.empty(1, dtype=object)
            cells.ecm_to_cells[0] = np.asarray([0, 1])
            cells.ecm_vol, cells.ecm_sa = np.asarray([0.25]), np.asarray([1.0])
            cells.ecmdl = 1
            fail("makeECM")

        method.__globals__["step"] = step
        return method

    monkeypatch.setattr(ecm, "_namespace", namespace)
    return SimpleNamespace(h=h, request=request, events=events, errors=errors)


def parent(h):
    return ecm.geometry.prepare(h.request.geometry_request)


def test_software_literal_bodies_descriptor_declaration_and_ordinary_order(evidence):
    save(evidence, "pins", ecm._verify_sources())
    native = ast.parse((ecm.aliases.NATIVE / "betse/science/parameters.py").read_text())
    cls = next(n for n in native.body if isinstance(n, ast.ClassDef) and n.name == "Parameters")
    declaration = next(n for n in cls.body if isinstance(n, ast.Assign) and n.lineno == 390)
    assert ast.dump(declaration) == ast.dump(
        ast.parse("grid_size = yaml_alias(\"['general options']['comp grid size']\", int)").body[0]
    )
    cells = ast.parse((ecm.aliases.NATIVE / "betse/science/cells.py").read_text())
    cls = next(n for n in cells.body if isinstance(n, ast.ClassDef) and n.name == "Cells")
    world = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "make_world")
    calls = [
        n.func.attr
        for n in ast.walk(world)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ]
    assert calls.index("makeECM") < calls.index("environment") < calls.index("make_maskM")
    assert ecm.aliases.specification()["castable"] is False


def test_software_fresh_descriptor_same_parameter_caller_grid_aliases_and_work(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = ecm.prepare(h.request)
    context = ecm._authority(owner)
    cells = owner.cells
    assert h.events == [
        "descriptor_factory_before_parameters",
        "descriptor_read",
        "delta_after_descriptor",
        "constructor_body",
        "constructor_return_before_assignment",
        "assignment",
        "cell_grid_body",
    ]
    assert context.parent.parent.p is h.h.upstream.state.p
    assert "grid_size" not in vars(context.parent.parent.p)
    assert cells.grid_obj is context.grid
    assert cells.X is context.grid.cents_X and cells.Y is context.grid.cents_Y
    assert cells.xypts is context.grid.xy_cents and cells.map_ij2k is context.grid.map_ij2k_cents
    assert cells.all_points_cell_i is cells.cell_i
    assert (
        owner.trial.source_completed
        and owner.trial.stream_before.identity == owner.trial.stream_after.identity
    )
    assert {"makeECM", "__init__", "cell_grid"}.issubset(
        {e["entry_method"] for e in owner.trial.work}
    )
    assert any(
        e["phase"] == "cell_grid" and e["entry_method"] == "cell_grid" for e in owner.trial.work
    )
    assert owner.cells is cells
    save(evidence, "trial", owner.trial)


def test_software_legacy_geometry_cannot_be_retrofitted(monkeypatch, tmp_path, evidence):
    helper = runpy.run_path(
        str(ROOT / "tests/unit/test_betse_native_single_cell_initial_geometry.py")
    )
    h = helper["harness"](monkeypatch, tmp_path)
    owner = ecm.geometry.prepare(h.request)
    with pytest.raises(ecm.EcmRejected) as caught:
        ecm.from_geometry(owner, law_id=ecm.LAW_ID)
    assert caught.value.stage == "grid_descriptor_prerequisite"
    assert owner not in ecm.geometry._FORWARDED
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize(
    "stage",
    [
        "descriptor_read",
        "constructor",
        "assignment",
        "cell_grid",
        "rounding",
        "tree",
        "object_array",
        "makeECM",
    ],
)
def test_software_source_failures_retain_primary_partial_and_irreversible_claim(
    stage, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure=stage)
    before = parent(h)
    request = ecm.from_geometry(before, law_id=ecm.LAW_ID)
    with pytest.raises(ecm.EcmRejected) as caught:
        ecm.prepare_continuation(request)
    error = caught.value
    save(evidence, "failure", error)
    assert (
        error.source_error is h.errors["source"]
        and error.source_error.__cause__ is h.errors["cause"]
    )
    assert error.partial["parent_trial"] is before.trial
    assert error.partial["geometry_consumed"] and not error.partial["usable_ecm_child_available"]
    assert not error.trial.source_completed
    if stage != "descriptor_read":
        grid = error.partial["grid"]
        assert grid is not None
        for method in (grid.__init__, lambda: grid.cell_grid(1, 0, 1, 0, 1)):
            with pytest.raises(ecm.EcmRejected) as blocked:
                method()
            assert blocked.value.stage == "source_call_unavailable"
    with pytest.raises(ecm.geometry.GeometryRejected):
        _ = before.cells


def test_software_descriptor_factory_failure_keeps_original_before_caller(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure="descriptor_factory")
    request = h.request.geometry_request.prefix_request.parameter_request
    with pytest.raises(ecm.parameters.ParameterRejected) as caught:
        ecm.parameters.prepare_parameters(request)
    assert caught.value.source_error is h.errors["source"]
    assert caught.value.source_error.__cause__ is h.errors["cause"]
    assert not h.h.upstream.events and not caught.value.partial["usable_parameter_owner_available"]
    save(evidence, "failure", caught.value)


@pytest.mark.parametrize("value", [True, 0, -1, 3.0, "3"])
def test_software_descriptor_retains_native_type_domain_without_eager_cast(
    value, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, grid_size=value)
    before = parent(h)
    p = ecm.geometry._authority(before).parent.p
    assert "grid_size" not in vars(p)
    with pytest.raises(ValueError):
        _ = p.grid_size
    if value is True or value == -1:
        child = ecm.prepare_continuation(ecm.from_geometry(before, law_id=ecm.LAW_ID))
        assert child.trial.source_completed
        save(evidence, "counterfactual-trial", child.trial)
    else:
        with pytest.raises(ecm.EcmRejected) as caught:
            ecm.prepare_continuation(ecm.from_geometry(before, law_id=ecm.LAW_ID))
        save(evidence, "failure", caught.value)
        assert isinstance(
            caught.value.source_error, ZeroDivisionError if value == 0 else SyntheticSourceFailure
        )


@pytest.mark.parametrize(
    "change",
    [
        "grid_value",
        "parent_invalid",
        "grid_class",
        "runtime_class",
        "equal_alias",
        "grid_graph_edge",
        "kernel_code",
        "grid_code",
        "descriptor_code",
        "descriptor_object",
        "configuration",
        "caller_binding",
        "observer",
        "rng",
        "helper",
    ],
)
def test_software_live_ecm_authority_drift_refuses(change, monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    owner = ecm.prepare(h.request)
    context = ecm._authority(owner)
    cells = owner.cells
    if change == "grid_value":
        context.grid.cents_X[0, 0] = 9.0
    elif change in ("grid_class", "runtime_class"):
        original = type(context.grid)
        other = type(
            original.__name__,
            original.__bases__,
            {k: v for k, v in vars(original).items() if k not in {"__dict__", "__weakref__"}},
        )
        before_state = ecm._snapshot(context).identity
        if change == "grid_class":
            context.grid.__class__ = other
        else:
            monkeypatch.setattr(ecm, "_GridRuntime", other)
        assert ecm._snapshot(context).identity == before_state
    elif change == "parent_invalid":
        before = ecm._snapshot(context).identity
        stream = ecm.core.initial._rng_stream(context.parent.parent.rng).identity
        context.parent.invalid = True
        assert ecm._snapshot(context).identity == before
        assert ecm.core.initial._rng_stream(context.parent.parent.rng).identity == stream
    elif change == "equal_alias":
        cells.X = context.grid.cents_Y
    elif change == "grid_graph_edge":
        context.grid.equal_reference = context.grid.cents_Y
    elif change in ("kernel_code", "grid_code", "descriptor_code"):
        method = {
            "kernel_code": ecm._MAKE,
            "grid_code": ecm._GRID,
            "descriptor_code": type(context.parameter_info.native).__get__,
        }[change]
        monkeypatch.setattr(method, "__code__", method.__code__.replace())
    elif change == "descriptor_object":
        monkeypatch.setattr(context.parameter_info.runtime, "grid_size", object())
    elif change == "configuration":
        context.parent.parent.p._conf["general options"]["comp grid size"] = 7
    elif change == "caller_binding":
        monkeypatch.setattr(ecm.completion, "_CELL_INDEX", lambda *a: None)
    elif change == "observer":
        cells.mesh._cells_rng.observer = ecm.core.initial._Observer(())
    elif change == "rng":
        context.parent.parent.rng.epoch = "changed"
    else:
        context.method.__globals__["fd"].FiniteDiffSolver = lambda: context.grid
    with pytest.raises(ecm.EcmRejected) as caught:
        _ = owner.cells
    save(evidence, "refusal", caught.value)
    assert caught.value.stage == "ecm_drift"


@pytest.mark.parametrize("unwind", [False, True])
def test_software_capture_failure_retains_primary_profiler_and_raw_state(
    unwind, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure="makeECM" if unwind else None)
    before = parent(h)
    request = ecm.from_geometry(before, law_id=ecm.LAW_ID)
    original, previous = ecm.geometry._capture_locals, sys.getprofile()
    capture = SyntheticCaptureFailure("synthetic ECM locals observation failure")

    def broken(context, name, frame):
        if name == "makeECM":
            raise capture
        return original(context, name, frame)

    monkeypatch.setattr(ecm.geometry, "_capture_locals", broken)
    with pytest.raises(ecm.EcmRejected) as caught:
        ecm.prepare_continuation(request)
    error = caught.value
    save(evidence, "failure", error)
    assert sys.getprofile() is previous and error.capture_error is capture
    assert error.source_error is (h.errors["source"] if unwind else None)
    assert error.partial["parent_trial"] is before.trial and error.partial["geometry_consumed"]
    assert error.partial["grid"] is error.partial["caller"].grid_obj
    assert not any(ctx.request is request for ctx in ecm._ISSUED.values())


def test_software_raw_success_grid_descriptor_repeat_and_environment_stay_closed(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = ecm.prepare(h.request)
    context = ecm._authority(owner)
    for method in (context.grid.__init__, lambda: context.grid.cell_grid(1, 0, 1, 0, 1)):
        with pytest.raises(ecm.EcmRejected):
            method()
    with pytest.raises(ValueError):
        _ = context.parent.parent.p.grid_size
    with pytest.raises(ValueError):
        context.parent.parent.p.grid_size = 4
    with pytest.raises(ecm.geometry.GeometryRejected):
        _ = context.request.geometry_owner.cells
    with pytest.raises(ecm.EcmRejected):
        ecm.prepare_continuation(context.request)
    assert owner.cells is context.parent.parent.caller
    with pytest.raises(TypeError):
        pickle.dumps(owner)
    with pytest.raises(TypeError):
        pickle.dumps(context.grid)
    with pytest.raises(ecm.EcmRejected) as caught:
        ecm.require_environment(owner, phase=SimpleNamespace())
    assert (
        caught.value.stage == "environment_held"
        and len(caught.value.partial["invalidated_owners"]) == 11
    )
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize("part", ["snapshot", "trial", "identity"])
@pytest.mark.parametrize("unwind", [False, True])
def test_software_sealing_failure_retains_original_trial_and_partial_objects(
    part, unwind, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure="makeECM" if unwind else None)
    before = parent(h)
    request = ecm.from_geometry(before, law_id=ecm.LAW_ID)
    failure = SyntheticCaptureFailure("synthetic final ECM seal failure")
    if part == "snapshot":
        original = ecm._snapshot

        def snapshot(context):
            if hasattr(context.parent.parent.caller, "ecmdl"):
                raise failure
            return original(context)

        monkeypatch.setattr(ecm, "_snapshot", snapshot)
    else:

        def broken(*a, **k):
            raise failure

        monkeypatch.setattr(ecm, "Trial" if part == "trial" else "trial_record", broken)
    with pytest.raises(ecm.EcmRejected) as caught:
        ecm.prepare_continuation(request)
    error = caught.value
    save(evidence, "failure", error)
    assert error.stage == "capture" and error.capture_error is failure
    assert error.source_error is (h.errors["source"] if unwind else None)
    assert error.partial["parent_trial"] is before.trial
    assert error.partial["grid"] is error.partial["caller"].grid_obj
    assert error.partial["geometry_consumed"] and not error.partial["usable_ecm_child_available"]
    assert not any(ctx.request is request for ctx in ecm._ISSUED.values())


def test_software_issuance_graph_failure_retains_successful_source_trial(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    before = parent(h)
    request = ecm.from_geometry(before, law_id=ecm.LAW_ID)
    capture = SyntheticCaptureFailure("synthetic ECM graph seal failure")

    def broken(*a):
        raise capture

    monkeypatch.setattr(ecm, "_graphs", broken)
    with pytest.raises(ecm.EcmRejected) as caught:
        ecm.prepare_continuation(request)
    save(evidence, "failure", caught.value)
    assert caught.value.capture_error is capture and caught.value.trial.source_completed
    assert caught.value.partial["parent_trial"] is before.trial
    assert not any(ctx.request is request for ctx in ecm._ISSUED.values())


@pytest.mark.parametrize("unwind", [False, True])
def test_software_event_observation_failure_preserves_read_error_and_stops_constructor(
    unwind, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure="descriptor_read" if unwind else None)
    before = parent(h)
    request = ecm.from_geometry(before, law_id=ecm.LAW_ID)
    original = ecm._namespace
    capture = SyntheticCaptureFailure("synthetic ECM event append failure")

    class Broken(list):
        def append(self, value):
            raise capture

    def namespace(context):
        context.events = Broken([("previous", "retained")])
        return original(context)

    monkeypatch.setattr(ecm, "_namespace", namespace)
    with pytest.raises(ecm.EcmRejected) as caught:
        ecm.prepare_continuation(request)
    save(evidence, "failure", caught.value)
    assert caught.value.capture_error is capture
    assert caught.value.source_error is (h.errors["source"] if unwind else None)
    assert list(caught.value.partial["events"]) == [("previous", "retained")]
    assert "constructor_body" not in h.events and caught.value.partial["grid"] is None


def test_software_reentrant_attempt_cannot_rearm_consumed_geometry(monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    before = parent(h)
    request = ecm.from_geometry(before, law_id=ecm.LAW_ID)
    original = ecm._namespace
    refusals = []

    def namespace(context):
        with pytest.raises(ecm.EcmRejected) as caught:
            ecm.prepare_continuation(request)
        refusals.append(caught.value)
        return original(context)

    monkeypatch.setattr(ecm, "_namespace", namespace)
    child = ecm.prepare_continuation(request)
    assert child.cells is ecm._authority(child).parent.parent.caller
    assert len(refusals) == 1 and refusals[0].partial["geometry_consumed"]
    assert h.events.count("constructor_body") == h.events.count("cell_grid_body") == 1
    save(evidence, "refusal", refusals[0])
    save(evidence, "trial", child.trial)


@pytest.mark.parametrize("origin", ["foreign", "unissued"])
def test_software_unavailable_native_module_authority_refuses_without_import(
    origin, monkeypatch, tmp_path, evidence
):
    file = (
        str(tmp_path / "foreign.py")
        if origin == "foreign"
        else str(ecm.aliases.NATIVE / "betse/lib/yaml/yamlalias.py")
    )
    monkeypatch.setitem(sys.modules, "betse.synthetic_unissued", SimpleNamespace(__file__=file))
    with pytest.raises(ValueError) as caught:
        ecm.aliases._check_modules()
    assert (
        "unavailable source origin" in str(caught.value)
        if origin == "foreign"
        else "process-local source issuance" in str(caught.value)
    )
    save(evidence, "refusal", caught.value)


def test_software_default_parameter_path_has_no_descriptor_factory_or_record_delta(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)

    def forbidden():
        raise AssertionError("Default height path must not execute grid descriptor factory")

    monkeypatch.setattr(ecm.aliases, "_descriptor_from_source", forbidden)
    p = ecm.parameters
    request = p.from_core(
        h.h.upstream.parent, {"world options": {"cell height": "2.5"}}, law_id=p.LAW_ID
    )
    assert request.grid_descriptor is None and "selected_descriptor" not in p.request_record(
        request
    )
    owner = p.prepare_parameters(request)
    assert type(owner.parameters) is p._Runtime
    assert owner.trial.descriptor_proof == () and "selected_descriptor" not in p.trial_record(
        owner.trial
    )
    assert h.events == []
    save(evidence, "trial", owner.trial)
