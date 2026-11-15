"""R-closed and R-qss: closed forms of one site population (FR-3), an independent reference.

Written from docs/SITE_OCCUPANCY_DESIGN.md Appendix A.4 and A.5 (each re-derived here) and
D150's saturable sink (docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §2.3's table), without reading
the operator or its tests. Units: fmol, pL, mM, s. One population, multipliers 1.

R-closed (A.4):
* association at a fixed free concentration c: B(t) = B_eq + (B0 - B_eq) e^(-lambda t),
  lambda = k_on c + k_off, B_eq = S c/(K_d + c) (Langmuir's isotherm);
* dissociation into a node held near zero: B(t) = B0 e^(-k_off t);
* depletion in a closed node, no internalisation: with N = n + B constant,
  dB/dt = (k_on/V)(B - r-)(B - r+), r+- the roots of B^2 - (N + S + K_d V) B + N S = 0. With
  Delta = r+ - r-, kappa = k_on Delta / V and Q0 = (B0 - r-)/(B0 - r+), the Riccati solution is
  B(t) = r- - Q Delta/(1 - Q), Q = Q0 e^(-kappa t); its equilibrium r- is the quadratic binding
  equation of ligand depletion (Hulme & Trevethick 2010, context). r- is formed as
  2 N S/(b + sqrt(b^2 - 4 N S)) to avoid cancellation;
* internalisation at a fixed c: Lambda = k_on c + k_off + k_int, B* = k_on c S/Lambda,
  B(t) = B* + (B0 - B*) e^(-Lambda t), and U(t) = k_int [B* t + (B0 - B*)(1 - e^(-Lambda t))/
  Lambda].
The fixed-c forms are limits of a large node; their residual depletion is of relative order
S/(V (K_d + c)) (§8.3), reported by ``depletion_term``.

R-qss (A.5): D150's saturable sink, the quasi-steady limit of binding with site-conserving
internalisation (Segel & Slemrod 1989; Borghans, de Boer & Segel 1996):
dn/dt = -a c/(K_M + c) with a = k_int S (A V_max), K_M = (k_off + k_int)/k_on and b = K_M V, so
b ln(n0/n) + (n0 - n) = a t. It is solved for n by Brent's method in y = ln(n0/n) on the
bracket [a t/(b + n0), a t/b]. epsilon = (S/V)/(K_M + c0).

Decimal (``exact=True``) versions of the closed node's forms carry 50 digits.
"""

import math
from decimal import Decimal, localcontext

from scipy.optimize import brentq


def depletion_term(S, V, K_d, c):
    """S/(V (K_d + c)): the relative depletion a fixed-c form neglects (§8.3)."""
    return S / (V * (K_d + c))


def association(t, B0, S, c, k_on, k_off):
    """B(t) at a fixed free concentration c (A.4)."""
    lam = k_on * c + k_off
    B_eq = S * c / (k_off / k_on + c)
    return B_eq + (B0 - B_eq) * math.exp(-lam * t)


def dissociation(t, B0, k_off):
    """B(t) into a node held near zero (A.4)."""
    return B0 * math.exp(-k_off * t)


def internalisation_fixed(t, B0, S, c, k_on, k_off, k_int):
    """(B(t), U(t)) at a fixed free concentration with site-conserving internalisation (A.4)."""
    Lam = k_on * c + k_off + k_int
    Bs = k_on * c * S / Lam
    e = math.exp(-Lam * t)
    B = Bs + (B0 - Bs) * e
    U = k_int * (Bs * t + (B0 - Bs) * (-math.expm1(-Lam * t)) / Lam)
    return B, U


def depletion_roots(N, S, K_d, V, *, exact=False):
    """(r-, r+) of B^2 - (N + S + K_d V) B + N S = 0, r- the depleted equilibrium (A.4)."""
    if exact:
        with localcontext() as ctx:
            ctx.prec = 50
            N, S, K_d, V = (Decimal(x) for x in (N, S, K_d, V))
            b = N + S + K_d * V
            root = (b * b - 4 * N * S).sqrt()
            rm = 2 * N * S / (b + root)
            return rm, (b + root) / 2
    b = N + S + K_d * V
    root = math.sqrt(b * b - 4.0 * N * S)
    return 2.0 * N * S / (b + root), 0.5 * (b + root)


def depletion(t, B0, n0, S, V, k_on, k_off, *, exact=False):
    """B(t) in a closed node with no internalisation: the Riccati solution (A.4). n(t) = N - B(t)
    with N = n0 + B0."""
    K_d = k_off / k_on
    N = n0 + B0
    if exact:
        with localcontext() as ctx:
            ctx.prec = 50
            rm, rp = depletion_roots(N, S, K_d, V, exact=True)
            t, B0d, Vd, kon = (Decimal(x) for x in (t, B0, V, k_on))
            delta = rp - rm
            kappa = kon * delta / Vd
            if B0d == rm:
                return rm
            Q = (B0d - rm) / (B0d - rp) * (-kappa * t).exp()
            return rm - Q * delta / (1 - Q)
    rm, rp = depletion_roots(N, S, K_d, V)
    delta = rp - rm
    kappa = k_on * delta / V
    if B0 == rm:
        return rm
    Q = (B0 - rm) / (B0 - rp) * math.exp(-kappa * t)
    return rm - Q * delta / (1.0 - Q)


def langmuir(S, c, K_d):
    """B = S c/(K_d + c): the isotherm at a fixed free concentration."""
    return S * c / (K_d + c)


def free_concentration_closed(n_total, S, K_d, V):
    """The equilibrium free concentration in a closed node holding n_total of ligand (free plus
    bound) facing one population: (N - r-)/V with N = n_total (A.4's quadratic)."""
    rm, _ = depletion_roots(n_total, S, K_d, V)
    return (n_total - rm) / V


# ---------------------------------------------------------------- R-qss


def sink_constants(S, V, k_on, k_off, k_int):
    """A.5's unit map: dict(a = k_int S (fmol/s), K_M (mM), b = K_M V (fmol))."""
    K_M = (k_off + k_int) / k_on
    return dict(a=k_int * S, K_M=K_M, b=K_M * V)


def epsilon(S, V, k_on, k_off, k_int, c0):
    """epsilon = (S/V)/(K_M + c0) (A.5, §8.3)."""
    return (S / V) / ((k_off + k_int) / k_on + c0)


def sink_amount(t, n0, a, b):
    """n(t) of D150's saturable sink: the root of b ln(n0/n) + (n0 - n) = a t, by Brent's method
    in y = ln(n0/n) on [a t/(b + n0), a t/b]."""
    if t == 0.0 or a == 0.0:
        return n0
    lo, hi = a * t / (b + n0), a * t / b

    def g(y):
        return b * y - n0 * math.expm1(-y) - a * t  # b y + n0 (1 - e^-y) - a t

    if g(lo) >= 0.0:
        return n0 * math.exp(-lo)
    y = brentq(g, lo, hi, xtol=1e-16, rtol=4.0 * 2.220446049250313e-16, maxiter=200)
    return n0 * math.exp(-y)


def sink_half_time(n0, a, b):
    """The time at which the sink's node amount reaches n0/2: (b ln 2 + n0/2)/a."""
    return (b * math.log(2.0) + 0.5 * n0) / a


def quasi_steady_bound(S, c, K_M):
    """B = S c/(K_M + c): the bound pool's quasi-steady value (A.5)."""
    return S * c / (K_M + c)
