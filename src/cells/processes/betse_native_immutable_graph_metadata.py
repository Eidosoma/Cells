"""Immutable historical YAML metadata prototype; no owner or live-state authority.

The producer must freeze its fresh descriptor before publishing a capture. The
returned bytes, rather than the discarded mutable descriptor, become historical
metadata. Raw object references remain separate and are not made immutable.

This does not retrofit existing captures or cache successful validation of a
mutable graph. Consumers must retain the exact returned image, authenticate this
module in their existing bindings, and continue their live-state/observer checks.
"""

import hashlib
import json
import weakref
from io import BytesIO
from types import CodeType
from typing import NamedTuple

MAX_NODES = 131072
MAX_DEPTH = 128
MAX_BYTES = 16 * 2**20
DEFAULT_LIMITS = (MAX_NODES, MAX_DEPTH, MAX_BYTES)
HISTORY_FORMAT = "exact_immutable_parameter_history@1"
_HISTORY_ISSUED = {}


class FrozenGraph(NamedTuple):
    """Metadata transport, not an issuance token or proof of a native parent."""

    raw_objects: tuple
    descriptor_bytes: bytes
    descriptor_sha256: str


class MetadataRejected(ValueError):
    """Retain exact raw inputs and an original failure, including falsey errors."""

    def __init__(self, reason, *, graph, stage, source_error, partial):
        super().__init__(reason)
        self.graph = graph
        self.raw_objects = graph[0] if type(graph) is tuple and len(graph) == 2 else None
        self.descriptor = graph[1] if type(graph) is tuple and len(graph) == 2 else None
        self.stage = stage
        self.source_error = source_error
        self.partial = partial


def _limits(limits):
    if (
        type(limits) is not tuple
        or len(limits) != 3
        or any(type(value) is not int or value <= 0 for value in limits)
        or limits[0] > MAX_NODES
        or limits[1] > MAX_DEPTH
        or limits[2] > MAX_BYTES
    ):
        raise ValueError("Exact positive limits within the prototype bounds required")
    return limits


def _tree(value, limits):
    """Detach into exact immutable tagged tuples before any JSON encoding.

    Witnesses are temporary, bounded capture checks, not retained authority. An
    alias is visited at each wire occurrence; only an active ancestor is a cycle.
    No user iterator, equality, repr, conversion, or mapping implementation runs.
    """
    maximum, depth_limit, byte_limit = limits
    active, witnesses = set(), []
    count = 0

    def visit(item, depth):
        nonlocal count
        count += 1
        if count > maximum or depth > depth_limit:
            raise ValueError("Historical descriptor node/depth bound exceeded")
        kind = type(item)
        if item is None or kind is bool or kind is int or kind is str:
            if kind is str and len(item) > byte_limit:
                raise ValueError("Historical descriptor scalar byte bound exceeded")
            if kind is int and item.bit_length() > byte_limit * 4:
                raise ValueError("Historical descriptor integer byte bound exceeded")
            return ("scalar", item)
        if kind is not dict and kind is not list and kind is not tuple:
            raise ValueError("Unsupported exact historical descriptor type")
        if len(item) > maximum - count:
            raise ValueError("Historical descriptor pending node bound exceeded")
        token = id(item)
        if token in active:
            raise ValueError("Cyclic historical descriptor refused")
        active.add(token)
        try:
            if kind is dict:
                rows = tuple(dict.items(item))
                if any(type(key) is not str or len(key) > byte_limit for key, _ in rows):
                    raise ValueError("Exact bounded string descriptor keys required")
                witnesses.append((item, kind, rows))
                children = tuple((key, visit(child, depth + 1)) for key, child in rows)
                return ("object", tuple(sorted(children, key=lambda row: row[0])))
            rows = tuple(item)
            witnesses.append((item, kind, rows))
            return (
                "list" if kind is list else "tuple",
                tuple(visit(child, depth + 1) for child in rows),
            )
        finally:
            active.remove(token)

    return visit(value, 0), witnesses


def _encode(tree, byte_limit):
    """Canonical original JSON from immutable nodes; tuples become JSON arrays."""
    # Retaining every fragment also makes bytes.join allocate a buffer record
    # per fragment, in addition to the final payload. Write directly into one
    # growing buffer; getvalue returns the same complete immutable wire format.
    encoded, pending, length = BytesIO(), [tree], 0
    while pending:
        current = pending.pop()
        if type(current) is bytes:
            piece = current
        else:
            tag, value = current
            if tag == "scalar":
                if value is None:
                    piece = b"null"
                elif type(value) is bool:
                    piece = b"true" if value else b"false"
                elif type(value) is int:
                    piece = str(value).encode("ascii")
                else:
                    piece = json.encoder.encode_basestring_ascii(value).encode("ascii")
            elif tag in ("list", "tuple"):
                piece = b"["
                pending.append(b"]")
                for index in range(len(value) - 1, -1, -1):
                    pending.append(value[index])
                    if index:
                        pending.append(b",")
            else:
                piece = b"{"
                pending.append(b"}")
                for index in range(len(value) - 1, -1, -1):
                    key, child = value[index]
                    pending.extend((child, b":", ("scalar", key)))
                    if index:
                        pending.append(b",")
        length += len(piece)
        if length > byte_limit:
            raise ValueError("Historical descriptor encoded byte bound exceeded")
        encoded.write(piece)
    return encoded.getvalue()


def _unchanged(witnesses):
    """Refuse observed container writes during capture, without user equality."""
    for container, kind, before in witnesses:
        if type(container) is not kind or len(container) != len(before):
            raise ValueError("Historical descriptor changed during capture")
        after = tuple(dict.items(container)) if kind is dict else tuple(container)
        if kind is dict:
            same = all(a[0] is b[0] and a[1] is b[1] for a, b in zip(after, before, strict=True))
        else:
            same = all(a is b for a, b in zip(after, before, strict=True))
        if not same:
            raise ValueError("Historical descriptor changed during capture")


def _parts(graph, limits):
    """Capture immutable metadata once; callers decide its transport shape."""
    stage, tree, payload = "input", None, None
    try:
        limits = _limits(limits)
        if (
            type(graph) is not tuple
            or len(graph) != 2
            or type(graph[0]) is not tuple
            or type(graph[1]) is not dict
        ):
            raise ValueError("Exact captured raw-object tuple and descriptor dictionary required")
        stage = "immutable_tree"
        tree, witnesses = _tree(graph[1], limits)
        stage = "canonical_bytes"
        payload = _encode(tree, limits[2])
        stage = "identity"
        identity = hashlib.sha256(payload).hexdigest()
        stage = "capture_recheck"
        _unchanged(witnesses)
        return tree, payload, identity
    except BaseException as error:
        raise MetadataRejected(
            "Historical metadata freezing failed",
            graph=graph,
            stage=stage,
            source_error=error,
            partial=(tree, payload),
        ) from error


def freeze_graph(graph, *, limits=DEFAULT_LIMITS):
    """Freeze a fresh ``(raw_objects, descriptor)`` capture, before publication.

    The exact supported domain is dict/list/tuple/str/int/bool/None. The YAML
    producer already represents floats and bytes as strings. Unsupported input
    refuses; there is no conversion, fallback, authority issuance or owner reuse.
    Observers must remain guarded by the caller: this is not an atomic snapshot
    of concurrently mutable native state, nor a detector of writes after return.
    """
    _, payload, identity = _parts(graph, limits)
    return FrozenGraph(graph[0], payload, identity)


def require_retained(image, *, retained_image, retained_objects):
    """Check the caller's exact image/reference edges, never successful history.

    The caller must obtain and retain these arguments at its genuine capture
    boundary. Matching bytes, a new tuple, or a supplied image is not a substitute.
    This deliberately says nothing about the current contents of raw objects.
    """
    if (
        type(image) is not FrozenGraph
        or image is not retained_image
        or type(retained_objects) is not tuple
        or image.raw_objects is not retained_objects
        or type(image.descriptor_bytes) is not bytes
        or type(image.descriptor_sha256) is not str
    ):
        raise ValueError("Exact retained immutable metadata and raw-reference edges required")
    return image


def export_descriptor(image):
    """Return an independent wire view; editing it never changes the image."""
    if type(image) is not FrozenGraph or type(image.descriptor_bytes) is not bytes:
        raise TypeError("Exact immutable graph metadata required")
    return json.loads(image.descriptor_bytes)


class HistoricalDescriptor:
    """Deeply immutable historical metadata with fresh-descriptor comparison.

    The registry authenticates immutable fields/issuance only; it contains no
    mutable descriptor or successful live validation. No native owner is issued.
    """

    __slots__ = ("_seal", "__weakref__")
    __hash__ = None

    def __new__(cls):
        raise TypeError("Use a fresh producer capture through freeze_history_graph")

    def __setattr__(self, name, value):
        raise AttributeError("Historical descriptor fields are immutable")

    def __eq__(self, other):
        row = _history_entry(self)
        if type(other) is HistoricalDescriptor:
            other_row = _history_entry(other)
            result = row[1] == other_row[1] and row[2] == other_row[2]
        elif type(other) is dict:
            result = _matches(other, row[2])
        else:
            return False
        if _history_entry(self) is not row:
            raise ValueError("Historical metadata association changed during comparison")
        if type(other) is HistoricalDescriptor and _history_entry(other) is not other_row:
            raise ValueError("Historical comparison peer changed")
        return result

    def __ne__(self, other):
        result = self.__eq__(other)
        return NotImplemented if result is NotImplemented else not result


def _history_entry(descriptor):
    if type(descriptor) is not HistoricalDescriptor:
        raise TypeError("Exact issued historical descriptor required")
    row = _HISTORY_ISSUED.get(id(descriptor))
    if (
        type(row) is not tuple
        or len(row) != 4
        or object.__getattribute__(descriptor, "_seal") is not row
        or type(row[0]) is not weakref.ReferenceType
        or type(row[1]) is not bytes
        or type(row[2]) is not tuple
        or type(row[3]) is not str
        or row[0]() is not descriptor
    ):
        raise ValueError("Historical descriptor issuance/immutable field association changed")
    return row


def _forget_history(identity, reference):
    row = _HISTORY_ISSUED.get(identity)
    if row is not None and row[0] is reference:
        del _HISTORY_ISSUED[identity]


def _matches(actual, tree):
    """Fresh exact-type comparison, without freezing, hashing, or JSON decoding.

    The expected immutable tree bounds traversal. List versus tuple and exact
    scalar types remain distinct even though their canonical JSON can coincide.
    """
    pending = [(actual, tree)]
    while pending:
        item, expected = pending.pop()
        tag, value = expected
        if tag == "scalar":
            if type(item) is not type(value) or item != value:
                return False
        elif tag in ("list", "tuple"):
            kind = list if tag == "list" else tuple
            if type(item) is not kind or len(item) != len(value):
                return False
            pending.extend(zip(item, value, strict=True))
        else:
            if type(item) is not dict or len(item) != len(value):
                return False
            if any(type(key) is not str for key in item):
                return False
            for key, child in value:
                if key not in item:
                    return False
                pending.append((dict.__getitem__(item, key), child))
    return True


def freeze_history_graph(graph, *, limits=DEFAULT_LIMITS):
    """Opt-in producer boundary only; return the existing exact two-tuple shape."""
    tree, payload, identity = _parts(graph, limits)
    descriptor, row, token = None, None, None
    try:
        descriptor = object.__new__(HistoricalDescriptor)
        token = id(descriptor)
        reference = weakref.ref(descriptor, lambda ref: _forget_history(token, ref))
        row = (reference, payload, tree, identity)
        object.__setattr__(descriptor, "_seal", row)
        _HISTORY_ISSUED[token] = row
        if _history_entry(descriptor) is not row:
            raise ValueError("Historical descriptor publication changed")
        return graph[0], descriptor
    except BaseException as error:
        secondary = ()
        try:
            if row is not None and _HISTORY_ISSUED.get(token) is row:
                del _HISTORY_ISSUED[token]
        except BaseException as cleanup:
            secondary = (cleanup,)
        failure = MetadataRejected(
            "Historical metadata publication failed",
            graph=graph,
            stage="history_issuance",
            source_error=error,
            partial=(tree, payload, descriptor, row),
        )
        failure.capture_errors = secondary
        raise failure from error


def history_digest(descriptor):
    """Read the immutable image's digest, after exact association validation."""
    return _history_entry(descriptor)[3]


def history_wire_descriptor(descriptor):
    """Export a fresh original JSON-compatible descriptor, never a live owner."""
    row = _history_entry(descriptor)
    result = json.loads(row[1])
    if _history_entry(descriptor) is not row:
        raise ValueError("Historical metadata changed during wire export")
    return result


def history_bindings():
    """Current helper/class atoms for the existing parameter authority roster."""
    atoms = [
        _HISTORY_ISSUED,
        HISTORY_FORMAT,
        DEFAULT_LIMITS,
        MAX_NODES,
        MAX_DEPTH,
        MAX_BYTES,
        __file__,
        __name__,
        BytesIO,
        BytesIO.write,
        BytesIO.getvalue,
    ]
    for function in (
        _limits,
        _tree,
        _encode,
        _unchanged,
        _parts,
        _history_entry,
        _forget_history,
        _matches,
        freeze_history_graph,
        history_digest,
        history_wire_descriptor,
        history_bindings,
        HistoricalDescriptor.__new__,
        HistoricalDescriptor.__setattr__,
        HistoricalDescriptor.__eq__,
        HistoricalDescriptor.__ne__,
        MetadataRejected.__init__,
        json.loads,
    ):
        atoms.extend(
            (
                function,
                function.__code__,
                function.__defaults__,
                function.__kwdefaults__,
                function.__closure__,
                function.__globals__,
                function.__builtins__,
            )
        )
        # Keyword-default mappings are mutable in place. Their identity alone
        # cannot bind limits or json.loads hooks used by a later wire export.
        if function.__kwdefaults__ is not None:
            for name, value in function.__kwdefaults__.items():
                atoms.extend((name, value))
        pending, resolved = [function.__code__], set()
        while pending:
            code = pending.pop()
            pending.extend(value for value in code.co_consts if type(value) is CodeType)
            for name in code.co_names:
                if name in resolved:
                    continue
                resolved.add(name)
                namespace = (
                    function.__globals__ if name in function.__globals__ else function.__builtins__
                )
                if name in namespace:
                    atoms.extend((namespace, name, namespace[name]))
    for cls in (HistoricalDescriptor, MetadataRejected):
        atoms.extend((cls, cls.__mro__))
        for name, value in vars(cls).items():
            atoms.extend((name, value))
    atoms.extend(
        (
            hashlib,
            hashlib.sha256,
            json,
            json.loads,
            json.encoder,
            json.encoder.encode_basestring_ascii,
            weakref,
            weakref.ref,
            weakref.ReferenceType,
        )
    )
    return tuple(atoms)
