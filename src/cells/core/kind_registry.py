"""The kind registry of resolved_pump_tissue@3 (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)).

A kind is one module's contribution to the inner model: its fields (state, layout, control and
observation columns) and optional hooks that the core calls at fixed seams. The core reaches
kinds only through the registry active for the model build: BUILTIN, unless a caller builds
inside `scope(registry)`. It imports no kind module. Built-in kinds (models/inner_kinds/)
register on BUILTIN exactly as an external package would, with `registry.register(kind)`.

IDs are namespaced ("cells.transporter@1"); a bare ID resolves in the `cells` namespace, so an
outside package cannot collide with a built-in. The canonical kind order, the order in which a
structure's kinds append their fields, is the sorted namespaced ID: total, and independent of
registration, import and declaration order.
"""

from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

NAMESPACE = "cells"


def qualified(identifier):
    """The namespaced form of a kind or law ID: a bare ID belongs to the cells namespace."""
    if not isinstance(identifier, str) or not identifier:
        raise ValueError(f"A kind or law ID must be a non-empty string, not {identifier!r}")
    head = identifier.split("@", 1)[0]
    return identifier if "." in head else f"{NAMESPACE}.{identifier}"


@dataclass(frozen=True, eq=False)
class Kind:
    """One kind's declaration (§7.4 (k)). Fields are appended in canonical kind order.

    state_axes: ((field, (axis, ...)), ...); layout_fields, control_fields and readout_columns:
    field names. Every hook is optional and pure, closing over the kind's declaration only.
    Scope rules (§7.4 (j), ruled): its ledger terms fold into today's ten ledgers by role; its
    state fields are observation columns right after today's state fields; its material moves
    land in the shared inventory; its controls are availabilities in [0, 1] unless
    control_domain says otherwise.
    """

    kind_id: str
    model_key: str
    state_axes: tuple = ()
    layout_fields: tuple = ()
    control_fields: tuple = ()
    readout_columns: tuple = ()
    parse: Callable | None = None
    to_dict: Callable | None = None
    structure_entry: Callable | None = None
    initial: Callable | None = None
    control_values: Callable | None = None
    stage_read: Callable | None = None
    rates: Callable | None = None
    book: Callable | None = None
    ledger_terms: Callable | None = None
    domain: Callable | None = None
    control_domain: Callable | None = None
    readouts: Callable | None = None
    moved_rows: Callable | None = None
    check_definition: Callable | None = None


class KindRegistry:
    """Registered kinds by namespaced ID. A registered kind that a definition does not declare
    changes nothing: no field, no hook call, no change to types, compile key or snapshot."""

    def __init__(self):
        self._kinds = {}

    def register(self, kind):
        key = qualified(kind.kind_id)
        known = self._kinds.get(key)
        if known is not None and known is not kind:
            raise ValueError(f"Kind {key} is already registered")
        clash = [k for k in self._kinds.values() if k.model_key == kind.model_key and k is not kind]
        if clash:
            raise ValueError(f"Kind {key}'s model key {kind.model_key!r} is already registered")
        self._kinds[key] = kind
        return kind

    def lookup(self, kind_id):
        key = qualified(kind_id)
        if key not in self._kinds:
            raise KeyError(f"No registered kind {key}")
        return self._kinds[key]

    def __contains__(self, kind_id):
        return qualified(kind_id) in self._kinds

    def model_keys(self):
        """{model key: kind} of every registered kind."""
        return {kind.model_key: kind for kind in self._kinds.values()}

    @staticmethod
    def canonical(kind_ids):
        """kind_ids, namespaced, distinct and in canonical (sorted) order."""
        return tuple(sorted({qualified(k) for k in kind_ids}))


BUILTIN = KindRegistry()
_ACTIVE = ContextVar("cells_kind_registry", default=None)


def active():
    """The registry of the model build in progress: BUILTIN unless scope() says otherwise."""
    return _ACTIVE.get() or BUILTIN


@contextmanager
def scope(registry):
    """Build (parse, bind, run) with `registry` as the kind lookup, restored on exit."""
    token = _ACTIVE.set(registry)
    try:
        yield registry
    finally:
        _ACTIVE.reset(token)
