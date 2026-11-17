"""The operator section of the build's registry (docs/CORE_SEAMS_DESIGN.md §8.4).

Operators register the way kinds do (core/kind_registry.py):
- one registration call, `registry.register(operator)`, with an operator class or its one
  instance. It runs the operator contract's check_declarations (models/operators/contract.py) at
  registration, and refuses a second operator under one namespaced ID, whatever the spelling;
- namespaced IDs: an operator's LAW_ID, a bare ID being in `cells`;
- the built-in operators register on BUILTIN from their own package, loaded by name
  (BUILTIN_PACKAGE), through the call an outside package uses;
- the active section is BUILTIN, unless a caller builds inside `scope(section)`.

OPERATORS is the active section as a mapping: each operator's instance under its LAW_ID as
declared, in registration order. Lookup is by that exact key, as today's dictionary's was, because
definitions and the composite's checks compare operator law IDs as strings. Assigning an operator
under its LAW_ID registers it, check_declarations included. Deleting one unregisters it, for a
planted operator that a test or a control registers only for its block.
"""

import importlib
from collections.abc import MutableMapping
from contextlib import contextmanager
from contextvars import ContextVar

from cells.core.kind_registry import qualified

__all__ = ("BUILTIN", "BUILTIN_PACKAGE", "OPERATORS", "OperatorRegistry", "active", "scope")


class OperatorRegistry:
    """Registered operators by namespaced ID, each one instance, in registration order."""

    def __init__(self):
        self._operators = {}

    def register(self, operator):
        """The one registration call: an operator class (or its one instance), checked by the
        contract's check_declarations, held under its namespaced LAW_ID. Returns the instance."""
        # Imported here: the built-in package's __init__ registers its operators on this module.
        from cells.models.operators.contract import check_declarations

        cls = operator if isinstance(operator, type) else type(operator)
        check_declarations(cls)
        key = qualified(cls.LAW_ID)
        known = self._operators.get(key)
        if known is not None and (known is operator or (operator is cls and type(known) is cls)):
            return known
        if known is not None:
            raise ValueError(f"Operator {key} is already registered")
        instance = cls() if operator is cls else operator
        self._operators[key] = instance
        return instance

    def lookup(self, law_id):
        """The operator of a law ID, in either spelling (a bare ID is in cells)."""
        key = qualified(law_id)
        if key not in self._operators:
            raise KeyError(f"No registered operator {key}")
        return self._operators[key]

    def unregister(self, law_id):
        """Remove a registered operator (a planted one, after its block)."""
        key = qualified(law_id)
        if key not in self._operators:
            raise KeyError(f"No registered operator {key}")
        del self._operators[key]

    def __contains__(self, law_id):
        return isinstance(law_id, str) and bool(law_id) and qualified(law_id) in self._operators

    def operators(self):
        """The registered instances, in registration order."""
        return tuple(self._operators.values())

    def extended(self, *operators):
        """A new section holding this one's operators, then `operators`; this one is unchanged."""
        out = OperatorRegistry()
        for operator in (*self._operators.values(), *operators):
            out.register(operator)
        return out


class _ActiveOperators(MutableMapping):
    """The active section as a mapping (module docstring): keys are the LAW_IDs as declared."""

    def __getitem__(self, law_id):
        if isinstance(law_id, str) and law_id:
            operator = active()._operators.get(qualified(law_id))
            if operator is not None and operator.LAW_ID == law_id:
                return operator
        raise KeyError(law_id)

    def __iter__(self):
        return iter(tuple(op.LAW_ID for op in active().operators()))

    def __len__(self):
        return len(active().operators())

    def __setitem__(self, law_id, operator):
        if getattr(operator, "LAW_ID", None) != law_id:
            raise ValueError(f"An operator is registered under its own LAW_ID, not {law_id!r}")
        if isinstance(operator, type):
            raise ValueError(f"OPERATORS holds instances; register {law_id}'s class or instance")
        active().register(operator)

    def __delitem__(self, law_id):
        self[law_id]  # noqa: B018  (the exact key, or KeyError)
        active().unregister(law_id)

    def __repr__(self):
        return f"OPERATORS({dict(self)!r})"


BUILTIN = OperatorRegistry()
_ACTIVE = ContextVar("cells_operator_registry", default=None)
BUILTIN_PACKAGE = "cells.models.operators"
_builtins_loaded = False
OPERATORS = _ActiveOperators()


def _load_builtins():
    """Import the built-in operators' package once (by name), which registers them on BUILTIN."""
    global _builtins_loaded
    if not _builtins_loaded:
        importlib.import_module(BUILTIN_PACKAGE)
        _builtins_loaded = True


def active():
    """The operator section of the model build in progress: BUILTIN, with the built-in operators
    registered, unless scope() says otherwise."""
    section = _ACTIVE.get()
    if section is not None:
        return section
    _load_builtins()
    return BUILTIN


@contextmanager
def scope(section):
    """Build (parse, bind, run) with `section` as the operator lookup, restored on exit."""
    token = _ACTIVE.set(section)
    try:
        yield section
    finally:
        _ACTIVE.reset(token)
