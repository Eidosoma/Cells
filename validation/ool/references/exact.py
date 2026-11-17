"""Exact arithmetic for rates and Boltzmann weights: numbers of the form r * exp(q).

Every registered world uses rational rate constants, rational activities, standard
potentials of the form mu0 = -ln(p/q), rational interaction parameters chi and rational
catalytic enhancements beta. Each rate and each Boltzmann weight exp(-F) is then exactly a
positive rational times exp(rational): the logarithms of rationals are absorbed into the
rational factor, and only the regular-mixing term (1/2N) Sum chi_ij n_i n_j stays in the
exponent.

Products and quotients of such numbers stay in the class, so Kolmogorov's cycle test and
the detailed-balance identity are decided exactly. Equality is decided on (r, q): for
rational r, r' > 0 and rational q != q', r e^q != r' e^q', because e^x is transcendental
for every nonzero algebraic x (Lindemann-Weierstrass). Sums leave the class; they are
formed in floating point from the exact logarithms.
"""

from __future__ import annotations

import math
from fractions import Fraction


def as_fraction(value) -> Fraction:
    """A Fraction from an int, a Fraction or a decimal or 'p/q' string; floats are refused."""
    if isinstance(value, bool):
        raise TypeError("a boolean is not a number here")
    if isinstance(value, (int, Fraction)):
        return Fraction(value)
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"exact values are written as int or 'p/q' strings, not {type(value).__name__}")


def log_fraction(r: Fraction) -> float:
    """ln r for a positive Fraction with large numerator or denominator, to about 1 ulp."""
    if r <= 0:
        raise ValueError("log of a non-positive number")
    return math.log(r.numerator) - math.log(r.denominator)


class RatExp:
    """An exact non-negative number r * exp(q), with r and q rational (r >= 0)."""

    __slots__ = ("r", "q")

    def __init__(self, r=1, q=0):
        r = as_fraction(r)
        q = as_fraction(q)
        if r < 0:
            raise ValueError("RatExp holds non-negative numbers only")
        if r == 0:
            q = Fraction(0)
        self.r = r
        self.q = q

    # -- arithmetic -------------------------------------------------------------------
    def __mul__(self, other) -> "RatExp":
        other = other if isinstance(other, RatExp) else RatExp(as_fraction(other))
        return RatExp(self.r * other.r, self.q + other.q)

    __rmul__ = __mul__

    def __truediv__(self, other) -> "RatExp":
        other = other if isinstance(other, RatExp) else RatExp(as_fraction(other))
        if other.r == 0:
            raise ZeroDivisionError("RatExp division by zero")
        return RatExp(self.r / other.r, self.q - other.q)

    def __pow__(self, k: int) -> "RatExp":
        if not isinstance(k, int):
            raise TypeError("integer powers only")
        if k < 0:
            return RatExp(1) / RatExp(self.r ** (-k), self.q * (-k))
        return RatExp(self.r ** k, self.q * k)

    @staticmethod
    def exp(q) -> "RatExp":
        return RatExp(1, as_fraction(q))

    # -- comparison and conversion ----------------------------------------------------
    def __eq__(self, other) -> bool:
        if not isinstance(other, RatExp):
            if not isinstance(other, (int, Fraction, str)) or isinstance(other, bool):
                return NotImplemented
            other = RatExp(as_fraction(other))
        return self.r == other.r and self.q == other.q

    def __hash__(self) -> int:
        return hash((self.r, self.q))

    def is_zero(self) -> bool:
        return self.r == 0

    def is_one(self) -> bool:
        return self.r == 1 and self.q == 0

    def log(self) -> float:
        """ln of the value (float); -inf for zero."""
        if self.r == 0:
            return -math.inf
        return log_fraction(self.r) + float(self.q)

    def __float__(self) -> float:
        if self.r == 0:
            return 0.0
        return math.exp(self.log())

    def __repr__(self) -> str:
        return f"RatExp({self.r}, {self.q})"


ZERO = RatExp(0)
ONE = RatExp(1)


def falling_factorial(n: int, k: int) -> int:
    """n (n - 1) ... (n - k + 1); zero when n < k."""
    if k < 0:
        raise ValueError("negative order")
    out = 1
    for j in range(k):
        out *= n - j
    return out if n >= k else 0
