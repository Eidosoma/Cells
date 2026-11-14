"""Piecewise-smooth ODE integration shared by the coupling references (R-state, R-cell and
R-feedback). numpy and scipy only.

A run integrates segment by segment between breakpoints (schedule changes, records), so every
record is an integration end point and no value is read from dense output. Radau's continuous
extension (its collocation polynomial) is of lower order than its steps, so values between
solver steps come from a fresh integration from the last stored step instead. The first upward
crossing of a level is bracketed by the stored steps and located by Brent's method on such
re-integrations (Brent 1973).

The integrators are scipy's solve_ivp methods: Radau IIA of order 5 (Hairer E, Wanner G. Solving
Ordinary Differential Equations II, 2nd ed., Springer 1996), DOP853 (Hairer E, Norsett SP,
Wanner G. Solving Ordinary Differential Equations I, 2nd ed., Springer 1993) and LSODA.
"""

import math
from bisect import bisect_left

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq


class Run:
    """One integration from points[0] to points[-1].

    ``segment(t0, t1)`` returns ``(fun, jac)`` for the open interval (t0, t1), the right-hand
    side being smooth there; ``jac`` may be None (finite differences). Every point of
    ``points`` is a segment end, so the state at each is an integration end point."""

    def __init__(self, segment, y0, points, *, rtol, atol, method="Radau", max_step=math.inf):
        points = sorted(set(float(p) for p in points))
        if len(points) < 2:
            raise ValueError("a run needs two distinct points")
        self.rtol, self.atol, self.method, self.max_step = rtol, atol, method, max_step
        self.segments = []  # (t0, t1, fun, jac, ts, ys)
        self.steps = 0
        y = np.asarray(y0, dtype=float)
        for t0, t1 in zip(points, points[1:], strict=False):
            fun, jac = segment(t0, t1)
            sol = self._solve(fun, jac, t0, t1, y)
            self.steps += sol.t.size - 1
            y = sol.y[:, -1].copy()
            self.segments.append((t0, t1, fun, jac, sol.t.copy(), sol.y.T.copy()))
        self.t0, self.t_end = points[0], points[-1]
        self._ends = [s[1] for s in self.segments]

    def _solve(self, fun, jac, t0, t1, y):
        options = dict(method=self.method, rtol=self.rtol, atol=self.atol)
        if self.method in ("Radau", "BDF", "LSODA") and jac is not None:
            options["jac"] = jac
        if math.isfinite(self.max_step):
            options["max_step"] = self.max_step
        sol = solve_ivp(fun, (t0, t1), y, **options)
        if not sol.success:
            raise RuntimeError(f"integration failed on [{t0}, {t1}]: {sol.message}")
        return sol

    def _segment_of(self, t):
        if not self.t0 <= t <= self.t_end:
            raise ValueError(f"t = {t} lies outside [{self.t0}, {self.t_end}]")
        return min(bisect_left(self._ends, t), len(self.segments) - 1)

    def state(self, t):
        """The state at t: a stored step if t is one, else a fresh integration from the last
        stored step before t (same method and tolerances)."""
        t = float(t)
        t0, t1, fun, jac, ts, ys = self.segments[self._segment_of(t)]
        j = int(np.searchsorted(ts, t, side="right")) - 1
        if ts[j] == t:
            return ys[j].copy()
        return self._solve(fun, jac, ts[j], t, ys[j]).y[:, -1].copy()

    def end_state(self):
        return self.segments[-1][5][-1].copy()

    def first_crossing(self, g, level, *, xtol=None):
        """The first t with g(t, y(t)) >= level (0 if it holds at the start, inf if never),
        resolved at the stored steps and refined by Brent's method on re-integrations from the
        step that brackets it. A crossing that comes and goes within one solver step is not
        seen; ``max_step`` bounds the step."""
        first = self.segments[0]
        if g(first[4][0], first[5][0]) >= level:
            return 0.0
        for _, _, fun, jac, ts, ys in self.segments:
            values = np.array([g(t, y) for t, y in zip(ts, ys, strict=True)])
            hit = np.nonzero(values >= level)[0]
            if hit.size == 0:
                continue
            j = int(hit[0])
            ta, ya = ts[j - 1], ys[j - 1]

            def gap(t, ta=ta, ya=ya, fun=fun, jac=jac):
                if t == ta:
                    return g(ta, ya) - level
                return g(t, self._solve(fun, jac, ta, t, ya).y[:, -1]) - level

            lo, hi = gap(ta), gap(ts[j])
            if not (lo < 0.0 <= hi):  # re-integration noise at a bracket end
                return float(ts[j]) if hi >= 0.0 else float(ta)
            tol = xtol if xtol is not None else 4.0 * np.finfo(float).eps * max(1.0, abs(ts[j]))
            return float(brentq(gap, ta, ts[j], xtol=tol, rtol=4.0 * np.finfo(float).eps))
        return math.inf
