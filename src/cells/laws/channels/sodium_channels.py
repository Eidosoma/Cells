"""Named NaV1.2/Kv1.5/Kir2.1 laws for the resolved multispecies catalog.

NaV1.2 follows BETSE v1.5.0 Nav1p2 coefficients, including its voltage
shifts and m**3*h opening. Removable rate singularities use their analytic
limits. This is a continuous-time law, not the native discrete update clock. The law's own
module is laws/channels/nav1p2_m3h_regularized.py (docs/CORE_SEAMS_DESIGN.md §8.2); this one
dispatches over the catalogue's codes and re-imports its names.
"""

import jax.numpy as jnp

from cells.laws.channels import potassium_channels
from cells.laws.channels.nav1p2_m3h_regularized import LAW_ID, nav1p2_kinetics

LAW_CODES = {**potassium_channels.LAW_CODES, LAW_ID: 2}
LAW_SPECIES = {law: "Na" if law == LAW_ID else "K" for law in LAW_CODES}


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
