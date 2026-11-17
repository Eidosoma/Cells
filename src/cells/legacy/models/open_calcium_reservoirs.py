"""Complete static ideal-reservoir closure for owned calcium/plasma rates.

The finite-exterior parents intentionally add PMCA/NCX/Ca-channel rates without
reservoir maintenance. This separate law retains every reaction/gate/pump rate
and history, then closes the actual open material/electrode/work budgets. It
does not relax or invoke the closed parents' conserved-pool admission bounds.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp

from cells.models import surface_tissue as passive
from cells.numerics import surface_field as electrical
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

LAW_ID = "complete_owned_calcium_static_reservoir_material_electrode_work@1"


class Values(NamedTuple):
    field: object
    derivative: object
    additional_reservoir_supply_fmol_s: object
    reservoir_chemical_power_pJ_s: object
    valid: object


def close(
    state, p, raw, *, internal_chemical_power_pJ_s=0.0, external_chemical_power_pJ_s=0.0, xp=jnp
):
    """Close actual full rates, with explicit energy-owner contributions.

    ``internal_chemical_power`` is finite ATP/ADP/Pi free-energy power (zero for
    maintained-fuel calcium). ``external_chemical_power`` is maintained pump
    work for calcium, or the declared regeneration-port work for finite fuel.
    All ER/plasma dissipation and capacitor power already belong to raw.field.
    """
    field, derivative = raw.field, raw.derivative
    reservoir = p.reservoir & p.outside_active
    additional = -xp.where(reservoir, derivative.extracellular_amount_increment, 0.0)
    outside = derivative.extracellular_amount_increment + additional
    supply = derivative.reservoir_supplied + additional
    qdot = CHARGE_PER_FMOL * xp.sum(
        p.valence * xp.concatenate((derivative.amount_increment, outside), axis=1), axis=0
    )
    potential_rate = electrical._capacitor_solve(
        qdot, xp.zeros_like(qdot), passive.field_layout(p), xp=xp
    )
    n = p.active.size
    electrode = xp.where(reservoir, (p.field_capacitor_matrix @ potential_rate)[n:], 0.0)
    membrane_rate = xp.where(
        p.membrane_active,
        potential_rate[p.membrane_cell] - potential_rate[n + p.membrane_outside],
        0.0,
    )
    concentration = xp.where(
        p.outside_active,
        (p.extracellular_amount_reference + state.extracellular_amount_increment)
        / p.extracellular_volume,
        1.0,
    )
    chemical_mu = R * p.temperature * xp.log(concentration)
    chemical_work = 1e-3 * xp.sum(chemical_mu * supply, axis=0)
    electrochemical_work = 1e-3 * xp.sum(
        (chemical_mu + p.valence * F * p.boundary_V) * supply, axis=0
    )
    electrode_work = 1e12 * p.boundary_V * electrode
    chemical = field.chemical_energy_rate_pJ_s + 1e-3 * xp.sum(chemical_mu * additional)
    energy = (
        chemical
        + field.capacitor_energy_rate_pJ_s
        + internal_chemical_power_pJ_s
        + field.dissipation_pJ_s
        - external_chemical_power_pJ_s
        - xp.sum(electrochemical_work)
        - xp.sum(electrode_work)
    )
    result = derivative._replace(
        extracellular_amount_increment=outside,
        reservoir_supplied=supply,
        electrode_charge_transferred_C=electrode,
        reservoir_work_pJ=electrochemical_work,
        electrode_work_pJ=electrode_work,
    )
    valid = raw.valid & xp.asarray(True)
    for value in (*result, additional, chemical_work, energy, membrane_rate, potential_rate):
        valid &= xp.all(xp.isfinite(value))
    updated = field._replace(
        rates=field.rates._replace(
            outside_rate_fmol_s=outside, reservoir_supply_fmol_s=supply, valid=valid
        ),
        electrode_current_A=electrode,
        reservoir_supply_charge_A=CHARGE_PER_FMOL * xp.sum(p.valence * supply, axis=0),
        membrane_voltage_rate_V_s=membrane_rate,
        chemical_energy_rate_pJ_s=chemical,
        reservoir_power_pJ_s=xp.sum(electrochemical_work),
        electrode_power_pJ_s=xp.sum(electrode_work),
        energy_balance_pJ_s=energy,
        converged=valid,
    )
    # A world without ideal reservoirs uses the original finite-exterior
    # results exactly, including its summation order and all derivative arrays.
    open_world = xp.any(reservoir)
    updated = jax.tree_util.tree_map(
        lambda new, old: xp.where(open_world, new, old), updated, field
    )
    result = type(derivative)(
        *(xp.where(open_world, new, old) for new, old in zip(result, derivative, strict=True))
    )
    return Values(
        updated, result, additional, chemical_work, xp.where(open_world, valid, raw.valid)
    )
