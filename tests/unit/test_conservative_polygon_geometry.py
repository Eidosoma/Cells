"""Prepared independent geometry/owner panel; no automatic qualification run."""

import json
import os
import traceback
from dataclasses import replace
from pathlib import Path

import pytest

from cells.processes import conservative_polygon_geometry as geometry
from validation.geometry import conservative_polygon_geometry_fixtures as fixtures
from validation.geometry import conservative_polygon_geometry_reference as reference

# Two irregular generated meshes, exported once (b10a99e) as declared polygons.
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GENERATED = json.loads((FIXTURES / "conservative_polygon_generated.json").read_text())


def save(name, value):
    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "conservative-polygon"
    root.mkdir(exist_ok=True)
    with (root / (name + ".json")).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def bind(case, raw=None):
    raw = fixtures.fixture(case) if raw is None else raw
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
            bridge_bundle_sha256="0" * 64,
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


@pytest.mark.parametrize("case", sorted(GENERATED["cases"]))
def test_exported_generated_polygons_and_explicit_physical_merges(case):
    exported = GENERATED["cases"][case]
    request, binding = bind(case, exported["raw"])
    targets = mathematical(request, case)
    comparison = reference.compare(request.declaration, binding.geometry, *targets)
    save(case + "-comparison", comparison)
    assert comparison["exact_physical_owner_and_interface_correspondence"]
    assert comparison["integer_incidence_columns_sum_to_zero"]
    geometry.validate_binding(request, binding)
    actual, expected = binding.geometry, exported["expected"]
    # Same exact measures as the original generated-source binding at export.
    assert [len(actual[key]) for key in ("cells", "membranes", "contacts")] == [
        expected[key] for key in ("cells", "membranes", "contacts")
    ]
    for key in (
        "source_edges",
        "physical_edges",
        "merge_internal_edges_removed",
        "source_area_exact",
        "merged_area_exact",
    ):
        assert actual["geometry_checks"][key] == expected[key], key
    assert actual["source_only_vertex_ids"] == expected["source_only_vertex_ids"]
    assert not actual["B09_admission_inherited"]
    if case == "generated-merged-interface":
        assert any(len(row["source_cell_ids"]) == 2 for row in actual["cells"])
