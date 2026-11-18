"""R-eq: the equilibrium of populations sharing a closed node, and its total heat.

With no internalisation, a closed node of volume V holding N = n + sum_k B_k of ligand reaches
B_k = S_k c/(K_d,k + c) for every population facing it, where c solves

    f(c) = c V + sum_k S_k c/(K_d,k + c) - N = 0,

which increases strictly in c, so its root in (0, N/V) is unique. It is found by bisection and
Newton in 50-digit decimals. For one population it equals the depletion quadratic's r-.

The relaxation's total heat is G(start) - G(equilibrium) (the closed sub-system books no work).
"""

from __future__ import annotations

from decimal import localcontext

from . import energy
from .exact import DIGITS, dec


def shared_node(N, V, sites: list, K_d: list) -> dict:
    """{c_mM, n_fmol, B_fmol [k]} at equilibrium, in decimals then rounded."""
    with localcontext() as ctx:
        ctx.prec = DIGITS + 5
        Nd, Vd = dec(N), dec(V)
        S = [dec(s) for s in sites]
        K = [dec(k) for k in K_d]

        def f(c):
            return c * Vd + sum(s * c / (k + c) for s, k in zip(S, K, strict=True)) - Nd
        lo, hi = dec(0), Nd / Vd
        for _ in range(400):
            mid = (lo + hi) / 2
            if f(mid) > 0:
                hi = mid
            else:
                lo = mid
            if hi - lo <= hi * dec(10) ** (-(DIGITS + 2)):
                break
        c = (lo + hi) / 2
        B = [s * c / (k + c) for s, k in zip(S, K, strict=True)]
        return {"c_mM": float(c), "n_fmol": float(c * Vd), "B_fmol": [float(b) for b in B],
                "residual_fmol": float(f(c))}


def relaxation_heat(n_start, B_start: list, V, sites: list, K_d: list, RT) -> dict:
    """The total heat of a closed relaxation to equilibrium: G(start) - G(eq) (pJ)."""
    N = float(n_start) + sum(float(b) for b in B_start)
    eq = shared_node(N, V, sites, K_d)

    def G(n, Bs):
        return energy.node_free_energy(n, V, RT) + sum(
            energy.site_free_energy(b, s, k, RT) for b, s, k in zip(Bs, sites, K_d, strict=True))
    return {"heat_pJ": G(n_start, B_start) - G(eq["n_fmol"], eq["B_fmol"]), "equilibrium": eq}
