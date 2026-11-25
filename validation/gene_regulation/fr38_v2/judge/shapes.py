"""The engine tables' registered shapes (amendments 5 and 6), and the pass that reads them.

- **Where the shapes come from.** `table_shapes.json` is the format sample's README (registered by
  hash, amendment 5, §1) read by `schema_from_readme`, with amendment 5's own pins (`_pins`). No
  table of the sample enters it: the sample check (§5) regenerates it from the README and reads the
  six tables with it.
- **The structure pass** (`structure`) reads one table: its top-level keys, its rungs, every entry
  by kind, and every definition, as keys, nesting and types to the leaf, matched by name. It takes
  no number. The judgement and the sample check run this same pass; the value pass (`records`) is
  the judgement's alone.
- **What a finding does** (amendment 5, §2 and §4; amendment 6, §2). `missing`, `type`, `duplicate`
  and `forbidden` findings are faults: at a top-level key they refuse the table, at an entry's
  pinned key the entry, a recorded-only leaf's included. In a definition they are recorded, since
  C0's echo (`definitions`) decides there; the sample check counts them too. `unexpected` keys are
  recorded, never a fault (amendment 2, Q6).
- **The excess** (amendment 6, §1). An `absent excess` is a fault only where the entry's blank is
  there and not refused, which a single entry does not show: the judge's C0 and the sample check
  each decide it from the blank.
- **Types.** "float" is any finite JSON number and "integer" only a JSON integer; a boolean is
  neither. A blank may lack its `route2` and `survival`; where present they have their types.
- **A non-finite number anywhere in an entry refuses it** (CRITERIA.md C0; amendment 6, §2), but for
  a survival ratio ("number"), whose NaN or Infinity token C1 fails at an idle fate and the value
  pass refuses at an active one (amendment 1, item 3; amendment 4, item 7).
"""

import dataclasses
import hashlib
import json
import math
import os
import re

SHAPES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "table_shapes.json")
SHAPES_KIND = "cells.fr38_v2.table_shapes@1"
TABLE_KIND = "cells.fr38_v2.engine_table@1"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
FAULTS = ("missing", "type", "duplicate", "forbidden")
ABSENT_EXCESS = "absent excess"

GENE_UNIT = "templated_polymerisation@1"
LABEL_OWNER = "neutral_arrival_labels@1"
STORE = "local_species_reactions@1"
WATER = "ideal_osmosis_linear_compliance_water@1"
TURNOVER = "scheduled_species_turnover@1"
COUPLING = "species_regulated_availability@2"

RUNG_KEYS = {"primary": ("2.0", "1.0", "0.5"), "retry": ("1.0", "0.5", "0.25")}
PROFILE_SECTION = {"A": "hold", "B": "B", "C": "C", "D": "D"}

# amendment 5, item 3: each plant's reference run; its honest engine run has the same name, except
# for P8 blank, whose honest run is `blank returned`
JUDGED_AS = {
    "P2": "p=1 returned", "P5": "p_sched returned", "P7": "p_sched held",
    "P3a": "p_sched returned", "P3b": "p_sched returned", "P4 AN": "p_sched returned",
    "P4 B": "p=0.55 returned", "P8": "p_sched returned", "P8 blank": "blank",
    "P9": "p_sched returned",
}  # fmt: skip
PLANT_NAMES = {"AF": ("P2", "P5", "P7"), "AN": ("P3a", "P3b", "P4 AN"), "B": ("P4 B",),
               "C": ("P8", "P8 blank"), "D": ("P9",)}  # fmt: skip
PLANT_OF = {"P4 AN": "P4", "P4 B": "P4", "P8 blank": "P8"}
JUDGE_PLANTS = ("P1", "P1′", "P1″", "P6", "P1'", "P1''")  # formed by the judge (amendment 4, §5)

# The kinds of entry (the README's lists); B's twin and P8 blank are read from them: a B run has no
# blank, and a planted blank is a plant without the excess.
ENTRY_KINDS = ("labelled", "blank", "twin", "B run", "B twin", "restart", "plant", "P8",
               "P8 blank", "refused")  # fmt: skip


def load_shapes(path=SHAPES_PATH):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("kind") != SHAPES_KIND:
        raise ValueError(f"{path}: not the judge's table shapes")
    return doc


def sample_hashes(shapes=None):
    """The nine SHA-256 that amendment 5, §1 registers. They identify registered data files, not
    source files, so AGENTS.md's rule against source-file hash literals does not apply."""
    return dict((shapes or load_shapes())["sample_sha256"])


# ------------------------------------------------------------------ the README, as a schema

_BULLET = re.compile(r"^( *)- (.*)$")
_KEY = re.compile(r"^`([^`]+)`: (.*)$")
_NAMED = re.compile(r"^the entry whose `([^`]+)` is `([^`]+)`:$")
_SOME = re.compile(r"^\(in some entries only: (.*)\)$")
_LEAVES = ("string", "float", "integer", "boolean", "null")


def _bullets(lines):
    out = []
    for line in lines:
        m = _BULLET.match(line)
        if m:
            out.append((len(m.group(1)) // 2, m.group(2)))
    return out


def _node(desc, kids):
    """A README bullet's description and its children, as a schema node."""
    if desc in _LEAVES:
        return desc
    if desc.startswith("list, empty"):
        return {"t": "list", "of": "any"}
    m = re.match(r"^list of \d+ (float|string|integer|boolean)s?$", desc)
    if m:
        return {"t": "list", "of": m.group(1)}
    if re.match(r"^list of \d+ objects?$", desc):
        names, by = {}, None
        for text, sub in kids:
            n = _NAMED.match(text)
            if n:
                by = n.group(1)
                names[n.group(2)] = _object(sub)
        if names:
            return {"t": "named", "by": by, "names": names}
        return {"t": "list", "of": _object(kids)}
    if desc.startswith("object, one list of floats per series"):
        return {"t": "map", "of": {"t": "list", "of": "float"}}
    if desc.startswith("object, the engine's declaration"):
        return {"t": "definition"}
    if desc.startswith("object"):
        return _object(kids)
    raise ValueError(f"README: unread description {desc!r}")


def _object(kids):
    keys, optional = {}, []
    for text, sub in kids:
        some = _SOME.match(text)
        if some:
            optional += re.findall(r"`([^`]+)`", some.group(1))
            continue
        m = _KEY.match(text)
        if not m:
            raise ValueError(f"README: unread bullet {text!r}")
        keys[m.group(1)] = _node(m.group(2), sub)
    out = {"t": "object", "keys": keys}
    if optional:
        out["optional"] = sorted(optional)
    return out


def _tree(bullets):
    """Bullets with their indents as nested (text, children)."""
    root = []
    stack = [(-1, root)]
    for level, text in bullets:
        while stack[-1][0] >= level:
            stack.pop()
        node = (text, [])
        stack[-1][1].append(node)
        stack.append((level, node[1]))
    return root


def _section(lines, start, stop):
    i = next(k for k, x in enumerate(lines) if x.startswith(start))
    j = next((k for k in range(i + 1, len(lines)) if stop(lines[k])), len(lines))
    return lines[i + 1 : j]


def schema_from_readme(text):
    """The format sample's README as a schema: the run entry, the keys each kind carries, the
    checkpoint, P9's patch, the series names by family and the four definitions."""
    lines = text.splitlines()
    blankline = re.compile(r"^\s*$")

    def till_blank(x):
        return bool(blankline.match(x))

    entry = _object(_tree(_bullets(_section(lines, "**A run entry**", till_blank))))
    kinds = {}
    for line in _section(lines, "Which keys each kind of entry carries:", till_blank):
        if not line.startswith("- "):
            continue
        keys = line.rpartition("): ")[2] if "): " in line else line.partition(": ")[2]
        names = sorted(re.findall(r"`([^`]+)`", keys))
        for tag, kind in (
            ("a labelled run", "labelled"),
            ("a blank (", "blank"),
            ("a twin", "twin"),
            ("B's run", "B run"),
            ("the restart", "restart"),
            ("a plant (", "plant"),
            ("P8, with its planted blank", "P8"),
        ):
            if line[2:].startswith(tag):
                kinds[kind] = names
    refused = {
        m
        for m in re.findall(
            r"`([a-z]+)`", " ".join(_section(lines, "**The refused entry**", till_blank))
        )
    }
    kinds["refused"] = sorted(refused & {"refused", "refusal", "definition", "record"})
    kinds["B twin"] = [k for k in kinds["twin"] if k != "excess_over_blank"]
    kinds["P8 blank"] = [k for k in kinds["P8"] if k != "excess_over_blank"]
    readouts = {}
    for m in re.finditer(r"^- (AF|AN|B|C|D) \((\d+)\): (.*)$", text, re.M):
        names = sorted(re.findall(r"`([^`]+)`", m.group(3)))
        if len(names) != int(m.group(2)):
            raise ValueError(f"README: {m.group(1)} lists {len(names)} series")
        readouts[m.group(1)] = names

    def heading(x):
        return x.startswith("### ") or x.startswith("## ")

    definition = {}
    for tag, key in (("### the hold worlds", "hold"), ("### family C", "C"),
                     ("### family D", "D"), ("### arm B", "B")):  # fmt: skip
        definition[key] = _object(_tree(_bullets(_section(lines, tag, heading))))
    out = {
        "entry": entry,
        "kinds": kinds,
        "checkpoint": _object(
            _tree(_bullets(_section(lines, "`restart.checkpoint`:", till_blank)))
        ),  # fmt: skip
        "host_patch": _object(
            _tree(_bullets(_section(lines, "`plants.P9.host_patch` (D):", till_blank)))
        ),  # fmt: skip
        "readouts": readouts,
        "definition": definition,
    }
    return _pins(out)


def _pins(s):
    """The pins of amendments 1, 4 and 5 on the README's lists: the entries amendment 5 names by id
    where the README names a law, `durable_fraction` a number or "scheduled" with its control (item
    6), a survival ratio null at a zero count or a token that C1 and C0 score, and the classes of
    `smallest_class_increment`, which the README lists for one family."""
    s["entry"]["keys"]["survival"]["of"]["keys"]["ratio"] = "number|null"
    s["entry"]["keys"]["checks"]["keys"]["smallest_class_increment"] = {"t": "map", "of": "float"}
    by_id = {"membranes": "patch_0", "reactions": "store_M", "couplings": "c_regulator"}

    def walk(node):
        if not isinstance(node, dict):
            return
        if node["t"] == "object":
            for k, v in node["keys"].items():
                if k in by_id and isinstance(v, dict) and v.get("by") == "law":
                    (only,) = v["names"].values()
                    node["keys"][k] = {"t": "named", "by": "id", "names": {by_id[k]: only}}
                if k == "durable_fraction":
                    node["keys"][k] = "float|string"
                if k == "polymerisation_controls":
                    v["optional"] = ["tx_release"]
                walk(node["keys"][k])
        elif node["t"] == "named":
            for v in node["names"].values():
                walk(v)
        elif node["t"] in ("list", "map"):
            walk(node["of"])

    for d in s["definition"].values():
        walk(d)
        d["keys"]["model"]["keys"]["operators"]["strict"] = True
    return s


# ------------------------------------------------------------------ the walk


def leaf_ok(t, v):
    kind = type(v)
    for x in t.split("|"):
        if x == "float" and kind in (int, float) and math.isfinite(v):
            return True
        if x == "number" and kind in (int, float):
            return True
        if x == "integer" and kind is int:
            return True
        if x == "string" and kind is str:
            return True
        if x == "boolean" and kind is bool:
            return True
        if x == "null" and v is None:
            return True
        if x == "any":
            return True
    return False


def _found(v):
    return {type(None): "null", bool: "boolean", int: "integer", float: "float", str: "string",
            list: "list", dict: "object"}.get(type(v), type(v).__name__)  # fmt: skip


def walk(node, v, path, out):
    """Findings of one value against one node, as (kind, path, detail)."""
    if isinstance(node, str):
        if not leaf_ok(node, v):
            what = "a non-finite number" if type(v) is float and not math.isfinite(v) else _found(v)
            out.append(("type", path, f"{node} expected, {what} found"))
        return
    t = node["t"]
    if t == "definition":
        if not isinstance(v, dict):
            out.append(("type", path, f"object expected, {_found(v)} found"))
        return
    if t in ("object", "map"):
        if not isinstance(v, dict):
            out.append(("type", path, f"object expected, {_found(v)} found"))
            return
        if t == "map":
            for k, x in v.items():
                walk(node["of"], x, f"{path}.{k}", out)
            return
        optional = node.get("optional", ())
        for k, sub in node["keys"].items():
            if k in v:
                walk(sub, v[k], f"{path}.{k}", out)
            elif k not in optional:
                out.append(("missing", f"{path}.{k}", "a listed key"))
        for k in v:
            if k not in node["keys"]:
                out.append(("unexpected", f"{path}.{k}", "a key the README does not list"))
        return
    if not isinstance(v, list):
        out.append(("type", path, f"list expected, {_found(v)} found"))
        return
    if t == "list":
        of = node["of"]
        if isinstance(of, str):
            if of == "any":
                return
            if of == "float" and all(type(x) in (int, float) for x in v):
                bad = [i for i, x in enumerate(v) if not math.isfinite(x)]
            else:
                bad = [i for i, x in enumerate(v) if not leaf_ok(of, x)]
            if bad:
                i = bad[0]
                out.append(("type", f"{path}[{i}]", f"{of} expected, {_found(v[i])} found "
                            f"({len(bad)} entries)"))  # fmt: skip
            return
        for i, x in enumerate(v):
            walk(of, x, f"{path}[{i}]", out)
        return
    # a list of named entries, matched by name, never by position
    by, names, optional = node["by"], node["names"], node.get("optional", ())
    seen = {}
    for i, x in enumerate(v):
        name = x.get(by) if isinstance(x, dict) else None
        if not isinstance(name, str):
            out.append(("type", f"{path}[{i}]", f"an entry with a string {by!r} expected"))
            continue
        seen.setdefault(name, []).append(x)
    for name, entries in seen.items():
        where = f"{path}[{by}={name}]"
        if len(entries) > 1:
            out.append(("duplicate", where, f"{len(entries)} entries of that name"))
        if name not in names:
            kind = "forbidden" if node.get("strict") else "unexpected"
            out.append((kind, where, "an entry that is not listed"))
            continue
        for x in entries:
            walk(names[name], x, where, out)
    for name in names:
        if name not in seen and name not in optional:
            out.append(("missing", f"{path}[{by}={name}]", "a listed entry"))


# ------------------------------------------------------------------ the structure pass


@dataclasses.dataclass
class Entry:
    """One entry of a table, as the structure pass reads it."""

    where: str
    name: str
    kind: str  # one of ENTRY_KINDS; a refused entry's is "refused"
    role: str  # honest, blank, twin, restart or plant
    run: str
    machine: object
    plant: object
    dt: float
    obj: object
    findings: list = dataclasses.field(default_factory=list)  # of the entry's own keys
    definition_findings: list = dataclasses.field(default_factory=list)

    @property
    def faults(self):
        return [f for f in self.findings if f[0] in FAULTS]

    @property
    def excess_absent(self):
        return any(f[0] == ABSENT_EXCESS for f in self.findings)


@dataclasses.dataclass
class Structure:
    findings: list  # of the top-level keys and the rungs
    entries: list
    notes: list  # what is recorded and left out
    present: int  # the entries in the file, counted raw
    null_plants: list
    restart: str  # "absent", "null", "present" or "unregistered"

    @property
    def faults(self):
        return [f for f in self.findings if f[0] in FAULTS]


def classify(name, honest):
    """(role, reference run, machine) of a registered run name, or None."""
    if name in honest:
        return "honest", name, None
    if name in ("blank returned", "blank held"):
        return "blank", "blank", name.split()[1]
    if name.endswith(" unlabelled") and name[: -len(" unlabelled")] in honest:
        return "twin", name[: -len(" unlabelled")], None
    return None


def entry_kind(role, profile, name):
    if role == "honest":
        return "B run" if profile == "B" else "labelled"
    if role == "twin":
        return "B twin" if profile == "B" else "twin"
    if role == "plant":
        return name if name in ("P8", "P8 blank") else "plant"
    return role


def _entry_node(kind, name, shapes):
    """The schema of one kind of entry: the README's keys for that kind, with `blank` a string or
    null by kind (item 2), and `host_patch` P9's alone (item 7)."""
    base = shapes["entry"]["keys"]
    keys = {}
    for k in shapes["kinds"][kind]:
        if k == "blank":
            keys[k] = "string" if kind in ("labelled", "twin", "restart", "P8") else "null"
        elif k == "checkpoint":
            keys[k] = shapes["checkpoint"]
        elif k == "host_patch":
            keys[k] = shapes["host_patch"] if name == "P9" else "null"
        elif k == "judged_as":
            keys[k] = "string"
        else:
            keys[k] = base[k]
    node = {"t": "object", "keys": keys}
    if kind in ("blank", "P8 blank"):
        node["optional"] = ["route2", "survival"]  # item 4: their absence is no fault
    return node


_REFUSED = {
    "t": "object",
    "keys": {
        "refused": "boolean",
        "refusal": "string",
        "definition": {"t": "definition"},
        "record": "string",
    },
}


def _hex64(x):
    return isinstance(x, str) and re.fullmatch(r"[0-9a-fA-F]{64}", x) is not None


def nonfinite(x, path):
    """The paths of every number in a JSON value that is not finite (the first of each list)."""
    if isinstance(x, dict):
        return [p for k, v in x.items() for p in nonfinite(v, f"{path}.{k}")]
    if isinstance(x, list):
        if all(type(v) in (int, float) for v in x):
            return [f"{path}[{i}]" for i, v in enumerate(x) if not math.isfinite(v)][:1]
        return [p for i, v in enumerate(x) for p in nonfinite(v, f"{path}[{i}]")]
    return [path] if type(x) is float and not math.isfinite(x) else []


def _without_ratios(e):
    """The entry but for its survival ratios, which the value pass and C1 decide; a blank's, never
    judged, stay."""
    rows = e.obj.get("survival")
    if e.kind in ("blank", "P8 blank") or not isinstance(rows, list):
        return e.obj
    cut = [{k: v for k, v in r.items() if k != "ratio"} if isinstance(r, dict) else r for r in rows]
    return dict(e.obj, survival=cut)


def entry_findings(e, profile, shapes):
    """One entry's own keys (and its definition's shape), against its kind."""
    obj, out = e.obj, e.findings
    if not isinstance(obj, dict):
        out.append(("type", e.where, f"object expected, {_found(obj)} found"))
        return
    if "refused" in obj:  # item 5: exactly refused (true), refusal, definition and record
        e.kind = "refused"
        walk(_REFUSED, obj, e.where, out)
        if type(obj["refused"]) is bool and obj["refused"] is not True:
            out.append(("type", f"{e.where}.refused", "true expected, false found"))
    else:
        walk(_entry_node(e.kind, e.name, shapes), obj, e.where, out)
        excess = ("missing", f"{e.where}.excess_over_blank")
        out[:] = [(ABSENT_EXCESS if f[:2] == excess else f[0], *f[1:]) for f in out]
        sha = obj.get("record_sha256")
        if isinstance(sha, str) and not _hex64(sha):
            out.append(("type", f"{e.where}.record_sha256", "64 hexadecimal digits expected"))
    named = {f[1] for f in out if f[0] in FAULTS}
    out += [("type", p, "a non-finite number found")
            for p in nonfinite(_without_ratios(e), e.where) if p not in named]  # fmt: skip
    if isinstance(obj.get("definition"), dict):
        definition_findings(obj["definition"], profile, e.role != "twin",
                            f"{e.where}.definition", shapes, e.definition_findings)  # fmt: skip


def definition_findings(defn, profile, labelled, path, shapes, out):
    """A declaration's shape against the README's list for its family: a twin's has no label owner
    and no `label_arrivals` (item 6); `tx_release` has a control where p is scheduled, and only
    there; `label_arrivals` holds its three entries by name."""
    node = shapes["definition"][PROFILE_SECTION[profile]]
    exp = node["keys"]["experiment"]
    model = node["keys"]["model"]
    ops = model["keys"]["operators"]
    if not labelled:
        exp = {"t": "object", "keys": {k: v for k, v in exp["keys"].items()
                                       if k != "label_arrivals"}}  # fmt: skip
        ops = dict(ops, names={k: v for k, v in ops["names"].items() if k != LABEL_OWNER})
        model = {"t": "object", "keys": dict(model["keys"], operators=ops)}
        node = {"t": "object", "keys": dict(node["keys"], experiment=exp, model=model)}
    walk(node, defn, path, out)
    e = defn.get("experiment")
    if not isinstance(e, dict):
        return
    if not labelled and "label_arrivals" in e:
        out[:] = [f for f in out if f[1] != f"{path}.experiment.label_arrivals"]
        out.append(("forbidden", f"{path}.experiment.label_arrivals", "a twin is unlabelled"))
    df = _durable_fraction(defn)
    controls = e.get("polymerisation_controls")
    has = isinstance(controls, list) and any(
        isinstance(c, dict) and c.get("route_id") == "tx_release" for c in controls
    )
    where = f"{path}.experiment.polymerisation_controls[route_id=tx_release]"
    if isinstance(df, str) and not has:
        out.append(("missing", where, "p is scheduled, so its control is listed"))
    if not isinstance(df, str) and df is not None and has:
        out.append(("unexpected", where, "p is a constant"))
    arr = e.get("label_arrivals")
    if labelled and isinstance(arr, list):
        got = [(a.get("species"), a.get("source")) for a in arr if isinstance(a, dict)]
        for sp, src in (("R", None), ("R_s", None), ("R", "tx")):
            n = got.count((sp, src))
            tag = f"{path}.experiment.label_arrivals[species={sp}" + (
                f", source={src}]" if src else "]"
            )
            if n == 0:
                out.append(("missing", tag, "a listed entry"))
            elif n > 1:
                out.append(("duplicate", tag, f"{n} entries of that name"))


def _durable_fraction(defn):
    try:
        ops = defn["model"]["operators"]
        gene = next(o for o in ops if o.get("law") == GENE_UNIT)
        tx = next(c for c in gene["chains"] if c.get("id") == "tx")
        return tx["release"]["durable_fraction"]
    except (KeyError, TypeError, StopIteration, AttributeError):
        return None


_TOP = {
    "family": "string",
    "kind": "string",
    "missing": {"t": "list", "of": "any"},
    "plants": {"t": "map", "of": "any"},
    "rungs": {"t": "map", "of": "any"},
    "samples_s": {"t": "list", "of": "float"},
    "window_s": {"t": "list", "of": "float"},
}


def structure(doc, family, attempt, profile, role, honest, shapes, *, restart_run=None):
    """The structure pass of one table. `role` is the registered family whose plants and restart
    the table carries (None: an invented family, which may carry any registered plant);
    `restart_run` is the run its restart resumes, where one is registered."""
    out = Structure([], [], [], 0, [], "absent")
    if not isinstance(doc, dict):
        out.findings.append(("type", "table", f"object expected, {_found(doc)} found"))
        return out
    top = out.findings
    for k, node in _TOP.items():
        if k not in doc:
            top.append(("missing", k, "a pinned top-level key"))
        else:
            walk(node, doc[k], k, top)
    if isinstance(doc.get("kind"), str) and doc["kind"] != TABLE_KIND:
        top.append(("type", "kind", f"{TABLE_KIND!r} expected, {doc['kind']!r} found"))
    if isinstance(doc.get("family"), str) and doc["family"] != family:
        top.append(("type", "family", f"{family!r} expected, {doc['family']!r} found"))
    for k in doc:
        if k not in _TOP and k != "restart":
            top.append(("unexpected", k, "a top-level key that is not listed"))
    rungs = doc.get("rungs") if isinstance(doc.get("rungs"), dict) else {}
    for key, rung in rungs.items():
        if key not in RUNG_KEYS[attempt]:
            top.append(("unexpected", f"rungs.{key}", f"not a rung of the {attempt} attempt"))
            out.notes.append(f"rungs.{key}: not a rung of the {attempt} attempt, ignored")
            if isinstance(rung, dict) and isinstance(rung.get("runs"), dict):
                out.present += len(rung["runs"])
            continue
        before = len(top)
        walk({"t": "object", "keys": {"dt_s": "float", "runs": {"t": "map", "of": "any"}}}, rung,
             f"rungs.{key}", top)  # fmt: skip
        if any(f[0] in FAULTS for f in top[before:]) or not isinstance(rung, dict):
            continue
        for name, obj in rung["runs"].items():
            out.present += 1
            c = classify(name, honest)
            where = f"rungs.{key}.runs.{name}"
            if c is None:
                out.notes.append(f"{where}: not a registered run name, ignored")
                continue
            r, run, machine = c
            e = Entry(where, name, entry_kind(r, profile, name), r, run, machine, None,
                      float(key), obj)  # fmt: skip
            entry_findings(e, profile, shapes)
            out.entries.append(e)
    _plants(doc.get("plants"), out, attempt, profile, role, honest, shapes)
    _restart(doc, out, attempt, profile, restart_run, shapes)
    return out


def excess_faults(st):
    """Amendment 6, §1, by structure alone (the sample check's): an absent `excess_over_blank` is a
    fault where the blank its entry names is in the table and not refused. The judgement decides it
    from the registered blank and C0 (`judge._decide_excess`)."""
    at, out = {e.where: e for e in st.entries}, []
    for e in st.entries:
        if not e.excess_absent:
            continue
        rung = e.where[: e.where.index(".runs.") + 6] if ".runs." in e.where else "plants."
        rung = "rungs.0.5.runs." if e.role == "restart" else rung
        blank = at.get(rung + str(e.obj.get("blank")))
        if blank is not None and blank.kind != "refused" and not blank.faults:
            out.append(("missing", f"{e.where}.excess_over_blank", "its blank is there"))
    return out


def _plants(plants, out, attempt, profile, role, honest, shapes):
    if not isinstance(plants, dict):
        return
    allowed = PLANT_NAMES[role] if role in PLANT_NAMES else tuple(JUDGED_AS)
    for name, obj in plants.items():
        where = f"plants.{name}"
        if obj is not None:
            out.present += 1
        if name in JUDGE_PLANTS:
            out.notes.append(f"{where}: formed by the judge itself, excluded from scoring and "
                             "recorded (amendment 4, item 5)")  # fmt: skip
            continue
        if attempt != "primary":
            out.notes.append(f"{where}: plants run only at h, so a retry's is ignored (item 1)")
            continue
        if name not in allowed:
            out.notes.append(f"{where}: not a registered plant of this family, ignored")
            continue
        if obj is None:
            out.null_plants.append(name)
            out.notes.append(f"{where}: null, a missing record (unscorable, item 1)")
            continue
        run = JUDGED_AS[name]
        if run != "blank" and run not in honest:  # an invented family with no role
            out.notes.append(f"{where}: its run {run!r} is not a run of this family, ignored")
            continue
        machine = "returned" if name == "P8 blank" else None
        e = Entry(where, name, entry_kind("plant", profile, name), "plant", run, machine,
                  PLANT_OF.get(name, name), 0.5, obj)  # fmt: skip
        entry_findings(e, profile, shapes)
        if e.kind != "refused" and isinstance(obj, dict) and isinstance(obj.get("judged_as"), str):
            if obj["judged_as"] != run:
                e.findings.append(("type", f"{where}.judged_as",
                                   f"{run!r} expected, {obj['judged_as']!r} found"))  # fmt: skip
        out.entries.append(e)


def _restart(doc, out, attempt, profile, restart_run, shapes):
    if "restart" not in doc:
        return
    obj = doc["restart"]
    if attempt != "primary" or restart_run is None:
        out.restart = "unregistered"
        if obj is not None:
            out.present += 1
        out.notes.append("restart: only AN's primary table has one; ignored (§4 (b))")
        return
    if obj is None:
        out.restart = "null"
        out.notes.append("restart: null, a missing registered run (item 5)")
        return
    out.present += 1
    out.restart = "present"
    if not isinstance(obj, dict):
        out.findings.append(("type", "restart", f"object expected, {_found(obj)} found"))
        return
    e = Entry("restart", "restart", "restart", "restart", restart_run, None, None, 0.5, obj)
    entry_findings(e, profile, shapes)
    out.entries.append(e)
