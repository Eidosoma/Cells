"""Immutable CPU5 native-blocked synthetic saved-comparison controls."""

import argparse
import importlib
import json
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import native_seed_demo_report_software as reused

ROOT = Path(__file__).resolve().parents[2]
SOURCE = LITERAL = "validation/betse/native_seed_demo_compare.py"
TEST = "tests/unit/test_native_seed_demo_compare.py"
FILE = "validation/betse/native_seed_demo_compare_software.py"
MODULE = "validation.betse.native_seed_demo_compare_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_DEMO_COMPARE_SOFTWARE_RELEASED"
OWNED = (SOURCE, TEST, FILE)
DEPENDENCIES = (
    "validation/betse/native_seed_demo_report.py",
    "validation/betse/native_seed_demo_evidence.py",
    "validation/betse/native_single_cell_prefix_payload.py",
    "tests/unit/test_native_seed_demo_report.py",
)
base, snapshot = reused.base, reused.snapshot
NATIVE_ROOT, FORBIDDEN_MODULES = reused.NATIVE_ROOT, reused.FORBIDDEN_MODULES
Reports, is_forbidden_frame = reused.Reports, reused.is_forbidden_frame
_RAW_FAILURES = ()


def _namespace():
    return dict(
        reused._namespace(),
        ROOT=ROOT,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        FORBIDDEN_MODULES=FORBIDDEN_MODULES,
        is_forbidden_frame=is_forbidden_frame,
        __file__=__file__,
    )


def prepare(output, select):
    if os.sched_getaffinity(0) != {5} or os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Explicit CPU5 blocked synthetic comparison controls required")
    FunctionType(reused.base.base.prepare.__code__, _namespace())(output, select)
    inputs = json.loads((output / "inputs.json").read_text())
    snapshot.write_json(output / "default-lane-inputs.json", inputs)
    inputs.update(
        cpu=5,
        comparison_dependencies={
            name: snapshot.digest(output / "source" / name) for name in DEPENDENCIES
        },
        saved_comparison_metadata_only=True,
    )
    pending = output / "cpu5-inputs.json.pending"
    snapshot.write_json(pending, inputs)
    os.replace(pending, output / "inputs.json")


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    if (
        os.sched_getaffinity(0) != {5}
        or inputs.get("cpu") != 5
        or inputs.get("selection") != select
        or inputs.get("threads") != 1
        or inputs.get("software_release_requested") is not True
        or inputs.get("saved_comparison_metadata_only") is not True
        or inputs.get("software_bytes") != 2**30
        or inputs.get("wall_seconds") != 480
        or inputs.get("reserve_bytes") != 8 * 2**30
    ):
        raise ValueError("Exact frozen CPU5 software envelope required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for key, names in (("owned_files", OWNED), ("comparison_dependencies", DEPENDENCIES)):
        if set(inputs.get(key, ())) != set(names):
            raise ValueError("Exact selected saved-comparison producer roster required")
        for name in names:
            if (
                inputs[key][name] != manifest["files"][name]["sha256"]
                or snapshot.digest(ROOT / name) != inputs[key][name]
            ):
                raise ValueError("Frozen saved-comparison producer changed")
    module = importlib.import_module("validation.betse.native_seed_demo_compare")
    if Path(module.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Actual frozen comparison source required")
    snapshot.write_json(output / "source-plan.json", module.source_plan())
    namespace = dict(
        vars(reused.reuse),
        **{
            key: globals()[key]
            for key in (
                "ROOT",
                "SOURCE",
                "TEST",
                "FILE",
                "MODULE",
                "OWNED",
                "SOFTWARE_RELEASE",
                "FORBIDDEN_MODULES",
                "is_forbidden_frame",
            )
        },
    )
    try:
        return FunctionType(reused.reuse.child.__code__, namespace)(output, select)
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--child", type=Path)
    parser.add_argument("--select", default="test_compare_")
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, ((2**30 if args.child else 512 * 2**20), 2**30))
    return child(args.child, args.select) if args.child else prepare(args.prepare, args.select)


if __name__ == "__main__":
    raise SystemExit(main())
