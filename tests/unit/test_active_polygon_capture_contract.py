"""Serialization regressions only; no model or independent equation evaluation."""

import json
import os
import struct
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

import numpy as np
import pytest

from validation.geometry import active_polygon_physiology_runtime as runtime


def test_finite_json_schema_and_typed_buffers_are_preserved(tmp_path):
    pair = namedtuple("Pair", ("left", "right"))
    value = dict(
        state=np.array([[1.5, -0.0], [3.0, 4.0]], dtype=">f8"),
        counter=np.int32(7),
        labels=["one", "two"],
        row=pair(1.0, 2.0),
    )
    expected = (
        json.dumps(value, indent=2, allow_nan=False, default=lambda x: np.asarray(x).tolist())
        + "\n"
    )
    path = tmp_path / "trial.json"
    runtime.write(path, value)
    assert path.read_text() == expected
    raw = json.loads(path.with_suffix(".raw.json").read_text())
    assert raw["value"]["state"] == dict(array="root/state", dtype=">f8", shape=[2, 2])
    with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
        for name, source in (("root/state", value["state"]), ("root/counter", value["counter"])):
            assert archive[name].dtype == np.asarray(source).dtype
            assert archive[name].shape == np.asarray(source).shape
            assert archive[name].tobytes() == np.asarray(source).tobytes()


def test_nonfinite_array_bits_survive_strict_json_failure(tmp_path):
    bits = np.array([0x7FF8000000000021, 0xFFF0000000000000, 0x7FF0000000000000], dtype=np.uint64)
    array = bits.view(np.float64)
    path = tmp_path / "nonfinite.json"
    with pytest.raises(ValueError, match="Out of range float"):
        runtime.write(path, {"full_return": array, "metadata": {"owner": "cell"}})
    raw = json.loads(path.with_suffix(".raw.json").read_text())
    assert raw["value"]["metadata"] == {"owner": "cell"}
    with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
        assert archive["root/full_return"].tobytes() == bits.tobytes()
    assert array.tobytes() == bits.tobytes()


@pytest.mark.parametrize("bits", ["7ff8000000000021", "7ff0000000000000", "fff0000000000000"])
def test_python_nonfinite_scalar_bits_survive_strict_json_failure(tmp_path, bits):
    value = struct.unpack(">d", bytes.fromhex(bits))[0]
    path = tmp_path / "scalar.json"
    with pytest.raises(ValueError, match="Out of range float"):
        runtime.write(path, {"nested": [value]})
    raw = json.loads(path.with_suffix(".raw.json").read_text())
    assert raw["value"]["nested"][0]["binary64_bits_hex"] == bits
    assert raw["typed_arrays"] is None


def test_unserializable_late_value_does_not_erase_numerical_return(tmp_path):
    path = tmp_path / "unsupported.json"
    with pytest.raises(TypeError, match="not JSON serializable"):
        runtime.write(path, {"rates": np.array([1.0, 2.0]), "bad": object()})
    raw = json.loads(path.with_suffix(".raw.json").read_text())
    assert raw["value"]["bad"] == {"unsupported_type": "builtins.object"}
    with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
        assert archive["root/rates"].tobytes() == np.array([1.0, 2.0]).tobytes()


def test_serializer_exception_preserves_raw_return_and_original_error(tmp_path, monkeypatch):
    path = tmp_path / "exception.json"
    original = json.dump

    def fail_only_primary(value, handle, *args, **kwargs):
        if Path(handle.name) == path:
            raise RuntimeError("deliberate primary serialization failure")
        return original(value, handle, *args, **kwargs)

    monkeypatch.setattr(json, "dump", fail_only_primary)
    with pytest.raises(RuntimeError, match="deliberate primary serialization failure"):
        runtime.write(path, {"rates": np.array([1.0, 2.0])})
    assert path.with_suffix(".raw.json").is_file()
    with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
        assert archive["root/rates"].shape == (2,)


@pytest.mark.parametrize("existing", ["primary", "raw", "arrays"])
def test_exclusive_capture_never_overwrites_existing_artifacts(tmp_path, existing):
    path = tmp_path / "once.json"
    old = dict(primary=path, raw=path.with_suffix(".raw.json"), arrays=path.with_suffix(".npz"))[
        existing
    ]
    old.write_bytes(b"retained evidence")
    with pytest.raises(FileExistsError):
        runtime.write(path, {"rates": np.array([1.0, 2.0])})
    assert list(tmp_path.iterdir()) == [old]
    assert old.read_bytes() == b"retained evidence"


def test_guarded_conversion_capture_does_not_import_numpy(tmp_path):
    script = """
import json, pathlib, struct, sys
from validation.geometry import active_polygon_physiology_runtime as runtime
runtime.guard('conversion')
folder = pathlib.Path(sys.argv[1])
runtime.write(folder/'finite.json', {'ratio': {'numerator': '1', 'denominator': '3'}})
bits = '7ff8000000000021'
try:
    runtime.write(folder/'nonfinite.json', {'proof': struct.unpack('>d', bytes.fromhex(bits))[0]})
except ValueError:
    pass
else:
    raise AssertionError('Nonfinite strict JSON was accepted')
assert 'numpy' not in sys.modules and 'cells' not in sys.modules
raw = json.loads((folder/'nonfinite.raw.json').read_text())
assert raw['value']['proof']['binary64_bits_hex'] == bits
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script, str(tmp_path)],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
