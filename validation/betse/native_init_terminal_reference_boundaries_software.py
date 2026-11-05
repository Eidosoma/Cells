"""Immutable CPU5 native-blocked controls for independent observation boundaries."""

import argparse
import importlib
import json
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import native_init_terminal_reference_software as base

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_init_terminal_reference.py"
TEST = "tests/unit/test_native_init_terminal_reference_boundaries.py"
FILE = "validation/betse/native_init_terminal_reference_boundaries_software.py"
MODULE = "validation.betse.native_init_terminal_reference_boundaries_software"
OWNED = (SOURCE, TEST, FILE)
RELEASE = "CELLS_INIT_REFERENCE_BOUNDARIES_BLOCKED_SOFTWARE"
POLICY = dict(base.POLICY)
snapshot, guard, runtime = base.snapshot, base.guard, base.runtime
blocked, NativeBlocked, Reports = base.blocked, base.NativeBlocked, base.Reports


def _namespace():
    return dict(
        vars(base),
        **{
            name: globals()[name]
            for name in (
                "ROOT",
                "SOURCE",
                "TEST",
                "FILE",
                "MODULE",
                "OWNED",
                "RELEASE",
                "POLICY",
            )
        },
        __file__=__file__,
    )


def prepare(output, select):
    return FunctionType(base.prepare.__code__, _namespace())(output, select)


def software(output, select):
    return FunctionType(base.software.__code__, _namespace())(output, select)


def child(output, select):
    import numpy  # noqa: F401
    import pytest

    from validation.betse import betse_initial_mesh_preparation_wire  # noqa: F401

    module = importlib.import_module("validation.betse.native_init_terminal_reference")
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["software_release_requested"] is not True or inputs["policy"] != POLICY:
        raise ValueError("Explicit native-blocked immutable SIM reference software required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != inputs["owned_files"][name]:
            raise ValueError("Exact selected SIM reference producer changed")
    snapshot.write_json(output / "source-plan.json", module.source_plan())
    os.environ[RELEASE] = "1"
    code = 1
    try:
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
            plugins=[Reports(output / "reports")],
        )
    finally:
        snapshot.write_json(output / "runtime.json", runtime.inventory())
        snapshot.write_json(
            output / "loaded-selected.json",
            {name: manifest["files"][name]["sha256"] for name in OWNED},
        )
    return int(code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="reference_boundary")
    args = parser.parse_args()
    if args.child:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        return child(args.child, args.select)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    if args.prepare:
        prepare(args.prepare, args.select)
        return 0
    if args.software:
        return software(args.software, args.select)
    parser.error("Choose immutable preparation or blocked software")


if __name__ == "__main__":
    raise SystemExit(main())
