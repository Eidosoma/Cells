"""Development evidence (not a verdict): FR-5's declared world (FR-1's compartment operator
included, the composite) against its development world (without it), record for record. The
operator adds identity and refusals only (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.1, §3.4.3), so
the two must be bitwise equal, as FR-4's were over 900 s.

    python -m validation.compartment_ph_engine.world_agreement START_JSON ARM OUT_JSON
        [--horizon S] [--window T0 T1] [--dt S] [--path vector|host]

One arm (T or R) of definitions.fr5_world from the start extract, its window and horizon as
fr5_quick_check moves them (defaults 10 s and 2 to 6 s), through engine_records.run in each world.
Reported: each run's admission, completion, refusal and steps, and the paths where the two records
differ (the judge's compare: every leaf bit for bit, run times apart), with every series' and
amount row's largest difference.
"""

import argparse
import json
from pathlib import Path

from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine import engine_records
from validation.compartment_ph_engine.fr5_quick_check import arm
from validation.tissue import compartment_ph_judge as judge
from validation.tissue.regulated_availability_judge import differences


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("start", type=Path)
    parser.add_argument("arm", choices=("T", "R"))
    parser.add_argument("out", type=Path)
    parser.add_argument("--horizon", type=float, default=10.0)
    parser.add_argument("--window", type=float, nargs=2, default=(2.0, 6.0))
    parser.add_argument("--dt", type=float, default=None)
    parser.add_argument("--path", choices=engine_records.PATHS, default="vector")
    args = parser.parse_args(argv)
    extract = defs.read_start(args.start)
    definition = defs.fr5_world(arm(args.arm, extract, args.horizon, args.window), dt_s=args.dt,
                               start=extract)
    records = {world: engine_records.run(definition, path=args.path, world=world)
               for world in ("development", "declared")}
    dev, dec = records["development"], records["declared"]
    found = differences(judge.without_run_times(dev), judge.without_run_times(dec))
    found = [f for f in found if not f.startswith((".world", ".resources"))]  # The world's name.
    out = dict(
        kind="development check (not a verdict): FR-5's declared world against its development "
             "world",
        arm=args.arm, path=args.path, horizon_s=args.horizon, window_s=list(args.window),
        start=dict(producer=extract["producer"], time_s=extract["time_s"],
                   extract_sha256=defs.start_sha256(extract)),
        runs={w: dict(admitted=r["admitted"], completed=r["completed"], refusal=r["refusal"],
                      steps=r["steps"], records=len(r["record_s"])) for w, r in records.items()},
        bitwise=not found, differences=found[:40],
        series_max_abs={name: judge.max_abs_difference(dev, dec, name)
                        for name in dev.get("series", {}) if dev["record_s"]},
    )
    args.out.write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    print(json.dumps(dict(arm=args.arm, bitwise=out["bitwise"], runs=out["runs"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
