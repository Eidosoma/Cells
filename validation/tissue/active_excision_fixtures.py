"""Three active cells with declared gate memory and excision control clocks.

Manufactured transient examples, not fitted biology or slow-gate equilibrium.
The full catalog is read as raw data; no production Python is imported.
"""

import json
from copy import deepcopy
from pathlib import Path

from validation.tissue import surface_excision_fixtures as passive

DT = 1.25e-6
CUT_TIME = 40 * DT
END_TIME = 120 * DT
ARMS = (
    "open",
    "clamped",
    "blocked",
    "no-op",
    "single-survivor",
    "sequential",
    "closed",
    "disconnected",
    "reordered",
    "empty",
)
COMPACT_LAWS = (
    "betse_kv1p5_ml_dynamic_m@1",
    "betse_cagpotassium_numeric_mM_scale@1",
    "betse_nav1p2_m3h_regularized@1",
)


def definition(arm="open", *, catalog="compact", backend="cpu", padded=False):
    if arm not in ARMS or catalog not in ("compact", "full"):
        raise ValueError((arm, catalog))
    raw = passive.definition(arm if arm in passive.ARMS else "open", backend=backend, padded=padded)
    source = json.loads(
        (Path(__file__).resolve().parents[2] / "configs/resolved_hcn_extra_ionic.json").read_text()
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"], m["temperature_K"] = "resolved_tissue@12", 298.15
    m["species"].append(dict(id="Ca", valence=2))
    for i, row in enumerate([*m["cells"], *m["extracellular"]]):
        amount = row["volume_pL"] * (0.002 + i * 0.0003 if i < 3 else 0.02)
        row["initial_amount_fmol"]["Ca"] = amount
        row["fixed_charge_equivalent_fmol"] -= 2 * amount
    for row in m["membranes"]:
        row["permeability_m_per_s"]["Ca"] = 1e-9
    for row in m["faces"]:
        row["diffusivity_m2_per_s"]["Ca"] = 0.0 if arm == "blocked" else 1e-10
    extra = deepcopy(m["junctions"][0])
    extra.update(id="junction_0_2", sender="cell_0", receiver="cell_2")
    m["junctions"].append(extra)
    for j, row in enumerate(m["junctions"]):
        row["permeability_m_per_s"]["Ca"] = 1e-9
        row["gate"] = dict(
            law="betse_rate_junction_relaxation@1",
            threshold_voltage_V=0.015,
            minimum_open_fraction=0.1,
            initial_gate=0.4 + 0.1 * j,
        )
    pump_template = source["model"]["membranes"][0]["pump"]
    for j, row in enumerate(m["membranes"]):
        row["pump"] = deepcopy(pump_template)
        row["pump"].update(id="pump_" + row["id"], capacity_fmol_per_s=0.02 + 0.005 * j)
    templates = {row["kinetic_law"]: row for row in source["model"]["channels"]}
    laws = list(templates) if catalog == "full" else list(COMPACT_LAWS) * 3
    m["channels"] = []
    for j, law in enumerate(laws):
        owner = j % 3 if catalog == "full" else j // 3
        row = deepcopy(templates[law])
        row.update(id=f"active_channel_{j}", membrane_id=f"membrane_{owner}_bath")
        # Distinct, nonstationary memory makes resets and owner permutations visible.
        row["initial_gate"] = [0.2 + 0.03 * (j % 7), 0.75 - 0.02 * (j % 5)][
            : len(row["initial_gate"])
        ]
        m["channels"].append(row)
    if arm == "empty":
        m["channels"] = []
        for row in m["membranes"]:
            row["pump"] = None
    level = 0.0 if arm == "blocked" else 0.8
    owners = {
        "membrane": m["membranes"],
        "junction": m["junctions"],
        "channel": m["channels"],
        "pump": [row["pump"] for row in m["membranes"] if row["pump"] is not None],
    }
    for kind, rows in owners.items():
        e[kind + "_controls"] = [
            dict(**{kind + "_id": row["id"]}, schedule=[dict(time=0.0, availability=level)])
            for row in rows
        ]
    removed_channel = next(
        (row["id"] for row in m["channels"] if row["membrane_id"] == "membrane_1_bath"), None
    )
    events = (
        ("membrane", "membrane_1_bath", 17.3e-6, 81.1e-6),
        ("junction", "junction_1_2", 23.7e-6, 88.3e-6),
        ("channel", removed_channel, 31.1e-6, 93.7e-6),
        ("pump", "pump_membrane_1_bath", 37.3e-6, 107.9e-6),
        ("junction", "junction_0_2", 73.3e-6, 112.7e-6),
    )
    for kind, name, off, on in events:
        for row in e[kind + "_controls"]:
            if row[kind + "_id"] == name:
                row["schedule"] += [
                    dict(time=off, availability=0.0),
                    dict(time=on, availability=0.0 if arm == "blocked" else 0.6),
                ]
    clocks = {
        v["time"] for kind in owners for row in e[kind + "_controls"] for v in row["schedule"]
    }
    e.update(
        end_time=END_TIME,
        observation_times=sorted(clocks | {i * DT for i in (0, 10, 20, 40, 60, 80, 100, 120)}),
    )
    x.update(
        dt=DT,
        edge_capacity=3 + int(padded),
        channel_capacity=len(m["channels"]) + int(padded),
        max_steps=2048,
    )
    x["material_balance_atol_fmol"]["Ca"] = 2e-11
    if arm == "reordered":
        for name in ("cells", "extracellular", "species", "membranes", "junctions", "channels"):
            m[name].reverse()
        for kind in owners:
            e[kind + "_controls"].reverse()
    return raw


def cut_plan(arm="open"):
    if arm not in ARMS:
        raise ValueError(arm)
    removed = (
        []
        if arm == "no-op"
        else ["cell_0", "cell_1"]
        if arm == "single-survivor"
        else ["cell_0" if arm == "disconnected" else "cell_1"]
    )
    result = [dict(time_s=CUT_TIME, removed_cell_ids=removed)]
    if arm == "sequential":
        result.append(dict(time_s=80 * DT, removed_cell_ids=["cell_0"]))
    return result
