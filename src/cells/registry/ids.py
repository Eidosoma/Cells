"""The ID grammar (D345, D371; docs/ID_HIERARCHY_DESIGN.md §2 and §3).

- **A piece's ID** is `namespace.family.name@major`: a law's, a kind's, an operator's, a model's, a
  solver's, a heat choice's or an execution choice's. **An interface's ID** is
  `namespace.name@major`. A schema's keeps its name, of two or more parts, the second never a
  family word. Pieces, interfaces and schemas never share a slot, so a slot says which it holds.
- **The families of the reserved `cells` namespace are a closed list:** the fixed words, and one
  word for each law interface (LAW_FAMILIES, those words' only home). The interface decides a law's
  family, never its folder, and every operator's family is `operator`.
- **In another namespace** the words `kind`, `operator` and `model` hold, a law of a `cells`
  interface takes that interface's word, and an outside interface declares its own word beside
  itself.
- **A refusal has one wording** (`reason`), which each site writes after its slot: an old spelling
  is refused by naming its new ID, from the table of renamed IDs (registry/renamed_ids.py), and
  anything else for its shape or its family. A slot that takes a plain word or an ID checks its
  words first.

Pure functions of strings: this module imports that table and nothing else from Cells, so the
registries and the parsers may both import it.
"""

import re
from types import MappingProxyType
from typing import NamedTuple

from cells.registry.renamed_ids import RENAMED

__all__ = (
    "FAMILIES",
    "FIXED_FAMILIES",
    "LAW_FAMILIES",
    "NAMESPACE",
    "RENAMED",
    "SUBLAW_FAMILIES",
    "Parts",
    "interface",
    "own_word",
    "parts",
    "piece",
    "reason",
    "refuse_old",
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
        "cells.transfer_factor_law@1": "transfer_factor",
        "cells.exchange_law@1": "exchange",
        "cells.reaction_law@1": "reaction",
        "cells.rate_factor_law@1": "rate_factor",
        "cells.rate_factor_law@2": "rate_factor",
        "cells.free_energy_term@1": "free_energy",
        "cells.population_structure@1": "population",
        "cells.assembly_geometry@1": "assembly_geometry",
        "cells.assembly_hazard@1": "assembly_hazard",
        "cells.assembly_observable@1": "assembly_observable",
        "cells.assembly_representation@1": "assembly_representation",
    }
)
# The words of the pieces that no registry holds (D383): a law inside an operator or a kind, a fuel
# kind, a lookup table's key. Such a piece may also take an interface's word, as the two other
# transfer factors do: each word has one place.
SUBLAW_FAMILIES = (
    "analysis",
    "damage",
    "field_closure",
    "fuel_kind",
    "junction_formation",
    "potential_set",
    "regulation",
    "site_binding",
    "site_internalisation",
    "species_reaction",
    "topology",
)
FAMILIES = frozenset({*FIXED_FAMILIES, *LAW_FAMILIES.values(), *SUBLAW_FAMILIES})

_PART = r"[a-z][a-z0-9_]*"
_NAME = r"[a-z][A-Za-z0-9_]*"  # Names are kept, and one has upper case.
_MAJOR = r"[1-9][0-9]*"
_PIECE = re.compile(rf"({_PART})\.({_PART})\.({_NAME})@({_MAJOR})")
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
    """Whether `value` is an interface's ID."""
    return isinstance(value, str) and _INTERFACE.fullmatch(value) is not None


def own_word(value):
    """Whether `value` may be an outside interface's own family word: none of the cells words."""
    return isinstance(value, str) and bool(re.fullmatch(_PART, value)) and value not in FAMILIES


def reason(value, *, family=None, what="a piece"):
    """Why `value` is not the ID of `what` (of `family`, where given), or None where it is: the one
    wording of a refusal."""
    if isinstance(value, str) and value in RENAMED:
        return f"{value} was renamed {RENAMED[value]} (D345)"
    match = _match(value)
    if match is None:
        shaped = _PIECE.fullmatch(value) if isinstance(value, str) else None
        if shaped is not None:
            return f"{value}: {shaped[2]} is not a family of the {NAMESPACE} namespace (D345)"
        return f"{value} is not namespace.family.name@major (D345)"
    if family not in (None, match[2]):
        return f"{what}'s ID is {match[1]}.{family}.<name>@major"
    return None


def _first_old(value):
    """(slot, spelling) of the first old spelling in JSON-like data, or None."""
    if isinstance(value, str):
        return ("", value) if value in RENAMED else None
    if isinstance(value, dict):
        for key, item in value.items():
            if key in RENAMED:
                return "", key
            found = _first_old(item)
            if found is not None:
                return f".{key}{found[0]}", found[1]
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _first_old(item)
            if found is not None:
                return f"[{index}]{found[0]}", found[1]
    return None


def refuse_old(data, error=ValueError):
    """Refuse JSON-like data that holds an old spelling, as a value or as a mapping's key, naming
    the slot of the first."""
    found = _first_old(data)
    if found is not None:
        slot, spelling = found
        raise error(f"{slot.lstrip('.')}: {reason(spelling)}")
