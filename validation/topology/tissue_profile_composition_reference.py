"""Independent nested property preparation and existing complete parent equations."""

from copy import deepcopy
from importlib import import_module

from validation.topology import tissue_profile_preparation_reference as direct

REFERENCES = {
    **{f"ionic_v{i}": "validation.tissue.surface_kinetic_reference" for i in range(2, 12)},
    "calcium": "validation.tissue.surface_calcium_reference",
    "fuel": "validation.tissue.surface_calcium_energy_reference",
    "transport": "validation.tissue.calcium_energy_network_transport_reference",
    "mitochondria": "validation.tissue.calcium_energy_mitochondria_reference",
    "calcium_water": "validation.tissue.calcium_water_reference",
    "fuel_water": "validation.tissue.calcium_energy_water_reference",
    "water": "validation.tissue.surface_water_reference",
    "kinetic_water": "validation.tissue.surface_water_kinetic_reference",
    "energy": "validation.tissue.surface_energy_reference",
    "morris_energy": "validation.tissue.surface_energy_reference",
    "energy_water": "validation.tissue.surface_energy_water_reference",
    "morris_water": "validation.tissue.surface_water_kinetic_reference",
    "morris_energy_water": "validation.tissue.surface_energy_water_reference",
    "regulation_v1": "validation.regulation.integrated_network_regulation_reference",
    "regulation_v2": "validation.regulation.integrated_network_regulation_v2_reference",
}


def equations(family):
    return import_module(REFERENCES[family])


def prepare(inputs):
    result = deepcopy(inputs["definition"])
    nested = "ionic" in result["model"]
    leaf = result["model"]["ionic"] if nested else result["model"]
    local = deepcopy(inputs)
    local["definition"] = {"model": deepcopy(leaf)}
    expected = direct.prepare(local)
    if nested:
        result["model"]["ionic"] = expected["definition"]["model"]
    else:
        result["model"] = expected["definition"]["model"]
    return dict(
        definition=result,
        profiles=expected["profile_result"],
        insular_junction_weights=expected["insular_junction_weights"],
    )


def owners(raw):
    m = raw["model"]
    leaf = m.get("ionic", m)
    return dict(
        cells={
            r["id"]: dict(
                volume=r["volume_pL"],
                amounts=deepcopy(r["initial_amount_fmol"]),
                charge=r["initial_charge_C"],
            )
            for r in leaf["cells"]
        },
        exterior={
            r["id"]: dict(volume=r["volume_pL"], amounts=deepcopy(r["initial_amount_fmol"]))
            for r in leaf["extracellular"]
        },
        stores={
            r["cell_id"]: {
                c["id"]: dict(volume=c["volume_pL"], amounts=deepcopy(c["initial_amount_fmol"]))
                for c in r["model"]["compartments"]
            }
            for r in m.get("stores", [])
        },
        fuel={
            r["id"]: dict(owner=r["cell_id"], amounts=deepcopy(r["initial_amount_fmol"]))
            for r in m.get("energy_pools", [])
        },
        mitochondria={
            r["id"]: dict(
                owner=r["cell_id"],
                volume=r["volume_pL"],
                amounts=deepcopy(r["initial_amount_fmol"]),
                voltage=r["initial_voltage_V"],
            )
            for r in m.get("mitochondria", {}).get("compartments", [])
        },
        water={r["compartment_id"]: deepcopy(r) for r in m.get("water_compartments", [])},
        gates={r["id"]: deepcopy(r.get("initial_gate")) for r in leaf.get("channels", [])},
        junction_gates={r["id"]: deepcopy(r.get("gate")) for r in leaf["junctions"]},
    )
