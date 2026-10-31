"""Prepared independent geometry/owner panel; no automatic qualification run."""

import hashlib
import json
import os
import traceback
from dataclasses import replace
from pathlib import Path

import pytest

from cells.processes import conservative_polygon_geometry as geometry
from validation.geometry import conservative_polygon_geometry_fixtures as fixtures
from validation.geometry import conservative_polygon_geometry_reference as reference


def save(name, value):
    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "conservative-polygon"
    root.mkdir(exist_ok=True)
    with (root / (name + ".json")).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def retain_generated_prelude(
    case, stage, *, native_request=None, request=None, state=None, error=None, inputs=None
):
    """Publish full typed upstream requests/trials before polygon admission."""
    import numpy as np

    from cells.processes import betse_environment_field as arrays
    from cells.processes import betse_initial_mesh_preparation as initial
    from cells.processes import betse_initial_mesh_preparation_cache as caches
    from cells.processes import stable_initial_mesh_preparation as upstream
    from validation.geometry import stable_initial_mesh_preparation_io as transport

    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "conservative-polygon"
    root.mkdir(exist_ok=True)
    path = root / (case + "-upstream-" + stage)
    columns = {}

    def record(prefix, cache):
        columns.update(
            {prefix + "__" + name: value for name, value in cache.numeric_columns().items()}
        )
        return dict(column_prefix=prefix, descriptor=cache.descriptor, identity=cache.identity)

    mesh_trial = state if type(state) is upstream.State else None
    value = dict(
        mode="generated_prelude_before_polygon_comparison",
        stage=stage,
        inputs=inputs,
        native_request=None
        if native_request is None
        else arrays.plain(initial.request_record(native_request)),
        native_request_identity=None if native_request is None else native_request.identity,
        request=None if request is None else arrays.plain(upstream.request_record(request)),
        request_identity=None if request is None else request.identity,
        native_request_cache=None
        if native_request is None
        else record("native_request", caches.snapshot(dict(native_request.constructor_kwargs))),
        state=None if mesh_trial is None else upstream.state_record(mesh_trial),
        state_identity=None if mesh_trial is None else mesh_trial.identity,
        constructed=None
        if mesh_trial is None
        else record("constructed", mesh_trial.constructed_cache),
        final=None if mesh_trial is None else record("final", mesh_trial.cache),
        events=[]
        if mesh_trial is None
        else [
            dict(
                sequence=e.sequence,
                kind=e.kind,
                method=e.method,
                depth=e.depth,
                payload=record(f"event{e.sequence}", e.payload),
            )
            for e in mesh_trial.events
        ],
        non_mesh_trial=state if mesh_trial is None else None,
        global_rng=initial.streams.native_stream_manifest(initial._rng_stream(np.random)),
        failure=None
        if error is None
        else dict(
            type=type(error).__name__,
            module=type(error).__module__,
            reason=str(error),
            traceback="".join(traceback.format_exception(error)),
        ),
    )
    transport.write(path, arrays.plain(value), columns)
    return dict(
        metadata=str(path.with_suffix(".json")),
        arrays=str(path.with_suffix(".npz")),
        state_identity=value["state_identity"],
        typed_mesh_trial=mesh_trial is not None,
    )


def bind(case):
    raw = fixtures.fixture(case)
    save(case + "-input", raw)
    request = geometry.from_polygons(raw, law_id=geometry.LAW_ID)
    save(
        case + "-request", dict(record=geometry.request_record(request), identity=request.identity)
    )
    try:
        binding = geometry.prepare(request)
    except Exception as error:
        save(
            case + "-failure",
            dict(
                type=type(error).__name__,
                reason=str(error),
                trial=getattr(error, "trial", None),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    save(case + "-actual", dict(geometry=binding.geometry, identity=binding.identity))
    return request, binding


def mathematical(request, label):
    reports = []
    for refinement in (1, 2):
        target = reference.evaluate(request.declaration, refinement=refinement)
        save(label + f"-reference-{refinement}", target)
        reports.append(target)
    return reports


@pytest.mark.parametrize("case", fixtures.POSITIVE_CASES)
def test_exact_geometry_shared_interfaces_and_owners(case):
    request, binding = bind(case)
    targets = mathematical(request, case)
    comparison = reference.compare(request.declaration, binding.geometry, *targets)
    save(case + "-comparison", comparison)
    assert comparison["exact_physical_owner_and_interface_correspondence"]
    assert comparison["integer_incidence_columns_sum_to_zero"]
    assert not comparison["trajectory_conservation_claimed"]
    geometry.validate_binding(request, binding)
    if case in ("merged-square", "quad-grid-merged", "quad-grid-merged-all", "concave-merged"):
        assert binding.geometry["geometry_checks"]["merge_internal_edges_removed"] > 0
    if case == "quad-grid-merged-all":
        assert binding.geometry["source_only_vertex_ids"] == ["v-1-1"]
        assert len(binding.geometry["cells"][0]["source_cell_ids"]) == 4


@pytest.mark.parametrize("case", fixtures.DOMAIN_CASES)
def test_unsupported_geometry_refuses_with_evidence(case):
    raw = fixtures.domain(case)
    save(case + "-input", raw)
    with pytest.raises(ValueError) as caught:
        request = geometry.from_polygons(raw, law_id=geometry.LAW_ID)
        geometry.prepare(request)
    error = caught.value
    save(
        case + "-refusal",
        dict(type=type(error).__name__, reason=str(error), trial=getattr(error, "trial", None)),
    )
    if case in ("area-underflow", "volume-overflow"):
        reports = []
        for refinement in (1, 2):
            target = reference.evaluate(raw, refinement=refinement)
            save(case + f"-reference-{refinement}", target)
            reports.append(target)
        assert all(not row["required_outputs_representable"] for row in reports)
    else:
        with pytest.raises((reference.ReferenceRejected, ValueError)) as independent:
            reference.evaluate(raw)
        save(
            case + "-independent-refusal",
            dict(type=type(independent.value).__name__, reason=str(independent.value)),
        )


@pytest.mark.parametrize("case", fixtures.OWNERSHIP_CASES)
def test_geometry_request_and_result_authority(case):
    request, binding = bind("two-triangles")
    if case == "wrong-law":
        with pytest.raises(ValueError):
            geometry.from_polygons(request.declaration, law_id="native_geometry_passive_tissue@1")
    elif case == "boolean-law":
        with pytest.raises(ValueError):
            geometry.from_polygons(request.declaration, law_id=True)
    elif case == "forged-generated-source":
        raw = request.declaration
        raw["source"] = dict(
            kind="owned_stable_initial_dual_mesh@1",
            request_identity="0" * 64,
            state_identity="0" * 64,
            cache_identity="0" * 64,
            bridge_bundle_sha256=geometry.MESH_BRIDGE_BUNDLE_SHA256,
            bridge_request={},
            bridge_state={},
            coordinate_policy="owned_vor_verts_and_vor_cells@1",
        )
        forged = geometry.Request(geometry._json(raw), (), "")
        forged = replace(forged, identity=geometry._digest(geometry.request_record(forged)))
        with pytest.raises(ValueError):
            geometry.validate_request(forged)
        with pytest.raises(ValueError):
            geometry.from_polygons(raw, law_id=geometry.LAW_ID)
    elif case == "changed-request-identity":
        with pytest.raises(ValueError):
            geometry.validate_request(replace(request, identity="0" * 64))
    elif case == "resealed-binding-owner":
        changed = fixtures.corrupt("balanced-wrong-owner", binding.geometry)
        forged = geometry.Binding(
            request.identity, geometry._json(changed), geometry._digest(changed)
        )
        with pytest.raises(ValueError):
            geometry.validate_binding(request, forged)
    elif case == "returned-copy-alias":
        changed = binding.geometry
        changed["membranes"][0]["bath_id"] = "unowned"
        assert binding.geometry["membranes"][0]["bath_id"] == "bath"
        geometry.validate_binding(request, binding)
    else:
        raise AssertionError(case)
    save(case + "-ownership", dict(case=case, authority_control_passed=True))


@pytest.mark.parametrize("case", fixtures.CORRUPTION_CASES)
def test_independent_geometry_checker_rejects_balanced_and_metric_defects(case):
    request, binding = bind("two-triangles")
    targets = mathematical(request, case)
    changed = fixtures.corrupt(case, binding.geometry)
    save(case + "-corrupt-actual", changed)
    if case == "balanced-wrong-owner":
        assert all(
            sum(row[i] for row in changed["membrane_incidence"]) == 0
            for i in range(len(changed["membranes"]))
        )
    with pytest.raises(AssertionError) as caught:
        reference.compare(request.declaration, changed, *targets)
    save(
        case + "-independent-rejection",
        dict(reason=str(caught.value), incidence_balance_alone_was_not_acceptance=True),
    )


@pytest.mark.parametrize("case", fixtures.GENERATED_CASES)
def test_owned_generated_polygons_and_explicit_physical_merges(case, tmp_path):
    captures = []

    def retain(stage, **values):
        captures.append(retain_generated_prelude(case, stage, **values))

    try:
        request, inputs = fixtures.generated(case, tmp_path, retain=retain)
    except BaseException as error:
        save(
            case + "-fixture-failure",
            dict(
                type=type(error).__name__,
                reason=str(error),
                traceback=traceback.format_exc(),
                upstream_captures=captures,
            ),
        )
        raise
    save(case + "-input", dict(request=geometry.request_record(request), inputs=inputs))
    save(
        case + "-request", dict(record=geometry.request_record(request), identity=request.identity)
    )
    try:
        binding = geometry.prepare(request)
    except BaseException as error:
        owned_request = request.upstream[0]
        retain(
            "polygon-preparation-replay-failure",
            native_request=owned_request.native_request,
            request=owned_request,
            state=getattr(error, "trial", None),
            error=error,
            inputs=inputs,
        )
        save(
            case + "-failure",
            dict(
                type=type(error).__name__,
                reason=str(error),
                trial={"upstream_capture": captures[-1]}
                if captures[-1]["typed_mesh_trial"]
                else getattr(error, "trial", None),
                traceback=traceback.format_exc(),
                upstream_captures=captures,
            ),
        )
        raise
    save(case + "-actual", dict(geometry=binding.geometry, identity=binding.identity))
    targets = mathematical(request, case)
    comparison = reference.compare(request.declaration, binding.geometry, *targets)
    save(case + "-comparison", comparison)
    assert request.declaration["source"]["kind"] == "owned_stable_initial_dual_mesh@1"
    assert not binding.geometry["B09_admission_inherited"]
    if case == "generated-merged-interface":
        assert any(len(row["source_cell_ids"]) == 2 for row in binding.geometry["cells"])


def test_original_B09_merged_physical_guard_is_preserved():
    from cells.processes import betse_geometry_initialization as original
    from validation.betse import betse_initial_mesh_preparation_fixtures as old_fixtures

    assert (
        hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()
        == "9035c4dba445292010821eb871970cbb3348fdfedd0d597459ccfe6adb1234de"
    )
    with pytest.raises(ValueError) as caught:
        old_fixtures.reused_B09("merged-square-aux")
    save(
        "B09-physical-refusal",
        dict(
            reason=str(caught.value),
            original_guard_unchanged=True,
            constructor_only_adapter_used=False,
        ),
    )
