"""G of a node's amounts, per world: the references' own SPEC.md §1.3 free energy.

The judge's C3b compares each heat the engine books with -dG of the engine's own saved
states, and AMENDMENT-2026-11-24 §2.2 has it take G from the references rather than from a
judge-side copy. This module exposes that one function. It is the same implementation the
reference heats are written from (``fr45ref_model.System.G``), at the references' working
precision.

    import sys
    sys.path.insert(0, "validation/fr45/references")
    from fr45ref_free_energy import G

    heat = float(G("W1", "well", amounts_at_start) - G("W1", "well", amounts_at_end))

``amounts`` maps every amount at the node to its value, named as the reference files'
trajectory names them: n:<ligand>@<node> for each free amount a law moves there, R:<set> for
each set facing the node and B:<population> for those sets' populations. No other key is
accepted and none may be missing. Each value enters exactly (a binary64 is converted without
rounding). The result is a decimal.Decimal at the working precision: subtract two and round
once. No engine module is imported.
"""

from __future__ import annotations

import decimal
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import fr45ref_hp as HP  # noqa: E402
import fr45ref_worlds as WL  # noqa: E402
from fr45ref_build import PROFILES  # noqa: E402
from fr45ref_model import System  # noqa: E402

DIGITS = PROFILES["reference"]["digits"]

_WORLDS = {
    "W1": WL.world_W1,
    "W1eq": WL.world_W1eq_inputs,  # G does not read the start, only V, S and the constants
    "W1p": WL.world_W1p,
    "W2": WL.world_W2,
    "W3": WL.world_W3,
    "W3p": WL.world_W3p,
    "W4": WL.world_W4,
    "W5": WL.world_W5,
    "W6": WL.world_W6,
    "W7": WL.world_W7,  # amendment 2
    "W7s": WL.world_W7s,
}
_SYSTEMS: dict[str, System] = {}


def _system(world_id: str) -> System:
    if world_id not in _WORLDS:
        raise KeyError(f"unknown world {world_id!r}; known: {', '.join(_WORLDS)}")
    if world_id not in _SYSTEMS:
        with decimal.localcontext(HP.make_context(DIGITS)):
            _SYSTEMS[world_id] = System(WL.numeric(_WORLDS[world_id]()[0]))
    return _SYSTEMS[world_id]


def G(world_id: str, node: str, amounts: dict) -> decimal.Decimal:
    """SPEC.md §1.3's G (pJ) of one facing node: its pools plus the sets that face it."""
    sysm = _system(world_id)
    if node not in sysm.facing_nodes():
        raise KeyError(f"{node!r} is not a facing node of {world_id}")
    names = sysm.observables()
    at_node = [i for i in range(sysm.n) if sysm.node_of_component(i) == node]
    wanted = {names[i] for i in at_node}
    missing = sorted(wanted - set(amounts))
    extra = sorted(set(amounts) - wanted)
    if missing or extra:
        raise KeyError(f"{world_id} {node}: missing {missing}, not at this node {extra}")
    y = [HP.ZERO] * sysm.n
    for i in at_node:
        y[i] = HP.D(amounts[names[i]])
        if y[i] < 0:
            raise ValueError(f"{names[i]} is negative")
    with decimal.localcontext(HP.make_context(DIGITS)):
        return +sysm.G(y, node)
