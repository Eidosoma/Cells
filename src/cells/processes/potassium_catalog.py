"""Remaining pinned potassium gate laws, with literal source Kv3p3 recovery.

Standalone codes1,24--31; -1 is neutral padding. Shared code0 is not redefined.
Voltage [...,population] is in V; gates/targets/tau [...,2,population] use seconds.
No inferred temperature scaling, fixed ionic reversal or gate thermodynamics.
"""

import jax.numpy as jnp

from cells.processes import potassium_channels as accepted

PAD_CODE = -1
VOLTAGE_DOMAIN_V = accepted.VOLTAGE_DOMAIN_V
POTASSIUM_LAWS = {
    accepted.KIR_LAW_ID: "Kir2p1",
    "betse_kv2p1_mh@1": "Kv2p1",
    "betse_kv2p2_mh@1": "Kv2p2",
    "betse_kv3p1_m@1": "Kv3p1",
    "betse_kv3p2_m2@1": "Kv3p2",
    "betse_kv3p3_m2h_source_tau@1": "Kv3p3",
    "betse_kv3p4_mh@1": "Kv3p4",
    "betse_k_fast_mh@1": "K_Fast",
    "betse_kleak_always_open@1": "KLeak",
}
LAW_CODES = {
    law: code for law, code in zip(POTASSIUM_LAWS, (1, 24, 25, 26, 27, 28, 29, 30, 31), strict=True)
}
LAW_PERMEABILITIES = {law: (("K", 1.0),) for law in POTASSIUM_LAWS}
GATE_POWERS = {
    law: (1, 2)
    if name == "Kir2p1"
    else (1, 0)
    if name == "Kv3p1"
    else (2, 0)
    if name == "Kv3p2"
    else (2, 1)
    if name == "Kv3p3"
    else (0, 0)
    if name == "KLeak"
    else (1, 1)
    for law, name in POTASSIUM_LAWS.items()
}


def _numeric(value):
    return value.dtype.kind in "fiu"


def _broadcast(voltage, law_codes, *, xp):
    v, codes = xp.asarray(voltage), xp.asarray(law_codes)
    if v.ndim < 1 or codes.ndim < 1:
        raise ValueError("Potassium voltage/codes require explicit population axes")
    return xp.broadcast_arrays(v, codes)


def _gates(gates, voltage, law_codes, *, xp):
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    g = xp.asarray(gates)
    if g.ndim < 2 or g.shape[-2] != 2:
        raise ValueError("Potassium gates require [...,2,population] axes")
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
    return xp.all((codes == PAD_CODE) | (codes == 1) | ((codes >= 24) & (codes <= 31)))


def kinetics(voltage, law_codes, *, xp=jnp):
    """Unchecked source targets/tau in seconds; preserve long Kv3p3 tau literally."""
    v, codes = _broadcast(voltage, law_codes, xp=xp)
    v = xp.where(codes == PAD_CODE, 0.0, v)
    one = xp.ones_like(v, dtype=xp.result_type(v, 1.0))
    target, tau = xp.stack((0 * one, 0 * one), axis=-2), xp.stack((one, one), axis=-2)

    def sigmoid(midpoint, slope):
        return 1 / (1 + xp.exp((v - midpoint) / slope))

    def select(code, m, h, tm, th):
        nonlocal target, tau
        mask = xp.expand_dims(codes == code, -2)
        target = xp.where(mask, xp.stack((m, h), axis=-2), target)
        tau = xp.where(mask, xp.stack((tm, th), axis=-2), tau)

    kir = accepted.kir2p1_kinetics(v, xp=xp)
    target = xp.where(xp.expand_dims(codes == 1, -2), kir[0], target)
    tau = xp.where(xp.expand_dims(codes == 1, -2), kir[1], tau)
    select(
        24,
        sigmoid(-0.0092, -0.0066),
        sigmoid(-0.019, 0.005),
        0.100 * sigmoid(-0.04656, 0.04414),
        10 * sigmoid(-0.04656, -0.04414),
    )
    select(
        25,
        sigmoid(0.005, -0.012),
        sigmoid(-0.0163, 0.0048),
        0.130 * sigmoid(-0.04656, -0.04414),
        10 * sigmoid(-0.04656, -0.04414),
    )
    select(26, sigmoid(0.0187, -0.0097), one, 0.020 * sigmoid(-0.04656, -0.04414), 0.001 * one)
    select(
        27,
        sigmoid(-0.000373267, -0.008568187),
        one,
        0.003241643 + 0.019106496 * sigmoid(0.019220623, 0.004451533),
        0.001 * one,
    )
    select(
        28,
        sigmoid(0.035, -0.0073),
        0.25 + 0.75 * sigmoid(-0.028293856, 0.029385636),
        0.000676808 + 0.027913114 * sigmoid(0.022414149, 0.009704638),
        0.199786728 + 2.776119438 * xp.exp(-v / 0.007309565),
    )
    select(
        29,
        sigmoid(-0.0034, -0.0084),
        sigmoid(-0.05332, 0.0074),
        0.010 * sigmoid(0.00444, 0.03814),
        20 * sigmoid(-0.04656, -0.04414),
    )
    select(
        30,
        sigmoid(-0.047, -0.029),
        sigmoid(-0.056, 0.010),
        0.00034 + 0.00092 * xp.exp(-(((v + 0.071) / 0.059) ** 2)),
        0.008 + 0.049 * xp.exp(-(((v + 0.073) / 0.023) ** 2)),
    )
    select(31, one, one, one, one)
    return target, tau


def initial_gates(voltage, law_codes, *, xp=jnp):
    return kinetics(voltage, law_codes, xp=xp)[0]


def opening(gates, law_codes, *, xp=jnp):
    gates, codes = xp.asarray(gates), xp.asarray(law_codes)
    if gates.ndim < 2 or gates.shape[-2] != 2 or codes.ndim < 1:
        raise ValueError("Potassium opening requires explicit gate/population axes")
    m, h, codes = xp.broadcast_arrays(gates[..., 0, :], gates[..., 1, :], codes)
    result = xp.where(
        codes == 26,
        m,
        xp.where(
            codes == 27, m**2, xp.where(codes == 28, m**2 * h, xp.where(codes == 31, 1.0, m * h))
        ),
    )
    # Preserve the accepted floating-point evaluation order m*h*h exactly.
    result = xp.where(codes == 1, accepted.opening(xp.stack((m, h), axis=-2), codes, xp=xp), result)
    active = (codes == 1) | ((codes >= 24) & (codes <= 31))
    return xp.where(active, result, 0.0)


def rhs(gates, voltage, law_codes, *, xp=jnp):
    gates, v, codes = _gates(gates, voltage, law_codes, xp=xp)
    target, tau = kinetics(v, codes, xp=xp)
    return xp.where(xp.expand_dims(codes != PAD_CODE, -2), (target - gates) / tau, 0.0)


def domain_valid(gates, voltage, law_codes, *, xp=jnp):
    try:
        g, v, codes = _gates(gates, voltage, law_codes, xp=xp)
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)
    if not all(_numeric(value) for value in (g, v)) or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    active = codes != PAD_CODE
    voltage_ok = xp.isfinite(v) & (v >= VOLTAGE_DOMAIN_V[0]) & (v <= VOLTAGE_DOMAIN_V[1])
    gates_ok = xp.isfinite(g) & (g >= 0) & (g <= 1)
    valid = valid_codes(codes, xp=xp)
    valid &= xp.all(xp.where(active, voltage_ok, v == 0))
    valid &= xp.all(xp.where(xp.expand_dims(active, -2), gates_ok, g == 0))
    # Neutral predicate arguments never repair an active physical trial.
    target, tau = kinetics(xp.where(voltage_ok, v, 0.0), codes, xp=xp)
    valid &= xp.all(xp.isfinite(target) & (target >= 0) & (target <= 1))
    valid &= xp.all(xp.isfinite(tau) & (tau > 0))
    derivative = rhs(xp.where(gates_ok, g, 0.0), xp.where(voltage_ok, v, 0.0), codes, xp=xp)
    return valid & xp.all(xp.isfinite(derivative))
