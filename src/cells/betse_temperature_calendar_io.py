"""Separate exact restart archive for the native temperature replay component."""

import hashlib
import json
import os
from pathlib import Path

from cells.core import physiology_native_calendar as clocks
from cells.processes import betse_global_controls as setters
from cells.processes import betse_temperature_calendar as replay

KIND = "cells.betse_temperature_calendar_archive@1"


def _sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write(path, value):
    with path.open("x") as stream:
        json.dump(replay.plain(value), stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def save_checkpoint(directory, binding, point):
    replay.validate(binding, point)
    root = Path(directory)
    root.mkdir(exist_ok=False)
    _write(
        root / "binding.json",
        dict(identity=binding.identity, binding=replay.binding_record(binding)),
    )
    _write(root / "checkpoint.json", replay.checkpoint_record(point))
    record = dict(
        kind=KIND,
        binding_identity=binding.identity,
        files={name: _sha(root / name) for name in ("binding.json", "checkpoint.json")},
    )
    _write(root / "manifest.json", record)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return record


def load_checkpoint(directory, *, expected_binding_identity):
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text())
    if (
        type(manifest) is not dict
        or set(manifest) != {"kind", "binding_identity", "files"}
        or manifest["kind"] != KIND
        or manifest["binding_identity"] != expected_binding_identity
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != {"binding.json", "checkpoint.json"}
    ):
        raise ValueError("Require the original complete source temperature archive manifest")
    for name, digest in manifest["files"].items():
        if _sha(root / name) != digest:
            raise ValueError("Source temperature archive file content changed: " + name)
    saved = json.loads((root / "binding.json").read_text())
    if type(saved) is not dict or set(saved) != {"identity", "binding"}:
        raise ValueError("Source temperature binding record is incomplete or extended")
    record = saved["binding"]
    if saved["identity"] != expected_binding_identity:
        raise ValueError("Source temperature archive differs from the original binding")
    try:
        calendar = clocks.restore(
            record["calendar"], expected_identity=record["calendar"]["identity"]
        )
        program = setters.restore(
            record["program"], expected_identity=record["program"]["identity"]
        )
        binding = replay.bind(record["definition"], calendar, program)
    except (KeyError, TypeError) as error:
        raise ValueError("Malformed original source temperature declaration") from error
    if binding.identity != expected_binding_identity or replay._json(
        replay.binding_record(binding)
    ) != replay._json(record):
        raise ValueError("Source temperature cache/owners/clock differ from the original inputs")
    point = replay.restore(binding, json.loads((root / "checkpoint.json").read_text()))
    return binding, point
