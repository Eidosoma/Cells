"""Configured routes on the frozen neutral-removal calcium/fuel geometry.

Each cell explicitly owns copies of the four previously qualified synthetic
route configurations. Their rate, density, stoichiometry, Km and supplied work
are unchanged; only route IDs/names and membrane assignments differ. Removed
neutral cells have all external routes blocked, including these transporters.
The explicit removed_neutral_history arm instead enables one electroneutral
KCl route on cell_1 with a declared 6000 J/mol maintained drive, leaving its
kinetic parameters unchanged. This creates removable nonzero route histories
without changing the removed cell's plasma charge.
"""

from copy import deepcopy

from validation.tissue import calcium_energy_excision_fixtures as prior
from validation.tissue import calcium_energy_network_transport_fixtures as network

DT, CUT_TIME, END_TIME = prior.DT, prior.CUT_TIME, prior.END_TIME
ARMS = (
    *prior.ARMS,
    "zero_routes",
    "network_blocked",
    "zero_drive",
    "removed_neutral_history",
)


def definition(arm="open", *, catalog="compact", backend="cpu", padded=False):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(
        arm if arm in prior.ARMS else "open", catalog=catalog, backend=backend, padded=padded
    )
    source = network.definition("active", padded=False)["model"]["network_transport"]
    group = deepcopy(source)
    group["routes"] = []
    m, e = raw["model"], raw["experiment"]
    m["id"] = "resolved_calcium_energy_transport@1"
    e["network_transport_controls"] = []
    for cell in sorted(m["ionic"]["cells"], key=lambda p: p["id"]):
        for template in source["routes"]:
            route = deepcopy(template)
            name = template["id"] + "_" + cell["id"]
            outside = "shared" if template["id"] in ("kcl", "ca_out") else "bath"
            route.update(
                id=name, membrane_id="membrane_" + cell["id"].removeprefix("cell_") + "_" + outside
            )
            route["configuration"]["name"] = name
            if arm == "zero_drive":
                route["configuration"]["standard free energy"] = 0.0
                route["drive"]["supplied_energy_J_per_mol"] = 0.0
            if arm == "removed_neutral_history" and name == "kcl_cell_1":
                route["configuration"]["standard free energy"] = -6000.0
                route["drive"]["supplied_energy_J_per_mol"] = 6000.0
            group["routes"].append(route)
            blocked = arm in ("blocked", "network_blocked") or cell["initial_charge_C"] == 0
            if arm == "removed_neutral_history" and name == "kcl_cell_1":
                blocked = False
            level = 0.0 if blocked else 0.8
            schedule = [dict(time=0.0, availability=level)]
            if name == "na_drive_cell_0":
                schedule += [
                    dict(time=13.3e-6, availability=0.0),
                    dict(time=61.1e-6, availability=0.0 if blocked else 0.6),
                ]
            if name == "na_drive_cell_1":
                schedule += [
                    dict(time=27.1e-6, availability=0.0),
                    dict(time=97.3e-6, availability=0.0),
                ]
            e["network_transport_controls"].append(dict(transporter_id=name, schedule=schedule))
    if arm == "zero_routes":
        group["routes"], e["network_transport_controls"] = [], []
    if arm == "reordered":
        group["routes"].reverse()
        e["network_transport_controls"].reverse()
        for route in group["routes"]:
            for key in ("products", "product multipliers", "Km products"):
                route["configuration"][key].reverse()
    m["network_transport"] = group
    times = {v["time"] for row in e["network_transport_controls"] for v in row["schedule"]}
    e["observation_times"] = sorted(set(e["observation_times"]) | times)
    raw["execution"]["network_transport_capacity"] = len(group["routes"]) + int(padded)
    return raw


def cut_plan(arm="open"):
    if arm not in ARMS:
        raise ValueError(arm)
    return prior.cut_plan(arm if arm in prior.ARMS else "open")
