"""Item 4's reference evidence: finite fuel against held fuel, for the usage note and the lead.

    python -m validation.compartment_ph.fuel_crosschecks --out DIR

Writes DIR/crosschecks.json and DIR/log.txt for the calibrated first case over 900 s: the
regeneration off on [100, 300) s (depletion, reduced pump activity, recovery), held fuel (no
depletion), and the negative control (m = 1). Records every 10 s, and every second around the
window's edges. Reports the pump, the fuel, Y, the free energies, every heat, the energy identity
and the moieties, plus the floor (rtol 1e-11 against 1e-12). Seconds of CPU.
"""

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy

from validation.compartment_ph import fuel_reference as fr

T = 900.0
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


def records():
    return tuple(sorted({*np.arange(10.0, T + 1e-9, 10.0), *np.arange(95.0, 106.0, 1.0),
                         *np.arange(295.0, 331.0, 1.0), 299.0}))


def summary(run, rec):
    at = run.at
    fed = at[99.0]
    out = dict(
        J_cyc={str(t): at[t]["J_cyc"] for t in (99.0, 150.0, 200.0, 299.0, 310.0, 400.0, T)},
        ATP_mM={str(t): at[t]["c"]["ATP"] for t in (99.0, 150.0, 200.0, 299.0, 310.0, 400.0, T)},
        ADP_mM_299=at[299.0]["c"]["ADP"], Pi_mM_299=at[299.0]["c"]["Pi"],
        Y_s_mM={str(t): at[t]["c"]["Y_s"] for t in (99.0, 299.0, 400.0, T)},
        dG_ATP_kJ={str(t): at[t]["dG_ATP"] / 1e3 for t in (99.0, 299.0, 400.0)},
        dG_cyc_over_RT_max=max(abs(at[t]["dG_cyc"]) for t in rec) / run.model.w.rt,
        J_cyc_min=min(at[t]["J_cyc"] for t in rec),
        recovered_within_1pc_at_s=next((t for t in rec if t >= 300.0
                                        and abs(at[t]["J_cyc"] / fed["J_cyc"] - 1) < 1e-2), None),
        recovered_within_0p1pc_at_s=next((t for t in rec if t >= 300.0
                                          and abs(at[t]["J_cyc"] / fed["J_cyc"] - 1) < 1e-3), None),
        cycles=at[T]["cycles"], regenerated=at[T]["regenerated"], heat_pJ=at[T]["heat_pJ"],
        W_pJ=at[T]["W_pJ"], Q_pJ=at[T]["Q_pJ"], stored_change_pJ=at[T]["stored_change_pJ"],
        energy_residual_max_pJ=max(abs(at[t]["energy_residual_pJ"]) for t in rec),
        moiety_drift_max={k: max(abs(at[t]["moieties"][k] - at[rec[0]]["moieties"][k])
                                 for t in rec) / abs(at[rec[0]]["moieties"][k])
                          for k in at[rec[0]]["moieties"]},
        steps=run.steps)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    rec = records()
    w = fr.acceptance_world()
    result = dict(kind="cells.compartment_fuel_reference_crosschecks@1", horizon_s=T,
                  records=len(rec), python=sys.version, numpy=np.__version__,
                  scipy=scipy.__version__, platform=platform.platform(),
                  dG0_hyd_J_per_mol=w.dG0_hyd(), dG0_reg_J_per_mol=w.dG0_reg(),
                  standard_mM=w.standard_mM, rt_J_per_mol=w.rt)
    runs = {"finite": fr.integrate(w, T, record=rec),
            "held": fr.integrate(fr.acceptance_world(held=True), T, record=rec),
            "control_m_equals_1": fr.integrate(fr.acceptance_world(off_windows=()), T, record=rec)}
    for name, run in runs.items():
        result[name] = summary(run, rec)
        log(name, result[name])
    f, h = runs["finite"].at, runs["held"].at
    result["finite_against_held"] = dict(
        J_cyc_ratio_at_299=f[299.0]["J_cyc"] / h[299.0]["J_cyc"],
        cycles_lost_fmol=h[T]["cycles"] - f[T]["cycles"],
        Y_s_difference_at_299_mM=h[299.0]["c"]["Y_s"] - f[299.0]["c"]["Y_s"])
    log("finite against held", result["finite_against_held"])
    tight = fr.integrate(w, T, record=rec, rtol=1e-12)
    result["floor"] = dict(
        ATP_mM=max(abs(runs["finite"].at[t]["c"]["ATP"] - tight.at[t]["c"]["ATP"]) for t in rec),
        J_cyc=max(abs(runs["finite"].at[t]["J_cyc"] - tight.at[t]["J_cyc"]) for t in rec),
        Q_pJ=max(abs(runs["finite"].at[t]["Q_pJ"] - tight.at[t]["Q_pJ"]) for t in rec))
    log("floor", result["floor"])
    result["wall_s"] = time.perf_counter() - started
    (out / "crosschecks.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
    (out / "log.txt").write_text("\n".join(LOG) + "\n")
    log("wrote", out / "crosschecks.json")


if __name__ == "__main__":
    main()
