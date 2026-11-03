"""Frozen CPU5 blocked controls; original dynamics/helpers remain held."""

import argparse
import importlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_parameter_phase_construction_software as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_dynamics_prelude.py"
LITERAL = "src/cells/processes/betse_native_init_dynamics_prelude_source.py"
TEST = "tests/unit/test_betse_native_init_dynamics_prelude.py"
FILE = "validation/betse/betse_native_init_dynamics_prelude_software.py"
MODULE = "validation.betse.betse_native_init_dynamics_prelude_software"
SOFTWARE_RELEASE = "CELLS_NATIVE_INIT_DYNAMICS_PRELUDE_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot, runtime, ref = previous.snapshot, previous.runtime, previous.ref


def is_forbidden_frame(frame):
    return frame.f_globals.get("__name__") in (
        "cells.processes.betse_native_init_dynamics_prelude_source",
        "cells.processes.betse_native_init_retained_world_source",
    ) or previous.is_forbidden_frame(frame)


def _scope():
    return dict(
        previous._scope(),
        ROOT=ROOT,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        SOFTWARE_CPU=5,
        OWNED=OWNED,
        __file__=__file__,
    )


def prepare(directory, select=""):
    function = previous.reused.prepare
    return FunctionType(function.__code__, _scope(), argdefs=function.__defaults__)(
        directory, select
    )


def software(directory, select=""):
    function = previous.reused.software
    return FunctionType(function.__code__, _scope(), argdefs=function.__defaults__)(
        directory, select
    )


def child(directory):
    if os.environ.get(SOFTWARE_RELEASE) != "1" or os.sched_getaffinity(0) != {5} or not __debug__:
        raise ValueError("Actual assertion-enabled CPU5 software child required")
    inputs = json.loads((directory / "inputs.json").read_text())
    if ROOT != directory / "source" or not inputs["software_release_requested"]:
        raise ValueError("Actual immutable prepared source required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name, pin in inputs["owned_files"].items():
        if manifest["files"][name]["sha256"] != pin:
            raise ValueError("Selected producer changed")
    initial = sys.getprofile(), sys.gettrace()
    stage = importlib.import_module("cells.processes.betse_native_init_dynamics_prelude")
    if Path(stage.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Canonical frozen dynamics-prelude producer required")
    if any(name == "betse" or name.startswith("betse.") for name in sys.modules):
        raise ValueError("Native module imported before software blockade")
    snapshot.write_json(directory / "source-plan.json", stage.source_plan())
    import pytest

    args = [
        "-q",
        "-x",
        "-p",
        "no:cacheprovider",
        str(ROOT / TEST),
        "--basetemp",
        str(directory / "pytest"),
        "--junitxml",
        str(directory / "junit.xml"),
    ]
    if inputs["select"]:
        args.extend(("-k", inputs["select"]))
    status = pytest.main(args)
    cases = list(ET.parse(directory / "junit.xml").iter("testcase"))
    guards = sorted((directory / "pytest").rglob("native-blocked.json"))
    records = [json.loads(path.read_text()) for path in guards]
    nodes = {TEST + "::" + case.get("name") for case in cases}
    intact = sys.getprofile() is initial[0] and sys.gettrace() is initial[1]
    clean = (
        len(cases) == len(records) == len(nodes)
        and {row["nodeid"] for row in records} == nodes
        and all(
            not row["attempts"]
            and row["active_restored"]
            and row["hooks_intact"]
            and row["profile_restored"]
            and row["trace_restored"]
            for row in records
        )
    )
    snapshot.write_json(directory / "runtime.json", runtime.inventory())
    value = dict(
        status="completed" if status == 0 and clean and intact else "failed",
        pytest_status=int(status),
        cases=len(cases),
        complete_guards=clean,
        guards=[ref(path) for path in guards],
        source_plan=ref(directory / "source-plan.json"),
        runtime=ref(directory / "runtime.json"),
        source_pins=inputs["owned_files"],
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        pid=os.getpid(),
        original_hooks_restored=intact,
        actual_native_gap_gaussian_source_material_or_RNG_entries=0,
        conditional_metadata_models_are_not_actual_InitOwner_authority=True,
        bootstrap_scope="Definition/runtime bootstrap precedes per-case native/model/RNG guards",
    )
    snapshot.write_json(
        directory / ("result.json" if value["status"] == "completed" else "failure.json"), value
    )
    if value["status"] != "completed":
        raise ValueError("Native-blocked controls failed; immutable evidence retained")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--software", type=Path)
    modes.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--select", default="")
    args = parser.parse_args()
    if args.prepare:
        return prepare(args.prepare, args.select)
    if args.software:
        return software(args.software, args.select)
    return child(args.child)


if __name__ == "__main__":
    main()
