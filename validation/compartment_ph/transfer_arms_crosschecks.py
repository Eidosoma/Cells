"""FR-5's revised world (§13.2 at 220d6e4d: arms T and R), checked by R-transfer.

    python -m validation.compartment_ph.transfer_arms_crosschecks --out DIR

Writes DIR/crosschecks.json and DIR/log.txt. Both arms start from FR-4's steady state at 1800 s,
here R-closure's own state there (the engine's checkpoint can be passed as tr.Start instead), with
X at 1 mM in the lumen and 1e-4 mM in the cytosol (the owner is impermeant, so the bath's X does
not enter). Horizon 400 s; records every second, and log-spaced below 1 s. Per arm and control:
the lumen's pH against pH50 and the damage window, f, X, the conditioned and pore transfers, X's
budget (1e-3 of X_L(0)) and each control's distance from its arm in units of it, the max-side
explicit-limit figure dt G/C_b at dt = 1 ms, the books, the steady pH under full damage, and the
floor (rtol 1e-11 against 1e-12). About a minute of CPU.
"""

import argparse
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy

from validation.compartment_ph import ph_reference as ph
from validation.compartment_ph import transfer_reference as tr

T = 400.0
PH50, HILL = 5.5, 4.0
ARMS = {
    "T": dict(P_X=1e-9, P_pore_X=0.0, P_pore_H=1e-5, window=(60.0, 120.0)),
    "R": dict(P_X=1e-10, P_pore_X=1e-6, P_pore_H=1e-5, window=(100.0, 160.0)),
}
DT = 1e-3  # s, the engine's step for the explicit-limit figure
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


def records():
    return tuple(sorted({*np.geomspace(1e-3, 1.0, 13), *np.arange(1.0, T + 1e-9, 1.0)}))


def arm_world(start, *, P_X, P_pore_X, P_pore_H, window, conditioned=True, damaged=True):
    damage = (tr.Damage(k_inj_per_s=1.0, k_res_per_s=0.05, injure=(tr.Window(*window),),
                        reseal=(tr.Window(window[1], math.inf),)) if damaged else tr.Damage())
    routes = [tr.CargoRoute("transfer", P_X, conditioned=conditioned)]
    if P_pore_X > 0:
        routes.append(tr.CargoRoute("pore", P_pore_X, damaged=True))
    return tr.TransferWorld(base=ph.acceptance_world(), start=start, cargo_routes=tuple(routes),
                            proton_pore_m_s=P_pore_H, condition=tr.Condition(PH50, HILL),
                            damage=damage)


def explicit_limit(run, rec, P_pore_H):
    """Max over the records of dt G/C_b, with the max-side GHK conductance
    G = z^2 F^2/(RT) P A max(c_in, c_out): the proton routes (leak and pore), and with K+."""
    b = run.model.w.base
    c = b.constants
    k = c.faraday_C_per_mol ** 2 / c.rt * b.patch_area_m2 * DT / b.patch_capacitance_F
    V = run.model.base.V
    proton, total = 0.0, 0.0
    for t in rec:
        r = run.at[t]
        gH = k * (b.proton_permeability_m_s + r["d"] * P_pore_H) * max(r["h_c"], r["h_L"])
        gK = k * b.permeability_m_s.get("K", 0.0) * max(r["ions_c"]["K"] / V[0],
                                                       r["ions_L"]["K"] / V[1])
        proton, total = max(proton, gH), max(total, gH + gK)
    h51 = 1000.0 * 10 ** -5.1
    at_51 = k * (b.proton_permeability_m_s + P_pore_H) * h51
    return dict(proton_routes_max=proton, with_K_max=total,
                proton_routes_at_pH_5p1_full_damage=at_51)


def arm_summary(run, rec, window, X_L0):
    at = run.at
    pH0 = at[rec[0]]["pH_L"]
    above = [t for t in rec if at[t]["pH_L"] > PH50]
    peak = max(rec, key=lambda t: at[t]["pH_L"])
    fmin = min(rec, key=lambda t: at[t]["f"])
    w0, w1 = window
    before = max(t for t in rec if t < w0)
    moved = {k: at[T]["moved_fmol"][k] for k in at[T]["moved_fmol"]}
    out = dict(
        pH_L_start=pH0, pH_L_peak=at[peak]["pH_L"], pH_L_peak_at_s=peak,
        pH_L_at_window_end=at[w1]["pH_L"],
        first_above_pH50_s=above[0] if above else None,
        last_above_pH50_s=above[-1] if above else None,
        crosses_pH50_within_window=bool(above) and w0 <= above[0] <= w1,
        reacidified_within_0p01_at_s=next((t for t in rec if t > peak
                                           and at[t]["pH_L"] - pH0 < 0.01), None),
        f_start=at[rec[0]]["f"], f_min=at[fmin]["f"], f_min_at_s=fmin,
        X_L_fraction={str(t): at[t]["X_L"] / X_L0 for t in (before, w1, T)},
        cX_L_over_cX_c={str(t): at[t]["cX_L"] / at[t]["cX_c"] for t in (before, w1, T)},
        J_transfer={"before_damage": at[before]["J_X"]["transfer"],
                    "at_f_min": at[fmin]["J_X"]["transfer"], "end": at[T]["J_X"]["transfer"]},
        moved_fmol_end=moved,
        moved_by_transfer_fraction={str(t): at[t]["moved_fmol"]["X_transfer"] / X_L0
                                    for t in (before, w1, T)},
        energy_residual_max_pJ=max(abs(at[t]["energy_residual_pJ"]) for t in rec),
        cytosol_band_max=max(abs(at[t]["pH_c"] - 7.2) for t in rec),
        steps=run.steps)
    if "X_pore" in moved:
        out["released_by_pore_in_window_fraction"] = (
            at[w1]["moved_fmol"]["X_pore"] - at[before]["moved_fmol"]["X_pore"]) / X_L0
        out["pore_flux_peak"] = min(at[t]["J_X"]["pore"] for t in rec)
    return out


def control_distance(arm, ctl, rec, X_L0):
    """Each quantity's largest difference, in units of the budget 1e-3 X_L(0)."""
    B = 1e-3 * X_L0
    dX = max((abs(arm.at[t]["X_L"] - ctl.at[t]["X_L"]), t) for t in rec)
    dM = max((abs(arm.at[t]["moved_fmol"]["X_transfer"] - ctl.at[t]["moved_fmol"]["X_transfer"]), t)
             for t in rec)
    dpH = max((abs(arm.at[t]["pH_L"] - ctl.at[t]["pH_L"]), t) for t in rec)
    return dict(X_L_in_budgets=dX[0] / B, X_L_at_s=dX[1],
                transfer_in_budgets=dM[0] / B, transfer_at_s=dM[1],
                pH_L_max=dpH[0], pH_L_at_s=dpH[1])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    rec = records()
    result = dict(kind="cells.compartment_transfer_arms_crosschecks@1", note_revision="220d6e4d",
                  horizon_s=T, records=len(rec), dt_s=DT, python=sys.version,
                  numpy=np.__version__, scipy=scipy.__version__, platform=platform.platform())
    start, steady = tr.steady_start(t_steady=1800.0)
    X_L0 = start.X_fmol[1]
    result["start"] = dict(t_steady_s=1800.0, pH_L=steady["pH_L"], pH_c=steady["pH_c"],
                           Vb=steady["Vb"], X_L0_fmol=X_L0, budget_fmol=1e-3 * X_L0)
    log("start", result["start"])
    for name, p in ARMS.items():
        arm = tr.integrate(arm_world(start, **p), T, record=rec)
        if name == "T":
            ctl_name, ctl = "f_equals_1", tr.integrate(arm_world(start, **p, conditioned=False), T,
                                                       record=rec)
        else:
            ctl_name, ctl = "d_equals_0", tr.integrate(arm_world(start, **p, damaged=False), T,
                                                       record=rec)
        tight = tr.integrate(arm_world(start, **p), T, record=rec, rtol=1e-12)
        full = tr.integrate(tr.TransferWorld(
            base=ph.acceptance_world(), start=start, proton_pore_m_s=p["P_pore_H"],
            damage=tr.Damage(d0=1.0)), 3600.0, record=(3600.0,))
        result[name] = dict(
            parameters=dict(p, window=list(p["window"])),
            arm=arm_summary(arm, rec, p["window"], X_L0),
            control=dict(name=ctl_name, summary=arm_summary(ctl, rec, p["window"], X_L0),
                         distance=control_distance(arm, ctl, rec, X_L0)),
            explicit_limit=explicit_limit(arm, rec, p["P_pore_H"]),
            full_damage_steady=dict(pH_L=full.at[3600.0]["pH_L"], Vb=full.at[3600.0]["Vb"],
                                    f=tr.Condition(PH50, HILL).f(full.at[3600.0]["pH_L"])),
            floor=dict(X_L=max(abs(arm.at[t]["X_L"] - tight.at[t]["X_L"]) for t in rec) / X_L0,
                       pH_L=max(abs(arm.at[t]["pH_L"] - tight.at[t]["pH_L"]) for t in rec)),
            material_drift_max=dict(
                Heq=max(abs(arm.at[t]["Heq_c"] + arm.at[t]["Heq_L"] - sum(start.Heq_fmol))
                        for t in rec) / sum(start.Heq_fmol),
                X=max(abs(arm.at[t]["X_c"] + arm.at[t]["X_L"] - sum(start.X_fmol)) for t in rec)
                / sum(start.X_fmol)))
        log("arm", name, result[name])
    result["wall_s"] = time.perf_counter() - started
    (out / "crosschecks.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
    (out / "log.txt").write_text("\n".join(LOG) + "\n")
    log("wrote", out / "crosschecks.json")


if __name__ == "__main__":
    main()
