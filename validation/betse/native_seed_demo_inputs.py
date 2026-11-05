"""Prepare complete BETSE input data for two independent flux-operator modes.

This copies original data bytes and emits Key's existing path-permission input
program. The explicit headless profile changes only the two while-solving
animation switches; headless_core also disables cutting and the custom network
in fresh files. Neither changes numerical inputs. This never parses YAML, decodes an image,
imports BETSE or issues live parameters. Original output-directory placeholders
are retained; no simulation
output is produced until a separately released worker.
"""

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import native_seed_demo_input_profiles as profiles

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
NATIVE = BASE / "betse-v1.5.0/betse/data/yaml"
FILE = "validation/betse/native_seed_demo_inputs.py"
KIND = "cells.original_betse_seed_demo_input_pair@1"
HEADLESS_KIND = "cells.headless_betse_seed_demo_input_pair@1"
HEADLESS_CORE_KIND = "cells.headless_core_betse_seed_demo_input_pair@1"
MODES = ("original", "disabled")
MAX_FILES, MAX_BYTES, MAX_FILE_BYTES = 512, 16 * 2**20, 8 * 2**20
BUNDLE_SHA256 = "a46d83ac79195a2e15078feccd5e0fc62804ca1976042cc9516c30a9f859db27"
PARAMETER_METADATA_SHA256 = "e23dbe4c9e124f1e022939895ad7c07fa199a1af36623a47397ffb6a7e46c1ad"
CORE = {
    "sim_config.yaml": "7ed5a32f9fc256c541db63090aeed6d0207bf706d2847b27269d6bc8c9e85415",
    "extra_configs/expression_data.yaml": (
        "c1e47550c76dd5e3a89989c3e3258833426c5fab3188e40557ddef604eba396d"
    ),
    "extra_configs/grn_basic.yaml": (
        "f25edb13132685589c803b3b4a58d9b8af80f6f8885c9d32fac3be2e382339f2"
    ),
}


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def source_plan():
    return dict(
        kind=KIND,
        original_data_root=str(NATIVE),
        bundle_sha256=BUNDLE_SHA256,
        core_yaml_pins=dict(CORE),
        parameter_metadata_sha256=PARAMETER_METADATA_SHA256,
        modes=MODES,
        configuration_profiles=profiles.PROFILES,
        headless_configuration_changes=profiles.changes(),
        headless_core_configuration_changes=profiles.changes(profiles.HEADLESS_CORE),
        full_original_geo_and_extra_configs=True,
        unchanged_numeric_or_image_bytes=True,
        native_execution=False,
        actual_parameter_or_phase_authority=False,
        limits=dict(files=MAX_FILES, total_bytes=MAX_BYTES, file_bytes=MAX_FILE_BYTES),
    )


def kind_for_profile(profile):
    profiles.require_profile(profile)
    return {
        profiles.ORIGINAL: KIND,
        profiles.HEADLESS: HEADLESS_KIND,
        profiles.HEADLESS_CORE: HEADLESS_CORE_KIND,
    }[profile]


def _unlinked(path):
    path = Path(path)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or any(p.is_symlink() for p in (path, *path.parents))
    ):
        raise ValueError("Absolute unlinked path required")
    return path


def _output(path):
    path = _unlinked(path)
    if path.exists() or path == BASE or not path.is_relative_to(BASE):
        raise ValueError("Fresh contained run output required")
    for protected in (ROOT, NATIVE):
        if path == protected or path.is_relative_to(protected) or protected.is_relative_to(path):
            raise ValueError("Output intersects source data")
    return path


def inventory(root):
    """Bounded data inventory only, with no model or YAML evaluation."""
    root = _unlinked(root)
    if not root.is_dir():
        raise ValueError("Original data directory required")
    files, directories, total = {}, [], 0
    for path in root.rglob("*"):
        if len(files) + len(directories) >= 2 * MAX_FILES or path.is_symlink():
            raise ValueError("Unlinked bounded original tree required")
        info, name = path.lstat(), str(path.relative_to(root))
        if stat.S_ISDIR(info.st_mode):
            directories.append(name)
        elif stat.S_ISREG(info.st_mode):
            total += info.st_size
            if len(files) >= MAX_FILES or info.st_size > MAX_FILE_BYTES or total > MAX_BYTES:
                raise ValueError("Original data inventory exceeds declared bound")
            files[name] = dict(size_bytes=info.st_size, sha256=snapshot.digest(path))
        else:
            raise ValueError("Only ordinary files and directories are data inputs")
    return dict(directories=sorted(directories), files=dict(sorted(files.items())))


def _source():
    value = inventory(NATIVE)
    if type(BUNDLE_SHA256) is not str or _digest(value) != BUNDLE_SHA256:
        raise ValueError("Original complete data bundle changed or remains unbound")
    if any(value["files"].get(name, {}).get("sha256") != pin for name, pin in CORE.items()):
        raise ValueError("Original three YAML inputs changed")
    return value


def _program(root, profile=profiles.ORIGINAL):
    profiles.require_profile(profile)
    values = (
        ("init_pickle_dirname", "INITS"),
        ("sim_pickle_dirname", "SIMS"),
        ("init_pickle_filename", "INITS/init_1.betse.gz"),
        ("seed_pickle_filename", "INITS/world_1.betse.gz"),
        ("sim_pickle_filename", "SIMS/sim_1.betse.gz"),
        ("init_export_dirname", "RESULTS/init_1"),
        ("sim_export_dirname", "RESULTS/sim_1"),
        ("grn_config_filename", "extra_configs/grn_basic.yaml"),
        ("grn_pickle_dirname", "RESULTS/GRN"),
        ("grn_pickle_filename", "RESULTS/GRN/GRN_1.betse.gz"),
        ("grn_unpickle_filename", None),
    )
    core = dict(CORE)
    if profile != profiles.ORIGINAL:
        core[profiles.MAIN] = profiles.main_file(profile)["sha256"]
    value = dict(
        files={
            name: dict(input=dict(path=str(root / name), sha256=pin)) for name, pin in core.items()
        },
        ordered_path_permission=[
            [name, None if value is None else str(root / value)] for name, value in values
        ],
    )
    if profile != profiles.ORIGINAL:
        value["input_profile"] = profile
    return value


def _parameter_metadata():
    path = ROOT / "validation/betse/betse_native_parameter_world_ready_qualification.py"
    if path.is_symlink() or snapshot.digest(path) != PARAMETER_METADATA_SHA256:
        raise ValueError("Reviewed Key metadata interface changed")
    from validation.betse import betse_native_parameter_world_ready_qualification as parameter

    if Path(parameter.__file__).resolve() != path or parameter.RAW_FILES != CORE:
        raise ValueError("Actual selected parameter metadata producer required")
    return parameter


def _directory_state(directories):
    return [[name, Path(name).is_dir(), Path(name).exists()] for name in directories]


def _copy_file(source, target, expected):
    """No hard links: the two workers get independent, read-only input inodes."""
    digest = hashlib.sha256()
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as read, target.open("xb") as write:
        before = os.fstat(read.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != expected["size_bytes"]:
            raise ValueError("Source data changed before copying")
        while chunk := read.read(1024 * 1024):
            write.write(chunk)
            digest.update(chunk)
        write.flush()
        os.fsync(write.fileno())
        after = os.fstat(read.fileno())
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or digest.hexdigest() != expected["sha256"]:
            raise ValueError("Source data changed during copying")
    target.chmod(0o444)


def _copy_headless(source, target, expected, profile=profiles.HEADLESS):
    # The source is a bounded exact file, and the result is born in a fresh
    # independent inode. Never rewrite an already-issued configuration.
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as read:
        before = os.fstat(read.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != profiles.ORIGINAL_BYTES:
            raise ValueError("Exact bounded original main YAML required")
        original = read.read(profiles.ORIGINAL_BYTES + 1)
        after = os.fstat(read.fileno())
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError("Original main YAML changed during reading")
    value = profiles.transform(original, profile)
    if dict(size_bytes=len(value), sha256=hashlib.sha256(value).hexdigest()) != expected:
        raise ValueError("Declared input-profile target inventory changed")
    with target.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    target.chmod(0o444)


def _prepare(output, source, parameter, profile=profiles.ORIGINAL):
    selected = profiles.inventory(source, profile)
    output.mkdir(parents=True)
    cases = {}
    try:
        for mode in MODES:
            config = output / mode / "config"
            config.mkdir(parents=True)
            for directory in source["directories"]:
                (config / directory).mkdir(parents=True, exist_ok=True)
            for name, row in source["files"].items():
                if profile != profiles.ORIGINAL and name == profiles.MAIN:
                    _copy_headless(NATIVE / name, config / name, selected["files"][name], profile)
                else:
                    _copy_file(NATIVE / name, config / name, row)
            if inventory(config) != selected:
                raise ValueError("Complete copied input bytes/layout changed")
            program = output / mode / "input-program.json"
            snapshot.write_json(program, _program(config, profile))
            program.chmod(0o444)
            pin = snapshot.digest(program)
            checked = parameter.input_program(program, pin)
            if checked["root"] != str(config):
                raise ValueError("Actual copied input program root required")
            if checked.get("input_profile", profiles.ORIGINAL) != profile:
                raise ValueError("Actual parameter program must retain the declared profile")
            cases[mode] = dict(
                config=str(config),
                program=dict(path=str(program), sha256=pin),
                initial_native_directories=checked["directories"],
                initial_directory_state=_directory_state(checked["directories"]),
            )
        if inventory(NATIVE) != source:
            raise ValueError("Original data source changed during pair preparation")
        result = dict(
            kind=KIND,
            source_origin=str(NATIVE),
            source_tree_sha256=BUNDLE_SHA256,
            source_inventory=source,
            modes=cases,
            parameter_metadata_sha256=PARAMETER_METADATA_SHA256,
            raw_configuration_and_images_unchanged=True,
            independent_input_inodes=True,
            distribution_output_placeholders_preserved=True,
            native_simulation_outputs_created=False,
            native_execution=False,
            physical_or_scientific_claim=False,
            held=True,
        )
        if profile != profiles.ORIGINAL:
            result.update(
                kind=kind_for_profile(profile),
                configuration_profile=profile,
                configuration_changes=profiles.changes(profile),
                input_inventory=selected,
                raw_configuration_and_images_unchanged=False,
            )
        snapshot.write_json(output / "inputs.json", result)
        (output / "inputs.json").chmod(0o444)
        return result
    except BaseException as error:
        try:
            snapshot.write_json(
                output / "failure.json",
                dict(
                    status="failed",
                    error=type(error).__qualname__,
                    completed_modes=list(cases),
                    partial_files_preserved=True,
                    automatic_retry=False,
                    native_execution=False,
                ),
            )
        except BaseException as secondary:
            try:
                error.input_preparation_capture_error = secondary
            except BaseException:
                pass
        raise


def prepare(output, *, profile=profiles.ORIGINAL):
    profiles.require_profile(profile)
    output = _output(output)
    source, parameter = _source(), _parameter_metadata()
    return _prepare(output, source, parameter, profile)


def verify(output, expected_sha256, *, mode=None):
    """Verify a fresh selected mode without reopening a used sibling's outputs."""
    output = _unlinked(output)
    path = output / "inputs.json"
    if path.is_symlink() or path.stat().st_size > 2**20 or snapshot.digest(path) != expected_sha256:
        raise ValueError("Exact bounded paired input manifest required")
    value = json.loads(path.read_text())
    selected_inventory = profiles.selected_inventory(value)
    profile = value.get("configuration_profile", profiles.ORIGINAL)
    if (
        value["kind"] != kind_for_profile(profile)
        or value["held"] is not True
        or value["source_origin"] != str(NATIVE)
        or value["source_tree_sha256"] != BUNDLE_SHA256
        or value["source_inventory"] != _source()
        or value["parameter_metadata_sha256"] != PARAMETER_METADATA_SHA256
        or set(value["modes"]) != set(MODES)
        or mode is not None
        and mode not in MODES
    ):
        raise ValueError("Original paired inputs changed")
    parameter, inodes = _parameter_metadata(), set()
    for selected in MODES if mode is None else (mode,):
        row, config = value["modes"][selected], output / selected / "config"
        if row["config"] != str(config) or inventory(config) != selected_inventory:
            raise ValueError("Copied mode input tree changed")
        for name in value["source_inventory"]["files"]:
            info = (config / name).stat()
            identity = (info.st_dev, info.st_ino)
            if info.st_mode & 0o222 or info.st_nlink != 1 or identity in inodes:
                raise ValueError("Read-only independent input files required")
            inodes.add(identity)
        program = output / selected / "input-program.json"
        if row["program"]["path"] != str(program):
            raise ValueError("Input program path retargeted")
        checked = parameter.input_program(program, row["program"]["sha256"])
        if (
            checked["root"] != str(config)
            or checked["directories"] != row["initial_native_directories"]
            or checked.get("input_profile", profiles.ORIGINAL) != profile
        ):
            raise ValueError("Original output permission program changed")
        if _directory_state(checked["directories"]) != row["initial_directory_state"]:
            raise ValueError("Selected mode native output epoch changed from original data")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--profile", choices=profiles.PROFILES, default=profiles.ORIGINAL)
    args = parser.parse_args()
    if args.prepare is not None:
        prepare(args.prepare, profile=args.profile)
        print(
            json.dumps(
                dict(
                    path=str(args.prepare / "inputs.json"),
                    sha256=snapshot.digest(args.prepare / "inputs.json"),
                )
            )
        )
    elif args.verify is not None and args.sha256:
        verify(args.verify, args.sha256, mode=args.mode)
        print(json.dumps(dict(verified=True, mode=args.mode, native_execution=False)))
    else:
        parser.error("Prepare or verify original input data only")


if __name__ == "__main__":
    main()
