"""Prepared rectangular native bath fixtures and scoped scalar controls."""

from validation.betse.betse_normal_catalog_join_fixtures import fixture as catalog_fixture
from validation.betse.betse_normal_channel_join_fixtures import fixture as old_fixture

CASES = (
    "active",
    "alpha_zero",
    "alpha_negative",
    "nonuniform_bath",
    "closed_mask_rho",
    "block_ignored",
    "met_ignored",
    "temperature_split",
    "zero_membrane_Ca",
    "negative_stale_Ca",
    "stationary_Ca",
    "reverse_drive",
    "channel_coupled",
)
PROJECTION_CASES = ("standard", "duplicate_targets", "blocked_restore", "publish_off")


def fixture(case="active"):
    if case not in CASES:
        raise ValueError("Choose a declared CaATP source case")
    data = catalog_fixture("CatLeak", steps=3)
    i = data["ion_definition"]["ions"]["ids"].index("Ca")
    data["initial"]["bath_mol_m3"] = [[value] * 9 for value in data["initial"]["bath_mol_m3"]]
    # This new caller representation is explicit; it is the native initialized
    # rectangular rank, never an in-place reinterpretation of frozen adapters.
    data["channel_definition"]["kind"] = "cells.betse_normal_calcium_join_inputs@1"
    policy = dict(
        Ca_dyn=0,
        provenance="Native rectangular bath; active maintained-pool CaATP; ER unimplemented",
        maintained=dict(data["pump_definition"]["maintained"]),
        kinetics=dict(
            KmCa_Ca=1e-3, KmCa_ATP=0.5, deltaGATP=data["pump_definition"]["kinetics"]["deltaGATP"]
        ),
    )
    data["channel_definition"]["calcium_handler"] = policy
    if case != "channel_coupled":
        data["channel_definition"]["channels"] = []
        for drive in data["drives"]:
            drive["channels"]["modulators"] = {}
    if case == "nonuniform_bath":
        data["initial"]["bath_mol_m3"] = [
            [value * (0.95 + 0.01 * j) for j, value in enumerate(row)]
            for row in data["initial"]["bath_mol_m3"]
        ]
    if case in ("stationary_Ca", "negative_stale_Ca", "zero_membrane_Ca"):
        data["ion_definition"]["ions"]["moving_ids"] = ["Na", "K", "Cl"]
    if case == "negative_stale_Ca":
        data["initial"]["membrane_mol_m3"][i] = [-1e-6 if j % 2 else 0.0001 for j in range(9)]
    if case == "zero_membrane_Ca":
        data["initial"]["membrane_mol_m3"][i] = [0.0] * 9
    if case == "reverse_drive":
        data["pump_definition"]["kinetics"]["deltaGATP"] = 37000.0
        policy["kinetics"]["deltaGATP"] = 37000.0
    for step, drive in enumerate(data["drives"]):
        drive["calcium"] = dict(
            alpha_Ca=0.0
            if case == "alpha_zero"
            else -1e-7
            if case == "alpha_negative"
            else 1e-14
            if case == "reverse_drive"
            else 1e-7,
            block=[0.0 if case == "block_ignored" else 1.0] * 9,
        )
        if case == "closed_mask_rho":
            drive["pump"]["rho_pump"] = [0.2 + 0.1 * j for j in range(9)]
        if case == "met_ignored":
            drive["pump"]["met_concs"] = dict(cATP=[1e-12] * 9, cADP=[1000.0] * 9, cPi=[-7.0] * 9)
        if case == "temperature_split":
            drive["material"]["runtime_temperature_K"] = 281.0 + step
        # Independent controls share the exact source maintained p pools.
        if case == "reverse_drive":
            drive["pump"]["alpha_NaK"] = 1e-7
    return data


def projection_fixture(case="standard"):
    """Exact physical-state projection seam to the frozen B28 inputs.

    No Ca ion is invented. The native Ca-enabled flag is absent; the new rectangular
    normal caller is projected onto the old explicitly uniform scalar-scoped law.
    """
    data = old_fixture(case)
    data["initial"]["bath_mol_m3"] = [[value] * 9 for value in data["initial"]["bath_mol_m3"]]
    data["channel_definition"]["kind"] = "cells.betse_normal_calcium_join_inputs@1"
    data["channel_definition"]["calcium_handler"] = None
    data["initial_calcium_rate_proxy_mol_m2_s"] = None
    for drive in data["drives"]:
        drive["calcium"] = dict(alpha_Ca=0.0, block=[1.0] * 9)
    return data
