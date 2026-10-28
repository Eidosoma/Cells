"""Expanded shared populations with stable old law codes and explicit ion routes.

Codes 0--17 keep the accepted CaV/HCN/NaV1.2/Kv1/Kir behavior. New sodium,
potassium and leak laws occupy 18--34. Tissue padding uses a separate active
mask: code zero still means Kv1.5, not either standalone catalog's padding.
"""

import jax.numpy as jnp

from cells.processes import cav_channels, leak_channels, potassium_catalog, sodium_catalog

LAW_CODES = (
    cav_channels.LAW_CODES
    | sodium_catalog.LAW_CODES
    | potassium_catalog.LAW_CODES
    | leak_channels.LAW_CODES
)
LAW_PERMEABILITIES = (
    cav_channels.LAW_PERMEABILITIES
    | sodium_catalog.LAW_PERMEABILITIES
    | potassium_catalog.LAW_PERMEABILITIES
    | leak_channels.LAW_PERMEABILITIES
)
SPECIES_VALENCE = cav_channels.SPECIES_VALENCE | {"Cl": -1}


def _broadcast(voltage, law_codes, *, xp):
    v, codes = xp.asarray(voltage), xp.asarray(law_codes)
    if v.ndim < 1 or codes.ndim < 1:
        raise ValueError("Shared channels require explicit population axes")
    if v.shape[-1] != codes.shape[-1]:
        raise ValueError("Shared voltage and law arrays must have the same population count")
    return xp.broadcast_arrays(v, codes)


def kinetics(voltage, law_codes, *, xp=jnp):
    """Unchecked source kinetics; unused catalog branches receive neutral inputs."""
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    old = codes <= 17
    target, tau = cav_channels.kinetics(xp.where(old, v, 0.0), xp.where(old, codes, 0), xp=xp)
    for low, high, neutral, process in (
        (18, 23, 2, sodium_catalog),
        (24, 31, 1, potassium_catalog),
        (32, 34, -1, leak_channels),
    ):
        selected = (codes >= low) & (codes <= high)
        other_target, other_tau = process.kinetics(
            xp.where(selected, v, 0.0), xp.where(selected, codes, neutral), xp=xp
        )
        mask = xp.expand_dims(selected, -2)
        target, tau = xp.where(mask, other_target, target), xp.where(mask, other_tau, tau)
    return target, tau


def opening(gates, law_codes, *, xp=jnp):
    g, codes = xp.asarray(gates), xp.asarray(law_codes)
    if g.ndim < 2 or g.shape[-2] != 2 or codes.ndim < 1 or g.shape[-1] != codes.shape[-1]:
        raise ValueError("Shared opening requires matching gate and population axes")
    m, h, codes = xp.broadcast_arrays(g[..., 0, :], g[..., 1, :], codes)
    g = xp.stack((m, h), axis=-2)
    result = cav_channels.opening(g, xp.where(codes <= 17, codes, 0), xp=xp)
    for low, high, neutral, process in (
        (18, 23, 2, sodium_catalog),
        (24, 31, 1, potassium_catalog),
        (32, 34, -1, leak_channels),
    ):
        selected = (codes >= low) & (codes <= high)
        value = process.opening(g, xp.where(selected, codes, neutral), xp=xp)
        result = xp.where(selected, value, result)
    return result


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.ndim < 1 or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    return xp.all((codes >= 0) & (codes <= 34))


def controls_valid(law_codes, availability, active, *, xp=jnp):
    """Tissue controls preserve population count and keep inactive slots zero."""
    codes, levels, present = map(xp.asarray, (law_codes, availability, active))
    if codes.ndim < 1 or levels.shape != codes.shape or present.shape != codes.shape:
        return xp.asarray(False)
    if levels.dtype.kind not in "fiu" or present.dtype.kind != "b":
        return xp.asarray(False)
    finite = xp.all(xp.isfinite(levels) & (levels >= 0) & (levels <= 1))
    selected = present & (codes >= 32) & (codes <= 34)
    leak_valid = leak_channels.permeability_domain_valid(
        xp.where(selected, codes, -1), xp.where(selected, levels, 0.0), xp=xp
    )
    return (
        finite
        & valid_codes(codes, xp=xp)
        & leak_valid
        & xp.all(xp.where(present, True, (codes == 0) & (levels == 0)))
    )
