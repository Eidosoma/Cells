"""References for the sheet's amendment R: a release step with two fates (§9, FR-38).

Source: docs/TEMPLATED_POLYMERISATION_LAWS.md at tag gr1-sheet-fr38-r2-2026-11-22 (§9, its
addendum on R2's rows and translation included), read against §0–§8. Nothing here reads engine
code or the lane's tools.

The release worlds of §9.9, R1 and R2, are built on this package's G2 model (model.py,
unchanged). A `ReleaseSystem` adds to a G2 world:
- §9.1's hold H_ρ (one class: the label is set at release);
- the fate rows (§9.9's addendum): the durable fate is A1's row R, and the short-lived fate is a
  row R_s with R's chemistry. Both start at the trace c_R. With two label classes (§9.8's route
  1), class 2's rows are R_c2 and R_s_c2, also of R's chemistry;
- §9.2's release, Q^f = π_f H/τ with π_d = p and π_s = 1 − p, into the class ψ(t) names;
- the fates' losses (§4.4's law): deg_R takes k_d and deg_R_s takes k_s;
- §9.3's machine option: `returned` (back at completion) or `held` (back at release);
- §9.5's energy (the hold's standard term in G; release and loss heats in their own classes);
- with one class, three exact trackers that do not feed back:
  - CO_f, the release-window cohort under first-order, age-independent loss;
  - LR_f, the released molecules still present;
  - DL_f, LR_f's distance from the first-order value with the same releases, integrated directly.
    In R1 that value is the requester's limit.

R2's translation (the addendum) is two chains, `tl` templated by R and `tl_s` by R_s, each with
A1's parameters, sharing the ribosome pool and making P.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import DOP853

from . import model, sheet

SHEET_TAG_R = "gr1-sheet-fr38-2026-11-22"
SHEET_TAG_R2 = "gr1-sheet-fr38-r2-2026-11-22"
LN2 = math.log(2.0)
FPC = model.FMOL_PER_COPY
RT = model.RT_KJ

# §9.9's release table (the requester's values) and R1's and R2's declarations.
H0_COPIES = 80
TAU = 3600.0 / LN2  # s: an exit half-life of 1 h
P_CASES = (0.0, 0.25, 0.75, 1.0)
K_DURABLE = LN2 / 7200.0  # s⁻¹: a half-life of 2 h
K_SHORT = LN2 / 1800.0  # s⁻¹: a half-life of 0.5 h
T_OUT_R1 = (0.0, 1800.0, 3600.0, 7200.0, 14400.0)
WINDOW = (0.0, 3600.0)  # the release-window cohort's window, s
T_SAMPLE = (3600.0, 7200.0)  # the cohort's samples, s
P_R2 = 0.75
GRID_R1 = 60.0  # R1's internal grid: every switch and output lies on it
TRACE_mM = sheet.A1["c_R"]  # the addendum: "the inventory trace" is c_R = 1.0e-12 mM
FATES = ("d", "s")
FATE_ROW = {("d", 1): "R", ("s", 1): "R_s", ("d", 2): "R_c2", ("s", 2): "R_s_c2"}
LOSS_HEAT = {"d": "H_deg_R", "s": "H_deg_R_s"}


@dataclass(frozen=True)
class ReleaseDecl:
    """One chain's `release` block (§9.1–§9.4), with the references' run options."""

    route: str = "tx"
    tau: float = TAU
    p: float = 0.75
    k_d: float = K_DURABLE
    k_s: float = K_SHORT
    machine: str = "returned"  # §9.3: 'returned' or 'held'
    H0_copies: float = 0.0
    classes: int = 1  # 2: label at release, class 2 during `window` (§9.8, route 1)
    window: tuple = WINDOW

    def psi(self, t0: float) -> int:
        """The class a release at a segment starting at t0 enters (labelled at release)."""
        if self.classes == 1:
            return 1
        t1, t2 = self.window
        return 2 if t1 <= t0 < t2 else 1

    def in_window(self, t0: float) -> bool:
        t1, t2 = self.window
        return t1 <= t0 < t2

    def k_fate(self, f: str) -> float:
        return self.k_d if f == "d" else self.k_s

    def frac(self, f: str) -> float:
        return self.p if f == "d" else 1.0 - self.p

    def label(self) -> str:
        return f"p={self.p:g}, {self.machine}, H0={self.H0_copies:g}, K={self.classes}"


def fate_rows(classes: int) -> list[str]:
    return [FATE_ROW[(f, k)] for k in range(1, classes + 1) for f in FATES]


def _fates(decl: ReleaseDecl, V: float, L: int):
    """The fate rows other than R (A1's own row, already at the trace), at the trace, and every
    fate row's loss."""
    trace = float(Decimal(TRACE_mM)) * V
    rows = {s: trace for s in fate_rows(decl.classes) if s != "R"}
    degs = tuple(model.Degradation(FATE_ROW[(f, k)], decl.k_fate(f), L, "M", "R_res")
                 for k in range(1, decl.classes + 1) for f in FATES)
    return rows, degs


def r1_world(decl: ReleaseDecl, recharging: bool = False) -> model.World:
    """§9.9's R1. Reading R1: its routes are the chain (k_I = 0), the release and the fates'
    losses only; `recharging` adds A1's recharging as a reported variant."""
    a = sheet.A1
    V = model._fl(a["V"])
    rows0 = {s: model._fl(a["c_" + s]) * V
             for s in ("X", "N", "M", "A", "ATP", "ADP", "Pi", "R", "P")}
    fr, degs = _fates(decl, V, a["L_R"])
    rows0.update(fr)
    routes = (model.Route("tx", "tx", "pol", a["L_R"], a["m_tx"], model._fl(a["v_tx"]), 0.0,
                          a["T_copies"], None, "R", False),)
    lengths = {"R": a["L_R"], "P": a["L_P"], **{s: a["L_R"] for s in fr}}
    return model.World("R1" + (" + recharging" if recharging else ""), V, rows0, (),
                       {"pol": model._fl(a["M_pol"]) * FPC}, routes, degs, recharging, None,
                       ((0.0, math.inf, 0.0),), 14400.0, GRID_R1, None, model._K(),
                       model._fl(a["V_C"]), lengths)


def r2_world(decl: ReleaseDecl) -> model.World:
    """§9.9's R2 with its addendum: A1 (§5.1) with transcription's chain declaring §9; deg_R at
    k_d and deg_R_s at k_s; translation as two chains, `tl` on R and `tl_s` on R_s."""
    if decl.classes != 1:
        raise ValueError("R2 declares no label classes: whether class-2 rows are templates is "
                         "not ruled")
    w = model.a1_world()
    fr, degs = _fates(decl, w.V, sheet.A1["L_R"])
    rows0 = {**w.rows0, **fr}
    tl = next(r for r in w.routes if r.kind == "tl")
    routes = (*w.routes, replace(tl, name="tl_s", template_row="R_s"))
    others = tuple(g for g in w.degradations if g.row != "R")  # deg_P stays; deg_R is a fate's
    lengths = {**w.lengths, **{s: sheet.A1["L_R"] for s in fr}}
    return replace(w, name="R2", rows0=rows0, routes=routes, degradations=degs + others,
                   lengths=lengths)


class ReleaseSystem(model.System):
    """A G2 world with one chain declaring §9's release step."""

    def __init__(self, world: model.World, pot: sheet.Potentials, decl: ReleaseDecl):
        if decl.machine not in ("returned", "held") or not 0.0 <= decl.p <= 1.0 or decl.tau <= 0:
            raise ValueError(f"refused declaration: {decl}")  # §9.6
        self.decl = decl
        self.fates = fate_rows(decl.classes)
        self.fate_of = {FATE_ROW[key]: key for key in FATE_ROW if FATE_ROW[key] in self.fates}
        self.trackers = decl.classes == 1
        self._psi = 1
        self._in_window = False
        super().__init__(world, pot)
        self.rel_route = next(r for r in self.routes if r.name == decl.route)
        self.H0 = decl.H0_copies * FPC
        if decl.machine == "held" and self.H0 > self.world.pools[self.rel_route.pool]:
            raise ValueError("refused: the initial hold exceeds the pool (§9.3)")

    # ---- the state, the fluxes and the motion matrix ----------------------------------------
    def _motion_matrix(self) -> np.ndarray:
        d = self.decl
        base_heat = [h for h in self.HEAT_CLASSES if h in self.heat_classes]
        names = [n for n in self.names if n not in base_heat]
        names += [f"H:{d.route}"] + [f"RQ:{f}{k}" for f, k in self.fate_of.values()]
        if self.trackers:
            names += [f"{x}:{f}" for x in ("CO", "LR", "DL") for f in FATES]
        has_P_deg = any(g.row == "P" for g in self.world.degradations)
        keep = {"H_tx": True, "H_tl": any(r.kind == "tl" for r in self.routes),
                "H_deg_R": True, "H_deg_P": has_P_deg, "H_rc": self.world.recharging}
        self.heat_classes = [h for h in self.HEAT_CLASSES if keep[h]] + [
            "H_deg_R_s", "H_rel_d", "H_rel_s"]
        names += self.heat_classes
        self.names = names
        self.ix = {n: i for i, n in enumerate(names)}
        self.ns = len(names)
        self.flux_names = list(self.flux_names) + [f"Qf:{f}{k}"
                                                   for f, k in self.fate_of.values()]
        self.fx = {n: i for i, n in enumerate(self.flux_names)}
        self.iH = self.ix[f"H:{d.route}"]
        N = super()._motion_matrix()
        pool = next(r.pool for r in self.routes if r.name == d.route)
        for s, (f, k) in self.fate_of.items():
            c = self.fx[f"Qf:{f}{k}"]
            N[self.iH, c] -= 1.0
            N[self.ix[f"d:{s}"], c] += 1.0
            N[self.ix[f"RQ:{f}{k}"], c] += 1.0
            if d.machine == "held":
                N[self.ix[f"dF:{pool}"], c] += 1.0  # §9.3: the machine returns at release
        return N

    def columns(self, r: model.Route) -> tuple[dict, dict, dict]:
        ini, ex, rel = super().columns(r)
        if r.name == self.decl.route:  # §9.7: the completion enters the hold, not the product row
            rel = {f"W:{r.name}": -float(r.L), f"H:{r.name}": 1.0,
                   f"dF:{r.pool}": 1.0 if self.decl.machine == "returned" else 0.0}
        return ini, ex, rel

    def initial_state(self) -> np.ndarray:
        y = np.zeros(self.ns)
        y[self.iH] = self.H0
        if self.decl.machine == "held":
            y[self.ix[f"dF:{self.rel_route.pool}"]] = -self.H0  # §9.3: F_q(0) = M_q − ΣH(0)
        return y

    def set_segment(self, t0: float) -> None:
        self._psi = self.decl.psi(t0)
        self._in_window = self.decl.in_window(t0)

    def fluxes(self, y, amt=None, ch=None):
        """Every flux (fmol/s) and heat rate (pJ/s): §4's laws, with §9's changes."""
        if amt is None:
            amt = self.amounts(y)
        if ch is None:
            ch = self.chemistry(y, amt)
        d, V, K = self.decl, self.V, self.world.K
        c = {s: amt[s] / V for s in amt}
        J = np.empty(len(self.flux_names))
        heat = dict.fromkeys(self.heat_classes, 0.0)
        u = self.u_factor(y)
        k = 0
        for r in self.routes:
            uu = u if r.regulated else 1.0
            c_T = r.copies * FPC / V if r.kind == "tx" else c[r.template_row]  # §4.1
            J[k] = uu * r.k_I * c_T * (self.world.pools[r.pool] + y[self.ix[f"dF:{r.pool}"]])
            k += 1
        for r in self.routes:
            x = ch["x_tx"] if r.kind == "tx" else ch["x_tl"]
            if r.kind == "tx":
                sat = c["N"] / (K["K_N_tx"] + c["N"])
            else:
                sat = c["A"] / (K["K_A_tl"] + c["A"]) * c["ATP"] / (K["K_ATP_tl"] + c["ATP"])
            phi = sat * -math.expm1(x)
            i0 = self.ix[f"C:{r.name}:1"]
            stage = r.v / r.r * phi * y[i0:i0 + r.m]
            J[k:k + r.m] = stage
            k += r.m
            cls = "H_tx" if r.kind == "tx" else "H_tl"
            heat[cls] += r.r * float(stage.sum()) * (-x * RT)
            if r.name != d.route:  # §9.5: a chain with §9 has no release term in its class
                heat[cls] += float(stage[-1]) * (-ch[f"x_rel:{r.product}"] * RT)
        for g in self.world.degradations:
            xd = ch[f"x_deg:{g.row}"]
            J[k] = g.k * amt[g.row] * -math.expm1(xd / g.L)
            if g.row in self.fate_of:
                h = LOSS_HEAT[self.fate_of[g.row][0]]
            else:
                h = "H_deg_R" if g.monomer == "M" else "H_deg_P"
            heat[h] += J[k] * (-xd * RT)
            k += 1
        if self.world.recharging:
            x_rc = ch["x_rc"]
            J[k] = (V * self.world.V_C * c["M"] / (K["K_M_rc"] + c["M"])
                    * c["ATP"] / (K["K_ATP_rc"] + c["ATP"]) * -math.expm1(x_rc / 2.0))
            heat["H_rc"] += J[k] * (-x_rc * RT)
            k += 1
        out = y[self.iH] / d.tau  # §9.2, no affinity factor
        for s, (f, cls) in self.fate_of.items():
            q = d.frac(f) * out if cls == self._psi else 0.0
            J[self.fx[f"Qf:{f}{cls}"]] = q
            heat[f"H_rel_{f}"] += q * (-ch["lna"][s] * RT)  # −ΔG^rel_f = −RT ln(c_F/c°)
        return J, heat, u

    def rhs(self, t: float, y: np.ndarray, P_X: float) -> np.ndarray:
        amt = self.amounts(y)
        ch = self.chemistry(y, amt)
        J, heat, _ = self.fluxes(y, amt, ch)
        dy = self.N @ J
        for h, v in heat.items():
            dy[self.ix[h]] = v
        if self.world.regulator is not None:
            dy[self.iX] = P_X - self.world.regulator["k_X"] * (self.n0[self.iX] + y[self.iX])
        if self.trackers:
            L = self.rel_route.L
            for f in FATES:
                row = FATE_ROW[(f, 1)]
                kf = self.decl.k_fate(f)
                eps = math.exp(ch[f"x_deg:{row}"] / L)  # e^(y_f)
                kappa = kf * (1.0 - eps)  # the pool's per-capita loss rate
                q = J[self.fx[f"Qf:{f}1"]]
                co, lr, dl = (self.ix[f"{x}:{f}"] for x in ("CO", "LR", "DL"))
                dy[co] = (q if self._in_window else 0.0) - kappa * y[co]
                dy[lr] = q - kappa * y[lr]
                dy[dl] = -kf * y[dl] + kf * eps * y[lr]  # (LR − limit)′, the limit's loss k_f
        return dy

    # ---- the domain, G and the moieties --------------------------------------------------------
    def affinities(self, y: np.ndarray) -> dict:
        out = super().affinities(y)
        if self.rel_route.k_I == 0.0:  # R1: no complexes, so elongation's affinity is unused
            out.pop("x_tx", None)
        ch = self.chemistry(y)
        out["lna_F_max"] = max(ch["lna"][s] for s in self.fates)  # §9.6: c_F ≤ c°
        return out

    def G_minus_G0(self, y: np.ndarray) -> float:
        """§3.4's G − G(0), plus §9.5's hold term L μ°_res (H − H(0)), in pJ."""
        L = self.rel_route.L
        return super().G_minus_G0(y) + L * self.mu0["R_res"] * (y[self.iH] - self.H0) * RT

    def moiety_weights(self) -> dict:
        out = super().moiety_weights()
        L = float(self.rel_route.L)
        for m in ("phosphorus", "nucleoside"):
            out[m][f"H:{self.decl.route}"] = L  # the hold's L_R residues per molecule
        return out


# ---- integration -------------------------------------------------------------------------------
def _a_priori(sysm: ReleaseSystem) -> np.ndarray:
    s = np.empty(sysm.ns)
    big = 100 * FPC
    for n, i in sysm.ix.items():
        kind, _, rest = n.partition(":")
        if kind == "d":
            n0 = sysm.n0[sysm.rows.index(rest)]
            s[i] = max(n0, big) if rest[:1] in ("R", "P", "X") else 1e-4 * n0
        elif kind == "DL":
            s[i] = 1e-8 * big
        elif n.startswith("H_"):
            s[i] = 1e-6
        else:
            s[i] = big
    return s


def integrate(sysm: ReleaseSystem, times, rtol: float, scales: np.ndarray | None = None,
              track: bool = True) -> dict:
    """DOP853 from output to output (every switch lies on the grid); outputs hit exactly."""
    times = np.asarray(times, dtype=float)
    if scales is None:
        scales = _a_priori(sysm)
    atol = rtol * scales
    y = sysm.initial_state()
    Y = np.zeros((len(times), sysm.ns))
    Y[0] = y
    dom, heat_prev, steps, h_next = {}, None, 0, None
    heat_min = dict.fromkeys(sysm.heat_classes, math.inf)
    if track:
        sysm.set_segment(times[0])
        dom = {k: (v, 0.0) for k, v in sysm.affinities(y).items()}
    for k in range(1, len(times)):
        t0, t1 = times[k - 1], times[k]
        P_X = sysm.world.P_X(t0)
        sysm.set_segment(t0)

        def fun(t, yy, P_X=P_X):
            return sysm.rhs(t, yy, P_X)

        kw = {"rtol": rtol, "atol": atol}
        if h_next is not None:
            kw["first_step"] = min(h_next, t1 - t0)
        solver = DOP853(fun, t0, y, t1, **kw)
        h_save = None
        while solver.status == "running":
            h_save = solver.h_abs
            msg = solver.step()
            if solver.status == "failed":
                raise RuntimeError(f"{sysm.world.name} rtol={rtol}: {msg} at t={solver.t}")
            steps += 1
            if track:
                for key, val in sysm.affinities(solver.y).items():
                    if val > dom.get(key, (-math.inf,))[0]:
                        dom[key] = (val, float(solver.t))
                hv = {h: solver.y[sysm.ix[h]] for h in sysm.heat_classes}
                if heat_prev is not None:
                    for h in hv:
                        heat_min[h] = min(heat_min[h], hv[h] - heat_prev[h])
                heat_prev = hv
        if h_save:
            h_next = h_save
        y = solver.y.copy()
        Y[k] = y
    return {"times": times, "Y": Y, "rtol": rtol, "steps": steps, "domain": dom,
            "heat_min_increment": heat_min, "scales": scales}


def state_scales(sysm: ReleaseSystem, times, rtol0: float = 1e-8) -> np.ndarray:
    sol = integrate(sysm, times, rtol0, track=False)
    return np.maximum(np.max(np.abs(sol["Y"]), axis=0), 1e-6 * _a_priori(sysm))


# ---- readouts and identities --------------------------------------------------------------------
def readouts(sysm: ReleaseSystem, sol: dict) -> dict:
    """Every row and pool, the chain's states, §9.7's counters, G − G(0), the heats and each move's
    ΔG, at every output (fmol, pJ, kJ/mol, s)."""
    w, d = sysm.world, sysm.decl
    times, Y = sol["times"], sol["Y"]
    out = {"t": times.copy()}
    for s in w.rows0:
        out[f"n_{s}"] = sysm.n0[sysm.rows.index(s)] + Y[:, sysm.ix[f"d:{s}"]]
    for q, M in w.pools.items():
        out[f"F_{q}"] = M + Y[:, sysm.ix[f"dF:{q}"]]
    for r in sysm.routes:
        i0 = sysm.ix[f"C:{r.name}:1"]
        for j in range(r.m):
            out[f"C_{r.name}_{j + 1}"] = Y[:, i0 + j].copy()
        csum = Y[:, i0:i0 + r.m].sum(axis=1)
        held = r.name == d.route and d.machine == "held"
        out[f"C_sum_{r.name}"] = csum
        out[f"E_{r.name}"] = csum + (Y[:, sysm.iH] if held else 0.0)  # §9.3's E_ρ
        out[f"W_{r.name}"] = Y[:, sysm.ix[f"W:{r.name}"]].copy()
        out[f"int_J_I_{r.name}"] = Y[:, sysm.ix[f"I:{r.name}"]].copy()
        out[f"int_S_{r.name}"] = Y[:, sysm.ix[f"S:{r.name}"]].copy()
        out[f"int_Q_{r.name}"] = Y[:, sysm.ix[f"Q:{r.name}"]].copy()  # §9.7: arrivals A_ρ
    out[f"hold_{d.route}"] = Y[:, sysm.iH].copy()
    for f, k in sysm.fate_of.values():
        out[f"int_Qf_{f}{k}"] = Y[:, sysm.ix[f"RQ:{f}{k}"]].copy()  # release into each fate
    for g in w.degradations:
        out[f"int_D_{g.row}"] = Y[:, sysm.ix[f"D:{g.row}"]].copy()
    if w.recharging:
        out["int_J_C"] = Y[:, sysm.ix["JC"]].copy()
    if sysm.trackers:
        for x in ("CO", "LR", "DL"):
            for f in FATES:
                out[f"{x}_{f}"] = Y[:, sysm.ix[f"{x}:{f}"]].copy()
    out["G_minus_G0"] = np.array([sysm.G_minus_G0(y) for y in Y])
    for h in sysm.heat_classes:
        out[h] = Y[:, sysm.ix[h]].copy()
    chem = [sysm.chemistry(y) for y in Y]
    for key, name in (("x_tx", "dG_tx"), ("x_tl", "dG_tl"), ("x_rc", "dG_rc")):
        if key in chem[0]:
            out[name] = np.array([c[key] for c in chem]) * RT
    for p in sorted({r.product for r in sysm.routes if r.name != d.route}):
        out[f"dG_rel_{p}"] = np.array([c[f"x_rel:{p}"] for c in chem]) * RT
    for s in sysm.fates:
        out[f"dG_rel_{s}"] = np.array([c["lna"][s] for c in chem]) * RT  # §9.5's ΔG^rel_f
    for g in w.degradations:
        out[f"dG_deg_{g.row}"] = np.array([c[f"x_deg:{g.row}"] for c in chem]) * RT
    if w.regulator is not None:
        out["u"] = np.array([sysm.u_factor(y) for y in Y])
    return out


def identities(sysm: ReleaseSystem, ro: dict) -> dict:
    """§9.7's identities (and §4.8's) as (residual array, scale). Scales at t_end; a scale of 0
    (the blank's hold) leaves the residual absolute."""
    w, d = sysm.world, sysm.decl
    res = {}
    for q, M in w.pools.items():
        E = sum(ro[f"E_{r.name}"] for r in sysm.routes if r.pool == q)
        res[f"machines_{q}"] = (ro[f"F_{q}"] + E - M, M)
    for r in sysm.routes:
        S, Q, W = ro[f"int_S_{r.name}"], ro[f"int_Q_{r.name}"], ro[f"W_{r.name}"]
        res[f"residues_{r.name}"] = (r.r * S - W - r.L * Q, r.r * S[-1])
        Wdef = r.r * sum(j * ro[f"C_{r.name}_{j + 1}"] for j in range(r.m))
        res[f"W_definition_{r.name}"] = (W - Wdef, r.r * S[-1])
    for p in sorted({r.product for r in sysm.routes if r.name != d.route}):  # P: tl and tl_s
        Q = sum(ro[f"int_Q_{r.name}"] for r in sysm.routes if r.product == p)
        D = ro.get(f"int_D_{p}", 0.0)
        n = ro[f"n_{p}"]
        res[f"products_{p}"] = (n - n[0] - Q + D, n[0] + Q[-1])
    H, A = ro[f"hold_{d.route}"], ro[f"int_Q_{d.route}"]
    Hs = H[0] + A[-1]
    released = sum(ro[f"int_Qf_{f}{k}"] for f, k in sysm.fate_of.values())
    res["hold"] = (H[0] + A - H - released, Hs)
    attached_surviving_lost = H.copy()
    for s, (f, k) in sysm.fate_of.items():
        n, Qf, D = ro[f"n_{s}"], ro[f"int_Qf_{f}{k}"], ro[f"int_D_{s}"]
        res[f"fate_{s}"] = (n - n[0] - Qf + D, n[0] + Qf[-1])
        attached_surviving_lost = attached_surviving_lost + (n - n[0]) + D
    res["per_producer"] = (H[0] + A - attached_surviving_lost, Hs)
    for moiety, weights in sysm.moiety_weights().items():
        tot = 0.0
        for s, wt in weights.items():
            if s.startswith("W:"):
                v = ro[f"W_{s[2:]}"]
            elif s.startswith("H:"):
                v = ro[f"hold_{s[2:]}"]
            else:
                v = ro[f"n_{s}"]
            tot = tot + wt * v
        res[f"moiety_{moiety}"] = (tot - tot[0], float(tot[0]))
    Hsum = sum(ro[h] for h in sysm.heat_classes)
    res["energy"] = (ro["G_minus_G0"] + Hsum, float(Hsum[-1]))
    return res


def levels(ids: dict) -> dict:
    return {k: float(np.max(np.abs(r)) / abs(s)) if s else float(np.max(np.abs(r)))
            for k, (r, s) in ids.items()}


# ---- the requester's limit (§9.10), in decimal arithmetic -----------------------------------
def limit(p: float, times, prec: int = 50) -> dict:
    """§9.10's closed forms in copies (R1): hold, releases per fate, survivors per fate, and the
    window cohort over WINDOW sampled at each time ≥ its end; with k_e = 1/τ = ln 2/3600 s⁻¹."""
    with localcontext() as ctx:
        ctx.prec = prec
        ln2 = Decimal(2).ln()
        ke = ln2 / 3600
        kf = {"d": ln2 / 7200, "s": ln2 / 1800}
        pi = {"d": Decimal(repr(p)), "s": 1 - Decimal(repr(p))}
        H0 = Decimal(H0_COPIES)
        t2 = Decimal(repr(WINDOW[1]))
        out = {"hold": [], "released": [], **{f"released_{f}": [] for f in FATES},
               **{f"survivors_{f}": [] for f in FATES}, **{f"cohort_{f}": [] for f in FATES}}
        for t in times:
            T = Decimal(repr(float(t)))
            Ht = H0 * (-ke * T).exp()
            out["hold"].append(Ht)
            out["released"].append(H0 - Ht)
            for f in FATES:
                out[f"released_{f}"].append(pi[f] * (H0 - Ht))
                out[f"survivors_{f}"].append(
                    pi[f] * H0 * ke * ((-ke * T).exp() - (-kf[f] * T).exp()) / (kf[f] - ke))
                coh = (pi[f] * ke * H0 * (-kf[f] * T).exp() * (((kf[f] - ke) * t2).exp() - 1)
                       / (kf[f] - ke)) if T >= t2 else None
                out[f"cohort_{f}"].append(coh)
        return {k: [None if v is None else str(+v) for v in vals] for k, vals in out.items()}
