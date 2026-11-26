"""The fit on the six read points (docs/VESICLE_PORES_LAWS.md §8, tagged
`pores-laws-sheet-registered-2026-11-22`): a disclosed comparison with no pass or fail (D287).

The model is the engine's law (cells.assembly_hazard.pore_nucleation@1, src/cells/models/assembly_lineages_v2/
pore_nucleation.py), with C = A·ν_A:

    ln k_i = ln C + ½·ln σ_i − (3/2)·ln T_i − E_A/(R·T_i) − (π/(k_B·T_i·σ_i))·Γ²

It is linear in (ln C, Γ²). y_i is ln k_i less the law's Γ-free part, and x_i = π/(k_B·T_i·σ_i), so
y = ln C − Γ²·x. The fit is weighted least squares with weights 1/s_i², in the centred closed
form, since x is about 10²³. The covariance is the unscaled one (the lead's ruling). The
Birge-scaled view, max(1, χ²/4), is reported beside it, unscored and labelled so.

The temperatures are the unrounded quotients of the extraction's 10⁶/T readings (the sheet's §0):
T₂₅ = 10⁶/3356 K and T₃₂ = 10⁶/3279 K.

Usage: python -m validation.vesicle_pores.fit_rows [DATA.json] [OUT.json]
"""

import hashlib
import json
import math
import sys
from pathlib import Path

from cells.models.assembly_lineages_v2 import pore_nucleation as law

SHEET_TAG = "pores-laws-sheet-registered-2026-11-22"
DATA = Path("lean/checks/data/karal2015_rupture_rates.json")
E_A_J_PER_MOL = 27e3  # Filippov, Orädd and Lindblom 2003, Table 1, pure DOPC (the sheet's §4)
INVERSE_T_READING = {25: 3356.0, 32: 3279.0}  # the extraction's 10⁶/T positions (the sheet's §0)


def rows(data):
    """[(T_K, σ_N_per_m, ln k, s)] from the data file's points, s = half the bar caps' spread."""
    out = []
    for t_c, tension_mn_m, ln_k, ln_lo, ln_hi in data["points"]:
        t_k = 1e6 / INVERSE_T_READING[int(t_c)]
        out.append((t_k, tension_mn_m * 1e-3, ln_k, (ln_hi - ln_lo) / 2.0))
    return out


def weighted_line(xs, ys, ws):
    """y = a + b·x by weighted least squares, centred: (a, b, var_a, var_b, cov_ab)."""
    sw = math.fsum(ws)
    xbar = math.fsum(w * x for w, x in zip(ws, xs, strict=True)) / sw
    ybar = math.fsum(w * y for w, y in zip(ws, ys, strict=True)) / sw
    sxx = math.fsum(w * (x - xbar) ** 2 for w, x in zip(ws, xs, strict=True))
    sxy = math.fsum(w * (x - xbar) * (y - ybar) for w, x, y in zip(ws, xs, ys, strict=True))
    b = sxy / sxx
    a = ybar - b * xbar
    return a, b, 1.0 / sw + xbar**2 / sxx, 1.0 / sxx, -xbar / sxx


def fit(points, e_a=E_A_J_PER_MOL):
    """The sheet's §8 fit: estimates, unscaled covariance, χ², residuals and the Birge view."""
    xs = [law.sigma_beta(1.0, t) / s for t, s, _, _ in points]  # π/(k_B·T·σ), with Γ = 1 N
    ys = [lk - law.log_rate_per_area(s, t, 0.0, 0.0, e_a) for t, s, lk, _ in points]
    ws = [1.0 / se**2 for *_, se in points]
    a, b, var_a, var_b, cov_ab = weighted_line(xs, ys, ws)
    gamma2 = -b
    if not gamma2 > 0:
        raise ValueError(f"The fit gives Γ² = {gamma2!r} ≤ 0: refused (the sheet's §8)")
    gamma = math.sqrt(gamma2)
    fitted = [law.log_rate_per_area(s, t, a, gamma, e_a) for t, s, _, _ in points]
    resid = [(lk - f) / se for (_, _, lk, se), f in zip(points, fitted, strict=True)]
    chi2 = math.fsum(r * r for r in resid)
    dof = len(points) - 2
    birge = max(1.0, chi2 / dof)
    cov = [[var_a, -cov_ab], [-cov_ab, var_b]]  # (ln C, Γ²): Γ² = −b flips the cross term's sign
    return {
        "estimates": {"ln_C": a, "gamma2_N2": gamma2, "gamma_N": gamma, "gamma_pN": gamma * 1e12},
        "covariance_unscaled": {"order": ["ln_C", "gamma2_N2"], "matrix": cov},
        "chi2": chi2,
        "dof": dof,
        "rows": [
            {
                "T_K": t,
                "sigma_N_per_m": s,
                "ln_k_read": lk,
                "s": se,
                "ln_k_fitted": f,
                "residual_in_s": r,
            }
            for (t, s, lk, se), f, r in zip(points, fitted, resid, strict=True)
        ],  # fmt: skip
        "birge_view": {
            "label": "unscored: the covariance scaled by max(1, chi2/dof), beside the verdict only",
            "factor": birge,
            "matrix": [[birge * c for c in row] for row in cov],
        },
    }


def main(argv):
    data_path = Path(argv[1]) if len(argv) > 1 else DATA
    raw = data_path.read_bytes()
    result = fit(rows(json.loads(raw)))
    result = {
        "standing": "a disclosed comparison on the six read points, with no pass or fail (D287)",
        "sheet": SHEET_TAG,
        "law": "cells.assembly_hazard.pore_nucleation@1 (src/cells/models/assembly_lineages_v2/pore_nucleation.py)",
        "data": {"path": str(data_path), "sha256": hashlib.sha256(raw).hexdigest()},
        "inputs": {
            "E_A_J_per_mol": E_A_J_PER_MOL,
            "T_K": {str(k): 1e6 / v for k, v in INVERSE_T_READING.items()},
            "C": "A·ν_A, in s⁻¹·(N/m)^(−1/2)·K^(3/2)",
        },  # fmt: skip
        **result,
    }
    text = json.dumps(result, indent=1, ensure_ascii=False)
    if len(argv) > 2:
        Path(argv[2]).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv)
