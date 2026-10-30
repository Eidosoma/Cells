"""Explicit bounded ER inputs; source initialization occurs once per history."""

from validation.betse.betse_normal_calcium_join_fixtures import fixture as calcium_fixture

CASES = (
    "active",
    "serca_zero",
    "release_zero",
    "owners_absent",
    "owner_present_no_IP3",
    "molecules_precedence",
    "metabo_precedence",
    "grn_only",
    "moving_reversed",
    "Ca_stationary",
    "temperature_split",
    "channel_coupled",
)
RAW_CASES = ("zero_denominator", "unused_backward_pole", "equilibrium_overflow")


def owner(present=False, values=None):
    return dict(present=present, contains_IP3=values is not None, IP3_mM=values)


def fixture(case="active"):
    if case not in CASES:
        raise ValueError("Choose a declared ER history")
    data = calcium_fixture("channel_coupled" if case == "channel_coupled" else "active")
    definition = data["channel_definition"]
    definition["kind"] = "cells.betse_normal_er_join_inputs@1"
    policy = definition["calcium_handler"]
    policy.update(
        Ca_dyn=1,
        provenance="Owned all-ion ER state; exact native initialization and handler order",
        endoretic=dict(
            serca_max=1e-10,
            max_er=1e-16,
            act_Km_Ca=0.0002,
            act_n_Ca=2.0,
            inh_Km_Ca=0.0005,
            inh_n_Ca=2.0,
            act_Km_IP3=0.001,
            act_n_IP3=2.0,
        ),
    )
    if case == "serca_zero":
        policy["endoretic"]["serca_max"] = 0.0
    if case == "release_zero":
        policy["endoretic"]["max_er"] = 0.0
    if case == "moving_reversed":
        data["ion_definition"]["ions"]["moving_ids"].reverse()
    if case == "Ca_stationary":
        data["ion_definition"]["ions"]["moving_ids"] = ["Na", "K", "Cl"]
    for index, drive in enumerate(data["drives"]):
        context = dict(
            molecules=owner(True, [0.001, 0.003, 0.002]),
            metabo=owner(),
            grn=owner(),
        )
        if case == "owners_absent":
            context = {name: owner() for name in context}
        if case == "owner_present_no_IP3":
            context["molecules"] = owner(True)
        if case == "molecules_precedence":
            context["metabo"] = owner(True, [0.03, 0.01, 0.04])
            context["grn"] = owner(True, [0.04, 0.02, 0.03])
        if case == "metabo_precedence":
            context["molecules"] = owner(True)
            context["metabo"] = owner(True, [0.003, 0.001, 0.004])
            context["grn"] = owner(True, [0.04, 0.02, 0.03])
        if case == "grn_only":
            context["molecules"] = owner(True)
            context["metabo"] = owner(True)
            context["grn"] = owner(True, [0.004, 0.002, 0.003])
        if case == "temperature_split":
            drive["material"]["runtime_temperature_K"] = 281.0 + index
        drive["er_context"] = context
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared raw SERCA probe")
    p = fixture()["channel_definition"]["calcium_handler"]
    result = dict(
        kind="cells.raw_pumpCaER_probe@1",
        cER_mM=[0.2, 0.2, 0.2],
        cytosol_mM=[0.0001, 0.00012, 0.00009],
        voltage_V=[0.0, 0.0, 0.0],
        runtime_temperature_K=298.15,
        parameters=dict(p["maintained"])
        | dict(p["kinetics"])
        | dict(F=96485.0, R=8.314, serca_max=p["endoretic"]["serca_max"]),
    )
    if case == "zero_denominator":
        result["cytosol_mM"] = [0.0] * 3
    if case == "unused_backward_pole":
        result["cER_mM"][0] = -result["parameters"]["KmCa_Ca"]
    if case == "equilibrium_overflow":
        result["parameters"]["deltaGATP"] = -1e9
    return result
