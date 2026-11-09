"""Accepted-row checks of the resolved pump family as compiled array functions.

surface_pump.check_values tests every accepted row on the host with NumPy:
domain validity, the material, charge, energy and work ledgers against their
bounds, and nonnegative, nondecreasing dissipation. row_checks evaluates the
same tests for one row with jax.numpy, so a compiled window can reduce them per
world on the device and transfer only summaries. The ledger residuals are
surface_tissue.balances with the family's pump terms, term for term and in the
same order; bounds and failure messages come from surface_pump and are shared
with the host check. Residuals are rounding quantities (sums that cancel), so
device and host values agree to rounding, not bitwise; tests compare them.
"""

from typing import NamedTuple

import jax.numpy as jnp

from cells.models import surface_tissue as tissue
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import scatter
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

# Dissipation integrals may not fall below this, nor decrease by more per row.
DISSIPATION_ATOL_PJ = 1e-12


class CheckConstants(NamedTuple):
    """Per-world check inputs taken from the definition (host arrays)."""

    material_atol: object  # [species] fmol, execution.material_balance_atol_fmol
    energy_rtol: object  # scalar, the solver's declared energy tolerance


def tissue_balances(state, membrane_total, p):
    """surface_tissue.balances (free cytosol, no coupled store) with jax.numpy.

    membrane_total is the membrane transfer including pump stoichiometry, as the
    pump family passes it to the host balances.
    """
    di, do = state.amount_increment, state.extracellular_amount_increment
    hm, hj, hf = membrane_total, state.junction_transferred, state.face_transferred
    local = (
        di
        + scatter(hm, di, (p.membrane_cell,))
        + scatter(hj, di, (p.junction_sender,))
        - scatter(hj, di, (p.junction_receiver,))
    )
    outside = (
        do
        - scatter(hm, do, (p.membrane_outside,))
        + scatter(hf, do, (p.face_sender,))
        - scatter(hf, do, (p.face_receiver,))
        - state.reservoir_supplied
    )
    total = di.sum(axis=1) + do.sum(axis=1) - state.reservoir_supplied.sum(axis=1)
    q, cap, dv = tissue.capacitor_change(state, p, xp=jnp)
    n = p.active.size
    initial_q = jnp.concatenate((p.initial_cell_charge_C, p.initial_outside_charge_C))
    boundary = jnp.concatenate((jnp.zeros(n), p.boundary_V))
    base = field._capacitor_solve(initial_q, boundary, tissue.field_layout(p), xp=jnp)
    required = p.field_active & ~jnp.concatenate((jnp.zeros(n, dtype=bool), p.reservoir))
    charge = jnp.where(required, p.field_capacitor_matrix @ base - initial_q + cap - q, 0.0)
    electrode = state.electrode_charge_transferred_C - jnp.where(p.reservoir, cap[n:], 0.0)
    supply_charge = CHARGE_PER_FMOL * jnp.sum(p.valence * state.reservoir_supplied)
    global_charge = jnp.sum(state.electrode_charge_transferred_C) + supply_charge
    chemical = 0.0
    for delta, anchor, volume, mask in (
        (di, p.amount_reference, p.volume, p.active),
        (do, p.extracellular_amount_reference, p.extracellular_volume, p.outside_active),
    ):
        a = jnp.where(mask, anchor, 1.0)
        chemical += (
            1e-3
            * R
            * p.temperature
            * jnp.sum(delta * (jnp.log(a / volume) - 1) + (a + delta) * jnp.log1p(delta / a))
        )
    electric = 0.5e12 * jnp.sum(
        p.membrane_capacitance * dv * (2 * p.initial_membrane_voltage_V + dv)
    )
    dissipated = sum(
        jnp.sum(getattr(state, k + "_dissipated_energy_pJ"))
        for k in ("membrane", "junction", "face")
    )
    energy = (
        chemical
        + electric
        + dissipated
        - jnp.sum(state.reservoir_work_pJ)
        - jnp.sum(state.electrode_work_pJ)
    )
    co = jnp.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0)
    mu = R * p.temperature * jnp.log(co) + p.valence * F * p.boundary_V
    reservoir_work = state.reservoir_work_pJ - 1e-3 * jnp.sum(mu * state.reservoir_supplied, axis=0)
    electrode_work = (
        state.electrode_work_pJ - 1e12 * p.boundary_V * state.electrode_charge_transferred_C
    )
    return dict(
        local=local,
        outside=outside,
        total=total,
        charge=charge,
        electrode=electrode,
        global_charge=global_charge,
        energy=energy,
        reservoir_work=reservoir_work,
        electrode_work=electrode_work,
    )


def row_checks(
    previous, row, p, constants, steps, *, domain_valid, balances, limits, magnitudes, dissipation
):
    """(failed [checks], values [diagnostics]) for one accepted row and its predecessor.

    Checks, in host order: domain, each ledger of balances(), then dissipation
    (negative, or decreasing since previous). Values are the host diagnostics:
    each ledger's max |residual|, then the energy residual relative to its flows
    and the global-charge residual relative to its bound. steps is the row's
    accepted-step count (running-ledger rounding allowance). Nothing is skipped
    for an invalid row; a failed check marks the row, never repairs it.
    """
    failed = [~domain_valid(row, p, p.active, xp=jnp)]
    b = balances(row, p)
    flows, bounds = limits(
        row,
        p,
        constants.material_atol,
        constants.energy_rtol,
        steps=steps,
        magnitudes=magnitudes(row, p, xp=jnp),
        xp=jnp,
    )
    values = []
    for value, bound in zip(b.values(), bounds, strict=True):
        magnitude = jnp.abs(value)
        failed.append(~jnp.all(jnp.isfinite(value)) | jnp.any(magnitude > bound))
        values.append(jnp.max(magnitude, initial=0.0))
    values.append(jnp.abs(b["energy"]) / jnp.maximum(flows, tissue.ENERGY_ATOL_PJ))
    values.append(jnp.abs(b["global_charge"]) / bounds[5])
    decreasing = jnp.asarray(False)
    for name in dissipation:
        value = getattr(row, name)
        decreasing |= jnp.min(value, initial=0.0) < -DISSIPATION_ATOL_PJ
        decreasing |= jnp.min(value - getattr(previous, name), initial=0.0) < -DISSIPATION_ATOL_PJ
    failed.append(decreasing)
    return jnp.stack(failed), jnp.stack(values)
