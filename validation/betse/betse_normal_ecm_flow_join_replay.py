"""Fresh native boundary identity or stdlib-only disabled conditional verification."""

import argparse
import os
import traceback
from pathlib import Path

from validation.betse import betse_mechanics_join_runtime as runtime

PREFIX = "betse-normal-ecm-flow-join"


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
        target / "started.json", dict(mode=args.mode, pid=os.getpid(), parent_pid=os.getppid())
    )
    from validation.betse import betse_normal_ecm_flow_join_boundaries as boundary

    try:
        actual = runtime.restore(runtime.read(args.source / "points.json"))
        if args.mode == "native":
            from validation.betse import betse_normal_ecm_mechanics_join_native as native

            inputs = runtime.restore(runtime.read(args.source / "inputs.json"))
            proof = native.evaluate(inputs["ordinary_inputs"])
            persist(target, "proof", proof)
            expected = boundary.native_points(inputs, runtime.plain(proof))
            runtime.write(target / "expected-points.json", expected)
            assert proof["complete_source_condition_met"] and proof["RNG_unchanged"]
            assert not proof["ionic_field"]["warnings"] and not proof["mechanics"]["warnings"]
            boundary.assert_identical(actual, expected)
        else:
            expected = []
            for index, point in enumerate(actual):
                result = boundary.disabled_reference(point)
                runtime.write(target / ("conditional-" + str(index) + ".json"), result)
                expected.append(result)
        runtime.write(
            target / "result.json",
            dict(
                status="passed",
                points=len(actual),
                native_getFlow_executed=False,
                new_active_flow_equations_evaluated=False,
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
