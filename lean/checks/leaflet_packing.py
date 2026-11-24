"""Replay a fixed POPC footprint across temperature and compare two leaflet NMR records."""

import json
from pathlib import Path

import jax
import numpy as np

from cells.models.assembly_lineages_v2 import geometry, runner
from tests.unit.test_assembly_lineages_v2_lumen import osmotic_world, spec_of

DATA = Path(__file__).with_name("data") / "leaflet_packing.json"


def leaflet_fractions(inner_radius, outer_radius, inner_lipid_fraction):
    """Compare a spherical area fraction with the experimentally inferred lipid fraction."""
    inner_area_fraction = inner_radius**2 / (inner_radius**2 + outer_radius**2)
    outer_to_inner_footprint = (outer_radius / inner_radius) ** 2 * (
        inner_lipid_fraction / (1 - inner_lipid_fraction)
    )
    return {
        "inner_fraction_equal_footprint": inner_area_fraction,
        "inner_fraction_from_NMR": inner_lipid_fraction,
        "outer_to_inner_area_per_head": outer_to_inner_footprint,
    }


def compiled_area(temperature_C, area_per_lipid_A2, doi):
    """Run a closed 64-lipid synthetic vesicle using the specified molecular area."""
    count, quantum_m2 = 64, 1e-21
    area_m2 = area_per_lipid_A2 * 1e-20
    quanta = round(area_m2 / quantum_m2)
    raw = osmotic_world(L_pool=0, L_mem=count, S_pool=0, S_lumen=0, I_lumen=0, floor=count * quanta)
    raw["units"]["temperature_K"] = temperature_C + 273.15
    raw["geometry"]["area_quantum_m2"] = quantum_m2
    raw["geometry"]["area_per_leaflet"]["L"] = {
        "quanta": quanta,
        "provenance": "measured",
        "sourced_m2": area_m2,
        "source": doi,
    }
    spec = spec_of(raw, event_limit=4, row_every=1)
    run = runner.run(spec).check()
    footprint = run.rows["membrane_footprint_quanta"]
    assert run.closure["holds"] and not np.any(run.rows["channel_fired"])
    np.testing.assert_array_equal(footprint, count * quanta)
    areas = geometry.area_m2(spec.model.world, footprint) * 1e18
    np.testing.assert_allclose(areas, count * area_per_lipid_A2 * 0.01 / 2, rtol=2e-15, atol=0)
    return float(areas[-1])


def main():
    jax.config.update("jax_enable_x64", True)
    data = json.loads(DATA.read_text())
    first, second = data["finer1971_egg_pc@1"], data["huang1978_egg_pc@1"]
    finer = leaflet_fractions(
        first["outer_radius_A"] - first["bilayer_thickness_A"],
        first["outer_radius_A"],
        first["protected_headgroup_fraction"],
    )
    huang = leaflet_fractions(
        second["inner_headgroup_radius_A"],
        second["outer_headgroup_radius_A"],
        1 / (1 + second["nmr_outer_to_inner"]),
    )
    # Controls use the same physical identity for unequal radii and for equal radii.
    for ri, ro, expected in [(1, 2, 0.2), (2, 2, 0.5)]:
        check = leaflet_fractions(ri, ro, expected)
        assert check["inner_fraction_equal_footprint"] == expected
        assert check["outer_to_inner_area_per_head"] == 1
    # Table 2 rounds both headgroup areas to whole square angstroms.
    areas = second["inferred_area_per_head_A2"]
    assert (areas["outer"] - 0.5) / (areas["inner"] + 0.5) <= huang["outer_to_inner_area_per_head"]
    assert huang["outer_to_inner_area_per_head"] <= (areas["outer"] + 0.5) / (areas["inner"] - 0.5)
    study = data["kucerka2011_popc_temperature@1"]
    cold, warm = study["temperature_C"]
    cold_area, warm_area = study["area_per_lipid_A2"]
    fixed_cold = compiled_area(cold, cold_area, study["doi"])
    fixed_warm = compiled_area(warm, cold_area, study["doi"])
    calibrated_warm = compiled_area(warm, warm_area, study["doi"])
    assert fixed_warm == fixed_cold < calibrated_warm
    print(
        json.dumps(
            {
                "egg_pc_finer": finer,
                "egg_pc_huang": huang,
                "compiled_64_lipid_area_nm2": {
                    "cold": fixed_cold,
                    "warm_fixed_cold_input": fixed_warm,
                    "warm_with_measured_input": calibrated_warm,
                },
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
