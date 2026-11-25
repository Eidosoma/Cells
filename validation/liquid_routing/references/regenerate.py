"""Show that the writer's files are byte-identical under other hash seeds, and record how they were made.

    python -B -P regenerate.py --out DIR --scratch SCRATCH --revision REV --seeds 1,271828

Runs `write_references.py` afresh into SCRATCH/seed-<n> for each seed, compares every file with DIR's, and writes
`SHA256SUMS` and `provenance.json` into DIR. `run_times.json` is the writer's own and is not compared. Nothing here names a
folder of this machine.
"""

import argparse
import decimal
import hashlib
import json
import os
import platform
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["inputs_invented.json", "reference_invented.json"] + [f"reference_arm{k}.json" for k in range(1, 7)]
CHECKED = FILES + ["component_tests.json", "mutation_tests.json", "self_check.json"]


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--revision", required=True, help="the spec revision that the reference files carry")
    parser.add_argument("--read-revision", help="a later spec revision that was read since (default: the same)")
    parser.add_argument("--seeds", default="1,271828")
    parser.add_argument("--own-seed", default="0")
    parser.add_argument("--skip-run", action="store_true", help="compare folders that are already written")
    arguments = parser.parse_args()
    seeds = arguments.seeds.split(",")
    identical, differing = {}, {}
    for seed in seeds:
        folder = os.path.join(arguments.scratch, f"seed-{seed}")
        if not arguments.skip_run:
            environment = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
            environment["PYTHONHASHSEED"] = seed
            os.makedirs(folder, exist_ok=True)
            subprocess.run([sys.executable, "-B", "-P", os.path.join(HERE, "write_references.py"), "--out", folder,
                            "--revision", arguments.revision], env=environment, check=True)
        differing[seed] = [name for name in FILES if sha(os.path.join(folder, name)) != sha(os.path.join(arguments.out, name))]
        identical[seed] = not differing[seed]
        print(f"seed {seed}: {'identical' if identical[seed] else 'DIFFERS ' + str(differing[seed])}", flush=True)
    spec = os.path.join(HERE, os.pardir, "spec")
    sources = sorted(name for name in os.listdir(HERE) if name.endswith(".py"))
    sources += sorted(os.path.join("lrrefs", name) for name in os.listdir(os.path.join(HERE, "lrrefs")) if name.endswith(".py"))
    provenance = {
        "kind": "liquid-routing references provenance, version 1",
        "command": "python -B -P write_references.py --out DIR --revision REV (PYTHONPATH empty)",
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "libmpdec": getattr(decimal, "__libmpdec_version__", "none"),
        "libraries": "the standard library only",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hash_seeds": {"own": arguments.own_seed, "others": seeds},
        "byte_identical_under_other_seeds": identical,
        "spec_revision": arguments.revision,
        "spec_revision_read_last": arguments.read_revision or arguments.revision,
        "spec_files_sha256": {name: sha(os.path.join(spec, name)) for name in sorted(os.listdir(spec))},
        "source_files_sha256": {name: sha(os.path.join(HERE, name)) for name in sources},
        "working_digits": {"propagators and closed forms": 110, "quadratures": 120, "a centred difference": 260},
        "published_digits": 40,
        "decimal_rounding": "ROUND_HALF_EVEN",
    }
    with open(os.path.join(arguments.out, "provenance.json"), "w", encoding="ascii") as handle:
        json.dump(provenance, handle, indent=1, sort_keys=True)
        handle.write("\n")
    present = [name for name in CHECKED + ["provenance.json"] if os.path.exists(os.path.join(arguments.out, name))]
    with open(os.path.join(arguments.out, "SHA256SUMS"), "w", encoding="ascii") as handle:
        for name in sorted(present):
            handle.write(f"{sha(os.path.join(arguments.out, name))}  {name}\n")
    sys.exit(0 if all(identical.values()) else 1)


if __name__ == "__main__":
    main()
