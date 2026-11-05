"""CPU2 immutable-source native-blocked terminal-molecular metadata controls."""

import argparse
import importlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_init_molecule_short_runtime_software as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_terminal_molecules.py"
TEST = "tests/unit/test_betse_native_init_terminal_molecules.py"
FILE = "validation/betse/betse_native_init_terminal_molecules_software.py"
MODULE = "validation.betse.betse_native_init_terminal_molecules_software"
LITERAL = previous.LITERAL
OWNED = SOURCE, LITERAL, TEST, FILE
SOFTWARE_RELEASE = "CELLS_NATIVE_INIT_TERMINAL_MOLECULES_SOFTWARE_RELEASED"
snapshot, runtime, ref = previous.snapshot, previous.runtime, previous.ref
is_forbidden_frame = previous.is_forbidden_frame


def _scope():
    return dict(
        previous._scope(),
        ROOT=ROOT,
        SOURCE=SOURCE,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        SOFTWARE_CPU=2,
        __file__=__file__,
    )


def prepare(directory, select=""):
    namespace = dict(vars(previous.previous), **_scope(), _scope=_scope)
    return FunctionType(previous.previous.prepare.__code__, namespace)(directory, select)


def child(directory):
    if os.environ.get(SOFTWARE_RELEASE) != "1" or os.sched_getaffinity(0) != {2} or not __debug__:
        raise ValueError("Explicit assertion-enabled CPU2 blocked-software release required")
    inputs = json.loads((directory / "inputs.json").read_text())
    if ROOT != directory / "source" or not inputs["software_release_requested"]:
        raise ValueError("Actual immutable execution snapshot required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    if any(manifest["files"][name]["sha256"] != pin for name, pin in inputs["owned_files"].items()):
        raise ValueError("Exact terminal source/test bindings changed")
    before = sys.getprofile(), sys.gettrace()
    stage = importlib.import_module("cells.processes.betse_native_init_terminal_molecules")
    if Path(stage.__file__).resolve() != ROOT / SOURCE or any(
        n == "betse" or n.startswith("betse.") for n in sys.modules
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
    guards = sorted((directory / "pytest").rglob("native-blocked.json"))
    rows = [json.loads(path.read_text()) for path in guards]
    ids = {TEST + "::" + case.get("name") for case in cases}
    clean = (
        len(cases) == len(rows) == len(ids)
        and {row["nodeid"] for row in rows} == ids
        and all(
            not row["attempts"]
            and all(
                row[key]
                for key in ("hooks_intact", "active_restored", "profile_restored", "trace_restored")
            )
            for row in rows
        )
    )
    restored = sys.getprofile() is before[0] and sys.gettrace() is before[1]
    snapshot.write_json(directory / "runtime.json", runtime.inventory())
    result = dict(
        status="completed" if code == 0 and clean and restored else "failed",
        cases=len(cases),
        pytest_status=int(code),
        complete_guards=clean,
        hooks_restored=restored,
        guards=[ref(path) for path in guards],
        source_pins=inputs["owned_files"],
        runtime=ref(directory / "runtime.json"),
        source_plan=ref(directory / "source-plan.json"),
        actual_native_factory_owner_RNG_reference_or_numerical_entries=0,
        metadata_ledger_or_record_is_not_genuine_INIT_authority=True,
    )
    snapshot.write_json(
        directory / ("result.json" if result["status"] == "completed" else "failure.json"), result
    )
    if result["status"] != "completed":
        raise ValueError("Blocked terminal controls failed; all evidence retained")
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
