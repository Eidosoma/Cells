"""Read NumPy's .npy and .npz files with the standard library only.

The run adapter must not import numpy (or the engine), so it reads a run's records
itself. A .npz is a zip of .npy members; a .npy is a short header (a Python dict literal
giving the element type, the order and the shape) followed by the raw values.

Only what saved Cells runs use is supported: little-endian or single-byte numbers and
booleans, and little-endian fixed-width Unicode text ('<U<n>', as the engine's relationship
tables write their string ids), in C order. The vesicle adapter can also request column-major arrays in row-major order. Anything else, text in another byte order
included, raises ``ValueError`` and says what it met.
"""

from __future__ import annotations

import ast
import struct
import sys
import zipfile
from array import array
from itertools import product
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
    """A saved array: its NumPy type, its shape and its values as one flat ``array`` (numbers
    and booleans) or one flat list of ``str`` (text), in C order."""

    def __init__(self, descr, shape, values):
        self.descr = descr
        self.shape = tuple(shape)
        self.values = values

    @property
    def boolean(self):
        return self.descr == "|b1"

    @property
    def text(self):
        return self.descr[1:2] == "U"

    def __repr__(self):
        return f"Array({self.descr}, shape={self.shape})"


def read_npy(raw, name="array", *, allow_fortran=False):
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
    if header.get("fortran_order") and not allow_fortran:
        raise ValueError(f"{name}: Fortran order is not supported")
    descr, shape = header["descr"], tuple(header["shape"])
    if isinstance(descr, str) and descr[1:2] == "U":
        parsed = _read_text(raw[start + length :], descr, shape, name)
        return _row_major(parsed, header.get("fortran_order"))
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
    return _row_major(Array(descr, shape, values), header.get("fortran_order"))


def _row_major(parsed, fortran):
    if fortran and len(parsed.shape) > 1:
        strides = [prod(parsed.shape[:i]) for i in range(len(parsed.shape))]
        indices = product(*(range(n) for n in parsed.shape))
        values = parsed.values
        ordered = (values[sum(i * stride for i, stride in zip(index, strides))] for index in indices)
        parsed.values = array(values.typecode, ordered) if isinstance(values, array) else list(ordered)
    return parsed


def _read_text(body, descr, shape, name):
    """Fixed-width Unicode text, '<U<n>': n code points per element, each four bytes of UTF-32
    little-endian, padded with NUL code points, which are dropped from the end as NumPy drops
    them. Any other byte order ('>U', '|U', '=U') is refused, never misread."""
    width = descr[2:]
    if descr[0] != "<" or not width.isdigit():
        raise ValueError(f"{name}: element type {descr} is not supported (text is read as little-endian '<U' only)")
    size = 4 * int(width)
    count = prod(shape)
    data = body[: count * size]
    if len(data) != count * size:
        raise ValueError(f"{name}: the file is shorter than its shape {shape} says")
    try:
        values = [data[k * size : (k + 1) * size].decode("utf-32-le").rstrip("\x00") for k in range(count)]
    except UnicodeDecodeError as error:
        raise ValueError(f"{name}: an element is not UTF-32 text ({error.reason})") from None
    return Array(descr, shape, values)


def read_npz(path, names=None, *, allow_fortran=False):
    """{name: Array} for the members of a .npz file (all of them, or only ``names``)."""
    out = {}
    with zipfile.ZipFile(path) as archive:
        members = {info.filename[:-4]: info for info in archive.infolist() if info.filename.endswith(".npy")}
        for name in members if names is None else names:
            if name not in members:
                raise ValueError(f"{path}: no array called {name}")
            out[name] = read_npy(archive.read(members[name]), name, allow_fortran=allow_fortran)
    return out


HEADER_LIMIT = 65536  # a .npy header longer than this is not read (a package is untrusted input)
MEMBER_LIMIT = 65536  # nor a .npz of more members than this


def npy_header(stream, name="array", size=None):
    """The element type and shape of one .npy file, from its header alone: (descr, shape). ``stream`` is a binary file
    at the file's start; only the header is read, never the values. Where the file's length is given (``size``), a file
    shorter than its shape says is refused, as ``read_npy`` would refuse it."""
    lead = stream.read(10)
    if len(lead) < 10 or lead[:6] != MAGIC:
        raise ValueError(f"{name}: not a .npy file")
    major = lead[6]
    if major == 1:
        (length,) = struct.unpack("<H", lead[8:10])
        start = 10
    elif major in (2, 3):
        more = stream.read(2)
        if len(more) < 2:
            raise ValueError(f"{name}: not a .npy file")
        (length,) = struct.unpack("<I", lead[8:10] + more)
        start = 12
    else:
        raise ValueError(f"{name}: .npy version {major} is not supported")
    if length > HEADER_LIMIT:
        raise ValueError(f"{name}: its header is {length} bytes, more than {HEADER_LIMIT}")
    text = stream.read(length)
    if len(text) != length:
        raise ValueError(f"{name}: the file ends inside its header")
    try:
        header = ast.literal_eval(text.decode("utf-8" if major == 3 else "latin1"))
    except (ValueError, SyntaxError, UnicodeDecodeError, MemoryError, RecursionError):
        raise ValueError(f"{name}: its header is not a dict of NumPy's format") from None
    descr = header.get("descr") if isinstance(header, dict) else None
    shape = header.get("shape") if isinstance(header, dict) else None
    if not (isinstance(descr, str) and isinstance(shape, tuple) and all(type(n) is int and n >= 0 for n in shape)):
        raise ValueError(f"{name}: its header gives no element type and shape")
    if header.get("fortran_order"):
        raise ValueError(f"{name}: Fortran order is not supported")
    if descr[1:2] == "U":
        if descr[0] != "<" or not descr[2:].isdigit():
            raise ValueError(f"{name}: element type {descr} is not supported (text is read as little-endian '<U' only)")
        item = 4 * int(descr[2:])
    elif descr in CODES:
        item = array(CODES[descr]).itemsize
    else:
        raise ValueError(f"{name}: element type {descr} is not supported")
    if size is not None and size < start + length + prod(shape) * item:
        raise ValueError(f"{name}: the file is shorter than its shape {shape} says")
    return descr, shape


def npz_headers(path):
    """{name: (descr, shape)} for every .npy member of a .npz file, each from its header alone: no array is
    decompressed past its header, so a large file costs no more to check than a small one."""
    out = {}
    with zipfile.ZipFile(path) as archive:
        members = [info for info in archive.infolist() if info.filename.endswith(".npy")]
        if len(members) > MEMBER_LIMIT:
            raise ValueError(f"more than {MEMBER_LIMIT} arrays")
        for info in members:
            with archive.open(info) as stream:
                out[info.filename[:-4]] = npy_header(stream, info.filename[:-4], info.file_size)
    return out
