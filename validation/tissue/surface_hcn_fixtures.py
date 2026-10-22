"""Synthetic HCN/NaV/Kv/Kir tissue panels with explicit divalent transport.

The small calcium pool and compatible fixed background are manufactured inputs,
not measured physiology. No owned ER chemistry is claimed by this family.
"""

import math
from copy import deepcopy

from validation.tissue import surface_sodium_fixtures as base

ARMS = base.ARMS
PERMEABILITIES = (("Na", 0.2), ("K", 1.0), ("Ca", 0.05))


def convert(raw):
    raw = deepcopy(raw)
    raw["model"]["id"] = "resolved_tissue@5"
    for channel in raw["model"]["channels"]:
        channel["permeant_ions"] = [
            dict(species_id=channel.pop("species_id"), relative_permeability=1.0)
        ]
    return raw


def definition(arm="open", *, backend="cpu", padded=True):
    raw = convert(base.definition(arm, backend=backend, padded=padded))
    model = raw["model"]
    model["species"].append(dict(id="Ca", valence=2))
    charge_per_fmol = 6.02214076e23 * 1.602176634e-19 * 1e-15
    for owners, concentration in (("cells", 0.0001), ("extracellular", 0.02)):
        for owner in model[owners]:
            owner["initial_amount_fmol"]["Ca"] = concentration * owner["volume_pL"]
            owner["fixed_charge_equivalent_fmol"] = owner[
                "initial_charge_C"
            ] / charge_per_fmol - math.fsum(
                row["valence"] * owner["initial_amount_fmol"][row["id"]] for row in model["species"]
            )
    for kind, key in (
        ("membranes", "permeability_m_per_s"),
        ("junctions", "permeability_m_per_s"),
        ("faces", "diffusivity_m2_per_s"),
    ):
        for route in model[kind]:
            route[key]["Ca"] = 0.0
    for index, family in enumerate((1, 2, 4)):
        channel = deepcopy(model["channels"][index])
        channel.update(
            id=f"hcn_{family}",
            kinetic_law=f"betse_hcn{family}_m@1",
            permeant_ions=[dict(species_id=s, relative_permeability=p) for s, p in PERMEABILITIES],
            abundance=0.12 + 0.08 * index,
            initial_gate=[0.35 + 0.1 * index, 0.7],
        )
        model["channels"].append(channel)
        raw["experiment"]["channel_controls"].append(
            dict(
                channel_id=channel["id"],
                schedule=deepcopy(raw["experiment"]["channel_controls"][index]["schedule"]),
            )
        )
    raw["execution"].update(channel_capacity=10 + int(padded), max_trace_bytes=2**31)
    raw["execution"]["material_balance_atol_fmol"]["Ca"] = 2e-11
    return raw
