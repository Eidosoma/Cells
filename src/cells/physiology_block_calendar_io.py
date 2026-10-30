"""Durable association of original native phase, accepted call and blocker state."""

from dataclasses import dataclass
from pathlib import Path

from cells import physiology_block_checkpoint as blocked
from cells.core import physiology_block_calendar as calls
from cells.core import physiology_native_calendar as clocks
from cells.core.specs import ConfigError, digest, read_json
from cells.io import source_hashes

KIND = "cells.physiology_block_calendar_checkpoint@1"
FILES = frozenset(("point/manifest.json", "calendar.json"))


@dataclass(frozen=True, slots=True)
class CalendarSnapshot:
    spec: object
    checkpoint: calls.CalendarCheckpoint
    identity: str


def write_calendar_checkpoint(directory, spec, checkpoint, *, expected_source_hashes=None):
    calls.validate(spec, checkpoint)
    sources = source_hashes()
    if expected_source_hashes is not None and sources != expected_source_hashes:
        raise ConfigError("Source differs from the accepted native-calendar call")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    try:
        blocked.write_block_checkpoint(
            root / "point", spec, checkpoint.point, expected_source_hashes=sources
        )
        blocked.paired._write_json(root / "calendar.json", clocks.record(checkpoint.calendar))
        if source_hashes() != sources:
            raise ConfigError("Source changed during native-calendar checkpoint publication")
        payload = dict(
            kind=KIND,
            complete=True,
            checkpoint=calls.record(checkpoint),
            files={name: blocked.paired._sha(root / name) for name in sorted(FILES)},
        )
        blocked.paired._write_json(root / "manifest.json", payload | dict(identity=digest(payload)))
        blocked.paired._sync_directory(root)
        blocked.paired._sync_directory(root.parent)
    except Exception as error:
        blocked.paired._write_json(
            root / "failure.json", dict(type=type(error).__name__, message=str(error))
        )
        raise
    return root


def load_calendar_checkpoint(directory, tissue_binding):
    root = Path(directory)
    if (root / "failure.json").exists():
        raise ConfigError("Failed native-calendar checkpoint publication")
    manifest = read_json(root / "manifest.json")
    if type(manifest) is not dict or set(manifest) != {
        "kind",
        "complete",
        "checkpoint",
        "files",
        "identity",
    }:
        raise ConfigError("Incomplete native-calendar checkpoint manifest")
    payload = {k: v for k, v in manifest.items() if k != "identity"}
    if (
        manifest["kind"] != KIND
        or manifest["complete"] is not True
        or manifest["identity"] != digest(payload)
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != FILES
    ):
        raise ConfigError("Invalid native-calendar checkpoint identity or payload list")
    for name, expected in manifest["files"].items():
        if blocked.paired._sha(root / name) != expected:
            raise ConfigError("Native-calendar checkpoint payload changed: " + name)
    loaded = blocked.load_block_checkpoint(root / "point", tissue_binding)
    try:
        saved_calendar = read_json(root / "calendar.json")
        calendar = clocks.restore(
            saved_calendar,
            expected_identity=manifest["checkpoint"]["calendar_identity"],
        )
        if calls.intervals.seals._json(clocks.record(calendar)) != calls.intervals.seals._json(
            saved_calendar
        ):
            raise ValueError("Require canonical original calendar values")
        checkpoint = calls.restore(manifest["checkpoint"], loaded.spec, loaded.checkpoint, calendar)
    except (KeyError, TypeError, ValueError, calls.NumericalError) as error:
        raise ConfigError(
            "Invalid native-calendar checkpoint association: " + str(error)
        ) from error
    return CalendarSnapshot(loaded.spec, checkpoint, manifest["identity"])


def advance_calendar_checkpoint(source, destination, tissue_binding):
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    sources = source_hashes()
    loaded = load_calendar_checkpoint(source, tissue_binding)
    if source_hashes() != sources:
        raise ConfigError("Source changed during native-calendar checkpoint loading")
    result = calls.advance(loaded.spec, loaded.checkpoint)
    write_calendar_checkpoint(
        target, loaded.spec, result.checkpoint, expected_source_hashes=sources
    )
    return result
