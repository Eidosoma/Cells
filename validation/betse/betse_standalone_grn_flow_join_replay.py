"""Fresh native or stdlib conditional worker, with complete per-point evidence."""

import argparse
import hashlib
import os
import traceback
from pathlib import Path

from validation.betse import betse_mechanics_join_runtime as runtime

PREFIX = "betse-standalone-grn-flow-join"


def persist(root, name, value):
    import numpy as np

    runtime.write(root / (name + ".json"), value)
    runtime.write(root / (name + "-types.json"), runtime.typed_inventory(value))
    with (root / (name + ".npz")).open("xb") as stream:
        np.savez_compressed(stream, **runtime.arrays(value))
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("native", "reference"))
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    runtime.guard(args.mode)
    target = args.source / args.mode
    runtime.write(
        target / "started.json",
        dict(
            pid=os.getpid(),
            parent_pid=os.getppid(),
            mode=args.mode,
            input_sha256=hashlib.sha256((args.source / "inputs.json").read_bytes()).hexdigest(),
        ),
    )
    try:
        if args.mode == "native":
            from validation.betse import betse_standalone_grn_flow_join_native as native

            inputs = runtime.restore(runtime.read(args.source / "inputs.json"))
            result = native.capture(inputs)
            persist(target, "cold", result.pop("cold"))
            history = result.pop("history")
            for index, row in enumerate(history):
                persist(target, "invocation-" + str(index), row)
            persist(target, "metadata", result)
            runtime.write(
                target / "result.json",
                dict(
                    status="captured",
                    invocations=len(history),
                    source_status=result["status"],
                    ordinary_getFlow_executed=False,
                ),
            )
        else:
            from validation.betse import betse_standalone_grn_flow_join_reference as reference

            points = runtime.read(args.source / "points-index.json")
            completed = []
            for point in points:
                payload = runtime.restore(runtime.read(args.source / (point["name"] + ".json")))
                for level, precision in ((1, 100), (2, 160)):
                    names = []

                    def retain(name, value, point=point, names=names):
                        runtime.write(target / point["name"] / (name + ".json"), value)
                        names.append(name)

                    reference.evaluate(payload, refinement=level, retain=retain)
                    assert any(name.startswith("raw-") for name in names)
                    assert "projected-reference-" + str(precision) in names
                    completed.append(
                        dict(
                            name=point["name"],
                            precision=precision,
                            files=names,
                            input_sha256=hashlib.sha256(
                                (args.source / (point["name"] + ".json")).read_bytes()
                            ).hexdigest(),
                        )
                    )
            runtime.write(target / "index.json", completed)
            runtime.write(
                target / "result.json",
                dict(
                    status="captured",
                    points=len(points),
                    fresh_precision_forms=len(completed),
                    independently_carried_trajectory=False,
                ),
            )
    except BaseException as error:
        runtime.write(
            target / "failure.json",
            dict(type=type(error).__name__, reason=str(error), traceback=traceback.format_exc()),
        )
        raise
    finally:
        runtime.write(target / "runtime.json", runtime.capture())


if __name__ == "__main__":
    main()
