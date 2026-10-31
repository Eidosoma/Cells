"""Software checks for lossless owner capture; no native simulation is run."""

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_initialization as handoff
from cells.processes import betse_normal_ion_join as ions


@pytest.mark.parametrize(
    "bits",
    (
        "0000000000000000",  # positive zero
        "0000000000000080",  # negative zero
        "000000000000f43f",  # 1.25
        "0100000000000000",  # smallest positive subnormal
        "ffffffffffffef7f",  # largest finite value
        "010000000000f87f",  # quiet NaN payload; copying is not domain admission
    ),
)
def test_capture_preserves_native_float64_type_and_bits(bits):
    original = np.frombuffer(bytes.fromhex(bits), dtype="<f8")[0]
    captured = handoff._copy({"nested": [original]})["nested"][0]
    assert type(captured) is type(original) is np.float64
    assert captured.tobytes() == original.tobytes()


@pytest.mark.parametrize(
    "original",
    (np.bool_(True), np.int64(1), np.uint64(1), np.float32(1), np.complex128(1), np.str_("x")),
)
def test_unrepresentable_scalar_is_explicitly_uncaptured(original):
    with pytest.raises(ValueError, match="other scalar dtypes are unsupported"):
        handoff._copy(original)
    entry = handoff._entry({"held": original}, "held")
    assert entry["present"] is True and entry["captured"] is False
    assert "value" not in entry
    assert entry["type"] == type(original).__name__


def test_owner_cache_keeps_distinct_scalar_identity_and_detached_arrays():
    native = np.float64(-0.0)
    original = {"scalar": native, "python": -0.0, "array": np.array([1.0, 2.0])}
    captured = handoff._copy(original)
    assert ions.digest(captured) == ions.digest(original)
    assert ions.digest(captured) != ions.digest({**original, "scalar": float(native)})
    assert type(captured["scalar"]) is np.float64
    assert type(captured["python"]) is float
    assert not captured["array"].flags.writeable
    original["array"][0] = 9.0
    np.testing.assert_array_equal(captured["array"], [1.0, 2.0])
