"""Pinned Cl/mixed-cation always-open populations and explicit route weights.

Codes32--34, standalone padding -1. Gates remain strict auxiliary state with
one-second relaxation. Availability controls every route of a population once;
flux, electrochemical reversal and membrane ownership belong to the model.
"""

import jax.numpy as jnp

PAD_CODE = -1
VOLTAGE_DOMAIN_V = (-0.120, 0.060)
SPECIES = ("Cl", "Na", "K", "Ca")
SPECIES_VALENCE = {"Cl": -1, "Na": 1, "K": 1, "Ca": 2}
LEAK_LAWS = {
    "betse_clleak_always_open@1": "ClLeak",
    "betse_catleak_na_k@1": "CatLeak",
    "betse_catleak2_na_k_ca@1": "CatLeak2",
}
LAW_CODES = {law: code for law, code in zip(LEAK_LAWS, (32, 33, 34), strict=True)}
LAW_PERMEABILITIES = {
    "betse_clleak_always_open@1": (("Cl", 1.0),),
    "betse_catleak_na_k@1": (("Na", 1.0), ("K", 1.0), ("Ca", 0.0)),
    "betse_catleak2_na_k_ca@1": (("Na", 1.0), ("K", 1.0), ("Ca", 1.0)),
}
GATE_POWERS = {law: (0, 0) for law in LEAK_LAWS}


def _numeric(value):
    return value.dtype.kind in "fiu"


def _broadcast(voltage, law_codes, *, xp):
    v, codes = xp.asarray(voltage), xp.asarray(law_codes)
    if v.ndim < 1 or codes.ndim < 1:
        raise ValueError("Leak voltage/codes require explicit population axes")
    return xp.broadcast_arrays(v, codes)


def _gates(gates, voltage, law_codes, *, xp):
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    g = xp.asarray(gates)
    if g.ndim < 2 or g.shape[-2] != 2:
        raise ValueError("Leak gates require [...,2,population] axes")
    shape = xp.broadcast_shapes(g.shape[:-2] + (g.shape[-1],), v.shape)
    return (
        xp.broadcast_to(g, shape[:-1] + (2, shape[-1])),
        xp.broadcast_to(v, shape),
        xp.broadcast_to(codes, shape),
    )


def _active(codes):
    return (codes >= 32) & (codes <= 34)


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.ndim < 1 or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    return xp.all((codes == PAD_CODE) | _active(codes))


def kinetics(voltage, law_codes, *, xp=jnp):
    """Constant source targets and seconds, without voltage-dependent gating."""
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    one = xp.ones_like(v, dtype=xp.result_type(v, 1.0))
    target = xp.where(_active(codes), one, 0.0)
    return xp.stack((target, target), axis=-2), xp.stack((one, one), axis=-2)


def initial_gates(voltage, law_codes, *, xp=jnp):
    return kinetics(voltage, law_codes, xp=xp)[0]


def opening(gates, law_codes, *, xp=jnp):
    g, codes = xp.asarray(gates), xp.asarray(law_codes)
    if g.ndim < 2 or g.shape[-2] != 2 or codes.ndim < 1:
        raise ValueError("Leak opening requires gate/population axes")
    m, codes = xp.broadcast_arrays(g[..., 0, :], codes)
    return xp.where(_active(codes), xp.ones_like(m, dtype=xp.result_type(m, 1.0)), 0.0)


def rhs(gates, voltage, law_codes, *, xp=jnp):
    g, v, codes = _gates(gates, voltage, law_codes, xp=xp)
    target, tau = kinetics(v, codes, xp=xp)
    return xp.where(xp.expand_dims(_active(codes), -2), (target - g) / tau, 0.0)


def permeability_weights(law_codes, availability, *, xp=jnp):
    """Canonical [...,Cl/Na/K/Ca,population] weights; one control per population.

    Requires permeability_domain_valid, as an unchecked pure array calculation.
    This is dimensionless metadata/control composition, not an ionic flux law.
    The explicit zero Ca coefficient of CatLeak is preserved for every control.
    """
    codes, a = xp.asarray(law_codes), xp.asarray(availability)
    if codes.ndim < 1:
        raise ValueError("Leak permeability requires a population axis")
    population_count = codes.shape[-1]
    codes, a = xp.broadcast_arrays(codes, a)
    if codes.shape[-1] != population_count:
        raise ValueError("Leak controls cannot create additional population slots")
    cation = (codes == 33) | (codes == 34)
    unit = xp.stack((codes == 32, cation, cation, codes == 34), axis=-2)
    return unit.astype(xp.result_type(a, 1.0)) * a[..., None, :]


def permeability_domain_valid(law_codes, availability, *, xp=jnp):
    """Strict control predicate, including empty populations and zero padding."""
    try:
        codes, a = xp.asarray(law_codes), xp.asarray(availability)
        if codes.ndim < 1 or codes.dtype.kind not in "iu" or not _numeric(a):
            return xp.asarray(False)
        raw_ok = xp.all(xp.isfinite(a) & (a >= 0) & (a <= 1))
        population_count = codes.shape[-1]
        codes, a = xp.broadcast_arrays(codes, a)
        if codes.shape[-1] != population_count:
            return xp.asarray(False)
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)
    return raw_ok & valid_codes(codes, xp=xp) & xp.all(xp.where(codes == PAD_CODE, a == 0, True))


def domain_valid(gates, voltage, law_codes, availability=None, *, xp=jnp):
    """Strict auxiliary state/control domain, even when conductance is blocked."""
    try:
        g, v, codes = _gates(gates, voltage, law_codes, xp=xp)
        a = (
            xp.where(codes == PAD_CODE, 0.0, 1.0)
            if availability is None
            else xp.asarray(availability)
        )
        control_valid = permeability_domain_valid(codes, a, xp=xp)
        shape = xp.broadcast_shapes(v.shape, a.shape)
        g = xp.broadcast_to(g, shape[:-1] + (2, shape[-1]))
        v, codes, a = (xp.broadcast_to(x, shape) for x in (v, codes, a))
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)
    if codes.dtype.kind not in "iu" or not all(_numeric(x) for x in (g, v, a)):
        return xp.asarray(False)
    active = codes != PAD_CODE
    voltage_ok = xp.isfinite(v) & (v >= VOLTAGE_DOMAIN_V[0]) & (v <= VOLTAGE_DOMAIN_V[1])
    gates_ok = xp.isfinite(g) & (g >= 0) & (g <= 1)
    valid = valid_codes(codes, xp=xp)
    valid &= xp.all(xp.where(active, voltage_ok, v == 0))
    valid &= xp.all(xp.where(xp.expand_dims(active, -2), gates_ok, g == 0))
    return valid & control_valid
