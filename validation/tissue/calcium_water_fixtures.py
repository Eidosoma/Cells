"""53-law owned chemistry/water with fixed ER and additional inert osmolytes."""

from copy import deepcopy

from validation.tissue import morris_lecar_catalog_fixtures as calcium
from validation.tissue import morris_lecar_water_fixtures as water

MODEL_ID = "resolved_calcium_water@1"
ARMS = (*calcium.ARMS, "sealed", "release")


def definition(arm="open", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = calcium.definition(
        "calcium", arm if arm in calcium.ARMS else "open", backend=backend, padded=padded
    )
    w = water.definition(arm if arm in water.ARMS else "open", backend=backend, padded=padded)
    m, e = raw["model"], raw["experiment"]
    m.update(
        id=MODEL_ID,
        chemical_osmotic_coupling="ideal_all_cytosol_species_fixed_er@1",
        water_compartments=deepcopy(w["model"]["water_compartments"]),
        water_membranes=deepcopy(w["model"]["water_membranes"]),
    )
    e["water_controls"] = deepcopy(w["experiment"]["water_controls"])
    # The catalog helper pads channel slots only. This composition exercises
    # every material, geometric and chemical padding axis explicitly.
    for key in (
        "capacity",
        "extracellular_capacity",
        "membrane_capacity",
        "edge_capacity",
        "face_capacity",
        "channel_capacity",
    ):
        raw["execution"][key] = w["execution"][key]
    raw["execution"]["chemical_capacity"] = len(m["stores"][0]["model"]["compartments"]) + int(
        padded
    )
    raw["execution"]["reaction_capacity"] = len(m["stores"][0]["model"]["reactions"]) + int(padded)
    dt = raw["execution"]["dt"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 15, 20, 25, 30, 35, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [c for c in row[key] if c["time"] <= e["end_time"]]
    if arm == "release":
        for row in e["channel_controls"]:
            if row["channel_id"] in ("morris_lecar_0", "morris_lecar_5"):
                first = 10 if row["channel_id"] == "morris_lecar_0" else 20
                row["schedule"].extend(
                    [dict(time=first * dt, availability=0.0), dict(time=30 * dt, availability=0.6)]
                )
    return raw


def compact_probe(*, backend="cpu", padded=False):
    return definition("release", backend=backend, padded=padded)


def assembly_definition(*, backend="cpu"):
    raw = calcium.assembly_definition("calcium", backend=backend)
    raw["ionic"] = definition(backend=backend)
    end = raw["ionic"]["experiment"]["end_time"]
    raw["window_ticks"] = 8
    for row in raw["pools"]:
        row["pool"].update(end_time_s=end, k_off_s_inv=40000.0)
    return raw
