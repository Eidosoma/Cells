"""hill_product_factor@1: a product of Hill factors of concentrations, in log space (G-5).

docs/IP3_RELEASE_AND_ASSEMBLY_AVAILABILITY_DESIGN.md, sections 4.2, 5.2 and 5.8. One factor has
reads j = 1 to J, each a concentration x_j (mM) under a form, a half-saturation K_j (mM, > 0) and a
Hill coefficient n_j (> 0):

    z_j    = n_j (ln x_j - ln K_j)
    ln h_j = -ln(1 + e^(-z_j))  under hill_activation,  -ln(1 + e^(z_j))  under hill_inhibition
    ln f   = ln h_1 + ln h_2 + ...                      a serial left fold, in declared order
    f      = e^(ln f)                                   dimensionless, in [0, 1]

- **h_j is the helper's** (hill_factors.log_factor), so the factor of one read is that helper's
  factor bit for bit, and f is one exponential of one sum. Each ln h_j <= 0, so f lies in [0, 1].
- **Its sense.** An activation rises and an inhibition falls as its concentration rises. A route or
  a channel whose control is multiplied by f opens with f.
- **Zero, negative, NaN.** ln 0 = -infinity: an activation is exactly 0 there and an inhibition
  exactly 1, on the host and compiled. A negative or NaN concentration gives NaN, which the routing
  door refuses. Nothing is clipped.
- **Its slopes** (log_slopes), d ln f / d ln x_j at fixed volume, signed, one per read:
  +n_j (1 - h_j) for an activation and -n_j (1 - h_j) for an inhibition. 1 - h_j is formed directly,
  as the opposite form's factor at the same z_j, so it loses no accuracy where h_j is near 1. Each
  is finite, 0 in padding, and within [-n_j, n_j], at a zero concentration too.
- **What it does not represent.** The reads are separable: no read changes another's
  half-saturation. A reading binds nothing: no species is consumed by it. It is instantaneous.

The second half of the module is the law's declaration: its interface, cells.transfer_factor_law@1
(a dimensionless factor on a transfer's control), and its record (LAW), which the law registry's
loader registers through @3's model table (inert: importing this module registers nothing).

Pure functions in the xp style, in NumPy or JAX. Arrays are [..., read]; a form code is
hill_factors' (0 is padding, whose factor is 1).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from cells.laws.reactions import hill_factors
from cells.modules import Citation, CitedWork, Law

LAW_ID = "hill_product_factor@1"
TRANSFER_FACTOR_LAW = "cells.transfer_factor_law@1"  # Declared in @3's row of the model table.
FORMS = tuple(hill_factors.KINDS.items())  # ((form, code), ...): the codes are hill_factors'.
PARAMETERS = ("half_saturation_mM", "hill_coefficient")  # Each read's.
VALUE_RANGE = (0.0, 1.0)
BOTH = hill_factors.ACTIVATION + hill_factors.INHIBITION  # Less a form's code: the other form's.


def log_factor(log_x, half_saturation_mM, coefficient, form, *, xp):
    """ln f [...]: the reads' ln h_j [..., read], summed by a serial left fold in declared order.

    log_x: ln of each read's concentration in mM (-infinity at zero)."""
    terms = hill_factors.log_factor(log_x, half_saturation_mM, coefficient, form, xp=xp)
    total = terms[..., 0]
    for j in range(1, terms.shape[-1]):
        total = total + terms[..., j]
    return total


def factor(log_x, half_saturation_mM, coefficient, form, *, xp):
    """f [...] = e^(ln f), in [0, 1]."""
    return xp.exp(log_factor(log_x, half_saturation_mM, coefficient, form, xp=xp))


def log_slopes(log_x, half_saturation_mM, coefficient, form, *, xp):
    """d ln f / d ln x_j [..., read], signed (module docstring); 0 in padding, whose code BOTH - 0
    is neither form's."""
    complement = hill_factors.factor(log_x, half_saturation_mM, coefficient, BOTH - form, xp=xp)
    sign = xp.where(
        form == hill_factors.ACTIVATION,
        1.0,
        xp.where(form == hill_factors.INHIBITION, -1.0, 0.0),
    )
    return sign * coefficient * complement


# ---------------------------------------------------------------------------- the declaration

KERNELS = ("log_factor", "factor", "log_slopes")


@dataclass(frozen=True)
class TransferFactorLaw(Law):
    """cells.transfer_factor_law@1: a dimensionless factor on a transfer's control, read at a stage
    from what its host gives it. It has no state, moves nothing and books nothing: the route or the
    channel whose control it multiplies books what moves. Its kernels are pure functions in the xp
    style, of arrays [..., read]: each takes the reads' values (as their logarithms), its parameters
    in order and the form codes."""

    forms: tuple[tuple[str, int], ...]  # (form, code) of each form a read may take; 0 is padding.
    parameters: tuple[str, ...]  # Each read's parameters, in the kernels' order.
    value_range: tuple[float, float]  # What the factor's values lie in, both ends included.
    log_factor: Callable  # (log_x, *parameters, form, *, xp) -> ln f [...]
    factor: Callable  # (log_x, *parameters, form, *, xp) -> f [...]
    log_slopes: Callable  # (log_x, *parameters, form, *, xp) -> d ln f / d ln x [..., read], signed

    interface: ClassVar[str] = TRANSFER_FACTOR_LAW
    UNITS: ClassVar = MappingProxyType({"value_range": "1"})
    SIGNS: ClassVar = MappingProxyType(
        {"value_range": "a higher value opens what it multiplies: a route or a channel"}
    )

    def errors(self):
        out = super().errors()
        out += [f"its {name} is callable" for name in KERNELS if not callable(getattr(self, name))]
        forms = self.forms
        if not (
            isinstance(forms, tuple)
            and forms
            and all(
                isinstance(f, tuple)
                and len(f) == 2
                and isinstance(f[0], str)
                and f[0]
                and type(f[1]) is int
                and f[1] > 0
                for f in forms
            )
            and len(dict(forms)) == len({code for _, code in forms}) == len(forms)
        ):
            out.append("its forms are (form, code) pairs, distinct, each code a positive integer")
        names = self.parameters
        if not (
            isinstance(names, tuple)
            and all(isinstance(n, str) and n for n in names)
            and len(set(names)) == len(names)
        ):
            out.append("its parameters are distinct names")
        bounds = self.value_range
        if not (
            isinstance(bounds, tuple)
            and len(bounds) == 2
            and all(isinstance(v, float) and math.isfinite(v) for v in bounds)
            and bounds[0] < bounds[1]
        ):
            out.append("its value_range is a finite (low, high) interval")
        return out


LAW = TransferFactorLaw(
    LAW_ID,
    FORMS,
    PARAMETERS,
    VALUE_RANGE,
    log_factor,
    factor,
    log_slopes,
    host="cells.species_condition@1",
    provenance="parity",
    source=Citation(
        "Hill's equation (A. V. Hill, 1910; reviewed by J. N. Weiss, 1997): one saturating factor "
        "per read, and their product",
        "the form x^n/(K^n + x^n) and its complement K^n/(K^n + x^n), as the engine's Hill helper "
        "states them (laws/reactions/hill_factors.py), evaluated in log space",
        "no numbers taken: the law is a form, its half-saturations and coefficients a "
        "definition's values",
        (
            "a product of separable factors: no read changes another's half-saturation",
            "a reading binds nothing and consumes nothing",
            "instantaneous: no gate state, latency or inactivation",
        ),
        (
            CitedWork(
                ("Weiss JN",),
                1997,
                "The Hill equation revisited: uses and misuses",
                doi="10.1096/fasebj.11.11.9285481",
            ),
        ),
    ),
    test="tests/unit/test_hill_factors.py::test_the_hill_product_law_and_its_planted_errors",
)
