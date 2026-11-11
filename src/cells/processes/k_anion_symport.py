"""Electroneutral K+/anion symport by mass action, activated by cell volume (KCC-type).

LAW_ID, one route per membrane patch; outward (cell to outside) positive:

    J = k a f(V) (K_i A_i - K_o A_o)                               fmol/s
    f(V) = exp[(V - V_set) / (s V_set)]                            VOLUME_FACTOR_ID

K is the potassium role and A the anion role (a Cl-like species), both moved
1:1, so the route carries no current. k (fmol/(s mM^2)) is the route's capacity,
a its availability in [0, 1], V the cell's current volume, V_set the volume at
which f = 1 and s > 0 the steepness. The affinity of one outward cycle is
A = R T ln(K_i A_i / (K_o A_o)) (J/mol), and J A >= 0 because (x - y)(ln x -
ln y) >= 0: the heat 1e-3 J A (pJ/s) is never negative, and J reverses where
the concentration products are equal.

Sources (docs/PUMP_WATER_MODEL.md has the marks):
- Mass-action form with an exponential volume factor: Lew, Freeman, Ortiz &
  Bookchin 1991, J Clin Invest 87:100 (their f^V = exp[-(K^V - V_w)/K^V], s = 1).
- Steeper grading: s about 0.12 matches the 4-5x K flux at relative volume 1.2 of
  Kaji 1986, J Gen Physiol 88:719 (derived).
- 1:1 stoichiometry: Jennings & Adame 2001, Am J Physiol Cell Physiol 281:C825.

Limits:
- Activation is instantaneous; the ~10 min lag of red-cell KCC activation
  (Jennings & al-Rohil 1990, J Gen Physiol 95:1021) is not modelled.
- The law reverses at the 1:1 equilibrium; Delpire & Lauf 1991 (J Gen Physiol
  97:173) report efflux persisting until the outside product is about 2x the
  inside one.
- No pH, Mg or phosphorylation state.

Like the other processes, the law takes positive concentrations and volumes;
it never clips. Callers reject invalid trials with domain_valid.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.processes.electrochemistry import R

LAW_ID = "k_anion_symport_mass_action@1"
VOLUME_FACTOR_ID = "exponential_volume_activation@1"
MAX_ABS_VOLUME_EXPONENT = 80.0  # exp(80) ~ 5e34: beyond this the factor is not physical.


class Parameters(NamedTuple):
    """Numeric pytree; every leaf broadcasts over [..., membrane_slot]."""

    capacity_fmol_s_mM2: Any
    set_volume_pL: Any
    steepness: Any


class Rates(NamedTuple):
    cycles_fmol_s: Any  # Outward cycles: K and anion each leave the cell at this rate.
    affinity_J_mol: Any  # R T ln(K_i A_i / (K_o A_o)) of one outward cycle
    volume_factor: Any
    dissipation_pJ_s: Any  # 1e-3 J A >= 0


def volume_factor(volume_pL, parameters, *, xp=jnp):
    p = parameters
    return xp.exp((volume_pL - p.set_volume_pL) / (p.steepness * p.set_volume_pL))


def rates(
    k_in_mM,
    anion_in_mM,
    k_out_mM,
    anion_out_mM,
    volume_pL,
    temperature_K,
    parameters,
    availability,
    *,
    xp=jnp,
):
    """Outward cycles, cycle affinity, volume factor and heat of each route."""
    factor = volume_factor(volume_pL, parameters, xp=xp)
    inside, outside = k_in_mM * anion_in_mM, k_out_mM * anion_out_mM
    cycles = parameters.capacity_fmol_s_mM2 * availability * factor * (inside - outside)
    # The log of the product ratio has the sign of (inside - outside) exactly (a
    # correctly rounded quotient is > 1, = 1 or < 1 with the difference), so the
    # heat J A is never negative, not even by rounding.
    affinity = R * temperature_K * xp.log(inside / outside)
    return Rates(cycles, affinity, factor, 1e-3 * cycles * affinity)


def domain_valid(
    k_in_mM, anion_in_mM, k_out_mM, anion_out_mM, volume_pL, parameters, availability, *, xp=jnp
):
    """Positive finite concentrations and volume, valid parameters and availability."""
    p = parameters
    exponent = (volume_pL - p.set_volume_pL) / (p.steepness * p.set_volume_pL)
    valid = xp.isfinite(volume_pL) & (volume_pL > 0)
    for c in (k_in_mM, anion_in_mM, k_out_mM, anion_out_mM):
        valid = valid & xp.isfinite(c) & (c > 0)
    return (
        valid
        & xp.isfinite(p.capacity_fmol_s_mM2)
        & (p.capacity_fmol_s_mM2 >= 0)
        & xp.isfinite(p.set_volume_pL)
        & (p.set_volume_pL > 0)
        & xp.isfinite(p.steepness)
        & (p.steepness > 0)
        & xp.isfinite(exponent)
        & (xp.abs(exponent) <= MAX_ABS_VOLUME_EXPONENT)
        & xp.isfinite(availability)
        & (availability >= 0)
        & (availability <= 1)
    )


def capacity_from_flux(flux_mmol_L_h, product_difference_mM2, volume_pL):
    """k (fmol/(s mM^2)) of a cell of volume_pL whose flux per cell volume is
    flux_mmol_L_h (mmol/(L cells h)) at a concentration-product difference
    product_difference_mM2 (K_i A_i - K_o A_o) with f = 1."""
    return flux_mmol_L_h * volume_pL / 3600.0 / product_difference_mM2
