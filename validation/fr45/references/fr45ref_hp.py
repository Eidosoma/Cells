"""High-precision arithmetic for FR-45's code-blind references.

Standard library only: ``decimal`` (libmpdec) carries the working precision and
``fractions`` checks exact conversions. Every binary64 input enters exactly
(``Decimal(float)`` is exact), every operation rounds once to the working digits,
and every reported value leaves through ``f64``, the correctly rounded binary64
(round half to even), so a reported value is rounded once.

Wang's closed form needs arccos and cos; ``decimal`` has neither, so ``atan``,
``acos`` and ``cos`` below are series with argument reduction, evaluated with
guard digits.
"""

from __future__ import annotations

import decimal
from decimal import Decimal
from fractions import Fraction

WORKING_DIGITS = 50
_GUARD = 12


def make_context(digits: int) -> decimal.Context:
    return decimal.Context(
        prec=digits,
        rounding=decimal.ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow],
    )


def use_working_context(digits: int = WORKING_DIGITS) -> None:
    """Install the working context for this thread (the references run on one thread)."""
    decimal.setcontext(make_context(digits))


use_working_context()

ZERO = Decimal(0)
ONE = Decimal(1)
TWO = Decimal(2)
EPS = Decimal(2.0**-52)  # binary64's epsilon, exact


def D(x) -> Decimal:
    """Exact conversion of a binary64, an int or a decimal literal string."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        raise TypeError("a bool is not an amount")
    if isinstance(x, (int, float, str)):
        d = Decimal(x)
        if not d.is_finite():
            raise ValueError(f"not finite: {x!r}")
        return d
    raise TypeError(f"cannot convert {type(x).__name__}")


EPS_Q = Fraction(1, 2**52)


def Q(x) -> Fraction:
    """The exact rational value of a Decimal, binary64, int or decimal literal."""
    if isinstance(x, Fraction):
        return x
    if isinstance(x, bool):
        raise TypeError("a bool is not an amount")
    if isinstance(x, (Decimal, float, int, str)):
        return Fraction(x)
    raise TypeError(f"cannot convert {type(x).__name__}")


def fq(x: Fraction) -> float:
    """The binary64 nearest to an exact rational, ties to even (rounded once)."""
    if not isinstance(x, Fraction):
        raise TypeError("fq takes a Fraction")
    return float(x)


def f64(x: Decimal) -> float:
    """The binary64 nearest to x, ties to even (via the exact decimal string)."""
    if not isinstance(x, Decimal):
        raise TypeError("f64 takes a Decimal")
    return float(x)


def f64_exact_check(x: Decimal) -> bool:
    """True when f64 agrees with the exact rational rounding (used by the self-check)."""
    return f64(x) == float(Fraction(x))


def lit(text: str) -> float:
    """A declared binary64 literal, as written."""
    return float(text)


def ln(x: Decimal) -> Decimal:
    return x.ln()


def exp(x: Decimal) -> Decimal:
    return x.exp()


def sqrt(x: Decimal) -> Decimal:
    return x.sqrt()


def _atan_series(y: Decimal) -> Decimal:
    """atan(y) by its Taylor series, |y| <= 1/4, at the current precision."""
    tiny = Decimal(10) ** (-(decimal.getcontext().prec + 2))
    y2 = y * y
    power = y
    total = y
    k = 0
    while True:
        k += 1
        power = -power * y2
        term = power / (2 * k + 1)
        if abs(term) <= tiny * abs(total):
            break
        total += term
    return total


_PI: dict[int, Decimal] = {}


def pi() -> Decimal:
    """pi at the current precision (Machin's formula, guarded)."""
    prec = decimal.getcontext().prec
    if prec not in _PI:
        with decimal.localcontext() as ctx:
            ctx.prec = prec + _GUARD
            value = 16 * _atan_series(ONE / 5) - 4 * _atan_series(ONE / 239)
        _PI[prec] = +value
    return _PI[prec]


def atan(x: Decimal) -> Decimal:
    with decimal.localcontext() as ctx:
        ctx.prec += _GUARD
        if x == 0:
            return ZERO
        negative = x < 0
        y = abs(x)
        complement = y > 1
        if complement:
            y = ONE / y
        halvings = 0
        while y > Decimal("0.05"):
            y = y / (1 + (1 + y * y).sqrt())
            halvings += 1
        r = _atan_series(y) * (2**halvings)
        if complement:
            r = pi() / 2 - r
        if negative:
            r = -r
    return +r


def acos(x: Decimal) -> Decimal:
    if x > 1 or x < -1:
        raise ValueError("acos argument outside [-1, 1]")
    with decimal.localcontext() as ctx:
        ctx.prec += _GUARD
        if x == 1:
            r = ZERO
        elif x == -1:
            r = pi()
        else:
            r = 2 * atan(((1 - x) / (1 + x)).sqrt())
    return +r


def cos(x: Decimal) -> Decimal:
    with decimal.localcontext() as ctx:
        ctx.prec += _GUARD
        y = abs(x)
        halvings = 0
        while y > Decimal("0.125"):
            y = y / 2
            halvings += 1
        tiny = Decimal(10) ** (-(ctx.prec + 2))
        y2 = y * y
        term = ONE
        total = ONE
        k = 0
        while True:
            k += 2
            term = -term * y2 / (k * (k - 1))
            if abs(term) <= tiny:
                break
            total += term
        for _ in range(halvings):
            total = 2 * total * total - 1
    return +total


def dmax(values) -> Decimal:
    out = None
    for v in values:
        if out is None or v > out:
            out = v
    if out is None:
        raise ValueError("empty")
    return out
