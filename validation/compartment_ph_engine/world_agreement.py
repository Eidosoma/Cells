"""Development evidence (not a verdict): FR-5's declared world (FR-1's compartment operator
included, the composite) against its development world (without it), record for record. The
operator adds identity and refusals only (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.1, §3.4.3), so
the two must be bitwise equal, as FR-4's were over 900 s.

    python -m validation.compartment_ph_engine.world_agreement START_JSON ARM OUT_JSON
        [--horizon S] [--window T0 T1] [--dt S] [--path vector|host] [--world WORLD]
    python -m validation.compartment_ph_engine.world_agreement --compare DEVELOPMENT_JSON
        DECLARED_JSON OUT_JSON

One arm (T or R) of definitions.fr5_world from the start extract, its window and horizon as
fr5_quick_check moves them (defaults 10 s and 2 to 6 s), through engine_records.run in each world.
Reported: each run's admission, completion, refusal and steps, and the paths where the two records
differ (the judge's compare: every leaf bit for bit, run times apart), with every series' and
amount row's largest difference.

Without --world both worlds run in this process, one after the other. With --world (development or
declared) only that world runs, and OUT_JSON holds its records (JSON keeps every bit of a float),
so the two worlds can run as two units at once; --compare then reads the two records files, checks
that they are one arm's two worlds of the same definition, and writes the same comparison.
"""

import argparse
import json
from pathlib import Path

from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine import engine_records
from validation.compartment_ph_engine.fr5_quick_check import arm
from validation.tissue import compartment_ph_judge as judge
from validation.tissue.compartment_ph_qualification import plain
from validation.tissue.regulated_availability_judge import differences

WORLDS = ("development", "declared")
RECORDS_KIND = "FR-5 world-agreement records (development evidence): one world of one arm"
# What a records file's two worlds must share for --compare (the run itself apart).
SHARED = ("arm", "path", "horizon_s", "window_s", "dt_s", "start", "definition_sha256")


def comparison(meta, dev, dec):
    """The two worlds' records compared: every leaf bit for bit, run times and the world's own
    name apart."""
    found = differences(judge.without_run_times(dev), judge.without_run_times(dec))
    found = [f for f in found if not f.startswith((".world", ".resources"))]  # The world's name.
    records = {"development": dev, "declared": dec}
    return dict(
        kind="development check (not a verdict): FR-5's declared world against its development "
             "world",
        **{k: meta[k] for k in ("arm", "path", "horizon_s", "window_s", "start")},
        runs={w: dict(admitted=r["admitted"], completed=r["completed"], refusal=r["refusal"],
                      steps=r["steps"], records=len(r["record_s"])) for w, r in records.items()},
        bitwise=not found, differences=found[:40],
        series_max_abs={name: judge.max_abs_difference(dev, dec, name)
                        for name in dev.get("series", {}) if dev["record_s"]},
    )


def compare_files(dev_path, dec_path):
    """The comparison of two records files written with --world."""
    files = {w: json.loads(Path(p).read_text()) for w, p in zip(WORLDS, (dev_path, dec_path),
                                                               strict=True)}
    for world, data in files.items():
        if data.get("kind") != RECORDS_KIND or data.get("world") != world:
            raise SystemExit(f"Refused: {world} records expected, not {data.get('world')!r} "
                             f"({data.get('kind')!r})")
    dev, dec = files["development"], files["declared"]
    unlike = [k for k in SHARED if dev.get(k) != dec.get(k)]
    if unlike:
        raise SystemExit(f"Refused: the two files are not one arm's two worlds ({unlike} differ)")
    out = comparison(dev, dev["records"], dec["records"])
    out["files"] = dict(development=str(dev_path), declared=str(dec_path))
    out["definition_sha256"] = dev["definition_sha256"]
    return out


def main(argv=None):
    if argv is None:
        import sys

        argv = sys.argv[1:]
    if argv[:1] == ["--compare"]:
        parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
        parser.add_argument("--compare", nargs=2, type=Path, metavar=("DEVELOPMENT", "DECLARED"),
                            required=True)
        parser.add_argument("out", type=Path)
        args = parser.parse_args(argv)
        out = compare_files(*args.compare)
        args.out.write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
        print(json.dumps(dict(arm=out["arm"], bitwise=out["bitwise"], runs=out["runs"])))
        return 0
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("start", type=Path)
    parser.add_argument("arm", choices=("T", "R"))
    parser.add_argument("out", type=Path)
    parser.add_argument("--horizon", type=float, default=10.0)
    parser.add_argument("--window", type=float, nargs=2, default=(2.0, 6.0))
    parser.add_argument("--dt", type=float, default=None)
    parser.add_argument("--path", choices=engine_records.PATHS, default="vector")
    parser.add_argument("--world", choices=WORLDS, default=None,
                        help="run this world alone and write its records (then --compare)")
    args = parser.parse_args(argv)
    extract = defs.read_start(args.start)
    definition = defs.fr5_world(arm(args.arm, extract, args.horizon, args.window), dt_s=args.dt,
                               start=extract)
    meta = dict(arm=args.arm, path=args.path, horizon_s=args.horizon, window_s=list(args.window),
                dt_s=args.dt,
                start=dict(producer=extract["producer"], time_s=extract["time_s"],
                           extract_sha256=defs.start_sha256(extract)),
                definition_sha256=defs.canonical_sha256(definition))
    if args.world is not None:
        records = plain(engine_records.run(definition, path=args.path, world=args.world))
        out = dict(kind=RECORDS_KIND, world=args.world, **meta, records=records)
        args.out.write_text(json.dumps(out, allow_nan=True) + "\n")
        print(json.dumps(dict(arm=args.arm, world=args.world, admitted=records["admitted"],
                              completed=records["completed"], steps=records["steps"])))
        return 0
    records = {world: engine_records.run(definition, path=args.path, world=world)
               for world in WORLDS}
    out = comparison(meta, records["development"], records["declared"])
    args.out.write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    print(json.dumps(dict(arm=args.arm, bitwise=out["bitwise"], runs=out["runs"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
