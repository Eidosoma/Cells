"""Independent scalar Decimal leak metadata and one-second auxiliary clocks."""

from decimal import Decimal, localcontext
from numbers import Real

CLASSES = ("ClLeak", "CatLeak", "CatLeak2")
SPECIES = ("Cl", "Na", "K", "Ca")
ORDERED_PERMEABILITIES = {
    "ClLeak": (("Cl", 1),),
    "CatLeak": (("Na", 1), ("K", 1), ("Ca", 0)),
    "CatLeak2": (("Na", 1), ("K", 1), ("Ca", 1)),
}


def _d(value, name):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(name + " requires a finite real number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite " + name)
    return result


def _gates(gates, name):
    if name not in CLASSES or len(gates) != 2:
        raise ValueError("Require a declared leak and two auxiliary gates")
    values = [_d(g, "gate") for g in gates]
    if any(g < 0 or g > 1 for g in values):
        raise ValueError("Gate outside [0,1]")
    return values


def kinetics(voltage, name):
    if name not in CLASSES or not Decimal("-0.120") <= _d(voltage, "voltage") <= Decimal("0.060"):
        raise ValueError("Invalid class or computational voltage")
    return dict(target=[1.0, 1.0], tau_s=[1.0, 1.0])


def opening(gates, name):
    _gates(gates, name)
    return 1.0


def rhs(gates, voltage, name):
    with localcontext() as context:
        context.prec = 80
        kinetics(voltage, name)
        return [float(1 - g) for g in _gates(gates, name)]


def relaxation(initial, voltage, name, time_s):
    with localcontext() as context:
        context.prec = 80
        kinetics(voltage, name)
        time = _d(time_s, "time")
        if time < 0:
            raise ValueError("Negative time")
        return [float(1 + (g - 1) * (-time).exp()) for g in _gates(initial, name)]


def backward_euler(initial, voltage, name, dt_s):
    with localcontext() as context:
        context.prec = 80
        kinetics(voltage, name)
        dt = _d(dt_s, "step")
        if dt < 0:
            raise ValueError("Negative step")
        return [float((g + dt) / (1 + dt)) for g in _gates(initial, name)]


def permeability_weights(name, availability):
    with localcontext() as context:
        context.prec = 80
        if name not in CLASSES:
            raise ValueError("Unknown class")
        a = _d(availability, "availability")
        if not 0 <= a <= 1:
            raise ValueError("Availability outside [0,1]")
        declared = dict(ORDERED_PERMEABILITIES[name])
        return [float(a * declared.get(species, 0)) for species in SPECIES]


def clamp_clock():
    time, step, times = 0.0, 0.25, [0.0]
    while time < 12.0:
        time = min(12.0, time + step)
        times.append(time)
        step *= 1.2
    return times
