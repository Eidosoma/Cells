"""Pure physical edge flux and symmetric dynamic gate target, independent of assays.

Positive flux is from -> to. The external multiplier blocks all residual and
gated permeability without altering the endogenous gate equation. These are not
BITSEY's upwind transport or instantaneous source gate.
"""

import jax.numpy as jnp

from cells.processes.electrochemistry import MOL_PER_FMOL, F, R, bernoulli


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
