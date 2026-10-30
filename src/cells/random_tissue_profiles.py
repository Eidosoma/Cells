"""Prepare, replay and validate physical tissue profiles with owned native RNGs."""

import argparse
import sys
from pathlib import Path

from cells import physiology_checkpoint as durable
from cells import tissue_profiles as static
from cells.core import physiology_target_selection as selection
from cells.core import random_tissue_profile_preparation as preparation
from cells.core.specs import ConfigError, digest
from cells.io import runtime_identity, source_hashes

KIND = "cells.random_tissue_profile_bundle@1"
FILES = frozenset(("definition.json", "provenance.json", "stream.json"))


def write_preparation(directory, prepared, *, expected_source_hashes=None):
    root = Path(directory)
    if root.exists() or root.is_symlink():
        raise FileExistsError(root)
    sources, runtime = source_hashes(), runtime_identity("cpu")
    if expected_source_hashes is not None and sources != expected_source_hashes:
        raise ConfigError("Source differs from the random preparation request")
    checked = preparation.replay(prepared.provenance)
    if selection._json(checked.definition) != selection._json(
        prepared.definition
    ) or selection.stream_record(checked.stream) != selection.stream_record(prepared.stream):
        raise ConfigError("Prepared definition or successor tape differs from its complete recipe")
    if source_hashes() != sources or runtime_identity("cpu") != runtime:
        raise ConfigError("Source/runtime changed during preparation replay")
    root.mkdir(parents=True, exist_ok=False)
    try:
        for name, value in (
            ("definition.json", checked.definition),
            ("provenance.json", checked.provenance),
            ("stream.json", selection.stream_record(checked.stream)),
        ):
            durable._write_json(root / name, value)
        if source_hashes() != sources or runtime_identity("cpu") != runtime:
            raise ConfigError("Source/runtime changed during preparation publication")
        payload = dict(
            kind=KIND,
            complete=True,
            preparation_identity=checked.provenance["identity"],
            files={name: durable._sha(root / name) for name in sorted(FILES)},
            source_hashes=sources,
            runtime=runtime,
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


def read_preparation(directory):
    root = Path(directory)
    if (root / "failure.json").exists():
        raise ConfigError("Failed random preparation publication")
    manifest = static.read_json(root / "manifest.json")
    static._mapping(
        manifest,
        {
            "kind",
            "complete",
            "preparation_identity",
            "files",
            "source_hashes",
            "runtime",
            "identity",
        },
        "random preparation manifest",
    )
    payload = {key: value for key, value in manifest.items() if key != "identity"}
    if (
        manifest["kind"] != KIND
        or manifest["complete"] is not True
        or digest(payload) != manifest["identity"]
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != FILES
        or manifest["source_hashes"] != source_hashes()
        or manifest["runtime"] != runtime_identity("cpu")
    ):
        raise ConfigError("Invalid random preparation identity, source or runtime")
    for name, expected in manifest["files"].items():
        if durable._sha(root / name) != expected:
            raise ConfigError("Random preparation payload changed: " + name)
    prepared = preparation.replay(static.read_json(root / "provenance.json"))
    if (
        prepared.provenance["identity"] != manifest["preparation_identity"]
        or selection._json(static.read_json(root / "definition.json"))
        != selection._json(prepared.definition)
        or selection._json(static.read_json(root / "stream.json"))
        != selection._json(selection.stream_record(prepared.stream))
    ):
        raise ConfigError("Saved physical definition or successor stream changed")
    if manifest["source_hashes"] != source_hashes() or manifest["runtime"] != runtime_identity(
        "cpu"
    ):
        raise ConfigError("Source/runtime changed while reading random preparation")
    return prepared


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m cells.random_tissue_profiles", description=__doc__
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "replay"):
        command = commands.add_parser(name)
        command.add_argument("input", type=Path)
        command.add_argument("--output", type=Path, required=True)
    commands.add_parser("validate").add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            prepared = read_preparation(args.input)
        else:
            if args.output.exists() or args.output.is_symlink():
                raise FileExistsError(args.output)
            sources = source_hashes()
            value = static.read_json(args.input)
            prepared = (
                preparation.prepare(value)
                if args.command == "prepare"
                else preparation.replay(value)
            )
            write_preparation(args.output, prepared, expected_source_hashes=sources)
        print(
            selection._json(
                dict(
                    status="valid" if args.command == "validate" else "prepared",
                    kind=KIND,
                    model_id=prepared.definition["model"]["id"],
                    definition_sha256=digest(prepared.definition),
                    preparation_identity=prepared.provenance["identity"],
                    next_selection_call=prepared.stream.next_call,
                    scope="Initial tissue definition and complete native selection tapes",
                )
            )
        )
        return 0
    except (ConfigError, OSError, ValueError, TypeError) as error:
        print(f"random tissue profiles: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
