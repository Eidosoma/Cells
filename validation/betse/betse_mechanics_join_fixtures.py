"""Deferred complete declarations; preparation never constructs a layout."""

from copy import deepcopy

from validation.mechanics.betse_deformation_fixtures import layout

CASES = (
    "ordinary-steady",
    "ordinary-osmotic",
    "no-deformation",
    "all-controls-off",
    "noecm-osmotic",
    "molecule-grn-pressure",
    "no-aquaporin",
    "double-dt",
    "free-boundary",
    "zero-galvanotropism",
    "sampled-display",
    "sampled-display-once",
    "post-cut-provenance",
    "imported-display-cache",
)
REFUSALS = (
    "enabled-flow",
    "dynamic-deformation",
    "fast-solver",
    "missing-seed-provenance",
    "wrong-environment-map",
    "wrong-field-epoch",
    "wrong-field-stage",
    "wrong-dt",
    "foreign-state",
    "missing-electric-after-osmotic",
    "nonfinite-pressure-after-osmotic",
    "sample-without-barrier",
    "duplicate-sample",
    "adaptive-display",
    "noecm-permuted-map",
    "noecm-wrong-environment-size",
)
CORRUPTIONS = (
    "wrong-PP",
    "wrong-displacement-axis",
    "changed-disabled-flow",
    "stale-second-display-centres",
    "wrong-osmotic-dt",
)
RAW_FAILURES = ("missing-electric-after-osmotic", "nonfinite-pressure-after-osmotic")


def fixture(case="ordinary-steady"):
    if case not in CASES:
        raise ValueError("Unknown mechanics context")
    sampled = case in ("sampled-display", "sampled-display-once", "imported-display-cache")
    mesh = deepcopy(layout(6, 6) if sampled else layout())
    n, m = len(mesh["centers_m"]), len(mesh["neighbors"])
    is_ecm = case != "noecm-osmotic"
    e = 9 if is_ecm else m
    mapping = [i % e for i in range(n)]
    membrane_map = list(range(m)) if not is_ecm else [mapping[a] for a, _ in mesh["neighbors"]]
    sm = mesh["sum_membranes"]
    average = (
        [[float(j == mapping[i]) for j in range(e)] for i in range(n)]
        if is_ecm
        else [
            [sum(row[k] for k in range(m) if membrane_map[k] == j) / sum(row) for j in range(e)]
            for row in sm
        ]
    )
    cell_ids = ["seeded-cell/" + str(11 * i + 3) for i in range(n)]
    env_ids = ["environment/" + str(7 * i + 2) for i in range(e)]
    osmo = case in (
        "ordinary-osmotic",
        "no-deformation",
        "noecm-osmotic",
        "molecule-grn-pressure",
        "no-aquaporin",
        "double-dt",
    )
    definition = dict(
        kind="betse_ordinary_full_steady_mechanics_join_v1_5_0@1",
        geometry=dict(
            cell_ids=cell_ids,
            environment_ids=env_ids,
            layout=mesh,
            cell_to_environment=mapping,
            membrane_to_environment=membrane_map,
            environment_average=average,
            display_vertex_weights=[
                [
                    w * a / mesh["cell_area_m2"][i]
                    for w, a in zip(row, mesh["membrane_area_m2"], strict=True)
                ]
                for i, row in enumerate(sm)
            ],
        ),
        policy=dict(
            solver="FULL",
            fluid_flow=False,
            td_deform=False,
            deformation=case not in ("no-deformation", "all-controls-off"),
            deform_osmo=osmo,
            is_ecm=is_ecm,
            molecules_enabled=case == "molecule-grn-pressure",
            grn_enabled=case == "molecule-grn-pressure",
            display_regime="global_quartic_conditional" if sampled else "none",
        ),
        parameters=dict(
            young_modulus_Pa=1000.0,
            galvanotropism_m2_V=0.0 if case == "zero-galvanotropism" else 1e-9,
            fixed_boundary=case != "free-boundary",
            dt_s=2e-6 if case == "double-dt" else 1e-6,
            viscous_damping_native=0.01,
            cell_radius_m=1e-5,
            gas_constant_J_mol_K=8.314,
            aquaporin_fraction=0.0 if case == "no-aquaporin" else 0.01,
            water_viscosity_Pa_s=0.01,
            membrane_thickness_m=7.5e-9,
            density_kg_m3=1050.0,
        ),
        provenance=dict(
            geometry_epoch="post-cut-B" if case == "post-cut-provenance" else "seed-A",
            graph_origin="post_cut_graphLaplacian"
            if case == "post-cut-provenance"
            else "seed_graphLaplacian",
            prerequisites="caller_supplied_layout_DEC_fields_no_seed_execution",
        ),
    )
    initial = {
        key: [0.0] * n
        for key in (
            "osmo_P_cell",
            "osmo_P_delta",
            "u_osmo",
            "div_u_osmo",
            "PP",
            "gPxc",
            "gPyc",
            "d_cells_x",
            "d_cells_y",
        )
    }
    initial |= dict(
        osmo_P_env=[0.0] * e,
        u_cells_x=0.0,
        u_cells_y=0.0,
        u_env_x=0.0,
        u_env_y=0.0,
        display_centres_m=deepcopy(mesh["centers_m"]),
        display_vertices_m=deepcopy(mesh["vertices_m"]),
    )
    if case == "imported-display-cache":
        initial["display_centres_m"] = [[x + 2e-9, y - 3e-9] for x, y in mesh["centers_m"]]
        initial["display_vertices_m"] = [
            [x + 1e-7 + index * 1e-10, y - 2e-7 + index * 2e-10]
            for index, (x, y) in enumerate(mesh["vertices_m"])
        ]
    steps = []
    for index in range(2 if sampled else 3):
        field = [
            [5.0 + (index + 1) * (2e4 * x + 1e4 * y) for x, y in mesh["centers_m"]],
            [-3.0 + (index + 1) * (1e4 * x - 2e4 * y) for x, y in mesh["centers_m"]],
        ]
        steps.append(
            dict(
                receipt=dict(
                    stage="normal_full_after_handlers_before_deferred_material_voltage",
                    geometry_epoch=definition["provenance"]["geometry_epoch"],
                    cell_ids=cell_ids,
                    environment_ids=env_ids,
                    source_step=index,
                    deferred_material_voltage_commit_done=False,
                ),
                clock_s=index * definition["parameters"]["dt_s"],
                dt_s=definition["parameters"]["dt_s"],
                temperature_K=310.0 + index,
                primary_ids=["primary/0", "primary/1"],
                molecule_ids=["molecule/0"],
                grn_ids=["grn/0"],
                pressure_Pa=[0.0] * n
                if sampled
                else [1.0 + 0.1 * i + 0.02 * index for i in range(n)],
                electric_field_V_m=field,
                current_density_A_m2=[[0.03 * (i + 1) for i in range(n)], [-0.01] * n],
                charge_density_C_m3=[0.3 + 0.1 * i for i in range(n)],
                conductivity_S_m=[0.8] * n,
                primary_cell_mM=[[100.0 + i for i in range(n)], [20.0 - 0.1 * i for i in range(n)]],
                primary_env_mM=[[120.0 + i for i in range(e)], [25.0 - 0.2 * i for i in range(e)]],
                molecule_cell_mM=[[0.3 + 0.02 * i for i in range(n)]],
                molecule_env_mM=[[0.5 + 0.03 * i for i in range(e)]],
                grn_cell_mM=[[0.4 + 0.01 * i for i in range(n)]],
                grn_env_mM=[[0.2 + 0.03 * i for i in range(e)]],
                sample=sampled and (case != "sampled-display-once" or index == 0),
            )
        )
    return dict(case=case, definition=definition, initial=initial, steps=steps)
