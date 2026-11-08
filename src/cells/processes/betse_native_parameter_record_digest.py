"""Fresh, bounded metadata hashing with the unchanged normal-current oracle.

Only exact built-in scalar/list/tuple/dict trees with string keys use the
iterative projection. Unsupported, cyclic or oversized inputs go through the
original serializer. No input, projection, digest or successful check is cached.
"""

import ast
import dis
import hashlib
import json
import struct
import sys
from pathlib import Path
from types import CodeType, FunctionType, MappingProxyType, ModuleType

from cells.processes import betse_normal_current as records

ORIGINAL_SHA256 = "294a4d3e267e9d75caccd50eaaacc462931a8597d5eadd88ea94f9dc3856add7"
MAX_NODES = 131072
MAX_DEPTH = 128
MAX_SCALAR_BYTES = 8 * 2**20
_LIMITS = (MAX_NODES, MAX_DEPTH, MAX_SCALAR_BYTES)
_FALLBACK, _EXIT = object(), object()
_RECORD, _DIGEST = records.record, records._digest
_PACK, _DUMPS, _SHA256 = struct.pack, json.dumps, hashlib.sha256


def _original_source():
    """Bind the two existing metadata definitions without executing their code."""
    path = Path(__file__).with_name("betse_normal_current.py")
    raw = path.read_bytes()
    if (
        type(records) is not ModuleType
        or sys.modules.get("cells.processes.betse_normal_current") is not records
        or Path(records.__file__).resolve() != path.resolve()
        or hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256
    ):
        raise ValueError("Exact original metadata serializer source required")
    nodes = [
        node
        for node in ast.parse(raw).body
        if isinstance(node, ast.FunctionDef) and node.name in ("record", "_digest")
    ]
    # CPython's module symbol information affects imported-module LOAD_ATTR
    # compilation. Compile the entire pinned module, but execute none of it.
    code = compile(raw, str(path), "exec", dont_inherit=True)
    expected = {
        item.co_name: item
        for item in code.co_consts
        if type(item) is CodeType and item.co_name in ("record", "_digest")
    }
    if len(nodes) != 2 or set(expected) != {"record", "_digest"}:
        raise ValueError("Exact original metadata definitions required")
    for name, function in (("record", _RECORD), ("_digest", _DIGEST)):
        if (
            type(function) is not FunctionType
            or function.__code__ != expected[name]
            or function.__globals__ is not vars(records)
            or function.__defaults__ is not None
            or function.__kwdefaults__ is not None
            or function.__closure__ is not None
        ):
            raise ValueError("Original metadata callable/code/defaults changed")
    if (
        records.np is not sys.modules.get("numpy")
        or type(records.np) is not ModuleType
        or records.MappingProxyType is not MappingProxyType
        or records.struct is not struct
        or records.hashlib is not hashlib
        or records.json is not json
    ):
        raise ValueError("Original metadata globals changed")


def _function_rows(functions):
    rows = []
    for function in functions:
        resolved = []
        for instruction in dis.get_instructions(function):
            if instruction.opname == "LOAD_GLOBAL":
                name = instruction.argval
                namespace = (
                    function.__globals__ if name in function.__globals__ else function.__builtins__
                )
                if not any(old[0] is namespace and old[1] == name for old in resolved):
                    resolved.append((namespace, name, namespace[name]))
        rows.append(
            (
                function,
                function.__code__,
                function.__defaults__,
                function.__kwdefaults__,
                tuple((function.__kwdefaults__ or {}).items()),
                function.__closure__,
                function.__globals__,
                function.__builtins__,
                tuple(resolved),
            )
        )
    return tuple(rows)


def _authenticate(selected):
    if selected is not records or records.record is not _RECORD or records._digest is not _DIGEST:
        raise ValueError("Original metadata serializer identity changed")
    for row in _ROWS:
        function, code, defaults, kwdefaults, keywords, closure, namespace, builtins, resolved = row
        if (
            function.__code__ is not code
            or function.__defaults__ is not defaults
            or function.__kwdefaults__ is not kwdefaults
            or len(function.__kwdefaults__ or {}) != len(keywords)
            or function.__closure__ is not closure
            or function.__globals__ is not namespace
            or function.__builtins__ is not builtins
        ):
            raise ValueError("Metadata callable/code/default/global binding changed")
        for name, value in keywords:
            if name not in kwdefaults or kwdefaults[name] is not value:
                raise ValueError("Metadata keyword default changed")
        for scope, name, value in resolved:
            if name not in scope or scope[name] is not value:
                raise ValueError("Metadata resolved global changed")
    for namespace, name, value in _ATTRIBUTES:
        if vars(namespace).get(name) is not value:
            raise ValueError("Metadata helper binding changed")
    fields = vars(json.JSONEncoder)
    if json.JSONEncoder.__mro__ is not _ENCODER_MRO or len(fields) != len(_ENCODER_FIELDS):
        raise ValueError("Metadata JSON encoder dispatch changed")
    for name, value in _ENCODER_FIELDS:
        if name not in fields or fields[name] is not value:
            raise ValueError("Metadata JSON encoder dispatch changed")


def _metadata_tree(value, limits):
    """Iterative record projection; unsupported domains return an inert marker."""
    maximum, depth_limit, byte_limit = limits
    result, active = [None], set()
    pending = [(None, value, result, 0, 0)]
    count, scheduled, scalar_bytes = 0, 1, 0
    while pending:
        task, item, target, key, depth = pending.pop()
        if task is _EXIT:
            active.remove(target)
            continue
        count += 1
        if count > maximum or depth > depth_limit:
            return _FALLBACK
        kind = type(item)
        if item is None or kind is bool or kind is int or kind is str:
            if kind is str:
                scalar_bytes += 12 * len(item)
            elif kind is int:
                scalar_bytes += item.bit_length() + 1
            else:
                scalar_bytes += 5
            target[key] = item
        elif kind is float:
            target[key] = {"float64_bits": _PACK("<d", item).hex()}
            scalar_bytes += 64
        elif kind is dict or kind is list or kind is tuple:
            size = len(item)
            if size > maximum - scheduled:
                return _FALLBACK
            container_identity = id(item)
            if container_identity in active:
                return _FALLBACK
            scheduled += size
            if kind is dict:
                for name in item:
                    if type(name) is not str:
                        return _FALLBACK
                    scalar_bytes += 12 * len(name)
                if scalar_bytes > byte_limit:
                    return _FALLBACK
                output = {}
                children = list(item.items())
            else:
                output = [None] * size
                children = list(enumerate(item))
            target[key] = output
            active.add(container_identity)
            pending.append((_EXIT, None, container_identity, None, None))
            pending.extend(
                [
                    (None, child, output, child_key, depth + 1)
                    for child_key, child in reversed(children)
                ]
            )
        else:
            return _FALLBACK
        if scalar_bytes > byte_limit:
            return _FALLBACK
    return result[0]


def digest(value, *, selected=records):
    """Hash current data afresh, or call the exact original serializer unchanged."""
    if (
        _authenticate is not _AUTHENTICATE
        or _authenticate.__code__ is not _AUTHENTICATE_CODE
        or _authenticate.__defaults__ is not None
        or _authenticate.__kwdefaults__ is not None
        or _authenticate.__closure__ is not None
    ):
        raise ValueError("Metadata authentication helper changed")
    _authenticate(selected)
    projected = _metadata_tree(value, _LIMITS)
    if projected is _FALLBACK:
        result = _DIGEST(value)
    else:
        result = _SHA256(
            _DUMPS(projected, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
    # Do not run a fallible postcheck while an original error is unwinding.
    _authenticate(selected)
    return result


def bindings():
    """Expose live helper atoms to the existing YAML-owner binding roster."""
    atoms = [records, _ROWS, _ATTRIBUTES, _ENCODER_MRO, _ENCODER_FIELDS, _LIMITS, _FALLBACK, _EXIT]
    for row in _ROWS:
        function = row[0]
        atoms.extend(
            (
                function,
                function.__code__,
                function.__defaults__,
                function.__kwdefaults__,
                function.__closure__,
                function.__globals__,
            )
        )
        for namespace, name, _ in row[-1]:
            atoms.extend((namespace, namespace.get(name)))
    for function in (_authenticate, bindings):
        atoms.extend(
            (
                function,
                function.__code__,
                function.__defaults__,
                function.__kwdefaults__,
                function.__closure__,
                function.__globals__,
            )
        )
    atoms.extend(vars(namespace).get(name) for namespace, name, _ in _ATTRIBUTES)
    atoms.extend(vars(json.JSONEncoder).values())
    return tuple(atoms)


_original_source()
_ENCODER_MRO = json.JSONEncoder.__mro__
_ENCODER_FIELDS = tuple(vars(json.JSONEncoder).items())
_ATTRIBUTES = tuple(
    (namespace, name, vars(namespace)[name])
    for namespace, names in (
        (records, ("record", "_digest", "np", "MappingProxyType", "struct", "hashlib", "json")),
        (records.np, ("ndarray",)),
        (struct, ("pack",)),
        (hashlib, ("sha256",)),
        (json, ("dumps", "JSONEncoder", "encoder")),
        (
            json.encoder,
            ("encode_basestring", "encode_basestring_ascii", "c_make_encoder", "_make_iterencode"),
        ),
    )
    for name in names
)
_AUTHENTICATE, _AUTHENTICATE_CODE = _authenticate, _authenticate.__code__
_ROWS = _function_rows(
    (
        _RECORD,
        _DIGEST,
        _metadata_tree,
        digest,
        json.dumps,
        json.JSONEncoder.__init__,
        json.JSONEncoder.default,
        json.JSONEncoder.encode,
        json.JSONEncoder.iterencode,
        json.encoder._make_iterencode,
    )
)
