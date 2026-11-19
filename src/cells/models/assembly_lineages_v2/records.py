"""Run records of version 2: one bundle per run, self-describing (no engine code needed to read it).

A bundle is a new directory (never overwritten) holding:

- world.json (WORLD_FORMAT): {format, id, world, derived}. `world` is the world as its definitions
  state it (spec.world_to_dict: units, the declared conventions, species, phases, steps,
  free_energy, rate_factor, founder); `id` is the SHA-256 of its canonical JSON;
- run.json (RUN_FORMAT): the run record (below);
- records.npz: the arrays, each declared in run.json's `records` (loads with allow_pickle=False);
- resolved_config.json: the definition; summary.json: how the run ended;
- manifest.json, written last: every file's SHA-256, the runtime and the source.

run.json states: the world's id; the model and the registered IDs the run uses; the declared
conventions (the tokens, echoed); the laws, each with its interface, formulas and provenance; the
kernel's check (its probe verdict and the world's own report); the places (index, name, species,
phase, finite or held); the channel table (each step's forward and reverse, in fold order, with
the trace's codes); the SSA convention (draw, τ, selection, uniform); the lifecycle; the ledger's
conventions and its closure; the stream's identity; the engine's source; the end; the time unit
and temperature; and each array's base, axes and unit.

Relationship tables (cells.relations@1) arrive with OL3's division: an OL1 run is one life.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from cells.definitions.specs import ConfigError, digest
from cells.models.assembly_lineages_v2 import MODEL_ID, kernel, ledger, model, runner
from cells.models.assembly_lineages_v2 import spec as world_spec
from cells.models.assembly_lineages_v2 import world as world_rules
from cells.registry import laws as law_registry

WORLD_FORMAT = "cells.assembly_lineages.world@2"
RUN_FORMAT = "cells.assembly_lineages.run@2"
ARRAYS = "records.npz"

BASES = {
    "row": "the start (row_kind start), every row_every_events committed events (periodic), each "
    "observation time (observed: the state after the last event at or before it; its row_time is "
    "the observation time) and the end (end), in time order; the end row's time is the horizon "
    "when the state held to it (status complete or inert). Times: row_time",
    "event": "one entry per committed event, in order (the trace). Times: event_time",
}
ROW_LEGEND = {str(i): kind for i, kind in enumerate(runner.ROW_KINDS)}


def _record(base, axes, unit, kind, says, **extra):
    return {"base": base, "axes": list(axes), "unit": unit, "kind": kind, "says": says, **extra}


RECORDS = {
    "row_time": _record("row", ["row"], "s", "level", "the row's time"),
    "row_event": _record(
        "row", ["row"], "events", "cumulative", "committed events before the row", monotone=True
    ),
    "row_kind": _record("row", ["row"], "1", "level", "the row's kind", legend=ROW_LEGEND),
    "place_count": _record(
        "row",
        ["row", "place"],
        "molecules",
        "amount",
        "each place's count (run.json places; a held place has none: 0)",
    ),
    "reservoir_supplied": _record(
        "row",
        ["row", "place"],
        "molecules",
        "cumulative",
        "molecules each held place's reservoir supplied, net (0 for a finite place)",
    ),
    "channel_fired": _record(
        "row",
        ["row", "channel"],
        "events",
        "cumulative",
        "each declared channel's committed events (run.json channels' rows)",
        monotone=True,
    ),
    "event_heat_kT": _record(
        "row", ["row"], "k_BT", "cumulative", "Q: the event heat, declared non-monotone"
    ),
    "reservoir_work_kT": _record(
        "row", ["row"], "k_BT", "cumulative", "W: the held reservoirs' work, signed"
    ),
    "free_energy_kT": _record("row", ["row"], "k_BT", "level", "F(n) at the row, exactly"),
    "ledger_residual_kT": _record(
        "row", ["row"], "k_BT", "level", "Q - [W - (F(n_t) - F(n_0))]: rounding only"
    ),
    "event_time": _record("event", ["event"], "s", "level", "the event's time"),
    "event_channel": _record(
        "event",
        ["event"],
        "1",
        "level",
        "+(r+1): the forward of step r; -(r+1): its reverse (run.json channels)",
    ),
    "event_uniforms": _record(
        "event",
        ["event", "draw"],
        "1",
        "level",
        "diagnostic: the event's two uniforms (u1 sets tau, u2 the channel), for a replay",
    ),
}


# OL2's records, written only by a world that declares a geometry (OL1's bundles are unchanged).
GEOMETRY_RECORDS = {
    "lumen_volume_L": _record(
        "row", ["row"], "L", "level", "V(n) = min(V_osm, V_sph(A)), the osmotic lumen's volume"
    ),
    "tension_N_per_m": _record(
        "row", ["row"], "N/m", "level", "sigma = max(0, dp R / 2), the membrane's tension"
    ),
    "membrane_footprint_quanta": _record(
        "row",
        ["row"],
        "quanta",
        "level",
        "W(n) = sum_i n_i k_i, the membrane's footprint at the row; the bilayer's area is q W / 2",
    ),
}


def _geometry_derived(world):
    """The geometry's derived constants (world.json's `derived`), only when it is declared."""
    if world.geometry is None:
        return {}
    from cells.models.assembly_lineages_v2 import geometry

    c_area, c_radius = geometry.log_constants(world)
    return {
        "geometry": {
            "rho0_per_m3": geometry.rho0(world),
            "log_area_constant": c_area,
            "log_radius_constant": c_radius,
            "floor_quanta": geometry.floor_quanta(world),
            "closure_kT": geometry.closure_kT(world),
            "closure_form": world.geometry[1]["closure"]["form"],
            **(
                {"closure_law": geometry.CLOSURE_LAW}
                if world.geometry[1]["closure"]["form"] == "moduli"
                else {}
            ),
        }
    }


def world_record(world):
    body = world_spec.world_to_dict(world)
    return {
        "format": WORLD_FORMAT,
        "id": digest(body),
        "world": body,
        "derived": {
            "places": [p.name for p in world.places],
            "offset": world.conventions.offset,
            "kT_J": world.units.kT_J,
            "log_extent": {p: model.log_extent(world, p) for p, _ in world.volumes},
            **_geometry_derived(world),
        },
    }


def places_table(world):
    return [
        {
            "index": i,
            "name": p.name,
            "species": p.species,
            "phase": p.phase,
            "kind": "held" if p.held else "finite",
            "held_mM": p.held_mM,
            "standard_mu_RT": world.species_by_id(p.species).mu(p.phase),
        }
        for i, p in enumerate(world.places)
    ]


def _law(law_id):
    law = law_registry.active().lookup(law_id)
    source = law.source
    provenance = {"kind": law.provenance}
    if isinstance(source, law_registry.Citation):
        provenance |= {
            "source": source.source,
            "place": source.place,
            "licence": source.licence,
            "departures": list(source.departures),
            "works": [
                {"authors": list(w.authors), "year": w.year, "title": w.title, "doi": w.doi,
                 "url": w.url}
                for w in source.works
            ],
        }  # fmt: skip
    return {
        "id": law.law_id,
        "interface": law.interface,
        "energy_role": getattr(law, "energy_role", "state function"),
        "formulas": law.formulas,
        "provenance": provenance,
        "test": law.test,
    }


def _source():
    from cells.records.run_view import _engine_source

    source = _engine_source()
    if source is None:
        return {"unstated": "the engine ran from a checkout, not an execution snapshot"}
    return source


def run_record(run, world_id):
    spec = run.spec
    world = spec.model.world
    rows = run.rows
    arrays = sorted(_arrays(run))
    components = model.components(spec)
    return {
        "format": RUN_FORMAT,
        "world": world_id,
        "model": MODEL_ID,
        "engine_models": components,
        "definition_sha256": spec.fingerprint,
        "run": {"qualifier": run.qualifier, "start": "fresh"},
        "conventions": world_spec.conventions_rules.to_dict(world.conventions),
        "laws": [_law(law_id) for law_id in components["laws"]],
        "check": {"probe": run.verdict, "world": run.world_report},
        "mode": spec.execution.mode,
        "stream": world_spec.stream_identity(spec),
        "ssa": kernel.SSA_CONVENTION,
        "lifecycle": kernel.LIFECYCLE_OSMOTIC if run.osmotic is not None else kernel.LIFECYCLE,
        "ledger": {**ledger.CONVENTIONS, "closure": run.closure},
        "source": _source(),
        "end": {
            "status": run.status,
            "events": int(rows["row_event"][-1]),
            "time": float(rows["row_time"][-1]),
        },
        "time": {
            "unit": "s",
            "temperature_K": world.units.temperature_K,
            "kT_J": world.units.kT_J,
            "horizon_s": spec.experiment.time_horizon_s,
            "bases": BASES,
        },
        "places": places_table(world),
        "channels": kernel.channel_table(world),
        "records": {
            name: {"file": ARRAYS, "array": name, **{**RECORDS, **GEOMETRY_RECORDS}[name]}
            for name in arrays
        },
        "diagnostics": {"uniforms": spec.experiment.uniforms},
        **({"osmotic": run.osmotic} if run.osmotic is not None else {}),
    }


def _arrays(run):
    out = dict(run.rows)
    out.update(run.trace)
    out.update(run.diagnostics)
    return out


def _write_json(path, value):
    from cells.records.io import _write_json as write

    write(Path(path), value)


def write_run(directory, run, *, provenance=None):
    """Write one run's bundle into a new directory; returns its summary."""
    from cells.execution import blas_threads
    from cells.execution.devices import execution_device
    from cells.records.io import _sha256, runtime_identity, source_hashes

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
        "world": world["id"],
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
        "random_state": world_spec.stream_identity(run.spec),
        "timings": run.timings,
        "provenance": provenance or {"operation": "fresh"},
        "files_sha256": {
            str(p.relative_to(directory)): _sha256(p)
            for p in sorted(directory.rglob("*"))
            if p.is_file()
        },
    }
    _write_json(directory / "manifest.json", manifest)
    return summary


def read(directory):
    """(world record, run record, arrays) of a bundle, checking its manifest's checksums."""
    import json

    from cells.records.io import _sha256

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


assert world_rules.TIME_UNIT == "s"
