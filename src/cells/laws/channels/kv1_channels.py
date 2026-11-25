"""Complete BETSE v1.5.0 Kv1 family in the shared multi-ion channel catalog.

Kv1.1/2/3/4/6 extend the previously qualified Kv1.5, Kir2.1, NaV1.2 and HCN
laws. Voltage is in volts and time constants in seconds. These continuous
equations preserve source gate powers; they do not adopt BETSE's update clock.

Each law's numbers live in its own module, laws/channels/kv1p{1,2,3,4,6}_mh*.py, the law's one
source (docs/CORE_SEAMS_DESIGN.md §8.6 as amended: the lead's ruling (B), 18 November 2026). This
dispatcher gathers the same floats per element: a recorded temporary second form of the five laws'
math, which retires with the shared catalogue, holds these five, and takes no new law
(tests/unit/test_kv1_channel_laws.py). Its program text and outputs are today's. Why the two forms
differ under JAX: XLA on CPU rewrites x / constant as x * (1/constant), while this dispatcher
divides by gathered arrays, which it keeps exact; the per-law kernels, which divide by constants,
are held to it bitwise under NumPy and within 32 ulps under JAX.
"""

import jax.numpy as jnp

from cells.laws.channels import hcn_channels, kv1p1_mh2, kv1p2_mh, kv1p3_mh, kv1p4_mh, kv1p6_mh

FAMILIES = (1, 2, 3, 4, 6)
LAWS = (kv1p1_mh2, kv1p2_mh, kv1p3_mh, kv1p4_mh, kv1p6_mh)  # Catalogue codes 6-10, in order.
KV1_LAWS = {law.LAW_ID: i for law, i in zip(LAWS, FAMILIES, strict=True)}
LAW_CODES = {**hcn_channels.LAW_CODES, **{law: i for i, law in enumerate(KV1_LAWS, 6)}}
LAW_PERMEABILITIES = hcn_channels.LAW_PERMEABILITIES | {law: (("K", 1.0),) for law in KV1_LAWS}
SPECIES_VALENCE = hcn_channels.SPECIES_VALENCE
# A logistic time constant's (scale, midpoint, slope) where a law's takes another form (Kv1.3's
# affine, Kv1.4's constant), which then replaces it.
PLACEHOLDER = (0, 0, 1)


def _columns(name, *, logistic_tau=False):
    """Each coefficient of `name` across the five laws, as the lists this dispatcher gathers."""
    rows = [
        PLACEHOLDER if logistic_tau and law in (kv1p3_mh, kv1p4_mh) else getattr(law, name)
        for law in LAWS
    ]
    return [list(column) for column in zip(*rows, strict=True)]


def kinetics(voltage, law_codes, *, xp=jnp):
    target, tau = hcn_channels.kinetics(voltage, law_codes, xp=xp)
    index = xp.clip(law_codes - 6, 0, 4)

    def parameters(values):
        return xp.asarray(values)[index]

    def logistic(midpoint, slope):
        return 1 / (1 + xp.exp((voltage - parameters(midpoint)) / parameters(slope)))

    activation = logistic(*_columns("ACTIVATION"))
    inactivation = logistic(*_columns("INACTIVATION"))
    scale, midpoint, slope = _columns("ACTIVATION_TAU", logistic_tau=True)
    activation_tau = parameters(scale) * logistic(midpoint, slope)
    scale, midpoint, slope = _columns("INACTIVATION_TAU", logistic_tau=True)
    inactivation_tau = parameters(scale) * logistic(midpoint, slope)
    intercept, gradient = kv1p3_mh.ACTIVATION_TAU
    activation_tau = xp.where(index == 2, intercept - gradient * voltage, activation_tau)
    intercept, gradient = kv1p3_mh.INACTIVATION_TAU
    inactivation_tau = xp.where(index == 2, intercept - gradient * voltage, inactivation_tau)
    activation_tau = xp.where(index == 3, kv1p4_mh.ACTIVATION_TAU_S, activation_tau)
    inactivation_tau = xp.where(index == 3, kv1p4_mh.INACTIVATION_TAU_S, inactivation_tau)
    selected = xp.expand_dims(law_codes >= 6, -2)
    return (
        xp.where(selected, xp.stack((activation, inactivation), axis=-2), target),
        xp.where(selected, xp.stack((activation_tau, inactivation_tau), axis=-2), tau),
    )


def opening(gates, law_codes, *, xp=jnp):
    m, h = gates[..., 0, :], gates[..., 1, :]
    return xp.where(
        law_codes >= 6,
        m * h * xp.where(law_codes == 6, h, 1.0),
        hcn_channels.opening(gates, law_codes, xp=xp),
    )


def valid_codes(law_codes, *, xp=jnp):
    return xp.all((law_codes >= 0) & (law_codes <= 10) & (law_codes == xp.floor(law_codes)))
