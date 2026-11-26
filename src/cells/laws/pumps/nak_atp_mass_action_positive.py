"""cells.cycle.nak_atp_mass_action_positive@1: the Na/K-ATPase on maintained pools, the law and its
declaration on @3.

Positive-domain 3 Na out / 2 K in ATPase with maintained metabolic pools: SPEC-010 / D111's
mass-action cycle, whose signed cycle rate carries its thermodynamic factor from the cycle's free
energy (affinity), so a cycle never runs against its drive. Species roles, geometry, inventories,
masks and ledgers belong to the composing model. Supply neutral inactive padding BEFORE this law
and reject invalid trials using domain_valid. There is no concentration floor, clipping or state
repair. See docs/KINETIC_PUMP_PROCESS.md for units, evidence and remaining integration. A pump law
of cells.model.resolved_pump_tissue@3 (cells.cycle_law@1), registered by the law registry's loader
(docs/CORE_SEAMS_DESIGN.md §8.2). Moved from laws/pumps/kinetic_pump.py, which re-imports these
names.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.laws.electrochemistry import R
from cells.modules import CycleLaw

LAW_ID = "cells.cycle.nak_atp_mass_action_positive@1"
SODIUM_PER_CYCLE = -3
POTASSIUM_PER_CYCLE = 2
TEMPERATURE_DOMAIN_K = (200.0, 400.0)
MAX_ABS_AFFINITY_OVER_RT = 80.0
MAX_ABS_ION_POTENTIAL_OVER_RT = 1600.0
STANDARD_STATE_mM = 1000.0


class Parameters(NamedTuple):
    """Numeric pytree; every leaf broadcasts over [..., membrane_slot].

    Capacity is fmol *cycles*/s, not Na flux or mol/m²/s. The caller derives it
    from area and density if those are the input parameters. Pools and Km are
    mM; delta_g0 is J/mol cycles. All fields must be explicitly provided.
    """

    capacity_fmol_s: Any
    atp_mM: Any
    adp_mM: Any
    pi_mM: Any
    km_na_mM: Any
    km_k_mM: Any
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


def kinetics(
    na_inside_mM, k_outside_mM, mu_na, mu_k, temperature_K, parameters, availability, *, xp=jnp
):
    """Signed cycles and energies, with inward electrochemical potentials in J/mol.

    Arrays are broadcastable local routes; species have already been resolved
    by the composing model. Na/K must each have valence +1. The model applies
    -3/+2 to these cycles once and derives current from the same ion transfer.

    This unchecked pure kernel expects the declared domain. A zero capacity or
    availability is an exact zero rate, not permission for invalid substrates.
    Positive-interior gradients, including affinity zero, are well-defined;
    parameter gradients at disabled-route boundaries are not part of this API.
    """
    p = parameters
    drive = chemical_drive(p, temperature_K, xp=xp)
    energy = drive + SODIUM_PER_CYCLE * mu_na + POTASSIUM_PER_CYCLE * mu_k
    a = energy / (R * temperature_K)
    # Log saturation avoids overflowing positive concentration/Km ratios.
    log_saturation = (
        -xp.logaddexp(0.0, 3 * (xp.log(p.km_na_mM) - xp.log(na_inside_mM)))
        - xp.logaddexp(0.0, 2 * (xp.log(p.km_k_mM) - xp.log(k_outside_mM)))
        - xp.logaddexp(0.0, xp.log(p.km_atp_mM) - xp.log(p.atp_mM))
    )
    enabled = (p.capacity_fmol_s > 0) & (availability > 0)
    safe_capacity = xp.where(enabled, p.capacity_fmol_s, 1.0)
    safe_availability = xp.where(enabled, availability, 1.0)
    # Combine the exponent before exp: a tiny saturation times a large capacity
    # can be representable even when saturation alone underflows. The positive
    # branch uses exp(a)*expm1(-a); both branches retain the derivative at stall.
    magnitude = xp.exp(
        xp.log(safe_capacity) + xp.log(safe_availability) + log_saturation + xp.maximum(a, 0.0)
    )
    departure = xp.where(a >= 0, xp.expm1(-a), -xp.expm1(a))
    cycles = xp.where(enabled, magnitude * departure, 0.0)
    return Rates(cycles, energy, drive)


def domain_valid(
    na_inside_mM, k_outside_mM, mu_na, mu_k, temperature_K, parameters, availability, *, xp=jnp
):
    """Per-route validity predicate; neutral arithmetic does not repair a trial.

    The composing solver must additionally check finite RHS/output values and
    the full physical cell/bath domain. This predicate alone does not certify a
    concentration-to-potential mapping, a timestep, or inactive padding.
    """
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
    safe = Parameters(*fields)
    temperature_ok = (
        xp.isfinite(temperature_K)
        & (temperature_K >= TEMPERATURE_DOMAIN_K[0])
        & (temperature_K <= TEMPERATURE_DOMAIN_K[1])
    )
    rt = R * xp.where(temperature_ok, temperature_K, 298.15)
    valid = valid & temperature_ok
    valid = valid & xp.isfinite(p.capacity_fmol_s) & (p.capacity_fmol_s >= 0)
    valid = valid & xp.isfinite(availability) & (availability >= 0) & (availability <= 1)
    potentials = []
    for mu in (mu_na, mu_k):
        scaled = mu / rt
        ok = xp.isfinite(scaled) & (xp.abs(scaled) <= MAX_ABS_ION_POTENTIAL_OVER_RT)
        valid = valid & ok
        potentials.append(xp.where(ok, scaled, 0.0))
    affinity = (
        safe.delta_g0_J_mol / rt
        + xp.log(safe.adp_mM)
        + xp.log(safe.pi_mM)
        - xp.log(safe.atp_mM)
        - xp.log(STANDARD_STATE_mM)
        + SODIUM_PER_CYCLE * potentials[0]
        + POTASSIUM_PER_CYCLE * potentials[1]
    )
    return valid & xp.isfinite(affinity) & (xp.abs(affinity) <= MAX_ABS_AFFINITY_OVER_RT)


# Today's pumps run on maintained pools (definitions/kinetic_pump_spec.METABOLISM_ID).
MAINTAINED_FUEL_ID = "cells.fuel_kind.maintained_chemical_reservoirs@1"
LAW = CycleLaw(
    LAW_ID,
    (("sodium", SODIUM_PER_CYCLE), ("potassium", POTASSIUM_PER_CYCLE)),
    (MAINTAINED_FUEL_ID,),
    kinetics,
    domain_valid,
    host="cells.model.resolved_pump_tissue@3",
)
