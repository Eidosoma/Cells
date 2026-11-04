"""Frozen CPU5 source/metadata controls; native molecule construction is held."""

import argparse
import importlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_init_dynamics_completion_software as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_molecule_network.py"
LITERAL = "src/cells/processes/betse_native_init_molecule_network_source.py"
TEST = "tests/unit/test_betse_native_init_molecule_network.py"
FILE = "validation/betse/betse_native_init_molecule_network_software.py"
MODULE = "validation.betse.betse_native_init_molecule_network_software"
SOFTWARE_RELEASE = "CELLS_NATIVE_INIT_MOLECULE_NETWORK_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot, runtime, ref = previous.snapshot, previous.runtime, previous.ref


def is_forbidden_frame(frame):
    # This family's source module only parses/compiles pinned syntax. Original
    # compiled bodies retain native filenames and remain blocked by the same
    # inherited predicate; metadata compilation is never source execution.
    return previous.is_forbidden_frame(frame)


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
    fn = previous.previous.previous.reused.prepare
    return FunctionType(fn.__code__, _scope(), argdefs=fn.__defaults__)(directory, select)


def child(directory):
    if os.environ.get(SOFTWARE_RELEASE) != "1" or os.sched_getaffinity(0) != {5} or not __debug__:
        raise ValueError("Explicit assertion-enabled CPU5 blocked metadata child required")
    inputs = json.loads((directory / "inputs.json").read_text())
    if ROOT != directory / "source" or not inputs["software_release_requested"]:
        raise ValueError("Actual frozen metadata source required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    if any(manifest["files"][name]["sha256"] != pin for name, pin in inputs["owned_files"].items()):
        raise ValueError("Exact frozen molecule source/test binding changed")
    before = sys.getprofile(), sys.gettrace()
    stage = importlib.import_module("cells.processes.betse_native_init_molecule_network")
    if Path(stage.__file__).resolve() != ROOT / SOURCE or any(
        name == "betse" or name.startswith("betse.") for name in sys.modules
    ):
        raise ValueError("Actual frozen definitions without native import required")
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
    paths = sorted((directory / "pytest").rglob("native-blocked.json"))
    guards = [json.loads(path.read_text()) for path in paths]
    ids = {TEST + "::" + case.get("name") for case in cases}
    restored = sys.getprofile() is before[0] and sys.gettrace() is before[1]
    complete = (
        len(cases) == len(ids) == len(guards)
        and {row["nodeid"] for row in guards} == ids
        and all(
            not row["attempts"]
            and all(
                row[key]
                for key in ("hooks_intact", "active_restored", "profile_restored", "trace_restored")
            )
            for row in guards
        )
    )
    snapshot.write_json(directory / "runtime.json", runtime.inventory())
    result = dict(
        status="completed" if code == 0 and complete and restored else "failed",
        cases=len(cases),
        pytest_status=int(code),
        complete_guards=complete,
        hooks_restored=restored,
        guards=[ref(path) for path in paths],
        source_pins=inputs["owned_files"],
        runtime=ref(directory / "runtime.json"),
        source_plan=ref(directory / "source-plan.json"),
        actual_native_constructor_source_RNG_or_reference_entries=0,
        declarations_and_metadata_are_not_genuine_parent_authority=True,
    )
    snapshot.write_json(
        directory / ("result.json" if result["status"] == "completed" else "failure.json"), result
    )
    if result["status"] != "completed":
        raise ValueError("Blocked molecule metadata controls failed; all source/evidence retained")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--child", type=Path)
    parser.add_argument("--select", default="")
    args = parser.parse_args()
    return prepare(args.prepare, args.select) if args.prepare else child(args.child)


if __name__ == "__main__":
    main()
