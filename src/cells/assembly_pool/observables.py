"""What can be read from an assembly of finite_bond_assembly@1: its observables, as registered laws.

An observable (interface cells.assembly_observable@1) reads one assembly's occupied sites and its
bonds, as the pool's state holds them, and gives one of a few named values. It has no state, no
parameter and no number of its own.

**What its ID commits** is the readout: the value of each assembly. A change to that map takes a new
major. What a value does is data, declared beside the observable in the composed file that names it
(cells.assembly_pool.resolve): one level in [0, 1] for each value, the channel populations the level
scales, and the base schedule it multiplies. The ID says nothing of them. That an assembly's
topology sets a channel's availability at all is a hypothesis of the file that declares it.

**root_component_has_cycle@1** says whether the assembly has a closed ring of bonds. The pool keeps
its assembly connected to its root (engine.validate_state holds that at every accepted state), so
the assembly is one connected graph of V occupied sites and E bonds, and E - V + 1 of its cycles are
independent. It has a cycle exactly where E >= V, which is

    popcount(bonds) >= popcount(occupied).

This module is inert (docs/CORE_SEAMS_DESIGN.md section 8.2): it registers nothing, and the law
registry's loader registers its LAW through the static model table.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from cells.assembly_pool import MODEL_ID
from cells.modules import Citation, ConfigError, Law, hosted_laws, qualified

OBSERVABLE_INTERFACE = "cells.assembly_observable@1"  # Declared in @3's row of the model table.
HOST = MODEL_ID  # The pool's model, whose arrays an observable reads.
LAW_ID = "root_component_has_cycle@1"


@dataclass(frozen=True)
class AssemblyObservable(Law):
    """cells.assembly_observable@1: a readout of an assembly's topology (module docstring).

    Its kernel is a pure function in the xp style, of arrays of any one shape."""

    reads: tuple[str, ...]  # The fields of the pool's state it takes, in its kernel's order.
    values: tuple[str, ...]  # The names of its values, which a composed file's levels key.
    evaluate: Callable  # (*reads, *, xp) -> the index in `values` of each assembly's value.

    interface: ClassVar[str] = OBSERVABLE_INTERFACE

    def errors(self):
        out = super().errors()
        if qualified(self.host) != qualified(HOST):
            out.append(f"an observable is hosted by {HOST}")
        for name, least in (("reads", 1), ("values", 2)):
            given = getattr(self, name)
            if not (
                isinstance(given, tuple)
                and len(given) >= least
                and all(isinstance(v, str) and v for v in given)
                and len(set(given)) == len(given)
            ):
                out.append(f"its {name} are at least {least} distinct names")
        if not callable(self.evaluate):
            out.append("its evaluate is callable")
        return out


def registered():
    """{law ID: declaration} of the observables in the active law registry, in canonical order."""
    return {law.law_id: law for law in hosted_laws(OBSERVABLE_INTERFACE, HOST)}


def resolve(law_id):
    """The observable of this ID; ConfigError naming the registered ones for any other."""
    found = registered()
    if not isinstance(law_id, str) or law_id not in found:
        raise ConfigError(
            f"Unknown assembly observable {law_id!r}; registered: {', '.join(sorted(found))}"
        )
    return found[law_id]


def cycle_index(occupied, bonds, *, xp=np):
    """1 where the rooted, connected assembly has a cycle, 0 where it has none."""
    return xp.where(xp.bitwise_count(bonds) >= xp.bitwise_count(occupied), 1, 0)


LAW = AssemblyObservable(
    LAW_ID,
    ("occupied", "bonds"),
    ("false", "true"),
    cycle_index,
    host=HOST,
    provenance="cited",
    source=Citation(
        "The cycle rank of a connected graph, E - V + 1 (elementary graph theory), read from an "
        "assembly of finite_bond_assembly@1: a topology readout, no number",
        "docs/CAPSID_ASSEMBLY.md, 'Driving ionic channels from pools', which states the rule; its "
        "use as a channel's control is a hypothesis with no literature source",
        "no numbers taken: the levels of its values are a composed file's data",
        ("the pool keeps its assembly connected to its root, so one component is assumed",),
    ),
    test="tests/unit/test_assembly_pool.py"
    "::test_the_cycle_observable_is_the_cycle_rank_of_every_connected_assembly",
)
