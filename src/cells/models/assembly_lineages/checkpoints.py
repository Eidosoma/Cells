"""Checkpoints of assembly lineages: one lane saved verbatim, restored to continue or to branch.

A checkpoint holds one lane's complete state: every field of kernel.Lane as the kernel holds it,
the rate-factor law's incremental state and the rates included. The state is never recomputed at
a restore. The incremental catalysis state (x = beta n, one column per event) differs from an exact
recompute by rounding, so a recompute would move later rates, times and, rarely, events.

Nothing is pending but what the state says. The kernel draws each event's two uniforms from the
occupant's exchange stream at its own event counter (`age`), so a lane holds no pending draw. A
lane saved while its fission is due (`fission_due`) splits when the restored run's fission pass
runs, from the parent's partition stream: so a checkpoint may be taken mid-growth, between any two
events, or across a fission. A run from a checkpoint continues bitwise.

**A restart or a branch** is a new run whose definition names the checkpoint's world, law and
execution. Only these may differ:
- `execution.stream.branch`, the branch word: a different word makes a branch, an independent
  future, because the word folds into every stream of the world (streams.py). The restored lane's
  exchange stream is re-derived for the run's words; every other field is restored verbatim;
- the experiment's horizon and recording (`fissions`, `growth_event_limit`, `trace`, `uniforms`).
Entities alive at the checkpoint keep their keys (keys.py: `birth_kind` continued), and the
lineage counter continues. The run's qualifier is new: its start is the checkpoint's digest.

**The digest** is that of {definition fingerprint, clock, state}, the state being the SHA-256 of
every lane field's name, dtype, shape and bytes in field order. It holds no time of day, so a
replayed checkpoint has the same digest and a restarted run the same qualifier.

**Files** (write, read): `checkpoint.json` (FORMAT, the definition, its fingerprint, the qualifier
of the run that wrote it, the clock, the digest, the runtime and the source identity) and
`lane.npz`. Reading refuses a changed source or runtime, as a complete checkpoint of the fixed-step
engine is refused (io.load_snapshot), so no checkpoint crosses a source move (D195, item 4).
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells.core.specs import ConfigError, digest
from cells.models.assembly_lineages import MODE, kernel, keys, streams

FORMAT = "cells.assembly_lineages.checkpoint@1"
CLOCK = ("time", "events", "fissions", "age", "occupant", "generation", "next_carrier", "status")
RESUMABLE = (kernel.RUNNING, kernel.FISSION_DUE, kernel.COMPLETE)
MAY_DIFFER = (
    "execution.stream.branch",
    "experiment.fissions",
    "experiment.growth_event_limit",
    "experiment.trace",
    "experiment.uniforms",
)


@dataclass(frozen=True)
class Checkpoint:
    definition: dict  # The run's definition (spec.to_dict()).
    fingerprint: str
    qualifier: str  # The run that wrote it.
    clock: dict
    lane: dict  # {kernel.Lane field: numpy array}; factor_state absent without a rate factor.
    digest: str


def state_digest(lane):
    h = hashlib.sha256()
    for name in kernel.Lane._fields:
        if name not in lane:
            h.update(f"{name}:absent;".encode())
            continue
        value = np.ascontiguousarray(lane[name])
        h.update(f"{name}:{value.dtype.str}:{value.shape};".encode())
        h.update(value.tobytes())
    return h.hexdigest()


def clock_of(lane):
    out = {}
    for name in CLOCK:
        value = np.asarray(lane[name]).item()
        out[name] = float(value) if name == "time" else int(value)
    return out


def make(spec, qualifier, lane):
    """The checkpoint of one lane (host arrays) of a run of `spec`."""
    if spec.execution.mode != MODE:
        raise ConfigError("Checkpoints are of single-lineage runs")
    lane = {k: np.asarray(v).copy() for k, v in lane.items() if not _empty(v)}
    clock = clock_of(lane)
    return Checkpoint(
        definition=spec.to_dict(),
        fingerprint=spec.fingerprint,
        qualifier=qualifier,
        clock=clock,
        lane=lane,
        digest=digest(
            {"definition": spec.fingerprint, "clock": clock, "state": state_digest(lane)}
        ),
    )


def _empty(value):
    return isinstance(value, tuple) and not value


def _differs(a, b, prefix=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += _differs(a.get(k), b.get(k), f"{prefix}{k}.")
        return out
    return [] if a == b else [prefix[:-1]]


def admit(spec, checkpoint):
    """(the start record, the restored lane as host arrays) of a run of `spec` from `checkpoint`;
    refuses what may not change, and a lineage with no future."""
    from cells.core.specs import parse_spec

    parent = parse_spec(checkpoint.definition)
    if parent.fingerprint != checkpoint.fingerprint:
        raise ConfigError("The checkpoint's definition does not match its fingerprint")
    found = digest(
        {
            "definition": checkpoint.fingerprint,
            "clock": clock_of(checkpoint.lane),
            "state": state_digest(checkpoint.lane),
        }
    )
    if found != checkpoint.digest or clock_of(checkpoint.lane) != checkpoint.clock:
        raise ConfigError("The checkpoint's state does not match its digest")
    if spec.execution.mode != MODE:
        raise ConfigError("A run from a checkpoint is a single-lineage run")
    differs = _differs(parent.to_dict(), spec.to_dict())
    refused = [path for path in differs if path not in MAY_DIFFER]
    if refused:
        raise ConfigError(
            "A run from a checkpoint keeps the world, the law and the execution; only the branch "
            f"word and the experiment's horizon and recording may change, not {refused}"
        )
    lane = {k: np.asarray(v).copy() for k, v in checkpoint.lane.items()}
    status = int(lane["status"])
    if status not in RESUMABLE:
        raise ConfigError(
            f"The checkpoint's lineage is {kernel.STATUS[status]}: it has no future to continue"
        )
    if status == kernel.COMPLETE:
        if not (spec.experiment.fissions > int(lane["fissions"]) and int(lane["size"]) > 0):
            raise ConfigError(
                "The checkpoint's lineage completed its horizon; a run from it extends "
                "experiment.fissions beyond its fissions"
            )
        # A daughter born at the fission size and censored at the horizon splits at once when
        # the horizon is extended (fission.py), as it would have in the longer run.
        at_size = int(lane["size"]) >= parent.model.world.fission.size
        lane["status"] = np.int32(kernel.FISSION_DUE if at_size else kernel.RUNNING)
    x = spec.execution
    base = streams.base_key_data(x.seed, x.environment, x.lineage, x.branch)
    derived = np.asarray(
        streams.stream_key_data(base, np.int64(lane["occupant"]), "exchange"), dtype=np.uint32
    )
    old = parent.execution.branch
    if x.branch == old and not np.array_equal(derived, lane["exchange_stream"]):
        raise ConfigError("The checkpoint's exchange stream is not its occupant's")
    lane["exchange_stream"] = derived
    start = {
        "checkpoint": checkpoint.digest,
        "from_run": checkpoint.qualifier,
        "time": checkpoint.clock["time"],
        "events": checkpoint.clock["events"],
        "fissions": checkpoint.clock["fissions"],
        "occupant": keys.spelled(checkpoint.clock["occupant"]),
        "branch_word": x.branch,
        "parent_branch_word": old,
        "kind": "branch" if x.branch != old else "restart",
        "differs": differs,
    }
    return start, lane


def write(directory, checkpoint):
    """Write a checkpoint into a new directory."""
    from cells.core.specs import parse_spec
    from cells.io import _sha256, _write_json, runtime_identity, source_hashes

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    np.savez(directory / "lane.npz", **checkpoint.lane)
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
            "runtime": runtime_identity(backend),
            "source_hashes": source_hashes(),
            "lane_sha256": _sha256(directory / "lane.npz"),
        },
    )
    return directory


def read(directory):
    """A checkpoint from its directory; refuses a changed source or runtime, a changed file, or a
    state that does not match its digest."""
    from cells.core.specs import parse_spec
    from cells.io import _sha256, runtime_identity, source_hashes

    directory = Path(directory)
    record = json.loads((directory / "checkpoint.json").read_text())
    if record.get("format") != FORMAT:
        raise ConfigError(f"{directory}: not a {FORMAT}")
    if _sha256(directory / "lane.npz") != record["lane_sha256"]:
        raise ConfigError(f"{directory}: the lane file's checksum differs")
    if record["source_hashes"] != source_hashes():
        raise ConfigError(f"{directory}: the checkpoint's engine source differs from this one")
    backend = parse_spec(record["definition"]).execution.backend
    if record["runtime"] != runtime_identity(backend):
        raise ConfigError(f"{directory}: the checkpoint's runtime differs from this one")
    with np.load(directory / "lane.npz", allow_pickle=False) as saved:
        lane = {k: saved[k] for k in saved.files}
    checkpoint = Checkpoint(
        definition=record["definition"],
        fingerprint=record["definition_sha256"],
        qualifier=record["qualifier"],
        clock=record["clock"],
        lane=lane,
        digest=record["digest"],
    )
    if (
        digest(
            {
                "definition": checkpoint.fingerprint,
                "clock": clock_of(lane),
                "state": state_digest(lane),
            }
        )
        != checkpoint.digest
    ):
        raise ConfigError(f"{directory}: the lane does not match the checkpoint's digest")
    return checkpoint
