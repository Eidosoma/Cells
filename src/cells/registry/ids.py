"""The ID grammar (D345, D371; docs/ID_HIERARCHY_DESIGN.md §2 and §3).

- **A piece's ID** is `namespace.family.name@major`: a law's, a kind's, an operator's, a model's, a
  solver's, a heat choice's or an execution choice's. **An interface's or a schema's ID** is
  `namespace.name@major`. The two never share a slot.
- **The families of the reserved `cells` namespace are a closed list:** the fixed words, and one
  word for each law interface (LAW_FAMILIES, those words' only home). The interface decides a law's
  family, never its folder, and every operator's family is `operator`.
- **In another namespace** the words `kind`, `operator` and `model` hold, a law of a `cells`
  interface takes that interface's word, and an outside interface declares its own word beside
  itself.

Pure functions of strings: this module imports nothing from Cells, so the registries and the
parsers may both import it. No parse site checks an ID against it yet: they do once every live ID
has moved (D345).
"""

import re
from types import MappingProxyType
from typing import NamedTuple

__all__ = (
    "FAMILIES",
    "FIXED_FAMILIES",
    "LAW_FAMILIES",
    "NAMESPACE",
    "Parts",
    "interface",
    "parts",
    "piece",
)

NAMESPACE = "cells"  # Reserved: the built-in pieces' namespace.
FIXED_FAMILIES = ("model", "operator", "kind", "solver", "heat", "execution")
LAW_FAMILIES = MappingProxyType(  # {a law interface: its laws' family}
    {
        "cells.channel_law@1": "channel",
        "cells.cycle_law@1": "cycle",
        "cells.route_law@1": "route",
        "cells.junction_law@1": "junction",
        "cells.binding_law@1": "binding",
        "cells.channel_block_law@1": "channel_block",
        "cells.exchange_law@1": "exchange",
        "cells.reaction_law@1": "reaction",
        "cells.rate_factor_law@1": "rate_factor",
        "cells.rate_factor_law@2": "rate_factor",
        "cells.free_energy_term@1": "free_energy",
        "cells.population_structure@1": "population",
        "cells.assembly_geometry@1": "assembly_geometry",
        "cells.assembly_hazard@1": "assembly_hazard",
        "cells.assembly_representation@1": "assembly_representation",
    }
)
FAMILIES = frozenset({*FIXED_FAMILIES, *LAW_FAMILIES.values()})

_PART = r"[a-z][a-z0-9_]*"
_MAJOR = r"[1-9][0-9]*"
_PIECE = re.compile(rf"({_PART})\.({_PART})\.({_PART})@({_MAJOR})")
_INTERFACE = re.compile(rf"{_PART}\.{_PART}@{_MAJOR}")


class Parts(NamedTuple):
    """A piece's ID, taken apart."""

    namespace: str
    family: str
    name: str
    major: int


def _match(value):
    """The match of a piece's ID, or None: in the cells namespace its family is one of FAMILIES."""
    match = _PIECE.fullmatch(value) if isinstance(value, str) else None
    if match is None or (match[1] == NAMESPACE and match[2] not in FAMILIES):
        return None
    return match


def piece(value, *, family=None):
    """Whether `value` is a piece's ID, of `family` where given."""
    match = _match(value)
    return match is not None and family in (None, match[2])


def parts(value):
    """The Parts of a piece's ID; ValueError for anything else."""
    match = _match(value)
    if match is None:
        raise ValueError(f"{value!r} is not namespace.family.name@major")
    namespace, family, name, major = match.groups()
    return Parts(namespace, family, name, int(major))


def interface(value):
    """Whether `value` is an interface's or a schema's ID."""
    return isinstance(value, str) and _INTERFACE.fullmatch(value) is not None
