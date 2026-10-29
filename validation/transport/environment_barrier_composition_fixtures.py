"""Manufactured complete owners on a sealed 2x2 exterior grid.

Starting from the full catalog fixtures, remove the membrane-free fifth exterior
site and declare new uniform volumes/faces. Concentrations and capacitor charges
are retained, with fixed charge recalculated explicitly. This is a new synthetic
geometry, not a continuation or additional biological case.
"""

from copy import deepcopy

from validation.tissue import calcium_energy_water_hcn_extra_fixtures as water
from validation.tissue import calcium_energy_water_repair_hcn_extra_fixtures as repair
from validation.tissue import hcn_extra_catalog_fixtures as catalog
from validation.transport import environment_barrier_preparation_fixtures as grid_fixture

FAMILIES = ("ionic", "calcium", "energy", "water", "repair")
CASES = ("overlap", "asymmetric_modulators", "zero_endpoint")


def request(family="repair", case="overlap", *, permuted=False, padded=False):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    raw = (
        water.definition("release", padded=padded)
        if family == "water"
        else repair.definition("preinjured", parent="release", padded=padded)
        if family == "repair"
        else catalog.definition(family, padded=padded)
    )
    model = raw["model"]
    ion = model if family == "ionic" else model["ionic"]
    source = grid_fixture.request(case)
    sites = [f"outside_{i}" for i in range(4)]
    mapping = dict(zip(source["grid"]["site_ids"], sites, strict=True))
    volume = source["grid"]["delta_m"] ** 2 * source["grid"]["height_m"] * 1e15
    z = {s["id"]: s["valence"] for s in ion["species"]}
    ion["extracellular"] = [row for row in ion["extracellular"] if row["id"] in sites]
    # The original fixture gauges the membrane-free fifth site. This new
    # geometry explicitly gauges its first retained site; charge is unchanged.
    ion["closure"]["gauge_reference"] = sites[0]
    for row in ion["extracellular"]:
        ratio = volume / row["volume_pL"]
        row["initial_amount_fmol"] = {s: n * ratio for s, n in row["initial_amount_fmol"].items()}
        row["volume_pL"] = volume
        row["fixed_charge_equivalent_fmol"] = row["initial_charge_C"] / (96485.33212e-15) - sum(
            z[s] * n for s, n in row["initial_amount_fmol"].items()
        )
    faces = deepcopy(source["definition"]["model"]["faces"])
    for row in faces:
        row["sender"], row["receiver"] = mapping[row["sender"]], mapping[row["receiver"]]
        row["diffusivity_m2_per_s"]["Ca"] = 1e-12
    ion["faces"] = faces
    if "water_compartments" in model:
        model["water_compartments"] = [
            row for row in model["water_compartments"] if row["compartment_id"] != "outside_4"
        ]
        for row in model["water_compartments"]:
            if row["compartment_id"] in sites:
                row.update(
                    reference_volume_pL=volume,
                    minimum_volume_pL=0.5 * volume,
                    maximum_volume_pL=1.5 * volume,
                )
    raw["execution"].update(extracellular_capacity=4 + int(padded), face_capacity=4 + int(padded))
    grid = source["grid"]
    grid["site_ids"] = sites
    for key in ("internal_face_sites",):
        grid[key] = [[mapping[s] for s in pair] for pair in grid[key]]
    grid["boundary_face_sites"] = [mapping[s] for s in grid["boundary_face_sites"]]
    grid["species_ids"] = list(z)
    grid["valence"] = list(z.values())
    grid["provenance"] = dict(
        kind="manufactured_full_catalog_uniform_grid@1",
        purpose="static complete-owner preparation and stages; no biology",
    )
    for key, values in source["regions"].items():
        source["regions"][key] = [mapping[s] for s in values]
    for species, values in source["ion_modulators"].items():
        source["ion_modulators"][species] = {mapping[s]: value for s, value in values.items()}
    source["free_diffusion_m2_s"]["Ca"] = 1.2e-12
    source["relative_TJ"]["Ca"] = 0.6
    source["ion_modulators"]["Ca"] = dict(zip(sites, (0.9, 1.3, 0.4, 1.7), strict=True))
    source.update(kind="cells.composed_environment_barrier_preparation_request@1", definition=raw)
    if permuted:
        for key in ("species", "cells", "extracellular", "membranes", "channels", "faces"):
            ion[key].reverse()
        for face in ion["faces"]:
            face["sender"], face["receiver"] = face["receiver"], face["sender"]
        grid["species_ids"].reverse()
        grid["valence"].reverse()
    return source


def independent_coefficients(request):
    """Raw coefficient-only projection; no production binder or helper calls."""
    from validation.transport import environment_barrier_preparation_reference as oracle

    projected = deepcopy(request)
    parent = projected["definition"]["model"]
    leaf = parent if parent["id"] == "resolved_tissue@12" else parent["ionic"]
    projected["definition"]["model"] = deepcopy(leaf)
    projected["definition"]["model"]["id"] = "resolved_tissue@1"
    projected["kind"] = oracle.REQUEST_KIND
    expected = oracle.prepare(projected)
    result = deepcopy(request["definition"])
    target = (
        result["model"]
        if result["model"]["id"] == "resolved_tissue@12"
        else result["model"]["ionic"]
    )
    target["faces"] = expected["definition"]["model"]["faces"]
    return result, expected["coefficients"]
