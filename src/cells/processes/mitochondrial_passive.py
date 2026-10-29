"""Continuous physical form of BETSE mitochondrial constant-field transport.

Unlike the separately versioned native discrete component, this law uses the
current charge-consistent voltage, SI constants and exact neutral/zero limits.
It adds neither respiration nor ATP production. Positive transfer is inward
from cytosol to mitochondrion; voltage is mitochondrion minus cytosol.
"""

from typing import NamedTuple

import jax.numpy as jnp

from cells.processes.betse_mitochondria import LAW_ID as SOURCE_LAW
from cells.processes.electrochemistry import electrochemical_potential, ghk_leak

LAW_ID = "betse_mitochondrial_passive_continuous_si@1"
MAX_VOLTAGE_V = 0.2


class Rates(NamedTuple):
    transferred_fmol_s: object
    transfer_energy_J_mol: object
    dissipated_power_pJ_s: object


def rates(
    cytosol_mM,
    mitochondrial_mM,
    voltage_V,
    valence,
    temperature_K,
    area_m2,
    diffusivity_m2_s,
    thickness_m,
    availability,
    *,
    xp=jnp,
):
    """Unchecked law on positive concentrations; no active-state regularization."""
    energy = electrochemical_potential(
        mitochondrial_mM, cytosol_mM, voltage_V, valence, temperature_K, xp=xp
    )
    flux = ghk_leak(
        mitochondrial_mM,
        cytosol_mM,
        voltage_V,
        valence,
        temperature_K,
        area_m2,
        diffusivity_m2_s / thickness_m,
        availability,
        xp=xp,
    )
    return Rates(flux, energy, -1e-3 * flux * energy)


__all__ = ["LAW_ID", "SOURCE_LAW", "MAX_VOLTAGE_V", "Rates", "rates"]
