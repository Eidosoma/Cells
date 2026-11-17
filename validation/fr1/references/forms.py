"""The closed forms of Appendix A: A.2, A.3 and A.5 to A.8, each with a second method.

Units are @3's: fmol, pL, mM = fmol/pL, s, m and m/s. 1e15 converts m^3 to pL. Each function
takes plain numbers (read as the exact values of their doubles) and record times, and returns
float64 arrays at those times together with a ``floor``: the larger of half an ulp and the
difference from the second method. The primary values are evaluated in 50-digit decimals and
rounded once, so their own error is half an ulp.

**A.2, loading with retention** (export only):
- flux law: n_o(t) = n_o(0) + J t and n_c(t) = n_c(0) - J t while n_c > 0 (exact rationals; the
  times where n_c would not stay positive are flagged, not extrapolated);
- first-order law: n_c(t) = n_c(0) e^{-k_e t}, n_o(t) = n_o(0) + n_c(0)(1 - e^{-k_e t}).

**A.3, two-way first-order exchange:** dn_c/dt = -a n_c + b n_o and dn_o/dt = a n_c - b n_o, with
a = k_e and b = kappa = 1e15 k_u A / V_o. N = n_c + n_o is conserved, and x = n_c/N relaxes as
x(t) = x_eq + (x(0) - x_eq) e^{-(a+b) t}, x_eq = b/(a + b).

**A.5, saturable release:** dn_o/dt = -a c_o/(K_M + c_o), a = A V_max, c_o = n_o/V_o. With
b = K_M V_o, n_o(t) solves b ln(n_o(0)/n_o) + (n_o(0) - n_o) = a t, and n_c gains what n_o loses.
Primary: Newton on that equation in decimals. Second: n_o = b omega(n_o(0)/b + ln(n_o(0)/b) -
a t/b), with omega Wright's function (SciPy), since w + ln w = z gives w = omega(z).

**A.6, degradation with loading:** dn_c/dt = -k_e n_c, dn_o/dt = k_e n_c - k n_o; the cleared
amount is the integral of k n_o.

**A.7, a reaction inside:** dn_c/dt = -k_e n_c, dn_S/dt = k_e n_c - k_r n_S and dn_P/dt = k_r n_S
at the compartment; P's cytosolic row is untouched; n_c + n_S + n_P is conserved.

**A.8, the uptake path:** dn_e/dt = -kappa_u n_e (plus an optional face to the bath,
kappa_f (c_b - n_e/V_e)), dn_c/dt = kappa_u n_e - k_e n_c and dn_o/dt = k_e n_c, with
kappa_u = 1e15 k_u A_plasma / V_e.

A.6 to A.8 are linear (affine with the face): the primary is the 50-digit matrix exponential of
the augmented generator, the second SciPy's ``expm``.
"""

from __future__ import annotations

from decimal import localcontext
from fractions import Fraction

import numpy as np
from scipy.linalg import expm
from scipy.special import wrightomega

from .exact import DIGITS, dec, exact, expm_decimal, matvec_decimal


def kappa(k_u, area_m2, volume_pL) -> Fraction:
    """kappa = 1e15 k_u A / V (1/s): a first-order rate from a permeability-like k_u (m/s)."""
    return 10 ** 15 * exact(k_u) * exact(area_m2) / exact(volume_pL)


def _floor(primary: np.ndarray, second: np.ndarray) -> np.ndarray:
    return np.abs(primary - second) + 0.5 * np.spacing(np.abs(primary))


def loading_flux(n_c0, n_o0, J, times) -> dict:
    """A.2's flux law, exact in rationals; ``valid`` is False where n_c would not stay positive."""
    nc0, no0, Jx = exact(n_c0), exact(n_o0), exact(J)
    nc, no, ok = [], [], []
    for t in times:
        moved = Jx * exact(t)
        nc.append(float(nc0 - moved))
        no.append(float(no0 + moved))
        ok.append(nc0 - moved > 0)
    nc, no = np.array(nc), np.array(no)
    return {"n_c_fmol": nc, "n_o_fmol": no, "valid": np.array(ok),
            "floor_fmol": 0.5 * np.spacing(np.maximum(np.abs(nc), np.abs(no)))}


def loading_first_order(n_c0, n_o0, k_e, times) -> dict:
    """A.2's first-order law."""
    t = np.asarray(times, dtype=np.float64)
    with localcontext() as ctx:
        ctx.prec = DIGITS
        nc0, no0, k = dec(n_c0), dec(n_o0), dec(k_e)
        e = [(-k * dec(x)).exp() for x in t]
        nc = np.array([float(nc0 * x) for x in e])
        no = np.array([float(no0 + nc0 * (1 - x)) for x in e])
    nc_f = float(n_c0) * np.exp(-float(k_e) * t)
    no_f = float(n_o0) - float(n_c0) * np.expm1(-float(k_e) * t)
    return {"n_c_fmol": nc, "n_o_fmol": no,
            "floor_fmol": np.maximum(_floor(nc, nc_f), _floor(no, no_f))}


def two_way(n_c0, n_o0, a, b, times) -> dict:
    """A.3's two-way first-order exchange; ``x_eq`` = b/(a + b)."""
    t = np.asarray(times, dtype=np.float64)
    with localcontext() as ctx:
        ctx.prec = DIGITS
        A, B = dec(a), dec(b)
        N = dec(n_c0) + dec(n_o0)
        x0 = dec(n_c0) / N
        xeq = B / (A + B)
        xs = [xeq + (x0 - xeq) * (-(A + B) * dec(x)).exp() for x in t]
        nc = np.array([float(N * x) for x in xs])
        no = np.array([float(N * (1 - x)) for x in xs])
        x_eq = float(xeq)
    G = np.array([[-float(a), float(b)], [float(a), -float(b)]])
    y0 = np.array([float(n_c0), float(n_o0)])
    sec = np.array([expm(G * x) @ y0 for x in t])
    return {"n_c_fmol": nc, "n_o_fmol": no, "x_eq": x_eq,
            "floor_fmol": np.maximum(_floor(nc, sec[:, 0]), _floor(no, sec[:, 1]))}


def saturable_release(n_o0, n_c0, a_fmol_per_s, b_fmol, times) -> dict:
    """A.5's implicit closed form: the compartment releases into the cytosol at
    dn_o/dt = -a n_o/(b + n_o), with a = A V_max (fmol/s) and b = K_M V_o (fmol)."""
    a, b = exact(a_fmol_per_s), exact(b_fmol)
    t = np.asarray(times, dtype=np.float64)
    bf, n0f = float(b), float(n_o0)
    no_w = bf * wrightomega(n0f / bf + np.log(n0f / bf) - float(a) * t / bf).real
    out = []
    with localcontext() as ctx:
        ctx.prec = DIGITS
        A, B, n0 = dec(a), dec(b), dec(n_o0)
        for x, guess in zip(t, no_w, strict=True):
            target = A * dec(x)
            n = dec(guess) if guess > 0 else n0 / 2
            for _ in range(200):
                f = B * (n0 / n).ln() + (n0 - n) - target
                step = f / (-B / n - 1)
                while n - step <= 0:          # keep the iterate positive: halve the step
                    step /= 2
                n = n - step
                if abs(step) <= abs(n) * dec(Fraction(1, 10 ** 45)):
                    break
            out.append(n)
        no = np.array([float(v) for v in out])
        nc = np.array([float(dec(n_c0) + (n0 - v)) for v in out])
    return {"n_o_fmol": no, "n_c_fmol": nc, "a_fmol_per_s": float(a), "b_fmol": float(b),
            "floor_fmol": np.maximum(_floor(no, no_w), _floor(nc, float(n_c0) + n0f - no_w))}


def linear(G, g, y0, times) -> dict:
    """dy/dt = G y + g (constant), by the augmented matrix exponential: decimals and SciPy."""
    n = len(y0)
    forced = any(exact(x) != 0 for x in g)
    if forced:
        aug = [[exact(G[i][j]) for j in range(n)] + [exact(g[i])] for i in range(n)]
        aug.append([Fraction(0)] * (n + 1))
        v0 = [exact(x) for x in y0] + [Fraction(1)]
    else:
        aug = [[exact(G[i][j]) for j in range(n)] for i in range(n)]
        v0 = [exact(x) for x in y0]
    t = np.asarray(times, dtype=np.float64)
    prim = np.empty((t.size, n))
    for k, x in enumerate(t):
        E = expm_decimal(aug, exact(x))
        prim[k] = [float(v) for v in matvec_decimal(E, v0)[:n]]
    augf = np.array([[float(x) for x in row] for row in aug])
    v0f = np.array([float(x) for x in v0])
    sec = np.array([(expm(augf * x) @ v0f)[:n] for x in t])
    return {"y": prim, "y_expm": sec, "floor": _floor(prim, sec)}


def degradation(n_c0, n_o0, k_e, k, times) -> dict:
    """A.6: loading plus first-order clearance in the compartment; the cleared amount too."""
    ke, kk = exact(k_e), exact(k)
    G = [[-ke, 0, 0], [ke, -kk, 0], [0, kk, 0]]
    r = linear(G, [0, 0, 0], [n_c0, n_o0, 0], times)
    return {"n_c_fmol": r["y"][:, 0], "n_o_fmol": r["y"][:, 1], "cleared_fmol": r["y"][:, 2],
            "floor_fmol": r["floor"]}


def reaction_inside(n_c0, n_S0, n_P0, k_e, k_r, times) -> dict:
    """A.7: loading of S plus first-order S -> P at the compartment."""
    ke, kr = exact(k_e), exact(k_r)
    G = [[-ke, 0, 0], [ke, -kr, 0], [0, kr, 0]]
    r = linear(G, [0, 0, 0], [n_c0, n_S0, n_P0], times)
    return {"n_c_fmol": r["y"][:, 0], "n_S_fmol": r["y"][:, 1], "n_P_fmol": r["y"][:, 2],
            "floor_fmol": r["floor"]}


def uptake(n_e0, n_c0, n_o0, kappa_u, k_e, times, face=None) -> dict:
    """A.8: extracellular node -> cytosol -> compartment, with an optional face to a held bath.

    ``face`` is (kappa_f pL/s, V_e pL, c_b mM): dn_e/dt gains kappa_f (c_b - n_e/V_e), and the
    bath's cumulative supply S(t) (fmol, out of the bath) is returned.
    """
    ku, ke = exact(kappa_u), exact(k_e)
    G = [[-ku, 0, 0, 0], [ku, -ke, 0, 0], [0, ke, 0, 0], [0, 0, 0, 0]]
    g = [0, 0, 0, 0]
    if face is not None:
        kf, Ve, cb = (exact(x) for x in face)
        G[0][0] -= kf / Ve
        g[0] += kf * cb
        G[3][0] = -kf / Ve          # dS/dt = kappa_f (c_b - c_e)
        g[3] = kf * cb
    r = linear(G, g, [n_e0, n_c0, n_o0, 0], times)
    out = {"n_e_fmol": r["y"][:, 0], "n_c_fmol": r["y"][:, 1], "n_o_fmol": r["y"][:, 2],
           "floor_fmol": r["floor"][:, :3]}
    if face is not None:
        out["supply_fmol"] = r["y"][:, 3]
        out["supply_floor_fmol"] = r["floor"][:, 3]
    return out
