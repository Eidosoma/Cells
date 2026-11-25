"""JSON as the contract reads it. A duplicate key refuses the file; NaN and Infinity are read."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class DuplicateKey(ValueError):
    """A key that stands twice in one object."""


def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKey(f"the key {key!r} stands twice in one object")
        out[key] = value
    return out


def loads(data: bytes):
    """Parse bytes. Raises `DuplicateKey`, or `ValueError` for what is not JSON."""
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except DuplicateKey:
        raise
    except (ValueError, RecursionError) as error:
        raise ValueError(f"not readable as JSON: {error}") from error


def sha256(data: bytes) -> str:
    """The sha256 of bytes, as 64 hex digits."""
    return hashlib.sha256(data).hexdigest()


def read(path: Path):
    """A file's parsed JSON and the sha256 of its bytes."""
    data = Path(path).read_bytes()
    return loads(data), sha256(data)


def encode(value) -> bytes:
    """The bytes of a value as `dump` writes them."""
    return (json.dumps(plain(value), indent=1, allow_nan=True) + "\n").encode("utf-8")


def dump(path: Path, value) -> str:
    """Write a new JSON file and return its sha256. An existing file is never overwritten."""
    data = encode(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as handle:
        handle.write(data)
    return sha256(data)


def plain(value):
    """The value with numpy scalars and arrays, tuples and paths as JSON holds them."""
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "tolist"):
        return plain(value.tolist())
    raise TypeError(f"no JSON form for {type(value).__name__}")


def is_number(value) -> bool:
    """True for a JSON number. A boolean is not one."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_finite(value) -> bool:
    """True for a finite JSON number."""
    return is_number(value) and math.isfinite(value)


def is_integer(value) -> bool:
    """True for a JSON number that is an integer (4 and 4.0 alike)."""
    if isinstance(value, bool) or not is_number(value) or not math.isfinite(value):
        return False
    return isinstance(value, int) or float(value).is_integer()
