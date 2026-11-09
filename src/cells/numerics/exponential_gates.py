"""Exponential update of relaxation gates over a step whose voltage varies.

A gate g obeys dg/dt = (g_inf(V) - g) / tau(V) with V(t) supplied by the caller.
Over [t, t + h], given g(t) and the targets and time constants at both ends of
the interval, the update is the exact solution of the same equation with

* the rate 1/tau frozen at the mean of the two end rates, and
* the steady state varying linearly in time from g_inf(t) to g_inf(t + h):

    g(t + h) = g + (g_a - g) (1 - e^-z) + (g_b - g_a) (1 - (1 - e^-z) / z),
    z = h (1/tau_a + 1/tau_b) / 2.

The weights of g, g_a and g_b are e^-z, (1 - e^-z)/z - e^-z and
1 - (1 - e^-z)/z, all non-negative with unit sum, so the result lies between
the start gate and the two targets: gates stay in [0, 1] for any h, without
clipping. For smooth V the local error is O(h^3) (second order), provided the
end voltage has local error O(h^2). As h/tau grows the update tends to
g_b - (g_b - g_a)/z, the quasi-steady value with its first-order lag, instead
of oscillating as the SDIRK stages of the IMEX tableaux would (their stability
function is negative for h/tau > 1/(1 - 2 gamma), about 2.4). Rush and Larsen
(1978, IEEE Trans. Biomed. Eng. 25:389) introduced exponential gate updates with
frozen coefficients; the linear steady state is the exponential-integrator
treatment of a linearly varying forcing (Hochbruck and Ostermann 2010, Acta
Numerica 19:209).
"""

import jax.numpy as jnp

LAW_ID = "exponential_mean_rate_linear_target_gates@1"
# Below this z the weight 1 - (1 - e^-z)/z uses its four-term series (relative
# truncation z^4/360, 3e-15 at the switch); above it the closed form's relative
# rounding, about 4e-16/z, is below 5e-13.
SERIES_LIMIT = 1e-3


def lag_weight(z, *, xp=jnp):
    """1 - (1 - e^-z)/z for z >= 0, accurate near zero."""
    small = z < SERIES_LIMIT
    safe = xp.where(small, 1.0, z)
    series = z * (0.5 - z * (1 / 6 - z * (1 / 24 - z / 120)))
    return xp.where(small, series, (xp.expm1(-safe) + safe) / safe)


def advance(gate, target_start, tau_start, target_end, tau_end, dt, *, xp=jnp):
    """Gate after dt from the start gate and the end-point kinetics (seconds)."""
    z = 0.5 * dt * (1 / tau_start + 1 / tau_end)
    return (
        gate
        + (target_start - gate) * -xp.expm1(-z)
        + (target_end - target_start) * lag_weight(z, xp=xp)
    )
