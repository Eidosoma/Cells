"""Pure source/ownership controls; every real multi-cell native entry is blocked."""

import ast
import hashlib
import json
import os
import pickle
import sys
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace

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
            xpts=h.mask_record["xpts_m"], ypts=h.mask_record["ypts_m"]
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
