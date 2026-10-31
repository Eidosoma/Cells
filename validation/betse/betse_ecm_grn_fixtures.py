"""Nonempty ECM GRN cases on explicit retained material declarations."""

import copy

from validation.betse.betse_ecm_transport_fixtures import fixture as material
from validation.betse.betse_normal_grn_join_fixtures import fixture as grn

CASES = (
    "charged",
    "negative",
    "neutral_cold_control",
    "fast_duplicate",
    "rectangular",
    "tight_junction",
    "smoothed",
    "temperature_split",
    "time_dilation",
    "publication_carry",
    "no_modulators",
    "no_molecular_transport",
    "zero_environment_control",
)
COMPONENT_CONTROLS = (
    "neutral_cold_control",
    "no_modulators",
    "no_molecular_transport",
    "zero_environment_control",
)
RAW_CASES = (
    "cold_X_missing_Dm",
    "cold_Y_missing_Dm",
    "first_environment_negative",
    "second_environment_negative",
)
DEPENDENCIES = (
    "wrong_owner",
    "mitochondria",
    "fluid",
    "charged_cold",
    "missing_cache",
    "missing_default",
    "missing_coefficients",
    "prepared_mapping",
)


def fixture(case="charged"):
    if case not in CASES:
        raise ValueError("Choose a declared ECM GRN case")
    data = material(
        case
        if case in ("fast_duplicate", "rectangular", "smoothed", "temperature_split")
        else "slow"
    )
    cfg = copy.deepcopy(
        grn("time_dilation" if case == "time_dilation" else "regulated")["channel_definition"][
            "network"
        ]["grn_configuration"]
    )
    z = -1.0 if case == "negative" else 0.0 if case == "neutral_cold_control" else 1.0
    for row in cfg["biomolecules"]:
        row.update({"z": z, "scale factor": 1e-6, "Dm": 1e-5, "Do": 1e-3, "Dgj": 2e-4})
        if case == "tight_junction":
            row.update({"TJ permeable": False, "TJ factor": 0.2})
        if case == "no_molecular_transport":
            row.update({"Dm": 0.0, "Do": 0.0, "Dgj": 0.0, "GJ impermeable": True})
        if case == "zero_environment_control":
            row.update({"Dm": 0.0, "env conc": 0.0})
    cfg["modulators"][0].update({"activators": ["K"], "activator Km": [20.0], "activator n": [2.0]})
    if case == "tight_junction":
        cfg["modulators"][0]["activator zone"] = ["env"]
    if case == "no_modulators":
        cfg["modulators"] = None
    e = len(data["initial"]["environment_mol_m3"][0])
    data["network"] = dict(
        owner="grn",
        configuration=cfg,
        cold_publish=case == "neutral_cold_control",
        grid_index_groups=dict(
            all_bound_mem_inds=[0, e // 2],
            interior_bound_mem_inds=[e // 2, e - 1],
            ecm_inds_bound_cell=[0, e - 1],
        ),
        initial_controls=dict(gj_block=[0.7] * 9, NaKATP_block=[1.0] * 9),
        initial_ion_boundary=[row[0] for row in data["initial"]["environment_mol_m3"]],
        raw_initialization_fault=None,
        scope=dict(mitochondria=False, fluid=False, cuts=False, standalone=False),
    )
    data["steps"] = [
        dict(
            material=packet,
            publication=not (case == "publication_carry" and i == 1),
            scheduled_controls=None,
        )
        for i, packet in enumerate(data["steps"])
    ]
    data["case_id"], data["case_role"] = (
        case,
        "component_control" if case in COMPONENT_CONTROLS else "new_ecm_grn_case",
    )
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose an original ECM gene failure")
    data = fixture()
    if case.startswith("cold_"):
        name = case.split("_")[1]
        del data["network"]["configuration"]["biomolecules"][0 if name == "X" else 1]["Dm"]
        data["network"]["raw_initialization_fault"] = name
    else:
        i = 0 if case == "first_environment_negative" else 1
        data["network"]["configuration"]["biomolecules"][i]["Do"] = 1e12
        for call in data["steps"]:
            call["material"]["electric_y_source"] = [
                [0.0] * len(row) for row in call["material"]["electric_y_source"]
            ]
    data["case_id"], data["case_role"] = case, "raw_partial_failure"
    return data
