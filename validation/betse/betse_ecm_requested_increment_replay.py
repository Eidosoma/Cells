"""Fresh native-byte and isolated complete Decimal workers, launched by Root."""

import argparse
import os
import traceback
from pathlib import Path

from validation.betse import betse_ecm_requested_increment_runtime as runtime


def context(source, name, case, target):
    from validation.betse import betse_ecm_requested_increment_fixtures as fixtures

    inputs, declared, files = fixtures.fixture(case)
    producer = source / runtime.PREFIX / name
    runtime.write(target / "inputs.json", inputs)
    runtime.write(target / "retained-corpus.json", declared)
    saved = runtime.read(producer / "inputs.json")
    if saved != inputs:
        raise ValueError("Producer inputs differ from the original retained corpus")
    return inputs, declared, files, producer


def fresh_references(inputs, producer, target):
    from validation.betse import betse_ecm_requested_increment_reference as reference

    captured = {}

    def retain(name, payload):
        runtime.write(target / (name + ".json"), payload)
        captured[name] = payload

    first = reference.evaluate(inputs, refinement=1, retain=retain)
    second = reference.evaluate(inputs, refinement=2, retain=retain)
    comparisons = {}
    for precision, projection in ((100, first), (160, second)):
        raw_name = "raw-decimal-" + str(precision)
        projected_name = "projected-reference-" + str(precision)
        reference.validate_payload(captured[raw_name], projection)
        comparisons[raw_name] = captured[raw_name] == runtime.read(producer / (raw_name + ".json"))
        comparisons[projected_name] = reference.encode(projection) == reference.encode(
            runtime.read(producer / (projected_name + ".json"))
        )
    runtime.write(target / "complete-producer-reference-identity.json", comparisons)
    assert all(comparisons.values())
    return first, second


def native_worker(source, case, target):
    import numpy as np

    from validation.betse import betse_ecm_requested_increment_checks as checks
    from validation.betse import betse_ecm_transport_native as native

    inputs, declared, files, producer = context(source, case, case, target)
    proof = native.evaluate(inputs)
    runtime.write(target / "complete-native-proof.json", checks.plain(proof))
    with (target / "complete-native-proof.npz").open("xb") as stream:
        np.savez_compressed(stream, **checks.array_leaves(proof))
        stream.flush()
        os.fsync(stream.fileno())
    observed = checks.columns(proof["history"], ledgers=False)
    comparisons = {
        "fresh_native_to_original_native": checks.exact_columns(
            observed, checks.retained_columns(files["actual_native_arrays"], "native")
        ),
        "fresh_native_to_producer_actual": checks.exact_columns(
            observed,
            {
                name: value
                for name, value in runtime.read(producer / "actual-columns.json").items()
                if ".ledger." not in name
            },
        ),
        "fresh_native_to_producer_native": checks.exact_columns(
            observed, runtime.read(producer / "native-columns.json")
        ),
        "producer_actual_to_original_actual": checks.exact_columns(
            runtime.read(producer / "actual-columns.json"),
            checks.retained_columns(files["actual_native_arrays"], "actual"),
        ),
    }
    runtime.write(target / "native-byte-identity.json", comparisons)
    assert proof["failure"] is None and not proof["warnings"] and proof["RNG_unchanged"]
    assert checks.metadata(proof["history"]) == declared["frame_metadata"]
    assert all(report["all_exact"] for report in comparisons.values())
    runtime.write(
        target / "result.json",
        dict(
            status="passed_native_byte_identity",
            complete_native_columns=len(observed),
            source_calls=len(proof["history"]),
            original_panel_status="failed_39_of_40",
            physical_conservation_claim=False,
        ),
    )


def reference_worker(source, case, target):
    from validation.betse import betse_ecm_requested_increment_checks as checks

    inputs, declared, files, producer = context(source, case, case, target)
    first, second = fresh_references(inputs, producer, target)
    actual = runtime.read(producer / "actual-history.json")
    report = checks.increment_report(
        checks.requested(actual),
        checks.requested(first["history"]),
        checks.requested(second["history"]),
    )
    legacy = {
        "producer_actual_to_original": checks.exact_columns(
            runtime.read(producer / "actual-columns.json"),
            checks.retained_columns(files["actual_native_arrays"], "actual"),
        ),
        "reference_100_to_original": checks.exact_columns(
            checks.columns(first["history"]),
            checks.retained_columns(files["reference_arrays"], "reference"),
        ),
        "reference_160_to_original": checks.exact_columns(
            checks.columns(second["history"]),
            checks.retained_columns(files["reference_arrays"], "refined"),
        ),
    }
    meaning = checks.semantics(inputs, actual)
    runtime.write(target / "legacy-byte-identity.json", legacy)
    runtime.write(target / "requested-increment-comparison.json", report)
    runtime.write(target / "requested-increment-semantics.json", meaning)
    assert len(actual) == declared["source_calls"]
    assert all(item["all_exact"] for item in legacy.values())
    checks.assert_increment(report)
    checks.assert_semantics(meaning)
    runtime.write(
        target / "result.json",
        dict(
            status="passed_isolated_requested_increment",
            complete_decimal_precisions=[100, 160],
            maximum_error_over_fixed_budget=report["maximum_error_over_budget"],
            maximum_reference_resolution=report["maximum_reference_resolution"],
            original_panel_status="failed_39_of_40",
            physical_conservation_claim=False,
        ),
    )


def corruption_worker(source, case, target):
    from validation.betse import betse_ecm_requested_increment_checks as checks
    from validation.betse import betse_ecm_requested_increment_reference as reference

    original_case = {
        "stationary-nonzero": "stationary",
        "clipped-raw-lag": "bulk_clipping",
    }.get(case, "signed_environment")
    inputs, _, _, producer = context(source, "corruption-" + case, original_case, target)
    first, second = fresh_references(inputs, producer, target)
    actual = runtime.read(producer / "actual-history.json")
    saved = runtime.read(producer / "corruption.json")
    corrupted = checks.corrupt_requested(inputs, actual, case)
    runtime.write(
        target / "complete-corruption.json",
        dict(case=case, original=checks.requested(actual), corrupted=corrupted),
    )
    valid = checks.increment_report(
        checks.requested(actual),
        checks.requested(first["history"]),
        checks.requested(second["history"]),
    )
    invalid = checks.increment_report(
        corrupted, checks.requested(first["history"]), checks.requested(second["history"])
    )
    runtime.write(target / "valid-comparison.json", valid)
    runtime.write(target / "corrupt-comparison.json", invalid)
    assert reference.encode(saved["original"]) == reference.encode(checks.requested(actual))
    assert reference.encode(saved["corrupted"]) == reference.encode(corrupted)
    checks.assert_increment(valid)
    assert invalid["maximum_error_over_budget"] > 1
    try:
        checks.assert_increment(invalid)
    except AssertionError:
        pass
    else:
        raise AssertionError("Corrupted requested increment was accepted")
    runtime.write(target / "result.json", dict(status="correctly_rejected", corruption=case))


def callback_worker(source, target):
    from decimal import Decimal

    from validation.betse import betse_ecm_requested_increment_reference as reference
    from validation.betse import betse_ecm_transport_reference as original

    inputs, _, _, producer = context(source, "callback", "signed_environment", target)
    captured = []

    def observer(raw):
        payload = dict(
            kind=reference.RAW_KIND,
            precision_digits=100,
            counts=reference.counts(raw),
            payload=reference.encode(raw),
        )
        runtime.write(target / "raw-decimal-100.json", payload)
        captured.append(payload)
        raw["history"][0]["candidate"]["cell_mol_m3"][0][0] = Decimal("-999")
        raw.clear()

    projected = original.evaluate(inputs, retain_decimal=observer)
    runtime.write(target / "projected-reference-100.json", projected)
    assert len(captured) == 1
    reference.validate_payload(captured[0], projected)
    assert captured[0] == runtime.read(producer / "raw-decimal-100.json")
    assert reference.encode(projected) == reference.encode(
        runtime.read(producer / "projected-reference-100.json")
    )
    runtime.write(target / "result.json", dict(status="observer_copy_isolated"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", required=True, choices=("native", "reference", "corruption", "callback")
    )
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    runtime.guard(args.mode)
    from validation.betse import betse_ecm_requested_increment_fixtures as fixtures

    if (
        (args.mode in ("native", "reference") and args.case not in fixtures.CASES)
        or (args.mode == "corruption" and args.case not in fixtures.CORRUPTION_CASES)
        or (args.mode == "callback" and args.case != "callback")
    ):
        raise ValueError("Undeclared fresh worker unit")
    target = runtime.root("fresh-" + args.mode + "-" + args.case)
    runtime.write(
        target / "unit.json", dict(mode=args.mode, case=args.case, source=str(args.source))
    )
    try:
        if args.mode == "native":
            native_worker(args.source, args.case, target)
        elif args.mode == "reference":
            reference_worker(args.source, args.case, target)
        elif args.mode == "corruption":
            corruption_worker(args.source, args.case, target)
        else:
            callback_worker(args.source, target)
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
