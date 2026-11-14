"""Read NumPy's .npy and .npz files with the standard library only.

The run adapter must not import numpy (or the engine), so it reads a run's records
itself. A .npz is a zip of .npy members; a .npy is a short header (a Python dict literal
giving the element type, the order and the shape) followed by the raw values.

Only what saved Cells runs use is supported: little-endian or single-byte numbers and
booleans, in C order. Anything else raises ``ValueError`` and says what it met.
"""

from __future__ import annotations

import ast
import struct
import sys
import zipfile
from array import array
from math import prod

MAGIC = b"\x93NUMPY"
# NumPy element type -> the standard library's array type code.
CODES = {
    "<f8": "d", "<f4": "f",
    "<i8": "q", "<i4": "i", "<i2": "h", "|i1": "b",
    "<u8": "Q", "<u4": "I", "<u2": "H", "|u1": "B",
    "|b1": "B",
}


class Array:
    """A saved array: its NumPy type, its shape and its values as one flat ``array``."""

    def __init__(self, descr, shape, values):
        self.descr = descr
        self.shape = tuple(shape)
        self.values = values

    @property
    def boolean(self):
        return self.descr == "|b1"

    def __repr__(self):
        return f"Array({self.descr}, shape={self.shape})"


def read_npy(raw, name="array"):
    """Parse the bytes of one .npy file."""
    if raw[:6] != MAGIC:
        raise ValueError(f"{name}: not a .npy file")
    major = raw[6]
    if major == 1:
        (length,) = struct.unpack("<H", raw[8:10])
        start = 10
    elif major in (2, 3):
        (length,) = struct.unpack("<I", raw[8:12])
        start = 12
    else:
        raise ValueError(f"{name}: .npy version {major} is not supported")
    header = ast.literal_eval(raw[start : start + length].decode("utf-8" if major == 3 else "latin1"))
    if header.get("fortran_order"):
        raise ValueError(f"{name}: Fortran order is not supported")
    descr, shape = header["descr"], tuple(header["shape"])
    code = CODES.get(descr)
    if code is None:
        raise ValueError(f"{name}: element type {descr} is not supported")
    values = array(code)
    count = prod(shape)
    data = raw[start + length : start + length + count * values.itemsize]
    if len(data) != count * values.itemsize:
        raise ValueError(f"{name}: the file is shorter than its shape {shape} says")
    values.frombytes(data)
    if sys.byteorder == "big" and values.itemsize > 1:
        values.byteswap()
    return Array(descr, shape, values)


def read_npz(path, names=None):
    """{name: Array} for the members of a .npz file (all of them, or only ``names``)."""
    out = {}
    with zipfile.ZipFile(path) as archive:
        members = {info.filename[:-4]: info for info in archive.infolist() if info.filename.endswith(".npy")}
        for name in members if names is None else names:
            if name not in members:
                raise ValueError(f"{path}: no array called {name}")
            out[name] = read_npy(archive.read(members[name]), name)
    return out
