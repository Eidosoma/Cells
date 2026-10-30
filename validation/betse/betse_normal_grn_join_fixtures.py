"""Real normal GRN configuration, neutral gene products and separate controls."""

import copy

from validation.betse.betse_normal_molecule_join_fixtures import fixture as previous

CASES = (
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
COMPONENT_CONTROLS = ("no_regulators", "no_modulators", "no_growth")
RAW_CASES = (
    "cold_first_missing_Dm",
    "cold_second_missing_Dm",
    "runtime_first_negative",
    "runtime_second_negative",
)
DEPENDENCIES = (
    "wrong_owner",
    "intracellular_field",
    "charged_gene",
    "missing_owner_cache",
    "missing_source_default",
)


def fixture(case="regulated"):
    if case not in CASES:
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
    data["case_role"] = "component_control" if case in COMPONENT_CONTROLS else "new_grn_case"
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a distinct source partial failure")
    data = fixture()
    net = data["channel_definition"]["network"]
    index = 0 if "first" in case else 1
    if case.startswith("cold_"):
        row = net["grn_configuration"]["biomolecules"][index]
        del row["Dm"]
        net["raw_initialization_fault"] = row["name"]
    else:
        growth = net["molecules"][index]["growth"]
        growth.update(enabled=True, production_rate_mM_s=0.0, decay_rate_per_s=1e6)
        gad = net["grn_configuration"]["biomolecules"][index]["growth and decay"]
        gad.update({"production rate": 0.0, "decay rate": 1e6})
    data["drives"] = data["drives"][:1]
    data["grn_case_id"], data["case_role"] = case, "raw_partial_failure"
    return data
