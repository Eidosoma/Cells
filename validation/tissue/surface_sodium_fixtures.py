"""Synthetic NaV1.2/Kv1.5/Kir2.1 tissues; no physiological fit."""

from copy import deepcopy

from validation.tissue import surface_channel_fixtures as base

ARMS = base.ARMS


def definition(arm="open", *, backend="cpu", padded=True):
    raw = base.definition(arm, backend=backend, padded=padded)
    raw["model"]["id"] = "resolved_tissue@4"
    for index, patch in enumerate((0, 2)):
        channel = deepcopy(raw["model"]["channels"][patch])
        channel.update(
            id=f"sodium_{index}",
            species_id="Na",
            kinetic_law="betse_nav1p2_m3h_regularized@1",
            abundance=0.2 + 0.1 * index,
            initial_gate=[0.15 + 0.2 * index, 0.8 - 0.2 * index],
        )
        raw["model"]["channels"].append(channel)
        schedule = deepcopy(raw["experiment"]["channel_controls"][patch]["schedule"])
        raw["experiment"]["channel_controls"].append(
            dict(channel_id=channel["id"], schedule=schedule)
        )
    raw["execution"].update(dt=2.5e-6, max_steps=4096, channel_capacity=7 + int(padded))
    return raw
