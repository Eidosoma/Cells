"""Durable initial tissue/component bundle with draw-free restoration."""

import argparse
import sys
from pathlib import Path

from cells import physiology_checkpoint as paired
from cells import tissue_profiles as strict
from cells.core import physiology_initial_preparation as preparation
from cells.core import physiology_tissue_binding as units
from cells.core.specs import ConfigError, digest, parse_spec
from cells.io import runtime_identity, source_hashes

KIND = "cells.physiology_initial_bundle@1"
FILES = {"initialization.json", "physiology/manifest.json"}


def write_initialization(directory, initialized, *, expected_source_hashes=None):
    root = Path(directory)
    if root.exists() or root.is_symlink():
        raise FileExistsError(root)
    sources, runtime = source_hashes(), runtime_identity("cpu")
    if expected_source_hashes is not None and sources != expected_source_hashes:
        raise ConfigError("Initialization source changed before publication")
    preparation.validate(initialized)
    # Publication audits from private original tapes. The one committed static
    # draw is already represented by initialized.component's saved successor.
    checked = preparation.replay(initialized.provenance)
    if source_hashes() != sources or runtime_identity("cpu") != runtime:
        raise ConfigError("Initialization source/runtime changed during admission")
    root.mkdir(parents=True, exist_ok=False)
    try:
        paired.write_physiology_checkpoint(
            root / "physiology",
            checked.spec,
            checked.checkpoint,
            checked.component.stream,
            checked.binding.component,
            component_state=checked.component,
            tissue_binding=checked.binding,
            expected_source_hashes=sources,
        )
        paired._write_json(root / "initialization.json", checked.provenance)
        if source_hashes() != sources or runtime_identity("cpu") != runtime:
            raise ConfigError("Initialization source/runtime changed during publication")
        payload = dict(
            kind=KIND,
            complete=True,
            initialization_identity=checked.provenance["identity"],
            source_hashes=sources,
            runtime=runtime,
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


def load_initialization(directory):
    root = Path(directory)
    if (root / "failure.json").exists():
        raise ConfigError("Failed initial physiology publication")
    manifest = strict.read_json(root / "manifest.json")
    strict._mapping(
        manifest,
        {
            "kind",
            "complete",
            "initialization_identity",
            "source_hashes",
            "runtime",
            "files",
            "identity",
        },
        "initial physiology manifest",
    )
    payload = {k: v for k, v in manifest.items() if k != "identity"}
    if (
        manifest["kind"] != KIND
        or manifest["complete"] is not True
        or digest(payload) != manifest["identity"]
        or manifest["source_hashes"] != source_hashes()
        or manifest["runtime"] != runtime_identity("cpu")
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != FILES
    ):
        raise ConfigError("Invalid initial physiology manifest, source or runtime")
    if {path.name for path in root.iterdir()} != {
        "physiology",
        "initialization.json",
        "manifest.json",
    }:
        raise ConfigError("Unexpected initial bundle artifacts")
    for name, sha in manifest["files"].items():
        if paired._sha(root / name) != sha:
            raise ConfigError("Changed initialization payload: " + name)
    record = strict.read_json(root / "initialization.json")
    if record["identity"] != manifest["initialization_identity"]:
        raise ConfigError("Initialization association differs from manifest")
    spec = parse_spec(record["definition"])
    binding = units.restore_binding(record["binding"], spec)
    active = record["active_stream"]
    loaded = paired.load_physiology_checkpoint(
        root / "physiology",
        binding.component,
        expected_stream_id=active["stream_id"],
        expected_world_id=active["world_id"],
        require_component=True,
        tissue_binding=binding,
        require_tissue_binding=True,
    )
    result = preparation.Initialization(
        loaded.snapshot.spec, loaded.snapshot.checkpoint, binding, loaded.component_state, record
    )
    preparation.validate(result)
    if manifest["source_hashes"] != source_hashes() or manifest["runtime"] != runtime_identity(
        "cpu"
    ):
        raise ConfigError("Initialization source/runtime changed during restoration")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "replay"):
        command = commands.add_parser(name)
        command.add_argument("input", type=Path)
        command.add_argument("--output", type=Path, required=True)
    commands.add_parser("validate").add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = load_initialization(args.input)
        else:
            if args.output.exists() or args.output.is_symlink():
                raise FileExistsError(args.output)
            sources = source_hashes()
            value = strict.read_json(args.input)
            result = (
                preparation.initialize(value)
                if args.command == "prepare"
                else preparation.replay(value)
            )
            write_initialization(args.output, result, expected_source_hashes=sources)
        print(
            preparation.targets._json(
                dict(
                    status="passed",
                    kind=KIND,
                    initialization_identity=result.provenance["identity"],
                    next_component_tick=result.component.stream.next_tick,
                    scope=preparation.SCOPE,
                )
            )
        )
        return 0
    except (ConfigError, OSError, ValueError, KeyError, TypeError) as error:
        print("physiology initialization: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
