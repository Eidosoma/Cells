"""Pair a complete Cells checkpoint with an explicitly owned physiological RNG.

The ordinary numeric snapshot retains its existing validation and source/runtime
pins. This outer bundle saves the logical draw counter independently of physical
time and commits their association last. It neither injects noise into a model
nor infers how a perturbation layout maps onto physical state. Consumers must
define that coupling and the points at which draws occur.

Only the paired loader restores both objects. Loading its inner deterministic
snapshot directly intentionally does not restore or advance the random stream.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cells.core import physiology_random_streams as streams
from cells.core.specs import ConfigError, digest, read_json
from cells.io import Snapshot, load_snapshot, source_hashes, write_snapshot

KIND = "cells.physiology_random_checkpoint@1"
FILES = frozenset(("snapshot/manifest.json", "snapshot/state.npz", "stream.json"))
FIELDS = frozenset(
    (
        "kind",
        "complete",
        "snapshot_identity",
        "spec_sha256",
        "clock",
        "stream_identity",
        "stream_id",
        "world_id",
        "layout_identity",
        "next_tick",
        "files",
        "identity",
    )
)


@dataclass(frozen=True)
class PhysiologyCheckpoint:
    snapshot: Snapshot
    stream: streams.PhysiologyRandomStream
    identity: str


def _sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _clock(point):
    return dict(time=point.time, step_index=point.step_index, event_index=point.event_index)


def _stream_identity(stream, record):
    return dict(
        stream_identity=record["identity"],
        stream_id=stream.stream_id,
        world_id=stream.world_id,
        layout_identity=stream.layout_identity,
        next_tick=stream.next_tick,
    )


def write_physiology_checkpoint(directory, spec, checkpoint, stream, binding):
    """Save both states in a new directory; a failed publication is never loadable.

    The caller supplies the exact stream associated with this accepted numeric
    endpoint. Logical next_tick need not equal step_index or any floating clock.
    A retained stream object deliberately permits explicit replay/branching;
    this writer does not allocate a new random world or silently reseed it.
    """
    record = streams.stream_record(stream)
    streams.restore_stream(record, binding)
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    try:
        write_snapshot(root / "snapshot", spec, checkpoint)
        _write_json(root / "stream.json", record)
        numeric = read_json(root / "snapshot/manifest.json")
        if numeric["source_hashes"] != source_hashes():
            raise ConfigError("Checkpoint source changed during paired publication")
        manifest = dict(
            kind=KIND,
            complete=True,
            snapshot_identity=numeric["manifest_sha256"],
            spec_sha256=numeric["spec_sha256"],
            clock=numeric["clock"],
            **_stream_identity(stream, record),
            files={name: _sha(root / name) for name in sorted(FILES)},
        )
        # The ordinary writer closes its files. Sync them before committing the
        # association so a durable outer manifest never precedes its payloads.
        for name in FILES:
            with (root / name).open("rb") as payload:
                os.fsync(payload.fileno())
        _sync_directory(root / "snapshot")
        _write_json(root / "manifest.json", manifest | dict(identity=digest(manifest)))
        _sync_directory(root)
        _sync_directory(root.parent)
    except Exception as error:
        _write_json(root / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
    return root


def load_physiology_checkpoint(
    directory, binding, *, expected_stream_id=None, expected_world_id=None
):
    """Restore numeric and RNG states together, refusing partial or mixed evidence.

    Binding is explicit and must match the saved perturbation layout exactly.
    Optional expected identifiers guard a caller's intended stream/world; they
    do not reinterpret native RNG as a world-keyed sampling law.
    """
    root = Path(directory).resolve()
    if (root / "failure.json").exists():
        raise ConfigError("Failed physiological checkpoint publication")
    manifest = read_json(root / "manifest.json")
    if not isinstance(manifest, dict) or set(manifest) != FIELDS:
        raise ConfigError("Invalid physiological checkpoint manifest fields")
    if (
        manifest["kind"] != KIND
        or manifest["complete"] is not True
        or digest({key: value for key, value in manifest.items() if key != "identity"})
        != manifest["identity"]
    ):
        raise ConfigError("Invalid physiological checkpoint identity or completion marker")
    if not isinstance(manifest["files"], dict) or set(manifest["files"]) != FILES:
        raise ConfigError("Invalid physiological checkpoint file inventory")
    present = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    if present != FILES | {"manifest.json"}:
        raise ConfigError("Physiological checkpoint has missing or extra artifacts")
    for name, expected in manifest["files"].items():
        path = root / name
        if not path.resolve().is_relative_to(root) or _sha(path) != expected:
            raise ConfigError("Physiological checkpoint payload changed: " + name)
    for field in ("world_id", "next_tick"):
        if type(manifest[field]) is not int or not 0 <= manifest[field] < 2**64:
            raise ConfigError("Invalid physiological checkpoint " + field)
    if expected_stream_id is not None and (
        not isinstance(expected_stream_id, str)
        or not expected_stream_id
        or manifest["stream_id"] != expected_stream_id
    ):
        raise ConfigError("Physiological checkpoint belongs to another stream")
    if expected_world_id is not None and (
        type(expected_world_id) is not int or manifest["world_id"] != expected_world_id
    ):
        raise ConfigError("Physiological checkpoint belongs to another world")
    record = read_json(root / "stream.json")
    stream = streams.restore_stream(record, binding)
    if any(manifest[key] != value for key, value in _stream_identity(stream, record).items()):
        raise ConfigError("Physiological checkpoint stream/clock association disagrees")
    snapshot = load_snapshot(root / "snapshot")
    if (
        manifest["snapshot_identity"] != snapshot.fingerprint
        or manifest["spec_sha256"] != snapshot.spec.fingerprint
        or manifest["clock"] != _clock(snapshot.checkpoint)
    ):
        raise ConfigError("Physiological checkpoint numeric/clock association disagrees")
    return PhysiologyCheckpoint(snapshot, stream, manifest["identity"])
