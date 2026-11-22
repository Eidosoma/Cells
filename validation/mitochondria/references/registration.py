"""MR1's registration as MT-2's model-level reference (D236).

Builds ``mr1_mt2_registration.json`` and its rendering from the ``mr1_mt2`` arm's full-check
run: the arm's inputs, the 12 reported states with tolerances, MR1's own convergence floor,
the fit and departures as recorded, the thermodynamic checks, and what MR1 does not claim.

Run: ``python -m validation.mitochondria.references.registration --run RUN.json
--published PUBLISHED.json --out mr1_mt2_registration.json --markdown mr1_mt2_registration.md``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import model as M
from . import repairs as P

APPENDIX_TAG = "mito-laws-appendix-2026-11-20b"
APPENDIX_COMMIT = "c9c5be1fda8ab316e51926de53fc405be49186c7"

TOLERANCES = {
    "dPsi_mV": {"abs": 0.05, "unit": "mV"},
    "pH_x": {"abs": 0.0005, "unit": "1"},
    "NADH_frac": {"abs": 0.0005, "unit": "1"},
    "cytc_red_frac": {"abs": 0.0005, "unit": "1"},
    "O2_flux_mol_per_s_per_l": {"rel": 0.001, "unit": "mol O2 s^-1 (l mito)^-1"},
    "K_x_mM": {"rel": 0.001, "unit": "mM"},
    "Pi_x_mM": {"rel": 0.001, "unit": "mM"},
    "ATP_x_mM": {"rel": 0.001, "unit": "mM"},
}
BAND_BASIS = ("A stated physical scale: about a third of the published figures' 1-px resolution (0.13 mV, 0.0033 pH, "
              "0.001 fraction), far above MR1's convergence floor (below). Not derived from any engine output.")

LAW_MATCH = [
    ("Eq. 1, held_reductant_supply@1 (section 6)", "eq1_balanced_supply, h_ref = 10^-7.10 M",
     "J = X_DH phi_DH (r[NAD] - [NADH] h_N/10^-7.10 M); dG/RT = ln([NADH]/(r[NAD])) + ln(h_N/10^-7.10 M): identical"),
    ("Eqs. 2-5, complex I (section 1.1)", "printed", "declared = printed: identical"),
    ("Eqs. 6, 7, 24, complex III (section 1.2)", "eq24_with_eq7_proton_term",
     "Eq. 24 restored as phi_Pi x Eq. 7: identical"),
    ("Eqs. 8, 9, complex IV (section 1.3)", "printed, per 1/2 O2",
     "the appendix's law per O2 is half the printed flux per 1/2 O2: the same physics, identical"),
    ("Eqs. 10, 11, ATP synthesis (section 2)", "eq11_appendix_balanced",
     "printed forward term, backward x (1e-7/h_N)(1 + h_N/k_dH)/(1 + 1e-7/k_dH): identical"),
    ("Eq. 14, nucleotide exchange (section 3)", "printed", "declared = printed (shares 0.35 + 0.65 = 1): identical"),
    ("Eqs. 15, 16, phosphate carrier (section 4)", "eq16_appendix_balanced",
     "printed forward term, backward [H2PO4-]_N h_N^2/h_P: identical"),
    ("Eq. 21, K+/H+ exchange (section 5)", "printed", "declared = printed: identical"),
    ("Eqs. 17, 18, IMS adenylate kinase (section 7)", "eq18_base_forms, K_base = 0.388964538",
     "X_AK (1 + [Mg2+]_P/K_MgATP)(K_base [ADP3-]^2 - [AMP2-][ATP4-]) = the source's form on totals with "
     "K_tot = K_base (1 + m/K_MgATP)/(1 + m/K_MgADP)^2: identical at binding equilibrium (every steady state)"),
    ("Eq. 13, outer membrane (section 8)", "printed, on totals",
     "the appendix's per-form Fick fluxes sum to Eq. 13's totals exactly; with the IMS free Mg2+ held (declared with "
     "the world) the steady states are identical"),
    ("Eq. 22's proton row, frame B (section 0)", "pi_protons_counted",
     "the total counts the protons on phosphate and on the buffer; coefficients -5, -2, -8 per O2 (= -4 per 1/2 O2), "
     "+(n_A - 1), +2, -1, +1, +1: identical"),
    ("Constants (section 0)", "T = 298.15 K; exact SI R and F", "identical"),
    ("Parameters (section 9)", "Table 1 (2006), with phosphate control",
     "all 29 listed values equal MR1's; declared pH_ref 7.10, dG_S = 0 at pH 7, K_base, Mg2+ total 5 mM: identical"),
    ("Not covered by the appendix (section 12)", "the source's forms",
     "proton leak (Eq. 19), passive K+ (Eq. 20, X_K = 0), Mg2+ binding (Eq. 12; MR1 kinetic at X_MgA = 1e6, at "
     "equilibrium in every steady state), the matrix buffer r_buff, C_IM = 6.75e-6"),
]

NON_CLAIMS = [
    "Not Beard's published model. The D236 repairs move it from MR1's published arm by the departures given here; "
    "at this Mg2+ total the published arm fits the published curves at rms z 1.40, MR1-MT2 at 3.72.",
    "Not the measured data (Bose et al. 2003), which MR1 never read; a later question (D151).",
    "Conditional on declared inputs the source does not report: 298.15 K; the matrix Mg2+ total (5 mM); the matrix "
    "charge inventory (anchored to Fig. 4D's pH at [Pi]e = 0, recorded here as a number); the IMS free Mg2+ (the "
    "buffer's free Mg2+); the reference pH 7.10 of the supply.",
    "Steady states only. The model was fitted to steady states; no transient is claimed. Transients need a rapid "
    "Mg2+-binding closure (Q15: at X_MgA = 1e6 an ADP step drives IMS free ADP negative).",
    "Q15, random binding: with Mg2+ binding away from equilibrium, F1F0 (Eq. 11 reads Mg-bound forms, Eq. 22 books "
    "free forms) and the base-form kinase (it reads totals through the free Mg2+) can dissipate negatively. Every "
    "steady state has binding at equilibrium, and a rapid binding closure removes it; it is not a property of the "
    "reported states.",
    "MVO2 in the figures' units (per mol cytochrome a) is not claimed: no conversion is reported, and MR1's scale is one anchor.",
    "Host P only (D235): a matrix, an IMS node and a held buffer. No cell, no calcium, no low-oxygen rows (P50 is "
    "not part of this registration).",
    "The ATP and AMP effluxes into a buffer held at zero have unbounded dissipation; they are excluded from every "
    "dissipation check.",
]


def build(run: dict, published: dict) -> dict:
    states = []
    for st, adp in (("state4", 0.0), ("state3", 1.3)):
        for r in run["sweeps"][st]:
            states.append({
                "state": st, "ADP_e_mM": adp, "Pi_e_mM": r["Pi_e_mM"],
                "dPsi_mV": r["dPsi_mV"], "pH_x": r["pH_x"], "NADH_frac": r["NADH_frac"],
                "cytc_red_frac": r["cytc_red_frac"], "O2_flux_mol_per_s_per_l": r["MVO2_mol_per_s_per_l"],
                "K_x_mM": r["K_x_mM"], "Pi_x_mM": r["Pi_x_mM"], "ATP_x_mM": r["ATP_x_mM"],
                "IMS_free_Mg_mM": None,
                "integration_vs_newton_rel": r.get("integration_vs_newton_rel"),
                "newton_residual": r["newton_residual"]})
    model = M.load()
    arm = P.all_arms()["mr1_mt2"]
    from . import reproduce as R
    runner = R.Runner(arm, mg_x_total=P.MG_RECOMMENDED)
    for s in states:
        s["IMS_free_Mg_mM"] = 1e3 * runner.held(ADP_e=s["ADP_e_mM"] * 1e-3, Pi_e=s["Pi_e_mM"] * 1e-3)["Mg_i"]
    sw, ov, desc = P.COMBINED["mr1_mt2"]
    fc = {k: run[k] for k in ("existence", "uniqueness_state3_Pi3", "dissipation_reported_states",
                              "dissipation_random_states_binding_at_equilibrium",
                              "dissipation_random_states_binding_random")}
    return {
        "kind": "cells.validation.mito_reference_registration@1",
        "name": "MR1-MT2",
        "role": "MT-2's model-level reference (D236), written code-blind from Beard 2005 and its 2006 correction",
        "status": "prepared for registration before any engine organelle output exists; the coordinator's tag registers it",
        "arm": {"name": "mr1_mt2", "switches": sw, "overrides": ov, "description": desc, "label": arm.label(),
                "T_K": arm.T, "matrix_Mg_total_M": P.MG_RECOMMENDED,
                "matrix_charge_inventory_mol_per_l_mito": run["charge_inventory_mol_per_l"],
                "charge_inventory_definition": "V_x (ln[H+]x/(100 M^-1) + [Pi]x h/(h + k_dH) + [K+]x - [NADH]x - [ATP]x - 2[Pi]x) + C_IM dPsi, conserved by Eq. 22 (frame B), anchored to pH_x = 7.1418 at [Pi]e = 0, state 4",
                "IMS_free_Mg_rule": "held at the buffer's free Mg2+ (5.0 mM total; Table 1 binding constants)",
                "buffer": {"pH_e": 7.1, "K_e_mM": 150, "Mg_total_mM": 5.0, "ATP_e": 0, "AMP_e": 0,
                           "ADP_e_mM": [0, 1.3], "Pi_e_mM": [0, 1, 2, 3, 5, 10], "O2_M": 2.6e-5},
                "parameters": "beard2005_model.json, Table 1 (2006), with phosphate control"},
        "appendix": {"tag": APPENDIX_TAG, "commit": APPENDIX_COMMIT,
                     "match": [{"law": a, "MR1": b, "result": c} for a, b, c in LAW_MATCH]},
        "reported_states": states,
        "tolerances": TOLERANCES, "band_basis": BAND_BASIS,
        "convergence_floor": fc["existence"] | {"uniqueness_three_starts_rel": fc["uniqueness_state3_Pi3"]["max_relative_spread"]},
        "fit_rms_z_to_published_curves": run["rms_z"],
        "fit_max_abs_diff_per_panel": {k: v["max_abs_diff"] for k, v in run["summary"].items()},
        "departure_from_published_arm": P.departure(run, published),
        "thermodynamics": {k: {"negative_states": v["negative_states"], "processes_counted": len(v["states_counted"])}
                           for k, v in fc.items() if k.startswith("dissipation")},
        "non_claims": NON_CLAIMS,
    }


def markdown(doc: dict) -> str:
    a = doc["arm"]
    L = ["# MR1-MT2: registration of MT-2's model-level reference", "",
         "*Generated by `registration.py` from `mr1_mt2_registration.json`; do not edit by hand.*", "",
         f"**Status:** {doc['status']}.", "",
         f"**Arm:** `{a['name']}`. {a['description']}", "",
         f"- T = {a['T_K']} K; matrix Mg2+ total {1e3 * a['matrix_Mg_total_M']:g} mM; matrix charge inventory "
         f"{a['matrix_charge_inventory_mol_per_l_mito']:.12g} mol per l mito ({a['charge_inventory_definition']}).",
         f"- IMS free Mg2+: {a['IMS_free_Mg_rule']}.",
         f"- Buffer: {json.dumps(a['buffer'])}.", "",
         f"**Appendix:** `{doc['appendix']['tag']}` ({doc['appendix']['commit'][:8]}), checked term by term:", ""]
    for m in doc["appendix"]["match"]:
        L.append(f"- {m['law']}: MR1 `{m['MR1']}`: {m['result']}.")
    L += ["", "**The 12 reported states** (tolerances: " + ", ".join(
        f"{k} {('+-' + str(v['abs'])) if 'abs' in v else ('+-' + str(100 * v['rel']) + '%')}" for k, v in doc["tolerances"].items())
        + f"). {doc['band_basis']}", "",
        "| State | [Pi]e mM | dPsi mV | pH_x | NADH/NAD_tot | cyt c red | O2 flux mol/s/l | K_x mM | Pi_x mM | ATP_x mM | IMS free Mg2+ mM |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in doc["reported_states"]:
        L.append(f"| {s['state']} | {s['Pi_e_mM']:g} | {s['dPsi_mV']:.4f} | {s['pH_x']:.5f} | {s['NADH_frac']:.5f} | "
                 f"{s['cytc_red_frac']:.5f} | {s['O2_flux_mol_per_s_per_l']:.6e} | {s['K_x_mM']:.4f} | {s['Pi_x_mM']:.5f} | "
                 f"{s['ATP_x_mM']:.5f} | {s['IMS_free_Mg_mM']:.6f} |")
    cf = doc["convergence_floor"]
    d = doc["departure_from_published_arm"]
    L += ["", f"**Convergence floor:** integration against the 50-digit Newton solve within "
              f"{cf['max_integration_vs_newton_rel']:.1e} relative; Newton residual {cf['max_newton_residual']:.1e}; "
              f"three far-apart starts within {cf['uniqueness_three_starts_rel']:.1e}.", "",
          f"**Fit to the published curves:** rms z {doc['fit_rms_z_to_published_curves']:.4f}.", "",
          f"**Departure from MR1's published arm** (same Mg2+ total, 12 states): dPsi {d['dPsi_mV']:.3f} mV, pH "
          f"{d['pH_x']:.4f}, NADH {d['NADH_frac']:.4f}, cyt c {d['cytc_red_frac']:.4f}, O2 flux {100 * d['O2_flux_rel']:.2f}%.", "",
          "**Thermodynamics (every process, frame B):**"]
    for k, v in doc["thermodynamics"].items():
        L.append(f"- {k.replace('_', ' ')}: negative at {v['negative_states'] or 'none'} "
                 f"({v['processes_counted']} processes counted).")
    L += ["", "**What MR1-MT2 does not claim:**", ""] + [f"- {x}" for x in doc["non_claims"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--published", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--markdown", type=Path, required=True)
    a = ap.parse_args(argv)
    doc = build(json.loads(a.run.read_text()), json.loads(a.published.read_text()))
    a.out.write_text(json.dumps(doc, indent=1, default=float) + "\n")
    a.markdown.write_text(markdown(doc))


if __name__ == "__main__":
    sys.exit(main())
