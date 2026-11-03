"""Immutable CPU4 metadata controls for original-data pair preparation."""

import argparse
import importlib
import json
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import native_seed_demo_software as base

ROOT = Path(__file__).resolve().parents[2]
SOURCE = LITERAL = "validation/betse/native_seed_demo_inputs.py"
TEST = "tests/unit/test_native_seed_demo_inputs.py"
FILE = "validation/betse/native_seed_demo_inputs_software.py"
MODULE = "validation.betse.native_seed_demo_inputs_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_DEMO_INPUTS_SOFTWARE_RELEASED"
OWNED = (SOURCE, TEST, FILE)
FORBIDDEN_MODULES = base.FORBIDDEN_MODULES
NATIVE_ROOT, Reports, reuse = base.NATIVE_ROOT, base.Reports, base.reuse
snapshot = base.snapshot
is_forbidden_frame = base.is_forbidden_frame
_RAW_FAILURES = ()


def _namespace():
    return dict(
        vars(base.base),
        **{
            key: globals()[key]
            for key in (
                "ROOT",
                "SOURCE",
                "LITERAL",
                "TEST",
                "FILE",
                "MODULE",
                "SOFTWARE_RELEASE",
                "OWNED",
                "FORBIDDEN_MODULES",
                "is_forbidden_frame",
            )
        },
        __file__=__file__,
    )


def prepare(output, select):
    return FunctionType(base.base.prepare.__code__, _namespace())(output, select)


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True:
        raise ValueError("Explicit metadata-only software release required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    module = importlib.import_module("validation.betse.native_seed_demo_inputs")
    actual = snapshot.digest(ROOT / SOURCE)
    if (
        Path(module.__file__).resolve() != ROOT / SOURCE
        or actual != inputs["owned_files"][SOURCE]
        or actual != manifest["files"][SOURCE]["sha256"]
    ):
        raise ValueError("Actual immutable metadata producer required")
    snapshot.write_json(
        output / "source-plan.json",
        dict(
            source_plan=module.source_plan(), source=SOURCE, sha256=actual, native_execution=False
        ),
    )
    namespace = dict(
        vars(reuse),
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
        return FunctionType(reuse.child.__code__, namespace)(output, select)
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())


def software(output, select):
    return FunctionType(base.base.software.__code__, _namespace())(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="inputs")
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
    parser.error("Choose prepare, software or child")


if __name__ == "__main__":
    raise SystemExit(main())
