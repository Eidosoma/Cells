"""Complete moving-volume/fuel/repair inputs with both native schedules.

The original 50-us controls, water anchors, molecular stores and live-pool pump
ownership are retained. These are manufactured component cases, not new
biological observations or qualified full trajectories.
"""

from copy import deepcopy

from validation.transport import active_profile_barrier_interventions_fixtures as ionic
from validation.transport import environment_barrier_composition_fixtures as exterior

FAMILIES = ("water", "repair")
CASES = ionic.CASES
MODEL_IDS = {
    "water": "resolved_calcium_energy_water_profile_barriers@1",
    "repair": "resolved_calcium_energy_water_repair_profile_barriers@1",
}
PARENT_IDS = {
    "water": "resolved_calcium_energy_water@2",
    "repair": "resolved_calcium_energy_water_repair@2",
}
PHYSICAL_FIELDS = {"water": 43, "repair": 48}
DT_S = 62.5e-9


def inputs(family="water", case="joint", *, permuted=False, padded=True):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    values = ionic.inputs(case, permuted=permuted, padded=padded)
    full = exterior.request(
        family,
        "zero_endpoint" if case == "closed" else "asymmetric_modulators",
        permuted=permuted,
        padded=padded,
    )
    raw = full["definition"]
    assert raw["model"]["id"] == PARENT_IDS[family]
    leaf = raw["model"]["ionic"]
    assert leaf["id"] == "resolved_tissue@12" and len(leaf["channels"]) == 63
    for key, layout_key in (
        ("cells", "cell_ids"),
        ("membranes", "membrane_ids"),
        ("extracellular", "environment_ids"),
    ):
        assert {row["id"] for row in leaf[key]} == set(
            values["profile_request"]["geometry"]["layout"][layout_key]
        )
    if case == "closed":
        full["relative_TJ"]["Na"] = 0.0
        for row in leaf["membranes"]:
            row["permeability_m_per_s"]["Na"] = 0.0
    raw["execution"].update(dt=DT_S, max_steps=4096, jit=False)
    experiment = raw["experiment"]
    times = {0.0, experiment["end_time"], *experiment["observation_times"]}
    for key, groups in experiment.items():
        if key.endswith("_controls"):
            times.update(
                point["time"]
                for group in groups
                for point in group.get("controls", group.get("schedule", []))
            )
    for event in (
        *values["membrane_interventions"],
        *((values["barrier_intervention"],) if values["barrier_intervention"] else ()),
    ):
        times.update((event["on_s"], (event["on_s"] + event["off_s"]) / 2, event["off_s"]))
    experiment["observation_times"] = sorted(times)
    carrier = experiment["membrane_controls"][0]["schedule"]
    before = deepcopy(carrier)
    carrier[:] = [
        dict(next(row for row in reversed(before) if row["time"] <= time), time=time)
        for time in sorted(times | {row["time"] for row in before})
    ]
    # This replaces the complete source definition only. Maintained ionic pump
    # projections are never copied into the full finite-fuel owner.
    values["profile_request"]["definition"] = deepcopy(raw)
    values["barrier_template"] = deepcopy(full)
    return values


def preparation_request(values, profile_preparation):
    result = ionic.preparation_request(values, profile_preparation)
    result["kind"] = "cells.joint_water_profile_barrier_preparation_request@1"
    return result


def definition(values, prepared):
    result = ionic.definition(values, prepared)
    family = next(key for key in FAMILIES if prepared.definition["model"]["id"] == PARENT_IDS[key])
    result["model"]["id"] = MODEL_IDS[family]
    return result
