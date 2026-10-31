"""Prepared ECM standalone contexts, distinct from scalar standalone controls."""

from validation.betse.betse_ecm_grn_fixtures import fixture as previous

CASES = (
    "standard",
    "negative",
    "rectangular",
    "fast_duplicate",
    "smoothed",
    "tight_junction",
    "fractional_sampling",
    "single_step",
    "sparse_samples",
    "time_dilation",
    "temperature_split",
    "no_growth",
    "no_transport",
    "no_modulators",
    "neutral_cold_control",
    "cold_publication_off",
    "zero_environment_control",
    "field_reversed",
)
COMPONENT_CONTROLS = (
    "no_growth",
    "no_transport",
    "no_modulators",
    "neutral_cold_control",
    "zero_environment_control",
)
INHERITED_SCALAR_CONTROLS = ("no_growth", "no_transport", "no_modulators")
RAW_CASES = (
    "cold_missing_Y_Dm",
    "first_negative",
    "second_negative",
    "second_call_missing_Y_Dm",
    "late_plot_cell",
    "first_environment_negative",
    "second_environment_negative",
)
DEPENDENCIES = (
    "ECM_disabled",
    "mitochondria",
    "fluid",
    "unsafe_sampling",
    "missing_owner_state",
    "missing_boundary_state",
    "missing_grid_state",
    "missing_coefficient_state",
    "file_restart",
    "prepared_mapping",
)


def fixture(case="standard"):
    if case not in CASES:
        raise ValueError("Choose a declared ECM standalone case")
    inherited = {
        "neutral_cold_control": "neutral_cold_control",
        "no_transport": "no_molecular_transport",
    }.get(case, case)
    selected = (
        inherited
        if inherited
        in (
            "negative",
            "rectangular",
            "fast_duplicate",
            "smoothed",
            "tight_junction",
            "time_dilation",
            "temperature_split",
            "no_modulators",
            "neutral_cold_control",
            "no_molecular_transport",
            "zero_environment_control",
        )
        else "charged"
    )
    old = previous(selected)
    network = old["network"]
    network["cold_publish"] = case == "neutral_cold_control"
    for row in network["configuration"]["biomolecules"]:
        if case in ("cold_publication_off", "neutral_cold_control"):
            row["z"] = 0.0
        if case == "no_growth":
            row["growth and decay"] = None
    calls = [
        dict(dt_s=0.002, total_s=0.006, sample_s=0.002, plot_cell=1, raw_fault=None),
        dict(dt_s=0.001, total_s=0.004, sample_s=0.002, plot_cell=1, raw_fault=None),
    ]
    if case == "fractional_sampling":
        calls[0].update(total_s=0.007, sample_s=0.003)
        calls[1].update(total_s=0.0045, sample_s=0.0015)
    if case == "single_step":
        for call in calls:
            call["total_s"] = call["dt_s"]
    if case == "sparse_samples":
        for call in calls:
            call["sample_s"] = 0.1
    e = len(old["initial"]["environment_mol_m3"][0])
    ex, ey = (
        old["steps"][0]["material"]["electric_x_source"],
        old["steps"][0]["material"]["electric_y_source"],
    )
    if case == "field_reversed":
        ex = [[-3 * v for v in row] for row in ex]
        ey = [[-3 * v for v in row] for row in ey]
    return dict(
        kind="cells.betse_ecm_sim_grn_inputs@1",
        is_ecm=True,
        provenance=(
            "Original standalone new-owner/reinitialize/run_core_sim on explicit "
            "native-derived ECM phase; no file loading or normal-solver update"
        ),
        material_definition=old["definition"],
        initial=old["initial"],
        network=network,
        calls=calls,
        case_id=case,
        case_role="component_control" if case in COMPONENT_CONTROLS else "new_ecm_standalone_case",
        inherited_scalar_control=case in INHERITED_SCALAR_CONTROLS,
        initial_dt_s=0.123,
        runtime_temperature_K=281.0 if case == "temperature_split" else 298.15,
        simulator_time_before=[-0.2, -0.1],
        rho_channel=[0.8 + 0.02 * j for j in range(9)],
        electric_x_source=ex,
        electric_y_source=ey,
        incoming_publication_fields=dict(
            extra_rho_cells=[0.01, -0.02, 0.03],
            extra_rho_env=[(k - 4) * 1e-3 for k in range(e)],
            extra_J_mem=[(j - 4) * 1e-6 for j in range(9)],
            extra_Jenv_x=[(k - 3) * 1e-7 for k in range(e)],
            extra_Jenv_y=[(2 - k) * 1e-7 for k in range(e)],
        ),
        scope=dict(mitochondria=False, fluid=False, cuts=False, grn_unpickle_filename=None),
    )


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared ECM standalone raw failure")
    data = fixture(
        "rectangular"
        if case in ("first_environment_negative", "second_environment_negative")
        else "standard"
    )
    cfg = data["network"]["configuration"]
    if case == "cold_missing_Y_Dm":
        del cfg["biomolecules"][1]["Dm"]
        data["network"]["raw_initialization_fault"] = "Y"
    elif case in ("first_negative", "second_negative"):
        cfg["biomolecules"][0 if case == "first_negative" else 1]["growth and decay"].update(
            {"production rate": 0.0, "decay rate": 1e6}
        )
    elif case == "second_call_missing_Y_Dm":
        data["calls"][1]["raw_fault"] = "missing_Y_Dm"
    elif case == "late_plot_cell":
        data["calls"][0]["plot_cell"] = 99
    else:
        cfg["biomolecules"][0 if case == "first_environment_negative" else 1]["Do"] = 1e12
        data["electric_y_source"] = [[0.0] * len(row) for row in data["electric_y_source"]]
    data["case_id"], data["case_role"] = case, "raw_partial_failure"
    return data
