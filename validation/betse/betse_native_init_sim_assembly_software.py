"""Reuse bounded CPU4 native-blocked preparation runner for SIM assembly."""

import argparse
import json
import os
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_init_sim_preparation_software as reused

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_sim_assembly.py"
LITERAL = "src/cells/processes/betse_native_init_sim_assembly_source.py"
TEST = "tests/unit/test_betse_native_init_sim_assembly.py"
FILE = "validation/betse/betse_native_init_sim_assembly_software.py"
MODULE = FILE[:-3].replace("/", ".")
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_SIM_ASSEMBLY_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot, guard, base = reused.snapshot, reused.guard, reused.base
FORBIDDEN_MODULES, NATIVE_ROOT = reused.FORBIDDEN_MODULES, reused.NATIVE_ROOT
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    return (
        (
            frame.f_globals.get("__name__") == "cells.processes.betse_native_init_sim_assembly"
            and frame.f_code.co_name in ("_native", "_construct", "_run_observed")
        )
        or (
            frame.f_globals.get("__name__")
            == "cells.processes.betse_native_init_molecule_wrapper_authority"
            and frame.f_code.co_name == "_backend"
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
    value["init_sim_assembly_metadata"] = True
    pending = output / "assembly-inputs.json.pending"
    snapshot.write_json(pending, value)
    os.replace(pending, output / "inputs.json")


def child(output, select):
    value = json.loads((output / "inputs.json").read_text())
    if value.get("init_sim_assembly_metadata") is not True:
        raise ValueError("Explicit assembly-only frozen software required")
    return _function(reused.child)(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--child", type=Path)
    parser.add_argument("--select", required=True)
    args = parser.parse_args()
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (2**30 if args.child else 512 * 2**20, 2**30))
    if args.child:
        return child(args.child, args.select)
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Explicit blocked-source preparation release required")
    prepare(args.prepare, args.select)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
