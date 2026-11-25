"""Decimal arithmetic: precision, constants, exact readings and the published formats.

Every declared real is read as the exact value of its nearest double (SPEC section 0): `exact` takes the
float that the JSON reader returned and converts it to Decimal without rounding.
"""

import decimal
from decimal import Decimal

WORK_DIGITS = 110      # working precision of the propagators and closed forms
QUAD_DIGITS = 120      # working precision inside the quadratures (cancellation near t = 0)
DEEP_DIGITS = 260      # working precision of the few checks that need more (a centred difference, an exact zero start)
PUBLISH_DIGITS = 40    # README: values are published at 40 significant digits

ZERO = Decimal(0)
ONE = Decimal(1)
TWO = Decimal(2)
HALF = Decimal("0.5")

_EMAX = 999999
_EMIN = -999999


def set_precision(digits=WORK_DIGITS):
    """Set the context of the running thread."""
    context = decimal.getcontext()
    context.prec = digits
    context.rounding = decimal.ROUND_HALF_EVEN
    context.Emax = _EMAX
    context.Emin = _EMIN
    for trap in (decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow):
        context.traps[trap] = True


class precision:
    """Context manager: a block at another working precision."""

    def __init__(self, digits):
        self.digits = digits

    def __enter__(self):
        self._saved = decimal.getcontext().prec
        decimal.getcontext().prec = self.digits

    def __exit__(self, *exc):
        decimal.getcontext().prec = self._saved
        return False


def exact(x):
    """The exact value of a declared number (a double or an integer)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError(f"not a declared number: {x!r}")
    return Decimal(x)


set_precision()        # before any constant below is computed

# LAWS section 0. Both are declared reals, so both are read as their nearest doubles.
N_A_TEXT = "6.02214076e23"
K_B_TEXT = "1.380649e-23"
N_A = exact(float(N_A_TEXT))
K_B = exact(float(K_B_TEXT))

U = TWO ** -53          # binary64's unit roundoff; exact in Decimal at the working precision


def thermal_energy(temperature):
    """RT in pJ/fmol: R T / 1000 (1 J/mol = 1e-3 pJ/fmol)."""
    return N_A * K_B * temperature / 1000


def pi():
    """Pi at the current precision, by Machin's formula."""
    digits = decimal.getcontext().prec

    def arctan_inverse(n):
        n = Decimal(n)
        power = ONE / n
        square = n * n
        total = power
        k = 1
        while True:
            power = -power / square
            term = power / (2 * k + 1)
            total += term
            if abs(term) < Decimal(10) ** (-(digits + 6)):
                return total
            k += 1

    with precision(digits + 8):
        value = 4 * (4 * arctan_inverse(5) - arctan_inverse(239))
    return +value


def phi(r):
    """r ln r - r + 1, with phi(0) = 1 (LAWS section 0)."""
    if r == 0:
        return ONE
    return r * r.ln() - r + 1


def x_ln_ratio(x, numerator, denominator):
    """x ln(numerator/denominator), and 0 where x = 0."""
    if x == 0:
        return ZERO
    return x * (numerator / denominator).ln()


_PUBLISH = decimal.Context(prec=PUBLISH_DIGITS, rounding=decimal.ROUND_HALF_EVEN, Emax=_EMAX, Emin=_EMIN)
_BOUND = decimal.Context(prec=3, rounding=decimal.ROUND_CEILING, Emax=_EMAX, Emin=_EMIN)
_SHORT = decimal.Context(prec=6, rounding=decimal.ROUND_HALF_EVEN, Emax=_EMAX, Emin=_EMIN)


def publish(x):
    """A value as a decimal string of 40 significant digits; an exact zero as "0"."""
    if x == 0:
        return "0"
    return format(_PUBLISH.plus(x), f".{PUBLISH_DIGITS - 1}E")


def publish_bound(x):
    """An absolute bound: three digits, rounded up; zero as "0"."""
    if x < 0:
        raise ValueError("a bound is not negative")
    if x == 0:
        return "0"
    return format(_BOUND.plus(x), ".2E")


def short(x):
    """A residual or a fraction at six digits."""
    if x == 0:
        return "0"
    return format(_SHORT.plus(x), ".5E")


RELATIVE_ACCURACY = Decimal(10) ** -39


def accuracy(value, extra=ZERO):
    """The absolute bound of a published value.

    Publication rounds to 40 digits (at most 5e-40 of the value). The computation's own error is far below
    that: every published amount is compared with a second method to 1e-50 of its scale (`checks`). `extra`
    is an additional absolute error (the integrals').
    """
    if value == 0 and extra == 0:
        return ZERO
    return abs(value) * RELATIVE_ACCURACY + extra
