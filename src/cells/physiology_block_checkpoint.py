"""Durable blocker/current-state association around the existing bound snapshot."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells import physiology_checkpoint as paired
from cells.core import physiology_block_control_step as step
from cells.core.specs import ConfigError, digest, read_json
from cells.io import source_hashes
from cells.models import physiology_block_control_view as blocks

KIND = "cells.physiology_block_checkpoint@1"
FILES = frozenset(("numeric/manifest.json", "block.json"))


@dataclass(frozen=True, slots=True)
class BlockSnapshot:
    spec: object
    checkpoint: step.BlockCheckpoint
    identity: str


def write_block_checkpoint(directory, spec, point, *, expected_source_hashes=None):
    step.validate(spec, point)
    sources = source_hashes()
    if expected_source_hashes is not None and sources != expected_source_hashes:
        raise ConfigError("Source differs from the accepted blocked interval")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    try:
        paired.write_physiology_checkpoint(
            root / "numeric",
            spec,
            point.numeric,
            point.component.stream,
            point.tissue_binding.component,
            component_state=point.component,
            tissue_binding=point.tissue_binding,
            expected_source_hashes=sources,
        )
        paired._write_json(
            root / "block.json",
            dict(
                binding=blocks.record(point.binding),
                state={k: np.asarray(v).tolist() for k, v in point.block_state._asdict().items()},
            ),
        )
        if source_hashes() != sources:
            raise ConfigError("Source changed during blocker checkpoint publication")
        payload = dict(
            kind=KIND,
            complete=True,
            checkpoint=step.record(point),
            files={name: paired._sha(root / name) for name in sorted(FILES)},
        )
        paired._write_json(root / "manifest.json", payload | dict(identity=digest(payload)))
        paired._sync_directory(root)
        paired._sync_directory(root.parent)
    except Exception as error:
        paired._write_json(
            root / "failure.json", dict(type=type(error).__name__, message=str(error))
        )
        raise
    return root


def load_block_checkpoint(directory, tissue_binding):
    """Restore the exact requested owners, current block buffer and unchanged RNG."""
    root = Path(directory)
    if (root / "failure.json").exists():
        raise ConfigError("Failed blocker checkpoint publication")
    manifest = read_json(root / "manifest.json")
    if type(manifest) is not dict or set(manifest) != {
        "kind",
        "complete",
        "checkpoint",
        "files",
        "identity",
    }:
        raise ConfigError("Incomplete blocker checkpoint manifest")
    payload = {k: v for k, v in manifest.items() if k != "identity"}
    if (
        manifest["kind"] != KIND
        or manifest["complete"] is not True
        or manifest["identity"] != digest(payload)
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != FILES
    ):
        raise ConfigError("Invalid blocker checkpoint identity or payload list")
    for name, expected in manifest["files"].items():
        if paired._sha(root / name) != expected:
            raise ConfigError("Blocker checkpoint payload changed: " + name)
    base = paired.load_physiology_checkpoint(
        root / "numeric",
        tissue_binding.component,
        tissue_binding=tissue_binding,
        require_component=True,
        require_tissue_binding=True,
    )
    if base.loop_cursor is not None:
        raise ConfigError("A loop-owned pair cannot become a blocker-only interval")
    try:
        saved = read_json(root / "block.json")
        if type(saved) is not dict or set(saved) != {"binding", "state"}:
            raise ValueError("Incomplete block-state payload")
        if type(saved["state"]) is not dict or set(saved["state"]) != set(
            blocks.BlockState._fields
        ):
            raise ValueError("Incomplete block factors")
        binding = blocks.restore(saved["binding"], base.snapshot.spec, base.tissue_binding)
        state = blocks.BlockState(
            **{k: np.asarray(v, dtype=np.float64) for k, v in saved["state"].items()}
        )
        canonical = {k: np.asarray(v).tolist() for k, v in state._asdict().items()}
        if step.seals._json(canonical) != step.seals._json(saved["state"]):
            raise ValueError("Block factors require canonical float64 JSON values")
        point = step.restore(
            manifest["checkpoint"],
            base.snapshot.spec,
            base.snapshot.checkpoint,
            base.tissue_binding,
            base.component_state,
            binding,
            state,
        )
    except (KeyError, TypeError, ValueError, step.NumericalError) as error:
        raise ConfigError("Invalid blocker checkpoint association: " + str(error)) from error
    return BlockSnapshot(base.snapshot.spec, point, manifest["identity"])


def advance_block_checkpoint(source, destination, tissue_binding, *, end_time_s=None):
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    sources = source_hashes()
    loaded = load_block_checkpoint(source, tissue_binding)
    if source_hashes() != sources:
        raise ConfigError("Source changed during blocker checkpoint loading")
    result = step.advance(loaded.spec, loaded.checkpoint, end_time_s=end_time_s)
    write_block_checkpoint(target, loaded.spec, result.checkpoint, expected_source_hashes=sources)
    return result
