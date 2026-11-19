"""The fail-fast landing gate's host steps (scripts/gates/gate.sh; the testing plan of 19 November
2026, items A and B). Host only: nothing here imports cells or JAX. The engine runs in gate.sh's own
subprocesses, and crossrev's set actions run through crossrev_sets.py's commands.

  preflight HEAD BASE OUT_JSON
      The configuration, checked before anything waits for a lane. Both snapshots are complete and
      clean. crossrev's record holds exactly the runner's sets, so a stale runner or record (the
      "10 of 9" fault of 18 November) is refused here. c1's save, the baseline, the tier record and
      every declared file exist. A guard file the head lacks (an older tree) is reported, not
      refused.
  select HEAD BASE TIERS OUT_JSON [--budget SECONDS]
      The pre-lock test files, as a tier-record subset for scripts/test_tiers.py run: the guard set
      (GUARDS) and the test files whose bytes differ between the two snapshots, or that only the
      head holds, within --budget seconds of their rows (default 600; new files first, then the
      cheapest; the rest are left to the tiers under the lock). Rows come from the head's record.
      Tier-3 files are listed, not run (they are run deliberately). New files go under tier "9",
      with a row that only asks for an exit code of 0.
  prelock-verdict SUBSET RUN_DIR OUT_JSON
      That run, judged against its rows: a recorded file as the tier runner judges it (its
      summary.json), and a new file by its exit code and failed and error counts only. A file that
      reached the cap without failing a test is deferred to the tiers under the lock, never refused.
  listing-complete PREFIX
      Whether one side's collection is complete: pytest ended it (exit 0, or 1 with the collection
      errors it reports), and the listing holds exactly the count pytest's summary line names.
  ids BASE_PREFIX HEAD_PREFIX OUT_JSON
      The IDs check: both listings complete (listing-complete), and the head's collected IDs are
      the base's plus additions from the files in ADDITIONS_FROM only, minus exactly the IDs in
      REMOVED_OK_FILE (one per line; each must be missing), with no collection error the base did
      not have. Both lists are declared before the gate (the lead's rule of 19 November).
  cache-find ROOT KIND BASE [ITEM ...] / cache-publish ROOT KIND BASE SRC [ITEM ...]
      The base side's results, cached per main revision. An entry is ROOT/KIND-REV-KEY, where KEY
      digests the base's revision, KIND, the ITEMs (for example the record's folder or the move
      map's digest) and the interpreter's identity (its path and its jax, jaxlib and numpy
      versions, read from the --python interpreter's metadata). Only a complete, clean snapshot is
      keyed. A published entry holds CACHE.json, and it is renamed into place whole, so a partial
      entry is never found. A second publish of the same key leaves the first in place.
  crossrev-sets
      crossrev's sets in the runner's order, one line.
  crossrev-run SNAPSHOT OUT --cpus LIST [--sets SET ...] [--python PY]
      crossrev's set actions (crossrev_sets.py's commands, unchanged) for each set, the sets spread
      over the CPUs, one CPU per set, the longest first. The layout is crossrev_sets.py's:
      OUT/SET, OUT/SET-ACTION.log and lines "SET ACTION exit RC seconds N" in OUT/crossrev.log.
      Exit 1 when any action failed.
  crossrev-verdict BASE_DIR HEAD_DIR COMPARE_DIR OUT_JSON [--sets ...] [--expected FILE]
      The landing's claim, set by set: COMPARE_DIR/compare-SET.txt, composite_crossrev's comparison
      of the base's set with the head's, says identical, and both file listings are the same. A
      difference passes only where --expected declares it: one SET/FILE per line, an exact list,
      so each declared file must differ and nothing else may. This is how a by-design program
      change is gated before its record is renewed.
  g1-plan BASELINE N OUT_JSON [--seconds FILE]
      G1's shards, by longest processing time, from the world seconds of the last passing G1
      (FILE), else the baseline's own. The plan's format is g1_plan.py's (d198-retire's tools).
  g1-groups PLAN K
      Shard K's groups, one per line: SET, a tab, then its worlds separated by spaces.
  g1-merge PARTS OUT
      The shards' parts as one baseline-shaped folder (g1_plan.py's merge, unchanged in behaviour).
  g1-seconds MERGED FILE
      The world seconds of a passing G1, written whole for the next plan.
  qualify-subsets RECORD OUT --verify FILE ... --tier3 FILE ...
      The cache qualification's two tier subsets of RECORD, rows only (cache_qualify.sh):
      OUT/verify-tiers.json and OUT/tier3-tiers.json.
  cache-verdict OUT
      The cache qualification's verdict on its arms (cache_qualify.sh), into OUT/verdict.json:
      every criterion, each listed with what failed, and notes (the cross-revision hit rate, the
      seconds and new cache entries per stage).
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PYTHON = "/mnt/workspaces/Cells/venv-cpu/bin/python"  # crossrev_sets.PYTHON

# The heavier modules are imported where they are used: each step is its own short process.


def xr():
    """crossrev_sets.py, beside this file (imported only by the steps that need it)."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import crossrev_sets

    return crossrev_sets

# The guard set: the static guards that scan the source tree and run no world, all tier 1 (about
# a minute on one CPU together). test_species_sum_sites.py alone caught three gates' faults on
# 18-19 November, each after about 25 minutes of tiers.
GUARDS = (
    "tests/unit/test_species_sum_sites.py",
    "tests/unit/test_legacy_entry.py",
    "tests/unit/test_engine_betse_boundary.py",
    "tests/unit/test_j2_bright_line.py",
    "tests/unit/test_continuity_bypass.py",
    "tests/unit/test_judge_imports.py",
    "tests/unit/test_law_modules.py",
    "tests/unit/test_source_profile_boundary.py",
)
NEW_TIER = "9"  # The subset's key for test files the head's record has no row for.
EMPTY_PATCH = hashlib.sha256(b"").hexdigest()
# crossrev's sets, longest first (their seconds on 19 November); only the order of the pool.
SET_WEIGHTS = {"qualification": 65, "base": 35, "division": 30, "species": 23, "reactions": 21,
               "acceptances": 21, "coupling": 19, "kinds": 18, "replication": 18, "volume": 10,
               "injection": 9}


def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path, doc):
    Path(path).write_text(json.dumps(doc, indent=1) + "\n")


def snapshot(tree):
    """(revision, problems) of an execution snapshot: complete, clean and naming its revision."""
    path = Path(tree) / "SNAPSHOT.json"
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        return None, [f"{tree}: no readable SNAPSHOT.json ({type(error).__name__})"]
    problems = []
    if doc.get("status") != "complete":
        problems.append(f"{tree}: snapshot status {doc.get('status')!r}, not 'complete'")
    if doc.get("patch_sha256") != EMPTY_PATCH:
        problems.append(f"{tree}: not clean (its patch is not empty)")
    if not doc.get("git_revision"):
        problems.append(f"{tree}: no git_revision")
    return doc.get("git_revision"), problems


def listed(path):
    return [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]


# ------------------------------------------------------------------------------------ preflight


def preflight(head, base, env):
    problems = []
    head_rev, found = snapshot(head)
    problems += found
    base_rev, found = snapshot(base)
    problems += found
    record = env.get("REC")
    if not record or not Path(record).is_dir():
        problems.append(f"crossrev's record {record!r} is not a folder")
    else:
        try:
            have = xr().record_sets(record)
            missing = [s for s in xr().ORDER if s not in have]
            if missing:
                problems.append(f"crossrev's record lacks sets the runner requires: {missing}")
        except SystemExit as refusal:  # A folder the runner does not know.
            problems.append(str(refusal))
    for name in ("C1", "BASELINE"):
        if not (Path(env.get(name) or "/nonexistent") / "manifest.json").is_file():
            problems.append(f"{name} {env.get(name)!r} holds no manifest.json")
    tiers = Path(head) / env.get("TIERS", "tests/test_tiers.json")
    try:
        doc = json.loads(tiers.read_text())
        gone = [r["file"] for t in ("1", "2") for r in doc["tiers"].get(t, [])
                if not (Path(head) / r["file"]).is_file()]
        if gone:
            problems.append(f"the tier record names files the head lacks: {gone[:5]}")
    except (OSError, ValueError, KeyError) as error:
        problems.append(f"the tier record {tiers} is unreadable ({type(error).__name__})")
    for name in env.get("ADDITIONS_FROM", "").replace(",", " ").split():
        if not (Path(head) / name).is_file():
            problems.append(f"ADDITIONS_FROM names {name}, which the head lacks")
    if env.get("REMOVED_OK_FILE"):
        try:
            bad = [line for line in listed(env["REMOVED_OK_FILE"]) if "::" not in line]
            if bad:
                problems.append(f"REMOVED_OK_FILE holds lines that are not test IDs: {bad[:3]}")
        except OSError:
            problems.append(f"REMOVED_OK_FILE {env['REMOVED_OK_FILE']} is unreadable")
    if env.get("CROSSREV_EXPECTED"):
        try:
            for line in listed(env["CROSSREV_EXPECTED"]):
                set_name, _, name = line.partition("/")
                if set_name not in xr().SETS or not name:
                    problems.append(f"CROSSREV_EXPECTED line {line!r} is not SET/FILE")
        except OSError:
            problems.append(f"CROSSREV_EXPECTED {env['CROSSREV_EXPECTED']} is unreadable")
    # A guard the head lacks is skipped by select (an older tree), not refused here: removing a
    # guard's file from a tree that had it shows as its missing IDs in the IDs check.
    return {"ok": not problems, "head": head_rev, "base": base_rev, "problems": problems,
            "guards_absent": [g for g in GUARDS if not (Path(head) / g).is_file()]}


# ------------------------------------------------------------------------- pre-lock test files


def test_files(tree):
    return {p.relative_to(tree).as_posix() for p in (Path(tree) / "tests").rglob("test_*.py")}


def select(head, base, tiers_rel, budget=600.0, new_seconds=30.0):
    """(subset document, report) of the pre-lock test files.

    The guard set always runs. The changed files run within budget seconds of their rows (a new
    file counts new_seconds), new files first and then the cheapest; the rest are left to the tiers
    under the lock. A move that touches most test files then keeps its pre-lock step short."""
    doc = json.loads((Path(head) / tiers_rel).read_text())
    tier_of = {r["file"]: (t, r) for t in doc["tiers"] for r in doc["tiers"][t]}
    head_files, base_files = test_files(head), test_files(base)
    changed = sorted(f for f in head_files if f not in base_files
                     or (Path(head) / f).read_bytes() != (Path(base) / f).read_bytes())
    guards = [g for g in GUARDS if g in head_files]
    cost = {f: tier_of[f][1]["seconds"] if f in tier_of else new_seconds for f in changed}
    spent, within, left = 0.0, [], []
    runnable = [f for f in changed if f not in guards and tier_of.get(f, ("new",))[0] != "3"]
    for name in sorted(runnable, key=lambda f: (f in tier_of, cost[f], f)):
        if spent + cost[name] <= budget:
            within.append(name)
            spent += cost[name]
        else:
            left.append(name)
    subset = {"1": [], "2": [], NEW_TIER: []}
    tier3 = sorted(f for f in changed if tier_of.get(f, ("new",))[0] == "3")
    for name in sorted(set(guards) | set(within)):
        if name not in tier_of:
            subset[NEW_TIER].append({"file": name, "seconds": 0.0, "exit_code": 0, "counts": {}})
        else:
            subset[tier_of[name][0]].append(tier_of[name][1])
    out = {"kind": "cells.test_tiers@1", "fast_seconds": doc.get("fast_seconds"),
           "cap_seconds": doc.get("cap_seconds"), "tiers": subset,
           "note": "the gate's pre-lock subset: the guard set and the head's changed test files"}
    report = {"guards": guards, "guards_absent": [g for g in GUARDS if g not in guards],
              "changed": changed, "new": [r["file"] for r in subset[NEW_TIER]],
              "tier3_not_run": tier3, "budget_seconds": budget,
              "changed_within_budget_seconds": round(spent, 1), "left_to_tiers": left,
              "files": sum(len(v) for v in subset.values())}
    return out, report


def prelock_verdict(subset_path, run_dir):
    subset = json.loads(Path(subset_path).read_text())
    new = {r["file"] for r in subset["tiers"].get(NEW_TIER, [])}
    run = json.loads((Path(run_dir) / "run.json").read_text())
    summary = json.loads((Path(run_dir) / "summary.json").read_text())
    ran = {r["file"]: r for r in run["files"]}
    wanted = {r["file"] for t in subset["tiers"].values() for r in t}
    refused = []
    # A file that reached the pre-lock cap is deferred to the tiers under the lock, never refused:
    # on a loaded light CPU wall time ran up to four times CPU time (19 November), so a healthy
    # heavy file can time out here. A test it failed before the cap still refuses.
    deferred = sorted(f for f, r in ran.items() if r.get("timed_out")
                      and not r["counts"].get("failed") and not r["counts"].get("error"))
    for name in sorted(wanted - set(ran)):
        refused.append({"file": name, "why": "not run"})
    for entry in summary["changed_vs_record"]:
        if entry["file"] not in new and entry["file"] not in deferred:
            refused.append({"file": entry["file"], "why": entry["why"], "now": entry["now"]})
    for name in sorted(new & set(ran)):
        row = ran[name]
        counts = row["counts"]
        if name in deferred:
            continue
        if row["exit_code"] != 0 or counts.get("failed") or counts.get("error"):
            refused.append({"file": name, "why": ["a new file did not pass"],
                            "now": [row["exit_code"], counts]})
    return {"ok": not refused, "files": len(ran), "refused": refused,
            "deferred_to_the_tiers": deferred}


# ------------------------------------------------------------------------------------------ IDs


def collected(prefix):
    return {line.strip() for line in Path(prefix + ".ids").read_text().splitlines()
            if "::" in line}


def collection_errors(prefix):
    text = Path(prefix + ".log").read_text(errors="replace")
    return sorted({line.split()[1] for line in text.splitlines()
                   if line.startswith("ERROR ") and len(line.split()) > 1})


def listing_complete(prefix):
    """(complete, why) of one side's collection.

    Complete means three things: pytest ended its collection (exit 0, or 1 with collection errors
    it reported), its summary line names a count, and the listing holds exactly that many IDs. A
    truncated or interrupted listing would hide removed tests, and must never be compared or
    cached."""
    text = Path(prefix + ".log").read_text(errors="replace")
    counts = [int(m[1]) for m in re.finditer(r"^(\d+) tests? collected", text, flags=re.M)]
    if Path(prefix + ".json").is_file():
        try:
            code = json.loads(Path(prefix + ".json").read_text()).get("exit")
        except ValueError:
            code = None
        if code not in (0, 1):
            return False, f"pytest's collection exit {code}"
    if not counts:
        return False, "no 'N tests collected' line"
    n = len(collected(prefix))
    if n != counts[-1]:
        return False, f"{n} IDs listed against {counts[-1]} collected"
    return True, f"{n} IDs, as collected"


def ids_check(base_prefix, head_prefix, additions_from, removed_ok):
    complete = {side: listing_complete(prefix)
                for side, prefix in (("base", base_prefix), ("head", head_prefix))}
    base, head = collected(base_prefix), collected(head_prefix)
    allowed = set(additions_from)
    new, missing = sorted(head - base), sorted(base - head)
    removed = sorted(set(missing) & removed_ok)
    present = sorted(removed_ok - set(missing))
    missing = [m for m in missing if m not in removed_ok]
    outside = [i for i in new if i.split("::")[0] not in allowed]
    new_errors = sorted(set(collection_errors(head_prefix)) - set(collection_errors(base_prefix)))
    empty = [side for side, found in (("base", base), ("head", head)) if not found]
    incomplete = {side: why for side, (done, why) in complete.items() if not done}
    ok = not (missing or present or outside or new_errors or empty or incomplete)
    # The keys and verdict words of ids_additions.py, which the lead's tools read.
    return {"ok": ok, "base": len(base), "head": len(head), "additions": len(new),
            "additions_by_file": {f: sum(1 for i in new if i.startswith(f + "::"))
                                  for f in sorted(allowed)},
            "outside_the_branch_files": outside[:10], "missing": missing[:10],
            "removed_as_listed": removed, "listed_but_present": present,
            "new_errors": new_errors[:5], "empty_listing": empty,
            "incomplete_listing": incomplete,
            "verdict": "additions only" if ok else "DIFFERS"}


# ------------------------------------------------------------------------------- the base cache


def interpreter(python):
    """The interpreter's identity: its path and its jax, jaxlib and numpy versions."""
    import subprocess

    code = ("import importlib.metadata as m\n"
            "print(' '.join(m.version(p) for p in ('jax', 'jaxlib', 'numpy')))")
    try:
        versions = subprocess.run([python, "-I", "-c", code], capture_output=True, text=True,
                                  timeout=120).stdout.strip()
    except OSError:
        versions = ""
    return [f"python={python}", f"versions={versions or 'unknown'}"]


def cache_entry(root, kind, base, items, python):
    """(folder, key document), or SystemExit when the base cannot be keyed."""
    revision, problems = snapshot(base)
    if problems:
        raise SystemExit(f"not cached: {problems}")
    doc = {"kind": kind, "revision": revision, "items": sorted(items) + interpreter(python)}
    key = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:16]
    return Path(root) / f"{kind}-{revision[:12]}-{key}", doc


def cache_find(root, kind, base, items, python):
    folder, doc = cache_entry(root, kind, base, items, python)
    try:
        stored = json.loads((folder / "CACHE.json").read_text())
    except (OSError, ValueError):
        return None
    return folder if stored.get("key") == doc else None


def cache_publish(root, kind, base, src, items, python):
    """The entry's folder: SRC copied in whole and renamed into place, or the one already there."""
    import shutil

    folder, doc = cache_entry(root, kind, base, items, python)
    if cache_find(root, kind, base, items, python):
        return folder
    Path(root).mkdir(parents=True, exist_ok=True)
    tmp = Path(root) / f".tmp-{folder.name}-{os.getpid()}"
    shutil.copytree(src, tmp / "entry", symlinks=False)
    write_json(tmp / "entry" / "CACHE.json",
               {"key": doc, "published": utc(), "from": str(Path(src).resolve())})
    try:
        os.rename(tmp / "entry", folder)  # Whole, or not at all; an existing entry is kept.
    except OSError:
        pass
    shutil.rmtree(tmp, ignore_errors=True)
    if not cache_find(root, kind, base, items, python):
        raise SystemExit(f"publish failed: {folder}")
    return folder


# ------------------------------------------------------------------------------------- crossrev


def crossrev_run(snapshot_dir, out, sets, cpus, python):
    import subprocess
    import threading
    from concurrent.futures import ThreadPoolExecutor

    snapshot_dir, out = Path(snapshot_dir).resolve(), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    env = xr().environment(snapshot_dir)
    lock = threading.Lock()
    free = list(cpus)

    def log(line):
        with lock, open(out / "crossrev.log", "a") as handle:
            handle.write(f"{utc()} {line}\n")

    def one(name):
        with lock:
            cpu = free.pop()
        status = 0
        try:
            for action, argv in xr().commands(snapshot_dir, out, name, python):
                start = time.time()
                with open(out / f"{name}-{action}.log", "w") as handle:
                    rc = subprocess.run(["taskset", "-c", str(cpu), "nice", "-n", "10", *argv],
                                        cwd=snapshot_dir, env=env, stdout=handle,
                                        stderr=subprocess.STDOUT).returncode
                status |= rc != 0
                log(f"{name} {action} exit {rc} seconds {round(time.time() - start)} cpu {cpu}")
        finally:
            with lock:
                free.append(cpu)
        return status

    log(f"crossrev sets {' '.join(sets)} of {snapshot_dir} on CPUs {','.join(map(str, cpus))}")
    order = sorted(sets, key=lambda s: -SET_WEIGHTS.get(s, 0))
    with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
        status = max([0, *pool.map(one, order)])
    log(f"done status {status}")
    return status


def crossrev_verdict(base_dir, head_dir, compare_dir, sets, expected_file=None):
    expected = {}
    for line in listed(expected_file) if expected_file else []:
        set_name, _, name = line.partition("/")
        expected.setdefault(set_name, set()).add(name)
    per_set, ok = {}, True
    for name in sets:
        text = Path(compare_dir, f"compare-{name}.txt")
        lines = text.read_text(errors="replace").splitlines() if text.is_file() else []
        differs = sorted(line.split()[0] for line in lines
                         if len(line.split()) >= 2 and line.split()[1] == "DIFFERS")
        verdict = next((line for line in lines if line.startswith("verdict ")), None)
        names = [sorted(p.name for p in Path(d, name).iterdir()) if Path(d, name).is_dir() else None
                 for d in (base_dir, head_dir)]
        listing_same = names[0] is not None and names[0] == names[1]
        want = sorted(expected.get(name, set()))
        if not want:
            passed = verdict == "verdict identical" and not differs and listing_same
        else:  # Exactly the declared files differ; everything else is identical.
            passed = verdict is not None and differs == want and listing_same
        ok &= passed
        per_set[name] = {"passed": passed, "verdict": verdict, "differs": differs,
                         "declared": want, "listing_same": listing_same}
    unknown = sorted(set(expected) - set(sets))
    ok &= not unknown
    same = sum(1 for v in per_set.values() if v["passed"] and not v["declared"])
    return {"ok": ok, "sets": len(sets), "identical": same,
            "as_declared": sum(1 for v in per_set.values() if v["passed"] and v["declared"]),
            "declared_for_sets_not_run": unknown, "per_set": per_set}


# ------------------------------------------------------------------------------------------- G1


def g1_plan(baseline, n, seconds_file=None):
    worlds = json.loads((Path(baseline) / "manifest.json").read_text())["worlds"]
    current = {}
    if seconds_file and Path(seconds_file).is_file():
        current = json.loads(Path(seconds_file).read_text()).get("seconds", {})
    jobs = sorted(((current.get(k, v["seconds"]) or 0.0, k) for k, v in worlds.items()),
                  reverse=True)
    shards = [{"seconds": 0.0, "groups": {}} for _ in range(n)]
    for seconds, key in jobs:
        shard = min(shards, key=lambda s: s["seconds"])
        set_name, name = key.split("/", 1)
        shard["groups"].setdefault(set_name, []).append(name)
        shard["seconds"] += seconds
    plan = [{"seconds": round(s["seconds"]),
             "groups": [{"set": k, "worlds": v} for k, v in s["groups"].items()]} for s in shards]
    source = {"current": sum(1 for k in worlds if k in current),
              "baseline": sum(1 for k in worlds if k not in current)}
    return plan, source


def g1_merge(parts, out):
    """g1_plan.py's merge, unchanged in behaviour: one manifest, and per set the parts' files."""
    parts, out = Path(parts), Path(out)
    merged, first = {}, None
    for manifest_path in sorted(parts.glob("part-*/manifest.json")):
        manifest = json.loads(manifest_path.read_text())
        first = first or manifest
        for key, value in manifest["worlds"].items():
            if key in merged:
                raise SystemExit(f"world {key} saved twice")
            merged[key] = value
        for set_dir in manifest_path.parent.iterdir():
            if not set_dir.is_dir():
                continue
            target = out / set_dir.name
            target.mkdir(parents=True, exist_ok=True)
            for f in set_dir.iterdir():
                (target / f.name).symlink_to(f.resolve())
    if first is None:
        raise SystemExit("no parts")
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "manifest.json", dict(first, worlds=merged))
    return len(merged)


def g1_seconds(merged, path):
    worlds = json.loads((Path(merged) / "manifest.json").read_text())["worlds"]
    seconds = {k: v.get("seconds") for k, v in worlds.items()}
    if not seconds or any(not isinstance(v, (int, float)) for v in seconds.values()):
        raise SystemExit("not every world has its seconds")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}")
    write_json(tmp, {"from": str(Path(merged).resolve()), "written": utc(), "seconds": seconds})
    os.replace(tmp, path)
    return len(seconds)


# ------------------------------------------------------------------- the cache qualification

TIMING = ("new timeout", "no verdict")  # Blocking kinds that lose coverage to time, not outcomes.
COMPLETED = ("pass", "pass-skips", "pass-empty", "fail")  # test_tiers.py's completed file endings
CACHE_ERRORS = ("CacheVerificationError", "Persistent compilation cache inconsistency",
                "Error reading persistent compilation cache",
                "Error writing persistent compilation cache")


def qualify_subsets(record_path, out, verify, tier3):
    """cache_qualify.sh's two tier subsets of a tier record, rows only (the record's measured
    provenance is left out): OUT/verify-tiers.json keeps the VERIFY files in their own tiers, and
    OUT/tier3-tiers.json puts the tier-3 stage's files under tier 3. A named file the record does
    not hold is refused."""
    record = json.loads(Path(record_path).read_text())
    rows = {r["file"]: (t, r) for t, rs in record["tiers"].items() for r in rs}
    missing = sorted(f for f in set(verify) | set(tier3) if f not in rows)
    if missing:
        raise SystemExit(f"Refused: not in {record_path}: {missing}")
    keep = {k: v for k, v in record.items() if k not in ("measured", "measured_provenance")}
    keep["subset_of"] = str(record_path)
    tiers = {t: [r for r in rs if r["file"] in set(verify)] for t, rs in record["tiers"].items()}
    write_json(Path(out) / "verify-tiers.json", dict(keep, tiers=tiers))
    write_json(Path(out) / "tier3-tiers.json",
               dict(keep, tiers={"1": [], "2": [], "3": [rows[f][1] for f in sorted(set(tier3))]}))


def _read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def _stages(out):
    """{(arm, stage): record} of cache_qualify.sh's stages.jsonl, the last record winning."""
    found, path = {}, Path(out) / "stages.jsonl"
    for line in path.read_text().splitlines() if path.is_file() else []:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        found[(row.get("arm"), row.get("stage"))] = row
    return found


def _peaks(folder):
    """{key: peak RSS in KB} of one stage's processes: /usr/bin/time's "%M %e" files (rss-*.txt,
    keyed by name) and the interpreter wrapper's lines "KB seconds exit command" (rss-*.log, keyed
    by the command with the stage's own folder written <stage>), the largest of a key's runs."""
    folder, out = Path(folder), {}
    for path in sorted(folder.glob("rss-*.txt")):
        fields = path.read_text(errors="replace").split()
        if fields and fields[0].isdigit():
            out[path.stem] = int(fields[0])
    for path in sorted(folder.glob("rss-*.log")):
        for line in path.read_text(errors="replace").splitlines():
            parts = line.split(" ", 3)
            if len(parts) == 4 and parts[0].isdigit():
                key = parts[3].replace(str(folder), "<stage>")
                out[key] = max(out.get(key, 0), int(parts[0]))
    return out


def _identical(compare, worlds):
    return bool(compare) and compare.get("verdict") == "identical" \
        and not compare.get("problems") and compare.get("worlds") == compare.get("equal") == worlds


def cache_verdict(out, rss_factor=1.25, stage_factor=1.5, fr_cap_kb=3 * 1024 * 1024,
                  warm_g1=0.6, verify_g1=0.75):
    """Every criterion of the qualification (cache_qualify.sh; the testing plan's section 5.3),
    each True or False with what failed, and notes: the qualification passes only when all hold.

    Outcomes, per test ID against OFF: tiers 1+2 (cold, warm, warm2, xrev-head), the VERIFY
    subset and the tier-3 stage's files, each complete at OFF's cap; an outcome change and a loss of
    coverage to time are separate criteria. Bits: G1 against c1 on the head and the base, every
    shard on one CPU; the planted controls against their own runs without the cache; FR's set;
    crossrev against the record and the replication set's 55 files. The cache: no cache or
    verification error in any log; written in COLD, read in WARM (no entry added, G1 faster),
    recompiled in VERIFY; the shared default folder untouched; OFF's reused tier run free of it.
    Memory: no out-of-memory kill; each G1 group's and FR process's peak RSS within rss_factor of
    OFF's, FR's under its 3 GiB unit cap; each stage's largest anonymous memory within
    stage_factor of COLD's same stage."""
    out, checks, notes = Path(out), {}, {}

    def check(name, ok, detail=None):
        checks[name] = bool(ok)
        if detail not in (None, [], {}):
            notes[name] = detail

    stages = _stages(out)
    plan = _read(out / "g1-plan.json") or []
    worlds = sum(len(g["worlds"]) for shard in plan for g in shard.get("groups", []))
    check("G1's shared plan holds worlds", worlds > 0)
    off_record = _read(out / "off" / "reuse.json") or {}
    check("off: its tier run wrote no persistent cache entry", off_record.get("cache_entries") == 0,
          off_record)
    t3 = (_read(out / "off" / "tier3-record.json") or {}).get("files", {})
    want3 = sum(len(v) for v in (_read(out / "tier3-tiers.json") or {}).get("tiers", {}).values())
    check("off: every tier-3 stage file ran to its end", len(t3) == want3 > 0
          and all(r.get("status") in COMPLETED for r in t3.values()),
          {f: r.get("status") for f, r in t3.items() if r.get("status") not in COMPLETED})
    wantv = sum(len(v) for v in (_read(out / "verify-tiers.json") or {}).get("tiers", {}).values())
    runs = [(a, "tiers", None) for a in ("cold", "warm", "warm2", "xrev-head")]
    runs += [("verify", "tiers", wantv)] + [(a, "tier3", want3) for a in ("cold", "warm", "warm2",
                                                                            "verify")]
    for arm, stage, want in runs:
        d = _read(out / arm / stage / "diff.json")
        blocking = (d or {}).get("blocking", [])
        outcome = [b for b in blocking if b.get("kind") not in TIMING]
        timing = [b for b in blocking if b.get("kind") in TIMING]
        complete = bool(d) and d.get("files_read", 0) > 0 and not d.get("caps_differ") and (
            d["files_read"] == want if want is not None else not d.get("record_files_not_in_runs"))
        read = {k: (d or {}).get(k) for k in ("files_read", "caps_differ")}
        check(f"{arm} {stage}: every file read against OFF's record at OFF's cap", complete,
              None if complete else read)
        check(f"{arm} {stage}: outcomes per test ID as OFF's", bool(d) and not outcome,
              outcome[:20])
        check(f"{arm} {stage}: no coverage lost to time", bool(d) and not timing, timing[:20])
    for arm in ("off", "cold", "warm", "warm2", "verify", "xrev-base", "xrev-head"):
        c = _read(out / arm / "g1" / "compare.json")
        cpus = sorted({p.read_text().strip() for p in (out / arm / "g1").glob("shard-*.cpus")})
        check(f"{arm} G1: {worlds} of {worlds} worlds bitwise as c1's", _identical(c, worlds),
              {k: (c or {}).get(k) for k in ("verdict", "worlds", "equal")})
        check(f"{arm} G1: every shard on one CPU, as c1's", cpus == ["1"], cpus)
    for name, n in (("unplanted", worlds), ("planted", worlds), ("c2prime", 1)):
        c = _read(out / "negative" / name / "compare.json")
        check(f"negative {name}: bitwise as its own run without the cache", _identical(c, n),
              {k: (c or {}).get(k) for k in ("verdict", "worlds", "equal")})
    for arm in ("off", "cold", "warm", "warm2", "verify"):
        v = _read(out / arm / "fr" / "verdict.json")
        check(f"{arm} FR: the set passes", bool(v) and v.get("passed") is True)
        peaks = _peaks(out / arm / "fr")
        over = {k: p for k, p in peaks.items() if p >= fr_cap_kb}
        check(f"{arm} FR: every process under its unit's 3 GiB", bool(peaks) and not over, over)
    for arm in ("cold", "warm", "warm2"):
        v = _read(out / arm / "crossrev" / "verdict.json") or {}
        check(f"{arm} crossrev: every set identical to the record", v.get("ok") is True
              and v.get("sets", 0) > 0 and v.get("identical") == v.get("sets"),
              {k: v.get(k) for k in ("sets", "identical")})
        done = out / arm / "replication" / "done"
        check(f"{arm} replication: 55 of 55, by the lead's check", done.is_file()
              and done.read_text().strip() == "0")
    bad = sorted(str(p.relative_to(out)) for p in out.rglob("*.log") if p.is_file()
                 and any(m in p.read_text(errors="replace") for m in CACHE_ERRORS))
    check("no cache error and no verification error in any log", not bad, bad[:20])
    check("no out-of-memory kill in any stage", bool(stages) and all(
        int(r.get("oom_kills") or 0) == 0 for r in stages.values()),
        {f"{a} {s}": r.get("oom_kills") for (a, s), r in stages.items() if r.get("oom_kills")})
    for arm, stage in [(a, "g1") for a in ("cold", "warm", "warm2", "verify", "xrev-head")] + [
            (a, "fr") for a in ("cold", "warm", "warm2", "verify")]:
        ref, now = _peaks(out / "off" / stage), _peaks(out / arm / stage)
        ratios = {k: round(now[k] / ref[k], 3) for k in sorted(set(ref) & set(now)) if ref[k]}
        worst = max(ratios.values(), default=None)
        check(f"{arm} {stage}: each process's peak RSS within {rss_factor} times OFF's",
              worst is not None and worst <= rss_factor,
              {"worst": worst, "over": {k: r for k, r in ratios.items() if r > rss_factor}})
    for arm, stage in [(a, s) for a in ("warm", "warm2") for s in ("tiers", "g1", "fr+tier3")] + [
            ("verify", "g1"), ("verify", "fr+tier3"), ("xrev-head", "tiers"), ("xrev-head", "g1")]:
        a, c = stages.get((arm, stage)) or {}, stages.get(("cold", stage)) or {}
        ok = bool(a.get("anon_peak")) and bool(c.get("anon_peak")) \
            and a["anon_peak"] <= stage_factor * c["anon_peak"]
        check(f"{arm} {stage}: the stage's largest anonymous memory within {stage_factor} times "
              f"cold's", ok, None if ok else [a.get("anon_peak"), c.get("anon_peak")])

    def added(arm, stage):
        r = stages.get((arm, stage)) or {}
        try:
            return int(r["entries_after"]) - int(r["entries_before"])
        except (KeyError, TypeError, ValueError):
            return None

    def seconds(arm, stage):
        return (stages.get((arm, stage)) or {}).get("seconds")

    for stage in ("tiers", "g1"):
        check(f"cold {stage}: wrote cache entries (the cache engaged)",
              (added("cold", stage) or 0) > 0, added("cold", stage))
    for arm in ("warm", "warm2"):
        new = {s: added(a, s) for (a, s) in stages if a == arm}
        check(f"{arm}: added no cache entry (every program read)", bool(new)
              and all(v == 0 for v in new.values()), {k: v for k, v in new.items() if v})
        w, c = seconds(arm, "g1"), seconds("cold", "g1")
        check(f"{arm} G1: under {warm_g1} of cold's seconds (read, not compiled)",
              bool(w is not None and c) and w < warm_g1 * c, [w, c])
    v, c = seconds("verify", "g1"), seconds("cold", "g1")
    check(f"verify G1: at least {verify_g1} of cold's seconds (every program recompiled)",
          bool(v is not None and c) and v >= verify_g1 * c, [v, c])
    before = _read(out / "default-cache-before.json")
    after = _read(out / "default-cache-after.json")
    check("the shared default cache folder is unchanged", before is not None and before == after,
          None if before == after else [before, after])

    head = (added("cold", "tiers") or 0) + (added("cold", "g1") or 0)
    head_new = (added("xrev-head", "tiers") or 0) + (added("xrev-head", "g1") or 0)
    if head:
        notes["cross-revision hit rate by programs: 1 - the head's new entries / its programs"] \
            = round(1 - head_new / head, 3)
    s = {arm: sum(seconds(arm, x) or 0 for x in ("tiers", "g1"))
         for arm in ("cold", "warm", "xrev-head")}
    if s["cold"] > s["warm"]:
        notes["cross-revision saving by seconds, tiers and G1: (cold - xrev) / (cold - warm)"] \
            = round((s["cold"] - s["xrev-head"]) / (s["cold"] - s["warm"]), 3)
    notes["seconds per stage"] = {f"{a} {st}": r.get("seconds") for (a, st), r in stages.items()}
    notes["entries added per stage"] = {f"{a} {st}": added(a, st) for (a, st) in stages}
    clis = {}
    for arm in ("cold", "warm", "warm2", "verify", "xrev-base", "xrev-head"):
        for stage in ("tiers", "tier3"):
            found = list((out / arm / stage / "outputs").glob("*/Cells/cache/jax/*-cache"))
            if found:
                clis[f"{arm} {stage}"] = {"files": len({p.parts[-5] for p in found}),
                                          "entries": len(found)}
    notes["per-file caches of engine CLIs under the tier runner (configure_caches)"] = clis
    base = _read(out / "xrev-base" / "tiers" / "summary.json") or {}
    notes["xrev-base tiers: files changed against the base's own record"] = len(
        base.get("changed_vs_record") or [])
    return {"passed": all(checks.values()), "checks": checks, "notes": notes}


# ------------------------------------------------------------------------------------------ CLI


def main(argv=None):
    import argparse

    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="step", required=True)
    s = sub.add_parser("preflight")
    s.add_argument("head")
    s.add_argument("base")
    s.add_argument("out")
    s = sub.add_parser("select")
    s.add_argument("head")
    s.add_argument("base")
    s.add_argument("tiers")
    s.add_argument("out")
    s.add_argument("--budget", type=float, default=600.0)
    s = sub.add_parser("prelock-verdict")
    s.add_argument("subset")
    s.add_argument("run")
    s.add_argument("out")
    s = sub.add_parser("listing-complete")
    s.add_argument("prefix")
    s = sub.add_parser("ids")
    s.add_argument("base_prefix")
    s.add_argument("head_prefix")
    s.add_argument("out")
    for step in ("cache-find", "cache-publish"):
        s = sub.add_parser(step)
        s.add_argument("root")
        s.add_argument("kind")
        s.add_argument("base")
        if step == "cache-publish":
            s.add_argument("src")
        s.add_argument("items", nargs="*")
        s.add_argument("--python", default=PYTHON)
    sub.add_parser("crossrev-sets")
    s = sub.add_parser("crossrev-run")
    s.add_argument("snapshot")
    s.add_argument("out")
    s.add_argument("--cpus", required=True)
    s.add_argument("--sets", nargs="+")
    s.add_argument("--python", default=PYTHON)
    s = sub.add_parser("crossrev-verdict")
    s.add_argument("base_dir")
    s.add_argument("head_dir")
    s.add_argument("compare_dir")
    s.add_argument("out")
    s.add_argument("--sets", nargs="+")
    s.add_argument("--expected")
    s = sub.add_parser("g1-plan")
    s.add_argument("baseline")
    s.add_argument("n", type=int)
    s.add_argument("out")
    s.add_argument("--seconds")
    s = sub.add_parser("g1-groups")
    s.add_argument("plan")
    s.add_argument("k", type=int)
    s = sub.add_parser("g1-merge")
    s.add_argument("parts")
    s.add_argument("out")
    s = sub.add_parser("g1-seconds")
    s.add_argument("merged")
    s.add_argument("file")
    s = sub.add_parser("qualify-subsets")
    s.add_argument("record")
    s.add_argument("out")
    s.add_argument("--verify", nargs="+", required=True)
    s.add_argument("--tier3", nargs="+", required=True)
    s = sub.add_parser("cache-verdict")
    s.add_argument("out")
    a = p.parse_args(argv)
    step = a.step
    if step == "preflight":
        doc = preflight(a.head, a.base, os.environ)
        write_json(a.out, doc)
        print(json.dumps({"ok": doc["ok"], "problems": doc["problems"][:3]}))
        return 0 if doc["ok"] else 1
    if step == "select":
        subset, report = select(a.head, a.base, a.tiers, a.budget)
        write_json(a.out, subset)
        write_json(Path(a.out).with_name("selection.json"), report)
        print(json.dumps({k: (v if not isinstance(v, list) else len(v))
                          for k, v in report.items()}))
        return 0
    if step == "prelock-verdict":
        doc = prelock_verdict(a.subset, a.run)
        write_json(a.out, doc)
        print(json.dumps({"ok": doc["ok"], "files": doc["files"],
                          "refused": [r["file"] for r in doc["refused"]][:5]}))
        return 0 if doc["ok"] else 1
    if step == "listing-complete":
        done, why = listing_complete(a.prefix)
        print(why)
        return 0 if done else 1
    if step == "ids":
        removed = set(listed(os.environ["REMOVED_OK_FILE"])) if os.environ.get(
            "REMOVED_OK_FILE") else set()
        doc = ids_check(a.base_prefix, a.head_prefix,
                        os.environ.get("ADDITIONS_FROM", "").replace(",", " ").split(), removed)
        write_json(a.out, doc)
        print(json.dumps({k: doc[k] for k in ("verdict", "base", "head", "additions", "missing",
                                               "outside_the_branch_files", "listed_but_present",
                                               "new_errors")}))
        return 0 if doc["ok"] else 1
    if step == "cache-find":
        found = cache_find(a.root, a.kind, a.base, a.items, a.python)
        print(found or "")
        return 0 if found else 1
    if step == "cache-publish":
        print(cache_publish(a.root, a.kind, a.base, a.src, a.items, a.python))
        return 0
    if step == "crossrev-sets":
        print(" ".join(xr().ORDER))
        return 0
    if step == "crossrev-run":
        cpus = [int(c) for c in a.cpus.split(",") if c != ""]
        return crossrev_run(a.snapshot, a.out, xr().chosen(a.sets), cpus, a.python)
    if step == "crossrev-verdict":
        doc = crossrev_verdict(a.base_dir, a.head_dir, a.compare_dir,
                               xr().chosen(a.sets), a.expected)
        write_json(a.out, doc)
        print(json.dumps({k: doc[k] for k in ("ok", "sets", "identical", "as_declared")}))
        return 0 if doc["ok"] else 1
    if step == "g1-plan":
        plan, source = g1_plan(a.baseline, a.n, a.seconds)
        write_json(a.out, plan)
        print(f"shards (planned seconds): {[s['seconds'] for s in plan]}; worlds timed by the "
              f"last passing G1 {source['current']}, by the baseline {source['baseline']}")
        return 0
    if step == "g1-groups":
        for group in json.loads(Path(a.plan).read_text())[a.k]["groups"]:
            print(group["set"] + "\t" + " ".join(group["worlds"]))
        return 0
    if step == "g1-merge":
        print(f"merged {g1_merge(a.parts, a.out)} worlds")
        return 0
    if step == "g1-seconds":
        print(f"{g1_seconds(a.merged, a.file)} world seconds written to {a.file}")
        return 0
    if step == "qualify-subsets":
        qualify_subsets(a.record, a.out, a.verify, a.tier3)
        return 0
    if step == "cache-verdict":
        doc = cache_verdict(a.out)
        write_json(Path(a.out) / "verdict.json", doc)
        failed = [k for k, v in doc["checks"].items() if not v]
        print(json.dumps({"passed": doc["passed"], "failed": failed, "notes": doc["notes"]})[:2000])
        return 0 if doc["passed"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
