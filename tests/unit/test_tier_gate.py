"""The tier gate's comparison with its record (scripts/test_tiers.py run), on planted records.

A file counts as changed when its exit code, failed or error count differs from its tier row,
when its passed count falls below the row's, or when its skipped count rises above it: tests
silently lost to collection or to a skipif that starts firing must not pass the gate. A passed
count above the row's is reported in summary.json's count_increases (a stale row to re-measure),
not changed. Host only: the script is loaded from its path and no test file is run.
"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test_tiers.py"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("test_tiers_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(name, exit_code=0, **counts):
    return {"file": f"tests/unit/{name}.py", "exit_code": exit_code, "counts": counts}


def judge(tool, now, recorded):
    """The comparison of one planted result with its planted row."""
    return tool.compare_with_record([now], {recorded["file"]: recorded})


def test_passed_decrease_is_changed(tool):
    changed, increases = judge(tool, row("a", passed=9), row("a", passed=10))
    assert [c["why"] for c in changed] == [["passed below the record"]]
    assert increases == []


def test_skipped_increase_is_changed(tool):
    changed, increases = judge(tool, row("a", passed=10, skipped=2), row("a", passed=10, skipped=1))
    assert [c["why"] for c in changed] == [["skipped above the record"]]
    assert increases == []


def test_a_test_turned_into_a_skip_is_changed(tool):
    changed, _ = judge(tool, row("a", passed=9, skipped=1), row("a", passed=10))
    assert changed[0]["why"] == ["passed below the record", "skipped above the record"]
    assert changed[0]["now"] == [0, {"passed": 9, "skipped": 1}]
    assert changed[0]["recorded"] == [0, {"passed": 10}]


def test_passed_increase_is_reported_not_changed(tool):
    changed, increases = judge(tool, row("a", passed=12), row("a", passed=10))
    assert changed == []
    assert increases == [
        {"file": "tests/unit/a.py", "now": [0, {"passed": 12}], "recorded": [0, {"passed": 10}]}
    ]


def test_unchanged_file_is_not_changed(tool):
    assert judge(tool, row("a", passed=10, skipped=1), row("a", passed=10, skipped=1)) == ([], [])


def test_outcome_rule_is_kept(tool):
    """The rule before this change: exit code, failed and error counts against the row."""
    outcomes = (row("a", 1, passed=10), row("a", passed=10, failed=1), row("a", passed=10, error=1))
    for now in outcomes:
        changed, _ = judge(tool, now, row("a", passed=10))
        assert changed[0]["why"] == ["exit code, failed or error count differs"]
    recorded_failure = row("a", 1, passed=9, failed=1)
    assert judge(tool, row("a", 1, passed=9, failed=1), recorded_failure) == ([], [])


def test_unparsed_counts_are_changed(tool):
    """A file whose summary line could not be read (no counts) does not pass as unchanged."""
    changed, _ = judge(tool, row("a"), row("a", passed=10))
    assert changed[0]["why"] == ["passed below the record"]


def test_run_writes_both_lists_and_fails_only_on_changes(tool, tmp_path, monkeypatch):
    """run() end to end, with the files' results planted in place of running them."""
    recorded = [
        row("same", passed=4),
        row("fewer", passed=4),
        row("skips", passed=4),
        row("more", passed=4),
    ]
    planted = {
        "tests/unit/same.py": row("same", passed=4),
        "tests/unit/fewer.py": row("fewer", passed=3),
        "tests/unit/skips.py": row("skips", passed=3, skipped=1),
        "tests/unit/more.py": row("more", passed=6),
    }
    record = tmp_path / "test_tiers.json"
    record.write_text(json.dumps({"tiers": {"1": recorded, "2": [], "3": []}}))
    monkeypatch.setattr(tool, "_provenance", lambda: {})
    monkeypatch.setattr(tool, "_parallel", lambda files, *a: [planted[f] for f in files])

    def run(out):
        args = SimpleNamespace(
            tiers=str(record), tier=[1], out=str(tmp_path / out), cpus=[0], cap=1.0
        )
        code = tool.run(args)
        return code, json.loads((tmp_path / out / "summary.json").read_text())

    code, summary = run("all")
    assert code == 1
    assert summary["files"] == 4
    assert [c["file"] for c in summary["changed_vs_record"]] == [
        "tests/unit/fewer.py",
        "tests/unit/skips.py",
    ]
    assert [c["file"] for c in summary["count_increases"]] == ["tests/unit/more.py"]

    del planted["tests/unit/fewer.py"], planted["tests/unit/skips.py"]
    recorded[:] = [r for r in recorded if r["file"] in planted]
    record.write_text(json.dumps({"tiers": {"1": recorded, "2": [], "3": []}}))
    code, summary = run("increase-only")
    assert code == 0
    assert summary["changed_vs_record"] == []
    assert [c["file"] for c in summary["count_increases"]] == ["tests/unit/more.py"]
