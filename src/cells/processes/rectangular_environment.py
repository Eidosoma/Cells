"""Cells rectangular, cell-centred, homogeneous-Neumann Poisson convention.

Each physical axis has its own uniform spacing. Observed coordinates are
retained, never rescaled to BETSE's scalar stencil delta. The operator is the
conservative five-point Laplacian with zero normal flux at the outer faces.
It is separate from native BETSE source correspondence and from live tissue,
material, masked-domain, phase or checkpoint admission.

bind() computes one bounded dense inverse on the CPU using the same declared
constant-nullspace projection as Cells' uniform-grid compatible-gauge solver.
bind_metric() retains only validated geometry, without constructing a matrix or
inverse. It supplies the existing face stencils, not a Poisson solver.
The immutable kernels support batched NumPy/JAX array operations via ``xp``;
no GPU execution or performance is asserted by their presence.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np

from cells.processes import betse_native_grid_metric_audit as metric

LAW_ID = "cells.rectangular_zero_flux_poisson@1"
METRIC_LAW_ID = "cells.rectangular_zero_flux_metric@1"
MAX_POINTS = 625
MAX_METRIC_POINTS = 2**20
RHS_RTOL = 2e-12
COORDINATE_EPS_MULTIPLIER = 64


@dataclass(frozen=True)
class GridSpec:
    environment_ids: tuple
    shape: tuple  # ny, nx; full C-order rectangle only.
    bounds_m: tuple  # xmin, xmax, ymin, ymax.
    coordinates_m: object  # Supplied physical cell centres; no reconstruction.
    vertices_x_m: object
    vertices_y_m: object
    provenance: dict


@dataclass(frozen=True)
class GridBinding:
    environment_ids: tuple
    shape: tuple
    bounds_m: tuple
    spacing_xy_m: tuple
    coordinates_m: object
    vertices_x_m: object
    vertices_y_m: object
    cell_area_m2: float
    laplacian: object
    compatible_inverse: object
    provenance_json: str
    identity: str


@dataclass(frozen=True)
class MetricBinding:
    """Immutable physical geometry with O(number of cells) storage.

    No dense operator, inverse, live tissue ownership or material field is
    attached. The point limit is a host binding bound, not GPU qualification.
    """

    environment_ids: tuple
    shape: tuple
    bounds_m: tuple
    spacing_xy_m: tuple
    coordinates_m: object
    vertices_x_m: object
    vertices_y_m: object
    cell_area_m2: float
    provenance_json: str
    identity: str


class SolveResult(NamedTuple):
    potential: object  # Complete raw result, including any nonfinite values.
    residual: object  # Against the original input, never a mean-subtracted RHS.
    rhs_compatible: object  # Per batch row; false is an explicit refusal.
    finite_result: object

    @property
    def usable(self):
        """Compatibility and finiteness only; callers must assess residual accuracy."""
        return self.rhs_compatible & self.finite_result


def _frozen(value, shape, label):
    if type(value) is not np.ndarray or value.dtype != np.dtype("float64") or value.shape != shape:
        raise ValueError("Require complete float64 " + label)
    if not np.isfinite(value).all():
        raise ValueError("Require finite " + label)
    # A bytes backing store cannot have WRITEABLE switched back on by a caller.
    return np.frombuffer(value.tobytes(order="C"), dtype=np.float64).reshape(shape)


def spec_from_observation(audit, *, environment_ids):
    """Declare a new physical metric from retained native observations.

    Native audit consistency is necessary input evidence, not live ownership.
    A failed *scalar* metric is allowed here: each physical axis is validated
    separately by bind(). The original audit and native operators stay intact.
    """
    metric.validate(audit)
    if dict(audit.boundaries) != dict.fromkeys(metric.SIDES, "flux"):
        raise ValueError("Only the complete homogeneous all-flux rectangle is declared")
    record = audit.record
    if not record["selected_native_observation_checks_passed"]:
        raise ValueError("Retained native coordinate/mapping observations are inconsistent")
    raw = audit.observation
    return GridSpec(
        environment_ids,
        raw.shape,
        raw.bounds_m,
        np.array(raw.coordinates_m, dtype=np.float64),
        np.array(raw.vertices_x_m, dtype=np.float64),
        np.array(raw.vertices_y_m, dtype=np.float64),
        dict(
            source_observation_identity=audit.identity,
            source_receipt=raw.source_receipt,
            retained_native_scalar_delta_m=raw.delta_m,
            retained_native_uniform_metric_passed=record["uniform_metric_passed"],
            metric_convention=LAW_ID,
            native_source_equivalence=False,
            native_owner_or_physical_tissue_admission=False,
        ),
    )


def _validated_metric(spec, point_limit):
    """Shared coordinate validation; neither route repairs or resamples inputs."""
    if type(spec) is not GridSpec:
        raise ValueError("Require an explicit rectangular-grid specification")
    shape = spec.shape
    if (
        type(shape) is not tuple
        or len(shape) != 2
        or any(type(n) is not int or n < 2 for n in shape)
        or math.prod(shape) > point_limit
    ):
        raise ValueError(f"Require ny,nx>=2 with at most{point_limit} physical grid cells")
    n = math.prod(shape)
    ids = spec.environment_ids
    if (
        type(ids) is not tuple
        or len(ids) != n
        or any(type(x) is not str or not x for x in ids)
        or len(set(ids)) != n
    ):
        raise ValueError("Require one unique stable ID per C-order physical cell")
    bounds = spec.bounds_m
    if (
        type(bounds) is not tuple
        or len(bounds) != 4
        or any(type(x) is not float or not math.isfinite(x) for x in bounds)
    ):
        raise ValueError("Require four retained finite binary64 bounds")
    xmin, xmax, ymin, ymax = bounds
    ny, nx = shape
    dx, dy = (xmax - xmin) / nx, (ymax - ymin) / ny
    if any(not math.isfinite(d) or d <= 0 for d in (dx, dy)):
        raise ValueError("Require increasing bounds and resolved positive physical spacings")
    area = dx * dy
    squares = (dx * dx, dy * dy)
    if any(not math.isfinite(v) or v <= 0 for v in (area, *squares)):
        raise ValueError("Unrepresentable physical cell area or squared spacing")
    cx, cy = (1.0 / value for value in squares)
    if any(not math.isfinite(v) or v <= 0 for v in (cx, cy)):
        raise ValueError("Unrepresentable physical stencil coefficient")
    points = _frozen(spec.coordinates_m, (n, 2), "physical centres")
    vx = _frozen(spec.vertices_x_m, (nx + 1,), "physical x vertices")
    vy = _frozen(spec.vertices_y_m, (ny + 1,), "physical y vertices")
    tolerances = []
    for axis, lo, hi, count, spacing in ((vx, xmin, xmax, nx, dx), (vy, ymin, ymax, ny, dy)):
        tolerance = COORDINATE_EPS_MULTIPLIER * np.finfo(float).eps * max(abs(lo), abs(hi), spacing)
        # A rounding allowance must not span a significant part of a cell.
        # Refuse poorly resolved coordinates instead of using their offset to
        # accept duplicate/reordered centres or widening the other axis' gate.
        if tolerance >= spacing / 4:
            raise ValueError("Physical coordinates are unresolved at the declared cell spacing")
        tolerances.append(tolerance)
        if axis[0] != lo or axis[-1] != hi or not np.all(np.diff(axis) > 0):
            raise ValueError("Retain increasing physical vertices with exact bound endpoints")
        expected = lo + np.arange(count + 1) * spacing
        if not np.allclose(axis, expected, rtol=0, atol=tolerance) or not np.allclose(
            np.diff(axis), spacing, rtol=metric.UNIFORM_RTOL, atol=0
        ):
            raise ValueError("Nonuniform per-axis spacing is outside the declared metric")
    # Use retained adjacent vertices to check actual centres, with no sorting or
    # replacing input coordinates by an idealized scalar-delta grid.
    centres = np.array(
        [[(vx[j] + vx[j + 1]) / 2, (vy[i] + vy[i + 1]) / 2] for i, j in np.ndindex(shape)]
    )
    if not np.allclose(points, centres, rtol=0, atol=np.array(tolerances)):
        raise ValueError("Physical centres disagree with retained C-order vertex midpoints")
    plane = points.reshape(ny, nx, 2)
    if not (
        np.all((plane[:, :, 0] > vx[:-1]) & (plane[:, :, 0] < vx[1:]))
        and np.all((plane[:, :, 1] > vy[:-1, None]) & (plane[:, :, 1] < vy[1:, None]))
        and np.all(np.diff(plane[:, :, 0], axis=1) > 0)
        and np.all(np.diff(plane[:, :, 1], axis=0) > 0)
    ):
        raise ValueError("Require ordered centres strictly inside their physical cells")
    if type(spec.provenance) is not dict or not spec.provenance:
        raise ValueError("Require explicit grid-data provenance")
    provenance = json.dumps(spec.provenance, sort_keys=True, separators=(",", ":"), allow_nan=False)

    header = json.dumps(
        dict(
            law=METRIC_LAW_ID,
            ids=ids,
            shape=shape,
            bounds=bounds,
            spacing_xy=(dx, dy),
            provenance=provenance,
        ),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    digest = hashlib.sha256(header)
    for array in (points, vx, vy):
        digest.update(array.tobytes(order="C"))
    return MetricBinding(
        ids, shape, bounds, (dx, dy), points, vx, vy, area, provenance, digest.hexdigest()
    )


def bind_metric(spec):
    """Validate a complete rectangle without allocating a dense matrix/inverse.

    Uses exactly the dense route's per-axis spacing, coordinate-resolution,
    stable-ID, finiteness and provenance requirements, with a separate limit of
    2**20 cells. Only retained geometry is issued. Use the face-stencil module
    for gradients, divergence and Laplacian action; dense solve() refuses this
    type. No solve, GPU execution or live-tissue admission is implied.
    """
    return _validated_metric(spec, MAX_METRIC_POINTS)


def bind(spec):
    """Build physical dx/dy coefficients without altering supplied grid data.

    Uniform per-axis rectangles only. Irregular spacing, holes, mixed/value
    boundaries, heterogeneous conductivity and nonzero boundary flux are outside
    this law. The new inverse is never substituted for a retained native inverse.
    The existing 625-cell bound, numerical construction and identity are retained.
    """
    geometry = _validated_metric(spec, MAX_POINTS)
    ids, shape, bounds = geometry.environment_ids, geometry.shape, geometry.bounds_m
    n = math.prod(shape)
    ny, nx = shape
    dx, dy = geometry.spacing_xy_m
    area = geometry.cell_area_m2
    points, vx, vy = geometry.coordinates_m, geometry.vertices_x_m, geometry.vertices_y_m
    provenance = geometry.provenance_json
    cx, cy = (1.0 / value for value in (dx * dx, dy * dy))

    matrix = np.zeros((n, n), dtype=np.float64)
    for i, j in np.ndindex(shape):
        here = i * nx + j
        for ii, jj, coefficient in ((i, j + 1, cx), (i + 1, j, cy)):
            if ii < ny and jj < nx:
                other = ii * nx + jj
                matrix[here, other] = matrix[other, here] = coefficient
                matrix[here, here] -= coefficient
                matrix[other, other] -= coefficient
    if not np.isfinite(matrix).all():
        raise ValueError("Unrepresentable physical Laplacian")
    # Stabilize dimensions before the same declared-nullspace construction used
    # by betse_geometry.bind_grid: P inv(M-J/n) P / scale. No rank-cutoff pinv.
    scale = max(cx, cy)
    constant = np.ones((n, n), dtype=np.float64) / n
    projection = np.eye(n) - constant
    inverse = projection @ np.linalg.inv(matrix / scale - constant) @ projection / scale
    matrix = _frozen(matrix, (n, n), "physical Laplacian")
    inverse = _frozen(inverse, (n, n), "compatible inverse")
    header = json.dumps(
        dict(
            law=LAW_ID,
            ids=ids,
            shape=shape,
            bounds=bounds,
            spacing_xy=(dx, dy),
            provenance=provenance,
        ),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    digest = hashlib.sha256(header)
    for array in (points, vx, vy, matrix, inverse):
        digest.update(array.tobytes(order="C"))
    return GridBinding(
        ids,
        shape,
        bounds,
        (dx, dy),
        points,
        vx,
        vy,
        area,
        matrix,
        inverse,
        provenance,
        digest.hexdigest(),
    )


def _field(values, grid, xp):
    if type(grid) is not GridBinding:
        raise ValueError("Require the separate rectangular-grid binding")
    values = xp.asarray(values)
    if (
        values.ndim < 1
        or values.shape[-1] != len(grid.environment_ids)
        or str(values.dtype) != "float64"
    ):
        raise ValueError("Require binary64 fields with the grid axis last")
    return values


def apply(values, grid, *, xp=np):
    """Batched physical Laplacian; pure array action with no Python per-cell work."""
    values = _field(values, grid, xp)
    return values @ xp.asarray(grid.laplacian).T


def solve(rhs, grid, *, xp=np):
    """Return raw batched candidates and explicit validity, suitable for JIT.

    A false usable flag refuses that row; callers must check it before use.
    Array evaluation still occurs for refused rows and is not counted as a
    successful solve. The original RHS is never projected or mean-subtracted.
    No new residual-acceptance tolerance is imposed here.
    """
    values = _field(rhs, grid, xp)
    magnitude = xp.max(xp.abs(values), axis=-1, keepdims=True)
    scaled = values / xp.where(magnitude > 0, magnitude, 1.0)
    compatible = xp.all(xp.isfinite(values), axis=-1) & (
        xp.abs(xp.sum(scaled, axis=-1)) <= RHS_RTOL * xp.sum(xp.abs(scaled), axis=-1)
    )
    potential = values @ xp.asarray(grid.compatible_inverse).T
    residual = apply(potential, grid, xp=xp) - values
    finite = xp.all(xp.isfinite(potential), axis=-1) & xp.all(xp.isfinite(residual), axis=-1)
    return SolveResult(potential, residual, compatible, finite)
