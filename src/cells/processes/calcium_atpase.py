"""Positive-domain plasma-membrane Ca-ATPase: one Ca out per formal cycle.

Neutral identity for the equations of the existing Cells law
``plasma_calcium.PUMP_LAW``, evaluated by that same kernel
(``plasma_calcium.pump_rates``); its module cites the source law. Positive
cycles move one divalent Ca from the cytosol to the outside and hydrolyse one
ATP from maintained ATP/ADP/Pi pools. Saturation is in cytosolic Ca and ATP;
the thermodynamic factor is (1 - exp(affinity)) with

    affinity RT = drive - mu_Ca,   mu_Ca = RT ln(ci/co) + 2 F V   (V inside - outside).

The standard hydrolysis energy is declared, like nak_atp_mass_action_positive@1,
against a 1 M standard state; the kernel's numeric-mM quotient receives it as
delta_g0 - RT ln(1000), so both ATPases of one model use the same convention.
Species roles, geometry, inventories and ledgers belong to the composing model.
Supply neutral padding BEFORE this law and reject invalid trials with
domain_valid; there is no concentration floor, clipping or state repair.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.processes import er_calcium, plasma_calcium
from cells.processes.electrochemistry import F, R
from cells.processes.kinetic_pump import TEMPERATURE_DOMAIN_K, STANDARD_STATE_mM

LAW_ID = "ca_atp_mass_action_positive@1"
CALCIUM_PER_CYCLE = -1  # Inward-positive stoichiometry of the transported Ca.
VALENCE = 2
MAX_ABS_AFFINITY_OVER_RT = er_calcium.MAX_AFFINITY_RT
MAX_ABS_VOLTAGE_V = plasma_calcium.MAX_VOLTAGE


class Parameters(NamedTuple):
    """Numeric pytree; every leaf broadcasts over [..., membrane_slot].

    Capacity is fmol cycles/s; pools and Km are mM; delta_g0 is J/mol cycles at
    a 1 M standard state. All fields must be explicitly provided.
    """

    capacity_fmol_s: Any
    atp_mM: Any
    adp_mM: Any
    pi_mM: Any
    km_ca_mM: Any
    km_atp_mM: Any
    delta_g0_J_mol: Any


class Rates(NamedTuple):
    cycles_fmol_s: Any
    cycle_free_energy_J_mol: Any
    chemical_drive_J_mol: Any


def chemical_drive(parameters, temperature_K, *, xp=jnp):
    """Free energy of forward hydrolysis with the explicit 1 M standard state."""
    p = parameters
    return p.delta_g0_J_mol + R * temperature_K * (
        xp.log(p.adp_mM) + xp.log(p.pi_mM) - xp.log(p.atp_mM) - xp.log(STANDARD_STATE_mM)
    )


def kernel_parameters(parameters, temperature_K, *, xp=jnp):
    """The same pools in the existing kernel's numeric-mM convention."""
    p = parameters
    return er_calcium.PumpParameters(
        p.capacity_fmol_s,
        p.km_ca_mM,
        p.km_atp_mM,
        p.atp_mM,
        p.adp_mM,
        p.pi_mM,
        p.delta_g0_J_mol - R * temperature_K * xp.log(STANDARD_STATE_mM),
    )


def kinetics(
    ca_inside_mM, ca_outside_mM, voltage_V, temperature_K, parameters, availability, *, xp=jnp
):
    """Signed cycles (positive extrudes Ca), cycle free energy and chemical drive.

    This unchecked pure kernel expects the declared domain. A zero capacity or
    availability is an exact zero rate, not permission for invalid substrates.
    """
    cycles, energy, _ = plasma_calcium.pump_rates(
        ca_inside_mM,
        ca_outside_mM,
        voltage_V,
        temperature_K,
        kernel_parameters(parameters, temperature_K, xp=xp),
        availability,
        xp=xp,
    )
    return Rates(cycles, energy, chemical_drive(parameters, temperature_K, xp=xp))


def domain_valid(
    ca_inside_mM, ca_outside_mM, voltage_V, temperature_K, parameters, availability, *, xp=jnp
):
    """Per-route validity predicate; neutral arithmetic does not repair a trial."""
    p = parameters

    def positive(value):
        return xp.isfinite(value) & (value > 0)

    valid = positive(ca_inside_mM) & positive(ca_outside_mM)
    safe = [xp.where(positive(v), v, 1.0) for v in (ca_inside_mM, ca_outside_mM)]
    for value in p[1:-1]:
        valid = valid & positive(value)
    pools = [xp.where(positive(v), v, 1.0) for v in p[1:-1]]
    valid = valid & xp.isfinite(p.delta_g0_J_mol)
    delta = xp.where(xp.isfinite(p.delta_g0_J_mol), p.delta_g0_J_mol, 0.0)
    temperature_ok = (
        xp.isfinite(temperature_K)
        & (temperature_K >= TEMPERATURE_DOMAIN_K[0])
        & (temperature_K <= TEMPERATURE_DOMAIN_K[1])
    )
    rt = R * xp.where(temperature_ok, temperature_K, 298.15)
    valid = valid & temperature_ok
    valid = valid & xp.isfinite(p.capacity_fmol_s) & (p.capacity_fmol_s >= 0)
    valid = valid & xp.isfinite(availability) & (availability >= 0) & (availability <= 1)
    voltage_ok = xp.isfinite(voltage_V) & (xp.abs(voltage_V) <= MAX_ABS_VOLTAGE_V)
    valid = valid & voltage_ok
    voltage = xp.where(voltage_ok, voltage_V, 0.0)
    atp, adp, pi = pools[0], pools[1], pools[2]
    affinity = (
        delta / rt
        + xp.log(adp)
        + xp.log(pi)
        - xp.log(atp)
        - xp.log(STANDARD_STATE_mM)
        + xp.log(safe[1])
        - xp.log(safe[0])
        - VALENCE * F * voltage / rt
    )
    return valid & xp.isfinite(affinity) & (xp.abs(affinity) <= MAX_ABS_AFFINITY_OVER_RT)
