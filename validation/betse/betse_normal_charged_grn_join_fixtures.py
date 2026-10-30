"""Real normal GRN configuration, neutral gene products and separate controls."""

import copy

from validation.betse.betse_normal_molecule_join_fixtures import fixture as previous

TEMPLATE_CASES = (
    "regulated",
    "no_regulators",
    "no_modulators",
    "GJ_zero",
    "source_defaults",
    "time_dilation",
    "temperature_split",
    "publish_off",
    "scheduled_override",
    "no_growth",
)
TEMPLATE_CONTROLS = ("no_regulators", "no_modulators", "no_growth")


def _template(case="regulated"):
    if case not in TEMPLATE_CASES:
        raise ValueError("Choose a declared genuine GRN case")
    data = previous(
        case if case in ("temperature_split", "publish_off", "scheduled_override") else "coupled"
    )
    definition = data["channel_definition"]
    definition["kind"] = "cells.betse_normal_grn_join_inputs@1"
    definition["channels"] = []
    definition["provenance"] = (
        "Actual MasterOfGenes initialization and original guarded normal dispatch"
    )
    net = definition["network"]
    net["owner"] = "grn"
    net["provenance"] = (
        "Configured neutral genes; actual owner lifecycle, full public-field cache carry; "
        "no standalone sim-grn credit"
    )
    if case == "no_modulators":
        net["modulators"] = []
    if case == "GJ_zero":
        net["modulators"][0]["max effect"] = 0.0
    for drive in data["drives"]:
        drive["channels"]["modulators"] = {}
    biomolecules = []
    for row in net["molecules"]:
        name = row["name"]
        value = 0.8 if name == "X" else 0.4
        env = 0.6 if name == "X" else 0.2
        row["initial"] = dict(
            c_cells=[value] * 3, cc_at_mem=[value] * 9, c_env=[env] * 9, flux_intra=[0.0] * 9
        )
        row["parameters"].update(
            c_bound=env, modify_time_factor=2.0 if case == "time_dilation" else 1.0
        )
        growth = row["growth"]
        growth.update(
            enabled=case != "no_growth",
            production_rate_mM_s=0.03 if name == "X" else 0.02,
            decay_rate_per_s=0.02 if name == "X" else 0.015,
            decay_max_per_s=0.01 if name == "X" else 0.0,
            scale_factor=0.7 if name == "X" else 1.0,
        )
        if case == "no_growth":
            growth.update(
                production_rate_mM_s=0.0,
                decay_rate_per_s=0.0,
                decay_max_per_s=0.0,
                scale_factor=1.0,
            )
        gad = (
            None
            if case == "no_growth"
            else {
                "production rate": growth["production_rate_mM_s"],
                "decay rate": growth["decay_rate_per_s"],
                "decay max": growth["decay_max_per_s"],
                "scale factor": growth["scale_factor"],
                "apply to": "all",
            }
        )
        if gad is not None and case != "no_regulators":
            if name == "X":
                gad.update(
                    {
                        "activators": ["Y"],
                        "Km activators": [0.3],
                        "n activators": [2.0],
                        "decay inhibitors": ["Na"],
                        "Km decay inhibitors": [20.0],
                        "n decay inhibitors": [1.0],
                    }
                )
            else:
                gad.update({"inhibitors": ["X"], "Km inhibitors": [0.8], "n inhibitors": [2.0]})
        params = row["parameters"]
        config = {
            "name": name,
            "cell conc": value,
            "env conc": env,
            "Dm": params["Dm"],
            "Do": params["Do"],
            "Dgj": params["Dgj"],
            "z": 0.0,
            "update intracellular": False,
            "TJ permeable": params["ignoreTJ"],
            "GJ impermeable": params["ignoreGJ"],
            "TJ factor": params["TJ_factor"],
            "growth and decay": gad,
            "plotting": {
                "plot 2D": False,
                "animate": False,
                "autoscale colorbar": True,
                "max val": 1.0,
                "min val": 0.0,
            },
        }
        if case == "time_dilation":
            config["use time dilation"] = True
        if case == "source_defaults":
            del config["Dgj"]
            params["Dgj"] = 1e-16
        biomolecules.append(config)
    net["grn_configuration"] = {
        "biomolecules": biomolecules,
        "reactions": copy.deepcopy(net["reactions"]),
        "modulators": copy.deepcopy(net["modulators"]) or None,
        "time dilation factor": 2.0 if case == "time_dilation" else 1.0,
    }
    net["ion_boundary_mM"] = [row[0] for row in data["initial"]["bath_mol_m3"]]
    net["grn_initialization_publish"] = True
    net["raw_initialization_fault"] = None
    data["grn_case_id"] = case
    data["case_role"] = "component_control" if case in TEMPLATE_CONTROLS else "new_grn_case"
    return data


CASES = (
    "positive",
    "negative",
    "zero_charge_control",
    "compensation_off",
    "runtime_publish_off",
    "negative_threshold_gap",
    "source_defaults",
    "growth_off",
    "no_modulators",
    "temperature_split",
    "time_dilation",
    "scaled_charge",
)
COMPONENT_CONTROLS = ("zero_charge_control", "compensation_off", "growth_off")
RAW_CASES = (
    "cell_positive_excess",
    "cell_negative_excess",
    "env_positive_excess",
    "env_negative_excess",
)
DEPENDENCIES = (
    "missing_M",
    "wrong_M_valence",
    "missing_ionic_cache",
    "missing_balance_events",
    "missing_source_default",
    "wrong_owner",
)


def fixture(case="positive"):
    if case not in CASES:
        raise ValueError("Choose a declared charged GRN case")
    data = _template(
        {"runtime_publish_off": "publish_off", "growth_off": "no_growth"}.get(
            case, case if case in TEMPLATE_CASES else "regulated"
        )
    )
    # A real sixth, stationary M(-1) ion is supplied by this caller. Subtracting
    # the same amount from the pre-existing P(-1) inputs retains their combined
    # nominal charge. This is a manufactured input recipe, not a source repair.
    ion = data["ion_definition"]["ions"]
    original_ids = list(ion["ids"])
    for definition in (data["ion_definition"], data["current_definition"]):
        definition["ions"]["ids"] = original_ids + ["M"]
        definition["ions"]["valence"] = list(definition["ions"]["valence"]) + [-1.0]
    for key in ("membrane_diffusion_m2_s", "gap_diffusion_m2_s"):
        ion[key] = list(ion[key]) + [[0.0] * 9]
    voltage = data["voltage_definition"]["ions"]
    voltage["free_diffusion_m2_s"] = list(voltage["free_diffusion_m2_s"]) + [0.0]
    gap = case == "negative_threshold_gap"
    for key, value in (
        ("cell_mol_m3", 0.5e-6 if gap else 1e-4),
        ("membrane_mol_m3", 2e-6 if gap else 1e-4),
        ("bath_mol_m3", 1e-4),
        ("membrane_flux_mol_m2_s", 0.0),
        ("junction_flux_mol_m2_s", 0.0),
    ):
        width = 3 if key == "cell_mol_m3" else 9
        data["initial"][key] = list(data["initial"][key]) + [[value] * width]
        if key in ("cell_mol_m3", "membrane_mol_m3", "bath_mol_m3"):
            p = original_ids.index("P")
            data["initial"][key][p] = [v - value for v in data["initial"][key][p]]
    definition = data["channel_definition"]
    definition["kind"] = "cells.betse_normal_charged_grn_join_inputs@1"
    net = definition["network"]
    z = (
        -1.0
        if case in ("negative", "negative_threshold_gap")
        else 0.0
        if case == "zero_charge_control"
        else 1.0
    )
    scale = 2e-6 if case == "scaled_charge" else 1e-6
    for config, row in zip(net["grn_configuration"]["biomolecules"], net["molecules"], strict=True):
        config.update({"z": z, "scale factor": scale})
        row["parameters"].update(z=z, scale_factor=scale)
        row["provenance"] = (
            "Manufactured charged product; formal charge scale, no physiological calibration"
        )
    net["ion_boundary_mM"] = [row[0] for row in data["initial"]["bath_mol_m3"]]
    net["grn_initialization_publish"] = case != "compensation_off"
    net["provenance"] = (
        "Actual charged MasterOfGenes/Core lifecycle and normal dispatch; "
        "real M(-1) compensation row"
    )
    data["charged_grn_case_id"] = data.pop("grn_case_id")
    data["charged_grn_case_id"] = case
    data["case_role"] = (
        "component_control" if case in COMPONENT_CONTROLS else "new_charged_grn_case"
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
        raise ValueError("Choose a declared cold charge capacity refusal")
    data = fixture("negative" if "negative" in case else "positive")
    net = data["channel_definition"]["network"]
    for config, row in zip(net["grn_configuration"]["biomolecules"], net["molecules"], strict=True):
        scale = 1.0 if case == "cell_positive_excess" else 1e-6
        cell = 200.0 if case.startswith("cell_") else config["cell conc"]
        env = (
            (2e8 if "positive" in case else 200.0)
            if case.startswith("env_")
            else config["env conc"]
        )
        config.update({"cell conc": cell, "env conc": env, "scale factor": scale})
        row["parameters"].update(c_bound=env, scale_factor=scale)
        row["initial"].update(c_cells=[cell] * 3, cc_at_mem=[cell] * 9, c_env=[env] * 9)
    net["raw_initialization_fault"] = case
    data["drives"] = data["drives"][:1]
    data["charged_grn_case_id"], data["case_role"] = case, "raw_partial_failure"
    return data
