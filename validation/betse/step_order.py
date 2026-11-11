#!/usr/bin/env python3
"""Observed step order of the BETSE-order emulator and the parity step-term rule (read-only).

From one case's emulator runs at BETSE's dt, dt/10 and dt/100 (same constants, model
differences and SIM start): d1 = |x(dt) - x(dt/10)| and d2 = |x(dt/10) - x(dt/100)|, the
default_world_adapter difference rows (max over common samples and the phase end, interior
ECM), and the observed order p solving d1 / d2 = (1 - 0.1^p) / (0.1^p - 0.01^p) (p = 1 gives
10). The rule (lead, 10 November 2026; parity P3/P4b): a case's BETSE step terms are
(10/9) |x(dt) - x(dt/10)| when every checked quantity has an observed order within the band
(default 0.9-1.1); otherwise |x(dt) - x(dt/100)| for the step terms, and the dt/100 values of
the model-difference terms measured at dt/10. Checked: Vm and every cell ion but immobile P,
in INIT and SIM; ECM ions are reported. An undetermined order counts as outside the band.

    python3 validation/betse/step_order.py check --case CASE [--runner network] \\
        --dt1 LAYOUT --dt10 LAYOUT --dt100 LAYOUT --out OUT.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

from validation.betse import protocol_tolerances as pt  # noqa: E402

BAND = (0.9, 1.1)
CLEAN = "step terms (10/9)|dt1 - dt10|"
FALLBACK = "dt1-dt100 step terms; model-difference terms at dt/100"


def order(d1, d2, *, ratio=10.0):
    """p with d1 / d2 = (1 - r^-p) / (r^-p - r^-2p), by bisection on [0.05, 6]; None if none."""
    if not (d1 > 0 and d2 > 0):
        return None
    target, h = d1 / d2, 1 / ratio

    def f(p):
        return (1 - h**p) / (h**p - h ** (2 * p)) - target

    lo, hi = 0.05, 6.0
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if f(lo) * f(mid) <= 0 else (mid, hi)
    return 0.5 * (lo + hi)


def evaluate(d1, d2, d12, *, band=BAND):
    """The rule from three rows_terms sets {phase: {quantity: ...}} (dt-dt/10, dt/10-dt/100,
    dt-dt/100)."""

    def entry(get, checked):
        a, b, c = get(d1), get(d2), get(d12)
        p = order(a, b)
        return {
            "dt1_vs_dt10": a,
            "dt10_vs_dt100": b,
            "dt1_vs_dt100": c,
            "ratio": a / b if b else None,
            "observed_order": p,
            "step_term_10_over_9_dt1_dt10": 10 / 9 * a,
            "checked": checked,
            "within_band": None if p is None else bool(band[0] <= p <= band[1]),
        }

    result = {"kind": "cells.parity_step_order_check@1", "band": list(band), "phases": {}}
    outside = []
    for p in pt.PHASES:
        ions = [i for i in d1[p]["cell_concentration"] if i != "P"]
        phase = {
            "voltage": entry(lambda x, p=p: x[p]["voltage"], True),
            "cell_concentration": {
                i: entry(lambda x, p=p, i=i: x[p]["cell_concentration"][i], True) for i in ions
            },
            "ecm_concentration": {
                i: entry(lambda x, p=p, i=i: x[p]["ecm_concentration"][i], False) for i in ions
            },
        }
        result["phases"][p] = phase
        checked = [(f"{p}/voltage", phase["voltage"])] + [
            (f"{p}/cell_concentration/{i}", v) for i, v in phase["cell_concentration"].items()
        ]
        outside += [k for k, v in checked if not v["within_band"]]
    result["outside_band_or_undetermined"] = outside
    result["rule_outcome"] = CLEAN if not outside else FALLBACK
    return result


def check(world, dt1, dt10, dt100, *, band=BAND):
    from validation.betse import default_world_adapter as adapter

    def rows(a, b):
        phases = adapter.layout_difference(world, a, b)["phases"]
        return {p: pt.rows_terms(phases[p]["observables"]) for p in pt.PHASES}

    result = evaluate(rows(dt1, dt10), rows(dt10, dt100), rows(dt1, dt100), band=band)
    result["layouts"] = {"dt1": str(dt1), "dt10": str(dt10), "dt100": str(dt100)}
    return result


def main(argv=None):
    from validation.betse import field_propagation as fp

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("check", help="observed order and the rule for one case")
    run.add_argument("--case", required=True, help="BETSE case (inputs only)")
    run.add_argument("--runner", choices=sorted(fp.RUNNERS), default="network")
    for name in ("dt1", "dt10", "dt100"):
        run.add_argument(f"--{name}", required=True, help=f"emulator layout at {name}")
    run.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    world = fp.runner(args.runner).world(args.case, blind=True)
    result = check(world, Path(args.dt1), Path(args.dt10), Path(args.dt100))
    result["case"] = str(Path(args.case).resolve())
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({k: result[k] for k in ("outside_band_or_undetermined", "rule_outcome")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
