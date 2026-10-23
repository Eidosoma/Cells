"""Prescribed, dimensionless patch damage; not an energy-supported repair law.

An injury hazard opens the intact fraction. Resealing closes the damaged
fraction. Both rates have units s^-1; neither resets any physical inventory.
"""

import jax.numpy as jnp

LAW_ID = "prescribed_patch_injury_resealing@1"


def rates(damage, injury_rate, resealing_rate, injury, resealing, *, xp=jnp):
    opened = injury_rate * injury * (1 - damage)
    closed = resealing_rate * resealing * damage
    return opened - closed, opened, closed
