"""Bounded endogenous control feedback, with explicitly empty chemistry."""

import copy

from validation.betse.betse_normal_calcium_join_fixtures import fixture as calcium_fixture

CASES = (
    "active",
    "GJ_zero",
    "NaK_zero",
    "ordered_writes",
    "env_sampling",
    "grn_owner",
    "scheduled_override",
    "publish_off",
    "channel_coupled",
    "init_phase",
)


def fixture(case="active"):
    if case not in CASES:
        raise ValueError("Choose a declared native network-feedback case")
    data = calcium_fixture(
        "channel_coupled" if case in ("channel_coupled", "init_phase") else "active"
    )
    definition = data["channel_definition"]
    definition["kind"] = "cells.betse_normal_network_join_inputs@1"
    mods = [
        {
            "name": "gj_control",
            "target": "GJ",
            "max effect": 0.8,
            "activators": ["Ca"],
            "activator Km": [0.0002],
            "activator n": [2.0],
        },
        {
            "name": "nak_control",
            "target": "Na/K-ATPase",
            "max effect": 1.2,
            "inhibitors": ["Na"],
            "inhibitor Km": [20.0],
            "inhibitor n": [2.0],
        },
    ]
    if case == "GJ_zero":
        mods[0]["max effect"] = 0.0
    if case == "NaK_zero":
        mods[1]["max effect"] = 0.0
    if case == "ordered_writes":
        mods += [
            {"name": "gj_last", "target": "GJ", "max effect": 1.4},
            {"name": "nak_last", "target": "Na/K-ATPase", "max effect": 0.6},
        ]
    if case == "env_sampling":
        mods[0] = {
            "name": "gj_env",
            "target": "GJ",
            "max effect": 0.9,
            "activators": ["K"],
            "activator Km": [50.0],
            "activator n": [1.5],
            "activator zone": ["env"],
        }
        data["initial"]["bath_mol_m3"] = [
            [value * (0.9 + 0.03 * j) for j, value in enumerate(row)]
            for row in data["initial"]["bath_mol_m3"]
        ]
    definition["network"] = dict(
        owner="grn" if case == "grn_owner" else "molecules",
        provenance="One native network core; endogenous GJ/NaK feedback; no molecule chemistry",
        reactions=[],
        modulators=mods,
        membrane_to_environment=list(data["voltage_definition"]["grid"]["membrane_to_grid"]),
        initial_controls=dict(
            gj_block=list(data["drives"][0]["material"]["junction_block"]),
            NaKATP_block=list(data["drives"][0]["pump"]["block"]),
        ),
    )
    for index, drive in enumerate(data["drives"]):
        drive["scheduled_controls"] = None
        drive["scheduled_control_provenance"] = None
        if case == "scheduled_override" and index == 1:
            drive["scheduled_controls"] = dict(gj_block=[0.3] * 9, NaKATP_block=[0.7] * 9)
            drive["scheduled_control_provenance"] = (
                "Supplied external control write; no native event execution claim"
            )
        if case == "publish_off":
            drive["channels"]["substances_affect_charge"] = False
        if case == "init_phase" and index == 0:
            drive["channels"]["phase_kind"] = "INIT"
    if case == "init_phase":
        definition["channels"][0]["init_active"] = False
    return data


def projection_fixture():
    data = fixture()
    data["channel_definition"]["network"]["modulators"] = []
    for drive in data["drives"]:
        drive["scheduled_controls"] = dict(
            gj_block=list(drive["material"]["junction_block"]),
            NaKATP_block=list(drive["pump"]["block"]),
        )
        drive["scheduled_control_provenance"] = "Explicit original caller controls for projection"
    return data


def raw_reaction_fixture():
    """Preserve the source-audited empty-growth/nonempty-reaction stack blocker."""
    data = copy.deepcopy(fixture())
    data["drives"] = data["drives"][:1]
    data["channel_definition"]["network"]["reactions"] = [
        {
            "name": "cation_pair",
            "reaction zone": "cell",
            "reactants": ["Na"],
            "reactant multipliers": [2.0],
            "Km reactants": [10.0],
            "products": ["Ca"],
            "product multipliers": [1.0],
            "Km products": [0.001],
            "max rate": 0.01,
            "standard free energy": "None",
        }
    ]
    return data
