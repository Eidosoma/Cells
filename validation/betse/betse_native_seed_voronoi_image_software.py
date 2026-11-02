"""Unreleased immutable runner for native-blocked image-prefix metadata only."""

import argparse
import importlib
import json
import os
import resource
import runpy
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_phase_tail_software as tail
from validation.betse import betse_native_world_phase_construction_software as reuse

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_seed_voronoi_image.py"
LITERAL = "src/cells/processes/betse_native_seed_voronoi_image_source.py"
TEST = "tests/unit/test_betse_native_seed_voronoi_image.py"
FILE = "validation/betse/betse_native_seed_voronoi_image_software.py"
MODULE = "validation.betse.betse_native_seed_voronoi_image_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_VORONOI_IMAGE_SOFTWARE_RELEASED"
OWNED = (
    SOURCE,
    LITERAL,
    TEST,
    FILE,
    "src/cells/processes/betse_native_seed_world_prefix.py",
    "src/cells/processes/betse_native_world_phase_construction.py",
    "src/cells/processes/betse_native_phase_tail.py",
)
FORBIDDEN_MODULES = reuse.FORBIDDEN_MODULES | frozenset(
    (
        "cells.processes.betse_native_seed_voronoi_image_source",
        "cells.processes.betse_native_single_cell_image_mask_source",
    )
)
NATIVE_ROOT, snapshot, inherited = reuse.NATIVE_ROOT, reuse.snapshot, reuse.inherited
Reports = reuse.Reports
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    if frame.f_globals.get("__name__") in FORBIDDEN_MODULES:
        return True
    name = os.path.normpath(frame.f_code.co_filename)
    return os.path.isabs(name) and (name == NATIVE_ROOT or name.startswith(NATIVE_ROOT + os.sep))


def prepare(output, select):
    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical-checkout image preparation required")
    external = {}
    for name, filename, expected in tail.PILLOW_PINS:
        if snapshot.digest(Path(filename)) != expected:
            raise ValueError("Reviewed existing Pillow producer changed: " + name)
        external[name] = dict(path=filename, sha256=expected)
    files = runpy.run_path(str(ROOT / inherited.CLOSURE))["closure"](ROOT, list(OWNED))
    for name in (inherited.CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    snapshot.assert_checkout_unchanged(output / "source")
    snapshot.write_json(
        output / "inputs.json",
        dict(
            source_plan=None,
            source_plan_deferred=True,
            source_plan_capture="verified_frozen_child_before_tests",
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            git_revision=manifest["git_revision"],
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            selection=select,
            external_runtime_pins=external,
            cpu=6,
            threads=1,
            metadata_bytes=512 * 2**20,
            software_bytes=2**30,
            wall_seconds=480,
            reserve_bytes=8 * 2**30,
            software_release_requested=os.environ.get(SOFTWARE_RELEASE) == "1",
            actual_source_native_reference_or_scientific_release=False,
            prepared_image_route_and_helper_pins_bound=False,
            native_guard_policy=dict(root=NATIVE_ROOT, modules=sorted(FORBIDDEN_MODULES)),
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True:
        raise ValueError("Source-only image preparation has no metadata execution release")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    # Load frozen definitions and shared libraries before installing the method
    # blockade, just as the existing constructor runners do. No constructor,
    # descriptor read, image decoder, source replay or RNG call occurs here.
    module = importlib.import_module("cells.processes.betse_native_seed_voronoi_image")
    if Path(module.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Canonical frozen selected image definitions required")
    source_sha256 = snapshot.digest(ROOT / SOURCE)
    if (
        source_sha256 != inputs["owned_files"][SOURCE]
        or source_sha256 != manifest["files"][SOURCE]["sha256"]
    ):
        raise ValueError("Selected image producer differs from the verified snapshot")
    snapshot.write_json(
        output / "definition-imports.json",
        dict(
            module=module.__name__,
            source=SOURCE,
            sha256=source_sha256,
            definitions_and_shared_library_imports_only=True,
            source_constructor_decoder_RNG_or_scientific_credit=0,
        ),
    )
    # This is the actual metadata plan from the verified producer, evaluated
    # under the existing software cap; preparation never imports that producer.
    snapshot.write_json(
        output / "source-plan.json",
        dict(
            source_plan=module.source_plan(),
            source_producer=dict(module=module.__name__, source=SOURCE, sha256=source_sha256),
            snapshot_sha256=inputs["snapshot_sha256"],
            captured_before_tests=True,
            source_constructor_decoder_RNG_or_scientific_credit=0,
        ),
    )
    # Reuse unchanged independent restoration/evidence/immutable producer checks.
    # The private globals choose this test/source/module and stricter literal roster.
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
    fn = FunctionType(reuse.child.__code__, namespace)
    result = fn(output, select)
    global _RAW_FAILURES
    _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())
    return result


def software(output, select):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Image metadata software requires separate Root release")
    namespace = dict(vars(inherited), ROOT=ROOT, SOURCE=SOURCE, TEST=TEST, FILE=FILE, MODULE=MODULE)
    return FunctionType(inherited.software.__code__, namespace)(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="preparation,entry,observer,bindings,retention")
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
