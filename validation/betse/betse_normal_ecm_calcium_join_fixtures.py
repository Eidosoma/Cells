"""Declared native CaATP cases on the full-field macro-geometry boundary."""

import copy

from validation.betse.betse_normal_ecm_field_join_fixtures import fixture as field_fixture

CASES = (
    "active",
    "polarized",
    "negative_genes",
    "rectangular",
    "fast_duplicate",
    "smoothed",
    "temperature_split",
    "time_dilation",
    "publication_carry",
    "zero_membrane_Ca",
    "negative_environment_Ca",
    "stationary_Ca",
    "no_CaATP",
    "neutral_genes",
    "zero_boundary",
    "cluster_open",
)
COMPONENT_CONTROLS = ("stationary_Ca", "no_CaATP", "neutral_genes", "zero_boundary")
RAW_CASES = (
    "first_gene_negative",
    "second_gene_negative",
    "CaATP_equilibrium_underflow",
    "late_CaATP_underflow",
    "bootstrap_zero_screen",
    "CaATP_alpha_overflow",
)
DEPENDENCIES = (
    "ER_requested",
    "ER_kinetics_injected",
    "maintained_override",
    "missing_Ca",
    "wrong_Ca_valence",
    "changed_rate_cache",
    "invented_rate_presence",
    "wrong_clock",
    "varying_dt",
    "supplied_old_field",
    "negative_alpha",
    "missing_network_cache",
)


def neutralize(field):
    external = field["definition"]["environment_geometry_definition"]
    names = external["current_definition"]["ions"]["ids"]
    na, k, cl, p, ca = (names.index(x) for x in ("Na", "K", "Cl", "P", "Ca"))
    for key in ("cell_mol_m3", "membrane_mol_m3", "environment_mol_m3"):
        rows = field["initial"][key]
        rows[p] = [
            a + b + 2 * c - d
            for a, b, c, d in zip(rows[na], rows[k], rows[ca], rows[cl], strict=True)
        ]
    for step in field["steps"]:
        boundary = step["material"]["boundary_mol_m3"]
        boundary[p] = boundary[na] + boundary[k] + 2 * boundary[ca] - boundary[cl]


def fixture(case="active"):
    if case not in CASES:
        raise ValueError("Choose a declared native ECM CaATP history")
    base = {
        "active": "coupled",
        "negative_genes": "negative",
        "zero_membrane_Ca": "coupled",
        "negative_environment_Ca": "coupled",
        "stationary_Ca": "coupled",
        "no_CaATP": "coupled",
        "neutral_genes": "neutral_products",
        "cluster_open": "coupled",
    }.get(case, case)
    field = field_fixture(base)
    definition = field["definition"]
    external = definition["environment_geometry_definition"]
    cg = external["current_definition"]["geometry"]
    n, m, e = 3, len(cg["owner"]), len(field["initial"]["environment_mol_m3"][0])
    external["current_definition"]["ions"]["ids"].append("Ca")
    external["current_definition"]["ions"]["valence"].append(2.0)
    ca = 4
    definition["ions"]["moving_ids"].append("Ca")
    for name, values in (
        ("membrane_diffusion_m2_s", [1.4e-5] * m),
        ("gap_diffusion_m2_s", [1.6e-4] * m),
        ("environment_diffusion_m2_s", [1.4e-3] * e),
        ("tight_junction_modulator", [0.6] * e),
    ):
        definition["ions"][name].append(values)
    bulk = [0.0 if case == "zero_membrane_Ca" else 1e-4 + 2e-5 * j for j in range(n)]
    field["initial"]["cell_mol_m3"].append(bulk)
    field["initial"]["membrane_mol_m3"].append([bulk[i] for i in cg["owner"]])
    field["initial"]["environment_mol_m3"].append([2.0 + 0.1 * (j % 3) for j in range(e)])
    for key, size, value in (
        ("membrane_flux_mol_m2_s", m, 7e-7),
        ("junction_flux_mol_m2_s", m, -4e-7),
        ("environment_flux_x_mol_m2_s", e, 3e-6),
        ("environment_flux_y_mol_m2_s", e, -2e-6),
    ):
        field["initial"][key].append([value] * size)
    if case == "cluster_open":
        definition["parameters"]["cluster_open"] = True
    if case == "stationary_Ca":
        definition["ions"]["moving_ids"].remove("Ca")
    for call in field["steps"]:
        packet = call["material"]
        packet["boundary_mol_m3"].append(2.0)
        packet["supplied_pump_membrane_flux_mol_m2_s"].append([0.0] * m)
        packet["supplied_late_membrane_flux_mol_m2_s"].append([0.0] * m)
    neutralize(field)
    external["cache_initial_state"] = dict(
        cell_mol_m3=copy.deepcopy(field["initial"]["cell_mol_m3"]),
        environment_mol_m3=copy.deepcopy(field["initial"]["environment_mol_m3"]),
        free_diffusion_m2_s=[1e-9] * 5,
    )
    if case == "negative_environment_Ca":
        # Explicit post-cache prepared state. Clipping the mapped temporary must
        # not rewrite the actual negative environment row in source or port.
        field["initial"]["environment_mol_m3"][ca] = [-0.01 - 0.002 * (j % 3) for j in range(e)]
        for call in field["steps"]:
            call["material"]["boundary_mol_m3"][ca] = -0.02
        neutralize(field)
    field["network"]["initial_ion_boundary"] = [
        row[0] for row in field["initial"]["environment_mol_m3"]
    ]
    if case == "negative_environment_Ca":
        # The existing genuine-GRN declaration admits a nonnegative cold
        # reservoir. A separately declared signed warm boundary is external.
        field["network"]["initial_ion_boundary"][ca] = external["cache_initial_state"][
            "environment_mol_m3"
        ][ca][0]
    field["case_id"] = case
    field["input_recipe"].pop("P_equals_Na_plus_K_minus_Cl")
    field["input_recipe"].update(
        P_equals_Na_plus_K_plus_2Ca_minus_Cl=True,
        explicit_post_cache_material=case == "negative_environment_Ca",
        configured_native_dt_constant=True,
    )
    return dict(
        kind="cells.normal_ecm_calcium_join_inputs@1",
        case_id=case,
        case_role="component_control" if case in COMPONENT_CONTROLS else "new_ECM_CaATP_field_case",
        field=field,
        calcium=dict(
            kind="cells.native_ECM_CaATP_configuration@1",
            Ca_dyn=False,
            alpha_Ca=0.0 if case == "no_CaATP" else 1e-6,
            provenance=(
                "Original configured alpha_Ca; native maintained/Km producers and "
                "Ca_dynFalse; no supplied ER/defaults"
            ),
        ),
    )


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared calcium/field raw limit")
    data = fixture()
    field = data["field"]
    if case in ("first_gene_negative", "second_gene_negative"):
        i = 0 if case.startswith("first_") else 1
        field["network"]["configuration"]["biomolecules"][i]["growth and decay"].update(
            {"production rate": 0.0, "decay rate": 1e8}
        )
    elif case in ("CaATP_equilibrium_underflow", "late_CaATP_underflow"):
        field["definition"]["ions"]["moving_ids"] = []
        target = field["bootstrap"] if case.startswith("CaATP_") else field["steps"][1]
        target["boundary_V"] = dict.fromkeys(("R", "L", "T", "B"), 1000.0)
    elif case == "bootstrap_zero_screen":
        for key in ("cell_mol_m3", "membrane_mol_m3", "environment_mol_m3"):
            field["initial"][key] = [[0.0] * len(row) for row in field["initial"][key]]
        cache = field["definition"]["environment_geometry_definition"]["cache_initial_state"]
        for key in ("cell_mol_m3", "environment_mol_m3"):
            cache[key] = [[0.0] * len(row) for row in cache[key]]
    else:
        data["calcium"]["alpha_Ca"] = 1e308
    data["case_id"], data["case_role"] = case, "raw_CaATP_or_full_field_limit"
    return data
