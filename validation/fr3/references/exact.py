"""Exact and high-precision helpers: rationals, 50-digit decimals, a decimal matrix exponential
and a rational linear solve.

**Inputs** are read as the exact values of their doubles (``Fraction(float(x))``), as an engine
reading the same numbers holds them. **Constants** are the exact SI (2019) values,
F = N_A e and R = N_A k_B; Appendix A's printed RT = 2.577 pJ/fmol and F = 96485.33 C/mol are
rounded and are never used.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction

import numpy as np

DIGITS = 50
UNIT_ROUNDOFF = 2.0 ** -53

AVOGADRO = Fraction("6.02214076e23")
ELEMENTARY_CHARGE = Fraction("1.602176634e-19")
BOLTZMANN = Fraction("1.380649e-23")
FARADAY = AVOGADRO * ELEMENTARY_CHARGE           # C/mol
GAS_CONSTANT = AVOGADRO * BOLTZMANN              # J/mol/K
SI_KEYS = {"avogadro_per_mol": AVOGADRO, "elementary_charge_C": ELEMENTARY_CHARGE,
           "boltzmann_J_per_K": BOLTZMANN}
SITES_PER_FMOL = AVOGADRO / 10 ** 15                # N_f = 602,214,076 per fmol, exact


def check_constants(block=None) -> None:
    """Refuse a constants block whose values are not the exact SI ones (to their doubles)."""
    if block is None:
        return
    for key, value in SI_KEYS.items():
        if key in block and float(block[key]) != float(value):
            raise ValueError(f"constant {key}={block[key]!r} is not the exact SI value {value}")


def exact(x) -> Fraction:
    if isinstance(x, Fraction):
        return x
    if isinstance(x, (int, np.integer)) and not isinstance(x, bool):
        return Fraction(int(x))
    return Fraction(float(x))


def dec(x) -> Decimal:
    if isinstance(x, Decimal):
        return x
    fr = exact(x)
    with localcontext() as ctx:
        ctx.prec = DIGITS
        return Decimal(fr.numerator) / Decimal(fr.denominator)


def RT(temperature_K) -> Fraction:
    """RT in J/mol (exact)."""
    return GAS_CONSTANT * exact(temperature_K)


def RT_pJ_per_fmol(temperature_K) -> Fraction:
    """RT in pJ/fmol, 1e-3 R T (exact): the unit Appendix A's energies use."""
    return RT(temperature_K) / 1000


def expm_decimal(A, t) -> list:
    """exp(A t) for a small square matrix, in 50-digit decimals (scaling, Taylor and squaring).

    ``A`` holds numbers ``exact`` accepts, or Decimals. The Taylor sum runs until its terms fall
    below 1e-60 of the norm, after scaling the matrix to a norm below 1/2.
    """
    n = len(A)
    with localcontext() as ctx:
        ctx.prec = DIGITS + 10
        At = [[dec(A[i][j]) * dec(t) for j in range(n)] for i in range(n)]
        norm = max(sum(abs(x) for x in row) for row in At)
        s = 0
        while norm > Decimal("0.5"):
            norm /= 2
            s += 1
        scale = Decimal(2) ** s
        X = [[x / scale for x in row] for row in At]
        result = [[Decimal(1 if i == j else 0) for j in range(n)] for i in range(n)]
        term = [row[:] for row in result]
        eps = Decimal(10) ** (-(DIGITS + 8))
        for k in range(1, 200):
            term = [[sum(term[i][m] * X[m][j] for m in range(n)) / k for j in range(n)]
                    for i in range(n)]
            result = [[result[i][j] + term[i][j] for j in range(n)] for i in range(n)]
            if max(abs(x) for row in term for x in row) < eps:
                break
        for _ in range(s):
            result = [[sum(result[i][m] * result[m][j] for m in range(n)) for j in range(n)]
                      for i in range(n)]
        return result


def matvec_decimal(M, v) -> list:
    with localcontext() as ctx:
        ctx.prec = DIGITS + 10
        return [sum(M[i][j] * dec(v[j]) for j in range(len(v))) for i in range(len(M))]


def solve_rational(A, b) -> list:
    """Solve A x = b exactly in rationals (Gaussian elimination with exact pivots)."""
    n = len(A)
    M = [[exact(A[i][j]) for j in range(n)] + [exact(b[i])] for i in range(n)]
    for col in range(n):
        piv = next((r for r in range(col, n) if M[r][col] != 0), None)
        if piv is None:
            raise ValueError("singular system")
        M[col], M[piv] = M[piv], M[col]
        for r in range(n):
            if r != col and M[r][col] != 0:
                f = M[r][col] / M[col][col]
                M[r] = [a - f * c for a, c in zip(M[r], M[col], strict=True)]
    return [M[i][n] / M[i][i] for i in range(n)]
