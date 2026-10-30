"""Explicit active gate initialization, ion order and per-call block packets."""

from validation.betse.betse_normal_voltage_fixtures import fixture as voltage_fixture

CASE_MOVING_COUNTS = {
    "standard": 3,
    "polarized": 3,
    "reversed": 3,
    "one_moving": 1,
    "all_moving": 4,
    "no_moving": 0,
    "partial_block": 3,
    "zero_restore": 3,
    "cached_init": 3,
    "zero_weights": 3,
    "over_one": 3,
    "nonce_neutral": 3,
}
CASES = (
    "standard",
    "polarized",
    "reversed",
    "one_moving",
    "all_moving",
    "no_moving",
    "partial_block",
    "zero_restore",
    "cached_init",
    "zero_weights",
    "over_one",
    "nonce_neutral",
)


def fixture(case="standard"):
    if case not in CASE_MOVING_COUNTS:
        raise ValueError("Require a declared active gate join case")
    raw = voltage_fixture(
        "polarized"
        if case == "polarized"
        else "moving_reversed"
        if case == "reversed"
        else "simple"
    )
    ions = raw["ion_definition"]["ions"]
    if case == "one_moving":
        ions["moving_ids"] = ["Na"]
    elif case == "all_moving":
        ions["moving_ids"] = list(ions["ids"])
    elif case == "no_moving":
        ions["moving_ids"] = []
    if case == "zero_weights":
        raw["ion_definition"]["geometry"]["gap_weights"] = [0.0] * 9
    raw["initial"]["gap_open"] = [1.05 if case == "over_one" else 0.6 + 0.01 * j for j in range(9)]
    if case == "cached_init":
        raw["initial"]["junction_voltage_V"] = [0.08 - 0.002 * j for j in range(9)]
    raw["gate_definition"] = dict(
        kind="cells.betse_normal_gated_join_inputs@1",
        provenance="Explicit cached class initialization; no conditioning or availability law",
        threshold_mV=15.0,
        minimum=0.3 if case == "over_one" else 0.1,
    )
    raw["initial_gate_block"] = [0.8] * 9
    if case == "nonce_neutral":
        raw["initial"]["voltage_V"] = [0.0] * 9
        ions["valence"][1] = 0.0
        raw["current_definition"]["ions"]["valence"][1] = 0.0
        for j in range(3):
            raw["initial"]["cell_mol_m3"][2][j] = raw["initial"]["cell_mol_m3"][0][j] - 4.0
        owner = raw["ion_definition"]["geometry"]["owner"]
        raw["initial"]["membrane_mol_m3"] = [
            [row[a] for a in owner] for row in raw["initial"]["cell_mol_m3"]
        ]
    for index, forcing in enumerate(raw["drives"]):
        block = (
            0.5
            if case == "partial_block"
            else (0.0, 0.3, 1.0)[index]
            if case == "zero_restore"
            else 1.4
            if case == "over_one"
            else 1.0
        )
        forcing["material"]["junction_block"] = [block] * 9
    return raw
