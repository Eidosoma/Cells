"""Typed full sidecars, nonfinite bits and separate worker import boundaries."""

import json
import math
import os
import struct
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path

from validation.geometry import stable_geometry_primitives_runtime as inventory

PREFIX = "betse-mechanics-join"


def plain(value):
    if is_dataclass(value):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if hasattr(value, "tolist"):
        return plain(value.tolist())
    if hasattr(value, "__dict__"):
        return plain(vars(value))
    if type(value) is float and not math.isfinite(value):
        return dict(nonfinite_binary64_bits=struct.pack(">d", value).hex())
    return value


def arrays(value, prefix="payload"):
    if hasattr(value, "dtype") and hasattr(value, "shape"):
        return {prefix: value} if value.dtype.kind in "bifu" else {}
    if is_dataclass(value):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if hasattr(value, "__dict__"):
        value = vars(value)
    if isinstance(value, Mapping):
        items = value.items()
    elif isinstance(value, (tuple, list)):
        items = enumerate(value)
    else:
        return {}
    result = {}
    for key, item in items:
        result.update(arrays(item, prefix + "__" + str(key)))
    return result


def typed_inventory(value, prefix="payload"):
    if hasattr(value, "dtype") and hasattr(value, "shape"):
        return {
            prefix: dict(
                dtype=value.dtype.str,
                shape=list(value.shape),
                object_values=plain(value) if value.dtype.kind == "O" else None,
            )
        }
    if is_dataclass(value):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if hasattr(value, "__dict__"):
        value = vars(value)
    if isinstance(value, Mapping):
        items = value.items()
    elif isinstance(value, (list, tuple)):
        items = enumerate(value)
    else:
        return {}
    result = {}
    for key, item in items:
        result.update(typed_inventory(item, prefix + "__" + str(key)))
    return result


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(plain(value), separators=(",", ":"), allow_nan=False)
    if len(data.encode()) > 16 * 2**20:
        raise ValueError("Split complete payloads without truncation; metadata bound stays16 MiB")
    with path.open("x") as stream:
        stream.write(data + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read(path):
    path = Path(path)
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Oversize sidecar")
    return json.loads(path.read_text())


def restore(value):
    if isinstance(value, dict):
        if set(value) == {"nonfinite_binary64_bits"}:
            return struct.unpack(">d", bytes.fromhex(value["nonfinite_binary64_bits"]))[0]
        return {key: restore(item) for key, item in value.items()}
    if isinstance(value, list):
        return [restore(item) for item in value]
    return value


def root(name):
    return Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / PREFIX / name


def guard(mode):
    inventory.BLOCKED = (
        {"cells", "betse", "jax", "jaxlib", "torch"}
        if mode in ("native", "raw")
        else inventory.SCIENTIFIC | {"cells"}
    )
    inventory.deny_production()


def capture():
    return inventory.capture()


def pytest_sessionfinish(session, exitstatus):
    write(
        Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "runtime.json",
        capture() | dict(exitstatus=int(exitstatus)),
    )
