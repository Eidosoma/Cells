"""Independent scalar Cav1.2/constant-field reference and pinned BETSE methods.

No Cells or JAX imports. The reference retains both ionic and chemical owners.
"""

import ast
import hashlib
import math
import os
from bisect import bisect_right
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from tests import reference_plasma_calcium as base

F, R = base.F, base.R
NATIVE_HASHES = {
    "vg_ca.py": "843d83f969ec53ba9322504f6ef0f699171c3c7c6e2caf03784de5bb17171dd6",
    "channelsabc.py": "ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4",
}


def native_channel():
    root = Path(
        os.environ.get(
            "CELLS_CAV_NATIVE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0/betse/science/channels"
        )
    )
    namespace = {"np": np, "logs": SimpleNamespace(log_info=lambda *args: None)}
    for name, expected in NATIVE_HASHES.items():
        source = (root / name).read_bytes()
        if hashlib.sha256(source).hexdigest() != expected:
            raise ValueError("Pinned BETSE calcium gate source changed")
        tree = ast.parse(source)
        owner = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == ("Cav1p2" if name == "vg_ca.py" else "ChannelsABC")
        )
        if name == "vg_ca.py":
            owner.bases = []
            selected = [owner]
        else:
            selected = [
                n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "update_mh"
            ]
        exec(
            compile(ast.Module(body=selected, type_ignores=[]), str(root / name), "exec"), namespace
        )
    return namespace["Cav1p2"](), namespace["update_mh"]


def scalar_kinetics(voltage):
    # Direct native mV/ms expressions, separate from production stable sigmoids.
    v = 1000 * voltage - 10
    return (
        np.array([1 / (1 + math.exp(-(v + 30) / 6)), 1 / (1 + math.exp((v + 80) / 6.4))]),
        np.array([5 + 20 / (1 + math.exp((v + 25) / 5)), 20 + 50 / (1 + math.exp((v + 40) / 7))])
        / 1000,
    )


def scalar_flux(ci, co, voltage, temperature, area, permeability):
    x = 2 * F * voltage / (R * temperature)
    b = 1 - x / 2 + x * x / 12 - x**4 / 720 + x**6 / 30240 if abs(x) < 1e-3 else x / math.expm1(x)
    flux = area * permeability / 1e-15 * (co * b - ci * (b + x))
    mu = R * temperature * math.log(ci / co) + 2 * F * voltage
    return flux, -1e-3 * flux * mu


class System(base.System):
    def __init__(self, raw):
        super().__init__(raw)
        self.channels = raw["model"]["calcium_channels"]
        self.channel_controls = {
            r["channel_id"]: r["schedule"] for r in raw["experiment"]["calcium_channel_controls"]
        }
        self.extra_times |= {p["time"] for s in self.channel_controls.values() for p in s}
        self.channel_offset = self.size
        n = len(self.channels)
        self.size += 4 * n
        self.shapes.update(
            calcium_gate=(2, n),
            calcium_channel_transferred=(n,),
            calcium_channel_dissipated_energy_pJ=(n,),
        )

    def initial(self):
        y = super().initial()
        n = len(self.channels)
        y[self.channel_offset : self.channel_offset + 2 * n] = np.array(
            [[c["initial_gate"][key] for c in self.channels] for key in ("m", "h")]
        ).ravel()
        return y

    def unpack(self, y):
        result = super().unpack(y[: self.channel_offset])
        start, n = self.channel_offset, len(self.channels)
        return result | {
            "calcium_gate": y[start : start + 2 * n].reshape(2, n),
            "calcium_channel_transferred": y[start + 2 * n : start + 3 * n],
            "calcium_channel_dissipated_energy_pJ": y[start + 3 * n : start + 4 * n],
        }

    def rhs(self, y, time, *, channel_levels=None):
        derivative = super().rhs(y[: self.channel_offset], time, channel_levels=channel_levels)
        state = self.unpack(y)
        external = base.base.spatial.unpack(self.context, derivative[: self.offsets[0]])
        voltage = base.base.spatial.voltage(self.context, state["amount_increment"])
        outside = self.context["outside_initial"] + state["extracellular_amount_increment"]
        dg, fluxes, energies = [], [], []
        for j, channel in enumerate(self.channels):
            owner = next(
                i
                for i, c in enumerate(self.context["cells"])
                if c["membrane"]["id"] == channel["membrane_id"]
            )
            destination = next(
                i
                for i, c in enumerate(self.context["outside"])
                if c["id"] == self.context["cells"][owner]["membrane"]["outside"]
            )
            store = self.stores[owner]
            a, b = self.offsets[owner : owner + 2]
            ca = store.ids.index(self.context["ids"][self.ca])
            ci = (store.n0 + store.unpack(y[a:b])[0])[ca, store.cy] / store.volume[store.cy]
            co = outside[self.ca, destination] / self.context["outside_volume"][destination]
            targets, tau = scalar_kinetics(voltage[owner])
            g = state["calcium_gate"][:, j]
            dg.append((targets - g) / tau)
            controls = self.channel_controls[channel["id"]]
            availability = controls[bisect_right([p["time"] for p in controls], time) - 1][
                "availability"
            ]
            permeability = (
                channel["max_permeability_m_per_s"]
                * channel["abundance"]
                * availability
                * g[0] ** 2
                * g[1]
            )
            f, e = scalar_flux(
                ci,
                co,
                voltage[owner],
                self.context["model"]["temperature_K"],
                self.context["cells"][owner]["membrane"]["area_m2"],
                permeability,
            )
            external["amount_increment"][self.ca, owner] += f
            external["extracellular_amount_increment"][self.ca, destination] -= f
            store.unpack(derivative[a:b])[0][ca, store.cy] += f
            fluxes.append(f)
            energies.append(e)
        return np.r_[derivative, np.asarray(dg).T.ravel(), fluxes, energies]


def reference(raw, requested, **kwargs):
    return base.base.reference(raw, requested, system_class=System, **kwargs)


physical_energy_derivative = base.physical_energy_derivative
