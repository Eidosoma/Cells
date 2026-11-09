"""Measure per-file test cost and run fast test tiers.

The full suite is far too slow for a routine gate (hundreds of heavy files), so
files are timed individually and grouped into tiers:

  measure  run each test file once, with a per-file wall cap, recording duration,
           outcome and counts to a JSON file (written incrementally)
  tiers    group measured files: tier 1 (< 20 s), tier 2 (< cap), tier 3 (cap hit)
  run      run every file of the given tiers and compare outcomes with the record

Example:
  python scripts/test_tiers.py measure --out RUN_DIR --cpus 4,5,6,7 --cap 90
  python scripts/test_tiers.py tiers --measured RUN_DIR/measured.json --out tests/test_tiers.json
  python scripts/test_tiers.py run --tiers tests/test_tiers.json --tier 1 \
      --out RUN_DIR --cpus 4,5,6,7
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTS = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected)")


def _git(*args):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _provenance():
    extra = {}
    try:
        revision = _git("rev-parse", "HEAD")
        dirty = bool(_git("status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.CalledProcessError):  # immutable snapshot without .git
        snapshot = json.loads((ROOT / "SNAPSHOT.json").read_text())
        revision = snapshot["git_revision"]
        if "dirty" in snapshot:
            dirty = snapshot["dirty"]
        else:  # validation/source_snapshot.py: the selected files' Git status and patch
            dirty = bool(snapshot["selected_status_porcelain_v1_z"])
            extra["patch_sha256"] = snapshot["patch_sha256"]
    return {
        "git_revision": revision,
        "dirty": dirty,
        **extra,
        "root": str(ROOT),
        "python": sys.executable,
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _test_files():
    return sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").rglob("test_*.py"))


def _run_file(path, cpu, cap, log_dir):
    """One test file under the standard gate environment.

    Scientific code is float64 (JAX_ENABLE_X64), and tests that write outputs or
    component evidence get their own directories under the run, never shared paths.
    """
    slug = path.replace("/", "__")
    outputs = log_dir.parent / "outputs" / slug
    evidence = log_dir.parent / "evidence" / slug
    outputs.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        PYTHONPATH=str(ROOT / "src"),
        CUDA_VISIBLE_DEVICES="",
        JAX_ENABLE_X64="1",
        CELLS_OUTPUT_ROOT=str(outputs),
        CELLS_COMPONENT_EVIDENCE=str(evidence),
    )
    log = log_dir / (slug + ".log")
    cmd = [
        "taskset",
        "-c",
        str(cpu),
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "--continue-on-collection-errors",
        path,
    ]
    start = time.monotonic()
    with log.open("w") as out:
        proc = subprocess.Popen(
            cmd, cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            code = proc.wait(timeout=cap)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, 9)
            proc.wait()
            code, timed_out = None, True
    tail = log.read_text(errors="replace")[-2000:]
    counts = {}
    last = [line for line in tail.splitlines() if " in " in line and COUNTS.search(line)]
    for number, kind in COUNTS.findall(last[-1] if last else ""):
        counts[kind.rstrip("s") if kind.startswith("error") else kind] = int(number)
    return {
        "file": path,
        "seconds": round(time.monotonic() - start, 2),
        "exit_code": code,
        "timed_out": timed_out,
        "counts": counts,
        "log": str(log),
    }


def _parallel(files, cpus, cap, out_dir, record_path, header):
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    results, free = [], list(cpus)

    def task(path):
        cpu = free.pop()
        try:
            return _run_file(path, cpu, cap, log_dir)
        finally:
            free.append(cpu)

    with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
        for row in pool.map(task, files):
            results.append(row)
            record_path.write_text(json.dumps({**header, "files": results}, indent=1) + "\n")
    return results


def measure(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = _test_files()
    if args.only:
        doc = json.loads(Path(args.only).read_text())
        chosen = {r["file"] for t in args.only_tiers for r in doc["tiers"][str(t)]}
        files = [f for f in files if f in chosen]
    header = {
        "kind": "cells.test_file_costs@1",
        "provenance": _provenance(),
        "cap_seconds": args.cap,
        "cpus": args.cpus,
        "file_count": len(files),
    }
    _parallel(files, args.cpus, args.cap, out, out / "measured.json", header)
    print(out / "measured.json")


def tiers(args):
    # Later measurements override earlier ones per file (e.g. a re-measured subset).
    records = [json.loads(Path(m).read_text()) for m in args.measured]
    latest, sources, provenance = {}, [], []
    if args.base:
        # Keep an existing tiers record (whose paths may have been edited, e.g. after
        # test files moved) and override only re-measured files.
        base = json.loads(Path(args.base).read_text())
        for tier, rows in base["tiers"].items():
            for row in rows:
                latest[row["file"]] = {**row, "timed_out": tier == "3"}
        sources, provenance = list(base["measured"]), list(base["measured_provenance"])
    for record in records:
        for row in record["files"]:
            latest[row["file"]] = row
    existing = set(_test_files())
    dropped = sorted(f for f in latest if f not in existing)
    for name in dropped:
        del latest[name]
    if dropped:
        print("dropped (no longer in tests/):", dropped)
    measured = {
        "sources": sources + [str(m) for m in args.measured],
        "provenance": provenance + [r["provenance"] for r in records],
        "cap_seconds": records[-1]["cap_seconds"],
    }
    groups = {"1": [], "2": [], "3": []}
    for row in latest.values():
        tier = "3" if row["timed_out"] else ("1" if row["seconds"] < args.fast else "2")
        groups[tier].append(
            {
                "file": row["file"],
                "seconds": row["seconds"],
                "exit_code": row["exit_code"],
                "counts": row["counts"],
            }
        )
    doc = {
        "kind": "cells.test_tiers@1",
        "measured": measured["sources"],
        "measured_provenance": measured["provenance"],
        "fast_seconds": args.fast,
        "cap_seconds": measured["cap_seconds"],
        "tiers": {k: sorted(v, key=lambda r: r["file"]) for k, v in groups.items()},
        "note": "Tier 3 files exceeded the cap; run them deliberately, not as a gate. "
        "exit_code/counts are the measured outcome, so pre-existing failures "
        "are visible.",
    }
    Path(args.out).write_text(json.dumps(doc, indent=1) + "\n")
    print({k: len(v) for k, v in groups.items()})


def run(args):
    doc = json.loads(Path(args.tiers).read_text())
    wanted = [r for t in args.tier for r in doc["tiers"][str(t)]]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    header = {
        "kind": "cells.test_tier_run@1",
        "provenance": _provenance(),
        "tiers": args.tier,
        "cap_seconds": args.cap,
    }
    results = _parallel(
        [r["file"] for r in wanted], args.cpus, args.cap, out, out / "run.json", header
    )
    before = {r["file"]: r for r in wanted}
    changed = [
        r
        for r in results
        if (r["exit_code"], r["counts"].get("failed", 0), r["counts"].get("error", 0))
        != (
            before[r["file"]]["exit_code"],
            before[r["file"]]["counts"].get("failed", 0),
            before[r["file"]]["counts"].get("error", 0),
        )
    ]
    summary = {
        "files": len(results),
        "changed_vs_record": [
            {
                "file": r["file"],
                "now": [r["exit_code"], r["counts"]],
                "recorded": [before[r["file"]]["exit_code"], before[r["file"]]["counts"]],
            }
            for r in changed
        ],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({"files": len(results), "changed": len(changed)}))
    return 1 if changed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    cpus = lambda s: [int(c) for c in s.split(",")]  # noqa: E731
    m = sub.add_parser("measure")
    m.add_argument("--out", required=True)
    m.add_argument("--cpus", type=cpus, default=[4, 5, 6, 7])
    m.add_argument("--cap", type=float, default=90.0)
    m.add_argument("--only", help="tiers JSON restricting which files to measure")
    m.add_argument("--only-tiers", type=int, nargs="+", default=[1, 2])
    t = sub.add_parser("tiers")
    t.add_argument("--measured", required=True, nargs="+")
    t.add_argument("--base", help="existing tiers JSON to keep, overriding re-measured files")
    t.add_argument("--out", required=True)
    t.add_argument("--fast", type=float, default=20.0)
    r = sub.add_parser("run")
    r.add_argument("--tiers", required=True)
    r.add_argument("--tier", type=int, nargs="+", default=[1])
    r.add_argument("--out", required=True)
    r.add_argument("--cpus", type=cpus, default=[4, 5, 6, 7])
    r.add_argument("--cap", type=float, default=300.0)
    args = parser.parse_args(argv)
    return {"measure": measure, "tiers": tiers, "run": run}[args.command](args) or 0


if __name__ == "__main__":
    sys.exit(main())
