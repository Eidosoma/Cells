"""Charged cold ECM recipes; every counterion has a real owned species row."""

from validation.betse.betse_ecm_grn_fixtures import fixture as previous

CASES = (
    "positive",
    "negative",
    "zero_charge_control",
    "compensation_off",
    "runtime_publish_off",
    "publication_carry",
    "negative_threshold_gap",
    "source_defaults",
    "scaled_charge",
    "rectangular",
    "fast_duplicate",
    "tight_junction",
    "temperature_split",
    "time_dilation",
    "smoothed",
    "scheduled_boundary",
    "no_modulators",
    "no_molecular_transport",
)
COMPONENT_CONTROLS = (
    "zero_charge_control",
    "compensation_off",
    "no_modulators",
    "no_molecular_transport",
)
RAW_CASES = (
    "cell_positive_excess",
    "cell_negative_excess",
    "env_positive_excess",
    "env_negative_excess",
)
DEPENDENCIES = (
    "wrong_owner",
    "missing_M",
    "wrong_M_valence",
    "moving_M",
    "mitochondria",
    "fluid",
    "missing_cache",
    "missing_ionic_cache",
    "missing_balance_events",
    "wrong_environment_shape",
    "missing_default",
    "missing_coefficients",
    "prepared_mapping",
)


def fixture(case="positive"):
    if case not in CASES:
        raise ValueError("Choose a declared ECM charged GRN case")
    inherited = {"positive": "charged", "zero_charge_control": "neutral_cold_control"}.get(
        case, case
    )
    data = previous(
        inherited
        if inherited
        in (
            "charged",
            "negative",
            "neutral_cold_control",
            "publication_carry",
            "rectangular",
            "fast_duplicate",
            "tight_junction",
            "temperature_split",
            "time_dilation",
            "smoothed",
            "no_modulators",
            "no_molecular_transport",
        )
        else "charged"
    )
    definition = data["definition"]
    geometry = definition["environment_geometry_definition"]
    ion = geometry["current_definition"]["ions"]
    original_ids = list(ion["ids"])
    ion["ids"] = original_ids + ["M"]
    ion["valence"] = list(ion["valence"]) + [-1.0]
    m = len(data["initial"]["voltage_V"])
    e = len(data["initial"]["environment_mol_m3"][0])
    n = len(data["initial"]["cell_mol_m3"][0])
    p_index = original_ids.index("P")
    gap = case == "negative_threshold_gap"
    for key, count, value in (
        ("cell_mol_m3", n, 0.5e-6 if gap else 1e-4),
        ("membrane_mol_m3", m, 2e-6 if gap else 1e-4),
        ("environment_mol_m3", e, 1e-4),
        ("membrane_flux_mol_m2_s", m, 0.0),
        ("junction_flux_mol_m2_s", m, 0.0),
        ("environment_flux_x_mol_m2_s", e, 0.0),
        ("environment_flux_y_mol_m2_s", e, 0.0),
    ):
        rows = data["initial"][key]
        rows.append([value] * count)
        if key in ("cell_mol_m3", "membrane_mol_m3", "environment_mol_m3"):
            rows[p_index] = [v - value for v in rows[p_index]]
    for key, width, value in (
        ("membrane_diffusion_m2_s", m, 0.0),
        ("gap_diffusion_m2_s", m, 0.0),
        ("environment_diffusion_m2_s", e, 0.0),
        ("tight_junction_modulator", e, 1.0),
    ):
        definition["ions"][key].append([value] * width)
    geometry["cache_initial_state"] = dict(
        cell_mol_m3=[row[:] for row in data["initial"]["cell_mol_m3"]],
        environment_mol_m3=[row[:] for row in data["initial"]["environment_mol_m3"]],
        free_diffusion_m2_s=list(geometry["cache_initial_state"]["free_diffusion_m2_s"]) + [0.0],
    )
    net = data["network"]
    z = (
        -1.0
        if case in ("negative", "negative_threshold_gap")
        else 0.0
        if case == "zero_charge_control"
        else 1.0
    )
    for row in net["configuration"]["biomolecules"]:
        row.update({"z": z, "scale factor": 2e-6 if case == "scaled_charge" else 1e-6})
        if case == "source_defaults":
            del row["Dgj"]
    net["cold_publish"] = case != "compensation_off"
    net["initial_ion_boundary"] = [row[0] for row in data["initial"]["environment_mol_m3"]]
    for index, call in enumerate(data["steps"]):
        packet = call["material"]
        packet["supplied_pump_membrane_flux_mol_m2_s"].append([0.0] * m)
        packet["supplied_late_membrane_flux_mol_m2_s"].append([0.0] * m)
        packet["boundary_mol_m3"][p_index] -= 1e-4
        packet["boundary_mol_m3"].append(1e-4)
        call["boundary_override"] = case == "scheduled_boundary" and index == 1
        if case == "runtime_publish_off":
            call["publication"] = False
    data["case_id"] = case
    data["case_role"] = (
        "component_control" if case in COMPONENT_CONTROLS else "new_ecm_charged_grn_case"
    )
    data["counterion_input_recipe"] = dict(
        actual_M_row=True,
        stationary_M=True,
        P_decrement_equals_supplied_M=True,
        membrane_cache_independent_from_bulk=gap,
        biological_calibration=False,
    )
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared ECM cold capacity refusal")
    # Environment failures use E=12, M=9 to expose region/shape ownership.
    data = fixture("rectangular" if case.startswith("env_") else "positive")
    for row in data["network"]["configuration"]["biomolecules"]:
        row.update(
            {
                "z": -1.0 if "negative" in case else 1.0,
                "scale factor": 1.0 if case == "cell_positive_excess" else 1e-6,
                "cell conc": 200.0 if case.startswith("cell_") else row["cell conc"],
                "env conc": (2e8 if "positive" in case else 200.0)
                if case.startswith("env_")
                else row["env conc"],
            }
        )
    data["network"]["raw_initialization_fault"] = case
    data["case_id"], data["case_role"] = case, "raw_partial_capacity_failure"
    return data
