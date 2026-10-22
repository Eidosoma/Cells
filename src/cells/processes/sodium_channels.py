"""Named NaV1.2/Kv1.5/Kir2.1 laws for the resolved multispecies catalog.

NaV1.2 follows pinned BETSE 1.5.0 Nav1p2 coefficients, including its voltage
shifts and m**3*h opening. Removable rate singularities use their analytic
limits. This is a continuous-time law, not the native discrete update clock.
"""

import jax.numpy as jnp

from cells.processes import potassium_channels
from cells.processes.electrochemistry import bernoulli

LAW_ID = "betse_nav1p2_m3h_regularized@1"
LAW_CODES = {**potassium_channels.LAW_CODES, LAW_ID: 2}
LAW_SPECIES = {law: "Na" if law == LAW_ID else "K" for law in LAW_CODES}


def nav1p2_kinetics(voltage, *, xp=jnp):
    """Gate targets and time constants in seconds, with voltage in volts."""
    shifted = (voltage + 0.025) / 0.009
    activation = 0.182 * 9 * bernoulli(-shifted, xp=xp)
    deactivation = 0.124 * 9 * bernoulli(shifted, xp=xp)
    recovery = 0.024 * 5 * bernoulli(-(voltage + 0.040) / 0.005, xp=xp)
    inactivation = 0.0091 * 5 * bernoulli((voltage + 0.065000123) / 0.005, xp=xp)
    target = xp.stack(
        (
            activation / (activation + deactivation),
            1 / (1 + xp.exp((voltage + 0.055) / 0.0062)),
        ),
        axis=-2,
    )
    tau = xp.stack(
        (0.001 / (activation + deactivation), 0.001 / (recovery + inactivation)), axis=-2
    )
    return target, tau


def kinetics(voltage, law_codes, *, xp=jnp):
    potassium = potassium_channels.kinetics(voltage, law_codes, xp=xp)
    sodium = nav1p2_kinetics(voltage, xp=xp)
    selected = xp.expand_dims(law_codes == 2, -2)
    return tuple(xp.where(selected, b, a) for a, b in zip(potassium, sodium, strict=True))


def opening(gates, law_codes, *, xp=jnp):
    return xp.where(
        law_codes == 2,
        gates[..., 0, :] ** 3 * gates[..., 1, :],
        potassium_channels.opening(gates, law_codes, xp=xp),
    )


def valid_codes(law_codes, *, xp=jnp):
    return xp.all((law_codes == 0) | (law_codes == 1) | (law_codes == 2))
