"""39 dynamic/auxiliary-gate laws plus one instantaneous free-calcium K law."""

import jax.numpy as jnp

from cells.processes import calcium_activated_potassium as calcium_k
from cells.processes import shared_channel_catalog_v2 as prior

LAW_CODES = prior.LAW_CODES | calcium_k.LAW_CODES
LAW_PERMEABILITIES = prior.LAW_PERMEABILITIES | calcium_k.LAW_PERMEABILITIES
SPECIES_VALENCE = prior.SPECIES_VALENCE


def gate_active(law_codes, *, xp=jnp):
    return xp.asarray(law_codes) != calcium_k.LAW_CODE


def kinetics(voltage, law_codes, *, xp=jnp):
    """Zero target/tau denotes absent gates, never a zero-time relaxation law."""
    codes = xp.asarray(law_codes)
    instant = codes == calcium_k.LAW_CODE
    target, tau = prior.kinetics(
        xp.where(instant, 0.0, voltage), xp.where(instant, 0, codes), xp=xp
    )
    mask = xp.expand_dims(instant, -2)
    return xp.where(mask, 0.0, target), xp.where(mask, 0.0, tau)


def opening(gates, law_codes, *, voltage, calcium_free_mM, temperature_K, xp=jnp):
    codes = xp.asarray(law_codes)
    instant = codes == calcium_k.LAW_CODE
    original = prior.opening(gates, xp.where(instant, 0, codes), xp=xp)
    added = calcium_k.opening(
        xp.where(instant, voltage, 0.0),
        xp.where(instant, calcium_free_mM, 0.0),
        xp.where(instant, temperature_K, 298.15),
        xp.where(instant, codes, calcium_k.PAD_CODE),
        xp=xp,
    )
    return xp.where(instant, added, original)


def instantaneous_domain_valid(voltage, calcium_free_mM, temperature_K, codes, control, *, xp):
    instant = codes == calcium_k.LAW_CODE
    return calcium_k.domain_valid(
        xp.where(instant, voltage, 0.0),
        xp.where(instant, calcium_free_mM, 0.0),
        xp.where(instant, temperature_K, 298.15),
        xp.where(instant, codes, calcium_k.PAD_CODE),
        xp.where(instant, control, 0.0),
        xp=xp,
    )


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.ndim < 1 or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    return xp.all((codes >= 0) & (codes <= calcium_k.LAW_CODE))


def controls_valid(law_codes, availability, active, *, xp=jnp):
    codes, present = xp.asarray(law_codes), xp.asarray(active)
    if codes.ndim < 1 or present.shape != codes.shape or present.dtype.kind != "b":
        return xp.asarray(False)
    return (
        valid_codes(codes, xp=xp)
        & prior.controls_valid(
            xp.where(codes == calcium_k.LAW_CODE, 0, codes), availability, active, xp=xp
        )
        & xp.all(xp.where(present, True, codes == 0))
    )
