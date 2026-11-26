"""FR-30, Revilla, Castro and Barrio (1999): the labelled, non-blind diagnostic (D343, D344),
Deliverable 1, from the record only.

No law is evaluated and nothing is fitted. Every number below is arithmetic on the record:
- the observations, read by the tagged scorer's own `resolve` (reader erratum 1; this checkout's
  revilla1999_score.py, unchanged since the tag fr30-revilla1999-reader-erratum-1-2026-11-23);
- the windows, from the tagged scorer's own `compare_time` and `compare_steady`;
- the predicted values, copied from the judged fit's report (run-f734b96e/fit_report.json) and the
  judged verdict (verdict/verdict.json).

Its first run (24 November 2026, /mnt/workspaces/Cells/fr30-revilla-diagnostic-20261124/d1/) was
this script before it moved into the checkout; it imported the scorer from the judged score's frozen
snapshot. The inputs and their record digests are revilla1999_diagnostic.json's.

**A window** is the registered pass set of one comparison (section 13.5 point 4):
- a time passes if |ln(pred/obs)| <= ln 1.25 or |pred - obs| <= 2 SEM, so its window is
  [min(obs/1.25, obs - 2 SEM), max(1.25 obs, obs + 2 SEM)];
- G_ss/G_0 passes if |pred - obs| <= max(0.05, 2 SEM), the base 0.05 alone where no SEM is reported.

**Window units** (defined here; the record defines none): u = (pred - obs) / |edge - obs|, where
edge is the window's edge on the prediction's side (the scorer's applied edge). So |u| <= 1 is
exactly the registered pass, and the sign is the side (+ above the observation). The script checks
this against every `passes` flag in the record.

**A ± pair's floor**, for any prediction that is equal at +V and -V (one |V_j|-symmetric value):
the smallest achievable max(|u-|, |u+|) is |o- - o+| / (h- + h+), with h the two windows' half
widths facing each other. Above 1, the two windows are disjoint and no symmetric value passes both.

**The polarity chi^2 floor**, with the fitter's own sigmas (fit_revilla1999.py at f734b96e): the
sum over the ± pairs of (o- - o+)^2 / (s-^2 + s+^2), on the log scale for times. No symmetric
prediction can bring the fitter's chi^2 below it.

Run (from the checkout's or a frozen snapshot's root; standard library only):
    python -m validation.junction_gate_benchmark.revilla1999_diagnostic_record OUT.json
"""

import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from validation.junction_gate_benchmark import revilla1999_score as scorer

DECLARATION = Path(__file__).with_name("revilla1999_diagnostic.json")
INPUT_NAMES = (
    "fit_json",
    "held_out_json",
    "fit_report_json",
    "params_json",
    "predictions_json",
    "verdict_json",
    "checker_verdict_json",
)
TIMES = scorer.TIMES
STEADY = scorer.STEADY
DECAY_MAGNITUDES = (60, 80, 100)  # the six voltages: three magnitudes at both polarities
STEADY_ONLY_MAGNITUDES = (20, 40)  # training G_ss only; outside the six (side note)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance():
    """The module root, and its Git revision and dirty paths where it sits in a checkout."""
    root = Path(__file__).resolve().parents[2]

    def git(*args):
        done = subprocess.run(("git", "-C", str(root), *args), capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else None

    revision, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
    snapshot = root / "SNAPSHOT.json"
    frozen = None
    if snapshot.is_file():
        meta = json.loads(snapshot.read_text())
        frozen = {k: meta.get(k) for k in ("git_revision", "patch_sha256", "repository")}
    return {
        "root": str(root),
        "git_revision": revision.strip() if revision else None,
        "dirty_paths": status.splitlines() if status is not None else None,
        "snapshot": frozen,
    }


def load_inputs():
    """Each input from revilla1999_diagnostic.json, refused unless its bytes are the record's."""
    declared = json.loads(DECLARATION.read_text())["inputs"]
    docs, record = {}, {}
    for name in INPUT_NAMES:
        path, expected = declared[name]["path"], declared[name]["sha256"]
        digest = sha256(path)
        if digest != expected:
            raise SystemExit(f"{name}: sha256 {digest} is not the record's {expected}")
        docs[name] = json.loads(Path(path).read_text())
        record[name] = {"path": str(path), "sha256": digest}
    record["scorer"] = {"path": str(Path(scorer.__file__).resolve())}
    return docs, record


def observations(docs):
    """Every judged observation at the six voltages, and G_ss at ±20 and ±40, by the scorer's reader."""
    fit, held = docs["fit_json"], docs["held_out_json"]
    out = {}
    out.update(scorer.resolve(fit, (-100, -60, 60, 100))["entries"])
    out.update(scorer.resolve(held, (-80, 80))["entries"])
    out.update(scorer.resolve(fit, (-40, -20, 20, 40), (STEADY,))["entries"])
    return out


def window(observable, entry):
    """The registered window's edges, from the scorer's own comparison functions."""
    o, sem = entry["value"], entry["sem"]
    if observable in TIMES:
        edges = {}
        for side, probe in (("upper", o * 10.0), ("lower", o / 10.0)):
            c = scorer.compare_time(probe, o, sem)
            edges[side] = c["sem_edge"] if c["applied"] == "2 SEM" else c["ln_edge"]
            edges[side + "_applied"] = c["applied"]
        return {
            "observed": o,
            "sem": sem,
            **edges,
            "lower_note": "negative: every positive time below the observation passes"
            if edges["lower"] <= 0
            else None,
        }
    c = scorer.compare_steady(o, o, sem)
    tol = c["tolerance"]
    return {
        "observed": o,
        "sem": sem,
        "lower": o - tol,
        "upper": o + tol,
        "lower_applied": c["applied"],
        "upper_applied": c["applied"],
        "lower_note": None,
    }


def units(observable, predicted, entry):
    """The residual in window units, with the scorer's own pass flag for the self-check."""
    o, sem = entry["value"], entry["sem"]
    if observable in TIMES:
        c = scorer.compare_time(predicted, o, sem)
        edge = c["sem_edge"] if c["applied"] == "2 SEM" else c["ln_edge"]
        u = (predicted - o) / abs(edge - o)  # signed: the half width on the prediction's side
        return {
            "predicted": predicted,
            "observed": o,
            "edge": edge,
            "applied": c["applied"],
            "u": u,
            "ln_ratio": c["ln_ratio"],
            "passes": c["passes"],
        }
    c = scorer.compare_steady(predicted, o, sem)
    u = (predicted - o) / c["tolerance"]
    return {
        "predicted": predicted,
        "observed": o,
        "edge": o + math.copysign(c["tolerance"], u or 1.0),
        "applied": c["applied"],
        "u": u,
        "passes": c["passes"],
    }


def pair(observable, magnitude, obs):
    neg, pos = obs[(-magnitude, observable)], obs[(magnitude, observable)]
    wn, wp = window(observable, neg), window(observable, pos)
    lo, hi = max(wn["lower"], wp["lower"]), min(wn["upper"], wp["upper"])
    (w_hi, e_hi), (w_lo, e_lo) = sorted(((wn, "-"), (wp, "+")), key=lambda x: -x[0]["observed"])
    h_hi = w_hi["observed"] - w_hi["lower"]  # the higher one's lower half width
    h_lo = w_lo["upper"] - w_lo["observed"]  # the lower one's upper half width
    floor = (w_hi["observed"] - w_lo["observed"]) / (h_hi + h_lo)
    common = w_lo["observed"] + floor * h_lo
    return {
        "observable": observable,
        "magnitude_mV": magnitude,
        "minus": wn,
        "plus": wp,
        "disjoint": lo > hi,
        "overlap": None if lo > hi else [lo, hi],
        "gap": lo - hi if lo > hi else None,
        "higher_polarity": e_hi,
        "symmetric_floor_u": floor,
        "symmetric_floor_at": common,
    }


def chi2_floor(docs, obs):
    """The polarity chi^2 floor with the fitter's sigmas, and the selected fit's chi^2 split into
    the floor and its own excess, from the fit report's training rows."""
    steady_sems = [
        e["sem"]
        for (v, o), e in obs.items()
        if o == STEADY and abs(v) in (20, 40, 60, 100) and e["sem"] is not None
    ]
    sem_floor = statistics.median(steady_sems)
    report = docs["fit_report_json"]
    if not math.isclose(sem_floor, report["objective"]["steady_sem_floor"], rel_tol=1e-12):
        raise SystemExit("the G_ss SEM floor does not match the fit report's")
    rows = {(r["vj_mV"], r["observable"]): r for r in report["training_residuals"]}
    pairs, total, excess_total = [], 0.0, 0.0
    for observable, magnitudes in (
        (STEADY, (20, 40, 60, 100)),
        ("tau_fast", (60, 100)),
        ("tau_slow", (60, 100)),
    ):
        for m in magnitudes:
            en, ep = obs[(-m, observable)], obs[(m, observable)]
            if observable in TIMES:
                xn, xp = math.log(en["value"]), math.log(ep["value"])
                sn, sp = en["sem"] / en["value"], ep["sem"] / ep["value"]
            else:
                xn, xp = en["value"], ep["value"]
                sn = en["sem"] if en["sem"] is not None else sem_floor
                sp = ep["sem"] if ep["sem"] is not None else sem_floor
            floor = (xn - xp) ** 2 / (sn**2 + sp**2)
            weight = 1 / sn**2 + 1 / sp**2
            mean = (xn / sn**2 + xp / sp**2) / weight
            pn, pp = rows[(-m, observable)]["predicted"], rows[(m, observable)]["predicted"]
            if pn != pp:
                raise SystemExit("the selected fit's ± predictions differ")
            p = math.log(pn) if observable in TIMES else pn
            excess = (p - mean) ** 2 * weight
            fit_chi2 = (
                rows[(-m, observable)]["weighted_residual"] ** 2
                + rows[(m, observable)]["weighted_residual"] ** 2
            )
            if not math.isclose(fit_chi2, floor + excess, rel_tol=1e-9):
                raise SystemExit("the pair's chi^2 does not split into floor + excess")
            total += floor
            excess_total += excess
            pairs.append(
                {
                    "observable": observable,
                    "magnitude_mV": m,
                    "sigma_minus": sn,
                    "sigma_plus": sp,
                    "scale": "ln" if observable in TIMES else "linear",
                    "floor_chi2": floor,
                    "symmetric_optimum": math.exp(mean) if observable in TIMES else mean,
                    "selected_fit_predicted": pn,
                    "selected_fit_chi2": fit_chi2,
                    "selected_fit_excess_chi2": excess,
                }
            )
    ratio = rows[(-100, "A_fast/A_slow")]["weighted_residual"] ** 2
    selected = report["selected"]["chi2"]
    free = report["best_per_mode"]["free"]["chi2"]
    recomputed = sum(r["weighted_residual"] ** 2 for r in report["training_residuals"])
    if not math.isclose(recomputed, selected, rel_tol=1e-12):
        raise SystemExit("the selected chi^2 does not recompute from its rows")
    if not math.isclose(total + excess_total + ratio, selected, rel_tol=1e-9):
        raise SystemExit("the selected chi^2 is not floor + excess + ratio")
    return {
        "sigmas": "the fitter's: times ln-scale SEM/obs; G_ss its SEM, or the median reported G_ss SEM where none",
        "steady_sem_floor": sem_floor,
        "pairs": pairs,
        "floor_chi2_total": total,
        "singleton_ratio_chi2_selected": ratio,
        "selected_mode_chi2": selected,
        "selected_excess_over_floor": selected - total,
        "free_mode_chi2": free,
        "free_minus_floor": free - total,
    }


def main(out):
    began = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    docs, inputs = load_inputs()
    obs = observations(docs)

    # 1. The windows at all six voltages, and the ± pairs (G_ss at ±20, ±40 as a side note).
    pairs = [pair(o, m, obs) for o in TIMES + (STEADY,) for m in DECAY_MAGNITUDES]
    side = [pair(STEADY, m, obs) for m in STEADY_ONLY_MAGNITUDES]

    # 2. The registered fit's in-sample residuals, in window units (all its training rows).
    report = docs["fit_report_json"]
    checks, signs = [], []
    in_sample = []
    for r in report["training_residuals"]:
        key = (r["vj_mV"], r["observable"])
        if key not in obs:
            in_sample.append(
                {
                    "vj_mV": r["vj_mV"],
                    "observable": r["observable"],
                    "predicted": r["predicted"],
                    "observed": r["value"],
                    "u": None,
                    "note": "no registered window (amplitude ratio; section 13.2)",
                }
            )
            continue
        u = units(r["observable"], r["predicted"], obs[key])
        flag = r["section_13_5_comparison"]["passes"]
        checks.append((abs(u["u"]) <= 1) == u["passes"] == flag)
        signs.append(
            math.copysign(1.0, u["u"]) == math.copysign(1.0, u["predicted"] - u["observed"])
        )
        in_sample.append(
            {"vj_mV": r["vj_mV"], "observable": r["observable"], **u, "fit_report_passes": flag}
        )

    # 3. D320's six judged lines, in window units.
    judged = []
    for c in docs["verdict_json"]["comparisons"]:
        key = (c["vj_mV"], c["observable"])
        u = units(c["observable"], c["predicted"], obs[key])
        checks.append((abs(u["u"]) <= 1) == u["passes"] == c["passes"])
        signs.append(
            math.copysign(1.0, u["u"]) == math.copysign(1.0, u["predicted"] - u["observed"])
        )
        judged.append(
            {"vj_mV": c["vj_mV"], "observable": c["observable"], **u, "verdict_passes": c["passes"]}
        )
    pred = docs["predictions_json"]["predictions"]
    for e in pred:  # the judged values are predictions.json's own
        for o in TIMES + (STEADY,):
            row = next(j for j in judged if j["vj_mV"] == e["vj_mV"] and j["observable"] == o)
            if row["predicted"] != e[scorer.PREDICTED_KEY[o]]:
                raise SystemExit("verdict.json's prediction is not predictions.json's")

    # 4. Free parameters against the observables.
    floor = chi2_floor(docs, obs)
    modes = report["search"]["modes"]
    distinct = {
        "G_ss/G_0 at |V| = 20, 40, 60, 100 mV": 4,
        "tau_fast at 60, 100 mV": 2,
        "tau_slow at 60, 100 mV": 2,
        "A_fast/A_slow at -100 mV (no +100 counterpart)": 1,
    }
    count = {
        "law": "cells.junction.junction_series_gates@1, two boltzmann_eyring gates (kinds.json): (rate, slope, midpoint, split, residual) per gate",
        "free_parameters": modes,
        "selected_mode": report["selected"]["mode"],
        "training_residuals": report["objective"]["observations"],
        "distinct_symmetric_targets": distinct,
        "distinct_symmetric_target_count": sum(distinct.values()),
        "fit_report_diagnostics": {
            "coordinates": report["coordinates"],
            "jacobian_singular_values": report["jacobian_singular_values"],
            "jacobian_condition": report["jacobian_condition"],
            "jacobian_weak_direction": report["jacobian_weak_direction"],
        },
        "chi2_floor": floor,
    }

    if not all(checks):
        raise SystemExit("window units disagree with a recorded pass flag")
    if not all(signs):
        raise SystemExit("a window unit's sign is not the sign of pred - obs")
    doc = {
        "kind": "fr30-revilla1999-diagnostic-d1@1",
        "label": "labelled, non-blind diagnostic (D343, D344); decides nothing (W6); no verdict or law changes; one study's indication",
        "began_utc": began,
        "inputs": inputs,
        "script": {"path": str(Path(__file__).resolve())},
        "provenance": provenance(),
        "python": platform.python_version(),
        "definitions": {
            "window": "section 13.5 point 4: times [min(o/1.25, o-2SEM), max(1.25o, o+2SEM)]; G_ss o ± max(0.05, 2SEM), 0.05 alone without an SEM",
            "window_units": "u = (pred - obs)/|edge - obs|, edge the window's edge on the prediction's side; |u| <= 1 is the registered pass; + is above the observation",
            "symmetric_floor_u": "the least max(|u-|, |u+|) any prediction equal at -V and +V can reach: |o- - o+|/(h- + h+), h the facing half widths",
        },
        "windows_and_pairs": pairs,
        "side_note_steady_only_pairs": side,
        "amplitudes": "A_fast and A_slow are not reported per voltage (fit.json, section 13.2): no window exists at any voltage. The only amplitude datum is the fast:slow ratio 3 at -100 mV, with no dispersion, no registered tolerance and no +100 mV counterpart.",
        "in_sample_residuals": in_sample,
        "judged_lines": judged,
        "parameters_against_observables": count,
        "self_check": {
            "window_units_match_every_recorded_pass_flag": all(checks),
            "flags_checked": len(checks),
            "every_sign_is_pred_minus_obs": all(signs),
            "signs_checked": len(signs),
        },
    }
    Path(out).write_text(json.dumps(doc, indent=1) + "\n")

    # A compact table on stdout.
    print("1. windows and ± pairs (six voltages; G_ss ±20, ±40 as a side note)")
    for p in pairs + side:
        n, q = p["minus"], p["plus"]
        tail = (
            f"DISJOINT, gap {p['gap']:.4f}"
            if p["disjoint"]
            else f"overlap [{p['overlap'][0]:.4f}, {p['overlap'][1]:.4f}]"
        )
        print(
            f"  {p['observable']:9s} ±{p['magnitude_mV']:3d}: -V {n['observed']:.4f} [{n['lower']:.4f}, {n['upper']:.4f}]"
            f"  +V {q['observed']:.4f} [{q['lower']:.4f}, {q['upper']:.4f}]  {tail}; floor u {p['symmetric_floor_u']:.3f} at {p['symmetric_floor_at']:.4f}"
        )
    print("2. in-sample residuals (window units)")
    for r in in_sample:
        u = "  n/a" if r["u"] is None else f"{r['u']:+.3f}"
        print(
            f"  {r['vj_mV']:+5d} {r['observable']:13s} pred {r['predicted']:.4f} obs {r['observed']:.4f} u {u}"
        )
    print("3. D320's judged lines (window units)")
    for r in judged:
        print(
            f"  {r['vj_mV']:+5d} {r['observable']:9s} pred {r['predicted']:.4f} obs {r['observed']:.4f} u {r['u']:+.3f} {'pass' if r['passes'] else 'MISS'}"
        )
    print("4. chi^2 floor by pair")
    for r in floor["pairs"]:
        print(
            f"  {r['observable']:9s} ±{r['magnitude_mV']:3d}: floor {r['floor_chi2']:.4f}  fit excess {r['selected_fit_excess_chi2']:.4f}"
            f"  optimum {r['symmetric_optimum']:.4f} fit {r['selected_fit_predicted']:.4f}"
        )
    print(
        f"  floor total {floor['floor_chi2_total']:.6f}; free mode chi2 {floor['free_mode_chi2']:.6f} (minus floor {floor['free_minus_floor']:+.2e});"
        f" selected chi2 {floor['selected_mode_chi2']:.6f} (excess {floor['selected_excess_over_floor']:.4f}, of which ratio {floor['singleton_ratio_chi2_selected']:.4f})"
    )
    print(
        f"self-check: {len(checks)} pass flags agree with |u| <= 1; {len(signs)} signs equal sign(pred - obs)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
