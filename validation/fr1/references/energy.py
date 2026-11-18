"""A.10: the free energy of the nodes and each law's work.

G = 1e-3 RT sum_nodes n (ln(n/V) - 1) pJ, with RT in J/mol (exact SI), n in fmol, V in pL and the
log of the mM number (a 1 mM standard state). A node's change for an amount change dn is
evaluated per node, never as a difference of totals:

    dG_node(n, dn) = 1e-3 RT [dn (ln(n/V) - 1) + (n + dn) log1p(dn/n)],

in 50-digit decimals. Each law's work is the change of the nodes it touches:
- an exchange move of m from node 1 to node 2: dG_node(n_1, -m) + dG_node(n_2, +m);
- a turnover clearance of m at a node: dG_node(n, -m);
- a reaction S -> P of extent m at a node: dG_node(n_S, -m) + dG_node(n_P, +m), plus
  1e-3 (mu0_P - mu0_S) m when standard potentials (J/mol) are declared.

The energy closes as dG = sum W_ops + W_bath - H_faces (A.10). ``closure`` returns that residual
from the parts a run books.
"""

from __future__ import annotations

from decimal import Decimal, localcontext

from .exact import DIGITS, RT, dec, exact


def node_free_energy(n, V, temperature_K) -> float:
    """G of one node's species: 1e-3 RT n (ln(n/V) - 1) pJ."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        N = dec(n)
        return float(dec(RT(temperature_K)) * N * ((N / dec(V)).ln() - 1) / 1000)


def node_change(n, dn, V, temperature_K) -> Decimal:
    """dG_node(n, dn) in decimals (pJ); n > 0 and n + dn > 0."""
    n_, dn_ = exact(n), exact(dn)
    if dn_ == 0:
        return Decimal(0)
    if n_ <= 0 or n_ + dn_ <= 0:
        raise ValueError("amounts must stay positive")
    with localcontext() as ctx:
        ctx.prec = DIGITS
        return dec(RT(temperature_K)) * (dec(dn_) * (dec(n_ / exact(V)).ln() - 1) +
                                         dec(n_ + dn_) * dec((n_ + dn_) / n_).ln()) / 1000


def exchange_work(n_from, n_to, moved, V_from, V_to, temperature_K) -> float:
    with localcontext() as ctx:
        ctx.prec = DIGITS
        return float(node_change(n_from, -exact(moved), V_from, temperature_K) +
                     node_change(n_to, exact(moved), V_to, temperature_K))


def clearance_work(n, cleared, V, temperature_K) -> float:
    return float(node_change(n, -exact(cleared), V, temperature_K))


def reaction_work(n_S, n_P, extent, V, temperature_K, mu0_S=0, mu0_P=0) -> float:
    with localcontext() as ctx:
        ctx.prec = DIGITS
        w = node_change(n_S, -exact(extent), V, temperature_K) + \
            node_change(n_P, exact(extent), V, temperature_K) + \
            (dec(mu0_P) - dec(mu0_S)) * dec(extent) / 1000
        return float(w)


def closure(dG_total, works, bath_work=0.0, face_heat=0.0) -> float:
    """The residual dG - (sum W_ops + W_bath - H_faces) (pJ)."""
    return float(dG_total) - (sum(float(w) for w in works) + float(bath_work) -
                              float(face_heat))
