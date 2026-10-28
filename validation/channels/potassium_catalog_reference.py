"""Independent scalar/80-digit pinned potassium targets, powers and clocks.

No Cells/NumPy/JAX imports. Millivolt equations and literal source time units
are reconstructed separately from the production voltage/second expressions.
"""

from decimal import Decimal, localcontext
from numbers import Real

CLASSES = ("Kir2p1", "Kv2p1", "Kv2p2", "Kv3p1", "Kv3p2", "Kv3p3", "Kv3p4", "K_Fast", "KLeak")
POWERS = {
    name: (1, 2)
    if name == "Kir2p1"
    else (1, 0)
    if name == "Kv3p1"
    else (2, 0)
    if name == "Kv3p2"
    else (2, 1)
    if name == "Kv3p3"
    else (0, 0)
    if name == "KLeak"
    else (1, 1)
    for name in CLASSES
}
TRANSITIONS_V = {
    "Kir2p1": (-0.09648, -0.0329),
    "Kv2p1": (-0.0092, -0.019),
    "Kv2p2": (0.005, -0.0163),
    "Kv3p1": (0.0187,),
    "Kv3p2": (-0.000373267, 0.019220623),
    "Kv3p3": (0.035, -0.028293856),
    "Kv3p4": (-0.0034, -0.05332),
    "K_Fast": (-0.047, -0.056, -0.071, -0.073),
    "KLeak": (),
}


def _d(value, name):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(name + " requires a finite real number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite " + name)
    return result


def _kinetics(voltage, name):
    if name not in CLASSES:
        raise ValueError("Unknown pinned potassium class")
    v = _d(voltage, "voltage")
    if not Decimal("-0.120") <= v <= Decimal("0.060"):
        raise ValueError("Voltage outside declared domain")
    mv, ms = 1000 * v, Decimal("0.001")

    def sigmoid(midpoint, slope):
        return 1 / (1 + ((mv - Decimal(midpoint)) / Decimal(slope)).exp())

    if name == "KLeak":
        return [Decimal(1), Decimal(1)], [Decimal(1), Decimal(1)]
    if name == "Kir2p1":
        return [sigmoid("-96.48", "23.26"), sigmoid("-168.28", "-44.13")], [
            ms * (Decimal("3.7") - Decimal("3.37") * sigmoid("-32.9", "27.93")),
            ms * (Decimal("0.85") + Decimal("306.3") * sigmoid("-118.29", "-27.23")),
        ]
    if name == "Kv2p1":
        return [sigmoid("-9.2", "-6.6"), sigmoid("-19", "5")], [
            ms * 100 * sigmoid("-46.56", "44.14"),
            ms * 10000 * sigmoid("-46.56", "-44.14"),
        ]
    if name == "Kv2p2":
        return [sigmoid("5", "-12"), sigmoid("-16.3", "4.8")], [
            ms * 130 * sigmoid("-46.56", "-44.14"),
            ms * 10000 * sigmoid("-46.56", "-44.14"),
        ]
    if name == "Kv3p1":
        return [sigmoid("18.7", "-9.7"), Decimal(1)], [ms * 20 * sigmoid("-46.56", "-44.14"), ms]
    if name == "Kv3p2":
        return [sigmoid("-0.373267", "-8.568187"), Decimal(1)], [
            ms * (Decimal("3.241643") + Decimal("19.106496") * sigmoid("19.220623", "4.451533")),
            ms,
        ]
    if name == "Kv3p3":
        return [
            sigmoid("35", "-7.3"),
            Decimal("0.25") + Decimal("0.75") * sigmoid("-28.293856", "29.385636"),
        ], [
            ms * (Decimal("0.676808") + Decimal("27.913114") * sigmoid("22.414149", "9.704638")),
            ms
            * (Decimal("199.786728") + Decimal("2776.119438") * (-mv / Decimal("7.309565")).exp()),
        ]
    if name == "Kv3p4":
        return [sigmoid("-3.4", "-8.4"), sigmoid("-53.32", "7.4")], [
            ms * 10 * sigmoid("4.44", "38.14"),
            ms * 20000 * sigmoid("-46.56", "-44.14"),
        ]
    return [sigmoid("-47", "-29"), sigmoid("-56", "10")], [
        ms * (Decimal("0.34") + Decimal("0.92") * (-(((mv + 71) / 59) ** 2)).exp()),
        ms * (8 + 49 * (-(((mv + 73) / 23) ** 2)).exp()),
    ]


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
        a, b = POWERS[name]
        # Decimal explicitly treats 0**0 as invalid, unlike the native gate convention.
        return float((m**a if a else Decimal(1)) * (h**b if b else Decimal(1)))


def rhs(gates, voltage, name):
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage, name)
        opening(gates, name)
        return [float((a - _d(g, "gate")) / t) for g, a, t in zip(gates, target, tau, strict=True)]


def relaxation(initial, voltage, name, time_s):
    with localcontext() as context:
        context.prec = 80
        # Preserve the literal multi-day Kv3p3 horizon and its very fast companion
        # without a concentration/gate floor or shortening the physical time.
        context.Emin, context.Emax = -999999999, 999999999
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


def clamp_clock(voltage, name):
    values = kinetics(voltage, name)
    stop, step, time, times = 12 * max(values["tau_s"]), min(values["tau_s"]) / 4, 0.0, [0.0]
    while time < stop:
        time = min(stop, time + step)
        times.append(time)
        step *= 1.2
    return times
