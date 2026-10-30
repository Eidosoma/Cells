"""Distinct real-molecule coupled cases and explicitly separate component controls."""

import copy

from validation.betse.betse_normal_network_join_fixtures import fixture as feedback_fixture

CASES = (
    "reaction_only",
    "growth_only",
    "transport_only",
    "coupled",
    "charged",
    "nonuniform_bath",
    "closed_mask",
    "zero_Dm_GJ",
    "ignore_GJ",
    "time_dilation",
    "temperature_split",
    "reverse_order",
    "late_channel_coupled",
    "publish_off",
    "scheduled_override",
)
COMPONENT_CONTROLS = ("reaction_only", "growth_only", "transport_only")
RAW_CASES = ("first_molecule_negative", "second_molecule_negative")
DEPENDENCIES = ("missing_molecule_state", "intracellular_field", "radius_mismatch", "GRN_owner")


def molecule(name):
    values = [0.8, 1.1, 0.9] if name == "X" else [0.3, 0.4, 0.5]
    owner = [0, 0, 0, 1, 1, 1, 2, 2, 2]
    return dict(
        name=name,
        parameters=dict(
            z=0.0,
            Dm=1e-14,
            Do=1e-10,
            Dgj=2e-13,
            c_bound=0.6,
            TJ_factor=1.0,
            ignoreTJ=True,
            ignoreGJ=False,
            update_intra_conc=False,
            transmem=False,
            modify_time_factor=1.0,
            Mu_mem=0.0,
            u_mt=0.0,
            scale_factor=1.0,
            active_pumping=False,
            ion_channel_gating=False,
            change_bounds=False,
            cell_clamp=False,
        ),
        growth=dict(
            enabled=name == "X",
            production_rate_mM_s=0.03 if name == "X" else 0.0,
            decay_rate_per_s=0.02 if name == "X" else 0.0,
            decay_max_per_s=0.01 if name == "X" else 0.0,
            scale_factor=0.7,
        ),
        initial=dict(
            c_cells=values,
            cc_at_mem=[values[i] * (0.97 + 0.005 * j) for j, i in enumerate(owner)],
            c_env=[0.6 if name == "X" else 0.2] * 9,
            flux_intra=[(j - 4) * 1e-17 for j in range(9)],
        ),
        provenance="Manufactured complete configured molecular state; no native initialization or biological claim",
    )


def fixture(case="coupled"):
    if case not in CASES:
        raise ValueError("Choose a frozen real-molecule case")
    prior = {
        "late_channel_coupled": "channel_coupled",
        "publish_off": "publish_off",
        "scheduled_override": "scheduled_override",
    }.get(case, "active")
    data = feedback_fixture(prior)
    definition = data["channel_definition"]
    definition["kind"] = "cells.betse_normal_molecule_join_inputs@1"
    definition["provenance"] = (
        "Conditional real-molecule chemistry/mover join on the supplied normal prefix"
    )
    network = definition["network"]
    network["owner"] = "molecules"
    network["provenance"] = (
        "Two actual Molecule instances and original generated growth/reaction equations; original mover executes even at D0"
    )
    network["molecules"] = [molecule("X"), molecule("Y")]
    network["radius_m"] = copy.deepcopy(data["voltage_definition"]["geometry"]["radius_m"])
    network["rho_channel"] = [1.0] * 9
    network["reactions"] = [
        dict(
            name="X_to_Y",
            **{
                "reaction zone": "cell",
                "reactants": ["X"],
                "products": ["Y"],
                "reactant multipliers": [1.0],
                "product multipliers": [1.0],
                "Km reactants": [0.4],
                "Km products": [0.7],
                "max rate": 0.025,
                "standard free energy": "None",
            },
        )
    ]
    # The existing feedback scope remains ion-driven; these are real coupled
    # chemistry cases rather than newly claimed GRN owner-dispatch histories.
    if case in COMPONENT_CONTROLS:
        network["modulators"] = []
    if case in ("reaction_only", "transport_only"):
        for row in network["molecules"]:
            row["growth"]["enabled"] = False
    if case in ("growth_only", "transport_only"):
        network["reactions"] = []
    if case in ("reaction_only", "growth_only"):
        for row in network["molecules"]:
            row["parameters"].update(Dm=0.0, Dgj=0.0, ignoreGJ=True)
    if case == "charged":
        for row in network["molecules"]:
            row["parameters"].update(z=1.0, scale_factor=1e-6)
    if case in ("nonuniform_bath", "zero_Dm_GJ"):
        for row in network["molecules"]:
            row["initial"]["c_env"] = [
                value * (0.92 + 0.02 * j) for j, value in enumerate(row["initial"]["c_env"])
            ]
    if case == "closed_mask":
        data["ion_definition"]["parameters"]["cluster_open"] = False
    if case == "zero_Dm_GJ":
        for row in network["molecules"]:
            row["parameters"]["Dm"] = 0.0
    if case == "ignore_GJ":
        for row in network["molecules"]:
            row["parameters"]["ignoreGJ"] = True
    if case == "time_dilation":
        network["molecules"][0]["parameters"]["modify_time_factor"] = 2.0
    if case == "temperature_split":
        for j, drive in enumerate(data["drives"]):
            drive["material"]["runtime_temperature_K"] = 281.0 + j
    if case == "reverse_order":
        network["molecules"].reverse()
    data["molecule_case_id"] = case
    data["case_role"] = "component_control" if case in COMPONENT_CONTROLS else "new_coupled_case"
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a separate source partial-failure case")
    data = fixture("charged")
    index = 0 if case == "first_molecule_negative" else 1
    growth = data["channel_definition"]["network"]["molecules"][index]["growth"]
    growth.update(enabled=True, production_rate_mM_s=0.0, decay_rate_per_s=1e6)
    data["drives"] = data["drives"][:1]
    data["molecule_case_id"] = case
    data["case_role"] = "raw_partial_failure"
    return data
