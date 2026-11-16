"""FR-4's and FR-5's dt studies: criteria first, the ladders, and the rungs' definitions.

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §7.2, §13.1 and §13.2. FR-4's world declares dt x G/C_b =
0.025 on the max-side G at 1 ms; FR-5's arms declare 0.5 ms on the patch total (about 0.024). Each
study confirms its world's declared step once the laws are wired: it extends the step ladder on
both sides, and judges the state's convergence and the energy residual against the criteria
written here before any run.

It lives in validation/compartment_ph_engine/, the lane's engine-facing package (parameters,
definitions and this study; on fr45-transporter the engine's records and planted laws), apart from
the independent references' code-blind folder validation/compartment_ph/ (the lead's ruling, 16
November 2026). The runs themselves are the qualification generator's parts
(validation/tissue/compartment_ph_qualification.py): a development dt study is its `dev` entry
on the ladder's parts, and its verdict is the judge's development verdict
(validation/tissue/compartment_ph_judge.py) against the protocol's criteria, which carry C1-C9
and F1-F5 below.

Usage:
    python -B -m validation.compartment_ph_engine.dt_study OUTDIR --write-criteria  # first
    python -B -m validation.compartment_ph_engine.dt_study OUTDIR --dry  # builds, no engine
    python -B -m validation.compartment_ph_engine.dt_study OUTDIR --run  # names the generator
"""

import json
import math
import sys
from pathlib import Path

from validation.compartment_ph_engine.definitions import fr4_world, fr5_world, today_only
from validation.compartment_ph_engine.parameters import ARM_R, ARM_T, World

LADDER_S = (2e-3, 1e-3, 5e-4, 2.5e-4)  # dt x G/C_b = 0.051, 0.025, 0.013, 0.0063 (max-side)
OBSERVABLES = ("lumen_pH", "patch_voltage_V", "lumen_K_fmol", "pump_cycles_fmol")
FR5_LADDER_S = (1e-3, 5e-4, 2.5e-4, 1.25e-4)  # patch total about 0.048, 0.024, 0.012, 0.006
FR5_DECLARED_DT_S = 5e-4
FR5_OBSERVABLES = ("lumen_X_fmol", "lumen_pH", "patch_voltage_V", "damage")
FR5_ARMS = {"T": ARM_T, "R": ARM_R}

CRITERIA = {
    "written": "before any run (this file's revision is the record); C7 revised on 15 "
               "November, still before any run, to the state-dependent lag check (the FR-4 "
               "references' run 02 found the fixed ratio insufficient)",
    "world": "parameters.World() (FR-4 §13.1), 900 s, explicit ARS(2,2,2), B7 present",
    "ladder_s": LADDER_S,
    "checks": {
        "C1_admission": "every rung is admitted; no rung is refused at run time",
        "C2_order": "the observed order of each observable, from successive differences on "
                    "shared record times, lies in [1.8, 2.2] on the three finest rungs",
        "C3_state_error_at_declared_dt": "at 1 ms, the Richardson-estimated error of the lumen "
                                         "pH is <= 1e-3 pH units, and of V_b <= 1e-3 of its range",
        "C4_energy": "the energy residual over flows is <= 2e-3 at 1 ms (today's booking), and "
                     "falls at second order down the ladder",
        "C5_ledgers": "material per species within its declared floor (H at 1e-16 fmol), charge "
                      "within the capacitor tolerance, at every record",
        "C6_bands": "the cytosol's pH stays within 7.2 ± 0.05 (the fuel band) on every rung",
        "C7_envelope": "the closure's estimated lag (rapid_proton_buffer.lag_estimate_ph) is "
                       "within 1e-3 pH at every stage of every buffered node",
        "C8_reference": "at 1 ms, agreement with the references agent's solution of Appendix A "
                        "within the budget that agent declares before comparing",
        "C9_control": "the P_K = 0 control at 1 ms stalls within 0.1 pH units, against a drop of "
                      "more than 1 unit with the route",
    },
    "verdict": "the declared dt (1 ms, 0.025) stands if C1-C9 hold; otherwise the world declares "
               "the finest rung that passes, and the failure is reported, not repaired",
}

FR5_CRITERIA = {
    "written": "before any run (this file's revision is the record), 15 November 2026, from "
               "fr5-transfer-v1's dt_study_criteria_written_first as the lead corrected it the "
               "same day (pre-run: the state error and the verdict at the declared 0.5 ms; the "
               "energy line at 1 ms; d exact at rounding)",
    "world": "definitions.fr5_world(parameters.ARM_T or ARM_R, start=FR-4's 1800 s extract), "
             "400 s, explicit ARS(2,2,2), records every 1 s",
    "ladder_s": FR5_LADDER_S,
    "declared_dt_s": FR5_DECLARED_DT_S,
    "checks": {
        "F1_admission": "every rung of both arms is admitted and runs to its end",
        "F2_order": "the lumen's X, the lumen's pH and V_b on the three finest rungs (0.5, 0.25 "
                    "and 0.125 ms) by FR-4's classes rule, as J2; d exact at rounding on every "
                    "rung pair (each difference under its floor)",
        "F3_state_error_at_declared_dt": "at the declared 0.5 ms, the Richardson-estimated error "
                                         "of the lumen's X <= X's budget and of the lumen's pH "
                                         "<= 1e-3, as J3",
        "F4_energy": "the energy residual over flows <= 2e-3 at 1 ms (the coarsest rung), "
                     "falling at second order down the ladder (the lead's ruling: at 0.5 ms it "
                     "would loosen about fourfold)",
        "F5_envelope": "the closure's state-dependent envelope at every stage of every buffered "
                       "node on every rung, as J5",
    },
    "verdict": "the declared 0.5 ms stands if F1-F5 hold for both arms; otherwise the arm "
               "declares the finest rung that passes, reported, not repaired",
}


def write_criteria(outdir):
    path = Path(outdir) / "DT_STUDY_CRITERIA.json"
    path.write_text(json.dumps(dict(fr4=CRITERIA, fr5=FR5_CRITERIA), indent=1))
    return path


def observed_order(coarse, middle, fine):
    """Order from three rungs at halving dt: log2(|coarse - middle| / |middle - fine|); None when
    either difference is zero (undefined values are None, never NaN, so records compare
    bitwise)."""
    num, den = abs(coarse - middle), abs(middle - fine)
    return math.log2(num / den) if den > 0 and num > 0 else None


def build_rungs(world=None):
    """FR-4: one definition per rung (today's parts and the pending parts), with its max-side
    product."""
    w = world or World()
    return [dict(dt_s=dt, product=w.counterion_rate_per_s(dt), definition=fr4_world(w, dt_s=dt))
            for dt in LADDER_S]


def build_fr5_rungs(arm, start=None, control=None):
    """FR-5: one definition per rung of one arm ("T" or "R"), from the start extract (None: FR-4's
    pH 7.2 start, for dry builds only), with the counterion's max-side product at that dt (the
    patch total's own figure is the references' measured 0.048 at 1 ms: §13.2)."""
    dw = FR5_ARMS[arm]
    return [dict(dt_s=dt, product=dw.base.counterion_rate_per_s(dt),
                 definition=fr5_world(dw, dt_s=dt, start=start, control=control))
            for dt in FR5_LADDER_S]


def _dry(rung):
    d = rung["definition"]
    return dict(dt_s=rung["dt_s"], product=rung["product"],
                steps=d["execution"]["max_steps"] - 8,
                records=len(d["experiment"]["observation_times"]),
                today_keys=sorted(today_only(d)["model"]))


def main(argv):
    outdir = Path(argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    if "--write-criteria" in argv:
        print(write_criteria(outdir))
        return 0
    if "--dry" in argv:
        summary = dict(fr4=[_dry(r) for r in build_rungs()],
                       fr5={arm: [_dry(r) for r in build_fr5_rungs(arm)] for arm in FR5_ARMS})
        (outdir / "dry.json").write_text(json.dumps(summary, indent=1))
        print(json.dumps(summary))
        return 0
    if "--run" in argv:
        raise SystemExit("the dt studies run as the qualification generator's parts: python -m "
                         "validation.tissue.compartment_ph_qualification dev fr4|fr5 OUT PART ... "
                         "(its engine path is a stand-in until the core's seams land)")
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
