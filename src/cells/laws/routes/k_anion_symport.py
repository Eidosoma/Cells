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

The affinity's log of the product ratio (log_product_ratio) is ln of the quotient
K_i A_i / (K_o A_o) wherever that quotient is a normal float, as it always was. Where
the two products and the four concentrations are normal and their quotient is not, it
is the sum of the two ions' log ratios, within an ulp. A quotient is not normal when it
overflows, or when it falls below the smallest normal float, which compiled CPU code
flushes to zero. The independent Lean project (lean/) found 16 mM inside and 2^-510 mM
outside (both products normal) giving an infinite affinity and heat before this.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.laws.electrochemistry import R

LAW_ID = "cells.operator.k_anion_symport_mass_action@1"
VOLUME_FACTOR_ID = "cells.transfer_factor.exponential_volume_activation@1"
MAX_ABS_VOLUME_EXPONENT = 80.0  # exp(80) ~ 5e34: beyond this the factor is not physical.
SPLIT_MARGIN = 1e-9  # log_product_ratio: in the exponent, as a power of 2.


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


def log_product_ratio(k_in_mM, anion_in_mM, k_out_mM, anion_out_mM, *, xp=jnp):
    """ln(K_i A_i / (K_o A_o)), overflow-safe (the module docstring). The split form,
    (ln K_i - ln K_o) + (ln A_i - ln A_o) (the Lean project's electrochemical_sum), serves only
    where the four concentrations are normal floats and, read from their log2, both products are
    normal and the quotient is not, each by SPLIT_MARGIN in the exponent (about 1000 times the
    error of four log2 and their sums). So a normal quotient is never split: every input but those
    keeps ln of the quotient bit for bit. Quotients within the margin of the ends of the normal
    range (a relative sliver of 7e-10) keep that form too, as before; so does a subnormal operand,
    which compiled CPU code reads as zero.

    The choice reads no product of the concentrations. Measured on 20 November 2026, choices that
    compared the cycles' own products K_i A_i and K_o A_o, or formed products of screened
    concentrations for an exact test, changed compiled code's arithmetic for the cycles in the
    composite's fused step (the Lean project's closed pairs; comparing the products also moved
    the W2 trajectories), while this choice kept every field of the closed pairs and of a held-bath
    world bit for bit. Why one added computation moves those bits and another does not is not
    established: the invariance is measured, not derived.

    The double where: the split form reads 1 for every concentration where the direct form is
    taken, and the direct form reads 1 for every concentration where the split form is taken. So
    the branch not taken puts no inf or NaN into a value, or into a derivative, forward or reverse.

    Sign: ln of a correctly rounded quotient is > 0, = 0 or < 0 with the products' difference.
    The split form serves only where the quotient overflows or underflows, so |ln| > 708 there,
    far beyond its rounding, and it too has the sign of the difference: either way the heat J A
    is never negative, not even by rounding."""
    concentrations = (k_in_mM, anion_in_mM, k_out_mM, anion_out_mM)
    info = xp.finfo(xp.result_type(k_in_mM))
    ok = None
    for c in concentrations:
        n = (c >= info.tiny) & (c <= info.max)
        ok = n if ok is None else ok & n
    e = [xp.log2(xp.where(ok, c, 1.0)) for c in concentrations]
    inside, outside = e[0] + e[1], e[2] + e[3]
    low, high = info.minexp + SPLIT_MARGIN, info.maxexp - SPLIT_MARGIN
    products = (inside > low) & (inside < high) & (outside > low) & (outside < high)
    exponent = inside - outside
    split = (
        ok
        & products
        & ((exponent > info.maxexp + SPLIT_MARGIN) | (exponent < info.minexp - SPLIT_MARGIN))
    )
    k_in, a_in, k_out, a_out = (xp.where(split, 1.0, c) for c in concentrations)
    direct = xp.log((k_in * a_in) / (k_out * a_out))
    ln = [xp.log(xp.where(split, c, 1.0)) for c in concentrations]
    return xp.where(split, (ln[0] - ln[2]) + (ln[1] - ln[3]), direct)


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
    # The log has the sign of (inside - outside) exactly (log_product_ratio), so the heat J A
    # is never negative, not even by rounding.
    log_ratio = log_product_ratio(k_in_mM, anion_in_mM, k_out_mM, anion_out_mM, xp=xp)
    affinity = R * temperature_K * log_ratio
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
