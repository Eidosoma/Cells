"""cells.free_energy.ideal_mixing@1: the ideal part of F, exact in the counts (OL1; §2.2, §0.2a).

In k_BT, with X_φ = N_A V_φ c0 for a dilute phase φ, N the membrane's count and c the condensed
measure's offset (`condensed_measure`: 0 for the multinomial, 1 for @1's measure):

    F_id(n) = Σ_dilute φ Σ_s [n_s (μ°_s,sol − ln X_φ) + ln n_s!]
            + Σ_i n_i μ°_i,bil − ln (N − c)! + Σ_i ln n_i!

- A held pool species has no term: its exchanges book reservoir work instead (the kernel's w).
- The membrane's term at N = 0 is 0 under both measures (−ln 0! = 0 for the multinomial, and a
  convention for @1's measure, booked only as `last_molecule: extinct`'s end).
- `free_energy_form: discrete`: ln n! exactly, from a table of math.lgamma bound as layout, so the
  host and every device read the same values. Stirling's form is the large-count limit of this one.

The term is folded into mass action's reverse (mass_action.py): with it, the reverse derived from
F is the products' mass action, k⁻ = k_f exp(Σ ν μ°). Its value and its change under a step are
still stated here, for the ledger (ledger.py), the kernel's check (balance.py), and the heat of the
one event that has no reverse (an extinction).
"""

import numpy as np

from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import IDEAL_MIXING, MODEL_ID
from cells.models.assembly_lineages_v2.interfaces import FreeEnergyTerm
from cells.models.assembly_lineages_v2.mass_action import entry_sum, gather
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_ledger.py::"
    "test_the_ideal_term_is_exact_and_its_change_matches_its_value"
)


def parse_data(raw, world):
    """The ideal term reads nothing beyond the world (its species, phases and conventions)."""
    return {}


def data_to_dict(data):
    return {}


def layout(data, world, capacity):
    return ()


def state(counts, totals, term_layout, xp):
    return ()


def update(state, term_layout, places, delta, xp):
    return ()


def size_term(total, offset, log_factorial, xp):
    """ln (N − c)!, and 0 for the empty membrane under both measures."""
    return xp.where(total > 0, gather(log_factorial, total - offset, xp), 0.0)


def value(counts, tables, term_layout):
    """F_id(n) on the host (NumPy), a serial fold over the places in place order.

    tables: the world's host tables (kernel.Tables: mu0, log_X, finite, membrane per place, the
    log-factorial table and the offset c)."""
    lf = tables.log_factorial
    n = np.asarray(counts, dtype=np.int64)
    terms = np.where(
        tables.finite,
        n * (tables.mu0 - np.where(tables.membrane, 0.0, tables.log_X)) + gather(lf, n, np),
        0.0,
    )
    total = np.int64(np.sum(np.where(tables.membrane, n, 0)))
    return float(folds.total(terms, np)) - float(size_term(total, tables.offset, lf, np))


def delta(state, term_layout, view, change, xp):
    """F_id(n + change) − F_id(n) for each step's change at its entries ([R, K] -> [R])."""
    lf = view.log_factorial
    finite = view.membrane | view.dilute
    n = view.counts
    after = n + change
    cf = change.astype(np.float64)
    terms = xp.where(
        finite,
        cf * (view.mu0 - xp.where(view.dilute, view.log_X, 0.0))
        + gather(lf, after, xp)
        - gather(lf, n, xp),
        0.0,
    )
    moved = entry_sum(xp.where(view.membrane, change, 0), xp)
    N = view.membrane_total + xp.zeros_like(moved)
    size = size_term(N + moved, view.offset, lf, xp) - size_term(N, view.offset, lf, xp)
    return entry_sum(terms, xp) - size


def _x_log_x(n, xp):
    """n ln n − n, with 0 at n = 0 and a guarded logarithm (finite derivatives)."""
    positive = n > 0
    return xp.where(positive, n * xp.log(xp.where(positive, n, 1.0)) - n, 0.0)


def limit_value(counts, tables, term_layout, xp):
    """OL6: F_id in Stirling's form at real counts (the design note's §1.3): every ln k! by
    k ln k − k, the membrane's measure as −[(N − c) ln(N − c) − (N − c)]. Traceable, so its
    gradient is μ by differentiation."""
    n = counts.astype(np.float64)
    finite = tables.finite
    membrane = tables.membrane
    per_place = xp.where(
        finite,
        n * (tables.mu0 - xp.where(membrane, 0.0, tables.log_X)) + _x_log_x(n, xp),
        0.0,
    )
    size = xp.sum(xp.where(membrane, n, 0.0)) - tables.offset
    return xp.sum(per_place) - _x_log_x(size, xp)


FORMULAS = {
    "F_id": "sum_dilute sum_s [n_s (mu°_s,sol - ln X) + ln n_s!] + sum_i n_i mu°_i,bil "
    "- ln (N - c)! + sum_i ln n_i!, X = N_A V c0; held species: no term",
    "empty_membrane": "the membrane's term is 0 at N = 0 under both measures",
    "measure": "c = 0 (multinomial) or 1 (multinomial_less_one, @1's measure = multinomial + ln N)",
    "form": "discrete: ln n! exactly (free_energy_form discrete)",
}

TERM = law_registry.BUILTIN.register(
    FreeEnergyTerm(
        "cells.free_energy.ideal_mixing@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §2.2 and §0.2a (standard statistical mechanics "
            "of ideal dilute solutions and ideal mixtures)",
            "the pool and assembly terms of the one free-energy function",
            "no numbers taken",
            (
                "exact in the counts (ln n!), not Stirling's form: the discrete form in which the "
                "reverse rate derived from F is the products' mass action",
                "the condensed measure is declared: the multinomial, or @1's (multinomial plus "
                "ln N)",
            ),
        ),
        test=TEST,
        part="ideal",
        phases=("pool", "membrane", "lumen"),
        data=(),
        parse_data=parse_data,
        data_to_dict=data_to_dict,
        layout=layout,
        state=state,
        update=update,
        value=value,
        delta=delta,
        formulas=FORMULAS,
        limit=limit_value,
        limit_formulas={
            "F_id": "sum_dilute [n (mu° - ln X) + n ln n - n] + sum_i [n_i mu°_bil + n_i ln n_i "
            "- n_i] - [(N - c) ln(N - c) - (N - c)] (Stirling's form of the declared F_id)",
            "mu": "the gradient: mu° + ln(n/X) (dilute), mu° + ln(n_i/(N - c)) (membrane)",
        },
    )
)
assert TERM.law_id == IDEAL_MIXING
