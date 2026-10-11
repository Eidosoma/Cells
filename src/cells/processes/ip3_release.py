"""Pinned BETSE IP3 Hill factor, evaluated on the current owned concentration."""

import jax.numpy as jnp

LAW_ID = "betse_1_5_ip3_er_release@1"


def open_fraction(ip3_mM, activation_mM, activation_n, *, xp=jnp):
    # Keep the zero-ligand limit exact without taking log(0), including in JAX.
    positive = ip3_mM > 0
    log_c = xp.log(xp.where(positive, ip3_mM, 1.0))
    fraction = xp.exp(-xp.logaddexp(0.0, activation_n * (xp.log(activation_mM) - log_c)))
    return xp.where(ip3_mM >= 0, xp.where(positive, fraction, 0.0), xp.nan)
