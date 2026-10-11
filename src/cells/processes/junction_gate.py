"""Continuous physical-time junction conductance from pinned BETSE rate equations.

The finite_extracellular@3 composition evaluates the rates at common solver
stages. State g is relative intrinsic conductance in [minimum, 1]. Availability
multiplies conductance without
changing g. Native per-ion updates, stored-state blocking and class initialization
belong to the separate validation compatibility adapter, not this physical law.
No temperature scaling, connexin catalog or biological fit is implied.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

LAW_ID = "betse_rate_junction_relaxation@1"
MAX_ABS_VOLTAGE_V = 0.120


class Parameters(NamedTuple):
    """Numeric pytree with leaves broadcast over [..., edge_slot]."""

    threshold_voltage_V: Any
    minimum_open_fraction: Any


class Rates(NamedTuple):
    alpha_per_s: Any
    beta_per_s: Any
    target: Any
    relaxation_per_s: Any


def kinetics(voltage, parameters, *, xp=jnp):
    """Volts/seconds, equivalent to BETSE's mV/ms rates on the declared domain."""
    shift = xp.abs(voltage) - parameters.threshold_voltage_V
    alpha = 1.3 * xp.exp(-77.0 * shift)
    # 1000*b/(1+50*b), b=.0013*exp(140*shift). Stable saturated
    # closing rate avoids creating a huge intermediate exponential.
    log_beta = xp.log(0.065) + 140.0 * shift
    beta = 20.0 * xp.exp(-xp.logaddexp(0.0, -log_beta))
    relaxation = alpha + beta
    target = (alpha + beta * parameters.minimum_open_fraction) / relaxation
    return Rates(alpha, beta, target, relaxation)


def rhs(gate, voltage, parameters, *, xp=jnp):
    """One physical-time derivative; independent of species count/availability."""
    rate = kinetics(voltage, parameters, xp=xp)
    return rate.alpha_per_s * (1 - gate) - rate.beta_per_s * (
        gate - parameters.minimum_open_fraction
    )


def advance_clamped(gate, voltage, parameters, dt_s, *, xp=jnp):
    """Exact constant-voltage interval, not a solver for freely varying voltage.

    The composing solver must split voltage changes and reject invalid inputs.
    Use rhs at common solver stages for free-voltage coupling. No clipping or
    hidden equilibrium preparation occurs here.
    """
    rate = kinetics(voltage, parameters, xp=xp)
    return gate + (rate.target - gate) * (-xp.expm1(-rate.relaxation_per_s * dt_s))


def open_fraction(gate, availability):
    return gate * availability


def domain_valid(gate, voltage, parameters, availability, dt_s=0.0, *, xp=jnp):
    """Per-route predicate; even blocked routes retain their physical domain."""
    threshold, minimum = parameters
    return (
        xp.isfinite(threshold)
        & (threshold >= 0)
        & (threshold <= MAX_ABS_VOLTAGE_V)
        & xp.isfinite(minimum)
        & (minimum >= 0)
        & (minimum <= 1)
        & xp.isfinite(voltage)
        & (xp.abs(voltage) <= MAX_ABS_VOLTAGE_V)
        & xp.isfinite(gate)
        & (gate >= minimum)
        & (gate <= 1)
        & xp.isfinite(availability)
        & (availability >= 0)
        & (availability <= 1)
        & xp.isfinite(dt_s)
        & (dt_s >= 0)
    )
