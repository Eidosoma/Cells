"""Stand-in steppers on the registered dt ladder: what an honest or a first-order engine gives.

These are not references. They let the design state, before any engine output, how far an
honest second-order engine lies from the exact solution at each dt of the ladder, and how far a
first-order one does, so that a tolerance can be placed between them and the planted controls.

**The schemes,** each applied with the bath of the step's start (events right-continuous, on the
grid):
- ``ars_implicit``: the implicit half of ARS(2,2,2) (Ascher, Ruuth and Spiteri 1997, Appl. Numer.
  Math. 25:151, §2.6), i.e. the L-stable two-stage SDIRK with gamma = 1 - 1/sqrt(2):
  Y2 = y + dt gamma f(Y2); y' = y + dt [(1 - gamma) f(Y2) + gamma f(y')].
- ``ars_explicit``: the explicit half of the same tableau, delta = 1 - 1/(2 gamma):
  Y2 = y + dt gamma f(y); y' = y + dt [delta f(y) + (1 - delta) f(Y2)]. Second order.
- ``implicit_euler``: first order, the planted scheme.
- ``rk4``: the classical fourth-order method.

An engine's IMEX split puts some terms in each half; the two pure halves bracket the error of a
second-order engine on these worlds, which have one kind of term each (faces, or one membrane).
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np

from .common import exact

GAMMA = 1.0 - 1.0 / math.sqrt(2.0)
DELTA = 1.0 - 1.0 / (2.0 * GAMMA)
SCHEMES = ("ars_implicit", "ars_explicit", "implicit_euler", "rk4")


def _grid(dt: float, t_end: float) -> int:
    n = round(t_end / dt)
    if abs(n * dt - t_end) > 1e-9 * dt:
        raise ValueError(f"t_end {t_end} is not on the grid of dt {dt}")
    return n


def _bath_index(step_start: Fraction, epochs) -> int:
    e = 0
    while e + 1 < len(epochs) and step_start >= epochs[e + 1][0]:
        e += 1
    return e


def step_linear(M: np.ndarray, c: np.ndarray, g: np.ndarray, dt: float, scheme: str):
    """One step of dc/dt = M c + g (g constant over the step)."""
    eye = np.eye(M.shape[0])
    if scheme == "implicit_euler":
        return np.linalg.solve(eye - dt * M, c + dt * g)
    if scheme == "ars_implicit":
        A = eye - GAMMA * dt * M
        Y2 = np.linalg.solve(A, c + GAMMA * dt * g)
        f2 = M @ Y2 + g
        return np.linalg.solve(A, c + dt * (1 - GAMMA) * f2 + GAMMA * dt * g)
    if scheme == "ars_explicit":
        k1 = M @ c + g
        Y2 = c + GAMMA * dt * k1
        k2 = M @ Y2 + g
        return c + dt * (DELTA * k1 + (1 - DELTA) * k2)
    if scheme == "rk4":
        k1 = M @ c + g
        k2 = M @ (c + 0.5 * dt * k1) + g
        k3 = M @ (c + 0.5 * dt * k2) + g
        k4 = M @ (c + dt * k3) + g
        return c + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
    raise ValueError(scheme)


def run_faces(world, dt: float, scheme: str, epochs=None, times=None) -> np.ndarray:
    """A stand-in run of a parsed face world: amounts [T, N] (fmol) at the record times."""
    epochs = world.epochs if epochs is None else [(exact(t), exact(c)) for t, c in epochs]
    times = world.times if times is None else np.asarray(times, dtype=np.float64)
    L, kb = world.conductance_matrix()
    V = np.array([float(v) for v in world.volume])
    M = np.array([[float(x) for x in row] for row in L]) / V[:, None]
    kbV = np.array([float(x) for x in kb]) / V
    n_steps = _grid(dt, float(times.max()))
    want = {round(float(t) / dt): k for k, t in enumerate(times)}
    out = np.empty((times.size, world.n))
    c = np.array([float(x) for x in world.c0])
    dt_exact = exact(dt)
    # Every scheme is affine in (c, g) for a linear problem: c' = P c + q_e.
    zero = np.zeros(world.n)
    P = np.column_stack([step_linear(M, col, zero, dt, scheme) for col in np.eye(world.n)])
    q = [step_linear(M, zero, kbV * float(cb), dt, scheme) for _, cb in epochs]
    if 0 in want:
        out[want[0]] = V * c
    for i in range(n_steps):
        e = _bath_index(i * dt_exact, epochs)
        c = P @ c + q[e]
        if i + 1 in want:
            out[want[i + 1]] = V * c
    return out


def _newton(F, x0: float, tol: float = 1e-17, h: float = 1e-7, maxit: int = 50) -> float:
    x = x0
    for _ in range(maxit):
        r = F(x)
        d = (F(x + h) - F(x - h)) / (2 * h)
        dx = -r / d
        x += dx
        if abs(dx) <= tol + 1e-15 * abs(x):
            return x
    raise RuntimeError("Newton did not converge")


def step_scalar(f, y: float, dt: float, scheme: str) -> float:
    """One step of dy/dt = f(y) (autonomous within the step)."""
    if scheme == "implicit_euler":
        return _newton(lambda x: x - y - dt * f(x), y + dt * f(y))
    if scheme == "ars_implicit":
        Y2 = _newton(lambda x: x - y - GAMMA * dt * f(x), y + GAMMA * dt * f(y))
        base = y + dt * (1 - GAMMA) * f(Y2)
        return _newton(lambda x: x - base - GAMMA * dt * f(x), Y2 + dt * f(Y2) * (1 - GAMMA))
    if scheme == "ars_explicit":
        k1 = f(y)
        k2 = f(y + GAMMA * dt * k1)
        return y + dt * (DELTA * k1 + (1 - DELTA) * k2)
    if scheme == "rk4":
        k1 = f(y)
        k2 = f(y + 0.5 * dt * k1)
        k3 = f(y + 0.5 * dt * k2)
        k4 = f(y + dt * k3)
        return y + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
    raise ValueError(scheme)


def run_ion(world, dt: float, scheme: str, epochs=None) -> dict:
    """A stand-in run of a parsed one-ion world: V_m [T] (V) and the ion's amount [T] (fmol).

    It integrates the scalar equation on the charge invariant, which every Runge-Kutta method
    preserves exactly (a linear invariant), so it equals stepping the full state.
    """
    from .ion import Fluxes  # local import: ion imports nothing from here
    epochs = world.epochs if epochs is None else epochs
    perm = world.permeant
    if len(perm) != 1:
        raise ValueError("the stand-in steps one permeant ion")
    p = perm[0]
    zp = world.z[p]
    times = world.times
    n_steps = _grid(dt, float(times.max()))
    want = {round(float(t) / dt): k for k, t in enumerate(times)}
    V0 = world.V0()
    n0 = float(world.amounts0[p])
    fl = [Fluxes(world, bath, [p]) for _, bath in epochs]
    per = 1.0 / (fl[0].q * zp)

    def f_for(e):
        fe = fl[e]
        return lambda V: -fe.q * zp * fe.J_list(V, [n0 + per * (V - V0)])[0]
    fs = [f_for(e) for e in range(len(epochs))]
    V_out = np.empty(times.size)
    V = V0
    dt_exact = exact(dt)
    if 0 in want:
        V_out[want[0]] = V
    for i in range(n_steps):
        e = _bath_index(i * dt_exact, epochs)
        V = step_scalar(fs[e], V, dt, scheme)
        if i + 1 in want:
            V_out[want[i + 1]] = V
    return {"V_m_V": V_out, "amount_fmol": n0 + per * (V_out - V0)}
