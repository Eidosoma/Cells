"""Live ATP routes on qualified neutral-removal geometry, with both gross directions.

KCl cargo is electroneutral. Its 32:32 uphill import route reverses to synthesize
ATP on actual pools, creating explicit removable synthesis history without
changing plasma charge. These are short synthetic cut probes, not wound laws.
"""

from copy import deepcopy

from validation.tissue import calcium_energy_transport_excision_fixtures as prior

MODEL_ID = "resolved_calcium_energy_atp_transport@1"
DT, CUT_TIME, END_TIME = prior.DT, prior.CUT_TIME, prior.END_TIME
ARMS = (
    "open",
    "reordered",
    "zero_routes",
    "network_blocked",
    "removed_neutral_history",
    "sequential",
)


def definition(arm="removed_neutral_history", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(arm, backend=backend, padded=padded)
    m, e = raw["model"], raw["experiment"]
    m["id"] = MODEL_ID
    group = m["network_transport"]
    group["accounting"] = "finite_pool_atp_hydrolysis_species_transport@1"
    group["constants"].update(ionic_standard_state_mM=1.0, fuel_standard_state_mM=1000.0)
    membranes = {row["id"]: row for row in m["ionic"]["membranes"]}
    pools = {row["cell_id"]: row for row in m["energy_pools"]}
    for row in group["routes"]:
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
    if arm not in ("zero_routes", "network_blocked"):
        for cell in m["ionic"]["cells"]:
            name = cell["id"]
            route = deepcopy(next(row for row in group["routes"] if row["id"] == "kcl_" + name))
            route["id"] = route["configuration"]["name"] = "kcl_atp_synthesis_" + name
            route["configuration"].update(
                {
                    "reactant multipliers": [32, 32, 1],
                    "Km reactants": [1.0, 20.0, 0.5],
                    "products": ["K", "Cl", "ADP", "Pi"],
                    "product multipliers": [32, 32, 1, 1],
                    "Km products": [20.0, 23.0, 0.3, 0.7],
                    "max rate": 1e-10,
                }
            )
            group["routes"].append(route)
            level = (
                0.8 if name != "cell_1" or arm in ("removed_neutral_history", "sequential") else 0.0
            )
            e["network_transport_controls"].append(
                dict(transporter_id=route["id"], schedule=[dict(time=0.0, availability=level)])
            )
        if arm == "sequential":
            for control in e["network_transport_controls"]:
                if control["transporter_id"] in ("kcl_cell_0", "kcl_cell_1"):
                    control["schedule"][0]["availability"] = 0.8
    raw["execution"].update(
        jit=False, network_transport_capacity=len(group["routes"]) + int(padded)
    )
    for control in e["network_transport_controls"]:
        if control["transporter_id"] == "kcl_cell_2":
            level = control["schedule"][0]["availability"]
            control["schedule"].append(dict(time=1.75 * DT, availability=0.35 if level else 0.0))
            e["observation_times"] = sorted({*e["observation_times"], 1.75 * DT})
    return raw
