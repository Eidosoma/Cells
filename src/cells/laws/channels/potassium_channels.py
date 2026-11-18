"""Named potassium gate laws for resolved tissue, in volts and seconds.

Kir2.1 coefficients and m*h**2 opening correspond to BETSE v1.5.0's
Kir2p1. This independently expressed continuous law is not its discrete clock
or a new fit to measurements. See docs/TISSUE_RETURN_CURRENT.md. The law's own module is
laws/channels/kir2p1_mh2.py (docs/CORE_SEAMS_DESIGN.md §8.2); this one keeps the older
families' dispatch and re-imports its names.
"""

import jax.numpy as jnp

from cells.laws.channels import voltage_gates
from cells.laws.channels.kir2p1_mh2 import LAW_ID as KIR_LAW_ID
from cells.laws.channels.kir2p1_mh2 import kir2p1_kinetics

LAW_CODES = {voltage_gates.LAW_ID: 0, KIR_LAW_ID: 1}
TEMPERATURE_K = voltage_gates.TEMPERATURE_K
VOLTAGE_DOMAIN_V = voltage_gates.VOLTAGE_DOMAIN_V


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
