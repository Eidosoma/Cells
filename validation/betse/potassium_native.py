"""Small external-process capture of unmodified pinned BETSE channel methods.

Run with the separate BETSE environment. No upstream source is vendored.
"""

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
    voltage = np.linspace(-0.120, 0.060, 37)
    output = dict(
        version=__version__,
        source_sha256={
            name: hashlib.sha256(Path(inspect.getfile(module)).read_bytes()).hexdigest()
            for name, module in (("vg_k.py", vg_k), ("channelsabc.py", channelsabc))
        },
        voltage_V=voltage.tolist(),
        laws={},
    )
    for cls in (vg_k.Kv1p5, vg_k.Kir2p1):
        channel = cls()
        channel.init(voltage, None, SimpleNamespace())
        initial = np.stack((channel.m, channel.h)).copy()
        channel._calculate_state(voltage * 1000)
        target = np.stack((channel._mInf, channel._hInf))
        tau = np.stack((channel._mTau, channel._hTau)) / channel.time_unit
        traces = []
        for dt in (25e-6, 12.5e-6, 6.25e-6):
            channel.m, channel.h = np.full(voltage.shape, 0.2), np.full(voltage.shape, 0.7)
            history, opening, inputs = [], [], []
            for step in range(32):
                v = np.roll(voltage, step // 8)
                channel.run(v, SimpleNamespace(dt=dt))
                inputs.append(v.tolist())
                history.append(np.stack((channel.m, channel.h)).tolist())
                opening.append(channel.P.tolist())
            traces.append(dict(dt_s=dt, voltages_V=inputs, gates=history, opening=opening))
        output["laws"][cls.__name__] = dict(
            initial=initial.tolist(),
            target=target.tolist(),
            tau_s=tau.tolist(),
            powers=[channel._mpower, channel._hpower],
            traces=traces,
        )
    return output


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(capture(), indent=2, allow_nan=False) + "\n")
