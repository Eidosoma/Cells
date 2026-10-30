"""Durable complete ideal-ramp histories around unchanged ordinary checkpoints."""

import os
import zipfile
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from cells import io as numeric_io
from cells import physiology_checkpoint as durable
from cells.core import physiology_boundary_voltage as boundary
from cells.core import physiology_boundary_voltage_transition as transition
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, read_json
from cells.models import physiology_boundary_voltage_transition_algebra as algebra

KIND = "cells.physiology_boundary_voltage_transition_checkpoint@1"
FILES = frozenset(
    ("numeric/manifest.json", "numeric/state.npz", "transition.json", "transition.npz")
)
ARRAY_FIELDS = tuple(row.name for row in fields(algebra.CapacitiveChange))[:5]
SCALAR_FIELDS = tuple(row.name for row in fields(algebra.CapacitiveChange))[5:]


@dataclass(frozen=True, slots=True)
class TransitionSnapshot:
    spec: object
    checkpoint: transition.TransitionCheckpoint
    identity: str


def write_transition_checkpoint(directory, spec, point, *, expected_source_hashes=None):
    transition.validate(spec, point)
    sources = numeric_io.source_hashes()
    if expected_source_hashes is not None and sources != expected_source_hashes:
        raise ConfigError("Source differs from the accepted ideal capacitive ramp")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    try:
        numeric_io.write_snapshot(root / "numeric", spec, point.numeric)
        arrays = {"control_" + key: value for key, value in point.control._asdict().items()}
        arrays.update(
            origin_boundary_voltage_V=point.origin_boundary_state.boundary_voltage_V,
            current_boundary_voltage_V=point.boundary_state.boundary_voltage_V,
            cumulative_electrode_charge_C=point.cumulative_electrode_charge_C,
            cumulative_external_work_pJ=point.cumulative_external_work_pJ,
        )
        for i, row in enumerate(point.segments):
            arrays.update({f"segment_{i}_{key}": getattr(row.change, key) for key in ARRAY_FIELDS})
        with (root / "transition.npz").open("xb") as handle:
            np.savez_compressed(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
        durable._write_json(
            root / "transition.json",
            dict(
                binding=boundary.record(point.binding),
                checkpoint=transition.record(point),
                declarations=[
                    transition.declaration_record(row.declaration) for row in point.segments
                ],
                changes=[
                    {key: getattr(row.change, key) for key in SCALAR_FIELDS}
                    for row in point.segments
                ],
            ),
        )
        for path in (root / "numeric").iterdir():
            if path.is_file():
                with path.open("rb") as handle:
                    os.fsync(handle.fileno())
        durable._sync_directory(root / "numeric")
        if numeric_io.source_hashes() != sources:
            raise ConfigError("Source changed during ideal-ramp checkpoint publication")
        payload = dict(
            kind=KIND,
            complete=True,
            checkpoint_identity=point.identity,
            files={name: durable._sha(root / name) for name in sorted(FILES)},
        )
        durable._write_json(root / "manifest.json", payload | dict(identity=digest(payload)))
        durable._sync_directory(root)
        durable._sync_directory(root.parent)
    except Exception as error:
        durable._write_json(
            root / "failure.json", dict(type=type(error).__name__, message=str(error))
        )
        raise
    return root


def load_transition_checkpoint(directory):
    root = Path(directory)
    if (root / "failure.json").exists():
        raise ConfigError("Failed ideal-ramp checkpoint publication")
    manifest = read_json(root / "manifest.json")
    if type(manifest) is not dict or set(manifest) != {
        "kind",
        "complete",
        "checkpoint_identity",
        "files",
        "identity",
    }:
        raise ConfigError("Incomplete ideal-ramp checkpoint manifest")
    payload = {key: value for key, value in manifest.items() if key != "identity"}
    if (
        manifest["kind"] != KIND
        or manifest["complete"] is not True
        or manifest["identity"] != digest(payload)
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != FILES
    ):
        raise ConfigError("Invalid ideal-ramp checkpoint identity or payload list")
    for name, expected in manifest["files"].items():
        if durable._sha(root / name) != expected:
            raise ConfigError("Ideal-ramp checkpoint payload changed: " + name)
    original = numeric_io.load_snapshot(root / "numeric")
    try:
        saved = read_json(root / "transition.json")
        if type(saved) is not dict or set(saved) != {
            "binding",
            "checkpoint",
            "declarations",
            "changes",
        }:
            raise ValueError("Incomplete ideal-ramp association payload")
        declarations, changes = saved["declarations"], saved["changes"]
        if (
            type(declarations) is not list
            or type(changes) is not list
            or len(declarations) != len(changes)
            or len(declarations) > transition.MAX_CAPACITY
        ):
            raise ValueError("Incomplete or excessive ideal-ramp history")
        binding = boundary.restore(saved["binding"], original.spec)
        table = control_values(original.spec, [original.checkpoint.time])
        expected_names = (
            {"control_" + key for key in table._fields}
            | {
                "origin_boundary_voltage_V",
                "current_boundary_voltage_V",
                "cumulative_electrode_charge_C",
                "cumulative_external_work_pJ",
            }
            | {f"segment_{i}_{key}" for i in range(len(changes)) for key in ARRAY_FIELDS}
        )
        with np.load(root / "transition.npz", allow_pickle=False) as archive:
            if set(archive.files) != expected_names or len(archive.files) != len(expected_names):
                raise ValueError("Incomplete or extended ideal-ramp numeric fields")
            arrays = {key: boundary._freeze(archive[key]) for key in expected_names}
        control = type(table)(*(arrays["control_" + key] for key in table._fields))
        segments = []
        for i, (declaration, scalar) in enumerate(zip(declarations, changes, strict=True)):
            if type(scalar) is not dict or set(scalar) != set(SCALAR_FIELDS):
                raise ValueError("Incomplete or extended ideal-ramp scalar diagnostics")
            change = algebra.CapacitiveChange(
                **({key: arrays[f"segment_{i}_{key}"] for key in ARRAY_FIELDS} | scalar)
            )
            segments.append(transition.Segment(transition.restore_declaration(declaration), change))
        point = transition.restore(
            saved["checkpoint"],
            original.spec,
            original.checkpoint,
            binding,
            control,
            boundary.BoundaryState(arrays["origin_boundary_voltage_V"]),
            boundary.BoundaryState(arrays["current_boundary_voltage_V"]),
            tuple(segments),
            arrays["cumulative_electrode_charge_C"],
            arrays["cumulative_external_work_pJ"],
        )
        if point.identity != manifest["checkpoint_identity"]:
            raise ValueError("Saved ideal-ramp parent association differs from outer manifest")
    except (KeyError, TypeError, ValueError, NumericalError, zipfile.BadZipFile) as error:
        raise ConfigError("Invalid ideal-ramp checkpoint association: " + str(error)) from error
    return TransitionSnapshot(original.spec, point, manifest["identity"])


def advance_transition_checkpoint(source, destination, declaration):
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    sources = numeric_io.source_hashes()
    loaded = load_transition_checkpoint(source)
    if numeric_io.source_hashes() != sources:
        raise ConfigError("Source changed during ideal-ramp checkpoint loading")
    result = transition.advance(loaded.spec, loaded.checkpoint, declaration)
    write_transition_checkpoint(
        target, loaded.spec, result.checkpoint, expected_source_hashes=sources
    )
    return result
