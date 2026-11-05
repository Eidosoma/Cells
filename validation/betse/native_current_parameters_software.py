"""Frozen blocked controls for the explicit second fresh Parameters load."""

import argparse
import importlib
import json
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import native_init_terminal_reference_software as base

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/betse_native_parameter_world_ready_qualification.py"
TEST = "tests/unit/test_native_current_parameters.py"
FILE = "validation/betse/native_current_parameters_software.py"
MODULE = "validation.betse.native_current_parameters_software"
OWNED = (SOURCE, TEST, FILE)
RELEASE = "CELLS_CURRENT_PARAMETERS_BLOCKED_SOFTWARE"
POLICY = dict(base.POLICY, cpu=4)
snapshot, guard, runtime = base.snapshot, base.guard, base.runtime
BASE, CLOSURE, Reports = base.BASE, base.CLOSURE, base.Reports


def forbidden(frame):
    return base.forbidden(frame) or (
        frame.f_globals.get("__name__")
        == "validation.betse.betse_native_parameter_world_ready_qualification"
        and frame.f_code.co_name == "_execute"
    )


def blocked(folder):
    from contextlib import contextmanager

    return contextmanager(
        FunctionType(base.blocked.__wrapped__.__code__, dict(vars(base), forbidden=forbidden))
    )(folder)


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
    return FunctionType(base.prepare.__code__, _namespace())(output, select)


def software(output, select):
    return FunctionType(base.software.__code__, _namespace())(output, select)


def child(output, select):
    import pytest

    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["software_release_requested"] is not True or inputs["policy"] != POLICY:
        raise ValueError("Explicit immutable CPU4 metadata software required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != inputs["owned_files"][name]:
            raise ValueError("Selected current-parameter producer changed")
    module = importlib.import_module(
        "validation.betse.betse_native_parameter_world_ready_qualification"
    )
    if Path(module.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Actual frozen qualifier required")
    snapshot.write_json(
        output / "source-plan.json",
        dict(
            current_sequence=module.CURRENT_LOADS,
            default_sequence=module.ONE_LOAD,
            actual_pipeline_source_imports_or_owners_executed=False,
            metadata_pair_tokens_are_not_native_owners=True,
            real_issued_chain_still_requires_separate_release=True,
        ),
    )
    os.environ[RELEASE] = "1"
    reports = Reports(output / "reports")
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
            plugins=[reports],
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
    for name in ("prepare", "child", "software"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="current_parameters")
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
    parser.error("Choose immutable preparation or blocked software")


if __name__ == "__main__":
    raise SystemExit(main())
