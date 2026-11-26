"""cells.damage.bounding_patch_damage@1: injury, leak and reseal on a compartment's bounding patch (FR-5).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §9. A prescribed injury and resealing of a bounding patch,
as a control state with no ledger:

    dd/dt = a (1 - d) - b d,    a = k_inj u_inj(t),  b = k_res u_res(t),   d in [0, 1],

with u_inj and u_res declared piecewise-constant schedules in [0, 1] that change only at step
boundaries. Over a step of length h at constant a and b the solution is exact:

    d(h) = d_eq + (d - d_eq) exp(-(a + b) h),   d_eq = a / (a + b)   (d unchanged when a + b = 0),

so the state stays in [0, 1] at any step and needs no stage rule. d reaches the leak and transfer
routes as a control factor through the routing door (§8); it moves no material itself. On a lumped
population d is the damaged fraction of the whole bounding area, uniform over the members (§9).

Pure functions in the xp style of processes/.
"""

import jax.numpy as jnp

LAW_ID = "cells.damage.bounding_patch_damage@1"


def rates(damage, injury_rate_per_s, resealing_rate_per_s, injury, resealing, *, xp=jnp):
    """(dd/dt, opened, closed) per s: the older law's rates, unchanged in form."""
    opened = injury_rate_per_s * injury * (1.0 - damage)
    closed = resealing_rate_per_s * resealing * damage
    return opened - closed, opened, closed


def exact_step(damage, injury_rate_per_s, resealing_rate_per_s, injury, resealing, step_s,
               *, xp=jnp):
    """d after one step at constant schedules, exactly: d_eq + (d - d_eq) exp(-(a + b) h).

    Evaluated in that form, the equilibrium plus the decaying offset: for d >= d_eq both terms
    are nonnegative, and for d < d_eq a nonnegative product is taken from d_eq <= 1, so the result
    stays in [0, 1] at any step without cancellation (the form d + (a - (a + b) d) h phi(x) lost
    one rounding below 0 at large x with a = 0, d near 1). Where a + b = 0, d is unchanged
    exactly (d_eq is then d and the decay 1)."""
    a = injury_rate_per_s * injury
    b = resealing_rate_per_s * resealing
    total = a + b
    opening = total > 0
    equilibrium = xp.where(opening, a / xp.where(opening, total, 1.0), damage)
    return equilibrium + (damage - equilibrium) * xp.exp(-total * step_s)


def domain_valid(damage, injury_rate_per_s, resealing_rate_per_s, injury, resealing, *, xp=jnp):
    """d in [0, 1]; rates finite and >= 0; schedules in [0, 1]."""
    ok = xp.isfinite(damage) & (damage >= 0) & (damage <= 1)
    for rate in (injury_rate_per_s, resealing_rate_per_s):
        ok = ok & xp.isfinite(rate) & (rate >= 0)
    for value in (injury, resealing):
        ok = ok & xp.isfinite(value) & (value >= 0) & (value <= 1)
    return ok


def leak_permeability_m_s(damage, pore_permeability_m_s):
    """The damage leak's effective permeability, d P_pore: the routing door's factor applied."""
    return damage * pore_permeability_m_s
