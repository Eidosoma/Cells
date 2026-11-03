"""Frozen CPU5 blocked controls for the fresh INIT/SIM parameter contract.

Reuse the reviewed profile runner's unchanged preparation/resource envelope.
This entry has no actual phase/native/source execution mode.
"""

import argparse
import importlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_seed_init_profiles_software as reused

ROOT = Path(__file__).resolve().parents[2]
BASE = reused.BASE
SOURCE = "src/cells/processes/betse_native_parameter_phase_construction.py"
LITERAL = "src/cells/processes/betse_native_parameter_phase_construction_source.py"
TEST = "tests/unit/test_betse_native_parameter_phase_construction.py"
FILE = "validation/betse/betse_native_parameter_phase_construction_software.py"
MODULE = "validation.betse.betse_native_parameter_phase_construction_software"
SOFTWARE_RELEASE = "CELLS_NATIVE_PARAMETER_PHASE_CONSTRUCTION_SOFTWARE_RELEASED"
SOFTWARE_CPU = 5
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot, runtime = reused.snapshot, reused.runtime
ref = reused.ref


def is_forbidden_frame(frame):
    module = frame.f_globals.get("__name__", "")
    return (
        module == "cells.processes.betse_native_parameter_phase_construction_source"
        or (module.startswith("ruamel.yaml") and frame.f_code.co_name != "<module>")
        or reused.is_forbidden_frame(frame)
    )


def _scope():
    return dict(
        vars(reused),
        ROOT=ROOT,
        BASE=BASE,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        SOFTWARE_CPU=SOFTWARE_CPU,
        OWNED=OWNED,
        __file__=__file__,
    )


def prepare(directory, select=""):
    return FunctionType(reused.prepare.__code__, _scope(), argdefs=reused.prepare.__defaults__)(
        directory, select
    )


def software(directory, select=""):
    return FunctionType(reused.software.__code__, _scope(), argdefs=reused.software.__defaults__)(
        directory, select
    )


def child(directory):
    if os.environ.get(SOFTWARE_RELEASE) != "1" or os.sched_getaffinity(0) != {5} or not __debug__:
        raise ValueError("Actual released CPU5 frozen software child required")
    inputs = json.loads((directory / "inputs.json").read_text())
    if ROOT != directory / "source" or not inputs["software_release_requested"]:
        raise ValueError("Actual prepared immutable source required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name, pin in inputs["owned_files"].items():
        if manifest["files"][name]["sha256"] != pin:
            raise ValueError("Exact prepared producer required")
    initial = (sys.getprofile(), sys.gettrace())
    stage = importlib.import_module("cells.processes.betse_native_parameter_phase_construction")
    if Path(stage.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Canonical frozen parameter producer required")
    if any(name == "betse" or name.startswith("betse.") for name in sys.modules):
        raise ValueError("Native module imported before blockade")
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
    nodeids = {TEST + "::" + case.get("name") for case in cases}
    clean = (
        len(cases) == len(records) == len(nodeids)
        and all(
            not row["attempts"]
            and row["profile_restored"]
            and row["trace_restored"]
            and row["active_restored"]
            and row["hooks_intact"]
            for row in records
        )
        and {row["nodeid"] for row in records} == nodeids
    )
    snapshot.write_json(directory / "runtime.json", runtime.inventory())
    intact = sys.getprofile() is initial[0] and sys.gettrace() is initial[1]
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
        optimize=sys.flags.optimize,
        original_hooks_restored=intact,
        actual_native_source_parser_factory_RNG_or_time_law_entries=0,
        synthetic_models_issue_no_native_phase_or_completed_INIT_owner=True,
        bootstrap_scope=(
            "Shared definition/runtime imports precede per-case source/native/RNG guards"
        ),
    )
    snapshot.write_json(
        directory / ("result.json" if value["status"] == "completed" else "failure.json"), value
    )
    if value["status"] != "completed":
        raise ValueError("Blocked software failed; immutable evidence retained")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--software", type=Path)
    mode.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--select", default="")
    args = parser.parse_args()
    if args.prepare:
        return prepare(args.prepare, args.select)
    if args.software:
        return software(args.software, args.select)
    return child(args.child)


if __name__ == "__main__":
    main()
