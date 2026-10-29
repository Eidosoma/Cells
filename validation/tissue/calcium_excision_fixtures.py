"""Closed, neutral-removal calcium/ER cases, distinct from held-bath cutting.

The removed cell is electrically neutral and all its external transport is
explicitly blocked; its binding, ER exchange and gate clocks remain live.
Unchanged source rate constants are used. The 150-us cases test transient
owner/gate continuation, not equilibrium, wound healing or native tissue cuts.
"""

import json
import math
from copy import deepcopy
from pathlib import Path

from validation.tissue import active_excision_fixtures as active

F = 6.02214076e23 * 1.602176634e-19
DT, CUT_TIME, END_TIME = active.DT, active.CUT_TIME, active.END_TIME
ARMS = (
    "open",
    "blocked",
    "reordered",
    "empty",
    "no-op",
    "single-survivor",
    "sequential",
    "charged",
    "terminal",
)


def definition(arm="open", *, catalog="compact", backend="cpu", padded=False):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = active.definition(
        "empty" if arm == "empty" else "open", catalog=catalog, backend=backend, padded=padded
    )
    source = json.loads(
        (
            Path(__file__).resolve().parents[2] / "configs/resolved_hcn_extra_calcium.json"
        ).read_text()
    )
    ionic, experiment = raw["model"], raw["experiment"]
    neutral = {"cell_0", "cell_1"} if arm in ("single-survivor", "sequential") else {"cell_1"}
    cells = {v["id"]: v for v in ionic["cells"]}
    exteriors = {v["id"]: v for v in ionic["extracellular"]}
    for row in exteriors.values():
        row.update(reservoir=False, boundary_potential_V=0.0)
    ionic["closure"]["gauge_reference"] = "bath"
    voltage = {"cell_0": -0.02, "cell_1": 0.0, "cell_2": -0.03, "shared": 0.0, "bath": 0.0}
    voltage.update({name: 0.0 for name in neutral})
    charge = dict.fromkeys(voltage, 0.0)
    for patch in ionic["membranes"]:
        q = patch["capacitance_F"] * (voltage[patch["inside"]] - voltage[patch["outside"]])
        charge[patch["inside"]] += q
        charge[patch["outside"]] -= q
    for row in [*cells.values(), *exteriors.values()]:
        row["initial_charge_C"] = charge[row["id"]]
        row["fixed_charge_equivalent_fmol"] = charge[row["id"]] / (F * 1e-15) - math.fsum(
            species["valence"] * row["initial_amount_fmol"][species["id"]]
            for species in ionic["species"]
        )
    membranes = {p["id"]: p for p in ionic["membranes"]}
    blocked_membranes = {p["id"] for p in membranes.values() if p["inside"] in neutral}
    blocked_owners = {
        "membrane": blocked_membranes,
        "junction": {
            p["id"]
            for p in ionic["junctions"]
            if p["sender"] in neutral or p["receiver"] in neutral
        },
        "channel": {p["id"] for p in ionic["channels"] if p["membrane_id"] in blocked_membranes},
        "pump": {
            p["pump"]["id"]
            for p in membranes.values()
            if p["id"] in blocked_membranes and p["pump"] is not None
        },
    }
    for kind, owners in blocked_owners.items():
        for row in experiment[kind + "_controls"]:
            if arm == "blocked" or row[kind + "_id"] in owners:
                for event in row["schedule"]:
                    event["availability"] = 0.0
    model = deepcopy(source["model"])
    model["ionic"] = ionic
    model["stores"], model["ip3_release"] = [], []
    experiment["store_controls"] = []
    for cell in cells.values():
        store = deepcopy(source["model"]["stores"][0]["model"])
        for compartment in store["compartments"]:
            volume = cell["volume_pL"] * (1.0 if compartment["id"] == "cytosol" else 0.1)
            factor = volume / compartment["volume_pL"]
            compartment["volume_pL"] = volume
            compartment["initial_amount_fmol"] = {
                name: amount * factor for name, amount in compartment["initial_amount_fmol"].items()
            }
            if compartment["id"] == "cytosol":
                compartment["initial_amount_fmol"].update(cell["initial_amount_fmol"])
        model["stores"].append(dict(cell_id=cell["id"], model=store))
        binding = deepcopy(source["model"]["ip3_release"][0])
        binding["cell_id"] = cell["id"]
        model["ip3_release"].append(binding)
        controls = deepcopy(source["experiment"]["store_controls"][0])
        controls["cell_id"] = cell["id"]
        if cell["id"] == "cell_1":
            a, b = deepcopy(controls["controls"][0]), deepcopy(controls["controls"][0])
            a.update(time=47.3e-6, pump=0.0)
            b.update(time=91.7e-6, pump=1.0)
            controls["controls"] += [a, b]
        experiment["store_controls"].append(controls)
    model["plasma_transport"]["membranes"], model["calcium_channels"] = [], []
    experiment["plasma_controls"], experiment["calcium_channel_controls"] = [], []
    for j, patch in enumerate(membranes.values()):
        route = deepcopy(source["model"]["plasma_transport"]["membranes"][0])
        route["membrane_id"] = patch["id"]
        model["plasma_transport"]["membranes"].append(route)
        channel = deepcopy(source["model"]["calcium_channels"][0])
        channel.update(
            id="dedicated_" + patch["id"],
            membrane_id=patch["id"],
            initial_gate=dict(m=0.2 + 0.01 * j, h=0.7 - 0.01 * j),
        )
        model["calcium_channels"].append(channel)
        level = 0.0 if arm == "blocked" or patch["id"] in blocked_membranes else 0.8
        plasma = [dict(time=0.0, pump=level, exchanger=level)]
        calcium = [dict(time=0.0, availability=level)]
        if patch["id"] == "membrane_1_bath":
            plasma += [dict(time=t, pump=0.0, exchanger=0.0) for t in (43.3e-6, 101.3e-6)]
            calcium += [dict(time=t, availability=0.0) for t in (46.1e-6, 103.9e-6)]
        experiment["plasma_controls"].append(dict(membrane_id=patch["id"], schedule=plasma))
        experiment["calcium_channel_controls"].append(
            dict(channel_id=channel["id"], schedule=calcium)
        )
    raw["model"] = model
    clocks = {
        v["time"]
        for name, rows in experiment.items()
        if name.endswith("_controls")
        for row in rows
        for v in row.get("schedule", row.get("controls", []))
    }
    experiment["observation_times"] = sorted(set(experiment["observation_times"]) | clocks)
    raw["execution"].update(chemical_capacity=2 + int(padded), reaction_capacity=5 + int(padded))
    if arm == "reordered":
        for name in ("cells", "extracellular", "species", "membranes", "junctions", "channels"):
            ionic[name].reverse()
        for name in ("stores", "ip3_release", "calcium_channels"):
            model[name].reverse()
        model["plasma_transport"]["membranes"].reverse()
        for name, rows in experiment.items():
            if name.endswith("_controls"):
                rows.reverse()
    return raw


def cut_plan(arm="open"):
    if arm not in ARMS:
        raise ValueError(arm)
    removed = (
        []
        if arm == "no-op"
        else ["cell_0"]
        if arm == "charged"
        else (
            ["cell_0", "cell_1", "cell_2"]
            if arm == "terminal"
            else ["cell_0", "cell_1"]
            if arm == "single-survivor"
            else ["cell_1"]
        )
    )
    result = [dict(time_s=CUT_TIME, removed_cell_ids=removed)]
    if arm == "sequential":
        result.append(dict(time_s=80 * DT, removed_cell_ids=["cell_0"]))
    return result
