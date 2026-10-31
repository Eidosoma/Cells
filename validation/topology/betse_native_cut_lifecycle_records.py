"""Generic typed array/alias records for independent source capture; no Cells imports."""

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from types import SimpleNamespace

import numpy as np


class _DataOwner:
    pass


def snapshot(value):
    """Encode data types, dictionary order and shared mutable references exactly.

    Object arrays encode children rather than object-pointer bytes. This record
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


def restore(packet):
    """Decode supplied fixture evidence; never create a physical geometry."""
    raw = json.loads(packet) if isinstance(packet, str) else packet
    if raw["kind"] != "cells.cut_typed_alias_graph@1":
        raise ValueError("Unknown cut evidence graph")
    known = {}

    def decode(value):
        if not isinstance(value, dict):
            return value
        if "float64" in value:
            return float.fromhex(value["float64"])
        if "numpy_scalar" in value:
            return np.frombuffer(
                bytes.fromhex(value["data"]), dtype=np.dtype(value["numpy_scalar"])
            )[0]
        at = value["ref"]
        if at in known:
            return known[at]
        node = raw["nodes"][at]
        kind = node["kind"]
        if kind == "ndarray":
            if "items" in node:
                result = np.empty(node["shape"], dtype=object)
                known[at] = result
                for i, item in enumerate(node["items"]):
                    result.flat[i] = decode(item)
                return result
            result = (
                np.frombuffer(bytes.fromhex(node["data"]), dtype=np.dtype(node["dtype"]))
                .copy()
                .reshape(node["shape"])
            )
        elif kind in ("dict", "namespace", "dataclass"):
            result = {} if kind == "dict" else _DataOwner()
            known[at] = result
            target = result if isinstance(result, dict) else vars(result)
            for key, item in node["items"]:
                target[key] = decode(item)
            return result
        elif kind in ("list", "tuple", "set"):
            result = []
            known[at] = result
            result.extend(decode(v) for v in node["items"])
            if kind == "tuple":
                result = tuple(result)
            elif kind == "set":
                result = set(result)
        else:
            raise ValueError("Unknown supplied cut node type")
        known[at] = result
        return result

    return decode(raw["root"])
