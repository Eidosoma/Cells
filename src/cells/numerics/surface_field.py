"""Charge-constrained membrane surfaces with coupled return currents and baths.

Capacitance-connected nodes share an undetermined voltage offset. The charge
equations determine their relative potentials; Kirchhoff current balance fixes
the floating offsets. Reservoirs impose absolute outside voltages and expose
their electrode charge/current/work instead of hiding electrical sources.
"""

import contextvars
from contextlib import contextmanager
from typing import NamedTuple

import jax
import jax.numpy as jnp
import jax.scipy.linalg
import numpy as np

from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.numerics import sparse_cholesky as sparse
from cells.numerics import surface_transport as surface
from cells.numerics.extracellular_field import logmean
from cells.numerics.tissue_field import _bernoulli_derivative

LAW_ID = "resolved_capacitor_components_current_continuity@1"
SOLVER_ID = "capacitive_reduction_gauged_damped_newton@1"
# Same law and Newton; the constant capacitor reduction is Cholesky-factored
# once at bind, so each stage needs two triangular solves instead of two dense
# LU solves. This removes the dense O(N^3)-per-stage bound of version 1.
FACTORED_SOLVER_ID = "capacitive_reduction_gauged_damped_newton@2"
# Version 2 plus convergence at the attainable rounding floor of the offset
# Newton. Its iterations are version 2's, so wherever version 2 converges the
# result is bitwise the same; where version 2 stops above NEWTON_TARGET (line
# search unable to decrease, or the iteration bound), version 3 also accepts a
# residual within CURRENT_FLOOR_ULPS ulps of its potentials. The floor: a
# component's offset, and so each potential phi, is resolved only to about
# eps |phi|; a potential change of one ulp moves a face current by G (|phi_s| +
# |phi_r|) eps (G its conductance) and a junction current by its slope times
# eps (|phi_a| + |phi_b|). The computed Kirchhoff residual cannot be driven
# below about eps x that incident sum. Measured at refused P4 and P2 parity
# states: 1.2 eps x the sum under XLA and numpy alike, while the norm against
# CURRENT_ATOL_A differed 5x between them. 1e3 ulps is a potential error of
# about 1e-14 V; a solve whose residual is above it is still refused.
FLOOR_SOLVER_ID = "capacitive_reduction_gauged_damped_newton@3"
CURRENT_FLOOR_ULPS = 1e3
CURRENT_ATOL_A = 1e-23
CURRENT_RTOL = 2e-12
CHARGE_ATOL_C = 3e-25
CHARGE_RTOL = 2e-12
NEWTON_TARGET = 0.01
# Component net charge. Each capacitor component's representative node is fixed
# in the reduction, so its charge enters no potential and no offset: its row
# residual is the component's net charge, a conservation quantity rather than a
# convergence one. solve() reports it in charge_residual_C and charge_normalized
# but leaves it out of convergence; the identities' capacitor ledgers check it
# with charge_tolerance. Node increments are the state, so rounding in their
# stage additions (at most five per IMEX step, each up to u = eps/2 of the
# increment) moves a floating component's net charge by at most
# COMPONENT_STEP_ROUNDING eps x steps x its summed |z F dn| of stored increments.
# A closed world's gauge component holds the world's net charge less the
# floating components', and the implicit face drift returns a floating
# component's net charge to the gauge, so its rows allow the world's summed
# increments. Measured on the closed @1 fixture at 1 ms over 8000 steps
# (ledger-fix-20261109-01/diag/gauge_magnitudes.json): floating components
# stayed within 1e-26 C; the single-node gauge component reached 5.7e-25 C,
# 1.6 eps x the world's increments, about 1e4x inside the allowance; the fixed
# bound alone refuses that world within 5 s (3.6 s on the runner's grid).
# A component that holds a reservoir has no representative: its held node fixes
# its potential, so its net charge is carried by its electrodes instead, and the
# global charge ledger allows it the same rounding (grounded_tolerance).
COMPONENT_STEP_ROUNDING = 2.5
# FR-17 stage 1 (docs/FIELD_SOLVER_INTERFACE_DESIGN.md §8, D317): version 2's method (the same
# capacitive reduction, gauge, damped Newton on the floating offsets and acceptance checks) with the
# node-space linear algebra on static sparsity patterns bound once per definition: the capacitor
# matrix C on its pattern, the capacitor solve's factor, and the IMEX operator C + a L assembled,
# factored and solved on its pattern (numerics/sparse_cholesky: minimum degree, level-scheduled
# left-looking Cholesky, pairwise sums in a fixed order). No n x n array is bound or formed. The
# floating offsets keep version 2's dense algebra in their own dimension (floating components x
# components and x routes). Its bounds: SPARSE_MAX_NODES nodes, and SPARSE_MAX_ENTRIES entries in
# its bound arrays together (plans, factors and the floating basis), so the factor's fill, not the
# node count, sets the size it admits (§8.2).
SPARSE_SOLVER_ID = "sparse_capacitive_reduction_gauged_damped_newton@1"
MAX_NODES = 256
FACTORED_MAX_NODES = 2048
SPARSE_MAX_NODES = 65536
SPARSE_MAX_ENTRIES = 1 << 24
NODE_BOUNDS = {
    SOLVER_ID: MAX_NODES,
    FACTORED_SOLVER_ID: FACTORED_MAX_NODES,
    FLOOR_SOLVER_ID: FACTORED_MAX_NODES,
    SPARSE_SOLVER_ID: SPARSE_MAX_NODES,
}


class Layout(NamedTuple):
    surface: surface.Layout
    gauge_mask: object
    active: object
    fixed: object
    capacitor_matrix: object
    capacitor_scale: object
    capacitor_solve_matrix: object
    floating_basis: object
    offset_free: object
    face_incidence: object
    junction_incidence: object


# Version 2 layout: every version 1 field plus the lower Cholesky factor of
# capacitor_solve_matrix. A distinct pytree type keeps the dispatch static.
FactoredLayout = NamedTuple(
    "FactoredLayout", [(k, object) for k in (*Layout._fields, "capacitor_factor")]
)
# Version 3 layout: version 2's plus its floor in ulps (CURRENT_FLOOR_ULPS).
FloorLayout = NamedTuple(
    "FloorLayout", [(k, object) for k in (*FactoredLayout._fields, "current_floor")]
)
# The sparse layout (SPARSE_SOLVER_ID): version 1's fields without its two n x n matrices, then
# C's values on its pattern (capacitor_values, sparse_cholesky.ProductPlan order) with that
# pattern's product plan; the capacitor solve's factor on its pattern (capacitor_factor_values)
# with its solve plan; and the IMEX operator's pattern: C's values on it, its product plan, the
# face Laplacian's terms on it (each face's conductance, signed, in face order), the map of its
# entries into the reduced operator's factor positions (and the reduced operator's held diagonals,
# which hold 1), and the reduced operator's factor and solve plans. Every field is an array whose
# shape fixes the static choices, so a checkpoint carries them and validate_checkpoint compares
# them.
_PRODUCT_FIELDS = sparse.ProductPlan._fields
_SOLVE_FIELDS = sparse.SolvePlan._fields
_FACTOR_FIELDS = sparse.FactorPlan._fields
SparseLayout = NamedTuple(
    "SparseLayout",
    [
        (k, object)
        for k in (
            *(k for k in Layout._fields if k not in ("capacitor_matrix", "capacitor_solve_matrix")),
            "capacitor_values",
            *("capacitor_product_" + k for k in _PRODUCT_FIELDS),
            "capacitor_factor_values",
            *("capacitor_solve_" + k for k in _SOLVE_FIELDS),
            "operator_capacitor_values",
            *("operator_product_" + k for k in _PRODUCT_FIELDS),
            "operator_laplacian_face",
            "operator_laplacian_sign",
            "operator_laplacian_pairs",
            "operator_laplacian_out",
            "operator_assembly_position",
            "operator_assembly_entry",
            "operator_assembly_ones",
            *("operator_factor_" + k for k in _FACTOR_FIELDS),
            *("operator_solve_" + k for k in _SOLVE_FIELDS),
        )
    ],
)


def _plan(p, prefix, kind):
    return kind(*(getattr(p, prefix + k) for k in kind._fields))


def capacitor_product_plan(p):
    """The ProductPlan of C's pattern in a SparseLayout."""
    return _plan(p, "capacitor_product_", sparse.ProductPlan)


def capacitor_solve_plan(p):
    """The SolvePlan of the capacitor solve's factor in a SparseLayout."""
    return _plan(p, "capacitor_solve_", sparse.SolvePlan)


def operator_product_plan(p):
    """The ProductPlan of the IMEX operator's pattern in a SparseLayout."""
    return _plan(p, "operator_product_", sparse.ProductPlan)


def operator_factor_plan(p):
    """The FactorPlan of the reduced IMEX operator in a SparseLayout."""
    return _plan(p, "operator_factor_", sparse.FactorPlan)


def operator_solve_plan(p):
    """The SolvePlan of the reduced IMEX operator in a SparseLayout."""
    return _plan(p, "operator_solve_", sparse.SolvePlan)


class FormsField(NamedTuple):
    """The forms faces at one stage, for solve's offset balance: their entity set
    (surface_transport.FormsFaces), each mover's concentration (mM) at each face's sender and
    receiver [mover, forms face], and each face's incidence on the floating offsets [component,
    forms face] (basis[sender] - basis[receiver], as bind's face_incidence)."""

    faces: object
    left: object
    right: object
    incidence: object


class Values(NamedTuple):
    potential_V: object
    membrane_charge_C: object
    capacitor_node_charge_C: object
    charge_residual_C: object
    charge_normalized: object
    component_current_residual_A: object
    current_normalized: object
    electrode_charge_C: object
    electrode_current_A: object
    reservoir_supply_charge_A: object
    membrane_voltage_rate_V_s: object
    capacitor_energy_pJ: object
    capacitor_energy_rate_pJ_s: object
    chemical_energy_rate_pJ_s: object
    reservoir_power_pJ_s: object
    electrode_power_pJ_s: object
    dissipation_pJ_s: object
    energy_balance_pJ_s: object
    rates: surface.Rates
    iterations: object
    converged: object


# The forms faces' return paths (logmean_electrodiffusion_forms@1; models/surface_pump_v3): each a
# charged path between two outside nodes (index pairs) that the layout's faces do not hold, since
# forms faces are their own entity set. bind's connectivity check counts them, so a floating
# component whose only path to a clamp is a forms face is admitted. Empty outside return_paths,
# which resolved_pump_tissue@3's initial_values enters and leaves around its one base binding, so
# every other binding is today's. bind is its only reader.
_RETURN_PATHS = contextvars.ContextVar("forms_face_return_paths", default=())


@contextmanager
def return_paths(pairs):
    """Within the block, bind counts these (sender, receiver) outside-node index pairs as charged
    return paths (the forms faces')."""
    token = _RETURN_PATHS.set(tuple((int(a), int(b)) for a, b in pairs))
    try:
        yield
    finally:
        _RETURN_PATHS.reset(token)


def bind(layout, gauge_mask, *, solver=SOLVER_ID):
    """Host-only capacitance topology, fixed gauge and fail-closed connectivity.

    A reservoir is both a concentration bath and a voltage clamp in this law.
    Closed graphs require exactly one outside gauge. All floating components
    need a charged outside-face path to a clamp/gauge even if junctions close:
    a face of the layout, or a forms face's return path (return_paths).
    The factored solver returns a FactoredLayout with the same reduction, and
    the floor solver a FloorLayout. The sparse solver (SPARSE_SOLVER_ID) returns
    a SparseLayout: the same reduction on its patterns, no n x n array formed.
    """
    if solver not in NODE_BOUNDS:
        raise ValueError("Unknown resolved field solver")
    p = surface.validate_layout(layout)
    n, o = p.cell_active.size, p.outside_active.size
    size = n + o
    if size > NODE_BOUNDS[solver]:
        raise ValueError("Resolved field exceeds the declared bounded dense node limit")
    sparse_field = solver == SPARSE_SOLVER_ID
    gauge = np.asarray(gauge_mask)
    if gauge.shape != (o,) or gauge.dtype != np.bool_:
        raise ValueError("Resolved field gauge must be an outside boolean mask")
    if gauge.sum() != (0 if np.any(p.reservoir) else 1) or np.any(gauge & ~p.outside_active):
        raise ValueError("Use reservoir voltage clamps or exactly one active outside gauge")
    active = np.r_[p.cell_active, p.outside_active]
    parent = list(range(size))

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i

    def join(i, j):
        parent[root(j)] = root(i)

    # The sparse field accumulates C's entries in the same membrane order with the same additions,
    # so each of its entries is the dense matrix's, bit for bit.
    capacitor = None if sparse_field else np.zeros((size, size))
    entries = {}
    for k in np.flatnonzero(p.membrane_active):
        i, j = int(p.membrane_cell[k]), n + int(p.membrane_outside[k])
        c = p.membrane_capacitance[k]
        join(i, j)
        if sparse_field:
            for key, value in (((i, i), c), ((j, j), c), ((i, j), -c), ((j, i), -c)):
                entries[key] = entries.get(key, 0.0) + value
            continue
        capacitor[i, i] += c
        capacitor[j, j] += c
        capacitor[i, j] -= c
        capacitor[j, i] -= c
    groups = {}
    for i in np.flatnonzero(active):
        groups.setdefault(root(int(i)), []).append(int(i))
    reservoirs = set((n + np.flatnonzero(p.reservoir)).tolist())
    gauge_nodes = set((n + np.flatnonzero(gauge)).tolist())
    fixed = ~active.copy()
    fixed[list(reservoirs)] = True
    floating, free = [], []
    for members in groups.values():
        if reservoirs.intersection(members):
            continue
        choices = gauge_nodes.intersection(members)
        representative = next(iter(choices)) if choices else min(i for i in members if i >= n)
        fixed[representative] = True
        floating.append(np.isin(np.arange(size), members).astype(float))
        free.append(not bool(choices))
    basis = np.asarray(floating).reshape((-1, size)).T
    offset_free = np.asarray(free, dtype=bool)
    # Connectivity of the reduced offsets through guaranteed outside conductance.
    reached = {root(i) for i in reservoirs | gauge_nodes}
    edges = []
    conductive = np.any((p.valence != 0) & (p.face_factor > 0), axis=0)
    for k in np.flatnonzero(p.face_active & conductive):
        edges.append((root(n + int(p.face_sender[k])), root(n + int(p.face_receiver[k]))))
    for a, b in _RETURN_PATHS.get():  # The forms faces' (empty outside return_paths).
        edges.append((root(n + a), root(n + b)))
    for _ in groups:
        for i, j in edges:
            if i in reached or j in reached:
                reached.update((i, j))
    if reached != set(groups):
        raise ValueError(
            "Floating capacitor components require an outside return path to a clamp/gauge"
        )
    if sparse_field:
        return _bind_sparse(p, gauge, active, fixed, entries, basis, offset_free)
    scale = np.max(np.abs(capacitor))
    solve_matrix = np.where((~fixed)[:, None] & (~fixed)[None, :], capacitor / scale, 0.0)
    solve_matrix += np.diag(fixed.astype(float))
    # A singular capacitance reduction is an invalid layout, never regularized.
    factor = np.linalg.cholesky(solve_matrix)
    values = (
        p,
        gauge,
        active,
        fixed,
        capacitor,
        np.asarray(scale),
        solve_matrix,
        basis,
        offset_free,
        (basis[n + p.face_sender] - basis[n + p.face_receiver]).T,
        (basis[p.junction_sender] - basis[p.junction_receiver]).T,
    )
    if solver == FACTORED_SOLVER_ID:
        return FactoredLayout(*values, factor)
    if solver == FLOOR_SOLVER_ID:
        return FloorLayout(*values, factor, np.asarray(CURRENT_FLOOR_ULPS))
    return Layout(*values)


def _coordinates(pairs):
    """Two int64 arrays (rows, columns) of an iterable of (row, column) pairs."""
    pairs = list(pairs)
    return (np.asarray([i for i, _ in pairs], dtype=np.int64),
            np.asarray([j for _, j in pairs], dtype=np.int64))  # fmt: skip


def _bind_sparse(p, gauge, active, fixed, entries, basis, offset_free):
    """bind's SparseLayout (host, once per definition): entries holds C's nonzero entries {(i, j):
    value}, accumulated as the dense matrix is (bind); fixed, basis and offset_free are bind's
    own."""
    n, o = p.cell_active.size, p.outside_active.size
    size = n + o
    scale = np.max(np.abs(np.fromiter(entries.values(), dtype=float, count=len(entries))),
                   initial=0.0)  # fmt: skip
    off = [(i, j) for i, j in entries if i != j]
    c_plan = sparse.product_plan(size, *_coordinates(off))
    c_values = np.asarray(
        [entries.get(key, 0.0)
         for key in zip(c_plan.row.tolist(), c_plan.column.tolist(), strict=True)]  # fmt: skip
    )
    # The capacitor solve: C / scale on the solved rows and columns, 1 on the fixed diagonal (the
    # dense path's solve matrix entry by entry), factored here once, as version 2 factors it.
    solved = ~fixed
    keep = [(i, j) for i, j in off if solved[i] and solved[j]]
    symbolic = sparse.bind(size, *_coordinates(keep))
    lower = [(i, j) for i, j in keep if i > j] + [(i, i) for i in range(size)]
    values = np.zeros(symbolic.row.size)
    values[sparse.positions(symbolic, *_coordinates(lower))] = [
        entries.get((i, j), 0.0) / scale + 0.0 if solved[i] else 0.0 + 1.0 for i, j in lower
    ]
    with np.errstate(invalid="ignore", divide="ignore"):
        factor = sparse.factor(values, sparse.factor_plan(symbolic), xp=np)
    pivots = factor[symbolic.column_start[:-1]]
    if not (bool(sparse.finite(factor, xp=np)) and np.all(pivots > 0)):
        # A singular capacitance reduction is an invalid layout, never regularized.
        raise ValueError("The capacitor reduction is not positive definite")
    # The IMEX operator's pattern: C's and every face slot's (n + sender, n + receiver), then the
    # reduced operator on the free nodes (every active node but the clamps, factor_operator's).
    clamp = np.r_[np.zeros(n, dtype=bool), p.reservoir | gauge]
    free = active & ~clamp
    faces = [(n + int(a), n + int(b)) for a, b in zip(p.face_sender, p.face_receiver, strict=True)]
    m_pairs = set(off) | {(a, b) for a, b in faces if a != b} | {(b, a) for a, b in faces if a != b}
    m_plan = sparse.product_plan(size, *_coordinates(m_pairs))
    m_keys = zip(m_plan.row.tolist(), m_plan.column.tolist(), strict=True)
    m_index = {key: e for e, key in enumerate(m_keys)}
    m_capacitor = np.asarray([entries.get(key, 0.0) for key in m_index])
    # The face Laplacian on the pattern: each face's conductance +g at (a, a) and (b, b) and -g at
    # (a, b) and (b, a); an entry's terms in face order, then in that order of the four.
    contributions = [[] for _ in m_index]
    for f, (a, b) in enumerate(faces):
        for key, sign in (((a, a), 1.0), ((b, b), 1.0), ((a, b), -1.0), ((b, a), -1.0)):
            contributions[m_index[key]].append((f, sign))
    segments, face, sign = [], [], []
    for terms in contributions:
        segments.append(list(range(len(face), len(face) + len(terms))))
        face += [f for f, _ in terms]
        sign += [s for _, s in terms]
    l_pairs, l_out = sparse.pairwise_plan(segments, len(face))
    reduced = [(i, j) for i, j in m_pairs if free[i] and free[j]]
    operator = sparse.bind(size, *_coordinates(reduced))
    from_m = [(i, j) for i, j in reduced if i > j] + [(i, i) for i in range(size) if free[i]]
    held = [i for i in range(size) if not free[i]]
    values = dict(
        surface=p,
        gauge_mask=gauge,
        active=active,
        fixed=fixed,
        capacitor_scale=np.asarray(scale),
        floating_basis=basis,
        offset_free=offset_free,
        face_incidence=(basis[n + p.face_sender] - basis[n + p.face_receiver]).T,
        junction_incidence=(basis[p.junction_sender] - basis[p.junction_receiver]).T,
        capacitor_values=c_values,
        capacitor_factor_values=factor,
        operator_capacitor_values=m_capacitor,
        operator_laplacian_face=np.asarray(face, dtype=np.int64),
        operator_laplacian_sign=np.asarray(sign, dtype=float),
        operator_laplacian_pairs=l_pairs,
        operator_laplacian_out=l_out,
        operator_assembly_position=sparse.positions(operator, *_coordinates(from_m)),
        operator_assembly_entry=np.asarray([m_index[key] for key in from_m], dtype=np.int64),
        operator_assembly_ones=sparse.positions(operator, held, held),
    )
    for prefix, plan in (
        ("capacitor_product_", c_plan),
        ("capacitor_solve_", sparse.solve_plan(symbolic)),
        ("operator_product_", m_plan),
        ("operator_factor_", sparse.factor_plan(operator)),
        ("operator_solve_", sparse.solve_plan(operator)),
    ):
        values.update({prefix + k: v for k, v in plan._asdict().items()})
    total = sum(np.asarray(v).size for k, v in values.items() if k != "surface")
    if total > SPARSE_MAX_ENTRIES:
        raise ValueError(
            f"The sparse field's bound arrays hold {total} entries, above its bound of "
            f"{SPARSE_MAX_ENTRIES} (SPARSE_MAX_ENTRIES)"
        )
    return SparseLayout(**values)


def capacitor_product(p, x, *, xp):
    """C x for a field layout: the dense layouts' matrix product (their program as before), or the
    SparseLayout's product on C's pattern. x is [nodes] or [nodes, ...]."""
    if isinstance(p, SparseLayout):
        return sparse.product(p.capacitor_values, x, capacitor_product_plan(p), xp=xp)
    return p.capacitor_matrix @ x


def capacitor_diagonal(p, *, xp):
    """diag(C) for a field layout."""
    if isinstance(p, SparseLayout):
        return xp.asarray(p.capacitor_values)[p.capacitor_product_diagonal]
    return xp.diagonal(p.capacitor_matrix)


def capacitor_factor_solve(rhs, p, *, xp):
    """The capacitor solve matrix's solve of rhs ([nodes] or [nodes, ...], zero on the fixed rows):
    version 1's dense solve, version 2's and 3's bound factor, or the SparseLayout's."""
    if isinstance(p, SparseLayout):
        return sparse.solve(p.capacitor_factor_values, rhs, capacitor_solve_plan(p), xp=xp)
    if isinstance(p, (FactoredLayout, FloorLayout)):
        return cholesky_solve(p.capacitor_factor, rhs, xp=xp)
    return xp.linalg.solve(p.capacitor_solve_matrix, rhs)


def representatives(p, *, xp=np):
    """Node mask of component representatives: fixed in the reduction, active, not held.

    A representative's capacitor row residual is its component's net charge
    (the gauge of a closed world, or the lowest outside node of a floating
    component). Reservoir nodes are held and checked by the electrode ledger.
    """
    n = p.surface.cell_active.size
    held = xp.concatenate((xp.zeros(n, dtype=bool), xp.asarray(p.surface.reservoir)))
    return xp.asarray(p.fixed) & xp.asarray(p.active) & ~held


def charge_tolerance(charge_C, increment_C, steps, p, *, xp=np):
    """Capacitor-ledger bound per node (cells, then outside nodes).

    charge_C is each node's charge and increment_C its summed |z F dn| of stored
    increments. Every row allows CHARGE_ATOL_C + CHARGE_RTOL |charge|; each
    representative row, which carries its component's net charge, also allows
    COMPONENT_STEP_ROUNDING eps x steps x the summed increments of its floating
    component, or of the whole world for the gauge's component, with steps the
    accepted steps at that state.
    """
    bound = CHARGE_ATOL_C + CHARGE_RTOL * xp.abs(charge_C)
    basis = xp.asarray(p.floating_basis)
    summed = xp.where(xp.asarray(p.offset_free), basis.T @ increment_C, xp.sum(increment_C))
    rounding = COMPONENT_STEP_ROUNDING * np.finfo(float).eps * steps * (basis @ summed)
    return bound + xp.where(representatives(p, xp=xp), rounding, 0.0)


def grounded_nodes(p, *, xp=np):
    """Node mask of the components grounded through a held node: their active, non-held nodes.

    bind gives a capacitor component that holds a reservoir no floating-basis column. Its held
    node fixes its potential, so no representative carries its net charge and every other node
    is solved; its electrodes carry that net charge (grounded_tolerance).
    """
    n = p.surface.cell_active.size
    held = xp.concatenate((xp.zeros(n, dtype=bool), xp.asarray(p.surface.reservoir)))
    floating = xp.any(xp.asarray(p.floating_basis) != 0, axis=1)
    return xp.asarray(p.active) & ~held & ~floating


def grounded_tolerance(increment_C, steps, p, *, xp=np):
    """The component rule's allowance for the components grounded through a held node (C).

    increment_C is each node's summed |z F dn| of stored increments and steps the accepted steps
    at that state. A held node's electrode charge is its plate-charge change: the IMEX step books
    it from the step's start and end charge states (surface_pump.electrode_increment), RK4
    integrates it from the same node rates. A component's capacitor rows sum to zero, so that
    plate charge is minus the net charge of the component's non-held nodes. The electrodes thus
    carry the grounded components' net charge, a conservation quantity that rounds as a floating
    component's does (charge_tolerance): by at most COMPONENT_STEP_ROUNDING eps x steps x the
    summed |z F dn| of those nodes' stored increments. 0 in a world with no such component.
    """
    summed = xp.sum(xp.where(grounded_nodes(p, xp=xp), increment_C, 0.0))
    return COMPONENT_STEP_ROUNDING * np.finfo(float).eps * steps * summed


def check_neutral_components(charge_C, potential_V, p):
    """Host, at definition: refuse a capacitor component that carries net charge.

    A component's capacitor rows sum to zero, so its charges have a solution only if they sum
    to zero. solve() fixes each component's representative, whose row residual C phi - charge
    is then the component's net charge: it enters no potential, so a definition that declares
    one would run as a different world. A run's capacitor ledgers bound that residual with
    charge_tolerance, whose allowance grows with the accepted steps because node increments
    round; a definition has taken no step, so its bound is charge_tolerance's fixed part, the
    ledger's own test of its first row. Field convergence applied that bound to these rows
    until gauge option 2 (9 November 2026) moved them to the ledgers. potential_V is the
    definition's capacitor solve (_capacitor_solve). ValueError, as bind's topology refusals,
    which the families' parsers report as a ConfigError.
    """
    charge_C = np.asarray(charge_C, dtype=float)
    if isinstance(p, SparseLayout):
        residual = capacitor_product(p, np.asarray(potential_V), xp=np) - charge_C
    else:
        residual = np.asarray(p.capacitor_matrix) @ np.asarray(potential_V) - charge_C
    bound = charge_tolerance(charge_C, np.zeros_like(charge_C), 0, p)
    charged = representatives(p) & ~(np.abs(residual) <= bound)  # NaN is refused too.
    if np.any(charged):
        worst = int(np.argmax(np.where(charged, np.abs(residual) / bound, -np.inf)))
        raise ValueError(
            f"A capacitor component carries net charge ({-residual[worst]:.3g} C against a "
            f"bound of {bound[worst]:.3g} C): its charges must sum to zero"
        )


def cholesky_solve(factor, rhs, *, xp):
    """Solve L L^T x = rhs with a lower factor; rhs may carry trailing columns."""
    if xp is not np:
        return jax.scipy.linalg.cho_solve((factor, True), rhs)
    # NumPy has no triangular solver: blocked substitution, small dense blocks.
    lower, upper = np.asarray(factor), np.ascontiguousarray(np.asarray(factor).T)
    y = np.array(rhs, dtype=np.result_type(lower, rhs), copy=True)
    starts = range(0, len(y), 64)
    for start in starts:
        stop = start + 64
        part = y[start:stop] - lower[start:stop, :start] @ y[:start]
        y[start:stop] = np.linalg.solve(lower[start:stop, start:stop], part)
    for start in reversed(starts):
        stop = start + 64
        part = y[start:stop] - upper[start:stop, stop:] @ y[stop:]
        y[start:stop] = np.linalg.solve(upper[start:stop, start:stop], part)
    return y


def _capacitor_solve(charge, boundary, p, *, xp):
    rhs = xp.where(
        ~p.fixed, (charge - capacitor_product(p, boundary, xp=xp)) / p.capacitor_scale, 0.0
    )
    return capacitor_factor_solve(rhs, p, xp=xp) + boundary


def _offset_solve(matrix, rhs, p, *, xp):
    if p.offset_free.size == 0:
        return xp.zeros_like(rhs)
    scale = xp.max(xp.abs(matrix), initial=0.0)
    scale = xp.where(scale > 0, scale, 1.0)  # Only the fixed gauge can remain.
    free = p.offset_free
    reduced = xp.where(free[:, None] & free[None, :], matrix / scale, 0.0)
    reduced += xp.diag((~free).astype(matrix.dtype))
    return xp.linalg.solve(reduced, xp.where(free, rhs / scale, 0.0))


def solve(
    ci,
    co,
    cell_charge_C,
    outside_charge_C,
    membrane_open,
    junction_open,
    boundary_V,
    p,
    *,
    xp=jnp,
    max_iterations=16,
    max_backtracks=12,
    forms=None,
):
    """Recompute one world's field and transport from same-stage state/controls.

    Charge inputs include fixed backgrounds and use coulombs. boundary_V is
    nonzero only at reservoir/gauge owners; boundary voltages are held constant
    when reporting instantaneous capacitor/electrode energy and charge rates.
    Every capacitor row is reported; convergence tests the solved rows, while
    each representative's row (its component's net charge) is the identities'
    capacitor-ledger check (charge_tolerance). Invalid/incompatible states or
    exhausted roots return converged=False; with a FloorLayout, a root within
    the attainable current floor (FLOOR_SOLVER_ID) counts as found.

    forms (static; None for every world without forms faces, whose program is
    then today's): a FormsField, the forms faces' movers at their ends and
    each face's incidence on the floating offsets. Their conductance joins the
    offset matrix and their currents the Kirchhoff residual, as the faces'
    do; their rates are the caller's (surface_transport.forms_face_transport).
    """
    if type(max_iterations) is not int or max_iterations < 0:
        raise ValueError("Require a nonnegative Newton bound")
    if type(max_backtracks) is not int or max_backtracks < 1:
        raise ValueError("Require a positive backtrack bound")
    s = p.surface
    n, o = s.cell_active.size, s.outside_active.size
    if cell_charge_C.shape != (n,) or outside_charge_C.shape != (o,) or boundary_V.shape != (o,):
        raise ValueError("Resolved field charge/boundary shape disagrees with geometry")
    charge = xp.concatenate((cell_charge_C, outside_charge_C))
    clamps = s.reservoir | p.gauge_mask
    boundary = xp.concatenate((xp.zeros_like(cell_charge_C), xp.where(clamps, boundary_V, 0.0)))
    base = _capacitor_solve(charge, boundary, p, xp=xp)
    required = p.active & ~xp.concatenate((xp.zeros(n, dtype=bool), s.reservoir))
    domain = (
        xp.all(xp.isfinite(charge))
        & xp.all(xp.isfinite(boundary_V))
        & xp.all(xp.where(p.active, True, charge == 0))
        & xp.all(xp.where(clamps, True, boundary_V == 0))
    )
    rt, z = R * s.temperature, s.valence
    mean, log = logmean(
        xp.where(s.face_active, co[:, s.face_sender], 1.0),
        xp.where(s.face_active, co[:, s.face_receiver], 1.0),
        xp=xp,
    )
    weight = s.face_factor * mean
    conductance = F**2 / rt * xp.sum(z * z * weight, axis=0)
    dv = base[n + s.face_sender] - base[n + s.face_receiver]
    face0 = F * xp.sum(z * weight * log, axis=0) + conductance * dv
    matrix = (p.face_incidence * conductance) @ p.face_incidence.T
    if forms is None:
        initial_offset = _offset_solve(matrix, -p.face_incidence @ face0, p, xp=xp)
    else:  # The forms faces' conductance and start currents, as the faces' (static).
        ff = forms.faces
        left_f = xp.where(ff.active, forms.left, 1.0)
        right_f = xp.where(ff.active, forms.right, 1.0)
        mean_f, log_f = logmean(left_f, right_f, xp=xp)
        weight_f = ff.factor * mean_f
        zf = ff.valence
        conductance_f = F**2 / rt * xp.sum(zf * zf * weight_f, axis=0)
        dv_f = base[n + ff.sender] - base[n + ff.receiver]
        face0_f = F * xp.sum(zf * weight_f * log_f, axis=0) + conductance_f * dv_f
        matrix = matrix + (forms.incidence * conductance_f) @ forms.incidence.T
        initial_offset = _offset_solve(
            matrix, -(p.face_incidence @ face0 + forms.incidence @ face0_f), p, xp=xp
        )

    def evaluate(offset):
        phi = base + p.floating_basis @ offset
        rates = surface.transport(ci, co, phi[:n], phi[n:], membrane_open, junction_open, s, xp=xp)
        residual = (
            p.face_incidence @ rates.face_current_A
            + p.junction_incidence @ rates.junction_current_A
        )
        scale = xp.maximum(
            xp.max(xp.abs(rates.face_current_A), initial=0.0),
            xp.max(xp.abs(rates.junction_current_A), initial=0.0),
        )
        forms_ok = True
        if forms is not None:  # The forms faces' currents join each floating component's balance.
            ff = forms.faces
            fr = surface.forms_face_transport(
                forms.left, forms.right, phi[n + ff.sender] - phi[n + ff.receiver],
                s.temperature, ff, xp=xp,
            )  # fmt: skip
            residual = residual + forms.incidence @ fr.current_A
            scale = xp.maximum(scale, xp.max(xp.abs(fr.current_A), initial=0.0))
            forms_ok = fr.valid
        norm = xp.max(xp.abs(residual), initial=0.0) / (CURRENT_ATOL_A + CURRENT_RTOL * scale)
        x = z * F * rates.junction_voltage_V / rt
        a, b = ci[:, s.junction_sender], ci[:, s.junction_receiver]
        slope = (
            F**2
            / rt
            * s.junction_area
            * junction_open
            * xp.sum(
                z
                * z
                * s.junction_permeability
                * (-a * _bernoulli_derivative(-x, xp=xp) - b * _bernoulli_derivative(x, xp=xp)),
                axis=0,
            )
        )
        slope = xp.where(s.junction_active, slope, 0.0)
        valid = domain & rates.valid & xp.isfinite(norm) & xp.all(xp.isfinite(phi))
        valid &= xp.all(xp.isfinite(slope) & (slope >= 0))
        if forms is not None:
            valid &= forms_ok
        return phi, rates, residual, norm, slope, valid

    def keep_going(state):
        count, _, norm, valid = state
        return (count < max_iterations) & (norm > NEWTON_TARGET) & valid

    def iteration(state):
        count, offset, _, _ = state
        _, _, residual, norm, slope, _ = evaluate(offset)
        jac = matrix + (p.junction_incidence * slope) @ p.junction_incidence.T
        delta = _offset_solve(jac, -residual, p, xp=xp)
        before = xp.max(xp.abs(residual), initial=0.0)

        def retry(search):
            step, _, _, accepted = search
            return (step < max_backtracks) & ~accepted

        def trial(search):
            step, _, _, _ = search
            proposal = offset + delta * (0.5**step)
            _, _, residual, norm, _, valid = evaluate(proposal)
            accepted = valid & (
                (xp.max(xp.abs(residual), initial=0.0) < before) | (norm <= NEWTON_TARGET)
            )
            return step + 1, proposal, norm, accepted

        search = (xp.asarray(0, dtype=xp.int32), offset, norm, xp.asarray(False))
        if xp is np:
            while retry(search):
                search = trial(search)
        else:
            search = jax.lax.while_loop(retry, trial, search)
        _, proposal, norm, accepted = search
        return count + 1, xp.where(accepted, proposal, offset), norm, accepted

    _, _, _, norm, _, valid = evaluate(initial_offset)
    state = (xp.asarray(0, dtype=xp.int32), initial_offset, norm, valid)
    if xp is np:
        while keep_going(state):
            state = iteration(state)
    else:
        state = jax.lax.while_loop(keep_going, iteration, state)
    count, offset, _, accepted = state
    phi, rates, current_residual, norm, slope, valid = evaluate(offset)
    rooted = accepted & (norm <= NEWTON_TARGET)
    if isinstance(p, FloorLayout):  # Version 3: or within the attainable floor.
        size = xp.abs(phi)
        incident = xp.abs(p.face_incidence) @ (
            conductance * (size[n + s.face_sender] + size[n + s.face_receiver])
        ) + xp.abs(p.junction_incidence) @ (
            slope * (size[s.junction_sender] + size[s.junction_receiver])
        )
        if forms is not None:  # The forms faces' currents round as the faces' do.
            incident = incident + xp.abs(forms.incidence) @ (
                conductance_f * (size[n + forms.faces.sender] + size[n + forms.faces.receiver])
            )
        floor = p.current_floor * np.finfo(float).eps * incident
        rooted |= xp.all(xp.abs(current_residual) <= floor)
    patch_charge = s.membrane_capacitance * rates.membrane_voltage_V
    cap_charge = capacitor_product(p, phi, xp=xp)
    residual = xp.where(required, cap_charge - charge, 0.0)
    charge_scale = xp.maximum(xp.abs(charge), xp.abs(cap_charge))
    charge_bound = CHARGE_ATOL_C + CHARGE_RTOL * charge_scale
    charge_norm = xp.max(xp.abs(residual) / charge_bound)
    solved = required & ~p.fixed  # Representatives carry net charge, not a solve residual.
    solved_norm = xp.max(xp.where(solved, xp.abs(residual), 0.0) / charge_bound)
    electrode_charge = xp.where(s.reservoir, cap_charge[n:] - outside_charge_C, 0.0)
    amount_rates = xp.concatenate((rates.cell_rate_fmol_s, rates.outside_rate_fmol_s), axis=1)
    ionic_rate = CHARGE_PER_FMOL * xp.sum(z * amount_rates, axis=0)
    derivative = _capacitor_solve(ionic_rate, xp.zeros_like(phi), p, xp=xp)
    vm_rate = xp.where(
        s.membrane_active, derivative[s.membrane_cell] - derivative[n + s.membrane_outside], 0.0
    )
    electrode_current = xp.where(s.reservoir, capacitor_product(p, derivative, xp=xp)[n:], 0.0)
    supply_charge = CHARGE_PER_FMOL * xp.sum(z * rates.reservoir_supply_fmol_s, axis=0)
    chemical_rate = (
        1e-3
        * rt
        * (
            xp.sum(xp.log(ci) * rates.cell_rate_fmol_s)
            + xp.sum(xp.log(co) * rates.outside_rate_fmol_s)
        )
    )
    capacitor_energy = 0.5e12 * xp.sum(patch_charge * rates.membrane_voltage_V)
    capacitor_rate = 1e12 * xp.sum(patch_charge * vm_rate)
    reservoir_power = 1e-3 * xp.sum(
        (rt * xp.log(co) + z * F * phi[n:]) * rates.reservoir_supply_fmol_s
    )
    electrode_power = 1e12 * xp.sum(phi[n:] * electrode_current)
    dissipation = (
        xp.sum(rates.membrane_dissipation_pJ_s)
        + xp.sum(rates.junction_dissipation_pJ_s)
        + xp.sum(rates.face_dissipation_pJ_s)
    )
    energy_balance = (
        chemical_rate + capacitor_rate + dissipation - reservoir_power - electrode_power
    )
    physical = (
        phi,
        patch_charge,
        cap_charge,
        residual,
        charge_norm,
        current_residual,
        norm,
        electrode_charge,
        electrode_current,
        supply_charge,
        vm_rate,
        capacitor_energy,
        capacitor_rate,
        chemical_rate,
        reservoir_power,
        electrode_power,
        dissipation,
        energy_balance,
    )
    for value in physical:
        valid &= xp.all(xp.isfinite(value))
    converged = valid & rooted & (solved_norm <= 1.0)
    return Values(*physical, rates, count, converged)
