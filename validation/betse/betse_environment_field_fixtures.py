"""Bounded stable manufactured fields; no native or production execution."""

from copy import deepcopy

from validation.betse.betse_normal_current_fixtures import fixture as current_fixture

CASES = (
    "standard",
    "rectangular",
    "offset",
    "duplicate",
    "permuted",
    "multivalent",
    "zero_flux",
    "uniform_current",
    "edge_field",
    "zero_sigma",
    "two_by_two",
    "five_by_five",
)


def fixture(case="standard", *, is_ecm=True):
    if case not in CASES or type(is_ecm) is not bool:
        raise ValueError("Require an explicit manufactured environment branch/case")
    original = current_fixture("multivalent" if case == "multivalent" else "standard")
    definition = deepcopy(original["definition"])
    geometry = definition["geometry"]
    # Declared metre-scale manufactured geometry keeps fixed field budgets
    # meaningful. These are not native Voronoi worlds or biological cells.
    geometry["membrane_area_m2"] = [value * 1e10 for value in geometry["membrane_area_m2"]]
    geometry["cell_area_m2"] = [
        sum(
            geometry["membrane_area_m2"][j]
            for j, owner in enumerate(geometry["owner"])
            if owner == i
        )
        for i in range(len(geometry["cell_ids"]))
    ]
    if case != "multivalent":
        definition["ions"] = dict(ids=["Na", "Cl"], valence=[1.0, -1.0])
    s, m, n = (
        len(definition["ions"]["ids"]),
        len(geometry["membrane_ids"]),
        len(geometry["cell_ids"]),
    )
    nx = 2 if case == "two_by_two" else 5 if case == "five_by_five" else 3
    ny = 4 if case == "rectangular" else nx
    delta = 2.0 if case == "offset" else 1.0
    xmin, ymin = (-2.0, 1.0) if case == "offset" else (0.0, 0.0)
    world = dict(
        xmin_m=xmin, xmax_m=xmin + nx * delta, ymin_m=ymin, ymax_m=ymin + ny * delta, grid_size=nx
    )
    sites = [
        [xmin + (j + 0.5) * delta, ymin + (i + 0.5) * delta] for i in range(ny) for j in range(nx)
    ]
    e = len(sites)
    assignment = (
        [0] * m if case == "duplicate" else [value % e for value in (0, 1, 4, 4, 5, 8, 6, 7, 8)]
    )
    mids = [[sites[k][0] + 0.03 * delta, sites[k][1] - 0.04 * delta] for k in assignment]
    centres = [[sites[k][0] - 0.07 * delta, sites[k][1] + 0.06 * delta] for k in (0, e // 2, e - 1)]
    initial_cell, initial_environment = [], []
    for i in range(s):
        multiplier = 2 if case == "multivalent" and i == 1 else 1
        initial_cell.append([multiplier * (13.0 + j) for j in range(n)])
        initial_environment.append([multiplier * (20.0 + k % 7) for k in range(e if is_ecm else m)])
    raw = dict(
        kind="cells.betse_environment_field_inputs@1",
        provenance="Explicit stable manufactured centres/midpoints/measures, not a Voronoi seed",
        is_ecm=is_ecm,
        current_definition=definition,
        world=world,
        geometry=dict(
            cell_centres_m=centres, membrane_midpoints_m=mids, cell_volume_m3=[0.001, 0.0015, 0.002]
        ),
        parameters=dict(
            q_C=1.602e-19,
            kb_J_K=1.3806e-23,
            NAv_per_mol=6.022e23,
            relative_permittivity=80.0,
            vacuum_permittivity_F_m=8.85419e-12,
            configured_temperature_K=298.15,
            cell_height_m=0.1,
            cell_space_m=0.05,
            cell_radius_m=0.05,
            true_cell_size_m=0.1,
            magnetic_permeability_H_m=1.25664e-6,
        ),
        cache_initial_state=dict(
            cell_mol_m3=initial_cell,
            environment_mol_m3=initial_environment,
            free_diffusion_m2_s=[
                0.0 if case == "zero_sigma" else (1 + 0.2 * i) * 1e-9 for i in range(s)
            ],
        ),
    )
    frames = []
    for tick in range(3):
        current = dict(
            cell_mol_m3=[[value + 0.1 * tick for value in row] for row in initial_cell],
            membrane_flux_mol_m2_s=[
                [(i + 1) * (j - 3) * 1e-8 * (1 + 0.05 * tick) for j in range(m)] for i in range(s)
            ],
            junction_flux_mol_m2_s=[
                [(i + 2) * (4 - j) * 1e-8 * (1 + 0.04 * tick) for j in range(m)] for i in range(s)
            ],
            extra_charge_C_m3=[(j - 1) * 0.002 for j in range(n)],
            extra_current_A_m2=[(j - 4) * 0.0002 for j in range(m)],
        )
        packet = dict(
            old_voltage_V=[(-0.03 + 0.004 * j) * (1 + 0.03 * tick) for j in range(m)],
            boundary_V=dict(R=0.007, L=-0.011, T=0.013, B=-0.017),
        )
        if is_ecm:
            packet.update(
                environment_mol_m3=deepcopy(initial_environment),
                environment_flux_x=[
                    [(i + 1) * ((k % nx) - 1) * 1e-8 * (1 + 0.1 * tick) for k in range(e)]
                    for i in range(s)
                ],
                environment_flux_y=[
                    [(i + 2) * ((k // nx) - 1) * 1e-8 * (1 + 0.07 * tick) for k in range(e)]
                    for i in range(s)
                ],
                extra_environment_current_xy=[
                    [(k % 3 - 1) * 0.0001, (k % 5 - 2) * 0.0002] for k in range(e)
                ],
                extra_environment_charge_C_m3=[(k % 5 - 2) * 0.01 for k in range(e)],
            )
            if case in ("zero_flux", "uniform_current"):
                packet["environment_flux_x"] = [[0.0] * e for _ in range(s)]
                packet["environment_flux_y"] = [[0.0] * e for _ in range(s)]
                packet["extra_environment_current_xy"] = [
                    [0.01, -0.02] if case == "uniform_current" else [0.0, 0.0] for _ in range(e)
                ]
                packet["boundary_V"] = dict.fromkeys(("R", "L", "T", "B"), 0.0)
            if case == "edge_field":
                packet["extra_environment_charge_C_m3"] = [0.0] * e
                packet["extra_environment_charge_C_m3"][0] = 0.05
        else:
            packet["environment_weight"] = [
                [0.4 + 0.05 * ((i * nx + j) % 7) for j in range(nx)] for i in range(ny)
            ]
            if case in ("zero_flux", "uniform_current"):
                packet["old_voltage_V"] = [0.0] * m
                packet["boundary_V"] = dict.fromkeys(("R", "L", "T", "B"), 0.0)
        frames.append(dict(current=current, environment=packet))
    if case == "permuted":
        order = list(reversed(range(m)))
        for key in ("membrane_ids", "owner", "membrane_area_m2", "normal_xy"):
            geometry[key] = [geometry[key][j] for j in order]
        raw["geometry"]["membrane_midpoints_m"] = [mids[j] for j in order]
        if not is_ecm:
            raw["cache_initial_state"]["environment_mol_m3"] = [
                [row[j] for j in order] for row in initial_environment
            ]
        for frame in frames:
            for key in ("membrane_flux_mol_m2_s", "junction_flux_mol_m2_s"):
                frame["current"][key] = [[row[j] for j in order] for row in frame["current"][key]]
            frame["current"]["extra_current_A_m2"] = [
                frame["current"]["extra_current_A_m2"][j] for j in order
            ]
            frame["environment"]["old_voltage_V"] = [
                frame["environment"]["old_voltage_V"][j] for j in order
            ]
    return dict(definition=raw, frames=frames)
