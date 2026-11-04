"""Immutable ordinary480s controls only; positive owner/source work held."""

import argparse
import importlib
import json
import os
import resource
import traceback
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_init_first_step_software as reused

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_short_history.py"
DIAGNOSTICS = "src/cells/processes/betse_native_init_short_history_diagnostics.py"
LITERAL = reused.LITERAL
TEST = "tests/unit/test_betse_native_init_short_history.py"
DIAGNOSTICS_TEST = "tests/unit/test_betse_native_init_short_history_diagnostics.py"
FILE = "validation/betse/betse_native_init_short_history_software.py"
MODULE = "validation.betse.betse_native_init_short_history_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_SHORT_HISTORY_SOFTWARE_RELEASED"
OWNED = (SOURCE, DIAGNOSTICS, TEST, DIAGNOSTICS_TEST, FILE)
snapshot, base = reused.snapshot, reused.base
NATIVE_ROOT = reused.NATIVE_ROOT
FORBIDDEN_MODULES = reused.FORBIDDEN_MODULES
_RAW_FAILURES = ()


def _cpu(value):
    if type(value) is not int or value not in (4, 6):
        raise ValueError("Explicit released software CPU4 or default CPU6 required")
    return value


def is_forbidden_frame(frame):
    if frame.f_globals.get("__name__") == "cells.processes.betse_native_init_short_history":
        if frame.f_code.co_name in ("_run", "_namespace", "_dispatch_impl"):
            return True
    return reused.is_forbidden_frame(frame)


def _policy(select, seconds):
    if type(select) is not str or not select or type(seconds) is not int or seconds != 480:
        raise ValueError("Only explicit ordinary480 native-blocked controls are available")
    return 480


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
        SOFTWARE_CPU=6,
        FORBIDDEN_MODULES=FORBIDDEN_MODULES,
        is_forbidden_frame=is_forbidden_frame,
        _scope=_scope,
        _integration_policy=_policy,
        __file__=__file__,
    )


def prepare(output, select, *, cpu=6):
    lane = _cpu(cpu)
    _policy(select, 480)
    origin = reused.inherited.inherited.inherited.reuse
    fn = FunctionType(origin.prepare.__code__, _scope(), "prepare", origin.prepare.__defaults__)
    fn.__kwdefaults__ = origin.prepare.__kwdefaults__
    result = fn(output, select)
    inputs = json.loads((output / "inputs.json").read_text())
    snapshot.write_json(output / "default-lane-inputs.json", inputs)
    inputs.update(
        cpu=lane,
        short_history_software_lane=dict(
            selected=lane,
            default=6,
            source_native_and_resource_caps_unchanged=True,
        ),
    )
    pending = output / "lane-inputs.json.pending"
    snapshot.write_json(pending, inputs)
    os.replace(pending, output / "inputs.json")
    return result


def child(output, select, *, cpu=6):
    lane = _cpu(cpu)
    inputs = json.loads((output / "inputs.json").read_text())
    _policy(select, inputs.get("wall_seconds"))
    if inputs.get("selection") != select or inputs.get("software_release_requested") is not True:
        raise ValueError("Exact prepared software selection/release required")
    if inputs.get("cpu") != lane or os.sched_getaffinity(0) != {lane}:
        raise ValueError("Exact prepared and measured software lane required")
    reused.inherited.inherited._external_producers(inputs, loaded=False)
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if (
            snapshot.digest(ROOT / name) != inputs["owned_files"][name]
            or inputs["owned_files"][name] != manifest["files"][name]["sha256"]
        ):
            raise ValueError("Selected frozen short-history producer changed")
    stage = importlib.import_module("cells.processes.betse_native_init_short_history")
    if Path(stage.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Actual frozen source module required")
    snapshot.write_json(output / "short-history-source-plan.json", stage.source_plan())
    origin = reused.inherited.inherited.inherited
    namespace = dict(vars(origin), **_scope())
    try:
        return FunctionType(origin.child.__code__, namespace)(output, select)
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--child", type=Path)
    parser.add_argument("--select", required=True)
    parser.add_argument("--cpu", type=int, default=6, choices=(4, 6))
    args = parser.parse_args()
    output = args.child if args.child is not None else args.prepare
    try:
        if args.child is not None:
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(output, args.select, cpu=args.cpu)
        if os.environ.get(SOFTWARE_RELEASE) != "1":
            raise ValueError("Explicit native-blocked software release required")
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        return prepare(output, args.select, cpu=args.cpu)
    except BaseException as primary:
        try:
            snapshot.write_json(
                output / "short-history-runner-failure.json",
                dict(
                    status="failed",
                    type=type(primary).__name__,
                    message=str(primary),
                    traceback=traceback.format_exc(),
                    native_scientific_credit=0,
                    full_raw_failed_owner_serialization_claimed=False,
                ),
            )
        except BaseException:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
