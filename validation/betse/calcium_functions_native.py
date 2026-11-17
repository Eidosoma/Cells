"""Run pinned BETSE v1.5.0 calcium functions unchanged, in their separate environment.

Only the BETSE environment runs this file (/mnt/workspaces/Cells/venv-betse); a Cells test starts
it as a child process and compares the saved capture (AGENTS.md: BETSE runs unmodified, out of
process, and Cells is compared with its saved, extracted outputs):

    python -B calcium_functions_native.py REQUEST.json CAPTURE.json

The request lists cases of four kinds. The capture holds each case's outputs as the source
computes them, the BETSE version, and the SHA-256 of every source file used:
- "er_pump": sim_toolbox.pumpCaER(cCai, cCao, Vm, T, p);
- "plasma_pump": sim_toolbox.pumpCaATP(cCai, cCao, Vm, T, p, block), once per given block;
- "er_channels": EndoRetic.channels(er, sim, None, p), the ER release gate, either calcium-only
  ("absent": no network) or with IP3 from one named source (`IP3_SOURCES`);
- "cav1p2": vg_ca.Cav1p2's initial state, targets and time constants, and its semi-implicit clock
  (ChannelsABC.update_mh) run from a held gate.

Nothing is copied, patched or re-implemented: the inputs are plain stand-ins for the source's
simulation objects (its parameters, its `sim` and an ER holding only the two fields the gate
writes), as the other captures in this folder use.
"""

import hashlib
import inspect
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("MPLBACKEND", "Agg")  # endo_retic imports pyplot; no display here.

import numpy as np  # noqa: E402
from betse import __version__  # noqa: E402
from betse.science import sim_toolbox  # noqa: E402
from betse.science.channels import channelsabc, vg_ca  # noqa: E402
from betse.science.organelles import endo_retic  # noqa: E402

SOURCES = (
    ("sim_toolbox.py", sim_toolbox),
    ("endo_retic.py", endo_retic),
    ("vg_ca.py", vg_ca),
    ("channelsabc.py", channelsabc),
)
# Where EndoRetic.channels looks for IP3, in its order, and the two controls of that search.
IP3_SOURCES = ("molecules", "metabo", "grn", "priority", "missing", "absent")


def _array(values):
    return np.asarray(values, dtype=float)


def er_pump(case):
    flux = sim_toolbox.pumpCaER(
        _array(case["cCai"]),
        _array(case["cCao"]),
        _array(case["Vm"]),
        case["T"],
        SimpleNamespace(**case["parameters"]),
    )
    return {"flux": np.asarray(flux).tolist()}


def plasma_pump(case):
    flux = [
        np.asarray(
            sim_toolbox.pumpCaATP(
                _array(case["cCai"]),
                _array(case["cCao"]),
                _array(case["Vm"]),
                case["T"],
                SimpleNamespace(**case["parameters"]),
                block,
            )
        ).tolist()
        for block in case["blocks"]
    ]
    return {"blocks": case["blocks"], "flux": flux}


def er_channels(case):
    """The ER gate with IP3 from one source: each source the function searches, a higher-priority
    source that holds IP3 beside lower ones that also hold it ("priority"), a network with no IP3
    ("missing"), and no network at all ("absent", calcium-only)."""
    source = case["source"]
    if source not in IP3_SOURCES:
        raise ValueError("Unknown IP3 source " + repr(source))
    calcium = _array(case["calcium"])
    count = calcium.size
    sim = SimpleNamespace(
        iCa=0, cc_cells=calcium[None, :], cdl=count, molecules=None, metabo=None, grn=None
    )
    if case["ip3"] is not None:
        ip3 = _array(case["ip3"])
        molecules = SimpleNamespace(molecules={"IP3": object()}, cell_concs={"IP3": ip3})
        network = SimpleNamespace(core=SimpleNamespace(cell_concs={"IP3": ip3}))
        if source == "molecules":
            sim.molecules = molecules
        elif source in ("metabo", "grn"):
            # Empty higher-priority sources must fall through to the named network.
            sim.molecules = SimpleNamespace(molecules={}, cell_concs={})
            if source == "grn":
                sim.metabo = SimpleNamespace(core=SimpleNamespace(cell_concs={}))
            setattr(sim, source, network)
        elif source == "priority":
            sim.molecules = molecules
            sim.metabo = SimpleNamespace(core=SimpleNamespace(cell_concs={"IP3": ip3 * 9}))
            sim.grn = SimpleNamespace(core=SimpleNamespace(cell_concs={"IP3": ip3 * 17}))
        elif source == "missing":
            sim.grn = SimpleNamespace(core=SimpleNamespace(cell_concs={}))
    elif source != "absent":
        raise ValueError("Only the calcium-only form ('absent') takes no IP3")
    er = SimpleNamespace(
        Dm_channels=np.zeros((1, count)), Dm_er_base=np.full((1, count), float(case["base"]))
    )
    endo_retic.EndoRetic.channels(er, sim, None, SimpleNamespace(**case["parameters"]))
    return {
        "Dm_channels": er.Dm_channels.tolist(),
        "Dm_er_base": er.Dm_er_base.tolist(),
        "Dm_er": er.Dm_er.tolist(),
    }


def cav1p2(case):
    """Cav1p2's own initialization and state at the given voltages (V; the source takes mV), then
    its semi-implicit clock from a held gate for `duration_s` at each step in `dt_s`."""
    voltage = _array(case["voltage_V"])
    channel = vg_ca.Cav1p2()
    channel._init_state(1000 * voltage)
    initial = {"m": np.asarray(channel.m).tolist(), "h": np.asarray(channel.h).tolist()}
    channel._calculate_state(1000 * voltage)
    clocks = []
    for dt in case["dt_s"]:
        channel.m = np.full(voltage.shape, float(case["gate"]))
        channel.h = np.full(voltage.shape, float(case["gate"]))
        for _ in range(round(case["duration_s"] / dt)):
            channelsabc.ChannelsABC.update_mh(
                channel, SimpleNamespace(dt=dt), time_unit=channel.time_unit
            )
        clocks.append({"dt_s": dt, "m": channel.m.tolist(), "h": channel.h.tolist()})
    return {
        "initial": initial,
        "m_inf": np.asarray(channel._mInf).tolist(),
        "h_inf": np.asarray(channel._hInf).tolist(),
        "m_tau": np.asarray(channel._mTau).tolist(),
        "h_tau": np.asarray(channel._hTau).tolist(),
        "time_unit": channel.time_unit,
        "powers": [channel._mpower, channel._hpower],
        "clocks": clocks,
    }


KINDS = {
    "er_pump": er_pump,
    "plasma_pump": plasma_pump,
    "er_channels": er_channels,
    "cav1p2": cav1p2,
}


def capture(request):
    unknown = sorted(set(request) - set(KINDS))
    if unknown:
        raise ValueError("Unknown case kinds: " + ", ".join(unknown))
    return {
        "version": __version__,
        "source_sha256": {
            name: hashlib.sha256(Path(inspect.getfile(module)).read_bytes()).hexdigest()
            for name, module in SOURCES
        },
        **{kind: [KINDS[kind](case) for case in cases] for kind, cases in request.items()},
    }


if __name__ == "__main__":
    request = json.loads(Path(sys.argv[1]).read_text())
    Path(sys.argv[2]).write_text(json.dumps(capture(request), allow_nan=False) + "\n")
