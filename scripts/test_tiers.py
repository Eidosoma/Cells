"""Measure per-file test cost and run fast test tiers.

The full suite is far too slow for a routine gate (hundreds of heavy files), so
files are timed individually and grouped into tiers:

  measure  run each test file once, with a per-file wall cap, recording duration,
           outcome and counts to a JSON file (written incrementally)
  tiers    group measured files: tier 1 (< 20 s), tier 2 (< cap), tier 3 (cap hit)
  fold     a landing's measured rows onto the current record at landing time (D222): each
           measured file's row replaces its row in place, or is inserted at its sorted place,
           in the tier its time gives; every other row is kept as it stands, in its order;
           the measurements' sources and provenance are appended. Refused, with nothing
           written, when a row would be dropped (its file has left tests/), when a measured
           file is not in tests/, or when a measured row failed (exit code, failures, errors).
           Run it in the tree that holds the landing's test files (fold reads tests/ beside
           itself), on main's record: at a landing, merge without committing, take main's
           tests/test_tiers.json (git checkout --ours), fold the landing's measured.json files
           (later ones win per file), and commit the merge with the folded record
  merge    the three-way fold of a merge, when the branch's measurements are not at hand: the
           branch's row delta against the merge base (rows it added, changed or removed) applied
           to main's record, main's order kept and the branch's new rows inserted at their sorted
           places; the branch's new measured sources and provenance appended. Refused, with
           nothing written, when both sides changed the same row differently (a clash) or when
           they changed another key differently
  run      run every file of the given tiers and compare outcomes with the record:
           a file is changed when its exit code, failed or error count differs from
           its row, its passed count falls below the row's or its skipped count rises
           above it (tests silently lost to collection or a skipif); a passed count
           above the row's is reported in summary.json's count_increases (a stale
           row to re-measure), not changed. With --scope-map DIR (the nightly run only,
           D229), each file's processes also record what they read of the tree, into
           DIR/<file> (scripts/gates/scope_inject; scripts/gates/scope.py builds the map).
           With --trace DIR as well (D358), strace also writes the opens and processes of each
           file into DIR/<file>, as scope.py's check on the recorder; where strace cannot
           trace (absent, or the run is traced already), the run goes on without it and its
           record says why

JAX's persistent compilation cache (D321 R1): every test process runs with it disabled
(JAX_ENABLE_COMPILATION_CACHE=false, no cache folder), whatever the caller's environment, since tier
membership is decided by seconds and a warm cache moves files across tiers (measured warm on 20
November 2026, 77 of 189 tier-2 files fell under 20 s). measure always runs cold and marks its record
"jax_compilation_cache": "disabled"; fold and tiers refuse a measurement without that marker
(--pre-marker-ok takes one made before UNMARKED_UNTIL, when none could run warm). Only run takes
--jax-cache FOLDER, for checks whose outcomes count and whose seconds do not (the cache
qualification's arms, and gates once D321 step 2 is ruled in); its record names the folder.

Tier 3 (D187): its rows hold no outcome (they hit the 90 s measuring cap), so each
landing's final tier-3 table is frozen per test ID in tests/tier3_record.json, and a
later tier-3 run is compared with it instead of re-running old code:
  collect  the test IDs of a finished run's files, in collection order, from the tree the
           run ran on (its run.json's root), written beside the run
  freeze   tier 3's record from finished run folders (later folders win per file): per
           file its status, counts and seconds, per test ID its outcome and, for a
           failing test, its normalized error lines
  diff     finished run folders against the record, per test ID; only what changed is
           reported. Blocking (exit 1): a new failure, a changed error, a removed test, a
           test now skipped, a new timeout, a signal ending (no verdict), a collection
           error, a log that does not align with its collected IDs. Reported only: a new
           pass, a newly reached or added test, a test no longer reached, a file that now
           completes, and a file time beyond --factor (and --min-seconds)
One reader serves freeze and diff: pytest -q prints one progress character per test in
collection order, so a file's log is read against its collected IDs, and error lines are
normalized for the run's own paths (root, run folder, interpreter, pytest's tmp, home) and
addresses. The -q logs carry file wall times only, so time is compared per file.

Example:
  python scripts/test_tiers.py measure --out RUN_DIR --cpus 4,5,6,7 --cap 90
  python scripts/test_tiers.py tiers --measured RUN_DIR/measured.json --out tests/test_tiers.json
  python scripts/test_tiers.py fold --record tests/test_tiers.json \
      --measured LANDING/measure/measured.json --out tests/test_tiers.json
  python scripts/test_tiers.py merge --base BASE.json --ours BRANCH.json --theirs MAIN.json \
      --out tests/test_tiers.json
  python scripts/test_tiers.py run --tiers tests/test_tiers.json --tier 1 \
      --out RUN_DIR --cpus 4,5,6,7
  python scripts/test_tiers.py run --tiers tests/test_tiers.json --tier 3 \
      --out RUN_DIR --cpus 4,5,6,7 --cap 1800
  python scripts/test_tiers.py collect --run RUN_DIR --cpu 4
  python scripts/test_tiers.py diff --record tests/tier3_record.json --run RUN_DIR \
      --out RUN_DIR/diff.json
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


def _repository():
    """The repository the tool's tree belongs to (its common Git directory's parent: the main
    checkout, also for a worktree inside it), or None for an immutable snapshot without .git."""
    try:
        common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    except (OSError, subprocess.CalledProcessError):
        return None
    return common.parent


def recorded_root(root, repository):
    """A run's tree as its record names it: relative to the repository when the tree is the
    repository or a worktree inside it ("." for the repository), so a record kept in the public
    repository carries no home path; a tree outside it (a snapshot) keeps its absolute path."""
    if repository is not None:
        try:
            return str(Path(root).resolve().relative_to(Path(repository).resolve()))
        except ValueError:
            pass
    return str(root)


def _provenance():
    extra = {}
    try:
        revision = _git("rev-parse", "HEAD")
        # Untracked files count (D259): measure globs tests/, so an untracked test file is
        # measured, and it may import an untracked source under src/, validation/ or scripts/.
        dirty = bool(_git("status", "--porcelain", "--untracked-files=all", "--", "src", "tests",
                          "validation", "scripts", "pyproject.toml"))
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
        "root": recorded_root(ROOT, _repository()),
        "python": sys.executable,
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _test_files():
    return sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").rglob("test_*.py"))


CACHE_ENV = ("JAX_COMPILATION_CACHE_DIR", "JAX_PERSISTENT_CACHE_MIN_COMPILE_TIME_SECS",
             "JAX_PERSISTENT_CACHE_MIN_ENTRY_SIZE_BYTES", "JAX_COMPILATION_CACHE_MAX_SIZE",
             "CELLS_JAX_CACHE")
COLD = "disabled"  # The cold marker: a record's "jax_compilation_cache" when the cache was off.
# Before this marker existed (D321, 23 November 2026), the tier runner had no way to run warm and no
# unit could opt in, so an unmarked measurement made before this time was cold. fold and tiers take
# one only with --pre-marker-ok; any later unmarked measurement is refused.
UNMARKED_UNTIL = "2026-11-24T12:00:00+00:00"


def cache_environment(env, jax_cache=None):
    """ENV with JAX's persistent compilation cache disabled (the default: tier seconds are cold,
    D321 R1), or, for a run given --jax-cache, pointed at that folder with the qualified settings
    (every compile written). A caller's own cache settings never reach a test process either way."""
    env = {k: v for k, v in env.items() if k not in CACHE_ENV}
    if jax_cache is None:
        env["JAX_ENABLE_COMPILATION_CACHE"] = "false"
    else:
        env.update(JAX_ENABLE_COMPILATION_CACHE="true", JAX_COMPILATION_CACHE_DIR=str(jax_cache),
                   JAX_PERSISTENT_CACHE_MIN_COMPILE_TIME_SECS="0",
                   JAX_PERSISTENT_CACHE_MIN_ENTRY_SIZE_BYTES="0")
    return env


# strace for the scope map's check (D358): the opens that succeed (a folder is listed only through its
# own), with the path the kernel opened (-y), and the processes. -D keeps the test process this
# runner's own child, so a process that outlives it does not hold the run up; --seccomp-bpf stops it
# at these calls alone.
STRACE = ("strace", "-D", "-ff", "-y", "-z", "-q", "--seccomp-bpf", "-s", "200", "-e", "signal=!SIGCHLD", "-e",
          "trace=open,openat,openat2,creat,execve,execveat,clone,clone3,fork,vfork,open_by_handle_at,"
          "io_uring_setup")


def trace_refused():
    """Why strace cannot trace here, or None."""
    try:
        done = subprocess.run(["strace", "-f", "-qq", "--seccomp-bpf", "-o", os.devnull, "true"],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"strace: {type(error).__name__}"
    return None if done.returncode == 0 else f"strace: {done.stderr.strip()[-200:] or done.returncode}"


def _await_trace(folder, seconds=2.0):
    """strace ends just after the last process it follows, so this waits until every trace has its
    closing line. A process that outlives its test file is not waited for: its trace is not whole."""
    end, open_logs = time.monotonic() + seconds, None
    while open_logs is None or (open_logs and time.monotonic() < end):
        if open_logs:
            time.sleep(0.02)
        open_logs = []
        for log in folder.glob("t.*"):
            with log.open("rb") as stream:
                stream.seek(max(0, os.fstat(stream.fileno()).st_size - 120))
                if b"\n+++ " not in b"\n" + stream.read():
                    open_logs.append(log)


def _run_file(path, cpu, cap, log_dir, scope=None, jax_cache=None, trace=None):
    """One test file under the standard gate environment.

    Scientific code is float64 (JAX_ENABLE_X64), and tests that write outputs or
    component evidence get their own directories under the run, never shared paths.
    The tiers are CPU-only by definition: no GPU is visible and JAX's platform is the
    CPU (JAX_PLATFORMS, which some tests assert), whatever the caller's environment.
    JAX's persistent compilation cache is disabled unless the run names one (cache_environment).
    """
    slug = path.replace("/", "__")
    outputs = log_dir.parent / "outputs" / slug
    evidence = log_dir.parent / "evidence" / slug
    outputs.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    env = cache_environment(dict(
        os.environ,
        PYTHONPATH=str(ROOT / "src"),
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="1",
        CELLS_OUTPUT_ROOT=str(outputs),
        CELLS_COMPONENT_EVIDENCE=str(evidence),
    ), jax_cache)
    if scope:  # The scope map's recorder (sitecustomize), in this file's processes only.
        env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "scripts" / "gates" / "scope_inject"),
                                             env["PYTHONPATH"]])
        env.update(CELLS_SCOPE_LOG=str(Path(scope) / slug), CELLS_SCOPE_ROOT=str(ROOT))
    log = log_dir / (slug + ".log")
    tracer = []
    if trace:
        folder = Path(trace) / slug
        folder.mkdir(parents=True, exist_ok=True)
        tracer = [*STRACE, "-o", str(folder / "t")]
    cmd = [
        "taskset",
        "-c",
        str(cpu),
        *tracer,
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
    seconds = round(time.monotonic() - start, 2)
    if tracer:
        _await_trace(folder)
    tail = log.read_text(errors="replace")[-2000:]
    counts = {}
    last = [line for line in tail.splitlines() if " in " in line and COUNTS.search(line)]
    for number, kind in COUNTS.findall(last[-1] if last else ""):
        counts[kind.rstrip("s") if kind.startswith("error") else kind] = int(number)
    return {
        "file": path,
        "seconds": seconds,
        "exit_code": code,
        "timed_out": timed_out,
        "counts": counts,
        "log": str(log),
    }


def _parallel(files, cpus, cap, out_dir, record_path, header, scope=None, jax_cache=None, trace=None):
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    results, free = [], list(cpus)

    def task(path):
        cpu = free.pop()
        try:
            return _run_file(path, cpu, cap, log_dir, scope, jax_cache, trace)
        finally:
            free.append(cpu)

    with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
        for row in pool.map(task, files):
            results.append(row)
            record_path.write_text(json.dumps({**header, "files": results}, indent=1) + "\n")
    return results


def only_files(doc, only_tiers, files):
    """The files an only-list selects from `files`, in their order. A tier the list does not hold
    selects nothing (D222: an only-list without a "2" key raised KeyError under the default
    --only-tiers 1 2). A listed file that is not a test file is refused, since it would be measured
    as nothing."""
    chosen = {r["file"] for t in only_tiers for r in doc["tiers"].get(str(t), [])}
    unknown = sorted(chosen - set(files))
    if unknown:
        raise SystemExit(f"--only lists files that are not test files under tests/: {unknown}")
    return [f for f in files if f in chosen]


def measure(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = _test_files()
    if args.only:
        files = only_files(json.loads(Path(args.only).read_text()), args.only_tiers, files)
    header = {
        "kind": "cells.test_file_costs@1",
        "provenance": _provenance(),
        "cap_seconds": args.cap,
        "cpus": args.cpus,
        "file_count": len(files),
        "jax_compilation_cache": COLD,  # Always: measure has no way to run warm (D321 R1).
    }
    _parallel(files, args.cpus, args.cap, out, out / "measured.json", header)
    print(out / "measured.json")


def require_cold(records, sources, pre_marker_ok=False):
    """Refuse (SystemExit) a measurement whose seconds may be warm (D321 R1): only a record marked
    cold places a row by its seconds. An unmarked record made before UNMARKED_UNTIL, when no
    measurement could run warm, passes with pre_marker_ok."""
    for record, source in zip(records, sources, strict=True):
        mark = record.get("jax_compilation_cache")
        if mark == COLD:
            continue
        utc = record.get("provenance", {}).get("utc")
        if mark is None and pre_marker_ok and utc and utc < UNMARKED_UNTIL:
            continue
        why = (f"it was measured with the compilation cache {mark!r}" if mark is not None else
               "it has no cold marker (jax_compilation_cache), so its seconds may be warm")
        raise SystemExit(f"refused: the measurement {source}: {why}. Tier seconds are measured with "
                         f"the cache disabled (D321 R1): measure again with a scripts/test_tiers.py "
                         f"that writes the marker" + ("" if pre_marker_ok or mark is not None else
                         f", or pass --pre-marker-ok for a measurement made before {UNMARKED_UNTIL}"))


def tiers(args):
    # Later measurements override earlier ones per file (e.g. a re-measured subset).
    records = [json.loads(Path(m).read_text()) for m in args.measured]
    require_cold(records, args.measured, getattr(args, "pre_marker_ok", False))
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


def tier_of(row, fast):
    return "3" if row.get("timed_out") else ("1" if row["seconds"] < fast else "2")


def fold_rows(record, measured_records, sources, files):
    """The record with the measured rows folded in (module docstring: fold), or SystemExit.

    record: the current tier record; measured_records: measure's records, later ones win per
    file; sources: their paths; files: the test files under tests/ now."""
    fast = record["fast_seconds"]
    where = {r["file"]: t for t in record["tiers"] for r in record["tiers"][t]}
    gone = sorted(f for f in where if f not in set(files))
    if gone:
        raise SystemExit(f"fold refused: the record's rows {gone} name files no longer under "
                         "tests/, and fold never drops a row (resolve them by hand)")
    latest = {}
    for m in measured_records:
        for row in m["files"]:
            latest[row["file"]] = row
    unknown = sorted(f for f in latest if f not in set(files))
    if unknown:
        raise SystemExit(f"fold refused: measured files {unknown} are not under tests/")
    # A row that reached the cap (timed_out, exit code None) is not a failure: it goes to tier 3,
    # as tier_of places it. A failed or erroring count still refuses, timed out or not.
    failing = sorted(f for f, r in latest.items()
                     if (r["exit_code"] != 0 and not r.get("timed_out"))
                     or r["counts"].get("failed") or r["counts"].get("error"))
    if failing:
        raise SystemExit(f"fold refused: measured rows {failing} did not pass")
    out = json.loads(json.dumps(record))
    for name, row in sorted(latest.items()):
        new = {k: row[k] for k in ("file", "seconds", "exit_code", "counts")}
        tier = tier_of(row, fast)
        rows = out["tiers"][where[name]] if name in where else None
        if rows is not None and where[name] == tier:
            rows[next(i for i, r in enumerate(rows) if r["file"] == name)] = new
            continue
        if rows is not None:
            rows[:] = [r for r in rows if r["file"] != name]
        target = out["tiers"].setdefault(tier, [])
        target.insert(next((i for i, r in enumerate(target) if r["file"] > name), len(target)),
                      new)
    for path, m in zip(sources, measured_records, strict=True):
        if str(path) not in out["measured"]:
            out["measured"].append(str(path))
            out["measured_provenance"].append(m["provenance"])
    kept = {r["file"] for t in out["tiers"] for r in out["tiers"][t]}
    assert set(where) <= kept, "fold dropped a row"
    for tier, rows in record["tiers"].items():  # Every unmeasured row as it stood, in its order.
        assert [r for r in rows if r["file"] not in latest] == [
            r for r in out["tiers"][tier] if r["file"] not in latest], tier
    return out


def merge_rows(base, ours, theirs):
    """theirs with ours' row delta against base (module docstring: merge), or SystemExit."""
    def rows(doc):
        return {r["file"]: (t, r) for t in doc["tiers"] for r in doc["tiers"][t]}

    b, o, t = rows(base), rows(ours), rows(theirs)
    clashes = []
    for name in sorted(set(b) | set(o)):
        mine, was = o.get(name), b.get(name)
        if mine == was:
            continue  # Unchanged on the branch.
        now = t.get(name)
        if now != was and now != mine:
            clashes.append(name)  # Both sides changed it, differently.
    for key in sorted(set(base) | set(ours) | set(theirs)):
        if key in ("tiers", "measured", "measured_provenance"):
            continue
        if ours.get(key) != base.get(key) and theirs.get(key) not in (base.get(key), ours.get(key)):
            clashes.append(f"key {key}")
    if clashes:
        raise SystemExit(f"merge refused: both sides changed {clashes} differently")
    out = json.loads(json.dumps(theirs))
    for key in set(ours) - {"tiers", "measured", "measured_provenance"}:
        if ours[key] != base.get(key):
            out[key] = ours[key]
    for name in sorted(set(b) | set(o)):
        mine, was = o.get(name), b.get(name)
        if mine == was or t.get(name) == mine:
            continue  # Unchanged on the branch, or the same change on both sides.
        where = next((k for k, rs in out["tiers"].items() if any(r["file"] == name for r in rs)),
                     None)  # Theirs' place, which is the base's (no clash).
        if mine is not None and where == mine[0]:  # Changed within its tier: in place.
            rs = out["tiers"][where]
            rs[next(i for i, r in enumerate(rs) if r["file"] == name)] = mine[1]
            continue
        if where is not None:  # Removed on the branch, or moved to another tier.
            out["tiers"][where] = [r for r in out["tiers"][where] if r["file"] != name]
        if mine is not None:  # Added, or moved: at its sorted place in its tier.
            target = out["tiers"].setdefault(mine[0], [])
            target.insert(next((i for i, r in enumerate(target) if r["file"] > name),
                               len(target)), mine[1])
    for key in ("measured", "measured_provenance"):
        for item in ours[key]:
            if item not in base[key] and item not in out[key]:
                out[key].append(item)
    return out


def merge(args):
    docs = [json.loads(Path(p).read_text()) for p in (args.base, args.ours, args.theirs)]
    out = merge_rows(*docs)
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print({t: len(v) for t, v in out["tiers"].items()})


def fold(args):
    record = json.loads(Path(args.record).read_text())
    measured = [json.loads(Path(m).read_text()) for m in args.measured]
    require_cold(measured, args.measured, getattr(args, "pre_marker_ok", False))
    out = fold_rows(record, measured, args.measured, _test_files())
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print({t: len(v) for t, v in out["tiers"].items()})


def run(args):
    doc = json.loads(Path(args.tiers).read_text())
    wanted = [r for t in args.tier for r in doc["tiers"][str(t)]]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jax_cache = getattr(args, "jax_cache", None)  # Callers that build args by hand may omit it.
    if jax_cache is not None:
        jax_cache = Path(jax_cache).resolve()
    header = {
        "kind": "cells.test_tier_run@1",
        "provenance": _provenance(),
        "tiers": args.tier,
        "cap_seconds": args.cap,
        "jax_compilation_cache": str(jax_cache) if jax_cache else COLD,
    }
    scope, trace = getattr(args, "scope_map", None), getattr(args, "trace", None)
    if scope:
        header["scope_map"] = str(Path(scope).resolve())
    if trace:
        refused = trace_refused()
        header["trace"] = None if refused else str(Path(trace).resolve())
        if refused:
            header["trace_refused"], trace = refused, None
    results = _parallel(
        [r["file"] for r in wanted], args.cpus, args.cap, out, out / "run.json", header,
        scope and Path(scope).resolve(), jax_cache, trace and Path(trace).resolve(),
    )
    changed, increases = compare_with_record(results, {r["file"]: r for r in wanted})
    summary = {
        "files": len(results),
        "changed_vs_record": changed,
        "count_increases": increases,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(
        json.dumps(
            {"files": len(results), "changed": len(changed), "count_increases": len(increases)}
        )
    )
    return 1 if changed else 0


def compare_with_record(results, record):
    """(changed, count_increases) of a run's file results against their tier rows.

    A file is changed when its exit code, failed or error count differs from its row, when
    its passed count falls below the row's, or when its skipped count rises above it: tests
    that silently stop being collected or start skipping change the file, as a failure
    does. A passed count above the row's is not a change (tests were added since the row
    was measured); such files are listed in count_increases so their rows get re-measured.
    Each entry is {"file", "now": [exit_code, counts], "recorded": [...]}; a changed one
    also names why.
    """
    changed, increases = [], []
    for r in results:
        row = record[r["file"]]
        now, was = r["counts"], row["counts"]
        why = []
        if (r["exit_code"], now.get("failed", 0), now.get("error", 0)) != (
            row["exit_code"],
            was.get("failed", 0),
            was.get("error", 0),
        ):
            why.append("exit code, failed or error count differs")
        if now.get("passed", 0) < was.get("passed", 0):
            why.append("passed below the record")
        if now.get("skipped", 0) > was.get("skipped", 0):
            why.append("skipped above the record")
        entry = {
            "file": r["file"],
            "now": [r["exit_code"], now],
            "recorded": [row["exit_code"], was],
        }
        if why:
            changed.append({**entry, "why": why})
        if now.get("passed", 0) > was.get("passed", 0):
            increases.append(entry)
    return changed, increases


# ------------------------------------------------------------------ tier 3's record (D187)

RECORD_KIND = "cells.tier3_record@1"
IDS_KIND = "cells.test_ids@1"
DIFF_KIND = "cells.tier3_diff@1"
PROGRESS_LINE = re.compile(r"^([.FEsxX]+)\s*(?:\[\s*\d+%\])?\s*$")
SECTION = re.compile(r"^_+ (\S.*?) _+$")
BANNER = re.compile(r"^=+ (.*?) =+$")
WORD = {".": "passed", "F": "failed", "E": "error", "s": "skipped", "x": "xfailed", "X": "xpassed"}
FAILING, PASSING, SKIPPING = ("failed", "error"), ("passed", "xpassed"), ("skipped", "xfailed")
PHASES = ("ERROR at setup of ", "ERROR at teardown of ")
ERROR_LINES, ERROR_WIDTH = 12, 300  # per failing test: its first E lines, each cut to this width
BLOCKING = (
    "new failure",
    "changed error",
    "removed",
    "now skipped",
    "new timeout",
    "no verdict",
    "collection error",
    "unaligned",
)


def file_status(row):
    """A file's ending: pass, pass-skips, pass-empty, fail, timeout, signal N or no exit."""
    if row.get("timed_out"):
        return "timeout"
    code, counts = row.get("exit_code"), row.get("counts", {})
    if code is None:
        return "no exit"
    if code < 0:
        return f"signal {code}"
    if code != 0 or counts.get("failed", 0) or counts.get("error", 0):
        return "fail"
    if not counts.get("passed", 0):
        return "pass-empty"
    return "pass-skips" if counts.get("skipped", 0) else "pass"


def _completed(status):
    return status in ("pass", "pass-skips", "pass-empty", "fail")


def _unreached(status):
    if status == "timeout":
        return "not run (cap)"
    return "not run (signal)" if status.startswith("signal") else "not run"


def normalizer(paths):
    """A function normalizing one error line for comparison across runs.

    paths: (path, token) pairs, e.g. the run's tree as <root> and its folder as <run>: each
    path becomes its token, the longest first. Then pytest's tmp folders, home folders and
    hexadecimal addresses are replaced, and the line is cut to ERROR_WIDTH characters.
    """
    subs = sorted(
        ((str(p).rstrip("/"), t) for p, t in paths if p and str(p).rstrip("/")),
        key=lambda pair: -len(pair[0]),
    )
    patterns = [(re.compile(re.escape(p)), t) for p, t in subs] + [
        (re.compile(r"/tmp/pytest-of-[^/\s]+/pytest-\d+"), "<tmp>"),
        (re.compile(r"/home/[^/\s'\"]+"), "<home>"),
        (re.compile(r"0x[0-9a-fA-F]+"), "0x?"),
    ]

    def norm(line):
        for pattern, token in patterns:
            line = pattern.sub(token, line)
        return line[:ERROR_WIDTH]

    return norm


def _progress(lines):
    """The first block of pytest -q progress lines, as one string of outcome characters."""
    out, started = [], False
    for line in lines:
        m = PROGRESS_LINE.match(line)
        if m:
            started = True
            out.append(m[1])
        elif started:
            break
    return "".join(out)


def _sections(lines, norm):
    """{section title: its normalized E lines} of the log's FAILURES and ERRORS parts."""
    out, title, inside = {}, None, False
    for line in lines:
        m = BANNER.match(line)
        if m:
            inside, title = m[1] in ("FAILURES", "ERRORS"), None
            continue
        if not inside:
            continue
        m = SECTION.match(line)
        if m and not re.fullmatch(r"[_ ]+", m[1]):
            title = m[1]
            out.setdefault(title, [])
        elif title is not None and line.startswith("E   "):
            out[title].append(norm(line.rstrip()))
    return out


def _summary(lines, path, ids):
    """({test ID: FAILED or ERROR, with its message}, collection error?) of the short summary.

    Matched against the collected IDs (a parametrized ID may hold spaces or " - "); a failing
    node that matches none is kept under its own text, so it shows as not aligning.
    """
    prefix, found, collection = path + "::", {}, False
    known = sorted(ids, key=len, reverse=True)
    for line in lines:
        for word in ("FAILED ", "ERROR "):
            if not line.startswith(word):
                continue
            rest = line[len(word) :]
            if rest == path or rest.startswith(path + " - "):
                collection = True
            elif rest.startswith(prefix):
                node = rest[len(prefix) :]
                test = next((i for i in known if node == i or node.startswith(i + " - ")), None)
                if test is None:
                    test = node.split(" - ", 1)[0]
                found[test] = (word.strip(), node[len(test) + 3 :] if node != test else "")
    return found, collection


def read_file(row, ids, norm):
    """One file's reading: its log (row["log"]) read against its collected test IDs.

    pytest -q prints one progress character per test in collection order. A completed file
    aligns when it has one character per collected ID and its F and E positions are exactly
    the short summary's FAILED and ERROR IDs; a file stopped at the cap or by a signal aligns
    as a prefix, its unreached tests "not run (cap)" or "not run (signal)". A file that does
    not align keeps the summary's failing IDs and "unknown" for every other test, with
    aligned False: it is reported, never guessed. A failing test carries its normalized E
    lines (its failure sections, else its summary message); one stopped before the summary
    carries none, and its error is not compared.
    """
    status = file_status(row)
    try:
        lines = Path(row["log"]).read_text(errors="replace").splitlines()
    except (KeyError, OSError, TypeError):
        lines = []
    chars = _progress(lines)
    failing, collection = _summary(lines, row["file"], ids)
    sections = _sections(lines, norm)
    heads = {i.replace("::", "."): i for i in ids}
    errors, collection_lines = {}, []
    for title, found in sections.items():
        if title.startswith("ERROR collecting "):
            collection, collection_lines = True, collection_lines + found
            continue
        name = next((title[len(p) :] for p in PHASES if title.startswith(p)), title)
        if name in heads:
            errors.setdefault(heads[name], []).extend(found)
    n, why = len(ids), None
    if _completed(status) and len(chars) != n:
        why = f"{len(chars)} progress characters for {n} collected tests"
    elif not _completed(status) and len(chars) > n:
        why = f"{len(chars)} progress characters for {n} collected tests (stopped)"
    elif _completed(status):
        at = {ids[i] for i, c in enumerate(chars) if c in "FE"}
        if at != set(failing):
            why = "F/E positions differ from the summary's FAILED/ERROR IDs"
    if why is None:
        outcomes = [WORD[c] for c in chars] + [_unreached(status)] * (n - len(chars))
    else:
        outcomes = ["unknown"] * n
        for k, test in enumerate(ids):
            if test in failing:
                outcomes[k] = "failed" if failing[test][0] == "FAILED" else "error"
    tests = []
    for test, outcome in zip(ids, outcomes, strict=True):
        if outcome not in FAILING:
            tests.append([test, outcome])
        elif test in errors:
            tests.append([test, outcome, errors[test][:ERROR_LINES]])
        elif test in failing:
            tests.append([test, outcome, [norm(failing[test][1])] if failing[test][1] else []])
        else:
            tests.append([test, outcome])
    reading = {
        "status": status,
        "exit_code": row.get("exit_code"),
        "timed_out": bool(row.get("timed_out")),
        "counts": row.get("counts", {}),
        "seconds": row.get("seconds"),
        "collected": n,
        "reached": min(len(chars), n),
        "aligned": why is None,
    }
    if why is not None:
        reading["unaligned"] = why
        reading["unmatched_failing"] = sorted(set(failing) - set(ids))
    if collection:
        reading["collection_error"] = collection_lines[:ERROR_LINES]
    reading["tests"] = tests
    return reading


def _tree_revision(root):
    snapshot = Path(root) / "SNAPSHOT.json"
    if snapshot.is_file():
        return json.loads(snapshot.read_text()).get("git_revision")
    if (Path(root) / ".git").exists():
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
    return None


def _run_doc(run_dir):
    """A finished run folder's run.json (the tier runner's, or an attribution runner's)."""
    doc = json.loads((Path(run_dir) / "run.json").read_text())
    provenance = doc.get("provenance") or {}
    root = provenance.get("root") or doc.get("target")
    if root and not Path(root).is_absolute():  # Recorded relative to the repository.
        root = str((_repository() or ROOT) / root)
    python = provenance.get("python") or doc.get("python")
    return doc, root, python


def _collect_once(root, files, cpu, scratch):
    env = cache_environment(dict(
        os.environ,
        PYTHONPATH=str(Path(root) / "src"),
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="1",
        CELLS_OUTPUT_ROOT=str(scratch / "outputs"),
        CELLS_COMPONENT_EVIDENCE=str(scratch / "evidence"),
    ))
    cmd = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    cmd += ["--continue-on-collection-errors", "--collect-only", *files]
    if cpu is not None:
        cmd = ["taskset", "-c", str(cpu), *cmd]
    proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
    ids = {f: [] for f in files}
    for line in proc.stdout.splitlines():
        path, sep, test = line.partition("::")
        if sep and path in ids:
            ids[path].append(test)
    return ids, proc.stdout


def collect(args):
    """The test IDs of finished runs' files in their own tree, in collection order.

    Collect on the tree the runs ran on, as it was: right after a run on a checkout. A tree
    whose revision differs from the one a run recorded is refused.
    """
    roots, files, revisions = set(), [], set()
    for run_dir in args.run:
        doc, root, _ = _run_doc(run_dir)
        roots.add(str(Path(root).resolve()))
        revisions.add(
            (doc.get("provenance") or {}).get("git_revision") or doc.get("target_revision")
        )
        files += [r["file"] for r in doc["files"] if not r.get("absent") and not r.get("not_run")]
    if len(roots) != 1:
        sys.exit(f"the runs ran on different trees: {sorted(roots)}")
    root, files = roots.pop(), sorted(set(files))
    now = _tree_revision(root)
    if now and revisions - {None, now}:
        sys.exit(f"{root} is at {now}, but the runs recorded {sorted(revisions - {None})}")
    out = Path(args.out) if args.out else Path(args.run[0]) / "collected.json"
    if out.exists():
        sys.exit(f"refused: {out} exists")
    scratch = out.parent / (out.stem + "-scratch")
    scratch.mkdir(parents=True, exist_ok=True)
    ids, text = _collect_once(root, files, args.cpu, scratch)
    logs = {"all": text}
    for f in [f for f in files if not ids[f]]:  # Collected alone, as the run ran it.
        alone, logs[f] = _collect_once(root, [f], args.cpu, scratch)
        ids[f] = alone[f]
    record = {
        "kind": IDS_KIND,
        "root": root,
        "root_revision": _tree_revision(root),
        "runs": [str(Path(r).resolve()) for r in args.run],
        "python": sys.executable,
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": ids,
    }
    out.write_text(json.dumps(record, indent=1) + "\n")
    (out.parent / (out.stem + ".log")).write_text(
        "".join(f"== {k}\n{v}\n" for k, v in logs.items())
    )
    empty = [f for f in files if not ids[f]]
    print(json.dumps({"files": len(files), "tests": sum(map(len, ids.values())), "empty": empty}))
    print(out)


def _listings(paths):
    """{resolved tree: {file: [test IDs]}} of collect's listings."""
    out = {}
    for path in paths:
        doc = json.loads(Path(path).read_text())
        out.setdefault(str(Path(doc["root"]).resolve()), {}).update(doc["files"])
    return out


def readings(run_dirs, listing_paths):
    """({file: reading}, {run folder: cap}) of finished run folders, later folders winning.

    Each folder's files are read against the listing collected from that folder's own tree,
    with that folder's paths normalized; rows that record no run (absent, not run) are skipped.
    """
    listings, out, caps = _listings(listing_paths), {}, {}
    for run_dir in run_dirs:
        doc, root, python = _run_doc(run_dir)
        tree = listings.get(str(Path(root).resolve()))
        if tree is None:
            sys.exit(f"no collected test IDs for {root} (run {run_dir}): run collect on it")
        interpreter = Path(python).parents[1] if python else None
        norm = normalizer(((run_dir, "<run>"), (root, "<root>"), (interpreter, "<python>")))
        caps[str(run_dir)] = doc.get("cap_seconds")
        for row in doc["files"]:
            if row.get("absent") or row.get("not_run"):
                continue
            if row["file"] not in tree:
                sys.exit(f"{row['file']} is not in the listing collected from {root}")
            reading = read_file(row, tree[row["file"]], norm)
            out[row["file"]] = {"run": str(run_dir), "log": row.get("log"), **reading}
    return out, caps


def write_record(path, doc):
    """The record as JSON with one line per test, so a refreeze diffs readably in Git."""
    head = json.dumps({k: v for k, v in doc.items() if k != "files"}, indent=1)
    parts = []
    for name, row in doc["files"].items():
        meta = json.dumps({k: v for k, v in row.items() if k != "tests"}, ensure_ascii=False)
        tests = ",\n".join("   " + json.dumps(t, ensure_ascii=False) for t in row["tests"])
        body = meta[:-1] + ', "tests": [' + (f"\n{tests}\n  " if tests else "") + "]}"
        parts.append(f"  {json.dumps(name)}: {body}")
    text = head[:-2] + ',\n "files": {\n' + ",\n".join(parts) + "\n }\n}\n"
    if json.loads(text) != json.loads(json.dumps(doc)):
        raise AssertionError("the record's layout does not round-trip")
    Path(path).write_text(text)


def freeze(args):
    """Tier 3's record from finished run folders: per test ID, with normalized errors."""
    out = Path(args.out)
    if out.exists() and not args.replace:
        sys.exit(f"refused: {out} exists (--replace to refreeze)")
    found, caps = readings(args.run, args.collected)
    notes = json.loads(Path(args.notes).read_text()) if args.notes else {}
    if len(set(caps.values())) != 1:
        sys.exit(f"the run folders' caps differ: {caps}")
    doc = {
        "kind": RECORD_KIND,
        **notes.get("header", {}),
        "frozen_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cap_seconds": next(iter(caps.values())),
        "runs": [str(r) for r in args.run],
        "collected": [str(c) for c in args.collected],
        "time": "file wall seconds only: the -q logs carry no per-test times",
        "outcomes": sorted(set(WORD.values()))
        + ["not run (cap)", "not run (signal)", "not run", "unknown"],
        "files": {f: {**found[f], **notes.get("files", {}).get(f, {})} for f in sorted(found)},
    }
    write_record(out, doc)
    tiers = json.loads(Path(args.tiers).read_text())["tiers"]["3"] if args.tiers else None
    report = {
        "files": len(found),
        "tests": sum(r["collected"] for r in found.values()),
        "unaligned": sorted(f for f, r in found.items() if not r["aligned"]),
    }
    if tiers is not None:
        rows = {r["file"] for r in tiers}
        report["tier3_rows_not_frozen"] = sorted(rows - set(found))
        report["frozen_not_tier3_rows"] = sorted(set(found) - rows)
    print(json.dumps(report))
    return 1 if report["unaligned"] else 0


def _test_change(was, now):
    """The kind of change between two [id, outcome(, errors)] entries (None: unchanged)."""
    a = was[1] if was else "absent"
    b = now[1] if now else "absent"
    if a == b:
        if b in FAILING and len(was) > 2 and len(now) > 2 and was[2] != now[2]:
            return "changed error"
        return None
    if b in FAILING:
        return "changed error" if a in FAILING else "new failure"
    if b == "absent":
        return "removed"
    if a == "absent":
        return "added"
    if "unknown" in (a, b):
        return None  # Not failing by the summary; the file's "unaligned" entry stands for it.
    if b.startswith("not run"):
        return None if a.startswith("not run") else "not reached"
    if a.startswith("not run"):
        return "newly reached"
    if b in SKIPPING and (a in PASSING or a in FAILING):
        return "now skipped"
    if b in PASSING and (a in FAILING or a in SKIPPING):
        return "new pass"
    return "changed outcome"


def diff_readings(record, found, factor=2.0, min_seconds=60.0):
    """(blocking, reported, unchanged files) of run readings against tier 3's record.

    Per test ID: a test failing now that did not fail (or was not reached, or is new) is a
    new failure; failing in both with other error lines (or failed <-> error) a changed
    error; a test that disappears is removed; a passing or failing test now skipped is now
    skipped. Per file: completed -> timeout is a new timeout; a signal or no exit is no
    verdict (its tests are not compared: the file owes a run alone); a log that does not
    align with its IDs is unaligned; a new or changed collection error. All of these block.
    Reported only: new passes, newly reached and added tests, tests no longer reached, a
    file that now completes, a new file, and time: completed in both with the seconds beyond
    the factor either way and at least min_seconds apart, or timed out in both with the
    number of tests reached beyond the factor.
    """
    blocking, reported, unchanged = [], [], []
    for f in sorted(found):
        now, was = found[f], record["files"].get(f)
        size = len(blocking) + len(reported)

        def add(kind, f=f, **detail):
            (blocking if kind in BLOCKING else reported).append({"file": f, "kind": kind, **detail})

        if was is None:
            add("new file", now=now["status"])
            was = {"status": "absent", "tests": [], "reached": 0, "seconds": None}
        ws, ns = was["status"], now["status"]
        if ns.startswith("signal") or ns == "no exit":
            failing = [t[0] for t in now["tests"] if t[1] in FAILING]
            add("no verdict", was=ws, now=ns, reached=now["reached"], failing_before_end=failing)
            continue
        if not now["aligned"]:
            add("unaligned", now=ns, why=now.get("unaligned"))
        if _completed(ws) and ns == "timeout":
            add("new timeout", was=ws, now=ns, reached=now["reached"], collected=now["collected"])
        if ws == "timeout" and _completed(ns):
            add("now completes", was=ws, now=ns, seconds=now["seconds"])
        if now.get("collection_error") and now.get("collection_error") != was.get(
            "collection_error"
        ):
            add("collection error", was=was.get("collection_error"), now=now["collection_error"])
        before = {t[0]: t for t in was["tests"]}
        after = {t[0]: t for t in now["tests"]}
        for test in list(before) + [t for t in after if t not in before]:
            a, b = before.get(test), after.get(test)
            kind = _test_change(a, b)
            if kind:
                detail = {
                    "test": test,
                    "was": a[1] if a else "absent",
                    "now": b[1] if b else "absent",
                }
                if kind == "changed error":
                    detail |= {"errors_was": a[2] if len(a) > 2 else None, "errors_now": b[2]}
                elif kind == "new failure" and len(b) > 2:
                    detail["errors_now"] = b[2]
                add(kind, **detail)
        w, n = was.get("seconds"), now.get("seconds")
        if _completed(ws) and _completed(ns) and w and n is not None:
            if abs(n - w) >= min_seconds and (n > factor * w or n * factor < w):
                add("time", was=w, now=n, factor=round(n / w, 2))
        elif ws == "timeout" and ns == "timeout":
            w, n = was["reached"], now["reached"]
            if n * factor < w or n > factor * w:
                add("time", was_reached=w, now_reached=n, within_cap=True)
        if len(blocking) + len(reported) == size:
            unchanged.append(f)
    return blocking, reported, unchanged


def diff(args):
    """Finished run folders against tier 3's record: only what changed, per test ID."""
    record = json.loads(Path(args.record).read_text())
    found, caps = readings(args.run, args.collected)
    blocking, reported, unchanged = diff_readings(record, found, args.factor, args.min_seconds)
    missing = sorted(set(record["files"]) - set(found))
    caps_differ = sorted({c for c in caps.values() if c != record.get("cap_seconds")})
    counts = {}
    for entry in blocking + reported:
        counts[entry["kind"]] = counts.get(entry["kind"], 0) + 1
    result = {
        "kind": DIFF_KIND,
        "record": str(args.record),
        "runs": [str(r) for r in args.run],
        "factor": args.factor,
        "min_seconds": args.min_seconds,
        "record_cap_seconds": record.get("cap_seconds"),
        "run_caps": caps,
        "caps_differ": caps_differ,
        "files_read": len(found),
        "files_unchanged": len(unchanged),
        "record_files_not_in_runs": missing,
        "counts": counts,
        "blocking": blocking,
        "reported": reported,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({k: result[k] for k in ("files_read", "files_unchanged", "counts")}))
    if caps_differ:
        print(f"caps differ from the record's {record.get('cap_seconds')} s: {caps_differ}")
    if missing:
        print(f"{len(missing)} record files not in these runs")
    for entry in blocking:
        print(
            f"BLOCKING {entry['kind']}: {entry['file']}"
            + (f"::{entry['test']}" if "test" in entry else "")
        )
    incomplete = bool(missing) and args.require_complete
    return 1 if blocking or caps_differ or incomplete else 0


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
    fo = sub.add_parser("fold", help="a landing's measured rows onto the current record (D222)")
    fo.add_argument("--record", required=True, help="the current tier record (main's)")
    fo.add_argument("--measured", required=True, nargs="+", help="measure's records, later win")
    fo.add_argument("--out", required=True)
    for p in (t, fo):
        p.add_argument("--pre-marker-ok", action="store_true",
                       help=f"take an unmarked measurement made before {UNMARKED_UNTIL} (D321 R1)")
    me = sub.add_parser("merge", help="the three-way fold of a merge, by row delta")
    me.add_argument("--base", required=True, help="the merge base's record")
    me.add_argument("--ours", required=True, help="the branch's record")
    me.add_argument("--theirs", required=True, help="main's record")
    me.add_argument("--out", required=True)
    r = sub.add_parser("run")
    r.add_argument("--tiers", required=True)
    r.add_argument("--tier", type=int, nargs="+", default=[1])
    r.add_argument("--out", required=True)
    r.add_argument("--cpus", type=cpus, default=[4, 5, 6, 7])
    r.add_argument("--cap", type=float, default=300.0)
    r.add_argument("--scope-map", help="record each file's reads of the tree into this folder")
    r.add_argument("--trace", help="strace's view of each file too, as a check on --scope-map's record")
    r.add_argument("--jax-cache", help="run with JAX's persistent compilation cache in this folder "
                   "(every compile written); default disabled. Never for tier seconds (D321)")
    c = sub.add_parser("collect", help="the test IDs of finished runs' files, from their tree")
    c.add_argument("--run", required=True, nargs="+", help="run folders on one tree")
    c.add_argument("--out", help="listing to write (default RUN/collected.json)")
    c.add_argument("--cpu", type=int, help="CPU for the collecting pytest (taskset)")
    f = sub.add_parser("freeze", help="tier 3's record from finished run folders")
    f.add_argument("--run", required=True, nargs="+", help="run folders, later ones win")
    f.add_argument("--collected", required=True, nargs="+", help="collect's listings")
    f.add_argument("--out", required=True)
    f.add_argument("--notes", help='JSON {"header": {...}, "files": {file: {...}}} to add')
    f.add_argument("--tiers", help="tier record whose tier-3 rows the record should cover")
    f.add_argument("--replace", action="store_true", help="refreeze over an existing record")
    d = sub.add_parser("diff", help="finished run folders against tier 3's record")
    d.add_argument("--record", required=True)
    d.add_argument("--run", required=True, nargs="+", help="run folders, later ones win")
    d.add_argument("--collected", nargs="+", help="listings (default RUN/collected.json)")
    d.add_argument("--out", help="diff JSON to write")
    d.add_argument("--factor", type=float, default=2.0, help="file time factor reported")
    d.add_argument("--min-seconds", type=float, default=60.0, help="smaller time changes ignored")
    d.add_argument("--require-complete", action="store_true", help="fail when files are missing")
    args = parser.parse_args(argv)
    if args.command == "diff" and not args.collected:
        args.collected = [str(Path(r) / "collected.json") for r in args.run]
    commands = {"measure": measure, "tiers": tiers, "fold": fold, "merge": merge, "run": run}
    commands |= {"collect": collect, "freeze": freeze, "diff": diff}
    return commands[args.command](args) or 0


if __name__ == "__main__":
    sys.exit(main())
