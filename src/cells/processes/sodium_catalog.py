"""All seven pinned BETSE sodium classes as regularized continuous gate laws.

Standalone sodium codes 2 and 18--23; zero is neutral padding only here.
Voltage is [..., population] in V, gates/targets/tau are [..., 2, population].
No temperature scaling, fixed ionic reversal, geometry or gate thermodynamics.
"""

import jax.numpy as jnp

from cells.processes import sodium_channels
from cells.processes.electrochemistry import bernoulli
from cells.processes.voltage_gates import VOLTAGE_DOMAIN_V

SODIUM_LAWS = {
    sodium_channels.LAW_ID: "Nav1p2",
    "betse_nav1p3_m3h_regularized@1": "Nav1p3",
    "betse_navrat2_m3h_regularized@1": "NavRat2",
    "betse_navrat1_m3h_regularized@1": "NavRat1",
    "betse_navrat3_m3h_regularized@1": "NavRat3",
    "betse_naleak_always_open@1": "NaLeak",
    "betse_nav1p6_persistent_m@1": "Nav1p6",
}
LAW_CODES = {law: code for law, code in zip(SODIUM_LAWS, (2, 18, 19, 20, 21, 22, 23), strict=True)}
LAW_PERMEABILITIES = {law: (("Na", 1.0),) for law in SODIUM_LAWS}
GATE_POWERS = {
    law: (0, 0) if name == "NaLeak" else (1, 0) if name == "Nav1p6" else (3, 1)
    for law, name in SODIUM_LAWS.items()
}


def _numeric(value):
    return value.dtype.kind in "fiu"


def _broadcast(voltage, law_codes, *, xp):
    v, codes = xp.asarray(voltage), xp.asarray(law_codes)
    if not v.ndim or not codes.ndim:
        raise ValueError("Sodium voltage and law codes require explicit population axes")
    v, codes = xp.broadcast_arrays(v, codes)
    return v, codes


def _gates(gates, voltage, law_codes, *, xp):
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    g = xp.asarray(gates)
    if g.ndim < 2 or g.shape[-2] != 2:
        raise ValueError("Sodium gates require [..., 2, population] axes")
    shape = xp.broadcast_shapes(g.shape[:-2] + (g.shape[-1],), v.shape)
    return (
        xp.broadcast_to(g, shape[:-1] + (2, shape[-1])),
        xp.broadcast_to(v, shape),
        xp.broadcast_to(codes, shape),
    )


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.dtype.kind not in "iu" or codes.ndim < 1:
        return xp.asarray(False)
    return xp.all((codes == 0) | (codes == 2) | ((codes >= 18) & (codes <= 23)))


def kinetics(voltage, law_codes, *, xp=jnp):
    """Unchecked targets and seconds; only padding receives neutral arguments."""
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    v = xp.where(codes == 0, 0.0, v)
    one = xp.ones_like(v, dtype=xp.result_type(v, 1.0))
    target = xp.stack((xp.zeros_like(one), xp.zeros_like(one)), axis=-2)
    tau = xp.stack((one, one), axis=-2)

    def select(mask, values):
        nonlocal target, tau
        target = xp.where(xp.expand_dims(mask, -2), values[0], target)
        tau = xp.where(xp.expand_dims(mask, -2), values[1], tau)

    # Exact overlap: evaluate the accepted component, without reimplementing it.
    select(codes == 2, sodium_channels.nav1p2_kinetics(v, xp=xp))
    a = 0.182 * 9 * bernoulli(-(v + 0.026) / 0.009, xp=xp)
    b = 0.124 * 9 * bernoulli((v + 0.026) / 0.009, xp=xp)
    select(
        codes == 18,
        (
            xp.stack((a / (a + b), 1 / (1 + xp.exp((v + 0.065) / 0.0081))), axis=-2),
            xp.stack((0.001 / (a + b), 0.001 * (0.40 + 0.265 * xp.exp(-v / 0.00947))), axis=-2),
        ),
    )
    a = 0.091 * 5 * bernoulli(-(v + 0.038) / 0.005, xp=xp)
    b = 0.062 * 5 * bernoulli((v + 0.038) / 0.005, xp=xp)
    h_a, h_b = 0.016 * xp.exp((-0.055 - v) / 0.015), 2.07 / (xp.exp((0.017 - v) / 0.021) + 1)
    select(
        codes == 19,
        (
            xp.stack((a / (a + b), h_a / (h_a + h_b)), axis=-2),
            xp.stack((0.001 / (a + b), 0.001 / (h_a + h_b)), axis=-2),
        ),
    )
    # Rat1/Rat3 are exactly the source's unshifted form of accepted Nav1p2.
    select((codes == 20) | (codes == 21), sodium_channels.nav1p2_kinetics(v + 0.010, xp=xp))
    select(codes == 22, (xp.stack((one, one), axis=-2), xp.stack((one, one), axis=-2)))
    persistent = 1 / (1 + xp.exp(-0.03937 * 4.2 * (1000 * v + 17.0)))
    select(
        codes == 23,
        (xp.stack((persistent, one), axis=-2), xp.stack((0.001 * one, 0.001 * one), axis=-2)),
    )
    return target, tau


def initial_gates(voltage, law_codes, *, xp=jnp):
    """Source initialization, with scalar auxiliary gates broadcast explicitly."""
    return kinetics(voltage, law_codes, xp=xp)[0]


def opening(gates, law_codes, *, xp=jnp):
    g = xp.asarray(gates)
    codes = xp.asarray(law_codes)
    if g.ndim < 2 or g.shape[-2] != 2 or codes.ndim < 1:
        raise ValueError("Sodium opening requires explicit gate and population axes")
    m, h, codes = xp.broadcast_arrays(g[..., 0, :], g[..., 1, :], codes)
    active = (codes == 2) | ((codes >= 18) & (codes <= 23))
    result = xp.where(codes == 22, xp.ones_like(m), xp.where(codes == 23, m, m**3 * h))
    return xp.where(active, result, 0.0)


def rhs(gates, voltage, law_codes, *, xp=jnp):
    """Continuous relaxation; the native backward-Euler clock is separate."""
    gates, voltage, codes = _gates(gates, voltage, law_codes, xp=xp)
    target, tau = kinetics(voltage, codes, xp=xp)
    return xp.where(xp.expand_dims(codes != 0, -2), (target - gates) / tau, 0.0)


def domain_valid(gates, voltage, law_codes, *, xp=jnp):
    """Strict compiled-compatible domain, including physically unused gates."""
    try:
        g, v, codes = _gates(gates, voltage, law_codes, xp=xp)
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)
    if not all(_numeric(value) for value in (g, v)) or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    active = codes != 0
    good_voltage = xp.isfinite(v) & (v >= VOLTAGE_DOMAIN_V[0]) & (v <= VOLTAGE_DOMAIN_V[1])
    good_gates = xp.isfinite(g) & (g >= 0) & (g <= 1)
    valid = valid_codes(codes, xp=xp)
    valid &= xp.all(xp.where(active, good_voltage, v == 0))
    valid &= xp.all(xp.where(xp.expand_dims(active, -2), good_gates, g == 0))
    # Predicate-only neutral arguments never change a physical active trial.
    target, tau = kinetics(xp.where(good_voltage, v, 0.0), codes, xp=xp)
    valid &= xp.all(xp.isfinite(target) & (target >= 0) & (target <= 1))
    valid &= xp.all(xp.isfinite(tau) & (tau > 0))
    derivative = rhs(xp.where(good_gates, g, 0.0), xp.where(good_voltage, v, 0.0), codes, xp=xp)
    return valid & xp.all(xp.isfinite(derivative))
