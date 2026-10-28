"""56-law catalog; previous 53 laws retain their codes and state contracts."""

import jax.numpy as jnp

from cells.processes import hcn_extra_channels as hcn
from cells.processes import morris_lecar_catalog as prior

LAW_CODES = prior.LAW_CODES | hcn.LAW_CODES
LAW_PERMEABILITIES = prior.LAW_PERMEABILITIES | hcn.LAW_PERMEABILITIES
SPECIES_VALENCE = prior.SPECIES_VALENCE
STATE_COUNTS = prior.STATE_COUNTS | hcn.STATE_COUNTS


def selected(codes, *, xp):
    return (xp.asarray(codes) >= 53) & (xp.asarray(codes) <= 55)


def gate_active(law_codes, *, xp=jnp):
    use = selected(law_codes, xp=xp)
    old = prior.gate_active(xp.where(use, 0, law_codes), xp=xp)
    return xp.where(xp.expand_dims(use, -2), hcn.gate_active(law_codes, xp=xp), old)


def kinetics(voltage, law_codes, *, xp=jnp):
    use = selected(law_codes, xp=xp)
    old = prior.kinetics(xp.where(use, 0.0, voltage), xp.where(use, 0, law_codes), xp=xp)
    added = hcn.kinetics(xp.where(use, voltage, 0.0), xp.where(use, law_codes, 53), xp=xp)
    return tuple(xp.where(xp.expand_dims(use, -2), b, a) for a, b in zip(old, added, strict=True))


def opening(gates, law_codes, *, voltage, calcium_free_mM, temperature_K, xp=jnp):
    use = selected(law_codes, xp=xp)
    old = prior.opening(
        gates,
        xp.where(use, 0, law_codes),
        voltage=voltage,
        calcium_free_mM=calcium_free_mM,
        temperature_K=temperature_K,
        xp=xp,
    )
    return xp.where(use, hcn.opening(gates, law_codes, xp=xp), old)


def hybrid_domain_valid(gates, voltage, calcium_free_mM, temperature_K, codes, control, *, xp):
    use = selected(codes, xp=xp)
    # Full gate, voltage, availability and absent-state domains are enforced by
    # the tissue layer. Preserve the older Ca/ML special domains here.
    return prior.hybrid_domain_valid(
        gates,
        voltage,
        calcium_free_mM,
        temperature_K,
        xp.where(use, 0, codes),
        control,
        xp=xp,
    )


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.ndim < 1 or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    return xp.all((codes >= 0) & (codes <= 55))


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
