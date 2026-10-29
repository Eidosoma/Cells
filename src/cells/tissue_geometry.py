"""Prepare, validate and replay an initial passive tissue from explicit geometry."""

import argparse
import json
import sys
from pathlib import Path

from cells.core import geometry_tissue_preparation as bridge
from cells.core.specs import ConfigError, digest


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _nonfinite(value):
    raise ConfigError(f"Nonfinite JSON value: {value}")


def read_json(path):
    """Reject duplicate keys, nonstandard constants and overflowed literals."""
    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_nonfinite,
        )
        json.dumps(value, allow_nan=False)
        return value
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ConfigError(f"Invalid finite JSON in {path}: {error}") from error


def prepare_request(request):
    """Use the frozen component without adding or inferring physical inputs."""
    try:
        return bridge.prepare(request)
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as error:
        raise ConfigError("Invalid initial geometry preparation request: " + str(error)) from error


def replay(provenance):
    try:
        if type(provenance) is not dict or provenance.get("kind") != bridge.KIND:
            raise ConfigError("Require complete initial static geometry preparation provenance")
        json.dumps(provenance, allow_nan=False)
        expected = bridge.replay(provenance)
        if digest(expected.provenance) != digest(provenance):
            raise ConfigError("Complete preparation provenance changed its JSON identity")
        return expected
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as error:
        raise ConfigError(
            "Invalid initial geometry preparation provenance: " + str(error)
        ) from error


def read_preparation(directory):
    """Strictly parse both files and compare them with the complete recipe."""
    path = Path(directory)
    provenance = read_json(path / "provenance.json")
    definition = read_json(path / "definition.json")
    expected = replay(provenance)
    if digest(definition) != digest(expected.definition):
        raise ConfigError("Prepared definition changed relative to its geometry/physics recipe")
    return expected


def _parser():
    parser = argparse.ArgumentParser(prog="cells.tissue_geometry", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("prepare", "prepare an ordinary passive tissue from a complete JSON request"),
        ("replay", "rebuild from a complete provenance JSON file"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("input", type=Path)
        command.add_argument("--output", type=Path, required=True, help="new directory")
    command = commands.add_parser("validate", help="verify both files in a preparation directory")
    command.add_argument("input", type=Path)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            prepared = read_preparation(args.input)
        else:
            if args.output.exists() or args.output.is_symlink():
                raise ConfigError(f"Output already exists; choose a new directory: {args.output}")
            value = read_json(args.input)
            prepared = prepare_request(value) if args.command == "prepare" else replay(value)
            bridge.write_preparation(args.output, prepared)
        model = prepared.definition["model"]
        summary = dict(
            status={"prepare": "prepared", "replay": "replayed", "validate": "valid"}[args.command],
            kind=prepared.provenance["kind"],
            model_id=model["id"],
            volume_policy=prepared.provenance["volume_policy"],
            owners={
                key: len(model[key])
                for key in ("cells", "extracellular", "membranes", "junctions", "faces")
            },
            definition_sha256=digest(prepared.definition),
            preparation_identity=prepared.provenance["identity"],
            geometry_identity=prepared.provenance["geometry_manifest"]["identity"],
        )
        if args.command != "validate":
            summary["output"] = str(args.output)
        print(json.dumps(summary, indent=2, allow_nan=False))
        return 0
    except (ConfigError, OSError, ValueError, TypeError, RecursionError) as error:
        print(f"cells.tissue_geometry: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
