"""Stand-ins for an engine that splits two exact first-order flows (not references).

R_linear's worlds compose exchange with turnover's clearance (C6) or with a reaction (C7), or
two exchange routes in series (C8). An engine that runs each as its own exact stage commits a
splitting error. ``split_run`` iterates two exact linear sub-flows of a linear system in Lie
order X(dt) Y(dt) or in Strang order X(dt/2) Y(dt) X(dt/2), in float64, so the design can state
how far an honest split engine lies from the exact solution at the declared dt, beside the
planted controls.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import expm


def split_run(G1, G2, y0, dt: float, times, order: str = "strang") -> np.ndarray:
    """y at the record times under a Lie or Strang split of dy/dt = (G1 + G2) y."""
    G1, G2 = np.asarray(G1, float), np.asarray(G2, float)
    if order == "lie":
        step = expm(G2 * dt) @ expm(G1 * dt)
    elif order == "strang":
        half = expm(G1 * dt / 2)
        step = half @ expm(G2 * dt) @ half
    else:
        raise ValueError(order)
    t = np.asarray(times, dtype=np.float64)
    n = np.rint(t / dt).astype(int)
    if np.any(np.abs(n * dt - t) > 1e-9 * dt):
        raise ValueError("record times must lie on the dt grid")
    out = np.empty((t.size, len(y0)))
    y = np.asarray(y0, float).copy()
    k = 0
    for i, ni in enumerate(n):
        while k < ni:
            y = step @ y
            k += 1
        out[i] = y
    return out
