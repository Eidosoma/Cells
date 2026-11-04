"""CPU5 frozen native-blocked wrapper-authority metadata controls only."""

import argparse
import importlib
from pathlib import Path
from types import FunctionType, SimpleNamespace

from validation.betse import betse_native_init_molecule_network_software as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_molecule_wrapper_authority.py"
LITERAL = "src/cells/processes/betse_native_init_molecule_channels_source.py"
TEST = "tests/unit/test_betse_native_init_molecule_wrapper_authority.py"
FILE = "validation/betse/betse_native_init_molecule_wrapper_authority_software.py"
MODULE = "validation.betse.betse_native_init_molecule_wrapper_authority_software"
SOFTWARE_RELEASE = "CELLS_NATIVE_INIT_MOLECULE_WRAPPER_SOFTWARE_RELEASED"
OWNED = SOURCE, LITERAL, TEST, FILE
snapshot, runtime, ref = previous.snapshot, previous.runtime, previous.ref


def is_forbidden_frame(frame):
    module = frame.f_globals.get("__name__", "")
    return (
        module == "beartype" or module.startswith("beartype.") or previous.is_forbidden_frame(frame)
    )


def _scope():
    return dict(
        previous._scope(),
        ROOT=ROOT,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        SOFTWARE_CPU=5,
        OWNED=OWNED,
        __file__=__file__,
    )


def prepare(directory, select=""):
    function = previous.previous.previous.previous.reused.prepare
    return FunctionType(function.__code__, _scope(), argdefs=function.__defaults__)(
        directory, select
    )


def child(directory):
    # The established child owns snapshot, guard, result and runtime checks.
    # Only its hard-coded DEFINITION import is redirected to this exact family.
    target = SOURCE.removeprefix("src/").removesuffix(".py").replace("/", ".")

    def own_import(name):
        if name != "cells.processes.betse_native_init_molecule_network":
            raise ValueError("Only the exact existing software definition import is selected")
        return importlib.import_module(target)

    namespace = dict(vars(previous), **_scope())
    namespace["importlib"] = SimpleNamespace(import_module=own_import)
    return FunctionType(previous.child.__code__, namespace)(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--child", type=Path)
    parser.add_argument("--select", default="")
    args = parser.parse_args()
    return prepare(args.prepare, args.select) if args.prepare else child(args.child)


if __name__ == "__main__":
    main()
