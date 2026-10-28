"""Pinned Morris–Lecar laws with five kinetic and eight instantaneous openings.

State/V/codes use [...,population]. Only codes40--44 own an m state; all
algebraic and padding slots are exactly zero. tau=0 explicitly means no clock.
"""

import jax.numpy as jnp

PAD_CODE = -1
VOLTAGE_DOMAIN_V = (-0.120, 0.060)
MORRIS_LECAR_LAWS = {
    "betse_kv_ml1_dynamic_m@1": "Kv_ML1",
    "betse_kv2p1_ml_dynamic_m@1": "Kv2p1_ML",
    "betse_kv1p3_ml_dynamic_m@1": "Kv1p3_ML",
    "betse_kv1p5_ml_dynamic_m@1": "Kv1p5_ML",
    "betse_kv1p5s_ml_slow_dynamic_m@1": "Kv1p5S_ML",
    "betse_nav_ml_instantaneous@1": "Nav_ML",
    "betse_cav_l_ml_instantaneous@1": "Cav_L_ML",
    "betse_cav_l_ml2_instantaneous@1": "Cav_L_ML2",
    "betse_cav_n_ml_instantaneous@1": "Cav_N_ML",
    "betse_cav_t_ml_instantaneous@1": "Cav_T_ML",
    "betse_kir_ml_instantaneous@1": "Kir_ML",
    "betse_hcn2_ml_source_sign_instantaneous@1": "HCN2_ML",
    "betse_hcn4_ml_source_sign_instantaneous@1": "HCN4_ML",
}
LAW_CODES = {law: code for law, code in zip(MORRIS_LECAR_LAWS, range(40, 53), strict=True)}
STATE_COUNTS = {law: 1 if code <= 44 else 0 for law, code in LAW_CODES.items()}
LAW_PERMEABILITIES = {
    law: (("K", 1.0), ("Na", 0.2))
    if name.startswith("HCN")
    else (("Na", 1.0),)
    if name == "Nav_ML"
    else (("Ca", 1.0),)
    if name.startswith("Cav")
    else (("K", 1.0),)
    for law, name in MORRIS_LECAR_LAWS.items()
}

# Voltage-domain parameters are separate from the reference's millivolt equations.
_MIDPOINT = (
    0.012,
    0.014,
    -0.014,
    -0.006,
    -0.006,
    -0.017,
    -0.020,
    -0.020,
    -0.001,
    -0.043,
    -0.135,
    -0.099,
    -0.099,
)
_SLOPE = (
    0.017,
    0.030,
    0.020,
    0.015,
    0.015,
    0.018,
    0.024,
    0.012,
    0.018,
    0.024,
    0.037,
    0.0124,
    0.0192,
)
_PHI = (0.066, 0.066, 0.066, 0.066, 0.00132, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)


def _numeric(value):
    return value.dtype.kind in "fiu"


def _broadcast(voltage, law_codes, *, xp):
    v, codes = xp.asarray(voltage), xp.asarray(law_codes)
    if v.ndim < 1 or codes.ndim < 1:
        raise ValueError("Morris–Lecar V/codes require explicit population axes")
    shape = xp.broadcast_shapes(v.shape, codes.shape)
    if shape[-1] != codes.shape[-1]:
        raise ValueError("V must preserve the declared code-array population count")
    return xp.broadcast_to(v, shape), xp.broadcast_to(codes, shape)


def _state(state, voltage, law_codes, *, xp):
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    m = xp.asarray(state)
    if m.ndim < 1:
        raise ValueError("Morris–Lecar state requires an explicit population axis")
    shape = xp.broadcast_shapes(m.shape, v.shape)
    if shape[-1] != codes.shape[-1]:
        raise ValueError("State must preserve the declared population count")
    return tuple(xp.broadcast_to(value, shape) for value in (m, v, codes))


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.ndim < 1 or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    return xp.all((codes == PAD_CODE) | ((codes >= 40) & (codes <= 52)))


def is_dynamic(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    return (codes >= 40) & (codes <= 44)


def kinetics(voltage, law_codes, *, xp=jnp):
    """m_inf and effective tau_s; zero tau marks instantaneous/absent clocks."""
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    active = (codes >= 40) & (codes <= 52)
    index = xp.where(active, codes - 40, 0)
    v = xp.where(active, v, 0.0)
    midpoint, slope, phi = (xp.asarray(table)[index] for table in (_MIDPOINT, _SLOPE, _PHI))
    x = (v - midpoint) / slope
    target = xp.where(codes == 50, 1 / xp.cosh(x), 0.5 * (1 + xp.tanh(x)))
    tau = xp.where(is_dynamic(codes, xp=xp), 1 / (1000 * phi * xp.cosh(x / 2)), 0.0)
    return xp.where(active, target, 0.0), tau


def initial_state(voltage, law_codes, *, xp=jnp):
    target, _ = kinetics(voltage, law_codes, xp=xp)
    return xp.where(is_dynamic(law_codes, xp=xp), target, 0.0)


def opening(state, voltage, law_codes, *, xp=jnp):
    m, v, codes = _state(state, voltage, law_codes, xp=xp)
    target, _ = kinetics(v, codes, xp=xp)
    return xp.where(is_dynamic(codes, xp=xp), m, target)


def rhs(state, voltage, law_codes, *, xp=jnp):
    m, v, codes = _state(state, voltage, law_codes, xp=xp)
    target, tau = kinetics(v, codes, xp=xp)
    dynamic = is_dynamic(codes, xp=xp)
    # This neutral denominator is only for absent clocks, never a kinetic floor.
    return xp.where(dynamic, (target - m) / xp.where(dynamic, tau, 1.0), 0.0)


def domain_valid(state, voltage, law_codes, *, xp=jnp):
    try:
        m, v, codes = _state(state, voltage, law_codes, xp=xp)
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)
    if not all(_numeric(value) for value in (m, v)) or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    raw_m, raw_v = xp.asarray(state), xp.asarray(voltage)
    valid = valid_codes(law_codes, xp=xp)
    valid &= xp.all(xp.isfinite(raw_m) & (raw_m >= 0) & (raw_m <= 1))
    valid &= xp.all(
        xp.isfinite(raw_v) & (raw_v >= VOLTAGE_DOMAIN_V[0]) & (raw_v <= VOLTAGE_DOMAIN_V[1])
    )
    dynamic = is_dynamic(codes, xp=xp)
    valid &= xp.all(xp.where(dynamic, True, m == 0))
    valid &= xp.all(xp.where(codes == PAD_CODE, v == 0, True))
    voltage_ok = xp.isfinite(v) & (v >= VOLTAGE_DOMAIN_V[0]) & (v <= VOLTAGE_DOMAIN_V[1])
    safe_v = xp.where(voltage_ok, v, 0.0)
    target, tau = kinetics(safe_v, codes, xp=xp)
    valid &= xp.all(xp.isfinite(target) & (target >= 0) & (target <= 1))
    valid &= xp.all(xp.isfinite(tau) & xp.where(dynamic, tau > 0, tau == 0))
    safe_m = xp.where(xp.isfinite(m) & (m >= 0) & (m <= 1), m, 0.0)
    return valid & xp.all(xp.isfinite(rhs(safe_m, safe_v, codes, xp=xp)))
