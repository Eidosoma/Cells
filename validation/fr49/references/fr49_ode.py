"""FR-49 references: the ODE integrations (SciPy, binary64), the README's cross-checks.

- World L: Radau at rtol 1e-13, its steps stopped at t1 and t2 (one solve per piece). The README's
  example is 1e-12; the tighter tolerance keeps the check below World L's declared 1e-13.
- World B: Radau at rtol 1e-12 on (B, n_L).
- C2: Radau at rtol 1e-12 and DOP853 at rtol 1e-13 on (B1, B2, n1, n2, R).
atol is 1e-30 throughout, so the error control is relative in every component. The thread
variables are pinned before NumPy is imported.
"""

from __future__ import annotations

import os
from itertools import pairwise

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np  # noqa: E402
from fr49_spec import Spec, WorldL  # noqa: E402
from scipy.integrate import solve_ivp  # noqa: E402

RTOL = 1e-12
RTOL_L = 1e-13  # World L: its check is held to World L's declared 1e-13 as well
RTOL_DOP853 = 1e-13
ATOL = 1e-30


def capacity(sites, sites_per_fmol: str) -> float:
    """S = alpha nu N / N_f from the declared strings, in binary64: the ODE routes' own S."""
    return (float(sites.accessible_fraction) * sites.sites_per_copy * float(sites.copies)
            / float(sites_per_fmol))


def _times(samples) -> list[float]:
    step = float(samples.step)
    return [step * i for i in range(samples.last + 1)]


def _solve(fun, jac, span, y0, t_eval, method, rtol):
    kwargs = {"jac": jac} if method == "Radau" else {}
    sol = solve_ivp(fun, span, y0, method=method, t_eval=t_eval, rtol=rtol, atol=ATOL, **kwargs)
    if not sol.success:
        raise RuntimeError(f"{method} failed: {sol.message}")
    return sol


def world_L_radau(L: WorldL) -> np.ndarray:
    """(n_O, n_C, x_O, x_C) at every sample time, shape (4, samples)."""
    V_O, V_C, a, k_d, P = (float(v) for v in (L.V_O, L.V_C, L.a, L.k_d, L.P))
    t1, t2, horizon = float(L.t1), float(L.t2), float(L.horizon)
    A = np.array([[-a / V_O, a / V_C], [a / V_O, -a / V_C - k_d]])
    big = np.zeros((4, 4))
    big[:2, :2] = A
    big[2:, 2:] = A
    times = _times(L.samples)
    y = np.array([float(L.n_O0), float(L.n_C0), float(L.x_O0), float(L.x_C0)])
    out = np.zeros((4, len(times)))
    out[:, 0] = y
    edges = sorted(dict.fromkeys([0.0] + [t for t in (t1, t2) if 0 < t < horizon] + [horizon]))
    for start, end in pairwise(edges):
        P_x = P if t1 <= start < t2 else 0.0
        source = np.array([P, 0.0, P_x, 0.0])
        inner = [t for t in times if start < t <= end]
        if inner[-1:] != [end]:
            inner.append(end)
        sol = _solve(lambda _t, v, s=source: big @ v + s, lambda _t, v: big, (start, end), y,
                     inner, "Radau", RTOL_L)
        for k, t in enumerate(sol.t):
            if t in times:
                out[:, times.index(t)] = sol.y[:, k]
        y = sol.y[:, -1]
    return out


def world_B_radau(spec: Spec) -> np.ndarray:
    """(B, n_L) at every sample time, shape (2, samples)."""
    W = spec.B
    S = capacity(W.sites, spec.sites_per_fmol)
    V_C, k_on, k_off = float(W.V_C), float(W.k_on), float(W.k_off)

    def fun(_t, v):
        J = k_on * (v[1] / V_C) * (S - v[0]) - k_off * v[0]
        return [J, -J]

    def jac(_t, v):
        dB = -k_on * v[1] / V_C - k_off
        dn = k_on * (S - v[0]) / V_C
        return [[dB, dn], [-dB, -dn]]

    times = _times(W.samples)
    sol = _solve(fun, jac, (0.0, times[-1]), [float(W.B0), float(W.n_L0)], times, "Radau", RTOL)
    return sol.y


def c2_integrate(spec: Spec, method: str) -> np.ndarray:
    """(B1, B2, n1, n2, R) at every sample time, shape (5, samples), by Radau or DOP853.

    The free sites R are a state of their own, dR/dt = -(J1 + J2) from R(0) = S - B1 - B2, so
    that each solver's relative error control covers R. Formed as S - B1 - B2 from the bound
    amounts, R would carry their errors amplified S/R times (about 50 near equilibrium)."""
    W = spec.C2
    S = capacity(W.sites, spec.sites_per_fmol)
    V_C = float(W.V_C)
    k_on = [float(g.k_on) for g in W.ligands]
    k_off = [float(g.k_off) for g in W.ligands]

    def fun(_t, v):
        J = [k_on[j] * (v[2 + j] / V_C) * v[4] - k_off[j] * v[j] for j in range(2)]
        return [J[0], J[1], -J[0], -J[1], -J[0] - J[1]]

    def jac(_t, v):
        rows = []
        for j in range(2):
            row = [0.0] * 5
            row[j] = -k_off[j]
            row[2 + j] = k_on[j] * v[4] / V_C
            row[4] = k_on[j] * v[2 + j] / V_C
            rows.append(row)
        dR = [-(a + b) for a, b in zip(rows[0], rows[1], strict=True)]
        return rows + [[-x for x in rows[0]], [-x for x in rows[1]], dR]

    times = _times(W.samples)
    B0 = [float(b) for b in W.B0]
    y0 = B0 + [float(g.total) - b for g, b in zip(W.ligands, B0, strict=True)]
    y0.append(S - B0[0] - B0[1])
    rtol = RTOL if method == "Radau" else RTOL_DOP853
    sol = _solve(fun, jac if method == "Radau" else None, (0.0, times[-1]), y0, times, method,
                 rtol)
    return sol.y
