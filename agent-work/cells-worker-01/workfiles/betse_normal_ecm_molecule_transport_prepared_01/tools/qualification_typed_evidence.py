"""Bounded, NumPy-free verification of saved numeric qualification archives.

This reads completed evidence only. It evaluates no physical model and assigns
no scientific acceptance. Deliberately incomplete JSON is admitted only through
the explicit three-case raw-writer software contract.
"""

import ast
import hashlib
import itertools
import json
import math
import re
import struct
import zipfile
from pathlib import Path

MAX_BYTES = 16 * 2**20
FAILURE_BITS = {
    "nan": "7ff8000000000000",
    "inf": "7ff0000000000000",
    "negative-inf": "fff0000000000000",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), "JSON must be a regular unlinked file")
    require(path.stat().st_size <= MAX_BYTES, "JSON size bound")

    def invalid(value):
        raise ValueError("Nonstandard JSON constant: " + value)

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    return json.loads(path.read_text(), parse_constant=invalid, object_pairs_hook=pairs)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def archive_arrays(path):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), "Archive must be a regular unlinked file")
    require(path.stat().st_size <= MAX_BYTES, "Compressed archive size bound")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(0 < len(entries) <= 4096, "Archive member count bound")
        require(sum(row.file_size for row in entries) <= MAX_BYTES, "Expanded archive size bound")
        require(len({row.filename for row in entries}) == len(entries), "Duplicate archive member")
        result = {}
        for row in entries:
            name = row.filename
            require(name.endswith(".npy") and not row.is_dir(), "Only NPY archive members")
            key = name[:-4]
            parts = key.split("/")
            require(
                parts[0] == "root" and all(p not in ("", ".", "..") for p in parts),
                "Noncanonical array owner path",
            )
            result[key] = archive.read(row)
        return result


def array_header(data):
    require(len(data) >= 10 and data[:6] == b"\x93NUMPY", "Invalid NPY magic")
    require(data[6:8] in (b"\x01\x00", b"\x02\x00", b"\x03\x00"), "Unsupported NPY version")
    width = 2 if data[6] == 1 else 4
    require(len(data) >= 8 + width, "Truncated NPY header")
    length = int.from_bytes(data[8 : 8 + width], "little")
    offset = 8 + width + length
    require(0 < length <= 16384 and offset <= len(data), "NPY header size bound")
    header = ast.literal_eval(
        data[8 + width : offset].decode("utf-8" if data[6] == 3 else "latin1")
    )
    require(
        type(header) is dict and set(header) == {"descr", "shape", "fortran_order"},
        "NPY header fields",
    )
    dtype, shape, order = header["descr"], header["shape"], header["fortran_order"]
    require(
        type(dtype) is str and re.fullmatch(r"[<>=|][biuf][1248]", dtype),
        "Plain numeric dtype required",
    )
    formats = {
        ("b", 1): "?",
        ("i", 1): "b",
        ("u", 1): "B",
        ("i", 2): "h",
        ("u", 2): "H",
        ("i", 4): "i",
        ("u", 4): "I",
        ("i", 8): "q",
        ("u", 8): "Q",
        ("f", 4): "f",
        ("f", 8): "d",
    }
    kind, size = dtype[1], int(dtype[2:])
    require((kind, size) in formats, "Unsupported numeric dtype width")
    require(
        type(shape) is tuple
        and len(shape) <= 16
        and all(type(n) is int and 0 <= n <= 2**21 for n in shape),
        "NPY shape bound",
    )
    require(type(order) is bool, "NPY order type")
    count = math.prod(shape)
    require(count <= 2**21 and len(data) - offset == count * size, "NPY data extent")
    return dict(
        dtype=dtype,
        shape=shape,
        fortran=order,
        offset=offset,
        count=count,
        size=size,
        kind=kind,
        fmt=(dtype[0] if dtype[0] in "<>=" else "=") + formats[kind, size],
    )


def array_matches(data, value, *, descriptor=None, allow_nonfinite=False):
    header = array_header(data)
    if descriptor is not None:
        require(
            descriptor
            == dict(array=descriptor["array"], dtype=header["dtype"], shape=list(header["shape"])),
            "Raw array descriptor differs",
        )

    def scalar(item):
        if header["kind"] == "b":
            require(type(item) is bool, "Boolean scalar type")
        elif header["kind"] in "iu":
            require(type(item) is int, "Integer scalar type")
        else:
            if allow_nonfinite and type(item) is dict:
                require(
                    set(item) == {"binary64_bits_hex", "nonfinite"}, "Nonfinite scalar descriptor"
                )
                bits = item["binary64_bits_hex"]
                require(type(bits) is str and re.fullmatch(r"[0-9a-f]{16}", bits), "Binary64 bits")
                decoded = struct.unpack(">d", bytes.fromhex(bits))[0]
                require(
                    not math.isfinite(decoded) and item["nonfinite"] == decoded.hex(),
                    "Expected a nonfinite software scalar",
                )
                item = decoded
            else:
                require(type(item) in (int, float) and math.isfinite(item), "Finite float scalar")
        return item

    def shape_check(item, depth=0):
        if depth == len(header["shape"]):
            scalar(item)
            return
        require(
            type(item) is list and len(item) == header["shape"][depth], "JSON/NPY shape differs"
        )
        for child in item:
            shape_check(child, depth + 1)

    shape_check(value)
    dims = tuple(reversed(header["shape"])) if header["fortran"] else header["shape"]
    for index, coordinates in enumerate(itertools.product(*(range(n) for n in dims))):
        item = value
        for coordinate in reversed(coordinates) if header["fortran"] else coordinates:
            item = item[coordinate]
        begin = header["offset"] + index * header["size"]
        require(
            data[begin : begin + header["size"]] == struct.pack(header["fmt"], scalar(item)),
            "JSON/NPY numeric bytes differ",
        )
    return header["count"]


def bind_legacy(path):
    """Bind every legacy named array to its full, strict JSON representation."""
    path = Path(path)
    primary = read_json(path)
    arrays = archive_arrays(path.with_suffix(".npz"))
    count = 0
    for name, data in arrays.items():
        value = primary
        for part in name.split("/")[1:]:
            if type(value) is list:
                require(
                    part.isascii() and part.isdigit() and str(int(part)) == part,
                    "Noncanonical sequence owner",
                )
                value = value[int(part)]
            else:
                require(type(value) is dict and part in value, "Unknown array owner")
                value = value[part]
        count += array_matches(data, value)
    return dict(
        primary_sha256=digest(path),
        archive_sha256=digest(path.with_suffix(".npz")),
        arrays=len(arrays),
        scalars=count,
        mode="legacy_strict_JSON",
    )


def bind_raw(path, *, failed_capture=None):
    """Bind raw metadata/arrays, with a tightly scoped expected failure mode."""
    path = Path(path)
    raw_path, archive_path = path.with_suffix(".raw.json"), path.with_suffix(".npz")
    raw = read_json(raw_path)
    require(
        set(raw) == {"kind", "typed_arrays", "value"}
        and raw["kind"] == "cells.active_polygon_raw_return@1",
        "Raw metadata schema",
    )
    require(raw["typed_arrays"] == archive_path.name, "Raw archive ownership")
    arrays = archive_arrays(archive_path)
    if failed_capture is not None:
        require(
            failed_capture in FAILURE_BITS
            and path.name == failed_capture + ".json"
            and path.parent.name == "raw-write-contract",
            "Undeclared incomplete JSON",
        )
        try:
            read_json(path)
        except json.JSONDecodeError:
            pass
        else:
            raise ValueError("Expected the preserved strict-JSON serialization failure")
        marker = dict(
            binary64_bits_hex=FAILURE_BITS[failed_capture],
            nonfinite="-inf" if failed_capture == "negative-inf" else failed_capture,
        )
        require(raw["value"]["scalar"] == marker, "Expected nonfinite scalar bits")
        require(set(raw["value"]) == {"values", "scalar"}, "Failure capture fields")
        require(
            raw["value"]["values"] == dict(array="root/values", dtype="<f8", shape=[2]),
            "Failure array metadata",
        )
        require(set(arrays) == {"root/values"}, "Failure array owner")
        count = array_matches(
            arrays["root/values"],
            [1.0, marker],
            descriptor=raw["value"]["values"],
            allow_nonfinite=True,
        )
    else:
        primary = read_json(path)
        used, count = set(), 0

        def visit(tree, value, trail="root"):
            nonlocal count
            if type(tree) is dict and set(tree) == {"array", "dtype", "shape"}:
                require(
                    tree["array"] == trail and trail in arrays and trail not in used,
                    "Raw array path/ownership",
                )
                used.add(trail)
                count += array_matches(arrays[trail], value, descriptor=tree)
            elif type(tree) is dict:
                if type(value) is list:
                    require(len(tree) == len(value), "Named tuple extent")
                    pairs = zip(tree.items(), value, strict=True)
                else:
                    require(
                        type(value) is dict and set(tree) == set(value), "Raw mapping structure"
                    )
                    pairs = ((item, value[item[0]]) for item in tree.items())
                for (key, child), actual in pairs:
                    visit(child, actual, trail + "/" + key.replace("~", "~0").replace("/", "~1"))
            elif type(tree) is list:
                require(type(value) is list and len(tree) == len(value), "Raw sequence structure")
                for index, (child, actual) in enumerate(zip(tree, value, strict=True)):
                    visit(child, actual, trail + "/" + str(index))
            else:
                require(type(tree) is type(value) and tree == value, "Raw scalar differs")

        visit(raw["value"], primary)
        require(used == set(arrays), "Unowned raw arrays")
    return dict(
        primary_sha256=digest(path),
        raw_sha256=digest(raw_path),
        archive_sha256=digest(archive_path),
        arrays=len(arrays),
        scalars=count,
        mode="expected_software_serialization_failure" if failed_capture else "raw_strict_JSON",
    )
