"""Preserve reproducible initialization when entering complete ordinary loops.

The handoff adds a zero-loop cursor without a component call or a random draw.
Its managed child uses the existing complete-loop checkpoint interface; the
origin bundle retains the earlier selection/static tapes and recipe separately.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from cells import physiology_initial_preparation_io as initial_io
from cells.core import physiology_initial_preparation as initial
from cells.core import physiology_tissue_loop as loop
from cells.core.specs import ConfigError, digest
from cells.io import runtime_identity, source_hashes

paired = initial.paired
KIND = "cells.physiology_initial_loop_handoff@1"
FILES = {"origin/manifest.json", "loop/manifest.json", "handoff.json"}


@dataclass(frozen=True, slots=True)
class Handoff:
    initialization: initial.Initialization
    cursor: loop.TissueLoopCursor


def prepare(initialized):
    """Declare the first complete-loop boundary; preserve both tapes exactly."""
    initial.validate(initialized)
    return Handoff(
        initialized,
        loop.initialise(
            initialized.spec,
            initialized.checkpoint,
            initialized.binding,
            initialized.component,
            loop_index=0,
        ),
    )


def record(value):
    if type(value) is not Handoff:
        raise ConfigError("Require a complete initial-loop handoff")
    origin = value.initialization
    payload = dict(
        kind=KIND,
        initialization_identity=origin.provenance["identity"],
        source_definition_sha256=origin.spec.fingerprint,
        binding_identity=origin.binding.identity,
        cursor=loop.cursor_record(value.cursor),
    )
    return payload | dict(identity=digest(payload))


def validate(value):
    if type(value) is not Handoff:
        raise ConfigError("Require a complete initial-loop handoff")
    expected = prepare(value.initialization)
    if record(value) != record(expected):
        raise ConfigError("Handoff differs from the actual zero-loop initial pair")


def write_handoff(directory, value, *, expected_source_hashes=None):
    root = Path(directory)
    if root.exists() or root.is_symlink():
        raise FileExistsError(root)
    sources, runtime = source_hashes(), runtime_identity("cpu")
    if expected_source_hashes is not None and sources != expected_source_hashes:
        raise ConfigError("Initial-loop sources changed before publication")
    validate(value)
    origin = value.initialization
    root.mkdir(parents=True, exist_ok=False)
    try:
        # The existing origin publisher audits private tapes. The committed
        # component and cursor below retain the original single static draw.
        initial_io.write_initialization(root / "origin", origin, expected_source_hashes=sources)
        paired.write_physiology_checkpoint(
            root / "loop",
            origin.spec,
            origin.checkpoint,
            origin.component.stream,
            origin.binding.component,
            component_state=origin.component,
            tissue_binding=origin.binding,
            loop_cursor=value.cursor,
            expected_source_hashes=sources,
        )
        paired._write_json(root / "handoff.json", record(value))
        if source_hashes() != sources or runtime_identity("cpu") != runtime:
            raise ConfigError("Initial-loop source/runtime changed during publication")
        payload = dict(
            kind=KIND,
            complete=True,
            source_hashes=sources,
            runtime=runtime,
            handoff_identity=record(value)["identity"],
            files={name: paired._sha(root / name) for name in sorted(FILES)},
        )
        paired._write_json(root / "manifest.json", payload | dict(identity=digest(payload)))
        paired._sync_directory(root)
        paired._sync_directory(root.parent)
    except Exception as error:
        paired._write_json(
            root / "failure.json", dict(type=type(error).__name__, message=str(error))
        )
        paired._sync_directory(root)
        raise
    return root


def load_handoff(directory):
    root = Path(directory)
    if (root / "failure.json").exists():
        raise ConfigError("Failed initial-loop publication")
    # A published bundle owns its children. Hash-valid links could otherwise
    # depend on files outside the bundle and break when it is moved or copied.
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ConfigError("Initial-loop bundle must not contain symbolic links")
    raw = initial.static.read_json(root / "manifest.json")
    initial.static._mapping(
        raw,
        {"kind", "complete", "source_hashes", "runtime", "handoff_identity", "files", "identity"},
        "initial-loop manifest",
    )
    if (
        raw["kind"] != KIND
        or raw["complete"] is not True
        or raw["identity"] != digest({k: v for k, v in raw.items() if k != "identity"})
        or raw["source_hashes"] != source_hashes()
        or raw["runtime"] != runtime_identity("cpu")
        or type(raw["files"]) is not dict
        or set(raw["files"]) != FILES
        or {p.name for p in root.iterdir()} != {"origin", "loop", "handoff.json", "manifest.json"}
    ):
        raise ConfigError("Invalid initial-loop inventory, source or runtime association")
    for name, checksum in raw["files"].items():
        if paired._sha(root / name) != checksum:
            raise ConfigError("Changed initial-loop payload: " + name)
    origin = initial_io.load_initialization(root / "origin")
    value = prepare(origin)
    saved = initial.static.read_json(root / "handoff.json")
    if saved != record(value) or raw["handoff_identity"] != saved["identity"]:
        raise ConfigError("Handoff differs from its complete initialization origin")
    actual = paired.load_physiology_checkpoint(
        root / "loop",
        origin.binding.component,
        expected_stream_id=origin.component.stream.stream_id,
        expected_world_id=origin.component.stream.world_id,
        require_component=True,
        tissue_binding=origin.binding,
        require_tissue_binding=True,
        loop_cursor=value.cursor,
        require_loop_cursor=True,
    )
    # Do not accept independently valid but different initial/managed children.
    if (
        actual.snapshot.spec.fingerprint != origin.spec.fingerprint
        or initial._arrays(actual.snapshot.checkpoint) != initial._arrays(origin.checkpoint)
        or initial._json(
            paired._component_record(
                actual.component_state, origin.binding.component, actual.stream
            )
        )
        != initial._json(origin.provenance["component"])
    ):
        raise ConfigError("Managed loop child differs from the complete initial state")
    if source_hashes() != raw["source_hashes"] or runtime_identity("cpu") != raw["runtime"]:
        raise ConfigError("Initial-loop source/runtime changed during restoration")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("prepare")
    command.add_argument("source", type=Path)
    command.add_argument("--output", type=Path, required=True)
    commands.add_parser("validate").add_argument("source", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            if args.output.exists() or args.output.is_symlink():
                raise FileExistsError(args.output)
            sources = source_hashes()
            value = prepare(initial_io.load_initialization(args.source))
            write_handoff(args.output, value, expected_source_hashes=sources)
        else:
            value = load_handoff(args.source)
        print(initial.targets._json(dict(status="passed", **record(value))))
        return 0
    except (ConfigError, OSError, ValueError, KeyError, TypeError) as error:
        print("initial-loop handoff: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
