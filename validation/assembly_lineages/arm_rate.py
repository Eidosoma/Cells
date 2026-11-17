"""The ensemble arm's event rate on CPU (GARD_DESIGN §7.3: the ensemble arm and a CPU measurement).

Measured, never presumed. One arm of the T2-02-like comparison world (worlds.py; the
pair-consistent form; matrix seed 20261117, founder seed 1117, arm seed 1), WORLDS worlds of
FISSIONS fissions each, run at each lane width in LANES and each chunk in CHUNKS. Each setting runs
the whole arm REPEATS times on its compiled programs (compiled by a first, unmeasured run); the
rate is the arm's committed events over the median wall time of its batches' run loops (the
runner's run_seconds: device calls, fission passes and per-chunk transfers; compile excluded).
Every setting's worlds must give the same events as the first setting's, or the measurement
stops: the rate of a different computation is not the same quantity.

    python -m validation.assembly_lineages.arm_rate freeze OUT
    cd OUT/source && PYTHONPATH=src:. taskset -c CPU \
        python -m validation.assembly_lineages.arm_rate run OUT

Pin it to one CPU that no other job uses (the timed lane), so the rate is one core's.
"""

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from statistics import median

from validation.assembly_lineages import probes

WORLDS, FISSIONS, SEED = 64, 20, 1
LANES = (1, 4, 16, 64)
CHUNKS = (32, 128)
REPEATS = 3


def the_arm(chunk):
    from cells.models.assembly_lineages import GARD_PAIR_CONSISTENT, arms

    data = probes.lineage_definition(GARD_PAIR_CONSISTENT, fissions=FISSIONS)
    data["execution"]["stream"]["seed"] = SEED
    data["execution"]["chunk_events"] = chunk
    return arms.parse({"definition": data, "worlds": WORLDS, "world_id_start": 0, "seed": SEED})


def measure(chunk, lanes):
    from cells.models.assembly_lineages import arms

    arm = the_arm(chunk)
    arms.run(arm, lanes)  # Compiles (cached per structure and lane count); not measured.
    seconds, events, channels = [], None, None
    for _ in range(REPEATS):
        runs = arms.run(arm, lanes)
        batches = {}
        for r in runs.values():  # One run_seconds per batch, shared by its worlds.
            batches[id(r.timings)] = r.timings
        seconds.append(
            sum(
                t["run_seconds"]
                for t in {
                    (t["run_seconds"], t["lanes"], t["chunks"]): t for t in batches.values()
                }.values()
            )
        )
        events = sum(r.timings["events"] for r in runs.values())
        channels = {w: r.trace["event_channel"].tobytes() for w, r in runs.items()}
    return {
        "chunk": chunk,
        "lanes": lanes,
        "worlds": WORLDS,
        "fissions": FISSIONS,
        "events": events,
        "run_seconds": seconds,
        "events_per_second": events / median(seconds),
    }, channels


def run(out):
    import cells
    from cells.core import blas_threads

    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    results, first = [], None
    for chunk in CHUNKS:
        for lanes in LANES:
            row, channels = measure(chunk, lanes)
            if first is None:
                first = channels
            elif channels != first:
                raise RuntimeError(f"chunk {chunk}, lanes {lanes}: other events than the first")
            results.append(row)
            print(json.dumps({k: row[k] for k in ("chunk", "lanes", "events_per_second")}))
    record = {
        "kind": "cells.assembly_lineages.arm_rate@1",
        "judged": False,
        "results": results,
        "same_events_in_every_setting": True,
        "scope": "the median over the repeats of the summed run_seconds of the arm's batches "
        "(device calls, fission passes and per-chunk transfers); compile excluded",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "cpu": platform.processor() or platform.machine(),
        "blas": blas_threads.record(),
        "source": probes._source(),
        "cells": cells.__file__,
        "python": sys.version,
    }
    (out / "arm_rate.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("freeze")
    frozen.add_argument("out", type=Path)
    running = commands.add_parser("run")
    running.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        probes.freeze(args.out)
    else:
        run(args.out)


if __name__ == "__main__":
    main()
