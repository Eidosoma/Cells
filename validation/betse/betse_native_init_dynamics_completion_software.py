"""Frozen CPU5 source/blocked controls; no completion/native/RNG run mode."""

import argparse
import importlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_init_dynamics_prelude_software as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_dynamics_completion.py"
LITERAL = "src/cells/processes/betse_native_init_dynamics_completion_source.py"
TEST = "tests/unit/test_betse_native_init_dynamics_completion.py"
FILE = "validation/betse/betse_native_init_dynamics_completion_software.py"
MODULE = "validation.betse.betse_native_init_dynamics_completion_software"
SOFTWARE_RELEASE = "CELLS_NATIVE_INIT_DYNAMICS_COMPLETION_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot, runtime, ref = previous.snapshot, previous.runtime, previous.ref


def is_forbidden_frame(frame):
    return (
        frame.f_globals.get("__name__")
        == "cells.processes.betse_native_init_dynamics_completion_source"
        or previous.is_forbidden_frame(frame)
    )


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
    fn = previous.previous.reused.prepare
    return FunctionType(fn.__code__, _scope(), argdefs=fn.__defaults__)(directory, select)


def software(directory, select=""):
    fn = previous.previous.reused.software
    return FunctionType(fn.__code__, _scope(), argdefs=fn.__defaults__)(directory, select)


def child(directory):
    if os.environ.get(SOFTWARE_RELEASE) != "1" or os.sched_getaffinity(0) != {5} or not __debug__:
        raise ValueError("Explicit frozen assertion-enabled CPU5 software child required")
    inputs = json.loads((directory / "inputs.json").read_text())
    if ROOT != directory / "source" or not inputs["software_release_requested"]:
        raise ValueError("Actual immutable execution snapshot required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    assert all(
        manifest["files"][name]["sha256"] == pin for name, pin in inputs["owned_files"].items()
    )
    initial = sys.getprofile(), sys.gettrace()
    stage = importlib.import_module("cells.processes.betse_native_init_dynamics_completion")
    if Path(stage.__file__).resolve() != ROOT / SOURCE or any(
        n == "betse" or n.startswith("betse.") for n in sys.modules
    ):
        raise ValueError("Canonical frozen source and no imported native module required")
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
    code = pytest.main(args)
    cases = list(ET.parse(directory / "junit.xml").iter("testcase"))
    guards = sorted((directory / "pytest").rglob("native-blocked.json"))
    rows = [json.loads(p.read_text()) for p in guards]
    ids = {TEST + "::" + c.get("name") for c in cases}
    intact = sys.getprofile() is initial[0] and sys.gettrace() is initial[1]
    clean = (
        len(cases) == len(rows) == len(ids)
        and {r["nodeid"] for r in rows} == ids
        and all(
            not r["attempts"]
            and all(
                r[k]
                for k in ("hooks_intact", "active_restored", "profile_restored", "trace_restored")
            )
            for r in rows
        )
    )
    snapshot.write_json(directory / "runtime.json", runtime.inventory())
    value = dict(
        status="completed" if code == 0 and clean and intact else "failed",
        cases=len(cases),
        pytest_status=int(code),
        complete_guards=clean,
        original_hooks_restored=intact,
        guards=[ref(p) for p in guards],
        source_pins=inputs["owned_files"],
        runtime=ref(directory / "runtime.json"),
        source_plan=ref(directory / "source-plan.json"),
        actual_native_source_helpers_RNG_or_reference_entries=0,
        domain_declarations_or_records_are_not_actual_parent_authority=True,
        bootstrap_scope="Definition/runtime imports precede each case blockade",
    )
    snapshot.write_json(
        directory / ("result.json" if value["status"] == "completed" else "failure.json"), value
    )
    if value["status"] != "completed":
        raise ValueError("Blocked controls failed; source/evidence preserved")
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
