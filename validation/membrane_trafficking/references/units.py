"""The units' references (T5): piecewise closed forms, and the two-direction ODE solved exactly.

Written from FR-2's design statement 1 §4 and §12 (T5) and MEMBRANE_RETRIEVAL_DESIGN §4.1. No
engine code is read.

- **Retrieval** from a patch of area A by dA: N' = N (A'/A)^e, exact for a constant rate.
- **Recycling** from the pool of area A_b by dA: R' = R (A_b'/A_b)^e_r, and the returned units
  join the plasma population.
- **Both directions at once** (rates r1 out of k, r2 out of b), with M = N + R conserved:

      dN/dt = −r1 e N/A_k + r2 e_r (M − N)/A_b,   A_k = A_k0 − (r1 − r2) t,
      A_b = A_b0 + (r1 − r2) t.

  It is linear, so N(t) = (N0 + ∫_0^t μ q ds)/μ(t), with q = r2 e_r M/A_b and the integrating factor
  μ(t) = (A_k/A_k0)^(−r1 e/(r1 − r2)) (A_b/A_b0)^(r2 e_r/(r1 − r2)), or exp(p t) when r1 = r2.
  The integral is taken by Gauss–Legendre quadrature at 60 digits on subintervals. This is the
  lead's stronger reference (19 November 2026) in place of the builder's 20,000-step RK4.
- **The half-step schemes:** the palindrome S_ret(h/2) S_rec(h) S_ret(h/2) (second order), and the
  planted Lie split S_ret(h) S_rec(h) (first order), composed exactly from the closed forms.
"""

from __future__ import annotations

from decimal import Decimal

from validation.core_seams.references.exact import context, dec


def retrieve(N, A, dA, e):
    """N (A'/A)^e after dA leaves an area A (exact)."""
    with context():
        N, A, dA, e = dec(N), dec(A), dec(dA), dec(e)
        return N * (e * ((A - dA) / A).ln()).exp()


def recycle(R, Ab, dA, er):
    with context():
        R, Ab, dA, er = dec(R), dec(Ab), dec(dA), dec(er)
        return R * (er * ((Ab - dA) / Ab).ln()).exp()


# --------------------------------------------------------------------------------------------
# Gauss–Legendre nodes at 60 digits
# --------------------------------------------------------------------------------------------

_GL = {}


def gauss_legendre(n: int) -> list:
    """(x_i, w_i) on [−1, 1] by Newton on P_n at the working precision."""
    if n in _GL:
        return _GL[n]
    import math
    out = []
    with context():
        for i in range(1, n + 1):
            x = dec(math.cos(math.pi * (i - 0.25) / (n + 0.5)))
            for _ in range(100):
                p0, p1 = Decimal(1), x
                for k in range(2, n + 1):
                    p0, p1 = p1, ((2 * k - 1) * x * p1 - (k - 1) * p0) / k
                dp = n * (x * p1 - p0) / (x * x - 1)
                dx = p1 / dp
                x -= dx
                if abs(dx) < Decimal("1e-58"):
                    break
            p0, p1 = Decimal(1), x
            for k in range(2, n + 1):
                p0, p1 = p1, ((2 * k - 1) * x * p1 - (k - 1) * p0) / k
            dp = n * (x * p1 - p0) / (x * x - 1)
            out.append((x, 2 / ((1 - x * x) * dp * dp)))
    _GL[n] = out
    return out


def integrate(f, a, b, pieces: int = 8, n: int = 40):
    """∫_a^b f by n-point Gauss–Legendre on ``pieces`` equal subintervals (60 digits)."""
    with context():
        a, b = dec(a), dec(b)
        total = Decimal(0)
        L = (b - a) / pieces
        for k in range(pieces):
            lo = a + k * L
            mid, half = lo + L / 2, L / 2
            for x, wgt in gauss_legendre(n):
                total += wgt * half * f(mid + half * x)
        return total


def two_direction_exact(N0, R0, Ak0, Ab0, r1, r2, e, er, t, pieces: int = 8,
                        n: int = 40) -> dict:
    """N(t) and R(t) for both directions at once (see the module's docstring), with the integral by
    ``n``-point Gauss–Legendre on ``pieces`` subintervals (``quadrature_agreement`` checks it)."""
    with context():
        N0, R0, Ak0, Ab0 = dec(N0), dec(R0), dec(Ak0), dec(Ab0)
        r1, r2, e, er, t = dec(r1), dec(r2), dec(e), dec(er), dec(t)
        M = N0 + R0
        d = r1 - r2

        def Ak(s):
            return Ak0 - d * s

        def Ab(s):
            return Ab0 + d * s

        if d != 0:
            a_exp = -r1 * e / d
            b_exp = r2 * er / d

            def mu(s):
                return ((a_exp * (Ak(s) / Ak0).ln()) + (b_exp * (Ab(s) / Ab0).ln())).exp()
        else:
            p = r1 * e / Ak0 + r2 * er / Ab0

            def mu(s):
                return (p * s).exp()

        integral = integrate(lambda s: mu(s) * r2 * er * M / Ab(s), Decimal(0), t, pieces, n)
        N = (N0 + integral) / mu(t)
        return {"N": N, "R": M - N, "A_k": Ak(t), "A_b": Ab(t)}


def two_direction_scheme(N0, R0, Ak0, Ab0, r1, r2, e, er, h, steps, scheme="palindrome") -> dict:
    """The half-step schemes composed exactly from the closed forms, over ``steps`` half-steps."""
    with context():
        N, R, Ak, Ab = dec(N0), dec(R0), dec(Ak0), dec(Ab0)
        r1, r2, h = dec(r1), dec(r2), dec(h)
        if scheme == "palindrome":
            plan = [("ret", h / 2), ("rec", h), ("ret", h / 2)]
        elif scheme == "lie":
            plan = [("ret", h), ("rec", h)]
        else:
            raise ValueError(scheme)
        for _ in range(steps):
            for kind, tau in plan:
                if kind == "ret" and r1 > 0:
                    dA = r1 * tau
                    Nn = retrieve(N, Ak, dA, e)
                    R += N - Nn
                    N = Nn
                    Ak -= dA
                    Ab += dA
                elif kind == "rec" and r2 > 0:
                    dA = r2 * tau
                    Rn = recycle(R, Ab, dA, er)
                    N += R - Rn
                    R = Rn
                    Ab -= dA
                    Ak += dA
        return {"N": N, "R": R, "A_k": Ak, "A_b": Ab}


def quadrature_agreement(N0, R0, Ak0, Ab0, r1, r2, e, er, t) -> Decimal:
    """|N(8 × 40 points) − N(16 × 40 points)| / N: the exact solution's quadrature check."""
    with context():
        a = two_direction_exact(N0, R0, Ak0, Ab0, r1, r2, e, er, t, 8, 40)["N"]
        b = two_direction_exact(N0, R0, Ak0, Ab0, r1, r2, e, er, t, 16, 40)["N"]
        return abs(a - b) / abs(b)


def richardson(N0, R0, Ak0, Ab0, r1, r2, e, er, t, n: int = 512) -> dict:
    """The palindrome at n and 2n half-steps and their Richardson value (4 N_2n − N_n)/3: a second,
    independent route to N(t), good to the h⁴ term."""
    with context():
        a = two_direction_scheme(N0, R0, Ak0, Ab0, r1, r2, e, er, dec(t) / n, n)["N"]
        b = two_direction_scheme(N0, R0, Ak0, Ab0, r1, r2, e, er, dec(t) / (2 * n), 2 * n)["N"]
        return {"N_n": a, "N_2n": b, "richardson": (4 * b - a) / 3, "n": n}


def cycle_closed_forms(N0: dict, e: dict, er: dict, Ak0, Ab0, schedule: list, times: list) -> dict:
    """Units, records and areas at each time under a piecewise-constant schedule in which only one
    direction runs at a time (the compiled cycle world): the closed forms are then exact whatever
    the splitting. ``schedule`` is [(t_start, r_retrieval, r_recycling)], knots on the dt grid."""
    with context():
        out = []
        knots = [dec(k[0]) for k in schedule] + [Decimal("Infinity")]
        for t in times:
            t = dec(t)
            N = {p: dec(x) for p, x in N0.items()}
            R = {p: Decimal(0) for p in N0}
            Ak, Ab = dec(Ak0), dec(Ab0)
            for i, (_t0, r1, r2) in enumerate(schedule):
                lo, hi = knots[i], min(knots[i + 1], t)
                if hi <= lo:
                    break
                r1, r2 = dec(r1), dec(r2)
                if r1 > 0 and r2 > 0:
                    raise ValueError("both directions at once: no closed form")
                if r1 > 0:
                    dA = r1 * (hi - lo)
                    for p in N:
                        Nn = retrieve(N[p], Ak, dA, e[p])
                        R[p] += N[p] - Nn
                        N[p] = Nn
                    Ak, Ab = Ak - dA, Ab + dA
                elif r2 > 0:
                    dA = r2 * (hi - lo)
                    for p in N:
                        Rn = recycle(R[p], Ab, dA, er[p])
                        N[p] += R[p] - Rn
                        R[p] = Rn
                    Ak, Ab = Ak + dA, Ab - dA
            out.append({"t": t, "N": N, "R": R, "A_k": Ak, "A_b": Ab})
        return out


def orders(N0, R0, Ak0, Ab0, r1, r2, e, er, t_end, ladder: list, scheme="palindrome") -> dict:
    """Errors of a scheme against the exact solution on a ladder of half-step counts, and the
    ratios between consecutive rungs (4 for second order per halving, 2 for first)."""
    with context():
        ex = two_direction_exact(N0, R0, Ak0, Ab0, r1, r2, e, er, t_end)
        errs, runs = [], []
        for n in ladder:
            h = dec(t_end) / n
            r = two_direction_scheme(N0, R0, Ak0, Ab0, r1, r2, e, er, h, n, scheme)
            runs.append(r)
            errs.append(abs(r["N"] - ex["N"]))
        ratios = [errs[i] / errs[i + 1] for i in range(len(errs) - 1)]
        return {"exact_N": ex["N"], "exact_R": ex["R"], "runs": runs, "errors": errs,
                "ratios": ratios}
