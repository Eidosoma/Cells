"""R-dG (Appendix A.3, §3.3): the site and node free energies, their stable increments, and the
ledger.

Energies are in pJ with RT in pJ/fmol (1e-3 R T, R exact SI), amounts in fmol, volumes in pL and
concentrations in mM; ln is taken of the mM number (a 1 mM standard state).

- **Site:** G_site = B [dG0 + RT ln(B/S)] + RT R ln(R/S), with dG0 = RT ln(K_d / 1 mM), R + B = S
  and 0 ln 0 = 0 (the empty population is the reference, G = 0).
- **Node:** G_node = RT n (ln(n/V) - 1), on the ligand's row.
- **Stable increments** for a pool with anchor a, change d and capacity S:
  dg = mu0 d + RT [d ln(a/S) + (a + d) log1p(d/a)] when a > 0, and
  dg = mu0 d + RT xlogy(d, d/S) when a = 0 (exactly 0 at d = 0). A node is the same with V for S
  and an extra -RT d.
- **The ledger:** d(sum G_node) + d(sum G_site) + H - W = 0.

All evaluations are in 50-digit decimals and returned as floats.
"""

from __future__ import annotations

from decimal import Decimal, localcontext

from .exact import DIGITS, dec, exact


def _xlogy(x: Decimal, y: Decimal) -> Decimal:
    return Decimal(0) if x == 0 else x * y.ln()


def site_free_energy(B, S, K_d_mM, RT) -> float:
    """G_site (pJ) of a population with bound B and capacity S (fmol)."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        Bd, Sd, rt = dec(B), dec(S), dec(RT)
        if Bd < 0 or Bd > Sd:
            raise ValueError("bound amount outside [0, S]")
        Rd = Sd - Bd
        dG0 = rt * dec(K_d_mM).ln()
        return float(Bd * dG0 + rt * (_xlogy(Bd, Bd / Sd) + _xlogy(Rd, Rd / Sd)))


def node_free_energy(n, V, RT) -> float:
    """G_node (pJ) of a ligand row."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        N = dec(n)
        return float(dec(RT) * N * ((N / dec(V)).ln() - 1))


def pool_increment(anchor, delta, capacity, RT, mu0=0) -> float:
    """§3.3's stable increment of one site pool (pJ), both branches.

    With a > 0, (a + d) log1p(d/a) = xlogy(a + d, (a + d)/a), which is 0 when the pool empties.
    """
    with localcontext() as ctx:
        ctx.prec = DIGITS
        a, d, S, rt = dec(anchor), dec(delta), dec(capacity), dec(RT)
        if a + d < 0:
            raise ValueError("the pool would go negative")
        if a > 0:
            body = d * (a / S).ln() + _xlogy(a + d, (a + d) / a)
        else:
            body = _xlogy(d, d / S)
        return float(dec(mu0) * d + rt * body)


def node_increment(anchor, delta, V, RT) -> float:
    """The node's stable increment: RT [d (ln(a/V) - 1) + (a + d) log1p(d/a)] (pJ)."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        a, d = dec(anchor), dec(delta)
        if a <= 0 or a + d <= 0:
            raise ValueError("a ligand row must stay positive")
        return float(dec(RT) * (d * ((a / dec(V)).ln() - 1) + (a + d) * (1 + d / a).ln()))


def ledger_residual(G_nodes_start, G_nodes_end, G_sites_start, G_sites_end, heat, work) -> float:
    """d(sum G_node) + d(sum G_site) + H - W (pJ): zero along the exact path."""
    return (float(exact(G_nodes_end)) - float(exact(G_nodes_start)) + float(exact(G_sites_end)) -
            float(exact(G_sites_start)) + float(heat) - float(work))
