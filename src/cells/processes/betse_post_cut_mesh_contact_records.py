"""Typed source evidence. Snapshot encoding is reused unchanged from cut25."""

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from types import SimpleNamespace

import numpy as np


class _DataOwner:
    """Explicit data carrier whose dictionary preserves supplied graph aliases."""


def snapshot(value):
    """Encode data types, dictionary order and shared mutable references exactly.

    Object arrays encode children rather than object-pointer bytes. Shared object
    identity is retained; distinct ndarray views do not encode shared buffer
    ownership. The literal prefix never mutates existing numeric buffers. This record
    is evidence only; it does not constitute a simulator checkpoint migration.
    """
    nodes, seen = ([], {})

    def encode(item, depth=0):
        if depth > 48 or len(nodes) > 32768:
            raise ValueError("Refuse unbounded cut evidence graph")
        if item is None or type(item) in (str, bool, int):
            return item
        if type(item) is float:
            return dict(float64=item.hex())
        if isinstance(item, np.generic):
            return dict(numpy_scalar=item.dtype.str, data=item.tobytes().hex())
        if not isinstance(
            item, (np.ndarray, Mapping, list, tuple, set, SimpleNamespace, _DataOwner)
        ) and (not is_dataclass(item)):
            raise ValueError("Require explicit cut data without executable or opaque owners")
        at = seen.get(id(item))
        if at is not None:
            return dict(ref=at)
        at = len(nodes)
        seen[id(item)] = at
        nodes.append(None)
        if isinstance(item, np.ndarray):
            if item.nbytes > 16 * 2**20:
                raise ValueError("Refuse an unbounded cut array")
            node = dict(kind="ndarray", dtype=item.dtype.str, shape=list(item.shape))
            if item.dtype.hasobject:
                node["items"] = [encode(v, depth + 1) for v in item.flat]
            else:
                node["data"] = item.tobytes(order="C").hex()
        elif isinstance(item, Mapping):
            if any((type(key) is not str for key in item)):
                raise ValueError("Require named cut data fields")
            node = dict(kind="dict", items=[[key, encode(v, depth + 1)] for key, v in item.items()])
        elif isinstance(item, (SimpleNamespace, _DataOwner)):
            node = dict(
                kind="namespace",
                items=[[key, encode(v, depth + 1)] for key, v in vars(item).items()],
            )
        elif is_dataclass(item):
            node = dict(
                kind="dataclass",
                type=type(item).__name__,
                items=[[f.name, encode(getattr(item, f.name), depth + 1)] for f in fields(item)],
            )
        else:
            kind = "set" if isinstance(item, set) else "list" if isinstance(item, list) else "tuple"
            values = sorted(item, key=repr) if isinstance(item, set) else item
            node = dict(kind=kind, items=[encode(v, depth + 1) for v in values])
        nodes[at] = node
        return dict(ref=at)

    root = encode(value)
    return json.dumps(
        dict(kind="cells.cut_typed_alias_graph@1", root=root, nodes=nodes),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def restore(text):
    raw = json.loads(text)
    if set(raw) != {"kind", "root", "nodes"} or raw["kind"] != "cells.cut_typed_alias_graph@1":
        raise ValueError("Complete typed source graph required")
    if len(raw["nodes"]) > 32768:
        raise ValueError("Bounded graph nodes required")
    decoded = {}
    active = set()

    def decode(item):
        if not isinstance(item, dict):
            return item
        if set(item) == {"float64"}:
            return float.fromhex(item["float64"])
        if set(item) == {"numpy_scalar", "data"}:
            return np.frombuffer(bytes.fromhex(item["data"]), dtype=item["numpy_scalar"])[0]
        if (
            set(item) != {"ref"}
            or type(item["ref"]) is not int
            or not 0 <= item["ref"] < len(raw["nodes"])
        ):
            raise ValueError("Typed graph reference differs")
        index = item["ref"]
        if index in decoded:
            return decoded[index]
        if index in active:
            raise ValueError("Immutable tuple-cycle is unsupported")
        active.add(index)
        node = raw["nodes"][index]
        kind = node["kind"]
        if kind == "dict":
            value = {}
            decoded[index] = value
            for key, child in node["items"]:
                if key in value:
                    raise ValueError("Duplicate source graph field")
                value[key] = decode(child)
        elif kind in {"namespace", "dataclass"}:
            value = SimpleNamespace()
            decoded[index] = value
            for key, child in node["items"]:
                setattr(value, key, decode(child))
        elif kind == "ndarray":
            dtype = np.dtype(node["dtype"])
            shape = tuple(node["shape"])
            if dtype.hasobject:
                value = np.empty(shape, dtype=dtype)
                decoded[index] = value
                if value.size != len(node["items"]):
                    raise ValueError("Complete object-array axes required")
                for offset, child in enumerate(node["items"]):
                    value.flat[offset] = decode(child)
            else:
                value = (
                    np.frombuffer(bytes.fromhex(node["data"]), dtype=dtype).copy().reshape(shape)
                )
                decoded[index] = value
        elif kind == "list":
            value = []
            decoded[index] = value
            value.extend(decode(child) for child in node["items"])
        elif kind == "tuple":
            value = tuple(decode(child) for child in node["items"])
            decoded[index] = value
        elif kind == "set":
            value = set()
            decoded[index] = value
            value.update(decode(child) for child in node["items"])
        else:
            raise ValueError("Unknown explicit typed source node")
        active.remove(index)
        return value

    return decode(raw["root"])
