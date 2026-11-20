"""FR-29's desk evaluation of the proton-return mode against Kettner et al. (2003) Fig. 3 (D258).

The design note's family (docs/PROTON_RETURN_MODE_DESIGN.md §1.3, §2.1) in closed form, as a
desk computation: no engine code. The pump mode is today's proton pump, n = 2 H+ per ATP,
saturated in ATP and in cytosolic H+, its drive at Table 2's E_ATP. The return moves one H+ from
the vacuole to the cytosol through one site, loaded from the vacuole and emptied to the
cytosol, with a bounded voltage term:

    I = A [n (1 - e^(x_c)) - rho th_v th_c b(psi) (1 - e^(x_r))]           (mA m^-2)
    x_c = (E_ATP + n (E_H - V)) / (RT/F),   x_r = (V - E_H) / (RT/F),   psi = V / (RT/F)
    th_v = h_v / (h_v + K),   th_c = K / (K + h_c)
    b(psi) = e^(-delta psi) / (1 + e^(-delta (psi - psi_s)))

V is cytosol minus vacuole (mV) and E_H = (RT/F) ln(h_v / h_c). The current is positive from the
cytosol into the vacuole, the pumping direction, as Fig. 3 draws it.

Two steps, in this order (the lead's instruction of 20 November 2026):
- `predict OUT`: fit delta, psi_s, rho, pK and the scale A on panel B's vacuolar pH 6.0 and 4.1
  curves below -5 mV, reading only those rows. It then writes the prediction for panel A's four
  curves and the three bounds, with the scoring rules, to OUT. It never reads panel A's rows.
- `score PREDICTION OUT`: loads panel A's rows and scores the prediction as written.
- `joint OUT`: the family question. It fits every curve's separable stretch, with the pH 3.1 bound
  as a constraint, and reports whether any member satisfies both.

E_ATP is Table 2's estimate by cytosolic pH, a bare cited number (D227). Temperature is 298.15 K,
which the table's E_H implies; the source states none.
"""

import argparse
import csv
import hashlib
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, least_squares

HERE = Path(__file__).resolve().parent
READINGS = HERE / "kettner2003_fig3_readings.csv"
RT_F_MV = 8.31446261815324 * 298.15 / 96485.33212331001 * 1e3
N = 2  # H+ per ATP: the paper's N and the note's registered value.
# Table 2 (Kettner et al. 2003, doi:10.1016/S0006-3495(03)74789-4): E_ATP (mV) by cytosolic pH,
# the authors' estimate from their Table 1's K_ATP and free Mg-ATP.
E_ATP_MV = {8.5: -587.5, 7.5: -531.4, 6.0: -491.9, 5.0: -494.0}
FIT = ((7.5, 6.0), (7.5, 4.1))  # Panel B's vacuolar pH 6.0 and 4.1 curves: rows 5 and 3.
PANEL_A = ((5.0, 5.0), (6.0, 5.0), (7.5, 5.0), (8.5, 5.0))  # Cytosolic pH, vacuolar pH.
BOUNDS = (  # Table 2's three bounds: (cytosolic pH, vacuolar pH, relation, mV).
    (7.5, 3.1, ">", 40.0),  # Row 2, from Fig. 2.
    (5.0, 5.0, "<", -80.0),  # Row 7, panel A's cytosolic pH 5 curve.
    (7.5, 7.5, "<", -80.0),  # Row 8, panel B's vacuolar pH 7.5 curve.
)
GRID_MV = np.arange(-80.0, 60.0 + 1e-9, 5.0)
PARAMETERS = ("delta", "V_s_mV", "rho", "pK", "A_mA_per_m2")


def current(params, ph_c, ph_v, v_mv):
    """The family's current density (mA m^-2) at voltages v_mv for one pH pair."""
    delta, v_s, rho, pk, scale = params
    v = np.asarray(v_mv, dtype=float)
    h_c, h_v = 10.0**-ph_c, 10.0**-ph_v
    e_h = RT_F_MV * math.log(h_v / h_c)
    x_c = (E_ATP_MV[ph_c] + N * (e_h - v)) / RT_F_MV
    x_r = (v - e_h) / RT_F_MV
    k = 10.0**-pk
    occupied = h_v / (h_v + k) * k / (k + h_c)
    psi, psi_s = v / RT_F_MV, v_s / RT_F_MV
    bounded = np.exp(-delta * psi - np.logaddexp(0.0, -delta * (psi - psi_s)))
    pump = N * -np.expm1(np.minimum(x_c, 700.0))
    back = rho * occupied * bounded * -np.expm1(x_r)
    return scale * (pump - back)


def reversal(params, ph_c, ph_v, lo=-200.0, hi=200.0):
    """The current's first zero crossing from lo upwards (mV), or None where it has none."""
    grid = np.linspace(lo, hi, 4001)
    values = current(params, ph_c, ph_v, grid)
    for a, b, fa, fb in zip(grid[:-1], grid[1:], values[:-1], values[1:], strict=True):
        if np.isfinite(fa) and np.isfinite(fb) and fa * fb <= 0 and fa != fb:
            return brentq(lambda v: float(current(params, ph_c, ph_v, [v])[0]), a, b)
    return None


def rows(panel, pairs, *, below_mv=None):
    """The readings of the named curves only. Every other row is dropped as it is read, never
    used."""
    out = []
    with READINGS.open() as f:
        for r in csv.DictReader(f):
            if r["panel"] != panel or not r["pH_cyt"] or not r["pH_vac"]:
                continue
            pair = (float(r["pH_cyt"]), float(r["pH_vac"]))
            if pair not in pairs or not r["I_mA_per_m2"]:
                continue
            v = float(r["V_mV"])
            if below_mv is not None and not v < below_mv:
                continue
            out.append((pair, v, float(r["I_mA_per_m2"]), r["flags"], r["identity"]))
    return out


def fit(data, starts):
    """Least squares over the family's five parameters, from several starts: the best."""

    def residuals(x):
        params = (x[0], x[1], math.exp(x[2]), x[3], math.exp(x[4]))
        return np.concatenate([
            current(params, *pair, [v]) - i for pair, v, i, *_ in data
        ])  # fmt: skip

    lower, upper = [0.0, -300.0, -12.0, 3.0, -5.0], [1.0, 100.0, 12.0, 10.0, 8.0]
    best = None
    for start in starts:
        try:
            s = least_squares(residuals, start, bounds=(lower, upper))
        except ValueError:
            continue
        if best is None or s.cost < best.cost:
            best = s
    x = best.x
    params = (x[0], x[1], math.exp(x[2]), x[3], math.exp(x[4]))
    rms = float(np.sqrt(np.mean(residuals(x) ** 2)))
    return params, rms


STARTS = [
    [d, vs, r, pk, a]
    for d in (0.25, 0.5, 0.9)
    for vs in (-150.0, -60.0)
    for r in (-1.0, 0.5)
    for pk in (5.5, 6.5, 7.5)
    for a in (1.0, 2.5)
]


def head():
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def predict(out_path):
    data = [d for d in rows("B", FIT, below_mv=-5.0) if "trace_end" not in d[3]]  # Transients out.
    params, rms = fit(data, STARTS)
    predicted = {}
    for ph_c, ph_v in PANEL_A:
        predicted[f"{ph_c}/{ph_v}"] = {
            "I_mA_per_m2": [round(float(i), 6) for i in current(params, ph_c, ph_v, GRID_MV)],
            "reversal_mV": reversal(params, ph_c, ph_v),
        }
    bounds = []
    for ph_c, ph_v, relation, mv in BOUNDS:
        rev = reversal(params, ph_c, ph_v)
        lowest = float(np.min(current(params, ph_c, ph_v, GRID_MV)))
        if relation == ">":
            met = rev is not None and rev > mv
        else:  # No crossing above mv in Fig. 3's range, as its curves show.
            met = rev is None or rev < mv
        bounds.append(
            dict(pair=f"{ph_c}/{ph_v}", relation=relation, bound_mV=mv,
                 predicted_reversal_mV=rev, lowest_current_on_grid=lowest, met=met)
        )  # fmt: skip
    record = {
        "kind": "cells.fr29_desk_prediction@1",
        "written_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "revision": head(),
        "family": "docs/PROTON_RETURN_MODE_DESIGN.md §1.3 and §2.1, closed form (module docstring)",
        "fitted_on": {
            "curves": [f"{c}/{v}" for c, v in FIT],
            "range": "V < -5 mV (panel B's separable stretch), the -80 mV trace end left out",
            "rows": len(data),
            "flags_seen": sorted({f for *_, f, _ in data if f}),
        },
        "parameters": dict(zip(PARAMETERS, [float(p) for p in params], strict=True)),
        "in_sample_rms_mA_per_m2": rms,
        "grid_mV": [float(v) for v in GRID_MV],
        "panel_A": predicted,
        "bounds": bounds,
        "scoring": {
            "reversals": (
                "Primary: each panel A curve's read zero crossing "
                "(kettner2003_fig3_reversals.csv), the same reading the fit used; pass within 2 "
                "Table 2 SE of it (8.5/5.0: 10, "
                "7.5/5.0: 8, 6.0/5.0: 6 mV). Table 2's means are reported beside it"
            ),
            "shapes": (
                "Each panel A curve from -75 to +20 mV, excluding the -80 mV trace end and the "
                "channel-contaminated limb above +20 mV: the RMS of predicted less read, pass at "
                "most twice the in-sample RMS (the family's own fidelity on the curves it was "
                "fitted to); the absolute RMS is reported beside it"
            ),
            "bounds": "each as Table 2 states it; met or not",
            "seen_before": (
                "Panel A's reversals shaped the family's cytosolic factor (the note's §1.3). The "
                "README's text gave its zero crossings, where its curves meet one another, their "
                "order and values near +60 mV, the 7.5/5.0 curve's 12.2 mA m^-2 at 0 mV and the "
                "zero-gradient curves' lowest readings. The reversals file's first rows gave the "
                "6.0/5.0 curve's slope at its reversal. Its curves' other values were not read"
            ),
        },
    }
    text = json.dumps(record, indent=1) + "\n"
    Path(out_path).write_text(text)
    print(f"wrote {out_path}, sha256 {hashlib.sha256(text.encode()).hexdigest()}")
    print("parameters:", record["parameters"], "in-sample RMS", round(rms, 3))
    for key, value in predicted.items():
        print(f"  panel A {key}: reversal {value['reversal_mV']}")
    for b in bounds:
        rev, met = b["predicted_reversal_mV"], b["met"]
        print(f"  bound {b['pair']} {b['relation']} {b['bound_mV']}: {rev}, met {met}")


REVERSALS = HERE / "kettner2003_fig3_reversals.csv"
SHAPE_RANGE_MV = (-75.0, 20.0)  # The registered shape window: no trace end, no channel limb.
SE_TABLE2 = {"8.5/5.0": 5.0, "7.5/5.0": 4.0, "6.0/5.0": 3.0}


def score(prediction_path, out_path):
    """Panel A's rows read only now, and the prediction scored by the rules it carries."""
    record = json.loads(Path(prediction_path).read_text())
    grid = dict(zip(record["grid_mV"], range(len(record["grid_mV"])), strict=True))
    readings = rows("A", PANEL_A)
    read_reversals = {}
    with REVERSALS.open() as f:
        for r in csv.DictReader(f):
            if r["panel"] == "A":
                key = f"{float(r['pH_cyt'])}/{float(r['pH_vac'])}"
                read_reversals[key] = dict(
                    read=float(r["read_reversal_mV"]) if r["read_reversal_mV"] else None,
                    table2=r["table2_reversal_mV"],
                )
    curves = {}
    for ph_c, ph_v in PANEL_A:
        key = f"{ph_c}/{ph_v}"
        predicted = record["panel_A"][key]
        window, ambiguous = [], 0
        for pair, v, i, flags, identity in readings:
            if pair != (ph_c, ph_v) or not SHAPE_RANGE_MV[0] <= v <= SHAPE_RANGE_MV[1]:
                continue
            if "ambiguous" in identity or "ambiguous" in flags:
                ambiguous += 1
                continue
            window.append((v, i, predicted["I_mA_per_m2"][grid[v]]))
        residual = np.array([p - i for _, i, p in window])
        rms = float(np.sqrt(np.mean(residual**2)))
        bound_rms = 2.0 * record["in_sample_rms_mA_per_m2"]
        reversal_score = None
        read = read_reversals.get(key, {}).get("read")
        if read is not None and predicted["reversal_mV"] is not None:
            miss = predicted["reversal_mV"] - read
            reversal_score = dict(
                predicted=predicted["reversal_mV"], read=read, miss=miss,
                table2=read_reversals[key]["table2"], tolerance=2.0 * SE_TABLE2[key],
                passed=abs(miss) <= 2.0 * SE_TABLE2[key],
            )  # fmt: skip
        curves[key] = dict(
            shape=dict(rms=rms, rows=len(window), ambiguous_left_out=ambiguous,
                       threshold=bound_rms, passed=rms <= bound_rms,
                       max_abs=float(np.max(np.abs(residual))),
                       mean_signed=float(np.mean(residual))),
            reversal=reversal_score,
        )  # fmt: skip
    result = dict(
        kind="cells.fr29_desk_score@1",
        written_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        revision=head(),
        prediction=dict(path=str(prediction_path), sha256=hashlib.sha256(
            Path(prediction_path).read_bytes()).hexdigest()),
        curves=curves,
        bounds=record["bounds"],
    )  # fmt: skip
    Path(out_path).write_text(json.dumps(result, indent=1) + "\n")
    for key, c in curves.items():
        s, r = c["shape"], c["reversal"]
        rev = "no crossing" if r is None else (
            f"reversal {r['predicted']:.1f} vs read {r['read']:.1f} (Table 2 {r['table2']}): "
            f"miss {r['miss']:+.1f}, passed {r['passed']}"
        )  # fmt: skip
        print(f"{key}: shape RMS {s['rms']:.2f} (threshold {s['threshold']:.2f}, "
              f"max {s['max_abs']:.2f}, mean {s['mean_signed']:+.2f}, rows {s['rows']}, "
              f"ambiguous out {s['ambiguous_left_out']}) passed {s['passed']}; {rev}")  # fmt: skip
    for b in record["bounds"]:
        print(f"bound {b['pair']} {b['relation']} {b['bound_mV']}: met {b['met']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("predict").add_argument("out")
    scoring = sub.add_parser("score")
    scoring.add_argument("prediction")
    scoring.add_argument("out")
    args = parser.parse_args()
    if args.step == "predict":
        predict(args.out)
    elif args.step == "score":
        score(args.prediction, args.out)


if __name__ == "__main__":
    main()
