"""Emulator variants and the membrane laws whose constants they choose.

The BETSE-order emulator reproduces BETSE 1.5.0's discrete update so that Cells
results can be attributed against plain-BETSE references. Two choices are
static per run, so jit compiles them as constants:

* the physical constants: Cells' CODATA F and R (the qualified behaviour) or
  BETSE's rounded F = 96485 C/mol and R = 8.314 J/(mol K)
  (betse/science/parameters.py, v1.5.0);
* the qualified envelope: grid-site bound and whether a Kv1p5 population (whose
  m/h panel is fixed at 298.15 K) may be present;
* optional model differences (``MODEL_DIFFERENCES``), each one deliberate difference
  of Cells' own physics from BETSE's order, switched on alone to size it for a
  difference budget. BETSE's order has none of them.

The laws below are the arithmetic of cells.processes.electrochemistry
(electrochemical_potential, ghk_leak), cells.coupling.selective.selective_flux,
cells.processes.kinetic_pump (chemical_drive, kinetics, domain_valid) and the
plasma-membrane Ca-ATPase kernel cells.processes.plasma_calcium.pump_rates with F
and R passed explicitly. With CODATA constants they are the same operations in the
same order as those engine laws; tests/unit/test_betse_emulator_laws.py checks
bitwise equality, so the qualified variant is unchanged by the move out of the engine.
"""

from typing import NamedTuple

import jax.numpy as jnp

from cells.processes import electrochemistry, kinetic_pump
from cells.processes.electrochemistry import MOL_PER_FMOL, bernoulli


class Variant(NamedTuple):
    """Static emulator choices (hashable; pass to jitted code by closure or as static)."""

    name: str
    faraday_C_mol: float
    gas_J_mol_K: float
    max_grid_sites: int
    kv1p5_population: bool
    ecm_drift_off: bool = False
    compact_ecm_faces: bool = False
    gate_once: bool = False
    no_membrane_lag: bool = False
    cells_calcium_law: bool = False


# Model differences an emulator run may switch on (sizes, not a Cells model):
MODEL_DIFFERENCES = {
    # No extracellular electromigration: bounds the effect of Cells' resolved capacitor
    # field replacing BETSE's screened, smoothed exterior potential (the drift it drives).
    "ecm_drift_off": ("ecm_drift_off",),
    # Conservative compact faces between neighbouring grid squares (BETSE's arithmetic-mean
    # coefficients at each face, face-centred field), the boundary ring held: Cells'
    # finite-volume exterior instead of BETSE's 2-delta-wide central divergence. Explicit
    # Euler with compact faces needs a smaller step than BETSE's 10 ms INIT step.
    "compact_ecm_faces": ("compact_ecm_faces",),
    # Physical-time junction gate (once per step for every ion) and no membrane
    # concentration lag (membranes see the bulk cell concentration).
    "gate_once_no_lag": ("gate_once", "no_membrane_lag"),
    # Cells' plasma-membrane Ca-ATPase law (cells.processes.calcium_atpase, with Cells'
    # constants and the 1 M standard energy deltaGATP + R T ln(1000) that the adapter maps)
    # in place of BETSE's pumpCaATP, evaluated at BETSE's point in the update.
    "cells_calcium_pump_law": ("cells_calcium_law",),
}


# Registered compatibility configs: CODATA constants, <= 256 grid sites, Kv1p5 at 298.15 K.
QUALIFIED = Variant("qualified", electrochemistry.F, electrochemistry.R, 256, True)
BETSE_F_C_MOL = 96485.0
BETSE_R_J_MOL_K = 8.314
# BETSE default world (headless_core): 600-625 ECM sites and no channel population.
DEFAULT_WORLD_MAX_GRID_SITES = 1024


def default_world(constants, differences=()):
    """Channel-free default-world variant with BETSE's or Cells' constants.

    ``differences`` names MODEL_DIFFERENCES to switch on (none: BETSE's order).
    """
    values = {
        "betse": (BETSE_F_C_MOL, BETSE_R_J_MOL_K),
        "codata": (electrochemistry.F, electrochemistry.R),
    }[constants]
    flags = {flag: True for name in differences for flag in MODEL_DIFFERENCES[name]}
    name = "_".join([f"default_world_{constants}", *sorted(differences)])
    return Variant(name, *values, DEFAULT_WORLD_MAX_GRID_SITES, False, **flags)


def electrochemical_potential(ci, co, voltage, valence, temperature, variant, *, xp=jnp):
    f, r = variant.faraday_C_mol, variant.gas_J_mol_K
    return r * temperature * (xp.log(ci) - xp.log(co)) + valence * f * voltage


def ghk_leak(
    ci, co, voltage, valence, temperature, area, permeability, multiplier, variant, *, xp=jnp
):
    x = valence * variant.faraday_C_mol * voltage / (variant.gas_J_mol_K * temperature)
    return (
        area
        * permeability
        * multiplier
        / MOL_PER_FMOL
        * (co * bernoulli(x, xp=xp) - ci * bernoulli(-x, xp=xp))
    )


def selective_flux(
    c_from,
    c_to,
    delta_voltage,
    valence,
    temperature,
    area,
    permeability,
    residual,
    gate,
    multiplier,
    variant,
    *,
    xp=jnp,
):
    x = valence * variant.faraday_C_mol * delta_voltage / (variant.gas_J_mol_K * temperature)
    available = multiplier * (residual + (1 - residual) * gate)
    return (
        area
        * permeability
        * available
        / MOL_PER_FMOL
        * (c_from * bernoulli(-x, xp=xp) - c_to * bernoulli(x, xp=xp))
    )


def chemical_drive(parameters, temperature_K, variant, *, xp=jnp):
    p = parameters
    return p.delta_g0_J_mol + variant.gas_J_mol_K * temperature_K * (
        xp.log(p.adp_mM)
        + xp.log(p.pi_mM)
        - xp.log(p.atp_mM)
        - xp.log(kinetic_pump.STANDARD_STATE_mM)
    )


def pump_kinetics(
    na_inside_mM,
    k_outside_mM,
    mu_na,
    mu_k,
    temperature_K,
    parameters,
    availability,
    variant,
    *,
    xp=jnp,
):
    """Signed 3 Na out / 2 K in cycles (fmol/s); kinetic_pump.kinetics with explicit R."""
    p = parameters
    drive = chemical_drive(p, temperature_K, variant, xp=xp)
    energy = drive + kinetic_pump.SODIUM_PER_CYCLE * mu_na + kinetic_pump.POTASSIUM_PER_CYCLE * mu_k
    a = energy / (variant.gas_J_mol_K * temperature_K)
    log_saturation = (
        -xp.logaddexp(0.0, 3 * (xp.log(p.km_na_mM) - xp.log(na_inside_mM)))
        - xp.logaddexp(0.0, 2 * (xp.log(p.km_k_mM) - xp.log(k_outside_mM)))
        - xp.logaddexp(0.0, xp.log(p.km_atp_mM) - xp.log(p.atp_mM))
    )
    enabled = (p.capacity_fmol_s > 0) & (availability > 0)
    safe_capacity = xp.where(enabled, p.capacity_fmol_s, 1.0)
    safe_availability = xp.where(enabled, availability, 1.0)
    magnitude = xp.exp(
        xp.log(safe_capacity) + xp.log(safe_availability) + log_saturation + xp.maximum(a, 0.0)
    )
    departure = xp.where(a >= 0, xp.expm1(-a), -xp.expm1(a))
    cycles = xp.where(enabled, magnitude * departure, 0.0)
    return kinetic_pump.Rates(cycles, energy, drive)


def pump_domain_valid(
    na_inside_mM,
    k_outside_mM,
    mu_na,
    mu_k,
    temperature_K,
    parameters,
    availability,
    variant,
    *,
    xp=jnp,
):
    """kinetic_pump.domain_valid with explicit R."""
    p = parameters

    def positive(value):
        return xp.isfinite(value) & (value > 0)

    valid = positive(na_inside_mM) & positive(k_outside_mM)
    fields = [p.capacity_fmol_s]
    for value in p[1:-1]:
        ok = positive(value)
        valid = valid & ok
        fields.append(xp.where(ok, value, 1.0))
    valid = valid & xp.isfinite(p.delta_g0_J_mol)
    fields.append(xp.where(xp.isfinite(p.delta_g0_J_mol), p.delta_g0_J_mol, 0.0))
    safe = kinetic_pump.Parameters(*fields)
    low, high = kinetic_pump.TEMPERATURE_DOMAIN_K
    temperature_ok = xp.isfinite(temperature_K) & (temperature_K >= low) & (temperature_K <= high)
    rt = variant.gas_J_mol_K * xp.where(temperature_ok, temperature_K, 298.15)
    valid = valid & temperature_ok
    valid = valid & xp.isfinite(p.capacity_fmol_s) & (p.capacity_fmol_s >= 0)
    valid = valid & xp.isfinite(availability) & (availability >= 0) & (availability <= 1)
    potentials = []
    for mu in (mu_na, mu_k):
        scaled = mu / rt
        ok = xp.isfinite(scaled) & (xp.abs(scaled) <= kinetic_pump.MAX_ABS_ION_POTENTIAL_OVER_RT)
        valid = valid & ok
        potentials.append(xp.where(ok, scaled, 0.0))
    affinity = (
        safe.delta_g0_J_mol / rt
        + xp.log(safe.adp_mM)
        + xp.log(safe.pi_mM)
        - xp.log(safe.atp_mM)
        - xp.log(kinetic_pump.STANDARD_STATE_mM)
        + kinetic_pump.SODIUM_PER_CYCLE * potentials[0]
        + kinetic_pump.POTASSIUM_PER_CYCLE * potentials[1]
    )
    return (
        valid & xp.isfinite(affinity) & (xp.abs(affinity) <= kinetic_pump.MAX_ABS_AFFINITY_OVER_RT)
    )


def calcium_pump_kinetics(
    ca_inside_mM,
    ca_outside_mM,
    voltage_V,
    temperature_K,
    parameters,
    availability,
    variant,
    *,
    xp=jnp,
):
    """Signed one-Ca extrusion cycles (fmol/s), cycle energy and drive (J/mol).

    plasma_calcium.pump_rates (er_calcium.pump_rates at -Vm) with explicit F and R:
    ``parameters`` is an er_calcium.PumpParameters whose standard energy uses the
    numeric-mM quotient of BETSE's pumpCaATP (sim_toolbox.py), Vm is inside minus
    outside. Equals BETSE's -alpha_Ca * frwd * (1 - Q/Keq) per unit area.
    """
    p = parameters
    r, f = variant.gas_J_mol_K, variant.faraday_C_mol
    drive = p.delta_g0_J_per_mol + r * temperature_K * (
        xp.log(p.adp_mM) + xp.log(p.pi_mM) - xp.log(p.atp_mM)
    )
    voltage = -voltage_V
    energy = (
        drive + r * temperature_K * (xp.log(ca_outside_mM) - xp.log(ca_inside_mM)) + 2 * f * voltage
    )
    affinity = energy / (r * temperature_K)
    log_saturation = -xp.logaddexp(0.0, xp.log(p.km_ca_mM) - xp.log(ca_inside_mM))
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
