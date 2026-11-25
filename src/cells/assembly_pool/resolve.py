"""cells assembly-pool resolve: the ionic definitions whose channels assembly pools drive (G-7;
docs/IP3_RELEASE_AND_ASSEMBLY_AVAILABILITY_DESIGN.md Part II, docs/CAPSID_ASSEMBLY.md).

**The composed file** is a strict JSON object with exactly the keys `schema_version` (1), `ionic`
and `pools`. `ionic` is an ordinary definition (resolved_pump_tissue@3 or
resolved_pump_composite@1). Each entry of `pools` has exactly these keys:
- `channels`: the channel populations it sets, by ID, each set by one pool at most;
- `observable`: what is read from the pool's assembly, the ID of a registered law
  (assembly_pool/observables.py);
- `levels`: one availability level in [0, 1] for each value of the observable;
- `pool`: an ordinary finite_bond_assembly@1 definition. Every pool declares the same worlds,
  `recording: "events"`, the ionic definition's horizon and its own effective seed.

**What resolve does.** It runs each pool with the pool's own engine, unchanged, walks the events it
recorded, and multiplies each driven channel's declared schedule by the pool's level
(assembly_pool/schedule.py). The pools never read the ionic side, so each world's definition is an
ordinary one: `cells run`, `windowed`, `batch`, `resume` and `branch` take it as any other, and a
run reads nothing else. The ionic definition is untouched but for the driven channels' schedules.

**Its output**, a new folder:
- `composed.json`: the composed file's own bytes;
- `pools/pool-NNN/`: each pool's run, ordinary `assembly-pool run` output but for `source/`, which
  is one copy of the package beside them;
- `worlds/world-ID.json`: one definition for each of the pools' worlds, by the pools' world ID;
- `batch.json`, if asked for: an independent_worlds batch of them (its world IDs start at 1, so they
  are the pools' plus 1);
- `resolution.json`: how each schedule was made: every pool's fingerprint and seed, and in every
  world its events, its switches, its exposure and its final state;
- `inputs.json`: what a run of those definitions records with `--inputs` (the composed file's
  SHA-256, the pools' fingerprints and seeds, the observables and every world's switches), so that a
  run record says what its schedule came from. No run reads either file's numbers.

The definitions, resolution.json and inputs.json hold no time of day and no path of this machine:
the same composed file gives the same bytes.

**Refused by name.** Before any pool runs: what parse_composed and check_composed name. After the
pools and before any definition is written: a pool that faults, with its world and its event cap; a
switch that nearly misses a point of the clock (D283), unless the caller asks for it to be declared
there; a switch at the same instant as a base change of its channel; and a clock of more than
`execution.max_steps` steps.
"""

import hashlib
import json
import math
from dataclasses import dataclass, replace

import numpy as np

from cells.assembly.cli import output_path
from cells.assembly.io import write_json
from cells.assembly.spec import AssemblyError
from cells.assembly_pool import cli, observables
from cells.assembly_pool.io import load_checkpoint
from cells.assembly_pool.schedule import (
    ChannelDrive,
    initial_fields,
    joined,
    missed_point,
    moved,
    repeated_seeds,
    step_count,
    switch_path,
)
from cells.assembly_pool.spec import PoolSpec
from cells.assembly_pool.spec import parse_spec as parse_pool
from cells.definitions import pump_composite_spec as composite
from cells.definitions import surface_pump_v3_spec as ionic
from cells.definitions.spec_values import fraction
from cells.definitions.specs import (
    ConfigError,
    SimulationSpec,
    digest,
    parse_spec,
    read_json,
    require_fields,
)
from cells.execution.batch import parse_batch
from cells.execution.grid import NEAR_MISS, applied_definition
from cells.execution.state import initialise
from cells.numerics.surface_field import FACTORED_SOLVER_ID, FLOOR_SOLVER_ID, SPARSE_SOLVER_ID
from cells.operators import membrane_trafficking

IONIC_MODELS = (ionic.MODEL_ID, composite.MODEL_ID)
REFUSE, TO_GRID = "refuse", "to_grid"  # What a near miss meets.
RESOLUTION, INPUTS = "cells_assembly_drive_resolution", "cells_assembly_drive_inputs"


# ------------------------------------------------------------------ the composed file


@dataclass(frozen=True)
class PoolDrive:
    """One entry of a composed file's pools: what it sets, what is read, and the pool."""

    channels: tuple[str, ...]
    observable: observables.AssemblyObservable
    levels: tuple[float, ...]  # One for each of the observable's values, in its order.
    pool: PoolSpec

    def level_of(self):
        return dict(zip(self.observable.values, self.levels, strict=True))

    def to_dict(self):
        return {
            "channels": list(self.channels),
            "observable": self.observable.law_id,
            "levels": self.level_of(),
            "pool": self.pool.to_dict(),
        }


@dataclass(frozen=True)
class Composed:
    """A parsed composed file: the ionic definition as declared and as parsed, and its pools."""

    raw: dict
    ionic: SimulationSpec
    drives: tuple[PoolDrive, ...]

    @property
    def fingerprint(self):
        """The digest of what the file means: its parsed ionic definition and its pools."""
        return digest(
            {
                "schema_version": 1,
                "ionic": self.ionic.to_dict(),
                "pools": [d.to_dict() for d in self.drives],
            }
        )

    def cells(self):
        """{channel ID: the cell its membrane patch is of}."""
        inside = {p.id: p.inside for p in self.ionic.model.membranes}
        return {c.id: inside[c.membrane_id] for c in self.ionic.model.channels}


def _copy(value):
    """A JSON value as new objects, shared by nothing."""
    return json.loads(json.dumps(value, allow_nan=False))


def _drive(entry, k, channels):
    require_fields(entry, {"channels", "observable", "levels", "pool"}, f"pool {k}")
    given = entry["channels"]
    if (
        not isinstance(given, list)
        or not given
        or not all(isinstance(c, str) for c in given)
        or len(set(given)) != len(given)
    ):
        raise ConfigError(f"Pool {k}: channels is a non-empty list of distinct channel IDs")
    unknown = sorted(set(given) - set(channels))
    if unknown:
        raise ConfigError(f"Pool {k}: {unknown[0]!r} is no channel of the ionic definition")
    try:
        law = observables.resolve(entry["observable"])
        pool = parse_pool(entry["pool"])
    except (AssemblyError, ConfigError) as exc:
        raise ConfigError(f"Pool {k}: {exc}") from exc
    levels = require_fields(entry["levels"], set(law.values), f"pool {k}: levels")
    levels = tuple(fraction(levels[v], f"pool {k}: the level of {v!r}") for v in law.values)
    return PoolDrive(tuple(given), law, levels, pool)


def parse_composed(data):
    """A composed file's JSON value as a Composed, or ConfigError naming what is wrong with it."""
    require_fields(data, {"schema_version", "ionic", "pools"}, "composed definition")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 of a composed definition is supported")
    model = data["ionic"].get("model") if isinstance(data["ionic"], dict) else None
    model_id = model.get("id") if isinstance(model, dict) else None
    if model_id not in IONIC_MODELS:
        raise ConfigError(
            f"The ionic definition's model is one of {', '.join(IONIC_MODELS)}, not {model_id!r}"
        )
    spec = parse_spec(data["ionic"])  # Its own refusals first; it keeps no part of what it reads.
    raw = _copy(data["ionic"])
    entries = data["pools"]
    if not isinstance(entries, list) or not entries:
        raise ConfigError("pools is a non-empty list")
    channels = [c.id for c in spec.model.channels]
    drives = tuple(_drive(entry, k, channels) for k, entry in enumerate(entries))
    setters = {}
    for k, drive in enumerate(drives):
        for channel in drive.channels:
            if channel in setters:
                raise ConfigError(
                    f"Channel {channel!r} is set by pools {setters[channel]} and {k}: a channel "
                    "is set by one pool at most"
                )
            setters[channel] = k
    composed = Composed(raw, spec, drives)
    check_pools(composed)
    check_composed(composed)
    return composed


def check_pools(composed):
    """The pools' own agreement: recording, horizon, worlds and seeds, each refused by name."""
    end = composed.ionic.experiment.end_time
    first = composed.drives[0].pool
    for k, drive in enumerate(composed.drives):
        pool = drive.pool
        if pool.recording != "events":
            raise ConfigError(
                f"Pool {k} declares recording {pool.recording!r}: a path is read from a pool's "
                'recorded events, so it declares "events"'
            )
        if pool.end_time_s != end:
            raise ConfigError(
                f"Pool {k}'s horizon, end_time_s = {pool.end_time_s!r}, is not the ionic "
                f"definition's end_time = {end!r}"
            )
        if (pool.worlds, pool.world_id_start) != (first.worlds, first.world_id_start):
            raise ConfigError(
                f"Pool {k} declares {pool.worlds} worlds from ID {pool.world_id_start}, and pool 0 "
                f"{first.worlds} from ID {first.world_id_start}: the pools' worlds are one set"
            )
    for i, j in repeated_seeds([d.pool.seed for d in composed.drives]):
        raise ConfigError(
            f"Pools {i} and {j} have one seed, {composed.drives[i].pool.seed}: two pools of one "
            "world each declare their own, or they draw the same numbers"
        )


def free_field_offsets(spec):
    """The free field offsets of a definition's layout (D147), which do not depend on its backend:
    0 where the layout has none."""
    on_cpu = replace(spec, execution=replace(spec.execution, backend="cpu"))
    free = getattr(initialise(on_cpu).layout, "field_offset_free", None)
    return 0 if free is None else int(np.sum(np.asarray(free)))


def lifecycles(spec, cells):
    """((law, what it does, cell), ...) for each operator of a composite that ends, begins, replaces
    or empties one of `cells`: a pool's path belongs to a channel's slot, so it would outlive the
    cell there."""
    if type(spec.model) is not composite.CompositeModel:
        return ()
    inside = {p.id: p.inside for p in spec.model.membranes}
    out = []
    for op, declaration, schedule in composite.entries(spec):
        lives = op.living_intervals(spec, declaration, schedule)
        # An operator that retires or replaces cells without naming them reaches every one.
        reached = [("begins or ends", c) for c in (cells if op.RETIRES and not lives else lives)]
        if op.EVENT_REPLACES:
            slots = [getattr(event, "slot", None) for event in schedule]
            reached += [("replaces", c) for c in (cells if None in slots else slots)]
        if isinstance(declaration, membrane_trafficking.Trafficking):
            reached += [
                ("moves channels out of", inside[r.plasma_patch]) for r in declaration.routes
            ]
        out += [(op.LAW_ID, what, cell) for what, cell in reached if cell in cells]
    return tuple(out)


def check_composed(composed):
    """The ionic side's refusals, each by name and before any pool runs: its clock, its field
    solver (D147) and the lives of the driven channels' cells."""
    spec, cells = composed.ionic, composed.cells()
    step_count(spec, [c.time for c in spec.experiment.changes])  # The clock's own refusals.
    solver = spec.execution.field_solver
    if solver in (FACTORED_SOLVER_ID, SPARSE_SOLVER_ID):
        free = free_field_offsets(spec)
        if free:
            raise ConfigError(
                f"The ionic definition has {free} free field offsets and declares {solver}: such "
                f"a definition declares {FLOOR_SOLVER_ID} (D147)"
            )
    driven = {cells[c]: (c, k) for k, d in enumerate(composed.drives) for c in d.channels}
    for law, what, cell in lifecycles(spec, driven):
        channel, k = driven[cell]
        raise ConfigError(
            f"{law} {what} cell {cell}, and pool {k} drives its channel {channel!r}: the pool's "
            "path belongs to the channel's slot and would outlive the cell"
        )


def load_composed(path):
    return parse_composed(read_json(path))


# ------------------------------------------------------------------ the pools


def run_pool(composed, k, output, *, backend, device_index):
    """Pool k's ordinary run in `output`; a fault is refused naming its world and its event cap."""
    pool = composed.drives[k].pool
    cli.register(
        output, pool, backend=backend, device_index=device_index, until=pool.end_time_s, parent=None
    )
    try:
        cli.execute(output)
    except AssemblyError as exc:
        saved = output / "failure-state.npz"
        if saved.exists():
            with np.load(saved, allow_pickle=False) as arrays:
                faults, times = arrays["fault"], arrays["time_s"]
            for world in np.flatnonzero(faults):
                cap = pool.max_events_per_world
                what = (
                    f"reached its event cap, max_events_per_world = {cap},"
                    if faults[world] == 2
                    else "has a clock that does not advance"
                )
                raise AssemblyError(
                    f"Pool {k}, world {pool.world_id_start + world}: it {what} at "
                    f"{float(times[world])!r} s of {pool.end_time_s!r} s"
                ) from exc
        raise AssemblyError(f"Pool {k}: {exc}") from exc


def recorded(output):
    """(Trace, final state) of a pool's finished run, from its own event files and checkpoint."""
    chunks = []
    for path in sorted(output.glob("events-*.npz")):
        with np.load(path, allow_pickle=False) as arrays:
            chunks.append([arrays[k] for k in ("time_s", "occupied", "bonds", "free", "event")])
    _, state, _ = load_checkpoint(output / "checkpoint")
    trace = joined(chunks)
    committed = trace.event >= 0
    if not np.array_equal(committed.sum(axis=0), state.event_count):
        raise AssemblyError(f"{output.name}: its recorded events are not its checkpoint's")
    for world in np.flatnonzero(state.event_count):
        last = np.flatnonzero(committed[:, world])[-1]
        for name in ("occupied", "bonds", "free"):
            if getattr(trace, name)[last, world] != getattr(state, name)[world]:
                raise AssemblyError(f"{output.name}: its last event is not its checkpoint's state")
    return trace, state


def state_record(state, world):
    """One world of a pool's final state as JSON (a pending time of no next event as null)."""
    out = {}
    for name, values in state._asdict().items():
        value = np.asarray(values)[world].tolist()
        out[name] = None if isinstance(value, float) and not math.isfinite(value) else value
    return out


# ------------------------------------------------------------------ the worlds


@dataclass(frozen=True)
class World:
    """One resolved world: its pools' paths as walked and as declared, and its definition."""

    world_id: int
    paths: tuple
    declared: tuple
    shifts: tuple  # Per pool: {a switch time: the clock's point it is declared at}.
    text: str
    spec: SimulationSpec
    fingerprint: str
    steps: int
    snapped: tuple


def driven_definition(raw, schedules):
    """The raw definition with these channels' schedules, {channel: ((time, availability), ...)},
    and nothing else changed or shared."""
    out = _copy(raw)
    for control in out["experiment"]["channel_controls"]:
        if control["channel_id"] in schedules:
            control["schedule"] = [
                {"time": t, "availability": a} for t, a in schedules[control["channel_id"]]
            ]
    return out


def resolve_world(composed, world_id, paths, near_misses=REFUSE):
    """The World of these paths, one for each pool. A near miss is refused by name, or declared at
    the point it misses where near_misses is TO_GRID."""
    spec, name = composed.ionic, f"World {world_id}"
    base = {
        c.id: tuple((p.time, p.availability) for p in changes)
        for c, changes in zip(spec.model.channels, spec.experiment.channels, strict=True)
    }
    declared, shifts, schedules = [], [], {}
    for k, (drive, path) in enumerate(zip(composed.drives, paths, strict=True)):
        points = {}
        for time, _, count in path.switches:
            point = missed_point(spec, time)
            if point is None:
                continue
            if near_misses != TO_GRID:
                raise ConfigError(
                    f"{name}, pool {k}: its switch at {time!r} s (event {count}) misses the "
                    f"clock's point {point!r} by {abs(time - point)!r} s, at most {NEAR_MISS} of "
                    "its step (a near miss, D283); --near-misses-to-grid declares it there"
                )
            points[time] = point
        declared.append(moved(path, points) if points else path)
        shifts.append(points)
        for channel in drive.channels:
            drives = ChannelDrive(channel, base[channel], declared[-1])
            for switch, change in drives.clashes():
                raise ConfigError(
                    f"{name}, pool {k}: its switch at {switch!r} s is the same instant as channel "
                    f"{channel!r}'s change at {change!r} s"
                )
            schedules[channel] = drives.schedule()
    changes = [c.time for c in spec.experiment.changes]
    times = {*changes, *(t for path in declared for t in path.times)}
    steps, limit = step_count(spec, sorted(times)), spec.execution.max_steps
    if steps > limit:
        raise ConfigError(
            f"{name}: its clock takes {steps} steps ({step_count(spec)} without a change), more "
            f"than execution.max_steps = {limit}"
        )
    text = _text(driven_definition(composed.raw, schedules))
    try:
        parsed = parse_spec(json.loads(text))
        snapped = applied_definition(parsed)[1]
    except ConfigError as exc:
        raise ConfigError(f"{name}: {exc}") from exc
    return World(
        world_id,
        tuple(paths),
        tuple(declared),
        tuple(shifts),
        text,
        parsed,
        parsed.fingerprint,
        steps,
        snapped,
    )


def batch_definition(worlds, max_working_bytes):
    """The independent_worlds batch of the worlds. Its padded-step limit is what its planner counts
    (execution/batch.py), its world limit its worlds, and its memory limit the caller's."""
    padded = len(worlds) * max(
        max(1, math.ceil(w.spec.experiment.end_time / w.spec.execution.dt))
        + len(w.spec.experiment.changes)
        for w in worlds
    )
    return {
        "schema_version": 1,
        "kind": "independent_worlds",
        "worlds": [{"world_id": w.world_id + 1, "simulation": json.loads(w.text)} for w in worlds],
        "execution": {
            "mapping": "lax_map",
            "max_worlds": len(worlds),
            "max_padded_steps": padded,
            "max_working_bytes": max_working_bytes,
        },
    }


# ------------------------------------------------------------------ the records


def _text(value):
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _publish(path, text):
    with path.open("x") as stream:
        stream.write(text)


def switches_of(world):
    """The switches of a world's pools in time order, each as its pool made it: {pool, time, level,
    event}, and where it is declared at a point of the clock, {declared} and {shift_s}."""
    out = []
    for k, (path, points) in enumerate(zip(world.paths, world.shifts, strict=True)):
        for time, level, count in path.switches:
            row = {"pool": k, "time": time, "level": level, "event": count}
            if time in points:
                row |= {"declared": points[time], "shift_s": points[time] - time}
            out.append(row)
    return sorted(out, key=lambda row: (row["time"], row["pool"]))


def pool_record(drive):
    """What sets a drive's path, beside its walk: the pool, its seed, and the rule."""
    return {
        "channels": list(drive.channels),
        "observable": drive.observable.law_id,
        "levels": drive.level_of(),
        "pool_sha256": drive.pool.fingerprint,
        "seed": drive.pool.seed,
    }


def inputs_record(composed, worlds, *, file_sha256, near_misses, batch=None):
    """inputs.json: what a run of the resolved definitions records (the module's docstring).
    `definitions_sha256` lists the definitions it is about, the batch among them."""
    return {
        "schema_version": 1,
        "kind": INPUTS,
        "composed_file_sha256": file_sha256,
        "composed_sha256": composed.fingerprint,
        "ionic_sha256": composed.ionic.fingerprint,
        "near_misses": near_misses,
        "pools": [pool_record(d) for d in composed.drives],
        "worlds": [
            {
                "world": w.world_id,
                "definition_sha256": w.fingerprint,
                "switches": switches_of(w),
            }
            for w in worlds
        ],
        "definitions_sha256": [w.fingerprint for w in worlds] + ([] if batch is None else [batch]),
    }


def resolution_record(composed, worlds, states, *, inputs, batch=None):
    """resolution.json: inputs.json's facts, and how each world's schedules were made."""
    cells = composed.cells()
    pools = [
        row | {"run": f"pools/pool-{k:03}", "cells": sorted({cells[c] for c in row["channels"]})}
        for k, row in enumerate(inputs["pools"])
    ]
    rows = []
    for index, world in enumerate(worlds):
        facts = inputs["worlds"][index]
        rows.append(
            facts
            | {
                "definition": f"worlds/world-{world.world_id}.json",
                "steps": world.steps,
                "snapped": [list(pair) for pair in world.snapped],
                "pools": [
                    {
                        "initial_level": path.levels[0],
                        "events": path.events,
                        "exposure_s": path.exposure(),
                        "final": state_record(states[k], index),
                    }
                    for k, path in enumerate(world.paths)
                ],
            }
        )
    return inputs | {
        "kind": RESOLUTION,
        "nominal_steps": step_count(composed.ionic),
        "pools": pools,
        "worlds": rows,
        "batch": None if batch is None else {"path": "batch.json", "definition_sha256": batch},
    }


def resolve(
    path, output, *, backend="cpu", device_index=0, near_misses=REFUSE, max_working_bytes=None
):
    """Resolve the composed file at `path` into the new folder `output` (the module's docstring).
    max_working_bytes: also write batch.json, with this memory limit. Returns a summary."""
    if near_misses not in (REFUSE, TO_GRID):
        raise ConfigError(f"near_misses is one of {REFUSE} and {TO_GRID}")
    source = path.read_bytes()
    composed = load_composed(path)
    if path.read_bytes() != source:
        raise ConfigError(f"The composed file changed while it was read: {path}")
    output = output_path(output)
    output.mkdir()
    try:
        return _resolve(
            composed, source, output, backend, device_index, near_misses, max_working_bytes
        )
    except BaseException as exc:
        write_json(output / "failure.json", {"status": "failed", "error": str(exc)})
        raise


def _resolve(composed, source, output, backend, device_index, near_misses, max_working_bytes):
    with (output / "composed.json").open("xb") as stream:
        stream.write(source)
    cli.copy_source(output)
    (output / "pools").mkdir()
    traces, states = [], []
    for k in range(len(composed.drives)):
        folder = output / "pools" / f"pool-{k:03}"
        run_pool(composed, k, folder, backend=backend, device_index=device_index)
        trace, state = recorded(folder)
        traces.append(trace)
        states.append(state)
    pool, end = composed.drives[0].pool, composed.ionic.experiment.end_time
    worlds = []
    for index in range(pool.worlds):
        paths = [
            switch_path(d.observable, d.level_of(), initial_fields(d.pool), trace, index, end)
            for d, trace in zip(composed.drives, traces, strict=True)
        ]
        worlds.append(resolve_world(composed, pool.world_id_start + index, paths, near_misses))
    batch, batch_sha256 = None, None
    if max_working_bytes is not None:
        batch = batch_definition(worlds, max_working_bytes)
        batch_sha256 = parse_batch(_copy(batch)).fingerprint
    inputs = inputs_record(
        composed,
        worlds,
        file_sha256=hashlib.sha256(source).hexdigest(),
        near_misses=near_misses,
        batch=batch_sha256,
    )
    record = resolution_record(composed, worlds, states, inputs=inputs, batch=batch_sha256)
    (output / "worlds").mkdir()
    for world in worlds:
        _publish(output / "worlds" / f"world-{world.world_id}.json", world.text)
    if batch is not None:
        _publish(output / "batch.json", _text(batch))
    _publish(output / "inputs.json", _text(inputs))
    _publish(output / "resolution.json", _text(record))
    return {
        "status": "resolved",
        "output": str(output),
        "worlds": len(worlds),
        "pools": len(composed.drives),
        "switches": sum(len(w["switches"]) for w in inputs["worlds"]),
        "batch": batch is not None,
        "composed_sha256": inputs["composed_sha256"],
    }
