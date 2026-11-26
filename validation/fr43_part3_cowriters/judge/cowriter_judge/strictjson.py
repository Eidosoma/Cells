"""Strict JSON for the judge: every duplicate key and every non-finite number is found with its location.

CRITERIA.md §4 treats a duplicate key and a NaN or an infinity differently by where they stand (a reference file;
a table's run entry; elsewhere in a table), so the parser keeps them instead of letting Python's json module drop a
duplicate silently or turn `1e999` into an infinity.

- A JSON object becomes a `JObject` (a dict). A key given more than once keeps its last value in the dict, and
  `JObject.duplicates[key]` lists every value given for it, in order (a run name twice in one `runs` is judged
  entry by entry, CRITERIA.md §4).
- `NaN`, `Infinity`, `-Infinity` and any number literal whose double is not finite become `NonFinite`.
- Nothing here executes or imports anything named in a file; it parses text.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Iterator


class NonFinite:
    """A number that is not finite: a NaN or infinity literal, or a literal whose double overflows."""

    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text

    def __repr__(self) -> str:
        return f"NonFinite({self.text!r})"


class JObject(dict):
    """A parsed JSON object; `duplicates` maps each key given more than once to all its values, in order."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.duplicates: dict[str, list[Any]] = {}


def _object_pairs(pairs: list[tuple[str, Any]]) -> JObject:
    obj = JObject()
    for key, value in pairs:
        if key in obj:
            obj.duplicates.setdefault(key, [obj[key]]).append(value)
        obj[key] = value
    return obj


def _parse_float(text: str) -> float | NonFinite:
    value = float(text)
    if not math.isfinite(value):
        return NonFinite(text)
    return value


def _parse_constant(text: str) -> NonFinite:
    return NonFinite(text)


class StrictJSONError(ValueError):
    """The bytes are not JSON (or not UTF-8)."""


def loads(text: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_float=_parse_float,
            parse_constant=_parse_constant,
        )
    except (ValueError, RecursionError) as exc:  # json.JSONDecodeError is a ValueError
        raise StrictJSONError(str(exc)) from exc


@dataclass(frozen=True)
class LoadedFile:
    path: str
    sha256: str
    data: Any


def load_file(path: str) -> LoadedFile:
    with open(path, "rb") as handle:
        raw = handle.read()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StrictJSONError(f"not UTF-8: {exc}") from exc
    return LoadedFile(path=path, sha256=digest, data=loads(text))


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


Path = tuple[Any, ...]


def problems(value: Any, path: Path = ()) -> Iterator[tuple[Path, str]]:
    """Yield (path, kind) for every duplicate key ('duplicate key') and non-finite number ('non-finite')."""
    if isinstance(value, JObject):
        for key in value.duplicates:
            yield path + (key,), "duplicate key"
        for key, item in value.items():
            yield from problems(item, path + (key,))
        for key, values in value.duplicates.items():
            # The values shadowed by the last one are looked into too: a fault inside them is still a fault.
            for index, item in enumerate(values[:-1]):
                yield from problems(item, path + (key, f"<duplicate {index}>"))
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from problems(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from problems(item, path + (index,))
    elif isinstance(value, NonFinite):
        yield path, "non-finite"


def path_text(path: Path) -> str:
    return "/".join(str(part) for part in path) or "<top>"


# ---- types (TABLE.md §3: an integer may be a float with no fraction, never a string; a bool is not a number) ----


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def is_integer(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value) and value == int(value)


def as_int(value: Any) -> int:
    return int(value)


def is_string(value: Any) -> bool:
    return isinstance(value, str)


def is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def is_object(value: Any) -> bool:
    return isinstance(value, dict)


def is_list(value: Any) -> bool:
    return isinstance(value, list)


def is_hex64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value)
