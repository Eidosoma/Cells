"""Disjoint mitochondrial owners on the qualified three-cell cut geometry.

Every mitochondrial row copies the prior continuous45 fixture's actual volume,
area, capacitance, thickness, concentrations and diffusivities; cell_2 uses its
first row. No transport rate is accelerated. Cytosol volumes remain those of
the frozen cut fixture and exclude both internal organelles.
"""

from copy import deepcopy

from validation.tissue import calcium_energy_mitochondria_fixtures as mitochondrial
from validation.tissue import calcium_energy_transport_excision_fixtures as prior

DT, CUT_TIME, END_TIME = prior.DT, prior.CUT_TIME, prior.END_TIME
ARMS = (*prior.ARMS, "mitochondria_blocked", "zero_diffusion", "mitochondria_reverse")


def definition(arm="open", *, catalog="compact", backend="cpu", padded=False):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(
        arm if arm in prior.ARMS else "open", catalog=catalog, backend=backend, padded=padded
    )
    source = mitochondrial.definition("active", padded=False)["model"]["mitochondria"]
    group = deepcopy(source)
    group["compartments"] = []
    m, e = raw["model"], raw["experiment"]
    m["id"] = "resolved_calcium_energy_mitochondria@1"
    e["mitochondria_controls"] = []
    for i, cell in enumerate(sorted(m["ionic"]["cells"], key=lambda v: v["id"])):
        row = deepcopy(source["compartments"][i % len(source["compartments"])])
        row.update(id="mitochondrion_" + cell["id"], cell_id=cell["id"])
        if arm == "zero_diffusion":
            row["diffusivity_m2_per_s"] = {s: 0.0 for s in row["diffusivity_m2_per_s"]}
        if arm == "mitochondria_reverse":
            row["initial_voltage_V"] = 0.08
        group["compartments"].append(row)
        level = 0.0 if arm == "mitochondria_blocked" else 0.8
        schedule = [dict(time=0.0, availability=level)]
        if cell["id"] == "cell_0":
            schedule += [
                dict(time=12.7e-6, availability=0.0),
                dict(time=71.9e-6, availability=0.0 if not level else 0.6),
            ]
        if cell["id"] == "cell_1":
            schedule += [
                dict(time=43.1e-6, availability=0.0),
                dict(time=109.7e-6, availability=0.0 if not level else 0.7),
            ]
        e["mitochondria_controls"].append(dict(mitochondrion_id=row["id"], schedule=schedule))
    if arm == "reordered":
        group["compartments"].reverse()
        e["mitochondria_controls"].reverse()
    m["mitochondria"] = group
    times = {v["time"] for row in e["mitochondria_controls"] for v in row["schedule"]}
    e["observation_times"] = sorted(set(e["observation_times"]) | times)
    return raw


def cut_plan(arm="open"):
    if arm not in ARMS:
        raise ValueError(arm)
    return prior.cut_plan(arm if arm in prior.ARMS else "open")
