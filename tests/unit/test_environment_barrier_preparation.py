"""Independent static coefficients, complete owners and resolved physical stages."""

import ast
import hashlib
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.core import environment_barrier_preparation as bridge
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models import surface_tissue as model
from cells.processes import betse_environment_transport as native
from validation.tissue import surface_dynamics_reference as physical
from validation.transport import environment_barrier_preparation_fixtures as fixtures
from validation.transport import environment_barrier_preparation_reference as reference


def evidence(name, report, arrays=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "environment-barriers"
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


@pytest.mark.parametrize("case", fixtures.CASES)
@pytest.mark.parametrize("permuted", (False, True))
def test_independent_coefficients_preserve_full_initial_tissue(case, permuted):
    raw = fixtures.request(case, permuted=permuted, padded=permuted)
    untouched = deepcopy(raw)
    prepared, expected = bridge.prepare(raw), reference.prepare(raw)
    source = parse_spec(raw["definition"]).to_dict()
    result = deepcopy(prepared.definition)
    for actual, target in zip(
        result["model"]["faces"], expected["definition"]["model"]["faces"], strict=True
    ):
        assert actual["id"] == target["id"]
        for species, value in target["diffusivity_m2_per_s"].items():
            np.testing.assert_allclose(
                actual["diffusivity_m2_per_s"][species], value, rtol=5e-14, atol=0
            )
    for group, target in expected["coefficients"].items():
        actual = prepared.provenance["coefficients"][group]
        assert actual.keys() == target.keys()
        for species, row in target.items():
            assert actual[species].keys() == row.keys()
            for owner, value in row.items():
                np.testing.assert_allclose(actual[species][owner], value, rtol=5e-14, atol=0)
    original_faces = {r["id"]: r for r in source["model"]["faces"]}
    for face in result["model"]["faces"]:
        face["diffusivity_m2_per_s"] = original_faces[face["id"]]["diffusivity_m2_per_s"]
    assert digest(result) == digest(source)
    before, _ = model.initial_values(parse_spec(source))
    after, _ = model.initial_values(parse_spec(prepared.definition))
    assert type(before) is type(after) is model.STATE_TYPE and len(after) == 12
    for a, b in zip(before, after, strict=True):
        assert a.dtype == b.dtype
        np.testing.assert_array_equal(a, b)
    assert raw == untouched
    assert bridge.replay(prepared.provenance) == prepared
    evidence(
        "coefficients-" + case + "-" + str(permuted),
        dict(
            inputs=raw,
            provenance=prepared.provenance,
            independent=expected,
            complete_initial_state_exact=True,
            scope="Static preparation; no trajectory claim",
        ),
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_prepared_complete_field_and_material_energy_rates_match_independent_model(case):
    raw = fixtures.request(case, padded=True)
    prepared, expected = bridge.prepare(raw), reference.prepare(raw)
    spec = parse_spec(prepared.definition)
    state, layout = model.initial_values(spec)
    table = control_values(spec, [0.0])
    control = type(table)(*(v[0] for v in table))
    rates = model.rhs(state, control, layout, layout.active, xp=np)
    bound = physical.bind(expected["definition"])
    target, potential, proof = physical.evaluate(bound, physical.initial(bound), 0.0)
    actual = physical.flatten(bound, rates._asdict())
    budgets = physical.flatten(
        bound,
        {
            name: np.full(shape, 3e-23 if name.endswith("_C") else 3e-12)
            for name, shape in bound["shapes"].items()
        },
    ) + 3e-10 * np.abs(target)
    ratio = float(np.max(np.abs(actual - target) / budgets, initial=0))
    field = model.field_values(state, control, layout, xp=np)
    n, outside = len(spec.model.cells), len(spec.model.extracellular)
    observed_potential = np.r_[
        field.potential_V[:n],
        field.potential_V[spec.execution.capacity : spec.execution.capacity + outside],
    ]
    report = dict(
        inputs=raw,
        definition=prepared.definition,
        max_error_over_budget=ratio,
        independent_field=proof,
        physical_energy_balance_pJ_s=float(field.energy_balance_pJ_s),
        scope="Complete initial physical stage on independently mapped coefficients; "
        "not an evolved history, native stencil comparison or biological case",
    )
    evidence(
        "physical-stage-" + case,
        report,
        dict(
            actual=actual,
            reference=target,
            potential=observed_potential,
            reference_potential=potential,
            budgets=budgets,
        ),
    )
    assert ratio <= 1
    np.testing.assert_allclose(observed_potential, potential, rtol=3e-10, atol=3e-13)
    assert field.converged and abs(field.energy_balance_pJ_s) < 1e-10
    assert model.check_values(state, spec)["max_energy_balance_error_pJ"] == 0


def test_duplicate_boundary_occurrences_keep_precedence_and_explicit_history():
    raw = fixtures.request()
    original = bridge.prepare(raw)
    name = raw["regions"]["boundary_membrane_sites"][0]
    raw["regions"]["neighbor_membrane_sites"].extend([name, name])
    repeated = bridge.prepare(raw)
    assert repeated.definition == original.definition
    assert repeated.provenance["coefficients"] == original.provenance["coefficients"]
    assert repeated.provenance["identity"] != original.provenance["identity"]
    assert repeated.provenance["target_site_occurrences"].count(name) == (
        original.provenance["target_site_occurrences"].count(name) + 2
    )


@pytest.mark.parametrize(
    "fault",
    (
        "schema_bool",
        "unknown_request",
        "unsupported_model",
        "open_perimeter",
        "volume",
        "area",
        "length",
        "valence",
        "boolean_valence",
        "site_ids",
        "face_ids",
        "face_endpoints",
        "boundary_alias",
        "unknown_region",
        "missing_species",
        "missing_modulator_site",
        "unknown_modulator_site",
        "negative_factor",
        "boolean_factor",
        "negative_modulator",
        "zero_sodium",
        "nonfinite",
        "coefficient_overflow",
        "reservoir",
    ),
)
def test_refuses_implicit_geometry_owners_invalid_coefficients_and_open_ports(fault):
    raw = fixtures.request()
    grid, tissue = raw["grid"], raw["definition"]["model"]
    if fault == "schema_bool":
        raw["schema_version"] = True
    elif fault == "unknown_request":
        raw["bath"] = "implicit"
    elif fault == "unsupported_model":
        tissue["id"] = "resolved_tissue@12"
    elif fault == "open_perimeter":
        raw["perimeter_policy"] = "open"
    elif fault == "volume":
        tissue["extracellular"][0]["volume_pL"] *= 2
    elif fault in ("area", "length"):
        tissue["faces"][0]["area_m2" if fault == "area" else "length_m"] *= 2
    elif fault == "valence":
        grid["valence"][0] += 1
    elif fault == "boolean_valence":
        grid["valence"][0] = True
    elif fault == "site_ids":
        grid["site_ids"][0] = "unknown-site"
    elif fault == "face_ids":
        grid["internal_face_ids"][0] = "unknown-face"
    elif fault == "face_endpoints":
        grid["internal_face_sites"][0] = [grid["site_ids"][0], grid["site_ids"][-1]]
    elif fault == "boundary_alias":
        grid["boundary_face_ids"][0] = tissue["cells"][0]["id"]
    elif fault == "unknown_region":
        raw["regions"]["cluster_sites"].append("unknown-site")
    elif fault == "missing_species":
        raw["free_diffusion_m2_s"].pop("Na")
    elif fault == "missing_modulator_site":
        raw["ion_modulators"]["Na"].pop(grid["site_ids"][0])
    elif fault == "unknown_modulator_site":
        raw["ion_modulators"]["Na"]["unknown-site"] = 1.0
    elif fault == "negative_factor":
        raw["tight_factor"] = -0.1
    elif fault == "boolean_factor":
        raw["adherens_factor"] = True
    elif fault == "negative_modulator":
        raw["ion_modulators"]["Na"][grid["site_ids"][0]] = -0.1
    elif fault == "zero_sodium":
        raw["free_diffusion_m2_s"]["Na"] = 0.0
    elif fault == "nonfinite":
        raw["relative_TJ"]["Na"] = float("nan")
    elif fault == "coefficient_overflow":
        raw["free_diffusion_m2_s"]["Na"] = 1e308
        raw["tight_factor"] = 1e308
    else:
        tissue["extracellular"][0]["reservoir"] = True
        tissue["closure"]["gauge_reference"] = None
    with pytest.raises(ConfigError):
        bridge.prepare(raw)


@pytest.mark.parametrize("fault", ("face_value", "initial_state", "grid", "request", "typed_value"))
def test_resealed_recipe_cannot_change_derived_values_or_request_without_recomputation(fault):
    prepared = bridge.prepare(fixtures.request())
    changed = deepcopy(prepared.provenance)
    if fault == "face_value":
        row = changed["coefficients"]["face_m2_s"]["Na"]
        row[next(iter(row))] *= 1.1
    elif fault == "initial_state":
        changed["initial_state_sha256"] = "0" * 64
    elif fault == "grid":
        changed["grid"]["delta_m"] *= 2
    elif fault == "request":
        changed["request"]["tight_factor"] *= 2
    else:
        changed["request"]["schema_version"] = True
    changed.pop("identity")
    changed["identity"] = digest(changed)
    with pytest.raises(ConfigError):
        bridge.replay(changed)


def test_reference_has_no_production_or_array_library_dependency():
    source = Path(reference.__file__).read_text()
    imports = [
        name
        for node in ast.walk(ast.parse(source))
        for name in (
            [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else [v.name for v in node.names]
            if isinstance(node, ast.Import)
            else []
        )
    ]
    assert all(name.split(".")[0] in sys.stdlib_module_names for name in imports)
    assert (
        hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest()
        == (bridge.SOURCE_CORRESPONDENCE["coefficient_kernel_sha256"])
    )
