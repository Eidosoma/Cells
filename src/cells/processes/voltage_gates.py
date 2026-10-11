"""Pure continuous m/h kinetics in volts/seconds; no implicit preparation.

SPEC-006 specifies the BETSE-v1.5.0 Kv1p5-derived engineering law. This is not
native BETSE execution or a temperature-calibrated channel catalog.
"""

import jax.numpy as jnp

LAW_ID = "betse_kv1p5_mh@1"
TEMPERATURE_K = 298.15
VOLTAGE_DOMAIN_V = (-0.120, 0.060)


def kinetics(voltage, *, xp=jnp):
    def sigmoid(value):
        e = xp.exp(-xp.abs(value))
        return xp.where(value >= 0, 1 / (1 + e), e / (1 + e))

    targets = xp.stack(
        (sigmoid((voltage + 0.0060) / 0.0064), sigmoid(-(voltage + 0.0253) / 0.0035)), axis=-2
    )
    tau = xp.stack((0.008330 - 0.1163 * voltage, 1.620000 - 15.500 * voltage), axis=-2)
    return targets, tau
