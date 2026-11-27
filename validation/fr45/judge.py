"""FR-45's judge (validation/fr45/spec/TABLE.md §11, §12.3), to RULINGS-2's import rules: the standard library,
the registered agreement.py (loaded by its path after its blob is checked) and the references' G (from their folder
on sys.path, never read); nothing from src/, nothing of the builder's driver, exporter or worlds. One file, run by
its path, so no package's __init__ is imported.

- `compare`: a table's structure against the format sample's, key by key and type by type (TABLE §12.1). Every
  path is reduced to a pattern (data keys as `<key>`, list members as `[]`); the comparison finds the patterns
  one side lacks and the types the sample does not show. `definition` is compared as an object only.
- `structure`: the structure-only pass over a table (§12.1): its keys, words, counts and nulls; no other number.
- `plant-rule`: each plant run against its honest twin (TABLE §4, §8.1, §11.1): its world, dt_s, backend and
  operators equal; its inputs and definition equal after its declared inputs_changed (B6) is applied, the
  execution record's excluded fields left out.
- `judge`: §12.3 in order: the blobs against the binding tag (S14), the structure-only pass over the reference
  files (12b), the expected-inputs file against the references' echo (S5), the table's sha256 (§1); then the
  judgement: every value §11.1 fixes in every run, its faults scoped as §11.2 says, every entry the registration
  and the references' pairs give, each criterion's verdict, and each plant by §8.2. It writes verdict.json.

Usage:
  python -B validation/fr45/judge.py compare TABLE_JSON SAMPLE_JSON [OUT_JSON]
  python -B validation/fr45/judge.py structure TABLE_JSON [OUT_JSON]
  python -B validation/fr45/judge.py plant-rule TABLE_JSON [OUT_JSON] [--exclude PATH ...]
  python -B validation/fr45/judge.py judge --references REFERENCES_DIR --expected EXPECTED_JSON --out OUT_DIR
      --repo CHECKOUT --tag BINDING_TAG                                   (steps 1 to 3, before any registered run)
  python -B validation/fr45/judge.py judge --table TABLE_DIR --references REFERENCES_DIR --expected EXPECTED_JSON
      --out OUT_DIR --repo CHECKOUT --tag BINDING_TAG --table-sha256 HEX --sample-sha256 HEX --addendum JSON
      --execution-record JSON --checks-list JSON [--exclude PATH ...]     (the judgement; every input is owed)
"""

import argparse
import copy
import json
import re
import sys
from pathlib import Path

# Objects keyed by data (the sample README's path syntax): their children's names are data, not keys.
DATA = re.compile(
    r"^(runs"
    r"|runs\.<key>\.(rows\[\]|event_map\[\]\.(before|after))\.(amounts|records)"
    r"|runs\.<key>\.rows\[\]\.(site_heat_pJ|site_occupied_fraction)"
    r"|runs\.<key>\.(capacities|free_sites|checks)"
    r"|runs\.<key>\.events\[\]\.(collected|supplied)"
    r"|runs\.<key>\.event_map\[\]\.buffer_mM"
    r"|runs\.<key>\.inputs\.(wash\.buffer_mM|ion_permeabilities|ion_permeabilities\.<key>|charges)"
    r"|runs\.<key>\.inputs\.host_values\.(areas|capacitances|ion_amounts|ion_amounts\.<key>))$"
)
OPAQUE = re.compile(
    r"^runs\.<key>\.definition$"
)  # The engine's own form: an object, not listed further.


def kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "list" if isinstance(value, list) else "object"


def patterns(doc, keysets=None):
    """{pattern: {types}} of every path in a table, the top level's INVENTED skipped. With `keysets` (a dict),
    also each object pattern's key sets, {pattern: {frozenset(keys)}}, for objects not keyed by data."""
    out = {}

    def walk(value, path):
        out.setdefault(path, set()).add(kind(value))
        if OPAQUE.match(path):
            return
        if isinstance(value, dict):
            keyed = bool(DATA.match(path))
            if keysets is not None and not keyed:
                keysets.setdefault(path, set()).add(
                    frozenset(k for k in value if path or k != "INVENTED")
                )
            for k, v in value.items():
                if not path and k == "INVENTED":
                    continue
                walk(v, f"{path}.<key>" if keyed else (f"{path}.{k}" if path else k))
        elif isinstance(value, list):
            for v in value:
                walk(v, f"{path}[]")

    walk(doc, "")
    out.pop("", None)
    return out


def compare(table, sample):
    """The structural differences of `table` from `sample` (TABLE §12.1)."""
    ours_keys, their_keys = {}, {}
    ours, theirs = patterns(table, ours_keys), patterns(sample, their_keys)
    missing = sorted(set(theirs) - set(ours))
    extra = sorted(set(ours) - set(theirs))
    types = {p: dict(ours=sorted(ours[p]), sample=sorted(theirs[p]))
             for p in sorted(set(ours) & set(theirs)) if not ours[p] <= theirs[p]}  # fmt: skip
    # Every object of ours holds a key set the sample shows at its pattern: a key missing from one entry or one
    # list member is found even where another holds it.
    keys = {p: dict(ours=[sorted(k) for k in ours_keys[p] - their_keys.get(p, set())],
                    sample=[sorted(k) for k in their_keys.get(p, set())])
            for p in sorted(ours_keys) if ours_keys[p] - their_keys.get(p, set())}  # fmt: skip
    return dict(identical=not (missing or extra or types or keys), missing=missing, extra=extra, types=types,
                keys=keys, patterns=len(ours), sample_patterns=len(theirs))  # fmt: skip


# ------------------------------------------------------------------ the structure-only pass

KIND_TABLE = "fr45 site-competition engine table, version 1"
PROTOCOL = "fr45-site-competition-v1"
UNITS = {"amount": "fmol", "volume": "pL", "concentration": "mM", "k_on": "per mM per s", "k_off": "per s",
         "time": "s", "heat": "pJ", "fraction": "1", "load": "per s", "copies": "copies"}  # fmt: skip
ENTRY = {"status", "world", "plant", "dt_s", "steps", "backend", "driver", "rows", "capacities", "free_sites",
         "events", "event_map", "step_report", "refusal", "checks", "operators", "inputs", "definition", "source",
         "record", "record_sha256"}  # fmt: skip
REFUSAL_KINDS = {"stage", "check", "definition", "domain", "harness"}
BOOKS = {"moiety ledger", "energy ledger", "dissipation check"}
OPERATOR_ID = re.compile(r"^cells\.[a-z_]+\.[a-z0-9_]+@[0-9]+$")
MAPS = {"W2": 2, "W7": 4}  # A completed run's event-map entries; one event in each.


def shape(run):
    name = run.removeprefix("INVENTED-").split("~")[0]
    return name.split("-P")[0].split("-dt")[0]


def structure(table):
    """The structure-only pass (TABLE §12.1): keys, the words and counts the contract fixes, and the nulls it
    allows; no other number. Returns (faults, the entry kinds found)."""
    faults, kinds = [], set()
    if table.get("kind") != KIND_TABLE or table.get("protocol") != PROTOCOL:
        faults.append("top: kind or protocol")
    if table.get("units") != UNITS:
        faults.append("top: units")
    for name, run in table.get("runs", {}).items():
        bad = lambda why, n=name: faults.append(f"{n}: {why}")  # noqa: E731
        if set(run) != ENTRY:
            bad(f"keys {sorted(set(run) ^ ENTRY)}")
            continue
        refusal, plant, world_shape = run["refusal"], run["plant"], shape(name)
        if run["status"] not in ("completed", "refused") or (run["status"] == "completed") != (
            refusal is None
        ):
            bad("status against refusal")
        if run["backend"] != "compiled" or run["driver"] != {"window_steps": 1}:
            bad("backend or driver")
        if plant is not None and (plant.get("id") not in {f"P{k}" for k in range(1, 10)}
                                  or not str(plant.get("patch", "")).startswith("validation/")):  # fmt: skip
            bad("plant id or patch")
        if any(not OPERATOR_ID.match(op) for op in run["operators"]):
            bad("an operator ID")
        if any(v not in ("state", "derived") for v in run["free_sites"].values()):
            bad("free_sites word")
        for event in run["events"]:
            if (
                event.get("kind") != "wash"
                or event.get("operator") != "cells.operator.scheduled_compartment_wash@1"
            ):
                bad("event words")
        if any(m.get("variant") not in ("numpy", "compiled") for m in run["event_map"]):
            bad("event_map variant")
        report = run["step_report"]
        if report is not None:
            if world_shape != "W5" or report.get("step") != 1 or report.get("limit") != 0.5 or report.get(
                    "verdict") not in ("refused", "admitted") or any(
                    x.get("kind") not in ("L_n", "L_R", "L_B") for x in report.get("loads", [])):  # fmt: skip
                bad("step_report words")
        parsed = run["inputs"] is not None
        if refusal is not None:
            kinds.add(f"refused:{refusal.get('kind')}")
            if refusal.get("kind") not in REFUSAL_KINDS:
                bad("refusal kind")
            book = refusal.get("book")
            if refusal.get("kind") == "check":
                if not (book in BOOKS or str(book).startswith("host check: ")):
                    bad("refusal book")
            elif book is not None:
                bad("a book outside check")
            if refusal.get("raised") is None and refusal.get("kind") != "harness":
                bad("raised null outside harness")
            if not parsed and (run["definition"] is not None or run["checks"] is not None or run["operators"]
                               or run["capacities"] or run["free_sites"] or run["rows"] or run["events"]
                               or run["event_map"] or report is not None):  # fmt: skip
                bad("a run refused before parse holds more than its nulls")
            if not parsed and (
                refusal.get("step") is not None or refusal.get("time_s") is not None
            ):
                bad("step or time at parse")
        else:
            kinds.add("completed" if plant is None else f"plant:{plant.get('id')}")
            want = MAPS.get(world_shape, 0)
            if len(run["events"]) != (1 if want else 0) or len(run["event_map"]) != want:
                bad("event or map count")
            if world_shape == "W5" and report is None:
                bad("W5 without its step report")
        if parsed and (run["definition"] is None or run["checks"] is None):
            bad("a parsed run without definition or checks")
    return faults, sorted(kinds)


# ------------------------------------------------------------------ the plant rule

PATH = re.compile(r"^(?P<list>\w+)\[(?P<match>[^\]]+)\]\.(?P<key>\w+)$")
SITE_LAW = "cells.operator.site_occupancy@1"
B6_DEFINITION = {
    "k_off": "dissociation_rate_per_s"
}  # P2's declared change, where it sits in `definition`.


def _member(items, match):
    want = dict(part.split("=", 1) for part in match.split(","))
    return next(i for i in items if all(str(i.get(k)) == v for k, v in want.items()))


def get_path(doc, path):
    m = PATH.match(path)
    if m:
        return _member(doc[m["list"]], m["match"])[m["key"]]
    value = doc
    for part in path.split("."):
        value = value[part]
    return value


def set_path(doc, path, value):
    m = PATH.match(path)
    if m:
        _member(doc[m["list"]], m["match"])[m["key"]] = value
        return
    *parents, last = path.split(".")
    target = doc
    for part in parents:
        target = target[part]
    target[last] = value


def _definition_with(definition, changes):
    """The honest run's definition with a plant's declared changes (B6) applied where they sit in it."""
    definition = copy.deepcopy(definition)
    if not changes:
        return definition
    block = next(op for op in definition["model"]["operators"] if op.get("law") == SITE_LAW)
    for path, value in changes.items():
        m = PATH.match(path)
        if not m or m["list"] != "populations" or m["key"] not in B6_DEFINITION:
            raise ValueError(f"no B6 path in the definition for {path}")
        _member(block["populations"], m["match"])[B6_DEFINITION[m["key"]]] = value
    return definition


def _drop(doc, paths):
    doc = copy.deepcopy(doc)
    for path in paths:
        *parents, last = path.split(".")
        target = doc
        for part in parents:
            target = target.get(part, {}) if isinstance(target, dict) else {}
        if isinstance(target, dict):
            target.pop(last, None)
    return doc


def twin_of(name, runs):
    """A plant run's honest twin: the run of its shape with no plant (INVENTED-W1p for INVENTED-W1p-P8)."""
    base = name.split("~")[0].rsplit("-P", 1)[0]
    return base if base in runs and runs[base]["plant"] is None else None


def plant_rule(table, exclusions=()):
    """Each plant run against its honest twin: the departures (TABLE §4, §8.1), and the runs it could not form."""
    runs = table["runs"]
    out = {}
    for name, run in runs.items():
        if run["plant"] is None:
            continue
        twin = twin_of(name, runs)
        if twin is None or runs[twin]["inputs"] is None:
            out[name] = dict(twin=twin, formed=False, departures=["no honest twin in the table"])
            continue
        honest = runs[twin]
        departures = [k for k in ("world", "dt_s", "backend", "operators") if run[k] != honest[k]]
        changed = {p: get_path(run["inputs"], p) for p in run["plant"]["inputs_changed"]}
        inputs = copy.deepcopy(honest["inputs"])
        for path, value in changed.items():
            set_path(inputs, path, value)
        if inputs != run["inputs"]:
            departures.append("inputs")
        if run["definition"] is None:
            departures.append("definition: null")
        else:
            try:
                expected = _definition_with(honest["definition"], changed)
            except (KeyError, StopIteration, ValueError) as error:
                departures.append(
                    f"definition: the B6 paths cannot be applied ({type(error).__name__})"
                )
            else:
                if _drop(expected, exclusions) != _drop(run["definition"], exclusions):
                    departures.append("definition")
        out[name] = dict(
            twin=twin, formed=True, inputs_changed=list(changed), departures=departures
        )
    return dict(departures=sum(len(r["departures"]) for r in out.values()), runs=out)


# ------------------------------------------------------------------ the judgement (TABLE §1, §10, §11, §8.2, §12.3)

EPS = 2.0**-52
SOLVER = "cells.solver.imex_ars222_face_electromigration@1"
WASH_ID = "cells.operator.scheduled_compartment_wash@1"
BASE_OPERATORS = (
    "cells.model.resolved_pump_composite@1",
    "cells.model.resolved_pump_tissue@3",
    SITE_LAW,
)
# The refusal mapping (TABLE §7; its dated addendum fixes it before any registered run): (raised, name) -> (kind,
# book). A check's name gives its book; the stage condition gives `stage`; the site operator's domain names give
# `domain`; anything the engine did not raise is `harness`.
BOOK_OF = {
    "site_moiety_entity": "moiety ledger",
    "energy": "energy ledger",
    "dissipation": "dissipation check",
}
CHECK_NAMES = ("domain", "local", "outside", "total", "charge", "electrode", "global_charge", "energy",
               "reservoir_work", "electrode_work", "metabolic_work", "site_bound_entity", "site_moiety_entity",
               "dissipation", "wash_ions")  # fmt: skip
DOMAIN_NAMES = ("initial occupancies over 1 on a set", "solver domain")


def mapped(refusal):
    """(kind, book) of a refusal, by the judge's own mapping of `raised` and `name` (TABLE §7, B4)."""
    raised, name = refusal.get("raised"), refusal.get("name")
    if raised is None or not str(raised).startswith("cells."):
        return "harness", None
    if raised.endswith("NumericalError"):
        if name == "stage condition":
            return "stage", None
        if name in CHECK_NAMES and name != "domain":
            return "check", BOOK_OF.get(name, f"host check: {name}")
        return "domain", None
    if raised.endswith("ConfigError"):
        return ("domain" if name in DOMAIN_NAMES else "definition"), None
    return "harness", None


# The registration (TABLE §3, §5.1, §5.2, §6, §8.2, §9): the runs and their dt, each world's saved rows (time, step),
# the wash's step and time, the event map's steps, the reference file each world reads, the facing nodes, the
# operators and the plants' entries (plant, criterion, world, time_s). The judge enumerates every entry from these
# and the references' pairs, never from the table [B2].
def _saved(dt, *rows):
    return {repr(dt): [list(r) for r in rows]}


_W1 = ((0.0, 0), (0.2, 25), (0.4, 50), (0.8, 100), (1.6, 200), (3.2, 400), (6.4, 800), (12.8, 1600), (25.6, 3200),
       (51.2, 6400))  # fmt: skip
_W3 = ((0.0, 0), (0.1, 25), (0.2, 50), (0.5, 125), (1.0, 250), (2.0, 500), (4.0, 1000), (8.0, 2000), (16.0, 4000),
       (30.0, 7500))  # fmt: skip
_WORLDS = ("W1", "W1eq", "W1p", "W2", "W3", "W3p", "W4", "W5", "W6", "W7", "W7s")
REGISTERED = dict(
    runs={**{w: dict(world=w, plant=None, dt_s=dt) for w, dt in (
              ("W1", 0.008), ("W1eq", 0.008), ("W2", 0.0125), ("W3", 0.004), ("W5", 0.1), ("W6", 0.00625),
              ("W7", 0.0025), ("W7s", 0.0025), ("W1p", 0.008), ("W3p", 0.004))},
          **{f"W4-dt{dt!r}": dict(world="W4", plant=None, dt_s=dt) for dt in (0.08, 0.04, 0.02)},
          **{f"W1p-{p}": dict(world="W1p", plant=p, dt_s=0.008) for p in ("P1", "P2", "P3", "P6", "P8", "P9")},
          "W5-P4": dict(world="W5", plant="P4", dt_s=0.1), "W2-P5": dict(world="W2", plant="P5", dt_s=0.0125),
          "W7-P5": dict(world="W7", plant="P5", dt_s=0.0025), "W3p-P7": dict(world="W3p", plant="P7", dt_s=0.004)},
    rows={"W1": _saved(0.008, *_W1), "W1eq": _saved(0.008, (0.0, 0), (0.8, 100), (4.0, 500), (8.0, 1000)),
          "W1p": _saved(0.008, *_W1[:7]),
          "W2": _saved(0.0125, (0.0, 0), (2.0, 160), (4.0, 320), (4.0125, 321), (5.0, 400), (7.5, 600), (10.0, 800),
                       (20.0, 1600), (40.0, 3200), (60.0, 4800), (75.0, 6000)),
          "W3": _saved(0.004, *_W3), "W3p": _saved(0.004, *_W3[:6]),
          "W4": {**_saved(0.08, (0.0, 0), (0.4, 5), (0.8, 10), (1.2, 15), (1.6, 20)),
                 **_saved(0.04, (0.0, 0), (0.4, 10), (0.8, 20), (1.2, 30), (1.6, 40)),
                 **_saved(0.02, (0.0, 0), (0.4, 20), (0.8, 40), (1.2, 60), (1.6, 80))},
          "W5": _saved(0.1, (0.0, 0), (1.0, 10)),
          "W6": _saved(0.00625, (0.0, 0), (0.25, 40), (0.5, 80), (1.0, 160), (2.0, 320), (4.0, 640), (8.0, 1280),
                       (16.0, 2560), (25.0, 4000)),
          "W7": _saved(0.0025, (0.0, 0), (0.5, 200), (1.0, 400), (1.0025, 401), (1.5, 600), (2.0, 800), (3.0, 1200),
                       (5.0, 2000), (8.0, 3200), (12.0, 4800)),
          "W7s": _saved(0.0025, (0.0, 0), (0.25, 100), (0.5, 200), (1.0, 400), (1.5, 600), (2.0, 800))},
    wash={"W2": dict(time_s=4.0), "W7": dict(time_s=1.0)},  # Steps 320 and 400 (§5.1).
    maps={"W2": [4.0], "W7": [0.0, 1.0]},  # The saved states the map acts on, by time: steps 320; 0 and 400 (§6).
    files={**{w: w for w in _WORLDS}, "W3p": "W3"},
    heat_nodes={**{w: ["well"] for w in ("W1", "W1eq", "W1p", "W2", "W5", "W6", "W7", "W7s")},
                "W3": ["specimen", "well"], "W3p": ["specimen", "well"], "W4": ["vat"]},
    operators={w: [*BASE_OPERATORS, *([WASH_ID] if w in ("W2", "W7") else [])] for w in _WORLDS},
    plants=[["P1", "C1", "W1p", None], ["P2", "C1", "W1p", None], ["P3", "C3b", "W1p", None],
            ["P4", "C7", "W5", None], ["P5", "C6", "W2", 4.0], ["P5", "C4a", "W2", None], ["P5", "C6", "W7", 0.0],
            ["P5", "C6", "W7", 1.0], ["P5", "C4a", "W7", None], ["P6", "C3b", "W1p", None],
            ["P7", "C1", "W3p", None], ["P7", "C5", "W3p", None], ["P8", "C10", "W1p", None],
            ["P9", "C9", "W1p", None]],
)  # fmt: skip
# CRITERIA:119-129 with reading 2: the criteria that catch each plant (P5 and P7 need both), the book its row names,
# and the entries kept as information (P3's and P6's under C3a), which never catch [§8.2].
CAUGHT_BY = {"P1": ("C1",), "P2": ("C1",), "P3": ("C3b",), "P4": ("C7",), "P5": ("C6", "C4a"), "P6": ("C3b",),
             "P7": ("C5", "C1"), "P8": (), "P9": ("C9",)}  # fmt: skip
NEEDS_ALL = ("P5", "P7")
ROW_BOOK = {"P3": "dissipation check", "P6": "energy ledger", "P8": "moiety ledger"}
INFORMATION = (("P3", "C3a"), ("P6", "C3a"))
# The honest W1p's and W3p's entries that are the plants' baselines, not criteria (TABLE §3) [7a, 7c].
BASELINE_ONLY = (("W1p", "C1"), ("W1p", "C3b"), ("W1p", "C9"), ("W3p", "C1"))
CRITERIA = (
    "C1",
    "C2a",
    "C2b",
    "C3a",
    "C3b",
    "C3c",
    "C4a",
    "C4b",
    "C4c",
    "C5",
    "C6",
    "C7",
    "C8",
    "C9",
    "C10",
)


class Registration:
    """The registration the judge reads: REGISTERED at the judged run; an invented one (same shape) in the dress
    rehearsal, its run names carrying the `INVENTED-` prefix."""

    def __init__(self, data, prefix=""):
        self.data, self.prefix = data, prefix
        self.runs = data["runs"]
        self.plants = [tuple(e) for e in data["plants"]]

    def full(self, name):
        return self.prefix + name

    def honest(self, world=None):
        """{name: spec} of the honest runs (of one world)."""
        return {
            n: s for n, s in self.runs.items() if s["plant"] is None and world in (None, s["world"])
        }

    def rows(self, world, dt):
        return [(t, k) for t, k in self.data["rows"][world][repr(dt)]]

    def step(self, world, dt, t):
        """The registered step of a registered time t (TABLE §5.1); None for a time the registration lacks."""
        found = [k for tt, k in self.rows(world, dt) if tt == t]
        return found[0] if found else None

    def dts(self, world):
        return [float(d) for d in self.data["rows"][world]]


# ------------------------------------------------------------------ reading files (TABLE §1, §10, §12.3)


def strict_load(path):
    """Strict JSON (TABLE §1): no NaN or infinity, and no key twice in one object."""

    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError(f"a key twice in one object in {path}")
        return dict(items)

    def constant(word):
        raise ValueError(f"{word} in {path}: not strict JSON")

    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=constant)


def table_sha256(folder, recorded=None, sample=None):
    """(sha256, departures) of table/table.json against its SHA256SUMS line, the lead's record and the format
    sample's (TABLE §1). A departure means the judge does not read the table."""
    import hashlib

    folder = Path(folder)
    digest = hashlib.sha256((folder / "table.json").read_bytes()).hexdigest()
    out = []
    lines = (folder / "SHA256SUMS").read_text().splitlines()
    if lines != [f"{digest}  table.json"]:
        out.append("SHA256SUMS is not the one line of table.json's sha256")
    if recorded is not None and recorded != digest:
        out.append("the sha256 departs from the lead's record")
    if sample is not None and sample == digest:
        out.append("the table is the format sample")
    return digest, out


def git_blob(data):
    """The git blob SHA-1 of a file's bytes (the judge's S14 check)."""
    import hashlib

    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tag_blobs(repo, tag, paths):
    """{path: blob} of the binding tag's files under `paths` (git ls-tree; names and blobs, no content)."""
    import subprocess

    listed = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--full-tree", tag, "--", *paths],
                            capture_output=True, text=True, check=True).stdout  # fmt: skip
    out = {}
    for line in listed.splitlines():
        meta, path = line.split("\t", 1)
        out[path] = meta.split()[2]
    return out


def check_blobs(found, expected):
    """{path: (found, expected)} of every file whose blob departs from the binding tag's, or that one side lacks
    (TABLE §10, S14); empty when every file agrees. `found` maps a path to its bytes' blob."""
    return {p: (found.get(p), expected.get(p)) for p in sorted(set(found) | set(expected))
            if found.get(p) != expected.get(p)}  # fmt: skip


def load_by_path(name, path):
    """A module loaded from its file alone (importlib.util), so no package's __init__ is imported."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The references' file forms (the census, CENSUS-2026-11-27): each pair's (criterion, class, value type, tolerance
# type, terms, its other keys), and the observables each criterion's text maps onto.
REFERENCE_TOP = {"schema", "invented", "world", "units", "equilibrium", "trajectory", "balances", "heats", "pairs",
                 "spread", "spread_note", "distance_at_horizon", "plants", "provenance"}  # fmt: skip
REFERENCE_OPTIONAL = {"wash", "closed_form", "stage"}
PAIR_FORMS = {
    ("C1", "band", "float", "float", "-", "against"), ("C10", "constant", "str", "null", "-", "against,dt_s"),
    ("C2a", "band", "float", "float", "-", "against"), ("C2b", "derived", "float", "float", "-", "against,dt_s"),
    ("C3a", "band", "float", "float", "-", "against,end_s,start_s"),
    ("C3b", "derived", "null", "float", "-", "against,dt_s,end_s,start_s"),
    ("C3c", "derived", "null", "float", "-", "against,end_s,start_s"),
    ("C3c", "derived", "null", "float", "-", "against,end_s,spans_wash,start_s"),
    ("C4a", "derived", "float", "float", "-", "against,dt_s"), ("C4b", "derived", "float", "float", "-", "against"),
    ("C4b", "derived", "null", "null", "terms", "against,tolerance_information,tolerance_terms"),
    ("C4c", "band", "float", "float", "-", "against"), ("C5", "derived", "float", "float", "-", "against,dt_s"),
    ("C6", "constant", "str", "null", "-", "against"), ("C7", "constant", "str", "null", "-", "against"),
    ("C8", "band", "float", "float", "-", "against,dt_s,scale"),
    ("C8", "band", "float", "null", "-", "against,dt_s,scale"), ("C8", "band", "null", "null", "-", "against,minimum"),
    ("C9", "derived", "null", "null", "terms", "against,tolerance_information,tolerance_terms"),
}  # fmt: skip
AMOUNT = r"(n:[^@:]+@[^@:]+|R:[^:]+|B:[^:]+)"
OBSERVABLE = {
    "C1": AMOUNT, "C2a": AMOUNT, "C2b": AMOUNT, "C3a": r"H:[^:]+", "C3b": r"H:[^:]+",
    "C3c": r"cumulative_site_heat:[^:]+", "C4a": r"books:[^@:]+@[^@:]+", "C4b": r"(n|removed|supplied):[^@:]+@[^@:]+",
    "C4c": r"(removed|supplied):[^@:]+@[^@:]+", "C5": r"sites:[^:]+", "C6": r"(R|B):[^:]+", "C7": r"stage:first_step",
    "C8": AMOUNT + r"|ratio:e\([^)]+\)/e\([^)]+\)", "C9": r"theta:[^:]+", "C10": r"run",
}  # fmt: skip
WORDS = {"C6": "unchanged", "C7": "refused", "C10": "completes"}
TERMS = {
    "C4b": {"n": ("eps_factor", "f_V_c_buf"), "removed": ("eps_factor",)},
    "C9": {"theta": ("eps_term",)},
}


def _type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "float"
    return type(value).__name__


def pair_form(pair):
    extra = ",".join(
        sorted(set(pair) - {"criterion", "observable", "time_s", "class", "value", "tolerance"})
    )
    return (pair.get("criterion"), pair.get("class"), _type(pair.get("value")), _type(pair.get("tolerance")),
            "terms" if "tolerance_terms" in pair else "-", extra)  # fmt: skip


def invented_file_structure(ref):
    """The structure-only pass over the references' invented file, the file the judge reads first (the plan's
    step 2; PROTOCOL:129-130; SPEC:391-392): every pair's form one the judge maps, every census form present in
    it, every observable one its criterion's text names, and the constant words. Returns the findings."""
    out = []
    forms = {pair_form(p) for p in ref.get("pairs", [])}
    out += [f"form {f} is not one the judge maps" for f in sorted(forms - PAIR_FORMS, key=str)]
    out += [
        f"the census's form {f} is not in the invented file"
        for f in sorted(PAIR_FORMS - forms, key=str)
    ]
    for pair in ref.get("pairs", []):
        crit = pair.get("criterion")
        if not re.fullmatch(OBSERVABLE.get(crit, "$^"), str(pair.get("observable"))):
            out.append(
                f"{crit} {pair.get('observable')}: an observable its criterion's text does not name"
            )
        if crit in WORDS and pair.get("value") != WORDS[crit]:
            out.append(f"{crit}: the constant {pair.get('value')!r}")
    return out


def reference_structure(refs, reg, invented):
    """The structure-only pass over the reference files (TABLE §12.3 step 2) [12b]: their top keys, each pair's
    form and observable against its criterion's text, the constant words, the terms each formula needs, the plant
    entries against the registration's, and each world's echo keys that G and the cross-check read. Returns the
    findings: a form the judge cannot map is reported here, before any registered run."""
    out = []
    worlds = {reg.data["files"][w] for w in reg.data["rows"]}
    for world in sorted(worlds - set(refs)):
        out.append(f"{world}: no reference file")
    for world, ref in sorted(refs.items()):
        keys = set(ref)
        missing, extra = (
            sorted(REFERENCE_TOP - keys),
            sorted(keys - REFERENCE_TOP - REFERENCE_OPTIONAL),
        )
        if missing or extra:
            out.append(f"{world}: top keys missing {missing}, beyond the census's {extra}")
        if ref.get("invented") is not invented:
            out.append(f"{world}: invented is {ref.get('invented')!r}")
        echo = ref.get("world", {})
        for key in (
            "constants",
            "nodes",
            "sets",
            "populations",
            "free_amounts",
            "ligands",
            "start",
        ):
            if key not in echo:
                out.append(f"{world}: world.{key} missing")
        for pair in ref.get("pairs", []):
            crit, form = pair.get("criterion"), pair_form(pair)
            where = f"{world}: {crit} {pair.get('observable')} at {pair.get('time_s')}"
            if form not in PAIR_FORMS:
                out.append(f"{where}: form {form} is not one the judge maps")
            if not re.fullmatch(OBSERVABLE.get(crit, "$^"), str(pair.get("observable"))):
                out.append(f"{where}: an observable its criterion's text does not name")
            if crit in WORDS and pair.get("value") != WORDS[crit]:
                out.append(f"{where}: the constant {pair.get('value')!r}")
            kind = str(pair.get("observable")).split(":", 1)[0]
            need = TERMS.get(crit, {}).get(kind, ()) if "tolerance_terms" in pair else ()
            if any(not isinstance(pair["tolerance_terms"].get(t), (int, float)) for t in need):
                out.append(f"{where}: tolerance_terms lacks {need}")
        for entry in ref.get("plants", []):
            row = (
                entry.get("plant"),
                entry.get("criterion"),
                entry.get("world"),
                entry.get("time_s"),
            )
            if row not in reg.plants and row[:2] not in INFORMATION:
                out.append(f"{world}: plant entry {row} is not a registered entry")
    found = {(e.get("plant"), e.get("criterion"), e.get("world"), e.get("time_s")) for r in refs.values()
             for e in r.get("plants", [])}  # fmt: skip
    for row in reg.plants:
        if row not in found:
            out.append(f"registered plant entry {row} is in no reference file")
    return out


# ------------------------------------------------------------------ the echo against the expected inputs (§4.1, S5)

MATCH = {"nodes": ("id",), "patches": ("id",), "free_amounts": ("ligand", "node"), "sets": ("id",),
         "populations": ("id",), "permeabilities": ("patch", "ligand"), "multipliers": ("of", "name"),
         "capacitor_components": ("held_by",)}  # fmt: skip
VALUE_SETS = ("ligands", "observation_times_s", "members")


def _same_number(a, b):
    import struct

    return struct.pack("<d", float(a)) == struct.pack("<d", float(b))


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


class Echo:
    """One run's comparison of its `inputs` with its expected entry (TABLE §4.1): lists as sets of members by their
    keys, numbers as binary64 values, the markers and nulls as the exceptions' closed list says."""

    def __init__(self, markers, addendum=None, start=None, changed=None, extra_ligands=()):
        self.markers, self.addendum, self.start = markers or {}, addendum, start
        self.changed, self.extra = changed or {}, set(extra_ligands)
        self.departures, self.unchecked = [], []

    def compare(self, echo, expected):
        self.echo = echo
        self._walk(echo, expected, "")
        for path, value in self.changed.items():
            got = _get(echo, path)
            if not (_is_number(got) and _is_number(value) and _same_number(got, value)):
                self.departures.append(f"{path}: the declared change {value!r} departs ({got!r})")
        return self

    def _skip(self, path):
        return path in self.changed

    def _walk(self, got, want, path):
        if self._skip(path):
            return
        if isinstance(want, str) and want in self.markers.values():
            return self._marker(got, want, path)
        if want is None and (path == "constants.RT_pJ_per_fmol" or self.start is not None and path.endswith(
                (".initial_occupancy", ".n_fmol"))):  # fmt: skip
            return self._null(got, path)
        if isinstance(want, dict):
            if path == "ion_permeabilities":
                return self._ions(got, want)
            if path == "charges" and isinstance(got, dict):
                got = {k: v for k, v in got.items() if not (k in self.extra and v == 0)}
            if not isinstance(got, dict) or set(got) != set(want):
                return self.departures.append(f"{path}: keys {sorted(set(got or {}) ^ set(want))}")
            for key in want:
                self._walk(got[key], want[key], f"{path}.{key}" if path else key)
            return None
        if isinstance(want, list):
            return self._list(got, want, path)
        if _is_number(want):
            if not (_is_number(got) and _same_number(got, want)):
                self.departures.append(f"{path}: {got!r} for {want!r}")
            return None
        if got != want:
            self.departures.append(f"{path}: {got!r} for {want!r}")
        return None

    def _list(self, got, want, path):
        name = path.rsplit(".", 1)[-1].split("]")[-1]
        if not isinstance(got, list):
            return self.departures.append(f"{path}: not a list")
        if name in VALUE_SETS:
            extra = [g for g in got if name == "ligands" and g in self.extra]
            got = [g for g in got if g not in extra]
            bad = len(got) != len(set(map(repr, got))) or {repr(float(g)) if _is_number(g) else g for g in got} != {
                repr(float(w)) if _is_number(w) else w for w in want}  # fmt: skip
            if bad:
                self.departures.append(
                    f"{path}: members {sorted(map(str, got))} for {sorted(map(str, want))}"
                )
            return None
        keys = MATCH.get(name)
        if keys is None:
            return self.departures.append(f"{path}: a list the comparison does not know")

        def key(member):
            return tuple(member.get(k) for k in keys)

        got_by = {
            key(m): m
            for m in got
            if not (self.extra and set(key(m)) & self.extra and self._trace(m))
        }
        want_by = {key(m): m for m in want}
        if len(got_by) != len(
            [m for m in got if not (self.extra and set(key(m)) & self.extra and self._trace(m))]
        ):
            self.departures.append(f"{path}: a member twice")
        for k in sorted(set(got_by) ^ set(want_by), key=str):
            self.departures.append(
                f"{path}[{','.join(map(str, k))}]: {'extra' if k in got_by else 'missing'}"
            )
        for k in sorted(set(got_by) & set(want_by), key=str):
            label = ",".join(f"{a}={b}" for a, b in zip(keys, k, strict=True))
            self._walk(got_by[k], want_by[k], f"{name}[{label}]")
        return None

    def _trace(self, member):
        """W7s's L2, if the engine holds it (S11, S-g): at its trace, permeability 0.0 or charge 0 -- information."""
        if "declared" in member:
            return member["declared"] is False
        if "value" in member:
            return member["value"] == 0.0
        return True

    def _marker(self, got, marker, path):
        kind = next(k for k, v in self.markers.items() if v == marker)
        if kind == "trace":
            found = re.search(r"node=([^,\]]+)", path)
            node = found.group(1) if found else None
            volume = next((n["volume_pL"] for n in self.echo["nodes"] if n["id"] == node), None)
            ok = _is_number(got) and _is_number(volume) and _same_number(got, 1e-12 * volume)
            if not ok:
                self.departures.append(f"{path}: {got!r} is not 1e-12 x the compartment's volume")
            return None
        value = None if self.addendum is None else _get(self.addendum, path)
        if value is None:
            self.unchecked.append(f"{path}: the host-entity addendum's value (§9.6)")
            return None
        return self._walk(got, value, path + "<addendum>")

    def _null(self, got, path):
        if path == "constants.RT_pJ_per_fmol":
            return None  # Recorded (SPEC:36-39).
        if self.start is not None and path.endswith((".initial_occupancy", ".n_fmol")):
            want = _get(self.start, path)
            if not (_is_number(got) and _is_number(want) and _same_number(got, want)):
                self.departures.append(
                    f"{path}: {got!r} departs from the references' start {want!r}"
                )
            return None
        return None

    def _ions(self, got, want):
        ions = set()
        for amounts in (self.echo.get("host_values") or {}).get("ion_amounts", {}).values():
            ions |= set(amounts)
        if not isinstance(got, dict) or set(got) != set(want):
            return self.departures.append("ion_permeabilities: patches")
        for patch, values in got.items():
            if set(values) != ions or any(
                not _is_number(v) or not _same_number(v, 0.0) for v in values.values()
            ):
                self.departures.append(
                    f"ion_permeabilities.{patch}: not 0.0 for each of the world's ions"
                )
        return None


def _get(doc, path):
    """A value by an inputs key path (TABLE §8.1's syntax, as `get_path`, plus dotted keys and `key=value` members
    matched by several keys); None where there is none."""
    current = doc
    for part in re.findall(r"[^.\[\]]+(?:\[[^\]]+\])?", path.replace("<addendum>", "")):
        name, _, match = part.partition("[")
        current = current.get(name) if isinstance(current, dict) else None
        if match:
            wants = dict(kv.split("=", 1) for kv in match.rstrip("]").split(","))
            found = [m for m in current or [] if all(str(m.get(k)) == v for k, v in wants.items())]
            current = found[0] if len(found) == 1 else None
        if current is None:
            return None
    return current


def cross_check(expected, refs, reg):
    """The expected-inputs file against the references' world echo, by §4.1's key map (TABLE §12.3 step 3) [S5].
    Any departure stops the judge before anything is scored."""
    out = []
    for name, want in sorted(expected["runs"].items()):
        spec = reg.runs.get(name)
        if spec is None:
            out.append(f"{name}: not a registered honest run")
            continue
        world = spec["world"]
        echo = refs.get(reg.data["files"][world], {}).get("world")
        if echo is None:
            out.append(f"{name}: no reference file")
            continue

        def eq(a, b, where, name=name):
            if a is None:  # A null of the expected file is not cross-checked (W1eq's start, RT).
                return
            same = _same_number(a, b) if _is_number(a) and _is_number(b) else a == b
            if not same:
                out.append(f"{name}: {where}: {a!r} against the references' {b!r}")

        eq(want["constants"]["sites_per_fmol"], echo["constants"].get("N_f_sites_per_fmol"), "N_f")
        eq(want["constants"]["temperature_K"], echo["constants"].get("T_K"), "T")
        nodes = {n["id"]: n for n in echo["nodes"]}
        registered = {n["id"] for n in want["nodes"] if n["registered"]}
        for node in want["nodes"]:
            if node["registered"]:
                eq(node["kind"], nodes.get(node["id"], {}).get("kind"), f"nodes[{node['id']}].kind")
                eq(node["volume_pL"], nodes.get(node["id"], {}).get("V"), f"nodes[{node['id']}].V")
        for patch in echo.get("patches", []):
            mine = next((p for p in want["patches"] if p["id"] == patch["id"]), None)
            for side in ("inside", "outside"):
                if patch.get(side) in registered:
                    eq(
                        None if mine is None else mine[side],
                        patch[side],
                        f"patches[{patch['id']}].{side}",
                    )
        if set(want["ligands"]) != set(echo["ligands"]):
            out.append(
                f"{name}: ligands {sorted(want['ligands'])} against {sorted(echo['ligands'])}"
            )
        amounts = {(a["ligand"], a["node"]): a for a in want["free_amounts"]}
        for a in echo["free_amounts"]:
            mine = amounts.get((a["ligand"], a["node"]))
            if mine is None:
                out.append(f"{name}: free_amounts[{a['ligand']}@{a['node']}] missing")
                continue
            eq(mine["n_fmol"], a["n"], f"free_amounts[{a['ligand']}@{a['node']}].n")
            eq(mine["declared"], a["declared"], f"free_amounts[{a['ligand']}@{a['node']}].declared")
        sets = {s["id"]: s for s in want["sets"]}
        if set(sets) != {s["id"] for s in echo["sets"]}:
            out.append(
                f"{name}: sets {sorted(sets)} against {sorted(s['id'] for s in echo['sets'])}"
            )
        for s in echo["sets"]:
            for key in ("copies", "sites_per_copy", "accessible_fraction", "faces"):
                eq(sets.get(s["id"], {}).get(key), s[key], f"sets[{s['id']}].{key}")
        pops = {p["id"]: p for p in want["populations"]}
        if set(pops) != {p["id"] for p in echo["populations"]}:
            out.append(f"{name}: populations against the references'")
        for p in echo["populations"]:
            mine = pops.get(p["id"], {})
            for key in ("set", "ligand", "k_on", "k_off", "initial_occupancy"):
                eq(mine.get(key), p[key], f"populations[{p['id']}].{key}")
            eq(
                sets.get(mine.get("set"), {}).get("faces"),
                p.get("faces"),
                f"populations[{p['id']}].faces",
            )
        dts = echo["dt"] if isinstance(echo["dt"], list) else [echo["dt"]]
        if not any(_same_number(want["dt_s"], d) for d in dts):
            out.append(f"{name}: dt_s {want['dt_s']!r} not among the references' {dts}")
        if world != "W3p":
            if "observation_times" in echo and {float(t) for t in want["observation_times_s"]} != {
                    float(t) for t in echo["observation_times"]}:  # fmt: skip
                out.append(f"{name}: observation_times_s against the references'")
            if "horizon" in echo:
                eq(want["horizon_s"], echo["horizon"], "horizon")
        if want.get("wash") is not None or echo.get("wash") is not None:
            w, r = want.get("wash") or {}, echo.get("wash") or {}
            for a, b in (("time_s", "t"), ("node", "node"), ("fraction", "f")):
                eq(w.get(a), r.get(b), f"wash.{a}")
            if set(w.get("buffer_mM", {})) != set(r.get("buffer", {})):
                out.append(f"{name}: wash.buffer_mM members against the references'")
            for lig, c in w.get("buffer_mM", {}).items():
                eq(c, r.get("buffer", {}).get(lig), f"wash.buffer_mM.{lig}")
    return out


# ------------------------------------------------------------------ the run's identity (TABLE §11.1) and its faults (§11.2)

ROW_KEYS = {"step", "time_s", "amounts", "records", "site_heat_pJ", "site_occupied_fraction"}
SOURCE_TYPES = {"engine_revision": str, "checkout_dirty": bool, "snapshot": str, "snapshot_patch_sha256": str,
                "python": str, "numpy": str, "scipy": str, "jax": str, "jaxlib": str, "jax_enable_x64": bool,
                "jax_platforms": str, "blas_threads": int, "machine": str, "external_modules": list}  # fmt: skip
# Which entries a fault touches (§11.2): the identity items and the record hash touch every entry of their run; the
# others, the entries that read their key (§11's table, §8.1's), a refusal-based catch among them.
IDENTITY_ITEMS = (2, 3, 4, 9, 10, 11, 12, 13, 14)
TOUCHES = {5: ("C4c",), 6: ("C4b", "C6"), 7: ("C7",), 8: ("C7", "C10", "refusal")}


def _bits_equal(a, b):
    """Equality bit for bit (TABLE §1): numbers by their binary64 patterns, objects and lists member by member."""
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_bits_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_bits_equal(x, y) for x, y in zip(a, b, strict=True))
    if _is_number(a) and _is_number(b):
        return type(a) is type(b) and (a == b if isinstance(a, int) else _same_number(a, b))
    return a == b


def _has_null(value):
    if isinstance(value, dict):
        return any(_has_null(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_null(v) for v in value)
    return value is None


class Env:
    """The judgement's inputs: the table, the reference files, the registration, agreement.py, G, and the files the
    identity checks read (the expected inputs; the addenda and the execution record when they exist)."""

    def __init__(self, table, refs, reg, agreement, G, expected=None, addendum=None, record=None, checks=None,
                 exclusions=()):  # fmt: skip
        self.table, self.refs, self.reg, self.agreement, self.G = table, refs, reg, agreement, G
        self.expected, self.addendum, self.record, self.checks = expected, addendum, record, checks
        self.exclusions = list(exclusions)
        self.faults, self.unchecked = [], []

    def run(self, name):
        return (self.table.get("runs") or {}).get(self.reg.full(name))

    def ref(self, world):
        return self.refs.get(self.reg.data["files"][world])

    def honest_name(self, world, dt=None):
        """The world's honest run by its dt, or its one run where the pair holds no dt (an invented registration
        may name a world's default dt; the registered worlds' pairs need none)."""
        runs = self.reg.honest(world)
        dt = dt if dt is not None else self.reg.data.get("default_dt", {}).get(world)
        if dt is not None:
            found = [n for n, s in runs.items() if _same_number(s["dt_s"], dt)]
            return found[0] if found else None
        return next(iter(runs)) if len(runs) == 1 else None

    def touching(self, name, criterion):
        return [f for f in self.faults if f["run"] is None or (f["run"] == name and (
            f["item"] in IDENTITY_ITEMS or criterion in TOUCHES.get(f["item"], ())))]  # fmt: skip

    def note(self, what):
        if what not in self.unchecked:
            self.unchecked.append(what)


def identity(env):
    """Every value §11.1 fixes, in every run: the faults, each with its run (None for the top level) and item."""
    t, reg = env.table, env.reg

    def fault(run, item, why):
        env.faults.append(dict(run=run, item=item, why=why))

    if t.get("kind") != KIND_TABLE or t.get("protocol") != PROTOCOL:
        fault(None, 1, "kind or protocol")
    if t.get("units") != UNITS:
        fault(None, 1, "units")
    names = {reg.full(n) for n in reg.runs}
    runs, missing = t.get("runs") or {}, t.get("missing") or []
    for n in sorted((set(runs) | set(missing)) - names):
        fault(None, 1, f"{n} is not one of §3's runs")
    if set(runs) & set(missing) or len(set(missing)) != len(missing):
        fault(None, 1, "runs and missing are not disjoint, or missing names a run twice")
    sources = {}
    for name, spec in reg.runs.items():
        run = runs.get(reg.full(name))
        if run is None:
            continue
        if set(run) != ENTRY:
            fault(name, 2, f"entry keys {sorted(set(run) ^ ENTRY)}")
            continue
        sources[name] = run["source"]
        _identity_run(env, name, spec, run, lambda item, why, n=name: fault(n, item, why))
    for key in ("engine_revision", "snapshot", "external_modules"):
        if len({json.dumps(s.get(key), sort_keys=True) for s in sources.values()}) > 1:
            for name in sources:
                fault(name, 11, f"source.{key} is not the same in every run")
    plants = {n: r for n, r in runs.items() if isinstance(r, dict) and r.get("plant") is not None}
    if plants:
        try:
            rule = plant_rule(
                dict(runs={**{n: r for n, r in runs.items() if isinstance(r, dict)}}),
                env.exclusions,
            )
        except (KeyError, TypeError, StopIteration) as error:
            rule = dict(
                runs={
                    n: dict(departures=[f"the plant rule cannot be formed ({error})"])
                    for n in plants
                }
            )
        for full, result in rule["runs"].items():
            for why in result["departures"]:
                fault(full.removeprefix(reg.prefix), 13, f"against its honest run: {why}")
    return env.faults


def _identity_run(env, name, spec, run, fault):
    reg, world = env.reg, spec["world"]
    refusal, inputs, plant = run["refusal"], run["inputs"], run["plant"]
    parsed = inputs is not None
    if run["world"] != reg.full(world):
        fault(2, f"world {run['world']!r}")
    if (plant is None) != (spec["plant"] is None) or (
        plant is not None and plant.get("id") != spec["plant"]
    ):
        fault(2, "plant")
    if run["status"] not in ("completed", "refused") or (run["status"] == "completed") != (
        refusal is None
    ):
        fault(2, "status against refusal")
    if not (_is_number(run["dt_s"]) and _same_number(run["dt_s"], spec["dt_s"])):
        fault(2, f"dt_s {run['dt_s']!r}")
    if refusal is None:
        steps = run["rows"][-1]["step"] if run["rows"] else None
    else:
        steps = 0 if refusal.get("step") is None else refusal["step"] - 1
    if not (
        _is_number(run["steps"]) and run["steps"] == steps and float(run["steps"]).is_integer()
    ):
        fault(2, f"steps {run['steps']!r} for {steps!r}")
    if run["backend"] != "compiled":
        fault(2, "backend")
    if run["driver"] != {"window_steps": 1}:
        fault(14, "driver")
    if not re.fullmatch(r"[0-9a-f]{64}", str(run["record_sha256"])):
        fault(12, "record_sha256")
    src = run["source"] if isinstance(run["source"], dict) else {}
    if set(src) != set(SOURCE_TYPES) or any(
        not isinstance(src[k], kind) or (kind is int and isinstance(src[k], bool)) or src[k] in ("", None)
        for k, kind in SOURCE_TYPES.items() if k in src
    ):  # fmt: skip
        fault(11, "source keys or types")
    if src.get("checkout_dirty") is not False or src.get("jax_enable_x64") is not True or src.get(
            "jax_platforms") != "cpu":  # fmt: skip
        fault(11, "source: dirty, x64 or platform")
    if refusal is not None:
        kind, book = mapped(refusal)
        if refusal.get("kind") != kind or refusal.get("book") != book:
            fault(
                8,
                f"refusal {refusal.get('kind')}/{refusal.get('book')} for the mapping's {kind}/{book}",
            )
        if (refusal.get("step") is None) != (not parsed) or (refusal.get("time_s") is None) != (
            not parsed
        ):
            fault(8, "refusal step and time null exactly at parse")
    report = run["step_report"]
    if not parsed:
        if (
            run["definition"] is not None
            or run["checks"] is not None
            or run["operators"]
            or run["capacities"]
            or run["free_sites"]
            or run["rows"]
            or run["events"]
            or run["event_map"]
            or report is not None
        ):
            fault(3, "a run refused at parse holds more than its nulls")  # fmt: skip
        return
    if sorted(run["operators"]) != sorted(reg.data["operators"][world]):
        fault(9, f"operators {run['operators']}")
    _rows(reg, world, spec, run, inputs, steps, fault)
    sets = {s["id"]: s for s in inputs["sets"]}
    if set(run["capacities"]) != set(sets) or set(run["free_sites"]) != set(sets):
        fault(4, "capacities or free_sites: not every set")
    for sid, s in sets.items():
        want = (
            s["accessible_fraction"]
            * s["sites_per_copy"]
            * s["copies"]
            / inputs["constants"]["sites_per_fmol"]
        )
        got = run["capacities"].get(sid)
        if not (_is_number(got) and abs(got - want) <= 4 * EPS * abs(want)):
            fault(4, f"capacity of {sid}")
        if run["free_sites"].get(sid) not in ("state", "derived"):
            fault(4, f"free_sites of {sid}")
    _events(reg, world, spec["dt_s"], run, inputs, refusal, steps, fault)
    if (world == "W5") != (report is not None):
        fault(7, "step_report present exactly in W5's runs")
    if report is not None:
        if report.get("step") != 1 or not (_is_number(report.get("h_s")) and _same_number(
                report["h_s"], run["dt_s"] / 2)) or not (_is_number(report.get("limit")) and _same_number(
                report["limit"], 0.5)):  # fmt: skip
            fault(7, "step_report: step, h_s or limit")
        if spec["plant"] is None and not _limiting(report, inputs):
            fault(7, "max_load is not the set's summed free-site load, the largest (S2)")
    definition = run["definition"] or {}
    ex = definition.get("execution", {}) if isinstance(definition, dict) else {}
    if ex.get("solver") != SOLVER or not (_is_number(ex.get("dt")) and _same_number(ex["dt"], run["dt_s"])) or ex.get(
            "jit") is not True or ex.get("backend") != "cpu" or "energy_check" in ex:  # fmt: skip
        fault(13, "definition's literal fields")
    _record(env, name, spec, run, ex, fault)
    _echo(env, name, spec, run, fault)


def _limiting(report, inputs):
    """S2: max_load has kind L_R and id the set, sums both populations, and is the member of loads with the
    largest per_s."""
    loads = report.get("loads") or []
    if len(inputs["sets"]) != 1 or not loads or any(not _is_number(x.get("per_s")) for x in loads):
        return False
    sid = inputs["sets"][0]["id"]
    members = sorted(p["id"] for p in inputs["populations"] if p["set"] == sid)
    top = max(loads, key=lambda x: x["per_s"])
    return (report.get("max_load") == top and top["kind"] == "L_R" and top["id"] == sid
            and sorted(top["sums"]) == members and sum(x["per_s"] == top["per_s"] for x in loads) == 1)  # fmt: skip


def _rows(reg, world, spec, run, inputs, steps, fault):
    registered = reg.rows(world, spec["dt_s"])
    refused = run["refusal"] is not None
    want = [k for _, k in registered if not refused or k <= steps]
    got = [r.get("step") for r in run["rows"]]
    if got != want:
        fault(3, f"rows at steps {got[:6]}... for {want[:6]}...")
    times = {k: t for t, k in registered}
    nodes = [n["id"] for n in inputs["nodes"]]
    amounts = ({f"n:{lig}@{n}" for lig in inputs["ligands"] for n in nodes} | {f"R:{s['id']}" for s in inputs["sets"]}
               | {f"B:{p['id']}" for p in inputs["populations"]})  # fmt: skip
    wash = inputs.get("wash")
    records = {f"{lig}@{wash['node']}" for lig in inputs["ligands"]} if wash else set()
    pops = {p["id"] for p in inputs["populations"]}
    heat = set(reg.data["heat_nodes"][world])
    for row in run["rows"]:
        k, t = row.get("step"), times.get(row.get("step"))
        if set(row) != ROW_KEYS:
            fault(3, f"row {k}: keys")
            continue
        if t is not None and not (_is_number(row["time_s"]) and (
                row["time_s"] == 0.0 if k == 0 else abs(row["time_s"] - t) <= 1e-12 * t)):  # fmt: skip
            fault(3, f"row {k}: the clock")
        if set(row["amounts"]) != amounts or set(row["records"]) != records or any(
                set(v) != {"collected", "supplied"} for v in row["records"].values()):  # fmt: skip
            fault(3, f"row {k}: amounts or records not complete")
        if set(row["site_heat_pJ"]) != heat or set(row["site_occupied_fraction"]) != pops:
            fault(3, f"row {k}: site_heat_pJ or site_occupied_fraction not complete")


def _events(reg, world, dt, run, inputs, refusal, steps, fault):
    wash, events, entries = reg.data["wash"].get(world), run["events"], run["event_map"]
    if wash is None:
        if events or entries:
            fault(5 if events else 6, "an event or map entry in a world without a wash")
        return
    ws = reg.step(world, dt, wash["time_s"])
    if refusal is None:
        count = (1,)
    elif refusal.get("step") is None or refusal["step"] <= ws:
        count = (0,)
    else:  # A refusal at the wash's step may be the wash's own, or a check's at the wash row [Y2].
        count = (0, 1) if refusal["step"] == ws + 1 else (1,)
    if len(events) not in count:
        fault(5, f"{len(events)} events")
    for e in events:
        if (e.get("kind") != "wash" or e.get("operator") != WASH_ID or e.get("node") != inputs["wash"]["node"]
                or e.get("after_step") != ws):  # fmt: skip
            fault(5, "event: words, node or step")
        if not (
            _is_number(e.get("time_s"))
            and abs(e["time_s"] - wash["time_s"]) <= 1e-12 * wash["time_s"]
        ):
            fault(5, "event: the clock")
        if set(e.get("collected") or {}) != set(inputs["ligands"]) or set(e.get("supplied") or {}) != set(
                inputs["ligands"]):  # fmt: skip
            fault(5, "event: collected or supplied not complete")
    seen = [(m.get("state_step"), m.get("variant")) for m in entries]
    allowed = {
        (k, v)
        for k in (reg.step(world, dt, t) for t in reg.data["maps"][world])
        for v in ("numpy", "compiled")
        if refusal is None or k <= steps
    }
    if (
        len(seen) != len(set(seen))
        or not set(seen) <= allowed
        or (refusal is None and set(seen) != allowed)
    ):
        fault(6, f"event_map entries {sorted(seen, key=str)}")
    rows = {r.get("step"): r for r in run["rows"]}
    for m in entries:
        w = inputs["wash"]
        if m.get("node") != w["node"] or not _bits_equal(m.get("fraction"), w["fraction"]) or not _bits_equal(
                m.get("buffer_mM"), w["buffer_mM"]):  # fmt: skip
            fault(6, f"event_map at {m.get('state_step')}: parameters")
        row = rows.get(m.get("state_step"))
        if row is None or not _bits_equal(
            m.get("before"), dict(amounts=row["amounts"], records=row["records"])
        ):
            fault(
                6, f"event_map at {m.get('state_step')} ({m.get('variant')}): before is not its row"
            )


def _honest_of(reg, name, spec):
    if spec["plant"] is None:
        return name
    found = [n for n, s in reg.honest(spec["world"]).items()]
    return found[0] if len(found) == 1 else None


def _record(env, name, spec, run, ex, fault):
    """Item 13's execution record: the declared keys only, against the honest run's record (W1eq takes W1's)."""
    if env.record is None:
        env.note(
            "item 13: the execution record (§14.1) is not given; its declared keys are not compared"
        )
        return
    honest = _honest_of(env.reg, name, spec)
    key = "W1" if honest == "W1eq" else honest
    rec = env.record.get("runs", {}).get(key)
    if rec is None:
        fault(13, f"no execution record for {key}")
        return
    for k in ("solver", "dt", "jit", "backend", "field_solver"):
        if not _bits_equal(ex.get(k), rec["execution"].get(k)):
            fault(13, f"execution.{k} against the record")
    if "energy_check" in ex or not _bits_equal(ex.get("material_balance_atol_fmol"),
                                               rec["execution"].get("material_balance_atol_fmol")):  # fmt: skip
        fault(13, "energy_check or material_balance_atol_fmol against the record")


def _echo(env, name, spec, run, fault):
    """Item 10: the inputs echo against the expected-inputs file (TABLE §4.1, §12.2) [S5]."""
    if env.expected is None:
        env.note("item 10: no expected-inputs file is given")
        return
    honest = _honest_of(env.reg, name, spec)
    want = env.expected["runs"].get(honest)
    if want is None:
        fault(10, f"no expected inputs for {honest}")
        return
    changed = {}
    if spec["plant"] is not None:
        declared = (env.expected.get("plant_inputs_changed") or {}).get(name, {})
        for path in run["plant"].get("inputs_changed") or []:
            if path not in declared:
                fault(10, f"inputs_changed {path} is not a declared change")
            else:
                changed[path] = declared[path]
    start = None
    if spec["world"] == "W1eq":
        echo = (env.ref("W1eq") or {}).get("world", {})
        start = dict(populations=echo.get("populations", []),
                     free_amounts=[dict(a, n_fmol=a.get("n")) for a in echo.get("free_amounts", [])])  # fmt: skip
    extra = set(run["inputs"]["ligands"]) - set(want["ligands"]) if spec["world"] == "W7s" else ()
    addendum = None if env.addendum is None else env.addendum.get("runs", {}).get(honest)
    if env.addendum is None:
        env.note(
            "item 10: the host-entity addendum is not given; host volumes and host_values are not compared"
        )
    markers = (env.expected.get("host") or {}).get("markers") or {}
    result = Echo(markers, addendum, start, changed, extra).compare(run["inputs"], want)
    for why in result.departures[:8]:
        fault(10, f"inputs: {why}")
    for what in result.unchecked:
        env.note(f"item 10: {what.split(':')[0]}: the addendum's value")


# ------------------------------------------------------------------ the entries and their verdicts (TABLE §11)


def _row_at(env, world, name, run, t):
    """The row at a registered time t: its step is t's step in §5.1, its clock within 1e-12 t."""
    k = env.reg.step(world, env.reg.runs[name]["dt_s"], t)
    if k is None:
        raise KeyError(f"{t} is not a registered time of {world}")
    rows = [r for r in run["rows"] if r["step"] == k]
    if len(rows) != 1:
        raise KeyError(f"no single row at step {k}")
    row = rows[0]
    if (k == 0 and row["time_s"] != 0.0) or (k and abs(row["time_s"] - t) > 1e-12 * t):
        raise ValueError(f"the clock at step {k} departs")
    return row


def _facing(inputs):
    sets = {s["id"]: s["faces"] for s in inputs["sets"]}
    pops = {p["id"]: p["set"] for p in inputs["populations"]}
    return sets, pops


def at_node(row, node, inputs, names):
    """What G receives (TABLE §9, S3): the row's n: amounts at the node and the R: and B: amounts of the sets facing
    it, keeping only names that the reference's trajectory holds."""
    sets, pops = _facing(inputs)
    out = {}
    for key, value in row["amounts"].items():
        kind, what = key.split(":", 1)
        where = (
            what.split("@")[1] if kind == "n" else sets[what] if kind == "R" else sets[pops[what]]
        )
        if where == node and key in names:
            if value is None:
                raise TypeError(f"{key} is not finite")
            out[key] = value
    return out


def _band(e, value, tol):
    if not _is_number(e):
        return dict(unformed="the engine's value is not finite")
    ok = abs(e - value) <= tol
    return dict(passes=ok, fails=not ok, gap=abs(e - value), tolerance=tol)


def _derived(agreement, value, expected, tolerance):
    """agreement.judge_derived on one value: its expected value a scalar, its tolerance a float."""
    if not _is_number(value):
        return dict(unformed="the engine's value is not finite")
    return agreement.judge_derived([value], float(expected), float(tolerance))


def evaluate(env, world, pair, name, honest=True):
    """One pair's result on one run: {passes, fails, ...}, {unformed: why} or {fault: [...]} (TABLE §11, §11.2)."""
    run = env.run(name)
    if run is None:
        return dict(unformed="the run is missing")
    hit = env.touching(name, pair["criterion"])
    if hit:
        return dict(fault=[f"item {f['item']}: {f['why']}" for f in hit[:3]])
    if honest and run["refusal"] is not None and mapped(run["refusal"])[0] == "harness":
        return dict(unformed="a harness refusal fails every criterion that reads the run [S9]")
    try:
        return _value(env, world, pair, name, run)
    except (KeyError, IndexError, StopIteration, TypeError, ValueError, ZeroDivisionError) as error:
        return dict(unformed=f"{type(error).__name__}: {error}")


def _value(env, world, pair, name, run):
    crit, obs, A = pair["criterion"], pair["observable"], env.agreement
    inputs = run["inputs"]
    if crit == "C7":
        return _c7(run)
    if inputs is None:
        return dict(unformed="refused before parse")
    kind, what = obs.split(":", 1)
    if crit in ("C1", "C2a", "C2b", "C8"):
        e = _row_at(env, world, name, run, pair["time_s"])["amounts"][obs]
        if crit == "C2b":
            return _derived(A, e, pair["value"], pair["tolerance"])
        return _band(e, pair["value"], pair["tolerance"])
    if crit in ("C3a", "C3b", "C3c"):
        r0, r1 = (_row_at(env, world, name, run, pair[k]) for k in ("start_s", "end_s"))
        h0, h1 = r0["site_heat_pJ"][what], r1["site_heat_pJ"][what]
        if not (_is_number(h0) and _is_number(h1)):
            return dict(unformed="a heat is not finite")
        if crit == "C3a":
            return _band(h1 - h0, pair["value"], pair["tolerance"])
        if (
            crit == "C3c"
        ):  # One-sided [5c]: the fall max(H_k - H_k+1, 0) against 0.0 within the file's tolerance.
            return _derived(A, max(h0 - h1, 0.0), 0.0, pair["tolerance"])
        ref = env.ref(world)
        names = {x["observable"] for x in ref["trajectory"]} | {
            x["observable"] for x in ref["world"]["start"]
        }
        # G as the plan writes it, G(world, node, amounts): the world by its registered name, since G's module
        # knows the worlds by name (RULINGS-2 Q4a: W1p and W3p among them); the amounts at the node by name (S3).
        g0 = env.G(world, what, at_node(r0, what, inputs, names))
        g1 = env.G(world, what, at_node(r1, what, inputs, names))
        return _derived(A, h1 - h0, float(g0 - g1), pair["tolerance"])
    sets, pops = _facing(inputs)
    if crit in ("C4a", "C5", "C9"):
        row = _row_at(env, world, name, run, pair["time_s"])
        a = row["amounts"]
        if crit == "C4a":
            ligand, node = what.split("@")
            bound = [
                a[f"B:{p['id']}"]
                for p in inputs["populations"]
                if p["ligand"] == ligand and sets[p["set"]] == node
            ]
            rec = row["records"].get(f"{ligand}@{node}", dict(collected=0.0, supplied=0.0))
            books = a[f"n:{ligand}@{node}"] + sum(bound) + rec["collected"] - rec["supplied"]
            return _derived(A, books, pair["value"], pair["tolerance"])
        if crit == "C5":
            sites = a[f"R:{what}"] + sum(a[f"B:{p}"] for p, s in pops.items() if s == what)
            return _derived(A, sites, pair["value"], pair["tolerance"])
        s = pops[what]
        S = run["capacities"][s]
        moiety = abs(a[f"R:{s}"] + sum(a[f"B:{p}"] for p, ps in pops.items() if ps == s) - S) / S
        tol = pair["tolerance_terms"]["eps_term"] + moiety
        return _derived(A, row["site_occupied_fraction"][what], a[f"B:{what}"] / S, tol)
    if crit in ("C4b", "C6"):
        k = env.reg.step(world, env.reg.runs[name]["dt_s"], pair["time_s"])
        entries = [m for m in run["event_map"] if m["state_step"] == k]
        if k is None or sorted(m["variant"] for m in entries) != ["compiled", "numpy"]:
            return dict(unformed=f"the event map at step {k} lacks a variant [4b]")
        variants = {m["variant"]: _map_pair(pair, m, inputs, A) for m in entries}
        if any("unformed" in v for v in variants.values()):
            return dict(unformed="a variant cannot be formed", variants=variants)
        ok = all(v["passes"] for v in variants.values())
        fails = all(v["fails"] for v in variants.values()) if crit == "C6" else not ok
        return dict(passes=ok, fails=fails, variants=variants)
    if crit == "C4c":
        if len(run["events"]) != 1:
            return dict(unformed="not exactly one event")
        record = run["events"][0]["collected" if kind == "removed" else "supplied"]
        return _band(record[what.split("@")[0]], pair["value"], pair["tolerance"])
    return dict(unformed=f"no rule for {crit} {obs}")


def _map_pair(pair, entry, inputs, A):
    """C4b's and C6's pair on one variant's map entry (TABLE §6, §11 [5d])."""
    obs, tt = pair["observable"], pair.get("tolerance_terms") or {}
    kind, what = obs.split(":", 1)
    before, after = entry["before"], entry["after"]
    if pair["criterion"] == "C6":
        b, a = before["amounts"][obs], after["amounts"][obs]
        if not (_is_number(a) and _is_number(b)):
            return dict(unformed="not finite")
        return A.judge_constant([a], b)
    ligand, node = what.split("@")
    n = before["amounts"][f"n:{ligand}@{node}"]
    f = entry["fraction"]
    if kind == "n":
        volume = next(x["volume_pL"] for x in inputs["nodes"] if x["id"] == node)
        expected = (1.0 - f) * n + f * volume * entry["buffer_mM"][ligand]
        anchor = next(
            x["n_fmol"]
            for x in inputs["free_amounts"]
            if x["ligand"] == ligand and x["node"] == node
        )
        tol = tt["eps_factor"] * (abs(anchor) + abs(n) + tt["f_V_c_buf"])
        return _derived(A, after["amounts"][obs], expected, tol)
    key = f"{ligand}@{node}"
    record = "collected" if kind == "removed" else "supplied"
    value = after["records"][key][record] - before["records"][key][record]
    if kind == "removed":
        return _derived(A, value, f * n, tt["eps_factor"] * f * abs(n))
    return _derived(A, value, pair["value"], pair["tolerance"])


def _c7(run):
    """C7 (TABLE §7): refused by the stage condition at step 1, nothing after the start, its report's verdict
    refused and its own h max L above 1/2 (never its `limit`)."""
    refusal, report = run["refusal"], run["step_report"]
    ok = (run["status"] == "refused" and refusal is not None and mapped(refusal)[0] == "stage"
          and refusal.get("step") == 1 and report is not None and report.get("verdict") == "refused"
          and _is_number(report.get("h_max_load")) and report["h_max_load"] > 0.5
          and [r["step"] for r in run["rows"]] == [0])  # fmt: skip
    return dict(passes=ok, fails=not ok)


def _c10(env, name):
    """C10 (TABLE §4, §11): the honest run completes, holds every registered row, and its checks are present, hold
    every check listed for its world, and record no failure. A missing run does not complete [11a]."""
    run = env.run(name)
    if run is None:
        return dict(passes=False, fails=True, why="missing")
    hit = env.touching(name, "C10")
    if hit:
        return dict(fault=[f"item {f['item']}: {f['why']}" for f in hit[:3]])
    spec = env.reg.runs[name]
    if run["status"] != "completed" or run["checks"] is None:
        return dict(passes=False, fails=True, why=f"status {run['status']}")
    if env.checks is None:
        env.note(
            "C10: the list of checks (§14.1 item 2) is not given; the run's own checks are read"
        )
        listed = set(run["checks"])
    else:
        listed = set(env.checks.get(spec["world"], []))
    clean = listed <= set(run["checks"]) and all(not c["failures"] for c in run["checks"].values())
    rows = [r["step"] for r in run["rows"]] == [
        k for _, k in env.reg.rows(spec["world"], spec["dt_s"])
    ]
    ok = clean and rows
    return dict(passes=ok, fails=not ok, why=None if ok else "checks" if not clean else "rows")


def s_node(observable, ref):
    """s_node (CRITERIA:50-52): the largest |reference value| of any amount at the observable's facing node, over
    the start and the observation times."""
    echo = ref["world"]
    faces = {s["id"]: s["faces"] for s in echo["sets"]}
    of = {p["id"]: p.get("set") for p in echo["populations"]}

    def node(obs):
        kind, name = obs.split(":", 1)
        return (
            name.split("@")[1]
            if kind == "n"
            else faces.get(name)
            if kind == "R"
            else faces.get(of.get(name))
        )

    where = node(observable)
    values = [abs(x["value"]) for x in [*echo.get("start", []), *ref.get("trajectory", [])]
              if node(x["observable"]) == where]  # fmt: skip
    return max(values) if values else 0.0


def inconclusive(pair, ref):
    """The references' own convergence (CRITERIA:41-44): R-ode's two tolerances differ at the pair by more than
    1e-10 of its scale (s_node for an amount; S for C8; E for a heat, taken as |G| at both ends, no larger than E)."""
    crit, obs = pair["criterion"], pair["observable"]
    gaps = {(x["observable"], x["time_s"]): x["tolerance_gap"] for x in ref.get("trajectory", [])}
    if crit == "C1":
        gap = gaps.get((obs, pair["time_s"]))
        return gap is not None and gap > 1e-10 * s_node(obs, ref)
    if crit == "C8" and not obs.startswith("ratio:"):
        gap = gaps.get((obs, pair["time_s"]))
        return gap is not None and gap > 1e-10 * pair["scale"]
    if crit == "C8":
        return any(
            inconclusive(p, ref) for p in ref["pairs"] if p["criterion"] == "C8" and "scale" in p
        )
    if crit == "C4c" and obs.startswith("removed:"):
        what = obs.split(":", 1)[1]
        gap = gaps.get((f"n:{what}", pair["time_s"]))
        return gap is not None and gap > 1e-10 * s_node(f"n:{what}", ref)
    if crit == "C3a":
        node = obs.split(":", 1)[1]
        G = {(x["node"], x["time_s"]): x["G"] for x in ref.get("heats", {}).get("G", [])}
        for x in ref.get("heats", {}).get("intervals", []):
            if (x["node"], x["start_s"], x["end_s"]) == (node, pair["start_s"], pair["end_s"]):
                scale = abs(G.get((node, x["start_s"]), 0.0)) + abs(G.get((node, x["end_s"]), 0.0))
                return x["tolerance_gap"] > 1e-10 * scale
    return False


def entries(env):
    """Every compared entry, from the registration and the reference files' pairs (TABLE §11) [B2]: each world's
    pairs (W3p's from W3's file at its own times, C1 and C5 only), C10 for every honest run but W5's, and C8's
    ratios. Each entry counts toward its criterion unless it is a plant's baseline only (TABLE §3)."""
    out = []
    for world in env.reg.data["rows"]:
        ref = env.ref(world)
        if ref is None:
            continue
        own = env.reg.data["files"][world] == world
        times = {t for d in env.reg.dts(world) for t, _ in env.reg.rows(world, d)}
        for pair in ref["pairs"]:
            crit = pair["criterion"]
            if crit == "C10" or (crit == "C8" and (pair.get("tolerance") is None)):
                continue
            if not own and (crit not in ("C1", "C5") or pair.get("time_s") not in times):
                continue
            key = (world, crit, pair["observable"], pair.get("time_s"), pair.get("start_s"), pair.get("end_s"),
                   pair.get("dt_s"))  # fmt: skip
            name = env.honest_name(world, pair.get("dt_s"))
            out.append(
                dict(
                    key=key,
                    world=world,
                    pair=pair,
                    run=name,
                    counts=(world, crit) not in BASELINE_ONLY,
                )
            )
    return out


def c8_ratios(env):
    """C8 (TABLE §11) [item 3]: e(dt) = max |y_e - y_ref| / scale over R and the B_b at W4's times, each dt's run;
    each ratio entry against the file's minimum."""
    ref = env.ref("W4") if "W4" in env.reg.data["rows"] else None
    if ref is None:
        return []
    errors, broken = {}, set()
    for p in ref["pairs"]:
        if p["criterion"] != "C8" or p["observable"].startswith("ratio:"):
            continue
        name = env.honest_name("W4", p["dt_s"])
        run = env.run(name) if name else None
        try:
            if run is None or env.touching(name, "C8"):
                raise KeyError("missing or touched by a fault")
            e = _row_at(env, "W4", name, run, p["time_s"])["amounts"][p["observable"]]
            errors[p["dt_s"]] = max(errors.get(p["dt_s"], 0.0), abs(e - p["value"]) / p["scale"])
        except (KeyError, TypeError, ValueError):
            broken.add(p["dt_s"])
    out = []
    for p in ref["pairs"]:
        if p["criterion"] != "C8" or not p["observable"].startswith("ratio:"):
            continue
        a, b = (float(x) for x in re.findall(r"e\(([^)]+)\)", p["observable"]))
        key = ("W4", "C8", p["observable"], None, None, None, None)
        if inconclusive(p, ref):
            out.append(
                dict(
                    key=key,
                    world="W4",
                    pair=p,
                    run=None,
                    counts=True,
                    result=dict(inconclusive=True),
                )
            )
        elif {a, b} & broken or a not in errors or b not in errors or errors[b] == 0.0:
            out.append(dict(key=key, world="W4", pair=p, run=None, counts=True,
                            result=dict(unformed="an e(dt) cannot be formed")))  # fmt: skip
        else:
            ratio = errors[a] / errors[b]
            ok = ratio >= p["minimum"]
            out.append(dict(key=key, world="W4", pair=p, run=None, counts=True,
                            result=dict(passes=ok, fails=not ok, ratio=ratio, e=dict(errors))))  # fmt: skip
    return out


def judge_entries(env):
    """Every entry's result on its honest run."""
    out = []
    for entry in entries(env):
        ref = env.ref(entry["world"])
        if inconclusive(entry["pair"], ref):
            entry["result"] = dict(inconclusive=True)
        elif entry["run"] is None:
            entry["result"] = dict(unformed="no registered run for this pair's dt")
        else:
            entry["result"] = evaluate(env, entry["world"], entry["pair"], entry["run"])
        out.append(entry)
    for name, spec in env.reg.honest().items():
        if spec["world"] == "W5":
            continue
        key = (spec["world"], "C10", "run", None, None, None, spec["dt_s"])
        out.append(
            dict(
                key=key,
                world=spec["world"],
                pair=None,
                run=name,
                counts=True,
                result=_c10(env, name),
            )
        )
    out.extend(c8_ratios(env))
    return out


def summarize(results):
    """{criterion: its verdict and counts}: a criterion passes only when every entry passes; an entry missing, not
    formed or touched by a fault fails it (§11.2); inconclusive only from the references' convergence."""
    out = {
        c: dict(entries=0, passed=0, failed=0, unformed=0, faulted=0, inconclusive=0, first=[])
        for c in CRITERIA
    }
    for entry in results:
        if not entry["counts"]:
            continue
        state, result = out[entry["key"][1]], entry["result"]
        state["entries"] += 1
        bad = None
        if result.get("inconclusive"):
            state["inconclusive"] += 1
        elif "fault" in result:
            state["faulted"] += 1
            bad = result["fault"]
        elif "unformed" in result:
            state["unformed"] += 1
            bad = result["unformed"]
        elif result.get("passes") is True:
            state["passed"] += 1
        else:
            state["failed"] += 1
            bad = {
                k: v
                for k, v in result.items()
                if k in ("gap", "largest_gap", "tolerance", "ratio", "why")
            }
        if bad is not None and len(state["first"]) < 5:
            state["first"].append(
                [str(x) for x in entry["key"]] + [json.dumps(bad, default=str)[:300]]
            )
    for state in out.values():
        failing = state["failed"] + state["unformed"] + state["faulted"]
        state["verdict"] = ("fail" if failing or not state["entries"] else
                            "inconclusive" if state["inconclusive"] else "pass")  # fmt: skip
    return out


# ------------------------------------------------------------------ the plants (TABLE §8.2)


def _plant_pairs(env, world, crit, time_s):
    """The pairs of one plant entry (plant, criterion, world, time_s): its world's pairs of that criterion, at that
    time when it names one; W3p's from W3's file at its own times."""
    ref = env.ref(world)
    if ref is None:
        return []
    own = env.reg.data["files"][world] == world
    times = {t for d in env.reg.dts(world) for t, _ in env.reg.rows(world, d)}
    return [p for p in ref["pairs"] if p["criterion"] == crit and (time_s is None or p.get("time_s") == time_s)
            and (own or p.get("time_s") in times)]  # fmt: skip


def _refusal_catch(env, plant, name, honest):
    """P-c: a refusal of kind `check` by the judge's mapping, by the book the plant's row names (any book where it
    names none), untouched by a fault, with the honest run completed [P-d]: completed as the registered world, so a
    fault of its identity, or of its status and refusal, leaves no baseline (§11.2, the stricter reading). Never
    P4's."""
    run = env.run(name)
    if plant == "P4" or run is None or run["refusal"] is None:
        return False, None
    kind, book = mapped(run["refusal"])
    if kind != "check" or (plant in ROW_BOOK and book != ROW_BOOK[plant]):
        return (
            False,
            f"refused by {kind}{'' if book is None else ': ' + book}, which does not catch it",
        )
    if env.touching(name, "refusal"):
        return False, "its refusal is touched by a fault"
    base = env.run(honest) if honest else None
    if base is None or base["status"] != "completed":
        return False, "the honest run did not complete"
    if env.touching(honest, "C10"):
        return False, "the honest run is touched by a fault, so it gives no baseline"
    return True, f"refused by its own {book}"


def judge_plants(env):
    """{plant: caught, its runs, its entries and baselines} by TABLE §8.2 [P-a to P-d, reading 2]."""
    out = {}
    for plant, crit, world, time_s in env.reg.plants:
        name = f"{world}-{plant}"
        honest = env.honest_name(world)
        state = out.setdefault(plant, dict(entries=[], runs={}))
        state["runs"].setdefault(name, None)
        run = env.run(name)
        row = dict(run=name, criterion=crit, time_s=time_s)
        if run is None:
            state["entries"].append(dict(row, caught=False, why="no run"))
            continue
        if (
            crit == "C7"
        ):  # P4: by `verdict` "admitted" alone; its entry is the whole report [W14, W-i].
            report = run["step_report"]
            formed = report is not None and not _has_null(report) and not env.touching(name, "C7")
            base = evaluate(env, world, dict(criterion="C7", observable="stage:first_step"), honest)
            caught = formed and report.get("verdict") == "admitted" and base.get("passes") is True
            why = ("caught" if caught else "its baseline fails" if formed and report.get("verdict") == "admitted"
                   else "not admitted, or its report cannot be formed")  # fmt: skip
            state["entries"].append(
                dict(row, caught=caught, why=why, baseline=base.get("passes") is True)
            )
            continue
        if crit == "C10":  # P8: by its own ledger's refusal alone.
            state["entries"].append(
                dict(row, caught=False, why="P8 is caught by its own ledger's refusal only")
            )
            continue
        pairs = _plant_pairs(env, world, crit, time_s)
        failed, baseline, failing = False, bool(pairs), []
        for pair in pairs:
            planted = evaluate(env, world, pair, name, honest=False)
            base = evaluate(env, world, pair, honest) if honest else dict(unformed="no honest run")
            if base.get("passes") is not True:
                baseline = False
                failing.append(
                    [pair["observable"], pair.get("time_s"), json.dumps(base, default=str)[:200]]
                )
            if (
                planted.get("fails") is True
                and "unformed" not in planted
                and "fault" not in planted
            ):
                failed = True
        caught = failed and baseline
        why = "caught" if caught else "its baseline fails" if failed else "no formed pair fails"
        state["entries"].append(
            dict(row, caught=caught, why=why, baseline=baseline, baseline_failures=failing[:3])
        )
    for plant, state in out.items():
        for name in state["runs"]:
            world = name.rsplit("-", 1)[0]
            by_refusal, why = _refusal_catch(env, plant, name, env.honest_name(world))
            mine = [e for e in state["entries"] if e["run"] == name]
            needed = CAUGHT_BY[plant]
            crits = {c: all(e["caught"] for e in mine if e["criterion"] == c) and any(e["criterion"] == c for e in mine)
                     for c in needed}  # fmt: skip
            by_entries = bool(needed) and (
                all(crits.values()) if plant in NEEDS_ALL else any(crits.values())
            )
            if plant == "P8":
                by_entries = False
            state["runs"][name] = dict(caught=by_refusal or by_entries, refusal=why, criteria=crits)
        state["caught"] = bool(state["runs"]) and all(r["caught"] for r in state["runs"].values())
    return out


def judge(env):
    """The judgement (TABLE §11, §8.2): the identity faults, every entry, the criteria, the plants."""
    identity(env)
    results = judge_entries(env)
    criteria = summarize(results)
    plants = judge_plants(env)
    derived = sorted(f"{n}:{s}" for n, r in (env.table.get("runs") or {}).items() if isinstance(r, dict)
                     for s, w in (r.get("free_sites") or {}).items() if w == "derived")  # fmt: skip
    fails = [c for c, s in criteria.items() if s["verdict"] == "fail"]
    loose = [p for p, s in plants.items() if not s["caught"]]
    unsure = [c for c, s in criteria.items() if s["verdict"] == "inconclusive"]
    overall = "fail" if fails or loose else "inconclusive" if unsure else "pass"
    return dict(overall=overall, criteria={c: s["verdict"] for c, s in criteria.items()},
                plants={p: s["caught"] for p, s in plants.items()}, failing_criteria=fails, plants_not_caught=loose,
                derived_sets=derived, faults=env.faults, unchecked=env.unchecked, criteria_detail=criteria,
                plants_detail=plants, entries=len(results))  # fmt: skip


# ------------------------------------------------------------------ the judged run's order (TABLE §12.3)


def run_judgement(args):
    """§12.3's steps 1 to 3 and 7: the blobs, the references' structure, the cross-check, the table's sha256, and
    then the judgement. A departure at steps 1, 3 or 7 stops the judge before anything is scored."""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    folder = Path(args.references)
    invented = args.registration is not None
    reg = (
        Registration(strict_load(args.registration), prefix="INVENTED-")
        if invented
        else Registration(REGISTERED)
    )
    agreement_path = Path(
        args.agreement
        or Path(__file__).resolve().parents[1] / "assembly_lineages_v2" / "agreement.py"
    )
    verdict = dict(kind="fr45 judgement, version 1", invented=invented, stopped=None)

    def write(code):
        (out / "verdict.json").write_text(json.dumps(verdict, indent=1, default=str) + "\n")
        keys = ("overall", "stopped", "scope", "criteria", "plants", "derived_sets", "unchecked")
        brief = {k: verdict.get(k) for k in keys}
        brief["references_structure"] = len(verdict.get("references_structure") or [])
        brief["invented_file_structure"] = verdict.get("invented_file_structure")
        brief["faults"] = len(verdict.get("faults") or [])
        print(json.dumps(brief, indent=1, default=str))
        return code

    if (
        not invented
    ):  # A registered judgement has every input it owes, or it scores nothing (§1, §14.1, S14).
        owed = [flag for flag, value in (("--repo", args.repo), ("--tag", args.tag)) if not value]
        if args.table:
            owed += [flag for flag, value in (
                ("--table-sha256", args.table_sha256), ("--sample-sha256", args.sample_sha256),
                ("--addendum", args.addendum), ("--execution-record", args.execution_record),
                ("--checks-list", args.checks_list)) if not value]  # fmt: skip
        if owed:
            verdict["stopped"] = f"a registered judgement needs {', '.join(owed)}"
            return write(2)
    if args.tag:  # Step 1 [S14]: the snapshot's reference files and agreement.py against the binding tag's blobs.
        files = {f"validation/fr45/references/{p.relative_to(folder).as_posix()}": p for p in sorted(folder.rglob("*"))
                 if p.is_file() and "__pycache__" not in p.parts}  # fmt: skip
        files["validation/assembly_lineages_v2/agreement.py"] = agreement_path
        found = {k: git_blob(v.read_bytes()) for k, v in files.items()}
        tagged = tag_blobs(args.repo, args.tag, ["validation/fr45/references",
                                                 "validation/assembly_lineages_v2/agreement.py"])  # fmt: skip
        departures = check_blobs(found, tagged)
        verdict["blobs"] = dict(tag=args.tag, files=len(found), departures=departures)
        if departures:
            verdict["stopped"] = (
                "the snapshot's references or agreement.py depart from the binding tag (S14)"
            )
            return write(2)
    else:
        verdict["blobs"] = "not checked: an invented rehearsal"
    sample = (
        folder / "format_sample_INVENTED.json"
    )  # The file the judge reads first (the plan's step 2).
    if sample.exists():
        verdict["invented_file_structure"] = invented_file_structure(strict_load(sample))
    elif not invented:
        verdict["stopped"] = "the references' format_sample_INVENTED.json is missing"
        return write(2)
    refs = {}
    for world in sorted(set(reg.data["files"].values())):
        path = folder / "outputs" / f"reference_{world}.json"
        if path.exists():
            refs[world] = strict_load(path)
    verdict["references_structure"] = reference_structure(refs, reg, invented)  # Step 2 [12b].
    expected = strict_load(args.expected)
    verdict["cross_check"] = cross_check(expected, refs, reg)  # Step 3 [S5].
    if verdict["cross_check"]:
        verdict["stopped"] = "the expected-inputs file departs from the references' echo (S5)"
        return write(2)
    if not args.table:  # §12.3's steps 1 to 3 come before any registered run, so before any table.
        verdict["scope"] = (
            "§12.3 steps 1 to 3 only: the blobs, the references' structure, the cross-check"
        )
        findings = verdict["references_structure"] or verdict.get("invented_file_structure")
        return write(1 if findings else 0)
    digest, departures = table_sha256(
        args.table, args.table_sha256, args.sample_sha256
    )  # Step 7 (§1).
    verdict["table_sha256"] = digest
    if departures:
        verdict.update(stopped="the table's sha256 (§1)", table_departures=departures)
        return write(2)
    table = strict_load(Path(args.table) / "table.json")
    sys.dont_write_bytecode = True
    sys.path.insert(
        0, str(folder)
    )  # The references' G, called as the plan says (ruling 6); never its source.
    import importlib

    G = importlib.import_module("fr45ref_free_energy").G
    agreement = load_by_path("fr45_agreement", agreement_path)
    extra = {k: (strict_load(v) if v else None) for k, v in (("addendum", args.addendum), (
        "record", args.execution_record), ("checks", args.checks_list))}  # fmt: skip
    env = Env(table, refs, reg, agreement, G, expected=expected, exclusions=args.exclude, **extra)
    verdict.update(judge(env))
    return write(0 if verdict["overall"] == "pass" else 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("compare")
    c.add_argument("table")
    c.add_argument("sample")
    c.add_argument("out", nargs="?")
    st = sub.add_parser("structure")
    st.add_argument("table")
    st.add_argument("out", nargs="?")
    r = sub.add_parser("plant-rule")
    r.add_argument("table")
    r.add_argument("out", nargs="?")
    r.add_argument("--exclude", nargs="*", default=[])
    j = sub.add_parser("judge")
    j.add_argument(
        "--table",
        help="the table/ folder: table.json and SHA256SUMS; without it, steps 1 to 3 only",
    )
    j.add_argument("--references", required=True, help="the snapshot's validation/fr45/references")
    j.add_argument("--expected", required=True, help="validation/fr45/spec/expected_inputs.json")
    j.add_argument("--out", required=True)
    j.add_argument(
        "--registration", help="an invented registration (the rehearsal); never at the judged run"
    )
    j.add_argument("--repo", help="the checkout holding the binding tag")
    j.add_argument("--tag", help="the binding tag (S14)")
    j.add_argument("--agreement", help="agreement.py (default: the snapshot's)")
    j.add_argument("--table-sha256", help="the lead's record of the table's sha256")
    j.add_argument("--sample-sha256", help="the format sample's table sha256")
    j.add_argument("--addendum", help="the host-entity addendum (§14.1 item 6)")
    j.add_argument("--execution-record", help="the execution record (§14.1)")
    j.add_argument(
        "--checks-list", help="the list of ledgers and host checks by world (§14.1 item 2)"
    )
    j.add_argument(
        "--exclude", nargs="*", default=[], help="the execution record's excluded definition paths"
    )
    args = parser.parse_args(argv)
    if args.command == "judge":
        return run_judgement(args)
    table = json.loads(Path(args.table).read_text())
    if args.command == "compare":
        result = compare(table, json.loads(Path(args.sample).read_text()))
        ok = result["identical"]
    elif args.command == "structure":
        faults, found = structure(table)
        result, ok = dict(faults=faults, kinds=found), not faults
    else:
        result = plant_rule(table, args.exclude)
        ok = result["departures"] == 0
    text = json.dumps(result, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text[:4000])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
