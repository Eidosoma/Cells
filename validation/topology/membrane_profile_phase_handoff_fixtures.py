"""Independent declarations for evolved INIT and a separate SIM experiment."""

from copy import deepcopy

CASES = ("continued-controls", "changed-controls", "empty-SIM", "safe-negative-SIM")


def definitions(prepared, case="continued-controls"):
    source = deepcopy(prepared)
    target = deepcopy(prepared)
    source["model"]["phase"] = "INIT"
    target["model"]["phase"] = "SIM"
    for kind in ("membrane_controls", "junction_controls"):
        for row in target["experiment"][kind]:
            initial = row["schedule"][0]["availability"]
            row["schedule"] = [
                dict(
                    time=0.0, availability=initial * (0.35 if case == "changed-controls" else 0.6)
                ),
                dict(time=5e-6, availability=initial * 0.8),
            ]
    if case == "empty-SIM":
        target["model"]["interventions"] = []
        target["execution"].update(intervention_capacity=0, intervention_target_capacity=0)
    if case == "safe-negative-SIM":
        for row in target["model"]["interventions"]:
            row["amplitude"] = -0.2
    return source, target


def public_definitions(prepared):
    source, target = definitions(prepared)
    source["model"]["interventions"] = []
    source["execution"].update(intervention_capacity=0, intervention_target_capacity=0)
    source["experiment"].update(end_time=0.25e-6, observation_times=[0.0, 0.25e-6])
    for kind in ("membrane_controls", "junction_controls"):
        for row in source["experiment"][kind]:
            row["schedule"] = row["schedule"][:1]
        for row in target["experiment"][kind]:
            row["schedule"] = row["schedule"][:1]
    event = next(v for v in target["model"]["interventions"] if v["kind"] == "Na_mem")
    event.update(
        profiles=["Selected"],
        spatial=None,
        source_function="None",
        on_s=0.5e-9,
        off_s=1.5e-9,
        change_s=8e-9,
    )
    target["model"]["interventions"] = [event]
    p = target["model"]["profile_preparation"]["provenance"]
    count = len(p["binding"]["targets"]["Selected"]["membranes"])
    target["execution"].update(
        dt=1e-9, max_steps=4, intervention_capacity=1, intervention_target_capacity=count
    )
    target["experiment"].update(end_time=2e-9, observation_times=[0.0, 1e-9, 2e-9])
    return source, target
