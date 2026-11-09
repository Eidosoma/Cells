"""BETSE literal extracellular update paths, built on the engine's face-transport law.

The engine keeps the conservative Bernoulli-fitted face law, the grid binding, bath
ledgers and barriers (`cells.processes.extracellular_face_transport`). The paths
below reproduce BETSE v1.5.0's collocated derivative, boundary and smoothing
conventions, defects included. They are validation tooling only. Engine names are
re-exported unchanged.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.processes import extracellular_face_transport as _faces

globals().update({k: v for k, v in vars(_faces).items() if not k.startswith("__")})
from cells.processes.extracellular_face_transport import (  # noqa: E402
    _field,
    _fields,
    _number,
    _region_indices,
    _scalar,
    _thermal,
    grid_to_owner,
    owner_to_grid,
    reflect_gaussian,
)


def legacy_non_ecm_weight(grid, regions, tight_factor, *, xp=jnp):
    if not _number(tight_factor) or tight_factor < 0:
        raise ValueError("Require nonnegative source tight factor")
    targets = _region_indices(
        tuple(
            v
            for field in (
                "boundary_membrane_sites",
                "neighbor_membrane_sites",
                "boundary_cell_sites",
            )
            for v in getattr(regions, field)
        ),
        grid,
    )
    mask = np.zeros(len(grid.site_ids), bool)
    mask[targets] = True
    return reflect_gaussian(xp.where(xp.asarray(mask), tight_factor, 1.0), grid, sigma=1.0, xp=xp)


def source_gradient(values, h, *, negative_boundary=False, xp=jnp):
    value = xp.asarray(values)
    if value.ndim < 2 or min(value.shape[-2:]) < 2 or value.dtype.kind not in "fiu":
        raise ValueError("Native derivatives require two explicit spatial axes of length >=2")
    sign = -1.0 if negative_boundary else 1.0
    gx = xp.concatenate(
        (
            sign * (value[..., :, 1:2] - value[..., :, 0:1]) / h,
            (value[..., :, 2:] - value[..., :, :-2]) / (2 * h),
            sign * (value[..., :, -1:] - value[..., :, -2:-1]) / h,
        ),
        axis=-1,
    )
    gy = xp.concatenate(
        (
            sign * (value[..., 1:2, :] - value[..., 0:1, :]) / h,
            (value[..., 2:, :] - value[..., :-2, :]) / (2 * h),
            sign * (value[..., -1:, :] - value[..., -2:-1, :]) / h,
        ),
        axis=-2,
    )
    return gx, gy


def source_integrator(values, sharpness, *, xp=jnp):
    image = xp.asarray(values)
    sides = (1 - sharpness) / 4
    if image.ndim < 2 or min(image.shape[-2:]) < 2:
        raise ValueError("Explicit spatial grid axes required")
    interior = sharpness * image[..., 1:-1, 1:-1] + sides * (
        image[..., :-2, 1:-1] + image[..., 2:, 1:-1] + image[..., 1:-1, :-2] + image[..., 1:-1, 2:]
    )
    middle = xp.concatenate((image[..., 1:-1, 0:1], interior, image[..., 1:-1, -1:]), axis=-1)
    return xp.concatenate((image[..., 0:1, :], middle, image[..., -1:, :]), axis=-2)


class SourceResult(NamedTuple):
    concentration_mol_m3: object
    clamped_mol_m3: object
    after_euler_mol_m3: object
    flux_x_mol_m2_s: object
    flux_y_mol_m2_s: object
    clamp_change_mol: object
    collocated_change_mol: object
    smoothing_change_mol: object


def source_step(
    concentration,
    diffusion,
    bath,
    fields,
    thermal,
    dt_s,
    grid,
    *,
    sharpness=1.0,
    fluid_flow=False,
    extra_mobility=0.0,
    time_dilation=1.0,
    xp=jnp,
):
    if type(fluid_flow) is not bool or not _number(sharpness):
        raise ValueError("Source smoothing and flow guards are explicit scalar controls")
    c = owner_to_grid(concentration, grid, xp=xp)
    d = owner_to_grid(diffusion, grid, xp=xp)
    field = _fields(fields, grid, xp=xp)
    temp = _thermal(thermal, xp=xp)
    b = _field(bath, (len(grid.species_ids),), xp=xp)
    perimeter = xp.asarray(grid.kernel.perimeter).reshape(grid.shape)
    clamped = xp.where(perimeter, b[..., :, None, None], c)
    gx, gy = source_gradient(clamped, grid.delta_m, xp=xp)
    electric = field.electric_V_m.reshape(field.electric_V_m.shape[:-1] + grid.shape)
    velocity = field.velocity_m_s.reshape(field.velocity_m_s.shape[:-1] + grid.shape)
    beta = (temp.elementary_charge_C / (temp.boltzmann_J_K * temp.temperature_K))[
        ..., None, None, None
    ]
    z = xp.asarray(grid.kernel.valence)[:, None, None]
    mobility = _scalar(extra_mobility, xp=xp)[..., None, None, None]
    alpha = d * z * beta + mobility
    ux = velocity[..., 0, None, :, :] if fluid_flow else 0.0
    uy = velocity[..., 1, None, :, :] if fluid_flow else 0.0
    fx = -d * gx + alpha * electric[..., 0, None, :, :] * clamped + ux * clamped
    fy = -d * gy + alpha * electric[..., 1, None, :, :] * clamped + uy * clamped
    dx, _ = source_gradient(-fx, grid.delta_m, negative_boundary=True, xp=xp)
    _, dy = source_gradient(-fy, grid.delta_m, negative_boundary=True, xp=xp)
    step = (_scalar(dt_s, xp=xp) * _scalar(time_dilation, xp=xp))[..., None, None, None]
    euler = clamped + (dx + dy) * step
    updated = source_integrator(euler, sharpness, xp=xp) if sharpness < 1 else euler

    def amount_delta(a, b):
        return xp.sum(
            (grid_to_owner(a, grid, xp=xp) - grid_to_owner(b, grid, xp=xp))
            * xp.asarray(grid.kernel.volume_m3),
            axis=-1,
        )

    return SourceResult(
        grid_to_owner(updated, grid, xp=xp),
        grid_to_owner(clamped, grid, xp=xp),
        grid_to_owner(euler, grid, xp=xp),
        grid_to_owner(fx, grid, xp=xp),
        grid_to_owner(fy, grid, xp=xp),
        amount_delta(clamped, c),
        amount_delta(euler, clamped),
        amount_delta(updated, euler),
    )


def source_domain_valid(
    concentration,
    diffusion,
    bath,
    fields,
    thermal,
    dt_s,
    grid,
    *,
    sharpness=1.0,
    fluid_flow=False,
    extra_mobility=0.0,
    time_dilation=1.0,
    xp=jnp,
):
    try:
        result = source_step(
            concentration,
            diffusion,
            bath,
            fields,
            thermal,
            dt_s,
            grid,
            sharpness=sharpness,
            fluid_flow=fluid_flow,
            extra_mobility=extra_mobility,
            time_dilation=time_dilation,
            xp=xp,
        )
        values = (
            *result,
            concentration,
            diffusion,
            bath,
            *fields,
            *thermal,
            dt_s,
            extra_mobility,
            time_dilation,
        )
        valid = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in values]))
        valid &= (
            xp.all(xp.asarray(concentration) >= 0)
            & xp.all(xp.asarray(diffusion) >= 0)
            & xp.all(xp.asarray(bath) >= 0)
            & xp.all(result.concentration_mol_m3 >= 0)
        )
        valid &= (
            xp.all(xp.asarray(dt_s) > 0)
            & xp.all(xp.asarray(time_dilation) >= 0)
            & xp.asarray(0 <= sharpness <= 1)
        )
        valid &= xp.all(xp.stack([xp.all(xp.asarray(v) > 0) for v in thermal]))
        return valid
    except (ValueError, TypeError, IndexError):
        return xp.asarray(False)
