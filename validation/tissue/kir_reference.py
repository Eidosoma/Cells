"""Independent scalar Decimal Kir2.1 equations in native millivolt units.

No production or JAX imports. Return SI seconds for the continuous reference.
The squared h factor is part of the channel law, independent of gate kinetics.
"""

from decimal import Decimal, localcontext


def kinetics(voltage):
    with localcontext() as context:
        context.prec = 70
        v = Decimal(str(voltage)) * 1000

        def reciprocal_exp(x):
            return 1 / (1 + x.exp())

        m = reciprocal_exp((v + Decimal("96.48")) / Decimal("23.26"))
        h = reciprocal_exp(-(v + Decimal("168.28")) / Decimal("44.13"))
        tm = Decimal("3.7") - Decimal("3.37") * reciprocal_exp(
            (v + Decimal("32.9")) / Decimal("27.93")
        )
        th = Decimal("0.85") + Decimal("306.3") * reciprocal_exp(
            -(v + Decimal("118.29")) / Decimal("27.23")
        )
        return (m, h), (tm / 1000, th / 1000)


def opening(gates):
    m, h = (Decimal(str(v)) for v in gates)
    return m * h * h
