"""Prepared-phase standalone GRN cases; no normal solver advance."""

import copy

from validation.betse.betse_normal_grn_join_fixtures import fixture as previous

CASES = (
    "standard",
    "fractional_sampling",
    "single_step",
    "sparse_samples",
    "time_dilation",
    "temperature_split",
    "no_growth",
    "no_transport",
    "no_modulators",
    "cold_publication_off",
)
COMPONENT_CONTROLS = ("no_growth", "no_transport", "no_modulators")
RAW_CASES = (
    "cold_missing_Y_Dm",
    "first_negative",
    "second_negative",
    "second_call_missing_Y_Dm",
    "late_plot_cell",
)
DEPENDENCIES = (
    "ECM",
    "mitochondria",
    "fluid",
    "unsafe_sampling",
    "missing_owner_state",
    "missing_boundary_state",
    "file_restart",
)


def fixture(case="standard"):
    if case not in CASES:
        raise ValueError("Choose a declared standalone case")
    old = previous(
        case
        if case in ("time_dilation", "temperature_split", "no_growth", "no_modulators")
        else "regulated"
    )
    net = copy.deepcopy(old["channel_definition"]["network"])
    net["grn_initialization_publish"] = case != "cold_publication_off"
    if case == "no_transport":
        for config, row in zip(
            net["grn_configuration"]["biomolecules"], net["molecules"], strict=True
        ):
            config.update({"Dm": 0.0, "Dgj": 0.0, "GJ impermeable": True})
            row["parameters"].update(Dm=0.0, Dgj=0.0, ignoreGJ=True)
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
    return dict(
        kind="cells.betse_sim_grn_inputs@1",
        provenance=(
            "Explicit prior initialized phase; original simrunner new-owner branch and "
            "entire run_core_sim; file I/O captured in memory"
        ),
        ion_definition=copy.deepcopy(old["ion_definition"]),
        current_definition=copy.deepcopy(old["current_definition"]),
        initial=copy.deepcopy(old["initial"]),
        network=net,
        calls=calls,
        case_id=case,
        case_role="component_control" if case in COMPONENT_CONTROLS else "new_standalone_grn_case",
        initial_dt_s=0.123,
        runtime_temperature_K=281.0 if case == "temperature_split" else 298.15,
        simulator_time_before=[-0.2, -0.1],
        incoming_charge_C_m3=[0.01, -0.02, 0.03],
        incoming_current_A_m2=[(j - 4) * 1e-6 for j in range(9)],
        scope=dict(mitochondria=False, fluid=False, cuts=False, grn_unpickle_filename=None),
    )


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared standalone partial failure")
    data = fixture()
    net = data["network"]
    if case == "cold_missing_Y_Dm":
        del net["grn_configuration"]["biomolecules"][1]["Dm"]
        net["raw_initialization_fault"] = "Y"
    elif case in ("first_negative", "second_negative"):
        i = 0 if case == "first_negative" else 1
        net["molecules"][i]["growth"].update(production_rate_mM_s=0.0, decay_rate_per_s=1e6)
        net["grn_configuration"]["biomolecules"][i]["growth and decay"].update(
            {"production rate": 0.0, "decay rate": 1e6}
        )
    elif case == "second_call_missing_Y_Dm":
        data["calls"][1]["raw_fault"] = "missing_Y_Dm"
    else:
        data["calls"][0]["plot_cell"] = 99
    data["case_id"], data["case_role"] = case, "raw_partial_failure"
    return data
