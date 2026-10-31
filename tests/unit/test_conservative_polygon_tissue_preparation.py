"""Prepared full physical-owner admission and unit-conversion checks."""

import json
import os
import traceback
from dataclasses import replace
from pathlib import Path

import pytest

from cells.core import conservative_polygon_tissue_preparation as physical
from cells.processes import conservative_polygon_geometry as geometry
from validation.geometry import conservative_polygon_geometry_fixtures as fixtures
from validation.geometry import conservative_polygon_geometry_reference as reference


def save(name, value):
    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "conservative-polygon-tissue"
    root.mkdir(exist_ok=True)
    with (root / (name + ".json")).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def bound(case):
    raw = fixtures.fixture(case)
    save(case + "-geometry-input", raw)
    request = geometry.from_polygons(raw, law_id=geometry.LAW_ID)
    binding = geometry.prepare(request)
    save(
        case + "-geometry-actual",
        dict(
            request=geometry.request_record(request),
            identity=binding.identity,
            geometry=binding.geometry,
        ),
    )
    return request, binding


def admitted(case):
    request, binding = bound(case)
    raw = fixtures.physical(binding)
    save(case + "-physical-input", raw)
    try:
        prepared = physical.prepare(request, binding, raw)
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
    save(
        case + "-physical-actual",
        dict(
            definition=prepared.definition,
            provenance=prepared.provenance,
            identity=prepared.identity,
        ),
    )
    return request, binding, raw, prepared


@pytest.mark.parametrize("case", fixtures.PHYSICAL_CASES)
def test_existing_physical_admission_exact_owners_and_dimensioned_measures(case):
    request, binding, raw, prepared = admitted(case)
    targets = []
    for refinement in (1, 2):
        target = reference.evaluate(request.declaration, refinement=refinement)
        save(case + f"-geometry-reference-{refinement}", target)
        targets.append(target)
    geometry_comparison = reference.compare(request.declaration, binding.geometry, *targets)
    comparison = reference.compare_physical(binding.geometry, raw, prepared.definition, *targets)
    save(case + "-comparison", dict(geometry=geometry_comparison, physical=comparison))
    assert prepared.provenance["physical_model_prepared"]
    assert not prepared.provenance["inventories_rescaled"]
    assert not prepared.provenance["B09_admission_inherited"]
    assert not prepared.provenance["solver_trajectory_executed"]
    assert comparison["inventories_and_charge_anchors_preserved_by_exact_owner_id"]


@pytest.mark.parametrize("case", fixtures.PHYSICAL_DOMAIN_CASES)
def test_physical_owner_or_constitutive_refusal_does_not_prepare_a_model(case):
    request, binding = bound("two-triangles")
    raw = fixtures.physical_domain(case, binding)
    save(case + "-physical-input", raw)
    with pytest.raises(physical.PhysicalRejected) as caught:
        physical.prepare(request, binding, raw)
    save(case + "-physical-refusal", caught.value.trial)
    assert caught.value.trial["physical_model_prepared"] is False
    if case == "existing-closure-refusal":
        assert caught.value.trial["failure_type"] == "ConfigError"


@pytest.mark.parametrize("case", fixtures.PHYSICAL_OWNERSHIP_CASES)
def test_physical_preparation_cannot_change_inventory_or_geometry_by_resealing(case):
    request, binding, raw, prepared = admitted("two-triangles")
    definition, provenance = prepared.definition, prepared.provenance
    if case == "definition-area":
        definition["model"]["junctions"][0]["area_m2"] *= 2
    elif case == "definition-inventory":
        definition["model"]["cells"][0]["initial_amount_fmol"]["Na"] *= 2
    elif case == "provenance-owner":
        provenance["exact_owner_axes"]["cells"].reverse()
    elif case == "returned-copy-alias":
        definition["model"]["cells"][0]["id"] = "wrong-owner"
        assert prepared.definition["model"]["cells"][0]["id"] != "wrong-owner"
        physical.validate(request, binding, raw, prepared)
        save(case + "-ownership", dict(copy_alias_does_not_mutate_preparation=True))
        return
    else:
        raise AssertionError(case)
    forged = replace(
        prepared,
        definition_json=geometry._json(definition),
        provenance_json=geometry._json(provenance),
        identity=geometry._digest(dict(definition=definition, provenance=provenance)),
    )
    save(
        case + "-forged-preparation",
        dict(definition=definition, provenance=provenance, identity=forged.identity),
    )
    with pytest.raises(ValueError):
        physical.validate(request, binding, raw, forged)
    save(case + "-ownership", dict(resealed_physical_tamper_rejected=True))
