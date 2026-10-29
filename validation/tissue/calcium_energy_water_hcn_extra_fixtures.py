"""Full HCN-extra catalog on declared finite-fuel/chemical/water inputs."""

from copy import deepcopy

from validation.tissue import calcium_energy_water_fixtures as prior
from validation.tissue import hcn_extra_catalog_fixtures as hcn

MODEL_ID = "resolved_calcium_energy_water@2"
ARMS = (*prior.ARMS, "leak_only", "camp_only", "legacy53")
ADDED_IDS = {"hcn_extra_0", "hcn_extra_1", "hcn_extra_2"}


def definition(arm="open", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(arm if arm in prior.ARMS else "open", backend=backend, padded=padded)
    model, experiment = raw["model"], raw["experiment"]
    model["id"] = MODEL_ID
    ionic = model["ionic"]
    ionic["id"] = "resolved_tissue@12"
    source = hcn.definition("energy", backend=backend, padded=False)
    wanted = set(ADDED_IDS)
    if arm in ("empty", "legacy53"):
        wanted.clear()
    elif arm in ("instant_only", "leak_only"):
        wanted = {"hcn_extra_0"}
    elif arm in ("dynamic_only", "camp_only"):
        wanted = {"hcn_extra_1", "hcn_extra_2"}
    ionic["channels"].extend(
        deepcopy(c) for c in source["model"]["ionic"]["channels"] if c["id"] in wanted
    )
    for row in source["experiment"]["channel_controls"]:
        if row["channel_id"] in wanted:
            value = deepcopy(row)
            if arm == "blocked":
                for change in value["schedule"]:
                    change["availability"] = 0.0
            experiment["channel_controls"].append(value)
    if arm in ("leak_only", "camp_only"):
        ionic["channels"] = [c for c in ionic["channels"] if c["id"] in wanted]
        experiment["channel_controls"] = [
            c for c in experiment["channel_controls"] if c["channel_id"] in wanted
        ]
    if arm == "reordered":
        ionic["channels"].reverse()
        experiment["channel_controls"].reverse()
    raw["execution"]["channel_capacity"] = len(ionic["channels"]) + int(padded)
    return raw


def compact_probe(*, backend="cpu", padded=False):
    raw = definition("release", backend=backend, padded=padded)
    experiment, dt = raw["experiment"], raw["execution"]["dt"]
    for row in experiment["channel_controls"]:
        if row["channel_id"] in ("hcn_extra_0", "hcn_extra_2"):
            row["schedule"] = [
                dict(time=t * dt, availability=a) for t, a in ((0, 0.8), (10, 0), (30, 0.6))
            ]
    return all_observation_boundaries(raw)


def all_observation_boundaries(raw):
    """Declare every held-control boundary as an accepted observation."""
    result = deepcopy(raw)
    experiment = result["experiment"]
    times = {*experiment["observation_times"], 0.0, experiment["end_time"]}
    for name, groups in experiment.items():
        if name.endswith("_controls"):
            for group in groups:
                times.update(
                    c["time"] for c in group["controls" if "controls" in group else "schedule"]
                )
    experiment["observation_times"] = sorted(times)
    return result
