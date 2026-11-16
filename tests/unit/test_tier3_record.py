"""Tier 3's record and its diff (scripts/test_tiers.py freeze and diff, D187), on planted runs.

Each landing's tier-3 table is frozen per test ID; a later tier-3 run is compared with it and
only what changed is reported. These tests plant run folders (run.json, pytest -q logs and the
tree's collected IDs) and check that every kind of change is caught, and that what must not be
reported is not: the same error under other paths and addresses, and a time inside the factor.
Host only: the script is loaded from its path and no test file is run.
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test_tiers.py"
FILE = "tests/unit/test_planted.py"
IDS = ["test_a", "test_b[x]", "TestC::test_c", "test_d[a b - c]", "test_e"]


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("test_tiers_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def log(chars, failures=(), errors=(), final=None):
    """A pytest -q log: progress characters, FAILURES and ERRORS sections, the short summary.

    failures and errors: (test ID, E lines, summary message). final=None writes a completed
    log's summary; final=False stops after the progress characters (killed at the cap).
    """
    lines = [chars + (" [100%]" if final is not False else "")]
    if final is False:
        return "\n".join(lines) + "\n"
    if failures:
        lines.append("=" * 35 + " FAILURES " + "=" * 35)
        for test, e_lines, _ in failures:
            lines += [f"{'_' * 20} {test.replace('::', '.')} {'_' * 20}", "", ">   assert x"]
            lines += [f"E   {e}" for e in e_lines] + ["", f"{FILE}:9: AssertionError"]
    if errors:
        lines.append("=" * 36 + " ERRORS " + "=" * 36)
        for test, e_lines, _ in errors:
            lines += [f"{'_' * 6} ERROR at setup of {test.replace('::', '.')} {'_' * 6}"]
            lines += [f"E   {e}" for e in e_lines]
    lines.append("=" * 27 + " short test summary info " + "=" * 28)
    for word, entries in (("FAILED", failures), ("ERROR", errors)):
        lines += [f"{word} {FILE}::{t}" + (f" - {m}" if m else "") for t, _, m in entries]
    words = {".": "passed", "F": "failed", "E": "error", "s": "skipped"}
    counts = {w: chars.count(c) for c, w in words.items() if chars.count(c)}
    lines.append(", ".join(f"{n} {w}" for w, n in counts.items()) + " in 1.00s")
    return "\n".join(lines) + "\n"


def plant(tmp_path, name, files, cap=1800.0):
    """A finished run folder on its own tree: {file: (log text, seconds, ending, ids)}.

    ending: an exit code, "timeout" or a negative signal. Returns (run folder, its listing).
    The tree and the run folder are distinct per run, so their paths differ between runs.
    """
    root, run_dir = tmp_path / f"tree-{name}", tmp_path / f"run-{name}"
    (run_dir / "logs").mkdir(parents=True)
    root.mkdir()
    rows, listing = [], {}
    for path, (text, seconds, ending, ids) in files.items():
        logfile = run_dir / "logs" / (path.replace("/", "__") + ".log")
        logfile.write_text(text.replace("{root}", str(root)).replace("{run}", str(run_dir)))
        chars = text.splitlines()[0].split(" ")[0]
        counts = {}
        if ending != "timeout" and ending >= 0:
            for c, w in ((".", "passed"), ("F", "failed"), ("E", "error"), ("s", "skipped")):
                if chars.count(c):
                    counts[w] = chars.count(c)
        rows.append(
            {
                "file": path,
                "seconds": seconds,
                "exit_code": None if ending == "timeout" else ending,
                "timed_out": ending == "timeout",
                "counts": counts,
                "log": str(logfile),
            }
        )
        listing[path] = ids
    header = {"kind": "cells.test_tier_run@1", "cap_seconds": cap}
    header["provenance"] = {"root": str(root), "python": str(tmp_path / "venv" / "bin" / "python")}
    (run_dir / "run.json").write_text(json.dumps({**header, "files": rows}))
    ids_path = run_dir / "collected.json"
    ids_path.write_text(
        json.dumps({"kind": "cells.test_ids@1", "root": str(root), "files": listing})
    )
    return run_dir, ids_path


def failing_b(e_line="AssertionError: assert 2 == 1"):
    return [("test_b[x]", [e_line], "AssertionError")]


BASE = log(".F...", failing_b())


def freeze_and_diff(tool, tmp_path, base, later, **options):
    """Freeze the base run and diff the later one: (blocking, reported, unchanged files)."""
    run_a, ids_a = plant(tmp_path, "a", base)
    run_b, ids_b = plant(tmp_path, "b", later)
    record, _ = tool.readings([run_a], [ids_a])
    found, _ = tool.readings([run_b], [ids_b])
    return tool.diff_readings({"files": record}, found, **options)


def kinds(entries):
    return sorted((e["kind"], e.get("test", "")) for e in entries)


def test_a_run_against_its_own_record_has_no_changes(tool, tmp_path):
    files = {FILE: (BASE, 100.0, 1, IDS)}
    blocking, reported, unchanged = freeze_and_diff(tool, tmp_path, files, files)
    assert (blocking, reported, unchanged) == ([], [], [FILE])


def test_a_new_failure_blocks(tool, tmp_path):
    later = log(".F..F", failing_b() + [("test_e", ["ValueError: bad"], "")])
    blocking, reported, _ = freeze_and_diff(
        tool, tmp_path, {FILE: (BASE, 100.0, 1, IDS)}, {FILE: (later, 100.0, 1, IDS)}
    )
    assert kinds(blocking) == [("new failure", "test_e")]
    assert blocking[0]["was"] == "passed" and blocking[0]["errors_now"] == ["E   ValueError: bad"]
    assert reported == []


def test_a_new_pass_is_reported_not_blocking(tool, tmp_path):
    blocking, reported, _ = freeze_and_diff(
        tool, tmp_path, {FILE: (BASE, 100.0, 1, IDS)}, {FILE: (log("....."), 100.0, 0, IDS)}
    )
    assert blocking == []
    assert kinds(reported) == [("new pass", "test_b[x]")]


def test_a_changed_error_blocks(tool, tmp_path):
    later = log(".F...", failing_b("AssertionError: assert 3 == 1"))
    blocking, _, _ = freeze_and_diff(
        tool, tmp_path, {FILE: (BASE, 100.0, 1, IDS)}, {FILE: (later, 100.0, 1, IDS)}
    )
    assert kinds(blocking) == [("changed error", "test_b[x]")]
    assert blocking[0]["errors_was"] == ["E   AssertionError: assert 2 == 1"]
    assert blocking[0]["errors_now"] == ["E   AssertionError: assert 3 == 1"]


def test_the_same_error_under_other_paths_and_addresses_is_unchanged(tool, tmp_path):
    """Must not report: each run's tree, run folder, pytest tmp, home and addresses differ."""

    def run(user, number, address):
        e_line = (
            "FileNotFoundError: {root}/src/cells/x.py, {run}/outputs/f/y.npz, "
            f"/tmp/pytest-of-{user}/pytest-{number}/t0/z, /home/{user}/w, <obj at {address}>"
        )
        return {FILE: (log(".F...", failing_b(e_line)), 100.0, 1, IDS)}

    blocking, reported, unchanged = freeze_and_diff(
        tool, tmp_path, run("someone", 15199, "0x7f12ab"), run("other", 3, "0xdeadbeef")
    )
    assert (blocking, reported, unchanged) == ([], [], [FILE])


def test_time_beyond_the_factor_is_reported_and_inside_it_is_not(tool, tmp_path):
    slow, inside, small = "tests/unit/test_slow.py", "tests/unit/test_inside.py", FILE
    base = {
        p: (log("....."), s, 0, IDS) for p, s in ((slow, 100.0), (inside, 100.0), (small, 10.0))
    }
    later = {
        p: (log("....."), s, 0, IDS) for p, s in ((slow, 250.0), (inside, 190.0), (small, 40.0))
    }
    blocking, reported, unchanged = freeze_and_diff(tool, tmp_path, base, later)
    assert blocking == []
    assert [(e["file"], e["kind"], e["factor"]) for e in reported] == [(slow, "time", 2.5)]
    assert sorted(unchanged) == [inside, small]  # 1.9 x, and 30 s apart (under min_seconds)


def test_removed_and_added_tests(tool, tmp_path):
    ids_later = [i for i in IDS if i != "TestC::test_c"] + ["test_f"]
    later = log(".F...", failing_b())
    blocking, reported, _ = freeze_and_diff(
        tool, tmp_path, {FILE: (BASE, 100.0, 1, IDS)}, {FILE: (later, 100.0, 1, ids_later)}
    )
    assert kinds(blocking) == [("removed", "TestC::test_c")]
    assert kinds(reported) == [("added", "test_f")]


def test_a_timeout_is_compared_by_position_within_what_it_reached(tool, tmp_path):
    """Record: 4 of 5 reached, all passing. Now: 2 reached, the second failing."""
    base = {FILE: (log("....", final=False), 1800.0, "timeout", IDS)}
    later = {FILE: (log(".F", final=False), 1800.0, "timeout", IDS)}
    blocking, reported, _ = freeze_and_diff(tool, tmp_path, base, later)
    assert kinds(blocking) == [("new failure", "test_b[x]")]
    assert blocking[0]["was"] == "passed" and "errors_now" not in blocking[0]  # killed: no text
    assert kinds(reported) == [("not reached", "TestC::test_c"), ("not reached", "test_d[a b - c]")]
    later = {FILE: (log(".", final=False), 1800.0, "timeout", IDS)}
    _, reported, _ = freeze_and_diff(tool, tmp_path / "x", base, later)
    assert ("time", "") in kinds(reported)  # 1 reached against 4: beyond the factor


def test_a_new_timeout_and_a_signal_ending_block(tool, tmp_path):
    other = "tests/unit/test_other.py"
    base = {FILE: (log("....."), 100.0, 0, IDS), other: (log("....."), 100.0, 0, IDS)}
    later = {
        FILE: (log("...", final=False), 1800.0, "timeout", IDS),
        other: (log("..", final=False), 900.0, -9, IDS),
    }
    blocking, _, _ = freeze_and_diff(tool, tmp_path, base, later)
    assert sorted((e["file"], e["kind"]) for e in blocking) == [
        (other, "no verdict"),
        (FILE, "new timeout"),
    ]


def test_a_log_that_does_not_align_blocks_and_is_not_guessed(tool, tmp_path):
    short = log(".F..", failing_b())  # One progress character missing.
    moved = log("F....", failing_b())  # The F stands where the summary's ID is not.
    for later in (short, moved):
        blocking, _, _ = freeze_and_diff(
            tool,
            tmp_path / str(len(later)),
            {FILE: (BASE, 100.0, 1, IDS)},
            {FILE: (later, 1, 1, IDS)},
        )
        assert [e["kind"] for e in blocking] == ["unaligned"]
    run_b, ids_b = plant(tmp_path / "read", "b", {FILE: (short, 100.0, 1, IDS)})
    reading = tool.readings([run_b], [ids_b])[0][FILE]
    assert reading["aligned"] is False
    assert [t[1] for t in reading["tests"]] == [
        "unknown",
        "failed",
        "unknown",
        "unknown",
        "unknown",
    ]


def test_errors_come_from_sections_with_class_heads_setup_errors_and_spaced_ids(tool, tmp_path):
    """A class's test is headed TestC.test_c, a setup error "ERROR at setup of ...", and an
    ID holding spaces and " - " is matched in the summary against the collected IDs."""
    text = log(
        ".FFE.",
        failures=[
            ("test_b[x]", ["AssertionError: first"], ""),
            ("TestC::test_c", ["AssertionError: class head"], ""),
        ],
        errors=[
            ("test_d[a b - c]", ["RuntimeError: fixture broke"], "RuntimeError: fixture broke")
        ],
    )
    run_b, ids_b = plant(tmp_path, "b", {FILE: (text, 10.0, 1, IDS)})
    reading = tool.readings([run_b], [ids_b])[0][FILE]
    assert reading["aligned"] is True
    assert reading["tests"] == [
        ["test_a", "passed"],
        ["test_b[x]", "failed", ["E   AssertionError: first"]],
        ["TestC::test_c", "failed", ["E   AssertionError: class head"]],
        ["test_d[a b - c]", "error", ["E   RuntimeError: fixture broke"]],
        ["test_e", "passed"],
    ]


def test_freeze_writes_one_line_per_test_and_diff_runs_end_to_end(tool, tmp_path):
    run_a, ids_a = plant(tmp_path, "a", {FILE: (BASE, 100.0, 1, IDS)})
    later = log(".F..F", failing_b() + [("test_e", ["ValueError: bad"], "")])
    run_b, _ = plant(tmp_path, "b", {FILE: (later, 100.0, 1, IDS)})
    notes = tmp_path / "notes.json"
    notes.write_text(
        json.dumps({"header": {"landing": "planted"}, "files": {FILE: {"cause": "c"}}})
    )
    record = tmp_path / "record.json"
    freeze = ["freeze", "--run", str(run_a), "--collected", str(ids_a), "--out", str(record)]
    assert tool.main([*freeze, "--notes", str(notes)]) == 0
    doc = json.loads(record.read_text())
    assert doc["kind"] == "cells.tier3_record@1" and doc["landing"] == "planted"
    assert doc["files"][FILE]["cause"] == "c" and doc["cap_seconds"] == 1800.0
    assert sum(line.startswith('   ["') for line in record.read_text().splitlines()) == len(IDS)
    with pytest.raises(SystemExit, match="exists"):
        tool.main(freeze)
    same = ["diff", "--record", str(record), "--run", str(run_a), "--out", str(tmp_path / "s.json")]
    assert tool.main(same) == 0
    assert json.loads((tmp_path / "s.json").read_text())["counts"] == {}
    out = tmp_path / "d.json"
    assert tool.main(["diff", "--record", str(record), "--run", str(run_b), "--out", str(out)]) == 1
    assert json.loads(out.read_text())["counts"] == {"new failure": 1}


def test_a_run_at_another_cap_fails_the_diff(tool, tmp_path):
    run_a, ids_a = plant(tmp_path, "a", {FILE: (BASE, 100.0, 1, IDS)})
    run_b, _ = plant(tmp_path, "b", {FILE: (BASE, 100.0, 1, IDS)}, cap=300.0)
    record = tmp_path / "record.json"
    assert (
        tool.main(["freeze", "--run", str(run_a), "--collected", str(ids_a), "--out", str(record)])
        == 0
    )
    out = tmp_path / "d.json"
    assert tool.main(["diff", "--record", str(record), "--run", str(run_b), "--out", str(out)]) == 1
    assert json.loads(out.read_text())["caps_differ"] == [300.0]


def test_collect_refuses_a_tree_that_moved_on_since_the_run(tool, tmp_path):
    """IDs are collected from the tree as the run ran it: another revision is refused."""
    run_a, _ = plant(tmp_path, "a", {FILE: (BASE, 100.0, 1, IDS)})
    doc = json.loads((run_a / "run.json").read_text())
    doc["provenance"]["git_revision"] = "a" * 40
    (run_a / "run.json").write_text(json.dumps(doc))
    (tmp_path / "tree-a" / "SNAPSHOT.json").write_text(json.dumps({"git_revision": "b" * 40}))
    with pytest.raises(SystemExit, match="is at b+, but the runs recorded"):
        tool.main(["collect", "--run", str(run_a), "--out", str(tmp_path / "ids.json")])
    assert not (tmp_path / "ids.json").exists()


def test_provenance_names_a_checkout_relative_to_its_repository(tool, tmp_path, monkeypatch):
    """No home path in a public record: a tree inside the repository is named relative to it, a
    tree outside it (a snapshot) by its absolute path; _provenance records that name."""
    repo = tmp_path / "repo"
    worktree = repo / ".claude" / "worktrees" / "agent"
    worktree.mkdir(parents=True)
    assert tool.recorded_root(worktree, repo) == ".claude/worktrees/agent"
    assert tool.recorded_root(repo, repo) == "."
    snapshot = tmp_path / "snapshot"
    assert tool.recorded_root(snapshot, repo) == str(snapshot)
    assert tool.recorded_root(snapshot, None) == str(snapshot)
    monkeypatch.setattr(tool, "ROOT", worktree)
    monkeypatch.setattr(tool, "_repository", lambda: repo)
    monkeypatch.setattr(tool, "_git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    assert tool._provenance()["root"] == ".claude/worktrees/agent"


def test_a_relative_root_is_read_against_the_repository(tool, tmp_path, monkeypatch):
    """A run recorded with a relative root (a checkout's run) is read on its repository tree."""
    run_a, ids_a = plant(tmp_path, "a", {FILE: (BASE, 100.0, 1, IDS)})
    doc = json.loads((run_a / "run.json").read_text())
    doc["provenance"]["root"] = "tree-a"
    (run_a / "run.json").write_text(json.dumps(doc))
    monkeypatch.setattr(tool, "_repository", lambda: tmp_path)
    found, _ = tool.readings([run_a], [ids_a])
    assert [t[0] for t in found[FILE]["tests"]] == IDS
    assert found[FILE]["tests"][1][2] == ["E   AssertionError: assert 2 == 1"]
