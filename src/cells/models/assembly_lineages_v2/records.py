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
from cells.models.assembly_lineages_v2 import (
    MODEL_ID,
    diagnostic,
    division,
    kernel,
    ledger,
    model,
    runner,
)
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


# OL3's records, written only by a world that declares division (every other bundle is unchanged).
_F = "fission"
DIVISION_BASE = (
    "one row per attempt at a shear event, in order: split, or refused (the stress or v test: no "
    "draw; the floor test: drawn, the parent kept). Times: fission_time"
)
DIVISION_RECORDS = {
    "shear_work_kT": _record(
        "row", ["row"], "k_BT", "cumulative",
        "the shear work done on the lineage, sum_j F_v(d_j) - F_v(parent) per split (§0.2d item 7)",
    ),
    "discarded_free_energy_kT": _record(
        "row", ["row"], "k_BT", "cumulative",
        "the unfollowed daughters' F_v, taken to the declared sink (sink:discard)",
    ),
    "fission_time": _record(_F, [_F], "s", "level", "the shear event's time"),
    "fission_schedule": _record(_F, [_F], "1", "level", "the schedule's declared index"),
    "fission_k": _record(_F, [_F], "1", "level", "the schedule's k"),
    "fission_parent": _record(_F, [_F], "carrier key", "level", "the assembly attempted"),
    "fission_parent_generation": _record(_F, [_F], "1", "level", "its generation"),
    "fission_counter": _record(
        _F, [_F], "1", "level",
        "the parent's fission counter at its draw (domain 2, its key); -1: not admitted, no draw",
    ),
    "fission_outcome": _record(
        _F, [_F], "1", "level", "the attempt's outcome",
        legend={str(i): o for i, o in enumerate(division.OUTCOMES)},
    ),
    "fission_followed": _record(
        _F, [_F], "1", "level", "the daughter followed (an index into fission_daughters); -1: none",
    ),
    "fission_parent_counts": _record(
        _F, [_F, "place"], "molecules", "level", "the parent's counts",
    ),
    "fission_daughters": _record(
        _F, [_F, "daughter"], "carrier key", "level",
        "each daughter's key, in daughter order; -1 pads",
    ),
    "fission_daughter_counts": _record(
        _F, [_F, "daughter", "place"], "molecules", "level",
        "each daughter's vesicle with the pool as it was (rules 9 and 10's split)",
    ),
    "fission_lysed_at_birth": _record(
        _F, [_F, "daughter"], "1", "level", "the daughter was born beyond sigma_max (§0.2d 10.3)",
    ),
    "fission_shear_work_kT": _record(_F, [_F], "k_BT", "level", "the split's shear work"),
    "fission_discarded_kT": _record(_F, [_F], "k_BT", "level", "the unfollowed daughters' F_v"),
}  # fmt: skip
DIVISION_BASES = {
    **BASES,
    "row": BASES["row"] + "; a division world adds a shear row (row_kind shear) after each split, "
    "at its schedule time",
    "fission": DIVISION_BASE,
}
SCHEDULED_DRAW = (
    "two uniforms per draw, (u1, u2), from the occupant's event stream (domain 1, its carrier "
    "key) at counter = the occupant's draws since its birth: each committed event's, and the draw "
    "that crossed a schedule time, which is discarded (its wait is redrawn from the schedule time "
    "at the next counter; §0.2d item 6). A daughter's counter starts at 0 at its birth (item 10.6)"
)


def _division_record(run):
    """run.json's `division` block (division worlds only)."""
    spec = run.spec
    fissions = run.division["fissions"]
    outcomes = fissions["fission_outcome"].tolist()
    return {
        "operator": division.DECLARATION,
        "declared": division.data_to_dict(spec.model.world.division),
        "schedules": division.schedule_to_dict(spec.experiment.schedules),
        "attempts": len(outcomes),
        "outcomes": {o: outcomes.count(i) for i, o in enumerate(division.OUTCOMES)},
        "relations": "cells.relations@2 (relations.json, relations.npz): the lives, each split's "
        "event paid by its schedule's source (source:shear/<index>), the unfollowed daughters' "
        "material to sink:discard, and a lysis's event",
        "unstated": "an unfollowed daughter beyond sigma_max leaves for the sink as born (its flag "
        "is recorded); the rulings do not state it",
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
        "run": {"qualifier": run.qualifier, "start": run.start},
        "conventions": world_spec.conventions_rules.to_dict(world.conventions),
        "laws": [_law(law_id) for law_id in components["laws"]],
        "check": {"probe": run.verdict, "world": run.world_report},
        "mode": spec.execution.mode,
        "stream": world_spec.stream_identity(spec),
        "ssa": kernel.SSA_CONVENTION
        if run.division is None
        else {**kernel.SSA_CONVENTION, "draw": SCHEDULED_DRAW},
        "lifecycle": _lifecycle(run),
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
            "bases": BASES if run.division is None else DIVISION_BASES,
        },
        "places": places_table(world),
        "channels": kernel.channel_table(world),
        "records": {
            name: {"file": ARRAYS, "array": name, **_declared(run, name)} for name in arrays
        },
        "diagnostics": {
            "uniforms": spec.experiment.uniforms,
            **({"record": ["diagnostic.json", "diagnostic.npz"]} if run.diagnostic else {}),
        },
        **({"osmotic": run.osmotic} if run.osmotic is not None else {}),
        **({"division": _division_record(run)} if run.division is not None else {}),
        **({"population": _population_record(run)} if run.population is not None else {}),
    }


_S = "row"
POPULATION_RECORDS = {
    "pool_count": _record(_S, ["row", "place"], "molecules", "level", "the pool's places' counts "
                          "(every vesicle place 0)"),
    "slot_count": _record(_S, ["row", "slot", "place"], "molecules", "level",
                          "each slot's vesicle places' counts (every pool place 0; 0 when empty)"),
    "slot_key": _record(_S, ["row", "slot"], "carrier key", "level",
                        "the slot's assembly; -1 empty"),
    "membrane_footprint_quanta": _record(_S, ["row", "slot"], "quanta", "level",
                                         "each slot's W(n); 0 when empty"),
    "lumen_volume_L": _record(_S, ["row", "slot"], "L", "level", "each slot's V(n); 0 when empty"),
    "tension_N_per_m": _record(_S, ["row", "slot"], "N/m", "level", "each slot's sigma"),
    "schedule_work_kT": _record(_S, ["row", "schedule"], "k_BT", "cumulative",
                                "each declared schedule's work (run.json population."
                                "schedule_columns names the columns' schedules)"),
    "fission_slot": _record("fission", ["fission"], "1", "level", "the parent's slot"),
    "fission_daughter_slots": _record("fission", ["fission", "daughter"], "1", "level",
                                      "each daughter's slot (daughter 0 the parent's); -1 pads"),
    "event_group": _record("event", ["event"], "1", "level",
                           "the event's group: 0 the pool, 1 + k slot k"),
    "event_uniforms": _record("event", ["event", "draw"], "1", "level",
                              "diagnostic: the event's three uniforms (u1 tau, u2 the group, u3 "
                              "the channel), from the world's stream (domain 5)"),
}  # fmt: skip


def _lifecycle(run):
    if run.population is not None:  # a population ends slots_full too; a lysis frees one slot
        statuses = {**kernel.LIFECYCLE_OSMOTIC["statuses"]}
        statuses["lysed"] = ("never a population's end: a lysis frees its slot, books one row, "
                             "and the world goes on")  # fmt: skip
        statuses["slots_full"] = (
            "a division found fewer than k - 1 free slots: the run stopped before its draw, every "
            "life censored (§0.2c rule 13)"
        )
        statuses["stopped"] = (
            "the run's own stop, an exact event count (a run argument, FR-22): it stopped after "
            "that event and its own host action, before the next draw, every life censored, its "
            "state kept for a checkpoint (checkpoints.py)"
        )
        return {**kernel.LIFECYCLE_OSMOTIC, "statuses": statuses}
    return kernel.LIFECYCLE_OSMOTIC if run.osmotic is not None else kernel.LIFECYCLE


def _population_record(run):
    """run.json's `population` block (population runs only): the report less its tables."""
    report = run.population
    out = {k: report[k] for k in ("slots", "founders", "lyses", "draws", "schedule_columns",
                                  "transfers", "reads")}  # fmt: skip
    fissions = report["fissions"]
    if fissions is not None:
        outcomes = fissions["fission_outcome"].tolist()
        out["outcomes"] = {o: outcomes.count(i) for i, o in enumerate(division.POPULATION_OUTCOMES)}
    out["schedule_draws"] = [  # (index, counter, uniform, use, a gap's time or null)
        [*d[:4], None if d[4] != d[4] else d[4]] for d in report["schedule_draws"]
    ]
    out["payers"] = (
        "schedule_work_kT's column c is paid by the schedule whose declared index is "
        "schedule_columns[c] (source:shear/<index> or source:transfer/<index>); shear_work_kT is "
        "the shears' total, and at every row the columns sum to it plus the transfers' work"
    )
    return out


def _declared(run, name):
    table = {**RECORDS, **GEOMETRY_RECORDS}
    if run.population is not None:
        from cells.models.assembly_lineages_v2 import population

        if name == "row_kind":
            legend = {str(i): kind for i, kind in enumerate(population.ROW_KINDS)}
            return {**table[name], "legend": legend}
        if name == "fission_outcome":
            legend = {str(i): o for i, o in enumerate(division.POPULATION_OUTCOMES)}
            return {**DIVISION_RECORDS[name], "legend": legend}
        return {**table, **DIVISION_RECORDS, **POPULATION_RECORDS}[name]
    if run.division is None:
        return table[name]
    if name == "row_kind":  # A division world's rows include its shear rows.
        legend = {str(i): kind for i, kind in enumerate(runner.DIVISION_ROW_KINDS)}
        return {**table[name], "legend": legend}
    return {**table, **DIVISION_RECORDS}[name]


def _arrays(run):
    out = dict(run.rows)
    out.update(run.trace)
    out.update(run.diagnostics)
    if run.division is not None:
        out.update(run.division["fissions"])
    if run.population is not None and run.population["fissions"] is not None:
        out.update(run.population["fissions"])
    return out


def population_tables(directory, run):
    """cells.relations@2's tables of a population run: its lives (population.lives), one event per
    split (kind fission, by the shear fission, scheduled, paid by its schedule's source) and per
    lysis (kind lysis, by the osmotic lumen), its slots, and its schedules' sources."""
    from cells.models.assembly_lineages import keys
    from cells.models.assembly_lineages_v2 import (
        OSMOTIC_LUMEN,
        SHARED_POOL,
        SHEAR_FISSION,
        population,
    )
    from cells.records import relations as rel

    lives = [rel.Life(**row) for row in population.lives(run)]
    fissions = run.population["fissions"]
    before = run.population.get("numbering", {}).get("attempts", 0)  # a resumed run's offset
    events = []
    if fissions is not None:
        events = [
            rel.Event(f"event:fission/{before + r}", float(fissions["fission_time"][r]), "fission",
                      SHEAR_FISSION, scheduled=True, step=-1,
                      at=keys.carrier_id(int(fissions["fission_parent"][r])),
                      source=f"source:shear/{int(fissions['fission_schedule'][r])}")
            for r in np.flatnonzero(fissions["fission_outcome"] == 0)
        ]  # fmt: skip
    from cells.models.assembly_lineages_v2.transfer import SERIAL_TRANSFER

    events += [
        rel.Event(t["id"], t["time_s"], "transfer", SERIAL_TRANSFER, scheduled=True, step=-1,
                  source=f"source:transfer/{t['schedule']}")
        for t in run.population["transfers"]
    ]  # fmt: skip
    events += [
        rel.Event(life.end_event, life.end_time, "lysis", OSMOTIC_LUMEN, scheduled=False, step=-1,
                  at=life.id, source="")
        for life in lives
        if life.end_reason == "lysed"
    ]  # fmt: skip
    slots = run.population["slots"]
    nodes = [rel.Node(f"slot:{k}", "slot", SHARED_POOL) for k in range(slots)]
    sources, records = [], {}
    if run.population["schedule_columns"]:
        sources = [
            rel.Source(f"source:{s.kind}/{s.index}", "schedule",
                       "energy" if s.kind == "shear" else "substrate",
                       SHEAR_FISSION if s.kind == "shear" else SERIAL_TRANSFER,
                       payer_of="schedule_work_kT")
            for s in run.spec.experiment.schedules
        ]  # fmt: skip
        records = rel.records_in(directory, [ARRAYS], {"schedule_work_kT": "cumulative"},
                                 times="row_time")  # fmt: skip
    return {"lives": lives, "events": events, "nodes": nodes, "sources": sources,
            "records": records}  # fmt: skip


SINK = "sink:discard"
SLOT = "slot:0"


def relation_tables(directory, run):
    """cells.relations@2's tables of a division run whose records.npz is in `directory`: the lives
    (division.lives), one event per split (kind fission, by the shear fission, scheduled, paid by
    its schedule's source) and one per lysis (kind lysis, by the osmotic lumen), the slot and the
    sink, and each unfollowed daughter's molecules to the sink, per species, at its split."""
    from cells.models.assembly_lineages import keys
    from cells.models.assembly_lineages_v2 import OSMOTIC_LUMEN, SHEAR_FISSION
    from cells.records import relations as rel

    world = run.spec.model.world
    fissions = run.division["fissions"]
    lives = [rel.Life(**row) for row in run.division["lives"]]
    events = [
        rel.Event(f"event:fission/{r}", float(fissions["fission_time"][r]), "fission",
                  SHEAR_FISSION, scheduled=True, step=-1,
                  at=keys.carrier_id(int(fissions["fission_parent"][r])),
                  source=f"source:shear/{int(fissions['fission_schedule'][r])}")
        for r in np.flatnonzero(fissions["fission_outcome"] == 0)
    ]  # fmt: skip
    events += [
        rel.Event(life.end_event, life.end_time, "lysis", OSMOTIC_LUMEN, scheduled=False, step=-1,
                  at=life.id, source="")
        for life in lives
        if life.end_reason == "lysed"
    ]  # fmt: skip
    nodes = [rel.Node(SLOT, "slot", MODEL_ID), rel.Node(SINK, "sink", SHEAR_FISSION)]
    edges = []
    for life in lives:
        if life.end_reason != "not_followed":
            continue
        r = int(life.end_event.rsplit("/", 1)[1])
        j = fissions["fission_daughters"][r].tolist().index(life.key)
        by_species = {}
        for i, count in enumerate(fissions["fission_daughter_counts"][r, j].tolist()):
            place = world.places[i]
            if count and place.phase in ("membrane", "lumen"):
                by_species[place.species] = by_species.get(place.species, 0) + count
        edges += [
            rel.Edge("removes_to", life.id, SINK, SHEAR_FISSION, event=life.end_event,
                     species=species, weight=float(count), mode="event")
            for species, count in sorted(by_species.items())
        ]  # fmt: skip
    sources = [
        rel.Source(f"source:shear/{index}", "schedule", "energy", SHEAR_FISSION,
                   payer_of="shear_work_kT")
        for index in (s.index for s in run.spec.experiment.schedules)
    ]  # fmt: skip
    records = rel.records_in(
        directory,
        [ARRAYS],
        {"shear_work_kT": "cumulative", "discarded_free_energy_kT": "cumulative"},
        times="row_time",
    )
    return {"lives": lives, "events": events, "nodes": nodes, "sources": sources,
            "edges": edges, "records": records}  # fmt: skip


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
    if run.diagnostic is not None:  # §0.2d item 10.5, declared (diagnostic.py)
        np.savez(directory / "diagnostic.npz", **run.diagnostic["arrays"])
        _write_json(directory / "diagnostic.json", run.diagnostic["body"])
    if run.division is not None or run.population is not None:  # the relationship tables
        from cells.records import relations as rel

        tables = population_tables(directory, run) if run.population is not None else (
            relation_tables(directory, run))  # fmt: skip
        rel.write(directory, world=run.qualifier, version=rel.FORMAT_V2, **tables)
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
        "runtime": {  # the environment record, with §0.2d item 9's flag
            **runtime_identity(backend),
            "jax_threefry_partitionable": diagnostic.partitionable(),
        },
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
