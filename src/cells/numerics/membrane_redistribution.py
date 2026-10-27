"""Conservative lateral transport of membrane-bound populations on fixed patches.

Amounts are fmol, patch areas um^2, lengths um, diffusivities um^2/s and supplied
tangential potentials V. A population's effective charge controls drift; it is
not a new free-ion inventory. Edges stay within one cell. No synthesis, removal,
membrane crossing, field solve or channel-gate update is performed here.

This independently specified finite-volume law is not BETSE's radial weighting
update. It supports NumPy and JAX, with independent worlds composed using vmap.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.numerics.extracellular_field import ordered_scatter
from cells.processes.electrochemistry import F, R, bernoulli

LAW_ID = "fixed_surface_conservative_drift_diffusion@1"
MAX_ABS_X = 50.0


class Layout(NamedTuple):
    temperature_K: object
    effective_charge_e: object
    cell_active: object
    patch_active: object
    patch_cell: object
    patch_area_um2: object
    edge_active: object
    edge_sender: object
    edge_receiver: object
    edge_diffusivity_um2_s: object
    edge_width_um: object
    edge_distance_um: object


class Rates(NamedTuple):
    density_fmol_um2: object
    flux_fmol_s: object
    amount_rate_fmol_s: object
    forward_rate_s_inv: object
    reverse_rate_s_inv: object
    outgoing_rate_s_inv: object
    cell_rate_residual_fmol_s: object
    valid: object


class Step(NamedTuple):
    amount_fmol: object
    transferred_fmol: object
    cell_residual_fmol: object
    valid: object


def validate_layout(layout):
    """Check host ownership and units' domains before staging a device kernel."""
    p = Layout(*(np.asarray(v) for v in layout))
    for key in ("effective_charge_e", "cell_active", "patch_active", "edge_active"):
        if getattr(p, key).ndim != 1:
            raise ValueError("Redistribution axes must be one dimensional")
    k, c, m, e = (
        getattr(p, key).size
        for key in ("effective_charge_e", "cell_active", "patch_active", "edge_active")
    )
    shapes = {
        "temperature_K": (),
        "effective_charge_e": (k,),
        "cell_active": (c,),
        "patch_active": (m,),
        "patch_cell": (m,),
        "patch_area_um2": (m,),
        "edge_active": (e,),
        "edge_sender": (e,),
        "edge_receiver": (e,),
        "edge_diffusivity_um2_s": (k, e),
        "edge_width_um": (e,),
        "edge_distance_um": (e,),
    }
    if min(k, c, m) < 1 or any(getattr(p, key).shape != shape for key, shape in shapes.items()):
        raise ValueError("Invalid redistribution shapes")
    if any(
        getattr(p, key).dtype != np.bool_ for key in ("cell_active", "patch_active", "edge_active")
    ):
        raise ValueError("Redistribution masks must be boolean")
    if not all(np.isfinite(v).all() for v in p) or p.temperature_K <= 0:
        raise ValueError("Redistribution geometry requires finite values and positive temperature")
    if not np.any(p.cell_active) or not np.any(p.patch_active):
        raise ValueError("Redistribution requires active cells and patches")
    for key, size in (("patch_cell", c), ("edge_sender", m), ("edge_receiver", m)):
        indices = getattr(p, key)
        if not np.issubdtype(indices.dtype, np.integer) or np.any(
            (indices < 0) | (indices >= size)
        ):
            raise ValueError("Invalid redistribution owner: " + key)
    if np.any(p.patch_active & ~p.cell_active[p.patch_cell]):
        raise ValueError("Active membrane patches require active cell owners")
    counts = np.bincount(p.patch_cell[p.patch_active], minlength=c)
    if np.any(p.cell_active & (counts == 0)):
        raise ValueError("Every active cell requires a membrane patch")
    for key, mask in (
        ("patch_area_um2", p.patch_active),
        ("edge_width_um", p.edge_active),
        ("edge_distance_um", p.edge_active),
    ):
        values = getattr(p, key)
        if np.any(values[mask] <= 0) or np.any(values[~mask] != 0):
            raise ValueError("Positive active geometry and zero padding required: " + key)
    d = p.edge_diffusivity_um2_s
    if np.any(d < 0) or np.any(d[:, ~p.edge_active] != 0):
        raise ValueError("Diffusivity must be nonnegative with zero padding")
    active, src, dst = p.edge_active, p.edge_sender, p.edge_receiver
    if np.any(active & (~p.patch_active[src] | ~p.patch_active[dst] | (src == dst))):
        raise ValueError("Redistribution edges require two distinct active patches")
    if np.any(active & (p.patch_cell[src] != p.patch_cell[dst])):
        raise ValueError("Lateral redistribution cannot cross cell ownership")
    pairs = [tuple(sorted((int(a), int(b)))) for a, b in zip(src[active], dst[active], strict=True)]
    if len(set(pairs)) != len(pairs):
        raise ValueError("A membrane edge must be owned once")
    return p


def _sum(values, owners, size, *, xp):
    target = xp.zeros((*values.shape[:-1], size), dtype=values.dtype)
    return ordered_scatter(values, target, (xp.asarray(owners),), xp=xp)


def rates(amount_fmol, potential_V, p, *, xp=jnp):
    """Return same-stage material rates; positive edge flux is sender -> receiver.

    For edge i -> j, x = z F (phi_j - phi_i)/(RT), g = D width/distance,
    J = g [B(x) N_i/A_i - B(-x) N_j/A_j], B(x) = x/expm1(x).
    Thus zero-field equilibrium has uniform density, not uniform patch amount.
    At fixed potential, equilibrium density is proportional to exp(-z F phi/RT).
    Zero amounts are valid. Invalid state returns valid=False and NaN outputs;
    negative material is never clipped or redistributed to hide an invalid step.
    """
    shape = (p.effective_charge_e.size, p.patch_active.size)
    if amount_fmol.shape != shape or potential_V.shape != p.patch_active.shape:
        raise ValueError("Redistribution state shape disagrees with layout")
    src, dst, active = p.edge_sender, p.edge_receiver, p.edge_active
    area = xp.where(p.patch_active, p.patch_area_um2, 1.0)
    x = p.effective_charge_e[:, None] * F * (potential_V[dst] - potential_V[src])
    x = x / (R * p.temperature_K)
    x_ok = xp.isfinite(x) & (xp.abs(x) <= MAX_ABS_X)
    safe_x = xp.where(active & x_ok, x, 0.0)
    mobility = (
        p.edge_diffusivity_um2_s * p.edge_width_um / xp.where(active, p.edge_distance_um, 1.0)
    )
    forward = xp.where(active, mobility * bernoulli(safe_x, xp=xp) / area[src], 0.0)
    reverse = xp.where(active, mobility * bernoulli(-safe_x, xp=xp) / area[dst], 0.0)
    flux = forward * amount_fmol[:, src] - reverse * amount_fmol[:, dst]
    derivative = _sum(-flux, src, shape[1], xp=xp) + _sum(flux, dst, shape[1], xp=xp)
    outgoing = _sum(forward, src, shape[1], xp=xp) + _sum(reverse, dst, shape[1], xp=xp)
    values = (
        xp.where(p.patch_active, amount_fmol / area, 0.0),
        flux,
        derivative,
        forward,
        reverse,
        outgoing,
        _sum(derivative, p.patch_cell, p.cell_active.size, xp=xp),
    )
    valid = (
        xp.all(xp.isfinite(amount_fmol))
        & xp.all(amount_fmol >= 0)
        & xp.all(xp.where(p.patch_active, True, amount_fmol == 0))
        & xp.all(xp.isfinite(potential_V))
        & xp.all(xp.where(p.patch_active, True, potential_V == 0))
        & xp.all(xp.where(active, x_ok, True))
    )
    for value in values:
        valid = valid & xp.all(xp.isfinite(value))
    return Rates(*(xp.where(valid, value, xp.nan) for value in values), valid)


def explicit_step(amount_fmol, potential_V, dt_s, p, *, xp=jnp):
    """One conservative Euler step, rejecting dt * outgoing_rate > 1 anywhere.

    Separate nonnegative retained and incoming amounts avoid subtractive repair.
    This bounded primitive is not the coupled tissue integrator. Its transfer
    ledger records the same starting-state fluxes that advance the amounts.
    """
    if xp.ndim(dt_s) != 0:
        raise ValueError("Redistribution timestep must be scalar")
    r = rates(amount_fmol, potential_V, p, xp=xp)
    src, dst, size = p.edge_sender, p.edge_receiver, p.patch_active.size
    incoming = _sum(r.forward_rate_s_inv * amount_fmol[:, src], dst, size, xp=xp)
    incoming = incoming + _sum(r.reverse_rate_s_inv * amount_fmol[:, dst], src, size, xp=xp)
    retained = 1 - dt_s * r.outgoing_rate_s_inv
    after = retained * amount_fmol + dt_s * incoming
    transferred = dt_s * r.flux_fmol_s
    residual = _sum(after - amount_fmol, p.patch_cell, p.cell_active.size, xp=xp)
    valid = (
        r.valid
        & xp.isfinite(dt_s)
        & (dt_s >= 0)
        & xp.all(retained >= 0)
        & xp.all(xp.isfinite(after))
        & xp.all(after >= 0)
        & xp.all(xp.isfinite(transferred))
        & xp.all(xp.isfinite(residual))
    )
    return Step(
        *(xp.where(valid, value, xp.nan) for value in (after, transferred, residual)), valid
    )
