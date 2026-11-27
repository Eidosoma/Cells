"""FR-45's judge (validation/fr45/spec/TABLE.md §11, §12.3), to RULINGS-2's import rules: the standard library and
NumPy only; nothing from src/, nothing of the builder's driver or exporter.

This first part holds §12.3 step 5's two checks, which come before any registered run:
- `compare`: a table's structure against the format sample's, key by key and type by type (TABLE §12.1). Every
  path is reduced to a pattern (data keys as `<key>`, list members as `[]`); the comparison finds the patterns
  one side lacks and the types the sample does not show. `definition` is compared as an object only ("not listed
  further"), and the top level's `INVENTED` is skipped. No number, length, order or equality is compared.
- `plant_rule`: each plant run against its honest twin (TABLE §4, §8.1, §11.1): its world, dt_s, backend and
  operators equal; its inputs and definition equal after the plant's declared inputs_changed (B6) is applied, the
  execution record's excluded fields left out.

Usage:
  python -B -m validation.fr45.judge compare TABLE_JSON SAMPLE_JSON [OUT_JSON]
  python -B -m validation.fr45.judge plant-rule TABLE_JSON [OUT_JSON] [--exclude PATH ...]
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
OPAQUE = re.compile(r"^runs\.<key>\.definition$")  # The engine's own form: an object, not listed further.


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
                keysets.setdefault(path, set()).add(frozenset(k for k in value if path or k != "INVENTED"))
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
        if run["status"] not in ("completed", "refused") or (run["status"] == "completed") != (refusal is None):
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
            if event.get("kind") != "wash" or event.get("operator") != "cells.operator.scheduled_compartment_wash@1":
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
            if not parsed and (refusal.get("step") is not None or refusal.get("time_s") is not None):
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
B6_DEFINITION = {"k_off": "dissociation_rate_per_s"}  # P2's declared change, where it sits in `definition`.


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
                departures.append(f"definition: the B6 paths cannot be applied ({type(error).__name__})")
            else:
                if _drop(expected, exclusions) != _drop(run["definition"], exclusions):
                    departures.append("definition")
        out[name] = dict(twin=twin, formed=True, inputs_changed=list(changed), departures=departures)
    return dict(departures=sum(len(r["departures"]) for r in out.values()), runs=out)


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
    args = parser.parse_args(argv)
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
