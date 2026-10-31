"""Fresh independent mechanics, native full-buffer and raw-failure workers."""

import argparse
import os
import traceback
from pathlib import Path

from validation.betse import betse_mechanics_join_runtime as runtime


def persist(root, name, value):
    import numpy as np

    runtime.write(root / (name + ".json"), value)
    runtime.write(root / (name + "-types.json"), runtime.typed_inventory(value))
    with (root / (name + ".npz")).open("xb") as stream:
        np.savez_compressed(stream, **runtime.arrays(value))
        stream.flush()
        os.fsync(stream.fileno())


def references(inputs, producer, target):
    from validation.betse import betse_mechanics_join_reference as reference

    same = {}

    def retain(name, payload):
        runtime.write(target / (name + ".json"), payload)
        same[name] = payload == runtime.read(producer / (name + ".json"))

    first = reference.evaluate(inputs, refinement=1, retain=retain)
    second = reference.evaluate(inputs, refinement=2, retain=retain)
    runtime.write(target / "full-raw-and-projection-identity.json", same)
    assert len(same) == 4 and all(same.values())
    return first, second


def execute(mode, case, source, target):
    from validation.betse import betse_mechanics_join_checks as checks

    name = ("corruption-" if mode == "corruption" else "refusal-" if mode == "raw" else "") + case
    producer = source / runtime.PREFIX / name
    inputs = runtime.restore(runtime.read(producer / "inputs.json"))
    runtime.write(target / "inputs.json", inputs)
    if mode in ("native", "raw"):
        from validation.betse import betse_mechanics_join_native as native

        proof = native.evaluate(inputs)
        persist(target, "complete-native-proof", proof)
        saved = runtime.read(producer / "native-proof.json")
        if mode == "raw":
            same_history = runtime.plain(proof["history"]) == saved["history"]
            runtime.write(
                target / "raw-history-identity.json",
                dict(
                    complete_history_same=same_history,
                    producer_refusal=runtime.read(producer / "refusal.json"),
                ),
            )
            assert same_history and proof["RNG_unchanged"]
            if case == "missing-electric-after-osmotic":
                assert proof["failure"] and proof["failure"]["stage"] == "steady_deformation"
                trial = runtime.read(producer / "failed-trial.json")
                report = checks.compare(
                    trial["candidate"]["cache"], runtime.plain(proof["history"][0]["candidate"])
                )
                runtime.write(target / "full-partial-cache-comparison.json", report)
                checks.assert_compare(report)
            else:
                assert proof["failure"] is None
                trial = runtime.read(producer / "failed-trial.json")
                assert any(
                    isinstance(value, dict) and "nonfinite_binary64_bits" in value
                    for value in trial["candidate"]["cache"]["d_cells_x"]
                )
        else:
            actual = runtime.read(producer / "actual-history.json")
            report = checks.compare(runtime.plain(proof["history"]), actual, native=True)
            exact = checks.compare(runtime.plain(proof["history"]), saved["history"], native=True)
            runtime.write(
                target / "native-full-buffer-comparison.json",
                dict(actual=report, producer_native=exact),
            )
            assert proof["failure"] is None and not proof["warnings"] and proof["RNG_unchanged"]
            assert checks.stages(proof["history"]) == checks.stages(actual)
            checks.assert_compare(report)
            assert all(row["full_binary64_bytes_equal"] for row in exact["fields"])
            checks.assert_controls(inputs, runtime.plain(proof["history"]))
            assert all(
                all(len(knots) == 10 for knots in row["knots"]) for row in proof["spline_calls"]
            )
        assert (
            not proof["flow_forced_on"]
            and not proof["timeDeform_executed"]
            and not proof["physical_world_rebuilt"]
        )
    else:
        first, second = references(inputs, producer, target)
        actual = runtime.read(producer / "actual-history.json")
        report = checks.compare(actual, first["history"])
        resolution = checks.compare(first["history"], second["history"])
        runtime.write(
            target / "complete-independent-comparison.json",
            dict(actual=report, resolution=resolution),
        )
        checks.assert_compare(report)
        checks.assert_compare(resolution, resolution=True)
        checks.assert_controls(inputs, actual)
        if mode == "corruption":
            saved = runtime.read(producer / "complete-corruption.json")
            changed = checks.corrupt(actual, case)
            runtime.write(
                target / "complete-corruption.json", dict(original=actual, corrupted=changed)
            )
            assert changed == saved["corrupted"] and actual == saved["original"]
            invalid = checks.compare(changed, first["history"])
            runtime.write(target / "corruption-comparison.json", invalid)
            assert invalid["maximum_error_over_budget"] > 1
            try:
                checks.assert_compare(invalid)
            except AssertionError:
                pass
            else:
                raise AssertionError("Independent mechanics checker accepted corruption")
    runtime.write(
        target / "result.json",
        dict(
            status="passed_scoped_fresh_worker",
            mode=mode,
            case=case,
            ordinary_enabled_flow_qualified=False,
            dynamic_qualified=False,
            physical_rebuild_qualified=False,
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", required=True, choices=("native", "reference", "corruption", "raw")
    )
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    runtime.guard(args.mode)
    from validation.betse import betse_mechanics_join_fixtures as fixtures

    cases = (
        fixtures.CASES
        if args.mode in ("native", "reference")
        else (fixtures.CORRUPTIONS if args.mode == "corruption" else fixtures.RAW_FAILURES)
    )
    if args.case not in cases:
        raise ValueError("Undeclared worker")
    target = runtime.root("fresh-" + args.mode + "-" + args.case)
    runtime.write(target / "unit.json", dict(mode=args.mode, case=args.case))
    try:
        execute(args.mode, args.case, args.source, target)
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
