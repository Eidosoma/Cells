"""Face gradients and conservative divergence on the Cells rectangular metric.

Faces point along increasing x/y. Outer gradient faces have zero normal flux;
they are not one-sided estimates of an unconstrained boundary derivative.
Arrays may have any leading batch axes. The cell axis is C-order and flattened,
whereas face arrays retain their spatial axes. Arithmetic uses O(number of cells)
temporary storage and never reads a dense Laplacian or inverse.

The existing GridBinding and its 625-cell bound are unchanged. These kernels do
not create material currents, native owners, masked domains or a tissue phase.
The xp interface permits array backends; its presence is not GPU qualification.
"""

from typing import NamedTuple

import numpy as np

from cells.processes import rectangular_environment as field


class Faces(NamedTuple):
    x: object  # (..., ny, nx + 1), oriented towards increasing x.
    y: object  # (..., ny + 1, nx), oriented towards increasing y.


class DivergenceResult(NamedTuple):
    values: object  # (..., ny * nx); includes raw refused/nonfinite candidates.
    boundary_integral: object  # Net outward flux integrated along the 2D perimeter.
    cell_integral: object  # Cell area times the sum of the returned divergence.
    balance_residual: object  # Cell integral minus boundary integral; never corrected.
    zero_boundary: object  # Every outer face is exactly zero, not merely net-balanced.
    finite_result: object

    @property
    def usable(self):
        """Homogeneous boundary and finite arithmetic, not accuracy/material admission."""
        return self.zero_boundary & self.finite_result


def gradient(values, grid, *, xp=np):
    """Cell-to-face differences with the binding's homogeneous-flux boundary.

    The result has units of input units per metre. It is the mathematical gradient;
    an electric-field sign or conductivity needs a separately specified field law.
    Nonfinite arithmetic is retained. Inputs and the grid are never modified.
    """
    values = field._field(values, grid, xp)
    plane = values.reshape((*values.shape[:-1], *grid.shape))
    dx, dy = grid.spacing_xy_m
    x = (plane[..., 1:] - plane[..., :-1]) / dx
    y = (plane[..., 1:, :] - plane[..., :-1, :]) / dy
    x_zero, y_zero = xp.zeros_like(plane[..., :1]), xp.zeros_like(plane[..., :1, :])
    return Faces(
        xp.concatenate((x_zero, x, x_zero), axis=-1),
        xp.concatenate((y_zero, y, y_zero), axis=-2),
    )


def _faces(values, grid, xp):
    if type(grid) is not field.GridBinding or type(values) is not Faces:
        raise ValueError("Require the rectangular GridBinding and explicit face arrays")
    x, y = xp.asarray(values.x), xp.asarray(values.y)
    ny, nx = grid.shape
    if (
        x.ndim < 2
        or y.ndim < 2
        or x.shape[-2:] != (ny, nx + 1)
        or y.shape[-2:] != (ny + 1, nx)
        or x.shape[:-2] != y.shape[:-2]
        or str(x.dtype) != "float64"
        or str(y.dtype) != "float64"
    ):
        raise ValueError("Require complete float64 staggered faces with identical batch axes")
    return x, y


def divergence(values, grid, *, xp=np):
    """Retain full face divergence and its boundary/conservation diagnostics.

    Nonzero outer flux is outside this homogeneous-Neumann law even if its total
    is zero. It is flagged unusable without clamping, projecting or discarding the
    raw arithmetic. The two integrals are per unit out-of-plane thickness; no
    volume, material or thermodynamic interpretation is supplied here.
    """
    x, y = _faces(values, grid, xp)
    dx, dy = grid.spacing_xy_m
    plane = (x[..., 1:] - x[..., :-1]) / dx + (y[..., 1:, :] - y[..., :-1, :]) / dy
    result = plane.reshape((*plane.shape[:-2], len(grid.environment_ids)))
    boundary = dy * (xp.sum(x[..., -1], axis=-1) - xp.sum(x[..., 0], axis=-1)) + dx * (
        xp.sum(y[..., -1, :], axis=-1) - xp.sum(y[..., 0, :], axis=-1)
    )
    integrated = grid.cell_area_m2 * xp.sum(result, axis=-1)
    balance = integrated - boundary
    zero = (
        xp.all(x[..., 0] == 0, axis=-1)
        & xp.all(x[..., -1] == 0, axis=-1)
        & xp.all(y[..., 0, :] == 0, axis=-1)
        & xp.all(y[..., -1, :] == 0, axis=-1)
    )
    finite = (
        xp.all(xp.isfinite(x), axis=(-2, -1))
        & xp.all(xp.isfinite(y), axis=(-2, -1))
        & xp.all(xp.isfinite(result), axis=-1)
        & xp.isfinite(boundary)
        & xp.isfinite(integrated)
        & xp.isfinite(balance)
    )
    return DivergenceResult(result, boundary, integrated, balance, zero, finite)


def apply(values, grid, *, xp=np):
    """Raw divergence of the homogeneous-boundary gradient, without dense products.

    This is the same declared mathematical stencil as rectangular_environment.apply,
    with a different floating-point evaluation order; bit identity is not promised.
    Use divergence(gradient(...)) when boundary/finite/conservation flags are needed.
    """
    return divergence(gradient(values, grid, xp=xp), grid, xp=xp).values
