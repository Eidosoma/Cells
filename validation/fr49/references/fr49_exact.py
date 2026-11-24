"""FR-49 references: the high-precision routes, in decimal arithmetic (libmpdec).

- **World L** (LAWS.md 2): the matrix exponential of the augmented linear system
  y = (n_O, n_C, x_O, x_C, 1), on each interval between t = 0, t1, t2 and the sample times. It is
  evaluated by its Taylor series with scaling and squaring. The second high-precision route is the
  eigen closed form: e^(A t) by Sylvester's formula, about each interval's steady state.
- **World B** (LAWS.md 3): the equilibrium root and the exact Riccati transient.
- **The binding integrator:** a Taylor-series integration of LAWS.md 3 and 5's binding equations,
  for any number of ligands sharing one site pool. Coefficients come by the recursion of the
  quadratic right-hand side, and each step's series is summed until two terms fall below the
  tolerance. It is the high-precision check of World B's closed form, and C2's transient.
- **C2's equilibrium** (LAWS.md 5): one equation in the free sites R, solved by Newton from
  R = 0. The check solves LAWS.md's two equations in (c1, c2) by Newton.
- **C1** (LAWS.md 4): the wash's arithmetic.
"""

from __future__ import annotations

import decimal
from decimal import Decimal
from fractions import Fraction
from itertools import pairwise

from fr49_spec import Samples, Sites, Spec, WorldB, WorldC1, WorldC2, WorldL

PREC = 60  # World B and C1; World L and C2's roots work at PREC + 10
TAYLOR_PREC = 50  # the binding integrator
_TRAPS = [decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow]


def context(prec: int = PREC) -> decimal.Context:
    return decimal.Context(prec=prec, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999,
                           Emax=999999, traps=_TRAPS)


def sample_times(samples: Samples) -> list[Decimal]:
    step = Decimal(samples.step)
    return [step * i for i in range(samples.last + 1)]


def capacity(sites: Sites, sites_per_fmol: str) -> Decimal:
    """S = alpha nu N / N_f (fmol), LAWS.md 1."""
    with decimal.localcontext(context()):
        return (Decimal(sites.accessible_fraction) * sites.sites_per_copy * Decimal(sites.copies)
                / Decimal(sites_per_fmol))


def capacity_rational(sites: Sites, sites_per_fmol: str) -> Fraction:
    """S in exact rationals, for the second routes."""
    return (Fraction(sites.accessible_fraction) * sites.sites_per_copy * Fraction(sites.copies)
            / Fraction(sites_per_fmol))


def to_decimal(q: Fraction) -> Decimal:
    """A rational at the current context's precision."""
    return Decimal(q.numerator) / Decimal(q.denominator)


# ---- World L -------------------------------------------------------------------------------------

def _matmul(X: list, Y: list) -> list:
    n, m, p = len(X), len(Y), len(Y[0])
    return [[sum((X[i][k] * Y[k][j] for k in range(m)), Decimal(0)) for j in range(p)]
            for i in range(n)]


def expm(M: list) -> list:
    """e^M for a square Decimal matrix: Taylor series of M/2^s, then s squarings."""
    n = len(M)
    norm = max(sum(abs(x) for x in row) for row in M)
    s = 0
    while norm > Decimal("0.03"):
        norm /= 2
        s += 1
    scale = Decimal(2) ** s
    X = [[x / scale for x in row] for row in M]
    E = [[Decimal(int(i == j)) for j in range(n)] for i in range(n)]
    term = [row[:] for row in E]
    tiny = Decimal(10) ** -(decimal.getcontext().prec + 5)
    k = 0
    while True:
        k += 1
        term = [[x / k for x in row] for row in _matmul(term, X)]
        E = [[e + t for e, t in zip(er, tr, strict=True)] for er, tr in zip(E, term, strict=True)]
        if max(abs(x) for row in term for x in row) < tiny:
            break
    for _ in range(s):
        E = _matmul(E, E)
    return E


def _breakpoints(L: WorldL, times: list[Decimal]) -> list[Decimal]:
    t1, t2, horizon = Decimal(L.t1), Decimal(L.t2), Decimal(L.horizon)
    if times[-1] != horizon:
        raise ValueError("world L: the last sample time is not the horizon")
    points = [t for t in [*times, t1, t2] if 0 <= t <= horizon]
    return sorted(dict.fromkeys(points))


def _world_L_arrays(states: list[list[Decimal]]) -> dict:
    """The requested quantities from (n_O, n_C, x_O, x_C), at the caller's working precision."""
    out: dict = {"n_O": [], "n_C": [], "x_O": [], "x_C": [], "base_O": [], "base_C": [],
                 "share_x_O": [], "share_x_C": []}
    for n_O, n_C, x_O, x_C in states:
        out["n_O"].append(n_O)
        out["n_C"].append(n_C)
        out["x_O"].append(x_O)
        out["x_C"].append(x_C)
        out["base_O"].append(n_O - x_O)
        out["base_C"].append(n_C - x_C)
        out["share_x_O"].append(x_O / n_O)
        out["share_x_C"].append(x_C / n_C)
    return out


def world_L_expm(L: WorldL) -> dict:
    """World L at every sample time, by the augmented system's matrix exponentials."""
    times = sample_times(L.samples)
    with decimal.localcontext(context(PREC + 10)):
        V_O, V_C, a, k_d, P = (Decimal(v) for v in (L.V_O, L.V_C, L.a, L.k_d, L.P))
        t1, t2 = Decimal(L.t1), Decimal(L.t2)
        a00, a01, a10, a11 = -a / V_O, a / V_C, a / V_O, -a / V_C - k_d
        zero = Decimal(0)

        def augmented(P_x: Decimal, dt: Decimal) -> list:
            rows = [[a00, a01, zero, zero, P],
                    [a10, a11, zero, zero, zero],
                    [zero, zero, a00, a01, P_x],
                    [zero, zero, a10, a11, zero],
                    [zero, zero, zero, zero, zero]]
            return [[x * dt for x in row] for row in rows]

        y = [Decimal(L.n_O0), Decimal(L.n_C0), Decimal(L.x_O0), Decimal(L.x_C0), Decimal(1)]
        index = {t: i for i, t in enumerate(times)}
        states: list = [None] * len(times)
        states[0] = y[:4]
        cache: dict = {}
        points = _breakpoints(L, times)
        for ta, tb in pairwise(points):
            inside = t1 <= ta < t2
            key = (tb - ta, inside)
            if key not in cache:
                cache[key] = expm(augmented(P if inside else zero, tb - ta))
            y = [row[0] for row in _matmul(cache[key], [[v] for v in y])]
            if tb in index:
                states[index[tb]] = y[:4]
        return _world_L_arrays(states)


def world_L_sylvester(L: WorldL) -> dict:
    """World L by the eigen closed form: y(tb) = y* + e^(A dt) (y(ta) - y*), with y* = -A^-1 s
    the interval's steady state and e^(A dt) by Sylvester's formula."""
    times = sample_times(L.samples)
    with decimal.localcontext(context(PREC + 10)):
        V_O, V_C, a, k_d, P = (Decimal(v) for v in (L.V_O, L.V_C, L.a, L.k_d, L.P))
        t1, t2 = Decimal(L.t1), Decimal(L.t2)
        A = [[-a / V_O, a / V_C], [a / V_O, -a / V_C - k_d]]
        trace = A[0][0] + A[1][1]
        det = A[0][0] * A[1][1] - A[0][1] * A[1][0]
        root = (trace * trace - 4 * det).sqrt()
        lam2 = (trace - root) / 2  # the faster rate, formed without cancellation
        lam1 = det / lam2

        def propagator(dt: Decimal) -> list:
            e1, e2 = (lam1 * dt).exp(), (lam2 * dt).exp()
            return [[(e1 * (A[i][j] - lam2 * (i == j)) - e2 * (A[i][j] - lam1 * (i == j)))
                     / (lam1 - lam2) for j in range(2)] for i in range(2)]

        def steady(source: Decimal) -> list:
            # -A^-1 (source, 0)
            return [-(A[1][1] * source) / det, (A[1][0] * source) / det]

        def advance(y: list, source: Decimal, phi: list) -> list:
            star = steady(source)
            dev = [y[0] - star[0], y[1] - star[1]]
            return [star[i] + phi[i][0] * dev[0] + phi[i][1] * dev[1] for i in range(2)]

        n = [Decimal(L.n_O0), Decimal(L.n_C0)]
        x = [Decimal(L.x_O0), Decimal(L.x_C0)]
        index = {t: i for i, t in enumerate(times)}
        states: list = [None] * len(times)
        states[0] = n + x
        cache: dict = {}
        points = _breakpoints(L, times)
        for ta, tb in pairwise(points):
            dt = tb - ta
            if dt not in cache:
                cache[dt] = propagator(dt)
            n = advance(n, P, cache[dt])
            x = advance(x, P if t1 <= ta < t2 else Decimal(0), cache[dt])
            if tb in index:
                states[index[tb]] = n + x
        return _world_L_arrays(states)


# ---- World B -------------------------------------------------------------------------------------

def world_B_exact(spec: Spec) -> dict:
    """World B's equilibrium and its exact transient (LAWS.md 3)."""
    W: WorldB = spec.B
    times = sample_times(W.samples)
    if times[-1] != Decimal(W.horizon):
        raise ValueError("world B: the last sample time is not the horizon")
    S = capacity(W.sites, spec.sites_per_fmol)
    with decimal.localcontext(context()):
        V_C, k_on, k_off = Decimal(W.V_C), Decimal(W.k_on), Decimal(W.k_off)
        B0 = Decimal(W.B0)
        L_T = Decimal(W.n_L0) + B0
        K_d = k_off / k_on
        b = V_C * K_d + S - L_T
        d = (b * b + 4 * V_C * L_T * K_d).sqrt()
        c_star = 2 * L_T * K_d / (b + d) if b >= 0 else (d - b) / (2 * V_C)
        B_star = L_T - V_C * c_star
        s = L_T + S + V_C * K_d
        B2 = (s + (s * s - 4 * L_T * S).sqrt()) / 2
        B1 = L_T * S / B2  # the product of the roots is L_T S
        lam = k_on * (B2 - B1) / V_C
        r0 = (B0 - B1) / (B0 - B2)
        out: dict = {"B": [], "n_L": [], "c": []}
        for t in times:
            if t == 0:
                B = B0
            else:
                r = r0 * (-lam * t).exp()
                B = B1 - r * (B2 - B1) / (1 - r)
            n_L = L_T - B
            out["B"].append(B)
            out["n_L"].append(n_L)
            out["c"].append(n_L / V_C)
        out["once"] = {"S": S, "K_d": K_d, "b": b, "c*": c_star, "B*": B_star, "B1": B1,
                       "B2": B2, "lambda": lam, "L_T": L_T, "d": d}
        out["branch"] = "b >= 0" if b >= 0 else "b < 0"
        return out


def world_B_once_check(spec: Spec) -> dict:
    """World B's once values by a second route.
    - S, K_d, L_T and b in exact rationals.
    - d from b^2 + 4 V_C L_T K_d at 70 digits.
    - Since s^2 - 4 L_T S = b^2 + 4 V_C L_T K_d with s = L_T + S + V_C K_d, B2 - B1 = d, so
      B1 = (s - d)/2, B2 = (s + d)/2 and lambda = k_on d/V_C.
    - c* = (L_T - B1)/V_C, and B* = B1."""
    W: WorldB = spec.B
    S = capacity_rational(W.sites, spec.sites_per_fmol)
    V_C, k_on, k_off = Fraction(W.V_C), Fraction(W.k_on), Fraction(W.k_off)
    L_T = Fraction(W.n_L0) + Fraction(W.B0)
    K_d = k_off / k_on
    b = V_C * K_d + S - L_T
    s = L_T + S + V_C * K_d
    with decimal.localcontext(context(PREC + 10)):
        d = to_decimal(b * b + 4 * V_C * L_T * K_d).sqrt()
        B1 = (to_decimal(s) - d) / 2
        B2 = (to_decimal(s) + d) / 2
        return {"S": S, "K_d": K_d, "b": b, "c*": (to_decimal(L_T) - B1) / to_decimal(V_C),
                "B*": B1, "B1": B1, "B2": B2, "lambda": to_decimal(k_on) * d / to_decimal(V_C),
                "L_T": L_T, "d": d}


# ---- The binding integrator ----------------------------------------------------------------------

def _taylor_step(B: list, h: Decimal, V_C: Decimal, S: Decimal, k_on: list, k_off: list,
                 L_T: list, tol: Decimal) -> list:
    """One step of the Taylor series of dB_j/dt = k_on_j c_j R - k_off_j B_j,
    c_j = (L_T_j - B_j)/V_C, R = S - sum_j B_j. Y[j][n] is the n-th coefficient in the step's
    scaled time, so B_j(t + h) = sum_n Y[j][n]."""
    J = len(B)
    Y = [[B[j]] for j in range(J)]
    C = [[(L_T[j] - B[j]) / V_C] for j in range(J)]
    R = [S - sum(B, Decimal(0))]
    small = 0
    n = 0
    while True:
        new = []
        for j in range(J):
            Cj = C[j]
            product = sum((Cj[m] * R[n - m] for m in range(n + 1)), Decimal(0))
            new.append(h * (k_on[j] * product - k_off[j] * Y[j][n]) / (n + 1))
        for j in range(J):
            Y[j].append(new[j])
            C[j].append(-new[j] / V_C)
        R.append(-sum(new, Decimal(0)))
        n += 1
        if max(abs(v) for v in new) < tol:
            small += 1
            if small == 2:
                break
        else:
            small = 0
        if n > 600:
            raise RuntimeError("the Taylor series did not converge; reduce the step")
    return [sum(reversed(Y[j]), Decimal(0)) for j in range(J)]


def binding_taylor(V_C: str, S: Decimal, ligands: list[tuple[str, str, str]], B0: list[str],
                   times: list[Decimal], h: str, prec: int = TAYLOR_PREC) -> list[list[Decimal]]:
    """B_j at each of `times` (ascending from 0), for ligands (k_on, k_off, L_T) on one site
    pool. Fixed steps of h, shortened to land on every time exactly."""
    with decimal.localcontext(context(prec)):
        V = Decimal(V_C)
        k_on = [Decimal(g[0]) for g in ligands]
        k_off = [Decimal(g[1]) for g in ligands]
        L_T = [Decimal(g[2]) for g in ligands]
        tol = max(L_T) * Decimal(10) ** -(prec - 4)
        step = Decimal(h)
        S = +S
        B = [Decimal(b) for b in B0]
        t = Decimal(0)
        out = []
        for target in times:
            while t < target:
                dt = min(step, target - t)
                B = _taylor_step(B, dt, V, S, k_on, k_off, L_T, tol)
                t += dt
            out.append(list(B))
        return out


# ---- C2's equilibrium ----------------------------------------------------------------------------

def c2_root(spec: Spec) -> dict:
    """The positive root of LAWS.md 5's equilibrium, through the free sites R:
    B_j = c_j R/K_j and V_C c_j + B_j = L_T_j give c_j = L_T_j/(V_C + R/K_j), so
    f(R) = R + R sum_j L_T_j/(K_j V_C + R) - S = 0. f rises and is concave, so Newton from R = 0
    rises to the root without overshoot."""
    W: WorldC2 = spec.C2
    S = capacity(W.sites, spec.sites_per_fmol)
    with decimal.localcontext(context(PREC + 10)):
        V_C = Decimal(W.V_C)
        K = [Decimal(g.k_off) / Decimal(g.k_on) for g in W.ligands]
        L_T = [Decimal(g.total) for g in W.ligands]
        R = Decimal(0)
        for _ in range(400):
            terms = [(L_T[j], K[j] * V_C + R) for j in range(len(K))]
            f = R + R * sum((lt / den for lt, den in terms), Decimal(0)) - S
            df = 1 + sum((lt * K[j] * V_C / (den * den) for j, (lt, den) in enumerate(terms)),
                         Decimal(0))
            step = f / df
            R -= step
            if abs(step) <= R * Decimal(10) ** -(PREC + 5):
                break
        else:
            raise RuntimeError("C2's root did not converge")
        c = [L_T[j] / (V_C + R / K[j]) for j in range(len(K))]
        B = [L_T[j] - V_C * c[j] for j in range(len(K))]
        return {"c": c, "B": B, "R": R, "K": K, "S": S}


def c2_root_newton2(spec: Spec, guess: list[float]) -> dict:
    """The check: Newton on LAWS.md 5's two equations in (c1, c2) as written,
    F_j = V_C c_j + S (c_j/K_j)/(1 + c1/K1 + c2/K2) - L_T_j, from `guess`."""
    W: WorldC2 = spec.C2
    if len(W.ligands) != 2:
        raise ValueError("the check is written for two ligands")
    with decimal.localcontext(context(PREC + 10)):
        S = to_decimal(capacity_rational(W.sites, spec.sites_per_fmol))
        V_C = Decimal(W.V_C)
        K = [Decimal(g.k_off) / Decimal(g.k_on) for g in W.ligands]
        L_T = [Decimal(g.total) for g in W.ligands]
        c = [Decimal(g) for g in guess]
        for _ in range(200):
            D = 1 + c[0] / K[0] + c[1] / K[1]
            F = [V_C * c[j] + S * (c[j] / K[j]) / D - L_T[j] for j in range(2)]
            # dF_j/dc_i = V_C [i == j] + S [i == j]/(K_j D) - S c_j/(K_j K_i D^2)
            Jm = [[V_C * (i == j) + S * (i == j) / (K[j] * D) - S * c[j] / (K[j] * K[i] * D * D)
                   for i in range(2)] for j in range(2)]
            det = Jm[0][0] * Jm[1][1] - Jm[0][1] * Jm[1][0]
            dc = [(F[0] * Jm[1][1] - F[1] * Jm[0][1]) / det,
                  (Jm[0][0] * F[1] - Jm[1][0] * F[0]) / det]
            c = [c[0] - dc[0], c[1] - dc[1]]
            if max(abs(dc[j]) / c[j] for j in range(2)) <= Decimal(10) ** -(PREC + 5):
                break
        else:
            raise RuntimeError("the two-equation Newton check did not converge")
        D = 1 + c[0] / K[0] + c[1] / K[1]
        B = [S * (c[j] / K[j]) / D for j in range(2)]
        return {"c": c, "B": B, "R": S / D, "S": S, "K": K}


# ---- C1 ------------------------------------------------------------------------------------------

def c1_wash(W: WorldC1) -> dict:
    """The well's labels just before and just after the wash (LAWS.md 4)."""
    with decimal.localcontext(context()):
        f, V_W, c_buf = Decimal(W.wash_fraction), Decimal(W.V_W), Decimal(W.buffer_mM)
        x_before, b_before = Decimal(W.x_W0), Decimal(W.b_W0)
        x_after = (1 - f) * x_before
        b_after = (1 - f) * b_before + f * V_W * c_buf
        return _well(x_before, b_before, x_after, b_after)


def c1_wash_rational(W: WorldC1) -> dict:
    """The same arithmetic in exact rationals (the check)."""
    f, V_W, c_buf = Fraction(W.wash_fraction), Fraction(W.V_W), Fraction(W.buffer_mM)
    x_before, b_before = Fraction(W.x_W0), Fraction(W.b_W0)
    x_after = (1 - f) * x_before
    b_after = (1 - f) * b_before + f * V_W * c_buf
    return _well(x_before, b_before, x_after, b_after)


def _well(x_before, b_before, x_after, b_after) -> dict:
    return {
        "x_W_before": x_before, "b_W_before": b_before, "n_W_before": x_before + b_before,
        "share_x_W_before": x_before / (x_before + b_before),
        "share_b_W_before": b_before / (x_before + b_before),
        "x_W_after": x_after, "b_W_after": b_after, "n_W_after": x_after + b_after,
        "share_x_W_after": x_after / (x_after + b_after),
        "share_b_W_after": b_after / (x_after + b_after),
    }
