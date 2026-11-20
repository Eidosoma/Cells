"""Arithmetic backends, constants and the cited parameters of the component references.

The reference values are computed with the standard library's ``decimal`` at ``PREC``
significant digits (60; the appendix's section 8 asks for 50 or more). ``PREC_CHECK`` (80) is
the re-run that measures the references' own error. A float64 backend with the same interface
evaluates the same formulas the way an engine's kernel would; it is used only to size and
calibrate the bands.

Every Decimal operation runs inside ``precision()``, a local context: nothing here changes the
thread's global decimal context.
"""
from __future__ import annotations

import math
from contextlib import contextmanager
from decimal import Decimal, localcontext

PREC = 60
PREC_CHECK = 80

# float64's machine epsilon, 2**-52: the unit of every band.
EPS64 = 2.0 ** -52


@contextmanager
def precision(prec: int = PREC):
    """A local decimal context at ``prec`` digits; the default traps (invalid operation,
    division by zero, overflow) stay on, so a bad operation raises."""
    with localcontext() as ctx:
        ctx.prec = prec
        ctx.Emax = 999_999
        ctx.Emin = -999_999
        yield ctx


class DecimalBackend:
    """High precision. Numbers are built exactly from strings, ints and floats."""

    name = "decimal"

    @staticmethod
    def n(v) -> Decimal:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, (int, float)):
            return Decimal(v)  # a float's exact binary value
        return Decimal(str(v))

    @staticmethod
    def exp(x: Decimal) -> Decimal:
        return x.exp()

    @staticmethod
    def ln(x: Decimal) -> Decimal:
        return x.ln()

    @staticmethod
    def expm1(x: Decimal) -> Decimal:
        if abs(x) < Decimal("1e-6"):
            # Taylor series: exp(x) - 1 loses |log10 x| digits to cancellation.
            term, total, k = x, x, 1
            while True:
                k += 1
                term = term * x / k
                if term == 0 or abs(term) < abs(total) * Decimal(10) ** (-(PREC_CHECK + 10)):
                    break
                total += term
            return total
        return x.exp() - 1

    @staticmethod
    def to_float(x: Decimal) -> float:
        return float(x)


class FloatBackend:
    """float64, the way an engine's kernel computes (used for band calibration only)."""

    name = "float64"

    @staticmethod
    def n(v) -> float:
        return float(v)  # strings and Decimals are rounded correctly to the nearest double

    exp = staticmethod(math.exp)
    ln = staticmethod(math.log)
    expm1 = staticmethod(math.expm1)

    @staticmethod
    def to_float(x: float) -> float:
        return x


DEC = DecimalBackend()
F64 = FloatBackend()

# --- Constants (appendix section 0: declared, uncited) -------------------------------------
# The exact SI defining constants (2019); R = N_A k_B and F = N_A e.
N_A = "6.02214076e23"
K_B = "1.380649e-23"
E_CHARGE = "1.602176634e-19"
T_KELVIN = "310.15"


def constants(B, T: str = T_KELVIN, overrides: dict | None = None) -> dict:
    """R, F, T, RT (J/mol), F/RT per mV, ln 10 and RT ln 10^7 in backend ``B``.

    ``overrides`` replaces derived constants by given strings (used only by plants)."""
    NA, kB, e = B.n(N_A), B.n(K_B), B.n(E_CHARGE)
    TT = B.n(T)
    R = NA * kB
    F = NA * e
    RT = R * TT
    c = {"R": R, "F": F, "T": TT, "RT": RT}
    if overrides and "RT" in overrides:
        c["RT"] = B.n(overrides["RT"])
    c["F_RT_per_mV"] = c["F"] / c["RT"] / B.n(1000)
    if overrides and "F_RT_per_mV" in overrides:
        c["F_RT_per_mV"] = B.n(overrides["F_RT_per_mV"])
    c["ln10"] = B.ln(B.n(10))
    c["RT_ln_1e7"] = c["RT"] * B.n(7) * c["ln10"]
    return c


# --- Cited parameters ------------------------------------------------------------------------
# Beard 2005 (PLoS Comput Biol 1(4):e36) with its 2006 correction (2(1):e8), Table 1 as the
# appendix's section 7 lists it, and Table 2's standard free energies at pH 7 (J/mol). Units:
# M unless the key ends in _mM. The appendix's conventions (approved by the lead): every law
# uses the "With Pi control" column; the Eq. 7 rows use the "Without" column's X_C3.
PARAMS_WITH_PI_CONTROL = {
    "X_C1": "0.36923",
    "X_C3": "0.091737",
    "k_Pi3_mM": "0.19172",
    "k_Pi4_mM": "25.310",
    "X_C4": "3.2562e-5",
    "k_O2": "1.20e-4",
    "X_F1": "150.93",
    "n_A": "3",
    "K_MgATP": "24.0e-6",
    "K_MgADP": "347.0e-6",
    "k_dH": "1.7783e-7",
    "X_ANT": "0.0079204",
    "k_mADP": "3.5e-6",
    "X_PiHt": "3.3943e5",
    "k_PiHt_mM": "0.45082",
    "X_KH": "2.9802e7",
    "X_DH": "0.09183",
    "r": "4.5807",
    "k_Pi1_mM": "0.13413",
    "k_Pi2_mM": "0.67668",
    "NAD_tot_mM": "2.97",
    "Q_tot_mM": "1.35",
    "cytC_tot_mM": "2.70",
    "A_tot_mM": "10",
    # Eq. 14's voltage shares.
    "theta_P": "0.35",
    "theta_N": "0.65",
    # Table 2 at pH 7, J/mol. Complex IV's is per 1/2 O2; ATP's is for H+ + ADP + Pi -> ATP
    # with total Pi (the sign of Table 2, appendix section 2).
    "dG0_C1_pH7": "-69370",
    "dG0_C3_pH7": "-32530",
    "dG0_C4_pH7_half_O2": "-122940",
    "dG0_ATP_pH7": "36030",
}

# The "Without" column, where it differs. Only X_C3 is used (the Eq. 7 rows).
PARAMS_WITHOUT_PI_CONTROL = {
    "X_C1": "0.54088",
    "X_C3": "0.14483",
    "X_C4": "2.2669e-5",
    "X_F1": "154.82",
    "X_ANT": "0.010723",
    "X_PiHt": "3.7442e5",
    "k_PiHt_mM": "0.72911",
    "X_KH": "3.1775e7",
    "X_DH": "0.10990",
    "r": "4.2530",
    "k_Pi1_mM": "0.13890",
    "k_Pi2_mM": "0.62396",
}


def parameters(column: str = "with") -> dict:
    """The parameter strings of one column ("with" or "without" Pi control)."""
    p = dict(PARAMS_WITH_PI_CONTROL)
    if column == "without":
        p.update(PARAMS_WITHOUT_PI_CONTROL)
    elif column != "with":
        raise ValueError(column)
    return p


def fmt(x, digits: int = 25) -> str:
    """A Decimal (or float) as a string with ``digits`` significant digits."""
    d = x if isinstance(x, Decimal) else Decimal(x)
    if d == 0:
        return "0"
    return format(d, f".{digits - 1}E")
