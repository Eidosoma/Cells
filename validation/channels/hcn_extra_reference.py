"""Independent 80-digit equations for BETSE 1.5.0's three extra HCN classes.

The scalar API uses volts and seconds.  The native, otherwise unused m/h
states are retained here even for HCNLeak; its open fraction is exactly one.
The continuous relaxation and native backward-Euler clock are separate APIs.
No Cells, NumPy, JAX, or BETSE imports are used.
"""

from decimal import Decimal, localcontext
from numbers import Real

CLASSES = ("HCNLeak", "HCN2_cAMP", "HCN4_cAMP")
POWERS = {"HCNLeak": (0, 0), "HCN2_cAMP": (1, 0), "HCN4_cAMP": (1, 0)}
RELATIVE_PERMEABILITY = {
    "HCNLeak": (("Na", 0.33), ("K", 1.0), ("Ca", 0.05)),
    "HCN2_cAMP": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)),
    "HCN4_cAMP": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)),
}


def _decimal(value, label):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(label + " must be a real number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite " + label)
    return result


def _voltage(voltage_V, name):
    if name not in CLASSES:
        raise ValueError("Unknown extra HCN class")
    voltage = _decimal(voltage_V, "voltage")
    if not Decimal("-.120") <= voltage <= Decimal(".060"):
        raise ValueError("Voltage outside declared computational domain")
    return 1000 * voltage


def _gates(gates, name):
    if name not in CLASSES or len(gates) != 2:
        raise ValueError("Require a declared class and explicit m/h")
    values = [_decimal(value, "gate") for value in gates]
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("Gate outside [0,1]")
    return values


def _kinetics(voltage_V, name, *, initialization=False):
    mv = _voltage(voltage_V, name)
    one = Decimal(1)
    if name == "HCNLeak":
        return [one, one], [one, one]
    if name == "HCN2_cAMP":
        exponent = (mv - 20 + 99) / Decimal("6.2")
        tau_m = Decimal(184) / 1000
    else:
        shift = 20 if initialization else 24
        exponent = (mv - shift + 100) / Decimal("9.6")
        tau_m = Decimal(461) / 1000
    return [one / (one + exponent.exp()), one], [tau_m, one / 1000]


def kinetics(voltage_V, name):
    """Return (target[m,h], tau_s[m,h]) for the native update equations."""
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage_V, name)
        return [float(value) for value in target], [float(value) for value in tau]


def initial_gates(voltage_V, name):
    """Native initialization, including HCN4_cAMP's distinct −20-mV shift."""
    with localcontext() as context:
        context.prec = 80
        target, _ = _kinetics(voltage_V, name, initialization=True)
        return [float(value) for value in target]


def opening(gates, name):
    with localcontext() as context:
        context.prec = 80
        m, _ = _gates(gates, name)
        return 1.0 if name == "HCNLeak" else float(m)


def rhs(gates, voltage_V, name):
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage_V, name)
        current = _gates(gates, name)
        return [float((a - g) / t) for g, a, t in zip(current, target, tau, strict=True)]


def relaxation(gates, voltage_V, name, time_s):
    """Exact continuous fixed-voltage relaxation; not the native integrator."""
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage_V, name)
        current, time = _gates(gates, name), _decimal(time_s, "time")
        if time < 0:
            raise ValueError("Negative time")
        return [float(a + (g - a) * (-time / t).exp())
                for g, a, t in zip(current, target, tau, strict=True)]


def backward_euler(gates, voltage_V, name, dt_s):
    """Source clock: (tau*g + dt*target)/(tau + dt), with seconds throughout."""
    with localcontext() as context:
        context.prec = 80
        target, tau = _kinetics(voltage_V, name)
        current, dt = _gates(gates, name), _decimal(dt_s, "native step")
        if dt < 0:
            raise ValueError("Negative step")
        return [float((t * g + dt * a) / (t + dt))
                for g, a, t in zip(current, target, tau, strict=True)]
