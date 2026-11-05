"""Immutable CPU5 stdlib-only saved-reference comparison controls."""

import argparse
import importlib
import json
import os
import resource
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType

from validation.betse import native_init_terminal_reference_software as base

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_sim_reference_compare.py"
TEST = "tests/unit/test_native_sim_reference_compare.py"
FILE = "validation/betse/native_sim_reference_compare_software.py"
MODULE = "validation.betse.native_sim_reference_compare_software"
OWNED = (SOURCE, TEST, FILE)
RELEASE = "CELLS_SIM_REFERENCE_COMPARE_BLOCKED_SOFTWARE"
POLICY = dict(base.POLICY)
snapshot, guard, runtime = base.snapshot, base.guard, base.runtime
BASE, CLOSURE, Reports = base.BASE, base.CLOSURE, base.Reports
NativeBlocked = base.NativeBlocked


def forbidden(frame):
    name = frame.f_globals.get("__name__", "")
    return base.forbidden(frame) or name == "numpy" or name.startswith("numpy.")


blocked = contextmanager(
    FunctionType(base.blocked.__wrapped__.__code__, dict(vars(base), forbidden=forbidden))
)


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
    # The forensic fixtures read these producer bytes; they never import or
    # execute them. Include that explicit read closure in the immutable image.
    module = importlib.import_module("validation.betse.native_sim_reference_compare")
    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical checkout comparison preparation required")
    starts = [
        *OWNED,
        *module.REF_PRODUCERS,
        "validation/betse/native_seed_demo.py",
        "validation/betse/native_seed_world_callback_prelude.py",
        "validation/betse/native_seed_demo_launch.py",
    ]
    files = base.runpy.run_path(str(ROOT / CLOSURE))["closure"](ROOT, starts)
    for name in (CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    snapshot.assert_checkout_unchanged(output / "source")
    snapshot.write_json(
        output / "inputs.json",
        dict(
            kind="cells.SIM_saved_comparison_blocked_software@1",
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            reference_evidence_producers=module.REF_PRODUCERS,
            git_revision=manifest["git_revision"],
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            selection=select,
            policy=POLICY,
            software_release_requested=os.environ.get(RELEASE) == "1",
            native_source_reference_owner_or_scientific_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def software(output, select):
    return FunctionType(base.software.__code__, _namespace())(output, select)


def child(output, select):
    import pytest

    module = importlib.import_module("validation.betse.native_sim_reference_compare")
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["software_release_requested"] is not True or inputs["policy"] != POLICY:
        raise ValueError("Explicit immutable CPU5 blocked comparison software required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != inputs["owned_files"][name]:
            raise ValueError("Selected comparison producer changed")
    snapshot.write_json(output / "source-plan.json", module.source_plan())
    os.environ[RELEASE] = "1"
    reports = Reports(output / "reports")
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
            plugins=[reports],
        )
    finally:
        inventory = runtime.inventory()
        loaded = inventory["loaded_files"]
        if any(
            name == "numpy" or name.startswith(("numpy.", "betse.", "cells.processes."))
            for name in loaded
        ):
            code = 1
        snapshot.write_json(output / "runtime.json", inventory)
        snapshot.write_json(
            output / "loaded-selected.json",
            {name: manifest["files"][name]["sha256"] for name in OWNED},
        )
    return int(code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="sim_compare")
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
    parser.error("Choose immutable preparation or blocked saved-comparison software")


if __name__ == "__main__":
    raise SystemExit(main())
