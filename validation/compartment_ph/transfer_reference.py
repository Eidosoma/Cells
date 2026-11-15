"""FR-5's references: damage, leak and reseal, and pH-conditioned transfer of a neutral cargo X, on
FR-4's compartment state under the rapid-buffer closure (R-transfer), an independent reference.

Written from docs/COMPARTMENT_PH_TRANSFER_DESIGN.md's §8 (the routing door's factors), §9 (FR-5's
laws), §13.2 (the world) and Appendix A (FR-5's states, fluxes and energy identity), without
reading the engine. numpy, scipy and the standard library, plus this folder's ph_reference (FR-4's
R-closure, whose transport, charge and stored energy are reused unchanged).

* **Damage** (§9), a control state on the bounding patch with no ledger:
  dd/dt = k_inj u_inj(t) (1 - d) - k_res u_res(t) d, with u_inj and u_res piecewise constant in
  [0, 1]. It is integrated exactly on each constant piece: with a = k_inj u_inj, b = k_res u_res
  and s = a + b, d(t) = d_k e^{-s(t - t_k)} + (a/s)(1 - e^{-s(t - t_k)}), two non-negative terms.
* **The proton leak with damage** (Appendix A): J_H = 1e15 (P_H + d P_pore,H) A_b psi(u)
  (h_c - h_L e^{-u}), u = F V_b/(RT), on the free h of each closure (§7.1). The pore's share is
  kept apart as its own route.
* **Cargo X** (z = 0, §9 and Appendix A): each route r carries J_r = 1e15 m_r P_r A_b
  (c_X,c - c_X,L), with §8's multiplier m_r = 1, f(pH_L), d or f(pH_L) d (`multiply`, evaluated on
  the state at every time: the stage form). f(pH) = 1/(1 + 10^(m (pH - pH50))), open below pH50.
* **Everything else is FR-4's:** the pump on held fuel, the leak at P_H, the counterions, the
  potentials and the closure (ph_reference).
* **Fluxes are positive from c to L,** and whatever leaves L arrives in c on the same route.
* **Energy** (Appendix A): dG_stored + Q = W. G_stored adds n_X RT (ln(c_X/c0) - 1) at each node to
  FR-4's; Q adds each route's J (mu~_c - mu~_L). The heat of every route is also kept apart.

Sources: Goldman DE. J Gen Physiol 1943;27:37-60 (the constant-field flux); Hill AV. J Physiol
1910;40:iv-vii (the Hill form of f); Hairer E, Wanner G. Solving ODEs II. Springer; 1996
(Radau IIA).
"""

import math
from dataclasses import dataclass, field

import numpy as np

from validation.compartment_ph import ph_reference as ph
from validation.coupling import piecewise_ode

# ---------------------------------------------------------------- the laws


@dataclass(frozen=True)
class Window:
    """A schedule's value on [start_s, end_s) (end_s may be inf); 0 elsewhere."""

    start_s: float
    end_s: float
    value: float = 1.0


@dataclass(frozen=True)
class Damage:
    """§9's injury and resealing: rates (1/s), the schedules' windows, and d(0)."""

    k_inj_per_s: float = 0.0
    k_res_per_s: float = 0.0
    injure: tuple = ()
    reseal: tuple = ()
    d0: float = 0.0


class DamageSolution:
    """d(t), exact on every constant piece of the schedules (§9)."""

    def __init__(self, damage):
        self.damage = dm = damage
        if not (dm.k_inj_per_s >= 0 and dm.k_res_per_s >= 0 and math.isfinite(dm.k_inj_per_s)
                and math.isfinite(dm.k_res_per_s)):
            raise ValueError("k_inj and k_res are finite and >= 0")
        if not 0.0 <= dm.d0 <= 1.0:
            raise ValueError("d0 lies in [0, 1]")
        edges = {0.0}
        for w in (*dm.injure, *dm.reseal):
            if not (0.0 <= w.start_s < w.end_s and 0.0 <= w.value <= 1.0):
                raise ValueError("windows are [start, end) with 0 <= start < end, values in [0, 1]")
            edges.add(float(w.start_s))
            if math.isfinite(w.end_s):
                edges.add(float(w.end_s))
        self.breaks = sorted(edges)
        for t in self.breaks:  # the schedules stay in [0, 1] where windows overlap
            if self._u(dm.injure, t) > 1.0 or self._u(dm.reseal, t) > 1.0:
                raise ValueError("overlapping windows sum above 1")
        self.d_at_break = [float(dm.d0)]
        for k in range(len(self.breaks) - 1):
            self.d_at_break.append(self._advance(k, self.breaks[k + 1] - self.breaks[k]))

    @staticmethod
    def _u(windows, t):
        return sum(w.value for w in windows if w.start_s <= t < w.end_s)

    def rates(self, t):
        """(a, b) = (k_inj u_inj(t), k_res u_res(t)) (1/s)."""
        dm = self.damage
        return dm.k_inj_per_s * self._u(dm.injure, t), dm.k_res_per_s * self._u(dm.reseal, t)

    def _advance(self, k, tau):
        a, b = self.rates(self.breaks[k])
        d = self.d_at_break[k]
        s = a + b
        if s == 0.0 or tau == 0.0:
            return d
        grow = -math.expm1(-s * tau)
        return d * (1.0 - grow) + (a / s) * grow

    def at(self, t):
        if t < 0:
            raise ValueError("t >= 0")
        k = max(i for i, b in enumerate(self.breaks) if b <= t)
        return self._advance(k, t - self.breaks[k])


@dataclass(frozen=True)
class Condition:
    """§9's f(pH) = 1/(1 + 10^(m (pH - pH50))), open below pH50, Hill slope m > 0."""

    pH50: float
    hill: float

    def f(self, pH_value):
        if not self.hill > 0:
            raise ValueError("the Hill slope m is > 0")
        x = self.hill * (pH_value - self.pH50)
        if x > 0:  # 10^-x underflows to 0 instead of 10^x overflowing
            e = 10.0 ** -x
            return e / (1.0 + e)
        return 1.0 / (1.0 + 10.0 ** x)


@dataclass(frozen=True)
class CargoRoute:
    """One route of X across the bounding patch: P (m/s), and §8's factors."""

    name: str
    permeability_m_s: float
    conditioned: bool = False  # x f(pH_L)
    damaged: bool = False  # x d


@dataclass(frozen=True)
class Start:
    """The declared start (fmol): (cytosol, lumen) H_eq, ion amounts and X."""

    Heq_fmol: tuple
    ions_fmol: tuple
    X_fmol: tuple


@dataclass(frozen=True)
class TransferWorld:
    """FR-4's world (``base``; its pH0 start fixes each node's fixed charge, §13) with FR-5's
    routes, condition and damage, from a declared start."""

    base: ph.World
    start: Start
    cargo_routes: tuple = ()
    proton_pore_m_s: float = 0.0
    condition: Condition = None
    damage: Damage = field(default_factory=Damage)


# ---------------------------------------------------------------- the model


class _TransferModel:
    """R-closure of FR-4 (ph_reference._Model) with X, the damage pore and the per-route heats."""

    def __init__(self, world):
        self.w = w = world
        self.base = b = ph._Model(w.base, kinetic=False)
        self.F, self.rt, self.c0 = b.F, b.rt, b.c0
        self.ds = DamageSolution(w.damage)
        if not w.proton_pore_m_s >= 0 or any(not r.permeability_m_s >= 0 for r in w.cargo_routes):
            raise ValueError("permeabilities are >= 0")
        if any(r.conditioned for r in w.cargo_routes) and w.condition is None:
            raise ValueError("a conditioned route needs the condition")
        if len({r.name for r in w.cargo_routes}) != len(w.cargo_routes):
            raise ValueError("route names are unique")
        s = w.start
        if not all(x > 0 for x in (*s.Heq_fmol, *s.X_fmol)):
            raise ValueError("H_eq and X start > 0 (a resolved start, §13.2)")
        self.route_names = ("pump", "leak_H", "pore_H", *[f"ion_{i}" for i in b.ion_moving],
                            *[f"X_{r.name}" for r in w.cargo_routes])
        self.moved_names = ("H_pore", *[f"X_{r.name}" for r in w.cargo_routes])
        self.iX = b.size
        self.iq = b.size + 2
        self.im = self.iq + len(self.route_names)  # amounts moved by the FR-5 routes, c to L
        self.size = self.im + len(self.moved_names)
        y0 = np.zeros(self.size)
        y0[0], y0[1] = s.Heq_fmol
        m = len(b.ion_moving)
        for j, ion in enumerate(b.ion_moving):
            y0[b.iion + j] = s.ions_fmol[0][ion]
            y0[b.iion + m + j] = s.ions_fmol[1][ion]
        y0[self.iX], y0[self.iX + 1] = s.X_fmol
        self.y0 = y0
        self.ions_fixed = [{ion: s.ions_fmol[i][ion] for ion in ph.IONS} for i in range(2)]
        # The impermeant ions are read from the start, not from FR-4's pH0 state.
        b.ions0 = [dict(self.ions_fixed[0]), dict(self.ions_fixed[1])]
        scale = np.abs(y0).copy()
        G0 = abs(1e-3 * self.rt * float(np.max(np.abs(y0[:self.iq]))))
        scale[b.iW] = scale[b.iQ] = scale[b.iR] = G0
        scale[self.iq:] = G0
        scale[b.iC] = scale[self.im:] = float(np.max(np.abs(y0[:b.iW])))
        self.scale = scale

    def state(self, t, y):
        b, w = self.base, self.w
        sp = b.speciation(y)
        Vb, phic = b.potentials(sp)
        tr = b.transport(sp, Vb)
        d = self.ds.at(t)
        F, rt, A = self.F, self.rt, w.base.patch_area_m2
        hc, hL = sp[0]["h"], sp[1]["h"]
        u1 = F * Vb / rt
        Jp = d * ph.FMOL_PER_MOL * w.proton_pore_m_s * A * ph.psi(u1) * (hc - hL * math.exp(-u1))
        dmu_H = rt * math.log(hc / hL) + F * Vb
        pH_L = ph.pH(hL, self.c0)
        f = w.condition.f(pH_L) if w.condition is not None else 1.0
        xc, xL = float(y[self.iX]) / b.V[0], float(y[self.iX + 1]) / b.V[1]
        J_X = {}
        for r in w.cargo_routes:
            mult = (f if r.conditioned else 1.0) * (d if r.damaged else 1.0)
            J_X[r.name] = mult * ph.FMOL_PER_MOL * r.permeability_m_s * A * (xc - xL)
        dmu_X = rt * math.log(xc / xL)
        heats = [1e-3 * (-tr["dG_cyc"]) * tr["J_cyc"], 1e-3 * tr["J_H"] * dmu_H, 1e-3 * Jp * dmu_H]
        for ion in b.ion_moving:
            cin, cout = sp[0]["ions"][ion] / b.V[0], sp[1]["ions"][ion] / b.V[1]
            heats.append(1e-3 * tr["J_ions"][ion] * (rt * math.log(cin / cout)
                                                     + ph.Z_ION[ion] * F * Vb))
        heats += [1e-3 * J_X[r.name] * dmu_X for r in w.cargo_routes]
        return dict(sp=sp, Vb=Vb, phi_c=phic, tr=tr, d=d, f=f, pH_L=pH_L, J_H_pore=Jp, J_X=J_X,
                    heats=heats)

    def rhs(self, t, y):
        b = self.base
        st = self.state(t, y)
        tr = st["tr"]
        n = self.w.base.pump.n if self.w.base.pump is not None else 0
        dH = n * tr["J_cyc"] + tr["J_H"] + st["J_H_pore"]
        JX = sum(st["J_X"].values())
        out = np.zeros(self.size)
        out[0], out[1] = -dH, dH
        m = len(b.ion_moving)
        for j, ion in enumerate(b.ion_moving):
            out[b.iion + j] = -tr["J_ions"][ion]
            out[b.iion + m + j] = tr["J_ions"][ion]
        out[b.iW] = tr["work_rate"]
        out[b.iQ] = sum(st["heats"])
        out[b.iC] = tr["J_cyc"]
        out[self.iX], out[self.iX + 1] = -JX, JX
        out[self.iq:self.im] = st["heats"]
        out[self.im] = st["J_H_pore"]
        for k, r in enumerate(self.w.cargo_routes):
            out[self.im + 1 + k] = st["J_X"][r.name]
        return out

    def stored_free_energy(self, y):
        g = self.base.stored_free_energy(y)
        for i in range(2):
            n = float(y[self.iX + i])
            g += 1e-3 * n * self.rt * (math.log(n / self.base.V[i] / self.c0) - 1.0)
        return g


class TransferRun:
    """One run. ``at[t]``: dict(pH_c, pH_L, h_c, h_L (mM), Heq_c, Heq_L, ions_c, ions_L, X_c, X_L
    (fmol), cX_c, cX_L (mM), Vb, phi_c (V), d, f, J_cyc, J_H (the leak at P_H), J_H_pore,
    J_ions, J_X {route} (fmol/s, c to L), cycles (fmol), work_pJ, heat_pJ, heat_by_route_pJ
    {route}, moved_fmol {H_pore, X_route} (fmol moved c to L since the start), stored_change_pJ,
    energy_residual_pJ (dG_stored + Q - W))."""

    def __init__(self, model, run, record):
        self.model, self.run = model, run
        self.steps = run.steps
        self.G0 = model.stored_free_energy(model.y0)
        self.at = {t: self.observe(t) for t in record}

    def observe(self, t):
        m, b = self.model, self.model.base
        y = self.run.state(t)
        st = m.state(t, y)
        sp, tr = st["sp"], st["tr"]
        W, Q = float(y[b.iW]), float(y[b.iQ])
        G = m.stored_free_energy(y)
        X = (float(y[m.iX]), float(y[m.iX + 1]))
        return dict(
            t=t, pH_c=ph.pH(sp[0]["h"], m.c0), pH_L=st["pH_L"], h_c=sp[0]["h"], h_L=sp[1]["h"],
            Heq_c=float(y[0]), Heq_L=float(y[1]), ions_c=dict(sp[0]["ions"]),
            ions_L=dict(sp[1]["ions"]), X_c=X[0], X_L=X[1], cX_c=X[0] / b.V[0],
            cX_L=X[1] / b.V[1], Vb=st["Vb"], phi_c=st["phi_c"], d=st["d"], f=st["f"],
            J_cyc=tr["J_cyc"], J_H=tr["J_H"], J_H_pore=st["J_H_pore"],
            J_ions=dict(tr["J_ions"]), J_X=dict(st["J_X"]), cycles=float(y[b.iC]),
            work_pJ=W, heat_pJ=Q,
            heat_by_route_pJ=dict(zip(m.route_names, map(float, y[m.iq:m.im]), strict=True)),
            moved_fmol=dict(zip(m.moved_names, map(float, y[m.im:]), strict=True)),
            stored_change_pJ=G - self.G0, energy_residual_pJ=(G - self.G0) + Q - W)


def integrate(world, t_end, *, record=(), rtol=1e-11, method="Radau", atol_fraction=1e-6):
    """R-transfer from the declared start (t = 0) to t_end; Radau at rtol 1e-11 (Appendix A). The
    schedules' breakpoints are segment ends, so the right-hand side is smooth on every segment."""
    model = _TransferModel(world)
    record = tuple(sorted({float(t) for t in record}))
    breaks = [t for t in model.ds.breaks if 0.0 < t < t_end]
    points = sorted({0.0, float(t_end), *record, *breaks})
    run = piecewise_ode.Run(lambda t0, t1: (model.rhs, None), model.y0, points, rtol=rtol,
                            atol=rtol * atol_fraction * model.scale, method=method)
    return TransferRun(model, run, record)


# ---------------------------------------------------------------- the acceptance world (§13.2)


def steady_start(base=None, *, X_mM=(1e-4, 1.0), t_steady=3600.0, rtol=1e-11):
    """FR-4's world run to its steady state by R-closure (§13.2: "FR-4's world at its steady
    state"), with cargo X added at (cytosol, lumen) concentrations. Returns (Start, the FR-4 run's
    record at t_steady). By 1800 s the net proton flux is below 1e-11 fmol/s."""
    base = base or ph.acceptance_world()
    run = ph.integrate(base, t_steady, record=(t_steady,), rtol=rtol)
    r = run.at[t_steady]
    V = (base.cytosol.volume_pL, base.lumen.volume_pL)
    return Start(Heq_fmol=(r["Heq_c"], r["Heq_L"]), ions_fmol=(r["ions_c"], r["ions_L"]),
                 X_fmol=(X_mM[0] * V[0], X_mM[1] * V[1])), r


def acceptance_world(*, start=None, conditioned=True, damaged=True, P_X=1e-8, P_pore_H=1e-6):
    """§13.2's world: FR-4's at its steady state, X at 1 mM in the lumen and 1e-4 mM in the cytosol,
    the conditioned transfer (P_X 1e-8 m/s, pH50 5.5, m 4), and damage (k_inj 1/s on [100, 110) s,
    k_res 0.05/s from 110 s) opening pores for H+ and X (1e-6 m/s each). The negative controls:
    ``conditioned=False`` is f = 1; ``damaged=False`` is d = 0. ``P_X`` and ``P_pore_H`` (m/s)
    are for sensitivity runs only."""
    base = ph.acceptance_world()
    start = start or steady_start(base)[0]
    damage = (Damage(k_inj_per_s=1.0, k_res_per_s=0.05, injure=(Window(100.0, 110.0),),
                     reseal=(Window(110.0, math.inf),)) if damaged else Damage())
    return TransferWorld(
        base=base, start=start,
        cargo_routes=(CargoRoute("transfer", P_X, conditioned=conditioned),
                      CargoRoute("pore", 1e-6, damaged=True)),
        proton_pore_m_s=P_pore_H, condition=Condition(pH50=5.5, hill=4.0), damage=damage)
