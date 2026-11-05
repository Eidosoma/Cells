"""Immutable native-blocked natural-INIT metadata controls, CPU4 or CPU6."""

import argparse
import importlib
import json
import os
import resource
import sys
from pathlib import Path
from types import FunctionType, ModuleType

from validation.betse import betse_native_init_first_step_software as reused

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_terminal.py"
LITERAL = reused.LITERAL
TEST = "tests/unit/test_betse_native_init_terminal.py"
FILE = "validation/betse/betse_native_init_terminal_software.py"
MODULE = "validation.betse.betse_native_init_terminal_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_TERMINAL_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
DEPENDENCIES = (
    "src/cells/processes/betse_native_init_first_step.py",
    "src/cells/processes/betse_native_init_short_history_diagnostics.py",
    "src/cells/processes/betse_native_init_electrical.py",
    "tests/unit/test_betse_native_init_first_step.py",
    "tests/unit/test_betse_native_init_retained_world.py",
)
snapshot, base = reused.snapshot, reused.base
NATIVE_ROOT = reused.NATIVE_ROOT
FORBIDDEN_MODULES = reused.FORBIDDEN_MODULES | frozenset(
    ("cells.processes.betse_native_init_terminal_molecules",)
)
Reports = reused.Reports
_RAW_FAILURES = ()
OVERLAYS = (
    ("pillow", "PIL", Path("/mnt/workspaces/Cells/pillow-overlay-12.3.0-20261030-01")),
    ("beartype", "beartype", Path("/mnt/workspaces/Cells/beartype-overlay-0.22.9-20261031-01")),
)


def _overlay_inventory(overlays=OVERLAYS):
    """Bound existing file bytes without importing or installing either library."""
    result, count, total = {}, 0, 0
    for role, prefix, root in overlays:
        if role in result or not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise ValueError("Exact distinct existing overlay directories required")
        if root.resolve() != root:
            raise ValueError("Canonical unlinked overlay directory required")
        files = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if "__pycache__" in relative.parts or path.suffix in (".pyc", ".pyo"):
                continue
            if path.is_symlink():
                raise ValueError("Unlinked overlay payload required")
            if path.is_dir():
                continue
            size = path.stat().st_size
            count, total = count + 1, total + size
            if not path.is_file() or size > 64 * 2**20 or count > 8192 or total > 256 * 2**20:
                raise ValueError("Bounded existing overlay payload roster required")
            files[str(relative)] = dict(sha256=snapshot.digest(path), bytes=size)
        if not files or prefix.replace(".", "/") + "/__init__.py" not in files:
            raise ValueError("Actual declared overlay package payload required")
        result[role] = dict(root=str(root), module_prefix=prefix, files=files)
    return result


def _verify_overlay_manifest(inputs):
    declared = inputs.get("terminal_overlay_pins")
    if type(declared) is not dict or declared != _overlay_inventory():
        raise ValueError("Exact predeclared Pillow/beartype overlay roster and bytes required")
    return declared


def _loaded_overlays(declared, *, modules=None):
    """Check every loaded overlay origin; unimported files convey no loaded credit."""
    modules = sys.modules if modules is None else modules
    result = {}
    for role, row in declared.items():
        root, prefix = Path(row["root"]), row["module_prefix"]
        loaded, used = [], set()
        for name, module in tuple(modules.items()):
            if type(module) is not ModuleType:
                if name == prefix or name.startswith(prefix + "."):
                    raise ValueError("Actual loaded overlay module required")
                continue
            namespace = vars(module)
            raw_path = namespace.get("__file__")
            named = name == prefix or name.startswith(prefix + ".")
            path = Path(raw_path) if type(raw_path) is str else None
            within = path is not None and path.is_absolute() and path.is_relative_to(root)
            if not named and not within:
                continue
            spec = namespace.get("__spec__")
            if (
                not within
                or path.is_symlink()
                or path.resolve() != path
                or spec is None
                or getattr(spec, "origin", None) != raw_path
            ):
                raise ValueError("Loaded overlay origin differs from its declared image: " + name)
            relative = str(path.relative_to(root))
            pin = row["files"].get(relative)
            if (
                type(pin) is not dict
                or path.stat().st_size != pin["bytes"]
                or snapshot.digest(path) != pin["sha256"]
            ):
                raise ValueError("Loaded overlay producer bytes differ from preparation: " + name)
            used.add(relative)
            loaded.append(dict(module=name, path=raw_path, sha256=pin["sha256"]))
        result[role] = dict(
            root=str(root),
            used=bool(loaded),
            loaded=sorted(loaded, key=lambda value: value["module"]),
            unused_files=sorted(set(row["files"]) - used),
            unused_files_have_no_loaded_producer_credit=True,
        )
    return result


def _cpu(value):
    if type(value) is not int or value not in (4, 6):
        raise ValueError("Explicit blocked-metadata CPU4 or CPU6 required")
    return value


def is_forbidden_frame(frame):
    name = frame.f_globals.get("__name__")
    return (
        name in FORBIDDEN_MODULES
        or name == "cells.processes.betse_native_init_terminal"
        and frame.f_code.co_name in ("_namespace", "_run")
        or reused.is_forbidden_frame(frame)
    )


def _scope():
    return dict(
        reused._scope(),
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
        _scope=_scope,
        __file__=__file__,
    )


def prepare(output, select, *, cpu=4):
    lane = _cpu(cpu)
    if type(select) is not str or not select:
        raise ValueError("Explicit literal terminal metadata selector required")
    overlays = _overlay_inventory()
    origin = reused.inherited.inherited.inherited.reuse
    function = FunctionType(
        origin.prepare.__code__, _scope(), "prepare", origin.prepare.__defaults__
    )
    function.__kwdefaults__ = origin.prepare.__kwdefaults__
    result = function(output, select)
    inputs = json.loads((output / "inputs.json").read_text())
    snapshot.write_json(output / "default-lane-inputs.json", inputs)
    inputs.update(
        cpu=lane,
        terminal_dependencies={
            name: snapshot.digest(output / "source" / name) for name in DEPENDENCIES
        },
        terminal_metadata_only=True,
        terminal_overlay_pins=overlays,
        actual_parent_native_operator_RNG_reference_or_scientific_release=False,
    )
    _verify_overlay_manifest(inputs)
    pending = output / "lane-inputs.json.pending"
    snapshot.write_json(pending, inputs)
    os.replace(pending, output / "inputs.json")
    return result


def _prepared_policy(inputs, select, *, cpu):
    lane = _cpu(cpu)
    required = dict(
        selection=select,
        cpu=lane,
        threads=1,
        metadata_bytes=512 * 2**20,
        software_bytes=2**30,
        wall_seconds=480,
        reserve_bytes=8 * 2**30,
        software_release_requested=True,
        terminal_metadata_only=True,
        actual_parent_native_operator_RNG_reference_or_scientific_release=False,
    )
    if (
        type(select) is not str
        or not select
        or any(
            type(inputs.get(key)) is not type(value) or inputs.get(key) != value
            for key, value in required.items()
        )
    ):
        raise ValueError("Exact frozen terminal metadata/resource policy required")


def child(output, select, *, cpu=4):
    lane = _cpu(cpu)
    inputs = json.loads((output / "inputs.json").read_text())
    _prepared_policy(inputs, select, cpu=lane)
    if (
        os.environ.get(SOFTWARE_RELEASE) != "1"
        or os.sched_getaffinity(0) != {lane}
        or not __debug__
        or ROOT != output / "source"
    ):
        raise ValueError("Actual immutable assertion-enabled terminal software lane required")
    reused.inherited.inherited._external_producers(inputs, loaded=False)
    overlays = _verify_overlay_manifest(inputs)
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    if set(inputs.get("owned_files", ())) != set(OWNED) or set(
        inputs.get("terminal_dependencies", ())
    ) != set(DEPENDENCIES):
        raise ValueError("Exact selected terminal producer/dependency roster required")
    for roster in (inputs["owned_files"], inputs["terminal_dependencies"]):
        for name, expected in roster.items():
            if (
                snapshot.digest(ROOT / name) != expected
                or manifest["files"][name]["sha256"] != expected
            ):
                raise ValueError("Frozen terminal source or dependency changed: " + name)
    stage = importlib.import_module("cells.processes.betse_native_init_terminal")
    if Path(stage.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Actual frozen terminal definitions required")
    snapshot.write_json(output / "terminal-source-plan.json", stage.source_plan())
    origin = reused.inherited.inherited.inherited
    namespace = dict(vars(origin), **_scope())
    result, primary = None, None
    try:
        result = FunctionType(origin.child.__code__, namespace)(output, select)
    except BaseException as error:
        primary = error
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())
    try:
        reused.inherited.inherited._external_producers(inputs, loaded=False)
        snapshot.write_json(
            output / "terminal-external-producers.json",
            dict(
                original_pillow_pins=inputs["external_runtime_pins"],
                overlays=_loaded_overlays(overlays),
            ),
        )
    except BaseException as capture:
        _RAW_FAILURES += ((primary, capture, output),)
        if primary is None:
            raise
    if primary is not None:
        raise primary
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--child", type=Path)
    parser.add_argument("--select", required=True)
    parser.add_argument("--cpu", type=int, default=4, choices=(4, 6))
    args = parser.parse_args()
    output = args.child if args.child is not None else args.prepare
    try:
        if args.child is not None:
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(output, args.select, cpu=args.cpu)
        if os.environ.get(SOFTWARE_RELEASE) != "1":
            raise ValueError("Explicit blocked-terminal software release required")
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        return prepare(output, args.select, cpu=args.cpu)
    except BaseException as primary:
        try:
            reused.inherited.inherited.inherited.base.reuse.reuse._main_failure(output, primary)
        except BaseException as capture:
            global _RAW_FAILURES
            _RAW_FAILURES += ((primary, capture, output),)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
