"""CPU4 immutable software controls; actual RNG and all model entry stay held."""

import argparse
import json
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_sim_run_software as reused

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_common_start_rng.py"
LITERAL = SOURCE
TEST = "tests/unit/test_native_common_start_rng.py"
FILE = "validation/betse/native_common_start_rng_software.py"
MODULE = FILE[:-3].replace("/", ".")
SOFTWARE_RELEASE = "BETSE_COMMON_START_RNG_SOFTWARE_RELEASED"
OWNED = (SOURCE, TEST, FILE)
snapshot, guard, base = reused.snapshot, reused.guard, reused.base
FORBIDDEN_MODULES, NATIVE_ROOT = reused.FORBIDDEN_MODULES, reused.NATIVE_ROOT
_RAW_FAILURES = ()


def _definition_dependencies():
    """Closure seeds only; the reused child loads these under its 1GiB limit."""
    from cells.processes import betse_native_init_dynamics_prelude as prelude
    from cells.processes import betse_native_init_retained_world as retained
    from cells.processes import betse_native_parameter_seed_init_transition as transition

    return prelude, retained, transition


def is_forbidden_frame(frame):
    return (
        frame.f_globals.get("__name__") == "validation.betse.native_common_start_rng"
        and frame.f_code.co_name == "_execute_program"
    ) or reused.is_forbidden_frame(frame)


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
        dict(vars(reused.reused), **_scope()),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def prepare(output, select):
    _function(reused.reused.prepare)(output, select)
    value = json.loads((output / "inputs.json").read_text())
    value["common_start_rng_blocked_metadata"] = True
    pending = output / "rng-inputs.json.pending"
    snapshot.write_json(pending, value)
    os.replace(pending, output / "inputs.json")


def child(output, select):
    value = json.loads((output / "inputs.json").read_text())
    if value.get("common_start_rng_blocked_metadata") is not True:
        raise ValueError("Explicit immutable common-start metadata controls required")
    return _function(reused.reused.child)(output, select)


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
        raise ValueError("Explicit common-start software release required")
    prepare(args.prepare, args.select)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
