"""Immutable CPU4 software for prepared whole SEED init_core metadata only.

Reuses the established snapshot/resource guard and protected WPC test runner;
actual owner acquisition, source bodies, numerical solves and RNG stay blocked.
"""

import argparse
import importlib
import json
import os
import resource
import runpy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_seed_voronoi_mesh_software as base
from validation.betse import betse_native_tissue_handler_attachment_software as bounded

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_seed_init_core.py"
LITERAL = "src/cells/processes/betse_native_seed_init_core_source.py"
TEST = "tests/unit/test_betse_native_seed_init_core.py"
FILE = "validation/betse/betse_native_seed_init_core_software.py"
MODULE = "validation.betse.betse_native_seed_init_core_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_INIT_CORE_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)

FORBIDDEN_MODULES = base.FORBIDDEN_MODULES | frozenset(
    (
        "cells.processes.betse_native_seed_init_core_source",
        "cells.processes.betse_native_seed_world_geometry_source",
        "cells.processes.betse_native_single_cell_poisson_source",
        "cells.processes.betse_native_make_world_tail_source",
        "cells.processes.betse_native_seed_voronoi_lifecycle_source",
    )
)
snapshot, inherited, reuse = base.snapshot, base.inherited, base.reuse
NATIVE_ROOT, Reports = base.NATIVE_ROOT, base.Reports
BASE, guard, runtime = bounded.BASE, bounded.guard, bounded.runtime
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    if frame.f_globals.get("__name__") in FORBIDDEN_MODULES or str(
        frame.f_globals.get("__name__", "")
    ).startswith("numpy.linalg"):
        return True
    path = os.path.normpath(frame.f_code.co_filename)
    return os.path.isabs(path) and (path == NATIVE_ROOT or path.startswith(NATIVE_ROOT + os.sep))


def prepare(output, select):
    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical-checkout image preparation required")
    external = {}
    for name, filename, expected in base.base.tail.PILLOW_PINS:
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
            cpu=4,
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
        raise ValueError("Core source preparation has no software execution release")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    module = importlib.import_module("cells.processes.betse_native_seed_init_core")
    digest = snapshot.digest(ROOT / SOURCE)
    if (
        Path(module.__file__).resolve() != ROOT / SOURCE
        or digest != inputs["owned_files"][SOURCE]
        or digest != manifest["files"][SOURCE]["sha256"]
    ):
        raise ValueError("Actual verified frozen core producer required")
    snapshot.write_json(
        output / "definition-imports.json",
        dict(
            module=module.__name__,
            source=SOURCE,
            sha256=digest,
            definitions_and_shared_library_imports_only=True,
            source_constructor_decoder_RNG_operator_or_scientific_credit=0,
        ),
    )
    snapshot.write_json(
        output / "source-plan.json",
        dict(
            source_plan=module.source_plan(),
            source_producer=dict(module=module.__name__, source=SOURCE, sha256=digest),
            snapshot_sha256=inputs["snapshot_sha256"],
            captured_before_tests=True,
            source_constructor_decoder_RNG_operator_or_scientific_credit=0,
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
        raise ValueError("Separate native-blocked software release required")
    output = Path(output).absolute()
    if (
        not output.is_relative_to(BASE)
        or output.exists()
        or any(p.is_symlink() for p in (output, *output.parents))
        or os.sched_getaffinity(0) != {4}
    ):
        raise ValueError("Fresh real CPU4 output required")
    output.mkdir(parents=True)
    metadata = output / "metadata"
    metadata.mkdir()
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_"))}
    command = [sys.executable, "-B", "-m", MODULE, "--prepare", str(output)]
    if select:
        command.extend(["--select", select])
    guard.run_bounded(
        command,
        directory=metadata,
        cwd=ROOT,
        env=environment,
        timeout=120,
        max_rss_bytes=512 * 2**20,
        min_available_bytes=8 * 2**30,
        process_tree_memory_metric="rss",
    )
    frozen = output / "source"
    digest = json.loads((output / "inputs.json").read_text())["snapshot_sha256"]
    manifest = snapshot.verify(frozen, manifest_sha256=digest)
    snapshot.assert_checkout_unchanged(frozen)
    (output / "process").mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_"))}
    env.update(
        PYTHONPATH=os.pathsep.join(
            [
                str(frozen),
                str(frozen / "src"),
                *[
                    p
                    for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                    if p and not Path(p).resolve().is_relative_to(ROOT)
                ],
            ]
        ),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
    )
    result = None
    try:
        command = [sys.executable, "-B", "-m", MODULE, "--child", str(output)]
        if select:
            command.extend(["--select", select])
        result = guard.run_bounded(
            command,
            directory=output / "process",
            cwd=frozen,
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
    except Exception as error:
        result = (
            json.loads((output / "process/failure.json").read_text())
            if (output / "process/failure.json").exists()
            else dict(status="failed", error=str(error))
        )
    verification_errors = []
    try:
        snapshot.verify(frozen, manifest_sha256=digest)
        loaded = json.loads((output / "runtime.json").read_text())["loaded_files"]
        producers = {}
        for row in loaded.values():
            path = Path(row["path"])
            if path.is_relative_to(ROOT):
                raise ValueError(
                    "Frozen execution loaded a mutable checkout producer: " + str(path)
                )
            if path.is_relative_to(frozen):
                name = str(path.relative_to(frozen))
                if (
                    name not in manifest["files"]
                    or row.get("sha256") != manifest["files"][name]["sha256"]
                ):
                    raise ValueError("Loaded producer differs from immutable snapshot: " + name)
                producers[name] = row["sha256"]
        if not all(name in producers for name in (SOURCE, TEST, FILE)):
            raise ValueError("Missing selected loaded producer")
        snapshot.write_json(output / "producer-bindings.json", producers)
    except Exception as error:
        verification_errors.append(dict(type=type(error).__name__, message=str(error)))
    integration = None
    try:
        snapshot.assert_checkout_unchanged(frozen)
    except Exception as error:
        integration = dict(type=type(error).__name__, message=str(error))
    receipts = sorted((output / "pytest").rglob("native-blocked.json"))
    cases = (
        list(ET.parse(output / "tests.xml").iter("testcase"))
        if (output / "tests.xml").exists()
        else []
    )
    native_guard = (
        json.loads((output / "native-entry-guard.json").read_text())
        if (output / "native-entry-guard.json").exists()
        else {}
    )
    complete_guards = (
        bool(cases)
        and len(cases) == len(receipts)
        and all(json.loads(path.read_text())["attempted"] == [] for path in receipts)
    )
    guard_ok = (
        complete_guards
        and native_guard.get("attempted") == []
        and native_guard.get("prior_profile_trace_restored") is True
    )
    status = int(result.get("returncode", 1))
    if verification_errors or not guard_ok:
        status = 1
    snapshot.write_json(
        output / "result.json",
        dict(
            status="passed" if status == 0 else "failed",
            process=result,
            verification_errors=verification_errors,
            snapshot_sha256=digest,
            selected_cases=len(cases),
            guard_receipts=len(receipts),
            complete_guards=guard_ok,
            actual_native_entries=0 if guard_ok else None,
            integration_pending=integration is not None,
            checkout_drift=integration,
            scientific_credit=0,
        ),
    )
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="core")
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
