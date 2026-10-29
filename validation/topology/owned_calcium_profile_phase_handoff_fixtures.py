"""Declared INIT/SIM phases on the two complete owners and identical geometry."""

from copy import deepcopy

from validation.topology import owned_calcium_profile_interventions_fixtures as profiles

FAMILIES = profiles.FAMILIES
CASES = ("changed-controls", "empty-events", "close-reopen", "replayed-controls")
INIT_END = SIM_END = 4e-6
DT = 0.015625e-6


def inputs(family):
    raw = profiles.inputs(family, "INIT")
    raw["definition"]["execution"]["dt"] = DT
    # A declared manufactured coefficient panel gives measurable transient
    # transport error at pulse ramps without changing any parent equation.
    for profile in (raw["default"], *raw["profiles"]):
        profile["diffusivity_m2_s"] = [100 * v for v in profile["diffusivity_m2_s"]]
    experiment = raw["definition"]["experiment"]
    experiment["observation_times"] = sorted(
        {
            *experiment["observation_times"],
            *(
                v["time"]
                for name, rows in experiment.items()
                if name.endswith("_controls")
                for row in rows
                for v in row["controls" if "controls" in row else "schedule"]
            ),
        }
    )
    return raw


def definitions(prepared, case="changed-controls"):
    if case not in CASES:
        raise ValueError(case)
    source, target = deepcopy(prepared), deepcopy(prepared)
    source["model"]["phase"] = "INIT"
    target["model"]["phase"] = "SIM"
    observations = [*source["experiment"]["observation_times"], 0.75e-6, 1.125e-6]
    observations = sorted(set(observations))
    target["experiment"]["observation_times"] = observations
    if case != "replayed-controls":
        for name, rows in target["experiment"].items():
            if not name.endswith("_controls"):
                continue
            for row in rows:
                key = "controls" if "controls" in row else "schedule"
                first = deepcopy(row[key][0])
                values = []
                for time, scale in ((0.0, 0.45), (1.5e-6, 0.0), (2.5e-6, 0.8)):
                    value = profiles._scaled(first, scale)
                    value["time"] = time
                    values.append(value)
                row[key] = values
    # Preserve exact transient observation boundaries with explicit neutral
    # knots. These knots change neither the held physical controls nor dt.
    carrier = target["experiment"]["membrane_controls"][0]["schedule"]
    for time in observations:
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
        event = next(v for v in target["model"]["interventions"] if v["kind"] == "Na_mem")
        event.update(
            profiles=["Selected"],
            amplitude=-2.0,
            dynamic_factor=1.0,
            spatial=None,
            source_function="None",
        )
        target["model"]["interventions"] = [event]
    return source, target
