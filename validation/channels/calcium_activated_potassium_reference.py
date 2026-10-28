"""Independent 80-digit literal legacy cagPotassium formula and derivatives."""

from decimal import Decimal, localcontext
from numbers import Real

R = Decimal("8.31446261815324")
F = Decimal("96485.3321233100184")


def _d(value):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError("Require a finite real scalar")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite scalar")
    return result


def _opening(v, c, t):
    ratio = (1 + Decimal("1e6") * c / Decimal("10.22")) / (1 + Decimal("1e6") * c / Decimal(".89"))
    odds = 6182 * ratio**4 * (-Decimal("1.64") * F * v / (R * t)).exp()
    return 1 / (1 + odds)


def evaluate(voltage, calcium_free_mM, temperature_K, availability=1):
    with localcontext() as context:
        context.prec = 80
        v, c, t, a = map(_d, (voltage, calcium_free_mM, temperature_K, availability))
        if (
            not Decimal("-.120") <= v <= Decimal(".060")
            or c < 0
            or not 200 <= t <= 400
            or not 0 <= a <= 1
        ):
            raise ValueError("Outside computational input domain")
        p = _opening(v, c, t)
        susceptibility = p * (1 - p)
        calcium_log_derivative = 4 * (1 / (c + Decimal("10.22e-6")) - 1 / (c + Decimal(".89e-6")))
        return dict(
            opening=float(p),
            effective_opening=float(a * p),
            dP_dCa_per_mM=float(-susceptibility * calcium_log_derivative),
            dP_dV_per_V=float(susceptibility * Decimal("1.64") * F / (R * t)),
            dP_dT_per_K=float(-susceptibility * Decimal("1.64") * F * v / (R * t * t)),
            d_effective_d_availability=float(p),
        )


def limiting_opening(voltage, temperature_K, *, high_calcium):
    with localcontext() as context:
        context.prec = 80
        v, t = map(_d, (voltage, temperature_K))
        if not Decimal("-.120") <= v <= Decimal(".060") or not 200 <= t <= 400:
            raise ValueError("Outside computational domain")
        ratio = Decimal(".89") / Decimal("10.22") if high_calcium else Decimal(1)
        return float(1 / (1 + 6182 * ratio**4 * (-Decimal("1.64") * F * v / (R * t)).exp()))


def manufactured_calcium_input(time_s, *, tau_s=2):
    """Declared external input: zero, one-second pulse, twelve-tau decay.

    This is not a native channel clock or a claim about calcium dynamics.
    Control/voltage changes are algebraic alongside the same free-Ca history.
    """
    with localcontext() as context:
        context.prec = 80
        time, tau = _d(time_s), _d(tau_s)
        if time < 0 or tau <= 0:
            raise ValueError("Invalid external input clock")
        if time < 1:
            c = Decimal(0)
        elif time <= 2:
            c = Decimal("2e-5")
        else:
            c = Decimal("2e-5") * (-(time - 2) / tau).exp()
        return float(c)
