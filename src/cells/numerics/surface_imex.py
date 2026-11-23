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
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import logmean, scatter

EULER_ID = "imex_euler_face_electromigration@1"
ARS222_ID = "imex_ars222_face_electromigration@1"
# N2 (FR-8 rung 1, D235): ARS(2,2,2) with each membrane's and junction's slope conductance in the
# operator beside the faces', frozen for the step, and each junction gate advanced by its
# exponential update at the stages, as the channel gates are ((a)), so no junction-gate step bound
# applies. @3 implements it (models/surface_pump_v3.py) and @3's parse admits it, so it runs
# wherever the ionic step is @3's (water@1 and the composite too). The development ID without
# (a), imex_ars222_implicit_conductances_n2_alone@0, ran only from frozen snapshots and never lands
# (RUNG1 §6, §10.20).
IMPLICIT_CONDUCTANCES_ID = "imex_ars222_implicit_conductances@1"
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
    """Factor (C + coefficient L) on free nodes; clamps are reservoirs or the gauge."""
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


def solve_operator(charge, operator, *, xp=jnp):
    """Stage potentials and their charge residual (C + aL) phi - q on free nodes."""
    o = operator
    rhs = xp.where(o.free, (charge - o.matrix @ o.held) * o.scale, 0.0)
    phi = xp.where(o.free, field.cholesky_solve(o.factor, rhs, xp=xp) * o.scale, o.held)
    return phi, xp.where(o.free, o.matrix @ phi - charge, 0.0)
