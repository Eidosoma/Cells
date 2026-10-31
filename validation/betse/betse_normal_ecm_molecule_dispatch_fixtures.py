"""Unevaluated dual-handler declarations; inherited scientific data are untuned."""

import copy

from cells.processes import betse_normal_ecm_molecule_dispatch as dispatch
from validation.betse import betse_normal_ecm_calcium_join_fixtures as previous
from validation.betse import betse_normal_ecm_catalog_join_fixtures as channels

CASES = (
    "general_only",
    "both_enabled",
    "GRN_only",
    "both_disabled",
    "disabled_shared_carry",
    "rectangular",
    "fast_duplicate",
    "smoothed",
    "temperature_split",
    "time_dilation",
    "publication_carry",
    "no_modulators",
    "no_molecular_transport",
    "neutral_products",
    "no_CaATP",
    "general_channels",
    "GRN_channels",
    "both_channels",
    "empty_general_channels",
)
RAW_CASES = (
    "first_general_negative",
    "second_general_negative",
    "first_GRN_negative",
    "second_GRN_negative",
)
DEPENDENCIES = (
    "absent_general_network",
    "missing_implement_flag",
    "foreign_implement_flag",
    "GRN_flag_missing",
    "GRN_flag_not_bool",
    "enabled_ER",
    "enabled_flow",
    "FAST",
    "noise_requires_owner",
    "osmotic_requires_both_owners",
    "foreign_general_config",
    "foreign_profile_owner",
    "foreign_general_cache_role",
    "swapped_handler_caches",
    "missing_general_cache",
    "fabricated_disabled_owner",
    "missing_shared_charge",
    "changed_publication_projection",
    "changed_shared_epoch",
    "changed_field_owner",
    "changed_Ca_cache",
)


def fixture(case):
    if case not in CASES and case not in DEPENDENCIES and case not in RAW_CASES:
        raise ValueError("Unknown separately declared two-owner case")
    selected = (
        case
        if case
        in (
            "rectangular",
            "fast_duplicate",
            "smoothed",
            "temperature_split",
            "time_dilation",
            "publication_carry",
            "no_CaATP",
        )
        else "active"
    )
    if case == "neutral_products":
        selected = "neutral_genes"
    if case in RAW_CASES:
        selected = "first_gene_negative" if case.startswith("first_") else "second_gene_negative"
        base = previous.raw_fixture(selected)
    else:
        base = previous.fixture(selected)
    field = base["field"]
    general = copy.deepcopy(field["network"])
    grn = copy.deepcopy(field["network"])
    if case in RAW_CASES and "general" in case:
        # Keep the original failing declaration on the first owner and restore
        # the untouched original active declaration for the independent GRN.
        grn = copy.deepcopy(previous.fixture("active")["field"]["network"])
    elif case in RAW_CASES:
        general = copy.deepcopy(previous.fixture("active")["field"]["network"])
    field["network"] = copy.deepcopy(grn)
    general["owner"] = "molecules"
    if case in ("no_modulators", "no_molecular_transport"):
        for declaration in (general, grn, field["network"]):
            if case == "no_modulators":
                declaration["configuration"]["modulators"] = None
            else:
                for row in declaration["configuration"]["biomolecules"]:
                    row.update(Dm=0.0, Do=0.0, Dgj=0.0)
    catalog = channels.fixture("no_channels")["catalog"]
    general_catalog = copy.deepcopy(catalog)
    grn_catalog = copy.deepcopy(catalog)
    if case in ("general_channels", "GRN_channels", "both_channels"):
        configured = channels.fixture("mixed_forward")["catalog"]
        if case in ("general_channels", "both_channels"):
            general_catalog = copy.deepcopy(configured)
        if case in ("GRN_channels", "both_channels"):
            grn_catalog = copy.deepcopy(configured)
    if case == "empty_general_channels":
        general_catalog["populations"] = []
    enabled = case not in ("GRN_only", "both_disabled", "disabled_shared_carry")
    grn_enabled = case not in ("general_only", "both_disabled", "disabled_shared_carry")
    if case in ("first_general_negative", "second_general_negative"):
        grn_enabled = False
    native_general = dict(
        copy.deepcopy(general["configuration"]),
        **{"channels": copy.deepcopy(general_catalog["populations"]), "implement network": enabled},
    )
    external = field["definition"]["environment_geometry_definition"]
    n = len(field["initial"]["cell_mol_m3"][0])
    m = len(field["initial"]["voltage_V"])
    e = len(field["initial"]["environment_mol_m3"][0])
    assert len(external["current_definition"]["geometry"]["cell_ids"]) == n
    shared = {
        key: [0.0] * size
        for key, size in (
            ("extra_rho_cells", n),
            ("extra_rho_env", e),
            ("extra_J_mem", m),
            ("extra_Jenv_x", e),
            ("extra_Jenv_y", e),
        )
    }
    if case == "disabled_shared_carry":
        shared = {
            key: [(1e-9 if "rho" in key else 1e-12) * (j + 1) for j in range(len(values))]
            for key, values in shared.items()
        }
    return dict(
        kind=dispatch.INPUT_KIND,
        case_id=case,
        provenance=(
            "Explicit native general-network section and independent GRN flag; "
            "supplied physical entry, no whole setup/phase claim"
        ),
        flags=copy.deepcopy(dispatch.FLAGS),
        configuration={
            "general network": native_general,
            "gene regulatory network settings": {"gene regulatory network simulated": grn_enabled},
        },
        field=field,
        calcium=base["calcium"],
        handlers=dict(
            molecules=dict(network=general, catalog=general_catalog),
            grn=dict(network=grn, catalog=grn_catalog),
        ),
        shared_initial=shared,
    )
