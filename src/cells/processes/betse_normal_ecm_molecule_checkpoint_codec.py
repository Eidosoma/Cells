"""Lossless, bounded record/NPZ adapter for molecule run checkpoints only.

Uses the existing Cells JSON/fsync helpers and NumPy's non-pickle archive format.
Unlike the diagnostic raw writer, scalar/0D and container categories survive.
No setup, scientific bind/replay, dynamic import from data or RNG draw occurs.
"""

import ast
import hashlib
import io
import json
import math
import os
import re
import struct
import zipfile
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from cells.core.specs import digest
from cells.physiology_checkpoint import _sync_directory, _write_json
from cells.processes.betse_normal_ecm_molecule_checkpoint_records import registry

KIND = "cells.ordinary_ecm_molecule_checkpoint_graph@1"
ARRAY_KEY = re.compile(r"a[0-9]{8}")


@dataclass(frozen=True)
class Limits:
    json_bytes: int = 16 * 2**20
    archive_bytes: int = 64 * 2**20
    expanded_bytes: int = 64 * 2**20
    nodes: int = 200_000
    arrays: int = 8192
    depth: int = 128
    dimensions: int = 8
    elements: int = 8 * 2**20
    string_bytes: int = 2**20
    header_bytes: int = 16384

    def check(self):
        for name, maximum in vars(Limits()).items():
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= maximum:
                raise ValueError("Checkpoint limit may only narrow the fixed bound: " + name)
        return self


DEFAULT_LIMITS = Limits()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def parse_json(data, limits):
    require(len(data) <= limits.json_bytes, "Checkpoint JSON bound exceeded")

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate checkpoint JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("Nonstandard checkpoint JSON scalar: " + value)

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


class Encoder:
    def __init__(self, limits=DEFAULT_LIMITS):
        self.limits = limits.check()
        self.records = registry()
        self.by_class = {cls: (name, fields) for name, (cls, fields) in self.records.items()}
        self.nodes, self.arrays, self.seen, self.active = [], {}, {}, set()
        self.original_arrays = []
        self.bytes = 0

    def encode(self, value, depth=0):
        require(depth <= self.limits.depth, "Checkpoint graph depth bound")
        kind = type(value)
        if value is None:
            return ["none"]
        if kind is bool:
            return ["bool", value]
        if kind is int:
            require(value.bit_length() <= 256, "Checkpoint integer bound")
            return ["int", str(value)]
        if kind is str:
            require(len(value.encode()) <= self.limits.string_bytes, "Checkpoint string bound")
            return ["str", value]
        if kind is float:
            return ["float", struct.pack("<d", value).hex()]
        ident = id(value)
        require(ident not in self.active, "Cyclic runtime state is not owned")
        if ident in self.seen:
            return ["ref", self.seen[ident]]
        index = len(self.nodes)
        require(index < self.limits.nodes, "Checkpoint graph node bound")
        self.seen[ident] = index
        self.nodes.append(None)
        self.active.add(ident)
        if kind is np.ndarray or isinstance(value, np.generic):
            array = np.asarray(value)
            require(
                array.dtype.kind in "biuf" and array.dtype.itemsize in (1, 2, 4, 8),
                "Unowned/object/extended numeric dtype",
            )
            require(
                array.ndim <= self.limits.dimensions and array.size <= self.limits.elements,
                "Checkpoint array shape bound",
            )
            require(
                array.flags.c_contiguous or array.flags.f_contiguous,
                "Noncontiguous runtime views are not owned checkpoint buffers",
            )
            if kind is np.ndarray and array.flags.writeable:
                require(array.base is None, "Writable runtime views have unowned aliasing")
                require(
                    not any(np.shares_memory(array, prior) for prior in self.original_arrays),
                    "Writable runtime array alias is not owned",
                )
            else:
                require(
                    not any(
                        prior.flags.writeable and np.shares_memory(array, prior)
                        for prior in self.original_arrays
                    ),
                    "Unowned mutable array alias",
                )
            self.bytes += array.nbytes
            require(self.bytes <= self.limits.expanded_bytes, "Checkpoint numeric byte bound")
            require(len(self.arrays) < self.limits.arrays, "Checkpoint array count bound")
            key = f"a{len(self.arrays):08d}"
            fortran = bool(array.flags.f_contiguous and not array.flags.c_contiguous)
            self.arrays[key] = np.array(array, copy=True, order="F" if fortran else "C")
            self.original_arrays.append(array)
            node = dict(
                tag="array" if kind is np.ndarray else "scalar",
                key=key,
                dtype=array.dtype.str,
                shape=list(array.shape),
                fortran=fortran,
                writable=bool(array.flags.writeable) if kind is np.ndarray else False,
            )
        elif kind in self.by_class:
            name, fields = self.by_class[kind]
            node = dict(
                tag="record",
                type=name,
                fields=[[f, self.encode(getattr(value, f), depth + 1)] for f in fields],
            )
        elif kind in (dict, MappingProxyType):
            node = dict(
                tag="mapping",
                proxy=kind is MappingProxyType,
                items=[
                    [self.encode(k, depth + 1), self.encode(v, depth + 1)] for k, v in value.items()
                ],
            )
        elif kind in (list, tuple):
            node = dict(
                tag="list" if kind is list else "tuple",
                items=[self.encode(v, depth + 1) for v in value],
            )
        else:
            raise ValueError(
                "Missing ownership/codec for runtime type: "
                + kind.__module__
                + "."
                + kind.__qualname__
            )
        self.nodes[index] = node
        self.active.remove(ident)
        return ["ref", index]

    def capture(self, value):
        root = self.encode(value)
        tree = dict(kind=KIND, root=root, nodes=self.nodes)
        require(len(json_bytes(tree)) <= self.limits.json_bytes, "Checkpoint tree byte bound")
        return tree

    def seal(self, tree):
        return digest(
            dict(
                tree=tree,
                arrays={
                    key: dict(
                        dtype=a.dtype.str,
                        shape=list(a.shape),
                        sha256=hashlib.sha256(
                            a.tobytes(
                                order="F"
                                if a.flags.f_contiguous and not a.flags.c_contiguous
                                else "C"
                            )
                        ).hexdigest(),
                    )
                    for key, a in self.arrays.items()
                },
            )
        )

    def write(self, directory, tree):
        _write_json(directory / "state.json", tree)
        require(
            (directory / "state.json").stat().st_size <= self.limits.json_bytes,
            "Checkpoint written JSON byte bound",
        )
        with (directory / "arrays.npz").open("xb") as stream:
            np.savez(stream, allow_pickle=False, **self.arrays)
            stream.flush()
            os.fsync(stream.fileno())
        require(
            (directory / "arrays.npz").stat().st_size <= self.limits.archive_bytes,
            "Checkpoint archive byte bound",
        )
        _sync_directory(directory)


def fingerprint(value, limits=DEFAULT_LIMITS):
    encoder = Encoder(limits)
    tree = encoder.capture(value)
    return encoder.seal(tree)


def _headers(data, limits):
    require(22 <= len(data) <= limits.archive_bytes, "Checkpoint archive byte bound")
    end = struct.unpack("<4s4H2IH", data[-22:])
    require(
        end[0] == b"PK\x05\x06"
        and end[1] == end[2] == end[7] == 0
        and end[3] == end[4] <= limits.arrays
        and end[4] != 65535
        and end[5] + end[6] == len(data) - 22,
        "Noncanonical/oversized ZIP directory",
    )
    headers, total = {}, 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        require(len(archive.infolist()) == end[4], "Checkpoint ZIP count differs")
        for item in archive.infolist():
            key = item.filename.removesuffix(".npy")
            require(
                item.filename == key + ".npy"
                and ARRAY_KEY.fullmatch(key)
                and key not in headers
                and item.compress_type == zipfile.ZIP_STORED
                and not item.flag_bits & 1,
                "Duplicate/unsafe/compressed checkpoint member",
            )
            total += item.file_size
            require(
                total <= limits.expanded_bytes and item.file_size >= 10,
                "Checkpoint expanded byte bound",
            )
            with archive.open(item) as stream:
                magic = stream.read(8)
                require(
                    magic[:6] == b"\x93NUMPY"
                    and magic[6:] in (b"\x01\x00", b"\x02\x00", b"\x03\x00"),
                    "Checkpoint NPY magic",
                )
                width = 2 if magic[6] == 1 else 4
                raw_length = stream.read(width)
                require(len(raw_length) == width, "Truncated NPY header length")
                length = int.from_bytes(raw_length, "little")
                require(
                    0 < length <= limits.header_bytes and length + 8 + width <= item.file_size,
                    "Checkpoint NPY header bound",
                )
                header = ast.literal_eval(
                    stream.read(length).decode("utf8" if magic[6] == 3 else "latin1")
                )
            require(
                type(header) is dict and set(header) == {"descr", "shape", "fortran_order"},
                "Checkpoint NPY fields",
            )
            dtype, shape, order = header["descr"], header["shape"], header["fortran_order"]
            require(
                type(dtype) is str
                and re.fullmatch(r"[<>=|][biuf][1248]", dtype)
                and type(shape) is tuple
                and len(shape) <= limits.dimensions
                and all(type(n) is int and 0 <= n <= limits.elements for n in shape)
                and type(order) is bool,
                "Unsafe checkpoint dtype/shape",
            )
            count = math.prod(shape)
            require(
                count <= limits.elements
                and 8 + width + length + count * np.dtype(dtype).itemsize == item.file_size,
                "Checkpoint NPY payload/shape mismatch",
            )
            headers[key] = dict(dtype=np.dtype(dtype).str, shape=list(shape), fortran=order)
    return headers


def decode(tree, archive_data, limits=DEFAULT_LIMITS):
    limits.check()
    require(
        type(tree) is dict
        and set(tree) == {"kind", "root", "nodes"}
        and tree["kind"] == KIND
        and type(tree["nodes"]) is list
        and len(tree["nodes"]) <= limits.nodes,
        "Incomplete checkpoint graph",
    )
    headers = _headers(archive_data, limits)
    records, nodes = registry(), tree["nodes"]
    done, active, used = {}, set(), set()
    with np.load(
        io.BytesIO(archive_data), allow_pickle=False, max_header_size=limits.header_bytes
    ) as arrays:

        def atom(value, depth=0):
            require(
                depth <= limits.depth and type(value) is list and value,
                "Checkpoint graph atom/depth",
            )
            tag = value[0]
            if tag == "none":
                require(len(value) == 1, "Noncanonical null")
                return None
            require(len(value) == 2, "Noncanonical checkpoint atom")
            v = value[1]
            if tag == "bool":
                require(type(v) is bool, "Noncanonical bool")
                return v
            if tag == "int":
                require(
                    type(v) is str and len(v) <= 79 and re.fullmatch(r"0|-?[1-9][0-9]*", v),
                    "Noncanonical integer",
                )
                result = int(v)
                require(result.bit_length() <= 256, "Checkpoint integer bound")
                return result
            if tag == "str":
                require(
                    type(v) is str and len(v.encode()) <= limits.string_bytes,
                    "Checkpoint string bound",
                )
                return v
            if tag == "float":
                require(type(v) is str and re.fullmatch("[0-9a-f]{16}", v), "Checkpoint float bits")
                return struct.unpack("<d", bytes.fromhex(v))[0]
            require(
                tag == "ref" and type(v) is int and 0 <= v < len(nodes),
                "Checkpoint reference bounds",
            )
            require(v not in active, "Cyclic checkpoint graph")
            if v in done:
                return done[v]
            active.add(v)
            n = nodes[v]
            require(type(n) is dict and type(n.get("tag")) is str, "Checkpoint node schema")
            kind = n["tag"]
            if kind in ("array", "scalar"):
                require(
                    set(n) == {"tag", "key", "dtype", "shape", "fortran", "writable"}
                    and type(n["key"]) is str
                    and n["key"] in headers
                    and n["key"] not in used
                    and type(n["writable"]) is bool
                    and type(n["fortran"]) is bool
                    and type(n["shape"]) is list
                    and all(type(v) is int for v in n["shape"])
                    and type(n["dtype"]) is str,
                    "Checkpoint array owner schema",
                )
                key = n["key"]
                require(
                    headers[key] == {k: n[k] for k in ("dtype", "shape", "fortran")},
                    "Checkpoint descriptor/header differs",
                )
                array = arrays[key]
                if kind == "scalar":
                    require(
                        n["shape"] == [] and n["writable"] is False, "NumPy scalar category changed"
                    )
                    result = array[()]
                elif n["writable"]:
                    result = np.array(array, copy=True, order="F" if n["fortran"] else "C")
                else:
                    order = "F" if n["fortran"] else "C"
                    result = np.frombuffer(array.tobytes(order=order), dtype=array.dtype).reshape(
                        array.shape, order=order
                    )
                used.add(key)
            elif kind == "record":
                require(
                    set(n) == {"tag", "type", "fields"}
                    and type(n["type"]) is str
                    and n["type"] in records,
                    "Unowned checkpoint record type",
                )
                cls, names = records[n["type"]]
                require(
                    type(n["fields"]) is list
                    and all(type(r) is list and len(r) == 2 for r in n["fields"])
                    and [r[0] for r in n["fields"]] == list(names),
                    "Incomplete checkpoint record fields",
                )
                values = [atom(r[1], depth + 1) for r in n["fields"]]
                result = cls(*values)
            elif kind == "mapping":
                require(
                    set(n) == {"tag", "proxy", "items"}
                    and type(n["proxy"]) is bool
                    and type(n["items"]) is list,
                    "Checkpoint mapping schema",
                )
                result = {}
                for row in n["items"]:
                    require(type(row) is list and len(row) == 2, "Checkpoint mapping row")
                    key = atom(row[0], depth + 1)
                    require(
                        type(key) in (str, int, bool, float, type(None)) or type(key) is tuple,
                        "Unowned mapping key",
                    )
                    require(key not in result, "Duplicate checkpoint mapping key")
                    result[key] = atom(row[1], depth + 1)
                if n["proxy"]:
                    result = MappingProxyType(result)
            else:
                require(
                    kind in ("tuple", "list")
                    and set(n) == {"tag", "items"}
                    and type(n["items"]) is list,
                    "Unowned checkpoint node",
                )
                items = [atom(item, depth + 1) for item in n["items"]]
                result = tuple(items) if kind == "tuple" else items
            active.remove(v)
            done[v] = result
            return result

        result = atom(tree["root"])
    require(len(done) == len(nodes) and used == set(headers), "Unbound checkpoint nodes/arrays")
    return result
