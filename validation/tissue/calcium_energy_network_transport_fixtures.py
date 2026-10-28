"""Manufactured native transport on the serialized 56-law calcium/fuel fixture.

Only data/standard-library imports. Rates and inventories are synthetic;
the short full-model probe establishes coupling, not physiological settling.
"""

import json
import os
from copy import deepcopy
from pathlib import Path

MODEL_ID = "resolved_calcium_energy_transport@1"
ARMS = ("active", "blocked", "reordered", "empty", "reverse", "zero-drive")
F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23


def _configuration(name, species, coefficients, inward, outward, maximum, standard, km):
    return {
        "name": name,
        "reaction zone": "cell",
        "reactants": list(species),
        "reactant multipliers": list(coefficients),
        "Km reactants": list(km),
        "products": list(species),
        "product multipliers": list(coefficients),
        "Km products": [2 * value for value in km],
        "transfered into cell": list(inward),
        "transfered out of cell": list(outward),
        "max rate": maximum,
        "standard free energy": standard,
        "ignore ECM": False,
        "apply to": "all",
    }


def definition(arm="active", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    default = Path(__file__).resolve().parents[2] / "configs/resolved_hcn_extra_energy.json"
    raw = json.loads(Path(os.environ.get("CELLS_NETWORK_TRANSPORT_BASE", default)).read_text())
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if m["id"] != "resolved_calcium_energy@5" or m["ionic"]["id"] != "resolved_tissue@12":
        raise ValueError("Require the serialized owned-calcium/finite-fuel 56-law fixture")
    m["id"] = MODEL_ID
    definitions = [
        ("kcl", ("K", "Cl"), (1, 1), ("K", "Cl"), (), 1e-5, 0.0, (20.0, 23.0)),
        ("na_ca", ("Na", "Ca"), (3, 1), ("Na",), ("Ca",), 1e-6, 0.0, (20.0, 0.003)),
        ("na_drive", ("Na",), (1,), ("Na",), (), 2e-6, -6000.0, (20.0,)),
        ("ca_out", ("Ca",), (1,), (), ("Ca",), 1e-9, 0.0, (0.002,)),
    ]
    routes = []
    for index, values in enumerate(definitions):
        name, *arguments = values
        config = _configuration(name, *arguments)
        if arm == "reverse":
            config["standard free energy"] = 18000.0
            # Preserve the native law and rate. Positive reaction energy reverses its extent.
        if arm == "zero-drive":
            config["standard free energy"] = 0.0
        routes.append(
            dict(
                id=name,
                membrane_id=m["ionic"]["membranes"][index]["id"],
                density_multiplier=0.7 + 0.05 * index,
                configuration=config,
                drive=dict(
                    kind="maintained_work_per_cycle@1",
                    supplied_energy_J_per_mol=-config["standard free energy"],
                ),
            )
        )
    if arm == "empty":
        routes = []
    m["network_transport"] = dict(
        law="betse_network_transporter_source_v1_5_0@1",
        constants=dict(faraday_C_mol=F, gas_constant_J_mol_K=R),
        accounting="reversible_pure_transport_maintained_drive@1",
        routes=routes,
    )
    e["network_transport_controls"] = [
        dict(
            transporter_id=row["id"],
            schedule=[dict(time=0.0, availability=0.0 if arm == "blocked" else 0.8)],
        )
        for row in routes
    ]
    if arm == "reordered":
        m["ionic"]["species"].reverse()
        routes.reverse()
        e["network_transport_controls"].reverse()
        for route in routes:
            config = route["configuration"]
            for key in ("products", "product multipliers", "Km products"):
                config[key].reverse()
    ion = m["ionic"]
    x.update(backend=backend, network_transport_capacity=len(routes) + int(padded))
    for key, count in dict(
        capacity=len(ion["cells"]),
        extracellular_capacity=len(ion["extracellular"]),
        edge_capacity=len(ion["junctions"]),
        membrane_capacity=len(ion["membranes"]),
        face_capacity=len(ion["faces"]),
        channel_capacity=len(ion["channels"]),
        chemical_capacity=2,
        reaction_capacity=len(m["stores"][0]["model"]["reactions"]),
        regeneration_capacity=len(m["regeneration_ports"]),
    ).items():
        x[key] = count + int(padded)
    return raw


def compact_probe(arm="active", *, backend="cpu", padded=False):
    """50 us, distinct off-grid route clocks and inherited channel/fuel feedback."""
    raw = definition(arm, backend=backend, padded=padded)
    e = raw["experiment"]
    dt = raw["execution"]["dt"]
    e.update(
        end_time=40 * dt,
        observation_times=[0.0, 8 * dt, 13.3e-6, 15 * dt, 20 * dt, 31.1e-6, 30 * dt, 40 * dt],
    )
    if arm == "empty":
        e["observation_times"] = [
            time for time in e["observation_times"] if time not in (13.3e-6, 31.1e-6)
        ]
    for key, groups in e.items():
        if key.endswith("_controls"):
            for group in groups:
                field = "controls" if "controls" in group else "schedule"
                group[field] = [row for row in group[field] if row["time"] <= e["end_time"]]
    if arm != "empty":
        by_id = {row["transporter_id"]: row for row in e["network_transport_controls"]}
        by_id["na_drive"]["schedule"].extend(
            [
                dict(time=13.3e-6, availability=0.0),
                dict(time=31.1e-6, availability=0.0 if arm == "blocked" else 0.6),
            ]
        )
    e["regeneration_controls"][0]["schedule"].append(dict(time=15 * dt, availability=0.0))
    return raw


def parent_definition(raw):
    projected = deepcopy(raw)
    projected["model"]["id"] = "resolved_calcium_energy@5"
    projected["model"].pop("network_transport")
    projected["experiment"].pop("network_transport_controls")
    projected["execution"].pop("network_transport_capacity")
    return projected
