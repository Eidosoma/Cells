"""Instantaneous legacy cagPotassium equation with an explicit free-Ca input.

The source is a legacy function with no call site found in the pinned tree,
not a current-runtime class or BK/SK fit. Retain its literal numeric-mM scale.
No gating state, calcium consumption, ionic flux or invented relaxation clock.
"""

import jax.numpy as jnp
import numpy as np

from cells.processes.electrochemistry import F, R
from cells.processes.voltage_gates import VOLTAGE_DOMAIN_V

LAW_ID = "betse_cagpotassium_numeric_mM_scale@1"
LAW_CODE = 39
PAD_CODE = -1
LAW_CODES = {LAW_ID: LAW_CODE}
LAW_PERMEABILITIES = {LAW_ID: (("K", 1.0),)}
SENSED_SPECIES = "Ca"
TRANSPORTED_SPECIES = "K"
GATE_STATE_COUNT = 0
TEMPERATURE_DOMAIN_K = (200.0, 400.0)
NATIVE_CALCIUM_SCALE = 1e6


def _numeric(value):
    return value.dtype.kind in "fiu"


def _broadcast(voltage, calcium, temperature, law_codes, availability, *, xp):
    v, c, t, codes = (xp.asarray(value) for value in (voltage, calcium, temperature, law_codes))
    if v.ndim < 1 or codes.ndim < 1:
        raise ValueError("Calcium-activated K voltage/codes require explicit population axes")
    a = xp.where(codes == LAW_CODE, 1.0, 0.0) if availability is None else xp.asarray(availability)
    shape = xp.broadcast_shapes(v.shape, c.shape, t.shape, codes.shape, a.shape)
    if shape[-1] != codes.shape[-1]:
        raise ValueError("Inputs must preserve the declared code-array population count")
    return tuple(xp.broadcast_to(value, shape) for value in (v, c, t, codes, a))


def valid_codes(law_codes, *, xp=jnp):
    codes = xp.asarray(law_codes)
    if codes.ndim < 1 or codes.dtype.kind not in "iu":
        return xp.asarray(False)
    return xp.all((codes == LAW_CODE) | (codes == PAD_CODE))


def opening(voltage, calcium_free_mM, temperature_K, law_codes, *, xp=jnp):
    """Unchecked algebraic P; calcium is current FREE cytosolic amount/volume.

    Stable algebra exactly retains (1+1e6*C/10.22)/(1+1e6*C/.89).
    C=0 has the source's finite basal opening, without a concentration floor.
    """
    v, c, t, codes, _ = _broadcast(voltage, calcium_free_mM, temperature_K, law_codes, None, xp=xp)
    active = codes == LAW_CODE
    v, c, t = xp.where(active, v, 0.0), xp.where(active, c, 0.0), xp.where(active, t, 298.15)
    ratio_limit = 0.89 / 10.22
    numerator_constant = 10.22 / NATIVE_CALCIUM_SCALE
    denominator_constant = 0.89 / NATIVE_CALCIUM_SCALE
    ratio = ratio_limit * ((c + numerator_constant) / (c + denominator_constant))
    log_odds = xp.log(6182.0) + 4 * xp.log(ratio) - 1.64 * F * v / (R * t)
    return xp.where(active, xp.exp(-xp.logaddexp(0.0, log_odds)), 0.0)


def effective_opening(voltage, calcium_free_mM, temperature_K, law_codes, availability, *, xp=jnp):
    """One explicit availability multiplier per K population; no state update."""
    v, c, t, codes, a = _broadcast(
        voltage, calcium_free_mM, temperature_K, law_codes, availability, xp=xp
    )
    return xp.where(codes == LAW_CODE, a * opening(v, c, t, codes, xp=xp), 0.0)


def _domain_valid(voltage, calcium, temperature, law_codes, availability, *, xp):
    raw = [xp.asarray(v) for v in (voltage, calcium, temperature)]
    if availability is not None:
        raw.append(xp.asarray(availability))
    if not all(_numeric(v) for v in raw):
        return xp.asarray(False)
    try:
        v, c, t, codes, a = _broadcast(
            voltage, calcium, temperature, law_codes, availability, xp=xp
        )
    except (ValueError, TypeError, AttributeError, IndexError):
        return xp.asarray(False)
    if codes.dtype.kind not in "iu":
        return xp.asarray(False)
    # Validate declarations before an empty broadcast can erase invalid entries.
    valid = valid_codes(law_codes, xp=xp)
    valid &= xp.all(xp.stack([xp.all(xp.isfinite(value)) for value in raw]))
    valid &= xp.all((raw[0] >= VOLTAGE_DOMAIN_V[0]) & (raw[0] <= VOLTAGE_DOMAIN_V[1]))
    valid &= xp.all(raw[1] >= 0)
    valid &= xp.all((raw[2] >= TEMPERATURE_DOMAIN_K[0]) & (raw[2] <= TEMPERATURE_DOMAIN_K[1]))
    if availability is not None:
        valid &= xp.all((raw[3] >= 0) & (raw[3] <= 1))
    active = codes == LAW_CODE
    valid &= xp.all(xp.where(active, True, (v == 0) & (c == 0) & (t == 298.15) & (a == 0)))
    good_v = xp.isfinite(v) & (v >= VOLTAGE_DOMAIN_V[0]) & (v <= VOLTAGE_DOMAIN_V[1])
    good_c = xp.isfinite(c) & (c >= 0)
    good_t = xp.isfinite(t) & (t >= TEMPERATURE_DOMAIN_K[0]) & (t <= TEMPERATURE_DOMAIN_K[1])
    # Predicate-only neutral arguments never repair the rejected physical trial.
    result = opening(
        xp.where(good_v, v, 0.0),
        xp.where(good_c, c, 0.0),
        xp.where(good_t, t, 298.15),
        codes,
        xp=xp,
    )
    effective = xp.where(active, a * result, 0.0)
    valid &= xp.all(xp.isfinite(result) & (result >= 0) & (result <= 1))
    return valid & xp.all(xp.isfinite(effective) & (effective >= 0) & (effective <= 1))


def domain_valid(voltage, calcium_free_mM, temperature_K, law_codes, availability=None, *, xp=jnp):
    """Strict full instantaneous trial; blocking retains physical-input validity.

    Active free calcium is finite and nonnegative, including the source's zero
    input. Padding requires V=Ca=availability=0,T=298.15K. Temperature bounds
    are computational, not experimental calibration. No artificial gate state.
    """
    if xp is np:
        with np.errstate(all="ignore"):
            return _domain_valid(
                voltage, calcium_free_mM, temperature_K, law_codes, availability, xp=np
            )
    return _domain_valid(voltage, calcium_free_mM, temperature_K, law_codes, availability, xp=xp)
