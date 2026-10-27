"""Synthetic moving pump/channel/calcium/injury cases; no fitted repair rates."""

from validation.tissue import surface_mobile_pump_fixtures as pumps
from validation.tissue import surface_mobile_repair_fixtures as prior

ARMS = ("mobile", "immobile", "inhibited", "empty", "no_turnover", "reverse", "release")
TRAJECTORIES = ("mobile", "immobile", "reverse", "release")


def definition(arm="mobile", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(
        "release" if arm == "release" else "mobile", backend=backend, padded=padded
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_repair@3"
    m["mobile_pumps"] = pumps.definition(arm)["model"]["mobile_pumps"]
    for k, pop in enumerate(m["mobile_pumps"]):
        pop["initial_amount_fmol"] = {
            patch["id"]: (
                0.0
                if arm == "empty" or (k == 1 and patch["inside"] == "cell_1")
                else patch["area_m2"] * 1e12 * 1e-5 * (2.0 if j % 2 == 0 else 0.4)
            )
            for j, patch in enumerate(m["ionic"]["membranes"])
        }
    e["mobile_pump_controls"] = []
    for pop in m["mobile_pumps"]:
        for j, patch in enumerate(m["ionic"]["membranes"]):
            schedule = [
                dict(time=0.0, availability=0.0 if arm in ("release", "inhibited") else 1.0)
            ]
            if arm == "release":
                schedule += [
                    dict(time=10.1e-6, availability=0.8 if j % 2 else 0.6),
                    dict(time=20.1e-6, availability=0.0),
                ]
            e["mobile_pump_controls"].append(
                dict(pump_id=pop["id"], membrane_id=patch["id"], schedule=schedule)
            )
    if arm == "release":
        e["observation_times"] = sorted({*e["observation_times"], 10.1e-6, 20.1e-6})
    x["pump_population_capacity"] = 2 + int(padded)
    return raw
