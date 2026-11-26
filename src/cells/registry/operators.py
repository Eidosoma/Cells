"""The operator section of the build's registry (docs/CORE_SEAMS_DESIGN.md §8.4).

Operators register the way kinds do (registry/kind_registry.py):
- one registration call, `registry.register(operator)`, with an operator class or its one
  instance. It runs the operator contract's check_declarations (operators/contract.py) at
  registration, and refuses a second operator under one ID;
- one spelling: an operator's LAW_ID is `namespace.operator.name@major` (registry/ids.py);
- the built-in operators register on BUILTIN from their own homes, the static model table's
  `operator_homes` (registry/model_table.py), loaded by name once, the composite's package
  (BUILTIN_PACKAGE) first, through the call an outside package uses;
- the active section is BUILTIN, unless a caller builds inside `scope(section)`;
- one object per `cells` operator ID in every section: another section holds a cells operator
  only as BUILTIN's own instance, because the composite caches its compositions on operator law
  IDs (models/pump_composite.implementation). An outside operator takes its own namespace.

**The composite's operators and a family's own.** The contract above is the composite's
(`cells.operator@1`). A model family whose operators are not the composite's, such as the assembly
lineages' fission and continuation, declares each on the operator template, `FamilyOperator`: its
ID, the model that runs it (`host`), its family's interface (a `cells` one declared in the family's
row of the model table) and what it rests on, as a law does (registry/laws.py). Its own type
checks its own fields at registration (`errors()`), in place of the composite's contract. The same
call registers it, and the section holds it apart: `operators()`, `lookup` and OPERATORS are the
composite's alone, so no composite definition can name a family's operator, and
`family_operators()` lists the families'. One namespaced ID names one operator across both.

OPERATORS is the active section's composite operators as a mapping: each operator's instance under
its LAW_ID as declared, in registration order. Lookup is by that exact key, as today's
dictionary's was, because definitions and the composite's checks compare operator law IDs as
strings. Assigning an operator under its LAW_ID registers it, check_declarations included.
Deleting one unregisters it, for a planted operator that a test or a control registers only for
its block.

**A package of operators** registers through `register_package` (docs/CORE_SEAMS_DESIGN.md §18,
the further hand-offs): every operator its modules define, the order it names first, then the rest
by module name. So a new operator module joins the section with no edit to its package's
`__init__`; the composite's package (operators/__init__.py) registers this way.
"""

import importlib
import pkgutil
import sys
from collections.abc import MutableMapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import KW_ONLY, dataclass
from types import MappingProxyType
from typing import ClassVar

from cells.registry import ids
from cells.registry import laws as law_registry
from cells.registry.kind_registry import NAMESPACE, qualified
from cells.registry.model_table import MODELS

__all__ = (
    "BUILTIN",
    "BUILTIN_PACKAGE",
    "COMPOSITE_INTERFACE",
    "FamilyOperator",
    "OPERATORS",
    "OperatorRegistry",
    "active",
    "operator_species_moieties",
    "operator_standard_free_energies",
    "package_operators",
    "register_package",
    "scope",
)

COMPOSITE_INTERFACE = "cells.operator@1"  # The composite's operator contract.


@dataclass(frozen=True)
class FamilyOperator:
    """The operator template of a family's own operators (module docstring): what every such
    operator declares. A family's type is built on it, adds its own fields after `operator_id`,
    sets its `interface` and checks its own fields in `errors()`, calling this one first.

    - `operator_id`: `namespace.operator.name@major`, named for what it does;
    - `host`: the ID of the model that runs it;
    - `provenance`, `source` and `test`: as the law template's (registry/laws.py).
    """

    operator_id: str
    _: KW_ONLY
    host: str
    provenance: str = "parity"
    source: object = None
    test: str | None = None

    interface: ClassVar[str | None] = None
    UNITS: ClassVar = MappingProxyType({})  # {own field: unit}
    SIGNS: ClassVar = MappingProxyType({})  # {own field: its sign convention}

    def errors(self):
        """Why this declaration breaks the template (empty: it keeps it)."""
        out = []
        why = ids.reason(self.operator_id, family="operator", what="an operator")
        if why is not None:
            out.append(why)
        interface = type(self).interface
        if not ids.interface(interface):
            out.append("its type declares a namespaced interface ID with its major")
        elif interface.split(".", 1)[0] == NAMESPACE and interface not in (
            law_registry.FAMILY_INTERFACES
        ):
            out.append(
                f"{interface} is not a family's interface: a family operator's cells interface "
                "is one its family declares in the model table (the composite's is "
                f"{COMPOSITE_INTERFACE}, its contract's)"
            )
        if (why := ids.reason(self.host, family="model", what="a model")) is not None:
            out.append(f"its host, the model that runs it: {why}")
        return out + law_registry.source_errors(self.provenance, self.source, self.test, "operator")


class OperatorRegistry:
    """Registered operators by namespaced ID: the composite's, each one instance, in registration
    order; and the families' own (FamilyOperator declarations), apart."""

    def __init__(self):
        self._operators = {}
        self._family = {}  # {namespaced ID: a family's operator declaration}
        self._modules = {}  # {namespaced ID: the module that registered a family's operator}

    def register(self, operator):
        """The one registration call. The composite's operator class (or its one instance) is
        checked by the contract's check_declarations and held under its namespaced LAW_ID; a
        family's operator declaration is checked by its own type, held apart, with the module
        that called this (its declaring module). Returns what is held."""
        if isinstance(operator, FamilyOperator):
            return self._register_family(operator, sys._getframe(1).f_globals.get("__name__"))
        # Imported here: the built-in package's __init__ registers its operators on this module.
        from cells.operators.contract import check_declarations

        cls = operator if isinstance(operator, type) else type(operator)
        check_declarations(cls)
        key = cls.LAW_ID
        if (why := ids.reason(key, family="operator", what="an operator")) is not None:
            raise ValueError(f"Operator {key!r}: {why}")
        known = self._operators.get(key)
        if known is not None and (known is operator or (operator is cls and type(known) is cls)):
            return known
        if known is not None or key in self._family:
            raise ValueError(f"Operator {key} is already registered")
        instance = cls() if operator is cls else operator
        if self is not BUILTIN and key.split(".", 1)[0] == NAMESPACE:
            _load_builtins()
            builtin = BUILTIN._operators.get(key)
            if builtin is None or type(builtin) is not cls:
                raise ValueError(
                    f"Operator {key} is in the cells namespace: another section holds a cells "
                    "operator only as BUILTIN's own (one object per cells ID)"
                )
            instance = builtin
        self._operators[key] = instance
        return instance

    def _register_family(self, declaration, module):
        problems = declaration.errors()
        if problems:
            raise ValueError(f"Operator {declaration.operator_id!r}: " + "; ".join(problems))
        key = qualified(declaration.operator_id)
        known = self._family.get(key)
        if known is declaration:
            return declaration
        if known is not None or key in self._operators:
            raise ValueError(f"Operator {key} is already registered")
        if self is not BUILTIN and key.split(".", 1)[0] == NAMESPACE:
            _load_builtins()
            if BUILTIN._family.get(key) is not declaration:
                raise ValueError(
                    f"Operator {key} is in the cells namespace: another section holds a cells "
                    "operator only as BUILTIN's own (one object per cells ID)"
                )
        self._family[key] = declaration
        self._modules[key] = module
        return declaration

    def lookup(self, law_id):
        """The composite's operator of a law ID."""
        key = qualified(law_id)
        if key not in self._operators:
            raise KeyError(f"No registered operator {key}")
        return self._operators[key]

    def unregister(self, law_id):
        """Remove a registered operator, the composite's or a family's (a planted one, after its
        block)."""
        key = qualified(law_id)
        if key in self._operators:
            del self._operators[key]
        elif key in self._family:
            del self._family[key]
            self._modules.pop(key, None)
        else:
            raise KeyError(f"No registered operator {key}")

    def __contains__(self, law_id):
        return isinstance(law_id, str) and law_id in self._operators

    def operators(self):
        """The composite's registered instances, in registration order."""
        return tuple(self._operators.values())

    def family_operators(self, interface=None, host=None):
        """The families' operator declarations, in canonical (sorted namespaced ID) order: all, or
        those of `interface` that `host` runs, as a family finds its operators."""
        return tuple(
            declaration
            for _, declaration in sorted(self._family.items())
            if (interface is None or type(declaration).interface == interface)
            and (host is None or qualified(declaration.host) == qualified(host))
        )

    def module(self, operator_id):
        """The module that registered a family's operator (its declaring module), or None."""
        return self._modules.get(qualified(operator_id))

    def extended(self, *operators):
        """A new section holding this one's operators (BUILTIN's with its built-ins registered),
        then `operators`; this one is unchanged."""
        if self is BUILTIN:
            _load_builtins()
        caller = sys._getframe(1).f_globals.get("__name__")
        out = OperatorRegistry()
        for operator in self._operators.values():
            out.register(operator)
        for declaration in self._family.values():
            out.register(declaration)
        out._modules.update(self._modules)  # Each copied declaration keeps its declaring module.
        for operator in operators:
            new = isinstance(operator, FamilyOperator) and (
                qualified(operator.operator_id) not in out._family
            )
            out.register(operator)
            if new:
                out._modules[qualified(operator.operator_id)] = caller
        return out


def operator_standard_free_energies(operator, declaration):
    """A composite operator's reaction-level standard free energies (seam E: the contract's
    Operator.standard_free_energies), checked as a kind's are (kind_registry.free_energy_entries),
    with no law to name: an operator hosts none, so each entry's law_id and mode are None, and an
    entry that names a law is refused."""
    from cells.registry import kind_registry

    entries = operator.standard_free_energies(declaration)
    where = f"Operator {operator.LAW_ID}'s standard_free_energies"
    return kind_registry.free_energy_entries(entries, {}, where)


def operator_species_moieties(operator, declaration):
    """A composite operator's net moves (the contract's Operator.species_moieties), checked: a
    tuple of (move name, ((species, nu), ...)), each name a non-empty string used once, each
    stoichiometry non-empty with distinct named species and nonzero integer counts. Refused
    (ValueError, naming the operator) otherwise; the species registry's check_moieties reads it."""
    where = f"Operator {operator.LAW_ID}'s species_moieties"
    moves = operator.species_moieties(declaration)
    shape = f"{where} returns a tuple of (move name, ((species, nu), ...))"
    if not isinstance(moves, tuple):
        raise ValueError(shape)
    names, out = set(), []
    for item in moves:
        if not (isinstance(item, tuple) and len(item) == 2):
            raise ValueError(shape)
        name, stoichiometry = item
        if not (isinstance(name, str) and name):
            raise ValueError(shape)
        if name in names:
            raise ValueError(f"{where}: move {name!r} is named twice")
        names.add(name)
        pairs = stoichiometry if isinstance(stoichiometry, tuple) else ()
        if not pairs or not all(
            isinstance(pair, tuple)
            and len(pair) == 2
            and isinstance(pair[0], str)
            and pair[0]
            and type(pair[1]) is int
            and pair[1] != 0
            for pair in pairs
        ):
            raise ValueError(f"{where}: move {name!r} is a non-empty ((species, nonzero int), ...)")
        if len({species for species, _ in pairs}) != len(pairs):
            raise ValueError(f"{where}: move {name!r} names a species twice")
        out.append((name, pairs))
    return tuple(out)


def package_operators(package):
    """The composite operators a package's modules define, in module-name order and then in each
    module's own order (the order its namespace binds them).

    Every module directly in the package is imported by name, in sorted order, and an import that
    fails raises; a subpackage is refused, so no operator can sit where this does not look. An
    operator is a class that a module defines (its `__module__` is that module), a subclass of the
    contract's Operator (operators/contract.py), with a law ID of its own (a string LAW_ID in the
    class's own namespace): an imported class is its defining module's, an intermediate base
    declares no LAW_ID, and a subclass that only inherits one is not a second operator."""
    from cells.operators.contract import Operator

    root = importlib.import_module(package)
    found = []
    for info in sorted(pkgutil.iter_modules(root.__path__), key=lambda info: info.name):
        name = f"{root.__name__}.{info.name}"
        if info.ispkg:
            raise ValueError(f"{name}: an operator package holds modules, not subpackages")
        module = importlib.import_module(name)
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and value.__module__ == module.__name__
                and issubclass(value, Operator)
                and isinstance(vars(value).get("LAW_ID"), str)
                and value not in found
            ):
                found.append(value)
    return tuple(found)


def register_package(section, package, *, first=()):
    """Register every composite operator of `package` (package_operators) on `section`, through
    its one registration call (check_declarations included): `first`, in its order, then the
    others in package_operators' order. A new operator module so joins with no edit to the
    package's `__init__`. `first` names only operators the package defines. Returns the
    registered instances, in registration order."""
    found = package_operators(package)
    stray = [cls for cls in first if cls not in found]
    if stray or len(set(first)) != len(first):
        raise ValueError(
            f"Package {package}: `first` names each of its own operators once, not "
            + ", ".join(f"{cls.__module__}.{cls.__qualname__}" for cls in stray or first)
        )
    ordered = (*first, *(cls for cls in found if cls not in first))
    return tuple(section.register(cls) for cls in ordered)


class _ActiveOperators(MutableMapping):
    """The active section as a mapping (module docstring): keys are the LAW_IDs as declared."""

    def __getitem__(self, law_id):
        operator = active()._operators.get(law_id) if isinstance(law_id, str) else None
        if operator is None:
            raise KeyError(law_id)
        return operator

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
BUILTIN_PACKAGE = "cells.operators"  # The composite's operators: registered first.
# Every model's `operator_homes` in the static model table (registry/model_table.py), in its order,
# after the composite's package.
BUILTIN_HOMES = tuple(
    dict.fromkeys(
        (BUILTIN_PACKAGE, *(home for model in MODELS.values() for home in model.operator_homes))
    )
)
_builtins_loaded = False
OPERATORS = _ActiveOperators()


def _load_builtins():
    """Import the built-in operators' homes once (by name), which register them on BUILTIN."""
    global _builtins_loaded
    if not _builtins_loaded:
        for name in BUILTIN_HOMES:
            importlib.import_module(name)
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
