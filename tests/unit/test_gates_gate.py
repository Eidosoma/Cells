"""The fail-fast landing gate (scripts/gates/gate.sh) and its host steps
(scripts/gates/gate_steps.py). Each claim is tested with a planted failure it must catch (D187).
Host only: no world runs here.

- **preflight** passes two complete, clean snapshots and a complete record. It refuses:
  - a record that lacks a set the runner requires (the "10 of 9" fault of 18 November);
  - a record folder the runner does not know;
  - a dirty snapshot;
  - a declared file the head lacks.
- **select** chooses the guard set and the test files whose bytes differ, and nothing else:
  - changed files beyond the pre-lock budget are left to the tiers;
  - a changed tier-3 file is listed, not run;
  - a guard an older tree lacks is listed and skipped;
  - a new file is judged by its exit code alone, and a recorded file as the tier runner judges it.
- **ids** passes additions from the declared files only and exactly the declared removals. It
  refuses an undeclared removal, a declared removal still present, an addition outside the declared
  files, a new collection error, and a listing that is truncated or whose collection was
  interrupted.
- **The pre-lock verdict** defers a file that reached the cap to the tiers under the lock, never
  refusing it, unless it failed a test before the cap.
- **The base cache** finds only complete entries of the same key, keeps the first of two publishes,
  and never keys a dirty base.
- **crossrev-verdict** passes identical sets, and a difference only where it is declared, exactly.
- **G1's plan** places every world once, from the last passing G1's seconds where it has them, and
  the merge refuses a world saved twice.
- **The cache qualification's verdict** (cache_qualify.sh) passes only when every criterion holds.
  Each criterion's failure is planted once:
  - outcomes per test ID, completeness and coverage lost to time, apart;
  - G1 bitwise on one CPU per shard;
  - the planted controls as their runs without the cache;
  - FR's set and its 3 GiB cap;
  - crossrev and the replication check;
  - no cache or verification error, and no out-of-memory kill;
  - peak RSS per process and anonymous memory per stage within their factors;
  - the cache engaged: written in COLD, read in WARM;
  - the offline comparison of caches A and B run, its classes and machine-code differences noted;
  - the shared default cache folder untouched.

  It reports the cross-revision hit rate by programs and by seconds.
- **gate.sh** runs end to end with a stub interpreter, a private lock and this process's own CPU,
  so no case can reach a real lane, start a unit or run the engine. It shows that:
  - a pre-lock refusal never takes the lock;
  - an incomplete base listing is refused, and never published to the cache;
  - a crossrev refusal stops before tiers and G1;
  - a declared program change goes on;
  - a passing gate takes crossrev, then tiers, then G1, and its second run reuses the cached base;
  - PRELOCK_ONLY stops after the pre-lock steps, without queueing;
  - a used OUT is refused, so a stale verdict is never reported again;
  - a flock killed while it waits runs nothing.
- **Stacks** (stack.sh) run in a scratch Git checkout with the same stub, and a freezer that copies
  the tracked files:
  - a passing stack's trial merges have main and then each trial as first parents, the head's
    measured rows folded, and the stack gate's line before the message's trailers;
  - a planted failure in the middle head (a tier file, a crossrev set, a G1 world) is rerun alone
    on the intermediate trees, nearest first, blames that head, and the stack is re-gated without it;
  - a conflict refuses the stack with its paths (and a declared resolution is used), a head's own
    pre-lock record must have passed for its revision, and each declaration fault is refused;
  - the blame of each trail, and the failing stage read from the gate's log.
- **The scope map** (scope.py, the recorder, `test_tiers.py run --scope-map`) is built for real on
  a tiny snapshot of four test files:
  - it records imports, reads, listings and a child the map cannot see;
  - the selection holds every file whose recorded paths changed (a read file, an imported module, a
    new name in a listed folder, the file itself, a file that would replace a namespace package, one
    that would shadow a module, one of pytest's configuration files), and nothing else under
    `--always none`; the readers and scanners are D229's always-run set;
  - a planted read of a repository file pulls its test in, once the map is rebuilt;
  - a library's own discovery counts only the names it can use, a folder opened by descriptor is a
    listing, and the recorder leaves os.supports_* (so shutil's rmtree) as it found them;
  - the selection is refused for each planted fault (stopped, failed, old, missing or earlier map,
    src/);
  - the nightly run takes the free lane, and publishes its map or stops selection;
  - gate.sh runs only the selection's files, CHECKS drops crossrev and G1, and SELECT_ALWAYS names
    D229's rule.
- **D358's kinds and children**, on a second tiny snapshot (four test files, run under strace too):
  - each kind of question is recorded, and only it: a folder a library listed first, a size, an
    executable bit, a descriptor-relative open, an entry's size, a name that becomes a folder, a
    module an import or find_spec did not find, a name that would shadow another;
  - a child whose environment was rebuilt or replaced records itself; git on the tree and outside
    it, uname -p, an absent interpreter and a killed child that touched nothing leave the file
    mapped; a child masked by a recorded one, a shell that became Python, and a forked process that
    became a program do not, and only they are named;
  - a file that C code opened is missing from its entry: the trace marks the entry incomplete, and a
    reader whose entry no trace checked is always run; the fallback rule counts beside it;
  - a trace that is not whole checks nothing, and a listing or a program that it alone saw counts.
- **Hermetic:** every tool runs here with the tools' own variables and git's dropped from the
  environment, then only what each test sets. A landing gate runs this file with its own
  ADDITIONS_FROM, LANE and the rest (T66, 20 November): planted in this process's environment, they
  reach neither a test's gate nor its stack, and the list covers every variable the tools read.
- **Cold by construction** (D321 R1 and R2; JAX's persistent compilation cache):
  - a caller's cache settings reach none of a gate's processes, and the cold check runs after the
    pre-lock tests, crossrev, the tiers and G1;
  - a cache entry planted under the gate's outputs at each stage refuses the gate there, as its own
    fault (not bisected);
  - every gate script disables the cache, and the check finds entries by their names only;
  - on the real tier runner, a caller's settings reach no test process, measure marks its record
    cold, and only run --jax-cache FOLDER runs warm, its record naming the folder;
  - the nightly logs the cache disabled and its cold check.
"""

import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATES = ROOT / "scripts" / "gates"
GATE = GATES / "gate.sh"


def load():
    sys.path.insert(0, str(GATES))
    spec = importlib.util.spec_from_file_location("gate_steps", GATES / "gate_steps.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


steps = load()

# Every variable the gate tools read from the environment (gate.sh, stack.sh, nightly_tiers.sh,
# gate_steps.py and the recorder; a row below keeps the list whole), with git's own, is dropped from
# every invocation here, and from this process for the steps run in it. Each test then sets only
# what it means to (T66, 20 November 2026: the landing gate's ADDITIONS_FROM reached the tests' gates).
TOOL_ENV = frozenset((
    "ADDITIONS_FROM", "BASELINE", "BASE_S", "C1", "CELLS_SCOPE_LOG", "CELLS_SCOPE_ROOT", "CHECKS",
    "CPUS_A", "CPUS_B", "CROSSREV_EXPECTED", "CROSSREV_SETS", "FREEZE", "GATE_CACHE", "GATE_CPUS",
    "GATE_LOCK", "HOSTPY", "LANE", "LOCK_A", "LOCK_B", "NIGHTLY", "POLL", "PRELOCK", "PRELOCK_CPU",
    "PRELOCK_NICE", "PRELOCK_ONLY", "PRELOCK_TEST_SECONDS", "PRE_CPU", "PY", "REC", "REMOVED_OK_FILE",
    "REPO", "RESTACK", "SELECT", "SELECTION_STOPPED", "SELECT_ALWAYS", "TIERS", "TRACE", "WAIT_FREE"))
LOCALS = frozenset(("TR", "GD"))  # gate.sh's and stack.sh's own, assigned before they are expanded


def scrubbed(name):
    return name in TOOL_ENV or name.startswith("GIT_")


def clean_env(*parts, **extra):
    """This process's environment without the tools' variables and git's, then PARTS and EXTRA."""
    env = {k: v for k, v in os.environ.items() if not scrubbed(k)}
    for part in parts:
        env.update(part)
    env.update(extra)
    return env


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    for name in [n for n in os.environ if scrubbed(n)]:
        monkeypatch.delenv(name)
EMPTY = steps.EMPTY_PATCH
GUARD_TEXT = "def test_guard():\n    pass\n"


def snapshot_tree(root, rev, *, clean=True, extra=None, program="p1\n", ids=None):
    """A fake execution snapshot: the guard files, one more test file, its tier record, and the
    files the stub interpreter reads (ids.txt, program.txt)."""
    root.mkdir(parents=True)
    (root / "SNAPSHOT.json").write_text(json.dumps(
        {"status": "complete", "git_revision": rev, "patch_sha256": EMPTY if clean else "dirty"}))
    files = {g: GUARD_TEXT for g in steps.GUARDS}
    files["tests/unit/test_other.py"] = "def test_other():\n    pass\n"
    files.update(extra or {})
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    rows = [{"file": f, "seconds": 0.5, "exit_code": 0, "counts": {"passed": 1}}
            for f in sorted(files) if f.startswith("tests/") and Path(f).name.startswith("test_")]
    (root / "tests" / "test_tiers.json").write_text(json.dumps(
        {"kind": "cells.test_tiers@1", "fast_seconds": 20.0, "cap_seconds": 90.0,
         "tiers": {"1": rows, "2": [], "3": []}}))
    (root / "program.txt").write_text(program)
    (root / "ids.txt").write_text("\n".join(ids or ["tests/unit/test_other.py::test_other"]) + "\n")
    return root


@pytest.fixture
def world(tmp_path):
    """Base and head snapshots, crossrev's record with every set, and c1's and the baseline's
    manifests of two worlds."""
    base = snapshot_tree(tmp_path / "base", "b" * 40)
    head = snapshot_tree(tmp_path / "head", "c" * 40)
    record = tmp_path / "record"
    for name in steps.xr().ORDER:
        (record / name).mkdir(parents=True)
        (record / name / "jaxprs.txt").write_text("p1\n")
    worlds = {"crossrev-base/w1": {"seconds": 3.0, "digests": {"x": "1"}},
              "protocol-w1/w2": {"seconds": 1.0, "digests": {"x": "1"}}}
    for name in ("c1", "baseline"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "manifest.json").write_text(json.dumps({"worlds": worlds}))
    env = {"REC": str(record), "C1": str(tmp_path / "c1"),
           "BASELINE": str(tmp_path / "baseline")}
    return {"tmp": tmp_path, "base": base, "head": head, "record": record, "env": env}


# ------------------------------------------------------------------------------------- preflight


def test_preflight_passes_clean_snapshots_and_a_complete_record(world):
    doc = steps.preflight(world["head"], world["base"], world["env"])
    assert doc["ok"], doc["problems"]


@pytest.mark.parametrize("plant, words", [
    ("record lacks a set", "lacks sets the runner requires"),
    ("unknown record folder", "does not know"),
    ("dirty head", "not clean"),
    ("declared file missing", "ADDITIONS_FROM names"),
    ("a check dropped with src/ changed", "a src/ change keeps the full gate"),
    ("tiers dropped", "CHECKS must hold tiers"),
])
def test_preflight_refuses_each_planted_fault(world, plant, words):
    env = dict(world["env"])
    if plant == "record lacks a set":
        (world["record"] / "replication" / "jaxprs.txt").unlink()
        (world["record"] / "replication").rmdir()
    elif plant == "unknown record folder":
        (world["record"] / "newset").mkdir()
    elif plant == "dirty head":
        doc = json.loads((world["head"] / "SNAPSHOT.json").read_text())
        (world["head"] / "SNAPSHOT.json").write_text(json.dumps(dict(doc, patch_sha256="x")))
    elif plant == "declared file missing":
        env["ADDITIONS_FROM"] = "tests/unit/test_absent.py"
    elif plant == "a check dropped with src/ changed":
        env["CHECKS"] = "crossrev tiers"
        for tree, digest in ((world["head"], "1"), (world["base"], "2")):
            doc = json.loads((tree / "SNAPSHOT.json").read_text())
            doc["files"] = {"src/cells/x.py": {"sha256": digest}}
            (tree / "SNAPSHOT.json").write_text(json.dumps(doc))
    elif plant == "tiers dropped":
        env["CHECKS"] = "crossrev g1"
    doc = steps.preflight(world["head"], world["base"], env)
    assert not doc["ok"] and any(words in p for p in doc["problems"]), doc["problems"]


# --------------------------------------------------------------------------- pre-lock test files


def test_select_chooses_the_guards_and_the_changed_files_only(world):
    head = world["head"]
    (head / "tests/unit/test_other.py").write_text("def test_other():\n    assert True\n")
    (head / "tests/unit/test_new.py").write_text("def test_new():\n    pass\n")
    (head / "tests/unit/test_slow.py").write_text("def test_slow():\n    pass\n")
    doc = json.loads((head / "tests/test_tiers.json").read_text())
    doc["tiers"]["3"] = [{"file": "tests/unit/test_slow.py", "seconds": 90.0, "exit_code": None,
                          "counts": {}}]
    (head / "tests/test_tiers.json").write_text(json.dumps(doc))
    subset, report = steps.select(head, world["base"], "tests/test_tiers.json")
    tier1 = sorted(r["file"] for r in subset["tiers"]["1"])
    assert tier1 == sorted([*steps.GUARDS, "tests/unit/test_other.py"])
    assert [r["file"] for r in subset["tiers"][steps.NEW_TIER]] == ["tests/unit/test_new.py"]
    assert report["tier3_not_run"] == ["tests/unit/test_slow.py"]
    tight = steps.select(head, world["base"], "tests/test_tiers.json", budget=0.1)[1]
    assert tight["left_to_tiers"] == ["tests/unit/test_new.py", "tests/unit/test_other.py"]
    assert tight["files"] == len(steps.GUARDS)  # Over the budget: only the guard set runs early.
    unchanged = steps.select(world["base"], world["base"], "tests/test_tiers.json")[1]
    assert unchanged["changed"] == [] and unchanged["files"] == len(steps.GUARDS)
    (world["base"] / steps.GUARDS[0]).unlink()  # An older tree without a guard: skipped, listed.
    older = steps.select(world["base"], world["base"], "tests/test_tiers.json")[1]
    assert older["guards_absent"] == [steps.GUARDS[0]] and older["files"] == len(steps.GUARDS) - 1


@pytest.mark.parametrize("plant, ok", [
    (None, True), ("recorded file changed", False), ("new file fails", False),
    ("new file skips", True), ("file not run", False),
    ("recorded file timed out", True), ("new file timed out", True),
    ("timed out after a failure", False)])
def test_the_prelock_verdict(tmp_path, plant, ok):
    subset = {"tiers": {"1": [{"file": "a", "exit_code": 0, "counts": {"passed": 1}}], "2": [],
                        steps.NEW_TIER: [{"file": "n", "exit_code": 0, "counts": {}}]}}
    files = [{"file": "a", "exit_code": 0, "counts": {"passed": 1}},
             {"file": "n", "exit_code": 0, "counts": {"passed": 2}}]
    changed = []
    if plant == "recorded file changed":
        changed = [{"file": "a", "why": ["passed below the record"], "now": [1, {}]}]
    elif plant == "new file fails":
        files[1] = {"file": "n", "exit_code": 1, "counts": {"failed": 1}}
    elif plant == "new file skips":  # The tier runner flags it against its empty row; not here.
        files[1] = {"file": "n", "exit_code": 0, "counts": {"passed": 1, "skipped": 1}}
        changed = [{"file": "n", "why": ["skipped above the record"], "now": [0, {}]}]
    elif plant == "file not run":
        files = files[:1]
    elif plant == "recorded file timed out":  # Deferred to the tiers under the lock, not refused.
        files[0] = {"file": "a", "exit_code": None, "timed_out": True, "counts": {}}
        changed = [{"file": "a", "why": ["exit code, failed or error count differs"],
                    "now": [None, {}]}]
    elif plant == "new file timed out":
        files[1] = {"file": "n", "exit_code": None, "timed_out": True, "counts": {}}
    elif plant == "timed out after a failure":
        files[0] = {"file": "a", "exit_code": None, "timed_out": True, "counts": {"failed": 1}}
        changed = [{"file": "a", "why": ["exit code, failed or error count differs"],
                    "now": [None, {"failed": 1}]}]
    (tmp_path / "subset.json").write_text(json.dumps(subset))
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "run.json").write_text(json.dumps({"files": files}))
    (tmp_path / "run" / "summary.json").write_text(json.dumps({"changed_vs_record": changed}))
    doc = steps.prelock_verdict(tmp_path / "subset.json", tmp_path / "run")
    assert doc["ok"] is ok, doc
    if plant in ("recorded file timed out", "new file timed out"):
        assert doc["deferred_to_the_tiers"] == ["a" if plant.startswith("recorded") else "n"]


# ------------------------------------------------------------------------------------------- IDs


def listing(prefix, ids, errors=(), collected=None, exit_code=None):
    """One side's collection as gate.sh writes it: the listing, the log with pytest's summary line
    (collected defaults to the listing's size) and, when given, the exit code."""
    n = len(ids) if collected is None else collected
    Path(prefix + ".ids").write_text("\n".join(sorted(ids)) + "\n")
    Path(prefix + ".log").write_text("".join(f"ERROR {e} - boom\n" for e in errors)
                                     + f"{n} tests collected in 0.01s\n")
    if exit_code is not None:
        Path(prefix + ".json").write_text(json.dumps({"exit": exit_code, "ids": len(ids)}))


@pytest.mark.parametrize("plant, ok, key", [
    (None, True, None),
    ("undeclared removal", False, "missing"),
    ("declared removal still present", False, "listed_but_present"),
    ("addition outside the declared files", False, "outside_the_branch_files"),
    ("new collection error", False, "new_errors"),
    ("truncated base listing", False, "incomplete_listing"),
    ("interrupted base collection", False, "incomplete_listing"),
])
def test_ids_pass_only_as_declared(tmp_path, plant, ok, key):
    base = {"tests/a.py::t1", "tests/a.py::t2[x]", "tests/b.py::t3"}
    head = (base - {"tests/a.py::t2[x]"}) | {"tests/c.py::t4"}
    removed, errors = {"tests/a.py::t2[x]"}, []
    if plant == "undeclared removal":
        removed = set()
    elif plant == "declared removal still present":
        head |= {"tests/a.py::t2[x]"}
    elif plant == "addition outside the declared files":
        head |= {"tests/b.py::t5"}
    elif plant == "new collection error":
        errors = ["tests/c.py"]
    collected, exit_code = None, None
    if plant == "truncated base listing":  # pytest counted one more than the listing holds.
        collected = len(base) + 1
    elif plant == "interrupted base collection":
        exit_code = 2
    listing(str(tmp_path / "base"), base, collected=collected, exit_code=exit_code)
    listing(str(tmp_path / "head"), head, errors)
    doc = steps.ids_check(str(tmp_path / "base"), str(tmp_path / "head"), ["tests/c.py"], removed)
    assert doc["ok"] is ok, doc
    if key:
        assert doc[key], doc


# -------------------------------------------------------------------------------- the base cache


def test_the_cache_finds_only_complete_entries_of_its_key(world, tmp_path):
    root, src = tmp_path / "cache", tmp_path / "src"
    src.mkdir()
    (src / "result.txt").write_text("base side\n")
    py = sys.executable
    assert steps.cache_find(root, "ids", world["base"], ["a"], py) is None
    entry = steps.cache_publish(root, "ids", world["base"], src, ["a"], py)
    assert (entry / "result.txt").read_text() == "base side\n"
    assert steps.cache_find(root, "ids", world["base"], ["a"], py) == entry
    assert steps.cache_find(root, "ids", world["base"], ["b"], py) is None  # Another key.
    assert steps.cache_find(root, "crossrev", world["base"], ["a"], py) is None  # Another kind.
    (src / "result.txt").write_text("a later run\n")
    assert steps.cache_publish(root, "ids", world["base"], src, ["a"], py) == entry
    assert (entry / "result.txt").read_text() == "base side\n"  # The first publish is kept.
    (entry / "CACHE.json").unlink()  # A partial entry is never found.
    assert steps.cache_find(root, "ids", world["base"], ["a"], py) is None
    doc = json.loads((world["head"] / "SNAPSHOT.json").read_text())
    (world["head"] / "SNAPSHOT.json").write_text(json.dumps(dict(doc, patch_sha256="x")))
    with pytest.raises(SystemExit, match="not cached"):
        steps.cache_publish(root, "ids", world["head"], src, ["a"], py)


# ------------------------------------------------------------------------------------- crossrev


def sides(tmp_path, head_extra=False, compare_differs=()):
    for side in ("base", "head"):
        folder = tmp_path / side / "kinds"
        folder.mkdir(parents=True)
        (folder / "f.txt").write_text("p1\n")
        (folder / "g.txt").write_text("q\n")
        if side == "head" and head_extra:
            (folder / "h.txt").write_text("new\n")
    (tmp_path / "cmp").mkdir()
    lines = [f"{n} {'DIFFERS' if n in compare_differs else 'identical'}"
             for n in ("f.txt", "g.txt")]
    verdict = "verdict differs" if compare_differs else "verdict identical"
    (tmp_path / "cmp" / "compare-kinds.txt").write_text("\n".join([*lines, verdict]) + "\n")
    return tmp_path / "base", tmp_path / "head", tmp_path / "cmp"


@pytest.mark.parametrize("plant, declared, ok", [
    (None, None, True),
    ("a file differs", None, False),
    ("a file differs", "kinds/f.txt", True),
    (None, "kinds/f.txt", False),  # A declared file must differ: the list is exact.
    ("a file differs", "kinds/g.txt", False),
    ("the listings differ", None, False),
])
def test_crossrev_passes_a_difference_only_where_declared(tmp_path, plant, declared, ok):
    base, head, cmp = sides(tmp_path, head_extra=plant == "the listings differ",
                            compare_differs=("f.txt",) if plant == "a file differs" else ())
    expected = None
    if declared:
        expected = tmp_path / "expected.txt"
        expected.write_text(declared + "\n")
    doc = steps.crossrev_verdict(base, head, cmp, ["kinds"], expected)
    assert doc["ok"] is ok, doc


# ------------------------------------------------------------------------------------------- G1


def test_g1_plans_every_world_once_from_the_last_passing_seconds(tmp_path):
    worlds = {f"set{i % 3}/w{i}": {"seconds": 1.0} for i in range(20)}
    (tmp_path / "manifest.json").write_text(json.dumps({"worlds": worlds}))
    (tmp_path / "seconds.json").write_text(json.dumps({"seconds": {"set0/w0": 100.0}}))
    plan, source = steps.g1_plan(tmp_path, 4, tmp_path / "seconds.json")
    placed = [f"{g['set']}/{w}" for s in plan for g in s["groups"] for w in g["worlds"]]
    assert sorted(placed) == sorted(worlds) and source == {"current": 1, "baseline": 19}
    heavy = next(s for s in plan if any("w0" in g["worlds"] for g in s["groups"]))
    assert heavy["seconds"] == 100  # The long world alone on its shard: the plan saw its seconds.


def test_g1_merge_refuses_a_world_saved_twice(tmp_path):
    for k in (0, 1):
        part = tmp_path / "parts" / f"part-{k}-0"
        (part / "s").mkdir(parents=True)
        (part / "s" / "w.json").write_text("{}")
        (part / "manifest.json").write_text(json.dumps({"worlds": {"s/w": {"seconds": 1.0}}}))
    with pytest.raises(SystemExit, match="saved twice"):
        steps.g1_merge(tmp_path / "parts", tmp_path / "merged")


# ------------------------------------------------------------------- the cache qualification


def qualification(tmp_path, plant=None):
    """cache_qualify.sh's outputs for a qualification that passes, with one planted fault."""
    out = tmp_path / "q"

    def put(path, doc):
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        (out / path).write_text(doc if isinstance(doc, str) else json.dumps(doc))

    put("g1-plan.json", [{"seconds": 1, "groups": [{"set": "s", "worlds": ["a", "b"]}]}])
    put("tier3-tiers.json", {"tiers": {"1": [], "2": [], "3": [{"file": "t"}]}})
    put("off/reuse.json", {"cache_entries": int(plant == "reused")})
    status = "timeout" if plant == "off3" else "pass"
    put("off/tier3-record.json", {"files": {"t": {"status": status}}})
    runs = [(a, "tiers", 3) for a in ("cold", "warm", "warm2", "xrev-head")]
    for arm, stage, n in runs + [(a, "tier3", 1) for a in ("cold", "warm", "warm2")]:
        blocking = []
        if plant == "outcome" and (arm, stage) == ("warm", "tiers"):
            blocking = [{"file": "f", "kind": "new failure", "test": "t1"}]
        if plant == "time" and (arm, stage) == ("warm2", "tier3"):
            blocking = [{"file": "t", "kind": "new timeout"}]
        missing = ["g"] if plant == "missing" and (arm, stage) == ("cold", "tiers") else []
        put(f"{arm}/{stage}/diff.json", {"blocking": blocking, "caps_differ": [], "files_read": n,
                                         "record_files_not_in_runs": missing})
    for arm in ("off", "cold", "warm", "warm2", "xrev-base", "xrev-head"):
        equal = 1 if plant == "g1" and arm == "warm2" else 2
        put(f"{arm}/g1/compare.json", {"verdict": "identical" if equal == 2 else "differs",
                                       "worlds": 2, "equal": equal, "problems": []})
        put(f"{arm}/g1/shard-0.cpus", "2\n" if plant == "cpus" and arm == "cold" else "1\n")
        kb = "1300" if plant == "rss" and arm == "warm" else "1000"
        put(f"{arm}/g1/rss-0-0.txt", kb + " 9\n")
    for name, n in (("unplanted", 2), ("planted", 2), ("c2prime", 1)):
        masked = plant == "masked" and name == "planted"
        put(f"negative/{name}/compare.json", {"verdict": "differs" if masked else "identical",
                                              "worlds": n, "equal": n - masked, "problems": []})
    for arm in ("off", "cold", "warm", "warm2"):
        put(f"{arm}/fr/verdict.json", {"passed": not (plant == "fr" and arm == "cold")})
        kb = 3200000 if plant == "frcap" and arm == "warm2" else 2000000
        put(f"{arm}/fr/rss-q0.log", "Command exited with non-zero status 1\n"
            f"{kb} 9.0 1 /py -m q {out / arm / 'fr'}/part\n")
    for arm in ("cold", "warm", "warm2"):
        same = 1 if plant == "crossrev" and arm == "warm" else 2
        put(f"{arm}/crossrev/verdict.json", {"ok": same == 2, "sets": 2, "identical": same})
        failed = plant == "replication" and arm == "warm2"
        put(f"{arm}/replication/done", "1\n" if failed else "0\n")
    if plant == "read error":
        put("warm/g1/shard-0.log", "UserWarning: Error reading persistent compilation cache entry "
            "for 'k'\n")
    if plant != "compare":
        put("cache-compare.json", {"common_programs": 5, "kinds": {"equal bytes": 4,
                                                                  "different machine code": 1},
                                   "different machine code": ["jit_k-1-cache"]})
    engaged = plant != "engaged"

    def stage(arm, name, before, after, seconds, anon=1000, oom=0):
        before, after = (before, after) if engaged else (0, 0)
        return {"arm": arm, "stage": name, "exit": 0, "seconds": seconds, "entries_before": before,
                "entries_after": after, "anon_peak": anon, "oom_kills": oom}

    warm_g1 = 100 if plant == "engaged" else 70 if plant == "slowwarm" else 30
    rows = [stage("off", "g1", 0, 0, 100), stage("off", "fr+tier3", 0, 0, 50),
            stage("cold", "tiers", 0, 10, 200), stage("cold", "g1", 10, 15, 100,
                                                      oom=int(plant == "oom")),
            stage("cold", "fr+tier3", 15, 17, 60), stage("cold", "crossrev", 17, 17, 30)]
    for arm in ("warm", "warm2"):
        grow = int(plant == "added" and arm == "warm2")
        rows += [stage(arm, "tiers", 17, 17 + grow, 120,
                       anon=2000 if plant == "anon" and arm == "warm" else 1000),
                 stage(arm, "g1", 17 + grow, 17 + grow, 100 if plant == "engaged" else warm_g1),
                 stage(arm, "fr+tier3", 17, 17, 40), stage(arm, "crossrev", 17, 17, 30)]
    rows += [stage("xrev-base", "tiers", 0, 8, 200), stage("xrev-base", "g1", 8, 12, 100),
             stage("xrev-head", "tiers", 12, 13, 130), stage("xrev-head", "g1", 13, 13, 35),
             stage("negative", "unplanted", 17, 20, 90), stage("negative", "planted", 20, 23, 90),
             stage("negative", "c2prime", 23, 23, 5)]
    put("stages.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
    put("default-cache-before.json", {"files": 78, "newest": 1})
    put("default-cache-after.json", {"files": 79 if plant == "default" else 78, "newest": 1})
    return out


def test_a_clean_qualification_passes_with_its_cross_revision_figures(tmp_path):
    doc = steps.cache_verdict(qualification(tmp_path))
    assert doc["passed"], [k for k, v in doc["checks"].items() if not v]
    notes = doc["notes"]
    assert notes["cross-revision hit rate by programs: 1 - the head's new entries / its programs"] \
        == round(1 - 1 / 15, 3)
    assert notes["cross-revision saving by seconds, tiers and G1: (cold - xrev) / (cold - warm)"] \
        == round((300 - 165) / (300 - 150), 3)


@pytest.mark.parametrize("plant, check", [
    ("outcome", "warm tiers: outcomes per test ID as OFF's"),
    ("time", "warm2 tier3: no coverage lost to time"),
    ("missing", "cold tiers: every file read against OFF's record at OFF's cap"),
    ("off3", "off: every tier-3 stage file ran to its end"),
    ("reused", "off: its tier run wrote no persistent cache entry"),
    ("g1", "warm2 G1: 2 of 2 worlds bitwise as c1's"),
    ("cpus", "cold G1: every shard on one CPU, as c1's"),
    ("masked", "negative planted: bitwise as its own run without the cache"),
    ("fr", "cold FR: the set passes"),
    ("frcap", "warm2 FR: every process under its unit's 3 GiB"),
    ("crossrev", "warm crossrev: every set identical to the record"),
    ("replication", "warm2 replication: 55 of 55, by the lead's check"),
    ("read error", "no cache read or write error in any log"),
    ("compare", "the offline comparison of caches A and B ran"),
    ("oom", "no out-of-memory kill in any stage"),
    ("rss", "warm g1: each process's peak RSS within 1.25 times OFF's"),
    ("anon", "warm tiers: the stage's largest anonymous memory within 1.5 times cold's"),
    ("engaged", "cold tiers: wrote cache entries (the cache engaged)"),
    ("added", "warm2: added no cache entry (every program read)"),
    ("slowwarm", "warm G1: under 0.6 of cold's seconds (read, not compiled)"),
    ("default", "the shared default cache folder is unchanged"),
])
def test_each_failed_criterion_fails_the_qualification(tmp_path, plant, check):
    doc = steps.cache_verdict(qualification(tmp_path, plant))
    assert not doc["passed"] and doc["checks"][check] is False, doc["checks"]


def test_qualify_subsets_keeps_rows_only_and_refuses_an_unknown_file(tmp_path):
    record = {"kind": "k", "measured": ["m"], "measured_provenance": [{"root": "/scratch/x"}],
              "tiers": {"1": [{"file": "a"}, {"file": "b"}], "2": [{"file": "c"}],
                        "3": [{"file": "e"}]}}
    (tmp_path / "record.json").write_text(json.dumps(record))
    steps.qualify_subsets(tmp_path / "record.json", tmp_path, ["e", "b"])
    tier3 = json.loads((tmp_path / "tier3-tiers.json").read_text())
    assert "measured_provenance" not in tier3 and "measured" not in tier3
    assert [r["file"] for r in tier3["tiers"]["3"]] == ["b", "e"] and not tier3["tiers"]["1"]
    with pytest.raises(SystemExit, match="not in"):
        steps.qualify_subsets(tmp_path / "record.json", tmp_path, ["e", "zz"])


def _load_compare():
    spec = importlib.util.spec_from_file_location("cache_compare", GATES / "cache_compare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cache_compare_tells_reordered_kernels_from_different_machine_code(tmp_path):
    """Executables as XLA:CPU serializes them: kernels as length-delimited ELF objects, in an
    order that varies, and paths embedded (the cache's own, and the compiling tree's)."""
    compare = _load_compare()

    def kernel(name, code):
        elf = b"\x7fELF" + code
        return b"\x12" + bytes([len(name)]) + name + b"\n" + bytes([len(elf)]) + elf

    one, two = tmp_path / "cache-A", tmp_path / "cache-B"
    k1, k2 = kernel(b"add", b"\x01" * 20), kernel(b"mul", b"\x02" * 30)
    entries = {
        "jit_same-1-cache": (k1 + k2, k1 + k2),
        "jit_order-2-cache": (k1 + k2, k2 + k1),
        "jit_paths-3-cache": (b"opt " + str(one).encode() + b" /tree/head " + k1,
                              b"opt " + str(two).encode() + b" /tree/base " + k1),
        "jit_meta-4-cache": (b"m1" + k1, b"m2" + k1),
        "jit_code-5-cache": (k1 + k2, k1 + kernel(b"mul", b"\x03" * 30)),
    }
    for folder, side in ((one, 0), (two, 1)):
        folder.mkdir()
        for name, pair in entries.items():
            (folder / name).write_bytes(pair[side])
    (one / "jit_only-6-cache").write_bytes(k1)
    doc = compare.compare(one, two, [("/tree/head", "/tree/base")], read=lambda p: p.read_bytes())
    assert doc["common_programs"] == 5 and doc["only_in_one"] == 1
    assert doc["kinds"] == {"equal bytes": 2, "same objects, another order": 1,
                            "same objects, other bytes": 1, "different machine code": 1}
    assert doc["different machine code"] == ["jit_code-5-cache"]
    assert doc["same objects, other bytes"] == ["jit_meta-4-cache"]


# ---------------------------------------------------------------------- gate.sh, end to end

STUB = r'''
import json, os, sys
from pathlib import Path
args, cwd = sys.argv[1:], Path.cwd()
def note(text):
    with open(os.environ["STUB_LOG"], "a") as f:
        f.write(text + "\n")
if args[:2] == ["-I", "-c"]:  # The interpreter's identity.
    print("0.0.1 0.0.1 0.0.1"); sys.exit(0)
a = [x for x in args if x not in ("-B", "-u")]
if os.environ.get("JAX_ENABLE_COMPILATION_CACHE") != "false" or "JAX_COMPILATION_CACHE_DIR" in os.environ:
    note("warm " + " ".join(a[:2]))  # A process that would use a compilation cache (D321 R2).
PLANT = (cwd / "jax_entry.txt").read_text().strip() if (cwd / "jax_entry.txt").exists() else ""
def plant(folder):  # The entry a process that turned the cache back on would leave.
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ("jit_f-" + "0" * 64 + "-cache")).write_bytes(b"x")
if a[:2] == ["-m", "pytest"]:
    note("collect " + cwd.name)
    ids = [l for l in (cwd / "ids.txt").read_text().splitlines() if "::" in l]
    n = int((cwd / "collected.txt").read_text()) if (cwd / "collected.txt").exists() else len(ids)
    print("\n".join(ids)); print(f"{n} tests collected in 0.01s"); sys.exit(0)
if a[:2] == ["scripts/test_tiers.py", "fold"]:  # The tree's own fold, for real.
    import runpy
    sys.argv = a
    runpy.run_path(str(cwd / a[0]), run_name="__main__"); sys.exit(0)
if a[:2] == ["scripts/test_tiers.py", "run"]:
    tiers, i = [], a.index("--tier") + 1
    while i < len(a) and not a[i].startswith("--"):
        tiers.append(a[i]); i += 1
    doc = json.loads(Path(a[a.index("--tiers") + 1]).read_text())
    failing = set((cwd / "fail.txt").read_text().split()) if (cwd / "fail.txt").exists() else set()
    files, changed = [], []
    for t in tiers:
        for row in doc["tiers"].get(t, []):
            bad = row["file"] in failing
            counts = {"failed": 1} if bad else {"passed": 1}
            files.append({"file": row["file"], "exit_code": int(bad), "counts": counts})
            if bad:
                changed.append({"file": row["file"], "why": ["failed"], "now": [1, counts]})
    out = Path(a[a.index("--out") + 1]); out.mkdir(parents=True, exist_ok=True)
    if (PLANT == "prelock" and "9" in tiers) or (PLANT == "tiers" and tiers == ["1", "2"]):
        plant(out / "outputs" / "x" / "Cells" / "cache" / "jax")
    (out / "run.json").write_text(json.dumps({"files": files}))
    (out / "summary.json").write_text(json.dumps({"changed_vs_record": changed}))
    note("tiers " + " ".join(tiers) + " " + cwd.name)
    print(json.dumps({"files": len(files), "changed": len(changed)})); sys.exit(int(bool(changed)))
if a[:1] == ["-m"] and a[2] == "compare":
    one, two = Path(a[3]), Path(a[4])
    note("compare " + one.parent.name + "/" + one.name)
    differs = False
    for f in sorted(one.iterdir()):
        same = (two / f.name).is_file() and (two / f.name).read_bytes() == f.read_bytes()
        print(f.name, "identical" if same else "DIFFERS"); differs |= not same
    print("verdict differs" if differs else "verdict identical"); sys.exit(int(differs))
if a[:1] == ["-m"]:  # A crossrev action: MODULE ACTION TARGET [SET].
    target = Path(a[3]); target.mkdir(parents=True, exist_ok=True)
    note("crossrev " + a[2] + " " + target.name + " " + cwd.name)
    (target / (a[2] + ".txt")).write_text((cwd / "program.txt").read_text()); sys.exit(0)
if a[:2] == ["validation/results_baseline.py", "save"]:
    part, set_name = Path(a[2]), a[a.index("--sets") + 1]
    worlds = a[a.index("--worlds") + 1:a.index("--from")]
    note("save " + set_name + " " + cwd.name)
    (part / set_name).mkdir(parents=True, exist_ok=True)
    if PLANT == "save":  # Beside the parts: a part's own folders are its sets, which G1 merges.
        plant(part.parent.parent / ("jax-" + part.name))
    manifest = {"worlds": {}}
    planted = (cwd / "g1.txt").read_text().split() if (cwd / "g1.txt").exists() else []
    for w in worlds:
        (part / set_name / (w + ".json")).write_text("{}")
        digest = "2" if set_name + "/" + w in planted else "1"
        manifest["worlds"][set_name + "/" + w] = {"seconds": 2.5, "digests": {"x": digest}}
    (part / "manifest.json").write_text(json.dumps(manifest)); sys.exit(0)
if a[:2] == ["validation/results_baseline.py", "compare"]:
    note("g1 compare")
    x = json.loads((Path(a[2]) / "manifest.json").read_text())["worlds"]
    y = json.loads((Path(a[3]) / "manifest.json").read_text())["worlds"]
    rows = [{"world": k, "equal": k in y and x[k]["digests"] == y[k]["digests"]} for k in sorted(x)]
    ok = x.keys() == y.keys() and all(r["equal"] for r in rows)
    if "--output" in a:
        Path(a[a.index("--output") + 1]).write_text(json.dumps({"rows": rows, "problems": []}))
    print(("identical" if ok else "differs") + f": {len(y)} of {len(x)} worlds")
    sys.exit(int(not ok))
print("stub: unknown call", args, file=sys.stderr); sys.exit(3)
'''


@pytest.fixture
def gate(world):
    """gate.sh's environment on a custom lane: a private lock, this process's own CPU, the stub
    interpreter for every engine call, and a private cache."""
    tmp = world["tmp"]
    (tmp / "stub.py").write_text(STUB)
    py = tmp / "py"
    py.write_text(f'#!/bin/bash\nexec "{sys.executable}" -I "{tmp / "stub.py"}" "$@"\n')
    py.chmod(0o755)
    cpu = str(sorted(os.sched_getaffinity(0))[0])
    env = dict(world["env"], LANE="custom", GATE_LOCK=str(tmp / "lane.lock"),
               GATE_CPUS=cpu, PRELOCK_CPU=cpu, PRELOCK_NICE="0", PY=str(py),
               HOSTPY=sys.executable, GATE_CACHE=str(tmp / "cache"), STUB_LOG=str(tmp / "calls"),
               CROSSREV_SETS="kinds")
    world["envs"] = env
    return world


def run_gate(world, out, **extra):
    env = clean_env(world["envs"], extra)
    (world["tmp"] / "calls").write_text("")
    done = subprocess.run(["bash", str(GATE), str(world["head"]), str(world["base"]), str(out)],
                          env=env, capture_output=True, text=True, timeout=120)
    calls = (world["tmp"] / "calls").read_text().splitlines()
    log = (out / "gate.log").read_text()
    return done.returncode, calls, log


def test_a_passing_gate_takes_crossrev_then_tiers_then_g1_and_reuses_the_cached_base(gate):
    code, calls, log = run_gate(gate, gate["tmp"] / "out1")
    assert code == 0, log
    first = {kind: next(i for i, c in enumerate(calls) if c.startswith(kind))
             for kind in ("collect", "crossrev", "tiers 1 2 head", "save", "g1 compare")}
    assert first["collect"] < first["crossrev"] < first["tiers 1 2 head"] < first["save"]
    assert "base listing published" in log and "crossrev base published" in log
    code, calls, log = run_gate(gate, gate["tmp"] / "out2")
    assert code == 0, log
    assert "base listing from the cache" in log and "crossrev base from the cache" in log
    assert "collect base" not in calls and not any(c.endswith(" base") for c in calls
                                                   if c.startswith("crossrev"))
    assert "worlds timed by the last passing G1 2" in log  # Its plan read the first run's seconds.


def test_prelock_only_stops_before_queueing(gate):
    out = gate["tmp"] / "out"
    code, calls, log = run_gate(gate, out, PRELOCK_ONLY="1")
    assert code == 0 and "prelock passed" in log and "not queued" in log
    assert "waiting for" not in log and not any(c.startswith("crossrev") for c in calls)


def test_the_gate_runs_every_process_cold_whatever_its_callers_environment(gate):
    """D321 R2: a caller's cache settings (an opted-in shell) reach none of a gate's processes, and
    the cold check runs after every stage."""
    code, calls, log = run_gate(gate, gate["tmp"] / "out", JAX_ENABLE_COMPILATION_CACHE="true",
                                JAX_COMPILATION_CACHE_DIR=str(gate["tmp"] / "shared"))
    assert code == 0, log
    assert not [c for c in calls if c.startswith("warm")], calls
    assert "persistent compilation cache disabled in every process" in log
    for stage in ("the pre-lock tests", "crossrev", "the tiers", "G1"):
        assert f"cold check after {stage}: " in log, stage


@pytest.mark.parametrize("plant, stage", [
    ("prelock", "the pre-lock tests"), ("tiers", "the tiers"), ("save", "G1")])
def test_a_cache_entry_under_the_gates_outputs_refuses_it(gate, plant, stage):
    """An entry means something turned the cache back on: the gate stops there, and the stop is the
    gate's own fault, not a head's, so a stack does not bisect it."""
    (gate["head"] / "jax_entry.txt").write_text(plant)
    out = gate["tmp"] / "out"
    code, calls, log = run_gate(gate, out)
    assert code == 1, log
    assert f"JAX compilation cache entries appeared after {stage} (the cold check)" in log
    assert ("lock held" in log) == (plant != "prelock")
    assert any(c.startswith("save") for c in calls) == (plant == "save")
    assert steps.stack_failure(out)["stage"] is None


def test_a_prelock_refusal_never_takes_the_lock(gate):
    (gate["head"] / "ids.txt").write_text("tests/unit/test_new_elsewhere.py::t\n")  # One removed.
    out = gate["tmp"] / "out"
    code, calls, log = run_gate(gate, out)
    assert code == 1 and (out / "done").read_text().strip() == "1"
    assert "stopped at ids" in log and "waiting for" not in log and "lock held" not in log
    assert not any(c.startswith(("crossrev", "save")) for c in calls)


def test_an_incomplete_base_listing_is_refused_and_never_published(gate):
    (gate["base"] / "collected.txt").write_text("2\n")  # pytest counted more than it listed.
    out = gate["tmp"] / "out"
    code, calls, log = run_gate(gate, out)
    assert code == 1 and "base listing not published" in log and "stopped at ids" in log
    assert not list((gate["tmp"] / "cache").glob("ids-*")) and "waiting for" not in log


def test_a_crossrev_refusal_stops_before_tiers_and_g1(gate):
    (gate["head"] / "program.txt").write_text("p2\n")  # The head's programs differ.
    code, calls, log = run_gate(gate, gate["tmp"] / "out")
    assert code == 1 and "stopped at crossrev" in log
    assert not any(c.startswith(("tiers 1 2 head", "save", "g1 compare")) for c in calls)


def test_a_declared_program_change_goes_on(gate):
    (gate["head"] / "program.txt").write_text("p2\n")
    declared = gate["tmp"] / "expected.txt"
    declared.write_text("kinds/jaxprs.txt\nkinds/bindings.txt\n")
    code, calls, log = run_gate(gate, gate["tmp"] / "out", CROSSREV_EXPECTED=str(declared))
    assert code == 0, log
    assert "0 of 1 sets identical, 1 as declared" in log and "g1 compare" in calls


def flock_child(parent, lock, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                argv = (entry / "cmdline").read_bytes().split(b"\0")
                ppid = int((entry / "stat").read_text().rsplit(")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                continue
            if os.path.basename(argv[0].decode()) == "flock" and str(lock).encode() in argv \
                    and ppid == parent:
                return int(entry.name)
        time.sleep(0.05)
    raise AssertionError("the gate's flock did not start")


def test_a_used_out_is_refused_and_left_as_it_was(gate):
    out = gate["tmp"] / "out"
    out.mkdir()
    (out / "done").write_text("0\n")
    (out / "locked.done").write_text("0\n")  # A stale verdict must never be reported again.
    done = subprocess.run(["bash", str(GATE), str(gate["head"]), str(gate["base"]), str(out)],
                          env=clean_env(gate["envs"]), capture_output=True, text=True, timeout=60)
    assert done.returncode == 2 and "was used before" in done.stderr
    assert sorted(p.name for p in out.iterdir()) == ["done", "locked.done"]


def test_a_killed_flock_runs_nothing_under_the_lock(gate):
    """With PRELOCK=lane the pre-lock steps run under the lock too, so nothing may run at all."""
    lock, out = gate["tmp"] / "lane.lock", gate["tmp"] / "out"
    (gate["tmp"] / "calls").write_text("")
    with open(lock, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        run = subprocess.Popen(["bash", str(GATE), str(gate["head"]), str(gate["base"]), str(out)],
                               env=clean_env(gate["envs"], PRELOCK="lane"), start_new_session=True)
        try:
            os.kill(flock_child(run.pid, lock), signal.SIGTERM)
            code = run.wait(timeout=60)
        finally:
            try:
                os.killpg(run.pid, signal.SIGKILL)  # Anything left, while the lock is still held.
            except ProcessLookupError:
                pass
            run.wait()
    log = (out / "gate.log").read_text()
    assert code == 2 and (out / "done").read_text().strip() == "2"
    assert "the lock was never held" in log and "lock held" not in log
    calls = (gate["tmp"] / "calls").read_text().splitlines()
    assert calls == []  # Not even the pre-lock steps, which this mode runs under the lock.


# --------------------------------------------------------------------------------- stacks (C)

STACK = GATES / "stack.sh"
FREEZER = r'''
import hashlib, json, shutil, subprocess, sys
from pathlib import Path
src, dest = Path(sys.argv[1]), Path(sys.argv[2])
git = lambda *a: subprocess.run(["git", "-C", str(src), *a], capture_output=True, text=True,
                                check=True).stdout
files = {}
for name in git("ls-files").split():
    (dest / name).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / name, dest / name)
    files[name] = {"sha256": hashlib.sha256((src / name).read_bytes()).hexdigest()}
(dest / "SNAPSHOT.json").write_text(json.dumps({"status": "complete", "files": files,
    "git_revision": git("rev-parse", "HEAD").strip(), "patch_sha256": hashlib.sha256(b"").hexdigest()}))
'''


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def stack(gate):
    """A checkout whose main holds a snapshot tree's files and the real tier fold, with heads
    made by add_head; stack.sh's environment with a freezer that copies the tracked files."""
    tmp = gate["tmp"]
    repo = snapshot_tree(tmp / "repo", "-")
    (repo / "SNAPSHOT.json").unlink()
    record = json.loads((repo / "tests/test_tiers.json").read_text())
    (repo / "tests/test_tiers.json").write_text(json.dumps(
        dict(record, measured=[], measured_provenance=[])))
    (repo / "scripts").mkdir()
    (repo / "scripts/test_tiers.py").write_text((ROOT / "scripts/test_tiers.py").read_text())
    git(tmp, "init", "-q", str(repo))
    git(repo, "config", "user.name", "stack-test")
    git(repo, "config", "user.email", "stack-test@example.invalid")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "main")
    git(repo, "branch", "-M", "main")
    (tmp / "freeze.py").write_text(FREEZER)
    gate.update(repo=repo, envs=dict(gate["envs"], REPO=str(repo),
                                     FREEZE=f"{sys.executable} -I {tmp / 'freeze.py'}"))
    return gate


def add_head(stack, name, files):
    repo = stack["repo"]
    git(repo, "checkout", "-q", "-b", name, "main")
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", name)
    git(repo, "checkout", "-q", "main")
    return git(repo, "rev-parse", name)


def run_stack(stack, heads, name="out", **extra):
    out, decl = stack["tmp"] / name, stack["tmp"] / f"{name}.json"
    decl.write_text(json.dumps({"main": "main", "heads": heads}))
    (stack["tmp"] / "calls").write_text("")
    done = subprocess.run(["bash", str(STACK), str(decl), str(out)], capture_output=True,
                          text=True, timeout=300, env=clean_env(stack["envs"], extra))
    calls = (stack["tmp"] / "calls").read_text().splitlines()
    return done.returncode, calls, out, json.loads((out / "stack.json").read_text())


H1 = {"tests/unit/test_h1.py": "def test_h1():\n    pass\n",
      "ids.txt": "tests/unit/test_h1.py::test_h1\ntests/unit/test_other.py::test_other\n"}


def test_a_passing_stack_gates_its_trial_merges_once_as_they_land(stack):
    h1, h3 = add_head(stack, "h1", H1), add_head(stack, "h3", {"docs/h3.md": "three\n"})
    measured = stack["tmp"] / "h1-measured.json"
    measured.write_text(json.dumps({"provenance": {"by": "test"}, "jax_compilation_cache": "disabled",
                                    "files": [{"file": "tests/unit/test_h1.py", "seconds": 0.4,
                                               "exit_code": 0, "counts": {"passed": 1}}]}))
    message = "Merge h1 at its head\n\nCo-Authored-By: Someone <someone@example.invalid>"
    code, calls, out, doc = run_stack(stack, [
        {"name": "h1", "rev": h1, "additions_from": ["tests/unit/test_h1.py"],
         "measured": [str(measured)], "message": message},
        {"name": "h3", "rev": h3}])
    assert code == 0 and doc["verdict"] == "passed", (out / "stack.log").read_text()
    repo, (m1, m2) = stack["repo"], [t["commit"] for t in doc["trials"]]
    assert git(repo, "rev-list", "--parents", "-n", "1", m1).split()[1:] == [
        git(repo, "rev-parse", "main"), h1]
    assert git(repo, "rev-list", "--parents", "-n", "1", m2).split()[1:] == [m1, h3]
    record = json.loads(git(repo, "show", f"{m1}:tests/test_tiers.json"))
    assert "tests/unit/test_h1.py" in [r["file"] for r in record["tiers"]["1"]]  # Folded.
    body = git(repo, "log", "-1", "--format=%B", m1)
    assert body.index(f"Stack gate: {out} (head 1 of 2") < body.index("Co-Authored-By")
    assert git(repo, "rev-parse", doc["ref"]) == m2 == doc["top"]
    gate_log = (out / "gate" / "gate.log").read_text()
    assert "additions from tests/unit/test_h1.py" in gate_log and "done status 0" in gate_log
    assert not (out / "tree").exists() and doc["merge_line"].endswith("passed")


ONLY = {  # What a bisect's rerun leaves in a tree's folder: the failing check's outputs alone.
    "tiers": ["result.json", "run", "run.log", "subset.json", "subset.log"],
    "crossrev": ["compare", "head", "head.log", "result.json", "verdict.json", "verdict.log"],
    "g1": ["c1", "compare.json", "compare.log", "merged", "parts", "result.json", "save.log"]}


@pytest.mark.parametrize("stage, plant", [
    ("tiers", {"fail.txt": "tests/unit/test_other.py\n"}),
    ("crossrev", {"program.txt": "p2\n"}),
    ("g1", {"g1.txt": "protocol-w1/w2\n"}),
])
def test_a_planted_failure_bisects_to_its_head_rerunning_only_the_failing_check(
        stack, stage, plant):
    heads = [add_head(stack, "h1", H1), add_head(stack, "h2", plant),
             add_head(stack, "h3", {"docs/h3.md": "three\n"})]
    declared = [{"name": f"h{k}", "rev": rev} for k, rev in enumerate(heads, 1)]
    declared[0]["additions_from"] = ["tests/unit/test_h1.py"]
    code, calls, out, doc = run_stack(stack, declared, RESTACK="1" if stage == "tiers" else "0")
    log = (out / "stack.log").read_text()
    assert code == 1 and doc["failure"]["stage"] == stage, log
    assert doc["bisect"]["blamed_heads"] == [2] and doc["bisect"]["fails_on_main"] == [], log
    items = doc["failure"]["items"]
    assert items and all([t[0] for t in doc["bisect"]["trail"][i]] == [2, 1] for i in items)
    for k in (2, 1):  # Nearest first; main is never reached, since M1 passes.
        assert sorted(p.name for p in (out / "bisect" / f"m{k}").iterdir()) == ONLY[stage]
        assert list(json.loads((out / "bisect" / f"m{k}" / "result.json").read_text())[
            "items"]) == items
    assert not (out / "bisect" / "m0").exists()
    if stage == "tiers":  # Only the failing file ran, and the stack is re-gated without h2.
        ran = json.loads((out / "bisect" / "m2" / "run" / "run.json").read_text())["files"]
        assert [r["file"] for r in ran] == items == ["tests/unit/test_other.py"]
        assert doc["restack"]["without"] == ["h2"] and doc["restack"]["done"] == "0", log
        assert [h["name"] for h in json.loads((out / "restack" / "stack.json").read_text())[
            "heads"]] == ["h1", "h3"]
    if stage == "crossrev":
        assert sorted(p.name for p in (out / "bisect" / "m2" / "head").iterdir()
                      if p.is_dir()) == items == ["kinds"]
    if stage == "g1":
        rows = json.loads((out / "bisect" / "m2" / "compare.json").read_text())["rows"]
        assert [r["world"] for r in rows] == items == ["protocol-w1/w2"]


def test_a_conflicting_merge_refuses_the_stack_with_its_paths(stack):
    one = add_head(stack, "x1", {"docs/same.md": "one\n"})
    two = add_head(stack, "x2", {"docs/same.md": "two\n"})
    code, calls, out, doc = run_stack(stack, [{"name": "x1", "rev": one}, {"name": "x2", "rev": two}])
    assert code == 2 and doc["verdict"] == "not run" and doc["conflicts"] == ["docs/same.md"]
    assert calls == [] and not (out / "tree").exists()
    resolution = stack["tmp"] / "same.md"  # The lead's resolution, given for the conflicting path.
    resolution.write_text("one and two\n")
    trials = steps.stack_build({"main": "main", "n": 2, "heads": [
        {"name": "x1", "rev": one}, {"name": "x2", "rev": two, "resolve": {
            "docs/same.md": str(resolution)}}]}, stack["repo"], stack["tmp"] / "tree", "OUT", "python3")
    assert trials["ok"] and trials["trials"][1]["resolved"] == {"docs/same.md": str(resolution)}
    assert git(stack["repo"], "show", f"{trials['top']}:docs/same.md") == "one and two"


def test_a_heads_own_prelock_record_is_checked_and_recorded(stack):
    """A head may name its own PRELOCK_ONLY=1 gate: it must have passed, for that very revision."""
    h1 = add_head(stack, "h1", H1)

    def record(name, rev, done="0", passed=True):
        out, snap = stack["tmp"] / name, stack["tmp"] / name / "snap"
        snap.mkdir(parents=True)
        (snap / "SNAPSHOT.json").write_text(json.dumps(
            {"status": "complete", "git_revision": rev, "patch_sha256": EMPTY}))
        (out / "gate.log").write_text(f"t gate of head {snap} base /b; lane A\n"
                                      + ("t prelock passed, seconds 1\n" if passed else "t stopped at ids\n"))
        (out / "done").write_text(done + "\n")
        return str(out)

    def build(name, prelock):
        return steps.stack_build({"main": "main", "n": 1, "heads": [
            {"name": "h1", "rev": h1, "prelock": prelock}]}, stack["repo"], stack["tmp"] / f"t-{name}",
            "OUT", "python3")

    good = build("good", record("p1", h1))
    assert good["ok"] and good["trials"][0]["prelock"] == str(stack["tmp"] / "p1")
    for name, rev, done, passed, words in (("p2", "f" * 40, "0", True, "not the head"),
                                           ("p3", h1, "1", False, "did not pass")):
        bad = build(name, record(name, rev, done, passed))
        assert not bad["ok"] and words in bad["refused"], bad


@pytest.mark.parametrize("heads, words", [
    ([{"name": f"h{k}", "rev": "r"} for k in range(4)], "a stack holds 1 to 3"),
    ([{"name": "a", "rev": "r", "crossrev_expected": ["kinds/x"]}, {"name": "b", "rev": "r"}],
     "rides alone"),
    ([{"name": "a", "rev": "r"}, {"name": "a", "rev": "s"}], "unique name"),
    ([{"name": "a", "rev": "r", "measured": "one.json"}], "must be a list"),
])
def test_a_stack_declaration_is_refused_for_each_planted_fault(tmp_path, heads, words):
    plan = steps.stack_plan({"main": "m", "heads": heads}, tmp_path)
    assert not plan["ok"] and any(words in p for p in plan["problems"]), plan


def test_the_merge_line_goes_before_the_trailers():
    assert steps.merge_message("Subject\n\nBody.", "Stack gate: X") == \
        "Subject\n\nBody.\n\nStack gate: X\n"
    assert steps.merge_message("Subject\n\nCo-Authored-By: A <a@b>", "Stack gate: X") == \
        "Subject\n\nStack gate: X\n\nCo-Authored-By: A <a@b>\n"


@pytest.mark.parametrize("trail, blamed, main, unsure", [
    ({2: {"t": "pass"}}, [3], [], []),
    ({2: {"t": "fail"}, 1: {"t": "pass"}}, [2], [], []),
    ({2: {"t": "fail"}, 1: {"t": "fail"}, 0: {"t": "pass"}}, [1], [], []),
    ({2: {"t": "fail"}, 1: {"t": "fail"}, 0: {"t": "fail"}}, [], ["t"], []),
    ({2: {"t": "inconclusive"}}, [], [], ["t"]),
    ({2: {"t": "pass", "u": "fail"}, 1: {"u": "pass"}}, [2, 3], [], []),  # One blame per item.
])
def test_the_bisect_blames_the_head_above_the_first_passing_tree(tmp_path, trail, blamed, main,
                                                                  unsure):
    for k, items in trail.items():
        (tmp_path / f"m{k}").mkdir()
        steps.write_json(tmp_path / f"m{k}" / "result.json", {"items": items})
    doc = steps.stack_blame(tmp_path, 3)
    assert (doc["blamed_heads"], doc["fails_on_main"], doc["inconclusive"]) == (blamed, main, unsure)


@pytest.mark.parametrize("stop, stage, locked", [
    ("stopped at ids", "ids", False), ("stopped at preflight", "preflight", False),
    ("stopped at crossrev", "crossrev", True), ("G1 merge failed", None, None),
])
def test_the_failing_stage_is_read_from_the_gate_log(tmp_path, stop, stage, locked):
    (tmp_path / "crossrev").mkdir()
    steps.write_json(tmp_path / "crossrev" / "verdict.json", {"per_set": {
        "kinds": {"passed": False}, "base": {"passed": True}}})
    (tmp_path / "gate.log").write_text(f"2026-11-19T00:00:00Z {stop}\n2026-11-19T00:00:00Z done status 1\n")
    doc = steps.stack_failure(tmp_path)
    assert doc["stage"] == stage and doc.get("under_lock") == locked
    if stage == "crossrev":
        assert doc["items"] == ["kinds"]


# ------------------------------------------------------------------- the scope map and selection (E)

SCOPE_TESTS = {
    "tests/unit/test_reader.py": "from pathlib import Path\nfrom validation import helper\n\n\n"
                                 "def test_reads():\n    assert helper.VALUE == 1\n"
                                 "    assert Path('docs/a.md').read_text() == 'a\\n'\n",
    "tests/unit/test_plain.py": "def test_plain():\n    assert 1 + 1 == 2\n",
    "tests/unit/test_lister.py": "import os\n\n\ndef test_lists():\n"
                                 "    assert 'a.md' in os.listdir('docs')\n",
    "tests/unit/test_spawner.py": "import subprocess\n\n\ndef test_spawns():\n"
                                  "    subprocess.run(['true'], check=True)\n",
}


def scope_snapshot(root, changes=None, rev="r" * 40, executable=()):
    """A tiny execution snapshot with the real tier runner, recorder, map tool and nightly script,
    four test files and their rows; CHANGES (path: text or None) applied over the defaults, and its
    manifest's sizes and modes as a frozen copy's (EXECUTABLE names the executable files)."""
    files = {"validation/helper.py": "VALUE = 1\n", "docs/a.md": "a\n", "docs/b.md": "b\n",
             "src/cells/__init__.py": "", **SCOPE_TESTS}
    for name in ("scripts/test_tiers.py", "scripts/gates/scope.py", "scripts/gates/gate_steps.py",
                 "scripts/gates/nightly_tiers.sh", "scripts/gates/scope_inject/sitecustomize.py"):
        files[name] = (ROOT / name).read_text()
    for name, text in (changes or {}).items():
        if text is None:
            files.pop(name, None)
        else:
            files[name] = text
    rows = [{"file": f, "seconds": 1.0, "exit_code": 0, "counts": {"passed": 1}}
            for f in sorted(files) if f.startswith("tests/unit/test_")]
    files["tests/test_tiers.json"] = json.dumps({"kind": "cells.test_tiers@1", "fast_seconds": 20.0,
                                                 "cap_seconds": 90.0, "tiers": {"1": rows, "2": [], "3": []}})
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    (root / "SNAPSHOT.json").write_text(json.dumps({
        "status": "complete", "git_revision": rev, "patch_sha256": EMPTY, "dirty": False,
        "files": {n: {"sha256": hashlib.sha256(text.encode()).hexdigest(),
                      "observation": {"size": len(text.encode())},
                      "snapshot_mode": 0o555 if n in executable else 0o444} for n, text in files.items()}}))
    return root


def scope_module():
    sys.path.insert(0, str(GATES))
    spec = importlib.util.spec_from_file_location("scope", GATES / "scope.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scope = scope_module()


@pytest.fixture(scope="module")
def scope_map(tmp_path_factory):
    """The map of the tiny snapshot, from the real tier runner with the recorder on."""
    tmp = tmp_path_factory.mktemp("scope")
    snap = scope_snapshot(tmp / "nightly")
    cpu = str(sorted(os.sched_getaffinity(0))[0])
    run = subprocess.run([sys.executable, "-B", "scripts/test_tiers.py", "run", "--tiers",
                          "tests/test_tiers.json", "--tier", "1", "2", "--out", str(tmp / "run"),
                          "--cpus", cpu, "--cap", "120", "--scope-map", str(tmp / "run" / "scope")],
                         cwd=snap, capture_output=True, text=True, timeout=300,
                         env=clean_env(PYTHONPATH=str(snap / "src")))
    assert run.returncode == 0, run.stdout + run.stderr
    return {"tmp": tmp, "snap": snap, "doc": scope.build(tmp / "run", snap, sys.executable)}


def test_the_map_records_imports_reads_listings_and_unmapped_children(scope_map):
    doc = scope_map["doc"]
    files = doc["files"]
    assert doc["verdict"] == "passed" and all(e["complete"] for e in files.values()), files
    paths = lambda f, key="content": {doc["paths"][i] for i in files[f][key]}  # noqa: E731
    assert {"validation/helper.py", "docs/a.md", "tests/unit/test_reader.py"} <= paths(
        "tests/unit/test_reader.py")
    assert "docs/a.md" not in paths("tests/unit/test_plain.py")
    assert files["tests/unit/test_reader.py"]["reads"] == ["docs/a.md"]
    assert paths("tests/unit/test_lister.py", "lists") == {"docs"}
    assert {".", "src", "tests/unit"} <= paths("tests/unit/test_reader.py", "roots")
    assert files["tests/unit/test_spawner.py"]["children_unmapped"] == ["true"]
    assert not any(e["traced"] for e in files.values())  # This run had no --trace.
    assert not any(files[f]["reads_repository"] or files[f]["children_unmapped"]
                   for f in ("tests/unit/test_plain.py",))


L, P, R, S = (f"tests/unit/test_{n}.py" for n in ("lister", "plain", "reader", "spawner"))


@pytest.mark.parametrize("changes, always, chosen", [
    ({}, "none", [S]),  # A child the map cannot see is always run.
    ({}, "scanners", [L, S]),
    ({}, "readers", [L, R, S]),  # D229's always-run set, the fallback.
    ({"docs/a.md": "a, changed\n"}, "none", [R, S]),
    ({"validation/helper.py": "VALUE = 1  # changed\n"}, "none", [R, S]),
    ({"docs/c.md": "new\n"}, "none", [L, S]),  # A new name in a listed folder.
    ({"tests/unit/test_plain.py": "def test_plain():\n    assert 2 == 2\n"}, "none", [P, S]),
    ({"tests/unit/helper.py": "X = 1\n"}, "none", [S]),  # Nothing touched it.
    ({"validation.py": "VALUE = 2\n"}, "none", [R, S]),  # It would replace a namespace package.
    ({"validation/__init__.py": ""}, "none", [L, P, R, S]),  # pytest asks each top folder for one.
    ({"pytest.toml": "[pytest]\n"}, "none", [L, P, R, S]),  # pytest 9's configuration names (D358).
    ({"tests/.pytest.toml": "[pytest]\n"}, "none", [L, P, R, S]),
    ({"json.py": "X = 1\n"}, "none", [L, P, R, S]),  # It would shadow a module each one imports (D358).
    ({"tests/unit/helper/__init__.py": ""}, "none", [S]),  # No import looks this name up.
    ({"validation/helper/__init__.py": "VALUE = 1\n"}, "none", [R, S]),  # A package beside helper.py.
    ({}, "untraced", [L, R, S]),  # The default (D358): no trace checked these entries.
])
def test_the_selection_holds_every_file_whose_recorded_paths_changed(scope_map, tmp_path, changes,
                                                                     always, chosen):
    """Base is the map's own tree, and the head carries CHANGES."""
    base = scope_snapshot(tmp_path / "base")
    head = scope_snapshot(tmp_path / "head", changes, rev="h" * 40)
    subset, report = scope.select(head, base, scope_map["doc"], "tests/test_tiers.json", always)
    assert sorted(r["file"] for r in subset["tiers"]["1"]) == chosen, report["files"]


def test_a_planted_read_of_a_repository_file_pulls_its_test_in(scope_map, tmp_path):
    """Before the plant, a change to docs/b.md selects nothing it reads; once test_plain.py reads
    docs/b.md and the map is rebuilt, the same change selects it, for that path alone."""
    changed = {"docs/b.md": "b, changed\n"}
    base = scope_snapshot(tmp_path / "base")
    before = scope.select(scope_snapshot(tmp_path / "head", changed, rev="h" * 40), base,
                          scope_map["doc"], "tests/test_tiers.json", "none")[1]["files"]
    assert P not in before
    planted = {P: "from pathlib import Path\n\n\ndef test_plain():\n"
                  "    assert Path('docs/b.md').read_text()\n"}
    snap = scope_snapshot(tmp_path / "nightly", planted)
    cpu = str(sorted(os.sched_getaffinity(0))[0])
    subprocess.run([sys.executable, "-B", "scripts/test_tiers.py", "run", "--tiers",
                    "tests/test_tiers.json", "--tier", "1", "--out", str(tmp_path / "run"), "--cpus", cpu,
                    "--scope-map", str(tmp_path / "run" / "scope")], cwd=snap, check=True,
                   capture_output=True, timeout=300, env=clean_env(PYTHONPATH=str(snap / "src")))
    doc = scope.build(tmp_path / "run", snap, sys.executable)
    head = scope_snapshot(tmp_path / "head2", dict(planted, **changed), rev="h" * 40)
    after = scope.select(head, snap, doc, "tests/test_tiers.json", "none")[1]["files"]
    assert after[P] == ["touched paths changed since the map: ['docs/b.md']"]


def planted_map(tmp_path, rows, child=()):
    """The map of the tiny snapshot with test_plain.py's record planted: ROWS of its test process, and
    CHILD's of another process (its number is 11)."""
    snap = scope_snapshot(tmp_path / "nightly")
    run, record = tmp_path / "run", json.loads((snap / "tests/test_tiers.json").read_text())
    logs = run / "scope" / "tests__unit__test_plain.py"
    logs.mkdir(parents=True)
    (logs / "10-a.jsonl").write_text("".join(json.dumps(r) + "\n" for r in [
        {"process": 10, "parent": 1, "forked": False, "argv": ["python", "-m", "pytest"], "root": "/t"},
        *rows, {"exit": True, "modules": ["tests/unit/test_plain.py"]}]))
    if child:
        (logs / "11-b.jsonl").write_text("".join(json.dumps(r) + "\n" for r in [
            {"process": 11, "parent": 10, "forked": False, "argv": ["python", "x"], "root": "/t"}, *child]))
    (run / "run.json").write_text(json.dumps({"scope_map": str(run / "scope"), "files": [
        dict(r, timed_out=False) for r in record["tiers"]["1"]]}))
    (run / "summary.json").write_text(json.dumps({"changed_vs_record": []}))
    return snap, scope.build(run, snap, sys.executable)


def chosen_for(tmp_path, snap, doc, changes):
    head = scope_snapshot(tmp_path / "head", changes, rev="h" * 40)
    return scope.select(head, snap, doc, "tests/test_tiers.json", "none")[1]["files"].get(P)


@pytest.mark.parametrize("changes, chosen", [
    ({"tests/unit/test_new.py": "def test_new():\n    pass\n"}, False),  # Not a plugin's name.
    ({"tests/unit/test_reader.py": None}, False),  # A library's stat of a file it cannot use.
    ({"tests/unit/jax_rocm7_plugin/__init__.py": ""}, True),  # A plugin its discovery would find.
])
def test_a_librarys_own_discovery_is_compared_on_the_names_it_can_use(tmp_path, changes, chosen):
    """jaxlib's plugin search (pkgutil over sys.path) lists tests/unit and asks about each entry:
    only names discovery can use (DISCOVERY) count, so a new test file selects nothing."""
    snap, doc = planted_map(tmp_path, [
        {"list": "tests/unit", "by": "library", "via": "pkgutil"}, {"root": "tests/unit"},
        {"stat": "tests/unit/test_reader.py", "by": "library", "via": "pkgutil"}])
    assert doc["files"][P]["complete"] and not doc["files"][P]["reads_repository"]
    assert bool(chosen_for(tmp_path, snap, doc, changes)) is chosen


@pytest.mark.parametrize("rows, chosen", [
    ([{"list": "docs", "by": "library"}], True),
    ([{"stat": "docs/c.md", "by": "library"}], True),
    ([{"list": "docs", "by": "library", "via": "pkgutil"}], True),  # Sent elsewhere than sys.path.
    ([{"stat": "docs/c.md", "by": "library", "via": "pkgutil"}], True),
    ([{"list": "docs", "by": "repo:tests/unit/test_plain.py", "via": "metadata"}], False),  # Not a distribution.
    ([{"list": "docs", "by": "library", "via": "pkgutil"}, {"root": "docs"},  # Both classes of a
      {"list": "docs", "by": "repo:tests/unit/test_plain.py"}], True),        # listing are kept (D358).
    ([{"list": "docs", "by": "pytest"}], False),
    ([{"list": "docs", "by": "import"}, {"root": "docs"}], False),  # Replaced by the names looked up.
    ([{"list": "docs", "by": "import"}], True),  # A finder that code sent there itself.
])
def test_each_class_of_a_listing_counts_by_what_it_can_use(tmp_path, rows, chosen):
    """A new docs/c.md, after a listing of docs (or a question about the file) of each class (D358)."""
    snap, doc = planted_map(tmp_path, rows)
    assert bool(chosen_for(tmp_path, snap, doc, {"docs/c.md": "new\n"})) is chosen


CHILD = {"child": 11, "argv": ["python", "x"], "cwd": "/t", "program": "/usr/bin/python", "git": False}


@pytest.mark.parametrize("rows, child, complete, mapped", [
    ([], (), True, True),
    ([{"link": "docs"}], (), False, True),  # What is read through a link carries no path of the tree.
    ([{"fault": "open: OSError"}], (), False, True),
    ([CHILD], [{"open": "docs/a.md", "by": "stdlib"}, {"exit": True, "modules": []}], True, True),
    ([CHILD], [{"open": "docs/a.md", "by": "stdlib"}], False, True),  # Killed after it read the tree.
    ([CHILD], [{"list": "src", "by": "import"}], True, True),  # Killed, and it touched nothing.
    ([CHILD], (), True, False),  # No record of it.
    ([dict(CHILD, argv=["bash", "x"])], [{"exit": True, "modules": []}], True, False),  # It became Python.
    ([{"child": None, "argv": ["sh", "-c", "true"], "cwd": "/t"}], (), True, False),  # os.system
])
def test_a_missed_recording_keeps_the_file_running(tmp_path, rows, child, complete, mapped):
    """Incomplete or unmapped, the file is selected whatever changed, under every rule (D358)."""
    snap, doc = planted_map(tmp_path, rows, child)
    e = doc["files"][P]
    assert e["complete"] is complete and bool(e["children_unmapped"]) is not mapped, e
    assert bool(chosen_for(tmp_path, snap, doc, {})) is not (complete and mapped)


def test_a_folder_opened_by_descriptor_is_a_listing(tmp_path):
    """os.fwalk and scandir on a descriptor list nothing by path: the folder's open stands for it."""
    snap, doc = planted_map(tmp_path, [{"open": "docs", "by": "repo:tests/unit/test_plain.py"}])
    assert chosen_for(tmp_path, snap, doc, {"docs/c.md": "new\n"}) == [
        "listed folders changed since the map: ['docs']"]


def test_the_recorder_keeps_what_os_supports_says_of_its_wrappers(tmp_path):
    """shutil picks its descriptor-based rmtree by os.stat's place in os.supports_*, at import."""
    code = ("import os, shutil; print(os.stat in os.supports_follow_symlinks, os.stat in os.supports_fd,"
            " os.open in os.supports_dir_fd, shutil.rmtree.avoids_symlink_attacks)")
    seen = []
    for on in (False, True):
        env = clean_env(PYTHONPATH=str(GATES / "scope_inject"))
        if on:
            env.update(CELLS_SCOPE_LOG=str(tmp_path / "log"), CELLS_SCOPE_ROOT=str(tmp_path))
        seen.append(subprocess.run([sys.executable, "-B", "-c", code], env=env, capture_output=True,
                                   text=True, check=True, cwd=tmp_path).stdout)
    assert seen[0] == seen[1] == "True True True True\n" and list((tmp_path / "log").glob("*.jsonl"))


@pytest.mark.parametrize("plant, words", [
    ("stopped", "selection stopped"), ("failed", "nightly run failed"), ("old", "hours old"),
    ("src", "a src/ change keeps the full gate"), ("missing", "no readable scope map"),
    ("earlier", "the map is cells.scope_map@2, and this tool reads " + scope.KIND),
])
def test_the_selection_is_refused_for_each_planted_fault(scope_map, tmp_path, plant, words):
    base = scope_snapshot(tmp_path / "base")
    head = scope_snapshot(tmp_path / "head", {"src/cells/__init__.py": "X = 1\n"} if plant == "src"
                          else {}, rev="h" * 40)
    doc = json.loads(json.dumps(scope_map["doc"]))
    stopped = tmp_path / "selection-stopped"
    if plant == "stopped":
        stopped.write_text("a nightly failed\n")
    if plant == "failed":
        doc["verdict"] = "failed"
    if plant == "old":
        doc["built"] = "2026-01-01T00:00:00Z"
    if plant == "earlier":
        doc["kind"] = "cells.scope_map@2"
    why = scope.refusal(head, base, None if plant == "missing" else doc, stopped, None, 36.0)
    assert why and words in why, why


# ------------------------------------------------------- D358's kinds, children and trace check

K, C, M, H = (f"tests/unit/test_{n}.py" for n in ("kinds", "children", "masks", "hole"))
EXECUTABLE = object()
LIBRARY = ("import os\n\n\ndef scan(path):\n    return os.listdir(path)\n\n\n"
           "def ask(path):\n    return os.path.exists(path)\n")
KIND_FILES = {
    **{f: None for f in SCOPE_TESTS}, "docs/seen/a.md": "a\n", "docs/pkg/a.md": "a\n",
    "docs/size.md": "four\n", "docs/run.sh": "true\n", "docs/deep/b.md": "b\n",
    "docs/entries/a.md": "a\n", "docs/walked/a.md": "a\n", "docs/rebuilt.md": "r\n",
    "docs/replaced.md": "r\n",
    K: """import importlib
import importlib.util
import os
import sys

sys.path.insert(0, LIB)
import a_library  # noqa: E402
from validation import helper  # noqa: E402


def test_kinds():
    a_library.scan("docs/seen")  # A library lists it first, then the test's own code does.
    assert os.listdir("docs/seen") == ["a.md"]
    a_library.scan("docs/pkg")
    assert not a_library.ask("docs/absent.md")
    assert os.path.getsize("docs/size.md") and not os.access("docs/run.sh", os.X_OK)
    folder = os.open("docs/deep", os.O_RDONLY)
    os.close(os.open("b.md", os.O_RDONLY, dir_fd=folder))
    os.close(folder)
    assert [entry.stat().st_size for entry in os.scandir("docs/entries")]
    assert len(list(os.walk("docs/walked"))) == 1
    assert helper.VALUE == 1 and importlib.util.find_spec("validation.later") is None
    try:
        importlib.import_module("later_top")
    except ImportError:
        pass
""",
    C: """import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def python(code, env):
    return subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, env=env).returncode


def test_children(tmp_path):
    rebuilt = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    assert python("open('docs/rebuilt.md')", rebuilt) == 0
    assert python("open('docs/replaced.md')", {}) == 0
    assert python("import os; os.kill(os.getpid(), 9)", rebuilt) == -9
    repo = str(tmp_path / "repo")
    for args in (["uname", "-p"], ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                 ["git", "init", "-q", repo], ["git", "-C", repo, "status", "--", "src/cells"]):
        subprocess.run(args, capture_output=True)
    try:
        subprocess.run([str(ROOT / ".venv/bin/python"), "-c", "pass"])
    except FileNotFoundError:
        pass
""",
    M: """import multiprocessing
import os
import subprocess
import sys


def test_masks():
    child = multiprocessing.get_context("spawn").Process(target=os.getpid)  # It records itself,
    child.start()
    child.join()
    subprocess.run(["cat", "docs/a.md"], stdout=subprocess.DEVNULL)  # and stands for no other.
    subprocess.run(["bash", "-c", f"cat docs/b.md > /dev/null; exec {sys.executable} -c pass"])
    pid = os.fork()
    if pid == 0:
        os.execv("/usr/bin/cat", ["cat", "/dev/null"])
    os.waitpid(pid, 0)
""",
    H: """import ctypes


def test_hole():
    libc = ctypes.CDLL(None)
    assert libc.close(libc.open(b"docs/a.md", 0)) == 0 and libc.system(b"true") == 0
"""}


def kinds_snapshot(root, lib, changes=None, rev="r" * 40):
    """The tiny snapshot of D358's kinds and children (LIB holds the library that test_kinds.py uses)."""
    files = dict(KIND_FILES, **{K: KIND_FILES[K].replace("LIB", repr(str(lib)))}, **(changes or {}))
    return scope_snapshot(root, {n: "true\n" if t is EXECUTABLE else t for n, t in files.items()}, rev,
                          [n for n, t in files.items() if t is EXECUTABLE])


def traceable():
    """Whether strace can trace here. It cannot where the process is traced already: the nightly
    runs this file under strace, so these tests hold both ways."""
    return shutil.which("strace") is not None and "TracerPid:\t0\n" in Path("/proc/self/status").read_text()


@pytest.fixture(scope="module")
def kinds_map(tmp_path_factory):
    """Its map, from the real tier runner with the recorder on, and strace where it can trace (about 5 s)."""
    tmp = tmp_path_factory.mktemp("kinds")
    lib = tmp / "site-packages"
    lib.mkdir()
    (lib / "a_library.py").write_text(LIBRARY)
    snap = kinds_snapshot(tmp / "nightly", lib)
    cpu = str(sorted(os.sched_getaffinity(0))[0])
    run = subprocess.run([sys.executable, "-B", "scripts/test_tiers.py", "run", "--tiers",
                          "tests/test_tiers.json", "--tier", "1", "2", "--out", str(tmp / "run"), "--cpus",
                          cpu, "--cap", "120", "--scope-map", str(tmp / "run" / "scope"), "--trace",
                          str(tmp / "run" / "trace")], cwd=snap, capture_output=True, text=True, timeout=300,
                         env=clean_env(PYTHONPATH=str(snap / "src")))
    assert run.returncode == 0, run.stdout + run.stderr
    doc = scope.build(tmp / "run", snap, sys.executable)
    assert doc["trace"]["traced"] == (4 if traceable() else 0), doc["trace"]
    assert bool(json.loads((tmp / "run/run.json").read_text()).get("trace_refused")) != traceable()
    return {"tmp": tmp, "lib": lib, "snap": snap, "doc": doc}


@pytest.mark.parametrize("changes, chosen", [
    ({}, []),
    ({"docs/other.md": "n\n"}, []),
    ({"docs/seen/new.md": "n\n"}, [K]),  # Its own listing, after a library's.
    ({"docs/pkg/new.md": "n\n"}, [K]),  # A library's listing of a folder it was given.
    ({"docs/absent.md": "n\n"}, [K]),  # A library's question.
    ({"docs/size.md": "fours\n"}, [K]),
    ({"docs/size.md": "five\n"}, []),  # The same size, all that was asked of it.
    ({"docs/run.sh": EXECUTABLE}, [K]),
    ({"docs/deep/b.md": "c\n"}, [K]),  # Opened relative to a descriptor.
    ({"docs/entries/a.md": "longer\n"}, [K]),  # An entry's own stat.
    ({"docs/entries/a.md": "b\n"}, []),
    ({"docs/walked/a.md": "longer\n"}, []),  # Only its name and kind were read.
    ({"docs/walked/a.md": None, "docs/walked/a.md/b": "b\n"}, [K]),  # The name becomes a folder.
    ({"validation/later.py": "X = 1\n"}, [K]),  # find_spec found none.
    ({"later_top.py": "X = 1\n"}, [K]),  # import_module found none.
    ({"colorsys.py": "X = 1\n"}, []),  # No import looked this name up.
    ({"docs/rebuilt.md": "s\n"}, [C]),  # A child whose PYTHONPATH was rebuilt,
    ({"docs/replaced.md": "s\n"}, [C]),  # and one whose whole environment was replaced.
    ({"HEAD": "ref\n"}, [C]),  # git on the tree asks for a repository in it.
    ({".venv/bin/python": "true\n"}, [C]),  # An absent interpreter is a question.
])
def test_each_kind_of_question_is_recorded_and_only_it(kinds_map, tmp_path, changes, chosen):
    """test_masks.py is always selected (unmapped), and test_hole.py where it was traced."""
    base = kinds_snapshot(tmp_path / "base", kinds_map["lib"])
    head = kinds_snapshot(tmp_path / "head", kinds_map["lib"], changes, rev="h" * 40)
    _, report = scope.select(head, base, kinds_map["doc"], "tests/test_tiers.json", "none")
    assert sorted(set(report["files"]) - {M, H}) == chosen and M in report["files"], report["files"]


def test_only_the_children_without_a_record_leave_a_file_unmapped(kinds_map):
    files = kinds_map["doc"]["files"]
    assert files[C]["complete"] and not files[C]["children_unmapped"], files[C]
    named = [" ".join(c.split()[:2]) for c in files[M]["children_unmapped"]]
    assert files[M]["complete"] == (not traceable()), files[M]["why"]  # bash read docs/b.md.
    assert sorted(named) == ["bash -c", "cat /dev/null", "cat docs/a.md"]


def test_the_trace_marks_what_the_recorder_missed_and_only_a_traced_reader_is_released(kinds_map, tmp_path):
    doc = kinds_map["doc"]
    hole, found = doc["files"][H], doc["trace"]["found"].get(H, {})
    if traceable():
        assert hole["why"] == ["the trace shows what the entry lacks: ['docs/a.md']"]
        assert "docs/a.md" in found["files"]["docs/a.md"] and "execve" in found["programs"][0]
        assert hole["children_unmapped"][0].startswith("(the trace) execve(")
    assert doc["files"][K]["reads_repository"] and doc["files"][K]["complete"], doc["files"][K]
    base = kinds_snapshot(tmp_path / "base", kinds_map["lib"])
    head = kinds_snapshot(tmp_path / "head", kinds_map["lib"], rev="h" * 40)
    for traced in (True, False):
        doc = json.loads(json.dumps(doc))
        doc["files"][K]["traced"] = traced
        _, report = scope.select(head, base, doc, "tests/test_tiers.json")
        assert (K in report["files"]) is not traced and report["always"] == "untraced", report["files"]
        assert report["readers_rule"]["selected"] == len({*report["files"], K, C})  # D229's, for comparison.


TREE_LINE = 'openat(AT_FDCWD</t>, "/t/docs/a.md", O_RDONLY) = 3</t/docs/a.md>\n'


@pytest.mark.parametrize("plant, words", [
    ("whole", None), ("no trace", "no trace"), ("no end", "t.11 has no end"),
    ("missing child", "no trace of the process or thread 11"), ("io_uring", "t.10 holds io_uring_setup"),
])
def test_a_trace_that_is_not_whole_checks_nothing(tmp_path, plant, words):
    """strace's lines for a process (10), a thread of it (12) and a child (11); /t is the tree."""
    logs = {10: 'execve("/usr/bin/python", ["python"], 0x1 /* 2 vars */) = 0\n'
                "clone3({flags=CLONE_VM|CLONE_THREAD, child_tid=0x1}, 88) = 12\nvfork() = 11\n",
            11: 'execve("/usr/bin/cat", ["cat"], 0x1 /* 2 vars */) = 0\n' + TREE_LINE,
            12: "getdents64(3</t>, 0x1 /* 4 entries */, 32768) = 96\n"
                'openat(AT_FDCWD</t>, "/tt/x", O_RDONLY) = 3</tt/x>\n'}
    if plant == "no trace":
        logs = {}
    if plant == "missing child":
        del logs[11]
    if plant == "io_uring":
        logs[10] += "io_uring_setup(8, 0x1) = 5</t>\n"
    for thread, text in logs.items():
        end = "" if plant == "no end" and thread == 11 else "+++ exited with 0 +++\n"
        (tmp_path / f"t.{thread}").write_text(text + end)
    trace, why = scope.read_trace(tmp_path, "/t")
    assert (why or "").startswith(words or "") and (trace is None) == bool(words), (trace, why)
    if plant == "whole":
        assert trace["opened"] == {"docs/a.md": TREE_LINE.strip()} and trace["listed"] == {10: {"."}}
        assert trace["parent"] == {11: 10} and sorted(trace["ran"]) == [10, 11]


@pytest.mark.parametrize("argv, cwd, asks", [
    (["git", "-C", "/t", "rev-parse", "HEAD"], "/", {".git", ".git/HEAD", "HEAD"}),
    (["git", "status"], "/t/docs", {".git", ".git/HEAD", "HEAD", "docs/.git", "docs/.git/HEAD", "docs/HEAD"}),
    (["git", "-C", "/t", "diff", "--", "a", "b"], "/", None),  # Outside a repository it compares the two.
    (["git", "-C", "/t", "--git-dir=/r", "status"], "/", None),
    (["git", "-C", "/r", "-c", "user.name=t", "add", "src/cells"], "/t", set()),
    (["git", "init", "-q", "/r"], "/t", set()),
    (["git", "-C", "/r", "add", "../t/docs/a.md"], "/", None),  # A path in the tree.
    (["git", "-C", "/r", "-c", "core.hooksPath=/t/hooks", "commit"], "/", None),
    (["uname", "-p"], "/t", set()), (["uname", "-a"], "/t", None),
    (["fc-list", "--help"], "/t", set()), (["cat", "docs/a.md"], "/t", None),
])
def test_the_argument_rules_hold_exactly_what_was_traced(argv, cwd, asks):
    assert scope.answered(argv, f"/usr/bin/{argv[0]}", cwd, False, "/t") == asks
    assert scope.answered(argv, None, cwd, False, "/t") == set()  # No such program: no child ran.
    assert scope.answered(argv, f"/t/bin/{argv[0]}", cwd, False, "/t") is None  # The tree's own program.
    if argv[0] == "git":
        assert scope.answered(argv, "/usr/bin/git", cwd, True, "/t") is None  # GIT_DIR names the tree.


@pytest.mark.parametrize("fail", [False, True])
def test_the_nightly_takes_a_free_lane_and_publishes_or_stops_selection(tmp_path, fail):
    """Lane A's lock is held, so the run takes lane B's. A passing run publishes its map; a file
    that no longer matches its row writes the stop marker and keeps the last passing map."""
    out = tmp_path / "nightly"
    scope_snapshot(out / "snapshot", {"tests/unit/test_plain.py": "def test_plain():\n    assert 0\n"}
                   if fail else {})
    cache, cpu = tmp_path / "cache", str(sorted(os.sched_getaffinity(0))[0])
    cache.mkdir()
    (cache / "scope-map.json").write_text("{\"kind\": \"the last passing map\"}\n")
    env = clean_env(GATE_CACHE=str(cache), PY=sys.executable, HOSTPY=sys.executable,
               PRE_CPU=cpu, CPUS_A=cpu, CPUS_B=cpu, LOCK_A=str(tmp_path / "a.lock"),
               LOCK_B=str(tmp_path / "b.lock"), POLL="1", WAIT_FREE="60")
    with open(tmp_path / "a.lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        done = subprocess.run(["bash", str(out / "snapshot/scripts/gates/nightly_tiers.sh"), "--run",
                               str(out)], env=env, capture_output=True, text=True, timeout=300)
    log = (out / "nightly.log").read_text()
    assert "lane B, lock held" in log and done.returncode == int(fail), log
    trace = json.loads((out / "verdict.json").read_text())["trace"]  # What the trace found is recorded,
    assert trace["traced"] == (4 if traceable() else 0) and trace["found"] == {}, trace
    assert not list((out / "tiers-1+2").glob("trace/*/t.*"))  # and a trace that found nothing goes.
    assert "compilation cache disabled in every process" in log and "cold check after the tiers: " in log
    published = json.loads((cache / "scope-map.json").read_text())
    if fail:
        assert (cache / "selection-stopped").is_file() and published["kind"] == "the last passing map"
    else:
        assert not (cache / "selection-stopped").exists() and published["kind"] == scope.KIND


def test_a_gate_with_a_selection_runs_only_its_files_and_may_drop_crossrev_and_g1(gate):
    """gate.sh's SELECT: the map leaves test_other.py out (none of its paths changed, and a trace
    checked its entry), so the tiers run the guard set alone; CHECKS drops crossrev and G1 (no src/
    change). SELECT_ALWAYS=readers is D229's rule, under which it runs (about 2 s, pre-lock only). A
    missing map runs the full tiers."""
    m = gate["tmp"] / "map.json"
    m.write_text(json.dumps({
        "kind": scope.KIND, "built": steps.utc(), "revision": "b" * 40, "verdict": "passed",
        "interpreter": steps.interpreter(gate["envs"]["PY"]), "paths": ["tests/unit/test_other.py"],
        "content": ["-"], "asked": ["-"], "names": ["-"], "discovery": ["-"], "tops": [], "subs": [],
        "importable": {}, "files": {"tests/unit/test_other.py": {
            "complete": True, "why": [], "traced": True, "content": [0], "exists": [], "lists": [],
            "finds": [], "roots": [], "tops": [], "subs": [], "reads_repository": True, "scans": False,
            "reads": [], "children_unmapped": [], "row": {"exit_code": 0, "counts": {"passed": 1}}}}}))
    code, calls, log = run_gate(gate, gate["tmp"] / "out", SELECT=str(m), CHECKS="tiers")
    assert code == 0 and "selection: " in log and "tiers: the selection" in log, log
    assert "crossrev not run" in log and "G1 not run" in log
    assert not any(c.startswith(("crossrev", "save")) for c in calls)
    subset = json.loads((gate["tmp"] / "out" / "prelock" / "selection" / "subset.json").read_text())
    assert sorted(r["file"] for r in subset["tiers"]["1"]) == sorted(steps.GUARDS)
    code, _, _ = run_gate(gate, gate["tmp"] / "old", SELECT=str(m), SELECT_ALWAYS="readers", PRELOCK_ONLY="1")
    subset = json.loads((gate["tmp"] / "old" / "prelock" / "selection" / "subset.json").read_text())
    assert code == 0 and "tests/unit/test_other.py" in [r["file"] for r in subset["tiers"]["1"]]
    code, calls, log = run_gate(gate, gate["tmp"] / "out2", SELECT=str(gate["tmp"] / "absent.json"))
    assert code == 0 and "selection not used (exit 3)" in log and "tiers: the selection" not in log


# ------------------------------------------------------------------------------------- hermetic

OUTER = {"ADDITIONS_FROM": "tests/unit/test_gates_gate.py", "LANE": "A", "TIERS": "tests/absent.json",
         "REMOVED_OK_FILE": "/absent/removed-ok.txt", "CROSSREV_EXPECTED": "/absent/expected.txt",
         "CHECKS": "g1", "PRELOCK_ONLY": "1", "SELECT": "auto", "BASE_S": "/absent/base",
         "GIT_DIR": "/absent/repo.git"}


@pytest.mark.parametrize("tool", ["gate", "stack"])
def test_the_outer_environment_never_reaches_a_tests_gate_or_stack(stack, monkeypatch, tool):
    """A landing gate runs this file with its own ADDITIONS_FROM, LANE and the rest (T66): planted
    in this process's environment after the fixtures, each is ignored. Undropped, ADDITIONS_FROM
    names a file the synthetic head lacks (preflight refuses), PRELOCK_ONLY stops before the lock,
    TIERS and CHECKS are refused, BASE_S is not main and GIT_DIR moves every git call."""
    h1 = add_head(stack, "h1", H1) if tool == "stack" else None
    for name, value in OUTER.items():
        monkeypatch.setenv(name, value)
    if tool == "gate":
        code, calls, log = run_gate(stack, stack["tmp"] / "out")
        declared = "additions from none; removals listed in none; "
    else:  # stack.sh sets the union of the heads' declarations itself.
        code, calls, out, doc = run_stack(stack, [
            {"name": "h1", "rev": h1, "additions_from": ["tests/unit/test_h1.py"]}])
        log = (out / "gate" / "gate.log").read_text()
        assert doc["verdict"] == "passed", (out / "stack.log").read_text()
        declared = f"additions from tests/unit/test_h1.py; removals listed in {out}/decl-1/removed-ok.txt; "
    assert code == 0 and "lock held" in log and "g1 compare" in calls, log
    assert "; lane custom, " in log and "; tiers tests/test_tiers.json; " in log
    assert declared + "crossrev differences declared in none; " in log
    assert "; checks crossrev tiers g1; selection off; " in log


def test_every_variable_the_tools_read_is_dropped_from_the_tests():
    bash = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::?[-+?=])")  # ${NAME:-...}, ${NAME-...}, ${NAME:?...}
    py = re.compile(r"(?:environ|env)(?:\.get\(|\[)\s*[\"']([A-Z][A-Z0-9_]*)[\"']")
    read = set()
    for name in ("gate.sh", "stack.sh", "nightly_tiers.sh"):
        read |= set(bash.findall((GATES / name).read_text()))
    for name in ("gate_steps.py", "scope.py", "scope_inject/sitecustomize.py"):
        read |= set(py.findall((GATES / name).read_text()))
    assert {"ADDITIONS_FROM", "LANE", "TIERS", "BASE_S", "PRE_CPU", "CELLS_SCOPE_LOG"} <= read
    assert read - LOCALS <= TOOL_ENV, sorted(read - LOCALS - TOOL_ENV)


# --------------------------------------------------------------- cold by construction (D321)

@pytest.mark.parametrize("script, guard, checks", [
    ("gate.sh", "export JAX_ENABLE_COMPILATION_CACHE=false", True),
    ("stack.sh", "export JAX_ENABLE_COMPILATION_CACHE=false", True),
    ("nightly_tiers.sh", "export JAX_ENABLE_COMPILATION_CACHE=false", True),
    ("fr_landing_set.sh", "export JAX_ENABLE_COMPILATION_CACHE=false", True),
    ("fr_landing_holder.sh", "--env JAX_ENABLE_COMPILATION_CACHE=false", False),  # Its queue units.
])
def test_every_gate_script_disables_the_compilation_cache(script, guard, checks):
    """R2: each gate disables the cache for all it starts, drops any folder it was given, and runs
    the cold check (the holder's units are checked by fr_landing_set.sh)."""
    text = (GATES / script).read_text()
    assert guard in text
    assert ("unset JAX_COMPILATION_CACHE_DIR" in text) == guard.startswith("export")
    assert ("jax-entries" in text) == checks


def test_the_cold_check_finds_cache_entries_by_their_names(tmp_path):
    key = "0123456789abcdef" * 4
    names = [f"a/b/jit_f-{key}-cache", f"jit__window_rollout-{key}-cache", "x-cache",
             f"jit_f-{key[:-1]}-cache", f"jit_f-{key}-cache.txt", "ids-820bc1ea2a8a-d034178668872798"]
    for name in names:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("")
    found = [Path(p).relative_to(tmp_path).as_posix() for p in steps.jax_entries([tmp_path])]
    assert found == names[:2]
    assert steps.main(["jax-entries", str(tmp_path / "a")]) == 1
    assert steps.main(["jax-entries", str(tmp_path / "missing")]) == 0


ENV_TEST = ("import os\n\n\ndef test_env():\n"
            "    assert os.environ['JAX_ENABLE_COMPILATION_CACHE'] == os.environ['EXPECT_ENABLED']\n"
            "    assert os.environ.get('JAX_COMPILATION_CACHE_DIR', '') == os.environ['EXPECT_DIR']\n")


def test_the_tier_runner_is_cold_unless_a_run_names_a_cache(tmp_path):
    """R1, on the real tier runner (about 3 s, no JAX): a caller's cache settings never reach a test
    process; measure runs cold and marks its record so; only run --jax-cache FOLDER runs warm, with
    the qualified settings, and its record names the folder."""
    snap = scope_snapshot(tmp_path / "snap", {"tests/unit/test_env.py": ENV_TEST})
    only = tmp_path / "only.json"
    only.write_text(json.dumps({"tiers": {"1": [{"file": "tests/unit/test_env.py", "seconds": 1.0,
                                                 "exit_code": 0, "counts": {"passed": 1}}]}}))
    shared, mine = tmp_path / "shared", (tmp_path / "mine").resolve()
    caller = clean_env(PYTHONPATH=str(snap / "src"), JAX_ENABLE_COMPILATION_CACHE="true",
                       JAX_COMPILATION_CACHE_DIR=str(shared))
    cpu = str(sorted(os.sched_getaffinity(0))[0])

    def tool(*args, enabled, folder=""):
        done = subprocess.run([sys.executable, "-B", "scripts/test_tiers.py", *args, "--cpus", cpu],
                              cwd=snap, capture_output=True, text=True, timeout=120,
                              env=dict(caller, EXPECT_ENABLED=enabled, EXPECT_DIR=folder))
        assert done.returncode == 0, done.stdout + done.stderr

    tool("run", "--tiers", str(only), "--out", str(tmp_path / "cold"), enabled="false")
    tool("run", "--tiers", str(only), "--out", str(tmp_path / "warm"), "--jax-cache", str(mine),
         enabled="true", folder=str(mine))
    tool("measure", "--only", str(only), "--out", str(tmp_path / "m"), enabled="false")
    cold, warm = (json.loads((tmp_path / d / "run.json").read_text()) for d in ("cold", "warm"))
    measured = json.loads((tmp_path / "m" / "measured.json").read_text())
    assert cold["jax_compilation_cache"] == measured["jax_compilation_cache"] == "disabled"
    assert warm["jax_compilation_cache"] == str(mine)
    assert [r["exit_code"] for r in cold["files"] + warm["files"] + measured["files"]] == [0, 0, 0]
    assert not shared.exists()
