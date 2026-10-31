"""PROPOSAL: bounded ECM-only extension of the six pinned NaV reference laws.

This computational envelope is not a biological voltage range. The standalone
sodium oracle, literal native classes and production code remain unchanged.
Equations and elementary Decimal helpers are the existing independent oracle's
equations; only this explicitly named caller has a different voltage admission.
"""

from decimal import Decimal, localcontext

from validation.channels.sodium_catalog_reference import _d, _quotient, _sigmoid

DOMAIN_ID = "cells.ecm_sodium_reference_voltage_domain@1"
CLASSES = ("Nav1p2", "Nav1p3", "NavRat2", "NavRat1", "NavRat3", "Nav1p6")
# Preserve the old exact decimal lower bound. The prospective upper endpoint
# includes the exact source binary64 value spelling 0.400 V; the ECM caller
# passes Decimal.from_float values, so using Decimal("0.400") would reject it.
VOLTAGE_DOMAIN_V = (Decimal("-0.120"), Decimal.from_float(0.400))


def _kinetics(voltage, name):
    if name not in CLASSES:
        raise ValueError("Require a declared voltage-dependent ECM sodium class")
    v = _d(voltage, "voltage")
    if not VOLTAGE_DOMAIN_V[0] <= v <= VOLTAGE_DOMAIN_V[1]:
        raise ValueError("Voltage outside declared ECM sodium computational domain")
    mv, ms = 1000 * v, Decimal("0.001")
    if name == "Nav1p6":
        return [_sigmoid(-Decimal("0.03937") * Decimal("4.2") * (mv + 17)), Decimal(1)], [ms, ms]
    if name == "NavRat2":
        a = Decimal("0.091") * _quotient(mv + 38, Decimal(5))
        b = Decimal("0.062") * _quotient(-mv - 38, Decimal(5))
        ha = Decimal("0.016") * ((-55 - mv) / 15).exp()
        hb = Decimal("2.07") / (((17 - mv) / 21).exp() + 1)
        return [a / (a + b), ha / (ha + hb)], [ms / (a + b), ms / (ha + hb)]
    if name == "Nav1p3":
        a = Decimal("0.182") * _quotient(mv + 26, Decimal(9))
        b = Decimal("0.124") * _quotient(-mv - 26, Decimal(9))
        return [a / (a + b), _sigmoid((mv + 65) / Decimal("8.1"))], [
            ms / (a + b),
            ms * (Decimal("0.40") + Decimal("0.265") * (-mv / Decimal("9.47")).exp()),
        ]
    shifted = mv - 10 if name == "Nav1p2" else mv
    a = Decimal("0.182") * _quotient(shifted + 35, Decimal(9))
    b = Decimal("0.124") * _quotient(-shifted - 35, Decimal(9))
    ha = Decimal("0.024") * _quotient(shifted + 50, Decimal(5))
    hb = Decimal("0.0091") * _quotient(-shifted - Decimal("75.000123"), Decimal(5))
    return [a / (a + b), _sigmoid((shifted + 65) / Decimal("6.2"))], [ms / (a + b), ms / (ha + hb)]


def kinetics(voltage, name, *, precision):
    """Decimal targets and time constants in seconds; no clipping or fallback."""
    if type(precision) is not int or precision not in (100, 160):
        raise ValueError("Require declared ECM sodium precision100 or160")
    with localcontext() as context:
        context.prec = precision
        target, tau = _kinetics(voltage, name)
        if not all(x.is_finite() and 0 <= x <= 1 for x in target):
            raise ValueError("Invalid ECM sodium reference targets")
        if not all(x.is_finite() and x > 0 for x in tau):
            raise ValueError("Invalid ECM sodium reference time constants")
        return target, tau
