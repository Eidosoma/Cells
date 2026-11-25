"""kv1p2_mh@1: Kv1.2-type potassium channel gating, the law and its declaration on @3.

Two gates, activation m and inactivation h, relax toward logistic targets of the membrane voltage V
(inside less outside, volts), with logistic time constants (seconds); the population is open in
proportion to m h, and K⁺ crosses by the host's constant-field flux. The coefficients are BETSE
v1.5.0's Kv1p2 channel class (betse/science/channels/vg_k.py:180 at commit 5269a714, read as text,
never run here; BSD-2-Clause), converted from its millivolts and milliseconds. Cells evaluates the
continuous equations: the source's semi-implicit update clock is not adopted, and its nominal
reversal voltage gives way to the constant-field flux at the concentrations
(docs/TISSUE_RETURN_CURRENT.md, the Kv1 correspondence). BETSE's docstring cites Sprunger LK. et
al. Effects of charybdotoxin on K+ channel (KV1.2) deactivation and inactivation kinetics. Eur. J.
Pharmacol., 1996 Oct 31, 314 (357-64); that work is not read here.

Ported from the Kv1 catalogue (laws/channels/kv1_channels.py, its code 7), as seam F's step-2
extraction (D211, D213): this module holds the law's numbers, and the catalogue's dispatcher
gathers the same floats, a recorded temporary second form that retires with the shared catalogue
(the lead's ruling (B), 18 November 2026). Held bitwise to it under NumPy; under JAX
within 32 ulps, because XLA on CPU rewrites x / constant as x * (1/constant) while the dispatcher
divides by gathered arrays (tests/unit/test_kv1_channel_laws.py).

Channel code 6 of resolved_pump_tissue@3 (cells.channel_law@1), registered from @3's row of the
model table since @3's parser reads its channel table from the law registry (the Kv1 trigger).
"""

import jax.numpy as jnp

from cells.laws.channels.kv1p5_mh import VOLTAGE_DOMAIN_V  # The catalogue's domain, -120..60 mV.
from cells.modules import ChannelLaw, Citation, CitedWork

LAW_ID = "kv1p2_mh@1"
ACTIVATION = (-0.021, -0.0113943)  # Its target's logistic: (midpoint V, slope V).
INACTIVATION = (-0.022, 0.0113943)
ACTIVATION_TAU = (0.15, -0.06756, 0.0341479)  # (scale s, midpoint V, slope V)
INACTIVATION_TAU = (15, -0.04656, -0.0441479)
# The RK4 bound that the Kv1 populations' tissue tests qualified, as with sodium channels: 2.5 us.
RK4_STEP_S = 2.5e-6


def kinetics(voltage, *, xp=jnp):
    """Gate targets and time constants [..., 2, n] (s), with voltage in volts."""

    def logistic(midpoint, slope):
        return 1 / (1 + xp.exp((voltage - midpoint) / slope))

    activation = logistic(*ACTIVATION)
    inactivation = logistic(*INACTIVATION)
    activation_tau = ACTIVATION_TAU[0] * logistic(*ACTIVATION_TAU[1:])
    inactivation_tau = INACTIVATION_TAU[0] * logistic(*INACTIVATION_TAU[1:])
    return (
        xp.stack((activation, inactivation), axis=-2),
        xp.stack((activation_tau, inactivation_tau), axis=-2),
    )


def opening(gates, *, xp):
    """The open fraction m h, [..., channel]."""
    m, h = gates[..., 0, :], gates[..., 1, :]
    return m * h


LAW = ChannelLaw(
    LAW_ID,
    6,
    ("m", "h"),
    (("K", 1, 1.0),),
    VOLTAGE_DOMAIN_V,
    RK4_STEP_S,
    kinetics,
    opening,
    host="cells.resolved_pump_tissue@3",
    provenance="cited",
    source=Citation(
        "BETSE v1.5.0's Kv1p2 channel class, read as text",
        "betse/science/channels/vg_k.py:180 (class Kv1p2) at commit 5269a714; BETSE's docstring "
        "cites Sprunger LK. et al. Effects of charybdotoxin on K+ channel (KV1.2) deactivation and"
        " inactivation kinetics. Eur. J. Pharmacol., 1996 Oct 31, 314 (357-64) (not read)",
        "BSD-2-Clause, BETSE's licence (its LICENSE at 5269a714): the coefficients are taken "
        "from its source; no code is copied",
        (
            "continuous gates in volts and seconds: the source's semi-implicit update clock is "
            "not adopted",
            "the constant-field flux at the concentrations in place of the source's nominal "
            "reversal voltage",
        ),
        (
            CitedWork(
                ("Alexis Pietak", "Cecil Curry"),
                2025,
                "BETSE (BioElectric Tissue Simulation Engine) 1.5.0",
                url="https://github.com/betsee/betse",
            ),
        ),
    ),
    test="tests/unit/test_kv1_channel_laws.py::test_each_kv1_law_matches_its_references",
)
