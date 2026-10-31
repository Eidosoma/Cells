"""Process-local source transport controls; every native numerical entry is blocked."""

import hashlib
import os
import pickle
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_dec_parent as transport
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    core,
    harness,
    inject_capture,
    save,
)


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_DEC_TRANSPORT_EVIDENCE", str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def synthetic(
    monkeypatch,
    *,
    outcome="success",
    warning=None,
    cut_failure=False,
    method_failure=None,
    cut_chain=False,
):
    """A deliberately synthetic runtime; no synthetic object is native authority.

    The existing harness blocks constructor/pre_mesh/core, replay, pinv, image,
    lattice and real RNG work. Here only the early typed-request check and its
    metadata signature are replaced for the explicitly synthetic request.
    """
    h = harness(monkeypatch, outcome=outcome, warning=warning)
    base = core._Runtime
    guarded_runtime = transport._Runtime
    vertices = np.asarray([[0.0, 1.0], [2.0, 3.0]])
    polygons = np.empty(1, dtype=object)
    polygons[0] = vertices
    view = vertices.view()
    added = dict(vor_verts=vertices, vcell_verts=polygons, tri_verts=vertices, synthetic_view=view)
    h.parent.constructed_cache = h.original_snapshot(
        dict(core.caches.plain(h.parent.constructed_cache), **added)
    )
    h.parent.cache = h.original_snapshot(dict(core.caches.plain(h.parent.cache), **added))
    h.calls["synthetic_cut"] = 0
    h.calls["synthetic_methods"] = []
    h.returned = (np.asarray([4, 1]), np.asarray([3]))

    def forbidden(*args, **kwargs):
        h.calls["native_attempts"].append("post-cut-native-entry")
        raise AssertionError("Native post-cut equations are forbidden in these software controls")

    for name in transport._METHODS:
        monkeypatch.setattr(transport.source.MeshKernel, name, forbidden)
    monkeypatch.setattr(transport.source, "cut_through_contacts", forbidden)
    for name in vars(transport.source.CellKernel):
        if not name.startswith("_"):
            monkeypatch.setattr(transport.source.CellKernel, name, forbidden)

    class SyntheticCallable(base):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.__dict__.update(added)
            self._cells_rng.observer = self._cells_observer
            h.kernel = self

        create_tri_map = guarded_runtime.create_tri_map
        create_mappings = guarded_runtime.create_mappings
        create_core_operators = guarded_runtime.create_core_operators
        cut_mesh = guarded_runtime.cut_mesh
        __reduce_ex__ = guarded_runtime.__reduce_ex__

        def synthetic_cut(self, targets):
            h.calls["synthetic_cut"] += 1
            h.cut_self, h.cut_targets = self, targets
            # Literal mutation and rebinding test transport, never cut geometry.
            self.vor_verts[0, 0] = 17.0
            self.vcell_verts = np.empty(0, dtype=object)
            core.warnings.warn("synthetic cut warning", RuntimeWarning)
            if cut_chain:
                self.create_tri_map()
                self.create_mappings(ignoreb=True)
                self.create_core_operators()
            if cut_failure:
                try:
                    raise SyntheticSourceCause("original synthetic cut cause")
                except SyntheticSourceCause as cause:
                    h.errors["cut_cause"] = cause
                    error = SyntheticSourceFailure("original synthetic cut failure")
                    h.errors["cut"] = error
                    raise error from cause
            return h.returned

    def native_method(name):
        def invoke(self, *args, **kwargs):
            h.calls["synthetic_methods"].append(
                dict(method=name, self=self, args=args, kwargs=kwargs)
            )
            if not core._preparing_runtime(self):
                self.synthetic_method_mutation = name
                if method_failure == name:
                    try:
                        raise SyntheticSourceCause("original synthetic method cause")
                    except SyntheticSourceCause as cause:
                        h.errors["method_cause"] = cause
                        error = SyntheticSourceFailure("original synthetic method failure")
                        h.errors["method"] = error
                        raise error from cause
            if name == "create_core_operators":
                return base.create_core_operators(self, *args, **kwargs)
            return None

        return invoke

    monkeypatch.setattr(transport, "_Runtime", SyntheticCallable)
    monkeypatch.setattr(transport, "_NATIVE_CUT", SyntheticCallable.synthetic_cut)
    monkeypatch.setattr(
        transport, "_NATIVE_METHODS", {name: native_method(name) for name in transport._METHODS[1:]}
    )
    monkeypatch.setattr(transport, "_check_request", lambda request: None)
    monkeypatch.setattr(
        transport, "_request_signature", lambda request: core.records._digest(request.identity)
    )
    # A cache decoder must never become a native object constructor.
    monkeypatch.setattr(core.caches, "plain", forbidden)
    h.vertices, h.polygons = vertices, polygons
    h.base_runtime = base
    return h


def prepare(h, evidence):
    save(evidence, "request", h.request)
    try:
        parent = transport.prepare(h.request, law_id=transport.LAW_ID)
    except BaseException as error:
        save(evidence, "error", dict(error=error, calls=h.calls))
        if isinstance(error, core.CorePrerequisiteRejected):
            save(
                evidence,
                "core-error",
                dict(trial=error.trial, partial=error.partial, runtime=error.live_runtime),
            )
        elif isinstance(error, transport.NativeParentRejected):
            save(evidence, "transport-error", dict(runtime=error.runtime, partial=error.partial))
        raise
    save(evidence, "prepared", dict(record=transport.source_record(parent), calls=h.calls))
    return parent


def no_native(h):
    assert h.calls["native_attempts"] == []
    assert h.calls["real_rng_attempts"] == []


def test_software_original_method_bindings_and_source_pins(evidence):
    assert transport._NATIVE_CUT is transport.source.MeshKernel.cut_mesh
    for name in transport._METHODS[1:]:
        assert transport._NATIVE_METHODS[name] is getattr(core._Runtime, name)
    assert len(transport._verify_sources()) == 3
    save(evidence, "source-pins", transport._verify_sources())


def test_software_default_core_still_returns_only_its_sealed_state(monkeypatch, evidence):
    h = synthetic(monkeypatch)

    class DefaultRuntime(transport._Runtime):
        create_core_operators = h.base_runtime.create_core_operators

    monkeypatch.setattr(core, "_Runtime", DefaultRuntime)
    state = core.prepare(h.request)
    assert type(state) is core.State and state.core_source_completed
    assert not hasattr(h.kernel, "_cells_dec_source_authority")
    with pytest.raises(transport.NativeParentRejected) as caught:
        h.kernel.cut_mesh(np.asarray([], dtype=int))
    assert caught.value.stage == "live_authority_unavailable"
    assert h.calls["synthetic_core"] == 1 and h.calls["synthetic_cut"] == 0
    no_native(h)
    save(evidence, "default-core", dict(state=state, calls=h.calls))


def test_software_invalid_runtime_type_refuses_before_authentication(monkeypatch, evidence):
    monkeypatch.setattr(core, "validate_request", lambda *a: pytest.fail("Unexpected replay"))
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        core.prepare(None, _runtime_type=object)
    assert caught.value.stage == "live_runtime_type"
    save(evidence, "runtime-type-refusal", caught.value)


@pytest.mark.parametrize("value", [None, {}, {"source_completed": True}, SimpleNamespace()])
def test_software_absent_or_supplied_authority_refuses_before_replay(value, monkeypatch, evidence):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("native-work")
        raise AssertionError("Refusal reached source work")

    monkeypatch.setattr(core, "prepare", forbidden)
    monkeypatch.setattr(core, "validate_request", forbidden)
    monkeypatch.setattr(core.initial, "validate_state", forbidden)
    with pytest.raises(transport.NativeParentRejected) as caught:
        transport.prepare(value, law_id=transport.LAW_ID)
    assert caught.value.stage == "upstream_request_owner"
    assert calls == []
    save(evidence, "refusal", dict(error=caught.value, calls=calls))


def test_software_forged_handle_and_wrong_law_refuse(monkeypatch, evidence):
    monkeypatch.setattr(core, "prepare", lambda *a, **k: pytest.fail("Source work forbidden"))
    with pytest.raises(transport.NativeParentRejected) as caught:
        transport.prepare(None, law_id="a polygon or dictionary cannot opt in")
    assert caught.value.stage == "opt_in"
    with pytest.raises(TypeError):
        transport.SingleCellDECSourceParent()
    forged = object.__new__(transport.SingleCellDECSourceParent)
    for candidate in (forged, None, {}, SimpleNamespace(mesh=object())):
        with pytest.raises(transport.NativeParentRejected) as caught:
            transport.source_record(candidate)
        assert caught.value.stage == "live_authority_unavailable"
    mesh_without_execution = object.__new__(transport._Runtime)
    for method in transport._METHODS:
        with pytest.raises(transport.NativeParentRejected) as caught:
            arguments = (np.asarray([], dtype=int),) if method == "cut_mesh" else ()
            getattr(mesh_without_execution, method)(*arguments)
        assert caught.value.stage == "live_authority_unavailable"
    save(evidence, "refused", dict(forged_handle_admitted=False, native_calls=0))


def test_software_exact_runtime_aliases_events_and_no_extra_replay(monkeypatch, evidence):
    h = synthetic(monkeypatch, warning="synthetic upstream warning")
    parent = prepare(h, evidence)
    authority = transport._authority(parent)
    mesh, aliases = parent.mesh, parent.aliases
    assert mesh is h.kernel is authority.runtime.kernel
    assert aliases.mesh is mesh
    assert aliases.ecm_verts is mesh.vcell_verts is h.polygons
    assert aliases.ecm_verts_unique is mesh.vor_verts is h.vertices
    assert aliases.ecm_verts[0] is mesh.tri_verts is h.vertices
    assert mesh.synthetic_view.base is h.vertices
    assert mesh._cells_observer is authority.runtime.observer
    assert mesh._cells_rng.rng is authority.runtime.rng
    assert parent.state is authority.runtime.state
    assert authority.runtime.request is h.request
    assert transport._events(authority.runtime.observer.events) == transport._events(
        parent.state.events
    )
    record = transport.source_record(parent)
    record["live_graph"]["nodes"].clear()
    record = transport.source_record(parent)
    assert record["live_graph"]["nodes"] and parent.mesh is mesh
    assert record["invalidated_owners"] == list(core.INVALIDATED_OWNERS)
    assert len(record["invalidated_owners"]) == 11
    for key in (
        "executable_DEC_parent_admitted",
        "physical_geometry_admitted",
        "ordinary_continuation_admitted",
        "checkpoint_admitted",
        "cells_owner_available",
    ):
        assert record[key] is False
    assert record["native_initial_qualification"].startswith("19/22")
    assert record["stable_independent_geometry"].startswith("0/9")
    assert set(record["native_method_qualification"].values()) == {"unrun"}
    assert not core._preparing_runtime(mesh)
    assert (
        h.calls["synthetic_constructor"],
        h.calls["synthetic_pre_mesh"],
        h.calls["synthetic_core"],
        h.calls["synthetic_cut"],
    ) == (1, 1, 1, 0)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(parent)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(mesh)
    no_native(h)
    save(
        evidence,
        "verified",
        dict(
            record=record,
            runtime=authority.runtime,
            aliases=aliases,
            calls=h.calls,
            extra_replay=False,
        ),
    )


@pytest.mark.parametrize(
    "change",
    [
        "equal-array",
        "nested-equal-array",
        "view-base",
        "observer-owner",
        "rng-owner",
        "rng-state",
        "event-prefix",
        "equal-event-copy",
        "warnings",
        "equal-id-tuple",
        "callable-method",
        "source-producer",
    ],
)
def test_software_live_drift_refuses_without_reconstruction(change, monkeypatch, evidence):
    h = synthetic(monkeypatch, warning="synthetic upstream warning")
    parent = prepare(h, evidence)
    authority = transport._authority(parent)
    runtime, mesh = authority.runtime, parent.mesh
    if change == "equal-array":
        mesh.tri_verts = mesh.tri_verts.copy()
    elif change == "nested-equal-array":
        mesh.vcell_verts[0] = mesh.vcell_verts[0].copy()
    elif change == "view-base":
        mesh.synthetic_view = mesh.synthetic_view.copy().view()
    elif change == "observer-owner":
        mesh._cells_observer = core.initial._Observer(runtime.observer.ids)
    elif change == "rng-owner":
        mesh._cells_rng.rng = object()
    elif change == "rng-state":
        monkeypatch.setattr(
            core.initial, "_rng_stream", lambda rng: SimpleNamespace(identity="changed")
        )
    elif change == "event-prefix":
        runtime.observer.events[0] = replace(runtime.observer.events[0], depth=77)
    elif change == "equal-event-copy":
        runtime.observer.events[0] = replace(runtime.observer.events[0])
    elif change == "warnings":
        runtime.warning_records[0].message.args = ("changed upstream warning",)
    elif change == "equal-id-tuple":
        runtime.observer.ids = tuple(list(runtime.observer.ids))
    elif change == "callable-method":
        monkeypatch.setattr(
            transport._Runtime, "cut_mesh", lambda *args: pytest.fail("Changed method ran")
        )
    else:
        monkeypatch.setattr(transport, "_verify_sources", lambda: {"changed": "producer"})
    if change in {"equal-array", "nested-equal-array", "view-base"}:
        # These would pass a cache-only comparison; live graph identity matters.
        assert (
            core.caches.snapshot(core.initial._public_cache(mesh)).identity
            == parent.state.cache.identity
        )
    with pytest.raises(transport.NativeParentRejected) as caught:
        parent.cut_mesh(np.asarray([], dtype=int))
    assert caught.value.stage == "live_authority_drift"
    assert caught.value.runtime is runtime
    assert parent.last_attempt is None
    assert transport.source_record(parent)["status"] == "invalidated_source_drift"
    assert h.calls["synthetic_core"] == 1 and h.calls["synthetic_cut"] == 0
    no_native(h)
    save(
        evidence,
        "drift",
        dict(
            change=change,
            error=caught.value,
            runtime=runtime,
            record=transport.source_record(parent),
            calls=h.calls,
        ),
    )


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("via", ["handle", "mesh"])
def test_software_callable_keeps_self_arguments_returns_and_stale_aliases(
    empty, via, monkeypatch, evidence
):
    h = synthetic(monkeypatch)
    parent = prepare(h, evidence)
    aliases, state = parent.aliases, parent.state
    target = np.asarray([] if empty else [1, 0, 1], dtype=int)
    caller_object = parent if via == "handle" else parent.mesh
    returned = caller_object.cut_mesh(target)
    attempt = parent.last_attempt
    assert returned is h.returned and attempt.returned is returned
    assert h.cut_self is h.kernel and h.cut_targets is target is attempt.targets
    assert attempt.runtime.kernel is h.kernel and attempt.aliases is aliases
    assert attempt.finished and attempt.source_completed and attempt.source_error is None
    assert str(attempt.warning_records[0].message) == "synthetic cut warning"
    assert aliases.ecm_verts is h.polygons and aliases.ecm_verts is not h.kernel.vcell_verts
    assert aliases.ecm_verts_unique is h.vertices and h.vertices[0, 0] == 17.0
    assert parent.state is state and parent.state.cache.identity == state.cache.identity
    with pytest.raises(transport.NativeParentRejected) as caught:
        parent.cut_mesh(target)
    assert caught.value.stage == "live_authority_consumed"
    assert h.calls["synthetic_cut"] == 1
    no_native(h)
    save(
        evidence,
        "call",
        dict(attempt=attempt, record=transport.source_record(parent), calls=h.calls),
    )


@pytest.mark.parametrize("via", ["handle", "mesh"])
def test_software_native_style_failure_retains_primary_chain_and_mutation(
    via, monkeypatch, evidence
):
    h = synthetic(monkeypatch, cut_failure=True)
    parent = prepare(h, evidence)
    target = np.asarray([], dtype=int)
    caller_object = parent if via == "handle" else parent.mesh
    with pytest.raises(SyntheticSourceFailure) as caught:
        caller_object.cut_mesh(target)
    attempt = parent.last_attempt
    assert caught.value is attempt.source_error is h.errors["cut"]
    assert caught.value.__cause__ is h.errors["cut_cause"]
    assert attempt.runtime.kernel is h.kernel and attempt.targets is target
    assert attempt.finished and not attempt.source_completed and attempt.returned is None
    assert h.kernel.vor_verts[0, 0] == 17.0
    assert attempt.aliases.ecm_verts is h.polygons
    assert attempt.aliases.ecm_verts is not h.kernel.vcell_verts
    assert attempt.runtime.state is parent.state
    assert h.calls["synthetic_cut"] == 1
    no_native(h)
    save(evidence, "failed-call", dict(attempt=attempt, calls=h.calls))


@pytest.mark.parametrize("name", transport._METHODS[1:])
@pytest.mark.parametrize("outcome", ["success", "mutated", "failure"])
def test_software_raw_map_core_calls_guard_and_retain_attempt(name, outcome, monkeypatch, evidence):
    h = synthetic(monkeypatch, method_failure=name if outcome == "failure" else None)
    parent = prepare(h, evidence)
    mesh = parent.mesh
    kwargs = {"ignoreb": True} if name == "create_mappings" else {}
    count = len(h.calls["synthetic_methods"])
    if outcome == "mutated":
        mesh.tri_verts = mesh.tri_verts.copy()
        with pytest.raises(transport.NativeParentRejected) as caught:
            getattr(mesh, name)(**kwargs)
        assert caught.value.stage == "live_authority_drift"
        assert len(h.calls["synthetic_methods"]) == count
        assert parent.last_attempt is None
    else:
        if outcome == "failure":
            with pytest.raises(SyntheticSourceFailure) as caught:
                getattr(mesh, name)(**kwargs)
            assert caught.value is h.errors["method"]
            assert caught.value.__cause__ is h.errors["method_cause"]
        else:
            assert getattr(mesh, name)(**kwargs) is None
        call = h.calls["synthetic_methods"][-1]
        attempt = parent.last_attempt
        assert call["self"] is mesh and call["args"] == () and call["kwargs"] == kwargs
        assert attempt.runtime.kernel is mesh and attempt.method == name
        assert attempt.args == () and attempt.kwargs == kwargs and attempt.targets is None
        assert attempt.finished and attempt.source_completed is (outcome == "success")
        assert attempt.source_error is (h.errors["method"] if outcome == "failure" else None)
        assert transport._authority(parent).active_thread is None
        with pytest.raises(transport.NativeParentRejected) as caught:
            getattr(mesh, name)(**kwargs)
        assert caught.value.stage == "live_authority_consumed"
    no_native(h)
    save(evidence, "map-core-call", dict(attempt=parent.last_attempt, calls=h.calls))


def test_software_cut_inner_maps_use_same_dynamic_authority(monkeypatch, evidence):
    h = synthetic(monkeypatch, cut_chain=True)
    parent = prepare(h, evidence)
    mesh = parent.mesh
    first = len(h.calls["synthetic_methods"])
    returned = mesh.cut_mesh(np.asarray([], dtype=int))
    assert returned is h.returned
    calls = h.calls["synthetic_methods"][first:]
    assert [row["method"] for row in calls] == list(transport._METHODS[1:])
    assert all(row["self"] is mesh for row in calls)
    assert calls[1]["kwargs"] == {"ignoreb": True}
    assert parent.last_attempt.method == "cut_mesh" and parent.last_attempt.source_completed
    assert transport._authority(parent).active_thread is None
    assert h.calls["synthetic_core"] == 2  # Synthetic initial/inner calls, not independent cases.
    with pytest.raises(transport.NativeParentRejected) as caught:
        mesh.create_core_operators()
    assert caught.value.stage == "live_authority_consumed"
    no_native(h)
    save(evidence, "nested-source-call", dict(attempt=parent.last_attempt, calls=h.calls))


@pytest.mark.parametrize("name", transport._METHODS)
def test_software_copied_complete_object_state_cannot_mint_authority(name, monkeypatch, evidence):
    h = synthetic(monkeypatch)
    parent = prepare(h, evidence)
    authority = transport._authority(parent)
    original = parent.mesh
    clone = object.__new__(transport._Runtime)
    vars(clone).update(vars(original))
    runtime = replace(authority.runtime, kernel=clone)
    aliases = replace(authority.aliases, mesh=clone)
    graft = replace(authority, runtime=runtime, aliases=aliases)
    clone._cells_dec_source_authority = graft
    graft.graph_objects, graft.graph_record = transport._graph(runtime, aliases)
    # Even internally consistent copied cache, epochs, aliases and receipts
    # cannot replace the actual constructor object registered in this process.
    transport._check_runtime(runtime, aliases)
    assert (
        core.caches.snapshot(core.initial._public_cache(clone)).identity
        == parent.state.cache.identity
    )
    before = len(h.calls["synthetic_methods"])
    with pytest.raises(transport.NativeParentRejected) as caught:
        args = (np.asarray([], dtype=int),) if name == "cut_mesh" else ()
        getattr(clone, name)(*args)
    assert caught.value.stage == "live_authority_unavailable"
    assert len(h.calls["synthetic_methods"]) == before and h.calls["synthetic_cut"] == 0
    assert parent.mesh is original
    no_native(h)
    save(evidence, "copied-state-refused", dict(error=caught.value, graft=graft, calls=h.calls))


@pytest.mark.parametrize("name", ["create_mappings", "create_core_operators"])
def test_software_stale_thread_field_cannot_authorize_native_method(name, monkeypatch, evidence):
    h = synthetic(monkeypatch)
    parent = prepare(h, evidence)
    mesh = parent.mesh
    transport._authority(parent).active_thread = transport.get_ident()
    before = len(h.calls["synthetic_methods"])
    with pytest.raises(transport.NativeParentRejected) as caught:
        getattr(mesh, name)()
    assert caught.value.stage == "live_authority_drift"
    assert len(h.calls["synthetic_methods"]) == before and parent.last_attempt is None
    no_native(h)
    save(evidence, "thread-marker-refused", dict(error=caught.value, calls=h.calls))


def test_software_initial_capture_failure_never_enables_native_methods(monkeypatch, evidence):
    h = synthetic(monkeypatch)
    inject_capture(monkeypatch, h, "initial_snapshot")
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        prepare(h, evidence)
    error = caught.value
    mesh = error.partial["original_kernel"]
    assert error.live_runtime is None and error.trial is None
    assert error.capture_error is h.errors["capture"] and error.source_error is None
    assert not core._preparing_runtime(mesh)
    assert h.calls["synthetic_constructor"] == h.calls["synthetic_core"] == 0
    for method in transport._METHODS:
        with pytest.raises(transport.NativeParentRejected) as rejected:
            args = (np.asarray([], dtype=int),) if method == "cut_mesh" else ()
            getattr(mesh, method)(*args)
        assert rejected.value.stage == "live_authority_unavailable"
    no_native(h)


@pytest.mark.parametrize(
    "outcome,capture", [("failure", False), ("failure", True), ("success", True)]
)
def test_software_core_failure_never_mints_parent(outcome, capture, monkeypatch, evidence):
    h = synthetic(monkeypatch, outcome=outcome)
    if capture:
        inject_capture(monkeypatch, h, "final_snapshot")
    existing_handles = frozenset(transport._AUTHORITIES)
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        prepare(h, evidence)
    error = caught.value
    assert error.live_runtime is None
    assert error.partial["original_kernel"] is h.kernel
    assert error.partial["original_observer"] is h.kernel._cells_observer
    assert not core._preparing_runtime(h.kernel)
    assert error.parent_request is h.base and error.parent_state is h.parent
    assert frozenset(transport._AUTHORITIES) == existing_handles
    if capture:
        assert error.capture_error is h.errors["capture"]
        assert error.trial is None
        assert error.partial["original_kernel"] is h.kernel
        assert not error.partial["complete_state_available"]
    else:
        assert error.trial is not None and not error.trial.core_source_completed
        assert not error.partial["usable_live_handle_available"]
    if outcome == "failure":
        assert error.source_error is h.errors["source"]
        assert error.__cause__ is h.errors["source"]
        assert error.source_error.__cause__ is h.errors["source_cause"]
    else:
        assert error.source_error is None and error.__cause__ is error.capture_error
    for method in transport._METHODS:
        with pytest.raises(transport.NativeParentRejected) as rejected:
            arguments = (np.asarray([], dtype=int),) if method == "cut_mesh" else ()
            getattr(h.kernel, method)(*arguments)
        assert rejected.value.stage == "live_authority_unavailable"
    no_native(h)


def test_software_transport_seal_failure_retains_successful_core(monkeypatch, evidence):
    h = synthetic(monkeypatch)
    primary = SyntheticCaptureFailure("synthetic transport graph capture failed")

    def fail(*args):
        raise primary

    monkeypatch.setattr(transport, "_graph", fail)
    with pytest.raises(transport.NativeParentRejected) as caught:
        prepare(h, evidence)
    error = caught.value
    assert error.stage == "live_transport_capture" and error.__cause__ is primary
    assert error.runtime.kernel is h.kernel
    assert error.runtime.state.core_source_completed
    assert error.runtime.state.status == "source_core_operators_completed_unqualified"
    with pytest.raises(transport.NativeParentRejected) as incomplete:
        h.kernel.cut_mesh(np.asarray([], dtype=int))
    assert incomplete.value.stage == "live_authority_unavailable"
    assert h.calls["synthetic_core"] == 1 and h.calls["synthetic_cut"] == 0
    no_native(h)


@pytest.mark.parametrize("declarations", [None, {"executable_DEC_parent_admitted": True}])
def test_software_full_caller_requires_unavailable_owned_cells(declarations, monkeypatch, evidence):
    h = synthetic(monkeypatch)
    parent = prepare(h, evidence)
    with pytest.raises(transport.NativeParentRejected) as caught:
        transport.require_post_cut_parent(parent, declarations=declarations)
    error = caught.value
    assert error.stage == "post_cut_owner_authority_unavailable"
    assert error.runtime.kernel is h.kernel
    assert error.partial["supplied_declarations"] is declarations
    assert not error.partial["source"]["executable_DEC_parent_admitted"]
    assert error.partial["source"]["invalidated_owners"] == list(core.INVALIDATED_OWNERS)
    assert h.calls["synthetic_cut"] == 0
    no_native(h)
    save(evidence, "remaining-boundary", dict(error=error, partial=error.partial, calls=h.calls))
