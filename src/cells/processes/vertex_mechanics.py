"""Apical vertex mechanics: geometry, energy, box stress and a step bound.

Pure functions of vertex positions, padded periodic topology and per-junction or
per-cell parameters, written for numpy (host checks) and jax.numpy (device steps).

Energy (Farhadifar et al. 2007, Curr Biol 17:2095, Box 1;
doi:10.1016/j.cub.2007.11.049):

    E = sum_c K_c/2 (A_c - A0_c)^2 + sum_j Lambda_j l_j + sum_c Gamma_c/2 L_c^2

A, L are cell area and perimeter and l a junction's length. Cells are polygons of
half-edges (one per corner, counterclockwise); corner positions are unwrapped
through integer periodic images, u_h = x[tail] + B m_h - x[ref(cell)], where B's
columns are the two periodic vectors and m_h the corner's image relative to the
cell's first corner. Junction vectors are x[head] + B n_j - x[tail]. Topology is
data (padded arrays with active masks), never closed over, so one compiled kernel
serves any tissue of the same capacities.

Norms are guarded (sqrt of 1 on padding), so padded slots never produce NaN
gradients. Active junctions shorter than the declared floor are outside the
model's domain (an edge collapse needs a T1 transition, which is not modelled)
and must be refused before a gradient is used.

Step bound. For the overdamped law eta_v dx_v/dt = F_v the explicit methods need
dt * lambda_max(eta^-1 H) bounded. hessian_rate() returns
rho = max_v (1/eta_v) sum_{terms t touching v} b_t >= lambda_max(eta^-1 H), a
block-Gershgorin bound over energy terms (x^T H x = sum_t x_t^T H_t x_t <=
sum_v |x_v|^2 sum_{t ni v} b_t), with per-term bounds on ||H_t||:
  junction  b = 2 |Lambda_j| / l_j                       (Hessian of Lambda l)
  perimeter b = Gamma_c (4 n_c + 4 L_c / min_k l_k)      (Gamma grad L grad L^T + Gamma L Hess L)
  area      b = K_c (sum_k l_k^2 + |A_c - A0_c|)         (K grad A grad A^T + K (A - A0) Hess A)
using |grad_k L| <= 2, ||Hess l|| = 2/l, |grad A|^2 <= sum_k l_k^2 and ||Hess A|| <= 1
for the shoelace area. Corners repeated within one small periodic cell are counted
once per corner, which keeps the bound valid.
"""

from typing import Any, NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

TWO_PI = 2.0 * np.pi
# Exact vertex winding is 2 pi; a fold-over changes the sum by a multiple of 2 pi.
ANGLE_SUM_ATOL = 1e-6


class Topology(NamedTuple):
    """Padded periodic topology (indices are slots; masks mark real entries)."""

    vertex_active: Any  # [V] bool
    he_tail: Any  # [H] vertex slot of the half-edge's corner
    he_next: Any  # [H] half-edge slot of the next corner of the same cell
    he_prev: Any  # [H] half-edge slot of the previous corner
    he_cell: Any  # [H] cell slot
    he_junction: Any  # [H] junction slot
    he_image: Any  # [H, 2] corner image relative to the cell's first corner (float64 integers)
    he_active: Any  # [H] bool
    cell_reference: Any  # [C] vertex slot of the cell's first corner
    cell_active: Any  # [C] bool
    junction_tail: Any  # [J] vertex slot
    junction_head: Any  # [J] vertex slot
    junction_image: Any  # [J, 2] image of the head relative to the tail (float64 integers)
    junction_active: Any  # [J] bool


class Mechanics(NamedTuple):
    """Energy parameters in effect (reduced units: sqrt(A0), K A0^2)."""

    line_tension: Any  # [J] Lambda_j (signed)
    contractility: Any  # [C] Gamma_c >= 0
    area_elasticity: Any  # [C] K_c > 0
    preferred_area: Any  # [C] A0_c > 0


class Geometry(NamedTuple):
    area: Any  # [C] signed shoelace area of each active cell (0 on padding)
    perimeter: Any  # [C]
    length: Any  # [J] junction lengths (0 on padding)
    junction_vector: Any  # [J, 2]
    corner: Any  # [H, 2] unwrapped corner position relative to the cell's first corner


def scatter_add(values, index, size, *, xp=jnp):
    if xp is jnp:
        return jnp.zeros((size,) + values.shape[1:], values.dtype).at[index].add(values)
    result = np.zeros((size,) + values.shape[1:], values.dtype)
    np.add.at(result, index, values)
    return result


def scatter_min(values, index, size, fill, *, xp=jnp):
    if xp is jnp:
        return jnp.full((size,), fill, values.dtype).at[index].min(values)
    result = np.full((size,), fill, values.dtype)
    np.minimum.at(result, index, values)
    return result


def guarded_norm(vectors, active, *, xp=jnp):
    """|v| on active rows, exactly 0 on padding, with a finite gradient there."""
    squared = xp.sum(vectors * vectors, axis=-1)
    return xp.where(active, xp.sqrt(xp.where(active, squared, 1.0)), 0.0)


def cross(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def geometry(position, topology, box, *, xp=jnp):
    t = topology
    shift = t.junction_image @ box.T
    vector = position[t.junction_head] + shift - position[t.junction_tail]
    vector = xp.where(t.junction_active[:, None], vector, 0.0)
    length = guarded_norm(vector, t.junction_active, xp=xp)
    reference = position[t.cell_reference][t.he_cell]
    corner = position[t.he_tail] + t.he_image @ box.T - reference
    corner = xp.where(t.he_active[:, None], corner, 0.0)
    following = corner[t.he_next]
    size = t.cell_active.shape[0]
    twice = scatter_add(
        xp.where(t.he_active, cross(corner, following), 0.0), t.he_cell, size, xp=xp
    )
    perimeter = scatter_add(
        xp.where(t.he_active, length[t.he_junction], 0.0), t.he_cell, size, xp=xp
    )
    area = xp.where(t.cell_active, 0.5 * twice, 0.0)
    return Geometry(area, xp.where(t.cell_active, perimeter, 0.0), length, vector, corner)


def energy_terms(position, topology, box, mechanics, *, xp=jnp):
    """(area, perimeter, line) energies per cell, cell and junction; 0 on padding."""
    g = geometry(position, topology, box, xp=xp)
    t, m = topology, mechanics
    area = xp.where(t.cell_active, 0.5 * m.area_elasticity * (g.area - m.preferred_area) ** 2, 0.0)
    perimeter = xp.where(t.cell_active, 0.5 * m.contractility * g.perimeter**2, 0.0)
    line = xp.where(t.junction_active, m.line_tension * g.length, 0.0)
    return area, perimeter, line


def energy(position, topology, box, mechanics, *, xp=jnp):
    area, perimeter, line = energy_terms(position, topology, box, mechanics, xp=xp)
    return xp.sum(area) + xp.sum(perimeter) + xp.sum(line)


def energy_magnitude(position, topology, box, mechanics, *, xp=jnp):
    """Sum of absolute energy terms: the scale that rounding acts on."""
    area, perimeter, line = energy_terms(position, topology, box, mechanics, xp=xp)
    return xp.sum(xp.abs(area)) + xp.sum(xp.abs(perimeter)) + xp.sum(xp.abs(line))


def forces(position, topology, box, mechanics):
    """F = -dE/dx (jax.grad), zero on inactive vertices."""
    gradient = jax.grad(energy)(position, topology, box, mechanics)
    return jnp.where(topology.vertex_active[:, None], -gradient, 0.0)


def box_stress(position, topology, box, mechanics):
    """Tissue stress (1/det B) dE(x F^T, F B)/dF at F = I (tension positive)."""

    def strained(deformation):
        return energy(position @ deformation.T, topology, deformation @ box, mechanics)

    return jax.grad(strained)(jnp.eye(2, dtype=position.dtype)) / jnp.linalg.det(box)


def corner_angle_sums(position, topology, box, *, xp=jnp):
    """Per vertex, the sum of the interior angles of its cell corners.

    At a corner h the angle runs counterclockwise from the outgoing cell edge to
    the reversed incoming one, in (0, 2 pi). A valid embedding winds once (2 pi);
    a local fold-over changes the sum by a multiple of 2 pi.
    """
    t = topology
    g = geometry(position, topology, box, xp=xp)
    out = g.corner[t.he_next] - g.corner
    back = g.corner[t.he_prev] - g.corner
    angle = xp.mod(xp.arctan2(cross(out, back), xp.sum(out * back, axis=-1)), TWO_PI)
    return scatter_add(
        xp.where(t.he_active, angle, 0.0), t.he_tail, t.vertex_active.shape[0], xp=xp
    )


def domain_valid(position, topology, box, length_floor, *, xp=jnp):
    """Finite, positive areas, junctions at or above the floor, rotations preserved."""
    t = topology
    g = geometry(position, topology, box, xp=xp)
    sums = corner_angle_sums(position, topology, box, xp=xp)
    ok = xp.all(xp.isfinite(position))
    ok &= xp.all(xp.where(t.cell_active, g.area > 0, True))
    ok &= xp.all(xp.where(t.junction_active, g.length >= length_floor, True))
    ok &= xp.all(xp.where(t.vertex_active, xp.abs(sums - TWO_PI) <= ANGLE_SUM_ATOL, True))
    return ok


def hessian_rate(position, topology, box, mechanics, friction, *, xp=jnp):
    """rho >= lambda_max(eta^-1 H): the block-Gershgorin bound of the module docstring."""
    t, m = topology, mechanics
    g = geometry(position, topology, box, xp=xp)
    cells, vertices = t.cell_active.shape[0], t.vertex_active.shape[0]
    safe = xp.where(t.junction_active, g.length, 1.0)
    junction = xp.where(t.junction_active, 2.0 * xp.abs(m.line_tension) / safe, 0.0)
    he_length = g.length[t.he_junction]
    sides = scatter_add(xp.where(t.he_active, 1.0, 0.0), t.he_cell, cells, xp=xp)
    shortest = scatter_min(
        xp.where(t.he_active, he_length, np.inf), t.he_cell, cells, np.inf, xp=xp
    )
    squares = scatter_add(xp.where(t.he_active, he_length**2, 0.0), t.he_cell, cells, xp=xp)
    shortest = xp.where(t.cell_active, shortest, 1.0)
    cell = m.contractility * (4.0 * sides + 4.0 * g.perimeter / shortest)
    cell += m.area_elasticity * (squares + xp.abs(g.area - m.preferred_area))
    cell = xp.where(t.cell_active, cell, 0.0)
    total = scatter_add(junction, t.junction_tail, vertices, xp=xp)
    total += scatter_add(junction, t.junction_head, vertices, xp=xp)
    total += scatter_add(xp.where(t.he_active, cell[t.he_cell], 0.0), t.he_tail, vertices, xp=xp)
    rate = xp.where(t.vertex_active, total / xp.where(t.vertex_active, friction, 1.0), 0.0)
    return xp.max(rate)


def bounded_below(mechanics, topology, *, xp=np):
    """False if a cell without contractility borders a junction with negative tension.

    Then the energy is unbounded below (the junction lengthens without limit at
    fixed cell area), so no mechanical equilibrium exists.
    """
    t, m = topology, mechanics
    free = xp.where(t.cell_active, m.contractility == 0, False)
    negative = xp.where(t.junction_active, m.line_tension < 0, False)
    touching = xp.where(t.he_active, free[t.he_cell] & negative[t.he_junction], False)
    return not bool(xp.any(touching))
