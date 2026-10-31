"""Bounded nominally electroneutral normal ECM field-feedback declarations."""

from validation.betse.betse_ecm_grn_fixtures import fixture as previous

CASES = (
    "coupled",
    "polarized",
    "negative",
    "rectangular",
    "fast_duplicate",
    "smoothed",
    "temperature_split",
    "time_dilation",
    "publication_carry",
    "reversed_boundaries",
    "changed_boundary",
    "stationary",
    "no_modulators",
    "no_molecular_transport",
    "neutral_products",
    "zero_boundary",
)
COMPONENT_CONTROLS = (
    "no_modulators",
    "no_molecular_transport",
    "neutral_products",
    "zero_boundary",
)
RAW_CASES = (
    "first_network_negative",
    "second_network_negative",
    "bootstrap_zero_screen",
    "bootstrap_current_overflow",
    "late_field_driven_material_overflow",
)
DEPENDENCIES = (
    "ECM_disabled",
    "fluid",
    "charged_cold",
    "missing_field_state",
    "changed_field_output",
    "supplied_operator",
    "supplied_old_field",
    "missing_cache",
    "missing_default",
    "nonpositive_capacitance",
)


def fixture(case="coupled"):
    if case not in CASES:
        raise ValueError("Choose a declared normal ECM field history")
    base = (
        case
        if case
        in (
            "negative",
            "rectangular",
            "fast_duplicate",
            "smoothed",
            "temperature_split",
            "time_dilation",
            "publication_carry",
            "no_modulators",
            "no_molecular_transport",
        )
        else "charged"
    )
    data = previous(base)
    external = data["definition"]["environment_geometry_definition"]
    ids = external["current_definition"]["ions"]["ids"]
    na, k, cl, p = (ids.index(name) for name in ("Na", "K", "Cl", "P"))
    # A declared new material family, independent of the retained old stress.
    for key in ("cell_mol_m3", "membrane_mol_m3", "environment_mol_m3"):
        rows = data["initial"][key]
        rows[p] = [a + b - c for a, b, c in zip(rows[na], rows[k], rows[cl], strict=True)]
    external["cache_initial_state"]["cell_mol_m3"] = [
        row[:] for row in data["initial"]["cell_mol_m3"]
    ]
    external["cache_initial_state"]["environment_mol_m3"] = [
        row[:] for row in data["initial"]["environment_mol_m3"]
    ]
    for row in data["network"]["configuration"]["biomolecules"]:
        row["scale factor"] = 1e-4
        if case == "neutral_products":
            row["z"] = 0.0
    data["network"]["cold_publish"] = case == "neutral_products"
    data["network"]["initial_ion_boundary"] = [
        row[0] for row in data["initial"]["environment_mol_m3"]
    ]
    bounds = dict(R=0.007, L=-0.011, T=0.013, B=-0.017)
    if case == "zero_boundary":
        bounds = dict.fromkeys(bounds, 0.0)
    if case == "reversed_boundaries":
        bounds = {key: -value for key, value in bounds.items()}
    for index, call in enumerate(data["steps"]):
        packet = call["material"]
        packet.pop("electric_x_source")
        packet.pop("electric_y_source")
        packet["dt_s"] = 1e-4
        packet["boundary_mol_m3"][p] = (
            packet["boundary_mol_m3"][na]
            + packet["boundary_mol_m3"][k]
            - packet["boundary_mol_m3"][cl]
        )
        call["boundary_V"] = {
            key: value * (2 if case == "changed_boundary" and index == 1 else 1)
            for key, value in bounds.items()
        }
    if case == "stationary":
        data["definition"]["ions"]["moving_ids"] = []
    data.update(
        kind="cells.normal_ecm_field_join_inputs@1",
        case_id=case,
        case_role="component_control"
        if case in COMPONENT_CONTROLS
        else "new_normal_ecm_field_case",
        field_parameters=dict(
            capacitance_F_m2=1.0, polarizability=1.0 if case == "polarized" else 0.0
        ),
        bootstrap=dict(dt_s=1e-4, boundary_V=bounds),
        input_recipe=dict(
            P_equals_Na_plus_K_minus_Cl=True,
            fixed_macro_geometry_capacitance_F_m2=1.0,
            fixed_dt_s=1e-4,
            fixed_formal_gene_charge_scale=1e-4,
            values_fixed_before_execution=True,
            old_signed_environment_not_repaired=True,
        ),
    )
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared composed source limit")
    data = fixture()
    if case in ("first_network_negative", "second_network_negative"):
        index = 0 if case.startswith("first_") else 1
        data["network"]["configuration"]["biomolecules"][index]["growth and decay"].update(
            {"production rate": 0.0, "decay rate": 1e8}
        )
    elif case == "bootstrap_zero_screen":
        for key in ("cell_mol_m3", "membrane_mol_m3", "environment_mol_m3"):
            data["initial"][key] = [[0.0] * len(row) for row in data["initial"][key]]
        cached = data["definition"]["environment_geometry_definition"]["cache_initial_state"]
        for key in ("cell_mol_m3", "environment_mol_m3"):
            cached[key] = [[0.0] * len(row) for row in cached[key]]
    elif case == "bootstrap_current_overflow":
        # Explicit post-cache prepared material; the original finite initializer
        # cache retains its separately declared pre-state and is never refreshed.
        data["initial"]["cell_mol_m3"][0] = [1e305] * 3
    else:
        data["steps"][1]["boundary_V"] = dict.fromkeys(("R", "L", "T", "B"), 1000.0)
    data["case_id"], data["case_role"] = case, "raw_source_limit"
    return data
