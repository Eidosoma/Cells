"""Independent 80-digit sodium gates, initialization and held-voltage clocks.

No production Cells, NumPy or JAX imports. Equations use explicit millivolts,
scalar exponential quotients and analytic zero limits, not production helpers.
"""

from decimal import Decimal, localcontext
from numbers import Real

CLASSES = ("Nav1p2", "Nav1p3", "NavRat2", "NavRat1", "NavRat3", "NaLeak", "Nav1p6")
SINGULAR_V = {
    "Nav1p2": (-0.025, -0.040, -0.065000123),
    "Nav1p3": (-0.026,),
    "NavRat2": (-0.038,),
    "NavRat1": (-0.035, -0.050, -0.075000123),
    "NavRat3": (-0.035, -0.050, -0.075000123),
    "NaLeak": (),
    "Nav1p6": (),
}


def _d(value, name):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(name + " requires a real number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite " + name)
    return result


def _quotient(x, scale):
    return scale if x == 0 else x / (1 - (-x / scale).exp())


def _sigmoid(x):
    return 1 / (1 + x.exp())


def _kinetics(voltage, name):
    if name not in CLASSES:
        raise ValueError("Unknown pinned sodium class")
    v = _d(voltage, "voltage")
    if not Decimal("-0.120") <= v <= Decimal("0.060"):
        raise ValueError("Voltage outside declared computational domain")
    mv, ms = 1000 * v, Decimal("0.001")
    if name == "NaLeak":
        return [Decimal(1), Decimal(1)], [Decimal(1), Decimal(1)]
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


def kinetics(voltage, name):
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage, name)
        return dict(target=[float(v) for v in target], tau_s=[float(v) for v in tau])


def opening(gates, name):
    with localcontext() as context:
        context.prec = 80
        if name not in CLASSES or len(gates) != 2:
            raise ValueError("Require a declared class and m/h gates")
        m, h = (_d(v, "gate") for v in gates)
        if not 0 <= m <= 1 or not 0 <= h <= 1:
            raise ValueError("Gate outside [0,1]")
        return float(Decimal(1) if name == "NaLeak" else m if name == "Nav1p6" else m**3 * h)


def rhs(gates, voltage, name):
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage, name)
        opening(gates, name)
        return [float((a - _d(g, "gate")) / t) for g, a, t in zip(gates, target, tau, strict=True)]


def relaxation(initial, voltage, name, time_s):
    """Exact continuous held-voltage solution, covering arbitrarily slow gates."""
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage, name)
        time = _d(time_s, "relaxation time")
        if time < 0:
            raise ValueError("Negative time")
        opening(initial, name)
        return [
            float(a + (_d(g, "gate") - a) * (-time / t).exp())
            for g, a, t in zip(initial, target, tau, strict=True)
        ]


def backward_euler(initial, voltage, name, dt_s):
    """Separate native-clock oracle, using seconds consistently."""
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
    """Base event clock to 12 slow time constants, resolving the fast gate first."""
    values = kinetics(voltage, name)
    stop = 12 * max(values["tau_s"])
    step, time, times = min(values["tau_s"]) / 4, 0.0, [0.0]
    while time < stop:
        time = min(stop, time + step)
        times.append(time)
        step *= 1.2
    return times
