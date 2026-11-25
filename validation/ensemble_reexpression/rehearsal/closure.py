"""What SPEC section 6's closure term leaves out, as shares of what it counts, world by world.

SPEC section 6 forms e_close from a potential error of 2.13e-12 V* at each free offset, 2e-12 V* at
a node's charge, and the flux that such an error moves (a share of the gross scale). The criteria's
author said that four things are not in it: the engine's absolute charge tolerance, the paths
through gates, a junction's two membranes, and the second factor of a heat (J times the error of its
driving force). Each number below is arithmetic on the declared values alone, with the field
solver's constants as the frozen snapshot declares them (CHARGE_ATOL_C, CHARGE_RTOL, CURRENT_ATOL_A,
CURRENT_RTOL, NEWTON_TARGET). It is the share of the admitted error, not a measured one: an honest
run's own residual is at rounding.

    closure.py              one row per world and path
    closure.py table        one line per world: the largest share of each path
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules  # noqa: E402

# The snapshot's numerics/surface_field.py and tissue_field.py declare these.
CHARGE_ATOL_C, CHARGE_RTOL = 3e-25, 2e-12
CURRENT_ATOL_A, CURRENT_RTOL, NEWTON_TARGET = 1e-23, 2e-12, 0.01
COUNTED_V = 2.13e-12 * rules.V_STAR  # The potential error that SPEC section 6 counts at one offset.
CODE_V = 2e-12 * rules.V_STAR  # ... and at one node's charge.


def bernoulli(x):
    return np.where(
        np.abs(x) < 1e-4, 1 - x / 2 + x * x / 12, x / np.expm1(np.where(x == 0, 1.0, x))
    )


class State:
    """The declared initial state of a world: concentrations, potentials, route conductances."""

    def __init__(self, ionic):
        self.b = rules.Block(ionic)
        b = self.b
        self.rt = b.RT
        gauge = ionic["closure"]["gauge_reference"]
        self.regions = list(b.outside)
        faced = {m["outside"]: [] for m in b.membranes.values()}
        for mid, m in b.membranes.items():
            faced[m["outside"]].append(mid)
        self.v = {mid: b.cells[m["inside"]]["initial_voltage_V"] for mid, m in b.membranes.items()}
        self.floating = [
            r for r in self.regions if r != gauge
        ]  # Every region that is not the gauge floats (its component may hold cells).
        self.phi = dict.fromkeys(self.regions, 0.0)
        self._solve(gauge)

    def conductance(self, f):
        e = self.b.faces[f]
        total = 0.0
        for x, d in e["diffusivity_m2_per_s"].items():
            a, c = self.b.conc(e["sender"], x), self.b.conc(e["receiver"], x)
            mean = a if a == c else (a - c) / math.log(a / c)
            total += self.b.z[x] ** 2 * d * e["area_m2"] / e["length_m"] * mean
        return rules.F**2 / self.rt * total

    def face_current(self, f, phi):
        e = self.b.faces[f]
        total = 0.0
        for x, d in e["diffusivity_m2_per_s"].items():
            a, c = self.b.conc(e["sender"], x), self.b.conc(e["receiver"], x)
            mean = a if a == c else (a - c) / math.log(a / c)
            mu = (
                math.log(a / c)
                + self.b.z[x] * rules.F * (phi[e["sender"]] - phi[e["receiver"]]) / self.rt
            )
            total += self.b.z[x] * d * e["area_m2"] / e["length_m"] * mean * mu
        return rules.F * total

    def cell_potential(self, cell, phi):
        m = next(m for m in self.b.membranes.values() if m["inside"] == cell)
        mid = next(k for k, v in self.b.membranes.items() if v is m)
        return self.v[mid] + phi[m["outside"]]

    def junction(self, j, phi):
        """(voltage V, {species: flux fmol/s}, {species: Delta mu J/mol}, {species: gross})."""
        e = self.b.junctions[j]
        a, c = e["from_cell"], e["to_cell"]
        dv = self.cell_potential(a, phi) - self.cell_potential(c, phi)
        g = e["gate"]["initial_gate"]
        flux, mu, gross = {}, {}, {}
        for x, p in e["permeability_m_per_s"].items():
            y = self.b.z[x] * rules.F * dv / self.rt
            ca, cb = self.b.conc(a, x), self.b.conc(c, x)
            unit = e["area_m2"] * p / rules.FMOL
            flux[x] = unit * g * (ca * float(bernoulli(-y)) - cb * float(bernoulli(y)))
            mu[x] = self.rt * math.log(ca / cb) + self.b.z[x] * rules.F * dv
            gross[x] = unit * max(ca, cb) * self.b.chi(x)
        return dv, flux, mu, gross

    def _solve(self, gauge):
        unknown = self.floating
        if not unknown or not self.b.faces:
            return
        phi = dict(self.phi)

        def residual(values):
            phi.update(dict(zip(unknown, values, strict=True)))
            out = np.zeros(len(unknown))
            for f, e in self.b.faces.items():
                i = self.face_current(f, phi)
                if e["sender"] in unknown:
                    out[unknown.index(e["sender"])] += i
                if e["receiver"] in unknown:
                    out[unknown.index(e["receiver"])] -= i
            for j, e in self.b.junctions.items():
                _, flux, _, _ = self.junction(j, phi)
                current = rules.F * rules.FMOL * sum(self.b.z[x] * v for x, v in flux.items())
                for name, sign in ((e["from_cell"], 1.0), (e["to_cell"], -1.0)):
                    r = next(m["outside"] for m in self.b.membranes.values() if m["inside"] == name)
                    if r in unknown:
                        out[unknown.index(r)] += sign * current
            return out

        values = np.zeros(len(unknown))
        for _ in range(60):
            r = residual(values)
            if np.max(np.abs(r)) < 1e-30:
                break
            jac = np.zeros((len(unknown), len(unknown)))
            for k in range(len(unknown)):
                step = np.zeros(len(unknown))
                step[k] = 1e-6
                jac[:, k] = (residual(values + step) - residual(values - step)) / 2e-6
            delta = np.linalg.solve(jac, -r)
            values = values + delta
        residual(values)
        self.phi = dict(phi)


def shares(name, world):
    ionic = world["ionic"]
    s = State(ionic)
    b = s.b
    out = {}
    # (1) charge: what one code's charge residual may leave of a potential, absolute and relative.
    v = max(abs(m["initial_voltage_V"]) for m in ionic["cells"].values())
    cap = min(m["capacitance_F"] for m in ionic["membranes"].values())
    out["charge: absolute tolerance, smallest capacitor, over 2e-12 V*"] = (
        CHARGE_ATOL_C / cap / CODE_V
    )
    out["charge: relative tolerance, largest potential, over 2e-12 V*"] = CHARGE_RTOL * v / CODE_V
    # (2) free offsets: current residual admitted over the smallest incident conductance.
    if s.floating and b.faces:
        g = {f: s.conductance(f) for f in b.faces}
        current = max(abs(s.face_current(f, s.phi)) for f in b.faces)
        for j in b.junctions:
            _, flux, _, _ = s.junction(j, s.phi)
            current = max(
                current,
                abs(rules.F * rules.FMOL * sum(b.z[x] * w for x, w in flux.items())),
            )
        small = min(
            sum(g[f] for f, e in b.faces.items() if r in (e["sender"], e["receiver"]))
            for r in s.floating
        )
        tolerance = CURRENT_ATOL_A + CURRENT_RTOL * current
        out[
            "offset: legacy's current rule over the smallest incident conductance, over 2.13e-12 V*"
        ] = tolerance / small / COUNTED_V
        out["offset: the inner model's Newton target over the same, over 2.13e-12 V*"] = (
            NEWTON_TARGET * tolerance / small / COUNTED_V
        )
        out["offset: the absolute part of legacy's current rule, share"] = (
            CURRENT_ATOL_A / tolerance
        )
    # (3) a junction's two membranes, and (4) the gate: an error of 2e-12 V* (one code) at each
    # membrane.
    for j, e in b.junctions.items():
        dv, flux, mu, gross = s.junction(j, s.phi)
        shift = abs(dv) - e["gate"]["threshold_voltage_V"]
        alpha = 1.3 * math.exp(-77 * shift)
        beta = 20 / (1 + math.exp(-(math.log(0.065) + 140 * shift)))
        g0, lo = e["gate"]["initial_gate"], e["gate"]["minimum_open_fraction"]
        # d(rate)/dV: alpha' = -77 alpha sign, beta' = 140 beta (1 - beta/20) sign.
        slope = -77 * alpha * (1 - g0) - 140 * beta * (1 - beta / 20) * (g0 - lo)
        key = f"junction {j} (V {dv:.4f} V)"
        share = 1 - math.exp(-abs(rules.F * dv / s.rt))  # Informative only.
        out[f"{key}: two membranes, over one"] = 2.0
        relative = abs(slope) * 2 * CODE_V * b.end / max(g0, 1e-9)
        out[f"{key}: gate path, error of the gate over the run as a share of 4e-12 of it"] = (
            relative / 4e-12
        )
        del share
        # the heat's second factor: |J| z F error against the heat's scale (per code, over 2e-12 of
        # it).
        second = sum(abs(flux[x]) * abs(b.z[x]) * rules.F * 2 * CODE_V * 1e-3 for x in flux)
        scale = sum(
            gross[x]
            * 1e-3
            * s.rt
            * (
                1
                + abs(math.log(b.conc(e["from_cell"], x) / b.conc(e["to_cell"], x)))
                + abs(b.z[x]) * rules.F * rules.V_STAR / s.rt
            )
            for x in gross
        )
        out[f"{key}: heat, second factor over the heat scale, over 2e-12"] = second / scale / 2e-12
        out[f"{key}: |J|/gross, largest over the species"] = max(
            abs(flux[x]) / gross[x] for x in flux
        )
    for mid, m in b.membranes.items():
        heat = []
        for x, p in m["passive"]["permeability_m_per_s"].items():
            y = b.z[x] * rules.F * s.v[mid] / s.rt
            ci, co = b.conc(m["inside"], x), b.conc(m["outside"], x)
            unit = m["area_m2"] * p / rules.FMOL
            flux = unit * (ci * float(bernoulli(-y)) - co * float(bernoulli(y)))
            heat.append(
                (abs(flux), unit * max(ci, co) * b.chi(x), abs(b.z[x]), abs(math.log(ci / co)))
            )
        if any(h[1] for h in heat):
            second = sum(f * z * rules.F * CODE_V * 1e-3 for f, _, z, _ in heat)
            scale = sum(
                g * 1e-3 * s.rt * (1 + ln + z * rules.F * rules.V_STAR / s.rt)
                for _, g, z, ln in heat
            )
            out[f"membrane {mid}: leak heat, second factor over the heat scale, over 2e-12"] = (
                second / scale / 2e-12
            )
            out[f"membrane {mid}: leak |J|/gross, largest over the species"] = max(
                f / g for f, g, _, _ in heat if g
            )
    return out


def largest(out, *words):
    return max((v for k, v in out.items() if all(x in k for x in words)), default=0.0)


def table():
    """One line per world: the largest share of each path."""
    inputs = json.loads((rules.HERE / "inputs_rehearsal.json").read_text())
    heads = ("ATOL", "RTOL", "current", "gate", "heat", "|J|/gross")
    print(f"{'world':20s} " + " ".join(f"{h:>9s}" for h in heads))
    for name, w in inputs["worlds"].items():
        out = shares(name, w)
        values = (
            largest(out, "absolute tolerance, smallest"),
            largest(out, "relative tolerance"),
            largest(out, "Newton target"),
            largest(out, "gate path"),
            largest(out, "heat", "second factor"),
            largest(out, "|J|/gross"),
        )
        print(f"{name:20s} " + " ".join(f"{v:9.2g}" for v in values))


def main():
    if sys.argv[1:] == ["table"]:
        return table()
    inputs = json.loads((rules.HERE / "inputs_rehearsal.json").read_text())
    for name, w in inputs["worlds"].items():
        print(name)
        for k, v in shares(name, w).items():
            print(f"  {k}: {v:.3g}")


if __name__ == "__main__":
    main()
