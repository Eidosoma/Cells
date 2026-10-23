"""Same-stage passive field block, sparse ownership and a bounded dense solve.

No time integration, state repair, hidden warm start, persistent dense geometry,
or reference implementation dependency. Both NumPy observations and JAX stages
use the declared gauged_dense_kirchhoff@1 algorithm.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.processes.electrochemistry import CHARGE_PER_FMOL, MOL_PER_FMOL, F, R


def scatter(values, target, indices, *, xp=jnp):
    result = xp.zeros_like(target)
    if xp is np:
        np.add.at(result, (Ellipsis, *indices), values)
        return result
    return result.at[..., *indices].add(values)


def ordered_scatter(values, target, indices, *, xp=jnp):
    """Accumulate routes in declared order, without conflicting GPU updates.

    Each index array describes the last (route) axis of ``values``. Leading
    species/observation/world axes remain independent. A loop iteration writes
    one destination per leading entry, so ``set`` needs no atomic addition.
    This matches NumPy's sequential ``add.at`` for repeated destinations while
    keeping storage proportional to the input and output arrays.
    """
    if xp is np:
        return scatter(values, target, indices, xp=np)
    result = xp.zeros_like(target)
    if not values.shape[-1]:
        return result

    def add(i, accumulated):
        key = (Ellipsis, *(index[i] for index in indices))
        value = accumulated[key] + values[..., i]
        return accumulated.at[key].set(value, unique_indices=True)

    return jax.lax.fori_loop(0, values.shape[-1], add, result)


def logmean(left, right, *, xp=jnp):
    """Positive logarithmic mean and oriented log ratio, including equal inputs."""
    middle = 0.5 * left + 0.5 * right
    difference = left - right
    ratio = (0.5 * difference) / middle
    near = xp.abs(ratio) < 0.5
    log = xp.where(near, 2 * xp.arctanh(xp.where(near, ratio, 0.0)), xp.log(left) - xp.log(right))
    small = xp.abs(ratio) < 1e-4
    square = ratio * ratio
    mean = xp.where(
        small,
        middle * (1 - square / 3 - 4 * square * square / 45),
        difference / xp.where(small, 1.0, log),
    )
    return mean, log


class FieldValues(NamedTuple):
    potential_V: object
    flux_fmol_per_s: object
    delta_mu_J_per_mol: object
    conductance_S: object
    diffusion_current_A: object
    drift_current_A: object
    current_A: object
    current_residual_A: object
    current_normalized: object
    dissipation_rate_pJ_per_s: object


def solve(concentration, layout, *, xp=jnp):
    """Solve one connected outside graph (optional leading observation axes).

    Removing the one declared gauge row AND column leaves the physical Kirchhoff
    equations unchanged. Unit rows for inactive padding do not ground any active
    physical owner. No epsilon, pseudoinverse or least-squares repair is used.
    """
    active, src, dst = layout.face_active, layout.senders, layout.receivers
    left = xp.where(active, concentration[..., :, src], 1.0)
    right = xp.where(active, concentration[..., :, dst], 1.0)
    mean, log = logmean(left, right, xp=xp)
    weight = layout.face_factor * mean
    rt, z = R * layout.temperature, layout.valence
    conductance = F * F / rt * xp.sum(z * z * weight, axis=-2)
    diffusion = F * xp.sum(z * weight * log, axis=-2)
    size = concentration.shape[-1]
    matrix = xp.zeros((*conductance.shape[:-1], size, size), dtype=concentration.dtype)
    matrix = (
        scatter(conductance, matrix, (src, src), xp=xp)
        + scatter(conductance, matrix, (dst, dst), xp=xp)
        - scatter(conductance, matrix, (src, dst), xp=xp)
        - scatter(conductance, matrix, (dst, src), xp=xp)
    )
    target = xp.zeros((*conductance.shape[:-1], size), dtype=concentration.dtype)
    rhs = scatter(-diffusion, target, (src,), xp=xp) + scatter(diffusion, target, (dst,), xp=xp)
    free = layout.extracellular_active & ~layout.gauge_mask
    scale = xp.max(xp.abs(matrix), axis=(-2, -1))
    scale = xp.where(scale > 0, scale, 1.0)  # Also the single-volume/no-face case.
    matrix = xp.where(free[:, None] & free[None, :], matrix / scale[..., None, None], 0.0)
    matrix = matrix + xp.diag((~free).astype(concentration.dtype))
    rhs = xp.where(free, rhs / scale[..., None], 0.0)
    potential = xp.linalg.solve(matrix, rhs[..., None])[..., 0]
    dv = potential[..., src] - potential[..., dst]
    mu = rt * log + z * F * dv[..., None, :]
    flux = xp.where(active, weight / MOL_PER_FMOL * (mu / rt), 0.0)
    current = CHARGE_PER_FMOL * xp.sum(z * flux, axis=-2)
    residual = scatter(current, target, (src,), xp=xp) - scatter(current, target, (dst,), xp=xp)
    drift = conductance * dv
    current_scale = xp.maximum(
        xp.max(xp.abs(diffusion), axis=-1, initial=0.0),
        xp.max(xp.abs(drift), axis=-1, initial=0.0),
    )
    normalized = xp.max(xp.abs(residual), axis=-1) / (1e-23 + 2e-12 * current_scale)
    return FieldValues(
        potential,
        flux,
        xp.where(active, mu, 0.0),
        conductance,
        diffusion,
        drift,
        current,
        residual,
        normalized,
        1e-3 * xp.sum(flux * mu, axis=-2),
    )
