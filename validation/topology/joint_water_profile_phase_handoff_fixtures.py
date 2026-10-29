"""Short evolved full56 water/repair checkpoints for explicit epoch contracts."""

from copy import deepcopy

from validation.topology import joint_water_profile_interventions_fixtures as profiles

FAMILIES = profiles.FAMILIES
CASES = ("changed-controls", "empty-events", "close-reopen", "replayed-controls")
INIT_END = SIM_END = 0.25e-6
INIT_DT = 0.015625e-6
SIM_DT = 0.0078125e-6


def inputs(family):
    result = profiles.inputs(family, "INIT", padded=True)
    raw = result["definition"]
    experiment = raw["experiment"]
    experiment.update(end_time=INIT_END, observation_times=[0.0, 0.0625e-6, 0.125e-6, INIT_END])
    for name, rows in experiment.items():
        if name.endswith("_controls"):
            for j, row in enumerate(rows):
                key = "controls" if "controls" in row else "schedule"
                first = deepcopy(row[key][0])
                row[key] = [first]
                if j == 0:
                    second = profiles.native._scaled(first, 0.8)
                    second["time"] = 0.125e-6
                    row[key].append(second)
    raw["execution"].update(dt=INIT_DT, max_steps=256)
    for event in result["interventions"]:
        event.update(on_s=0.0625e-6, off_s=0.1875e-6, change_s=0.0625e-6)
    return result


def definitions(prepared, case="changed-controls"):
    if case not in CASES:
        raise ValueError(case)
    source, target = deepcopy(prepared), deepcopy(prepared)
    source["model"]["phase"] = "INIT"
    target["model"]["phase"] = "SIM"
    target["execution"]["dt"] = SIM_DT
    target["experiment"]["observation_times"] = [
        v * 1e-6 for v in (0, 0.03125, 0.0625, 0.09375, 0.125, 0.1875, 0.21875, 0.25)
    ]
    if case != "replayed-controls":
        for name, rows in target["experiment"].items():
            if name.endswith("_controls"):
                for row in rows:
                    key = "controls" if "controls" in row else "schedule"
                    first = deepcopy(row[key][0])
                    row[key] = []
                    for time, scale in ((0.0, 0.45), (0.125e-6, 0.0), (0.1875e-6, 0.8)):
                        change = profiles.native._scaled(first, scale)
                        change["time"] = time
                        row[key].append(change)
    carrier = target["experiment"]["membrane_controls"][0]["schedule"]
    for time in target["experiment"]["observation_times"]:
        if time == SIM_END or any(v["time"] == time for v in carrier):
            continue
        held = deepcopy(next(v for v in reversed(carrier) if v["time"] <= time))
        held["time"] = time
        carrier.append(held)
        carrier.sort(key=lambda v: v["time"])
    if case == "empty-events":
        target["model"]["interventions"] = []
        target["execution"].update(intervention_capacity=0, intervention_target_capacity=0)
    elif case == "close-reopen":
        event = next(e for e in target["model"]["interventions"] if e["kind"] == "Na_mem")
        event.update(
            profiles=["Selected"],
            amplitude=-2.0,
            dynamic_factor=1.0,
            spatial=None,
            source_function="None",
        )
        target["model"]["interventions"] = [event]
    return source, target
