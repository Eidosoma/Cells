"""Prepared immutable mesh-constructor metadata runner; no release is granted."""

import argparse
import importlib
import json
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_seed_voronoi_image_software as base

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_seed_voronoi_mesh.py"
LITERAL = "src/cells/processes/betse_native_seed_voronoi_mesh_source.py"
TEST = "tests/unit/test_betse_native_seed_voronoi_mesh.py"
FILE = "validation/betse/betse_native_seed_voronoi_mesh_software.py"
MODULE = "validation.betse.betse_native_seed_voronoi_mesh_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_VORONOI_MESH_SOFTWARE_RELEASED"
OWNED = (
    SOURCE,
    LITERAL,
    TEST,
    FILE,
    "src/cells/processes/betse_native_seed_voronoi_image.py",
    "src/cells/processes/betse_native_seed_world_prefix.py",
    "src/cells/processes/betse_native_world_phase_construction.py",
    "src/cells/processes/betse_native_phase_tail.py",
)
FORBIDDEN_MODULES = base.FORBIDDEN_MODULES | frozenset(
    ("cells.processes.betse_native_seed_voronoi_mesh_source", "betse.science.math.mesh")
)
snapshot, inherited, reuse = base.snapshot, base.inherited, base.reuse
NATIVE_ROOT, Reports = base.NATIVE_ROOT, base.Reports
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    if frame.f_globals.get("__name__") in FORBIDDEN_MODULES:
        return True
    name = os.path.normpath(frame.f_code.co_filename)
    return os.path.isabs(name) and (name == NATIVE_ROOT or name.startswith(NATIVE_ROOT + os.sep))


def prepare(output, select):
    # Reuse the reviewed metadata-only freeze. No stage/Pillow/scientific
    # definition import is required under the unchanged 512 MiB metadata cap.
    namespace = dict(
        vars(base),
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
    return FunctionType(base.prepare.__code__, namespace)(output, select)


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True:
        raise ValueError("Mesh source preparation has no metadata execution release")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    module = importlib.import_module("cells.processes.betse_native_seed_voronoi_mesh")
    digest = snapshot.digest(ROOT / SOURCE)
    if (
        Path(module.__file__).resolve() != ROOT / SOURCE
        or digest != inputs["owned_files"][SOURCE]
        or digest != manifest["files"][SOURCE]["sha256"]
    ):
        raise ValueError("Actual verified frozen mesh producer required")
    snapshot.write_json(
        output / "definition-imports.json",
        dict(
            module=module.__name__,
            source=SOURCE,
            sha256=digest,
            definitions_and_shared_library_imports_only=True,
            source_constructor_decoder_RNG_or_scientific_credit=0,
        ),
    )
    snapshot.write_json(
        output / "source-plan.json",
        dict(
            source_plan=module.source_plan(),
            source_producer=dict(module=module.__name__, source=SOURCE, sha256=digest),
            snapshot_sha256=inputs["snapshot_sha256"],
            captured_before_tests=True,
            source_constructor_decoder_RNG_or_scientific_credit=0,
        ),
    )
    namespace = dict(
        vars(reuse),
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
    result = FunctionType(reuse.child.__code__, namespace)(output, select)
    global _RAW_FAILURES
    _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())
    return result


def software(output, select):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Separate Root metadata release required")
    namespace = dict(vars(inherited), ROOT=ROOT, SOURCE=SOURCE, TEST=TEST, FILE=FILE, MODULE=MODULE)
    return FunctionType(inherited.software.__code__, namespace)(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="preparation,entry,graph,retention,integration")
    args = parser.parse_args()
    output = (
        args.child
        if args.child is not None
        else args.prepare
        if args.prepare is not None
        else args.software
    )
    try:
        if args.child:
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(args.child, args.select)
        if args.prepare:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
            prepare(args.prepare, args.select)
            return 0
        if args.software:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
            return software(args.software, args.select)
    except BaseException as error:
        if output is not None:
            try:
                reuse.reuse._main_failure(output, error)
            except BaseException as secondary:
                global _RAW_FAILURES
                _RAW_FAILURES += ((error, secondary, output),)
        raise
    parser.error("Choose prepare, software or child")


if __name__ == "__main__":
    raise SystemExit(main())
