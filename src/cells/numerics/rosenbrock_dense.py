"""cells.solver.rosenbrock_rodas4_dense@1: Rodas4, a Rosenbrock method with an embedded error estimate and a
dense output (OL6; docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md §6.1, D304).

**The method** (Hairer and Wanner 1996, Solving Ordinary Differential Equations II, §VI.4: RODAS's
first coefficient set). For an autonomous system y' = f(y) with Jacobian J = f'(y), one step of
size h solves six linear systems with one matrix,

    (I/(γh) − J) U_i = f(Y_i) + Σ_(j<i) (C_ij/h) U_j,     Y_i = y + Σ_(j<i) A_ij U_j,

and takes y_new = y + Σ_j b_j U_j, with b = (A_61, …, A_65, 1). It is of order 4, L-stable and
stiffly accurate. U_6 is the embedded error estimate (an order-3 solution's difference), so the
step controller uses the exponent 1/4. The dense output, of order 3, is

    y(θ) = (1 − θ) y + θ (y_new + (1 − θ)(k_1 + θ k_2)),   k_m = Σ_j H_mj U_j,   θ in [0, 1].

The non-autonomous terms (Hairer's d_i h ∂f/∂t) are not used: every system this module serves is
autonomous between its caller's stops.

**The coefficients** are Hairer and Wanner's, as the MIT-licensed SciML tableau
(OrdinaryDiffEqRosenbrockTableaus, `Rodas4Tableau`: RODAS4A, RODAS4C, RODAS4H) states them; they
were read from that file on 22 November 2026, and the tests check the method's order, its dense
output's order and its L-stability, so a wrong digit fails.

**Linear invariants.** With the exact Jacobian, a linear invariant L (L·f ≡ 0, so L·J ≡ 0) is kept to
rounding by every stage: L·U_i = 0 follows from the stage equation (the design note's §2.4). The
caller supplies an exact Jacobian (forward differentiation of its own f).

**Determinism.** Every sum over stages is a fixed, unrolled order, and the error norm is a fixed
reduction, so a given program gives the same bits on every run. The caller drives steps and stops;
this module holds no state.

**A quantity carried by the stages** (`quadrature`; OL6 S3, the design note's §3.5). A quantity
Z' = k(y) that the system never reads (its Jacobian column is 0) is the augmented system's last
component, and the method's own stage equation for that row needs no new solve:

    U^Z_i = γh (k(Y_i) + ∇k(y)·U_i + Σ_(j<i) (C_ij/h) U^Z_j),

with Y_i and U_i the step's own stages (`Step.stages`). So Z is integrated by the same method, of
order 4 with its own embedded estimate U^Z_6 and dense output, while the step's arithmetic on y is
untouched: a system with such a quantity takes exactly the steps of its twin without it (an
appended row would enter the LU's pivoting).
"""

import math
from typing import NamedTuple

import jax.numpy as jnp
import jax.scipy.linalg as jsl
import numpy as np

METHOD_ID = "cells.solver.rosenbrock_rodas4_dense@1"
ORDER = 4  # the solution's; the embedded estimate and the dense output are of order 3
GAMMA = 0.25
A = np.array(
    [
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [1.544, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.9466785280815826, 0.2557011698983284, 0.0, 0.0, 0.0, 0.0],
        [3.314825187068521, 2.896124015972201, 0.9986419139977817, 0.0, 0.0, 0.0],
        [1.221224509226641, 6.019134481288629, 12.53708332932087, -0.687886036105895, 0.0, 0.0],
        [1.221224509226641, 6.019134481288629, 12.53708332932087, -0.687886036105895, 1.0, 0.0],
    ]
)
C = np.array(
    [
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [-5.6688, 0.0, 0.0, 0.0, 0.0],
        [-2.430093356833875, -0.2063599157091915, 0.0, 0.0, 0.0],
        [-0.1073529058151375, -9.594562251023355, -20.47028614809616, 0.0, 0.0],
        [7.496443313967647, -10.24680431464352, -33.99990352819905, 11.7089089320616, 0.0],
        [8.083246795921522, -7.981132988064893, -31.52159432874371, 16.31930543123136,
         -6.058818238834054],
    ]
)  # fmt: skip
H = np.array(
    [
        [10.12623508344586, -7.487995877610167, -34.80091861555747, -7.992771707568823,
         1.025137723295662, 0.0],
        [-0.6762803392801253, 6.087714651680015, 16.43084320892478, 24.76722511418386,
         -6.594389125716872, 0.0],
    ]
)  # fmt: skip
B = np.array([*A[5, :5], 1.0])  # y_new = y + Σ b_j U_j
STAGES = 6

# The step controller (Hairer and Wanner's standard form, from their RODAS: a safety factor and
# bounds on the change of h per step).
SAFETY = 0.9
GROW = 6.0
SHRINK = 0.2

SOURCE = (
    "Hairer E, Wanner G (1996), Solving Ordinary Differential Equations II, 2nd ed., Springer, "
    "§VI.4 (RODAS, coefficient set 1); coefficients as SciML's OrdinaryDiffEqRosenbrockTableaus "
    "states them (MIT licence)"
)


class Step(NamedTuple):
    """One step's outputs: the new state, the embedded error estimate, the dense output's two
    coefficient vectors, whether every stage was finite, and the stages U_i [STAGES, size] (for a
    quantity they carry, `quadrature`)."""

    y: object
    error: object
    k1: object
    k2: object
    finite: object
    stages: object


def _combine(weights, vectors, start=None):
    """start + Σ_j w_j v_j in j order, skipping exact zeros (fixed and unrolled)."""
    out = start
    for w, v in zip(weights, vectors, strict=False):
        if w == 0.0:
            continue
        term = float(w) * v
        out = term if out is None else out + term
    return out


def step(rhs, jacobian, y, h):
    """One Rodas4 step of y' = rhs(y) from y with step h; rhs and jacobian are traceable."""
    size = y.shape[0]
    matrix = jnp.eye(size, dtype=y.dtype) / (GAMMA * h) - jacobian(y)
    lu = jsl.lu_factor(matrix)
    stages = []
    finite = jnp.all(jnp.isfinite(matrix))
    for i in range(STAGES):
        point = y if i == 0 else _combine(A[i, :i], stages, start=y)
        f = rhs(point)
        coupling = _combine(C[i, :i] / 1.0, stages) if i > 0 else None
        right = f if coupling is None else f + coupling / h
        u = jsl.lu_solve(lu, right)
        finite = finite & jnp.all(jnp.isfinite(u))
        stages.append(u)
    y_new = _combine(B, stages, start=y)
    k1 = _combine(H[0], stages)
    k2 = _combine(H[1], stages)
    return Step(y_new, stages[-1], k1, k2, finite, jnp.stack(stages))


def dense(y, result, theta):
    """The dense output at θ in [0, 1] of a step from y (order 3)."""
    return (1.0 - theta) * y + theta * (result.y + (1.0 - theta) * (result.k1 + theta * result.k2))


class Carried(NamedTuple):
    """A carried quantity's step (`quadrature`): its increment, its embedded error estimate and its
    dense output's two coefficients, each of the quantity's shape."""

    increment: object
    error: object
    k1: object
    k2: object


def quadrature(rate, gradient, y, h, stages):
    """Z' = rate(y), carried by the stages of the step from y with step h (the module docstring):
    rate(y) and gradient(y) = ∂rate/∂y (shape [..., size]) are traceable; the stages are
    Step.stages. The quantity's start value never enters: Z_new = Z + increment."""
    grad = gradient(y)
    units = [stages[i] for i in range(STAGES)]
    carried = []
    for i in range(STAGES):
        point = y if i == 0 else _combine(A[i, :i], units, start=y)
        right = rate(point) + grad @ units[i]
        coupling = _combine(C[i, :i] / 1.0, carried) if i > 0 else None
        if coupling is not None:
            right = right + coupling / h
        carried.append(GAMMA * h * right)
    return Carried(_combine(B, carried), carried[-1], _combine(H[0], carried),
                   _combine(H[1], carried))  # fmt: skip


def dense_carried(start, carried, theta):
    """A carried quantity's dense output at θ in [0, 1], from its value at the step's start."""
    end = start + carried.increment
    return (1.0 - theta) * start + theta * (end + (1.0 - theta) * (carried.k1 + theta * carried.k2))


def error_norm(error, y, y_new, rtol, atol, weight):
    """The weighted root mean square of the error estimate over the controlled components
    (weight 1) and none of the others (weight 0): scale atol + rtol·max(|y|, |y_new|)."""
    scale = atol + rtol * jnp.maximum(jnp.abs(y), jnp.abs(y_new))
    ratio = weight * error / scale
    count = jnp.maximum(jnp.sum(weight), 1.0)
    return jnp.sqrt(jnp.sum(ratio * ratio) / count)


def next_step(h, norm, rejected):
    """The next step size (host floats): h·min(GROW, max(SHRINK, SAFETY·norm^(−1/4))), at most h
    after a rejection."""
    if not math.isfinite(norm):
        return h * SHRINK
    factor = GROW if norm == 0.0 else min(GROW, max(SHRINK, SAFETY * norm ** (-1.0 / ORDER)))
    if rejected:
        factor = min(1.0, factor)
    return h * factor


def initial_step(rhs, y, rtol, atol, weight, span):
    """A first step (Hairer, Nørsett and Wanner 1993, §II.4's starting step, from memory), at most
    `span`: from the sizes of y, f(y) and an Euler step's change of f (host floats)."""
    y = np.asarray(y, dtype=np.float64)
    f0 = np.asarray(rhs(jnp.asarray(y)), dtype=np.float64)
    w = np.asarray(weight, dtype=np.float64)
    count = max(float(np.sum(w)), 1.0)
    scale = atol + rtol * np.abs(y)

    def size(v):
        return float(np.sqrt(np.sum((w * v / scale) ** 2) / count))

    d0, d1 = size(y), size(f0)
    h0 = 1e-6 if (d0 < 1e-5 or d1 < 1e-5) else 0.01 * d0 / d1
    h0 = min(h0, span)
    f1 = np.asarray(rhs(jnp.asarray(y + h0 * f0)), dtype=np.float64)
    d2 = size(f1 - f0) / h0
    largest = max(d1, d2)
    h1 = max(1e-6, h0 * 1e-3) if largest <= 1e-15 else (0.01 / largest) ** (1.0 / (ORDER + 1))
    return min(100.0 * h0, h1, span)
