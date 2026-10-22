"""Independent 80-digit Nav1p2 rates in the source's millivolt units.

No Cells/JAX imports. The x/(1-exp(-x/k)) value at x=0 is exactly k.
"""

from decimal import Decimal, localcontext

import numpy as np


def kinetics(voltage):
    with localcontext() as context:
        context.prec = 80
        v = Decimal(str(voltage)) * 1000

        def rate(x, scale):
            return scale if x == 0 else x / (1 - (-x / scale).exp())

        alpha = Decimal("0.182") * rate(v + 25, Decimal(9))
        beta = Decimal("0.124") * rate(-v - 25, Decimal(9))
        recovery = Decimal("0.024") * rate(v + 40, Decimal(5))
        inactivation = Decimal("0.0091") * rate(-v - Decimal("65.000123"), Decimal(5))
        target = (
            alpha / (alpha + beta),
            1 / (1 + ((v + 55) / Decimal("6.2")).exp()),
        )
        return target, (1 / (1000 * (alpha + beta)), 1 / (1000 * (recovery + inactivation)))


def opening(gates):
    m, h = (Decimal(str(v)) for v in gates)
    return m**3 * h


def source_float_parameters(voltage):
    """Diagnostic replay of source arithmetic, separate from the Decimal oracle.

    Keep the source's subtraction order and 1-exp cancellation. This is used
    only to identify finite native roundoff, never as a physical accuracy target.
    """
    v = np.asarray(voltage) * 1000
    a, b = (v - 10) - -35, -(v - 10) - 35
    c, d = (v - 10) - -50, -(v - 10) - 75.000123
    activation = 0.182 * a / (1 - np.exp(-a / 9))
    deactivation = 0.124 * b / (1 - np.exp(-b / 9))
    recovery = 0.024 * c / (1 - np.exp(-c / 5))
    inactivation = 0.0091 * d / (1 - np.exp(-d / 5))
    return (
        np.stack(
            (
                activation / (activation + deactivation),
                1 / (1 + np.exp((v - -65 - 10) / 6.2)),
            )
        ),
        np.stack((1 / (activation + deactivation), 1 / (recovery + inactivation))) / 1000,
    )
