"""Independent high-precision rate evaluation and analytic clamped solutions."""

from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp


def rates(voltage, threshold):
    voltage, threshold = np.broadcast_arrays(voltage, threshold)
    opening, closing = [], []
    with localcontext() as context:
        context.prec = 65
        for v, h in zip(voltage.flat, threshold.flat, strict=True):
            offset = (abs(Decimal(str(float(v)))) - Decimal(str(float(h)))) * 1000
            a = Decimal("0.0013") * (-Decimal("0.077") * offset).exp()
            b = Decimal("0.0013") * (Decimal("0.14") * offset).exp()
            opening.append(float(1000 * a))
            closing.append(float(1000 * b / (1 + 50 * b)))
    return np.asarray(opening).reshape(voltage.shape), np.asarray(closing).reshape(voltage.shape)


def solution(initial, voltage, threshold, minimum, times, *, clock=1):
    a, b = rates(voltage, threshold)
    target = (a + b * minimum) / (a + b)
    return target + (initial - target) * np.exp(-clock * np.asarray(times)[..., None] * (a + b))


def ode(initial, voltage, threshold, minimum, duration):
    a, b = rates(voltage, threshold)
    # DOP853 controls a weighted aggregate step error, not the maximum error
    # of every route's dense output. Resolve the fastest relaxation even after
    # that route approaches equilibrium and the adaptive controller enlarges dt.
    max_step = min(duration / 20, 0.125 / np.max(a + b))
    answer = solve_ivp(
        lambda t, y: a * (1 - y) - b * (y - minimum),
        (0, duration),
        initial,
        method="DOP853",
        rtol=2e-12,
        atol=2e-14,
        max_step=max_step,
        dense_output=True,
    )
    if not answer.success:
        raise ValueError(answer.message)
    return answer
