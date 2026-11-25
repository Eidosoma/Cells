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
- identity checks a tree's files against a Git revision, blob by blob.
No tree is recorded here: the record step's rehearsal on move 2's landing-gate inputs is recorded
in the hand-back.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "gates" / "fingerprints.py"
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


def write(d, worlds, arrays, through=False):
    d.mkdir(parents=True)
    (d / "record.json").write_text(json.dumps(dict(worlds=worlds, outputs_through=through)))
    np.savez(d / "arrays.npz", **arrays)
    return d


def world(digest="d" * 64, module="cells.definitions.specs"):
    return dict(fingerprint_value=["digest", digest], parse=["spec", f"{module}.ModelSpec"],
                to_dict=["dict", "{}"], fingerprint=["object", "builtins.str"],
                get_model=["module", "cells.registry.models"],
                control_values=["controls", "Controls", ["a"]],
                control_shapes={"a": ["float64", [2]]})


def compare(fp, tmp_path, old_worlds, new_worlds, old_arrays=None, new_arrays=None,
            through=(False, False), declared=()):
    arrays = {"<tree>/configs/x.json::a": np.array([1.0, 2.0])}
    old = write(tmp_path / "old", old_worlds, old_arrays or arrays, through[0])
    new = write(tmp_path / "new", new_worlds, new_arrays or arrays, through[1])
    r1 = tmp_path / "r1.json"
    r1.write_text(json.dumps(dict(worlds={"/somewhere/d188-r1/configs/x.json": {}})))
    out = tmp_path / "compare.json"
    code = fp.compare(old, new, MAP, out, r1_record=r1, declared=declared)
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
