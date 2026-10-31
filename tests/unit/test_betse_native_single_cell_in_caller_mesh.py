"""Lifetime/ordering controls with all native and real RNG/operator entry blocked."""

import hashlib
import os
import pickle
import sys
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_in_caller_mesh as mesh
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_IN_CALLER_MESH_EVIDENCE", str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def harness(monkeypatch, tmp_path, *, failure=None, request_metadata=None):
    """Issued synthetic parents, literal caches and no real source execution.

    Metadata-only upstream projectors substitute for separately reviewed seed
    and image audits. The real registry, epoch-consumption and child driver
    functions run. Synthetic kernels never call original source/RNG/operators.
    """
    core, callers, images = mesh.core, mesh.callers, mesh.images
    snapshot = core.caches.snapshot
    calls = dict(authentication=0, constructor=0, init=0, pre_mesh=0, core=0, order=[])
    errors = {}
    producers = dict(synthetic_only="no native authority")
    rng = SimpleNamespace(epoch="before")
    streams = {
        name: SimpleNamespace(identity=name) for name in ("before", "constructed", "pre_mesh")
    }
    monkeypatch.setattr(core.initial, "_rng_stream", lambda actual: streams[actual.epoch])
    filename = tmp_path / "synthetic-original-input.dat"
    filename.write_bytes(b"synthetic input, never decoded")
    image_input = SimpleNamespace(
        native_filename=str(filename),
        resolved_filename=str(filename),
        file_bytes=filename.read_bytes(),
    )
    prelude = SimpleNamespace(identity="synthetic-prelude", image=image_input)

    class SyntheticCaller(callers._Runtime):
        def __setattr__(self, name, value):
            if name == "mesh" and failure == "assignment":
                fail("assignment")
            object.__setattr__(self, name, value)
            if name == "mesh" and failure == "assignment_after":
                fail("assignment_after")

    def original_lattice():
        raise AssertionError("The original lattice body is not used by this synthetic fixture")

    caller = object.__new__(SyntheticCaller)
    caller.centre = np.asarray([0.5, 0.75])
    caller.xmin, caller.xmax = 0.0, 1.0
    caller._cells_original_lattice = original_lattice
    p = SimpleNamespace(cell_radius=1.25, cell_lattice_type=callers.source.CellLatticeType.HEX)
    caller_tape = SimpleNamespace(rng=rng, events=[], draws=[], locals={})
    image_tape = SimpleNamespace(
        mask=SimpleNamespace(matrix=np.asarray([[1.0, 1.0], [1.0, 1.0]])),
        picker=SimpleNamespace(filename=str(filename)),
        splines=[],
        hull=SimpleNamespace(vertices=np.asarray([0, 1])),
        locals={},
        events=[],
    )
    a, b = np.asarray([0.0, 1.0]), np.asarray([0.0, 1.0])
    constructed = dict(
        cell_radius=p.cell_radius,
        make_all_operators=False,
        single_cell=True,
        n_tverts=2,
        n_tedges=1,
        n_tcell=1,
        center=caller.centre,
        synthetic_a=a,
        synthetic_b=b,
        synthetic_aliases=[a],
    )
    prepared = {key: np.asarray([0.0, 1.0]) for key in core.REQUIRED_PRE_MESH_FIELDS}
    prepared.update(
        constructed,
        tri_verts=np.asarray([[0.0, 0.0], [1.0, 0.0]]),
        tri_edges=np.asarray([[0, 1]]),
        tri_cells=np.asarray([[0, 1]]),
    )
    # Cache identity includes original attribute insertion order. pre_mesh
    # extends the constructed instance; it does not replace its __dict__.
    prepared = dict(constructed, **prepared)
    ids = ("synthetic-point-0", "synthetic-point-1")
    expected = core.initial._Observer(ids)
    expected.add("synthetic_constructor", dict(synthetic_only=True))
    expected.add("synthetic_pre_mesh", dict(synthetic_only=True))
    initial_request = SimpleNamespace(
        identity="synthetic-initial-request",
        upstream=(None, None, prelude),
        stream_before=streams["before"],
        constructor_point_ids=ids,
        constructor_kwargs=dict(
            cell_radius=p.cell_radius,
            seed_points=None,
            use_alpha_shape=False,
            allow_merging=False,
            single_cell_noise=0.1,
            single_cell_sides=6,
            image_mask=None,
            make_all_operators=False,
            mesh_type="tri",
            center=caller.centre,
        ),
    )
    initial_state = SimpleNamespace(
        identity="synthetic-retained-initial-state",
        constructed_cache=snapshot(constructed),
        cache=snapshot(prepared),
        retained_point_ids=ids,
        stream_after=streams["pre_mesh"],
        stream_after_constructor=streams["constructed"],
        events=tuple(expected.events),
        warnings=(),
    )
    core_request = SimpleNamespace(
        identity="synthetic-core-request",
        initial_request=initial_request,
        initial_state=initial_state,
    )
    caller_request = callers.Request(core_request, "")

    def request_record(request):
        result = dict(synthetic_only=True, core=request.core_request.identity)
        if request_metadata is not None:
            result["frozen_metadata"] = request_metadata
        return result

    monkeypatch.setattr(callers, "request_record", request_record)
    caller_request = replace(
        caller_request, identity=core.records._digest(callers.request_record(caller_request))
    )
    monkeypatch.setattr(callers, "_verify_sources", lambda: dict(producers))
    monkeypatch.setattr(images, "_verify_sources", lambda: dict(producers))
    monkeypatch.setattr(mesh, "_verify_sources", lambda: dict(producers))

    def caller_audit(actual, parameters, tape, *upstream):
        assert actual is caller and parameters is p and tape is caller_tape
        return snapshot(dict(synthetic_only=True, events=tape.events, draws=tape.draws))

    monkeypatch.setattr(callers, "_audit", caller_audit)
    caller_trial = callers.Trial(
        caller_request.identity,
        snapshot({}),
        snapshot(callers._parameters(p)),
        snapshot(callers._public(caller)),
        caller_audit(caller, p, caller_tape),
        (),
        streams["before"],
        (),
        "synthetic_only",
        None,
        None,
        None,
        "",
    )
    caller_trial = replace(
        caller_trial, identity=core.records._digest(callers.trial_record(caller_trial))
    )
    caller_owner = object.__new__(callers.CallerOwner)
    caller_graph, caller_edges = callers._graph(caller, p, caller_tape)
    parent_caller = dict(
        request=caller_request,
        caller=caller,
        parameters=p,
        tape=caller_tape,
        trial=caller_trial,
        producers=dict(producers),
        invalid=False,
        graph=caller_graph,
        graph_edges=caller_edges,
        bindings=callers._bindings(caller),
    )
    callers._ISSUED[caller_owner] = parent_caller

    def image_context(owner):
        return callers._validate_owner(owner), prelude

    def image_audit(tape, retained):
        assert tape is image_tape and retained is prelude
        return snapshot(dict(matrix=tape.mask.matrix))

    monkeypatch.setattr(images, "_context", image_context)
    monkeypatch.setattr(images, "_audit", image_audit)
    monkeypatch.setattr(
        images,
        "request_record",
        lambda r: dict(synthetic_only=True, caller=callers._authority(r.caller)["trial"].identity),
    )
    image_request = images.Request(caller_owner, "")
    image_request = replace(
        image_request, identity=core.records._digest(images.request_record(image_request))
    )
    image_trial = images.Trial(
        image_request.identity,
        image_audit(image_tape, prelude),
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
    image_owner = object.__new__(images.ImageOwner)
    image_graph, image_edges = images._graph(image_tape)
    parent_image = dict(
        request=image_request,
        trial=image_trial,
        tape=image_tape,
        caller=caller,
        rng=rng,
        rng_epoch="before",
        graph=image_graph,
        graph_edges=image_edges,
        producers=dict(producers),
        invalid=False,
    )
    images._ISSUED[image_owner] = parent_image

    def fail(stage):
        try:
            raise SyntheticSourceCause("synthetic cause at " + stage)
        except SyntheticSourceCause as cause:
            error = SyntheticSourceFailure("synthetic failure at " + stage)
            errors[stage], errors[stage + "_cause"] = error, cause
            raise error from cause

    def authenticate(context):
        calls["authentication"] += 1
        assert parent_caller["continuation_consumed"] and parent_image["continuation_consumed"]
        if failure == "authentication":
            fail("authentication")

    def constructor(self, **kwargs):
        calls["constructor"] += 1
        calls["order"].append("constructor")
        assert "mesh" not in vars(caller)
        assert kwargs["center"] is caller.centre
        assert self._cells_rng.rng is rng and rng.epoch == "before"
        vars(self).update(constructed)
        rng.epoch = "constructed"
        self._cells_observer.add("synthetic_constructor", dict(synthetic_only=True))
        if failure == "constructor":
            fail("constructor")

    def pre_mesh(self):
        calls["pre_mesh"] += 1
        calls["order"].append("pre_mesh")
        assert caller.mesh is self and self._cells_rng.rng is rng
        vars(self).update(prepared)
        rng.epoch = "pre_mesh"
        self._cells_observer.add("synthetic_pre_mesh", dict(synthetic_only=True))
        if failure == "pre_mesh":
            fail("pre_mesh")

    def operators(self):
        calls["core"] += 1
        calls["order"].append("core")
        assert caller.mesh is self and rng.epoch == "pre_mesh"
        self.delta_tri_0 = np.asarray([[-1.0, 1.0]])
        self.delta_tri_0_inv = np.asarray([[-0.5], [0.5]])
        self._cells_observer.add("synthetic_core_return", dict(synthetic_only=True))
        if failure == "core":
            fail("core")

    def init(self):
        calls["init"] += 1
        calls["order"].append("init")
        assert caller.mesh is self and rng.epoch == "constructed"
        self.pre_mesh()
        self.create_core_operators()
        self._cells_observer.add("synthetic_init_tail", dict(synthetic_only=True))
        if failure == "init_tail":
            fail("init_tail")

    monkeypatch.setattr(mesh, "_authenticate", authenticate)
    monkeypatch.setattr(mesh, "_CONSTRUCTOR", constructor)
    monkeypatch.setattr(mesh, "_PRE_MESH", pre_mesh)
    monkeypatch.setattr(mesh, "_CORE", operators)
    monkeypatch.setattr(mesh, "_INIT_MESH", init)
    request = mesh.from_image(image_owner, law_id=mesh.LAW_ID)
    return SimpleNamespace(
        request=request,
        caller=caller,
        rng=rng,
        p=p,
        caller_owner=caller_owner,
        image_owner=image_owner,
        parent_caller=parent_caller,
        parent_image=parent_image,
        caller_trial=caller_trial,
        image_trial=image_trial,
        core_request=core_request,
        calls=calls,
        errors=errors,
        snapshot=snapshot,
        producers=producers,
        original_kernels=dict(
            constructor=constructor, pre_mesh=pre_mesh, core=operators, init=init
        ),
    )


def assert_consumed(h):
    assert h.caller_owner.trial is h.caller_trial
    assert h.image_owner.trial is h.image_trial
    assert mesh.callers._epoch_consumed(h.caller_owner)
    with pytest.raises(mesh.callers.CallerRejected) as caller:
        _ = h.caller_owner.cells
    with pytest.raises(mesh.images.ImageOwnerRejected) as image:
        _ = h.image_owner.mask
    assert caller.value.stage == "caller_epoch_consumed"
    assert image.value.stage == "image_epoch_consumed"
    with pytest.raises(mesh.ContinuationRejected) as repeated:
        mesh.prepare(h.request)
    assert isinstance(repeated.value.source_error, mesh.images.ImageOwnerRejected)
    assert repeated.value.source_error.stage == "image_epoch_consumed"
    assert repeated.value.partial["parent_epochs_consumed"] is True
    assert repeated.value.partial["this_attempt_retired_parents"] is False


def test_software_literal_dependencies_and_default_paths_unchanged(evidence):
    pins = mesh._verify_sources()
    assert (
        mesh.images.CALLER_PINS["betse_native_single_cell_caller_lattice"]
        == mesh.DEPENDENCIES["betse_native_single_cell_caller_lattice"]
    )
    assert (
        pins[str(Path(mesh.core.__file__).resolve())]
        == mesh.DEPENDENCIES["betse_native_single_cell_core_preparation"]
    )
    assert mesh._CONSTRUCTOR is mesh.core._Runtime.__init__
    assert mesh._CORE is mesh.core._Runtime.create_core_operators
    assert mesh._INIT_MESH is mesh.core.lifecycle.source.LifecycleKernel.init_mesh
    save(evidence, "source-pins", pins)


@pytest.mark.parametrize("value", [None, {}, "inspection", object.__new__(mesh.images.ImageOwner)])
def test_software_absent_authority_is_not_hydrated(value, evidence):
    with pytest.raises(mesh.images.ImageOwnerRejected) as error:
        mesh.from_image(value, law_id=mesh.LAW_ID)
    save(evidence, "refusal", error.value)


def test_software_real_registry_transition_order_shared_identity_and_no_rearm(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    parent_ids = (h.caller_trial.identity, h.image_trial.identity)
    child = mesh.prepare(h.request)
    assert child.cells is h.caller and child.mesh is h.caller.mesh
    assert child.mesh._cells_rng.rng is h.rng
    assert child.mesh.center is h.caller.centre
    assert h.calls == dict(
        authentication=1,
        constructor=1,
        init=1,
        pre_mesh=1,
        core=1,
        order=["constructor", "init", "pre_mesh", "core"],
    )
    assert child.trial.ordering == (
        "parents_preflight_return",
        "parents_retired",
        "constructor_enter",
        "constructor_return",
        "caller_mesh_assignment_enter",
        "caller_mesh_assigned",
        "init_mesh_enter",
        "pre_mesh_enter",
        "pre_mesh_return",
        "core_operators_enter",
        "core_return",
        "init_mesh_return",
    )
    assert child.trial.source_completed
    assert child.trial.stream_before.identity == "before"
    assert child.trial.stream_after.identity == "pre_mesh"
    assert child.trial.identity == mesh.core.records._digest(mesh.trial_record(child.trial))
    assert len(child.trial.events) == 5
    assert (h.caller_trial.identity, h.image_trial.identity) == parent_ids
    assert_consumed(h)
    save(evidence, "trial", child.trial)
    save(evidence, "work-and-order", h.calls)


@pytest.mark.parametrize(
    "stage",
    [
        "authentication",
        "constructor",
        "assignment",
        "assignment_after",
        "pre_mesh",
        "core",
        "init_tail",
    ],
)
def test_software_failure_consumes_parents_and_preserves_actual_partial_state(
    stage, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure=stage)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    error = caught.value
    assert error.source_error is h.errors[stage]
    assert error.source_error.__cause__ is h.errors[stage + "_cause"]
    assert error.__cause__ is error.source_error
    assert error.partial["caller"] is h.caller
    assert error.partial["rng"] is h.rng
    assert error.partial["parent_initial_request"] is h.core_request.initial_request
    assert error.partial["parent_initial_state"] is h.core_request.initial_state
    assert error.partial["parent_caller_trial"] is h.caller_trial
    assert error.partial["parent_image_trial"] is h.image_trial
    assert error.partial["usable_live_child_available"] is False
    if stage == "authentication":
        assert error.trial is None and error.capture_error is not None
        assert error.partial["kernel"] is None and "mesh" not in vars(h.caller)
    else:
        assert error.trial is not None and not error.trial.source_completed
        assert error.partial["kernel"] not in mesh._ACTIVE
        assert ("mesh" in vars(h.caller)) == (stage not in {"constructor", "assignment"})
        if "mesh" in vars(h.caller):
            assert h.caller.mesh is error.partial["kernel"]
        with pytest.raises(mesh.ContinuationRejected):
            error.partial["kernel"].init_mesh()
    assert not any(c.request is h.request for c in mesh._ISSUED.values())
    assert_consumed(h)
    save(evidence, "failure", error)
    save(evidence, "work-and-order", h.calls)


@pytest.mark.parametrize("source_failure", [None, "core"])
@pytest.mark.parametrize("point", ["snapshot", "trial", "identity", "rng", "graphs"])
def test_software_capture_failure_never_issues_child_or_erases_source(
    source_failure, point, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure=source_failure)
    capture = SyntheticCaptureFailure("injected final " + point)
    original_core = mesh._CORE

    def fail_capture(*a, **k):
        raise capture

    def arm():
        if point == "snapshot":
            monkeypatch.setattr(mesh, "_snapshot", fail_capture)
        elif point == "trial":
            monkeypatch.setattr(mesh, "Trial", fail_capture)
        elif point == "identity":
            monkeypatch.setattr(mesh, "trial_record", fail_capture)
        elif point == "rng":
            original_stream = mesh.core.initial._rng_stream

            def stream(rng):
                if mesh._ACTIVE:
                    return original_stream(rng)
                raise capture

            monkeypatch.setattr(mesh.core.initial, "_rng_stream", stream)
        else:
            monkeypatch.setattr(mesh, "_graphs", fail_capture)

    def operators(self):
        try:
            original_core(self)
        finally:
            arm()

    monkeypatch.setattr(mesh, "_CORE", operators)
    if point == "graphs" and source_failure is not None:
        # Failed source trials never enter child issuance; prove the real source
        # failure survives and no graph capture is attempted at all.
        expected_capture = None
    else:
        expected_capture = capture
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    error = caught.value
    assert error.capture_error is expected_capture
    assert error.source_error is (None if source_failure is None else h.errors[source_failure])
    assert h.caller.mesh is error.partial["kernel"]
    assert error.partial["parent_epochs_consumed"]
    assert not any(c.request is h.request for c in mesh._ISSUED.values())
    assert_consumed(h)
    save(evidence, "failure", error)


@pytest.mark.parametrize("change", ["ids", "events", "warnings", "cache", "epoch"])
def test_software_actual_premesh_evidence_must_match_retained_parent(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    before = mesh._PRE_MESH

    def changed(self):
        before(self)
        if change == "ids":
            self._cells_observer.ids = ("changed-0", "changed-1")
        elif change == "events":
            event = self._cells_observer.events[-1]
            self._cells_observer.events[-1] = replace(event, method="changed")
        elif change == "warnings":
            mesh.warnings.warn("synthetic warning difference", RuntimeWarning)
        elif change == "cache":
            self.tri_verts[0, 0] = 9.0
        else:
            h.rng.epoch = "before"

    monkeypatch.setattr(mesh, "_PRE_MESH", changed)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    assert caught.value.source_error is not None
    assert h.calls["core"] == 0
    assert h.caller.mesh is caught.value.partial["kernel"]
    assert_consumed(h)
    save(evidence, "failure", caught.value)


def test_software_frozen_request_evidence_preserves_bits_and_original_parents(
    monkeypatch, tmp_path, evidence
):
    bits = np.asarray([0x8000000000000000, 0x7FF8000000000042], dtype=np.uint64)
    raw = bits.view(np.float64)
    original_bytes = raw.tobytes()
    metadata = MappingProxyType(
        {"nested": MappingProxyType({"negative_zero": -0.0, "raw": raw}), "labels": (1, "x")}
    )
    h = harness(monkeypatch, tmp_path, request_metadata=metadata)
    original_request = h.parent_caller["request"]
    observed = mesh._parent_evidence(h.parent_image, h.parent_caller)
    declaration = mesh.core.caches.plain(observed)["caller_request"]
    save(evidence, "parent-evidence", observed)
    assert declaration["frozen_metadata"]["nested"]["negative_zero"] == {
        "float64_bits": "0000000000000080"
    }
    assert declaration["frozen_metadata"]["nested"]["raw"] == {
        "dtype": raw.dtype.str,
        "shape": [2],
        "sha256": hashlib.sha256(original_bytes).hexdigest(),
    }
    assert mesh.core.records._digest(declaration) == original_request.identity
    child = mesh.prepare(h.request)
    save(evidence, "trial", child.trial)
    context = mesh._authority(child)
    assert context.caller_request is original_request
    assert context.parent_evidence.identity == observed.identity
    assert raw.tobytes() == original_bytes and type(metadata) is MappingProxyType
    assert h.parent_caller["request"] is original_request
    assert h.calls["constructor"] == h.calls["core"] == 1
    assert_consumed(h)


@pytest.mark.parametrize("changed", ["signed_zero", "array_nan_bits"])
def test_software_frozen_request_backing_mutation_refuses_before_constructor(
    changed, monkeypatch, tmp_path, evidence
):
    raw = np.asarray([0x7FF8000000000042], dtype=np.uint64)
    backing = {"value": -0.0, "array": raw.view(np.float64)}
    metadata = MappingProxyType({"nested": MappingProxyType(backing)})
    h = harness(monkeypatch, tmp_path, request_metadata=metadata)
    original = mesh._authenticate

    def authenticate(context):
        original(context)
        if changed == "signed_zero":
            backing["value"] = 0.0
        else:
            raw[0] = 0x7FF8000000000043

    monkeypatch.setattr(mesh, "_authenticate", authenticate)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    save(evidence, "failure", caught.value)
    assert "Authentication changed original source evidence" in str(caught.value.source_error)
    assert h.calls["authentication"] == 1 and h.calls["constructor"] == 0
    assert "mesh" not in vars(h.caller)
    assert caught.value.partial["this_attempt_retired_parents"]
    assert_consumed(h)


@pytest.mark.parametrize(
    "change",
    [
        "rng",
        "mesh",
        "caller",
        "array",
        "alias",
        "events",
        "wrapper",
        "method",
        "parent",
        "image",
        "parameters",
        "registry",
        "caller_code",
        "occurrences",
        "stack",
        "producer",
    ],
)
def test_software_child_rejects_stale_or_retargeted_actual_authority(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    child = mesh.prepare(h.request)
    context = mesh._authority(child)
    original_final = context.trial.final_cache.identity
    if change == "rng":
        h.rng.epoch = "before"
    elif change == "mesh":
        h.caller.mesh = object()
    elif change == "caller":
        h.caller.xmin = 7.0
    elif change == "array":
        h.caller.mesh.tri_verts[0, 0] = 8.0
    elif change == "alias":
        a, b = h.caller.mesh.synthetic_a, h.caller.mesh.synthetic_b
        assert a is not b and np.array_equal(a, b)
        old_objects, old_edges = mesh._graphs(context)[2]
        h.caller.mesh.synthetic_aliases[0] = b
        assert mesh._snapshot(context).identity == original_final
        new_objects, new_edges = mesh._graphs(context)[2]
        assert len(old_objects) == len(new_objects)
        assert all(a is b for a, b in zip(old_objects, new_objects, strict=True))
        assert old_edges != new_edges
    elif change == "events":
        context.observer.events[-1] = replace(context.observer.events[-1])
    elif change == "wrapper":
        context.kernel._cells_rng = SimpleNamespace(rng=h.rng, observer=context.observer)
    elif change == "method":
        monkeypatch.setattr(mesh, "_CORE", lambda self: None)
    elif change == "parent":
        h.parent_caller["continuation_consumed"] = False
    elif change == "image":
        h.parent_image["tape"].mask.matrix = np.array(h.parent_image["tape"].mask.matrix, copy=True)
    elif change == "parameters":
        h.p.cell_radius = 5.0
    elif change == "registry":
        mesh.images._ISSUED[h.image_owner] = dict(h.parent_image)
    elif change == "caller_code":
        h.caller._cells_original_lattice.__code__ = (lambda: None).__code__
    elif change == "occurrences":
        context.observer.ids = ("different-0", "different-1")
    elif change == "stack":
        context.observer.stack.append("unexpected_active_native_call")
    else:
        h.producers["external_drift"] = "changed"
    with pytest.raises(mesh.ContinuationRejected) as caught:
        _ = child.mesh
    assert caught.value.stage == "child_authority_drift"
    assert context.invalid
    assert child.trial is context.trial
    save(evidence, "refusal", caught.value)
    save(evidence, "trial", child.trial)


@pytest.mark.parametrize(
    "name",
    mesh.GUARDED_NATIVE_METHODS,
)
def test_software_raw_runtime_cannot_bypass_driver(name, evidence):
    raw = object.__new__(mesh._Runtime)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        getattr(raw, name)()
    assert caught.value.stage == "source_call_unavailable"
    save(evidence, "refusal", caught.value)


def test_software_guard_roster_covers_every_inherited_native_callable(evidence):
    inherited = {
        name
        for base in mesh.core._Runtime.__mro__
        if base is not object
        for name, value in vars(base).items()
        if callable(value)
    }
    assert set(mesh.core.initial.OBSERVED_METHODS) <= set(mesh.GUARDED_NATIVE_METHODS)
    assert inherited | {"init_mesh"} == set(mesh.GUARDED_NATIVE_METHODS)
    assert len(mesh.GUARDED_NATIVE_METHODS) == len(set(mesh.GUARDED_NATIVE_METHODS))
    for name in mesh.GUARDED_NATIVE_METHODS:
        assert name in vars(mesh._Runtime)
    for name, method in mesh._INHERITED_NATIVE.items():
        assert method is getattr(mesh.core._Runtime, name)
        assert not hasattr(getattr(mesh._Runtime, name), "__wrapped__")
    save(
        evidence,
        "guard-roster",
        dict(
            guarded=mesh.GUARDED_NATIVE_METHODS,
            initial_observed=mesh.core.initial.OBSERVED_METHODS,
            inherited=sorted(inherited),
        ),
    )


@pytest.mark.parametrize("outcome", ["success", "failed"])
@pytest.mark.parametrize("name", mesh.GUARDED_NATIVE_METHODS)
def test_software_successful_and_failed_raw_mesh_refuse_before_observer_or_rng(
    name, outcome, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure="core" if outcome == "failed" else None)
    child = failure = None
    if outcome == "success":
        child = mesh.prepare(h.request)
        raw = child.mesh
    else:
        with pytest.raises(mesh.ContinuationRejected) as caught:
            mesh.prepare(h.request)
        failure = caught.value
        raw = failure.partial["kernel"]
        assert h.caller.mesh is raw
        assert failure.source_error is h.errors["core"]
    observer = raw._cells_observer
    before = h.snapshot(mesh.core.initial._public_cache(raw))
    events = tuple(observer.events)
    stack, ids, epoch = tuple(observer.stack), observer.ids, h.rng.epoch
    calls = dict(h.calls)
    calls["order"] = list(h.calls["order"])
    assert raw not in mesh._ACTIVE
    with pytest.raises(mesh.ContinuationRejected) as caught:
        getattr(raw, name)()
    assert caught.value.stage == "source_call_unavailable"
    assert h.snapshot(mesh.core.initial._public_cache(raw)).identity == before.identity
    assert len(observer.events) == len(events)
    assert all(a is b for a, b in zip(observer.events, events, strict=True))
    assert tuple(observer.stack) == stack and observer.ids is ids
    assert h.rng.epoch == epoch and h.calls == calls
    if child is not None:
        assert child.mesh is raw and child.cells is h.caller
    else:
        assert_consumed(h)
    save(evidence, "direct-entry-refusal", caught.value)
    save(evidence, "unchanged-state", dict(cache=before, events=events, ids=ids, epoch=epoch))
    if failure is not None:
        save(evidence, "original-failed-trial", failure)


@pytest.mark.parametrize("phase", ["constructor", "pre_mesh", "core"])
def test_software_nested_inherited_delegates_preserve_arguments_returns_and_actual_object(
    phase, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    marker, result = object(), object()
    calls = []
    entry = "make_single_cell_points" if phase == "constructor" else "create_tri_mesh"
    if phase == "core":
        entry = "_cells_pinv"

    def primitive(self, value, *, named):
        assert self is mesh._context(self).kernel
        assert value is marker and named is marker
        calls.append("primitive")
        return result

    def callback(self, *args, **kwargs):
        assert self._cells_rng.rng is h.rng
        assert args == (marker,) and kwargs["named"] is marker
        if phase == "constructor":
            assert "mesh" not in vars(h.caller)
        else:
            assert h.caller.mesh is self
        calls.append(entry)
        assert self.area(marker, named=marker) is result
        return result

    monkeypatch.setitem(mesh._INHERITED_NATIVE, "area", primitive)
    monkeypatch.setitem(mesh._INHERITED_NATIVE, entry, callback)
    name = {"constructor": "_CONSTRUCTOR", "pre_mesh": "_PRE_MESH", "core": "_CORE"}[phase]
    original = getattr(mesh, name)

    def outer(self, **kwargs):
        original(self, **kwargs)
        assert getattr(self, entry)(marker, named=marker) is result

    monkeypatch.setattr(mesh, name, outer)
    child = mesh.prepare(h.request)
    assert child.mesh is h.caller.mesh
    assert child.mesh._cells_rng.rng is h.rng
    assert calls == [entry, "primitive"]
    assert child.trial.source_completed
    # Active nested access does not leave the inherited method armed after sealing.
    with pytest.raises(mesh.ContinuationRejected):
        getattr(child.mesh, entry)(marker, named=marker)
    assert calls == [entry, "primitive"]
    save(evidence, "trial", child.trial)
    save(evidence, "nested-calls", calls)


def test_software_nested_inherited_failure_retains_source_cause_and_guarded_partial(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    source = SyntheticSourceFailure("nested synthetic point construction failed")
    cause = SyntheticSourceCause("original nested synthetic cause")
    calls = []

    def points(self):
        assert self._cells_rng.rng is h.rng
        calls.append("nested-points")
        raise source from cause

    monkeypatch.setitem(mesh._INHERITED_NATIVE, "make_single_cell_points", points)
    original = mesh._CONSTRUCTOR

    def constructor(self, **kwargs):
        original(self, **kwargs)
        self.make_single_cell_points()

    monkeypatch.setattr(mesh, "_CONSTRUCTOR", constructor)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    error = caught.value
    assert error.source_error is source and source.__cause__ is cause
    assert "mesh" not in vars(h.caller)
    assert error.partial["kernel"] is not None
    with pytest.raises(mesh.ContinuationRejected):
        error.partial["kernel"].make_single_cell_points()
    assert calls == ["nested-points"]
    assert_consumed(h)
    save(evidence, "failure", error)


@pytest.mark.parametrize("change", ["delegate", "wrapper"])
def test_software_changed_inherited_method_binding_invalidates_child(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    child = mesh.prepare(h.request)
    if change == "delegate":
        monkeypatch.setitem(mesh._INHERITED_NATIVE, "make_single_cell_points", lambda self: None)
    else:
        monkeypatch.setattr(mesh._Runtime, "make_single_cell_points", lambda self: None)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        _ = child.mesh
    assert caught.value.stage == "child_authority_drift"
    assert child.trial.source_completed
    save(evidence, "refusal", caught.value)


def test_software_native_parent_or_height_or_checkpoint_is_not_admitted(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    child = mesh.prepare(h.request)
    for value in (child, child.mesh):
        with pytest.raises(TypeError):
            pickle.dumps(value)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.require_later_continuation(child, parameters=SimpleNamespace(cell_height=1.0))
    assert caught.value.stage == "later_caller_authority_unavailable"
    assert caught.value.partial["invalidated_owners"] == mesh.INVALIDATED_OWNERS
    assert len(mesh.INVALIDATED_OWNERS) == 11
    save(evidence, "refusal", caught.value)


def test_software_nested_accounting_observes_work_without_executing_source(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    namespace = dict(__name__=mesh.core.initial.__name__)
    exec(compile("def prepare():\n    return 17\n", "<synthetic-work-entry>", "exec"), namespace)
    original = mesh._authenticate

    def authenticate(context):
        assert namespace["prepare"]() == 17
        original(context)

    monkeypatch.setattr(mesh, "_authenticate", authenticate)
    assert sys.gettrace() is None
    child = mesh.prepare(h.request)
    assert sys.gettrace() is None
    work = [w for w in child.trial.work if w["kind"] == "python_source_entry"]
    assert len(work) == 1 and work[0]["phase"] == "authentication"
    assert work[0]["method"] == "prepare"
    assert h.calls["authentication"] == h.calls["constructor"] == h.calls["core"] == 1
    save(evidence, "work", child.trial.work)


def test_software_authentication_failure_restores_trace_and_consumes_epoch(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, failure="authentication")
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    assert sys.gettrace() is None
    assert h.calls["authentication"] == 1 and h.calls["constructor"] == 0
    assert_consumed(h)
    save(evidence, "failure", caught.value)


def test_software_paired_retirement_failure_after_publication_is_irreversible(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    original = mesh.callers._consume_epoch
    failure = SyntheticSourceFailure("retirement bookkeeping failed after the shared claim")

    def retire(*args, **kwargs):
        value = original(*args, **kwargs)
        # Both public owners already refuse while the image bookkeeping flag
        # has not been written. That flag cannot be the retirement authority.
        with pytest.raises(mesh.callers.CallerRejected):
            _ = h.caller_owner.cells
        with pytest.raises(mesh.images.ImageOwnerRejected):
            _ = h.image_owner.mask
        assert value is h.parent_caller
        raise failure

    monkeypatch.setattr(mesh.callers, "_consume_epoch", retire)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    error = caught.value
    assert error.source_error is failure
    assert error.partial["source_stage"] == "retirement"
    assert error.partial["this_attempt_retired_parents"]
    assert error.partial["kernel"] is None and "mesh" not in vars(h.caller)
    assert h.calls["authentication"] == h.calls["constructor"] == 0
    # Attempts to edit the old metadata flags do not undo the shared claim.
    h.parent_caller["continuation_consumed"] = False
    h.parent_image["continuation_consumed"] = False
    assert_consumed(h)
    save(evidence, "failure", error)


@pytest.mark.parametrize("change", ["caller", "rng", "caller_invalid", "image_invalid"])
def test_software_pair_preflight_refuses_before_claiming_either_epoch(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    if change == "caller":
        h.parent_image["caller"] = SimpleNamespace()
    elif change == "rng":
        h.parent_image["rng"] = SimpleNamespace(epoch="before")
    elif change == "caller_invalid":
        h.parent_caller["invalid"] = True
    else:
        h.parent_image["invalid"] = True
    with pytest.raises((mesh.ContinuationRejected, mesh.images.ImageOwnerRejected)) as caught:
        mesh.prepare(h.request)
    assert not mesh.callers._epoch_consumed(h.caller_owner)
    assert not h.parent_caller.get("continuation_consumed", False)
    assert not h.parent_image.get("continuation_consumed", False)
    assert h.calls["authentication"] == h.calls["constructor"] == 0
    assert h.caller_owner.trial is h.caller_trial and h.image_owner.trial is h.image_trial
    if change.endswith("invalid"):
        assert (
            h.parent_caller["invalid"] if change == "caller_invalid" else h.parent_image["invalid"]
        )
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize("change", ["image_equal_object", "caller_equal_object", "rng_epoch"])
def test_software_preflight_bookkeeping_cannot_replace_original_issuance_graph(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    original = mesh._before_claim

    def before(context):
        if change == "image_equal_object":
            mask = h.parent_image["tape"].mask
            old = mask.matrix
            mask.matrix = np.array(old, copy=True)
            assert mask.matrix is not old and np.array_equal(mask.matrix, old)
        elif change == "caller_equal_object":
            old = h.caller.centre
            h.caller.centre = np.array(old, copy=True)
            assert h.caller.centre is not old and np.array_equal(h.caller.centre, old)
        else:
            h.rng.epoch = "constructed"
        original(context)

    monkeypatch.setattr(mesh, "_before_claim", before)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    assert not mesh.callers._epoch_consumed(h.caller_owner)
    assert not caught.value.partial["this_attempt_retired_parents"]
    assert h.parent_image["invalid"]
    assert h.calls["authentication"] == h.calls["constructor"] == 0
    assert "mesh" not in vars(h.caller)
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize("phase", ["preflight", "authentication", "constructor", "init"])
def test_software_reentrant_prepare_never_acquires_the_same_pair(
    phase, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    errors = []

    def nested():
        try:
            mesh.prepare(h.request)
        except mesh.ContinuationRejected as error:
            errors.append(error)
        else:
            pytest.fail("A reentrant continuation acquired an owned parent pair")

    if phase == "preflight":
        original = mesh._parent_evidence
        entered = False

        def parent(*args):
            nonlocal entered
            if not entered:
                entered = True
                nested()
            return original(*args)

        monkeypatch.setattr(mesh, "_parent_evidence", parent)
    elif phase == "authentication":
        original = mesh._authenticate

        def authenticate(context):
            nested()
            original(context)

        monkeypatch.setattr(mesh, "_authenticate", authenticate)
    else:
        name = "_CONSTRUCTOR" if phase == "constructor" else "_INIT_MESH"
        original = getattr(mesh, name)

        def method(self, **kwargs):
            nested()
            return original(self, **kwargs)

        monkeypatch.setattr(mesh, name, method)
    child = mesh.prepare(h.request)
    assert len(errors) == 1
    assert isinstance(errors[0].source_error, mesh.images.ImageOwnerRejected)
    expected = "retirement_reentrant" if phase == "preflight" else "image_epoch_consumed"
    assert errors[0].source_error.stage == expected
    assert h.calls["authentication"] == h.calls["constructor"] == h.calls["init"] == 1
    assert child.mesh is h.caller.mesh
    assert_consumed(h)
    save(evidence, "reentrant-refusal", errors[0])
    save(evidence, "outer-trial", child.trial)


@pytest.mark.parametrize("change", ["rng_epoch", "rng_object", "caller_cache", "alias", "invalid"])
def test_software_post_retirement_authentication_cannot_hide_live_parent_drift(
    change, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    original = mesh._authenticate

    def authenticate(context):
        original(context)
        if change == "rng_epoch":
            h.rng.epoch = "constructed"
        elif change == "rng_object":
            h.parent_caller["tape"].rng = SimpleNamespace(epoch="before")
        elif change == "caller_cache":
            h.caller.xmin = 9.0
        elif change == "alias":
            h.caller.centre = np.array(h.caller.centre, copy=True)
        else:
            h.parent_image["invalid"] = True

    monkeypatch.setattr(mesh, "_authenticate", authenticate)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    assert caught.value.source_error is not None
    assert caught.value.partial["parent_epochs_consumed"]
    assert h.calls["authentication"] == 1 and h.calls["constructor"] == 0
    assert "mesh" not in vars(h.caller)
    assert_consumed(h)
    save(evidence, "failure", caught.value)


@pytest.mark.parametrize("method", ["random", "set_state"])
def test_software_authentication_cannot_touch_continuing_rng_even_if_epoch_would_be_restored(
    method, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    calls = []

    class SyntheticRng:
        epoch = "before"

        def random(self):
            calls.append("random")
            self.epoch = "constructed"

        def set_state(self):
            calls.append("set_state")
            self.epoch = "before"

    rng = SyntheticRng()
    h.rng = rng
    h.parent_caller["tape"].rng = rng
    h.parent_image["rng"] = rng
    # Issue a synthetic metadata epoch on this stand-in without drawing or
    # executing any actual constructor/native RNG function.
    h.parent_caller["graph"], h.parent_caller["graph_edges"] = mesh.callers._graph(
        h.caller, h.p, h.parent_caller["tape"]
    )
    original = mesh._authenticate

    def authenticate(context):
        original(context)
        getattr(rng, method)()
        rng.set_state()

    monkeypatch.setattr(mesh, "_authenticate", authenticate)
    previous = sys.getprofile()
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    assert sys.getprofile() is previous
    assert calls == [] and rng.epoch == "before"
    assert h.calls["constructor"] == 0
    assert "must not call/advance/reset" in str(caught.value.source_error)
    assert_consumed(h)
    save(evidence, "failure", caught.value)


@pytest.mark.parametrize("step", ["constructor", "init_mesh", "pre_mesh", "create_core_operators"])
def test_software_reentrant_or_repeated_raw_source_steps_refuse_without_retry(
    step, monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    name = {
        "constructor": "_CONSTRUCTOR",
        "init_mesh": "_INIT_MESH",
        "pre_mesh": "_PRE_MESH",
        "create_core_operators": "_CORE",
    }[step]
    original = getattr(mesh, name)

    def method(self, **kwargs):
        original(self, **kwargs)
        if step == "constructor":
            self.__init__(**kwargs)
        else:
            getattr(self, step)()

    monkeypatch.setattr(mesh, name, method)
    with pytest.raises(mesh.ContinuationRejected) as caught:
        mesh.prepare(h.request)
    assert "Repeated/reentrant source step" in str(caught.value.source_error)
    assert caught.value.partial["this_attempt_retired_parents"]
    assert h.calls["constructor"] == 1
    if step != "constructor":
        assert h.caller.mesh is caught.value.partial["kernel"]
    assert_consumed(h)
    save(evidence, "failure", caught.value)
