"""Prepare and replay static tissue profiles from explicit JSON recipes."""

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import fields
from pathlib import Path

from cells.core import active_profile_barrier_preparation as active_combined
from cells.core import environment_barrier_composition_preparation as composed_barriers
from cells.core import environment_barrier_preparation as environment_barriers
from cells.core import geometry_profile_preparation as geometry_profiles
from cells.core import tissue_profile_composition_preparation as composed
from cells.core import tissue_profile_preparation as bridge
from cells.core.specs import ConfigError, digest
from cells.processes import betse_tissue_profiles as native

REQUEST_KIND = "cells.tissue_profile_preparation_request@1"
REQUEST_FIELDS = {
    "schema_version",
    "kind",
    "definition",
    "geometry",
    "default",
    "profiles",
    "ion_enabled",
    "enabled",
    "is_ecm",
}


def _mapping(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ConfigError(f"Require exactly the declared {label} fields: {sorted(keys)}")
    return value


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
    try:
        value = json.loads(
            Path(path).read_text(), object_pairs_hook=_unique_object, parse_constant=_nonfinite
        )
        # Also rejects overflowed numeric literals such as 1e999.
        json.dumps(value, allow_nan=False)
        return value
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ConfigError(f"Invalid finite JSON in {path}: {error}") from error


def _profile(row):
    _mapping(row, {f.name for f in fields(native.Profile)}, "profile")
    selector = _mapping(row["selector"], {f.name for f in fields(native.Selector)}, "selector")
    if selector["kind"] == "image":
        _mapping(selector["value"], {"grayscale_F"}, "decoded image")
    # Use the same decoding as the qualified preparation/replay contract. In
    # particular, native index selectors still require an explicit layout hash.
    return bridge._decode_profile(row)


def _definition_bridge(definition):
    if type(definition) is not dict or type(definition.get("model")) is not dict:
        raise ConfigError("Require a complete ordinary tissue definition")
    model_id = definition["model"].get("id")
    if type(model_id) is str:
        if model_id in bridge.SUPPORTED_MODELS:
            return bridge
        if model_id in composed.SCHEMAS:
            return composed
    raise ConfigError(
        "Unsupported tissue profile schema; cut, assembly and repair need new contracts"
    )


def _provenance_bridge(provenance):
    if type(provenance) is not dict:
        raise ConfigError("Require complete preparation provenance")
    if provenance.get("kind") == active_combined.KIND:
        return active_combined
    if provenance.get("kind") == environment_barriers.KIND:
        return environment_barriers
    if provenance.get("kind") == composed_barriers.KIND:
        return composed_barriers
    if provenance.get("kind") == geometry_profiles.KIND:
        return geometry_profiles
    if provenance.get("kind") == bridge.KIND:
        implementation, recipe = bridge, provenance
    elif provenance.get("kind") == composed.KIND:
        implementation = composed
        recipe = provenance.get("direct_parameter_preparation")
        if type(recipe) is not dict:
            raise ConfigError("Require complete composed preparation provenance")
    else:
        raise ConfigError("Unsupported preparation provenance kind")
    geometry = recipe.get("geometry")
    if type(geometry) is not dict or type(geometry.get("layout")) is not dict:
        raise ConfigError("Require complete preparation provenance with explicit geometry")
    return implementation


def prepare_request(request):
    """Convert a complete JSON request without inferring owners, units or order."""
    try:
        if type(request) is dict and request.get("kind") == active_combined.REQUEST_KIND:
            return active_combined.prepare(request)
        if type(request) is dict and request.get("kind") == environment_barriers.REQUEST_KIND:
            return environment_barriers.prepare(request)
        if type(request) is dict and request.get("kind") == composed_barriers.REQUEST_KIND:
            return composed_barriers.prepare(request)
        if type(request) is dict and request.get("kind") == geometry_profiles.REQUEST_KIND:
            return geometry_profiles.prepare(request)
        _mapping(request, REQUEST_FIELDS, "preparation request")
        if type(request["schema_version"]) is not int or request["schema_version"] != 1:
            raise ConfigError("Require preparation request schema_version 1")
        if request["kind"] != REQUEST_KIND:
            raise ConfigError("Require " + REQUEST_KIND)
        json.dumps(request, allow_nan=False)
        raw = deepcopy(request)
        geometry = _mapping(raw["geometry"], {f.name for f in fields(bridge.Geometry)}, "geometry")
        layout = _mapping(geometry.pop("layout"), {f.name for f in fields(native.Layout)}, "layout")
        if type(raw["profiles"]) is not list:
            raise ConfigError("Require an ordered JSON profile list")
        return _definition_bridge(raw["definition"]).prepare(
            raw["definition"],
            bridge.Geometry(native.Layout(**layout), **geometry),
            _profile(raw["default"]),
            [_profile(row) for row in raw["profiles"]],
            ion_enabled=raw["ion_enabled"],
            enabled=raw["enabled"],
            is_ecm=raw["is_ecm"],
        )
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid static tissue-profile request: " + str(error)) from error


def read_preparation(directory):
    """Apply strict JSON parsing as well as the qualified physical replay checks."""
    root = Path(directory)
    provenance = read_json(root / "provenance.json")
    definition = read_json(root / "definition.json")
    expected = replay(provenance)
    if digest(definition) != digest(expected.definition):
        raise ConfigError("Prepared definition changed relative to the complete physical recipe")
    return expected


def replay(provenance):
    try:
        expected = _provenance_bridge(provenance).replay(provenance)
        if digest(expected.provenance) != digest(provenance):
            raise ConfigError("Complete preparation provenance changed its JSON identity")
        return expected
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as error:
        raise ConfigError("Invalid static tissue-profile provenance: " + str(error)) from error


def _write_preparation(directory, prepared):
    implementation = _provenance_bridge(prepared.provenance)
    if implementation is not active_combined:
        return implementation.write_preparation(directory, prepared)
    checked = replay(prepared.provenance)
    if digest(checked.definition) != digest(prepared.definition):
        raise ConfigError("Combined definition disagrees with its complete preparation recipe")
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise ConfigError("Preparation output already exists")
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in (("definition", checked.definition), ("provenance", checked.provenance)):
        with (directory / (name + ".json")).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
    return directory


def _parser():
    parser = argparse.ArgumentParser(prog="cells tissue-profiles", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("prepare", "prepare a tissue definition from an explicit JSON request"),
        ("replay", "rebuild a tissue preparation from its complete provenance JSON"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("input", type=Path)
        command.add_argument("--output", type=Path, required=True, help="new directory")
    validate = commands.add_parser("validate", help="verify a complete preparation directory")
    validate.add_argument("input", type=Path)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            prepared = read_preparation(args.input)
        else:
            # Check before reading or evaluating a potentially expensive recipe.
            if args.output.exists() or args.output.is_symlink():
                raise ConfigError(f"Output already exists; choose a new directory: {args.output}")
            value = read_json(args.input)
            prepared = prepare_request(value) if args.command == "prepare" else replay(value)
            _write_preparation(args.output, prepared)
        if prepared.provenance["kind"] == active_combined.KIND:
            layers = {
                "membrane": len(
                    prepared.provenance["profile_preparation"]["provenance"]["changes"]
                ),
                "extracellular": len(
                    prepared.provenance["barrier_preparation"]["provenance"]["changes"]
                ),
            }
            changed = sum(layers.values())
        else:
            layers = None
            changed = len(prepared.provenance["changes"])
        summary = dict(
            status="valid" if args.command == "validate" else "prepared",
            kind=prepared.provenance["kind"],
            model_id=prepared.definition["model"]["id"],
            definition_sha256=digest(prepared.definition),
            preparation_identity=prepared.provenance["identity"],
            changed_coefficients=changed,
            scope="Static tissue preparation; trajectory and resource qualification are separate",
        )
        if args.command != "validate":
            summary["output"] = str(args.output)
        if layers is not None:
            summary["coefficient_changes_by_layer"] = layers
        print(json.dumps(summary, indent=2, allow_nan=False))
        return 0
    except (ConfigError, OSError, ValueError, TypeError) as error:
        print(f"cells tissue-profiles: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
