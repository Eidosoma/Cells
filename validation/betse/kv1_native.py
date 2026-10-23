"""Execute unchanged pinned BETSE Kv1.1–Kv1.6 in its separate environment."""

import hashlib
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from betse import __version__
from betse.science.channels import channelsabc, vg_k


def capture():
    voltage = np.linspace(-0.120, 0.060, 61)

    def pair(a, b):
        return np.stack([np.broadcast_to(value, voltage.shape) for value in (a, b)])

    rows = {}
    for family in (1, 2, 3, 4, 5, 6):
        channel = getattr(vg_k, f"Kv1p{family}")()
        channel.init(voltage, None, SimpleNamespace())
        initial = pair(channel.m, channel.h).copy()
        channel._calculate_state(voltage * 1000)
        row = dict(
            initial=initial.tolist(),
            target=pair(channel._mInf, channel._hInf).tolist(),
            tau_s=(pair(channel._mTau, channel._hTau) / channel.time_unit).tolist(),
            powers=[channel._mpower, channel._hpower],
            ions=channel.ions,
            relative_permeability=channel.rel_perm,
            time_unit=channel.time_unit,
            traces=[],
        )
        for dt in (25e-6, 0.0001, 0.001):
            channel.m, channel.h = np.full(voltage.shape, 0.2), np.full(voltage.shape, 0.7)
            inputs, states, opening = [], [], []
            for step in range(32):
                v = np.roll(voltage, step // 8)
                channel.run(v, SimpleNamespace(dt=dt))
                inputs.append(v.tolist())
                states.append(pair(channel.m, channel.h).tolist())
                opening.append(channel.P.tolist())
            row["traces"].append(dict(dt_s=dt, voltage_V=inputs, gates=states, opening=opening))
        rows[str(family)] = row
    return {
        "version": __version__,
        "source_sha256": {
            name: hashlib.sha256(Path(inspect.getfile(module)).read_bytes()).hexdigest()
            for name, module in (("vg_k.py", vg_k), ("channelsabc.py", channelsabc))
        },
        "voltage_V": voltage.tolist(),
        "families": rows,
    }


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(capture(), indent=2, allow_nan=False) + "\n")
