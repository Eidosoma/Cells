"""Explicit SIM declarations on an unchanged prepared active physical parent."""

from copy import deepcopy

from validation.topology import surface_active_profile_interventions_fixtures as active

CASES = ("changed-controls", "empty-events", "close-reopen", "replayed-controls")
INIT_END = 8e-6
SIM_END = 8e-6
DT = 0.0625e-6


def inputs():
    return active.inputs("INIT", catalog="full")


def definitions(prepared, case="changed-controls"):
    if case not in CASES:
        raise ValueError(case)
    source, target = deepcopy(prepared), deepcopy(prepared)
    source["model"]["phase"] = "INIT"
    target["model"]["phase"] = "SIM"
    if case != "replayed-controls":
        for kind in ("membrane", "junction", "channel", "pump"):
            for row in target["experiment"][kind + "_controls"]:
                initial = row["schedule"][0]["availability"]
                schedule = [
                    dict(time=0.0, availability=0.45 * initial),
                    dict(time=3e-6, availability=0.0),
                    dict(time=5e-6, availability=0.8 * initial),
                ]
                # Preserve exact requested observation boundaries after replacing
                # the old controls. These explicit no-op knots change no held
                # availability, physical rate, observation time or tolerance.
                knots = sorted(
                    {*target["experiment"]["observation_times"], *(v["time"] for v in schedule)}
                )
                row["schedule"] = [
                    dict(
                        time=time,
                        availability=next(
                            v["availability"] for v in reversed(schedule) if v["time"] <= time
                        ),
                    )
                    for time in knots
                ]
    if case == "empty-events":
        target["model"]["interventions"] = []
        target["execution"].update(intervention_capacity=0, intervention_target_capacity=0)
    elif case == "close-reopen":
        event = next(v for v in target["model"]["interventions"] if v["kind"] == "Na_mem")
        event.update(
            profiles=["Selected"],
            spatial=None,
            source_function="None",
            amplitude=-2.0,
            dynamic_factor=1.0,
            on_s=1e-6,
            off_s=7e-6,
        )
        target["model"]["interventions"] = [event]
    return source, target
