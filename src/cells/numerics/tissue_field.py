"""Same-stage extracellular return currents for junction-connected cell regions.

One capacitor joins each cell to its local extracellular owner. The gauged
nonlinear Kirchhoff equation includes both extracellular face currents and
constant-field junction currents, using absolute intracellular potentials.
There is no stored field, ion/charge repair, or change to existing model IDs.
This numerical component must be qualified before integration into a model.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.coupling.selective import selective_flux
from cells.numerics.extracellular_field import logmean, scatter
from cells.processes.electrochemistry import CHARGE_PER_FMOL, MOL_PER_FMOL, F, R

LAW_ID = "capacitive_regions_ghk_return_current@1"
SOLVER_ID = "gauged_damped_newton@1"
CURRENT_ATOL_A = 1e-23
CURRENT_RTOL = 2e-12
NEWTON_TARGET = 0.01  # Leave margin for independently accumulated local charge balances.
MAX_ABS_X = 50.0


class Layout(NamedTuple):
    temperature: object
    valence: object
    cell_active: object
    cell_outside: object
    extracellular_active: object
    gauge_mask: object
    face_active: object
    face_senders: object
    face_receivers: object
    face_factor: object
    junction_active: object
    junction_senders: object
    junction_receivers: object
    junction_area: object
    junction_permeability: object


class Values(NamedTuple):
    potential_V: object
    cell_potential_V: object
    face_flux_fmol_per_s: object
    face_delta_mu_J_per_mol: object
    face_current_A: object
    face_dissipation_rate_pJ_per_s: object
    junction_voltage_V: object
    junction_flux_fmol_per_s: object
    junction_delta_mu_J_per_mol: object
    junction_current_A: object
    junction_dissipation_rate_pJ_per_s: object
    current_residual_A: object
    current_normalized: object
    iterations: object
    converged: object


def validate_layout(layout):
    """Host-only structural validation before passing immutable arrays to JIT.

    The extracellular conductive graph must stay connected even with all junctions
    blocked. Padding may not introduce an additional gauge or physical connection.
    """
    p = Layout(*(np.asarray(v) for v in layout))
    n, o, f, e = (
        len(getattr(p, k))
        for k in ("cell_active", "extracellular_active", "face_active", "junction_active")
    )
    s = p.valence.shape[0]
    shapes = {
        "temperature": (),
        "valence": (s, 1),
        "cell_active": (n,),
        "cell_outside": (n,),
        "extracellular_active": (o,),
        "gauge_mask": (o,),
        "face_active": (f,),
        "face_senders": (f,),
        "face_receivers": (f,),
        "face_factor": (s, f),
        "junction_active": (e,),
        "junction_senders": (e,),
        "junction_receivers": (e,),
        "junction_area": (e,),
        "junction_permeability": (s, e),
    }
    if not n or not o or not s or any(getattr(p, k).shape != v for k, v in shapes.items()):
        raise ValueError("Invalid tissue field array shapes")
    for key in (
        "cell_active",
        "extracellular_active",
        "gauge_mask",
        "face_active",
        "junction_active",
    ):
        if getattr(p, key).dtype != np.bool_:
            raise ValueError("Tissue field masks must be boolean")
    if not all(np.isfinite(v).all() for v in p):
        raise ValueError("Tissue field layout must be finite")
    if p.temperature <= 0 or not np.any(p.cell_active) or not np.any(p.extracellular_active):
        raise ValueError("Tissue field requires positive temperature and active owners")
    if (
        not np.any(p.valence != 0)
        or np.any(p.valence != np.rint(p.valence))
        or np.any(np.abs(p.valence) > 8)
    ):
        raise ValueError("Require finite integer valences in [-8,8], including a charged species")
    if p.gauge_mask.sum() != 1 or np.any(p.gauge_mask & ~p.extracellular_active):
        raise ValueError("Require exactly one active extracellular gauge")
    for key, limit in (
        ("cell_outside", o),
        ("face_senders", o),
        ("face_receivers", o),
        ("junction_senders", n),
        ("junction_receivers", n),
    ):
        v = getattr(p, key)
        if not np.issubdtype(v.dtype, np.integer) or np.any((v < 0) | (v >= limit)):
            raise ValueError("Invalid tissue field owner index: " + key)
    if np.any(p.cell_active & ~p.extracellular_active[p.cell_outside]):
        raise ValueError("Cell must face an active outside owner")
    for active, src, dst, owners in (
        (p.face_active, p.face_senders, p.face_receivers, p.extracellular_active),
        (p.junction_active, p.junction_senders, p.junction_receivers, p.cell_active),
    ):
        if np.any(active & (~owners[src] | ~owners[dst] | (src == dst))):
            raise ValueError("Active route requires distinct active endpoints")
        edges = [
            tuple(sorted((int(a), int(b)))) for a, b in zip(src[active], dst[active], strict=True)
        ]
        if len(set(edges)) != len(edges):
            raise ValueError("Each physical tissue route must be owned once")
    if (
        np.any(p.face_factor < 0)
        or np.any(p.junction_permeability < 0)
        or np.any(p.junction_area <= 0)
        or np.any(p.face_factor[:, ~p.face_active] != 0)
        or np.any(p.junction_permeability[:, ~p.junction_active] != 0)
    ):
        raise ValueError("Invalid route coefficient or nonzero padding")
    conductive = np.any((p.valence != 0) & (p.face_factor > 0), axis=0)
    if np.any(p.face_active & ~conductive):
        raise ValueError("Each outside face needs positive charged-species conductivity")
    reached = {int(np.flatnonzero(p.gauge_mask)[0])}
    for _ in range(o):
        for a, b in zip(
            p.face_senders[p.face_active], p.face_receivers[p.face_active], strict=True
        ):
            if a in reached or b in reached:
                reached.update((int(a), int(b)))
    if reached != set(np.flatnonzero(p.extracellular_active)):
        raise ValueError("Outside return graph must remain connected when junctions close")
    return p


def _laplacian(weight, src, dst, size, *, xp):
    zero = xp.zeros((size, size), dtype=weight.dtype)
    return (
        scatter(weight, zero, (src, src), xp=xp)
        + scatter(weight, zero, (dst, dst), xp=xp)
        - scatter(weight, zero, (src, dst), xp=xp)
        - scatter(weight, zero, (dst, src), xp=xp)
    )


def _divergence(current, src, dst, size, *, xp):
    zero = xp.zeros(size, dtype=current.dtype)
    return scatter(current, zero, (src,), xp=xp) - scatter(current, zero, (dst,), xp=xp)


def _linear_solve(matrix, rhs, p, *, xp):
    free = p.extracellular_active & ~p.gauge_mask
    scale = xp.max(xp.abs(matrix))
    scale = xp.where(scale > 0, scale, 1.0)  # Single outside owner/no faces.
    reduced = xp.where(free[:, None] & free[None, :], matrix / scale, 0.0)
    reduced = reduced + xp.diag((~free).astype(matrix.dtype))
    return xp.linalg.solve(reduced, xp.where(free, rhs / scale, 0.0))


def _bernoulli_derivative(x, *, xp):
    small = xp.abs(x) < 1e-4
    a, b = xp.where(small, x, 0.0), xp.where(small, 1.0, x)
    em1 = xp.expm1(b)
    return xp.where(small, -0.5 + a / 6 - a**3 / 180, (em1 - b * xp.exp(b)) / (em1 * em1))


def solve(
    ci, co, membrane_voltage, gate, availability, p, *, xp=jnp, max_iterations=16, max_backtracks=12
):
    """Solve one world; explicit vmap may batch independent worlds.

    Inputs are mM (= mol/m3), V, dimensionless gate/availability, and a validated
    Layout. Both masks are multiplicative; blocking a junction never changes its
    intrinsic gate. Failed/domain-invalid roots return converged=False; callers
    must reject them. Residuals include every active node, including the gauge.
    No equation, flux, state, or tolerance is adjusted to obtain convergence.
    """
    if type(max_iterations) is not int or max_iterations < 0:
        raise ValueError("Require a nonnegative Newton iteration bound")
    if type(max_backtracks) is not int or max_backtracks < 1:
        raise ValueError("Require a positive line-search bound")
    s, n, o, e = (
        p.valence.shape[0],
        p.cell_active.size,
        p.extracellular_active.size,
        p.junction_active.size,
    )
    if (
        ci.shape != (s, n)
        or co.shape != (s, o)
        or membrane_voltage.shape != (n,)
        or gate.shape != (e,)
        or availability.shape != (e,)
    ):
        raise ValueError("Tissue field state shape disagrees with layout")
    domain = (
        xp.all(xp.isfinite(ci) & (ci > 0))
        & xp.all(xp.isfinite(co) & (co > 0))
        & xp.all(xp.isfinite(membrane_voltage))
        & xp.all(xp.isfinite(gate) & (gate >= 0) & (gate <= 1))
        & xp.all(xp.isfinite(availability) & (availability >= 0) & (availability <= 1))
    )
    rt, z = R * p.temperature, p.valence
    fs, ft, js, jt = p.face_senders, p.face_receivers, p.junction_senders, p.junction_receivers
    os, ot = p.cell_outside[js], p.cell_outside[jt]
    mean, log = logmean(
        xp.where(p.face_active, co[:, fs], 1.0), xp.where(p.face_active, co[:, ft], 1.0), xp=xp
    )
    weight = p.face_factor * mean
    conductance = F * F / rt * xp.sum(z * z * weight, axis=0)
    diffusion = F * xp.sum(z * weight * log, axis=0)
    matrix = _laplacian(conductance, fs, ft, o, xp=xp)
    phi0 = _linear_solve(matrix, -_divergence(diffusion, fs, ft, o, xp=xp), p, xp=xp)
    ca = xp.where(p.junction_active, ci[:, js], 1.0)
    cb = xp.where(p.junction_active, ci[:, jt], 1.0)

    def evaluate(phi):
        face_mu = rt * log + z * F * (phi[fs] - phi[ft])
        face_flux = xp.where(p.face_active, weight / MOL_PER_FMOL * (face_mu / rt), 0.0)
        face_current = CHARGE_PER_FMOL * xp.sum(z * face_flux, axis=0)
        cell_phi = xp.where(p.cell_active, membrane_voltage + phi[p.cell_outside], 0.0)
        dv = xp.where(p.junction_active, cell_phi[js] - cell_phi[jt], 0.0)
        flux = selective_flux(
            ca,
            cb,
            dv,
            z,
            p.temperature,
            p.junction_area,
            p.junction_permeability,
            0.0,
            gate,
            availability,
            xp=xp,
        )
        flux = xp.where(p.junction_active, flux, 0.0)
        current = CHARGE_PER_FMOL * xp.sum(z * flux, axis=0)
        residual = _divergence(face_current, fs, ft, o, xp=xp) + _divergence(
            current, os, ot, o, xp=xp
        )
        scale = xp.maximum(
            xp.max(xp.abs(diffusion), initial=0.0),
            xp.max(xp.abs(conductance * (phi[fs] - phi[ft])), initial=0.0),
        )
        scale = xp.maximum(scale, xp.max(xp.abs(current), initial=0.0))
        norm = xp.max(xp.abs(residual)) / (CURRENT_ATOL_A + CURRENT_RTOL * scale)
        x = z * F * dv / rt
        mu = rt * (xp.log(ca) - xp.log(cb)) + z * F * dv
        slope = (
            F
            * F
            / rt
            * p.junction_area
            * gate
            * availability
            * xp.sum(
                z
                * z
                * p.junction_permeability
                * (-ca * _bernoulli_derivative(-x, xp=xp) - cb * _bernoulli_derivative(x, xp=xp)),
                axis=0,
            )
        )
        slope = xp.where(p.junction_active, slope, 0.0)
        valid = (
            domain
            & xp.all(xp.abs(x) <= MAX_ABS_X)
            & xp.all(xp.isfinite(phi))
            & xp.all(xp.isfinite(flux))
            & xp.all(xp.isfinite(face_flux))
            & xp.all(xp.isfinite(slope) & (slope >= 0))
            & xp.isfinite(norm)
        )
        values = Values(
            phi,
            cell_phi,
            face_flux,
            xp.where(p.face_active, face_mu, 0.0),
            face_current,
            1e-3 * xp.sum(face_flux * face_mu, axis=0),
            dv,
            flux,
            xp.where(p.junction_active, mu, 0.0),
            current,
            1e-3 * xp.sum(flux * mu, axis=0),
            residual,
            norm,
            xp.asarray(0, dtype=xp.int32),
            valid & (norm <= NEWTON_TARGET),
        )
        return values, slope, valid

    def keep_going(state):
        count, _, norm, valid = state
        return (count < max_iterations) & (norm > NEWTON_TARGET) & valid

    def iteration(state):
        count, phi, _, _ = state
        old, slope, _ = evaluate(phi)
        jacobian = matrix + _laplacian(slope, os, ot, o, xp=xp)
        delta = _linear_solve(jacobian, -old.current_residual_A, p, xp=xp)
        before = xp.max(xp.abs(old.current_residual_A))

        def trial(backtrack):
            step, _, _, _ = backtrack
            proposal = phi + delta * (0.5**step)
            values, _, valid = evaluate(proposal)
            accepted = valid & (
                (xp.max(xp.abs(values.current_residual_A)) < before)
                | (values.current_normalized <= NEWTON_TARGET)
            )
            return step + 1, proposal, values.current_normalized, accepted

        def retry(backtrack):
            step, _, _, accepted = backtrack
            return (step < max_backtracks) & ~accepted

        search = (xp.asarray(0, dtype=xp.int32), phi, old.current_normalized, xp.asarray(False))
        if xp is np:
            while retry(search):
                search = trial(search)
        else:
            search = jax.lax.while_loop(retry, trial, search)
        _, proposal, norm, accepted = search
        return count + 1, xp.where(accepted, proposal, phi), norm, accepted

    initial, _, valid = evaluate(phi0)
    state = (xp.asarray(0, dtype=xp.int32), phi0, initial.current_normalized, valid)
    if xp is np:
        while keep_going(state):
            state = iteration(state)
    else:
        state = jax.lax.while_loop(keep_going, iteration, state)
    count, phi, _, valid = state
    result, _, _ = evaluate(phi)
    return result._replace(iterations=count, converged=result.converged & valid)
