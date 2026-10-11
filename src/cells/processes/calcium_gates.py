"""Pinned BETSE Cav1p2 targets/time constants in volts and seconds.

The native -10 mV shift is part of this law. Continuous relaxation is integrated
by Cells' ordinary solver; this is not BETSE's semi-implicit time updater.
"""

import jax.numpy as jnp

LAW_ID = "betse_cav1p2_m2h@1"
TEMPERATURE_K = 298.15
VOLTAGE_DOMAIN_V = (-0.120, 0.060)
MIN_TAU_S = 0.005


def kinetics(voltage, *, xp=jnp):
    def sigmoid(value):
        e = xp.exp(-xp.abs(value))
        return xp.where(value >= 0, 1 / (1 + e), e / (1 + e))

    shifted = voltage - 0.010
    targets = xp.stack(
        (sigmoid((shifted + 0.030) / 0.006), sigmoid(-(shifted + 0.080) / 0.0064)),
        axis=-2,
    )
    tau = xp.stack(
        (
            0.005 + 0.020 * sigmoid(-(shifted + 0.025) / 0.005),
            0.020 + 0.050 * sigmoid(-(shifted + 0.040) / 0.007),
        ),
        axis=-2,
    )
    return targets, tau


def open_probability(gate):
    return gate[..., 0, :] ** 2 * gate[..., 1, :]
