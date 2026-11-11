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
each candidate box followed by a vertex relaxation and accepted only if the
relaxed energy decreases.

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
"""

from dataclasses import dataclass
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.specs import ConfigError
from cells.processes import vertex_mechanics as vm

ANALYSIS_ID = "mechanical_equilibrium_analysis@1"
MODEL_ID = "apical_vertex_mechanics@1"
SHEAR = np.array([[0.0, 1.0], [0.0, 0.0]])
DILATION = np.eye(2)
BOX_STRAINS = (np.array([[1.0, 0.0], [0.0, 0.0]]), np.array([[0.0, 0.0], [0.0, 1.0]]), SHEAR)
ZERO_MODE_RTOL = 1e-9


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
    x, fire_steps = fire(pb, x0, box, tolerance=tolerance)
    newton_steps = 0
    if polish:
        x, newton_steps = newton(pb, x, box, tolerance=0.1 * tolerance)
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
        e_now, t = energy(pb, x, current), 1.0
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
            if energy(pb, trial, trial_box) <= e_now:
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


def _path_valid(pb, x, junction, ends):
    t = pb.host_topology
    g = vm.geometry(x, t, pb.box, xp=np)
    others = np.asarray(t.junction_active) & (np.arange(len(g.length)) != junction)
    sums = vm.corner_angle_sums(x, t, pb.box, xp=np)
    check = np.asarray(t.vertex_active).copy()
    check[list(ends)] = False
    return bool(
        np.all(g.area[np.asarray(t.cell_active)] > 0)
        and np.all(g.length[others] >= pb.length_floor)
        and np.all(np.abs(sums[check] - vm.TWO_PI) <= vm.ANGLE_SUM_ATOL)
    )


def _minimize_path(pb, junction, length, x, theta, *, tolerance, max_iterations=400000):
    t = pb.host_topology
    ends = (int(t.junction_tail[junction]), int(t.junction_head[junction]))
    shift = jnp.asarray(np.asarray(t.junction_image[junction]) @ pb.box.T)
    args = (junction, ends[0], ends[1], shift, length, jnp.asarray(pb.box))

    def value_and_grad(z):
        return _path_value_and_grad(z, *args, pb.topology, pb.mechanics)

    def place(x, theta):
        return _place_jit(x, theta, ends[0], ends[1], shift, length)

    z = np.concatenate([np.asarray(x).ravel(), [theta]])
    keep = np.zeros(z.size, dtype=bool)
    keep[np.concatenate([2 * pb.vertices, 2 * pb.vertices + 1])] = True
    keep[[2 * ends[1], 2 * ends[1] + 1]] = False
    keep[-1] = True
    v, dt, alpha, positive = np.zeros_like(z), 0.02, 0.1, 0
    e, g = value_and_grad(jnp.asarray(z))
    f = np.where(keep, -np.asarray(g), 0.0)
    for _ in range(max_iterations):
        if np.max(np.abs(f[:-1])) <= tolerance and abs(f[-1]) <= tolerance * length + 1e-300:
            break
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
        trial = z + dt * v
        placed = np.asarray(place(jnp.asarray(trial[:-1].reshape(-1, 2)), trial[-1]))
        if not _path_valid(pb, placed, junction, ends):
            v[:] = 0.0
            dt *= 0.5
            if dt < 1e-14:
                raise ConfigError("Contraction left the model domain")
            continue
        z = trial
        e, g = value_and_grad(jnp.asarray(z))
        f = np.where(keep, -np.asarray(g), 0.0)
    else:
        raise ConfigError("Contraction minimization did not converge")
    placed = np.asarray(place(jnp.asarray(z[:-1].reshape(-1, 2)), z[-1]))
    return placed, float(z[-1]), float(e), float(np.max(np.abs(f)))


def contraction(pb, x, junction, fractions, *, tolerance=1e-11):
    """Quasi-static junction contraction from a minimum x; fractions start at 1."""
    fractions = np.asarray(fractions, dtype=np.float64)
    if fractions[0] != 1 or np.any(np.diff(fractions) >= 0) or fractions[-1] < 0:
        raise ConfigError("Contraction fractions must decrease from 1 to a value >= 0")
    t = pb.host_topology
    tail, head = int(t.junction_tail[junction]), int(t.junction_head[junction])
    d = np.asarray(x)[head] + np.asarray(t.junction_image[junction]) @ pb.box.T - x[tail]
    length0, theta = float(np.linalg.norm(d)), float(np.arctan2(d[1], d[0]))
    energies, positions, forces = [], [], []
    current = np.array(x)
    for fraction in fractions:
        current, theta, e, f = _minimize_path(
            pb, junction, fraction * length0, current, theta, tolerance=tolerance
        )
        energies.append(e)
        positions.append(current.copy())
        forces.append(f)
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
    )
