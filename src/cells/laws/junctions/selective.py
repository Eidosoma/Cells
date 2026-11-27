"""Pure physical edge flux and symmetric dynamic gate target, independent of assays.

Positive flux is from -> to. The external multiplier blocks all residual and
gated permeability without altering the endogenous gate equation. These are not
BITSEY's upwind transport or instantaneous source gate.

selective_one_way gives the flux's two one-way parts (FR-50 phase 2, D327): the
constant-field law's terms g c_from B(-x) and g c_to B(x), each >= 0, with g
formed by the same operations as selective_flux's prefactor, so their difference
is selective_flux's flux at rounding. Their ratio is Ussing's flux ratio: the
part to -> from over the part from -> to is (c_to / c_from) e^(x) (Ussing 1949,
cited from memory). The parts follow the law's independence assumption, so they
are the model's one-way fluxes, not a prediction of isotope fluxes through
multi-ion pores (the FR-49/50/51 design note, §2.2).
"""

import jax.numpy as jnp

from cells.laws.electrochemistry import MOL_PER_FMOL, F, R, bernoulli


def gate_target(delta_voltage, sensitivity, half_voltage, *, xp=jnp):
    left = sensitivity * (-delta_voltage - half_voltage)
    right = sensitivity * (delta_voltage - half_voltage)
    return xp.exp(-xp.logaddexp(0.0, xp.logaddexp(left, right)))


def selective_flux(
    c_from,
    c_to,
    delta_voltage,
    valence,
    temperature,
    area,
    permeability,
    residual,
    gate,
    multiplier,
    *,
    xp=jnp,
):
    x = valence * F * delta_voltage / (R * temperature)
    available = multiplier * (residual + (1 - residual) * gate)
    return (
        area
        * permeability
        * available
        / MOL_PER_FMOL
        * (c_from * bernoulli(-x, xp=xp) - c_to * bernoulli(x, xp=xp))
    )


def selective_one_way(
    c_from,
    c_to,
    delta_voltage,
    valence,
    temperature,
    area,
    permeability,
    residual,
    gate,
    multiplier,
    *,
    xp=jnp,
):
    """(from -> to, to -> from): selective_flux's two one-way parts, each >= 0, in its units
    (module docstring). The prefactor's operations are selective_flux's, in its order."""
    x = valence * F * delta_voltage / (R * temperature)
    available = multiplier * (residual + (1 - residual) * gate)
    conductance = area * permeability * available / MOL_PER_FMOL
    return conductance * (c_from * bernoulli(-x, xp=xp)), conductance * (c_to * bernoulli(x, xp=xp))
