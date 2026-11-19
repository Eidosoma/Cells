"""Thermodynamic audit of Beard 2005 (corrected 2006).

For every process: its reaction in reference species with compartments, its Gibbs energy
change from the paper's own standard energies (Table 2) and the model's potentials, and
three checks:

1. **Zero:** does the rate law vanish exactly where Delta G does?
2. **Sign:** is J * Delta G <= 0 (non-negative dissipation) on a random grid of states?
3. **Form:** for mass-action laws, is J+/J- = exp(-Delta G / (nu RT)) (detailed balance)?

Then, at the reported steady states, each process's dissipation -J * Delta G, and the
matrix charge and proton bookkeeping across the inner membrane.

Delta G conventions (kJ/mol, per turnover in the printed direction):
- DG_H = F dPsi + RT ln([H+]e/[H+]x): one proton moved matrix -> outside (Eq. 4);
- moving charge z from matrix to outside costs z F dPsi; an electron (z = -1) carried
  from matrix to IMS gains F dPsi;
- standard energies are the paper's at pH 7 with [H+] referred to 10^-7 M (Eqs. 3-9) and
  1 M otherwise; O2 enters as ln([O2]/1 M) (Eq. 9).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

from . import model as M


def delta_g(comp, y, h) -> dict:
    """Gibbs energy change per turnover (kJ/mol) of each process, printed direction."""
    S = dict(zip(M.STATES, np.asarray(y, float)))
    p = comp.params
    RT = p["R"] * p["T"]
    F = p["F"]
    ln = math.log
    NAD = p["NAD_tot"] - S["NADH_x"]
    Q = p["Q_tot"] - S["QH2_x"]
    cox = p["cytC_tot"] - S["cytCred"]
    ADP_x = p["A_tot"] - S["ATP_x"]
    fATP_x, fADP_x = S["ATP_x"] - S["mATP_x"], ADP_x - S["mADP_x"]
    fATP_i, fADP_i = S["ATP_i"] - S["mATP_i"], S["ADP_i"] - S["mADP_i"]
    Hx, He, psi = S["H_x"], h["H_e"], S["dPsi"]
    DG_H = F * psi + RT * ln(He / Hx)
    hx = ln(Hx / 1e-7)
    out = {
        # H+(x) + NADH + Q -> NAD+ + QH2 + 4 H+ pumped
        "J_C1": p["DGo_C1"] + RT * ln(NAD * S["QH2_x"] / (S["NADH_x"] * Q)) - RT * hx + 4 * DG_H,
        # QH2 + 2 cytc(ox) -> Q + 2 cytc(red) + 2 H+(x) + 4 H+ pumped, 2 e- matrix side -> IMS
        "J_C3": p["DGo_C3"] + RT * ln(Q * S["cytCred"] ** 2 / (S["QH2_x"] * cox ** 2)) + 2 * RT * hx
        + 4 * DG_H - 2 * F * psi,
        # 2 H+(x) + 2 cytc(red) + 1/2 O2 -> 2 cytc(ox) + H2O + 2 H+ pumped, 2 e- IMS -> matrix side
        "J_C4": p["DGo_C4"] + RT * ln(cox ** 2 / (S["cytCred"] ** 2 * h["O2"] ** 0.5)) - 2 * RT * hx
        + 2 * DG_H + 2 * F * psi,
        # H+(x) + ADP + Pi + n_A H+ in -> ATP (free forms; Table 2 at pH 7)
        "J_F1": p["DGo_ATP"] + RT * ln(fATP_x / (fADP_x * S["Pi_x"])) - RT * hx - p["n_A"] * DG_H
        if S["Pi_x"] > 0 and fADP_x > 0 and fATP_x > 0 else float("nan"),
        # ADP3-(i) + ATP4-(x) -> ADP3-(x) + ATP4-(i): one negative charge matrix -> IMS
        "J_ANT": RT * ln(fATP_i * fADP_x / (fADP_i * fATP_x)) - F * psi
        if min(fATP_i, fADP_i, fATP_x, fADP_x) > 0 else float("nan"),
        # H2PO4-(i) + H+(i) -> H2PO4-(x) + H+(x), electroneutral (the stated co-transport)
        "J_PiHt": RT * ln((Hx * S["Pi_x"] / (Hx + p["k_dH"])) * Hx / ((He * S["Pi_i"] / (He + p["k_dH"])) * He))
        if S["Pi_x"] > 0 and S["Pi_i"] > 0 else float("nan"),
        # K+(e) + H+(x) -> K+(x) + H+(e)
        "J_KH": RT * ln(S["K_x"] * He / (h["K_e"] * Hx)),
        # H+(e) -> H+(x)
        "J_Hle": -DG_H,
        # K+(e) -> K+(x)
        "J_K": -(F * psi + RT * ln(h["K_e"] / S["K_x"])),
        # 2 ADP -> ATP + AMP (IMS totals, apparent constant)
        "J_AK": RT * ln(S["ATP_i"] * S["AMP_i"] / (p["K_AK"] * S["ADP_i"] ** 2))
        if min(S["ATP_i"], S["AMP_i"], S["ADP_i"]) > 0 else float("nan"),
        # outer membrane, totals, no potential: buffer -> IMS
        "J_ATPt": RT * ln(S["ATP_i"] / h["ATP_e"]) if S["ATP_i"] > 0 and h["ATP_e"] > 0 else float("nan"),
        "J_ADPt": RT * ln(S["ADP_i"] / h["ADP_e"]) if S["ADP_i"] > 0 and h["ADP_e"] > 0 else float("nan"),
        "J_Pit": RT * ln(S["Pi_i"] / h["Pi_e"]) if S["Pi_i"] > 0 and h["Pi_e"] > 0 else float("nan"),
        # Mg binding: ATP + Mg -> MgATP
        "J_MgATPx": RT * ln(S["mATP_x"] * p["K_MgATP"] / (fATP_x * S["Mg_x"])) if min(S["mATP_x"], fATP_x) > 0 else float("nan"),
        "J_MgADPx": RT * ln(S["mADP_x"] * p["K_MgADP"] / (fADP_x * S["Mg_x"])) if min(S["mADP_x"], fADP_x) > 0 else float("nan"),
    }
    return out


DIRECT = ("J_C1", "J_C3", "J_C4", "J_F1", "J_ANT", "J_PiHt", "J_KH", "J_Hle", "J_AK", "J_MgATPx", "J_MgADPx")


def random_states(comp, n, rng):
    """States spread over and beyond the physiological ranges (all forms positive)."""
    p = comp.params
    ys, hs = [], []
    for _ in range(n):
        ATP_x = rng.uniform(0.05, 0.95) * p["A_tot"]
        ADP_x = p["A_tot"] - ATP_x
        mATP_x = rng.uniform(0.05, 0.95) * ATP_x
        mADP_x = rng.uniform(0.05, 0.95) * ADP_x
        ATP_i, ADP_i, AMP_i = rng.uniform(1e-5, 2e-3, 3)
        y = {"H_x": 10 ** -rng.uniform(6.6, 7.8), "K_x": rng.uniform(0.05, 0.2), "Mg_x": rng.uniform(1e-5, 3e-3),
             "NADH_x": rng.uniform(0.02, 0.98) * p["NAD_tot"], "QH2_x": rng.uniform(0.02, 0.98) * p["Q_tot"],
             "cytCred": rng.uniform(0.02, 0.98) * p["cytC_tot"], "ATP_x": ATP_x, "mATP_x": mATP_x,
             "mADP_x": mADP_x, "Pi_x": rng.uniform(1e-4, 2e-2), "ATP_i": ATP_i, "ADP_i": ADP_i,
             "AMP_i": AMP_i, "mATP_i": rng.uniform(0.05, 0.95) * ATP_i, "mADP_i": rng.uniform(0.05, 0.95) * ADP_i,
             "Pi_i": rng.uniform(1e-4, 2e-2), "dPsi": rng.uniform(-50.0, 250.0)}
        h = {"H_e": 10 ** -rng.uniform(6.6, 7.8), "K_e": rng.uniform(0.05, 0.2), "Mg_i": rng.uniform(1e-4, 5e-3),
             "ATP_e": rng.uniform(1e-5, 2e-3), "ADP_e": rng.uniform(1e-5, 2e-3), "AMP_e": rng.uniform(1e-5, 1e-3),
             "Pi_e": rng.uniform(1e-4, 2e-2), "O2": rng.uniform(1e-7, 5e-5)}
        ys.append(np.array([y[s] for s in M.STATES]))
        hs.append(h)
    return ys, hs


def sign_test(comp, n=4000, seed=1):
    """Fraction of random states with J * DG > 0 (negative dissipation), per process, and
    the largest |DG| inside such a violating state."""
    rng = np.random.default_rng(seed)
    ys, hs = random_states(comp, n, rng)
    res = {k: {"violations": 0, "max_violating_abs_DG_kJ": 0.0, "n": 0} for k in DIRECT}
    for y, h in zip(ys, hs):
        fl = comp.fluxes(y, h)
        dg = delta_g(comp, y, h)
        for k in DIRECT:
            g = dg[k]
            if not np.isfinite(g):
                continue
            res[k]["n"] += 1
            if fl[k] * g > 0 and abs(g) > 1e-9:
                res[k]["violations"] += 1
                res[k]["max_violating_abs_DG_kJ"] = max(res[k]["max_violating_abs_DG_kJ"], abs(g))
    return res


def zero_offset(comp, y, h):
    """Where each rate law vanishes, in Delta G: solve J(y + s e) = 0 along one coordinate
    and report Delta G there (kJ/mol). Zero means the law's zero is the reaction's equilibrium."""
    from scipy.optimize import brentq
    knobs = {"J_C1": "NADH_x", "J_C3": "cytCred", "J_C4": "cytCred", "J_F1": "ATP_x", "J_ANT": "ATP_i",
             "J_PiHt": "Pi_x", "J_KH": "K_x", "J_Hle": "H_x", "J_AK": "AMP_i"}
    out = {}
    for k, s in knobs.items():
        i = M.STATES.index(s)
        y0 = np.array(y, float)

        def J(v):
            yy = y0.copy()
            yy[i] = v
            if s == "ATP_x":       # keep the bound fractions while moving the total
                yy[M.STATES.index("mATP_x")] = y0[M.STATES.index("mATP_x")] * v / y0[i]
                yy[M.STATES.index("mADP_x")] = y0[M.STATES.index("mADP_x")] * (comp.params["A_tot"] - v) / (comp.params["A_tot"] - y0[i])
            if s == "ATP_i":
                yy[M.STATES.index("mATP_i")] = y0[M.STATES.index("mATP_i")] * v / y0[i]
            return comp.fluxes(yy, h)[k], yy

        lo, hi = y0[i] * 1e-6, y0[i] * 1e6
        if s in ("NADH_x",):
            hi = comp.params["NAD_tot"] * (1 - 1e-12)
        if s == "cytCred":
            hi = comp.params["cytC_tot"] * (1 - 1e-12)
        if s == "ATP_x":
            hi = comp.params["A_tot"] * (1 - 1e-9)
        try:
            root = brentq(lambda v: J(v)[0], lo, hi, xtol=1e-30, rtol=1e-14, maxiter=500)
            out[k] = delta_g(comp, J(root)[1], h)[k]
        except ValueError:
            out[k] = None
    return out


def dissipation(comp, y, h):
    """-J * Delta G per process (kW per litre of mitochondria = kJ s^-1 (l mito)^-1)."""
    fl = comp.fluxes(y, h)
    dg = delta_g(comp, y, h)
    return {k: (-fl[k] * dg[k] if np.isfinite(dg.get(k, float("nan"))) else None) for k in dg}, fl, dg


def charge_bookkeeping(comp, y, h):
    """Charge carried matrix -> outside per second (mol/s/l mito), by process, from the
    reactions' own charges, against Eq. 22's dPsi row."""
    fl = comp.fluxes(y, h)
    n_A = comp.params["n_A"]
    by_reaction = {"J_C1": 4 * fl["J_C1"], "J_C3": 2 * fl["J_C3"], "J_C4": 4 * fl["J_C4"],
                   "J_F1": -n_A * fl["J_F1"], "J_ANT": fl["J_ANT"], "J_Hle": -fl["J_Hle"], "J_K": -fl["J_K"],
                   "J_PiHt": 0.0, "J_KH": 0.0}
    total = sum(by_reaction.values())
    row = M.ode_rows(comp.model, comp.arm)["dPsi"]["terms"]
    env = {k: M.Fraction(repr(v)) for k, v in comp.params.items()}
    from_row = sum(float(M.eval_fraction(c, env)) * fl[j] for j, c in row.items())
    return {"by_process": by_reaction, "total": total, "eq22_dPsi_row": from_row}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Thermodynamic audit of Beard 2005")
    ap.add_argument("--repro", type=Path, required=True, help="a reproduce.py arm JSON (steady states)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    rep = json.loads(args.repro.read_text())
    model = M.load()
    res = {"sign_tests": {}, "states": {}}
    for name, arm in (("published", M.Arm.published()), ("eq7", M.Arm.without_control()),
                      ("eq24_with_eq7_proton_term", M.Arm.published(J_C3="eq24_with_eq7_proton_term")),
                      ("eq16_symport", M.Arm.published(J_PiHt="eq16_symport")),
                      ("eq11_with_proton_term", M.Arm.published(J_F1="eq11_with_proton_term"))):
        comp = M.compile_model(model, arm)
        res["sign_tests"][name] = sign_test(comp)
    print(json.dumps(res["sign_tests"], indent=1))
    args.out.write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    sys.exit(main())
