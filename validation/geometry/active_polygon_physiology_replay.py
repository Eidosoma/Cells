"""Fresh guarded conversion or initial-field worker; never execute a trajectory."""

import argparse
import json
import os
import traceback
from pathlib import Path

from validation.geometry import active_polygon_physiology_runtime as runtime


def read(path):
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Active physiology evidence input exceeds 16 MiB")
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", required=True, choices=("conversion", "initial-field", "corruption")
    )
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])

    def write(name, value):
        runtime.write(root / (name + ".json"), value)

    runtime.guard(args.mode)
    from validation.geometry import active_polygon_physiology_reference as reference

    status = "failed"
    try:
        source = args.source / "active-polygon-physiology"
        stem = ("corruption-" if args.mode == "corruption" else "positive-") + args.case
        packet = read(source / (stem + "-packet.json"))
        write("input", packet)
        if args.mode in ("conversion", "corruption"):
            for refinement in (1, 2):
                target = reference.materialize(
                    packet["geometry_declaration"],
                    packet["geometry"],
                    packet["request"],
                    refinement=refinement,
                )
                write("conversion-targets-" + str(refinement), target)
                if args.mode == "conversion":
                    assert target == read(
                        source / (stem + f"-conversion-targets-{refinement}.json")
                    )
            if args.mode == "corruption":
                try:
                    reference.compare_conversion(packet)
                except AssertionError as error:
                    write(
                        "corruption-refusal",
                        dict(
                            type=type(error).__name__,
                            reason=str(error),
                            expected_corruption_refused=True,
                        ),
                    )
                else:
                    raise AssertionError(
                        "Independent reference admitted the corrupted active definition"
                    )
            else:
                report = reference.compare_conversion(packet)
                write("conversion-comparison", report)
                assert report == read(source / (stem + "-conversion-comparison.json"))
        else:
            report = reference.compare_initial_field(packet, retain=write)
            write("field-comparison", report)
            reference.assert_initial_field(report)
        status = "passed"
        write(
            "result",
            dict(
                status=status,
                case=args.case,
                mode=args.mode,
                production_imports=False,
                trajectory_executed=False,
                native_equivalence=False,
            ),
        )
    except Exception as error:
        write(
            "failure",
            dict(
                status="failed",
                case=args.case,
                mode=args.mode,
                type=type(error).__name__,
                reason=str(error),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    finally:
        write("runtime", runtime.capture() | dict(status=status, case=args.case, mode=args.mode))


if __name__ == "__main__":
    main()
