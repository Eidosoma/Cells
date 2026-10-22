"""Mixed potassium channel worlds; synthetic inputs, not biological calibration."""

import copy

from validation.tissue import surface_kinetic_fixtures as base

ARMS = base.ARMS


def definition(arm="open", *, backend="cpu", padded=True):
    raw = base.definition(arm, backend=backend, padded=padded)
    raw["model"]["id"] = "resolved_tissue@3"
    channels = raw["model"]["channels"]
    for i in (1, 3):
        channels[i]["kinetic_law"] = "betse_kir2p1_mh2@1"
    # Two distinct populations on patch zero exercise additive material transfer
    # while retaining separate intrinsic gates and transfer/energy ledgers.
    second = copy.deepcopy(channels[0])
    second.update(id="channel_4", kinetic_law="betse_kir2p1_mh2@1", initial_gate=[0.65, 0.35])
    channels.append(second)
    controls = raw["experiment"]["channel_controls"]
    controls.append(dict(channel_id="channel_4", schedule=copy.deepcopy(controls[0]["schedule"])))
    raw["execution"].update(dt=25e-6, max_steps=1024, channel_capacity=5 + int(padded))
    return raw
