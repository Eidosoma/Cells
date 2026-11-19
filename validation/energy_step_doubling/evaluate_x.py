"""FR-18 criterion X's registered run: the evaluator (docs/FR18_CRITERION_X_2026-11-18.md).

Reads recorder_x.py's records (OUT_DIR/NAME.npz and NAME.json) and applies the registration as
written, for both variants (X1: kappa = 1/4; X2: kappa = 1/16 with out-of-band steps held, capped),
then decides (a), (b) and (c) per variant. P1 and P2 are reported, not decided, beside today's
check and the probe's E2 (c = 2).

Usage: python evaluate_x.py OUT_DIR RESULTS_JSON
"""

import glob
import json
import math
import sys

import numpy as np

ROUNDING = 2.5  # LEDGER_STEP_ROUNDING (models/surface_pump.py), the other running ledgers' rule.
COUNT_FACTOR = 1000.0  # A counted step: |d''_k| > 1000 eps M_k.
BAND = (3.5, 4.6)  # The order condition's band, and X2's out-of-band test.
VARIANTS = {"X1": dict(kappa=0.25, hold_out_of_band=False), "X2": dict(kappa=1 / 16, hold_out_of_band=True)}
REFUSED_ARMS = ("fr18-fig5net100-16", "fr18-fig5net100-32", "fr18-fig3g50-16")
PLANT_WORLD = "fr3plant-q1_eps_1e-1"
PLANTS = ("P1", "P2heat", "P2work")


def first(mask):
    hits = np.flatnonzero(mask)
    return int(hits[0]) if hits.size else None


def variant(d, meta, name):
    eps, atol, rtol = meta["eps"], meta["atol_pJ"], meta["rtol"]
    kappa, hold_out = VARIANTS[name]["kappa"], VARIANTS[name]["hold_out_of_band"]
    R, F, T, O = d["R"], d["F"], d["T"], d["O"]
    full, half = d["d_full"], d["d_half"]
    n = R.size
    k = np.arange(1, n + 1, dtype=float)
    M = F + T + O
    held1 = ~np.isfinite(half)
    counted = ~held1 & (np.abs(np.where(held1, 0.0, half)) > COUNT_FACTOR * eps * M)
    q = np.where(counted, full / np.where(counted, half, 1.0), np.nan)
    in_band = counted & (q >= BAND[0]) & (q <= BAND[1])
    out_band = counted & ~in_band
    median = float(np.median(q[counted])) if counted.any() else None
    order_ok = True if median is None else BAND[0] <= median <= BAND[1]
    cap = max(8, math.ceil(0.02 * int(counted.sum())))
    hold = held1 | (out_band if hold_out else np.zeros(n, dtype=bool))
    cap_ok = (not hold_out) or int(out_band.sum()) <= cap
    a = np.where(hold, 0.0, 4.0 / 3.0 * (full - np.where(held1, 0.0, half)))
    S = np.cumsum(np.abs(a))
    C = R - np.cumsum(a) - np.cumsum(np.where(hold, full, 0.0))
    floor = ROUNDING * eps * k * M
    ratio = np.abs(C) / (floor + kappa * S)
    worst = int(np.argmax(ratio))
    held_idx = np.flatnonzero(hold)
    held_ratio = (
        float(np.max(np.abs(full[held_idx]) / (atol + rtol * F[held_idx]))) if held_idx.size else None
    )
    out = dict(
        kappa=kappa,
        largest_ratio=float(ratio[worst]),
        largest_ratio_row=worst + 1,
        check_ok=bool(ratio[worst] <= 1.0),
        held_steps=int(held_idx.size),
        held_out_of_band=int(out_band.sum()) if hold_out else 0,
        cap=cap if hold_out else None,
        cap_ok=bool(cap_ok),
        held_largest_ratio_to_today=held_ratio,
        held_ok=held_ratio is None or held_ratio <= 1.0,
        counted_steps=int(counted.sum()),
        median_step_ratio=median,
        out_of_band_counted=int(out_band.sum()),
        order_ok=bool(order_ok),
        integration_error_max=float(np.max(S / np.maximum(F, 1e-300))),
        integration_error_end=float(S[-1] / max(F[-1], 1e-300)),
    )
    out["world_ok"] = bool(out["check_ok"] and out["held_ok"] and out["order_ok"] and out["cap_ok"])
    plants = {}
    eps2 = np.where(held1, 0.0, 4.0 / 3.0 * np.abs(full - np.where(held1, 0.0, half)))
    sum_eps2 = np.cumsum(eps2)
    for key in PLANTS:
        if f"delta_{key}" not in d.files:
            continue
        delta, fp = d[f"delta_{key}"], d[f"F_{key}"]
        if not np.any(delta):
            plants[key] = "no such flow"
            continue
        mp = fp + T + O
        plants[key] = dict(
            today=first(np.abs(R + delta) > atol + rtol * fp),
            E2=first(np.abs(R + delta) > atol + 16 * eps * fp + 2 * sum_eps2),
            X=first(np.abs(C + delta) > ROUNDING * eps * k * mp + kappa * S),
        )
    out["plants"] = plants
    reg = meta.get("registered") or {}
    if reg:
        j = int(reg["step"])
        mp = reg["F"] + T[j] + O[j]
        allowance = ROUNDING * eps * (j + 1) * mp + kappa * S[j]
        out["registered_plant"] = dict(
            row=j + 1,
            ratio=float(abs(C[j] + reg["delta"]) / allowance),
            caught=bool(abs(C[j] + reg["delta"]) > allowance),
            caught_today=bool(abs(R[j] + reg["delta"]) > atol + rtol * reg["F"]),
            caught_E2=bool(abs(R[j] + reg["delta"]) > atol + 16 * eps * reg["F"] + 2 * sum_eps2[j]),
        )
    return out


def main(argv):
    out_dir, results_path = argv[1], argv[2]
    worlds = {}
    for path in sorted(glob.glob(out_dir + "/*.json")):
        name = path.split("/")[-1][:-5]
        meta = json.load(open(path))
        if not isinstance(meta, dict) or "kind" not in meta:
            continue
        row = dict(label=meta.get("label"), model=meta.get("model"), steps=meta.get("steps"),
                   planned_steps=meta.get("planned_steps"), refusal=meta.get("refusal"),
                   events=len(meta.get("events") or []), seconds=meta.get("seconds"))
        if meta.get("excluded"):
            row["excluded"] = meta["excluded"]
        elif meta.get("error"):
            row["error"] = meta["error"]
        else:
            d = np.load(path[:-5] + ".npz")
            for v in VARIANTS:
                row[v] = variant(d, meta, v)
        worlds[name] = row
    decisions = {}
    evaluated = {n: w for n, w in worlds.items() if "X1" in w}
    for v in VARIANTS:
        arms = {n: evaluated.get(n) for n in REFUSED_ARMS}
        a = all(w is not None and w[v]["world_ok"] for w in arms.values())
        failing = [
            dict(world=n, ratio=w[v]["largest_ratio"], row=w[v]["largest_ratio_row"],
                 held_ok=w[v]["held_ok"], order_ok=w[v]["order_ok"], cap_ok=w[v]["cap_ok"])
            for n, w in evaluated.items() if n not in REFUSED_ARMS and not w[v]["world_ok"]
        ]
        plant = (evaluated.get(PLANT_WORLD) or {}).get(v, {}).get("registered_plant")
        decisions[v] = dict(
            a_refused_arms_admitted=a,
            a_arms={n: None if w is None else w[v]["largest_ratio"] for n, w in arms.items()},
            b_honest_admitted=not failing,
            b_failing=failing,
            c_registered_plant_caught=bool(plant and plant["caught"]),
            c_plant=plant,
            works=bool(a and not failing and plant and plant["caught"]),
        )
    summary = dict(
        worlds=len(worlds),
        evaluated=len(evaluated),
        excluded=sorted(n for n, w in worlds.items() if "excluded" in w),
        errors={n: w["error"][:200] for n, w in worlds.items() if "error" in w},
        refused_by_step=sorted(n for n, w in worlds.items() if w.get("refusal")),
        decisions=decisions,
        worlds_detail=worlds,
    )
    json.dump(summary, open(results_path, "w"), indent=1, default=float)
    print(json.dumps({k: summary[k] for k in ("worlds", "evaluated", "excluded", "errors", "refused_by_step")}, indent=1, default=float))
    for v, dec in decisions.items():
        print(v, json.dumps({k: dec[k] for k in ("works", "a_refused_arms_admitted", "a_arms", "b_honest_admitted", "c_registered_plant_caught")}, default=float))
        for f in dec["b_failing"][:10]:
            print("   failing:", f)


if __name__ == "__main__":
    main(sys.argv)
