"""R-dG: the per-law Delta-G test of cells.operator.site_occupancy@1's half-step and bookings (FR-3), an
independent reference.

Written from docs/SITE_OCCUPANCY_DESIGN.md (§3.3, §3.4 item 2, §4.2, §4.3, Appendix A.3) and the
booking rules of docs/SHARED_INVENTORY_REACTIONS_DESIGN.md Appendix A (D152), which §3.3 adopts,
without reading the operator or its tests. numpy and the standard library.

**The half-step** (§4.2): SSPRK(3,3) in Butcher form over the whole site network (every binding
and internalisation route, every facing node's ligand row, every receiving node's row), unsplit:
    Y1 = y, Y2 = y + h nu J(Y1), Y3 = y + h nu (J(Y1) + J(Y2))/4,
    dxi = h (J(Y1) + J(Y2) + 4 J(Y3))/6 per route, y' = y + nu dxi
(Shu & Osher 1988; Gottlieb, Shu & Tadmor 2001). Routes: binding L_i + R_k <-> B_k,
J = m_b (k_on c R - k_off B) with J+ = m_b k_on c R and J- = m_b k_off B; internalisation
B_k -> R_k + L_r, I = m_i k_int B. The stage condition is h max L <= theta = 1/2 (inclusive) at
Y1, Y2 and Y3, with L_n,i = sum_{k facing i} m_b k_on R_k / V_i, L_R,k = m_b k_on c_i and
L_B,k = m_b k_off + m_i k_int; free rows must stay > 0 and pools >= 0 at every stage and the end.

**Components and class** (§3.3): the static union of each population with its facing node and,
where internalisation is declared, its receiving node. Per step: "idle" when every route of the
component has a zero multiplier (its start state is selected, never offset by a computed zero),
"mixed" when an internalisation route has a positive multiplier, "passive" otherwise.

**Bookings** (§3.3, D152 Appendix A), with the site pools as species of "volume" S and standard
potentials 0 (R) and dG0 = RT ln(K_d / 1 mM) (B), and the facing node as D152's node:
* passive: each facing node's sub-system (its ligand row and the populations facing it) books
  H = -dG of the sub-system and no work;
* mixed: every route's average-vector-field share dxi_r sum_j nu_jr mu_bar_j, with mu_bar_j each
  row's divided-difference potential over the half-step (McLachlan, Quispel & Robidoux 1999);
  each binding route books D152's hybrid heat at its facing node: its share (H = -share) if it
  does not reverse within the step (sign J(Y1) = sign J(Y2) = sign J(Y3) = sign A(y'), all
  nonzero), else the stage quadrature h sum_s b_s RT J(Y_s) A(Y_s), b = (1/6, 1/6, 2/3),
  A = ln(c R/(K_d B)); each population's work is its internalisation share + its binding share +
  its binding heat, so W - H = dG per population and in total.
The increments are §3.3's stable forms: RT [d (ln(a/V) - 1) + (a + d) log1p(d/a)] for a ligand
row, mu0 d + RT [d ln(a/S) + (a + d) log1p(d/a)] for a pool (mu0 d + RT xlogy(d, d/S) at a = 0).

Readings taken here (see the usage note): a binding route with a zero multiplier in a mixed
component books exactly 0; a pool at 0 at a stage is admitted (>= 0); the a = 0, d = 0 pool's
divided difference is unused (every share touching it has a zero extent) and is set to mu0.

Sources: Shu C-W, Osher S. J Comput Phys 1988;77:439-471. Gottlieb S, Shu C-W, Tadmor E. SIAM Rev
2001;43:89-112. McLachlan RI, Quispel GRW, Robidoux N. Phil Trans R Soc Lond A 1999;357:1021-1045.
"""

import math
from dataclasses import dataclass
from decimal import Decimal, localcontext

import numpy as np

from validation.occupancy import site_reference as sr

WEIGHTS = (1.0 / 6.0, 1.0 / 6.0, 2.0 / 3.0)


class Layout:
    """The world's arrays in declaration order (nodes, then populations)."""

    def __init__(self, world):
        w = world
        self.world = w
        self.nodes = list(w.nodes)
        self.pops = list(w.populations)
        ni = {x: i for i, x in enumerate(self.nodes)}
        P = [w.populations[p] for p in self.pops]
        self.rt = w.rt_pJ_per_fmol
        self.V = np.array([w.nodes[x].volume_pL for x in self.nodes])
        self.S = np.array([p.S for p in P])
        self.kon = np.array([p.k_on_per_mM_per_s for p in P])
        self.koff = np.array([p.k_off_per_s for p in P])
        self.kint = np.array([p.k_int_per_s for p in P])
        self.lnKd = np.log(self.koff / self.kon)
        self.dG0 = self.rt * self.lnKd
        self.face = np.array([ni[p.facing] for p in P], dtype=int)
        self.recv = np.array([ni[p.receiving] if p.receiving is not None else -1 for p in P],
                             dtype=int)
        # Static components (union-find over nodes 0..N-1 and populations N..N+P-1).
        nn, npop = len(self.nodes), len(self.pops)
        parent = list(range(nn + npop))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for k in range(npop):
            parent[find(nn + k)] = find(int(self.face[k]))
            if self.recv[k] >= 0:
                parent[find(nn + k)] = find(int(self.recv[k]))
        roots = [find(x) for x in range(nn + npop)]
        ids = {r: j for j, r in enumerate(dict.fromkeys(roots))}
        self.node_component = np.array([ids[roots[i]] for i in range(nn)], dtype=int)
        self.pop_component = np.array([ids[roots[nn + k]] for k in range(npop)], dtype=int)
        self.components = len(ids)

    def initial_state(self):
        w = self.world
        n = np.array([w.nodes[x].ligand_fmol for x in self.nodes])
        theta = np.array([w.populations[p].initial_occupancy for p in self.pops])
        B = theta * self.S
        return n, B, self.S - B


def _rates(L, n, B, R, mb, mi):
    c = n / L.V
    jp = mb * L.kon * c[L.face] * R
    jm = mb * L.koff * B
    return c, jp, jm, jp - jm, mi * L.kint * B


def _apply(L, n, B, R, J, Iv, scale):
    dn = np.zeros_like(n)
    np.add.at(dn, L.face, -J)
    has = L.recv >= 0
    np.add.at(dn, L.recv[has], Iv[has])
    return n + scale * dn, B + scale * (J - Iv), R + scale * (-J + Iv)


def _loads(L, n, B, R, mb, mi):
    """(L_n [nodes], L_R [pops], L_B [pops]) in s^-1."""
    c = n / L.V
    Ln = np.zeros_like(n)
    np.add.at(Ln, L.face, mb * L.kon * R / L.V[L.face])
    return Ln, mb * L.kon * c[L.face], mb * L.koff + mi * L.kint


def _affinity(L, n, B, R):
    """A = ln(c R/(K_d B)) per binding route (+-inf at B = 0 or R = 0)."""
    c = n / L.V
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log(c[L.face]) + np.log(R) - L.lnKd - np.log(B)


def _ratio(x):
    """(1 + x) log1p(x)/x, with the series 1 + x/2 - x^2/6 below |x| = 1e-6 (D152's form)."""
    small = np.abs(x) < 1e-6
    safe = np.where(small, 1.0, x)
    return np.where(small, 1.0 + x / 2.0 - x * x / 6.0, (1.0 + safe) * np.log1p(safe) / safe)


def node_increments(L, n, dn):
    return L.rt * (dn * (np.log(n / L.V) - 1.0) + (n + dn) * np.log1p(dn / n))


def pool_increments(L, a, d, mu0):
    out = np.empty_like(a)
    for k in range(a.size):
        out[k] = sr.pool_increment(float(a[k]), float(d[k]), float(L.S[k]), float(mu0[k]), L.rt)
    return out


def node_mu_bar(L, n, dn):
    return L.rt * (np.log(n / L.V) + _ratio(dn / n) - 1.0)


def pool_mu_bar(L, a, d, mu0):
    out = np.empty_like(a)
    for k in range(a.size):
        ak, dk, S = float(a[k]), float(d[k]), float(L.S[k])
        if ak > 0.0:
            out[k] = mu0[k] + L.rt * (math.log(ak / S) + float(_ratio(np.array(dk / ak))))
        elif dk > 0.0:
            out[k] = mu0[k] + L.rt * math.log(dk / S)
        else:
            out[k] = mu0[k]  # a = d = 0: unused (see the module's readings)
    return out


@dataclass
class HalfStep:
    """One half-step and its bookings. Arrays follow the layout's order: [nodes] or [pops]."""

    layout: Layout
    start: tuple  # (n, B, R)
    end: tuple  # the candidate (n', B', R'); idle components select the start bitwise
    accepted: tuple  # end if admitted, else start
    delta: tuple  # (dn, dB, dR) = nu dxi (0 in idle components)
    extent_binding: np.ndarray
    extent_internalisation: np.ndarray
    stages: list  # [(n, B, R)] at Y1, Y2, Y3
    stage_binding: np.ndarray  # [3, pops] J
    stage_forward: np.ndarray  # [3, pops] J+
    stage_reverse: np.ndarray  # [3, pops] J-
    stage_internalisation: np.ndarray  # [3, pops] I
    stage_affinity: np.ndarray  # [3, pops] A
    end_affinity: np.ndarray
    hL: np.ndarray  # [3, components]
    stage_condition_ok: bool
    positive_ok: bool
    finite_ok: bool
    admitted: bool
    component_class: list  # per component: "idle", "passive" or "mixed"
    non_reversing: np.ndarray  # [pops] bool
    branch: list  # [pops]: "node", "share", "quadrature", "off" or "idle"
    sign_margin: np.ndarray  # [pops] min |A| over the stages and the end
    heat_share: np.ndarray  # [pops] -share_b
    heat_quadrature: np.ndarray  # [pops]
    share_binding: np.ndarray  # [pops]
    share_internalisation: np.ndarray  # [pops]
    mu_bar: tuple  # (nodes, B, R)
    route_heat: np.ndarray  # [pops] the booked binding heat (mixed), else 0
    heat: np.ndarray  # [nodes] heat booked at each facing node (pJ)
    work: np.ndarray  # [pops] (pJ)
    delta_G: np.ndarray  # [components] (pJ), increment form
    delta_G_terms: np.ndarray  # [components]: the rounding scale of dG
    heat_terms: np.ndarray  # [components]: the rounding scale of H and W
    ledger_residual: np.ndarray  # [components]: dG + H - W

    def named(self, field):
        """A [nodes] or [pops] field as a dict by name."""
        arr = getattr(self, field)
        names = self.layout.nodes if len(arr) == len(self.layout.nodes) else self.layout.pops
        return {x: float(v) for x, v in zip(names, arr, strict=True)}


def half_step(world, n, B, R, h, mb=None, mi=None, theta=0.5):
    """One half-step of length h from (n, B, R) with multipliers mb, mi [pops] (default 1)."""
    L = Layout(world)
    n, B, R = (np.asarray(x, dtype=float).copy() for x in (n, B, R))
    npop = len(L.pops)
    mb = np.ones(npop) if mb is None else np.asarray(mb, dtype=float)
    mi = np.ones(npop) if mi is None else np.asarray(mi, dtype=float)
    declared_int = L.recv >= 0
    # Classes.
    comp_class = []
    for c in range(L.components):
        in_c = L.pop_component == c
        if not np.any(in_c & (mb > 0)) and not np.any(in_c & declared_int & (mi > 0)):
            comp_class.append("idle")
        elif np.any(in_c & declared_int & (mi > 0)):
            comp_class.append("mixed")
        else:
            comp_class.append("passive")
    pop_idle = np.array([comp_class[c] == "idle" for c in L.pop_component], dtype=bool)
    node_idle = np.array([comp_class[c] == "idle" for c in L.node_component], dtype=bool)
    mbe = np.where(pop_idle, 0.0, mb)
    mie = np.where(pop_idle | ~declared_int, 0.0, mi)
    # Stages.
    Y = [(n, B, R)]
    flux = []
    for s in range(3):
        c, jp, jm, J, Iv = _rates(L, *Y[s], mbe, mie)
        flux.append((jp, jm, J, Iv))
        if s == 0:
            Y.append(_apply(L, n, B, R, J, Iv, h))
        elif s == 1:
            J1, I1 = flux[0][2], flux[0][3]
            Y.append(_apply(L, n, B, R, (J1 + J) / 4.0, (I1 + Iv) / 4.0, h))
    xb = h * (flux[0][2] + flux[1][2] + 4.0 * flux[2][2]) / 6.0
    xi = h * (flux[0][3] + flux[1][3] + 4.0 * flux[2][3]) / 6.0
    dn = np.zeros_like(n)
    np.add.at(dn, L.face, -xb)
    np.add.at(dn, L.recv[declared_int], xi[declared_int])
    dB, dR = xb - xi, -xb + xi
    dn = np.where(node_idle, 0.0, dn)
    dB = np.where(pop_idle, 0.0, dB)
    dR = np.where(pop_idle, 0.0, dR)
    end = (np.where(node_idle, n, n + dn), np.where(pop_idle, B, B + dB),
           np.where(pop_idle, R, R + dR))
    # Checks.
    hL = np.zeros((3, L.components))
    pos, fin = True, True
    for s in range(3):
        Ln, LR, LB = _loads(L, *Y[s], mbe, mie)
        for c in range(L.components):
            if comp_class[c] == "idle":
                continue
            vals = [*Ln[L.node_component == c], *LR[L.pop_component == c],
                    *LB[L.pop_component == c]]
            hL[s, c] = h * max(vals) if vals else 0.0
    for state in (*Y, end):
        sn, sB, sR = state
        act_n, act_p = ~node_idle, ~pop_idle
        if not (np.all(np.isfinite(sn)) and np.all(np.isfinite(sB)) and np.all(np.isfinite(sR))):
            fin = False
        if np.any(sn[act_n] <= 0.0) or np.any(sB[act_p] < 0.0) or np.any(sR[act_p] < 0.0):
            pos = False
    fin = fin and bool(np.all(np.isfinite(hL)))
    stage_ok = bool(np.all(hL <= theta))
    admitted = stage_ok and pos and fin
    # Bookings.
    A_st = np.array([_affinity(L, *Y[s]) for s in range(3)])
    A_end = _affinity(L, *end)
    Js = np.array([f[2] for f in flux])
    sgn = np.sign(np.vstack([Js, A_end[None, :]]))
    nonrev = np.all(sgn == sgn[0], axis=0) & (sgn[0] != 0)
    with np.errstate(invalid="ignore"):
        margin = np.min(np.abs(np.vstack([A_st, A_end[None, :]])), axis=0)
        quad = h * L.rt * np.sum(np.array(WEIGHTS)[:, None] * Js * A_st, axis=0)
    quad = np.where(Js[0] == 0.0, np.where(np.all(Js == 0.0, axis=0), 0.0, quad), quad)
    gn = node_increments(L, n, dn)
    gB = pool_increments(L, B, dB, L.dG0)
    gR = pool_increments(L, R, dR, np.zeros(npop))
    mun = node_mu_bar(L, n, dn)
    muB = pool_mu_bar(L, B, dB, L.dG0)
    muR = pool_mu_bar(L, R, dR, np.zeros(npop))
    share_b = xb * (muB - muR - mun[L.face])
    recv0 = np.maximum(L.recv, 0)
    share_i = np.where(declared_int, xi * (muR + mun[recv0] - muB), 0.0)
    heat = np.zeros(len(L.nodes))
    work = np.zeros(npop)
    route_heat = np.zeros(npop)
    branch = []
    for k in range(npop):
        cls = comp_class[L.pop_component[k]]
        if cls == "idle":
            branch.append("idle")
        elif cls == "passive":
            branch.append("node")
        elif mbe[k] == 0.0:
            branch.append("off")  # the binding route books exactly 0; internalisation is work
            work[k] = share_i[k] + share_b[k]
        else:
            branch.append("share" if nonrev[k] else "quadrature")
            route_heat[k] = -share_b[k] if nonrev[k] else quad[k]
            np.add.at(heat, L.face[k], route_heat[k])
            work[k] = share_i[k] + share_b[k] + route_heat[k]
    # Passive-only components: H = -dG of each facing node's sub-system, no work.
    for i in range(len(L.nodes)):
        if comp_class[L.node_component[i]] != "passive":
            continue
        facing = L.face == i
        if np.any(facing):
            heat[i] = -(gn[i] + float(np.sum(gB[facing])) + float(np.sum(gR[facing])))
    dG = np.zeros(L.components)
    terms = np.zeros(L.components)
    hterms = np.zeros(L.components)
    for c in range(L.components):
        on, op = L.node_component == c, L.pop_component == c
        dG[c] = math.fsum([*gn[on], *gB[op], *gR[op]])
        terms[c] = math.fsum(np.abs(np.concatenate([gn[on], gB[op], gR[op]])))
        terms[c] += L.rt * math.fsum(np.abs(np.concatenate([dn[on], dB[op], dR[op]])))
        hterms[c] = math.fsum(np.abs(np.concatenate([
            xb[op] * np.abs(muB[op]), xb[op] * np.abs(muR[op]),
            np.abs(xb[op] * mun[L.face[op]]), np.abs(xi[op]) * np.abs(muB[op]),
            np.abs(xi[op]) * np.abs(muR[op]), np.abs(xi[op] * mun[recv0[op]]),
            np.where(np.isfinite(quad[op]), np.abs(quad[op]), 0.0)]))) + terms[c]
    residual = np.array([dG[c] + math.fsum(heat[L.node_component == c])
                         - math.fsum(work[L.pop_component == c]) for c in range(L.components)])
    return HalfStep(
        layout=L, start=(n, B, R), end=end,
        accepted=end if admitted else (n, B, R), delta=(dn, dB, dR),
        extent_binding=np.where(pop_idle, 0.0, xb),
        extent_internalisation=np.where(pop_idle, 0.0, xi),
        stages=Y, stage_binding=Js, stage_forward=np.array([f[0] for f in flux]),
        stage_reverse=np.array([f[1] for f in flux]),
        stage_internalisation=np.array([f[3] for f in flux]), stage_affinity=A_st,
        end_affinity=A_end, hL=hL, stage_condition_ok=stage_ok, positive_ok=pos,
        finite_ok=fin, admitted=admitted, component_class=comp_class, non_reversing=nonrev,
        branch=branch, sign_margin=margin, heat_share=-share_b, heat_quadrature=quad,
        share_binding=share_b, share_internalisation=share_i, mu_bar=(mun, muB, muR),
        route_heat=route_heat, heat=heat, work=work, delta_G=dG, delta_G_terms=terms,
        heat_terms=hterms, ledger_residual=residual)


def exact_delta_G(world, n, B, R, dn, dB, dR, digits=50):
    """dG per component in ``digits``-digit decimal arithmetic from the float start and change (the
    form for a rounding-level check of the engine's own change). a + d is rounded to ``digits``
    digits, a relative 1e-50 at the default; an unchanged row contributes exactly 0."""
    L = Layout(world)
    with localcontext() as ctx:
        ctx.prec = digits
        rt = Decimal(L.rt)

        def xlnx(x, s):
            return Decimal(0) if x == 0 else x * (x / s).ln()

        out = [Decimal(0)] * L.components
        for i in range(len(L.nodes)):
            if float(dn[i]) == 0.0:
                continue  # an unchanged row contributes exactly 0
            a, d, V = Decimal(float(n[i])), Decimal(float(dn[i])), Decimal(float(L.V[i]))
            b = a + d
            g = rt * (b * ((b / V).ln() - 1) - a * ((a / V).ln() - 1))
            out[L.node_component[i]] += g
        for k in range(len(L.pops)):
            S = Decimal(float(L.S[k]))
            dG0 = rt * (Decimal(float(L.koff[k])) / Decimal(float(L.kon[k]))).ln()
            for a, d, mu0 in ((B[k], dB[k], dG0), (R[k], dR[k], Decimal(0))):
                if float(d) == 0.0:
                    continue
                a, d = Decimal(float(a)), Decimal(float(d))
                out[L.pop_component[k]] += mu0 * d + rt * (xlnx(a + d, S) - xlnx(a, S))
        return out


@dataclass
class HalfStepRun:
    times: np.ndarray
    n: np.ndarray  # [steps + 1, nodes]
    B: np.ndarray
    R: np.ndarray
    heat: np.ndarray  # cumulative [steps + 1, nodes]
    work: np.ndarray  # cumulative [steps + 1, pops]
    bound_net: np.ndarray  # cumulative binding extent [steps + 1, pops]
    internalised: np.ndarray
    branches: list
    refused_at: object


def run_half_steps(world, h, count, multipliers=None, theta=0.5, state=None):
    """``count`` consecutive half-steps from the world's initial state (or ``state``), with
    nothing between them: a face-free world, where the engine's step is two half-steps per dt.
    ``multipliers(k) -> (mb, mi)`` for half-step k (default 1). Stops at the first refusal."""
    L = Layout(world)
    n, B, R = L.initial_state() if state is None else state
    npop, nn = len(L.pops), len(L.nodes)
    ns, Bs, Rs = [n.copy()], [B.copy()], [R.copy()]
    H, W = [np.zeros(nn)], [np.zeros(npop)]
    X, U = [np.zeros(npop)], [np.zeros(npop)]
    branches, refused = [], None
    for k in range(count):
        mb, mi = (None, None) if multipliers is None else multipliers(k)
        st = half_step(world, n, B, R, h, mb, mi, theta)
        if not st.admitted:
            refused = k
            break
        n, B, R = st.end
        ns.append(n.copy())
        Bs.append(B.copy())
        Rs.append(R.copy())
        H.append(H[-1] + st.heat)
        W.append(W[-1] + st.work)
        X.append(X[-1] + st.extent_binding)
        U.append(U[-1] + st.extent_internalisation)
        branches.append(st.branch)
    steps = len(ns) - 1
    return HalfStepRun(np.arange(steps + 1) * h, np.array(ns), np.array(Bs), np.array(Rs),
                       np.array(H), np.array(W), np.array(X), np.array(U), branches, refused)
