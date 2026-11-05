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
CAPACITY_RELEASE = "CELLS_SIM_RESULT_OBSERVATION_CAPACITY_SOFTWARE"
CAPACITY_SELECT = (
    "test_sim_observation_history_protocol_preserves_each_actual_row_and_two_full_sweeps[350]"
)
POLICY = dict(reused.POLICY)
snapshot, guard, runtime = reused.snapshot, reused.guard, reused.runtime
BASE, CLOSURE, Reports, blocked = reused.BASE, reused.CLOSURE, reused.Reports, reused.blocked


def _run_policy(select):
    if os.environ.get(CAPACITY_RELEASE) != "1":
        return dict(POLICY)
    if select != CAPACITY_SELECT:
        raise ValueError(
            "Separate capacity policy permits exactly the instrumented 350-row control"
        )
    return dict(POLICY, wall_seconds=3600)


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
    policy = _run_policy(select)
    capacity = os.environ.get(CAPACITY_RELEASE) == "1"
    snapshot.write_json(
        output / "inputs.json",
        dict(
            kind=(
                "cells.completed_SIM_observation_capacity_software@1"
                if capacity
                else "cells.completed_SIM_observation_blocked_software@1"
            ),
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            git_revision=manifest["git_revision"],
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            selection=select,
            policy=policy,
            separate_capacity_benchmark=capacity,
            ordinary_wall_seconds=POLICY["wall_seconds"],
            software_release_requested=os.environ.get(RELEASE) == "1",
            native_source_reference_owner_or_scientific_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def child(output, select):
    import pytest

    module = importlib.import_module("validation.betse.native_sim_result_observation")
    inputs = json.loads((output / "inputs.json").read_text())
    policy = _run_policy(select)
    capacity = os.environ.get(CAPACITY_RELEASE) == "1"
    if (
        inputs["software_release_requested"] is not True
        or inputs["policy"] != policy
        or inputs["separate_capacity_benchmark"] is not capacity
        or inputs["ordinary_wall_seconds"] != POLICY["wall_seconds"]
        or inputs["kind"]
        != (
            "cells.completed_SIM_observation_capacity_software@1"
            if capacity
            else "cells.completed_SIM_observation_blocked_software@1"
        )
    ):
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


def software(output, select, *, capacity=False):
    if capacity is not (os.environ.get(CAPACITY_RELEASE) == "1"):
        raise ValueError("Capacity software requires its separate explicit command and release")
    policy = _run_policy(select)
    namespace = dict(
        vars(reused.base),
        ROOT=ROOT,
        SOURCE=SOURCE,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        RELEASE=RELEASE,
        POLICY=policy,
        __file__=__file__,
    )
    return FunctionType(reused.base.software.__code__, namespace)(output, select)


def capacity_software(output, select):
    """Durable controller outcome, including pre-worker preparation failures."""
    try:
        code = software(output, select, capacity=True)
    except BaseException as error:
        if output.is_dir() and not output.is_symlink():
            snapshot.write_json(
                output / "capacity-controller-failure.json",
                dict(
                    status="failed",
                    type=type(error).__qualname__,
                    message=str(error),
                    policy=dict(POLICY, wall_seconds=3600),
                    automatic_retry=False,
                    native_source_reference_or_scientific_release=False,
                ),
            )
        raise
    snapshot.write_json(
        output / "capacity-terminal.json",
        dict(
            status="passed" if code == 0 else "failed",
            result=dict(
                path=str(output / "result.json"),
                sha256=snapshot.digest(output / "result.json"),
            ),
            policy=_run_policy(select),
            ordinary_wall_seconds=POLICY["wall_seconds"],
            instrumented_inert_rows=350,
            independent_inputs=1,
            ordinary_480s_control_credit=False,
            native_source_reference_or_scientific_release=False,
        ),
    )
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "capacity-software", "child"):
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
    if args.capacity_software:
        return capacity_software(args.capacity_software, args.select)
    parser.error("Select immutable metadata preparation or blocked software")


if __name__ == "__main__":
    raise SystemExit(main())
