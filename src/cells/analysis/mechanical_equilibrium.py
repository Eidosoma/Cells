"""mechanical_equilibrium_analysis@1: equilibria, spectra and linear moduli of a vertex tissue.

An opt-in, read-only analysis of an apical_vertex_mechanics@1 definition (or of a
state of one). It evaluates the model's own energy (processes/vertex_mechanics.py)
and never writes a run, a checkpoint or a definition; ordinary runs do not import
it. A problem takes the definition's topology, box, friction and the parameters of
one experiment control (the one at time zero by default), with the definition's
positions or given ones.

minimize: FIRE (Bitzek et al. 2006, PRL 97:170201) with forces from jax.grad, then
a Newton polish with the dense Hessian of the active vertices (pseudo-inverse over
its nonzero spectrum, so translations and other zero modes take no step; a
backtracking line search keeps the energy decreasing). A candidate outside the
model's domain is never accepted: FIRE stops the motion and halves its step,
Newton halves its step. With box=True an outer Newton iteration relaxes the
upper-triangular box: strains e = (e_xx, e_yy, e_xy) applied affinely to vertices
and box, the step solving K e = -dE/de with K the relaxed elastic matrix below,
each candidate box followed by a vertex relaxation and accepted only if the box
force dE/de decreases (the relaxed energy sits at its rounding floor near the
minimum).

moduli: linear response of a stationary state to strains F = I + sum_k e_k M_k
applied to the vertices and the box (Maloney & Lemaitre 2006, PRE 74:016118):
relaxed d2E/de2 = E_ee - Xi^T H^+ Xi, with Xi = d2E/(du de) and H^+ over the
nonzero spectrum of the vertex Hessian (translations are orthogonal to Xi). The
shear modulus is the relaxed simple-shear curvature over the box area, the bulk
modulus the relaxed dilation curvature over 4 x the box area; affine values omit
the Xi term. These are moduli of a stress-free state; the box stress is reported.

contraction: quasi-static shortening of one junction to lambda * l0, down to 0 (a
four-fold vertex: the onset of a T1 transition, which this model does not
perform). The head vertex is placed at x_tail - B n + lambda l0 (cos theta,
sin theta); theta and every other vertex are unknowns. The junction's length is
prescribed (vertex_mechanics.geometry(prescribed=...)), so no sqrt(0) gradient
arises, and the length floor and rotation test exempt that junction and its two
vertices only. Each lambda starts from the previous minimum. The barrier is
E(lambda=0) - E(lambda=1) (Bi et al. 2015, Nat Phys 11:1074, Methods, whose energy
is twice this one).

Each contraction point is minimized in three stages over the free coordinates:
(1) FIRE to max |F| <= PATH_COARSE (globalization); (2) trust-region Newton on the
energy with the exact Hessian over all modes (scipy trust-exact; negative curvature is
handled by the trust region); (3) damped Newton on the force residual through the
Hessian's eigendecomposition, delta = -sum_i v_i (v_i . g) / (|lambda_i| + mu), with mu
adapted and a step accepted when the residual's 2-norm decreases, never by comparing
energies; convergence is tested on the max-norm. Stage 2 minimizes the energy change
from its start point computed term by term (_path_energy_change), which resolves the
small changes that the total energy's float64 rounding hides. Stages 2 and 3 repeat in
cycles, each re-anchored, until the tolerance is met or a cycle fails to halve the
largest force (at most PATH_CYCLES).

Stage 3 exists because a path that crosses the constrained network's own
compatibility transition (at a critical contraction fraction) meets critically flat
points: a band of near-zero Hessian modes, where FIRE converges only algebraically
and energy-based acceptance stalls at the energy's float64 resolution (Farhadifar
energies carry a large cancelling constant). Normal equations (H^2) would square the
condition number there; the eigendecomposition does not. The accepted point must have
no Hessian eigenvalue below -ZERO_MODE_RTOL x the largest (a minimum, not a saddle).
A point that does not converge raises PathNotConverged with its stage diagnostics;
nothing is clipped or accepted.
"""

from dataclasses import dataclass, field
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
from scipy import optimize

from cells.core.specs import ConfigError
from cells.processes import vertex_mechanics as vm

ANALYSIS_ID = "mechanical_equilibrium_analysis@1"
MODEL_ID = "apical_vertex_mechanics@1"
SHEAR = np.array([[0.0, 1.0], [0.0, 0.0]])
DILATION = np.eye(2)
BOX_STRAINS = (np.array([[1.0, 0.0], [0.0, 0.0]]), np.array([[0.0, 0.0], [0.0, 1.0]]), SHEAR)
ZERO_MODE_RTOL = 1e-9
# FIRE hands over to the trust-region Newton at this largest force on contraction paths.
PATH_COARSE = 1e-3
PATH_TRUST_ITERATIONS = 2000
PATH_POLISH_ITERATIONS = 30
PATH_CYCLES = 8
# Stages 2 and 3 move at most this fraction of the shortest junction per step: on
# near-singular (compatible) landscapes an unbounded Newton step can jump to a locally
# valid but globally crossed configuration.
PATH_STEP_FRACTION = 0.05


class PathNotConverged(ConfigError):
    """A contraction point did not converge; diagnostics name the stage reached."""

    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


@dataclass(frozen=True)
class Problem:
    spec: Any
    topology: vm.Topology  # jax arrays
    host_topology: vm.Topology  # the same, numpy
    mechanics: vm.Mechanics
    box: np.ndarray
    friction: np.ndarray
    length_floor: float
    position: np.ndarray
    vertices: np.ndarray  # slots of active vertices


@dataclass(frozen=True)
class Equilibrium:
    position: np.ndarray
    box: np.ndarray
    energy: float
    max_force: float
    stress: np.ndarray
    fire_iterations: int
    newton_iterations: int
    box_iterations: int


@dataclass(frozen=True)
class Moduli:
    shear: float
    bulk: float
    shear_affine: float
    bulk_affine: float
    stress: np.ndarray
    negative_modes: int
    zero_modes: int


@dataclass(frozen=True)
class ContractionPath:
    fractions: np.ndarray
    energies: np.ndarray
    positions: tuple
    max_forces: np.ndarray
    barrier: float
    initial_length: float
    diagnostics: tuple = field(default=())


def problem(spec, *, position=None, control=0, box=None):
    from cells.core.apical_vertex_spec import held_parameters
    from cells.models import apical_vertex as av

    if getattr(spec.model, "units", None) != "reduced" or not hasattr(spec.model, "cells"):
        raise ConfigError(f"{ANALYSIS_ID} supports {MODEL_ID} definitions only")
    state, layout = av.initial_values(spec)
    held = held_parameters(spec, spec.experiment.changes[control])
    host = av.topology(layout)
    topology = jax.tree.map(jnp.asarray, host)
    mechanics = vm.Mechanics(*(jnp.asarray(held[k]) for k in av.Control._fields))
    x = state.position if position is None else np.asarray(position, dtype=np.float64)
    return Problem(
        spec,
        topology,
        host,
        mechanics,
        np.asarray(layout.box if box is None else box, dtype=np.float64),
        np.asarray(layout.friction),
        float(layout.length_floor[0]),
        x.copy(),
        np.flatnonzero(layout.vertex_active),
    )


@jax.jit
def _energy_and_gradient(x, topology, box, mechanics):
    return jax.value_and_grad(vm.energy)(x, topology, box, mechanics)


@jax.jit
def _valid(x, topology, box, floor):
    return vm.domain_valid(x, topology, box, floor)


def energy(pb, x=None, box=None):
    x = pb.position if x is None else x
    box = pb.box if box is None else box
    return float(
        _energy_and_gradient(jnp.asarray(x), pb.topology, jnp.asarray(box), pb.mechanics)[0]
    )


def max_force(pb, x, box=None):
    box = pb.box if box is None else box
    _, g = _energy_and_gradient(jnp.asarray(x), pb.topology, jnp.asarray(box), pb.mechanics)
    return float(np.max(np.linalg.norm(np.asarray(g)[pb.vertices], axis=1)))


def box_stress(pb, x, box=None):
    box = pb.box if box is None else box
    return np.asarray(vm.box_stress(jnp.asarray(x), pb.topology, jnp.asarray(box), pb.mechanics))


def fire(pb, x0, box=None, *, tolerance=1e-12, max_iterations=400000, dt=0.02):
    """FIRE descent on the vertex positions at a fixed box; returns (x, iterations)."""
    box = jnp.asarray(pb.box if box is None else box)
    x = np.array(x0, dtype=np.float64)
    v = np.zeros_like(x)
    dt_max, alpha, positive = 10.0 * dt, 0.1, 0
    _, g = _energy_and_gradient(jnp.asarray(x), pb.topology, box, pb.mechanics)
    f = -np.asarray(g)
    for iteration in range(max_iterations):
        if np.max(np.linalg.norm(f[pb.vertices], axis=1)) <= tolerance:
            return x, iteration
        power = np.sum(f * v)
        if power > 0:
            v = (1 - alpha) * v + alpha * np.linalg.norm(v) * f / np.linalg.norm(f)
            if positive > 5:
                dt, alpha = min(1.1 * dt, dt_max), 0.99 * alpha
            positive += 1
        else:
            v[:] = 0.0
            dt, alpha, positive = 0.5 * dt, 0.1, 0
        v = v + dt * f
        trial = x + dt * v
        if not bool(_valid(jnp.asarray(trial), pb.topology, box, pb.length_floor)):
            v[:] = 0.0
            dt *= 0.5
            if dt < 1e-14:
                raise ConfigError("FIRE cannot move without leaving the model domain")
            continue
        x = trial
        _, g = _energy_and_gradient(jnp.asarray(x), pb.topology, box, pb.mechanics)
        f = -np.asarray(g)
    raise ConfigError(f"FIRE did not reach max |F| <= {tolerance} in {max_iterations} steps")


def _reduced_energy(q, base, index, box, topology, mechanics):
    return vm.energy(base.at[index].set(q.reshape(-1, 2)), topology, box, mechanics)


_reduced_hessian = jax.jit(jax.hessian(_reduced_energy))


def hessian(pb, x, box=None):
    """Dense Hessian of the energy over the active vertex coordinates, [2n, 2n]."""
    box = jnp.asarray(pb.box if box is None else box)
    x = jnp.asarray(x)
    index = jnp.asarray(pb.vertices)
    q = x[index].ravel()
    return np.asarray(_reduced_hessian(q, x, index, box, pb.topology, pb.mechanics))


def _pseudo_solve(matrix, vector):
    values, vectors = np.linalg.eigh(matrix)
    keep = np.abs(values) > ZERO_MODE_RTOL * np.max(np.abs(values))
    return vectors[:, keep] @ ((vectors[:, keep].T @ vector) / values[keep]), values, keep


def newton(pb, x, box=None, *, tolerance=1e-13, iterations=12):
    """Newton polish of a FIRE minimum; returns (x, iterations)."""
    box = np.asarray(pb.box if box is None else box)
    x = np.array(x, dtype=np.float64)
    for iteration in range(iterations):
        e, g = _energy_and_gradient(jnp.asarray(x), pb.topology, jnp.asarray(box), pb.mechanics)
        g = np.asarray(g)[pb.vertices].ravel()
        if np.max(np.abs(g)) <= tolerance:
            return x, iteration
        step, values, keep = _pseudo_solve(hessian(pb, x, box), -g)
        if np.any(values[keep] < 0):
            return x, iteration  # Not a minimum's basin: leave FIRE's state.
        t = 1.0
        while t > 1e-6:
            trial = x.copy()
            trial[pb.vertices] += t * step.reshape(-1, 2)
            ok = bool(_valid(jnp.asarray(trial), pb.topology, jnp.asarray(box), pb.length_floor))
            if ok and energy(pb, trial, box) <= float(e) + 1e-15 * abs(float(e)):
                break
            t *= 0.5
        else:
            return x, iteration
        x = trial
    return x, iterations


def _strained_energy(z, base, index, generators, box, topology, mechanics):
    n = 2 * index.shape[0]
    u, e = z[:n].reshape(-1, 2), z[n:]
    deformation = jnp.eye(2) + jnp.tensordot(e, generators, axes=1)
    y = base.at[index].add(u) @ deformation.T
    return vm.energy(y, topology, deformation @ box, mechanics)


_strain_hessian = jax.jit(jax.hessian(_strained_energy))
_strain_gradient = jax.jit(jax.grad(_strained_energy))


def _strain_response(pb, x, box, generators):
    """(E_ee, Xi, H, dE/de) at e = 0 for strains F = I + sum_k e_k M_k."""
    generators = jnp.asarray(np.array(generators))
    index = jnp.asarray(pb.vertices)
    n = 2 * len(pb.vertices)
    args = (jnp.asarray(x), index, generators, jnp.asarray(box), pb.topology, pb.mechanics)
    z = jnp.zeros(n + generators.shape[0])
    full = np.asarray(_strain_hessian(z, *args))
    gradient = np.asarray(_strain_gradient(z, *args))
    return full[n:, n:], full[:n, n:], full[:n, :n], gradient[n:]


def strain_gradient(pb, x, box, generators=BOX_STRAINS):
    """dE/de for strains F = I + sum_k e_k M_k at e = 0 (no Hessian)."""
    generators = jnp.asarray(np.array(generators))
    index = jnp.asarray(pb.vertices)
    z = jnp.zeros(2 * len(pb.vertices) + generators.shape[0])
    args = (jnp.asarray(x), index, generators, jnp.asarray(box), pb.topology, pb.mechanics)
    return np.asarray(_strain_gradient(z, *args))[2 * len(pb.vertices) :]


def relaxed_elasticity(pb, x, box=None, generators=BOX_STRAINS):
    """(relaxed d2E/de2, affine d2E/de2, dE/de, vertex Hessian eigenvalues)."""
    box = np.asarray(pb.box if box is None else box)
    affine, xi, h, gradient = _strain_response(pb, x, box, generators)
    values, vectors = np.linalg.eigh(h)
    keep = np.abs(values) > ZERO_MODE_RTOL * np.max(np.abs(values))
    projected = vectors[:, keep].T @ xi
    relaxed = affine - projected.T @ (projected / values[keep][:, None])
    return 0.5 * (relaxed + relaxed.T), affine, gradient, values


def moduli(pb, x, box=None):
    box = np.asarray(pb.box if box is None else box)
    relaxed, affine, _, values = relaxed_elasticity(pb, x, box, (SHEAR, DILATION))
    area = float(np.linalg.det(box))
    scale = np.max(np.abs(values))
    return Moduli(
        shear=float(relaxed[0, 0] / area),
        bulk=float(relaxed[1, 1] / (4 * area)),
        shear_affine=float(affine[0, 0] / area),
        bulk_affine=float(affine[1, 1] / (4 * area)),
        stress=box_stress(pb, x, box),
        negative_modes=int(np.sum(values < -ZERO_MODE_RTOL * scale)),
        zero_modes=int(np.sum(np.abs(values) <= ZERO_MODE_RTOL * scale)),
    )


def relax_vertices(pb, x0, box=None, *, tolerance=1e-12, polish=True):
    """FIRE (to 1e-6 when polishing), Newton to the tolerance, then FIRE if needed."""
    x, fire_steps = fire(pb, x0, box, tolerance=max(tolerance, 1e-6) if polish else tolerance)
    newton_steps = 0
    if polish:
        x, newton_steps = newton(pb, x, box, tolerance=0.1 * tolerance)
        if max_force(pb, x, box) > tolerance:
            x, more = fire(pb, x, box, tolerance=tolerance)
            fire_steps += more
    return x, fire_steps, newton_steps


def minimize(pb, x0=None, *, box=False, tolerance=1e-12, stress_tolerance=1e-11, max_box=30):
    """Relax the vertices, and with box=True also the upper-triangular box."""
    x0 = pb.position if x0 is None else x0
    current = np.array(pb.box)
    if box and current[1, 0] != 0:
        raise ConfigError("Box relaxation requires an upper-triangular periodic box")
    x, fire_steps, newton_steps = relax_vertices(pb, x0, current, tolerance=tolerance)
    box_steps = 0
    while box:
        relaxed, _, gradient, _ = relaxed_elasticity(pb, x, current)
        area = float(np.linalg.det(current))
        if np.max(np.abs(gradient)) <= stress_tolerance * area or box_steps >= max_box:
            break
        step = -np.linalg.solve(relaxed, gradient)
        t = 1.0
        while t > 1e-6:
            deformation = np.eye(2) + np.tensordot(t * step, np.array(BOX_STRAINS), axes=1)
            trial_box = deformation @ current
            trial = x.copy()
            trial[pb.vertices] = x[pb.vertices] @ deformation.T
            try:
                trial, f_steps, n_steps = relax_vertices(pb, trial, trial_box, tolerance=tolerance)
            except ConfigError:
                t *= 0.5
                continue
            # Accept while the box force dE/de decreases (energies sit at their rounding
            # floor near the minimum, gradients do not).
            if np.max(np.abs(strain_gradient(pb, trial, trial_box))) < np.max(np.abs(gradient)):
                x, current = trial, trial_box
                fire_steps, newton_steps = fire_steps + f_steps, newton_steps + n_steps
                break
            t *= 0.5
        else:
            break
        box_steps += 1
    return Equilibrium(
        x,
        current,
        energy(pb, x, current),
        max_force(pb, x, current),
        box_stress(pb, x, current),
        fire_steps,
        newton_steps,
        box_steps,
    )


def _place(x, theta, tail, head, shift, length):
    direction = jnp.array([jnp.cos(theta), jnp.sin(theta)])
    return x.at[head].set(x[tail] - shift + length * direction)


def _path_energy(z, junction, tail, head, shift, length, box, topology, mechanics):
    x = _place(z[:-1].reshape(-1, 2), z[-1], tail, head, shift, length)
    count = topology.junction_active.shape[0]
    mask = jnp.arange(count) == junction
    lengths = jnp.where(mask, length, 0.0)
    return vm.energy(x, topology, box, mechanics, prescribed=(mask, lengths))


_path_value_and_grad = jax.jit(jax.value_and_grad(_path_energy))
_place_jit = jax.jit(_place)


def _path_energy_change(z, anchor, junction, tail, head, shift, length, box, topology, mechanics):
    """E(z) - E(anchor) term by term from the displacement, without large cancellation.

    The total energy carries large cancelling terms (Gamma L^2 / 2 against Lambda l), so
    its float64 resolution near a minimum is far coarser than the energy changes a
    critically flat point needs. Here every term's change is a product of O(delta) and
    O(1) quantities: dl = dd.(2 d0 + dd) / (|d0 + dd| + |d0|), Gamma/2 dL (2 L0 + dL),
    K/2 dA (2 (A0 - A_pref) + dA) with dA from shoelace differences, Lambda dl. The
    contracted junction's length is prescribed (dl = 0); its head vertex follows the tail
    and the angle through a stable cosine/sine difference.
    """
    t, m = topology, mechanics
    x0 = anchor[:-1].reshape(-1, 2)
    dx = z[:-1].reshape(-1, 2) - x0
    theta, theta0 = z[-1], anchor[-1]
    half = 0.5 * (theta - theta0)
    mid = 0.5 * (theta + theta0)
    turn = 2.0 * jnp.sin(half) * jnp.array([-jnp.sin(mid), jnp.cos(mid)])
    dx = dx.at[head].set(dx[tail] + length * turn)
    x0 = _place(x0, theta0, tail, head, shift, length)
    count = t.junction_active.shape[0]
    mask = jnp.arange(count) == junction
    g0 = vm.geometry(x0, t, box, prescribed=(mask, jnp.where(mask, length, 0.0)))
    dd = jnp.where(t.junction_active[:, None], dx[t.junction_head] - dx[t.junction_tail], 0.0)
    d0 = g0.junction_vector
    norm1 = vm.guarded_norm(d0 + dd, t.junction_active & ~mask)
    norm0 = vm.guarded_norm(d0, t.junction_active & ~mask)
    denominator = jnp.where(t.junction_active & ~mask, norm1 + norm0, 1.0)
    dl = jnp.where(
        t.junction_active & ~mask, jnp.sum(dd * (2.0 * d0 + dd), axis=-1) / denominator, 0.0
    )
    size = t.cell_active.shape[0]
    dL = vm.scatter_add(jnp.where(t.he_active, dl[t.he_junction], 0.0), t.he_cell, size)
    du = dx[t.he_tail] - dx[t.cell_reference][t.he_cell]
    du = jnp.where(t.he_active[:, None], du, 0.0)
    u0 = g0.corner
    w0, dw = u0[t.he_next], du[t.he_next]
    twice = vm.cross(du, w0) + vm.cross(u0, dw) + vm.cross(du, dw)
    dA = 0.5 * vm.scatter_add(jnp.where(t.he_active, twice, 0.0), t.he_cell, size)
    area = jnp.where(
        t.cell_active,
        0.5 * m.area_elasticity * dA * (2.0 * (g0.area - m.preferred_area) + dA),
        0.0,
    )
    perimeter = jnp.where(
        t.cell_active, 0.5 * m.contractility * dL * (2.0 * g0.perimeter + dL), 0.0
    )
    line = jnp.where(t.junction_active, m.line_tension * dl, 0.0)
    return jnp.sum(area) + jnp.sum(perimeter) + jnp.sum(line)


_path_energy_change_jit = jax.jit(_path_energy_change)


@jax.jit
def _path_valid_jit(x, topology, box, floor, junction, tail, head):
    """The model domain with the contracted junction and its two vertices exempt."""
    g = vm.geometry(x, topology, box)
    others = topology.junction_active & (jnp.arange(topology.junction_active.shape[0]) != junction)
    sums = vm.corner_angle_sums(x, topology, box)
    slots = jnp.arange(topology.vertex_active.shape[0])
    check = topology.vertex_active & (slots != tail) & (slots != head)
    ok = jnp.all(jnp.isfinite(x))
    ok &= jnp.all(jnp.where(topology.cell_active, g.area > 0, True))
    ok &= jnp.all(jnp.where(others, g.length >= floor, True))
    ok &= jnp.all(jnp.where(check, jnp.abs(sums - vm.TWO_PI) <= vm.ANGLE_SUM_ATOL, True))
    return ok


def _path_valid(pb, x, junction, ends):
    return bool(
        _path_valid_jit(
            jnp.asarray(x), pb.topology, jnp.asarray(pb.box), pb.length_floor, junction, *ends
        )
    )


_path_hessian = jax.jit(jax.hessian(_path_energy))


def _minimize_path(pb, junction, length, x, theta, *, tolerance, max_iterations=400000):
    """Coarse FIRE, trust-region Newton, force-residual LM polish (module docstring).

    Returns (positions, theta, energy, max force, diagnostics).
    """
    t = pb.host_topology
    ends = (int(t.junction_tail[junction]), int(t.junction_head[junction]))
    shift = jnp.asarray(np.asarray(t.junction_image[junction]) @ pb.box.T)
    args = (junction, ends[0], ends[1], shift, length, jnp.asarray(pb.box))
    z0 = np.concatenate([np.asarray(x).ravel(), [theta]])
    keep = np.zeros(z0.size, dtype=bool)
    keep[np.concatenate([2 * pb.vertices, 2 * pb.vertices + 1])] = True
    keep[[2 * ends[1], 2 * ends[1] + 1]] = False
    keep[-1] = True
    index = np.flatnonzero(keep)
    angle = len(index) - 1

    def full(q):
        z = z0.copy()
        z[index] = q
        return z

    def energy_and_gradient(q):
        e, g = _path_value_and_grad(jnp.asarray(full(q)), *args, pb.topology, pb.mechanics)
        return float(e), np.asarray(g)[index]

    def hessian(q):
        h = np.asarray(_path_hessian(jnp.asarray(full(q)), *args, pb.topology, pb.mechanics))
        return h[np.ix_(index, index)]

    def scaled(g):  # The angle's force is a torque: compare it per unit length.
        g = g.copy()
        g[angle] = g[angle] / length if length > 0 else 0.0
        return g

    def size(g):  # Convergence: the registered max-norm tolerance.
        return float(np.max(np.abs(scaled(g))))

    def norm(g):  # LM acceptance: the residual 2-norm, which LM steps decrease.
        return float(np.linalg.norm(scaled(g)))

    def place(q):
        z = full(q)
        return np.asarray(
            _place_jit(jnp.asarray(z[:-1].reshape(-1, 2)), z[-1], ends[0], ends[1], shift, length)
        )

    def valid(q):
        return _path_valid(pb, place(q), junction, ends)

    def embedded(q):  # Local validity and no crossing junctions (host check).
        return valid(q) and not vm.crossing_junctions(place(q), t, pb.box)

    def step_limit(q):
        lengths = vm.geometry(place(q), t, pb.box, xp=np).length
        others = np.asarray(t.junction_active) & (np.arange(len(lengths)) != junction)
        return PATH_STEP_FRACTION * float(np.min(lengths[others]))

    diagnostics = {}
    # Stage 1: FIRE to a coarse force (globalization).
    q, dt, alpha, positive, iterations = z0[index].copy(), 0.02, 0.1, 0, 0
    v = np.zeros_like(q)
    e, g = energy_and_gradient(q)
    while size(g) > max(tolerance, PATH_COARSE):
        iterations += 1
        if iterations > max_iterations:
            raise PathNotConverged(
                "Contraction FIRE stage did not reach its coarse force", diagnostics
            )
        f = -g
        power = np.sum(f * v)
        if power > 0:
            v = (1 - alpha) * v + alpha * np.linalg.norm(v) * f / np.linalg.norm(f)
            if positive > 5:
                dt, alpha = min(1.1 * dt, 0.2), 0.99 * alpha
            positive += 1
        else:
            v[:] = 0.0
            dt, alpha, positive = 0.5 * dt, 0.1, 0
        v = v + dt * f
        trial = q + dt * v
        if not valid(trial):
            v[:] = 0.0
            dt *= 0.5
            if dt < 1e-14:
                raise PathNotConverged("Contraction left the model domain", diagnostics)
            continue
        q = trial
        e, g = energy_and_gradient(q)
    diagnostics["fire"] = {"iterations": iterations, "max_force": size(g)}

    def trust_region(q, e, g):
        """Stage 2: trust-region Newton on the energy change from q (all modes)."""
        anchor = jnp.asarray(full(q))

        def change_and_gradient(qq):
            zz = jnp.asarray(full(qq))
            delta = _path_energy_change_jit(zz, anchor, *args, pb.topology, pb.mechanics)
            return float(delta), energy_and_gradient(qq)[1]

        limit = step_limit(q)
        result = optimize.minimize(
            change_and_gradient,
            q,
            jac=True,
            hess=hessian,
            method="trust-exact",
            options={
                "gtol": tolerance,
                "maxiter": PATH_TRUST_ITERATIONS,
                "initial_trust_radius": 0.2 * limit,
                "max_trust_radius": limit,
            },
        )
        if embedded(result.x):
            e_t, g_t = energy_and_gradient(result.x)
            if size(g_t) < size(g):
                q, e, g = result.x, e_t, g_t
        return q, e, g, int(result.nit)

    def polish(q, e, g):
        """Stage 3: damped Newton on the force residual (eigendecomposition)."""
        mu = 1e-14 * np.max(np.abs(np.linalg.eigvalsh(hessian(q))))
        steps = 0
        while steps < PATH_POLISH_ITERATIONS and size(g) > tolerance:
            steps += 1
            values, vectors = np.linalg.eigh(hessian(q))
            projected = vectors.T @ g
            limit = step_limit(q)
            for _ in range(40):
                delta = vectors @ (projected / (np.abs(values) + mu))
                longest = float(np.max(np.abs(delta)))
                if longest > limit:
                    delta = delta * (limit / longest)
                trial = q - delta
                if valid(trial):
                    e_t, g_t = energy_and_gradient(trial)
                    if norm(g_t) < norm(g):
                        q, e, g, mu = trial, e_t, g_t, mu / 3
                        break
                mu *= 4
            else:
                break
        return q, e, g, steps

    # Stages 2 and 3 in cycles, each re-anchored at the last point, until the tolerance
    # is met or a cycle does not halve the largest force.
    cycles = []
    while size(g) > tolerance and len(cycles) < PATH_CYCLES:
        before = size(g)
        q, e, g, trust_iterations = trust_region(q, e, g)
        after_trust = size(g)
        q, e, g, polish_iterations = polish(q, e, g)
        cycles.append(
            {
                "trust_region_iterations": trust_iterations,
                "after_trust_region": after_trust,
                "polish_iterations": polish_iterations,
                "max_force": size(g),
            }
        )
        if size(g) > 0.5 * before:
            break
    diagnostics["cycles"] = cycles
    values = np.linalg.eigvalsh(hessian(q))
    top = np.max(np.abs(values))
    diagnostics["spectrum"] = {
        "negative": int(np.sum(values < -ZERO_MODE_RTOL * top)),
        "near_zero": int(np.sum(np.abs(values) <= ZERO_MODE_RTOL * top)),
        "largest": float(top),
    }
    if size(g) > tolerance:
        raise PathNotConverged(
            f"Contraction point did not converge (max force {size(g):.2e})", diagnostics
        )
    if diagnostics["spectrum"]["negative"]:
        raise PathNotConverged("Contraction point is not a minimum (negative modes)", diagnostics)
    if not embedded(q):
        raise PathNotConverged("Contraction point has crossing junctions", diagnostics)
    z = full(q)
    return place(q), float(z[-1]), e, float(size(g)), diagnostics


def contraction(pb, x, junction, fractions, *, tolerance=1e-11):
    """Quasi-static junction contraction from a minimum x; fractions start at 1."""
    fractions = np.asarray(fractions, dtype=np.float64)
    if fractions[0] != 1 or np.any(np.diff(fractions) >= 0) or fractions[-1] < 0:
        raise ConfigError("Contraction fractions must decrease from 1 to a value >= 0")
    t = pb.host_topology
    tail, head = int(t.junction_tail[junction]), int(t.junction_head[junction])
    d = np.asarray(x)[head] + np.asarray(t.junction_image[junction]) @ pb.box.T - x[tail]
    length0, theta = float(np.linalg.norm(d)), float(np.arctan2(d[1], d[0]))
    energies, positions, forces, stages = [], [], [], []
    current = np.array(x)
    for fraction in fractions:
        try:
            current, theta, e, f, diagnostics = _minimize_path(
                pb, junction, fraction * length0, current, theta, tolerance=tolerance
            )
        except PathNotConverged as error:
            error.diagnostics = dict(error.diagnostics, fraction=float(fraction))
            raise
        energies.append(e)
        positions.append(current.copy())
        forces.append(f)
        stages.append(dict(diagnostics, fraction=float(fraction)))
        if vm.crossing_junctions(current, t, pb.box):
            raise ConfigError("Contraction produced crossing junctions")
    energies = np.array(energies)
    return ContractionPath(
        fractions,
        energies,
        tuple(positions),
        np.array(forces),
        float(energies[-1] - energies[0]),
        length0,
        tuple(stages),
    )
