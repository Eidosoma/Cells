"""MR1: the candidate repairs of Beard 2005's Eqs. 1, 11, 16 and 24, side by side.

Written for the user's ruling on which repair to approve. The candidates for each equation:
- its printed form;
- the engine appendix's balanced form, which keeps the printed forward term
  (docs/MITOCHONDRIA_LAWS_APPENDIX.md at tag mito-laws-appendix-2026-11-20);
- the appendix's alternative repairs: the forward term changed instead, by the factor that
  balances it. At pH_N 7.4 and pH_P 7.1 these are x0.51 for Eq. 11, x2.0 for Eq. 16 and x2.51
  for Eq. 24;
- MR1-declared's forms.

**Two thermodynamic frames.** They differ in how the protons on phosphate are booked.
- **Frame S, the source's.** Total Pi is one proton-free species: F1F0 consumes one matrix H+,
  and the carrier moves two H+ per Pi. This is exactly Eq. 22's bookkeeping, so S is the frame
  in which MR1's own invariants close.
- **Frame B, base forms (the appendix's).** HPO4 2- carries k_dH speciation, and the protons
  bound to phosphate count as protons. A binding closure with species works in this frame.

A form is balanced in a frame when its rate law vanishes exactly where that frame's Gibbs
energy does, with J dG <= 0 everywhere. Frame S and frame B differ by:
- F1F0: RT ln((1 + h_N/k_dH)/(1 + 10^-7/k_dH));
- the carrier: RT ln((k_dH + h_P)/(k_dH + h_N)).
Both vanish only at pH 7, or where h_N = h_P.

Run: ``python -m validation.mitochondria.references.repairs --runs DIR --arms all`` (the fits),
then ``--table OUT`` (the comparison, from DIR). Nothing here imports ``cells``.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

from . import audit as A
from . import model as M
from . import reproduce as R

MG_RECOMMENDED = 5.0e-3          # the matrix Mg2+ total MR1 recommends (README; proposal.json)
STATES = M.STATES


def ph_ref_h(ph):
    return 10.0 ** -ph


# eq -> list of (key, switch field, switch value, overrides, description, appendix role)
CANDIDATES = {
    "Eq. 1": [
        ("eq1_printed", "J_DH", "eq1", {}, "printed: X phi (r[NAD] - [NADH]); no reductant, no free energy", "printed"),
        ("eq1_supply_pH7.06", "J_DH", "eq1_balanced_supply", {"h_ref_DH": ph_ref_h(7.06)},
         "balanced supply, held neutral reductant pair, printed forward kept; reference matrix pH 7.06", "appendix balanced"),
        ("eq1_supply_pH7.10", "J_DH", "eq1_balanced_supply", {"h_ref_DH": ph_ref_h(7.10)},
         "the same, reference matrix pH 7.10 (the buffer's)", "appendix balanced"),
        ("eq1_supply_pH7.14", "J_DH", "eq1_balanced_supply", {"h_ref_DH": ph_ref_h(7.1418)},
         "the same, reference matrix pH 7.1418 (Fig. 4D at [Pi]e = 0, MR1's anchor)", "appendix balanced"),
    ],
    "Eq. 11": [
        ("eq11_printed", "J_F1", "eq11", {}, "printed", "printed"),
        ("eq11_appendix_balanced", "J_F1", "eq11_appendix_balanced", {},
         "printed forward kept; backward x (1e-7/h_N)(1 + h_N/k_dH)/(1 + 1e-7/k_dH)", "appendix balanced"),
        ("eq11_proton_in_exponent_base", "J_F1", "eq11_proton_in_exponent_base", {},
         "proton restored inside the exponent, base forms: forward x (h_N/1e-7)(1 + 1e-7/k_dH)/(1 + h_N/k_dH) (x0.51 at pH_N 7.4)",
         "appendix alternative"),
        ("eq11_pi_as_h2po4", "J_F1", "eq11_pi_as_h2po4", {},
         "Pi read as H2PO4-, printed constant: forward x h_N/(h_N + k_dH)", "appendix alternative"),
        ("eq11_mr1", "J_F1", "eq11_with_proton_term", {},
         "MR1-declared: -RT ln(h_N/1e-7) restored in the exponent, total Pi (frame S): forward x h_N/1e-7 (x0.40 at pH_N 7.4)",
         "MR1-declared"),
    ],
    "Eq. 16": [
        ("eq16_printed", "J_PiHt", "eq16_printed", {}, "printed: [H2PO4-]_P h_N - [H2PO4-]_N h_P", "printed"),
        ("eq16_appendix_balanced", "J_PiHt", "eq16_appendix_balanced", {},
         "printed forward kept; backward [H2PO4-]_N h_N^2/h_P", "appendix balanced"),
        ("eq16_swapped_mr1", "J_PiHt", "eq16_symport", {},
         "subscripts swapped to the stated co-transport, [H2PO4-]_P h_P - [H2PO4-]_N h_N (x2.0 at pH_N 7.4); this is MR1-declared",
         "appendix alternative = MR1-declared"),
        ("eq16_total_pi_frame_s", "J_PiHt", "eq16_symport_total_pi", {},
         "swapped forward kept; backward balanced in frame S: [Pi]_N h_N^2/(h_P + k_dH)", "MR1 frame-S variant (extra)"),
    ],
    "Eq. 24": [
        ("eq24_printed", "J_C3", "eq24_printed", {}, "printed: Eq. 7's 2RT ln(h_N/1e-7) dropped", "printed"),
        ("eq24_appendix_balanced", "J_C3", "eq24_appendix_balanced", {},
         "printed forward kept; backward x h_N/1e-7", "appendix balanced"),
        ("eq24_restored_mr1", "J_C3", "eq24_with_eq7_proton_term", {},
         "dropped term restored, forward x 1e-7/h_N (x2.51 at pH_N 7.4); identical to phi_Pi x Eq. 7; MR1's published arm",
         "appendix alternative = MR1 published and declared"),
        ("eq24_full_affinity", "J_C3", "eq24_full_affinity", {},
         "printed forward kept, full affinity: J = A (1 - e^x) in place of A (1 - e^(x/2))", "appendix alternative"),
    ],
}

COMBINED = {
    "mr1_declared": ({"J_F1": "eq11_with_proton_term", "J_PiHt": "eq16_symport"}, {},
                     "MR1-declared: Eq. 11 with its proton term, Eq. 16 swapped; Eq. 24 restored"),
    "appendix_all": ({"J_F1": "eq11_appendix_balanced", "J_PiHt": "eq16_appendix_balanced",
                      "J_C3": "eq24_appendix_balanced"}, {},
                     "the appendix's balanced Eqs. 11, 16 and 24 together"),
}


def arm_of(field, value, overrides):
    return M.Arm.published(**{field: value}, overrides=dict(overrides))


def all_arms():
    out = {}
    for eq, cands in CANDIDATES.items():
        for key, field, value, ov, _, _ in cands:
            out[key] = arm_of(field, value, ov)
    for key, (sw, ov, _) in COMBINED.items():
        out[key] = M.Arm.published(**sw, overrides=dict(ov))
    return out


# --------------------------------------------------------------------------- frames

def frames(comp, y, h, flux):
    """(frame S, frame B) Gibbs energy per turnover, kJ/mol, for the flux the candidate changes."""
    S = dict(zip(STATES, np.asarray(y, float)))
    p = comp.params
    RT = p["R"] * p["T"]
    k = p["k_dH"]
    hx, he = S["H_x"], h["H_e"]
    dg = A.delta_g(comp, y, h)
    if flux == "J_F1":
        s = dg["J_F1"]
        return s, s + RT * math.log((1 + hx / k) / (1 + 1e-7 / k))
    if flux == "J_PiHt":
        b = dg["J_PiHt"]
        s = RT * math.log(S["Pi_x"] * hx * hx / (S["Pi_i"] * he * he)) if S["Pi_x"] > 0 and S["Pi_i"] > 0 else float("nan")
        return s, b
    if flux == "J_C3":
        return dg["J_C3"], dg["J_C3"]
    if flux == "J_DH":
        # the balanced supply's own frame at its reference pH; the printed law has none
        href = p.get("h_ref_DH", 10 ** -7.1418)
        NAD = p["NAD_tot"] - S["NADH_x"]
        x = math.log(S["NADH_x"] * hx / (p["r"] * NAD * href))
        return RT * x, RT * x
    raise KeyError(flux)


def equilibrium_binding(comp, y, h):
    """Put Mg2+ binding at equilibrium (matrix and IMS), so frames compare free and bound forms alike."""
    y = np.array(y, float)
    p = comp.params
    S = dict(zip(STATES, y))
    Mg = S["Mg_x"]
    ADP_x = p["A_tot"] - S["ATP_x"]
    y[STATES.index("mATP_x")] = S["ATP_x"] * Mg / (Mg + p["K_MgATP"])
    y[STATES.index("mADP_x")] = ADP_x * Mg / (Mg + p["K_MgADP"])
    y[STATES.index("mATP_i")] = S["ATP_i"] * h["Mg_i"] / (h["Mg_i"] + p["K_MgATP"])
    y[STATES.index("mADP_i")] = S["ADP_i"] * h["Mg_i"] / (h["Mg_i"] + p["K_MgADP"])
    return y


def sign_counts(comp, flux, n=2000, seed=7):
    """Random states (binding at equilibrium): violations of J dG <= 0 in frames S and B."""
    rng = np.random.default_rng(seed)
    ys, hs = A.random_states(comp, n, rng)
    out = {"S": 0, "B": 0, "n": 0, "max_abs_dG_violating_kJ": {"S": 0.0, "B": 0.0}}
    for y, h in zip(ys, hs):
        y = equilibrium_binding(comp, y, h)
        J = comp.fluxes(y, h)[flux]
        gs, gb = frames(comp, y, h, flux)
        if not (np.isfinite(gs) and np.isfinite(gb)):
            continue
        out["n"] += 1
        for tag, g in (("S", gs), ("B", gb)):
            if J * g > 0 and abs(g) > 1e-9:
                out[tag] += 1
                out["max_abs_dG_violating_kJ"][tag] = max(out["max_abs_dG_violating_kJ"][tag], abs(g))
    return out


KNOB = {"J_F1": "ATP_x", "J_PiHt": "Pi_x", "J_C3": "cytCred", "J_DH": "NADH_x"}


def zero_offsets(comp, y, h, flux):
    """dG (frames S, B; kJ/mol) where the candidate's law vanishes, moving one state."""
    from scipy.optimize import brentq
    s = KNOB[flux]
    i = STATES.index(s)
    y0 = equilibrium_binding(comp, y, h)
    p = comp.params

    def state(v):
        yy = y0.copy()
        yy[i] = v
        return equilibrium_binding(comp, yy, h)

    lo, hi = y0[i] * 1e-8, y0[i] * 1e8
    cap = {"ATP_x": p["A_tot"], "cytCred": p["cytC_tot"], "NADH_x": p["NAD_tot"]}.get(s)
    if cap is not None:
        hi = cap * (1 - 1e-12)
    f = lambda v: comp.fluxes(state(v), h)[flux]
    try:
        root = brentq(f, lo, hi, xtol=1e-30, rtol=1e-14, maxiter=500)
    except ValueError:
        return None, None
    return frames(comp, state(root), h, flux)


def identities(eq, n=500, seed=11):
    """For each pair of candidates of one equation: identical, proportional (same zero), or not.

    On random states the flux ratio is examined: max |ratio - 1| < 1e-9 is identical; otherwise
    the two laws' zeros are compared through their zero offsets."""
    cands = CANDIDATES[eq]
    model = M.load()
    comps = {key: M.compile_model(model, arm_of(f, v, ov)) for key, f, v, ov, _, _ in cands}
    flux = cands[0][1].replace("J_DH", "J_DH")
    rng = np.random.default_rng(seed)
    base = comps[cands[0][0]]
    ys, hs = A.random_states(base, n, rng)
    J = {key: [] for key in comps}
    for y, h in zip(ys, hs):
        y = equilibrium_binding(base, y, h)
        for key, comp in comps.items():
            J[key].append(comp.fluxes(y, h)[flux])
    keys = list(comps)
    out = {}
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            ja, jb = np.array(J[keys[a]]), np.array(J[keys[b]])
            ok = (ja != 0) & (jb != 0)
            ratio = ja[ok] / jb[ok]
            dev = float(np.max(np.abs(ratio - 1))) if ok.any() else float("nan")
            out[f"{keys[a]} vs {keys[b]}"] = {"identical": bool(dev < 1e-9), "max_abs_ratio_minus_1": dev,
                                               "ratio_range": [float(np.min(ratio)), float(np.max(ratio))]}
    return out


# --------------------------------------------------------------------------- runs

def unique_names():
    """One name per distinct arm (the printed forms of Eqs. 1, 11 and 16 are MR1's published arm)."""
    seen, out = {}, []
    for name, arm in all_arms().items():
        if arm.label() not in seen:
            seen[arm.label()] = name
            out.append(name)
    return out, seen


def run(names, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    arms = all_arms()
    for name in names:
        arm = arms[name]
        try:
            res = R.run_arm(arm, mg_x_total=MG_RECOMMENDED, low_oxygen=False, check_every=False)
        except Exception as exc:   # recorded, not hidden
            res = {"arm": arm.label(), "error": repr(exc)}
        (out / f"{name}.json").write_text(json.dumps(res, indent=1, default=float))
        print(name, res.get("rms_z"), res.get("error"), flush=True)


def link_duplicates(out: Path):
    """Write each duplicate arm's JSON from its distinct twin's run."""
    _, seen = unique_names()
    for name, arm in all_arms().items():
        twin = seen[arm.label()]
        if twin != name and (out / f"{twin}.json").exists():
            (out / f"{name}.json").write_text((out / f"{twin}.json").read_text())


def departure(cand, base):
    worst = {"dPsi_mV": 0.0, "pH_x": 0.0, "NADH_frac": 0.0, "cytc_red_frac": 0.0, "O2_flux_rel": 0.0}
    b = {(st, r["Pi_e_mM"]): r for st in ("state4", "state3") for r in base["sweeps"][st]}
    for st in ("state4", "state3"):
        for r in cand["sweeps"][st]:
            q = b[(st, r["Pi_e_mM"])]
            for k in ("dPsi_mV", "pH_x", "NADH_frac", "cytc_red_frac"):
                worst[k] = max(worst[k], abs(r[k] - q[k]))
            worst["O2_flux_rel"] = max(worst["O2_flux_rel"], abs(r["MVO2_mol_per_s_per_l"] / q["MVO2_mol_per_s_per_l"] - 1))
    return worst


def state_dissipation(cand_name, res, flux):
    """Sign of -J dG at the candidate's own reported states, frames S and B (W per l mito)."""
    arms = all_arms()
    comp = M.compile_model(M.load(), arms[cand_name])
    run_ = R.Runner(arms[cand_name], mg_x_total=MG_RECOMMENDED, charge=res["charge_inventory_mol_per_l"])
    out = {"S_min_W_per_l": None, "B_min_W_per_l": None, "negative_at": []}
    for st, adp in (("state4", 0.0), ("state3", 1.3e-3)):
        for r in res["sweeps"][st]:
            h = run_.held(ADP_e=adp, Pi_e=r["Pi_e_mM"] * 1e-3)
            y = np.array(r["y"])
            J = comp.fluxes(y, h)[flux]
            gs, gb = frames(comp, y, h, flux)
            for tag, g in (("S", gs), ("B", gb)):
                if not np.isfinite(g):
                    continue
                d = -J * g * 1e3
                key = f"{tag}_min_W_per_l"
                out[key] = d if out[key] is None else min(out[key], d)
                if d < -1e-9:
                    out["negative_at"].append(f"{tag}:{st}:Pi{r['Pi_e_mM']:g}")
    return out


def table(runs: Path, out: Path):
    model = M.load()
    base = json.loads((runs / "eq24_restored_mr1.json").read_text())    # = MR1's published arm at 5 mM
    rows = []
    h_ref_state = None
    for eq, cands in CANDIDATES.items():
        ident = identities(eq)
        for key, field, value, ov, desc, role in cands:
            arm = arm_of(field, value, ov)
            comp = M.compile_model(model, arm)
            f = json.loads((runs / f"{key}.json").read_text()) if (runs / f"{key}.json").exists() else {}
            row = {"equation": eq, "candidate": key, "role": role, "form": desc, "switch": {field: value, **ov}}
            row["identical_to"] = sorted({k.replace(key, "").replace(" vs ", "") for k, v in ident.items()
                                          if v["identical"] and key in k.split(" vs ")})
            row["proportional_to"] = {k.replace(key, "").replace(" vs ", ""): v["ratio_range"]
                                      for k, v in ident.items() if not v["identical"] and key in k.split(" vs ")}
            row["sign_random_states"] = sign_counts(comp, field)
            if "sweeps" in f:
                r3 = next(r for r in f["sweeps"]["state3"] if r["Pi_e_mM"] == 10.0)
                h = R.Runner(arm, mg_x_total=MG_RECOMMENDED).held(ADP_e=1.3e-3, Pi_e=10e-3)
                zs, zb = zero_offsets(comp, np.array(r3["y"]), h, field)
                row["zero_offset_kJ_state3_Pi10"] = {"S": zs, "B": zb}
                row["dissipation_reported_states"] = state_dissipation(key, f, field)
                row["fit_rms_z_mg5"] = f["rms_z"]
                row["fit_max_abs_diff"] = f["summary"]
                row["departure_from_published_arm_mg5"] = departure(f, base)
            elif f:
                row["error"] = f.get("error")
            rows.append(row)
    for key, (sw, ov, desc) in COMBINED.items():
        f = json.loads((runs / f"{key}.json").read_text()) if (runs / f"{key}.json").exists() else {}
        row = {"equation": "combined", "candidate": key, "form": desc, "switch": sw}
        if "sweeps" in f:
            row["fit_rms_z_mg5"] = f["rms_z"]
            row["departure_from_published_arm_mg5"] = departure(f, base)
        rows.append(row)
    doc = {"kind": "cells.validation.mito_reference_repairs@1",
           "base": "MR1's published arm (2006 Table 1; Eq. 24 restored; Eqs. 11 and 16 printed; 298.15 K) at the recommended matrix Mg2+ total, 5 mM; matrix charge anchored to Fig. 4D's pH at [Pi]e = 0",
           "frames": __doc__.split("**Two thermodynamic frames.**")[1].split("Run:")[0].strip(),
           "appendix": "docs/MITOCHONDRIA_LAWS_APPENDIX.md at tag mito-laws-appendix-2026-11-20",
           "rows": rows}
    out.write_text(json.dumps(doc, indent=1, default=float))
    return doc


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="MR1: candidate repairs side by side")
    ap.add_argument("--runs", type=Path, required=True, help="workspace directory of the fit runs")
    ap.add_argument("--arms", default=None, help="comma list of candidates to fit, or 'all'")
    ap.add_argument("--table", type=Path, default=None, help="write the comparison JSON here")
    a = ap.parse_args(argv)
    if a.arms:
        names = unique_names()[0] if a.arms == "all" else a.arms.split(",")
        run(names, a.runs)
    if a.table:
        link_duplicates(a.runs)
        table(a.runs, a.table)


if __name__ == "__main__":
    sys.exit(main())
