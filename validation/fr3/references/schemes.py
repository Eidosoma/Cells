"""A stand-in honest engine for the dt study (not a reference).

The design runs the operator's whole network as one SSPRK(3,3) stage per half-step h = dt/2
(D152's scheme; Shu and Osher 1988; Gottlieb, Shu and Tadmor 2001):

    u1 = u + h f(u),   u2 = 3/4 u + 1/4 (u1 + h f(u1)),   u' = 1/3 u + 2/3 (u2 + h f(u2)).

``run`` applies it to R-ode's network (amounts, pools and internalised amounts), with the
multipliers of the step's start, and records at the registered times. Its distance from R-ode at
each dt states what an honest third-order engine shows, beside the planted controls.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np

from . import kinetics
from .exact import exact


def run(net, times, dt: float, scheme: str = "ssprk33") -> dict:
    """``scheme``: ``ssprk33`` (the honest stand-in), or the planted lower orders ``ssprk22``
    (Heun, second order) and ``euler`` (first order)."""
    nodes = sorted(net.volumes)
    t = np.asarray(times, dtype=np.float64)
    n_steps = np.rint(t / dt).astype(int)
    if np.any(np.abs(n_steps * dt - t) > 1e-9 * dt):
        raise ValueError("record times must lie on the dt grid")
    N, K = len(nodes), len(net.populations)
    y = np.concatenate([[float(net.n0[n]) for n in nodes], [p.B0 for p in net.populations],
                        np.zeros(K), [0.0, 0.0]])
    starts = [exact(e[0]) for e in net.epochs]
    rhs_e = []
    for e in range(len(net.epochs)):
        rhs, *_ = kinetics._rhs_factory(net, nodes, kinetics._multipliers(net, e))
        rhs_e.append(rhs)
    h = dt / 2
    out = np.empty((t.size, y.size))
    k = 0
    dtx = exact(dt)
    for i, target in enumerate(n_steps):
        while k < target:
            tk = Fraction(k) * dtx
            e = max(j for j, s in enumerate(starts) if s <= tk)
            f = rhs_e[e]
            for _ in range(2):
                if scheme == "ssprk33":
                    u1 = y + h * np.asarray(f(0.0, y))
                    u2 = 0.75 * y + 0.25 * (u1 + h * np.asarray(f(0.0, u1)))
                    y = y / 3.0 + 2.0 / 3.0 * (u2 + h * np.asarray(f(0.0, u2)))
                elif scheme == "ssprk22":
                    u1 = y + h * np.asarray(f(0.0, y))
                    y = 0.5 * y + 0.5 * (u1 + h * np.asarray(f(0.0, u1)))
                elif scheme == "euler":
                    y = y + h * np.asarray(f(0.0, y))
                else:
                    raise ValueError(scheme)
            k += 1
        out[i] = y
    return {"nodes": nodes, "n_fmol": out[:, :N], "B_fmol": out[:, N:N + K],
            "internalised_fmol": out[:, N + K:N + 2 * K]}
