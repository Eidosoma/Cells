"""Charge-constrained membrane surfaces with coupled return currents and baths.

Capacitance-connected nodes share an undetermined voltage offset. The charge
equations determine their relative potentials; Kirchhoff current balance fixes
the floating offsets. Reservoirs impose absolute outside voltages and expose
their electrode charge/current/work instead of hiding electrical sources.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.numerics import surface_transport as surface
from cells.numerics.extracellular_field import logmean
from cells.numerics.tissue_field import _bernoulli_derivative
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

LAW_ID = "resolved_capacitor_components_current_continuity@1"
SOLVER_ID = "capacitive_reduction_gauged_damped_newton@1"
CURRENT_ATOL_A = 1e-23
CURRENT_RTOL = 2e-12
CHARGE_ATOL_C = 3e-25
CHARGE_RTOL = 2e-12
NEWTON_TARGET = 0.01
MAX_NODES = 256


class Layout(NamedTuple):
    surface: surface.Layout
    gauge_mask: object
    active: object
    fixed: object
    capacitor_matrix: object
    capacitor_scale: object
    capacitor_solve_matrix: object
    floating_basis: object
    offset_free: object
    face_incidence: object
    junction_incidence: object


class Values(NamedTuple):
    potential_V: object
    membrane_charge_C: object
    capacitor_node_charge_C: object
    charge_residual_C: object
    charge_normalized: object
    component_current_residual_A: object
    current_normalized: object
    electrode_charge_C: object
    electrode_current_A: object
    reservoir_supply_charge_A: object
    membrane_voltage_rate_V_s: object
    capacitor_energy_pJ: object
    capacitor_energy_rate_pJ_s: object
    chemical_energy_rate_pJ_s: object
    reservoir_power_pJ_s: object
    electrode_power_pJ_s: object
    dissipation_pJ_s: object
    energy_balance_pJ_s: object
    rates: surface.Rates
    iterations: object
    converged: object


def bind(layout, gauge_mask):
    """Host-only capacitance topology, fixed gauge and fail-closed connectivity.

    A reservoir is both a concentration bath and a voltage clamp in this law.
    Closed graphs require exactly one outside gauge. All floating components
    need a charged outside-face path to a clamp/gauge even if junctions close.
    """
    p = surface.validate_layout(layout)
    n, o = p.cell_active.size, p.outside_active.size
    size = n + o
    if size > MAX_NODES:
        raise ValueError("Resolved field exceeds the declared bounded dense node limit")
    gauge = np.asarray(gauge_mask)
    if gauge.shape != (o,) or gauge.dtype != np.bool_:
        raise ValueError("Resolved field gauge must be an outside boolean mask")
    if gauge.sum() != (0 if np.any(p.reservoir) else 1) or np.any(gauge & ~p.outside_active):
        raise ValueError("Use reservoir voltage clamps or exactly one active outside gauge")
    active = np.r_[p.cell_active, p.outside_active]
    parent = list(range(size))

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i

    def join(i, j):
        parent[root(j)] = root(i)

    capacitor = np.zeros((size, size))
    for k in np.flatnonzero(p.membrane_active):
        i, j = int(p.membrane_cell[k]), n + int(p.membrane_outside[k])
        c = p.membrane_capacitance[k]
        join(i, j)
        capacitor[i, i] += c
        capacitor[j, j] += c
        capacitor[i, j] -= c
        capacitor[j, i] -= c
    groups = {}
    for i in np.flatnonzero(active):
        groups.setdefault(root(int(i)), []).append(int(i))
    reservoirs = set((n + np.flatnonzero(p.reservoir)).tolist())
    gauge_nodes = set((n + np.flatnonzero(gauge)).tolist())
    fixed = ~active.copy()
    fixed[list(reservoirs)] = True
    floating, free = [], []
    for members in groups.values():
        if reservoirs.intersection(members):
            continue
        choices = gauge_nodes.intersection(members)
        representative = next(iter(choices)) if choices else min(i for i in members if i >= n)
        fixed[representative] = True
        floating.append(np.isin(np.arange(size), members).astype(float))
        free.append(not bool(choices))
    basis = np.asarray(floating).reshape((-1, size)).T
    offset_free = np.asarray(free, dtype=bool)
    # Connectivity of the reduced offsets through guaranteed outside conductance.
    reached = {root(i) for i in reservoirs | gauge_nodes}
    edges = []
    conductive = np.any((p.valence != 0) & (p.face_factor > 0), axis=0)
    for k in np.flatnonzero(p.face_active & conductive):
        edges.append((root(n + int(p.face_sender[k])), root(n + int(p.face_receiver[k]))))
    for _ in groups:
        for i, j in edges:
            if i in reached or j in reached:
                reached.update((i, j))
    if reached != set(groups):
        raise ValueError(
            "Floating capacitor components require an outside return path to a clamp/gauge"
        )
    scale = np.max(np.abs(capacitor))
    solve_matrix = np.where((~fixed)[:, None] & (~fixed)[None, :], capacitor / scale, 0.0)
    solve_matrix += np.diag(fixed.astype(float))
    # A singular capacitance reduction is an invalid layout, never regularized.
    np.linalg.cholesky(solve_matrix)
    return Layout(
        p,
        gauge,
        active,
        fixed,
        capacitor,
        np.asarray(scale),
        solve_matrix,
        basis,
        offset_free,
        (basis[n + p.face_sender] - basis[n + p.face_receiver]).T,
        (basis[p.junction_sender] - basis[p.junction_receiver]).T,
    )


def _capacitor_solve(charge, boundary, p, *, xp):
    rhs = xp.where(~p.fixed, (charge - p.capacitor_matrix @ boundary) / p.capacitor_scale, 0.0)
    return xp.linalg.solve(p.capacitor_solve_matrix, rhs) + boundary


def _offset_solve(matrix, rhs, p, *, xp):
    if p.offset_free.size == 0:
        return xp.zeros_like(rhs)
    scale = xp.max(xp.abs(matrix), initial=0.0)
    scale = xp.where(scale > 0, scale, 1.0)  # Only the fixed gauge can remain.
    free = p.offset_free
    reduced = xp.where(free[:, None] & free[None, :], matrix / scale, 0.0)
    reduced += xp.diag((~free).astype(matrix.dtype))
    return xp.linalg.solve(reduced, xp.where(free, rhs / scale, 0.0))


def solve(
    ci,
    co,
    cell_charge_C,
    outside_charge_C,
    membrane_open,
    junction_open,
    boundary_V,
    p,
    *,
    xp=jnp,
    max_iterations=16,
    max_backtracks=12,
):
    """Recompute one world's field and transport from same-stage state/controls.

    Charge inputs include fixed backgrounds and use coulombs. boundary_V is
    nonzero only at reservoir/gauge owners; boundary voltages are held constant
    when reporting instantaneous capacitor/electrode energy and charge rates.
    All capacitor constraints (including floating representatives) are checked.
    Invalid/incompatible states or exhausted roots return converged=False.
    """
    if type(max_iterations) is not int or max_iterations < 0:
        raise ValueError("Require a nonnegative Newton bound")
    if type(max_backtracks) is not int or max_backtracks < 1:
        raise ValueError("Require a positive backtrack bound")
    s = p.surface
    n, o = s.cell_active.size, s.outside_active.size
    if cell_charge_C.shape != (n,) or outside_charge_C.shape != (o,) or boundary_V.shape != (o,):
        raise ValueError("Resolved field charge/boundary shape disagrees with geometry")
    charge = xp.concatenate((cell_charge_C, outside_charge_C))
    clamps = s.reservoir | p.gauge_mask
    boundary = xp.concatenate((xp.zeros_like(cell_charge_C), xp.where(clamps, boundary_V, 0.0)))
    base = _capacitor_solve(charge, boundary, p, xp=xp)
    required = p.active & ~xp.concatenate((xp.zeros(n, dtype=bool), s.reservoir))
    domain = (
        xp.all(xp.isfinite(charge))
        & xp.all(xp.isfinite(boundary_V))
        & xp.all(xp.where(p.active, True, charge == 0))
        & xp.all(xp.where(clamps, True, boundary_V == 0))
    )
    rt, z = R * s.temperature, s.valence
    mean, log = logmean(
        xp.where(s.face_active, co[:, s.face_sender], 1.0),
        xp.where(s.face_active, co[:, s.face_receiver], 1.0),
        xp=xp,
    )
    weight = s.face_factor * mean
    conductance = F**2 / rt * xp.sum(z * z * weight, axis=0)
    dv = base[n + s.face_sender] - base[n + s.face_receiver]
    face0 = F * xp.sum(z * weight * log, axis=0) + conductance * dv
    matrix = (p.face_incidence * conductance) @ p.face_incidence.T
    initial_offset = _offset_solve(matrix, -p.face_incidence @ face0, p, xp=xp)

    def evaluate(offset):
        phi = base + p.floating_basis @ offset
        rates = surface.transport(ci, co, phi[:n], phi[n:], membrane_open, junction_open, s, xp=xp)
        residual = (
            p.face_incidence @ rates.face_current_A
            + p.junction_incidence @ rates.junction_current_A
        )
        scale = xp.maximum(
            xp.max(xp.abs(rates.face_current_A), initial=0.0),
            xp.max(xp.abs(rates.junction_current_A), initial=0.0),
        )
        norm = xp.max(xp.abs(residual), initial=0.0) / (CURRENT_ATOL_A + CURRENT_RTOL * scale)
        x = z * F * rates.junction_voltage_V / rt
        a, b = ci[:, s.junction_sender], ci[:, s.junction_receiver]
        slope = (
            F**2
            / rt
            * s.junction_area
            * junction_open
            * xp.sum(
                z
                * z
                * s.junction_permeability
                * (-a * _bernoulli_derivative(-x, xp=xp) - b * _bernoulli_derivative(x, xp=xp)),
                axis=0,
            )
        )
        slope = xp.where(s.junction_active, slope, 0.0)
        valid = domain & rates.valid & xp.isfinite(norm) & xp.all(xp.isfinite(phi))
        valid &= xp.all(xp.isfinite(slope) & (slope >= 0))
        return phi, rates, residual, norm, slope, valid

    def keep_going(state):
        count, _, norm, valid = state
        return (count < max_iterations) & (norm > NEWTON_TARGET) & valid

    def iteration(state):
        count, offset, _, _ = state
        _, _, residual, norm, slope, _ = evaluate(offset)
        jac = matrix + (p.junction_incidence * slope) @ p.junction_incidence.T
        delta = _offset_solve(jac, -residual, p, xp=xp)
        before = xp.max(xp.abs(residual), initial=0.0)

        def retry(search):
            step, _, _, accepted = search
            return (step < max_backtracks) & ~accepted

        def trial(search):
            step, _, _, _ = search
            proposal = offset + delta * (0.5**step)
            _, _, residual, norm, _, valid = evaluate(proposal)
            accepted = valid & (
                (xp.max(xp.abs(residual), initial=0.0) < before) | (norm <= NEWTON_TARGET)
            )
            return step + 1, proposal, norm, accepted

        search = (xp.asarray(0, dtype=xp.int32), offset, norm, xp.asarray(False))
        if xp is np:
            while retry(search):
                search = trial(search)
        else:
            search = jax.lax.while_loop(retry, trial, search)
        _, proposal, norm, accepted = search
        return count + 1, xp.where(accepted, proposal, offset), norm, accepted

    _, _, _, norm, _, valid = evaluate(initial_offset)
    state = (xp.asarray(0, dtype=xp.int32), initial_offset, norm, valid)
    if xp is np:
        while keep_going(state):
            state = iteration(state)
    else:
        state = jax.lax.while_loop(keep_going, iteration, state)
    count, offset, _, accepted = state
    phi, rates, current_residual, norm, _, valid = evaluate(offset)
    patch_charge = s.membrane_capacitance * rates.membrane_voltage_V
    cap_charge = p.capacitor_matrix @ phi
    residual = xp.where(required, cap_charge - charge, 0.0)
    charge_scale = xp.maximum(xp.abs(charge), xp.abs(cap_charge))
    charge_norm = xp.max(xp.abs(residual) / (CHARGE_ATOL_C + CHARGE_RTOL * charge_scale))
    electrode_charge = xp.where(s.reservoir, cap_charge[n:] - outside_charge_C, 0.0)
    amount_rates = xp.concatenate((rates.cell_rate_fmol_s, rates.outside_rate_fmol_s), axis=1)
    ionic_rate = CHARGE_PER_FMOL * xp.sum(z * amount_rates, axis=0)
    derivative = _capacitor_solve(ionic_rate, xp.zeros_like(phi), p, xp=xp)
    vm_rate = xp.where(
        s.membrane_active, derivative[s.membrane_cell] - derivative[n + s.membrane_outside], 0.0
    )
    electrode_current = xp.where(s.reservoir, (p.capacitor_matrix @ derivative)[n:], 0.0)
    supply_charge = CHARGE_PER_FMOL * xp.sum(z * rates.reservoir_supply_fmol_s, axis=0)
    chemical_rate = (
        1e-3
        * rt
        * (
            xp.sum(xp.log(ci) * rates.cell_rate_fmol_s)
            + xp.sum(xp.log(co) * rates.outside_rate_fmol_s)
        )
    )
    capacitor_energy = 0.5e12 * xp.sum(patch_charge * rates.membrane_voltage_V)
    capacitor_rate = 1e12 * xp.sum(patch_charge * vm_rate)
    reservoir_power = 1e-3 * xp.sum(
        (rt * xp.log(co) + z * F * phi[n:]) * rates.reservoir_supply_fmol_s
    )
    electrode_power = 1e12 * xp.sum(phi[n:] * electrode_current)
    dissipation = (
        xp.sum(rates.membrane_dissipation_pJ_s)
        + xp.sum(rates.junction_dissipation_pJ_s)
        + xp.sum(rates.face_dissipation_pJ_s)
    )
    energy_balance = (
        chemical_rate + capacitor_rate + dissipation - reservoir_power - electrode_power
    )
    physical = (
        phi,
        patch_charge,
        cap_charge,
        residual,
        charge_norm,
        current_residual,
        norm,
        electrode_charge,
        electrode_current,
        supply_charge,
        vm_rate,
        capacitor_energy,
        capacitor_rate,
        chemical_rate,
        reservoir_power,
        electrode_power,
        dissipation,
        energy_balance,
    )
    for value in physical:
        valid &= xp.all(xp.isfinite(value))
    converged = valid & accepted & (norm <= NEWTON_TARGET) & (charge_norm <= 1.0)
    return Values(*physical, rates, count, converged)
