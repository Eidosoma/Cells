"""Positive-domain calcium extrusion and reversible 3-Na/1-Ca exchange.

PMCA preserves BETSE 1.5's one-Ca, numeric-mM ATP quotient. NCX is a named
synthetic symmetric-barrier law, not a fit or a native BETSE transporter.
Positive cycles move Ca out; NCX additionally moves three Na inward.
"""

from typing import NamedTuple

import jax.numpy as jnp

from cells.processes import er_calcium
from cells.processes.electrochemistry import F, R

PUMP_LAW = "betse_1_5_plasma_calcium_pump_positive@1"
EXCHANGER_LAW = "ncx_3na_1ca_symmetric_barrier@1"
MAX_AFFINITY_RT = 80.0
MAX_VOLTAGE = 0.15
PumpParameters = er_calcium.PumpParameters
chemical_drive = er_calcium.chemical_drive


class ExchangerParameters(NamedTuple):
    capacity_fmol_per_s: object
    km_na_mM: object
    km_ca_mM: object


def pump_rates(ci, co, voltage, temperature, p, availability, *, xp=jnp):
    # ER voltage is destination minus source. Plasma Vm is inside minus outside.
    return er_calcium.pump_rates(ci, co, -voltage, temperature, p, availability, xp=xp)


def exchange_rates(ni, no, ci, co, voltage, temperature, p, availability, *, xp=jnp):
    """Common positive denominator enforces the prescribed reversal potential.

    D = (1 + (Ni/Kn)^3 + (No/Kn)^3) (1 + Ci/Kc + Co/Kc).
    Forward weight: (No/Kn)^3 (Ci/Kc) exp(-FV/2RT) / D.
    Reverse weight: (Ni/Kn)^3 (Co/Kc) exp(+FV/2RT) / D.
    No concentration floors, clipping or implicit ATP supply.
    """
    lni, lno = xp.log(ni) - xp.log(p.km_na_mM), xp.log(no) - xp.log(p.km_na_mM)
    lci, lco = xp.log(ci) - xp.log(p.km_ca_mM), xp.log(co) - xp.log(p.km_ca_mM)
    x = F * voltage / (R * temperature)
    a = 3 * (xp.log(ni) - xp.log(no)) + xp.log(co) - xp.log(ci) + x
    log_d = xp.logaddexp(0.0, xp.logaddexp(3 * lni, 3 * lno))
    log_d += xp.logaddexp(0.0, xp.logaddexp(lci, lco))
    log_forward = 3 * lno + lci - 0.5 * x - log_d
    enabled = (p.capacity_fmol_per_s > 0) & (availability > 0)
    magnitude = xp.exp(
        xp.log(xp.where(enabled, p.capacity_fmol_per_s, 1.0))
        + xp.log(xp.where(enabled, availability, 1.0))
        + log_forward
        + xp.maximum(a, 0.0)
    )
    departure = xp.where(a >= 0, xp.expm1(-a), -xp.expm1(a))
    return xp.where(enabled, magnitude * departure, 0.0), R * temperature * a
