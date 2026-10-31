"""Declared ECM modern populations; no worker-evaluated fixture outcomes.

All55 class prefixes use a predeclared nonsingular prepared Vm recipe before
bootstrap. These are separate identities from the preserved old Cav_G failure.
"""

from validation.betse.betse_normal_ecm_calcium_join_fixtures import fixture as calcium_fixture

CLASSES = (
    "CaLeak",
    "Ca_L2",
    "Ca_L3",
    "CatLeak",
    "CatLeak2",
    "Cav1p2",
    "Cav1p3",
    "Cav2p1",
    "Cav2p2",
    "Cav2p3",
    "Cav3p1",
    "Cav3p3",
    "Cav_G",
    "Cav_L_ML",
    "Cav_L_ML2",
    "Cav_N_ML",
    "Cav_T_ML",
    "ClLeak",
    "HCN1",
    "HCN2",
    "HCN2_ML",
    "HCN2_cAMP",
    "HCN4",
    "HCN4_ML",
    "HCN4_cAMP",
    "HCNLeak",
    "KLeak",
    "K_Fast",
    "Kir2p1",
    "Kir_ML",
    "Kv1p1",
    "Kv1p2",
    "Kv1p3",
    "Kv1p3_ML",
    "Kv1p4",
    "Kv1p5",
    "Kv1p5S_ML",
    "Kv1p5_ML",
    "Kv1p6",
    "Kv2p1",
    "Kv2p1_ML",
    "Kv2p2",
    "Kv3p1",
    "Kv3p2",
    "Kv3p3",
    "Kv3p4",
    "Kv_ML1",
    "NaLeak",
    "Nav1p2",
    "Nav1p3",
    "Nav1p6",
    "NavRat1",
    "NavRat2",
    "NavRat3",
    "Nav_ML",
)
FAMILIES = {
    "CaLeak": "Ca",
    "Ca_L2": "Ca",
    "Ca_L3": "Ca",
    "CatLeak": "Cat",
    "CatLeak2": "Cat",
    "Cav1p2": "Ca",
    "Cav1p3": "Ca",
    "Cav2p1": "Ca",
    "Cav2p2": "Ca",
    "Cav2p3": "Ca",
    "Cav3p1": "Ca",
    "Cav3p3": "Ca",
    "Cav_G": "Ca",
    "Cav_L_ML": "ML",
    "Cav_L_ML2": "ML",
    "Cav_N_ML": "ML",
    "Cav_T_ML": "ML",
    "ClLeak": "Cl",
    "HCN1": "Fun",
    "HCN2": "Fun",
    "HCN2_ML": "ML",
    "HCN2_cAMP": "Fun",
    "HCN4": "Fun",
    "HCN4_ML": "ML",
    "HCN4_cAMP": "Fun",
    "HCNLeak": "Fun",
    "KLeak": "K",
    "K_Fast": "K",
    "Kir2p1": "K",
    "Kir_ML": "ML",
    "Kv1p1": "K",
    "Kv1p2": "K",
    "Kv1p3": "K",
    "Kv1p3_ML": "ML",
    "Kv1p4": "K",
    "Kv1p5": "K",
    "Kv1p5S_ML": "ML",
    "Kv1p5_ML": "ML",
    "Kv1p6": "K",
    "Kv2p1": "K",
    "Kv2p1_ML": "ML",
    "Kv2p2": "K",
    "Kv3p1": "K",
    "Kv3p2": "K",
    "Kv3p3": "K",
    "Kv3p4": "K",
    "Kv_ML1": "ML",
    "NaLeak": "Na",
    "Nav1p2": "Na",
    "Nav1p3": "Na",
    "Nav1p6": "Na",
    "NavRat1": "Na",
    "NavRat2": "Na",
    "NavRat3": "Na",
    "Nav_ML": "ML",
}

CONTEXT_CASES = (
    "mixed_forward",
    "mixed_reverse",
    "empty_channels",
    "cat_zero_Ca",
    "publication_carry",
    "rectangular",
    "fast_duplicate",
    "profile_duplicate",
    "Ca_membrane_activator",
    "Ca_environment_inhibitor",
    "rho_blocked",
    "maximum_zero",
    "init_inactive_SIM",
    "no_channels",
    "no_CaATP",
    "polarized",
)
CASES = (
    "CaLeak",
    "Ca_L2",
    "Ca_L3",
    "CatLeak",
    "CatLeak2",
    "Cav1p2",
    "Cav1p3",
    "Cav2p1",
    "Cav2p2",
    "Cav2p3",
    "Cav3p1",
    "Cav3p3",
    "Cav_G",
    "Cav_L_ML",
    "Cav_L_ML2",
    "Cav_N_ML",
    "Cav_T_ML",
    "ClLeak",
    "HCN1",
    "HCN2",
    "HCN2_ML",
    "HCN2_cAMP",
    "HCN4",
    "HCN4_ML",
    "HCN4_cAMP",
    "HCNLeak",
    "KLeak",
    "K_Fast",
    "Kir2p1",
    "Kir_ML",
    "Kv1p1",
    "Kv1p2",
    "Kv1p3",
    "Kv1p3_ML",
    "Kv1p4",
    "Kv1p5",
    "Kv1p5S_ML",
    "Kv1p5_ML",
    "Kv1p6",
    "Kv2p1",
    "Kv2p1_ML",
    "Kv2p2",
    "Kv3p1",
    "Kv3p2",
    "Kv3p3",
    "Kv3p4",
    "Kv_ML1",
    "NaLeak",
    "Nav1p2",
    "Nav1p3",
    "Nav1p6",
    "NavRat1",
    "NavRat2",
    "NavRat3",
    "Nav_ML",
    "mixed_forward",
    "mixed_reverse",
    "empty_channels",
    "cat_zero_Ca",
    "publication_carry",
    "rectangular",
    "fast_duplicate",
    "profile_duplicate",
    "Ca_membrane_activator",
    "Ca_environment_inhibitor",
    "rho_blocked",
    "maximum_zero",
    "init_inactive_SIM",
    "no_channels",
    "no_CaATP",
    "polarized",
)
COMPONENT_CONTROLS = ("rho_blocked", "maximum_zero", "no_channels", "no_CaATP", "empty_channels")
RAW_CASES = (
    "cold_Cav_G_literal_pole",
    "second_constructor_literal_pole",
    "empty_profile_indices",
    "first_channel_overflow",
    "second_channel_overflow",
    "first_gene_after_channels",
    "second_gene_after_channels",
)
DEPENDENCIES = (
    "ER_requested",
    "expression_profile",
    "legacy_cagPotassium",
    "INIT_requested",
    "missing_profile_map",
    "missing_route_ion",
    "unsupported_modifier",
    "missing_channel_cache",
    "missing_private_gate",
    "changed_target_cache",
    "changed_owner_flag",
    "wrong_clock",
    "invented_rate_presence",
    "supplied_old_field",
    "missing_constructor_metadata",
    "varying_dt",
)


def population(name, slot=0, maximum=1e-7, apply_to="all"):
    return {
        "name": "population_" + str(slot),
        "channel class": FAMILIES[name],
        "channel type": name,
        "max Dm": maximum,
        "apply to": apply_to,
        "init active": True,
    }


def fixture(case="mixed_forward"):
    if case not in CASES:
        raise ValueError("Choose a declared ECM modern catalog prefix")
    base = (
        case
        if case in ("publication_carry", "rectangular", "fast_duplicate", "polarized", "no_CaATP")
        else "active"
    )
    data = calcium_fixture(base)
    field = data["field"]
    m = len(field["initial"]["voltage_V"])
    # Fixed before all numerical execution. No warm-field or gate-output selection.
    field["initial"]["voltage_V"] = [-0.031123 + 0.003317 * j for j in range(m)]
    channel_names = [case] if case in CLASSES else ["Nav1p2", "HCN2", "Ca_L2"]
    if case == "mixed_reverse":
        channel_names.reverse()
    if case == "cat_zero_Ca":
        channel_names = ["CatLeak", "CaLeak"]
    if case in ("Ca_membrane_activator", "Ca_environment_inhibitor"):
        channel_names = ["CaLeak", "Kv1p2", "NaLeak"]
    if case in ("rho_blocked", "maximum_zero", "init_inactive_SIM"):
        channel_names = ["NaLeak", "HCN2"]
    rows = [population(name, j) for j, name in enumerate(channel_names)]
    profiles = {}
    if case == "profile_duplicate":
        profiles = {"alpha": [0, 1, 1], "beta": [4, 7, 1]}
        for row in rows:
            row["apply to"] = ["beta", "alpha"]
        rows[1]["apply to"] = None
    if case == "Ca_membrane_activator":
        rows[1].update(
            {
                "channel activators": ["Ca"],
                "activator Km": [1.2e-4],
                "activator n": [2.0],
                "activator zone": ["cell"],
            }
        )
    if case == "Ca_environment_inhibitor":
        rows[1].update(
            {
                "channel inhibitors": ["Ca"],
                "inhibitor Km": [1.7],
                "inhibitor n": [2.0],
                "inhibitor zone": ["env"],
            }
        )
    if case == "rho_blocked":
        for call in field["steps"]:
            call["material"]["channel_multiplier"] = [0.0] * m
    if case == "maximum_zero":
        for row in rows:
            row["max Dm"] = 0.0
    if case == "init_inactive_SIM":
        for row in rows:
            row["init active"] = False
        rows[0]["max conductivity"] = 2e-7
    if case == "empty_channels":
        rows = []
    if case == "no_channels":
        rows = None
    data.update(
        kind="cells.normal_ecm_catalog_join_inputs@1",
        case_id=case,
        case_role="component_control"
        if case in COMPONENT_CONTROLS
        else "new_ECM_modern_catalog_composition",
        catalog=dict(
            kind="cells.native_ECM_modern_channel_configuration@1",
            populations=rows,
            tissue_profiles=profiles,
            phase="SIM",
            provenance=(
                "Original read_channels and Channel.init_channel; prepared sim.dyna "
                "index maps; no expression profile"
            ),
        ),
        stop_after_calls=1 if case in CLASSES else 3,
    )
    field["input_recipe"].update(
        modern_cold_vm_recipe="-0.031123+0.003317*j V",
        channel_maxDm_m2_s=1e-7,
        explicit_source_clock_N=3,
    )
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared ECM catalog raw limit")
    data = fixture("mixed_forward")
    rows = [population("NaLeak")]
    if case in ("cold_Cav_G_literal_pole", "second_constructor_literal_pole"):
        rows = [] if case.startswith("cold_") else [population("NaLeak")]
        rows.append(population("Cav_G", len(rows)))
        data["field"]["initial"]["voltage_V"][2] = -0.027
    elif case == "empty_profile_indices":
        rows[0]["apply to"] = []
    elif case == "first_channel_overflow":
        rows[0]["max Dm"] = 1e308
    elif case == "second_channel_overflow":
        rows.append(population("NaLeak", 1, 1e308))
    elif case in ("first_gene_after_channels", "second_gene_after_channels"):
        i = 0 if case.startswith("first_") else 1
        data["field"]["network"]["configuration"]["biomolecules"][i]["growth and decay"].update(
            {"production rate": 0.0, "decay rate": 1e8}
        )
    data["catalog"]["populations"] = rows
    data.update(
        case_id=case, case_role="raw_native_constructor_channel_or_gene_limit", stop_after_calls=1
    )
    return data
