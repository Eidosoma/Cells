"""Capture seven unchanged pinned BETSE CaV classes in their own environment.

The exact CaV2.2 singularity is retained as nonfinite source evidence. It is
not counted as a finite comparison and no source equation is repaired here.
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
from betse.science.channels import channelsabc, vg_ca


def capture():
    rows = {}
    for family in ("Cav1p2", "Cav1p3", "Cav2p1", "Cav2p2", "Cav2p3", "Cav3p1", "Cav3p3"):
        voltage = np.unique(
            np.r_[np.linspace(-0.120, 0.060, 61), 0.02, -0.010, -1e-5 - 1e-8, -1e-5, -1e-5 + 1e-8]
        )
        if family == "Cav2p2":
            voltage = voltage[np.abs(voltage - 0.02) > 1e-9]

        def pair(a, b):
            # Called only inside this iteration, before voltage can change.
            return np.stack([np.broadcast_to(value, voltage.shape) for value in (a, b)])  # noqa: B023

        channel = getattr(vg_ca, family)()
        channel.init(voltage, None, SimpleNamespace())
        initial = pair(channel.m, channel.h).copy()
        channel._calculate_state(voltage * 1000)
        row = dict(
            voltage_V=voltage.tolist(),
            initial=initial.tolist(),
            target=pair(channel._mInf, channel._hInf).tolist(),
            tau_s=(pair(channel._mTau, channel._hTau) / channel.time_unit).tolist(),
            powers=[channel._mpower, channel._hpower],
            ions=channel.ions,
            relative_permeability=channel.rel_perm,
            time_unit=channel.time_unit,
            traces=[],
        )
        for dt in (2.5e-6, 25e-6, 0.001):
            channel.m, channel.h = np.full(voltage.shape, 0.2), np.full(voltage.shape, 0.7)
            inputs, states, opening = [], [], []
            for step in range(32):
                v = np.roll(voltage, step // 8)
                channel.run(v, SimpleNamespace(dt=dt))
                inputs.append(v.tolist())
                states.append(pair(channel.m, channel.h).tolist())
                opening.append(channel.P.tolist())
            row["traces"].append(dict(dt_s=dt, voltage_V=inputs, gates=states, opening=opening))
        rows[family] = row
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        channel = vg_ca.Cav2p2()
        channel.init(np.array([0.02]), None, SimpleNamespace())
        initial = np.stack((channel.m, channel.h)).copy()
        channel._calculate_state(np.array([20.0]))
        probes = np.concatenate(
            (initial, np.stack((channel._mInf, channel._hInf, channel._mTau, channel._hTau)))
        )
    return dict(
        version=__version__,
        source_sha256={
            name: hashlib.sha256(Path(inspect.getfile(module)).read_bytes()).hexdigest()
            for name, module in (("vg_ca.py", vg_ca), ("channelsabc.py", channelsabc))
        },
        families=rows,
        singular_probes=dict(
            family="Cav2p2",
            voltage_mV=[20.0],
            fields=["initial_m", "initial_h", "m_target", "h_target", "m_tau_ms", "h_tau_ms"],
            values=[[float(x) if np.isfinite(x) else None for x in row] for row in probes],
            finite=np.isfinite(probes).tolist(),
            warnings=[str(w.message) for w in captured],
        ),
        cav3p1_branch=dict(
            source_argument_unit="mV",
            literal_threshold=-0.01,
            threshold_V=-1e-5,
            inferred_minus_10_mV_repair=False,
        ),
    )


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(capture(), indent=2, allow_nan=False) + "\n")
