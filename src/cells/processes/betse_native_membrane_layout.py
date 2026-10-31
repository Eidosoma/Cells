"""Lossless native six-column membrane snapshots and explicit consumer views.

This module copies stores and checks schema/owners only. It never evaluates
geometry, normalizes vectors, advances native state, or admits physical meshes.
Numeric bytes retain their original dtype, byte order and logical row order.
"""

import hashlib
import inspect
import json
import math
import struct
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType

LAW_ID = "betse_native_six_column_membrane_layout_v1_5_0@1"
DECLARATION_KIND = "cells.betse_native_membrane_layout_declaration@1"
SOURCE_REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
NATIVE_TYPE = "betse.science.cells.Cells"
NATIVE_SOURCE_SHA256 = "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"
COLUMNS = ("mid_x", "mid_y", "nx", "ny", "tx", "ty")
COLUMN_UNITS = ("m", "m", "1", "1", "1", "1")
OWNER_FIELDS = (
    "cell_i",
    "mem_i",
    "mem_to_cells",
    "cell_to_mems",
    "mem_mids_flat",
    "mem_vects_flat",
)
MIDPOINT_NORMAL_LAW = "cells.native_six_to_midpoint_normal_xy@1"
NORMAL_TANGENT_LAW = "cells.native_six_to_normal_tangent_xy@1"
MAX_CELLS = 16
MAX_MEMBRANES = 128
MAX_BUFFER_BYTES = 65536
GATES = MappingProxyType(
    dict(
        physical_geometry_admitted=False,
        vector_geometry_qualified=False,
        native_seed_init_history_proven=False,
        initialization_handoff_integrated=False,
        ordinary_ECM_loop_ready=False,
    )
)


@dataclass(frozen=True)
class Buffer:
    dtype: str
    shape: tuple
    raw: bytes
    original_strides: tuple


@dataclass(frozen=True)
class Snapshot:
    declaration: object
    observation: str
    entries: object
    source: object
    identity: str


@dataclass(frozen=True)
class Layout:
    snapshot: Snapshot
    owner_cells: tuple
    owner_local_indices: tuple
    columns: tuple
    column_units: tuple
    gates: object
    identity: str


@dataclass(frozen=True)
class ConsumerView:
    parent: Layout
    conversion_law: str
    selected_columns: tuple
    columns: tuple
    column_units: tuple
    values: Buffer
    gates: object
    identity: str


class LayoutRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__("Native membrane layout refused at " + stage + ": " + str(reason))
        self.stage, self.original, self.partial = stage, original, partial


def plain(value):
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(child) for child in value]
    if type(value) is bytes:
        return dict(bytes_hex=value.hex())
    return value


def digest(value):
    encoded = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(child) for child in value)
    if value is None or type(value) in (str, int, bool, bytes) or type(value) is Buffer:
        return value
    raise ValueError("Require explicit bounded nonnumeric metadata or typed buffers")


def _array_header(value):
    if type(value).__module__ != "numpy" or type(value).__name__ != "ndarray":
        raise ValueError("Require an actual base ndarray; no coercion or object methods")
    return dict(dtype=value.dtype.str, shape=tuple(value.shape), strides=tuple(value.strides))


def _buffer(value):
    if type(value) is Buffer:
        return value
    header = _array_header(value)
    view = memoryview(value)
    if view.nbytes > MAX_BUFFER_BYTES or value.dtype.kind not in "fiu":
        raise ValueError("Require a bounded real/integer native buffer; no object serialization")
    return Buffer(header["dtype"], header["shape"], view.tobytes(order="C"), header["strides"])


def _indices(value):
    if type(value) in (tuple, list):
        if len(value) > MAX_MEMBRANES or any(type(index) is not int for index in value):
            raise ValueError("Require bounded original integer index sequences")
        return dict(kind="python_indices", container=type(value).__name__, values=tuple(value))
    if type(value) is not Buffer:
        header = _array_header(value)
        if header["dtype"] == "|O":
            items = value.tolist()
            if (
                len(header["shape"]) != 1
                or len(items) > MAX_MEMBRANES
                or any(type(index) is not int for index in items)
            ):
                raise ValueError("Require a bounded original object row of integer indices")
            return dict(kind="object_indices", header=header, values=tuple(items))
    return dict(kind="array_indices", buffer=_buffer(value))


def _owner_rows(value):
    if type(value) in (tuple, list):
        header = dict(container=type(value).__name__, dtype=None, shape=(len(value),), strides=None)
    else:
        header = _array_header(value)
        header["container"] = "ndarray"
        if len(header["shape"]) not in (1, 2) or header["dtype"] != "|O":
            raise ValueError("Require original ragged object owner rows; no inferred grouping")
    if not 1 <= len(value) <= MAX_CELLS:
        raise ValueError("Owner row count exceeds the explicit native-layout domain")
    return dict(
        kind="native_cell_to_mems_rows", header=header, rows=tuple(_indices(row) for row in value)
    )


def snapshot_record(value):
    return (LAW_ID, value.declaration, value.observation, value.entries, value.source)


def capture_supplied(owners, declaration):
    """Copy the six named stores, retaining absence and per-field capture errors."""
    entries = {}
    try:
        values = owners if isinstance(owners, Mapping) else vars(owners)
        for key in OWNER_FIELDS:
            if key not in values:
                entries[key] = dict(present=False)
                continue
            try:
                original = values[key]
                value = (
                    _owner_rows(original)
                    if key == "cell_to_mems"
                    else _indices(original)
                    if key in ("cell_i", "mem_i")
                    else _buffer(original)
                )
                entries[key] = dict(present=True, captured=True, value=value)
            except Exception as error:
                entries[key] = dict(
                    present=True,
                    captured=False,
                    type=type(values[key]).__name__,
                    error_type=type(error).__name__,
                    reason=str(error),
                )
        snapshot = Snapshot(freeze(declaration), "supplied_owner_stores", freeze(entries), None, "")
        return replace(snapshot, identity=digest(snapshot_record(snapshot)))
    except Exception as error:
        raise LayoutRejected(
            error, stage="capture", original=owners, partial=freeze(entries)
        ) from error


def capture_native(cells, declaration):
    """Passively read one pinned Cells instance; its construction history stays open."""
    snapshot = capture_supplied(cells, declaration)
    partial = {}
    try:
        cls = type(cells)
        qualified = cls.__module__ + "." + cls.__qualname__
        partial["qualified_type"] = qualified
        if qualified != NATIVE_TYPE:
            raise ValueError("Require the actual pinned native Cells class")
        source = Path(inspect.getfile(cls))
        partial.update(source=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if partial["sha256"] != NATIVE_SOURCE_SHA256:
            raise ValueError("Changed native Cells source")
        result = replace(
            snapshot, observation="pinned_native_Cells_stores", source=freeze(partial), identity=""
        )
        return replace(result, identity=digest(snapshot_record(result)))
    except Exception as error:
        raise LayoutRejected(
            error, stage="native_source", original=snapshot, partial=freeze(partial)
        ) from error


def _decoded(buffer, *, floating, rank):
    if type(buffer) is not Buffer or type(buffer.raw) is not bytes:
        raise ValueError("Require an immutable typed numeric buffer")
    formats = (
        {"<f8": "<d", ">f8": ">d"}
        if floating
        else {
            "<i4": "<i",
            ">i4": ">i",
            "<i8": "<q",
            ">i8": ">q",
            "<u4": "<I",
            ">u4": ">I",
            "<u8": "<Q",
            ">u8": ">Q",
        }
    )
    if buffer.dtype not in formats:
        raise ValueError("Require original binary64 geometry or 32/64-bit integer owners")
    if (
        type(buffer.shape) is not tuple
        or len(buffer.shape) != rank
        or any(type(v) is not int or not 1 <= v <= MAX_MEMBRANES for v in buffer.shape)
        or type(buffer.original_strides) is not tuple
        or len(buffer.original_strides) != rank
        or any(type(v) is not int for v in buffer.original_strides)
    ):
        raise ValueError("Incomplete original shape/stride metadata")
    form = formats[buffer.dtype]
    if len(buffer.raw) != math.prod(buffer.shape) * struct.calcsize(form):
        raise ValueError("Typed payload length differs from its actual shape and dtype")
    if len(buffer.raw) > MAX_BUFFER_BYTES:
        raise ValueError("Native layout buffer exceeds the bounded domain")
    result = tuple(row[0] for row in struct.iter_unpack(form, buffer.raw))
    if floating and any(not math.isfinite(value) for value in result):
        raise ValueError("Nonfinite native vector/midpoint stores are unsupported")
    return result


def _index_values(value):
    if value["kind"] == "array_indices" and set(value) == {"kind", "buffer"}:
        return _decoded(value["buffer"], floating=False, rank=1)
    if value["kind"] == "object_indices" and set(value) == {"kind", "header", "values"}:
        header = value["header"]
        if (
            set(header) != {"dtype", "shape", "strides"}
            or header["dtype"] != "|O"
            or header["shape"] != (len(value["values"]),)
            or len(header["strides"]) != 1
            or any(type(stride) is not int for stride in header["strides"])
            or any(type(index) is not int for index in value["values"])
        ):
            raise ValueError("Changed original object index row metadata or values")
        return value["values"]
    if (
        set(value) != {"kind", "container", "values"}
        or value["kind"] != "python_indices"
        or value["container"] not in ("list", "tuple")
        or type(value["values"]) is not tuple
        or any(type(index) is not int for index in value["values"])
    ):
        raise ValueError("Changed original index sequence type or payload")
    return value["values"]


def _declaration(value):
    if (
        not isinstance(value, Mapping)
        or set(value)
        != {
            "kind",
            "opted_in_law",
            "columns",
            "column_units",
            "owner_order",
            "geometry_classification",
            "evidence",
        }
        or value["kind"] != DECLARATION_KIND
        or value["opted_in_law"] != LAW_ID
        or tuple(value["columns"]) != COLUMNS
        or tuple(value["column_units"]) != COLUMN_UNITS
        or value["owner_order"] != "native_cell_major_then_membrane_local_i"
        or value["geometry_classification"] != "unqualified_native_layout"
    ):
        raise ValueError("Declare the complete six-column source roles/units and unqualified order")
    if not isinstance(value["evidence"], tuple) or not value["evidence"]:
        raise ValueError("Link original owner evidence; links do not prove native initialization")
    for row in value["evidence"]:
        if (
            set(row) != {"path", "sha256"}
            or type(row["path"]) is not str
            or not row["path"]
            or type(row["sha256"]) is not str
            or len(row["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in row["sha256"])
        ):
            raise ValueError("Require explicit evidence paths and SHA256 identities")


def layout_record(value):
    return (
        LAW_ID,
        value.snapshot,
        value.owner_cells,
        value.owner_local_indices,
        value.columns,
        value.column_units,
        value.gates,
    )


def bind_layout(snapshot):
    partial = {}
    try:
        if type(snapshot) is not Snapshot or snapshot.identity != digest(snapshot_record(snapshot)):
            raise ValueError("Changed or unsealed native layout snapshot")
        _declaration(snapshot.declaration)
        if snapshot.observation == "pinned_native_Cells_stores":
            if (
                set(snapshot.source) != {"qualified_type", "source", "sha256"}
                or snapshot.source["qualified_type"] != NATIVE_TYPE
                or snapshot.source["sha256"] != NATIVE_SOURCE_SHA256
                or type(snapshot.source["source"]) is not str
                or not snapshot.source["source"]
            ):
                raise ValueError("Incomplete native class/source observation")
        elif snapshot.observation != "supplied_owner_stores" or snapshot.source is not None:
            raise ValueError("Unknown source observation; no native history may be inferred")
        if set(snapshot.entries) != set(OWNER_FIELDS):
            raise ValueError("Incomplete original owner field inventory")
        values = {}
        for key in OWNER_FIELDS:
            entry = snapshot.entries[key]
            if set(entry) != {"present", "captured", "value"} or (
                entry["present"] is not True or entry["captured"] is not True
            ):
                raise ValueError("Missing or unreadable actual native store: " + key)
            values[key] = entry["value"]
        ci, mi = (_index_values(values[key]) for key in ("cell_i", "mem_i"))
        n, m = len(ci), len(mi)
        if (
            not 1 <= n <= MAX_CELLS
            or not 1 <= m <= MAX_MEMBRANES
            or ci != tuple(range(n))
            or mi != tuple(range(m))
        ):
            raise ValueError("Native cell_i/mem_i must retain the complete source row axes")
        owner = _decoded(values["mem_to_cells"], floating=False, rank=1)
        partial["owner_cells"] = owner
        if len(owner) != m:
            raise ValueError("Incomplete membrane-to-cell owner axis")
        rows = values["cell_to_mems"]
        if (
            set(rows) != {"kind", "header", "rows"}
            or rows["kind"] != "native_cell_to_mems_rows"
            or len(rows["rows"]) != n
        ):
            raise ValueError("Require complete original cell_to_mems rows")
        header = rows["header"]
        if set(header) != {"container", "dtype", "shape", "strides"}:
            raise ValueError("Incomplete ragged owner container metadata")
        if header["container"] == "ndarray":
            if (
                header["dtype"] != "|O"
                or len(header["shape"]) not in (1, 2)
                or header["shape"][0] != n
                or len(header["strides"]) != len(header["shape"])
                or any(type(v) is not int or not 1 <= v <= MAX_MEMBRANES for v in header["shape"])
                or any(type(v) is not int for v in header["strides"])
            ):
                raise ValueError("Changed native object owner container header")
        elif (
            header["container"] not in ("list", "tuple")
            or header["dtype"] is not None
            or header["shape"] != (n,)
            or header["strides"] is not None
        ):
            raise ValueError("Changed original owner row sequence header")
        flat, expected_owners, local_indices = [], [], []
        partial.update(
            flat_owner_rows=flat, expected_owners=expected_owners, owner_local_indices=local_indices
        )
        for cell, row in enumerate(rows["rows"]):
            indices = _index_values(row)
            if (
                not indices
                or header["container"] == "ndarray"
                and len(header["shape"]) == 2
                and (len(indices) != header["shape"][1])
            ):
                raise ValueError("Incomplete original local membrane axis")
            flat.extend(indices)
            expected_owners.extend([cell] * len(indices))
            local_indices.extend(range(len(indices)))
        if tuple(flat) != mi or tuple(expected_owners) != owner:
            raise ValueError("Native cell-major/local order or inverse owner maps disagree")
        vectors, midpoints = values["mem_vects_flat"], values["mem_mids_flat"]
        _decoded(vectors, floating=True, rank=2)
        _decoded(midpoints, floating=True, rank=2)
        if vectors.shape != (m, 6) or midpoints.shape != (m, 2):
            raise ValueError("Require full six-column native vectors and matching midpoint rows")
        if vectors.dtype != midpoints.dtype:
            raise ValueError("Midpoint duplicate stores changed dtype/byte order")
        duplicate = b"".join(vectors.raw[48 * i : 48 * i + 16] for i in range(m))
        if duplicate != midpoints.raw:
            raise ValueError("Native midpoint columns differ bitwise from mem_mids_flat")
        result = Layout(
            snapshot, owner, tuple(local_indices), COLUMNS, COLUMN_UNITS, freeze(GATES), ""
        )
        return replace(result, identity=digest(layout_record(result)))
    except Exception as error:
        raise LayoutRejected(
            error, stage="schema_and_owners", original=snapshot, partial=freeze(partial)
        ) from error


def _validate_layout(value):
    if type(value) is not Layout or value.identity != digest(layout_record(value)):
        raise ValueError("Changed or unsealed layout")
    checked = bind_layout(value.snapshot)
    if digest(layout_record(value)) != digest(layout_record(checked)):
        raise ValueError("Resealed layout differs from the original six-column parent")


def view_record(value):
    return (
        value.parent,
        value.conversion_law,
        value.selected_columns,
        value.columns,
        value.column_units,
        value.values,
        value.gates,
    )


def _view(layout, opted_in_conversion, law, columns):
    try:
        _validate_layout(layout)
        if opted_in_conversion != law:
            raise ValueError("Name the exact requested column conversion")
        original = layout.snapshot.entries["mem_vects_flat"]["value"]
        m = original.shape[0]
        raw = b"".join(
            original.raw[48 * i + 8 * c : 48 * i + 8 * (c + 1)] for i in range(m) for c in columns
        )
        values = Buffer(original.dtype, (m, 4), raw, (32, 8))
        result = ConsumerView(
            layout,
            law,
            columns,
            tuple(COLUMNS[c] for c in columns),
            tuple(COLUMN_UNITS[c] for c in columns),
            values,
            freeze(GATES),
            "",
        )
        return replace(result, identity=digest(view_record(result)))
    except Exception as error:
        raise LayoutRejected(
            error,
            stage="explicit_conversion",
            original=layout,
            partial=freeze(dict(requested=opted_in_conversion, expected=law)),
        ) from error


def midpoint_normal_view(layout, *, opted_in_conversion):
    """Select [mid_x,mid_y,nx,ny]; original tangents remain in the parent."""
    return _view(layout, opted_in_conversion, MIDPOINT_NORMAL_LAW, (0, 1, 2, 3))


def normal_tangent_view(layout, *, opted_in_conversion):
    """Select [nx,ny,tx,ty]; original midpoint stores remain in the parent."""
    return _view(layout, opted_in_conversion, NORMAL_TANGENT_LAW, (2, 3, 4, 5))


def validate_view(value):
    try:
        if type(value) is not ConsumerView or value.identity != digest(view_record(value)):
            raise ValueError("Changed or unsealed consumer view")
        functions = {
            MIDPOINT_NORMAL_LAW: midpoint_normal_view,
            NORMAL_TANGENT_LAW: normal_tangent_view,
        }
        if value.conversion_law not in functions:
            raise ValueError("Unknown explicit column conversion")
        expected = functions[value.conversion_law](
            value.parent, opted_in_conversion=value.conversion_law
        )
        if digest(view_record(value)) != digest(view_record(expected)):
            raise ValueError("Resealed view differs from its complete original parent")
        return value
    except Exception as error:
        raise LayoutRejected(error, stage="view_authentication", original=value) from error


def require_initialization_handoff(value):
    raise LayoutRejected(
        "Schema/owner capture does not establish physical geometry, vector "
        "qualification, seed/init history or initialization integration",
        stage="initialization_handoff",
        original=value,
    )
