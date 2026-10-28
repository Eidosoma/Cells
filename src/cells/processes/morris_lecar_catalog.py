"""53 laws with explicit two-, one- and zero-state population contracts."""

import jax.numpy as jnp

from cells.processes import calcium_activated_catalog as prior
from cells.processes import morris_lecar_channels as ml

LAW_CODES = prior.LAW_CODES | ml.LAW_CODES
LAW_PERMEABILITIES = prior.LAW_PERMEABILITIES | ml.LAW_PERMEABILITIES
SPECIES_VALENCE = prior.SPECIES_VALENCE
STATE_COUNTS = {
    law: 0 if code == 39 else 2 for law, code in prior.LAW_CODES.items()
} | ml.STATE_COUNTS


def selected(codes, *, xp):
    codes = xp.asarray(codes)
    return (codes >= 40) & (codes <= 52)


def gate_active(law_codes, *, xp=jnp):
    """Mask each of the two packed rows, including absent h and algebraic m."""
    codes = xp.asarray(law_codes)
    count = xp.where(codes < 39, 2, xp.where(ml.is_dynamic(codes, xp=xp), 1, 0))
    return xp.arange(2)[:, None] < xp.expand_dims(count, -2)


def kinetics(voltage, law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    use = selected(codes, xp=xp)
    old = prior.kinetics(xp.where(use, 0.0, voltage), xp.where(use, 0, codes), xp=xp)
    target, tau = ml.kinetics(xp.where(use, voltage, 0.0), xp.where(use, codes, ml.PAD_CODE), xp=xp)
    target = xp.where(ml.is_dynamic(codes, xp=xp), target, 0.0)
    added = (
        xp.stack((target, xp.zeros_like(target)), axis=-2),
        xp.stack((tau, xp.zeros_like(tau)), axis=-2),
    )
    return tuple(xp.where(xp.expand_dims(use, -2), b, a) for a, b in zip(old, added, strict=True))


def opening(gates, law_codes, *, voltage, calcium_free_mM, temperature_K, xp=jnp):
    codes = xp.asarray(law_codes)
    use = selected(codes, xp=xp)
    old = prior.opening(
        gates,
        xp.where(use, 0, codes),
        voltage=voltage,
        calcium_free_mM=calcium_free_mM,
        temperature_K=temperature_K,
        xp=xp,
    )
    added = ml.opening(
        xp.where(use, xp.take(gates, 0, axis=-2), 0.0),
        xp.where(use, voltage, 0.0),
        xp.where(use, codes, ml.PAD_CODE),
        xp=xp,
    )
    return xp.where(use, added, old)


def hybrid_domain_valid(gates, voltage, calcium_free_mM, temperature_K, codes, control, *, xp):
    use = selected(codes, xp=xp)
    return prior.instantaneous_domain_valid(
        voltage, calcium_free_mM, temperature_K, xp.where(use, 0, codes), control, xp=xp
    ) & ml.domain_valid(
        xp.where(use, xp.take(gates, 0, axis=-2), 0.0),
        xp.where(use, voltage, 0.0),
        xp.where(use, codes, ml.PAD_CODE),
        xp=xp,
    )


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.ndim < 1 or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    return xp.all((codes >= 0) & (codes <= 52))


def controls_valid(law_codes, availability, active, *, xp=jnp):
    codes, present = xp.asarray(law_codes), xp.asarray(active)
    if codes.ndim < 1 or present.shape != codes.shape or present.dtype.kind != "b":
        return xp.asarray(False)
    return (
        valid_codes(codes, xp=xp)
        & prior.controls_valid(
            xp.where(selected(codes, xp=xp), 0, codes), availability, active, xp=xp
        )
        & xp.all(xp.where(present, True, codes == 0))
    )
