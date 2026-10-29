"""Representative ordinary compositions with complete original owner histories."""

import json
from copy import deepcopy
from pathlib import Path

from validation.regulation import integrated_network_regulation_fixtures as reg1
from validation.regulation import integrated_network_regulation_v2_fixtures as reg2
from validation.tissue import calcium_energy_mitochondria_fixtures as mito
from validation.tissue import calcium_energy_network_transport_fixtures as transport
from validation.tissue import calcium_energy_water_fixtures as fuel_water
from validation.tissue import calcium_water_fixtures as calcium_water
from validation.tissue import morris_lecar_energy_water_fixtures as morris_fuel_water
from validation.tissue import morris_lecar_water_fixtures as morris_water
from validation.tissue import surface_calcium_cav_fixtures as cav
from validation.tissue import surface_calcium_kv1_fixtures as kv1
from validation.tissue import surface_energy_fixtures as energy
from validation.tissue import surface_energy_water_fixtures as energy_water
from validation.tissue import surface_water_fixtures as water
from validation.tissue import surface_water_kinetic_fixtures as kinetic_water

FILES = {
    "ionic_v2": "resolved_kinetic_tissue.json",
    "ionic_v3": "resolved_channels_cluster.json",
    "ionic_v4": "resolved_sodium_cluster.json",
    "ionic_v5": "resolved_hcn_cluster.json",
    "ionic_v8": "resolved_catalog_tissue.json",
    "ionic_v9": "resolved_catalog_v2_ionic.json",
    "ionic_v10": "resolved_calcium_activated_ionic.json",
    "ionic_v11": "resolved_morris_lecar_ionic.json",
    "calcium": "resolved_hcn_extra_calcium.json",
    "fuel": "resolved_hcn_extra_energy.json",
    "calcium_water": "resolved_calcium_water.json",
    "fuel_water": "resolved_calcium_energy_water.json",
    "water": "resolved_water_tissue.json",
    "kinetic_water": "resolved_water_kinetic_tissue.json",
    "energy": "resolved_energy_tissue.json",
    "energy_water": "resolved_energy_water_tissue.json",
    "morris_water": "resolved_morris_lecar_water.json",
}
FAMILIES = (
    *FILES,
    "ionic_v6",
    "ionic_v7",
    "morris_energy_water",
    "morris_energy",
    "transport",
    "mitochondria",
    "regulation_v1",
    "regulation_v2",
)


def definition(family):
    root = Path(__file__).resolve().parents[2]
    if family in ("ionic_v6", "ionic_v7"):
        # Take the complete declared ionic submodel from the established Kv1/
        # CaV fixture. The new case is explicitly ionic-only; no chemical store
        # state or control is represented as part of that model.
        raw = (kv1 if family == "ionic_v6" else cav).definition(padded=True)
        raw["model"] = raw["model"]["ionic"]
        template = json.loads((root / "configs/resolved_hcn_cluster.json").read_text())
        for key in ("experiment", "execution"):
            raw[key] = {k: v for k, v in raw[key].items() if k in template[key]}
    elif family == "calcium_water":
        raw = calcium_water.definition(padded=True)
    elif family == "fuel_water":
        raw = fuel_water.definition(padded=True)
    elif family == "water":
        raw = water.definition(padded=True)
    elif family == "kinetic_water":
        raw = kinetic_water.definition(padded=True)
    elif family == "energy":
        raw = energy.definition(padded=True)
    elif family == "energy_water":
        raw = energy_water.definition(padded=True)
    elif family == "morris_water":
        raw = morris_water.definition(padded=True)
    elif family == "morris_energy_water":
        raw = morris_fuel_water.definition("water", padded=True)
    elif family == "morris_energy":
        raw = morris_fuel_water.definition("energy", padded=True)
    elif family in FILES:
        raw = json.loads((root / "configs" / FILES[family]).read_text())
    elif family == "transport":
        raw = transport.definition(padded=True)
    elif family == "mitochondria":
        raw = mito.definition(padded=True)
    elif family == "regulation_v1":
        raw = reg1.definition("active", padded=True)
    elif family == "regulation_v2":
        raw = reg2.definition("active", padded=True)
    else:
        raise ValueError(family)
    leaf = raw["model"].get("ionic", raw["model"])
    # Compact populations retain all physical owners and the current initial
    # chemistry/fuel/volume/transport data. No constitutive parameter is changed.
    if "channels" in leaf and not family.startswith("ionic_v"):
        keep = leaf["channels"][:3]
        required = {
            r["target_id"]
            for r in raw["model"].get("network_regulation", {}).get("rules", [])
            if r.get("kind") == "channel"
        }
        ids = {r["id"] for r in keep} | required
        leaf["channels"] = [r for r in leaf["channels"] if r["id"] in ids]
        raw["experiment"]["channel_controls"] = [
            r for r in raw["experiment"]["channel_controls"] if r["channel_id"] in ids
        ]
        raw["execution"]["channel_capacity"] = len(ids) + 1
    return raw


def inputs(family, *, blocked=True, permuted=False):
    raw = definition(family)
    leaf = raw["model"].get("ionic", raw["model"])
    cells = [r["id"] for r in leaf["cells"]]
    mids = [r["id"] for r in leaf["membranes"]]
    env = [r["id"] for r in leaf["extracellular"]]
    patches = {r["id"]: r for r in leaf["membranes"]}
    partners = {mid: mid for mid in mids}
    contacts = {}
    neighbors = {cid: [] for cid in cells}
    available = {cid: [r["id"] for r in leaf["membranes"] if r["inside"] == cid] for cid in cells}
    for edge in leaf["junctions"]:
        a = available[edge["sender"]].pop(0)
        b = available[edge["receiver"]].pop(0)
        contacts[edge["id"]] = [a, b]
        partners[a] = b
        partners[b] = a
        neighbors[edge["sender"]].append(edge["receiver"])
        neighbors[edge["receiver"]].append(edge["sender"])
    centres = {cid: [i * 1e-5, i * 0.5e-5] for i, cid in enumerate(cells)}
    if permuted:
        cells.reverse()
        mids.reverse()
        env.reverse()
    layout = dict(
        cell_ids=cells,
        membrane_ids=mids,
        environment_ids=env,
        membrane_cell_ids=[patches[mid]["inside"] for mid in mids],
        membrane_environment_ids=[patches[mid]["outside"] for mid in mids],
        cell_membrane_ids=[
            [mid for mid in reversed(mids) if patches[mid]["inside"] == cid] for cid in cells
        ],
        cell_centres_m=[centres[cid] for cid in cells],
        bounds_m=[-1e-5, max(centres[cid][0] for cid in cells) + 1e-5, -1e-5, 2e-5],
        seed_fills=["red" if i % 2 == 0 else "blue" for i, _ in enumerate(cells)],
    )
    geometry = dict(
        layout=layout,
        thickness_m={r["id"]: (7.5 + 0.3 * i) * 1e-9 for i, r in enumerate(leaf["membranes"])},
        partner_membrane_ids=partners,
        junction_membrane_ids=contacts,
        cell_neighbor_ids=neighbors,
        provenance=dict(source="Explicit composed fixture SI surfaces and reciprocal contacts"),
        length_unit="m",
        rho_channel=1.0,
    )

    def selector(value):
        return dict(
            kind="ids", value=value, expected_layout_identity=None, permutation_cell_ids=None
        )

    default = dict(
        name="Default",
        selector=selector([cells[-1]]),
        diffusivity_m2_s=[1e-18 * (i + 1) for i in range(6)],
        is_gj_insular=False,
    )
    rows = [
        dict(
            name="Region",
            selector=selector([cells[0], cells[0]]),
            diffusivity_m2_s=[2e-18 * (i + 1) for i in range(6)],
            is_gj_insular=blocked,
        )
    ]
    species = {r["id"] for r in leaf["species"]}
    return deepcopy(
        dict(
            definition=raw,
            geometry=geometry,
            default=default,
            profiles=rows,
            ion_enabled=[
                ion in species and ion in ("Na", "K", "Cl", "Ca")
                for ion in ("Na", "K", "Cl", "Ca", "M", "P")
            ],
            enabled=True,
            is_ecm=False,
        )
    )
