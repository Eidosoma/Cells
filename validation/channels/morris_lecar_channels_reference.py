"""Independent 80-digit Morris–Lecar equations, raw clock and absent states."""

from decimal import Decimal, localcontext
from numbers import Real

CLASSES = (
    "Kv_ML1",
    "Kv2p1_ML",
    "Kv1p3_ML",
    "Kv1p5_ML",
    "Kv1p5S_ML",
    "Nav_ML",
    "Cav_L_ML",
    "Cav_L_ML2",
    "Cav_N_ML",
    "Cav_T_ML",
    "Kir_ML",
    "HCN2_ML",
    "HCN4_ML",
)
KINETIC = frozenset(CLASSES[:5])
PERMEABILITIES = {
    name: (("K", 1.0), ("Na", 0.2))
    if name in ("HCN2_ML", "HCN4_ML")
    else (("Na", 1.0),)
    if name == "Nav_ML"
    else (("Ca", 1.0),)
    if name in ("Cav_L_ML", "Cav_L_ML2", "Cav_N_ML", "Cav_T_ML")
    else (("K", 1.0),)
    for name in CLASSES
}
PARAMETERS = {
    "Kv_ML1": ("12", "17", ".066"),
    "Kv2p1_ML": ("14", "30", ".066"),
    "Kv1p3_ML": ("-14", "20", ".066"),
    "Kv1p5_ML": ("-6", "15", ".066"),
    "Kv1p5S_ML": ("-6", "15", ".00132"),
    "Nav_ML": ("-17", "18", "1"),
    "Cav_L_ML": ("-20", "24", "1"),
    "Cav_L_ML2": ("-20", "12", "1"),
    "Cav_N_ML": ("-1", "18", "1"),
    "Cav_T_ML": ("-43", "24", "1"),
    "Kir_ML": ("-135", "37", "1"),
    "HCN2_ML": ("-99", "12.4", "1"),
    "HCN4_ML": ("-99", "19.2", "1"),
}


def _d(value, name):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(name + " requires a real number")
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError("Nonfinite " + name)
    return value


def _values(voltage, name):
    if name not in CLASSES:
        raise ValueError("Unknown Morris–Lecar class")
    v = _d(voltage, "voltage")
    if not Decimal("-.120") <= v <= Decimal(".060"):
        raise ValueError("Outside computational voltage domain")
    midpoint, slope, phi = map(Decimal, PARAMETERS[name])
    x = (1000 * v - midpoint) / slope
    ex = x.exp()
    inverse = (-x).exp()
    cosh = (ex + inverse) / 2
    target = 1 / cosh if name == "Kir_ML" else (2 * x).exp() / (1 + (2 * x).exp())
    raw_tau = 2 / ((x / 2).exp() + (-x / 2).exp()) if name in KINETIC else Decimal(1)
    tau = raw_tau / (1000 * phi) if name in KINETIC else Decimal(0)
    return target, tau, raw_tau, phi, x, slope


def kinetics(voltage, name):
    with localcontext() as context:
        context.prec = 80
        target, tau, raw, phi, _, _ = _values(voltage, name)
        return dict(
            target=float(target),
            tau_s=float(tau),
            raw_tau=float(raw),
            phi=float(phi),
            kinetic=name in KINETIC,
        )


def opening(state, voltage, name):
    with localcontext() as context:
        context.prec = 80
        m = _d(state, "state")
        target, *_ = _values(voltage, name)
        if not 0 <= m <= 1 or (name not in KINETIC and m != 0):
            raise ValueError("Invalid dynamic/absent state")
        return float(m if name in KINETIC else target)


def rhs(state, voltage, name):
    with localcontext() as context:
        context.prec = 80
        opening(state, voltage, name)
        target, tau, *_ = _values(voltage, name)
        return float((target - _d(state, "state")) / tau) if name in KINETIC else 0.0


def relaxation(initial, voltage, name, time_s):
    """Continuous dynamic oracle only; algebraic laws have no relaxation clock."""
    with localcontext() as context:
        context.prec = 80
        if name not in KINETIC:
            raise ValueError("Instantaneous law has no dynamic state or tau")
        opening(initial, voltage, name)
        time = _d(time_s, "time")
        if time < 0:
            raise ValueError("Negative time")
        target, tau, *_ = _values(voltage, name)
        return float(target + (_d(initial, "initial state") - target) * (-time / tau).exp())


def native_update(initial, voltage, name, dt_s):
    """Raw source m attribute, including unconditional algebraic replacement."""
    with localcontext() as context:
        context.prec = 80
        m, dt = _d(initial, "source m"), _d(dt_s, "native dt")
        if not 0 <= m <= 1 or dt < 0:
            raise ValueError("Invalid source state/time")
        target, _, raw, phi, _, _ = _values(voltage, name)
        if name not in KINETIC:
            return float(target)
        step = dt * 1000 * phi / raw
        return float((m + step * target) / (1 + step))


def voltage_derivative(voltage, name):
    with localcontext() as context:
        context.prec = 80
        target, tau, _, _, x, slope = _values(voltage, name)
        tanh = (x.exp() - (-x).exp()) / (x.exp() + (-x).exp())
        dtgt = (
            -1000 * target * tanh / slope
            if name == "Kir_ML"
            else 2000 * target * (1 - target) / slope
        )
        half_tanh = ((x / 2).exp() - (-x / 2).exp()) / ((x / 2).exp() + (-x / 2).exp())
        dtau = -1000 * tau * half_tanh / (2 * slope) if name in KINETIC else Decimal(0)
        return [float(dtgt), float(dtau)]


def clamp_clock(voltage, name):
    if name not in KINETIC:
        raise ValueError("No clock for an algebraic law")
    tau = kinetics(voltage, name)["tau_s"]
    time, step, times = 0.0, tau / 4, [0.0]
    while time < 12 * tau:
        time = min(12 * tau, time + step)
        times.append(time)
        step *= 1.2
    return times
