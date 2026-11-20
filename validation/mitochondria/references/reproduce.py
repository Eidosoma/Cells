"""Reproduce Beard 2005's published steady states and low-oxygen numbers.

Every steady state is reached by stiff integration (Radau, float64) from a declared,
equilibrated start and then polished by the 50-digit Newton solve with the two invariants
of Eq. 22 imposed. A sweep continues along [Pi]e by Newton from the previous solution and
checks one point per sweep against a fresh integration.

Inputs Beard 2005 does not report (Q24-Q28) are explicit arguments:
- ``T`` (declared 310.15 K);
- ``mg_x_total``: the matrix Mg2+ inventory (declared; scanned);
- the matrix charge inventory, anchored to the published matrix pH at [Pi]e = 0
  (Fig. 4D, the only anchor), or given directly;
- ``mg_i_rule``: the IMS free Mg2+ (the buffer's free Mg2+, or its 5 mM total);
- the cytochrome a content that converts MVO2 to Figs. 2B/4B's units (one anchor, for
  display only; MVO2 is judged as ratios).
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from . import model as M

HERE = Path(__file__).parent
TARGETS = HERE / "published_targets.json"
PI_KNOTS = (0.0, 1.0, 2.0, 3.0, 5.0, 10.0)        # mM
IMS_NUCLEOTIDES = ("ATP_i", "ADP_i", "AMP_i", "mATP_i", "mADP_i")
PH_ANCHOR = 7.1418                                # Fig. 4D model curve at [Pi]e = 0 (digitised)


def outputs(comp, h, y) -> dict:
    y = np.asarray(y, float)
    S = dict(zip(M.STATES, y))
    p = comp.params
    fl = comp.fluxes(y, h)
    return {
        "NADH_frac": S["NADH_x"] / p["NAD_tot"],
        "cytc_red_frac": S["cytCred"] / p["cytC_tot"],
        "dPsi_mV": S["dPsi"],
        "pH_x": -math.log10(S["H_x"]),
        "MVO2_mol_per_s_per_l": fl["J_C4"] / 2.0,
        "K_x_mM": S["K_x"] * 1e3,
        "Pi_x_mM": S["Pi_x"] * 1e3,
        "Pi_i_mM": S["Pi_i"] * 1e3,
        "ATP_x_mM": S["ATP_x"] * 1e3,
        "Mg_x_free_mM": S["Mg_x"] * 1e3,
        "ATP_i_mM": S["ATP_i"] * 1e3,
        "ADP_i_mM": S["ADP_i"] * 1e3,
        "AMP_i_mM": S["AMP_i"] * 1e3,
        "J_ANT": fl["J_ANT"],
        "J_F1": fl["J_F1"],
        "J_Hle": fl["J_Hle"],
        "J_DH": fl["J_DH"],
        "DG_H_kJ": p["F"] * S["dPsi"] + p["R"] * p["T"] * math.log(h["H_e"] / S["H_x"]),
    }


class Runner:
    def __init__(self, arm: M.Arm, mg_x_total=1.0e-3, mg_i_rule="buffer_free", charge=None,
                 model=None):
        self.model = model or M.load()
        self.arm = arm
        self.comp = M.compile_model(self.model, arm)
        self.mg_x_total = mg_x_total
        self.mg_i_rule = mg_i_rule
        self.charge = charge

    def held(self, ADP_e=0.0, Pi_e=0.0, ATP_e=0.0, O2=2.6e-5):
        return M.held(self.model, self.comp, ADP_e=ADP_e, ATP_e=ATP_e, Pi_e=Pi_e, O2=O2,
                      mg_i_rule=self.mg_i_rule)

    def _pinned(self, h):
        return IMS_NUCLEOTIDES if h["ATP_e"] == 0 and h["ADP_e"] == 0 and h["AMP_e"] == 0 else ()

    def start(self, h):
        y0 = M.initial_state(self.comp, h, Mg_x_total=self.mg_x_total)
        return M.with_invariants(self.comp, y0, charge=self.charge, mg_total=self.mg_x_total)

    def solve(self, h, guess=None, integrate=True, t_end=4000.0):
        """Steady state: integrate from the declared start (or a guess), then Newton."""
        info = {}
        if integrate or guess is None:
            y0 = self.start(h) if guess is None else M.with_invariants(self.comp, guess, charge=self.charge,
                                                                        mg_total=self.mg_x_total)
            t0 = time.time()
            sol = M.integrate(self.comp, h, y0, t_end=t_end)
            yi = sol.y[:, -1]
            info["integration_s"] = time.time() - t0
            info["nfev"] = int(sol.nfev)
            guess = yi
        else:
            yi = None
        inv = None
        if self.charge is not None:
            laws, vals = M.invariants(self.comp, guess)
            inv = [self.charge if "K_x" in law else self.mg_x_total * self.comp.params["V_x"]
                   for law in laws]
        try:
            ss = M.steady_state(self.comp, h, guess, invariant_values=inv, pinned=self._pinned(h))
        except ArithmeticError:
            if yi is not None:
                raise
            return self.solve(h, guess=guess, integrate=True, t_end=t_end)   # continuation failed: integrate
        yn = ss.floats()
        info["newton_residual"] = float(ss.residual)
        info["newton_iterations"] = ss.iterations
        if yi is not None:
            info["integration_vs_newton_rel"] = float(np.max(np.abs(yn - yi) / np.maximum(np.abs(yn), 1e-9)))
        return yn, info

    def calibrate_charge(self, target_pH=PH_ANCHOR, ADP_e=0.0):
        """The matrix charge inventory that gives the published matrix pH at [Pi]e = 0."""
        h = self.held(ADP_e=ADP_e, Pi_e=0.0)
        self.charge = None
        y, _ = self.solve(h)
        laws, vals = M.invariants(self.comp, y)
        k = next(i for i, law in enumerate(laws) if "K_x" in law)
        c0 = vals[k]

        def ph_at(c):
            self.charge = c
            yy, _ = self.solve(h, guess=y, integrate=False)
            return -math.log10(yy[M.STATES.index("H_x")]), yy

        # pH falls as the charge inventory rises (K_x = K_e H_x / H_e at steady state)
        a, b = c0 - 0.002, c0 + 0.002
        fa, _ = ph_at(a)
        fb, _ = ph_at(b)
        for _ in range(40):
            c = b - (fb - target_pH) * (b - a) / (fb - fa)
            fc, y = ph_at(c)
            a, fa, b, fb = b, fb, c, fc
            if abs(fc - target_pH) < 1e-10:
                break
        self.charge = c
        return c

    def sweep(self, ADP_e, pis=PI_KNOTS, check_every=True):
        rows = []
        guess = None
        for k, pi in enumerate(pis):
            h = self.held(ADP_e=ADP_e, Pi_e=pi * 1e-3)
            y, info = self.solve(h, guess=guess, integrate=(check_every or k == 0))
            out = outputs(self.comp, h, y)
            out.update({"Pi_e_mM": pi, "ADP_e_mM": ADP_e * 1e3, **info, "y": [float(v) for v in y]})
            rows.append(out)
            guess = y
        return rows

    def low_oxygen(self, ADP_e, ATP_e, Pi_e, o2_uM=None):
        """MVO2 and cytochrome c reduction against [O2] (continuation downward from 50 uM)."""
        if o2_uM is None:
            o2_uM = np.concatenate([np.linspace(50, 5, 10), np.geomspace(4.5, 0.02, 36)])
        rows = []
        guess = None
        for k, o in enumerate(o2_uM):
            h = self.held(ADP_e=ADP_e, ATP_e=ATP_e, Pi_e=Pi_e, O2=o * 1e-6)
            y, info = self.solve(h, guess=guess, integrate=(k == 0))
            out = outputs(self.comp, h, y)
            out["O2_uM"] = float(o)
            rows.append(out)
            guess = y
        mv = np.array([r["MVO2_mol_per_s_per_l"] for r in rows])
        o2 = np.array([r["O2_uM"] for r in rows])
        half = 0.5 * mv[0]
        order = np.argsort(o2)
        p50 = float(np.interp(half, mv[order], o2[order]))
        return {"P50_uM": p50, "cytc_at_50uM": rows[0]["cytc_red_frac"], "MVO2_at_50uM": float(mv[0]),
                "rows": rows}


def adp_step_time_course(runner: "Runner", Pi_e=10e-3, ADP_on=1.3e-3, t_on=60.0, t_off=120.0,
                         samples=None, rtol=1e-10):
    """The design note's first protocol step (Sec. 7): state 4 -> [ADP]e step -> state 4.

    Starts at the state-4 steady state with the runner's inventories, steps the buffer ADP
    to ``ADP_on`` at t = 0 and back to 0 at ``t_on``, and samples every state. Beard 2005
    reports no transients and was fitted to steady states only, so these depend on the
    switches that only move transients (Q05) and on C_IM, X_MgA and X_AK."""
    from scipy.integrate import solve_ivp
    if samples is None:
        samples = np.concatenate([np.linspace(0, t_on, 241), np.linspace(t_on, t_on + t_off, 481)[1:]])
    h4 = runner.held(ADP_e=0.0, Pi_e=Pi_e)
    h3 = runner.held(ADP_e=ADP_on, Pi_e=Pi_e)
    y4, _ = runner.solve(h4)
    f = runner.comp.fn("float")
    scale = np.maximum(np.abs(y4), 1e-6)
    scale[M.STATES.index("H_x")] = 1e-8
    scale[M.STATES.index("dPsi")] = 100.0
    out = []
    y = y4.copy()
    for (t0, t1, h) in ((0.0, t_on, h3), (t_on, t_on + t_off, h4)):
        ts = samples[(samples >= t0) & (samples <= t1)]
        sol = solve_ivp(lambda t, yy: f(yy, h)[0], (t0, t1), y, method="Radau", rtol=rtol,
                        atol=1e-12 * scale, t_eval=ts)
        if not sol.success:
            raise RuntimeError(sol.message)
        for k, t in enumerate(sol.t):
            o = outputs(runner.comp, h, sol.y[:, k])
            out.append({"t_s": float(t), **{q: o[q] for q in ("dPsi_mV", "NADH_frac", "cytc_red_frac", "pH_x",
                                                               "MVO2_mol_per_s_per_l", "ATP_x_mM", "Pi_x_mM")}})
        y = sol.y[:, -1]
    return out


def compare(sweeps: dict, targets: dict, model_kind: str, cyta_anchor=("state3", 10.0)) -> list:
    """Rows of (panel, curve, Pi, published, unc, reproduced, diff, diff/unc)."""
    figs = {"with": ("fig4A", "fig4B", "fig4C", "fig4D", "fig5"),
            "without": ("fig2A", "fig2B", "fig2C", "fig2D", "fig3")}[model_kind]
    rows = []
    # MVO2 scale (cytochrome a per l mito volume) from one anchor, for display only
    mvo2_fig = figs[1]
    pub_anchor = targets["figures"][mvo2_fig]["curves"][cyta_anchor[0]][f"{cyta_anchor[1]:g}"][0]
    mod_anchor = next(r for r in sweeps[cyta_anchor[0]] if r["Pi_e_mM"] == cyta_anchor[1])["MVO2_mol_per_s_per_l"]
    scale = pub_anchor / (mod_anchor * 60.0)     # (mol O2/min/mol cyt a) per (mol O2/min/l mito)
    for f in figs:
        q = targets["figures"][f]["quantity"]
        for curve, pts in targets["figures"][f]["curves"].items():
            if curve not in sweeps:
                continue
            for pi_s, (val, unc) in pts.items():
                r = next((r for r in sweeps[curve] if abs(r["Pi_e_mM"] - float(pi_s)) < 1e-12), None)
                if r is None:
                    continue
                if q == "MVO2_per_cyta":
                    rep = r["MVO2_mol_per_s_per_l"] * 60.0 * scale
                else:
                    rep = r[q]
                rows.append({"panel": f, "curve": curve, "Pi_e_mM": float(pi_s), "quantity": q,
                             "published": val, "unc": unc, "reproduced": rep, "diff": rep - val,
                             "z": (rep - val) / unc, "anchor": (q == "MVO2_per_cyta" and curve == cyta_anchor[0]
                                                               and float(pi_s) == cyta_anchor[1]) or
                             (q == "pH_x" and float(pi_s) == 0.0)})
    return rows, 1.0 / scale


def summarise(rows):
    out = {}
    for r in rows:
        if r["anchor"]:
            continue
        key = (r["panel"], r["curve"])
        out.setdefault(key, []).append(r)
    s = {}
    for (panel, curve), rr in out.items():
        s[f"{panel}:{curve}"] = {"max_abs_diff": max(abs(r["diff"]) for r in rr),
                                 "rms_z": math.sqrt(sum(r["z"] ** 2 for r in rr) / len(rr))}
    allz = [r["z"] for r in rows if not r["anchor"]]
    return s, math.sqrt(sum(z * z for z in allz) / len(allz))


def run_arm(arm: M.Arm, mg_x_total=1.0e-3, mg_i_rule="buffer_free", targets=None, low_oxygen=True,
            pi_fig6=(1.0, 3.0, 10.0), check_every=True):
    targets = targets or json.loads(TARGETS.read_text())
    R = Runner(arm, mg_x_total=mg_x_total, mg_i_rule=mg_i_rule)
    t0 = time.time()
    charge = R.calibrate_charge()
    sweeps = {"state4": R.sweep(0.0, check_every=check_every), "state3": R.sweep(1.3e-3, check_every=check_every)}
    rows, cyta = compare(sweeps, targets, arm.column)
    summary, rmsz = summarise(rows)
    res = {"arm": arm.label(), "arm_fields": asdict(arm), "mg_x_total_M": mg_x_total, "mg_i_rule": mg_i_rule,
           "charge_inventory_mol_per_l": charge, "cyt_a_mol_per_l_mito_implied": cyta,
           "sweeps": sweeps, "comparison": rows, "summary": summary, "rms_z": rmsz}
    if low_oxygen:
        res["low_oxygen"] = {}
        for pi in pi_fig6:
            lo = R.low_oxygen(1.0e-3, 0.0, pi * 1e-3)
            lc = R.low_oxygen(0.5e-3, 0.87e-3, pi * 1e-3, o2_uM=np.array([50.0]))
            res["low_oxygen"][f"{pi:g}"] = {"P50_uM": lo["P50_uM"], "P50_mmHg": lo["P50_uM"] / 1.3,
                                            "cytc_at_50uM_state3_0.5ADP_0.87ATP": lc["cytc_at_50uM"]}
    res["seconds"] = time.time() - t0
    return res


def arms():
    """Named arms. ``published`` is the model the published curves were computed with
    (Q02 resolved by them); the others each change one switch or input."""
    P, W = M.Arm.published, M.Arm.without_control
    thermo = dict(J_F1="eq11_with_proton_term", J_PiHt="eq16_symport")
    return {
        "published": (P(), {}),
        "without_control": (W(), {}),
        "eq24_printed": (P(J_C3="eq24_printed"), {}),
        "eq16_symport": (P(J_PiHt="eq16_symport"), {}),
        "eq11_with_proton_term": (P(J_F1="eq11_with_proton_term"), {}),
        "thermo_consistent": (P(**thermo), {}),
        "T310": (P(T=310.15), {}),
        "without_control_T310": (W(T=310.15), {}),
        "mg_i_total": (P(), {"mg_i_rule": "total"}),
        "mg_x_0.25mM": (P(), {"mg_x_total": 0.25e-3}),
        "mg_x_0.5mM": (P(), {"mg_x_total": 0.5e-3}),
        "mg_x_2mM": (P(), {"mg_x_total": 2.0e-3}),
        "mg_x_5mM": (P(), {"mg_x_total": 5.0e-3}),
        "plant_table_2005": (P(table="e36"), {}),
        "plant_k_O2_2005": (P(overrides={"k_O2": 1.0e-6}), {}),
        "plant_stale_xml_row": (P(H_x_row="stale_web_xml"), {}),
        "plant_DGo_ATP_text_sign": (P(DGo_ATP_sign=-1), {}),
        "plant_X_ANT_plus_1pct": (P(overrides={"X_ANT": 0.0079204 * 1.01}), {}),
        # does the Eqs. 11/16 ranking survive the undeclared matrix Mg2+ total? (Q03, Q11, Q25)
        "mg_x_15mM": (P(), {"mg_x_total": 15e-3}),
        **{f"{k}_mg{tag}": (P(**sw), {"mg_x_total": mg}) for k, sw in
           (("eq16_symport", {"J_PiHt": "eq16_symport"}), ("eq11_with_proton_term", {"J_F1": "eq11_with_proton_term"}))
           for tag, mg in (("0.25", 0.25e-3), ("5", 5e-3), ("15", 15e-3))},
    }


FULL = ("published", "without_control", "eq24_printed", "eq16_symport", "eq11_with_proton_term",
        "thermo_consistent", "T310", "plant_table_2005", "plant_k_O2_2005")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Reproduce Beard 2005's published results")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--arms", default="published,without_control", help="comma list, or 'all'")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    table = arms()
    names = list(table) if args.arms == "all" else args.arms.split(",")
    for name in names:
        arm, kw = table[name]
        t0 = time.time()
        try:
            res = run_arm(arm, pi_fig6=(1.0, 3.0, 10.0), low_oxygen=name in FULL,
                          check_every=name in ("published", "without_control"), **kw)
        except Exception as exc:   # a failure is a finding, recorded, not hidden
            res = {"arm": arm.label(), "error": repr(exc), "seconds": time.time() - t0}
        (args.out / f"{name}.json").write_text(json.dumps(res, indent=1, default=float))
        print(name, json.dumps({k: res.get(k) for k in ("arm", "rms_z", "charge_inventory_mol_per_l",
                                                         "cyt_a_mol_per_l_mito_implied", "seconds", "error")},
                               default=float), flush=True)


if __name__ == "__main__":
    sys.exit(main())
