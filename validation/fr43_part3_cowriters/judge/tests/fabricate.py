"""Fabricated engine tables for the judge's self-tests. No engine and no physics: an honest run is a reference
copy's own values plus a smooth error of the declared order in the step, made at test time and never committed.

- Books (and event times) carry r × A × e_round(h_n) × (h/h_n)^p, r a fixed pseudo-random factor per family, copy
  and entry; p = 2 (3 for the gene unit's own `made` and `exits`, far below resolution); the Lie runs' event times
  carry first order.
- Rows are re-derived from the start values and the books through the world's identities, so every identity holds
  to rounding; W5-exact's event times are the reference's.
- `fabricate()` returns the tables as Python objects; `write()` writes them with SHA256SUMS.
"""

from __future__ import annotations

import copy as copy_module
import hashlib
import json
import os
import random
from typing import Any

from cowriter_judge.echo import registered_echo
from cowriter_judge.registry import M_ROW, M_TIME, Inputs, RunSpec, e_round, steps
from cowriter_judge.table import LIE_PATCH_ID, TABLE_KIND, UNITS

BOOKS = {"reactions": ["xi_1", "xi_2", "moved"], "gene": ["inits", "exits", "made", "lost", "moved"]}
AMPLITUDE = 300.0
REVISION = "f" * 40


def _factor(*key: Any) -> float:
    rng = random.Random(hashlib.sha256(repr(key).encode()).hexdigest())
    return rng.choice([-1.0, 1.0]) * rng.uniform(0.5, 1.5)


def _rows_from_books(inputs: Inputs, world_name: str, start: dict[str, float], books: dict[str, list[float]],
                     reference_rows: dict[str, list[float]]) -> dict[str, list[float]]:
    world = inputs.worlds[world_name]
    n = len(world.samples)
    if world.kind == "reactions":
        x1, x2, mv = books["xi_1"], books["xi_2"], books["moved"]
        return {
            "n_S_c": [start["n_S_c"] + x1[i] - x2[i] - mv[i] for i in range(n)],
            "n_S_o": [start["n_S_o"] + mv[i] for i in range(n)],
            "n_X": [start["n_X"] - x1[i] for i in range(n)],
            "n_Y": [start["n_Y"] - x2[i] for i in range(n)],
            "n_W": [start["n_W"] + x2[i] for i in range(n)],
            **books,
        }
    r, big_l = inputs.gene_r_and_l(world_name)
    inits, exits, made, lost, mv = (books[k] for k in ("inits", "exits", "made", "lost", "moved"))
    engaged = [inits[i] - made[i] for i in range(n)]
    return {
        "n_R_c": [start["n_R_c"] + made[i] - lost[i] - mv[i] for i in range(n)],
        "n_R_o": [start["n_R_o"] + mv[i] for i in range(n)],
        "n_N": [start["n_N"] - r * exits[i] for i in range(n)],
        "n_Pi": [start["n_Pi"] + 2 * r * exits[i] for i in range(n)],
        "n_M": [start["n_M"] + big_l * lost[i] for i in range(n)],
        "engaged": engaged,
        "free": [start["free"] - engaged[i] for i in range(n)],
        "transit": [r * exits[i] - big_l * made[i] for i in range(n)],
        **books,
    }


def honest_entry(inputs: Inputs, reference: dict, spec: RunSpec, operators: dict[str, list[str]],
                 lie: bool = False) -> dict:
    world = inputs.worlds[spec.world]
    fam = inputs.families[spec.family]
    ref = reference["copies"][spec.copy]
    h_n = fam.rungs[-1]
    h = spec.step
    exact = "t_events" in world.judged.get("R", [])
    start = {name: inputs.start_value(spec.world, name) for name in world.start}
    books = {}
    sizing = reference["sizing"].get(spec.family, {})
    s_books = [sizing[n]["E"] for n in BOOKS[world.kind] if n in sizing and n not in world.at_rounding()]
    for name in BOOKS[world.kind]:
        scale = reference["scales"][name]
        p = 3 if name in world.at_rounding() else 2
        if name in sizing:  # the expected honest E_n of the references' sizing
            amp = sizing[name]["E"]
        elif s_books:
            amp = max(s_books)
        else:
            amp = AMPLITUDE * e_round(M_ROW, steps(world.end_s, h_n), scale)
        values = []
        for i, t in enumerate(world.samples):
            base = ref["series"][name]["value"][i]
            if t == 0:
                values.append(start[name])
                continue
            values.append(base + _factor(spec.family, spec.copy, name, i) * amp * (h / h_n) ** p)
        books[name] = values
    series = _rows_from_books(inputs, spec.world, start, books, {})
    times = list(ref["events"]["time_s"])
    if not exact:
        amp_t = sizing["t_events"]["E"] if "t_events" in sizing else AMPLITUDE * e_round(
            M_TIME, steps(world.end_s, h_n), world.end_s)
        order = 1 if lie else 2
        if lie:  # the Lie emulation's error at its finest rung (the references' mutant), first order
            amp_t = reference["sizing"]["mutant"][spec.family]["E"][-1]
        times = [t + _factor(spec.family, spec.copy, "t", k) * amp_t * (h / h_n) ** order for k, t in enumerate(times)]
    keep = [k for k, t in enumerate(times) if t <= world.end_s]
    entry = {
        "status": "completed",
        "world": spec.world,
        "first": spec.first,
        "copy": spec.copy,
        "step_s": spec.raw["step_s"],
        "steps": int(steps(world.end_s, h)),
        "variant": spec.variant,
        "seed": world.seeds[spec.copy],
        "t": list(world.samples),
        "series": series,
        "events": {
            "time_s": [times[k] for k in keep],
            "channel": [ref["events"]["channel"][k] for k in keep],
            "counts_after": [list(ref["events"]["counts_after"][k]) for k in keep],
            "first_index": 0,
        },
        "events_total": len(keep),
        "trace_capacity": 100000,
        "integer_ledger": [world.ledger_total] * len(world.samples),
        "samples_echo": list(world.samples),
        "operators": list(operators[spec.family]),
        "inputs": registered_echo(inputs, spec),
        "definition": {"fabricated": True},
        "checks": {"fabricated": True},
        "pools_at_event": None,
        "restart": None,
        "host_patch": {"id": LIE_PATCH_ID, "change": "second halves in declared order"} if lie else None,
        "refusal": None,
        "source": {"engine_revision": REVISION, "checkout_dirty": False, "snapshot": "fabricated",
                   "snapshot_patch_sha256": "0" * 64, "python": "3", "numpy": "2", "scipy": "1", "jax": "0",
                   "blas_threads": 1, "machine": "fabricated"},
        "record": f"records/{spec.name}.json",
        "record_sha256": hashlib.sha256(spec.name.encode()).hexdigest(),
    }
    return entry


def restart_entry(inputs: Inputs, uninterrupted: dict, spec: RunSpec) -> dict:
    world = inputs.worlds[spec.world]
    time_s = float(inputs.data["restart"][spec.world]["time_s"])
    entry = copy_module.deepcopy(uninterrupted)
    keep = [i for i, t in enumerate(world.samples) if t >= time_s]
    entry["t"] = [world.samples[i] for i in keep]
    entry["series"] = {k: [v[i] for i in keep] for k, v in uninterrupted["series"].items()}
    entry["integer_ledger"] = [uninterrupted["integer_ledger"][i] for i in keep]
    ev = uninterrupted["events"]
    first = sum(1 for t in ev["time_s"] if t <= time_s)
    entry["events"] = {"time_s": ev["time_s"][first:], "channel": ev["channel"][first:],
                       "counts_after": ev["counts_after"][first:], "first_index": first}
    entry["variant"] = spec.variant
    entry["restart"] = {"time_s": time_s, "step_index": int(steps(time_s, spec.step)), "through": "fabricated"}
    entry["record"] = f"records/{spec.name}.json"
    entry["record_sha256"] = hashlib.sha256(spec.name.encode()).hexdigest()
    return entry


def refused_entry(inputs: Inputs, spec: RunSpec, operators: dict[str, list[str]], kind: str) -> dict:
    world = inputs.worlds[spec.world]
    names = list(BOOKS[world.kind])
    entry = {
        "status": "refused", "world": spec.world, "first": spec.first, "copy": spec.copy, "step_s": spec.raw["step_s"],
        "steps": 0, "variant": spec.variant, "seed": world.seeds[spec.copy], "t": [],
        "series": {name: [] for name in _rows_from_books(inputs, spec.world, {n: 0.0 for n in world.start},
                                                         {n: [0.0] * len(world.samples) for n in names}, {})},
        "events": {"time_s": [], "channel": [], "counts_after": [], "first_index": 0}, "events_total": 0,
        "trace_capacity": 100000, "integer_ledger": [], "samples_echo": list(world.samples), "operators": [],
        "inputs": None, "definition": None, "checks": {}, "pools_at_event": None, "restart": None,
        "host_patch": None, "refusal": {"kind": kind, "message": "fabricated", "time_s": 0.0},
        "source": {"engine_revision": REVISION, "checkout_dirty": False, "snapshot": "fabricated",
                   "snapshot_patch_sha256": "0" * 64, "python": "3", "numpy": "2", "scipy": "1", "jax": "0",
                   "blas_threads": 1, "machine": "fabricated"},
        "record": f"records/{spec.name}.json", "record_sha256": hashlib.sha256(spec.name.encode()).hexdigest(),
    }
    return entry


def operators_for(inputs: Inputs) -> dict[str, list[str]]:
    out = {}
    for fam_id, fam in inputs.families.items():
        writer = "writer_" + inputs.worlds[fam.world].kind
        out[fam_id] = [writer, "population"] if fam.first != "population" else ["population", writer]
    return out


def fabricate(inputs: Inputs, references: dict[str, dict], retry_families: tuple[str, ...] = ()) -> dict:
    """{table file name: table object}, for every registered run (and the retry runs of `retry_families`)."""
    operators = operators_for(inputs)
    tables: dict[str, dict] = {}
    retry_tables: dict[str, dict] = {}
    entries: dict[str, dict] = {}
    for spec in inputs.run_list:
        if spec.role == "judged" or spec.role == "plant":
            entries[spec.name] = honest_entry(inputs, references[spec.world], spec, operators,
                                              lie=spec.variant == "second halves in declared order")
    for spec in inputs.run_list:
        if spec.variant == "restart":
            unint = inputs.data["restart"][spec.world]["run"]
            entries[spec.name] = restart_entry(inputs, entries[unint], spec)
        elif spec.role == "support":
            entries[spec.name] = refused_entry(inputs, spec, operators,
                                               "definition" if spec.variant == "refused" else "domain")
    for arm, world in inputs.arms.items():
        runs = {spec.name: entries[spec.name] for spec in inputs.run_list if spec.world == world}
        tables[f"table_{world}.json"] = {"kind": TABLE_KIND, "arm": arm, "runs": runs, "missing": [],
                                         "units": dict(UNITS)}
    for fam_id in retry_families:
        fam = inputs.families[fam_id]
        runs = {}
        for c in range(inputs.worlds[fam.world].copies):
            spec = inputs.retry_spec(fam_id, c)
            runs[spec.name] = honest_entry(inputs, references[fam.world], spec, operators)
        name = f"table_{fam.world}-retry.json"
        arm = [a for a, w in inputs.arms.items() if w == fam.world][0]
        block = retry_tables.setdefault(name, {"kind": TABLE_KIND, "arm": arm, "runs": {}, "missing": [],
                                               "units": dict(UNITS)})
        block["runs"].update(runs)
    return {"tables": tables, "retry": retry_tables, "operators": operators}


def write(folder: str, tables: dict[str, Any], raw_text: dict[str, str] | None = None) -> dict[str, str]:
    """Write each table and SHA256SUMS; `raw_text` gives a file's exact text instead (for planted parse faults)."""
    os.makedirs(folder, exist_ok=True)
    sums = {}
    for name, table in tables.items():
        text = raw_text[name] if raw_text and name in raw_text else json.dumps(table)
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write(text)
        sums[name] = hashlib.sha256(text.encode()).hexdigest()
    with open(os.path.join(folder, "SHA256SUMS"), "w", encoding="utf-8") as handle:
        for name in sorted(sums):
            handle.write(f"{sums[name]}  {name}\n")
    return sums
