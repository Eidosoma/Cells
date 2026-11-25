"""Scalar arithmetic on a junction-only world: the order of a scheme and its energy residual.

Two steps of the rehearsal are chosen by arithmetic and not by a run of a candidate: the steps of
the IMEX family (at which its second order is resolved) and the step of the world that the engine's
own energy check stops. Both worlds have cells that face one outside region, gated junctions, no
leak, no channel, no pump and no face, so every rate is explicit in ARS(2,2,2) as in RK4, and the
scheme is its explicit tableau (Ascher, Ruuth and Spiteri 1997). The equations are the legacy
engine's (constant-field junction flux, one-gate relaxation); the code is this file's own. What it
gives is an ESTIMATE of a candidate's differences, never a measurement of one.

    estimate.py order WORLD STEP1 STEP2 STEP3     the order of ARS(2,2,2) at three steps, entry by
    entry
    estimate.py energy WORLD STEP                 RK4's energy residual at each accepted row
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules  # noqa: E402

GAMMA = 1.0 - 1.0 / math.sqrt(2.0)
DELTA = 1.0 - 1.0 / (2.0 * GAMMA)


class World:
    def __init__(self, ionic):
        b = self.b = ionic
        self.x = list(b["species"])
        self.z = np.array([b["species"][x] for x in self.x], float)
        self.RT = rules.R * b["temperature_K"]
        self.cells = list(b["cells"])
        c = b["cells"]
        self.vol = np.array([c[k]["volume_pL"] for k in self.cells])
        self.n0 = np.array([[c[k]["initial_amount_fmol"][x] for x in self.x] for k in self.cells])
        mem = {m["inside"]: m for m in b["membranes"].values()}
        self.cap = np.array([mem[k]["capacitance_F"] for k in self.cells])
        self.v0 = np.array([c[k]["initial_voltage_V"] for k in self.cells])
        j = b["junctions"]
        self.jid = list(j)
        self.a = np.array([self.cells.index(j[k]["from_cell"]) for k in self.jid])
        self.c = np.array([self.cells.index(j[k]["to_cell"]) for k in self.jid])
        self.area = np.array([j[k]["area_m2"] for k in self.jid])
        self.perm = np.array([[j[k]["permeability_m_per_s"][x] for x in self.x] for k in self.jid])
        self.thr = np.array([j[k]["gate"]["threshold_voltage_V"] for k in self.jid])
        self.lo = np.array([j[k]["gate"]["minimum_open_fraction"] for k in self.jid])
        self.g0 = np.array([j[k]["gate"]["initial_gate"] for k in self.jid])
        ctrl = b["controls"]["junction"] or {}
        self.schedule = [ctrl.get(k, [[0.0, 1.0]]) for k in self.jid]
        self.end = b["end_s"]

    def opening(self, t):
        out = []
        for s in self.schedule:
            value = s[0][1]
            for time, v in s:
                if time <= t + 4 * math.ulp(t):
                    value = v
            out.append(value)
        return np.array(out)

    def start(self):
        nj, nx = len(self.jid), len(self.x)
        return [np.zeros((len(self.cells), nx)), np.zeros((nj, nx)), self.g0.copy(), np.zeros(nj)]

    def voltage(self, dn):
        return self.v0 + rules.F * rules.FMOL / self.cap * (dn * self.z).sum(1)

    def rates(self, s, opening):
        dn, _, gate, _ = s
        v = self.voltage(dn)
        dv = v[self.a] - v[self.c]
        n = self.n0 + dn
        conc = n / self.vol[:, None]
        ca, cb = conc[self.a], conc[self.c]
        x = self.z[None, :] * rules.F * dv[:, None] / self.RT

        def b(q):
            return np.where(
                np.abs(q) < 1e-4, 1 - q / 2 + q**2 / 12, q / np.expm1(np.where(q == 0, 1, q))
            )

        flux = (
            self.area[:, None]
            * self.perm
            * (opening * gate)[:, None]
            / rules.FMOL
            * (ca * b(-x) - cb * b(x))
        )
        mu = self.RT * np.log(ca / cb) + self.z[None, :] * rules.F * dv[:, None]
        heat = 1e-3 * (flux * mu).sum(1)
        ddn = np.zeros_like(dn)
        np.add.at(ddn, self.a, -flux)
        np.add.at(ddn, self.c, flux)
        shift = np.abs(dv) - self.thr
        alpha = 1.3 * np.exp(-77.0 * shift)
        beta = 20.0 / (1 + np.exp(-(math.log(0.065) + 140.0 * shift)))
        dg = alpha * (1 - gate) - beta * (gate - self.lo)
        return [ddn, flux, dg, heat]

    def rk4(self, s, h, o):
        k1 = self.rates(s, o)
        k2 = self.rates([y + 0.5 * h * d for y, d in zip(s, k1, strict=True)], o)
        k3 = self.rates([y + 0.5 * h * d for y, d in zip(s, k2, strict=True)], o)
        k4 = self.rates([y + h * d for y, d in zip(s, k3, strict=True)], o)
        return [
            y + h / 6 * (a + 2 * b + 2 * c + d)
            for y, a, b, c, d in zip(s, k1, k2, k3, k4, strict=True)
        ]

    def ars222(self, s, h, o):
        k1 = self.rates(s, o)
        k2 = self.rates([y + h * GAMMA * d for y, d in zip(s, k1, strict=True)], o)
        return [y + h * (DELTA * a + (1 - DELTA) * b) for y, a, b in zip(s, k1, k2, strict=True)]

    def run(self, scheme, h):
        """[(t, state)] at every accepted step."""
        n = rules.grid_steps(self.end, h)
        s, out = self.start(), []
        step = getattr(self, scheme)
        out.append((0.0, s))
        for i in range(n):
            s = step(s, h, self.opening(i * h))
            out.append(((i + 1) * h, s))
        return out

    def energy(self, s):
        dn, _, _, heat = s
        n0, n = self.n0, self.n0 + dn
        chemical = (
            1e-3
            * self.RT
            * (dn * (np.log(n0 / self.vol[:, None]) - 1) + n * np.log1p(dn / n0)).sum()
        )
        dv = rules.F * rules.FMOL / self.cap * (dn * self.z).sum(1)
        electric = 0.5e12 * (self.cap * dv * (2 * self.v0 + dv)).sum()
        return chemical + electric + heat.sum()


def entries(world, rows, times):
    """{entry: array over (time, entity)} at the compared times."""
    keep = {}
    index = {
        round(t / times["spacing"]): s
        for t, s in rows
        if abs(t / times["spacing"] - round(t / times["spacing"])) < 1e-6
    }
    keys = sorted(index)
    for i, x in enumerate(world.x):
        keep[f"n_cell_{x}"] = np.array([index[k][0][:, i] for k in keys])
        keep[f"junction_{x}"] = np.array([index[k][1][:, i] for k in keys])
    keep["junction_gate"] = np.array([index[k][2] for k in keys])
    keep["heat_junction"] = np.array([index[k][3] for k in keys])
    keep["voltage"] = np.array([world.voltage(index[k][0]) for k in keys])
    return keep


def order(world, ionic, steps, spacing, consumer="integrated", p=2.0):
    derived = rules.derived(consumer, ionic)
    scales, refs = derived["scales"], derived["amount_refs"]
    h1, h2, h3 = steps
    runs = [entries(world, world.run("ars222", h), dict(spacing=spacing)) for h in steps]
    ref = entries(world, world.run("rk4", h3 / 4), dict(spacing=spacing))
    S = rules.grid_steps(world.end, h3)
    print(f"S_c {S}; steps {h1:g} {h2:g} {h3:g}")
    for e in runs[0]:
        d2 = float(np.max(np.abs(runs[1][e] - runs[0][e])))
        d1 = float(np.max(np.abs(runs[2][e] - runs[1][e])))
        theta = 10 * (rules.e_round(S, scales[e]) + rules.e_store(S, refs.get(e, 0.0)))
        q = math.log2(d2 / d1) if d1 > 0 else math.inf
        err = float(np.max(np.abs(runs[2][e] - ref[e])))
        u = max(d1 / (2**p - 1), d2 / (2**p * (2**p - 1)))
        print(
            f"  {e:14s} d2 {d2:9.2e} d1 {d1:9.2e} q {q:5.2f} theta {theta:8.1e} "
            f"d1/theta {d1 / theta:9.1e}"
            f" U_c {u:8.1e} |Y3-ref| {err:8.1e} max|ref| {np.max(np.abs(ref[e])):8.1e}"
        )


def energy(world, h):
    rows = world.run("rk4", h)
    values = [(t, world.energy(s)) for t, s in rows]
    return values


if __name__ == "__main__":
    kind, name, *steps = sys.argv[1:]
    inputs = json.loads((rules.HERE / "inputs_rehearsal.json").read_text())
    ionic = inputs["worlds"][name]["ionic"]
    world = World(ionic)
    steps = [float(s) for s in steps]
    if kind == "order":
        order(world, ionic, steps, inputs["worlds"][name]["history_times"]["spacing_s"])
    else:
        rows = energy(world, steps[0])
        worst = 0.0
        for t, e in rows:
            if abs(e) > 2 * worst and abs(e) > 1e-12:
                worst = abs(e)
                print(f"  t {t:.6g} s  residual {e:9.2e} pJ")
        print(
            f"largest {max(abs(e) for _, e in rows):.2e} pJ, against 2e-8 (inner model, RK4) "
            "and 1e-6 (legacy)"
        )
