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
"""

import fcntl
import importlib.util
import json
import os
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
if a[:2] == ["-m", "pytest"]:
    note("collect " + cwd.name)
    ids = [l for l in (cwd / "ids.txt").read_text().splitlines() if "::" in l]
    n = int((cwd / "collected.txt").read_text()) if (cwd / "collected.txt").exists() else len(ids)
    print("\n".join(ids)); print(f"{n} tests collected in 0.01s"); sys.exit(0)
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
    note("save " + set_name)
    (part / set_name).mkdir(parents=True, exist_ok=True)
    manifest = {"worlds": {}}
    for w in worlds:
        (part / set_name / (w + ".json")).write_text("{}")
        manifest["worlds"][set_name + "/" + w] = {"seconds": 2.5, "digests": {"x": "1"}}
    (part / "manifest.json").write_text(json.dumps(manifest)); sys.exit(0)
if a[:2] == ["validation/results_baseline.py", "compare"]:
    note("g1 compare")
    x = json.loads((Path(a[2]) / "manifest.json").read_text())["worlds"]
    y = json.loads((Path(a[3]) / "manifest.json").read_text())["worlds"]
    ok = x.keys() == y.keys() and all(x[k]["digests"] == y[k]["digests"] for k in x)
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
    env = dict(os.environ, **world["env"], LANE="custom", GATE_LOCK=str(tmp / "lane.lock"),
               GATE_CPUS=cpu, PRELOCK_CPU=cpu, PRELOCK_NICE="0", PY=str(py),
               HOSTPY=sys.executable, GATE_CACHE=str(tmp / "cache"), STUB_LOG=str(tmp / "calls"),
               CROSSREV_SETS="kinds")
    world["envs"] = env
    return world


def run_gate(world, out, **extra):
    env = dict(world["envs"], **extra)
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
                          env=gate["envs"], capture_output=True, text=True, timeout=60)
    assert done.returncode == 2 and "was used before" in done.stderr
    assert sorted(p.name for p in out.iterdir()) == ["done", "locked.done"]


def test_a_killed_flock_runs_nothing_under_the_lock(gate):
    """With PRELOCK=lane the pre-lock steps run under the lock too, so nothing may run at all."""
    lock, out = gate["tmp"] / "lane.lock", gate["tmp"] / "out"
    (gate["tmp"] / "calls").write_text("")
    with open(lock, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        run = subprocess.Popen(["bash", str(GATE), str(gate["head"]), str(gate["base"]), str(out)],
                               env=dict(gate["envs"], PRELOCK="lane"), start_new_session=True)
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
