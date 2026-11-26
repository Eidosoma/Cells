"""cells.free_energy.regular_mixing@1: the regular-solution excess term of the membrane (OL1; §2.2, §2.5, E2).

In k_BT, over the membrane's species, with N its count:

    F_reg(n) = (1/(2N)) Σ_ij χ_ij n_i n_j,  and 0 at N = 0

- χ is symmetric: the Maxwell condition ∂μ_i/∂n_j = ∂μ_j/∂n_i, which a composition-dependent rate
  must satisfy to keep detailed balance (the design note's probe E2), holds because the term is one
  function of the counts.
- χ has a zero diagonal and finite entries (k_BT), declared as unordered pairs of distinct membrane
  species, each at most once: `{"law": "cells.free_energy.regular_mixing@1", "chi_kT": [{"pair": ["A", "B"],
  "chi": 1.5}, ...]}`. An unlisted pair is 0.

The term is an excess term: it enters the reverse rate as exp(F_reg(n) − F_reg(n − ν)), so it moves
the equilibrium (thermodynamic selection, the design note's A2), never a rate constant.

**Incrementally** (R2): the state is y = χ n (one entry per place) and S = n·y, both computed
exactly by serial folds at the founder. A step's change δ at its entries gives S' = S + 2 δ·y + δ·χδ
and N' = N + Σ δ over the membrane, so its ΔF costs one row of χ per entry. After an event, y gains
one column of χ per entry moved. The ledger recomputes F_reg exactly at every saved row.
"""

import numpy as np

from cells.definitions.specs import ConfigError, require_fields
from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import MODEL_ID, REGULAR_MIXING
from cells.models.assembly_lineages_v2.interfaces import FreeEnergyTerm
from cells.models.assembly_lineages_v2.mass_action import entry_sum
from cells.modules import Citation, CitedWork

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_ledger.py::"
    "test_the_regular_term_is_exact_and_its_change_matches_its_value"
)


def parse_data(raw, world):
    require_fields(raw, {"law", "chi_kT"}, "world: free_energy: regular mixing")
    pairs = raw["chi_kT"]
    if type(pairs) is not list:
        raise ConfigError("world: regular mixing: chi_kT is a list of {pair, chi}")
    membrane = [p.species for p in world.places if p.phase == "membrane"]
    seen, out = set(), []
    for entry in pairs:
        require_fields(entry, {"pair", "chi"}, "world: regular mixing: a chi entry")
        pair = entry["pair"]
        if type(pair) is not list or len(pair) != 2:
            raise ConfigError("world: regular mixing: a pair names two membrane species")
        a, b = pair
        if a == b:
            raise ConfigError(
                f"world: regular mixing: chi has a zero diagonal ({a} with itself is refused)"
            )
        for name in (a, b):
            if name not in membrane:
                raise ConfigError(
                    f"world: regular mixing: {name!r} is not a membrane species of the world"
                )
        key = tuple(sorted((a, b)))
        if key in seen:
            raise ConfigError(f"world: regular mixing: the pair {list(key)} is listed twice")
        seen.add(key)
        chi = entry["chi"]
        if isinstance(chi, bool) or not isinstance(chi, (int, float)) or not np.isfinite(chi):
            raise ConfigError(f"world: regular mixing: chi of {list(key)} is a finite number")
        out.append((key, float(chi)))
    return {"chi_kT": tuple(sorted(out))}


def data_to_dict(data):
    return {"chi_kT": [{"pair": list(pair), "chi": chi} for pair, chi in data["chi_kT"]]}


def layout(data, world, capacity):
    """(chi [P, P],): symmetric over the membrane places, zero elsewhere and on the diagonal."""
    chi = np.zeros((capacity, capacity), dtype=np.float64)
    index = {p.species: i for i, p in enumerate(world.places) if p.phase == "membrane"}
    for (a, b), value in data["chi_kT"]:
        chi[index[a], index[b]] = chi[index[b], index[a]] = value
    return (chi,)


def state(counts, totals, term_layout, xp):
    """(y = χ n, S = n·y), exactly: serial folds over the places in place order."""
    (chi,) = term_layout
    n = counts.astype(np.float64)
    y = folds.total((chi * n[None, :]).T, xp)
    return y, folds.total(n * y, xp)


def update(state, term_layout, places, change, xp):
    """The state after one step: places [K] and change [K] at the fired step's entries."""
    (chi,) = term_layout
    y, s = state
    d = change.astype(np.float64)
    gained = folds.total((chi[:, places] * d[None, :]).T, xp)
    s_new = (
        s
        + 2.0 * folds.total(d * y[places], xp)
        + folds.total(d * folds.total((chi[places][:, places] * d[None, :]).T, xp), xp)
    )
    return y + gained, s_new


def _f(s, total):
    return np.where(total > 0, s / np.where(total > 0, total, 1), 0.0)


def value(counts, tables, term_layout):
    """F_reg(n) on the host (NumPy)."""
    (chi,) = term_layout
    n = np.asarray(counts, dtype=np.float64)
    y = folds.total((chi * n[None, :]).T, np)
    s = folds.total(n * y, np)
    total = float(np.sum(np.where(tables.membrane, np.asarray(counts), 0)))
    return float(_f(s, total)) / 2.0


def delta(state, term_layout, view, change, xp):
    """F_reg(n + change) − F_reg(n) for each step's change at its entries ([R, K] -> [R])."""
    (chi,) = term_layout
    y, s = state
    place = view.places
    d = change.astype(np.float64)
    linear = entry_sum(d * y[place], xp)
    pairs = chi[place[:, :, None], place[:, None, :]]  # [R, K, K]
    inner = folds.total(xp.moveaxis(pairs * d[:, None, :], 2, 0), xp)  # Σ_f χ_ef δ_f: [R, K]
    quadratic = entry_sum(d * inner, xp)
    s_after = s + 2.0 * linear + quadratic
    moved = entry_sum(xp.where(view.membrane, change, 0), xp).astype(np.float64)
    total = view.membrane_total.astype(np.float64) + xp.zeros_like(moved)
    after = total + moved

    def f(value, count):
        return xp.where(count > 0, value / xp.where(count > 0, count, 1.0), 0.0) / 2.0

    return f(s_after, after) - f(s + xp.zeros_like(moved), total)


def limit_value(counts, tables, term_layout, xp):
    """OL6: F_reg = (1/(2N)) n·χn at real counts, 0 at N = 0; traceable (its gradient is the
    excess μ)."""
    (chi,) = term_layout
    n = counts.astype(np.float64)
    total = xp.sum(xp.where(tables.membrane, n, 0.0))
    quadratic = n @ (chi @ n)
    safe = xp.where(total > 0, total, 1.0)
    return xp.where(total > 0, quadratic / (2.0 * safe), 0.0)


FORMULAS = {
    "F_reg": "(1/(2N)) sum_ij chi_ij n_i n_j over the membrane's species; 0 at N = 0",
    "chi": "symmetric (Maxwell), zero diagonal, finite, k_BT; unlisted pairs 0",
    "state": "y = chi n, S = n.y, exactly by serial folds at the founder",
    "change": "S' = S + 2 d.y + d.chi d, N' = N + sum d over the membrane",
    "role": "excess: the reverse rate carries exp(F_reg(n) - F_reg(n - nu))",
}

TERM = law_registry.BUILTIN.register(
    FreeEnergyTerm(
        "cells.free_energy.regular_mixing@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "Hildebrand (1929), J Am Chem Soc 51:66; docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §2.2, "
            "§2.5 and probe E2",
            "the regular solution: an excess free energy quadratic in the composition",
            "no numbers taken",
            ("written in counts, (1/(2N)) sum chi n n, with a symmetric chi and a zero diagonal",),
            (
                CitedWork(
                    ("J. H. Hildebrand",),
                    1929,
                    "Solubility. XII. Regular solutions",
                    doi="10.1021/ja01376a009",
                ),
            ),
        ),
        test=TEST,
        part="excess",
        phases=("membrane",),
        data=("chi_kT",),
        parse_data=parse_data,
        data_to_dict=data_to_dict,
        layout=layout,
        state=state,
        update=update,
        value=value,
        delta=delta,
        formulas=FORMULAS,
        limit=limit_value,
        limit_formulas={"F_reg": "(1/(2N)) sum_ij chi_ij n_i n_j at real counts (the same form)"},
    )
)
assert TERM.law_id == REGULAR_MIXING
