"""Pinned AST-extracted scalar laws; no production imports or integration."""

import math
from decimal import Decimal, localcontext

import numpy as np

F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23


def decimal_flux(ca, cb, dv, z, temperature, area, diffusion, length, opening, constants):
    """Independent high-precision constant-field formula, positive A -> B, fmol/s."""
    with localcontext() as context:
        context.prec = 70
        ca, cb, dv, z, temperature, area, diffusion, length, opening = (
            Decimal(str(x)) for x in (ca, cb, dv, z, temperature, area, diffusion, length, opening)
        )
        x = z * Decimal(str(constants["F"])) * dv / (Decimal(str(constants["R"])) * temperature)
        if x == 0:
            driving = ca - cb
        else:
            exponential = x.exp()
            driving = x * (ca * exponential - cb) / (exponential - 1)
        return float(area * diffusion / length * opening * driving * Decimal("1e15"))


def bernoulli(x):
    if abs(x) < 1e-05:
        return 1 - x / 2 + x * x / 12 - x**4 / 720 + x**6 / 30240
    return x / math.expm1(x)


def logarithmic_mean(left, right):
    """Scalar positive log mean and log ratio, stable for adjacent floats.

    Near equality, neither subtracting logs nor forming left/right before
    taking its log preserves the relative concentration difference. Use log1p
    on that difference; unlike the production atanh/series implementation,
    this reference evaluates the mean directly from the stable log ratio.
    """
    difference = left - right
    if difference == 0:
        return (left, 0.0)
    relative = difference / right
    log = math.log1p(relative) if abs(relative) < 0.5 else math.log(left) - math.log(right)
    return (difference / log, log)


def transport(raw, cell_potential, outside_potential):
    p, ci, co = (raw["layout"], np.asarray(raw["ci"]), np.asarray(raw["co"]))
    dci, dco = (np.zeros_like(ci), np.zeros_like(co))
    result = {}
    for prefix in ("membrane", "junction", "face"):
        active = p[prefix + "_active"]
        if prefix == "membrane":
            sender, receiver = (p["membrane_cell"], p["membrane_outside"])
            a, b, va, vb, da, db = (ci, co, cell_potential, outside_potential, dci, dco)
        elif prefix == "junction":
            sender, receiver = (p["junction_sender"], p["junction_receiver"])
            a, b, va, vb, da, db = (ci, ci, cell_potential, cell_potential, dci, dci)
        else:
            sender, receiver = (p["face_sender"], p["face_receiver"])
            a, b, va, vb, da, db = (co, co, outside_potential, outside_potential, dco, dco)
        dv, flux, mu = (
            np.zeros(len(active)),
            np.zeros((len(ci), len(active))),
            np.zeros((len(ci), len(active))),
        )
        for k, enabled in enumerate(active):
            if not enabled:
                continue
            i, j = (sender[k], receiver[k])
            dv[k] = va[i] - vb[j]
            for s, (z,) in enumerate(p["valence"]):
                left, right = (float(a[s, i]), float(b[s, j]))
                mean, log = logarithmic_mean(left, right)
                chemical = R * p["temperature"] * log
                mu[s, k] = chemical + z * F * dv[k]
                if prefix == "face":
                    rate = (
                        p["face_factor"][s][k]
                        * mean
                        * mu[s, k]
                        / (R * p["temperature"])
                        * 1000000000000000.0
                    )
                else:
                    rate = decimal_flux(
                        left,
                        right,
                        dv[k],
                        z,
                        p["temperature"],
                        p[prefix + "_area"][k],
                        p[prefix + "_permeability"][s][k],
                        1.0,
                        raw[prefix + "_open"][k],
                        {"F": F, "R": R},
                    )
                flux[s, k] = rate
                da[s, i] -= rate
                db[s, j] += rate
        result.update(
            {
                prefix + "_voltage_V": dv,
                prefix + "_flux_fmol_s": flux,
                prefix + "_delta_mu_J_mol": mu,
                prefix + "_current_A": 1e-15 * F * (np.asarray(p["valence"]).T @ flux)[0],
                prefix + "_dissipation_pJ_s": np.sum(flux * mu, axis=0) * 0.001,
            }
        )
    result.update(
        cell_rate_fmol_s=dci,
        outside_rate_fmol_s=np.where(p["reservoir"], 0, dco),
        reservoir_supply_fmol_s=np.where(p["reservoir"], -dco, 0),
    )
    return result


def accounting(raw, cell_potential, outside_potential, values):
    ci, co, p = (np.asarray(raw["ci"]), np.asarray(raw["co"]), raw["layout"])
    cell, outside, supply = (
        np.asarray(values[k])
        for k in ("cell_rate_fmol_s", "outside_rate_fmol_s", "reservoir_supply_fmol_s")
    )
    mass = cell.sum(axis=1) + outside.sum(axis=1) - supply.sum(axis=1)
    mu_cell = R * p["temperature"] * np.log(ci) + F * np.asarray(p["valence"]) * cell_potential
    mu_out = R * p["temperature"] * np.log(co) + F * np.asarray(p["valence"]) * outside_potential
    free = 0.001 * (np.sum(mu_cell * cell) + np.sum(mu_out * outside))
    supplied = 0.001 * np.sum(mu_out * supply)
    dissipation = sum(
        (float(np.sum(values[k + "_dissipation_pJ_s"])) for k in ("membrane", "face", "junction"))
    )
    return {
        "material_residual_fmol_s": mass.tolist(),
        "electrochemical_port_power_residual_pJ_s": float(free + dissipation - supplied),
    }
