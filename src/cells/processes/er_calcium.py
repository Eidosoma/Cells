"""Positive-domain BETSE 1.5 ER pump and instantaneous calcium release laws.

The source pump transports one Ca per formal turnover and uses a numeric mM
metabolic quotient. This identity deliberately does not imply a two-Ca SERCA
cycle or proton exchange. Maintained ATP/ADP/Pi supply external chemical work.
"""

from typing import NamedTuple

import jax.numpy as jnp

from cells.processes.electrochemistry import F, R

PUMP_LAW = "betse_1_5_er_calcium_pump_positive@1"
RELEASE_LAW = "betse_1_5_er_calcium_release@1"
METABOLISM = "betse_1_5_maintained_mM_quotient@1"
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


def release_open(ca_mM, activation_mM, activation_n, inhibition_mM, inhibition_n, *, xp=jnp):
    log_ca = xp.log(ca_mM)
    return xp.exp(
        -xp.logaddexp(0.0, activation_n * (xp.log(activation_mM) - log_ca))
        - xp.logaddexp(0.0, inhibition_n * (log_ca - xp.log(inhibition_mM)))
    )
