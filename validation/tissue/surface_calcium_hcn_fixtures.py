"""Synthetic HCN/owned-calcium/assembly composition with no parameter fitting."""

from copy import deepcopy

from validation.tissue import surface_calcium_sodium_fixtures as base
from validation.tissue import surface_hcn_fixtures as hcn

ARMS = base.ARMS


def definition(arm="baseline", *, backend="cpu", padded=True):
    raw = base.definition(arm, backend=backend, padded=padded)
    raw["model"]["id"] = "resolved_calcium@4"
    ion = hcn.convert({"model": raw["model"]["ionic"]})["model"]
    raw["model"]["ionic"] = ion
    added = hcn.definition("closed", backend=backend, padded=padded)["model"]["channels"][7:]
    for index, population in enumerate(added):
        ion["channels"].append(population)
        raw["experiment"]["channel_controls"].append(
            dict(
                channel_id=population["id"],
                schedule=deepcopy(raw["experiment"]["channel_controls"][index]["schedule"]),
            )
        )
    raw["execution"]["channel_capacity"] = len(ion["channels"]) + int(padded)
    return raw


def assembly_definition(*, backend="cpu"):
    raw = base.assembly_definition(backend=backend)
    raw["ionic"] = definition(backend=backend)
    return raw
