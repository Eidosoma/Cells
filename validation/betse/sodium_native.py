"""Capture unmodified pinned BETSE Nav1p2 in its separate environment.

Nonfinite source values at removable singularities are recorded explicitly,
not converted into passing finite comparisons. No upstream code is vendored.
"""

import hashlib
import inspect
import json
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from betse import __version__
from betse.science.channels import channelsabc, vg_na


def capture():
    singular = np.asarray([-0.025, -0.040, -0.065000123])
    voltage = np.linspace(-0.120, 0.060, 37)
    voltage = voltage[np.all(np.abs(voltage[:, None] - singular) > 1e-9, axis=1)]
    channel = vg_na.Nav1p2()
    channel.init(voltage, None, SimpleNamespace())
    initial = np.stack((channel.m, channel.h)).copy()
    channel._calculate_state(voltage * 1000)
    target = np.stack((channel._mInf, channel._hInf)).copy()
    tau = np.stack((channel._mTau, channel._hTau)) / channel.time_unit
    traces = []
    for dt in (5e-6, 2.5e-6, 1.25e-6):
        channel.m, channel.h = np.full(voltage.shape, 0.2), np.full(voltage.shape, 0.7)
        history, opened, inputs = [], [], []
        for step in range(32):
            v = np.roll(voltage, step // 8)
            channel.run(v, SimpleNamespace(dt=dt))
            inputs.append(v.tolist())
            history.append(np.stack((channel.m, channel.h)).tolist())
            opened.append(channel.P.tolist())
        traces.append(dict(dt_s=dt, voltages_V=inputs, gates=history, opening=opened))
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        # Direct mV probes distinguish exact native singularities from roundoff
        # introduced by converting the input voltage into native units.
        probe_mV = np.asarray([-25.0, -40.0, -65.000123])
        channel._calculate_state(probe_mV)
        probes = np.stack((channel._mInf, channel._hInf, channel._mTau, channel._hTau))
    return dict(
        version=__version__,
        source_sha256={
            name: hashlib.sha256(Path(inspect.getfile(module)).read_bytes()).hexdigest()
            for name, module in (("vg_na.py", vg_na), ("channelsabc.py", channelsabc))
        },
        voltage_V=voltage.tolist(),
        initial=initial.tolist(),
        target=target.tolist(),
        tau_s=tau.tolist(),
        powers=[channel._mpower, channel._hpower],
        traces=traces,
        singular_probes=dict(
            voltage_mV=probe_mV.tolist(),
            fields=["m_target", "h_target", "m_tau_ms", "h_tau_ms"],
            values=[[float(x) if np.isfinite(x) else None for x in row] for row in probes],
            finite=np.isfinite(probes).tolist(),
            warnings=[str(w.message) for w in recorded],
        ),
    )


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(capture(), indent=2, allow_nan=False) + "\n")
