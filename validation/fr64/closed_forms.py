"""FR-64's shift kinds as closed forms in 50-digit decimal arithmetic, written from the design
note's formulas (docs/FR64_VOLTAGE_SHIFT_DESIGN.md §1, §3.5, §3.6 and §4.2), never from the
engine's kernels. This module imports nothing from cells.

This is an independent reference for the host rows of
tests/unit/test_surface_pump_v3_populations.py. FR-64 has no registered comparison: the kinds are
proved as engine arithmetic (D361).

- **The reversal** (Nernst 1889): E = (R T/(z F)) ln(c_o/c_i). Its slope at one end is
  |dE/dc| = R T/(|z| F c).
- **The pH:** pH = -log10(h / 1000 mM), with h the free proton concentration in mM.
- **The pH shift:** dV = sigma (pH - pH_ref), with sigma in V per pH unit. Its slope in h is
  |d(dV)/dh| = |sigma|/(h ln 10).
- **The constants** are exact by the 2019 SI.
"""

from decimal import Decimal as D
from decimal import localcontext

PRECISION = 50
F = D("6.02214076e23") * D("1.602176634e-19")
R = D("6.02214076e23") * D("1.380649e-23")
PH_REFERENCE_MM = D(1000)


def _d(value):
    """A Decimal as it is, a decimal string as written, or a binary64 as its exact value."""
    if isinstance(value, D):
        return value
    return D(value) if isinstance(value, str) else D(float(value))


def reversal(inside_mM, outside_mM, valence, temperature_K):
    """E (V) of an ion of this valence."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ratio = _d(outside_mM) / _d(inside_mM)
        return R * _d(temperature_K) / (D(valence) * F) * ratio.ln()


def reversal_slope(concentration_mM, valence, temperature_K):
    """|dE/dc| (V/mM) at one end."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return R * _d(temperature_K) / (abs(D(valence)) * F * _d(concentration_mM))


def ph(h_mM):
    """pH of a free proton concentration (mM)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return -(_d(h_mM) / PH_REFERENCE_MM).log10()


def ph_shift(h_mM, shift_V_per_ph, reference_ph):
    """dV (V) = sigma (pH - pH_ref)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return _d(shift_V_per_ph) * (ph(h_mM) - _d(reference_ph))


def ph_slope(h_mM, shift_V_per_ph):
    """|d(dV)/dh| (V/mM) = |sigma|/(h ln 10)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return abs(_d(shift_V_per_ph)) / (_d(h_mM) * D(10).ln())
