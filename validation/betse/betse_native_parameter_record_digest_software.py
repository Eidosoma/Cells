"""Reuse frozen resource/guard accounting for the metadata digest only."""

import argparse
import importlib
import json
import os
import resource
import sys
from contextlib import contextmanager
from pathlib import Path
from types import CodeType, FunctionType
from typing import TYPE_CHECKING

from validation.betse import native_init_terminal_reference_software as base

if TYPE_CHECKING:
    from cells.processes import betse_native_parameter_yaml_prefix as _yaml_metadata  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_parameter_record_digest.py"
TEST = "tests/unit/test_betse_native_parameter_record_digest.py"
FILE = "validation/betse/betse_native_parameter_record_digest_software.py"
MODULE = "validation.betse.betse_native_parameter_record_digest_software"
PREFIX = "src/cells/processes/betse_native_parameter_yaml_prefix.py"
ORIGINAL = "src/cells/processes/betse_normal_current.py"
OWNED = (SOURCE, TEST, FILE)
RELEASE = "CELLS_PARAMETER_RECORD_DIGEST_BLOCKED_SOFTWARE"
POLICY = dict(base.POLICY, cpu=4)
snapshot, guard, runtime = base.snapshot, base.guard, base.runtime
BASE, CLOSURE, Reports = base.BASE, base.CLOSURE, base.Reports
_RECORD_CODES = frozenset()
_CAPTURE_FAILURES = []


def forbidden(frame):
    module, filename = frame.f_globals.get("__name__", ""), frame.f_code.co_filename
    if filename.startswith(base.NATIVE_ROOT + os.sep):
        return True
    if module == "cells.processes.betse_native_parameter_record_digest":
        return False
    if module == "cells.processes.betse_normal_current":
        return frame.f_code not in _RECORD_CODES
    return base.forbidden(frame)


@contextmanager
def blocked(folder):
    global _RECORD_CODES
    module = sys.modules["cells.processes.betse_native_parameter_record_digest"]
    pending, codes = [module._RECORD.__code__, module._DIGEST.__code__], set()
    while pending:
        code = pending.pop()
        codes.add(code)
        pending.extend(item for item in code.co_consts if type(item) is CodeType)
    _RECORD_CODES = frozenset(codes)
    delegate = contextmanager(
        FunctionType(base.blocked.__wrapped__.__code__, dict(vars(base), forbidden=forbidden))
    )
    with delegate(folder):
        yield


def _namespace():
    return dict(
        vars(base),
        **{
            name: globals()[name]
            for name in ("ROOT", "SOURCE", "TEST", "FILE", "MODULE", "OWNED", "RELEASE", "POLICY")
        },
        __file__=__file__,
    )


def prepare(output, select):
    FunctionType(base.prepare.__code__, _namespace())(output, select)
    inputs = json.loads((output / "inputs.json").read_text())
    manifest = snapshot.verify(output / "source", manifest_sha256=inputs["snapshot_sha256"])
    for path in (PREFIX, ORIGINAL):
        if path not in manifest["files"]:
            raise ValueError("Read-only original serializer/YAML metadata absent from snapshot")


def software(output, select):
    return FunctionType(base.software.__code__, _namespace())(output, select)


def child(output, select):
    import pytest

    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["software_release_requested"] is not True or inputs["policy"] != POLICY:
        raise ValueError("Explicit immutable CPU4 metadata digest software required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != inputs["owned_files"][name]:
            raise ValueError("Selected metadata digest producer changed")
    code, primary, failures = 1, None, []
    try:
        module = importlib.import_module("cells.processes.betse_native_parameter_record_digest")
        if Path(module.__file__).resolve() != ROOT / SOURCE:
            raise ValueError("Actual frozen metadata digest required")
        snapshot.write_json(
            output / "source-plan.json",
            dict(
                original_serializer_sha256=module.ORIGINAL_SHA256,
                fresh_hash_every_call=True,
                recursive_original_fallback=True,
                input_or_digest_cache=False,
                optimized_limits=module._LIMITS,
                metadata_read_files={
                    name: manifest["files"][name]["sha256"] for name in (PREFIX, ORIGINAL)
                },
                actual_native_source_or_owner_execution=False,
            ),
        )
        os.environ[RELEASE] = "1"
        reports = Reports(output / "reports")
        code = pytest.main(
            [
                "--noconftest",
                "-q",
                "-x",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                "--basetemp=" + str(output / "pytest"),
                "--junitxml=" + str(output / "tests.xml"),
                str(ROOT / TEST),
                "-k",
                select,
            ],
            plugins=[reports],
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            snapshot.write_json(output / "runtime.json", runtime.inventory())
        except BaseException as error:
            failures.append(error)
        try:
            snapshot.write_json(
                output / "loaded-selected.json",
                {name: manifest["files"][name]["sha256"] for name in OWNED},
            )
        except BaseException as error:
            failures.append(error)
        if failures:
            _CAPTURE_FAILURES.append((primary, failures))
            if primary is None:
                raise failures[0]
    return int(code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="record_digest")
    args = parser.parse_args()
    if args.child is not None:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        return child(args.child, args.select)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    if args.prepare is not None:
        prepare(args.prepare, args.select)
        return 0
    if args.software is not None:
        return software(args.software, args.select)
    parser.error("Choose prepare, software or child")


if __name__ == "__main__":
    raise SystemExit(main())
