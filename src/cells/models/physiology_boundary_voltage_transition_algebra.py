"""Incremental capacitive ramp algebra at fixed complete ionic/gate state.

Displacement charge is accumulated from C*dV on actual patch incidences, never
by subtracting absolute solved charges. Work uses the declared linear ramp.
"""

import math
from dataclasses import dataclass

import numpy as np

from cells.models import physiology_boundary_voltage_view as held
from cells.models import surface_tissue
from cells.numerics import surface_field

LAW = "ideal_fixed_inventory_linear_capacitive_ramp@1"
VOLTAGE_ATOL_V = 3e-13
VOLTAGE_RTOL = 3e-10
WORK_ATOL_PJ = 3e-14
WORK_RTOL = 3e-10


@dataclass(frozen=True, slots=True)
class CapacitiveChange:
    delta_boundary_V: object
    delta_membrane_voltage_V: object
    node_charge_change_C: object
    electrode_charge_change_C: object
    externally_supplied_work_pJ: object
    capacitor_energy_change_pJ: float
    work_residual_pJ: float
    endpoint_error_fraction: float
    free_charge_error_fraction: float
    work_error_fraction: float
    valid: bool


def derive(original_layout, before, after):
    """Complete immutable trial; the caller owns admission and parent retention."""
    p = original_layout
    n, o = p.active.size, p.outside_active.size
    delta_b = after.runtime_layout.boundary_V - before.runtime_layout.boundary_V
    delta_phi = surface_field._capacitor_solve(
        np.zeros(n + o), np.r_[np.zeros(n), delta_b], surface_tissue.field_layout(p), xp=np
    )
    delta_vm = np.where(
        p.membrane_active,
        delta_phi[p.membrane_cell] - delta_phi[n + p.membrane_outside],
        0.0,
    )
    terms = [[] for _ in range(n + o)]
    for k in np.flatnonzero(p.membrane_active):
        charge = float(p.membrane_capacitance[k] * delta_vm[k])
        terms[p.membrane_cell[k]].append(charge)
        terms[n + p.membrane_outside[k]].append(-charge)
    node = np.asarray([math.fsum(row) for row in terms])
    dq = np.where(p.reservoir, node[n:], 0.0)
    work = np.asarray(
        [
            1e12 * math.fsum((float(start), 0.5 * float(delta))) * float(charge)
            for start, delta, charge in zip(
                before.runtime_layout.boundary_V, delta_b, dq, strict=True
            )
        ]
    )
    vm0, vm1 = before.field.rates.membrane_voltage_V, after.field.rates.membrane_voltage_V
    energy = math.fsum(
        0.5e12 * float(capacitance) * float(delta) * math.fsum((2 * float(start), float(delta)))
        for capacitance, delta, start in zip(p.membrane_capacitance, delta_vm, vm0, strict=True)
    )
    residual = math.fsum((energy, *(-float(value) for value in work)))
    voltage_budget = VOLTAGE_ATOL_V + VOLTAGE_RTOL * abs(vm1)
    endpoint_error = float(np.max(abs((vm1 - vm0) - delta_vm) / voltage_budget, initial=0))
    required = p.field_active & ~np.r_[np.zeros(n, dtype=bool), p.reservoir]
    gross = np.asarray([math.fsum(abs(value) for value in row) for row in terms])
    budget = surface_field.CHARGE_ATOL_C + surface_field.CHARGE_RTOL * gross
    charge_error = float(np.max(np.where(required, abs(node) / budget, 0.0), initial=0))
    work_budget = WORK_ATOL_PJ + WORK_RTOL * math.fsum(
        (abs(energy), *(abs(float(v)) for v in work))
    )
    work_error = abs(residual) / work_budget
    numbers = (
        delta_b,
        delta_vm,
        node,
        dq,
        work,
        energy,
        residual,
        endpoint_error,
        charge_error,
        work_error,
    )
    valid = all(np.isfinite(value).all() for value in numbers)
    valid = valid and max(endpoint_error, charge_error, work_error) <= 1
    arrays = [held.ordinary._freeze(value) for value in (delta_b, delta_vm, node, dq, work)]
    return CapacitiveChange(
        *arrays, energy, residual, endpoint_error, charge_error, work_error, bool(valid)
    )


def cumulative(segments, outside_capacity):
    """Compensated owner sums over every segment, retaining cancellation history."""
    charge = np.asarray(
        [
            math.fsum(float(row.change.electrode_charge_change_C[i]) for row in segments)
            for i in range(outside_capacity)
        ]
    )
    work = np.asarray(
        [
            math.fsum(float(row.change.externally_supplied_work_pJ[i]) for row in segments)
            for i in range(outside_capacity)
        ]
    )
    energy = math.fsum(row.change.capacitor_energy_change_pJ for row in segments)
    return held.ordinary._freeze(charge), held.ordinary._freeze(work), energy
