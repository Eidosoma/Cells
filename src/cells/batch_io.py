"""Batch ownership wraps ordinary complete scalar snapshots and run artifacts."""

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Mapping

from cells.core.batch import (
    BatchSpec,
    _checkpoint_map,
    checkpoint_batch_limits,
    parse_batch,
    plan_batch,
)
from cells.core.runner import validate_checkpoint
from cells.core.specs import ConfigError, _fields, digest, read_json
from cells.core.state import Checkpoint
from cells.io import (
    _sha256,
    _write_json,
    _write_snapshot_payload,
    load_snapshot,
    runtime_identity,
    source_hashes,
    write_run,
)


@dataclass(frozen=True)
class BatchSnapshot:
    spec: BatchSpec
    checkpoints: Mapping[int, Checkpoint]
    fingerprint: str


def _validate(spec, checkpoints):
    spec, _ = checkpoint_batch_limits(spec)
    _checkpoint_map(spec, checkpoints)
    for world in spec.worlds:
        validate_checkpoint(world.simulation, checkpoints[world.world_id])
    return spec


def write_batch_snapshot(directory, spec, checkpoints):
    spec = _validate(spec, checkpoints)
    return _write_batch_snapshot_payload(directory, spec, checkpoints)


def _write_batch_snapshot_payload(directory, spec, checkpoints):
    """Internal publication of a fully validated complete cohort."""
    backend = spec.worlds[0].simulation.execution.backend
    identity = {"runtime": runtime_identity(backend), "source_hashes": source_hashes()}
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    worlds = []
    for world in spec.worlds:
        relative = f"world-{world.world_id}"
        _write_snapshot_payload(
            path / relative, world.simulation, checkpoints[world.world_id], identity=identity
        )
        saved = read_json(path / relative / "manifest.json")
        worlds.append(
            {
                "world_id": world.world_id,
                "path": relative,
                "snapshot_sha256": saved["manifest_sha256"],
            }
        )
    # No identity cache crosses publications. Refuse the enclosing manifest if
    # source or runtime changed while its ordinary scalar children were written.
    if (
        source_hashes() != identity["source_hashes"]
        or runtime_identity(backend) != identity["runtime"]
    ):
        raise ConfigError("Batch checkpoint source/runtime changed during publication")
    manifest = {
        "schema_version": 1,
        "kind": "cells_independent_world_checkpoint",
        "spec": spec.to_dict(),
        "spec_sha256": spec.fingerprint,
        "runtime": identity["runtime"],
        "source_hashes": identity["source_hashes"],
        "worlds": worlds,
    }
    manifest["manifest_sha256"] = digest(manifest)
    _write_json(path / "manifest.json", manifest)
    return path


def load_batch_snapshot(directory):
    path = Path(directory).resolve()
    manifest = _fields(
        read_json(path / "manifest.json"),
        {
            "schema_version",
            "kind",
            "spec",
            "spec_sha256",
            "runtime",
            "source_hashes",
            "worlds",
            "manifest_sha256",
        },
        "batch checkpoint manifest",
    )
    fingerprint = manifest.pop("manifest_sha256")
    if digest(manifest) != fingerprint:
        raise ConfigError("Batch checkpoint manifest checksum mismatch")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ConfigError("Unsupported batch checkpoint schema")
    if manifest["kind"] != "cells_independent_world_checkpoint":
        raise ConfigError("Not a complete independent-world checkpoint")
    if manifest["source_hashes"] != source_hashes():
        raise ConfigError("Batch checkpoint source differs from this installation")
    spec, _ = checkpoint_batch_limits(parse_batch(manifest["spec"]))
    if manifest["runtime"] != runtime_identity(spec.worlds[0].simulation.execution.backend):
        raise ConfigError("Batch checkpoint runtime differs; no implicit migration")
    if manifest["spec_sha256"] != spec.fingerprint:
        raise ConfigError("Batch checkpoint specification checksum mismatch")
    records = manifest["worlds"]
    if not isinstance(records, list) or len(records) != len(spec.worlds):
        raise ConfigError("Batch checkpoint world inventory differs")
    checkpoints = {}
    for world, record in zip(spec.worlds, records, strict=True):
        _fields(record, {"world_id", "path", "snapshot_sha256"}, "checkpoint world")
        if type(record["world_id"]) is not int or record["world_id"] != world.world_id:
            raise ConfigError("Batch checkpoint world identity/order differs")
        if record["path"] != f"world-{world.world_id}":
            raise ConfigError("Invalid batch checkpoint child path")
        child = (path / record["path"]).resolve()
        if not child.is_relative_to(path):
            raise ConfigError("Batch checkpoint child escapes its directory")
        saved = load_snapshot(child)
        if saved.spec != world.simulation or saved.fingerprint != record["snapshot_sha256"]:
            raise ConfigError("Batch checkpoint child specification/identity differs")
        checkpoints[world.world_id] = saved.checkpoint
    return BatchSnapshot(spec, checkpoints, fingerprint)


def write_batch_run(directory, result, *, checkpoint_times=(), provenance=None):
    spec = plan_batch(parse_batch(result.spec.to_dict())).spec
    final = {identity: world.final for identity, world in result.worlds.items()}
    _validate(spec, final)
    for world in spec.worlds:
        if result.worlds[world.world_id].spec != world.simulation:
            raise ConfigError("Batch result world definition differs")
    # Validate the entire request before creating any output, including every
    # world clock. A scalar time is only a convenience for a shared boundary.
    requested = [result.checkpoint_at(time) for time in sorted(set(checkpoint_times))]
    for checkpoints in requested:
        _validate(spec, checkpoints)
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    records = []
    for world in spec.worlds:
        relative = f"worlds/world-{world.world_id}"
        write_run(
            path / relative,
            result.worlds[world.world_id],
            provenance={
                "operation": "independent_world_batch",
                "world_id": world.world_id,
                "batch_definition_sha256": spec.fingerprint,
                "execution_timings": "shared; see enclosing batch manifest",
            },
        )
        records.append(
            {
                "world_id": world.world_id,
                "path": relative,
                "manifest_sha256": _sha256(path / relative / "manifest.json"),
            }
        )
    snapshots = []
    for index, checkpoints in enumerate(requested):
        relative = f"snapshots/checkpoint-{index:06d}"
        write_batch_snapshot(path / relative, spec, checkpoints)
        snapshots.append(relative)
    write_batch_snapshot(path / "checkpoint_final", spec, final)
    snapshots.append("checkpoint_final")
    _write_json(path / "resolved_batch.json", spec.to_dict())
    files = {str(p.relative_to(path)): _sha256(p) for p in sorted(path.rglob("*")) if p.is_file()}
    manifest = {
        "schema_version": 1,
        "kind": "cells_independent_world_run",
        "status": "complete",
        "definition_sha256": spec.fingerprint,
        "runtime": runtime_identity(spec.worlds[0].simulation.execution.backend),
        "source_hashes": source_hashes(),
        "worlds": records,
        "snapshots": snapshots,
        "files_sha256": files,
        "mapping": spec.mapping,
        "resources": result.resources,
        "timings": {**result.timings, "artifact_payload_write_seconds": perf_counter() - started},
        "timing_scope": "shared batch timings; payload write excludes final manifest publication",
        "provenance": provenance or {"operation": "fresh_batch"},
    }
    _write_json(path / "manifest.json", manifest)
    return {
        "status": "complete",
        "worlds": len(records),
        "world_ids": [w.world_id for w in spec.worlds],
    }
