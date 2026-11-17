"""FR-5's full-horizon world agreement: the acceptance reading (development evidence only).

    python -m validation.compartment_ph_engine.worlds_check COMPARISONS HORIZON_T HORIZON_R DT
        CHECK_JSON

COMPARISONS is the folder holding each arm's comparison, T.json and R.json (world_agreement.py
--compare: the arm's development world against its declared world). An arm passes only when both
worlds were admitted and completed, each ran the arm's full step count (HORIZON / DT) and record
count (one per second, both ends included), and every record is bitwise equal; a missing
comparison fails its arm. The reading goes to CHECK_JSON, a new file (an existing one is refused,
so a run folder's reading is never overwritten), with a one-line summary on stdout; the exit code
is 0 only when both arms pass.

Moved into the checkout from the lane's run folder at the lead's ruling of 16 November 2026 (the
copy that ran, fr45/pipeline/worlds_check.py, stays there as a frozen run input). The reading is
unchanged; the output path is now an argument. Standard library only.
"""

import argparse
import json
from pathlib import Path

KIND = "FR-5 world agreement, full horizon (development evidence, not a verdict)"
WORLDS = ["declared", "development"]


def arm_reading(comparison, horizon, dt):
    """One arm's reading from its comparison (world_agreement --compare's output)."""
    steps, records = round(horizon / dt), int(round(horizon)) + 1
    runs = comparison["runs"]
    ok = dict(both_worlds=sorted(runs) == WORLDS,
              both_admitted=all(r["admitted"] for r in runs.values()),
              both_completed=all(r["completed"] for r in runs.values()),
              full_steps=all(r["steps"] == steps for r in runs.values()),
              full_records=all(r["records"] == records for r in runs.values()),
              bitwise=comparison["bitwise"] is True)
    return dict(passed=all(ok.values()), **ok, expected_steps=steps, expected_records=records,
                runs=runs, horizon_s=comparison["horizon_s"], window_s=comparison["window_s"],
                start=comparison["start"], differences=comparison["differences"][:10])


def check(comparisons, horizon_t, horizon_r, dt):
    """The reading of both arms' comparisons in the folder `comparisons`."""
    out = dict(kind=KIND, arms={})
    for arm, horizon in (("T", horizon_t), ("R", horizon_r)):
        path = Path(comparisons) / f"{arm}.json"
        if not path.exists():
            out["arms"][arm] = dict(passed=False, why="no comparison written (see ARM.log)")
            continue
        out["arms"][arm] = arm_reading(json.loads(path.read_text()), horizon, dt)
    out["passed"] = all(a["passed"] for a in out["arms"].values())
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("comparisons", type=Path, help="the folder holding T.json and R.json")
    parser.add_argument("horizon_t", type=float, help="arm T's horizon (s)")
    parser.add_argument("horizon_r", type=float, help="arm R's horizon (s)")
    parser.add_argument("dt", type=float, help="the declared step (s)")
    parser.add_argument("check_json", type=Path, help="the reading to write (a new file)")
    args = parser.parse_args(argv)
    if args.check_json.exists():
        raise SystemExit(f"Refused: {args.check_json} exists (each reading writes its own)")
    out = check(args.comparisons, args.horizon_t, args.horizon_r, args.dt)
    args.check_json.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(passed=out["passed"],
                          arms={k: v["passed"] for k, v in out["arms"].items()})))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
