"""Immutable CPU5 metadata controls for completed-SIM observations, no native work."""

import argparse
import importlib
import json
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import native_sim_reference_compare_software as reused

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_sim_result_observation.py"
TEST = "tests/unit/test_native_sim_result_observation.py"
FILE = "validation/betse/native_sim_result_observation_software.py"
MODULE = FILE[:-3].replace("/", ".")
OWNED = (
    SOURCE,
    TEST,
    FILE,
    "validation/betse/native_sim_reference_compare.py",
    "tests/unit/test_native_sim_reference_compare.py",
)
RELEASE = "CELLS_SIM_RESULT_OBSERVATION_BLOCKED_SOFTWARE"
POLICY = dict(reused.POLICY)
snapshot, guard, runtime = reused.snapshot, reused.guard, reused.runtime
BASE, CLOSURE, Reports, blocked = reused.BASE, reused.CLOSURE, reused.Reports, reused.blocked


def prepare(output, select):
    from validation.betse import native_sim_result_observation as module

    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical observation preparation required")
    starts = [
        *OWNED,
        *module.comparison.REF_PRODUCERS,
        module.KEY_FILE,
        module.HISTORY_FILE,
        "src/cells/processes/betse_native_sim_run_source.py",
        "validation/betse/native_seed_demo.py",
        "validation/betse/native_seed_world_callback_prelude.py",
        "validation/betse/native_seed_demo_launch.py",
    ]
    files = reused.base.runpy.run_path(str(ROOT / CLOSURE))["closure"](ROOT, starts)
    for name in (CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    snapshot.assert_checkout_unchanged(output / "source")
    snapshot.write_json(
        output / "inputs.json",
        dict(
            kind="cells.completed_SIM_observation_blocked_software@1",
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            git_revision=manifest["git_revision"],
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            selection=select,
            policy=POLICY,
            software_release_requested=os.environ.get(RELEASE) == "1",
            native_source_reference_owner_or_scientific_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def child(output, select):
    import pytest

    module = importlib.import_module("validation.betse.native_sim_result_observation")
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["software_release_requested"] is not True or inputs["policy"] != POLICY:
        raise ValueError("Explicit blocked observation software required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != inputs["owned_files"][name]:
            raise ValueError("Selected observation source drift")
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
        if any(
            name == "numpy" or name.startswith(("numpy.", "betse.", "cells.processes."))
            for name in inventory["loaded_files"]
        ):
            code = 1
        snapshot.write_json(output / "runtime.json", inventory)
        snapshot.write_json(
            output / "loaded-selected.json",
            {name: manifest["files"][name]["sha256"] for name in OWNED},
        )
    return int(code)


def software(output, select):
    namespace = dict(
        vars(reused.base),
        ROOT=ROOT,
        SOURCE=SOURCE,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        RELEASE=RELEASE,
        POLICY=POLICY,
        __file__=__file__,
    )
    return FunctionType(reused.base.software.__code__, namespace)(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="sim_observation")
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (2**30 if args.child else 512 * 2**20, 2**30))
    if args.child:
        return child(args.child, args.select)
    if args.prepare:
        prepare(args.prepare, args.select)
        return 0
    if args.software:
        return software(args.software, args.select)
    parser.error("Select immutable metadata preparation or blocked software")


if __name__ == "__main__":
    raise SystemExit(main())
