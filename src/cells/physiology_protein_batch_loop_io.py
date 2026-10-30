"""Durable complete-world restarts with numeric histories and failed attempts.

The frozen loop codec owns every physical checkpoint. This wrapper publishes
the cohort manifest last and keeps full immutable journal arrays, including
nonfinite speculative states. Restore does not draw or replay ionic evolution;
explicit source replay is provided separately by the batch loop owner.
"""

import os
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import numpy as np

from cells import physiology_protein_loop_io as checkpoint_io
from cells.core import physiology_protein_batch_loop as batch
from cells.core import physiology_protein_packet_provider as provider
from cells.core.specs import ConfigError, digest, read_json
from cells.io import runtime_identity, source_hashes
from cells.physiology_checkpoint import _sha, _sync_directory, _write_json

KIND = "cells.complete_charged_protein_batch_restart@1"
ARCHIVE_KIND = KIND + "/raw_numeric_evidence"


@dataclass(frozen=True, slots=True)
class SavedLoopAttempt:
    world_id: str
    source: object
    parent_identity: str
    target_identity: str
    accepted: bool
    stage: str
    payload: object
    identity: str


@dataclass(frozen=True, slots=True)
class ProteinBatchSnapshot:
    worlds: tuple
    attempts: tuple
    identity: str


def _encode(value, arrays):
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "biuf":
            raise ValueError("Raw evidence requires explicit real numeric buffers")
        name = f"leaf{len(arrays):06d}"
        arrays[name] = value
        return dict(array=name, dtype=value.dtype.str, shape=list(value.shape))
    if isinstance(value, Mapping):
        return dict(mapping=[[name, _encode(item, arrays)] for name, item in value.items()])
    if isinstance(value, tuple):
        return dict(tuple=[_encode(item, arrays) for item in value])
    if type(value) is float:
        return dict(float64_bits=struct.pack("<d", value).hex())
    if value is None or type(value) in (str, int, bool):
        return value
    raise ValueError("Unsupported raw evidence node")


def _decode(node, archive, used):
    if type(node) is dict:
        if set(node) == {"array", "dtype", "shape"}:
            name = node["array"]
            if type(name) is not str or name in used or name not in archive:
                raise ConfigError("Changed/duplicated raw numeric archive leaf")
            value = archive[name]
            if (
                value.dtype.kind not in "biuf"
                or value.dtype.str != node["dtype"]
                or list(value.shape) != node["shape"]
            ):
                raise ConfigError("Raw numeric evidence dtype/shape changed")
            used.add(name)
            return provider._freeze(value)
        if set(node) == {"mapping"}:
            pairs = node["mapping"]
            if (
                type(pairs) is not list
                or any(
                    type(pair) is not list or len(pair) != 2 or type(pair[0]) is not str
                    for pair in pairs
                )
                or len({pair[0] for pair in pairs}) != len(pairs)
            ):
                raise ConfigError("Changed raw evidence field map")
            return MappingProxyType({key: _decode(value, archive, used) for key, value in pairs})
        if set(node) == {"tuple"} and type(node["tuple"]) is list:
            return tuple(_decode(item, archive, used) for item in node["tuple"])
        if set(node) == {"float64_bits"} and type(node["float64_bits"]) is str:
            value = bytes.fromhex(node["float64_bits"])
            if len(value) != 8:
                raise ConfigError("Changed raw scalar float64 evidence")
            return struct.unpack("<d", value)[0]
        raise ConfigError("Unknown/extended raw evidence node")
    if node is None or type(node) in (str, int, bool):
        return node
    raise ConfigError("Invalid raw evidence scalar")


def write_raw_evidence(directory, payload):
    """Preserve full failed/accepted arrays before a manifest; no clipping."""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    arrays = {}
    encoded = _encode(payload, arrays)
    _write_json(path / "data.json", encoded)
    with (path / "arrays.npz").open("xb") as handle:
        np.savez(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    record = dict(
        kind=ARCHIVE_KIND,
        complete=True,
        payload_identity=digest(batch.raw_record(payload)),
        files={name: _sha(path / name) for name in ("data.json", "arrays.npz")},
    )
    _write_json(path / "manifest.json", record | dict(identity=digest(record)))
    _sync_directory(path)
    return path


def load_raw_evidence(directory):
    path = Path(directory)
    record = read_json(path / "manifest.json")
    if type(record) is not dict or set(record) != {
        "kind",
        "complete",
        "payload_identity",
        "files",
        "identity",
    }:
        raise ConfigError("Incomplete raw evidence manifest")
    payload = {key: value for key, value in record.items() if key != "identity"}
    if (
        record["kind"] != ARCHIVE_KIND
        or record["complete"] is not True
        or record["identity"] != digest(payload)
        or set(record["files"]) != {"data.json", "arrays.npz"}
    ):
        raise ConfigError("Invalid raw evidence manifest identity")
    for name, expected in record["files"].items():
        if _sha(path / name) != expected:
            raise ConfigError("Raw speculative evidence file changed")
    with np.load(path / "arrays.npz", allow_pickle=False) as archive:
        if len(set(archive.files)) != len(archive.files):
            raise ConfigError("Duplicate raw NPZ member")
        used = set()
        result = _decode(read_json(path / "data.json"), archive, used)
        if used != set(archive.files):
            raise ConfigError("Unused/unknown raw NPZ members")
    if digest(batch.raw_record(result)) != record["payload_identity"]:
        raise ConfigError("Raw speculative evidence content differs")
    return result


def _attempt_record(attempt):
    payload = dict(
        world_id=attempt.parent.world_id,
        parent_identity=attempt.parent.identity,
        source_checkpoint_identity=attempt.parent.checkpoint.identity,
        target_identity=attempt.world.identity,
        accepted=attempt.accepted,
        stage=attempt.stage,
        payload_identity=digest(batch.raw_record(attempt.payload)),
    )
    return payload | dict(identity=digest(payload))


def write_batch_checkpoint(directory, worlds, *, attempts=()):
    """Publish self-contained base/current/history checkpoints and raw attempts.

    Pass returned attempts to journal failures as well as accepted histories.
    Existing output is never replaced. An incomplete tree lacks the final
    manifest and cannot restore, while its raw failure evidence remains intact.
    """
    worlds = batch._envelope(worlds)
    attempts = tuple(attempts)
    for world in worlds:
        batch.validate_world(world)
    by_name = {world.world_id: world for world in worlds}
    if any(
        type(a) is not batch.WorldLoopAttempt or a.parent.world_id not in by_name for a in attempts
    ):
        raise ValueError("Journal attempts must belong to the saved world cohort")
    sources, runtime = source_hashes(), runtime_identity("cpu")
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    world_rows, attempt_rows = [], []
    for index, world in enumerate(worlds):
        relative = f"worlds/{index:06d}"
        folder = path / relative
        folder.mkdir(parents=True, exist_ok=False)
        points = {
            point.identity: point
            for point in (
                world.base,
                world.checkpoint,
                *(entry.source for entry in world.history),
                *(a.parent.checkpoint for a in attempts if a.parent.world_id == world.world_id),
            )
        }
        for identity, point in points.items():
            checkpoint_io.write_protein_loop_checkpoint(
                folder / "checkpoints" / identity, world.spec, point
            )
        history = []
        for position, entry in enumerate(world.history):
            write_raw_evidence(folder / f"history/{position:06d}", entry.payload)
            history.append(
                dict(
                    source_identity=entry.source.identity,
                    target_identity=entry.target_identity,
                    proposal_identity=entry.proposal_identity,
                    receipt_identity=entry.receipt_identity,
                    budget=batch.loop.transition._record(entry.budget),
                    identity=entry.identity,
                )
            )
        _write_json(
            folder / "world.json",
            dict(
                world=batch.world_record(world),
                checkpoints=sorted(points),
                history=history,
            ),
        )
        world_rows.append(
            dict(directory=relative, identity=world.identity, world_id=world.world_id)
        )
        for attempt in attempts:
            if attempt.parent.world_id == world.world_id:
                relative_attempt = f"attempts/{len(attempt_rows):06d}"
                write_raw_evidence(path / relative_attempt, attempt.payload)
                attempt_rows.append(
                    dict(directory=relative_attempt, record=_attempt_record(attempt))
                )
    if source_hashes() != sources or runtime_identity("cpu") != runtime:
        raise ConfigError("Source/runtime changed during complete batch publication")
    files = {
        str(file.relative_to(path)): _sha(file)
        for file in sorted(path.rglob("*"))
        if file.is_file()
    }
    record = dict(
        kind=KIND,
        complete=True,
        worlds=world_rows,
        attempts=attempt_rows,
        runtime=runtime,
        source_hashes=sources,
        files=files,
    )
    _write_json(path / "manifest.json", record | dict(identity=digest(record)))
    _sync_directory(path)
    return path


def _relative(path, value):
    if (
        type(value) is not str
        or Path(value).is_absolute()
        or any(part in (".", "..") for part in Path(value).parts)
    ):
        raise ConfigError("Invalid complete batch artifact path")
    return path / value


def load_batch_checkpoint(directory):
    """Strict complete-boundary restore, with raw history and no new RNG draw."""
    path = Path(directory)
    record = read_json(path / "manifest.json")
    if type(record) is not dict or set(record) != {
        "kind",
        "complete",
        "worlds",
        "attempts",
        "runtime",
        "source_hashes",
        "files",
        "identity",
    }:
        raise ConfigError("Incomplete complete-loop batch manifest")
    payload = {key: value for key, value in record.items() if key != "identity"}
    if (
        record["kind"] != KIND
        or record["complete"] is not True
        or record["identity"] != digest(payload)
        or record["source_hashes"] != source_hashes()
        or record["runtime"] != runtime_identity("cpu")
    ):
        raise ConfigError("Complete-loop batch source/runtime/manifest identity differs")
    actual_files = {
        str(file.relative_to(path))
        for file in path.rglob("*")
        if file.is_file() and file != path / "manifest.json"
    }
    if actual_files != set(record["files"]):
        raise ConfigError("Missing/extended complete-loop batch artifact set")
    for name, expected in record["files"].items():
        file = _relative(path, name)
        if file.is_symlink() or _sha(file) != expected:
            raise ConfigError("Complete-loop batch artifact changed: " + name)
    worlds, tables = [], {}
    for row in record["worlds"]:
        if type(row) is not dict or set(row) != {"directory", "identity", "world_id"}:
            raise ConfigError("Invalid complete-loop world index")
        folder = _relative(path, row["directory"])
        saved = read_json(folder / "world.json")
        if type(saved) is not dict or set(saved) != {"world", "checkpoints", "history"}:
            raise ConfigError("Incomplete complete-loop world/history")
        points, spec = {}, None
        if len(set(saved["checkpoints"])) != len(saved["checkpoints"]):
            raise ConfigError("Duplicate complete physical checkpoint")
        for identity in saved["checkpoints"]:
            if (
                type(identity) is not str
                or len(identity) != 64
                or any(c not in "0123456789abcdef" for c in identity)
            ):
                raise ConfigError("Invalid complete physical checkpoint identity")
            restored = checkpoint_io.load_protein_loop_checkpoint(folder / "checkpoints" / identity)
            if restored.checkpoint.identity != identity or (
                spec is not None and spec.fingerprint != restored.spec.fingerprint
            ):
                raise ConfigError("Physical checkpoint differs from its world definition")
            points[identity], spec = restored.checkpoint, restored.spec
        history = []
        for position, item in enumerate(saved["history"]):
            if type(item) is not dict or set(item) != {
                "source_identity",
                "target_identity",
                "proposal_identity",
                "receipt_identity",
                "budget",
                "identity",
            }:
                raise ConfigError("Incomplete per-world history entry")
            evidence = load_raw_evidence(folder / f"history/{position:06d}")
            history.append(
                batch.LoopHistory(
                    points[item["source_identity"]],
                    item["target_identity"],
                    item["proposal_identity"],
                    item["receipt_identity"],
                    batch.loop.transition.DrivingBudget(**item["budget"]),
                    evidence,
                    item["identity"],
                )
            )
        item = saved["world"]
        world = batch.ProteinBatchWorld(
            item["world_id"],
            spec,
            points[item["base"]["identity"]],
            points[item["checkpoint"]["identity"]],
            tuple(history),
            item["identity"],
        )
        if (
            batch.world_record(world) != item
            or world.identity != row["identity"]
            or world.world_id != row["world_id"]
        ):
            raise ConfigError("Complete world/ordered history association changed")
        batch.validate_world(world)
        worlds.append(world)
        tables[world.world_id] = points
    batch._envelope(worlds)
    attempts = []
    for row in record["attempts"]:
        if type(row) is not dict or set(row) != {"directory", "record"}:
            raise ConfigError("Invalid raw attempt index")
        item = row["record"]
        keys = {
            "world_id",
            "parent_identity",
            "source_checkpoint_identity",
            "target_identity",
            "accepted",
            "stage",
            "payload_identity",
            "identity",
        }
        if (
            type(item) is not dict
            or set(item) != keys
            or type(item["accepted"]) is not bool
            or item["identity"] != digest({k: v for k, v in item.items() if k != "identity"})
        ):
            raise ConfigError("Invalid raw attempted-world metadata")
        evidence = load_raw_evidence(_relative(path, row["directory"]))
        if digest(batch.raw_record(evidence)) != item["payload_identity"]:
            raise ConfigError("Raw attempted-world evidence association changed")
        source = tables[item["world_id"]][item["source_checkpoint_identity"]]
        attempts.append(
            SavedLoopAttempt(
                item["world_id"],
                source,
                item["parent_identity"],
                item["target_identity"],
                item["accepted"],
                item["stage"],
                evidence,
                item["identity"],
            )
        )
    return ProteinBatchSnapshot(tuple(worlds), tuple(attempts), record["identity"])
