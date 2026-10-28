"""Independent scalar/80-digit equations for the four extra calcium classes.

Only standard-library imports. Millivolts/native time units are expressed
separately from the production volts/seconds equations and Bernoulli helper.
"""

from decimal import Decimal, localcontext
from numbers import Real

CLASSES = ("Ca_L2", "Ca_L3", "Cav_G", "CaLeak")
POWERS = {name: (0, 0) if name == "CaLeak" else (2, 1) for name in CLASSES}
TRANSITIONS_V = {
    "Ca_L2": (-0.030, -0.080),
    "Ca_L3": (-0.015, -0.065),
    "Cav_G": (-0.027, -0.075, -0.013, -0.015),
    "CaLeak": (),
}


def _d(value, name):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(name + " requires a real number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite " + name)
    return result


def _kinetics(voltage, name):
    if name not in CLASSES:
        raise ValueError("Unknown calcium-extra class")
    v = _d(voltage, "voltage")
    if not Decimal("-.120") <= v <= Decimal(".060"):
        raise ValueError("Voltage outside computational domain")
    mv, ms = 1000 * v, Decimal(".001")
    if name == "CaLeak":
        return [Decimal(1), Decimal(1)], [Decimal(1), Decimal(1)]
    if name in ("Ca_L2", "Ca_L3"):
        if name == "Ca_L3":
            mv -= 15
        return [1 / (1 + ((mv + 30) / -6).exp()), 1 / (1 + ((mv + 80) / Decimal("6.4")).exp())], [
            10 * ms,
            59 * ms,
        ]
    difference = -27 - mv
    ma = (
        Decimal(".209")
        if difference == 0
        else Decimal(".055") * difference / ((difference / Decimal("3.8")).exp() - 1)
    )
    mb = Decimal(".94") * ((-75 - mv) / 17).exp()
    ha = Decimal(".000457") * ((-13 - mv) / 50).exp()
    hb = Decimal(".0065") / (((-mv - 15) / 28).exp() + 1)
    return [ma / (ma + mb), ha / (ha + hb)], [ms / (ma + mb), ms / (ha + hb)]


def kinetics(voltage, name):
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage, name)
        return dict(target=[float(v) for v in target], tau_s=[float(v) for v in tau])


def opening(gates, name):
    with localcontext() as context:
        context.prec = 80
        if name not in CLASSES or len(gates) != 2:
            raise ValueError("Require a declared class and explicit m/h")
        m, h = (_d(v, "gate") for v in gates)
        if not 0 <= m <= 1 or not 0 <= h <= 1:
            raise ValueError("Gate outside [0,1]")
        return 1.0 if name == "CaLeak" else float(m * m * h)


def rhs(gates, voltage, name):
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage, name)
        opening(gates, name)
        return [float((a - _d(g, "gate")) / t) for g, a, t in zip(gates, target, tau, strict=True)]


def relaxation(initial, voltage, name, time_s):
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage, name)
        time = _d(time_s, "time")
        if time < 0:
            raise ValueError("Negative time")
        opening(initial, name)
        return [
            float(a + (_d(g, "gate") - a) * (-time / t).exp())
            for g, a, t in zip(initial, target, tau, strict=True)
        ]


def backward_euler(initial, voltage, name, dt_s):
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage, name)
        dt = _d(dt_s, "native step")
        if dt < 0:
            raise ValueError("Negative step")
        opening(initial, name)
        return [
            float((t * _d(g, "gate") + dt * a) / (t + dt))
            for g, a, t in zip(initial, target, tau, strict=True)
        ]


def voltage_derivative(voltage, name):
    """80-digit centered difference with a 1e-20-V increment, including the limit."""
    with localcontext() as context:
        context.prec = 80
        v, h = _d(voltage, "voltage"), Decimal("1e-20")
        plus, minus = _kinetics(v + h, name), _kinetics(v - h, name)
        return [
            float((a - b) / (2 * h))
            for group_a, group_b in zip(plus, minus, strict=True)
            for a, b in zip(group_a, group_b, strict=True)
        ]


def clamp_clock(voltage, name):
    values = kinetics(voltage, name)
    stop, step = 12 * max(values["tau_s"]), min(values["tau_s"]) / 4
    time, times = 0.0, [0.0]
    while time < stop:
        time = min(stop, time + step)
        times.append(time)
        step *= 1.2
    return times
