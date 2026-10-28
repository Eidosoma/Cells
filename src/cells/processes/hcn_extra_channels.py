"""Pinned BETSE HCN leak and fixed cAMP-shift variants, in volts and seconds.

HCN4_cAMP initializes at a -20 mV source shift and updates at -24 mV.
The explicit initial_gates helper preserves that distinction. These are fixed
source variants, not a model of cAMP concentration or binding. HCNLeak has no
physical gate state; its native unused m/h bookkeeping does not affect opening.
"""

import jax.numpy as jnp

LAW_CODES = {
    "betse_hcn_leak_open@1": 53,
    "betse_hcn2_camp_m@1": 54,
    "betse_hcn4_camp_m@1": 55,
}
LAW_PERMEABILITIES = {
    law: (("Na", 0.33 if code == 53 else 0.2), ("K", 1.0), ("Ca", 0.05))
    for law, code in LAW_CODES.items()
}
STATE_COUNTS = {law: 0 if code == 53 else 2 for law, code in LAW_CODES.items()}


def gate_active(law_codes, *, xp=jnp):
    dynamic = (xp.asarray(law_codes) == 54) | (xp.asarray(law_codes) == 55)
    return xp.stack((dynamic, dynamic), axis=-2 if dynamic.ndim else 0)


def initial_gates(voltage, law_codes, *, xp=jnp):
    """Source initialization, with absent leak gates represented by exact zeros."""
    v, codes = xp.broadcast_arrays(xp.asarray(voltage), xp.asarray(law_codes))
    midpoint = xp.where(codes == 54, -0.079, -0.080)
    slope = xp.where(codes == 54, 0.0062, 0.0096)
    activation = 1 / (1 + xp.exp((v - midpoint) / slope))
    axis = -2 if v.ndim else 0
    return xp.where(gate_active(codes, xp=xp), xp.stack((activation, xp.ones_like(v)), axis), 0.0)


def kinetics(voltage, law_codes, *, xp=jnp):
    v, codes = xp.broadcast_arrays(xp.asarray(voltage), xp.asarray(law_codes))
    midpoint = xp.where(codes == 54, -0.079, -0.076)
    slope = xp.where(codes == 54, 0.0062, 0.0096)
    activation = 1 / (1 + xp.exp((v - midpoint) / slope))
    axis = -2 if v.ndim else 0
    target = xp.stack((activation, xp.ones_like(v)), axis)
    seconds = xp.where(codes == 54, 0.184, 0.461)
    tau = xp.stack((seconds, xp.full_like(v, 0.001)), axis)
    active = gate_active(codes, xp=xp)
    return xp.where(active, target, 0.0), xp.where(active, tau, 0.0)


def opening(gates, law_codes, *, xp=jnp):
    g = xp.asarray(gates)
    return xp.where(xp.asarray(law_codes) == 53, 1.0, xp.take(g, 0, axis=-2 if g.ndim > 1 else 0))
