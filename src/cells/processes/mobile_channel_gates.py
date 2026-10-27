"""Joint Kv1.5 gate-state amounts; mixing must not refactor their correlations.

The four m/h states realize the existing independent binary gate kinetics.
Ideal-mixture dissipation and rate-bias work are a phenomenological accounting
identity, not measured gating heat, ATP use or resolved gating-charge work.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.processes import voltage_gates
from cells.processes.electrochemistry import R

LAW_ID = voltage_gates.LAW_ID
STATE_IDS = ("m0h0", "m0h1", "m1h0", "m1h1")
TRANSITION_IDS = ("m_h0", "m_h1", "h_m0", "h_m1")
SENDERS = (0, 1, 0, 2)
RECEIVERS = (2, 3, 1, 3)
GATES = (0, 0, 1, 1)
MAX_GATE_EXIT_PER_S = float(
    np.sum(1 / voltage_gates.kinetics(np.array([voltage_gates.VOLTAGE_DOMAIN_V[1]]), xp=np)[1])
)


class Rates(NamedTuple):
    amount_rate: object
    transfer: object
    dissipation: object
    bias_work: object
    targets: object
    tau_s: object
    valid: object


def incidence(flow, *, xp=jnp):
    a, b, c, d = (flow[:, i] for i in range(4))
    return xp.stack((-a - c, -b + c, a - d, b + d), axis=1)


def rates(amount, voltage, present, dynamic, temperature, *, xp=jnp):
    """[population, 4, patch] amounts, with named m/h transition histories."""
    v = xp.where(present, voltage, 0.0)
    target, tau = voltage_gates.kinetics(v, xp=xp)
    alpha, beta = target / tau, (1 - target) / tau
    source, dest, gate = (xp.asarray(v) for v in (SENDERS, RECEIVERS, GATES))
    forward = alpha[:, gate] * amount[:, source]
    backward = beta[:, gate] * amount[:, dest]
    flow = xp.where(present[:, None] & dynamic[:, None, None], forward - backward, 0.0)
    safe = xp.where(present[:, None], amount, 1.0)
    bias = xp.log(alpha[:, gate]) - xp.log(beta[:, gate])
    force = bias + xp.log(safe[:, source]) - xp.log(safe[:, dest])
    heat, work = (1e-3 * R * temperature * flow * v for v in (force, bias))
    valid = xp.all(xp.isfinite(amount)) & xp.all(
        xp.where(present[:, None], amount > 0, amount == 0)
    )
    valid &= xp.all(
        xp.where(
            present,
            (v >= voltage_gates.VOLTAGE_DOMAIN_V[0]) & (v <= voltage_gates.VOLTAGE_DOMAIN_V[1]),
            True,
        )
    )
    valid &= temperature == voltage_gates.TEMPERATURE_K
    valid &= xp.all(xp.isfinite(target)) & xp.all((target > 0) & (target < 1))
    valid &= xp.all(xp.isfinite(tau)) & xp.all(tau > 0)
    for value in (flow, heat, work):
        valid &= xp.all(xp.isfinite(value))
    return Rates(incidence(flow, xp=xp), flow, heat, work, target, tau, valid)
