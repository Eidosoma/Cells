"""Fresh guarded finite-ECM references; no solver time advance or native call."""

import argparse
import hashlib
import json
import os
import traceback
from pathlib import Path

from validation.geometry import finite_ecm_polygon_runtime as runtime


def read(path):
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Finite-ECM reference input exceeds 16 MiB")
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
        choices=("geometry", "domain", "conversion", "initial-field", "corruption"),
    )
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    runtime.guard(args.mode)
    from validation.geometry import conservative_polygon_geometry_reference as polygon
    from validation.geometry import finite_ecm_polygon_reference as reference

    folder = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])

    def write(name, value):
        runtime.write(folder / (name + ".json"), value)

    source = args.source / "finite-ecm-polygon"
    status = "failed"
    try:
        if args.mode == "domain":
            stem = "domain-" + args.case
            raw = read(source / (stem + "-input.json"))
            write("input", raw)
            refusal = read(source / (stem + "-refusal.json"))
            assert refusal["reason"] and refusal["type"] == "PartitionRejected"
            try:
                reference.evaluate(raw)
            except (reference.ReferenceRejected, polygon.ReferenceRejected) as error:
                report = dict(type=type(error).__name__, reason=str(error))
                write("independent-refusal", report)
                assert report == read(source / (stem + "-independent-refusal.json"))
            else:
                raise AssertionError("Independent reference admitted an unsupported partition")
        elif args.mode in ("geometry", "corruption"):
            stem = ("geometry-" if args.mode == "geometry" else "corruption-") + args.case
            if args.mode == "geometry":
                raw = read(source / (stem + "-input.json"))
                actual = read(source / (stem + "-geometry.json"))
                assert digest(actual["geometry"]) == actual["identity"]
                g = actual["geometry"]
            else:
                packet = read(source / (stem + "-packet.json"))
                write("input-packet", packet)
                raw, g = packet["geometry_declaration"], packet["geometry"]
            write("input", raw)
            targets = []
            for refinement in (1, 2):
                target = reference.evaluate(raw, refinement=refinement)
                write("geometry-targets-" + str(refinement), target)
                assert target == read(
                    source / (stem + "-geometry-targets-" + str(refinement) + ".json")
                )
                targets.append(target)
            if args.mode == "corruption":
                try:
                    reference.compare_geometry(raw, g, *targets)
                except AssertionError as error:
                    write(
                        "expected-refusal",
                        dict(type=type(error).__name__, reason=str(error), corruption_refused=True),
                    )
                else:
                    raise AssertionError(
                        "Independent reference admitted corrupted owner or geometry"
                    )
            else:
                report = reference.compare_geometry(raw, g, *targets)
                write("comparison", report)
                assert report == read(source / (stem + "-comparison.json"))
        else:
            stem = "physical-" + args.case
            packet = read(source / (stem + "-packet.json"))
            write("input", packet)
            assert digest(packet["geometry"]) == packet["geometry_identity"]
            record = packet["geometry_request"]
            assert (
                digest({key: value for key, value in record.items() if key != "identity"})
                == record["identity"]
            )
            assert packet["geometry"]["request_identity"] == record["identity"]
            assert (
                digest(dict(definition=packet["definition"], provenance=packet["provenance"]))
                == packet["identity"]
            )
            if args.mode == "conversion":
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
                report = reference.compare_conversion(packet, *targets)
                write("comparison", report)
                assert report == read(source / (stem + "-conversion-comparison.json"))
            else:
                report = reference.compare_initial_field(packet, retain=write)
                write("comparison", report)
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
