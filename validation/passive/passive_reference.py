"""The passive permeation law's closed-pair reference (cells.route.passive_neutral_permeation@1), an
independent reference.

Written from docs/ARCHITECTURE.md ("Transport laws by physical contract") and
docs/INNER_MODEL_V4_DESIGN.md §11 (with §10.2 and §13.6, which change neither the equations nor
the admissible worlds), and from Fick's law, without reading the engine. numpy, scipy and the
standard library, plus validation.coupling.piecewise_ode (another independent reference's
segment-by-segment integrator).

The law (§11): the constant-field route at valence 0, which is Fick's law. For a neutral species
moving between compartments a and b (two cells joined by a junction, or a cell and a face-free
node), with every other wall impermeant to it and the species absent from (a trace in) any bath
behind those walls, so the bath never enters:
    J = 1e15 PA (c_a - c_b)    (fmol/s, from a to b),
with PA = P A in m^3/s (for a junction P_s A_e times its gate and availability), c = n/V in mM
(= fmol/pL = mol/m^3) and the factor 1e15 fmol/mol. The constant-field flux
PA psi(x)(c_a - c_b e^-x) at x = z F dV/RT = 0 is exactly this (psi(0) = 1).

The closed pair at fixed volumes V_a, V_b (pL), with N = n_a + n_b conserved:
    dn_a/dt = -J,  dn_b/dt = +J,  c_a - c_b = (c_a0 - c_b0) e^(-k t),
    k = 1e15 PA (1/V_a + 1/V_b),  n_x(t) = n_x0 e^(-k t) - n_x,inf expm1(-k t),
    n_x,inf = V_x N/(V_a + V_b) (equal concentrations, equal chemical potentials).
Each compartment is evaluated from its own expression, a sum of two non-negative terms, so a trace
side keeps its digits; it is never formed as N - n_a.

Energy: G = RT sum_x n_x (ln(n_x/V_x) - 1) (pJ; RT = 1e-3 R T in pJ/fmol, an input; the standard
potential is common to both sides and cancels in a closed pair). The heat of the exact path is
    dH/dt = RT J ln(c_a/c_b) >= 0,   so   H(t) = G(0) - G(t),   W = 0
(no externally supplied work; the free-energy decrease is dissipated, de Groot & Mazur 1962;
Keener & Sneyd 2009 ch. 2).

The increment form of a change d from a > 0 (D152's stable form):
    g(a + d) - g(a) = RT [d (ln(a/V) - 1) + (a + d) log1p(d/a)].

Sources: Fick A. Ann Phys 1855;170:59-86. Goldman DE. J Gen Physiol 1943;27:37-60 (the
constant-field flux, here at valence 0). de Groot SR, Mazur P. Non-Equilibrium Thermodynamics.
North-Holland; 1962. Keener J, Sneyd J. Mathematical Physiology I, 2nd ed. Springer; 2009.
"""

import math
from dataclasses import dataclass, field
from decimal import Decimal, localcontext

import numpy as np

from validation.coupling import piecewise_ode

FMOL_PER_MOL = 1e15


# ---------------------------------------------------------------- the closed pair


def rate_constant(PA_m3_per_s, V_a_pL, V_b_pL):
    """k = 1e15 PA (1/V_a + 1/V_b) (1/s): the relaxation rate of the concentration difference."""
    return FMOL_PER_MOL * PA_m3_per_s * (1.0 / V_a_pL + 1.0 / V_b_pL)


def _check_pair(n_a0, n_b0, V_a, V_b, PA):
    if not all(math.isfinite(x) and x > 0 for x in (n_a0, n_b0, V_a, V_b)):
        raise ValueError("amounts (a trace at the least) and volumes are finite and > 0")
    if not (math.isfinite(PA) and PA >= 0):
        raise ValueError("PA is finite and >= 0")


def closed_pair(t, n_a0, n_b0, V_a, V_b, PA, rt=None):
    """The closed pair at time t (s): dict(n_a, n_b, c_a, c_b, flux_fmol_per_s (a to b), k,
    c_eq, delta_a (n_a - n_a0, formed stably), heat_pJ, heat_scale_pJ (its rounding scale) and
    work_pJ (with rt))."""
    _check_pair(n_a0, n_b0, V_a, V_b, PA)
    k = rate_constant(PA, V_a, V_b)
    N = n_a0 + n_b0
    a_inf, b_inf = V_a * N / (V_a + V_b), V_b * N / (V_a + V_b)
    e, em1 = math.exp(-k * t), -math.expm1(-k * t)  # e^-kt, 1 - e^-kt
    n_a = n_a0 * e + a_inf * em1
    n_b = n_b0 * e + b_inf * em1
    c_a0, c_b0 = n_a0 / V_a, n_b0 / V_b
    # n_a,inf - n_a0 = V_a V_b (c_b0 - c_a0)/(V_a + V_b): the change, from the concentrations.
    delta_a = V_a * V_b / (V_a + V_b) * (c_b0 - c_a0) * em1
    out = dict(n_a=n_a, n_b=n_b, c_a=n_a / V_a, c_b=n_b / V_b, k=k, c_eq=N / (V_a + V_b),
               flux_fmol_per_s=FMOL_PER_MOL * PA * (c_a0 - c_b0) * e, delta_a=delta_a)
    if rt is not None:
        out["heat_pJ"] = 0.0 - (increment(n_a0, delta_a, V_a, rt)
                                + increment(n_b0, -delta_a, V_b, rt))  # 0.0 - x: no -0.0
        # The heat's rounding scale: near equal starts the heat is second order in the gradient
        # while its terms are first order, so its float error is a few eps x this, not x heat.
        out["heat_scale_pJ"] = (increment_terms(n_a0, delta_a, V_a, rt)
                                + increment_terms(n_b0, -delta_a, V_b, rt))
        out["work_pJ"] = 0.0
    return out


def exact_closed_pair(t, n_a0, n_b0, V_a, V_b, PA, rt, digits=50):
    """The closed pair in ``digits``-digit decimal arithmetic from exact float inputs:
    dict(n_a, n_b, flux, heat) as Decimals (the heat as G(0) - G(t), every term exact)."""
    _check_pair(n_a0, n_b0, V_a, V_b, PA)
    with localcontext() as ctx:
        ctx.prec = digits
        t, na0, nb0, Va, Vb, PA, rt = (Decimal(float(x)) for x in (t, n_a0, n_b0, V_a, V_b, PA,
                                                                   rt))
        k = Decimal(FMOL_PER_MOL) * PA * (1 / Va + 1 / Vb)
        e = (-k * t).exp()
        N = na0 + nb0
        n_a = na0 * e + Va * N / (Va + Vb) * (1 - e)
        n_b = nb0 * e + Vb * N / (Va + Vb) * (1 - e)

        def g(n, V):
            return rt * n * ((n / V).ln() - 1)

        heat = g(na0, Va) + g(nb0, Vb) - g(n_a, Va) - g(n_b, Vb)
        flux = Decimal(FMOL_PER_MOL) * PA * (na0 / Va - nb0 / Vb) * e
        return dict(n_a=n_a, n_b=n_b, flux=flux, heat=heat)


def equilibrium(n_a0, n_b0, V_a, V_b, rt=None):
    """The closed pair's equilibrium: equal concentrations N/(V_a + V_b); with rt, the total heat
    of the relaxation G(0) - G(eq)."""
    N = n_a0 + n_b0
    c = N / (V_a + V_b)
    out = dict(c_eq=c, n_a=c * V_a, n_b=c * V_b)
    if rt is not None:
        d = V_a * V_b / (V_a + V_b) * (n_b0 / V_b - n_a0 / V_a)
        out["heat_pJ"] = -(increment(n_a0, d, V_a, rt) + increment(n_b0, -d, V_b, rt))
    return out


# ---------------------------------------------------------------- free energy, per step


def free_energy(n, V, rt):
    """g(n) = RT n (ln(n/V) - 1) (pJ)."""
    return rt * n * (math.log(n / V) - 1.0)


def increment(a, d, V, rt):
    """g(a + d) - g(a) = RT [d (ln(a/V) - 1) + (a + d) log1p(d/a)], a > 0 (stable)."""
    return rt * (d * (math.log(a / V) - 1.0) + (a + d) * math.log1p(d / a))


def increment_terms(a, d, V, rt):
    """The sum of the absolute values of the increment's terms: its rounding scale."""
    return rt * (abs(d * (math.log(a / V) - 1.0)) + abs((a + d) * math.log1p(d / a)))


def step_heat(starts, deltas, volumes, rt):
    """The exact heat of one step of a closed sub-system: -(sum of the compartments' free-energy
    increments) from the engine's own start amounts and changes (fmol), with its rounding scale:
    (heat_pJ, scale_pJ). A step that moves material through the passive law alone books this as
    heat and no work (§11's exact booking)."""
    heat = -math.fsum(increment(a, d, V, rt) for a, d, V in zip(starts, deltas, volumes,
                                                                strict=True))
    scale = math.fsum(increment_terms(a, d, V, rt) for a, d, V in zip(starts, deltas, volumes,
                                                                     strict=True))
    return heat, scale


def exact_step_heat(starts, deltas, volumes, rt, digits=50):
    """The same in ``digits``-digit decimal arithmetic (a + d formed to ``digits`` digits, a
    relative 1e-50); an unchanged compartment contributes exactly 0."""
    with localcontext() as ctx:
        ctx.prec = digits
        rt_d = Decimal(float(rt))
        total = Decimal(0)
        for a, d, V in zip(starts, deltas, volumes, strict=True):
            if float(d) == 0.0:
                continue
            a, d, V = Decimal(float(a)), Decimal(float(d)), Decimal(float(V))
            b = a + d
            total -= rt_d * (b * ((b / V).ln() - 1) - a * ((a / V).ln() - 1))
        return total


# ---------------------------------------------------------------- R-ode, any graph of compartments


@dataclass(frozen=True)
class Compartment:
    """A closed compartment of fixed volume (pL) holding the species (fmol, > 0: a trace at the
    least)."""

    volume_pL: float
    amount_fmol: float


@dataclass(frozen=True)
class Route:
    """A passive route between two compartments, PA in m^3/s (positive flux from ``a`` to ``b``)."""

    a: str
    b: str
    PA_m3_per_s: float


@dataclass(frozen=True)
class World:
    rt_pJ_per_fmol: float
    compartments: dict
    routes: dict = field(default_factory=dict)


def check_world(world):
    w = world
    if not (math.isfinite(w.rt_pJ_per_fmol) and w.rt_pJ_per_fmol > 0):
        raise ValueError("RT is finite and > 0")
    for name, c in w.compartments.items():
        if not (math.isfinite(c.volume_pL) and c.volume_pL > 0 and math.isfinite(c.amount_fmol)
                and c.amount_fmol > 0):
            raise ValueError(f"compartment {name}: a positive volume and amount")
    for name, r in w.routes.items():
        if r.a not in w.compartments or r.b not in w.compartments or r.a == r.b:
            raise ValueError(f"route {name} joins two distinct compartments")
        if not (math.isfinite(r.PA_m3_per_s) and r.PA_m3_per_s >= 0):
            raise ValueError(f"route {name}: PA is finite and >= 0")


class PassiveRun:
    """``at[t]``: dict(n_fmol, c_mM, transferred_fmol (per route, a to b), flux_fmol_per_s,
    heat_pJ (the integrated dissipation), free_energy_change_pJ (increment form), closure_pJ
    (H + dG: zero for the exact path, since no work is supplied), material_residual_fmol)."""

    def __init__(self, world, run, record, names, routes):
        self.world, self.run, self.names, self.route_names = world, run, names, routes
        self.steps = run.steps
        self.at = {t: self.observe(t) for t in record}

    def observe(self, t):
        w = self.world
        y = self.run.state(t)
        nc = len(self.names)
        n = y[:nc]
        V = np.array([w.compartments[x].volume_pL for x in self.names])
        n0 = np.array([w.compartments[x].amount_fmol for x in self.names])
        rt = w.rt_pJ_per_fmol
        c = n / V
        flux = {r: FMOL_PER_MOL * w.routes[r].PA_m3_per_s
                * (c[self.names.index(w.routes[r].a)] - c[self.names.index(w.routes[r].b)])
                for r in self.route_names}
        dG = math.fsum(increment(float(n0[i]), float(n[i] - n0[i]), float(V[i]), rt)
                       for i in range(nc))
        heat = float(y[-1])
        return dict(t=t, n_fmol={x: float(n[i]) for i, x in enumerate(self.names)},
                    c_mM={x: float(c[i]) for i, x in enumerate(self.names)},
                    transferred_fmol={r: float(y[nc + j]) for j, r in enumerate(self.route_names)},
                    flux_fmol_per_s=flux, heat_pJ=heat, work_pJ=0.0,
                    free_energy_change_pJ=dG, closure_pJ=heat + dG,
                    material_residual_fmol=float(np.sum(n) - np.sum(n0)))


def integrate(world, t_end, *, record=(), rtol=1e-12, method="Radau", atol_fraction=1e-6):
    """Integrate the passive law on any graph of closed compartments, with each route's transferred
    amount and the dissipation dH/dt = RT sum_r J_r ln(c_a/c_b) as extra states. Each amount's
    absolute tolerance is rtol x atol_fraction x its own initial amount, so a trace keeps its
    relative accuracy."""
    check_world(world)
    w = world
    names = list(w.compartments)
    routes = list(w.routes)
    idx = {x: i for i, x in enumerate(names)}
    a = np.array([idx[w.routes[r].a] for r in routes], dtype=int)
    b = np.array([idx[w.routes[r].b] for r in routes], dtype=int)
    pa = np.array([w.routes[r].PA_m3_per_s for r in routes]) * FMOL_PER_MOL
    V = np.array([w.compartments[x].volume_pL for x in names])
    n0 = np.array([w.compartments[x].amount_fmol for x in names])
    rt = w.rt_pJ_per_fmol
    nc, nr = len(names), len(routes)

    def rhs(t, y):
        c = y[:nc] / V
        J = pa * (c[a] - c[b])
        out = np.zeros(nc + nr + 1)
        np.add.at(out, a, -J)
        np.add.at(out, b, J)
        out[nc:nc + nr] = J
        out[-1] = rt * float(np.sum(J * (np.log(c[a]) - np.log(c[b]))))
        return out

    y0 = np.concatenate([n0, np.zeros(nr), [0.0]])
    scale = np.concatenate([n0, np.full(nr, n0.max()), [rt * n0.max()]])
    record = tuple(sorted({float(t) for t in record}))
    points = sorted({0.0, float(t_end), *record})
    run = piecewise_ode.Run(lambda t0, t1: (rhs, None), y0, points, rtol=rtol,
                            atol=rtol * atol_fraction * scale, method=method)
    return PassiveRun(w, run, record, names, routes)
