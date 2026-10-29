"""Small independent arithmetic/ownership tests; no transport integration."""

import ast
import math
import sys
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from validation.transport.environment_barrier_preparation_fixtures import (
    CASES,
    FARADAY_C_MOL,
    request,
)
from validation.transport.environment_barrier_preparation_reference import prepare


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("permuted", [False, True])
@pytest.mark.parametrize("padded", [False, True])
def test_complete_axes_and_only_face_diffusivity_changes(case, permuted, padded):
    raw = request(case, permuted=permuted, padded=padded)
    before = deepcopy(raw)
    result = prepare(raw)
    assert raw == before
    restored = deepcopy(result["definition"])
    old_faces = {row["id"]: row for row in raw["definition"]["model"]["faces"]}
    for row in restored["model"]["faces"]:
        row["diffusivity_m2_per_s"] = old_faces[row["id"]]["diffusivity_m2_per_s"]
    assert restored == raw["definition"]
    arrays = result["arrays"]
    assert arrays["species_ids"] == raw["grid"]["species_ids"]
    assert arrays["site_ids"] == raw["grid"]["site_ids"]
    assert arrays["internal_face_ids"] == raw["grid"]["internal_face_ids"]
    assert arrays["internal_face_sites"] == raw["grid"]["internal_face_sites"]
    for key, axis in (
        ("site_base_m2_s", arrays["site_ids"]),
        ("site_effective_m2_s", arrays["site_ids"]),
        ("face_m2_s", arrays["internal_face_ids"]),
    ):
        assert arrays[key] == [
            [result["coefficients"][key][species][owner] for owner in axis]
            for species in arrays["species_ids"]
        ]
    for array_key, model_key, owner_ids in (
        ("grid_to_definition_species_index", "species", arrays["species_ids"]),
        ("grid_to_definition_site_index", "extracellular", arrays["site_ids"]),
        ("grid_to_definition_face_index", "faces", arrays["internal_face_ids"]),
    ):
        model_rows = raw["definition"]["model"][model_key]
        assert [model_rows[index]["id"] for index in arrays[array_key]] == owner_ids


def test_hand_calculated_overwrite_values_and_harmonic_not_arithmetic_mean():
    result = prepare(request())
    assert result["coefficients"]["site_base_m2_s"] == {
        "Na": {"sw": 2.5e-13, "se": 1e-13, "nw": 1e-13, "ne": 1e-12},
        "K": {"sw": 5e-13, "se": 1.4e-13, "nw": 1.4e-13, "ne": 2e-12},
        "Cl": {"sw": 3.75e-13, "se": 6e-14, "nw": 6e-14, "ne": 1.5e-12},
    }
    assert result["arrays"]["sodium_weight"] == [0.25, 0.1, 0.1, 1.0]
    with localcontext() as context:
        context.prec = 80
        expected_na = float(Decimal("1e-12") / 7)
        expected_k = float(Decimal("7e-12") / 32)
    face = result["coefficients"]["face_m2_s"]
    assert face["Na"]["face_sw_se"] == expected_na
    assert face["K"]["face_sw_se"] == expected_k
    assert face["Na"]["face_sw_se"] != (2.5e-13 + 1e-13) / 2


def test_boundary_occurrences_retained_without_repeated_multiplication():
    raw = request()
    result = prepare(raw)
    assert result["arrays"]["boundary_target_site_ids"] == ["se", "nw", "nw", "nw", "se"]
    assert result["arrays"]["boundary_target_site_indices"] == [1, 2, 2, 2, 1]
    assert result["arrays"]["cluster_site_indices"] == [0, 1, 1]
    reduced = deepcopy(raw)
    reduced["regions"] = {
        "cluster_sites": ["sw", "se"],
        "boundary_membrane_sites": ["se", "nw"],
        "neighbor_membrane_sites": [],
        "boundary_cell_sites": [],
    }
    assert prepare(reduced)["coefficients"] == result["coefficients"]
    raw["adherens_factor"] = 9.0
    changed = prepare(raw)["coefficients"]["site_base_m2_s"]
    for sid, row in result["coefficients"]["site_base_m2_s"].items():
        assert changed[sid]["se"] == row["se"]
        assert changed[sid]["nw"] == row["nw"]
        assert changed[sid]["sw"] == float(Decimal(str(raw["free_diffusion_m2_s"][sid])) * 9)


@pytest.mark.parametrize("case", ["no_regions", "unit_factors"])
def test_uniform_free_diffusion_reduction(case):
    raw = request(case)
    result = prepare(raw)
    for sid, free in raw["free_diffusion_m2_s"].items():
        for key in ("site_base_m2_s", "site_effective_m2_s", "face_m2_s"):
            assert set(result["coefficients"][key][sid].values()) == {free}
    assert result["arrays"]["sodium_weight"] == [1.0] * 4


def test_amplification_is_not_clipped_to_free_diffusion():
    raw = request("amplified")
    result = prepare(raw)
    for sid, free in raw["free_diffusion_m2_s"].items():
        assert result["coefficients"]["site_base_m2_s"][sid]["sw"] == float(
            Decimal(str(free)) * Decimal("2.5")
        )
        assert result["coefficients"]["site_base_m2_s"][sid]["se"] > free
        assert result["coefficients"]["face_m2_s"][sid]["face_sw_se"] > free


def test_modulators_act_before_face_harmonic_mean():
    result = prepare(request("asymmetric_modulators"))
    base = result["coefficients"]["site_base_m2_s"]["Na"]
    effective = result["coefficients"]["site_effective_m2_s"]["Na"]
    assert base["sw"] == 2.5e-13 and base["se"] == 1e-13
    assert effective["sw"] == 7.5e-14 and effective["se"] == 3e-13
    assert result["coefficients"]["face_m2_s"]["Na"]["face_sw_se"] == 1.2e-13
    assert result["arrays"]["sodium_weight"] == [0.25, 0.1, 0.1, 1.0]


def test_zero_species_and_endpoint_barriers():
    zero_species = prepare(request("zero_species"))
    for key in ("site_base_m2_s", "site_effective_m2_s", "face_m2_s"):
        assert set(zero_species["coefficients"][key]["Cl"].values()) == {0.0}
    zero_endpoint = prepare(request("zero_endpoint"))["coefficients"]["face_m2_s"]
    assert zero_endpoint["K"]["face_sw_se"] == zero_endpoint["K"]["face_se_ne"] == 0.0
    assert zero_endpoint["K"]["face_sw_nw"] > 0.0
    assert zero_endpoint["K"]["face_nw_ne"] > 0.0
    assert zero_endpoint["Cl"]["face_sw_nw"] == zero_endpoint["Cl"]["face_nw_ne"] == 0.0
    assert zero_endpoint["Cl"]["face_sw_se"] > 0.0


def test_sodium_normalization_precedes_modulators_and_retains_native_refusal():
    result = prepare(request("post_modulator_zero_na"))
    assert set(result["coefficients"]["site_effective_m2_s"]["Na"].values()) == {0.0}
    assert set(result["coefficients"]["face_m2_s"]["Na"].values()) == {0.0}
    assert result["arrays"]["sodium_weight"] == [0.25, 0.1, 0.1, 1.0]
    raw = request()
    raw["free_diffusion_m2_s"]["Na"] = 0.0
    with pytest.raises(ValueError, match="sodium normalization"):
        prepare(raw)
    raw = request()
    raw["regions"]["boundary_cell_sites"] = raw["grid"]["site_ids"][:]
    raw["relative_TJ"]["Na"] = 0.0
    with pytest.raises(ValueError, match="sodium normalization"):
        prepare(raw)


@pytest.mark.parametrize("case", CASES)
def test_stable_id_maps_survive_independent_owner_face_and_species_permutations(case):
    ordinary = prepare(request(case))
    permuted = prepare(request(case, permuted=True, padded=True))
    assert ordinary["coefficients"] == permuted["coefficients"]
    assert ordinary["arrays"]["sodium_weight"] == permuted["arrays"]["sodium_weight"]
    assert (
        ordinary["arrays"]["grid_to_definition_site_index"]
        != permuted["arrays"]["grid_to_definition_site_index"]
    )
    assert (
        ordinary["arrays"]["grid_to_definition_face_index"]
        != permuted["arrays"]["grid_to_definition_face_index"]
    )
    assert (
        ordinary["arrays"]["grid_to_definition_species_index"]
        != permuted["arrays"]["grid_to_definition_species_index"]
    )


@pytest.mark.parametrize("missing", ["species", "site"])
def test_modulator_axes_require_explicit_complete_maps(missing):
    raw = request()
    if missing == "species":
        raw["ion_modulators"].pop("Cl")
    else:
        raw["ion_modulators"]["Cl"].pop("ne")
    with pytest.raises(ValueError, match="complete explicit owner map"):
        prepare(raw)


@pytest.mark.parametrize("target", ["free_diffusion_m2_s", "relative_TJ"])
def test_species_maps_require_all_declared_species(target):
    raw = request()
    raw[target].pop("K")
    with pytest.raises(ValueError, match="complete explicit owner map"):
        prepare(raw)


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf"), True])
def test_invalid_factors_and_modulators_are_rejected(value):
    raw = request()
    raw["adherens_factor"] = value
    with pytest.raises(ValueError):
        prepare(raw)
    raw = request()
    raw["ion_modulators"]["Na"]["sw"] = value
    with pytest.raises(ValueError):
        prepare(raw)


@pytest.mark.parametrize(
    "geometry", ["volume", "area", "length", "coordinates", "valence", "finite", "law", "gauge"]
)
def test_incompatible_physical_mapping_is_rejected(geometry):
    raw = request()
    model = raw["definition"]["model"]
    if geometry == "volume":
        model["extracellular"][0]["volume_pL"] *= 1.01
    elif geometry == "area":
        model["faces"][0]["area_m2"] *= 1.01
    elif geometry == "length":
        model["faces"][0]["length_m"] *= 1.01
    elif geometry == "coordinates":
        raw["grid"]["coordinates_m"][1][0] *= 1.01
    elif geometry == "valence":
        raw["grid"]["valence"][0] = 2
    elif geometry == "finite":
        model["extracellular"][0]["reservoir"] = True
    elif geometry == "law":
        model["faces"][0]["law"] = "bernoulli_fitted_environment_faces@1"
    elif geometry == "gauge":
        model["closure"]["gauge_reference"] = None
    with pytest.raises(ValueError):
        prepare(raw)


@pytest.mark.parametrize(
    "mapping",
    [
        "missing_edge",
        "duplicate_edge",
        "wrong_face_owner",
        "missing_perimeter",
        "duplicate_perimeter",
    ],
)
def test_grid_requires_every_physical_edge_and_perimeter_owner(mapping):
    raw = request()
    grid = raw["grid"]
    if mapping == "missing_edge":
        removed = grid["internal_face_ids"].pop()
        grid["internal_face_sites"].pop()
        raw["definition"]["model"]["faces"] = [
            row for row in raw["definition"]["model"]["faces"] if row["id"] != removed
        ]
    elif mapping == "duplicate_edge":
        grid["internal_face_sites"][1] = grid["internal_face_sites"][0][:]
    elif mapping == "wrong_face_owner":
        raw["definition"]["model"]["faces"][0]["receiver"] = "nw"
    elif mapping == "missing_perimeter":
        for key in ("boundary_face_ids", "boundary_face_sites", "boundary_face_sides"):
            grid[key].pop()
    else:
        grid["boundary_face_sites"][1] = grid["boundary_face_sites"][0]
        grid["boundary_face_sides"][1] = grid["boundary_face_sides"][0]
    with pytest.raises(ValueError):
        prepare(raw)


@pytest.mark.parametrize(
    "model_id", ["resolved_tissue@12", "resolved_water@1", "resolved_tissue_excision@1"]
)
def test_only_declared_ordinary_parent_supported(model_id):
    raw = request()
    raw["definition"]["model"]["id"] = model_id
    with pytest.raises(ValueError, match="ordinary resolved_tissue@1"):
        prepare(raw)


def test_fixture_charge_and_inventory_are_explicit_not_neutralized_by_preparation():
    raw = request()
    model = raw["definition"]["model"]
    owners = model["cells"] + model["extracellular"]
    assert abs(math.fsum(row["initial_charge_C"] for row in owners)) < 1e-27
    assert all(row["initial_charge_C"] != 0.0 for row in owners)
    valence = {row["id"]: row["valence"] for row in model["species"]}
    for owner in owners:
        ionic = math.fsum(valence[s] * n for s, n in owner["initial_amount_fmol"].items())
        represented_charge = FARADAY_C_MOL * 1e-15 * (ionic + owner["fixed_charge_equivalent_fmol"])
        assert abs(represented_charge - owner["initial_charge_C"]) < 1e-23
    prepared = prepare(raw)["definition"]
    assert prepared["model"]["cells"] == model["cells"]
    assert prepared["model"]["extracellular"] == model["extracellular"]
    assert prepared["model"]["membranes"] == model["membranes"]
    assert prepared["experiment"] == raw["definition"]["experiment"]


def test_reference_and_fixture_import_only_standard_library():
    # This assertion also works when these tests share a process with production
    # tests. The isolated worker separately records its loaded module closure.
    for filename in (
        "environment_barrier_preparation_reference.py",
        "environment_barrier_preparation_fixtures.py",
    ):
        tree = ast.parse(Path(__file__).with_name(filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    alias.name.split(".")[0] in sys.stdlib_module_names for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0
                assert node.module.split(".")[0] in sys.stdlib_module_names
