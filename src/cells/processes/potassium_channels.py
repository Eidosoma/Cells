"""Named potassium gate laws for resolved tissue, in volts and seconds.

Kir2.1 coefficients and m*h**2 opening correspond to pinned BETSE 1.5.0's
Kir2p1. This independently expressed continuous law is not its discrete clock
or a new fit to measurements. See docs/TISSUE_RETURN_CURRENT.md.
"""

import jax.numpy as jnp

from cells.processes import voltage_gates

KIR_LAW_ID = "betse_kir2p1_mh2@1"
LAW_CODES = {voltage_gates.LAW_ID: 0, KIR_LAW_ID: 1}
TEMPERATURE_K = voltage_gates.TEMPERATURE_K
VOLTAGE_DOMAIN_V = voltage_gates.VOLTAGE_DOMAIN_V


def kir2p1_kinetics(voltage, *, xp=jnp):
    def logistic(x):
        e = xp.exp(-xp.abs(x))
        return xp.where(x >= 0, 1 / (1 + e), e / (1 + e))

    target = xp.stack(
        (logistic(-(voltage + 0.09648) / 0.02326), logistic((voltage + 0.16828) / 0.04413)),
        axis=-2,
    )
    tau = xp.stack(
        (
            0.0037 - 0.00337 * logistic(-(voltage + 0.0329) / 0.02793),
            0.00085 + 0.3063 * logistic((voltage + 0.11829) / 0.02723),
        ),
        axis=-2,
    )
    return target, tau


def kinetics(voltage, law_codes, *, xp=jnp):
    """Array dispatch; final voltage axis is the channel population axis."""
    kv = voltage_gates.kinetics(voltage, xp=xp)
    kir = kir2p1_kinetics(voltage, xp=xp)
    mask = xp.expand_dims(law_codes == 1, -2)
    return tuple(xp.where(mask, b, a) for a, b in zip(kv, kir, strict=True))


def opening(gates, law_codes, *, xp=jnp):
    m, h = gates[..., 0, :], gates[..., 1, :]
    return m * h * xp.where(law_codes == 1, h, 1.0)


def valid_codes(law_codes, *, xp=jnp):
    return xp.all((law_codes == 0) | (law_codes == 1))
