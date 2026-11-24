"""R-eq: the finite-volume equilibrium (SPEC §3.1), by three independent routes.

Unknowns: each pool's free concentration c_p and each set's free sites R_s. With the
detailed balance B_b = R_s(b) * c_p(b) / K_b (SPEC §1.2), the equations are

  pool p:  V_p * c_p + c_p * sum_{b from p} R_s(b) / K_b - N_p = 0
  set s:   R_s * (1 + sum_{b on s} c_p(b) / K_b) - S_s = 0

1. ``bracket``: the map T(R)_s = S_s / (1 + sum_b c_p(b)(R)/K_b), with
   c_p(R) = N_p / (V_p + sum_b R_s(b)/K_b), is isotone on the box [0, S]. Iterated from
   R = 0 and from R = S, it gives a rising and a falling sequence that enclose every fixed
   point. The fixed point is unique because G is strictly convex on the conservation
   manifold, so both sequences converge to it, and their gap is a certificate.
2. ``newton``: damped Newton on the full system, with an analytic Jacobian.
3. ``wang``: for a subsystem of one set and two ligand pools, the trigonometric root of
   the cubic in the free-site variable (Wang 1995), derived and checked here:
   with K'_l = K_l * V (fmol),
     R^3 + a R^2 + b R + c = 0,
     a = K'_1 + K'_2 + N_1 + N_2 - S,
     b = K'_2 (N_1 - S) + K'_1 (N_2 - S) + K'_1 K'_2,
     c = -K'_1 K'_2 S.
   The cubic f has f(0) < 0 < f(S), and f(-K'_1), f(-K'_2) have opposite signs, so it
   has three real roots and exactly one of them lies in (0, S). The root is chosen by
   that check, not by assuming a branch. With K'_1 = K'_2 one root is -K' exactly, and
   the root in (0, S) is still the only one there.
4. ``pooled``: where every population on a lone set shares one K'_b (W7, whose two K are
   both 12 mM, and W7s, with one population), the quadratic of one pooled ligand.
"""

from __future__ import annotations

from decimal import Decimal

from fr45ref_hp import ONE, ZERO, acos, cos, pi, sqrt


def _c_of_R(sys, N, R):
    c = []
    for p in range(sys.nP):
        den = sys.Vd[p] + sum(
            (R[sys.pops[b]["set_index"]] / sys.K[b] for b in sys.pops_of_pool[p]), ZERO
        )
        c.append(N[p] / den)
    return c


def _T(sys, N, R):
    c = _c_of_R(sys, N, R)
    out = []
    for s in range(sys.nS):
        den = ONE + sum((c[sys.pops[b]["pool_index"]] / sys.K[b] for b in sys.pops_of_set[s]), ZERO)
        out.append(sys.Sd[s] / den)
    return out


def state_from(sys, c, R):
    """(n_p, R_s, B_b) from concentrations and free sites, by detailed balance."""
    n = [sys.Vd[p] * c[p] for p in range(sys.nP)]
    B = [R[q["set_index"]] * c[q["pool_index"]] / sys.K[b] for b, q in enumerate(sys.pops)]
    return n + list(R) + B


def _rel_tol(spare_digits: int) -> Decimal:
    """A stopping tolerance a few digits above the working precision's rounding."""
    import decimal

    return Decimal(10) ** (-(decimal.getcontext().prec - spare_digits))


def bracket(sys, N, rel=None, max_iter=200000):
    rel = _rel_tol(4) if rel is None else rel
    lo = [ZERO] * sys.nS
    hi = list(sys.Sd)
    it = 0
    while True:
        it += 1
        lo_n = _T(sys, N, lo)
        hi_n = _T(sys, N, hi)
        width = max(((hi_n[s] - lo_n[s]) / sys.Sd[s] for s in range(sys.nS)), default=ZERO)
        stalled = lo_n == lo and hi_n == hi
        lo, hi = lo_n, hi_n
        if width <= rel or stalled:
            break
        if it >= max_iter:
            raise RuntimeError("the enclosure did not close")
    for s in range(sys.nS):
        if lo[s] > hi[s] * (1 + _rel_tol(5)):
            raise RuntimeError("the enclosure inverted beyond rounding")
    R = [(lo[s] + hi[s]) / 2 for s in range(sys.nS)]
    c = _c_of_R(sys, N, R)
    return {
        "state": state_from(sys, c, R),
        "c": c,
        "R": R,
        "iterations": it,
        "width": [hi[s] - lo[s] for s in range(sys.nS)],
    }


def _residual_vector(sys, N, c, R):
    F = []
    for p in range(sys.nP):
        F.append(
            sys.Vd[p] * c[p]
            + c[p]
            * sum((R[sys.pops[b]["set_index"]] / sys.K[b] for b in sys.pops_of_pool[p]), ZERO)
            - N[p]
        )
    for s in range(sys.nS):
        F.append(
            R[s]
            * (
                ONE
                + sum((c[sys.pops[b]["pool_index"]] / sys.K[b] for b in sys.pops_of_set[s]), ZERO)
            )
            - sys.Sd[s]
        )
    return F


def _solve(A, b):
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if M[piv][col] == 0:
            raise ZeroDivisionError("singular Jacobian")
        M[col], M[piv] = M[piv], M[col]
        for r in range(col + 1, n):
            f = M[r][col] / M[col][col]
            if f != 0:
                for k in range(col, n + 1):
                    M[r][k] -= f * M[col][k]
    x = [ZERO] * n
    for r in range(n - 1, -1, -1):
        s = M[r][n] - sum((M[r][k] * x[k] for k in range(r + 1, n)), ZERO)
        x[r] = s / M[r][r]
    return x


def newton(sys, N, tol=None, max_iter=400):
    tol = _rel_tol(3) if tol is None else tol
    P, S = sys.nP, sys.nS
    c = [N[p] / sys.Vd[p] for p in range(P)]
    R = list(sys.Sd)
    scale = max([abs(v) for v in N] + list(sys.Sd))
    for it in range(1, max_iter + 1):
        F = _residual_vector(sys, N, c, R)
        J = [[ZERO] * (P + S) for _ in range(P + S)]
        for p in range(P):
            J[p][p] = sys.Vd[p] + sum(
                (R[sys.pops[b]["set_index"]] / sys.K[b] for b in sys.pops_of_pool[p]), ZERO
            )
            for b in sys.pops_of_pool[p]:
                J[p][P + sys.pops[b]["set_index"]] += c[p] / sys.K[b]
        for s in range(S):
            J[P + s][P + s] = ONE + sum(
                (c[sys.pops[b]["pool_index"]] / sys.K[b] for b in sys.pops_of_set[s]), ZERO
            )
            for b in sys.pops_of_set[s]:
                J[P + s][sys.pops[b]["pool_index"]] += R[s] / sys.K[b]
        dx = _solve(J, [-v for v in F])
        norm0 = max(abs(v) for v in F)
        lam = ONE
        while True:
            c_try = [c[p] + lam * dx[p] for p in range(P)]
            R_try = [R[s] + lam * dx[P + s] for s in range(S)]
            if all(v > 0 for v in c_try) and all(v > 0 for v in R_try):
                F_try = _residual_vector(sys, N, c_try, R_try)
                if max(abs(v) for v in F_try) <= norm0 or lam < Decimal("1e-30"):
                    break
            lam /= 2
            if lam < Decimal("1e-40"):
                raise RuntimeError("Newton's line search failed")
        c, R = c_try, R_try
        step = max(
            [abs(lam * dx[p]) / max(c[p], Decimal("1e-300")) for p in range(P)]
            + [abs(lam * dx[P + s]) / sys.Sd[s] for s in range(S)]
        )
        if step <= tol and max(abs(v) for v in F_try) <= tol * scale:
            return {"state": state_from(sys, c, R), "c": c, "R": R, "iterations": it}
    raise RuntimeError("Newton did not converge")


def residuals(sys, N, y) -> dict:
    """Largest absolute residual (fmol) of each family of R-eq's equations at state y."""
    tot = sys.pool_totals(y)
    sums = sys.set_sums(y)
    db = []
    for b, q in enumerate(sys.pops):
        p = q["pool_index"]
        db.append(
            abs(y[sys.i_pop(b)] - y[sys.i_set(q["set_index"])] * (y[p] / sys.Vd[p]) / sys.K[b])
        )
    return {
        "ligand_totals": max(abs(tot[p] - N[p]) for p in range(sys.nP)),
        "moieties": max(abs(sums[s] - sys.Sd[s]) for s in range(sys.nS)),
        "detailed_balance": max(db) if db else ZERO,
    }


def components(sys) -> list[dict]:
    """Connected subsystems of pools and sets (linked by populations)."""
    parent = list(range(sys.nP + sys.nS))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for q in sys.pops:
        a, b = find(q["pool_index"]), find(sys.nP + q["set_index"])
        if a != b:
            parent[max(a, b)] = min(a, b)
    groups: dict[int, dict] = {}
    for i in range(sys.nP + sys.nS):
        g = groups.setdefault(find(i), {"pools": [], "sets": []})
        if i < sys.nP:
            g["pools"].append(i)
        else:
            g["sets"].append(i - sys.nP)
    return [groups[k] for k in sorted(groups)]


def wang(sys, N, s: int) -> dict:
    """Wang's trigonometric root for set s, when s and its two pools form a subsystem."""
    bs = sys.pops_of_set[s]
    if len(bs) != 2:
        raise ValueError("Wang's form needs two populations on the set")
    p1, p2 = sys.pops[bs[0]]["pool_index"], sys.pops[bs[1]]["pool_index"]
    if p1 == p2 or len(sys.pops_of_pool[p1]) != 1 or len(sys.pops_of_pool[p2]) != 1:
        raise ValueError("Wang's form needs two pools that bind only this set")
    K1 = sys.K[bs[0]] * sys.Vd[p1]
    K2 = sys.K[bs[1]] * sys.Vd[p2]
    N1, N2, S = N[p1], N[p2], sys.Sd[s]
    a = K1 + K2 + N1 + N2 - S
    b = K2 * (N1 - S) + K1 * (N2 - S) + K1 * K2
    c = -K1 * K2 * S
    q = a * a - 3 * b
    if q <= 0:
        raise ValueError("a^2 - 3b must be positive for three real roots")
    arg = (-2 * a * a * a + 9 * a * b - 27 * c) / (2 * q * sqrt(q))
    if arg > 1 or arg < -1:
        raise ValueError("the arccos argument is outside [-1, 1]")
    theta = acos(arg)
    roots = []
    for k in range(3):
        roots.append(-a / 3 + (2 * sqrt(q) / 3) * cos((theta + 2 * k * pi()) / 3))
    inside = [k for k in range(3) if 0 < roots[k] < S]
    if len(inside) != 1:
        raise ValueError(f"expected one root in (0, S), found {len(inside)}")
    k = inside[0]
    R = roots[k]
    resid = ((R + a) * R + b) * R + c
    terms = abs(R * R * R) + abs(a * R * R) + abs(b * R) + abs(c)
    return {
        "R": R,
        "branch": k,
        "arg": arg,
        "cubic_residual": resid,
        "cubic_terms": terms,
        "pools": (p1, p2),
        "is_largest": all(roots[k] >= roots[j] for j in range(3)),
    }


def pooled(sys, N) -> dict:
    """A closed form for a set whose populations all share one K'_b = K_b * V (fmol).

    Where a subsystem is one set s, each of its pools binds one population on s, and every
    K'_b is the same K', the set sees one pooled ligand of amount sum_b N_b, and R solves

      R + (sum_b N_b) R / (K' + R) = S,  so  R^2 + b R - S K' = 0,  b = K' + sum_b N_b - S,
      R = 2 S K' / (b + sqrt(b^2 + 4 S K')),

    with B_b = N_b R / (K' + R) and n_b = N_b K' / (K' + R). With one population it is SPEC
    §3.1's one-population form B = N R / (K V + R) (W7s); W7's two K are both 12 mM. It is
    a third route, independent of the enclosure and of Newton. Returns {set index: {"R": R,
    "amounts": {state index: value}}} for every set where it applies.
    """
    out = {}
    for comp in components(sys):
        if len(comp["sets"]) != 1:
            continue
        s = comp["sets"][0]
        bs = sys.pops_of_set[s]
        if not bs or any(len(sys.pops_of_pool[sys.pops[b]["pool_index"]]) != 1 for b in bs):
            continue
        kprime = {sys.K[b] * sys.Vd[sys.pops[b]["pool_index"]] for b in bs}
        if len(kprime) != 1:
            continue
        Kp = kprime.pop()
        S = sys.Sd[s]
        Ntot = sum((N[sys.pops[b]["pool_index"]] for b in bs), ZERO)
        b_coef = Kp + Ntot - S
        R = 2 * S * Kp / (b_coef + sqrt(b_coef * b_coef + 4 * S * Kp))
        amounts = {sys.i_set(s): R}
        for b in bs:
            p = sys.pops[b]["pool_index"]
            amounts[sys.i_pop(b)] = N[p] * R / (Kp + R)
            amounts[p] = N[p] * Kp / (Kp + R)
        out[s] = {"R": R, "amounts": amounts}
    return out


def wang_binary64(sys, N, s: int) -> float:
    """The same closed form evaluated in binary64 (for the accuracy record only)."""
    import math

    bs = sys.pops_of_set[s]
    p1, p2 = sys.pops[bs[0]]["pool_index"], sys.pops[bs[1]]["pool_index"]
    K1 = float(sys.K[bs[0]]) * sys.pools[p1]["V"]
    K2 = float(sys.K[bs[1]]) * sys.pools[p2]["V"]
    N1, N2, S = float(N[p1]), float(N[p2]), sys.sets[s]["S"]
    a = K1 + K2 + N1 + N2 - S
    b = K2 * (N1 - S) + K1 * (N2 - S) + K1 * K2
    c = -K1 * K2 * S
    q = a * a - 3 * b
    arg = (-2 * a**3 + 9 * a * b - 27 * c) / (2 * q**1.5)
    arg = max(-1.0, min(1.0, arg))
    return -a / 3 + (2 * math.sqrt(q) / 3) * math.cos(math.acos(arg) / 3)


def affinities(sys, y, eta_rel=Decimal("1e-20")) -> list[Decimal]:
    """dG/dxi_b along each population's reaction, by a finite difference of G itself.

    At the root every affinity vanishes (detailed balance), which checks G's formula
    (SPEC §1.3) against the equilibrium independently of the hand-derived derivative.
    """
    out = []
    for b, q in enumerate(sys.pops):
        node = sys.sets[q["set_index"]]["faces"]
        eta = eta_rel * sys.Sd[q["set_index"]]
        yp = list(y)
        yp[sys.i_pop(b)] += eta
        yp[sys.i_set(q["set_index"])] -= eta
        yp[q["pool_index"]] -= eta
        ym = list(y)
        ym[sys.i_pop(b)] -= eta
        ym[sys.i_set(q["set_index"])] += eta
        ym[q["pool_index"]] += eta
        out.append((sys.G(yp, node) - sys.G(ym, node)) / (2 * eta))
    return out
