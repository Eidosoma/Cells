"""Plain-data, manufactured inputs for static extracellular barrier preparation.

The finite 2-by-2 exterior and two passive cells have explicit charge anchors.
These are coefficient/ownership cases, not measured tissue parameters or a
native BETSE transport-stencil qualification.  No production imports occur.
"""

import math

CASES = (
    "overlap",
    "amplified",
    "zero_species",
    "no_regions",
    "unit_factors",
    "asymmetric_modulators",
    "zero_endpoint",
    "post_modulator_zero_na",
)
SITE_IDS = ("sw", "se", "nw", "ne")
SPECIES_IDS = ("Na", "K", "Cl")
FARADAY_C_MOL = 6.02214076e23 * 1.602176634e-19


def request(case="overlap", *, permuted=False, padded=False):
    """Return a fresh complete preparation request, with stable owner IDs.

    ``permuted`` changes definition owner order, species order, face order and
    orientation, and independent grid face/species order. Grid sites remain in
    the required C-order. ``padded`` changes only declared execution capacity.
    The optional 2.5-us execution interval is an initial coupled transient.
    """
    if case not in CASES:
        raise ValueError(f"Unknown barrier fixture {case!r}")
    delta, height = 1e-5, 1e-5
    volume = delta * delta * height * 1e15
    charge_per_fmol = FARADAY_C_MOL * 1e-15
    valence = {"Na": 1, "K": 1, "Cl": -1}
    outside_voltage = (0.0, 0.001, -0.0005, 0.0003)
    cell_voltage = (-0.04, -0.047)
    membranes = []
    cell_charge = [0.0, 0.0]
    outside_charge = [0.0] * 4
    for cell in range(2):
        owned_charges = []
        for site, site_id in enumerate(SITE_IDS):
            capacitance = (1.0 + 0.2 * cell) * (1.0 + 0.1 * site) * 1e-12
            charge = capacitance * (cell_voltage[cell] - outside_voltage[site])
            owned_charges.append(charge)
            outside_charge[site] -= charge
            membranes.append(
                {
                    "id": f"membrane_{cell}_{site_id}",
                    "inside": f"cell_{cell}",
                    "outside": site_id,
                    "area_m2": capacitance / 0.01,
                    "capacitance_F": capacitance,
                    "permeability_m_per_s": {"Na": 1e-9, "K": 2e-9, "Cl": 8e-10},
                    "law": "constant_field@1",
                }
            )
        cell_charge[cell] = math.fsum(owned_charges)

    def owner(identifier, owner_volume, concentration, charge, *, outside=False):
        amounts = dict(zip(SPECIES_IDS, (c * owner_volume for c in concentration), strict=True))
        result = {
            "id": identifier,
            "volume_pL": owner_volume,
            "initial_amount_fmol": amounts,
            "fixed_charge_equivalent_fmol": charge / charge_per_fmol
            - math.fsum(valence[s] * amounts[s] for s in SPECIES_IDS),
            "initial_charge_C": charge,
        }
        if outside:
            result.update(reservoir=False, boundary_potential_V=0.0)
        return result

    pairs = (("sw", "se"), ("nw", "ne"), ("sw", "nw"), ("se", "ne"))
    face_ids = tuple(f"face_{a}_{b}" for a, b in pairs)
    model = {
        "id": "resolved_tissue@1",
        "temperature_K": 310.0,
        "species": [{"id": s, "valence": valence[s]} for s in SPECIES_IDS],
        "cells": [
            owner("cell_0", 2.0, (12.0, 140.0, 10.0), cell_charge[0]),
            owner("cell_1", 3.0, (15.0, 130.0, 13.0), cell_charge[1]),
        ],
        "extracellular": [
            owner(site, volume, concentrations, charge, outside=True)
            for site, concentrations, charge in zip(
                SITE_IDS,
                (
                    (145.0, 4.0, 120.0),
                    (142.0, 4.5, 125.0),
                    (147.0, 5.0, 124.0),
                    (139.0, 4.2, 118.0),
                ),
                outside_charge,
                strict=True,
            )
        ],
        "membranes": membranes,
        "junctions": [],
        "faces": [
            {
                "id": face,
                "sender": a,
                "receiver": b,
                "area_m2": delta * height,
                "length_m": delta,
                "diffusivity_m2_per_s": {"Na": 7e-13, "K": 9e-13, "Cl": 8e-13},
                "law": "logmean_electrodiffusion@1",
            }
            for face, (a, b) in zip(face_ids, pairs, strict=True)
        ],
        "closure": {
            "law": "resolved_capacitor_components_current_continuity@1",
            "gauge_reference": "sw",
        },
    }
    dt = 1.25e-8
    padding = int(padded)
    definition = {
        "schema_version": 1,
        "model": model,
        "experiment": {
            "end_time": 200 * dt,
            "observation_times": [0.0, 100 * dt, 200 * dt],
            "membrane_controls": [
                {"membrane_id": m["id"], "schedule": [{"time": 0.0, "availability": 1.0}]}
                for m in membranes
            ],
            "junction_controls": [],
        },
        "execution": {
            "dt": dt,
            "capacity": 2 + padding,
            "extracellular_capacity": 4 + padding,
            "membrane_capacity": 8 + padding,
            "edge_capacity": padding,
            "face_capacity": 4 + padding,
            "backend": "cpu",
            "jit": True,
            "precision": "float64",
            "solver": "rk4",
            "field_solver": "capacitive_reduction_gauged_damped_newton@1",
            "max_steps": 256,
            "max_trace_bytes": 2**29,
            "material_balance_atol_fmol": {s: 2e-11 for s in SPECIES_IDS},
        },
    }
    boundary = (
        ("sw", "S"),
        ("sw", "W"),
        ("se", "S"),
        ("se", "E"),
        ("nw", "N"),
        ("nw", "W"),
        ("ne", "N"),
        ("ne", "E"),
    )
    result = {
        "schema_version": 1,
        "kind": "cells.environment_barrier_preparation_request@1",
        "definition": definition,
        "grid": {
            "site_ids": list(SITE_IDS),
            "species_ids": list(SPECIES_IDS),
            "valence": [valence[s] for s in SPECIES_IDS],
            "shape": [2, 2],
            "coordinates_m": [[0.0, 0.0], [delta, 0.0], [0.0, delta], [delta, delta]],
            "delta_m": delta,
            "height_m": height,
            "internal_face_ids": list(face_ids),
            "internal_face_sites": [list(pair) for pair in pairs],
            "boundary_face_ids": [f"sealed_{site}_{side}" for site, side in boundary],
            "boundary_face_sites": [site for site, _ in boundary],
            "boundary_face_sides": [side for _, side in boundary],
            "provenance": {
                "kind": "manufactured_uniform_grid@1",
                "purpose": "static barrier coefficients and ownership; not native PDE parity",
            },
        },
        "regions": {
            "cluster_sites": ["sw", "se", "se"],
            "boundary_membrane_sites": ["se", "nw", "nw"],
            "neighbor_membrane_sites": ["nw"],
            "boundary_cell_sites": ["se"],
        },
        "free_diffusion_m2_s": {"Na": 1e-12, "K": 2e-12, "Cl": 1.5e-12},
        "relative_TJ": {"Na": 1.0, "K": 0.7, "Cl": 0.4},
        "adherens_factor": 0.25,
        "tight_factor": 0.1,
        "ion_modulators": {s: dict.fromkeys(SITE_IDS, 1.0) for s in SPECIES_IDS},
        "perimeter_policy": "sealed",
    }
    if case == "amplified":
        result.update(adherens_factor=2.5, tight_factor=1.7)
        result["relative_TJ"] = {"Na": 1.2, "K": 1.4, "Cl": 2.0}
    elif case == "zero_species":
        result["free_diffusion_m2_s"]["Cl"] = 0.0
    elif case == "no_regions":
        result["regions"] = {name: [] for name in result["regions"]}
    elif case == "unit_factors":
        result.update(adherens_factor=1.0, tight_factor=1.0)
        result["relative_TJ"] = dict.fromkeys(SPECIES_IDS, 1.0)
    elif case == "asymmetric_modulators":
        result["ion_modulators"] = {
            "Na": dict(zip(SITE_IDS, (0.3, 3.0, 0.7, 1.2), strict=True)),
            "K": dict(zip(SITE_IDS, (1.4, 0.25, 1.0, 2.0), strict=True)),
            "Cl": dict(zip(SITE_IDS, (0.6, 1.7, 0.4, 0.9), strict=True)),
        }
    elif case == "zero_endpoint":
        result["ion_modulators"]["K"]["se"] = 0.0
        result["ion_modulators"]["Cl"]["nw"] = 0.0
    elif case == "post_modulator_zero_na":
        result["ion_modulators"]["Na"] = dict.fromkeys(SITE_IDS, 0.0)

    if permuted:
        model["species"] = [model["species"][i] for i in (2, 0, 1)]
        model["cells"].reverse()
        model["extracellular"] = [model["extracellular"][i] for i in (2, 0, 3, 1)]
        model["membranes"].reverse()
        model["faces"] = [model["faces"][i] for i in (2, 0, 3, 1)]
        for face in model["faces"]:
            face["sender"], face["receiver"] = face["receiver"], face["sender"]
        definition["experiment"]["membrane_controls"].reverse()
        grid = result["grid"]
        grid["species_ids"] = ["K", "Cl", "Na"]
        grid["valence"] = [valence[s] for s in grid["species_ids"]]
        grid["internal_face_ids"] = [face_ids[i] for i in (3, 1, 0, 2)]
        grid["internal_face_sites"] = [list(reversed(pairs[i])) for i in (3, 1, 0, 2)]
        for name in ("boundary_face_ids", "boundary_face_sites", "boundary_face_sides"):
            grid[name].reverse()
    return result


def definition(case="overlap", *, permuted=False, padded=False):
    """Convenience name for the complete request; the raw model is under definition."""
    return request(case, permuted=permuted, padded=padded)
