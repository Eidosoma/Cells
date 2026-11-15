"""FR-4's reference evidence on §13.1's world (900 s), for the usage note and the lead.

    python -m validation.compartment_ph.ph_crosschecks --out DIR

Writes DIR/crosschecks.json and DIR/log.txt, with records log-spaced from 1 us and every 10 s:
1. buffered acidification against a gradient, K+ counterion and maintained fuel, by full kinetics
   (R-kinetic at k_on = 1e7 mM^-1 s^-1) and by the closure: lumen pH, V_b, the pump's cycles, the
   K+ moved, the energy identity, the cytosol's pH band (transformed_at(7.2, delta 0.05));
2. convergence to the closure as k_on grows (1e3, 1e5, 1e7): the largest |pH_kinetic - pH_closure|
   over the run, per node;
3. the outside case (the lumen's k_on = 1e-3 mM^-1 s^-1, 1 M^-1 s^-1): beyond the 1e-3 pH budget,
   with the closure run's envelope ratio lambda/rho at that k_on;
4. the negative control (P_K = 0): the stall, against the 1e-3 pH budget;
plus the floor (rtol 1e-11 against 1e-12) of both references. About a minute on one core.
"""

import argparse
import json
import platform
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import scipy

from validation.compartment_ph import ph_reference as ph

T = 900.0
BUDGET = 1e-3
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


def records():
    return tuple(sorted({*np.geomspace(1e-6, T, 120), *np.arange(10.0, T + 1e-9, 10.0)}))


def summary(run, rec):
    last = run.at[rec[-1]]
    return dict(
        pH_L_final=last["pH_L"], pH_c_final=last["pH_c"], Vb_final=last["Vb"],
        Vb_extreme=max((run.at[t]["Vb"] for t in rec), key=abs), cycles=last["cycles"],
        K_moved_into_cytosol=last["ions_c"].get("K", 0.0) - run.model.ions0[0]["K"],
        work_pJ=last["work_pJ"], heat_pJ=last["heat_pJ"],
        energy_residual_max_pJ=max(abs(run.at[t]["energy_residual_pJ"]) for t in rec),
        cytosol_band_max=max(abs(run.at[t]["pH_c"] - 7.2) for t in rec),
        envelope_ratio_min=min(min(run.at[t]["envelope_ratio"]) for t in rec),
        steps=run.steps)


def max_dpH(a, b, rec, key):
    vals = [(abs(a.at[t][key] - b.at[t][key]), t) for t in rec]
    v, t = max(vals)
    return dict(max=v, at_s=t)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    rec = records()
    w = ph.acceptance_world()
    result = dict(kind="cells.compartment_ph_reference_crosschecks@1", horizon_s=T,
                  budget_pH=BUDGET, records=len(rec), python=sys.version,
                  numpy=np.__version__, scipy=scipy.__version__, platform=platform.platform())
    closure = ph.integrate(w, T, record=rec)
    result["closure"] = summary(closure, rec)
    log("closure", result["closure"])
    kin, wall = {}, {}
    for kon in (1e3, 1e5, 1e7):
        t0 = time.perf_counter()
        kin[kon] = ph.integrate(w, T, record=rec, kinetic=True, k_on=(kon, kon))
        wall[kon] = time.perf_counter() - t0
    result["kinetic_1e7"] = summary(kin[1e7], rec)
    log("kinetic 1e7", result["kinetic_1e7"])
    result["convergence"] = {
        f"{kon:g}": dict(lumen=max_dpH(kin[kon], closure, rec, "pH_L"),
                         cytosol=max_dpH(kin[kon], closure, rec, "pH_c"),
                         heat_difference_final_pJ=kin[kon].at[T]["heat_pJ"]
                         - closure.at[T]["heat_pJ"], steps=kin[kon].steps, wall_s=wall[kon])
        for kon in (1e3, 1e5, 1e7)}
    lumen = [result["convergence"][f"{kon:g}"]["lumen"]["max"] for kon in (1e3, 1e5, 1e7)]
    result["convergence_ratios_lumen"] = [lumen[0] / lumen[1], lumen[1] / lumen[2]]
    log("convergence", result["convergence"])
    outside = ph.integrate(w, T, record=rec, kinetic=True, k_on=(None, 1e-3))
    w_out = replace(w, lumen=replace(w.lumen, buffers=(replace(w.lumen.buffers[0],
                                                               k_on_per_mM_per_s=1e-3),)))
    closure_out = ph.integrate(w_out, T, record=rec)
    result["outside"] = dict(lumen=max_dpH(outside, closure, rec, "pH_L"),
                             cytosol=max_dpH(outside, closure, rec, "pH_c"),
                             envelope_ratio_min_lumen=min(closure_out.at[t]["envelope_ratio"][1]
                                                          for t in rec),
                             energy_residual_max_pJ=max(abs(outside.at[t]["energy_residual_pJ"])
                                                        for t in rec))
    log("outside", result["outside"])
    neg = ph.integrate(ph.acceptance_world(P_K=0.0), T, record=rec)
    neg_kin = ph.integrate(ph.acceptance_world(P_K=0.0), T, record=rec, kinetic=True)
    result["negative_control"] = dict(
        closure=summary(neg, rec), kinetic_1e7=summary(neg_kin, rec),
        stall_pH=7.2 - neg.at[T]["pH_L"],
        difference_from_the_run_with_K_pH=neg.at[T]["pH_L"] - closure.at[T]["pH_L"],
        over_budget=(neg.at[T]["pH_L"] - closure.at[T]["pH_L"]) / BUDGET)
    log("negative control", result["negative_control"]["stall_pH"],
        result["negative_control"]["difference_from_the_run_with_K_pH"])
    tight_c = ph.integrate(w, T, record=rec, rtol=1e-12)
    tight_k = ph.integrate(w, T, record=rec, kinetic=True, k_on=(1e7, 1e7), rtol=1e-12)
    result["floor"] = dict(closure=max_dpH(closure, tight_c, rec, "pH_L"),
                           kinetic_1e7=max_dpH(kin[1e7], tight_k, rec, "pH_L"))
    log("floor", result["floor"])
    result["wall_s"] = time.perf_counter() - started
    (out / "crosschecks.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
    (out / "log.txt").write_text("\n".join(LOG) + "\n")
    log("wrote", out / "crosschecks.json")


if __name__ == "__main__":
    main()
