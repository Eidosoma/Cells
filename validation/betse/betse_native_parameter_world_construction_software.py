"""Prepare the new pre-phase parameter claim; no automatic test/native launch."""

import argparse
import json
import os
from pathlib import Path

from validation.betse import betse_native_parameter_load_remainder_software as reused

FILE = "validation/betse/betse_native_parameter_world_construction_software.py"
TEST = "tests/unit/test_betse_native_parameter_world_construction.py"
OWNED = ("src/cells/processes/betse_native_parameter_world_construction.py", FILE, TEST)
SOFTWARE_RELEASE = "CELLS_NATIVE_PARAMETER_WORLD_CONSTRUCTION_SOFTWARE_RELEASED"


def prepare(repository, directory):
    from cells.processes import betse_native_parameter_world_construction as stage

    repo = Path(repository).resolve(strict=True)
    if Path(__file__).resolve() != repo / FILE:
        raise ValueError("Prepare the actual single editable checkout only")
    return reused.prepare_sources(repo, directory, file=FILE, owned=OWNED, plan=stage.source_plan())


def child(output):
    return reused.callbacks.delegate(reused.inherited.child, TEST=TEST)(output)


def software(packet, output):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("World-construction software execution remains held for Root")
    return reused.callbacks.delegate(reused.inherited.software, FILE=FILE)(packet, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--software", type=Path)
    mode.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.child:
        return child(args.child)
    if args.prepare:
        print(json.dumps(prepare(args.repository, args.prepare)))
        return 0
    if args.software and args.output:
        result = software(args.software, args.output)
        print(json.dumps(result))
        return int(result["returncode"])
    parser.error("--software requires --output")


if __name__ == "__main__":
    raise SystemExit(main())
