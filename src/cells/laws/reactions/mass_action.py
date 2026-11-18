"""Reversible ideal mass action with rate ratios fixed by standard potentials."""

import jax.numpy as jnp


def reversible_flux(activity, reactants, products, delta_mu_RT, scale_fmol_per_s, *, xp=jnp):
    """Return net fmol/s and dimensionless affinity; activities must be positive.

    scale = volume * standard concentration * forward_rate_per_s. The reverse
    constant is forward_rate_per_s * exp(delta_mu_RT), enforcing detailed balance.
    The expm1 form retains small differences near equilibrium without clipping.
    Species and reactions occupy the final two axes.
    """
    logarithm = xp.log(activity)
    forward = xp.sum(reactants * logarithm, axis=-2)
    reverse = xp.sum(products * logarithm, axis=-2) + delta_mu_RT
    affinity = forward - reverse
    net = (
        scale_fmol_per_s
        * xp.exp(xp.maximum(forward, reverse))
        * (-xp.expm1(-xp.abs(affinity)))
        * xp.sign(affinity)
    )
    return net, affinity
