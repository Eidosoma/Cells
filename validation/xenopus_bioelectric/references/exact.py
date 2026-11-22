"""Arbitrary-precision helpers: ``decimal`` at 60 digits, reported to 50 (no mpmath on the venvs)."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Context, Decimal, localcontext

PREC = 60
REPORT_DIGITS = 50
U64 = Decimal(2) ** -53          # float64 unit roundoff


@contextmanager
def context():
    """Every reference computation runs inside this context (never set globally)."""
    with localcontext(Context(prec=PREC, Emax=999999, Emin=-999999)) as ctx:
        yield ctx


def dec(x) -> Decimal:
    """A float is read as the exact value of its double; a string as its decimal value."""
    return Decimal(x) if not isinstance(x, str) else Decimal(x)


def fmt(x: Decimal) -> str:
    """50 significant digits, fixed layout (deterministic bytes)."""
    return format(+x, f".{REPORT_DIGITS - 1}e")


def logmean(a: Decimal, b: Decimal) -> Decimal:
    if a == b:
        return a
    return (a - b) / (a / b).ln()


def sign(x: Decimal) -> int:
    return 0 if x == 0 else (1 if x > 0 else -1)


def rk4(rhs, y0, t_end, steps, record_every=None):
    """Classical RK4 with ``steps`` equal steps; ``record_every`` (steps) keeps (t, y) pairs."""
    h = t_end / steps
    y = list(y0)
    t = Decimal(0)
    out = [(t, tuple(y))]
    half = h / 2
    for i in range(1, steps + 1):
        k1 = rhs(t, y)
        k2 = rhs(t + half, [a + half * b for a, b in zip(y, k1)])
        k3 = rhs(t + half, [a + half * b for a, b in zip(y, k2)])
        k4 = rhs(t + h, [a + h * b for a, b in zip(y, k3)])
        y = [a + h / 6 * (p + 2 * q + 2 * r + s) for a, p, q, r, s in zip(y, k1, k2, k3, k4)]
        t = h * i
        if record_every and i % record_every == 0:
            out.append((t, tuple(y)))
    return out


def rk4_richardson(rhs, y0, t_end, steps, record_every):
    """Values from N and 2N steps: returns (extrapolated list of (t, y), max error estimate list).

    The extrapolated value is y_2N + (y_2N - y_N)/15; the error estimate is |y_2N - y_N|/15, a
    bound on the remaining error of the extrapolation.
    """
    a = rk4(rhs, y0, t_end, steps, record_every)
    b = rk4(rhs, y0, t_end, 2 * steps, 2 * record_every)
    pts, errs = [], []
    for (ta, ya), (tb, yb) in zip(a, b):
        assert abs(ta - tb) < Decimal('1e-45') * (1 + abs(tb))
        pts.append((tb, tuple(v + (v - u) / 15 for u, v in zip(ya, yb))))
        errs.append(tuple(abs(v - u) / 15 for u, v in zip(ya, yb)))
    return pts, errs


def find_roots(fn, dfn, lo, hi, n_scan):
    """All roots of ``fn`` in [lo, hi]: sign scan, bisection to 1e-6 width, then Newton (checked)."""
    xs = [lo + (hi - lo) * i / n_scan for i in range(n_scan + 1)]
    fs = [fn(x) for x in xs]
    roots = []
    for i in range(n_scan):
        if fs[i] == 0:
            roots.append(xs[i])
            continue
        if fs[i] * fs[i + 1] < 0:
            a, b, fa = xs[i], xs[i + 1], fs[i]
            for _ in range(60):
                m = (a + b) / 2
                fm = fn(m)
                if fm == 0:
                    a = b = m
                    break
                if fa * fm < 0:
                    b = m
                else:
                    a, fa = m, fm
            x = (a + b) / 2
            for _ in range(40):
                dx = fn(x) / dfn(x)
                x -= dx
                if abs(dx) < Decimal("1e-50"):
                    break
            assert a - Decimal("1e-12") <= x <= b + Decimal("1e-12"), "Newton left its bracket"
            roots.append(x)
    return roots
