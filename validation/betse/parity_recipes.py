#!/usr/bin/env python3
"""Tolerance recipe of one parity case by the pinned method (protocol_tolerances.py input).

The recipe of the P4b cases (parity-p4b-channels-20261110-01), from a preparation run
directory laid out as derive-01's run_case.sh writes it:

  RUN/emulator/CASE_difference_budget.json   emulator budget pairs (SIM chained)
  RUN/emulator/CASE_pump_law_budget.json     Ca-pump-law pairs (BETSE and CODATA constants)
  RUN/blind/CASE-D/layout, CASE-D-half/layout   blind Cells runs at (dt) and (dt/2)
  RUN/propagation/CASE_propagation_budget.json  field propagation pairs (field_MODE_LAYOUT)

Terms: betse_init_step ((10/9) |dt - dt/10| if the step-order check is clean, else
|dt - dt/100|), constants_codata_vs_betse, exterior_field_law_bound_ecm_drift_off,
conservative_compact_ecm_faces_at_dt_over_{10|100}, physical_time_gate_and_no_concentration_lag
(dt and dt/{10|100}), calcium_pump_law_cells_vs_betse, cells_numerics_ars222 (blind pair
x 4/3, second order), cells_exterior_field_propagated (max over the propagation pairs) and
cells_exterior_field_boltzmann_response (ECM; cell Ca only, as P4). No X_ext heuristic.

    python3 validation/betse/parity_recipes.py --run RUN --case CASE --order-check FILE \\
        --out RECIPE.json
"""

import argparse
import json
import sys
from pathlib import Path

FIELD_MODES = ("boltzmann", "vpatch", "both")
BLIND = ("D", "D-half")


def recipe(run, case, order_check, *, margin=3, floor=1e-12, blind=BLIND, modes=FIELD_MODES):
    run = Path(run)
    order = json.loads(Path(order_check).read_text())
    clean = order["rule_outcome"].startswith("step terms (10/9)")
    e, f, b = run / "emulator", run / "propagation", run / "blind"
    budget = str(e / f"{case}_difference_budget.json")
    at = "dt_over_10" if clean else "dt_over_100"
    step = (
        {"budget": budget, "pairs": ["betse_dt_vs_dt_over_10"], "scale": 10 / 9}
        if clean
        else {"budget": budget, "pairs": ["betse_dt_vs_dt_over_100"]}
    )
    layouts = [str(b / f"{case}-{name}/layout") for name in blind]
    return {
        "case": str(run / "betse-reference" / case),
        "margin": margin,
        "floor": floor,
        "step_order_rule": {"check": str(Path(order_check)), "outcome": order["rule_outcome"]},
        "terms": {
            "betse_init_step": step,
            "constants_codata_vs_betse": {"budget": budget, "pairs": ["betse_vs_codata_constants"]},
            "exterior_field_law_bound_ecm_drift_off": {
                "budget": budget,
                "pairs": ["ecm_drift_off"],
            },
            f"conservative_compact_ecm_faces_at_{at}": {
                "budget": budget,
                "pairs": [f"compact_ecm_faces_at_{at}"],
            },
            "physical_time_gate_and_no_concentration_lag": {
                "budget": budget,
                "pairs": ["gate_once_no_lag", f"gate_once_no_lag_at_{at}"],
            },
            "calcium_pump_law_cells_vs_betse": {
                "budget": str(e / f"{case}_pump_law_budget.json"),
                "pairs": ["pump_law_betse_constants", "pump_law_codata_constants"],
            },
            "cells_numerics_ars222": {"layouts": layouts, "scale": 4 / 3},
            "cells_exterior_field_propagated": {
                "budget": str(f / f"{case}_propagation_budget.json"),
                "pairs": [f"field_{m}_{name.replace('-', '_')}" for m in modes for name in blind],
            },
            "cells_exterior_field_boltzmann_response": {"field_layouts": layouts},
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", required=True, help="preparation run directory")
    parser.add_argument(
        "--case", required=True, help="case name (directory under RUN/betse-reference)"
    )
    parser.add_argument("--order-check", required=True, help="step_order.py check output")
    parser.add_argument("--out", required=True, help="fresh recipe JSON")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"Refusing existing output: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(recipe(args.run, args.case, args.order_check), indent=1) + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
