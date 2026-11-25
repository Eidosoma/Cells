"""scripts/gates/fingerprints.py: R1's definition-fingerprint check through a move map.

- The harness parts it carries (copied from R1's frozen harness) work as the harness's did: the
  definitions found in JSON trees and in G1's merged save, the normalized texts and exception keys.
  R1's record's keys are made tree-relative at their definitions folder.
- The comparison reads the old side through the move's map (move 2's, from this checkout). It
  compares digest values, not types: two records that differ only in a fingerprint's digest differ
  here, although the harness's value_key gives ["object", "builtins.str"] for both. A control
  array's bytes, a key on one side only, and a row that the map does not explain each differ too.
- Through a table of renamed IDs (--outputs, D345) a result is read before it is serialized,
  digested or cut, so an old tree's is a new tree's; a record read through one is compared only with
  another such. A world differs only where it is declared.
- A key is missing on the new side only where a list of removals names it, and a listed one must be.
  The records, the comparison and the landing script's cache key name the list's digest.
- identity checks a tree's files against a Git revision, blob by blob.
No tree is recorded here but a made-up one without an engine: the record step's rehearsal on move
2's landing-gate inputs is recorded in the hand-back.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "gates" / "fingerprints.py"
LANDING = ROOT / "scripts" / "gates" / "fingerprints_landing.sh"
MAP = ROOT / "scripts" / "moves" / "move2.json"


@pytest.fixture(scope="module")
def fp():
    spec = importlib.util.spec_from_file_location("fingerprints", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tree_relative_keys(fp):
    assert fp.tree_relative("/a/b/d188-r1/configs/x.json/ionic") == "<tree>/configs/x.json/ionic"
    assert fp.tree_relative("/t/validation/y.json") == "<tree>/validation/y.json"
    assert fp.tree_relative("g1:w/z") == "g1:w/z"
    nested = "/r/d188-r1/validation/betse/emulator/configs/betse_spatial_active.json"
    assert fp.tree_relative(nested) == (
        "<tree>/validation/betse/emulator/configs/betse_spatial_active.json")


def test_the_harness_finds_definitions(fp, tmp_path):
    d = dict(schema_version=1, model={}, experiment={}, execution={})
    (tmp_path / "defs").mkdir()
    (tmp_path / "defs" / "one.json").write_text(json.dumps(dict(runs=[dict(spec=d), 3])))
    (tmp_path / "defs" / "none.json").write_text(json.dumps(dict(other=1)))
    (tmp_path / "defs" / "broken.json").write_text("{")
    (tmp_path / "g1" / "w1").mkdir(parents=True)
    (tmp_path / "g1" / "w1" / "r.json").write_text(json.dumps(dict(definition=d)))
    found = fp.Harness.definitions([tmp_path / "defs"], tmp_path / "g1")
    assert sorted(found) == [f"{tmp_path / 'defs' / 'one.json'}/runs/0/spec", "g1:w1/r"]


def test_the_harness_normalizes_texts_and_exceptions(fp, tmp_path):
    h = fp.Harness()
    h.ROOT = tmp_path
    assert h.norm(f"{tmp_path}/cells/x.py at 0x7f3a2b1c4d5e") == "<src>/cells/x.py at 0x?"
    try:
        raise ValueError(f"bad at {tmp_path}")
    except ValueError as error:
        kind, name, text, frame = h.exc_key(error)
    assert (kind, name, text) == ("raise", "ValueError", "bad at <src>")
    assert frame[1] == "test_the_harness_normalizes_texts_and_exceptions"


def test_results_are_read_through_the_table_before_they_are_digested_or_cut(fp, tmp_path):
    table = tmp_path / "table.json"
    old, new = "cells.zeta@1", "cells.alpha_family.zeta@1"  # It sorts before cells.beta, not after.
    table.write_text(json.dumps({old: new}))
    gives = fp.reader(table)
    assert fp.reader(None) is None and gives({"a": [old, (old,)]}) == {"a": [new, (new,)]}

    class Spec:
        fingerprint = "f" * 64

        def __init__(self, law):
            self.law = law

        def to_dict(self):
            return {"rows": {self.law: 1, "cells.beta@1": 2}}

    def canonical(value):
        return json.dumps(value, sort_keys=True)

    assert fp.fingerprint_value(Spec(old), canonical) == "f" * 64
    read = [fp.fingerprint_value(Spec(x), canonical, gives) for x in (old, new)]
    assert read[0] == read[1] != fp.fingerprint_value(Spec(old), canonical, lambda value: value)
    h = fp.Harness(gives)
    try:
        raise ValueError("x" * 390 + f" {old} is refused")  # Cut at 400, after the table.
    except ValueError as error:
        _, _, text, frame = h.exc_key(error)
    assert text == ("x" * 390 + f" {new} is refused")[:400] and len(frame) == 2  # No line number.


def test_a_record_read_through_a_table_is_compared_only_with_another(fp, tmp_path):
    key = "<tree>/configs/x.json"
    code, _ = compare(fp, tmp_path / "both", {key: world()}, {key: world()}, through=(True, True))
    assert code == 0
    with pytest.raises(SystemExit, match="one record's results are read through a table"):
        compare(fp, tmp_path / "one", {key: world()}, {key: world()}, through=(False, True))


def write(d, worlds, arrays, through=False, removed_list=None):
    d.mkdir(parents=True)
    named = dict(removed_list=removed_list) if removed_list else {}
    (d / "record.json").write_text(json.dumps(dict(worlds=worlds, outputs_through=through) | named))
    np.savez(d / "arrays.npz", **arrays)
    return d


def world(digest="d" * 64, module="cells.definitions.specs"):
    return dict(fingerprint_value=["digest", digest], parse=["spec", f"{module}.ModelSpec"],
                to_dict=["dict", "{}"], fingerprint=["object", "builtins.str"],
                get_model=["module", "cells.registry.models"],
                control_values=["controls", "Controls", ["a"]],
                control_shapes={"a": ["float64", [2]]})


def compare(fp, tmp_path, old_worlds, new_worlds, old_arrays=None, new_arrays=None,
            through=(False, False), declared=(), removed=None, named=None):
    """removed: a list of removals' text. The two records name it, or what named gives."""
    arrays = {"<tree>/configs/x.json::a": np.array([1.0, 2.0])}
    tmp_path.mkdir(exist_ok=True)
    listed = None if removed is None else tmp_path / "removed.txt"
    if listed:
        listed.write_text(removed)
    named = named or [fp.removals(listed)[1]] * 2
    old = write(tmp_path / "old", old_worlds, old_arrays or arrays, through[0], named[0])
    new = write(tmp_path / "new", new_worlds, new_arrays or arrays, through[1], named[1])
    r1 = tmp_path / "r1.json"
    r1.write_text(json.dumps(dict(worlds={"/somewhere/d188-r1/configs/x.json": {}})))
    out = tmp_path / "compare.json"
    code = fp.compare(old, new, MAP, out, r1_record=r1, declared=declared, removed=listed)
    return code, json.loads(out.read_text())


def test_the_old_side_is_read_through_the_map(fp, tmp_path):
    key = "<tree>/configs/x.json"
    code, report = compare(fp, tmp_path, {key: world(module="cells.core.specs")}, {key: world()})
    assert code == 0 and report["verdict"].startswith("all 1 fingerprints equal")
    assert report["r1_keys"]["r1_not_here"] == []


def test_a_digest_that_differs_is_caught_where_its_type_is_the_same(fp, tmp_path):
    key = "<tree>/configs/x.json"
    code, report = compare(fp, tmp_path, {key: world()}, {key: world(digest="e" * 64)})
    assert code == 1 and report["verdict"] == "DIFFERS"
    assert report["fingerprints"]["differ"] == 1
    assert world()["fingerprint"] == world(digest="e" * 64)["fingerprint"]  # The type alone.


def test_a_world_differs_only_where_it_is_declared_and_a_declared_one_must(fp, tmp_path):
    key, other = "<tree>/configs/x.json", "<tree>/configs/y.json"
    old, new = {key: world(), other: world()}, {key: world(digest="e" * 64), other: world()}
    arrays = {f"{key}::a": np.array([1.0]), f"{other}::a": np.array([2.0])}
    changed = arrays | {f"{key}::a": np.array([3.0])}
    for declared, ok in (((), False), ((key,), True), ((key, other), False)):
        folder = tmp_path / str(len(declared))
        code, report = compare(fp, folder, old, new, arrays, changed, declared=declared)
        assert (code == 0) == ok, report["declared"]
        assert report["declared"]["worlds"] == ([key] if declared else [])


GONE, ALSO, STAYS, NEVER = (f"<tree>/configs/{x}.json" for x in ("gone", "also", "stays", "never"))


@pytest.mark.parametrize(("plant", "says"), [
    (None, {}),
    ("unlisted", {"not_listed": [ALSO]}),
    ("held", {"still_held": [STAYS]}),
    ("never", {"never_held": [NEVER]}),
    ("added", {"added": [NEVER]}),
    ("digest", {}), ("row", {}), ("array", {}), ("array left", {}), ("declared", {}),
])  # fmt: skip
def test_a_key_goes_only_where_it_is_listed_and_a_listed_one_must(fp, tmp_path, plant, says):
    old, new, listed = {GONE: world(), STAYS: world()}, {STAYS: world()}, [GONE]
    arrays, left = {f"{k}::a": np.array([1.0]) for k in old}, {f"{STAYS}::a": np.array([1.0])}
    if plant == "unlisted":
        old[ALSO] = world()
    if plant in ("held", "never"):
        listed += says.get("still_held", []) + says.get("never_held", [])
    if plant == "added":
        new[NEVER] = world()
    if plant == "digest":
        new[STAYS] = world(digest="e" * 64)
    if plant == "row":
        new[STAYS]["get_model"] = ["module", "cells.registry.other"]
    if plant in ("array", "array left"):
        left[f"{STAYS if plant == 'array' else GONE}::a"] = np.array([1.0000000000000002])
    declared = [GONE] if plant == "declared" else []
    text = "".join(f"{key}\n" for key in listed)
    code, report = compare(fp, tmp_path, old, new, arrays, left, declared=declared, removed=text)
    removed = report["removed"]
    assert report["same_keys"] is False and removed["worlds"] == [GONE]
    assert removed["list_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    reasons = ("not_listed", "still_held", "never_held", "added")
    assert {k: removed[k] for k in reasons if removed[k]} == says
    assert code == (0 if plant is None else 1)
    if plant is None:
        assert removed["listed"] == removed["control_arrays"] == 1
        assert report["verdict"].startswith("all 1 fingerprints equal, and every other row")
        assert report["verdict"].endswith("; 1 worlds removed, as listed")
    else:
        assert report["verdict"] == "DIFFERS"


def test_an_empty_list_of_removals_is_no_list(fp, tmp_path):
    old = {GONE: world(), STAYS: world()}
    for name, new in (("same", old), ("gone", {STAYS: world()})):
        runs = [tmp_path / f"{name}-{x}" for x in ("none", "empty", "blank")]
        codes = [compare(fp, run, old, new, removed=text)[0]
                 for run, text in zip(runs, (None, "", "\n  \n"), strict=True)]
        assert codes == [0 if name == "same" else 1] * 3
        assert len({(run / "compare.json").read_bytes() for run in runs}) == 1
        assert "removed" not in json.loads((runs[0] / "compare.json").read_text())


@pytest.mark.parametrize("named", [(None, None), ("other", "other"), ("this", None)])
def test_the_records_and_the_comparison_name_one_list(fp, tmp_path, named):
    text, worlds = f"{GONE}\n", ({GONE: world(), STAYS: world()}, {STAYS: world()})
    digest = hashlib.sha256(text.encode()).hexdigest()
    named = [digest if x == "this" else x for x in named]
    with pytest.raises(SystemExit, match="must name one list of removals"):
        compare(fp, tmp_path / "list", *worlds, removed=text, named=named)
    if named[0] == named[1] == "other":  # A list in the records, none in the comparison.
        with pytest.raises(SystemExit, match="must name one list of removals"):
            compare(fp, tmp_path / "none", *worlds, named=named)


ENGINE = {  # A tree without an engine, in the layout before the moves, for the record step.
    "jax.py": "class config:\n    update = staticmethod(lambda *a: None)\n",
    "cells/__init__.py": "", "cells/core/__init__.py": "", "cells/models/__init__.py": "",
    "cells/core/schedule.py": "control_values = lambda spec, times: {}\n",
    "cells/core/specs.py": "import json\ncanonical_json = json.dumps\n"
                           "def parse_spec(d):\n    raise ValueError('no engine')\n",
    "cells/models/registry.py": "get_model = None\n",
}


def test_a_record_names_the_list_it_was_made_under(tmp_path):
    definition = dict(schema_version=1, model={}, experiment={}, execution={})
    for name, source in ENGINE.items():
        (tmp_path / "tree" / "src" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "tree" / "src" / name).write_text(source)
    (tmp_path / "tree" / "configs").mkdir()
    (tmp_path / "tree" / "configs" / "x.json").write_text(json.dumps(definition))
    records = []
    for name, text in (("none", None), ("empty", "\n"), ("list", f"{GONE}\n")):
        (tmp_path / name).write_text(text or "")
        option = [] if text is None else ["--removed", str(tmp_path / name)]
        subprocess.run(
            [sys.executable, "-B", "-I", str(SCRIPT), "record", str(tmp_path / "tree"),
             str(tmp_path / f"{name}-out"), "--layout", "premove", "--map", str(MAP), "--defs",
             str(tmp_path / "tree" / "configs"), *option], check=True, capture_output=True)
        records.append((tmp_path / f"{name}-out" / "record.json").read_bytes())
    none, empty, listed = records
    assert none == empty and b"removed_list" not in none
    listed = json.loads(listed)
    assert listed.pop("removed_list") == hashlib.sha256(f"{GONE}\n".encode()).hexdigest()
    assert listed == json.loads(none)


STUB = """#!/bin/bash
echo "$4 $*" >> "$STUB_LOG"
case "$4" in
  identity) echo '{}' ;;
  record) mkdir -p "$6" && echo '{}' > "$6/record.json" && echo recorded ;;
  compare) echo '{"verdict": "stub"}' > "$8" ;;
esac
"""


def test_the_landing_script_gives_the_list_and_keys_the_base_by_it(tmp_path):
    """The script's own steps: the interpreter is a stand-in for the tool's three commands."""
    (tmp_path / "py").write_text(STUB)
    (tmp_path / "py").chmod(0o755)
    (tmp_path / "list.txt").write_text(f"{GONE}\n")
    (tmp_path / "empty.txt").write_text("\n")
    for side in ("base", "head"):
        (tmp_path / side).mkdir()
        (tmp_path / side / "SNAPSHOT.json").write_text(json.dumps(dict(
            git_revision=side * 10, status="complete",
            patch_sha256=hashlib.sha256(b"").hexdigest())))

    def run(name, listed, *premove):
        """(exit code, the record and compare calls, the cached bases' key items)."""
        done = subprocess.run(
            ["bash", str(LANDING), str(tmp_path / name), str(tmp_path / "head"),
             str(tmp_path / "base"), *premove], capture_output=True, text=True, timeout=120,
            env=dict(os.environ, PY=str(tmp_path / "py"), MAP=str(MAP), G1=str(tmp_path / "g1"),
                     REPO=str(tmp_path), GATE_CACHE=str(tmp_path / "cache"), REMOVED=str(listed),
                     STUB_LOG=str(tmp_path / f"{name}.calls")))
        log = tmp_path / f"{name}.calls"
        calls = log.read_text().splitlines() if log.exists() else []
        entries = [json.loads(p.read_text())["key"]["items"]
                   for p in (tmp_path / "cache").glob("r1-*/CACHE.json")]
        return (done.returncode, [c for c in calls if c.startswith(("record ", "compare "))],
                sorted(entries, key=len))

    code, calls, bases = run("none", "")
    assert code == 0 and len(calls) == 3 and not any("--removed" in c for c in calls)
    assert len(bases) == 1 and not (tmp_path / "none" / "removed.txt").exists()
    code, empty, after = run("empty", tmp_path / "empty.txt")  # No list: the cached base again.
    assert code == 0 and after == bases
    assert [c.replace("/empty", "/none") for c in empty] == calls[1:]
    code, calls, after = run("listed", tmp_path / "list.txt")
    copy = tmp_path / "listed" / "removed.txt"
    assert code == 0 and copy.read_bytes() == (tmp_path / "list.txt").read_bytes()
    assert len(calls) == 3 and all(c.endswith(f"--removed {copy}") for c in calls)
    digest = hashlib.sha256(copy.read_bytes()).hexdigest()
    assert len(after) == 2 and set(after[1]) - set(after[0]) == {f"removed={digest}"}
    for name, listed, *premove in (("missing", "no-such-file"), ("premove", "list.txt", "/p")):
        code, calls, _ = run(name, tmp_path / listed, *premove)
        assert code == 2 and not calls and (tmp_path / name / "done").read_text() == "2\n"


@pytest.mark.parametrize("plant", ["array", "key", "row"])
def test_each_other_departure_differs(fp, tmp_path, plant):
    key = "<tree>/configs/x.json"
    old, new = {key: world()}, {key: world()}
    new_arrays = None
    if plant == "array":
        new_arrays = {"<tree>/configs/x.json::a": np.array([1.0, 2.0000000000000004])}
    if plant == "key":
        new = {key: world(), "<tree>/configs/y.json": world()}
    if plant == "row":
        new[key]["get_model"] = ["module", "cells.registry.other"]
    code, report = compare(fp, tmp_path, old, new, new_arrays=new_arrays)
    assert code == 1 and report["verdict"] == "DIFFERS"


def test_identity_against_a_revision(fp, tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text("A = 1\n")
    (repo / "configs").mkdir()
    (repo / "configs" / "c.json").write_text("{}\n")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@invalid"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "t"], check=True)
    rev = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True,
                         check=True).stdout.strip()
    assert fp.identity(repo, rev, str(repo)) == 0
    (repo / "src" / "a.py").write_text("A = 2\n")
    assert fp.identity(repo, rev, str(repo)) == 1
    assert '"differ": 1' in capsys.readouterr().out
