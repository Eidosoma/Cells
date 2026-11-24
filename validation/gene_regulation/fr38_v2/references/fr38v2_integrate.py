"""FR-38's second comparison, the code-blind references: the two integration methods.

Primary: Gragg-Bulirsch-Stoer extrapolation (explicit). Each macro step H runs the modified
midpoint rule with n_j = 2, 4, ..., 2k substeps; Gragg's even-n expansion is in powers of h^2;
the k results are extrapolated to h = 0 (Aitken-Neville, as one linear combination with exact
rational weights). Order 2k. Fixed macro steps that divide every span between restarts.

Second: Gauss-Legendre collocation with s stages (implicit Runge-Kutta, order 2s), its stage
equations solved by fixed-point iteration to round-off. Coefficients are derived here in 50-digit
decimal arithmetic from the Legendre polynomial, not transcribed.

Both run in numpy long double on the deviation-form state, restart at every output time and at
every switch (SPEC.md section 3), and never interpolate an output.
"""

import math
from decimal import Decimal, localcontext
from fractions import Fraction

import numpy as np

LD = np.longdouble


def _ld(dec):
    """A Decimal to the nearest long double, through numpy's long-double string parser."""
    return LD(format(dec, ".30e"))


# --------------------------------------------------------------------------------------------
# Coefficients
# --------------------------------------------------------------------------------------------

def gbs_weights(k):
    """Substep counts n_j = 2j and the exact weights extrapolating to h = 0 in h^2."""
    n = [2 * (j + 1) for j in range(k)]
    w = []
    for j in range(k):
        f = Fraction(1)
        for m in range(k):
            if m != j:
                f *= Fraction(n[j] ** 2, n[j] ** 2 - n[m] ** 2)
        w.append(f)
    assert sum(w) == 1
    with localcontext() as ctx:
        ctx.prec = 50
        wl = [_ld(Decimal(x.numerator) / Decimal(x.denominator)) for x in w]
    return n, wl


def _legendre(s):
    """P_s's coefficients, ascending powers of x, exactly (Bonnet's recurrence)."""
    pm, p = [Fraction(1)], [Fraction(0), Fraction(1)]
    if s == 0:
        return pm
    for n in range(1, s):
        xp = [Fraction(0)] + p
        pm_ext = pm + [Fraction(0)] * (len(xp) - len(pm))
        nxt = [((2 * n + 1) * xp[i] - n * pm_ext[i]) / (n + 1) for i in range(len(xp))]
        pm, p = p, nxt
    return p


def _poly_eval(coeffs, x):
    acc = Decimal(0)
    for c in reversed(coeffs):
        acc = acc * x + c
    return acc


def gauss_legendre(s, prec=50):
    """Nodes c, matrix A, weights b and the stage predictor E of s-stage Gauss-Legendre.

    c_i are the roots of P_s(2c - 1); A_ij = integral_0^{c_i} l_j, b_j = integral_0^1 l_j, with
    l_j the Lagrange basis on the nodes; E_ij = l_j(1 + c_i) extrapolates one step's stage
    derivatives to the next step's nodes (a starting guess only).
    """
    with localcontext() as ctx:
        ctx.prec = prec
        P = [Decimal(c.numerator) / Decimal(c.denominator) for c in _legendre(s)]
        dP = [P[i] * i for i in range(1, len(P))]
        x0s, _ = np.polynomial.legendre.leggauss(s)
        roots = []
        for x0 in x0s:
            x = Decimal(float(x0))
            for _ in range(200):
                dx = _poly_eval(P, x) / _poly_eval(dP, x)
                x -= dx
                if abs(dx) < Decimal(10) ** (-(prec - 8)):
                    break
            roots.append(x)
        c = [(1 + x) / 2 for x in sorted(roots)]

        def basis(j):
            poly = [Decimal(1)]
            for m in range(s):
                if m == j:
                    continue
                den = c[j] - c[m]
                new = [Decimal(0)] * (len(poly) + 1)
                for i, a in enumerate(poly):
                    new[i + 1] += a / den
                    new[i] -= a * c[m] / den
                poly = new
            return poly

        def integral(poly, x):
            return sum(a * x ** (i + 1) / (i + 1) for i, a in enumerate(poly))

        bases = [basis(j) for j in range(s)]
        A = [[integral(bases[j], c[i]) for j in range(s)] for i in range(s)]
        b = [integral(bases[j], Decimal(1)) for j in range(s)]
        E = [[_poly_eval(bases[j], 1 + c[i]) for j in range(s)] for i in range(s)]
        # order conditions B(2s) and C(s), checked in the 50-digit arithmetic
        tol = Decimal(10) ** (-(prec - 15))
        for q in range(1, 2 * s + 1):
            assert abs(sum(b[j] * c[j] ** (q - 1) for j in range(s)) - Decimal(1) / q) < tol
        for i in range(s):
            for q in range(1, s + 1):
                lhs = sum(A[i][j] * c[j] ** (q - 1) for j in range(s))
                assert abs(lhs - c[i] ** q / q) < tol
        cl = np.array([_ld(x) for x in c], dtype=LD)
        Al = np.array([[_ld(x) for x in row] for row in A], dtype=LD)
        bl = np.array([_ld(x) for x in b], dtype=LD)
        El = np.array([[_ld(x) for x in row] for row in E], dtype=LD)
    return cl, Al, bl, El


# --------------------------------------------------------------------------------------------
# One span between restarts
# --------------------------------------------------------------------------------------------

def _nsteps(span, hmax):
    n = int(math.ceil(span / hmax))
    while n > 1 and span / (n - 1) <= hmax:
        n -= 1
    return max(n, 1)


class GBS:
    kind = "gbs"

    def __init__(self, k=8):
        self.k = k
        self.n, self.w = gbs_weights(k)
        self.rhs_calls = 0

    def describe(self):
        return (f"Gragg-Bulirsch-Stoer extrapolation, explicit: modified midpoint rule with "
                f"n = {self.n} substeps per macro step, extrapolated to h = 0 in h^2 "
                f"(Aitken-Neville, exact rational weights), order {2 * self.k}")

    def span(self, world, sv, d, ta, tb, hmax):
        k, R = self.k, world.R
        nst = _nsteps(tb - ta, hmax)
        H = (LD(tb) - LD(ta)) / LD(nst)
        b1 = world.batch(1, sv)
        bk = world.batch(k, sv)
        ncol = np.repeat(np.array(self.n, dtype=np.int64), R)
        hcol = np.repeat(np.array([H / LD(nj) for nj in self.n], dtype=LD), R)
        two_h = 2 * hcol
        NS = world.NS
        for _ in range(nst):
            # the midpoint sums run on the macro step's increment z (from 0), so their
            # round-off is relative to the increment, not to the accumulated deviation d
            f0 = world.rhs(d, b1)
            D = np.tile(d, (1, k))
            Zp = np.zeros_like(D)
            Zc = hcol * np.tile(f0, (1, k))
            self.rhs_calls += 1
            for m in range(1, self.n[-1]):
                Fm = world.rhs(D + Zc, bk)
                self.rhs_calls += 1
                Zn = Zp + two_h * Fm
                act = ncol > m
                Zp = np.where(act, Zc, Zp)
                Zc = np.where(act, Zn, Zc)
            inc = Zc.reshape(NS, k, R)
            acc = self.w[0] * inc[:, 0, :]
            for j in range(1, k):
                acc = acc + self.w[j] * inc[:, j, :]
            d = d + acc
        return d


class Gauss:
    kind = "gauss"

    def __init__(self, s=5, max_iter=80):
        self.s = s
        self.c, self.A, self.b, self.E = gauss_legendre(s)
        self.max_iter = max_iter
        self.rhs_calls = 0
        self.max_iterations_used = 0

    def describe(self):
        return (f"Gauss-Legendre collocation, implicit Runge-Kutta, {self.s} stages, order "
                f"{2 * self.s}; stage equations solved by fixed-point iteration until the stage "
                f"states stop changing at round-off; coefficients derived in 50-digit decimal")

    # Convergence of the stage iteration: every stage state's change is at most 2^-62 of
    # (|its value at t = 0| + |its value| + FLOOR), FLOOR = 1e-16 in the state's own unit (fmol,
    # pJ, pL): the precision the deviation-form state can hold, so a tiny amount is converged
    # to 2e-35 absolute; or the change has stalled at round-off (no halving in 3 iterations once
    # below 1e-15).
    FLOOR = LD("1e-16")

    def span(self, world, sv, d, ta, tb, hmax, K=None):
        """Advance d across [ta, tb]; K, if given, is the last step's stage derivatives (no
        switch between them), used only as the fixed-point iteration's starting guess."""
        s, R = self.s, world.R
        nst = _nsteps(tb - ta, hmax)
        h = (LD(tb) - LD(ta)) / LD(nst)
        b1 = world.batch(1, sv)
        bs = world.batch(s, sv)
        hA = h * self.A
        hb = h * self.b
        y0abs = world.y0[None, :, :]
        y0abs_n = np.abs(y0abs)
        NS = world.NS
        for _ in range(nst):
            if K is None:
                f0 = world.rhs(d, b1)
                self.rhs_calls += 1
                K = np.stack([f0] * s)                  # (s, NS, R)
            else:
                K = np.einsum("ij,jnr->inr", self.E, K)
            Y = None
            best = None
            stall = 0
            for it in range(self.max_iter):
                Ynew = d[None, :, :] + np.einsum("ij,jnr->inr", hA, K)    # stage states
                if Y is not None:
                    full = np.abs(y0abs + Ynew) + y0abs_n + self.FLOOR
                    err = float(np.max(np.abs(Ynew - Y) / full))
                    if err <= 2.0 ** -62:
                        break
                    if best is None or err < 0.5 * best:
                        best, stall = err, 0
                    else:
                        stall += 1
                        if err < 1e-15 and stall >= 3:
                            break
                Y = Ynew
                # the batch's columns are stage-major: [stage 0's rows, stage 1's rows, ...]
                Kc = world.rhs(Y.transpose(1, 0, 2).reshape(NS, s * R), bs)
                self.rhs_calls += 1
                K = Kc.reshape(NS, s, R).transpose(1, 0, 2)
            else:
                raise RuntimeError("Gauss-Legendre stage iteration did not converge")
            self.max_iterations_used = max(self.max_iterations_used, it)
            d = d + np.einsum("j,jnr->nr", hb, K)
        self.last_K = K
        return d


# --------------------------------------------------------------------------------------------
# A whole run: restart at every output time and every switch
# --------------------------------------------------------------------------------------------

def output_times(world):
    inp = world.inp
    horizon = inp["horizon_s"] if world.arm == "A" else inp["t_end_s"]
    dt = inp["output_interval_s"]
    n = int(round(horizon / dt))
    assert n * dt == horizon
    return [dt * i for i in range(n + 1)]


GRADE_LEVELS = 12


def grading_points(world):
    """A graded mesh in the first output interval: restarts at dt_out * 2^-k, k = 1..12.

    Start-up transients (a row from a tiny initial amount, such as C's store row, whose log
    moves on a sub-second scale at t = 0) are resolved with steps proportional to t there.
    """
    dt = world.inp["output_interval_s"]
    return [dt * 2.0 ** -k for k in range(1, GRADE_LEVELS + 1)]


def integrate(world, method, hmax, grade_min_steps=4):
    """The state deviation at every output time: an array (n_outputs, NS, R) of long doubles.

    Every span between restarts takes ceil(span/hmax) equal steps; a span inside the graded
    first interval takes at least grade_min_steps (so h <= t/(2 grade_min_steps) near t = 0).
    """
    outs = output_times(world)
    switches = set(world.switch_times())
    grade = set(grading_points(world))
    bps = sorted(set(outs) | switches | grade)
    d = np.zeros((world.NS, world.R), dtype=LD)
    states = np.zeros((len(outs), world.NS, world.R), dtype=LD)
    oi = 1
    K = None
    for ta, tb in zip(bps[:-1], bps[1:]):
        sv = world.segment_values(ta)
        h_here = hmax
        if tb <= outs[1]:
            h_here = min(hmax, (tb - ta) / grade_min_steps)
        if method.kind == "gauss":
            # the predictor is only a starting guess; it is dropped at every switch
            d = method.span(world, sv, d, ta, tb, h_here, K=None if ta in switches else K)
            K = method.last_K
        else:
            d = method.span(world, sv, d, ta, tb, h_here)
        if world.water:
            V = world.y0[world.ix["V"]] + d[world.ix["V"]]
            if np.any(V < world.Vmin) or np.any(V > world.Vmax):
                raise RuntimeError("volume outside its declared bounds: refused")
        if oi < len(outs) and tb == outs[oi]:
            states[oi] = d
            oi += 1
    assert oi == len(outs)
    return states
