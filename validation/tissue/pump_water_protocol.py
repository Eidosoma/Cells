"""Pin the judged tolerances of the resolved_pump_water@1 qualification (W1e).

Order (docs/PUMP_WATER_MODEL.md): the predictions are frozen first, then the engine
dt study runs, then this script pins each tolerance, and only then is the judge run.
For every trajectory world and quantity:

    tolerance = 3 x (engine step-error term at 1 ms + reference stability term)

- The step-error term is the dt study's |x(1 ms) - x(0.5 ms)| x 4/3, taken at its
  maximum over the predicted times.
- The reference stability term is |ref(rtol 1e-11) - ref(rtol 1e-12)|, maximum over
  the same times; this script recomputes the reference at 1e-12.

Like the parity method, the factor 3 covers terms measured once. The order check
(observed order >= 1.8 for ARS on the 4-2-1-0.5 ms sequence) is recorded with
the tolerances. The stationary states are judged to 1e-6 relative in volume and
1e-6 V in Vm: the reference solves them to about 1e-12 and the engine Newton to
1e-10 in its units, so this is a modelling-equivalence bound, not a rounding bound.

Usage: python -m validation.tissue.pump_water_protocol --predictions FILE --dt-study FILE
       --output FILE
"""

import argparse
import json
from pathlib import Path

import numpy as np

from validation.tissue import pump_water_qualification as qualification
from validation.tissue import pump_water_reference as ref


def reference_stability(predictions, name, path):
    entry = qualification.item(predictions, path)
    raw = entry["definition"]
    if name == "P1":
        return {"cell_volume_pL": 0.0}  # Exact solution (brentq to rounding).
    times = sorted(float(t) for t in entry["observations"])
    r = ref.Reference(raw)
    method = "DOP853" if name == "P5" else "Radau"
    tight = r.integrate(max(times), times, method=method, rtol=1e-12)
    out = {}
    for t in times:
        a = qualification.reference_arrays(entry["observations"][f"{t:.6f}"])
        b = qualification.reference_arrays(r.observe(tight[t]))
        for key in a:
            if a[key].size:
                out[key] = max(out.get(key, 0.0), float(np.max(np.abs(a[key] - b[key]))))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--dt-study", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    predictions = json.loads(Path(args.predictions).read_text())
    study = json.loads(Path(args.dt_study).read_text())
    tolerances, terms, orders = {}, {}, {}
    for name, path in qualification.TRAJECTORIES.items():
        if name not in study:
            continue
        stability = reference_stability(predictions, name, path)
        tolerances[name], terms[name] = {}, {}
        for key, values in study[name]["step_error_term_1ms"].items():
            if name == "P1" and key != "cell_volume_pL":
                continue
            if key not in stability and name != "P1":
                continue
            step = float(np.max(values))
            reference = stability.get(key, 0.0)
            tolerances[name][key] = 3 * (step + reference)
            terms[name][key] = dict(step_error_1ms=step, reference_stability=reference)
        orders[name] = study[name]["observed_orders"]
    protocol = dict(
        kind="cells.pump_water_qualification_protocol@1",
        predictions=args.predictions,
        dt_study=args.dt_study,
        rule="tolerance = 3 x (step-error term at 1 ms + reference stability), max over times",
        tolerances=tolerances,
        terms=terms,
        observed_orders=orders,
        order_requirement=(
            "ARS(2,2,2): observed order >= 1.8 on 4-2-1-0.5 ms where errors exceed rounding"
        ),
        stationary=dict(
            volume_relative=1e-6,
            voltage_V=1e-6,
            identity_relative=1e-9,
            step_map_correction=1e-8,
        ),
    )
    Path(args.output).write_text(json.dumps(protocol, indent=2) + "\n")


if __name__ == "__main__":
    main()
