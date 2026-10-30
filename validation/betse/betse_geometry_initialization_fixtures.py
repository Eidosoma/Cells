"""Declarations over frozen B09 records; material is explicitly manufactured."""

import json
import os
from copy import deepcopy
from pathlib import Path

ROOT = Path(
    os.environ.get("CELLS_B09_ROOT", "/mnt/workspaces/Cells/betse-geometry-development-20261029-03")
)
CASES = (
    "native-single-preset-seed17",
    "native-single-preset-seed23",
    "irregular-centroid-aux",
    "irregular-circumcenter-aux",
    "translated-scaled-circumcenter",
)


def fixture(case=CASES[0]):
    if case not in CASES:
        raise ValueError("Require a frozen B09 case in the initial adapter panel")
    record = json.loads((ROOT / "native-source" / (case + ".json")).read_text())
    generated = record["input"]["seed_points_m"] is None
    recipe = dict(
        kind="cells.betse_geometry_initialization_recipe@1",
        classification="native_generated_ring_and_centre"
        if generated
        else "manufactured_seed_cloud",
        provenance="B09 generated initial geometry; not full make_world or biological calibration",
        native_input=deepcopy(record["input"]),
    )
    material = dict(
        F_C_mol=96485.0,
        sharpness_cell=0.5,
        ions=[
            dict(
                id=name,
                valence=z,
                initial_cell_mol_m3=15.0,
                initial_environment_mol_m3=20.0,
                free_diffusion_m2_s=diffusion,
            )
            for name, z, diffusion in (("Na", 1.0, 1e-9), ("Cl", -1.0, 1.2e-9))
        ],
        constants=dict(
            q_C=1.602e-19,
            kb_J_K=1.3806e-23,
            NAv_per_mol=6.022e23,
            relative_permittivity=80.0,
            vacuum_permittivity_F_m=8.85419e-12,
            configured_temperature_K=298.15,
            true_cell_size_m=1e-5,
            magnetic_permeability_H_m=1.25664e-6,
        ),
    )
    return dict(recipe=recipe, material=material)


def readout(definition):
    raw = definition
    n, m = (
        len(raw["current_definition"]["geometry"]["cell_ids"]),
        len(raw["current_definition"]["geometry"]["membrane_ids"]),
    )
    world = raw["world"]
    delta = (world["xmax_m"] - world["xmin_m"]) / world["grid_size"]
    nx, ny = (
        int((world["xmax_m"] - world["xmin_m"]) / delta),
        int((world["ymax_m"] - world["ymin_m"]) / delta),
    )
    e = nx * ny
    current = dict(
        cell_mol_m3=[[15.0] * n for _ in range(2)],
        membrane_flux_mol_m2_s=[[(j - 3) * (i + 1) * 1e-12 for j in range(m)] for i in range(2)],
        junction_flux_mol_m2_s=[[(4 - j) * (i + 2) * 1e-12 for j in range(m)] for i in range(2)],
        extra_charge_C_m3=[(i % 3 - 1) * 0.001 for i in range(n)],
        extra_current_A_m2=[0.0] * m,
    )
    packet = dict(
        old_voltage_V=[-0.03] * m,
        boundary_V=dict.fromkeys(("R", "L", "T", "B"), 0.0),
        environment_mol_m3=[[20.0] * e for _ in range(2)],
        environment_flux_x=[[(k % nx - 1) * (i + 1) * 1e-10 for k in range(e)] for i in range(2)],
        environment_flux_y=[[(k // nx - 1) * (i + 2) * 1e-10 for k in range(e)] for i in range(2)],
        extra_environment_current_xy=[[(k % 3 - 1) * 1e-6, (k % 5 - 2) * 1e-6] for k in range(e)],
        extra_environment_charge_C_m3=[(k % 5 - 2) * 0.01 for k in range(e)],
    )
    return dict(definition=definition, frames=[dict(current=current, environment=packet)])
