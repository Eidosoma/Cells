"""cells.reaction.phase_exchange@1: one molecule joins the membrane from the pool (OL2; §2.5, §0.2b rule 1,
§0.2c rules 2 and 3, §0.2d item 2; docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.2).

**The law.** A step of this law is a join: one molecule of a pool place (finite or held) to the
membrane place of the same species. Its forward at the firing state n is

    a⁺(n) = k · E(m) · ρ0 · θ⁺(n),   m = min(n, n + ν) = n

- θ⁺ is the pool's activity, n/X_pool for a finite place or c/c0 for a held one, so ρ0·θ⁺ is the
  pool's number density; ρ0 = N_A·c0 in molecules per m³;
- k and E(m) follow the world's `exchange_encounter` token: `insertion_area`, k = k_ins
  (`insertion_velocity_m_per_s`, m/s) and E = A(m) (m²); `diffusion_radius`, k = D_i
  (`diffusivity_m2_per_s`, m²/s) and E = 4πR(m) (m). The kernel supplies ln(E(m)·ρ0) from the
  geometry (geometry.py), the same for both directions of a pair.

The leave is the reverse, from the one F: this same law applied to the products (the membrane
molecule's activity drawn without replacement, ff(n_i, 1)/ff(N − c, 1), at the firing state), with
k⁻ = k·exp(Σ ν μ°) and the same extent on m, as for every law of this family (mass_action.py). So
ln a⁺ − ln a⁻ = −ΔF + w for every pair (the kernel's check, balance.py).

`geometric_log_direction` is shared with cells.reaction.membrane_permeation@1 (permeation.py).
"""

import numpy as np

from cells.models.assembly_lineages_v2 import MODEL_ID, PHASE_EXCHANGE
from cells.models.assembly_lineages_v2.interfaces import ReactionLaw
from cells.models.assembly_lineages_v2.mass_action import entry_sum, log_falling
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_geometry.py::"
    "test_insertion_area_at_equal_quanta_is_count_on_m_at_c_1"
)


def geometric_log_direction(view, locus_membrane, log_extent_dilute, offset, xp):
    """ln [a / k] of one direction of every step at its firing state: the reactants' activities
    (as mass action's, at the firing state), the membrane reactants' normalisation 1/ff(N − c, r),
    and the geometric extent on m, ln(E(m)·ρ0) = view.log_encounter (−inf where E(m) = 0); −inf
    where the direction cannot fire."""
    n, k = view.counts, view.coeff
    finite = view.membrane | view.dilute
    feasible = xp.all(xp.where(finite, n >= k, True), axis=1)
    log_ff = log_falling(n, k, xp)  # OL5's precision fix: no log-factorial differences
    kf = k.astype(np.float64)
    terms = (
        xp.where(view.dilute, log_ff - kf * view.log_X, 0.0)
        + xp.where(view.membrane, log_ff, 0.0)
        + xp.where(view.held, kf * view.log_activity, 0.0)
    )
    activity = entry_sum(terms, xp)
    r = entry_sum(xp.where(view.membrane, k, 0), xp)
    M = view.membrane_total - offset + xp.zeros_like(r)  # N − c, per step.
    defined = (r == 0) | ((M - r) >= 0)
    normalisation = xp.where(r >= 1, -log_falling(xp.where(defined, M, r), r, xp), 0.0)
    return xp.where(feasible & defined, activity + normalisation + view.log_encounter, -xp.inf)


RATE_KEYS = {
    "insertion_area": "insertion_velocity_m_per_s",
    "diffusion_radius": "diffusivity_m2_per_s",
}

FORMULAS = {
    "forward": "a+(n) = k E(m) rho0 theta+(n): theta+ the pool's activity (n/X_pool, or c/c0 when "
    "held), rho0 = N_A c0 (molecules per m^3), m = n",
    "insertion_area": "k = k_ins (m/s), E(m) = A(m) (m^2)",
    "diffusion_radius": "k = D_i (m^2/s), E(m) = 4 pi R(m) (m)",
    "reverse": "the leave: the same law applied to the products, k- = k exp(sum nu mu°), the same "
    "extent on m; the membrane molecule's activity ff(n_i, 1)/ff(N - c, 1) at the firing state",
}

LAW = law_registry.BUILTIN.register(
    ReactionLaw(
        "cells.reaction.phase_exchange@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §2.5, §0.2b rule 1, §0.2c rules 2 and 3, §0.2d "
            "item 2 (reaction-limited insertion by area; Smoluchowski's diffusion-limited rate, "
            "cited from memory there)",
            "a molecule joins a membrane from the pool; the leave is the reverse, from F",
            "no numbers taken",
            (
                "declared as the join only, one molecule of one species",
                "the area-equivalent radius for a floppy vesicle is a declared approximation",
            ),
        ),
        test=TEST,
        energy_role="passive",
        energy_source=None,
        split="encounter",
        log_direction=geometric_log_direction,
        formulas=FORMULAS,
        rate_key=RATE_KEYS,
        extent="geometric",
        limit=geometric_log_direction,  # OL6: one molecule a step, so ff(n, 1) = n: arithmetic A
        limit_formulas={
            "rule": "the same kernel on real counts: every falling factorial has a <= 1, so "
            "arithmetics A and C coincide (the design note's §1.4); the extent at real W",
        },
    )
)
assert LAW.law_id == PHASE_EXCHANGE
