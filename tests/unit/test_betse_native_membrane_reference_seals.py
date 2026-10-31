"""Match the pinned serialization functions without constructing a simulator."""

import ast
import struct
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_current as source_serializer
from validation.betse import betse_native_membrane_initialization_archive as archive
from validation.betse import betse_native_membrane_initialization_reference as reference


@pytest.fixture(scope="module")
def bridge_record():
    # Execute the actual record function only. Importing the complete bridge
    # would unnecessarily load unrelated simulation layers for a byte test.
    path = Path(source_serializer.__file__).with_name("betse_native_membrane_initialization.py")
    tree = ast.parse(path.read_bytes())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "record")
    namespace = dict(np=np, Mapping=Mapping, fields=fields, is_dataclass=is_dataclass)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["record"]


def decoded(value):
    return reference.decode_python_floats(archive.snapshot(value))


@pytest.mark.parametrize("legacy", (False, True))
@pytest.mark.parametrize(
    "bits",
    (
        "0000000000000000",  # Positive zero.
        "0000000000000080",  # Negative zero.
        "0100000000000000",  # Smallest positive subnormal.
        "0100000000000080",
        "ffffffffffffef7f",  # Largest finite binary64.
        "2d431cebe2361a3f",
        "000000000000f07f",  # Infinity is retainable metadata, not physical admission.
        "000000000000f0ff",
        "010000000000f87f",  # Quiet NaN payload.
        "010000000000f07f",  # Signalling NaN payload.
    ),
)
def test_python_float_seals_match_actual_source_serializer(bits, legacy):
    value = struct.unpack("<d", bytes.fromhex(bits))[0]
    restored = decoded(value)
    assert struct.pack("<d", restored).hex() == bits
    assert reference.digest(restored, legacy=legacy) == source_serializer._digest(value)


@pytest.mark.parametrize("value", (np.float64(0.0), np.float64(-0.0), np.float64(1e-4)))
def test_numpy_scalar_legacy_and_bridge_seals_remain_distinct(value, bridge_record):
    restored = decoded(value)
    assert reference.digest(restored, legacy=True) == source_serializer._digest(value)
    assert reference.digest(restored) == source_serializer._digest(bridge_record(value))
    assert reference.digest(restored) != reference.digest(restored, legacy=True)


@pytest.mark.parametrize("value", (np.float64("inf"), np.float64("-inf"), np.float64("nan")))
def test_legacy_numpy_nonfinite_json_still_refused(value, bridge_record):
    with pytest.raises(ValueError):
        source_serializer._digest(value)
    with pytest.raises(ValueError):
        reference.digest(decoded(value), legacy=True)
    # The bridge's typed scalar tag is lossless metadata, as in the actual source.
    assert reference.digest(decoded(value)) == source_serializer._digest(bridge_record(value))


@pytest.mark.parametrize("dtype", ("<f8", ">f8", "<i8", "|b1"))
@pytest.mark.parametrize("legacy", (False, True))
def test_complete_array_schema_and_logical_bytes_match(dtype, legacy):
    value = np.array([[0, 1], [2, 3]], dtype=dtype)[:, ::-1]
    assert reference.digest(decoded(value), legacy=legacy) == source_serializer._digest(value)


def test_nested_python_and_numpy_floats_match_each_seal_family(bridge_record):
    value = {"python": [-0.0, 310.0], "numpy": np.float64(1e-4), "flags": [True, None, 4]}
    restored = decoded(value)
    assert reference.digest(restored, legacy=True) == source_serializer._digest(value)
    assert reference.digest(restored) == source_serializer._digest(bridge_record(value))


def test_indexed_owners_retain_integer_keys(bridge_record):
    value = {4: {"dt": -0.0}, 2: {"dt": 1e-4}}
    restored = decoded(value)
    assert reference.digest(restored) == source_serializer._digest(bridge_record(value))


def test_structured_boundary_metadata_uses_actual_bridge_record(bridge_record):
    @dataclass
    class Metadata:
        dt: float
        raw: bytes

    value = Metadata(-0.0, b"\x00\xff")
    assert reference.digest(decoded(value)) == source_serializer._digest(bridge_record(value))


def test_signed_zero_and_changed_array_bits_are_not_equal_seals():
    assert reference.digest(decoded(0.0)) != reference.digest(decoded(-0.0))
    first = np.array([0.0, 1.0], dtype="<f8")
    second = np.array([-0.0, 1.0], dtype="<f8")
    assert reference.digest(decoded(first)) != reference.digest(decoded(second))


@pytest.mark.parametrize(
    "tag",
    (
        {"float64_bits": "00"},
        {"float64_bits": "00" * 9},
        {"float64_bits": "G" * 16},
        {"float64_bits": "F" * 16},
        {"float64_bits": 0},
        {"float64_bits": "00" * 8, "extra": True},
    ),
)
def test_malformed_float_tags_remain_refused(tag):
    with pytest.raises(ValueError):
        reference.decode_python_floats({"nested": [tag]})
