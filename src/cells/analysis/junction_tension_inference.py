"""junction_tension_inference@1: junction tensions and cell pressures from tissue geometry.

An opt-in, read-only analysis (numpy) of a polygonal apical tissue in mechanical
equilibrium with straight junctions. At each vertex v the force balance is linear
in the unknowns,

    F_v = sum_{j at v} T_j u_j(v) + sum_{c at v} P_c grad_v A_c = 0,

where u_j(v) is the unit vector along junction j away from v, grad_v A_c =
1/2 J (x_next - x_prev) the derivative of the cell's shoelace area, T_j the total
junction tension and P_c the cell pressure. For the apical vertex energy,
T_j = Lambda_j + Gamma_a L_a + Gamma_b L_b and P_c = -K_c (A_c - A0_c). The
geometry determines T only up to an overall scale (the system is homogeneous) and
P up to scale plus a uniform offset (sum_{c at v} grad_v A_c = 0 because the cells
tile the periodic box). Lambda_j is recovered only when Gamma is known, because
line tension and contractility are degenerate in a single geometry (Godolphim
2025, arXiv:2508.18470). Straight junctions also leave every cell a near-null
pressure-tension mode on near-regular geometry, so the joint problem can be badly
conditioned (Chiou et al. 2012, PLoS Comput Biol 8:e1002512; Noll et al. 2020,
PRX 10:011072); the singular spectrum is reported.

Methods:
* known_pressure: least squares for T with P given.
* joint: least squares for (T, P) with the gauges fixed by the mean tension and
  the mean pressure; the null-space dimension at a relative SVD threshold and the
  condition number beyond the two gauges are reported.
* bayesian: Gaussian prior T ~ N(1, sigma^2/mu I) (tensions near uniform, which
  also sets the scale) with the pressures profiled out, data 0 = A T + noise with
  A the force balance projected off range(P); the hyperparameter mu minimizes ABIC,
  -2 log marginal likelihood with sigma^2 profiled (Akaike 1980; the approach of
  Ishihara & Sugimura 2012, J Theor Biol 313:201):
      ABIC(mu) = n' log q(mu) + sum_i log(1 + s_i^2/mu),
      q(mu) = min_T |A T|^2 + mu |T - 1|^2,
  with s_i the singular values of A and n' its row count. The MAP tension is
  T = mu (A^T A + mu I)^-1 1, then P by least squares.
"""

from dataclasses import dataclass

import numpy as np

from cells.processes import vertex_mechanics as vm

ANALYSIS_ID = "junction_tension_inference@1"


@dataclass(frozen=True)
class Balance:
    tension_matrix: np.ndarray  # [2V, J] over active vertices and junctions
    pressure_matrix: np.ndarray  # [2V, C]
    junctions: np.ndarray  # slots of active junctions (columns)
    cells: np.ndarray  # slots of active cells (columns)


@dataclass(frozen=True)
class Inference:
    tension: np.ndarray
    pressure: np.ndarray
    residual: float
    singular_values: np.ndarray
    null_dimension: int
    condition_beyond_gauges: float


@dataclass(frozen=True)
class BayesianInference:
    tension: np.ndarray
    pressure: np.ndarray
    hyperparameter: float
    abic: np.ndarray
    hyperparameter_grid: np.ndarray


def balance(position, topology, box):
    """The force-balance matrices of a geometry (numpy topology and positions)."""
    t = topology
    x, box = np.asarray(position, dtype=np.float64), np.asarray(box, dtype=np.float64)
    g = vm.geometry(x, t, box, xp=np)
    vertices = np.flatnonzero(np.asarray(t.vertex_active))
    junctions = np.flatnonzero(np.asarray(t.junction_active))
    cells = np.flatnonzero(np.asarray(t.cell_active))
    row = np.full(len(np.asarray(t.vertex_active)), -1)
    row[vertices] = np.arange(len(vertices))
    tension = np.zeros((2 * len(vertices), len(junctions)))
    unit = g.junction_vector[junctions] / g.length[junctions, None]
    tails, heads = np.asarray(t.junction_tail)[junctions], np.asarray(t.junction_head)[junctions]
    for column, (a, b, u) in enumerate(zip(tails, heads, unit, strict=True)):
        tension[2 * row[a] : 2 * row[a] + 2, column] += u
        tension[2 * row[b] : 2 * row[b] + 2, column] -= u
    column_of = np.full(len(np.asarray(t.cell_active)), -1)
    column_of[cells] = np.arange(len(cells))
    pressure = np.zeros((2 * len(vertices), len(cells)))
    corner = g.corner
    active = np.flatnonzero(np.asarray(t.he_active))
    nxt, prv = np.asarray(t.he_next), np.asarray(t.he_prev)
    for h in active:
        chord = corner[nxt[h]] - corner[prv[h]]
        v, c = row[np.asarray(t.he_tail)[h]], column_of[np.asarray(t.he_cell)[h]]
        pressure[2 * v : 2 * v + 2, c] += 0.5 * np.array([chord[1], -chord[0]])
    return Balance(tension, pressure, junctions, cells)


def known_pressure(balance, pressure, *, threshold=1e-8):
    """T from the force balance with the pressures given ([C] over active cells)."""
    pressure = np.asarray(pressure, dtype=np.float64)
    tension, *_ = np.linalg.lstsq(balance.tension_matrix, -balance.pressure_matrix @ pressure)
    residual = balance.tension_matrix @ tension + balance.pressure_matrix @ pressure
    sv = np.linalg.svd(balance.tension_matrix, compute_uv=False)
    null = int(np.sum(sv < threshold * sv[0])) + max(0, len(tension) - len(sv))
    return Inference(
        tension, pressure, float(np.linalg.norm(residual)), sv, null, float(sv[0] / sv[-1])
    )


def joint(balance, *, mean_tension=1.0, mean_pressure=0.0, threshold=1e-8):
    """(T, P) with gauges: the mean tension and the mean pressure are given."""
    m = np.hstack([balance.tension_matrix, balance.pressure_matrix])
    scale = np.linalg.norm(m, axis=0)
    sv = np.linalg.svd(m / scale, compute_uv=False)
    columns = m.shape[1]
    null = int(np.sum(sv < threshold * sv[0])) + max(0, columns - len(sv))
    gauges = np.zeros((2, columns))
    j = balance.tension_matrix.shape[1]
    gauges[0, :j], gauges[1, j:] = 1.0 / j, 1.0 / (columns - j)
    rhs = np.concatenate([np.zeros(m.shape[0]), [mean_tension, mean_pressure]])
    solution, *_ = np.linalg.lstsq(np.vstack([m, gauges]), rhs)
    residual = np.linalg.norm(m @ solution)
    beyond = sv[-3] if len(sv) >= 3 else sv[-1]
    return Inference(solution[:j], solution[j:], float(residual), sv, null, float(sv[0] / beyond))


def bayesian(balance, *, grid=None, mean_pressure=0.0):
    """MAP tensions with a uniform-tension Gaussian prior; mu chosen by ABIC."""
    grid = np.logspace(-10, 4, 57) if grid is None else np.asarray(grid, dtype=np.float64)
    u, s, _ = np.linalg.svd(balance.pressure_matrix, full_matrices=True)
    rank = int(np.sum(s > 1e-12 * s[0]))
    complement = u[:, rank:]
    a = complement.T @ balance.tension_matrix
    rows, junctions = a.shape
    sv = np.linalg.svd(a, compute_uv=False)
    gram = a.T @ a
    ones = np.ones(junctions)
    abic = []
    for mu in grid:
        tension = mu * np.linalg.solve(gram + mu * np.eye(junctions), ones)
        q = np.sum((a @ tension) ** 2) + mu * np.sum((tension - 1.0) ** 2)
        abic.append(rows * np.log(q) + np.sum(np.log1p(sv**2 / mu)))
    abic = np.array(abic)
    mu = float(grid[int(np.argmin(abic))])
    tension = mu * np.linalg.solve(gram + mu * np.eye(junctions), ones)
    pressure, *_ = np.linalg.lstsq(balance.pressure_matrix, -balance.tension_matrix @ tension)
    pressure = pressure - np.mean(pressure) + mean_pressure
    return BayesianInference(tension, pressure, mu, abic, grid)


def true_tensions(position, topology, box, mechanics):
    """T_j = Lambda_j + Gamma_a L_a + Gamma_b L_b and P_c = -K_c (A_c - A0_c), active only."""
    t, m = topology, mechanics
    g = vm.geometry(np.asarray(position), t, np.asarray(box), xp=np)
    junctions = np.flatnonzero(np.asarray(t.junction_active))
    cells = np.flatnonzero(np.asarray(t.cell_active))
    contractile = np.asarray(m.contractility) * g.perimeter
    total = np.asarray(m.line_tension).astype(np.float64).copy()
    for h in np.flatnonzero(np.asarray(t.he_active)):
        total[np.asarray(t.he_junction)[h]] += contractile[np.asarray(t.he_cell)[h]]
    pressure = -np.asarray(m.area_elasticity) * (g.area - np.asarray(m.preferred_area))
    return total[junctions], pressure[cells]
