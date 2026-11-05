"""Reuse immutable CPU4 native-blocked controls for full SIM source preparation."""

import argparse
import json
import os
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_init_sim_preparation_software as reused

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_sim_run.py"
LITERAL = "src/cells/processes/betse_native_sim_run_source.py"
TEST = "tests/unit/test_betse_native_sim_run.py"
FILE = "validation/betse/betse_native_sim_run_software.py"
MODULE = FILE[:-3].replace("/", ".")
SOFTWARE_RELEASE = "BETSE_NATIVE_SIM_RUN_SOFTWARE_RELEASED"
OWNED = (
    SOURCE,
    LITERAL,
    TEST,
    FILE,
    "src/cells/processes/betse_native_init_sim_assembly.py",
    "src/cells/processes/betse_native_init_terminal.py",
    "src/cells/processes/betse_native_init_sim_preparation.py",
)
snapshot, guard, base = reused.snapshot, reused.guard, reused.base
FORBIDDEN_MODULES, NATIVE_ROOT = reused.FORBIDDEN_MODULES, reused.NATIVE_ROOT
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    return (
        (
            frame.f_globals.get("__name__") == "cells.processes.betse_native_sim_run"
            and frame.f_code.co_name in ("_execute", "_run_observed", "_bind_runtime")
        )
        or (
            frame.f_globals.get("__name__") == "cells.processes.betse_native_init_sim_assembly"
            and frame.f_code.co_name in ("_native", "_construct", "_run_observed")
        )
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
        is_forbidden_frame=is_forbidden_frame,
        _scope=_scope,
        __file__=__file__,
    )


def _function(function):
    result = FunctionType(
        function.__code__,
        dict(vars(reused), **_scope()),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def prepare(output, select):
    _function(reused.prepare)(output, select)
    value = json.loads((output / "inputs.json").read_text())
    value["sim_run_blocked_metadata"] = True
    pending = output / "sim-run-inputs.json.pending"
    snapshot.write_json(pending, value)
    os.replace(pending, output / "inputs.json")


def child(output, select):
    value = json.loads((output / "inputs.json").read_text())
    if value.get("sim_run_blocked_metadata") is not True:
        raise ValueError("Explicit immutable full-SIM preparation software required")
    return _function(reused.child)(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--child", type=Path)
    parser.add_argument("--select", required=True)
    args = parser.parse_args()
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (2**30 if args.child else 512 * 2**20, 2**30))
    if args.child:
        return child(args.child, args.select)
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Explicit source-blocked software release required")
    prepare(args.prepare, args.select)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
