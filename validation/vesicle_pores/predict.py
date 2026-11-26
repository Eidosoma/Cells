"""The blind test's stage-1 predictions (docs/VESICLE_PORES_LAWS.md §8, tagged
`pores-laws-sheet-registered-2026-11-22`; the lead's rulings D293, D294 and D295), computed from the
recorded fit (fit_rows.py) at the sealed extractor's conditions, before any held-out value is read.

**The prediction** at each held-out condition (σ, T) is the fitted law (cells.assembly_hazard.pore_nucleation@1):

    ln k_pred = ln C + ½·ln σ − (3/2)·ln T − E_A/(R·T) − (π/(k_B·T·σ))·Γ²

with (ln C, Γ²) and their unscaled covariance from the fit, and E_A = 27 kJ/mol fixed. It is taken
twice, by the engine's law function with Γ = (Γ²)^(1/2) and by the line in (ln C, Γ²) directly;
the two must agree to 10⁻¹² in ln k.

**Its terms** (§8):
- s_pred² = J·Σ·Jᵀ, J = (1, −π/(k_B·T·σ)), Σ the unscaled covariance of (ln C, Γ²);
- s_T = |∂ln k/∂T|·δT, ∂ln k/∂T = E_A/(R·T²) + σ_β/(σ·T) − 3/(2T), with δT = 0.5 K for set 1 (a
  column's position) and 1 K for set 2 (25 ± 1 °C; D293 item 1, D294 item 4);
- s_dig: 0.03 for set 1; 0 for set 2's osmotic rows, whose rates are tabulated (§8; the lead's
  ruling of 22 November 2026: D294 item 5's Fig. 1C rule governs only how s_read is read from the
  bars); for set 2's controls, digitised from Fig. 1C, max(0.03, the ln k span of 2 pixels on its
  y-axis), set at stage 2 from the axis calibration (D294 item 5), so recorded as its rule and
  floor;
- s_area, set 2's only: 0.03 (D295: Shibly's ±0.2 µm on r0 ≈ 13.5 µm, 2 × 0.2/13.5);
- t₀.₉₇₅,₂ = 4.303. s_read is stage 2's.

**The points and their modes:**
- set 1 (Karal and Yamazaki 2015, Fig. 2a), T = 10⁶/x at each column's plotted position (D293
  item 1): S1-1 to S1-5 scored two-sided, S1-4 and S1-5 flagged `extrapolated` (below 297 K);
  S1-6 (12 °C, 8.0 mN/m) predicted, reported only (D293 item 2), and extrapolated too;
- set 2 (Shibly et al. 2016), T = 298.15 K, the area ratio 1 under D295's premise: the six osmotic
  rows scored one-sided at σ_ex (D287, D293), the quoted count's matched point to be dropped from
  scoring at stage 2 (D293 item 6); the controls at 7.0, 7.5 and 8.0 mN/m and a point at
  6.5 mN/m with ΔC₀ = 0, reported only (D294 item 1).

Usage: python -m validation.vesicle_pores.predict FIT.json STAGE1.json STAGE1B.json STAGE1C.json
OUT.json
"""

import hashlib
import json
import math
import sys
from pathlib import Path

from cells.models.assembly_lineages_v2 import pore_nucleation as law

SHEET_TAG = "pores-laws-sheet-registered-2026-11-22"
FORMAT = "cells.vesicle_pores.predictions@1"
E_A_J_PER_MOL = 27e3  # fixed, as in the fit (the sheet's §4)
T_975_2 = 4.303  # the two-sided 95% t value for three experiments per setting (§8)
IN_RANGE_K = (297.0, 334.0)  # E_A's range, 298-333 K, with 1 K at each end (§4)
SET1_DT_K = 0.5  # a column's position on the 10⁶/T axis (§8)
SET1_S_DIG = 0.03  # the vertical reading (§8; D293 item 7)
SET2_T_K, SET2_DT_K = 298.15, 1.0  # 25 ± 1 °C (D293 item 1; D294 item 4 for the controls)
SET2_S_DIG_TABULATED = 0.0  # the osmotic rows' rates are tabulated (§8; the lead, 22 November)
SET2_S_DIG = {"floor": 0.03, "rule": "max(0.03, the ln k span of 2 pixels on Fig. 1C's y-axis), "
              "the pixel scale from the axis calibration at stage 2 (D294 item 5)"}  # fmt: skip
SET2_S_AREA = 0.03  # D295: 2 x 0.2/13.5, Shibly's stated ±0.2 µm on r0 of about 13.5 µm
CONTROL_EXTRA_MN_M = 6.5  # D294 item 1: recorded in case stage 2 finds a control there


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point_terms(fit, sigma, temperature, dt):
    """(ln k_pred by the law, by the line, s_pred, ∂ln k/∂T, s_T) at (σ N/m, T K) and δT K."""
    ln_c, gamma2 = fit["estimates"]["ln_C"], fit["estimates"]["gamma2_N2"]
    (v_c, c_cg), (_, v_g) = fit["covariance_unscaled"]["matrix"]
    x = law.sigma_beta(1.0, temperature) / sigma  # π/(k_B·T·σ)
    by_law = law.log_rate_per_area(sigma, temperature, ln_c, math.sqrt(gamma2), E_A_J_PER_MOL)
    by_line = (ln_c + 0.5 * math.log(sigma) - 1.5 * math.log(temperature)
               - E_A_J_PER_MOL / (law.R * temperature) - x * gamma2)  # fmt: skip
    s_pred = math.sqrt(v_c + x * x * v_g - 2.0 * x * c_cg)
    slope = law.dlog_rate_dt(sigma, temperature, math.sqrt(gamma2), E_A_J_PER_MOL)
    return by_law, by_line, s_pred, slope, abs(slope) * dt


def _point(fit, birge, ident, source, sigma, temperature, dt, mode, s_dig, s_area, flags,
           **extra):  # fmt: skip
    by_law, by_line, s_pred, slope, s_t = point_terms(fit, sigma, temperature, dt)
    if abs(by_law - by_line) > 1e-12:
        raise AssertionError(f"{ident}: the law and the line differ by {by_law - by_line:.3g}")
    lo, hi = IN_RANGE_K
    domain = "in_range" if lo <= temperature <= hi else "extrapolated"
    floor = s_dig if isinstance(s_dig, float) else s_dig["floor"]
    known = [s_pred, s_t, floor] + ([s_area] if s_area is not None else [])
    return {
        "id": ident,
        "source": source,
        "sigma_N_per_m": sigma,
        "T_K": temperature,
        "dT_K": dt,
        **extra,
        "ln_k_pred": by_law,
        "ln_k_pred_by_line": by_line,
        "k_pred_per_s": math.exp(by_law),
        "s_pred": s_pred,
        "dlnk_dT_per_K": slope,
        "s_T": s_t,
        "s_dig": s_dig,
        "s_area": s_area,
        "t": T_975_2,
        "tau_without_s_read": T_975_2 * math.sqrt(math.fsum(v * v for v in known)),
        "tau_without_s_read_note": "t (s_pred^2 + s_T^2 + s_dig^2"
        + (" + s_area^2" if s_area is not None else "") + ")^(1/2)"
        + (", s_dig at its floor" if not isinstance(s_dig, float) else ""),
        "mode": mode,
        "domain": domain,
        "flags": (["extrapolated"] if domain == "extrapolated" else []) + flags,
        "s_pred_birge_unscored": s_pred * math.sqrt(birge),
    }


def predictions(fit, stage1, stage1b):
    """Every held-out point's prediction and terms, in the extractor's order (module docstring)."""
    birge = fit["birge_view"]["factor"]
    out = []
    karal = "Karal and Yamazaki 2015, Fig. 2(a)"
    for p in stage1["set1"]["held_out_points"]:
        temperature = 1e6 / p["inv_T_1e6"]
        reported = p["id"] == "S1-6"
        flags = ["reported only: FR-31 quotes 12 °C survival from the same paper (D293 item 2)"]
        out.append(_point(
            fit, birge, p["id"], karal, p["tension_mN_m"] * 1e-3, temperature, SET1_DT_K,
            "reported" if reported else "two_sided", SET1_S_DIG, None,
            flags if reported else [], set=1, inv_T_1e6=p["inv_T_1e6"],
        ))  # fmt: skip
    shibly = "Shibly et al. 2016, Tables 1-2 (rates) and Fig. 1C (standard errors)"
    candidates = {c["id"] for c in stage1["set2"]["quoted_count"]["candidates"]}
    premise = (
        "the area ratio is 1 under D295's declared premise (one laboratory, one method, one "
        "period): a failure may come from a size difference between preparations"
    )
    for p in stage1["set2"]["tabulated_points"]:
        flags = [premise]
        if p["id"] in candidates:
            flags.append("a candidate for the quoted survival count: the point it matches at stage "
                         "2 is reported, not scored, and every candidate if the match is ambiguous "
                         "(D293 item 6)")  # fmt: skip
        out.append(_point(
            fit, birge, p["id"], shibly, p["sigma_ex_mN_m"] * 1e-3, SET2_T_K, SET2_DT_K,
            "one_sided", SET2_S_DIG_TABULATED, SET2_S_AREA, flags, set=2, dC0_mM=p["dC0_mM"],
            area_ratio=1.0,
        ))  # fmt: skip
    controls = [(c["id"], c["sigma_ex_mN_m"]) for c in stage1b["set2_controls"]["control_points"]]
    controls.append(("S2-C0", CONTROL_EXTRA_MN_M))
    for ident, tension in controls:
        flags = ["reported only: a control from the fit data's laboratory and method paper, whose "
                 "independence cannot be shown (D294 item 1)"]  # fmt: skip
        if ident == "S2-C0":
            flags.append("recorded in case stage 2 finds a control at 6.5 mN/m (D294 item 1)")
        out.append(_point(
            fit, birge, ident, "Shibly et al. 2016, Fig. 1C open squares (ref. 27's data)",
            tension * 1e-3, SET2_T_K, SET2_DT_K, "reported", SET2_S_DIG, SET2_S_AREA, flags,
            set=2, dC0_mM=0.0, area_ratio=1.0,
        ))  # fmt: skip
    return out


def main(argv):
    fit_path, s1, s1b, s1c, out_path = (Path(a) for a in argv[1:6])
    fit = json.loads(fit_path.read_text())
    stage1, stage1b = json.loads(s1.read_text()), json.loads(s1b.read_text())
    record = {
        "format": FORMAT,
        "standing": "the blind test's stage-1 predictions, computed before any held-out value is "
        "read (the sheet's §8; D293, D294, D295)",
        "sheet": SHEET_TAG,
        "law": "cells.assembly_hazard.pore_nucleation@1 (src/cells/models/assembly_lineages_v2/pore_nucleation.py)",
        "fit": {
            "path": str(fit_path),
            "sha256": _sha256(fit_path),
            "estimates": fit["estimates"],
            "covariance_unscaled": fit["covariance_unscaled"],
            "chi2": fit["chi2"],
            "dof": fit["dof"],
            "birge_factor_unscored": fit["birge_view"]["factor"],
        },  # fmt: skip
        "conditions": {p.name: _sha256(p) for p in (s1, s1b, s1c)},
        "inputs": {
            "E_A_J_per_mol": E_A_J_PER_MOL,
            "R_J_per_mol_K": law.R,
            "k_B_J_per_K": law.K_B,
            "in_range_K": list(IN_RANGE_K),
        },  # fmt: skip
        "rule": {
            "tau": "t (s_read^2 + s_dig^2 + s_T^2 + s_pred^2 [+ s_area^2, set 2])^(1/2), t = 4.303",
            "two_sided": "passes when |ln k_pred - ln k_read| <= tau",
            "one_sided": "passes when ln k_read >= ln k_pred(sigma_ex) - tau",
            "reported": "predicted and reported beside the verdicts, not scored",
            "no_bar": "a set-2 point with no readable bar is reported, not scored (D293 item 5)",
            "verdicts": "set 1 and set 2, and in-range and extrapolated points, reported apart",
        },
        "disclosures": [
            "a vesicle's first rupture is taken as its first opening (declared, uncited; §2)",
            "set 2 rests on D295's premise of equal vesicle sizes across the two preparations",
            "the unscored Birge view scales s_pred by sqrt(max(1, chi2/dof)), beside the verdict",
            "the disclosed alternative temperature law (§4) is not computed here: it lives outside "
            "committed files",
        ],
        "points": predictions(fit, stage1, stage1b),
    }
    text = json.dumps(record, indent=1, ensure_ascii=False)
    out_path.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv)
