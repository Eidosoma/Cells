"""R-closed (Appendix A.4) and R-qss (A.5): closed forms for one population (m = 1).

Every form is evaluated in 50-digit decimals and rounded once.

- **Association at fixed c:** B(t) = B_eq + (B0 - B_eq) e^{-lambda t}, lambda = k_on c + k_off,
  B_eq = S c/(K_d + c).
- **Dissociation** into a node held near zero: B(t) = B0 e^{-k_off t}.
- **Depletion in a closed node, no internalisation:** with N = n + B constant,
  dB/dt = (k_on/V)(B - r-)(B - r+), r+- = [(N + S + K_d V) +- sqrt((N + S + K_d V)^2 - 4 N S)]/2,
  the equilibrium r- (the depletion quadratic); with D = r+ - r-, kappa = k_on D/V and
  Q0 = (B0 - r-)/(B0 - r+), B(t) = (r- - r+ Q0 e^{-kappa t})/(1 - Q0 e^{-kappa t}).
- **Internalisation at fixed c:** Lambda = k_on c + k_off + k_int, B* = k_on c S/Lambda,
  B(t) = B* + (B0 - B*) e^{-Lambda t}, U(t) = k_int [B* t + (B0 - B*)(1 - e^{-Lambda t})/Lambda].
- **R-qss:** with eps = (S/V)/(K_M + c0) << 1 the node follows D150's saturable law,
  b ln(n0/n) + (n0 - n) = a t, a = k_int S, b = K_M V, K_M = (k_off + k_int)/k_on (Segel and
  Slemrod 1989). Its error against R-ode is O(eps) after a layer of about 1/Lambda.

The fixed-c forms are large-V limits: they are checked against R-ode at the world's V, where the
depletion term S/(V (K_d + c)) is stated, never compared with the engine directly.
"""

from __future__ import annotations

from decimal import localcontext
from fractions import Fraction

import numpy as np

from .exact import DIGITS, dec


def association(B0, S, k_on, k_off, c, times) -> np.ndarray:
    with localcontext() as ctx:
        ctx.prec = DIGITS
        kon, koff, C, Sd, b0 = dec(k_on), dec(k_off), dec(c), dec(S), dec(B0)
        lam = kon * C + koff
        beq = Sd * C / (koff / kon + C)
        return np.array([float(beq + (b0 - beq) * (-lam * dec(t)).exp()) for t in times])


def dissociation(B0, k_off, times) -> np.ndarray:
    with localcontext() as ctx:
        ctx.prec = DIGITS
        return np.array([float(dec(B0) * (-dec(k_off) * dec(t)).exp()) for t in times])


def depletion_roots(N, S, K_d, V) -> tuple:
    """(r-, r+) of the depletion quadratic, in decimals; r- is the equilibrium bound amount."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        p = dec(N) + dec(S) + dec(K_d) * dec(V)
        disc = (p * p - 4 * dec(N) * dec(S)).sqrt()
        rp = (p + disc) / 2
        rm = 4 * dec(N) * dec(S) / (2 * (p + disc))          # = (p - disc)/2, without cancelling
        return rm, rp


def depletion(B0, n0, S, k_on, k_off, V, times) -> dict:
    """The closed node's Riccati solution: B(t) and the free amount n(t) = N - B(t)."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        N = dec(n0) + dec(B0)
        rm, rp = depletion_roots(N, S, dec(k_off) / dec(k_on), V)
        kappa = dec(k_on) * (rp - rm) / dec(V)
        b0 = dec(B0)
        Q0 = (b0 - rm) / (b0 - rp)
        Bs = []
        for t in times:
            e = Q0 * (-kappa * dec(t)).exp()
            Bs.append((rm - rp * e) / (1 - e))
        B = np.array([float(x) for x in Bs])
        n = np.array([float(N - x) for x in Bs])
        return {"B_fmol": B, "n_fmol": n, "B_eq_fmol": float(rm), "r_plus_fmol": float(rp),
                "kappa_per_s": float(kappa)}


def internalisation(B0, S, k_on, k_off, k_int, c, times) -> dict:
    with localcontext() as ctx:
        ctx.prec = DIGITS
        kon, koff, ki, C, Sd, b0 = (dec(x) for x in (k_on, k_off, k_int, c, S, B0))
        Lam = kon * C + koff + ki
        Bs = kon * C * Sd / Lam
        B, U = [], []
        for t in times:
            e = (-Lam * dec(t)).exp()
            B.append(float(Bs + (b0 - Bs) * e))
            U.append(float(ki * (Bs * dec(t) + (b0 - Bs) * (1 - e) / Lam)))
        return {"B_fmol": np.array(B), "internalised_fmol": np.array(U), "B_star_fmol": float(Bs)}


def qss(n0, S, k_on, k_off, k_int, V, times) -> dict:
    """R-qss: D150's saturable law with A.5's unit map; returns n(t), a, b, K_M and eps."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        kon, koff, ki = dec(k_on), dec(k_off), dec(k_int)
        KM = (koff + ki) / kon
        A = ki * dec(S)
        B = KM * dec(V)
        n_init = dec(n0)
        eps = (dec(S) / dec(V)) / (KM + n_init / dec(V))
        out = []
        n = n_init
        for t in times:
            target = A * dec(t)
            for _ in range(200):
                f = B * (n_init / n).ln() + (n_init - n) - target
                step = f / (-B / n - 1)
                while n - step <= 0:
                    step /= 2
                n = n - step
                if abs(step) <= abs(n) * dec(Fraction(1, 10 ** 45)):
                    break
            out.append(float(n))
        return {"n_fmol": np.array(out), "a_fmol_per_s": float(A), "b_fmol": float(B),
                "K_M_mM": float(KM), "epsilon": float(eps)}
