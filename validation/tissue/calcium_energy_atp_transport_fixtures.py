"""Data-only synthetic one-ATP native transport on the owned56 fuel recipe."""

from copy import deepcopy

from validation.tissue import calcium_energy_network_transport_fixtures as original

MODEL_ID = "resolved_calcium_energy_atp_transport@1"
ACCOUNTING = "finite_pool_atp_hydrolysis_species_transport@1"
ARMS = ("active", "blocked", "empty", "reordered", "reverse", "mixed", "fuel-regulated")


def definition(arm="active", *, padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = original.definition(arm if arm in original.ARMS else "active", padded=padded)
    m, e = raw["model"], raw["experiment"]
    m["id"] = MODEL_ID
    block = m["network_transport"]
    block["accounting"] = ACCOUNTING
    block["constants"].update(ionic_standard_state_mM=1.0, fuel_standard_state_mM=1000.0)
    membranes = {row["id"]: row for row in m["ionic"]["membranes"]}
    pools = {row["cell_id"]: row for row in m["energy_pools"]}
    for row in block["routes"]:
        pool = pools[membranes[row["membrane_id"]]["inside"]]
        config = row["configuration"]
        config["reactants"].append("ATP")
        config["reactant multipliers"].append(1)
        config["Km reactants"].append(0.5)
        config["products"].extend(("ADP", "Pi"))
        config["product multipliers"].extend((1, 1))
        config["Km products"].extend((0.3, 0.7))
        config["standard free energy"] = pool["delta_g0_J_per_mol"]
        row["drive"] = dict(
            kind="finite_energy_pool_hydrolysis@1", pool_id=pool["id"], atp_per_cycle=1
        )
    if arm in ("reverse", "mixed"):
        route = deepcopy(next(row for row in block["routes"] if row["id"] == "na_drive"))
        route.update(id="na_atp_synthesis", membrane_id="membrane_1")
        route["configuration"].update(
            {
                "name": "na_atp_synthesis",
                "reactants": ["Na", "ATP"],
                "reactant multipliers": [8, 1],
                "Km reactants": [20.0, 0.5],
                "products": ["Na", "ADP", "Pi"],
                "product multipliers": [8, 1, 1],
                "Km products": [40.0, 0.3, 0.7],
                "transfered into cell": [],
                "transfered out of cell": ["Na"],
                "max rate": 2e-8,
            }
        )
        route["drive"]["pool_id"] = pools["cell_0"]["id"]
        block["routes"] = [route] if arm == "reverse" else [*block["routes"], route]
        if arm == "reverse":
            e["network_transport_controls"] = []
        e["network_transport_controls"].append(
            dict(transporter_id=route["id"], schedule=[dict(time=0.0, availability=0.8)])
        )
    if arm == "fuel-regulated":
        block["routes"][0]["configuration"].update(
            {"transporter activators": ["ATP*"], "activator Km": [0.4], "activator n": [2.0]}
        )
    raw["execution"]["network_transport_capacity"] = len(block["routes"]) + int(padded)
    return raw


def probe(arm="active", *, padded=False):
    """Two original nominal steps and an actual off-grid route-only event."""
    raw = definition(arm, padded=padded)
    dt = raw["execution"]["dt"]
    end = 2 * dt
    e = raw["experiment"]
    e["end_time"] = end
    for key, groups in e.items():
        if key.endswith("_controls"):
            for group in groups:
                name = "controls" if "controls" in group else "schedule"
                group[name] = [row for row in group[name] if row["time"] <= end]
    times = [0.0, dt, end]
    if e["network_transport_controls"]:
        event = 0.75 * dt
        times.append(event)
        e["network_transport_controls"][0]["schedule"].append(
            dict(time=event, availability=0.0 if arm == "blocked" else 0.35)
        )
    e["observation_times"] = sorted(times)
    return raw


parent_definition = original.parent_definition
