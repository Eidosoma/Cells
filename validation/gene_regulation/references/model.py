"""A's worlds (sheet §5.1, §5.2) and their full ODE (§4.7), with §6's readouts.

Written from the sheet's text alone. The motion table of §4.7 is assembled as a matrix over the
fluxes, so that each of the sheet's plants is the exact edit it names: an entry of a column, or a
term of a law.

States are deviations from the initial state, so that small changes of large rows keep their
digits: a row's amount is n_s = n_s(0) + δ_s and a pool's free machines F_q = M_q + δF_q. The
stage complexes C, the residues in transit W, the cumulative extents and the heat classes start at
zero. Amounts are in fmol, time in s, free energies in kJ/mol, heats in pJ (§0).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from decimal import Decimal

import numpy as np
from scipy.integrate import DOP853, Radau

from . import sheet

_NA = Decimal(sheet.N_A)
RT_KJ = float(_NA * Decimal(sheet.K_B) * Decimal(sheet.T_KELVIN) / 1000)  # kJ/mol
FMOL_PER_COPY = float(Decimal(10) ** 15 / _NA)  # fmol per molecule (§0)
C0_mM = float(sheet.C_STANDARD_mM)

# The plants. The sheet's (§5.4 for A1, §5.2 for A1-M) and the references' own (README).
SHEET_EDITS = {
    "m_tx_6": "§5.4 plant 1: m_tx = 6, so r_tx = 200 and κ_tx = v_tx/200",
    "v_tx_40": "§5.4 plant 2: v_tx = 40",
    "S_tl_fuel_zero": "§5.4 plant 3: the S_tl column's ATP, ADP and Pi entries are 0",
    "Q_tx_no_return": "§5.4 plant 4 / §5.2 plant 2: the Q_tx column's F_pol entry is 0",
    "u_squared": "§5.4 plant 5: u² in place of u in J^I_tx",
    "S_tl_A_49": "§5.4 plant 6: the S_tl column's A entry is −49",
    "init_total_machines": "§5.2 plant 1: J^I = λ M_q in place of λ F_q",
    "Q_tl_no_return": "§5.2 plant 2: the Q_tl column's F_rib entry is 0",
}
OWN_EDITS = {
    "rc_sign_flip": "own: recharging's law and heat read −E_rc in place of E_rc",
    "rc_share_1": "own: recharging's factor (1 − e^(ΔG_rc/RT)) in place of share 2",
    "deg_no_back": "own: degradation's per-residue factor dropped (J^D = k n)",
    "rel_heat_dropped": "own: H_tx does not book the release's −ΔG_rel,R",
    "per_chain_factor": "own: elongation's factor (1 − e^(r x)) in place of (1 − e^x)",
}
ALL_EDITS = {**SHEET_EDITS, **OWN_EDITS}


@dataclass(frozen=True)
class Route:
    name: str  # 'tx', 'tx1', 'tx2' or 'tl'
    kind: str  # 'tx' (transcription) or 'tl' (translation)
    pool: str  # 'pol' or 'rib'
    L: int  # chain length (nt or aa)
    m: int  # stages
    v: float  # residues per second
    k_I: float  # mM⁻¹ s⁻¹
    copies: int | None  # the gene's copies T (transcription); None for translation
    template_row: str | None  # the mRNA row (translation)
    product: str  # the row that a release writes
    regulated: bool  # u(t) multiplies this route's initiation (§4.6, §5.3)

    @property
    def r(self) -> int:
        if self.L % self.m:
            raise ValueError(f"{self.name}: m = {self.m} does not divide L = {self.L} (§2)")
        return self.L // self.m


@dataclass(frozen=True)
class Degradation:
    row: str
    k: float  # s⁻¹
    L: int  # residues per molecule
    monomer: str  # 'M' or 'A'
    residue: str  # 'R_res' or 'P_res'


@dataclass(frozen=True)
class World:
    name: str
    V: float  # pL
    rows0: dict  # row -> initial amount, fmol (held rows included)
    held: tuple  # rows that nothing writes
    pools: dict  # pool -> M_q, fmol
    routes: tuple
    degradations: tuple
    recharging: bool
    regulator: dict | None  # K_X, n_X, b_X, k_X
    phases: tuple  # ((t_start, t_stop, P_X), ...), P_X in fmol/s
    t_end: float
    dt: float
    window: float | None
    K: dict  # saturation constants, mM
    V_C: float  # mM/s
    lengths: dict  # polymer row -> residues per molecule (L_R, L_2 or L_P)

    def times(self) -> np.ndarray:
        n = int(round(self.t_end / self.dt))
        return np.arange(n + 1, dtype=float) * self.dt

    def P_X(self, t: float) -> float:
        for t0, t1, p in self.phases:
            if t0 <= t < t1:
                return p
        return self.phases[-1][2]


def _fl(x) -> float:
    return float(Decimal(str(x)))


def _K() -> dict:
    a = sheet.A1
    return {k: _fl(a[k]) for k in ("K_N_tx", "K_A_tl", "K_ATP_tl", "K_M_rc", "K_ATP_rc")}


def a1_world() -> World:
    """§5.1: one gene, open loop, the regulator through B1′'s factor, two phases."""
    a = sheet.A1
    V = _fl(a["V"])
    rows0 = {s: _fl(a["c_" + s]) * V for s in ("X", "N", "M", "A", "ATP", "ADP", "Pi", "R", "P")}
    pools = {"pol": _fl(a["M_pol"]) * FMOL_PER_COPY, "rib": _fl(a["M_rib"]) * FMOL_PER_COPY}
    routes = (
        Route("tx", "tx", "pol", a["L_R"], a["m_tx"], _fl(a["v_tx"]), _fl(a["k_I_tx"]),
              a["T_copies"], None, "R", True),
        Route("tl", "tl", "rib", a["L_P"], a["m_tl"], _fl(a["v_tl"]), _fl(a["k_I_tl"]),
              None, "R", "P", False),
    )
    degs = (Degradation("R", _fl(a["k_R"]), a["L_R"], "M", "R_res"),
            Degradation("P", _fl(a["k_P"]), a["L_P"], "A", "P_res"))
    reg = {"K_X": _fl(a["K_X"]), "n_X": a["n_X"], "b_X": _fl(a["b_X"]), "k_X": _fl(a["k_X"])}
    phases = ((0.0, float(a["t_off"]), _fl(a["P_on"])), (float(a["t_off"]), math.inf, 0.0))
    return World("A1", V, rows0, (), pools, routes, degs, True, reg, phases, float(a["t_end"]),
                 float(a["dt_out"]), None, _K(), _fl(a["V_C"]), {"R": a["L_R"], "P": a["L_P"]})


def _pol_rows(V: float, products: tuple) -> dict:
    a, m = sheet.A1, sheet.A1M
    rows0 = {p: _fl(a["c_R"]) * V for p in products}
    rows0.update({"N": _fl(m["c_N"]) * V, "M": _fl(a["c_M"]) * V, "ATP": _fl(a["c_ATP"]) * V,
                  "ADP": _fl(a["c_ADP"]) * V, "Pi": _fl(a["c_Pi"]) * V})
    return rows0


def pol_world(T: int) -> World:
    """§5.2: polymerase-limited, one world per copy number T. No translation, no regulator."""
    a, m = sheet.A1, sheet.A1M
    V = _fl(a["V"])
    routes = (Route("tx", "tx", "pol", a["L_R"], a["m_tx"], _fl(a["v_tx"]), _fl(m["k_I_tx"]), T,
                    None, "R", False),)
    degs = (Degradation("R", _fl(a["k_R"]), a["L_R"], "M", "R_res"),)
    pools = {"pol": _fl(m["M_pol"]) * FMOL_PER_COPY}
    return World(f"pol T={T}", V, _pol_rows(V, ("R",)), (), pools,
                 routes, degs, True, None, ((0.0, math.inf, 0.0),), float(m["t_end_pol"]),
                 float(m["dt_pol"]), float(m["window_pol"]), _K(), _fl(a["V_C"]), {"R": a["L_R"]})


def two_gene_world() -> World:
    """§5.2: gene 1 (T_1 = 10, 1200 nt) and gene 2 (T_2 = 5, 2400 nt) share 100 polymerases."""
    a, m = sheet.A1, sheet.A1M
    V = _fl(a["V"])
    routes = (Route("tx1", "tx", "pol", a["L_R"], a["m_tx"], _fl(a["v_tx"]), _fl(m["k_I_tx"]),
                    m["T_1"], None, "R1", False),
              Route("tx2", "tx", "pol", m["L_2"], a["m_tx"], _fl(a["v_tx"]), _fl(m["k_I_tx"]),
                    m["T_2"], None, "R2", False))
    degs = (Degradation("R1", _fl(a["k_R"]), a["L_R"], "M", "R_res"),
            Degradation("R2", _fl(a["k_R"]), m["L_2"], "M", "R_res"))
    return World("two-gene", V, _pol_rows(V, ("R1", "R2")), (),
                 {"pol": _fl(m["M_pol"]) * FMOL_PER_COPY}, routes, degs, True, None,
                 ((0.0, math.inf, 0.0),), float(m["t_end_pol"]), float(m["dt_pol"]),
                 float(m["window_pol"]), _K(), _fl(a["V_C"]), {"R1": a["L_R"], "R2": m["L_2"]})


def rib_world(n_R: int) -> World:
    """§5.2: ribosome-limited, the mRNA held at n_R copies. No recharging (no N or M rows)."""
    a, m = sheet.A1, sheet.A1M
    V = _fl(a["V"])
    rows0 = {"R": n_R * FMOL_PER_COPY, "P": _fl(a["c_P"]) * V, "A": _fl(m["c_A"]) * V,
             "ATP": _fl(a["c_ATP"]) * V, "ADP": _fl(a["c_ADP"]) * V, "Pi": _fl(a["c_Pi"]) * V}
    routes = (Route("tl", "tl", "rib", a["L_P"], a["m_tl"], _fl(a["v_tl"]), _fl(m["k_I_tl"]),
                    None, "R", "P", False),)
    degs = (Degradation("P", _fl(a["k_P"]), a["L_P"], "A", "P_res"),)
    return World(f"rib n_R={n_R}", V, rows0, ("R",), {"rib": _fl(m["M_rib"]) * FMOL_PER_COPY},
                 routes, degs, False, None, ((0.0, math.inf, 0.0),), float(m["t_end_rib"]),
                 float(m["dt_rib"]), float(m["window_rib"]), _K(), _fl(a["V_C"]),
                 {"R": a["L_R"], "P": a["L_P"]})


def all_worlds() -> list[World]:
    return [a1_world(), *[pol_world(T) for T in sheet.SWEEP_T], two_gene_world(),
            *[rib_world(n) for n in sheet.SWEEP_NR]]


def mu0_RT(pot: sheet.Potentials) -> dict:
    """Standard potentials in RT units at c° = 1 M (§3.3), from the four symbols.

    The test instance's convention μ′°/RT = 0 for ADP, Pi, M and A is used for every set; only the
    moves' ΔG enter the laws, and every readout (G(t) − G(0) included) is independent of it.
    Residues carry their per-residue potential.
    """
    f = pot.as_float()
    g = f["G_ATP"] / RT_KJ
    mu = {"ADP": 0.0, "Pi": 0.0, "M": 0.0, "A": 0.0}
    mu["ATP"] = mu["ADP"] + mu["Pi"] - g  # ΔG′°_ATP = μ_ADP + μ_Pi − μ_ATP
    mu["N"] = f["E_rc_RT"] + mu["M"] + 2 * mu["ATP"] - 2 * mu["ADP"]  # E_rc: M + 2ATP → N + 2ADP
    mu["R_res"] = mu["M"] - f["E_pd"] / RT_KJ  # E_pd: R_res → M
    mu["P_res"] = mu["A"] - f["E_pep"] / RT_KJ  # E_pep: P_res → A
    return mu


class System:
    """One world's full ODE at one potential set, with an optional set of plant edits."""

    HEAT_CLASSES = ("H_tx", "H_tl", "H_deg_R", "H_deg_P", "H_rc")

    def __init__(self, world: World, pot: sheet.Potentials, edits=frozenset()):
        unknown = set(edits) - set(ALL_EDITS)
        if unknown:
            raise ValueError(f"unknown edits {sorted(unknown)}")
        self.edits = frozenset(edits)
        routes = []
        for r in world.routes:
            if r.kind == "tx" and "m_tx_6" in self.edits:
                r = replace(r, m=6)
            if r.kind == "tx" and "v_tx_40" in self.edits:
                r = replace(r, v=40.0)
            routes.append(r)
        self.world = world
        self.routes = tuple(routes)
        self.pot = pot
        self.mu0 = mu0_RT(pot)
        self.V = world.V
        self.rows = [s for s in world.rows0 if s not in world.held]
        self.held = {s: world.rows0[s] for s in world.held}
        self.n0 = np.array([world.rows0[s] for s in self.rows])
        self.L_of = dict(world.lengths)
        for r in self.routes:  # a plant's own stage count never changes L
            assert self.L_of[r.product] == r.L
        self.iX = self.rows.index("X") if "X" in self.rows else None
        self.e_rc = float(pot.E_rc_RT)
        names = [f"d:{s}" for s in self.rows] + [f"dF:{q}" for q in world.pools]
        for r in self.routes:
            names += [f"C:{r.name}:{j}" for j in range(1, r.m + 1)]
        names += [f"W:{r.name}" for r in self.routes]
        for r in self.routes:
            names += [f"I:{r.name}", f"S:{r.name}", f"Q:{r.name}"]
        names += [f"D:{d.row}" for d in world.degradations]
        if world.recharging:
            names.append("JC")
        heat = {"H_tx": any(r.kind == "tx" for r in self.routes),
                "H_tl": any(r.kind == "tl" for r in self.routes),
                "H_deg_R": any(d.monomer == "M" for d in world.degradations),
                "H_deg_P": any(d.monomer == "A" for d in world.degradations),
                "H_rc": world.recharging}
        self.heat_classes = [h for h in self.HEAT_CLASSES if heat[h]]
        names += self.heat_classes
        self.names = names
        self.ix = {n: i for i, n in enumerate(names)}
        self.ns = len(names)
        # Fluxes, in order: initiations, stage exits, degradations, recharging.
        fl = [f"J_I:{r.name}" for r in self.routes]
        for r in self.routes:
            fl += [f"J:{r.name}:{j}" for j in range(1, r.m + 1)]
        fl += [f"D:{d.row}" for d in world.degradations]
        if world.recharging:
            fl.append("J_C")
        self.flux_names = fl
        self.fx = {n: i for i, n in enumerate(fl)}
        self.N = self._motion_matrix()

    # §4.7's motion table, column by column, with the plants' entry edits.
    def columns(self, r: Route) -> tuple[dict, dict, dict]:
        rr = r.r
        initiation = {f"dF:{r.pool}": -1.0}
        if r.kind == "tx":
            exit_col = {f"W:{r.name}": rr, "d:N": -rr, "d:Pi": 2 * rr}
        else:
            exit_col = {f"W:{r.name}": rr, "d:A": -rr, "d:ATP": -4 * rr, "d:ADP": 4 * rr,
                        "d:Pi": 4 * rr}
            if "S_tl_fuel_zero" in self.edits:
                exit_col.update({"d:ATP": 0.0, "d:ADP": 0.0, "d:Pi": 0.0})
            if "S_tl_A_49" in self.edits:
                exit_col["d:A"] = -49.0
        release = {f"W:{r.name}": -r.L, f"d:{r.product}": 1.0, f"dF:{r.pool}": 1.0}
        if (r.kind == "tx" and "Q_tx_no_return" in self.edits) or (
                r.kind == "tl" and "Q_tl_no_return" in self.edits):
            release[f"dF:{r.pool}"] = 0.0
        return initiation, exit_col, release

    def _motion_matrix(self) -> np.ndarray:
        N = np.zeros((self.ns, len(self.flux_names)))

        def put(col: int, entries: dict):
            for name, c in entries.items():
                if name in self.ix:  # rows absent from a world are not written
                    N[self.ix[name], col] += c

        for r in self.routes:
            ini, ex, rel = self.columns(r)
            c = self.fx[f"J_I:{r.name}"]
            put(c, ini)
            N[self.ix[f"C:{r.name}:1"], c] += 1.0
            N[self.ix[f"I:{r.name}"], c] += 1.0
            for j in range(1, r.m + 1):
                c = self.fx[f"J:{r.name}:{j}"]
                N[self.ix[f"C:{r.name}:{j}"], c] -= 1.0
                put(c, ex)
                N[self.ix[f"S:{r.name}"], c] += 1.0
                if j < r.m:
                    N[self.ix[f"C:{r.name}:{j + 1}"], c] += 1.0
                else:
                    put(c, rel)
                    N[self.ix[f"Q:{r.name}"], c] += 1.0
        for d in self.world.degradations:
            c = self.fx[f"D:{d.row}"]
            put(c, {f"d:{d.row}": -1.0, f"d:{d.monomer}": float(d.L), f"D:{d.row}": 1.0})
        if self.world.recharging:
            put(self.fx["J_C"], {"d:M": -1.0, "d:ATP": -2.0, "d:N": 1.0, "d:ADP": 2.0, "JC": 1.0})
        return N

    # ---- the state's chemistry -------------------------------------------------------------
    def amounts(self, y: np.ndarray) -> dict:
        amt = dict(self.held)
        for i, s in enumerate(self.rows):
            amt[s] = self.n0[i] + y[i]
        return amt

    def chemistry(self, y: np.ndarray, amt: dict | None = None) -> dict:
        """Potentials (RT units) and each move's ΔG/RT (§3.4) at the state y."""
        if amt is None:
            amt = self.amounts(y)
        mu0 = self.mu0
        lna = {s: math.log(amt[s] / self.V / C0_mM) for s in amt if s != "X"}
        mu = {}
        for s, la in lna.items():
            mu[s] = (self.L_of[s] * mu0["R_res" if s.startswith("R") else "P_res"] + la
                     if s in self.L_of else mu0[s] + la)
        ch = {"lna": lna, "mu": mu}
        kinds = {r.kind for r in self.routes}
        if "tx" in kinds:
            ch["x_tx"] = mu0["R_res"] + 2 * mu["Pi"] - mu["N"]
        if "tl" in kinds:
            ch["x_tl"] = mu0["P_res"] + 4 * mu["ADP"] + 4 * mu["Pi"] - mu["A"] - 4 * mu["ATP"]
        for r in self.routes:
            ch[f"x_rel:{r.product}"] = mu[r.product] - r.L * mu0[
                "R_res" if r.kind == "tx" else "P_res"]  # = ln a_product
        for d in self.world.degradations:
            ch[f"x_deg:{d.row}"] = d.L * mu[d.monomer] - mu[d.row]  # per molecule
        if self.world.recharging:
            ch["x_rc"] = mu["N"] + 2 * mu["ADP"] - mu["M"] - 2 * mu["ATP"]
        return ch

    def u_factor(self, y: np.ndarray) -> float:
        reg = self.world.regulator
        if reg is None:
            return 1.0
        c = (self.n0[self.iX] + y[self.iX]) / self.V
        hill = c ** reg["n_X"] / (reg["K_X"] ** reg["n_X"] + c ** reg["n_X"])
        return reg["b_X"] + (1.0 - reg["b_X"]) * hill

    def fluxes(self, y: np.ndarray, amt: dict | None = None, ch: dict | None = None):
        """Every flux of §4.7 (fmol/s) and the heat rates of §3.4 (pJ/s)."""
        if amt is None:
            amt = self.amounts(y)
        if ch is None:
            ch = self.chemistry(y, amt)
        V, K, E = self.V, self.world.K, self.edits
        c = {s: amt[s] / V for s in amt}
        J = np.empty(len(self.flux_names))
        heat = dict.fromkeys(self.heat_classes, 0.0)
        u = self.u_factor(y)
        k = 0
        for r in self.routes:
            uu = (u * u if "u_squared" in E else u) if r.regulated else 1.0
            c_T = (r.copies * FMOL_PER_COPY / V) if r.kind == "tx" else c[r.template_row]
            machines = (self.world.pools[r.pool] if "init_total_machines" in E
                        else self.world.pools[r.pool] + y[self.ix[f"dF:{r.pool}"]])
            J[k] = uu * r.k_I * c_T * machines
            k += 1
        for r in self.routes:
            x = ch["x_tx"] if r.kind == "tx" else ch["x_tl"]
            if r.kind == "tx":
                sat = c["N"] / (K["K_N_tx"] + c["N"])
            else:
                sat = c["A"] / (K["K_A_tl"] + c["A"]) * c["ATP"] / (K["K_ATP_tl"] + c["ATP"])
            phi = sat * -math.expm1(r.r * x if "per_chain_factor" in E else x)
            kap = r.v / r.r
            i0 = self.ix[f"C:{r.name}:1"]
            stage = kap * phi * y[i0:i0 + r.m]
            J[k:k + r.m] = stage
            k += r.m
            S, Q = float(stage.sum()), float(stage[-1])
            cls = "H_tx" if r.kind == "tx" else "H_tl"
            heat[cls] += r.r * S * (-x * RT_KJ)
            if not (r.kind == "tx" and "rel_heat_dropped" in E):
                heat[cls] += Q * (-ch[f"x_rel:{r.product}"] * RT_KJ)
        for d in self.world.degradations:
            xd = ch[f"x_deg:{d.row}"]
            back = 1.0 if "deg_no_back" in E else -math.expm1(xd / d.L)
            J[k] = d.k * amt[d.row] * back
            heat["H_deg_R" if d.monomer == "M" else "H_deg_P"] += J[k] * (-xd * RT_KJ)
            k += 1
        if self.world.recharging:
            x_rc = ch["x_rc"] - (2 * self.e_rc if "rc_sign_flip" in E else 0.0)
            share = 1.0 if "rc_share_1" in E else 2.0
            J[k] = (V * self.world.V_C * c["M"] / (K["K_M_rc"] + c["M"])
                    * c["ATP"] / (K["K_ATP_rc"] + c["ATP"]) * -math.expm1(x_rc / share))
            heat["H_rc"] += J[k] * (-x_rc * RT_KJ)
        return J, heat, u

    def rhs(self, t: float, y: np.ndarray, P_X: float) -> np.ndarray:
        J, heat, _ = self.fluxes(y)
        dy = self.N @ J
        for h, v in heat.items():
            dy[self.ix[h]] = v
        if self.world.regulator is not None:
            iX = self.iX
            dy[iX] = P_X - self.world.regulator["k_X"] * (self.n0[iX] + y[iX])
        return dy

    def affinities(self, y: np.ndarray) -> dict:
        """The per-residue affinity of every one-sided move (§3.5), for the domain."""
        ch = self.chemistry(y)
        out = {}
        if "x_tx" in ch:
            out["x_tx"] = ch["x_tx"]
        if "x_tl" in ch:
            out["x_tl"] = ch["x_tl"]
        for d in self.world.degradations:
            out[f"y_{d.row}"] = ch[f"x_deg:{d.row}"] / d.L
        return out

    # ---- G and the identities ---------------------------------------------------------------
    def G_minus_G0(self, y: np.ndarray) -> float:
        """G(t) − G(0) of §3.4 in pJ, in deviation form so that its digits survive.

        n(μ° + RT(ln a − 1)) − n0(μ° + RT(ln a0 − 1)) = δ(μ° + RT(ln a − 1)) + n0 RT ln(1 + δ/n0).
        Held rows have δ = 0; X is outside G.
        """
        amt = self.amounts(y)
        mu0 = self.mu0
        total = 0.0
        for i, s in enumerate(self.rows):
            if s == "X":
                continue
            n0, d = self.n0[i], y[i]
            m0 = (self.L_of[s] * mu0["R_res" if s.startswith("R") else "P_res"]
                  if s in self.L_of else mu0[s])
            lna = math.log(amt[s] / self.V / C0_mM)
            total += d * (m0 + lna - 1.0) + n0 * math.log1p(d / n0)
        for r in self.routes:
            total += mu0["R_res" if r.kind == "tx" else "P_res"] * y[self.ix[f"W:{r.name}"]]
        return total * RT_KJ

    def moiety_weights(self) -> dict:
        """§1.4's weights over this world's states: rows (as d:), residues in transit (as W:)."""
        out = {}
        for moiety, table in sheet.MOIETIES.items():
            w = {}
            for key, val in table.items():
                if key in ("R", "P"):
                    for s in self.L_of:
                        if (s.startswith("R") and key == "R") or (s == "P" and key == "P"):
                            w[s] = float(self.L_of[s])
                elif key in ("R_res", "P_res"):
                    for r in self.routes:
                        if (r.kind == "tx") == (key == "R_res"):
                            w[f"W:{r.name}"] = float(val)
                else:
                    w[key] = float(val)
            w = {s: v for s, v in w.items() if s in self.world.rows0 or s in self.ix}
            if w:
                out[moiety] = w
        return out


# ---- integration -----------------------------------------------------------------------------
METHODS = {"DOP853": DOP853, "Radau": Radau}


def _a_priori_scales(sysm: System) -> np.ndarray:
    s = np.empty(sysm.ns)
    for n, i in sysm.ix.items():
        kind, _, rest = n.partition(":")
        if kind == "d":
            n0 = sysm.n0[sysm.rows.index(rest)]
            s[i] = n0 if rest in ("R", "R1", "R2", "P", "X") else 1e-4 * n0
        elif n.startswith("H_"):
            s[i] = 1e-3
        else:
            s[i] = FMOL_PER_COPY
    return s


def integrate(sysm: System, method: str = "DOP853", rtol: float = 1e-11,
              scales: np.ndarray | None = None, track_steps: bool = True) -> dict:
    """Solve the world over its output grid, restarting at every output so each is hit exactly.

    atol_i = rtol × scale_i, with scale_i the state's largest magnitude in a coarse first solve
    (`scales`), so that the absolute and relative tolerances shrink together.
    """
    times = sysm.world.times()
    if scales is None:
        scales = _a_priori_scales(sysm)
    atol = rtol * scales
    cls = METHODS[method]
    Y = np.zeros((len(times), sysm.ns))
    y = np.zeros(sysm.ns)
    h_next = None
    steps = 0
    nfev = 0
    dom = {}
    if track_steps:  # the initial state is part of the trajectory's domain
        dom = {key: (val, 0.0) for key, val in sysm.affinities(y).items()}
    heat_prev = None
    heat_min_increment = dict.fromkeys(sysm.heat_classes, math.inf)
    for k in range(1, len(times)):
        t0, t1 = times[k - 1], times[k]
        P_X = sysm.world.P_X(t0)

        def fun(t, yy, P_X=P_X):
            return sysm.rhs(t, yy, P_X)

        kw = {"rtol": rtol, "atol": atol}
        if h_next is not None:
            kw["first_step"] = min(h_next, t1 - t0)
        solver = cls(fun, t0, y, t1, **kw)
        while solver.status == "running":
            h_save = solver.h_abs
            msg = solver.step()
            if solver.status == "failed":
                raise RuntimeError(f"{sysm.world.name} {method} rtol={rtol}: {msg} at t={solver.t}")
            steps += 1
            if track_steps:
                for key, val in sysm.affinities(solver.y).items():
                    if val > dom.get(key, (-math.inf,))[0]:
                        dom[key] = (val, float(solver.t))
                hv = {h: solver.y[sysm.ix[h]] for h in sysm.heat_classes}
                if heat_prev is not None:
                    for h in hv:
                        heat_min_increment[h] = min(heat_min_increment[h], hv[h] - heat_prev[h])
                heat_prev = hv
        nfev += solver.nfev
        if h_save is not None and h_save > 0:
            h_next = h_save
        y = solver.y.copy()
        Y[k] = y
    return {"times": times, "Y": Y, "method": method, "rtol": rtol, "atol": atol,
            "steps": steps, "nfev": nfev, "domain_steps": dom,
            "heat_min_increment": heat_min_increment, "scales": scales}


def state_scales(sysm: System, rtol0: float = 1e-8) -> np.ndarray:
    """Each state's largest magnitude over the horizon, from a coarse solve (floored)."""
    sol = integrate(sysm, "DOP853", rtol0, _a_priori_scales(sysm), track_steps=False)
    s = np.max(np.abs(sol["Y"]), axis=0)
    floor = 1e-6 * _a_priori_scales(sysm)
    return np.maximum(s, floor)


# ---- readouts ---------------------------------------------------------------------------------
def readouts(sysm: System, sol: dict) -> dict:
    """§6's readouts at every output, as arrays (fmol, pJ, kJ/mol, s)."""
    w = sysm.world
    times, Y = sol["times"], sol["Y"]
    out = {"t": times.copy()}
    for s in w.rows0:
        if s in w.held:
            out[f"n_{s}"] = np.full(len(times), w.rows0[s])
        else:
            out[f"n_{s}"] = sysm.n0[sysm.rows.index(s)] + Y[:, sysm.ix[f"d:{s}"]]
    for q, M in w.pools.items():
        out[f"F_{q}"] = M + Y[:, sysm.ix[f"dF:{q}"]]
    for r in sysm.routes:
        i0 = sysm.ix[f"C:{r.name}:1"]
        for j in range(r.m):
            out[f"C_{r.name}_{j + 1}"] = Y[:, i0 + j].copy()
        out[f"E_{r.name}"] = Y[:, i0:i0 + r.m].sum(axis=1)
        out[f"W_{r.name}"] = Y[:, sysm.ix[f"W:{r.name}"]].copy()
        out[f"int_J_I_{r.name}"] = Y[:, sysm.ix[f"I:{r.name}"]].copy()
        out[f"int_S_{r.name}"] = Y[:, sysm.ix[f"S:{r.name}"]].copy()
        out[f"int_Q_{r.name}"] = Y[:, sysm.ix[f"Q:{r.name}"]].copy()
    for d in w.degradations:
        out[f"int_D_{d.row}"] = Y[:, sysm.ix[f"D:{d.row}"]].copy()
    if w.recharging:
        out["int_J_C"] = Y[:, sysm.ix["JC"]].copy()
    out["G_minus_G0"] = np.array([sysm.G_minus_G0(y) for y in Y])
    for h in sysm.heat_classes:
        out[h] = Y[:, sysm.ix[h]].copy()
    # Each move's ΔG at the outputs (§3.4), kJ/mol per unit of progress, and the heat rates.
    chem = [sysm.chemistry(y) for y in Y]
    for key, name in (("x_tx", "dG_tx"), ("x_tl", "dG_tl"), ("x_rc", "dG_rc")):
        if key in chem[0]:
            out[name] = np.array([c[key] for c in chem]) * RT_KJ
    for r in sysm.routes:
        out[f"dG_rel_{r.product}"] = np.array([c[f"x_rel:{r.product}"] for c in chem]) * RT_KJ
    for d in w.degradations:
        out[f"dG_deg_{d.row}"] = np.array([c[f"x_deg:{d.row}"] for c in chem]) * RT_KJ
    rates = [sysm.fluxes(y)[1] for y in Y]
    for h in sysm.heat_classes:
        out[f"rate_{h}"] = np.array([rr[h] for rr in rates])
    if w.regulator is not None:
        out["u"] = np.array([sysm.u_factor(y) for y in Y])
    if w.window is not None:
        k_end = len(times) - 1
        k_w = int(round((w.t_end - w.window) / w.dt))
        for r in sysm.routes:
            q = out[f"int_Q_{r.name}"]
            out[f"J_bar_{r.name}"] = np.array([(q[k_end] - q[k_w]) / w.window])
    return out


def identities(sysm: System, ro: dict) -> dict:
    """§4.8's identities (and W's definition, §1.2) as residual arrays with their scales.

    Scales (the lead's reading 1, recorded in the README): machines and moieties use their
    conserved totals; the residue identity r∫S(t_end); the product identity n(0) + ∫Q(t_end);
    G's identity ΣH(t_end).
    """
    w = sysm.world
    res = {}
    for q, M in w.pools.items():
        E = sum(ro[f"E_{r.name}"] for r in sysm.routes if r.pool == q)
        res[f"machines_{q}"] = (ro[f"F_{q}"] + E - M, M)
    for r in sysm.routes:
        S, Q, W = ro[f"int_S_{r.name}"], ro[f"int_Q_{r.name}"], ro[f"W_{r.name}"]
        res[f"residues_{r.name}"] = (r.r * S - W - r.L * Q, r.r * S[-1])
        Wdef = r.r * sum(j * ro[f"C_{r.name}_{j + 1}"] for j in range(r.m))
        res[f"W_definition_{r.name}"] = (W - Wdef, r.r * S[-1])
    for r in sysm.routes:
        p = r.product
        D = ro[f"int_D_{p}"] if f"int_D_{p}" in ro else 0.0
        n = ro[f"n_{p}"]
        res[f"products_{p}"] = (n - n[0] - ro[f"int_Q_{r.name}"] + D,
                                n[0] + ro[f"int_Q_{r.name}"][-1])
    for moiety, weights in sysm.moiety_weights().items():
        tot = 0.0
        for s, wt in weights.items():
            tot = tot + wt * (ro[f"W_{s[2:]}"] if s.startswith("W:") else ro[f"n_{s}"])
        res[f"moiety_{moiety}"] = (tot - tot[0], float(tot[0]))
    H = sum(ro[h] for h in sysm.heat_classes)
    res["energy"] = (ro["G_minus_G0"] + H, float(H[-1]))
    return res
