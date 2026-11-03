"""Pure source/ownership controls; every real multi-cell native entry is blocked."""

import ast
import hashlib
import json
import os
import pickle
import sys
from collections import OrderedDict
from dataclasses import dataclass, fields, replace
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_multi_cell_caller as multi
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


@pytest.fixture
def evidence(request, tmp_path):
    path = (
        Path(os.environ.get("CELLS_MULTI_CALLER_EVIDENCE", str(tmp_path)))
        / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    )
    path.mkdir(parents=True, exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def typed(cls, **values):
    return cls(**{field.name: values.get(field.name) for field in fields(cls)})


def inputs():
    cache = multi.core.caches.snapshot({})
    stream = multi.core.caches.snapshot(dict(synthetic_stream=0))
    recipe = dict(world_len_m=4.0, cell_radius_m=0.5, lattice_disorder=0.0, lattice_type="SQUARE")
    controls = dict(
        kind=multi.initial.image_stage.CONTROLS_KIND,
        single_cell=False,
        svg_override=False,
        alpha_shape=0.05,
        use_centroids=False,
        refine_mesh=False,
        maximum_voronoi_steps=10,
        voronoi_convergence=2.5,
    )
    conf = {"world options": {"cell height": "2.5", "cell spacing": "0.25"}}
    points = np.asarray([[0.0, 0.0], [1.0, 0.0]])
    binding = typed(
        multi.initial.image_stage.lattice.Binding,
        definition_json=json.dumps(recipe),
        identity="synthetic-binding",
    )
    seed = typed(
        multi.initial.image_stage.lattice.SeedState,
        stream_before=stream,
        stream_after=stream,
        identity="synthetic-seed",
    )
    image = typed(multi.initial.image_stage.ImageSource, identity="synthetic-image")
    prelude = typed(
        multi.initial.image_stage.Prelude,
        image=image,
        controls_json=json.dumps(controls),
        next_method="clip_and_refine",
        identity="synthetic-prelude",
    )
    ir = typed(
        multi.initial.Request,
        origin="owned_image_prelude",
        upstream=(binding, seed, prelude),
        constructor_kwargs=dict(seed_points=points),
        constructor_point_ids=("v0", "v1"),
        stream_before=stream,
        identity="synthetic-initial-request",
    )
    state = typed(
        multi.initial.State,
        request_identity=ir.identity,
        cache=cache,
        constructed_cache=cache,
        events=(),
        retained_point_ids=("v0", "v1"),
        stream_before=stream,
        stream_after=stream,
        stream_after_constructor=stream,
        warnings=(),
        constructor_completed=True,
        pre_mesh_completed=True,
        status="source_completed_unqualified",
        identity="synthetic-initial",
    )
    cr = multi.clipped.Request(ir, state, "synthetic-clip-request")
    cs = typed(
        multi.clipped.State,
        request_identity=cr.identity,
        cache=cache,
        events=(),
        warnings=(),
        retained_point_ids=("v0", "v1"),
        stream_after=stream,
        status="source_clipped_rebuilt_unqualified",
        identity="synthetic-clip",
    )
    lr = multi.lifecycle.Request(
        cr, cs, "owned_make_voronoi_lifecycle", "{}", "synthetic-lifecycle-request"
    )
    ls = typed(
        multi.lifecycle.State,
        request_identity=lr.identity,
        before_cache=cache,
        cache=cache,
        events=(),
        warnings=(),
        point_ids_after=("v0", "v1"),
        stream_after=stream,
        status="source_lifecycle_completed_unqualified",
        identity="synthetic-lifecycle",
    )
    request = multi.from_lifecycle(lr, ls, conf, law_id=multi.LAW_ID)
    return SimpleNamespace(
        request=request,
        lr=lr,
        ls=ls,
        ir=ir,
        state=state,
        cr=cr,
        cs=cs,
        points=points,
        conf=conf,
        controls=controls,
        stream=stream,
        recipe=recipe,
    )


def harness(monkeypatch, *, failure=None):
    h = inputs()
    h.events, h.errors, h.hooks = [], {}, {}
    h.rng = SimpleNamespace(epoch=0)
    h.mask = SimpleNamespace(
        clipping_matrix=np.asarray([[0.0, 1.0], [1.0, 0.0]]),
        clipcurve=np.asarray([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]),
        msize=2,
        clipping_function=lambda x, y: 1.0,
    )
    h.mask_record = dict(
        kind="owned_image_prelude_mask_token",
        identity="synthetic-prelude",
        image_identity="synthetic-image",
        xpts_m=np.asarray([0.0, 1.0]),
        ypts_m=np.asarray([0.0, 1.0]),
        clipping_matrix=h.mask.clipping_matrix,
        clipcurve_m=h.mask.clipcurve,
    )
    h.mask.additional_audit_payload = np.asarray([0.0])

    def image_state(context):
        return multi.core.caches.snapshot(
            dict(synthetic_image_payload=h.mask.additional_audit_payload)
        )

    monkeypatch.setattr(multi, "_image_state", image_state)
    attributes = dict(
        tri_verts=h.points,
        single_cell=False,
        make_all_operators=False,
        image_mask=None,
        vcell_verts=np.asarray([[[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]]),
        vor_verts=h.mask.clipcurve,
        vor_cents=np.asarray([[0.25, 0.25]]),
        vor_sa=np.asarray([0.5]),
    )
    initial_cache = multi.core.caches.snapshot(attributes)
    clip_cache = multi.core.caches.snapshot(dict(attributes, image_mask=h.mask_record))
    final_cache = multi.core.caches.snapshot(
        dict(attributes, image_mask=h.mask_record, delta_tri_0=np.asarray([[-1.0, 1.0]]))
    )
    event = multi.initial.Event(
        0,
        "clip_continuation_start",
        "driver",
        0,
        multi.core.caches.snapshot(dict(initial_cache=attributes, parent_point_ids=("v0", "v1"))),
    )
    h.state = replace(h.state, cache=initial_cache)
    h.cr = replace(h.cr, initial_state=h.state)
    h.cs = replace(h.cs, cache=clip_cache, events=(event,))
    h.lr = replace(h.lr, clip_request=h.cr, clip_state=h.cs)
    h.ls = replace(h.ls, cache=final_cache)
    h.request = multi.from_lifecycle(h.lr, h.ls, h.conf, law_id=multi.LAW_ID)
    pins = {"synthetic-producer": "software-only"}
    monkeypatch.setattr(multi, "_verify_sources", lambda: dict(pins))
    monkeypatch.setattr(
        multi.initial,
        "_rng_stream",
        lambda rng: (
            h.stream
            if rng is h.rng and rng.epoch == 0
            else multi.core.caches.snapshot(dict(changed_RNG=True))
        ),
    )

    def step(name, context=None):
        h.events.append(name)
        if name in h.hooks:
            h.hooks[name](context)
        if name == failure:
            try:
                raise SyntheticSourceCause("original synthetic source cause")
            except SyntheticSourceCause as cause:
                error = SyntheticSourceFailure("synthetic source failure at " + name)
                h.errors.update(source=error, cause=cause)
                raise error from cause

    def stores(p):
        p.plot_grid_size, p.wsx, p.wsy = 50, 4.0, 4.0
        p.cell_height, p.cell_space = 2.5, 0.25
        for name in (
            "single_cell",
            "svg_override",
            "alpha_shape",
            "use_centroids",
            "refine_mesh",
            "maximum_voronoi_steps",
            "voronoi_convergence",
        ):
            setattr(p, name, h.controls[name])
        p.ac, p.scale_cell, p.tm = 1e-6, 0.99, 7.5e-9
        p.d_cell, p.nx, p.ny = 1.0, 4, 4
        step("parameters")

    def init(caller, p):
        caller.clust_xy = h.points
        caller.bbox = np.asarray([[0.0, 0.0], [1.0, 1.0]])
        caller.centre = np.asarray([0.5, 0.5])
        step("caller")

    def constructor(mesh, **kwargs):
        assert kwargs["seed_points"] is h.points
        vars(mesh).update(attributes)
        step("constructor", multi._context(mesh))

    def pre_mesh(mesh):
        step("pre_mesh", multi._context(mesh))

    def clip(mesh, mask):
        mesh.image_mask = mask
        step("clip", multi._context(mesh))

    def core(mesh):
        mesh.delta_tri_0 = np.asarray([[-1.0, 1.0]])
        step("core", multi._context(mesh))

    def index(caller, p):
        caller.cell_centres = caller.mesh.vor_cents
        caller.cell_vol = np.asarray([1.25])
        step("index", multi._context(caller))

    monkeypatch.setattr(multi, "_STORES", stores)
    monkeypatch.setattr(multi, "_CELL_INIT", init)
    monkeypatch.setattr(multi, "_INDEX", index)
    for name, fn in {
        "__init__": constructor,
        "pre_mesh": pre_mesh,
        "clip_to_curve": clip,
        "create_core_operators": core,
    }.items():
        monkeypatch.setattr(multi._Runtime, name, multi._guard(name, fn))

    def tools_init(tools, observer):
        tools._cells_observer = observer

    monkeypatch.setattr(multi._Tools, "__init__", multi._guard("__init__", tools_init, tool=True))
    values = dict(multi.source.__dict__)
    exec(
        compile(
            "def voronoi(self,p,image_mask):\n"
            "    self.mesh=DECMesh(seed_points=self.clust_xy)\n"
            "    self.mesh.clip_and_refine(image_mask)\n"
            "    self.ecm_verts=self.mesh.vcell_verts\n"
            "    self.cluster_mask=image_mask.clipping_matrix\n"
            "    self.msize=image_mask.msize\n"
            "    self.ecm_verts_unique=self.mesh.vor_verts\n"
            "def pipeline(self,imagemask,smoothing=None,refinement=True,"
            "max_steps=25,convergence=7.5,fix_bounds=True):\n"
            "    self.pre_mesh()\n"
            "    self.clip_to_curve(imagemask)\n"
            "    self.create_core_operators()\n",
            "<synthetic-multi-cell>",
            "exec",
        ),
        values,
    )
    monkeypatch.setattr(multi, "_VORONOI", values["voronoi"])
    monkeypatch.setattr(multi, "_PIPELINE", values["pipeline"])

    def execute(context):
        context.initial_request, context.initial_state = h.ir, h.state
        context.clip_state, context.prelude = h.cs, h.ir.upstream[2]
        step("authentication", context)
        context.stage = "fresh_parameters"
        context.p = object.__new__(multi._Parameters)
        monkeypatch.setitem(multi._ACTIVE, context.p, context)
        context.p.__init__(h.recipe, json.loads(h.request.configuration_json))
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
        context.lattice_audit = multi.core.caches.snapshot(dict(synthetic=True))
        context.image_audit = image_state(context)
        context.lattice_method = lambda *a: None
        context.caller_method, context.pipeline = multi._namespaces(context)
        context.namespace_bindings = multi._namespace_bindings(context)
        context.native_entry_codes = multi._entry_codes(context)
        context.caller = object.__new__(multi._Caller)
        monkeypatch.setitem(multi._ACTIVE, context.caller, context)
        context.caller.__init__(context.p)
        context.executing = True
        context.caller_method(context.caller, context.p, context.mask)
        multi._compare_mesh(context, h.ls)
        context.caller.cell_index(context.p)
        context.finished = True
        multi._check(context)

    monkeypatch.setattr(multi, "_execute", execute)
    return h


def test_software_source_projection_native_clip_order_and_no_phase_fabrication(evidence):
    save(evidence, "source-pins", multi._verify_sources())
    assert multi.source.STORE_LINES.index(521) < multi.source.STORE_LINES.index(533)
    assert multi.source.STORE_LINES.index(546) < multi.source.STORE_LINES.index(1118)
    assert multi.source.CALLER_LINES == (888, 930, 947, 954, 958, 959, 961)
    tree = ast.parse(Path(multi.source.__file__).read_text())
    assert not any(isinstance(n, ast.Name) and n.id == "phase" for n in ast.walk(tree))
    assert len(multi.INVALIDATED_OWNERS) == 11


@pytest.mark.parametrize(
    "kind",
    [
        "mapping",
        "initial_failed",
        "clip_failed",
        "lifecycle_failed",
        "single",
        "SVG",
        "late_SVG",
        "native_options",
        "law",
    ],
)
def test_software_missing_failed_wrong_branch_parents_refuse_without_authentication(
    kind, monkeypatch, evidence
):
    h = inputs()
    calls = []
    monkeypatch.setattr(multi, "_authenticate", lambda *a: calls.append("forbidden"))
    lr, ls, conf, law = h.lr, h.ls, h.conf, multi.LAW_ID
    if kind == "initial_failed":
        lr = replace(
            lr,
            clip_request=replace(
                h.cr, initial_state=replace(h.state, status="retained_source_failure")
            ),
        )
    elif kind == "clip_failed":
        lr = replace(lr, clip_state=replace(h.cs, status="retained_source_failure"))
    elif kind == "lifecycle_failed":
        ls = replace(ls, status="retained_source_failure")
    elif kind in {"single", "SVG"}:
        controls = dict(h.controls, **{"single_cell" if kind == "single" else "svg_override": True})
        prelude = replace(h.ir.upstream[2], controls_json=json.dumps(controls))
        ir = replace(h.ir, upstream=(*h.ir.upstream[:2], prelude))
        lr = replace(lr, clip_request=replace(h.cr, initial_request=ir))
    elif kind == "late_SVG":
        conf["world options"]["import from svg"] = {"svg override": False}
    elif kind == "native_options":
        lr = replace(lr, origin="manufactured_native_api_options")
    elif kind == "law":
        law = "supplied-state"
    with pytest.raises(multi.MultiCellRejected) as caught:
        if kind == "mapping":
            multi.prepare(dict(lifecycle=lr))
        else:
            multi.from_lifecycle(lr, ls, conf, law_id=law)
    assert calls == []
    save(evidence, "refusal", caught.value)


def test_software_default_authentication_stops_before_live_constructor(monkeypatch, evidence):
    h = inputs()
    failure = SyntheticSourceFailure("unavailable upstream authority")

    def refuse(*a):
        raise failure

    monkeypatch.setattr(multi.lifecycle, "validate_state", refuse)
    with pytest.raises(multi.MultiCellRejected) as caught:
        multi.prepare(h.request)
    save(evidence, "failure", caught.value)
    assert caught.value.source_error is failure
    assert caught.value.partial["caller"] is caught.value.partial["kernel"] is None
    assert caught.value.partial["parent_trials"] == (h.state, h.cs, h.ls)


def test_software_actual_identity_order_aliases_mask_and_work_with_synthetic_bodies(
    monkeypatch, evidence
):
    h = harness(monkeypatch)
    owner = multi.prepare(h.request)
    context = multi._authority(owner)
    save(evidence, "trial", owner.trial)
    assert h.events == [
        "authentication",
        "parameters",
        "caller",
        "constructor",
        "pre_mesh",
        "clip",
        "core",
        "index",
    ]
    assert owner.cells is context.caller and owner.cells.mesh is context.kernel
    assert owner.cells.mesh.image_mask is context.mask is h.mask
    assert context.kernel._cells_rng.rng is h.rng
    assert owner.cells.ecm_verts is context.kernel.vcell_verts
    assert owner.cells.cell_centres is context.kernel.vor_cents
    assert owner.cells.cluster_mask is context.mask.clipping_matrix
    assert owner.trial.stream_before.identity == owner.trial.stream_after.identity
    assert any(row["entry_method"] == "clip_to_curve" for row in owner.trial.work)
    assert all(row["status"] == "entered_not_success_credit" for row in owner.trial.work)
    assert context.p.plot_grid_size == 50
    assert [name for name, _ in owner.trial.stages] == [
        "__init__",
        "pre_mesh",
        "clip_to_curve",
        "create_core_operators",
        "cell_index",
    ]
    with pytest.raises(TypeError):
        pickle.dumps(owner)
    with pytest.raises(multi.MultiCellRejected) as caught:
        multi.require_initial_geometry(owner, phase=SimpleNamespace())
    assert caught.value.stage == "initial_geometry_held"
    save(evidence, "next-boundary", caught.value)


@pytest.mark.parametrize(
    "stage",
    ["authentication", "parameters", "caller", "constructor", "pre_mesh", "clip", "core", "index"],
)
def test_software_failure_keeps_original_cause_parent_trials_and_partial_assignment(
    stage, monkeypatch, evidence
):
    h = harness(monkeypatch, failure=stage)
    with pytest.raises(multi.MultiCellRejected) as caught:
        multi.prepare(h.request)
    error = caught.value
    save(evidence, "failure", error)
    assert error.source_error is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert error.partial["parent_trials"] == (h.state, h.cs, h.ls)
    assert not any(c.request is h.request for c in multi._ISSUED.values())
    if stage in {"pre_mesh", "clip", "core", "index"}:
        assert error.partial["caller"].mesh is error.partial["kernel"]
    if error.partial["kernel"] is not None:
        with pytest.raises(multi.MultiCellRejected):
            error.partial["kernel"].pre_mesh()
    caller, kernel, p = (error.partial[name] for name in ("caller", "kernel", "parameters"))
    # Archive actual selected buffers/aliases without traversing module/class
    # bindings or pretending to serialize a complete executable native object.
    save(
        evidence,
        "retained-state",
        dict(
            caller=None
            if caller is None
            else {k: v for k, v in multi.callers._public(caller).items() if k != "mesh"},
            kernel=None if kernel is None else multi.initial._public_cache(kernel),
            parameters=None if p is None else multi.callers._parameters(p),
            parents=error.partial["parent_trials"],
            stage=error.partial["stage"],
            ordering=[kind for kind, _ in error.partial["events"]],
            work=error.partial["work"],
        ),
    )


@pytest.mark.parametrize(
    "change",
    [
        "caller_array",
        "equal_mask_alias",
        "kernel_array",
        "parameter",
        "RNG",
        "observer",
        "mesh_method",
        "caller_method",
        "helper",
        "events",
        "upstream_cache",
        "upstream_trial",
        "image_payload",
    ],
)
def test_software_issued_owner_refuses_value_alias_callable_event_and_epoch_drift(
    change, monkeypatch, evidence
):
    h = harness(monkeypatch)
    owner = multi.prepare(h.request)
    context = multi._authority(owner)
    if change == "caller_array":
        context.caller.cell_vol[0] = 9.0
    elif change == "equal_mask_alias":
        context.caller.cluster_mask = h.mask.clipping_matrix.copy()
    elif change == "kernel_array":
        context.kernel.delta_tri_0[0, 0] = 9.0
    elif change == "parameter":
        context.p.cell_height = 9.0
    elif change == "RNG":
        h.rng.epoch = 1
    elif change == "observer":
        context.kernel._cells_rng.observer = object()
    elif change == "mesh_method":
        monkeypatch.setattr(multi._Runtime, "pre_mesh", lambda *a: None)
    elif change == "caller_method":
        monkeypatch.setattr(multi._Caller, "cell_index", lambda *a: None)
    elif change == "helper":
        monkeypatch.setattr(multi.initial.np, "sqrt", lambda *a: None)
    elif change == "events":
        context.observer.events[0] = replace(context.observer.events[0], kind="changed")
    elif change == "upstream_cache":
        values = h.state.cache.columns[0].values
        with pytest.raises(ValueError):
            values.setflags(write=True)
        corrupted = values.copy()
        corrupted.flat[0] += 1
        object.__setattr__(h.state.cache.columns[0], "values", corrupted)
    elif change == "image_payload":
        h.mask.additional_audit_payload[0] = 9.0
    else:
        object.__setattr__(h.lr, "clip_state", replace(h.cs))
    with pytest.raises(multi.MultiCellRejected) as caught:
        _ = owner.cells
    assert caught.value.stage == "caller_drift"
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize("part", ["trial", "identity", "graphs"])
@pytest.mark.parametrize("source_failure", [False, True])
def test_software_sealing_preserves_original_parent_and_primary_separately(
    part, source_failure, monkeypatch, evidence
):
    h = harness(monkeypatch, failure="core" if source_failure else None)
    capture = SyntheticCaptureFailure("synthetic sealing failure")
    if part == "trial":
        monkeypatch.setattr(multi, "Trial", lambda *a: (_ for _ in ()).throw(capture))
    elif part == "identity":
        monkeypatch.setattr(multi, "trial_record", lambda *a: (_ for _ in ()).throw(capture))
    else:
        monkeypatch.setattr(multi, "_graphs", lambda *a: (_ for _ in ()).throw(capture))
    with pytest.raises(multi.MultiCellRejected) as caught:
        multi.prepare(h.request)
    error = caught.value
    save(evidence, "failure", error)
    assert error.partial["parent_trials"] == (h.state, h.cs, h.ls)
    assert error.source_error is (h.errors["source"] if source_failure else None)
    assert error.capture_error is (None if source_failure and part == "graphs" else capture)
    assert not any(c.request is h.request for c in multi._ISSUED.values())


def test_software_raw_native_methods_and_reentrant_pipeline_never_rearm(monkeypatch, evidence):
    h = harness(monkeypatch)
    blocked = []

    def reenter(context):
        for call in (
            lambda: context.kernel.make_single_cell_points(),
            lambda: context.kernel.clip_and_refine(h.mask),
            lambda: context.kernel._cells_tools.clip_counterclockwise([], []),
        ):
            with pytest.raises(multi.MultiCellRejected) as caught:
                call()
            blocked.append(caught.value)

    h.hooks["core"] = reenter
    owner = multi.prepare(h.request)
    context = multi._authority(owner)
    for name in ("make_single_cell_points", "pre_mesh", "create_core_operators", "clip_to_curve"):
        with pytest.raises(multi.MultiCellRejected):
            getattr(context.kernel, name)()
    assert len(blocked) == 3
    save(evidence, "refusals", blocked)


@pytest.mark.parametrize("unwind", [False, True])
def test_software_local_observer_capture_preserves_primary_trace_and_native_guard(unwind, evidence):
    capture = SyntheticCaptureFailure("synthetic local observer capture failure")
    primary = SyntheticSourceFailure("synthetic primary source failure")

    def synthetic_source():
        if unwind:
            raise primary
        return "completed synthetic source"

    def broken(*a):
        raise capture

    context = SimpleNamespace(
        tape=SimpleNamespace(codes={synthetic_source.__code__}, trace=broken),
        image_tape=SimpleNamespace(trace=lambda *a: None),
        local_codes={synthetic_source.__code__},
        mask=None,
        observer=None,
        locals={},
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
    )
    previous, guard = sys.gettrace(), sys.getprofile()
    with multi._capture(context):
        if unwind:
            with pytest.raises(SyntheticSourceFailure) as caught:
                synthetic_source()
            assert caught.value is primary
        else:
            assert synthetic_source() == "completed synthetic source"
    assert sys.gettrace() is previous and sys.getprofile() is guard
    assert context.observation_error is capture
    with pytest.raises(multi._CaptureStop):
        multi._stop(context)
    save(evidence, "capture", capture)
    save(evidence, "primary", primary if unwind else None)


@pytest.mark.parametrize("stage", ["__init__", "clip_to_curve", "cell_index"])
def test_software_stage_snapshot_capture_stops_next_source_and_keeps_previous_buffers(
    stage, monkeypatch, evidence
):
    h = harness(monkeypatch)
    capture = SyntheticCaptureFailure("synthetic stage snapshot failure")
    original = multi._execute

    class Stages(list):
        def append(self, value):
            if value[0] == stage:
                raise capture
            return super().append(value)

    def execute(context):
        context.stages = Stages()
        return original(context)

    monkeypatch.setattr(multi, "_execute", execute)
    with pytest.raises(multi.MultiCellRejected) as caught:
        multi.prepare(h.request)
    error = caught.value
    save(evidence, "failure", error)
    save(evidence, "previous-snapshots", error.partial["last_successful_snapshots"])
    assert error.source_error is None and error.capture_error is capture
    assert not any(c.request is h.request for c in multi._ISSUED.values())
    if stage == "__init__":
        assert "pre_mesh" not in h.events and not hasattr(error.partial["caller"], "mesh")
    elif stage == "clip_to_curve":
        assert "core" not in h.events and len(error.partial["last_successful_snapshots"]) == 2
    else:
        assert error.partial["caller"].cell_centres is error.partial["kernel"].vor_cents


def mask_token_fixture(h=None, *, side=4):
    h = inputs() if h is None else h
    # Real NumPy storage/view fixtures only; no image, spline or native work.
    base = np.zeros((side, side))
    base[0, 0] = base[-1, -1] = 1.0
    live = base[::-1]

    def frozen(value):
        return multi.core.caches.snapshot(value).columns[0].values

    stored = frozen(live)
    if not hasattr(h, "mask"):
        h.mask = SimpleNamespace(
            clipping_matrix=live,
            msize=side,
            clipcurve=np.asarray([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]),
        )
        h.mask_record = dict(xpts_m=np.linspace(0.0, 1.0, side), ypts_m=np.linspace(0.0, 1.0, side))
    else:
        # Keep the old synthetic token pixel bytes exactly, while giving the
        # actual live mask its original row-flip allocation/view relationship.
        base[:] = h.mask.clipping_matrix[::-1]
        stored = frozen(live)
    h.mask.clipping_matrix = live
    bitmap = frozen(np.asarray((base == 0) * 255, dtype=float))
    prelude = h.ir.upstream[2]
    image = replace(prelude.image, bitmap=bitmap)
    values = dict.fromkeys(multi.initial.image_stage.MaskValues._fields, frozen(np.asarray([])))
    values.update(
        bitmap=bitmap,
        clipping_matrix=stored,
        xpts_m=frozen(h.mask_record["xpts_m"]),
        ypts_m=frozen(h.mask_record["ypts_m"]),
        clipcurve_m=frozen(h.mask.clipcurve),
    )
    prelude = replace(prelude, image=image, values=multi.initial.image_stage.MaskValues(**values))
    h.ir = replace(h.ir, upstream=(*h.ir.upstream[:2], prelude))
    h.cr = replace(h.cr, initial_request=h.ir)
    h.lr = replace(h.lr, clip_request=h.cr)
    h.request = multi.from_lifecycle(h.lr, h.ls, h.conf, law_id=multi.LAW_ID)
    h.synthetic_constructor_locals = dict(self=h.mask, bitmap=bitmap)
    local = dict(
        h.synthetic_constructor_locals, xpts=h.mask_record["xpts_m"], ypts=h.mask_record["ypts_m"]
    )
    context = SimpleNamespace(
        request=h.request,
        prelude=prelude,
        mask=h.mask,
        image_tape=SimpleNamespace(
            image=image, mask=h.mask, locals={"TissuePickerImageMask.__init__": local}
        ),
        work_context=SimpleNamespace(work=[]),
        mask_token_comparisons=[],
        stage="clip_to_curve",
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
    )
    actual = multi.core.caches.snapshot(dict(image_mask=multi._mask_record(context)))
    expected = multi.core.caches.snapshot(dict(image_mask=multi.clipped.mask_record(h.cr)))
    h.bridge_context, h.live_base, h.live_view, h.stored = context, base, live, stored
    h.actual_token_cache, h.retained_token_cache = actual, expected
    return h


@pytest.mark.parametrize("side", [1, 2, 4])
def test_software_mask_token_bridge_exact_distinct_layouts_keep_actual_view_and_raw_caches(
    side, evidence
):
    h = mask_token_fixture(side=side)
    context, actual, expected = h.bridge_context, h.actual_token_cache, h.retained_token_cache
    original = (actual.descriptor_json, expected.descriptor_json)
    assert actual.identity != expected.identity
    assert h.live_view.base is h.live_base and h.live_view.strides == (-8 * side, 8)
    assert multi._same_source_cache(context, actual, expected)
    assert context.mask.clipping_matrix is h.live_view
    assert (actual.descriptor_json, expected.descriptor_json) == original
    assert len(context.mask_token_comparisons) == 1
    proof = context.mask_token_comparisons[0]
    assert proof["actual_matrix_layout"]["strides_bytes"] == [-8 * side, 8]
    assert proof["retained_matrix_layout"]["strides_bytes"] == [8 * side, 8]
    assert proof["actual_cache"] == actual.identity and proof["retained_cache"] == expected.identity
    assert proof["live_mask_or_array_replaced"] is False
    assert multi._same_source_cache(context, expected, expected)
    assert len(context.mask_token_comparisons) == 1  # Exact path needs no bridge.
    save(
        evidence,
        "comparison",
        dict(
            actual=actual,
            retained=expected,
            proof=proof,
            live_layout=multi.core.caches.layout(h.live_view),
        ),
    )


@pytest.mark.parametrize(
    "change",
    [
        "live_pixels",
        "stored_signed_zero",
        "column_flip",
        "transpose",
        "contiguous_copy",
        "flattened_base",
        "local_owner",
        "tape_owner",
        "prelude_owner",
        "live_readonly",
        "base_readonly",
    ],
)
def test_software_mask_token_bridge_refuses_other_views_bits_or_constructor_owners(
    change, evidence
):
    h = mask_token_fixture()
    context = h.bridge_context
    if change == "live_pixels":
        h.live_view[0, 0] += 1.0
    elif change == "stored_signed_zero":
        new = h.stored.copy()
        new[0, 0] = -0.0
        assert np.array_equal(new, h.stored)
        values = context.prelude.values._replace(
            clipping_matrix=multi.core.caches.snapshot(new).columns[0].values
        )
        object.__setattr__(context.prelude, "values", values)
    elif change == "column_flip":
        context.mask.clipping_matrix = h.live_base[:, ::-1]
    elif change == "transpose":
        context.mask.clipping_matrix = h.live_base.T[::-1]
    elif change == "contiguous_copy":
        context.mask.clipping_matrix = h.live_view.copy()
    elif change == "flattened_base":
        context.mask.clipping_matrix = np.arange(16.0).reshape(4, 4)[::-1]
    elif change == "local_owner":
        context.image_tape.locals["TissuePickerImageMask.__init__"]["self"] = SimpleNamespace()
    elif change == "tape_owner":
        context.image_tape.mask = SimpleNamespace()
    elif change == "prelude_owner":
        context.prelude = replace(context.prelude)
    elif change == "live_readonly":
        h.live_view.setflags(write=False)
    else:
        h.live_base.setflags(write=False)
    with pytest.raises(ValueError) as caught:
        multi._mask_layout_bridge(context)
    assert context.mask_token_comparisons == []
    save(
        evidence,
        "refusal",
        dict(
            change=change,
            error=caught.value,
            live=multi.core.caches.snapshot(context.mask.clipping_matrix),
        ),
    )


@pytest.mark.parametrize(
    "change",
    [
        "other_array_layout",
        "token_pixels",
        "token_layout",
        "token_identity",
        "token_extra",
        "token_missing",
        "stranger_token",
    ],
)
def test_software_mask_token_bridge_changes_only_the_exact_owned_matrix_descriptor(
    change, evidence
):
    h = mask_token_fixture()
    context = h.bridge_context
    actual_token, expected_token = multi._mask_record(context), multi.clipped.mask_record(h.cr)
    other = np.arange(4.0).reshape(2, 2)[::-1]
    actual, expected = dict(image_mask=actual_token), dict(image_mask=expected_token)
    if change == "other_array_layout":
        actual["unrelated"] = other
        expected["unrelated"] = other.copy()
    elif change == "token_pixels":
        altered = h.live_base.copy()[::-1]
        altered[0, 0] = 1.0
        actual_token["clipping_matrix"] = altered
    elif change == "token_layout":
        actual_token["clipping_matrix"] = np.array(h.live_view, order="F")
    elif change == "token_identity":
        actual_token["identity"] = "unrelated"
    elif change == "token_extra":
        actual_token["extra"] = expected_token["extra"] = 1
    elif change == "token_missing":
        del actual_token["xpts_m"]
        del expected_token["xpts_m"]
    else:
        actual_token["kind"] = expected_token["kind"] = "unowned_mask_token"
    actual_cache, expected_cache = map(multi.core.caches.snapshot, (actual, expected))
    try:
        matched = multi._same_source_cache(context, actual_cache, expected_cache)
    except ValueError as error:
        matched = False
        save(evidence, "error", error)
    assert matched is False and context.mask_token_comparisons == []
    save(
        evidence,
        "refused-caches",
        dict(actual=actual_cache, retained=expected_cache, change=change),
    )


@pytest.mark.parametrize(
    "change", [None, "header", "payload_pixels", "payload_other_layout", "IDs", "RNG", "warning"]
)
def test_software_mask_token_bridge_events_preserve_headers_ids_rng_and_warnings(
    change, monkeypatch, evidence
):
    h = mask_token_fixture()
    context = h.bridge_context
    stream = multi.core.caches.snapshot(dict(synthetic_epoch=1))
    context.rng, context.caught, context.mesh_warning_offset = SimpleNamespace(), [], 0
    monkeypatch.setattr(multi.initial, "_rng_stream", lambda rng: stream)
    monkeypatch.setattr(multi, "_mesh_cache", lambda ctx: h.actual_token_cache)
    actual_payload = dict(call_parameters=dict(imagemask=multi._mask_record(context)))
    expected_payload = dict(call_parameters=dict(imagemask=multi.clipped.mask_record(h.cr)))
    if change == "payload_pixels":
        actual_payload["call_parameters"]["imagemask"]["clipping_matrix"] = np.ones((4, 4))
    elif change == "payload_other_layout":
        view = np.zeros((2, 2))[::-1]
        actual_payload["other"] = view
        expected_payload["other"] = view.copy()
    actual_event = multi.initial.Event(
        0, "method_enter", "clip_to_curve", 1, multi.core.caches.snapshot(actual_payload)
    )
    expected_event = replace(actual_event, payload=multi.core.caches.snapshot(expected_payload))
    if change == "header":
        actual_event = replace(actual_event, depth=2)
    context.observer = SimpleNamespace(ids=("v0",), events=[actual_event])
    state = typed(
        multi.clipped.State,
        cache=h.retained_token_cache,
        retained_point_ids=("v0",),
        stream_after=stream,
        warnings=(),
        events=(expected_event,),
    )
    if change == "IDs":
        context.observer.ids = ("wrong",)
    elif change == "RNG":
        state = replace(state, stream_after=multi.core.caches.snapshot(dict(synthetic_epoch=2)))
    elif change == "warning":
        state = replace(state, warnings=("different warning",))
    if change is None:
        multi._compare_mesh(context, state)
        assert len(context.mask_token_comparisons) == 2
    else:
        with pytest.raises(ValueError) as caught:
            multi._compare_mesh(context, state)
        save(evidence, "refusal", caught.value)
    save(
        evidence,
        "events",
        dict(
            actual=actual_event, retained=expected_event, comparisons=context.mask_token_comparisons
        ),
    )


def test_software_mask_token_bridge_full_blocked_caller_keeps_actual_mask_and_seals_comparison_work(
    monkeypatch, evidence
):
    h = mask_token_fixture(harness(monkeypatch), side=2)
    child = multi.prepare(h.request)
    context = multi._authority(child)
    assert child.cells.mesh.image_mask is h.mask
    assert child.cells.cluster_mask is h.live_view
    assert context.mask.clipping_matrix.base is h.live_base
    assert len(context.mask_token_comparisons) >= 2
    assert any(row["layer"] == "owned_mask_token_layout_bridge" for row in child.trial.work)
    # Snapshot retains original negative strides; only comparison descriptors
    # use the stored token's positive layout, never the source computation.
    raw = multi.core.caches.plain(child.trial.mesh_cache)
    assert raw["image_mask"]["clipping_matrix"] == h.stored.tolist()
    save(evidence, "trial", child.trial)
    save(evidence, "bridge-proofs", context.mask_token_comparisons)
    save(
        evidence, "live-view", dict(layout=multi.core.caches.layout(h.live_view), base=h.live_base)
    )


@pytest.fixture
def lineage_plans(monkeypatch):
    # This is a descriptor-only test cache, never an issued caller or parent.
    plans = OrderedDict()
    monkeypatch.setattr(multi, "_LINEAGE_PLANS", plans)
    multi._lineage_memoized_descriptor.cache_clear()
    try:
        yield plans
    finally:
        multi._lineage_memoized_descriptor.cache_clear()


def _lineage_cache_fixture(kind="mixed"):
    if kind == "empty":
        value = dict(empty=(), scalar=7)
    elif kind == "nonfinite":
        value = dict(array=np.asarray([np.inf, np.nan]), scalar=np.float64(np.inf), raw=-np.inf)
    elif kind == "object":
        value = np.empty(2, dtype=object)
        value[0], value[1] = np.asarray([1, 2], dtype=np.int16), [None, -0.0]
    elif kind == "complex":
        value = dict(array=np.asarray([1 + 2j, 0j]), scalar=np.complex128(3 - 4j))
    else:
        value = dict(
            array=np.asarray([[-0.0, 1.25]], dtype=">f8"),
            second=np.asarray([2, 3], dtype=np.int32),
            scalar=np.float64(-0.0),
            raw=-0.0,
            nested=(None, True, "text", [1, 2]),
        )
    return multi.core.caches.snapshot(value)


def _lineage_outcome(function, value):
    try:
        result = function(value)
    except Exception as error:
        return dict(
            type=type(error).__module__ + "." + type(error).__qualname__, message=str(error)
        )
    return dict(returned_same_object=result is value)


def _lineage_descriptor_cache(descriptor, columns=(), finite=True):
    raw = json.dumps(descriptor, separators=(",", ":"), ensure_ascii=False)
    return multi.core.caches.Cache(
        raw, tuple(columns), finite, hashlib.sha256(raw.encode()).hexdigest()
    )


@pytest.mark.parametrize("kind", ["mixed", "nonfinite", "empty", "object", "complex"])
def test_lineage_descriptor_cold_warm_matches_canonical(kind, monkeypatch, lineage_plans, evidence):
    cache = _lineage_cache_fixture(kind)
    canonical = multi.core.caches.validate
    assert canonical(cache) is cache
    calls = []

    def original(value):
        calls.append(value)
        return canonical(value)

    monkeypatch.setattr(multi.core.caches, "validate", original)
    assert multi._lineage_validate_cache(cache) is cache
    assert cache.descriptor_json in lineage_plans
    assert multi._lineage_validate_cache(cache) is cache
    separate = replace(cache)
    assert multi._lineage_validate_cache(separate) is separate
    assert calls == [cache]
    save(
        evidence,
        "cold-warm",
        dict(kind=kind, canonical_calls=len(calls), entries=len(lineage_plans)),
    )


@pytest.mark.parametrize(
    "change",
    [
        "identity",
        "bits",
        "dtype",
        "shape",
        "writeable",
        "missing",
        "duplicate",
        "extra",
        "name",
        "finite",
    ],
)
def test_lineage_descriptor_warm_rechecks_live_mutations(change, lineage_plans, evidence):
    cache = _lineage_cache_fixture()
    multi._lineage_validate_cache(cache)
    first, *rest = cache.columns
    changed = replace(cache)
    if change == "identity":
        changed = replace(cache, identity="0" * 64)
    elif change == "finite":
        changed = replace(cache, all_finite=not cache.all_finite)
    elif change == "missing":
        changed = replace(cache, columns=tuple(rest))
    elif change == "duplicate":
        changed = replace(cache, columns=(*cache.columns, first))
    elif change == "extra":
        changed = replace(cache, columns=(*cache.columns, replace(first, name="extra")))
    elif change == "name":
        changed = replace(cache, columns=(replace(first, name="renamed"), *rest))
    else:
        values = first.values.copy()
        if change == "bits":
            values.flat[0] = 5.0
        elif change == "dtype":
            values = values.astype(np.float32)
        elif change == "shape":
            values = values.reshape(-1)
        if change != "writeable":
            values.flags.writeable = False
        changed = replace(cache, columns=(replace(first, values=values), *rest))
    expected = _lineage_outcome(multi.core.caches.validate, changed)
    actual = _lineage_outcome(multi._lineage_validate_cache, changed)
    assert "type" in expected and actual == expected
    save(evidence, "mutation", dict(change=change, expected=expected, actual=actual))


def test_lineage_descriptor_repeated_numeric_order_and_final_membership(
    monkeypatch, lineage_plans, evidence
):
    single = multi.core.caches.snapshot(np.asarray([np.inf]))
    node = json.loads(single.descriptor_json)
    cache = _lineage_descriptor_cache(dict(kind="list", items=[node, node]), single.columns, False)
    multi._lineage_validate_cache(cache)
    finite, hashes = np.isfinite, hashlib.sha256
    observed = []

    def finite_call(value):
        observed.append(("finite", id(value)))
        return finite(value)

    def hash_call(value=b"", *args, **kwargs):
        observed.append(("hash", bytes(value)))
        return hashes(value, *args, **kwargs)

    monkeypatch.setattr(np, "isfinite", finite_call)
    monkeypatch.setattr(hashlib, "sha256", hash_call)
    assert multi.core.caches.validate(cache) is cache
    expected = tuple(observed)
    observed.clear()
    assert multi._lineage_validate_cache(cache) is cache
    assert tuple(observed) == expected
    assert sum(kind == "finite" for kind, _ in observed) == 2
    duplicate = replace(cache, columns=(cache.columns[0], cache.columns[0]))
    observed.clear()
    oracle = _lineage_outcome(multi.core.caches.validate, duplicate)
    calls = tuple(observed)
    observed.clear()
    actual = _lineage_outcome(multi._lineage_validate_cache, duplicate)
    assert actual == oracle and tuple(observed) == calls
    save(evidence, "repeated-order", dict(finite_checks=2, failure=actual))


@pytest.mark.parametrize(
    "change", ["descriptor_identity", "malformed_json", "column_before_json", "array_before_scalar"]
)
def test_lineage_descriptor_cold_error_precedence(change, monkeypatch, lineage_plans, evidence):
    cache = _lineage_cache_fixture()
    if change == "descriptor_identity":
        cache = replace(cache, identity="bad", columns=(object(),))
    elif change in ("malformed_json", "column_before_json"):
        cache = replace(cache, descriptor_json="{", identity=hashlib.sha256(b"{").hexdigest())
        if change == "column_before_json":
            cache = replace(cache, columns=(object(),))
    else:
        node = json.loads(multi.core.caches.snapshot(np.asarray([1.0])).descriptor_json)
        column = multi.core.caches.CacheColumn(node["column"], np.asarray([2.0]))
        cache = _lineage_descriptor_cache(
            dict(kind="list", items=[node, dict(kind="float", bits="invalid")]), (column,)
        )
    expected = _lineage_outcome(multi.core.caches.validate, cache)

    def forbidden_plan(raw):
        raise AssertionError("A refused cold cache must not reach plan compilation")

    monkeypatch.setattr(multi, "_lineage_descriptor_plan", forbidden_plan)
    assert _lineage_outcome(multi._lineage_validate_cache, cache) == expected
    assert not lineage_plans and "type" in expected
    save(evidence, "cold-refusal", dict(change=change, expected=expected))


@pytest.mark.parametrize(
    "reason",
    [
        "descriptor",
        "utf8",
        "nodes",
        "depth",
        "instructions",
        "entry_bytes",
        "total_bytes",
        "unknown",
        "shape_type",
        "text_subclass",
    ],
)
def test_lineage_descriptor_fallback_preserves_canonical_outcome(
    reason, monkeypatch, lineage_plans, evidence
):
    cache = _lineage_cache_fixture()
    constants = {
        "descriptor": "_LINEAGE_DESCRIPTOR_BYTES",
        "nodes": "_LINEAGE_PLAN_NODES",
        "depth": "_LINEAGE_PLAN_DEPTH",
        "instructions": "_LINEAGE_PLAN_INSTRUCTIONS",
        "entry_bytes": "_LINEAGE_PLAN_BYTES",
        "total_bytes": "_LINEAGE_RETAINED_BYTES",
    }
    if reason in constants:
        monkeypatch.setattr(
            multi, constants[reason], 0 if reason in ("nodes", "depth", "instructions") else 1
        )
    elif reason == "utf8":
        cache = _lineage_descriptor_cache(dict(kind="str", value="\u03b4" * 20))
        monkeypatch.setattr(multi, "_LINEAGE_DESCRIPTOR_BYTES", len(cache.descriptor_json))
        assert len(cache.descriptor_json.encode()) > multi._LINEAGE_DESCRIPTOR_BYTES
    elif reason == "unknown":
        cache = _lineage_descriptor_cache(dict(kind="accepted_unknown_leaf", value=7))
    elif reason == "shape_type":
        cache = multi.core.caches.snapshot(np.asarray([1.0]))
        descriptor = json.loads(cache.descriptor_json)
        descriptor["source_layout"]["shape"] = [True]
        cache = _lineage_descriptor_cache(descriptor, cache.columns)
    else:

        class Text(str):
            pass

        cache = replace(cache, descriptor_json=Text(cache.descriptor_json))
    canonical = multi.core.caches.validate
    expected = _lineage_outcome(canonical, cache)
    calls = []

    def original(value):
        calls.append(value)
        return canonical(value)

    monkeypatch.setattr(multi.core.caches, "validate", original)
    assert _lineage_outcome(multi._lineage_validate_cache, cache) == expected
    assert _lineage_outcome(multi._lineage_validate_cache, cache) == expected
    assert len(calls) == 2 and not lineage_plans
    assert expected == dict(returned_same_object=True)
    save(evidence, "fallback", dict(reason=reason, canonical_calls=len(calls), expected=expected))


def test_lineage_descriptor_eviction_and_retained_bounds(monkeypatch, lineage_plans, evidence):
    monkeypatch.setattr(multi, "_LINEAGE_PLAN_ENTRIES", 2)
    values = [multi.core.caches.snapshot(dict(value=i)) for i in range(3)]
    canonical = multi.core.caches.validate
    calls = []

    def original(value):
        calls.append(value)
        return canonical(value)

    monkeypatch.setattr(multi.core.caches, "validate", original)
    for value in values[:2]:
        multi._lineage_validate_cache(value)
    multi._lineage_validate_cache(values[0])
    multi._lineage_validate_cache(values[2])
    assert list(lineage_plans) == [values[0].descriptor_json, values[2].descriptor_json]
    multi._lineage_validate_cache(values[1])
    assert calls == [values[0], values[1], values[2], values[1]]
    assert len(lineage_plans) == 2
    assert sum(size for _, size in lineage_plans.values()) <= multi._LINEAGE_RETAINED_BYTES
    lineage_plans.clear()
    multi._lineage_validate_cache(values[0])
    first_size = next(iter(lineage_plans.values()))[1]
    monkeypatch.setattr(multi, "_LINEAGE_RETAINED_BYTES", first_size)
    multi._lineage_validate_cache(values[1])
    assert len(lineage_plans) <= 1
    assert sum(size for _, size in lineage_plans.values()) <= first_size
    save(
        evidence,
        "bounds",
        dict(max_entries=2, payload_budget=first_size, canonical_calls=len(calls)),
    )


def test_lineage_descriptor_exact_text_keys_and_immutable_payloads(lineage_plans, evidence):
    first = _lineage_cache_fixture()
    second_raw = json.dumps(json.loads(first.descriptor_json), indent=1)
    second = replace(
        first, descriptor_json=second_raw, identity=hashlib.sha256(second_raw.encode()).hexdigest()
    )
    assert multi._lineage_validate_cache(first) is first
    assert multi._lineage_validate_cache(second) is second
    assert set(lineage_plans) == {first.descriptor_json, second_raw}
    seen = []

    def immutable(value):
        seen.append(type(value).__name__)
        assert type(value) in (tuple, str, int)
        if type(value) is tuple:
            for child in value:
                immutable(child)

    for raw, (plan, size) in lineage_plans.items():
        immutable(plan)
        assert size == multi._lineage_plan_size(raw, plan)
        assert size <= multi._LINEAGE_PLAN_BYTES
    save(evidence, "immutable", dict(entries=2, payload_types=sorted(set(seen))))


@pytest.mark.parametrize("change", ["forged_hash", "retarget", "empty_nonfinite"])
def test_lineage_descriptor_forged_warm_plan_never_authenticates_values(
    change, lineage_plans, evidence
):
    original = multi.core.caches.snapshot(
        np.asarray([np.inf if change == "empty_nonfinite" else 1.0])
    )
    replacement = multi.core.caches.snapshot(np.asarray([2.0]))
    multi._lineage_validate_cache(original)
    multi._lineage_validate_cache(replacement)
    baseline = multi._bindings()
    plan, size = lineage_plans[original.descriptor_json]
    if change == "empty_nonfinite":
        changed = replace(original, all_finite=True)
        forged = ((), size)
    else:
        changed = replace(original, columns=replacement.columns)
        if change == "retarget":
            forged = lineage_plans[replacement.descriptor_json]
        else:
            instruction = (
                *plan[0][:-1],
                hashlib.sha256(replacement.columns[0].values.tobytes()).hexdigest(),
            )
            forged = ((instruction,), size)
    lineage_plans[original.descriptor_json] = forged
    # Map identity, source/helper bindings, descriptor text and cache identity
    # are unchanged. Only authenticated plan issuance can reject this forgery.
    multi.accounting._check_binding_identity(multi._bindings(), baseline)
    expected = _lineage_outcome(multi.core.caches.validate, changed)
    actual = _lineage_outcome(multi._lineage_validate_cache, changed)
    assert "type" in expected and actual == expected
    assert (
        changed.descriptor_json == original.descriptor_json
        and changed.identity == original.identity
    )
    save(evidence, "forged-plan", dict(change=change, expected=expected, actual=actual))


@pytest.mark.parametrize("kind", ["subclass", "opaque"])
def test_lineage_descriptor_string_keys_refuse_substitution(
    kind, monkeypatch, lineage_plans, evidence
):
    original = multi.core.caches.snapshot(np.asarray([1.0]))
    replacement = multi.core.caches.snapshot(np.asarray([2.0]))
    multi._lineage_validate_cache(original)
    multi._lineage_validate_cache(replacement)
    changed = replace(original, columns=replacement.columns)
    expected = _lineage_outcome(multi.core.caches.validate, changed)
    assert expected["type"] == "builtins.ValueError"
    assert (
        multi._lineage_lookup_plan(original.descriptor_json)
        is lineage_plans[original.descriptor_json]
    )
    dispatched = []

    class Substitution(str if kind == "subclass" else object):
        def __hash__(self):
            dispatched.append("hash")
            return hash(replacement.descriptor_json)

        def __eq__(self, other):
            dispatched.append("equal")
            return other == replacement.descriptor_json

        def __str__(self):
            dispatched.append("text")
            return replacement.descriptor_json

    candidate = Substitution(original.descriptor_json) if kind == "subclass" else Substitution()
    with pytest.raises(ValueError, match="exact descriptor string"):
        multi._lineage_lookup_plan(candidate)
    assert not dispatched

    # Even a direct call to the private C wrapper cannot borrow an exact-str
    # entry through equality with a string subclass: its cache is typed.
    class EqualText(str):
        pass

    hits = multi._lineage_memoized_descriptor.cache_info().hits
    with pytest.raises(ValueError, match="memoization budget"):
        multi._lineage_memoized_descriptor(EqualText(replacement.descriptor_json))
    assert multi._lineage_memoized_descriptor.cache_info().hits == hits
    assert multi._lineage_memoized_descriptor.cache_parameters()["typed"] is True
    lineage_plans[original.descriptor_json] = lineage_plans[replacement.descriptor_json]
    assert _lineage_outcome(multi._lineage_validate_cache, changed) == expected
    assert not dispatched
    assert (
        changed.descriptor_json == original.descriptor_json
        and changed.identity == original.identity
    )
    save(evidence, "string-key", dict(kind=kind, canonical_refusal=expected, key_dispatches=[]))


def test_lineage_descriptor_private_eviction_uses_canonical_fallback(
    monkeypatch, lineage_plans, evidence
):
    cache = _lineage_cache_fixture()
    multi._lineage_validate_cache(cache)
    old = lineage_plans[cache.descriptor_json]
    multi._lineage_memoized_descriptor.cache_clear()
    canonical, calls = multi.core.caches.validate, []

    def original(value):
        calls.append(value)
        return canonical(value)

    monkeypatch.setattr(multi.core.caches, "validate", original)
    assert multi._lineage_validate_cache(cache) is cache and calls == [cache]
    assert lineage_plans[cache.descriptor_json] is not old
    info = multi._lineage_memoized_descriptor.cache_info()
    assert info.maxsize == multi._LINEAGE_CANONICAL_ENTRIES and info.currsize <= info.maxsize
    assert multi._lineage_memoized_descriptor.cache_parameters()["typed"] is True
    save(evidence, "private-eviction", dict(canonical_calls=1, max_entries=info.maxsize))


@pytest.mark.parametrize("change", ["forged_unseen", "private_miss"])
def test_lineage_descriptor_unissued_key_preserves_column_before_parser(
    change, lineage_plans, evidence
):
    cache = _lineage_cache_fixture()
    if change == "forged_unseen":
        cache = replace(cache, descriptor_json="{", identity=hashlib.sha256(b"{").hexdigest())
        lineage_plans[cache.descriptor_json] = ((), 0)
    else:
        multi._lineage_validate_cache(cache)
        multi._lineage_memoized_descriptor.cache_clear()
    cache = replace(cache, columns=(object(),))
    expected = _lineage_outcome(multi.core.caches.validate, cache)
    assert expected["type"] == "builtins.AttributeError"
    previous, attempted, caught = sys.getprofile(), [], None
    sentinel = LookupError("Parser must not precede malformed current columns")

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code is json.loads.__code__:
            attempted.append("parser")
            raise sentinel

    try:
        sys.setprofile(profile)
        try:
            multi._lineage_validate_cache(cache)
        except BaseException as error:
            caught = error
    finally:
        sys.setprofile(previous)
    assert sys.getprofile() is previous and not attempted
    assert type(caught) is AttributeError and str(caught) == expected["message"]
    save(evidence, "unissued-order", dict(change=change, expected=expected, parser_attempts=[]))


@pytest.mark.parametrize(
    "change",
    [
        "wrong_result",
        "wrong_raw",
        "equal_raw_object",
        "subclass",
        "changed_after_validation",
        "direct_miss",
        "foreign_globals",
    ],
)
def test_lineage_descriptor_cold_publication_authenticates_live_result(
    change, monkeypatch, lineage_plans, evidence
):
    baseline = multi.core.caches.snapshot(dict(value=1))
    valid, issued = multi._lineage_publish_plan(baseline, baseline.descriptor_json)
    assert valid is baseline and issued is not None
    assert multi._lineage_lookup_plan(baseline.descriptor_json) is issued
    cache = multi.core.caches.snapshot(dict(value=2))
    raw = cache.descriptor_json
    canonical, compile_plan = multi.core.caches.validate, multi._lineage_descriptor_plan
    validations, compilations = [], []

    def validate(value):
        validations.append(value)
        result = canonical(value)
        if change == "wrong_result":
            return replace(result)
        if change == "changed_after_validation":
            object.__setattr__(value, "descriptor_json", baseline.descriptor_json)
        return result

    def compile_current(value):
        compilations.append(value)
        return compile_plan(value)

    monkeypatch.setattr(multi.core.caches, "validate", validate)
    monkeypatch.setattr(multi, "_lineage_descriptor_plan", compile_current)
    publisher = multi._lineage_publish_plan
    if change == "wrong_raw":
        raw = baseline.descriptor_json
    elif change == "equal_raw_object":
        raw = (raw + " ")[:-1]
        assert raw == cache.descriptor_json and raw is not cache.descriptor_json
    elif change == "subclass":

        class Text(str):
            pass

        raw = Text(raw)
    elif change == "foreign_globals":
        publisher = FunctionType(publisher.__code__, dict(vars(multi)), "foreign_publisher")
    if change == "direct_miss":
        with pytest.raises(ValueError, match="private descriptor memo caller"):
            multi._lineage_memoized_descriptor(raw)
        assert not validations
    else:
        with pytest.raises(
            ValueError, match="descriptor publication|private descriptor memo caller"
        ):
            publisher(cache, raw)
        assert len(validations) == 1 and validations[0] is cache
    assert not compilations
    assert not lineage_plans
    save(
        evidence,
        "publication",
        dict(change=change, positive_issued=True, canonical_calls=len(validations), parser_calls=0),
    )


def test_lineage_descriptor_preserves_references_and_digest(monkeypatch, lineage_plans, evidence):
    @dataclass(frozen=True)
    class Metadata:
        fields: object
        raw: object

    cache = _lineage_cache_fixture()
    equal_cache = replace(cache)
    cycle = []
    cycle.append(cycle)
    request = Metadata(
        dict(first=cache, repeated=cache, equal=equal_cache, cycle=cycle), np.asarray([1.0, -0.0])
    )
    canonical = multi.core.caches.validate
    oracle = FunctionType(
        multi._lineage.__code__,
        dict(vars(multi), _lineage_validate_cache=canonical),
        "lineage_oracle",
    )
    expected_refs, expected_digest = oracle(request)
    checks = []
    replay = multi._lineage_validate_cache

    def fresh(value):
        checks.append(value)
        return replay(value)

    monkeypatch.setattr(multi, "_lineage_validate_cache", fresh)
    for _ in range(2):
        actual_refs, actual_digest = multi._lineage(request)
        assert actual_digest == expected_digest
        assert len(actual_refs) == len(expected_refs)
        assert all(a is b for a, b in zip(actual_refs, expected_refs, strict=True))
    assert len(checks) == 4
    assert checks[0] is checks[2] is cache and checks[1] is checks[3] is equal_cache
    request.fields["equal"] = replace(equal_cache)
    changed_refs, changed_digest = multi._lineage(request)
    oracle_refs, oracle_digest = oracle(request)
    assert changed_digest == oracle_digest
    assert all(a is b for a, b in zip(changed_refs, oracle_refs, strict=True))
    assert any(a is not b for a, b in zip(changed_refs, expected_refs, strict=True))
    save(
        evidence,
        "lineage",
        dict(signature=expected_digest, references=len(expected_refs), cache_checks=len(checks)),
    )


@pytest.mark.parametrize(
    "change",
    [
        "helper_code",
        "compiled_body",
        "memo_body",
        "publisher",
        "frame_reader",
        "defaults",
        "keyword_defaults",
        "parser",
        "decoder",
        "finite",
        "constant",
        "memo",
        "descriptor",
    ],
)
def test_lineage_descriptor_binding_drift_refuses(change, monkeypatch, lineage_plans, evidence):
    baseline = multi._bindings()
    multi.accounting._check_binding_identity(multi._bindings(), baseline)
    if change == "helper_code":
        monkeypatch.setattr(multi._lineage_descriptor_plan, "__code__", (lambda raw: ()).__code__)
    elif change == "compiled_body":
        monkeypatch.setattr(
            multi._lineage_compiled_descriptor, "__code__", (lambda raw: ()).__code__
        )
    elif change == "memo_body":
        monkeypatch.setattr(
            multi._lineage_memoized_descriptor.__wrapped__, "__code__", (lambda key: ()).__code__
        )
    elif change == "publisher":
        monkeypatch.setattr(
            multi._lineage_publish_plan, "__code__", (lambda cache, raw: (cache, None)).__code__
        )
    elif change == "frame_reader":
        # Restore the process-wide helper before assertions or report writers.
        with monkeypatch.context() as patch:
            patch.setattr(sys, "_getframe", lambda depth=0: None)
            current = multi._bindings()
        with pytest.raises(ValueError, match="callable or code identity"):
            multi.accounting._check_binding_identity(current, baseline)
        multi.accounting._check_binding_identity(multi._bindings(), baseline)
        save(evidence, "binding-refusal", dict(change=change, frame_reader_restored=True))
        return
    elif change == "defaults":
        monkeypatch.setattr(multi._lineage_descriptor_plan, "__defaults__", (None,))
    elif change == "keyword_defaults":
        monkeypatch.setattr(multi._lineage_descriptor_plan, "__kwdefaults__", {"unexpected": None})
    elif change == "parser":
        monkeypatch.setattr(json, "loads", lambda raw: {})
    elif change == "decoder":
        monkeypatch.setattr(json._default_decoder, "scan_once", lambda raw, index: ({}, len(raw)))
    elif change == "finite":
        monkeypatch.setattr(np, "isfinite", lambda value: True)
    elif change == "constant":
        monkeypatch.setattr(multi, "_LINEAGE_PLAN_ENTRIES", multi._LINEAGE_PLAN_ENTRIES + 1)
    elif change == "memo":
        monkeypatch.setattr(multi, "_LINEAGE_PLANS", OrderedDict())
    else:
        monkeypatch.setattr(multi.core.caches.Cache, "descriptor", property(lambda self: {}))
    with pytest.raises(ValueError):
        multi.accounting._check_binding_identity(multi._bindings(), baseline)
    save(evidence, "binding-refusal", dict(change=change))


@pytest.mark.parametrize(
    "target", ["canonical", "plan", "warm", "parser", "lookup_miss", "lookup_token"]
)
def test_lineage_descriptor_inherited_entry_rejection_is_not_a_miss(
    target, monkeypatch, lineage_plans, evidence
):
    class Refusal(BaseException):
        def __bool__(self):
            return False

    class LookupRefusal(LookupError):
        def __bool__(self):
            return False

    cache = _lineage_cache_fixture()
    if target in ("warm", "parser", "lookup_miss", "lookup_token"):
        multi._lineage_validate_cache(cache)
    if target in ("parser", "lookup_miss", "lookup_token"):
        multi._lineage_memoized_descriptor.cache_clear()
    if target == "warm":
        finite = np.isfinite

        def finite_call(value):
            return finite(value)

        monkeypatch.setattr(np, "isfinite", finite_call)
    exception_type = LookupRefusal if target == "lookup_miss" else Refusal
    original, cause = exception_type("inherited metadata guard"), LookupError("original cause")
    original.__cause__ = cause
    selected = {
        "canonical": multi.core.caches.validate.__code__,
        "plan": multi._lineage_descriptor_plan.__code__,
        "warm": finite_call.__code__ if target == "warm" else None,
        "parser": json.loads.__code__,
        "lookup_miss": multi._lineage_memoized_descriptor.__wrapped__.__code__,
        "lookup_token": multi._lineage_memoized_descriptor.__wrapped__.__code__,
    }[target]
    previous, attempted, caught = sys.getprofile(), [], None

    def profile(frame, event, arg):
        nonlocal original
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code is selected:
            attempted.append(target)
            if target == "lookup_token":
                original = frame.f_back.f_locals["miss"]
                original.__cause__ = cause
            raise original

    try:
        sys.setprofile(profile)
        try:
            multi._lineage_validate_cache(cache)
        except BaseException as error:
            caught = error
    finally:
        sys.setprofile(previous)
    assert sys.getprofile() is previous
    assert caught is original and caught.__cause__ is cause and attempted == [target]
    if target in ("canonical", "plan"):
        assert not lineage_plans
    save(
        evidence,
        "observer-refusal",
        dict(target=target, primary_retained=True, cause_retained=True),
    )


def test_lineage_descriptor_crowded_working_set_stays_warm(monkeypatch, lineage_plans, evidence):
    """A tissue-sized metadata roster retains no arrays or authority decisions."""
    caches = tuple(
        multi.core.caches.snapshot(dict(index=index, values=np.asarray([index, index + 0.5])))
        for index in range(1200)
    )
    canonical_validate = multi.core.caches.validate
    canonical_lineage = FunctionType(
        multi._lineage.__code__,
        dict(vars(multi), _lineage_validate_cache=canonical_validate),
        "canonical_lineage",
    )
    references, signature = canonical_lineage(caches)
    calls = []

    def counted_validate(cache):
        calls.append(cache.identity)
        return canonical_validate(cache)

    monkeypatch.setattr(multi.core.caches, "validate", counted_validate)
    for sweep in range(3):
        actual_references, actual_signature = multi._lineage(caches)
        assert actual_signature == signature
        assert len(actual_references) == len(references)
        assert all(a is b for a, b in zip(actual_references, references, strict=True))
        assert len(calls) == len(caches), sweep
    info = multi._lineage_memoized_descriptor.cache_info()
    assert len(lineage_plans) == info.currsize == len(caches)
    assert info.currsize <= info.maxsize == multi._LINEAGE_CANONICAL_ENTRIES
    retained_bytes = sum(size for _, size in lineage_plans.values())
    assert retained_bytes <= multi._LINEAGE_RETAINED_BYTES

    # A warm descriptor still authenticates the current column bytes.
    sample = caches[len(caches) // 2]
    column = sample.columns[0]
    changed_values = column.values.copy()
    changed_values.flat[0] += 1.0
    changed_values.flags.writeable = False
    changed = replace(sample, columns=(replace(column, values=changed_values),))
    expected = _lineage_outcome(canonical_validate, changed)
    actual = _lineage_outcome(multi._lineage_validate_cache, changed)
    assert "type" in expected and actual == expected
    assert len(calls) == len(caches)
    save(
        evidence,
        "crowded-working-set",
        dict(
            descriptors=len(caches),
            sweeps=3,
            canonical_validations=len(calls),
            retained_descriptor_bytes=retained_bytes,
            cache_info=info._asdict(),
            exact_references_and_digest=True,
            changed_column_refused=actual,
            synthetic_metadata_only=True,
        ),
    )


def test_lineage_descriptor_item_selection_is_exact(evidence):
    from validation.betse import betse_native_multi_cell_caller_software as software

    assert software._selection("focused", None) == [
        str(software.ROOT / software.TEST),
        "-k",
        "software",
    ]
    selected = software._selection("focused", software.LINEAGE_ITEMS)
    assert len(selected) == len(software.LINEAGE_ITEMS)
    assert selected == [
        str(software.ROOT / software.TEST) + "::" + item for item in software.LINEAGE_ITEMS
    ]
    for bad in ((), ("test_unknown",), (software.LINEAGE_ITEMS[0],) * 2, ("-k software",)):
        with pytest.raises(ValueError):
            software._selection("focused", bad)
    save(evidence, "item-selection", dict(items=software.LINEAGE_ITEMS, selected=selected))


@pytest.mark.parametrize("workload", ["empty", "state-shaped", "mesh-shaped"])
def test_lineage_descriptor_metadata_cost_observation(workload, lineage_plans, evidence):
    """Observe toy metadata cost; no speed threshold or tissue-performance claim."""
    from statistics import median
    from time import perf_counter_ns, process_time_ns

    if workload == "empty":
        values = {}
    elif workload == "state-shaped":
        values = dict(words=np.arange(624, dtype=np.uint32), position=0, cached=0.0)
    else:
        values = dict(
            points=np.arange(128, dtype=np.float64).reshape(64, 2),
            ids=np.arange(64, dtype=np.int64),
            edges=np.arange(64, dtype=np.int64).reshape(32, 2),
            mask=np.arange(64, dtype=np.uint8).reshape(8, 8),
            bounds=(0.0, 8.0, 0.0, 8.0),
        )
    cache = multi.core.caches.snapshot(values)
    request = (cache, replace(cache), {"repeated_reference": cache})
    canonical = FunctionType(
        multi._lineage.__code__,
        dict(vars(multi), _lineage_validate_cache=multi.core.caches.validate),
        "canonical_lineage",
    )
    functions = dict(canonical=canonical, descriptor_reuse=multi._lineage)
    expected_refs, expected_digest = canonical(request)
    previous_profile, previous_trace = sys.getprofile(), sys.gettrace()
    assert previous_profile is not None, "The inherited native blockade must remain active"

    def same(result):
        refs, digest = result
        assert digest == expected_digest and len(refs) == len(expected_refs)
        assert all(a is b for a, b in zip(refs, expected_refs, strict=True))

    for function in functions.values():
        same(function(request))
    iterations, rounds = 32, 3
    samples = {name: [] for name in functions}
    for round_index in range(rounds):
        order = tuple(functions) if round_index % 2 == 0 else tuple(reversed(functions))
        for name in order:
            function = functions[name]
            cpu_start, wall_start = process_time_ns(), perf_counter_ns()
            for _ in range(iterations):
                result = function(request)
            wall_ns, cpu_ns = perf_counter_ns() - wall_start, process_time_ns() - cpu_start
            same(result)
            samples[name].append(dict(round=round_index, wall_ns=wall_ns, cpu_ns=cpu_ns))
    calls = {}
    for name, function in functions.items():
        counts = dict(call=0, c_call=0)

        def profile(frame, event, arg, counts=counts):
            previous_profile(frame, event, arg)
            if event in counts:
                counts[event] += 1

        try:
            sys.setprofile(profile)
            result = function(request)
        finally:
            sys.setprofile(previous_profile)
        same(result)
        calls[name] = counts
    assert sys.getprofile() is previous_profile and sys.gettrace() is previous_trace
    per_call = {
        name: {
            metric: median(row[metric] / iterations for row in rows)
            for metric in ("wall_ns", "cpu_ns")
        }
        for name, rows in samples.items()
    }
    save(
        evidence,
        "metadata-cost-observation",
        dict(
            workload=workload,
            synthetic_only=True,
            actual_rng_or_owner_created=False,
            performance_extrapolation=False,
            descriptor_bytes=len(cache.descriptor_json.encode()),
            numeric_columns=len(cache.columns),
            cache_identity=cache.identity,
            lineage_digest=expected_digest,
            retained_reference_count=len(expected_refs),
            iterations=iterations,
            rounds=rounds,
            warm_only=True,
            inherited_guard_active=True,
            timed_with_extra_counter=False,
            counting_note="Separate call counts exclude profiler callbacks and their descendants",
            raw_samples=samples,
            median_per_call=per_call,
            calls_per_lineage=calls,
            reuse_over_canonical={
                metric: per_call["descriptor_reuse"][metric] / per_call["canonical"][metric]
                for metric in ("wall_ns", "cpu_ns")
            },
            exact_references_and_digest_preserved=True,
            final_hooks_restored=True,
        ),
    )
