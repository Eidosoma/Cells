"""Immutable native-blocked controls for the actual callback prelude dispatcher."""

import argparse
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_seed_world_geometry_software as base

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_seed_world_callback_prelude.py"
LITERAL = SOURCE
TEST = "tests/unit/test_native_seed_world_callback_prelude.py"
FILE = "validation/betse/native_seed_world_callback_prelude_software.py"
MODULE = "validation.betse.native_seed_world_callback_prelude_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_WORLD_CALLBACK_PRELUDE_SOFTWARE_RELEASED"
OWNED = (
    SOURCE,
    TEST,
    FILE,
    "src/cells/processes/betse_native_tissue_configuration.py",
    "src/cells/processes/betse_native_simulator_construction.py",
    "src/cells/processes/betse_native_phase_callbacks.py",
)
FORBIDDEN_MODULES = base.FORBIDDEN_MODULES
NATIVE_ROOT = base.NATIVE_ROOT
snapshot = base.snapshot
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    if base.is_forbidden_frame(frame):
        return True
    return frame.f_globals.get("__name__") in (
        "cells.processes.betse_native_tissue_configuration",
        "cells.processes.betse_native_simulator_construction",
        "cells.processes.betse_native_phase_callbacks",
    ) and frame.f_code.co_name in ("prepare", "_native_setup", "_acquire_native")


def prepare(output, select):
    namespace = dict(
        vars(base.base.base),
        __file__=__file__,
        ROOT=ROOT,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        FORBIDDEN_MODULES=FORBIDDEN_MODULES,
    )
    return FunctionType(base.base.base.prepare.__code__, namespace)(output, select)


def child(output, select):
    namespace = dict(
        vars(base.reuse),
        ROOT=ROOT,
        SOURCE=SOURCE,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        FORBIDDEN_MODULES=FORBIDDEN_MODULES,
        is_forbidden_frame=is_forbidden_frame,
    )
    try:
        return FunctionType(base.reuse.child.__code__, namespace)(output, select)
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--child", type=Path)
    parser.add_argument("--select", default="")
    args = parser.parse_args()
    if not args.select:
        parser.error("Exact item-name selector required")
    output = args.child if args.child is not None else args.prepare
    try:
        if args.child is not None:
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(args.child, args.select)
        if args.prepare is not None:
            if os.environ.get(SOFTWARE_RELEASE) != "1":
                raise ValueError("Explicit isolated blocked-software release required")
            resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
            return prepare(args.prepare, args.select)
    except BaseException as primary:
        if output is not None:
            try:
                base.reuse.reuse._main_failure(output, primary)
            except BaseException as capture:
                global _RAW_FAILURES
                _RAW_FAILURES += ((primary, capture, output),)
        raise
    parser.error("Choose prepare or child")


if __name__ == "__main__":
    raise SystemExit(main())
