"""R-ode: the binding kinetics of cells.operator.site_occupancy@1 on finite site populations, an independent
reference (FR-3).

Written from docs/SITE_OCCUPANCY_DESIGN.md (Appendix A, with §2, §3.3, §4.3, §8 and §12's
as-built trace rule) and from the textbook law, without reading the operator, its fixtures or its
tests. numpy, scipy and the standard library, plus validation.coupling.piecewise_ode (another
independent reference's segment-by-segment integrator).

The model (Appendix A.1-A.3; @3's units: fmol, pL, mM = fmol/pL, s; RT in pJ/fmol is an input):
* nodes i (cells or finite outside nodes) of fixed volume V_i holding the free ligand n_i > 0,
  c_i = n_i / V_i;
* site populations k facing a node i(k), with S_k = alpha_k nu_k N_k / N_f accessible sites
  (N_f = 602,214,076 per fmol), free R_k and bound B_k, R_k + B_k = S_k;
* binding (Langmuir mass action; Langmuir 1918; Lauffenburger & Linderman 1993, ch. 2):
  J_k = m_b,k (k_on,k c_i(k) R_k - k_off,k B_k);
* site-conserving internalisation into a receiving node r(k) (Lauffenburger & Linderman 1993,
  ch. 3; Wiley & Cunningham 1981): I_k = m_i,k k_int,k B_k;
* dB/dt = J - I, dR/dt = -J + I, dn_i/dt = -sum_{k: i(k)=i} J_k + sum_{k: r(k)=i} I_k;
* the free energy (A.3): G_node,i = RT n_i (ln(n_i/V_i) - 1) and
  G_site,k = B [dG0_k + RT ln(B/S)] + RT R ln(R/S), dG0_k = RT ln(K_d,k / 1 mM), 0 ln 0 = 0;
* the heat and work along the exact path: dH/dt = RT sum_k J_k A_k with
  A_k = ln(c R/(K_d B)), and dW/dt = sum_k I_k (mu_r + mu_R - mu_B), with
  mu_r = RT ln(n_r/V_r), mu_R = RT ln(R/S), mu_B = dG0 + RT ln(B/S). The ledger is
  dG_node + dG_site + H - W = 0.

The heat's integrand is infinite at B = 0, the default start. It is integrated in a regular form:
the identity J ln(R/B) = I ln(R/B) - d/dt [R ln(R/S) + B ln(B/S)] (from dR/dt = -dB/dt = I - J)
gives
    H(t) = RT int_0^t sum_k [J_k ln(c_i/K_d,k) + I_k ln(R_k/B_k)] dt
           - RT sum_k [R ln(R/S) + B ln(B/S)]_0^t,
whose integrand is finite wherever B > 0 or I = 0 (I ln(R/B) = k_int B ln(R/B) -> 0 as B -> 0).
It is singular only at R = 0 with I > 0 (every site bound at the start); R is floored at the
smallest normal float inside that logarithm, a declared limit.

Integration: scipy's Radau (default) or DOP853, segment by segment between the multiplier
schedules' changes and the records (piecewise_ode), so every record is an integration end point.
The states are the amounts n_i, B_k and R_k themselves, each with its own absolute tolerance (a
fraction of its own scale), so trace rows and nearly saturated pools keep their relative accuracy;
the route extents and the energy integrals are extra states.

Sources: Langmuir I. J Am Chem Soc 1918;40:1361-1403. Lauffenburger DA, Linderman JJ. Receptors:
Models for Binding, Trafficking, and Signaling. Oxford University Press; 1993. Wiley HS,
Cunningham DD. Cell 1981;25:433-440. Hairer E, Wanner G. Solving Ordinary Differential Equations
II, 2nd ed. Springer; 1996 (Radau IIA).
"""

import math
from dataclasses import dataclass, field
from decimal import Decimal, localcontext

import numpy as np

from validation.coupling import piecewise_ode

N_F = 602_214_076.0  # sites per fmol (Avogadro's number x 1e-15), exact
TRACE_RATIO = 1e-6  # §4.3 and §12: the trace must be at most 1e-6 K_d of every population
TRACE_RELATIVE = 1e-12  # §12: every declared concentration at or above the trace, to 1e-12
TINY = float(np.finfo(float).tiny)


# ---------------------------------------------------------------- the world


@dataclass(frozen=True)
class Node:
    """A node (a cell or a finite outside node): its fixed volume (pL) and initial free ligand
    amount (fmol, > 0: an "absent" ligand is a trace, §4.3)."""

    volume_pL: float
    ligand_fmol: float


@dataclass(frozen=True)
class Population:
    """A site population facing one node.

    Sites: give ``sites_fmol`` (S) directly, or ``copies``, ``sites_per_copy`` and
    ``accessible_fraction`` (S = alpha nu N / N_f, §2.3's capacity form). Rates: k_on (mM^-1
    s^-1) and k_off (s^-1), both > 0; k_int >= 0 (s^-1) with a ``receiving`` node for
    site-conserving internalisation. Multipliers: piecewise-constant schedules
    ((t_start_s, m), ...) from 0, m >= 0."""

    facing: str
    k_on_per_mM_per_s: float
    k_off_per_s: float
    sites_fmol: float = math.nan
    copies: float = math.nan
    sites_per_copy: float = math.nan
    accessible_fraction: float = 1.0
    initial_occupancy: float = 0.0
    k_int_per_s: float = 0.0
    receiving: object = None
    binding_schedule: tuple = ((0.0, 1.0),)
    internalisation_schedule: tuple = ((0.0, 1.0),)

    @property
    def S(self):
        if math.isfinite(self.sites_fmol):
            return float(self.sites_fmol)
        return self.accessible_fraction * self.sites_per_copy * self.copies / N_F

    @property
    def K_d(self):
        return self.k_off_per_s / self.k_on_per_mM_per_s


@dataclass(frozen=True)
class World:
    """One ligand, its nodes and the site populations binding it. ``trace_mM`` is the ligand's
    declared trace (§2.1, §4.3); NaN declares none (and the trace rule is then not checked)."""

    rt_pJ_per_fmol: float
    nodes: dict
    populations: dict = field(default_factory=dict)
    trace_mM: float = math.nan


def _finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def _check_schedule(name, schedule):
    starts = [a for a, _ in schedule]
    if not schedule or starts[0] != 0.0 or starts != sorted(set(starts)):
        raise ValueError(f"{name}: a schedule starts at 0 and strictly increases")
    if any(not (_finite(m) and m >= 0.0) for _, m in schedule):
        raise ValueError(f"{name}: multipliers are finite and >= 0")


def check_world(world, *, trace_rule=True):
    """Refuse an inadmissible world: the law's domain (§2.2: k_on, k_off > 0, k_int >= 0;
    S > 0; alpha in (0, 1]; theta0 in [0, 1]; n > 0; V > 0) and, with ``trace_rule`` (the
    default), §12's as-built trace rule: every node's initial concentration is at or above the
    declared trace (to 1e-12 relative), and the trace is at most 1e-6 K_d of every population.
    ``trace_rule=False`` admits a world the engine would refuse, for reference-side studies."""
    w = world
    if not (_finite(w.rt_pJ_per_fmol) and w.rt_pJ_per_fmol > 0):
        raise ValueError("RT (pJ/fmol) is finite and > 0")
    if not w.nodes:
        raise ValueError("a world has at least one node")
    for name, node in w.nodes.items():
        if not (_finite(node.volume_pL) and node.volume_pL > 0):
            raise ValueError(f"node {name}: a positive volume")
        if not (_finite(node.ligand_fmol) and node.ligand_fmol > 0):
            raise ValueError(f"node {name}: a positive free ligand amount (absent is a trace)")
    for name, p in w.populations.items():
        if p.facing not in w.nodes:
            raise ValueError(f"population {name}: no node {p.facing}")
        if not (_finite(p.k_on_per_mM_per_s) and p.k_on_per_mM_per_s > 0
                and _finite(p.k_off_per_s) and p.k_off_per_s > 0):
            raise ValueError(f"population {name}: k_on and k_off are finite and > 0 (§2.2)")
        if not (_finite(p.k_int_per_s) and p.k_int_per_s >= 0):
            raise ValueError(f"population {name}: k_int is finite and >= 0")
        if p.k_int_per_s > 0 and p.receiving not in w.nodes:
            raise ValueError(f"population {name}: internalisation needs a receiving node")
        if not math.isfinite(p.sites_fmol):
            if not (_finite(p.copies) and p.copies > 0 and _finite(p.sites_per_copy)
                    and p.sites_per_copy > 0):
                raise ValueError(f"population {name}: give S, or copies and sites per copy")
            if not (_finite(p.accessible_fraction) and 0 < p.accessible_fraction <= 1):
                raise ValueError(f"population {name}: the accessible fraction lies in (0, 1]")
        if not (_finite(p.S) and p.S > 0):
            raise ValueError(f"population {name}: S > 0")
        if not (_finite(p.initial_occupancy) and 0 <= p.initial_occupancy <= 1):
            raise ValueError(f"population {name}: the initial occupancy lies in [0, 1]")
        _check_schedule(f"population {name} binding", p.binding_schedule)
        _check_schedule(f"population {name} internalisation", p.internalisation_schedule)
    if trace_rule and math.isfinite(w.trace_mM):
        if not w.trace_mM > 0:
            raise ValueError("the declared trace is > 0")
        for name, node in w.nodes.items():
            c = node.ligand_fmol / node.volume_pL
            if c < w.trace_mM * (1.0 - TRACE_RELATIVE):
                raise ValueError(f"node {name}: concentration {c:.6g} mM below the declared "
                                 f"trace {w.trace_mM:.6g} mM (§4.3, §12)")
        for name, p in w.populations.items():
            if w.trace_mM > TRACE_RATIO * p.K_d:
                raise ValueError(f"population {name}: the trace {w.trace_mM:.6g} mM exceeds "
                                 f"1e-6 K_d = {TRACE_RATIO * p.K_d:.6g} mM (ratio "
                                 f"{w.trace_mM / p.K_d:.3g}; §4.3, §12)")


def schedule_value(schedule, t0, t1):
    """The piecewise-constant multiplier on (t0, t1) (segments never straddle a change)."""
    mid = 0.5 * (t0 + t1)
    value = schedule[0][1]
    for start, m in schedule:
        if start > mid:
            break
        value = m
    return float(value)


def breakpoints(world, t_end, record=()):
    points = {0.0, float(t_end), *(float(t) for t in record)}
    for p in world.populations.values():
        points |= {a for a, _ in (*p.binding_schedule, *p.internalisation_schedule)}
    return sorted(x for x in points if 0.0 <= x <= t_end)


# ---------------------------------------------------------------- free energies


def _xlnx_over(x, s):
    """x ln(x/s) with 0 ln 0 = 0."""
    return 0.0 if x == 0.0 else x * math.log(x / s)


def node_free_energy(n, V, rt):
    """G_node = RT n (ln(n/V) - 1) (pJ)."""
    return rt * n * (math.log(n / V) - 1.0)


def site_free_energy(B, R, S, dG0, rt):
    """G_site = B [dG0 + RT ln(B/S)] + RT R ln(R/S) (pJ), 0 ln 0 = 0 (A.3)."""
    return B * dG0 + rt * (_xlnx_over(B, S) + _xlnx_over(R, S))


def standard_binding_energy(population, rt):
    """dG0 = RT ln(K_d / 1 mM) (pJ/fmol)."""
    return rt * math.log(population.K_d)


def node_increment(a, d, V, rt):
    """G_node(a + d) - G_node(a), stable for small d: RT [d (ln(a/V) - 1) + (a + d) log1p(d/a)]."""
    return rt * (d * (math.log(a / V) - 1.0) + (a + d) * math.log1p(d / a))


def pool_increment(a, d, S, mu0, rt):
    """g(a + d) - g(a) for a site pool, g(x) = mu0 x + RT x ln(x/S) (§3.3's stable form; the
    a = 0 branch is RT xlogy(d, d/S))."""
    if a == 0.0:
        return mu0 * d + (0.0 if d == 0.0 else rt * d * math.log(d / S))
    return mu0 * d + rt * (d * math.log(a / S) + (a + d) * math.log1p(d / a))


def exact_free_energy_change(world, start, end, digits=50):
    """dG_node + dG_site between two states, in ``digits``-digit decimal arithmetic from exact
    float inputs: dict(total, nodes, sites) of Decimals. ``start`` and ``end`` are
    dict(n={node: fmol}, B={pop: fmol}, R={pop: fmol})."""
    w = world
    with localcontext() as ctx:
        ctx.prec = digits
        rt = Decimal(w.rt_pJ_per_fmol)

        def xlnx(x, s):
            return Decimal(0) if x == 0 else x * (x / s).ln()

        nodes = {}
        for name, node in w.nodes.items():
            V = Decimal(node.volume_pL)
            a, b = Decimal(start["n"][name]), Decimal(end["n"][name])
            nodes[name] = rt * (b * ((b / V).ln() - 1) - a * ((a / V).ln() - 1))
        sites = {}
        for name, p in w.populations.items():
            S = Decimal(p.S)
            dG0 = rt * (Decimal(p.k_off_per_s) / Decimal(p.k_on_per_mM_per_s)).ln()

            def g(B, R, S=S, dG0=dG0):
                B, R = Decimal(B), Decimal(R)
                return B * dG0 + rt * (xlnx(B, S) + xlnx(R, S))

            sites[name] = g(end["B"][name], end["R"][name]) - g(start["B"][name],
                                                                  start["R"][name])
        return dict(total=sum(nodes.values(), Decimal(0)) + sum(sites.values(), Decimal(0)),
                    nodes=nodes, sites=sites)


# ---------------------------------------------------------------- R-ode


class _Model:
    def __init__(self, world, rtol, atol_fraction):
        self.w = w = world
        self.nodes = list(w.nodes)
        self.ni = {name: i for i, name in enumerate(self.nodes)}
        self.pops = list(w.populations)
        self.rt = w.rt_pJ_per_fmol
        nn, npop = len(self.nodes), len(self.pops)
        self.V = np.array([w.nodes[x].volume_pL for x in self.nodes])
        self.S = np.array([w.populations[p].S for p in self.pops])
        self.kon = np.array([w.populations[p].k_on_per_mM_per_s for p in self.pops])
        self.koff = np.array([w.populations[p].k_off_per_s for p in self.pops])
        self.kint = np.array([w.populations[p].k_int_per_s for p in self.pops])
        self.Kd = self.koff / self.kon
        self.lnKd = np.log(self.Kd)
        self.dG0 = self.rt * self.lnKd
        self.face = np.array([self.ni[w.populations[p].facing] for p in self.pops], dtype=int)
        self.recv = np.array([self.ni[w.populations[p].receiving]
                              if w.populations[p].receiving is not None else -1
                              for p in self.pops], dtype=int)
        # Layout: n [nodes], B, R, xi, U, H_reg, W [pops each]: the regular part of each
        # population's heat and its work, so heat is reported per facing node and work per
        # population, as the engine books them.
        self.iN = slice(0, nn)
        self.iB = slice(nn, nn + npop)
        self.iR = slice(nn + npop, nn + 2 * npop)
        self.iX = slice(nn + 2 * npop, nn + 3 * npop)
        self.iU = slice(nn + 3 * npop, nn + 4 * npop)
        self.iH = slice(nn + 4 * npop, nn + 5 * npop)
        self.iW = slice(nn + 5 * npop, nn + 6 * npop)
        self.size = nn + 6 * npop
        n0 = np.array([w.nodes[x].ligand_fmol for x in self.nodes])
        theta0 = np.array([w.populations[p].initial_occupancy for p in self.pops])
        B0 = theta0 * self.S
        R0 = self.S - B0
        y0 = np.zeros(self.size)
        y0[self.iN], y0[self.iB], y0[self.iR] = n0, B0, R0
        self.y0 = y0
        # Absolute tolerances: a fraction of each state's own scale.
        scale = np.zeros(self.size)
        scale[self.iN] = n0
        scale[self.iB] = self.S
        scale[self.iR] = self.S
        material = max(float(n0.max()), float(self.S.max()) if npop else 0.0)
        scale[self.iX] = self.S if npop else 1.0
        scale[self.iU] = material
        scale[self.iH] = scale[self.iW] = self.rt * material
        self.atol = rtol * atol_fraction * scale

    def controls(self, t0, t1):
        w = self.w
        mb = np.array([schedule_value(w.populations[p].binding_schedule, t0, t1)
                       for p in self.pops])
        mi = np.array([schedule_value(w.populations[p].internalisation_schedule, t0, t1)
                       for p in self.pops])
        return mb, mi

    def rates(self, y, mb, mi):
        n, B, R = y[self.iN], y[self.iB], y[self.iR]
        c = n / self.V
        J = mb * (self.kon * c[self.face] * R - self.koff * B)
        Iv = mi * self.kint * B
        return n, B, R, c, J, Iv

    def rhs(self, t, y, mb, mi):
        n, B, R, c, J, Iv = self.rates(y, mb, mi)
        out = np.zeros(self.size)
        dn = np.zeros(len(self.nodes))
        np.add.at(dn, self.face, -J)
        has = self.recv >= 0
        np.add.at(dn, self.recv[has], Iv[has])
        out[self.iN] = dn
        out[self.iB] = J - Iv
        out[self.iR] = -J + Iv
        out[self.iX] = J
        out[self.iU] = Iv
        lnc = np.log(c)
        # The regular part of the heat, and the work (R floored inside the logs, see above).
        with np.errstate(divide="ignore", invalid="ignore"):
            lnRB = np.where(Iv > 0.0, np.log(np.maximum(R, TINY)) - np.log(np.maximum(B, TINY)),
                            0.0)
        out[self.iH] = self.rt * (J * (lnc[self.face] - self.lnKd) + Iv * lnRB)
        lnc_r = np.where(self.recv >= 0, lnc[np.maximum(self.recv, 0)], 0.0)
        out[self.iW] = Iv * (self.rt * lnc_r - self.dG0 + self.rt * lnRB)
        return out

    def boundary(self, y):
        """RT [R ln(R/S) + B ln(B/S)] per population (pJ)."""
        B, R = y[self.iB], y[self.iR]
        return np.array([self.rt * (_xlnx_over(float(b), float(s)) + _xlnx_over(float(r),
                                                                                  float(s)))
                         for b, r, s in zip(B, R, self.S, strict=True)])

    def population_heat(self, y):
        """Each population's heat RT int J A dt along the path (pJ): the regular integral minus
        the boundary term's change."""
        return y[self.iH] - (self.boundary(y) - self.boundary(self.y0))

    def free_energy(self, y):
        n, B, R = y[self.iN], y[self.iB], y[self.iR]
        g_nodes = {x: node_free_energy(float(n[i]), float(self.V[i]), self.rt)
                   for i, x in enumerate(self.nodes)}
        g_sites = {p: site_free_energy(float(B[k]), float(R[k]), float(self.S[k]),
                                       float(self.dG0[k]), self.rt)
                   for k, p in enumerate(self.pops)}
        return g_nodes, g_sites


class SiteRun:
    """One R-ode run. ``at[t]`` is the record at each requested time (see the usage note);
    ``observe(t)`` gives one anywhere by re-integration from the last stored step."""

    def __init__(self, model, run, record, points):
        self.model, self.run, self.points = model, run, np.array(points)
        self.steps = run.steps
        self.t_end = run.t_end
        self.at = {t: self.observe(t) for t in record}

    def _sides(self, t):
        pts = self.points
        j = int(np.searchsorted(pts, t, side="right"))
        right = (pts[j - 1], pts[j]) if j < len(pts) else (pts[-2], pts[-1])
        k = int(np.searchsorted(pts, t, side="left"))
        left = (pts[k - 1], pts[k]) if k >= 1 else right
        return left, right

    def observe(self, t):
        m = self.model
        y = self.run.state(t)
        left, right = self._sides(t)
        mb_r, mi_r = m.controls(*right)
        mb_l, mi_l = m.controls(*left)
        n, B, R, c, J, Iv = m.rates(y, mb_r, mi_r)
        _, _, _, _, J_l, I_l = m.rates(y, mb_l, mi_l)
        heat_pop = m.population_heat(y)
        work_pop = y[m.iW]
        heat_node = np.zeros(len(m.nodes))
        np.add.at(heat_node, m.face, heat_pop)
        heat = math.fsum(heat_pop)
        work = math.fsum(work_pop)
        n0, B0, R0 = m.y0[m.iN], m.y0[m.iB], m.y0[m.iR]
        dG_nodes = {x: node_increment(float(n0[i]), float(n[i] - n0[i]), float(m.V[i]), m.rt)
                    for i, x in enumerate(m.nodes)}
        dG_sites = {p: pool_increment(float(B0[k]), float(B[k] - B0[k]), float(m.S[k]),
                                      float(m.dG0[k]), m.rt)
                    + pool_increment(float(R0[k]), float(R[k] - R0[k]), float(m.S[k]), 0.0, m.rt)
                    for k, p in enumerate(m.pops)}
        dG = math.fsum([*dG_nodes.values(), *dG_sites.values()])
        rec = dict(
            t=t,
            n_fmol={x: float(n[i]) for i, x in enumerate(m.nodes)},
            c_mM={x: float(c[i]) for i, x in enumerate(m.nodes)},
            B_fmol={p: float(B[k]) for k, p in enumerate(m.pops)},
            R_fmol={p: float(R[k]) for k, p in enumerate(m.pops)},
            occupancy={p: float(B[k] / m.S[k]) for k, p in enumerate(m.pops)},
            bound_net_fmol={p: float(y[m.iX][k]) for k, p in enumerate(m.pops)},
            internalised_fmol={p: float(y[m.iU][k]) for k, p in enumerate(m.pops)},
            binding_rate_fmol_per_s={p: float(J[k]) for k, p in enumerate(m.pops)},
            binding_rate_left_fmol_per_s={p: float(J_l[k]) for k, p in enumerate(m.pops)},
            internalisation_rate_fmol_per_s={p: float(Iv[k]) for k, p in enumerate(m.pops)},
            internalisation_rate_left_fmol_per_s={p: float(I_l[k])
                                                  for k, p in enumerate(m.pops)},
            heat_pJ=heat,
            work_pJ=work,
            heat_by_node_pJ={x: float(heat_node[i]) for i, x in enumerate(m.nodes)},
            heat_by_population_pJ={p: float(heat_pop[k]) for k, p in enumerate(m.pops)},
            work_by_population_pJ={p: float(work_pop[k]) for k, p in enumerate(m.pops)},
            free_energy_change_pJ=dG,
            node_free_energy_change_pJ=dG_nodes,
            site_free_energy_change_pJ=dG_sites,
            closure_pJ=work - heat - dG,
            moiety_residual_fmol={p: float(B[k] + R[k] - m.S[k]) for k, p in enumerate(m.pops)},
        )
        total0 = float(np.sum(m.y0[m.iN]) + np.sum(m.y0[m.iB]))
        rec["material_residual_fmol"] = float(np.sum(n) + np.sum(B)) - total0
        rec["material_total_fmol"] = total0
        return rec


def integrate(world, t_end, *, record=(), rtol=1e-12, method="Radau", atol_fraction=1e-6,
              trace_rule=True, max_step=math.inf):
    """Integrate the binding kinetics (A.2) from 0 to t_end; returns a SiteRun.

    ``rtol`` and ``method`` are scipy's (Radau, or DOP853 for non-stiff worlds); each state's
    absolute tolerance is rtol x atol_fraction x its scale (n_i(0) for a node, S for a pool)."""
    check_world(world, trace_rule=trace_rule)
    if not (_finite(t_end) and t_end > 0):
        raise ValueError("t_end is finite and > 0")
    record = tuple(sorted({float(t) for t in record}))
    if any(not 0.0 <= t <= t_end for t in record):
        raise ValueError("records lie in [0, t_end]")
    model = _Model(world, rtol, atol_fraction)
    points = breakpoints(world, t_end, record)

    def segment(t0, t1):
        mb, mi = model.controls(t0, t1)
        return (lambda t, y: model.rhs(t, y, mb, mi)), None

    run = piecewise_ode.Run(segment, model.y0, points, rtol=rtol, atol=model.atol,
                            method=method, max_step=max_step)
    return SiteRun(model, run, record, points)


def compare(a, b, record):
    """Max |a - b| per observable over the records of two runs of one world, each in its own
    units: n (fmol), B, R (fmol), occupancy, J, I (fmol/s), U (fmol), heat, work (pJ)."""
    out = dict(n=0.0, B=0.0, R=0.0, occupancy=0.0, J=0.0, I=0.0, U=0.0, heat=0.0, work=0.0)
    keys = dict(n="n_fmol", B="B_fmol", R="R_fmol", occupancy="occupancy",
                J="binding_rate_fmol_per_s", I="internalisation_rate_fmol_per_s",
                U="internalised_fmol")
    for t in record:
        ra, rb = a.at[t], b.at[t]
        for k, key in keys.items():
            for x in ra[key]:
                out[k] = max(out[k], abs(ra[key][x] - rb[key][x]))
        out["heat"] = max(out["heat"], abs(ra["heat_pJ"] - rb["heat_pJ"]))
        out["work"] = max(out["work"], abs(ra["work_pJ"] - rb["work_pJ"]))
    return out


def floor(world, t_end, record, *, rtol=1e-12, method="Radau", factor=100.0, **kw):
    """The numerical floor of a run: (run, tight run, differences), the tight run at
    rtol / factor (method unchanged), the differences estimating the run's own error."""
    run = integrate(world, t_end, record=record, rtol=rtol, method=method, **kw)
    tight = integrate(world, t_end, record=record, rtol=rtol / factor, method=method, **kw)
    return run, tight, compare(run, tight, record)


def background_guard(world, t_end, record, *, factor=1e3, **kw):
    """Q5's background guard on the reference side: the world as declared, and the same world with
    the trace (and every node whose concentration equals it) lowered by ``factor``; returns
    (run, lowered run, differences). The worlds must satisfy the trace rule."""
    w = world
    if not math.isfinite(w.trace_mM):
        raise ValueError("the background guard needs a declared trace")
    lowered_nodes = {}
    for name, node in w.nodes.items():
        c = node.ligand_fmol / node.volume_pL
        if abs(c - w.trace_mM) <= TRACE_RELATIVE * w.trace_mM:
            node = Node(node.volume_pL, node.ligand_fmol / factor)
        lowered_nodes[name] = node
    lowered = World(w.rt_pJ_per_fmol, lowered_nodes, w.populations, w.trace_mM / factor)
    a = integrate(world, t_end, record=record, **kw)
    b = integrate(lowered, t_end, record=record, **kw)
    return a, b, compare(a, b, record)
