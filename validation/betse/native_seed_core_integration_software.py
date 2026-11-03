"""Immutable native-blocked controls for genuine world/Poisson/core integration."""

import argparse
import importlib
import json
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_seed_world_geometry_software as base

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_seed_init_core.py"
LITERAL = "src/cells/processes/betse_native_seed_init_core_source.py"
TEST = "tests/unit/test_native_seed_core_integration.py"
FILE = "validation/betse/native_seed_core_integration_software.py"
MODULE = "validation.betse.native_seed_core_integration_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_CORE_INTEGRATION_SOFTWARE_RELEASED"
OWNED = (
    "src/cells/processes/betse_native_world_phase_construction.py",
    "src/cells/processes/betse_native_seed_world_geometry.py",
    "src/cells/processes/betse_native_seed_world_poisson.py",
    SOURCE,
    "src/cells/processes/betse_native_phase_assembly.py",
    "src/cells/processes/betse_native_seed_world_prefix.py",
    "src/cells/processes/betse_native_seed_voronoi_mesh.py",
    TEST,
    FILE,
)
FORBIDDEN_MODULES = (
    base.FORBIDDEN_MODULES - {"cells.processes.betse_native_phase_assembly"}
) | frozenset(
    (
        "cells.processes.betse_native_seed_init_core_source",
        "cells.processes.betse_native_single_cell_poisson_source",
        "cells.processes.betse_native_make_world_tail_source",
    )
)
NATIVE_ROOT, snapshot = base.NATIVE_ROOT, base.snapshot
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    if frame.f_globals.get("__name__") in FORBIDDEN_MODULES:
        return True
    path = os.path.normpath(frame.f_code.co_filename)
    return os.path.isabs(path) and (path == NATIVE_ROOT or path.startswith(NATIVE_ROOT + os.sep))


def prepare(output, select):
    scope = dict(
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
    return FunctionType(base.base.base.prepare.__code__, scope)(output, select)


def child(output, select):
    # Load definitions before the inherited whole-module blockade. The actual
    # assembly adapter is exercised below; every original native filename and
    # literal kernel remains forbidden, including functions it compiles.
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True:
        raise ValueError("Explicit blocked-software release required before definition imports")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for path in OWNED:
        if (
            snapshot.digest(ROOT / path) != inputs["owned_files"][path]
            or inputs["owned_files"][path] != manifest["files"][path]["sha256"]
        ):
            raise ValueError("Selected frozen integration source changed")
    modules = (
        "cells.processes.betse_native_phase_assembly",
        "cells.processes.betse_native_seed_init_core",
    )
    loaded = {}
    for name in modules:
        module = importlib.import_module(name)
        path = "src/" + name.replace(".", "/") + ".py"
        if Path(module.__file__).resolve() != ROOT / path:
            raise ValueError("Actual frozen definitions required")
        loaded[name] = dict(path=path, sha256=snapshot.digest(ROOT / path))
    snapshot.write_json(
        output / "definition-imports.json",
        dict(modules=loaded, definitions_only=True, actual_native_or_scientific_credit=0),
    )
    scope = dict(
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
        return FunctionType(base.reuse.child.__code__, scope)(output, select)
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = scope.get("_RAW_FAILURES", ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--child", type=Path)
    parser.add_argument("--select", required=True)
    args = parser.parse_args()
    output = args.child if args.child is not None else args.prepare
    try:
        if args.child is not None:
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(args.child, args.select)
        if args.prepare is not None:
            if os.environ.get(SOFTWARE_RELEASE) != "1":
                raise ValueError("Explicit blocked-software release required")
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
