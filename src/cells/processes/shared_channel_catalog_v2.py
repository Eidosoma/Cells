"""39-law shared catalog; previous law codes and the 35-law module stay fixed."""

import jax.numpy as jnp

from cells.processes import calcium_catalog_extra as calcium
from cells.processes import shared_channel_catalog as prior

LAW_CODES = prior.LAW_CODES | calcium.LAW_CODES
LAW_PERMEABILITIES = prior.LAW_PERMEABILITIES | calcium.LAW_PERMEABILITIES
SPECIES_VALENCE = prior.SPECIES_VALENCE


def kinetics(voltage, law_codes, *, xp=jnp):
    v, codes = prior._broadcast(voltage, law_codes, xp=xp)
    selected = (codes >= 35) & (codes <= 38)
    target, tau = prior.kinetics(xp.where(selected, 0.0, v), xp.where(selected, 0, codes), xp=xp)
    added_target, added_tau = calcium.kinetics(
        xp.where(selected, v, 0.0), xp.where(selected, codes, calcium.PAD_CODE), xp=xp
    )
    mask = xp.expand_dims(selected, -2)
    return xp.where(mask, added_target, target), xp.where(mask, added_tau, tau)


def opening(gates, law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    selected = (codes >= 35) & (codes <= 38)
    original = prior.opening(gates, xp.where(selected, 0, codes), xp=xp)
    added = calcium.opening(gates, xp.where(selected, codes, calcium.PAD_CODE), xp=xp)
    return xp.where(selected, added, original)


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.ndim < 1 or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    return xp.all((codes >= 0) & (codes <= 38))


def controls_valid(law_codes, availability, active, *, xp=jnp):
    codes, present = xp.asarray(law_codes), xp.asarray(active)
    if codes.ndim < 1 or present.shape != codes.shape or present.dtype.kind != "b":
        return xp.asarray(False)
    return (
        valid_codes(codes, xp=xp)
        & prior.controls_valid(
            xp.where((codes >= 35) & (codes <= 38), 0, codes), availability, active, xp=xp
        )
        & xp.all(xp.where(present, True, codes == 0))
    )
