"""The exporter: from the records of runs to the engine's table (spec/TABLE.md, spec/READOUTS.md).

    python -m validation.ensemble_reexpression.table export --runs DIR --output DIR [--owed FILE]
        [--owed-sha256 HEX] [--inputs FILE]
    python -m validation.ensemble_reexpression.table check DIRECTORY [--strings NOTE]

`export` writes one `table_<consumer>.json` for each consumer and their `SHA256SUMS`, and replaces
nothing. Each entry is made from one run's own record and from no other run: nothing here forms a
difference, a ratio or an estimate. A world's block is read back from the definition that the engine
parsed and ran (worlds.read), and never from inputs.json. `check` holds a folder of tables to the
contract's keys and types, and to a strings note where one is given.

**The retry's runs.** `--owed FILE` exports the runs that the judge's note lists, which were made
after it. Where they were made up front with the batch (`run all --retries`), they stand apart and
are exported with `--owed-sha256 HEX` too, and only if HEX is the note's own sha256.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from cells.assembly_pool import observables
from cells.assembly_pool.kernel import PoolState
from cells.assembly_pool.schedule import joined
from validation.ensemble_reexpression import readouts, worlds
from validation.ensemble_reexpression.inputs import (
    DRIVEN,
    MATCH_S,
    POOL,
    REGISTERED,
    Inputs,
    matched,
    read_json,
)
from validation.ensemble_reexpression.labels import LABELS, declared_strings, label, strings
from validation.ensemble_reexpression.pieces import Pieces
from validation.ensemble_reexpression.refusals import PARTIAL, SECOND_PASS
from validation.ensemble_reexpression.run import RECORD, Folders, digest

KIND = "ensemble-reexpression engine table, version 1"
UNITS = {"amount": "fmol", "energy": "pJ", "potential": "V", "time": "s"}
SUMS = "SHA256SUMS"
OFF_GRID = "off_grid"
HARNESS = ("event_chunk_size", "recording", "max_output_bytes", "max_wall_seconds")
SOURCE = {
    "engine_revision": str,
    "checkout_dirty": bool,
    "snapshot": str,
    "snapshot_patch_sha256": str,
    "python": str,
    "numpy": str,
    "jax": str,
    "jaxlib": str,
    "cpu_model": str,
    "blas_threads": int,
}


class ExportError(RuntimeError):
    """A record that the exporter cannot make an entry of."""


# ------------------------------------------------------------------ what a run declared


def read(path):
    return read_json(path) if Path(path).is_file() else None


def submitted_ionic(submitted):
    """The ionic definition in what a run submitted: a composed file's, or the definition itself."""
    return submitted["ionic"] if isinstance(submitted, dict) and "ionic" in submitted else submitted


def ionic_definition(attempt):
    """The definition that the engine parsed and ran (its canonical form), or where it parsed none,
    the one submitted."""
    parsed = read(attempt / "output/resolved_config.json") or read(attempt / "parsed.json")
    return parsed if parsed is not None else submitted_ionic(read(attempt / "submitted.json"))


def driven_cells(definition):
    """The cells that have a channel (one that carries calcium apart), in the definition's order of
    cells: the k-th is the cell of the k-th pool of a composed file (Amendment 1, items 3 and 7)."""
    model, own = definition["model"], Pieces(definition).channels
    inside = {m["id"]: m["inside"] for m in model["membranes"]}
    held = {inside.get(c["membrane_id"]) for c in model["channels"] if c["id"] in own}
    return [c["id"] for c in model["cells"] if c["id"] in held]


def block(definition):
    """The block of a definition as a table's `inputs` holds it."""
    return worlds.shown(worlds.read(definition))


def beyond(definition):
    """What a composite's definition holds that its block does not say, for `definition` (PART2 §2.1
    and §2.4): every species row, the release's conditions by cell, and the concentration of each
    row at each node that no block names it at."""
    p = Pieces(definition)
    if not p.composite:
        return {}
    model = p.model
    unnamed = {name: [s for s in p.species if s not in p.ionic] for name in p.regions}
    unnamed |= {node: [s for s in p.species if s in p.fuel] for node in p.store.values()}
    return {
        "species_rows": list(p.species),
        "release_conditions": {cell: c["id"] for cell, c in p.release_condition.items()},
        "trace_mM": {
            o["id"]: {s: o["initial_amount_fmol"][s] / o["volume_pL"] for s in unnamed[o["id"]]}
            for o in model["extracellular"]
        },
    }


def readable(read_back, *args):
    """What is read back from a declaration, or why it cannot be (one that was never parsed)."""
    try:
        return read_back(*args)
    except Exception as error:
        return {"unreadable": f"{type(error).__name__}: {error}"}


def unswitched(definition):
    """A switch list without a switch: every channel of the world is a key (Amendment 2, 9.1), the
    ones that carry calcium apart, which no pool's availability touches (PART2 §1)."""
    return {channel: [] for channel in Pieces(definition).channels}


def assembly(definition, made_from, world_id):
    """`inputs.assembly` of a driven run (spec/TABLE.md §3), from what its definition was made from
    (the resolution's inputs.json, as the run recorded it)."""
    of_position = driven_cells(definition)
    entry = next(w for w in made_from["worlds"] if w["world"] == world_id)
    switches = unswitched(definition)
    for row in entry["switches"]:
        for channel in made_from["pools"][row["pool"]]["channels"]:
            switches[channel].append([row.get("declared", row["time"]), row["level"]])
    observed = {pool["observable"] for pool in made_from["pools"]}
    return {
        "assembly_observable": label(observed.pop()) if len(observed) == 1 else sorted(observed),
        "composed_file_fingerprint": made_from["composed_file_sha256"],
        "pool_seeds": {of_position[k]: pool["seed"] for k, pool in enumerate(made_from["pools"])},
        "switch_list": switches,
    }


def submitted_assembly(submitted, definition, composed_sha256):
    """`inputs.assembly` of a driven run that the engine refused before it had a schedule: what its
    composed file submits."""
    of_position = driven_cells(definition)
    pools = submitted["pools"]
    observed = {label(pool["observable"]) for pool in pools}
    return {
        "assembly_observable": observed.pop() if len(observed) == 1 else sorted(observed),
        "composed_file_fingerprint": composed_sha256,
        "pool_seeds": {of_position[k]: p["pool"].get("seed") for k, p in enumerate(pools)},
        "switch_list": unswitched(definition),
    }


# ------------------------------------------------------------------ ionic runs


def arrays_of(attempt):
    """A run's recorded arrays: its trajectory, or the rows a refused run keeps; None without."""
    for name in ("output/trajectory.npz", PARTIAL):
        path = attempt / name
        if path.is_file():
            with np.load(path, allow_pickle=False) as archive:
                return {key: archive[key] for key in archive.files}
    return None


def trajectory(world, run, record, attempt, definition):
    """The rows and potentials of an ionic run's entry, at the registered times its rows match."""
    arrays = arrays_of(attempt)
    if arrays is None:
        return {"t": [], "rows": {}, "potential_t": [], "potentials": {}, "steps": 0}
    times = arrays["accepted_times"].tolist()
    start = -math.inf if run.restart_time is None else record["restart"]["time_s"]
    wanted = [t for t in world.row_times if t >= start - MATCH_S]
    found = matched(times, wanted)
    observed = arrays["observation_times"].tolist()
    wanted_potentials = [t for t in world.potential_times if t > start + MATCH_S]
    seen = matched(observed, wanted_potentials)
    if record["status"] == "completed":
        # A row at a restart's checkpoint is optional; every other registered time is there.
        for what, want, have in (("row", wanted, found), ("potential", wanted_potentials, seen)):
            lost = [want[k] for k in range(len(want)) if k not in have]
            if lost:
                raise ExportError(f"{run.name!r} has no {what} at {lost[0]!r} s")
    indices = [found[k] for k in sorted(found)]
    places = [seen[k] for k in sorted(seen)]
    return {
        "t": [times[i] for i in indices],
        "rows": readouts.rows(definition, arrays, indices) if indices else {},
        "potential_t": [observed[i] for i in places],
        "potentials": readouts.potentials(definition, arrays, places) if places else {},
        "steps": len(times) - 1,
    }


def ionic_entry(world, run, record, attempt):
    submitted = read(attempt / "submitted.json")
    definition = ionic_definition(attempt)
    manifest = read(attempt / "output/manifest.json") or {}
    parsed = record["definition"].get("fingerprint")
    if manifest.get("definition_sha256", parsed) != parsed:
        raise ExportError("the engine's record is of another definition than the one parsed")
    inputs, declared = readable(block, definition), declared_strings(definition)
    shown = {"ionic": definition} | readable(beyond, definition)
    if run.kind == DRIVEN:
        made_from = manifest.get("provenance", {}).get("inputs") or read(attempt / "inputs.json")
        if made_from is not None:
            inputs["assembly"] = assembly(definition, made_from, run.world_id)
            own = [w for w in made_from["worlds"] if w["world"] == run.world_id]
            kept = {k: v for k, v in made_from.items() if k != "definitions_sha256"}
            shown["made_from"] = kept | {"worlds": own}
        else:
            sha256 = digest(attempt / "submitted.json")
            inputs["assembly"] = readable(submitted_assembly, submitted, definition, sha256)
        declared = sorted({*declared, *(p["observable"] for p in submitted["pools"])})
    return trajectory(world, run, record, attempt, definition) | {
        "inputs": inputs,
        "strings": strings(declared),
        "declared_strings": declared,
        "definition": shown,
        "checks": read(attempt / "output/summary.json") or {},
        "pool": None,
        "path": None,
    }


# ------------------------------------------------------------------ pool runs


def pool_path(folder, definition, parent=None):
    """{world ID: [[time, availability], ...]}: the events that a pool's run committed, in order,
    with the availability after each, by the registered observable and 1 where it holds.

    parent: the checkpoint's event counts that a resumed run started from."""
    law = observables.resolve(LABELS["assembly_observable"])
    chunks = []
    for path in sorted(folder.glob("events-*.npz")):
        with np.load(path, allow_pickle=False) as saved:
            chunks.append([saved[k] for k in ("time_s", "occupied", "bonds", "free", "event")])
    state, out = pool_state(folder / "checkpoint"), {}
    trace = joined(chunks) if chunks else None
    for world in range(definition["worlds"]):
        rows = [] if trace is None else np.flatnonzero(trace.event[:, world] >= 0)
        before = 0 if parent is None else int(parent[world])
        if len(rows) != int(state.event_count[world]) - before:
            raise ExportError(f"{folder}: its recorded events are not its checkpoint's")
        held = []
        if len(rows):
            values = law.evaluate(*(getattr(trace, n)[rows, world] for n in law.reads), xp=np)
            held = [int(law.values[int(v)] == "true") for v in values]
        times = [] if trace is None else trace.time_s[rows, world].tolist()
        out[str(definition["world_id_start"] + world)] = [
            [t, a] for t, a in zip(times, held, strict=True)
        ]
    return out


def pool_state(checkpoint):
    """The arrays of a pool's checkpoint, as its manifest lists them. Read as data, so that a table
    can be made by a tree that did not make the run."""
    path = checkpoint / "state.npz"
    if digest(path) != read_json(checkpoint / "manifest.json")["state_sha256"]:
        raise ExportError(f"{checkpoint}: its arrays are not what its manifest lists")
    with np.load(path, allow_pickle=False) as archive:
        return PoolState(*(archive[name] for name in PoolState._fields))


def pool_arrays(folder):
    """{array: nested lists [world, ...]} of a pool run's final state, the live pool's fields."""
    state = pool_state(folder / "checkpoint")
    return {name: getattr(state, name).tolist() for name in PoolState._fields}


def pool_block(definition):
    """The pool block of a parsed pool definition (SPEC §2.5): its own fields, without the seed and
    the harness, with a label for its model and its topology."""
    return {
        key: label(value) if key in ("model", "topology") else value
        for key, value in definition.items()
        if key not in (*HARNESS, "seed")
    }


def pool_entry(run, record, attempt):
    """A pool run's entry. Its composed file says which channel each pool drives and its position;
    each pool's own registration says what ran."""
    submitted = read(attempt / "submitted.json")
    definition = submitted_ionic(submitted)
    inside = driven_cells(definition)
    inputs, arrays, paths, ran, checks = {}, {}, {}, {}, {}
    for k, entry in enumerate(submitted["pools"]):
        cell, folder = inside[k], attempt / f"output/pools/pool-{k:03}"
        registration = read(folder / "registration.json") or {}
        own = registration.get("definition", entry["pool"])
        channels = entry["channels"]
        inputs[cell] = {
            "channel": channels[0] if len(channels) == 1 else channels,
            "stream_id": k,
            "seed": own.get("seed"),
            "pool": pool_block(own),
        }
        ran[cell] = own
        result = read(folder / "result.json")
        if result is None:
            continue
        checks[cell] = result
        first = attempt / f"output/first-leg-{k:03}/checkpoint"
        parent = pool_state(first).event_count if run.restart_time is not None else None
        arrays[cell] = {"arrays": pool_arrays(folder), "seed": own["seed"], "stream_id": k}
        paths[cell] = pool_path(folder, own, parent)
    observed = {pool["observable"] for pool in submitted["pools"]}
    declared = sorted({*declared_strings(*ran.values()), *observed})
    return {
        "steps": None,
        "t": [],
        "rows": {},
        "potential_t": [],
        "potentials": {},
        "pool": arrays,
        "path": paths,
        "inputs": inputs,
        "strings": strings(declared),
        "declared_strings": declared,
        "definition": {"pools": ran, "composed": submitted},
        "checks": checks,
    }


# ------------------------------------------------------------------ one entry


def verified(folders, run, record):
    """A record's attempt, its files as the record lists them."""
    attempt = folders.attempt(run)
    for name, sha256 in record["files_sha256"].items():
        path = attempt / name
        if not path.is_file() or digest(path) != sha256:
            raise ExportError(f"{run.name!r}: {name} is not what its record lists")
    resolution = record["resolution"]
    if resolution is not None:
        path = folders.root / resolution["record"]
        if not path.is_file() or digest(path) != resolution["record_sha256"]:
            raise ExportError(f"{run.name!r}: its resolution is not what its record lists")
    return attempt


def empty(run, record):
    """The entry of a run that has nothing but its record: a crash, or a fault of the exporter."""
    return {
        "steps": None if run.kind == POOL else 0,
        "t": [],
        "rows": {},
        "potential_t": [],
        "potentials": {},
        "pool": None,
        "path": None,
        "inputs": {},
        "strings": {},
        "declared_strings": [],
        "definition": {},
        "checks": {},
    }


def unknown_source(record):
    """`source` of a run whose record has none: what its driver knew of it."""
    return {name: kind() for name, kind in SOURCE.items()} | (record["driver_source"] or {})


def entry(inputs, run, folders):
    """A run's entry of its table (spec/TABLE.md §3), from its record; None where it has none."""
    record = folders.record(run)
    if record is None:
        return None
    refusal, status = record["refusal"], record["status"]
    try:
        if record["run"] != run.name or record["inputs"]["sha256"] != inputs.sha256:
            raise ExportError(f"its record is of {record['run']!r}, or of other inputs")
        if record["options"]["off_grid"] and not run.invented:
            raise ExportError("off_grid: a registered run is never made with --off-grid")
        attempt = verified(folders, run, record)
        if not (attempt / "submitted.json").is_file():
            made = empty(run, record)
        elif run.kind == POOL:
            made = pool_entry(run, record, attempt)
        else:
            made = ionic_entry(inputs.worlds[run.world], run, record, attempt)
    except Exception as error:  # The exporter's own fault is no pass: the run is refused by it.
        made, status = empty(run, record), "refused"
        message = f"export: {type(error).__name__}: {error}"
        refusal = {"kind": "harness", "message": message, "time_s": None}
    path = folders.run(run) / RECORD
    out = {
        "status": status,
        "world": run.world,
        "variant": run.variant,
        "seed_index": run.seed_index,
        "world_id": run.world_id,
        "step_s": run.step_s,
        "steps": made["steps"],
        "t": made["t"],
        "rows": made["rows"],
        "potential_t": made["potential_t"],
        "potentials": made["potentials"],
        "pool": made["pool"],
        "path": made["path"],
        "inputs": made["inputs"],
        "strings": made["strings"],
        "declared_strings": made["declared_strings"],
        "definition": made["definition"],
        "checks": made["checks"],
        "restart": record["restart"],
        "host_patch": None,
        "refusal": refusal,
        "source": record["source"] or unknown_source(record),
        "record": str(path.relative_to(folders.root)),
        "record_sha256": digest(path),
    }
    if record["options"]["off_grid"]:  # An extra key: absent, the switch was off (Amendment 1).
        out[OFF_GRID] = True
    return out


# ------------------------------------------------------------------ the tables


def tables(inputs, folders, *, owed=None):
    """{consumer: its table}; with `owed`, the retry's runs alone."""
    runs = list(inputs.runs.values()) if owed is None else list(inputs.owed(owed))
    early = [r.name for r in runs if r.retry and not folders.held and folders.made_early(r)]
    if early:
        raise ExportError(f"{early[0]!r} was made up front: it needs the sha256 of the retry note")
    out = {}
    for run in runs:
        table = out.setdefault(
            run.consumer,
            {
                "kind": KIND,
                "part": inputs.part,
                "consumer": run.consumer,
                "runs": {},
                "missing": [],
                "units": UNITS,
            },
        )
        made = entry(inputs, run, folders)
        if made is None:
            table["missing"].append(run.name)
        else:
            table["runs"][run.name] = made
    return out


def text(table):
    """A table's JSON: one line for each run, every double as its repr."""
    head = {key: value for key, value in table.items() if key != "runs"}
    lines = [f" {json.dumps(name)}: {json.dumps(run)}" for name, run in table["runs"].items()]
    body = json.dumps(head)[:-1] + ', "runs": {\n' + ",\n".join(lines) + "\n}}\n"
    return body


def write(found, output):
    """The tables and their SHA256SUMS in a new folder."""
    output.mkdir(parents=True)
    for consumer, table in found.items():
        with (output / f"table_{consumer}.json").open("x") as stream:
            stream.write(text(table))
    write_sums(output)


def write_sums(output):
    """SHA256SUMS of a folder's tables: the sha256, two spaces, the name."""
    lines = [f"{digest(path)}  {path.name}\n" for path in sorted(output.glob("table_*.json"))]
    with (output / SUMS).open("x") as stream:
        stream.writelines(lines)


# ------------------------------------------------------------------ the contract's keys and types


TOP = {"kind", "part", "consumer", "runs", "missing", "units"}
ENTRY = {
    "status",
    "world",
    "variant",
    "seed_index",
    "world_id",
    "step_s",
    "steps",
    "t",
    "rows",
    "potential_t",
    "potentials",
    "pool",
    "path",
    "inputs",
    "strings",
    "declared_strings",
    "definition",
    "checks",
    "restart",
    "host_patch",
    "refusal",
    "source",
    "record",
    "record_sha256",
}
ASSEMBLY = {"assembly_observable", "composed_file_fingerprint", "pool_seeds", "switch_list"}
KINDS = ("definition", "domain", "check", "harness")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite(value):
    return _is_number(value) and math.isfinite(value)


def entry_faults(name, e, *, retried=False):
    """Where one run's entry is not the contract's shape (spec/TABLE.md §3 and §4)."""
    out = []

    def need(condition, what):
        if not condition:
            out.append(f"{name}: {what}")

    need(ENTRY <= set(e), f"keys missing: {sorted(ENTRY - set(e))}")
    if not ENTRY <= set(e):
        return out
    is_pool = e["step_s"] is None
    need(e["status"] in ("completed", "refused"), "status")
    need((e["refusal"] is None) == (e["status"] == "completed"), "refusal beside its status")
    need(isinstance(e["world"], str), "world")
    for key in ("variant",):
        need(e[key] is None or isinstance(e[key], str), key)
    for key in ("seed_index", "world_id"):
        need(e[key] is None or type(e[key]) is int, key)
    need(is_pool or _finite(e["step_s"]), "step_s")
    need((e["steps"] is None) == is_pool and (is_pool or type(e["steps"]) is int), "steps")
    for key in ("t", "potential_t"):
        need(isinstance(e[key], list) and all(_finite(t) for t in e[key]), key)
        need(all(b > a for a, b in zip(e[key], e[key][1:], strict=False)), f"{key} increases")
    for key, times in (("rows", "t"), ("potentials", "potential_t")):
        for readout, held in e[key].items():
            for entity, values in held.items():
                where = f"{key} {readout} {entity}"
                need(len(values) == len(e[times]), f"{where}: its length")
                need(all(_is_number(v) for v in values), f"{where}: numbers")
    if is_pool:
        need(e["t"] == [] and e["rows"] == {} and e["potentials"] == {}, "a pool run's rows")
        need(isinstance(e["pool"], dict) and isinstance(e["path"], dict), "pool and path")
        for cell, held in (e["pool"] or {}).items():
            need(set(held) == {"arrays", "seed", "stream_id"}, f"pool {cell}")
            need(set(held["arrays"]) == set(PoolState._fields), f"pool {cell}: its arrays")
        for cell, held in (e["path"] or {}).items():
            for world, events in held.items():
                need(isinstance(world, str), f"path {cell}: a world ID is a string")
                for row in events:
                    need(len(row) == 2 and all(_finite(v) for v in row), f"path {cell} {world}")
    else:
        need(e["pool"] is None and e["path"] is None, "an ionic run's pool and path")
    if not is_pool and "assembly" in e["inputs"]:
        need(set(e["inputs"]["assembly"]) == ASSEMBLY, "inputs.assembly")
    restart = e["restart"]
    need(
        restart is None or set(restart) == {"time_s", "step_index", "through"},
        "restart",
    )
    if not is_pool and e["t"]:
        need((restart is not None) == (e["t"][0] != 0.0), "t's first time")
    need(e["host_patch"] is None, "host_patch")
    if e["refusal"] is not None:
        need({"kind", "message", "time_s"} <= set(e["refusal"]), "refusal's keys")
        need(e["refusal"]["kind"] in KINDS, "refusal's kind")
        time = e["refusal"]["time_s"]
        need((time is not None) == (e["refusal"]["kind"] == "check"), "refusal's time_s")
        need(time is None or _finite(time), "refusal's time_s is a number")
        if SECOND_PASS in e["refusal"]:  # True and of a check, or absent.
            own = e["refusal"]["kind"] == "check" and e["refusal"][SECOND_PASS] is True
            need(own, f"refusal's {SECOND_PASS}")
    need(set(e["source"]) == set(SOURCE), "source")
    for key, kind in SOURCE.items():
        need(type(e["source"].get(key)) is kind, f"source.{key}")
    need(e["declared_strings"] == sorted(set(e["declared_strings"])), "declared_strings")
    need(set(e["strings"].values()) <= set(e["declared_strings"]), "strings")
    need(isinstance(e["record"], str), "record")
    sha = e["record_sha256"]
    need(isinstance(sha, str) and len(sha) == 64 and not set(sha) - set("0123456789abcdef"), "sha")
    need("retry" in name or not retried, "a retry's name")
    return out


def table_faults(table):
    """Where a table is not the contract's (spec/TABLE.md §2 and §3)."""
    out = [] if set(table) >= TOP else [f"keys missing: {sorted(TOP - set(table))}"]
    if out:
        return out
    if table["kind"] != KIND:
        out.append("kind")
    if type(table["part"]) is not int or not isinstance(table["consumer"], str):
        out.append("part and consumer")
    if table["units"] != UNITS:
        out.append("units")
    if not isinstance(table["missing"], list) or set(table["missing"]) & set(table["runs"]):
        out.append("missing")
    for name, made in table["runs"].items():
        out += entry_faults(name, made)
    return out


def string_faults(table, note):
    """Where the runs of a table do not declare what a strings note lists (spec/TABLE.md §5); a
    retry's, what its family's runs are listed with."""
    out = []
    for name, made in table["runs"].items():
        listed = note["runs"].get(name)
        if listed is None and name.endswith(" retry"):
            family = name.rsplit(" h=", 1)[0] + " h="
            listed = next((v for k, v in note["runs"].items() if k.startswith(family)), None)
        if listed is None:
            out.append(f"{name}: the note lists no such run")
            continue
        names = {v for v in (listed[k] for k in ("model", "solver", "field_solver")) if v}
        for key in ("operators", "kinds", "laws", "pool"):
            names |= set(listed[key])
        if listed.get("observable"):
            names.add(listed["observable"])
        expected = {n: note["labels"].get(n) for n in names}
        if made["strings"] != expected:
            out.append(f"{name}: strings {sorted(made['strings'])} and not {sorted(expected)}")
        if set(made["declared_strings"]) != set(expected.values()):
            out.append(f"{name}: declared_strings")
    return out


def check(folder, note=None):
    """The faults of a folder of tables: their sums, their shape and, with a note, their strings."""
    out, sums = [], {}
    if (folder / SUMS).is_file():
        for line in (folder / SUMS).read_text().splitlines():
            sha256, name = line.split("  ", 1)
            sums[name] = sha256
    for path in sorted(folder.glob("table_*.json")):
        if sums.get(path.name) != digest(path):
            out.append(f"{path.name}: its sha256 is not in {SUMS}")
        table = read_json(path)
        out += [f"{path.name}: {fault}" for fault in table_faults(table)]
        if note is not None:
            out += [f"{path.name}: {fault}" for fault in string_faults(table, note)]
    return out


def open_folders(args):
    """The folders of the records to export. The retry's, made up front, are opened by the sha256 of
    the judge's note alone."""
    if args.owed_sha256 is None:
        return Folders(args.runs)
    if args.owed is None or digest(args.owed) != args.owed_sha256:
        raise ExportError("--owed-sha256 is not the sha256 of the retry note that --owed names")
    return Folders(args.runs, held=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="write the tables of a campaign's records")
    export.add_argument("--inputs", type=Path, default=REGISTERED)
    export.add_argument("--runs", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True, help="a new folder")
    export.add_argument("--owed", type=Path, help="the judge's retry_owed.json: the retry's tables")
    export.add_argument("--owed-sha256", help="its sha256: opens the runs made up front")
    checked = commands.add_parser("check", help="hold a folder of tables to the contract")
    checked.add_argument("folder", type=Path)
    checked.add_argument("--strings", type=Path, help="the strings note")
    args = parser.parse_args(argv)
    if args.command == "export":
        try:
            found = tables(Inputs(args.inputs), open_folders(args), owed=args.owed)
        except ExportError as error:
            print(f"refused: {error}", file=sys.stderr)
            return 2
        write(found, args.output)
        faults = check(args.output)
        for consumer, table in found.items():
            refused = [n for n, e in table["runs"].items() if e["status"] == "refused"]
            shown = {"consumer": consumer, "runs": len(table["runs"]), "refused": refused}
            print(json.dumps(shown | {"missing": table["missing"]}))
    else:
        faults = check(args.folder, None if args.strings is None else read_json(args.strings))
    print(json.dumps({"faults": faults}, indent=1))
    return 1 if faults else 0


if __name__ == "__main__":
    raise SystemExit(main())
