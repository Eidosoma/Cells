"""kir2p1_mh2@1: Kir2.1-type inward-rectifier potassium channel gating, the law and its
declaration on @3.

Two gates m and h relax toward logistic targets of the membrane voltage V (volts) with
voltage-dependent time constants (seconds); the population is open in proportion to (m h) h.
The coefficients and the m h² opening correspond to BETSE v1.5.0's Kir2p1 channel, as
docs/TISSUE_RETURN_CURRENT.md records; this is an independently expressed continuous law, not the
source's discrete clock or a new fit to measurements. Channel code 1 of resolved_pump_tissue@3
(cells.channel_law@1), registered by the law registry's loader (docs/CORE_SEAMS_DESIGN.md §8.2).
Moved from laws/channels/potassium_channels.py, which re-imports these names.
"""

import jax.numpy as jnp

from cells.laws.channels.kv1p5_mh import VOLTAGE_DOMAIN_V  # @3's channel domain, -120..60 mV.
from cells.modules import ChannelLaw

LAW_ID = "kir2p1_mh2@1"
RK4_STEP_S = 25e-6  # The resolved channel family's qualified RK4 bound.


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


def opening(gates, *, xp):
    """The open fraction (m h) h, today's operation order (potassium_channels.opening)."""
    m, h = gates[..., 0, :], gates[..., 1, :]
    return m * h * h


LAW = ChannelLaw(
    LAW_ID,
    1,
    ("m", "h"),
    (("K", 1, 1.0),),
    VOLTAGE_DOMAIN_V,
    RK4_STEP_S,
    kir2p1_kinetics,
    opening,
    host="cells.resolved_pump_tissue@3",
)
