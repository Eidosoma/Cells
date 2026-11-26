"""Write the reference files: the invented set first, then one file per registered world.

    python -I write_references.py [--out DIR] [--workers N] [--invented-only] [--revision HASH]

The invented set is the writer's own test (SPEC section 8): the registered files are written only where
every check of the invented set passes.  A file's bytes are fixed by its values; the run times go in the
sidecar `run_times.json` alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import numpy  # noqa: E402
import scipy  # noqa: E402

from cowriter_refs import draws, invented, layout  # noqa: E402
from cowriter_refs.build import WorldSet  # noqa: E402

SPEC = HERE.parent / "spec"
WORLDS = ("W5", "W5-exact", "W6")


def code_revision():
    """The commit that last changed the references' code (the outputs left out)."""
    code = ["write_references.py", "cowriter_refs"]
    command = ["git", "-C", str(HERE), "log", "-1", "--format=%H", "--", *code]
    found = subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(HERE), "status", "--porcelain", "--", *code], capture_output=True, text=True, check=True
    ).stdout.strip()
    return (found or "uncommitted") + (" (modified)" if dirty else "")


def provenance(revision):
    return {
        "revision": revision,
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "sha256_of_this_file_excluded": True,
    }


def timed(call):
    key, function, argument = call
    start = time.perf_counter()
    value = function(argument)
    return key, value, time.perf_counter() - start


def read_table(drawn, pairs):
    """Each world's copies with u1 as doubles, and the number of entries that differ from LAWS section 6's rule."""
    tables, differ = {}, {}
    for name, world in drawn["worlds"].items():
        tables[name], differ[name] = [], []
        for entry in world["copies"]:
            u1, u2 = draws.copy_table(entry["seed"], entry["site_index"], pairs)
            if len(entry["u1"]) != pairs or len(entry["u2"]) != pairs:
                raise ValueError("the table does not hold the declared number of pairs")
            declared = entry["u1"] + entry["u2"]
            differ[name].append(sum(1 for a, b in zip(u1 + u2, declared, strict=True) if a.hex() != b))
            tables[name].append({"seed": entry["seed"], "u1": u1})
    return tables, differ


def world_sets(inputs, tables, workers, times):
    """Every world's tasks, run on `workers` processes."""
    sets = {name: WorldSet(inputs, name, tables[name]) for name in WORLDS}
    for name in WORLDS:
        if [entry["seed"] for entry in tables[name]] != inputs["worlds"][name]["seeds"]:
            raise ValueError("the draws are not those of the declared seeds")
    calls = [call for name in WORLDS for call in sets[name].tasks()]
    with ProcessPoolExecutor(workers) as pool:
        for key, value, seconds in pool.map(timed, calls):
            sets[key[1]].take(key, value)
            label = f"{key[0]} {key[1]}"
            times[label] = times.get(label, 0.0) + seconds
    for name in WORLDS:
        start = time.perf_counter()
        sets[name].finish()
        times[f"finish {name}"] = time.perf_counter() - start
    return sets


def failures(reference):
    return [
        check for entry in reference["copies"] for check in entry["checks"] if not check["passes"]
    ] + ([] if reference["draws_check"]["identical"] else [{"name": "draws_check"}])


def write(path, value):
    path.write_bytes(layout.dump(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_set(inputs, inputs_sha256, drawn, workers, source, times):
    tables, differ = read_table(drawn, inputs["draws"]["pairs_per_copy"])
    sets = world_sets(inputs, tables, workers, times)
    return {name: layout.reference(sets[name], inputs_sha256, differ[name], source) for name in WORLDS}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE / "out")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--invented-only", action="store_true")
    parser.add_argument("--revision", help="the code's revision, where the folder is not a Git checkout")
    arguments = parser.parse_args()
    out = arguments.out
    out.mkdir(parents=True, exist_ok=True)
    source = provenance(arguments.revision or code_revision())
    registered = json.loads((SPEC / "inputs.json").read_bytes())
    registered_draws = json.loads((SPEC / "draws.json").read_bytes())
    times = {"invented": {}, "registered": {}}

    start = time.perf_counter()
    made = invented.build_inputs(registered)
    shared = invented.equal_numbers(made, registered)
    if shared:
        raise SystemExit(f"the invented set shares numbers with the registered one: {shared}")
    write(out / "inputs_invented.json", made)
    write(out / "draws_invented.json", invented.build_draws(registered_draws))
    made = json.loads((out / "inputs_invented.json").read_bytes())
    digest = hashlib.sha256((out / "inputs_invented.json").read_bytes()).hexdigest()
    drawn = json.loads((out / "draws_invented.json").read_bytes())
    references = make_set(made, digest, drawn, arguments.workers, source, times["invented"])
    write(out / "reference_invented.json", references)
    times["invented"]["wall"] = time.perf_counter() - start
    failed = {name: failures(reference) for name, reference in references.items() if failures(reference)}
    for name, checks in failed.items():
        for check in checks:
            print(f"invented {name}: {check}", file=sys.stderr)
    if failed:
        (out / "run_times.json").write_bytes(layout.dump(times))
        raise SystemExit("a check of the invented set does not pass: the registered files are not written")

    if not arguments.invented_only:
        start = time.perf_counter()
        digest = hashlib.sha256((SPEC / "inputs.json").read_bytes()).hexdigest()
        references = make_set(registered, digest, registered_draws, arguments.workers, source, times["registered"])
        for name, reference in references.items():
            write(out / f"reference_{name}.json", reference)
        times["registered"]["wall"] = time.perf_counter() - start
        for name, reference in references.items():
            for check in failures(reference):
                print(f"registered {name}: {check}", file=sys.stderr)
                failed.setdefault(name, []).append(check)

    for path in sorted(out.glob("*.json")):
        if path.name != "run_times.json":
            print(hashlib.sha256(path.read_bytes()).hexdigest(), "", path.name)
    times["machine"] = {
        "platform": platform.platform(),
        "workers": arguments.workers,
        "hashseed": "random (-I)" if sys.flags.ignore_environment else os.environ.get("PYTHONHASHSEED", "random"),
        "blas_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
    }
    (out / "run_times.json").write_bytes(layout.dump(times))
    if failed:
        raise SystemExit("a check of the registered set does not pass")


if __name__ == "__main__":
    main()
