"""scripts/test_tiers.py's only-list and its landing-time fold (D222's second and third faults).

- measure --only under the default --only-tiers 1 2: an only-list without a "2" key raised
  KeyError (the operators' 42ca1c94 measurement, 18 November 2026). Now a tier the list does not
  hold selects nothing, and a listed file that is not a test file is refused.
- fold: a landing's measured rows go onto main's current record at landing time, never as a
  folded file merged in. Today's conflict was the bundle's row commit 2aa7421e, folded against an
  older record, against main's three rows from 746a37ef. A re-measured row is replaced in place
  (or moved, when its time changes its tier); a new row is inserted at its sorted place; every other
  row stays as it stands, in its order (main's out-of-order rows included); the measurements'
  sources and provenance are appended once each. Refused, with nothing written, when a row would
  be dropped, when a measured file is not a test file, or when a measured row failed.
- fold and tiers take only a measurement marked cold (D321 R1): an unmarked or warm one is refused,
  and an unmarked one from before the marker existed passes only with --pre-marker-ok.
Host only: the script is loaded from its path and no test file is run.
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test_tiers.py"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("test_tiers_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def f(name):
    return f"tests/unit/{name}.py"


def row(name, seconds, passed=1, exit_code=0, **counts):
    return dict(file=f(name), seconds=seconds, exit_code=exit_code,
                counts=dict(passed=passed, **counts))


# ------------------------------------------------------------------------------------ only


def test_an_only_list_without_tier_2_selects_its_tier_1_files(tool):
    doc = {"tiers": {"1": [{"file": f("a")}]}}
    with pytest.raises(KeyError):  # The fault: the old selection expression.
        _ = {r["file"] for t in (1, 2) for r in doc["tiers"][str(t)]}
    assert tool.only_files(doc, [1, 2], [f("a"), f("b")]) == [f("a")]
    assert tool.only_files({"tiers": {}}, [1, 2], [f("a")]) == []


def test_an_only_list_naming_no_test_file_is_refused(tool):
    with pytest.raises(SystemExit, match="not test files"):
        tool.only_files({"tiers": {"1": [{"file": f("typo")}]}}, [1], [f("a")])


# ------------------------------------------------------------------------------------ fold


def record(rows1, rows2=(), rows3=()):
    return dict(kind="cells.test_tiers@1", measured=["m0"], measured_provenance=[{"r": 0}],
                fast_seconds=20.0, cap_seconds=90.0,
                tiers={"1": list(rows1), "2": list(rows2), "3": list(rows3)}, note="kept")


def measured(*rows, revision="b", mark="disabled"):
    """measure's record of ROWS; MARK is its compilation cache marker (None: made before it)."""
    doc = dict(provenance={"git_revision": revision}, files=list(rows), cap_seconds=90.0)
    if mark is not None:
        doc["jax_compilation_cache"] = mark
    return doc


def files_of(*records):
    return sorted({r["file"] for rec in records for t in rec["tiers"].values() for r in t}
                  | {f(n) for n in ("new", "moved", "z_new")})


def test_a_new_row_is_inserted_and_every_other_row_kept_in_its_order(tool):
    rows = [row("b", 1), row("d", 2), row("a_out_of_order", 3)]  # main's order, as it stands
    base = record(rows, [row("x", 30)])
    out = tool.fold_rows(base, [measured(row("c_new", 4))], ["m1"], files_of(base) + [f("c_new")])
    assert [r["file"] for r in out["tiers"]["1"]] == [f("b"), f("c_new"), f("d"),
                                                     f("a_out_of_order")]
    assert out["tiers"]["2"] == base["tiers"]["2"]
    assert out["measured"] == ["m0", "m1"] and out["measured_provenance"][-1] == {
        "git_revision": "b"}
    assert {k: out[k] for k in ("kind", "fast_seconds", "cap_seconds", "note")} == {
        k: base[k] for k in ("kind", "fast_seconds", "cap_seconds", "note")}
    again = tool.fold_rows(out, [measured(row("c_new", 4))], ["m1"], files_of(out))
    assert again == out  # Idempotent: a source is appended once.


def test_a_remeasured_row_is_replaced_in_place_or_moved_with_its_tier(tool):
    base = record([row("a", 1), row("moved", 2), row("c", 3)], [row("x", 30), row("y", 40)])
    out = tool.fold_rows(base, [measured(row("a", 5, passed=7), row("moved", 25))], ["m1"],
                         files_of(base))
    assert [r["file"] for r in out["tiers"]["1"]] == [f("a"), f("c")]
    assert out["tiers"]["1"][0]["counts"] == {"passed": 7} and out["tiers"]["1"][0]["seconds"] == 5
    assert [r["file"] for r in out["tiers"]["2"]] == [f("moved"), f("x"), f("y")]


def test_todays_conflict_is_a_fold_not_a_merge(tool):
    """The branch folded its row against an older record; main then gained three rows. Taking the
    branch's folded file would drop main's three rows; folding the branch's measurement onto main's
    current record keeps them and adds the branch's row."""
    older = record([row("a", 1), row("c", 2)])
    branch_folded = tool.fold_rows(older, [measured(row("z_new", 3))], ["mb"],
                                   files_of(older) + [f("z_new")])
    main_now = record([row("a", 1), row("b_main", 1), row("c", 2), row("d_main", 1)],
                      [row("e_main", 25)])
    main_rows = {r["file"] for t in main_now["tiers"].values() for r in t}
    branch_rows = {r["file"] for t in branch_folded["tiers"].values() for r in t}
    assert sorted(main_rows - branch_rows) == [f("b_main"), f("d_main"), f("e_main")]  # Dropped.
    out = tool.fold_rows(main_now, [measured(row("z_new", 3))], ["mb"],
                         sorted(main_rows | {f("z_new")}))
    kept = {r["file"] for t in out["tiers"].values() for r in t}
    assert kept == main_rows | {f("z_new")}


def test_fold_refuses_a_dropped_row_an_unknown_file_and_a_failing_row(tool):
    base = record([row("a", 1), row("left_tests", 2)])
    with pytest.raises(SystemExit, match="never drops a row"):
        tool.fold_rows(base, [measured(row("a", 1))], ["m1"], [f("a")])
    with pytest.raises(SystemExit, match="not under tests"):
        tool.fold_rows(base, [measured(row("nowhere", 1))], ["m1"], files_of(base))
    for bad in (row("a", 1, exit_code=1), row("a", 1, failed=1), row("a", 1, error=2)):
        with pytest.raises(SystemExit, match="did not pass"):
            tool.fold_rows(base, [measured(bad)], ["m1"], files_of(base))


def test_a_row_that_reached_the_cap_folds_into_tier_3(tool):
    """measure records a file that reached the cap as timed_out with exit code None; fold places
    it in tier 3 (19 November: FR-2's restart file), and still refuses a timed-out row that had
    already failed a test."""
    base = record([row("a", 1)], [row("x", 30)], [row("slow", 90.02, exit_code=None, passed=0)])
    capped = dict(row("new", 90.12, exit_code=None, passed=0), timed_out=True)
    out = tool.fold_rows(base, [measured(capped)], ["m1"], files_of(base) + [f("new")])
    assert [r["file"] for r in out["tiers"]["3"]] == [f("new"), f("slow")]
    assert out["tiers"]["3"][0]["exit_code"] is None and out["tiers"]["3"][0]["seconds"] == 90.12
    assert "timed_out" not in out["tiers"]["3"][0]  # The record keeps its row form.
    failed = dict(row("new", 90.12, exit_code=None, passed=0, failed=1), timed_out=True)
    with pytest.raises(SystemExit, match="did not pass"):
        tool.fold_rows(base, [measured(failed)], ["m1"], files_of(base) + [f("new")])
    unmarked = row("new", 90.12, exit_code=None, passed=0)  # No timed_out: a missing exit code.
    with pytest.raises(SystemExit, match="did not pass"):
        tool.fold_rows(base, [measured(unmarked)], ["m1"], files_of(base) + [f("new")])


def test_the_fold_command_writes_nothing_when_refused(tool, tmp_path, monkeypatch):
    base = record([row("a", 1)])
    (tmp_path / "record.json").write_text(json.dumps(base))
    (tmp_path / "m.json").write_text(json.dumps(measured(row("a", 1, exit_code=1))))
    monkeypatch.setattr(tool, "_test_files", lambda: [f("a")])
    out = tmp_path / "out.json"
    with pytest.raises(SystemExit, match="did not pass"):
        tool.main(["fold", "--record", str(tmp_path / "record.json"), "--measured",
                   str(tmp_path / "m.json"), "--out", str(out)])
    assert not out.exists()
    (tmp_path / "m.json").write_text(json.dumps(measured(row("a", 2, passed=3))))
    tool.main(["fold", "--record", str(tmp_path / "record.json"), "--measured",
               str(tmp_path / "m.json"), "--out", str(out)])
    assert json.loads(out.read_text())["tiers"]["1"][0]["counts"] == {"passed": 3}


@pytest.mark.parametrize("mark, utc, flag, refused", [
    ("disabled", None, False, None),  # measure's cold marker: taken.
    (None, None, False, "no cold marker"),  # No marker: its seconds may be warm.
    ("/mnt/x/jax-cache", None, False, "with the compilation cache"),  # A warm run's record.
    (None, "2026-11-20T10:00:00+00:00", True, None),  # Unmarked from before the marker, as allowed.
    (None, "2026-12-01T10:00:00+00:00", True, "no cold marker"),  # Unmarked after it: refused.
    ("/mnt/x/jax-cache", "2026-11-20T10:00:00+00:00", True, "with the compilation cache"),
])
def test_fold_and_tiers_take_only_a_measurement_marked_cold(tool, tmp_path, monkeypatch, mark,
                                                            utc, flag, refused):
    """D321 R1: tier membership is decided by seconds, so only a cold measurement places a row."""
    (tmp_path / "record.json").write_text(json.dumps(record([row("a", 1)])))
    doc = measured({**row("a", 2, passed=3), "timed_out": False}, mark=mark)
    if utc:
        doc["provenance"]["utc"] = utc
    (tmp_path / "m.json").write_text(json.dumps(doc))
    monkeypatch.setattr(tool, "_test_files", lambda: [f("a")])
    for command in (["fold", "--record", str(tmp_path / "record.json")], ["tiers"]):
        out = tmp_path / f"{command[0]}.json"
        argv = [*command, "--measured", str(tmp_path / "m.json"), "--out", str(out)]
        argv += ["--pre-marker-ok"] if flag else []
        if refused:
            with pytest.raises(SystemExit, match=refused):
                tool.main(argv)
            assert not out.exists()
        else:
            tool.main(argv)
            assert json.loads(out.read_text())["tiers"]["1"][0]["counts"] == {"passed": 3}


# ----------------------------------------------------------------------------------- merge


def test_merge_keeps_both_sides_rows(tool):
    """The branch added a row and re-measured one in place; main added two rows (one out of order):
    all are kept, main's order stands, the branch's new row goes to its sorted place, and its
    in-place change stays in place even after a new row lands ahead of it in the same tier."""
    base = record([row("b", 1), row("d", 2)], [row("x", 30)])
    ours = record([row("a_branch", 1), row("b", 1), row("d", 5, passed=4)], [row("x", 30)])
    ours["measured"].append("m_branch")
    ours["measured_provenance"].append({"r": "branch"})
    theirs = record([row("b", 1), row("c_main", 1), row("d", 2), row("a2_main_out_of_order", 1)],
                    [row("x", 30), row("y_main", 40)])
    theirs["measured"].append("m_main")
    theirs["measured_provenance"].append({"r": "main"})
    out = tool.merge_rows(base, ours, theirs)
    assert [r["file"] for r in out["tiers"]["1"]] == [
        f("a_branch"), f("b"), f("c_main"), f("d"), f("a2_main_out_of_order")]
    assert next(r for r in out["tiers"]["1"] if r["file"] == f("d"))["counts"] == {"passed": 4}
    assert [r["file"] for r in out["tiers"]["2"]] == [f("x"), f("y_main")]
    assert out["measured"] == ["m0", "m_main", "m_branch"]
    assert out["measured_provenance"] == [{"r": 0}, {"r": "main"}, {"r": "branch"}]


def test_merge_moves_removes_and_agrees(tool):
    base = record([row("a", 1), row("gone", 2), row("same", 3)], [row("x", 30)])
    ours = record([row("same", 4)], [row("a", 25), row("x", 30)])  # a moved; gone removed
    theirs = record([row("a", 1), row("gone", 2), row("same", 4)], [row("x", 30)])
    out = tool.merge_rows(base, ours, theirs)  # "same": the same change on both sides.
    assert [r["file"] for r in out["tiers"]["1"]] == [f("same")]
    assert [r["file"] for r in out["tiers"]["2"]] == [f("a"), f("x")]


@pytest.mark.parametrize("plant", ["both_remeasured", "removed_and_changed", "key"])
def test_a_clash_is_refused(tool, tmp_path, plant):
    base = record([row("a", 1)])
    ours, theirs = record([row("a", 2)]), record([row("a", 3)])  # The same file, differently.
    if plant == "removed_and_changed":
        ours = record([])
    if plant == "key":
        ours, theirs = record([row("a", 1)]), record([row("a", 1)])
        ours["fast_seconds"], theirs["fast_seconds"] = 15.0, 25.0
    with pytest.raises(SystemExit, match="merge refused"):
        tool.merge_rows(base, ours, theirs)
    paths = []
    for name, doc in (("base", base), ("ours", ours), ("theirs", theirs)):
        paths.append(tmp_path / f"{name}.json")
        paths[-1].write_text(json.dumps(doc))
    with pytest.raises(SystemExit, match="merge refused"):
        tool.main(["merge", "--base", str(paths[0]), "--ours", str(paths[1]), "--theirs",
                   str(paths[2]), "--out", str(tmp_path / "out.json")])
    assert not (tmp_path / "out.json").exists()
