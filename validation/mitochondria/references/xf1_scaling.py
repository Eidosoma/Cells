"""MR1: what a lower declared F1F0 activity costs (X_F1 divided by a scale).

The question: an engine could declare a smaller synthase activity instead of building an
implicit block. For two arms, MR1's published arm and the best consistent arm (frame B with
Eq. 24 restored, repairs_table), and for each scale, this module reports:
- the fit to the published curves (rms z, matrix Mg2+ total 5 mM);
- the departures at the 12 reported states, from the published arm and from the arm's own
  unscaled run;
- whether the steady states exist: every point is integrated (Radau) and matches the
  50-digit Newton solve;
- whether they are unique: three far-apart starts with equal inventories reach one state, at
  state 3 with [Pi]e 3 mM.
Then it finds the largest scale that keeps the fit within 10% of the arm's own fit, by
geometric bisection. The 10% threshold is the coordinator's orientation, not a ruling.

Run: ``python -m validation.mitochondria.references.xf1_scaling --runs DIR --arm NAME --scales 1,30``,
``--bisect NAME`` for the threshold, then ``--table OUT`` (JSON) and ``--markdown OUT``.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from . import model as M
from . import reproduce as R

MG = 5.0e-3
X_F1 = 150.93                    # Table 1 (2006), with phosphate control
ARMS = {"published": {},
        "frame_b_restored_eq24": {"J_F1": "eq11_appendix_balanced", "J_PiHt": "eq16_appendix_balanced"}}
SCALES = (1, 30, 300, 3000, 9000)
THRESHOLD = 1.10


def arm(name, scale):
    return M.Arm.published(**ARMS[name], overrides={"X_F1": X_F1 / scale})


def uniqueness(run, charge, t_end=20000.0):
    """Three far-apart starts with equal inventories: max relative spread of the end states."""
    h = run.held(ADP_e=1.3e-3, Pi_e=3e-3)
    ends = []
    for kw in (dict(), dict(pH_x=7.4, K_x=0.09, dPsi=60.0, NADH_frac=0.1, QH2_frac=0.9, cytc_red_frac=0.6, Pi_x=0.5e-3),
               dict(pH_x=6.9, K_x=0.2, dPsi=220.0, NADH_frac=0.95, QH2_frac=0.05, cytc_red_frac=0.02, Pi_x=8e-3)):
        y0 = M.with_invariants(run.comp, M.initial_state(run.comp, h, **kw), charge=charge, mg_total=run.mg_x_total)
        sol = M.integrate(run.comp, h, y0, t_end=t_end)
        y = sol.y[:, -1]
        rate = np.max(np.abs(run.comp.rhs(y, h)) / np.maximum(np.abs(y), 1e-9))
        ends.append((y, float(rate)))
    spread = max(float(np.max(np.abs(e[0] - ends[0][0]) / np.maximum(np.abs(ends[0][0]), 1e-12))) for e in ends[1:])
    return {"max_relative_spread": spread, "max_relative_rate_at_end_per_s": max(e[1] for e in ends)}


def run_one(name, scale, out: Path):
    t0 = time.time()
    a = arm(name, scale)
    try:
        res = R.run_arm(a, mg_x_total=MG, low_oxygen=False, check_every=True)
        rows = [r for s in res["sweeps"].values() for r in s]
        res["existence"] = {"max_integration_vs_newton_rel": max(r["integration_vs_newton_rel"] for r in rows),
                            "max_newton_residual": max(r["newton_residual"] for r in rows)}
        run = R.Runner(a, mg_x_total=MG, charge=res["charge_inventory_mol_per_l"])
        res["uniqueness_state3_Pi3"] = uniqueness(run, res["charge_inventory_mol_per_l"])
    except Exception as exc:     # a failure is a finding, recorded
        res = {"arm": a.label(), "error": repr(exc)}
    res["xf1_arm"], res["xf1_scale"], res["seconds"] = name, scale, time.time() - t0
    (out / f"{name}_x{scale:g}.json").write_text(json.dumps(res, indent=1, default=float))
    print(name, scale, res.get("rms_z"), res.get("error"), flush=True)
    return res


def bisect(name, out: Path, steps=4):
    """Geometric bisection on the scale between the last passing and the first failing scan point."""
    own = json.loads((out / f"{name}_x1.json").read_text())["rms_z"]
    done = {float(p.stem.split("_x")[-1]): json.loads(p.read_text()) for p in out.glob(f"{name}_x*.json")}
    ok = lambda r: "rms_z" in r and r["rms_z"] <= THRESHOLD * own
    passing = [s for s, r in done.items() if ok(r)]
    failing = [s for s, r in done.items() if not ok(r) and s > max(passing)]
    lo, hi = max(passing), (min(failing) if failing else None)
    if hi is None:
        return lo, None
    for _ in range(steps):
        mid = float(f"{math.sqrt(lo * hi):.3g}")
        if mid in (lo, hi):
            break
        r = done.get(mid) or run_one(name, mid, out)
        lo, hi = (mid, hi) if ok(r) else (lo, mid)
    return lo, hi


def departure(cand, base):
    w = {"dPsi_mV": 0.0, "pH_x": 0.0, "NADH_frac": 0.0, "cytc_red_frac": 0.0, "O2_flux_rel": 0.0}
    b = {(st, r["Pi_e_mM"]): r for st in ("state4", "state3") for r in base["sweeps"][st]}
    for st in ("state4", "state3"):
        for r in cand["sweeps"][st]:
            q = b[(st, r["Pi_e_mM"])]
            for k in ("dPsi_mV", "pH_x", "NADH_frac", "cytc_red_frac"):
                w[k] = max(w[k], abs(r[k] - q[k]))
            w["O2_flux_rel"] = max(w["O2_flux_rel"], abs(r["MVO2_mol_per_s_per_l"] / q["MVO2_mol_per_s_per_l"] - 1))
    return w


def table(out: Path):
    base = json.loads((out / "published_x1.json").read_text())
    rows = []
    for name in ARMS:
        own = json.loads((out / f"{name}_x1.json").read_text())
        for p in sorted(out.glob(f"{name}_x*.json"), key=lambda p: float(p.stem.split("_x")[-1])):
            r = json.loads(p.read_text())
            row = {"arm": name, "scale": r["xf1_scale"], "X_F1": X_F1 / r["xf1_scale"]}
            if "error" in r:
                row["error"] = r["error"]
            else:
                row.update({"fit_rms_z": r["rms_z"], "within_10pct_of_own": r["rms_z"] <= THRESHOLD * own["rms_z"],
                            "departure_from_published_arm": departure(r, base),
                            "departure_from_own_unscaled": departure(r, own),
                            "existence": r["existence"], "uniqueness_state3_Pi3": r["uniqueness_state3_Pi3"],
                            "state3_Pi10": {k: next(x for x in r["sweeps"]["state3"] if x["Pi_e_mM"] == 10.0)[k]
                                            for k in ("dPsi_mV", "NADH_frac", "MVO2_mol_per_s_per_l", "J_F1")}})
            rows.append(row)
    best = {}
    for name in ARMS:
        own = next(r for r in rows if r["arm"] == name and r["scale"] == 1)["fit_rms_z"]
        ok = [r["scale"] for r in rows if r["arm"] == name and r.get("within_10pct_of_own")]
        bad = [r["scale"] for r in rows if r["arm"] == name and "fit_rms_z" in r and not r["within_10pct_of_own"]
               and r["scale"] > max(ok)]
        best[name] = {"own_fit": own, "threshold": THRESHOLD * own, "largest_passing_scale": max(ok),
                      "smallest_failing_scale_above": min(bad) if bad else None}
    doc = {"kind": "cells.validation.mito_reference_xf1_scaling@1",
           "question": "the cost of declaring F1F0's activity X_F1 lower by a scale, instead of an implicit block",
           "conditions": "matrix Mg2+ total 5 mM; matrix charge anchored per arm to Fig. 4D's pH at [Pi]e = 0; 298.15 K",
           "threshold": "fit within 10% of the arm's own unscaled fit (the coordinator's orientation)",
           "largest_scale_within_threshold": best, "rows": rows}
    return doc


def render_markdown(doc) -> str:
    L = ["# MR1: declaring F1F0's activity lower (X_F1 / scale)", "",
         "*Generated by `xf1_scaling.py` from `xf1_scaling.json`; do not edit by hand.*", "",
         f"Conditions: {doc['conditions']}. Threshold: {doc['threshold']}.", "",
         "| Arm | Scale | X_F1 | Fit | Within 10% | Departure from the published arm: dPsi mV, pH, NADH, cyt c, O2 | From the arm unscaled | Exists (integration vs Newton) | Unique (three starts) |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    fmt = lambda d: (f"{d['dPsi_mV']:.2f}, {d['pH_x']:.4f}, {d['NADH_frac']:.4f}, {d['cytc_red_frac']:.4f}, "
                     f"{100 * d['O2_flux_rel']:.1f}%")
    for r in doc["rows"]:
        if "error" in r:
            L.append(f"| {r['arm']} | {r['scale']:g} | {r['X_F1']:.4g} | {r['error']} | | | | | |")
            continue
        ex, un = r["existence"], r["uniqueness_state3_Pi3"]
        L.append(f"| {r['arm']} | {r['scale']:g} | {r['X_F1']:.4g} | {r['fit_rms_z']:.2f} | "
                 f"{'yes' if r['within_10pct_of_own'] else 'no'} | {fmt(r['departure_from_published_arm'])} | "
                 f"{fmt(r['departure_from_own_unscaled'])} | {ex['max_integration_vs_newton_rel']:.1e} | "
                 f"{un['max_relative_spread']:.1e} |")
    L += ["", "**Largest scale within the threshold:**", ""]
    for name, b in doc["largest_scale_within_threshold"].items():
        L.append(f"- {name}: own fit {b['own_fit']:.2f}, threshold {b['threshold']:.2f}: largest passing scale "
                 f"{b['largest_passing_scale']:g}" + (f", next tried {b['smallest_failing_scale_above']:g} fails" if
                                                       b['smallest_failing_scale_above'] else ""))
    return "\n".join(L) + "\n"


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--arm", default=None)
    ap.add_argument("--scales", default=None, help="comma list")
    ap.add_argument("--bisect", default=None, help="arm name: bisect its threshold scale")
    ap.add_argument("--table", type=Path, default=None)
    ap.add_argument("--markdown", type=Path, default=None)
    a = ap.parse_args(argv)
    a.runs.mkdir(parents=True, exist_ok=True)
    if a.arm and a.scales:
        for s in a.scales.split(","):
            run_one(a.arm, float(s), a.runs)
    if a.bisect:
        print("bracket", bisect(a.bisect, a.runs))
    if a.table:
        doc = table(a.runs)
        a.table.write_text(json.dumps(doc, indent=1, default=float))
        if a.markdown:
            a.markdown.write_text(render_markdown(doc))


if __name__ == "__main__":
    sys.exit(main())
