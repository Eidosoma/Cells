"""The format sample's runs on the engine (validation/fr45/spec/TABLE.md §12.1, §12.3 step 5): every run of the
sample's table, each in its own process through the driver, then the exporter's table of them.

Each run's world is its `inputs` in the sample. A run refused at parse holds null inputs, so its world is its
completing twin's with the cause the sample's README names; the harness refusal is the driver's time limit; the
plant runs take their honest twin's inputs and their plant's patch (validation/fr45/plants/); INVENTED-W1eq reads
its start from the sample's start file. `missing` holds INVENTED-W3p as the sample does; its honest run is made
apart (`extra`), for the plant rule's twin of INVENTED-W3p-P7.

Usage (PYTHONPATH at a snapshot, JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu):
  python -B -m validation.fr45.sample SAMPLE_DIR OUT --cpus 6,7
SAMPLE_DIR: the sample's folder (table/table.json, start_INVENTED-W1eq.json), read-only.
"""

import argparse
import copy
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PLANTS = {"P1": "p1", "P2": "p2", "P3": "p3", "P4": "p4", "P5": "p5", "P6": "p6", "P7": "p7", "P8": "p8", "P9": "p9"}
INVENTED_PLANTS = {"INVENTED-W1p-P3~check": "INVENTED_p3_dissipation", "INVENTED-W3p-P7~check": "INVENTED_p7_host"}
TWIN = {"W1p": "INVENTED-W1p", "W5": "INVENTED-W5", "W2": "INVENTED-W2", "W7": "INVENTED-W7"}
EXTRA = "INVENTED-W3p"  # In the sample's `missing`; made apart as INVENTED-W3p-P7's honest twin.


def jobs(sample):
    """[(run, job)] for every run of the sample's table, and the extra honest twin."""
    table = json.loads((sample / "table" / "table.json").read_text())
    runs = table["runs"]
    out = []
    for name, entry in runs.items():
        job = dict(run=name, inputs=entry["inputs"], plant=None, start=None, time_limit_step=None, judged=False)
        if name == "INVENTED-W1eq":
            job["start"] = json.loads((sample / "start_INVENTED-W1eq.json").read_text())
        elif name == "INVENTED-W2~harness":
            job["inputs"], job["time_limit_step"] = runs["INVENTED-W2"]["inputs"], 15
        elif name == "INVENTED-W3~definition":  # A second population on `plate` binding X1 (PROTOCOL:56).
            inputs = copy.deepcopy(runs["INVENTED-W3"]["inputs"])
            twin = next(p for p in inputs["populations"] if p["id"] == "plate_X1")
            inputs["populations"].append(dict(twin, id="plate_X1_second", initial_occupancy=0.03))
            inputs["multipliers"].append(dict(of="plate_X1_second", name="site_binding_multiplier", value=1.0))
            job["inputs"] = inputs
        elif name == "INVENTED-W6~domain":  # skin's initial occupancies 0.72 and 0.61, over 1 (PROTOCOL:57).
            inputs = copy.deepcopy(runs["INVENTED-W6"]["inputs"])
            for pop, theta in zip((p for p in inputs["populations"] if p["set"] == "skin"), (0.72, 0.61), strict=True):
                pop["initial_occupancy"] = theta
            job["inputs"] = inputs
        if entry["plant"] is not None:
            job["plant"] = INVENTED_PLANTS.get(name, PLANTS[entry["plant"]["id"]])
            shape = name.removeprefix("INVENTED-").split("-P")[0]
            if shape in TWIN:
                job["inputs"] = runs[TWIN[shape]]["inputs"]
        out.append((name, job))
    p7 = runs["INVENTED-W3p-P7"]["inputs"]
    out.append((EXTRA, dict(run=EXTRA, inputs=p7, plant=None, start=None, time_limit_step=None, judged=False)))
    return list(runs), out


def run_all(sample, out, cpus):
    names, todo = jobs(Path(sample))
    out = Path(out)
    (out / "jobs").mkdir(parents=True, exist_ok=True)
    free = list(cpus)
    log = out / "runs.log"

    def one(item):
        name, job = item
        cpu = free.pop()
        try:
            path = out / "jobs" / f"{name}.json"
            path.write_text(json.dumps(job, indent=1) + "\n")
            target = out / ("records-extra" if name == EXTRA else "records") / f"{name}.json"
            started = time.time()
            done = subprocess.run(["taskset", "-c", str(cpu), sys.executable, "-B", "-m", "validation.fr45.driver",
                                   "run", str(path), str(target)], capture_output=True, text=True, env=os.environ)  # fmt: skip
            (out / "logs").mkdir(exist_ok=True)
            (out / "logs" / f"{name}.log").write_text(done.stdout + done.stderr)
            with log.open("a") as f:
                f.write(f"{name}: exit {done.returncode}, {time.time() - started:.1f} s, CPU {cpu}\n")
            return name, done.returncode
        finally:
            free.append(cpu)

    with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
        results = list(pool.map(one, todo))
    import shutil

    from validation.fr45 import exporter

    every = out / "records-all"
    every.mkdir(exist_ok=True)
    for folder in (out / "records", out / "records-extra"):
        for record in folder.glob("*.json") if folder.exists() else ():
            shutil.copyfile(record, every / record.name)
    exporter.export(out / "records", out / "table", names, invented="INVENTED: the format sample's runs on the engine")
    exporter.export(every, out / "table-with-twin", [*names, EXTRA], invented="INVENTED: with INVENTED-W3p")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sample")
    parser.add_argument("out")
    parser.add_argument("--cpus", default="6,7")
    args = parser.parse_args(argv)
    results = run_all(args.sample, args.out, [int(c) for c in args.cpus.split(",")])
    bad = [n for n, rc in results if rc != 0]
    print(f"{len(results)} runs, driver failures: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
