"""CPU4 immutable native-blocked completed-history observation controls."""

import argparse
import json
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_sim_run_software as inherited

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_sim_history_observation.py"
LITERAL = inherited.LITERAL
TEST = "tests/unit/test_betse_native_sim_history_observation.py"
FILE = "validation/betse/betse_native_sim_history_observation_software.py"
MODULE = FILE[:-3].replace("/", ".")
SOFTWARE_RELEASE = "BETSE_NATIVE_SIM_HISTORY_OBSERVATION_SOFTWARE_RELEASED"
OWNED = (*inherited.OWNED, SOURCE, TEST, FILE)
snapshot, guard, base = inherited.snapshot, inherited.guard, inherited.base
FORBIDDEN_MODULES, NATIVE_ROOT = inherited.FORBIDDEN_MODULES, inherited.NATIVE_ROOT
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    return (
        frame.f_globals.get("__name__") == "cells.processes.betse_native_sim_history_observation"
        and frame.f_code.co_name == "_live"
    ) or inherited.is_forbidden_frame(frame)


def _scope():
    return dict(
        inherited._scope(),
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
        dict(vars(inherited.reused), **_scope()),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def prepare(output, select):
    _function(inherited.reused.prepare)(output, select)
    value = json.loads((output / "inputs.json").read_text())
    value["history_observation_blocked_metadata"] = True
    pending = output / "history-inputs.json.pending"
    snapshot.write_json(pending, value)
    os.replace(pending, output / "inputs.json")


def child(output, select):
    value = json.loads((output / "inputs.json").read_text())
    if value.get("history_observation_blocked_metadata") is not True:
        raise ValueError("Explicit immutable completed-history software required")
    return _function(inherited.reused.child)(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--child", type=Path)
    parser.add_argument("--select", required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (2**30 if args.child else 512 * 2**20, 2**30))
    if args.child:
        return child(args.child, args.select)
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Explicit blocked completed-history software release required")
    prepare(args.prepare, args.select)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
