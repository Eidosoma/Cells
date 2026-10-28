"""Synthetic salt/water/finite-energy compositions for short CPU checks."""

from copy import deepcopy

from validation.tissue import surface_cotransport_fixtures as cotransport
from validation.tissue import surface_energy_water_fixtures as water

DT, END_TIME, CHECKPOINT_TIME = water.DT, water.END_TIME, water.CHECKPOINT_TIME
ARMS = (*cotransport.ARMS, "sealed_water")
STEPS = water.STEPS


def definition(arm="coupled", *, backend="cpu", padded=False, dt=DT):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = cotransport.definition(
        "coupled" if arm == "sealed_water" else arm, backend=backend, padded=padded, dt=dt
    )
    example = water.definition("release" if arm == "release" else "coupled")
    m, e = raw["model"], raw["experiment"]
    m.update(
        id="resolved_cotransport_water@1",
        energy_osmotic_coupling=example["model"]["energy_osmotic_coupling"],
        water_compartments=deepcopy(example["model"]["water_compartments"]),
        water_membranes=[
            dict(membrane_id=p["id"], hydraulic_permeability_m_per_Pa_s=1e-10)
            for p in m["membranes"]
        ],
    )
    schedule = deepcopy(example["experiment"]["water_controls"][0]["schedule"])
    if arm == "sealed_water":
        schedule = [dict(time=0.0, availability=0.0)]
    e["water_controls"] = [
        dict(membrane_id=p["id"], schedule=deepcopy(schedule)) for p in m["membranes"]
    ]
    e["observation_times"] = sorted(set(e["observation_times"]) | {c["time"] for c in schedule})
    return raw


normalized = water.normalized
