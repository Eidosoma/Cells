"""Representation checks only: no solver, physics or reference equations."""

import io
import json
import struct
import zipfile

import numpy as np
import pytest

from validation.geometry import qualification_typed_evidence as evidence
from validation.geometry.active_polygon_physiology_runtime import write as raw_write


def npy(array, version=(1, 0)):
    output = io.BytesIO()
    np.lib.format.write_array(output, array, version=version, allow_pickle=False)
    return output.getvalue()


@pytest.mark.parametrize(
    "dtype",
    [
        "?",
        "i1",
        "u1",
        "<i2",
        ">i2",
        "<i4",
        ">i4",
        "<u4",
        ">u4",
        "<i8",
        ">i8",
        "<u8",
        ">u8",
        "<f4",
        ">f4",
        "<f8",
        ">f8",
    ],
)
@pytest.mark.parametrize("order", ["C", "F"])
def test_exact_dtype_shape_and_order(dtype, order):
    array = np.array([[0, 1, 2], [3, 4, 5]], dtype=dtype, order=order)
    assert evidence.array_matches(npy(array), array.tolist()) == 6


@pytest.mark.parametrize(
    "array", [np.asarray(-0.0), np.empty((2, 0), dtype="f8"), np.asarray([[2**63 + 7]], dtype="u8")]
)
@pytest.mark.parametrize("version", [(1, 0), (2, 0), (3, 0)])
def test_scalar_empty_and_integer_precision(array, version):
    assert evidence.array_matches(npy(array, version), array.tolist()) == array.size


def test_changed_zero_sign_and_shape_refused():
    with pytest.raises(ValueError, match="numeric bytes"):
        evidence.array_matches(npy(np.asarray([-0.0])), [0.0])
    with pytest.raises(ValueError, match="shape differs"):
        evidence.array_matches(npy(np.asarray([[1.0]])), [1.0])


@pytest.mark.parametrize("mutation", ["truncated", "trailing", "version", "object", "structured"])
def test_bad_array_refused(mutation):
    data = npy(np.asarray([1.0]))
    if mutation == "truncated":
        data = data[:-1]
    elif mutation == "trailing":
        data += b"0"
    elif mutation == "version":
        data = data[:6] + b"\x04\x00" + data[8:]
    elif mutation == "object":
        data = data.replace(b"'<f8'", b"'|O8'")
    else:
        output = io.BytesIO()
        np.lib.format.write_array(output, np.asarray([(1,)], dtype=[("x", "i4")]))
        data = output.getvalue()
    with pytest.raises(ValueError):
        evidence.array_matches(data, [1.0])


def test_legacy_full_binding_and_changed_owner(tmp_path):
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(dict(state=dict(values=[[1.0, -0.0]]), gates=[dict(value=True)])))
    np.savez_compressed(
        path.with_suffix(".npz"),
        **{"root/state/values": np.asarray([[1.0, -0.0]]), "root/gates/0/value": np.asarray(True)},
    )
    result = evidence.bind_legacy(path)
    assert (result["arrays"], result["scalars"]) == (2, 3)
    value = json.loads(path.read_text())
    value["state"]["values"][0][0] = 2.0
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="numeric bytes"):
        evidence.bind_legacy(path)


@pytest.mark.parametrize(
    "owner", ["root/missing", "root/../values", "root//values", "wrong/values"]
)
def test_legacy_owner_escape_and_unknown_refused(tmp_path, owner):
    path = tmp_path / "capture.json"
    path.write_text('{"values":[1.0]}')
    np.savez_compressed(path.with_suffix(".npz"), **{owner: np.asarray([1.0])})
    with pytest.raises(ValueError):
        evidence.bind_legacy(path)


def test_duplicate_member_and_symlink_refused(tmp_path):
    path = tmp_path / "capture.npz"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("root/values.npy", npy(np.asarray([1.0])))
        with pytest.warns(UserWarning, match="Duplicate"):
            archive.writestr("root/values.npy", npy(np.asarray([2.0])))
    with pytest.raises(ValueError, match="Duplicate"):
        evidence.archive_arrays(path)
    link = tmp_path / "link.npz"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="unlinked"):
        evidence.archive_arrays(link)


def test_raw_success_binds_metadata_values_and_dtype(tmp_path):
    path = tmp_path / "capture.json"
    raw_write(path, dict(values=np.asarray([1.0, -0.0]), gate=np.asarray(True)))
    assert evidence.bind_raw(path)["scalars"] == 3
    raw_path = path.with_suffix(".raw.json")
    raw = json.loads(raw_path.read_text())
    raw["value"]["values"]["dtype"] = ">f8"
    raw_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="descriptor"):
        evidence.bind_raw(path)


@pytest.mark.parametrize("label", ["nan", "inf", "negative-inf"])
def test_explicit_expected_raw_failure_has_bound_payload(tmp_path, label):
    folder = tmp_path / "raw-write-contract"
    folder.mkdir()
    path = folder / (label + ".json")
    invalid = struct.unpack(">d", bytes.fromhex(evidence.FAILURE_BITS[label]))[0]
    with pytest.raises(ValueError):
        raw_write(path, dict(values=np.asarray([1.0, invalid]), scalar=invalid))
    result = evidence.bind_raw(path, failed_capture=label)
    assert result["mode"] == "expected_software_serialization_failure"
    with pytest.raises(json.JSONDecodeError):
        evidence.bind_raw(path)
    path.write_text("{}")
    with pytest.raises(ValueError, match="serialization failure"):
        evidence.bind_raw(path, failed_capture=label)


def test_failed_capture_wrong_path_or_corrupted_payload_refused(tmp_path):
    path = tmp_path / "nan.json"
    with pytest.raises(ValueError):
        raw_write(path, dict(values=np.asarray([1.0, float("nan")]), scalar=float("nan")))
    with pytest.raises(ValueError, match="Undeclared"):
        evidence.bind_raw(path, failed_capture="nan")
    folder = tmp_path / "raw-write-contract"
    folder.mkdir()
    for suffix in (".json", ".raw.json", ".npz"):
        path.with_suffix(suffix).rename((folder / "nan.json").with_suffix(suffix))
    path = folder / "nan.json"
    np.savez_compressed(
        path.with_suffix(".npz"), **{"root/values": np.asarray([2.0, float("nan")])}
    )
    with pytest.raises(ValueError, match="numeric bytes"):
        evidence.bind_raw(path, failed_capture="nan")


@pytest.mark.parametrize("content", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_nonstandard_or_ambiguous_json_refused(tmp_path, content):
    path = tmp_path / "invalid.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        evidence.read_json(path)
