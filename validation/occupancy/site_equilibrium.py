"""R-eq: the equilibrium of passive binding on finite site populations (FR-3), an independent
reference.

Written from docs/SITE_OCCUPANCY_DESIGN.md (§3.3, Appendix A.3-A.4), without reading the
operator or its tests. numpy, scipy and the standard library.

A world without internalisation is closed per facing node: the node's ligand and the populations
facing it exchange only with each other (the site operator has no faces), so each node's total
N_i = n_i + sum_{k facing i} B_k is conserved and its equilibrium is independent of the others.
At equilibrium every population obeys Langmuir's isotherm at the common free concentration c,
B_k = S_k c/(K_d,k + c), so c solves the monotone scalar equation
    f(c) = c V_i + sum_k S_k c/(K_d,k + c) - N_i = 0,
bracketed by [N_i/(V_i + sum_k S_k/K_d,k), N_i/V_i] (from S c/(K_d + c) <= c S/K_d and >= 0).
It is solved by Brent's method in ln c, then polished by Newton's method in 50-digit decimal
arithmetic. The relaxation's total heat is G(start) - G(equilibrium), in the increment form
(A.3). One population on its node reduces to the depletion quadratic (A.4, R-closed's r-).
"""

import math
from decimal import Decimal, localcontext

from scipy.optimize import brentq

from validation.occupancy import site_reference as sr


def _node_equilibrium(N, V, pops, digits=50):
    """The free concentration c (float, decimal-polished) for a node of volume V holding N
    (free plus bound) faced by pops = [(S, K_d), ...]."""
    lo = N / (V + sum(S / K for S, K in pops))
    hi = N / V

    def f(x):
        c = math.exp(x)
        return c * V + sum(S * c / (K + c) for S, K in pops) - N

    if lo == hi:
        return hi, Decimal(hi)
    x = brentq(f, math.log(lo), math.log(hi), xtol=1e-15, rtol=4 * 2.220446049250313e-16,
               maxiter=300)
    with localcontext() as ctx:
        ctx.prec = digits
        c = Decimal(math.exp(x))
        Nd, Vd = Decimal(N), Decimal(V)
        dp = [(Decimal(S), Decimal(K)) for S, K in pops]
        for _ in range(8):
            g = c * Vd + sum(S * c / (K + c) for S, K in dp) - Nd
            dg = Vd + sum(S * K / (K + c) ** 2 for S, K in dp)
            step = g / dg
            c -= step
            if abs(step) <= c * Decimal(10) ** (-digits + 5):
                break
        return float(c), c


def equilibrium(world, *, trace_rule=True):
    """The equilibrium of a world without internalisation (refused otherwise).

    Returns dict(c_mM, n_fmol, B_fmol, R_fmol, occupancy, heat_pJ (total, = G(start) - G(eq)),
    node_heat_pJ (per facing node's sub-system), delta_G_pJ, langmuir_at_start (B at each
    population's starting free concentration, the large-V limit) and depletion_term
    (S/(V (K_d + c)) at equilibrium))."""
    sr.check_world(world, trace_rule=trace_rule)
    w = world
    rt = w.rt_pJ_per_fmol
    for name, p in w.populations.items():
        if p.k_int_per_s > 0:
            raise ValueError(f"population {name}: R-eq covers passive binding only "
                             "(internalisation has no equilibrium)")
    facing = {}
    for name, p in w.populations.items():
        facing.setdefault(p.facing, []).append(name)
    out = dict(c_mM={}, n_fmol={}, B_fmol={}, R_fmol={}, occupancy={}, node_heat_pJ={},
               langmuir_at_start={}, depletion_term={})
    for node_name, node in w.nodes.items():
        names = facing.get(node_name, [])
        pops = [w.populations[k] for k in names]
        B0 = [p.initial_occupancy * p.S for p in pops]
        N = node.ligand_fmol + math.fsum(B0)
        c, _ = (_node_equilibrium(N, node.volume_pL, [(p.S, p.K_d) for p in pops])
                if pops else (N / node.volume_pL, None))
        n_eq = c * node.volume_pL
        out["c_mM"][node_name] = c
        out["n_fmol"][node_name] = n_eq
        dG = sr.node_increment(node.ligand_fmol, n_eq - node.ligand_fmol, node.volume_pL, rt)
        c0 = node.ligand_fmol / node.volume_pL
        for name, p, b0 in zip(names, pops, B0, strict=True):
            B = p.S * c / (p.K_d + c)
            R = p.S - B
            out["B_fmol"][name] = B
            out["R_fmol"][name] = R
            out["occupancy"][name] = B / p.S
            out["langmuir_at_start"][name] = p.S * c0 / (p.K_d + c0)
            out["depletion_term"][name] = p.S / (node.volume_pL * (p.K_d + c))
            dG0 = rt * math.log(p.K_d)
            dG += sr.pool_increment(b0, B - b0, p.S, dG0, rt)
            dG += sr.pool_increment(p.S - b0, R - (p.S - b0), p.S, 0.0, rt)
        out["node_heat_pJ"][node_name] = -dG
    out["delta_G_pJ"] = -math.fsum(out["node_heat_pJ"].values())
    out["heat_pJ"] = -out["delta_G_pJ"]
    return out
