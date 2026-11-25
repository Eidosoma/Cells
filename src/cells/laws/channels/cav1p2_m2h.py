"""cav1p2_m2h@1: CaV1.2-type calcium channel gating, the law and its declaration on @3.

Two gates, activation m and inactivation h, relax toward sigmoid targets of the membrane voltage V
(inside less outside, volts), with sigmoid time constants (seconds). Both read the voltage less
10 mV, u = V - 0.010 V, a shift that is part of the law. The population is open in proportion to
m² h, and Ca²⁺ (valence 2) crosses by the host's constant-field flux at the concentrations:

    m_inf = 1 / (1 + exp(-(u + 0.030) / 0.006)),    h_inf = 1 / (1 + exp((u + 0.080) / 0.0064)),
    tau_m = 0.005 + 0.020 / (1 + exp((u + 0.025) / 0.005)),
    tau_h = 0.020 + 0.050 / (1 + exp((u + 0.040) / 0.007)).

The coefficients are BETSE v1.5.0's Cav1p2 channel class (betse/science/channels/vg_ca.py:292 at
commit 5269a714, read as text, never run here; BSD-2-Clause), converted from its millivolts and
milliseconds. Cells evaluates the continuous equations: the source's semi-implicit update clock is
not adopted, and its nominal reversal voltage gives way to the constant-field flux at the
concentrations (docs/PLASMA_CALCIUM.md). There is no temperature term. The source's docstring cites
Carlin KP. et al. Characterization of calcium currents in functionally mature mouse spinal
motoneurons. Eur. J. Neurosci., 2000 May, 12 (1624-34); that work is not read here.

Moved from laws/channels/calcium_gates.py, an older family's kernel, which re-imports these names:
moving is not calibrating, so its provenance is parity, its Citation kept as its source.

It declares no RK4 step bound, so no RK4 grid runs it. Its material term names the kernel of its
flux's material slope (laws/routes/constant_field_permeation.py). The host holds the step to that
slope at every explicit stage, at calcium's rows at both ends
(surface_pump_v3.channel_material_rates), since the charge rule alone does not hold a scarce ion's
amounts.

Channel code 11 of resolved_pump_tissue@3 (cells.channel_law@1), registered by the law registry's
loader from @3's row of the model table (docs/CORE_SEAMS_DESIGN.md §8.2).
"""

import jax.numpy as jnp

from cells.laws.channels.kv1p5_mh import VOLTAGE_DOMAIN_V  # @3's channel domain, -120..60 mV.
from cells.modules import ChannelLaw, Citation, CitedWork

LAW_ID = "cav1p2_m2h@1"
SHIFT_V = 0.010  # The gates read the voltage less this.


def kinetics(voltage, *, xp=jnp):
    """Gate targets and time constants [..., 2, n] (s), with voltage in volts."""

    def sigmoid(value):
        e = xp.exp(-xp.abs(value))
        return xp.where(value >= 0, 1 / (1 + e), e / (1 + e))

    shifted = voltage - SHIFT_V
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


def opening(gates, *, xp=jnp):
    """The open fraction m² h, [..., channel]."""
    return gates[..., 0, :] ** 2 * gates[..., 1, :]


LAW = ChannelLaw(
    LAW_ID,
    11,
    ("m", "h"),
    (("Ca", 2, 1.0),),
    VOLTAGE_DOMAIN_V,
    None,  # No RK4 grid runs it.
    kinetics,
    opening,
    material_term="material_slope_per_s",
    host="cells.resolved_pump_tissue@3",
    provenance="parity",
    source=Citation(
        "BETSE v1.5.0's Cav1p2 channel class, read as text",
        "betse/science/channels/vg_ca.py:292 (class Cav1p2) at commit 5269a714; BETSE's docstring "
        "cites Carlin KP. et al. Characterization of calcium currents in functionally mature mouse "
        "spinal motoneurons. Eur. J. Neurosci., 2000 May, 12 (1624-34) (not read)",
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
    test="tests/unit/test_kv1_channel_laws.py"
    "::test_the_calcium_law_meets_its_reference_and_each_plant_misses_it",
)
