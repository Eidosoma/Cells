"""apical_vertex_mechanics@1: overdamped 2-D apical vertex mechanics, periodic tissue.

Dynamics. Each vertex moves by eta_v dx_v/dt = F_v = -dE/dx_v (forces from
jax.grad of processes/vertex_mechanics.energy), with E the Farhadifar 2007
energy. Topology, box and cell number are fixed: no T1, T2, division or
extrusion. Parameters (junction line tensions; cell contractility, area
elasticity and preferred area) are right-continuous experiment controls.

State. Vertex positions; a per-vertex dissipation ledger D_v = int eta_v |x_v'|^2
dt; the parameters in effect; the control work W booked when a scheduled
parameter change is applied, W += E(x; new) - E(x; old) at the step that starts
at the change; and the declared energy-balance allowance. Every accepted row then
satisfies, by itself, E(x; applied) + sum_v D_v - W = E(x_0; theta_0) within its
allowance, so a checkpoint is checkable without its history.

Solvers. "rk4" (classical RK4 on positions and dissipation) and "euler" (forward
Euler, the law used by tyssue's EulerSolver). Each step refuses itself, with no
repair, if a trial or end state leaves the domain (vertex_mechanics.domain_valid:
finite, positive areas, junctions at or above the length floor, vertex rotations
preserved); if dt * rho exceeds the solver's bound at any evaluated state (rho the
rigorous Hessian bound of vertex_mechanics.hessian_rate; 1 for Euler, the
descent-lemma range; 2 for RK4, inside its real-axis limit 2.785); or if the energy
rises above the start energy by more than rounding.

Energy-balance allowance. For Euler, a step's residual E(x+) - E(x) + dt|F|^2/eta
is the Taylor remainder 1/2 (dt/eta)^2 F^T H F, at most 1/2 dt rho_seg dD, with
rho_seg the bound along the step. The ledger books dt * rho_max * dD per step,
rho_max the largest bound at the evaluated states: the factor 2 over the derived
1/2 is a declared margin for the variation of rho along the step, not a derived
bound. RK4 books the same declared allowance; its residual is higher order and
the time-step study must confirm the allowance is conservative.
"""

from dataclasses import dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.apical_vertex_spec import MODEL_ID, held_parameters, topology_index
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.processes import vertex_mechanics as vm

OBSERVER_ID = "apical_vertex_rows@1"
OBSERVATION_SAMPLING = "accepted_rows_only"
STEP_BOUNDS = {1: 1.0, 4: 2.0}  # tableau stages -> bound on dt * rho
TABLEAUX = {"euler": (1.0,), "rk4": (1 / 6, 1 / 3, 1 / 3, 1 / 6)}
# Energy may not rise across a step by more than this many eps x its term magnitude.
ENERGY_ROUNDING = 64.0
# Rounding allowance growth per accepted step, in eps x the magnitude rounded.
STEP_ROUNDING = 2.5
EPS = float(np.finfo(np.float64).eps)
STATE_AXES = {
    "position": ["vertex_slot", "xy"],
    "dissipated": ["vertex_slot"],
    "line_tension": ["junction_slot"],
    "contractility": ["cell_slot"],
    "area_elasticity": ["cell_slot"],
    "preferred_area": ["cell_slot"],
    "control_work": ["scalar"],
    "energy_allowance": ["scalar"],
}


class VertexState(NamedTuple):
    position: object
    dissipated: object
    line_tension: object
    contractility: object
    area_elasticity: object
    preferred_area: object
    control_work: object
    energy_allowance: object


class VertexLayout(NamedTuple):
    active: object  # [C] cell mask (the runner's `active`)
    ids: object  # [C] positive local cell codes (declared order)
    vertex_active: object
    vertex_ids: object
    friction: object
    he_tail: object
    he_next: object
    he_prev: object
    he_cell: object
    he_junction: object
    he_image: object
    he_active: object
    cell_reference: object
    junction_ids: object
    junction_tail: object
    junction_head: object
    junction_image: object
    junction_active: object
    box: object  # [2, 2], columns are the periodic vectors
    length_floor: object  # [1]


class Control(NamedTuple):
    line_tension: object
    contractility: object
    area_elasticity: object
    preferred_area: object


class Parameters(NamedTuple):
    topology: vm.Topology
    box: object
    length_floor: object
    friction: object
    tableau: object  # shape (1,) Euler or (4,) RK4: static under jit


STATE_TYPE = VertexState
LAYOUT_TYPE = VertexLayout


def initial_values(spec):
    m, x = spec.model, spec.execution
    V, J, C, H = x.vertex_capacity, x.junction_capacity, x.capacity, x.half_edge_capacity
    slot = {v.id: i for i, v in enumerate(m.vertices)}
    nv, nj, nc = len(m.vertices), len(m.junctions), len(m.cells)
    position = np.zeros((V, 2))
    position[:nv] = [v.position for v in m.vertices]
    friction = np.ones(V)
    friction[:nv] = [v.friction for v in m.vertices]
    junction_tail, junction_head = np.zeros(J, dtype=np.int64), np.zeros(J, dtype=np.int64)
    junction_image = np.zeros((J, 2))
    for i, j in enumerate(m.junctions):
        junction_tail[i], junction_head[i] = slot[j.vertices[0]], slot[j.vertices[1]]
        junction_image[i] = j.image
    he_tail, he_cell, he_junction = (np.zeros(H, dtype=np.int64) for _ in range(3))
    he_next, he_prev = np.arange(H, dtype=np.int64), np.arange(H, dtype=np.int64)
    he_image = np.zeros((H, 2))
    cell_reference = np.zeros(C, dtype=np.int64)
    base = 0
    for c, (cell, row) in enumerate(zip(m.cells, topology_index(m), strict=True)):
        n = len(cell.corners)
        first = cell.corners[0].image
        cell_reference[c] = slot[cell.corners[0].vertex]
        for k, (corner, (junction, _)) in enumerate(zip(cell.corners, row, strict=True)):
            h = base + k
            he_tail[h], he_cell[h], he_junction[h] = slot[corner.vertex], c, junction
            he_next[h], he_prev[h] = base + (k + 1) % n, base + (k - 1) % n
            he_image[h] = (corner.image[0] - first[0], corner.image[1] - first[1])
        base += n
    held = held_parameters(spec, spec.experiment.changes[0])
    state = VertexState(
        position,
        np.zeros(V),
        held["line_tension"],
        held["contractility"],
        held["area_elasticity"],
        held["preferred_area"],
        np.zeros(1),
        np.zeros(1),
    )
    layout = VertexLayout(
        np.arange(C) < nc,
        np.where(np.arange(C) < nc, np.arange(1, C + 1), -1),
        np.arange(V) < nv,
        np.where(np.arange(V) < nv, np.arange(1, V + 1), -1),
        friction,
        he_tail,
        he_next,
        he_prev,
        he_cell,
        he_junction,
        he_image,
        np.arange(H) < base,
        cell_reference,
        np.where(np.arange(J) < nj, np.arange(1, J + 1), -1),
        junction_tail,
        junction_head,
        junction_image,
        np.arange(J) < nj,
        np.array(m.periods, dtype=np.float64).T,
        np.array([m.length_floor]),
    )
    return state, layout


def topology(layout):
    return vm.Topology(
        layout.vertex_active,
        layout.he_tail,
        layout.he_next,
        layout.he_prev,
        layout.he_cell,
        layout.he_junction,
        layout.he_image,
        layout.he_active,
        layout.cell_reference,
        layout.active,
        layout.junction_tail,
        layout.junction_head,
        layout.junction_image,
        layout.junction_active,
    )


def parameters(spec, layout):
    return Parameters(
        topology(layout),
        layout.box,
        layout.length_floor[0],
        layout.friction,
        np.array(TABLEAUX[spec.execution.solver]),
    )


def mechanics(state):
    return vm.Mechanics(
        state.line_tension, state.contractility, state.area_elasticity, state.preferred_area
    )


def rhs(state, p):
    """x' = F / eta and D_v' = |F_v|^2 / eta_v; parameters and ledgers are constant."""
    force = vm.forces(state.position, p.topology, p.box, mechanics(state))
    active = p.topology.vertex_active
    eta = jnp.where(active, p.friction, 1.0)
    zeros = jax.tree.map(jnp.zeros_like, state)
    return zeros._replace(
        position=jnp.where(active[:, None], force / eta[:, None], 0.0),
        dissipated=jnp.where(active, jnp.sum(force * force, axis=1) / eta, 0.0),
    )


def _valid(state, p):
    ok = vm.domain_valid(state.position, p.topology, p.box, p.length_floor)
    for value in state:
        ok &= jnp.all(jnp.isfinite(value))
    return ok


def _rate(state, p):
    return vm.hessian_rate(state.position, p.topology, p.box, mechanics(state), p.friction)


def checked_step(state, dt, control, p, active):
    """One Euler or RK4 step with control-work booking and refusal (see docstring)."""
    del active  # Masks come from the topology in p.
    x, topo, box = state.position, p.topology, p.box
    old, new = mechanics(state), vm.Mechanics(*control)
    changed = jnp.array(False)
    for a, b in zip(old, new, strict=True):
        changed |= jnp.any(a != b)
    e_new = vm.energy(x, topo, box, new)
    work = jnp.where(changed, e_new - vm.energy(x, topo, box, old), 0.0)
    start = state._replace(
        line_tension=control.line_tension,
        contractility=control.contractility,
        area_elasticity=control.area_elasticity,
        preferred_area=control.preferred_area,
        control_work=state.control_work + work,
    )

    def slope(trial, ok):
        return jax.lax.cond(
            ok, lambda y: rhs(y, p), lambda y: jax.tree.map(jnp.zeros_like, y), trial
        )

    def increment(derivative, factor):
        return jax.tree.map(lambda y, dy: y + factor * dt * dy, start, derivative)

    stages = p.tableau.shape[0]
    ok = _valid(start, p)
    rates = [_rate(start, p)]
    k1 = slope(start, ok)
    if stages == 1:
        updated = increment(k1, 1.0)
    else:
        slopes = [k1]
        for factor in (0.5, 0.5, 1.0):
            trial = increment(slopes[-1], factor)
            trial_ok = _valid(trial, p)
            ok &= trial_ok
            rates.append(_rate(trial, p))
            slopes.append(slope(trial, trial_ok))
        updated = jax.tree.map(
            lambda y, a, b, c, d: y + (dt / 6.0) * (a + 2.0 * b + 2.0 * c + d), start, *slopes
        )
    ok &= _valid(updated, p)
    rates.append(_rate(updated, p))
    rate = jnp.max(jnp.stack(rates))
    ok &= dt * rate <= STEP_BOUNDS[stages]
    magnitude = vm.energy_magnitude(x, topo, box, new)
    ok &= vm.energy(updated.position, topo, box, new) <= e_new + ENERGY_ROUNDING * EPS * magnitude
    dissipated = jnp.sum(updated.dissipated) - jnp.sum(start.dissipated)
    updated = updated._replace(energy_allowance=start.energy_allowance + dt * rate * dissipated)
    ok &= jnp.all(jnp.isfinite(updated.energy_allowance))
    return jax.tree.map(lambda old_v, new_v: jnp.where(ok, new_v, old_v), state, updated), ok


def _numpy_topology(spec):
    _, layout = initial_values(spec)
    return topology(layout), layout


def check_definition(spec):
    """Initial domain, tiling area identity and bounded energy for every control."""
    from cells.core.apical_vertex_spec import control_values

    state, layout = initial_values(spec)
    topo = topology(layout)
    g = vm.geometry(state.position, topo, layout.box, xp=np)
    det = float(np.linalg.det(layout.box))
    if not np.all(g.area[layout.active] > 0):
        raise ConfigError("Every cell must be counterclockwise with positive initial area")
    if abs(float(np.sum(g.area)) - det) > 1e-9 * det:
        raise ConfigError("Cell areas must tile the periodic box exactly once")
    if not vm.domain_valid(state.position, topo, layout.box, layout.length_floor[0], xp=np):
        raise ConfigError("Initial vertex geometry is outside the model domain")
    times = [c.time for c in spec.experiment.changes]
    controls = control_values(spec, times)
    for i in range(len(times)):
        if not vm.bounded_below(vm.Mechanics(*(v[i] for v in controls)), topo, xp=np):
            raise ConfigError("A cell without contractility borders a negative-tension junction")


def check_steps(spec, steps, controls):
    """Observations on accepted boundaries; the step bound at the initial state."""
    from cells.core.grid import EventGrid

    grid = EventGrid(spec)
    for t in spec.experiment.observation_times:
        try:
            grid.exact_index(t)
        except ConfigError as error:
            raise ConfigError("Vertex observations must lie on accepted step boundaries") from error
    del controls  # Every declared control is checked, whichever rows this window holds.
    if len(steps) == 0:
        return
    state, layout = initial_values(spec)
    topo = topology(layout)
    bound = STEP_BOUNDS[len(TABLEAUX[spec.execution.solver])]
    largest = float(np.max(steps))
    for change in spec.experiment.changes:
        held = held_parameters(spec, change)
        mech = vm.Mechanics(*(held[k] for k in Control._fields))
        rate = vm.hessian_rate(state.position, topo, layout.box, mech, layout.friction, xp=np)
        if not np.isfinite(rate) or largest * rate > bound:
            raise ConfigError(
                f"Step {largest} exceeds the {spec.execution.solver} bound at the initial state "
                f"(dt * rho = {largest * rate:.3g} > {bound})"
            )


def _row_values(position, mech, topo, box, floor):
    g = vm.geometry(position, topo, box)
    return (
        vm.energy(position, topo, box, mech),
        vm.energy_magnitude(position, topo, box, mech),
        vm.domain_valid(position, topo, box, floor),
        jnp.sum(g.area),
        jnp.min(jnp.where(topo.cell_active, g.area, jnp.inf)),
        jnp.min(jnp.where(topo.junction_active, g.length, jnp.inf)),
    )


_rows = jax.jit(jax.vmap(_row_values, in_axes=(0, 0, None, None, None)))


def _on_cpu(values):
    return jax.device_put(values, jax.devices("cpu")[0])


def check_values(state, spec, steps=None):
    """Host checks of accepted rows (or one state): domain, padding, ledgers, sums."""
    initial, layout = initial_values(spec)
    if np.asarray(state.position).ndim == 2:  # A single checkpoint state.
        state = VertexState(*(np.asarray(v)[None] for v in state))
    state = VertexState(*(np.asarray(v) for v in state))
    rows = state.position.shape[0]
    if not all(np.isfinite(np.asarray(v)).all() for v in state):
        raise NumericalError("Non-finite vertex state; refused without repair")
    for name in VertexState._fields:
        if np.asarray(getattr(state, name)).shape[1:] != np.asarray(getattr(initial, name)).shape:
            raise NumericalError(f"Vertex state {name} has the wrong shape")
    v, j, c = layout.vertex_active, layout.junction_active, layout.active
    if (
        np.any(state.position[:, ~v] != 0)
        or np.any(state.dissipated[:, ~v] != 0)
        or np.any(state.line_tension[:, ~j] != 0)
        or any(np.any(getattr(state, k)[:, ~c] != 0) for k in VertexState._fields[3:6])
    ):
        raise NumericalError("Inactive vertex, junction or cell storage changed")
    topo = topology(layout)
    with jax.default_device(jax.devices("cpu")[0]):
        mech = vm.Mechanics(
            *(_on_cpu(np.asarray(getattr(state, k))) for k in VertexState._fields[2:6])
        )
        values = _rows(
            _on_cpu(np.asarray(state.position)),
            mech,
            _on_cpu(topo),
            _on_cpu(layout.box),
            _on_cpu(layout.length_floor[0]),
        )
        energy0 = float(vm.energy(initial.position, topo, layout.box, mechanics(initial), xp=np))
    energy, magnitude, valid, area_sum, min_area, min_length = (np.asarray(a) for a in values)
    if not np.all(valid):
        raise NumericalError("Vertex row outside the domain (area, length floor or rotation)")
    if np.any(state.dissipated < 0) or np.any(np.diff(state.dissipated, axis=0) < 0):
        raise NumericalError("Dissipation ledger negative or decreasing")
    if np.any(state.energy_allowance < 0) or np.any(np.diff(state.energy_allowance, axis=0) < 0):
        raise NumericalError("Energy allowance negative or decreasing")
    count = np.zeros(rows) if steps is None else np.asarray(steps, dtype=np.float64)
    dissipated = state.dissipated.sum(axis=1)
    work = state.control_work[:, 0]
    residual = energy + dissipated - work - energy0
    scale = abs(energy0) + np.abs(energy) + dissipated + np.abs(work) + magnitude
    rounding = (512 + STEP_ROUNDING * count) * EPS * scale
    if np.any(np.abs(residual) > state.energy_allowance[:, 0] + rounding):
        raise NumericalError("Energy balance E + D - W = E0 failed beyond its allowance")
    eta = layout.friction[:, None] * v[:, None]
    momentum = np.sum(eta * state.position, axis=1) - np.sum(eta * initial.position, axis=0)
    momentum_scale = np.sum(eta * np.abs(state.position), axis=1)
    if np.any(np.abs(momentum) > (512 + STEP_ROUNDING * count[:, None]) * EPS * momentum_scale):
        raise NumericalError("Friction-weighted vertex sum changed: net force not zero")
    det = float(np.linalg.det(layout.box))
    area_error = np.abs(area_sum - det)
    if np.any(area_error > 1024 * EPS * (det + np.abs(area_sum))):
        raise NumericalError("Cell areas no longer tile the periodic box")
    return {
        "max_energy_balance_residual": float(np.max(np.abs(residual))),
        "max_energy_balance_allowance_used": float(
            np.max(np.abs(residual) / (state.energy_allowance[:, 0] + rounding))
        ),
        "max_momentum_drift": float(np.max(np.abs(momentum))),
        "max_area_identity_error": float(np.max(area_error)),
        "min_cell_area": float(np.min(min_area)),
        "min_junction_length": float(np.min(min_length)),
        "final_energy": float(energy[-1]),
        "final_dissipated_energy": float(dissipated[-1]),
        "final_control_work": float(work[-1]),
    }


def working_size(spec):
    x = spec.execution
    return 3 * x.vertex_capacity + 2 * x.junction_capacity + 6 * x.capacity + 16


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    position: np.ndarray
    cell_area: np.ndarray
    cell_perimeter: np.ndarray
    junction_length: np.ndarray
    energy: np.ndarray
    area_energy: np.ndarray
    perimeter_energy: np.ndarray
    line_energy: np.ndarray
    max_force: np.ndarray
    box_stress: np.ndarray
    dissipated_energy: np.ndarray
    control_work: np.ndarray
    energy_residual: np.ndarray


def _observe_row(position, mech, topo, box):
    g = vm.geometry(position, topo, box)
    area, perimeter, line = vm.energy_terms(position, topo, box, mech)
    force = vm.forces(position, topo, box, mech)
    return (
        g.area,
        g.perimeter,
        g.length,
        jnp.sum(area),
        jnp.sum(perimeter),
        jnp.sum(line),
        jnp.max(jnp.linalg.norm(force, axis=1)),
        vm.box_stress(position, topo, box, mech),
    )


_observe = jax.jit(jax.vmap(_observe_row, in_axes=(0, 0, None, None)))


def observe_history(times, history, layout, requested, spec):
    times, requested = np.asarray(times), np.asarray(requested, dtype=np.float64)
    index = np.searchsorted(times, requested)
    if np.any(index >= len(times)) or np.any(times[np.minimum(index, len(times) - 1)] != requested):
        raise ConfigError("Vertex observations are read only at accepted rows")
    rows = VertexState(*(np.asarray(v)[index] for v in history))
    layout = VertexLayout(*(np.asarray(v) for v in layout))
    topo = topology(layout)
    with jax.default_device(jax.devices("cpu")[0]):
        mech = vm.Mechanics(*(_on_cpu(getattr(rows, k)) for k in VertexState._fields[2:6]))
        values = [
            np.asarray(v)
            for v in _observe(_on_cpu(rows.position), mech, _on_cpu(topo), _on_cpu(layout.box))
        ]
    initial, _ = initial_values(spec)
    energy0 = float(vm.energy(initial.position, topo, layout.box, mechanics(initial), xp=np))
    area, perimeter, length, e_area, e_perimeter, e_line, max_force, stress = values
    energy = e_area + e_perimeter + e_line
    dissipated = rows.dissipated.sum(axis=1)
    work = rows.control_work[:, 0]
    return Observations(
        requested,
        rows.position,
        area,
        perimeter,
        length,
        energy,
        e_area,
        e_perimeter,
        e_line,
        max_force,
        stress,
        dissipated,
        work,
        energy + dissipated - work - energy0,
    )


def summarize(history, diagnostics, spec):
    m = spec.model
    return {
        "claim_scope": (
            "passive 2-D apical vertex mechanics on a fixed periodic topology in reduced "
            "units; no T1/T2, division, extrusion, noise or coupling; not calibrated"
        ),
        "model_id": MODEL_ID,
        "solver": spec.execution.solver,
        "state_axes": STATE_AXES,
        "vertices": len(m.vertices),
        "junctions": len(m.junctions),
        "cells": len(m.cells),
        **diagnostics,
    }
