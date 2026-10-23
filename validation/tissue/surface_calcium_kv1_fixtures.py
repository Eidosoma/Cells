"""Synthetic complete Kv1 catalog with shared HCN and owned calcium/ER.

The five added populations exercise different patches and both chemical owners.
Inputs are manufactured verification cases, with no physiological parameter fit.
"""

from copy import deepcopy

from validation.tissue import surface_calcium_hcn_fixtures as base

ARMS = base.ARMS


def definition(arm="baseline", *, backend="cpu", padded=True):
    raw = base.definition(arm, backend=backend, padded=padded)
    raw["model"]["id"] = "resolved_calcium@5"
    ion = raw["model"]["ionic"]
    ion["id"] = "resolved_tissue@6"
    for index, family in enumerate((1, 2, 3, 4, 6)):
        population = deepcopy(ion["channels"][index % 4])
        population.update(
            id=f"kv1_{family}",
            kinetic_law=f"betse_kv1p{family}_mh{'2' if family == 1 else ''}@1",
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
