"""FR-4's dt study harness: criteria first, the ladder, and the checks (ready for the wired laws).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §7.2 and §13.1. The world declares dt × G/C_b = 0.025 on
the max-side G at 1 ms. This study confirms that choice once the pump and the closure are wired.
It extends the step ladder on both sides, and judges the state's convergence and the energy
residual against the criteria written here before any run.

Usage:
    python -B -m validation.compartment_ph.dt_study OUTDIR --write-criteria   # before any run
    python -B -m validation.compartment_ph.dt_study OUTDIR --dry              # builds, no engine
    python -B -m validation.compartment_ph.dt_study OUTDIR --run              # after the wiring

`--run` needs the core's insertion points (stage reads, transporters, held rows) and this
branch's laws wired. Until then it refuses, saying so.
"""

import json
import sys
from pathlib import Path

from validation.compartment_ph.definitions import fr4_world, today_only
from validation.compartment_ph.parameters import World

LADDER_S = (2e-3, 1e-3, 5e-4, 2.5e-4)  # dt x G/C_b = 0.051, 0.025, 0.013, 0.0063 (max-side)
OBSERVABLES = ("lumen_pH", "patch_voltage_V", "lumen_K_fmol", "pump_cycles_fmol")

CRITERIA = {
    "written": "before any run (this file's revision is the record)",
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
        "C7_envelope": "the closure's envelope (lambda >= 1e3 rho) holds at every stage",
        "C8_reference": "at 1 ms, agreement with the references agent's solution of Appendix A "
                        "within the budget that agent declares before comparing",
        "C9_control": "the P_K = 0 control at 1 ms stalls within 0.1 pH units, against a drop of "
                      "more than 1 unit with the route",
    },
    "verdict": "the declared dt (1 ms, 0.025) stands if C1-C9 hold; otherwise the world declares "
               "the finest rung that passes, and the failure is reported, not repaired",
}


def write_criteria(outdir):
    path = Path(outdir) / "DT_STUDY_CRITERIA.json"
    path.write_text(json.dumps(CRITERIA, indent=1))
    return path


def observed_order(coarse, middle, fine):
    """Order from three rungs at halving dt: log2(|coarse - middle| / |middle - fine|)."""
    import math

    num, den = abs(coarse - middle), abs(middle - fine)
    return math.log2(num / den) if den > 0 and num > 0 else float("nan")


def build_rungs(world=None):
    """One definition per rung (today's parts and the pending parts), with its max-side product."""
    w = world or World()
    return [dict(dt_s=dt, product=w.counterion_rate_per_s(dt), definition=fr4_world(w, dt_s=dt))
            for dt in LADDER_S]


def main(argv):
    outdir = Path(argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    if "--write-criteria" in argv:
        print(write_criteria(outdir))
        return 0
    rungs = build_rungs()
    if "--dry" in argv:
        summary = [dict(dt_s=r["dt_s"], product=r["product"],
                        steps=r["definition"]["execution"]["max_steps"] - 8,
                        today_keys=sorted(today_only(r["definition"])["model"]))
                   for r in rungs]
        (outdir / "dry.json").write_text(json.dumps(summary, indent=1))
        print(json.dumps(summary))
        return 0
    if "--run" in argv:
        raise SystemExit("dt_study --run needs the core's insertion points and the FR-4 laws "
                         "wired (stage reads, transporters, held rows); not yet on this branch")
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
