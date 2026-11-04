"""CPU5 immutable-source controls for continuous runtime metadata only."""

import argparse
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_init_molecule_wrapper_authority_software as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_molecule_short_runtime.py"
LITERAL = "src/cells/processes/betse_native_init_molecule_network_source.py"
TEST = "tests/unit/test_betse_native_init_molecule_short_runtime.py"
FILE = "validation/betse/betse_native_init_molecule_short_runtime_software.py"
MODULE = "validation.betse.betse_native_init_molecule_short_runtime_software"
SOFTWARE_RELEASE = "CELLS_NATIVE_INIT_MOLECULE_SHORT_RUNTIME_SOFTWARE_RELEASED"
OWNED = SOURCE, LITERAL, TEST, FILE
snapshot, runtime, ref = previous.snapshot, previous.runtime, previous.ref
is_forbidden_frame = previous.is_forbidden_frame


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


def _namespace():
    return dict(vars(previous), **_scope(), _scope=_scope)


def prepare(directory, select=""):
    return FunctionType(previous.prepare.__code__, _namespace())(directory, select)


def child(directory):
    return FunctionType(previous.child.__code__, _namespace())(directory)


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
