"""Shared constants, exact input parsing and result types for FR-10's references.

**Constants.** The FR lane's inputs state the exact SI (2019) defining constants:
N_A = 6.02214076e23 /mol, e = 1.602176634e-19 C and k_B = 1.380649e-23 J/K, with F = N_A e and
R = N_A k_B. The references use these exact values, never Appendix A's rounded RT = 2.577 pJ/fmol
and F = 96485.33 C/mol (their relative errors, 1.9e-4 and 2.2e-8, would fail a 1e-12 criterion).

**Inputs.** Every world value (volume, concentration, area, time, charge) is read as the exact
value of its IEEE double, ``Fraction(float(x))``: what an engine reading the same file holds. The
file's ``0.010000000000000002`` is therefore float(0.001 + 0.009), not 0.01.

**Units** (the design's and the inputs'): fmol, pL, mM = fmol/pL, s, m, m^2, m/s, F, C, V and
pJ. Chemical potentials are in J/mol, so an energy is 1e-3 x (J/mol) x fmol in pJ.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
INPUTS_PATH = HERE / "reference_inputs.json"
DESIGNS = HERE / "designs"

UNIT_ROUNDOFF = 2.0 ** -53
DIGITS = 50
"""Decimal working precision of the exact evaluations (ln and exp at 50 significant digits)."""

MIN_MARGIN = 10.0
"""A planted control has power when its deviation is at least this multiple of the tolerance."""

FMOL_PER_MOL = 10 ** 15
PJ_PER_JMOL_FMOL = Fraction(1, 1000)
"""(J/mol) x fmol = 1e-15 J = 1e-3 pJ: the design's 10^-3 factor."""

SI_EXACT = {
    "avogadro_per_mol": Fraction("6.02214076e23"),
    "elementary_charge_C": Fraction("1.602176634e-19"),
    "boltzmann_J_per_K": Fraction("1.380649e-23"),
}


@dataclass(frozen=True)
class Constants:
    """The exact SI constants, with F and R derived from them."""

    avogadro: Fraction = SI_EXACT["avogadro_per_mol"]
    elementary_charge: Fraction = SI_EXACT["elementary_charge_C"]
    boltzmann: Fraction = SI_EXACT["boltzmann_J_per_K"]

    @property
    def faraday(self) -> Fraction:
        """F = N_A e (C/mol)."""
        return self.avogadro * self.elementary_charge

    @property
    def gas_constant(self) -> Fraction:
        """R = N_A k_B (J/mol/K)."""
        return self.avogadro * self.boltzmann

    def RT(self, temperature_K) -> Fraction:
        """RT in J/mol."""
        return self.gas_constant * exact(temperature_K)

    def thermal_voltage(self, temperature_K) -> Fraction:
        """RT/F = k_B T/e in V."""
        return self.boltzmann * exact(temperature_K) / self.elementary_charge


def constants_from_block(block=None) -> Constants:
    """The exact SI constants, after checking that an inputs block states the same values.

    Each stated number must round to the same double as the exact SI value; anything else is
    refused, since the references are defined on the exact constants.
    """
    if block is None:
        return Constants()
    for key, value in SI_EXACT.items():
        if key not in block:
            raise ValueError(f"constants block lacks {key!r}")
        if float(block[key]) != float(value):
            raise ValueError(f"constant {key}={block[key]!r} is not the exact SI value {value}")
    return Constants()


def exact(x) -> Fraction:
    """The exact value of the double that ``x`` denotes (int, float, Decimal or numeric string)."""
    if isinstance(x, Fraction):
        return x
    if isinstance(x, (int, np.integer)) and not isinstance(x, bool):
        return Fraction(int(x))
    return Fraction(float(x))


def dec(x) -> Decimal:
    """A Fraction (or anything ``exact`` accepts) as a Decimal at the working precision."""
    fr = exact(x)
    with localcontext() as ctx:
        ctx.prec = DIGITS
        return Decimal(fr.numerator) / Decimal(fr.denominator)


def dec_ln(x) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = DIGITS
        return dec(x).ln() if not isinstance(x, Decimal) else x.ln()


def dec_exp(x: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = DIGITS
        return x.exp()


def load_inputs(path=INPUTS_PATH) -> dict:
    """The registered inputs, as a plain ``json.load`` gives them (floats)."""
    return json.loads(Path(path).read_text())


@dataclass
class CheckResult:
    """A check's verdict with the numbers that decided it."""

    name: str
    passed: bool
    detail: dict

    def as_dict(self) -> dict:
        return {"name": self.name, "passed": bool(self.passed), "detail": jsonable(self.detail)}


def jsonable(obj):
    """Convert NumPy, Fraction and Decimal values to plain JSON types, recursively."""
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return jsonable(obj.tolist())
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, Fraction, Decimal)):
        return float(obj)
    return obj
