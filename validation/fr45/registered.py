"""FR-45's registered runs' inputs, and the parse-only passes the addenda copy (TABLE §3, §4, §4.1, §12.2, §14.1).

`inputs_for(run, expected, addendum)` is each run's entry of the expected-inputs file (a plant run its world's
honest run's, TABLE §8.1) with the host entities' values filled in: the host-entity addendum's once it exists, or,
for the parse-only passes that make it, the bath form's own (secreted_species_fixtures': each held bath and host
cell 1.0 pL, the wall's and the contact's areas and capacitances, each compartment at the bath's ion
composition). A marked trace is the binary64 product 1e-12 x its compartment's volume (TABLE §4.1).

`passes` runs `driver.py parse` for every registered honest run but W1eq, each in its own process, and
`addenda` copies by machine what the execution record and the host-entity addendum hold (TABLE §4, §14.1): W1eq
takes W1's, its start apart, and a plant run its honest run's.

Usage (PYTHONPATH at a snapshot, JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu):
  python -B -m validation.fr45.registered passes EXPECTED_JSON OUT --cpus 6,7
  python -B -m validation.fr45.registered addenda OUT
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

HOST_VOLUME_PL = 1.0  # The bath form's held bath and host cell (secreted_species_fixtures.world).
PARSED = ("W1", "W1p", "W2", "W3", "W3p", "W4-dt0.08", "W4-dt0.04", "W4-dt0.02", "W5", "W6", "W7", "W7s")
PLANTS = {"W1p-P1": "W1p", "W1p-P2": "W1p", "W1p-P3": "W1p", "W1p-P6": "W1p", "W1p-P8": "W1p", "W1p-P9": "W1p",
          "W5-P4": "W5", "W2-P5": "W2", "W7-P5": "W7", "W3p-P7": "W3p"}  # fmt: skip


def honest_of(run):
    """A run's honest run (TABLE §8.1): itself, or its plant's world's."""
    return PLANTS.get(run, run)


def inputs_for(run, expected, addendum=None):
    """The run's inputs (TABLE §4.1's shape) from its expected entry, the host values filled in."""
    honest = honest_of(run)
    inputs = copy.deepcopy(expected["runs"][honest])
    markers = expected["host"]["markers"]
    host = None if addendum is None else addendum["runs"]["W1" if honest == "W1eq" else honest]
    volumes = {} if host is None else {n["id"]: n["volume_pL"] for n in host["nodes"]}
    for node in inputs["nodes"]:
        if node["volume_pL"] == markers["volume"]:
            node["volume_pL"] = volumes.get(node["id"], HOST_VOLUME_PL)
    volume = {n["id"]: n["volume_pL"] for n in inputs["nodes"]}
    for entry in inputs["free_amounts"]:
        if entry["n_fmol"] == markers["trace"]:
            entry["n_fmol"] = 1e-12 * volume[entry["node"]]
    if inputs["host_values"] == markers["host_values"]:
        inputs["host_values"] = None if host is None else copy.deepcopy(host["host_values"])
    return inputs


def passes(expected_path, out, cpus):
    """Every registered honest run but W1eq through `driver.py parse`, each in its own process, one CPU each."""
    expected = json.loads(Path(expected_path).read_text())
    out = Path(out)
    (out / "jobs").mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    free = list(cpus)

    def one(run):
        cpu = free.pop()
        try:
            job = dict(run=run, inputs=inputs_for(run, expected), plant=None, start=None, time_limit_step=None)
            path = out / "jobs" / f"{run}.json"
            path.write_text(json.dumps(job, indent=1) + "\n")
            started = time.time()
            done = subprocess.run(["taskset", "-c", str(cpu), sys.executable, "-B", "-m", "validation.fr45.driver",
                                   "parse", str(path), str(out / "parsed" / f"{run}.json")], capture_output=True,
                                  text=True, env=os.environ)  # fmt: skip
            (out / "logs" / f"{run}.log").write_text(done.stdout + done.stderr)
            with (out / "passes.log").open("a") as f:
                f.write(f"{run}: exit {done.returncode}, {time.time() - started:.1f} s, CPU {cpu}\n")
            return run, done.returncode
        finally:
            free.append(cpu)

    with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
        return list(pool.map(one, PARSED))


# The execution block's declared keys the judge compares (TABLE §4, R5-1), and the driver's own record.
DECLARED = ("solver", "dt", "jit", "backend", "field_solver", "material_balance_atol_fmol")


def _named(value, names, path=""):
    """Every path in `value` whose string leaf names one of `names` (the run, its world, a record's path)."""
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            found += _named(v, names, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found += _named(v, names, f"{path}[{i}]")
    elif isinstance(value, str) and any(n in value for n in names):
        found.append(path)
    return found


def addenda(out):
    """The execution record and the host-entity values, copied by machine from the parse records (TABLE §4,
    §4.1, §14.1), with the paths of `definition` that name a run or its record (R5-4)."""
    out = Path(out)
    records = {run: json.loads((out / "parsed" / f"{run}.json").read_text()) for run in PARSED}
    refused = {run: r["refusal"] for run, r in records.items() if r["status"] != "parsed"}
    if refused:
        raise SystemExit(f"refused at parse: {refused}")
    execution, host, named = {}, {}, {}
    for run, r in records.items():
        block = r["definition"]["execution"]
        execution[run] = dict(execution=block, declared={k: block.get(k) for k in DECLARED},
                              energy_check="energy_check" in block, driver=dict(window_steps=1))  # fmt: skip
        echo = r["inputs"]
        host[run] = dict(nodes=[dict(id=n["id"], volume_pL=n["volume_pL"]) for n in echo["nodes"]
                                if not n["registered"]], host_values=echo["host_values"])  # fmt: skip
        names = {run, f"{run}.json", "records/", "INVENTED"}
        named[run] = _named(r["definition"], names)
    host["W1eq"] = copy.deepcopy(host["W1"])  # W1eq takes W1's (TABLE §4.1, E27).
    same = all(execution[run]["declared"] == execution["W1"]["declared"] for run in ("W1p",))
    sources = {json.dumps(r["source"], sort_keys=True) for r in records.values()}
    provenance = dict(made_from=sorted(str(out / "parsed" / f"{run}.json") for run in PARSED),
                      source=json.loads(next(iter(sources))) if len(sources) == 1 else "differs by run")  # fmt: skip
    record = dict(kind="fr45 execution record, version 1", runs=execution,
                  takes=dict(W1eq="W1, its start apart (TABLE §4; §9.2, WF5)",
                             plants="each its honest run's (TABLE §8.1)"),  # fmt: skip
                  excluded_paths=sorted({p for paths in named.values() for p in paths}),
                  W1p_declared_equal_W1=same, provenance=provenance)  # fmt: skip
    entities = dict(kind="fr45 host-entity addendum, version 1", runs=host,
                    takes=dict(W1eq="W1's, copied", plants="each its honest run's (TABLE §8.1)"),
                    provenance=provenance)  # fmt: skip
    (out / "execution_record.json").write_text(json.dumps(record, indent=1) + "\n")
    (out / "host_entities.json").write_text(json.dumps(entities, indent=1) + "\n")
    print(json.dumps(dict(runs=len(records), excluded_paths=record["excluded_paths"], named=named), indent=1))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("passes")
    p.add_argument("expected")
    p.add_argument("out")
    p.add_argument("--cpus", default="6,7")
    a = sub.add_parser("addenda")
    a.add_argument("out")
    args = parser.parse_args(argv)
    if args.command == "passes":
        results = passes(args.expected, args.out, [int(c) for c in args.cpus.split(",")])
        bad = [run for run, rc in results if rc]
        print(f"{len(results)} passes, driver failures: {bad}")
        return 1 if bad else 0
    return addenda(args.out)


if __name__ == "__main__":
    sys.exit(main())
