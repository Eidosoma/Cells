"""Strict numeric-only saved artifacts, with no array/simulator dependency.

NPY v1 decoding follows the established D096 format contract. Physics is not
imported from the producer, its reference solver or its comparison helpers.
"""

import ast
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read(path):
    return json.loads(
        Path(path).read_text(),
        object_pairs_hook=unique,
        parse_constant=lambda _: require(False, "Nonfinite JSON constant"),
    )


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def flatten(value):
    if isinstance(value, list):
        for v in value:
            yield from flatten(v)
    else:
        yield value


def decode_npy(raw):
    require(raw[:8] == b"\x93NUMPY\x01\x00" and len(raw) >= 10, "NPY version/length")
    size = struct.unpack("<H", raw[8:10])[0]
    require(0 < size <= 4096 and len(raw) >= 10 + size, "NPY header length")
    header = ast.literal_eval(raw[10 : 10 + size].decode("ascii"))
    require(
        set(header) == {"descr", "shape", "fortran_order"}
        and type(header["fortran_order"]) is bool,
        "NPY header/layout",
    )
    shape, dtype = header["shape"], header["descr"]
    require(
        type(shape) is tuple
        and all(type(n) is int and 0 <= n <= 1000000 for n in shape)
        and math.prod(shape) <= 1000000,
        "NPY extent",
    )
    require(dtype in ("<f8", "<i8", "|b1"), "NPY dtype")
    width, code = (1, "B") if dtype == "|b1" else (8, "d" if dtype == "<f8" else "q")
    payload = raw[10 + size :]
    require(len(payload) == width * math.prod(shape), "NPY payload length")
    values = [v[0] for v in struct.iter_unpack("<" + code, payload)]
    require(all(math.isfinite(v) for v in values), "Nonfinite saved array")
    if dtype == "|b1":
        require(all(v in (0, 1) for v in values), "Noncanonical boolean")
        values = list(map(bool, values))
    strides = [
        math.prod(shape[:i] if header["fortran_order"] else shape[i + 1 :])
        for i in range(len(shape))
    ]

    def nested(axis, offset):
        if axis == len(shape):
            return values[offset]
        return [nested(axis + 1, offset + i * strides[axis]) for i in range(shape[axis])]

    return {"dtype": dtype, "shape": list(shape), "values": nested(0, 0)}


def decode_npz(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(
            len(names) == len(set(names))
            and all(n.endswith(".npy") and "/" not in n for n in names),
            "NPZ membership",
        )
        require(sum(v.file_size for v in archive.infolist()) <= 64 * 1024**2, "NPZ decode budget")
        return {n[:-4]: decode_npy(archive.read(n)) for n in names}


def near(actual, expected, *, atol=0.0, rtol=128 * 2.220446049250313e-16):
    a, b = list(flatten(actual)), list(flatten(expected))
    require(len(a) == len(b), "Numeric comparison extent")
    require(all(math.isfinite(v) for v in (*a, *b)), "Nonfinite comparison")
    require(
        all(abs(x - y) <= atol + rtol * max(1.0, abs(y)) for x, y in zip(a, b, strict=True)),
        "Independent numeric mismatch",
    )
