"""Durable restart for the separate, held-protein charged trajectory family.

The ordinary seed is preserved and validated using its original format. The
charged endpoint is never published as an ordinary snapshot. Its independent
balance validation runs on both save and load; the outer manifest commits the
full numeric/protein/reference/RNG association last. Partial writes are kept
but cannot load as completed checkpoints.
"""

import os
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from cells.core import physiology_protein_charge_interval as interval
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError, digest, parse_spec, read_json
from cells.io import load_snapshot, runtime_identity, source_hashes, write_snapshot
from cells.physiology_checkpoint import (
    _component_record,
    _restore_component,
    _sha,
    _sync_directory,
    _write_json,
)

KIND = "cells.held_protein_charge_restart@1"
FILES = frozenset(
    (
        "seed/manifest.json",
        "seed/state.npz",
        "state.npz",
        "binding.json",
        "components.json",
    )
)
FIELDS = frozenset(("kind", "complete", "checkpoint", "files", "identity"))


@dataclass(frozen=True, slots=True)
class HeldProteinSnapshot:
    spec: object
    checkpoint: interval.HeldProteinCheckpoint
    identity: str


def _components(point):
    return {
        name: dict(
            stream=streams.stream_record(component.stream),
            state=_component_record(component, point.binding.component, component.stream),
        )
        for name, component in (
            ("charge_reference", point.charge_reference),
            ("component", point.component),
        )
    }


def write_held_protein_checkpoint(directory, spec, point):
    """Validate and publish a new complete directory; never replace an old one."""
    spec = parse_spec(spec.to_dict())
    interval.validate(spec, point)
    sources, runtime = source_hashes(), runtime_identity(spec.execution.backend)
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    write_snapshot(path / "seed", spec, point.seed)
    _write_json(path / "binding.json", units.binding_record(point.binding))
    _write_json(path / "components.json", _components(point))
    with (path / "state.npz").open("xb") as handle:
        np.savez(handle, **point.state._asdict())
        handle.flush()
        os.fsync(handle.fileno())
    if sources != source_hashes() or runtime != runtime_identity(spec.execution.backend):
        raise ConfigError("Source/runtime changed during held-protein checkpoint publication")
    # The seed writer does not fsync its payloads; make every outer-owned byte
    # durable before the final association becomes visible to the reader.
    for name in sorted(FILES):
        with (path / name).open("rb") as handle:
            os.fsync(handle.fileno())
    _sync_directory(path / "seed")
    payload = dict(
        kind=KIND,
        complete=True,
        checkpoint=interval.checkpoint_record(point),
        files={name: _sha(path / name) for name in sorted(FILES)},
    )
    _write_json(path / "manifest.json", payload | dict(identity=digest(payload)))
    _sync_directory(path)
    return path


def load_held_protein_checkpoint(directory):
    """Restore full context, recheck source pins and all charged balances."""
    path = Path(directory)
    manifest = read_json(path / "manifest.json")
    if type(manifest) is not dict or set(manifest) != FIELDS:
        raise ConfigError("Incomplete held-protein restart manifest")
    payload = {key: value for key, value in manifest.items() if key != "identity"}
    if (
        manifest["kind"] != KIND
        or manifest["complete"] is not True
        or manifest["identity"] != digest(payload)
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != FILES
    ):
        raise ConfigError("Invalid held-protein restart kind/completeness/identity")
    for name, expected in manifest["files"].items():
        if _sha(path / name) != expected:
            raise ConfigError("Held-protein restart payload changed: " + name)
    seed = load_snapshot(path / "seed")
    try:
        binding = units.restore_binding(read_json(path / "binding.json"), seed.spec)
        records = read_json(path / "components.json")
        if type(records) is not dict or set(records) != {"charge_reference", "component"}:
            raise ValueError("Missing fixed protein reference/component")
        components = {}
        for name, record in records.items():
            if type(record) is not dict or set(record) != {"stream", "state"}:
                raise ValueError("Incomplete component/RNG association")
            stream = streams.restore_stream(record["stream"], binding.component)
            components[name] = _restore_component(record["state"], binding.component, stream)
        with np.load(path / "state.npz", allow_pickle=False) as archive:
            names = seed.checkpoint.state._fields
            if set(archive.files) != set(names) or len(archive.files) != len(names):
                raise ValueError("Incomplete or duplicate charged numeric state fields")
            state = type(seed.checkpoint.state)(*(archive[name] for name in names))
        # Build through the same initial-context admission. No trusted bypass
        # accepts a current endpoint merely because its byte checksums match.
        record = manifest["checkpoint"]
        initial = interval.initialise(
            seed.spec,
            seed.checkpoint,
            binding,
            components["charge_reference"],
            components["component"],
            protein_species_id=record["protein_species_id"],
            valence=record["valence"],
        )
        point = replace(
            initial,
            state=interval.view._immutable_tree(state),
            time=record["time"],
            step_index=record["step_index"],
            event_index=record["event_index"],
            identity=record["identity"],
        )
        if interval.checkpoint_record(point) != record:
            raise ValueError("Numeric seed/reference/component/endpoint association differs")
        interval.validate(seed.spec, point)
        return HeldProteinSnapshot(seed.spec, point, manifest["identity"])
    except (KeyError, TypeError, ValueError, NumericalError) as error:
        raise ConfigError("Invalid held-protein restart: " + str(error)) from error
