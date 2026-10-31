"""PROSPECTIVE, UNRUN: refusal metadata must survive exact-value serialization."""

import json
import struct
from decimal import Decimal

import pytest

from validation.betse import betse_ecm_reference_failure as capture


def test_decimal_and_binary_nonfinite_bits_are_retained_before_strict_json(tmp_path):
    error = ValueError("Declared ECM sodium domain refusal")
    error.reference_partial = dict(
        stage="channel_kinetics",
        class_name="Nav1p2",
        membrane_index=1,
        completed_population_books=[],
        updated_gates_partial={"m": [Decimal("1e-160")]},
        values_before_failed_gate={"voltage_V": [0.4, float("nan"), float("inf"), -0.0]},
    )
    path = capture.write(
        tmp_path / "reference-1.json",
        input_bytes=b'{"mode":"material"}',
        mode="material",
        refinement=1,
        error=error,
        runtime={"loaded_files": {}},
        available_result=None,
    )
    result = json.loads(path.read_text())
    values = dict(result["partial"]["mapping"])
    leaves = dict(values["values_before_failed_gate"]["mapping"])["voltage_V"]["sequence"]
    assert [item["float64_bits"] for item in leaves] == [
        struct.pack("<d", value).hex() for value in (0.4, float("nan"), float("inf"), -0.0)
    ]
    assert result["primary_result_is_not_accepted"] is True and result["new_reference_forms"] == 0
    assert not (tmp_path / "reference-1.json").exists()


def test_failure_sidecar_is_exclusive(tmp_path):
    arguments = dict(
        input_bytes=b"{}",
        mode="channels",
        refinement=1,
        error=ValueError("domain"),
        runtime={},
        available_result=None,
    )
    path = capture.write(tmp_path / "reference-1.json", **arguments)
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        capture.write(tmp_path / "reference-1.json", **arguments)
    assert path.read_bytes() == original


def test_unsupported_object_is_an_explicit_capture_refusal():
    with pytest.raises(TypeError, match="Unsupported reference-failure"):
        capture.typed(object())


def test_partial_sequence_ownership_is_kept_distinct():
    assert capture.typed((1, 2))["sequence_type"] == "tuple"
    assert capture.typed([1, 2])["sequence_type"] == "list"
