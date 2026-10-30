"""Distinct prepared-state declarations; no initial packet is evaluated here."""

import copy

from validation.betse.betse_normal_er_join_fixtures import fixture as literal_fixture

CASES = (
    "prepared_er_cl_neutral__active",
    "prepared_er_cl_neutral__serca_zero",
    "prepared_er_cl_neutral__release_zero",
    "prepared_er_cl_neutral__owners_absent",
    "prepared_er_cl_neutral__owner_present_no_IP3",
    "prepared_er_cl_neutral__molecules_precedence",
    "prepared_er_cl_neutral__metabo_precedence",
    "prepared_er_cl_neutral__grn_only",
    "prepared_er_cl_neutral__moving_reversed",
    "prepared_er_cl_neutral__Ca_stationary",
    "prepared_er_cl_neutral__temperature_split",
    "prepared_er_cl_neutral__channel_coupled",
    "prepared_er_P_neutral__active",
)
SIGN_CASES = (
    "prepared_er_cl_Ca_thermal_plus__conditional_ER",
    "prepared_er_cl_Ca_thermal_minus__conditional_ER",
)
REFINEMENT_CASES = ("prepared_er_cl_neutral__active", "prepared_er_P_neutral__active")
REFUSALS = (
    "nonpositive_counterion",
    "charge",
    "voltage",
    "axes_or_geometry",
    "cache_context",
    "parent_association",
)
SUBDIVISIONS = (1, 2, 4)


def recipe(*, counterion="Cl", target="neutral", scope="whole_join"):
    return dict(
        kind="cells.prepared_owned_ER_recipe@1",
        mode="prepared_owned_ER_before_outer_call_channels_primed_v1",
        scope=scope,
        counterion_id=counterion,
        target=target,
        provenance=(
            "Declared manufactured initial inventory and cache phase; "
            "no native constructor, restart or biological equivalence"
        ),
    )


def fixture(case=CASES[0], *, subdivision=1):
    if case not in CASES + SIGN_CASES or subdivision not in SUBDIVISIONS:
        raise ValueError("Choose a frozen distinct prepared-state declaration")
    baseline = case.split("__")[-1]
    if case in SIGN_CASES:
        baseline = "active"
    result = literal_fixture(baseline)
    result["channel_definition"]["provenance"] = (
        "Unchanged ER update engine with an explicitly supplied prepared initial state"
    )
    result["channel_definition"]["calcium_handler"]["provenance"] = (
        "Conditional ER updates from declared complete initial inventories and primed caches; "
        "literal source initializer remains separate"
    )
    target = (
        "Ca_thermal_plus"
        if "thermal_plus" in case
        else "Ca_thermal_minus"
        if "thermal_minus" in case
        else "neutral"
    )
    result["prepared_er_recipe"] = recipe(
        counterion="P" if case.startswith("prepared_er_P_") else "Cl",
        target=target,
        scope="conditional_ER" if case in SIGN_CASES else "whole_join",
    )
    result["prepared_case_id"] = case
    result["subdivision"] = subdivision
    result["original_interval_s"] = 0.002
    result["matched_horizon_s"] = 0.006
    result["original_drive_indices"] = [i for i in range(3) for _ in range(subdivision)]
    drives = []
    for source in result["drives"]:
        for _ in range(subdivision):
            drive = copy.deepcopy(source)
            drive["material"]["dt_s"] = 0.002 / subdivision
            drives.append(drive)
    result["drives"] = drives
    return result
