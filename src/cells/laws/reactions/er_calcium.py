"""The calcium pump's kernel from the cytosol into a store, on positive concentrations.

One calcium per formal turnover, with a numeric-mM metabolic quotient: BETSE v1.5.0's pumpCaER
(betse/science/sim_toolbox.py; docs/ER_CALCIUM.md). It deliberately does not imply a two-calcium
SERCA cycle or proton exchange. Maintained ATP, ADP and Pi supply external chemical work. The
plasma membrane's pump evaluates it too (laws/reactions/plasma_calcium.py). The factor of a store's
release is laws/reactions/hill_product_factor.py.
"""

from typing import NamedTuple

import jax.numpy as jnp

from cells.laws.electrochemistry import F, R

MAX_AFFINITY_RT = 80.0


class PumpParameters(NamedTuple):
    capacity_fmol_per_s: object
    km_ca_mM: object
    km_atp_mM: object
    atp_mM: object
    adp_mM: object
    pi_mM: object
    delta_g0_J_per_mol: object


def chemical_drive(p, temperature, *, xp=jnp):
    return p.delta_g0_J_per_mol + R * temperature * (
        xp.log(p.adp_mM) + xp.log(p.pi_mM) - xp.log(p.atp_mM)
    )


def pump_rates(cytosol_mM, er_mM, voltage, temperature, p, availability, *, xp=jnp):
    drive = chemical_drive(p, temperature, xp=xp)
    energy = drive + R * temperature * (xp.log(er_mM) - xp.log(cytosol_mM)) + 2 * F * voltage
    affinity = energy / (R * temperature)
    log_saturation = -xp.logaddexp(0.0, xp.log(p.km_ca_mM) - xp.log(cytosol_mM))
    log_saturation -= xp.logaddexp(0.0, xp.log(p.km_atp_mM) - xp.log(p.atp_mM))
    enabled = (p.capacity_fmol_per_s > 0) & (availability > 0)
    magnitude = xp.exp(
        xp.log(xp.where(enabled, p.capacity_fmol_per_s, 1.0))
        + xp.log(xp.where(enabled, availability, 1.0))
        + log_saturation
        + xp.maximum(affinity, 0.0)
    )
    departure = xp.where(affinity >= 0, xp.expm1(-affinity), -xp.expm1(affinity))
    return xp.where(enabled, magnitude * departure, 0.0), energy, drive
