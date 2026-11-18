"""Development run (not judged): one T2-02-like lineage, both GARD forms, and its event rate.

G1's development check (GARD_DESIGN §7.3; D192): one lineage of the T2-02-like comparison world
(worlds.py), run once with each form of GARD's catalysis from one founder and one set of
streams, written as a pair of bundles (records.write_pair). The event rate is measured, never
presumed: each form's lineage is run REPEATS more times on the same compiled program, and the
rate is events per second of wall time on one lane, compile excluded.

    python -m validation.assembly_lineages.dev_lineage freeze OUT
        freezes the checkout's source (validation/source_snapshot.py) into OUT/source;
    cd OUT/source && PYTHONPATH=src python -m validation.assembly_lineages.dev_lineage run OUT
        runs from that snapshot, so run.json names the revision, and writes OUT/pair and
        OUT/rate.json.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
REPEATS = 3


def snapshot_files():
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        + ["--", "src/cells", "validation/assembly_lineages", "validation/source_snapshot.py"],
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout
    names = sorted({os.fsdecode(n) for n in listed.split(b"\0") if n})
    names = [n for n in names if (ROOT / n).is_file() and "__pycache__" not in n]
    return {name: name for name in names} | {"pyproject.toml": "pyproject.toml"}


def freeze(out):
    from validation import source_snapshot

    out = Path(out)
    record = source_snapshot.freeze(ROOT, out / "source", snapshot_files())
    print(json.dumps({"source": str(out / "source"), "git_revision": record["git_revision"]}))


def run(out, *, fissions, matrix_seed, founder_seed, seed):
    import cells
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages import (
        GARD_PAIR_CONSISTENT,
        GARD_SINGLE_EVENT,
        records,
        runner,
    )
    from validation.assembly_lineages import worlds

    out = Path(out)
    world = worlds.t2_02_like(matrix_seed, founder_seed)
    runs, rate = [], {}
    for law in (GARD_SINGLE_EVENT, GARD_PAIR_CONSISTENT):
        spec = parse_spec(worlds.definition(world, law, fissions=fissions, seed=seed))
        first = runner.run(spec).check()
        again = [runner.run(spec).check() for _ in range(REPEATS)]
        if any(
            r.trace["event_channel"].tolist() != first.trace["event_channel"].tolist()
            for r in again
        ):
            raise RuntimeError("A repeat changed the event sequence")
        seconds = [r.timings["run_seconds"] for r in again]
        rate[law] = {
            "events": first.timings["events"],
            "fissions": int(len(first.fissions["fission_time"])),
            "status": first.status,
            "compile_seconds": first.timings["compile_seconds"],
            "first_run_seconds": first.timings["run_seconds"],
            "repeat_run_seconds": seconds,
            "events_per_second_median": first.timings["events"] / median(seconds),
            "events_per_growth_mean": float(first.trace["events_per_growth"].mean()),
            "ledger": first.closure,
            "check": first.verdict,
            "world_report": first.world_report,
        }
        runs.append(first)
    entries = records.write_pair(out / "pair", runs, provenance={"operation": "development"})
    summary = {
        "kind": "cells.assembly_lineages.development_run@1",
        "judged": False,
        "world": records.world_record(runs[0].spec.model.world)["id"],
        "seeds": {"matrix": matrix_seed, "founder": founder_seed, "stream": seed},
        "fissions": fissions,
        "pair": entries,
        "rate": rate,
        "rate_scope": "one lane on one CPU, wall time of the runner's host loop and device "
        "calls (the event steps, fission passes and per-chunk transfers), compile excluded; the "
        "median of the repeats. Not in it: the host-side checks before the loop (the law's "
        "verdict, cached, and a driven law's report on the world's data, run each time)",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "cells": cells.__file__,
        "python": sys.version,
    }
    (out / "rate.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({law: v["events_per_second_median"] for law, v in rate.items()}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("freeze")
    frozen.add_argument("out", type=Path)
    running = commands.add_parser("run")
    running.add_argument("out", type=Path)
    running.add_argument("--fissions", type=int, default=100)
    running.add_argument("--matrix-seed", type=int, default=20261117)
    running.add_argument("--founder-seed", type=int, default=1117)
    running.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        freeze(args.out)
    else:
        run(
            args.out,
            fissions=args.fissions,
            matrix_seed=args.matrix_seed,
            founder_seed=args.founder_seed,
            seed=args.seed,
        )


if __name__ == "__main__":
    main()
