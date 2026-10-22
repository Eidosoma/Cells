"""Independent Decimal HCN rates in the source's millivolt/millisecond units.

No Cells or JAX imports. HCN2/4 shift V by -10 mV; HCN1 does not.
"""

from decimal import Decimal, localcontext


def kinetics(voltage, family):
    with localcontext() as context:
        context.prec = 80
        v = Decimal(str(voltage)) * 1000
        midpoint, slope, tau, shift = {
            1: ("-94", "8.1", "30", "0"),
            2: ("-99", "6.2", "184", "-10"),
            4: ("-100", "9.6", "461", "-10"),
        }[family]
        argument = (v + Decimal(shift) - Decimal(midpoint)) / Decimal(slope)
        return (1 / (1 + argument.exp()), Decimal(1)), (Decimal(tau) / 1000, Decimal("0.001"))


def opening(gates):
    return Decimal(str(gates[0]))
