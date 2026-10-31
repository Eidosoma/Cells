"""Deferred manufactured shared owners plus explicit additional DEC declaration.

The field specimen is not a Voronoi seed. Extra neighbor/DEC/unused display
coordinates below are declared conditional inputs, never inferred seed data.
"""

from copy import deepcopy

from validation.betse.betse_normal_ecm_field_join_fixtures import fixture as field_fixture

CASES = (
    "coupled-osmotic",
    "pressure-only",
    "polarized",
    "publication-carry",
    "temperature-split",
    "mechanics-disabled",
    "osmotic-without-deformation",
    "electric-only",
    "no-aquaporin",
    "stationary-primary",
)
REFUSALS = (
    "foreign-cell-owners",
    "foreign-membrane-owners",
    "changed-cell-measure",
    "changed-membrane-measure",
    "changed-centres",
    "changed-environment-map",
    "wrong-pressure-stage",
    "invented-zero-baseline-pressure",
    "wrong-phase-dt",
    "sampled-display",
    "enabled-flow",
    "dynamic-deformation",
    "FAST",
    "foreign-mechanics-parent",
    "changed-prior-field",
    "late-pressure-counter",
    "nonzero-disabled-flow-drive",
)
RAW_CASES = ("network-negative", "mechanics-overflow-before-commit")
CORRUPTIONS = ("wrong-PP", "wrong-displacement-axis", "changed-disabled-flow", "wrong-osmotic-dt")
PHASE_CORRUPTIONS = ("end-field-for-previous-field", "post-commit-primary-for-pre-commit")


def fixture(case="coupled-osmotic"):
    if case not in CASES:
        raise ValueError("Undeclared field/mechanics specimen")
    field_case = {
        "polarized": "polarized",
        "publication-carry": "publication_carry",
        "temperature-split": "temperature_split",
        "stationary-primary": "stationary",
    }.get(case, "coupled")
    original = field_fixture(field_case)
    for call in original["steps"]:
        for key in ("velocity_x_m_s", "velocity_y_m_s"):
            call["material"][key] = [[0.0 for _ in row] for row in call["material"][key]]
    external = original["definition"]["environment_geometry_definition"]
    cg, fg = external["current_definition"]["geometry"], external["geometry"]
    n, m = len(cg["cell_ids"]), len(cg["membrane_ids"])
    if (n, m) != (3, 9):
        raise ValueError("This explicitly declared extra layout has exactly3/9 owners")
    e = len(original["initial"]["environment_mol_m3"][0])
    sm = [[float(owner == i) for owner in cg["owner"]] for i in range(n)]
    # Independent source-layout declaration on these manufactured owners. It
    # does not claim native mesh generation, polygon closure or DEC inference.
    extra = dict(
        neighbors=[[0, 1], [0, 0], [0, 2], [1, 0], [1, 2], [1, 1], [1, 1], [2, 1], [2, 0]],
        lengths_m=[1.2, 1.0, 2.1, 1.2, 1.3, 1.0, 1.0, 1.3, 2.1],
        force_directions=[
            [1.0, 0.0],
            [0.0, 1.0],
            [0.6, 0.8],
            [-1.0, 0.0],
            [0.8, 0.6],
            [0.0, -1.0],
            [1.0, 0.0],
            [-0.8, -0.6],
            [-0.6, -0.8],
        ],
        curl_directions=[
            [0.8, 0.2],
            [0.0, 1.0],
            [0.4, 0.9],
            [-0.8, -0.2],
            [0.9, 0.4],
            [0.0, -1.0],
            [1.0, 0.0],
            [-0.9, -0.4],
            [-0.4, -0.9],
        ],
        incidence=[[-1.0, 1.0, 0.0], [0.0, -1.0, 1.0], [1.0, 0.0, -1.0]],
        incidence_inverse=[[-1 / 3, 0.0, 1 / 3], [1 / 3, -1 / 3, 0.0], [0.0, 1 / 3, -1 / 3]],
        dual_edge_m=[0.7, 0.8, 0.9],
        primal_edge_m=[1.2, 1.3, 2.1],
        dual_area_m2=[0.2, 0.3, 0.4],
        vertices_m=[
            [0.1, 0.2],
            [0.2, 0.4],
            [0.4, 0.2],
            [1.1, 1.2],
            [1.2, 1.4],
            [1.4, 1.4],
            [1.4, 1.2],
            [2.1, 2.2],
            [2.4, 2.3],
        ],
        layout_scope=(
            "Explicit manufactured DEC/neighbor/display-array prerequisite; "
            "no seeded polygon geometry claim"
        ),
    )
    extra |= dict(
        centers_m=deepcopy(fg["cell_centres_m"]),
        membrane_ids=list(cg["membrane_ids"]),
        sum_membranes=sm,
        membrane_area_m2=list(cg["membrane_area_m2"]),
        cell_area_m2=list(cg["cell_area_m2"]),
        cell_volume_m3=list(fg["cell_volume_m3"]),
        membrane_volume_m3=[
            a * original["definition"]["parameters"]["membrane_thickness_m"]
            for a in cg["membrane_area_m2"]
        ],
        cell_height_m=external["parameters"]["cell_height_m"],
    )
    # Map coordinates come from the original field's independently derived
    # nearest-grid construction at bind time. These are the explicit fixture
    # declarations for this original3x3 manufactured input, not prepared operators.
    cell_map = [0, e // 2, e - 1]
    membrane_map = [0, 1, 4, 4, 5, 8, 6, 7, 8]
    osmo = case not in ("pressure-only", "electric-only", "mechanics-disabled")
    p = original["definition"]["parameters"]
    definition = dict(
        kind="betse_ordinary_full_steady_mechanics_join_v1_5_0@1",
        geometry=dict(
            cell_ids=list(cg["cell_ids"]),
            environment_ids=["native-grid/" + str(k) for k in range(e)],
            layout=extra,
            cell_to_environment=cell_map,
            membrane_to_environment=membrane_map,
            environment_average=[[float(j == cell_map[i]) for j in range(e)] for i in range(n)],
            display_vertex_weights=[
                [
                    w * a / cg["cell_area_m2"][i]
                    for w, a in zip(row, cg["membrane_area_m2"], strict=True)
                ]
                for i, row in enumerate(sm)
            ],
        ),
        policy=dict(
            solver="FULL",
            fluid_flow=False,
            td_deform=False,
            deformation=case not in ("mechanics-disabled", "osmotic-without-deformation"),
            deform_osmo=osmo,
            is_ecm=True,
            molecules_enabled=False,
            grn_enabled=True,
            display_regime="none",
        ),
        parameters=dict(
            young_modulus_Pa=1000.0,
            galvanotropism_m2_V=0.0 if case == "pressure-only" else 1e-9,
            fixed_boundary=True,
            dt_s=original["steps"][0]["material"]["dt_s"],
            viscous_damping_native=0.01,
            cell_radius_m=external["parameters"]["cell_radius_m"],
            gas_constant_J_mol_K=p["R_J_mol_K"],
            aquaporin_fraction=0.0 if case == "no-aquaporin" else 0.01,
            water_viscosity_Pa_s=0.01,
            membrane_thickness_m=p["membrane_thickness_m"],
            density_kg_m3=1050.0,
        ),
        provenance=dict(
            geometry_epoch="declared-common-owners-A",
            graph_origin="seed_graphLaplacian",
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
        u_env_x=deepcopy(original["steps"][0]["material"]["velocity_x_m_s"]),
        u_env_y=deepcopy(original["steps"][0]["material"]["velocity_y_m_s"]),
        display_centres_m=deepcopy(extra["centers_m"]),
        display_vertices_m=deepcopy(extra["vertices_m"]),
    )
    drives = [
        dict(
            stage="after_fire_events_before_pumps",
            source_step=i,
            P_base_Pa=[1.0 + 0.2 * k for k in range(n)] if case == "pressure-only" else [0.0] * n,
            P_mod_Pa=[0.1 * i * (k - 1) for k in range(n)]
            if case == "pressure-only"
            else [0.0] * n,
        )
        for i in range(3)
    ]
    return dict(
        kind="cells.normal_ecm_mechanics_join_inputs@1",
        case_id=case,
        field_inputs=original,
        mechanics_definition=definition,
        mechanics_initial=initial,
        pressure_policy="supplied_post_event_pressure"
        if case == "pressure-only"
        else "native_zero_baseline_no_pressure_events",
        pressure_drives=drives,
        clocks_s=[i * definition["parameters"]["dt_s"] for i in range(3)],
    )


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Unknown raw boundary")
    result = fixture()
    if case == "network-negative":
        row = result["field_inputs"]["network"]["configuration"]["biomolecules"][0]
        row["growth and decay"].update({"production rate": 0.0, "decay rate": 1e8})
    else:
        result["mechanics_definition"]["parameters"]["young_modulus_Pa"] = 1e-320
        result["pressure_policy"] = "supplied_post_event_pressure"
        for drive in result["pressure_drives"]:
            drive["P_mod_Pa"] = [1.0, -1.0, 0.5]
    return result
