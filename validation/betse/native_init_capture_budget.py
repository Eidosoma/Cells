"""Non-expanding budget check before the existing typed archive serializer.

This checks observations, never owners. It does not freeze the input, authorize
its producer, replace the archive, or guarantee that a later capture succeeds.
Callers must keep the input stable; the existing writer must still validate its
actual output. All raw numeric occurrences count toward the unchanged 64/128
MiB budgets, including small inline values. That is deliberately conservative
relative to the sidecar writer's threshold-only accounting.

The supported projection is the archive's plain containers, plain dataclass
instances, canonical namedtuples, exact ndarray and genuine NumPy scalars.
Opaque Mapping/_asdict implementations and custom attribute/iteration hooks
are refused without invoking them. Object arrays are traversed without tolist;
no ndarray tobytes, whole-array byte copy, hex string, or owner serialization
is performed here. Strided buffers are read in bounded logical-C-order blocks.
"""

import collections
import dataclasses
import hashlib
import inspect
import json
import sys
from dataclasses import Field, dataclass
from types import FunctionType, GetSetDescriptorType, MappingProxyType, MemberDescriptorType

from validation.betse import native_seed_demo_evidence as transport
from validation.betse import native_single_cell_prefix_payload as payload

KIND = "cells.native_init_capture_budget@1"
MAX_UNIQUE = 64 * 2**20
MAX_EXPANDED = 128 * 2**20
MAX_BLOB = 16 * 2**20
MAX_METADATA = 64 * 2**20
MAX_NODES = 1048576
MAX_DEPTH = 64
BLOCK_BYTES = 64 * 2**10
_ABSENT = object()
_NAMEDTUPLE_ASDICT = collections.namedtuple("_BudgetTuple", "value")._asdict


class CaptureBudgetRejected(ValueError):
    """A pre-serialization refusal, with bounded plain accounting only."""

    def __init__(self, reason, counts):
        super().__init__(reason)
        self.counts = dict(counts)


def _limits():
    if (payload.MAX_UNIQUE, payload.MAX_EXPANDED, payload.MAX_BLOB, payload.MAX_DEPTH) != (
        MAX_UNIQUE,
        MAX_EXPANDED,
        MAX_BLOB,
        MAX_DEPTH,
    ) or (transport.MAX_METADATA, transport.MAX_NODES) != (MAX_METADATA, MAX_NODES):
        raise ValueError("Existing capture budgets changed")


def _numpy_types():
    module = sys.modules.get("numpy")
    if module is None:
        return None, None
    namespace = vars(module)
    return namespace.get("ndarray"), namespace.get("generic")


def _extent(shape, itemsize):
    """Pure metadata arithmetic, including zero-sized and rank-zero arrays."""
    if (
        type(shape) is not tuple
        or len(shape) > MAX_DEPTH
        or type(itemsize) is not int
        or itemsize < 0
        or any(type(n) is not int or n < 0 for n in shape)
    ):
        raise ValueError("Unsupported array extent metadata")
    elements = 1
    for n in shape:
        elements *= n
    return elements, elements * itemsize


def _array_metadata(value):
    shape, strides, dtype = value.shape, value.strides, value.dtype
    elements, size = _extent(shape, value.itemsize)
    if (
        type(strides) is not tuple
        or len(strides) != len(shape)
        or any(type(n) is not int for n in strides)
        or type(value.nbytes) is not int
        or value.nbytes != size
        or type(dtype.str) is not str
        or type(dtype.kind) is not str
    ):
        raise ValueError("Unsupported array layout metadata")
    return shape, strides, dtype.str, dtype.kind, value.itemsize, elements, size


def _plain_dataclass(value):
    cls = type(value)
    fields = inspect.getattr_static(cls, "__dataclass_fields__", _ABSENT)
    if fields is _ABSENT:
        return None
    if (
        type(cls) is not type
        or type(fields) is not dict
        or cls.__getattribute__ is not object.__getattribute__
    ):
        raise ValueError("Opaque dataclass observation refused")
    result = []
    for field in fields.values():
        # Match dataclasses.fields: InitVar/ClassVar are not serialized.
        if type(field) is not Field:
            raise ValueError("Opaque dataclass field refused")
        if field._field_type is not dataclasses._FIELD:
            continue
        name = field.name
        actual = inspect.getattr_static(value, name, _ABSENT)
        if (
            type(name) is not str
            or actual is _ABSENT
            or (
                hasattr(type(actual), "__get__")
                and type(actual) not in (MemberDescriptorType, GetSetDescriptorType)
            )
        ):
            raise ValueError("Opaque or missing dataclass attribute refused")
        result.append(name)
        if len(result) > MAX_NODES:
            raise ValueError("Dataclass field bound")
    return tuple(result)


def _namedtuple_fields(value):
    cls = type(value)
    function = inspect.getattr_static(cls, "_asdict", _ABSENT)
    if function is _ABSENT:
        return None
    fields = inspect.getattr_static(cls, "_fields", _ABSENT)
    canonical = _NAMEDTUPLE_ASDICT
    closure = (
        tuple(c.cell_contents for c in function.__closure__ or ())
        if type(function) is FunctionType
        else ()
    )
    expected = tuple(c.cell_contents for c in canonical.__closure__ or ())
    if (
        type(cls) is not type
        or cls.__mro__ != (cls, tuple, object)
        or cls.__getattribute__ is not tuple.__getattribute__
        or cls.__iter__ is not tuple.__iter__
        or type(function) is not FunctionType
        or function.__code__ is not canonical.__code__
        or function.__globals__ is not canonical.__globals__
        or function.__defaults__ is not canonical.__defaults__
        or function.__kwdefaults__ is not canonical.__kwdefaults__
        or len(closure) != len(expected)
        or any(a is not b for a, b in zip(closure, expected, strict=True))
        or type(fields) is not tuple
        or len(fields) != len(value)
        or any(type(name) is not str for name in fields)
        or len(set(fields)) != len(fields)
    ):
        raise ValueError("Opaque _asdict observation refused")
    return fields


@dataclass(slots=True)
class _Raw:
    value: object
    metadata: tuple
    size: int
    occurrences: int = 1


def _blocks(raw, array_type):
    """Read exact bytes without ndarray.tobytes or an unbounded conversion."""
    value, metadata = raw.value, raw.metadata
    if _array_metadata(value) != metadata:
        raise ValueError("Array metadata changed before budget read")
    if raw.size == 0:
        return
    view = memoryview(value)
    if view.c_contiguous:
        byte_view = view.cast("B")
        for offset in range(0, raw.size, BLOCK_BYTES):
            yield byte_view[offset : offset + BLOCK_BYTES]
    else:
        if type(value) is not array_type:
            raise ValueError("Opaque strided scalar buffer refused")
        shape, itemsize = metadata[0], metadata[4]
        indices = [0] * (len(shape) - 1)
        rows = 1
        for length in shape[:-1]:
            rows *= length
        width = max(1, BLOCK_BYTES // itemsize)
        for _ in range(rows):
            for offset in range(0, shape[-1], width):
                selected = array_type.__getitem__(
                    value, (*indices, slice(offset, min(shape[-1], offset + width)))
                )
                selected_view = memoryview(selected)
                if selected_view.c_contiguous:
                    byte_view = selected_view.cast("B")
                    for start in range(0, byte_view.nbytes, BLOCK_BYTES):
                        yield byte_view[start : start + BLOCK_BYTES]
                else:
                    if selected_view.nbytes > BLOCK_BYTES:
                        raise ValueError("Bounded strided buffer block required")
                    yield selected_view.tobytes(order="C")
            for index in range(len(indices) - 1, -1, -1):
                indices[index] += 1
                if indices[index] < shape[index]:
                    break
                indices[index] = 0
    if _array_metadata(value) != metadata:
        raise ValueError("Array metadata changed during budget read")


class _Budget:
    def __init__(self):
        self.counts = dict(
            nodes=0,
            metadata_bytes_upper_bound=0,
            raw_occurrences=0,
            raw_expanded_bytes=0,
            raw_unique_bytes=0,
            raw_unique_objects=0,
            raw_unique_contents=0,
            hashed_bytes=0,
        )
        self.active, self.raw = set(), {}
        self.array_type, self.scalar_type = _numpy_types()

    def reject(self, reason):
        raise CaptureBudgetRejected(reason, self.counts)

    def node(self, depth, count=1):
        self.counts["nodes"] += count
        if depth > MAX_DEPTH or self.counts["nodes"] > MAX_NODES:
            self.reject("Typed observation node/depth bound")
        self.metadata((8 + 4 * depth) * count)

    def metadata(self, size):
        self.counts["metadata_bytes_upper_bound"] += size
        if self.counts["metadata_bytes_upper_bound"] > MAX_METADATA:
            self.reject("Typed observation metadata bound")

    def text(self, value):
        self.metadata(2)
        for start in range(0, len(value), 4096):
            self.metadata(len(json.dumps(value[start : start + 4096])) - 2)

    def binary(self, value, metadata, depth):
        size = metadata[-1]
        if size > MAX_BLOB:
            self.reject("Individual raw observation bound")
        self.counts["raw_occurrences"] += 1
        self.counts["raw_expanded_bytes"] += size
        if self.counts["raw_expanded_bytes"] > MAX_EXPANDED:
            self.reject("Expanded raw observation bound")
        self.node(depth)
        self.metadata(200 if size >= payload.THRESHOLD else 2 * size)
        old = self.raw.get(id(value))
        if old is None:
            self.raw[id(value)] = _Raw(value, metadata, size)
            self.counts["raw_unique_objects"] += 1
        else:
            if old.value is not value or old.metadata != metadata:
                self.reject("Repeated raw observation metadata changed")
            old.occurrences += 1

    def mapping(self, pairs, depth):
        self.node(depth)
        for key, value in pairs:
            self.text(key)
            self.walk(value, depth + 1)

    def array(self, value, depth, *, scalar):
        metadata = _array_metadata(value)
        shape, strides, dtype, kind, _, elements, _ = metadata
        if not scalar and kind == "O":
            # Count the list skeleton before reading any object elements.
            count, prefix = 0, 1
            for length in shape:
                count += prefix
                prefix *= length
            if self.counts["nodes"] + count + elements > MAX_NODES:
                self.reject("Object-array observation node bound")
        layout = (
            {"numpy_scalar_dtype": dtype}
            if scalar
            else dict(__ndarray__=True, dtype=dtype, shape=list(shape), strides=list(strides))
        )
        self.mapping(layout.items(), depth)
        if scalar or kind != "O":
            self.text("raw_bytes_hex")
            self.binary(value, metadata, depth + 1)
        else:
            self.text("object_values")
            if shape:
                self.node(depth + len(shape), count)
            for child in value.flat:
                self.walk(child, depth + 1 + len(shape))

    def walk(self, value, depth=0):
        kind = type(value)
        if value is None or kind in (bool, int, str, float, bytes):
            self.node(depth)
            if kind is str:
                self.text(value)
            elif kind is bytes:
                # bytes_hex stays metadata in the existing writer.
                self.node(depth + 1)
                self.metadata(2 * len(value) + 32)
            elif kind is int:
                if value.bit_length() > MAX_METADATA * 4:
                    self.reject("Integer observation metadata bound")
                self.metadata(len(str(value)))
            elif kind is float:
                self.node(depth + 1)
                self.metadata(40)  # archive preserves exact binary64 bits, including NaNs.
            return
        if id(value) in self.active:
            self.reject("Cyclic observation cannot be archived")
        self.active.add(id(value))
        try:
            if self.array_type is not None and kind is self.array_type:
                self.array(value, depth, scalar=False)
            elif (
                self.scalar_type is not None
                and isinstance(value, self.scalar_type)
                and kind.__module__ == "numpy"
                and vars(sys.modules["numpy"]).get(kind.__name__) is kind
            ):
                self.array(value, depth, scalar=True)
            elif kind in (dict, collections.OrderedDict, MappingProxyType):
                if all(type(key) is str for key in value):
                    self.mapping(value.items(), depth)
                else:
                    self.node(depth)
                    self.text("__indexed_items__")
                    self.node(depth + 1)
                    for key, child in value.items():
                        self.node(depth + 2)
                        self.walk(key, depth + 3)
                        self.walk(child, depth + 3)
            elif kind in (tuple, list):
                self.node(depth)
                for child in value:
                    self.walk(child, depth + 1)
            else:
                fields = _plain_dataclass(value)
                if fields is not None:
                    self.mapping(((name, getattr(value, name)) for name in fields), depth)
                    return
                fields = _namedtuple_fields(value)
                if fields is not None:
                    self.mapping(
                        ((name, tuple.__getitem__(value, i)) for i, name in enumerate(fields)),
                        depth,
                    )
                    return
                self.reject("Unsupported or opaque raw observation type: " + kind.__qualname__)
        finally:
            self.active.remove(id(value))

    def finish(self):
        contents = set()
        for raw in self.raw.values():
            digest, count = hashlib.sha256(), 0
            for block in _blocks(raw, self.array_type):
                count += len(block)
                if len(block) > BLOCK_BYTES or count > raw.size:
                    self.reject("Raw budget reader exceeded declared extent")
                digest.update(block)
            if count != raw.size:
                self.reject("Raw budget reader missed declared bytes")
            self.counts["hashed_bytes"] += count
            key = (digest.digest(), count)
            if key not in contents:
                contents.add(key)
                self.counts["raw_unique_contents"] += 1
                self.counts["raw_unique_bytes"] += count
                if self.counts["raw_unique_bytes"] > MAX_UNIQUE:
                    self.reject("Unique raw observation bound")
        return dict(
            kind=KIND,
            completed=True,
            limits=dict(
                raw_unique_bytes=MAX_UNIQUE,
                raw_expanded_bytes=MAX_EXPANDED,
                raw_blob_bytes=MAX_BLOB,
                nodes=MAX_NODES,
                depth=MAX_DEPTH,
                metadata_bytes=MAX_METADATA,
                read_block_bytes=BLOCK_BYTES,
            ),
            counts=dict(self.counts),
            ndarray_tobytes_or_hex_calls=0,
            input_frozen=False,
            actual_writer_validation_required=True,
            owner_or_source_authority=False,
            inline_numeric_bytes_counted_conservatively=True,
        )


def preflight(value):
    """Refuse unsafe expansion, then hash bounded buffers for unique-byte cost.

    Structural/expanded-size failures happen before any numeric buffer read.
    A unique-content decision necessarily reads bounded buffers; it still never
    calls ndarray.tobytes or constructs hex. No input or global state is changed.
    """
    _limits()
    budget = _Budget()
    budget.walk(value)
    return budget.finish()
