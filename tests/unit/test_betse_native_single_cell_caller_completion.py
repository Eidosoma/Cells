"""Fresh height-owner/caller-tail controls; all literal/native entry is blocked."""

import ast
import hashlib
import json
import os
import pickle
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_caller_completion as done
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

pmod, meshes, callers, images, core = (
    done.parameters,
    done.meshes,
    done.callers,
    done.images,
    done.core,
)


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_CALLER_COMPLETION_EVIDENCE", str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def harness(monkeypatch, tmp_path, *, parameter_failure=False, tail_failure=None):
    """Counterfactual upstream source trials; no numerical source is executed.

    The production parameter/caller claim, tail retirement, sealing, aliases,
    reference guards and public pipeline run. Literal bodies are stand-ins;
    the reusable runner independently forbids the original code objects.
    """
    events = []
    failures = {}
    pins = dict(synthetic_only="native blocked")
    recipe = dict(world_len_m=4.0, cell_radius_m=0.5, lattice_disorder=0.0, lattice_type="HEX")
    base = SimpleNamespace(
        identity="synthetic-initial-request",
        upstream=(SimpleNamespace(definition=recipe), None, None),
    )
    parent = core.Request(base, SimpleNamespace(identity="synthetic-initial-state"), "")
    monkeypatch.setattr(callers, "_precheck", lambda value: None)
    monkeypatch.setattr(
        core,
        "request_record",
        lambda value: dict(synthetic_only=True, initial=value.initial_request.identity),
    )
    parent = replace(parent, identity=core.records._digest(core.request_record(parent)))
    monkeypatch.setattr(
        callers,
        "request_record",
        lambda value: dict(synthetic_only=True, core=value.core_request.identity),
    )
    for module in (pmod, done, meshes):
        monkeypatch.setattr(module, "_verify_sources", lambda: dict(pins))
    request = done.from_core(parent, {"world options": {"cell height": "2.5"}}, law_id=done.LAW_ID)
    rng = SimpleNamespace(epoch="synthetic-shared-stream")
    stream = SimpleNamespace(identity=rng.epoch)
    monkeypatch.setattr(
        core.initial, "_rng_stream", lambda value: SimpleNamespace(identity=value.epoch)
    )

    def fail(label):
        try:
            raise SyntheticSourceCause("original synthetic cause: " + label)
        except SyntheticSourceCause as cause:
            error = SyntheticSourceFailure("synthetic source failure: " + label)
            failures[label], failures[label + "_cause"] = error, cause
            raise error from cause

    def construct(p, actual_recipe, configuration):
        events.append("parameters")
        assert actual_recipe == recipe
        # Explicit literal fixture values; no float conversion, derived mesh,
        # RNG or original parameter-store function is evaluated.
        p._conf = configuration
        p.world_len = 4.0
        p.cell_radius = 0.5
        p.cell_lattice_disorder = 0.0
        p.cell_lattice_type = callers.source.CellLatticeType.HEX
        p.wsx = 4.0
        p.wsy = 4.0
        if parameter_failure:
            fail("parameters")
        p.cell_height = 2.5
        p.ac = 1e-6
        p.d_cell = 1.0
        p.nx = 4
        p.ny = 4
        p.wsx = 4.0
        p.wsy = 4.0

    monkeypatch.setattr(pmod, "_construct", construct)
    state = SimpleNamespace(
        parameter=None, p=None, caller=None, image=None, mesh=None, caller_request=None
    )

    def lattice_body():
        raise AssertionError("No original or synthetic lattice execution is needed")

    def caller_factory(parameter_request, parameter_owner):
        events.append("caller")
        assert events[0] == "parameters"
        caller_request = callers.Request(parameter_request.core_request, "")
        caller_request = replace(
            caller_request, identity=core.records._digest(callers.request_record(caller_request))
        )
        p = pmod._claim_for_caller(parameter_owner, caller_request, recipe)
        cells = object.__new__(callers._Runtime)
        cells._cells_original_lattice = lattice_body
        cells.centre = np.asarray([0.5, 0.5])
        cells.xmin, cells.xmax, cells.ymin, cells.ymax = 0.0, 2.0, 0.0, 1.0
        tape = SimpleNamespace(rng=rng, events=[], draws=[], locals={})
        cache = core.caches.snapshot(callers._public(cells))
        trial = callers.Trial(
            caller_request.identity,
            core.caches.snapshot({}),
            pmod._authority(parameter_owner).trial.cache,
            cache,
            core.caches.snapshot({}),
            (),
            stream,
            (),
            "synthetic_only",
            None,
            None,
            None,
            "synthetic-caller-trial",
        )
        trial = replace(trial, identity=core.records._digest(callers.trial_record(trial)))
        owner = object.__new__(callers.CallerOwner)
        callers._ISSUED[owner] = dict(
            caller=cells,
            parameters=p,
            parameter_owner=parameter_owner,
            request=caller_request,
            trial=trial,
            tape=tape,
            invalid=False,
            bindings=callers._bindings(cells),
        )
        state.parameter, state.p, state.caller, state.caller_request = (
            parameter_owner,
            p,
            owner,
            caller_request,
        )
        return owner

    def image_factory(caller_owner):
        events.append("image")
        caller = callers._authority(caller_owner)
        assert caller["parameters"] is state.p
        mask = SimpleNamespace(clipping_matrix=np.asarray([[1.0, 0.0], [0.0, 1.0]]), msize=2)
        tape = SimpleNamespace(
            mask=mask,
            picker=SimpleNamespace(filename="synthetic-unused"),
            splines=[],
            hull=SimpleNamespace(vertices=np.asarray([0, 1])),
            locals={},
            events=[],
        )
        owner = object.__new__(images.ImageOwner)
        image_trial = images.Trial(
            "synthetic-image-request",
            core.caches.snapshot(dict(synthetic_only=True)),
            (),
            (),
            (),
            True,
            None,
            None,
            None,
            "",
        )
        image_trial = replace(
            image_trial, identity=core.records._digest(images.trial_record(image_trial))
        )
        images._ISSUED[owner] = dict(
            caller=caller["caller"],
            rng=rng,
            tape=tape,
            request=images.Request(caller_owner, "synthetic-image-request"),
            trial=image_trial,
            invalid=False,
        )
        state.image = owner
        return owner

    def mesh_factory(image_owner):
        events.append("mesh_constructor")
        image = images._authority(image_owner)
        caller = callers._authority(image["request"].caller)
        assert caller["parameters"] is state.p
        # Model already-qualified upstream source ownership only. No original
        # constructor/init is executed or credited by these tail controls.
        retirement = object()
        callers._CONSUMED[image["request"].caller] = retirement
        caller["continuation_consumed"] = image["continuation_consumed"] = True
        kernel = object.__new__(meshes._Runtime)
        kernel.vcell_verts = np.asarray(
            [[[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]], [[1.0, 0.0], [2.0, 0.0], [1.0, 1.0]]]
        )
        kernel.vor_verts = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 1.0]])
        kernel.vor_cents = np.asarray([[0.5, 0.5], [1.5, 0.5]])
        kernel.vor_sa = np.asarray([3.0, 4.0])
        observer = core.initial._Observer(("synthetic-p0", "synthetic-p1"))
        kernel._cells_rng = SimpleNamespace(rng=rng, observer=observer)
        kernel._cells_observer = observer
        caller["caller"].mesh = kernel
        events.extend(["mesh_assigned", "mesh_init"])
        context = SimpleNamespace(
            caller=caller["caller"],
            kernel=kernel,
            rng=rng,
            observer=observer,
            parent_caller=caller,
            parent_image=image,
            request=SimpleNamespace(identity="synthetic-mesh-request"),
            trial=SimpleNamespace(identity="synthetic-mesh-trial"),
            retirement=retirement,
            invalid=False,
            producers=dict(pins),
            bindings=meshes._bindings(),
            graph_tape=SimpleNamespace(
                rng=rng,
                events=observer.events,
                draws=[],
                locals=dict(wrapper=vars(kernel._cells_rng)),
            ),
        )
        cache = core.caches.snapshot(core.initial._public_cache(kernel))
        mesh_trial = meshes.Trial(
            "synthetic-mesh-request",
            caller["trial"].identity,
            image["trial"].identity,
            cache,
            cache,
            meshes._snapshot(context),
            observer.ids,
            tuple(observer.events),
            (),
            stream,
            stream,
            (),
            (),
            True,
            None,
            None,
            None,
            "",
        )
        context.trial = replace(
            mesh_trial, identity=core.records._digest(meshes.trial_record(mesh_trial))
        )
        owner = object.__new__(meshes.MeshOwner)
        meshes._ISSUED[owner] = context
        state.mesh = owner
        return owner

    original_validate = meshes._validate_owner

    def validate_mesh(owner):
        if owner is not state.mesh or owner in meshes._FORWARDED:
            return original_validate(owner)
        context = meshes._authority(owner)
        if context.invalid or context.caller.mesh is not context.kernel:
            raise meshes.ContinuationRejected(
                "Synthetic upstream owner stale", stage="child_authority_drift"
            )
        pmod._validate_binding(state.parameter, state.caller_request, state.p)
        return context

    monkeypatch.setattr(meshes, "_validate_owner", validate_mesh)

    def aliases(cells, mask):
        events.append("tail_aliases")
        assert cells is callers._authority(state.caller)["caller"]
        cells.ecm_verts = cells.mesh.vcell_verts
        if tail_failure == "alias_first":
            fail("alias_first")
        cells.cluster_mask = mask.clipping_matrix
        cells.msize = mask.msize
        cells.ecm_verts_unique = cells.mesh.vor_verts
        if tail_failure == "alias_last":
            fail("alias_last")

    def cell_index(cells, p):
        events.append("cell_index")
        assert p is state.p and pmod._authority(state.parameter).p is p
        cells.cell_centres = cells.mesh.vor_cents
        if tail_failure == "cell_index":
            fail("cell_index")
        # Independent literal fixture result, not native volume arithmetic.
        cells.cell_vol = np.asarray([7.5, 10.0])
        if tail_failure == "index_last":
            fail("index_last")

    monkeypatch.setattr(done, "_caller", caller_factory)
    monkeypatch.setattr(done, "_image", image_factory)
    monkeypatch.setattr(done, "_mesh", mesh_factory)
    monkeypatch.setattr(done, "_TAIL_ALIASES", aliases)
    monkeypatch.setattr(done, "_CELL_INDEX", cell_index)
    return SimpleNamespace(
        request=request,
        parent=parent,
        state=state,
        events=events,
        failures=failures,
        pins=pins,
        rng=rng,
        recipe=recipe,
    )


def prefix_through_mesh(h):
    owner = pmod.prepare_parameters(h.request.parameter_request)
    caller = done._caller(h.request.parameter_request, owner)
    image = done._image(caller)
    return done._mesh(image)


def test_software_literal_parameter_order_and_tail_binding(evidence):
    pins = done._verify_sources()
    assert pmod.source.STORE_LINES == [533, 534, 535, 1118, 1127, 1128, 1129, 1130, 1131]
    tree = ast.parse(Path(pmod.source.__file__).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    stores = next(n for n in cls.body if isinstance(n, ast.FunctionDef)).body
    assert stores[2].targets[0].attr == "cell_height"
    assert isinstance(stores[2].value, ast.Call) and stores[2].value.func.id == "float"
    native = ast.parse((callers.NATIVE_ROOT / "betse/science/parameters.py").read_text())
    native_stores = {n.lineno: n for n in ast.walk(native) if isinstance(n, ast.Assign)}
    assert ast.dump(ast.Module(body=stores, type_ignores=[])) == ast.dump(
        ast.Module(body=[native_stores[line] for line in pmod.source.STORE_LINES], type_ignores=[])
    )
    assert done._TAIL_ALIASES is images.source.CallerTail.make_voronoi_mesh_aliases
    assert done._CELL_INDEX is images.source.CallerTail.cell_index
    save(evidence, "source-pins", pins)


@pytest.mark.parametrize("value", [None, {}, SimpleNamespace(cell_height=2.5)])
def test_software_untyped_parameter_or_tail_authority_refuses(value, evidence):
    with pytest.raises(pmod.ParameterRejected):
        pmod.prepare_parameters(value)
    with pytest.raises(done.CompletionRejected):
        done.prepare_tail(value)
    save(evidence, "refused-input", value)


def test_software_fresh_parameter_order_same_conf_and_raw_entry_guard(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = pmod.prepare_parameters(h.request.parameter_request)
    p = owner.parameters
    names = [name for name, _ in owner.trial.stores]
    assert names == [
        "_conf",
        "world_len",
        "cell_radius",
        "cell_lattice_disorder",
        "cell_lattice_type",
        "wsx",
        "wsy",
        "cell_height",
        "ac",
        "d_cell",
        "nx",
        "ny",
        "wsx",
        "wsy",
    ]
    assert p._conf is pmod._authority(owner).configuration
    assert p.cell_height == 2.5 and h.events == ["parameters"]
    before = owner.trial.cache.identity
    with pytest.raises(pmod.ParameterRejected):
        p.initialize_source_stores()
    with pytest.raises(pmod.ParameterRejected):
        p.__init__(h.recipe, {"world options": {"cell height": "9"}})
    assert owner.parameters is p and owner.trial.cache.identity == before
    save(evidence, "parameter-trial", owner.trial)


def test_software_inconsistent_upstream_core_identity_refuses_before_parameter_work(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    changed = replace(h.parent, identity="inconsistent")
    with pytest.raises(pmod.ParameterRejected) as caught:
        pmod.from_core(changed, {"world options": {"cell height": "2.5"}}, law_id=pmod.LAW_ID)
    assert caught.value.stage == "upstream_identity"
    assert h.events == []
    save(evidence, "refusal", caught.value)


def test_software_parameter_claim_precedes_caller_and_cannot_be_reused(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = pmod.prepare_parameters(h.request.parameter_request)
    p = owner.parameters
    caller = done._caller(h.request.parameter_request, owner)
    assert callers._authority(caller)["parameters"] is p
    with pytest.raises(pmod.ParameterRejected):
        _ = owner.parameters
    with pytest.raises(pmod.ParameterRejected):
        done._caller(h.request.parameter_request, owner)
    assert pmod._validate_binding(owner, h.state.caller_request, p).p is p
    save(evidence, "parameter-trial", owner.trial)


@pytest.mark.parametrize("value", [None, {}, SimpleNamespace(cell_height=2.5)])
def test_software_real_caller_parameter_hook_refuses_unissued_substitutes(
    value, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    request = callers.Request(h.parent, "synthetic-caller-request")
    entered = []

    def forbidden(request):
        entered.append("authentication")
        raise AssertionError("No authentication after absent parameter authority")

    monkeypatch.setattr(callers, "_validate_request", forbidden)
    # None selects the legacy default path, so use an unissued handle for that
    # case rather than disabling the new explicit source-owner option.
    if value is None:
        value = object.__new__(pmod.ParameterOwner)
    with pytest.raises(pmod.ParameterRejected) as caught:
        callers.prepare(request, _parameter_owner=value)
    assert entered == []
    save(evidence, "refusal", caught.value)


def test_software_real_caller_hook_keeps_exact_preconstructed_instance(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = pmod.prepare_parameters(h.request.parameter_request)
    p = owner.parameters
    before = owner.trial
    request = callers.Request(h.parent, "synthetic-caller-request")
    inputs = []
    monkeypatch.setattr(
        callers,
        "_validate_request",
        lambda value: (SimpleNamespace(definition=h.recipe), SimpleNamespace(stream_before=None)),
    )
    monkeypatch.setattr(
        core.initial.streams,
        "native_stream_manifest",
        lambda value: dict(state=["synthetic", [0], 0, 0, 0.0]),
    )

    class SyntheticRng:
        epoch = "synthetic-shared-stream"

        def set_state(self, value):
            self.saved = value

    monkeypatch.setattr(callers.np.random, "RandomState", lambda value: SyntheticRng())

    def constructor(self, actual):
        inputs.append(("constructor", self, actual))

    def lattice(self, actual):
        inputs.append(("lattice", self, actual))
        self.centre = np.asarray([0.5, 0.5])

    monkeypatch.setattr(callers._Runtime, "__init__", constructor)
    monkeypatch.setattr(callers, "_body", lambda tape: lattice)
    monkeypatch.setattr(
        callers, "_audit", lambda *a: core.caches.snapshot(dict(synthetic_only=True))
    )
    child = callers.prepare(request, _parameter_owner=owner)
    value = callers._authority(child)
    assert value["parameters"] is p and value["parameter_owner"] is owner
    assert [kind for kind, _, _ in inputs] == ["constructor", "lattice"]
    assert all(actual is p and caller is value["caller"] for _, caller, actual in inputs)
    assert (
        owner.trial is before
        and owner.trial.cache.identity == value["trial"].parameters_cache.identity
    )
    with pytest.raises(pmod.ParameterRejected):
        callers.prepare(request, _parameter_owner=owner)
    assert len(inputs) == 2
    save(evidence, "parameter-trial", owner.trial)
    save(evidence, "caller-trial", value["trial"])


@pytest.mark.parametrize("change", ["height", "conf_equal"])
def test_software_caller_authentication_cannot_change_claimed_parameter_owner(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = pmod.prepare_parameters(h.request.parameter_request)
    p = owner.parameters
    request = callers.Request(h.parent, "synthetic-caller-request")

    def authenticate(value):
        if change == "height":
            p.cell_height = 9.0
        else:
            p._conf = {"world options": dict(p._conf["world options"])}
        return SimpleNamespace(definition=h.recipe), SimpleNamespace(stream_before=None)

    monkeypatch.setattr(callers, "_validate_request", authenticate)
    with pytest.raises(pmod.ParameterRejected) as caught:
        callers.prepare(request, _parameter_owner=owner)
    assert caught.value.stage == "parameter_drift"
    assert pmod._CLAIMED[owner] is request
    assert h.events == ["parameters"]
    with pytest.raises(pmod.ParameterRejected):
        _ = owner.parameters
    save(evidence, "failure", caught.value)


@pytest.mark.parametrize(
    "text", ["[]", "0", json.dumps({"world options": {"cell height": "x" * 66000}})]
)
def test_software_direct_typed_request_cannot_bypass_configuration_bounds(
    text, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    request = replace(h.request.parameter_request, configuration_json=text)
    with pytest.raises(pmod.ParameterRejected) as caught:
        pmod.prepare_parameters(request)
    assert caught.value.stage == "configuration"
    assert h.events == []
    save(evidence, "failure", caught.value)


@pytest.mark.parametrize("change", ["height", "conf_equal", "conf_value", "store_binding"])
def test_software_parameter_reference_and_source_drift_refuse(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = pmod.prepare_parameters(h.request.parameter_request)
    p = owner.parameters
    if change == "height":
        p.cell_height = 9.0
    elif change == "conf_equal":
        p._conf = {"world options": dict(p._conf["world options"])}
    elif change == "conf_value":
        p._conf["world options"]["cell height"] = "9"
    else:
        monkeypatch.setattr(pmod, "_PARAMETER_STORES", lambda self: None)
    with pytest.raises(pmod.ParameterRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "parameter_drift"
    save(evidence, "failure", caught.value)


def test_software_parameter_failure_keeps_partial_before_height(monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path, parameter_failure=True)
    with pytest.raises(pmod.ParameterRejected) as caught:
        pmod.prepare_parameters(h.request.parameter_request)
    error = caught.value
    p = error.partial["parameters"]
    assert p.wsx == p.wsy == 4.0 and "cell_height" not in vars(p)
    assert error.source_error is h.failures["parameters"]
    assert error.source_error.__cause__ is h.failures["parameters_cause"]
    assert not error.trial.source_completed
    assert p not in pmod._ACTIVE
    save(evidence, "failure", error)


@pytest.mark.parametrize("source_failure", [False, True])
def test_software_parameter_sealing_failure_retains_source_and_actual_object(
    source_failure, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, parameter_failure=source_failure)
    capture = SyntheticCaptureFailure("synthetic parameter sealing failed")
    monkeypatch.setattr(pmod, "trial_record", lambda value: (_ for _ in ()).throw(capture))
    with pytest.raises(pmod.ParameterRejected) as caught:
        pmod.prepare_parameters(h.request.parameter_request)
    assert caught.value.capture_error is capture
    assert caught.value.source_error is (h.failures["parameters"] if source_failure else None)
    assert caught.value.partial["parameters"] is not None
    save(evidence, "failure", caught.value)


def test_software_full_prefix_uses_same_born_parameters_and_retained_objects(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = done.prepare(h.request)
    state = h.state
    mesh = meshes._authority(state.mesh)
    cells = owner.cells
    assert owner.parameters is state.p
    assert cells is mesh.caller and cells.mesh is mesh.kernel
    assert cells.ecm_verts is mesh.kernel.vcell_verts
    assert cells.cluster_mask is images._authority(state.image)["tape"].mask.clipping_matrix
    assert cells.ecm_verts_unique is mesh.kernel.vor_verts
    assert cells.cell_centres is mesh.kernel.vor_cents
    assert np.array_equal(cells.cell_vol, np.asarray([7.5, 10.0]))
    assert h.events == [
        "parameters",
        "caller",
        "image",
        "mesh_constructor",
        "mesh_assigned",
        "mesh_init",
        "tail_aliases",
        "cell_index",
    ]
    assert owner.trial.prefix_identity == h.request.identity
    assert any(w["method"] == "prepare_parameters" for w in owner.trial.work)
    assert (
        owner.trial.source_completed
        and owner.trial.stream_before.identity == owner.trial.stream_after.identity
    )
    with pytest.raises(meshes.ContinuationRejected):
        _ = state.mesh.mesh
    with pytest.raises(pmod.ParameterRejected):
        _ = state.parameter.parameters
    save(evidence, "trial", owner.trial)
    save(evidence, "prefix-order", h.events)


def test_software_legacy_mesh_missing_owned_height_refuses_without_retirement(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    mesh_owner = prefix_through_mesh(h)
    parent = meshes._authority(mesh_owner)
    parent.parent_caller["parameter_owner"] = None
    with pytest.raises(done.CompletionRejected) as caught:
        done.from_mesh(mesh_owner, law_id=done.LAW_ID)
    assert caught.value.stage == "owned_cell_height_unavailable"
    assert mesh_owner not in meshes._FORWARDED
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize("phase", ["alias_first", "alias_last", "cell_index", "index_last"])
def test_software_tail_source_failure_preserves_partial_aliases_and_consumption(
    phase, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, tail_failure=phase)
    mesh_owner = prefix_through_mesh(h)
    request = done.from_mesh(mesh_owner, law_id=done.LAW_ID)
    with pytest.raises(done.CompletionRejected) as caught:
        done.prepare_tail(request)
    error = caught.value
    cells = error.partial["caller"]
    assert error.source_error is h.failures[phase]
    assert error.source_error.__cause__ is h.failures[phase + "_cause"]
    assert cells.ecm_verts is error.partial["mesh"].vcell_verts
    assert error.partial["mesh_epoch_consumed"]
    assert not error.trial.source_completed
    if phase in {"cell_index", "index_last"}:
        assert cells.cell_centres is cells.mesh.vor_cents
    if phase == "cell_index":
        assert "cell_vol" not in vars(cells)
    with pytest.raises(meshes.ContinuationRejected):
        _ = mesh_owner.mesh
    assert len(h.events) == len(set(h.events))
    save(evidence, "failure", error)


@pytest.mark.parametrize("source_failure", [None, "cell_index"])
@pytest.mark.parametrize("point", ["snapshot", "trial", "identity", "graphs"])
def test_software_tail_sealing_failures_do_not_erase_original_state(
    point, source_failure, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, tail_failure=source_failure)
    mesh_owner = prefix_through_mesh(h)
    request = done.from_mesh(mesh_owner, law_id=done.LAW_ID)
    capture = SyntheticCaptureFailure("injected tail capture failure")
    original = done._CELL_INDEX

    def bad(*args, **kwargs):
        raise capture

    def arm(cells, p):
        try:
            original(cells, p)
        finally:
            if point == "snapshot":
                monkeypatch.setattr(done, "_snapshot", bad)
            elif point == "trial":
                monkeypatch.setattr(done, "Trial", bad)
            elif point == "identity":
                monkeypatch.setattr(done, "trial_record", bad)
            else:
                monkeypatch.setattr(meshes, "_graphs", bad)

    monkeypatch.setattr(done, "_CELL_INDEX", arm)
    with pytest.raises(done.CompletionRejected) as caught:
        done.prepare_tail(request)
    error = caught.value
    assert error.capture_error is (None if point == "graphs" and source_failure else capture)
    assert error.source_error is (None if source_failure is None else h.failures[source_failure])
    assert error.partial["mesh_epoch_consumed"]
    assert error.partial["caller"].mesh is error.partial["mesh"]
    assert not any(c.request is request for c in done._ISSUED.values())
    save(evidence, "failure", error)


@pytest.mark.parametrize(
    "change",
    [
        "volume",
        "alias_equal",
        "rng",
        "parameter",
        "config_equal",
        "method",
        "parent_invalid",
        "parent_trial",
        "caller_retirement",
        "mesh_rng_registry",
    ],
)
def test_software_completed_caller_guard_refuses_drift(change, monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    owner = done.prepare(h.request)
    cells = owner.cells
    if change == "volume":
        cells.cell_vol[0] = 99.0
    elif change == "alias_equal":
        cells.ecm_verts = np.array(cells.ecm_verts, copy=True)
    elif change == "rng":
        h.rng.epoch = "different"
    elif change == "parameter":
        h.state.p.cell_height = 9.0
    elif change == "config_equal":
        h.state.p._conf = {"world options": dict(h.state.p._conf["world options"])}
    elif change == "method":
        monkeypatch.setattr(done, "_CELL_INDEX", lambda cells, p: None)
    elif change == "parent_invalid":
        meshes._authority(h.state.mesh).parent_image["invalid"] = True
    elif change == "parent_trial":
        object.__setattr__(meshes._authority(h.state.mesh).trial, "warnings", ("changed parent",))
    elif change == "caller_retirement":
        callers._CONSUMED[h.state.caller] = object()
    else:
        meshes._authority(h.state.mesh).rng = SimpleNamespace(epoch=h.rng.epoch)
    with pytest.raises(done.CompletionRejected) as caught:
        _ = owner.cells
    assert caught.value.stage == "caller_drift"
    save(evidence, "failure", caught.value)


def test_software_reentrant_tail_cannot_acquire_retired_mesh(monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    mesh_owner = prefix_through_mesh(h)
    request = done.from_mesh(mesh_owner, law_id=done.LAW_ID)
    original = done._TAIL_ALIASES
    refusals = []

    def aliases(cells, mask):
        with pytest.raises(done.CompletionRejected) as caught:
            done.prepare_tail(request)
        refusals.append(caught.value)
        original(cells, mask)

    monkeypatch.setattr(done, "_TAIL_ALIASES", aliases)
    owner = done.prepare_tail(request)
    assert owner.cells.mesh is meshes._authority(mesh_owner).kernel
    assert len(refusals) == 1 and refusals[0].stage == "caller_reentrant"
    save(evidence, "refusal", refusals[0])
    save(evidence, "trial", owner.trial)


def test_software_no_checkpoint_or_cellVerts_phase_admission(monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    owner = done.prepare(h.request)
    for value in (owner, owner.parameters, pmod._authority(h.state.parameter).p):
        with pytest.raises(TypeError):
            pickle.dumps(value)
    with pytest.raises(done.CompletionRejected) as caught:
        done.require_cellVerts(owner, phase=SimpleNamespace())
    assert caught.value.stage == "cellVerts_environment_held"
    assert len(caught.value.partial["invalidated_owners"]) == 11
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize(
    "change",
    [
        "mesh_wrapper",
        "mesh_delegate",
        "mesh_code",
        "caller_wrapper",
        "caller_code",
        "caller_lattice_code",
    ],
)
@pytest.mark.parametrize("when", ["tail", "after_seal"])
def test_software_completed_child_keeps_original_mesh_and_caller_callables(
    change, when, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)

    def change_binding():
        if change == "mesh_wrapper":
            monkeypatch.setattr(meshes._Runtime, "make_single_cell_points", lambda self: None)
        elif change == "mesh_delegate":
            monkeypatch.setitem(
                meshes._INHERITED_NATIVE, "make_single_cell_points", lambda self: None
            )
        elif change == "mesh_code":
            method = meshes._Runtime.make_single_cell_points
            # An equal code clone is a different callable epoch. No patched
            # method is invoked by this control.
            monkeypatch.setattr(method, "__code__", method.__code__.replace())
        elif change == "caller_wrapper":
            monkeypatch.setattr(callers._Runtime, "_make_cell_lattice", lambda self, p: None)
        elif change == "caller_code":
            method = callers._Runtime._make_cell_lattice
            monkeypatch.setattr(method, "__code__", method.__code__.replace())
        else:
            method = callers._authority(h.state.caller)["caller"]._cells_original_lattice
            monkeypatch.setattr(method, "__code__", method.__code__.replace())

    if when == "tail":
        original = done._CELL_INDEX

        def cell_index(cells, p):
            original(cells, p)
            change_binding()

        monkeypatch.setattr(done, "_CELL_INDEX", cell_index)
        with pytest.raises(done.CompletionRejected) as caught:
            done.prepare(h.request)
        assert h.state.mesh in meshes._FORWARDED
        assert not any(c.request.mesh_owner is h.state.mesh for c in done._ISSUED.values())
        save(evidence, "refusal", caught.value)
    else:
        child = done.prepare(h.request)
        cells = child.cells
        before = core.caches.snapshot(meshes._caller_without_mesh(cells)).identity
        change_binding()
        assert core.caches.snapshot(meshes._caller_without_mesh(cells)).identity == before
        with pytest.raises(done.CompletionRejected) as caught:
            _ = child.cells
        assert caught.value.stage == "caller_drift"
        assert done._authority(child).invalid
        assert child.trial.source_completed
        save(evidence, "refusal", caught.value)
        save(evidence, "original-trial", child.trial)


@pytest.mark.parametrize("association", ["kernel_observer", "wrapper_observer", "mesh_observer"])
@pytest.mark.parametrize("when", ["tail", "after_seal"])
def test_software_completed_child_keeps_observer_links_with_unchanged_rng(
    association, when, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)

    def retarget():
        mesh = meshes._authority(h.state.mesh)
        substitute = core.initial._Observer(mesh.observer.ids)
        assert substitute is not mesh.observer
        assert tuple(substitute.events) == tuple(mesh.observer.events) == ()
        if association == "kernel_observer":
            mesh.kernel._cells_observer = substitute
        elif association == "wrapper_observer":
            mesh.kernel._cells_rng.observer = substitute
        else:
            mesh.observer = substitute
        assert mesh.kernel._cells_rng.rng is h.rng
        assert h.rng.epoch == "synthetic-shared-stream"

    if when == "tail":
        original = done._CELL_INDEX

        def cell_index(cells, p):
            original(cells, p)
            retarget()

        monkeypatch.setattr(done, "_CELL_INDEX", cell_index)
        with pytest.raises(done.CompletionRejected) as caught:
            done.prepare(h.request)
        assert h.state.mesh in meshes._FORWARDED
        assert not any(c.request.mesh_owner is h.state.mesh for c in done._ISSUED.values())
    else:
        child = done.prepare(h.request)
        before = done._snapshot(done._authority(child)).identity
        retarget()
        assert done._snapshot(done._authority(child)).identity == before
        with pytest.raises(done.CompletionRejected) as caught:
            _ = child.cells
        assert caught.value.stage == "caller_drift"
    save(evidence, "refusal", caught.value)


_PROFILE_OPERATORS = (
    "pre_mesh",
    "init_mesh",
    "create_core_operators",
    "create_tri_map",
    "create_mappings",
)


@pytest.mark.parametrize("name", _PROFILE_OPERATORS)
@pytest.mark.parametrize("failed", [False, True])
def test_software_primary_profile_retains_literal_operator_entries_and_failures(
    name, failed, evidence
):
    error = SyntheticSourceFailure("synthetic operator failure " + name)
    namespace = dict(__name__=core.lifecycle.source.__name__, error=error)
    body = "raise error" if failed else "return 7"
    exec(
        compile("def " + name + "():\n    " + body + "\n", "<synthetic-operator-profile>", "exec"),
        namespace,
    )
    context = SimpleNamespace(stage="mesh", work=[])
    previous = sys.getprofile()
    with done._account_prefix(context):
        if failed:
            with pytest.raises(SyntheticSourceFailure) as caught:
                namespace[name]()
            assert caught.value is error
        else:
            assert namespace[name]() == 7
    assert sys.getprofile() is previous
    assert len(context.work) == 1
    entry = context.work[0]
    assert entry["phase"] == "mesh" and entry["layer"] == "body"
    assert entry["entry_method"] == name and entry["execution"] == "source"
    assert entry["status"] == "entered_not_success_credit"
    save(evidence, "work", context.work)
    if failed:
        save(evidence, "original-error", error)


@pytest.mark.parametrize("phase", ["authentication", "continuation"])
def test_software_primary_profile_distinguishes_wrapper_and_body_execution(phase, evidence):
    body = dict(__name__=core.initial.source.__name__)
    exec(
        compile(
            "def create_core_operators():\n    return 13\n", "<synthetic-operator-body>", "exec"
        ),
        body,
    )
    wrapper = dict(__name__=meshes.__name__, body=body["create_core_operators"])
    exec(
        compile(
            "class _Runtime:\n"
            "    def create_core_operators(self):\n"
            "        return body()\n"
            "def _execute(context):\n"
            "    return _Runtime().create_core_operators()\n",
            "<synthetic-operator-wrapper>",
            "exec",
        ),
        wrapper,
    )
    context = SimpleNamespace(stage="mesh", work=[])
    with done._account_prefix(context):
        assert wrapper["_execute"](SimpleNamespace(phase=phase)) == 13
    operators = [e for e in context.work if e["entry_method"] == "create_core_operators"]
    assert [e["layer"] for e in operators] == ["wrapper", "body"]
    assert all(e["phase"] == "mesh" and e["execution"] == phase for e in operators)
    assert [e["sequence"] for e in context.work] == list(range(len(context.work)))
    save(evidence, "work", context.work)


def test_software_primary_prefix_failure_keeps_entered_operator_work(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    error = SyntheticSourceFailure("synthetic failed init entry")
    namespace = dict(__name__=core.lifecycle.source.__name__, error=error)
    exec(
        compile("def init_mesh():\n    raise error\n", "<synthetic-failed-init>", "exec"), namespace
    )
    original = done._mesh

    def mesh(image_owner):
        original(image_owner)
        namespace["init_mesh"]()

    monkeypatch.setattr(done, "_mesh", mesh)
    previous = sys.getprofile()
    with pytest.raises(done.CompletionRejected) as caught:
        done.prepare(h.request)
    assert sys.getprofile() is previous
    assert caught.value.source_error is error
    work = caught.value.partial["work"]
    entries = [e for e in work if e["entry_method"] == "init_mesh"]
    assert len(entries) == 1 and entries[0]["layer"] == "body"
    assert entries[0]["status"] == "entered_not_success_credit"
    assert caught.value.partial["parents"]["parameter"] is h.state.parameter
    save(evidence, "failure", caught.value)


def _synthetic_profile_entry(module, qualname, body="return None", **values):
    namespace = dict(__name__=module, **values)
    exec(
        compile("def entry():\n    " + body + "\n", "<synthetic-work-profile>", "exec"),
        namespace,
    )
    entry = namespace["entry"]
    entry.__code__ = entry.__code__.replace(
        co_name=qualname.rsplit(".", 1)[-1], co_qualname=qualname
    )
    return entry


@pytest.mark.parametrize(
    "site",
    [
        "_atoms",
        "_atoms.<locals>.visit",
        "_module_bindings.<locals>.<genexpr>",
        "_check_modules.<locals>.<genexpr>",
        "_check_modules.<locals>.<genexpr>.<genexpr>",
        "validate.<locals>.<genexpr>",
        "_bindings.<locals>.<genexpr>",
    ],
)
def test_software_primary_metadata_counts_separate_sites_phases_and_executions(site, evidence):
    module = "cells.processes.betse_native_single_cell_grid_alias"
    helper = _synthetic_profile_entry(module, site)
    wrapper = dict(__name__=meshes.__name__, helper=helper)
    exec(
        compile("def _execute(context):\n    helper()\n", "<synthetic-work-wrapper>", "exec"),
        wrapper,
    )
    context = SimpleNamespace(stage="environment", work=[])
    with done._account_prefix(context, _source_modules=(SimpleNamespace(__name__=module),)):
        for phase in ("environment", "make_maskM"):
            context.stage = phase
            for execution_kind in ("authentication", "continuation"):
                for _ in range(3):
                    wrapper["_execute"](SimpleNamespace(phase=execution_kind))
    save(evidence, "work", context.work)
    rows = [r for r in context.work if r["module"] == module]
    assert len(rows) == 4
    assert {(r["phase"], r["execution"]): r["attempts"] for r in rows} == {
        (phase, execution_kind): 3
        for phase in ("environment", "make_maskM")
        for execution_kind in ("authentication", "continuation")
    }
    assert all(r["layer"] == "metadata_aggregate" and not r["native_body_credit"] for r in rows)
    assert [r["sequence"] for r in context.work] == list(range(len(context.work)))


def test_software_primary_metadata_repetition_exceeds_old_row_count_without_dropping_work(evidence):
    module = "cells.processes.betse_native_single_cell_grid_alias"
    helper = _synthetic_profile_entry(module, "_atoms")
    context = SimpleNamespace(stage="make_maskM", work=[])
    try:
        with done._account_prefix(context, _source_modules=(SimpleNamespace(__name__=module),)):
            for _ in range(100005):
                helper()
    finally:
        save(evidence, "ledger-size", dict(rows=len(context.work)))
        save(evidence, "ledger-ends", context.work[:8] + context.work[-8:])
    assert len(context.work) == 1
    assert context.work[0]["attempts"] == 100005


def test_software_primary_metadata_aggregation_preserves_factory_read_and_failed_body_order(
    evidence,
):
    module = "cells.processes.betse_native_single_cell_grid_alias"
    helper = _synthetic_profile_entry(module, "_atoms")
    factory = _synthetic_profile_entry(module, "_descriptor_from_source")
    getter = _synthetic_profile_entry(module, "__get__")
    cause = SyntheticSourceCause("original synthetic operator cause")
    error = SyntheticSourceFailure("failed synthetic operator")
    operator = _synthetic_profile_entry(
        core.lifecycle.source.__name__,
        "create_core_operators",
        "raise error from cause",
        error=error,
        cause=cause,
    )
    context = SimpleNamespace(stage="make_maskM", work=[])
    with pytest.raises(SyntheticSourceFailure) as caught:
        with done._account_prefix(context, _source_modules=(SimpleNamespace(__name__=module),)):
            helper()
            factory()
            helper()
            getter()
            helper()
            operator()
    save(evidence, "work", context.work)
    save(evidence, "primary-error", caught.value)
    assert caught.value is error and caught.value.__cause__ is cause
    assert [r["entry_method"] for r in context.work] == [
        "_atoms",
        "_descriptor_from_source",
        "__get__",
        "create_core_operators",
    ]
    assert context.work[0]["attempts"] == 3
    assert all(r["layer"] == "body" and "attempts" not in r for r in context.work[1:])


def test_software_primary_ordered_source_row_allowance_is_unchanged(evidence):
    calls = []
    operator = _synthetic_profile_entry(
        core.lifecycle.source.__name__, "create_core_operators", "calls.append(1)", calls=calls
    )
    context = SimpleNamespace(stage="mesh", work=[None] * 100000)
    previous = sys.getprofile()
    with pytest.raises(ValueError, match="Bounded prefix work ledger exhausted") as caught:
        with done._account_prefix(context):
            operator()
    save(evidence, "refusal", caught.value)
    save(evidence, "counts", dict(rows=len(context.work), actual_body_calls=len(calls)))
    assert not calls and len(context.work) == 100000
    assert sys.getprofile() is previous


def test_software_primary_metadata_aggregate_still_chains_previous_rejection(evidence):
    module = "cells.processes.betse_native_single_cell_grid_alias"
    calls = []
    helper = _synthetic_profile_entry(module, "_atoms", "calls.append(1)", calls=calls)
    previous = sys.getprofile()
    error = SyntheticSourceFailure("outer source guard refusal")
    attempts = []

    def outer(frame, event, arg):
        if event == "call" and frame.f_code is helper.__code__:
            attempts.append(event)
            if len(attempts) == 2:
                raise error
        if previous is not None:
            previous(frame, event, arg)

    context = SimpleNamespace(stage="make_maskM", work=[])
    sys.setprofile(outer)
    try:
        with pytest.raises(SyntheticSourceFailure) as caught:
            with done._account_prefix(context, _source_modules=(SimpleNamespace(__name__=module),)):
                helper()
                helper()
        restored = sys.getprofile() is outer
    finally:
        sys.setprofile(previous)
    save(evidence, "work", context.work)
    save(evidence, "outer-error", caught.value)
    save(evidence, "guard", dict(attempts=attempts, body_calls=calls, restored=restored))
    assert caught.value is error and restored
    assert len(attempts) == 2 and calls == [1]
    assert len(context.work) == 1 and context.work[0]["attempts"] == 2
