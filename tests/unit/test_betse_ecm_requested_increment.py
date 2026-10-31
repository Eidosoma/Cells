"""Prospective junction operand; original raw-lag acceptance is unchanged."""

import os
import struct
import traceback
from copy import deepcopy
from decimal import Decimal

import numpy as np
import pytest

from cells.processes import betse_ecm_transport as transport
from validation.betse import betse_ecm_requested_increment_checks as checks
from validation.betse import betse_ecm_requested_increment_fixtures as fixtures
from validation.betse import betse_ecm_requested_increment_reference as reference
from validation.betse import betse_ecm_requested_increment_runtime as runtime
from validation.betse import betse_ecm_transport_native as native
from validation.betse import betse_ecm_transport_reference as source_reference


def persist(root, name, value):
    """Retain complete returned/failed objects and every typed NumPy array."""
    runtime.write(root / (name + ".json"), checks.plain(value))
    with (root / (name + ".npz")).open("xb") as stream:
        np.savez_compressed(stream, **checks.array_leaves(value))
        stream.flush()
        os.fsync(stream.fileno())


def run(inputs, root):
    binding = parent = forcing = None
    try:
        binding = transport.bind(inputs["definition"])
        persist(root, "binding", binding)
        parent = transport.state(binding, inputs["initial"])
        persist(root, "initial-state", parent)
        rows = []
        for step, packet in enumerate(inputs["steps"]):
            forcing = transport.drive(binding, packet)
            trial = transport.step(binding, parent, forcing)
            persist(root, "actual-step-" + str(step), trial)
            rows.append(trial)
            parent = trial.candidate
        return binding, rows
    except BaseException as error:
        if (trial := getattr(error, "trial", None)) is not None:
            persist(root, "failed-trial", trial)
        persist(root, "failed-parent-drive", dict(parent=parent, drive=forcing))
        runtime.write(
            root / "failure.json",
            dict(type=type(error).__name__, reason=str(error), traceback=traceback.format_exc()),
        )
        raise


def history(rows):
    return [
        dict(
            frames=checks.plain(row.frames),
            environment_records=checks.plain(row.environment_records),
            candidate=checks.plain(row.candidate.values),
            ledgers=checks.plain(row.diagnostics),
        )
        for row in rows
    ]


def references(inputs, root):
    retained = {}

    def retain(name, payload):
        runtime.write(root / (name + ".json"), payload)
        retained[name] = payload

    first = reference.evaluate(inputs, refinement=1, retain=retain)
    second = reference.evaluate(inputs, refinement=2, retain=retain)
    return first, second, retained


def start(case, name):
    inputs, row, files = fixtures.fixture(case)
    root = runtime.root(name)
    runtime.write(root / "inputs.json", inputs)
    runtime.write(root / "retained-corpus.json", row)
    return inputs, row, files, root


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_requested_increment_and_unchanged_legacy_history(case):
    inputs, declared, files, root = start(case, case)
    before = deepcopy(inputs)
    binding, actual = run(inputs, root)
    actual_history = history(actual)
    runtime.write(root / "actual-history.json", actual_history)
    runtime.write(root / "actual-columns.json", checks.described(checks.columns(actual)))
    proof = native.evaluate(inputs)
    persist(root, "native-proof", proof)
    runtime.write(
        root / "native-columns.json",
        checks.described(checks.columns(proof["history"], ledgers=False)),
    )
    first, second, retained = references(inputs, root)
    comparisons = {
        "actual_legacy_to_retained": checks.exact_columns(
            checks.columns(actual), checks.retained_columns(files["actual_native_arrays"], "actual")
        ),
        "actual_to_native": checks.exact_columns(
            checks.columns(actual, ledgers=False), checks.columns(proof["history"], ledgers=False)
        ),
        "native_to_retained": checks.exact_columns(
            checks.columns(proof["history"], ledgers=False),
            checks.retained_columns(files["actual_native_arrays"], "native"),
        ),
        "reference_100_legacy_to_retained": checks.exact_columns(
            checks.columns(first["history"]),
            checks.retained_columns(files["reference_arrays"], "reference"),
        ),
        "reference_160_legacy_to_retained": checks.exact_columns(
            checks.columns(second["history"]),
            checks.retained_columns(files["reference_arrays"], "refined"),
        ),
    }
    increment = checks.increment_report(
        checks.requested(actual),
        checks.requested(first["history"]),
        checks.requested(second["history"]),
    )
    meaning = checks.semantics(inputs, actual)
    runtime.write(root / "legacy-byte-comparisons.json", comparisons)
    runtime.write(root / "requested-increment-comparison.json", increment)
    runtime.write(root / "requested-increment-semantics.json", meaning)
    assert inputs == before
    assert len(actual) == declared["source_calls"]
    assert (
        checks.metadata(actual) == checks.metadata(proof["history"]) == declared["frame_metadata"]
    )
    assert checks.metadata(first["history"]) == checks.metadata(second["history"])
    assert checks.metadata(actual) == checks.metadata(first["history"])
    assert proof["failure"] is None and not proof["warnings"] and proof["RNG_unchanged"]
    assert all(report["all_exact"] for report in comparisons.values())
    assert (
        proof["native_source_sha256"]
        == fixtures.read(native.PROTOCOL)["native_source"]["source_sha256"]
    )
    for precision, result in ((100, first), (160, second)):
        reference.validate_payload(retained["raw-decimal-" + str(precision)], result)
    checks.assert_increment(increment)
    checks.assert_semantics(meaning)
    original = fixtures.read(files["metadata"])
    if "original_binding_identity" in original:
        assert binding.identity == original["original_binding_identity"]
        assert [row.parent_identity for row in actual] == original["parent_identities"]
        assert [row.candidate.identity for row in actual] == original["candidate_identities"]
    for row in actual:
        assert (
            row.diagnostics["finite"] and not row.diagnostics["physical_material_or_energy_parity"]
        )
        quantity = row.diagnostics[reference.KEY]
        assert quantity.shape == row.candidate.values.cell_mol_m3.shape
        with pytest.raises(ValueError):
            quantity.setflags(write=True)
    if case == "bulk_clipping":
        assert any(value > 0 for row in actual for value in row.diagnostics["clipping_added_mol"])
    runtime.write(
        root / "result.json",
        dict(
            status="passed_prospective_requested_increment",
            source_calls=len(actual),
            legacy_columns=comparisons["actual_legacy_to_retained"]["columns"],
            native_columns=comparisons["actual_to_native"]["columns"],
            maximum_error_over_fixed_budget=increment["maximum_error_over_budget"],
            maximum_reference_resolution=increment["maximum_reference_resolution"],
            original_panel_status="failed_39_of_40",
            original_raw_lag_assertion_reclassified=False,
            trial_identity_may_change_with_added_diagnostic=True,
            physical_conservation_or_energy_claim=False,
        ),
    )


@pytest.mark.parametrize("case", fixtures.CORRUPTION_CASES)
def test_requested_increment_checker_rejects_corruption(case):
    original_case = {
        "stationary-nonzero": "stationary",
        "clipped-raw-lag": "bulk_clipping",
    }.get(case, "signed_environment")
    inputs, _, _, root = start(original_case, "corruption-" + case)
    _, actual = run(inputs, root)
    saved_history = history(actual)
    runtime.write(root / "actual-history.json", saved_history)
    first, second, _ = references(inputs, root)
    valid = checks.requested(actual)
    corrupted = checks.corrupt_requested(inputs, saved_history, case)
    runtime.write(
        root / "corruption.json",
        dict(case=case, original=valid, corrupted=corrupted, source_case=original_case),
    )
    valid_report = checks.increment_report(
        valid, checks.requested(first["history"]), checks.requested(second["history"])
    )
    corrupt_report = checks.increment_report(
        corrupted, checks.requested(first["history"]), checks.requested(second["history"])
    )
    runtime.write(root / "valid-comparison.json", valid_report)
    runtime.write(root / "corrupt-comparison.json", corrupt_report)
    checks.assert_increment(valid_report)
    assert corrupt_report["maximum_error_over_budget"] > 1
    with pytest.raises(AssertionError):
        checks.assert_increment(corrupt_report)
    runtime.write(root / "result.json", dict(status="correctly_rejected", corruption=case))


def test_complete_decimal_codec_preserves_digits_types_and_binary64_bits():
    root = runtime.root("codec")
    original = {
        "type": "mapping",
        "items": [
            Decimal("-0E-199"),
            Decimal("1." + "2345678901" * 16),
            Decimal("9.87654321E-400"),
            (0.0, -0.0, float.fromhex("0x1.0000000000001p-1000")),
        ],
        "empty": {},
        "tuple": (),
        "flags": [True, None, "decimal", 100],
    }
    encoded = reference.encode(original)
    runtime.write(root / "complete-raw.json", encoded)
    decoded = reference.decode(encoded)
    assert reference.encode(decoded) == encoded
    assert [value.as_tuple() for value in decoded["items"][:3]] == [
        value.as_tuple() for value in original["items"][:3]
    ]
    assert all(
        struct.pack(">d", a) == struct.pack(">d", b)
        for a, b in zip(decoded["items"][3], original["items"][3], strict=True)
    )
    assert type(decoded["items"][3]) is tuple and type(decoded["items"]) is list
    runtime.write(root / "result.json", dict(status="exact_round_trip"))


def test_raw_decimal_callback_cannot_mutate_the_returned_reference():
    inputs, _, _, root = start("signed_environment", "callback")
    captured = []

    def observer(raw):
        payload = dict(
            kind=reference.RAW_KIND,
            precision_digits=100,
            counts=reference.counts(raw),
            payload=reference.encode(raw),
        )
        runtime.write(root / "raw-decimal-100.json", payload)
        captured.append(payload)
        raw["history"][0]["candidate"]["cell_mol_m3"][0][0] = Decimal("-999")
        raw.clear()

    projected = source_reference.evaluate(inputs, retain_decimal=observer)
    runtime.write(root / "projected-reference-100.json", projected)
    assert len(captured) == 1
    reference.validate_payload(captured[0], projected)
    runtime.write(root / "result.json", dict(status="observer_copy_isolated"))
