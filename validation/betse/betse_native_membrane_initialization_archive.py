"""Exact typed sidecars for the bridge; importing this module runs no science."""

import json
import os
import struct
from collections.abc import Mapping
from dataclasses import fields, is_dataclass


def snapshot(value):
    kind = type(value)
    if kind.__module__ == "numpy" and kind.__name__ == "ndarray":
        result = dict(
            __ndarray__=True,
            dtype=value.dtype.str,
            shape=list(value.shape),
            strides=list(value.strides),
        )
        if value.dtype.kind == "O":
            result["object_values"] = snapshot(value.tolist())
        else:
            result["raw_bytes_hex"] = value.tobytes(order="C").hex()
        return result
    if kind.__module__.startswith("numpy") and hasattr(value, "dtype"):
        return dict(numpy_scalar_dtype=value.dtype.str, raw_bytes_hex=value.tobytes().hex())
    if is_dataclass(value):
        return {field.name: snapshot(getattr(value, field.name)) for field in fields(value)}
    if hasattr(value, "_asdict"):
        return {key: snapshot(child) for key, child in value._asdict().items()}
    if isinstance(value, Mapping):
        if all(type(key) is str for key in value):
            return {key: snapshot(child) for key, child in value.items()}
        return dict(
            __indexed_items__=[[snapshot(key), snapshot(child)] for key, child in value.items()]
        )
    if isinstance(value, (tuple, list)):
        return [snapshot(child) for child in value]
    if kind is bytes:
        return dict(bytes_hex=value.hex())
    if kind is float:
        return dict(float64_bits=struct.pack("<d", value).hex())
    if value is None or kind in (str, int, bool):
        return value
    raise ValueError("Unsupported sidecar value; no repr/pickle substitution: " + kind.__qualname__)


def original_six_stores(cells):
    """Capture original stores before any initializer copy or normalization."""
    owners = vars(cells)

    def direct(value):
        kind = type(value)
        return dict(
            python_type=kind.__module__ + "." + kind.__qualname__, value=snapshot(value)
        )

    stores = {}
    for name in (
        "cell_i",
        "mem_i",
        "mem_to_cells",
        "cell_to_mems",
        "mem_mids_flat",
        "mem_vects_flat",
    ):
        if name not in owners:
            stores[name] = dict(present=False)
            continue
        observed = direct(owners[name])
        if name == "cell_to_mems":
            # Preserve each original row's container/dtype/strides too; an
            # object-array .tolist() alone cannot retain those row headers.
            observed["rows"] = [direct(row) for row in owners[name]]
        stores[name] = dict(present=True, value=observed)
    return dict(kind="cells.original_six_membrane_stores@1", stores=stores)


def require_declared_refusal(report, label):
    """An unrelated positive-baseline failure is not a successful control."""
    rows = report.get("rows")
    prefix = (
        "full_original_pair_retained",
        "original_pair_seal",
        "original_native_boundary_seal",
    )
    if (
        report.get("passed") is not False
        or type(rows) is not list
        or len(rows) < 4
        or rows[:3] != [dict(label=name, passed=True) for name in prefix]
        or rows[-1] != dict(label=label, passed=False)
        or any(row.get("passed") is not True for row in rows[:-1])
    ):
        raise ValueError("Independent control did not reach its declared refusal: " + label)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(snapshot(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
