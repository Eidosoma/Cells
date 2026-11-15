"""FR-4's reference evidence on §13.1's world (900 s), for the usage note and the lead.

    python -m validation.compartment_ph.ph_crosschecks --out DIR

Writes DIR/crosschecks.json and DIR/log.txt, with records log-spaced from 1 us and every 10 s:
1. buffered acidification against a gradient, K+ counterion and maintained fuel, by full kinetics
   (R-kinetic at k_on = 1e7 mM^-1 s^-1) and by the closure: pH, V_b, the pump's cycles and
   dG_cyc, the K+ moved, the energy identity, the cytosol's pH band;
2. convergence to the closure as k_on grows (1e3, 1e5, 1e7), per node: the largest
   |pH_kinetic - pH_closure| over the run and after 10 s; the lag's first-order term at the peak;
   the local lag (pH_kinetic against the closure's pH at the kinetic run's own H_eq) against that
   term; §4.2's envelope ratio at each k_on; the flux errors (the budget's second clause, read as
   the largest difference over the run's largest closure flux); the reaction heat;
3. the outside case (the lumen's k_on = 1e-3 mM^-1 s^-1, 1 M^-1 s^-1): beyond the 1e-3 pH budget,
   with the envelope ratio at that k_on;
4. the negative control (P_K = 0): the stall, against the 1e-3 pH budget, by both references;
5. the window between §4.2's envelope and the budget: the k_on from which the envelope check
   passes, and the k_on from which the budget holds (first order in 1/k_on, from the 1e7 run);
plus the floor (rtol 1e-11 against 1e-12) of both references. About 30 s of CPU.
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
BUDGET = 1e-3  # pH (§4.2)
K_ONS = (1e3, 1e5, 1e7)  # mM^-1 s^-1
NODES = (("cytosol", 0, "pH_c", "h_c", "Heq_c"), ("lumen", 1, "pH_L", "h_L", "Heq_L"))
LOCAL_FLOOR = 1e-10  # pH; the local lag is compared where its first-order term exceeds this
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


def records():
    return tuple(sorted({*np.geomspace(1e-6, T, 120), *np.arange(10.0, T + 1e-9, 10.0)}))


def summary(run, rec):
    last = run.at[rec[-1]]
    n = run.model.w.pump.n
    return dict(
        pH_L_final=last["pH_L"], pH_c_final=last["pH_c"],
        gradient_pH_final=last["pH_c"] - last["pH_L"], Vb_final=last["Vb"],
        Vb_extreme=max((run.at[t]["Vb"] for t in rec), key=abs), cycles=last["cycles"],
        dG_cyc_final_J_per_mol=last["dG_cyc"], J_net_H_final=n * last["J_cyc"] + last["J_H"],
        K_moved_into_cytosol=last["ions_c"].get("K", 0.0) - run.model.ions0[0]["K"],
        work_pJ=last["work_pJ"], heat_pJ=last["heat_pJ"], reaction_heat_pJ=last["reaction_heat_pJ"],
        energy_residual_max_pJ=max(abs(run.at[t]["energy_residual_pJ"]) for t in rec),
        cytosol_band_max=max(abs(run.at[t]["pH_c"] - 7.2) for t in rec),
        envelope_ratio_min=[min(run.at[t]["envelope_ratio"][i] for t in rec) for i in (0, 1)],
        steps=run.steps)


def max_dpH(a, b, rec, key):
    v, t = max((abs(a.at[t][key] - b.at[t][key]), t) for t in rec)
    return dict(max=v, at_s=t)


def first_order_lag(r, i, h_key):
    """The closure's first-order lag in pH, (rho/lambda)(beta/ln 10 - h)/(h ln 10), at a record
    (one buffer per node): the quasi-steady excess of free protons, dH_eq/dt over lambda, times the
    bound share, over h ln 10 (Keener and Sneyd 2009, ch. 7, the rapid-buffer expansion)."""
    h, beta = r[h_key], r["buffer_capacity"][i]
    return (beta / ph.LN10 - h) / (h * ph.LN10) / r["envelope_ratio"][i]


def local_closure_pH(run, r, i, heq_key):
    """The closure's pH at this record's own H_eq (the local reference for the lag)."""
    m = run.model
    V = m.V[i]
    pairs = [(Bt / V, K) for Bt, K, *_ in m.buf[i]]
    return ph.pH(ph.free_proton(r[heq_key] / V, pairs, m.c0), m.c0)


def flux_errors(kin, clo, rec):
    n = clo.model.w.pump.n
    get = dict(J_cyc=lambda r: r["J_cyc"], J_H=lambda r: r["J_H"],
               J_K=lambda r: r["J_ions"]["K"], J_net_H=lambda r: n * r["J_cyc"] + r["J_H"])
    return {key: max(abs(f(kin.at[t]) - f(clo.at[t])) for t in rec)
            / max(abs(f(clo.at[t])) for t in rec) for key, f in get.items()}


def kinetic_against_closure(kin, clo, rec):
    late = [t for t in rec if t >= 10.0]
    plateau = [t for t in rec if t >= 1e-3]
    out = dict(flux_errors=flux_errors(kin, clo, rec),
               reaction_heat_pJ=kin.at[rec[-1]]["reaction_heat_pJ"],
               heat_difference_final_pJ=kin.at[rec[-1]]["heat_pJ"] - clo.at[rec[-1]]["heat_pJ"],
               steps=kin.steps)
    for name, i, p_key, h_key, heq_key in NODES:
        peak = max_dpH(kin, clo, rec, p_key)
        pairs = []
        for t in plateau:
            r = kin.at[t]
            pred = first_order_lag(r, i, h_key)
            if pred > LOCAL_FLOOR:
                pairs.append((abs(r[p_key] - local_closure_pH(kin, r, i, heq_key)), pred))
        out[name] = dict(
            max_pH=peak["max"], at_s=peak["at_s"],
            max_after_10s_pH=max_dpH(kin, clo, late, p_key)["max"] if late else None,
            first_order_lag_at_peak_pH=first_order_lag(kin.at[peak["at_s"]], i, h_key),
            local_lag_max_pH=max(o for o, _ in pairs),
            local_lag_over_first_order=[min(o / q for o, q in pairs), max(o / q for o, q in pairs)],
            local_lag_records=len(pairs),
            envelope_ratio_min=min(kin.at[t]["envelope_ratio"][i] for t in rec))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    rec = records()
    w = ph.acceptance_world()
    result = dict(kind="cells.compartment_ph_reference_crosschecks@2", horizon_s=T,
                  budget_pH=BUDGET, records=len(rec), python=sys.version,
                  numpy=np.__version__, scipy=scipy.__version__, platform=platform.platform())

    # 1. The acidification, by the closure and by full kinetics at the declared k_on.
    closure = ph.integrate(w, T, record=rec)
    result["closure"] = summary(closure, rec)
    log("closure", result["closure"])
    kin, wall = {}, {}
    for kon in K_ONS:
        t0 = time.perf_counter()
        kin[kon] = ph.integrate(w, T, record=rec, kinetic=True, k_on=(kon, kon))
        wall[kon] = time.perf_counter() - t0
    result["kinetic_1e7"] = summary(kin[1e7], rec)
    log("kinetic 1e7", result["kinetic_1e7"])

    # 2. Convergence as k_on grows.
    result["convergence"] = {}
    for kon in K_ONS:
        row = kinetic_against_closure(kin[kon], closure, rec)
        row["wall_s"] = wall[kon]
        result["convergence"][f"{kon:g}"] = row
        log("convergence", f"{kon:g}", row)
    lumen = [result["convergence"][f"{kon:g}"]["lumen"]["max_pH"] for kon in K_ONS]
    result["convergence_ratios_lumen"] = [lumen[0] / lumen[1], lumen[1] / lumen[2]]

    # 3. The outside case: the lumen's k_on at 1e-3 mM^-1 s^-1, the cytosol's as declared.
    outside = ph.integrate(w, T, record=rec, kinetic=True, k_on=(None, 1e-3))
    lumen_slow = replace(w.lumen.buffers[0], k_on_per_mM_per_s=1e-3)
    closure_slow = ph.integrate(replace(w, lumen=replace(w.lumen, buffers=(lumen_slow,))), T,
                                record=rec)
    result["outside"] = dict(
        lumen=max_dpH(outside, closure, rec, "pH_L"),
        cytosol=max_dpH(outside, closure, rec, "pH_c"),
        envelope_ratio_min_lumen_closure_run=min(closure_slow.at[t]["envelope_ratio"][1]
                                                 for t in rec),
        envelope_ratio_min_lumen_kinetic_run=min(outside.at[t]["envelope_ratio"][1] for t in rec),
        energy_residual_max_pJ=max(abs(outside.at[t]["energy_residual_pJ"]) for t in rec),
        reaction_heat_pJ=outside.at[T]["reaction_heat_pJ"])
    log("outside", result["outside"])

    # 4. The negative control, P_K = 0.
    neg = ph.integrate(ph.acceptance_world(P_K=0.0), T, record=rec)
    neg_kin = ph.integrate(ph.acceptance_world(P_K=0.0), T, record=rec, kinetic=True)
    difference = neg.at[T]["pH_L"] - closure.at[T]["pH_L"]
    result["negative_control"] = dict(
        closure=summary(neg, rec), kinetic_1e7=summary(neg_kin, rec),
        kinetic_against_closure_max_pH=max_dpH(neg_kin, neg, rec, "pH_L"),
        stall_pH=7.2 - neg.at[T]["pH_L"], difference_from_the_run_with_K_pH=difference,
        over_budget=difference / BUDGET)
    log("negative control", result["negative_control"]["stall_pH"], difference)

    # 5. The window: lambda is proportional to k_on at a fixed state, and the lag is first order
    # in 1/k_on (the convergence ratios).
    ratio_1e7 = [min(closure.at[t]["envelope_ratio"][i] for t in rec) for i in (0, 1)]
    worst_1e7 = max(result["convergence"]["1e+07"][name]["max_pH"] for name, *_ in NODES)
    result["window"] = dict(
        envelope_ratio_min_at_1e7=ratio_1e7,
        k_on_from_which_the_envelope_check_passes=max(1e3 * 1e7 / r for r in ratio_1e7),
        k_on_from_which_the_budget_holds=1e7 * worst_1e7 / BUDGET)
    log("window", result["window"])

    # The floor.
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
