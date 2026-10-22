"""Synthetic NaV/potassium/owned-calcium composition, without parameter fitting."""

from copy import deepcopy

from validation.tissue import surface_calcium_channel_fixtures as base
from validation.tissue import surface_sodium_fixtures as sodium

ARMS = base.ARMS


def definition(arm="baseline", *, backend="cpu", padded=True):
    raw = base.definition(arm, backend=backend, padded=padded)
    mixed = sodium.definition("closed", backend=backend, padded=padded)
    raw["model"]["id"] = "resolved_calcium@3"
    ion = raw["model"]["ionic"]
    ion["id"] = "resolved_tissue@4"
    ion["channels"] = mixed["model"]["channels"]
    controls = raw["experiment"]["channel_controls"]
    for index, patch in enumerate((0, 2)):
        controls.append(
            dict(
                channel_id=f"sodium_{index}",
                schedule=deepcopy(controls[patch]["schedule"]),
            )
        )
    for key in ("dt", "max_steps", "channel_capacity"):
        raw["execution"][key] = mixed["execution"][key]
    # Full 0.625-us refinement has a conservative trace estimate below 2 GiB.
    # The older 512-MiB allowance only covers this composition's default grid.
    raw["execution"]["max_trace_bytes"] = 2**31
    return raw


def assembly_definition(*, backend="cpu"):
    raw = base.assembly_definition(backend=backend)
    raw["ionic"] = definition(backend=backend)
    return raw
