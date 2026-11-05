"""Frozen CPU5 blocked controls for complete INIT-to-SIM orchestration."""

import argparse
import importlib
import json
import os
import resource
import runpy
import sys
from pathlib import Path
from types import FunctionType

from validation.betse import native_init_terminal_reference_software as base

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_sim_demo.py"
TEST = "tests/unit/test_native_sim_demo.py"
FILE = "validation/betse/native_sim_demo_software.py"
MODULE = "validation.betse.native_sim_demo_software"
OBSERVATION = "validation/betse/native_sim_demo_observation.py"
OBSERVATION_TEST = "tests/unit/test_native_sim_demo_observation.py"
OWNED = (SOURCE, TEST, FILE, "validation/betse/native_seed_demo.py", OBSERVATION, OBSERVATION_TEST)
COMPILE_ONLY = ("src/cells/processes/betse_native_init_sim_preparation.py",)
RELEASE = "CELLS_SIM_DEMO_BLOCKED_SOFTWARE"
POLICY = dict(base.POLICY, cpu=5)
snapshot, guard, runtime = base.snapshot, base.guard, base.runtime
BASE, CLOSURE, Reports = base.BASE, base.CLOSURE, base.Reports
OVERLAY = Path("/mnt/workspaces/Cells/pillow-overlay-12.3.0-20261030-01")
OVERLAY_PINS = {
    "PIL/__init__.py": "7361b6ad3878589affe5956e4a4da24d71398b0891fd3a8c15e9362217b4ca01",
    "PIL/Image.py": "04af3f2db7ffdd61e829fa7aa8f5481d394a0a4129a8fd8aa5b13908928fcd6d",
}


def forbidden(frame):
    return base.forbidden(frame) or (
        frame.f_globals.get("__name__")
        == "validation.betse.betse_native_parameter_world_ready_qualification"
        and frame.f_code.co_name
        in ("_execute", "acquire_world_ready", "acquire_current_world_ready")
    )


def blocked(folder):
    from contextlib import contextmanager

    return contextmanager(
        FunctionType(base.blocked.__wrapped__.__code__, dict(vars(base), forbidden=forbidden))
    )(folder)


def _namespace():
    return dict(
        vars(base),
        **{
            name: globals()[name]
            for name in ("ROOT", "SOURCE", "TEST", "FILE", "MODULE", "OWNED", "RELEASE", "POLICY")
        },
        __file__=__file__,
    )


def _overlay():
    for name, expected in OVERLAY_PINS.items():
        path = OVERLAY / name
        if path.is_symlink() or not path.is_file() or snapshot.digest(path) != expected:
            raise ValueError("Reviewed existing Pillow definition overlay changed")
    files = {}
    for path in sorted(OVERLAY.rglob("*")):
        if path.is_symlink():
            raise ValueError("Linked overlay refused")
        if path.is_file() and "__pycache__" not in path.parts:
            files[str(path.relative_to(OVERLAY))] = snapshot.digest(path)
    return dict(root=str(OVERLAY), files=files, selected=OVERLAY_PINS)


def prepare(output, select):
    snapshot.write_json(output / "external-runtime.json", _overlay())
    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical SIM software snapshot required")
    files = runpy.run_path(str(ROOT / CLOSURE))["closure"](
        ROOT,
        [
            *OWNED,
            *COMPILE_ONLY,
            "validation/betse/native_seed_world_callback_prelude.py",
            "validation/betse/native_seed_demo_launch.py",
        ],
    )
    for name in (CLOSURE, "tests/__init__.py", "pyproject.toml", *COMPILE_ONLY):
        files[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    snapshot.assert_checkout_unchanged(output / "source")
    snapshot.write_json(
        output / "inputs.json",
        dict(
            kind="cells.complete_SIM_orchestration_blocked_software@1",
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            compile_only_sources={name: manifest["files"][name]["sha256"] for name in COMPILE_ONLY},
            git_revision=manifest["git_revision"],
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            selection=select,
            policy=POLICY,
            software_release_requested=os.environ.get(RELEASE) == "1",
            native_source_reference_owner_or_scientific_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def software(output, select):
    return FunctionType(base.software.__code__, _namespace())(output, select)


def child(output, select):
    import pytest

    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["software_release_requested"] is not True or inputs["policy"] != POLICY:
        raise ValueError("Explicit immutable CPU5 SIM software required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != inputs["owned_files"][name]:
            raise ValueError("Selected SIM orchestration producer changed")
    declared = json.loads((output / "external-runtime.json").read_text())
    if _overlay() != declared:
        raise ValueError("Predeclared overlay inventory changed")
    sys.path.append(str(OVERLAY))
    module = importlib.import_module("validation.betse.native_sim_demo")
    # Definition imports precede the per-case blockade. Actual native modules,
    # owners, source bodies, RNG and operators are refused in every test.
    importlib.import_module("tests.unit.test_native_sim_demo")
    snapshot.write_json(output / "source-plan.json", module.source_plan())
    os.environ[RELEASE] = "1"
    reports = Reports(output / "reports")
    try:
        code = pytest.main(
            [
                "--noconftest",
                "-q",
                "-x",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                "--basetemp=" + str(output / "pytest"),
                "--junitxml=" + str(output / "tests.xml"),
                str(ROOT / TEST),
                str(ROOT / OBSERVATION_TEST),
                "-k",
                select,
            ],
            plugins=[reports],
        )
    finally:
        snapshot.write_json(output / "runtime.json", runtime.inventory())
        snapshot.write_json(
            output / "loaded-selected.json",
            {name: manifest["files"][name]["sha256"] for name in OWNED},
        )
    return int(code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "child", "software"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="sim_demo")
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
    parser.error("Choose immutable preparation or blocked software")


if __name__ == "__main__":
    raise SystemExit(main())
