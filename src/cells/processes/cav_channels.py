"""Pinned CaV populations in the shared Na/K/Ca channel catalog.

Volts/seconds, with source gate powers and K/Na/HCN laws retained. CaV2.2's
removable +20-mV singularity uses its analytic limit. CaV3.1 deliberately
retains the source's -0.01-mV branch threshold, not an inferred -10-mV repair.
"""

import jax.numpy as jnp

from cells.processes import calcium_gates, kv1_channels
from cells.processes.electrochemistry import bernoulli

CAV_LAWS = {
    "betse_cav1p2_m2h@1": "Cav1p2",
    "betse_cav1p3_m2h@1": "Cav1p3",
    "betse_cav2p1_m@1": "Cav2p1",
    "betse_cav2p2_m2h_regularized@1": "Cav2p2",
    "betse_cav2p3_mh@1": "Cav2p3",
    "betse_cav3p1_mh_source_branch@1": "Cav3p1",
    "betse_cav3p3_mh@1": "Cav3p3",
}
LAW_CODES = {**kv1_channels.LAW_CODES, **{law: i for i, law in enumerate(CAV_LAWS, 11)}}
LAW_PERMEABILITIES = kv1_channels.LAW_PERMEABILITIES | {law: (("Ca", 1.0),) for law in CAV_LAWS}
SPECIES_VALENCE = kv1_channels.SPECIES_VALENCE


def cav_kinetics(voltage, law_codes, *, xp=jnp):
    """CaV targets and time constants; codes 11–17 have defined meaning here."""
    target, tau = calcium_gates.kinetics(voltage, xp=xp)

    def sigmoid(midpoint, slope):
        return 1 / (1 + xp.exp((voltage - midpoint) / slope))

    def select(code, m, h, tm, th):
        nonlocal target, tau
        mask = xp.expand_dims(law_codes == code, -2)
        target = xp.where(mask, xp.stack((m, h), axis=-2), target)
        tau = xp.where(mask, xp.stack((tm, th), axis=-2), tau)

    one = xp.ones_like(voltage)
    select(
        12,
        sigmoid(-0.030, -0.006),
        sigmoid(-0.080, 0.0064),
        0.005 + 0.020 * sigmoid(-0.025, 0.005),
        0.020 + 0.050 * sigmoid(-0.040, 0.007),
    )
    a, b = 8.5 * sigmoid(0.008, -0.0125), 35 * sigmoid(-0.074, 0.0145)
    select(13, a / (a + b), one, 0.001 / (a + b), 0.001 * one)
    a = bernoulli(-(voltage - 0.020) / 0.010, xp=xp)
    b = 0.4 * xp.exp(-(voltage + 0.025) / 0.018)
    c = 0.01 * xp.exp(-(voltage + 0.050) / 0.010)
    d = 0.1 * sigmoid(-0.017, -0.017)
    select(14, a / (a + b), c / (c + d), 0.001 / (a + b), 0.001 / (c + d))
    a, b = 2.6 * sigmoid(-0.007, -0.008), 0.18 * sigmoid(-0.026, 0.004)
    c, d = 0.0025 * sigmoid(-0.032, 0.008), 0.19 * sigmoid(-0.042, -0.010)
    select(15, a / (a + b), c / (c + d), 0.001 / (a + b), 0.001 / (c + d))
    select(
        16,
        sigmoid(-0.042921064, -0.005163208),
        sigmoid(-0.072907420, 0.004575763),
        xp.where(
            voltage * 1000 >= -0.01,
            0.001,
            -0.000855809 + 0.001493527 * xp.exp(-voltage / 0.027414182),
        ),
        0.009987873 + 0.000002883 * xp.exp(-voltage / 0.005598574),
    )
    select(
        17,
        sigmoid(-0.045454426, -0.005073015),
        sigmoid(-0.074031965, 0.008416382),
        0.003394938 + 0.054187616 * sigmoid(-0.040040397, 0.004110392),
        0.109701136 + 0.000003816 * xp.exp(-voltage / 0.004781719),
    )
    return target, tau


def kinetics(voltage, law_codes, *, xp=jnp):
    previous = kv1_channels.kinetics(voltage, law_codes, xp=xp)
    calcium = cav_kinetics(voltage, law_codes, xp=xp)
    mask = xp.expand_dims(law_codes >= 11, -2)
    return tuple(xp.where(mask, b, a) for a, b in zip(previous, calcium, strict=True))


def opening(gates, law_codes, *, xp=jnp):
    m, h = gates[..., 0, :], gates[..., 1, :]
    calcium = m * xp.where((law_codes == 11) | (law_codes == 12) | (law_codes == 14), m, 1.0)
    calcium *= xp.where(law_codes == 13, 1.0, h)
    return xp.where(law_codes >= 11, calcium, kv1_channels.opening(gates, law_codes, xp=xp))


def valid_codes(law_codes, *, xp=jnp):
    return xp.all((law_codes >= 0) & (law_codes <= 17) & (law_codes == xp.floor(law_codes)))
