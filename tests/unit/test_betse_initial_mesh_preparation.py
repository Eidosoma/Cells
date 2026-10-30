"""Prepared initial-mesh source/ownership checks; no automatic mesh run."""

import json
import os
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from cells.processes import betse_environment_field as arrays
from cells.processes import betse_initial_mesh_preparation as mesh
from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams
from validation.betse import betse_initial_mesh_preparation_fixtures as fixtures
from validation.betse import betse_initial_mesh_preparation_native as native
from validation.betse import betse_initial_mesh_preparation_reference as reference
from validation.betse import betse_initial_mesh_preparation_wire as wire

CASES = (*fixtures.B09_CASES, *fixtures.CALLER_CASES)


def request(case, directory):
    return (
        fixtures.reused_B09(case)
        if case in fixtures.B09_CASES
        else fixtures.caller(case, directory)
    )


def save(label, value, columns=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "initial-mesh"
        root.mkdir(parents=True, exist_ok=True)
        if columns is not None:
            with (root / (label + ".npz")).open("xb") as handle:
                np.savez_compressed(handle, **columns)
                handle.flush()
                os.fsync(handle.fileno())
        with (root / (label + ".json")).open("x") as handle:
            json.dump(arrays.plain(value), handle, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())


def retain_actual(label, req, state, inputs):
    columns = {}

    def record(prefix, cache):
        columns.update(
            {prefix + "__" + name: value for name, value in cache.numeric_columns().items()}
        )
        return dict(column_prefix=prefix, descriptor=cache.descriptor, identity=cache.identity)

    value = dict(
        mode="actual_before_native_capture",
        inputs=inputs,
        request=arrays.plain(mesh.request_record(req)),
        state=mesh.state_record(state),
        request_cache=record("request", caches.snapshot(dict(req.constructor_kwargs))),
        constructed=record("constructed", state.constructed_cache),
        final=record("final", state.cache),
        events=[
            dict(
                sequence=e.sequence,
                kind=e.kind,
                method=e.method,
                depth=e.depth,
                payload=record(f"event{e.sequence}", e.payload),
            )
            for e in state.events
        ],
    )
    save(label + "-actual", value, columns)


def retain_native(label, proof):
    columns = {}

    def record(prefix, snapshot):
        columns.update({prefix + "__" + name: value for name, value in snapshot["columns"].items()})
        return dict(tree=snapshot["tree"], column_prefix=prefix)

    value = {
        key: item
        for key, item in proof.items()
        if key not in ("cache", "constructed_cache", "events")
    }
    value.update(
        constructed_cache=record("constructed", proof["constructed_cache"]),
        cache=record("final", proof["cache"]),
        events=[
            dict(
                sequence=e["sequence"],
                kind=e["kind"],
                method=e["method"],
                depth=e["depth"],
                payload=record(f"event{e['sequence']}", e["payload"]),
            )
            for e in proof["events"]
        ],
    )
    save(label + "-native", value, columns)


def native_proof(req, inputs, *, label=None):
    if req.origin == "owned_image_prelude":
        caller = native.caller_kwargs(
            inputs["seed_recipe"], inputs["seed_stream_before"], inputs["controls"]
        )
        kwargs, before = caller["kwargs"], caller["rng_before_constructor"]
        if label is not None:
            captured = wire.capture(kwargs)
            save(
                label + "-native-caller",
                {
                    "caller": {key: value for key, value in caller.items() if key != "kwargs"},
                    "kwargs": captured["tree"],
                },
                captured["columns"],
            )
        for key in ("seed_points", "center"):
            if isinstance(kwargs.get(key), np.ndarray):
                assert caches.layout(kwargs[key]) == caches.layout(req.constructor_kwargs[key])
    else:
        raw = inputs["input"]
        kwargs = dict(
            raw["mesh"],
            seed_points=None
            if raw["seed_points_m"] is None
            else np.asarray(raw["seed_points_m"], dtype=float),
        )
        before = inputs["rng_before"]
    return native.evaluate(kwargs, req.constructor_point_ids, before)


def compare_events(actual, expected, *, failed=False):
    assert len(actual) == len(expected)
    for event, proof in zip(actual, expected, strict=True):
        assert (event.sequence, event.kind, event.method, event.depth) == (
            proof["sequence"],
            proof["kind"],
            proof["method"],
            proof["depth"],
        )
        if failed and event.kind.endswith("failure"):
            # Preserve full raw reasons. Qhull run identifiers/tracebacks are
            # diagnostic text; source cache values and failure type are checked.
            left = caches.plain(event.payload)
            right = wire.plain(proof["payload"]["tree"], proof["payload"]["columns"])
            left.pop("reason", None)
            right.pop("reason", None)
            assert records.record(left) == records.record(right)
        else:
            wire.compare_owned(
                event.payload.descriptor, event.payload.numeric_columns(), proof["payload"]
            )


def reference_fraction(actual, expected, atol):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    assert a.shape == b.shape
    fraction = float(np.max(abs(a - b) / (np.asarray(atol) + 6e-12 * abs(b)), initial=0))
    assert fraction <= 1, fraction
    return fraction


def retained_reference(label, events, *, refinement=1):
    try:
        report = reference.evaluate(events, refinement=refinement)
    except reference.ReferenceFailure as error:
        save(label + f"-reference-{refinement}-failure", error.trial)
        raise
    save(label + f"-reference-{refinement}", report)
    return report


@pytest.mark.parametrize("case", CASES)
def test_complete_owned_constructor_and_pre_mesh_native_trace(tmp_path, case):
    req, inputs = request(case, tmp_path)
    try:
        state = mesh.prepare(req)
    except mesh.InitialMeshRejected as error:
        if error.trial is not None:
            retain_actual(case, req, error.trial, inputs)
        raise
    retain_actual(case, req, state, inputs)
    proof = native_proof(req, inputs, label=case)
    retain_native(case, proof)
    assert proof["status"] == "source_completed" and proof["failure"] is None
    assert state.failure_stage is state.failure_type is state.failure_message is None
    assert proof["constructor_completed"] and proof["pre_mesh_completed"]
    wire.compare_owned(
        state.constructed_cache.descriptor,
        state.constructed_cache.numeric_columns(),
        proof["constructed_cache"],
    )
    wire.compare_owned(state.cache.descriptor, state.cache.numeric_columns(), proof["cache"])
    compare_events(state.events, proof["events"])
    assert list(state.retained_point_ids) == list(proof["retained_point_ids"])
    assert (
        streams.native_stream_manifest(state.stream_after_constructor)["state"]
        == proof["rng_after_constructor"]
    )
    assert streams.native_stream_manifest(state.stream_after)["state"] == proof["rng_after"]
    assert (
        proof["original_global_rng_unchanged"]
        and not proof["operators_created"]
        and not proof["image_clip_executed"]
    )
    events = [
        dict(sequence=e.sequence, kind=e.kind, method=e.method, payload=caches.plain(e.payload))
        for e in state.events
    ]
    first = retained_reference(case, events)
    second = retained_reference(case, events, refinement=2)
    save(case + "-precomparison", dict(reference=first, refined_reference=second))
    by_sequence = {e.sequence: caches.plain(e.payload) for e in state.events}
    maximum = resolution = 0.0
    for a, b in zip(first["primitives"], second["primitives"], strict=True):
        assert a["sequence"] == b["sequence"] and a["method"] == b["method"]
        method = a["method"]
        atol = (
            1e-26
            if method == "area"
            else [1e-27, 1e-26, 1e-27, 1e-27]
            if method == "quad_circumc"
            else 1e-27
        )
        maximum = max(
            maximum,
            reference_fraction(by_sequence[a["sequence"]]["result"], a["expected_result"], atol),
        )
        resolution = max(
            resolution, reference_fraction(a["expected_result"], b["expected_result"], atol)
        )
    assert len(first["nearest"]) == len(second["nearest"])
    for table, refined_table in zip(first["nearest"], second["nearest"], strict=True):
        assert table["sequence"] == refined_table["sequence"]
        payload = by_sequence[table["sequence"]]
        actual = np.asarray(payload["result"][0]).ravel().tolist()
        expected = [v for row in table["expected"] for v in row["ranked_distances"]]
        refined = [v for row in refined_table["expected"] for v in row["ranked_distances"]]
        assert len(actual) == len(expected) == len(refined)
        assert [r["exact_tie_candidate_indices"] for r in table["expected"]] == [
            r["exact_tie_candidate_indices"] for r in refined_table["expected"]
        ]
        for a, b, c in zip(actual, expected, refined, strict=True):
            if b == "infinity":
                assert np.isinf(a) and c == "infinity"
            else:
                # Integer-pair trees are native index space, not metres.
                source_event = next(e for e in state.events if e.sequence == table["sequence"])
                descriptor = source_event.payload.descriptor
                assert descriptor["kind"] == "dict"
                data = np.asarray(payload["data"])
                floor = 2e-14 if data.dtype.kind in "iu" else 1e-27
                maximum = max(maximum, reference_fraction(a, b, floor))
                resolution = max(resolution, reference_fraction(b, c, floor))
    assert resolution <= 0.1
    assert not first["topology_qualified"] and not proof["topology_qualified"]
    if req.origin == "reused_fixed_B09":
        final = caches.plain(state.cache)
        for key in (
            "tri_verts",
            "tri_cells",
            "tri_edges",
            "tri_cents",
            "tri_ccents",
            "tri_sa",
            "tri_sa_o",
            "vor_verts",
            "vor_cells",
            "vor_edges",
            "vor_sa",
            "vor_cents",
            "vcell_verts",
        ):
            assert records.record(final[key]) == records.record(inputs["mesh"][key]), key
    save(
        case,
        dict(
            mode="complete_source_initial_mesh",
            reference=first,
            refined_reference=second,
            maximum_error_fraction=maximum,
            maximum_reference_resolution_fraction=resolution,
            B09_coverage_reused=req.origin == "reused_fixed_B09",
            new_B09_coverage=False,
            topology_qualified=False,
            image_clip_executed=False,
            operators_created=False,
        ),
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_raw_native_mesh_failure_retains_prefix_and_occurrence_ledger(tmp_path, case):
    req, inputs = request(case, tmp_path)
    rejection = None
    try:
        trial = mesh.prepare(req)
    except mesh.InitialMeshRejected as error:
        rejection, trial = error, error.trial
    assert trial is not None
    retain_actual(case, req, trial, inputs)
    proof = native_proof(req, inputs, label=case)
    retain_native(case, proof)
    # An unexpected completion must retain both actual and native evidence.
    assert rejection is not None, "Expected source refusal; unexpected completion retained"
    assert proof["status"] == "source_failed" and proof["failure"]
    assert trial.status == "retained_source_failure"
    assert trial.failure_type == proof["failure"]["type"]
    assert trial.failure_stage == proof["stage"]
    assert trial.failure_message
    wire.compare_owned(trial.cache.descriptor, trial.cache.numeric_columns(), proof["cache"])
    compare_events(trial.events, proof["events"], failed=True)
    assert list(trial.retained_point_ids) == list(proof["retained_point_ids"])
    assert streams.native_stream_manifest(trial.stream_after)["state"] == proof["rng_after"]


@pytest.mark.parametrize("target", ("points", "radius", "stream", "point_ids"))
def test_resealed_constructor_request_tampering_is_refused(tmp_path, target):
    req, _ = fixtures.caller("caller-square-disordered", tmp_path)
    if target in ("points", "radius"):
        kwargs = dict(req.constructor_kwargs)
        if target == "points":
            kwargs["seed_points"] = mesh._own_layout(kwargs["seed_points"] + 1e-7)
        else:
            kwargs["cell_radius"] *= 1.01
        req = replace(req, constructor_kwargs=MappingProxyType(kwargs))
    elif target == "stream":
        req = replace(req, stream_before=streams.native_stream(123))
    else:
        req = replace(req, constructor_point_ids=tuple(reversed(req.constructor_point_ids)))
    req = replace(req, identity=records._digest(mesh.request_record(req)))
    with pytest.raises(ValueError):
        mesh.validate_request(req)


def test_caches_own_all_ragged_members_without_object_pointer_bytes(tmp_path):
    req, _ = fixtures.caller("caller-square-zero", tmp_path)
    state = mesh.prepare(req)
    for cache in (state.constructed_cache, state.cache, *(e.payload for e in state.events)):
        caches.validate(cache)
        for value in cache.numeric_columns().values():
            assert not value.dtype.hasobject
            with pytest.raises(ValueError):
                value.setflags(write=True)
    assert state.status == "source_completed_unqualified"


def test_unrecognized_source_provenance_is_not_a_mesh_authority(tmp_path):
    req, _ = fixtures.caller("caller-square-zero", tmp_path)
    with pytest.raises(ValueError):
        mesh.validate_request(replace(req, origin="manufactured_relabel_of_native_lattice"))


def test_initial_stage_does_not_build_operators_or_clip_image(tmp_path):
    req, _ = fixtures.caller("caller-square-zero", tmp_path)
    state = mesh.prepare(req)
    fields = caches.plain(state.cache)
    assert fields["image_mask"] is None
    assert not any(name.startswith("delta_") for name in fields)
    assert not any(
        e.method in ("clip_to_curve", "create_core_operators", "refine_mesh") for e in state.events
    )


def test_source_deletions_preserve_distinct_duplicate_occurrence_identity(tmp_path):
    req, _ = fixtures.caller("caller-square-zero", tmp_path)
    state = mesh.prepare(req)
    assert len(req.source_occurrence_ids) == 20 and len(set(req.source_occurrence_ids)) == 20
    current = req.constructor_point_ids
    for event in state.events:
        if event.kind == "source_row_deletion":
            payload = caches.plain(event.payload)
            assert tuple(payload["point_ids_before"]) == current
            indices = payload["indices"]
            current = tuple(name for i, name in enumerate(current) if i not in indices)
            assert tuple(payload["point_ids_after"]) == current
    assert current == state.retained_point_ids


def test_restored_source_layout_matches_fresh_native_caller(tmp_path):
    req, inputs = fixtures.caller("caller-square-disordered", tmp_path)
    proof = native.caller_kwargs(
        inputs["seed_recipe"], inputs["seed_stream_before"], inputs["controls"]
    )
    captured = wire.capture(proof["kwargs"])
    save("source-layout-caller", dict(kwargs=captured["tree"]), captured["columns"])
    assert caches.layout(req.constructor_kwargs["seed_points"]) == caches.layout(
        proof["kwargs"]["seed_points"]
    )
    np.testing.assert_array_equal(
        req.constructor_kwargs["seed_points"], proof["kwargs"]["seed_points"]
    )


def test_single_constructor_continues_cached_stream_and_pre_mesh_does_not_draw(tmp_path):
    req, inputs = fixtures.caller("caller-single-square-cache", tmp_path)
    state = mesh.prepare(req)
    proof = native_proof(req, inputs, label="cached-stream-continuation")
    assert (
        streams.native_stream_manifest(state.stream_after_constructor)["state"]
        == proof["rng_after_constructor"]
    )
    assert state.stream_after.identity == state.stream_after_constructor.identity
    assert streams.native_stream_manifest(state.stream_after)["state"][3:] == [1, -0.25]
