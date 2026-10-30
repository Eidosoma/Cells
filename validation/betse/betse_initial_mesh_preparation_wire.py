"""Independent typed native-cache wire records; production imports unnecessary."""

import hashlib
import struct

import numpy as np


def _layout(value):
    return dict(
        dtype=value.dtype.str,
        shape=list(value.shape),
        strides_bytes=list(value.strides),
        C_contiguous=bool(value.flags.c_contiguous),
        F_contiguous=bool(value.flags.f_contiguous),
    )


def capture(value):
    columns = {}

    def visit(item):
        if isinstance(item, np.ndarray):
            if item.dtype.hasobject:
                return dict(
                    type="object_array", layout=_layout(item), values=[visit(v) for v in item.flat]
                )
            name = f"native_{len(columns):06d}"
            columns[name] = np.array(item, copy=True, order="K")
            return dict(
                type="array",
                layout=_layout(item),
                column=name,
                sha256=hashlib.sha256(item.tobytes()).hexdigest(),
            )
        if isinstance(item, np.generic):
            return dict(type="numpy_scalar", dtype=item.dtype.str, bits=item.tobytes().hex())
        if type(item) is float:
            return dict(type="float", bits=struct.pack("<d", item).hex())
        if item is None or type(item) in (str, int, bool):
            return dict(type=type(item).__name__, value=item)
        if isinstance(item, dict):
            return dict(type="dict", values=[[visit(k), visit(v)] for k, v in item.items()])
        if isinstance(item, (list, tuple, set, frozenset)):
            return dict(type=type(item).__name__, values=[visit(v) for v in item])
        raise ValueError("Uncaptured native cache member: " + type(item).__name__)

    return dict(tree=visit(value), columns=columns)


def signature(tree):
    """Array storage names do not define numerical or owner identity."""
    if tree["type"] == "array":
        return {key: value for key, value in tree.items() if key != "column"}
    if tree["type"] == "dict":
        return dict(type="dict", values=[[signature(k), signature(v)] for k, v in tree["values"]])
    if "values" in tree:
        return {
            key: [signature(v) for v in value] if key == "values" else value
            for key, value in tree.items()
        }
    return tree


def owned_signature(node, columns):
    kind = node["kind"]
    if kind == "numeric_array":
        value = columns[node["column"]]
        digest = hashlib.sha256(value.tobytes()).hexdigest()
        assert digest == node["sha256"]
        assert value.dtype.str == node["source_layout"]["dtype"]
        assert list(value.shape) == node["source_layout"]["shape"]
        return dict(type="array", layout=node["source_layout"], sha256=digest)
    if kind == "object_array":
        return dict(
            type=kind,
            layout=node["source_layout"],
            values=[owned_signature(v, columns) for v in node["items"]],
        )
    if kind == "numpy_scalar":
        return dict(type=kind, dtype=node["dtype"], bits=node["bits"])
    if kind == "float":
        return dict(type=kind, bits=node["bits"])
    if kind == "dict":
        return dict(
            type=kind,
            values=[
                [owned_signature(k, columns), owned_signature(v, columns)] for k, v in node["items"]
            ],
        )
    if "items" in node:
        return dict(type=kind, values=[owned_signature(v, columns) for v in node["items"]])
    return dict(type=kind, value=node["value"])


def compare_owned(descriptor, columns, native):
    validate(native)
    assert owned_signature(descriptor, columns) == signature(native["tree"])


def validate(snapshot):
    columns, seen = snapshot["columns"], set()

    def walk(node):
        if node["type"] == "array":
            name = node["column"]
            if name in seen:
                raise ValueError("Duplicated native wire column")
            seen.add(name)
            value = columns[name]
            layout = node["layout"]
            if (
                value.dtype.hasobject
                or value.dtype.str != layout["dtype"]
                or list(value.shape) != layout["shape"]
                or hashlib.sha256(value.tobytes()).hexdigest() != node["sha256"]
            ):
                raise ValueError("Changed native wire array")
        elif node["type"] == "dict":
            for key, value in node["values"]:
                walk(key)
                walk(value)
        elif "values" in node:
            for value in node["values"]:
                walk(value)

    walk(snapshot["tree"])
    if seen != set(columns):
        raise ValueError("Unreferenced native wire columns")
    return snapshot


def plain(tree, columns):
    kind = tree["type"]
    if kind == "array":
        return columns[tree["column"]].tolist()
    if kind == "numpy_scalar":
        return np.frombuffer(bytes.fromhex(tree["bits"]), dtype=np.dtype(tree["dtype"]))[0].item()
    if kind == "float":
        return struct.unpack("<d", bytes.fromhex(tree["bits"]))[0]
    if kind == "dict":
        return {plain(k, columns): plain(v, columns) for k, v in tree["values"]}
    if kind == "object_array":
        shape = tree["layout"]["shape"]
        leaves = [plain(v, columns) for v in tree["values"]]

        def reshape(at, dims):
            if not dims:
                return leaves[at]
            width = 1
            for dim in dims[1:]:
                width *= dim
            return [reshape(at + i * width, dims[1:]) for i in range(dims[0])]

        return reshape(0, shape)
    if "values" in tree:
        return [plain(v, columns) for v in tree["values"]]
    return tree["value"]
