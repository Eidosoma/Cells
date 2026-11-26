"""cells.channel.nav1p2_m3h_regularized@1: NaV1.2-type sodium channel gating, the law and its declaration
on @3.

Two gates, activation m and inactivation h, follow BETSE v1.5.0's Nav1p2 coefficients, with its
voltage shifts and m³ h opening; removable rate singularities take their analytic limits (the
Bernoulli function of laws/electrochemistry.py). This is a continuous-time law, not the native
discrete update clock. Channel code 2 of cells.model.resolved_pump_tissue@3 (cells.channel_law@1),
registered by the law registry's loader (docs/CORE_SEAMS_DESIGN.md §8.2). Moved from
laws/channels/sodium_channels.py, which re-imports these names.
"""

import jax.numpy as jnp

from cells.laws.channels.kv1p5_mh import VOLTAGE_DOMAIN_V  # @3's channel domain, -120..60 mV.
from cells.laws.electrochemistry import bernoulli
from cells.modules import ChannelLaw

LAW_ID = "cells.channel.nav1p2_m3h_regularized@1"
RK4_STEP_S = 2.5e-6  # The resolved channel family's qualified RK4 bound with NaV1.2.


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


def opening(gates, *, xp):
    """The open fraction m³ h, today's operation order (sodium_channels.opening)."""
    return gates[..., 0, :] ** 3 * gates[..., 1, :]


LAW = ChannelLaw(
    LAW_ID,
    2,
    ("m", "h"),
    (("Na", 1, 1.0),),
    VOLTAGE_DOMAIN_V,
    RK4_STEP_S,
    nav1p2_kinetics,
    opening,
    host="cells.model.resolved_pump_tissue@3",
)
