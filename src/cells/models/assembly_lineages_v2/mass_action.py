"""cells.reaction.stochastic_mass_action@1: a step's encounter on the event-pair contract (OL1; §2.1, §0.2a).

**The law.** For a step with forward rate constant k_f (`forward_rate_per_s`, D152's key, in the
activity form), one direction's rate at its firing state n is

    a(n) = k × E(m) × Π_dilute ff(n_p, a_p)/X_p^a_p × Π_held (c_s/c0)^a_s
                    × Π_mem ff(n_i, a_i)/ff(N − c, r)

- k is k_f for the forward and k⁻ = k_f exp(Σ_p ν_p μ°_p) for the reverse. The reverse is this same
  law applied to the products: with the exact ideal F (ideal_mixing.py) it is identical to the pair
  rule a⁻(n + ν) = s(m) θ⁺(n) exp(F(n + ν) − F(n) − w), for every order up to three on each side,
  under either condensed measure, held species included (w their reservoir work);
- ff(n, a) = n!/(n − a)!; X_p = N_A V_p c0 for a dilute place; c_s/c0 a held species' activity;
- r is the direction's membrane reactant molecules, N the membrane's count and c the condensed
  measure's offset (`condensed_measure`);
- E(m) is the step's locus extent on the pair's common state m = min(n, n + ν): X_locus for a
  dilute locus (a constant in OL1), and N(m) − c + 1 for the membrane (`membrane_kinetics:
  count_on_m`). So a step inside a dilute phase is volume-scaled mass action, k X^(1−r) Π ff, and a
  step inside the membrane is k Π ff/ff(N − c, r − 1).

**The membrane factor in its cancelled form** (§0.2a, amended 17 November 2026). With r* the
direction's net membrane consumption (r* = r unless a membrane place is both a reactant and a
product), N(m) = N − r*, so E(m)/ff(N − c, r) = (N − c − r* + 1)/ff(N − c, r). Where r* = r ≥ 1 the
common factor cancels to 1/ff(N − c, r − 1): that is the factor's value everywhere, and where the
literal product is 0/0 (c = 1, a direction that consumes the whole membrane) the cancelled form is
the rule. So under `last_molecule: extinct` the last molecule's leave, in either direction, is
k⁻·1 or k_f·1 exactly: G1's leave. A literal zero there is an error. Where r* < r (a membrane place
on both sides), the factor is (N − c − r* + 1)/ff(N − c, r); under c = 1 it is singular at N = r,
where the declared measure gives the rate +inf: a run that reaches such a state stops, stalled
(refused), and a probe reports +inf there.

**The boundary tokens** (`last_molecule`): `kept` gives the rate 0, in both directions, only to a
pair whose step changes the membrane's count and one of whose end states has an empty membrane, so
the membrane never empties and a step that leaves the membrane's count alone fires at its own rate
(a pool step at an empty membrane fires at the pool's mass action: kernel.kept_zero); `reversible`
(c = 0) and `extinct` (c = 1) change no rate: the first makes the empty membrane a state, the
second ends the assembly at the event that empties it (kernel.py).

The direct kernel works on a View (kernel.py): every array is per step and per entry, an entry
being one distinct place of the step ([R, K], K = 6), in the same xp arithmetic on the host (NumPy)
and the device (jax.numpy).
"""

import numpy as np

from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import MASS_ACTION, MODEL_ID
from cells.models.assembly_lineages_v2.interfaces import ReactionLaw
from cells.modules import Citation, CitedWork

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_kernel.py::"
    "test_the_reverse_from_F_is_the_products_mass_action"
)


def safe_log(values, xp):
    """ln of non-negative values, −inf at 0, without a warning on the host."""
    positive = values > 0
    return xp.where(positive, xp.log(xp.where(positive, values, 1)), -xp.inf)


def gather(table, index, xp):
    """table[index] with the index clipped to the table (a masked entry reads a valid slot)."""
    return table[xp.clip(index, 0, table.shape[0] - 1)]


def entry_sum(values, xp):
    """Σ over a step's entries ([R, K] -> [R]): a serial left fold in entry order (D182)."""
    return folds.total(xp.swapaxes(values, 0, 1), xp)


MAX_SIDE = 3  # D152: at most three molecules a side, so a falling factorial has at most 3 factors


def log_falling(n, k, xp):
    """ln ff(n, k) = ln n + ln(n − 1) + ... (k factors, 0 ≤ k ≤ 3; D152), each logarithm taken
    directly. A difference of two log-factorials, lf[n] − lf[n − k], carries the table's rounding
    at ln n! (about 1e4 at a few thousand molecules: up to 5e-12 in OL5's registered worlds); these
    k logarithms keep the counts' double precision (OL5's precision fix, 22 November 2026). Where
    n < k a factor is not positive and the value is −inf; every caller masks that state."""
    nf = n.astype(np.float64)
    out = xp.zeros_like(nf)
    for j in range(MAX_SIDE):
        out = out + xp.where(k > j, safe_log(nf - j, xp), 0.0)
    return out


def membrane_factor(view, offset, xp):
    """ln [E(m) / ff(N − c, r)] for a membrane locus, in its cancelled form (module docstring)."""
    k = view.coeff
    r = entry_sum(xp.where(view.membrane, k, 0), xp)
    r_star = entry_sum(xp.where(view.membrane, view.consumed, 0), xp)
    M = view.membrane_total - offset + xp.zeros_like(r)  # N − c, per step.
    cancelled = xp.where(
        r >= 1,
        -log_falling(M, r - 1, xp),
        safe_log((M + 1).astype(np.float64), xp),
    )
    # Where N − c < r, ff(N − c, r) = 0: the factor is +inf where E(m) > 0 (the singular state of
    # @1's measure, declared) and never a value of a factor that is not positive.
    defined = (M - r) >= 0
    numerator = M - r_star + 1
    general = xp.where(
        defined,
        safe_log(numerator.astype(np.float64), xp)
        - xp.where(defined, log_falling(xp.where(defined, M, r), r, xp), 0.0),
        xp.where(numerator > 0, xp.inf, -xp.inf),
    )
    return xp.where(r_star == r, cancelled, general)


def log_direction(view, locus_membrane, log_extent_dilute, offset, xp):
    """ln [a / k] for one direction of every step at its firing state (module docstring): the
    extent and the activities, without the rate constant, the rate factor and the excess free
    energy; −inf where the direction cannot fire. The kernel multiplies by the rate constant after
    the exponential, so a rate constant scaled by a power of two scales the rate exactly.

    view: the direction's View (kernel.py); locus_membrane [R]: the step's locus is the membrane;
    log_extent_dilute [R]: ln X of a dilute locus; offset: c."""
    n, k = view.counts, view.coeff
    finite = view.membrane | view.dilute
    feasible = xp.all(xp.where(finite, n >= k, True), axis=1)
    log_ff = log_falling(n, k, xp)
    kf = k.astype(np.float64)
    terms = (
        xp.where(view.dilute, log_ff - kf * view.log_X, 0.0)
        + xp.where(view.membrane, log_ff, 0.0)
        + xp.where(view.held, kf * view.log_activity, 0.0)
    )
    activity = entry_sum(terms, xp)
    extent = xp.where(locus_membrane, membrane_factor(view, offset, xp), log_extent_dilute)
    # Mask both operands before the sum: at an infeasible direction activity can be −inf and the
    # extent +inf, and −inf + inf raises NumPy's invalid-value warning before the mask applies. A
    # feasible direction's operands pass through unchanged, so its value is bit for bit the same.
    return xp.where(feasible, xp.where(feasible, activity, 0.0) + xp.where(feasible, extent, 0.0),
                    -xp.inf)


def limit_log_direction(view, locus_membrane, log_extent_dilute, offset, xp):
    """OL6's large-count limit of log_direction (arithmetic A; the design note's §1.3): ln [a / k]
    of one direction at real counts n, with every falling factorial ff(n, a) by its power n^a, the
    membrane's ff(N − c, r) by (N − c)^r, and the common state m by n, so E = N − c + 1 for the
    membrane. Entries with no coefficient contribute nothing (so a padding entry's empty place
    never forms 0 × ln 0), and every logarithm is guarded, so the derivatives stay finite."""
    n = view.counts.astype(np.float64)
    k = view.coeff
    kf = k.astype(np.float64)
    log_n = safe_log(n, xp)
    terms = (
        xp.where(view.dilute & (k > 0), kf * (log_n - view.log_X), 0.0)
        + xp.where(view.membrane & (k > 0), kf * log_n, 0.0)
        + xp.where(view.held & (k > 0), kf * view.log_activity, 0.0)
    )
    activity = entry_sum(terms, xp)
    r = entry_sum(xp.where(view.membrane, kf, 0.0), xp)
    size = (view.membrane_total - offset) + xp.zeros_like(r)  # N − c, per step, real
    membrane = safe_log(size + 1.0, xp) - xp.where(r > 0, r * safe_log(size, xp), 0.0)
    extent = xp.where(locus_membrane, membrane, log_extent_dilute)
    return activity + extent


LIMIT_FORMULAS = {
    "forward": "a+(n) = k_f E(n) prod_dilute (n_p/X_p)^a_p prod_held (c_s/c0)^a_s "
    "prod_membrane n_i^a_i / (N - c)^r, E(n) = N - c + 1 for the membrane locus and X_locus for a "
    "dilute one; n real",
    "rule": "arithmetic A (Kurtz's limit): ff(n, a) -> n^a, ff(N - c, r) -> (N - c)^r, m -> n",
    "reverse": "the same limit applied to the products, k- = k_f exp(sum nu mu°): equal to "
    "a+ exp(nu . grad F_cont - w), F_cont Stirling's form of the declared F (the limit's check)",
}

FORMULAS = {
    "forward": "a+(n) = k_f E(m) prod_dilute ff(n_p, a_p)/X_p^a_p prod_held (c_s/c0)^a_s "
    "prod_membrane ff(n_i, a_i)/ff(N - c, r), m = min(n, n + nu)",
    "reverse": "the same law applied to the products, with k- = k_f exp(sum_p nu_p mu°_p), times "
    "exp(F_ex(n) - F_ex(n - nu)) for the excess terms; identical to the pair rule a-(n + nu) = "
    "s(m) theta+(n) exp(F(n + nu) - F(n) - w)",
    "extent": "E(m) = X_locus = N_A V_locus c0 for a dilute locus; N(m) - c + 1 for the membrane "
    "(membrane_kinetics count_on_m)",
    "membrane_factor": "E(m)/ff(N - c, r) = (N - c - r* + 1)/ff(N - c, r), cancelled to "
    "1/ff(N - c, r - 1) where r* = r >= 1 (sec. 0.2a): the last molecule's leave is k-.1 under "
    "last_molecule extinct",
    "kept": "rate 0 only for a pair whose step changes the membrane's count and one of whose end "
    "states has an empty membrane; every other step fires at its own rate",
    "units": "k_f in 1/s (the activity form, D152's forward_rate_per_s)",
}

LAW = law_registry.BUILTIN.register(
    ReactionLaw(
        "cells.reaction.stochastic_mass_action@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "Gillespie (1977), J Phys Chem 81:2340; docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.1, "
            "§0.2a and §2.1",
            "the stochastic propensity k (N_A V)^(1-r) prod n!/(n-a)! of an elementary step; the "
            "event-pair rule; the lead's rulings for OL1",
            "no numbers taken",
            (
                "the reverse propensity is derived from the one free energy F, never declared",
                "a membrane (condensed phase) has no volume until OL2: its reactants' activities "
                "are drawn without replacement, and the locus extent is evaluated on the pair's "
                "common state",
                "the rate constant is D152's forward_rate_per_s, in the activity form",
            ),
            (
                CitedWork(
                    ("D. T. Gillespie",),
                    1977,
                    "Exact stochastic simulation of coupled chemical reactions",
                    doi="10.1021/j100540a008",
                ),
            ),
        ),
        test=TEST,
        energy_role="passive",
        energy_source=None,
        split="encounter",
        log_direction=log_direction,
        formulas=FORMULAS,
        limit=limit_log_direction,
        limit_formulas=LIMIT_FORMULAS,
    )
)
assert LAW.law_id == MASS_ACTION
