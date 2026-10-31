"""Deferred prepared standalone ECM/flow contexts; no fixture is evaluated here."""

from validation.betse.betse_ecm_sim_grn_fixtures import fixture as parent_fixture

CASES = (
    "active-current-advection",
    "active-rectangular",
    "reinitialize-disables-flow",
    "active-zero-current",
)
RAW_CASES = ("zero-mean-concentration", "missing-current-y-after-first-flow-write")
DEPENDENCIES = ("missing-flow-owner", "foreign-cell-owners", "wrong-grid-shape", "ordinary-scope")


def fixture(case=CASES[0]):
    if case not in CASES:
        raise ValueError("Choose a declared standalone current-flow context")
    raw = parent_fixture("rectangular" if case == "active-rectangular" else "standard")
    raw["kind"] = "cells.betse_standalone_grn_flow_join_inputs@1"
    raw["case_id"] = case
    raw["case_role"] = (
        "component_control"
        if case in ("reinitialize-disables-flow", "active-zero-current")
        else "new_standalone_flow_composition"
    )
    raw["scope"]["fluid"] = True
    raw["network"]["scope"].update(fluid=True, standalone=True)
    raw["network"]["configuration"].update(
        {
            "recalculate fluid flow": True,
            "recalculate fluid": case != "reinitialize-disables-flow",
        }
    )
    for call in raw["calls"]:
        call["flow_fault"] = None
    current = raw["material_definition"]["environment_geometry_definition"]["current_definition"]
    geometry = current["geometry"]
    n = len(geometry["cell_ids"])
    shape = (4, 3) if case == "active-rectangular" else (3, 3)
    ny, nx = shape
    fields = {
        name: [0.0] * n
        for name in (
            "P_cells",
            "PP",
            "E_cell_x",
            "E_cell_y",
            "J_cell_x",
            "J_cell_y",
            "rho_cells",
            "u_cells_x",
            "u_cells_y",
        )
    }
    fields["P_cells"] = [1.0, -2.0, 0.5]
    fields["PP"] = [1e-12, -3e-12, 2e-12]
    fields["E_cell_x"] = [2.0, -1.0, 4.0]
    fields["E_cell_y"] = [-3.0, 0.5, 1.0]
    fields["J_cell_x"] = [0.01, 0.02, -0.01]
    fields["J_cell_y"] = [-0.02, 0.005, 0.03]
    fields["rho_cells"] = [0.1, -0.2, 0.3]
    fields["u_env_x"] = [[0.0] * nx for _ in range(ny)]
    fields["u_env_y"] = [[0.0] * nx for _ in range(ny)]
    scale = 0.0 if case == "active-zero-current" else 1.0
    fields["J_env_x"] = [
        [scale * (0.05 + 0.01 * i - 0.005 * j) for j in range(nx)] for i in range(ny)
    ]
    fields["J_env_y"] = [
        [scale * (-0.04 + 0.005 * i + 0.01 * j) for j in range(nx)] for i in range(ny)
    ]
    raw["flow_state"] = dict(
        cell_ids=geometry["cell_ids"],
        membrane_ids=geometry["membrane_ids"],
        environment_ids=["standalone-ECM/" + str(i) for i in range(ny * nx)],
        shape=list(shape),
        initial_simulator_fields=fields,
    )
    raw["presentation"] = dict(autosave=False, turn_all_plots_off=True, capture_stream_inputs=True)
    return raw


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose an explicit standalone source-defect control")
    raw = fixture()
    raw["case_id"] = case
    raw["case_role"] = "raw_source_defect_control_no_accuracy_credit"
    raw["calls"] = raw["calls"][:1]
    if case == "zero-mean-concentration":
        raw["initial"]["environment_mol_m3"] = [
            [0.0 for _ in row] for row in raw["initial"]["environment_mol_m3"]
        ]
    else:
        raw["calls"][0]["flow_fault"] = "missing_current_y"
    return raw
