"""Isolated production-free native phases and fresh conditional references."""

import argparse
import os
import traceback
from pathlib import Path

from validation.betse import betse_normal_ecm_mechanics_join_runtime as runtime


def persist(root, name, value):
    import numpy as np

    runtime.write(root / (name + ".json"), value)
    runtime.write(root / (name + "-types.json"), runtime.typed_inventory(value))
    with (root / (name + ".npz")).open("xb") as stream:
        np.savez_compressed(stream, **runtime.arrays(value))
        stream.flush()
        os.fsync(stream.fileno())


def produce_native(source, target):
    from validation.betse import betse_normal_ecm_mechanics_join_native as native

    inputs = runtime.restore(runtime.read(source / "inputs.json"))
    runtime.write(target / "inputs.json", inputs)
    proof = native.evaluate(inputs)
    persist(target, "proof", proof)
    runtime.write(
        target / "result.json",
        dict(
            status="native_phase_outputs_retained",
            field_source_status=proof["ionic_field"]["status"],
            mechanics_points=len(proof["mechanics_inputs"]["steps"]),
            monolithic_native_solver_executed=False,
        ),
    )
    return runtime.plain(proof)


def produce_references(source, target):
    from validation.betse import betse_normal_ecm_mechanics_join_reference as reference

    points = runtime.read(source / "points-index.json")
    completed = []
    for point in points:
        incoming = runtime.restore(runtime.read(source / (point["name"] + ".json")))
        paths = []
        for level, precision in ((1, 100), (2, 160)):
            names = []

            def retain(name, value, names=names, point=point):
                path = target / point["name"] / (name + ".json")
                runtime.write(path, value)
                names.append(str(path.relative_to(target)))

            reference.evaluate(point["kind"], incoming, refinement=level, retain=retain)
            paths.extend(names)
            if not any("raw-" in name for name in names) or not any(
                "projected-reference-" + str(precision) in name for name in names
            ):
                raise ValueError("Missing complete raw/projection reference retention")
        completed.append(
            dict(name=point["name"], kind=point["kind"], files=paths, precisions=[100, 160])
        )
    runtime.write(target / "index.json", completed)
    runtime.write(
        target / "result.json",
        dict(
            status="conditional_references_retained",
            points=len(completed),
            precision_forms=2 * len(completed),
            independently_carried_trajectory=False,
        ),
    )
    return completed


def fresh_native(source, target, *, raw):
    from validation.betse import betse_normal_ecm_mechanics_join_boundaries as boundaries

    proof = produce_native(source, target / "native")
    saved = runtime.read(source / "native/proof.json")
    boundaries.assert_identical(proof["ionic_field"], saved["ionic_field"])
    boundaries.assert_identical(proof["mechanics_inputs"], saved["mechanics_inputs"])
    if proof["mechanics"] is not None:
        for key in ("history", "final_cache", "physical_geometry", "native_source_sha256"):
            boundaries.assert_identical(proof["mechanics"][key], saved["mechanics"][key])
    assert proof["RNG_unchanged"]
    if not raw:
        assert proof["complete_source_condition_met"]
        assert not proof["ionic_field"]["warnings"] and not proof["mechanics"]["warnings"]
    else:
        assert runtime.read(source / "failure.json")["partial_retained"]
    runtime.write(target / "result.json", dict(status="fresh_native_phase_identity", raw=raw))


def fresh_reference(source, target):
    from validation.betse import betse_normal_ecm_mechanics_join_checks as checks

    completed = produce_references(source, target / "references")
    for row in completed:
        for name in row["files"]:
            if runtime.read(target / "references" / name) != runtime.read(
                source / "references" / name
            ):
                raise ValueError("Changed complete independent raw/projection payload: " + name)
    for name in runtime.read(source / "comparison-index.json"):
        rows = runtime.read(source / (name + ".json"))
        report = checks.verify_rows(rows)
        runtime.write(target / (name + "-fresh-errors.json"), report)
        checks.assert_rows(report)
    from validation.betse import betse_mechanics_join_checks as mechanical_checks

    names = runtime.read(source / "mechanics-comparison-index.json")
    assert len(names) == 3
    for index, name in enumerate(names):
        stem = "step-" + str(index)
        trial = runtime.read(source / (stem + "-mechanics-output-before-material.json"))
        actual = [
            dict(
                frames=trial["frames"],
                auxiliaries=trial["auxiliaries"],
                candidate=trial["candidate"]["cache"],
                sample=None,
                carried_cache=trial["candidate"]["cache"],
            )
        ]
        reference_root = target / "references" / (stem + "-mechanics-input")
        first = runtime.read(reference_root / "projected-reference-100.json")
        second = runtime.read(reference_root / "projected-reference-160.json")
        record = dict(
            actual=mechanical_checks.compare(actual, first["history"]),
            resolution=mechanical_checks.compare(first["history"], second["history"]),
        )
        runtime.write(target / (name + "-fresh-errors.json"), record)
        mechanical_checks.assert_compare(record["actual"])
        mechanical_checks.assert_compare(record["resolution"], resolution=True)
    runtime.write(
        target / "result.json",
        dict(
            status="fresh_complete_conditionals_reproduced", independently_carried_trajectory=False
        ),
    )


def check_corruption(source, target):
    from validation.betse import betse_mechanics_join_checks as checks
    from validation.betse import betse_normal_ecm_mechanics_join_boundaries as boundaries

    record = runtime.read(source / "corruption.json")
    if record["kind"] == "phase-parent":
        try:
            boundaries.assert_identical(record["corrupted"], record["native_expected"])
        except AssertionError:
            pass
        else:
            raise AssertionError("Wrong source phase was accepted")
        runtime.write(
            target / "phase-corruption-result.json", dict(status="wrong_source_epoch_rejected")
        )
    else:
        targets = [
            runtime.read(
                target
                / "references"
                / ("step-" + str(index) + "-mechanics-input")
                / "projected-reference-100.json"
            )["history"][0]
            for index in range(3)
        ]
        report = checks.compare(record["corrupted"], targets)
        runtime.write(target / "corrupt-complete-comparison.json", report)
        assert report["maximum_error_over_budget"] > 1
        try:
            checks.assert_compare(report)
        except AssertionError:
            pass
        else:
            raise AssertionError("Changed mechanics output was accepted")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "produce-native",
            "produce-references",
            "native",
            "reference",
            "raw",
            "corruption",
        ),
    )
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    runtime.guard(args.mode)
    source = args.source
    if not (source / "inputs.json").exists():
        source = source / runtime.PREFIX / args.case
    if args.mode.startswith("produce-"):
        target = source / ("native" if args.mode == "produce-native" else "references")
    else:
        target = runtime.root("fresh-" + args.mode + "-" + args.case)
    runtime.write(target / "unit.json", dict(mode=args.mode, case=args.case, producer=str(source)))
    try:
        if args.mode == "produce-native":
            produce_native(source, target)
        elif args.mode == "produce-references":
            produce_references(source, target)
        elif args.mode in ("native", "raw"):
            fresh_native(source, target, raw=args.mode == "raw")
        else:
            fresh_reference(source, target)
            if args.mode == "corruption":
                check_corruption(source, target)
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
