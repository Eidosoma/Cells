"""Configured transporter histories; manufactured, without isoform calibration."""

import copy

from validation.betse.betse_normal_molecule_join_fixtures import fixture as molecule_fixture
from validation.transport.betse_network_transport_fixtures import configuration

CASES = (
    "electrogenic_import",
    "electrogenic_export",
    "nkcc_multiplier_two",
    "ncx_multiplier_three",
    "ordered",
    "neutral_molecule",
    "reverse_order",
    "activator",
    "ignored_product_km",
    "init_phase",
    "late_channel",
    "scheduled_override",
    "publish_off",
    "temperature_split",
    "closed_boundary",
    "transporter_only",
    "zero_capacity",
    "zero_rho",
)
COMPONENT_CONTROLS = ("transporter_only", "zero_capacity", "zero_rho")
RAW_CASES = ("first_subset_partial", "second_subset_partial")
DEPENDENCIES = (
    "missing_membrane_volume",
    "missing_configuration",
    "unknown_profile",
    "mitochondrial_zone",
    "missing_flux_cache",
)


def transporter(
    name, species=("Na",), coefficients=(1,), *, inward=None, outward=(), reversible=True
):
    row = configuration(
        species,
        coefficients,
        inward=inward,
        outward=outward,
        standard=0.0 if reversible else "None",
    )
    row["name"], row["max rate"] = name, 1e-9
    return row


def fixture(case="ordered"):
    if case not in CASES:
        raise ValueError("Choose a declared configured-transporter case")
    prior = {
        "late_channel": "late_channel_coupled",
        "publish_off": "publish_off",
        "scheduled_override": "scheduled_override",
        "temperature_split": "temperature_split",
    }.get(case, "coupled")
    data = molecule_fixture(prior)
    definition = data["channel_definition"]
    definition["kind"] = "cells.betse_normal_transporter_join_inputs@1"
    definition["provenance"] = (
        "Actual configured transporter execution before late channels and chemistry"
    )
    network = definition["network"]
    network["provenance"] = (
        "Supplied configured state; actual read/write/execute transporter methods; "
        "no wrapper lifecycle claim"
    )
    geometry = data["ion_definition"]["geometry"]
    network["membrane_volume_m3"] = [
        0.5 * radius * area
        for radius, area in zip(network["radius_m"], geometry["membrane_area_m2"], strict=True)
    ]
    network["transporter_profiles"] = {}
    rows = [transporter("Na_import")]
    if case == "electrogenic_export":
        rows = [transporter("Na_export", inward=(), outward=("Na",))]
    if case == "nkcc_multiplier_two":
        rows = [transporter("NKCC_configured", ("Na", "K", "Cl"), (1, 1, 2))]
    if case == "ncx_multiplier_three":
        rows = [
            transporter("NCX_configured", ("Na", "Ca"), (3, 1), inward=("Na",), outward=("Ca",))
        ]
    if case == "neutral_molecule":
        rows = [transporter("X_import", ("X",), (1,), reversible=False)]
    if case in ("ordered", "reverse_order", "transporter_only", "zero_capacity", "zero_rho"):
        rows += [
            transporter("Na_export", inward=(), outward=("Na",), reversible=False),
            transporter("X_import", ("X",), (1,), reversible=False),
        ]
    if case == "reverse_order":
        rows.reverse()
    if case == "activator":
        rows[0].update(
            {
                "transporter activators": ["Na"],
                "activator Km": [20.0],
                "activator n": [2.0],
                "activator zone": ["env"],
            }
        )
    if case == "ignored_product_km":
        rows[0]["Km products"] = [3e-6]
    if case == "zero_capacity":
        for row in rows:
            row["max rate"] = 0.0
    if case == "transporter_only":
        network["modulators"], network["reactions"] = [], []
        for row in network["molecules"]:
            row["growth"]["enabled"] = False
            row["parameters"].update(Dm=0.0, Dgj=0.0, ignoreGJ=True)
    if case == "zero_rho":
        for drive in data["drives"]:
            drive["pump"]["rho_pump"] = [0.0] * 9
    if case == "init_phase":
        data["drives"][0]["channels"]["phase_kind"] = "INIT"
    if case == "closed_boundary":
        data["ion_definition"]["parameters"]["cluster_open"] = False
    network["transporters"] = rows
    data["transporter_case_id"] = case
    data["case_role"] = "component_control" if case in COMPONENT_CONTROLS else "new_coupled_case"
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a distinct source partial-write failure")
    data = copy.deepcopy(fixture("ordered"))
    network = data["channel_definition"]["network"]
    bad = transporter("subset_export", inward=(), outward=("Na",), reversible=False)
    bad["apply to"] = ["supplied_subset"]
    network["transporter_profiles"] = {
        "supplied_subset": dict(cells=[1], membranes=[3, 4, 5], environment=[0])
    }
    network["transporters"] = (
        [bad] if case == "first_subset_partial" else [transporter("Na_import"), bad]
    )
    data["drives"] = data["drives"][:1]
    data["transporter_case_id"], data["case_role"] = case, "raw_partial_failure"
    return data
