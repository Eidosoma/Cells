"""BETSE-convention geometry operators, built on the engine's geometry operator binding.

The engine binds mesh, grid and cell geometry (`cells.processes.geometry_operator_binding`).
The calculus below reproduces BETSE v1.5.0's discrete operators on those bindings,
including the source radial-volume and collocation conventions. It is validation
tooling only. Engine names are re-exported unchanged.
"""

import jax.numpy as jnp
import numpy as np

from cells.processes import geometry_operator_binding as _binding

globals().update({k: v for k, v in vars(_binding).items() if not k.startswith("__")})
from cells.processes.geometry_operator_binding import _domain, _field, _matvec  # noqa: E402


def edge_gradient(values, mesh, *, domain, xp=jnp):
    _domain(mesh, domain)
    k = mesh.kernel
    d0, lengths = (
        (k.primal_d0, k.primal_length_m) if domain == "primal" else (k.dual_d0, k.dual_length_m)
    )
    return _matvec(d0, values, xp=xp) / xp.asarray(lengths)


def mesh_divergence(values, mesh, *, domain, boundary, xp=jnp):
    _domain(mesh, domain)
    values = _field(values, len(mesh.edge_ids), xp=xp)
    if boundary not in ("closed", "interior_rows"):
        raise ValueError("Declare source closed or interior_rows boundary convention")
    if boundary == "interior_rows" and not mesh.auxiliary:
        raise ValueError("Native core-only mesh lacks auxiliary interior-row divergence")
    k = mesh.kernel
    if domain == "primal":
        matrix = -k.primal_d0.T if boundary == "closed" else k.dual_d1
        return _matvec(
            matrix, xp.asarray(values) * xp.asarray(k.dual_length_m), xp=xp
        ) / xp.asarray(k.cell_area_m2)
    if boundary == "closed":
        return _matvec(
            -k.dual_d0.T, xp.asarray(values) * xp.asarray(k.primal_length_m), xp=xp
        ) / xp.asarray(k.dual_control_area_m2)
    matrix = np.zeros((len(mesh.dual_vertex_ids), len(mesh.edge_ids)))
    matrix[np.asarray(k.inner_dual)] = k.primal_d1 / k.face_area_m2[:, None]
    return _matvec(matrix, xp.asarray(values) * xp.asarray(k.primal_length_m), xp=xp)


def mesh_laplacian(values, mesh, *, domain, boundary, xp=jnp):
    return mesh_divergence(
        edge_gradient(values, mesh, domain=domain, xp=xp),
        mesh,
        domain=domain,
        boundary=boundary,
        xp=xp,
    )


def source_factorized_inverse(values, mesh, *, domain, boundary, xp=jnp):
    _domain(mesh, domain)
    if (
        boundary not in ("closed", "interior_rows")
        or boundary == "interior_rows"
        and not mesh.auxiliary
    ):
        raise ValueError("Require an available explicit source boundary convention")
    k = mesh.kernel
    matrix = (
        (k.source_inverse_closed if boundary == "closed" else k.source_inverse_interior)
        if domain == "primal"
        else (
            k.dual_source_inverse_closed if boundary == "closed" else k.dual_source_inverse_interior
        )
    )
    return _matvec(matrix, values, xp=xp)


def density_poisson(values, mesh, *, xp=jnp):
    """Separate Cells least-squares inverse, arithmetic-zero component gauge.

    Call density_rhs_valid first. This differs from native factorized inverse.
    It neither imposes boundary potentials nor projects an incompatible source.
    """
    return _matvec(mesh.kernel.density_pseudoinverse, values, xp=xp)


def density_rhs_valid(values, mesh, *, rtol=2e-12, xp=jnp):
    try:
        value = xp.asarray(values)
        k = mesh.kernel
        if value.ndim < 1 or value.shape[-1] != len(mesh.cell_ids) or value.dtype.kind not in "fiu":
            return xp.asarray(False)
        sums = _matvec(k.components, value * xp.asarray(k.cell_area_m2), xp=xp)
        scale = _matvec(k.components, xp.abs(value) * xp.asarray(k.cell_area_m2), xp=xp)
        return xp.all(xp.isfinite(value)) & xp.all(xp.abs(sums) <= rtol * scale)
    except (ValueError, TypeError):
        return xp.asarray(False)


def source_xy_gradient(values, mesh, *, xp=jnp):
    """Literal native grad_xy mixing; not a guaranteed Cartesian gradient."""
    if not mesh.auxiliary:
        raise ValueError("Source Cartesian-mixing helper requires auxiliary operators")
    k = mesh.kernel
    edge_mean = _matvec(np.abs(k.primal_d0) / 2, values, xp=xp)
    weights = np.abs(k.dual_d0.T) * k.primal_length_m[None, :]
    denominators = np.sum(weights, axis=-1)
    if np.any(denominators == 0):
        raise ValueError("Native dual interpolation has an unbound zero-path vertex")
    dual = _matvec(weights, edge_mean, xp=xp) / xp.asarray(denominators)
    primal_grad = edge_gradient(values, mesh, domain="primal", xp=xp)
    dual_grad = edge_gradient(dual, mesh, domain="dual", xp=xp)
    return (
        xp.asarray(k.primal_tangent[:, 0]) * primal_grad
        + xp.asarray(k.primal_tangent[:, 1]) * dual_grad,
        xp.asarray(k.dual_tangent[:, 0]) * primal_grad
        + xp.asarray(k.dual_tangent[:, 1]) * dual_grad,
    )


def environment_laplacian(values, grid, *, xp=jnp):
    return _matvec(grid.kernel.laplacian, values, xp=xp)


def environment_poisson(values, grid, *, convention, xp=jnp):
    """Choose literal native SVD behavior or declared compatible-gauge inverse.

    Native numerical null-mode leakage is retained. The separate compatible
    solve requires environment_rhs_valid; it is not a source solver repair.
    """
    if convention not in ("native", "compatible_gauge"):
        raise ValueError("Choose native or compatible_gauge environment inverse")
    matrix = grid.kernel.pseudoinverse if convention == "native" else grid.kernel.compatible_inverse
    return _matvec(matrix, values, xp=xp)


def environment_rhs_valid(values, grid, *, rtol=2e-12, xp=jnp):
    try:
        value = _field(values, len(grid.environment_ids), xp=xp)
        finite = xp.all(xp.isfinite(value))
        if np.any(grid.kernel.fixed_value_rows):
            return finite
        return finite & xp.all(
            xp.abs(xp.sum(value, axis=-1)) <= rtol * xp.sum(xp.abs(value), axis=-1)
        )
    except (ValueError, TypeError):
        return xp.asarray(False)


def cell_gradient(values, geometry, *, domain, xp=jnp):
    if domain != "cell":
        raise ValueError("Cell gradient requires explicit cell owner values")
    normal = edge = _matvec(geometry.kernel.cell_gradient, values, xp=xp)
    return edge, normal[..., None] * xp.asarray(geometry.kernel.membrane_normal)


def cell_mean(values, geometry, *, domain, xp=jnp):
    if domain == "cell":
        return _matvec(geometry.kernel.cell_mean, values, xp=xp)
    if domain == "membrane":
        value = xp.asarray(values)
        if (
            value.ndim < 1
            or value.shape[-1] != len(geometry.membrane_ids)
            or value.dtype.kind not in "fiu"
        ):
            raise ValueError("Membrane mean requires declared final owner axis")
        return (value + xp.take(value, xp.asarray(geometry.kernel.partner), axis=-1)) / 2
    raise ValueError("Declare cell or membrane mean owner axis")


def surface_integrals(normal_flux, geometry, *, domain, xp=jnp):
    if domain not in ("cell", "environment"):
        raise ValueError("Declare destination cell or environment owners")
    k = geometry.kernel
    normal_flux = _field(normal_flux, len(geometry.membrane_ids), xp=xp)
    matrix = k.cell_sum if domain == "cell" else k.environment_sum
    return _matvec(matrix, xp.asarray(normal_flux) * xp.asarray(k.membrane_area_m2), xp=xp)


def cell_divergence(vectors, geometry, *, closed, volume_policy, xp=jnp):
    value = xp.asarray(vectors)
    k = geometry.kernel
    if (
        value.ndim < 2
        or value.shape[-2:] != (len(geometry.membrane_ids), 2)
        or value.dtype.kind not in "fiu"
        or type(closed) is not bool
    ):
        raise ValueError("Declare membrane vector axes [...,M,2] and boundary policy")
    if volume_policy not in ("native_radial", "polygon"):
        raise ValueError("Choose explicit native_radial or polygon density volume")
    normal = xp.sum(value * xp.asarray(k.membrane_normal), axis=-1)
    if closed:
        normal = xp.where(xp.asarray(k.boundary), 0, normal)
    volume = (
        k.native_cell_volume_m3 if volume_policy == "native_radial" else k.polygon_cell_volume_m3
    )
    return surface_integrals(normal, geometry, domain="cell", xp=xp) / xp.asarray(volume)


def circumference_gradient(values, geometry, *, domain, xp=jnp):
    if domain != "membrane":
        raise ValueError("Circumference derivative requires membrane ownership")
    return _matvec(geometry.kernel.theta, values, xp=xp)


def field_valid(values, geometry, *, domain, vector=False, xp=jnp):
    """Finite declared geometry fields; signed scalar/vector values are allowed."""
    counts = dict(
        cell=len(geometry.mesh.cell_ids),
        membrane=len(geometry.membrane_ids),
        environment=len(geometry.grid.environment_ids),
        primal=len(geometry.mesh.cell_ids),
        dual=len(geometry.mesh.dual_vertex_ids),
    )
    if domain not in counts or type(vector) is not bool:
        return xp.asarray(False)
    value = xp.asarray(values)
    tail = (counts[domain], 2) if vector else (counts[domain],)
    if value.ndim < len(tail) or value.shape[-len(tail) :] != tail or value.dtype.kind not in "fiu":
        return xp.asarray(False)
    return xp.all(xp.isfinite(value))
