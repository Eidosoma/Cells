"""Development evidence for FR-5's engine path (not a verdict): one arm of FR-5's world on the
engine against R-transfer, from one start extract, over a short horizon with the damage window
moved inside it, so the damage, the pores and the condition all act before the end.

    python -m validation.compartment_ph_engine.fr5_quick_check START_JSON ARM OUT_JSON
        [--horizon S] [--window T0 T1] [--dt S] [--path vector|host] [--world declared|development]

ARM is T or R (parameters.ARM_T, ARM_R). The arm is replaced with the extract's time as its start
checkpoint, the horizon (default 20 s) and the window (default 2 to 8 s); the engine runs
definitions.fr5_world at dt (default the arm's 0.5 ms) through engine_records.run on the path and
world named (default the protocols': vector, declared); R-transfer runs the same arm from the same
extract (the reference stage's tr_start and arm_world) at the stage's rtol, recorded at the same
integer seconds. Reported with the judge's arithmetic (max-norm differences on shared records):
X_L in units of the X budget (1e-3 X_L(0)), the pH of both buffered nodes against the 1e-3 budget,
d, f, V_b, and each route's cumulative transfer (moved_*), with the engine's admission, steps,
ledgers and cost. The protocol's arms keep their own windows; this check only moves the window.
"""

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path

from validation.compartment_ph import transfer_reference as tr
from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine import engine_records
from validation.compartment_ph_engine.parameters import ARM_R, ARM_T
from validation.tissue import compartment_ph_judge as judge
from validation.tissue import compartment_ph_reference_stage as stage

ARMS = {"T": ARM_T, "R": ARM_R}
SERIES = ("X_L", "X_c", "pH_L", "pH_c", "V_b", "d", "f", "moved_X_transfer", "moved_X_pore",
          "moved_H_pore", "moved_H_leak")


def arm(name, extract, horizon_s, window_s):
    return replace(ARMS[name], start_checkpoint_s=extract["time_s"], horizon_s=horizon_s,
                   injury_window_s=tuple(window_s))


def reference(dw, extract):
    times = stage.record_times(dw.horizon_s)
    run = tr.integrate(stage.arm_world(stage.tr_start(extract, dw), dw), times[-1],
                       record=times, rtol=stage.RTOL)
    return dict(record_s=times, series=stage.transfer_series(run, times), completed=True,
                start_check=stage.start_check(run, extract))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("start", type=Path)
    parser.add_argument("arm", choices=sorted(ARMS))
    parser.add_argument("out", type=Path)
    parser.add_argument("--horizon", type=float, default=20.0)
    parser.add_argument("--window", type=float, nargs=2, default=(2.0, 8.0))
    parser.add_argument("--dt", type=float, default=None)
    parser.add_argument("--path", choices=engine_records.PATHS, default="vector")
    parser.add_argument("--world", choices=engine_records.WORLDS, default="declared")
    args = parser.parse_args(argv)
    extract = defs.read_start(args.start)
    dw = arm(args.arm, extract, args.horizon, args.window)
    started = time.perf_counter()
    eng = engine_records.run(defs.fr5_world(dw, dt_s=args.dt, start=extract), path=args.path,
                             world=args.world)
    eng_s = time.perf_counter() - started
    ref = reference(dw, extract)
    x0 = ref["series"]["X_L"][0]
    budget = dw.x_budget_fraction * x0
    out = dict(
        kind="development check (not a verdict): FR-5's engine against R-transfer",
        arm=args.arm, horizon_s=dw.horizon_s, window_s=list(dw.injury_window_s),
        dt_s=args.dt or dw.dt_s, path=args.path, world=args.world,
        start=dict(producer=extract["producer"], time_s=extract["time_s"],
                   extract_sha256=defs.start_sha256(extract)),
        engine=dict(admitted=eng["admitted"], completed=eng["completed"], refusal=eng["refusal"],
                    steps=eng["steps"], seconds=eng_s, stage=eng.get("stage"),
                    ledgers=eng.get("ledgers"), timings=eng.get("timings")),
        reference_start_check=ref["start_check"],
        x_budget_fmol=budget,
        max_abs={}, at_end={},
    )
    if eng["completed"]:
        for name in SERIES:
            if name in eng["series"] and name in ref["series"]:
                out["max_abs"][name] = judge.max_abs_difference(eng, ref, name)
                out["at_end"][name] = dict(engine=eng["series"][name][-1],
                                           reference=ref["series"][name][-1])
        out["X_L_over_budget"] = out["max_abs"]["X_L"] / budget
        out["pH_max_abs"] = judge.ph_max_abs(eng, ref, ["pH_L", "pH_c"])
        out["moved_X_over_budget"] = {k: v / budget for k, v in out["max_abs"].items()
                                      if k.startswith("moved_X")}
        out["engine_series_names"] = sorted(eng["series"])
    args.out.write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    print(json.dumps({k: out[k] for k in ("arm", "X_L_over_budget", "pH_max_abs",
                                          "moved_X_over_budget") if k in out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
