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
- A key is on one side only where a list names it, of removals or of additions, and a listed one
  must be. The records, the comparison and the landing script's cache key name the lists' digests.
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


def write(d, worlds, arrays, through=False, named=()):
    d.mkdir(parents=True)
    named = {k: v for k, v in dict(named).items() if v}
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
            through=(False, False), declared=(), named=None, **lists):
    """lists: removed and added, each a list's text. The records name them, or what named gives."""
    arrays = {"<tree>/configs/x.json::a": np.array([1.0, 2.0])}
    tmp_path.mkdir(exist_ok=True)
    for kind, keys in lists.items():
        lists[kind] = None if keys is None else tmp_path / f"{kind}.txt"
        if keys is not None:
            lists[kind].write_text(keys)
    named = named or [{f"{kind}_list": fp.key_list(x)[1] for kind, x in lists.items()}] * 2
    old = write(tmp_path / "old", old_worlds, old_arrays or arrays, through[0], named[0])
    new = write(tmp_path / "new", new_worlds, new_arrays or arrays, through[1], named[1])
    r1 = tmp_path / "r1.json"
    r1.write_text(json.dumps(dict(worlds={"/somewhere/d188-r1/configs/x.json": {}})))
    out = tmp_path / "compare.json"
    code = fp.compare(old, new, MAP, out, r1_record=r1, declared=declared, **lists)
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


GONE, CAME, ALSO, STAYS, NEVER = (
    f"<tree>/configs/{x}.json" for x in ("gone", "came", "also", "stays", "never"))


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize(("plant", "removed_says", "added_says"), [
    (None, {}, {}),
    ("unlisted removal", {"not_listed": [ALSO]}, {}),
    ("listed removal held", {"still_held": [STAYS]}, {}),
    ("listed removal never held", {"never_held": [NEVER]}, {}),
    ("unlisted addition", {}, {"not_listed": [ALSO]}),
    ("listed addition missing", {}, {"missing": [NEVER]}),
    ("listed addition held before", {}, {"held_before": [STAYS]}),
    ("the addition on both lists", {"still_held": [CAME], "never_held": [CAME]}, {}),
    ("the removal on both lists", {}, {"missing": [GONE], "held_before": [GONE]}),
    ("the removal declared", {}, {}), ("the addition declared", {}, {}),
    ("digest", {}, {}), ("row", {}, {}), ("array", {}, {}),
    ("the removal's array on the new side", {}, {}),
    ("the addition's array on the old side", {}, {}),
])  # fmt: skip
def test_a_key_is_on_one_side_only_where_it_is_listed_and_a_listed_one_must(
    fp, tmp_path, plant, removed_says, added_says
):
    old, new = {GONE: world(), STAYS: world()}, {STAYS: world(), CAME: world()}
    removed, added, declared = [GONE], [CAME], []
    if plant == "unlisted removal":
        old[ALSO] = world()
    if plant == "unlisted addition":
        new[ALSO] = world()
    removed += removed_says.get("still_held") or removed_says.get("never_held", [])
    added += added_says.get("missing") or added_says.get("held_before", [])
    if plant == "digest":
        new[STAYS] = world(digest="e" * 64)
    if plant == "row":
        new[STAYS]["get_model"] = ["module", "cells.registry.other"]
    arrays = [{f"{k}::a": np.array([1.0]) for k in side} for side in (old, new)]
    changed = np.array([1.0000000000000002])
    if plant == "array":
        arrays[1][f"{STAYS}::a"] = changed
    if plant == "the removal's array on the new side":
        arrays[1][f"{GONE}::a"] = changed
    if plant == "the addition's array on the old side":
        arrays[0][f"{CAME}::a"] = changed
    if plant in ("the removal declared", "the addition declared"):
        declared = [GONE if "removal" in plant else CAME]
    texts = ["".join(f"{key}\n" for key in keys) for keys in (removed, added)]
    code, report = compare(fp, tmp_path, old, new, *arrays, declared=declared, removed=texts[0],
                           added=texts[1])
    reasons = dict(removed=("not_listed", "still_held", "never_held"),
                   added=("not_listed", "missing", "held_before"))
    assert report["same_keys"] is False
    for kind, key, says, keys in zip(("removed", "added"), (GONE, CAME), (removed_says, added_says),
                                     texts, strict=True):
        part = report[kind]
        assert part["list_sha256"] == digest(keys) and part["worlds"] == [key]
        assert {k: part[k] for k in reasons[kind] if part[k]} == says
    assert code == (0 if plant is None else 1)
    if plant is None:
        assert [report[k][x] for k in reasons for x in ("listed", "control_arrays")] == [1] * 4
        assert report["verdict"].startswith("all 1 fingerprints equal, and every other row")
        assert report["verdict"].endswith(
            "; 1 worlds removed, as listed; 1 worlds added, as listed")
    else:
        assert report["verdict"] == "DIFFERS"


def test_each_list_stands_alone_and_an_addition_refused_at_parse_is_named(fp, tmp_path):
    refused = world() | dict(parse=["raise", "ConfigError", "no", None])
    both = {STAYS: world()}
    code, report = compare(fp, tmp_path / "removed", both | {GONE: world()}, both,
                           removed=f"{GONE}\n")
    assert code == 0 and report["verdict"].endswith("control array; 1 worlds removed, as listed")
    code, report = compare(fp, tmp_path / "added", both, both | {CAME: refused}, added=f"{CAME}\n")
    assert code == 0 and report["verdict"].endswith("control array; 1 worlds added, as listed")
    assert report["added"]["refused_at_parse"] == [CAME] and report["removed"]["listed"] == 0
    code, report = compare(fp, tmp_path / "gone", both | {GONE: world()}, both | {CAME: world()},
                           added=f"{CAME}\n")
    assert code == 1 and report["removed"]["not_listed"] == [GONE]


@pytest.mark.parametrize("kind", ["removed", "added"])
def test_an_empty_list_is_no_list(fp, tmp_path, kind):
    both = {STAYS: world()}
    moved = both | {GONE: world()}
    for name, sides in (("same", (both, both)), ("moved", (moved, both)), ("came", (both, moved))):
        runs = [tmp_path / f"{name}-{x}" for x in ("none", "empty", "blank")]
        codes = [compare(fp, run, *sides, **{kind: text})[0]
                 for run, text in zip(runs, (None, "", "\n  \n"), strict=True)]
        assert codes == [0 if name == "same" else 1] * 3
        assert len({(run / "compare.json").read_bytes() for run in runs}) == 1
        assert not {"removed", "added"} & set(json.loads((runs[0] / "compare.json").read_text()))


@pytest.mark.parametrize("kind", ["removed", "added"])
@pytest.mark.parametrize("named", [(None, None), ("other",) * 2, ("this", None), (None, "this")])
def test_the_records_and_the_comparison_name_one_list(fp, tmp_path, kind, named):
    text, worlds = f"{GONE}\n", [{GONE: world(), STAYS: world()}, {STAYS: world()}]
    worlds = worlds if kind == "removed" else worlds[::-1]
    names = [{f"{kind}_list": digest(text) if x == "this" else x} for x in named]
    for given in ({kind: text}, {}):  # A list, and none, in the comparison.
        if given or any(named):
            with pytest.raises(SystemExit, match=f"must name one list of {kind} keys"):
                compare(fp, tmp_path / f"{len(given)}", *worlds, named=names, **given)


ENGINE = {  # A tree without an engine, in the layout before the moves, for the record step.
    "jax.py": "class config:\n    update = staticmethod(lambda *a: None)\n",
    "cells/__init__.py": "", "cells/core/__init__.py": "", "cells/models/__init__.py": "",
    "cells/core/schedule.py": "control_values = lambda spec, times: {}\n",
    "cells/core/specs.py": "import json\ncanonical_json = json.dumps\n"
                           "def parse_spec(d):\n    raise ValueError('no engine')\n",
    "cells/models/registry.py": "get_model = None\n",
}


def test_a_record_names_the_lists_it_was_made_under(fp, tmp_path, capsys):
    definition = dict(schema_version=1, model={}, experiment={}, execution={})
    for name, source in ENGINE.items():
        (tmp_path / "tree" / "src" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "tree" / "src" / name).write_text(source)
    docs = {"configs/x": definition, "examples/y": {"a b": [definition] * 2},
            "validation/z": {"c": definition}}
    for name, doc in docs.items():
        (tmp_path / "tree" / name).parent.mkdir()
        (tmp_path / "tree" / f"{name}.json").write_text(json.dumps(doc))
    records = []
    for name, text in (("none", None), ("empty", "\n"), ("list", f"{GONE}\n")):
        (tmp_path / name).write_text(text or "")
        (tmp_path / f"{name}-added").write_text((text or "") * 2)
        options = ["--removed", str(tmp_path / name), "--added", str(tmp_path / f"{name}-added")]
        subprocess.run(
            [sys.executable, "-B", "-I", str(SCRIPT), "record", str(tmp_path / "tree"),
             str(tmp_path / f"{name}-out"), "--layout", "premove", "--map", str(MAP), "--defs",
             *(str((tmp_path / "tree" / doc).parent) for doc in docs),
             *([] if text is None else options)],
            check=True, capture_output=True)
        records.append((tmp_path / f"{name}-out" / "record.json").read_bytes())
    none, empty, listed = records
    assert none == empty and not {"removed_list", "added_list"} & set(json.loads(none))
    listed = json.loads(listed)
    assert listed.pop("removed_list") == digest(f"{GONE}\n")
    assert listed.pop("added_list") == digest(f"{GONE}\n" * 2)
    assert listed == json.loads(none)
    fp.keys(tmp_path / "tree")  # The keys that a list names are the record's own.
    assert capsys.readouterr().out.splitlines() == sorted(listed["worlds"])
    assert sorted(listed["worlds"]) == [
        "<tree>/configs/x.json", "<tree>/examples/y.json/a b/0", "<tree>/examples/y.json/a b/1",
        "<tree>/validation/z.json/c"]


STUB = """#!/bin/bash
echo "$4 $*" >> "$STUB_LOG"
case "$4" in
  identity) echo '{}' ;;
  record) mkdir -p "$6" && echo '{}' > "$6/record.json" && echo recorded ;;
  compare) echo '{"verdict": "stub"}' > "$8" ;;
esac
"""


def test_the_landing_script_gives_the_lists_and_keys_the_base_by_them(tmp_path):
    """The script's own steps: the interpreter is a stand-in for the tool's three commands."""
    (tmp_path / "py").write_text(STUB)
    (tmp_path / "py").chmod(0o755)
    for name, text in (("list", f"{GONE}\n"), ("more", f"{CAME}\n"), ("empty", "\n")):
        (tmp_path / f"{name}.txt").write_text(text)
    for side in ("base", "head"):
        (tmp_path / side).mkdir()
        (tmp_path / side / "SNAPSHOT.json").write_text(json.dumps(dict(
            git_revision=side * 10, status="complete",
            patch_sha256=hashlib.sha256(b"").hexdigest())))

    def run(name, removed, added, *premove):
        """(exit code, the record and compare calls, the cached bases' key items)."""
        done = subprocess.run(
            ["bash", str(LANDING), str(tmp_path / name), str(tmp_path / "head"),
             str(tmp_path / "base"), *premove], capture_output=True, text=True, timeout=120,
            env=dict(os.environ, PY=str(tmp_path / "py"), MAP=str(MAP), G1=str(tmp_path / "g1"),
                     REPO=str(tmp_path), GATE_CACHE=str(tmp_path / "cache"),
                     REMOVED=removed and str(tmp_path / removed),
                     ADDED=added and str(tmp_path / added),
                     STUB_LOG=str(tmp_path / f"{name}.calls")))
        log = tmp_path / f"{name}.calls"
        calls = log.read_text().splitlines() if log.exists() else []
        entries = [json.loads(p.read_text())["key"]["items"]
                   for p in (tmp_path / "cache").glob("r1-*/CACHE.json")]
        return (done.returncode, [c for c in calls if c.startswith(("record ", "compare "))],
                sorted(entries, key=len))

    code, calls, bases = run("none", "", "")
    assert code == 0 and len(calls) == 3
    assert not any(word in c for c in calls for word in ("--removed", "--added"))
    assert len(bases) == 1 and not list((tmp_path / "none").glob("*.txt"))
    code, empty, after = run("empty", "empty.txt", "empty.txt")  # No list: the cached base again.
    assert code == 0 and after == bases
    assert [c.replace("/empty", "/none") for c in empty] == calls[1:]
    code, calls, after = run("listed", "list.txt", "more.txt")
    copies = [tmp_path / "listed" / f"{kind}.txt" for kind in ("removed", "added")]
    assert [copy.read_text() for copy in copies] == [f"{GONE}\n", f"{CAME}\n"]
    said = "--removed {} --added {}".format(*copies)
    assert code == 0 and len(calls) == 3 and all(c.endswith(said) for c in calls)
    assert len(after) == 2 and set(after[1]) - set(after[0]) == {
        f"removed={digest(f'{GONE}\n')}", f"added={digest(f'{CAME}\n')}"}
    for name, *given in (("missing", "no-such-file", ""), ("missing-too", "", "no-such-file"),
                         ("premove", "list.txt", "", "/p"), ("premove-too", "", "more.txt", "/p")):
        code, calls, _ = run(name, *given)
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
