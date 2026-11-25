"""kv1p5_mh@1: Kv1.5-type potassium channel gating, the law and its declaration on @3.

Two gates, activation m and inactivation h, relax toward sigmoid targets of the membrane voltage
V (inside less outside, volts) with time constants linear in V (seconds); the population is open
in proportion to m h, and K⁺ crosses by the host's constant-field flux. The equations are
SPEC-006's engineering law (docs/VOLTAGE_GATED_CHANNEL_SPEC.md), which derives the two-gate form
and its coefficients from BETSE v1.5.0's Kv1p5 channel, converted to SI units with both gate
powers one; SPEC-006 read the source. The gates follow the continuous equations, not the source's
update clock, and carry no temperature term (fixed at 298.15 K); the domain, -120 to 60 mV, keeps
both time constants positive. It is a law of the inner model resolved_pump_tissue@3, channel code
0 (cells.channel_law@1), declared here and registered by the law registry's loader
(registry/laws.py; docs/CORE_SEAMS_DESIGN.md §8.2). laws/channels/voltage_gates.py re-imports
these names.
"""

import jax.numpy as jnp

from cells.modules import ChannelLaw

LAW_ID = "kv1p5_mh@1"
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


RK4_STEP_S = 25e-6  # The resolved channel family's qualified RK4 bound.


def opening(gates, *, xp):
    """The open fraction m h, [..., channel]."""
    return gates[..., 0, :] * gates[..., 1, :]


LAW = ChannelLaw(
    LAW_ID,
    0,
    ("m", "h"),
    (("K", 1, 1.0),),
    VOLTAGE_DOMAIN_V,
    RK4_STEP_S,
    kinetics,
    opening,
    host="cells.resolved_pump_tissue@3",
    test="tests/unit/test_channel_law_kernels.py"
    "::test_kv1p5_meets_the_independent_decimals_and_each_plant_misses_them",
)
