"""Ordinary initial-geometry lifetime controls with literal/native work blocked."""

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

from cells.processes import betse_native_single_cell_initial_geometry as geo
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_TEST = "tests/unit/test_betse_native_single_cell_caller_completion.py"


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_INITIAL_GEOMETRY_EVIDENCE", str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def harness(monkeypatch, tmp_path, *, failure=None):
    # Reuse the reviewed counterfactual source chain. Parameters are freshly
    # constructed before the synthetic caller/image/mesh, never hydrated.
    helper = runpy.run_path(str(ROOT / UPSTREAM_TEST))
    h = helper["harness"](monkeypatch, tmp_path)
    parameters = geo.parameters

    def construct(p, recipe, configuration):
        h.events.append("parameters")
        geometry = parameters._context(p).request.projection == parameters.GEOMETRY
        p._conf = configuration
        p.world_len = 4.0
        p.cell_radius = 0.5
        p.cell_lattice_disorder = 0.0
        p.cell_lattice_type = geo.callers.source.CellLatticeType.HEX
        p.wsx = 4.0
        p.wsy = 4.0
        p.cell_height = 2.5
        if geometry:
            p.cell_space = 0.25
        p.ac = 1e-6
        if geometry:
            p.scale_cell = 0.99
            p.tm = 7.5e-9
        p.d_cell = 1.0
        p.nx = 4
        p.ny = 4
        p.wsx = 4.0
        p.wsy = 4.0

    monkeypatch.setattr(parameters, "_construct", construct)
    monkeypatch.setattr(geo, "_verify_sources", lambda: dict(h.pins))
    request = geo.from_core(
        h.parent,
        {"world options": {"cell height": "2.5", "cell spacing": "0.25"}},
        law_id=geo.LAW_ID,
    )
    calls = []
    errors = {}

    def step(cells, p, name):
        calls.append(name)
        assert p is h.state.p
        assert p.cell_space == 0.25 and p.scale_cell == 0.99 and p.tm == 7.5e-9
        assert h.events[:3] == ["parameters", "caller", "image"]
        # Literal fixture outputs only. Actual NumPy/object-array/tree/pinv
        # source bodies are independently forbidden by the runner.
        if name == "cellVerts":
            cells.gj_len = p.cell_space
            cells.cell_verts = np.empty(2, dtype=object)
            cells.cell_verts[0] = np.asarray([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
            cells.cell_verts[1] = np.asarray([[1.0, 0.0], [2.0, 0.0], [1.0, 1.0]])
            cells.mem_i = [0, 1]
        elif name == "cellMatrices":
            cells.M_sum_mems = np.asarray([[1.0, 0.0], [0.0, 1.0]])
        elif name == "cell_vols":
            cells.mem_vol = np.asarray([1.0, 2.0])
            cells.cell_vol = np.asarray([1.0, 2.0])
        elif name == "mem_processing":
            cells.mem_nn = np.asarray([[0, 0], [1, 1]])
        else:
            cells.cell_nn = np.empty(2, dtype=object)
            cells.cell_nn[0] = []
            cells.cell_nn[1] = []
            cells.num_nn = np.asarray([0, 0])
        if failure == name:
            try:
                raise SyntheticSourceCause("original synthetic geometry cause")
            except SyntheticSourceCause as cause:
                error = SyntheticSourceFailure("synthetic source failure at " + name)
                errors["source"], errors["cause"] = error, cause
                raise error from cause

    def namespace(context):
        values = dict(geo.source.__dict__)
        values.update(step=step, logs=geo._Logs(context))
        program = "\n".join(
            "def " + name + "(self,p):\n    step(self,p," + repr(name) + ")" for name in geo.METHODS
        )
        exec(compile(program, "<synthetic-initial-geometry>", "exec"), values)
        return {name: values[name] for name in geo.METHODS}

    monkeypatch.setattr(geo, "_namespace", namespace)
    return SimpleNamespace(upstream=h, request=request, calls=calls, errors=errors)


def parent(h):
    return geo._prefix(h.request.prefix_request)


def test_software_literal_stores_and_ordinary_caller_order(evidence):
    pins = geo._verify_sources()
    source = geo.parameters.geometry_source
    expected = [533, 534, 535, 536, 1118, 1119, 1122, 1127, 1128, 1129, 1130, 1131]
    assert source.STORE_LINES == expected
    tree = ast.parse(Path(source.__file__).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    stores = next(n for n in cls.body if isinstance(n, ast.FunctionDef)).body
    native = ast.parse((geo.callers.NATIVE_ROOT / "betse/science/parameters.py").read_text())
    originals = {n.lineno: n for n in ast.walk(native) if isinstance(n, ast.Assign)}
    assert ast.dump(ast.Module(body=stores, type_ignores=[])) == ast.dump(
        ast.Module(body=[originals[line] for line in expected], type_ignores=[])
    )
    cells = ast.parse((geo.callers.NATIVE_ROOT / "betse/science/cells.py").read_text())
    cls = next(n for n in cells.body if isinstance(n, ast.ClassDef) and n.name == "Cells")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "make_world")
    calls = [
        n.value.func.attr
        for n in method.body
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Attribute)
        and isinstance(n.value.func.value, ast.Name)
        and n.value.func.value.id == "self"
    ]
    start = calls.index("cellVerts")
    assert tuple(calls[start : start + 5]) == geo.METHODS
    assert calls[start + 5] == "makeECM"
    assert "intra_updater" not in geo.METHODS and "calc_gj_vects" not in geo.METHODS
    save(evidence, "source-pins", pins)


def test_software_full_geometry_uses_fresh12_parameters_same_caller_and_order(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = geo.prepare(h.request)
    cells = owner.cells
    old = geo.completion._authority(geo._authority(owner).request.caller_owner)
    assert cells is old.caller and cells.mesh is old.mesh_context.kernel
    assert old.p is h.upstream.state.p
    names = [name for name, _ in geo.parameters._authority(h.upstream.state.parameter).trial.stores]
    assert names == [
        "_conf",
        "world_len",
        "cell_radius",
        "cell_lattice_disorder",
        "cell_lattice_type",
        "wsx",
        "wsy",
        "cell_height",
        "cell_space",
        "ac",
        "scale_cell",
        "tm",
        "d_cell",
        "nx",
        "ny",
        "wsx",
        "wsy",
    ]
    assert tuple(h.calls) == geo.METHODS
    assert [name for name, _ in owner.trial.stages] == ["before", *geo.METHODS]
    assert cells.cell_verts.dtype == object
    assert owner.trial.stream_before.identity == owner.trial.stream_after.identity
    assert all(
        any(e["entry_method"] == name and e["layer"] == "body" for e in owner.trial.work)
        for name in geo.METHODS
    )
    assert owner.trial.source_completed
    with pytest.raises(geo.completion.CompletionRejected) as caught:
        _ = geo._authority(owner).request.caller_owner.cells
    assert caught.value.stage == "caller_epoch_consumed"
    save(evidence, "trial", owner.trial)


def test_software_old_height_only_owner_refuses_without_retirement(monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    old = geo.completion.prepare(h.upstream.request)
    with pytest.raises(geo.GeometryRejected) as caught:
        geo.from_caller(old, law_id=geo.LAW_ID)
    assert caught.value.stage == "geometry_parameter_prerequisite"
    assert old not in geo.completion._FORWARDED
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize("name", geo.METHODS)
def test_software_each_method_failure_retains_partial_state_and_consumes_parent(
    name, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure=name)
    before = parent(h)
    request = geo.from_caller(before, law_id=geo.LAW_ID)
    with pytest.raises(geo.GeometryRejected) as caught:
        geo.prepare_continuation(request)
    error = caught.value
    assert error.source_error is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert error.partial["caller"] is geo.completion._authority(before).caller
    assert error.partial["caller_epoch_consumed"]
    assert error.partial["source_stage"] == name
    assert name in error.partial["raw_locals"]
    assert error.partial["raw_locals"][name]["self"] is error.partial["caller"]
    assert not error.trial.source_completed
    assert h.calls == list(geo.METHODS[: geo.METHODS.index(name) + 1])
    with pytest.raises(geo.completion.CompletionRejected):
        _ = before.cells
    save(evidence, "failure", error)


@pytest.mark.parametrize("kind", ["object_array", "empty", "degenerate"])
def test_software_native_style_failures_are_retained_without_repair(
    kind, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    original = geo._namespace
    error = {
        "object_array": TypeError("native object-array operation unsupported"),
        "empty": IndexError("native empty geometry index"),
        "degenerate": ValueError("native degenerate geometry"),
    }[kind]

    def namespace(context):
        methods = original(context)

        def fail(cells, p):
            cells.cell_verts = np.empty(0, dtype=object)
            raise error

        fail.__globals__.update(
            {
                k: v
                for k, v in methods["cellVerts"].__globals__.items()
                if k in {"np", "math", "cKDTree", "tb", "logs"}
            }
        )
        methods["cellVerts"] = fail
        return methods

    monkeypatch.setattr(geo, "_namespace", namespace)
    with pytest.raises(geo.GeometryRejected) as caught:
        geo.prepare(h.request)
    inner = caught.value.source_error
    assert inner.source_error is error
    assert inner.partial["caller"].cell_verts.size == 0
    assert inner.partial["caller"].cell_verts.dtype == object
    assert h.calls == []
    save(evidence, "failure", caught.value)


@pytest.mark.parametrize("failed", [False, True])
@pytest.mark.parametrize("point", ["snapshot", "trial", "identity", "graphs"])
def test_software_geometry_capture_failure_keeps_primary_and_partial(
    point, failed, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure="near_neigh" if failed else None)
    before = parent(h)
    request = geo.from_caller(before, law_id=geo.LAW_ID)
    original = geo._namespace
    capture = SyntheticCaptureFailure("injected geometry capture failure")

    def bad(*args, **kwargs):
        raise capture

    def namespace(context):
        methods = original(context)
        old = methods["near_neigh"]

        def last(cells, p):
            try:
                old(cells, p)
            finally:
                if point == "snapshot":
                    monkeypatch.setattr(geo, "_snapshot", bad)
                elif point == "trial":
                    monkeypatch.setattr(geo, "Trial", bad)
                elif point == "identity":
                    monkeypatch.setattr(geo, "trial_record", bad)
                else:
                    monkeypatch.setattr(geo.meshes, "_graphs", bad)

        last.__globals__.update(
            {
                k: v
                for k, v in old.__globals__.items()
                if k in {"np", "math", "cKDTree", "tb", "logs"}
            }
        )
        methods["near_neigh"] = last
        return methods

    monkeypatch.setattr(geo, "_namespace", namespace)
    with pytest.raises(geo.GeometryRejected) as caught:
        geo.prepare_continuation(request)
    error = caught.value
    assert error.source_error is (h.errors["source"] if failed else None)
    assert error.capture_error is (None if point == "graphs" and failed else capture)
    assert error.partial["caller_epoch_consumed"]
    assert error.partial["caller"] is geo.completion._authority(before).caller
    save(evidence, "failure", error)


@pytest.mark.parametrize(
    "change", ["parameter", "mesh", "rng", "alias_equal", "method", "observer", "parent_trial"]
)
def test_software_geometry_child_rejects_authority_drift(change, monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    owner = geo.prepare(h.request)
    context = geo._authority(owner)
    cells = owner.cells
    if change == "parameter":
        context.parent.p.tm = 1.0
    elif change == "mesh":
        cells.mesh.vor_sa[0] = 99.0
    elif change == "rng":
        context.parent.rng.epoch = "changed"
    elif change == "alias_equal":
        cells.ecm_verts = np.array(cells.ecm_verts, copy=True)
    elif change == "method":
        monkeypatch.setitem(geo._NATIVE, "cellVerts", lambda self, p: None)
    elif change == "observer":
        cells.mesh._cells_rng.observer = geo.core.initial._Observer(())
    else:
        object.__setattr__(context.parent.trial, "work", ({"changed": True},))
    with pytest.raises(geo.GeometryRejected) as caught:
        _ = owner.cells
    assert caught.value.stage == "geometry_drift"
    save(evidence, "refusal", caught.value)


def test_software_no_phase_callback_ECM_grid_or_checkpoint_admission(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = geo.prepare(h.request)
    with pytest.raises(TypeError):
        pickle.dumps(owner)
    with pytest.raises(geo.GeometryRejected) as caught:
        geo.require_makeECM(owner, phase=SimpleNamespace())
    assert caught.value.stage == "ECM_environment_held"
    assert len(caught.value.partial["invalidated_owners"]) == 11
    save(evidence, "refusal", caught.value)


def test_software_projection_and_exact_store_roster_bind_request_and_trial(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    p = geo.parameters
    geometry = h.request.prefix_request.parameter_request
    height = p.from_core(
        h.upstream.parent,
        {"world options": {"cell height": "2.5", "cell spacing": "0.25"}},
        law_id=p.LAW_ID,
    )
    assert height.projection == p.HEIGHT and geometry.projection == p.GEOMETRY
    assert height.identity != geometry.identity
    old, new = p.prepare_parameters(height), p.prepare_parameters(geometry)
    assert old.trial.projection == p.HEIGHT and new.trial.projection == p.GEOMETRY
    assert len(old.trial.store_lines) == 9 and len(new.trial.store_lines) == 12
    assert tuple(name for name, _ in old.trial.stores) == old.trial.store_roster
    assert tuple(name for name, _ in new.trial.stores) == new.trial.store_roster
    assert "cell_space" not in vars(old.parameters) and "cell_space" in vars(new.parameters)
    assert p.request_record(height)["store_roster"] == old.trial.store_roster
    assert p.trial_record(new.trial)["store_roster"] == new.trial.store_roster
    save(evidence, "height-trial", old.trial)
    save(evidence, "geometry-trial", new.trial)


@pytest.mark.parametrize(
    "change",
    ["height_to_geometry", "geometry_to_height", "trial_mode", "trial_roster", "trial_lines"],
)
def test_software_changed_projection_or_resealed_roster_cannot_gain_authority(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    p = geo.parameters
    request = h.request.prefix_request.parameter_request
    if change == "height_to_geometry":
        request = p.from_core(
            h.upstream.parent, {"world options": {"cell height": "2.5"}}, law_id=p.LAW_ID
        )
    owner = p.prepare_parameters(request)
    context = p._authority(owner)
    original = owner.trial
    if change in {"height_to_geometry", "geometry_to_height"}:
        mode = p.GEOMETRY if change == "height_to_geometry" else p.HEIGHT
        object.__setattr__(request, "projection", mode)
        object.__setattr__(request, "identity", geo.core.records._digest(p.request_record(request)))
    else:
        update = {
            "trial_mode": dict(projection=p.HEIGHT),
            "trial_roster": dict(store_roster=context.trial.store_roster[:-1]),
            "trial_lines": dict(store_lines=context.trial.store_lines[:-1]),
        }[change]
        forged = replace(context.trial, **update)
        context.trial = replace(forged, identity=geo.core.records._digest(p.trial_record(forged)))
    with pytest.raises(p.ParameterRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "parameter_drift"
    assert context.invalid
    save(evidence, "original-trial", original)
    save(evidence, "refusal", caught.value)


def test_software_namespace_setup_failure_is_irreversible_and_keeps_actual_prior_trial(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    before = parent(h)
    prior = before.trial
    request = geo.from_caller(before, law_id=geo.LAW_ID)
    failure = SyntheticSourceFailure("synthetic namespace setup failed")

    def namespace(context):
        raise failure

    monkeypatch.setattr(geo, "_namespace", namespace)
    with pytest.raises(geo.GeometryRejected) as caught:
        geo.prepare_continuation(request)
    error = caught.value
    assert error.source_error is failure and error.partial["parent_trial"] is prior
    assert error.partial["caller_epoch_consumed"]
    assert h.calls == []
    with pytest.raises(geo.completion.CompletionRejected):
        _ = before.cells
    save(evidence, "failure", error)


def test_software_reentrant_and_repeated_geometry_never_rearm_parent(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    before = parent(h)
    request = geo.from_caller(before, law_id=geo.LAW_ID)
    original = geo._namespace
    refusals = []

    def namespace(context):
        methods = original(context)
        first = methods["cellVerts"]

        def wrapped(cells, p):
            with pytest.raises(geo.GeometryRejected) as caught:
                geo.prepare_continuation(request)
            refusals.append(caught.value)
            first(cells, p)

        wrapped.__globals__.update(
            {
                k: v
                for k, v in first.__globals__.items()
                if k in {"np", "math", "cKDTree", "tb", "logs"}
            }
        )
        methods["cellVerts"] = wrapped
        return methods

    monkeypatch.setattr(geo, "_namespace", namespace)
    owner = geo.prepare_continuation(request)
    assert len(refusals) == 1 and refusals[0].stage == "geometry_reentrant"
    assert tuple(h.calls) == geo.METHODS
    with pytest.raises(geo.GeometryRejected) as caught:
        geo.prepare_continuation(request)
    assert caught.value.source_error.stage == "caller_epoch_consumed"
    assert tuple(h.calls) == geo.METHODS and owner.cells is geo.completion._authority(before).caller
    save(evidence, "reentrant-refusal", refusals[0])
    save(evidence, "repeat-refusal", caught.value)


def test_software_changed_parent_trial_preserves_actual_prior_object(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    before = parent(h)
    prior = before.trial
    request = geo.from_caller(before, law_id=geo.LAW_ID)
    original = geo._namespace

    def namespace(context):
        methods = original(context)
        first = methods["cellVerts"]

        def wrapped(cells, p):
            first(cells, p)
            geo.completion._authority(before).trial = replace(prior)

        wrapped.__globals__.update(
            {
                k: v
                for k, v in first.__globals__.items()
                if k in {"np", "math", "cKDTree", "tb", "logs"}
            }
        )
        methods["cellVerts"] = wrapped
        return methods

    monkeypatch.setattr(geo, "_namespace", namespace)
    with pytest.raises(geo.GeometryRejected) as caught:
        geo.prepare_continuation(request)
    assert caught.value.partial["parent_trial"] is prior
    assert caught.value.partial["caller_epoch_consumed"]
    save(evidence, "failure", caught.value)


@pytest.mark.parametrize("change", ["helper", "method_code"])
def test_software_execution_namespace_drift_refuses_without_shared_module_patch(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    source_flatten = geo.source.tb.flatten
    owner = geo.prepare(h.request)
    context = geo._authority(owner)
    fn = context.methods["cellVerts"]
    if change == "helper":
        fn.__globals__["tb"] = SimpleNamespace(flatten=lambda value: value)
    else:
        fn.__code__ = fn.__code__.replace()
    assert geo.source.tb.flatten is source_flatten
    with pytest.raises(geo.GeometryRejected) as caught:
        _ = owner.cells
    assert caught.value.stage == "geometry_drift"
    assert geo.source.tb.flatten is source_flatten
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize("observer", ["locals", "log", "both"])
@pytest.mark.parametrize("unwind", [False, True])
def test_software_observer_failure_preserves_primary_unwind_and_prior_profiler(
    observer, unwind, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure="cellMatrices" if unwind else None)
    before = parent(h)
    prior = before.trial
    request = geo.from_caller(before, law_id=geo.LAW_ID)
    capture_locals = SyntheticCaptureFailure("synthetic locals capture failed")
    capture_log = SyntheticCaptureFailure("synthetic log capture failed")
    captured = []
    original_capture = geo._capture_locals

    def capture(context, name, frame):
        if name == "cellMatrices" and observer in {"locals", "both"}:
            captured.append(frame)
            raise capture_locals
        original_capture(context, name, frame)

    monkeypatch.setattr(geo, "_capture_locals", capture)
    original_namespace = geo._namespace

    class BrokenLog(list):
        def append(self, value):
            raise capture_log

    codes = []

    def namespace(context):
        methods = original_namespace(context)
        if observer in {"log", "both"}:
            context.logs = BrokenLog([("original earlier message",)])
            log = geo._Logs(context)
            method = methods["cellMatrices"]

            def observed(cells, p):
                try:
                    method(cells, p)
                finally:
                    log.log_info("original source message", 17)

            observed.__globals__.update(
                {
                    k: v
                    for k, v in method.__globals__.items()
                    if k in {"np", "math", "cKDTree", "tb", "logs"}
                }
            )
            methods["cellMatrices"] = observed
        codes.append(methods["cellMatrices"].__code__)
        return methods

    monkeypatch.setattr(geo, "_namespace", namespace)
    previous = sys.getprofile()
    previous_events = []

    def prior_profile(frame, event, arg):
        if event == "return" and frame.f_code in codes:
            previous_events.append((frame.f_code.co_name, event))
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(prior_profile)
    try:
        with pytest.raises(geo.GeometryRejected) as caught:
            geo.prepare_continuation(request)
        assert sys.getprofile() is prior_profile
    finally:
        sys.setprofile(previous)
    error = caught.value
    assert error.stage == "capture"
    source = h.errors["source"] if unwind else None
    assert error.source_error is source
    assert error.capture_error is (capture_locals if observer == "locals" else capture_log)
    if unwind:
        assert error.source_error.__cause__ is h.errors["cause"]
        assert error.__cause__ is source
    else:
        assert error.__cause__ is error.capture_error
    assert previous_events and len(previous_events) == 1
    assert h.calls == ["cellVerts", "cellMatrices"]
    assert error.partial["source_stage"] == "cellMatrices"
    assert [name for name, _ in error.partial["stages"]] == ["before", "cellVerts"]
    assert error.partial["parent_trial"] is prior
    assert error.partial["caller"] is geo.completion._authority(before).caller
    assert error.partial["caller_epoch_consumed"]
    assert error.partial["usable_geometry_child_available"] is False
    assert "cellVerts" in error.partial["raw_locals"]
    if observer in {"locals", "both"}:
        assert captured
        assert any(error is capture_locals for _, error in error.partial["observation_errors"])
    if observer in {"log", "both"}:
        assert list(error.partial["logs"]) == [("original earlier message",)]
        assert any(error is capture_log for _, error in error.partial["observation_errors"])
    if observer == "both":
        assert [kind for kind, _ in error.partial["observation_errors"]] == [
            "log_info",
            "return_locals",
        ]
    assert not any(ctx.request is request for ctx in geo._ISSUED.values())
    with pytest.raises(geo.completion.CompletionRejected):
        _ = before.cells
    save(evidence, "failure", error)
    save(evidence, "profiler-events", previous_events)
    save(evidence, "raw-frame-keys", [list(frame.f_locals) for frame in captured])


def test_software_prior_profiler_rejection_still_propagates_and_restores(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    before = parent(h)
    request = geo.from_caller(before, law_id=geo.LAW_ID)
    rejected = SyntheticSourceFailure("synthetic prior native guard rejection")
    previous = sys.getprofile()
    calls = []

    def guard(frame, event, arg):
        if (
            event == "call"
            and frame.f_code.co_name == "cellMatrices"
            and frame.f_code.co_filename == "<synthetic-initial-geometry>"
        ):
            calls.append(frame.f_code.co_name)
            raise rejected
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(guard)
    try:
        with pytest.raises(geo.GeometryRejected) as caught:
            geo.prepare_continuation(request)
        assert sys.getprofile() is guard
    finally:
        sys.setprofile(previous)
    assert caught.value.source_error is rejected
    assert caught.value.capture_error is None
    assert calls == ["cellMatrices"] and h.calls == ["cellVerts"]
    assert caught.value.partial["caller_epoch_consumed"]
    save(evidence, "failure", caught.value)


@pytest.mark.parametrize("slot", ["_TAIL_ALIASES", "_CELL_INDEX", "_caller", "_image", "_mesh"])
@pytest.mark.parametrize("change", ["callable", "code"])
@pytest.mark.parametrize("when", ["issuance", "child_use"])
def test_software_geometry_retains_completion_callable_atoms_after_retirement(
    slot, change, when, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    before = parent(h)
    request = geo.from_caller(before, law_id=geo.LAW_ID)
    original_namespace = geo._namespace
    observations = []

    def forbid_consumed_parent(*args, **kwargs):
        raise AssertionError("Consumed completion validator must not be reopened")

    def mutate(context):
        before_state = geo._snapshot(context).identity
        before_rng = geo.core.initial._rng_stream(context.parent.rng).identity
        original = getattr(geo.completion, slot)
        if change == "callable":
            monkeypatch.setattr(geo.completion, slot, lambda *args, **kwargs: None)
        else:
            monkeypatch.setattr(original, "__code__", original.__code__.replace())
        monkeypatch.setattr(geo.completion, "_validate", forbid_consumed_parent)
        assert geo._snapshot(context).identity == before_state
        assert geo.core.initial._rng_stream(context.parent.rng).identity == before_rng
        assert context.parent.trial is before.trial
        observations.append((before_state, before_rng))

    def namespace(context):
        methods = original_namespace(context)
        method = methods["near_neigh"]

        def finish(cells, p):
            method(cells, p)
            mutate(context)

        methods["near_neigh"] = FunctionType(
            finish.__code__, method.__globals__, finish.__name__, closure=finish.__closure__
        )
        return methods

    if when == "issuance":
        monkeypatch.setattr(geo, "_namespace", namespace)
        with pytest.raises(geo.GeometryRejected) as caught:
            geo.prepare_continuation(request)
        assert caught.value.partial["parent_trial"] is before.trial
        assert not caught.value.trial.source_completed
        assert not any(ctx.request is request for ctx in geo._ISSUED.values())
    else:
        child = geo.prepare_continuation(request)
        context = geo._authority(child)
        assert child.cells is context.parent.caller
        mutate(context)
        with pytest.raises(geo.GeometryRejected) as caught:
            _ = child.cells
        assert caught.value.stage == "geometry_drift"
    assert (
        str(caught.value.source_error) == "Original mesh/caller callable or code identity changed"
    )
    assert before in geo.completion._FORWARDED
    assert tuple(h.calls) == geo.METHODS
    assert observations
    save(evidence, "unchanged-state-and-rng", observations)
    save(evidence, "refusal", caught.value)


def isolated_helpers(monkeypatch):
    """Retarget only counterfactual namespaces, never global NumPy/native helpers."""
    original_namespace = geo._namespace

    def namespace(context):
        methods = original_namespace(context)
        for globals_ in {id(fn.__globals__): fn.__globals__ for fn in methods.values()}.values():
            original_np = globals_["np"]
            globals_["np"] = SimpleNamespace(
                **{name: getattr(original_np, name) for name in geo._NUMPY_HELPERS},
                linalg=SimpleNamespace(norm=original_np.linalg.norm, pinv=original_np.linalg.pinv),
            )
            globals_["math"] = SimpleNamespace(pi=globals_["math"].pi)
            original_flatten = globals_["tb"].flatten
            flatten_globals = dict(original_flatten.__globals__)
            flatten_globals["copy"] = SimpleNamespace(deepcopy=flatten_globals["copy"].deepcopy)
            flatten = FunctionType(
                original_flatten.__code__,
                flatten_globals,
                original_flatten.__name__,
                original_flatten.__defaults__,
                original_flatten.__closure__,
            )
            globals_["tb"] = SimpleNamespace(flatten=flatten)
        return methods

    monkeypatch.setattr(geo, "_namespace", namespace)


@pytest.mark.parametrize(
    "helper",
    [
        "array",
        "sqrt",
        "vstack",
        "linalg.norm",
        "zeros",
        "abs",
        "roll",
        "dot",
        "asarray",
        "linalg.pinv",
        "flatten",
        "flatten_code",
        "deepcopy",
        "math_object",
        "pi_value",
        "pi_type",
        "log_method",
        "log_code",
        "log_context",
    ],
)
def test_software_reached_namespace_helper_and_log_retargets_refuse_without_state_drift(
    helper, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    isolated_helpers(monkeypatch)
    owner = geo.prepare(h.request)
    context = geo._authority(owner)
    assert owner.cells is context.parent.caller
    namespace = context.methods["cellVerts"].__globals__
    before_state = geo._snapshot(context).identity
    before_rng = geo.core.initial._rng_stream(context.parent.rng).identity
    source_flatten, source_deepcopy = geo.source.flatten, geo.source.copy.deepcopy

    if helper == "flatten":
        flatten = namespace["tb"].flatten
        namespace["tb"].flatten = FunctionType(
            flatten.__code__,
            flatten.__globals__,
            flatten.__name__,
            flatten.__defaults__,
            flatten.__closure__,
        )
    elif helper == "flatten_code":
        flatten = namespace["tb"].flatten
        monkeypatch.setattr(flatten, "__code__", flatten.__code__.replace())
    elif helper == "deepcopy":
        namespace["tb"].flatten.__globals__["copy"].deepcopy = lambda value: value
    elif helper == "math_object":
        namespace["math"] = SimpleNamespace(pi=namespace["math"].pi)
    elif helper == "pi_value":
        assert namespace["math"].pi.hex() == "0x1.921fb54442d18p+1"
        namespace["math"].pi = float.fromhex("0x1.921fb54442d19p+1")
    elif helper == "pi_type":

        class OtherFloat(float):
            pass

        namespace["math"].pi = OtherFloat(namespace["math"].pi)
    elif helper == "log_method":
        namespace["logs"].log_info = lambda *args: None
    elif helper == "log_code":
        method = namespace["logs"].log_info.__func__
        monkeypatch.setattr(method, "__code__", method.__code__.replace())
    elif helper == "log_context":
        namespace["logs"].context = SimpleNamespace(logs=context.logs)
    else:
        target, name = namespace["np"], helper
        if helper.startswith("linalg."):
            target, name = target.linalg, helper.split(".")[1]
        setattr(target, name, lambda *args, **kwargs: None)
    assert geo._snapshot(context).identity == before_state
    assert geo.core.initial._rng_stream(context.parent.rng).identity == before_rng
    assert geo.source.flatten is source_flatten and geo.source.copy.deepcopy is source_deepcopy
    with pytest.raises(geo.GeometryRejected) as caught:
        _ = owner.cells
    save(evidence, "refusal", caught.value)
    assert caught.value.stage == "geometry_drift"
    expected = {
        "pi_value": "Geometry math.pi value changed",
        "pi_type": "Geometry math.pi type changed",
        "log_context": "Geometry log observer context changed",
    }.get(helper, "Original mesh/caller callable or code identity changed")
    assert str(caught.value.source_error) == expected
    assert context.request.caller_owner in geo.completion._FORWARDED
    save(evidence, "unchanged-state-and-rng", (before_state, before_rng))


def test_software_unchanged_helpers_observer_and_exact_typed_pi_remain_usable(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    isolated_helpers(monkeypatch)
    owner = geo.prepare(h.request)
    context = geo._authority(owner)
    cells = owner.cells
    namespace = context.methods["cellVerts"].__globals__
    original_pi = namespace["math"].pi
    namespace["math"].pi = float.fromhex(original_pi.hex())
    assert namespace["math"].pi is not original_pi
    assert namespace["logs"].context is context
    assert namespace["logs"].log_info.__self__ is namespace["logs"]

    def forbidden(*args, **kwargs):
        raise AssertionError("Consumed completion validator must not be reopened")

    monkeypatch.setattr(geo.completion, "_validate", forbidden)
    assert owner.cells is cells and owner.cells is cells
    assert tuple(h.calls) == geo.METHODS
    save(evidence, "trial", owner.trial)
