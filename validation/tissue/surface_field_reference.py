"""Independent full-node charge/current equations; no Cells or JAX imports.

The production implementation reduces capacitance components before Newton.
This reference solves a full-node square system with scipy's hybrid root,
using independently discovered topology and scalar transport/current sums.
"""

import math

import numpy as np
from scipy.optimize import root
from scipy.sparse.csgraph import connected_components

from validation.tissue import surface_reference
from validation.tissue.reference import bernoulli

F, R = surface_reference.F, surface_reference.R


def topology(raw):
    p = raw["layout"]
    n, o = len(p["cell_active"]), len(p["outside_active"])
    active = np.r_[p["cell_active"], p["outside_active"]]
    capacitor = np.zeros((n + o, n + o))
    for k, enabled in enumerate(p["membrane_active"]):
        if enabled:
            i, j, c = (
                p["membrane_cell"][k],
                n + p["membrane_outside"][k],
                p["membrane_capacitance"][k],
            )
            for a, b, sign in ((i, i, 1), (j, j, 1), (i, j, -1), (j, i, -1)):
                capacitor[a, b] += sign * c
    _, labels = connected_components(capacitor != 0, directed=False)
    groups = [np.flatnonzero((labels == k) & active) for k in np.unique(labels[active])]
    reservoir = np.r_[np.zeros(n, bool), p["reservoir"]]
    gauge = np.r_[np.zeros(n, bool), raw["gauge_mask"]]
    fixed = ~active | reservoir | gauge
    floating = [members for members in groups if not np.any(reservoir[members])]
    current_rows = {}
    for members in floating:
        if not np.any(gauge[members]):
            # Deliberately choose a cell row when available; production always
            # pins an outside row in its capacitance reduction.
            current_rows[int(members[0])] = members
    return capacitor, active, reservoir, fixed, floating, current_rows


def currents(raw, phi):
    p, ci, co = raw["layout"], np.asarray(raw["ci"]), np.asarray(raw["co"])
    n, z, rt = len(p["cell_active"]), [v[0] for v in p["valence"]], R * p["temperature"]
    divergence = np.zeros(len(phi))
    values = []
    for kind in ("face", "junction"):
        for k, enabled in enumerate(p[kind + "_active"]):
            if not enabled:
                continue
            i, j = p[kind + "_sender"][k], p[kind + "_receiver"][k]
            a, b = (n + i, n + j) if kind == "face" else (i, j)
            dv = phi[a] - phi[b]
            current = 0.0
            for s, valence in enumerate(z):
                if kind == "face":
                    left, right = float(co[s, i]), float(co[s, j])
                    mean, log = surface_reference.logarithmic_mean(left, right)
                    rate_mol = p["face_factor"][s][k] * mean * (log + valence * F * dv / rt)
                else:
                    x = valence * F * dv / rt
                    drive = ci[s, i] * bernoulli(-x) - ci[s, j] * bernoulli(x)
                    rate_mol = (
                        p["junction_area"][k]
                        * p["junction_permeability"][s][k]
                        * raw["junction_open"][k]
                        * drive
                    )
                current += valence * F * rate_mol
            divergence[a] += current
            divergence[b] -= current
            values.append(current)
    return divergence, max(map(abs, values), default=0.0)


def solve(raw):
    p = raw["layout"]
    n = len(p["cell_active"])
    matrix, active, reservoir, fixed, floating, rows = topology(raw)
    charge = np.r_[raw["cell_charge_C"], raw["outside_charge_C"]]
    boundary = np.r_[np.zeros(n), raw["boundary_V"]]
    scale = np.max(np.abs(matrix))

    def equations(phi):
        residual = (matrix @ phi - charge) / scale
        divergence, _ = currents(raw, phi)
        for i, members in rows.items():
            residual[i] = math.fsum(float(divergence[j]) for j in members) / 1e-10
        residual[fixed] = phi[fixed] - boundary[fixed]
        return residual

    answer = root(
        equations, np.asarray(raw["seed_potential_V"]), method="hybr", options={"xtol": 1e-11}
    )
    phi = answer.x
    cap_charge = matrix @ phi
    required = active & ~reservoir
    np.testing.assert_array_less(
        np.abs((cap_charge - charge)[required]),
        3e-25 + 2e-12 * np.maximum(abs(charge[required]), abs(cap_charge[required])),
    )
    divergence, current_scale = currents(raw, phi)
    residual = np.asarray(
        [math.fsum(float(divergence[j]) for j in members) for members in floating]
    )
    assert np.max(abs(residual), initial=0) <= 1e-23 + 2e-12 * current_scale
    np.testing.assert_allclose(phi[fixed], boundary[fixed], rtol=0, atol=3e-13)
    assert np.isfinite(phi).all()
    # Physical residuals determine success, including scipy's near-root stagnation return.
    return phi, {
        "solver_success": bool(answer.success),
        "evaluations": int(answer.nfev),
        "max_charge_residual_C": float(np.max(abs((cap_charge - charge)[required]), initial=0)),
        "max_component_current_residual_A": float(np.max(abs(residual), initial=0)),
    }


def check(raw, values):
    """Reconstruct local charge rates and the open-system energy balance."""
    p = raw["layout"]
    n, o = len(p["cell_active"]), len(p["outside_active"])
    phi = np.asarray(values.potential_V)
    rates = values.rates
    expected_rates = surface_reference.transport(raw, phi[:n], phi[n:])
    capacitor, active, reservoir, _, floating, _ = topology(raw)
    q = np.r_[raw["cell_charge_C"], raw["outside_charge_C"]]
    charge_residual = (capacitor @ phi - q)[active & ~reservoir]
    bounds = 3e-25 + 2e-12 * np.maximum(
        abs((capacitor @ phi)[active & ~reservoir]), abs(q[active & ~reservoir])
    )
    assert np.all(abs(charge_residual) <= bounds)
    node_rate = np.zeros(n + o)
    energy, cap_power = 0.0, 0.0
    for k, enabled in enumerate(p["membrane_active"]):
        if enabled:
            i, j, c = (
                p["membrane_cell"][k],
                n + p["membrane_outside"][k],
                p["membrane_capacitance"][k],
            )
            vm, dvm = phi[i] - phi[j], values.membrane_voltage_rate_V_s[k]
            node_rate[i] += c * dvm
            node_rate[j] -= c * dvm
            energy += 0.5e12 * c * vm * vm
            cap_power += 1e12 * c * vm * dvm
    ionic_rate = (
        F
        * 1e-15
        * (np.asarray(p["valence"]).T @ np.c_[rates.cell_rate_fmol_s, rates.outside_rate_fmol_s])[0]
    )
    local_rate_error = (node_rate - ionic_rate)[active & ~reservoir]
    divergence, current_scale = currents(raw, phi)
    current_bound = 1e-23 + 2e-12 * current_scale
    assert np.max(abs(local_rate_error), initial=0) <= current_bound
    component_residual = [math.fsum(float(divergence[j]) for j in members) for members in floating]
    assert max(map(abs, component_residual), default=0) <= current_bound
    electrode = np.where(p["reservoir"], node_rate[n:], 0.0)
    np.testing.assert_allclose(values.electrode_current_A, electrode, rtol=2e-12, atol=1e-23)
    np.testing.assert_allclose(
        values.electrode_charge_C,
        np.where(p["reservoir"], (capacitor @ phi - q)[n:], 0),
        rtol=2e-12,
        atol=3e-25,
    )
    np.testing.assert_allclose(values.capacitor_energy_pJ, energy, rtol=2e-12, atol=3e-14)
    np.testing.assert_allclose(values.capacitor_energy_rate_pJ_s, cap_power, rtol=2e-12, atol=3e-12)
    material = (
        rates.cell_rate_fmol_s.sum(axis=1)
        + rates.outside_rate_fmol_s.sum(axis=1)
        - rates.reservoir_supply_fmol_s.sum(axis=1)
    )
    np.testing.assert_allclose(material, 0, rtol=0, atol=3e-14)
    np.testing.assert_allclose(
        np.sum(ionic_rate) + np.sum(electrode), 0, rtol=0, atol=current_bound
    )
    chemical = (
        1e-3
        * R
        * p["temperature"]
        * (
            np.sum(np.log(raw["ci"]) * rates.cell_rate_fmol_s)
            + np.sum(np.log(raw["co"]) * rates.outside_rate_fmol_s)
        )
    )
    supplied = 1e-3 * np.sum(
        (R * p["temperature"] * np.log(raw["co"]) + F * np.asarray(p["valence"]) * phi[n:])
        * rates.reservoir_supply_fmol_s
    )
    electrode_power = 1e12 * np.sum(phi[n:] * electrode)
    dissipation = sum(
        np.sum(getattr(rates, k + "_dissipation_pJ_s")) for k in ("membrane", "junction", "face")
    )
    energy_error = chemical + cap_power + dissipation - supplied - electrode_power
    assert abs(energy_error) <= 1e-10
    for name, target in {
        "chemical_energy_rate_pJ_s": chemical,
        "reservoir_power_pJ_s": supplied,
        "electrode_power_pJ_s": electrode_power,
        "dissipation_pJ_s": dissipation,
        "energy_balance_pJ_s": energy_error,
    }.items():
        np.testing.assert_allclose(getattr(values, name), target, rtol=2e-12, atol=3e-12)
    np.testing.assert_allclose(
        values.capacitor_node_charge_C, capacitor @ phi, rtol=2e-12, atol=3e-25
    )
    patch_voltage = phi[p["membrane_cell"]] - phi[n + np.asarray(p["membrane_outside"])]
    np.testing.assert_allclose(
        values.membrane_charge_C,
        np.asarray(p["membrane_capacitance"]) * patch_voltage,
        rtol=2e-12,
        atol=3e-25,
    )
    supply_charge = F * 1e-15 * (np.asarray(p["valence"]).T @ rates.reservoir_supply_fmol_s)[0]
    np.testing.assert_allclose(
        values.reservoir_supply_charge_A, supply_charge, rtol=2e-12, atol=1e-23
    )
    return expected_rates, {
        "max_material_residual_fmol_s": float(np.max(abs(material), initial=0)),
        "max_local_charge_rate_residual_A": float(np.max(abs(local_rate_error), initial=0)),
        "energy_balance_pJ_s": float(energy_error),
        "electrode_power_pJ_s": float(electrode_power),
        "reservoir_power_pJ_s": float(supplied),
    }
