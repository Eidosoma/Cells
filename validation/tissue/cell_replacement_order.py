"""Diagnosis of the Q5 observed-order estimate (development, on the dry-run inputs only).

The full-size dry run gave orders 1.67 (W7 short-lag) and 2.95 (C9 donor short-lag)
against the registered window [1.8, 2.2]. This driver separates the replacement split
from the inner model and from the estimator: the same dry-run definition, with and
without its events (without events the wrapper is @3 bitwise), at dt 4, 2, 1, 0.5 and
0.25 ms. It reports the slot Vm differences between successive levels (max over the
records after the first event) and two estimators:

  ratio     log2(max|V(2h) - V(h)| / max|V(h) - V(h/2)|) for h = 1 and 0.5 ms
  richardson  the judge's estimator (errors against 0.5 ms at 2 and 1 ms)

Usage: python -m validation.tissue.cell_replacement_order --inputs DIR --case NAME
       --output DIR [--no-events]
"""

import argparse
import copy
import json
import math
import time
from pathlib import Path

import numpy as np

from validation.tissue import cell_replacement_judge as judge
from validation.tissue import cell_replacement_qualification as qual

DTS = (4e-3, 2e-3, 1e-3, 5e-4, 2.5e-4)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-events", action="store_true")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    predictions = json.loads((args.inputs / "predictions.json").read_text())
    raw = copy.deepcopy(predictions["cases"][args.case]["definition"])
    slots = qual.slots_of(raw)
    first = min(e["time"] for e in raw["experiment"]["replacement_events"])
    if args.no_events:
        raw["experiment"]["replacement_events"] = []
    after = np.asarray(raw["experiment"]["observation_times"]) > first
    series, walls = {}, {}
    for dt in DTS:
        started = time.perf_counter()
        _, result = judge.engine(raw, dt)
        series[dt] = np.asarray(result.observations.membrane_voltage_V)[:, slots][after]
        walls[dt] = time.perf_counter() - started
        print(dt, round(walls[dt], 1), "s", flush=True)
    steps = {
        f"{a:g}-{b:g}": float(np.max(np.abs(series[a] - series[b])))
        for a, b in zip(DTS[:-1], DTS[1:], strict=True)
    }
    ratio = {
        f"h {h:g}": math.log2(
            np.max(np.abs(series[2 * h] - series[h])) / np.max(np.abs(series[h] - series[h / 2]))
        )
        for h in (2e-3, 1e-3, 5e-4)
    }
    errors = {dt: float(np.max(np.abs(series[dt] - series[5e-4]))) for dt in (2e-3, 1e-3)}
    out = dict(
        case=args.case,
        events=not args.no_events,
        slots=slots,
        successive_differences_V=steps,
        ratio_order=ratio,
        richardson_order_judge=judge.observed_order(errors, 5e-4),
        wall_s={f"{k:g}": v for k, v in walls.items()},
        **judge.provenance(),
    )
    with open(args.output / "order.json", "x") as f:
        json.dump(out, f, indent=1)
    print(
        json.dumps(
            {
                k: out[k]
                for k in ("successive_differences_V", "ratio_order", "richardson_order_judge")
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
