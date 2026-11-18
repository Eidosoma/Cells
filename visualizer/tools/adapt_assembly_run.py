#!/usr/bin/env python3
"""Turn saved runs of the engine's assembly family into the assembly view's own run files.

From a run folder of `cells.assembly_lineages.run@1` (run.json, world.json, records.npz,
manifest.json; the folder's FORMAT.md says what each holds) to one file of the viewer's own
contract, `cells.visualizer.assembly_run@1` (schema/ASSEMBLY_RUN.md):

    python3 tools/adapt_assembly_run.py --evidence ROOT --out DIR \\
        --standing development --standing-from "WHERE THAT IS RECORDED" RUN [RUN ...]

Each RUN is a run folder, named relative to ROOT (the folder that holds the evidence); each
becomes DIR/<law set>-<form>-<qualifier's first 8>.json. The file names the run folder as given
(relative to ROOT), never a machine path, and the same input gives the same bytes.

What it keeps to:
  * It reads saved files only, with the viewer's own reader (tools/lib/npy_reader.py): no numpy,
    and nothing of the engine is imported or run.
  * Every array is found through run.json's own `records` table (its file, its array, its axes,
    its base and its unit are held to what this adapter reads), and every convention it follows
    is read from the run's own tables: an event's type and sign from `channels`, a row's kind
    from `row_kind`'s legend, the types from the world. No name of the engine's interfaces is held
    here: the run's own are copied into what the file says of where it came from.
  * It stops with a plain error where the run lacks what the contract needs, or states something
    it does not know (a key of run.json it has not met, a mode, a form, a record of another shape).
  * It judges nothing. What the run states of its law's check and of its ledger is copied as the
    run's own text (numbers as run.json writes them), with each line's place in run.json.
  * run.json states no standing (judged or not). The standing is given on the command line, with
    where it is recorded, and the file says so.

Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from npy_reader import read_npz  # noqa: E402  (the viewer's own reader)

VIEW_FORMAT = "cells.visualizer.assembly_run@1"
RUN_FORMAT = "cells.assembly_lineages.run@1"
WORLD_FORMAT = "cells.assembly_lineages.world@1"
# The keys of run.json this adapter knows (FORMAT.md, "A run bundle"). Another key is something the
# run states that the adapter does not know: it stops rather than pass it over.
RUN_KEYS = {
    "bound", "channels", "definition_sha256", "diagnostics", "end", "engine_models", "format", "founder", "keys",
    "law", "layers", "ledger", "lifecycle", "lives", "mode", "model", "operators", "records", "run", "source",
    "ssa", "stream", "time", "world",
}
# The run's modes this contract reads, in the run's spelling, and in the contract's.
MODES = {"single_lineage": "single lineage"}
# The two forms of the law the contract names (schema/ASSEMBLY_RUN.md, `law.form`).
FORMS = ("single-event", "pair-consistent")
# What the standing given on the command line makes the file say.
STANDINGS = {"development": "Development run of the engine, not judged"}
# The licences a source may carry here, and their class (D173): only a permissive source stands behind a number.
LICENCE_CLASSES = {"CC BY 4.0": "permissive"}

# The records read, each with the axes and base it must have (FORMAT.md, run.json's `records`).
RECORDS = {
    "assembly_count": (("row", "type", "assembly"), "row"),
    "joined_total": (("row", "type", "assembly"), "row"),
    "left_total": (("row", "type", "assembly"), "row"),
    "discarded_total": (("row", "type", "assembly"), "row"),
    "row_kind": (("row",), "row"),
    "row_fission": (("row",), "row"),
    "row_time": (("row",), "row"),
    "occupant": (("row", "assembly"), "row"),
    "event_channel": (("event",), "event"),
    "event_time": (("event",), "event"),
    "events_per_growth": (("growth",), "growth"),
    "growth_carrier": (("growth",), "growth"),
    "fission_time": (("fission",), "fission"),
    "fission_parent": (("fission",), "fission"),
    "fission_daughters": (("fission", "daughter"), "fission"),
    "fission_split": (("fission", "type"), "fission"),
    "fission_followed": (("fission",), "fission"),
    "fission_similarity": (("fission", "daughter"), "fission"),
}


class Refused(Exception):
    """The run cannot be adapted: the message says why, in plain words."""


def need(condition, message):
    if not condition:
        raise Refused(message)


def text_of(value):
    """A value of run.json as run.json writes it (numbers were kept as their own text when read)."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def read_json(path, keep_numbers=False):
    raw = path.read_text(encoding="utf-8")
    if keep_numbers:
        return json.loads(raw, parse_float=str, parse_int=str, parse_constant=str)
    return json.loads(raw)


def lines_of(block, prefix, unit=None):
    """Every leaf of a block of run.json as {path, text} (with `unit` where the block states one for k_BT values)."""
    out = []
    for key, value in block.items():
        path = f"{prefix}.{key}"
        if isinstance(value, dict):
            out += lines_of(value, path, unit)
        elif isinstance(value, list):
            out.append({"path": path, "text": "[" + ", ".join(text_of(item) for item in value) + "]"})
        else:
            line = {"path": path, "text": text_of(value)}
            if unit and key.endswith("_kT"):
                line["unit"] = unit
            out.append(line)
    return out


def sparse(counts):
    return [[i, c] for i, c in enumerate(counts) if c]


def key_words(key):
    """A carrier key in the run's spelling s:c (key = s * 2**32 + c)."""
    return f"{key >> 32}:{key & 0xFFFFFFFF}"


class RunFolder:
    """One run folder, read and held to what the contract needs."""

    def __init__(self, root, name):
        self.name = name
        self.path = (root / name).resolve()
        need(self.path.is_dir(), f"{name}: no run folder there")
        for file in ("run.json", "world.json"):
            need((self.path / file).is_file(), f"{name}: it has no {file}")
        self.run = read_json(self.path / "run.json")
        self.stated = read_json(self.path / "run.json", keep_numbers=True)
        self.world = read_json(self.path / "world.json")
        manifest = self.path / "manifest.json"
        self.manifest = read_json(manifest) if manifest.is_file() else None
        self.check_header()
        self.arrays = self.read_records()

    # ------------------------------------------------------------ what the run says it is

    def check_header(self):
        run, name = self.run, self.name
        need(run.get("format") == RUN_FORMAT, f"{name}: run.json is not {RUN_FORMAT} (it says {run.get('format')!r})")
        unknown = sorted(set(run) - RUN_KEYS)
        need(not unknown, f"{name}: run.json states {', '.join(unknown)}, which this adapter does not know: it stops rather than pass it over")
        need(self.world.get("format") == WORLD_FORMAT, f"{name}: world.json is not {WORLD_FORMAT}")
        need(self.world.get("id") == run.get("world"), f"{name}: run.json names the world {run.get('world')!r}, and world.json is {self.world.get('id')!r}")
        need(run.get("mode") in MODES, f"{name}: the run's mode {run.get('mode')!r} is not one the contract reads ({', '.join(MODES)})")
        law = run.get("law") or {}
        need(law.get("form") in FORMS, f"{name}: the run's law states the form {law.get('form')!r}, not one of {', '.join(FORMS)}")
        need(isinstance(law.get("id"), str) and law["id"], f"{name}: the run's law has no id")
        need(isinstance(law.get("law_set"), str) and law["law_set"], f"{name}: the run's law names no law set (the model system it is a run of)")
        need(isinstance((run.get("source") or {}).get("revision"), str), f"{name}: the run names no source revision")
        need(isinstance((run.get("run") or {}).get("qualifier"), str), f"{name}: the run has no qualifier")
        models = run.get("engine_models") or {}
        need(models.get("model") and isinstance(models.get("laws"), list) and isinstance(models.get("operators"), list), f"{name}: the run does not name the engine's model, laws and operators")
        need(isinstance(run.get("records"), dict), f"{name}: run.json has no records table")
        need(isinstance((run.get("channels") or {}).get("rows"), list), f"{name}: run.json has no channel table")

    def read_records(self):
        table, name = self.run["records"], self.name
        wanted = {}
        for record, (axes, base) in RECORDS.items():
            entry = table.get(record)
            need(entry is not None, f"{name}: the run's records table has no {record}, which the contract needs")
            need(tuple(entry.get("axes") or ()) == axes, f"{name}: {record} has the axes {entry.get('axes')}, not {list(axes)}")
            need(entry.get("base") == base, f"{name}: {record} is on the base {entry.get('base')!r}, not {base!r}")
            need(entry.get("file") == "records.npz", f"{name}: {record} is in {entry.get('file')!r}, not records.npz")
            wanted[record] = entry["array"]
        need((self.path / "records.npz").is_file(), f"{name}: it has no records.npz")
        read = read_npz(self.path / "records.npz", sorted(set(wanted.values())))
        arrays = {record: read[array] for record, array in wanted.items()}
        for record, array in arrays.items():
            axes = RECORDS[record][0]
            need(len(array.shape) == len(axes), f"{name}: {record} has {len(array.shape)} axes in records.npz, and the table says {len(axes)}")
            if "assembly" in axes:
                need(array.shape[axes.index("assembly")] == 1, f"{name}: {record} holds more than one assembly at a row: the contract reads a single lineage")
        units = {record: table[record].get("unit") for record in RECORDS}
        for record in ("assembly_count", "joined_total", "left_total", "discarded_total", "fission_split"):
            need(units[record] == "molecules", f"{name}: {record} is in {units[record]!r}, not molecules")
        return arrays

    # ------------------------------------------------------------ the world

    def environment(self):
        world, name = self.world, self.name
        types = (world.get("derived") or {}).get("types")
        need(isinstance(types, list) and types and len(set(types)) == len(types), f"{name}: world.json lists no types")
        declared = (world.get("world") or {}).get("types") or {}
        need(declared.get("count") == len(types), f"{name}: world.json declares {declared.get('count')} types and lists {len(types)}")
        matrix = ((world.get("world") or {}).get("law_data") or {}).get("catalysis_matrix")
        need(isinstance(matrix, list) and len(matrix) == len(types) and all(isinstance(row, list) and len(row) == len(types) for row in matrix), f"{name}: the world has no catalysis matrix of {len(types)} by {len(types)}: the view's table needs one")
        need(all(isinstance(value, (int, float)) and value > 0 for row in matrix for value in row), f"{name}: a catalysis factor is not a positive number")
        supply = (world.get("world") or {}).get("supply")
        if isinstance(supply, (int, float)):
            reservoir = {"each": supply, "says": "the run's supply (rho): every type held at this concentration"}
        else:
            need(isinstance(supply, list) and len(supply) == len(types), f"{name}: the world's supply is neither one number nor one for each type")
            reservoir = {"of": supply, "says": "the run's supply (rho), for each type"}
        derived = world.get("derived") or {}
        rates = {}
        for word, key in (("join", "join_rate"), ("leave", "leave_rate")):
            values = derived.get(key)
            need(isinstance(values, list) and len(values) == len(types), f"{name}: the world derives no {key} for each type")
            rates[word] = values[0] if len(set(values)) == 1 else values
        return {
            "id": f"world-{world['id'][:12]}",
            "world": world["id"],
            "types": types,
            "catalysis": {
                "says": "beta_ij, the world's catalysis matrix: x_i = sum_j beta_ij n_j, so a molecule of type j in the assembly speeds the joining and the leaving of type i",
                "encoding": "log10, two decimals",
                "rows": [[round(math.log10(value), 2) for value in row] for row in matrix],
            },
            "reservoir": reservoir,
            "rates": {**rates, "says": f"the world's derived join and leave rates, per {(self.run.get('time') or {}).get('unit', 'nominal')} time unit"},
        }

    # ------------------------------------------------------------ the run

    def channel_types(self, types):
        """{event_channel value: signed type number of the contract}, from the run's channel table."""
        out = {}
        for row in self.run["channels"]["rows"]:
            kind, index, value = row.get("kind"), row.get("type_index"), row.get("event_channel")
            need(kind in ("join", "leave"), f"{self.name}: a channel is of the kind {kind!r}, neither a join nor a leave")
            need(isinstance(index, int) and 0 <= index < len(types) and row.get("type") == types[index], f"{self.name}: channel {value} names a type that is not the world's in its place")
            need(isinstance(value, int) and value not in out, f"{self.name}: channel values must be whole numbers, once each")
            out[value] = (index + 1) if kind == "join" else -(index + 1)
        need(len(types) < 128, f"{self.name}: {len(types)} types do not fit the trace's signed bytes")
        return out

    def row_codes(self):
        legend = self.run["records"]["row_kind"].get("legend") or {}
        codes = {words: int(code) for code, words in legend.items()}
        for words in ("start", "parent", "daughter"):
            need(words in codes, f"{self.name}: row_kind's legend has no {words!r} row")
        return codes

    def adapt(self, standing):
        run, a, name = self.run, self.arrays, self.name
        environment = self.environment()
        types = environment["types"]
        n = len(types)
        need(a["assembly_count"].shape[1] == n, f"{name}: assembly_count counts {a['assembly_count'].shape[1]} types, and the world has {n}")
        rows = a["row_kind"].shape[0]
        counts = a["assembly_count"].values

        def at_row(values, r):
            return list(values[r * n : (r + 1) * n])

        codes = self.row_codes()
        kind = list(a["row_kind"].values)
        fission_of = list(a["row_fission"].values)
        starts = [r for r in range(rows) if kind[r] == codes["start"]]
        need(len(starts) == 1 and starts[0] == 0, f"{name}: the run has no single start row first")
        founder = at_row(counts, 0)
        declared = (self.world.get("world") or {}).get("founder")
        if run.get("founder") == "world":
            need(declared == founder, f"{name}: the start row is not the world's founder, which the run says it starts from")
        need(sum(founder) > 0, f"{name}: the founder holds no molecule")

        fissions_count = a["fission_time"].shape[0]
        need(fissions_count >= 1, f"{name}: the run made no fission")
        end = run.get("end") or {}
        need(end.get("fissions") == fissions_count, f"{name}: run.json says {end.get('fissions')} fissions and the records hold {fissions_count}")
        parent_row = {fission_of[r]: r for r in range(rows) if kind[r] == codes["parent"]}
        daughter_row = {fission_of[r]: r for r in range(rows) if kind[r] == codes["daughter"]}
        split = a["fission_split"].values
        similarity = a["fission_similarity"].values
        followed = list(a["fission_followed"].values)
        times = list(a["fission_time"].values)
        parents_keys = list(a["fission_parent"].values)
        daughters_keys = a["fission_daughters"].values
        totals = {word: a[f"{word}_total"].values for word in ("joined", "left", "discarded")}
        fissions = []
        for k in range(1, fissions_count + 1):
            need(k in parent_row and k in daughter_row, f"{name}: fission {k} has no parent row and daughter row")
            parent = at_row(counts, parent_row[k])
            first = list(split[(k - 1) * n : k * n])
            need(all(0 <= f <= p for f, p in zip(first, parent)), f"{name}: fission {k}'s first daughter holds more of a type than its parent")
            second = [p - f for p, f in zip(parent, first)]
            carried = at_row(counts, daughter_row[k])
            # Which daughter carries on: read from the daughter row itself, and held to the run's own record of it.
            continues = "first" if carried == first else "second" if carried == second else None
            need(continues is not None, f"{name}: fission {k}'s daughter row is neither of its daughters")
            need(followed[k - 1] == (0 if continues == "first" else 1) or first == second, f"{name}: fission {k}'s fission_followed and its daughter row disagree")
            h = [similarity[2 * (k - 1)], similarity[2 * (k - 1) + 1]]
            need(all(not math.isnan(value) for value in h), f"{name}: fission {k} has a daughter with no similarity (an empty daughter): the contract has no place for it")
            need(all(-1e-12 <= value <= 1 + 1e-12 for value in h), f"{name}: fission {k}'s similarity is outside 0 to 1")
            r = parent_row[k]
            total = {word: sum(totals[word][r * n : (r + 1) * n]) for word in totals}
            fissions.append({
                "k": k,
                "nominal": times[k - 1],
                "parent": sparse(parent),
                "first": sparse(first),
                "continues": continues,
                "similarity": [min(1.0, max(0.0, value)) for value in h],
                "totals": total,
                "keys": {"parent": key_words(parents_keys[k - 1]), "first": key_words(daughters_keys[2 * (k - 1)]), "second": key_words(daughters_keys[2 * (k - 1) + 1])},
            })

        # The trace: one growth for each fission. The run keeps one more, the growth after its last fission
        # to its end; the contract has no place for it, so it must be empty (the run ended at that fission).
        growths = list(a["events_per_growth"].values)
        need(len(growths) == fissions_count + 1, f"{name}: the run has {len(growths)} growths for {fissions_count} fissions; the contract reads one for each fission and an empty last")
        need(growths[-1] == 0, f"{name}: the run goes on for {growths[-1]} events after its last fission (it ended {end.get('status')!r}): the contract has no place for a growth that ends without a fission")
        growths = growths[:-1]
        # Growth g is the life that grows to fission g + 1's parent, and from the second on, the daughter fission g carried on.
        carriers = list(a["growth_carrier"].values)
        for g in range(fissions_count):
            need(carriers[g] == parents_keys[g], f"{name}: growth {g} is not the life that splits at fission {g + 1}")
            if g:
                keys = fissions[g - 1]["keys"]
                need(key_words(carriers[g]) == keys[fissions[g - 1]["continues"]], f"{name}: growth {g} is not the daughter fission {g} carried on")
        channel = self.channel_types(types)
        raw_events = list(a["event_channel"].values)
        need(len(raw_events) == sum(growths) == end.get("events"), f"{name}: the trace holds {len(raw_events)} events, its growths {sum(growths)}, and run.json says {end.get('events')}")
        events = []
        for value in raw_events:
            need(value in channel, f"{name}: an event's channel {value} is not in the run's channel table")
            events.append(channel[value])
        # Replay: the founder and each carried daughter must reach the next parent exactly.
        x, at = list(founder), 0
        for g, length in enumerate(growths):
            for value in events[at : at + length]:
                x[abs(value) - 1] += 1 if value > 0 else -1
                need(x[abs(value) - 1] >= 0, f"{name}: the trace takes a count below zero in growth {g}")
            at += length
            parent = [0] * n
            for i, c in fissions[g]["parent"]:
                parent[i] = c
            need(x == parent, f"{name}: the trace does not reach fission {g + 1}'s parent")
            first = [0] * n
            for i, c in fissions[g]["first"]:
                first[i] = c
            x = first if fissions[g]["continues"] == "first" else [p - f for p, f in zip(parent, first)]
        # The events' own times, as each one's place in its growth's span (from its birth to its fission).
        event_times = list(a["event_time"].values)
        row_times = list(a["row_time"].values)
        fractions, at = [], 0
        for g, length in enumerate(growths):
            start = row_times[0] if g == 0 else times[g - 1]
            stop = times[g]
            need(stop > start, f"{name}: growth {g} spans no time")
            last = start
            for t in event_times[at : at + length]:
                need(last <= t <= stop, f"{name}: an event of growth {g} is out of order or outside its growth's span")
                last = t
                fractions.append(min(65535, max(0, round((t - start) / (stop - start) * 65535))))
            at += length

        law, stated = run["law"], self.stated
        models = run["engine_models"]
        ledger_unit = (run.get("ledger") or {}).get("unit")
        states = []
        states += lines_of(stated["law"].get("check") or {}, "law.check")
        if stated["law"].get("world_report") not in (None, "null"):
            states += lines_of(stated["law"]["world_report"], "law.world_report")
        states += lines_of((stated.get("ledger") or {}).get("closure") or {}, "ledger.closure", ledger_unit)
        need(states, f"{name}: the run states no check of its law and no ledger")
        formulas = law.get("formulas") or {}
        factors = "; ".join(f"{key} = {formulas[key]}" for key in sorted(formulas) if key.startswith("g_"))
        sources = {}
        for place, provenance in (("law", law.get("provenance")), ("exchange", (law.get("exchange") or {}).get("provenance")), ("fission", ((run.get("operators") or {}).get("fission") or {}).get("provenance"))):
            if not provenance:
                continue
            licence = provenance.get("licence", "")
            short = next((known for known in LICENCE_CLASSES if licence.startswith(known)), None)
            need(short, f"{name}: the {place}'s source carries the licence {licence!r}, which this adapter does not know")
            # One source cited for several places is listed once, with each place it stands behind.
            same = next((key for key, held in sources.items() if held["text"] == provenance.get("source", "") and held["licence"] == licence), None)
            if same:
                sources[same]["for"] += f"; {provenance.get('place', '')}"
            else:
                sources[place] = {"text": provenance.get("source", ""), "licence": licence, "class": LICENCE_CLASSES[short], "for": provenance.get("place", ""), "kind": provenance.get("kind", "")}
        operators = run.get("operators") or {}
        world = self.world.get("world") or {}
        fission = world.get("fission") or {}
        partition = fission.get("partition") or {}
        qualifier = run["run"]["qualifier"]
        form = law["form"]
        interfaces = {"law": law.get("interface"), "exchange": (law.get("exchange") or {}).get("interface")}
        interfaces.update({f"operator {key}": value.get("interface") for key, value in sorted(operators.items()) if isinstance(value, dict)})
        files = (self.manifest or {}).get("files_sha256") or {}
        return {
            "law_set": law["law_set"],
            "environment": environment,
            "standing": standing,
            "sources": sources,
            "time": run.get("time") or {},
            "run": {
                "id": f"{form}-{qualifier[:8]}",
                "label": f"Run {qualifier[:8]}",
                "environment": environment["id"],
                "world": run["world"],
                "mode": MODES[run["mode"]],
                "law": {"name": law["id"], "form": form, "engine_name": law["id"], "says": factors or law["id"]},
                "engine_models": [models["model"], *models["laws"], *models["operators"]],
                "revision": run["source"]["revision"],
                "rules": {
                    "start": f"the world's founder, {sum(founder)} molecules of {sum(1 for c in founder if c)} types",
                    "events": (run.get("ssa") or {}).get("method", "one molecule per event"),
                    "fission_size": fission.get("size"),
                    "split": ((operators.get("fission") or {}).get("provenance") or {}).get("place") or f"{partition.get('rule')}",
                    "continues": f"the {(world.get('continuation') or {}).get('daughter')} daughter",
                },
                "founder": sparse(founder),
                "fissions": fissions,
                "trace": {
                    "encoding": "signed type numbers, one for each molecule: +(i + 1) when type i joins, -(i + 1) when it leaves, read through the run's channel table",
                    "growths": growths,
                    "events": base64.b64encode(struct.pack(f"<{len(events)}b", *events)).decode("ascii"),
                    "times": {
                        "encoding": "each event's place in its growth's span, from the growth's start (its birth) to its fission, as 0 to 65535: unsigned 16-bit little-endian, base64",
                        "values": base64.b64encode(struct.pack(f"<{len(fractions)}H", *fractions)).decode("ascii"),
                    },
                },
                "keys": {"spelling": (run.get("keys") or {}).get("spelling"), "founder": (run.get("keys") or {}).get("founder")},
                "states": {
                    "says": "what the run states of its law's check and of its ledger, as run.json writes it: each line is its place in run.json and the run's own text",
                    "lines": states,
                },
                "provenance": {
                    "folder": self.name,
                    "format": run["format"],
                    "model": models["model"],
                    "laws": models["laws"],
                    "operators": models["operators"],
                    "interfaces": interfaces,
                    "revision": run["source"]["revision"],
                    "dirty": run["source"].get("dirty"),
                    "qualifier": qualifier,
                    "definition_sha256": run.get("definition_sha256"),
                    "world": run["world"],
                    "files_sha256": {file: files[file] for file in ("run.json", "world.json", "records.npz") if file in files},
                    "end": {key: end.get(key) for key in ("status", "fissions", "events", "time")},
                },
            },
        }


def file_of(adapted, entry):
    """The contract's file for one adapted run."""
    time = adapted["time"]
    standing = adapted["standing"]
    return {
        "format": VIEW_FORMAT,
        "development": standing,
        "model": {"id": entry["id"], "label": entry["label"], "plain": entry.get("plain", "")},
        "time": {
            "base": "fission",
            "unit": "fission",
            "plural": "fissions",
            "nominal": f"The clock counts fissions. The run's own time is in {time.get('unit', 'nominal')} units (its rates are {time.get('rates', 'per nominal time unit')}): a fission's nominal time is the run's.",
        },
        "environments": [adapted["environment"]],
        "runs": [adapted["run"]],
        "sources": adapted["sources"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="+", help="run folders, relative to --evidence")
    parser.add_argument("--evidence", required=True, help="the folder that holds the evidence (the run folders are named relative to it)")
    parser.add_argument("--out", required=True, help="where to write the run files")
    parser.add_argument("--standing", choices=sorted(STANDINGS), help="the runs' standing, which run.json does not state")
    parser.add_argument("--standing-from", help="where that standing is recorded (a file and its words)")
    parser.add_argument("--entries", default=str(HERE.parent / "data" / "models"), help="the viewer's model-system entries (for the model's label and words)")
    args = parser.parse_args(argv)
    try:
        need(args.standing and args.standing_from, "run.json states no standing (judged or not): give --standing development and --standing-from with where that is recorded")
        standing = {"says": STANDINGS[args.standing], "standing": args.standing, "from": args.standing_from, "run_states": "run.json states no standing of its own"}
        root = Path(args.evidence).resolve()
        need(root.is_dir(), f"{args.evidence}: no such folder")
        out = Path(args.out)
        written = []
        for name in args.runs:
            relative = Path(name)
            if relative.is_absolute():
                need(relative.resolve().is_relative_to(root), f"{name}: the run folder is not under --evidence")
                relative = relative.resolve().relative_to(root)
            folder = RunFolder(root, relative.as_posix())
            adapted = folder.adapt(standing)
            entry_path = Path(args.entries) / f"{adapted['law_set']}.json"
            need(entry_path.is_file(), f"{name}: the run is of the law set {adapted['law_set']!r}, and the viewer has no entry {entry_path.name}")
            entry = json.loads(entry_path.read_text(encoding="utf-8"))
            data = file_of(adapted, entry)
            text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
            out.mkdir(parents=True, exist_ok=True)
            target = out / f"{adapted['law_set']}-{adapted['run']['id']}.json"
            target.write_text(text, encoding="utf-8")
            written.append((target, len(text.encode("utf-8")), hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]))
        for target, size, digest in written:
            print(f"wrote {target} ({size / 1024:.0f} KB, sha256 {digest})")
    except Refused as error:
        print(f"adapt_assembly_run: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
