"""Fresh source-denied active ECM conversion and complete-field replay."""

import argparse
import hashlib
import json
import os
import traceback
from pathlib import Path

from validation.geometry import active_ecm_polygon_runtime as runtime


def read(path):
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Active ECM input exceeds 16 MiB")
    return json.loads(path.read_text())


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=("conversion", "initial-field", "corruption", "field-corruption"),
    )
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    runtime.guard(args.mode)
    from validation.geometry import active_ecm_polygon_reference as reference

    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])

    def write(name, value):
        runtime.write(root / (name + ".json"), value)

    status = "failed"
    try:
        source = args.source / "active-ecm-polygon"
        stem = (
            args.mode + "-" if args.mode in ("corruption", "field-corruption") else "positive-"
        ) + args.case
        suffix = "-changed-packet.json" if args.mode == "field-corruption" else "-packet.json"
        packet = read(source / (stem + suffix))
        write("input", packet)
        if args.mode != "corruption":
            assert digest(packet["geometry"]) == packet["geometry_identity"]
            assert (
                digest(dict(definition=packet["definition"], provenance=packet["provenance"]))
                == packet["identity"]
            )
            request = packet["geometry_request"]
            assert (
                digest({key: value for key, value in request.items() if key != "identity"})
                == request["identity"]
            )
            assert packet["geometry"]["request_identity"] == request["identity"]
        if args.mode in ("conversion", "corruption"):
            targets = []
            for refinement in (1, 2):
                target = reference.materialize(
                    packet["geometry_declaration"],
                    packet["geometry"],
                    packet["request"],
                    refinement=refinement,
                )
                write("conversion-targets-" + str(refinement), target)
                assert target == read(
                    source / (stem + "-conversion-targets-" + str(refinement) + ".json")
                )
                targets.append(target)
            if args.mode == "corruption":
                try:
                    reference.compare_conversion(packet, *targets)
                except AssertionError as error:
                    write(
                        "expected-refusal",
                        dict(type=type(error).__name__, reason=str(error), corruption_refused=True),
                    )
                else:
                    raise AssertionError("Independent reference admitted conversion corruption")
            else:
                report = reference.compare_conversion(packet, *targets)
                write("comparison", report)
                assert report == read(source / (stem + "-conversion-comparison.json"))
        else:
            report = reference.compare_initial_field(packet, retain=write)
            write("comparison", report)
            if args.mode == "field-corruption":
                try:
                    reference.assert_initial_field(report)
                except AssertionError as error:
                    write(
                        "expected-refusal",
                        dict(
                            type=type(error).__name__,
                            reason=str(error),
                            field_corruption_refused=True,
                        ),
                    )
                else:
                    raise AssertionError("Independent full-field reference admitted corruption")
            else:
                reference.assert_initial_field(report)
        status = "passed"
        write(
            "result",
            dict(
                status=status,
                case=args.case,
                mode=args.mode,
                production_imports=False,
                time_advanced=False,
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
