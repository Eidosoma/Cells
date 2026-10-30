"""Explicit maintained-pool pump packets and original source role/order cases."""

from validation.betse.betse_normal_gated_join_fixtures import fixture as gate_fixture

CASES = (
    "forward",
    "alpha_zero",
    "alpha_negative",
    "redistributed",
    "open_boundary",
    "pump_only",
    "temperature_split",
    "zero_na_membrane",
    "met_ignored",
    "na_stationary",
    "reordered_roles",
    "reverse",
)
CASE_MOVING_COUNTS = {
    "forward": 3,
    "alpha_zero": 3,
    "alpha_negative": 3,
    "redistributed": 3,
    "open_boundary": 3,
    "pump_only": 3,
    "temperature_split": 3,
    "zero_na_membrane": 3,
    "met_ignored": 3,
    "na_stationary": 2,
    "reordered_roles": 3,
    "reverse": 3,
}


def fixture(case="forward"):
    if case not in CASES:
        raise ValueError("Require a declared maintained-pool source pump case")
    data = gate_fixture()
    data["pump_definition"] = dict(
        kind="cells.betse_normal_pump_join_inputs@1",
        provenance="Maintained ATP/ADP/Pi; ignored met argument; no endogenous fuel consumption",
        sodium_id="Na",
        potassium_id="K",
        maintained=dict(cATP=1.5, cADP=0.15, cPi=0.15),
        kinetics=dict(
            KmNK_Na=12.0,
            KmNK_K=0.2,
            KmNK_ATP=0.5,
            deltaGATP=37000.0 if case == "reverse" else -37000.0,
        ),
    )
    data["initial_rate_proxy_mol_m2_s"] = [(j + 1) * 7e-9 for j in range(9)]
    ions = data["ion_definition"]["ions"]
    if case == "open_boundary":
        data["ion_definition"]["parameters"]["cluster_open"] = True
    if case == "pump_only":
        ions["membrane_diffusion_m2_s"] = [[0.0] * 9 for _ in range(4)]
        data["ion_definition"]["parameters"]["junction_surface_fraction"] = 0.0
    if case == "temperature_split":
        data["ion_definition"]["parameters"]["configured_temperature_K"] = 315.0
        data["voltage_definition"]["parameters"]["configured_temperature_K"] = 315.0
    if case == "zero_na_membrane":
        data["initial"]["membrane_mol_m3"][0] = [0.0] * 9
    if case == "na_stationary":
        ions["moving_ids"] = ["K", "Cl"]
    if case == "reordered_roles":
        order = [3, 2, 1, 0]
        for key in ("ids", "valence", "membrane_diffusion_m2_s", "gap_diffusion_m2_s"):
            ions[key] = [ions[key][i] for i in order]
        for key in ("ids", "valence"):
            data["current_definition"]["ions"][key] = [
                data["current_definition"]["ions"][key][i] for i in order
            ]
        for key in (
            "cell_mol_m3",
            "membrane_mol_m3",
            "bath_mol_m3",
            "membrane_flux_mol_m2_s",
            "junction_flux_mol_m2_s",
        ):
            data["initial"][key] = [data["initial"][key][i] for i in order]
        data["voltage_definition"]["ions"]["free_diffusion_m2_s"] = [
            data["voltage_definition"]["ions"]["free_diffusion_m2_s"][i] for i in order
        ]
    for index, forcing in enumerate(data["drives"]):
        if case == "temperature_split":
            forcing["material"]["runtime_temperature_K"] = 281.0 + index
        alpha = (
            0.0
            if case == "alpha_zero"
            else -1e-5
            if case == "alpha_negative"
            else 1e-7
            if case == "reverse"
            else 1e-5
        )
        forcing["pump"] = dict(
            alpha_NaK=alpha,
            block=[0.3 + 0.03 * j for j in range(9)] if case == "redistributed" else [1.0] * 9,
            rho_pump=[0.2 + 0.15 * j for j in range(9)] if case == "redistributed" else [1.0] * 9,
            met_concs=dict(cATP=[1e-9] * 9, cADP=[1000.0] * 9, cPi=[-7.0] * 9)
            if case == "met_ignored"
            else None,
        )
    return data
