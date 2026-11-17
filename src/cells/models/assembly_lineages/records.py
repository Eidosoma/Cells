"""Run records of assembly lineages: one bundle per run (GARD_DESIGN §5.1, §5.2, §5.4).

A bundle is a new directory (never overwritten) holding:

- world.json (WORLD_FORMAT): the world record, with its id, the SHA-256 of its canonical JSON.
  Two runs of one world write the same bytes and name the same id;
- run.json (RUN_FORMAT): the run record (below);
- records.npz: the arrays, each declared in run.json's `records`;
- resolved_config.json: the definition; summary.json: how the run ended;
- manifest.json, written last: every file's SHA-256, the runtime and the source, as io.write_run
  writes it (its helpers are used here, so the conventions are the engine's).

The run record states, per GARD_DESIGN §5.4: the world's id and that the run uses the world's
founder; the law (the rate factor's ID and `form`, single-event or pair-consistent, beside it; its
energy role and the kernel's check; the exchange law); the engine's source revision (from the
execution snapshot's record, or unstated with the reason); the registered model, law and operator
IDs; the mode; the random streams' identity; the SSA convention; the ledger's conventions and its
closure; the operators' rules; and each array's axes, unit, kind, monotonicity, layer and owner,
in the run view's vocabulary (docs/RUN_VIEW_DESIGN.md §3; the view itself waits for its owner,
GARD_DESIGN §5.3).

A pair of law forms (write_pair) is a directory with pair.json and one bundle per form. It is
refused unless the two runs share the world (so its founder), the experiment and the execution,
streams included, and differ in the law alone.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from cells.core.specs import ConfigError, digest
from cells.models.assembly_lineages import (
    EXCHANGE_LAW,
    MODEL_ID,
    continuation,
    factors,
    fission,
    kernel,
    keys,
    ledger,
    model,
)
from cells.models.assembly_lineages import exchange as exchange_law
from cells.models.assembly_lineages import spec as lineage_spec

WORLD_FORMAT = "cells.assembly_lineages.world@1"
RUN_FORMAT = "cells.assembly_lineages.run@1"
PAIR_FORMAT = "cells.assembly_lineages.pair@1"
ARRAYS = "records.npz"
# The clock's unit is the world's (spec.Units: "nominal", GARD's, or "s"); RECORDS names it CLOCK,
# and run_record writes the world's unit in its place.
CLOCK = "clock"

LAYERS = (
    {"id": "assemblies", "label": "Assemblies and their exchange", "representation": "simulated"},
    {"id": "lineage", "label": "Fission and continuation", "representation": "prescribed"},
)
BASES = {
    "row": "single lineage: the run's start (row_kind start: the founder, or the state a run from "
    "a checkpoint continues); per fission the parent before the split (parent) and the followed "
    "daughter after it (daughter), both at the fission's time, so the row saved at a fission's "
    "time holds the state before it; and always a final row (end), the lineage's state when the "
    "run ended. Every descendant: two rows per life in lives order, its birth (start for the "
    "founder, daughter otherwise) and its end (parent if it divided, end otherwise). Each row's "
    "assembly is `occupant`; cumulative records are its lineage path's, from the founder. "
    "Times: row_time",
    "fission": "one entry per fission: in order along the lineage (single lineage), or in lives "
    "order of the parents (every descendant). Times: fission_time",
    "event": "one entry per committed event, in order (the event trace): grouped by growth, "
    "growth by growth. Times: event_time",
    "growth": "one entry per life that ran in this run, from its birth (or the run's start) to "
    "its end (or the run's end), in lives order: single lineage, the slot's occupants; every "
    "descendant, every life (0 events for a life that never ran). growth_carrier names it",
    "life": "one entry per life: a birth and its end, in the order (generation, parent key, "
    "daughter index) (keys.py, the lives table)",
}
ROW_KINDS = {"0": "start", "1": "parent", "2": "daughter", "3": "end"}
_M, _X, _C = MODEL_ID, EXCHANGE_LAW, continuation.CONTINUATION
_F = fission.FISSION


def _record(base, axes, unit, layer, owner, kind=None, **extra):
    entry = {"base": base, "axes": list(axes), "unit": unit, "layer": layer, "owner": owner}
    if kind is not None:
        entry["kind"] = kind
    entry.update(extra)
    return entry


ROW, TYPE, SLOT = "row", "type", "assembly"
RECORDS = {
    "row_time": _record("row", [ROW], CLOCK, "assemblies", _M, "level"),
    "row_event": _record("row", [ROW], "events", "assemblies", _M, "cumulative", monotone=True),
    "row_kind": _record("row", [ROW], "1", "lineage", _M, "level", legend=ROW_KINDS),
    "row_fission": _record(
        "row",
        [ROW],
        "1",
        "lineage",
        _F,
        "level",
        says="the fission (from 1) a parent or daughter row belongs to; 0 else",
    ),
    "assembly_count": _record("row", [ROW, TYPE, SLOT], "molecules", "assemblies", _M, "amount"),
    "joined_total": _record(
        "row",
        [ROW, TYPE, SLOT],
        "molecules",
        "assemblies",
        _X,
        "cumulative",
        monotone=True,
        says="since the lineage's start",
    ),
    "left_total": _record(
        "row",
        [ROW, TYPE, SLOT],
        "molecules",
        "assemblies",
        _X,
        "cumulative",
        monotone=True,
        says="since the lineage's start",
    ),
    "discarded_total": _record(
        "row",
        [ROW, TYPE, SLOT],
        "molecules",
        "lineage",
        _C,
        "cumulative",
        monotone=True,
        says="material leaving with unfollowed daughters; count = founder + joined - left - "
        "discarded, exactly, at every row",
    ),
    "exchange_heat_kT": _record(
        "row",
        [ROW, SLOT],
        "k_BT",
        "assemblies",
        _X,
        "cumulative",
        monotone=False,
        says=ledger.CONVENTIONS["event_heat"],
    ),
    "fission_work_kT": _record(
        "row",
        [ROW, SLOT],
        "k_BT",
        "lineage",
        _F,
        "cumulative",
        monotone=False,
        says=ledger.CONVENTIONS["fission_work"],
    ),
    "discarded_free_energy_kT": _record(
        "row",
        [ROW, SLOT],
        "k_BT",
        "lineage",
        _C,
        "cumulative",
        monotone=False,
        says=ledger.CONVENTIONS["sink"],
    ),
    "log_weight": _record(
        "row",
        [ROW, SLOT],
        "k_BT",
        "assemblies",
        _X,
        "level",
        says=ledger.CONVENTIONS["state_function"],
    ),
    "ledger_residual_kT": _record(
        "row", [ROW, SLOT], "k_BT", "assemblies", _M, diagnostic=ledger.CONVENTIONS["closure"]
    ),
    "occupant": _record("row", [ROW, SLOT], "carrier key", "lineage", _C, "level"),
    "generation": _record("row", [ROW, SLOT], "fissions", "lineage", _C, "level"),
    "fission_time": _record("fission", ["fission"], CLOCK, "lineage", _F),
    "fission_slot": _record("fission", ["fission"], "1", "lineage", _F),
    "fission_parent": _record("fission", ["fission"], "carrier key", "lineage", _F),
    "fission_daughters": _record(
        "fission",
        ["fission", "daughter"],
        "carrier key",
        "lineage",
        _F,
        says="the first and the second daughter",
    ),
    "fission_followed": _record(
        "fission",
        ["fission"],
        "1",
        "lineage",
        _C,
        says="0: the first daughter continues; 1: the second",
    ),
    "fission_split": _record(
        "fission",
        ["fission", TYPE],
        "molecules",
        "lineage",
        _F,
        says="the first daughter's counts; the second is the parent less these",
    ),
    "fission_similarity": _record(
        "fission",
        ["fission", "daughter"],
        "1",
        "lineage",
        _F,
        says="H: the cosine of the parent's counts with each "
        "daughter's (NaN for an empty daughter)",
    ),
    "fission_partition_counter": _record(
        "fission",
        ["fission"],
        "1",
        "lineage",
        _F,
        says="the partition stream's counter (keyed by the parent's carrier key)",
    ),
    "event_time": _record("event", ["event"], CLOCK, "assemblies", _M),
    "event_channel": _record(
        "event",
        ["event"],
        "1",
        "assemblies",
        _M,
        says="+(i+1): a molecule of type i joined; -(i+1): one left",
    ),
    "events_per_growth": _record("growth", ["growth"], "events", "assemblies", _M),
    "growth_carrier": _record(
        "growth", ["growth"], "carrier key", "lineage", _C, says="the life whose growth it is"
    ),
    "event_uniforms": _record(
        "event",
        ["event", "draw"],
        "1",
        "assemblies",
        _M,
        diagnostic="(u1, u2) of each committed event",
    ),
    "partition_uniforms": _record(
        "fission",
        ["fission", "place"],
        "1",
        "lineage",
        _F,
        diagnostic="the partition's uniform for each molecule place",
    ),
    "continuation_uniform": _record(
        "fission", ["fission"], "1", "lineage", _C, diagnostic="the continuation stream's draw"
    ),
}
_LIVES = {
    "life_key": ("carrier key", "s * 2**32 + c, written s:c; its id is carrier:a<s>:<c>"),
    "life_slot": (
        "1",
        "the slot it occupies at birth; -1: none (an unfollowed daughter, or "
        "every-descendant mode, which has no slots)",
    ),
    "life_parent": (
        "carrier key",
        "the life it was split from; -1: none (a founder, or a life "
        "continued from a checkpoint, whose parent is in that run)",
    ),
    "life_birth_kind": ("1", "founder, division or continued (run.json lives.birth_kinds)"),
    "life_birth_time": (CLOCK, "the time of its birth (the run's start for a continued life)"),
    "life_birth_event": ("events", "its lineage path's cumulative event count at its birth"),
    "life_birth_fission": ("1", "the fission-table entry that made it; -1: none"),
    "life_end_reason": (
        "1",
        "divided, extinct, not_followed or censored (run.json lives.end_reasons)",
    ),
    "life_censored_by": (
        "1",
        "for a censored life: horizon, event_limit, stalled, budget or "
        "stop (run.json lives.censored_by); empty otherwise",
    ),
    "life_end_time": (CLOCK, "the time its record ends"),
    "life_end_event": ("events", "its lineage path's cumulative event count at its end"),
    "life_end_fission": (
        "1",
        "the fission-table entry that ended it (it divided, or it was "
        "born ended: extinct or not followed); -1: none",
    ),
    "life_generation": ("fissions", "fissions since its founder"),
    "life_root": ("carrier key", "its founder's key"),
    "life_sublineage": (
        "1",
        "the sub-lineage its own daughters' keys come from; -1: it takes "
        "none (it is extinct at birth, or not followed)",
    ),
    "life_size_at_birth": ("molecules", "its molecules at its birth (or at the run's start)"),
}
RECORDS.update(
    {
        name: _record("life", ["life"], unit, "lineage", _C, says=says)
        for name, (unit, says) in _LIVES.items()
    }
)


def world_record(world):
    body = lineage_spec.world_to_dict(world)
    return {
        "format": WORLD_FORMAT,
        "id": digest(body),
        "world": body,
        "derived": {
            "types": list(world.types.ids),
            "identity": "label_only: no catalogue entry and no valence",
            "standard_transfer_mu_RT": list(world.types.standard_transfer_mu_RT),
            "join_rate": list(world.join_rate),
            "leave_rate": list(world.leave_rate),
            "founder_size": sum(world.founder),
        },
    }


def _law(run):
    m = run.spec.model
    exchange = {
        "id": EXCHANGE_LAW,
        "energy_role": exchange_law.LAW.energy_role,
        "formulas": exchange_law.LAW.formulas,
        "provenance": exchange_law.provenance(exchange_law.LAW),
        "interface": exchange_law.LAW.interface,
    }
    if m.rate_factor is None:
        return {"id": None, "form": None, "exchange": exchange, "check": run.verdict}
    law = factors.resolve(m.rate_factor)
    return {
        "id": law.law_id,
        "form": law.form,
        "energy_role": law.energy_role,
        "law_set": law.law_set,
        "comparison_only": law.comparison_only,
        "note": law.note,
        "formulas": law.formulas,
        "provenance": exchange_law.provenance(law),
        "interface": law.interface,
        "check": run.verdict,
        "world_report": run.world_report,
        "exchange": exchange,
    }


def _source():
    from cells.run_view import _engine_source

    source = _engine_source()
    if source is None:
        return {"unstated": "the engine ran from a checkout, not an execution snapshot"}
    return source


def run_record(run, world_id):
    spec = run.spec
    rows = run.rows
    end = {
        "status": run.status,
        "fissions": int(len(run.fissions["fission_time"])),
        "events": int(rows["row_event"][-1]),
        "time": float(rows["row_time"][-1]),
    }
    arrays = sorted(_arrays(run))
    world = spec.model.world
    clock = world.units.time
    declared = {}
    for name in arrays:
        entry = {"file": ARRAYS, "array": name, **RECORDS[name]}
        if entry["unit"] == CLOCK:
            entry["unit"] = clock
        declared[name] = entry
    record = {
        "format": RUN_FORMAT,
        "world": world_id,
        "founder": "world",
        "model": MODEL_ID,
        "engine_models": model.components(spec),
        "definition_sha256": spec.fingerprint,
        "run": {"qualifier": run.qualifier, "start": run.start},
        "keys": keys.RULE,
        "lives": keys.LIVES,
        "law": _law(run),
        "mode": spec.execution.mode,
        "stream": lineage_spec.stream_identity(spec),
        "ssa": kernel.SSA_CONVENTION,
        "ledger": {**ledger.CONVENTIONS, "closure": run.closure},
        "operators": {"fission": fission.DECLARATION, "continuation": continuation.DECLARATION},
        "lifecycle": kernel.LIFECYCLE,
        "source": _source(),
        "end": end,
        "time": {
            "unit": clock,
            "temperature_K": world.units.temperature_K,
            "rates": f"per {clock} time unit",
            "bases": BASES,
        },
        "channels": kernel.channel_table(world.types.ids),
        "layers": list(LAYERS),
        "records": declared,
        "diagnostics": {"uniforms": spec.experiment.uniforms},
    }
    if run.bound is not None:
        record["bound"] = run.bound
    return record


def descent(lives, qualifier=None):
    """The lives table as RELATIONSHIPS_DESIGN §1.2's rows, for the relations writer: one dict
    per life with string ids (keys.py), in the table's order. `lives` is a run's lives arrays
    (run.lives, or a bundle's life_* arrays); `qualifier`, when given, qualifies every id."""

    def ident(value):
        if value < 0:
            return None
        return keys.carrier_id(value) if qualifier is None else keys.qualified_id(qualifier, value)

    def event(fission):
        return None if fission < 0 else f"fission:{int(fission)}"

    rows = []
    for i in range(len(lives["life_key"])):
        slot = int(lives["life_slot"][i])
        rows.append(
            {
                "id": ident(int(lives["life_key"][i])),
                "key": keys.spelled(int(lives["life_key"][i])),
                "slot": None if slot < 0 else f"slot:{slot}",
                "parent": ident(int(lives["life_parent"][i])),
                "predecessor": None,
                "birth_time": float(lives["life_birth_time"][i]),
                "birth_event": event(lives["life_birth_fission"][i]),
                "birth_kind": str(lives["life_birth_kind"][i]),
                "end_time": float(lives["life_end_time"][i]),
                "end_event": event(lives["life_end_fission"][i]),
                "end_reason": str(lives["life_end_reason"][i]),
                "censored_by": str(lives["life_censored_by"][i]) or None,
                "generation": int(lives["life_generation"][i]),
                "root": ident(int(lives["life_root"][i])),
            }
        )
    return rows


def _arrays(run):
    out = dict(run.rows)
    out.update(run.fissions)
    out.update(run.trace)
    out.update(run.diagnostics)
    out.update(run.lives)
    return out


def _write_json(path, value):
    from cells.io import _write_json as write

    write(Path(path), value)


def write_run(directory, run, *, provenance=None):
    """Write one run's bundle into a new directory; returns its summary."""
    from cells.core import blas_threads
    from cells.core.devices import execution_device
    from cells.io import _sha256, runtime_identity, source_hashes

    directory = Path(directory)
    world = world_record(run.spec.model.world)
    record = run_record(run, world["id"])
    directory.mkdir(parents=True, exist_ok=False)
    np.savez(directory / ARRAYS, **_arrays(run))
    _write_json(directory / "world.json", world)
    _write_json(directory / "run.json", record)
    _write_json(directory / "resolved_config.json", run.spec.to_dict())
    summary = {
        "status": run.status,
        "qualifier": run.qualifier,
        "start": run.start,
        "lives": int(len(run.lives["life_key"])),
        "world": world["id"],
        "law": record["law"]["id"],
        "form": record["law"]["form"],
        **record["end"],
        "ledger_closes": run.closure["holds"],
        "ledger_max_abs_residual_kT": run.closure["max_abs_residual_kT"],
        "timings": run.timings,
    }
    _write_json(directory / "summary.json", summary)
    backend = run.spec.execution.backend
    manifest = {
        "schema_version": 1,
        "status": run.status,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "definition_sha256": run.spec.fingerprint,
        "runtime": runtime_identity(backend),
        "source_hashes": source_hashes(),
        "device": str(execution_device(backend)),
        "cpu_affinity": sorted(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else None,
        "blas": blas_threads.record(),
        "random_state": lineage_spec.stream_identity(run.spec),
        "timings": run.timings,
        "provenance": provenance
        or (
            {"operation": "fresh"}
            if run.start == "fresh"
            else {"operation": run.start["kind"], "checkpoint": run.start["checkpoint"]}
        ),
        "files_sha256": {
            str(p.relative_to(directory)): _sha256(p)
            for p in sorted(directory.rglob("*"))
            if p.is_file()
        },
    }
    _write_json(directory / "manifest.json", manifest)
    return summary


def _same_but_law(a, b):
    da, db = a.spec.to_dict(), b.spec.to_dict()
    da["model"].pop("rate_factor", None)
    db["model"].pop("rate_factor", None)
    return da == db


def write_pair(directory, runs, *, provenance=None):
    """A pair of law forms of one world: pair.json and one bundle per form."""
    if len(runs) != 2:
        raise ConfigError("A pair holds two runs")
    forms = [r.spec.model.rate_factor for r in runs]
    if forms[0] == forms[1] or not _same_but_law(*runs):
        raise ConfigError(
            "A pair's runs share the world (its founder), the experiment and the execution, "
            "streams included, and differ in the law alone"
        )
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    entries = []
    for run in runs:
        law = factors.resolve(run.spec.model.rate_factor)
        name = law.form
        write_run(directory / name, run, provenance=provenance)
        entries.append({"bundle": name, "law": law.law_id, "form": law.form})
    world = world_record(runs[0].spec.model.world)
    _write_json(
        directory / "pair.json",
        {
            "format": PAIR_FORMAT,
            "world": world["id"],
            "founder": "world: one founder, shared by both runs",
            "runs": entries,
            "differs": ["law"],
            "shared": ["world", "experiment", "execution", "stream"],
            "clock": "one nominal clock and one fission count for both runs",
            "stream": lineage_spec.stream_identity(runs[0].spec),
        },
    )
    return entries


def read(directory):
    """(world record, run record, arrays) of a bundle, checking its manifest's checksums."""
    from cells.io import _sha256

    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    for name, expected in manifest["files_sha256"].items():
        if _sha256(directory / name) != expected:
            raise ConfigError(f"{directory / name}: its checksum differs from the manifest's")
    world = json.loads((directory / "world.json").read_text())
    record = json.loads((directory / "run.json").read_text())
    if world["id"] != digest(world["world"]) or record["world"] != world["id"]:
        raise ConfigError(f"{directory}: the world record's id does not match its content or run")
    with np.load(directory / ARRAYS, allow_pickle=False) as saved:
        arrays = {k: saved[k] for k in saved.files}
    if set(arrays) != set(record["records"]):
        raise ConfigError(f"{directory}: the arrays and the run record's records differ")
    return world, record, arrays
