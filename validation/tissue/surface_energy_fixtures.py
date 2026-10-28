"""Manufactured finite-fuel demand/supply cases; no fitted energetic rates."""

import json
import math
from copy import deepcopy
from pathlib import Path

DT = 1.25e-6
END_TIME = 40 * DT
CHECKPOINT_TIME = 10 * DT
ARMS = ("coupled", "supply_off", "inhibited", "reverse", "release", "two_patches")
STEPS = (DT, DT / 2, DT / 4)


def definition(arm="coupled", *, backend="cpu", padded=False, dt=DT):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = json.loads(
        (Path(__file__).resolve().parents[2] / "configs/resolved_energy_tissue.json").read_text()
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    e["end_time"] = END_TIME
    x.update(backend=backend, dt=dt)
    if arm != "release":
        e["observation_times"] = [i * DT for i in (0, 10, 20, 30, 40)]
        for kind in ("membrane", "channel", "pump", "regeneration"):
            for row in e[kind + "_controls"]:
                row["schedule"] = [dict(time=0.0, availability=1.0)]
    if arm == "supply_off":
        e["regeneration_controls"][0]["schedule"][0]["availability"] = 0.0
    if arm == "inhibited":
        e["pump_controls"][0]["schedule"][0]["availability"] = 0.0
    if arm == "reverse":
        m["energy_pools"][0]["initial_amount_fmol"] = dict(ATP=3e-6, ADP=0.04, Pi=0.04)
        e["regeneration_controls"][0]["schedule"][0]["availability"] = 0.0
        charge = m["membranes"][0]["capacitance_F"] * -0.08
        unit_charge = 6.02214076e23 * 1.602176634e-19 * 1e-15
        for owner, q in ((m["cells"][0], charge), (m["extracellular"][0], -charge)):
            owner["initial_charge_C"] = q
            owner["fixed_charge_equivalent_fmol"] = q / unit_charge - math.fsum(
                s["valence"] * owner["initial_amount_fmol"][s["id"]] for s in m["species"]
            )
    if arm == "two_patches":
        patch = m["membranes"][0]
        patch["area_m2"] *= 0.5
        patch["capacitance_F"] *= 0.5
        patch["pump"]["capacity_fmol_per_s"] *= 0.5
        second = deepcopy(patch)
        second["id"], second["pump"]["id"] = "membrane_1", "pump_1"
        m["membranes"].append(second)
        e["membrane_controls"].append(
            dict(membrane_id="membrane_1", schedule=[dict(time=0.0, availability=1.0)])
        )
        e["pump_controls"].append(
            dict(pump_id="pump_1", schedule=[dict(time=0.0, availability=0.6)])
        )
        for channel in list(m["channels"]):
            duplicate = deepcopy(channel)
            duplicate["id"] += "_second"
            duplicate["membrane_id"] = "membrane_1"
            m["channels"].append(duplicate)
            e["channel_controls"].append(
                dict(channel_id=duplicate["id"], schedule=[dict(time=0.0, availability=1.0)])
            )
    pad = int(padded)
    x.update(
        capacity=1 + pad,
        extracellular_capacity=1 + pad,
        membrane_capacity=len(m["membranes"]) + pad,
        edge_capacity=pad,
        face_capacity=pad,
        channel_capacity=len(m["channels"]) + pad,
        regeneration_capacity=len(m["regeneration_ports"]) + pad,
    )
    return raw


def normalized(raw):
    result = deepcopy(raw)
    result["execution"]["backend"] = "cpu"
    return result
