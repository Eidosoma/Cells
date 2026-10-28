"""Four remaining pinned voltage-only calcium classes, with Cav_G's limit.

Standalone codes35--38 and padding -1. V is [...,population] in volts;
gates/targets/tau are [...,2,population], with tau in seconds. No inferred
temperature or ligand scaling, ionic reversal or calcium-dependent gate.
"""

import jax.numpy as jnp

from cells.processes.electrochemistry import bernoulli
from cells.processes.voltage_gates import VOLTAGE_DOMAIN_V

PAD_CODE = -1
CALCIUM_EXTRA_LAWS = {
    "betse_ca_l2_m2h@1": "Ca_L2",
    "betse_ca_l3_shift15_m2h@1": "Ca_L3",
    "betse_cav_g_m2h_regularized@1": "Cav_G",
    "betse_caleak_always_open@1": "CaLeak",
}
LAW_CODES = {law: code for law, code in zip(CALCIUM_EXTRA_LAWS, range(35, 39), strict=True)}
LAW_PERMEABILITIES = {law: (("Ca", 1.0),) for law in CALCIUM_EXTRA_LAWS}
GATE_POWERS = {
    law: (0, 0) if name == "CaLeak" else (2, 1) for law, name in CALCIUM_EXTRA_LAWS.items()
}


def _numeric(value):
    return value.dtype.kind in "fiu"


def _broadcast(voltage, law_codes, *, xp):
    v, codes = xp.asarray(voltage), xp.asarray(law_codes)
    if v.ndim < 1 or codes.ndim < 1:
        raise ValueError("Calcium-extra voltage/codes require explicit population axes")
    return xp.broadcast_arrays(v, codes)


def _gates(gates, voltage, law_codes, *, xp):
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    g = xp.asarray(gates)
    if g.ndim < 2 or g.shape[-2] != 2:
        raise ValueError("Calcium-extra gates require [...,2,population] axes")
    shape = xp.broadcast_shapes(g.shape[:-2] + (g.shape[-1],), v.shape)
    return (
        xp.broadcast_to(g, shape[:-1] + (2, shape[-1])),
        xp.broadcast_to(v, shape),
        xp.broadcast_to(codes, shape),
    )


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.ndim < 1 or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    return xp.all((codes == PAD_CODE) | ((codes >= 35) & (codes <= 38)))


def kinetics(voltage, law_codes, *, xp=jnp):
    """Unchecked targets/tau; Cav_G uses its analytic -27-mV rate limit."""
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    v = xp.where(codes == PAD_CODE, 0.0, v)
    one = xp.ones_like(v, dtype=xp.result_type(v, 1.0))
    target = xp.stack((0 * one, 0 * one), axis=-2)
    tau = xp.stack((one, one), axis=-2)

    def select(code, m, h, tm, th):
        nonlocal target, tau
        mask = xp.expand_dims(codes == code, -2)
        target = xp.where(mask, xp.stack((m, h), axis=-2), target)
        tau = xp.where(mask, xp.stack((tm, th), axis=-2), tau)

    for code, shift in ((35, 0.0), (36, 0.015)):
        adjusted = v - shift
        m = 1 / (1 + xp.exp((adjusted + 0.030) / -0.006))
        h = 1 / (1 + xp.exp((adjusted + 0.080) / 0.0064))
        select(code, m, h, 0.010 * one, 0.059 * one)
    # alpha_m = .055 * 3.8 * x/expm1(x), x=(-27-V_mV)/3.8.
    # The limit .209/ms preserves the actual equation, without a V offset.
    ma = 0.209 * bernoulli(-(v + 0.027) / 0.0038, xp=xp)
    mb = 0.94 * xp.exp((-0.075 - v) / 0.017)
    ha = 0.000457 * xp.exp((-0.013 - v) / 0.050)
    hb = 0.0065 / (1 + xp.exp((-v - 0.015) / 0.028))
    select(37, ma / (ma + mb), ha / (ha + hb), 0.001 / (ma + mb), 0.001 / (ha + hb))
    select(38, one, one, one, one)
    return target, tau


def initial_gates(voltage, law_codes, *, xp=jnp):
    return kinetics(voltage, law_codes, xp=xp)[0]


def opening(gates, law_codes, *, xp=jnp):
    g, codes = xp.asarray(gates), xp.asarray(law_codes)
    if g.ndim < 2 or g.shape[-2] != 2 or codes.ndim < 1:
        raise ValueError("Calcium-extra opening requires explicit gate/population axes")
    m, h, codes = xp.broadcast_arrays(g[..., 0, :], g[..., 1, :], codes)
    return xp.where(codes == 38, 1.0, xp.where((codes >= 35) & (codes <= 37), m**2 * h, 0.0))


def rhs(gates, voltage, law_codes, *, xp=jnp):
    g, v, codes = _gates(gates, voltage, law_codes, xp=xp)
    target, tau = kinetics(v, codes, xp=xp)
    return xp.where(xp.expand_dims(codes != PAD_CODE, -2), (target - g) / tau, 0.0)


def domain_valid(gates, voltage, law_codes, *, xp=jnp):
    """Strict computational V/gate domain, including unused leak auxiliaries."""
    try:
        g, v, codes = _gates(gates, voltage, law_codes, xp=xp)
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)
    if not all(_numeric(value) for value in (g, v)) or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    active = codes != PAD_CODE
    voltage_ok = xp.isfinite(v) & (v >= VOLTAGE_DOMAIN_V[0]) & (v <= VOLTAGE_DOMAIN_V[1])
    gates_ok = xp.isfinite(g) & (g >= 0) & (g <= 1)
    # Check declarations before empty broadcasting can discard bad entries.
    raw_g, raw_v = xp.asarray(gates), xp.asarray(voltage)
    valid = valid_codes(law_codes, xp=xp)
    valid &= xp.all(xp.isfinite(raw_g) & (raw_g >= 0) & (raw_g <= 1))
    valid &= xp.all(
        xp.isfinite(raw_v) & (raw_v >= VOLTAGE_DOMAIN_V[0]) & (raw_v <= VOLTAGE_DOMAIN_V[1])
    )
    valid &= xp.all(xp.where(active, voltage_ok, v == 0))
    valid &= xp.all(xp.where(xp.expand_dims(active, -2), gates_ok, g == 0))
    # Neutral predicate arguments do not repair active physical inputs.
    safe_v, safe_g = xp.where(voltage_ok, v, 0.0), xp.where(gates_ok, g, 0.0)
    target, tau = kinetics(safe_v, codes, xp=xp)
    valid &= xp.all(xp.isfinite(target) & (target >= 0) & (target <= 1))
    valid &= xp.all(xp.isfinite(tau) & (tau > 0))
    return valid & xp.all(xp.isfinite(rhs(safe_g, safe_v, codes, xp=xp)))
