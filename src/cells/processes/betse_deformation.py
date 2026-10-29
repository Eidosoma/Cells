"""Literal pinned BETSE steady deformation and disabled dynamic diagnostics.

Displacement axes are [...,2,cell], in metres. Operators/geometry are explicit;
no geometry rebuild, material change, fixed-boundary correction or force-energy
closure is inferred. The native osmotic PP auxiliary has unresolved physical
dimensions and is deliberately named as a source quantity.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

LAW_ID = "betse_deformation_source_v1_5_0@1"
MAX_DENSE_CELLS = 256


class Operators(NamedTuple):
    pressure_gradient_x: object
    pressure_gradient_y: object
    curl_gradient_x: object
    curl_gradient_y: object
    laplacian: object
    laplacian_inverse: object
    active: object


class Parameters(NamedTuple):
    shear_modulus_Pa: object
    galvanotropism_m2_V: object
    include_osmotic: object
    fixed_cluster_boundary: object  # Native HH_cells ignores this flag.
    dt_s: object
    viscous_damping_native: object
    cell_radius_m: object


class Forcing(NamedTuple):
    pressure_Pa: object
    osmotic_PP_native: object
    electric_field_V_m: object
    current_density_A_m2: object
    charge_density_C_m3: object
    conductivity_S_m: object


class SteadyResult(NamedTuple):
    displacement_m: object
    pressure_gradient_Pa_m: object
    unprojected_elastic_m: object
    rotational_m: object
    rotation_potential: object
    osmotic_addition_native: object
    electric_addition_m: object
    divergence_numeric: object


class History(NamedTuple):
    displacement_m: object
    previous_displacement_m: object


class DisabledTimeResult(NamedTuple):
    history: History
    pressure_gradient_native: object
    divided_body_force_native: object
    unprojected_candidate_m: object
    rotation_potential: object
    source_k_m2: object
    source_gamma_native: object
    divergence_numeric: object


class OsmoticGeometry(NamedTuple):
    environment_average: object  # [cell,env]; explicit map or membrane average.
    cell_area_m2: object
    cell_volume_m3: object


class OsmoticParameters(NamedTuple):
    gas_constant_J_mol_K: object
    temperature_K: object
    aquaporin_fraction: object
    water_viscosity_Pa_s: object
    membrane_thickness_m: object
    density_kg_m3: object
    dt_s: object


class OsmoticResult(NamedTuple):
    cell_osmotic_pressure_Pa: object
    environment_osmotic_pressure_Pa: object
    delta_pressure_Pa: object
    water_velocity_m_s: object
    divergence_per_s: object
    PP_native: object


class DisplayResult(NamedTuple):
    vertices_m: object
    cell_centres_m: object


def _real(value):
    return value.dtype.kind in "fiu"


def _operators(operators, *, xp):
    values = [xp.asarray(v) for v in operators]
    active = values[-1]
    if (
        active.ndim != 1
        or not 0 < active.size <= MAX_DENSE_CELLS
        or active.dtype.kind != "b"
        or any(v.shape != (active.size, active.size) or not _real(v) for v in values[:-1])
    ):
        raise ValueError("Require bounded square operators and an explicit boolean cell axis")
    valid = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in values[:-1]]))
    for value in values[:-1]:
        valid &= xp.all(xp.where(active[:, None] & active[None, :], True, value == 0))
    return valid, Operators(*values)


def validate_operators(operators):
    valid, value = _operators(operators, xp=np)
    if not valid:
        raise ValueError("Nonfinite operators or nonneutral inactive cell rows/columns")
    return value


def _parameters(parameters, *, xp):
    values = [xp.asarray(v) for v in parameters]
    for i, value in enumerate(values):
        if (value.dtype.kind != "b") if i in (2, 3) else not _real(value):
            raise ValueError("Require real mechanics parameters and explicit boolean flags")
        if not value.ndim:
            values[i] = value.reshape((1,))
        if values[i].shape[-1] != 1:
            raise ValueError("Mechanics parameters require singleton final world axes")
    return Parameters(*values)


def _forcing(forcing, operators, *, xp):
    values = [xp.asarray(v) for v in forcing]
    n = operators.active.size
    if (
        any(not _real(v) for v in values)
        or any(v.ndim < 1 or v.shape[-1] != n for v in (values[0], values[1], values[4]))
        or any(v.ndim < 2 or v.shape[-2:] != (2, n) for v in (values[2], values[3]))
    ):
        raise ValueError("Forcing requires scalar-cell and vector [2,cell] axes")
    if values[5].ndim and values[5].shape[-1] not in (1, n):
        raise ValueError("Conductivity requires scalar or final singleton/cell axis")
    return Forcing(*values)


def _mat(matrix, value, *, xp):
    return xp.einsum("ij,...j->...i", matrix, value)


def _vector_mat(matrix, value, *, xp):
    return xp.einsum("ij,...aj->...ai", matrix, value)


def _gradient(value, operators, *, xp):
    return xp.stack([_mat(matrix, value, xp=xp) for matrix in operators[:2]], axis=-2)


def rotation_only(vector, operators, *, xp=jnp):
    """Actual curl/inverse/curl source operator; no projection property assumed."""
    curl = _mat(operators.curl_gradient_x, vector[..., 1, :], xp=xp) - _mat(
        operators.curl_gradient_y, vector[..., 0, :], xp=xp
    )
    potential = _mat(operators.laplacian_inverse, -curl, xp=xp)
    rotated = xp.stack(
        (
            _mat(operators.curl_gradient_y, potential, xp=xp),
            -_mat(operators.curl_gradient_x, potential, xp=xp),
        ),
        axis=-2,
    )
    return potential, rotated


def divergence_numeric(vector, operators, *, xp=jnp):
    return _mat(operators.curl_gradient_x, vector[..., 0, :], xp=xp) + _mat(
        operators.curl_gradient_y, vector[..., 1, :], xp=xp
    )


def steady(forcing, operators, parameters, *, xp=jnp):
    """Reachable native quasi-static branch, independent of prior displacement."""
    p, f = _parameters(parameters, xp=xp), _forcing(forcing, operators, xp=xp)
    gradient = _gradient(f.pressure_Pa, operators, xp=xp)
    raw = _vector_mat(
        operators.laplacian_inverse, -gradient / p.shear_modulus_Pa[..., None, :], xp=xp
    )
    potential, rotated = rotation_only(raw, operators, xp=xp)
    osmotic = xp.where(
        p.include_osmotic[..., None, :], _gradient(f.osmotic_PP_native, operators, xp=xp), 0.0
    )
    electric = f.electric_field_V_m * p.galvanotropism_m2_V[..., None, :]
    displacement = xp.where(operators.active, rotated + osmotic + electric, 0.0)
    return SteadyResult(
        displacement,
        gradient,
        raw,
        rotated,
        potential,
        osmotic,
        electric,
        divergence_numeric(displacement, operators, xp=xp),
    )


def disabled_time_step(history, forcing, operators, parameters, *, xp=jnp):
    """Positive-clock branch of disabled native recurrence, for diagnostics only.

    Native parameters force td_deform=False and its t=0 path uses removed
    np.float. This kernel does not enable/repair native initialization. Supply
    both history levels explicitly; enforce positive time with its predicate.
    """
    p, f = _parameters(parameters, xp=xp), _forcing(forcing, operators, xp=xp)
    current, previous = (xp.asarray(v) for v in history)
    if (
        current.shape[-2:] != (2, operators.active.size)
        or previous.shape != current.shape
        or not all(_real(v) for v in (current, previous))
    ):
        raise ValueError("Require two equal-shaped displacement history levels")
    pressure = f.pressure_Pa + xp.where(p.include_osmotic, f.osmotic_PP_native, 0.0)
    gradient = _gradient(pressure, operators, xp=xp)
    sigma = xp.asarray(f.conductivity_S_m)
    body = (
        gradient
        + (
            f.current_density_A_m2 / sigma[..., None, :]
            if sigma.ndim
            else f.current_density_A_m2 / sigma
        )
        * f.charge_density_C_m3[..., None, :]
        * p.galvanotropism_m2_V[..., None, :]
    ) / p.shear_modulus_Pa[..., None, :]
    k = p.dt_s**2 * (p.shear_modulus_Pa / 1000.0)
    gamma = (
        p.dt_s**2 * p.viscous_damping_native * p.shear_modulus_Pa / (1000.0 * 2 * p.cell_radius_m)
    )
    candidate = (
        k[..., None, :] * _vector_mat(operators.laplacian, current, xp=xp)
        - gamma[..., None, :] * (current - previous) / p.dt_s[..., None, :]
        + (k / p.shear_modulus_Pa)[..., None, :] * body
        + 2 * current
        - previous
    )
    potential, result = rotation_only(candidate, operators, xp=xp)
    result = xp.where(operators.active, result, 0.0)
    return DisabledTimeResult(
        History(result, xp.broadcast_to(current, result.shape)),
        gradient,
        body,
        candidate,
        potential,
        k,
        gamma,
        divergence_numeric(result, operators, xp=xp),
    )


def domain_valid(
    forcing, operators, parameters, *, history=None, time_s=None, max_displacement_m=None, xp=jnp
):
    """Scalar trial predicate; vmap for world isolation. No physical clamping."""
    try:
        valid, op = _operators(operators, xp=xp)
        p, f = _parameters(parameters, xp=xp), _forcing(forcing, op, xp=xp)
        valid &= xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in (*p, *f)]))
        valid &= xp.all(
            (p.shear_modulus_Pa > 0)
            & (p.cell_radius_m > 0)
            & (p.dt_s > 0)
            & (p.viscous_damping_native >= 0)
        )
        for value in f[:5]:
            valid &= xp.all(xp.where(op.active, True, value == 0))
        if history is None:
            result = steady(f, op, p, xp=xp)
            displacement = result.displacement_m
            valid &= xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in result]))
        else:
            clock = xp.asarray(time_s)
            valid &= _real(clock) & xp.all(xp.isfinite(clock) & (clock > 0))
            valid &= xp.all(xp.asarray(f.conductivity_S_m) > 0)
            for value in history:
                value = xp.asarray(value)
                valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(op.active, True, value == 0))
            result = disabled_time_step(history, f, op, p, xp=xp)
            displacement = result.history.displacement_m
            valid &= xp.all(
                xp.stack([xp.all(xp.isfinite(v)) for v in (*result.history, *result[1:])])
            )
        if max_displacement_m is not None:
            limit = xp.asarray(max_displacement_m)
            valid &= _real(limit) & xp.all(xp.isfinite(limit) & (limit > 0))
            valid &= xp.all(xp.sqrt(xp.sum(displacement**2, axis=-2)) <= limit)
        return valid
    except (ValueError, TypeError, IndexError, AttributeError):
        return xp.asarray(False)


def osmotic_auxiliary(
    cell_total_mM, environment_total_mM, pressure_Pa, geometry, operators, parameters, *, xp=jnp
):
    """Source pressures.py numeric auxiliary; does not move water/amount/volume.

    Totals must include exactly the caller's intended ion/molecule/GRN rows.
    Native adds those rows without detecting duplicate physical inventories.
    """
    cell, env, pressure = (
        xp.asarray(v) for v in (cell_total_mM, environment_total_mM, pressure_Pa)
    )
    matrix, area, volume = (xp.asarray(v) for v in geometry)
    if (
        matrix.ndim != 2
        or matrix.shape != (operators.active.size, env.shape[-1])
        or cell.shape[-1] != matrix.shape[0]
        or pressure.shape[-1] != matrix.shape[0]
        or area.shape != cell.shape[-1:]
        or volume.shape != area.shape
    ):
        raise ValueError("Osmotic owners/geometry axes mismatch")
    r, temperature, aq, viscosity, thickness, density, dt = (xp.asarray(v) for v in parameters)
    pc, pe = r * temperature * cell, r * temperature * env
    delta = _mat(matrix, pe, xp=xp) - pc
    velocity = (delta - pressure) * (aq / viscosity) * (3e-10**2) / thickness
    safe_volume = xp.where(operators.active, volume, 1.0)
    div = xp.where(operators.active, velocity * area / safe_volume, 0.0)
    pp = _mat(operators.laplacian_inverse, -div * density * dt, xp=xp)
    return OsmoticResult(pc, pe, delta, velocity, div, pp)


def osmotic_domain_valid(
    cell_total_mM, environment_total_mM, pressure_Pa, geometry, operators, parameters, *, xp=jnp
):
    try:
        valid, op = _operators(operators, xp=xp)
        matrix, area, volume = (xp.asarray(v) for v in geometry)
        cell, env, pressure = (
            xp.asarray(v) for v in (cell_total_mM, environment_total_mM, pressure_Pa)
        )
        params = [xp.asarray(v) for v in parameters]
        valid &= all(_real(v) for v in (matrix, area, volume, cell, env, pressure, *params))
        valid &= xp.all(
            xp.stack(
                [
                    xp.all(xp.isfinite(v))
                    for v in (matrix, area, volume, cell, env, pressure, *params)
                ]
            )
        )
        valid &= xp.all((cell >= 0) & xp.where(op.active, True, cell == 0)) & xp.all(env >= 0)
        valid &= xp.all(xp.where(op.active, True, pressure == 0))
        valid &= xp.all(matrix >= 0) & xp.all(xp.sum(matrix, axis=-1) == op.active)
        valid &= xp.all(xp.where(op.active, (area > 0) & (volume > 0), (area == 0) & (volume == 0)))
        valid &= xp.all(params[0] > 0) & xp.all(params[1] > 0) & xp.all(params[2] >= 0)
        valid &= xp.all(xp.stack([xp.all(v > 0) for v in params[3:6]])) & xp.all(params[6] >= 0)
        result = osmotic_auxiliary(cell, env, pressure, geometry, op, parameters, xp=xp)
        return valid & xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in result]))
    except (ValueError, TypeError, IndexError, AttributeError):
        return xp.asarray(False)


def bind_operators(
    neighbors,
    lengths_m,
    force_directions,
    curl_directions,
    sum_membranes,
    incidence,
    incidence_inverse,
    dual_edge_m,
    primal_edge_m,
    dual_area_m2,
    *,
    cell_capacity=None,
):
    """Host native matrix construction from supplied layout/DEC data only."""
    nn, length, normal, tangent, sm, d, di, dual, primal, area = (
        np.asarray(v)
        for v in (
            neighbors,
            lengths_m,
            force_directions,
            curl_directions,
            sum_membranes,
            incidence,
            incidence_inverse,
            dual_edge_m,
            primal_edge_m,
            dual_area_m2,
        )
    )
    n, membranes = sm.shape
    if (
        not 0 < n <= MAX_DENSE_CELLS
        or nn.shape != (membranes, 2)
        or nn.dtype.kind not in "iu"
        or length.shape != (membranes,)
        or normal.shape != (membranes, 2)
        or tangent.shape != normal.shape
        or np.any((nn < 0) | (nn >= n))
        or d.ndim != 2
        or d.shape[1] != n
        or di.shape != d.T.shape
        or dual.shape != (d.shape[0],)
        or primal.shape != dual.shape
        or area.shape != (n,)
    ):
        raise ValueError("Inconsistent supplied native layout/DEC axes")
    if (
        not all(
            _real(v) and np.isfinite(v).all()
            for v in (length, normal, tangent, sm, d, di, dual, primal, area)
        )
        or np.any(length <= 0)
        or np.any(dual <= 0)
        or np.any(primal <= 0)
        or np.any(area <= 0)
        or not np.all((sm == 0) | (sm == 1))
        or not np.all(sm.sum(axis=0) == 1)
        or np.any(sm.sum(axis=1) <= 0)
    ):
        raise ValueError("Invalid explicit native geometry measures or membrane ownership")
    average = sm / sm.sum(axis=1)[:, None]
    difference = (np.eye(n)[nn[:, 1]] - np.eye(n)[nn[:, 0]]) / length[:, None]
    fg = [-average @ (normal[:, i, None] * difference) for i in range(2)]
    cg = [average @ (tangent[:, i, None] * difference) for i in range(2)]
    l1, l2 = (dual / primal)[:, None] * d, -d.T / area[:, None]
    inv1, inv2 = di * (primal / dual), -di.T * area
    matrices = [*fg, *cg, l2 @ l1, inv1 @ inv2]
    capacity = n if cell_capacity is None else cell_capacity
    if type(capacity) is not int or not n <= capacity <= MAX_DENSE_CELLS:
        raise ValueError("Cell capacity outside bounded dense component")
    return validate_operators(
        Operators(
            *(np.pad(v, ((0, capacity - n), (0, capacity - n))) for v in matrices),
            np.arange(capacity) < n,
        )
    )


def quartic_display_interpolator(cell_centres_m, vertices_m):
    """Global degree(4,4) least-squares map, only the captured polynomial regime.

    Native SmoothBivariateSpline may choose adaptive knots for other inputs.
    This helper does not implement adaptive FITPACK or infer tissue geometry.
    Rebuild against the current display centres at each sampled source call.
    """
    centres, vertices = np.asarray(cell_centres_m, float), np.asarray(vertices_m, float)
    if (
        centres.ndim != 2
        or centres.shape[1] != 2
        or not 25 <= centres.shape[0] <= MAX_DENSE_CELLS
        or vertices.ndim != 2
        or vertices.shape[1] != 2
        or not all(np.isfinite(v).all() for v in (centres, vertices))
    ):
        raise ValueError("Quartic display map requires >=25 finite two-dimensional centres")
    offset, scale = centres.mean(axis=0), np.ptp(centres, axis=0)
    if np.any(scale <= 0):
        raise ValueError("Degenerate display coordinate extent")
    # FITPACK's ev clamps to the fitted rectangular knot domain. This is an
    # interpolation boundary rule, not a displacement/physical-state clamp.
    target_vertices = np.clip(vertices, centres.min(axis=0), centres.max(axis=0))
    c, v = (a - offset for a in (centres, target_vertices))
    c, v = c / scale, v / scale
    design = np.polynomial.polynomial.polyvander2d(c[:, 0], c[:, 1], (4, 4)).reshape(len(c), 25)
    target = np.polynomial.polynomial.polyvander2d(v[:, 0], v[:, 1], (4, 4)).reshape(len(v), 25)
    solution, _, rank, _ = np.linalg.lstsq(design, np.eye(len(c)), rcond=1e-15)
    if rank != 25:
        raise ValueError("Rank-deficient quartic display fit")
    return target @ solution


def display(displacement_m, interpolation, original_vertices_m, cell_vertex_weights, *, xp=jnp):
    """Native visualization assignment only; no live physical world is rebuilt."""
    d, matrix, original, weights = (
        xp.asarray(v)
        for v in (displacement_m, interpolation, original_vertices_m, cell_vertex_weights)
    )
    if (
        d.ndim < 2
        or d.shape[-2] != 2
        or matrix.ndim != 2
        or matrix.shape[1] != d.shape[-1]
        or original.shape != (matrix.shape[0], 2)
        or weights.shape != (d.shape[-1], matrix.shape[0])
    ):
        raise ValueError("Explicit displacement/interpolation/vertex owner axes mismatch")
    vertices = original + xp.einsum("vn,...an->...va", matrix, d)
    centres = xp.einsum("nv,...va->...na", weights, vertices)
    return DisplayResult(vertices, centres)


def display_domain_valid(
    displacement_m, interpolation, original_vertices_m, cell_vertex_weights, *, xp=jnp
):
    """Finite explicit display geometry and normalized nonnegative owner weights."""
    try:
        values = [
            xp.asarray(v)
            for v in (displacement_m, interpolation, original_vertices_m, cell_vertex_weights)
        ]
        if not all(_real(v) for v in values):
            return xp.asarray(False)
        result = display(*values, xp=xp)
        valid = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in (*values, *result)]))
        weights = values[-1]
        valid &= xp.all(weights >= 0)
        valid &= xp.all(xp.abs(xp.sum(weights, axis=-1) - 1.0) <= 8 * np.finfo(float).eps)
        return valid
    except (ValueError, TypeError, IndexError, AttributeError):
        return xp.asarray(False)
