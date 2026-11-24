"""Bitwise regeneration of FR-45's reference files under other hash seeds and on another core.

  python validation/fr45/references/regeneration_check.py --spec-root <copy>/spec \
      --spec-sums <copy>/SHA256SUMS-...txt --spec-label <tag> --root <new dir> --cpus 6,7

It also runs the first, 50-digit profile once and records which written values differ from
the 70-digit ones (paths and relative differences only).

Runs run_references.py four times, one after another, each with BLAS pinned to one thread:
hash seeds 0, 1 and 2 (the writer's declared regeneration seeds) and seed 0 again, the first
two on the first CPU and the last two on the second (the two may be one CPU: each run has its
own numbered directory). Every output except run.log must be
byte-identical across the runs. The invented format sample is written under the same four
seeds and cores and must equal the committed file byte for byte. regeneration.json records
each run's digests (computed at run time) and the verdicts. The checkout must be clean, since
run_references.py refuses otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _diff(a, b, name, path, out):
    """Record where two parsed files differ: the path and, for numbers, the relative size."""
    if isinstance(a, dict) and isinstance(b, dict) and list(a) == list(b):
        for k in a:
            _diff(a[k], b[k], name, path + [k], out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (u, v) in enumerate(zip(a, b, strict=True)):
            _diff(u, v, name, path + [i], out)
    elif a != b:
        rel = None
        if isinstance(a, float) and isinstance(b, float) and a != 0:
            rel = abs(a - b) / abs(a)
        out.append(
            {"file": name, "path": "/".join(str(x) for x in path), "relative_difference": rel}
        )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec-root", required=True)
    ap.add_argument("--spec-sums", required=True)
    ap.add_argument("--spec-label", required=True)
    ap.add_argument("--root", required=True, type=pathlib.Path)
    ap.add_argument("--cpus", default="6,7")
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args(argv)
    sys.path.insert(0, str(HERE))
    import fr45ref_writer as WR

    cpu_a, cpu_b = args.cpus.split(",")
    seeds = list(WR.REGENERATION_HASH_SEEDS)
    plan = [(seeds[0], cpu_a), (seeds[1], cpu_a), (seeds[2], cpu_b), (seeds[0], cpu_b)]
    if args.root.exists() and any(args.root.iterdir()):
        raise SystemExit(f"refused: {args.root} is not empty")
    args.root.mkdir(parents=True, exist_ok=True)
    runs = []
    for idx, (seed, cpu) in enumerate(plan, start=1):
        out = args.root / f"run{idx}-seed{seed}-cpu{cpu}"
        env = dict(
            os.environ,
            PYTHONHASHSEED=str(seed),
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
        )
        cmd = [
            "taskset",
            "-c",
            cpu,
            args.python,
            str(HERE / "run_references.py"),
            "--spec-root",
            args.spec_root,
            "--spec-sums",
            args.spec_sums,
            "--spec-label",
            args.spec_label,
            "--out",
            str(out),
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        (args.root / f"run{idx}-seed{seed}-cpu{cpu}.stdout").write_text(
            proc.stdout + proc.stderr, encoding="utf-8"
        )
        if proc.returncode != 0:
            raise SystemExit(f"run seed={seed} cpu={cpu} failed:\n{proc.stdout}\n{proc.stderr}")
        digests = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.iterdir())
            if p.name != "run.log"
        }
        prov = json.loads((out / "reference_W1.json").read_text(encoding="utf-8"))["provenance"]
        runs.append(
            {
                "hash_seed": seed,
                "cpu": int(cpu),
                "sha256": digests,
                "references_revision": prov["references_revision"],
                "tree_clean": prov["tree_clean"],
            }
        )
        print(f"seed {seed} cpu {cpu}: {len(digests)} files", flush=True)
    # the invented format sample: the same seeds and cores, against the committed file
    committed = HERE / "format_sample_INVENTED.json"
    committed_digest = hashlib.sha256(committed.read_bytes()).hexdigest()
    sample_runs = []
    for idx, (seed, cpu) in enumerate(plan, start=1):
        out = args.root / f"sample{idx}-seed{seed}-cpu{cpu}"
        env = dict(
            os.environ,
            PYTHONHASHSEED=str(seed),
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
        )
        cmd = [
            "taskset",
            "-c",
            cpu,
            args.python,
            str(HERE / "run_references.py"),
            "--spec-root",
            args.spec_root,
            "--spec-sums",
            args.spec_sums,
            "--spec-label",
            args.spec_label,
            "--out",
            str(out),
            "--sample",
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"sample seed={seed} cpu={cpu} failed:\n{proc.stdout}\n{proc.stderr}")
        digest = hashlib.sha256((out / "format_sample_INVENTED.json").read_bytes()).hexdigest()
        sample_runs.append({"hash_seed": seed, "cpu": int(cpu), "sha256": digest})
        print(
            f"sample seed {seed} cpu {cpu}: equals committed {digest == committed_digest}",
            flush=True,
        )
    sample_ok = all(r["sha256"] == committed_digest for r in sample_runs)
    # the written values at the first, 50-digit profile, against the 70-digit ones: paths and
    # relative differences only
    seed, cpu = plan[0]
    out50 = args.root / "profile50"
    env = dict(
        os.environ,
        PYTHONHASHSEED=str(seed),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    cmd = [
        "taskset",
        "-c",
        cpu,
        args.python,
        str(HERE / "run_references.py"),
        "--spec-root",
        args.spec_root,
        "--spec-sums",
        args.spec_sums,
        "--spec-label",
        args.spec_label,
        "--out",
        str(out50),
        "--profile",
        "reference50",
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"the 50-digit run failed:\n{proc.stdout}\n{proc.stderr}")
    primary = args.root / f"run1-seed{plan[0][0]}-cpu{plan[0][1]}"
    differing = []
    for p in sorted(primary.glob("reference_*.json")):
        a = json.loads(p.read_text(encoding="utf-8"))
        b = json.loads((out50 / p.name).read_text(encoding="utf-8"))
        a.pop("provenance")
        b.pop("provenance")
        _diff(a, b, p.name, [], differing)
    precision = {
        "compared": "every value of the reference files but provenance",
        "differing_count": len(differing),
        "differing": differing,
    }
    first = runs[0]["sha256"]
    identical = all(r["sha256"] == first for r in runs)
    same_rev = len({r["references_revision"] for r in runs}) == 1 and all(
        r["tree_clean"] for r in runs
    )
    record = {
        "schema": "fr45-reference-regeneration/1",
        "compared": sorted(first),
        "excluded": ["run.log (seed, CPU and timings)"],
        "runs": runs,
        "bitwise_identical": identical,
        "one_clean_revision": same_rev,
        "precision_50_vs_70_digits": precision,
        "format_sample": {
            "committed_sha256": committed_digest,
            "runs": sample_runs,
            "bitwise_identical_to_committed": sample_ok,
        },
    }
    (args.root / "regeneration.json").write_text(
        json.dumps(record, indent=1) + "\n", encoding="utf-8"
    )
    print(
        f"bitwise identical: {identical}; one clean revision: {same_rev}; "
        f"format sample identical to the committed file: {sample_ok}"
    )
    return 0 if identical and same_rev and sample_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
