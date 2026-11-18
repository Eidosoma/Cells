"""Exact and high-precision helpers: 60-digit decimals, rationals and forward-mode duals.

**Inputs** are read as the exact values of their doubles (``Decimal(float)`` is exact), as an
engine reading the same numbers holds them. **Constants** are the exact SI (2019) values,
F = N_A e and R = N_A k_B. Everything is computed with ``PREC`` significant digits and reported
to 50; ``Decimal.exp`` and ``Decimal.ln`` are correctly rounded at the context's precision.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction

DIGITS = 50
PREC = 60
UNIT_ROUNDOFF = 2.0 ** -53
EPS = 2.0 ** -52

AVOGADRO = Fraction("6.02214076e23")
ELEMENTARY_CHARGE = Fraction("1.602176634e-19")
BOLTZMANN = Fraction("1.380649e-23")
FARADAY = AVOGADRO * ELEMENTARY_CHARGE           # C/mol
GAS_CONSTANT = AVOGADRO * BOLTZMANN              # J/(mol K)
SI = {"avogadro_per_mol": AVOGADRO, "elementary_charge_C": ELEMENTARY_CHARGE,
      "boltzmann_J_per_K": BOLTZMANN}


def context():
    """The decimal context every reference computation runs in."""
    return localcontext(prec=PREC)


def dec(x) -> Decimal:
    """A number as a Decimal: a double or an int exactly, a Fraction or a string to PREC digits."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        raise TypeError("a bool is not a number here")
    if isinstance(x, int):
        return Decimal(x)
    if isinstance(x, float):
        return Decimal(x)
    if isinstance(x, Fraction):
        with context():
            return Decimal(x.numerator) / Decimal(x.denominator)
    if isinstance(x, str):
        return Decimal(x)
    if isinstance(x, Dual):
        raise TypeError("a Dual is not a plain number")
    return Decimal(float(x))


def fl(x) -> float:
    """The nearest double of a Decimal (or Dual's value)."""
    if isinstance(x, Dual):
        x = x.a
    return float(x)


def RT_J_per_mol(T_K) -> Decimal:
    """RT in J/mol at PREC digits (R exact, T read exactly)."""
    with context():
        return dec(GAS_CONSTANT) * dec(T_K)


def F_C_per_mol() -> Decimal:
    with context():
        return dec(FARADAY)


def F_over_RT(T_K) -> Decimal:
    """F/RT in 1/V."""
    with context():
        return dec(FARADAY) / RT_J_per_mol(T_K)


def check_constants(block) -> None:
    """Refuse a constants block whose values are not the exact SI ones (to their doubles)."""
    for key, value in SI.items():
        if key in block and float(block[key]) != float(value):
            raise ValueError(f"constant {key}={block[key]!r} is not the exact SI value {value}")


# --------------------------------------------------------------------------------------------
# Forward-mode duals over Decimal: exact first derivatives along one direction.
# --------------------------------------------------------------------------------------------

class Dual:
    """a + b ε with ε² = 0, over Decimal. Used for exact slopes (∂J/∂V, ∂J/∂n)."""

    __slots__ = ("a", "b")

    def __init__(self, a, b=0):
        self.a = a if isinstance(a, Decimal) else dec(a)
        self.b = b if isinstance(b, Decimal) else dec(b)

    @staticmethod
    def lift(x) -> "Dual":
        return x if isinstance(x, Dual) else Dual(dec(x), Decimal(0))

    def __add__(self, o):
        o = Dual.lift(o)
        return Dual(self.a + o.a, self.b + o.b)

    __radd__ = __add__

    def __sub__(self, o):
        o = Dual.lift(o)
        return Dual(self.a - o.a, self.b - o.b)

    def __rsub__(self, o):
        return Dual.lift(o) - self

    def __mul__(self, o):
        o = Dual.lift(o)
        return Dual(self.a * o.a, self.a * o.b + self.b * o.a)

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = Dual.lift(o)
        return Dual(self.a / o.a, (self.b * o.a - self.a * o.b) / (o.a * o.a))

    def __rtruediv__(self, o):
        return Dual.lift(o) / self

    def __neg__(self):
        return Dual(-self.a, -self.b)

    def __abs__(self):
        return -self if self.a < 0 else self

    def __pow__(self, n):
        if not isinstance(n, int):
            raise TypeError("Dual powers are integers")
        if n == 0:
            return Dual(Decimal(1), Decimal(0))
        p = self.a ** (n - 1)
        return Dual(p * self.a, n * p * self.b)

    def exp(self):
        e = self.a.exp()
        return Dual(e, e * self.b)

    def ln(self):
        return Dual(self.a.ln(), self.b / self.a)

    def __lt__(self, o):
        return self.a < Dual.lift(o).a

    def __gt__(self, o):
        return self.a > Dual.lift(o).a

    def __repr__(self):
        return f"Dual({self.a!s}, {self.b!s})"


def dexp(x):
    return x.exp() if isinstance(x, (Decimal, Dual)) else dec(x).exp()


def dln(x):
    return x.ln() if isinstance(x, (Decimal, Dual)) else dec(x).ln()


def value(x) -> Decimal:
    return x.a if isinstance(x, Dual) else x


def slope(x) -> Decimal:
    return x.b if isinstance(x, Dual) else Decimal(0)


# --------------------------------------------------------------------------------------------
# Linear algebra in decimals.
# --------------------------------------------------------------------------------------------

def solve(A, b) -> list:
    """Solve A x = b by Gaussian elimination with partial pivoting, in the current precision.

    Entries may be Decimals or Duals; pivots compare their values."""
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(value(M[r][col])))
        if value(M[piv][col]) == 0:
            raise ValueError("singular system")
        M[col], M[piv] = M[piv], M[col]
        for r in range(n):
            if r != col and value(M[r][col]) != 0:
                f = M[r][col] / M[col][col]
                M[r] = [a - f * c for a, c in zip(M[r], M[col], strict=True)]
    return [M[i][n] / M[i][i] for i in range(n)]


def det(A):
    """Determinant by elimination with partial pivoting (Decimals or Duals)."""
    n = len(A)
    if n == 0:
        return Decimal(1)
    M = [list(row) for row in A]
    sign = 1
    out = None
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(value(M[r][col])))
        if value(M[piv][col]) == 0:
            return Decimal(0)
        if piv != col:
            M[col], M[piv] = M[piv], M[col]
            sign = -sign
        out = M[col][col] if out is None else out * M[col][col]
        for r in range(col + 1, n):
            if value(M[r][col]) != 0:
                f = M[r][col] / M[col][col]
                M[r] = [a - f * c for a, c in zip(M[r], M[col], strict=True)]
    return out if sign > 0 else -out
