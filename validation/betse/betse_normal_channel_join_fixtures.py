"""Bounded late-population cases with explicit clocks, targets and publication."""

from validation.betse.betse_normal_pump_join_fixtures import fixture as pump_fixture

CASES = (
    "standard",
    "pop_reversed",
    "duplicate_targets",
    "empty_targets",
    "blocked_restore",
    "init_skip_restore",
    "publish_off",
    "signed_modulator",
    "temperature_split",
    "stationary_na",
    "stale_membrane",
    "no_channels",
)
CASE_MOVING_COUNTS = {name: 2 if name == "stationary_na" else 3 for name in CASES}


def fixture(case="standard"):
    if case not in CASES:
        raise ValueError("Require declared late-channel case")
    raw = pump_fixture(
        "na_stationary"
        if case == "stationary_na"
        else "temperature_split"
        if case == "temperature_split"
        else "forward"
    )
    raw["channel_definition"] = dict(
        kind="cells.betse_normal_channel_join_inputs@1",
        provenance="Ordered explicit profile targets; original network modulator input seam",
        channels=[
            dict(
                id=name.lower(),
                class_name=name,
                targets=list(range(9)),
                maxDm_m2_s=(index + 1) * 1e-15,
                init_active=index % 2 == 0,
            )
            for index, name in enumerate(("Nav1p6", "Kv1p5", "Kv3p2", "ClLeak"))
        ],
    )
    rows = raw["channel_definition"]["channels"]
    if case == "pop_reversed":
        rows.reverse()
    if case == "duplicate_targets":
        for row in rows:
            row["targets"] = [8, 2, 8, 0, 4]
    if case == "empty_targets":
        for row in rows:
            row["targets"] = []
    if case == "no_channels":
        rows.clear()
    if case == "stale_membrane":
        raw["initial"]["membrane_mol_m3"] = [
            [x * 1.003 for x in row] for row in raw["initial"]["membrane_mol_m3"]
        ]
    for index, drive in enumerate(raw["drives"]):
        drive["channels"] = dict(
            phase_kind="INIT" if case == "init_skip_restore" and index == 0 else "SIM",
            substances_affect_charge=case != "publish_off",
            modulators={
                row["id"]: [
                    (0.0, 0.4, 1.0)[index]
                    if case == "blocked_restore"
                    else (-0.15 if j % 2 else 0.6)
                    if case == "signed_modulator"
                    else 0.6 + 0.03 * j
                    for j in range(9)
                ]
                for row in rows
            },
        )
    return raw
