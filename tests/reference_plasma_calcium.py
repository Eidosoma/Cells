"""Independent scalar plasma rates/scatter on the spatial calcium reference.

No Cells or JAX imports. Native PMCA extraction is bound to the pinned source;
scalar NCX uses direct forward/reverse products, unlike production log kinetics.
"""

import ast
import hashlib
import math
import os
from bisect import bisect_right
from pathlib import Path

import numpy as np

from tests import reference_spatial_calcium as base
from tests.reference_er_calcium import NATIVE_HASHES, F, R


def native_pmca():
    root = Path(
        os.environ.get("CELLS_ER_NATIVE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0/betse/science")
    )
    path = root / "sim_toolbox.py"
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != NATIVE_HASHES[path.name]:
        raise ValueError("Pinned PMCA source changed")
    tree = ast.parse(data)
    functions = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in ("pumpCaATP", "no_negs")
    ]
    namespace = {"np": np, "BetseSimUnstableException": ValueError}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["pumpCaATP"]


def scalar_rates(ni, no, ci, co, voltage, temperature, pump, exchanger, availability):
    rt = R * temperature
    pmca = gp = drive = ncx = gx = 0.0
    if pump is not None:
        drive = pump["delta_g0_J_per_mol"] + rt * math.log(
            pump["adp_mM"] * pump["pi_mM"] / pump["atp_mM"]
        )
        gp = drive + rt * math.log(co / ci) - 2 * F * voltage
        forward = (
            ci / (pump["km_ca_mM"] + ci) * pump["atp_mM"] / (pump["km_atp_mM"] + pump["atp_mM"])
        )
        pmca = pump["capacity_fmol_per_s"] * availability[0] * forward * (1 - math.exp(gp / rt))
    if exchanger is not None:
        a, b = ni / exchanger["km_na_mM"], no / exchanger["km_na_mM"]
        c, d = ci / exchanger["km_ca_mM"], co / exchanger["km_ca_mM"]
        forward, reverse = (
            b**3 * c * math.exp(-F * voltage / (2 * rt)),
            a**3 * d * math.exp(F * voltage / (2 * rt)),
        )
        ncx = (
            exchanger["capacity_fmol_per_s"]
            * availability[1]
            * (forward - reverse)
            / ((1 + a**3 + b**3) * (1 + c + d))
        )
        gx = rt * math.log((ni / no) ** 3 * co / ci) + F * voltage
    return pmca, ncx, gp, gx, drive


class System(base.System):
    def __init__(self, raw):
        super().__init__(raw)
        transport = raw["model"]["plasma_transport"]
        self.routes = transport["membranes"]
        self.ca, self.na = (
            self.context["ids"].index(transport[k]) for k in ("calcium_species", "sodium_species")
        )
        self.plasma_controls = {
            c["membrane_id"]: c["schedule"] for c in raw["experiment"]["plasma_controls"]
        }
        self.extra_times = {
            c["time"] for schedule in self.plasma_controls.values() for c in schedule
        }
        self.base_size = self.size
        n = len(self.routes)
        self.size += 4 * n
        self.shapes.update(
            plasma_pump_cycles=(n,), plasma_exchange_cycles=(n,), plasma_dissipated_energy_pJ=(2, n)
        )

    def unpack(self, y):
        result = super().unpack(y)
        start, n = self.base_size, len(self.routes)
        result.update(
            plasma_pump_cycles=y[start : start + n],
            plasma_exchange_cycles=y[start + n : start + 2 * n],
            plasma_dissipated_energy_pJ=y[start + 2 * n :].reshape(2, n),
        )
        return result

    def rhs(self, y, time, *, channel_levels=None):
        derivative = super().rhs(y, time, channel_levels=channel_levels)
        state = base.spatial.unpack(self.context, y[: self.offsets[0]])
        external = base.spatial.unpack(self.context, derivative[: self.offsets[0]])
        voltage = base.spatial.voltage(self.context, state["amount_increment"])
        outside = self.context["outside_initial"] + state["extracellular_amount_increment"]
        pmca, ncx, dissipation = [], [], []
        for route in self.routes:
            owner = next(
                i
                for i, c in enumerate(self.context["cells"])
                if c["membrane"]["id"] == route["membrane_id"]
            )
            destination = next(
                i
                for i, c in enumerate(self.context["outside"])
                if c["id"] == self.context["cells"][owner]["membrane"]["outside"]
            )
            store = self.stores[owner]
            a, b = self.offsets[owner : owner + 2]
            concentrations = (store.n0 + store.unpack(y[a:b])[0])[:, store.cy] / store.volume[
                store.cy
            ]
            names = self.context["ids"]
            ci, ni = (concentrations[store.ids.index(names[i])] for i in (self.ca, self.na))
            co, no = (
                outside[[self.ca, self.na], destination]
                / self.context["outside_volume"][destination]
            )
            controls = self.plasma_controls[route["membrane_id"]]
            held = controls[bisect_right([c["time"] for c in controls], time) - 1]
            p, x, gp, gx, _ = scalar_rates(
                ni,
                no,
                ci,
                co,
                voltage[owner],
                self.context["model"]["temperature_K"],
                route["pump"],
                route["exchanger"],
                (held["pump"], held["exchanger"]),
            )
            for i, amount in ((self.ca, -p - x), (self.na, 3 * x)):
                external["amount_increment"][i, owner] += amount
                external["extracellular_amount_increment"][i, destination] -= amount
                store.unpack(derivative[a:b])[0][store.ids.index(names[i]), store.cy] += amount
            pmca.append(p)
            ncx.append(x)
            dissipation.append([-1e-3 * p * gp, -1e-3 * x * gx])
        return np.r_[derivative, pmca, ncx, np.asarray(dissipation).T.ravel()]


def reference(raw, requested, **kwargs):
    return base.reference(raw, requested, system_class=System, **kwargs)


physical_energy_derivative = base.physical_energy_derivative
