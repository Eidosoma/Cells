"""CPU4 immutable native-blocked INIT/SIM preparation source/software controls."""

import argparse
import importlib
import json
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_init_terminal_issued_software as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_sim_preparation.py"
LITERAL = "src/cells/processes/betse_native_init_sim_preparation_source.py"
TEST = "tests/unit/test_betse_native_init_sim_preparation.py"
FILE = "validation/betse/betse_native_init_sim_preparation_software.py"
MODULE = "validation.betse.betse_native_init_sim_preparation_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_SIM_PREPARATION_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot, guard, base = previous.snapshot, previous.guard, previous.base
FORBIDDEN_MODULES, NATIVE_ROOT = previous.FORBIDDEN_MODULES, previous.NATIVE_ROOT
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    return (
        frame.f_globals.get("__name__") == "cells.processes.betse_native_init_sim_preparation"
        and frame.f_code.co_name in ("_native", "_run_prefix")
    ) or previous.is_forbidden_frame(frame)


def _policy(select, seconds):
    if type(select) is not str or not select or type(seconds) is not int or seconds != 480:
        raise ValueError("Explicit ordinary480 native-blocked selection required")
    return seconds


def _scope():
    return dict(
        previous._scope(),
        ROOT=ROOT,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        SOFTWARE_CPU=4,
        is_forbidden_frame=is_forbidden_frame,
        _scope=_scope,
        _integration_policy=_policy,
        __file__=__file__,
    )


def prepare(output, select):
    _policy(select, 480)
    origin = previous.prior.reused.inherited.inherited.inherited.reuse
    function = FunctionType(origin.prepare.__code__, _scope(), argdefs=origin.prepare.__defaults__)
    function.__kwdefaults__ = origin.prepare.__kwdefaults__
    function(output, select)
    inputs = json.loads((output / "inputs.json").read_text())
    snapshot.write_json(output / "default-lane-inputs.json", inputs)
    inputs.update(cpu=4, init_sim_preparation_metadata=True)
    pending = output / "lane-inputs.json.pending"
    snapshot.write_json(pending, inputs)
    os.replace(pending, output / "inputs.json")


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    _policy(select, inputs.get("wall_seconds"))
    expected = dict(
        cpu=4,
        threads=1,
        metadata_bytes=512 * 2**20,
        software_bytes=2**30,
        reserve_bytes=8 * 2**30,
        selection=select,
        software_release_requested=True,
        init_sim_preparation_metadata=True,
    )
    if (
        any(
            type(inputs.get(key)) is not type(value) or inputs[key] != value
            for key, value in expected.items()
        )
        or os.environ.get(SOFTWARE_RELEASE) != "1"
        or os.sched_getaffinity(0) != {4}
        or not __debug__
        or ROOT != output / "source"
    ):
        raise ValueError("Exact immutable released/assertion-enabled CPU4 software required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    if set(inputs.get("owned_files", ())) != set(OWNED):
        raise ValueError("Exact four preparation source producers required")
    for name, pin in inputs["owned_files"].items():
        if manifest["files"][name]["sha256"] != pin or snapshot.digest(ROOT / name) != pin:
            raise ValueError("Frozen INIT/SIM preparation producer changed")
    # Definitions only, before the inherited literal/native body blockade.
    fixture = importlib.import_module(TEST[:-3].replace("/", "."))
    if Path(fixture.__file__).resolve() != ROOT / TEST:
        raise ValueError("Actual pinned software fixture definitions required")
    snapshot.write_json(output / "preparation-source-plan.json", fixture.stage.source_plan())
    origin = previous.prior.reused.inherited.inherited.inherited
    namespace = dict(vars(origin), **_scope())
    try:
        return previous._exit_status(FunctionType(origin.child.__code__, namespace)(output, select))
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES += namespace.get("_RAW_FAILURES", ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--child", type=Path)
    parser.add_argument("--select", required=True)
    args = parser.parse_args()
    output = args.prepare or args.child
    resource.setrlimit(resource.RLIMIT_AS, ((2**30 if args.child else 512 * 2**20), 2**30))
    try:
        if args.child:
            return child(output, args.select)
        if os.environ.get(SOFTWARE_RELEASE) != "1":
            raise ValueError("Explicit source/software preparation release required")
        prepare(output, args.select)
        return 0
    except BaseException as primary:
        try:
            previous.prior.reused.inherited.inherited.inherited.base.reuse.reuse._main_failure(
                output, primary
            )
        except BaseException as capture:
            global _RAW_FAILURES
            _RAW_FAILURES += ((primary, capture, output),)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
