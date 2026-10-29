"""Explicit pinned-native geometry ownership and CPU/JAX operator binding.

Native geometry generation is external and provenance-bearing. This module
binds its declared topology/coordinates, recomputes measures and operators, and
keeps source radial volumes distinct from polygon volumes. No amount, charge,
geometry generation, cut execution or checkpoint migration happens here.
"""

import hashlib
import json
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

LAW_ID = "betse_geometry_source_v1_5_0@1"
MAX_CELLS = 256
MAX_DUAL_VERTICES = 1024
MAX_EDGES = 1536
MAX_GRID_CELLS = 1024


def _freeze(value, dtype=None):
    result = np.array(value, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _ids(values):
    if (
        not isinstance(values, (tuple, list))
        or not values
        or any(not isinstance(v, str) or not v for v in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError("Require an explicit nonempty axis of unique stable string IDs")
    return tuple(values)


def _finite(value, shape):
    result = np.asarray(value)
    if result.shape != shape or result.dtype.kind not in "fiu" or not np.isfinite(result).all():
        raise ValueError("Require declared finite numeric geometry axes")
    return _freeze(result, float)


def _positive(value):
    return (
        isinstance(value, Real)
        and not isinstance(value, (bool, np.bool_))
        and np.isfinite(value)
        and value > 0
    )


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _provenance(value):
    if not isinstance(value, dict) or not value:
        raise ValueError("Explicit geometry generation/seed provenance is required")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def polygon_measure(points):
    """Positive CCW signed area and centroid; no polygon repair/reorientation."""
    p = np.asarray(points)
    if p.ndim != 2 or p.shape[1] != 2 or p.shape[0] < 3:
        raise ValueError("Require a nondegenerate CCW polygon")
    p = _finite(p, p.shape)
    if len(np.unique(p, axis=0)) != len(p):
        raise ValueError("Duplicate polygon vertices are unsupported")
    q = np.roll(p, -1, axis=0)
    cross = p[:, 0] * q[:, 1] - q[:, 0] * p[:, 1]
    area = np.sum(cross) / 2
    scale = max(float(np.ptp(p, axis=0).max()), np.finfo(float).tiny)
    if area <= 32 * np.finfo(float).eps * scale**2:
        raise ValueError("Require positive resolved CCW polygon area")

    def orientation(a, b, c):
        u, v = b - a, c - a
        return u[0] * v[1] - u[1] * v[0]

    for i in range(len(p)):
        for j in range(i + 2, len(p)):
            if i == 0 and j == len(p) - 1:
                continue
            a, b, c, d = p[i], q[i], p[j], q[j]
            if (
                orientation(a, b, c) * orientation(a, b, d) < 0
                and orientation(c, d, a) * orientation(c, d, b) < 0
            ):
                raise ValueError("Self-intersecting polygons are unsupported")
    # Preserve native coordinate-wise summation/reciprocal order; tiny centroid
    # roundoff becomes visible when normals multiply large derivative probes.
    centre = np.asarray(
        [(1 / (6 * area)) * np.sum((p[:, axis] + q[:, axis]) * cross) for axis in (0, 1)]
    )
    return float(area), _freeze(centre)


def _pairs(values, ids):
    rows = tuple(tuple(row) for row in values)
    if any(len(row) != 2 or row[0] == row[1] or any(v not in ids for v in row) for row in rows):
        raise ValueError("Edges require two distinct explicit stable vertex IDs")
    return _freeze([[ids.index(a), ids.index(b)] for a, b in rows], int)


def _faces(values, ids):
    result = []
    for row in values:
        if len(row) < 3 or len(set(row)) != len(row) or any(v not in ids for v in row):
            raise ValueError("Faces require ordered nonrepeating stable vertex IDs")
        result.append(tuple(ids.index(v) for v in row))
    return tuple(result)


def _incidence(edges, count):
    result = np.zeros((len(edges), count))
    for i, (a, b) in enumerate(edges):
        result[i, a], result[i, b] = -1, 1
    return result


def _face_incidence(faces, edges, *, reverse=False):
    lookup = {}
    for i, (a, b) in enumerate(edges):
        # Explicit duplicate dual edges are rejected before building operators.
        lookup[(int(a), int(b))] = (i, 1)
        lookup[(int(b), int(a))] = (i, -1)
    result = np.zeros((len(faces), len(edges)))
    missing = []
    for i, face in enumerate(faces):
        other = face[-1:] + face[:-1] if reverse else face[1:] + face[:1]
        for a, b in zip(face, other, strict=True):
            if (a, b) in lookup:
                edge, sign = lookup[(a, b)]
                result[i, edge] = sign
            else:
                missing.append((i, a, b))
    return result, tuple(missing)


def _components(edges, count):
    remaining = set(range(count))
    result = []
    while remaining:
        found, frontier = set(), [min(remaining)]
        while frontier:
            at = frontier.pop()
            if at in found:
                continue
            found.add(at)
            frontier.extend(int(b if a == at else a) for a, b in edges if a == at or b == at)
        remaining -= found
        result.append([i in found for i in range(count)])
    return _freeze(result, bool)


@dataclass(frozen=True)
class MeshSpec:
    cell_ids: tuple  # Primal vertex owners; positions differ from cell centroids.
    edge_ids: tuple  # One declared primal/dual edge pairing per index.
    face_ids: tuple
    dual_vertex_ids: tuple
    primal_points_m: object
    primal_edges: tuple
    primal_faces: tuple
    dual_points_m: object
    dual_edges: tuple
    dual_cells: tuple  # One CCW polygon per cell owner.
    boundary_cell_ids: tuple
    inner_dual_vertex_ids: tuple  # One native tri-face mapping, in face order.
    dual_control_area_m2: object  # Native repeated reference tri_sa_o, explicit.
    dual_control_face_ids: tuple  # Explicit reference-face owner for every dual vertex.
    auxiliary: bool
    source_seed_ids: tuple
    removed_seed_ids: tuple  # Explicit generation ledger, never an amount remap.
    provenance: dict


class MeshKernel(NamedTuple):
    primal_d0: object
    dual_d0: object
    primal_d1: object
    dual_d1: object  # Native interior rows embedded in all cell rows.
    primal_length_m: object
    dual_length_m: object
    primal_tangent: object
    dual_tangent: object
    cell_area_m2: object
    dual_control_area_m2: object
    face_area_m2: object
    inner_cell: object
    inner_dual: object
    lap_closed: object
    lap_interior: object
    dual_lap_closed: object
    dual_lap_interior: object
    source_inverse_closed: object
    source_inverse_interior: object
    dual_source_inverse_closed: object
    dual_source_inverse_interior: object
    density_pseudoinverse: object
    components: object


@dataclass(frozen=True)
class MeshBinding:
    cell_ids: tuple
    edge_ids: tuple
    face_ids: tuple
    dual_vertex_ids: tuple
    primal_points_m: object
    dual_points_m: object
    primal_edges: object
    dual_edges: object
    primal_faces: tuple
    dual_cells: tuple
    centres_m: object
    auxiliary: bool
    missing_dual_face_steps: tuple
    source_seed_ids: tuple
    removed_seed_ids: tuple
    dual_control_face_ids: tuple
    kernel: MeshKernel
    provenance_json: str
    identity: str


def bind_mesh(spec):
    ids, edge_ids, face_ids, dual_ids = (
        _ids(v) for v in (spec.cell_ids, spec.edge_ids, spec.face_ids, spec.dual_vertex_ids)
    )
    if len(ids) > MAX_CELLS or len(dual_ids) > MAX_DUAL_VERTICES or len(edge_ids) > MAX_EDGES:
        raise ValueError("Mesh exceeds bounded dense geometry axes")
    source_ids = _ids(spec.source_seed_ids)
    removed_ids = tuple(spec.removed_seed_ids)
    if (
        len(set(removed_ids)) != len(removed_ids)
        or any(v not in source_ids for v in removed_ids)
        or set(ids) != set(source_ids) - set(removed_ids)
    ):
        raise ValueError(
            "Retained/removed stable seeds must partition the declared generation owners"
        )
    points = _finite(spec.primal_points_m, (len(ids), 2))
    dual_points = _finite(spec.dual_points_m, (len(dual_ids), 2))
    if len(np.unique(points, axis=0)) != len(points) or len(np.unique(dual_points, axis=0)) != len(
        dual_points
    ):
        raise ValueError("Coincident retained vertices require an explicit removal/merge decision")
    edges, dual_edges = _pairs(spec.primal_edges, ids), _pairs(spec.dual_edges, dual_ids)
    if len(edges) != len(edge_ids) or len(dual_edges) != len(edges):
        raise ValueError("Primal/dual edge pairing must match explicit edge IDs")
    for collection in (edges, dual_edges):
        if len({tuple(sorted(row)) for row in collection}) != len(collection):
            raise ValueError(
                "Duplicate paired edges are unsupported; retain native failure evidence"
            )
    faces, cells = _faces(spec.primal_faces, ids), _faces(spec.dual_cells, dual_ids)
    if len(faces) != len(face_ids) or len(cells) != len(ids) or type(spec.auxiliary) is not bool:
        raise ValueError("Face/cell/auxiliary axes must be explicit")
    measures = [polygon_measure(dual_points[list(row)]) for row in cells]
    areas, centres = np.asarray([v[0] for v in measures]), np.asarray([v[1] for v in measures])
    face_areas = np.asarray([polygon_measure(points[list(row)])[0] for row in faces])
    dual_areas = _finite(spec.dual_control_area_m2, (len(dual_ids),))
    if np.any(dual_areas <= 0):
        raise ValueError("Native dual control areas must be positive explicit measures")
    control_faces = tuple(spec.dual_control_face_ids)
    if len(control_faces) != len(dual_ids) or any(v not in face_ids for v in control_faces):
        raise ValueError("Every repeated dual control measure needs its explicit face owner")
    if not np.allclose(
        dual_areas, [face_areas[face_ids.index(v)] for v in control_faces], rtol=6e-12, atol=0
    ):
        raise ValueError("Dual control measure does not match its declared reference face")
    boundary = tuple(spec.boundary_cell_ids)
    if len(set(boundary)) != len(boundary) or any(v not in ids for v in boundary):
        raise ValueError("Invalid explicit primal boundary owners")
    inner = np.asarray([i for i, v in enumerate(ids) if v not in boundary], int)
    inner_dual_ids = tuple(spec.inner_dual_vertex_ids)
    if len(inner_dual_ids) != len(faces) or any(v not in dual_ids for v in inner_dual_ids):
        raise ValueError("Explicit face-to-dual-vertex ownership is required")
    inner_dual = np.asarray([dual_ids.index(v) for v in inner_dual_ids], int)
    if len(set(inner_dual_ids)) != len(inner_dual_ids):
        raise ValueError("Ambiguous face-to-dual-vertex ownership")
    d0, v0 = _incidence(edges, len(ids)), _incidence(dual_edges, len(dual_ids))
    d1, missing = _face_incidence(faces, edges)
    if missing or np.any(d1 @ d0 != 0):
        raise ValueError("Primal faces require complete oriented edge boundaries")
    dual_small, missing_dual = _face_incidence(
        tuple(cells[i] for i in inner), dual_edges, reverse=True
    )
    dual1 = np.zeros((len(ids), len(edges)))
    dual1[inner] = dual_small
    lengths = np.linalg.norm(points[edges[:, 1]] - points[edges[:, 0]], axis=-1)
    dual_lengths = np.linalg.norm(
        dual_points[dual_edges[:, 1]] - dual_points[dual_edges[:, 0]], axis=-1
    )
    if np.any(lengths <= 0) or np.any(dual_lengths <= 0):
        raise ValueError("Paired edge lengths must be positive")
    tangents = (points[edges[:, 1]] - points[edges[:, 0]]) / lengths[:, None]
    dual_tangents = (dual_points[dual_edges[:, 1]] - dual_points[dual_edges[:, 0]]) / dual_lengths[
        :, None
    ]
    closed = (-d0.T * (dual_lengths / lengths)[None, :]) @ d0 / areas[:, None]
    interior = (dual1 * (dual_lengths / lengths)[None, :]) @ d0 / areas[:, None]
    dual_closed = (-v0.T * (lengths / dual_lengths)[None, :]) @ v0 / dual_areas[:, None]
    dual_interior = np.zeros((len(dual_ids), len(dual_ids)))
    dual_interior[inner_dual] = (d1 * (lengths / dual_lengths)[None, :]) @ v0 / face_areas[:, None]
    d0inv, v0inv = np.linalg.pinv(d0), np.linalg.pinv(v0)
    source_inverse = (d0inv * (lengths / dual_lengths)[None, :]) @ (-d0inv.T * areas[None, :])
    source_open = np.zeros((len(ids), len(ids)))
    source_open[:, inner] = (d0inv * (lengths / dual_lengths)[None, :]) @ (
        np.linalg.pinv(dual_small) * areas[inner][None, :]
    )
    dual_inverse = (v0inv * (dual_lengths / lengths)[None, :]) @ (-v0inv.T * dual_areas[None, :])
    dual_open = np.zeros((len(dual_ids), len(dual_ids)))
    dual_open[:, inner_dual] = (v0inv * (dual_lengths / lengths)[None, :]) @ (
        np.linalg.pinv(d1) * face_areas[None, :]
    )
    scale = np.max(np.abs(closed))
    density_inverse = np.linalg.pinv(closed / scale) / scale
    kernel = MeshKernel(
        *(
            _freeze(v)
            for v in (
                d0,
                v0,
                d1,
                dual1,
                lengths,
                dual_lengths,
                tangents,
                dual_tangents,
                areas,
                dual_areas,
                face_areas,
                inner,
                inner_dual,
                closed,
                interior,
                dual_closed,
                dual_interior,
                source_inverse,
                source_open,
                dual_inverse,
                dual_open,
                density_inverse,
                _components(edges, len(ids)),
            )
        )
    )
    provenance = _provenance(spec.provenance)
    payload = dict(
        law_id=LAW_ID,
        cell_ids=ids,
        edge_ids=edge_ids,
        face_ids=face_ids,
        dual_vertex_ids=dual_ids,
        primal_points_m=points.tolist(),
        dual_points_m=dual_points.tolist(),
        primal_edges=edges.tolist(),
        dual_edges=dual_edges.tolist(),
        primal_faces=faces,
        dual_cells=cells,
        auxiliary=spec.auxiliary,
        source_seed_ids=source_ids,
        removed_seed_ids=removed_ids,
        dual_control_face_ids=control_faces,
        provenance=json.loads(provenance),
        kernel={k: v.tolist() for k, v in kernel._asdict().items()},
    )
    return MeshBinding(
        ids,
        edge_ids,
        face_ids,
        dual_ids,
        points,
        dual_points,
        edges,
        dual_edges,
        faces,
        cells,
        _freeze(centres),
        spec.auxiliary,
        missing_dual,
        source_ids,
        removed_ids,
        control_faces,
        kernel,
        provenance,
        _hash(payload),
    )


def _field(values, count, *, xp):
    value = xp.asarray(values)
    if value.ndim < 1 or value.shape[-1] != count or value.dtype.kind not in "fiu":
        raise ValueError("Field requires the declared final owner axis")
    return value


def _matvec(matrix, values, *, xp):
    value = _field(values, matrix.shape[-1], xp=xp)
    return xp.einsum("ij,...j->...i", xp.asarray(matrix), value)


def _domain(mesh, domain):
    if domain not in ("primal", "dual"):
        raise ValueError("Declare primal or dual vertex ownership")
    if domain == "dual" and not mesh.auxiliary:
        raise ValueError("Native world core-only mesh has no auxiliary dual operators")


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


@dataclass(frozen=True)
class GridSpec:
    environment_ids: tuple
    shape: tuple  # ny,nx; native flattened C order.
    bounds_m: tuple
    delta_m: float
    coordinates_m: object
    boundaries: dict  # Exact N,S,E,W source strings: flux/value.
    provenance: dict


class GridKernel(NamedTuple):
    laplacian: object
    pseudoinverse: object  # Literal native default SVD cutoff, including defects.
    compatible_inverse: object  # Separate Cells declared-nullspace solve.
    fixed_value_rows: object


@dataclass(frozen=True)
class GridBinding:
    environment_ids: tuple
    shape: tuple
    bounds_m: tuple
    delta_m: float
    coordinates_m: object
    boundaries: object
    kernel: GridKernel
    provenance_json: str
    identity: str


def bind_grid(spec):
    ids = _ids(spec.environment_ids)
    shape = tuple(spec.shape)
    bounds = _finite(spec.bounds_m, (4,))
    delta = spec.delta_m
    if (
        len(shape) != 2
        or any(type(v) is not int or v < 2 for v in shape)
        or np.prod(shape) != len(ids)
        or len(ids) > MAX_GRID_CELLS
        or not _positive(delta)
    ):
        raise ValueError("Grid requires explicit ny,nx>=2 and positive uniform spacing")
    ny, nx = shape
    xmin, xmax, ymin, ymax = bounds
    if (
        xmin >= xmax
        or ymin >= ymax
        or not np.allclose([(xmax - xmin) / nx, (ymax - ymin) / ny], delta, rtol=2e-14, atol=0)
    ):
        raise ValueError("Native truncated/nonintegral grid aspect is not a uniform metric")
    coords = _finite(spec.coordinates_m, (len(ids), 2))
    expected = np.array(
        [[xmin + (j + 0.5) * delta, ymin + (i + 0.5) * delta] for i in range(ny) for j in range(nx)]
    )
    tolerance = 64 * np.finfo(float).eps * max(float(np.max(np.abs(bounds))), delta)
    if not np.allclose(coords, expected, rtol=0, atol=tolerance):
        raise ValueError("Grid coordinates/order disagree with explicit C-order owner axes")
    bound = dict(spec.boundaries)
    if set(bound) != {"N", "S", "E", "W"} or any(
        v not in ("flux", "value") for v in bound.values()
    ):
        raise ValueError("Require all four explicit native flux/value boundary labels")
    matrix = np.zeros((len(ids), len(ids)))
    for i in range(ny):
        for j in range(nx):
            at = i * nx + j
            side = (
                ("S" if j == 0 else "E")
                if i == 0
                else (("N" if j == 0 else "E") if i == ny - 1 else None)
            )
            if side is not None and j not in (0, nx - 1):
                side = "S" if i == 0 else "N"
            if side is None:
                side = "W" if j == 0 else "E" if j == nx - 1 else None
            if side is not None and bound[side] == "value":
                matrix[at, at] = 1.0
            else:
                for ii, jj in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                    if 0 <= ii < ny and 0 <= jj < nx:
                        matrix[at, ii * nx + jj] = 1
                        matrix[at, at] -= 1
    # Boundary "value" rows are source identity/delta^2, not physical
    # potential data; callers must scale their boundary RHS consistently.
    inverse = np.linalg.pinv(matrix) * delta**2
    fixed = np.diag(matrix) > 0
    if np.any(fixed):
        compatible_inverse = np.linalg.inv(matrix) * delta**2
    else:
        constant = np.ones_like(matrix) / len(ids)
        projection = np.eye(len(ids)) - constant
        compatible_inverse = projection @ np.linalg.inv(matrix - constant) @ projection * delta**2
    kernel = GridKernel(
        _freeze(matrix / delta**2),
        _freeze(inverse),
        _freeze(compatible_inverse),
        _freeze(fixed),
    )
    provenance = _provenance(spec.provenance)
    identity = _hash(
        dict(
            ids=ids,
            shape=shape,
            bounds=bounds.tolist(),
            delta=delta,
            coords=coords.tolist(),
            bound=bound,
            provenance=json.loads(provenance),
        )
    )
    return GridBinding(
        ids,
        shape,
        tuple(bounds),
        float(delta),
        coords,
        MappingProxyType(bound),
        kernel,
        provenance,
        identity,
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


@dataclass(frozen=True)
class GeometrySpec:
    mesh: MeshBinding
    grid: GridBinding
    membrane_ids: tuple
    cell_membrane_ids: tuple
    partner_membrane_ids: tuple
    boundary_membrane_ids: tuple
    membrane_environment_ids: tuple
    cell_environment_ids: tuple
    shrink_factor: float
    height_m: float
    gap_m: float
    provenance: dict


class GeometryKernel(NamedTuple):
    owner: object
    partner: object
    environment_owner: object
    cell_environment_owner: object
    boundary: object
    membrane_edges_m: object
    membrane_midpoints_m: object
    membrane_normal: object
    membrane_tangent: object
    membrane_area_m2: object
    native_patch_volume_m3: object
    native_cell_volume_m3: object
    polygon_cell_volume_m3: object
    cell_surface_m2: object
    cell_sum: object
    environment_sum: object
    theta: object
    cell_gradient: object
    cell_mean: object
    environment_uniform_volume_m3: object
    environment_native_weighted_volume_m3: object
    contact_pairs: object


@dataclass(frozen=True)
class GeometryBinding:
    mesh: MeshBinding
    grid: GridBinding
    membrane_ids: tuple
    cell_membrane_ids: tuple
    cell_polygons_m: tuple
    height_m: float
    gap_m: float
    shrink_factor: float
    kernel: GeometryKernel
    provenance_json: str
    identity: str


def bind_geometry(spec):
    mesh, grid = spec.mesh, spec.grid
    ids = _ids(spec.membrane_ids)
    cell_ids = mesh.cell_ids
    env_ids = grid.environment_ids
    if (
        not _positive(spec.height_m)
        or not _positive(spec.gap_m)
        or not _positive(spec.shrink_factor)
        or spec.shrink_factor >= 1
    ):
        raise ValueError("Require positive height/gap and 0<shrink factor<1")
    groups = tuple(tuple(row) for row in spec.cell_membrane_ids)
    if len(groups) != len(cell_ids) or any(
        len(group) != len(face) for group, face in zip(groups, mesh.dual_cells, strict=True)
    ):
        raise ValueError("Every CCW cell edge requires its declared ordered membrane owner")
    flat = tuple(v for group in groups for v in group)
    if len(flat) != len(ids) or set(flat) != set(ids) or len(set(flat)) != len(flat):
        raise ValueError("Cell membrane groups must partition the stable membrane axis")
    partners = tuple(spec.partner_membrane_ids)
    if len(partners) != len(ids) or any(v not in ids for v in partners):
        raise ValueError("Explicit membrane partner owners required")
    partner = np.asarray([ids.index(v) for v in partners], int)
    if not np.array_equal(partner[partner], np.arange(len(ids))):
        raise ValueError(
            "Nonreciprocal native nearest contacts require an explicit contact decision"
        )
    boundary_ids = tuple(spec.boundary_membrane_ids)
    if len(set(boundary_ids)) != len(boundary_ids) or any(v not in ids for v in boundary_ids):
        raise ValueError("Explicit unique boundary membrane IDs required")
    boundary = np.asarray([v in boundary_ids for v in ids], bool)
    if np.any(boundary & (partner != np.arange(len(ids)))):
        raise ValueError("Boundary membrane cannot have a distinct contact partner")
    env = tuple(spec.membrane_environment_ids)
    cell_env = tuple(spec.cell_environment_ids)
    if (
        len(env) != len(ids)
        or len(cell_env) != len(cell_ids)
        or any(v not in env_ids for v in (*env, *cell_env))
    ):
        raise ValueError("Explicit grid environment owner maps required")
    env_index = np.asarray([env_ids.index(v) for v in env], int)
    cell_env_index = np.asarray([env_ids.index(v) for v in cell_env], int)
    owner = np.zeros(len(ids), int)
    edges = np.zeros((len(ids), 2, 2))
    polygons = []
    theta = np.zeros((len(ids), len(ids)))
    for i, (group, face) in enumerate(zip(groups, mesh.dual_cells, strict=True)):
        centre = mesh.centres_m[i]
        polygon = centre + spec.shrink_factor * (mesh.dual_points_m[list(face)] - centre)
        polygon_measure(polygon)
        polygons.append(_freeze(polygon))
        positions = np.asarray([ids.index(v) for v in group], int)
        owner[positions] = i
        edges[positions, 0] = np.roll(polygon, 1, axis=0)
        edges[positions, 1] = polygon
    mids = np.mean(edges, axis=1)
    vector = edges[:, 1] - edges[:, 0]
    length = np.linalg.norm(vector, axis=-1)
    tangent = vector / length[:, None]
    normal = np.column_stack((tangent[:, 1], -tangent[:, 0]))
    area = length * spec.height_m
    radius = np.linalg.norm(mids - mesh.centres_m[owner], axis=-1)
    patch = radius * area / 2
    if np.any(patch <= 0) or not np.isfinite(patch).all():
        raise ValueError("Require positive resolved native radial patch volumes")
    sums = np.zeros((len(cell_ids), len(ids)))
    sums[owner, np.arange(len(ids))] = 1
    cell_vol = sums @ patch
    cell_sa = sums @ area
    poly_vol = np.asarray([polygon_measure(p)[0] * spec.height_m for p in polygons])
    for group in groups:
        positions = np.asarray([ids.index(v) for v in group], int)
        previous = np.roll(positions, 1)
        distance = np.linalg.norm(mids[positions] - mids[previous], axis=-1)
        if np.any(distance <= 0):
            raise ValueError("Repeated membrane midpoint invalidates circumference derivative")
        theta[positions, positions] = 1 / distance
        theta[positions, previous] = -1 / distance
    gradient = np.zeros_like(sums.T)
    mean = np.zeros_like(gradient)
    for i, j in enumerate(partner):
        a, b = owner[i], owner[j]
        mean[i, a] += 0.5
        mean[i, b] += 0.5
        if a != b:
            distance = np.linalg.norm(mesh.centres_m[b] - mesh.centres_m[a])
            if distance <= 0:
                raise ValueError("Distinct cell centroids coincide")
            gradient[i, a] = -1 / distance
            gradient[i, b] = 1 / distance
    contacts = np.asarray([(i, int(j)) for i, j in enumerate(partner) if i < j], int).reshape(
        (-1, 2)
    )
    if contacts.size and (
        np.any(owner[contacts[:, 0]] == owner[contacts[:, 1]])
        or not np.allclose(area[contacts[:, 0]], area[contacts[:, 1]], rtol=2e-12, atol=0)
        or not np.allclose(normal[contacts[:, 0]], -normal[contacts[:, 1]], rtol=0, atol=2e-12)
    ):
        raise ValueError(
            "Paired contact owners/areas/normals do not define a conservative interface"
        )
    env_sum = np.zeros((len(env_ids), len(ids)))
    env_sum[env_index, np.arange(len(ids))] = 1
    uniform = np.full(len(env_ids), grid.delta_m**2 * spec.height_m)
    surfaces = env_sum @ area
    occupied = np.sum(env_sum, axis=1) > 0
    weighted = np.where(occupied, surfaces * spec.gap_m / 2, uniform)
    for coords, indices in ((mids, env_index), (mesh.centres_m, cell_env_index)):
        distance = np.sum((coords[:, None, :] - grid.coordinates_m[None, :, :]) ** 2, axis=-1)
        chosen = distance[np.arange(len(coords)), indices]
        tolerance = 128 * np.finfo(float).eps * np.maximum(distance.max(axis=-1), grid.delta_m**2)
        if np.any(chosen > distance.min(axis=-1) + tolerance):
            raise ValueError(
                "Declared nearest native environment owner is geometrically inconsistent"
            )
    kernel = GeometryKernel(
        *(
            _freeze(v)
            for v in (
                owner,
                partner,
                env_index,
                cell_env_index,
                boundary,
                edges,
                mids,
                normal,
                tangent,
                area,
                patch,
                cell_vol,
                poly_vol,
                cell_sa,
                sums,
                env_sum,
                theta,
                gradient,
                mean,
                uniform,
                weighted,
                contacts,
            )
        )
    )
    provenance = _provenance(spec.provenance)
    identity = _hash(
        dict(
            law_id=LAW_ID,
            mesh=mesh.identity,
            grid=grid.identity,
            membrane_ids=ids,
            groups=groups,
            height=spec.height_m,
            gap=spec.gap_m,
            shrink=spec.shrink_factor,
            provenance=json.loads(provenance),
            kernel={k: v.tolist() for k, v in kernel._asdict().items()},
        )
    )
    return GeometryBinding(
        mesh,
        grid,
        ids,
        groups,
        tuple(polygons),
        float(spec.height_m),
        float(spec.gap_m),
        float(spec.shrink_factor),
        kernel,
        provenance,
        identity,
    )


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


def geometry_manifest(geometry):
    """Identity/ownership metadata, never a physical state checkpoint."""
    k = geometry.kernel
    return dict(
        law_id=LAW_ID,
        identity=geometry.identity,
        mesh_identity=geometry.mesh.identity,
        grid_identity=geometry.grid.identity,
        cell_ids=geometry.mesh.cell_ids,
        membrane_ids=geometry.membrane_ids,
        environment_ids=geometry.grid.environment_ids,
        cell_membrane_ids=geometry.cell_membrane_ids,
        membrane_cell_ids=tuple(geometry.mesh.cell_ids[i] for i in k.owner),
        partner_membrane_ids=tuple(geometry.membrane_ids[i] for i in k.partner),
        membrane_environment_ids=tuple(
            geometry.grid.environment_ids[i] for i in k.environment_owner
        ),
        provenance=json.loads(geometry.provenance_json),
    )


def validate_geometry_manifest(manifest, geometry):
    expected = geometry_manifest(geometry)
    if manifest != expected and manifest != json.loads(json.dumps(expected)):
        raise ValueError("Stale geometry/owner/operator identity")
    return expected


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
