"""FR-47 references' regeneration check (SPEC.md rules; protocol section 5, step 2).

    python check_regeneration.py --log-dir /mnt/workspaces/Cells/<run> \
        [--runs random:6,0:7,1:22,4242:23]

Runs the generator once per (PYTHONHASHSEED, CPU) pair, in parallel, each pinned by ``taskset`` to
its CPU with one BLAS thread, into its own directory under ``--log-dir``. Every file each run writes
must equal the committed ``references/`` file bitwise. The default runs are an unset seed and the
declared seeds 0, 1 and 4242 (fr47_writer.REGENERATION_HASH_SEEDS), each on a different light CPU.

Writes ``regeneration.json`` in ``--log-dir``: each run's seed, CPU, exit code and the SHA-256 of
every file, the committed files' SHA-256, and the verdict. The package must be a clean commit,
because the generator refuses otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUNS = "random:6,0:7,1:22,4242:23"


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _tree(directory):
    return {
        name: _sha(os.path.join(directory, name))
        for name in sorted(os.listdir(directory))
        if name.endswith(".json")
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--log-dir", required=True)
    ap.add_argument(
        "--runs", default=DEFAULT_RUNS, help="seed:cpu pairs; seed 'random' leaves it unset"
    )
    ap.add_argument("--against", default=os.path.join(HERE, "references"))
    args = ap.parse_args(argv)
    os.makedirs(args.log_dir, exist_ok=True)
    rev = subprocess.run(
        ["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    procs = []
    for item in args.runs.split(","):
        seed, cpu = item.split(":")
        out = os.path.join(args.log_dir, f"seed-{seed}-cpu-{cpu}")
        os.makedirs(out, exist_ok=True)
        env = dict(os.environ)
        env.pop("PYTHONHASHSEED", None)
        if seed != "random":
            env["PYTHONHASHSEED"] = seed
        for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
            env[var] = "1"
        log = open(os.path.join(args.log_dir, f"seed-{seed}-cpu-{cpu}.log"), "w")
        cmd = [
            "taskset",
            "-c",
            cpu,
            sys.executable,
            os.path.join(HERE, "generate_fr47_references.py"),
            "--out",
            out,
        ]
        procs.append(
            (
                seed,
                cpu,
                out,
                log,
                subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT),
            )
        )
    committed = _tree(args.against)
    runs = []
    for seed, cpu, out, log, proc in procs:
        code = proc.wait()
        log.close()
        files = _tree(out) if code == 0 else {}
        runs.append(
            {
                "PYTHONHASHSEED": seed,
                "cpu": int(cpu),
                "exit_code": code,
                "sha256": files,
                "equal_to_committed": code == 0 and files == committed,
            }
        )
    verdict = bool(committed) and all(r["equal_to_committed"] for r in runs)
    report = {
        "head": rev,
        "committed_dir": os.path.relpath(args.against, HERE),
        "committed_sha256": committed,
        "runs": runs,
        "bitwise_identical": verdict,
    }
    with open(os.path.join(args.log_dir, "regeneration.json"), "w") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")
    print(
        json.dumps(
            {
                "head": rev,
                "files": len(committed),
                "runs": [
                    (r["PYTHONHASHSEED"], r["cpu"], r["exit_code"], r["equal_to_committed"])
                    for r in runs
                ],
                "bitwise_identical": verdict,
            }
        )
    )
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
