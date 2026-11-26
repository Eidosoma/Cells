"""Linearly implicit face electromigration for the resolved capacitor field.

The field law (surface_field.LAW_ID) is unchanged; this module only discretizes
it in time. With physical extracellular coefficients, charge relaxes through
face conductance against the patch capacitors within 10-100 ns, so explicit
stages would need steps of a few tens of nanoseconds. Here the face drift
(electromigration) is implicit: one SPD node-space system per implicit stage,

    (C + a dt L) phi = q,

where C is the capacitor Laplacian, L the face-conductance Laplacian built from
frozen face weights W, and q the node charges after the stage's explicit
increments. Reservoirs and a closed-system gauge are held at their boundary
potentials; every other active node, including floating-component
representatives, is solved. Species then move by W z F/RT (phi_a - phi_b) with
the same W, so material moves in flux form and C phi = Q holds at every required
node of each accepted state. Membranes, junctions, pumps, gates and face
diffusion stay explicit. Both tableaux are stiffly accurate, and the implicit
diagonal is constant, so one Cholesky factorization serves a whole step. W is
rebuilt and the matrix refactored every step at the tableau's operator time:
the step start (Euler), or a first-order prediction of the midpoint (ARS(2,2,2);
sum b_i c_i = 1/2 keeps the frozen weights second-order).
"""

import math
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.laws.electrochemistry import CHARGE_PER_FMOL, MOL_PER_FMOL, F, R
from cells.numerics import sparse_cholesky as sparse
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import logmean, scatter

EULER_ID = "cells.solver.imex_euler_face_electromigration@1"
ARS222_ID = "cells.solver.imex_ars222_face_electromigration@1"
# N2 (FR-8 rung 1, D235): ARS(2,2,2) with each membrane's and junction's slope conductance in the
# operator beside the faces', frozen for the step, and each junction gate advanced by its
# exponential update at the stages, as the channel gates are ((a)), so no junction-gate step bound
# applies. @3 implements it (models/surface_pump_v3.py) and @3's parse admits it, so it runs
# wherever the ionic step is @3's (water@1 and the composite too). The development ID without
# (a), imex_ars222_implicit_conductances_n2_alone@0, ran only from frozen snapshots and never lands
# (RUNG1 §6, §10.20).
IMPLICIT_CONDUCTANCES_ID = "cells.solver.imex_ars222_implicit_conductances@1"
IMPLICIT_CONDUCTANCE_IDS = (IMPLICIT_CONDUCTANCES_ID,)
_GAMMA = 1.0 - 1.0 / math.sqrt(2.0)
_DELTA = 1.0 - 1.0 / (2.0 * _GAMMA)


class Tableau(NamedTuple):
    explicit: object  # [stage, stage], strictly lower triangular
    implicit: object  # [stage, stage], zero first stage, constant diagonal
    # Step fraction at which face weights are frozen: a scalar, or under an N2 ID one per frozen
    # block of the implicit operator (faces, then the routes' slope conductances).
    operator_time: object


TABLEAUX = {
    EULER_ID: Tableau(
        np.array([[0.0, 0.0], [1.0, 0.0]]), np.array([[0.0, 0.0], [0.0, 1.0]]), np.asarray(0.0)
    ),
    # Ascher, Ruuth and Spiteri (1997), ARS(2,2,2): L-stable SDIRK implicit part.
    ARS222_ID: Tableau(
        np.array([[0.0, 0.0, 0.0], [_GAMMA, 0.0, 0.0], [_DELTA, 1.0 - _DELTA, 0.0]]),
        np.array([[0.0, 0.0, 0.0], [0.0, _GAMMA, 0.0], [0.0, 1.0 - _GAMMA, _GAMMA]]),
        np.asarray(0.5),
    ),
}
# N2's entry: ARS(2,2,2)'s own arrays, with a vector operator time. A vector operator time holds one
# entry per frozen block of the implicit operator, the faces' weights and then the routes' slope
# conductances (here both at half the step), and only N2's IDs declare one. That vector is N2's
# static switch (by shape, as a tableau's stage count sets its scheme): every other ID keeps a
# scalar, so no other world's layout or program carries anything of N2 (the lead, 21 November
# 2026). Readers take the times through operator_times, which refuses any other shape.
for _id in IMPLICIT_CONDUCTANCE_IDS:
    TABLEAUX[_id] = Tableau(
        TABLEAUX[ARS222_ID].explicit, TABLEAUX[ARS222_ID].implicit, np.asarray([0.5, 0.5])
    )
for _id, _tableau in TABLEAUX.items():  # Only N2's IDs declare a vector operator time.
    if (np.shape(_tableau.operator_time) == (2,)) != (_id in IMPLICIT_CONDUCTANCE_IDS) or np.ndim(
        _tableau.operator_time
    ) not in (0, 1):
        raise ValueError(f"{_id}: a vector operator time is N2's alone, one entry per frozen block")


def operator_times(operator_time):
    """(the faces' operator time, the routes' or None) from a tableau's or a layout's operator time:
    a scalar under every ID but N2's, whose vector holds one entry per frozen block (faces, then
    routes). Any other shape refuses, so a mismatch never broadcasts silently. Static (by shape)."""
    shape = tuple(getattr(operator_time, "shape", ()))
    if shape == ():
        return operator_time, None
    if shape == (2,):
        return operator_time[0], operator_time[1]
    raise ValueError(
        "A tableau's operator time is a scalar, or under an N2 ID one entry per frozen block "
        f"(faces, then routes); got shape {shape}"
    )


class Operator(NamedTuple):
    factor: object  # Lower Cholesky factor of the diagonally scaled reduced matrix.
    scale: object  # Symmetric diagonal scaling of free rows/columns.
    matrix: object  # Unreduced C + a dt L, for residuals.
    held: object  # Clamp potentials (boundary at clamps, zero elsewhere).
    free: object


class SparseOperator(NamedTuple):
    """Operator's sparse form (surface_field.SPARSE_SOLVER_ID): the same quantities on the bound
    patterns, with the plans its solve and products run on."""

    factor: object  # The reduced matrix's factor on its pattern (sparse_cholesky's storage).
    scale: object  # Symmetric diagonal scaling of free rows/columns.
    matrix: object  # Unreduced C + a dt L on its pattern (its ProductPlan's order), for residuals.
    held: object  # Clamp potentials (boundary at clamps, zero elsewhere).
    free: object
    product: object  # sparse_cholesky.ProductPlan of the unreduced pattern.
    solve: object  # sparse_cholesky.SolvePlan of the reduced matrix.


def face_weights(co, s, *, xp=jnp):
    """W [species, face], fmol/s per unit dimensionless driving force, and ln(a/b).

    Matches surface_transport: flux = W * (ln a - ln b + z F dv / RT).
    """
    left = xp.where(s.face_active, co[:, s.face_sender], 1.0)
    right = xp.where(s.face_active, co[:, s.face_receiver], 1.0)
    mean, _ = logmean(left, right, xp=xp)
    weight = xp.where(s.face_active, s.face_factor * mean / MOL_PER_FMOL, 0.0)
    return weight, xp.where(s.face_active, xp.log(left) - xp.log(right), 0.0)


def drift_flux(weight, outside_potential, s, *, xp=jnp):
    dv = xp.where(
        s.face_active, outside_potential[s.face_sender] - outside_potential[s.face_receiver], 0.0
    )
    return weight * (s.valence * F / (R * s.temperature)) * dv


def face_laplacian(weight, s, *, xp=jnp):
    """Face-conductance Laplacian (S) embedded in the cell+outside node space."""
    n, o = s.cell_active.size, s.outside_active.size
    conductance = CHARGE_PER_FMOL * F / (R * s.temperature) * xp.sum(s.valence**2 * weight, axis=0)
    a, b = n + s.face_sender, n + s.face_receiver
    zero = xp.zeros((n + o, n + o), dtype=weight.dtype)
    return (
        scatter(conductance, zero, (a, a), xp=xp)
        + scatter(conductance, zero, (b, b), xp=xp)
        - scatter(conductance, zero, (a, b), xp=xp)
        - scatter(conductance, zero, (b, a), xp=xp)
    )


def laplacian_values(weight, s, p, *, xp=jnp):
    """face_laplacian's values on a SparseLayout's operator pattern (S, its ProductPlan's order):
    each face's conductance, as face_laplacian computes it, summed into its four entries in the
    layout's fixed order (surface_field._bind_sparse)."""
    conductance = CHARGE_PER_FMOL * F / (R * s.temperature) * xp.sum(s.valence**2 * weight, axis=0)
    terms = p.operator_laplacian_sign * conductance[p.operator_laplacian_face]
    return sparse.fold(terms, p.operator_laplacian_pairs, p.operator_laplacian_out, xp=xp)


def operator_laplacian(weight, s, p, *, xp=jnp):
    """The face Laplacian in the form p's factor_operator takes: face_laplacian's dense matrix, or a
    SparseLayout's values on its operator pattern (laplacian_values)."""
    if isinstance(p, field.SparseLayout):
        return laplacian_values(weight, s, p, xp=xp)
    return face_laplacian(weight, s, xp=xp)


def forms_face_weights(left, right, forms, *, xp=jnp):
    """face_weights for the forms faces (surface_transport.FormsFaces): W [mover, forms face] and
    ln(a/b), from each mover's concentration at the faces' senders and receivers."""
    left = xp.where(forms.active, left, 1.0)
    right = xp.where(forms.active, right, 1.0)
    mean, _ = logmean(left, right, xp=xp)
    weight = xp.where(forms.active, forms.factor * mean / MOL_PER_FMOL, 0.0)
    return weight, xp.where(forms.active, xp.log(left) - xp.log(right), 0.0)


def forms_drift_flux(weight, outside_potential, temperature, forms, *, xp=jnp):
    """drift_flux for the forms faces: each mover at its own valence."""
    dv = xp.where(
        forms.active, outside_potential[forms.sender] - outside_potential[forms.receiver], 0.0
    )
    return weight * (forms.valence * F / (R * temperature)) * dv


def forms_face_laplacian(weight, temperature, size, offset, forms, *, xp=jnp):
    """face_laplacian for the forms faces: each face's conductance sum_f z_f^2 W_f (S) between its
    two outside nodes, in the node space of `size` nodes whose outside nodes start at `offset`."""
    conductance = (
        CHARGE_PER_FMOL * F / (R * temperature) * xp.sum(forms.valence**2 * weight, axis=0)
    )
    a, b = offset + forms.sender, offset + forms.receiver
    zero = xp.zeros((size, size), dtype=weight.dtype)
    return (
        scatter(conductance, zero, (a, a), xp=xp)
        + scatter(conductance, zero, (b, b), xp=xp)
        - scatter(conductance, zero, (a, b), xp=xp)
        - scatter(conductance, zero, (b, a), xp=xp)
    )


def factor_operator(coefficient, laplacian, boundary_V, p, *, xp=jnp):
    """Factor (C + coefficient L) on free nodes; clamps are reservoirs or the gauge. A SparseLayout
    takes L as its values on the operator pattern (operator_laplacian), and gives a
    SparseOperator."""
    if isinstance(p, field.SparseLayout):
        return _factor_sparse(coefficient, laplacian, boundary_V, p, xp=xp)
    s = p.surface
    n = s.cell_active.size
    clamp = xp.concatenate((xp.zeros(n, dtype=bool), s.reservoir | p.gauge_mask))
    free = p.active & ~clamp
    held = xp.where(clamp, xp.concatenate((xp.zeros(n), boundary_V)), 0.0)
    matrix = p.capacitor_matrix + coefficient * laplacian
    diagonal = xp.where(free, xp.diagonal(matrix), 1.0)
    scale = 1.0 / xp.sqrt(xp.where(diagonal > 0, diagonal, 1.0))
    reduced = xp.where(free[:, None] & free[None, :], matrix * scale[:, None] * scale[None, :], 0.0)
    reduced += xp.diag((~free).astype(matrix.dtype))
    factor = xp.linalg.cholesky(reduced)
    valid = xp.all(diagonal > 0) & xp.all(xp.isfinite(factor))
    return Operator(factor, scale, matrix, held, free), valid


def _factor_sparse(coefficient, laplacian, boundary_V, p, *, xp):
    """factor_operator on a SparseLayout: the dense path's operations on the bound patterns, entry
    by entry. C + coefficient L on the operator pattern; the Jacobi scaling from its diagonal on the
    free nodes; each reduced entry (M_ij s_i) s_j, symmetrized as the dense Cholesky symmetrizes its
    input ((A + A^T) / 2, which leaves a diagonal entry exactly), and 1 on the held diagonal; then
    the sparse factor. A reduced entry is zero off the free nodes in both paths, and an entry of M
    is never -0.0, so the masks' and the held diagonal's additions of +0.0 are left out."""
    s = p.surface
    n = s.cell_active.size
    clamp = xp.concatenate((xp.zeros(n, dtype=bool), s.reservoir | p.gauge_mask))
    free = p.active & ~clamp
    held = xp.where(clamp, xp.concatenate((xp.zeros(n), boundary_V)), 0.0)
    matrix = p.operator_capacitor_values + coefficient * laplacian
    product = field.operator_product_plan(p)
    diagonal = xp.where(free, matrix[product.diagonal], 1.0)
    scale = 1.0 / xp.sqrt(xp.where(diagonal > 0, diagonal, 1.0))
    entry = p.operator_assembly_entry
    value = matrix[entry]
    row, column = scale[product.row[entry]], scale[product.column[entry]]
    reduced = (value * row * column + value * column * row) / 2
    plan = field.operator_factor_plan(p)
    values = xp.zeros(plan.column.shape[0], dtype=matrix.dtype)
    if xp is np:
        values[p.operator_assembly_position] = reduced
        values[p.operator_assembly_ones] = 1.0
    else:
        values = values.at[p.operator_assembly_position].set(reduced)
        values = values.at[p.operator_assembly_ones].set(1.0)
    factor = sparse.factor(values, plan, xp=xp)
    valid = xp.all(diagonal > 0) & sparse.finite(factor, xp=xp)
    solve = field.operator_solve_plan(p)
    return SparseOperator(factor, scale, matrix, held, free, product, solve), valid


def operator_product(operator, x, *, xp=jnp):
    """(C + a L) x with an Operator's unreduced matrix, or a SparseOperator's on its pattern."""
    if isinstance(operator, SparseOperator):
        return sparse.product(operator.matrix, x, operator.product, xp=xp)
    return operator.matrix @ x


def solve_operator(charge, operator, *, xp=jnp):
    """Stage potentials and their charge residual (C + aL) phi - q on free nodes."""
    o = operator
    if isinstance(o, SparseOperator):
        rhs = xp.where(o.free, (charge - operator_product(o, o.held, xp=xp)) * o.scale, 0.0)
        phi = xp.where(o.free, sparse.solve(o.factor, rhs, o.solve, xp=xp) * o.scale, o.held)
        return phi, xp.where(o.free, operator_product(o, phi, xp=xp) - charge, 0.0)
    rhs = xp.where(o.free, (charge - o.matrix @ o.held) * o.scale, 0.0)
    phi = xp.where(o.free, field.cholesky_solve(o.factor, rhs, xp=xp) * o.scale, o.held)
    return phi, xp.where(o.free, o.matrix @ phi - charge, 0.0)
