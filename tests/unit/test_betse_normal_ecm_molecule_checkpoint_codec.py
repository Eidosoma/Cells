"""Bounded software controls for the molecule-only record/NPZ codec."""

import copy
import io
import json
import struct
import zipfile
from dataclasses import replace
from types import MappingProxyType

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_checkpoint_codec as codec


def packed(value):
    encoder = codec.Encoder()
    tree = encoder.capture(value)
    stream = io.BytesIO()
    np.savez(stream, allow_pickle=False, **encoder.arrays)
    return tree, stream.getvalue()


def test_exact_scalar_array_container_and_alias_categories():
    array = np.frombuffer(np.array([1.0, -0.0]).tobytes(), dtype="<f8")
    matrix = np.asfortranarray(np.arange(6.0).reshape(2, 3))
    value = MappingProxyType(
        dict(
            scalar=np.float64(-0.0),
            zero=np.array(-0.0),
            python=-0.0,
            first=array,
            alias=array,
            matrix=matrix,
            sequence=(1, [2, 3]),
            rng_key=np.array([0, 2**32 - 1], dtype="<u4"),
        )
    )
    tree, data = packed(value)
    actual = codec.decode(tree, data)
    assert type(actual) is MappingProxyType
    assert type(actual["scalar"]) is np.float64
    assert type(actual["zero"]) is np.ndarray and actual["zero"].shape == ()
    assert type(actual["python"]) is float
    assert actual["first"] is actual["alias"]
    assert not actual["first"].flags.writeable
    with pytest.raises(ValueError):
        actual["first"].setflags(write=True)
    assert actual["matrix"].flags.f_contiguous and actual["matrix"].flags.writeable
    assert type(actual["sequence"]) is tuple and type(actual["sequence"][1]) is list
    assert codec.fingerprint(actual) == codec.fingerprint(value)


@pytest.mark.parametrize(
    "value", [object(), lambda: None, np.array([object()]), np.random.RandomState(0)]
)
def test_unowned_runtime_object_or_stream_refused(value):
    with pytest.raises(ValueError, match="[Uu]nowned|ownership"):
        codec.Encoder().capture(value)


def test_cyclic_missing_and_unknown_record_nodes_refused():
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="Cyclic"):
        codec.Encoder().capture(cyclic)
    tree, data = packed({"a": 1})
    tree["nodes"][0] = {"tag": "record", "type": "os.system", "fields": []}
    with pytest.raises(ValueError, match="Unowned checkpoint record"):
        codec.decode(tree, data)


def test_duplicate_json_and_reference_depth_limits():
    with pytest.raises(ValueError, match="Duplicate"):
        codec.parse_json(b'{"a":1,"a":2}', codec.DEFAULT_LIMITS)
    with pytest.raises(ValueError, match="depth"):
        codec.Encoder(replace(codec.DEFAULT_LIMITS, depth=1)).capture([[[1]]])
    with pytest.raises(ValueError, match="shape"):
        codec.Encoder(replace(codec.DEFAULT_LIMITS, elements=1)).capture(np.ones(2))
    with pytest.raises(ValueError, match="narrow"):
        replace(codec.DEFAULT_LIMITS, archive_bytes=2**40).check()


def test_crc_truncation_and_misdeclared_array_shapes():
    tree, data = packed(np.array([1.0, 2.0]))
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        codec.decode(tree, data[:-1])
    changed = copy.deepcopy(tree)
    changed["nodes"][0]["shape"] = [200_000_000]
    with pytest.raises(ValueError, match="descriptor/header"):
        codec.decode(changed, data)
    corrupt = bytearray(data)
    offset = corrupt.index(b"\x93NUMPY")
    corrupt[offset + 128] ^= 1
    with pytest.raises(zipfile.BadZipFile, match="CRC"):
        codec.decode(tree, corrupt)


def test_huge_npy_shape_is_rejected_before_array_allocation():
    tree, _ = packed(np.array([1.0]))
    header = repr(dict(descr="<f8", fortran_order=False, shape=(2**40,))).encode()
    header += b" " * ((64 - (10 + len(header) + 1) % 64) % 64) + b"\n"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "a00000000.npy", b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header
        )
    with pytest.raises(ValueError, match="dtype/shape|payload/shape"):
        codec.decode(tree, stream.getvalue())


def test_duplicate_archive_owner_and_unbound_payload_refused():
    tree, data = packed(np.array([1.0]))
    stream = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as origin, zipfile.ZipFile(stream, "w") as target:
        body = origin.read("a00000000.npy")
        target.writestr("a00000000.npy", body)
        target.writestr("a00000001.npy", body)
    with pytest.raises(ValueError, match="Unbound"):
        codec.decode(tree, stream.getvalue())
    tree["nodes"].append(dict(tag="tuple", items=[]))
    with pytest.raises(ValueError, match="Unbound"):
        codec.decode(tree, data)


def test_codec_rejects_noncanonical_metadata_categories():
    tree, data = packed(np.array([1.0]))
    tree["nodes"][0]["fortran"] = 0
    with pytest.raises(ValueError, match="schema"):
        codec.decode(tree, data)
    with pytest.raises(ValueError, match="Nonstandard"):
        codec.parse_json(json.dumps({"value": float("nan")}).encode(), codec.DEFAULT_LIMITS)
