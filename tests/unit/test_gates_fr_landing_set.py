"""FR's bitwise landing set's repository tools: the verdict reader and the snapshot freezer.

- scripts/gates/fr_landing_verdict.py reads the set as the earlier landing verdicts were read: nine
  identical quick parts (FR-5's start may differ in its extract digest only), and both windowed arms
  bitwise against the rehearsal's records, run times apart, and completed. Each departure is planted
  here and must show under `unexpected`. The planner's admission estimate
  (resources.estimated_working_bytes) is information, not compared: a set differing in it alone
  passes with it reported, and another resources leaf still fails. The script runs as the gates run
  it (python -I), on this checkout as the snapshot it imports the judges' helpers from.
- scripts/gates/freeze_snapshot.py selects its scope's tracked files (full: everything but
  visualizer/; guards: src/cells, validation, tests and pyproject.toml), freezes them with the
  checkout's own validation/source_snapshot.py, and reports whether the selection is clean. A dirty
  file must make it unclean, and --require-clean must then exit 1. It runs on a throwaway Git
  repository holding a copy of that tool.
- scripts/gates/fr_landing_set.sh's lock: when its flock is killed while it waits, the set must
  refuse and run nothing. The set runs as a copy beside stubs of the holder and the verdict, in its
  own process group, so no case here can reach a real lane or start a unit.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VERDICT = ROOT / "scripts" / "gates" / "fr_landing_verdict.py"
FREEZE = ROOT / "scripts" / "gates" / "freeze_snapshot.py"
QUICK = ("start", "rung_1ms", "control_k1", "control_k2", "control_k3", "T_control", "R_control",
         "R_rung_0p5ms", "T_rung_0p5ms")


def landing(tmp_path, plant=None):
    land, before = tmp_path / "landing", tmp_path / "before"
    land.mkdir()
    before.mkdir()
    for name in QUICK:
        if plant == "eight" and name == "T_rung_0p5ms":
            continue
        part = dict(identical=True, differences=[])
        if plant == "quick" and name == "rung_1ms":
            part = dict(identical=False, differences=[".records.pH_L"])
        if name == "start" and plant in ("start_digest", "start_other"):
            found = ".extract_sha256" if plant == "start_digest" else ".records.x"
            part = dict(identical=False, differences=[found])
        if name == "rung_1ms" and plant in ("estimate", "resources"):
            found = [".resources.estimated_working_bytes"]
            part = dict(identical=False, differences=found + [".resources.window_width"] * (
                plant == "resources"))
        doc = dict(a_source=dict(git_revision="old"), b_source=dict(git_revision="new"),
                   parts={name: part})
        (land / f"compare-{name}.json").write_text(json.dumps(doc))
    for arm in ("T", "R"):
        old = dict(kind="windowed", wall_s=1.0, records=dict(
            completed=True, steps=100, x=[1.0, 2.0], seconds=5.0,
            resources=dict(estimated_working_bytes=11760, window_width=1000)))
        new = json.loads(json.dumps(old))
        new["wall_s"], new["records"]["seconds"] = 9.0, 7.0  # Run times differ: not compared.
        if plant in ("estimate", "resources"):
            new["records"]["resources"]["estimated_working_bytes"] = 19600
        if plant == "resources" and arm == "T":
            new["records"]["resources"]["window_width"] = 999
        if plant == "windowed" and arm == "T":
            new["records"]["x"][1] = 2.0000000000000004
        if plant == "incomplete" and arm == "R":
            new["records"]["completed"] = False
        (before / f"before-{arm}.json").write_text(json.dumps(old))
        if not (plant == "missing" and arm == "R"):
            (land / f"windowed-{arm}.json").write_text(json.dumps(new))
    return land, before


def verdict(tmp_path, plant=None):
    land, before = landing(tmp_path, plant)
    out = tmp_path / "verdict.json"
    done = subprocess.run([sys.executable, "-I", str(VERDICT), str(ROOT), str(land), str(before),
                           str(out)], capture_output=True, text=True, timeout=120)
    return done.returncode, json.loads(out.read_text())


def test_a_bitwise_set_passes(tmp_path):
    code, doc = verdict(tmp_path)
    assert code == 0 and doc["passed"] and doc["unexpected"] == {}
    assert doc["windowed"]["T"]["bitwise"] and len(doc["quick_20s"]) == 9
    assert doc["kind"].startswith("FR's bitwise landing set at new")
    # The admission estimate is reported, not compared (the third review's finding 3).
    (tmp_path / "estimate").mkdir()
    code, doc = verdict(tmp_path / "estimate", "estimate")
    assert code == 0 and doc["passed"], doc["unexpected"]
    leaf = ".records.resources.estimated_working_bytes"
    assert doc["windowed"]["T"]["estimate"] == dict(before={leaf: 11760}, after={leaf: 19600})


def test_the_start_may_differ_in_its_extract_digest_only(tmp_path):
    code, doc = verdict(tmp_path, "start_digest")
    assert code == 0 and doc["passed"]


@pytest.mark.parametrize("plant, key", [
    ("quick", "quick:rung_1ms"), ("start_other", "quick:start"), ("eight", "quick_count"),
    ("windowed", "windowed:T"), ("missing", "windowed:R"), ("incomplete", "windowed:R"),
    ("resources", "quick:rung_1ms"), ("resources", "windowed:T")])
def test_each_departure_is_unexpected(tmp_path, plant, key):
    code, doc = verdict(tmp_path, plant)
    assert code == 1 and not doc["passed"] and key in doc["unexpected"], doc["unexpected"]


# ---------------------------------------------------------------------------------- freezer


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=test",
                           "-c", "user.email=test@invalid", *args],
                          capture_output=True, text=True, check=True, timeout=60).stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    for name, text in {"src/cells/a.py": "A = 1\n", "tests/t.py": "T = 1\n", "docs/d.md": "d\n",
                       "visualizer/v.js": "v\n", "pyproject.toml": "[project]\n"}.items():
        (r / name).parent.mkdir(parents=True, exist_ok=True)
        (r / name).write_text(text)
    (r / "validation").mkdir()
    shutil.copy(ROOT / "validation" / "source_snapshot.py", r / "validation" / "source_snapshot.py")
    git(tmp_path, "init", "-q", str(r))
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "a test tree")
    return r


def freeze(repo, dest, *extra):
    done = subprocess.run([sys.executable, "-B", str(FREEZE), str(repo), str(dest), *extra],
                          capture_output=True, text=True, timeout=120)
    return done.returncode, (json.loads(done.stdout.strip().splitlines()[-1])
                             if done.stdout.strip() else done.stderr)


def snapshot_files(dest):
    return sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*")
                  if p.is_file() and p.name != "SNAPSHOT.json")


def test_the_scopes_select_their_tracked_files(repo, tmp_path):
    code, full = freeze(repo, tmp_path / "full")
    assert code == 0 and full["clean"] and full["files"] == 5
    assert "visualizer/v.js" not in snapshot_files(tmp_path / "full")
    assert "docs/d.md" in snapshot_files(tmp_path / "full")
    code, guards = freeze(repo, tmp_path / "guards", "--scope", "guards")
    assert code == 0 and guards["clean"] and guards["files"] == 4
    assert "docs/d.md" not in snapshot_files(tmp_path / "guards")
    assert json.loads((tmp_path / "guards" / "SNAPSHOT.json").read_text())["git_revision"] == (
        git(repo, "rev-parse", "HEAD").strip())


def test_a_dirty_file_makes_the_selection_unclean(repo, tmp_path):
    (repo / "src" / "cells" / "a.py").write_text("A = 2\n")
    code, dirty = freeze(repo, tmp_path / "dirty")
    assert code == 0 and not dirty["clean"]
    code, _ = freeze(repo, tmp_path / "required", "--require-clean")
    assert code == 1
    (repo / "docs" / "d.md").write_text("changed\n")  # Outside the guards' scope.
    (repo / "src" / "cells" / "a.py").write_text("A = 1\n")
    code, guards = freeze(repo, tmp_path / "guards", "--scope", "guards", "--require-clean")
    assert code == 0 and guards["clean"]


# ------------------------------------------------------------- the set's lock: a killed flock


SET = ROOT / "scripts" / "gates" / "fr_landing_set.sh"


def flock_child(parent, lock, timeout=20.0):
    """The flock process the set started on the lock (its argument), once it waits."""
    import os
    import time

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
            if (os.path.basename(argv[0].decode()) == "flock" and str(lock).encode() in argv
                    and ppid == parent):
                return int(entry.name)
        time.sleep(0.05)
    raise AssertionError("the set's flock did not start")


def stub_gates(tmp_path):
    """The set script as it stands, copied beside stubs of the holder and the verdict that only
    leave a mark. Whatever happens in the test, nothing can reach a real lane or start a unit."""
    gates = tmp_path / "gates"
    gates.mkdir()
    shutil.copy2(SET, gates / SET.name)
    (gates / "fr_landing_holder.sh").write_text('#!/bin/bash\ntouch "$4/holder-ran"\n')
    (gates / "fr_landing_verdict.py").write_text(
        "import pathlib\nimport sys\npathlib.Path(sys.argv[2], 'verdict-ran').touch()\n")
    return gates / SET.name


def test_a_killed_flock_refuses_the_set_and_runs_nothing(repo, tmp_path):
    """The plant: the lane's lock is held, the set waits in flock, and the flock is killed. The set
    must refuse (exit 2, done 2) without running the holder or the verdict, and remove its worktree.
    The gate scripts built as `exec 9> LOCK; flock 9` ran on unlocked when that happened. Its own
    process group is killed before the lock is released, so nothing outlives the test."""
    import fcntl
    import os
    import signal

    script, lock, out = stub_gates(tmp_path), tmp_path / "lane.lock", tmp_path / "out"
    rev = git(repo, "rev-parse", "HEAD").strip()
    env = dict(os.environ, REPO=str(repo), LANE_LOCK=str(lock), PY=sys.executable)
    with open(lock, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        run = subprocess.Popen(["bash", str(script), rev, str(out)], env=env,
                               start_new_session=True)
        try:
            os.kill(flock_child(run.pid, lock), signal.SIGTERM)
            code = run.wait(timeout=60)
        finally:
            try:
                os.killpg(run.pid, signal.SIGKILL)  # Anything left, while the lock is still held.
            except ProcessLookupError:
                pass
            run.wait()
    assert code == 2 and (out / "done").read_text().strip() == "2"
    log = (out / "fr-landing-set.log").read_text()
    assert "refused: the holder did not run to its end" in log
    assert not (out / "fr-landing" / "holder-ran").exists()  # The holder never ran.
    assert not (out / "fr-landing" / "verdict-ran").exists()  # Nor the verdict.
    assert not (out / "fr-worktree").exists()  # Its worktree removed.
