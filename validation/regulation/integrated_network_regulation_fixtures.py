"""Explicit synthetic 56-law calcium/fuel inputs with live regulator reads."""

import json
from copy import deepcopy
from pathlib import Path

MODEL_ID = "resolved_calcium_energy_regulated@1"
ARMS = ("active", "blocked", "identity", "empty", "reordered", "ordered", "independent", "direct")


def definition(arm="active", *, padded=False, compact=False):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = json.loads(
        (Path(__file__).resolve().parents[2] / "configs/resolved_hcn_extra_energy.json").read_text()
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    configurations = [
        dict(
            activators=["ATP"],
            **{
                "activator Km": [0.6],
                "activator n": [2.0],
                "activator zone": ["cell"],
                "inhibitors": ["Ca"],
                "inhibitor Km": [0.0006],
                "inhibitor n": [1.0],
                "inhibitor zone": ["cell"],
            },
        ),
        dict(
            activators=["Na"],
            **{"activator Km": [90.0], "activator n": [1.0], "activator zone": ["env"]},
        ),
        dict(
            activators=["ATP"],
            **{
                "activator Km": [0.8],
                "activator n": [1.0],
                "inhibitors": ["ADP"],
                "inhibitor Km": [0.4],
                "inhibitor n": [1.0],
            },
        ),
        dict(activators=["Pi"], **{"activator Km": [0.1], "activator n": [1.0]}),
    ]
    pools = {p["cell_id"]: p["id"] for p in m["energy_pools"]}
    rules = []
    for i, patch in enumerate(m["ionic"]["membranes"]):
        name = "nak_rule_" + str(i)
        configuration = dict(
            name=name, target="Na/K-ATPase", **{"max effect": 0.8, "target ion": None}
        )
        configuration.update(configurations[i])
        if arm in ("identity", "blocked"):
            configuration = dict(
                name=name, target="Na/K-ATPase", **{"max effect": 1.0 if arm == "identity" else 0.0}
            )
        if arm == "independent":
            configuration = dict(
                name=name,
                target="Na/K-ATPase",
                **{
                    "max effect": 0.4,
                    "activators": ["ATP!"],
                    "activator Km": [0.6],
                    "activator n": [1.0],
                },
            )
        if arm == "direct":
            configuration = dict(
                name=name,
                target="Na/K-ATPase",
                **{
                    "max effect": 0.1,
                    "activators": ["ATP&"],
                    "activator Km": [1.0],
                    "activator n": [1.0],
                },
            )
        rules.append(
            dict(
                id=name,
                pump_id=patch["pump"]["id"],
                fuel_pool_id=pools[patch["inside"]],
                configuration=configuration,
            )
        )
    if arm == "empty":
        rules = []
    if arm == "ordered":
        rules.append(
            dict(
                id="last_pump_0",
                pump_id="pump_0",
                fuel_pool_id="fuel_cell_0",
                configuration={"name": "last_pump_0", "target": "Na/K-ATPase", "max effect": 0.23},
            )
        )
    m.update(
        id=MODEL_ID,
        network_regulation=dict(
            law="betse_network_modulation_source_v1_5_0@1",
            timing="common_stage_free_cytosol_exterior_fuel@1",
            control_composition="scheduled_times_ordered_native_nak_factor@1",
            rules=rules,
        ),
    )
    if compact:
        kept = m["ionic"]["channels"][:2]
        keep = {r["id"] for r in kept}
        m["ionic"]["channels"] = kept
        e["channel_controls"] = [r for r in e["channel_controls"] if r["channel_id"] in keep]
    ion = m["ionic"]
    counts = dict(
        capacity=len(ion["cells"]),
        extracellular_capacity=len(ion["extracellular"]),
        membrane_capacity=len(ion["membranes"]),
        edge_capacity=len(ion["junctions"]),
        face_capacity=len(ion["faces"]),
        channel_capacity=len(ion["channels"]),
        chemical_capacity=2,
        reaction_capacity=len(m["stores"][0]["model"]["reactions"]),
        regeneration_capacity=len(m["regeneration_ports"]),
        regulation_capacity=len(rules),
    )
    x.update({k: v + int(padded) for k, v in counts.items()})
    x.update(backend="cpu", jit=True)
    if arm == "reordered":
        m["ionic"]["species"].reverse()
        m["energy_pools"].reverse()
        m["stores"].reverse()
        rules.reverse()
    return raw


def parent_definition(raw):
    result = deepcopy(raw)
    result["model"]["id"] = "resolved_calcium_energy@5"
    result["model"].pop("network_regulation")
    result["execution"].pop("regulation_capacity")
    return result


def probe(arm="active", *, compact=False, padded=False):
    raw = definition(arm, compact=compact, padded=padded)
    e = raw["experiment"]
    dt = raw["execution"]["dt"]
    e.update(end_time=40 * dt, observation_times=[0.0, 10 * dt, 13.3e-6, 20 * dt, 31.1e-6, 40 * dt])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                field = "controls" if "controls" in group else "schedule"
                group[field] = [r for r in group[field] if r["time"] <= e["end_time"]]
    e["pump_controls"][0]["schedule"].extend(
        [dict(time=13.3e-6, availability=0.0), dict(time=31.1e-6, availability=0.6)]
    )
    e["regeneration_controls"][0]["schedule"].append(dict(time=20 * dt, availability=0.0))
    return raw
