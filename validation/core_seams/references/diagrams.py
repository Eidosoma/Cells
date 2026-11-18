"""Kinetic diagrams: Hill's cycles, their one-way fluxes and Wegscheider's residual.

A diagram law has states and edges between two states; parallel edges are allowed (a
multigraph). Each edge has a forward rate (its ``from`` state to its ``to`` state) and a
backward rate, each of mass-action form

    α = k0 × Π_{(s,e)} a_{s,e}^order × exp(ζ ψ),    ψ = F (φ_N − φ_P)/RT,

with a = c/c° the activity of species s at end e (N or P). ζ_fwd − ζ_bwd is the charge the
transition moves from N to P. A cycle is a closed walk of distinct edges through distinct states,
declared with a traversal: each edge with +1 (from → to) or −1 (to → from).

**Two independent routes** (the cycle-flux decomposition is cited as the design cites it, Hill
1989 and King and Altman 1956, unread; it is self-verified here):
- *Combinatorial.* Spanning trees are enumerated; a state's directional sum D_i is the sum over
  trees of the product of rates directed toward i, and Σ = Σ_i D_i. A cycle's Σ_κ sums the trees
  of the diagram with the cycle contracted to one root. Then p_i = D_i/Σ and the cycle's one-way
  fluxes per carrier are j±_κ = Π±_κ Σ_κ/Σ.
- *Algebraic.* The master equation's steady state p Q = 0, Σ p = 1, is solved by elimination; D_i
  and Σ_κ are the principal minors of the out-rate Laplacian (the all-minors matrix-tree theorem).
- *Consistency.* Every edge's net flux p_i α_ij − p_j α_ji equals the signed sum of the net fluxes
  of the cycles through it, which holds only for the complete set of cycles.

Every function takes rates as Decimals or ``exact.Dual``s, so slopes come out exactly.
"""

from __future__ import annotations

import itertools
from decimal import Decimal

from . import exact
from .exact import Dual, context, dec, dexp, dln, value

ENDS = ("N", "P")


# --------------------------------------------------------------------------------------------
# Rates
# --------------------------------------------------------------------------------------------

def activity(state: dict, species: str, end: str, c0_mM):
    """a = c/c° at an end, from ``state['c_mM'][end][species]`` (a Decimal, a Dual or a float)."""
    c = state["c_mM"][end][species]
    c = c if isinstance(c, (Decimal, Dual)) else dec(c)
    return c / dec(c0_mM)


def psi(state: dict, T_K):
    """ψ = F (φ_N − φ_P)/RT, from ``state['phi_V']`` {N, P}."""
    phN, phP = state["phi_V"]["N"], state["phi_V"]["P"]
    phN = phN if isinstance(phN, (Decimal, Dual)) else dec(phN)
    phP = phP if isinstance(phP, (Decimal, Dual)) else dec(phP)
    return (phN - phP) * exact.F_over_RT(T_K)


def directed_rate(rate: dict, state: dict, c0_mM, ps):
    """α = k0 Π a^order exp(ζ ψ) for one direction of an edge."""
    with context():
        out = dec(rate["k0_per_s"])
        for species, end, order in rate.get("orders", []):
            out = out * activity(state, species, end, c0_mM) ** int(order)
        zeta = dec(rate.get("zeta", 0.0))
        if zeta != 0:
            out = out * dexp(zeta * ps)
        return out


def edge_rates(law: dict, state: dict, registry: dict) -> dict:
    """{edge id: (α_fwd, α_bwd)} at a state."""
    with context():
        ps = psi(state, registry["temperature_K"])
        c0 = registry["standard_concentration_mM"]
        return {e["id"]: (directed_rate(e["fwd"], state, c0, ps),
                          directed_rate(e["bwd"], state, c0, ps)) for e in law["edges"]}


# --------------------------------------------------------------------------------------------
# Structure: cycles and spanning trees (multigraph aware)
# --------------------------------------------------------------------------------------------

def _edge_ends(law):
    return {e["id"]: (int(e["from"]), int(e["to"])) for e in law["edges"]}


def _connected(vertices, edges, ends) -> bool:
    vertices = set(vertices)
    if not vertices:
        return True
    adj = {v: set() for v in vertices}
    for eid in edges:
        i, j = ends[eid]
        adj[i].add(j)
        adj[j].add(i)
    start = next(iter(vertices))
    seen, stack = {start}, [start]
    while stack:
        v = stack.pop()
        for w in adj[v]:
            if w not in seen:
                seen.add(w)
                stack.append(w)
    return seen == vertices


def simple_cycles(law: dict) -> list:
    """Every simple cycle of the diagram, as a sorted tuple of edge ids (a 2-cycle of two parallel
    edges included): edge subsets in which every touched state has degree 2 and which connect."""
    ends = _edge_ends(law)
    ids = [e["id"] for e in law["edges"]]
    out = []
    for r in range(2, len(ids) + 1):
        for sub in itertools.combinations(ids, r):
            deg = {}
            for eid in sub:
                i, j = ends[eid]
                if i == j:
                    break
                deg[i] = deg.get(i, 0) + 1
                deg[j] = deg.get(j, 0) + 1
            else:
                if all(d == 2 for d in deg.values()) and _connected(deg.keys(), sub, ends):
                    out.append(tuple(sorted(sub)))
    return out


def cycle_states(law: dict, cycle: dict) -> set:
    ends = _edge_ends(law)
    vs = set()
    for eid, _d in cycle["edges"]:
        vs.update(ends[eid])
    return vs


def check_traversal(law: dict, cycle: dict) -> None:
    """Refuse a declared cycle whose signed edges do not form one closed walk."""
    ends = _edge_ends(law)
    walk = []
    for eid, d in cycle["edges"]:
        i, j = ends[eid]
        walk.append((i, j) if int(d) == 1 else (j, i))
    for (_a, b), (c, _d) in zip(walk, walk[1:] + walk[:1], strict=True):
        if b != c:
            raise ValueError(f"cycle {cycle['id']}: the walk breaks between {b} and {c}")
    if len({a for a, _ in walk}) != len(walk):
        raise ValueError(f"cycle {cycle['id']}: a state is visited twice")


def _find(parent: list, x: int) -> int:
    """Union-find's root, with path halving."""
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def spanning_trees(n_states: int, edges: list, ends: dict) -> list:
    """Every spanning tree of the multigraph on ``n_states`` vertices, as tuples of edge ids."""
    out = []
    for sub in itertools.combinations(edges, n_states - 1):
        if any(ends[e][0] == ends[e][1] for e in sub):
            continue
        parent = list(range(n_states))
        ok = True
        for eid in sub:
            a, b = _find(parent, ends[eid][0]), _find(parent, ends[eid][1])
            if a == b:
                ok = False
                break
            parent[a] = b
        if ok:
            out.append(sub)
    return out


def _tree_toward(tree, root, ends, rates):
    """Product of the tree's rates with every edge directed toward ``root``."""
    adj = {}
    for eid in tree:
        i, j = ends[eid]
        adj.setdefault(i, []).append((j, eid))
        adj.setdefault(j, []).append((i, eid))
    prod = Decimal(1)
    seen, stack = {root}, [root]
    while stack:
        v = stack.pop()
        for w, eid in adj.get(v, []):
            if w in seen:
                continue
            seen.add(w)
            stack.append(w)
            i, _j = ends[eid]
            a_fwd, a_bwd = rates[eid]
            prod = prod * (a_fwd if w == i else a_bwd)    # the edge is traversed w -> v
    return prod


# --------------------------------------------------------------------------------------------
# Method 1: combinatorial (directional diagrams)
# --------------------------------------------------------------------------------------------

def directional_sums(law: dict, rates: dict) -> list:
    """D_i for every state (sum over spanning trees of the rates directed toward i)."""
    n = len(law["states"])
    ends = _edge_ends(law)
    trees = spanning_trees(n, [e["id"] for e in law["edges"]], ends)
    with context():
        return [sum((_tree_toward(t, i, ends, rates) for t in trees), Decimal(0))
                for i in range(n)]


def cycle_sigma_trees(law: dict, cycle: dict, rates: dict):
    """Σ_κ: the trees of the diagram with the cycle's states contracted to one root."""
    ends = _edge_ends(law)
    on = cycle_states(law, cycle)
    off = [v for v in range(len(law["states"])) if v not in on]
    if not off:
        return Decimal(1)
    root = -1
    label = {v: (root if v in on else v) for v in range(len(law["states"]))}
    cyc = {eid for eid, _d in cycle["edges"]}
    cand = [e["id"] for e in law["edges"]
            if e["id"] not in cyc and not (label[ends[e["id"]][0]] == root and
                                           label[ends[e["id"]][1]] == root)]
    cends = {eid: (label[ends[eid][0]], label[ends[eid][1]]) for eid in cand}
    verts = [root] + off
    index = {v: k for k, v in enumerate(verts)}
    iends = {eid: (index[a], index[b]) for eid, (a, b) in cends.items()}
    trees = spanning_trees(len(verts), cand, iends)
    with context():
        return sum((_tree_toward(t, index[root], iends, rates) for t in trees), Decimal(0))


# --------------------------------------------------------------------------------------------
# Method 2: algebraic (the master equation and the matrix-tree minors)
# --------------------------------------------------------------------------------------------

def out_laplacian(law: dict, rates: dict) -> list:
    """L with L_ii = Σ out-rates of i and L_ij = −(rate i → j), summed over parallel edges."""
    n = len(law["states"])
    with context():
        L = [[Decimal(0)] * n for _ in range(n)]
        for e in law["edges"]:
            i, j = int(e["from"]), int(e["to"])
            a_fwd, a_bwd = rates[e["id"]]
            L[i][j] = L[i][j] - a_fwd
            L[j][i] = L[j][i] - a_bwd
            L[i][i] = L[i][i] + a_fwd
            L[j][j] = L[j][j] + a_bwd
        return L


def minor(L: list, keep: list):
    with context():
        return exact.det([[L[r][c] for c in keep] for r in keep])


def directional_sums_minors(law: dict, rates: dict) -> list:
    L = out_laplacian(law, rates)
    n = len(L)
    return [minor(L, [k for k in range(n) if k != i]) for i in range(n)]


def cycle_sigma_minors(law: dict, cycle: dict, rates: dict):
    L = out_laplacian(law, rates)
    on = cycle_states(law, cycle)
    return minor(L, [k for k in range(len(L)) if k not in on])


def steady_state(law: dict, rates: dict) -> list:
    """p with p Q = 0 and Σ p = 1, Q = −L (the generator), by elimination."""
    L = out_laplacian(law, rates)
    n = len(L)
    with context():
        A = [[-L[c][r] for c in range(n)] for r in range(n)]     # Q^T
        A[-1] = [Decimal(1)] * n
        b = [Decimal(0)] * (n - 1) + [Decimal(1)]
        return exact.solve(A, b)


# --------------------------------------------------------------------------------------------
# Fluxes
# --------------------------------------------------------------------------------------------

def products(law: dict, cycle: dict, rates: dict) -> tuple:
    """(Π⁺, Π⁻) around the cycle in its declared + direction."""
    with context():
        pp, pm = Decimal(1), Decimal(1)
        for eid, d in cycle["edges"]:
            a_fwd, a_bwd = rates[eid]
            if int(d) == 1:
                pp, pm = pp * a_fwd, pm * a_bwd
            else:
                pp, pm = pp * a_bwd, pm * a_fwd
        return pp, pm


def edge_fluxes(law: dict, rates: dict, p: list) -> dict:
    """{edge: (one-way forward p_i α_fwd, one-way backward p_j α_bwd, net)} per carrier."""
    with context():
        out = {}
        for e in law["edges"]:
            i, j = int(e["from"]), int(e["to"])
            a_fwd, a_bwd = rates[e["id"]]
            f, b = p[i] * a_fwd, p[j] * a_bwd
            out[e["id"]] = (f, b, f - b)
        return out


def cycle_fluxes(law: dict, rates: dict, method: str = "trees") -> dict:
    """Per declared cycle: Π±, Σ_κ/Σ and the one-way fluxes j± per carrier (1/s)."""
    with context():
        if method == "trees":
            D = directional_sums(law, rates)
            sig = {c["id"]: cycle_sigma_trees(law, c, rates) for c in law["cycles"]}
        elif method == "minors":
            D = directional_sums_minors(law, rates)
            sig = {c["id"]: cycle_sigma_minors(law, c, rates) for c in law["cycles"]}
        else:
            raise ValueError(method)
        total = sum(D, Decimal(0))
        out = {}
        for c in law["cycles"]:
            pp, pm = products(law, c, rates)
            share = sig[c["id"]] / total
            out[c["id"]] = {"Pi_plus": pp, "Pi_minus": pm, "sigma_share": share,
                            "j_plus": pp * share, "j_minus": pm * share,
                            "j_net": (pp - pm) * share}
        out["_p"] = [d / total for d in D]
        return out


def hill_consistency(law: dict, rates: dict, cyc: dict, p: list):
    """max over edges of |J_edge − Σ_κ s(κ, e) J_κ| relative to the largest one-way edge flux."""
    flux = edge_fluxes(law, rates, p)
    with context():
        worst, scale = Decimal(0), Decimal(0)
        for e in law["edges"]:
            s = Decimal(0)
            for c in law["cycles"]:
                for eid, d in c["edges"]:
                    if eid == e["id"]:
                        s = s + int(d) * cyc[c["id"]]["j_net"]
            f, b, net = flux[e["id"]]
            worst = max(worst, abs(value(net) - value(s)))
            scale = max(scale, abs(value(f)), abs(value(b)))
        return worst / scale if scale > 0 else worst


def cycle_set_complete(law: dict) -> dict:
    """Whether the declared cycles are exactly the diagram's simple cycles (Hill's full set)."""
    found = set(simple_cycles(law))
    declared = {tuple(sorted(eid for eid, _d in c["edges"])) for c in law["cycles"]}
    return {"complete": declared == found, "declared": len(declared), "found": len(found),
            "missing": sorted(found - declared), "extra": sorted(declared - found)}


def basis_shares_an_edge(law: dict) -> bool:
    """True when two declared cycles share an edge (a basis is admitted only when none do)."""
    sets = [{eid for eid, _d in c["edges"]} for c in law["cycles"]]
    return any(a & b for a, b in itertools.combinations(sets, 2))


# --------------------------------------------------------------------------------------------
# Wegscheider's residual, exact and affine
# --------------------------------------------------------------------------------------------

def implied_stoichiometry(law: dict, cycle: dict) -> dict:
    """ν implied by the rates' orders around the cycle: Σ_edges d (order_bwd − order_fwd)."""
    edges = {e["id"]: e for e in law["edges"]}
    nu = {}
    for eid, d in cycle["edges"]:
        e = edges[eid]
        for s, end, o in e["bwd"].get("orders", []):
            nu[(s, end)] = nu.get((s, end), 0) + int(d) * int(o)
        for s, end, o in e["fwd"].get("orders", []):
            nu[(s, end)] = nu.get((s, end), 0) - int(d) * int(o)
    return {k: v for k, v in nu.items() if v != 0}


def affine_residual(law: dict, cycle: dict, registry: dict) -> dict:
    """r = ln Π⁺ − ln Π⁻ + ΔG/RT as r0 + Σ b_{s,e} ln a_{s,e} + b_ψ ψ, with exact coefficients.

    The declared ν gives ΔG/RT = Σ ν (μ°/RT + ln a) − n_q ψ (a charge-balanced mode). r0 is in
    decimals (the published constants are doubles, so it is zero only to their rounding); the
    other coefficients are exact rationals."""
    from fractions import Fraction
    edges = {e["id"]: e for e in law["edges"]}
    species = registry["species"]
    nu = {(s, end): int(n) for s, end, n in cycle["nu"]}
    b = {}
    bpsi = Fraction(0)
    with context():
        r0 = Decimal(0)
        for eid, d in cycle["edges"]:
            e = edges[eid]
            d = int(d)
            r0 = r0 + d * (dln(dec(e["fwd"]["k0_per_s"])) - dln(dec(e["bwd"]["k0_per_s"])))
            for s, end, o in e["fwd"].get("orders", []):
                b[(s, end)] = b.get((s, end), 0) + d * int(o)
            for s, end, o in e["bwd"].get("orders", []):
                b[(s, end)] = b.get((s, end), 0) - d * int(o)
            bpsi += d * (Fraction(float(e["fwd"].get("zeta", 0.0))) -
                         Fraction(float(e["bwd"].get("zeta", 0.0))))
        for (s, end), n in nu.items():
            r0 = r0 + n * dec(species[s]["mu0_RT"])
            b[(s, end)] = b.get((s, end), 0) + n
        nq = sum(int(species[s]["valence"]) * n for (s, end), n in nu.items() if end == "P")
        bpsi -= nq
    return {"r0": r0, "b": {k: v for k, v in b.items() if v != 0}, "b_psi": bpsi, "n_q": nq}


def residual(law: dict, cycle: dict, registry: dict, state: dict):
    """r at a state, at 50 digits: ln(Π⁺/Π⁻) from the rates plus ΔG/RT from the registry."""
    rates = edge_rates(law, state, registry)
    with context():
        pp, pm = products(law, cycle, rates)
        return dln(pp) - dln(pm) + mode_dG_RT(cycle["nu"], registry, state)


def mode_dG_RT(nu: list, registry: dict, state: dict):
    """ΔG/RT = Σ ν (μ°/RT + ln(c/c°) + z F φ_e/RT) over the mode's rows (absolute potentials)."""
    with context():
        T = registry["temperature_K"]
        c0 = registry["standard_concentration_mM"]
        f = exact.F_over_RT(T)
        out = Decimal(0)
        for s, end, n in nu:
            sp = registry["species"][s]
            phi = state["phi_V"][end]
            phi = phi if isinstance(phi, (Decimal, Dual)) else dec(phi)
            out = out + int(n) * (dec(sp["mu0_RT"]) + dln(activity(state, s, end, c0)) +
                                  int(sp["valence"]) * f * phi)
        return out


def residual_float(law: dict, cycle: dict, registry: dict, state: dict) -> dict:
    """The honest float64 stand-in: r evaluated in doubles, two ways (sums of logs, and the log
    of the products' ratio), with the absolute sum of its terms for the rounding band."""
    import math
    T = float(registry["temperature_K"])
    c0 = float(registry["standard_concentration_mM"])
    F = float(exact.FARADAY)
    R = float(exact.GAS_CONSTANT)
    ps = F * (float(state["phi_V"]["N"]) - float(state["phi_V"]["P"])) / (R * T)
    edges = {e["id"]: e for e in law["edges"]}

    def lnrate(rate):
        terms = [math.log(float(rate["k0_per_s"]))]
        for s, end, o in rate.get("orders", []):
            terms.append(int(o) * math.log(float(state["c_mM"][end][s]) / c0))
        z = float(rate.get("zeta", 0.0))
        if z:
            terms.append(z * ps)
        return terms

    def rate(rate):
        out = float(rate["k0_per_s"])
        for s, end, o in rate.get("orders", []):
            out *= (float(state["c_mM"][end][s]) / c0) ** int(o)
        z = float(rate.get("zeta", 0.0))
        return out * math.exp(z * ps) if z else out

    plus, minus = [], []
    pp, pm = 1.0, 1.0
    for eid, d in cycle["edges"]:
        e = edges[eid]
        fw, bw = (e["fwd"], e["bwd"]) if int(d) == 1 else (e["bwd"], e["fwd"])
        plus += lnrate(fw)
        minus += lnrate(bw)
        pp *= rate(fw)
        pm *= rate(bw)
    dg_terms = []
    for s, end, n in cycle["nu"]:
        sp = registry["species"][s]
        dg_terms.append(int(n) * float(sp["mu0_RT"]))
        dg_terms.append(int(n) * math.log(float(state["c_mM"][end][s]) / c0))
        dg_terms.append(int(n) * int(sp["valence"]) * F * float(state["phi_V"][end]) / (R * T))
    r_logs = sum(plus) - sum(minus) + sum(dg_terms)
    r_ratio = math.log(pp / pm) + sum(dg_terms)
    scale = sum(abs(t) for t in plus) + sum(abs(t) for t in minus) + sum(abs(t) for t in dg_terms)
    return {"r_sum_of_logs": r_logs, "r_log_of_ratio": r_ratio, "terms_abs_sum": scale}
