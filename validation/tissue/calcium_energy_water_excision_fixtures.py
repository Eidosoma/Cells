"""The three-cell neutral cut with exact 53-law compliant water semantics.

Compliance rows and hydraulic permeabilities are copied unchanged from the
prior continuous43 JSON. Only synthetic owner IDs/assignments and clocks are
new. Initial volumes need not equal the unchanged compliance reference volumes.
ER solvent volumes stay fixed. This is a transient cut case, not water physiology.
"""

import json
from copy import deepcopy
from pathlib import Path

from validation.tissue import calcium_energy_excision_fixtures as prior

DT, CUT_TIME, END_TIME = prior.DT, prior.CUT_TIME, prior.END_TIME
ARMS = (*prior.ARMS, "water_blocked", "sealed")
EXCLUDED_LAWS = {"betse_hcn_leak_open@1", "betse_hcn2_camp_m@1", "betse_hcn4_camp_m@1"}


def definition(arm="open", *, catalog="compact", backend="cpu", padded=False):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(
        arm if arm in prior.ARMS else "open", catalog=catalog, backend=backend, padded=padded
    )
    source = json.loads(
        (
            Path(__file__).resolve().parents[2] / "configs/resolved_calcium_energy_water.json"
        ).read_text()
    )
    m, e, ion = raw["model"], raw["experiment"], raw["model"]["ionic"]
    m["id"], ion["id"] = "resolved_calcium_energy_water@1", "resolved_tissue@11"
    ion["channels"] = [p for p in ion["channels"] if p["kinetic_law"] not in EXCLUDED_LAWS]
    channels = {p["id"] for p in ion["channels"]}
    old_events = {v["time"] for p in e["channel_controls"] for v in p["schedule"]}
    e["channel_controls"] = [p for p in e["channel_controls"] if p["channel_id"] in channels]
    # Preserve removed-law-only clock points without importing numerical helpers.
    carrier = e["membrane_controls"][0]["schedule"]
    for time in sorted(old_events - {p["time"] for p in carrier}):
        held = deepcopy(next(p for p in reversed(carrier) if p["time"] <= time))
        held["time"] = time
        carrier.append(held)
        carrier.sort(key=lambda p: p["time"])
    raw["execution"]["channel_capacity"] = len(channels) + int(padded)
    for key in ("chemical_osmotic_coupling", "energy_osmotic_coupling"):
        m[key] = source["model"][key]
    old = {p["compartment_id"]: p for p in source["model"]["water_compartments"]}
    assignments = dict(
        cell_0="cell_0", cell_1="cell_1", cell_2="cell_0", shared="outside_0", bath="outside_4"
    )
    m["water_compartments"] = [
        dict(deepcopy(old[assignments[p["id"]]]), compartment_id=p["id"])
        for p in (*ion["cells"], *ion["extracellular"])
    ]
    m["water_membranes"], e["water_controls"] = [], []
    templates = source["model"]["water_membranes"]
    for j, patch in enumerate(sorted(ion["membranes"], key=lambda p: p["id"])):
        row = deepcopy(templates[j % len(templates)])
        row["membrane_id"] = patch["id"]
        if arm == "sealed":
            row["hydraulic_permeability_m_per_Pa_s"] = 0.0
        m["water_membranes"].append(row)
        level = 0.0 if arm == "water_blocked" else 0.8
        schedule = [dict(time=0.0, availability=level)]
        if patch["id"] == "membrane_0_shared":
            schedule += [
                dict(time=11.7e-6, availability=0.0),
                dict(time=72.9e-6, availability=0.0 if not level else 0.6),
            ]
        if patch["id"] == "membrane_1_bath":
            schedule += [
                dict(time=41.7e-6, availability=0.0),
                dict(time=108.7e-6, availability=0.0 if not level else 0.7),
            ]
        e["water_controls"].append(dict(membrane_id=patch["id"], schedule=schedule))
    if arm == "reordered":
        m["water_compartments"].reverse()
        m["water_membranes"].reverse()
        e["water_controls"].reverse()
    times = {v["time"] for row in e["water_controls"] for v in row["schedule"]}
    e["observation_times"] = sorted(set(e["observation_times"]) | times)
    return raw


def cut_plan(arm="open"):
    if arm not in ARMS:
        raise ValueError(arm)
    return prior.cut_plan(arm if arm in prior.ARMS else "open")
