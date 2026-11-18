"""scripts/gates/crossrev_sets.py: the gates' cross-revision runner and record maker.

- The sets are the record's own, in the runner's order. Superseded copies (a dash in the name) are
  skipped. A set the runner does not know is refused, so a record cannot hold a set the gates skip.
- Each set's command lines: composite_crossrev's sets take their name after the directory, and
  the operators' own modules add their check action.
- A sweep fails when an action fails, when a compare differs, or when a file listing differs.
  The record maker compares with an earlier record only when one is given. Its log lines keep the
  shell runner's forms, which the gates grep.
The subprocesses are faked here: no set is traced. The runner's rehearsal on a real snapshot is
recorded in the hand-back.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gates" / "crossrev_sets.py"


@pytest.fixture(scope="module")
def cs():
    spec = importlib.util.spec_from_file_location("crossrev_sets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(tmp_path, names):
    r = tmp_path / "record"
    for n in names:
        (r / n).mkdir(parents=True)
        (r / n / f"{n}.world.npz").write_text("x")
    return r


def test_the_sets_are_the_records_own_in_order(cs, tmp_path):
    r = record(tmp_path, ["volume", "base", "acceptances", "kinds-superseded-20261117", "coupling"])
    assert cs.record_sets(r) == ["base", "volume", "coupling", "acceptances"]
    assert cs.chosen(None, r) == ["base", "volume", "coupling", "acceptances"]
    assert cs.chosen(["coupling", "base"], r) == ["base", "coupling"]


def test_an_unknown_set_is_refused(cs, tmp_path):
    with pytest.raises(SystemExit, match="does not know"):
        cs.record_sets(record(tmp_path, ["base", "newset"]))
    with pytest.raises(SystemExit, match="unknown sets"):
        cs.chosen(["nosuchset"], None)
    with pytest.raises(SystemExit, match="give --sets"):
        cs.chosen(None, None)


def test_the_command_lines(cs):
    base = dict(cs.commands("/snap", "/out", "base", "py"))
    assert base == {"jaxprs": ["py", "-B", "-u", "-m", cs.COMPOSITE, "jaxprs", "/out/base", "base"],
                    "bindings": ["py", "-B", "-u", "-m", cs.COMPOSITE, "bindings", "/out/base",
                                 "base"]}
    division = dict(cs.commands("/snap", "/out", "division", "py"))
    assert list(division) == ["jaxprs", "bindings", "check"]
    assert division["check"] == ["py", "-B", "-u", "-m", "validation.division.division_crossrev",
                                 "check", "/out/division"]
    replication = dict(cs.commands("/snap", "/out", "replication", "py"))
    assert replication["jaxprs"][-2:] == ["/out/replication", "replication"]


def fake_call(failing=(), differing=(), extra_file=()):
    """A call() that writes each set's files, and the compare's verdict line."""
    def call(argv, cwd, env, log_path):
        if "compare" in argv:
            name = Path(argv[-1]).name
            ok = name not in differing
            log_path.write_text("verdict " + ("identical" if ok else "differs") + "\n")
            return 0 if ok else 1
        action, target = argv[argv.index("-m") + 2], Path(argv[argv.index("-m") + 3])
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{target.name}.world.npz").write_text("x")
        if target.name in extra_file:
            (target / "stray.txt").write_text("x")
        log_path.write_text(f"{action}\n")
        return 1 if (target.name, action) in failing else 0
    return call


def sweep(cs, tmp_path, **plants):
    lines = []
    r = record(tmp_path, ["base", "division"])
    out = tmp_path / "out"
    out.mkdir()
    status = cs.sweep(tmp_path, out, ["base", "division"], r, "py", lines.append,
                      call=fake_call(**plants))
    return status, lines, out


def test_an_identical_sweep_passes_with_the_shell_runners_lines(cs, tmp_path):
    status, lines, out = sweep(cs, tmp_path)
    assert status == 0
    assert [x.split(" seconds")[0] for x in lines if " exit " in x and "compare" not in x] == [
        "base jaxprs exit 0", "base bindings exit 0", "division jaxprs exit 0",
        "division bindings exit 0", "division check exit 0"]
    assert "compare base exit 0: verdict identical; file listing same" in lines
    assert (out / "compare-division.txt").read_text().startswith("verdict identical")


@pytest.mark.parametrize("plant, expected", [
    (dict(failing=[("division", "check")]), "division check exit 1"),
    (dict(differing=["base"]), "compare base exit 1: verdict differs; file listing same"),
    (dict(extra_file=["division"]), "compare division exit 0: verdict identical; file listing "
                                    "DIFFERS")])
def test_each_departure_fails_the_sweep(cs, tmp_path, plant, expected):
    status, lines, out = sweep(cs, tmp_path, **plant)
    assert status == 1
    assert any(x.startswith(expected) for x in lines), lines
    if "extra_file" in plant:
        assert "> stray.txt" in (out / "listing-division.diff").read_text()


def test_the_record_maker_compares_only_with_a_given_previous_record(cs, tmp_path):
    lines = []
    out = tmp_path / "new-record"
    out.mkdir()
    status = cs.sweep(tmp_path, out, ["base"], None, "py", lines.append, call=fake_call())
    assert status == 0 and not any("compare" in x for x in lines)
    assert (out / "base" / "base.world.npz").exists()


def test_main_refuses_a_folder_that_is_not_a_snapshot(cs, tmp_path):
    with pytest.raises(SystemExit, match="not an execution snapshot"):
        cs.main(["run", str(tmp_path), str(tmp_path / "out"), str(record(tmp_path, ["base"]))])
