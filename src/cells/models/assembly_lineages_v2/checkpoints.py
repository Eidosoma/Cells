"""Checkpoints of population worlds in cells.model.assembly_lineages@2 (FR-22, rung P): one world's
state saved verbatim at an exact event count, restored to continue it.

This is @1's format and rules (cells.models.assembly_lineages.checkpoints) for version 2's
population runner, in version 2's files only; no @1 file is touched (D215, option a, the lead's
ruling of 20 November 2026).

**What is saved.** A run stopped by `runner.run(spec, stop=k)` ends `stopped` after its k-th
committed event and that event's own host action (a lysis), before the next draw. Its checkpoint
holds:
- the device lane (population.Lane), every field as the device left it: the pool, the slots, who
  is alive, the time, the event count, the world stream's draw counter, the reservoirs' supply, the
  heat and work sums with their magnitudes, the rates, the stream and the status. The state is
  never recomputed at a restore, as in @1;
- the host's state (population._Context.resume): each slot's key, sub-lineage and generation,
  every sub-lineage's count, the next sub-lineage, every fission and transfer counter, the host's
  bookings (the sums and each schedule's work column), the stops already applied, the world's
  fission and transfer numbering, the living lives, and the world's initial F, to which every
  later ledger row is referenced.
The schedule plan is not saved: it is the definition's (its Poisson gaps are drawn from it), so a
restored run recomputes it and drops the stops its checkpoint's run applied.

**Nothing is pending but what the state says.** The world stream's counter counts every draw,
committed or discarded, so a lane holds no pending draw; the next stop is the plan's.

**A restart** is a new run whose definition is the checkpoint's; only these may differ:
- the experiment's horizon (`time_horizon_s`, past the checkpoint's time) and its guard
  (`event_limit`, above its event count);
- its recording: `trace` and `diagnostic`.
A new branch word is refused in this rung: its streams would redraw the plan's past stops. A
single-lineage run's checkpoint (rung S) is refused too, until a consumer needs it.

**A cut at a lysing event is refused.** The resumed run's first row would sit at the lysis's time,
and cells.relations needs an order between same-time events for that (RELATIONSHIPS_DESIGN,
relations@2's requirements; the lead's ruling: cut before or after such an event).

**A world with the pore law** (FR-31, pore_clock.py) keeps its clocks: the host's document adds
each living vesicle's `{slot, key, threshold_E, counter, t_star}`, and a restart rebuilds each
clock from its key and counts, refusing one that is not the definition's. A rupture is a host stop,
not a committed event, and it stays out of the applied stops, which count the schedule's. A cut
at a rupture's time, applied or pending, is refused, as a cut at a lysing event is. Each segment's
ruptures are its own; the threshold draws are the first segment's.

**The resumed run** (population.run's start) continues the world: its rows count events from the
world's start, its periodic rows keep the world's cadence, its sums and bookings continue the
checkpoint's, and its ledger is referenced to the world's own initial F. Its fission and transfer
events keep the world's numbering; the lives alive at the checkpoint are continued
(`birth_kind: continued`, at the checkpoint's time, with their keys, sub-lineages, generations and
roots). So after the cut its trace, its rows and its ledger are the uninterrupted run's, bitwise.

**Joining two segments' records** (the stopped run's and the resumed run's):
- rows: the stopped run's rows to its end row, then the resumed run's after its start row; the
  resumed run's start row is the state at the cut;
- the trace and the event uniforms: concatenated;
- relations: a life censored at the cut by the stopped run and continued by the resumed run, with
  the same key, is one life, born as the stopped run says and ended as the resumed run says;
- the diagnostic record: the world's draws concatenated (the resumed run's counters continue the
  stopped run's, and the stopped run has no ending draw, since its own stop ended it); the step
  events concatenated (each event's heat and work are increments, so the cut changes none); each
  segment's attempts, transfers and lyses are its own, with their uniform blocks; the schedules'
  Poisson draws are listed by both segments (the plan is the definition's), and each transfer's
  draws by the segment that made them; the resumed run's initial state is the stopped run's final
  state.

**The digest** is that of {definition fingerprint, clock, state}, the state being the SHA-256 of
every lane field's name, dtype, shape and bytes in field order, then the host's arrays in name
order, then the host's document as canonical JSON. It holds no time of day.

**Files** (write, read): `checkpoint.json` (FORMAT, the definition, its fingerprint, the qualifier
of the run that wrote it, the clock, the digest, the host's document, the runtime and the source
identity), `lane.npz` and `host.npz`. Reading refuses a changed source or runtime, a changed file
and a state that does not match its digest, so no checkpoint crosses a source move (D195, item 4).
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells.definitions.specs import ConfigError, digest
from cells.models.assembly_lineages_v2 import kernel, population

FORMAT = "cells.assembly_lineages_v2.checkpoint@1"
CLOCK = ("time", "events", "counter")
MAY_DIFFER = (
    "experiment.time_horizon_s",
    "experiment.event_limit",
    "experiment.trace",
    "experiment.diagnostic",
)


@dataclass(frozen=True)
class Checkpoint:
    definition: dict  # The run's definition (spec.to_dict()).
    fingerprint: str
    qualifier: str  # The run that wrote it.
    clock: dict
    lane: dict  # {population.Lane field: numpy array}, as the device left it
    host: dict  # {"arrays": {name: numpy array}, "doc": the host's JSON document}
    digest: str


def state_digest(lane, host):
    h = hashlib.sha256()
    for name in population.Lane._fields:
        value = np.ascontiguousarray(lane[name])
        h.update(f"{name}:{value.dtype.str}:{value.shape};".encode())
        h.update(value.tobytes())
    for name in sorted(host["arrays"]):
        value = np.ascontiguousarray(host["arrays"][name])
        h.update(f"host.{name}:{value.dtype.str}:{value.shape};".encode())
        h.update(value.tobytes())
    h.update(json.dumps(host["doc"], sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()


def clock_of(lane):
    out = {}
    for name in CLOCK:
        value = np.asarray(lane[name]).item()
        out[name] = float(value) if name == "time" else int(value)
    return out


def make(run):
    """The checkpoint of a population run (runner.WorldRun) that stopped at an exact event count."""
    if run.population is None:
        raise ConfigError(
            "Checkpoints are built for population runs (FR-22 rung P); a single-lineage run's "
            "(rung S) waits for a consumer"
        )
    if run.status != "stopped" or run.resume is None:
        raise ConfigError(
            f"A checkpoint is taken of a run stopped at an exact event count, not one that ended "
            f"{run.status!r}"
        )
    lane = {k: np.asarray(run.final[k]).copy() for k in population.Lane._fields}
    events = int(lane["events"])
    lyses = run.population["lyses"]
    if any(record["event"] == events and not record["at_birth"] for record in lyses):
        raise ConfigError(
            f"A cut at event {events}, whose event lysed a vesicle, is refused: the resumed run's "
            "first row would sit at the lysis's time, which needs cells.relations' order between "
            "same-time events; cut one event before or after it"
        )
    if run.pores is not None:  # FR-31: nor at a rupture's time, applied or pending
        time = float(lane["time"])
        ruptures = [e["time_s"] for e in run.pores["events"]]
        if "pores" in run.resume["doc"]:  # Phase A's host clocks; OL6 S4's: their t_c
            ruptures += [clock["t_star"] for clock in run.resume["doc"]["pores"]]
        ruptures += [clock["t_c"] for clock in run.resume["doc"].get("pore_clocks", [])]
        if time in ruptures:
            raise ConfigError(
                f"A cut at {time} s, a vesicle's rupture time, is refused: the resumed run's first "
                "row would sit at the rupture's time, which needs cells.relations' order between "
                "same-time events; cut one event before or after it"
            )
    host = {
        "arrays": {k: np.asarray(v).copy() for k, v in run.resume["arrays"].items()},
        "doc": json.loads(json.dumps(run.resume["doc"])),
    }
    clock = clock_of(lane)
    return Checkpoint(
        definition=run.spec.to_dict(),
        fingerprint=run.spec.fingerprint,
        qualifier=run.qualifier,
        clock=clock,
        lane=lane,
        host=host,
        digest=digest(
            {"definition": run.spec.fingerprint, "clock": clock, "state": state_digest(lane, host)}
        ),  # fmt: skip
    )


def _differs(a, b, prefix=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += _differs(a.get(k), b.get(k), f"{prefix}{k}.")
        return out
    return [] if a == b else [prefix[:-1]]


def admit(spec, checkpoint):
    """(the start record, the restored lane, the host's state) of a run of `spec` from
    `checkpoint`; refuses what may not change, and a world with no future."""
    from cells.definitions.specs import parse_spec

    parent = parse_spec(checkpoint.definition)
    if parent.fingerprint != checkpoint.fingerprint:
        raise ConfigError("The checkpoint's definition does not match its fingerprint")
    found = digest(
        {
            "definition": checkpoint.fingerprint,
            "clock": clock_of(checkpoint.lane),
            "state": state_digest(checkpoint.lane, checkpoint.host),
        }
    )
    if found != checkpoint.digest or clock_of(checkpoint.lane) != checkpoint.clock:
        raise ConfigError("The checkpoint's state does not match its digest")
    if spec.execution.mode != "population":
        raise ConfigError("A run from this checkpoint is a population run (FR-22 rung P)")
    differs = _differs(parent.to_dict(), spec.to_dict())
    refused = [path for path in differs if path not in MAY_DIFFER]
    if refused:
        raise ConfigError(
            "A run from a checkpoint keeps the world, its laws and the execution, the branch word "
            "included; only the experiment's horizon, its event guard and its recording may "
            f"change, not {refused}"
        )
    if not spec.experiment.time_horizon_s > checkpoint.clock["time"]:
        raise ConfigError("A run from a checkpoint ends after the checkpoint's time")
    if not spec.experiment.event_limit > checkpoint.clock["events"]:
        raise ConfigError("A run from a checkpoint has an event limit above its event count")
    lane = {k: np.asarray(v).copy() for k, v in checkpoint.lane.items()}
    if int(lane["status"]) != kernel.EVENT_LIMIT:
        raise ConfigError(
            f"The checkpoint's world is {population.STATUS[int(lane['status'])]}, not stopped at "
            "an event count: it has no future to continue"
        )
    lane["status"] = np.asarray(np.int32(kernel.RUNNING))
    from cells.models.assembly_lineages_v2 import model, streams

    stream = streams.stream_key_data(model.layout(spec).base_key, streams.WORLD_CARRIER, "world")
    if not np.array_equal(np.asarray(stream, dtype=np.uint32), lane["world_stream"]):
        raise ConfigError("The checkpoint's world stream is not its definition's")
    host = {
        "arrays": {k: np.asarray(v).copy() for k, v in checkpoint.host["arrays"].items()},
        "doc": json.loads(json.dumps(checkpoint.host["doc"])),
    }
    start = {
        "checkpoint": checkpoint.digest,
        "from_run": checkpoint.qualifier,
        "time": checkpoint.clock["time"],
        "events": checkpoint.clock["events"],
        "counter": checkpoint.clock["counter"],
        "kind": "restart",
        "differs": differs,
    }
    return start, lane, host


def write(directory, checkpoint):
    """Write a checkpoint into a new directory."""
    from cells.definitions.specs import parse_spec
    from cells.records.io import _sha256, _write_json, runtime_identity, source_hashes

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    np.savez(directory / "lane.npz", **checkpoint.lane)
    np.savez(directory / "host.npz", **checkpoint.host["arrays"])
    backend = parse_spec(checkpoint.definition).execution.backend
    _write_json(
        directory / "checkpoint.json",
        {
            "format": FORMAT,
            "definition": checkpoint.definition,
            "definition_sha256": checkpoint.fingerprint,
            "qualifier": checkpoint.qualifier,
            "clock": checkpoint.clock,
            "digest": checkpoint.digest,
            "host": checkpoint.host["doc"],
            "runtime": runtime_identity(backend),
            "source_hashes": source_hashes(),
            "lane_sha256": _sha256(directory / "lane.npz"),
            "host_sha256": _sha256(directory / "host.npz"),
        },
    )
    return directory


def read(directory):
    """A checkpoint from its directory; refuses a changed source or runtime, a changed file, or a
    state that does not match its digest."""
    from cells.definitions.specs import parse_spec
    from cells.records.io import _sha256, runtime_identity, source_hashes

    directory = Path(directory)
    record = json.loads((directory / "checkpoint.json").read_text())
    if record.get("format") != FORMAT:
        raise ConfigError(f"{directory}: not a {FORMAT}")
    for name in ("lane", "host"):
        if _sha256(directory / f"{name}.npz") != record[f"{name}_sha256"]:
            raise ConfigError(f"{directory}: the {name} file's checksum differs")
    if record["source_hashes"] != source_hashes():
        raise ConfigError(f"{directory}: the checkpoint's engine source differs from this one")
    backend = parse_spec(record["definition"]).execution.backend
    if record["runtime"] != runtime_identity(backend):
        raise ConfigError(f"{directory}: the checkpoint's runtime differs from this one")
    with np.load(directory / "lane.npz", allow_pickle=False) as saved:
        lane = {k: saved[k] for k in saved.files}
    with np.load(directory / "host.npz", allow_pickle=False) as saved:
        arrays = {k: saved[k] for k in saved.files}
    checkpoint = Checkpoint(
        definition=record["definition"],
        fingerprint=record["definition_sha256"],
        qualifier=record["qualifier"],
        clock=record["clock"],
        lane=lane,
        host={"arrays": arrays, "doc": record["host"]},
        digest=record["digest"],
    )
    found = digest(
        {"definition": checkpoint.fingerprint, "clock": clock_of(lane),
         "state": state_digest(lane, checkpoint.host)}
    )  # fmt: skip
    if found != checkpoint.digest:
        raise ConfigError(f"{directory}: the state does not match the checkpoint's digest")
    return checkpoint
