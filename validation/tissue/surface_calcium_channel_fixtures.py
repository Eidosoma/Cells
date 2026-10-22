"""Synthetic mixed-potassium/calcium composition, without parameter refitting."""

from copy import deepcopy

from validation.tissue import surface_calcium_fixtures as base
from validation.tissue import surface_channel_fixtures as potassium

ARMS = base.ARMS


def definition(arm="baseline", *, backend="cpu", padded=True):
    raw = base.definition(arm, backend=backend, padded=padded)
    mixed = potassium.definition("closed", backend=backend, padded=padded)
    raw["model"]["id"] = "resolved_calcium@2"
    ion = raw["model"]["ionic"]
    ion["id"] = "resolved_tissue@3"
    ion["channels"] = mixed["model"]["channels"]
    controls = raw["experiment"]["channel_controls"]
    controls.append(dict(channel_id="channel_4", schedule=deepcopy(controls[0]["schedule"])))
    raw["execution"]["channel_capacity"] = mixed["execution"]["channel_capacity"]
    return raw


def assembly_definition(*, backend="cpu"):
    raw = base.assembly_definition(backend=backend)
    raw["ionic"] = definition(backend=backend)
    return raw
