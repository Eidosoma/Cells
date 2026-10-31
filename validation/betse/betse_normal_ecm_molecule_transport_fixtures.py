"""Unrun all-target configured transporters on unchanged supplied ECM histories."""

import copy
import math

from cells.processes import betse_normal_ecm_molecule_transport as dispatch
from validation.betse import betse_normal_ecm_molecule_dispatch_fixtures as prior
from validation.betse.betse_normal_transporter_join_fixtures import transporter

CASES = (
    "general_transport",
    "both_enabled",
    "GRN_only",
    "both_disabled",
    "zero_capacity",
    "disabled_configuration",
    "empty_transporters",
    "ordered",
    "reverse_order",
    "Na_export",
    "NKCC_two",
    "NCX_three",
    "charged_molecule",
    "ignored_product_Km",
    "activator",
    "fast_duplicate",
    "rectangular",
    "smoothed",
    "time_dilation",
    "temperature_split",
    "publication_carry",
    "no_CaATP",
    "both_channels",
)
COMPONENT_CONTROLS = (
    "GRN_only",
    "both_disabled",
    "zero_capacity",
    "disabled_configuration",
    "empty_transporters",
)
RAW_CASES = (
    "first_general_negative",
    "second_general_negative",
    "first_GRN_negative",
    "second_GRN_negative",
)
RAW_SETUP_CASES = ("missing_max_rate_0", "missing_max_rate_1")
TRANSPORT_DEPENDENCIES = (
    "missing_membrane_volume",
    "foreign_membrane_volume",
    "unmarked_missing_rate",
    "foreign_native_transporters",
    "unsupported_profile",
    "unsupported_GRN_transporters",
    "missing_transporter_cache",
    "changed_transporter_equation",
    "changed_transporter_flux_epoch",
    "arbitrary_pump_weight",
)


def fixture(case):
    if case not in (
        *CASES,
        *RAW_CASES,
        *RAW_SETUP_CASES,
        *TRANSPORT_DEPENDENCIES,
        *prior.DEPENDENCIES,
    ):
        raise ValueError("Unknown declared general-owner ECM transporter case")
    selected = {
        "general_transport": "general_only",
        "GRN_only": "GRN_only",
        "both_disabled": "both_disabled",
        "fast_duplicate": "fast_duplicate",
        "rectangular": "rectangular",
        "smoothed": "smoothed",
        "time_dilation": "time_dilation",
        "temperature_split": "temperature_split",
        "publication_carry": "publication_carry",
        "no_CaATP": "no_CaATP",
        "both_channels": "both_channels",
    }.get(case, "both_enabled")
    if case in RAW_CASES or case in prior.DEPENDENCIES:
        selected = case
    data = prior.fixture(selected)
    data["kind"], data["case_id"] = dispatch.INPUT_KIND, case
    data["provenance"] = (
        "Configured general-owner transporters on the original supplied ECM physical history; "
        "optional separate GRN and original last-writer publications; manufactured, uncalibrated"
    )
    rows = [transporter("general_Na_import")]
    if case == "Na_export":
        rows = [transporter("general_Na_export", inward=(), outward=("Na",))]
    if case == "NKCC_two":
        rows = [transporter("general_NKCC", ("Na", "K", "Cl"), (1, 1, 2))]
    if case == "NCX_three":
        rows = [transporter("general_NCX", ("Na", "Ca"), (3, 1), inward=("Na",), outward=("Ca",))]
    if case == "charged_molecule":
        rows = [transporter("general_X_import", ("X",), (1,), reversible=False)]
    if case in ("ordered", "reverse_order", "zero_capacity", *RAW_SETUP_CASES):
        rows += [
            transporter("general_Na_export", inward=(), outward=("Na",), reversible=False),
            transporter("general_X_import", ("X",), (1,), reversible=False),
        ]
    if case == "reverse_order":
        rows.reverse()
    if case == "zero_capacity":
        for row in rows:
            row["max rate"] = 0.0
    if case == "ignored_product_Km":
        rows[0]["Km products"] = [3e-6]
    if case == "activator":
        rows[0].update(
            {
                "transporter activators": ["Na"],
                "activator Km": [20.0],
                "activator n": [2.0],
                "activator zone": ["env"],
            }
        )
    fault = case if case in RAW_SETUP_CASES else None
    if fault is not None:
        del rows[int(fault[-1])]["max rate"]
    if case == "disabled_configuration":
        rows = None
    if case == "empty_transporters":
        rows = []
    data["handlers"]["molecules"]["network"]["configuration"]["transporters"] = copy.deepcopy(rows)
    data["configuration"]["general network"]["transporters"] = copy.deepcopy(rows)
    external = data["field"]["definition"]["environment_geometry_definition"]
    cg = external["current_definition"]["geometry"]
    mids, centres = (external["geometry"][k] for k in ("membrane_midpoints_m", "cell_centres_m"))
    radii = [
        math.sqrt((mid[0] - centres[owner][0]) ** 2 + (mid[1] - centres[owner][1]) ** 2)
        for mid, owner in zip(mids, cg["owner"], strict=True)
    ]
    data["transport"] = dict(
        membrane_volume_m3=[
            0.5 * radius * area for radius, area in zip(radii, cg["membrane_area_m2"], strict=True)
        ],
        raw_setup_fault=fault,
    )
    return data
