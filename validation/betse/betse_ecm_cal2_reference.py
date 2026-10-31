"""PROPOSAL: separately declared Ca_L2-only ECM computational voltage envelope.

No other calcium class, standalone helper, native equation or production domain
is changed. The interval is numerical extrapolation, not biological calibration.
"""

from decimal import Decimal, localcontext

from validation.channels.calcium_catalog_extra_reference import _d

DOMAIN_ID = "cells.ecm_cal2_reference_voltage_domain@1"
# This is independently declared for Ca_L2. Include the exact binary64 source
# value spelling 0.400 V while retaining the standalone exact lower endpoint.
VOLTAGE_DOMAIN_V = (Decimal("-0.120"), Decimal.from_float(0.400))


def kinetics(voltage, name, *, precision):
    if name != "Ca_L2":
        raise ValueError("Require the separately declared ECM Ca_L2 class")
    if type(precision) is not int or precision not in (100, 160):
        raise ValueError("Require declared ECM Ca_L2 precision100 or160")
    v = _d(voltage, "voltage")
    if not VOLTAGE_DOMAIN_V[0] <= v <= VOLTAGE_DOMAIN_V[1]:
        raise ValueError("Voltage outside declared ECM Ca_L2 computational domain")
    with localcontext() as context:
        context.prec = precision
        mv, ms = 1000 * v, Decimal(".001")
        target, tau = (
            [1 / (1 + ((mv + 30) / -6).exp()), 1 / (1 + ((mv + 80) / Decimal("6.4")).exp())],
            [10 * ms, 59 * ms],
        )
        if not all(x.is_finite() and 0 <= x <= 1 for x in target):
            raise ValueError("Invalid ECM Ca_L2 reference targets")
        if not all(x.is_finite() and x > 0 for x in tau):
            raise ValueError("Invalid ECM Ca_L2 reference time constants")
        return target, tau
