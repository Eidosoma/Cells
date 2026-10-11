"""Independent scalar GHK and reduced current-balance root; no Cells/JAX imports."""

import math

import numpy as np
from scipy.optimize import brentq, root

F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23


def bernoulli(x):
    if abs(x) < 1e-5:
        return 1 - x / 2 + x * x / 12 - x**4 / 720 + x**6 / 30240
    return x / math.expm1(x)


def evaluate(data, potential):
    p = data["layout"]
    z = [row[0] for row in p["valence"]]
    rt = R * p["temperature"]
    ci, co = np.asarray(data["ci"]), np.asarray(data["co"])
    face = np.zeros((len(z), len(p["face_active"])))
    junction = np.zeros((len(z), len(p["junction_active"])))
    face_mu, junction_mu = np.zeros_like(face), np.zeros_like(junction)
    residual = np.zeros(len(p["extracellular_active"]))
    cell_phi = np.asarray(data["membrane_voltage"]) + potential[p["cell_outside"]]
    cell_phi = np.where(p["cell_active"], cell_phi, 0.0)
    for j, active in enumerate(p["face_active"]):
        if not active:
            continue
        a, b = p["face_senders"][j], p["face_receivers"][j]
        for s, charge in enumerate(z):
            left, right = co[s, a], co[s, b]
            log = math.log(left) - math.log(right)
            mean = left if left == right else (left - right) / log
            mu = rt * log + charge * F * (potential[a] - potential[b])
            face_mu[s, j] = mu
            face[s, j] = p["face_factor"][s][j] * mean * mu / (rt * 1e-15)
            current = charge * F * 1e-15 * face[s, j]
            residual[a] += current
            residual[b] -= current
    for j, active in enumerate(p["junction_active"]):
        if not active:
            continue
        a, b = p["junction_senders"][j], p["junction_receivers"][j]
        oa, ob = p["cell_outside"][a], p["cell_outside"][b]
        for s, charge in enumerate(z):
            dv = cell_phi[a] - cell_phi[b]
            x = charge * F * dv / rt
            scale = (
                p["junction_area"][j]
                * p["junction_permeability"][s][j]
                * data["gate"][j]
                * data["availability"][j]
                / 1e-15
            )
            junction[s, j] = scale * (ci[s, a] * bernoulli(-x) - ci[s, b] * bernoulli(x))
            junction_mu[s, j] = rt * math.log(ci[s, a] / ci[s, b]) + charge * F * dv
            current = charge * F * 1e-15 * junction[s, j]
            residual[oa] += current
            residual[ob] -= current
    return {
        "potential_V": potential,
        "cell_potential_V": cell_phi,
        "face_flux_fmol_per_s": face,
        "face_delta_mu_J_per_mol": face_mu,
        "face_current_A": F * 1e-15 * np.sum(np.asarray(z)[:, None] * face, axis=0),
        "face_dissipation_rate_pJ_per_s": 1e-3 * np.sum(face * face_mu, axis=0),
        "junction_voltage_V": np.where(
            p["junction_active"],
            cell_phi[p["junction_senders"]] - cell_phi[p["junction_receivers"]],
            0,
        ),
        "junction_flux_fmol_per_s": junction,
        "junction_delta_mu_J_per_mol": junction_mu,
        "junction_current_A": F * 1e-15 * np.sum(np.asarray(z)[:, None] * junction, axis=0),
        "junction_dissipation_rate_pJ_per_s": 1e-3 * np.sum(junction * junction_mu, axis=0),
        "current_residual_A": residual,
    }


def solve(data):
    p = data["layout"]
    potential = np.zeros(len(p["extracellular_active"]))
    free = np.flatnonzero(np.asarray(p["extracellular_active"]) & ~np.asarray(p["gauge_mask"]))

    def residual(values):
        candidate = potential.copy()
        candidate[free] = values
        return evaluate(data, candidate)["current_residual_A"][free] / 1e-12

    if len(free) == 1:
        potential[free] = brentq(lambda v: residual([v])[0], -0.3, 0.3, xtol=5e-16, rtol=1e-14)
    elif len(free):
        solved = root(residual, np.zeros(len(free)), method="hybr", options={"xtol": 1e-11})
        potential[free] = solved.x
    result = evaluate(data, potential)
    scale = max(
        np.max(np.abs(result[k]), initial=0) for k in ("face_current_A", "junction_current_A")
    )
    if (
        not all(np.isfinite(v).all() for v in result.values())
        or np.max(np.abs(result["current_residual_A"])) > 1e-23 + 2e-12 * scale
    ):
        raise ValueError("Independent return-current reference did not converge")
    return result


def power_and_charge_rates(data, values):
    """Independent local capacitor and free-energy derivative, without repairs."""
    p = data["layout"]
    ci, co = np.asarray(data["ci"]), np.asarray(data["co"])
    di, do = np.zeros_like(ci), np.zeros_like(co)
    for j, active in enumerate(p["junction_active"]):
        if active:
            flux = np.asarray(values["junction_flux_fmol_per_s"])[:, j]
            di[:, p["junction_senders"][j]] -= flux
            di[:, p["junction_receivers"][j]] += flux
    for j, active in enumerate(p["face_active"]):
        if active:
            flux = np.asarray(values["face_flux_fmol_per_s"])[:, j]
            do[:, p["face_senders"][j]] -= flux
            do[:, p["face_receivers"][j]] += flux
    z = np.asarray(p["valence"])
    cell_current = F * 1e-15 * np.sum(z * di, axis=0)
    component = F * 1e-15 * np.sum(z * do, axis=0)
    for cell, outside in enumerate(p["cell_outside"]):
        component[outside] += cell_current[cell]
    chemical = 1e-3 * R * p["temperature"] * np.sum(np.log(ci) * di)
    chemical += 1e-3 * R * p["temperature"] * np.sum(np.log(co) * do)
    capacitive = 1e12 * np.dot(np.asarray(data["membrane_voltage"]), cell_current)
    dissipation = sum(
        np.sum(values[key])
        for key in ("junction_dissipation_rate_pJ_per_s", "face_dissipation_rate_pJ_per_s")
    )
    return {
        "material_rate_fmol_per_s": di.sum(axis=1) + do.sum(axis=1),
        "component_charge_rate_A": component,
        "energy_rate_residual_pJ_per_s": chemical + capacitive + dissipation,
    }
