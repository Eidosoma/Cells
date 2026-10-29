"""Regulated finite-fuel cut cases at unchanged parent rates and 50/150-us clocks.

The regulation expressions are copied from the frozen @2 examples. Assigning
them to this manufactured three-cell geometry is explicit, not fitted biology.
Rule order is physical: the last rule for a consumer supplies its factor.
"""

from copy import deepcopy

from validation.regulation import integrated_network_regulation_v2_fixtures as regulation
from validation.tissue import calcium_energy_excision_fixtures as fuel_cut

DT, CUT_TIME, END_TIME = fuel_cut.DT, fuel_cut.CUT_TIME, fuel_cut.END_TIME
ARMS = (*fuel_cut.ARMS, "no_rules", "shadowed", "identity", "factor_blocked")


def definition(arm="open", *, catalog="compact", backend="cpu", padded=False):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = fuel_cut.definition(
        arm if arm in fuel_cut.ARMS else "open", catalog=catalog, backend=backend, padded=padded
    )
    source = regulation.definition(
        "identity" if arm == "identity" else "blocked" if arm == "factor_blocked" else "active"
    )["model"]["network_regulation"]
    templates = {
        kind: [r for r in source["rules"] if r["kind"] == kind]
        for kind in ("nak", "channel", "junction")
    }
    model, ionic = raw["model"], raw["model"]["ionic"]
    membranes = {p["id"]: p for p in ionic["membranes"]}
    rules = []

    def add(kind, target, cell, outside, index):
        row = deepcopy(templates[kind][index % len(templates[kind])])
        name = f"reg_{kind}_{target}_{cell}_{index}"
        row.update(
            id=name,
            target_id=target,
            sample_cell_id=cell,
            sample_exterior_id=outside,
            fuel_pool_id="fuel_" + cell,
        )
        row["configuration"]["name"] = name
        rules.append(row)

    for j, patch in enumerate(sorted(membranes.values(), key=lambda p: p["id"])):
        if patch["pump"] is not None:
            add("nak", patch["pump"]["id"], patch["inside"], patch["outside"], j)
    # One population per cell, including zero/one/two-state populations in the
    # compact fixture. All other populations keep their scheduled availability.
    for j, cell in enumerate(sorted(p["id"] for p in ionic["cells"])):
        owned = sorted(
            (p for p in ionic["channels"] if membranes[p["membrane_id"]]["inside"] == cell),
            key=lambda p: p["id"],
        )
        if owned:
            channel = owned[min(j, len(owned) - 1)]
            patch = membranes[channel["membrane_id"]]
            add("channel", channel["id"], cell, patch["outside"], j)
    for edge in sorted(ionic["junctions"], key=lambda p: p["id"]):
        for j, cell in enumerate((edge["sender"], edge["receiver"])):
            add("junction", edge["id"], cell, None, j)
    if arm == "shadowed":
        overrides = regulation.definition("ordered")["model"]["network_regulation"]["rules"][-3:]
        for template in overrides:
            old = next(r for r in rules if r["kind"] == template["kind"])
            row = deepcopy(old)
            row["id"] = "last_" + old["id"]
            row["configuration"] = deepcopy(template["configuration"])
            row["configuration"]["name"] = row["id"]
            rules.append(row)
    if arm == "no_rules":
        rules = []
    model["id"] = regulation.MODEL_ID
    model["network_regulation"] = deepcopy(source)
    model["network_regulation"]["rules"] = rules
    raw["execution"]["regulation_capacity"] = len(rules) + int(padded)
    return raw


def cut_plan(arm="open"):
    if arm not in ARMS:
        raise ValueError(arm)
    return fuel_cut.cut_plan(arm if arm in fuel_cut.ARMS else "open")
