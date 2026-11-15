"""FR-5's reference evidence on §13.2's world, for the usage note and the lead.

    python -m validation.compartment_ph.transfer_crosschecks --out DIR

Writes DIR/crosschecks.json and DIR/log.txt:
1. the start: FR-4's world at its steady state (R-closure at 3600 s), against its state at 1800 s;
2. the declared world over 900 s (records log-spaced to 100 s, every 0.5 s on [100, 140] s, then
   every 10 s): X's transfer while the lumen is acidic, the damage's proton leak and pH rise, the
   pore's release of X, resealing and re-acidification, every route's heat and amount, the energy
   identity and the material;
3. the declared negative controls, f = 1 and d = 0, against the declared run;
4. a sensitivity grid to 300 s, over P_X and the proton pore's P, showing what the release burst
   and the condition's closing need;
plus the floor (rtol 1e-11 against 1e-12). About two minutes of CPU.
"""

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy

from validation.compartment_ph import ph_reference as ph
from validation.compartment_ph import transfer_reference as tr

T = 900.0
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


def records(t_end):
    return tuple(sorted({*np.geomspace(1e-3, 100.0, 40), 1.0, 10.0, 99.5,
                         *np.arange(100.0, 140.0 + 1e-9, 0.5),
                         *np.arange(140.0, t_end + 1e-9, 10.0)}))


def first_time(run, rec, test, after=0.0):
    return next((t for t in rec if t >= after and test(run.at[t])), None)


def summary(run, rec, start):
    at = run.at
    end = at[rec[-1]]
    pH0 = at[rec[0]]["pH_L"]
    peak_t = max(rec, key=lambda t: at[t]["pH_L"])
    K0 = start.ions_fmol[0]["K"] + start.ions_fmol[1]["K"]
    return dict(
        pH_L={str(t): at[t]["pH_L"] for t in (rec[0], 99.5, 110.0, 200.0, 300.0, 600.0, rec[-1])
              if t in at},
        pH_L_peak=at[peak_t]["pH_L"], pH_L_peak_at_s=peak_t,
        f_min=min(at[t]["f"] for t in rec), d_at_110=at[110.0]["d"] if 110.0 in at else None,
        reacidified_within_0p01_at_s=first_time(run, rec, lambda r: r["pH_L"] - pH0 < 0.01,
                                                after=peak_t),
        reacidified_within_0p001_at_s=first_time(run, rec, lambda r: r["pH_L"] - pH0 < 1e-3,
                                                 after=peak_t),
        cX_L={str(t): at[t]["cX_L"] for t in (rec[0], 1.0, 10.0, 99.5, 140.0, rec[-1])
              if t in at},
        cX_c_final=end["cX_c"],
        gradient_at_99p5_over_start=(at[99.5]["cX_L"] - at[99.5]["cX_c"])
        / (start.X_fmol[1] / run.model.base.V[1] - start.X_fmol[0] / run.model.base.V[0]),
        moved_fmol=end["moved_fmol"], heat_by_route_pJ=end["heat_by_route_pJ"],
        work_pJ=end["work_pJ"], heat_pJ=end["heat_pJ"], cycles=end["cycles"],
        energy_residual_max_pJ=max(abs(at[t]["energy_residual_pJ"]) for t in rec),
        material_drift_max=dict(
            Heq=max(abs(at[t]["Heq_c"] + at[t]["Heq_L"] - sum(start.Heq_fmol)) for t in rec)
            / sum(start.Heq_fmol),
            X=max(abs(at[t]["X_c"] + at[t]["X_L"] - sum(start.X_fmol)) for t in rec)
            / sum(start.X_fmol),
            K=max(abs(at[t]["ions_c"]["K"] + at[t]["ions_L"]["K"] - K0) for t in rec) / K0),
        phi_c_max=max(abs(at[t]["phi_c"]) for t in rec), steps=run.steps)


def largest_difference(a, b, rec, key):
    v, t = max((abs(a.at[t][key] - b.at[t][key]), t) for t in rec)
    return dict(max=v, at_s=t)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result = dict(kind="cells.compartment_transfer_reference_crosschecks@1", horizon_s=T,
                  python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                  platform=platform.platform())

    # 1. The start.
    start, steady = tr.steady_start()
    earlier = ph.integrate(ph.acceptance_world(), 1800.0, record=(1800.0,)).at[1800.0]
    n = ph.acceptance_world().pump.n
    result["start"] = dict(
        t_steady_s=3600.0, pH_L=steady["pH_L"], pH_c=steady["pH_c"], Vb=steady["Vb"],
        J_net_H=n * steady["J_cyc"] + steady["J_H"], J_K=steady["J_ions"]["K"],
        pH_L_change_since_1800s=steady["pH_L"] - earlier["pH_L"],
        X_mM=[start.X_fmol[0] / ph.acceptance_world().cytosol.volume_pL,
              start.X_fmol[1] / ph.acceptance_world().lumen.volume_pL])
    log("start", result["start"])

    # 2. The declared world.
    rec = records(T)
    result["records"] = len(rec)
    declared = tr.integrate(tr.acceptance_world(start=start), T, record=rec)
    result["declared"] = summary(declared, rec, start)
    model = declared.model
    V, A = model.base.V, model.w.base.patch_area_m2
    f0 = declared.at[rec[0]]["f"]
    k_X = 1e15 * f0 * 1e-8 * A * (1.0 / V[0] + 1.0 / V[1])
    result["declared"]["X_relaxation_time_s"] = 1.0 / k_X
    log("declared", result["declared"])

    # 3. The negative controls.
    controls = {}
    for name, kw in (("f_equals_1", dict(conditioned=False)), ("d_equals_0", dict(damaged=False))):
        run = tr.integrate(tr.acceptance_world(start=start, **kw), T, record=rec)
        controls[name] = dict(
            summary=summary(run, rec, start),
            against_declared=dict(pH_L=largest_difference(run, declared, rec, "pH_L"),
                                  cX_L=largest_difference(run, declared, rec, "cX_L"),
                                  cX_c=largest_difference(run, declared, rec, "cX_c")))
        log("control", name, controls[name]["against_declared"])
    result["negative_controls"] = controls

    # 4. Sensitivity, to 300 s.
    grid = []
    rec_s = tuple(t for t in rec if t <= 300.0)
    for P_X in (1e-8, 1e-10, 1e-11):
        for P_pore_H in (1e-6, 1e-5, 1e-4):
            run = tr.integrate(tr.acceptance_world(start=start, P_X=P_X, P_pore_H=P_pore_H),
                               300.0, record=rec_s)
            at = run.at
            X_L0 = start.X_fmol[1]
            row = dict(
                P_X=P_X, P_pore_H=P_pore_H,
                X_lumen_fraction_at_99p5=at[99.5]["X_L"] / X_L0,
                X_moved_by_pore_fraction=at[300.0]["moved_fmol"]["X_pore"] / X_L0,
                X_moved_by_transfer_fraction=at[300.0]["moved_fmol"]["X_transfer"] / X_L0,
                pH_L_peak=max(at[t]["pH_L"] for t in rec_s), f_min=min(at[t]["f"] for t in rec_s),
                energy_residual_max_pJ=max(abs(at[t]["energy_residual_pJ"]) for t in rec_s))
            grid.append(row)
            log("grid", row)
    result["sensitivity_to_300s"] = grid

    # The floor.
    tight = tr.integrate(tr.acceptance_world(start=start), T, record=rec, rtol=1e-12)
    result["floor"] = dict(pH_L=largest_difference(declared, tight, rec, "pH_L"),
                           cX_L=largest_difference(declared, tight, rec, "cX_L"))
    log("floor", result["floor"])
    result["wall_s"] = time.perf_counter() - started
    (out / "crosschecks.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
    (out / "log.txt").write_text("\n".join(LOG) + "\n")
    log("wrote", out / "crosschecks.json")


if __name__ == "__main__":
    main()
