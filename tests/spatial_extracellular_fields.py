"""NUM-010 independent outside-node field/flux equations and shared physical guards.

The independent path never calls SPEC-009's potential, face or GHK routines.
These functions evaluate a state, not a trajectory; the audit can import them
without importing SciPy, JAX, production code or an ODE integrator.
"""

import math

import numpy as np

from tests import spatial_extracellular_numerical_data as data

F, R, A, QF = data.F, data.R, data.A, data.QF


class DomainViolation(ValueError):
    pass


def state_domain(case, state):
    value = np.asarray(state)
    if value.shape != (case.size,) or not np.all(np.isfinite(value)):
        raise DomainViolation("Nonfinite or incomplete spatial state")
    p, g = case.layout.split(value), case.g
    amount = g.initial + p["amount"]
    concentration = amount / g.volume[:, None]
    if not np.all(np.isfinite(concentration)) or np.any(amount <= 0) or np.any(concentration <= 0):
        raise DomainViolation("Nonpositive or nonfinite spatial inventory/concentration")
    charge = g.initial_charge + QF * (p["amount"] @ g.z)
    if np.max(np.abs(g.p.T @ charge), initial=0) > 1e-20:
        raise DomainViolation("Capacitance-component charge constraint violated")
    voltage = np.asarray(
        [
            m["initial_voltage_V"] + QF / m["capacitance_F"] * math.fsum(g.z * p["amount"][u])
            for m, (u, _) in zip(case.raw["world"]["membranes"], g.membrane_pairs, strict=True)
        ]
    )
    max_x = float(np.max(np.abs(voltage[:, None] * g.z * F / (R * g.temperature)), initial=0))
    if not math.isfinite(max_x) or max_x > 50:
        raise DomainViolation("Membrane dimensionless voltage outside domain")
    return p, amount, concentration, charge, voltage, max_x


def finish(
    case,
    state,
    control,
    phi,
    membrane_flux,
    face_flux,
    membrane_mu,
    face_mu,
    diffusion_current,
    conductance,
):
    p, amount, concentration, charge, voltage, max_x = state_domain(case, state)
    g = case.g
    actual_voltage = g.bm.T @ phi
    cap_residual = g.bm @ (g.capacitance * actual_voltage) - charge
    face_current = QF * (face_flux @ g.z)
    current_residual = g.p.T @ g.bf @ face_current
    current_scale = max(
        float(np.max(np.abs(diffusion_current), initial=0)),
        float(np.max(np.abs(conductance * (g.bf.T @ phi)), initial=0)),
    )
    current_normalized = float(np.max(np.abs(current_residual), initial=0)) / (
        1e-23 + 2e-12 * current_scale
    )
    if np.max(np.abs(cap_residual), initial=0) > 1e-20 or current_normalized > 1:
        raise DomainViolation("Physical capacitor/current residual exceeds limit")
    out = {key: np.zeros(shape) for key, shape in case.layout.shapes.items()}
    out["membrane_transfer"][:] = membrane_flux
    out["face_transfer"][:] = face_flux
    out["membrane_dissipation"][:] = 1e-3 * np.sum(membrane_flux * membrane_mu, axis=-1)
    out["face_dissipation"][:] = 1e-3 * np.sum(face_flux * face_mu, axis=-1)
    # Literal once-owned contributions; no dependent inventory or charge projection.
    for pairs, flux in ((g.membrane_pairs, membrane_flux), (g.face_pairs, face_flux)):
        for (u, v), row in zip(pairs, flux, strict=True):
            out["amount"][u] -= row
            out["amount"][v] += row
    rate = case.layout.pack(out)
    if not np.all(np.isfinite(rate)) or not np.all(np.isfinite(phi)):
        raise DomainViolation("Nonfinite physical field or derivative")
    return rate, {
        "potential_V": phi,
        "membrane_voltage_V": actual_voltage,
        "minimum_amount_fmol": float(np.min(amount)),
        "max_membrane_abs_x": max_x,
        "max_component_charge_C": float(np.max(np.abs(g.p.T @ charge), initial=0)),
        "max_capacitor_residual_C": float(np.max(np.abs(cap_residual), initial=0)),
        "max_current_residual_A": float(np.max(np.abs(current_residual), initial=0)),
        "current_scale_A": current_scale,
        "current_normalized": current_normalized,
        "face_current_A": face_current,
    }


def independent(case, control, state):
    """Direct outside Kirchhoff assembly, symmetric log mean and hyperbolic GHK."""
    _, _, c, _, voltage, _ = state_domain(case, state)
    g, rt = case.g, R * case.g.temperature
    outside_index = {node: i for i, node in enumerate(case.outside)}
    matrix = np.zeros((len(case.outside), len(case.outside)))
    rhs = np.zeros(len(case.outside))
    weights = np.zeros((len(g.face_pairs), len(g.z)))
    logs = np.zeros_like(weights)
    diffusion_current, conductance = np.zeros(len(g.face_pairs)), np.zeros(len(g.face_pairs))
    for e, (u, v) in enumerate(g.face_pairs):
        for s in range(len(g.z)):
            left, right = float(c[u, s]), float(c[v, s])
            if left == right:
                mean, log = left, 0.0
            else:
                ratio = (left - right) / (left + right)
                log = (
                    2 * math.atanh(ratio) if abs(ratio) < 0.5 else math.log(left) - math.log(right)
                )
                mean = (left - right) / log
            weights[e, s], logs[e, s] = g.face_factor[e, s] * mean, log
        conductance[e] = F * F / rt * math.fsum(g.z * g.z * weights[e])
        diffusion_current[e] = F * math.fsum(g.z * weights[e] * logs[e])
        a, b = outside_index[u], outside_index[v]
        matrix[a, a] += conductance[e]
        matrix[b, b] += conductance[e]
        matrix[a, b] -= conductance[e]
        matrix[b, a] -= conductance[e]
        rhs[a] -= diffusion_current[e]
        rhs[b] += diffusion_current[e]
    if (
        not np.all(np.isfinite(conductance))
        or np.any(conductance <= 0)
        or not np.all(np.isfinite(diffusion_current))
    ):
        raise DomainViolation("Invalid field coefficients")
    phi = np.zeros(len(g.ids))
    if len(case.outside) > 1:
        scale = float(np.max(np.abs(matrix)))
        if not math.isfinite(scale) or scale <= 0:
            raise DomainViolation("Singular conducting field graph")
        try:
            phi[list(case.outside[1:])] = np.linalg.solve(matrix[1:, 1:] / scale, rhs[1:] / scale)
        except np.linalg.LinAlgError as exc:
            raise DomainViolation("Singular conducting field graph") from exc
    for j, (u, v) in enumerate(g.membrane_pairs):
        phi[u] = phi[v] + voltage[j]
    phi -= phi[-1]
    membrane_mu = np.zeros((len(g.membrane_pairs), len(g.z)))
    membrane_flux = np.zeros_like(membrane_mu)
    for e, (u, v) in enumerate(g.membrane_pairs):
        x = g.z * F * voltage[e] / rt
        factor = np.ones_like(x)
        mask = x != 0
        factor[mask] = x[mask] / (2 * np.tanh(x[mask] / 2))
        membrane_flux[e] = (
            g.membrane_area[e]
            * g.permeability[e]
            * control.availability[e]
            / A
            * ((c[u] - c[v]) * factor + (c[u] + c[v]) * x / 2)
        )
        membrane_mu[e] = rt * (np.log(c[u]) - np.log(c[v])) + g.z * F * voltage[e]
    face_mu = rt * logs + F * (g.bf.T @ phi)[:, None] * g.z
    face_flux = weights / A * (face_mu / rt)
    return finish(
        case,
        state,
        control,
        phi,
        membrane_flux,
        face_flux,
        membrane_mu,
        face_mu,
        diffusion_current,
        conductance,
    )


def candidate(case, control, state):
    """Frozen SPEC-009 component solve and Bernoulli membrane law, with owned controls."""
    p, _, c, _, _, _ = state_domain(case, state)
    g, rt = case.g, R * case.g.temperature
    try:
        value = data.spec.evaluate(g, p["amount"])
        _, logs, diffusion_current, conductance = data.spec.bulk_terms(g, c)
    except ValueError as exc:
        raise DomainViolation(str(exc)) from exc
    phi = value["potential_V"]
    membrane_flux = value["membrane_flux_fmol_per_s"] * np.asarray(control.availability)[:, None]
    membrane_mu = np.asarray(
        [
            rt * (np.log(c[u]) - np.log(c[v])) + F * g.z * (phi[u] - phi[v])
            for u, v in g.membrane_pairs
        ]
    ).reshape(-1, len(g.z))
    face_mu = rt * logs + F * (g.bf.T @ phi)[:, None] * g.z
    result, diagnostic = finish(
        case,
        state,
        control,
        phi,
        membrane_flux,
        value["face_flux_fmol_per_s"],
        membrane_mu,
        face_mu,
        diffusion_current,
        conductance,
    )
    # Independently scatter through the frozen incidence matrices, rather than
    # the reference branch's literal endpoint accumulation.
    case.layout.split(result)["amount"][:] = (
        -g.bm @ membrane_flux - g.bf @ value["face_flux_fmol_per_s"]
    )
    return result, diagnostic
