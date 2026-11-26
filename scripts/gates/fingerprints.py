"""R1's definition-fingerprint check through a move map (D188's moves; D220's gate tooling).

It is the worlds part of R1's behavioural equivalence harness, run on a tree before a move and on
the moved tree (layouts premove and moved), or on two trees in the moved layout at a later landing.
The two are compared through the move's map.

This supersedes /mnt/workspaces/Cells/d188-m2-move-20261118/tools/fingerprints.py, which is kept
byte for byte since recorded runs cite it. That tool loaded R1's frozen harness
(/mnt/workspaces/Cells/d188-r1-20261117/tools/equivalence.py) from its file. The harness parts it
used are copied here unchanged in behaviour (class Harness: DISPATCH_FILES, norm, exc_key, call
and definitions), so the check is self-contained. R1's record's keys are made tree-relative from the
keys themselves (at their definitions folder), not from a hardcoded tree path.

Adapted, for the moved layout only (each name read through the map; the harness's own names for the
tree before the move):
- the three dispatch imports of its `worlds` probe: cells.core.schedule.control_values,
  cells.core.specs.parse_spec and cells.models.registry.get_model;
- `value_key`'s import of canonical_json (cells.core.specs), which serializes every to_dict;
- DISPATCH_FILES, the dispatch modules' paths, by which an exception's innermost frame is labelled.

Added: the fingerprint's value. The harness keeps `value_key(spec.fingerprint)`, which for a str is
its type only (["object", "builtins.str"]). `fingerprint_value` here is the digest itself, or the
exception it raises, so two trees whose fingerprints differ in value differ here. Each tree reads
its own configs/, examples/ and validation/; the tree's path is written as <tree>, so both records'
keys name the same files.

  identity TREE REV REPO
      every file of TREE's src/, configs/, examples/ and validation/ against `git ls-tree REV`
      (git blob ids, computed here): the same paths and the same bytes, or exit 1.
  keys TREE
      the keys of TREE's definitions (configs/, examples/ and validation/) as record writes them,
      sorted, one on a line; no engine. What one tree's have beyond another's is a list of removals
      or additions: comm -23 or -13 of the two, under LC_ALL=C.
  record TREE OUT --layout premove|moved --map MAP --defs PATH... --g1 MERGED
         [--inputs TABLE] [--outputs TABLE] [--removed FILE] [--added FILE]
      OUT/record.json and OUT/arrays.npz (every control array). MAP's folder's parent holds the
      move tool (scripts/source_moves.py of the same tree).
      Across the ID rename (D345) the IDs are read through a table of renamed IDs
      (validation/id_table.py of these tools' checkout; a renamed_ids.py or a JSON {old: new}).
      --inputs: the definitions, before TREE parses them, so that one saved or frozen under an old
      spelling parses on a tree that refuses it. --outputs: what TREE gives, before anything is
      serialized, sorted, digested or cut, so that an old tree's results are a new tree's. With it
      the fingerprint's value is the digest of the read to_dict (a tree's own digest is of its own
      spellings), and an exception's frame keeps no line number, which the rename's rewrap moves.
      Both sides of a comparison name the same --outputs, or neither does.
      --removed, --added: the lists that compare takes; the record only names their digests
      (removed_list, added_list).
  compare OLD NEW MAP OUT_JSON [--r1-record RECORD] [--declared FILE] [--removed FILE]
          [--added FILE]
      the same keys on both sides; per world the fingerprint value, the harness's rows (parse,
      to_dict, fingerprint, get_model, control values and shapes) equal, with the old side's
      module names and paths read through the map; every control array bitwise; and the keys
      against R1's own record (R1's 274; --r1-record, by default R1's frozen one). A world may
      differ only where FILE declares it, one key on a line: an exact list, so a declared world
      that does not differ refuses the comparison too.
      --removed, --added: the keys that the new side removes and adds, one on a line, exact lists
      too. A key on one side only passes where its list names it. A listed removal that the new
      side still holds or the old side never held refuses the comparison, and so does a listed
      addition that the new side lacks or the old side held, or a key of either list that is also
      declared. What both sides hold is compared as without a list. same_keys still says that the
      keys differ, "removed" and "added" say which, and the verdict how many. Both records name the
      lists' digests too. An empty list is no list.
"""

import hashlib
import importlib
import importlib.util
import json
import linecache
import re
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np

R1_RECORD = Path("/mnt/workspaces/Cells/d188-r1-20261117/equivalence/old/record.json")
TOPS = ("/configs/", "/examples/", "/validation/")  # The definitions' folders of a tree.
OLD = ("cells.core.schedule", "cells.core.specs", "cells.models.registry")
READ = ("src", "configs", "examples", "validation")
PARTS = ("fingerprint_value", "parse", "to_dict", "fingerprint", "get_model", "control_values",
         "control_shapes")


class Harness:
    """R1's harness parts this check uses (d188-r1-20261117/tools/equivalence.py, copied unchanged
    in behaviour): record() sets ROOT, DISPATCH_FILES (for the moved layout) and value_key."""

    DISPATCH_FILES = (
        "cells/models/registry.py",
        "cells/core/specs.py",
        "cells/core/schedule.py",
        "cells/__main__.py",
        "cells/ensemble/families.py",
        "cells/ensemble/cli.py",
    )

    def __init__(self, gives=None):
        self.ROOT = None  # the tree's src folder, set by record
        self.DISPATCH_FILES = Harness.DISPATCH_FILES
        self.value_key = None
        self.gives = gives or (lambda value: value)  # What reads a result through --outputs.
        self.lines = gives is None

    def norm(self, text):
        text = str(text)
        if self.ROOT:
            text = text.replace(str(self.ROOT), "<src>")
        text = re.sub(r"0x[0-9a-f]{6,}", "0x?", text)
        return text

    def exc_key(self, error):
        tb = traceback.extract_tb(error.__traceback__)
        inner = tb[-1] if tb else None
        frame = None
        if inner is not None:
            rel = self.norm(inner.filename).removeprefix("<src>/")
            if rel in self.DISPATCH_FILES:
                line = linecache.getline(inner.filename, inner.lineno).strip()
                frame = ["<dispatch>", self.gives(line)]
            else:
                frame = [rel, inner.name, *([inner.lineno] if self.lines else [])]
        return ["raise", type(error).__name__, self.norm(self.gives(str(error)))[:400], frame]

    def call(self, f, *args):
        try:
            return self.value_key(f(*args))
        except Exception as error:  # noqa: BLE001  (an exception is a result)
            return self.exc_key(error)

    @staticmethod
    def definitions(paths, g1):
        out = {}
        for base in paths:
            base = Path(base)
            files = [base] if base.is_file() else sorted(base.rglob("*.json"))
            for p in files:
                try:
                    doc = json.loads(p.read_text())
                except Exception:  # noqa: BLE001
                    continue
                found = []

                def walk(v, where, depth=0, found=found):
                    if depth > 8:
                        return
                    if isinstance(v, dict):
                        if {"schema_version", "model", "experiment", "execution"} <= set(v):
                            found.append((where, v))
                            return
                        for k, x in v.items():
                            walk(x, f"{where}/{k}", depth + 1)
                    elif isinstance(v, list):
                        for k, x in enumerate(v[:5000]):
                            walk(x, f"{where}/{k}", depth + 1)

                walk(doc, "")
                for where, d in found:
                    out[f"{p}{where}"] = d
        if g1:
            for p in sorted(Path(g1).glob("*/*.json")):
                doc = json.loads(p.read_text())
                if isinstance(doc.get("definition"), dict):
                    out[f"g1:{p.parent.name}/{p.stem}"] = doc["definition"]
        return out


def tree_relative(key):
    """A record's world key with its tree's path as <tree>, cut at the earliest of the
    definitions' folders: the tree's own (a nested one, as in validation/betse/emulator/configs/,
    comes later)."""
    found = [at for at in (key.find(top) for top in TOPS) if at >= 0]
    return "<tree>" + key[min(found):] if found else key


def reader(table):
    """What reads JSON-like data through a table of renamed IDs; None without one."""
    if table is None:
        return None
    path = Path(__file__).resolve().parents[2] / "validation" / "id_table.py"
    spec = importlib.util.spec_from_file_location("id_table", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    renamed = module.read_table(table)
    return lambda value: module.translate(value, renamed)


def key_list(path):
    """The keys that a list names, one on a line, and its file's digest; (empty, None) of an empty
    list or none."""
    data = Path(path).read_bytes() if path else b""
    keys = {line for line in data.decode().splitlines() if line.strip()}
    return keys, hashlib.sha256(data).hexdigest() if keys else None


def fingerprint_value(spec, canonical_json, gives=None):
    """The tree's own fingerprint; read through --outputs, the digest of the read to_dict."""
    value = spec.fingerprint
    if gives is None:
        return value
    return hashlib.sha256(canonical_json(gives(spec.to_dict())).encode()).hexdigest()


def move_map(path):
    sys.path.insert(0, str(Path(path).resolve().parent.parent))
    import source_moves as sm

    return sm, sm.load_map(path)


def identity(tree, rev, repo):
    tree = Path(tree)
    listed = subprocess.run(["git", "-C", repo, "ls-tree", "-r", rev, "--", *READ],
                            capture_output=True, text=True, check=True).stdout.splitlines()
    want = {}
    for line in listed:
        meta, path = line.split("\t", 1)
        want[path] = meta.split()[2]
    have = {}
    for top in READ:
        for p in sorted((tree / top).rglob("*")):
            if p.is_file() or p.is_symlink():
                data = p.read_bytes() if not p.is_symlink() else str(p.readlink()).encode()
                blob = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
                have[str(p.relative_to(tree))] = blob
    differ = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))
    print(json.dumps(dict(tree=str(tree), rev=rev, files=len(want), differ=len(differ),
                          examples=differ[:5])))
    return 0 if not differ and want else 1


def keys(tree):
    tree = Path(tree).resolve()
    found = Harness.definitions([tree / top.strip("/") for top in TOPS], None)
    print(*sorted(key.replace(f"{tree}/", "<tree>/") for key in found), sep="\n")
    return 0


def record(tree, out, layout, map_path, defs, g1, inputs=None, outputs=None, removed=None,
           added=None):
    tree = Path(tree).resolve()
    named = {f"{kind}_list": key_list(path)[1] for kind, path in (("removed", removed),
                                                                 ("added", added))}
    sys.path.insert(0, str(tree / "src"))
    import jax

    jax.config.update("jax_enable_x64", True)
    given, gives = reader(inputs) or (lambda value: value), reader(outputs)
    h = Harness(gives)
    h.ROOT = tree / "src"
    sm, mp = move_map(map_path)
    names = OLD if layout == "premove" else tuple(mp.resolve(n) or n for n in OLD)
    schedule_name, specs_name, registry_name = names
    if layout == "moved":
        table = sm._old_files(mp)
        h.DISPATCH_FILES = tuple(
            "cells/" + table.get(p.removeprefix("cells/"), p.removeprefix("cells/"))
            for p in h.DISPATCH_FILES
        )
    canonical_json = importlib.import_module(specs_name).canonical_json

    def value_key(value):  # The harness's, with canonical_json from the tree's own module.
        if value is None:
            return ["None"]
        if type(value).__name__ == "module":
            return ["module", value.__name__]
        if isinstance(value, dict):
            try:
                return ["dict", canonical_json(h.gives(value))]
            except Exception as error:  # noqa: BLE001
                return ["dict-unserializable", h.gives(repr(error))[:200]]
        t = type(value)
        return ["object", f"{t.__module__}.{t.__qualname__}"]

    h.value_key = value_key
    control_values = importlib.import_module(schedule_name).control_values
    parse_spec = importlib.import_module(specs_name).parse_spec
    get_model = importlib.import_module(registry_name).get_model
    arrays, rows = {}, {}
    for name, d in h.definitions(defs, g1).items():  # The harness's worlds probe.
        row = {}
        try:
            spec = parse_spec(json.loads(json.dumps(given(d))))
        except Exception as error:  # noqa: BLE001
            row["parse"] = h.exc_key(error)
            rows[name] = row
            continue
        row["parse"] = [
            "spec", type(spec.model).__qualname__, h.norm(h.gives(repr(spec)))[:200000]
        ]  # fmt: skip
        row["to_dict"] = h.call(lambda s: s.to_dict(), spec)
        row["fingerprint"] = h.call(lambda s: s.fingerprint, spec)
        try:
            row["fingerprint_value"] = ["digest", fingerprint_value(spec, canonical_json, gives)]
        except Exception as error:  # noqa: BLE001
            row["fingerprint_value"] = h.exc_key(error)
        row["get_model"] = h.call(get_model, spec.model)
        try:
            e = spec.experiment
            times = sorted(
                {0.0, *(c.time for c in e.changes), *getattr(e, "observation_times", ()),
                 e.end_time}
            )
            values = control_values(spec, times)
            fields = getattr(values, "_fields", None)
            row["control_values"] = ["controls", type(values).__qualname__, list(fields or [])]
            items = values._asdict().items() if fields else [("", values)]
            for k, v in items:
                arrays[f"{name}::{k}"] = np.asarray(v)
            row["control_shapes"] = {
                k: [str(np.asarray(v).dtype), list(np.asarray(v).shape)] for k, v in items
            }
        except Exception as error:  # noqa: BLE001
            row["control_values"] = h.exc_key(error)
        rows[name] = row
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    result = dict(tree=str(tree), layout=layout, imports=list(names),
                  dispatch_files=list(h.DISPATCH_FILES), inputs_through=bool(inputs),
                  outputs_through=bool(outputs), **{k: v for k, v in named.items() if v},
                  worlds=rows)
    text = json.dumps(result, indent=1, default=str).replace(str(tree) + "/", "<tree>/")
    (out / "record.json").write_text(text + "\n")
    np.savez(out / "arrays.npz",
             **{k.replace(str(tree) + "/", "<tree>/"): v for k, v in arrays.items()})
    print(json.dumps(dict(tree=str(tree), layout=layout, imports=list(names), worlds=len(rows),
                          arrays=len(arrays))))
    return 0


def compare(old_dir, new_dir, map_path, out,
            r1_record=R1_RECORD, declared=(), removed=None, added=None):
    sm, mp = move_map(map_path)
    top = sm.map_top(mp)
    records = [json.loads((Path(d) / "record.json").read_text()) for d in (old_dir, new_dir)]
    if len({bool(r.get("outputs_through")) for r in records}) > 1:
        raise SystemExit("refused: one record's results are read through a table of renamed IDs, "
                         "and the other's are not")
    lists = dict(removed=key_list(removed), added=key_list(added))
    for kind, (_, digest) in lists.items():
        if {r.get(f"{kind}_list") for r in records} != {digest}:
            raise SystemExit("refused: the two records and the comparison must name one list of "
                             f"{kind} keys, or none")
    old, new = (r["worlds"] for r in records)
    going, coming = (keys for keys, _ in lists.values())
    gone, came = set(old) - set(new), set(new) - set(old)
    as_removed, as_added = gone & going, came & coming

    def through(v):  # Module names and dispatch paths of the tree before the move, moved.
        return json.loads(sm.rewrite_text(json.dumps(v), mp, top))

    differ, as_declared = {part: [] for part in PARTS}, set()
    for name in sorted((set(old) | set(new)) - as_removed - as_added):
        a, b = old.get(name, {}), new.get(name, {})
        for part in PARTS:
            x, y = a.get(part), b.get(part)
            if x != y and x is not None and through(x) == y:
                continue
            if x != y and name in declared:
                as_declared.add(name)
            elif x != y:
                differ[part].append([name, x, y])
    r1 = {tree_relative(k) for k in json.loads(Path(r1_record).read_text())["worlds"]}
    digests = [r["fingerprint_value"] for r in old.values() if "fingerprint_value" in r]
    report = dict(
        worlds_old=len(old), worlds_new=len(new), same_keys=sorted(old) == sorted(new),
        r1_keys=dict(r1=len(r1), here=len(old), r1_not_here=sorted(r1 - set(old)),
                     here_not_r1=sorted(set(old) - r1)),
        fingerprints=dict(
            worlds=len(old), with_a_digest=sum(1 for v in digests if v[0] == "digest"),
            raised=sum(1 for v in digests if v[0] != "digest"),
            refused_at_parse=sum(1 for r in old.values() if r["parse"][0] == "raise"),
            differ=len(differ["fingerprint_value"]), examples=differ["fingerprint_value"][:5]),
    )
    for part in PARTS[1:]:
        report[part] = dict(differ=len(differ[part]), examples=differ[part][:3])
    oa, na = np.load(Path(old_dir) / "arrays.npz"), np.load(Path(new_dir) / "arrays.npz")
    keys = sorted(set(oa.files) | set(na.files))
    bad = [k for k in keys if k not in oa.files or k not in na.files
           or oa[k].dtype != na[k].dtype or oa[k].shape != na[k].shape
           or oa[k].tobytes() != na[k].tobytes()]
    moved = dict(removed=[k for k in bad if k.split("::")[0] in as_removed and k not in na.files],
                 added=[k for k in bad if k.split("::")[0] in as_added and k not in oa.files])
    bad = sorted(set(bad) - {k for part in moved.values() for k in part})
    as_declared |= {k.split("::")[0] for k in bad} & set(declared)
    bad = [k for k in bad if k.split("::")[0] not in declared]
    report["control_arrays"] = dict(arrays=len(keys), differ=len(bad), examples=bad[:5])
    report["declared"] = dict(worlds=sorted(as_declared), equal=sorted(set(declared) - as_declared))
    keys_as_said = report["same_keys"]
    if any(digest for _, digest in lists.values()):
        wrong = dict(
            removed=dict(not_listed=gone - going, still_held=going & set(new),
                         never_held=going - set(old)),
            added=dict(not_listed=came - coming, missing=coming - set(new),
                       held_before=coming & set(old)))
        for kind, worlds in (("removed", as_removed), ("added", as_added)):
            report[kind] = dict(
                list_sha256=lists[kind][1], listed=len(lists[kind][0]), worlds=sorted(worlds),
                control_arrays=len(moved[kind]), **{k: sorted(v) for k, v in wrong[kind].items()})
        report["added"]["refused_at_parse"] = sorted(
            k for k in as_added if new[k]["parse"][0] == "raise")
        keys_as_said = not any(v for part in wrong.values() for v in part.values())
    ok = (keys_as_said and not any(differ.values()) and not bad
          and not report["declared"]["equal"])
    n = len(old) - len(as_declared) - len(as_removed)
    said = f", but for {len(as_declared)} worlds as declared" if as_declared else ""
    said += f"; {len(as_removed)} worlds removed, as listed" if as_removed else ""
    said += f"; {len(as_added)} worlds added, as listed" if as_added else ""
    report["verdict"] = (f"all {n} fingerprints equal, and every other row of the harness (through "
                         f"the map) and every control array{said}" if ok else "DIFFERS")
    Path(out).write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1)[:5000])
    return 0 if ok else 1


def main(argv):
    if len(argv) > 1 and argv[1] == "identity":
        return identity(*argv[2:5])
    if len(argv) > 1 and argv[1] == "keys":
        return keys(*argv[2:3])
    if len(argv) > 1 and argv[1] == "record":
        import argparse

        p = argparse.ArgumentParser()
        p.add_argument("tree")
        p.add_argument("out")
        p.add_argument("--layout", required=True, choices=["premove", "moved"])
        p.add_argument("--map", required=True)
        p.add_argument("--defs", nargs="*", default=[])
        p.add_argument("--g1")
        p.add_argument("--inputs")
        p.add_argument("--outputs")
        p.add_argument("--removed")
        p.add_argument("--added")
        a = p.parse_args(argv[2:])
        return record(a.tree, a.out, a.layout, a.map, a.defs, a.g1, a.inputs, a.outputs, a.removed,
                      a.added)
    if len(argv) > 1 and argv[1] == "compare":
        rest = argv[2:]
        r1, declared, lists = R1_RECORD, (), {}
        if "--r1-record" in rest:
            at = rest.index("--r1-record")
            r1, rest = rest[at + 1], rest[:at] + rest[at + 2:]
        if "--declared" in rest:
            at = rest.index("--declared")
            declared, rest = Path(rest[at + 1]).read_text().splitlines(), rest[:at] + rest[at + 2:]
        for kind in ("removed", "added"):
            if f"--{kind}" in rest:
                at = rest.index(f"--{kind}")
                lists[kind], rest = rest[at + 1], rest[:at] + rest[at + 2:]
        return compare(*rest[:4], r1_record=r1, declared=[x for x in declared if x.strip()],
                       **lists)
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
