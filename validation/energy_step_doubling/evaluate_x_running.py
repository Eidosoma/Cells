"""FR-18 criterion X, amendment 2's test (docs/FR18_CRITERION_X_2026-11-18.md, registered at
690f986d): X2's order condition and held-step cap re-evaluated in their running form at every row,
on the registered run's saved records, beside the registered (whole-run) verdicts. No simulation.

The registered evaluator, evaluate_x.py, is imported unchanged: its variant() gives each world's
registered outputs (the per-row check, the held steps and the whole-run conditions). This tool adds,
per world, the first row (if any) at which the running order condition or the running cap fails,
and derives X2's decisions in both forms:
- the full set: (a) the refused arms admitted, (b) no honest world failing, (c) the registered plant
  caught at its row (the per-row check, the same in both forms);
- FR-8's worlds (amendment 1): every world admitted.

Usage: python evaluate_x_running.py FULL_OUT_DIR FR8_OUT_DIR RESULTS_JSON
"""

import bisect
import glob
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_x as reg  # noqa: E402  The registered evaluator, unchanged.


def running_conditions(d, meta):
    """(first order failure, first cap failure): each (row, value, count) at the first row k where
    the running condition over the steps j <= k fails, else None (the registered definitions)."""
    eps = meta["eps"]
    F, T, O = d["F"], d["T"], d["O"]
    full, half = d["d_full"], d["d_half"]
    M = F + T + O
    held1 = ~np.isfinite(half)
    counted = ~held1 & (np.abs(np.where(held1, 0.0, half)) > reg.COUNT_FACTOR * eps * M)
    q = np.where(counted, full / np.where(counted, half, 1.0), np.nan)
    in_band = counted & (q >= reg.BAND[0]) & (q <= reg.BAND[1])
    out_band = counted & ~in_band
    order = cap = None
    values, out = [], 0
    for k in np.flatnonzero(counted):  # Both conditions change only at counted steps.
        bisect.insort(values, float(q[k]))
        out += int(out_band[k])
        m = len(values)
        median = values[m // 2] if m % 2 else 0.5 * (values[m // 2 - 1] + values[m // 2])
        if order is None and not (reg.BAND[0] <= median <= reg.BAND[1]):
            order = dict(row=int(k) + 1, median=median, counted=m)
        limit = max(8, math.ceil(0.02 * m))
        if cap is None and out > limit:
            cap = dict(row=int(k) + 1, held_out_of_band=out, cap=limit, counted=m)
    # The whole-run median, as np.median gives it, for the cross-check with the registered output.
    whole = float(np.median(q[counted])) if counted.any() else None
    return order, cap, whole


def evaluate(out_dir):
    worlds = {}
    for path in sorted(glob.glob(out_dir + "/*.json")):
        name = path.split("/")[-1][:-5]
        meta = json.load(open(path))
        if not isinstance(meta, dict) or "kind" not in meta or meta.get("excluded") or meta.get("error"):
            continue
        d = np.load(path[:-5] + ".npz")
        registered = reg.variant(d, meta, "X2")
        order, cap, whole = running_conditions(d, meta)
        assert (whole is None) == (registered["median_step_ratio"] is None)
        assert whole is None or abs(whole - registered["median_step_ratio"]) <= 1e-12 * abs(whole)
        running_ok = bool(
            registered["check_ok"] and registered["held_ok"] and order is None and cap is None
        )
        worlds[name] = dict(
            registered_ok=registered["world_ok"],
            running_ok=running_ok,
            order_first_failure=order,
            cap_first_failure=cap,
            registered=dict((k, registered[k]) for k in (
                "check_ok", "held_ok", "order_ok", "cap_ok", "median_step_ratio", "counted_steps",
                "held_out_of_band", "cap")),
            registered_plant=registered.get("registered_plant"),
        )
    return worlds


def decisions(worlds, form, fr8):
    key = "registered_ok" if form == "registered" else "running_ok"
    if fr8:
        return dict(all_admitted=all(w[key] for w in worlds.values()),
                    failing=sorted(n for n, w in worlds.items() if not w[key]))
    arms = {n: worlds.get(n) for n in reg.REFUSED_ARMS}
    plant = (worlds.get(reg.PLANT_WORLD) or {}).get("registered_plant")
    failing = sorted(n for n, w in worlds.items() if n not in reg.REFUSED_ARMS and not w[key])
    return dict(
        a_refused_arms_admitted=all(w is not None and w[key] for w in arms.values()),
        b_honest_admitted=not failing,
        b_failing=failing,
        c_registered_plant_caught=bool(plant and plant["caught"]),
    )


def main(argv):
    full_dir, fr8_dir, results_path = argv[1], argv[2], argv[3]
    out = {}
    for label, out_dir, fr8 in (("full", full_dir, False), ("fr8", fr8_dir, True)):
        worlds = evaluate(out_dir)
        out[label] = dict(
            worlds=len(worlds),
            registered=decisions(worlds, "registered", fr8),
            running=decisions(worlds, "running", fr8),
            differing_worlds=sorted(n for n, w in worlds.items() if w["registered_ok"] != w["running_ok"]),
            running_failures=sorted(
                (n, w["order_first_failure"], w["cap_first_failure"]) for n, w in worlds.items()
                if w["order_first_failure"] or w["cap_first_failure"]
            ),
            worlds_detail=worlds,
        )
    same = all(out[k]["registered"] == out[k]["running"] for k in out) and not any(
        out[k]["differing_worlds"] for k in out
    )
    out["verdicts_identical"] = same
    json.dump(out, open(results_path, "w"), indent=1, default=float)
    for k in ("full", "fr8"):
        print(k, "worlds", out[k]["worlds"])
        print("  registered:", json.dumps(out[k]["registered"]))
        print("  running:   ", json.dumps(out[k]["running"]))
        print("  differing worlds:", out[k]["differing_worlds"])
        for f in out[k]["running_failures"]:
            print("  running failure:", json.dumps(f, default=float))
    print("verdicts identical:", same)


if __name__ == "__main__":
    main(sys.argv)
