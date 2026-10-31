"""Synthetic caller issuance controls; no original constructor/lattice/RNG runs."""

import hashlib
import os
import pickle
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_caller_lattice as caller
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_CALLER_LATTICE_EVIDENCE", str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def harness(monkeypatch, *, outcome="success"):
    calls = dict(auth=0, constructor=0, lattice=0, draws=0, native=[])
    errors = {}
    real_runtime = caller._Runtime
    stream_before = SimpleNamespace(identity="synthetic-before")
    stream_mid = SimpleNamespace(identity="synthetic-middle")
    stream_after = SimpleNamespace(identity="synthetic-after")
    raw = dict(
        points=np.asarray([[0.0, 0.0], [1.0, 0.0]], order="F"),
        bbox=np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]]),
        all_points=np.asarray(
            [[0.0, 0.0], [1.0, 0.0], [0.0, 0.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]]
        ),
        expanded=np.asarray([[-1.0, -1.0], [2.0, -1.0], [2.0, 1.0], [-1.0, 1.0]]),
        centre=np.asarray([0.5, 0.0]),
        bounds=np.asarray([-1.0, 2.0, -1.0, 1.0]),
        ux=np.asarray([[0.25, 0.75]]),
        uy=np.asarray([[0.125, 0.625]]),
        dx=np.asarray([[0.0, 0.0]]),
        dy=np.asarray([[0.0, 0.0]]),
    )
    values = caller.core.initial.image_stage.lattice.Values(
        *[
            None if v is None else caller.core.initial.image_stage.arrays.frozen(v)
            for v in (
                raw["points"],
                None,
                None,
                raw["ux"],
                raw["uy"],
                raw["dx"],
                raw["dy"],
                raw["points"],
                raw["bbox"],
                raw["all_points"],
                raw["expanded"],
                raw["centre"],
                raw["bounds"],
            )
        ]
    )
    binding = SimpleNamespace(
        definition={"lattice_type": "SQUARE", "synthetic_only": True},
        parameters=SimpleNamespace(
            expanded_width_m=4.0,
            expanded_height_m=4.0,
            drawing_gap_m=1e-6,
            diameter_m=2.0,
            nx=2,
            ny=1,
        ),
    )
    seed = SimpleNamespace(
        values=values,
        stream_before=stream_before,
        stream_after=stream_after,
        occurrence_ids=tuple("synthetic-point-" + str(i) for i in range(6)),
        draw_order=(("x", (1, 2), 2), ("y", (1, 2), 2)),
    )
    record = dict(synthetic_request="caller-software-only")
    parent = SimpleNamespace(initial_request=SimpleNamespace(upstream=(binding, seed, None)))
    request = caller.Request(parent, caller._digest(record))

    def forbidden(*args, **kwargs):
        calls["native"].append("forbidden-native-entry")
        raise AssertionError("An original source or cache decoder ran in a synthetic control")

    class Parameters:
        def __init__(self, recipe):
            objects["parameters"] = self
            self.world_len, self.cell_radius, self.cell_lattice_disorder = 4.0, 1.0, 0.0
            if outcome == "parameter-failure":
                fail_source()
            self.cell_lattice_type = caller.source.CellLatticeType.SQUARE
            self.wsx, self.wsy, self.ac, self.d_cell, self.nx, self.ny = 4.0, 4.0, 1e-6, 2.0, 2, 1

        initialize_source_stores = forbidden

    class Rng:
        def set_state(self, state):
            self.state, self.stream = state, stream_before

        def rand(self, *shape):
            calls["draws"] += 1
            value = raw["ux"] if calls["draws"] == 1 else raw["uy"]
            self.stream = stream_mid if calls["draws"] == 1 else stream_after
            return value

    class Runtime:
        def __init__(self, p):
            calls["constructor"] += 1
            objects["caller"] = self
            if outcome == "constructor-failure":
                fail_source()

        _make_cell_lattice = real_runtime._make_cell_lattice
        __reduce_ex__ = real_runtime.__reduce_ex__
        make_voronoi = real_runtime.make_voronoi
        cell_index = real_runtime.cell_index

    def fail_source():
        try:
            raise SyntheticSourceCause("original synthetic cause")
        except SyntheticSourceCause as cause:
            error = SyntheticSourceFailure("original synthetic failure")
            errors["source"], errors["source_cause"] = error, cause
            raise error from cause

    def make_body(tape):
        def body(self, p):
            calls["lattice"] += 1
            x_2d = np.asarray([[0.0, 1.0]])
            y_2d = np.asarray([[0.0, 0.0]])
            tape.rand(1, 2)
            if outcome == "lattice-failure":
                self.partial_native_buffer = raw["points"]
                fail_source()
            tape.rand(1, 2)
            x_rnd, y_rnd = raw["dx"], raw["dy"]
            xypts, bbox = raw["points"], raw["bbox"]
            self.clust_xy, self.bbox, self.centre = (
                raw["all_points"],
                raw["expanded"],
                raw["centre"],
            )
            self.xmin, self.xmax, self.ymin, self.ymax = -1.0, 2.0, -1.0, 1.0
            self.xyaxis = [self.xmin, self.xmax, self.ymin, self.ymax]
            assert x_rnd is raw["dx"] and y_rnd is raw["dy"] and xypts is raw["points"]
            assert bbox is raw["bbox"] and x_2d.shape == y_2d.shape

        return body

    def authenticate(value):
        assert value is request
        calls["auth"] += 1
        return binding, seed

    objects = {}
    monkeypatch.setattr(caller, "_validate_request", authenticate)
    monkeypatch.setattr(caller, "request_record", lambda value: record)
    monkeypatch.setattr(caller, "_Parameters", Parameters)
    monkeypatch.setattr(caller, "_Runtime", Runtime)
    monkeypatch.setattr(caller, "_body", make_body)
    monkeypatch.setattr(caller.np.random, "RandomState", lambda value: Rng())
    monkeypatch.setattr(caller.core.initial, "_rng_stream", lambda rng: rng.stream)
    monkeypatch.setattr(
        caller.core.initial.streams,
        "native_stream_manifest",
        lambda stream: dict(state=["MT19937", [0], 0, 0, 0.0]),
    )
    monkeypatch.setattr(caller.core.caches, "plain", forbidden)
    for module, name in (
        (caller.core.initial.image_stage.lattice, "generate"),
        (caller.core.initial.image_stage.lattice, "validate_state"),
        (caller.core.initial.image_stage, "prepare"),
        (caller.core, "prepare"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    return SimpleNamespace(
        request=request,
        raw=raw,
        seed=seed,
        calls=calls,
        objects=objects,
        errors=errors,
        stream_after=stream_after,
    )


def execute(h, evidence):
    save(evidence, "input", h.request)
    try:
        owner = caller.prepare(h.request)
    except caller.CallerRejected as error:
        save(
            evidence,
            "failed",
            dict(
                error=error,
                trial=error.trial,
                partial=error.partial,
                source_error=error.source_error,
                capture_error=error.capture_error,
                calls=h.calls,
            ),
        )
        raise
    save(evidence, "result", dict(trial=owner.trial, calls=h.calls))
    return owner


def test_software_literal_source_binding(evidence):
    pins = caller._verify_sources()
    assert (
        caller.source.SITES["Cells._make_cell_lattice"]
        == "681709c00231ea0ba2fc9e4abb45d4dbe4ae9ea4350e912e8224447d872da50b"
    )
    save(evidence, "literal-source", pins)


@pytest.mark.parametrize("value", [None, {}, {"live_cells": True}, SimpleNamespace()])
def test_software_inspection_or_absent_owner_refuses_before_replay(value, monkeypatch, evidence):
    attempted = []

    def forbidden(*a, **k):
        attempted.append(True)
        raise AssertionError("Early refusal reached numerical replay")

    monkeypatch.setattr(caller.core.initial.image_stage.lattice, "validate_state", forbidden)
    with pytest.raises(caller.CallerRejected) as error:
        caller.from_core_request(value, law_id=caller.LAW_ID)
    assert error.value.stage == "upstream_request_owner" and attempted == []
    save(evidence, "refusal", dict(error=error.value, attempted=attempted))


def test_software_actual_synthetic_object_aliases_and_no_hydration(monkeypatch, evidence):
    h = harness(monkeypatch)
    owner = execute(h, evidence)
    cells = owner.cells
    assert cells is h.objects["caller"]
    assert cells.clust_xy is h.raw["all_points"] and cells.bbox is h.raw["expanded"]
    assert cells.centre is h.raw["centre"] and cells.centre is not h.seed.values.centre_m
    assert cells.clust_xy is not h.seed.values.all_seed_points_m
    assert owner.trial.status == "source_lattice_completed_unqualified"
    assert h.calls["auth"] == 1 and h.calls["constructor"] == 1 and h.calls["draws"] == 2
    assert h.calls["native"] == []
    assert len(caller.INVALIDATED_OWNERS) == 11
    assert not caller.trial_record(owner.trial)["physical_geometry_admitted"]
    with pytest.raises(TypeError, match="serialized"):
        pickle.dumps(owner)
    with pytest.raises(TypeError, match="serialized"):
        pickle.dumps(cells)
    with pytest.raises(caller.CallerRejected) as error:
        cells._make_cell_lattice(caller._authority(owner)["parameters"])
    assert error.value.stage == "source_call_unavailable"


@pytest.mark.parametrize(
    "change",
    [
        "array",
        "equal-array",
        "view-base",
        "parameters",
        "RNG",
        "RNG-owner",
        "caller-owner",
        "draw",
        "event",
        "method",
        "constructor-code",
        "producer",
    ],
)
def test_software_stale_source_owner_refuses_without_replay(change, monkeypatch, evidence):
    h = harness(monkeypatch)
    owner = execute(h, evidence)
    cells = owner.cells
    authority = caller._authority(owner)
    if change == "array":
        cells.clust_xy[0, 0] = 99.0
    elif change == "equal-array":
        cells.clust_xy = cells.clust_xy.copy()
    elif change == "view-base":
        cells.clust_xy = cells.clust_xy.copy().view()
    elif change == "parameters":
        authority["parameters"].nx = 9
    elif change == "RNG":
        authority["tape"].rng.stream = SimpleNamespace(identity="changed")
    elif change == "RNG-owner":
        old = authority["tape"].rng
        new = type(old)()
        new.set_state(old.state)
        new.stream = old.stream
        authority["tape"].rng = new
    elif change == "caller-owner":
        new = object.__new__(type(cells))
        new.__dict__ = cells.__dict__
        authority["caller"] = new
    elif change == "draw":
        authority["tape"].draws[0]["values"][0, 0] = 0.5
    elif change == "event":
        authority["tape"].events[0]["kind"] = "altered"
    elif change == "method":
        body = cells._cells_original_lattice
        body.__code__ = body.__code__.replace(co_name="altered_body")
    elif change == "constructor-code":
        method = type(cells).__init__
        method.__code__ = method.__code__.replace(co_name="altered_constructor")
    else:
        monkeypatch.setattr(caller, "_verify_sources", lambda: {"changed": "source"})
    with pytest.raises(caller.CallerRejected) as error:
        _ = owner.cells
    assert error.value.stage == "caller_authority_drift"
    assert h.calls["auth"] == h.calls["constructor"] == h.calls["lattice"] == 1
    assert h.calls["native"] == []
    save(evidence, "stale", dict(error=error.value, calls=h.calls))


@pytest.mark.parametrize("outcome", ["constructor-failure", "lattice-failure"])
def test_software_source_failure_retains_original_chain_without_owner(
    outcome, monkeypatch, evidence
):
    h = harness(monkeypatch, outcome=outcome)
    existing = frozenset(caller._ISSUED)
    with pytest.raises(caller.CallerRejected) as error:
        execute(h, evidence)
    value = error.value
    assert value.source_error is h.errors["source"]
    assert value.__cause__ is value.source_error
    assert value.source_error.__cause__ is h.errors["source_cause"]
    assert value.partial["caller"] is h.objects["caller"]
    assert not value.partial["usable_live_owner_available"]
    assert frozenset(caller._ISSUED) == existing
    assert h.calls["native"] == []


@pytest.mark.parametrize("point", ["final-cache", "identity", "issuance-graph"])
def test_software_final_sealing_failure_keeps_raw_source(monkeypatch, point, evidence):
    h = harness(monkeypatch)
    original = caller.core.caches.snapshot
    failed = SyntheticCaptureFailure("injected final caller capture failure")
    if point == "final-cache":

        def snapshot(value):
            if "clust_xy" in value and caller.sys._getframe(1).f_code.co_name == "prepare":
                raise failed
            return original(value)

        monkeypatch.setattr(caller.core.caches, "snapshot", snapshot)
    elif point == "identity":
        monkeypatch.setattr(caller, "_digest", lambda value: (_ for _ in ()).throw(failed))
    else:
        monkeypatch.setattr(caller, "_graph", lambda *a: (_ for _ in ()).throw(failed))
    with pytest.raises(caller.CallerRejected) as error:
        execute(h, evidence)
    value = error.value
    assert value.capture_error is failed and value.source_error is None
    assert value.__cause__ is failed
    assert value.partial["caller"] is h.objects["caller"]
    assert not value.partial["usable_live_owner_available"]
    assert h.calls["native"] == []


def test_software_partial_parameter_stores_keep_original_instance(monkeypatch, evidence):
    h = harness(monkeypatch, outcome="parameter-failure")
    with pytest.raises(caller.CallerRejected) as caught:
        execute(h, evidence)
    error = caught.value
    assert error.source_error is h.errors["source"]
    assert error.__cause__ is error.source_error
    assert error.partial["parameters"] is h.objects["parameters"]
    assert error.partial["parameters"].world_len == 4.0
    assert error.partial["caller"] is None and error.trial is None
    assert h.calls["constructor"] == h.calls["draws"] == 0 and h.calls["native"] == []


def test_software_secondary_capture_failure_retains_primary_source(monkeypatch, evidence):
    h = harness(monkeypatch, outcome="lattice-failure")
    failed = SyntheticCaptureFailure("secondary caller identity failure")
    monkeypatch.setattr(caller, "_digest", lambda value: (_ for _ in ()).throw(failed))
    existing = frozenset(caller._ISSUED)
    with pytest.raises(caller.CallerRejected) as caught:
        execute(h, evidence)
    error = caught.value
    assert error.source_error is h.errors["source"] and error.capture_error is failed
    assert error.__cause__ is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["source_cause"]
    assert error.trial is None and error.partial["caller"] is h.objects["caller"]
    assert frozenset(caller._ISSUED) == existing and h.calls["native"] == []


def test_software_missing_image_owner_and_shared_RNG_authority_refuses(monkeypatch, evidence):
    h = harness(monkeypatch)
    owner = execute(h, evidence)
    for image in (None, h.seed.values, {"live_mask": True}):
        with pytest.raises(caller.CallerRejected) as error:
            caller.require_voronoi_continuation(
                owner, image_owner=image, mesh_owner={"same_epoch": True}
            )
        assert error.value.stage == "live_image_mask_unavailable"
        assert error.value.partial["separate_mesh_RNG_epoch_equality_is_not_shared_RNG_identity"]
    with pytest.raises(caller.CallerRejected):
        owner.cells.cell_index(caller._authority(owner)["parameters"])
    assert h.calls["draws"] == 2 and h.calls["native"] == []


def test_software_forged_owner_cannot_use_inspection_state(evidence):
    forged = object.__new__(caller.CallerOwner)
    with pytest.raises(caller.CallerRejected) as error:
        _ = forged.cells
    assert error.value.stage == "caller_authority_unavailable"
    save(evidence, "forged-refusal", error.value)
