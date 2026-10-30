"""Immutable typed snapshots of native numeric and ragged mesh caches.

Object arrays are traversed element by element. Their pointer bytes are never
used as evidence or serialized, and no pickle is needed to restore values.
"""

import hashlib
import json
import math
import struct
from dataclasses import dataclass

import numpy as np

from cells.processes import betse_environment_field as arrays

MAX_ARRAY_ELEMENTS = 262144
MAX_TREE_NODES = 262144
MAX_TREE_DEPTH = 32


@dataclass(frozen=True, slots=True)
class CacheColumn:
    name: str
    values: object


@dataclass(frozen=True, slots=True)
class Cache:
    descriptor_json: str
    columns: tuple
    all_finite: bool
    identity: str

    @property
    def descriptor(self):
        return json.loads(self.descriptor_json)

    def numeric_columns(self):
        return {column.name: column.values for column in self.columns}


def layout(value):
    return dict(
        dtype=value.dtype.str,
        shape=list(value.shape),
        strides_bytes=list(value.strides),
        C_contiguous=bool(value.flags.c_contiguous),
        F_contiguous=bool(value.flags.f_contiguous),
    )


def snapshot(value):
    columns, finite, count = [], True, 0

    def visit(item, depth=0):
        nonlocal count, finite
        count += 1
        if depth > MAX_TREE_DEPTH or count > MAX_TREE_NODES:
            raise ValueError("Mesh cache exceeds bounded tree admission")
        if isinstance(item, np.ndarray):
            if item.size > MAX_ARRAY_ELEMENTS:
                raise ValueError("Mesh cache exceeds bounded array admission")
            source = layout(item)
            if item.dtype.hasobject:
                return dict(
                    kind="object_array",
                    source_layout=source,
                    items=[visit(v, depth + 1) for v in item.flat],
                )
            if item.dtype.kind not in "biufc":
                raise ValueError("Unsupported mesh cache array dtype")
            finite = bool(np.isfinite(item).all()) and finite
            name = f"column_{len(columns):05d}"
            owned = arrays.frozen(item)
            columns.append(CacheColumn(name, owned))
            return dict(
                kind="numeric_array",
                source_layout=source,
                column=name,
                sha256=hashlib.sha256(owned.tobytes()).hexdigest(),
            )
        if isinstance(item, np.generic):
            raw = np.asarray(item)
            if raw.dtype.kind not in "biufc":
                raise ValueError("Unsupported mesh cache scalar dtype")
            finite = bool(np.isfinite(raw)) and finite
            return dict(kind="numpy_scalar", dtype=raw.dtype.str, bits=raw.tobytes().hex())
        if type(item) is float:
            finite = math.isfinite(item) and finite
            return dict(kind="float", bits=struct.pack("<d", item).hex())
        if item is None or type(item) in (str, int, bool):
            return dict(kind=type(item).__name__, value=item)
        if isinstance(item, dict):
            return dict(
                kind="dict",
                items=[[visit(k, depth + 1), visit(v, depth + 1)] for k, v in item.items()],
            )
        if isinstance(item, (list, tuple, set, frozenset)):
            # Preserve native set enumeration; no topology sorting is introduced.
            return dict(kind=type(item).__name__, items=[visit(v, depth + 1) for v in item])
        raise ValueError("Unsupported mesh cache member type: " + type(item).__name__)

    descriptor = json.dumps(visit(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    identity = hashlib.sha256(descriptor.encode()).hexdigest()
    return Cache(descriptor, tuple(columns), finite, identity)


def validate(cache):
    if type(cache) is not Cache:
        raise ValueError("Require the complete typed mesh cache")
    if hashlib.sha256(cache.descriptor_json.encode()).hexdigest() != cache.identity:
        raise ValueError("Changed typed mesh cache descriptor")
    columns = cache.numeric_columns()
    seen, all_finite = set(), True

    def check(node):
        nonlocal all_finite
        if node["kind"] == "numeric_array":
            name = node["column"]
            seen.add(name)
            value = columns[name]
            source = node["source_layout"]
            if (
                value.dtype.str != source["dtype"]
                or list(value.shape) != source["shape"]
                or value.flags.writeable
                or hashlib.sha256(value.tobytes()).hexdigest() != node["sha256"]
            ):
                raise ValueError("Changed owned mesh cache column")
            all_finite = bool(np.isfinite(value).all()) and all_finite
        elif node["kind"] == "numpy_scalar":
            value = np.frombuffer(bytes.fromhex(node["bits"]), dtype=np.dtype(node["dtype"]))
            all_finite = bool(np.isfinite(value).all()) and all_finite
        elif node["kind"] == "float":
            all_finite = (
                math.isfinite(struct.unpack("<d", bytes.fromhex(node["bits"]))[0]) and all_finite
            )
        elif node["kind"] == "dict":
            for key, value in node["items"]:
                check(key)
                check(value)
        elif "items" in node:
            for value in node["items"]:
                check(value)

    check(cache.descriptor)
    if seen != set(columns) or len(columns) != len(cache.columns) or all_finite != cache.all_finite:
        raise ValueError("Missing or duplicated mesh cache columns")
    return cache


def plain(cache):
    """Fresh inspection values; this does not recreate a mutable native mesh."""
    validate(cache)
    columns = cache.numeric_columns()

    def decode(node):
        kind = node["kind"]
        if kind == "numeric_array":
            return columns[node["column"]].tolist()
        if kind == "numpy_scalar":
            return np.frombuffer(bytes.fromhex(node["bits"]), dtype=np.dtype(node["dtype"]))[
                0
            ].item()
        if kind == "float":
            return struct.unpack("<d", bytes.fromhex(node["bits"]))[0]
        if kind == "dict":
            return {decode(key): decode(value) for key, value in node["items"]}
        if kind == "object_array":
            shape = node["source_layout"]["shape"]
            items = [decode(v) for v in node["items"]]

            def reshape(start, remaining):
                if not remaining:
                    return items[start]
                width = math.prod(remaining[1:])
                return [reshape(start + i * width, remaining[1:]) for i in range(remaining[0])]

            return reshape(0, shape)
        if "items" in node:
            return [decode(v) for v in node["items"]]
        return node["value"]

    return decode(cache.descriptor)
