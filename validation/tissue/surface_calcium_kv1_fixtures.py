"""Synthetic complete Kv1 catalog with shared HCN and owned calcium/ER.

The five added populations exercise different patches and both chemical owners.
Inputs are manufactured verification cases, with no physiological parameter fit.
"""

from copy import deepcopy

from validation.tissue import surface_calcium_hcn_fixtures as base

ARMS = base.ARMS
KV1 = {
    1: "kv1p1_mh2@1",
    2: "kv1p2_mh@1",
    3: "kv1p3_mh@1",
    4: "kv1p4_mh@1",
    6: "kv1p6_mh@1",
}


def definition(arm="baseline", *, backend="cpu", padded=True):
    raw = base.definition(arm, backend=backend, padded=padded)
    raw["model"]["id"] = "resolved_calcium@5"
    ion = raw["model"]["ionic"]
    ion["id"] = "resolved_tissue@6"
    for index, (family, law) in enumerate(KV1.items()):
        population = deepcopy(ion["channels"][index % 4])
        population.update(
            id=f"kv1_{family}",
            kinetic_law=law,
            initial_gate=[0.25 + 0.1 * index, 0.65 - 0.05 * index],
            abundance=0.10 + 0.04 * index,
        )
        ion["channels"].append(population)
        raw["experiment"]["channel_controls"].append(
            dict(
                channel_id=population["id"],
                schedule=deepcopy(raw["experiment"]["channel_controls"][index % 4]["schedule"]),
            )
        )
    raw["execution"]["channel_capacity"] = len(ion["channels"]) + int(padded)
    return raw


def assembly_definition(*, backend="cpu"):
    raw = base.assembly_definition(backend=backend)
    raw["ionic"] = definition(backend=backend)
    return raw
