"""Synthetic closed finite calcium worlds; these are not measured tissue parameters."""

import json
from copy import deepcopy
from pathlib import Path

from validation.tissue.surface_kinetic_fixtures import definition as ionic_definition

ARMS = ("baseline", "blocked", "release", "weak_ip3")
ROOT = Path(__file__).resolve().parents[2]


def definition(arm="baseline", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = ionic_definition("closed", backend=backend, padded=padded)
    ion, e, x = raw["model"], raw["experiment"], raw["execution"]
    template = json.loads((ROOT / "configs/ip3_calcium_cluster.json").read_text())
    ion["species"].append(dict(id="Ca", valence=2))
    for name, concentration in (("cells", 0.002), ("extracellular", 0.02)):
        for c in ion[name]:
            calcium = concentration * c["volume_pL"]
            c["initial_amount_fmol"]["Ca"] = calcium
            c["fixed_charge_equivalent_fmol"] -= 2 * calcium
    for name in ("membranes", "junctions"):
        for p in ion[name]:
            p["permeability_m_per_s"]["Ca"] = 1e-9
    for f in ion["faces"]:
        f["diffusivity_m2_per_s"]["Ca"] = 1e-10
    m = dict(
        id="resolved_calcium@1",
        ionic=ion,
        stores=deepcopy(template["model"]["stores"]),
        plasma_transport=dict(calcium_species="Ca", sodium_species="Na", membranes=[]),
        calcium_channels=[],
        ip3_release=deepcopy(template["model"]["ip3_release"]),
    )
    for i, (c, store) in enumerate(zip(ion["cells"], m["stores"], strict=True)):
        s = store["model"]
        cy = next(p for p in s["compartments"] if p["id"] == "cytosol")
        ratio = c["volume_pL"] / cy["volume_pL"]
        for part in s["compartments"]:
            part["volume_pL"] *= ratio
            part["initial_amount_fmol"] = {
                k: v * ratio for k, v in part["initial_amount_fmol"].items()
            }
            for k in ("Na", "K", "Cl"):
                part["initial_amount_fmol"][k] = (
                    c["initial_amount_fmol"][k] * part["volume_pL"] / c["volume_pL"]
                )
        cy["volume_pL"] = c["volume_pL"]
        cy["initial_amount_fmol"].update(c["initial_amount_fmol"])
        s["membrane"]["area_m2"] *= ratio
        s["membrane"]["pump"]["capacity_fmol_per_s"] *= ratio
        if arm == "weak_ip3":
            m["ip3_release"][i]["activation_mM"] *= 10
    e["store_controls"] = deepcopy(template["experiment"]["store_controls"])
    e["plasma_controls"], e["calcium_channel_controls"] = [], []
    for i, p in enumerate(ion["membranes"]):
        owner = [c["id"] for c in ion["cells"]].index(p["inside"])
        route = deepcopy(template["model"]["plasma_transport"]["membranes"][owner])
        route["membrane_id"] = p["id"]
        m["plasma_transport"]["membranes"].append(route)
        channel = deepcopy(template["model"]["calcium_channels"][owner])
        channel.update(id=f"calcium_channel_{i}", membrane_id=p["id"])
        m["calcium_channels"].append(channel)
        level = 0.0 if arm in ("blocked", "release") else 1.0
        pc = [dict(time=0.0, pump=level, exchanger=level)]
        cc = [dict(time=0.0, availability=level)]
        if arm == "release":
            pc.append(dict(time=0.00073, pump=0.8, exchanger=0.6))
            cc.append(dict(time=0.00073, availability=0.7))
        e["plasma_controls"].append(dict(membrane_id=p["id"], schedule=pc))
        e["calcium_channel_controls"].append(dict(channel_id=channel["id"], schedule=cc))
    if arm in ("blocked", "release"):
        for row in e["store_controls"]:
            row["controls"][0]["release"] = 0
            if arm == "release":
                change = deepcopy(row["controls"][0])
                change.update(time=0.00073, release=0.9)
                row["controls"].append(change)
        for family in ("channel_controls", "pump_controls", "junction_controls"):
            for row in e[family]:
                row["schedule"][0]["availability"] = 0.0
                if arm == "release":
                    row["schedule"].append(dict(time=0.00073, availability=0.6))
    if arm == "release":
        e["observation_times"].insert(1, 0.00073)
    x.update(
        dt=2.5e-5,
        chemical_capacity=2 + int(padded),
        reaction_capacity=5 + int(padded),
        max_steps=1000,
    )
    x["material_balance_atol_fmol"]["Ca"] = 2e-11
    raw["model"] = m
    return raw


def assembly_definition(*, backend="cpu"):
    raw = json.loads((ROOT / "configs/assembly_regulated_ip3_calcium_cluster.json").read_text())
    raw["ionic"] = definition(backend=backend)
    raw["window_ticks"] = 20
    for row in raw["pools"]:
        row["pool"].update(end_time_s=0.002, max_wall_seconds=2400.0)
    return raw
