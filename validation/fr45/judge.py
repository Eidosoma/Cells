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


# ------------------------------------------------------------------ the judgement (TABLE §11, §8.2)

EPS = 2.0**-52
WORD_CONSTANTS = ("refused", "completes", "unchanged")
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


def git_blob(data):
    """The git blob SHA-1 of a file's bytes (the judge's S14 check)."""
    import hashlib

    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def check_blobs(files, expected):
    """{path: (found, expected)} of every file whose blob departs from the binding tag's (S14); empty when all
    agree. `files` maps a name to its path; `expected` maps the same names to their tag blobs."""
    out = {}
    for name, path in files.items():
        found = git_blob(Path(path).read_bytes())
        if found != expected.get(name):
            out[name] = (found, expected.get(name))
    return out


def load_by_path(name, path):
    """A module loaded from its file alone (importlib.util), so no package's __init__ is imported."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _step(t, dt):
    return int(round(t / dt))


def _row(run, t):
    """(row, why): the row whose step is t's step, its clock within 1e-12 t (TABLE §5.1)."""
    k = _step(t, run["dt_s"])
    rows = [r for r in run["rows"] if r["step"] == k]
    if len(rows) != 1:
        return None, f"no single row at step {k}"
    row = rows[0]
    if (k == 0 and row["time_s"] != 0.0) or (k and abs(row["time_s"] - t) > 1e-12 * t):
        return None, f"the clock at step {k} departs"
    return row, None


class Context:
    """One world's judgement inputs: its reference file, its honest runs and the table's plant runs."""

    def __init__(self, table, world, reference, prefix=""):
        self.table, self.world, self.ref, self.prefix = table, world, reference, prefix
        runs = table["runs"]
        self.honest = {
            r["dt_s"]: (n, r)
            for n, r in runs.items()
            if r["world"] == prefix + world and r["plant"] is None
        }
        echo = reference["world"]
        self.dt = echo["dt"] if isinstance(echo["dt"], list) else [echo["dt"]]

    def run(self, pair):
        """(name, run) of the honest run a pair reads: by its dt_s, else the world's one run."""
        dt = pair.get("dt_s")
        if dt is not None and dt in self.honest:
            return self.honest[dt]
        if len(self.honest) == 1:
            return next(iter(self.honest.values()))
        return self.honest.get(self.dt[0], (None, None))


def _facing(inputs):
    """{observable prefix -> node}: each set's and population's facing compartment, from the run's echo."""
    sets = {s["id"]: s["faces"] for s in inputs["sets"]}
    pops = {p["id"]: p["set"] for p in inputs["populations"]}
    return sets, pops


def at_node(row, node, inputs):
    """The row's amounts at one node, as §9 names them, for the references' G (TABLE §5.2, S3)."""
    sets, pops = _facing(inputs)
    out = {}
    for key, value in row["amounts"].items():
        kind, name = key.split(":", 1)
        where = (
            name.split("@")[1] if kind == "n" else sets[name] if kind == "R" else sets[pops[name]]
        )
        if where == node:
            out[key] = value
    return out


def _band(e, ref, tol):
    ok = e is not None and ref is not None and tol is not None and abs(e - ref) <= tol
    return dict(
        passes=bool(ok), fails=not ok, gap=None if e is None or ref is None else abs(e - ref)
    )


def evaluate(pair, ctx, agreement, G, run=None):
    """One pair's verdict on a run (the world's honest run by default): {passes, fails, ...}, or {unformed: why}."""
    crit, obs = pair["criterion"], pair["observable"]
    name, run = (None, run) if run is not None else ctx.run(pair)
    if run is None:
        return dict(unformed="no run")
    inputs = run["inputs"]
    if inputs is None and crit not in ("C7", "C10"):
        return dict(unformed="refused before parse")
    kind = obs.split(":", 1)[0]
    try:
        if crit in ("C1", "C2a", "C2b", "C8") and kind in ("n", "R", "B"):
            t = pair["time_s"] if crit != "C2a" else ctx.ref["world"]["horizon"]
            row, why = _row(run, t)
            if row is None:
                return dict(unformed=why)
            e = row["amounts"].get(obs)
            if crit == "C2b":
                return agreement.judge_derived([e], [pair["value"]], pair["tolerance"])
            if crit == "C8" and pair["tolerance"] is None:
                return dict(passes=True, fails=False, information=True, e=e)
            return _band(e, pair["value"], pair["tolerance"])
        if crit in ("C3a", "C3b", "C3c"):
            node = obs.split(":", 1)[1]
            (r0, w0), (r1, w1) = _row(run, pair["start_s"]), _row(run, pair["end_s"])
            if r0 is None or r1 is None:
                return dict(unformed=w0 or w1)
            h0, h1 = r0["site_heat_pJ"].get(node), r1["site_heat_pJ"].get(node)
            if crit == "C3a":
                return _band(h1 - h0, pair["value"], pair["tolerance"])
            if crit == "C3c":
                return agreement.judge_derived([max(h0 - h1, 0.0)], [0.0], pair["tolerance"])
            minus_dg = float(G(ctx.ref["world"], node, at_node(r0, node, inputs)) -
                             G(ctx.ref["world"], node, at_node(r1, node, inputs)))  # fmt: skip
            return agreement.judge_derived([h1 - h0], [minus_dg], pair["tolerance"])
        if crit in ("C4a", "C5", "C9"):
            row, why = _row(run, pair["time_s"])
            if row is None:
                return dict(unformed=why)
            sets, pops = _facing(inputs)
            if crit == "C4a":
                ligand, node = obs.split(":", 1)[1].split("@")
                bound = sum(row["amounts"][f"B:{p['id']}"] for p in inputs["populations"]
                            if p["ligand"] == ligand and sets[p["set"]] == node)  # fmt: skip
                rec = row["records"].get(f"{ligand}@{node}", dict(collected=0.0, supplied=0.0))
                books = (
                    row["amounts"][f"n:{ligand}@{node}"]
                    + bound
                    + rec["collected"]
                    - rec["supplied"]
                )
                return agreement.judge_derived([books], [pair["value"]], pair["tolerance"])
            if crit == "C5":
                s = obs.split(":", 1)[1]
                sites = row["amounts"][f"R:{s}"] + sum(
                    row["amounts"][f"B:{p}"] for p, ps in pops.items() if ps == s
                )
                return agreement.judge_derived([sites], [pair["value"]], pair["tolerance"])
            pop = obs.split(":", 1)[1]
            s = pops[pop]
            S = run["capacities"][s]
            members = [p for p, ps in pops.items() if ps == s]
            moiety = (
                abs(row["amounts"][f"R:{s}"] + sum(row["amounts"][f"B:{p}"] for p in members) - S)
                / S
            )
            tol = pair["tolerance_terms"]["eps_term"] + moiety
            return agreement.judge_derived(
                [row["site_occupied_fraction"][pop]], [row["amounts"][f"B:{pop}"] / S], tol
            )
        if crit in ("C4b", "C6"):
            k = _step(pair["time_s"], run["dt_s"])
            entries = [m for m in run["event_map"] if m["state_step"] == k]
            if sorted(m["variant"] for m in entries) != ["compiled", "numpy"]:
                return dict(unformed=f"the event map at step {k} lacks a variant")
            out = {}
            for m in entries:
                out[m["variant"]] = _map_pair(pair, m, inputs, agreement)
            ok = all(v.get("passes") for v in out.values())
            return dict(passes=ok, fails=all(v.get("fails") for v in out.values()) if crit == "C6" else not ok,
                        variants=out)  # fmt: skip
        if crit == "C4c":
            if len(run["events"]) != 1:
                return dict(unformed="not exactly one event")
            ligand = obs.split(":", 1)[1].split("@")[0]
            e = run["events"][0]["collected" if kind == "removed" else "supplied"].get(ligand)
            return _band(e, pair["value"], pair["tolerance"])
        if crit == "C7":
            return _c7(run)
        if crit == "C10":
            return _c10(run, ctx)
    except (KeyError, TypeError, ZeroDivisionError) as error:
        return dict(unformed=f"{type(error).__name__}: {error}")
    return dict(unformed=f"no rule for {crit} {obs}")


def _map_pair(pair, entry, inputs, agreement):
    obs, tt = pair["observable"], pair.get("tolerance_terms") or {}
    kind, name = obs.split(":", 1)
    before, after = entry["before"], entry["after"]
    if pair["criterion"] == "C6":
        return agreement.judge_constant([after["amounts"][obs]], before["amounts"][obs])
    ligand, node = name.split("@")
    n = before["amounts"][f"n:{ligand}@{node}"]
    f = entry["fraction"]
    if kind == "n":
        volume = next(x["volume_pL"] for x in inputs["nodes"] if x["id"] == node)
        expected = (1.0 - f) * n + f * volume * entry["buffer_mM"][ligand]
        anchor = next(
            a["n_fmol"]
            for a in inputs["free_amounts"]
            if a["ligand"] == ligand and a["node"] == node
        )
        tol = tt["eps_factor"] * (abs(anchor) + abs(n) + tt["f_V_c_buf"])
        return agreement.judge_derived([after["amounts"][obs]], [expected], tol)
    record = "collected" if kind == "removed" else "supplied"
    key = f"{ligand}@{node}"
    value = after["records"][key][record] - before["records"][key][record]
    if kind == "removed":
        return agreement.judge_derived([value], [f * n], tt["eps_factor"] * f * abs(n))
    return agreement.judge_derived([value], [pair["value"]], pair["tolerance"])


def _c7(run):
    """C7's outcome rule (TABLE §7): refused by the stage condition at step 1, its report's h max L above 1/2."""
    refusal, report = run["refusal"], run["step_report"]
    ok = (run["status"] == "refused" and refusal is not None and mapped(refusal)[0] == "stage"
          and refusal["step"] == 1 and report is not None and report["h_max_load"] > 0.5
          and report["verdict"] == "refused" and all(r["step"] == 0 for r in run["rows"]))  # fmt: skip
    if ok:  # S2: the limiting load is a set's summed free-site load, the largest of the loads.
        top = max(report["loads"], key=lambda x: x["per_s"])
        ok = report["max_load"] == top and top["kind"] == "L_R" and len(top["sums"]) >= 2
    return dict(passes=ok, fails=not ok)


def _c10(run, ctx):
    """C10 (TABLE §11): the run completes, holds every registered row, and its checks are complete and clean."""
    if run["status"] != "completed" or run["checks"] is None:
        return dict(passes=False, fails=True)
    want = registered_steps(ctx.ref["world"], run["dt_s"], ctx.world)
    clean = all(not c["failures"] for c in run["checks"].values())
    ok = [r["step"] for r in run["rows"]] == want and clean
    return dict(passes=ok, fails=not ok)


def registered_steps(echo, dt, world):
    """The registered rows' steps (TABLE §5.1): the start, every observation time and, in W5, the horizon."""
    steps = {0, *(_step(t, dt) for t in echo["observation_times"])}
    if world.removeprefix("INVENTED-").startswith("W5"):
        steps.add(_step(echo["horizon"], dt))
    return sorted(steps)


def inconclusive(pair, reference):
    """The references' own convergence (CRITERIA:41-44): R-ode's two tolerances differ at the pair by more than
    1e-10 of its scale s_node."""
    if pair["criterion"] not in ("C1", "C2a", "C8") or pair.get("time_s") is None:
        return False
    gaps = {
        (t["observable"], t["time_s"]): t["tolerance_gap"] for t in reference.get("trajectory", [])
    }
    gap = gaps.get((pair["observable"], pair["time_s"]))
    if gap is None:
        return False
    return gap > 1e-10 * s_node(pair["observable"], reference)


def s_node(observable, reference):
    """s_node (CRITERIA:50-52): the largest |reference value| of any amount at the observable's facing node, over
    the start and the observation times."""
    echo = reference["world"]
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
    values = [abs(x["value"]) for x in [*echo.get("start", []), *reference.get("trajectory", [])]
              if node(x["observable"]) == where]  # fmt: skip
    return max(values) if values else 0.0


def judge_world(ctx, agreement, G):
    """{entry key: result} for every pair of one world's reference file on its honest runs."""
    out = {}
    for pair in ctx.ref["pairs"]:
        key = (ctx.world, pair["criterion"], pair["observable"], pair.get("time_s"), pair.get("start_s"),
               pair.get("end_s"), pair.get("dt_s"))  # fmt: skip
        if pair["criterion"] == "C8" and pair["observable"].startswith("ratio:"):
            continue  # C8's ratios are formed below, from every dt's e(dt).
        if inconclusive(pair, ctx.ref):
            out[key] = dict(inconclusive=True)
            continue
        out[key] = evaluate(pair, ctx, agreement, G)
    out.update(c8_ratios(ctx))
    return out


def c8_ratios(ctx):
    """C8 (TABLE §11): e(dt) = max |y_e - y_ref| / scale over R and the B_b at the times, each dt's run; the ratio
    pairs against their minimum."""
    pairs = [p for p in ctx.ref["pairs"] if p["criterion"] == "C8"]
    errors = {}
    for p in pairs:
        if p["observable"].startswith("ratio:"):
            continue
        name, run = ctx.run(p)
        if run is None:
            continue
        row, _ = _row(run, p["time_s"])
        e = None if row is None else row["amounts"].get(p["observable"])
        if e is None:
            errors[p["dt_s"]] = float("nan")
            continue
        errors[p["dt_s"]] = max(errors.get(p["dt_s"], 0.0), abs(e - p["value"]) / p["scale"])
    out = {}
    for p in pairs:
        if not p["observable"].startswith("ratio:"):
            continue
        a, b = (float(x) for x in re.findall(r"e\(([^)]+)\)", p["observable"]))
        ratio = (
            errors.get(a, float("nan")) / errors.get(b, float("nan"))
            if errors.get(b)
            else float("nan")
        )
        ok = ratio >= p["minimum"]
        out[(ctx.world, "C8", p["observable"], None, None, None, None)] = dict(
            passes=ok, fails=not ok, ratio=ratio
        )
    return out


def summarize(entries):
    """{criterion: pass | fail | inconclusive}: a criterion passes only when every entry passes; an entry that
    cannot be formed fails it (TABLE §11.2); inconclusive only from the references' convergence."""
    out = {}
    for key, result in entries.items():
        crit = key[1]
        state = out.setdefault(crit, dict(entries=0, failed=0, unformed=0, inconclusive=0))
        state["entries"] += 1
        if result.get("inconclusive"):
            state["inconclusive"] += 1
        elif "unformed" in result:
            state["unformed"] += 1
        elif not result.get("passes"):
            state["failed"] += 1
    for state in out.values():
        bad = state["failed"] + state["unformed"]
        state["verdict"] = "fail" if bad else "inconclusive" if state["inconclusive"] else "pass"
    return out


# The plants' rules (TABLE §8.2): which criteria a plant needs (all) or any one of; the book its row names.
PLANT_RULE = {"P1": ("any", None), "P2": ("any", None), "P3": ("any", "dissipation check"), "P4": ("C7", None),
              "P5": ("all", None), "P6": ("any", "energy ledger"), "P7": ("all", None),
              "P8": ("refusal", "moiety ledger"), "P9": ("any", None)}  # fmt: skip


def judge_plants(table, references, agreement, G, prefix=""):
    """{plant: {caught, why, entries}} by TABLE §8.2: each entry (plant, criterion, world, time_s) caught where it
    fails on the plant's run and passes on the honest run; a check refusal by the book the plant's row names
    (any book where it names none), with the honest run completed; P4 by its verdict "admitted" alone; P8 by its
    own ledger alone; P5 on each of its runs."""
    runs = table["runs"]
    out = {}
    for world, ref in references.items():
        ctx = Context(table, world, ref, prefix)
        for entry in ref.get("plants", []):
            if entry.get("information"):
                continue
            plant, crit, pworld = entry["plant"], entry["criterion"], entry["world"]
            pname = f"{prefix}{pworld}-{plant}"
            state = out.setdefault(plant, dict(entries=[], runs={}))
            run = runs.get(pname)
            honest_ctx = Context(table, pworld, ref, prefix) if pworld != world else ctx
            result = _plant_entry(entry, ctx, honest_ctx, run, agreement, G)
            state["entries"].append(
                dict(run=pname, criterion=crit, time_s=entry.get("time_s"), **result)
            )
            state["runs"].setdefault(pname, run is not None)
    for plant, state in out.items():
        rule, book = PLANT_RULE[plant]
        by_run = {}
        for e in state["entries"]:
            by_run.setdefault(e["run"], []).append(e)
        caught_runs = {}
        for name, entries in by_run.items():
            run = runs.get(name)
            if run is None:
                caught_runs[name] = False
                continue
            refusal = run["refusal"]
            refused_by_book = refusal is not None and mapped(refusal)[0] == "check" and (
                book is None or mapped(refusal)[1] == book)  # fmt: skip
            if plant == "P4":
                caught_runs[name] = any(e["caught"] for e in entries)
            elif plant == "P8" or rule == "refusal":
                caught_runs[name] = refused_by_book
            elif refused_by_book:
                caught_runs[name] = True
            else:
                crits = {}
                for e in entries:
                    crits[e["criterion"]] = crits.get(e["criterion"], False) or e["caught"]
                caught_runs[name] = all(crits.values()) if rule == "all" else any(crits.values())
        state["caught_runs"] = caught_runs
        state["caught"] = bool(caught_runs) and all(caught_runs.values())
    return out


def _plant_entry(entry, ctx, honest_ctx, run, agreement, G):
    """One plant entry on its run, with its honest baseline (P-d)."""
    if run is None:
        return dict(caught=False, why="no run")
    crit, compared = entry["criterion"], entry.get("compared") or {}
    pairs = [p for p in ctx.ref["pairs"] if p["criterion"] == crit and (
        not compared.get("observable") or p["observable"] == compared["observable"])]  # fmt: skip
    if entry.get("time_s") is not None:
        pairs = [p for p in pairs if p.get("time_s") == entry["time_s"]]
    if crit == "C7":
        report = run["step_report"]
        caught = report is not None and report.get("verdict") == "admitted"
        return dict(caught=caught, why="verdict admitted" if caught else "not admitted")
    if crit == "C10":
        return dict(caught=False, why="by its own ledger's refusal only")
    if not pairs:
        return dict(caught=False, why="no reference pair")
    failed, baseline_ok = False, True
    for pair in pairs:
        planted = evaluate(pair, ctx, agreement, G, run=run)
        honest = evaluate(pair, honest_ctx, agreement, G)
        if not honest.get("passes"):
            baseline_ok = False
        if planted.get("fails") is True and "unformed" not in planted:
            failed = True
    caught = failed and baseline_ok
    return dict(caught=caught, failed=failed, baseline=baseline_ok,
                why="caught" if caught else "baseline failed" if failed else "not failed")  # fmt: skip


def judge(table, references, agreement, G, prefix=""):
    """The judgement: every world's entries, the criteria, the plants (TABLE §11, §8.2)."""
    entries = {}
    for world, ref in references.items():
        entries.update(judge_world(Context(table, world, ref, prefix), agreement, G))
    criteria = summarize(entries)
    plants = judge_plants(table, references, agreement, G, prefix)
    derived = sorted(
        {
            f"{n}:{s}"
            for n, r in table["runs"].items()
            for s, w in r["free_sites"].items()
            if w == "derived"
        }
    )
    return dict(criteria=criteria, plants={p: dict(caught=v["caught"], runs=v["caught_runs"]) for p, v in plants.items()},
                derived_sets=derived, entries=len(entries),
                failed_entries=[list(map(str, k)) + [json.dumps(v)[:300]] for k, v in entries.items()
                                if not v.get("passes") and not v.get("inconclusive")][:200],
                plant_detail=plants)  # fmt: skip


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
